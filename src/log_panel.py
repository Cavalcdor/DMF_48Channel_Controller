"""
DMF 48通道控制器 — 日志面板
带时间戳、颜色分级、搜索过滤、自动滚动的日志显示器。
"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QCheckBox
)
from PyQt5.QtCore import Qt


class LogPanel(QWidget):
    """带颜色分级、搜索过滤、自动滚动的运行日志面板。"""

    LEVEL_COLORS = {
        "DEBUG": "#94a3b8",
        "INFO": "#3b82f6",
        "SUCCESS": "#10b981",
        "WARN": "#f59e0b",
        "ERROR": "#ef4444",
    }
    LEVEL_ORDER = ["DEBUG", "INFO", "SUCCESS", "WARN", "ERROR"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 2000
        self._entries = []  # list of (timestamp, level, message, html)
        self._filter_text = ""
        self._filter_levels = set(self.LEVEL_ORDER)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # ── 标题栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        title = QLabel("运行日志")
        title.setStyleSheet("font-weight: 700; color: #0f172a;")
        toolbar.addWidget(title)

        toolbar.addStretch()

        self.log_count_label = QLabel("0 条记录")
        self.log_count_label.setStyleSheet("color: #94a3b8;")
        toolbar.addWidget(self.log_count_label)

        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(100, 36)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #e2e8f0;
                border-radius: 6px; font-weight: 600;
                color: #64748b;
            }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
        """)
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # ── 搜索栏 ──
        search_bar = QHBoxLayout()
        search_bar.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日志...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 6px 10px; background: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #3b82f6; }
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)
        search_bar.addWidget(self.search_input, 1)

        layout.addLayout(search_bar)

        # ── 级别过滤 ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("级别:"))
        self._level_checks = {}
        for lv in self.LEVEL_ORDER:
            cb = QCheckBox(lv)
            cb.setChecked(True)
            color = self.LEVEL_COLORS[lv]
            cb.setStyleSheet(
                f"color:{color};font-weight:600;font-size:12px;"
                f"spacing:4px;")
            cb.stateChanged.connect(self._on_filter_changed)
            self._level_checks[lv] = cb
            filter_row.addWidget(cb)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── 日志显示区 ──
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 10px;
                font-family: "Consolas", "Courier New", "Microsoft YaHei", monospace;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.log_view, 1)

    def _on_filter_changed(self):
        """搜索文本或级别过滤变化时重绘日志。"""
        self._filter_text = self.search_input.text().strip().lower()
        self._filter_levels = {
            lv for lv, cb in self._level_checks.items() if cb.isChecked()
        }
        self._rebuild_view()

    def _rebuild_view(self):
        """根据当前过滤条件重建日志显示。"""
        self.log_view.clear()
        count = 0
        for ts, level, msg, html in self._entries:
            # 级别过滤
            if level not in self._filter_levels:
                continue
            # 文本搜索
            if self._filter_text and self._filter_text not in msg.lower():
                continue
            self.log_view.insertHtml(html)
            count += 1
        # 自动滚动到底部
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.log_count_label.setText(f"{count} 条记录 (过滤后)")

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

        # 存入条目列表
        self._entries.append((timestamp, level, message, html))

        # 限制总条目数
        if len(self._entries) > self._max_lines:
            self._entries = self._entries[-self._max_lines:]

        # 检查当前过滤条件是否显示这条
        if level not in self._filter_levels:
            return
        if self._filter_text and self._filter_text not in message.lower():
            return

        self.log_view.insertHtml(html)

        # 限制显示行数
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
        show_count = doc.blockCount()
        self.log_count_label.setText(f"{show_count} 条记录 (过滤后)")

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
        self._entries.clear()
        self.log_view.clear()
        self.log_count_label.setText("0 条记录")

    def log_separator(self):
        """插入一条分隔线。"""
        html = '<hr style="border: none; border-top: 1px solid #334155; margin: 4px 0;"><br>'
        self._entries.append(("", "INFO", "---分隔线---", html))
        if "INFO" in self._filter_levels:
            self.log_view.insertHtml(html)
