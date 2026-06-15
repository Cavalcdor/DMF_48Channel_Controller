"""
DMF 48-通道控制器主应用程序
PyQt5 界面，整合串口通信、电极网格、寻路算法
"""

import sys
import os
from collections import Counter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QGroupBox, QMessageBox,
    QSizePolicy, QSpinBox, QLineEdit, QSplitter, QAction, QMenu,
    QDialog, QFrame, QToolButton, QTextEdit
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
from src.log_panel import LogPanel
from src.settings import SettingsWidget
from src.project_manager import ProjectManager


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48通道控制器")
        self.setGeometry(30, 30, 1920, 1080)
        self.setMinimumSize(1400, 850)
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
        """应用专业仪器控制软件风格样式。"""
        stylesheet = """
        /* ========== 全局 ========== */
        QMainWindow, QWidget#central_widget {
            background-color: #eef0f2;
        }
        QWidget {
            font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
            font-size: 15px;
            color: #1e293b;
        }

        /* ========== 菜单栏 ========== */
        QMenuBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #d4d8dd;
            padding: 4px 0;
            font-size: 15px;
        }
        QMenuBar::item {
            padding: 6px 18px;
            border-radius: 4px;
            margin: 2px 3px;
        }
        QMenuBar::item:selected {
            background: #e2e6ea;
        }
        QMenu {
            background: #ffffff;
            border: 1px solid #d4d8dd;
            border-radius: 8px;
            padding: 6px;
        }
        QMenu::item {
            padding: 8px 32px 8px 20px;
            border-radius: 4px;
            font-size: 14px;
        }
        QMenu::item:selected {
            background: #eef2ff;
            color: #1e40af;
        }
        QMenu::separator {
            height: 1px;
            background: #e2e6ea;
            margin: 6px 10px;
        }

        /* ========== 工具栏 ========== */
        QWidget#app_toolbar {
            background-color: #f8f9fa;
            border-bottom: 2px solid #d4d8dd;
            padding: 6px 12px;
        }
        QToolButton {
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 14px;
            color: #334155;
            background: transparent;
        }
        QToolButton:hover {
            background: #e2e6ea;
            border-color: #cbd5e1;
        }
        QToolButton:pressed, QToolButton:checked {
            background: #d1d5db;
        }

        /* ========== 分割器手柄 ========== */
        QSplitter::handle {
            background: #d4d8dd;
        }
        QSplitter::handle:horizontal { width: 4px; }
        QSplitter::handle:vertical { height: 4px; }

        /* ========== GroupBox ========== */
        QGroupBox {
            background: #ffffff;
            border: 1px solid #d4d8dd;
            border-radius: 8px;
            margin-top: 10px;
            padding: 18px 12px 12px 12px;
            font-size: 15px;
            font-weight: 600;
            color: #0f172a;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 0 8px;
            font-size: 16px;
            font-weight: 700;
            color: #1e293b;
            letter-spacing: 0.5px;
        }

        /* ========== 按钮 ========== */
        QPushButton {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 8px 18px;
            font-size: 14px;
            font-weight: 500;
            color: #334155;
            background: #ffffff;
        }
        QPushButton:hover {
            background: #f1f5f9;
            border-color: #94a3b8;
        }
        QPushButton:pressed {
            background: #e2e8f0;
        }
        QPushButton:disabled {
            background: #f8fafc;
            color: #94a3b8;
            border-color: #e2e8f0;
        }

        /* 蓝色强调按钮 */
        QPushButton#btn_primary {
            background: #2563eb;
            color: #ffffff;
            border: none;
            font-weight: 700;
            font-size: 14px;
            padding: 8px 20px;
        }
        QPushButton#btn_primary:hover {
            background: #3b82f6;
        }
        QPushButton#btn_primary:pressed {
            background: #1d4ed8;
        }
        QPushButton#btn_primary:disabled {
            background: #93c5fd;
            color: #ffffff;
        }

        /* 绿色运行按钮 */
        QPushButton#btn_run {
            background: #059669;
            color: #ffffff;
            border: none;
            font-weight: 700;
            font-size: 14px;
            padding: 8px 20px;
        }
        QPushButton#btn_run:hover {
            background: #10b981;
        }
        QPushButton#btn_run:pressed {
            background: #047857;
        }
        QPushButton#btn_run:disabled {
            background: #6ee7b7;
            color: #ffffff;
        }

        /* 红色停止按钮 */
        QPushButton#btn_stop {
            background: #dc2626;
            color: #ffffff;
            border: none;
            font-weight: 700;
            font-size: 14px;
            padding: 8px 20px;
        }
        QPushButton#btn_stop:hover {
            background: #ef4444;
        }
        QPushButton#btn_stop:pressed {
            background: #b91c1c;
        }
        QPushButton#btn_stop:disabled {
            background: #fca5a5;
            color: #ffffff;
        }

        /* 模式选择按钮组 */
        QPushButton#mode_btn {
            background: #ffffff;
            color: #475569;
            border: 1px solid #cbd5e1;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 12px;
        }
        QPushButton#mode_btn:hover {
            background: #f1f5f9;
        }
        QPushButton#mode_btn:checked {
            background: #1e293b;
            color: #ffffff;
            border-color: #1e293b;
        }

        /* ========== 输入控件 ========== */
        QComboBox {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 5px 10px;
            background: #ffffff;
            color: #0f172a;
            font-size: 14px;
            min-height: 26px;
        }
        QComboBox:hover { border-color: #94a3b8; }
        QComboBox:focus { border-color: #3b82f6; }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }

        QSpinBox {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 4px 8px;
            background: #ffffff;
            color: #0f172a;
            font-size: 14px;
            min-height: 26px;
        }
        QSpinBox:focus { border-color: #3b82f6; }

        QLineEdit {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 5px 10px;
            background: #ffffff;
            color: #0f172a;
            font-size: 14px;
            min-height: 26px;
        }
        QLineEdit:focus { border-color: #3b82f6; }

        /* ========== 标签 ========== */
        QLabel {
            color: #334155;
            font-size: 14px;
        }
        QLabel#status_value {
            font-weight: 600;
            font-size: 15px;
        }
        QLabel#section_title {
            font-size: 16px;
            font-weight: 700;
            color: #0f172a;
            padding: 6px 0;
        }

        /* ========== 状态栏 ========== */
        QStatusBar {
            background: #f8f9fa;
            border-top: 1px solid #d4d8dd;
            color: #475569;
            font-size: 13px;
            padding: 4px 14px;
        }
        QStatusBar::item { border: none; }

        /* ========== 日志面板 ========== */
        QTextEdit#log_view {
            background: #0f172a;
            color: #e2e8f0;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 10px;
            font-family: "Consolas", "Courier New", monospace;
            font-size: 13px;
        }

        /* ========== 串口监视区 ========== */
        QLabel#monitor_rx {
            background: #0f172a;
            color: #e2e8f0;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px;
            font-family: "Consolas", "Courier New", monospace;
            font-size: 13px;
            min-height: 80px;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        """初始化用户界面 — 专业仪器控制软件布局。"""
        central_widget = QWidget()
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ============ 菜单栏 ============
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)

        file_menu = menubar.addMenu("文件(&F)")
        act_new = QAction("新建工程", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._project_new)
        file_menu.addAction(act_new)
        act_open = QAction("打开工程...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._project_open)
        file_menu.addAction(act_open)
        act_save = QAction("保存工程", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._project_save)
        file_menu.addAction(act_save)
        act_save_as = QAction("另存为...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(lambda: self.project_manager.save_project(as_new=True))
        file_menu.addAction(act_save_as)
        file_menu.addSeparator()
        # ── 最近文件子菜单 ──
        self.recent_menu = QMenu("最近文件", self)
        self.recent_menu.setEnabled(False)
        file_menu.addMenu(self.recent_menu)
        file_menu.aboutToShow.connect(self._populate_recent_menu)
        file_menu.addSeparator()
        act_exit = QAction("退出(&Q)", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        tool_menu = menubar.addMenu("工具(&T)")
        act_settings = QAction("设置(&S)...", self)
        act_settings.triggered.connect(self._open_settings)
        tool_menu.addAction(act_settings)
        tool_menu.addSeparator()
        act_update = QAction("检查更新...", self)
        act_update.triggered.connect(lambda: check_for_update(self, silent=False))
        tool_menu.addAction(act_update)

        help_menu = menubar.addMenu("帮助(&H)")
        act_about = QAction("关于(&A)...", self)
        act_about.triggered.connect(lambda: AboutDialog(self).exec_())
        help_menu.addAction(act_about)

        # ============ 工具栏 ============
        toolbar = QWidget()
        toolbar.setObjectName("app_toolbar")
        toolbar.setFixedHeight(50)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(6)

        def _tb_btn(text, tooltip):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tooltip)
            return btn

        btn_new = _tb_btn("📄 新建", "新建工程 (Ctrl+N)")
        btn_new.clicked.connect(self._project_new)
        tb_layout.addWidget(btn_new)
        btn_open = _tb_btn("📂 打开", "打开工程 (Ctrl+O)")
        btn_open.clicked.connect(self._project_open)
        tb_layout.addWidget(btn_open)
        btn_save = _tb_btn("💾 保存", "保存工程 (Ctrl+S)")
        btn_save.clicked.connect(self._project_save)
        tb_layout.addWidget(btn_save)

        sep1 = QLabel("│")
        sep1.setStyleSheet("color:#cbd5e1;padding:0 8px;font-size:18px;")
        tb_layout.addWidget(sep1)

        # 串口选择
        tb_layout.addWidget(QLabel("🔌 端口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(130)
        self.port_combo.setMaximumWidth(160)
        tb_layout.addWidget(self.port_combo)
        self.refresh_ports_btn = QToolButton()
        self.refresh_ports_btn.setText("🔄")
        self.refresh_ports_btn.setToolTip("扫描串口")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        tb_layout.addWidget(self.refresh_ports_btn)
        self.connect_btn = QToolButton()
        self.connect_btn.setText("🔗 连接")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        tb_layout.addWidget(self.connect_btn)

        tb_layout.addStretch()

        self.tb_status = QLabel("● 系统就绪")
        self.tb_status.setStyleSheet("""
            color:#059669; font-size:13px; font-weight:700;
            padding:4px 14px; border:1px solid #059669; border-radius:12px;
            background:#ecfdf5;
        """)
        tb_layout.addWidget(self.tb_status)

        outer_layout.addWidget(toolbar)

        # ============ 主内容区: 左面板 | 网格 | 右面板 | 日志 ============
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(3)

        # 上部: 左面板 + 网格 + 右面板
        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.setHandleWidth(3)

        self._create_main_content(self.top_splitter)

        self.main_splitter.addWidget(self.top_splitter)

        # 下部: 日志面板
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(80)
        self.log_panel.setMaximumHeight(300)
        log_layout.addWidget(self.log_panel)
        self.main_splitter.addWidget(log_container)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([700, 180])

        outer_layout.addWidget(self.main_splitter, 1)

        # ============ 工程管理器 ============
        self.project_manager = ProjectManager(self)

        # ============ 状态栏 ============
        self.statusBar().showMessage("就绪")

        # ============ 初始化串口 ============
        self.refresh_serial_ports()

    # ── 左侧面板 + 网格 + 右侧面板 ──────────────────────

    def _create_main_content(self, parent_splitter):
        """创建主内容区: 左控制面板 | 网格视图 | 右信息面板。"""
        # ────────── 左面板 (360px) ──────────
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setMinimumWidth(340)
        left_panel.setMaximumWidth(420)
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(10, 10, 6, 10)
        left.setSpacing(8)

        # -- 串口状态 --
        sg = QGroupBox("🔌 串口")
        sl = QVBoxLayout(sg)
        sl.setContentsMargins(10, 10, 10, 10)
        sl.setSpacing(4)
        self.serial_status_label = QLabel("未连接")
        self.serial_status_label.setObjectName("status_value")
        self.serial_status_label.setStyleSheet("color:#dc2626;")
        sl.addWidget(self.serial_status_label)

        # 快捷指令
        qr = QHBoxLayout()
        qr.setSpacing(4)
        for label in ("ALLON", "ALLOFF", "TEST", "LIST"):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet("font-size:11px;padding:2px 6px;font-weight:600;")
            btn.clicked.connect(lambda checked, c=label: self.on_test_quick(c))
            qr.addWidget(btn)
        sl.addLayout(qr)

        # ON/OFF 发送
        sr = QHBoxLayout()
        sr.setSpacing(4)
        sr.addWidget(QLabel("指令:"))
        self.test_cmd_combo = QComboBox()
        self.test_cmd_combo.addItems(["ON", "OFF"])
        self.test_cmd_combo.setFixedWidth(70)
        sr.addWidget(self.test_cmd_combo)
        sr.addWidget(QLabel("通道:"))
        self.test_relay_spin = QSpinBox()
        self.test_relay_spin.setRange(0, 47)
        self.test_relay_spin.setFixedWidth(64)
        sr.addWidget(self.test_relay_spin)
        send_btn = QPushButton("发送")
        send_btn.setObjectName("btn_primary")
        send_btn.setFixedHeight(28)
        send_btn.clicked.connect(self.on_test_send)
        sr.addWidget(send_btn)
        sl.addLayout(sr)

        # 自定义指令
        cr = QHBoxLayout()
        cr.setSpacing(4)
        self.test_custom_input = QLineEdit()
        self.test_custom_input.setPlaceholderText("输入自定义指令...")
        cr.addWidget(self.test_custom_input)
        cst_send = QPushButton("发送")
        cst_send.setFixedHeight(28)
        cst_send.clicked.connect(self.on_test_custom)
        cr.addWidget(cst_send)
        sl.addLayout(cr)

        # 接收数据显示
        self.test_received_label = QLabel("等待数据...")
        self.test_received_label.setObjectName("monitor_rx")
        self.test_received_label.setWordWrap(True)
        self.test_received_label.setMinimumHeight(50)
        self.test_received_label.setMaximumHeight(80)
        sl.addWidget(self.test_received_label)

        sg.setLayout(sl)
        left.addWidget(sg)

        # -- 网格配置 --
        gg = QGroupBox("📐 网格")
        gl = QVBoxLayout(gg)
        gl.setContentsMargins(10, 10, 10, 10)
        gl.setSpacing(6)

        rc = QHBoxLayout()
        rc.setSpacing(8)
        rc.addWidget(QLabel("行:"))
        self.grid_rows_label = QLabel(str(global_cfg.ELECTRODE_ROWS))
        self.grid_rows_label.setAlignment(Qt.AlignCenter)
        self.grid_rows_label.setFixedSize(40, 30)
        self.grid_rows_label.setStyleSheet("background:#fff;border:1px solid #cbd5e1;border-radius:5px;font-weight:700;font-size:15px;")
        rc.addWidget(self.grid_rows_label)
        rup = QPushButton("▲")
        rup.setFixedSize(26, 22)
        rup.setStyleSheet("padding:0;font-size:10px;")
        rup.clicked.connect(lambda: self._spin_row(1))
        rc.addWidget(rup)
        rdn = QPushButton("▼")
        rdn.setFixedSize(26, 22)
        rdn.setStyleSheet("padding:0;font-size:10px;")
        rdn.clicked.connect(lambda: self._spin_row(-1))
        rc.addWidget(rdn)
        rc.addSpacing(12)
        rc.addWidget(QLabel("列:"))
        self.grid_cols_label = QLabel(str(global_cfg.ELECTRODE_COLS))
        self.grid_cols_label.setAlignment(Qt.AlignCenter)
        self.grid_cols_label.setFixedSize(40, 30)
        self.grid_cols_label.setStyleSheet("background:#fff;border:1px solid #cbd5e1;border-radius:5px;font-weight:700;font-size:15px;")
        rc.addWidget(self.grid_cols_label)
        cup = QPushButton("▲")
        cup.setFixedSize(26, 22)
        cup.setStyleSheet("padding:0;font-size:10px;")
        cup.clicked.connect(lambda: self._spin_col(1))
        rc.addWidget(cup)
        cdn = QPushButton("▼")
        cdn.setFixedSize(26, 22)
        cdn.setStyleSheet("padding:0;font-size:10px;")
        cdn.clicked.connect(lambda: self._spin_col(-1))
        rc.addWidget(cdn)
        rc.addStretch()
        gl.addLayout(rc)

        # 模式切换
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_sd_btn = QPushButton("✏️ 起点/终点")
        self.mode_sd_btn.setObjectName("mode_btn")
        self.mode_sd_btn.setCheckable(True)
        self.mode_sd_btn.setChecked(False)
        self.mode_sd_btn.clicked.connect(lambda: self.on_set_mode("sd"))
        mode_row.addWidget(self.mode_sd_btn)
        self.mode_obstacle_btn = QPushButton("🚧 障碍物")
        self.mode_obstacle_btn.setObjectName("mode_btn")
        self.mode_obstacle_btn.setCheckable(True)
        self.mode_obstacle_btn.clicked.connect(lambda: self.on_set_mode("obstacle"))
        mode_row.addWidget(self.mode_obstacle_btn)
        self.new_grid_btn = QPushButton("🆕 新建")
        self.new_grid_btn.clicked.connect(self.on_new_grid)
        mode_row.addWidget(self.new_grid_btn)
        gl.addLayout(mode_row)

        # 网格操作按钮
        grid_actions = QHBoxLayout()
        grid_actions.setSpacing(6)
        clr_obs = QPushButton("清除障碍物")
        clr_obs.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        grid_actions.addWidget(clr_obs)
        rst_grid = QPushButton("重置网格")
        rst_grid.clicked.connect(self.on_reset_grid)
        grid_actions.addWidget(rst_grid)
        gl.addLayout(grid_actions)

        gg.setLayout(gl)
        left.addWidget(gg)

        # -- 液滴配置 --
        dg = QGroupBox("💧 液滴")
        dl = QVBoxLayout(dg)
        dl.setContentsMargins(10, 10, 10, 10)
        dl.setSpacing(6)

        # 液滴编号导航
        dn = QHBoxLayout()
        dn.setSpacing(4)
        dn.addWidget(QLabel("编号:"))
        self.prev_droplet_btn = QPushButton("◀")
        self.prev_droplet_btn.setToolTip("上一个液滴")
        self.prev_droplet_btn.setStyleSheet("padding:4px 10px;font-size:13px;")
        self.prev_droplet_btn.clicked.connect(self.on_prev_droplet)
        dn.addWidget(self.prev_droplet_btn)
        self.droplet_label = QLabel("1")
        self.droplet_label.setAlignment(Qt.AlignCenter)
        self.droplet_label.setFixedSize(36, 30)
        self.droplet_label.setStyleSheet("background:#fff;border:1px solid #cbd5e1;border-radius:5px;font-weight:700;font-size:16px;")
        dn.addWidget(self.droplet_label)
        self.next_droplet_btn = QPushButton("▶")
        self.next_droplet_btn.setToolTip("下一个液滴")
        self.next_droplet_btn.setStyleSheet("padding:4px 10px;font-size:13px;")
        self.next_droplet_btn.clicked.connect(self.on_next_droplet)
        dn.addWidget(self.next_droplet_btn)
        dn.addSpacing(8)
        self.first_droplet_btn = QPushButton("⏮ 回到1")
        self.first_droplet_btn.setToolTip("回到液滴1")
        self.first_droplet_btn.clicked.connect(self.on_first_droplet)
        dn.addWidget(self.first_droplet_btn)
        dn.addStretch()
        dl.addLayout(dn)

        # 液滴操作按钮行
        da = QHBoxLayout()
        da.setSpacing(6)
        self.clear_droplet_btn = QPushButton("清除当前液滴")
        self.clear_droplet_btn.clicked.connect(self.on_clear_droplet)
        da.addWidget(self.clear_droplet_btn)
        self.clear_all_droplets_btn = QPushButton("清除全部液滴")
        self.clear_all_droplets_btn.clicked.connect(self.on_clear_all_droplets)
        da.addWidget(self.clear_all_droplets_btn)
        dl.addLayout(da)

        # 起点/终点显示
        info_grid = QHBoxLayout()
        info_grid.setSpacing(16)
        self.droplet_start_label = QLabel("起点: 未设置")
        self.droplet_start_label.setStyleSheet("color:#3b78ff;font-size:13px;font-weight:500;")
        info_grid.addWidget(self.droplet_start_label)
        self.droplet_target_label = QLabel("目标: 未设置")
        self.droplet_target_label.setStyleSheet("color:#f59e0b;font-size:13px;font-weight:500;")
        info_grid.addWidget(self.droplet_target_label)
        dl.addLayout(info_grid)

        self.droplet_summary_label = QLabel("配对: 0/8  已配置: 0 个液滴")
        self.droplet_summary_label.setStyleSheet("color:#059669;font-weight:600;font-size:13px;")
        dl.addWidget(self.droplet_summary_label)

        dg.setLayout(dl)
        left.addWidget(dg)

        # -- 路径规划与执行 --
        pg = QGroupBox("🚀 路径")
        pl = QVBoxLayout(pg)
        pl.setContentsMargins(10, 10, 10, 10)
        pl.setSpacing(6)

        delay_row = QHBoxLayout()
        delay_row.setSpacing(6)
        delay_row.addWidget(QLabel("执行间隔:"))
        self.delay_spinbox = QComboBox()
        self.delay_spinbox.addItems(["100", "200", "500", "1000"])
        self.delay_spinbox.setCurrentText("500")
        self.delay_spinbox.setFixedWidth(90)
        delay_row.addWidget(self.delay_spinbox)
        delay_row.addWidget(QLabel("毫秒/步"))
        delay_row.addStretch()
        pl.addLayout(delay_row)

        path_btns = QHBoxLayout()
        path_btns.setSpacing(8)
        self.plan_path_btn = QPushButton("🗺️ 规划路径")
        self.plan_path_btn.setObjectName("btn_primary")
        self.plan_path_btn.clicked.connect(self.on_plan_path)
        path_btns.addWidget(self.plan_path_btn)
        self.run_path_btn = QPushButton("▶ 执行")
        self.run_path_btn.setObjectName("btn_run")
        self.run_path_btn.clicked.connect(self.on_run_path)
        path_btns.addWidget(self.run_path_btn)
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setObjectName("btn_stop")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        path_btns.addWidget(self.stop_btn)
        pl.addLayout(path_btns)

        pg.setLayout(pl)
        left.addWidget(pg)

        left.addStretch()

        # ────────── 中间: 电极网格 ──────────
        grid_wrapper = QWidget()
        gw = QVBoxLayout(grid_wrapper)
        gw.setContentsMargins(6, 10, 6, 10)
        # 网格白色背景卡片
        grid_bg = QWidget()
        grid_bg.setStyleSheet("background:#ffffff;border:1px solid #d4d8dd;border-radius:8px;")
        gbg = QVBoxLayout(grid_bg)
        gbg.setContentsMargins(16, 16, 16, 16)
        gbg.addWidget(self.grid_widget, 1)
        gw.addWidget(grid_bg, 1)

        # ────────── 右面板 (280px) ──────────
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_panel.setMinimumWidth(260)
        right_panel.setMaximumWidth(320)
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(6, 10, 10, 10)
        right.setSpacing(8)

        # -- 路径信息 --
        pig = QGroupBox("📋 路径信息")
        pil = QVBoxLayout(pig)
        pil.setContentsMargins(10, 10, 10, 10)
        pil.setSpacing(4)
        self.path_info_label = QLabel("尚无路径规划\n\n请先在左侧面板配置液滴，\n然后点击「规划路径」")
        self.path_info_label.setWordWrap(True)
        self.path_info_label.setStyleSheet("color:#64748b;font-size:13px;line-height:1.6;")
        pil.addWidget(self.path_info_label)
        pig.setLayout(pil)
        right.addWidget(pig)

        # -- 图例 --
        lg = QGroupBox("🎨 图例")
        ll = QVBoxLayout(lg)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(6)
        legend_items = [
            ("起点", "#3b78ff"), ("目标", "#f59e0b"),
            ("障碍物", "#1e293b"), ("空闲", "#e8ecf0"),
        ]
        for text, color in legend_items:
            lr = QHBoxLayout()
            lr.setSpacing(10)
            sw = QWidget()
            sw.setFixedSize(20, 20)
            sw.setStyleSheet(f"background:{color};border:1px solid #cbd5e1;border-radius:4px;")
            lr.addWidget(sw)
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size:14px;")
            lr.addWidget(lbl)
            lr.addStretch()
            ll.addLayout(lr)

        # 路径颜色说明
        ll.addSpacing(6)
        path_legend_title = QLabel("路径颜色（按液滴编号）:")
        path_legend_title.setStyleSheet("font-size:12px;color:#94a3b8;font-weight:600;")
        ll.addWidget(path_legend_title)
        path_colors = ["#3b78ff", "#ff5722", "#4caf50", "#9c27b0",
                       "#ffb320", "#00bcd4", "#e91e63", "#3f51b5"]
        pc_grid = QHBoxLayout()
        pc_grid.setSpacing(4)
        for i, c in enumerate(path_colors):
            sw = QWidget()
            sw.setFixedSize(18, 18)
            sw.setToolTip(f"液滴{i+1}")
            sw.setStyleSheet(f"background:{c};border-radius:3px;")
            pc_grid.addWidget(sw)
        pc_grid.addStretch()
        ll.addLayout(pc_grid)

        lg.setLayout(ll)
        right.addWidget(lg)

        right.addStretch()

        # ────────── 组装 ──────────
        parent_splitter.addWidget(left_panel)
        parent_splitter.addWidget(grid_wrapper)
        parent_splitter.addWidget(right_panel)
        parent_splitter.setStretchFactor(0, 0)
        parent_splitter.setStretchFactor(1, 1)
        parent_splitter.setStretchFactor(2, 0)
        parent_splitter.setSizes([380, 800, 280])

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
            self.serial_status_label.setText("未连接")
            self.serial_status_label.setStyleSheet("color: #dc2626; font-weight: 700; font-size: 18px;")
            self.tb_status.setText("● 串口已断开")
            self.tb_status.setStyleSheet("color:#dc2626;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #dc2626;border-radius:12px;background:#fef2f2;")
            self.statusBar().showMessage("串口已断开连接")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.serial_status_label.setText(f"已连接 ({self.port_combo.currentText()})")
            self.serial_status_label.setStyleSheet("color: #16a34a; font-weight: 700; font-size: 18px;")
            self.tb_status.setText("● 串口已连接")
            self.tb_status.setStyleSheet("color:#059669;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #059669;border-radius:12px;background:#ecfdf5;")
            self.statusBar().showMessage(f"串口已连接：{self.port_combo.currentText()}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self.serial_connected = False
            self.serial_status_label.setText("连接失败")
            self.serial_status_label.setStyleSheet("color: #ea580c; font-weight: 700; font-size: 18px;")
            self.tb_status.setText("● 连接失败")
            self.tb_status.setStyleSheet("color:#ea580c;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #ea580c;border-radius:12px;background:#fff7ed;")
            self.statusBar().showMessage("串口连接失败")
            self.connect_btn.setChecked(False)

    @pyqtSlot(str)
    def on_serial_data(self, data):
        """处理串口接收数据。"""
        self.statusBar().showMessage(f"收到: {data}")
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

        self.tb_status.setText(f"● 规划完成: {success_count}/{len(results)}")
        self.tb_status.setStyleSheet("color:#059669;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #059669;border-radius:12px;background:#ecfdf5;")
        self.statusBar().showMessage(f"规划完成: {success_count}/{len(results)} 条路径")

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
                self.tb_status.setText(f"● 液滴{droplet_id} 运行中")
                self.tb_status.setStyleSheet("color:#d97706;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #d97706;border-radius:12px;background:#fffbeb;")

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
        self.tb_status.setText("● 全部完成")
        self.tb_status.setStyleSheet("color:#059669;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #059669;border-radius:12px;background:#ecfdf5;")
        self.statusBar().showMessage("所有液滴路径执行完成")

    def on_stop(self):
        """停止液滴移动。"""
        self.is_running = False
        self.move_timer.stop()
        # 断开所有继电器
        self.serial_thread.send_alloff()
        self.run_path_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.tb_status.setText("● 已停止")
        self.statusBar().showMessage("路径执行已停止，所有继电器已断开")
        self.tb_status.setStyleSheet("color:#dc2626;font-size:13px;font-weight:700;padding:4px 14px;border:1px solid #dc2626;border-radius:12px;background:#fef2f2;")

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
        self.statusBar().showMessage(
            f"液滴{droplet_id} 步骤 {self.current_droplet_index + 1}/{len(self.current_path)}: "
            f"({current_pos[0]}, {current_pos[1]}) 索引:{current_index}")

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

    # ── 最近文件动态填充 ──────────────────────

    def _populate_recent_menu(self):
        """动态填充最近文件子菜单。"""
        self.recent_menu.clear()
        files = self.project_manager.get_recent_files()
        if not files:
            self.recent_menu.setEnabled(False)
            action = self.recent_menu.addAction("(无最近文件)")
            action.setEnabled(False)
            return
        self.recent_menu.setEnabled(True)
        for fp in files:
            name = os.path.basename(fp)
            dirname = os.path.dirname(fp)
            action = self.recent_menu.addAction(f"{name}  —  {dirname}")
            action.setData(fp)
            action.triggered.connect(lambda checked, path=fp: self._project_open_recent(path))

    def _project_open_recent(self, filepath):
        """打开最近工程。"""
        self.project_manager.open_project(filepath)

    # ── 设置对话框 ────────────────────────────

    def _open_settings(self):
        """以对话框方式打开设置面板。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("设置")
        dlg.setMinimumWidth(700)
        dlg.setMinimumHeight(600)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        settings_widget = SettingsWidget(self)
        layout.addWidget(settings_widget)
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("soft_btn")
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dlg.exec_()

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

    window.log_panel.log_info("系统启动完成")

    # 关闭启动画面
    splash_mgr.close()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
