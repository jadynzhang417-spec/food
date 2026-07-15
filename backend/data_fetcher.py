"""
厦门美食漫游导航系统 - 数据抓取模块
负责通过百度地图 Web 服务 API 抓取厦门市美食 POI 数据，
并持久化存储到本地 JSON 文件中。

百度地图 Place API v2 文档：
https://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-placeapi

坐标系说明：
百度 Place API 返回 BD-09 坐标系，与前端百度 JS API 一致。
种子数据（手工采集的 GCJ-02 坐标）在运行时自动转换为 BD-09。
"""

import requests
import json
import os
import time
import math
from config import (
    BAIDU_MAP_AK,
    BAIDU_PLACE_SEARCH_URL,
    XIAMEN_CITY,
    FOOD_DISTRICTS,
    POIS_JSON_PATH,
    POI_TAGS,
    DATA_DIR,
    gcj02_to_bd09,
)


def ensure_data_dir():
    """确保数据存储目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def fetch_pois_by_keywords(keywords, region=XIAMEN_CITY, page_size=20, max_pages=None):
    """
    通过百度地图 Place API v2 搜索 POI 数据

    百度 Place API 参数说明:
    - ak: 服务端 AK（API Key）
    - query: 搜索关键字，多个关键字用 | 分隔
    - region: 检索区域（城市名），如 "厦门"
    - output: 输出格式，固定为 json
    - scope: 1=基本信息, 2=详细信息（含评分等）
    - page_size: 每页 POI 数量，最大 20
    - page_num: 页码，从 0 开始

    百度 API 返回格式:
    {
        "status": 0,           // 0=成功
        "total": 400,
        "results": [{
            "name": "...",
            "location": {"lat": 24.xxx, "lng": 118.xxx},  // BD-09 坐标
            "address": "...",
            "uid": "...",       // 唯一ID
            "telephone": "...",
            "detail_info": {
                "tag": "...",              // 分类标签
                "overall_rating": "4.5",
                ...
            }
        }]
    }

    参数:
        keywords: 搜索关键字
        region: 检索区域，默认厦门市
        page_size: 每页 POI 数量
        max_pages: 最大页数限制，None=不限制（最多20页）

    返回:
        POI 列表（BD-09 坐标系）
    """
    all_pois = []
    page_num = 0
    pages_fetched = 0

    while True:
        # 检查是否达到最大页数限制
        if max_pages is not None and pages_fetched >= max_pages:
            print(f"[数据抓取] 关键字 '{keywords}' 已达页数上限 ({max_pages} 页)，停止翻页")
            break
        params = {
            "ak": BAIDU_MAP_AK,
            "query": keywords,
            "region": region,
            "output": "json",
            "scope": "2",  # 获取详细信息（评分等）
            "page_size": page_size,
            "page_num": page_num,
        }

        try:
            print(f"[数据抓取] 正在搜索关键字 '{keywords}' 第 {page_num + 1} 页...")
            resp = requests.get(BAIDU_PLACE_SEARCH_URL, params=params, timeout=10)
            data = resp.json()

            # 百度 API 返回 status=0 表示成功
            if data.get("status") != 0:
                error_msg = data.get("message", "未知错误")
                print(f"[错误] 百度 API 返回异常 (status={data.get('status')}): {error_msg}")
                break

            results = data.get("results", [])
            if not results:
                print(f"[数据抓取] 关键字 '{keywords}' 无更多数据，共获取 {len(all_pois)} 条")
                break

            # 解析并清洗每条 POI 数据
            for poi in results:
                # 百度 API 返回的 location 为 {"lat": 纬度, "lng": 经度} 对象
                location = poi.get("location", {})
                lng = location.get("lng", 0)
                lat = location.get("lat", 0)

                # detail_info 扩展信息
                detail = poi.get("detail_info", {})
                tag = detail.get("tag", "") if detail else ""

                # 根据品类标签推断价格和签名
                _price_map = {
                    "小吃": 15, "甜品饮品": 20, "中餐厅": 30, "外国餐厅": 30,
                    "火锅": 30, "海鲜": 35, "咖啡厅": 20, "面包甜点": 15,
                    "美食": 25, "烧烤": 20, "大排档": 25, "日料": 40,
                    "西餐": 40, "闽南菜": 30, "闽菜": 30, "酒吧": 40,
                }
                inferred_price = 25  # 默认人均
                for key, price in _price_map.items():
                    if key in tag:
                        inferred_price = price
                        break

                cleaned_poi = {
                    "id": poi.get("uid", ""),  # 百度用 uid 作为唯一标识
                    "name": poi.get("name", ""),
                    "longitude": lng,  # BD-09 经度
                    "latitude": lat,  # BD-09 纬度
                    "address": poi.get("address", ""),
                    "type": tag,  # 分类标签（如 "小吃" "中餐厅"）
                    "tel": poi.get("telephone", ""),
                    "rating": detail.get("overall_rating", "") if detail else "",
                    "photos": [],  # 百度基础 API 不直接返回图片URL
                    "district": "",  # 后续根据坐标填充
                    "food_area": "",  # 后续根据坐标填充
                    "price": inferred_price,
                    "signature": f"招牌{tag}" if tag else "招牌美食",
                    "tags": tag,
                }
                all_pois.append(cleaned_poi)

            # 检查是否还有下一页
            pages_fetched += 1
            total_count = data.get("total", 0)
            if (page_num + 1) * page_size >= total_count:
                print(f"[数据抓取] 关键字 '{keywords}' 数据已全部获取，共 {len(all_pois)} 条")
                break

            page_num += 1
            time.sleep(0.5)  # 避免请求频率过高被限流

        except requests.exceptions.RequestException as e:
            print(f"[错误] 请求百度 API 失败: {e}")
            break
        except (ValueError, KeyError) as e:
            print(f"[错误] 解析 API 返回数据失败: {e}")
            break

    return all_pois


def assign_food_area(poi, districts):
    """
    根据 POI 的 BD-09 坐标判断其所属的美食片区
    计算 POI 到各片区中心点的欧氏距离，取最近的片区

    参数:
        poi: 单个 POI 数据字典（BD-09 坐标）
        districts: 美食片区配置列表（中心坐标为 BD-09）

    返回:
        片区名称字符串
    """
    min_dist = float("inf")
    closest_area = "其他区域"

    for district in districts:
        center_str = district.get("center", "")
        if not center_str:
            continue
        try:
            c_lng, c_lat = map(float, center_str.split(","))
        except ValueError:
            continue

        # 使用简化的欧氏距离（厦门小范围内精度足够）
        dist = math.sqrt(
            (poi["longitude"] - c_lng) ** 2 + (poi["latitude"] - c_lat) ** 2
        )
        if dist < min_dist:
            min_dist = dist
            closest_area = district["name"]

    # 如果距离最近片区超过约 5km（0.05度），标记为"其他区域"
    if min_dist > 0.05:
        closest_area = "其他区域"

    return closest_area


def get_district_by_area(food_area, districts):
    """根据美食片区名称获取所属行政区"""
    for d in districts:
        if d["name"] == food_area:
            return d["district"]
    return "未知"


def fetch_all_pois(target_count=60):
    """
    抓取所有美食片区的 POI 数据并存储到 JSON 文件

    流程:
    1. 按片区关键词搜索 POI（每片区限 2 页，确保覆盖）
    2. 按品类标签全城搜索 POI（每标签限 1 页，品类补全）
    3. 去重合并
    4. 按评分排序，选取 top-N（保证每个片区至少 5 家）
    5. 写入 JSON 文件（BD-09 坐标系）

    参数:
        target_count: 目标 POI 总数，默认 60
    """
    ensure_data_dir()
    all_pois = []
    seen_ids = set()

    print("=" * 50)
    print(f"开始抓取厦门市美食 POI 数据（目标: ~{target_count} 家）...")
    print("=" * 50)

    # 如果未配置 API Key，或 AK 仍为占位符，使用种子数据
    if BAIDU_MAP_AK == "YOUR_BAIDU_MAP_AK":
        print("[警告] 未配置百度地图 AK，将使用预设的种子数据。")
        print("[提示] 请在 backend/config.py 中设置 BAIDU_MAP_AK")
        print("[提示] 申请地址: https://lbsyun.baidu.com/apiconsole/key")
        print("[提示] 注意：需要申请「服务端」AK，浏览器端 AK 无法调用 Place API")
        all_pois = get_seed_data()
        save_to_json(all_pois)
        print(f"\n数据已保存至: {POIS_JSON_PATH}")
        print(f"总计 {len(all_pois)} 个美食 POI (BD-09 坐标系)")
        return all_pois

    # ============================================================
    # 阶段1: 按片区搜索（每片区使用片区名+"美食"作为关键词，2页）
    # 同时用片区关键字作为补充
    # ============================================================
    for district in FOOD_DISTRICTS:
        area_name = district["name"]
        print(f"\n[片区] {area_name} ({district['district']})")

        # 主搜索：片区名 + "美食"（地理相关性强）
        query_main = area_name.replace("美食街", "").replace("文创村", "").replace("艺术区", "").replace("美食区", "").replace("周边", "").replace("美食", "")
        query_main = query_main.strip() + "美食"

        pois = fetch_pois_by_keywords(query_main, page_size=10, max_pages=2)

        # 补充搜索：片区原始关键字（品类覆盖）
        keywords = district.get("keywords", "")
        if keywords:
            pois2 = fetch_pois_by_keywords(keywords, page_size=5, max_pages=1)
            # 合并
            seen_district = {p["id"] for p in pois}
            for p in pois2:
                if p["id"] not in seen_district:
                    pois.append(p)
                    seen_district.add(p["id"])

        # 为该片区的 POI 打上标签
        for poi in pois:
            poi["food_area"] = district["name"]
            poi["district"] = district["district"]
            poi["area_color"] = district.get("color", "#999999")

        print(f"  -> 获取到 {len(pois)} 个 POI")
        all_pois.extend(pois)
        time.sleep(0.3)

    # ============================================================
    # 阶段2: 按品类标签全城搜索（每标签限1页，补充品类覆盖）
    # ============================================================
    for tag in POI_TAGS:
        print(f"\n[品类] 全城搜索 '{tag}' ...")
        pois = fetch_pois_by_keywords(tag, region=XIAMEN_CITY, page_size=8, max_pages=1)
        print(f"  -> 获取到 {len(pois)} 个 POI（品类: {tag}）")
        all_pois.extend(pois)
        time.sleep(0.3)

    # ============================================================
    # 阶段3: 去重、过滤非美食、精选 top-N
    # ============================================================
    # 非美食类别过滤词
    NON_FOOD_FILTER = ["游戏", "娱乐", "KTV", "网吧", "酒店", "宾馆", "住宿", "棋牌", "按摩"]

    deduped = []
    for poi in all_pois:
        pid = poi.get("id", "")
        if not pid or pid in seen_ids:
            continue

        # 过滤非美食类 POI
        poi_type = poi.get("type", "")
        poi_name = poi.get("name", "")
        is_non_food = False
        for kw in NON_FOOD_FILTER:
            if kw in poi_type or kw in poi_name:
                is_non_food = True
                break
        if is_non_food:
            print(f"  [过滤] 跳过非美食: {poi_name} ({poi_type})")
            continue

        seen_ids.add(pid)
        # 对未归属片区的 POI 自动归类
        if not poi.get("food_area"):
            poi["food_area"] = assign_food_area(poi, FOOD_DISTRICTS)
            poi["district"] = get_district_by_area(poi["food_area"], FOOD_DISTRICTS)
            for d in FOOD_DISTRICTS:
                if d["name"] == poi["food_area"]:
                    poi["area_color"] = d.get("color", "#999999")
                    break
        deduped.append(poi)

    print(f"\n去重+过滤后共 {len(deduped)} 个 POI")

    # 如果 API 调用全部失败（返回0条），回退到种子数据
    if len(deduped) == 0:
        print("[警告] 百度 API 未返回任何数据，回退到种子数据。")
        print("[提示] 请确认 config.py 中的 BAIDU_MAP_AK 为「服务端」AK")
        print("[提示] 浏览器端 AK 无法调用 Place API（会返回 status=240）")
        print("[提示] 申请服务端 AK: https://lbsyun.baidu.com/apiconsole/key")
        all_pois = get_seed_data()
        save_to_json(all_pois)
        return all_pois

    # ============================================================
    # 阶段4: 精选 — 按评分排序，保证片区和品类多样性
    # ============================================================
    def sort_key(poi):
        try:
            return float(poi.get("rating", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    deduped.sort(key=sort_key, reverse=True)

    # 精选策略：每片区保底 minimum_per_area 家，其余按评分填充到 target_count
    minimum_per_area = max(5, target_count // len(FOOD_DISTRICTS))
    selected = []
    selected_ids = set()
    area_counts = {d["name"]: 0 for d in FOOD_DISTRICTS}
    area_counts["其他区域"] = 0

    # 第一轮：每片区保底选取（按评分从高到低）
    remaining = []
    for poi in deduped:
        area = poi.get("food_area", "其他区域")
        if area not in area_counts:
            area = "其他区域"
        if area_counts.get(area, 0) < minimum_per_area:
            selected.append(poi)
            selected_ids.add(poi["id"])
            area_counts[area] = area_counts.get(area, 0) + 1
        else:
            remaining.append(poi)

    print(f"\n[精选] 保底选取 {len(selected)} 个 POI（每片区至少 {minimum_per_area}）")
    for a, c in sorted(area_counts.items()):
        print(f"  {a}: {c} 个")

    # 第二轮：从剩余中按评分填充至 target_count，尽量均匀
    # 按评分从高到低，优先填充 POI 较少的片区
    remaining.sort(key=sort_key, reverse=True)
    for poi in remaining:
        if len(selected) >= target_count:
            break
        area = poi.get("food_area", "其他区域")
        if area not in area_counts:
            area = "其他区域"
        # 优先填充未达标的片区
        if area_counts.get(area, 0) < minimum_per_area + 2:
            selected.append(poi)
            selected_ids.add(poi["id"])
            area_counts[area] = area_counts.get(area, 0) + 1

    # 第三轮：如果还没达到 target_count，按评分继续填充
    for poi in remaining:
        if len(selected) >= target_count:
            break
        if poi["id"] not in selected_ids:
            selected.append(poi)
            selected_ids.add(poi["id"])

    all_pois = selected[:target_count]

    # 统计各片区分布
    area_stats = {}
    for p in all_pois:
        a = p.get("food_area", "其他区域")
        area_stats[a] = area_stats.get(a, 0) + 1
    print(f"\n精选后共 {len(all_pois)} 个 POI（目标 {target_count}）")
    for a, c in sorted(area_stats.items()):
        print(f"  {a}: {c} 个")

    # 持久化存储到 JSON 文件
    save_to_json(all_pois)
    print(f"\n数据已保存至: {POIS_JSON_PATH}")
    print(f"总计 {len(all_pois)} 个美食 POI (BD-09 坐标系)")

    return all_pois


def save_to_json(pois):
    """将 POI 数据保存到 JSON 文件"""
    ensure_data_dir()
    with open(POIS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)


def load_pois_from_json():
    """从 JSON 文件加载 POI 数据"""
    if not os.path.exists(POIS_JSON_PATH):
        return []
    with open(POIS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_seed_data():
    """
    预设的厦门美食种子数据（BD-09 坐标系）

    原始数据为手工采集的 GCJ-02 近似坐标，
    在运行时通过 gcj02_to_bd09() 转换为 BD-09 后存储。
    确保前端使用百度地图 JS API 时坐标精准对齐。
    """
    # 原始种子数据（GCJ-02 坐标系，手工采集）
    _seed_gcj02 = [
        # ---- 中山路美食街 ----
        {"id": "seed_001", "name": "黄则和花生汤(中山路总店)", "lng": 118.08402, "lat": 24.45757,
         "address": "思明区中山路22-24号", "type": "甜品饮品", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.5", "tel": "0592-2024678"},
        {"id": "seed_002", "name": "莲欢海蛎煎", "lng": 118.08453, "lat": 24.45697,
         "address": "思明区中山路局口街局口横巷10号", "type": "小吃", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.6", "tel": ""},
        {"id": "seed_003", "name": "月华沙茶面", "lng": 118.08241, "lat": 24.45821,
         "address": "思明区镇邦路78号", "type": "小吃", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.7", "tel": ""},
        {"id": "seed_004", "name": "1980烧肉粽(中山路店)", "lng": 118.08511, "lat": 24.45688,
         "address": "思明区中山路353号", "type": "小吃", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.4", "tel": ""},
        {"id": "seed_005", "name": "豪香里脊肉串", "lng": 118.08378, "lat": 24.45789,
         "address": "思明区中山路48号", "type": "小吃", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.3", "tel": ""},
        {"id": "seed_006", "name": "八婆婆烧仙草(中山路店)", "lng": 118.08435, "lat": 24.45733,
         "address": "思明区中山路49号", "type": "甜品饮品", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.5", "tel": ""},
        # ---- 曾厝垵文创村 ----
        {"id": "seed_007", "name": "阿信厚吐司", "lng": 118.11156, "lat": 24.43688,
         "address": "思明区曾厝垵天泉路328号", "type": "甜品饮品", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.4", "tel": ""},
        {"id": "seed_008", "name": "珍珍姜母鸭(曾厝垵店)", "lng": 118.11045, "lat": 24.43781,
         "address": "思明区曾厝垵社69号", "type": "中餐厅", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.5", "tel": ""},
        {"id": "seed_009", "name": "闽宗闽南肠粉", "lng": 118.11102, "lat": 24.43741,
         "address": "思明区曾厝垵社189号", "type": "小吃", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.3", "tel": ""},
        {"id": "seed_010", "name": "林氏鱼丸(曾厝垵店)", "lng": 118.11081, "lat": 24.43752,
         "address": "思明区曾厝垵社178号", "type": "小吃", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.2", "tel": ""},
        {"id": "seed_011", "name": "绿皮火车乌龙茶(曾厝垵店)", "lng": 118.11121, "lat": 24.43712,
         "address": "思明区曾厝垵社280号", "type": "甜品饮品", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.4", "tel": ""},
        # ---- 沙坡尾艺术区 ----
        {"id": "seed_012", "name": "不辍咖啡馆", "lng": 118.08341, "lat": 24.44731,
         "address": "思明区大学路116号", "type": "甜品饮品", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.5", "tel": ""},
        {"id": "seed_013", "name": "初期糖水铺", "lng": 118.08412, "lat": 24.44672,
         "address": "思明区沙坡尾58号", "type": "甜品饮品", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.6", "tel": ""},
        {"id": "seed_014", "name": "Marmara 土耳其餐厅", "lng": 118.08387, "lat": 24.44658,
         "address": "思明区大学路77号", "type": "外国餐厅", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.3", "tel": ""},
        {"id": "seed_015", "name": "thankyou cafe bar", "lng": 118.08355, "lat": 24.44688,
         "address": "思明区大学路112号", "type": "甜品饮品", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.4", "tel": ""},
        # ---- 鼓浪屿美食区 ----
        {"id": "seed_016", "name": "叶氏麻糍", "lng": 118.06856, "lat": 24.44831,
         "address": "思明区鼓浪屿龙头路139号", "type": "小吃", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.6", "tel": ""},
        {"id": "seed_017", "name": "林记鱼丸(鼓浪屿店)", "lng": 118.06881, "lat": 24.44811,
         "address": "思明区鼓浪屿龙头路45号", "type": "小吃", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.3", "tel": ""},
        {"id": "seed_018", "name": "赵小姐的店(鼓浪屿店)", "lng": 118.06828, "lat": 24.44851,
         "address": "思明区鼓浪屿龙头路298号", "type": "甜品饮品", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.4", "tel": ""},
        {"id": "seed_019", "name": "金兰饼店", "lng": 118.06756, "lat": 24.44894,
         "address": "思明区鼓浪屿内厝澳路413号", "type": "甜品饮品", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.5", "tel": ""},
        {"id": "seed_020", "name": "沈家闽南肠粉", "lng": 118.06893, "lat": 24.44797,
         "address": "思明区鼓浪屿福建路57号", "type": "小吃", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.2", "tel": ""},
        # ---- 厦门大学周边 ----
        {"id": "seed_021", "name": "亚尖大排档", "lng": 118.09893, "lat": 24.44031,
         "address": "思明区大学路213号", "type": "中餐厅", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.4", "tel": ""},
        {"id": "seed_022", "name": "乌糖沙茶面", "lng": 118.09236, "lat": 24.44515,
         "address": "思明区民族路76号", "type": "小吃", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.6", "tel": ""},
        {"id": "seed_023", "name": "南普陀素菜馆", "lng": 118.09655, "lat": 24.44382,
         "address": "思明区思明南路515号", "type": "中餐厅", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.5", "tel": ""},
        {"id": "seed_024", "name": "老森咖喱", "lng": 118.09782, "lat": 24.44121,
         "address": "思明区大学路189号", "type": "外国餐厅", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.3", "tel": ""},
        {"id": "seed_025", "name": "猫街麻糍", "lng": 118.09368, "lat": 24.44211,
         "address": "思明区思明南路400号", "type": "小吃", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.4", "tel": ""},
        # ---- SM城市广场 ----
        {"id": "seed_026", "name": "海底捞火锅(SM店)", "lng": 118.12456, "lat": 24.50289,
         "address": "湖里区嘉禾路468号SM城市广场5楼", "type": "中餐厅", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.5", "tel": ""},
        {"id": "seed_027", "name": "陶陶居(SM店)", "lng": 118.12381, "lat": 24.50321,
         "address": "湖里区嘉禾路468号SM城市广场4楼", "type": "中餐厅", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.4", "tel": ""},
        {"id": "seed_028", "name": "一幸日料(SM店)", "lng": 118.12421, "lat": 24.50345,
         "address": "湖里区嘉禾路468号SM城市广场3楼", "type": "外国餐厅", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.6", "tel": ""},
        {"id": "seed_029", "name": "喜茶(SM城市广场店)", "lng": 118.12345, "lat": 24.50367,
         "address": "湖里区嘉禾路468号SM城市广场1楼", "type": "甜品饮品", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.3", "tel": ""},
        # ---- 集美学村美食 ----
        {"id": "seed_030", "name": "味友鸭肉面线", "lng": 118.10423, "lat": 24.57253,
         "address": "集美区集源路58号", "type": "小吃", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.5", "tel": ""},
        {"id": "seed_031", "name": "联生老店", "lng": 118.10356, "lat": 24.57321,
         "address": "集美区大社路128号", "type": "中餐厅", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.6", "tel": ""},
        {"id": "seed_032", "name": "大社沙茶面", "lng": 118.10311, "lat": 24.57298,
         "address": "集美区大社路96号", "type": "小吃", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.7", "tel": ""},
        {"id": "seed_033", "name": "奔水冬粉鸭", "lng": 118.10467, "lat": 24.57189,
         "address": "集美区岑东路152号", "type": "小吃", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.4", "tel": ""},
        # ---- 海沧阿罗海 ----
        {"id": "seed_034", "name": "海沧佳味馆", "lng": 118.03956, "lat": 24.49389,
         "address": "海沧区滨湖北路阿罗海广场2楼", "type": "中餐厅", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.3", "tel": ""},
        {"id": "seed_035", "name": "海敢小鱿鱼(海沧店)", "lng": 118.03891, "lat": 24.49456,
         "address": "海沧区滨湖北路阿罗海广场1楼", "type": "中餐厅", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.5", "tel": ""},
        {"id": "seed_036", "name": "泰蒲泰国料理(海沧店)", "lng": 118.03911, "lat": 24.49411,
         "address": "海沧区滨湖北路阿罗海广场2楼", "type": "外国餐厅", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.4", "tel": ""},

        # ============================================================
        # 补充条目 — 扩展各片区覆盖（品类补全 + 数量扩充）
        # ============================================================

        # ---- 中山路美食街 补充 ----
        {"id": "seed_101", "name": "临家闽南菜(中山路店)", "lng": 118.08352, "lat": 24.45791,
         "address": "思明区中山路步行街88号", "type": "闽南菜", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.5", "tel": "", "price": 30, "signature": "地道闽南菜", "tags": "闽南菜,中餐厅"},
        {"id": "seed_102", "name": "中山路海鲜大排档", "lng": 118.08411, "lat": 24.45645,
         "address": "思明区中山路步行街156号", "type": "海鲜", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.3", "tel": "", "price": 35, "signature": "鲜活海鲜", "tags": "海鲜"},
        {"id": "seed_103", "name": "KOI Thé(中山路店)", "lng": 118.08391, "lat": 24.45812,
         "address": "思明区中山路100号", "type": "甜品饮品", "food_area": "中山路美食街", "district": "思明区",
         "area_color": "#FF6B6B", "rating": "4.4", "tel": "", "price": 20, "signature": "黄金珍奶", "tags": "甜品饮品"},

        # ---- 曾厝垵文创村 补充 ----
        {"id": "seed_104", "name": "曾厝垵海鲜大排档", "lng": 118.11035, "lat": 24.43815,
         "address": "思明区曾厝垵社105号", "type": "海鲜", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.3", "tel": "", "price": 35, "signature": "现捞现做", "tags": "海鲜"},
        {"id": "seed_105", "name": "三年二班(曾厝垵店)", "lng": 118.11135, "lat": 24.43705,
         "address": "思明区曾厝垵社210号", "type": "中餐厅", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.4", "tel": "", "price": 30, "signature": "厦门味道", "tags": "中餐厅,闽南菜"},
        {"id": "seed_106", "name": "曾厝垵阿杰烧烤", "lng": 118.11068, "lat": 24.43728,
         "address": "思明区曾厝垵社88号", "type": "烧烤", "food_area": "曾厝垵文创村", "district": "思明区",
         "area_color": "#FF9F43", "rating": "4.2", "tel": "", "price": 20, "signature": "炭烤海鲜", "tags": "烧烤,海鲜"},

        # ---- 沙坡尾艺术区 补充 ----
        {"id": "seed_107", "name": "避风坞海鲜馆", "lng": 118.08401, "lat": 24.44681,
         "address": "思明区大学路55号", "type": "海鲜", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.4", "tel": "", "price": 35, "signature": "沙坡尾海味", "tags": "海鲜"},
        {"id": "seed_108", "name": "锅炉咖啡", "lng": 118.08372, "lat": 24.44712,
         "address": "思明区沙坡尾60号", "type": "咖啡厅", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.5", "tel": "", "price": 20, "signature": "工业风咖啡", "tags": "咖啡厅,甜品饮品"},
        {"id": "seed_109", "name": "Juicy Supply(沙坡尾店)", "lng": 118.08333, "lat": 24.44745,
         "address": "思明区大学路92号", "type": "面包甜点", "food_area": "沙坡尾艺术区", "district": "思明区",
         "area_color": "#FECA57", "rating": "4.6", "tel": "", "price": 15, "signature": "手工面包", "tags": "面包甜点"},

        # ---- 鼓浪屿美食区 补充 ----
        {"id": "seed_110", "name": "鼓浪屿海鲜餐厅", "lng": 118.06845, "lat": 24.44865,
         "address": "思明区鼓浪屿龙头路200号", "type": "海鲜", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.3", "tel": "", "price": 35, "signature": "鼓浪屿本港海鲜", "tags": "海鲜"},
        {"id": "seed_111", "name": "褚家园咖啡馆", "lng": 118.06788, "lat": 24.44921,
         "address": "思明区鼓浪屿中华路15号", "type": "咖啡厅", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.7", "tel": "", "price": 20, "signature": "花园咖啡", "tags": "咖啡厅,甜品饮品"},
        {"id": "seed_112", "name": "苏小糖烘焙(鼓浪屿店)", "lng": 118.06816, "lat": 24.44841,
         "address": "思明区鼓浪屿龙头路168号", "type": "面包甜点", "food_area": "鼓浪屿美食区", "district": "思明区",
         "area_color": "#54A0FF", "rating": "4.4", "tel": "", "price": 15, "signature": "手工牛轧糖", "tags": "面包甜点"},

        # ---- 厦门大学周边 补充 ----
        {"id": "seed_113", "name": "八婆婆烧仙草(厦大店)", "lng": 118.09751, "lat": 24.44172,
         "address": "思明区思明南路422号", "type": "甜品饮品", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.5", "tel": "", "price": 20, "signature": "烧仙草", "tags": "甜品饮品"},
        {"id": "seed_114", "name": "大龙燚火锅(厦大店)", "lng": 118.09812, "lat": 24.44055,
         "address": "思明区大学路201号", "type": "火锅", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.3", "tel": "", "price": 30, "signature": "成都火锅", "tags": "火锅"},
        {"id": "seed_115", "name": "厦大西村大排档", "lng": 118.09723, "lat": 24.44231,
         "address": "思明区厦大西村11号", "type": "海鲜", "food_area": "厦门大学周边", "district": "思明区",
         "area_color": "#5F27CD", "rating": "4.2", "tel": "", "price": 35, "signature": "学生平价海鲜", "tags": "海鲜,大排档"},

        # ---- SM城市广场 补充 ----
        {"id": "seed_116", "name": "小龙坎火锅(SM店)", "lng": 118.12481, "lat": 24.50265,
         "address": "湖里区嘉禾路468号SM城市广场4楼", "type": "火锅", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.4", "tel": "", "price": 30, "signature": "重庆老火锅", "tags": "火锅"},
        {"id": "seed_117", "name": "星巴克(SM城市广场店)", "lng": 118.12391, "lat": 24.50389,
         "address": "湖里区嘉禾路468号SM城市广场1楼", "type": "咖啡厅", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.3", "tel": "", "price": 20, "signature": "星冰乐", "tags": "咖啡厅,甜品饮品"},
        {"id": "seed_118", "name": "莆田卤面(SM店)", "lng": 118.12441, "lat": 24.50331,
         "address": "湖里区嘉禾路468号SM城市广场B1", "type": "小吃", "food_area": "SM城市广场", "district": "湖里区",
         "area_color": "#01A3A4", "rating": "4.5", "tel": "", "price": 15, "signature": "莆田卤面", "tags": "小吃,闽南菜"},

        # ---- 集美学村美食 补充 ----
        {"id": "seed_119", "name": "逢甲冰菓室(集美店)", "lng": 118.10401, "lat": 24.57311,
         "address": "集美区集源路35号", "type": "甜品饮品", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.4", "tel": "", "price": 20, "signature": "台湾刨冰", "tags": "甜品饮品"},
        {"id": "seed_120", "name": "集美海味馆", "lng": 118.10342, "lat": 24.57245,
         "address": "集美区集源路88号", "type": "海鲜", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.3", "tel": "", "price": 35, "signature": "集美本港海鲜", "tags": "海鲜"},
        {"id": "seed_121", "name": "阿肥炸醋肉(集美店)", "lng": 118.10433, "lat": 24.57211,
         "address": "集美区岑东路78号", "type": "小吃", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.5", "tel": "", "price": 15, "signature": "闽南醋肉", "tags": "小吃"},
        {"id": "seed_122", "name": "集美大学路咖啡馆", "lng": 118.10375, "lat": 24.57356,
         "address": "集美区大学路22号", "type": "咖啡厅", "food_area": "集美学村美食", "district": "集美区",
         "area_color": "#10AC84", "rating": "4.2", "tel": "", "price": 20, "signature": "学生咖啡", "tags": "咖啡厅,甜品饮品"},

        # ---- 海沧阿罗海 补充 ----
        {"id": "seed_123", "name": "阿罗海小吃集市", "lng": 118.03945, "lat": 24.49371,
         "address": "海沧区滨湖北路阿罗海广场B1", "type": "小吃", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.2", "tel": "", "price": 15, "signature": "各地小吃", "tags": "小吃"},
        {"id": "seed_124", "name": "阿罗海糖水铺", "lng": 118.03876, "lat": 24.49478,
         "address": "海沧区滨湖北路阿罗海广场1楼", "type": "甜品饮品", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.3", "tel": "", "price": 20, "signature": "广式糖水", "tags": "甜品饮品"},
        {"id": "seed_125", "name": "潮牛火锅(海沧店)", "lng": 118.03901, "lat": 24.49435,
         "address": "海沧区滨湖北路阿罗海广场2楼", "type": "火锅", "food_area": "海沧阿罗海", "district": "海沧区",
         "area_color": "#EE5A24", "rating": "4.4", "tel": "", "price": 30, "signature": "潮汕牛肉火锅", "tags": "火锅"},
    ]

    # ============================================================
    # 关键步骤：将 GCJ-02 坐标转换为 BD-09
    # 确保前端百度地图渲染时无坐标偏移
    # ============================================================
    # 价格映射（根据美食类型推断人均消费）
    PRICE_MAP = {
        "小吃": 15, "甜品饮品": 20, "中餐厅": 30, "外国餐厅": 30,
        "火锅": 30, "海鲜": 35, "咖啡厅": 20, "面包甜点": 15,
        "大排档": 25, "烧烤": 20, "日料": 40, "西餐": 40,
        "闽南菜": 30, "闽菜": 30, "酒吧": 40,
    }

    seed_pois = []
    for item in _seed_gcj02:
        bd_lng, bd_lat = gcj02_to_bd09(item["lng"], item["lat"])
        food_type = item.get("type", "美食")

        converted = {
            "id": item["id"],
            "name": item["name"],
            "longitude": round(bd_lng, 6),
            "latitude": round(bd_lat, 6),
            "address": item["address"],
            "type": food_type,
            "food_area": item["food_area"],
            "district": item["district"],
            "area_color": item["area_color"],
            "rating": item["rating"],
            "tel": item.get("tel", ""),
            "photos": [],
            "coord_note": "BD-09（由 GCJ-02 种子数据转换）",
            "price": item.get("price", PRICE_MAP.get(food_type, 25)),
            "signature": item.get("signature", f"招牌{food_type}"),
            "tags": item.get("tags", food_type),
        }
        seed_pois.append(converted)

    print(f"[种子数据] 已加载 {len(seed_pois)} 个预设美食 POI（GCJ-02 → BD-09 已转换）")
    return seed_pois


# ============================================================
# 模块入口
# ============================================================
if __name__ == "__main__":
    pois = fetch_all_pois()
    areas = {}
    for p in pois:
        area = p.get("food_area", "未知")
        areas[area] = areas.get(area, 0) + 1
    print("\n各片区 POI 统计:")
    for area, count in areas.items():
        print(f"  {area}: {count} 个")
