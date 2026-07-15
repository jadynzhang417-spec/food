# 🍜 厦门美食漫游导航系统

## Xiamen Food Tour Navigation System

基于百度地图 API 的厦门市美食 POI 可视化展示、智能推荐与漫游路径规划 Web 应用。

---

**版本号**：v2.1  
**最后更新**：2026-07-15  
**编制部门**：计算机科学实训项目  

---

## 一、摘要

### 核心摘要

本系统是一个面向厦门市美食探索场景的 Web 应用，集成百度地图可视化、多维度美食检索、智能推荐算法（基于内容的推荐 + 达人匹配 + 一日游路线规划）以及 Dijkstra 最短路径漫游规划。系统提供双后端架构（Python Flask / C++ HTTP），前端采用原生 HTML/CSS/JS 实现，无需任何前端框架依赖。

### 背景与目的

厦门作为知名旅游城市，美食资源丰富但分布零散。游客和本地居民在美食探索中面临三大痛点：**信息分散**（不知去哪吃）、**选择困难**（选择太多无从下手）、**路线规划低效**（如何在有限的行程中高效串联多个美食点）。本系统旨在通过技术手段解决上述问题，提供一站式的美食查询、智能推荐与漫游规划体验。

### 适用范围

- **用户群体**：厦门游客、本地美食爱好者
- **业务场景**：美食 POI 浏览查询、偏好驱动的个性化推荐、单日/半日美食漫游路线规划
- **技术场景**：数据结构与算法课程实训、Web GIS 应用开发参考

---

## 二、技术架构与核心实现

### 1. 技术栈

#### 前端技术

| 类别 | 技术选型 | 说明 |
|------|---------|------|
| 地图引擎 | 百度地图 JS API v3.0 | BD-09 坐标系，支持 Marker/Polyline/InfoWindow/Circle/Label |
| UI 框架 | 无框架，原生 HTML/CSS/JS | 内联样式 + Material You (MD3) 设计语言 |
| 图标方案 | Canvas 动态绘制 | 径向渐变立体圆点 Marker，按片区颜色 + 评分动态尺寸 |
| 响应式 | CSS Media Query + Flexbox | 支持桌面端和移动端自适应布局 |
| 商圈可视化 | BMap.Circle + BMap.Label | 半透明填充圆 + 虚线边框 + 浮动标签，点击标签筛选片区 |

#### 后端技术

| 类别 | 方案 A（Python） | 方案 B（C++） |
|------|-----------------|---------------|
| Web 框架 | Flask 3.1 + flask-cors | cpp-httplib（header-only HTTP 库） |
| HTTP 客户端 | requests（调用百度 Place API） | N/A（使用本地数据文件） |
| 数据存储 | JSON 文件（`data/pois.json`） | CSV 文本文件（`food.txt`, `roads.txt`） |
| API 端口 | 5001 | 8080 |
| 坐标系 | BD-09（百度 Place API 原生） | GCJ-02 → 真实 GPS 映射 |
| 数据来源 | 百度 Place API v2 真实数据（60家） | 预设种子数据 |

#### 第三方服务与工具

- **百度地图 JavaScript API v3.0**：前端地图渲染与交互
- **百度地图 Place API v2**：后端 POI 数据抓取（Python 方案）
- **Google Fonts（Roboto）**：UI 字体

### 2. 主要核心技术

#### 2.1 数据结构

共实现了 **7 种**核心数据结构：

| 数据结构 | 底层实现 | 应用场景 |
|---------|---------|---------|
| **动态顺序表** `DynamicArray` | 连续内存 + 倍增扩容 | 存储全部门店数据 |
| **链地址法哈希表** `HashTable` | 31 桶 + 链表，DJB2 哈希 | 标签 → 门店索引 O(1) 快速检索 |
| **邻接表图** `Graph` | `EdgeNode*` 数组 + 无向边 | 8 个商圈路网建模 |
| **顺序栈** `ActionStack` | 数组 + 栈顶指针 | 操作历史与撤销回滚 |
| **双向链表** `FavoritesList` | `head`/`tail` 指针 + `prev`/`next` | 收藏夹正反向遍历 |
| **大顶堆** `RankingHeap` | 完全二叉树数组 | Top-K 排行榜（人气/性价比） |
| **决策树** | 内联多层条件过滤 | 多维度智能筛选（预算→口味→商圈） |

#### 2.2 核心算法

