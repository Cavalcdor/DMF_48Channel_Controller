"""
DMF 48通道控制器 — 关于对话框
展示应用版本、作者信息、技术栈等
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QApplication
)
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QPen, QRadialGradient, QBrush, QPainterPath, QFontDatabase
)

from src.splash_screen import VERSION, AUTHOR, YEAR

GITHUB_URL = "https://github.com/Cavalcdor/DMF_48Channel_Controller"


class AboutDialog(QDialog):
    """DMF 48通道控制器 关于对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 DMF 48通道控制器")
        self.setFixedSize(500, 380)
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

        # ========== 背景图 ==========
        bg = QPixmap(500, 380)
        bg.fill(Qt.transparent)
        self._draw_background(bg)

        # ========== UI 布局 ==========
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部装饰区 — 用背景图
        top_label = QLabel()
        top_label.setPixmap(bg)
        top_label.setFixedSize(500, 380)
        top_label.setScaledContents(True)
        layout.addWidget(top_label)

        # 覆盖文字层
        self._overlay_text(top_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 0, 20, 16)

        btn_layout.addStretch()

        close_btn = QPushButton("确  定")
        close_btn.setFixedSize(120, 36)
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
        btn_layout.addWidget(close_btn)

        # 把按钮放到顶层
        self.btn_widget = QWidget()
        self.btn_widget.setLayout(btn_layout)
        self.btn_widget.setStyleSheet("background: transparent;")
        self.btn_widget.setGeometry(0, 340, 500, 40)
        self.btn_widget.setParent(top_label)

    def _draw_background(self, pixmap: QPixmap):
        """绘制对话框背景。"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 圆角裁剪
        path = QPainterPath()
        path.addRoundedRect(0, 0, 500, 380, 16, 16)
        painter.setClipPath(path)

        # 深色渐变背景
        bg = QLinearGradient(0, 0, 500, 380)
        bg.setColorAt(0.0, QColor("#0f172a"))
        bg.setColorAt(0.5, QColor("#1e293b"))
        bg.setColorAt(1.0, QColor("#0f172a"))
        painter.fillRect(0, 0, 500, 380, bg)

        # 顶部光效
        glow = QRadialGradient(250, 60, 200)
        glow.setColorAt(0.0, QColor(59, 130, 246, 30))
        glow.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.fillRect(0, 0, 500, 380, glow)

        # 顶部装饰线
        pen = QPen(QColor("#3b82f6"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(30, 2, 470, 2)

        # 科技网格
        painter.setPen(QPen(QColor(59, 130, 246, 15), 1))
        for x in range(0, 500, 40):
            painter.drawLine(x, 0, x, 380)

        painter.end()

    def _overlay_text(self, parent: QLabel):
        """在背景上叠加文字信息。"""
        # Logo 圆
        labels = []

        def make_label(text, style, geometry):
            lbl = QLabel(text, parent)
            lbl.setStyleSheet(style)
            lbl.setGeometry(*geometry)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl.show()
            labels.append(lbl)
            return lbl

        # 应用名称
        make_label(
            "DMF 48通道控制器",
            """
            font-size: 26px;
            font-weight: 700;
            color: #f1f5f9;
            background: transparent;
            letter-spacing: 2px;
            """,
            (0, 30, 500, 40)
        )

        # 副标题
        make_label(
            "数字微流控液滴控制系统",
            """
            font-size: 13px;
            color: #94a3b8;
            background: transparent;
            letter-spacing: 1px;
            """,
            (0, 68, 500, 24)
        )

        # 分隔线
        sep_label = QLabel(parent)
        sep_label.setGeometry(180, 105, 140, 1)
        sep_label.setStyleSheet("background-color: #334155;")
        sep_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        sep_label.show()

        # 版本信息
        info_items = [
            ("版本", f"v{VERSION}"),
            ("制作者", AUTHOR),
            ("发布年份", str(YEAR)),
            ("运行环境", f"Python 3.12 + PyQt5"),
            ("协议", "MIT License"),
        ]

        y_start = 125
        for i, (label, value) in enumerate(info_items):
            y = y_start + i * 40
            make_label(
                label,
                """
                font-size: 12px;
                color: #64748b;
                background: transparent;
                """,
                (60, y, 80, 28)
            )
            make_label(
                value,
                """
                font-size: 13px;
                font-weight: 600;
                color: #e2e8f0;
                background: transparent;
                """,
                (150, y, 250, 28)
            )

        # 项目链接
        make_label(
            "🌐 GitHub 仓库",
            """
            font-size: 11px;
            color: #3b82f6;
            background: transparent;
            text-decoration: underline;
            """,
            (60, 315, 250, 20)
        )

        # 版权
        make_label(
            f"© {YEAR} {AUTHOR}. All rights reserved.",
            """
            font-size: 11px;
            color: #475569;
            background: transparent;
            """,
            (0, 310, 500, 20)
        )
