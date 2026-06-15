"""
DMF 48通道控制器 — 工程管理器
提供工程文件(.dmf)的保存、加载、最近文件管理。
"""
import json
import os
from datetime import datetime

from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QSettings

from .splash_screen import VERSION

PROJECT_EXT = ".dmf"
PROJECT_FILTER = f"DMF 工程文件 (*{PROJECT_EXT})"


class ProjectManager:
    """工程管理器：序列化/反序列化网格状态，管理最近文件。"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.current_file = None
        self._settings = QSettings("DMFController", "DMF48Channel")

    # ── 最近文件 ──────────────────────────────────

    def get_recent_files(self):
        raw = self._settings.value("recent_files", [])
        if isinstance(raw, str):
            raw = [raw]
        return [f for f in raw if os.path.exists(f)] if raw else []

    def add_recent_file(self, filepath):
        files = self.get_recent_files()
        if filepath in files:
            files.remove(filepath)
        files.insert(0, filepath)
        self._settings.setValue("recent_files", files[:5])

    def clear_recent_files(self):
        self._settings.setValue("recent_files", [])

    # ── 序列化 ──────────────────────────────────

    def _serialize(self):
        gw = self.main_window.grid_widget
        from . import global_cfg
        return {
            "format_version": VERSION,
            "created": datetime.now().isoformat(),
            "grid_rows": gw.rows,
            "grid_cols": gw.cols,
            "cells": [[gw.grid[r][c] for c in range(gw.cols)] for r in range(gw.rows)],
            "droplet_starts": {str(k): list(v) for k, v in gw.droplet_starts.items()},
            "droplet_targets": {str(k): list(v) for k, v in gw.droplet_targets.items()},
            "delay_ms": int(self.main_window.delay_spinbox.currentText()),
        }

    def _deserialize(self, data):
        from . import global_cfg
        gw = self.main_window.grid_widget
        rows = data.get("grid_rows", 6)
        cols = data.get("grid_cols", 8)

        # 更新全局配置
        global_cfg.ELECTRODE_ROWS = rows
        global_cfg.ELECTRODE_COLS = cols
        global_cfg.TOTAL_ELECTRODES = rows * cols

        # 重建网格
        gw.rebuild_grid(rows, cols)

        # 恢复单元格状态
        cells = data.get("cells", [])
        for r in range(min(len(cells), rows)):
            for c in range(min(len(cells[r]), cols)):
                gw.grid[r][c] = cells[r][c]

        # 恢复液滴配对
        gw.droplet_starts = {int(k): tuple(v) for k, v in data.get("droplet_starts", {}).items()}
        gw.droplet_targets = {int(k): tuple(v) for k, v in data.get("droplet_targets", {}).items()}

        # 恢复延迟设置
        delay = data.get("delay_ms", 500)
        delay_str = str(delay)
        idx = self.main_window.delay_spinbox.findText(delay_str)
        if idx >= 0:
            self.main_window.delay_spinbox.setCurrentIndex(idx)

        gw.update()
        gw.droplet_config_changed.emit()

    # ── 文件操作 ──────────────────────────────────

    def new_project(self):
        """新建工程：重置网格，清除所有配置。"""
        reply = QMessageBox.question(
            self.main_window, "新建工程",
            "当前未保存的更改将丢失，是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return False
        self.main_window.on_reset_grid()
        self.current_file = None
        self.main_window.statusBar().showMessage("已新建工程")
        return True

    def save_project(self):
        """保存工程到当前文件，若无则另存为。"""
        if self.current_file and os.path.exists(self.current_file):
            self._save(self.current_file)
            return True
        return self.save_project_as()

    def save_project_as(self):
        """另存为新的工程文件。"""
        filepath, _ = QFileDialog.getSaveFileName(
            self.main_window, "保存工程", "",
            PROJECT_FILTER
        )
        if not filepath:
            return False
        if not filepath.endswith(PROJECT_EXT):
            filepath += PROJECT_EXT
        self._save(filepath)
        return True

    def open_project(self, filepath=None):
        """打开工程文件。"""
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(
                self.main_window, "打开工程", "",
                PROJECT_FILTER
            )
            if not filepath:
                return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._deserialize(data)
            self.current_file = filepath
            self.add_recent_file(filepath)
            name = os.path.splitext(os.path.basename(filepath))[0]
            self.main_window.statusBar().showMessage(f"已加载工程: {name}")
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "加载失败",
                                 f"无法加载工程文件:\n{e}")
            return False

    def _save(self, filepath):
        try:
            data = self._serialize()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.current_file = filepath
            self.add_recent_file(filepath)
            name = os.path.splitext(os.path.basename(filepath))[0]
            self.main_window.statusBar().showMessage(f"已保存工程: {name}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "保存失败",
                                 f"无法保存工程文件:\n{e}")
