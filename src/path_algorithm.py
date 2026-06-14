"""
寻路算法模块 - DMF 电极控制

提供 A* 最短路径搜索功能，用于在电极网格上规划路径。
采用曼哈顿距离作为启发式函数，比 BFS 搜索效率更高。
"""

import heapq
from . import global_cfg


def a_star_shortest_path(start, target, obstacles=None):
    """使用 A* 算法找到从起点到目标的最短路径。
    
    采用曼哈顿距离启发式函数，完全匹配四方向移动约束。
    
    Args:
        start: 起点 (row, col)
        target: 目标点 (row, col)
        obstacles: 障碍物集合，例如 {(1, 2), (3, 4)} 或 None
        
    Returns:
        path: 路径坐标列表 [(row0, col0), (row1, col1), ...] 包括起点和终点。
        如果没有路径，返回空列表 []。
    """
    if obstacles is None:
        obstacles = set()
    else:
        obstacles = set(obstacles)

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

            tentative_g = g_score[current] + 1

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
            # 标记路径所有单元格为已占用（避免后续路径干涉）
            for cell in path:
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
