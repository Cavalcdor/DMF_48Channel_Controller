"""
DMF 48通道控制器 — 欢迎启动界面
富有科技感的加载画面，展示应用品牌信息
"""

# ========== 应用全局信息 ==========
VERSION = "2.1.0"
AUTHOR = "Charles WENG"
YEAR = 2026

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QSize
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QPen, QRadialGradient, QBrush, QPainterPath
)
import math


class DMFSplashScreen(QWidget):
    """DMF 48通道控制器 欢迎启动界面（基于 QWidget，完全控制尺寸）。"""

    # 固定尺寸常量 — 拉大上下空间
    SPLASH_W = 960
    SPLASH_H = 640

    # 加载进度信号
    progress_updated = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()

        # 窗口标志 — 无框、置顶、启动画面类型
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # ⭐ 强制窗口逻辑尺寸为 pixmap 大小（device-independent pixels）
        self.setFixedSize(QSize(self.SPLASH_W, self.SPLASH_H))

        # 加载状态
        self.current_progress = 0
        self._particle_offset = 0
        self._pulse_phase = 0
        self._pixmap = QPixmap(self.SPLASH_W, self.SPLASH_H)
        self._pixmap.fill(Qt.transparent)

        # 连接信号
        self.progress_updated.connect(self._on_progress_updated)

        # 动画定时器 — 粒子浮动 + 脉冲光效
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_frame)
        self._anim_timer.start(50)  # 20fps

        # 绘制初始画面
        self._draw_splash(0, "正在初始化...")

    # ── QWidget 事件重写 ──────────────────────────────────

    def paintEvent(self, event):
        """将缓存的 pixmap 绘制到窗口。"""
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

    def mousePressEvent(self, event):
        """点击不关闭启动画面（由主窗口控制关闭时机）。"""
        pass

    # ── 动画循环 ──────────────────────────────────────────

    def _animate_frame(self):
        """每帧更新粒子位置和脉冲效果，触发重绘。"""
        self._particle_offset = (self._particle_offset + 1) % 80
        self._pulse_phase = (self._pulse_phase + 1) % 100
        self._draw_splash(self.current_progress, "")

    def _draw_splash(self, progress: int, message: str):
        """绘制启动画面到离屏 pixmap 并触发重绘。"""
        W, H = self.SPLASH_W, self.SPLASH_H
        pixmap = QPixmap(W, H)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ========== 背景 ==========
        path = QPainterPath()
        path.addRoundedRect(0, 0, W, H, 24, 24)
        painter.setClipPath(path)

        bg_gradient = QLinearGradient(0, 0, 0, H)
        bg_gradient.setColorAt(0.0, QColor("#0b1120"))
        bg_gradient.setColorAt(0.5, QColor("#162240"))
        bg_gradient.setColorAt(1.0, QColor("#0d1829"))
        painter.fillRect(0, 0, W, H, bg_gradient)

        # 顶部脉冲光晕
        glow_radius = 480 + int(self._pulse_phase * 0.6)
        glow_alpha = 35 + int(self._pulse_phase * 0.2)
        glow = QRadialGradient(W // 2, 120, glow_radius)
        glow.setColorAt(0.0, QColor(59, 130, 246, glow_alpha))
        glow.setColorAt(0.5, QColor(59, 130, 246, int(glow_alpha * 0.35)))
        glow.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.fillRect(0, 0, W, H, glow)

        # ========== 顶部装饰线 ==========
        pen = QPen(QColor("#3b82f6"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(60, 2, W - 60, 2)

        pen2 = QPen(QColor("#3b82f6"))
        pen2.setWidth(1)
        pen2.setStyle(Qt.DotLine)
        painter.setPen(pen2)
        painter.drawLine(60, 6, W - 60, 6)

        # ========== 科技感装饰网格 ==========
        painter.setPen(QPen(QColor(59, 130, 246, 20), 1))
        for x in range(0, W, 60):
            painter.drawLine(x, 0, x, H)
        for y in range(0, H, 60):
            painter.drawLine(0, y, W, y)

        # ========== 浮动粒子 ==========
        for i in range(20):
            px = 60 + (i * 53 + self._particle_offset * 2) % (W - 120)
            py = 60 + (i * 37 + self._particle_offset * 3) % (H - 120)
            size = 2 + math.sin(self._pulse_phase * 0.1 + i) * 2
            p_alpha = int(60 + 30 * math.sin(self._pulse_phase * 0.08 + i * 0.7))
            p_alpha = max(10, min(100, p_alpha))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(147, 197, 253, p_alpha))
            painter.drawEllipse(int(px - size/2), int(py - size/2), int(size), int(size))

        # ========== Logo 区域 (下移，留足顶空) ==========
        cx, cy = W // 2, 160

        # 脉冲发光外圈
        pulse_r = 80 + int(5 * math.sin(self._pulse_phase * 0.06))
        glow_circle = QRadialGradient(cx, cy, pulse_r)
        glow_circle.setColorAt(0.0, QColor(59, 130, 246, 55))
        glow_circle.setColorAt(0.6, QColor(59, 130, 246, 18))
        glow_circle.setColorAt(1.0, QColor(59, 130, 246, 0))
        painter.setBrush(QBrush(glow_circle))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(cx - pulse_r), int(cy - pulse_r),
                            int(pulse_r * 2), int(pulse_r * 2))

        # 外圈 (r=52)
        painter.setPen(QPen(QColor("#3b82f6"), 2))
        painter.setBrush(QColor("#0b1120"))
        painter.drawEllipse(cx - 52, cy - 52, 104, 104)

        # 内圈 (r=34)
        inner_grad = QRadialGradient(cx, cy, 30)
        inner_grad.setColorAt(0.0, QColor("#60a5fa"))
        inner_grad.setColorAt(0.7, QColor("#3b82f6"))
        inner_grad.setColorAt(1.0, QColor("#2563eb"))
        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(QColor("#93c5fd"), 1))
        painter.drawEllipse(cx - 34, cy - 34, 68, 68)

        # "DMF" 文字
        font_logo = QFont("Segoe UI", 20, QFont.Bold)
        painter.setFont(font_logo)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(cx - 34, cy - 34, 68, 68),
                         Qt.AlignCenter, "DMF")

        # ========== 标题 (大幅下移 + 增高文字框) ==========
        font_title = QFont("Microsoft YaHei", 38, QFont.Bold)
        painter.setFont(font_title)
        # 阴影
        painter.setPen(QColor(15, 17, 32, 120))
        painter.drawText(QRect(3, 260, W, 60), Qt.AlignCenter, "DMF 48通道控制器")
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(QRect(0, 257, W, 60), Qt.AlignCenter, "DMF 48通道控制器")

        # ========== 副标题 ==========
        font_sub = QFont("Microsoft YaHei", 15)
        font_sub.setLetterSpacing(QFont.AbsoluteSpacing, 5)
        painter.setFont(font_sub)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRect(0, 322, W, 32), Qt.AlignCenter,
                         "数字微流控液滴控制系统")

        # ========== 分隔线 ==========
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        painter.drawLine(W // 2 - 180, 370, W // 2 + 180, 370)

        # ========== 版本标签 ==========
        v_label = f"  v{VERSION}  "
        font_ver = QFont("Segoe UI", 14, QFont.Bold)
        fm = painter.fontMetrics()
        v_w = fm.horizontalAdvance(v_label) + 28
        v_x, v_y = (W - v_w) // 2, 388
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(59, 130, 246, 40))
        painter.drawRoundedRect(v_x, v_y, v_w, 30, 15, 15)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(59, 130, 246, 100), 1))
        painter.drawRoundedRect(v_x, v_y, v_w, 30, 15, 15)
        painter.setFont(font_ver)
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(QRect(v_x, v_y, v_w, 30), Qt.AlignCenter, v_label)

        # ========== 作者 & 年份 ==========
        font_cr = QFont("Microsoft YaHei", 12)
        painter.setFont(font_cr)
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRect(0, 440, W, 26), Qt.AlignCenter,
                         f"© {YEAR} {AUTHOR}  ·  MIT License")

        # ========== 进度条 ==========
        bar_w, bar_h = 460, 6
        bar_x, bar_y = (W - bar_w) // 2, 510
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(51, 65, 85, 150))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        if progress > 0:
            fill_w = max(8, int(bar_w * progress / 100))
            pg = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            pg.setColorAt(0.0, QColor("#3b82f6"))
            pg.setColorAt(0.5, QColor("#60a5fa"))
            pg.setColorAt(1.0, QColor("#8b5cf6"))
            painter.setBrush(QBrush(pg))
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

            if progress > 5:
                gpen = QPen(QColor(59, 130, 246, 50), 10)
                gpen.setCapStyle(Qt.RoundCap)
                painter.setPen(gpen)
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(bar_x, bar_y + 3, bar_x + fill_w, bar_y + 3)

        # ========== 加载信息 ==========
        font_msg = QFont("Microsoft YaHei", 13)
        painter.setFont(font_msg)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRect(0, 538, W, 28), Qt.AlignCenter, message)

        # ========== 底部装饰线 ==========
        pen3 = QPen(QColor("#3b82f6"))
        pen3.setWidth(1)
        pen3.setStyle(Qt.DotLine)
        painter.setPen(pen3)
        painter.drawLine(60, H - 6, W - 60, H - 6)

        painter.end()

        self._pixmap = pixmap
        self.update()  # 触发 paintEvent 绘制到窗口

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
        """显示启动画面（居中显示）。"""
        # 确保窗口尺寸正确
        self.splash.setFixedSize(QSize(self.splash.SPLASH_W, self.splash.SPLASH_H))
        # 居中于屏幕
        screen_geo = QApplication.primaryScreen().geometry()
        x = (screen_geo.width() - self.splash.SPLASH_W) // 2
        y = (screen_geo.height() - self.splash.SPLASH_H) // 2
        self.splash.move(x, y)
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
            # 用进度条动画填充剩余时间（保持上一个消息，不提前显示"加载完成"）
            steps = int(remaining / 0.05)
            last_msg = tasks[-1][1] if tasks else "正在加载..."
            for i in range(steps):
                fill = 99 + int((i + 1) * 1 / steps)
                self.splash.set_progress(min(100, fill), last_msg)
                QApplication.processEvents()
                _time.sleep(0.05)

        self.splash.set_progress(100, "加载完成，正在启动...")
        QApplication.processEvents()
        _time.sleep(0.2)