| 算法 | 实现方式 | 应用场景 | 时间复杂度 |
|------|---------|---------|-----------|
| **Dijkstra 最短路径** | 邻接表 + 贪心松弛 | POI 间最短步行路径规划 | O(V²) |
| **BFS 广度优先搜索** | 队列 + 累计时间约束 | 周边美食圈探索（N 分钟步行可达） | O(V + E) |
| **Haversine 球面距离** | 三角函数公式 | POI 间实际地理距离计算 | O(1) |
| **堆排序** | 大顶堆 + 交换-下沉 | Top-K 人气/性价比排行 | O(N log N) |
| **余弦相似度** | 四维口味向量点积/模长 | 用户画像与门店特征匹配（智能推荐） | O(N) |
| **皮尔逊相关系数** | 协方差/标准差 | 用户与美食达人口味相似度计算 | O(N) |
| **链式 Dijkstra** | 多段最短路径串联 | 一日游多分类必经点路线规划 | O(K·V²) |

#### 2.3 坐标系处理

```
                    ┌─────────────┐
种子数据 (GCJ-02) ──▶│ gcj02_to_bd09() │──▶ BD-09 (统一存储)
百度 Place API ────▶│ (原生 BD-09)    │──▶ BD-09 (直接使用)
                    └─────────────┘
                           │
                    ┌──────▼──────┐
                    │ 前端百度地图  │
                    │ JS API v3.0 │  ← BD-09 原生支持
                    └─────────────┘

 前端 /api/shops → GCJ-02 (lng/lat) → gcj02ToBd09() → BMap.Point(BD-09)
 前端 /api/route → BD-09 (longitude/latitude) → 直接使用
```

#### 2.4 图构建策略（Python 后端 `src/algorithm/route_planner.py`）

为确保 POI 图连通性（尤其跨海/跨区场景），采用**混合建图策略**：
1. 所有 POI 两两计算 Haversine 距离
2. 距离 ≤ `max_edge_distance`（默认 10km）的节点对建立边
3. 每个节点额外连接其 **K 近邻**（K=5），保证跨区连通
4. 建图后执行 BFS 检测连通分量数量

### 3. 主要功能实现

#### 功能模块一：美食地图可视化与检索

**业务逻辑**：
- 以不同颜色圆点（Canvas 动态生成，立体渐变 + 阴影）在百度地图上展示 8 个美食片区的 POI
- 商圈半透明覆盖层（BMap.Circle）+ 浮动名称标签（BMap.Label），点击标签直接筛选片区
- 右上角毛玻璃商圈图例，显示各片区门店数量
- 支持按商圈、标签、名称搜索、多维度筛选四种检索模式

**前后端交互流程**：
```
用户操作 → 前端 filter/sort → GET /api/shops?landmark=X&tag=Y&search=Z
         → 后端列表过滤 / 模糊匹配 / 商圈过滤
         → 返回 JSON {count, shops: [...]}
         → 前端 renderShopMarkers() + renderShopList()
```

#### 功能模块二：智能推荐系统（三大子模块）

**子模块 1 — 基于用户画像的内容推荐（Content-Based Filtering）**：

```
用户调整滑块 → UserProfile {spicy, sweet, priceLevel, env}
             → getShopTasteVector(shop) 提取门店口味特征
             → cosineSimilarity(userVec, shopVec) 余弦相似度
             → priceBonus 价格偏好矫正
             → 排序输出 Top-10 匹配门店 + 匹配度百分比进度条
```

**子模块 2 — 美食达人推荐（Taste-Maker Matching）**：

- 内置 8 位虚拟美食达人（辣不怕的阿杰、甜牙齿小鹿、海鲜雷达老陈等），各有独立的口味向量和推荐门店列表
- 使用**皮尔逊相关系数**计算用户与达人的口味相似度
- 匹配 Top-2 "味蕾双胞胎"，展示达人私藏门店
- 支持点击达人卡片展开详情，点击门店标签跳转地图定位

**子模块 3 — 智能一日游路线规划**：

```
用户勾选必吃分类（如 #小吃, #海鲜, #甜品）
  → 每类自动筛选评分最高的门店作为必经点
  → 链式 Dijkstra: 起点 → 分类1最优门店 → 分类2最优门店 → ...
  → 返回完整路径、分段信息、总距离
  → 前端绘制绿色路线 + 步骤卡片
```

**异常处理**：分类无匹配门店时跳过该分类；路径不可达时提示用户调整选择。

#### 功能模块三：漫游路径规划引擎

**触发条件**：用户在地图上选择 2 个商圈圆点，或在门店列表中选择 ≥2 个停靠点

