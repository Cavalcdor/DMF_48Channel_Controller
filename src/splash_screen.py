"""
DMF 48通道控制器 — 欢迎启动界面
富有科技感的加载画面，展示应用品牌信息
"""

# ========== 应用全局信息 ==========
VERSION = "1.0.0"
AUTHOR = "Charles WENG"
YEAR = 2026

from PyQt5.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QPen, QFontDatabase, QRadialGradient, QBrush, QPainterPath
)
import time
import math


class DMFSplashScreen(QSplashScreen):
    """DMF 48通道控制器 欢迎启动界面。"""

    # 加载进度信号
    progress_updated = pyqtSignal(int, str)

    def __init__(self):
        # 创建启动画面图像
        splash_pixmap = QPixmap(640, 420)
        splash_pixmap.fill(Qt.transparent)

        super().__init__(splash_pixmap)

        # 存储引用防止被回收
        self._pixmap = splash_pixmap

        # 加载状态
        self.current_progress = 0
        self._particle_offset = 0
        self._pulse_phase = 0

        # 连接信号
        self.progress_updated.connect(self._on_progress_updated)

        # 设置窗口属性
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # 动画定时器 — 粒子浮动 + 脉冲光效
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_frame)
        self._anim_timer.start(50)  # 20fps

        # 绘制初始画面
        self._draw_splash(0, "正在初始化...")

    def _animate_frame(self):
        """每帧更新粒子位置和脉冲效果，重绘画面。"""
        self._particle_offset = (self._particle_offset + 1) % 80
        self._pulse_phase = (self._pulse_phase + 1) % 100
        self._draw_splash(self.current_progress, "")

    def _draw_splash(self, progress: int, message: str):
        """绘制启动画面。"""
        pixmap = QPixmap(640, 420)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ========== 背景 ==========
        # 圆角矩形裁剪
        path = QPainterPath()
        path.addRoundedRect(0, 0, 640, 420, 20, 20)
        painter.setClipPath(path)

        # 深空渐变背景
        bg_gradient = QLinearGradient(0, 0, 0, 420)
        bg_gradient.setColorAt(0.0, QColor("#0b1120"))    # 深空蓝黑
        bg_gradient.setColorAt(0.5, QColor("#162240"))    # 中夜蓝
        bg_gradient.setColorAt(1.0, QColor("#0d1829"))    # 深海蓝
        painter.fillRect(0, 0, 640, 420, bg_gradient)

        # 顶部装饰光晕
        glow_radius = 300 + int(self._pulse_phase * 0.5)
        glow_alpha = 30 + int(self._pulse_phase * 0.2)
        glow = QRadialGradient(320, 80, glow_radius)
        glow.setColorAt(0.0, QColor(59, 130, 246, glow_alpha))
        glow.setColorAt(0.5, QColor(59, 130, 246, int(glow_alpha * 0.4)))
        glow.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.fillRect(0, 0, 640, 420, glow)

        # ========== 顶部装饰线 ==========
        pen = QPen(QColor("#3b82f6"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(40, 1, 600, 1)

        # 细装饰线
        pen2 = QPen(QColor("#3b82f6"))
        pen2.setWidth(1)
        pen2.setStyle(Qt.DotLine)
        painter.setPen(pen2)
        painter.drawLine(40, 4, 600, 4)

        # ========== 科技感装饰网格 ==========
        painter.setPen(QPen(QColor(59, 130, 246, 30), 1))
        for x in range(0, 640, 40):
            painter.drawLine(x, 0, x, 420)
        for y in range(0, 420, 40):
            painter.drawLine(0, y, 640, y)

        # ========== 浮动粒子 ==========
        particle_base_alpha = 60
        for i in range(12):
            px = 40 + (i * 53 + self._particle_offset * 2) % 560
            py = 60 + (i * 37 + self._particle_offset * 3) % 300
            size = 2 + math.sin(self._pulse_phase * 0.1 + i) * 1.5
            p_alpha = int(particle_base_alpha + 30 * math.sin(self._pulse_phase * 0.08 + i * 0.7))
            p_alpha = max(10, min(100, p_alpha))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(147, 197, 253, p_alpha))
            painter.drawEllipse(int(px - size/2), int(py - size/2), int(size), int(size))

        # ========== 图标/Logo 区域 ==========
        # 外圈发光圆（脉冲动画）
        pulse_r = 70 + int(5 * math.sin(self._pulse_phase * 0.06))
        center_x, center_y = 320, 140
        glow_circle = QRadialGradient(center_x, center_y, pulse_r)
        glow_circle.setColorAt(0.0, QColor(59, 130, 246, 60))
        glow_circle.setColorAt(0.7, QColor(59, 130, 246, 20))
        glow_circle.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.setBrush(QBrush(glow_circle))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - 70, center_y - 70, 140, 140)

        # 外圈
        painter.setPen(QPen(QColor("#3b82f6"), 2))
        painter.setBrush(QColor("#0b1120"))
        painter.drawEllipse(center_x - 50, center_y - 50, 100, 100)

        # 内圈
        inner_gradient = QRadialGradient(center_x, center_y, 30)
        inner_gradient.setColorAt(0.0, QColor("#60a5fa"))
        inner_gradient.setColorAt(0.7, QColor("#3b82f6"))
        inner_gradient.setColorAt(1.0, QColor("#2563eb"))
        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(QPen(QColor("#93c5fd"), 1))
        painter.drawEllipse(center_x - 30, center_y - 30, 60, 60)

        # "DMF" 文字在圈内
        font_logo = QFont("Arial", 16, QFont.Bold)
        painter.setFont(font_logo)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(center_x - 30, center_y - 30, 60, 60),
                         Qt.AlignCenter, "DMF")

        # ========== 标题 ==========
        font_title = QFont("Microsoft YaHei", 28, QFont.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(QRect(0, 210, 640, 50), Qt.AlignCenter, "DMF 48通道控制器")

        # ========== 副标题 ==========
        font_sub = QFont("Microsoft YaHei", 13)
        painter.setFont(font_sub)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRect(0, 248, 640, 30), Qt.AlignCenter,
                         "数字微流控液滴控制系统")

        # ========== 信息区域 ==========
        info_y = 290

        # 版本
        font_info = QFont("Segoe UI", 11)
        painter.setFont(font_info)
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRect(0, info_y, 640, 24), Qt.AlignCenter,
                         f"版本 {VERSION}")

        # 作者
        painter.setPen(QColor("#475569"))
        painter.drawText(QRect(0, info_y + 22, 640, 24), Qt.AlignCenter,
                         f"© {YEAR} {AUTHOR}")

        # ========== 进度条背景 ==========
        bar_x, bar_y, bar_w, bar_h = 120, 360, 400, 6
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(51, 65, 85, 150))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        # ========== 进度条填充 ==========
        if progress > 0:
            fill_w = int(bar_w * progress / 100)
            progress_gradient = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            progress_gradient.setColorAt(0.0, QColor("#3b82f6"))
            progress_gradient.setColorAt(1.0, QColor("#8b5cf6"))
            painter.setBrush(QBrush(progress_gradient))
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

            # 进度条发光
            if progress > 5:
                glow_pen = QPen(QColor(59, 130, 246, 60), 8)
                glow_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.NoBrush)
                glow_end = bar_x + fill_w
                painter.drawLine(bar_x, bar_y + 3, glow_end, bar_y + 3)

        # ========== 加载信息文字 ==========
        font_msg = QFont("Microsoft YaHei", 10)
        painter.setFont(font_msg)
        painter.setPen(QColor("#94a3b8"))
        progress_text = f"{message}"
        painter.drawText(QRect(0, 374, 640, 24), Qt.AlignCenter, progress_text)

        # ========== 底部装饰线 ==========
        pen3 = QPen(QColor("#3b82f6"))
        pen3.setWidth(1)
        pen3.setStyle(Qt.DotLine)
        painter.setPen(pen3)
        painter.drawLine(40, 418, 600, 418)

        painter.end()

        self._pixmap = pixmap
        self.setPixmap(pixmap)

    def _on_progress_updated(self, value: int, message: str):
        """更新进度显示。"""
        self.current_progress = value
        self._draw_splash(value, message)
        QApplication.processEvents()

    def set_progress(self, value: int, message: str = ""):
        """线程安全地更新进度。"""
        self.progress_updated.emit(value, message)

    def mousePressEvent(self, event):
        """点击不关闭启动画面（由主窗口控制关闭时机）。"""
        pass


class SplashManager:
    """启动画面管理器，控制加载流程。"""

    def __init__(self):
        self.splash = DMFSplashScreen()

    def show(self):
        """显示启动画面。"""
        self.splash.show()
        QApplication.processEvents()

    def close(self):
        """关闭启动画面。"""
        self.splash.close()

    def run_loading_sequence(self, tasks: list):
        """执行加载任务序列。

        Args:
            tasks: [(weight, message, callback), ...]
                   weight: 该任务占总进度的比重
                   message: 显示的文字
                   callback: 执行的任务函数
        """
        total_weight = sum(t[0] for t in tasks)
        accumulated = 0

        for weight, message, callback in tasks:
            # 更新进度
            accumulated += weight
            progress = int(accumulated * 100 / total_weight)
            self.splash.set_progress(max(1, min(99, progress)), message)
            QApplication.processEvents()

            # 执行任务
            if callback:
                callback()

            # 小额延时让启动画面有呼吸感
            time.sleep(0.05)

        # 完成
        self.splash.set_progress(100, "加载完成，正在启动...")
        QApplication.processEvents()
        time.sleep(0.2)
