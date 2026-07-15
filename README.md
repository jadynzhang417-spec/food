# 🍜 厦门美食漫游导航系统

## Xiamen Food Tour Navigation System

基于百度地图 API 的厦门市美食 POI 可视化展示、智能推荐与漫游路径规划 Web 应用。

---

**版本号**：v2.0  
**最后更新**：2026-07-14  
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
| 地图引擎 | 百度地图 JS API v3.0 | BD-09 坐标系，支持 Marker/Polyline/InfoWindow |
| UI 框架 | 无框架，原生 HTML/CSS/JS | 内联样式 + Material You (MD3) 设计语言 |
| 图标方案 | Canvas 动态绘制 | 按片区颜色生成圆形 Marker，支持 Icon 缓存复用 |
| 响应式 | CSS Media Query + Flexbox | 支持桌面端和移动端自适应布局 |

#### 后端技术

| 类别 | 方案 A（Python） | 方案 B（C++） |
|------|-----------------|---------------|
| Web 框架 | Flask 3.1 + flask-cors | cpp-httplib（header-only HTTP 库） |
| HTTP 客户端 | requests（调用百度 Place API） | N/A（使用本地数据文件） |
| 数据存储 | JSON 文件（`data/pois.json`） | CSV 文本文件（`food.txt`, `roads.txt`） |
| API 端口 | 5001 | 8080 |
| 坐标系 | BD-09（百度 Place API 原生） | GCJ-02 → 真实 GPS 映射 |

#### 第三方服务与工具

- **百度地图 JavaScript API v3.0**：前端地图渲染与交互
- **百度地图 Place API v2**：后端 POI 数据抓取（Python 方案）
- **Google Fonts（Roboto）**：UI 字体
- **高德地图 API**：备选数据源（种子数据原始采集坐标系为 GCJ-02）

### 2. 主要核心技术

#### 2.1 数据结构（手写实现，无 STL 依赖）

共实现了 **7 种**核心数据结构：

| 数据结构 | 底层实现 | 应用场景 |
|---------|---------|---------|
| **动态顺序表** `DynamicArray` | 连续内存 + 倍增扩容 | 存储全部门店数据（50 条） |
| **链地址法哈希表** `HashTable` | 31 桶 + 链表，DJB2 哈希 | 标签 → 门店索引 O(1) 快速检索 |
| **邻接表图** `Graph` | `EdgeNode*` 数组 + 无向边 | 12 个商圈路网建模 |
| **顺序栈** `ActionStack` | 数组 + 栈顶指针 | 操作历史与撤销回滚 |
| **双向链表** `FavoritesList` | `head`/`tail` 指针 + `prev`/`next` | 收藏夹正反向遍历 |
| **大顶堆** `RankingHeap` | 完全二叉树数组 | Top-K 排行榜（人气/性价比） |
| **决策树** | 内联多层条件过滤 | 多维度智能筛选（预算→口味→商圈） |

#### 2.2 核心算法

| 算法 | 实现方式 | 应用场景 | 时间复杂度 |
|------|---------|---------|-----------|
| **Dijkstra 最短路径** | 邻接表 + 贪心松弛 | 商圈间最短步行路径规划 | O(V²) |
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
```

C++ 后端则使用**抽象坐标 → 真实 GPS 映射**：12 个商圈各有预设的 GCJ-02 GPS 坐标，门店通过最近商圈 + XY 偏移量计算真实经纬度。

#### 2.4 图构建策略（Python 后端 `route_planner.py`）

为确保 POI 图连通性（尤其跨海/跨区场景），采用**混合建图策略**：
1. 所有 POI 两两计算 Haversine 距离
2. 距离 ≤ `max_edge_distance`（默认 10km）的节点对建立边
3. 每个节点额外连接其 **K 近邻**（K=5），保证跨区连通
4. 建图后执行 BFS 检测连通分量数量

### 3. 主要功能实现

#### 功能模块一：美食地图可视化与检索

**业务逻辑**：
- 以不同颜色圆点（Canvas 动态生成）在百度地图上展示 8 个美食片区的 POI
- 支持按商圈、标签、名称搜索、多维度筛选四种检索模式

**前后端交互流程**：
```
用户操作 → 前端 filter/sort → GET /api/shops?tag=X&landmark=Y&search=Z
         → 后端哈希表检索 / 模糊匹配 / 商圈过滤
         → 返回 JSON {count, shops: [...]}
         → 前端 renderAllMarkers() + renderPoiList()
```

**数据流转**：
`food.txt` → `loadFoodData()` → `DynamicArray` + `HashTable` → API JSON → Canvas Marker

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
用户勾选必吃分类（如 #沙茶面, #海鲜, #甜品）
  → 每类自动筛选评分最高的门店作为必经点
  → 链式 Dijkstra: 起点 → 分类1最优门店 → 分类2最优门店 → ...
  → 返回完整路径、分段信息、总耗时
  → 前端绘制路线 + 步骤卡片
```

