"""
DMF 48通道控制器 — 关于对话框
展示应用版本、作者信息、技术栈等
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QFrame
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices

from src.splash_screen import VERSION, AUTHOR, YEAR

GITHUB_URL = "https://github.com/Cavalcdor/DMF_48Channel_Controller"


class ClickableLabel(QLabel):
    """可点击的标签，点击打开链接，hover 时高亮。"""

    _normal_style = "font-size: 12px; color: #60a5fa; background: transparent;"
    _hover_style  = "font-size: 12px; color: #93c5fd; background: transparent; text-decoration: underline;"

    def __init__(self, text, url, parent=None):
        super().__init__(parent)
        self._url = url
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self._normal_style)

    def mousePressEvent(self, event):
        QDesktopServices.openUrl(QUrl(self._url))

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)

    def leaveEvent(self, event):
        self.setStyleSheet(self._normal_style)


class AboutDialog(QDialog):
    """DMF 48通道控制器 关于对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 DMF 48通道控制器")
        self.setFixedSize(500, 420)
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

        # ========== 构建 UI ==========
        self._build_ui()

    def _build_ui(self):
        """构建完整的 UI 布局（使用布局管理器，无硬编码坐标）。"""
        # ── 根布局 ──
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 主内容容器 ──
        container = QWidget()
        container.setObjectName("aboutContainer")
        container.setStyleSheet("""
            QWidget#aboutContainer {
                background-color: #0f172a;
                border-radius: 12px;
            }
        """)
        root.addWidget(container)

        # 容器内部使用垂直布局
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 30, 40, 20)
        layout.setSpacing(0)

        # ═══════════ 顶部：Logo + 标题 ═══════════
        # Logo 圆
        logo_widget = QWidget()
        logo_widget.setFixedSize(72, 72)
        logo_widget.setStyleSheet("""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #3b82f6, stop:1 #2563eb);
            border-radius: 36px;
        """)
        logo_label = QLabel("DMF", logo_widget)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setGeometry(0, 0, 72, 72)
        logo_label.setStyleSheet("""
            font-size: 18px;
            font-weight: 800;
            color: white;
            background: transparent;
            letter-spacing: 1px;
        """)

        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(logo_widget)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        layout.addSpacing(16)

        # 标题
        title = QLabel("DMF 48通道控制器")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: #f1f5f9;
            background: transparent;
            letter-spacing: 2px;
        """)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("数字微流控液滴控制系统")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 12px;
            color: #94a3b8;
            background: transparent;
            letter-spacing: 2px;
            padding-top: 4px;
        """)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # ═══════════ 分隔线 ═══════════
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1e3a5f; border: none;")
        layout.addWidget(sep)

        layout.addSpacing(20)

        # ═══════════ 信息表格 ═══════════
        info_items = [
            ("版  本", f"v{VERSION}"),
            ("制作者", AUTHOR),
            ("年  份", str(YEAR)),
            ("运行环境", "Python 3.12 + PyQt5"),
            ("开源协议", "MIT License"),
        ]

        for label, value in info_items:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)

            lbl_key = QLabel(label)
            lbl_key.setFixedWidth(72)
            lbl_key.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl_key.setStyleSheet("""
                font-size: 12px;
                color: #64748b;
                background: transparent;
                padding: 5px 0;
            """)
            row.addWidget(lbl_key)

            lbl_val = QLabel(value)
            lbl_val.setStyleSheet("""
                font-size: 13px;
                font-weight: 600;
                color: #e2e8f0;
                background: transparent;
                padding: 5px 0;
            """)
            row.addWidget(lbl_val)

            row.addStretch()
            layout.addLayout(row)

        layout.addStretch()

        # ═══════════ 底部：GitHub 链接 + 版权 ═══════════
        # 分隔线
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: #1e3a5f; border: none;")
        layout.addWidget(sep2)

        layout.addSpacing(14)

        # GitHub 链接行
        gh_row = QHBoxLayout()
        gh_row.setContentsMargins(0, 0, 0, 0)
        gh_row.setSpacing(8)

        gh_icon = QLabel("G")
        gh_icon.setFixedSize(20, 20)
        gh_icon.setAlignment(Qt.AlignCenter)
        gh_icon.setStyleSheet("""
            font-size: 11px; font-weight: 800; color: #60a5fa;
            background: #1e3a5f; border-radius: 10px;
        """)
        gh_row.addWidget(gh_icon)

        gh_link = ClickableLabel("GitHub 仓库", GITHUB_URL)
        gh_link.setStyleSheet("""
            font-size: 12px;
            color: #60a5fa;
            background: transparent;
        """)
        gh_row.addWidget(gh_link)

        gh_row.addStretch()

        # 版权
        copyright_lbl = QLabel(f"© {YEAR} {AUTHOR}")
        copyright_lbl.setStyleSheet("""
            font-size: 11px;
            color: #475569;
            background: transparent;
        """)
        gh_row.addWidget(copyright_lbl)

        layout.addLayout(gh_row)

        layout.addSpacing(16)

        # ═══════════ 确定按钮 ═══════════
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()

        close_btn = QPushButton("确  定")
        close_btn.setFixedSize(120, 36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)
