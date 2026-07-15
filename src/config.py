"""
厦门美食漫游导航系统 - 配置文件
包含百度地图 API 密钥、坐标系转换工具、数据库路径等全局配置

坐标系说明:
- 百度地图 Web 服务 API 返回 BD-09 坐标系
- 百度地图 JS API 使用 BD-09 坐标系
- 本项目统一使用 BD-09 存储和展示，无需前端额外转换
- 种子数据（手工采集的 GCJ-02 坐标）运行时自动转换为 BD-09
"""

import os
import math

# ============================================================
# 坐标系转换工具
# 百度地图使用 BD-09 坐标系，与 GCJ-02 有约 0.006 度的偏移
# ============================================================

# 圆周率转换常量
X_PI = math.pi * 3000.0 / 180.0


def gcj02_to_bd09(lng, lat):
    """
    GCJ-02 坐标系 → BD-09 坐标系

    百度地图对外接口返回 BD-09 坐标，与国测局 GCJ-02 存在偏移。
    此函数实现标准的 GCJ-02 → BD-09 转换算法。

    参数:
        lng: GCJ-02 经度
        lat: GCJ-02 纬度

    返回:
        (bd_lng, bd_lat): BD-09 经纬度
    """
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * X_PI)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def bd09_to_gcj02(bd_lng, bd_lat):
    """
    BD-09 坐标系 → GCJ-02 坐标系

    当需要将百度地图坐标转换为国测局标准时使用。
    本项目统一使用 BD-09，此函数作为备用工具。

    参数:
        bd_lng: BD-09 经度
        bd_lat: BD-09 纬度

    返回:
        (gcj_lng, gcj_lat): GCJ-02 经纬度
    """
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj_lng, gcj_lat


# ============================================================
# 百度地图 API 配置
# ============================================================
# 百度地图服务端 AK（用于后端数据抓取、路径规划）
# 请到 https://lbsyun.baidu.com/apiconsole/key 申请服务端 AK
BAIDU_MAP_AK = "9CH15xGDSzwRua03bNDC4pWgBgjj2PF7"

# 百度地图 Place API v2 端点
BAIDU_PLACE_SEARCH_URL = "https://api.map.baidu.com/place/v2/search"

# 百度地图 Direction API v2（步行路线规划）
BAIDU_DIRECTION_URL = "https://api.map.baidu.com/directionlite/v1/walking"

# ============================================================
# 厦门市行政区划
# ============================================================
XIAMEN_CITY = "厦门"

# ============================================================
# 厦门市主要美食片区及坐标
# 注：center 坐标为 GCJ-02（原始采集数据），模块加载时自动转为 BD-09
# ============================================================
_FOOD_DISTRICTS_GCJ02 = [
    {
        "name": "中山路美食街",
        "center_gcj02": (118.08283, 24.45718),
        "district": "思明区",
        "keywords": "小吃|闽南菜|沙茶面|海蛎煎",
        "color": "#FF6B6B",
    },
    {
        "name": "曾厝垵文创村",
        "center_gcj02": (118.11097, 24.43763),
        "district": "思明区",
        "keywords": "小吃|海鲜|烧烤|土笋冻",
        "color": "#FF9F43",
    },
    {
        "name": "沙坡尾艺术区",
        "center_gcj02": (118.08366, 24.44695),
        "district": "思明区",
        "keywords": "咖啡馆|甜品|西餐|酒吧",
        "color": "#FECA57",
    },
    {
        "name": "鼓浪屿美食区",
        "center_gcj02": (118.06821, 24.44876),
        "district": "思明区",
        "keywords": "馅饼|鱼丸|麻糍|海蛎煎",
        "color": "#54A0FF",
    },
    {
        "name": "厦门大学周边",
        "center_gcj02": (118.09851, 24.44072),
        "district": "思明区",
        "keywords": "大排档|小吃|奶茶|面线糊",
        "color": "#5F27CD",
    },
    {
        "name": "SM城市广场",
        "center_gcj02": (118.12411, 24.50312),
        "district": "湖里区",
        "keywords": "餐厅|火锅|日料|甜品",
        "color": "#01A3A4",
    },
    {
        "name": "集美学村美食",
        "center_gcj02": (118.10389, 24.57287),
        "district": "集美区",
        "keywords": "小吃|沙茶面|大排档|海鲜",
        "color": "#10AC84",
    },
    {
        "name": "海沧阿罗海",
        "center_gcj02": (118.03926, 24.49430),
        "district": "海沧区",
        "keywords": "海鲜|闽菜|餐厅|火锅",
        "color": "#EE5A24",
    },
]

# ============================================================
# 将片区中心坐标转换为 BD-09（模块加载时自动执行）
# ============================================================
FOOD_DISTRICTS = []
for _d in _FOOD_DISTRICTS_GCJ02:
    _bd_lng, _bd_lat = gcj02_to_bd09(_d["center_gcj02"][0], _d["center_gcj02"][1])
    FOOD_DISTRICTS.append(
        {
            "name": _d["name"],
            "center": f"{_bd_lng:.5f},{_bd_lat:.5f}",
            "center_gcj02": f"{_d['center_gcj02'][0]:.5f},{_d['center_gcj02'][1]:.5f}",
            "district": _d["district"],
            "keywords": _d["keywords"],
            "color": _d["color"],
        }
    )

# ============================================================
# 数据存储路径
# ============================================================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_BASE_DIR)  # src/ 的上级目录即项目根
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
POIS_JSON_PATH = os.path.join(DATA_DIR, "pois.json")

# ============================================================
# 百度地图 POI 类型标签（用于搜索过滤）
# 百度 Place API 使用 tag 参数而非类型代码
# ============================================================
POI_TAGS = ["美食", "小吃", "中餐厅", "火锅", "海鲜", "甜品饮品", "咖啡厅", "面包甜点"]

# ============================================================
# Flask 服务配置
# ============================================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001  # 5000 被 macOS AirPlay 占用，改用 5001
FLASK_DEBUG = True