**异常处理**：分类无匹配门店时跳过该分类；路径不可达时提示用户调整选择。

#### 功能模块三：漫游路径规划引擎

**触发条件**：用户在地图上选择 2 个商圈圆点，或在门店列表中选择 ≥2 个停靠点

**执行步骤**：
1. `POST /api/route` 携带 `{from: "A", to: "H"}`
2. 后端运行 Dijkstra 算法计算最短路径
3. 回溯 `prev[]` 数组，输出路径节点序列 + 每段边权（步行分钟）
4. 前端使用 `BMap.Polyline` 双线绘制（主路线 + 光晕），`setViewport` 自适应聚焦

**多停靠点场景**：将用户选择的 POI 映射到最近商圈，逐段调用 Dijkstra 串联

#### 功能模块四：BFS 周边美食圈探索

用户选择起点商圈 + 步行时间阈值（5-60 分钟），BFS 搜索该时间范围内可达的所有商圈，汇总商圈内的美食门店列表。

#### 功能模块五：收藏夹与操作撤销

- **收藏夹**：双向链表存储，支持正序/倒序浏览、添加/删除、一键清空（带二次确认）
- **撤销机制**：顺序栈记录关键操作（收藏/取消收藏/清空），支持 `UndoType` 枚举区分的多类型回滚
- **数据持久化**：收藏夹保存到 `favorite.txt`，操作历史保存到 `history.txt`，启动时自动恢复

---

## 三、项目结构

```
xiamen-food-tour-web/
├── frontend/                          # 前端（原生 HTML/CSS/JS）
│   ├── index.html                     # 主页面（内嵌完整 CSS + JS 逻辑）
│   │   ├── 欢迎页（Material You 动画）
│   │   ├── 百度地图容器 + 侧边栏布局
│   │   ├── 7 个标签面板（商圈/标签/排行/探索/筛选/智能）
│   │   ├── 智能推荐 3 子模块（口味测试/达人推荐/一日游）
│   │   ├── Canvas 圆形 Marker 渲染
│   │   ├── Dijkstra 路径绘制（Polyline + 光晕）
│   │   └── 收藏夹 + 撤销 + 操作历史
│   ├── css/
│   │   └── style.css                  # 独立样式表（备选方案用）
│   ├── js/
│   │   └── app.js                     # 独立 JS 逻辑（备选方案，对接 Python 后端）
│   └── test.html                      # API 连通性测试页面
│
├── backend/                           # 后端方案 A：Python Flask
│   ├── app.py                         # Flask API 服务入口（7 个 RESTful 端点）
│   ├── config.py                      # 全局配置（8 美食片区、坐标转换、API Key）
│   ├── data_fetcher.py                # 百度 Place API POI 数据抓取 + 36 个种子数据
│   ├── route_planner.py               # Haversine 距离 + Dijkstra + 多停靠点贪心规划
│   ├── requirements.txt               # Python 依赖（Flask, flask-cors, requests）
│   └── data/
│       └── pois.json                  # POI 数据文件（自动生成，BD-09 坐标系）
│
├── backend_cpp/                       # 后端方案 B：C++ HTTP（课程核心）
│   ├── server.cpp                     # HTTP API 服务（15 个端点，cpp-httplib）
│   ├── httplib.h                      # 单头文件 HTTP 库
│   └── food_server                    # 编译产物
│
└── README.md                          # 本文件
```

> **注意**：C++ 后端的核心数据结构和算法源文件（`types.h`, `data_structures.cpp`, `algorithms.cpp`, `data_loader.cpp`, `data_saver.cpp`, `constants.h`, `food.txt`, `roads.txt`）位于第一版项目目录 `../厦门美食漫游导航系统-第一版/` 中，编译时通过相对路径引用。

### 双后端 API 对比

| 端点 | C++ 后端 (port 8080) | Python 后端 (port 5001) |
|------|---------------------|------------------------|
| 健康检查 | `GET /api/health` | `GET /api/health` |
| 商圈列表 | `GET /api/landmarks` | `GET /api/districts` |
| 门店列表 | `GET /api/shops?tag=&search=&landmark=&limit=` | `GET /api/pois?food_area=&district=&type=&search=` |
| 门店详情 | `GET /api/shops/:id` | `GET /api/pois/<id>` |
| 路径规划 | `POST /api/route {"from":"A","to":"H"}` | `POST /api/route {"start":"id","end":"id","waypoints":[]}` |
| 周边探索 | `GET /api/explore?landmark=A&time=15` | — |
| 排行榜 | `GET /api/ranking?mode=0&k=10` | — |
| 收藏夹 | `GET/POST /api/favorites` | — |
| 撤销操作 | `POST /api/undo` | — |
| 操作历史 | `GET /api/history` | — |
| 决策树筛选 | `POST /api/filter {"budget":50,"tag":"海鲜","landmark":"A"}` | — |
| 标签列表 | `GET /api/tags` | — |
| 智能一日游 | `POST /api/smart-route {"categories":["#沙茶面"],"start":"A"}` | — |
| 数据刷新 | — | `POST /api/refresh` |