**执行步骤**：
1. `POST /api/route` 携带 `{start: "poi_id", end: "poi_id", waypoints: [...]}`
2. 后端运行 Dijkstra 算法计算最短路径
3. 回溯 `prev[]` 数组，输出路径节点序列 + 每段距离（km）
4. 前端使用 `BMap.Polyline` 双线绘制（主路线 + 光晕），`setViewport` 自适应聚焦
5. 商圈停靠点自动查找最近门店 ID 进行路由

**多停靠点场景**：将用户选择的 POI 逐段调用 Dijkstra 串联

#### 功能模块四：BFS 周边美食圈探索

用户选择起点商圈 + 步行时间阈值（5-60 分钟），查询该时间范围内可达的所有商圈，汇总商圈内的美食门店列表。

#### 功能模块五：收藏夹与操作撤销

- **收藏夹**：持久化 JSON 存储，支持添加/删除、一键清空
- **撤销机制**：顺序栈记录关键操作（收藏/取消收藏/清空），支持多类型回滚
- **数据持久化**：收藏夹保存到 `data/favorites.json`，操作历史保存到 `data/history.json`，启动时自动恢复，页面关闭时 `sendBeacon` 保证写入

---

## 三、项目结构

```
厦门美食漫游导航系统-Web版/
│
├── src/                          # Python 后端源码
│   ├── __init__.py
│   ├── app.py                    # Flask 应用入口（17 个 RESTful 端点）
│   ├── config.py                 # 全局配置（8 美食片区、坐标转换、API Key）
│   ├── services/                 # 业务服务
│   │   ├── __init__.py
│   │   └── data_fetcher.py       #   百度 Place API POI 数据抓取（片区+品类双维度搜索）
│   ├── algorithm/                # 算法
│   │   ├── __init__.py
│   │   └── route_planner.py      #   Haversine 距离 + Dijkstra + 多停靠点贪心规划
│   └── utils/                    # 工具
│       └── __init__.py
│
├── src_cpp/                      # C++ 后端（备选方案）
│   ├── server.cpp                # HTTP API 服务（15 个端点，cpp-httplib）
│   └── httplib.h                 # 单头文件 HTTP 库
│
├── bin/                          # 编译产物
│   └── food_server               # C++ 可执行文件
│
├── web/                          # Web 前端
│   ├── index.html                # 主页面（内嵌完整 CSS + JS 逻辑，~1900行）
│   │   ├── 欢迎页（Material You 动画）
│   │   ├── 百度地图容器 + 侧边栏布局
│   │   ├── 7 个标签面板（商圈/标签/排行/探索/筛选/智能）
│   │   ├── 智能推荐 3 子模块（口味测试/达人推荐/一日游）
│   │   ├── Canvas 立体 Marker 渲染（径向渐变 + 评分动态尺寸）
│   │   ├── 商圈覆盖层（半透明圆 + 浮动标签 + 持久化图例）
│   │   ├── Dijkstra 路径绘制（Polyline + 光晕）
│   │   └── 收藏夹 + 撤销 + 操作历史
│   ├── test.html                  # API 连通性测试页面
│   ├── js/
│   │   └── app.js                 # 独立 JS 逻辑（备选方案，含商圈覆盖层渲染）
│   └── css/
│       └── style.css              # 独立样式表（备选方案用）
│
├── data/                         # 数据文件
│   ├── pois.json                 # 美食 POI 数据（60 条，百度 Place API 真实数据）
│   ├── favorites.json            # 用户收藏
│   └── history.json              # 操作历史
│
├── tools/                        # 工具脚本（预留）
├── docs/                         # 项目文档
├── requirements.txt              # Python 依赖（Flask, flask-cors, requests）
└── README.md                     # 本文件
```

