import math

from PyQt5.QtWidgets import QWidget, QSizePolicy
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
        STATE_IDLE: QColor(235, 240, 248),      # 柔和浅蓝灰
        STATE_START: QColor(59, 130, 246),      # 现代亮蓝
        STATE_TARGET: QColor(245, 158, 11),     # 琥珀橙
        STATE_OBSTACLE: QColor(30, 41, 59),     # 深石板色
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

    # 交互模式常量
    MODE_SD = "sd"          # 起点/终点设置模式
    MODE_OBSTACLE = "obstacle"  # 障碍物设置模式

    cell_changed = pyqtSignal(int, int, int)  # row, col, state

    # 信号：液滴配置变化（用于主窗口更新状态显示）
    droplet_config_changed = pyqtSignal()

    # 信号：交互模式变化
    mode_changed = pyqtSignal(str)  # "sd" 或 "obstacle"

    # 信号：撤销/重做状态变化
    undo_state_changed = pyqtSignal(bool, bool)  # can_undo, can_redo

    # 信号：途经点变化
    waypoint_changed = pyqtSignal(int, int, bool)  # row, col, added
    chip_test_cell_clicked = pyqtSignal(int, int)  # row, col （芯片测试模式点击网格）
    chip_test_enter_pressed = pyqtSignal()         # Enter 键标记通过

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
        self.border_radius = 1  # 圆角半径（学术风格，接近直角）

        # 显示的路径数据（用于路径可视化叠加）
        self.display_paths = []  # list[dict]: {'path': [(r,c),...], 'droplet_id': int, 'success': bool}

        # ============ 执行高亮 ============
        self.execution_highlight = None  # (row, col, droplet_id) 当前执行位置（逐个模式）
        self.sync_highlights = []  # [(row, col, droplet_id), ...] 同步模式多液滴高亮
        self.channel_test_highlight = None  # (row, col) 通道测试当前激活的电极

        # ============ 芯片测试模式 ============
        self.chip_test_active = False       # 芯片测试模式标志
        self.cell_test_results = {}         # cell_index -> 'pass'/'fail'

        # ============ 撤销/重做 ============
        self._undo_history = []             # 状态快照列表
        self._undo_index = -1               # 当前在历史中的位置

        # ============ 途经点（路径微调） ============
        self.waypoints = {}                 # droplet_id -> [(r,c), ...]
        self.chip_test_current = -1         # 当前正在测试的 cell_index (-1=无)

        # ============ 液滴配对数据 ============
        self.current_droplet_id = 1          # 当前正在设置的液滴编号
        self.droplet_starts = {}             # droplet_id -> (row, col)
        self.droplet_targets = {}            # droplet_id -> (row, col)

        # ============ 交互模式 ============
        self.mode = self.MODE_SD             # 默认：起点/终点设置模式

        self.setFocusPolicy(Qt.StrongFocus)  # 接收键盘事件
        self.setStyleSheet("background-color: transparent;")
        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 初始计算单元格大小
        self._recalc_cell_size()

    def set_droplet_id(self, droplet_id):
        """设置当前操作的液滴编号（由主窗口调用）。"""
        self.current_droplet_id = max(1, droplet_id)

    def cycle_cell_state(self, row, col, droplet_id=None, allow_obstacle=True):
        """循环切换单元格状态，并与液滴编号关联。
        
        点击顺序：Idle → Start(N) → Target(N) → (Obstacle →) Idle
        allow_obstacle=False 时在 Target 之后回到 Idle（跳过 Obstacle）。
        droplet_id: 仅由程序内部调用时传入，外部通过 set_droplet_id 设置。
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return

        did = droplet_id if droplet_id is not None else self.current_droplet_id
        current_state = self.grid[row][col]

        # 计算下一个状态
        if allow_obstacle:
            next_state = (current_state + 1) % 4
        else:
            # Idle(0) → Start(1) → Target(2) → Idle(0)，跳过 Obstacle(3)
            next_state = (current_state + 1) % 3

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
        """处理鼠标按下事件。根据当前交互模式执行不同操作。"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            cell = self._get_cell_from_pos(pos.x(), pos.y())
            if cell:
                # 保存快照用于撤销
                self.save_snapshot()
                row, col = cell

                # 芯片测试模式：点击电极即选中（不修改网格状态）
                if self.chip_test_active:
                    self.chip_test_cell_clicked.emit(row, col)
                    return

                if self.mode == self.MODE_OBSTACLE:
                    # 障碍物模式：Idle ↔ Obstacle 切换
                    if self.grid[row][col] == self.STATE_OBSTACLE:
                        self.grid[row][col] = self.STATE_IDLE
                    elif self.grid[row][col] == self.STATE_IDLE:
                        self.grid[row][col] = self.STATE_OBSTACLE
                    self.display_paths = []
                    self.cell_changed.emit(row, col, self.grid[row][col])
                    self.update()
                elif self.mode == self.MODE_SD:
                    # 智能模式：点空闲格自动设为起点/终点，点已设格取消
                    # 支持液滴融合：多个液滴可共享同一终点
                    did = self.current_droplet_id

                    # 点击自己的起点 → 取消
                    if did in self.droplet_starts and (row, col) == self.droplet_starts[did]:
                        del self.droplet_starts[did]
                        self.grid[row][col] = self.STATE_IDLE
                    # 点击自己的终点 → 取消
                    elif did in self.droplet_targets and (row, col) == self.droplet_targets[did]:
                        del self.droplet_targets[did]
                        # 检查是否有其他液滴也以此为目标，若无则恢复 Idle
                        other_targeting = any(
                            (r, c) == (row, col) for d, (r, c) in self.droplet_targets.items() if d != did
                        )
                        if not other_targeting:
                            self.grid[row][col] = self.STATE_IDLE
                    # 点击别人的起点 → 忽略
                    elif self.grid[row][col] == self.STATE_START:
                        return
                    # 点击别人的终点 → 融合：允许共享此终点
                    elif self.grid[row][col] == self.STATE_TARGET:
                        # 检查是否有液滴已以此为目标
                        existing = [d for d, (r, c) in self.droplet_targets.items()
                                    if (r, c) == (row, col) and d != did]
                        if existing:
                            # 已有其他液滴以此为目标——融合场景
                            if did in self.droplet_targets:
                                old_r, old_c = self.droplet_targets[did]
                                # 如果就目标不同且不被其他液滴使用，恢复空闲
                                if (old_r, old_c) != (row, col):
                                    other_on_old = any(
                                        (r, c) == (old_r, old_c) for d, (r, c) in self.droplet_targets.items() if d != did
                                    )
                                    if not other_on_old:
                                        self.grid[old_r][old_c] = self.STATE_IDLE
                            self.droplet_targets[did] = (row, col)
                            # 保持 TARGET 状态不变
                    # 空闲格子 → 自动设为起点或终点
                    elif self.grid[row][col] == self.STATE_IDLE:
                        if did not in self.droplet_starts:
                            # 还没有起点 → 设为起点
                            self.droplet_starts[did] = (row, col)
                            self.grid[row][col] = self.STATE_START
                        else:
                            # 已有起点 → 设为目标（覆盖旧目标）
                            if did in self.droplet_targets:
                                r, c = self.droplet_targets[did]
                                # 仅当其他液滴不使用该格子时才恢复 Idle
                                other_on_old = any(
                                    (rr, cc) == (r, c) for d2, (rr, cc) in self.droplet_targets.items() if d2 != did
                                )
                                if not other_on_old:
                                    self.grid[r][c] = self.STATE_IDLE
                                # 如果其他液滴也用此为目标，不改变网格状态
                            self.droplet_targets[did] = (row, col)
                            self.grid[row][col] = self.STATE_TARGET
                    self.display_paths = []
                    self.cell_changed.emit(row, col, self.grid[row][col])
                    self.droplet_config_changed.emit()
                    self.update()

        elif event.button() == Qt.RightButton:
            """右键：在当前液滴的路径上添加/移除途经点。"""
            pos = event.pos()
            cell = self._get_cell_from_pos(pos.x(), pos.y())
            if cell and self.display_paths:
                self.save_snapshot()
                row, col = cell
                # 只允许在空闲格子上设途经点
                if self.grid[row][col] == self.STATE_IDLE:
                    added = self.toggle_waypoint(row, col)
                    self.waypoint_changed.emit(row, col, added)
                    self.droplet_config_changed.emit()
                    self.update()

    def keyPressEvent(self, event):
        """键盘方向键 / WASD 在芯片测试模式下移动当前选中的电极。"""
        if not self.chip_test_active or self.chip_test_current < 0:
            super().keyPressEvent(event)
            return

        # 当前选中位置
        cur_row = self.chip_test_current // self.cols
        cur_col = self.chip_test_current % self.cols

        # Enter/Return → 标记通过
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.chip_test_enter_pressed.emit()
            return

        delta = None

        if event.key() in (Qt.Key_Up, Qt.Key_W):
            delta = (-1, 0)
        elif event.key() in (Qt.Key_Down, Qt.Key_S):
            delta = (1, 0)
        elif event.key() in (Qt.Key_Left, Qt.Key_A):
            delta = (0, -1)
        elif event.key() in (Qt.Key_Right, Qt.Key_D):
            delta = (0, 1)

        if delta is None:
            super().keyPressEvent(event)
            return

        dr, dc = delta
        new_row = cur_row + dr
        new_col = cur_col + dc

        # 边界检查
        if 0 <= new_row < self.rows and 0 <= new_col < self.cols:
            self.chip_test_cell_clicked.emit(new_row, new_col)

    def _build_cell_labels(self):
        """构建单元格标签映射：{(row, col): 'S1'|'T1,2'|...}
        
        支持液滴融合：同一终点上多个液滴显示为 T1,2,3
        """
        labels = {}
        for did, (r, c) in self.droplet_starts.items():
            labels[(r, c)] = f"S{did}"
        # 收集每个终点上的所有液滴编号
        target_groups = {}  # (r,c) -> [did1, did2, ...]
        for did, (r, c) in self.droplet_targets.items():
            if (r, c) not in target_groups:
                target_groups[(r, c)] = []
            target_groups[(r, c)].append(did)
        for (r, c), dids in target_groups.items():
            if len(dids) == 1:
                labels[(r, c)] = f"T{dids[0]}"
            elif len(dids) == 2:
                labels[(r, c)] = f"T{dids[0]},{dids[1]}"
            else:
                # 3 个及以上显示为 T1+2（表示 T1 和另外 2 个液滴）
                first = min(dids)
                rest = len(dids) - 1
                labels[(r, c)] = f"T{first}+{rest}"
        return labels

    def paintEvent(self, event):
        """绘制网格和所有单元格（带圆角、柔和边框、液滴标记），然后叠加路径。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 构建液滴标记映射
        cell_labels = self._build_cell_labels()

        # ============ 第一层：绘制网格单元格 ============
        # 收集路径覆盖的格子，用于避免坐标文字被半透明路径盖住后透出
        path_cells = set()
        for pd in self.display_paths:
            if pd.get('success', False):
                for coord in pd.get('path', []):
                    path_cells.add(tuple(coord))

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
                    border_color = QColor(208, 213, 221)
                else:
                    border_color = QColor(190, 195, 205)
                pen = QPen(border_color, self.border_width)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)

                # 如果是 Start/Target 且有液滴标记，显示 S{id}/T{id}/T1,2,3
                label = cell_labels.get((row, col))
                if label and state in (self.STATE_START, self.STATE_TARGET):
                    # 取第一个液滴编号来确定颜色（融合时用第一个液滴的颜色）
                    parts = label[1:].split(",")
                    try:
                        first_did = int(parts[0])
                    except ValueError:
                        first_did = 1
                    color_index = (first_did - 1) % len(self.PATH_BORDER_COLORS)
                    painter.setPen(self.PATH_BORDER_COLORS[color_index])
                    fs = max(10, self.cell_size // 5)
                    painter.setFont(QFont("Arial", fs, QFont.Bold))
                    painter.drawText(rect, Qt.AlignCenter, label)
                else:
                    # 如果该格子被路径覆盖，不再显示 (row,col) 防止半透明透出
                    in_path = (row, col) in path_cells
                    text = "" if in_path else (f"({row},{col})" if state != self.STATE_OBSTACLE else "")
                    text_color = QColor(255, 255, 255) if state == self.STATE_OBSTACLE else QColor(71, 85, 105)
                    painter.setPen(text_color)
                    fs = max(8, self.cell_size // 8)
                    painter.setFont(QFont("Arial", fs))
                    painter.drawText(rect, Qt.AlignCenter, text)

        # ============ 第二层：叠加绘制路径 ============
        if self.display_paths:
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

                    # 路径步骤编号（仅当 show_step_numbers 为 True 时显示）
                    if path_data.get('show_step_numbers', True):
                        painter.setPen(border_color)
                        fs = max(10, self.cell_size // 6)
                        font = QFont("Arial", fs, QFont.Bold)
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

        # ============ 第三层：执行高亮（当前激活的电极位置，整个填充） ============
        # 优先使用同步高亮列表（多液滴），否则使用单液滴高亮
        if self.sync_highlights:
            for sr, sc, sdid in self.sync_highlights:
                rect = self._get_cell_rect(sr, sc)
                rect_f = QRectF(rect)

                # 不透明绿色填充整个格子
                painter.setBrush(QColor(0, 200, 83, 255))
                painter.setPen(Qt.NoPen)
                hl_path = QPainterPath()
                hl_path.addRoundedRect(QRectF(rect_f.adjusted(-1, -1, 1, 1)),
                                       self.border_radius, self.border_radius)
                painter.drawPath(hl_path)

                # 深绿色边框
                highlight_pen = QPen(QColor(0, 150, 60), 3.0)
                highlight_pen.setCapStyle(Qt.RoundCap)
                highlight_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(highlight_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(hl_path)

                # 白色标注液滴编号
                painter.setPen(Qt.white)
                fs = max(16, self.cell_size // 3)
                painter.setFont(QFont("Arial", fs, QFont.Bold))
                painter.drawText(rect, Qt.AlignCenter, f"▶{sdid}")
        elif self.execution_highlight is not None:
            er, ec, edid = self.execution_highlight
            rect = self._get_cell_rect(er, ec)
            rect_f = QRectF(rect)

            # 不透明绿色填充整个格子
            painter.setBrush(QColor(0, 200, 83, 255))
            painter.setPen(Qt.NoPen)
            hl_path = QPainterPath()
            hl_path.addRoundedRect(QRectF(rect_f.adjusted(-1, -1, 1, 1)),
                                   self.border_radius, self.border_radius)
            painter.drawPath(hl_path)

            # 深绿色边框
            highlight_pen = QPen(QColor(0, 150, 60), 3.0)
            highlight_pen.setCapStyle(Qt.RoundCap)
            highlight_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(hl_path)

            # 白色标注液滴编号
            painter.setPen(Qt.white)
            fs = max(16, self.cell_size // 3)
            painter.setFont(QFont("Arial", fs, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, f"▶{edid}")

        # ============ 第 3.2 层：通道测试高亮（当前 ON 的测试电极） ============
        if self.channel_test_highlight is not None:
            tr, tc = self.channel_test_highlight
            rect = self._get_cell_rect(tr, tc)
            rect_f = QRectF(rect)

            # 绘制橙黄色粗边框
            test_pen = QPen(QColor(255, 160, 0), 4.0)
            test_pen.setCapStyle(Qt.RoundCap)
            test_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(test_pen)
            tp_path = QPainterPath()
            tp_path.addRoundedRect(QRectF(rect_f.adjusted(-1, -1, 1, 1)),
                                   self.border_radius, self.border_radius)
            painter.drawPath(tp_path)

            # 在角落标注 T 标记
            painter.setPen(QColor(255, 160, 0))
            fs = max(12, self.cell_size // 5)
            painter.setFont(QFont("Arial", fs, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, "T")

        # ============ 第 3.5 层：途经点标记（路径微调） ============
        if self.display_paths and any(self.waypoints.values()):
            for did, wps in self.waypoints.items():
                if not wps:
                    continue
                color_idx = (did - 1) % len(self.PATH_BORDER_COLORS)
                mark_color = self.PATH_BORDER_COLORS[color_idx]
                for r, c in wps:
                    rect = self._get_cell_rect(r, c)
                    # 菱形标记
                    cx, cy = rect.center().x(), rect.center().y()
                    hw, hh = 14, 14
                    diamond = QPainterPath()
                    diamond.moveTo(cx, cy - hh)
                    diamond.lineTo(cx + hw, cy)
                    diamond.lineTo(cx, cy + hh)
                    diamond.lineTo(cx - hw, cy)
                    diamond.closeSubpath()
                    painter.fillPath(diamond, QBrush(mark_color))
                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.drawLine(cx - 4, cy, cx + 4, cy)
                    painter.drawLine(cx, cy - 4, cx, cy + 4)

        # ============ 第四层：芯片测试模式叠加 ============
        if self.chip_test_active:
            for row in range(self.rows):
                for col in range(self.cols):
                    idx = row * self.cols + col
                    if idx not in self.cell_test_results:
                        continue
                    rect = self._get_cell_rect(row, col)
                    rect_f = QRectF(rect)
                    result = self.cell_test_results[idx]
                    if result == 'pass':
                        # 半透明绿色覆盖 + ✓
                        overlay = QColor(0, 180, 80, 50)
                        painter.fillRect(rect_f, overlay)
                        painter.setPen(QColor(0, 140, 60))
                        fs = max(14, self.cell_size // 4)
                        painter.setFont(QFont("Arial", fs, QFont.Bold))
                        painter.drawText(rect, Qt.AlignCenter, "✓")
                    elif result == 'fail':
                        # 半透明红色覆盖 + ✗
                        overlay = QColor(200, 40, 40, 50)
                        painter.fillRect(rect_f, overlay)
                        painter.setPen(QColor(180, 0, 0))
                        fs = max(14, self.cell_size // 4)
                        painter.setFont(QFont("Arial", fs, QFont.Bold))
                        painter.drawText(rect, Qt.AlignCenter, "✗")

            # 当前测试中的电极 — 蓝色脉冲边框
            if self.chip_test_current >= 0:
                cr = self.chip_test_current // self.cols
                cc = self.chip_test_current % self.cols
                if 0 <= cr < self.rows and 0 <= cc < self.cols:
                    rect = self._get_cell_rect(cr, cc)
                    rect_f = QRectF(rect)
                    test_pen = QPen(QColor(40, 100, 220), 4.0)
                    test_pen.setCapStyle(Qt.RoundCap)
                    test_pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(test_pen)
                    tp = QPainterPath()
                    tp.addRoundedRect(QRectF(rect_f.adjusted(-1, -1, 1, 1)),
                                      self.border_radius, self.border_radius)
                    painter.drawPath(tp)


    # ── 撤销/重做 ──────────────────────────────────

    def _grid_state(self):
        """返回当前网格状态的快照（用于撤销/重做）。"""
        return {
            'grid': [row[:] for row in self.grid],
            'starts': dict(self.droplet_starts),
            'targets': dict(self.droplet_targets),
            'waypoints': {d: list(wps) for d, wps in self.waypoints.items()},
            'paths': list(self.display_paths),
        }

    def _restore_grid_state(self, state):
        """从快照恢复网格状态。"""
        self.grid = [row[:] for row in state['grid']]
        self.droplet_starts = dict(state['starts'])
        self.droplet_targets = dict(state['targets'])
        self.waypoints = {int(d): list(wps) for d, wps in state['waypoints'].items()}
        self.display_paths = list(state['paths'])
        self.droplet_config_changed.emit()
        self.update()

    def save_snapshot(self):
        """保存当前状态快照（操作前调用）。"""
        # 丢弃当前位置之后的任何重做历史
        self._undo_history = self._undo_history[:self._undo_index + 1]
        state = self._grid_state()
        self._undo_history.append(state)
        # 限制历史深度
        if len(self._undo_history) > 100:
            self._undo_history.pop(0)
        self._undo_index = len(self._undo_history) - 1
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())

    def undo(self):
        """撤销上一步操作。返回 True 如果撤销成功。"""
        if self._undo_index <= 0:
            return False
        self._undo_index -= 1
        self._restore_grid_state(self._undo_history[self._undo_index])
        return True

    def redo(self):
        """重做被撤销的操作。返回 True 如果重做成功。"""
        if self._undo_index >= len(self._undo_history) - 1:
            return False
        self._undo_index += 1
        self._restore_grid_state(self._undo_history[self._undo_index])
        return True

    def can_undo(self):
        return self._undo_index > 0

    def can_redo(self):
        return self._undo_index < len(self._undo_history) - 1

    # ── 途经点（路径微调） ────────────────────────────

    def toggle_waypoint(self, row, col, droplet_id=None):
        """切换一个途经点标记。
        
        Args:
            row, col: 网格坐标
            droplet_id: 液滴编号，默认当前液滴
        """
        did = droplet_id if droplet_id is not None else self.current_droplet_id
        if did not in self.waypoints:
            self.waypoints[did] = []
        pos = (row, col)
        if pos in self.waypoints[did]:
            self.waypoints[did].remove(pos)
            return False  # 已移除
        else:
            self.waypoints[did].append(pos)
            return True   # 已添加

    def clear_waypoints(self, droplet_id=None):
        """清除途经点。"""
        if droplet_id is None:
            self.waypoints.clear()
        else:
            self.waypoints.pop(droplet_id, None)
        self.update()

    def has_waypoints(self, droplet_id=None):
        """检查是否有途经点。"""
        if droplet_id is None:
            return any(len(wps) > 0 for wps in self.waypoints.values())
        return bool(self.waypoints.get(droplet_id))

    def get_waypoints(self, droplet_id):
        """获取指定液滴的途经点列表。"""
        return list(self.waypoints.get(droplet_id, []))

    # ── 执行高亮 ──────────────────────────────────

    def set_execution_highlight(self, droplet_id, path, current_step):
        """设置执行高亮：标记当前执行到路径的哪一步。
        
        Args:
            droplet_id: 液滴编号
            path: 完整路径坐标列表
            current_step: 当前步索引（0-based）
        """
        if current_step < len(path):
            self.execution_highlight = (path[current_step][0], path[current_step][1], droplet_id)
        else:
            self.execution_highlight = None
        self.update()

    def clear_execution_highlight(self):
        """清除执行高亮。"""
        self.execution_highlight = None
        self.sync_highlights = []
        self.update()

    # ── 同步推进高亮 ─────────────────────────────────

    def set_sync_highlights(self, highlights):
        """设置同步推进高亮：多个液滴同时高亮。

        Args:
            highlights: list of (row, col, droplet_id)
        """
        self.sync_highlights = list(highlights)
        self.update()

    def clear_sync_highlights(self):
        """清除同步推进高亮。"""
        self.sync_highlights = []
        self.update()

    # ── 通道测试高亮 ──────────────────────────────────

    def set_channel_test_highlight(self, cell_index):
        """设置通道测试高亮：标记当前正在测试的电极。

        Args:
            cell_index: 电极编号 (0-based)，-1 清除高亮
        """
        if cell_index < 0:
            self.channel_test_highlight = None
        else:
            r = cell_index // self.cols
            c = cell_index % self.cols
            self.channel_test_highlight = (r, c)
        self.update()

    def clear_channel_test_highlight(self):
        """清除通道测试高亮。"""
        self.channel_test_highlight = None
        self.update()

    # ── 芯片测试模式 ──────────────────────────────────

    def set_chip_test_mode(self, active):
        """启用/禁用芯片测试模式。

        Args:
            active: True 进入测试模式，False 退出
        """
        self.chip_test_active = active
        if not active:
            self.chip_test_current = -1
            # 不清理 cell_test_results，留给外部按需清理（如 on_chip_test_start）
        self.update()

    def set_cell_test_result(self, index, result):
        """设置某个电极的测试结果。

        Args:
            index: 电极编号 (0-based)
            result: 'pass' 通过 | 'fail' 坏点 | None 清除
        """
        if result is None:
            self.cell_test_results.pop(index, None)
        else:
            self.cell_test_results[index] = result
        self.update()

    def clear_test_results(self):
        """清除所有测试结果。"""
        self.cell_test_results.clear()
        self.chip_test_current = -1
        self.update()

    def set_chip_test_current(self, index):
        """设置当前正在测试的电极编号。

        Args:
            index: 电极编号 (0-based)，-1 表示无
        """
        self.chip_test_current = index
        self.update()

    def get_test_summary(self):
        """获取测试结果统计。

        Returns:
            (pass_count, fail_count, fail_list)
        """
        pass_c = sum(1 for v in self.cell_test_results.values() if v == 'pass')
        fail_c = sum(1 for v in self.cell_test_results.values() if v == 'fail')
        fail_list = sorted(i for i, v in self.cell_test_results.items() if v == 'fail')
        return pass_c, fail_c, fail_list

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

    def rebuild_grid(self, rows, cols):
        """重建网格为指定尺寸，所有数据重置。"""
        self.rows = rows
        self.cols = cols
        self.grid = [[self.STATE_IDLE] * cols for _ in range(rows)]
        self.display_paths = []
        self.droplet_starts.clear()
        self.droplet_targets.clear()
        self.execution_highlight = None
        self.sync_highlights = []
        self.channel_test_highlight = None
        self.chip_test_active = False
        self.cell_test_results.clear()
        self.chip_test_current = -1
        self.waypoints.clear()
        self._undo_history.clear()
        self._undo_index = -1
        self._recalc_cell_size()
        self.droplet_config_changed.emit()
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())
        self.update()

    def _recalc_cell_size(self):
        """根据当前小部件尺寸重新计算单元格大小。"""
        w = self.width()
        h = self.height()
        margin = 12
        gap = 8
        # 按宽度和高度分别计算，取较小值确保完整显示
        cell_by_w = (w - 2 * margin - (self.cols - 1) * gap) // self.cols
        cell_by_h = (h - 2 * margin - (self.rows - 1) * gap) // self.rows
        self.cell_size = max(30, min(cell_by_w, cell_by_h))
        self.cell_margin = max(2, self.cell_size // 14)

    def resizeEvent(self, event):
        """窗口大小变化时重新计算单元格尺寸并重绘。"""
        self._recalc_cell_size()
        self.update()
        super().resizeEvent(event)

    def reset_grid(self):
        """重置所有单元格为 Idle 状态，清除路径显示和液滴配对。"""
        self.display_paths = []
        self.droplet_starts.clear()
        self.droplet_targets.clear()
        self.waypoints.clear()
        for row in range(self.rows):
            for col in range(self.cols):
                self.grid[row][col] = self.STATE_IDLE
        self.droplet_config_changed.emit()
        self.update()

    def set_mode(self, mode):
        """设置交互模式。
        
        Args:
            mode: 'sd' — 起点/终点设置模式，'obstacle' — 障碍物设置模式
        """
        if mode not in (self.MODE_SD, self.MODE_OBSTACLE):
            return
        self.mode = mode
        self.mode_changed.emit(mode)

    def clear_state(self, state):
        """清除指定状态的所有单元格，同时清除路径显示。"""
        self.save_snapshot()
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
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())
        self.update()

    def clear_droplet(self, droplet_id):
        """清除指定液滴的起点和终点，保留障碍物和其他液滴。"""
        self.save_snapshot()
        self.display_paths = []
        if droplet_id in self.droplet_starts:
            r, c = self.droplet_starts.pop(droplet_id)
            self.grid[r][c] = self.STATE_IDLE
        if droplet_id in self.droplet_targets:
            r, c = self.droplet_targets.pop(droplet_id)
            self.grid[r][c] = self.STATE_IDLE
        self.droplet_config_changed.emit()
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())
        self.update()

    def clear_all_droplets(self):
        """清除所有液滴的起点/终点配置，同时清除路径显示。"""
        self.save_snapshot()
        self.display_paths = []
        # 清除所有起点和终点的格子
        for did, (r, c) in list(self.droplet_starts.items()):
            self.grid[r][c] = self.STATE_IDLE
        for did, (r, c) in list(self.droplet_targets.items()):
            self.grid[r][c] = self.STATE_IDLE
        self.droplet_starts.clear()
        self.droplet_targets.clear()
        self.droplet_config_changed.emit()
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())
        self.update()
