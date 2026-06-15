"""
DMF 48通道控制器 — 设置面板
串口参数、路径控制、网格默认值等应用偏好设置。
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QGroupBox, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QSettings


class SettingsWidget(QWidget):
    """应用设置面板，使用 QSettings 持久化。"""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._settings = QSettings("DMFController", "DMF48Channel")
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(16)

        # ── 页面标题 ──
        title = QLabel("设置")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #0f172a;")
        layout.addWidget(title)

        desc = QLabel("配置应用偏好，更改会自动保存。部分参数需重启应用后生效。")
        desc.setStyleSheet("font-size: 13px; color: #64748b;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # ── 串口设置 ──
        serial_group = QGroupBox("串口通信")
        serial_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px; font-weight: 600; color: #0f172a;
                background: #ffffff; border: 1px solid #e2e8f0;
                border-radius: 10px; margin-top: 12px;
                padding: 20px 16px 16px 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                padding: 0 8px;
            }
        """)
        sf = QFormLayout(serial_group)
        sf.setSpacing(12)
        sf.setContentsMargins(8, 8, 8, 8)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(
            ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        )
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setFixedWidth(160)
        sf.addRow("默认波特率：", self.baud_combo)

        layout.addWidget(serial_group)

        # ── 路径控制 ──
        path_group = QGroupBox("路径控制")
        path_group.setStyleSheet(serial_group.styleSheet())
        pf = QFormLayout(path_group)
        pf.setSpacing(12)
        pf.setContentsMargins(8, 8, 8, 8)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(50, 5000)
        self.delay_spin.setValue(500)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setSingleStep(50)
        self.delay_spin.setFixedWidth(160)
        pf.addRow("默认执行间隔：", self.delay_spin)

        layout.addWidget(path_group)

        # ── 网格默认值 ──
        grid_group = QGroupBox("网格默认值")
        grid_group.setStyleSheet(serial_group.styleSheet())
        gf = QFormLayout(grid_group)
        gf.setSpacing(12)
        gf.setContentsMargins(8, 8, 8, 8)

        self.default_rows = QSpinBox()
        self.default_rows.setRange(2, 16)
        self.default_rows.setValue(6)
        self.default_rows.setFixedWidth(100)
        gf.addRow("默认行数：", self.default_rows)

        self.default_cols = QSpinBox()
        self.default_cols.setRange(2, 16)
        self.default_cols.setValue(8)
        self.default_cols.setFixedWidth(100)
        gf.addRow("默认列数：", self.default_cols)

        layout.addWidget(grid_group)

        layout.addStretch()

        # ── 底部操作区 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("↺ 恢复默认")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d1d5db;
                border-radius: 8px; padding: 10px 20px;
                font-size: 14px; font-weight: 600; color: #64748b;
            }
            QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("accent_btn")
        save_btn.setFixedSize(150, 42)
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self):
        """从 QSettings 加载设置。"""
        baud = self._settings.value("baudrate", "115200")
        delay = int(self._settings.value("delay_ms", 500))
        rows = int(self._settings.value("default_rows", 6))
        cols = int(self._settings.value("default_cols", 8))
        self.baud_combo.setCurrentText(baud)
        self.delay_spin.setValue(delay)
        self.default_rows.setValue(rows)
        self.default_cols.setValue(cols)

    def _save_settings(self):
        """保存设置到 QSettings。"""
        self._settings.setValue("baudrate", self.baud_combo.currentText())
        self._settings.setValue("delay_ms", self.delay_spin.value())
        self._settings.setValue("default_rows", self.default_rows.value())
        self._settings.setValue("default_cols", self.default_cols.value())

        # 同步到主窗口
        if self.main_window:
            # 更新 delay_spinbox 的当前值
            delay_str = str(self.delay_spin.value())
            idx = self.main_window.delay_spinbox.findText(delay_str)
            if idx >= 0:
                self.main_window.delay_spinbox.setCurrentIndex(idx)

        QMessageBox.information(
            self, "设置已保存",
            "设置已保存。\n\n"
            "• 步长延迟已即时生效\n"
            "• 串口波特率将在下次连接时生效\n"
            "• 网格默认值将在新建网格时生效"
        )

    def _reset_defaults(self):
        """恢复出厂默认设置。"""
        reply = QMessageBox.question(
            self, "恢复默认",
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.baud_combo.setCurrentText("115200")
        self.delay_spin.setValue(500)
        self.default_rows.setValue(6)
        self.default_cols.setValue(8)
        self._save_settings()