### API 端点一览（Python 后端，端口 5001）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/pois` | 获取所有美食 POI（支持 `food_area`, `district`, `type`, `search`, `limit` 参数） |
| GET | `/api/pois/<id>` | 获取单个 POI 详情 |
| GET | `/api/districts` | 获取美食片区列表 |
| GET | `/api/landmarks` | 获取商圈列表（GCJ-02 坐标，适配前端 landmarks 格式） |
| GET | `/api/shops` | 获取门店列表（GCJ-02 坐标，支持 `landmark`, `tag`, `search`, `limit` 参数） |
| GET | `/api/tags` | 获取美食分类标签及出现次数 |
| GET | `/api/ranking` | Top-K 排行榜（`mode=0` 按评分，`mode=1` 按性价比，`k` 参数控制数量） |
| GET | `/api/explore` | BFS 周边美食圈探索（`landmark` + `time` 时间阈值） |
| GET | `/api/favorites` | 获取收藏列表 |
| POST | `/api/favorites` | 添加/移除收藏（`{action: "add"|"remove", shop_id: "..."}`） |
| GET | `/api/history` | 获取操作历史 |
| POST | `/api/undo` | 撤销最近操作 |
| POST | `/api/save` | 强制持久化数据 |
| POST | `/api/route` | 规划漫游路径（`{start, end, waypoints}`） |
| POST | `/api/smart-route` | 智能一日游路线（`{categories, start}`） |
| POST | `/api/filter` | 多维度筛选（`{budget, tag, landmark}`） |
| POST | `/api/refresh` | 强制刷新 POI 数据（重新调用百度 API） |

---

## 四、快速开始

### 方式一：使用 Python 后端（推荐，数据最全）

#### 1. 安装依赖

```bash
cd 厦门美食漫游导航系统-Web版
pip install -r requirements.txt
```

#### 2. 配置百度地图 AK

编辑 `src/config.py`，设置 `BAIDU_MAP_AK`：

```python
BAIDU_MAP_AK = "你的服务端AK"
```

