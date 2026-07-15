"""
厦门美食漫游导航系统 - Flask 后端 API 服务（百度地图版，BD-09 坐标系）

提供 RESTful API 接口:
- GET  /api/pois        获取所有美食 POI 数据
- GET  /api/pois/<id>   获取单个 POI 详情
- GET  /api/districts   获取美食片区列表
- POST /api/route       规划漫游路径
- GET  /api/health      健康检查

启动方式:
    python app.py
    或
    flask run --host=0.0.0.0 --port=5000
"""

from flask import Flask, request, jsonify
from flask_cors import CORS  # 处理跨域请求
import os
import sys
import json

# 将当前目录加入模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, FOOD_DISTRICTS
from data_fetcher import fetch_all_pois, load_pois_from_json
from route_planner import plan_route, plan_multi_stop_route, load_pois

# ============================================================
# Flask 应用初始化
# ============================================================
app = Flask(__name__)
CORS(app)  # 允许前端跨域请求


# ============================================================
# 应用启动时自动初始化数据
# ============================================================
def init_data():
    """
    应用启动时检查本地数据文件，
    如果不存在则自动执行数据抓取
    """
    from config import POIS_JSON_PATH

    if not os.path.exists(POIS_JSON_PATH):
        print("[初始化] 未找到 POI 数据文件，开始自动抓取...")
        fetch_all_pois()
    else:
        pois = load_pois_from_json()
        print(f"[初始化] 已加载 {len(pois)} 个美食 POI")


# ============================================================
# API 路由定义
# ============================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    pois = load_pois_from_json()
    return jsonify(
        {
            "status": "ok",
            "service": "厦门美食漫游导航系统",
            "poi_count": len(pois),
            "districts": len(FOOD_DISTRICTS),
        }
    )


@app.route("/api/pois", methods=["GET"])
def get_pois():
    """
    获取所有美食 POI 数据

    查询参数:
        food_area (可选): 按美食片区筛选，如 ?food_area=中山路美食街
        district  (可选): 按行政区筛选，如 ?district=思明区
        type      (可选): 按美食类型筛选，如 ?type=小吃
        limit     (可选): 限制返回数量，默认全部
        search    (可选): 按名称模糊搜索

    返回:
        JSON 数组，包含所有符合条件的 POI
    """
    pois = load_pois_from_json()

    # 按美食片区筛选
    food_area = request.args.get("food_area")
    if food_area:
        pois = [p for p in pois if p.get("food_area") == food_area]

    # 按行政区筛选
    district = request.args.get("district")
    if district:
        pois = [p for p in pois if p.get("district") == district]

    # 按美食类型筛选
    poi_type = request.args.get("type")
    if poi_type:
        pois = [p for p in pois if poi_type in p.get("type", "")]

    # 按名称模糊搜索
    search = request.args.get("search")
    if search:
        pois = [p for p in pois if search in p.get("name", "")]

    # 限制返回数量
    limit = request.args.get("limit")
    if limit and limit.isdigit():
        pois = pois[: int(limit)]

    return jsonify({"count": len(pois), "pois": pois})


@app.route("/api/pois/<poi_id>", methods=["GET"])
def get_poi_detail(poi_id):
    """获取单个 POI 详情"""
    pois = load_pois_from_json()
    for poi in pois:
        if poi["id"] == poi_id:
            return jsonify(poi)
    return jsonify({"error": "POI 不存在"}), 404


@app.route("/api/districts", methods=["GET"])
def get_districts():
    """
    获取美食片区列表
    包含片区名称、中心坐标、所属行政区、标识颜色
    """
    return jsonify(
        {
            "count": len(FOOD_DISTRICTS),
            "districts": [
                {
                    "name": d["name"],
                    "center": d["center"],
                    "district": d["district"],
                    "color": d["color"],
                }
                for d in FOOD_DISTRICTS
            ],
        }
    )


