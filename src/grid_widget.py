from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
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
        STATE_IDLE: QColor(200, 200, 200),      # 浅灰
        STATE_START: QColor(0, 0, 255),         # 蓝色
        STATE_TARGET: QColor(255, 165, 0),      # 橙色
        STATE_OBSTACLE: QColor(0, 0, 0),        # 黑色
    }

    cell_changed = pyqtSignal(int, int, int)  # row, col, state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = global_cfg.ELECTRODE_ROWS
        self.cols = global_cfg.ELECTRODE_COLS

        # 初始化所有单元格为 Idle 状态
        self.grid = [[self.STATE_IDLE for _ in range(self.cols)] for _ in range(self.rows)]

        # 单元格大小和间距（可调整）
        self.cell_size = 40
        self.cell_margin = 2
        self.border_width = 1

        # 设置最小尺寸
        self.setMinimumSize(
            self.cols * (self.cell_size + self.cell_margin) + 20,
            self.rows * (self.cell_size + self.cell_margin) + 20
        )

        # 字体
        self.font = QFont("Arial", 8)

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
        x = col * (self.cell_size + self.cell_margin) + 10
        y = row * (self.cell_size + self.cell_margin) + 10
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
        """绘制网格和所有单元格。"""
        painter = QPainter(self)
        painter.setFont(self.font)

        for row in range(self.rows):
            for col in range(self.cols):
                rect = self._get_cell_rect(row, col)
                state = self.grid[row][col]
                color = self.STATE_COLORS[state]

                # 绘制填充矩形
                painter.fillRect(rect, color)

                # 绘制边框
                pen = QPen(QColor(0, 0, 0), self.border_width)
                painter.setPen(pen)
                painter.drawRect(rect)

                # 绘制坐标标签（可选）
                text = f"({row},{col})"
                text_color = QColor(255, 255, 255) if state == self.STATE_OBSTACLE else QColor(0, 0, 0)
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignCenter, text)

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
