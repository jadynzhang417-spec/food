"""
厦门美食漫游导航系统 - 路径规划模块
基于 Dijkstra 算法计算美食 POI 之间的最短漫游路径。

算法说明:
1. 将所有 POI 构建为图结构（Graph），节点为 POI，边为两点间的距离
2. 使用优先队列优化的 Dijkstra 算法查找最短路径
3. 返回按顺序排列的 POI 列表，供前端绘制漫游路线

坐标系说明:
所有计算使用 BD-09 坐标系，与百度地图一致。
Haversine 公式在小范围内使用 BD-09 精度足够（误差 < 0.1%）。
"""

import math
import heapq
import json
import os
from config import POIS_JSON_PATH


def haversine_distance(lon1, lat1, lon2, lat2):
    """
    使用 Haversine 公式计算两点间的球面距离

    地球并非完美球体，但 Haversine 公式在厦门这种小尺度范围内
    精度足够（误差 < 0.1%），计算速度快。

    参数:
        lon1, lat1: 第一个点的经纬度（GCJ-02）
        lon2, lat2: 第二个点的经纬度（GCJ-02）

    返回:
        两点间距离，单位为公里(km)
    """
    R = 6371.0  # 地球平均半径，单位 km

    # 将角度转换为弧度
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine 公式
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def build_graph(pois, max_edge_distance=10.0, k_nearest=5):
    """
    将 POI 列表构建为带权无向图（邻接表）

    策略（确保图连通性）：
    1. 先计算所有 POI 两两之间的距离
    2. 对每个节点，连接距离 <= max_edge_distance（默认 10km）的节点
    3. 额外连接每个节点到其最近的 K 个邻居（K=5），
       确保跨海/跨区节点也能连通（如厦门岛→海沧、集美）
    4. 边的权重为实际地理距离（km）

    参数:
        pois: POI 数据列表
        max_edge_distance: 常规边的最大距离阈值（km）
        k_nearest: 每个节点至少连接的最近邻居数（保证连通性）

    返回:
        graph: 邻接表，格式 {poi_index: [(neighbor_index, distance_km), ...]}
    """
    n = len(pois)
    graph = {i: [] for i in range(n)}

    print(f"[路径规划] 正在构建图结构，共 {n} 个节点...")

    # 步骤1: 计算所有节点对的距离（存储为列表便于排序）
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine_distance(
                pois[i]["longitude"],
                pois[i]["latitude"],
                pois[j]["longitude"],
                pois[j]["latitude"],
            )
            all_pairs.append((i, j, dist))

    # 步骤2: 为每个节点找到 K 个最近邻居
    neighbors_by_node = {i: [] for i in range(n)}
    for i, j, dist in all_pairs:
        neighbors_by_node[i].append((j, dist))
        neighbors_by_node[j].append((i, dist))

    # 按距离排序
    for node in neighbors_by_node:
        neighbors_by_node[node].sort(key=lambda x: x[1])

    # 步骤3: 建立边（距离阈值内的 + K近邻保证连通）
    added_edges = set()
    for i, j, dist in all_pairs:
        # 判断是否需要添加这条边
        # 条件1: 在距离阈值内
        # 条件2: 或者互为 K 近邻（保证连通性）
        within_threshold = dist <= max_edge_distance

        # 检查 j 是否在 i 的K近邻中
        i_knn = {n for n, _ in neighbors_by_node[i][:k_nearest]}
        j_knn = {n for n, _ in neighbors_by_node[j][:k_nearest]}
        is_knn = j in i_knn or i in j_knn

        if within_threshold or is_knn:
            edge_key = (min(i, j), max(i, j))
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                graph[i].append((j, dist))
                graph[j].append((i, dist))

    # 统计图的基本信息
    total_edges = len(added_edges)
    avg_degree = sum(len(neighbors) for neighbors in graph.values()) / max(n, 1)

    # 检查连通分量数量（简单的 BFS）
    visited = set()
    components = 0
    for node in range(n):
        if node not in visited:
            components += 1
            queue = [node]
            visited.add(node)
            while queue:
                u = queue.pop(0)
                for v, _ in graph[u]:
                    if v not in visited:
                        visited.add(v)
                        queue.append(v)

    print(
        f"[路径规划] 图构建完成: {n} 个节点, {total_edges} 条边, "
        f"平均度 {avg_degree:.1f}, 连通分量 {components}"
    )

    if components > 1:
        print(
            f"[路径规划] ⚠️ 图中存在 {components} 个连通分量，"
            f"跨分量节点间无法规划路径"
        )

    return graph