---

## 四、快速开始

### 方式一：使用 C++ 后端（推荐，功能最完整）

#### 1. 编译 C++ 后端

```bash
cd backend_cpp
g++ -std=c++11 -O2 server.cpp \
    ../../厦门美食漫游导航系统-第一版/data_structures.cpp \
    ../../厦门美食漫游导航系统-第一版/algorithms.cpp \
    ../../厦门美食漫游导航系统-第一版/data_loader.cpp \
    ../../厦门美食漫游导航系统-第一版/data_saver.cpp \
    -o food_server
```

#### 2. 启动 C++ 后端

```bash
cd backend_cpp
./food_server
# 服务启动在 http://localhost:8080
```

#### 3. 启动前端

```bash
# 方式 A: Python 简易服务器
cd frontend
python3 -m http.server 3000

```

> **⚠️ 注意**：请勿使用 `file://` 协议直接打开 `index.html`，浏览器 CORS 策略会拦截对后端 API 的跨域请求，导致数据无法加载。务必通过 HTTP 服务器访问。

访问 `http://localhost:3000`，点击"开始探索"即可使用。

#### 4. 配置百度地图 AK（如地图无法加载）

编辑 `frontend/index.html`，将第 7 行中的 `ak` 参数替换为你的百度地图浏览器端 AK：

```html
<script src="https://api.map.baidu.com/api?v=3.0&ak=你的AK"></script>
```

