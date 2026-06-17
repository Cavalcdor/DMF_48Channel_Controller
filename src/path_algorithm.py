"""
寻路算法模块 - DMF 电极控制

提供 A* 最短路径搜索功能，用于在电极网格上规划路径。
采用曼哈顿距离作为启发式函数，比 BFS 搜索效率更高。
"""

import heapq
from . import global_cfg


def a_star_shortest_path(start, target, obstacles=None, cell_costs=None):
    """使用 A* 算法找到从起点到目标的最短路径。
    
    采用曼哈顿距离启发式函数，完全匹配四方向移动约束。
    支持 cell_costs 为特定格子增加移动代价，用于绕开已测点。
    
    Args:
        start: 起点 (row, col)
        target: 目标点 (row, col)
        obstacles: 障碍物集合，例如 {(1, 2), (3, 4)} 或 None
        cell_costs: 格子额外代价字典 {(row, col): extra_cost}，默认 None。
                    代价越高的格子路径越倾向于避开。
        
    Returns:
        path: 路径坐标列表 [(row0, col0), (row1, col1), ...] 包括起点和终点。
        如果没有路径，返回空列表 []。
    """
    if obstacles is None:
        obstacles = set()
    else:
        obstacles = set(obstacles)
    if cell_costs is None:
        cell_costs = {}

    rows = global_cfg.ELECTRODE_ROWS
    cols = global_cfg.ELECTRODE_COLS

    # 边界检查
    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return []
    if not (0 <= target[0] < rows and 0 <= target[1] < cols):
        return []

    # 起点或目标在障碍物上
    if start in obstacles or target in obstacles:
        return []

    # 起点等于目标
    if start == target:
        return [start]

    def heuristic(a, b):
        """曼哈顿距离启发式函数。"""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # 4 方向移动（上、下、左、右）
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    # A* 主循环
    open_set = [(0, start)]
    g_score = {start: 0}
    parent = {start: None}
    visited = {start}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == target:
            # 重构路径
            path = []
            node = target
            while node is not None:
                path.append(node)
                node = parent[node]
            return path[::-1]  # 反转得到从起点到终点的路径

        for dr, dc in directions:
            next_row = current[0] + dr
            next_col = current[1] + dc
            neighbor = (next_row, next_col)

            # 检查边界
            if not (0 <= next_row < rows and 0 <= next_col < cols):
                continue

            # 检查是否已访问或是障碍物
            if neighbor in visited or neighbor in obstacles:
                continue

            # 基础移动代价1 + 额外代价（已测点增加权重，让路径绕开）
            extra = cell_costs.get(neighbor, 0)
            tentative_g = g_score[current] + 1 + extra

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, target)
                visited.add(neighbor)
                heapq.heappush(open_set, (f_score, neighbor))

    # 没有找到路径
    return []


def path_to_indices(path):
    """将路径坐标序列转换为硬件电极索引序列（0-based）。
    
    Args:
        path: 路径坐标列表 [(row, col), ...]
        
    Returns:
        indices: 硬件电极索引列表 [idx0, idx1, ...]
        索引公式：index = row * ELECTRODE_COLS + col
        映射到 Arduino 继电器编号 0-47（S1-S48）。
    """
    if not path:
        return []

    indices = []
    cols = global_cfg.ELECTRODE_COLS

    for row, col in path:
        index = row * cols + col
        indices.append(index)

    return indices


def find_path_avoiding_obstacles(start, target, obstacles=None):
    """高级寻路函数，返回完整的路径信息。
    
    Args:
        start: 起点 (row, col)
        target: 目标点 (row, col)
        obstacles: 障碍物集合
        
    Returns:
        dict 包含：
        - 'path': 坐标路径列表
        - 'indices': 硬件索引列表
        - 'length': 路径长度（单元格数）
        - 'valid': 是否找到有效路径
    """
    path = a_star_shortest_path(start, target, obstacles)

    return {
        'path': path,
        'indices': path_to_indices(path),
        'length': len(path),
        'valid': len(path) > 0,
    }