> **注意**：需要申请百度地图「服务端」AK，浏览器端 AK 无法调用 Place API（会返回 status=240）。
> 申请地址：[百度地图开放平台](https://lbsyun.baidu.com/apiconsole/key)
>
> 如未配置有效的服务端 AK，系统将自动使用内置的 61 个厦门知名美食 POI 作为演示数据。

#### 3. 启动后端

```bash
python3 src/app.py
# 服务启动在 http://localhost:5001
```

#### 4. 启动前端

```bash
cd web
python3 -m http.server 8080
```

> **⚠️ 注意**：请勿使用 `file://` 协议直接打开 `index.html`，浏览器 CORS 策略会拦截对后端 API 的跨域请求，导致数据无法加载。务必通过 HTTP 服务器访问。

访问 **http://localhost:8080**，点击"开始探索"即可使用。

#### 5. 配置百度地图前端 AK（如地图无法加载）

编辑 `web/index.html`，将第 7 行中的 `ak` 参数替换为你的百度地图浏览器端 AK：

```html
<script src="https://api.map.baidu.com/api?v=3.0&ak=你的浏览器端AK"></script>
```

### 方式二：使用 C++ 后端

#### 1. 编译 C++ 后端

```bash
cd src_cpp
g++ -std=c++11 -O2 server.cpp \
    ../../厦门美食漫游导航系统-第一版/data_structures.cpp \
    ../../厦门美食漫游导航系统-第一版/algorithms.cpp \
    ../../厦门美食漫游导航系统-第一版/data_loader.cpp \
    ../../厦门美食漫游导航系统-第一版/data_saver.cpp \
    -o ../bin/food_server
```

#### 2. 启动 C++ 后端

```bash
cd bin
./food_server
# 服务启动在 http://localhost:8080
```

#### 3. 启动前端

```bash
cd web
python3 -m http.server 3000
```

访问 `http://localhost:3000`。

### 一键启动（开发环境）

```bash
# 终端1：Python 后端（端口 5001）
python3 src/app.py

# 终端2：前端开发服务器（端口 8080）
cd web && python3 -m http.server 8080
```

浏览器访问 **http://localhost:8080**。

### 常见问题

| 问题 | 解决方案 |
|------|---------|
| 页面空白/数据不加载 | 确认后端已启动，检查 `http://localhost:5001/api/health` 是否返回 JSON |
| 地图不显示 | 检查 `web/index.html` 第 7 行百度地图浏览器端 AK 是否有效 |
| 数据只有种子数据 | 检查 `src/config.py` 中 `BAIDU_MAP_AK` 是否为有效的服务端 AK |
| API 返回 status=240 | 当前 AK 是浏览器端密钥，需更换为服务端 AK |
| 修改后页面不变 | 浏览器强制刷新（macOS: `Cmd+Shift+R`） |
| `file://` 协议无法加载数据 | 必须通过 HTTP 服务器访问（CORS 限制） |
| 端口 5001 被占用 | `lsof -i :5001` 查看占用进程，或修改 `src/config.py` 中 `FLASK_PORT` |

---

## 五、自定义配置

### 添加新的美食片区

编辑 `src/config.py` 中的 `_FOOD_DISTRICTS_GCJ02` 列表：

```python
{
    "name": "你的片区名称",
    "center_gcj02": (118.xxxxx, 24.xxxxx),  # GCJ-02 坐标
    "district": "所属行政区",
    "keywords": "搜索关键字1|关键字2",
    "color": "#HEX颜色",
}
```

### 调整数据抓取策略

编辑 `src/services/data_fetcher.py` 中 `fetch_all_pois()` 的参数：

- `target_count`：目标 POI 总数（默认 60）
- `page_size`：每页搜索结果数（片区搜索默认 10，品类搜索默认 8）
- `max_pages`：最大翻页数（片区搜索默认 2 页，品类搜索默认 1 页）

### 调整路径规划参数

编辑 `src/algorithm/route_planner.py`：
- `max_edge_distance`：POI 之间建立边的最大距离（默认 10km）
- `k_nearest`：每个节点至少连接的最近邻居数（默认 5）

---

## 六、关键数据结构与算法详解

### 6.1 图结构与 Dijkstra 算法

**图建模**：60 个厦门美食 POI 作为节点，POI 间 Haversine 球面距离作为带权无向边。K 近邻策略保证跨海/跨区连通。

**Dijkstra 算法流程**：
```
1. 初始化 dist[start]=0, dist[others]=∞, visited[all]=false
2. 每次从未访问节点中选择 dist 最小的 u
3. 标记 visited[u]=true
4. 遍历 u 的所有邻接边 (u,v,weight):
     if dist[u] + weight < dist[v]:
         dist[v] = dist[u] + weight
         prev[v] = u
5. 重复 2-4 直到 visited[end]=true
6. 回溯 prev[] 输出路径
```

### 6.2 智能推荐算法详解

**口味特征向量提取**（`getShopTasteVector`）：

```
门店特征 = {
    spicy: 从 tags/name/signature 正则推断 (0-10),
    sweet: 从 tags 推断甜品类关键词 (0-10),
    price: 人均价格归一化到 0-10,
    env:   从 tags 推断环境档次 (0-10)
}
```

**余弦相似度**：
```
similarity = cos(θ) = (A·B) / (|A| × |B|)
matchScore = min(1, similarity + priceBonus) × 100%
```

**皮尔逊相关系数**（达人匹配）：
```
r = Σ((x-x̄)(y-ȳ)) / √(Σ(x-x̄)² × Σ(y-ȳ)²)
simPct = (r + 1) / 2 × 100%   // 归一化到 0-100%
```

### 6.3 标签检索（哈希表）

使用 DJB2 哈希函数 + 链地址法：
- 哈希桶数：31（质数，减少冲突）
- 冲突处理：头插法链表
- 平均查找复杂度：O(1)

---

## 七、风险评估与应对

| 风险类型 | 具体描述 | 应对措施 |
|---------|---------|---------|
| **API 依赖风险** | 百度地图 API Key 失效或配额耗尽 | 内置 61 个种子数据作为降级方案，系统自动切换 |
| **AK 类型错误** | 浏览器端 AK 无法调用 Place API（status=240） | 自动检测 0 结果 → 回退种子数据 + 提示申请服务端 AK |
| **跨海连通性** | 厦门岛内与海沧/集美间 POI 距离过大 | K 近邻策略（K=5）保证图连通；超阈值自动标记"其他区域" |
| **性能瓶颈** | POI 数量增大时全对距离计算 O(N²) | 空间索引可优化；当前 60 条数据量下无瓶颈 |
| **坐标偏移** | GCJ-02 与 BD-09 混用导致点位漂移 | 统一存储为 BD-09，种子数据运行时自动转换；前端双端点分工明确 |
| **端口冲突** | macOS AirPlay 占用 5000 端口 | Python 后端使用 5001 端口 |
| **数据持久化** | 意外退出导致收藏/历史丢失 | 关键操作后立即调用 `/api/save` 写入磁盘；`beforeunload` 时 `sendBeacon` 保证 |
| **前端兼容性** | 旧版浏览器不支持 ES6/CSS 变量 | 支持 Chrome 90+, Firefox 90+, Safari 14+, Edge 90+ |

---

## 八、实施计划与后续展望

### 阶段性目标

| 阶段 | 目标 | 状态 |
|------|------|------|
| **短期** | 完成 C++ 后端全部 API、前端 UI 与交互 | ✅ 已完成 |
| **短期** | 实现三大智能推荐模块（口味匹配/达人推荐/一日游） | ✅ 已完成 |
| **中期** | 接入真实百度 Place API 数据替代种子数据 | ✅ 已完成（60 家真实门店） |
| **中期** | 商圈可视化（覆盖层 + 标签 + 图例） | ✅ 已完成 |
| **中期** | 项目结构规范化重组 | ✅ 已完成 |
| **中期** | 移动端适配与 PWA 支持 | 🔲 待开发 |
| **长期** | 用户系统与云端收藏同步 | 🔲 待开发 |
| **长期** | 基于用户行为数据的协同过滤推荐 | 🔲 待开发 |
| **长期** | 实时交通数据接入（动态调整步行耗时） | 🔲 待开发 |

### 后续行动建议

1. 统一前后端 API 端点格式，消除双后端方案的接口差异
2. 将内嵌在 HTML 中的 JS 逻辑拆分为独立模块文件
3. 增加单元测试覆盖核心算法（Dijkstra、Haversine、余弦相似度）
4. 接入真实用户反馈数据，优化推荐算法权重
5. 增加 POI 品类多样性过滤（去除非美食类结果）

---

## 九、附录

### A. 数据文件格式

**`data/pois.json`**（60 条厦门美食门店，百度 Place API 真实数据）：
```json
{
  "id": "c0b047006cf66858266e9842",     // 百度 POI uid
  "name": "林四喜·闽南传家菜(鼓浪屿店)",
  "longitude": 118.07724,               // BD-09 经度
  "latitude": 24.451249,                // BD-09 纬度
  "address": "龙头路300号",
  "type": "美食;中餐厅",                 // 品类标签
  "food_area": "中山路美食街",           // 所属片区
  "area_color": "#FF6B6B",              // 片区颜色
  "rating": "5.0",                      // 评分
  "price": 30,                          // 人均价格
  "signature": "招牌美食;中餐厅",         // 招牌信息
  "tags": "美食;中餐厅"                  // 标签
}
```

### B. 美食片区一览

| 编号 | 片区名称 | 行政区 | Marker 颜色 | POI 数量 |
|------|---------|--------|------------|---------|
| 1 | 中山路美食街 | 思明区 | `#FF6B6B` | 7 |
| 2 | 曾厝垵文创村 | 思明区 | `#FF9F43` | 7 |
| 3 | 沙坡尾艺术区 | 思明区 | `#FECA57` | 7 |
| 4 | 鼓浪屿美食区 | 思明区 | `#54A0FF` | 7 |
| 5 | 厦门大学周边 | 思明区 | `#5F27CD` | 7 |
| 6 | SM城市广场 | 湖里区 | `#01A3A4` | 7 |
| 7 | 集美学村美食 | 集美区 | `#10AC84` | 7 |
| 8 | 海沧阿罗海 | 海沧区 | `#EE5A24` | 7 |

> 片区覆盖层半径差异化：岛内核心商圈（中山路/沙坡尾/厦大/鼓浪屿）800m，岛内中型（曾厝垵/SM）1200m，岛外（集美/海沧）1500m。

### C. 术语解释

| 术语 | 全称/解释 |
|------|---------|
| **POI** | Point of Interest，兴趣点（美食门店） |
| **BD-09** | 百度坐标系，百度地图专用，在 GCJ-02 基础上二次加密 |
| **GCJ-02** | 国测局坐标系，中国法定坐标系（火星坐标系） |
| **Haversine** | 球面距离计算公式，用于计算地球表面两点间最短距离 |
| **Dijkstra** | 戴克斯特拉算法，求解带权图中单源最短路径的经典算法 |
| **BFS** | Breadth-First Search，广度优先搜索 |
| **KNN** | K-Nearest Neighbors，K 近邻算法 |
| **DJB2** | Daniel J. Bernstein 提出的字符串哈希函数 |
| **Content-Based Filtering** | 基于内容的推荐算法，通过物品特征与用户偏好匹配 |
| **canvas** | HTML5 Canvas API，用于动态生成 Marker 图标 |

### D. 参考资料

- [百度地图 JavaScript API v3.0 文档](https://lbsyun.baidu.com/index.php?title=jspopular3.0)
- [百度地图 Web 服务 Place API v2](https://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-placeapi)
- [cpp-httplib - A C++ Header-only HTTP Library](https://github.com/yhirose/cpp-httplib)
- [Flask 官方文档](https://flask.palletsprojects.com/)
- [Haversine formula - Wikipedia](https://en.wikipedia.org/wiki/Haversine_formula)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
