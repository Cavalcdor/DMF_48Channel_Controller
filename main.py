"""
DMF 48-通道控制器主应用程序
PyQt5 界面，整合串口通信、电极网格、寻路算法
"""

import sys
from collections import Counter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QGroupBox, QMessageBox,
    QSizePolicy, QSpinBox, QLineEdit, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from src import global_cfg
from src.serial_driver import SerialThread
from src.grid_widget import ElectrodeGrid
from src.path_algorithm import a_star_shortest_path, path_to_indices, plan_multiple_paths
from src.splash_screen import SplashManager, VERSION, AUTHOR, YEAR
from src.about_dialog import AboutDialog
from src.auto_update import check_for_update
from src.dashboard import DashboardWidget
from src.log_panel import LogPanel
from src.settings import SettingsWidget
from src.project_manager import ProjectManager


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48通道控制器")
        self.setGeometry(50, 50, 1800, 960)
        self.setMinimumSize(1200, 700)
        self.showMaximized()

        # ============ 初始化模块 ============
        self.serial_thread = SerialThread()
        self.grid_widget = ElectrodeGrid()
        self.is_running = False
        self.current_droplet_index = 0  # 液滴在当前路径上的步索引
        self.current_path = []  # 当前正在执行的路径
        self.droplet_plans = []  # 所有液滴的规划结果 [{'path':..., 'droplet_id':..., ...}]
        self.current_plan_index = 0  # 当前执行到第几个液滴的路径
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.move_droplet_step)

        # ============ 连接串口信号 ============
        self.serial_thread.data_received.connect(self.on_serial_data)
        self.serial_thread.error.connect(self.on_serial_error)
        self.serial_thread.port_opened.connect(self.on_port_opened)

        # ============ 连接网格信号 ============
        self.grid_widget.droplet_config_changed.connect(self.update_droplet_info)
        self.grid_widget.mode_changed.connect(self.on_mode_changed)

        # ============ 应用全局样式 ============
        self.apply_stylesheet()

        # ============ 状态变量 ============
        self.serial_connected = False
        self.droplet_position = None

        # ============ 创建 UI ============
        self.init_ui()

        # 初始化液滴信息显示
        self.update_droplet_info()

    def apply_stylesheet(self):
        """应用全局 QSS 样式表（商业级设计系统）。"""
        stylesheet = """
        /* ========== 全局基调 ========== */
        QMainWindow, QWidget#central_widget {
            background-color: #f0f2f5;
        }

        /* 顶部标题栏 */
        QWidget#app_header {
            background-color: #1a2332;
            border-bottom: 2px solid #2d3e50;
        }

        /* 透明容器 */
        QWidget#left_sidebar,
        QWidget#center_widget,
        QWidget#right_sidebar {
            background-color: transparent;
        }

        /* 网格卡片 */
        QWidget#grid_card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
        }
        QWidget {
            font-family: "Microsoft YaHei", "Segoe UI", -apple-system, Arial, sans-serif;
            font-size: 15px;
        }

        /* ========== GroupBox 卡片容器 ========== */
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            margin-top: 10px;
            padding-top: 14px;
            padding-left: 14px;
            padding-right: 14px;
            padding-bottom: 14px;
            font-size: 15px;
            font-weight: 600;
            color: #0f172a;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 16px;
            padding: 0 8px;
            font-size: 16px;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: 0.3px;
        }

        /* ========== 统一按钮体系 ========== */
        /* 基础按钮 — 中性灰色边框, 所有按钮继承此风格 */
        QPushButton {
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 15px;
            font-weight: 600;
            color: #374151;
            background-color: #ffffff;
        }
        QPushButton:hover {
            background-color: #f3f4f6;
            border-color: #9ca3af;
        }
        QPushButton:pressed {
            background-color: #e5e7eb;
        }
        QPushButton:disabled {
            background-color: #f3f4f6;
            color: #9ca3af;
            border-color: #e5e7eb;
        }

        /* 柔和次级按钮 — 通用中性风格 */
        QPushButton#soft_btn {
            background-color: #ffffff;
            color: #374151;
            border: 1px solid #d1d5db;
        }
        QPushButton#soft_btn:hover {
            background-color: #f3f4f6;
            border-color: #9ca3af;
        }
        QPushButton#soft_btn:pressed {
            background-color: #e5e7eb;
        }
        QPushButton#soft_btn:checked {
            background-color: #e5e7eb;
            border: 1px solid #9ca3af;
        }

        /* 起点/终点模式按钮 — 浅蓝底, 选中变深蓝 */
        QPushButton#mode_sd_btn {
            background-color: #eef2ff;
            color: #4338ca;
            border: 1px solid #c7d2fe;
        }
        QPushButton#mode_sd_btn:hover {
            background-color: #e0e7ff;
            border-color: #a5b4fc;
        }
        QPushButton#mode_sd_btn:pressed {
            background-color: #c7d2fe;
        }
        QPushButton#mode_sd_btn:checked {
            background-color: #4f46e5;
            border: none;
            color: #ffffff;
        }

        /* 障碍物模式按钮 — 浅灰底, 选中变深灰 */
        QPushButton#mode_obstacle_btn {
            background-color: #f3f4f6;
            color: #374151;
            border: 1px solid #d1d5db;
        }
        QPushButton#mode_obstacle_btn:hover {
            background-color: #e5e7eb;
            border-color: #9ca3af;
        }
        QPushButton#mode_obstacle_btn:pressed {
            background-color: #d1d5db;
        }
        QPushButton#mode_obstacle_btn:checked {
            background-color: #374151;
            border: none;
            color: #ffffff;
        }

        /* 规划路径按钮 — 蓝色, 规划/预览操作 */
        QPushButton#accent_btn {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
        }
        QPushButton#accent_btn:hover {
            background-color: #3b82f6;
        }
        QPushButton#accent_btn:pressed {
            background-color: #1d40af;
        }
        QPushButton#accent_btn:disabled {
            background-color: #93c5fd;
            color: #ffffff;
        }

        /* 运行路径按钮 — 绿色, 启动/执行操作 */
        QPushButton#success_btn {
            background-color: #059669;
            color: #ffffff;
            border: none;
        }
        QPushButton#success_btn:hover {
            background-color: #10b981;
        }
        QPushButton#success_btn:pressed {
            background-color: #047857;
        }
        QPushButton#success_btn:disabled {
            background-color: #6ee7b7;
            color: #ffffff;
        }

        /* 停止按钮 — 亮红, 紧急停止操作 */
        QPushButton#danger_btn {
            background-color: #e53935;
            color: #ffffff;
            border: none;
        }
        QPushButton#danger_btn:hover {
            background-color: #ef5350;
        }
        QPushButton#danger_btn:pressed {
            background-color: #c62828;
        }
        QPushButton#danger_btn:disabled {
            background-color: #ef9a9a;
            color: #ffffff;
        }

        /* ========== 输入控件 ========== */

        QLineEdit {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 8px 12px;
            background-color: #ffffff;
            color: #0f172a;
            font-size: 15px;
        }
        QLineEdit:focus {
            border-color: #93c5fd;
        }

        QSpinBox {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 6px 10px;
            background-color: #ffffff;
            color: #0f172a;
            font-size: 15px;
        }
        QSpinBox:focus {
            border-color: #93c5fd;
        }

        /* ========== 标签 ========== */
        QLabel {
            color: #0f172a;
            font-size: 15px;
        }
        QLabel[helper="true"] {
            color: #64748b;
            font-size: 14px;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        """初始化用户界面。"""
        central_widget = QWidget()
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)

        # ============ 外层垂直布局: 标题栏 + 主内容 ============
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ---------- 顶部标题栏 ----------
        header = QWidget()
        header.setObjectName("app_header")
        header.setFixedHeight(52)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        icon_label = QLabel("⚡")
        icon_label.setStyleSheet("font-size: 28px; color: #4fc3f7; background: transparent;")
        header_layout.addWidget(icon_label)

        title_label = QLabel("DMF 48通道控制器")
        title_label.setStyleSheet("""
            font-size: 22px;
            font-weight: 700;
            color: #ffffff;
            background: transparent;
            letter-spacing: 1px;
        """)
        header_layout.addWidget(title_label)

        # ---------- 工程工具栏 ----------
        project_btn_style = """
            QPushButton {
                color: #94a3b8; background: transparent;
                border: 1px solid #334155; border-radius: 6px;
                padding: 4px 12px; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover {
                color: #e2e8f0; border-color: #64748b;
                background: rgba(255,255,255,0.05);
            }
        """
        new_btn = QPushButton("📄 新建")
        new_btn.setStyleSheet(project_btn_style)
        new_btn.clicked.connect(self._project_new)
        header_layout.addWidget(new_btn)

        open_btn = QPushButton("📂 打开")
        open_btn.setStyleSheet(project_btn_style)
        open_btn.clicked.connect(self._project_open)
        header_layout.addWidget(open_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet(project_btn_style)
        save_btn.clicked.connect(self._project_save)
        header_layout.addWidget(save_btn)

        # 分隔
        sep = QLabel("|")
        sep.setStyleSheet("color: #334155; background: transparent; font-size: 16px; padding: 0 4px;")
        header_layout.addWidget(sep)

        header_layout.addStretch()

        # ---------- 菜单按钮 ----------
        about_btn = QPushButton("关于")
        about_btn.setStyleSheet("""
            QPushButton {
                color: #94a3b8;
                background: transparent;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #e2e8f0;
                border-color: #64748b;
                background: rgba(255,255,255,0.05);
            }
        """)
        about_btn.clicked.connect(lambda: AboutDialog(self).exec_())
        header_layout.addWidget(about_btn)

        update_btn = QPushButton("检查更新")
        update_btn.setStyleSheet("""
            QPushButton {
                color: #94a3b8;
                background: transparent;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #4fc3f7;
                border-color: #4fc3f7;
                background: rgba(79, 195, 247, 0.08);
            }
        """)
        update_btn.clicked.connect(lambda: check_for_update(self, silent=False))
        header_layout.addWidget(update_btn)

        self.header_status_label = QLabel("● 系统就绪")
        self.header_status_label.setStyleSheet("""
            font-size: 14px;
            color: #4ade80;
            background: rgba(74, 222, 128, 0.1);
            padding: 4px 14px;
            border: 1px solid #4ade80;
            border-radius: 12px;
        """)
        header_layout.addWidget(self.header_status_label)

        outer_layout.addWidget(header)

        # ============ Tab 多界面 ============
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("main_tabs")
        self.tab_widget.setStyleSheet("""
            QTabWidget#main_tabs::pane {
                border: none; background: transparent;
            }
            QTabBar::tab {
                background: #ffffff; color: #64748b;
                border: 1px solid #e2e8f0; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px;
                padding: 10px 24px; margin-right: 2px;
                font-size: 14px; font-weight: 600;
            }
            QTabBar::tab:selected {
                color: #1e293b; background: #f8fafc;
                border-bottom: 2px solid #3b82f6;
            }
            QTabBar::tab:hover:!selected {
                color: #0f172a; background: #f1f5f9;
            }
            QTabBar::tab:disabled {
                color: #cbd5e1;
            }
        """)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # ---- Tab 0: 仪表盘 ----
        self.dashboard = DashboardWidget(self)
        self.dashboard.signal_new_project.connect(self._project_new)
        self.dashboard.signal_open_project.connect(self._project_open)
        self.dashboard.signal_save_project.connect(self._project_save)
        self.dashboard.signal_plan_path.connect(self.on_plan_path)
        self.dashboard.signal_run_path.connect(self.on_run_path)
        self.dashboard.signal_open_recent.connect(self._project_open_recent)
        self.tab_widget.addTab(self.dashboard, "📊 仪表盘")

        # ---- Tab 1: 网格控制（原有界面）----
        self.grid_tab = self._create_grid_tab_widget()
        self.tab_widget.addTab(self.grid_tab, "🔌 网格控制")

        # ---- Tab 2: 日志面板 ----
        self.log_panel = LogPanel()
        self.tab_widget.addTab(self.log_panel, "📋 日志")

        # ---- Tab 3: 工程管理器 ----
        self.project_manager = ProjectManager(self)

        # ---- Tab 4: 设置 ----
        self.settings = SettingsWidget(self)
        self.tab_widget.addTab(self.settings, "⚙️ 设置")

        outer_layout.addWidget(self.tab_widget, 1)

        # ============ 状态栏 ============
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #ffffff;
                color: #475569;
                border-top: 1px solid #e2e8f0;
                padding: 2px 16px;
                font-size: 14px;
            }
        """)
        self.statusBar().showMessage("就绪")

        # ============ 初始化串口列表 ============
        self.refresh_serial_ports()

    def refresh_serial_ports(self):
        """刷新可用的串口列表。"""
        self.port_combo.clear()
        ports = SerialThread.scan_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("未发现串口")

    def toggle_serial_connection(self):
        """切换串口连接状态。"""
        if self.connect_btn.isChecked():
            port = self.port_combo.currentText()
            if port == "未发现串口":
                QMessageBox.warning(self, "错误", "未发现串口")
                self.connect_btn.setChecked(False)
                return
            self.serial_thread.open_port(port)
        else:
            self.serial_thread.close_port()
            self.serial_connected = False
            self.serial_status_label.setText("状态：未连接")
            self.serial_status_label.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 16px;")
            self.header_status_label.setText("● 串口已断开")
            self.header_status_label.setStyleSheet("""
                font-size: 14px; color: #fca5a5; background: rgba(239, 68, 68, 0.1);
                padding: 4px 14px; border: 1px solid #fca5a5; border-radius: 12px;
            """)
            self.statusBar().showMessage("串口已断开连接")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.serial_status_label.setText(f"状态：已连接 ({self.port_combo.currentText()})")
            self.serial_status_label.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 16px;")
            self.header_status_label.setText("● 串口已连接")
            self.header_status_label.setStyleSheet("""
                font-size: 14px; color: #4ade80; background: rgba(74, 222, 128, 0.1);
                padding: 4px 14px; border: 1px solid #4ade80; border-radius: 12px;
            """)
            self.statusBar().showMessage(f"串口已连接：{self.port_combo.currentText()}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self.serial_connected = False
            self.serial_status_label.setText("状态：连接失败")
            self.serial_status_label.setStyleSheet("color: #ea580c; font-weight: 600; font-size: 16px;")
            self.header_status_label.setText("● 连接失败")
            self.header_status_label.setStyleSheet("""
                font-size: 14px; color: #fb923c; background: rgba(234, 88, 12, 0.1);
                padding: 4px 14px; border: 1px solid #fb923c; border-radius: 12px;
            """)
            self.statusBar().showMessage("串口连接失败")
            self.connect_btn.setChecked(False)

    @pyqtSlot(str)
    def on_serial_data(self, data):
        """处理串口接收数据。"""
        self.info_label.setText(f"接收：{data}")
        # 同时更新串口测试区的接收显示
        current = self.test_received_label.text()
        if current == "等待数据...":
            self.test_received_label.setText(data)
        else:
            # 保留最近 5 条
            lines = current.split('\n')
            lines.append(data)
            if len(lines) > 5:
                lines = lines[-5:]
            self.test_received_label.setText('\n'.join(lines))

    @pyqtSlot(str)
    def on_serial_error(self, error_msg):
        """处理串口错误。"""
        self.statusBar().showMessage(f"错误：{error_msg}")
        QMessageBox.critical(self, "串口错误", error_msg)

    # ============ 液滴配置相关 ============

    def update_droplet_info(self):
        """更新液滴信息显示。"""
        did = int(self.droplet_label.text())

        # 更新当前液滴的起点/终点信息
        start = self.grid_widget.get_droplet_start(did)
        target = self.grid_widget.get_droplet_target(did)
        self.droplet_start_label.setText(f"起点：{start if start else '未设置'}")
        self.droplet_target_label.setText(f"目标：{target if target else '未设置'}")

        # 更新总览
        pairs = self.grid_widget.get_droplet_pairs()
        active_ids = self.grid_widget.get_active_droplet_ids()
        max_droplets = 8
        self.droplet_summary_label.setText(
            f"已配对：{len(pairs)} / {max_droplets}  已配置：{len(active_ids)} 个液滴")

    # ============ 路径规划 ============

    def on_plan_path(self):
        """规划路径：预先试跑，只计算和显示路径，不操作串口。"""
        obstacles = set(self.grid_widget.get_obstacle_points())
        droplet_pairs = self.grid_widget.get_droplet_pairs()

        if not droplet_pairs:
            QMessageBox.warning(self, "警告",
                                "未找到已配对的液滴！\n\n"
                                "请先为液滴分别设置起点和终点：\n"
                                "1. 在「液滴设置」中选择液滴编号\n"
                                "2. 点击网格设置起点（蓝色）和终点（橙色）")
            return

        pairs = [(start, target) for start, target, did in droplet_pairs]
        droplet_ids = [did for start, target, did in droplet_pairs]

        # 多液滴无干扰寻路
        results = plan_multiple_paths(pairs, obstacles)

        # 恢复正确的 droplet_id
        for i, r in enumerate(results):
            if i < len(droplet_ids):
                r['droplet_id'] = droplet_ids[i]

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        failed = [r for r in results if not r['success']]

        # 在网格上绘制所有路径
        self.grid_widget.set_paths(results)

        # 显示路径信息
        info_lines = [f"📋 规划结果: {success_count}/{len(results)} 成功"]
        for r in results:
            if r['success']:
                info_lines.append(
                    f"  ✅ 液滴{r['droplet_id']}: {r['start']}→{r['target']} ({len(r['path'])}步)")
            else:
                info_lines.append(
                    f"  ❌ 液滴{r['droplet_id']}: {r['start']}→{r['target']} 无路径")
        self.path_info_label.setText('\n'.join(info_lines))

        if failed:
            lines = ["以下液滴路径规划失败："]
            for r in failed:
                reason = r.get('fail_reason', '未知原因')
                lines.append(f"  • 液滴{r['droplet_id']}: {r['start']}→{r['target']}  —  {reason}")
            lines.append("")
            reason_counts = Counter(r.get('fail_reason', '未知') for r in failed)
            lines.append("建议：")
            for reason, count in reason_counts.items():
                if "障碍物" in reason:
                    lines.append(f"  · {count}个液滴{reason}，请调整障碍物位置")
                elif "占用" in reason:
                    lines.append(f"  · {count}个液滴路径被占用，请调整起点/终点顺序或位置")
                elif "等于" in reason:
                    lines.append(f"  · {count}个液滴{reason}，请设置不同的起点和终点")
                else:
                    lines.append(f"  · {count}个液滴{reason}，请检查起点/终点是否可行")
            QMessageBox.critical(self, "规划失败", '\n'.join(lines))

        if success_count == 0:
            self.grid_widget.clear_paths()
            self.path_info_label.setText("路径：规划失败")
            return

        self.statusBar().showMessage(f"规划完成: {success_count}/{len(results)} 条路径")
        self.info_label.setText(f"规划完成 ✓  {success_count}/{len(results)} 条路径成功")

    def on_run_path(self):
        """手动配对液滴路径规划并依次执行。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return

        obstacles = set(self.grid_widget.get_obstacle_points())
        droplet_pairs = self.grid_widget.get_droplet_pairs()

        if not droplet_pairs:
            QMessageBox.warning(self, "警告",
                                "未找到已配对的液滴！\n\n"
                                "请先为液滴分别设置起点和终点：\n"
                                "1. 在「液滴设置」中选择液滴编号\n"
                                "2. 点击网格设置起点（蓝色）和终点（橙色）")
            return

        # 构建 pairs 列表供 plan_multiple_paths 使用
        pairs = [(start, target) for start, target, did in droplet_pairs]
        droplet_ids = [did for start, target, did in droplet_pairs]

        # 多液滴无干扰寻路
        results = plan_multiple_paths(pairs, obstacles)

        # 恢复正确的 droplet_id（plan_multiple_paths 从 1 开始编号）
        for i, r in enumerate(results):
            if i < len(droplet_ids):
                r['droplet_id'] = droplet_ids[i]

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        failed = [r for r in results if not r['success']]

        # 在网格上绘制所有路径（不同颜色）
        self.grid_widget.set_paths(results)

        # 显示路径信息
        info_lines = [f"液滴规划: {success_count}/{len(results)} 成功"]
        for r in results:
            if r['success']:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} ({len(r['path'])}步)")
            else:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} ❌ 无路径")
        self.path_info_label.setText('\n'.join(info_lines))

        if failed:
            lines = ["以下液滴路径规划失败："]
            for r in failed:
                reason = r.get('fail_reason', '未知原因')
                lines.append(f"  • 液滴{r['droplet_id']}: {r['start']}→{r['target']}  —  {reason}")
            lines.append("")
            reason_counts = Counter(r.get('fail_reason', '未知') for r in failed)
            lines.append("建议：")
            for reason, count in reason_counts.items():
                if "障碍物" in reason:
                    lines.append(f"  · {count}个液滴{reason}，请调整障碍物位置")
                elif "占用" in reason:
                    lines.append(f"  · {count}个液滴路径被占用，请调整起点/终点顺序或位置")
                elif "等于" in reason:
                    lines.append(f"  · {count}个液滴{reason}，请设置不同的起点和终点")
                else:
                    lines.append(f"  · {count}个液滴{reason}，请检查起点/终点是否可行")
            QMessageBox.critical(self, "规划失败", '\n'.join(lines))

        if success_count == 0:
            self.grid_widget.clear_paths()
            self.path_info_label.setText("路径：规划失败")
            return

        # 保存规划结果，从第一个成功路径开始执行
        self.droplet_plans = results
        self.current_plan_index = 0
        self._start_next_droplet()

    # ============ 串口测试相关 ============

    @pyqtSlot()
    def on_test_send(self):
        """发送 ON/OFF 指令。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        cmd = self.test_cmd_combo.currentText()
        relay = self.test_relay_spin.value()
        self.serial_thread.send_cmd(f"{cmd},{relay}")
        self.test_received_label.setText(f">>> 发送: {cmd},{relay}\n等待数据...")

    @pyqtSlot(str)
    def on_test_quick(self, cmd):
        """发送快捷指令（ALLON, ALLOFF, TEST, LIST, HELP）。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        self.serial_thread.send_cmd(cmd)
        self.test_received_label.setText(f">>> 发送: {cmd}\n等待数据...")

    @pyqtSlot()
    def on_test_custom(self):
        """发送自定义指令。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        text = self.test_custom_input.text().strip()
        if not text:
            return
        self.serial_thread.send_cmd(text)
        self.test_received_label.setText(f">>> 发送: {text}\n等待数据...")
        self.test_custom_input.clear()

    def _start_next_droplet(self):
        """开始执行下一个液滴的路径。"""
        # 找到下一个成功的路径
        while self.current_plan_index < len(self.droplet_plans):
            plan = self.droplet_plans[self.current_plan_index]
            if plan['success']:
                self.current_path = plan['path']
                self.current_droplet_index = 0
                self.is_running = True

                self.run_path_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self.grid_widget.setEnabled(False)

                droplet_id = plan['droplet_id']
                self.statusBar().showMessage(
                    f"液滴{droplet_id} 路径执行中：{len(self.current_path)} 步")
                self.header_status_label.setText(f"● 液滴{droplet_id} 运行中")
                self.header_status_label.setStyleSheet("""
                    font-size: 15px; color: #ffd54f; background: transparent;
                    padding: 4px 14px; border: 1px solid #ffd54f; border-radius: 12px;
                """)

                # 启动定时器
                delay_ms = int(self.delay_spinbox.currentText())
                self.move_timer.start(delay_ms)
                return
            else:
                self.current_plan_index += 1

        # 所有液滴执行完毕
        self._finish_all()

    def _finish_all(self):
        """所有液滴执行完毕。"""
        self.is_running = False
        self.move_timer.stop()
        self.current_path = []
        self.run_path_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.statusBar().showMessage("所有液滴路径执行完成")
        self.info_label.setText("所有液滴已完成")
        self.header_status_label.setText("● 全部完成")
        self.header_status_label.setStyleSheet("""
            font-size: 14px; color: #4ade80; background: rgba(74, 222, 128, 0.1);
            padding: 4px 14px; border: 1px solid #4ade80; border-radius: 12px;
        """)

    def on_stop(self):
        """停止液滴移动。"""
        self.is_running = False
        self.move_timer.stop()
        # 断开所有继电器
        self.serial_thread.send_alloff()
        self.run_path_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.statusBar().showMessage("路径执行已停止，所有继电器已断开")
        self.info_label.setText("已停止")
        self.header_status_label.setText("● 已停止")
        self.header_status_label.setStyleSheet("""
            font-size: 14px; color: #fca5a5; background: rgba(239, 68, 68, 0.1);
            padding: 4px 14px; border: 1px solid #fca5a5; border-radius: 12px;
        """)

    def move_droplet_step(self):
        """液滴单步移动，完成后自动切换到下一个液滴。"""
        if not self.is_running or not self.current_path:
            self.move_timer.stop()
            return

        if self.current_droplet_index >= len(self.current_path):
            # 当前液滴路径完成，保持最后一个电极开启（到达目标）
            # 切换到下一个液滴
            self.current_plan_index += 1
            if self.current_plan_index < len(self.droplet_plans):
                self.statusBar().showMessage(
                    f"液滴 {self.droplet_plans[self.current_plan_index - 1]['droplet_id']} 已到达目标，"
                    f"准备下一个液滴...")
                self.move_timer.stop()
                self._start_next_droplet()
            else:
                self._finish_all()
            return

        # 获取当前步骤的电极
        current_pos = self.current_path[self.current_droplet_index]
        current_index = ElectrodeGrid.coord_to_index(current_pos[0], current_pos[1])

        # 关闭前一个位置的电极
        if self.current_droplet_index > 0:
            prev_pos = self.current_path[self.current_droplet_index - 1]
            prev_index = ElectrodeGrid.coord_to_index(prev_pos[0], prev_pos[1])
            self.serial_thread.send_cmd(f"OFF,{prev_index}")

        # 打开当前位置的电极
        self.serial_thread.send_cmd(f"ON,{current_index}")

        # 更新状态
        droplet_id = self.droplet_plans[self.current_plan_index]['droplet_id'] \
            if self.current_plan_index < len(self.droplet_plans) else '?'
        self.info_label.setText(
            f"液滴{droplet_id} 步骤 {self.current_droplet_index + 1}/{len(self.current_path)}："
            f"({current_pos[0]}, {current_pos[1]})")
        self.statusBar().showMessage(
            f"液滴{droplet_id} 移动到 ({current_pos[0]}, {current_pos[1]})，索引：{current_index}")

        self.current_droplet_index += 1

    def on_set_mode(self, mode):
        """切换交互模式。"""
        self.grid_widget.set_mode(mode)

    def on_next_droplet(self):
        """切换到下一个液滴编号。"""
        val = int(self.droplet_label.text()) % 8 + 1
        self.droplet_label.setText(str(val))
        self.grid_widget.set_droplet_id(val)
        self.update_droplet_info()
        self.statusBar().showMessage(f"已切换到液滴 {val}")

    def on_prev_droplet(self):
        """切换到上一个液滴编号。"""
        val = int(self.droplet_label.text()) - 1
        if val < 1:
            val = 8
        self.droplet_label.setText(str(val))
        self.grid_widget.set_droplet_id(val)
        self.update_droplet_info()
        self.statusBar().showMessage(f"已切换到液滴 {val}")

    def on_first_droplet(self):
        """回到液滴1。"""
        self.droplet_label.setText("1")
        self.grid_widget.set_droplet_id(1)
        self.update_droplet_info()
        self.statusBar().showMessage("已回到液滴 1")

    def on_clear_droplet(self):
        """清除当前液滴的起点和终点，保留其他液滴和障碍物。"""
        did = int(self.droplet_label.text())
        self.grid_widget.clear_droplet(did)
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.statusBar().showMessage(f"已清除液滴 {did} 的起点/终点")

    def on_clear_all_droplets(self):
        """清除所有液滴的起点/终点，保留障碍物和空闲格。"""
        self.grid_widget.clear_all_droplets()
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.statusBar().showMessage("已清除所有液滴的起点/终点")

    def _spin_row(self, delta):
        val = int(self.grid_rows_label.text()) + delta
        val = max(2, min(16, val))
        self.grid_rows_label.setText(str(val))

    def _spin_col(self, delta):
        val = int(self.grid_cols_label.text()) + delta
        val = max(2, min(16, val))
        self.grid_cols_label.setText(str(val))

    def on_mode_changed(self, mode):
        """交互模式变化时更新按钮状态。"""
        if mode == "sd":
            self.mode_sd_btn.setChecked(True)
            self.mode_obstacle_btn.setChecked(False)
        elif mode == "obstacle":
            self.mode_sd_btn.setChecked(False)
            self.mode_obstacle_btn.setChecked(True)
        self.statusBar().showMessage(f"已切换到{'起点/终点' if mode == 'sd' else '障碍物'}模式")

    def on_new_grid(self):
        """根据行/列值重建网格，并自动回到液滴1。"""
        rows = int(self.grid_rows_label.text())
        cols = int(self.grid_cols_label.text())
        # 同步更新全局配置，确保路径算法和索引映射使用正确的尺寸
        global_cfg.ELECTRODE_ROWS = rows
        global_cfg.ELECTRODE_COLS = cols
        global_cfg.TOTAL_ELECTRODES = rows * cols
        self.grid_widget.rebuild_grid(rows, cols)
        self.droplet_plans = []
        self.droplet_label.setText("1")
        self.grid_widget.set_droplet_id(1)
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.statusBar().showMessage(f"已新建 {rows}×{cols} 网格，当前液滴 1")

    def on_reset_grid(self):
        """重置网格所有单元格为 Idle，同时清除路径显示，并回到液滴1。"""
        self.grid_widget.reset_grid()  # 内部已清除 paths 和 droplet 配对
        self.droplet_plans = []
        self.droplet_label.setText("1")
        self.grid_widget.set_droplet_id(1)
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.statusBar().showMessage("网格已重置，当前液滴 1")

    def on_clear_state(self, state):
        """清除指定状态的所有单元格，同时清除路径显示。"""
        self.grid_widget.clear_state(state)  # 内部已清除 paths
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        state_name = ElectrodeGrid.STATE_NAMES[state]
        self.statusBar().showMessage(f"已清除所有 {state_name} 单元格")

    # ── 网格控制 Tab 构建 ──────────────────────

    def _create_grid_tab_widget(self):
        """创建网格控制标签页（原有左侧控制面板 + 中央网格 + 右侧图例）。"""
        grid_tab = QWidget()
        main_layout = QHBoxLayout(grid_tab)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(16)

        # ============ 左侧控制面板 ============
        left_sidebar = QWidget()
        left_sidebar.setObjectName("left_sidebar")
        left_sidebar.setFixedWidth(820)
        left_sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        left_panel = QVBoxLayout(left_sidebar)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(8)

        # 串口控制组
        serial_group = QGroupBox("串口连接")
        serial_layout = QVBoxLayout()
        serial_layout.setContentsMargins(12, 12, 12, 12)
        serial_layout.setSpacing(8)

        serial_combo_layout = QHBoxLayout()
        serial_combo_layout.setSpacing(10)
        serial_combo_layout.addWidget(QLabel("端口："), 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        serial_combo_layout.addWidget(self.port_combo, 1)
        self.refresh_ports_btn = QPushButton("刷新")
        self.refresh_ports_btn.setObjectName("soft_btn")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        serial_combo_layout.addWidget(self.refresh_ports_btn)
        serial_layout.addLayout(serial_combo_layout)

        self.connect_btn = QPushButton("连接")
        self.connect_btn.setObjectName("soft_btn")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        serial_layout.addWidget(self.connect_btn)

        self.serial_status_label = QLabel("状态：未连接")
        self.serial_status_label.setProperty("helper", True)
        self.serial_status_label.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 16px;")
        serial_layout.addWidget(self.serial_status_label)

        serial_group.setLayout(serial_layout)
        left_panel.addWidget(serial_group)

        # 路径规划和运动控制组
        control_group = QGroupBox("路径控制")
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(8)

        param_layout = QHBoxLayout()
        param_layout.setSpacing(10)
        param_layout.addWidget(QLabel("步长延迟 (ms)："))
        self.delay_spinbox = QComboBox()
        self.delay_spinbox.addItems(["100", "200", "500", "1000"])
        self.delay_spinbox.setCurrentText("500")
        self.delay_spinbox.setMaximumWidth(130)
        param_layout.addWidget(self.delay_spinbox)
        param_layout.addStretch()
        control_layout.addLayout(param_layout)

        self.plan_path_btn = QPushButton("规划路径")
        self.plan_path_btn.setObjectName("accent_btn")
        self.plan_path_btn.clicked.connect(self.on_plan_path)
        control_layout.addWidget(self.plan_path_btn)

        self.run_path_btn = QPushButton("运行路径")
        self.run_path_btn.setObjectName("success_btn")
        self.run_path_btn.clicked.connect(self.on_run_path)
        control_layout.addWidget(self.run_path_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("danger_btn")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        # 网格操作组 — 交互模式切换 + 网格配置
        grid_control_group = QGroupBox("网格操作")
        grid_control_layout = QVBoxLayout()
        grid_control_layout.setContentsMargins(12, 12, 12, 12)
        grid_control_layout.setSpacing(8)

        # ---- 网格尺寸配置 ----
        grid_size_layout = QHBoxLayout()
        grid_size_layout.setSpacing(6)
        grid_size_layout.addWidget(QLabel("行："), 0)
        self.grid_rows_label = QLabel(str(global_cfg.ELECTRODE_ROWS))
        self.grid_rows_label.setAlignment(Qt.AlignCenter)
        self.grid_rows_label.setFixedSize(50, 40)
        self.grid_rows_label.setStyleSheet("""
            background: white; border: 1px solid #e2e8f0;
            border-radius: 8px; font-size: 18px; font-weight: 700; color: #0f172a;
        """)
        rows_btn_layout = QVBoxLayout()
        rows_btn_layout.setSpacing(1)
        self.grid_rows_up = QPushButton("▲")
        self.grid_rows_up.setFixedSize(32, 19)
        self.grid_rows_up.setStyleSheet("QPushButton{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#475569;padding:0} QPushButton:hover{background:#e2e8f0}")
        self.grid_rows_up.clicked.connect(lambda: self._spin_row(1))
        self.grid_rows_down = QPushButton("▼")
        self.grid_rows_down.setFixedSize(32, 19)
        self.grid_rows_down.setStyleSheet("QPushButton{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#475569;padding:0} QPushButton:hover{background:#e2e8f0}")
        self.grid_rows_down.clicked.connect(lambda: self._spin_row(-1))
        rows_btn_layout.addWidget(self.grid_rows_up)
        rows_btn_layout.addWidget(self.grid_rows_down)
        grid_size_layout.addWidget(self.grid_rows_label, 0)
        grid_size_layout.addLayout(rows_btn_layout)

        grid_size_layout.addWidget(QLabel("列："), 0)
        self.grid_cols_label = QLabel(str(global_cfg.ELECTRODE_COLS))
        self.grid_cols_label.setAlignment(Qt.AlignCenter)
        self.grid_cols_label.setFixedSize(50, 40)
        self.grid_cols_label.setStyleSheet("""
            background: white; border: 1px solid #e2e8f0;
            border-radius: 8px; font-size: 18px; font-weight: 700; color: #0f172a;
        """)
        cols_btn_layout = QVBoxLayout()
        cols_btn_layout.setSpacing(1)
        self.grid_cols_up = QPushButton("▲")
        self.grid_cols_up.setFixedSize(32, 19)
        self.grid_cols_up.setStyleSheet("QPushButton{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#475569;padding:0} QPushButton:hover{background:#e2e8f0}")
        self.grid_cols_up.clicked.connect(lambda: self._spin_col(1))
        self.grid_cols_down = QPushButton("▼")
        self.grid_cols_down.setFixedSize(32, 19)
        self.grid_cols_down.setStyleSheet("QPushButton{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;font-size:10px;color:#475569;padding:0} QPushButton:hover{background:#e2e8f0}")
        self.grid_cols_down.clicked.connect(lambda: self._spin_col(-1))
        cols_btn_layout.addWidget(self.grid_cols_up)
        cols_btn_layout.addWidget(self.grid_cols_down)
        grid_size_layout.addWidget(self.grid_cols_label, 0)
        grid_size_layout.addLayout(cols_btn_layout)
        self.new_grid_btn = QPushButton("新建网格")
        self.new_grid_btn.setObjectName("soft_btn")
        self.new_grid_btn.clicked.connect(self.on_new_grid)
        grid_size_layout.addWidget(self.new_grid_btn, 1)
        grid_control_layout.addLayout(grid_size_layout)

        # ---- 交互模式切换 ----
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)

        self.mode_sd_btn = QPushButton("起点/终点")
        self.mode_sd_btn.setCheckable(True)
        self.mode_sd_btn.setChecked(False)
        self.mode_sd_btn.setObjectName("mode_sd_btn")
        self.mode_sd_btn.clicked.connect(lambda: self.on_set_mode("sd"))
        mode_layout.addWidget(self.mode_sd_btn, 1)

        self.mode_obstacle_btn = QPushButton("障碍物")
        self.mode_obstacle_btn.setCheckable(True)
        self.mode_obstacle_btn.setObjectName("mode_obstacle_btn")
        self.mode_obstacle_btn.clicked.connect(lambda: self.on_set_mode("obstacle"))
        mode_layout.addWidget(self.mode_obstacle_btn, 1)

        grid_control_layout.addLayout(mode_layout)

        # ---- 清除按钮 ----
        clear_btns_layout = QHBoxLayout()
        clear_btns_layout.setSpacing(8)
        self.clear_obstacles_btn = QPushButton("清除障碍物")
        self.clear_obstacles_btn.setObjectName("soft_btn")
        self.clear_obstacles_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        clear_btns_layout.addWidget(self.clear_obstacles_btn, 1)

        self.reset_grid_btn = QPushButton("重置网格")
        self.reset_grid_btn.setObjectName("soft_btn")
        self.reset_grid_btn.clicked.connect(self.on_reset_grid)
        clear_btns_layout.addWidget(self.reset_grid_btn, 1)
        grid_control_layout.addLayout(clear_btns_layout)

        grid_control_group.setLayout(grid_control_layout)
        left_panel.addWidget(grid_control_group)

        # 液滴设置组
        droplet_group = QGroupBox("液滴设置")
        droplet_layout = QVBoxLayout()
        droplet_layout.setContentsMargins(12, 12, 12, 12)
        droplet_layout.setSpacing(6)

        # ---- 第一行：液滴编号选择器 + 上下翻页 ----
        droplet_selector_layout = QHBoxLayout()
        droplet_selector_layout.setSpacing(6)
        droplet_selector_layout.addWidget(QLabel("当前："))
        self.droplet_label = QLabel("1")
        self.droplet_label.setAlignment(Qt.AlignCenter)
        self.droplet_label.setFixedSize(44, 40)
        self.droplet_label.setStyleSheet("""
            background: white; border: 1px solid #e2e8f0;
            border-radius: 8px; font-size: 18px; font-weight: 700; color: #0f172a;
        """)
        droplet_selector_layout.addWidget(self.droplet_label, 0)
        # 上一步 / 下一步
        self.prev_droplet_btn = QPushButton("◀ 上一个")
        self.prev_droplet_btn.setObjectName("soft_btn")
        self.prev_droplet_btn.clicked.connect(self.on_prev_droplet)
        droplet_selector_layout.addWidget(self.prev_droplet_btn, 1)
        self.next_droplet_btn = QPushButton("下一个 ▶")
        self.next_droplet_btn.setObjectName("soft_btn")
        self.next_droplet_btn.clicked.connect(self.on_next_droplet)
        droplet_selector_layout.addWidget(self.next_droplet_btn, 1)
        droplet_layout.addLayout(droplet_selector_layout)

        # ---- 第二行：回到液滴1 / 清除当前 / 清除所有 ----
        droplet_action_layout = QHBoxLayout()
        droplet_action_layout.setSpacing(6)
        self.first_droplet_btn = QPushButton("⏹ 回到液滴1")
        self.first_droplet_btn.setObjectName("soft_btn")
        self.first_droplet_btn.clicked.connect(self.on_first_droplet)
        droplet_action_layout.addWidget(self.first_droplet_btn, 1)
        self.clear_droplet_btn = QPushButton("✕ 清除当前")
        self.clear_droplet_btn.setObjectName("soft_btn")
        self.clear_droplet_btn.clicked.connect(self.on_clear_droplet)
        droplet_action_layout.addWidget(self.clear_droplet_btn, 1)
        self.clear_all_droplets_btn = QPushButton("✕ 清除所有")
        self.clear_all_droplets_btn.setObjectName("soft_btn")
        self.clear_all_droplets_btn.clicked.connect(self.on_clear_all_droplets)
        droplet_action_layout.addWidget(self.clear_all_droplets_btn, 1)
        droplet_layout.addLayout(droplet_action_layout)

        # ---- 第三行：当前液滴的起点 / 终点 ----
        start_target_layout = QHBoxLayout()
        start_target_layout.setSpacing(8)
        self.droplet_start_label = QLabel("起点：未设置")
        self.droplet_start_label.setProperty("helper", True)
        self.droplet_target_label = QLabel("目标：未设置")
        self.droplet_target_label.setProperty("helper", True)
        start_target_layout.addWidget(self.droplet_start_label, 1)
        start_target_layout.addWidget(self.droplet_target_label, 1)
        droplet_layout.addLayout(start_target_layout)

        # ---- 第四行：配对状态总览 ----
        self.droplet_summary_label = QLabel("已配对：0 / 8  已配置：0 个液滴")
        self.droplet_summary_label.setProperty("helper", True)
        self.droplet_summary_label.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 15px;")
        droplet_layout.addWidget(self.droplet_summary_label)

        droplet_group.setLayout(droplet_layout)
        left_panel.addWidget(droplet_group)

        # 串口测试组
        test_group = QGroupBox("串口测试")
        test_layout = QVBoxLayout()
        test_layout.setContentsMargins(12, 12, 12, 12)
        test_layout.setSpacing(6)

        # ON/OFF 快捷指令
        cmd_layout1 = QHBoxLayout()
        cmd_layout1.setSpacing(8)
        cmd_label = QLabel("指令：")
        cmd_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        cmd_layout1.addWidget(cmd_label)
        self.test_cmd_combo = QComboBox()
        self.test_cmd_combo.addItems(["ON", "OFF"])
        self.test_cmd_combo.setMinimumWidth(80)
        cmd_layout1.addWidget(self.test_cmd_combo)
        relay_label = QLabel("通道：")
        relay_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        cmd_layout1.addWidget(relay_label)
        self.test_relay_spin = QSpinBox()
        self.test_relay_spin.setRange(0, 47)
        self.test_relay_spin.setValue(0)
        self.test_relay_spin.setMinimumWidth(70)
        cmd_layout1.addWidget(self.test_relay_spin)
        self.test_send_btn = QPushButton("发送")
        self.test_send_btn.setObjectName("accent_btn")
        self.test_send_btn.clicked.connect(self.on_test_send)
        cmd_layout1.addWidget(self.test_send_btn)
        test_layout.addLayout(cmd_layout1)

        # 快速指令按钮
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        for label in ("ALLON", "ALLOFF", "TEST", "LIST", "HELP"):
            btn = QPushButton(label)
            btn.setObjectName("soft_btn")
            btn.clicked.connect(lambda checked, c=label: self.on_test_quick(c))
            quick_layout.addWidget(btn)
        test_layout.addLayout(quick_layout)

        # 自定义指令
        custom_layout = QHBoxLayout()
        custom_layout.setSpacing(8)
        self.test_custom_input = QLineEdit()
        self.test_custom_input.setPlaceholderText("输入自定义指令...")
        self.test_custom_btn = QPushButton("发送")
        self.test_custom_btn.setObjectName("accent_btn")
        self.test_custom_btn.clicked.connect(self.on_test_custom)
        custom_layout.addWidget(self.test_custom_input, 1)
        custom_layout.addWidget(self.test_custom_btn)
        test_layout.addLayout(custom_layout)

        # 接收数据显示
        self.test_received_label = QLabel("等待数据...")
        self.test_received_label.setWordWrap(True)
        self.test_received_label.setProperty("helper", True)
        self.test_received_label.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 8px;
            font-size: 13px;
            color: #0f172a;
            min-height: 36px;
        """)
        test_layout.addWidget(self.test_received_label)

        test_group.setLayout(test_layout)
        left_panel.addWidget(test_group)

        left_panel.addStretch()

        # ============ 中间区域: 电极网格 + 右侧图例 ============
        center_widget = QWidget()
        center_widget.setObjectName("center_widget")
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(16)

        # 网格容器（白色卡片效果）
        grid_card = QWidget()
        grid_card.setObjectName("grid_card")
        grid_card_layout = QVBoxLayout(grid_card)
        grid_card_layout.setContentsMargins(20, 20, 20, 20)
        grid_card_layout.addWidget(self.grid_widget, 1)

        center_layout.addWidget(grid_card, stretch=1)

        # 右侧图例面板
        right_sidebar = QWidget()
        right_sidebar.setObjectName("right_sidebar")
        right_sidebar.setFixedWidth(230)
        right_sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        right_panel = QVBoxLayout(right_sidebar)
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(0)

        legend_group = QGroupBox("颜色图例")
        legend_layout = QVBoxLayout()
        legend_layout.setContentsMargins(16, 16, 16, 16)
        legend_layout.setSpacing(10)

        legend_items = [
            ("蓝色", "起点", "#3b78ff"),
            ("橙色", "目标", "#ffb320"),
            ("黑色", "障碍物", "#262626"),
            ("浅灰色", "空闲", "#ebebeb"),
        ]

        for name, text, color in legend_items:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)
            row_layout.setAlignment(Qt.AlignVCenter)
            swatch = QWidget()
            swatch.setFixedSize(26, 26)
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #d0d5dd; border-radius: 4px;")
            label = QLabel(f"{name} = {text}")
            label.setStyleSheet("font-size: 16px; color: #334155;")
            row_layout.addWidget(swatch)
            row_layout.addWidget(label, 1)
            legend_layout.addLayout(row_layout)

        legend_group.setLayout(legend_layout)
        right_panel.addWidget(legend_group)

        # 信息面板（置于右栏图例下方）
        right_info_group = QGroupBox("信息")
        right_info_layout = QVBoxLayout()
        right_info_layout.setContentsMargins(12, 12, 12, 12)
        right_info_layout.setSpacing(6)

        self.info_label = QLabel("就绪")
        self.info_label.setWordWrap(True)
        right_info_layout.addWidget(self.info_label)

        self.path_info_label = QLabel("路径：无")
        self.path_info_label.setProperty("helper", True)
        self.path_info_label.setWordWrap(True)
        right_info_layout.addWidget(self.path_info_label)

        right_info_group.setLayout(right_info_layout)
        right_panel.addWidget(right_info_group)

        right_panel.addStretch()

        center_layout.addWidget(right_sidebar, stretch=0)
        center_widget.setLayout(center_layout)

        # ============ 组装主布局 ============
        main_layout.addWidget(left_sidebar, stretch=0)
        main_layout.addWidget(center_widget, stretch=1)

        return grid_tab

    # ── 工程管理 ──────────────────────────────

    def _project_new(self):
        """新建工程。"""
        self.project_manager.new_project()

    def _project_open(self):
        """打开工程。"""
        self.project_manager.open_project()

    def _project_save(self):
        """保存工程。"""
        self.project_manager.save_project()

    def _project_open_recent(self, filepath):
        """打开最近工程。"""
        self.project_manager.open_project(filepath)

    # ── Tab 切换事件 ──────────────────────────

    def _on_tab_changed(self, index):
        """Tab 切换时更新状态。"""
        if not hasattr(self, 'project_manager'):
            return
        if index == 0:  # 仪表盘
            self.dashboard.update_serial_status(
                self.serial_connected,
                self.port_combo.currentText() if self.serial_connected else ""
            )
            pairs = self.grid_widget.get_droplet_pairs()
            active_ids = self.grid_widget.get_active_droplet_ids()
            self.dashboard.update_droplet_info(len(pairs), 8, len(active_ids))
            success_count = sum(1 for p in getattr(self, 'droplet_plans', []) if p.get('success'))
            self.dashboard.update_path_info(success_count)
            self.dashboard.update_recent_files(
                self.project_manager.get_recent_files())

    # ── 窗口关闭事件 ──────────────────────────

    def closeEvent(self, event):
        """窗口关闭事件。"""
        if self.serial_connected:
            self.serial_thread.close_port()
        if self.move_timer.isActive():
            self.move_timer.stop()
        event.accept()


def main():
    """主函数：显示欢迎界面 → 加载资源 → 启动主窗口。"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # ========== 欢迎启动界面 ==========
    splash_mgr = SplashManager()
    splash_mgr.show()

    # 定义加载任务
    loading_tasks = [
        (10, "正在加载核心模块...", None),
        (10, "正在初始化串口驱动...", None),
        (15, "正在加载界面组件...", None),
        (10, "正在初始化电极网格...", None),
        (15, "正在加载路径算法...", None),
        (10, "正在应用视觉样式...", None),
        (15, "正在构建用户界面...", None),
        (10, "正在准备系统资源...", None),
        (5, "正在完成配置...", None),
    ]

    # 执行加载动画
    splash_mgr.run_loading_sequence(loading_tasks, min_duration=2.0)

    # 创建主窗口
    window = DMFControllerWindow()
    window.show()

    # 集成：串口数据路由到日志面板
    window.serial_thread.data_received.connect(
        lambda data: window.log_panel.log_info(f"RX: {data}")
    )
    window.serial_thread.error.connect(
        lambda err: window.log_panel.log_error(f"串口错误: {err}")
    )

    # 集成：路径运行/停止日志
    original_start = window._start_next_droplet
    def _logged_start():
        original_start()
        plan = window.droplet_plans[window.current_plan_index] if window.current_plan_index < len(window.droplet_plans) else None
        if plan and plan.get('success'):
            window.log_panel.log_success(f"液滴{plan['droplet_id']} 路径开始执行 ({len(plan['path'])}步)")
    window._start_next_droplet = _logged_start

    original_stop = window.on_stop
    def _logged_stop():
        original_stop()
        window.log_panel.log_warn("用户手动停止路径执行")
    window.on_stop = _logged_stop

    # 集成：首次加载仪表盘
    pairs = window.grid_widget.get_droplet_pairs()
    active_ids = window.grid_widget.get_active_droplet_ids()
    window.dashboard.update_droplet_info(len(pairs), 8, len(active_ids))
    window.dashboard.update_recent_files(
        window.project_manager.get_recent_files())
    window.log_panel.log_info("系统启动完成")

    # 关闭启动画面
    splash_mgr.close()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