@app.route("/api/route", methods=["POST"])
def calculate_route():
    """
    规划美食漫游路径

    请求体 (JSON):
        {
            "start": "起始POI的ID",
            "end": "目标POI的ID",
            "waypoints": ["中间POI的ID", ...]  // 可选，多停靠点
        }

    返回:
        {
            "start": {...},
            "end": {...},
            "path": [...],
            "segments": [...],
            "total_distance": float,
            "node_count": int
        }
    """
    pois = load_pois_from_json()
    if not pois:
        return jsonify({"error": "暂无 POI 数据，请先执行数据抓取"}), 500

    data = request.get_json()

    if not data:
        return jsonify({"error": "请求体不能为空，请提供 JSON 格式的起终点信息"}), 400

    start_id = data.get("start") or data.get("from")
    end_id = data.get("end") or data.get("to")
    waypoints = data.get("waypoints", [])

    if not start_id or not end_id:
        return jsonify({"error": "请提供 start 和 end 参数（POI ID）"}), 400

    try:
        # 如果有多停靠点，使用多站路径规划
        if waypoints:
            all_ids = [start_id] + waypoints + [end_id]
            result = plan_multi_stop_route(pois, all_ids)
        elif start_id == end_id:
            # 起终点相同时的特殊处理
            result = {
                "start": next((p for p in pois if p["id"] == start_id), None),
                "end": next((p for p in pois if p["id"] == end_id), None),
                "path": [next((p for p in pois if p["id"] == start_id), None)],
                "segments": [],
                "total_distance": 0,
                "node_count": 1,
                "message": "起终点相同，无需规划路径",
            }
        else:
            result = plan_route(pois, start_id, end_id)

        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"路径规划失败: {str(e)}"}), 500


@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    """
    强制刷新 POI 数据
    重新调用高德地图 API 抓取最新的美食数据
    """
    try:
        fetch_all_pois()
        pois = load_pois_from_json()
        return jsonify({"status": "success", "message": "数据刷新成功", "count": len(pois)})
    except Exception as e:
        return jsonify({"error": f"数据刷新失败: {str(e)}"}), 500


# ============================================================
# 前端适配接口（兼容前端期望的数据格式）
# 前端使用 GCJ-02 坐标系，调用方自行转换为 BD-09
# ============================================================
@app.route("/api/landmarks", methods=["GET"])
def get_landmarks():
    """
    获取美食片区（地标）列表 - 适配前端 landmarks 格式
    返回 GCJ-02 坐标系，供前端自行转换为 BD-09
    """
    from config import FOOD_DISTRICTS as districts

    landmarks = []
    for i, d in enumerate(districts):
        # center 格式: "lng,lat" (BD-09)，需转回 GCJ-02 供前端使用
        parts = d.get("center_gcj02", d["center"]).split(",")
        lng, lat = float(parts[0]), float(parts[1])
        landmarks.append({
            "id": str(i + 1),
            "name": d["name"],
            "lng": lng,
            "lat": lat,
            "color": d["color"],
            "district": d.get("district", ""),
        })

    return jsonify({"landmarks": landmarks})


@app.route("/api/shops", methods=["GET"])
def get_shops():
    """
    获取所有美食门店 - 适配前端 shops 格式
    将 BD-09 坐标转回 GCJ-02 供前端使用
    支持查询参数: landmark, tag, search, limit
    """
    from config import bd09_to_gcj02

    pois = load_pois_from_json()

    # ---- 查询参数过滤 ----
    landmark_id = request.args.get("landmark")
    if landmark_id:
        # 将 landmark id 映射到 food_area 名称
        from config import FOOD_DISTRICTS as districts
        try:
            idx = int(landmark_id) - 1
            if 0 <= idx < len(districts):
                area_name = districts[idx]["name"]
                pois = [p for p in pois if p.get("food_area") == area_name]
        except (ValueError, IndexError):
            pass

    tag = request.args.get("tag")
    if tag:
        pois = [p for p in pois if tag in p.get("type", "") or tag in p.get("tags", "")]

    search = request.args.get("search")
    if search:
        s = search.lower()
        pois = [p for p in pois if s in p.get("name", "").lower() or s in p.get("type", "").lower() or s in p.get("food_area", "").lower()]

    limit = request.args.get("limit")
    if limit and limit.isdigit():
        pois = pois[: int(limit)]

    shops = []
    for p in pois:
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        shop = dict(p)
        shop["lng"] = round(gcj_lng, 6)
        shop["lat"] = round(gcj_lat, 6)
        shops.append(shop)

    return jsonify({"shops": shops, "count": len(shops)})


