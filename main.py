"""
DMF 48-通道控制器主应用程序
PyQt5 界面，整合串口通信、电极网格、寻路算法
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QGroupBox, QMessageBox,
    QSizePolicy, QSpinBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from src import global_cfg
from src.serial_driver import SerialThread
from src.grid_widget import ElectrodeGrid
from src.path_algorithm import bfs_shortest_path, path_to_indices, plan_multiple_paths


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48通道控制器")
        self.setGeometry(50, 50, 1800, 960)
        self.setMinimumSize(1200, 700)

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

        # ============ 应用全局样式 ============
        self.apply_stylesheet()

        # ============ 创建 UI ============
        self.init_ui()

        # ============ 状态变量 ============
        self.serial_connected = False
        self.droplet_position = None

        # 初始化液滴信息显示
        self.update_droplet_info()

    def apply_stylesheet(self):
        """应用全局 QSS 样式表。"""
        stylesheet = """
        QMainWindow {
            background-color: #f7f7f7;
        }
        QWidget {
            font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
            font-size: 20px;
        }
        QGroupBox {
            color: #303030;
            background-color: #ffffff;
            border: 1px solid #d6d6d6;
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 20px;
            padding-left: 18px;
            padding-right: 18px;
            padding-bottom: 18px;
            font-size: 20px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 0 8px;
            font-size: 24px;
            font-weight: 700;
            color: #202020;
        }
        QPushButton {
            border: 1px solid #cdd5db;
            border-radius: 10px;
            padding: 14px 20px;
            font-size: 19px;
            font-weight: 600;
            color: #222222;
            background-color: #e8edf2;
        }
        QPushButton:hover {
            background-color: #edf2f6;
        }
        QPushButton:pressed {
            background-color: #dbe3ea;
        }
        QPushButton:disabled {
            background-color: #d9d9d9;
            color: #8c8c8c;
        }
        QPushButton#soft_btn {
            background-color: #e8edf2;
            color: #222222;
            border: 1px solid #cdd5db;
        }
        QPushButton#soft_btn:hover {
            background-color: #edf2f6;
        }
        QPushButton#soft_btn:pressed {
            background-color: #dbe3ea;
        }
        QComboBox {
            border: 1px solid #c4cbd2;
            border-radius: 8px;
            padding: 12px 14px;
            background-color: #ffffff;
            color: #303030;
            font-size: 19px;
        }
        QComboBox:focus {
            border: 1px solid #7aa0c8;
        }
        QLabel {
            color: #303030;
            font-size: 19px;
        }
        QLabel[helper="true"] {
            color: #666666;
            font-size: 17px;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        """初始化用户界面。"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #f7f7f7;")

        # ============ 外层垂直布局: 标题栏 + 主内容 ============
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ---------- 顶部标题栏 ----------
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet("""
            background-color: #1a2332;
            border-bottom: 2px solid #2d3e50;
        """)
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

        header_layout.addStretch()

        self.header_status_label = QLabel("● 系统就绪")
        self.header_status_label.setStyleSheet("""
            font-size: 15px;
            color: #a5d6a7;
            background: transparent;
            padding: 4px 14px;
            border: 1px solid #a5d6a7;
            border-radius: 12px;
        """)
        header_layout.addWidget(self.header_status_label)

        outer_layout.addWidget(header)

        # ---------- 主内容区域 ----------
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(20)

        # ============ 左侧控制面板 ============
        left_sidebar = QWidget()
        left_sidebar.setFixedWidth(560)
        left_sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left_sidebar.setStyleSheet("background-color: transparent;")

        left_panel = QVBoxLayout(left_sidebar)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(18)

        # 串口控制组
        serial_group = QGroupBox("串口连接")
        serial_layout = QVBoxLayout()
        serial_layout.setContentsMargins(16, 16, 16, 16)
        serial_layout.setSpacing(12)

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
        self.serial_status_label.setStyleSheet("color: #d32f2f; font-weight: 600; font-size: 18px;")
        serial_layout.addWidget(self.serial_status_label)

        serial_group.setLayout(serial_layout)
        left_panel.addWidget(serial_group)

        # 路径规划和运动控制组
        control_group = QGroupBox("路径控制")
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(16, 16, 16, 16)
        control_layout.setSpacing(12)

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

        self.run_path_btn = QPushButton("运行路径")
        self.run_path_btn.setStyleSheet("""
            QPushButton {
                background-color: #66bb6a;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 18px;
                font-weight: bold;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #7ac776;
            }
            QPushButton:pressed {
                background-color: #558b5a;
            }
        """)
        self.run_path_btn.clicked.connect(self.on_run_path)
        control_layout.addWidget(self.run_path_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef5350;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 18px;
                font-weight: bold;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #f76464;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        # 网格操作组
        grid_control_group = QGroupBox("网格操作")
        grid_control_layout = QVBoxLayout()
        grid_control_layout.setContentsMargins(16, 16, 16, 16)
        grid_control_layout.setSpacing(12)

        self.reset_grid_btn = QPushButton("重置网格")
        self.reset_grid_btn.setObjectName("soft_btn")
        self.reset_grid_btn.clicked.connect(self.on_reset_grid)
        grid_control_layout.addWidget(self.reset_grid_btn)

        clear_btns_layout = QHBoxLayout()
        clear_btns_layout.setSpacing(10)
        self.clear_starts_btn = QPushButton("清除起点")
        self.clear_starts_btn.setObjectName("soft_btn")
        self.clear_starts_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_START))
        clear_btns_layout.addWidget(self.clear_starts_btn, 1)

        self.clear_targets_btn = QPushButton("清除目标")
        self.clear_targets_btn.setObjectName("soft_btn")
        self.clear_targets_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_TARGET))
        clear_btns_layout.addWidget(self.clear_targets_btn, 1)

        self.clear_obstacles_btn = QPushButton("清除障碍物")
        self.clear_obstacles_btn.setObjectName("soft_btn")
        self.clear_obstacles_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        clear_btns_layout.addWidget(self.clear_obstacles_btn, 1)

        grid_control_layout.addLayout(clear_btns_layout)

        grid_control_group.setLayout(grid_control_layout)
        left_panel.addWidget(grid_control_group)

        # 液滴设置组
        droplet_group = QGroupBox("液滴设置")
        droplet_layout = QVBoxLayout()
        droplet_layout.setContentsMargins(16, 16, 16, 16)
        droplet_layout.setSpacing(10)

        droplet_selector_layout = QHBoxLayout()
        droplet_selector_layout.setSpacing(10)
        droplet_selector_layout.addWidget(QLabel("当前液滴："))
        self.droplet_spinbox = QSpinBox()
        self.droplet_spinbox.setRange(1, 8)
        self.droplet_spinbox.setValue(1)
        self.droplet_spinbox.valueChanged.connect(self.on_droplet_changed)
        self.droplet_spinbox.setMinimumWidth(100)
        droplet_selector_layout.addWidget(self.droplet_spinbox)
        droplet_selector_layout.addStretch()
        droplet_layout.addLayout(droplet_selector_layout)

        # 显示当前液滴的起点和终点
        start_target_layout = QHBoxLayout()
        start_target_layout.setSpacing(10)
        self.droplet_start_label = QLabel("起点：未设置")
        self.droplet_start_label.setProperty("helper", True)
        self.droplet_target_label = QLabel("目标：未设置")
        self.droplet_target_label.setProperty("helper", True)
        start_target_layout.addWidget(self.droplet_start_label, 1)
        start_target_layout.addWidget(self.droplet_target_label, 1)
        droplet_layout.addLayout(start_target_layout)

        # 配对状态总览
        self.droplet_summary_label = QLabel("已配对：0 个液滴  总计配置：0 个")
        self.droplet_summary_label.setProperty("helper", True)
        self.droplet_summary_label.setStyleSheet("color: #2e7d32; font-weight: 600; font-size: 15px;")
        droplet_layout.addWidget(self.droplet_summary_label)

        droplet_group.setLayout(droplet_layout)
        left_panel.addWidget(droplet_group)

        # 状态信息
        info_group = QGroupBox("信息")
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(12)

        self.info_label = QLabel("就绪")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        self.path_info_label = QLabel("路径：无")
        self.path_info_label.setProperty("helper", True)
        self.path_info_label.setWordWrap(True)
        info_layout.addWidget(self.path_info_label)

        info_group.setLayout(info_layout)
        left_panel.addWidget(info_group)

        # 串口测试组
        test_group = QGroupBox("串口测试")
        test_layout = QVBoxLayout()
        test_layout.setContentsMargins(16, 16, 16, 16)
        test_layout.setSpacing(10)

        # ON/OFF 快捷指令
        cmd_layout1 = QHBoxLayout()
        cmd_layout1.setSpacing(8)
        cmd_layout1.addWidget(QLabel("指令："))
        self.test_cmd_combo = QComboBox()
        self.test_cmd_combo.addItems(["ON", "OFF"])
        self.test_cmd_combo.setMinimumWidth(70)
        cmd_layout1.addWidget(self.test_cmd_combo)
        self.test_relay_spin = QSpinBox()
        self.test_relay_spin.setRange(0, 47)
        self.test_relay_spin.setValue(0)
        self.test_relay_spin.setMinimumWidth(70)
        cmd_layout1.addWidget(self.test_relay_spin)
        self.test_send_btn = QPushButton("发送")
        self.test_send_btn.setObjectName("soft_btn")
        self.test_send_btn.clicked.connect(self.on_test_send)
        cmd_layout1.addWidget(self.test_send_btn)
        test_layout.addLayout(cmd_layout1)

        # 快速按钮
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)
        for label, cmd in [("ALLON", "ALLON"), ("ALLOFF", "ALLOFF"),
                           ("TEST", "TEST"), ("LIST", "LIST"), ("HELP", "HELP")]:
            btn = QPushButton(label)
            btn.setObjectName("soft_btn")
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, c=cmd: self.on_test_quick(c))
            quick_layout.addWidget(btn)
        test_layout.addLayout(quick_layout)

        # 自定义指令
        custom_layout = QHBoxLayout()
        custom_layout.setSpacing(8)
        self.test_custom_input = QLineEdit()
        self.test_custom_input.setPlaceholderText("自定义指令...")
        self.test_custom_btn = QPushButton("发送")
        self.test_custom_btn.setObjectName("soft_btn")
        self.test_custom_btn.clicked.connect(self.on_test_custom)
        custom_layout.addWidget(self.test_custom_input, 1)
        custom_layout.addWidget(self.test_custom_btn)
        test_layout.addLayout(custom_layout)

        # 接收数据显示
        self.test_received_label = QLabel("等待数据...")
        self.test_received_label.setWordWrap(True)
        self.test_received_label.setProperty("helper", True)
        self.test_received_label.setStyleSheet("""
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 8px;
            font-size: 14px;
            color: #222222;
            min-height: 50px;
        """)
        test_layout.addWidget(self.test_received_label)

        test_group.setLayout(test_layout)
        left_panel.addWidget(test_group)

        left_panel.addStretch()

        # ============ 中间区域: 电极网格 + 右侧图例 ============
        center_widget = QWidget()
        center_widget.setStyleSheet("background-color: transparent;")
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(16)

        # 网格容器（加白色背景卡片效果）
        grid_card = QWidget()
        grid_card.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #d6d6d6;
            border-radius: 12px;
        """)
        grid_card_layout = QVBoxLayout(grid_card)
        grid_card_layout.setContentsMargins(20, 20, 20, 20)
        grid_card_layout.addWidget(self.grid_widget, 0, Qt.AlignCenter)

        center_layout.addWidget(grid_card, stretch=1)

        # 右侧图例面板
        right_sidebar = QWidget()
        right_sidebar.setFixedWidth(230)
        right_sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        right_sidebar.setStyleSheet("background-color: transparent;")

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
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #c7c7c7; border-radius: 4px;")
            label = QLabel(f"{name} = {text}")
            label.setStyleSheet("font-size: 18px; color: #303030;")
            row_layout.addWidget(swatch)
            row_layout.addWidget(label, 1)
            legend_layout.addLayout(row_layout)

        legend_group.setLayout(legend_layout)
        right_panel.addWidget(legend_group)
        right_panel.addStretch()

        center_layout.addWidget(right_sidebar, stretch=0)
        center_widget.setLayout(center_layout)

        # ============ 组装主布局 ============
        main_layout.addWidget(left_sidebar, stretch=0)
        main_layout.addWidget(center_widget, stretch=1)

        outer_layout.addLayout(main_layout)

        # ============ 状态栏 ============
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #ffffff;
                color: #333333;
                border-top: 1px solid #d0d0d0;
                padding: 2px 12px;
                font-size: 14px;
            }
        """)
        self.statusBar().showMessage("就绪")
        self.statusBar().setFont(QFont("Arial", 14))

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
            self.serial_status_label.setStyleSheet("color: #d32f2f; font-weight: 600; font-size: 18px;")
            self.header_status_label.setText("● 串口已断开")
            self.header_status_label.setStyleSheet("""
                font-size: 15px; color: #ef9a9a; background: transparent;
                padding: 4px 14px; border: 1px solid #ef9a9a; border-radius: 12px;
            """)
            self.statusBar().showMessage("串口已断开连接")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.serial_status_label.setText(f"状态：已连接 ({self.port_combo.currentText()})")
            self.serial_status_label.setStyleSheet("color: #2e7d32; font-weight: 600; font-size: 18px;")
            self.header_status_label.setText("● 串口已连接")
            self.header_status_label.setStyleSheet("""
                font-size: 15px; color: #81c784; background: transparent;
                padding: 4px 14px; border: 1px solid #81c784; border-radius: 12px;
            """)
            self.statusBar().showMessage(f"串口已连接：{self.port_combo.currentText()}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self.serial_connected = False
            self.serial_status_label.setText("状态：连接失败")
            self.serial_status_label.setStyleSheet("color: #e65100; font-weight: 600; font-size: 18px;")
            self.header_status_label.setText("● 连接失败")
            self.header_status_label.setStyleSheet("""
                font-size: 15px; color: #ffb74d; background: transparent;
                padding: 4px 14px; border: 1px solid #ffb74d; border-radius: 12px;
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

    @pyqtSlot(int)
    def on_droplet_changed(self, value):
        """液滴选择器变更时更新网格和显示。"""
        self.grid_widget.set_droplet_id(value)
        self.update_droplet_info()

    def update_droplet_info(self):
        """更新液滴信息显示。"""
        did = self.droplet_spinbox.value()

        # 更新当前液滴的起点/终点信息
        start = self.grid_widget.get_droplet_start(did)
        target = self.grid_widget.get_droplet_target(did)
        self.droplet_start_label.setText(f"起点：{start if start else '未设置'}")
        self.droplet_target_label.setText(f"目标：{target if target else '未设置'}")

        # 更新总览
        pairs = self.grid_widget.get_droplet_pairs()
        active_ids = self.grid_widget.get_active_droplet_ids()
        self.droplet_summary_label.setText(
            f"已配对：{len(pairs)} 个液滴  总计配置：{len(active_ids)} 个")

    # ============ 路径规划 ============

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
            fail_info = ', '.join(f"液滴{r['droplet_id']}" for r in failed)
            QMessageBox.critical(self, "路径规划失败",
                                 f"以下液滴无法找到无干扰路径：\n{fail_info}\n\n"
                                 f"可能原因：\n"
                                 f"- 起点被障碍物或其他路径阻挡\n"
                                 f"- 目标不可达\n"
                                 f"- 所有可行路径被其他液滴占用\n\n"
                                 f"请调整起点/目标/障碍物后重试。")

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
            font-size: 15px; color: #81c784; background: transparent;
            padding: 4px 14px; border: 1px solid #81c784; border-radius: 12px;
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
            font-size: 15px; color: #ef9a9a; background: transparent;
            padding: 4px 14px; border: 1px solid #ef9a9a; border-radius: 12px;
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

    def on_reset_grid(self):
        """重置网格所有单元格为 Idle，同时清除路径显示。"""
        self.grid_widget.reset_grid()  # 内部已清除 paths 和 droplet 配对
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.statusBar().showMessage("网格已重置")

    def on_clear_state(self, state):
        """清除指定状态的所有单元格，同时清除路径显示。"""
        self.grid_widget.clear_state(state)  # 内部已清除 paths
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        state_name = ElectrodeGrid.STATE_NAMES[state]
        self.statusBar().showMessage(f"已清除所有 {state_name} 单元格")

    def closeEvent(self, event):
        """窗口关闭事件。"""
        if self.serial_connected:
            self.serial_thread.close_port()
        if self.move_timer.isActive():
            self.move_timer.stop()
        event.accept()


def main():
    """主函数。"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = DMFControllerWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
