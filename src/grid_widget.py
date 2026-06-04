from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, QRectF, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from . import global_cfg


class ElectrodeGrid(QWidget):
    """电极网格小部件。
    
    显示 ELECTRODE_ROWS × ELECTRODE_COLS 的网格。
    每个单元格有 4 种状态：Idle、Start、Target、Obstacle。
    左键点击循环切换单元格状态。
    
    Signals:
    - cell_changed(row, col, state): 单元格状态改变时发出（state: 0=Idle, 1=Start, 2=Target, 3=Obstacle）
    """

    # 状态常数
    STATE_IDLE = 0
    STATE_START = 1
    STATE_TARGET = 2
    STATE_OBSTACLE = 3

    # 状态名称和颜色
    STATE_NAMES = {
        STATE_IDLE: "Idle",
        STATE_START: "Start",
        STATE_TARGET: "Target",
        STATE_OBSTACLE: "Obstacle",
    }

    STATE_COLORS = {
        STATE_IDLE: QColor(235, 235, 235),      # 柔和浅灭
        STATE_START: QColor(59, 120, 255),      # 现代轩蓝
        STATE_TARGET: QColor(255, 179, 32),     # 流畜橙
        STATE_OBSTACLE: QColor(38, 38, 38),     # 深阅
    }

    cell_changed = pyqtSignal(int, int, int)  # row, col, state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = global_cfg.ELECTRODE_ROWS
        self.cols = global_cfg.ELECTRODE_COLS

        # 初始化所有单元格为 Idle 状态
        self.grid = [[self.STATE_IDLE for _ in range(self.cols)] for _ in range(self.rows)]

        # 单元格大小和间距（可调整）
        self.cell_size = 48
        self.cell_margin = 4
        self.border_width = 0.8
        self.border_radius = 5  # 圆角半径

        # 设置最小尺寸
        self.setMinimumSize(
            self.cols * (self.cell_size + self.cell_margin) + 24,
            self.rows * (self.cell_size + self.cell_margin) + 24
        )
        self.setStyleSheet("background-color: #fafafa;")

    def set_cell_state(self, row, col, state):
        """设置指定单元格的状态。"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if state not in [self.STATE_IDLE, self.STATE_START, self.STATE_TARGET, self.STATE_OBSTACLE]:
                return
            self.grid[row][col] = state
            self.cell_changed.emit(row, col, state)
            self.update()

    def get_cell_state(self, row, col):
        """获取指定单元格的状态。"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return None

    def cycle_cell_state(self, row, col):
        """循环切换单元格状态（Idle → Start → Target → Obstacle → Idle）。"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            current_state = self.grid[row][col]
            next_state = (current_state + 1) % 4
            self.set_cell_state(row, col, next_state)

    def get_start_points(self):
        """返回所有 Start 状态的单元格坐标列表 [(row, col), ...]。"""
        return [(r, c) for r in range(self.rows) for c in range(self.cols)
                if self.grid[r][c] == self.STATE_START]

    def get_target_points(self):
        """返回所有 Target 状态的单元格坐标列表 [(row, col), ...]。"""
        return [(r, c) for r in range(self.rows) for c in range(self.cols)
                if self.grid[r][c] == self.STATE_TARGET]

    def get_obstacle_points(self):
        """返回所有 Obstacle 状态的单元格坐标列表 [(row, col), ...]。"""
        return [(r, c) for r in range(self.rows) for c in range(self.cols)
                if self.grid[r][c] == self.STATE_OBSTACLE]

    @staticmethod
    def coord_to_index(row, col):
        """将坐标 (row, col) 转换为硬件索引。
        
        公式：index = row * cols + 1
        这里 cols 从 global_cfg 中获取。
        """
        return row * global_cfg.ELECTRODE_COLS + 1

    def _get_cell_rect(self, row, col):
        """获取单元格的绘制矩形。"""
        x = col * (self.cell_size + self.cell_margin) + 12
        y = row * (self.cell_size + self.cell_margin) + 12
        return QRect(x, y, self.cell_size, self.cell_size)

    def _get_cell_from_pos(self, x, y):
        """根据鼠标位置获取单元格坐标 (row, col)，如不在任何单元格内则返回 None。"""
        for row in range(self.rows):
            for col in range(self.cols):
                rect = self._get_cell_rect(row, col)
                if rect.contains(x, y):
                    return (row, col)
        return None

    def mousePressEvent(self, event):
        """处理鼠标按下事件。左键点击循环切换单元格状态。"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            cell = self._get_cell_from_pos(pos.x(), pos.y())
            if cell:
                row, col = cell
                self.cycle_cell_state(row, col)

    def paintEvent(self, event):
        """绘制网格和所有单元格（带圆角、柔和边框、无文字）。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        for row in range(self.rows):
            for col in range(self.cols):
                rect = self._get_cell_rect(row, col)
                rect_f = QRectF(rect)  # 转换为 QRectF
                state = self.grid[row][col]
                color = self.STATE_COLORS[state]

                # 创建圆角路径
                path = QPainterPath()
                path.addRoundedRect(rect_f, self.border_radius, self.border_radius)

                # 绘制填充矩形（带圆角，流畜优雅）
                painter.fillPath(path, color)

                # 绘制边框（置灰色、细缩小）
                if state == self.STATE_IDLE:
                    border_color = QColor(215, 215, 215)  # 浅置灰
                else:
                    border_color = QColor(200, 200, 200)  # 稍深的置灰
                pen = QPen(border_color, self.border_width)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)

    def reset_grid(self):
        """重置所有单元格为 Idle 状态。"""
        for row in range(self.rows):
            for col in range(self.cols):
                self.grid[row][col] = self.STATE_IDLE
        self.update()

    def clear_state(self, state):
        """清除指定状态的所有单元格。"""
        for row in range(self.rows):
            for col in range(self.cols):
                if self.grid[row][col] == state:
                    self.grid[row][col] = self.STATE_IDLE
        self.update()
