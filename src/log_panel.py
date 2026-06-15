"""
DMF 48通道控制器 — 日志面板
带时间戳、颜色分级、自动滚动的日志显示器。
"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel
)
from PyQt5.QtCore import Qt


class LogPanel(QWidget):
    """带颜色分级、自动滚动的运行日志面板。"""

    LEVEL_COLORS = {
        "DEBUG": "#94a3b8",
        "INFO": "#3b82f6",
        "SUCCESS": "#10b981",
        "WARN": "#f59e0b",
        "ERROR": "#ef4444",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 2000
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # ── 标题栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        title = QLabel("📋 运行日志")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0f172a;")
        toolbar.addWidget(title)

        toolbar.addStretch()

        self.log_count_label = QLabel("0 条记录")
        self.log_count_label.setStyleSheet("font-size: 13px; color: #94a3b8;")
        toolbar.addWidget(self.log_count_label)

        clear_btn = QPushButton("🗑 清空")
        clear_btn.setFixedSize(100, 34)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #e2e8f0;
                border-radius: 6px; font-size: 13px; font-weight: 600;
                color: #64748b;
            }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
        """)
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # ── 日志显示区 ──
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 14px;
                font-family: "Consolas", "Courier New", "Microsoft YaHei", monospace;
                font-size: 14px;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.log_view, 1)

    def _log(self, level, message):
        """内部：写入一条带颜色的日志。"""
        if level not in self.LEVEL_COLORS:
            level = "INFO"
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.LEVEL_COLORS[level]
        html = (
            f'<span style="color: #475569;">[{timestamp}]</span> '
            f'<span style="color: {color}; font-weight: 700;">[{level}]</span> '
            f'<span style="color: #e2e8f0;">{message}</span><br>'
        )
        self.log_view.insertHtml(html)

        # 限制总行数
        doc = self.log_view.document()
        if doc.blockCount() > self._max_lines:
            cursor = self.log_view.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor,
                                doc.blockCount() - self._max_lines)
            cursor.removeSelectedText()

        # 自动滚动到底部
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 更新计数
        self.log_count_label.setText(f"{doc.blockCount()} 条记录")

    # ── 公开日志接口 ──────────────────────────

    def log_debug(self, message):
        self._log("DEBUG", message)

    def log_info(self, message):
        self._log("INFO", message)

    def log_success(self, message):
        self._log("SUCCESS", message)

    def log_warn(self, message):
        self._log("WARN", message)

    def log_error(self, message):
        self._log("ERROR", message)

    def clear(self):
        """清空所有日志。"""
        self.log_view.clear()
        self.log_count_label.setText("0 条记录")

    def log_separator(self):
        """插入一条分隔线。"""
        self.log_view.insertHtml(
            '<hr style="border: none; border-top: 1px solid #334155; margin: 4px 0;">'
        )