> 申请地址：[百度地图开放平台](https://lbsyun.baidu.com/apiconsole/key)

### 方式二：使用 Python 后端

#### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

#### 2. 配置百度地图 AK

编辑 `backend/config.py`，设置 `BAIDU_MAP_AK`：

```python
BAIDU_MAP_AK = "你的服务端AK"
```

> 如未配置，系统将自动使用内置的 36 个厦门知名美食 POI 作为演示数据。

#### 3. 启动后端

```bash
cd backend
python app.py
# 服务启动在 http://localhost:5001
```

#### 4. 启动前端

修改 `frontend/js/app.js` 中的 API 地址（如使用 Python 后端）：

```javascript
const CONFIG = {
    API_BASE_URL: "http://localhost:5001/api",
    // ...
};
```

或在 `frontend/index.html` 中修改嵌入脚本的 `API` 变量指向端口 5001，并调整端点路径以匹配 Python 后端的接口格式。

### 当前开发环境（一键启动）

```bash
# 终端1：C++ 后端（端口 8080）
cd backend_cpp && ./food_server

# 终端2：Python 后端（端口 5001，可选）
cd backend && python app.py

# 终端3：前端开发服务器（端口 3000）
cd frontend && python3 -m http.server 3000
```

浏览器访问 **http://localhost:3000**。

### 常见问题

| 问题 | 解决方案 |
|------|---------|
| 页面空白/数据不加载 | 确认后端已启动，检查 `http://localhost:8080/api/health` 是否返回 JSON |
| 地图不显示 | 检查 `index.html` 第 7 行百度地图 AK 是否有效 |
| 修改后页面不变 | 浏览器强制刷新（macOS: `Cmd+Shift+R`） |
| `file://` 协议无法加载数据 | 必须通过 HTTP 服务器访问（CORS 限制） |

---

## 五、自定义配置

### 添加新的美食片区

**Python 后端** — 编辑 `backend/config.py` 中的 `_FOOD_DISTRICTS_GCJ02` 列表：

```python
{
    "name": "你的片区名称",
    "center_gcj02": (118.xxxxx, 24.xxxxx),  # GCJ-02 坐标
    "district": "所属行政区",
    "keywords": "搜索关键字1|关键字2",
    "color": "#HEX颜色",
}
```

**C++ 后端** — 编辑 `algorithms.cpp` 中的 `LANDMARK_NAMES[]`、`LANDMARK_X[]`、`LANDMARK_Y[]` 数组，以及 `server.cpp` 中的 `LANDMARK_GPS[]` 和 `LANDMARK_COLORS[]`。

### 调整路径规划参数

**Python 后端**（`route_planner.py`）：
- `max_edge_distance`：POI 之间建立边的最大距离（默认 10km）
- `k_nearest`：每个节点至少连接的最近邻居数（默认 5）

**C++ 后端**（`algorithms.cpp`）：
- 路网数据直接编辑 `roads.txt`，格式：`起点ID,终点ID,耗时(分钟)`

---

## 六、关键数据结构与算法详解

### 6.1 图结构与 Dijkstra 算法

**图建模**：12 个厦门核心商圈（中山路、八市、厦大、沙坡尾、曾厝垵等）作为节点，商圈间步行耗时作为带权无向边。20 条边构成连通路网。

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
| **API 依赖风险** | 百度地图 API Key 失效或配额耗尽 | 内置 36 个种子数据作为降级方案，系统自动切换 |
| **跨海连通性** | 厦门岛内与海沧/集美间 POI 距离过大 | K 近邻策略（K=5）保证图连通；超阈值自动标记"其他区域" |
| **性能瓶颈** | POI 数量增大时全对距离计算 O(N²) | 空间索引可优化；当前 36-50 条数据量下无瓶颈 |
| **坐标偏移** | GCJ-02 与 BD-09 混用导致点位漂移 | 统一存储为 BD-09，种子数据运行时自动转换 |
| **端口冲突** | macOS AirPlay 占用 5000 端口 | Python 后端使用 5001 端口 |
| **数据持久化** | 意外退出导致收藏/历史丢失 | 关键操作后立即调用 `/api/save` 写入磁盘 |
| **前端兼容性** | 旧版浏览器不支持 ES6/CSS 变量 | 支持 Chrome 90+, Firefox 90+, Safari 14+, Edge 90+ |

---

## 八、实施计划与后续展望

### 阶段性目标

| 阶段 | 目标 | 状态 |
|------|------|------|
| **短期** | 完成 C++ 后端全部 API、前端 UI 与交互 | ✅ 已完成 |
| **短期** | 实现三大智能推荐模块（口味匹配/达人推荐/一日游） | ✅ 已完成 |
| **中期** | 接入真实百度 Place API 数据替代种子数据 | ✅ 已实现（Python 后端） |
| **中期** | 移动端适配与 PWA 支持 | 🔲 待开发 |
| **长期** | 用户系统与云端收藏同步 | 🔲 待开发 |
| **长期** | 基于用户行为数据的协同过滤推荐 | 🔲 待开发 |
| **长期** | 实时交通数据接入（动态调整步行耗时） | 🔲 待开发 |

### 后续行动建议

1. 统一前后端 API 端点格式，消除双后端方案的接口差异
2. 将内嵌在 HTML 中的 JS 逻辑拆分为独立模块文件
3. 增加单元测试覆盖核心算法（Dijkstra、Haversine、余弦相似度）
4. 接入真实用户反馈数据，优化推荐算法权重

---

## 九、附录

### A. 数据文件格式

**`food.txt`**（50 条厦门美食门店）：
```
ID,名称,X坐标,Y坐标,特色菜,价格,评分,标签
01,黄则和花生汤,10,20,花生汤,15,4.5,#甜品 #老字号
```

**`roads.txt`**（12 商圈路网，20 条边）：
```
起点ID,终点ID,耗时(分钟)
A,B,8
B,C,10
...
```

### B. 美食片区一览

| 编号 | 商圈名称 | 行政区 | Marker 颜色 |
|------|---------|--------|------------|
| A | 中山路步行街 | 思明区 | `#FF6B6B` |
| B | 思明北路/大同路 | 思明区 | `#FF9F43` |
| C | 八市（第八市场） | 思明区 | `#FECA57` |
| D | 轮渡码头 | 思明区 | `#54A0FF` |
| E | 中华城/思明南路 | 思明区 | `#5F27CD` |
| F | 厦大西村 | 思明区 | `#01A3A4` |
| G | 南普陀/南华路 | 思明区 | `#10AC84` |
| H | 沙坡尾 | 思明区 | `#EE5A24` |
| I | 曾厝垵 | 思明区 | `#FF6B6B` |
| J | 环岛路/书法广场 | 思明区 | `#48DBFB` |
| K | 火车站/梧村 | 思明区 | `#C39BD3` |
| L | SM城市广场 | 湖里区 | `#F368E0` |

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

### D. 参考资料

- [百度地图 JavaScript API v3.0 文档](https://lbsyun.baidu.com/index.php?title=jspopular3.0)
- [百度地图 Web 服务 Place API v2](https://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-placeapi)
- [cpp-httplib - A C++ Header-only HTTP Library](https://github.com/yhirose/cpp-httplib)
- [Flask 官方文档](https://flask.palletsprojects.com/)
- [Haversine formula - Wikipedia](https://en.wikipedia.org/wiki/Haversine_formula)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