def plan_multiple_paths(pairs, obstacles=None, sort_by_length=True):
    """规划多条互不干扰的液滴路径。
    
    使用贪心策略：按最短路径长度排序，依次规划路径，
    每条路径占用的电极会被标记为不可用，避免后续路径干扰。
    
    Args:
        pairs: 列表，每个元素为 (start, target)，start 和 target 均为 (row, col)
        obstacles: 障碍物集合，可选
        sort_by_length: 是否按预期距离排序（短路径优先），默认 True
        
    Returns:
        list[dict]: 每个元素包含：
            - 'start': 起点 (row, col)
            - 'target': 目标点 (row, col)
            - 'path': 坐标路径列表 [(row, col), ...]，失败则为 []
            - 'indices': 硬件索引列表，失败则为 []
            - 'success': bool 是否找到路径
            - 'droplet_id': int 液滴编号（从 1 开始）
    """
    if obstacles is None:
        obstacles = set()
    else:
        obstacles = set(obstacles)

    used_cells = set(obstacles)
    # 收集所有终点（支持融合场景：终点可被多个液滴共享）
    all_targets = {target for _, target in pairs}
    # 起点也不能互相占用
    all_starts = {start for start, _ in pairs}
    # 检测共享终点（融合液滴）
    target_counts = {}
    for _, tgt in pairs:
        target_counts[tgt] = target_counts.get(tgt, 0) + 1
    fusion_targets = {t for t, c in target_counts.items() if c > 1}

    results = []

    # 按曼哈顿距离排序（短路径优先），提高整体成功率
    indexed_pairs = list(enumerate(pairs))  # (original_index, (start, target))
    if sort_by_length and len(indexed_pairs) > 1:
        indexed_pairs.sort(key=lambda x: abs(x[1][0][0] - x[1][1][0]) + abs(x[1][0][1] - x[1][1][1]))
    else:
        # 保持原始顺序作为 droplet_id
        pass

    for droplet_id, (start, target) in indexed_pairs:
        path = a_star_shortest_path(start, target, used_cells)

        if path:
            if target in fusion_targets:
                # 融合（共享终点）：不标记中间格子，让所有液滴都可到达
                # 只阻挡其他液滴的起点
                for cell in path:
                    if cell in all_starts and cell != target:
                        used_cells.add(cell)
            else:
                # 非融合：标记路径为已占用，排除其他液滴的终点（融合支持）
                for cell in path:
                    if cell in all_targets and cell != start:
                        continue
                    if cell in all_starts and cell != target:
                        continue
                    used_cells.add(cell)
            results.append({
                'droplet_id': droplet_id + 1,
                'start': start,
                'target': target,
                'path': path,
                'indices': path_to_indices(path),
                'success': True,
            })
        else:
            # 诊断失败原因
            reason = "无可达路径"
            if start in obstacles:
                reason = "起点被障碍物阻挡"
            elif target in obstacles:
                reason = "终点被障碍物阻挡"
            elif start == target:
                reason = "起点等于终点"
            else:
                # 检查路径是否被其他液滴路径阻挡
                other_cells = used_cells - obstacles
                if other_cells:
                    # 简单试探：去掉其他路径占用再试一次
                    test_path = a_star_shortest_path(start, target, obstacles)
                    if test_path:
                        reason = "路径被其他液滴占用"
            results.append({
                'droplet_id': droplet_id + 1,
                'start': start,
                'target': target,
                'path': [],
                'indices': [],
                'success': False,
                'fail_reason': reason,
            })

    # 按原始 droplet_id 排序恢复顺序
    results.sort(key=lambda x: x['droplet_id'])
    return results