def dijkstra(graph, start, end):
    """
    Dijkstra 最短路径算法（优先队列优化）

    算法流程:
    1. 初始化距离数组 dist[] = ∞，dist[start] = 0
    2. 使用最小堆优先队列维护待访问节点
    3. 每次取出距离最小的节点，松弛其邻接边
    4. 使用 prev[] 数组记录路径，便于回溯

    时间复杂度: O((V + E) * log V)
    空间复杂度: O(V)

    参数:
        graph: 邻接表 {node: [(neighbor, weight), ...]}
        start: 起始节点索引
        end: 目标节点索引

    返回:
        (path, total_distance):
        - path: 从 start 到 end 的节点索引列表，如 [0, 3, 5, 7]
        - total_distance: 总距离（km）
        如果不可达，返回 ([], float('inf'))
    """
    n = len(graph)

    # 初始化距离和前驱节点
    dist = {i: float("inf") for i in range(n)}
    prev = {i: None for i in range(n)}
    dist[start] = 0

    # 优先队列：(距离, 节点)
    pq = [(0, start)]
    visited = set()

    while pq:
        current_dist, u = heapq.heappop(pq)

        # 如果已访问过（有更短的路径已处理），跳过
        if u in visited:
            continue
        visited.add(u)

        # 到达目标节点，可以提前终止
        if u == end:
            break

        # 松弛邻接边
        for v, weight in graph.get(u, []):
            if v in visited:
                continue
            new_dist = current_dist + weight
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    # 回溯路径
    if dist[end] == float("inf"):
        print(f"[路径规划] 节点 {start} 到 {end} 不可达")
        return [], float("inf")

    path = []
    current = end
    while current is not None:
        path.append(current)
        current = prev[current]
    path.reverse()  # 反转为 start -> end 的顺序

    print(f"[路径规划] 最短路径: {path}, 距离: {dist[end]:.2f} km")
    return path, dist[end]


def plan_route(pois, start_poi_id, end_poi_id):
    """
    规划从 start_poi_id 到 end_poi_id 的最短漫游路径

    该函数是路径规划的主入口，完成以下步骤:
    1. 从 POI 列表中查找起点和终点的索引
    2. 构建距离图
    3. 运行 Dijkstra 算法
    4. 组装返回结果

    参数:
        pois: 所有 POI 数据列表
        start_poi_id: 起始 POI 的 ID
        end_poi_id: 目标 POI 的 ID

    返回:
        {
            "start": {...},       # 起始 POI 信息
            "end": {...},         # 终点 POI 信息
            "path": [...],        # 路径上所有 POI 的完整信息
            "segments": [...],    # 路径分段信息（每段包含两个端点和距离）
            "total_distance": float,  # 总距离（km）
            "node_count": int,    # 路径经过的节点数
        }
    """
    # 查找起点和终点的索引
    start_idx = None
    end_idx = None
    for i, poi in enumerate(pois):
        if poi["id"] == start_poi_id:
            start_idx = i
        if poi["id"] == end_poi_id:
            end_idx = i

    if start_idx is None:
        raise ValueError(f"未找到起始 POI: {start_poi_id}")
    if end_idx is None:
        raise ValueError(f"未找到目标 POI: {end_poi_id}")

    # 构建图并运行 Dijkstra
    graph = build_graph(pois)
    path_indices, total_distance = dijkstra(graph, start_idx, end_idx)

    if not path_indices:
        return {
            "start": pois[start_idx],
            "end": pois[end_idx],
            "path": [],
            "segments": [],
            "total_distance": 0,
            "node_count": 0,
            "error": "两点之间无法连通，请选择距离更近的 POI 或调整搜索范围",
        }

    # 组装路径上的 POI 信息
    path_pois = [pois[i] for i in path_indices]

    # 构建路径分段信息（供前端逐段渲染）
    segments = []
    for i in range(len(path_indices) - 1):
        idx_a = path_indices[i]
        idx_b = path_indices[i + 1]
        seg_dist = haversine_distance(
            pois[idx_a]["longitude"],
            pois[idx_a]["latitude"],
            pois[idx_b]["longitude"],
            pois[idx_b]["latitude"],
        )
        segments.append(
            {"from": pois[idx_a], "to": pois[idx_b], "distance_km": round(seg_dist, 3)}
        )

    return {
        "start": pois[start_idx],
        "end": pois[end_idx],
        "path": path_pois,
        "segments": segments,
        "total_distance": round(total_distance, 3),
        "node_count": len(path_pois),
    }


