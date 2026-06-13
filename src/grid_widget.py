import math

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, QRectF, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QBrush
from . import global_cfg


class ElectrodeGrid(QWidget):
    """电极网格小部件。
    
    显示 ELECTRODE_ROWS × ELECTRODE_COLS 的网格。
    每个单元格有 4 种状态：Idle、Start、Target、Obstacle。
    左键点击循环切换单元格状态。
    支持多液滴路径的彩色叠加显示。
    
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

    # 路径颜色调色板（半透明，用于叠加显示多条路径）
    PATH_COLORS = [
        QColor(59, 120, 255, 110),    # 亮蓝
        QColor(255, 87, 34, 110),     # 朱红
        QColor(76, 175, 80, 110),     # 翠绿
        QColor(156, 39, 176, 110),    # 紫色
        QColor(255, 179, 32, 110),    # 橙黄
        QColor(0, 188, 212, 110),     # 青色
        QColor(233, 30, 99, 110),     # 粉红
        QColor(63, 81, 181, 110),     # 靛蓝
    ]

    # 路径边框颜色（不透明，用于边框和文字）
    PATH_BORDER_COLORS = [
        QColor(33, 93, 214),
        QColor(211, 57, 14),
        QColor(46, 135, 50),
        QColor(116, 19, 136),
        QColor(214, 139, 12),
        QColor(0, 148, 172),
        QColor(193, 10, 59),
        QColor(33, 51, 141),
    ]

    cell_changed = pyqtSignal(int, int, int)  # row, col, state

    # 信号：液滴配置变化（用于主窗口更新状态显示）
    droplet_config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = global_cfg.ELECTRODE_ROWS
        self.cols = global_cfg.ELECTRODE_COLS

        # 初始化所有单元格为 Idle 状态
        self.grid = [[self.STATE_IDLE for _ in range(self.cols)] for _ in range(self.rows)]

        # 单元格大小和间距（可调整）
        self.cell_size = 110
        self.cell_margin = 8
        self.border_width = 1.5
        self.border_radius = 10  # 圆角半径

        # 显示的路径数据（用于路径可视化叠加）
        self.display_paths = []  # list[dict]: {'path': [(r,c),...], 'droplet_id': int, 'success': bool}

        # ============ 液滴配对数据 ============
        self.current_droplet_id = 1          # 当前正在设置的液滴编号
        self.droplet_starts = {}             # droplet_id -> (row, col)
        self.droplet_targets = {}            # droplet_id -> (row, col)

        # 设置最小尺寸
        self.setMinimumSize(968, 732)
        self.setStyleSheet("background-color: transparent;")

    def set_droplet_id(self, droplet_id):
        """设置当前操作的液滴编号（由主窗口调用）。"""
        self.current_droplet_id = max(1, droplet_id)

    def cycle_cell_state(self, row, col, droplet_id=None):
        """循环切换单元格状态，并与液滴编号关联。
        
        点击顺序：Idle → Start(N) → Target(N) → Obstacle → Idle
        droplet_id: 仅由程序内部调用时传入，外部通过 set_droplet_id 设置。
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return

        did = droplet_id if droplet_id is not None else self.current_droplet_id
        current_state = self.grid[row][col]
        next_state = (current_state + 1) % 4

        # 如果当前是 Start/Target，从 droplet 字典中移除
        if current_state == self.STATE_START:
            for d, pos in list(self.droplet_starts.items()):
                if pos == (row, col):
                    del self.droplet_starts[d]
        elif current_state == self.STATE_TARGET:
            for d, pos in list(self.droplet_targets.items()):
                if pos == (row, col):
                    del self.droplet_targets[d]

        # 如果新状态是 Start/Target，关联到当前液滴
        if next_state == self.STATE_START:
            # 该液滴已有起点则清除旧位置
            if did in self.droplet_starts:
                old_r, old_c = self.droplet_starts[did]
                self.grid[old_r][old_c] = self.STATE_IDLE
            self.droplet_starts[did] = (row, col)
        elif next_state == self.STATE_TARGET:
            if did in self.droplet_targets:
                old_r, old_c = self.droplet_targets[did]
                self.grid[old_r][old_c] = self.STATE_IDLE
            self.droplet_targets[did] = (row, col)

        self.grid[row][col] = next_state
        self.display_paths = []
        self.cell_changed.emit(row, col, next_state)
        self.droplet_config_changed.emit()
        self.update()

    def get_cell_state(self, row, col):
        """获取指定单元格的状态。"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return None

    def get_droplet_pairs(self):
        """返回所有已配对的液滴路径规划数据。
        
        Returns:
            list[tuple]: [(start_pos, target_pos, droplet_id), ...]
            只返回同时设置了起点和终点的液滴。
        """
        pairs = []
        for did in sorted(self.droplet_starts.keys()):
            if did in self.droplet_targets:
                pairs.append((self.droplet_starts[did], self.droplet_targets[did], did))
        return pairs

    def get_droplet_start(self, droplet_id):
        """获取指定液滴的起点坐标，未设置则返回 None。"""
        return self.droplet_starts.get(droplet_id, None)

    def get_droplet_target(self, droplet_id):
        """获取指定液滴的目标坐标，未设置则返回 None。"""
        return self.droplet_targets.get(droplet_id, None)

    def get_obstacle_points(self):
        """返回所有 Obstacle 状态的单元格坐标列表 [(row, col), ...]。"""
        return [(r, c) for r in range(self.rows) for c in range(self.cols)
                if self.grid[r][c] == self.STATE_OBSTACLE]

    def get_active_droplet_ids(self):
        """返回有配置（起点或终点）的液滴编号列表。"""
        ids = set(self.droplet_starts.keys()) | set(self.droplet_targets.keys())
        return sorted(ids)

    @staticmethod
    def coord_to_index(row, col):
        """将坐标 (row, col) 转换为硬件索引（0-based）。
        
        公式：index = row * cols + col
        映射到 Arduino 继电器编号 0-47（S1-S48）。
        这里 cols 从 global_cfg 中获取。
        """
        return row * global_cfg.ELECTRODE_COLS + col

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
        """处理鼠标按下事件。左键点击循环切换单元格状态（关联当前液滴编号）。"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            cell = self._get_cell_from_pos(pos.x(), pos.y())
            if cell:
                row, col = cell
                self.cycle_cell_state(row, col, droplet_id=self.current_droplet_id)

    def _build_cell_labels(self):
        """构建单元格标签映射：{(row, col): 'S1'|'T2'|...}"""
        labels = {}
        for did, (r, c) in self.droplet_starts.items():
            labels[(r, c)] = f"S{did}"
        for did, (r, c) in self.droplet_targets.items():
            labels[(r, c)] = f"T{did}"
        return labels

    def paintEvent(self, event):
        """绘制网格和所有单元格（带圆角、柔和边框、液滴标记），然后叠加路径。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 构建液滴标记映射
        cell_labels = self._build_cell_labels()

        # ============ 第一层：绘制网格单元格 ============
        for row in range(self.rows):
            for col in range(self.cols):
                rect = self._get_cell_rect(row, col)
                rect_f = QRectF(rect)
                state = self.grid[row][col]
                color = self.STATE_COLORS[state]

                # 创建圆角路径
                path = QPainterPath()
                path.addRoundedRect(rect_f, self.border_radius, self.border_radius)

                # 绘制填充
                painter.fillPath(path, color)

                # 绘制边框
                if state == self.STATE_IDLE:
                    border_color = QColor(215, 215, 215)
                else:
                    border_color = QColor(200, 200, 200)
                pen = QPen(border_color, self.border_width)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)

                # 如果是 Start/Target 且有液滴标记，显示 S{id}/T{id}
                label = cell_labels.get((row, col))
                if label and state in (self.STATE_START, self.STATE_TARGET):
                    did = int(label[1:])
                    color_index = (did - 1) % len(self.PATH_BORDER_COLORS)
                    painter.setPen(self.PATH_BORDER_COLORS[color_index])
                    painter.setFont(QFont("Arial", 22, QFont.Bold))
                    painter.drawText(rect, Qt.AlignCenter, label)
                else:
                    text = f"({row},{col})" if state != self.STATE_OBSTACLE else ""
                    text_color = QColor(255, 255, 255) if state == self.STATE_OBSTACLE else QColor(70, 70, 70)
                    painter.setPen(text_color)
                    painter.setFont(QFont("Arial", 14))
                    painter.drawText(rect, Qt.AlignCenter, text)

        # ============ 第二层：叠加绘制路径 ============
        if not self.display_paths:
            return

        for path_data in self.display_paths:
            path_coords = path_data.get('path', [])
            if not path_coords or not path_data.get('success', False):
                continue

            droplet_id = path_data.get('droplet_id', 1)
            color_index = (droplet_id - 1) % len(self.PATH_COLORS)
            overlay_color = self.PATH_COLORS[color_index]
            border_color = self.PATH_BORDER_COLORS[color_index]

            # 绘制路径单元格（半透明叠加）
            for step, (row, col) in enumerate(path_coords):
                rect = self._get_cell_rect(row, col)
                rect_f = QRectF(rect)

                cell_path = QPainterPath()
                cell_path.addRoundedRect(rect_f, self.border_radius, self.border_radius)

                # 半透明填充
                painter.fillPath(cell_path, overlay_color)

                # 路径边框（带颜色，加粗）
                pen = QPen(border_color, 3.0)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(cell_path)

                # 路径步骤编号
                painter.setPen(border_color)
                font = QFont("Arial", 18, QFont.Bold)
                painter.setFont(font)
                step_text = str(step + 1)

                # 特殊标记：起点 S / 目标 T
                if step == 0:
                    marker = f"S{droplet_id}"
                elif step == len(path_coords) - 1:
                    marker = f"T{droplet_id}"
                else:
                    marker = step_text

                painter.drawText(rect, Qt.AlignCenter, marker)

            # 绘制路径连线（相邻单元格之间的箭头）
            painter.setPen(QPen(border_color, 3, Qt.SolidLine))
            for i in range(len(path_coords) - 1):
                r1, c1 = path_coords[i]
                r2, c2 = path_coords[i + 1]
                rect1 = self._get_cell_rect(r1, c1)
                rect2 = self._get_cell_rect(r2, c2)

                # 从当前单元格中心到下一个单元格中心
                x1 = rect1.center().x()
                y1 = rect1.center().y()
                x2 = rect2.center().x()
                y2 = rect2.center().y()

                # 缩进一点（从边缘而不是中心），避免覆盖文字
                margin = self.cell_size // 2 - 8
                dx = x2 - x1
                dy = y2 - y1
                length = (dx ** 2 + dy ** 2) ** 0.5
                if length > 0:
                    x1 = x1 + dx / length * (self.cell_size // 2 - margin)
                    y1 = y1 + dy / length * (self.cell_size // 2 - margin)
                    x2 = x2 - dx / length * (self.cell_size // 2 - margin)
                    y2 = y2 - dy / length * (self.cell_size // 2 - margin)

                # 画连线
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

                # 画箭头（在连线中点附近）
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                arrow_size = 10
                angle = math.atan2(dy, dx)

                # 箭头三角形
                arrow_p1 = (mid_x, mid_y)
                arrow_p2 = (mid_x - arrow_size * math.cos(angle - 0.5),
                            mid_y - arrow_size * math.sin(angle - 0.5))
                arrow_p3 = (mid_x - arrow_size * math.cos(angle + 0.5),
                            mid_y - arrow_size * math.sin(angle + 0.5))

                arrow_path = QPainterPath()
                arrow_path.moveTo(arrow_p1[0], arrow_p1[1])
                arrow_path.lineTo(arrow_p2[0], arrow_p2[1])
                arrow_path.lineTo(arrow_p3[0], arrow_p3[1])
                arrow_path.closeSubpath()
                painter.fillPath(arrow_path, QBrush(border_color))

    def set_paths(self, paths_data):
        """设置要叠加显示的路径。
        
        Args:
            paths_data: list[dict]，每个元素需包含:
                - 'path': [(row, col), ...] 路径坐标
                - 'droplet_id': int 液滴编号（用于选择颜色）
                - 'success': bool 是否成功
        """
        self.display_paths = paths_data
        self.update()

    def clear_paths(self):
        """清除所有显示的路径。"""
        self.display_paths = []
        self.update()

    def reset_grid(self):
        """重置所有单元格为 Idle 状态，清除路径显示和液滴配对。"""
        self.display_paths = []
        self.droplet_starts.clear()
        self.droplet_targets.clear()
        for row in range(self.rows):
            for col in range(self.cols):
                self.grid[row][col] = self.STATE_IDLE
        self.droplet_config_changed.emit()
        self.update()

    def clear_state(self, state):
        """清除指定状态的所有单元格，同时清除路径显示。"""
        self.display_paths = []
        # 如果清除 Start，从 droplet_starts 移除对应条目
        if state == self.STATE_START:
            self.droplet_starts.clear()
        # 如果清除 Target，从 droplet_targets 移除对应条目
        if state == self.STATE_TARGET:
            self.droplet_targets.clear()
        for row in range(self.rows):
            for col in range(self.cols):
                if self.grid[row][col] == state:
                    self.grid[row][col] = self.STATE_IDLE
        self.droplet_config_changed.emit()
        self.update()
