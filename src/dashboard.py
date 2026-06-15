"""
DMF 48通道控制器 — 仪表盘主页
系统状态总览、快速操作入口、最近工程列表。
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QBrush,
    QPen, QPixmap, QPainterPath, QFontDatabase
)

from .splash_screen import VERSION, AUTHOR, YEAR


class DashboardWidget(QWidget):
    """仪表盘主页 — 提供系统状态总览和快速操作入口。"""

    # 快速操作信号
    signal_new_project = pyqtSignal()
    signal_open_project = pyqtSignal()
    signal_save_project = pyqtSignal()
    signal_plan_path = pyqtSignal()
    signal_run_path = pyqtSignal()
    signal_open_recent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(24)

        # ===== 顶部横幅 =====
        banner = QWidget()
        banner.setFixedHeight(110)
        banner.setObjectName("dash_banner")
        banner.setStyleSheet("""
            QWidget#dash_banner {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a, stop:0.5 #1e293b, stop:1 #0f172a
                );
                border-radius: 14px;
            }
        """)
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(28, 0, 28, 0)

        welcome = QLabel("欢迎使用 DMF 48通道控制器")
        welcome.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #f1f5f9; background: transparent;"
        )
        banner_layout.addWidget(welcome)

        subtitle = QLabel("数字微流控液滴控制系统  ·  快速了解系统状态并执行操作")
        subtitle.setStyleSheet(
            "font-size: 13px; color: #94a3b8; background: transparent;"
        )
        banner_layout.addWidget(subtitle)
        layout.addWidget(banner)

        # ===== 状态卡片 =====
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        self.card_serial = self._make_card("🔌 串口状态", "未连接", "#ef4444")
        self.card_grid = self._make_card("📐 网格尺寸", "6 × 8", "#3b82f6")
        self.card_droplet = self._make_card("💧 液滴配置", "0 / 8", "#8b5cf6")
        self.card_path = self._make_card("🗺️ 路径规划", "无", "#f59e0b")

        cards_layout.addWidget(self.card_serial)
        cards_layout.addWidget(self.card_grid)
        cards_layout.addWidget(self.card_droplet)
        cards_layout.addWidget(self.card_path)
        cards_layout.addStretch()
        layout.addLayout(cards_layout)

        # ===== 分隔线 =====
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #e2e8f0; max-height: 1px;")
        layout.addWidget(sep)

        # ===== 快速操作 =====
        action_title = QLabel("⚡ 快速操作")
        action_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #0f172a;")
        layout.addWidget(action_title)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        actions = [
            ("📄 新工程", self.signal_new_project, "#3b82f6"),
            ("📂 打开工程", self.signal_open_project, "#8b5cf6"),
            ("💾 保存工程", self.signal_save_project, "#059669"),
            ("🗺️ 规划路径", self.signal_plan_path, "#f59e0b"),
            ("▶️ 运行路径", self.signal_run_path, "#10b981"),
        ]
        for text, sig, color in actions:
            btn = QPushButton(text)
            btn.setFixedHeight(46)
            btn.setMinimumWidth(130)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    font-size: 14px;
                    font-weight: 600;
                    color: #1e293b;
                    padding: 0 18px;
                }}
                QPushButton:hover {{
                    border-color: {color};
                    background: #f8fafc;
                }}
                QPushButton:pressed {{
                    background: #f1f5f9;
                }}
            """)
            btn.clicked.connect(sig.emit)
            actions_layout.addWidget(btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # ===== 分隔线 =====
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #e2e8f0; max-height: 1px;")
        layout.addWidget(sep2)

        # ===== 最近工程 =====
        recent_title = QLabel("📂 最近工程")
        recent_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #0f172a;")
        layout.addWidget(recent_title)

        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(150)
        self.recent_list.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 4px;
                font-size: 13px;
                color: #334155;
            }
            QListWidget::item {
                padding: 8px 14px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: #f1f5f9;
            }
            QListWidget::item:selected {
                background: #e2e8f0;
                color: #0f172a;
            }
        """)
        self.recent_list.itemDoubleClicked.connect(self._on_recent_double_click)
        layout.addWidget(self.recent_list)

        layout.addStretch()

        # ===== 版本脚注 =====
        footer = QLabel(f"DMF 48通道控制器  v{VERSION}  © {YEAR} {AUTHOR}  ·  MIT License")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 12px; color: #94a3b8;")
        layout.addWidget(footer)

    # ── 工具方法 ──────────────────────────────

    def _make_card(self, title, value, color):
        """创建状态卡片。"""
        card = QFrame()
        card.setFixedSize(215, 105)
        card.setObjectName("stat_card")
        card.setStyleSheet(f"""
            QFrame#stat_card {{
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.setSpacing(6)

        t = QLabel(title)
        t.setStyleSheet("font-size: 13px; color: #64748b; font-weight: 500; border: none;")
        cl.addWidget(t)

        card.value_label = QLabel(value)
        card.value_label.setStyleSheet(
            f"font-size: 26px; color: {color}; font-weight: 700; border: none;"
        )
        cl.addWidget(card.value_label)

        return card

    def _on_recent_double_click(self, item):
        """双击最近工程列表项。"""
        filepath = item.data(Qt.UserRole)
        if filepath and os.path.exists(filepath):
            self.signal_open_recent.emit(filepath)

    # ── 公开更新接口 ──────────────────────────

    def update_serial_status(self, connected, port=""):
        """更新串口状态卡片。"""
        text = f"已连接 ({port})" if connected else "未连接"
        color = "#16a34a" if connected else "#ef4444"
        self.card_serial.value_label.setText(text)
        self.card_serial.value_label.setStyleSheet(
            f"font-size: 18px; color: {color}; font-weight: 700; border: none;"
        )

    def update_grid_info(self, rows, cols):
        """更新网格尺寸卡片。"""
        self.card_grid.value_label.setText(f"{rows} × {cols}")

    def update_droplet_info(self, paired, total=8, configured=0):
        """更新液滴配置卡片。"""
        self.card_droplet.value_label.setText(f"{paired} / {total}")

    def update_path_info(self, count):
        """更新路径规划卡片。"""
        text = f"{count} 条路径" if count > 0 else "无"
        color = "#10b981" if count > 0 else "#f59e0b"
        self.card_path.value_label.setText(text)
        self.card_path.value_label.setStyleSheet(
            f"font-size: 22px; color: {color}; font-weight: 700; border: none;"
        )

    def update_recent_files(self, files):
        """更新最近工程列表。"""
        self.recent_list.clear()
        if not files:
            item = QListWidgetItem("暂无最近工程")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor("#94a3b8"))
            self.recent_list.addItem(item)
            return
        for fp in files:
            name = os.path.splitext(os.path.basename(fp))[0]
            dname = os.path.dirname(fp)
            if len(dname) > 40:
                dname = "..." + dname[-37:]
            item = QListWidgetItem(f"📄  {name}    —  {dname}")
            item.setData(Qt.UserRole, fp)
            self.recent_list.addItem(item)
