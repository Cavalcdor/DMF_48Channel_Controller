"""
DMF 48通道控制器 — 自动更新模块
通过 GitHub Releases API 检查新版本并下载
"""

import json
import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from PyQt5.QtWidgets import (
    QMessageBox, QProgressDialog, QApplication
)
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt

from src.splash_screen import VERSION

# GitHub 仓库信息
GITHUB_OWNER = "Cavalcdor"
GITHUB_REPO = "DMF_48Channel_Controller"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
TAGS_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags"


class UpdateChecker(QThread):
    """后台检查更新的线程。"""

    check_finished = pyqtSignal(dict)  # 检查完成：{has_update, latest_version, download_url, release_notes}
    check_error = pyqtSignal(str)      # 检查出错

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timeout = 10

    def run(self):
        """执行更新检查。"""
        try:
            # 先尝试通过 Releases API 获取最新正式版
            result = self._check_releases()
            if result:
                self.check_finished.emit(result)
                return

            # 降级：通过 Tags API 获取最新版本号（无安装包链接）
            result = self._check_tags()
            if result:
                self.check_finished.emit(result)
                return

            self.check_error.emit("未找到任何版本发布，请管理员在 GitHub 上创建 Release")

        except URLError as e:
            self.check_error.emit(f"网络连接失败：{e.reason}")
        except json.JSONDecodeError:
            self.check_error.emit("服务器返回数据格式异常")
        except Exception as e:
            self.check_error.emit(f"检查更新时出错：{str(e)}")

    def _check_releases(self):
        """通过 Releases API 检查。返回 result dict 或 None。"""
        try:
            req = Request(RELEASES_API, headers={
                "User-Agent": f"DMFController/{VERSION}",
                "Accept": "application/vnd.github.v3+json",
            })
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            latest_version = data.get("tag_name", "").lstrip("v")
            download_url = ""
            release_notes = data.get("body", "")

            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith((".exe", ".msi")):
                    download_url = asset.get("browser_download_url", "")
                    break

            has_update = self._compare_versions(latest_version, VERSION) > 0

            return {
                "has_update": has_update,
                "latest_version": latest_version,
                "download_url": download_url,
                "release_notes": release_notes[:500] if release_notes else "",
                "current_version": VERSION,
            }
        except HTTPError as e:
            if e.code == 404:
                return None  # 没有 Release，降级
            raise
        except URLError:
            return None

    def _check_tags(self):
        """降级：通过 Tags API 获取最新版本号。"""
        try:
            req = Request(TAGS_API, headers={
                "User-Agent": f"DMFController/{VERSION}",
                "Accept": "application/vnd.github.v3+json",
            })
            with urlopen(req, timeout=self.timeout) as resp:
                tags = json.loads(resp.read().decode("utf-8"))

            if not tags:
                return None

            # 找最高版本的 tag（过滤 v 前缀）
            latest_tag = ""
            for t in tags:
                name = t.get("name", "").lstrip("v")
                if self._compare_versions(name, latest_tag) > 0:
                    latest_tag = name

            if not latest_tag:
                return None

            has_update = self._compare_versions(latest_tag, VERSION) > 0
            return {
                "has_update": has_update,
                "latest_version": latest_tag,
                "download_url": "",
                "release_notes": "（无 Release 发布，仅检测到 Git 标签）",
                "current_version": VERSION,
            }
        except (HTTPError, URLError):
            return None

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """比较两个版本号。返回 1/0/-1。"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            max_len = max(len(parts1), len(parts2))
            parts1 += [0] * (max_len - len(parts1))
            parts2 += [0] * (max_len - len(parts2))
            for a, b in zip(parts1, parts2):
                if a > b:
                    return 1
                if a < b:
                    return -1
            return 0
        except (ValueError, AttributeError):
            return 0


class AutoUpdater(QObject):
    """自动更新管理器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.checker = None

    def check_for_update(self, silent: bool = False):
        """检查更新。

        Args:
            silent: 如果没有更新或出错，是否静默（不弹提示框）
        """
        self.checker = UpdateChecker()
        self.checker.check_finished.connect(
            lambda result: self._on_check_done(result, silent)
        )
        self.checker.check_error.connect(
            lambda err: self._on_check_error(err, silent)
        )
        self.checker.start()

    def _on_check_done(self, result: dict, silent: bool):
        """更新检查完成。"""
        if result["has_update"]:
            self._show_update_available(result)
        elif not silent:
            QMessageBox.information(
                None,
                "检查更新",
                f"✓ 当前已是最新版本 (v{result['current_version']})"
            )

    def _on_check_error(self, error: str, silent: bool):
        """更新检查出错。"""
        if not silent:
            QMessageBox.warning(None, "检查更新", f"检查更新失败：\n{error}")

    def _show_update_available(self, result: dict):
        """显示有新版本。"""
        msg = QMessageBox()
        msg.setWindowTitle("发现新版本")
        msg.setText(
            f"发现新版本 v{result['latest_version']}！\n"
            f"当前版本: v{result['current_version']}"
        )
        if result["release_notes"]:
            msg.setDetailedText(f"更新说明：\n{result['release_notes']}")

        if result["download_url"]:
            download_btn = msg.addButton("下载更新", QMessageBox.ActionRole)
            msg.addButton("稍后再说", QMessageBox.RejectRole)

        msg.exec_()

        if result.get("download_url") and msg.clickedButton() == download_btn:
            webbrowser.open(result["download_url"])


def check_for_update(parent=None, silent=False):
    """便捷函数：检查更新。"""
    updater = AutoUpdater(parent)
    updater.check_for_update(silent)
    return updater