def multi_target_pathfinding(start, targets, obstacles=None):
    """从单个起点到多个目标点寻路（找最近的目标）。
    
    Args:
        start: 起点 (row, col)
        targets: 目标点列表 [(row, col), ...]
        obstacles: 障碍物集合
        
    Returns:
        dict 包含：
        - 'nearest_target': 最近目标的坐标，如无可达目标则为 None
        - 'path': 到最近目标的路径
        - 'indices': 到最近目标的硬件索引
        - 'distance': 到最近目标的距离，如无可达目标则为 float('inf')
        - 'all_paths': 所有可达目标的路径信息字典
    """
    if obstacles is None:
        obstacles = set()

    nearest_target = None
    nearest_path = []
    min_distance = float('inf')
    all_paths = {}

    for target in targets:
        path = a_star_shortest_path(start, target, obstacles)
        if path:
            distance = len(path) - 1  # 边数 = 单元格数 - 1
            all_paths[target] = {
                'path': path,
                'indices': path_to_indices(path),
                'distance': distance,
            }
            if distance < min_distance:
                min_distance = distance
                nearest_target = target
                nearest_path = path

    return {
        'nearest_target': nearest_target,
        'path': nearest_path,
        'indices': path_to_indices(nearest_path),
        'distance': min_distance if min_distance != float('inf') else None,
        'all_paths': all_paths,
    }


def generate_scan_path(rows, cols, start_row=0):
    """生成蛇形扫描路径，覆盖网格上的所有单元格。
    
    用于芯片测试：引导液滴逐个走过每一个电极。
    蛇形模式：(0,0)→(0,1)→...→(0,cols-1)→(1,cols-1)→(1,cols-2)→...
    
    Args:
        rows: 行数
        cols: 列数
        start_row: 起始行（默认 0）
        
    Returns:
        list[(row,col)]: 蛇形路径坐标列表
    """
    path = []
    for r in range(start_row, rows):
        if r % 2 == 0:
            # 偶数行从左到右
            for c in range(cols):
                path.append((r, c))
        else:
            # 奇数行从右到左
            for c in range(cols - 1, -1, -1):
                path.append((r, c))
    return path


def reroute_around_obstacle(current_pos, remaining_path, obstacles,
                            cell_costs=None):
    """遇到障碍物时，从当前位置绕路到剩余路径中的下一个可达点。
    
    当液滴在芯片测试中遇到坏点（标记为障碍物）时，
    使用 A* 从当前位置寻路到剩余路径中最近的可达点。
    支持 cell_costs 避免经过已测点。
    
    Args:
        current_pos: 当前位置 (row, col)
        remaining_path: 剩余原始路径列表 [(row,col), ...] （不含当前位置）
        obstacles: 障碍物/坏点集合
        cell_costs: 格子额外代价字典 {(row, col): extra_cost}，默认 None。
                    已测通过的电极其代价较高，以尽量避开。
        
    Returns:
        dict:
        - 'success': bool 是否找到绕路
        - 'bypass_path': 绕路路径（含 current_pos 到目标点）
        - 'target_index': 绕路目标在 remaining_path 中的索引，失败为 -1
        - 'message': 状态描述
    """
    if not remaining_path:
        return {'success': False, 'bypass_path': [], 'target_index': -1, 'message': '剩余路径为空'}
    
    # 尝试找到剩余路径中第一个可达的点
    for i, target in enumerate(remaining_path):
        if target in obstacles:
            continue
        path = a_star_shortest_path(current_pos, target, obstacles,
                                    cell_costs=cell_costs)
        if path:
            # 找到了！返回绕路路径（不包含 current_pos 的第一个重复点）
            bypass = path[1:]  # 跳过 current_pos 本身
            return {
                'success': True,
                'bypass_path': bypass,
                'target_index': i,
                'message': f'已绕路到 ({target[0]},{target[1]})',
            }
    
    return {'success': False, 'bypass_path': [], 'target_index': -1, 'message': '无可达绕路路径'}
