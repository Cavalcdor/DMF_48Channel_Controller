"""
DMF 48-通道控制器主应用程序
PyQt5 界面，整合串口通信、电极网格、寻路算法
"""

import sys
import os
import json
from datetime import datetime
from collections import Counter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QGroupBox, QMessageBox,
    QSizePolicy, QSpinBox, QLineEdit, QSplitter, QAction, QMenu,
    QDialog, QFrame, QToolButton, QTextEdit, QFileDialog, QProgressBar,
    QTabWidget, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QDateTime
from PyQt5.QtGui import QFont, QColor, QPixmap

from src import global_cfg
from src.serial_driver import SerialThread, VIRTUAL_PORT_NAME
from src.grid_widget import ElectrodeGrid
from src.path_algorithm import a_star_shortest_path, path_to_indices, plan_multiple_paths
from src.splash_screen import SplashManager, VERSION, AUTHOR, YEAR
from src.about_dialog import AboutDialog
from src.auto_update import check_for_update
from src.log_panel import LogPanel
from src.settings import SettingsWidget
from src.project_manager import ProjectManager


def _resource_path(relative_path):
    """获取资源文件的绝对路径（兼容 PyInstaller 打包模式）。"""
    try:
        # PyInstaller 打包后，资源在 sys._MEIPASS 目录
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48通道控制器")
        self.setMinimumSize(1200, 750)
        self.showMaximized()

        # ============ 初始化模块 ============
        self.serial_thread = SerialThread()
        # 录制钩子
        self._original_send = self.serial_thread.send_cmd
        self.serial_thread.send_cmd = self._hooked_send_cmd
        self.grid_widget = ElectrodeGrid()
        self.is_running = False
        self.current_droplet_index = 0  # 液滴在当前路径上的步索引
        self.current_path = []  # 当前正在执行的路径
        self.droplet_plans = []  # 所有液滴的规划结果 [{'path':..., 'droplet_id':..., ...}]
        self.current_plan_index = 0  # 当前执行到第几个液滴的路径
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.move_droplet_step)
        self.auto_mode = False  # 默认单步模式
        self.sync_mode = False   # False=逐个(one-by-one), True=同步(sync)
        self.sync_progress = []  # 同步模式: [{'droplet_id','path','step'},...]

        # ============ 通道测试相关 ============
        self.test_running = False
        self.test_channel_index = 0  # 当前测试的通道号
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.test_channel_step)

        # ============ 液滴裂分 ============
        self.split_timer = QTimer()
        self.split_timer.timeout.connect(self._split_pull_step)
        self._split_pull_queue = []    # 逐层队列 list[list[int]]
        self._split_pull_layer = 0     # 当前层索引
        self._split_on_channels = []   # 第一层 ON 的电极（相邻的）
        self._split_off_channels = []  # OFF 的电极（中心）

        # ============ 芯片测试状态 ============
        self.chip_test_running = False
        self.chip_test_current = -1
        self.chip_bad_cells = set()          # 坏点坐标集合 {(row,col), ...}

        # ============ 连接串口信号 ============
        self.serial_thread.data_received.connect(self.on_serial_data)
        self.serial_thread.error.connect(self.on_serial_error)
        self.serial_thread.port_opened.connect(self.on_port_opened)

        # ============ 连接网格信号 ============
        self.grid_widget.droplet_config_changed.connect(self.update_droplet_info)
        self.grid_widget.mode_changed.connect(self.on_mode_changed)
        self.grid_widget.undo_state_changed.connect(self._on_undo_state_changed)
        self.grid_widget.chip_test_cell_clicked.connect(self.on_chip_test_cell_selected)
        self.grid_widget.chip_test_enter_pressed.connect(lambda: self.on_chip_mark('pass'))
        self.grid_widget.split_center_selected.connect(self._on_split_center_selected)
        self.grid_widget.multi_selection_changed.connect(self._on_multi_selection_changed)

        # ============ 撤销/重做状态 ============
        self._undo_action = None
        self._redo_action = None

        # ============ 操作录制 ============
        self.recording = False
        self.recorded_steps = []  # [(cmd_str, timestamp), ...]

        # ============ 通知音效 ============
        self.sound_enabled = True

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
        """应用学术风格样式 — 直角、清晰边框、传统仪器配色。"""
        stylesheet = """
        /* ========== 全局 ========== */
        QMainWindow, QWidget#central_widget {
            background-color: #f0f0f0;
        }
        QWidget {
            font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
            color: #202020;
            font-size: 15px;
        }

        /* ========== 菜单栏 ========== */
        QMenuBar {
            background-color: #e8e8e8;
            border-bottom: 1px solid #b0b0b0;
            padding: 2px 0;
        }
        QMenuBar::item {
            padding: 4px 12px;
            margin: 0;
        }
        QMenuBar::item:selected {
            background: #d0d0d0;
        }
        QMenu {
            background: #ffffff;
            border: 1px solid #909090;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 24px 6px 16px;
        }
        QMenu::item:selected {
            background: #d0e0f0;
            color: #000000;
        }
        QMenu::separator {
            height: 1px;
            background: #c0c0c0;
            margin: 4px 8px;
        }

        /* ========== 工具栏 ========== */
        QWidget#app_toolbar {
            background-color: #e8e8e8;
            border-bottom: 1px solid #b0b0b0;
            padding: 4px 10px;
        }
        QToolButton {
            border: 1px solid #909090;
            font-size: 15px;
            padding: 4px 12px;
            color: #000000;
            background: #f5f5f5;
            font-weight: 600;
        }
        QToolButton:hover {
            background: #e0e0e0;
        }
        QToolButton:pressed, QToolButton:checked {
            background: #c0c0c0;
        }

        /* ========== 分割器手柄 ========== */
        QSplitter::handle {
            background: #c0c0c0;
        }
        QSplitter::handle:horizontal { width: 3px; }
        QSplitter::handle:vertical { height: 3px; }

        /* ========== GroupBox ========== */
        QGroupBox {
            background: #ffffff;
            border: 1px solid #b0b0b0;
            margin-top: 16px;
            padding: 18px 12px 12px 12px;
            font-weight: 600;
            color: #000000;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 6px;
            font-weight: 700;
            color: #000000;
            font-size: 15px;
        }

        /* ========== 按钮 ========== */
        QPushButton {
            border: 1px solid #909090;
            padding: 7px 18px;
            font-weight: 600;
            color: #000000;
            background: #f5f5f5;
            font-size: 15px;
        }
        QPushButton:hover {
            background: #e8e8e8;
            border-color: #707070;
        }
        QPushButton:pressed {
            background: #d8d8d8;
        }
        QPushButton:disabled {
            background: #f0f0f0;
            color: #a0a0a0;
            border-color: #c0c0c0;
        }

        /* 蓝色强调按钮 — 规划/发送 */
        QPushButton#btn_primary {
            background: #3060b0;
            color: #ffffff;
            border: 1px solid #204080;
            font-weight: 700;
            font-size: 15px;
            padding: 5px 16px;
        }
        QPushButton#btn_primary:hover {
            background: #4070c0;
        }
        QPushButton#btn_primary:pressed {
            background: #2050a0;
        }
        QPushButton#btn_primary:disabled {
            background: #90a0c0;
            color: #d0d0d0;
        }

        /* 绿色运行按钮 — 执行路径 */
        QPushButton#btn_run {
            background: #308050;
            color: #ffffff;
            border: 1px solid #206040;
            font-weight: 700;
            font-size: 15px;
            padding: 5px 16px;
        }
        QPushButton#btn_run:hover {
            background: #409060;
        }
        QPushButton#btn_run:pressed {
            background: #207040;
        }
        QPushButton#btn_run:disabled {
            background: #80a090;
            color: #d0d0d0;
        }

        /* 红色停止按钮 */
        QPushButton#btn_stop {
            background: #b03030;
            color: #ffffff;
            border: 1px solid #802020;
            font-weight: 700;
            font-size: 15px;
            padding: 5px 16px;
        }
        QPushButton#btn_stop:hover {
            background: #c04040;
        }
        QPushButton#btn_stop:pressed {
            background: #a02020;
        }
        QPushButton#btn_stop:disabled {
            background: #c09090;
            color: #d0d0d0;
        }

        /* 琥珀色强调按钮 — 回到第一个液滴 */
        QPushButton#btn_amber {
            background: #b08020;
            color: #ffffff;
            border: 1px solid #906010;
            font-weight: 700;
            font-size: 13px;
            padding: 5px 16px;
        }
        QPushButton#btn_amber:hover {
            background: #c09030;
        }
        QPushButton#btn_amber:pressed {
            background: #a07010;
        }

        /* 清除/危险按钮 — 用于清除障碍/清除液滴/重置 */
        QPushButton#btn_danger {
            background: #ffffff;
            color: #b03030;
            border: 1px solid #d09090;
            font-weight: 600;
            font-size: 13px;
            padding: 4px 10px;
        }
        QPushButton#btn_danger:hover {
            background: #fff0f0;
            border-color: #b03030;
        }
        QPushButton#btn_danger:pressed {
            background: #ffe0e0;
        }

        /* 模式选择按钮组 */
        QPushButton#mode_btn {
            background: #ffffff;
            color: #404040;
            border: 1px solid #909090;
            font-weight: 600;
            padding: 5px 12px;
        }
        QPushButton#mode_btn:hover {
            background: #f0f0f0;
        }
        QPushButton#mode_btn:checked {
            background: #404040;
            color: #ffffff;
            border-color: #404040;
        }

        /* 障碍物模式按钮 — 红色系区分 */
        QPushButton#mode_btn_obstacle {
            background: #ffffff;
            color: #404040;
            border: 1px solid #909090;
            font-weight: 600;
            padding: 5px 12px;
        }
        QPushButton#mode_btn_obstacle:hover {
            background: #f0f0f0;
        }
        QPushButton#mode_btn_obstacle:checked {
            background: #b03030;
            color: #ffffff;
            border-color: #b03030;
        }

        /* ========== 输入控件 ========== */
        QComboBox {
            border: 1px solid #909090;
            padding: 3px 6px;
            background: #ffffff;
            color: #000000;
            min-height: 24px;
        }
        QComboBox:hover { border-color: #707070; }
        QComboBox:focus { border-color: #3060b0; }

        QSpinBox {
            border: 1px solid #909090;
            padding: 3px 6px;
            background: #ffffff;
            color: #000000;
            min-height: 24px;
        }
        QSpinBox:focus { border-color: #3060b0; }

        QLineEdit {
            border: 1px solid #909090;
            padding: 3px 8px;
            background: #ffffff;
            color: #000000;
            min-height: 24px;
        }
        QLineEdit:focus { border-color: #3060b0; }

        /* ========== 标签 ========== */
        QLabel {
            color: #404040;
        }
        QLabel#status_value {
            font-weight: 600;
            font-size: 16px;
        }
        QLabel#section_title {
            font-weight: 700;
            color: #000000;
            padding: 4px 0;
            font-size: 16px;
        }

        /* ========== 标签页 ========== */
        QTabWidget::pane {
            background: #f0f0f0;
            border: 1px solid #b0b0b0;
            border-top: none;
        }
        QTabBar::tab {
            background: #e0e0e0;
            border: 1px solid #b0b0b0;
            border-bottom: none;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 15px;
            min-width: 80px;
        }
        QTabBar::tab:selected {
            background: #f0f0f0;
            border-bottom: 2px solid #3060b0;
        }
        QTabBar::tab:hover:!selected {
            background: #e8e8e8;
        }

        /* ========== 状态栏 ========== */
        QStatusBar {
            background: #e8e8e8;
            border-top: 1px solid #b0b0b0;
            color: #606060;
            padding: 2px 10px;
            max-height: 20px;
        }
        QStatusBar::item { border: none; }

        /* ========== 日志面板 ========== */
        QTextEdit#log_view {
            background: #0a0a1a;
            color: #e0e0e0;
            border: 1px solid #404060;
            padding: 8px;
            font-family: "Consolas", "Courier New", monospace;
        }

        /* ========== 串口监视区 ========== */
        QTextEdit#monitor_rx {
            background: #0a0a1a;
            color: #e0e0e0;
            border: 1px solid #404060;
            padding: 6px;
            font-family: "Consolas", "Courier New", monospace;
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
        act_save_as.triggered.connect(self._project_save_as)
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

        # ============ 编辑菜单 ============
        edit_menu = menubar.addMenu("编辑(&E)")
        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self._on_undo)
        edit_menu.addAction(self.act_undo)
        self.act_redo = QAction("重做", self)
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self._on_redo)
        edit_menu.addAction(self.act_redo)

        self._undo_action = self.act_undo
        self._redo_action = self.act_redo

        edit_menu.addSeparator()
        act_screenshot = QAction("导出网格截图...", self)
        act_screenshot.setShortcut("Ctrl+E")
        act_screenshot.triggered.connect(self._export_grid_screenshot)
        edit_menu.addAction(act_screenshot)

        act_screenshot_clip = QAction("复制网格截图到剪贴板", self)
        act_screenshot_clip.setShortcut("Ctrl+Shift+E")
        act_screenshot_clip.triggered.connect(self._copy_grid_screenshot)
        edit_menu.addAction(act_screenshot_clip)

        # ============ 录制菜单 ============
        self.record_menu = edit_menu.addMenu("录制")
        self.act_record = QAction("开始录制操作...", self)
        self.act_record.triggered.connect(self._toggle_recording)
        self.record_menu.addAction(self.act_record)
        self.act_replay = QAction("回放录制...", self)
        self.act_replay.setEnabled(False)
        self.act_replay.triggered.connect(self._replay_recording)
        self.record_menu.addAction(self.act_replay)
        self.act_export_record = QAction("导出录制...", self)
        self.act_export_record.setEnabled(False)
        self.act_export_record.triggered.connect(self._export_recording)
        self.record_menu.addAction(self.act_export_record)

        edit_menu.addSeparator()
        act_toggle_sound = QAction("完成通知音效", self)
        act_toggle_sound.setCheckable(True)
        act_toggle_sound.setChecked(True)
        act_toggle_sound.triggered.connect(lambda checked: setattr(self, 'sound_enabled', checked))
        edit_menu.addAction(act_toggle_sound)

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

        btn_new = _tb_btn("新建", "新建工程 (Ctrl+N)")
        btn_new.clicked.connect(self._project_new)
        tb_layout.addWidget(btn_new)
        btn_open = _tb_btn("打开", "打开工程 (Ctrl+O)")
        btn_open.clicked.connect(self._project_open)
        tb_layout.addWidget(btn_open)
        btn_save = _tb_btn("保存", "保存工程 (Ctrl+S)")
        btn_save.clicked.connect(self._project_save)
        tb_layout.addWidget(btn_save)

        sep1 = QLabel("│")
        sep1.setStyleSheet("color:#cbd5e1;padding:0 6px;")
        tb_layout.addWidget(sep1)

        # 串口选择
        tb_layout.addWidget(QLabel("端口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(120)
        self.port_combo.setMaximumWidth(180)
        tb_layout.addWidget(self.port_combo)
        self.refresh_ports_btn = QToolButton()
        self.refresh_ports_btn.setText("刷新")
        self.refresh_ports_btn.setToolTip("扫描串口")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        tb_layout.addWidget(self.refresh_ports_btn)
        self.connect_btn = QToolButton()
        self.connect_btn.setText("连接")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        tb_layout.addWidget(self.connect_btn)

        tb_layout.addStretch()

        self.tb_status = QLabel("● 系统就绪")
        self.tb_status.setStyleSheet("""
            color:#059669; font-size:14px; font-weight:700;
            padding:6px 16px; border:1px solid #059669; border-radius:14px;
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
        self.log_panel.setMinimumHeight(160)
        self.log_panel.setMaximumHeight(260)
        log_layout.addWidget(self.log_panel)
        self.main_splitter.addWidget(log_container)
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([560, 120])

        outer_layout.addWidget(self.main_splitter, 1)

        # ============ 工程管理器 ============
        self.project_manager = ProjectManager(self)

        # ============ 状态栏 ============
        self.statusBar().showMessage("就绪")

        # ============ 初始化串口 ============
        self.refresh_serial_ports()

    # ── 左侧面板 + 网格 + 右侧面板 ──────────────────────

    def _create_main_content(self, parent_splitter):
        """创建主内容区: 左控制面板(含标签页) | 网格视图 | 右信息面板。"""
        # ────────── 左面板 (520-680px, 带标签页) ──────────
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setMinimumWidth(520)
        left_panel.setMaximumWidth(680)
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(10, 10, 8, 10)
        left.setSpacing(0)

        self.left_tabs = QTabWidget()
        self.left_tabs.setTabPosition(QTabWidget.North)

        # ========== Tab 0: 控制面板 ==========
        control_tab = QWidget()
        ct = QVBoxLayout(control_tab)
        ct.setContentsMargins(8, 10, 8, 8)
        ct.setSpacing(12)

        # -- 串口状态 --
        sg = QGroupBox("串口")
        sl = QVBoxLayout(sg)
        sl.setContentsMargins(14, 18, 14, 14)
        sl.setSpacing(10)
        self.serial_status_label = QLabel("未连接")
        self.serial_status_label.setObjectName("status_value")
        self.serial_status_label.setStyleSheet("color:#dc2626;font-size:16px;font-weight:700;")
        sl.addWidget(self.serial_status_label)

        # 快捷指令
        qr = QHBoxLayout()
        qr.setSpacing(6)
        for label in ("ALL ON", "ALL OFF", "LIST"):
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.setStyleSheet("font-weight:700;padding:0 8px;font-size:16px;")
            btn.clicked.connect(lambda checked, c=label: self.on_test_quick(c))
            qr.addWidget(btn, 1)
        sl.addLayout(qr)

        # 通道测试（可调间隔 + 单步）
        test_row = QHBoxLayout()
        test_row.setSpacing(6)
        test_row.addWidget(QLabel("通道测试:"))
        self.test_interval_spin = QSpinBox()
        self.test_interval_spin.setRange(50, 5000)
        self.test_interval_spin.setValue(500)
        self.test_interval_spin.setSingleStep(500)
        self.test_interval_spin.setFixedWidth(80)
        test_row.addWidget(self.test_interval_spin)
        test_row.addWidget(QLabel("ms"))
        self.test_start_btn = QPushButton("连续")
        self.test_start_btn.setObjectName("btn_run")
        self.test_start_btn.setFixedHeight(32)
        self.test_start_btn.clicked.connect(self.start_channel_test)
        test_row.addWidget(self.test_start_btn, 1)
        self.test_step_btn = QPushButton("单步")
        self.test_step_btn.setObjectName("btn_primary")
        self.test_step_btn.setFixedHeight(32)
        self.test_step_btn.setToolTip("手动测试下一个通道")
        self.test_step_btn.clicked.connect(self.step_channel_test)
        test_row.addWidget(self.test_step_btn, 1)
        self.test_stop_btn = QPushButton("停止")
        self.test_stop_btn.setObjectName("btn_stop")
        self.test_stop_btn.setFixedHeight(32)
        self.test_stop_btn.setEnabled(False)
        self.test_stop_btn.clicked.connect(self.stop_channel_test)
        test_row.addWidget(self.test_stop_btn, 1)
        sl.addLayout(test_row)

        # ON/OFF 发送
        sr = QHBoxLayout()
        sr.setSpacing(6)
        sr.addWidget(QLabel("指令:"))
        self.test_cmd_combo = QComboBox()
        self.test_cmd_combo.addItems(["ON", "OFF"])
        self.test_cmd_combo.setMinimumWidth(70)
        sr.addWidget(self.test_cmd_combo, 1)
        sr.addWidget(QLabel("通道:"))
        self.test_relay_spin = QSpinBox()
        self.test_relay_spin.setRange(0, 47)
        self.test_relay_spin.setMinimumWidth(60)
        sr.addWidget(self.test_relay_spin, 1)
        send_btn = QPushButton("发送")
        send_btn.setObjectName("btn_primary")
        send_btn.setFixedHeight(32)
        send_btn.clicked.connect(self.on_test_send)
        sr.addWidget(send_btn, 1)
        sl.addLayout(sr)

        # 自定义指令
        cr = QHBoxLayout()
        cr.setSpacing(6)
        self.test_custom_input = QLineEdit()
        self.test_custom_input.setPlaceholderText("输入指令...")
        self.test_custom_input.returnPressed.connect(self.on_test_custom)
        cr.addWidget(self.test_custom_input, 1)
        cst_send = QPushButton("发送")
        cst_send.setObjectName("btn_primary")
        cst_send.setFixedHeight(32)
        cst_send.clicked.connect(self.on_test_custom)
        cr.addWidget(cst_send)
        sl.addLayout(cr)

        # 接收数据显示
        self.test_received_label = QTextEdit()
        self.test_received_label.setReadOnly(True)
        self.test_received_label.setObjectName("monitor_rx")
        self.test_received_label.setMinimumHeight(60)
        self.test_received_label.setMaximumHeight(100)
        sl.addWidget(self.test_received_label)

        sg.setLayout(sl)
        ct.addWidget(sg)

        # -- 网格配置 --
        gg = QGroupBox("网格")
        gl = QVBoxLayout(gg)
        gl.setContentsMargins(14, 18, 14, 14)
        gl.setSpacing(8)

        # 固定网格尺寸提示
        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        info_label = QLabel("6 × 8  网格 (固定)")
        info_label.setStyleSheet("font-weight:700;font-size:17px;color:#3060b0;")
        info_row.addWidget(info_label)
        info_row.addStretch()
        gl.addLayout(info_row)

        # 模式切换
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self.mode_sd_btn = QPushButton("起点/终点")
        self.mode_sd_btn.setObjectName("mode_btn")
        self.mode_sd_btn.setCheckable(True)
        self.mode_sd_btn.setChecked(False)
        self.mode_sd_btn.clicked.connect(lambda: self.on_set_mode("sd"))
        mode_row.addWidget(self.mode_sd_btn, 1)
        self.mode_obstacle_btn = QPushButton("障碍物")
        self.mode_obstacle_btn.setObjectName("mode_btn_obstacle")
        self.mode_obstacle_btn.setCheckable(True)
        self.mode_obstacle_btn.clicked.connect(lambda: self.on_set_mode("obstacle"))
        mode_row.addWidget(self.mode_obstacle_btn, 1)
        gl.addLayout(mode_row)

        # 网格操作按钮
        grid_actions = QHBoxLayout()
        grid_actions.setSpacing(4)
        clr_obs = QPushButton("清除障碍")
        clr_obs.setObjectName("btn_danger")
        clr_obs.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        grid_actions.addWidget(clr_obs, 1)
        clr_wp = QPushButton("清除途经点")
        clr_wp.setObjectName("btn_danger")
        clr_wp.clicked.connect(self._clear_waypoints)
        grid_actions.addWidget(clr_wp, 1)
        rst_grid = QPushButton("重置")
        rst_grid.setObjectName("btn_danger")
        rst_grid.clicked.connect(self.on_reset_grid)
        grid_actions.addWidget(rst_grid, 1)
        gl.addLayout(grid_actions)

        gg.setLayout(gl)
        ct.addWidget(gg)

        # -- 液滴配置 --
        dg = QGroupBox("液滴")
        dl = QVBoxLayout(dg)
        dl.setContentsMargins(14, 18, 14, 14)
        dl.setSpacing(8)

        # 液滴编号导航
        dn = QHBoxLayout()
        dn.setSpacing(6)
        dn.addWidget(QLabel("编号:"))
        self.prev_droplet_btn = QPushButton("◀")
        self.prev_droplet_btn.setToolTip("上一个液滴")
        self.prev_droplet_btn.setStyleSheet("font-weight:700;padding:4px 12px;")
        self.prev_droplet_btn.clicked.connect(self.on_prev_droplet)
        dn.addWidget(self.prev_droplet_btn)
        self.droplet_label = QLabel("1")
        self.droplet_label.setAlignment(Qt.AlignCenter)
        self.droplet_label.setFixedSize(40, 34)
        self.droplet_label.setStyleSheet("background:#fff;border:1px solid #b0b0b0;font-weight:700;font-size:17px;")
        dn.addWidget(self.droplet_label)
        self.next_droplet_btn = QPushButton("▶")
        self.next_droplet_btn.setToolTip("下一个液滴")
        self.next_droplet_btn.setStyleSheet("font-weight:700;padding:4px 12px;")
        self.next_droplet_btn.clicked.connect(self.on_next_droplet)
        dn.addWidget(self.next_droplet_btn)
        self.next_droplet_text_btn = QPushButton("下一个")
        self.next_droplet_text_btn.setObjectName("btn_primary")
        self.next_droplet_text_btn.setFixedHeight(32)
        self.next_droplet_text_btn.clicked.connect(self.on_next_droplet)
        dn.addWidget(self.next_droplet_text_btn, 1)
        dn.addSpacing(8)
        self.first_droplet_btn = QPushButton("回到1")
        self.first_droplet_btn.setObjectName("btn_amber")
        self.first_droplet_btn.setFixedHeight(32)
        self.first_droplet_btn.setToolTip("回到液滴1")
        self.first_droplet_btn.clicked.connect(self.on_first_droplet)
        dn.addWidget(self.first_droplet_btn, 1)
        dl.addLayout(dn)

        # 液滴操作按钮行
        da = QHBoxLayout()
        da.setSpacing(6)
        self.clear_droplet_btn = QPushButton("清除当前")
        self.clear_droplet_btn.setObjectName("btn_danger")
        self.clear_droplet_btn.clicked.connect(self.on_clear_droplet)
        da.addWidget(self.clear_droplet_btn, 1)
        self.clear_all_droplets_btn = QPushButton("清除全部")
        self.clear_all_droplets_btn.setObjectName("btn_danger")
        self.clear_all_droplets_btn.clicked.connect(self.on_clear_all_droplets)
        da.addWidget(self.clear_all_droplets_btn, 1)
        dl.addLayout(da)

        # 起点/终点显示
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame{background:#f5f5f5;border:1px solid #d0d0d0;}")
        info_grid = QHBoxLayout(info_frame)
        info_grid.setContentsMargins(12, 8, 12, 8)
        info_grid.setSpacing(8)
        self.droplet_start_label = QLabel("起点: 未设置")
        self.droplet_start_label.setAlignment(Qt.AlignCenter)
        self.droplet_start_label.setStyleSheet("color:#3b78ff;font-weight:600;font-size:16px;")
        info_grid.addWidget(self.droplet_start_label, 1)
        sep = QLabel("|")
        sep.setStyleSheet("color:#cbd5e1;font-weight:700;")
        info_grid.addWidget(sep)
        self.droplet_target_label = QLabel("目标: 未设置")
        self.droplet_target_label.setAlignment(Qt.AlignCenter)
        self.droplet_target_label.setStyleSheet("color:#d08020;font-weight:600;font-size:16px;")
        info_grid.addWidget(self.droplet_target_label, 1)
        dl.addWidget(info_frame)

        self.droplet_summary_label = QLabel("已配对: 0/8\n已配置: 0 个液滴")
        self.droplet_summary_label.setStyleSheet("color:#059669;font-weight:600;line-height:1.6;padding:4px 0;")
        dl.addWidget(self.droplet_summary_label)

        dg.setLayout(dl)
        ct.addWidget(dg)

        # -- 路径规划与执行 --
        pg = QGroupBox("路径")
        pl = QVBoxLayout(pg)
        pl.setContentsMargins(14, 18, 14, 14)
        pl.setSpacing(8)

        delay_row = QHBoxLayout()
        delay_row.setSpacing(6)
        delay_row.addWidget(QLabel("执行间隔:"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(50, 5000)
        self.delay_spinbox.setValue(1000)
        self.delay_spinbox.setSingleStep(500)
        self.delay_spinbox.setFixedWidth(80)
        delay_row.addWidget(self.delay_spinbox)
        delay_row.addWidget(QLabel("ms"))
        delay_row.addStretch()

        # ── 执行模式: 逐个 / 同步 ──
        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("font-weight:600;")
        delay_row.addWidget(mode_label)
        self.seq_btn = QPushButton("逐个")
        self.seq_btn.setCheckable(True)
        self.seq_btn.setChecked(True)
        self.seq_btn.setFixedHeight(28)
        self.seq_btn.setToolTip("逐个执行: 一个液滴走完全程再切换到下一个")
        self.seq_btn.clicked.connect(lambda: self._set_exec_mode(False))
        delay_row.addWidget(self.seq_btn)
        self.sync_btn = QPushButton("同步")
        self.sync_btn.setCheckable(True)
        self.sync_btn.setChecked(False)
        self.sync_btn.setFixedHeight(28)
        self.sync_btn.setToolTip("同步推进: 所有液滴每步同时向前推进")
        self.sync_btn.clicked.connect(lambda: self._set_exec_mode(True))
        delay_row.addWidget(self.sync_btn)

        # ── 单步/自动模式切换 ──
        self.mode_toggle_btn = QPushButton("手动 ▶")
        self.mode_toggle_btn.setFixedHeight(28)
        self.mode_toggle_btn.setCheckable(True)
        self.mode_toggle_btn.setToolTip("切换 手动单步 / 自动定时执行")
        self.mode_toggle_btn.setStyleSheet(
            "QPushButton{background:#3060b0;color:#fff;font-weight:700;"
            "padding:4px 10px;border:1px solid #3060b0;font-size:13px;}"
            "QPushButton:hover{background:#2050a0;}")
        self.mode_toggle_btn.clicked.connect(self._toggle_path_mode)
        delay_row.addWidget(self.mode_toggle_btn)
        pl.addLayout(delay_row)

        path_btns = QHBoxLayout()
        path_btns.setSpacing(6)
        self.plan_path_btn = QPushButton("规划路径")
        self.plan_path_btn.setObjectName("btn_primary")
        self.plan_path_btn.clicked.connect(self.on_plan_path)
        path_btns.addWidget(self.plan_path_btn, 1)
        self.run_path_btn = QPushButton("执行路径")
        self.run_path_btn.setObjectName("btn_run")
        self.run_path_btn.clicked.connect(self.on_run_path)
        path_btns.addWidget(self.run_path_btn, 1)
        self.step_path_btn = QPushButton("单步")
        self.step_path_btn.setObjectName("btn_primary")
        self.step_path_btn.setToolTip("手动执行当前路径的下一步")
        self.step_path_btn.clicked.connect(self.on_step_path)
        self.step_path_btn.setEnabled(False)
        path_btns.addWidget(self.step_path_btn, 1)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("btn_stop")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        path_btns.addWidget(self.stop_btn, 1)
        pl.addLayout(path_btns)

        pg.setLayout(pl)
        ct.addWidget(pg)

        ct.addStretch()
        control_tab.setLayout(ct)

        # ========== Tab 1: 芯片测试 ==========
        chip_tab = QWidget()
        ch = QVBoxLayout(chip_tab)
        ch.setContentsMargins(8, 10, 8, 8)
        ch.setSpacing(10)

        # -- 测试状态与进度 --
        csg = QGroupBox("测试状态")
        csl = QVBoxLayout(csg)
        csl.setContentsMargins(14, 18, 14, 14)
        csl.setSpacing(8)

        self.chip_status_label = QLabel("芯片测试就绪")
        self.chip_status_label.setStyleSheet("font-weight:700;font-size:17px;color:#3060b0;")
        csl.addWidget(self.chip_status_label)

        # 当前通道显示
        self.chip_progress_label = QLabel("步进: 0 / 48  |  电极: 0")
        self.chip_progress_label.setStyleSheet("font-weight:600;font-size:16px;")
        csl.addWidget(self.chip_progress_label)

        # 进度条
        self.chip_progress_bar = QProgressBar()
        self.chip_progress_bar.setRange(0, 48)
        self.chip_progress_bar.setValue(0)
        self.chip_progress_bar.setTextVisible(True)
        self.chip_progress_bar.setFixedHeight(22)
        self.chip_progress_bar.setStyleSheet(
            "QProgressBar{background:#e0e0e0;border:1px solid #b0b0b0;text-align:center;"
            "font-size:12px;font-weight:600;}"
            "QProgressBar::chunk{background:#3060b0;}"
        )
        csl.addWidget(self.chip_progress_bar)

        self.chip_tested_label = QLabel("已测试: 0 / 48")
        self.chip_tested_label.setStyleSheet("font-weight:600;font-size:15px;color:#606060;")
        csl.addWidget(self.chip_tested_label)

        csg.setLayout(csl)
        ch.addWidget(csg)

        # -- 操作按钮 --
        cog = QGroupBox("操作")
        col = QVBoxLayout(cog)
        col.setContentsMargins(14, 18, 14, 14)
        col.setSpacing(8)

        chip_btn_row1 = QHBoxLayout()
        chip_btn_row1.setSpacing(6)
        self.chip_start_btn = QPushButton("开始测试")
        self.chip_start_btn.setObjectName("btn_run")
        self.chip_start_btn.setFixedHeight(34)
        self.chip_start_btn.setToolTip("进入芯片测试模式：点击网格选择电极进行测试")
        self.chip_start_btn.clicked.connect(self.on_chip_test_start)
        chip_btn_row1.addWidget(self.chip_start_btn, 1)
        self.chip_stop_btn = QPushButton("停止")
        self.chip_stop_btn.setObjectName("btn_stop")
        self.chip_stop_btn.setFixedHeight(34)
        self.chip_stop_btn.setEnabled(False)
        self.chip_stop_btn.clicked.connect(self.on_chip_test_stop)
        chip_btn_row1.addWidget(self.chip_stop_btn, 1)
        col.addLayout(chip_btn_row1)

        chip_btn_row2 = QHBoxLayout()
        chip_btn_row2.setSpacing(6)
        self.chip_pass_btn = QPushButton("✓ 通过")
        self.chip_pass_btn.setObjectName("btn_run")
        self.chip_pass_btn.setFixedHeight(34)
        self.chip_pass_btn.setEnabled(False)
        self.chip_pass_btn.clicked.connect(lambda: self.on_chip_mark('pass'))
        chip_btn_row2.addWidget(self.chip_pass_btn, 1)
        self.chip_fail_btn = QPushButton("✗ 坏点")
        self.chip_fail_btn.setObjectName("btn_stop")
        self.chip_fail_btn.setFixedHeight(34)
        self.chip_fail_btn.setEnabled(False)
        self.chip_fail_btn.clicked.connect(lambda: self.on_chip_mark('fail'))
        chip_btn_row2.addWidget(self.chip_fail_btn, 1)
        col.addLayout(chip_btn_row2)

        cog.setLayout(col)
        ch.addWidget(cog)

        # -- 结果 --
        crg = QGroupBox("测试结果")
        crl = QVBoxLayout(crg)
        crl.setContentsMargins(14, 18, 14, 14)
        crl.setSpacing(6)

        self.chip_result_label = QLabel("通过: 0  坏点: 0  未测: 48")
        self.chip_result_label.setStyleSheet("font-weight:600;font-size:16px;")
        crl.addWidget(self.chip_result_label)

        self.chip_fail_list_label = QLabel("坏点列表: (无)")
        self.chip_fail_list_label.setStyleSheet("color:#b03030;font-weight:600;font-size:15px;")
        self.chip_fail_list_label.setWordWrap(True)
        crl.addWidget(self.chip_fail_list_label)

        self.chip_export_btn = QPushButton("导出结果")
        self.chip_export_btn.setObjectName("btn_primary")
        self.chip_export_btn.setFixedHeight(32)
        self.chip_export_btn.setEnabled(False)
        self.chip_export_btn.clicked.connect(self.on_chip_export)
        crl.addWidget(self.chip_export_btn)

        crg.setLayout(crl)
        ch.addWidget(crg)

        ch.addStretch()
        chip_tab.setLayout(ch)

        # ──────────────────────── 液滴裂分标签页 ────────────────────────
        split_tab = QWidget()
        st = QVBoxLayout(split_tab)
        st.setContentsMargins(10, 10, 10, 10)
        st.setSpacing(10)

        # -- 选择中心电极 --
        ssg = QGroupBox("1. 选择裂分中心")
        ssl = QVBoxLayout(ssg)
        ssl.setContentsMargins(14, 18, 14, 14)
        ssl.setSpacing(8)

        self.split_status_label = QLabel("点击下方「进入裂分模式」后在网格上选择电极")
        self.split_status_label.setStyleSheet("font-weight:600;font-size:14px;color:#606060;")
        self.split_status_label.setWordWrap(True)
        ssl.addWidget(self.split_status_label)

        self.split_center_label = QLabel("中心电极: 未选择")
        self.split_center_label.setStyleSheet("font-weight:700;font-size:17px;color:#3060b0;")
        ssl.addWidget(self.split_center_label)

        split_btn_row = QHBoxLayout()
        self.split_enter_btn = QPushButton("进入裂分模式")
        self.split_enter_btn.setObjectName("btn_run")
        self.split_enter_btn.setFixedHeight(34)
        self.split_enter_btn.setCheckable(True)
        self.split_enter_btn.clicked.connect(self._toggle_split_mode)
        split_btn_row.addWidget(self.split_enter_btn, 1)

        self.split_clear_btn = QPushButton("清除选择")
        self.split_clear_btn.setFixedHeight(34)
        self.split_clear_btn.setEnabled(False)
        self.split_clear_btn.clicked.connect(self._clear_split_selection)
        split_btn_row.addWidget(self.split_clear_btn, 1)
        ssl.addLayout(split_btn_row)

        ssg.setLayout(ssl)
        st.addWidget(ssg)

        # -- 裂分参数 --
        spg = QGroupBox("2. 设置裂分参数")
        spl = QVBoxLayout(spg)
        spl.setContentsMargins(14, 18, 14, 14)
        spl.setSpacing(8)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("裂分方向:"))
        self.split_dir_combo = QComboBox()
        self.split_dir_combo.addItems(["水平 ←→", "垂直 ↕", "四向 ✦"])
        self.split_dir_combo.setCurrentIndex(0)
        self.split_dir_combo.currentIndexChanged.connect(self._on_split_param_changed)
        dir_row.addWidget(self.split_dir_combo, 1)
        spl.addLayout(dir_row)

        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel("子液滴数:"))
        self.split_count_combo = QComboBox()
        self.split_count_combo.addItems(["2 个"])
        self.split_count_combo.setCurrentIndex(0)
        self.split_count_combo.currentIndexChanged.connect(self._on_split_param_changed)
        cnt_row.addWidget(self.split_count_combo, 1)
        spl.addLayout(cnt_row)

        # 裂分预览提示
        self.split_preview_label = QLabel("提示: ON(绿) OFF(红) 中心(橙)")
        self.split_preview_label.setStyleSheet("font-size:13px;color:#888;")
        spl.addWidget(self.split_preview_label)

        spg.setLayout(spl)
        st.addWidget(spg)

        # -- 执行 --
        exg = QGroupBox("3. 执行裂分")
        exl = QVBoxLayout(exg)
        exl.setContentsMargins(14, 18, 14, 14)
        exl.setSpacing(8)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("逐级拉开延时:"))
        self.split_delay_spin = QSpinBox()
        self.split_delay_spin.setRange(30, 2000)
        self.split_delay_spin.setValue(150)
        self.split_delay_spin.setSuffix(" ms")
        self.split_delay_spin.setFixedWidth(110)
        delay_row.addWidget(self.split_delay_spin)
        delay_row.addStretch()
        exl.addLayout(delay_row)

        self.split_exec_btn = QPushButton("▶ 执行裂分")
        self.split_exec_btn.setObjectName("btn_primary")
        self.split_exec_btn.setFixedHeight(38)
        self.split_exec_btn.setEnabled(False)
        self.split_exec_btn.clicked.connect(self._execute_split)
        exl.addWidget(self.split_exec_btn)

        self.split_result_label = QLabel("就绪")
        self.split_result_label.setStyleSheet("font-weight:600;font-size:14px;color:#606060;")
        exl.addWidget(self.split_result_label)

        exg.setLayout(exl)
        st.addWidget(exg)
        st.addStretch()

        split_tab.setLayout(st)

        # 添加到标签页
        self.left_tabs.addTab(control_tab, "控制面板")
        self.left_tabs.addTab(chip_tab, "芯片测试")
        self.left_tabs.addTab(split_tab, "裂分操作")

        # ──────────────────────── 手动多选标签页 ────────────────────────
        multi_tab = QWidget()
        mt = QVBoxLayout(multi_tab)
        mt.setContentsMargins(10, 10, 10, 10)
        mt.setSpacing(10)

        # -- 模式切换 --
        mmg = QGroupBox("多选模式")
        mml = QVBoxLayout(mmg)
        mml.setContentsMargins(14, 18, 14, 14)
        mml.setSpacing(8)

        self.multi_mode_btn = QPushButton("进入多选模式")
        self.multi_mode_btn.setObjectName("btn_run")
        self.multi_mode_btn.setFixedHeight(34)
        self.multi_mode_btn.setCheckable(True)
        self.multi_mode_btn.clicked.connect(self._toggle_multi_mode)
        mml.addWidget(self.multi_mode_btn)

        self.multi_count_label = QLabel("已选电极: 0")
        self.multi_count_label.setStyleSheet("font-weight:700;font-size:16px;")
        mml.addWidget(self.multi_count_label)

        mmg.setLayout(mml)
        mt.addWidget(mmg)

        # -- 操作按钮 --
        mog = QGroupBox("批量操作")
        mol = QVBoxLayout(mog)
        mol.setContentsMargins(14, 18, 14, 14)
        mol.setSpacing(8)

        self.multi_select_all_btn = QPushButton("全选")
        self.multi_select_all_btn.setFixedHeight(34)
        self.multi_select_all_btn.clicked.connect(self._multi_select_all)
        mol.addWidget(self.multi_select_all_btn)

        self.multi_clear_btn = QPushButton("清除选择")
        self.multi_clear_btn.setFixedHeight(34)
        self.multi_clear_btn.clicked.connect(self._multi_clear)
        mol.addWidget(self.multi_clear_btn)

        mol.addSpacing(6)

        self.multi_batch_on_btn = QPushButton("⚡ 同时打开 (Batch ON)")
        self.multi_batch_on_btn.setObjectName("btn_primary")
        self.multi_batch_on_btn.setFixedHeight(38)
        self.multi_batch_on_btn.clicked.connect(self._multi_batch_on)
        mol.addWidget(self.multi_batch_on_btn)

        self.multi_all_off_btn = QPushButton("■ 全部关闭 (ALL OFF)")
        self.multi_all_off_btn.setObjectName("btn_stop")
        self.multi_all_off_btn.setFixedHeight(34)
        self.multi_all_off_btn.clicked.connect(self._multi_all_off)
        mol.addWidget(self.multi_all_off_btn)

        self.multi_log_label = QLabel("就绪")
        self.multi_log_label.setStyleSheet("font-size:13px;color:#888;")
        mol.addWidget(self.multi_log_label)

        mog.setLayout(mol)
        mt.addWidget(mog)
        mt.addStretch()

        multi_tab.setLayout(mt)

        # 添加到标签页
        self.left_tabs.addTab(control_tab, "控制面板")
        self.left_tabs.addTab(chip_tab, "芯片测试")
        self.left_tabs.addTab(split_tab, "裂分操作")
        self.left_tabs.addTab(multi_tab, "手动操作")
        left.addWidget(self.left_tabs, 1)

        # ────────── 中间: 电极网格 ──────────
        grid_wrapper = QWidget()
        gw = QVBoxLayout(grid_wrapper)
        gw.setContentsMargins(6, 10, 6, 10)
        grid_bg = QWidget()
        grid_bg.setStyleSheet("background:#ffffff;border:1px solid #b0b0b0;")
        gbg = QVBoxLayout(grid_bg)
        gbg.setContentsMargins(16, 16, 16, 16)
        gbg.addWidget(self.grid_widget, 1)
        gw.addWidget(grid_bg, 1)

        # ────────── 右面板 (280px) ──────────
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_panel.setMinimumWidth(220)
        right_panel.setMaximumWidth(280)
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(6, 10, 10, 10)
        right.setSpacing(10)

        # -- 路径信息 --
        pig = QGroupBox("路径信息")
        pil = QVBoxLayout(pig)
        pil.setContentsMargins(12, 12, 12, 12)
        pil.setSpacing(6)
        self.path_info_label = QLabel(
            "尚无路径规划\n\n"
            "请先在左侧面板配置液滴，\n"
            "然后点击「规划路径」"
        )
        self.path_info_label.setWordWrap(True)
        self.path_info_label.setStyleSheet("color:#606060;font-weight:500;font-size:15px;")
        pil.addWidget(self.path_info_label)
        pig.setLayout(pil)
        right.addWidget(pig)

        # -- 图例 --
        lg = QGroupBox("图例")
        ll = QVBoxLayout(lg)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)
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
            lbl.setStyleSheet("font-weight:600;")
            lr.addWidget(lbl)
            lr.addStretch()
            ll.addLayout(lr)

        # 路径颜色说明
        ll.addSpacing(6)
        path_legend_title = QLabel("路径颜色:")
        path_legend_title.setStyleSheet("color:#94a3b8;font-weight:600;")
        ll.addWidget(path_legend_title)
        path_colors = ["#3b78ff", "#ff5722", "#4caf50", "#9c27b0",
                       "#ffb320", "#00bcd4", "#e91e63", "#3f51b5"]
        pc_grid = QHBoxLayout()
        pc_grid.setSpacing(6)
        for i, c in enumerate(path_colors):
            sw = QWidget()
            sw.setFixedSize(20, 20)
            sw.setToolTip(f"液滴{i+1}")
            sw.setStyleSheet(f"background:{c};border-radius:4px;")
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
        parent_splitter.setSizes([440, 640, 300])

    def refresh_serial_ports(self):
        """刷新可用的串口列表，末尾始终添加虚拟串口选项。"""
        self.port_combo.clear()
        ports = SerialThread.scan_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("未发现串口")
        self.port_combo.addItem(VIRTUAL_PORT_NAME)

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
            self._disconnect_serial()

    def _disconnect_serial(self):
        """断开串口连接并恢复 UI 控件。"""
        self.serial_thread.close_port()
        self.serial_connected = False
        self.connect_btn.setChecked(False)
        self.connect_btn.setText("连接")
        self.port_combo.setEnabled(True)
        self.refresh_ports_btn.setEnabled(True)
        self.serial_status_label.setText("未连接")
        self.serial_status_label.setStyleSheet("color: #dc2626; font-weight: 700;")
        self.tb_status.setText("● 串口已断开")
        self.tb_status.setStyleSheet("color:#dc2626;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #dc2626;border-radius:12px;background:#fef2f2;")
        self.statusBar().showMessage("串口已断开连接")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.connect_btn.setText("断开")
            self.connect_btn.setChecked(True)
            port_text = self.port_combo.currentText()
            self.serial_status_label.setText(f"已连接 ({port_text})")
            self.serial_status_label.setStyleSheet("color: #16a34a; font-weight: 700;")
            is_virtual = (port_text == VIRTUAL_PORT_NAME)
            if is_virtual:
                self.tb_status.setText("● 虚拟模式")
                self.tb_status.setStyleSheet("color:#8b5cf6;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #8b5cf6;border-radius:12px;background:#f5f3ff;")
                self.statusBar().showMessage("虚拟串口已连接（模拟模式，无硬件）")
            else:
                self.tb_status.setText("● 串口已连接")
                self.tb_status.setStyleSheet("color:#059669;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #059669;border-radius:12px;background:#ecfdf5;")
                self.statusBar().showMessage(f"串口已连接：{port_text}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self._disconnect_serial()
            self.serial_status_label.setText("连接失败")
            self.serial_status_label.setStyleSheet("color: #ea580c; font-weight: 700;")

    @pyqtSlot(str)
    def on_serial_data(self, data):
        """处理串口接收数据。"""
        self.statusBar().showMessage(f"收到: {data}")
        # 追加到串口监视区，自动滚动到底部
        self.test_received_label.append(data)
        # 限制最多 50 行
        doc = self.test_received_label.document()
        if doc.blockCount() > 50:
            cursor = self.test_received_label.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor,
                                doc.blockCount() - 50)
            cursor.removeSelectedText()

    @pyqtSlot(str)
    def on_serial_error(self, error_msg):
        """处理串口错误 — 自动断开并恢复 UI。"""
        self.statusBar().showMessage(f"错误：{error_msg}")

        # 停止通道测试（如果正在运行）
        if self.test_running:
            self.test_timer.stop()
            self.test_running = False
            self.test_start_btn.setEnabled(True)
            self.test_stop_btn.setEnabled(False)

        # 停止路径执行（如果正在运行）
        if self.is_running:
            self.move_timer.stop()
            self.is_running = False
            self.run_path_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.grid_widget.setEnabled(True)
            self.current_path = []
            self.droplet_plans = []
            self.current_plan_index = 0

        # 断开串口连接
        self._disconnect_serial()
        self.serial_status_label.setText("串口异常")
        self.serial_status_label.setStyleSheet("color: #dc2626; font-weight: 700;")
        self.log_panel.log_error(f"串口错误: {error_msg}")

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

    def _compute_flexibility(self, droplets, all_used, all_starts, non_fusion_targets):
        """估算每个液滴的路径灵活度（分值越低越受限，应该优先规划）。

        Returns:
            list of (start, target, did, score)
            约束越强（邻居少、有途经点、距离短）则 score 越小。
        """
        scores = []
        for start, target, did in droplets:
            # 邻居数：起点和终点周围空闲格越少越受限
            free_neighbors = 0
            for (r, c) in [start, target]:
                for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nr, nc = r + dr, c + dc
                    if (nr, nc) not in all_used and (nr, nc) not in all_starts \
                       and (nr, nc) not in non_fusion_targets:
                        free_neighbors += 1
            # 曼哈顿距离（短路径选择少）
            dist = abs(start[0] - target[0]) + abs(start[1] - target[1])
            # 途经点 → 额外 -5（更受限）
            wps = self.grid_widget.get_waypoints(did)
            wps = [p for p in wps if p != start and p != target]
            wp_penalty = 5 if wps else 0
            # score 越低越优先
            score = free_neighbors * 10 + dist - wp_penalty
            scores.append((start, target, did, score))
        return scores

    def _plan_droplet_paths(self, droplet_pairs, obstacles):
        """核心规划引擎：智能排序 + 重试机制。

        Args:
            droplet_pairs: list of (start, target, droplet_id)
            obstacles: set of (r,c) 障碍物坐标

        Returns:
            results: list[dict] 规划结果
            fusion_targets: set 共享终点集合
            non_fusion_targets: set 独享终点集合
        """
        # 统计共享/独享终点
        target_counts = {}
        for _, tgt, _ in droplet_pairs:
            target_counts[tgt] = target_counts.get(tgt, 0) + 1
        fusion_targets = {t for t, c in target_counts.items() if c > 1}
        non_fusion_targets = {t for t, c in target_counts.items() if c == 1}
        all_starts = {p[0] for p in droplet_pairs}

        def _plan_one(start, target, did, all_used, blocked):
            """规划单个液滴路径（含途经点）。"""
            wps = self.grid_widget.get_waypoints(did)
            wps = [p for p in wps if p != start and p != target]

            full_path = []
            seg_start = start
            for wp in wps + [target]:
                seg_path = a_star_shortest_path(seg_start, wp, blocked)
                if not seg_path:
                    fail_reason = "无可达路径"
                    if start in obstacles:
                        fail_reason = "起点被障碍物阻挡"
                    elif target in obstacles:
                        fail_reason = "终点被障碍物阻挡"
                    elif start == target:
                        fail_reason = "起点等于终点"
                    return None, fail_reason
                if full_path:
                    full_path.extend(seg_path[1:])
                else:
                    full_path.extend(seg_path)
                seg_start = wp
                if wp != target:
                    all_used.add(wp)
                    # 途经点加入后更新 blocked
                    blocked = all_used | (all_starts - {start}) | (non_fusion_targets - {target})
            return full_path, None

        def _run_once(order):
            """按给定顺序执行一轮规划。返回 (results, failed_count)。"""
            used = set(obstacles)
            results = []
            fails = 0
            for start, target, did in order:
                blk = used | (all_starts - {start}) | (non_fusion_targets - {target})
                path, reason = _plan_one(start, target, did, used, blk)
                if path:
                    results.append({
                        'droplet_id': did,
                        'start': start,
                        'target': target,
                        'path': path,
                        'indices': path_to_indices(path),
                        'success': True,
                        'waypoints': self.grid_widget.get_waypoints(did),
                    })
                    if target not in fusion_targets:
                        for p in path[1:-1]:
                            used.add(p)
                else:
                    results.append({
                        'droplet_id': did,
                        'start': start,
                        'target': target,
                        'path': [],
                        'indices': [],
                        'success': False,
                        'fail_reason': reason or "无可达路径",
                    })
                    fails += 1
            return results, fails

        # ── 第 1 轮：按灵活度排序（约束最强的优先） ──
        scores = self._compute_flexibility(
            droplet_pairs, obstacles, all_starts, non_fusion_targets)
        # 按 score 升序（最受限的排最前）
        sorted_pairs = [p[0] for p in sorted(
            zip(droplet_pairs, scores), key=lambda x: x[1][3])]

        results, fails = _run_once(sorted_pairs)

        # ── 第 2 轮（如有失败）：先成功者保留占位，失败者重新排序后重试 ──
        if fails > 0:
            failed_indices = [i for i, r in enumerate(results) if not r['success']]
            # 取失败液滴，重新排序后重试
            failed_items = [(r['start'], r['target'], r['droplet_id']) for r in results if not r['success']]
            # 保留已成功液滴占用的格子
            used_only_success = set(obstacles)
            for r in results:
                if r['success']:
                    if r['target'] not in fusion_targets:
                        for p in r['path'][1:-1]:
                            used_only_success.add(p)
            # 为失败液滴再次排序（基于已成功液滴占用的空间）
            retry_scores = self._compute_flexibility(
                failed_items, used_only_success, all_starts, non_fusion_targets)
            retry_sorted = [p[0] for p in sorted(
                zip(failed_items, retry_scores), key=lambda x: x[1][3])]

            # 重新规划失败液滴，保留已有成功结果的空间
            retry_results = []
            all_fail = True
            for start, target, did in retry_sorted:
                blk = used_only_success | (all_starts - {start}) | (non_fusion_targets - {target})
                path, reason = _plan_one(start, target, did, used_only_success, blk)
                if path:
                    all_fail = False
                    retry_results.append({
                        'droplet_id': did,
                        'start': start,
                        'target': target,
                        'path': path,
                        'indices': path_to_indices(path),
                        'success': True,
                        'waypoints': self.grid_widget.get_waypoints(did),
                    })
                    if target not in fusion_targets:
                        for p in path[1:-1]:
                            used_only_success.add(p)
                else:
                    retry_results.append({
                        'droplet_id': did,
                        'start': start,
                        'target': target,
                        'path': [],
                        'indices': [],
                        'success': False,
                        'fail_reason': reason or "无可达路径",
                    })

            # 合并结果：成功保留原结果，失败替换为重试结果
            ri = 0
            for i in range(len(results)):
                if not results[i]['success']:
                    results[i] = retry_results[ri]
                    ri += 1

            # 第 3 轮（极少数极端情况）：检查是否有新堵塞，再试
            still_failed = [i for i, r in enumerate(results) if not r['success']]
            if still_failed and not all_fail:
                # 再做一轮简单重试
                used_final = set(obstacles)
                for r in results:
                    if r['success'] and r['target'] not in fusion_targets:
                        for p in r['path'][1:-1]:
                            used_final.add(p)
                for i in still_failed:
                    r = results[i]
                    blk = used_final | (all_starts - {r['start']}) | (non_fusion_targets - {r['target']})
                    path, reason = _plan_one(r['start'], r['target'], r['droplet_id'], used_final, blk)
                    if path:
                        results[i] = {
                            'droplet_id': r['droplet_id'],
                            'start': r['start'],
                            'target': r['target'],
                            'path': path,
                            'indices': path_to_indices(path),
                            'success': True,
                            'waypoints': self.grid_widget.get_waypoints(r['droplet_id']),
                        }

        return results, fusion_targets, non_fusion_targets

    def on_plan_path(self):
        """规划路径：预先试跑，只计算和显示路径，不操作串口。

        支持途经点（右键设置）：路径会依次经过所有途经点再到终点。
        采用智能排序算法最大化规划成功率。
        """
        obstacles = set(self.grid_widget.get_obstacle_points())
        droplet_pairs = self.grid_widget.get_droplet_pairs()

        if not droplet_pairs:
            QMessageBox.warning(self, "警告",
                                "未找到已配对的液滴！\n\n"
                                "请先为液滴分别设置起点和终点：\n"
                                "1. 在「液滴设置」中选择液滴编号\n"
                                "2. 点击网格设置起点（蓝色）和终点（橙色）")
            return

        # 使用智能规划引擎
        results, fusion_targets, _ = self._plan_droplet_paths(droplet_pairs, obstacles)

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        failed = [r for r in results if not r['success']]

        # 在网格上绘制所有路径
        self.grid_widget.set_paths(results)

        # 显示路径信息
        info_lines = [f"规划结果: {success_count}/{len(results)} 成功"]
        for r in results:
            if r['success']:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} ({len(r['path'])}步)")
            else:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} 无路径")
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
        self.tb_status.setStyleSheet("color:#059669;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #059669;border-radius:12px;background:#ecfdf5;")
        self.log_panel.log_info(f"规划完成: {success_count}/{len(results)} 条路径")

    def on_run_path(self):
        """手动配对液滴路径规划并依次执行。

        支持途经点（右键设置）：路径会依次经过所有途经点再到终点。
        采用智能排序算法最大化规划成功率。
        """
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

        # 使用智能规划引擎
        results, fusion_targets, _ = self._plan_droplet_paths(droplet_pairs, obstacles)

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        failed = [r for r in results if not r['success']]

        # 在网格上绘制所有路径（不同颜色）
        self.grid_widget.set_paths(results)

        # 显示路径信息
        exec_mode = "同步" if self.sync_mode else "逐个"
        auto_tag = "自动" if self.auto_mode else "单步"
        info_lines = [f"[{exec_mode}/{auto_tag}] 液滴规划: {success_count}/{len(results)} 成功"]
        for r in results:
            if r['success']:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} ({len(r['path'])}步)")
            else:
                info_lines.append(
                    f"  液滴{r['droplet_id']}: {r['start']}→{r['target']} 无路径")
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

        # 清除旧的高亮
        self.grid_widget.clear_execution_highlight()

        if self.sync_mode:
            self._start_sync_execution()
        else:
            self._start_next_droplet()

    # ============ 路径执行模式切换 ============

    def _set_exec_mode(self, sync_mode):
        """切换 逐个/同步 执行模式，互斥按钮状态。"""
        if sync_mode == self.sync_mode:
            return
        if self.is_running:
            QMessageBox.warning(self, "警告", "正在执行中，请先停止再切换模式")
            # 恢复按钮状态
            self.seq_btn.setChecked(not sync_mode)
            self.sync_btn.setChecked(sync_mode)
            return
        self.sync_mode = sync_mode
        self.seq_btn.setChecked(not sync_mode)
        self.sync_btn.setChecked(sync_mode)
        mode_name = "同步推进" if sync_mode else "逐个执行"
        self.log_panel.log_info(f"已切换为{mode_name}模式")

    @pyqtSlot()
    def _toggle_path_mode(self):
        """切换单步/自动执行模式，运行中也可无扰切换。"""
        self.auto_mode = self.mode_toggle_btn.isChecked()
        if self.auto_mode:
            self.mode_toggle_btn.setText("自动 ⏵")
            self.mode_toggle_btn.setStyleSheet(
                "QPushButton{background:#308050;color:#fff;font-weight:700;"
                "padding:4px 10px;border:1px solid #308050;font-size:13px;}")
            self.log_panel.log_info("已切换为自动执行模式")
            # 运行中无扰切换到自动：启动定时器
            if self.is_running:
                delay_ms = self.delay_spinbox.value()
                self.move_timer.start(delay_ms)
                if self.sync_mode:
                    self.tb_status.setText(f"● 同步推进中 ({len(self.sync_progress)}液滴 {delay_ms}ms/步)")
                else:
                    did = self.droplet_plans[self.current_plan_index]['droplet_id']
                    self.tb_status.setText(f"● 液滴{did} 自动运行中 ({delay_ms}ms/步)")
        else:
            self.mode_toggle_btn.setText("手动 ▶")
            self.mode_toggle_btn.setStyleSheet(
                "QPushButton{background:#3060b0;color:#fff;font-weight:700;"
                "padding:4px 10px;border:1px solid #3060b0;font-size:13px;}")
            self.log_panel.log_info("已切换为手动(单步)模式")
            # 运行中无扰切换到手动：停止定时器，等待用户点击单步
            if self.is_running:
                self.move_timer.stop()
                if self.sync_mode:
                    self.tb_status.setText(f"● 同步就绪 ({len(self.sync_progress)}液滴) — 点击单步")
                else:
                    did = self.droplet_plans[self.current_plan_index]['droplet_id']
                    self.tb_status.setText(f"● 液滴{did} 就绪 — 点击单步")

    @pyqtSlot()
    def on_step_path(self):
        """单步执行：手动点击执行下一步（根据模式派发）。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        if not self.is_running:
            return
        if self.sync_mode and not self.sync_progress:
            return
        if not self.sync_mode and not self.current_path:
            return
        # 如为自动模式，暂停定时器以执行单步
        if self.move_timer.isActive():
            self.move_timer.stop()
        if self.sync_mode:
            self._do_sync_step()
        else:
            self._do_single_step()

    def _do_single_step(self):
        """内部：执行单步路径电击切换，更新高亮。"""
        if not self.current_path or self.current_droplet_index >= len(self.current_path):
            # 当前液滴路径完成 → 找下一个成功的液滴
            self.grid_widget.clear_execution_highlight()
            self.current_plan_index += 1
            while self.current_plan_index < len(self.droplet_plans):
                plan = self.droplet_plans[self.current_plan_index]
                if plan['success']:
                    self.current_path = plan['path']
                    self.current_droplet_index = 0
                    self.log_panel.log_info(f"液滴{plan['droplet_id']} 路径开始")
                    self._do_single_step()
                    return
                else:
                    self.current_plan_index += 1
            self._finish_all()
            return

        droplet_id = self.droplet_plans[self.current_plan_index]['droplet_id']
        current_pos = self.current_path[self.current_droplet_index]
        current_index = ElectrodeGrid.coord_to_index(current_pos[0], current_pos[1])

        # 关闭前一步电极
        if self.current_droplet_index > 0:
            prev_pos = self.current_path[self.current_droplet_index - 1]
            prev_index = ElectrodeGrid.coord_to_index(prev_pos[0], prev_pos[1])
            self.serial_thread.send_cmd(f"OFF,{prev_index}")

        # 打开当前步电极
        self.serial_thread.send_cmd(f"ON,{current_index}")

        # 更新执行高亮
        self.grid_widget.set_execution_highlight(
            droplet_id, self.current_path, self.current_droplet_index
        )

        self.log_panel.log_info(
            f"单步: 液滴{droplet_id} 步骤 {self.current_droplet_index + 1}/{len(self.current_path)}: "
            f"({current_pos[0]}, {current_pos[1]}) 索引:{current_index}")

        self.current_droplet_index += 1

        # 更新路径信息显示
        info = self.path_info_label.text()
        if "单步" not in info:
            info = f"[单步模式]\n{info}"
        self.path_info_label.setText(info)

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
        self.test_received_label.append(f">>> 发送: {cmd},{relay}")

    @pyqtSlot(str)
    def on_test_quick(self, cmd):
        """发送快捷指令（ALLON, ALLOFF, TEST, LIST, HELP）。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        actual_cmd = cmd.replace(' ', '')
        self.serial_thread.send_cmd(actual_cmd)
        self.test_received_label.append(f">>> 发送: {actual_cmd}")

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
        self.test_received_label.append(f">>> 发送: {text}")
        self.test_custom_input.clear()

    # ============ 通道测试（可调间隔单步扫描） ============

    @pyqtSlot()
    def start_channel_test(self):
        """启动通道测试：从通道0开始逐个打开/关闭，间隔可调。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return

        self.test_running = True
        self.test_channel_index = 0
        self.test_start_btn.setEnabled(False)
        self.test_step_btn.setEnabled(False)
        self.test_stop_btn.setEnabled(True)

        # 先关闭所有通道
        self.serial_thread.send_alloff()
        self.grid_widget.clear_channel_test_highlight()

        delay = self.test_interval_spin.value()
        self.test_timer.start(delay)

        total = global_cfg.TOTAL_ELECTRODES
        self.log_panel.log_info(f"通道测试启动：0~{total-1}，间隔 {delay}ms")
        self.tb_status.setText(f"● 通道测试中 (0/{total})")
        self.tb_status.setStyleSheet("color:#b08020;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b08020;background:#fff8e8;")

    @pyqtSlot()
    def stop_channel_test(self):
        """停止通道测试，关闭所有通道。"""
        self.test_running = False
        self.test_timer.stop()
        self.test_start_btn.setEnabled(True)
        self.test_step_btn.setEnabled(True)
        self.test_step_btn.setText("单步")
        self.test_stop_btn.setEnabled(False)
        self.grid_widget.clear_channel_test_highlight()

        self.serial_thread.send_alloff()

        self.tb_status.setText("● 测试已停止")
        self.tb_status.setStyleSheet("color:#b03030;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b03030;background:#fef2f2;")
        self.log_panel.log_warn("通道测试已停止")

    @pyqtSlot()
    def step_channel_test(self):
        """单步通道测试：由用户手动点击执行下一步。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        if not self.test_running:
            # 启动单步模式
            self.test_running = True
            self.test_channel_index = 0
            self.test_start_btn.setEnabled(False)
            self.test_step_btn.setText("下一步")
            self.test_stop_btn.setEnabled(True)
            self.serial_thread.send_alloff()
            self.log_panel.log_info("单步通道测试启动")
        self._step_channel_once()

    def _step_channel_once(self):
        """执行一次通道步进（关闭上一个，打开当前）。"""
        total = global_cfg.TOTAL_ELECTRODES

        # 关闭上一个通道
        if self.test_channel_index > 0:
            prev = self.test_channel_index - 1
            self.serial_thread.send_cmd(f"OFF,{prev}")

        # 打开当前通道
        self.serial_thread.send_cmd(f"ON,{self.test_channel_index}")
        self.grid_widget.set_channel_test_highlight(self.test_channel_index)
        self.test_received_label.append(
            f">>> 单步测试: 通道 {self.test_channel_index} ON")
        self.log_panel.log_info(
            f"单步测试: 通道 {self.test_channel_index} ({self.test_channel_index+1}/{total}) ON")

        now = self.test_channel_index
        self.test_channel_index += 1

        self.tb_status.setText(f"● 单步: 通道 {now} / {total}")

        if self.test_channel_index >= total:
            # 所有通道测试完成
            self.serial_thread.send_cmd(f"OFF,{now}")
            self.grid_widget.clear_channel_test_highlight()
            self.test_running = False
            self.test_start_btn.setEnabled(True)
            self.test_step_btn.setText("单步")
            self.test_step_btn.setEnabled(True)
            self.test_stop_btn.setEnabled(False)
            self.tb_status.setText("● 通道测试完成")
            self.tb_status.setStyleSheet("color:#308050;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #308050;background:#ecfdf5;")
            self.log_panel.log_success(
                f"单步测试完成：已扫描 0~{total - 1} 共 {total} 个通道")
            self.test_received_label.append(
                f">>> 单步测试完成: 0~{total - 1}")

    @pyqtSlot()
    def test_channel_step(self):
        """通道测试定时器步进：关闭上一个通道，打开当前通道，步进到下一个。"""
        if not self.test_running:
            return

        total = global_cfg.TOTAL_ELECTRODES

        # 关闭上一个通道
        if self.test_channel_index > 0:
            prev = self.test_channel_index - 1
            self.serial_thread.send_cmd(f"OFF,{prev}")

        # 打开当前通道
        self.serial_thread.send_cmd(f"ON,{self.test_channel_index}")
        self.grid_widget.set_channel_test_highlight(self.test_channel_index)
        self.test_received_label.append(
            f">>> 通道测试: 通道 {self.test_channel_index} ON")

        # 步进到下一个通道
        self.test_channel_index += 1

        # 更新状态
        self.tb_status.setText(f"● 通道测试中 ({self.test_channel_index}/{total})")
        self.log_panel.log_info(
            f"通道测试: 通道 {self.test_channel_index - 1} ON")

        if self.test_channel_index >= total:
            # 所有通道测试完成，自动停止
            self.serial_thread.send_cmd(f"OFF,{total - 1}")
            self.grid_widget.clear_channel_test_highlight()
            self.test_timer.stop()
            self.test_running = False
            self.test_start_btn.setEnabled(True)
            self.test_step_btn.setEnabled(True)
            self.test_step_btn.setText("单步")
            self.test_stop_btn.setEnabled(False)
            self.tb_status.setText("● 通道测试完成")
            self.tb_status.setStyleSheet("color:#308050;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #308050;background:#ecfdf5;")
            self.log_panel.log_success(
                f"通道测试完成：已扫描 0~{total - 1} 共 {total} 个通道")
            self.test_received_label.append(
                f">>> 通道测试完成: 0~{total - 1}")

    def _start_next_droplet(self):
        """开始执行下一个液滴的路径。"""
        # 安全：如果定时器已在运行，先停止
        if self.move_timer.isActive():
            self.move_timer.stop()

        # 找到下一个成功的路径
        while self.current_plan_index < len(self.droplet_plans):
            plan = self.droplet_plans[self.current_plan_index]
            if plan['success']:
                self.current_path = plan['path']
                self.current_droplet_index = 0
                self.is_running = True

                self.run_path_btn.setEnabled(False)
                self.step_path_btn.setEnabled(True)
                self.stop_btn.setEnabled(True)
                self.grid_widget.setEnabled(False)

                droplet_id = plan['droplet_id']
                self.log_panel.log_info(
                    f"液滴{droplet_id} 路径执行中：{len(self.current_path)} 步")
                self.tb_status.setText(f"● 液滴{droplet_id} 运行中")
                self.tb_status.setStyleSheet("color:#b08020;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b08020;background:#fff8e8;")

                if self.auto_mode:
                    # 自动模式：启动定时器
                    delay_ms = self.delay_spinbox.value()
                    self.move_timer.start(delay_ms)
                    self.tb_status.setText(f"● 液滴{droplet_id} 自动运行中 ({delay_ms}ms/步)")
                else:
                    # 单步模式：等待用户点击「单步」
                    self.step_path_btn.setEnabled(True)
                    self.step_path_btn.setFocus()
                    self.tb_status.setText(f"● 液滴{droplet_id} 就绪 — 点击单步")
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
        self.sync_progress = []
        self.grid_widget.clear_execution_highlight()
        self.grid_widget.clear_sync_highlights()
        self.run_path_btn.setEnabled(True)
        self.step_path_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.tb_status.setText("● 全部完成")
        self.tb_status.setStyleSheet("color:#308050;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #308050;background:#ecfdf5;")
        self.log_panel.log_success("所有液滴路径执行完成")
        self._play_notification_sound()

    def _start_sync_execution(self):
        """同步模式：初始化所有液滴，全部置于起点。"""
        self.sync_progress = []
        for plan in self.droplet_plans:
            if plan['success']:
                self.sync_progress.append({
                    'droplet_id': plan['droplet_id'],
                    'path': plan['path'],
                    'step': 0,
                })

        if not self.sync_progress:
            self._finish_all()
            return

        self.is_running = True
        self.run_path_btn.setEnabled(False)
        self.step_path_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.grid_widget.setEnabled(False)

        num = len(self.sync_progress)
        # 打开所有液滴的起点电极
        highlights = []
        for d in self.sync_progress:
            r, c = d['path'][0]
            idx = ElectrodeGrid.coord_to_index(r, c)
            self.serial_thread.send_cmd(f"ON,{idx}")
            highlights.append((r, c, d['droplet_id']))
            self.log_panel.log_info(f"同步: 液滴{d['droplet_id']} 起点 ({r},{c}) 索引:{idx}")

        self.grid_widget.set_sync_highlights(highlights)

        self.log_panel.log_info(f"同步推进模式启动: {num} 个液滴")
        if self.auto_mode:
            delay_ms = self.delay_spinbox.value()
            self.move_timer.start(delay_ms)
            self.tb_status.setText(f"● 同步推进中 ({num}液滴 {delay_ms}ms/步)")
            self.tb_status.setStyleSheet("color:#b08020;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b08020;background:#fff8e8;")
        else:
            self.step_path_btn.setFocus()
            self.tb_status.setText(f"● 同步就绪 ({num}液滴) — 点击单步")
            self.tb_status.setStyleSheet("color:#b08020;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b08020;background:#fff8e8;")

    def _do_sync_step(self):
        """同步模式：所有液滴同时向前推进 1 步。已到终点的液滴保持原位。"""
        if not self.is_running or not self.sync_progress:
            self.move_timer.stop()
            return

        highlights = []
        active_count = 0

        for droplet in self.sync_progress:
            path = droplet['path']
            step = droplet['step']

            if step >= len(path):
                # 已到达终点，保持高亮和电极状态
                r, c = path[-1]
                highlights.append((r, c, droplet['droplet_id']))
                continue

            active_count += 1

            # 关闭前一步电极
            if step > 0:
                pr, pc = path[step - 1]
                pidx = ElectrodeGrid.coord_to_index(pr, pc)
                self.serial_thread.send_cmd(f"OFF,{pidx}")

            # 打开当前步电极
            cr, cc = path[step]
            cidx = ElectrodeGrid.coord_to_index(cr, cc)
            self.serial_thread.send_cmd(f"ON,{cidx}")

            highlights.append((cr, cc, droplet['droplet_id']))

            step_display = step + 1
            self.log_panel.log_info(
                f"同步步进: 液滴{droplet['droplet_id']} "
                f"{step_display}/{len(path)}: ({cr},{cc}) 索引:{cidx}")

            droplet['step'] += 1

        self.grid_widget.set_sync_highlights(highlights)

        if active_count == 0:
            # 所有液滴均已完成
            self._finish_all()

    def on_stop(self):
        """停止液滴移动。"""
        self.is_running = False
        self.move_timer.stop()
        # 断开所有继电器
        self.serial_thread.send_alloff()
        # 清除路径执行状态
        self.current_path = []
        self.droplet_plans = []
        self.current_plan_index = 0
        self.sync_progress = []
        self.grid_widget.clear_execution_highlight()
        self.grid_widget.clear_sync_highlights()
        self.run_path_btn.setEnabled(True)
        self.step_path_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.tb_status.setText("● 已停止")
        self.log_panel.log_warn("路径执行已停止，所有继电器已断开")
        self.tb_status.setStyleSheet("color:#b03030;font-size:14px;font-weight:700;padding:4px 14px;border:1px solid #b03030;background:#fef2f2;")

    def move_droplet_step(self):
        """定时器回调：根据当前模式执行一步。"""
        if self.sync_mode:
            self._do_sync_step()
            return
        if not self.is_running or not self.current_path:
            self.move_timer.stop()
            return

        if self.current_droplet_index >= len(self.current_path):
            # 当前液滴路径完成，保持最后一个电极开启（到达目标）
            # 切换到下一个液滴
            self.current_plan_index += 1
            if self.current_plan_index < len(self.droplet_plans):
                self.log_panel.log_info(
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
        self.log_panel.log_info(
            f"液滴{droplet_id} 步骤 {self.current_droplet_index + 1}/{len(self.current_path)}: "
            f"({current_pos[0]}, {current_pos[1]}) 索引:{current_index}")

        # 更新执行高亮
        self.grid_widget.set_execution_highlight(
            droplet_id, self.current_path, self.current_droplet_index
        )

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
        self.log_panel.log_info(f"已切换到液滴 {val}")

    def on_prev_droplet(self):
        """切换到上一个液滴编号。"""
        val = int(self.droplet_label.text()) - 1
        if val < 1:
            val = 8
        self.droplet_label.setText(str(val))
        self.grid_widget.set_droplet_id(val)
        self.update_droplet_info()
        self.log_panel.log_info(f"已切换到液滴 {val}")

    def on_first_droplet(self):
        """回到液滴1。"""
        self.droplet_label.setText("1")
        self.grid_widget.set_droplet_id(1)
        self.update_droplet_info()
        self.log_panel.log_info("已回到液滴 1")

    def on_clear_droplet(self):
        """清除当前液滴的起点和终点，保留其他液滴和障碍物。"""
        did = int(self.droplet_label.text())
        self.grid_widget.clear_droplet(did)
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.log_panel.log_info(f"已清除液滴 {did} 的起点/终点")

    def on_clear_all_droplets(self):
        """清除所有液滴的起点/终点，保留障碍物和空闲格。"""
        reply = QMessageBox.question(
            self, "清除全部液滴",
            "确定要清除所有液滴的起点和终点吗？\n\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.grid_widget.clear_all_droplets()
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.log_panel.log_info("已清除所有液滴的起点/终点")

    def on_mode_changed(self, mode):
        """交互模式变化时更新按钮状态。"""
        if mode == "sd":
            self.mode_sd_btn.setChecked(True)
            self.mode_obstacle_btn.setChecked(False)
        elif mode == "obstacle":
            self.mode_sd_btn.setChecked(False)
            self.mode_obstacle_btn.setChecked(True)
        mode_name = '起点/终点' if mode == 'sd' else '障碍物'
        self.log_panel.log_info(f"已切换到{mode_name}模式")

    def on_reset_grid(self):
        """重置网格所有单元格为 Idle，同时清除路径显示，并回到液滴1。"""
        self.grid_widget.reset_grid()  # 内部已清除 paths 和 droplet 配对
        self.droplet_plans = []
        self.current_plan_index = 0
        self.current_path = []
        self.droplet_label.setText("1")
        self.grid_widget.set_droplet_id(1)
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.log_panel.log_info("网格已重置，当前液滴 1")

    def _clear_waypoints(self):
        """清除当前液滴的所有途经点。"""
        did = int(self.droplet_label.text())
        self.grid_widget.clear_waypoints(did)
        self.log_panel.log_info(f"已清除液滴 {did} 途经点")

    def on_clear_state(self, state):
        """清除指定状态的所有单元格，同时清除路径显示。"""
        state_name = ElectrodeGrid.STATE_NAMES[state]
        reply = QMessageBox.question(
            self, f"清除{state_name}",
            f"确定要清除所有 {state_name} 单元格吗？\n\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.grid_widget.clear_state(state)
        self.droplet_plans = []
        self.path_info_label.setText("路径：无")
        self.update_droplet_info()
        self.log_panel.log_info(f"已清除所有 {state_name} 单元格")

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

    def _project_save_as(self):
        """另存为工程。"""
        self.project_manager.save_project_as()

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

    # ── 芯片测试（自由选点模式）────────────────

    @pyqtSlot()
    def on_chip_test_start(self):
        """启动芯片测试：点击网格选择电极，标记通过/坏点。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return

        # 如果路径执行正在进行，先停止
        if self.is_running or self.move_timer.isActive():
            self.log_panel.log_info("路径执行已停止（芯片测试启动）")
            self.on_stop()
            QApplication.processEvents()

        # 清除路径规划的起点/终点标记
        gw = self.grid_widget
        for did, (r, c) in list(gw.droplet_starts.items()):
            gw.grid[r][c] = ElectrodeGrid.STATE_IDLE
        gw.droplet_starts.clear()
        for did, (r, c) in list(gw.droplet_targets.items()):
            gw.grid[r][c] = ElectrodeGrid.STATE_IDLE
        gw.droplet_targets.clear()
        gw.droplet_config_changed.emit()

        # 清除上一次芯片测试留下的坏点障碍物
        for r, c in list(self.chip_bad_cells):
            if gw.grid[r][c] == ElectrodeGrid.STATE_OBSTACLE:
                gw.grid[r][c] = ElectrodeGrid.STATE_IDLE
        self.chip_bad_cells.clear()

        # 初始化测试状态
        self.chip_test_running = True
        self.chip_test_current = -1

        self.grid_widget.set_chip_test_mode(True)
        self.grid_widget.clear_test_results()
        self.grid_widget.set_paths([])  # 清除路径显示

        # UI 状态
        self.chip_start_btn.setEnabled(False)
        self.chip_start_btn.setText("测试中...")
        self.chip_stop_btn.setEnabled(True)
        self.chip_pass_btn.setEnabled(False)
        self.chip_fail_btn.setEnabled(False)
        self.chip_export_btn.setEnabled(False)

        total = global_cfg.TOTAL_ELECTRODES
        self.chip_status_label.setText("● 测试中 — 点击网格选择电极")
        self.chip_progress_label.setText("电极: —  点击网格选择")
        self.chip_progress_bar.setMaximum(total)
        self.chip_progress_bar.setValue(0)
        self.chip_result_label.setText(f"通过: 0  坏点: 0  未测: {total}")
        self.chip_tested_label.setText(f"已测: 0 / {total}")

        self.serial_thread.send_alloff()
        self.log_panel.log_info("芯片测试启动: 点击网格上的电极进行测试")

    @pyqtSlot(int, int)
    def on_chip_test_cell_selected(self, row, col):
        """用户在芯片测试模式下点击了网格上的电极。

        Args:
            row: 点击的网格行
            col: 点击的网格列
        """
        if not self.chip_test_running:
            return
        cols = self.grid_widget.cols
        idx = row * cols + col

        # 芯片测试模式下障碍物也可重新选择（允许修改坏点/好点状态）
        # 切换：OFF 旧电极 → ON 新电极
        if self.chip_test_current >= 0 and self.chip_test_current != idx:
            self.serial_thread.send_cmd(f"OFF,{self.chip_test_current}")
        self.serial_thread.send_cmd(f"ON,{idx}")

        self.chip_test_current = idx
        self.grid_widget.set_chip_test_current(idx)

        # 启用通过/坏点按钮
        self.chip_pass_btn.setEnabled(True)
        self.chip_fail_btn.setEnabled(True)

        # 显示上次测试结果（如有）
        old_result = self.grid_widget.cell_test_results.get(idx)
        if old_result == 'pass':
            self.chip_status_label.setText("● 上次标记: 通过 (可重新标记)")
        elif old_result == 'fail':
            self.chip_status_label.setText("● 上次标记: 坏点 (可重新标记)")
        else:
            self.chip_status_label.setText("● 测试中")
        self.chip_progress_label.setText(f"当前电极: 通道 {idx} (行{row} 列{col})")
        self.log_panel.log_info(f"选择电极: 通道 {idx} (行{row} 列{col})")

    @pyqtSlot()
    def on_chip_mark(self, result):
        """标记当前电极的测试结果（可随时修改）。

        Args:
            result: 'pass' 通过 | 'fail' 坏点
        """
        idx = self.chip_test_current
        if idx < 0:
            return

        prev_result = self.grid_widget.cell_test_results.get(idx)
        row = idx // self.grid_widget.cols
        col = idx % self.grid_widget.cols

        if result == 'fail':
            self.chip_bad_cells.add((row, col))
            # 坏点标注为障碍物
            self.grid_widget.grid[row][col] = ElectrodeGrid.STATE_OBSTACLE
            self.grid_widget.cell_changed.emit(row, col, ElectrodeGrid.STATE_OBSTACLE)
            self.serial_thread.send_cmd(f"OFF,{idx}")
            self.log_panel.log_warn(f"坏点标记: 通道 {idx} (行{row} 列{col})")
        else:  # pass
            # 如果是之前标记的坏点，清除障碍物状态
            if prev_result == 'fail' and (row, col) in self.chip_bad_cells:
                self.chip_bad_cells.discard((row, col))
                if self.grid_widget.grid[row][col] == ElectrodeGrid.STATE_OBSTACLE:
                    self.grid_widget.grid[row][col] = ElectrodeGrid.STATE_IDLE
                    self.grid_widget.cell_changed.emit(row, col, ElectrodeGrid.STATE_IDLE)
                self.log_panel.log_info(f"已清除坏点: 通道 {idx} → 改为通过")
            # 保持 ON，用户可继续观察
            self.log_panel.log_info(f"通过标记: 通道 {idx}")

        self.grid_widget.set_cell_test_result(idx, result)
        self.grid_widget.update()

        # 按钮保持启用，允许用户继续修改
        self.chip_pass_btn.setEnabled(True)
        self.chip_fail_btn.setEnabled(True)

        self._chip_update_summary()

    def _chip_update_summary(self):
        """更新测试结果统计显示。"""
        total = global_cfg.TOTAL_ELECTRODES
        pass_c, fail_c, fail_list = self.grid_widget.get_test_summary()
        untested = total - pass_c - fail_c
        self.chip_result_label.setText(
            f"通过: {pass_c}  坏点: {fail_c}  未测: {untested}")
        self.chip_tested_label.setText(f"已测: {pass_c + fail_c} / {total}")
        self.chip_progress_bar.setValue(pass_c + fail_c)
        if fail_list:
            self.chip_fail_list_label.setText(
                "坏点列表: " + ", ".join(f"通道{i}" for i in fail_list))
        else:
            self.chip_fail_list_label.setText("坏点列表: (无)")

    @pyqtSlot()
    def on_chip_test_stop(self):
        """停止芯片测试。"""
        self._chip_test_cleanup()
        self.log_panel.log_warn("芯片测试已停止")

    def _chip_finish(self):
        """芯片测试完成。"""
        if self.chip_test_current >= 0:
            self.serial_thread.send_cmd(f"OFF,{self.chip_test_current}")
        self.serial_thread.send_alloff()
        self._chip_update_summary()
        self._chip_test_cleanup()

        pass_c, fail_c, fail_list = self.grid_widget.get_test_summary()
        total = global_cfg.TOTAL_ELECTRODES
        self.chip_status_label.setText("● 测试完成")
        self.chip_export_btn.setEnabled(True)
        msg = f"芯片测试完成: {total} 电极, 通过 {pass_c}, 坏点 {fail_c}"
        self.log_panel.log_success(msg)

        self._play_notification_sound()

        if fail_c > 0:
            QMessageBox.warning(self, "芯片测试完成",
                f"测试完成！\n\n通过: {pass_c}\n坏点: {fail_c}\n"
                f"坏点通道: {', '.join(f'通道{i}' for i in fail_list)}")
        else:
            QMessageBox.information(self, "芯片测试完成",
                f"测试完成！\n\n通过: {pass_c}\n坏点: {fail_c}")

    def _chip_test_cleanup(self):
        """清理芯片测试 UI 状态（总是完全退出测试模式）。"""
        if self.chip_test_current >= 0:
            self.serial_thread.send_cmd(f"OFF,{self.chip_test_current}")
            self.chip_test_current = -1
        self.serial_thread.send_alloff()

        self.chip_test_running = False
        self.chip_start_btn.setEnabled(True)
        self.chip_start_btn.setText("开始测试")
        self.chip_stop_btn.setEnabled(False)
        self.chip_pass_btn.setEnabled(False)
        self.chip_fail_btn.setEnabled(False)

        # 始终退出芯片测试模式 + 清除路径显示，但保留测试结果以便导出
        self.grid_widget.set_chip_test_mode(False)
        self.grid_widget.set_paths([])
        self.chip_progress_label.setText("电极: —")
        self.chip_progress_bar.setValue(0)
        self.chip_status_label.setText("芯片测试就绪")

    @pyqtSlot()
    def on_chip_export(self):
        """导出芯片测试结果到文件。"""
        pass_c, fail_c, fail_list = self.grid_widget.get_test_summary()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出测试结果", "chip_test_result.txt",
            "文本文件 (*.txt);;CSV (*.csv)")
        if not filepath:
            return
        total = global_cfg.TOTAL_ELECTRODES
        lines = [
            "DMF 芯片测试结果",
            f"测试时间: {QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')}",
            f"总电极数: {total}",
            f"通过: {pass_c}",
            f"坏点: {fail_c}",
            "",
            "坏点列表:",
        ]
        if fail_list:
            for i in fail_list:
                row = i // self.grid_widget.cols
                col = i % self.grid_widget.cols
                lines.append(f"  通道 {i} (行{row} 列{col})")
        else:
            lines.append("  (无)")
        lines.append("")
        lines.append("详细结果:")
        for i in range(total):
            status = self.grid_widget.cell_test_results.get(i, "未测")
            row = i // self.grid_widget.cols
            col = i % self.grid_widget.cols
            lines.append(f"  {i:2d} (行{row} 列{col}): {status}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        self.log_panel.log_success(f"测试结果已导出: {filepath}")

    # ── 录制钩子 ──────────────────────────────────

    def _hooked_send_cmd(self, cmd):
        """录制钩子：发送指令时记录到录制列表。"""
        if self.recording:
            self.recorded_steps.append((cmd, datetime.now().strftime("%H:%M:%S")))
        self._original_send(cmd)

    # ── 撤销/重做 ──────────────────────────────────

    def _on_undo_state_changed(self, can_undo, can_redo):
        """撤销/重做按钮状态更新。"""
        if self._undo_action:
            self._undo_action.setEnabled(can_undo)
        if self._redo_action:
            self._redo_action.setEnabled(can_redo)

    def _on_undo(self):
        """执行撤销。"""
        if self.grid_widget.undo():
            self.log_panel.log_info("撤销: 恢复上一步网格状态")
            self.update_droplet_info()
            self._clear_path_state()

    def _on_redo(self):
        """执行重做。"""
        if self.grid_widget.redo():
            self.log_panel.log_info("重做: 恢复下一步网格状态")
            self.update_droplet_info()
            self._clear_path_state()

    def _clear_path_state(self):
        """撤销/重做后清除路径状态。"""
        self.droplet_plans = []
        self.current_plan_index = 0
        self.current_path = []
        if not self.is_running:
            self.path_info_label.setText("路径：无")

    # ── 网格截图导出 ──────────────────────────────

    def _export_grid_screenshot(self):
        """导出网格区域为 PNG 图片。"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出网格截图", "grid_screenshot.png",
            "PNG 图片 (*.png)")
        if not filepath:
            return
        pixmap = self.grid_widget.grab()
        pixmap.save(filepath, "PNG")
        self.log_panel.log_success(f"网格截图已保存: {filepath}")

    def _copy_grid_screenshot(self):
        """复制网格截图到剪贴板。"""
        pixmap = self.grid_widget.grab()
        QApplication.clipboard().setPixmap(pixmap)
        self.log_panel.log_info("网格截图已复制到剪贴板")

    # ── 操作录制/回放 ────────────────────────────

    def _toggle_recording(self):
        """开始/停止录制操作步骤。"""
        if not self.recording:
            # 开始录制
            self.recording = True
            self.recorded_steps = []
            self.record_menu.setTitle("录制 ●")
            self.act_record.setText("停止录制")
            self.log_panel.log_info("操作录制已开始")
        else:
            # 停止录制
            self.recording = False
            self.record_menu.setTitle("录制")
            self.act_record.setText("开始录制操作...")
            self.act_replay.setEnabled(bool(self.recorded_steps))
            self.act_export_record.setEnabled(bool(self.recorded_steps))
            self.log_panel.log_info(f"录制完成: {len(self.recorded_steps)} 步操作")

    def _replay_recording(self):
        """回放录制的操作步骤。"""
        if not self.recorded_steps:
            QMessageBox.warning(self, "回放", "没有录制内容")
            return
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        reply = QMessageBox.question(
            self, "回放录制",
            f"即将回放 {len(self.recorded_steps)} 步操作，"
            f"将按原始顺序发送所有指令。\n\n"
            f"继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.log_panel.log_info(f"开始回放: {len(self.recorded_steps)} 步")
        for cmd, ts in self.recorded_steps:
            self.serial_thread.send_cmd(cmd)
            self.log_panel.log_info(f"回放: {cmd}")
        self.log_panel.log_success("回放完成")

    def _export_recording(self):
        """导出录制内容到文件。"""
        if not self.recorded_steps:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出录制", "recorded_steps.txt",
            "文本文件 (*.txt)")
        if not filepath:
            return
        lines = [f"DMF 操作录制 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                  f"总步数: {len(self.recorded_steps)}", ""]
        for cmd, ts in self.recorded_steps:
            lines.append(f"{ts}  {cmd}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        self.log_panel.log_success(f"录制已导出: {filepath}")

    # ── 液滴裂分 ──────────────────────────────────

    @pyqtSlot()
    def _toggle_split_mode(self):
        """切换裂分模式。"""
        if self.split_enter_btn.isChecked():
            self.grid_widget.mode = ElectrodeGrid.MODE_SPLIT
            self.split_status_label.setText("点击网格上的电极选择裂分中心")
            self.split_status_label.setStyleSheet("font-weight:700;font-size:14px;color:#d08020;")
            self.split_center_label.setText("中心电极: 等待选择...")
            self.split_enter_btn.setText("退出裂分模式")
            if self.grid_widget.split_center:
                self.split_clear_btn.setEnabled(True)
            self.log_panel.log_info("已进入液滴裂分模式 — 点击网格电极选择裂分中心")
        else:
            self.grid_widget.mode = ElectrodeGrid.MODE_SD
            self.grid_widget.clear_split_center()
            self.split_status_label.setText("点击「进入裂分模式」后在网格上选择电极")
            self.split_status_label.setStyleSheet("font-weight:600;font-size:14px;color:#606060;")
            self.split_center_label.setText("中心电极: 未选择")
            self.split_enter_btn.setText("进入裂分模式")
            self.split_clear_btn.setEnabled(False)
            self.split_exec_btn.setEnabled(False)
            self.log_panel.log_info("已退出液滴裂分模式")

    @pyqtSlot()
    def _clear_split_selection(self):
        """清除裂分中心选择。"""
        self.grid_widget.clear_split_center()
        self.split_center_label.setText("中心电极: 未选择")
        self.split_clear_btn.setEnabled(False)
        self.split_exec_btn.setEnabled(False)
        self.split_result_label.setText("就绪")

    @pyqtSlot(int, int)
    def _on_split_center_selected(self, row, col):
        """处理网格上裂分中心的选择。"""
        if not self.split_enter_btn.isChecked():
            return
        idx = ElectrodeGrid.coord_to_index(row, col)
        self.split_center_label.setText(f"中心电极: 通道 {idx}  (行{row} 列{col})")
        self.split_center_label.setStyleSheet("font-weight:700;font-size:17px;color:#d08020;")
        self.split_clear_btn.setEnabled(True)
        self.split_exec_btn.setEnabled(True)
        self.split_result_label.setText("已选择 — 点击「执行裂分」开始")
        self.split_result_label.setStyleSheet("font-weight:600;font-size:14px;color:#3060b0;")
        self.log_panel.log_info(f"裂分中心已选择: 通道 {idx} (行{row} 列{col})")
        self._update_split_preview()

    def _on_split_param_changed(self):
        """裂分参数变更时更新预览。"""
        self._update_split_preview()

    def _update_split_preview(self):
        """更新网格上的裂分预览。"""
        dir_text = self.split_dir_combo.currentText()
        direction = {"水平 ←→": "horizontal", "垂直 ↕": "vertical", "四向 ✦": "cross"}.get(dir_text, "horizontal")

        self.grid_widget.set_split_preview(direction, 2)

        # 更新提示信息
        on_list, off_list = self.grid_widget.get_split_electrodes()
        if on_list or off_list:
            self.split_preview_label.setText(
                f"ON: {len(on_list)} 个  |  OFF: {len(off_list)} 个  |  网格已预览"
            )

    @pyqtSlot()
    def _execute_split(self):
        """执行液滴裂分 — 分两阶段：
        1) 先 send_joint 打开相邻电极 + 关闭中心
        2) 然后用 split_timer 由近到远逐级拉开外围电极
        """
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        if self.split_timer.isActive():
            return

        center = self.grid_widget.split_center
        if center is None:
            QMessageBox.warning(self, "提示", "请先选择裂分中心电极")
            return

        dir_text = self.split_dir_combo.currentText()
        direction = {"水平 ←→": "horizontal", "垂直 ↕": "vertical", "四向 ✦": "cross"}.get(dir_text, "horizontal")

        # 设置预览参数并计算电极
        self.grid_widget.set_split_preview(direction, 2)
        on_channels, off_channels = self.grid_widget.get_split_electrodes()

        if not on_channels:
            QMessageBox.warning(self, "提示", "裂分参数无效，请检查中心电极位置是否在边界")
            return

        r, c = center
        center_idx = ElectrodeGrid.coord_to_index(r, c)

        # ---- 阶段 1: 同时打开相邻电极 + 关闭中心 ----
        self.serial_thread.send_joint(on_channels=on_channels, off_channels=off_channels)

        on_str = ", ".join(str(ch) for ch in on_channels)
        off_str = ", ".join(str(ch) for ch in off_channels)
        self.log_panel.log_info(f"裂分 阶段1 — 中心关闭 + 相邻 ON: [{on_str}] OFF=[{off_str}]")
        self.split_result_label.setText("阶段1: 打开相邻电极...")
        self.split_result_label.setStyleSheet("font-weight:600;font-size:14px;color:#3060b0;")
        self.split_exec_btn.setEnabled(False)

        # ---- 阶段 2: 由近到远逐级拉开 ----
        sequence = self.grid_widget.get_split_sequence()
        if not sequence:
            # 没有外层可拉 — 直接完成
            self._finish_split(on_channels, off_channels, center, center_idx)
            return

        delay = self.split_delay_spin.value()
        self._split_pull_queue = sequence
        self._split_pull_layer = 0
        self._split_on_channels = on_channels
        self._split_off_channels = off_channels
        self._split_center = center
        self._split_center_idx = center_idx

        self.log_panel.log_info(f"裂分 阶段2 — 逐级拉开 {len(sequence)} 层, 延时={delay}ms")
        self.split_result_label.setText(f"阶段2: 逐级拉开中 (0/{len(sequence)} 层)...")
        self.split_timer.start(delay)

    def _split_pull_step(self):
        """QTimer 回调：发送下一层的拉开指令。"""
        if self._split_pull_layer >= len(self._split_pull_queue):
            # 所有层完成
            self.split_timer.stop()
            self._finish_split(
                self._split_on_channels,
                self._split_off_channels,
                self._split_center,
                self._split_center_idx
            )
            self.split_result_label.setText(f"阶段2: 逐级拉开完成 ✓")
            return

        layer_channels = self._split_pull_queue[self._split_pull_layer]
        self._split_pull_layer += 1

        # 只 ON 这一层的电极（不需要 OFF）
        self.serial_thread.send_joint(on_channels=layer_channels, off_channels=[])
        self.log_panel.log_info(f"裂分 拉开层 {self._split_pull_layer}/{len(self._split_pull_queue)}: ON {layer_channels}")
        self.split_result_label.setText(
            f"阶段2: 逐级拉开中 ({self._split_pull_layer}/{len(self._split_pull_queue)} 层)..."
        )

    def _finish_split(self, on_channels, off_channels, center, center_idx):
        """裂分完成：更新网格状态 + 退出裂分模式。"""
        r, c = center

        # 将裂分目标位置设为新液滴起点
        new_droplet_id = max([0] + list(self.grid_widget.droplet_starts.keys()) +
                             list(self.grid_widget.droplet_targets.keys())) + 1

        for ch in on_channels:
            if ch == center_idx:
                continue
            nr = ch // self.grid_widget.cols
            nc = ch % self.grid_widget.cols
            self.grid_widget.droplet_starts[new_droplet_id] = (nr, nc)
            self.grid_widget.grid[nr][nc] = ElectrodeGrid.STATE_START
            new_droplet_id += 1

        if center_idx not in on_channels:
            self.grid_widget.grid[r][c] = ElectrodeGrid.STATE_IDLE

        self.grid_widget.droplet_config_changed.emit()
        self.grid_widget.update()

        result_msg = f"✅ 裂分完成: {len(on_channels)} 个 ON, {len(off_channels)} 个 OFF"
        self.split_result_label.setText(result_msg)
        self.split_result_label.setStyleSheet("font-weight:700;font-size:14px;color:#059669;")
        self.log_panel.log_success(f"液滴裂分执行成功")

        self.split_exec_btn.setEnabled(True)
        self.split_enter_btn.setChecked(False)
        self._toggle_split_mode()

    # ── 手动多选 ──────────────────────────────────

    @pyqtSlot()
    def _on_multi_selection_changed(self):
        """多选选择变化时更新计数。"""
        n = len(self.grid_widget.multi_selected)
        self.multi_count_label.setText(f"已选电极: {n}")

    @pyqtSlot()
    def _toggle_multi_mode(self):
        """切换多选模式。"""
        if self.multi_mode_btn.isChecked():
            self.grid_widget.mode = ElectrodeGrid.MODE_MULTI
            self.multi_mode_btn.setText("退出多选模式")
            self.multi_log_label.setText("点击网格上的电极进行多选")
            self.log_panel.log_info("已进入手动多选模式 — 点击电极选择/取消")
        else:
            self.grid_widget.mode = ElectrodeGrid.MODE_SD
            self.grid_widget.multi_selected.clear()
            self.grid_widget.update()
            self.multi_mode_btn.setText("进入多选模式")
            self.multi_count_label.setText("已选电极: 0")
            self.multi_log_label.setText("就绪")
            self.log_panel.log_info("已退出手动多选模式")

    @pyqtSlot()
    def _multi_select_all(self):
        """全选所有电极。"""
        if not self.multi_mode_btn.isChecked():
            QMessageBox.warning(self, "提示", "请先进入多选模式")
            return
        self.grid_widget.set_multi_select_all()
        n = len(self.grid_widget.multi_selected)
        self.multi_count_label.setText(f"已选电极: {n}")
        self.multi_log_label.setText(f"全选: {n} 个电极")

    @pyqtSlot()
    def _multi_clear(self):
        """清除多选。"""
        self.grid_widget.clear_multi_select()
        self.multi_count_label.setText("已选电极: 0")
        self.multi_log_label.setText("已清除选择")

    @pyqtSlot()
    def _multi_batch_on(self):
        """同时打开选中的电极 (Batch ON)。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        indices = self.grid_widget.get_multi_selected_indices()
        if not indices:
            QMessageBox.warning(self, "提示", "请先选择至少一个电极")
            return
        on_str = ", ".join(str(i) for i in indices)
        self.log_panel.log_info(f"批量 ON: [{on_str}]")
        # 依次发送 ON 指令
        for idx in indices:
            self.serial_thread.send_cmd(f"ON,{idx}")
        self.multi_log_label.setText(f"已打开 {len(indices)} 个电极")
        self.log_panel.log_success(f"批量 ON: {len(indices)} 个电极已打开")

    @pyqtSlot()
    def _multi_all_off(self):
        """全部关闭。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return
        self.serial_thread.send_cmd("ALLOFF")
        self.multi_log_label.setText("已发送 ALL OFF")
        self.log_panel.log_info("手动操作: 全部关闭 (ALLOFF)")

    # ── 通知音效 ──────────────────────────────────

    def _play_notification_sound(self):
        """播放完成通知音效（assets/notification.mp3）。"""
        if not self.sound_enabled:
            return
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl

            player = QMediaPlayer()
            url = QUrl.fromLocalFile(_resource_path("assets/notification.mp3"))
            player.setMedia(QMediaContent(url))
            # 播放完毕自动清理
            player.mediaStatusChanged.connect(
                lambda status, p=player: p.deleteLater()
                if status == QMediaPlayer.EndOfMedia else None
            )
            player.play()
        except Exception:
            QApplication.beep()

    # ── 窗口关闭事件 ──────────────────────────

    def closeEvent(self, event):
        """窗口关闭事件。"""
        if self.serial_connected:
            self.serial_thread.close_port()
        if self.move_timer.isActive():
            self.move_timer.stop()
        if self.test_timer.isActive():
            self.test_timer.stop()
        event.accept()


def main():
    """主函数：显示欢迎界面 → 加载资源 → 启动主窗口。"""
    app = QApplication(sys.argv)

    # 基础点阵字体——Qt自动适配屏幕DPI
    app.setStyle('Fusion')
    app.setFont(QFont("Microsoft YaHei", 10))

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
