"""
寻路算法模块 - DMF 电极控制

提供 BFS 最短路径搜索功能，用于在电极网格上规划路径。
"""

from collections import deque
from . import global_cfg


def bfs_shortest_path(start, target, obstacles=None):
    """使用 BFS 找到从起点到目标的最短路径。
    
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

    # BFS
    queue = deque([start])
    visited = {start}
    parent = {start: None}

    # 4 方向移动（上、下、左、右）
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while queue:
        current = queue.popleft()

        if current == target:
            # 重构路径
            path = []
            node = target
            while node is not None:
                path.append(node)
                node = parent[node]
            return path[::-1]  # 反转得到从起点到终点的路径

        # 探索邻居
        for dr, dc in directions:
            next_row = current[0] + dr
            next_col = current[1] + dc

            # 检查边界
            if not (0 <= next_row < rows and 0 <= next_col < cols):
                continue

            # 检查是否已访问或是障碍物
            next_pos = (next_row, next_col)
            if next_pos in visited or next_pos in obstacles:
                continue

            visited.add(next_pos)
            parent[next_pos] = current
            queue.append(next_pos)

    # 没有找到路径
    return []


def path_to_indices(path):
    """将路径坐标序列转换为硬件电极索引序列。
    
    Args:
        path: 路径坐标列表 [(row, col), ...]
        
    Returns:
        indices: 硬件电极索引列表 [idx0, idx1, ...]
        索引公式：index = row * ELECTRODE_COLS + 1
    """
    if not path:
        return []

    indices = []
    cols = global_cfg.ELECTRODE_COLS

    for row, col in path:
        index = row * cols + 1
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
    path = bfs_shortest_path(start, target, obstacles)

    return {
        'path': path,
        'indices': path_to_indices(path),
        'length': len(path),
        'valid': len(path) > 0,
    }


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
        path = bfs_shortest_path(start, target, obstacles)
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
