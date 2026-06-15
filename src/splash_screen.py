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
        """绘制启动画面（v2.0 优化版 — 更精致的字体比例与布局）。"""
        pixmap = QPixmap(640, 420)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ========== 背景 ==========
        path = QPainterPath()
        path.addRoundedRect(0, 0, 640, 420, 20, 20)
        painter.setClipPath(path)

        bg_gradient = QLinearGradient(0, 0, 0, 420)
        bg_gradient.setColorAt(0.0, QColor("#0b1120"))
        bg_gradient.setColorAt(0.5, QColor("#162240"))
        bg_gradient.setColorAt(1.0, QColor("#0d1829"))
        painter.fillRect(0, 0, 640, 420, bg_gradient)

        # 顶部脉冲光晕
        glow_radius = 320 + int(self._pulse_phase * 0.4)
        glow_alpha = 28 + int(self._pulse_phase * 0.15)
        glow = QRadialGradient(320, 80, glow_radius)
        glow.setColorAt(0.0, QColor(59, 130, 246, glow_alpha))
        glow.setColorAt(0.5, QColor(59, 130, 246, int(glow_alpha * 0.35)))
        glow.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.fillRect(0, 0, 640, 420, glow)

        # ========== 顶部装饰线 ==========
        pen = QPen(QColor("#3b82f6"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(40, 1, 600, 1)

        pen2 = QPen(QColor("#3b82f6"))
        pen2.setWidth(1)
        pen2.setStyle(Qt.DotLine)
        painter.setPen(pen2)
        painter.drawLine(40, 4, 600, 4)

        # ========== 科技感装饰网格 ==========
        painter.setPen(QPen(QColor(59, 130, 246, 25), 1))
        for x in range(0, 640, 40):
            painter.drawLine(x, 0, x, 420)
        for y in range(0, 420, 40):
            painter.drawLine(0, y, 640, y)

        # ========== 浮动粒子 ==========
        for i in range(12):
            px = 40 + (i * 53 + self._particle_offset * 2) % 560
            py = 40 + (i * 37 + self._particle_offset * 3) % 340
            size = 2 + math.sin(self._pulse_phase * 0.1 + i) * 1.5
            p_alpha = int(60 + 30 * math.sin(self._pulse_phase * 0.08 + i * 0.7))
            p_alpha = max(10, min(100, p_alpha))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(147, 197, 253, p_alpha))
            painter.drawEllipse(int(px - size/2), int(py - size/2), int(size), int(size))

        # ========== Logo 区域 (更紧凑，位置上移) ==========
        cx, cy = 320, 100  # 中心从 y=140 → y=100

        # 脉冲发光外圈
        pulse_r = 60 + int(4 * math.sin(self._pulse_phase * 0.06))
        glow_circle = QRadialGradient(cx, cy, pulse_r)
        glow_circle.setColorAt(0.0, QColor(59, 130, 246, 55))
        glow_circle.setColorAt(0.6, QColor(59, 130, 246, 18))
        glow_circle.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.setBrush(QBrush(glow_circle))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(cx - pulse_r), int(cy - pulse_r),
                            int(pulse_r * 2), int(pulse_r * 2))

        # 外圈 (r=42)
        painter.setPen(QPen(QColor("#3b82f6"), 2))
        painter.setBrush(QColor("#0b1120"))
        painter.drawEllipse(cx - 42, cy - 42, 84, 84)

        # 内圈 (r=26)
        inner_grad = QRadialGradient(cx, cy, 22)
        inner_grad.setColorAt(0.0, QColor("#60a5fa"))
        inner_grad.setColorAt(0.7, QColor("#3b82f6"))
        inner_grad.setColorAt(1.0, QColor("#2563eb"))
        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(QColor("#93c5fd"), 1))
        painter.drawEllipse(cx - 26, cy - 26, 52, 52)

        # "DMF" 文字
        font_logo = QFont("Segoe UI", 14, QFont.Bold)
        painter.setFont(font_logo)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(cx - 26, cy - 26, 52, 52),
                         Qt.AlignCenter, "DMF")

        # ========== 标题 (y=168，与Logo间距舒适) ==========
        font_title = QFont("Microsoft YaHei", 30, QFont.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor("#f1f5f9"))
        # 轻微文字阴影
        painter.setPen(QColor(15, 17, 32, 120))
        painter.drawText(QRect(2, 172, 640, 48), Qt.AlignCenter, "DMF 48通道控制器")
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(QRect(0, 170, 640, 48), Qt.AlignCenter, "DMF 48通道控制器")

        # ========== 副标题 ==========
        font_sub = QFont("Microsoft YaHei", 12)
        font_sub.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        painter.setFont(font_sub)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRect(0, 215, 640, 26), Qt.AlignCenter,
                         "数字微流控液滴控制系统")

        # ========== 分隔线 ==========
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(200, 248, 440, 248)

        # ========== 版本标签 (胶囊样式) ==========
        v_label = f"  v{VERSION}  "
        font_ver = QFont("Segoe UI", 11, QFont.Bold)
        fm = painter.fontMetrics()
        v_w = fm.horizontalAdvance(v_label) + 20
        v_x, v_y = (640 - v_w) // 2, 262
        # 胶囊背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(59, 130, 246, 40))
        painter.drawRoundedRect(v_x, v_y, v_w, 24, 12, 12)
        # 胶囊边框
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(59, 130, 246, 100), 1))
        painter.drawRoundedRect(v_x, v_y, v_w, 24, 12, 12)
        # 版本文字
        painter.setFont(font_ver)
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(QRect(v_x, v_y, v_w, 24), Qt.AlignCenter, v_label)

        # ========== 作者 & 年份 ==========
        font_cr = QFont("Microsoft YaHei", 10)
        painter.setFont(font_cr)
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRect(0, 294, 640, 22), Qt.AlignCenter,
                         f"© {YEAR} {AUTHOR}  ·  MIT License")

        # ========== 进度条 ==========
        bar_w, bar_h = 340, 5
        bar_x, bar_y = (640 - bar_w) // 2, 340
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(51, 65, 85, 150))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        if progress > 0:
            fill_w = max(6, int(bar_w * progress / 100))
            pg = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            pg.setColorAt(0.0, QColor("#3b82f6"))
            pg.setColorAt(0.5, QColor("#60a5fa"))
            pg.setColorAt(1.0, QColor("#8b5cf6"))
            painter.setBrush(QBrush(pg))
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

            if progress > 5:
                gpen = QPen(QColor(59, 130, 246, 50), 8)
                gpen.setCapStyle(Qt.RoundCap)
                painter.setPen(gpen)
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(bar_x, bar_y + 3, bar_x + fill_w, bar_y + 3)

        # ========== 加载信息 ==========
        font_msg = QFont("Microsoft YaHei", 10)
        painter.setFont(font_msg)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRect(0, 356, 640, 22), Qt.AlignCenter, message)

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

    def run_loading_sequence(self, tasks: list, min_duration: float = 3.0):
        """执行加载任务序列，确保启动画面至少停留 min_duration 秒。

        Args:
            tasks: [(weight, message, callback), ...]
                   weight: 该任务占总进度的比重
                   message: 显示的文字
                   callback: 执行的任务函数
            min_duration: 最短停留时间（秒），默认 3.0
        """
        import time as _time
        _start = _time.time()

        total_weight = sum(t[0] for t in tasks)
        accumulated = 0

        for weight, message, callback in tasks:
            accumulated += weight
            progress = int(accumulated * 100 / total_weight)
            self.splash.set_progress(max(1, min(99, progress)), message)
            QApplication.processEvents()

            if callback:
                callback()

            _time.sleep(0.05)

        # 加载完毕，检查是否达到最低展示时间
        elapsed = _time.time() - _start
        remaining = min_duration - elapsed
        if remaining > 0:
            # 用进度条动画填充剩余时间
            steps = int(remaining / 0.05)
            for i in range(1, steps + 1):
                fill = 99 + int(i * 1 / steps)  # 99→100 平滑过渡
                msg = "加载完成" if i < steps else "加载完成，正在启动..."
                self.splash.set_progress(min(100, fill), msg)
                QApplication.processEvents()
                _time.sleep(0.05)

        self.splash.set_progress(100, "加载完成，正在启动...")
        QApplication.processEvents()
        _time.sleep(0.2)