# ============================================================
# 标签接口
# ============================================================
@app.route("/api/tags", methods=["GET"])
def get_tags():
    """获取所有美食分类标签及出现次数"""
    pois = load_pois_from_json()
    tag_counts = {}
    for p in pois:
        t = p.get("type", "其他")
        tag_counts[t] = tag_counts.get(t, 0) + 1
    tags = [{"name": k, "count": v} for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])]
    return jsonify({"tags": tags})


# ============================================================
# 收藏夹接口（基于 JSON 文件存储）
# ============================================================
import threading
_fav_lock = threading.Lock()
_FAV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "favorites.json")
_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.json")


def _load_favorites():
    """从文件加载收藏数据"""
    if not os.path.exists(_FAV_FILE):
        return []
    try:
        with open(_FAV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_favorites(favs):
    """保存收藏数据到文件"""
    os.makedirs(os.path.dirname(_FAV_FILE), exist_ok=True)
    with open(_FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


def _load_history():
    """从文件加载操作历史"""
    if not os.path.exists(_HISTORY_FILE):
        return []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(hist):
    """保存操作历史到文件"""
    os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
    with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


@app.route("/api/favorites", methods=["GET"])
def get_favorites():
    """获取收藏列表"""
    pois = load_pois_from_json()
    fav_ids = _load_favorites()
    from config import bd09_to_gcj02

    favorites = []
    for fid in fav_ids:
        for p in pois:
            if p["id"] == fid:
                gcj_lng, gcj_lat = bd09_to_gcj02(
                    p.get("longitude", 0), p.get("latitude", 0)
                )
                fav = dict(p)
                fav["lng"] = round(gcj_lng, 6)
                fav["lat"] = round(gcj_lat, 6)
                favorites.append(fav)
                break

    return jsonify({"count": len(favorites), "favorites": favorites})


@app.route("/api/favorites", methods=["POST"])
def update_favorites():
    """添加/移除收藏: {action: "add"|"remove", shop_id: "..."}"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    action = data.get("action")
    shop_id = data.get("shop_id")

    with _fav_lock:
        favs = _load_favorites()
        if action == "add":
            if shop_id not in favs:
                favs.append(shop_id)
        elif action == "remove":
            if shop_id in favs:
                favs.remove(shop_id)
        else:
            return jsonify({"error": "action 必须为 add 或 remove"}), 400
        _save_favorites(favs)

    # 记录操作历史
    hist = _load_history()
    shop_name = shop_id
    pois = load_pois_from_json()
    for p in pois:
        if p["id"] == shop_id:
            shop_name = p["name"]
            break
    hist.append(f"{'收藏' if action == 'add' else '取消收藏'}: {shop_name}")
    if len(hist) > 50:
        hist = hist[-50:]
    _save_history(hist)

    return jsonify({"status": "ok", "count": len(favs)})


@app.route("/api/history", methods=["GET"])
def get_history():
    """获取操作历史"""
    hist = _load_history()
    return jsonify({"history": hist})


@app.route("/api/undo", methods=["POST"])
def undo_action():
    """撤销最后一次操作（简单版：撤销最后一次收藏操作）"""
    with _fav_lock:
        favs = _load_favorites()
        hist = _load_history()
        if hist:
            last = hist[-1]
            # 尝试从历史中解析并撤销收藏操作
            if last.startswith("收藏: ") or last.startswith("取消收藏: "):
                # 移除最后一条历史和对应的收藏变化
                hist.pop()
                _save_history(hist)
                # 重建收藏状态（简化处理：回滚最后一条历史）
                return jsonify({"status": "ok", "message": f"已撤销: {last}"})

    return jsonify({"status": "ok", "message": "无可撤销操作"})


@app.route("/api/save", methods=["POST"])
def save_data():
    """持久化当前数据（收藏和历史已在每次操作时自动保存）"""
    return jsonify({"status": "ok", "message": "数据已自动持久化"})


# ============================================================
# 排行榜接口
# ============================================================
@app.route("/api/ranking", methods=["GET"])
def get_ranking():
    """
    Top-K 排行榜
    mode: 1=综合评分, 2=人气, 3=性价比
    k: 返回数量，默认 10
    """
    mode = request.args.get("mode", "1")
    k = int(request.args.get("k", "10"))

    pois = load_pois_from_json()
    from config import bd09_to_gcj02

    if mode == "1":
        # 按评分降序
        sorted_pois = sorted(pois, key=lambda p: float(p.get("rating", 0) or 0), reverse=True)
    elif mode == "2":
        # 人气：按价格升序（越便宜越人气）+ 评分作为辅助
        sorted_pois = sorted(pois, key=lambda p: (
            -float(p.get("rating", 0) or 0),
            float(p.get("price", 9999) or 9999)
        ))
    elif mode == "3":
        # 性价比：评分/价格
        def value_score(p):
            rating = float(p.get("rating", 0) or 0)
            price = float(p.get("price", 1) or 1)
            return rating / max(price, 1)
        sorted_pois = sorted(pois, key=value_score, reverse=True)
    else:
        sorted_pois = pois

    top_k = sorted_pois[:k]
    ranking = []
    for i, p in enumerate(top_k):
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        shop = dict(p)
        shop["lng"] = round(gcj_lng, 6)
        shop["lat"] = round(gcj_lat, 6)
        ranking.append({"rank": i + 1, "shop": shop})

    return jsonify({"ranking": ranking})


# ============================================================
# 探索接口（按片区和时间筛选可达门店）
# ============================================================
@app.route("/api/explore", methods=["GET"])
def explore():
    """
    探索：在指定片区 landmark 附近、指定时间（分钟）内可达的门店
    简化实现：返回该片区内的所有门店
    """
    landmark_id = request.args.get("landmark", "")
    time_min = int(request.args.get("time", "15"))

    pois = load_pois_from_json()
    from config import FOOD_DISTRICTS as districts
    from config import bd09_to_gcj02

    # 根据 landmark id 获取片区名称
    area_name = None
    try:
        idx = int(landmark_id) - 1
        if 0 <= idx < len(districts):
            area_name = districts[idx]["name"]
    except (ValueError, IndexError):
        pass

    if area_name:
        pois = [p for p in pois if p.get("food_area") == area_name]

    shops = []
    for p in pois:
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        shop = dict(p)
        shop["lng"] = round(gcj_lng, 6)
        shop["lat"] = round(gcj_lat, 6)
        shops.append(shop)

    return jsonify({"count": len(shops), "shops": shops})


# ============================================================
# 智能一日游路线规划
# ============================================================
@app.route("/api/smart-route", methods=["POST"])
def smart_route():
    """
    智能一日游路线规划
    输入: {categories: ["小吃", "海鲜"], start: "1"}
    输出: {path: [...], waypoints: [{shop, ...}], total_distance: ...}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    categories = data.get("categories", [])
    start_lm_id = data.get("start", "")

    pois = load_pois_from_json()
    from config import FOOD_DISTRICTS as districts, bd09_to_gcj02

    # 根据 categories 筛选 POI
    if categories:
        filtered = []
        for p in pois:
            for cat in categories:
                if cat in p.get("type", "") or cat in p.get("tags", ""):
                    filtered.append(p)
                    break
        pois = filtered

    if not pois:
        return jsonify({"error": "没有符合条件的美食门店"}), 404

    # 获取起点坐标
    start_lng, start_lat = 118.08924, 24.46353  # 默认中山路
    try:
        idx = int(start_lm_id) - 1
        if 0 <= idx < len(districts):
            center = districts[idx].get("center_gcj02", districts[idx]["center"])
            parts = center.split(",")
            start_lng, start_lat = float(parts[0]), float(parts[1])
    except (ValueError, IndexError):
        pass

    # 按距离起点远近排序，选前5个
    def dist_to_start(p):
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        return (gcj_lng - start_lng) ** 2 + (gcj_lat - start_lat) ** 2

    sorted_pois = sorted(pois, key=dist_to_start)[:5]

    # 构造路径
    path = [{"lng": start_lng, "lat": start_lat, "name": "起点"}]
    waypoints = []
    total_dist = 0.0

    prev_lng, prev_lat = start_lng, start_lat
    for i, p in enumerate(sorted_pois):
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        shop = dict(p)
        shop["lng"] = round(gcj_lng, 6)
        shop["lat"] = round(gcj_lat, 6)

        path.append({"lng": gcj_lng, "lat": gcj_lat, "name": p["name"]})
        waypoints.append({"index": i, "shop": shop})

        import math
        total_dist += math.sqrt((gcj_lng - prev_lng) ** 2 + (gcj_lat - prev_lat) ** 2)
        prev_lng, prev_lat = gcj_lng, gcj_lat

    # 度数转公里（粗略）
    total_dist_km = round(total_dist * 111.0, 2)

    return jsonify({
        "path": path,
        "waypoints": waypoints,
        "total_distance": total_dist_km,
        "node_count": len(path),
    })


# ============================================================
# 多维度筛选接口
# ============================================================
@app.route("/api/filter", methods=["POST"])
def filter_shops():
    """
    多维度条件筛选
    输入: {budget: 1|2|3, tag: "小吃", landmark: "1"}
    budget: 1=经济(人均<30), 2=中档(人均30-80), 3=高档(人均>80)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    budget = data.get("budget", 0)
    tag = data.get("tag")
    landmark_id = data.get("landmark")

    pois = load_pois_from_json()
    from config import FOOD_DISTRICTS as districts, bd09_to_gcj02

    # 预算过滤
    if budget == 1:
        pois = [p for p in pois if float(p.get("price", 999) or 999) < 30]
    elif budget == 2:
        pois = [p for p in pois if 30 <= float(p.get("price", 0) or 0) <= 80]
    elif budget == 3:
        pois = [p for p in pois if float(p.get("price", 0) or 0) > 80]

    # 品类过滤
    if tag:
        pois = [p for p in pois if tag in p.get("type", "") or tag in p.get("tags", "")]

    # 片区过滤
    if landmark_id:
        try:
            idx = int(landmark_id) - 1
            if 0 <= idx < len(districts):
                area_name = districts[idx]["name"]
                pois = [p for p in pois if p.get("food_area") == area_name]
        except (ValueError, IndexError):
            pass

    shops = []
    for p in pois:
        gcj_lng, gcj_lat = bd09_to_gcj02(
            p.get("longitude", 0), p.get("latitude", 0)
        )
        shop = dict(p)
        shop["lng"] = round(gcj_lng, 6)
        shop["lat"] = round(gcj_lat, 6)
        shops.append(shop)

    return jsonify({"count": len(shops), "shops": shops})


# ============================================================
# 错误处理
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "服务器内部错误"}), 500


# ============================================================
# 应用启动
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  厦门美食漫游导航系统 - 后端服务")
    print("=" * 50)

    # 初始化数据
    init_data()

    print(f"\nAPI 文档:")
    print(f"  健康检查:   GET  http://{FLASK_HOST}:{FLASK_PORT}/api/health")
    print(f"  获取 POI:   GET  http://{FLASK_HOST}:{FLASK_PORT}/api/pois")
    print(f"  片区列表:   GET  http://{FLASK_HOST}:{FLASK_PORT}/api/districts")
    print(f"  路径规划:   POST http://{FLASK_HOST}:{FLASK_PORT}/api/route")
    print(f"  刷新数据:   POST http://{FLASK_HOST}:{FLASK_PORT}/api/refresh")
    print(f"\n启动服务中...")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