def plan_multi_stop_route(pois, poi_ids):
    """
    规划经过多个停靠点的漫游路径（贪心算法）

    当用户选择了多个 POI 时，使用贪心策略逐一规划:
    从第一个 POI 出发，每次都走向最近的未访问 POI

    参数:
        pois: 所有 POI 数据列表
        poi_ids: 用户选择的 POI ID 列表（按期望顺序）

    返回:
        完整的路线规划结果
    """
    if len(poi_ids) < 2:
        return {"error": "至少需要选择 2 个 POI"}

    graph = build_graph(pois)

    full_path = []
    full_segments = []
    total_dist = 0

    for i in range(len(poi_ids) - 1):
        # 查找索引
        start_id = poi_ids[i]
        end_id = poi_ids[i + 1]

        start_idx = end_idx = None
        for j, poi in enumerate(pois):
            if poi["id"] == start_id:
                start_idx = j
            if poi["id"] == end_id:
                end_idx = j

        if start_idx is None or end_idx is None:
            continue

        # 运行 Dijkstra 计算该段路径
        path_indices, dist = dijkstra(graph, start_idx, end_idx)

        if not path_indices:
            continue

        # 组装该段路径（避免重复添加中间节点）
        start_offset = 0 if i == 0 else 1  # 第一段保留起点，后续段跳过起点（已在上段的终点）
        for idx in path_indices[start_offset:]:
            full_path.append(pois[idx])

        # 组装分段
        for k in range(len(path_indices) - 1):
            idx_a = path_indices[k]
            idx_b = path_indices[k + 1]
            seg_dist = haversine_distance(
                pois[idx_a]["longitude"],
                pois[idx_a]["latitude"],
                pois[idx_b]["longitude"],
                pois[idx_b]["latitude"],
            )
            full_segments.append(
                {
                    "from": pois[idx_a],
                    "to": pois[idx_b],
                    "distance_km": round(seg_dist, 3),
                }
            )

        total_dist += dist

    return {
        "path": full_path,
        "segments": full_segments,
        "total_distance": round(total_dist, 3),
        "node_count": len(full_path),
    }


def load_pois():
    """加载 POI 数据"""
    if not os.path.exists(POIS_JSON_PATH):
        return []
    with open(POIS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 调试入口
# ============================================================
if __name__ == "__main__":
    pois = load_pois()
    if len(pois) >= 2:
        print(f"已加载 {len(pois)} 个 POI")
        # 测试：规划第一个和最后一个 POI 之间的路径
        result = plan_route(pois, pois[0]["id"], pois[-1]["id"])
        print(f"\n路径规划结果:")
        print(f"  起点: {result['start']['name']}")
        print(f"  终点: {result['end']['name']}")
        print(f"  总距离: {result['total_distance']} km")
        print(f"  经过节点数: {result['node_count']}")
        print(f"  路径:")
        for poi in result["path"]:
            print(f"    -> {poi['name']} ({poi['food_area']})")
    else:
        print("POI 数据不足，请先运行 data_fetcher.py 抓取数据")
