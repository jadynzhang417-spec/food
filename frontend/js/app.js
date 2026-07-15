/**
 * ============================================================
 *  厦门美食漫游导航系统 - 前端主逻辑
 *  基于百度地图 JS API v3.0 实现地图可视化与交互
 * ============================================================
 *
 *  功能模块:
 *  1. 地图初始化与配置 (BMap.Map)
 *  2. POI 数据加载与渲染
 *  3. Canvas 圆形 Marker 图层
 *  4. 自定义 InfoWindow 弹窗 (BMap.InfoWindow)
 *  5. 漫游路线选择与规划
 *  6. BMap.Polyline 路径绘制
 *  7. 搜索与筛选交互
 *
 *  坐标系说明:
 *  百度地图 JS API 使用 BD-09 坐标系，后端返回的 POI 坐标
 *  也为 BD-09，前后端坐标一致，无需额外转换。
 */

// ============================================================
// 全局配置
// ============================================================
const CONFIG = {
    // 后端 API 地址（开发环境）
    API_BASE_URL: "http://localhost:5001/api",

    // 百度地图初始化参数
    MAP_CENTER_LNG: 118.096,   // 厦门市中心经度（BD-09）
    MAP_CENTER_LAT: 24.481,    // 厦门市中心纬度（BD-09）
    MAP_ZOOM: 13,

    // 路线绘制样式
    ROUTE_LINE_COLOR: "#FF6B6B",
    ROUTE_LINE_WIDTH: 6,
    ROUTE_LINE_OPACITY: 0.8,

    // 分页
    POI_LIST_PAGE_SIZE: 20,
};

// ============================================================
// 全局状态管理
// ============================================================
const STATE = {
    map: null,              // 百度地图实例 (BMap.Map)
    allPois: [],            // 全部 POI 数据 (BD-09)
    filteredPois: [],       // 筛选后的 POI 数据
    markers: [],            // 地图上的 Marker 对象数组
    infoWindow: null,       // 当前打开的 InfoWindow 引用
    routeStops: [],         // 用户选择的路线停靠点（POI ID 数组）
    routePolyline: null,    // 路线主 Polyline 对象
    routePolylineGlow: null,// 路线光晕 Polyline
    routeHighlightMarkers: [], // 路线节点高亮 Marker
    activeDistrict: null,   // 当前激活的片区筛选
    districtOverlays: [],   // 商圈覆盖层（Circle + Label）
    districtData: [],       // 商圈数据缓存
};

// ============================================================
// 工具函数
// ============================================================

/** 简易 HTML 转义，防止 XSS */
function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

/** 发起 GET 请求 */
async function apiGet(endpoint) {
    try {
        const resp = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`[API] GET ${endpoint} 失败:`, err);
        return null;
    }
}

/** 发起 POST 请求 */
async function apiPost(endpoint, body) {
    try {
        const resp = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`[API] POST ${endpoint} 失败:`, err);
        return null;
    }
}

// ============================================================
// Canvas 图标生成工具（用于创建彩色圆形 Marker）
// ============================================================

/**
 * 使用 Canvas 动态生成圆形图标
 *
 * 百度地图 BMap.Marker 不支持直接传入 HTML 元素作为外观，
 * 因此通过 Canvas 绘制圆形并导出为 data URL，作为 Marker 的图标。
 *
 * @param {string} color - 填充颜色（十六进制）
 * @param {number} radius - 圆点半径（像素），默认 12
 * @param {boolean} highlight - 是否为路线高亮模式（更大、带光晕）
 * @returns {BMap.Icon} 百度地图图标对象
 */
function createCircleIcon(color, radius, highlight) {
    radius = radius || 12;
    highlight = highlight || false;

    var size = (radius + (highlight ? 6 : 4)) * 2;
    var canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    var ctx = canvas.getContext("2d");

    var cx = size / 2;
    var cy = size / 2;

    // 外层阴影
    ctx.shadowColor = "rgba(0,0,0,0.25)";
    ctx.shadowBlur = highlight ? 8 : 4;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 2;

    if (highlight) {
        // 光晕
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 3, 0, 2 * Math.PI);
        ctx.fillStyle = color + "4D";
        ctx.fill();
    }

    // 白色外环
    ctx.shadowColor = "transparent";
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 1.5, 0, 2 * Math.PI);
    ctx.fillStyle = "#FFFFFF";
    ctx.fill();

    // 主体圆形（带阴影）
    ctx.shadowColor = "rgba(0,0,0,0.2)";
    ctx.shadowBlur = 2;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, radius - 1, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // 内圈高光（增加立体感）
    ctx.shadowColor = "transparent";
    var gradient = ctx.createRadialGradient(cx - radius * 0.3, cy - radius * 0.35, radius * 0.1, cx, cy, radius - 1);
    gradient.addColorStop(0, "rgba(255,255,255,0.45)");
    gradient.addColorStop(0.5, "rgba(255,255,255,0.1)");
    gradient.addColorStop(1, "rgba(0,0,0,0.08)");
    ctx.beginPath();
    ctx.arc(cx, cy, radius - 1, 0, 2 * Math.PI);
    ctx.fillStyle = gradient;
    ctx.fill();

    var icon = new BMap.Icon(canvas.toDataURL(), new BMap.Size(size, size), {
        anchor: new BMap.Size(cx, cy),
        imageSize: new BMap.Size(size, size),
    });

    return icon;
}

// ============================================================
// 模块 1: 地图初始化 (BMap.Map)
// ============================================================

/**
 * 初始化百度地图实例
 *
 * 百度地图 JS API v3.0 使用 BMap.Map 构造函数。
 * 基本流程: new BMap.Map() → centerAndZoom() → enableScrollWheelZoom()
 * 坐标使用 BD-09，直接传入 BMap.Point(lng, lat)。
 */
function initMap() {
    console.log("[地图] 正在初始化百度地图...");

    // 创建地图实例
    STATE.map = new BMap.Map("map-container");

    // 设置地图中心点和缩放级别
    // BMap.Point 参数顺序: (经度, 纬度) — 注意经度在前！
    STATE.map.centerAndZoom(
        new BMap.Point(CONFIG.MAP_CENTER_LNG, CONFIG.MAP_CENTER_LAT),
        CONFIG.MAP_ZOOM
    );

    // 启用滚轮缩放
    STATE.map.enableScrollWheelZoom(true);

    // ============================================================
    // 添加地图控件
    // ============================================================

    // 导航控件（缩放按钮 + 指北针）
    const navCtrl = new BMap.NavigationControl({
        anchor: BMAP_ANCHOR_TOP_LEFT,  // 左上角
        type: BMAP_NAVIGATION_CONTROL_LARGE,
    });
    STATE.map.addControl(navCtrl);

    // 比例尺控件
    const scaleCtrl = new BMap.ScaleControl({
        anchor: BMAP_ANCHOR_BOTTOM_LEFT,
    });
    STATE.map.addControl(scaleCtrl);

    // 地图点击空白处时关闭 InfoWindow
    STATE.map.addEventListener("click", function () {
        if (STATE.infoWindow) {
            STATE.infoWindow = null;
        }
    });

    console.log("[地图] 初始化完成 (BD-09 坐标系)");
}

// ============================================================
// 模块 2: POI 数据加载与处理
// ============================================================

/**
 * 从后端 API 加载 POI 数据（BD-09 坐标系）
 * 同时加载片区列表用于筛选
 */
async function loadPoiData() {
    console.log("[数据] 正在从后端加载 POI 数据...");
    updateApiStatus("checking");

    // 并行加载 POI 数据和片区列表
    const [poiResult, districtResult] = await Promise.all([
        apiGet("/pois"),
        apiGet("/districts"),
    ]);

    if (poiResult && poiResult.pois) {
        STATE.allPois = poiResult.pois;
        STATE.filteredPois = [...STATE.allPois];
        console.log(`[数据] 成功加载 ${STATE.allPois.length} 个 POI (BD-09)`);

        // 更新顶部状态栏
        document.getElementById("poi-count").textContent =
            `${STATE.allPois.length} 个美食点`;
        document.getElementById("list-count").textContent =
            STATE.allPois.length;

        updateApiStatus("online");
    } else {
        console.warn("[数据] 未能加载 POI 数据，请检查后端服务是否启动");
        updateApiStatus("offline");
        STATE.allPois = [];
        STATE.filteredPois = [];
    }

    // 渲染片区筛选按钮
    if (districtResult && districtResult.districts) {
        renderDistrictFilters(districtResult.districts);
        // 渲染地图上的商圈覆盖层（半透明圆 + 标签）
        renderDistrictOverlays(districtResult.districts);
    }

    // 渲染 Markers 和列表
    renderAllMarkers();
    renderPoiList();

    // 添加持久化图例
    if (poiResult && poiResult.pois) {
        addPersistentLegend(poiResult.pois);
    }
}

/**
 * 更新 API 连接状态指示器
 */
function updateApiStatus(status) {
    const el = document.getElementById("api-status");
    el.className = "badge";
    switch (status) {
        case "checking":
            el.classList.add("status-checking");
            el.textContent = "● 检测中";
            break;
        case "online":
            el.classList.add("status-online");
            el.textContent = "● 已连接";
            break;
        case "offline":
            el.classList.add("status-offline");
            el.textContent = "● 未连接";
            break;
    }
}

// ============================================================
// 模块 3: Canvas 圆形 Marker 渲染
// ============================================================

/**
 * 在地图上为所有 POI 渲染彩色圆点 Marker
 *
 * 百度地图 Marker 实现方式：
 * 使用 Canvas 动态生成不同颜色的圆形图标 (BMap.Icon)，
 * 每个 POI 根据其 area_color 属性使用对应颜色。
 *
 * BMap.Marker 的构造:
 *   new BMap.Marker(point, { icon: iconObj })
 *
 * 数据绑定:
 *   使用 marker.setExtData(poi) 将 POI 数据绑定到 Marker，
 *   后续通过 marker.getExtData() 获取。
 */
function renderAllMarkers() {
    // 先清除已有的所有 Marker
    clearAllMarkers();

    const pois = STATE.filteredPois;
    if (pois.length === 0) {
        console.log("[渲染] 无 POI 数据需要渲染");
        return;
    }

    console.log(`[渲染] 正在渲染 ${pois.length} 个 POI Marker...`);

    // 图标缓存：相同颜色复用同一个 Icon 对象，节省 Canvas 绘制开销
    const iconCache = {};

    pois.forEach(function (poi) {
        const color = poi.area_color || "#999999";
        const rating = parseFloat(poi.rating) || 0;

        // 根据评分动态调整标记大小: ≥4.8=14px, ≥4.5=12px, 其余=10px
        let markerRadius = 10;
        if (rating >= 4.8) markerRadius = 14;
        else if (rating >= 4.5) markerRadius = 12;

        // 从缓存获取或创建对应颜色的图标（颜色+尺寸作为缓存键）
        const cacheKey = color + "_" + markerRadius;
        if (!iconCache[cacheKey]) {
            iconCache[cacheKey] = createCircleIcon(color, markerRadius, false);
        }
        const icon = iconCache[cacheKey];

        // 创建 BMap.Point 坐标点（BD-09 坐标系，经度在前）
        const point = new BMap.Point(poi.longitude, poi.latitude);

        // 创建 Marker 并绑定图标
        const marker = new BMap.Marker(point, { icon: icon });

        // 将完整 POI 数据绑定到 Marker（点击时读取）
        marker.setExtData(poi);

        // ============================================================
        // 点击事件：弹出自定义 InfoWindow
        // 百度使用 addEventListener 绑定事件
        // ============================================================
        marker.addEventListener("click", function () {
            showInfoWindow(poi, marker);
        });

        // 添加到地图
        STATE.map.addOverlay(marker);
        STATE.markers.push(marker);
    });

    console.log(`[渲染] 已添加 ${STATE.markers.length} 个 Marker (图标缓存: ${Object.keys(iconCache).length} 种颜色)`);

    // 自动调整视野以包含所有 Marker
    if (STATE.markers.length > 0) {
        // 提取所有坐标点
        const points = STATE.markers.map(function (m) {
            return m.getPosition();
        });
        // setViewport 自动计算最佳视野，margins 右侧预留侧边栏空间
        STATE.map.setViewport(points, {
            margins: [60, 420, 60, 60],  // [上, 右, 下, 左]
        });
    }
}

/**
 * 清除地图上所有 POI Marker
 */
function clearAllMarkers() {
    if (STATE.markers.length > 0) {
        STATE.markers.forEach(function (marker) {
            STATE.map.removeOverlay(marker);
        });
        STATE.markers = [];
        console.log("[渲染] 已清除所有 Marker");
    }
}

// ============================================================
// 模块 3.5: 商圈覆盖层渲染（半透明圆 + 名称标签）
// ============================================================

/**
 * 在地图上渲染商圈覆盖层
 * 每个商圈绘制: 半透明填充圆 + 虚线边框 + 浮动名称标签
 *
 * 商圈半径根据片区特性差异化设置:
 * - 岛内密集商圈（中山路/沙坡尾/厦大/鼓浪屿）: 800m
 * - 岛内中型商圈（曾厝垵/SM广场）: 1200m
 * - 岛外商圈（集美/海沧）: 1500m
 */
function renderDistrictOverlays(districts) {
    // 清除旧覆盖层
    clearDistrictOverlays();

    if (!districts || districts.length === 0) return;

    // 商圈半径映射（米）
    var radiusMap = {
        "中山路美食街": 800,
        "沙坡尾艺术区": 800,
        "厦门大学周边": 800,
        "鼓浪屿美食区": 900,
        "曾厝垵文创村": 1200,
        "SM城市广场": 1200,
        "集美学村美食": 1500,
        "海沧阿罗海": 1500,
    };

    districts.forEach(function (d) {
        var parts = d.center.split(",");
        var lng = parseFloat(parts[0]);
        var lat = parseFloat(parts[1]);
        var point = new BMap.Point(lng, lat);
        var radius = radiusMap[d.name] || 1200;

        // --- 半透明填充圆（商圈范围示意）---
        var circle = new BMap.Circle(point, radius, {
            fillColor: d.color,
            fillOpacity: 0.07,
            strokeColor: d.color,
            strokeWeight: 2,
            strokeOpacity: 0.3,
            strokeStyle: "dashed",
        });
        STATE.map.addOverlay(circle);
        STATE.districtOverlays.push(circle);

        // --- 商圈名称标签 ---
        var label = new BMap.Label(d.name, {
            position: point,
            offset: new BMap.Size(-28, -10),
        });
        label.setStyle({
            backgroundColor: d.color + "E6",
            color: "#FFFFFF",
            fontSize: "12px",
            padding: "4px 10px",
            borderRadius: "14px",
            border: "none",
            fontWeight: "500",
            fontFamily: "'Roboto', 'PingFang SC', sans-serif",
            boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
            whiteSpace: "nowrap",
            letterSpacing: "0.5px",
        });
        STATE.map.addOverlay(label);
        STATE.districtOverlays.push(label);

        // --- 点击商圈标签筛选该片区 ---
        label.addEventListener("click", function () {
            // 更新侧边栏片区筛选状态
            var chips = document.querySelectorAll("#district-filters .filter-chip");
            chips.forEach(function (c) {
                c.classList.remove("active");
                if (c.dataset.district === d.name) {
                    c.classList.add("active");
                }
            });
            STATE.activeDistrict = d.name;
            applyFilters();
        });
    });

    STATE.districtData = districts;
    console.log("[商圈] 已渲染 " + districts.length + " 个商圈覆盖层");
}

/**
 * 清除所有商圈覆盖层
 */
function clearDistrictOverlays() {
    STATE.districtOverlays.forEach(function (overlay) {
        STATE.map.removeOverlay(overlay);
    });
    STATE.districtOverlays = [];
}

/**
 * 添加持久化地图图例（显示商圈颜色对照）
 */
function addPersistentLegend(pois) {
    // 移除旧图例
    var old = document.querySelector(".map-persistent-legend");
    if (old) old.remove();

    // 汇总商圈颜色
    var areaColors = {};
    pois.forEach(function (p) {
        var area = p.food_area || "其他区域";
        if (!areaColors[area]) {
            areaColors[area] = {
                color: p.area_color || "#999",
                count: 0,
            };
        }
        areaColors[area].count++;
    });

    var legend = document.createElement("div");
    legend.className = "map-persistent-legend";
    var html = '<div class="mpl-title">🍽️ 美食商圈</div>';
    Object.keys(areaColors).sort().forEach(function (area) {
        var info = areaColors[area];
        html +=
            '<div class="mpl-row">' +
            '<span class="mpl-dot" style="background:' + info.color + '"></span>' +
            '<span class="mpl-name">' + escapeHtml(area) + '</span>' +
            '<span class="mpl-count">' + info.count + "家" + "</span>" +
            "</div>";
    });

    legend.innerHTML = html;
    document.getElementById("map-container").appendChild(legend);
}

// ============================================================
// 模块 4: 自定义 InfoWindow (BMap.InfoWindow)
// ============================================================

/**
 * 显示自定义 InfoWindow 信息卡片
 *
 * 百度 BMap.InfoWindow 的使用方式:
 *   new BMap.InfoWindow(htmlContent, { width, height, ... })
 *   marker.openInfoWindow(infoWindow)  // 在 Marker 上方打开
 *
 * 内容包含：美食类型标签、评分、名称、地址、所属片区、
 * "加入路线"和"百度导航"两个操作按钮。
 *
 * @param {Object} poi - POI 数据对象
 * @param {BMap.Marker} marker - 关联的 Marker 对象
 */
function showInfoWindow(poi, marker) {
    // 使用隐藏模板构建 InfoWindow 的 HTML 内容
    const template = document.getElementById("info-window-template").innerHTML;
    const content = template
        .replace(/\{name\}/g, escapeHtml(poi.name))
        .replace(/\{type\}/g, escapeHtml(poi.type || "美食"))
        .replace(/\{rating\}/g, escapeHtml(poi.rating || "暂无"))
        .replace(/\{address\}/g, escapeHtml(poi.address || "暂无地址"))
        .replace(/\{food_area\}/g, escapeHtml(poi.food_area || "未知片区"))
        .replace(/\{id\}/g, escapeHtml(poi.id))
        .replace(/\{lng\}/g, poi.longitude)
        .replace(/\{lat\}/g, poi.latitude);

    // 创建百度 InfoWindow（设置宽度，高度自适应）
    const infoWindow = new BMap.InfoWindow(content, {
        width: 280,
        height: 0,   // 0 表示高度自适应内容
        enableMessage: false, // 不使用默认消息样式
    });

    // 在 Marker 上方打开 InfoWindow
    marker.openInfoWindow(infoWindow);

    // 记录当前打开的 InfoWindow（用于后续关闭）
    STATE.infoWindow = infoWindow;

    // ============================================================
    // InfoWindow 内按钮的事件绑定
    // InfoWindow 打开后 DOM 才渲染，需要延迟绑定
    // ============================================================
    setTimeout(function () {
        // "加入路线" 按钮
        const addBtn = document.querySelector(
            '.iw-btn-add[data-poi-id="' + poi.id + '"]'
        );
        if (addBtn) {
            addBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                addToRoute(poi);
                // 关闭 InfoWindow
                if (STATE.infoWindow) {
                    marker.closeInfoWindow();
                    STATE.infoWindow = null;
                }
            });
        }

        // "导航" 按钮 — 打开百度地图 Web 导航页面
        const navBtn = document.querySelector(
            '.iw-btn-nav[data-poi-id="' + poi.id + '"]'
        );
        if (navBtn) {
            navBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                // 使用百度地图 URI 打开导航（BD-09 坐标）
                const url =
                    "https://api.map.baidu.com/direction?" +
                    "destination=" + poi.latitude + "," + poi.longitude +
                    "&destination_name=" + encodeURIComponent(poi.name) +
                    "&mode=walking" +
                    "&output=html";
                window.open(url, "_blank");
            });
        }
    }, 150);
}

// ============================================================
// 模块 5: 侧边栏 POI 列表渲染
// ============================================================
// （此部分与地图 API 无关，逻辑保持不变）

function renderPoiList() {
    const container = document.getElementById("poi-list");
    const pois = STATE.filteredPois;

    if (pois.length === 0) {
        container.innerHTML =
            '<div class="list-empty">暂无美食数据<br>请确认后端服务已启动</div>';
        return;
    }

    const displayPois = pois.slice(0, CONFIG.POI_LIST_PAGE_SIZE);

    container.innerHTML = displayPois
        .map(function (poi) {
            const selected = STATE.routeStops.includes(poi.id);
            return (
                '<div class="poi-item' + (selected ? " selected" : "") + '"' +
                ' data-poi-id="' + escapeHtml(poi.id) + '"' +
                ' data-lng="' + poi.longitude + '"' +
                ' data-lat="' + poi.latitude + '">' +
                '<span class="poi-color-dot" style="background-color:' +
                    (poi.area_color || "#999") + '"></span>' +
                '<div class="poi-info">' +
                '<div class="poi-name">' + escapeHtml(poi.name) + '</div>' +
                '<div class="poi-meta">' +
                    escapeHtml(poi.food_area || "") + " · " +
                    escapeHtml(poi.type || "") +
                '</div>' +
                '</div>' +
                '<button class="poi-action' + (selected ? " in-route" : "") + '"' +
                ' data-poi-id="' + escapeHtml(poi.id) + '">' +
                    (selected ? "已选" : "+ 加入") +
                '</button>' +
                '</div>'
            );
        })
        .join("");

    // 绑定列表项点击事件
    container.querySelectorAll(".poi-item").forEach(function (item) {
        const poiId = item.dataset.poiId;
        const lng = parseFloat(item.dataset.lng);
        const lat = parseFloat(item.dataset.lat);

        // 点击列表项：地图飞到该 POI 并打开 InfoWindow
        item.addEventListener("click", function (e) {
            if (e.target.classList.contains("poi-action")) return;

            // 百度地图：使用 centerAndZoom 定位
            STATE.map.centerAndZoom(new BMap.Point(lng, lat), 16);

            // 查找对应的 POI 和 Marker
            const poi = STATE.filteredPois.find(function (p) {
                return p.id === poiId;
            });
            const marker = STATE.markers.find(function (m) {
                const d = m.getExtData();
                return d && d.id === poiId;
            });
            if (poi && marker) {
                showInfoWindow(poi, marker);
            }
        });

        // "加入路线" 按钮
        const btn = item.querySelector(".poi-action");
        if (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                const poi = STATE.filteredPois.find(function (p) {
                    return p.id === poiId;
                });
                if (poi) {
                    toggleRouteStop(poi);
                }
            });
        }
    });

    // POI 超过分页大小时显示提示
    if (pois.length > CONFIG.POI_LIST_PAGE_SIZE) {
        const more = document.createElement("div");
        more.className = "list-empty";
        more.textContent =
            "... 还有 " + (pois.length - CONFIG.POI_LIST_PAGE_SIZE) +
            " 个美食点，请使用搜索或筛选";
        container.appendChild(more);
    }

    document.getElementById("list-count").textContent = pois.length;
}

// ============================================================
// 模块 6: 美食片区筛选
// ============================================================

function renderDistrictFilters(districts) {
    const container = document.getElementById("district-filters");

    let html =
        '<span class="filter-chip active" data-district="">' +
        '<span class="chip-dot" style="background:#999"></span>全部</span>';

    districts.forEach(function (d) {
        html +=
            '<span class="filter-chip" data-district="' + escapeHtml(d.name) + '">' +
            '<span class="chip-dot" style="background:' + d.color + '"></span>' +
            escapeHtml(d.name) + '</span>';
    });

    container.innerHTML = html;

    container.querySelectorAll(".filter-chip").forEach(function (chip) {
        chip.addEventListener("click", function () {
            container.querySelectorAll(".filter-chip").forEach(function (c) {
                c.classList.remove("active");
            });
            chip.classList.add("active");

            STATE.activeDistrict = chip.dataset.district || null;
            applyFilters();
        });
    });
}

/** 应用筛选条件（片区 + 搜索词） */
function applyFilters() {
    let pois = STATE.allPois.slice();

    if (STATE.activeDistrict) {
        pois = pois.filter(function (p) {
            return p.food_area === STATE.activeDistrict;
        });
    }

    const searchTerm = document.getElementById("search-input").value.trim().toLowerCase();
    if (searchTerm) {
        pois = pois.filter(function (p) {
            return (
                p.name.toLowerCase().includes(searchTerm) ||
                (p.type && p.type.toLowerCase().includes(searchTerm)) ||
                (p.address && p.address.toLowerCase().includes(searchTerm))
            );
        });
    }

    STATE.filteredPois = pois;
    renderAllMarkers();
    renderPoiList();
    addPersistentLegend(pois);
}

// ============================================================
// 模块 7: 漫游路线管理
// ============================================================

function toggleRouteStop(poi) {
    const idx = STATE.routeStops.indexOf(poi.id);
    if (idx > -1) {
        STATE.routeStops.splice(idx, 1);
    } else {
        STATE.routeStops.push(poi.id);
        if (STATE.routeStops.length > 8) {
            STATE.routeStops.shift();
        }
    }
    renderRouteStops();
    renderPoiList();
    updateRouteButtons();
}

function addToRoute(poi) {
    if (!STATE.routeStops.includes(poi.id)) {
        STATE.routeStops.push(poi.id);
        if (STATE.routeStops.length > 8) {
            STATE.routeStops.shift();
        }
    }
    renderRouteStops();
    renderPoiList();
    updateRouteButtons();
}

function renderRouteStops() {
    const container = document.getElementById("route-stops");

    if (STATE.routeStops.length === 0) {
        container.innerHTML =
            '<p class="route-hint">点击地图上的美食点，将其加入漫游路线</p>';
        return;
    }

    container.innerHTML = STATE.routeStops
        .map(function (poiId, idx) {
            const poi = STATE.allPois.find(function (p) {
                return p.id === poiId;
            });
            if (!poi) return "";
            const isLast = idx === STATE.routeStops.length - 1;
            const icon = idx === 0 ? "🚩" : isLast ? "🏁" : "📍";
            return (
                '<div class="route-stop-item">' +
                '<span class="stop-index">' + icon + '</span>' +
                '<span class="stop-name">' + escapeHtml(poi.name) + '</span>' +
                '<span class="stop-remove" data-poi-id="' + poiId +
                    '" title="移除">✕</span>' +
                '</div>'
            );
        })
        .join("");

    container.querySelectorAll(".stop-remove").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            const poiId = btn.dataset.poiId;
            STATE.routeStops = STATE.routeStops.filter(function (id) {
                return id !== poiId;
            });
            renderRouteStops();
            renderPoiList();
            updateRouteButtons();
        });
    });
}

function updateRouteButtons() {
    document.getElementById("plan-route-btn").disabled =
        STATE.routeStops.length < 2;
    document.getElementById("clear-route-btn").disabled =
        STATE.routeStops.length === 0;
}

// ============================================================
// 模块 8: 路径规划与 BMap.Polyline 绘制
// ============================================================

/**
 * 规划漫游路线并在百度地图上绘制
 *
 * 使用 BMap.Polyline 绘制彩色路线，
 * BMap.Polyline(points, { strokeColor, strokeWeight, strokeOpacity })
 * points 为 BMap.Point 对象数组。
 *
 * 与高德地图的关键差异:
 * - 百度无 showDir 属性（方向箭头），通过额外绘制实现
 * - setViewport 代替 setFitView 调整视野
 * - addOverlay / removeOverlay 管理覆盖物
 */
async function planRoute() {
    if (STATE.routeStops.length < 2) {
        alert("请至少选择 2 个美食点来规划路线");
        return;
    }

    console.log(
        "[路线] 开始规划漫游路径，共 " + STATE.routeStops.length + " 个停靠点..."
    );

    // 构建请求参数
    const requestBody = {
        start: STATE.routeStops[0],
        end: STATE.routeStops[STATE.routeStops.length - 1],
    };
    if (STATE.routeStops.length > 2) {
        requestBody.waypoints = STATE.routeStops.slice(1, -1);
    }

    // 调用后端路径规划 API
    const result = await apiPost("/route", requestBody);

    if (!result || result.error) {
        alert("路径规划失败: " + (result ? result.error : "未知错误"));
        return;
    }

    console.log(
        "[路线] 规划完成: 总距离 " + result.total_distance + " km, " +
        "经过 " + result.node_count + " 个节点"
    );

    // 清除旧的路线
    clearRoute();

    // ============================================================
    // 使用 BMap.Polyline 绘制漫游路线
    //
    // BMap.Polyline 参数说明:
    // - strokeColor: 线条颜色 (CSS颜色)
    // - strokeWeight: 线条宽度（像素）
    // - strokeOpacity: 线条透明度 (0-1)
    // - strokeStyle: "solid" 实线 / "dashed" 虚线
    // ============================================================
    if (result.segments && result.segments.length > 0) {
        // 将分段路径拼接为 BMap.Point 数组
        const pathPoints = [];
        result.segments.forEach(function (seg) {
            if (
                pathPoints.length === 0 ||
                pathPoints[pathPoints.length - 1].lng !== seg.from.longitude ||
                pathPoints[pathPoints.length - 1].lat !== seg.from.latitude
            ) {
                pathPoints.push(
                    new BMap.Point(seg.from.longitude, seg.from.latitude)
                );
            }
            pathPoints.push(
                new BMap.Point(seg.to.longitude, seg.to.latitude)
            );
        });

        // 创建主路线 Polyline
        const polyline = new BMap.Polyline(pathPoints, {
            strokeColor: CONFIG.ROUTE_LINE_COLOR,
            strokeWeight: CONFIG.ROUTE_LINE_WIDTH,
            strokeOpacity: CONFIG.ROUTE_LINE_OPACITY,
            strokeStyle: "solid",
        });

        STATE.map.addOverlay(polyline);
        STATE.routePolyline = polyline;

        // 光晕效果（更宽的半透明线，在主路线下方）
        const glowPolyline = new BMap.Polyline(pathPoints, {
            strokeColor: CONFIG.ROUTE_LINE_COLOR,
            strokeWeight: CONFIG.ROUTE_LINE_WIDTH + 8,
            strokeOpacity: 0.15,
            strokeStyle: "solid",
        });
        STATE.map.addOverlay(glowPolyline);
        STATE.routePolylineGlow = glowPolyline;

        // ============================================================
        // 路线节点高亮 — 创建更大的带光晕 Marker
        // ============================================================
        const routePoiIds = new Set(result.path.map(function (p) {
            return p.id;
        }));

        result.path.forEach(function (poi) {
            const color = poi.area_color || CONFIG.ROUTE_LINE_COLOR;
            const highlightIcon = createCircleIcon(color, 16, true);

            const pt = new BMap.Point(poi.longitude, poi.latitude);
            const hMarker = new BMap.Marker(pt, { icon: highlightIcon });
            hMarker.setExtData(poi);

            // 点击高亮节点也弹出 InfoWindow
            hMarker.addEventListener("click", function () {
                showInfoWindow(poi, hMarker);
            });

            STATE.map.addOverlay(hMarker);
            STATE.routeHighlightMarkers.push(hMarker);
        });

        // 调整视野以包含整条路线
        STATE.map.setViewport([polyline], {
            margins: [80, 420, 80, 80],
        });
    }

    // 显示路线信息 + 图例
    showRouteInfo(result);
    addRouteLegend();
}

/**
 * 清除当前路线
 */
function clearRoute() {
    // 清除 Polyline
    if (STATE.routePolyline) {
        STATE.map.removeOverlay(STATE.routePolyline);
        STATE.routePolyline = null;
    }
    if (STATE.routePolylineGlow) {
        STATE.map.removeOverlay(STATE.routePolylineGlow);
        STATE.routePolylineGlow = null;
    }

    // 清除路线节点高亮 Marker
    STATE.routeHighlightMarkers.forEach(function (m) {
        STATE.map.removeOverlay(m);
    });
    STATE.routeHighlightMarkers = [];

    // 清除图例
    const legend = document.querySelector(".route-legend");
    if (legend) legend.remove();

    // 隐藏路线信息
    document.getElementById("route-info").style.display = "none";
}

/**
 * 清空所有路线停靠点
 */
function clearAllStops() {
    STATE.routeStops = [];
    renderRouteStops();
    renderPoiList();
    updateRouteButtons();
    clearRoute();
}

/**
 * 显示路线计算结果信息
 */
function showRouteInfo(result) {
    const container = document.getElementById("route-info");
    container.style.display = "block";

    const pathNames = result.path.map(function (p) {
        return p.name;
    }).join(" → ");

    container.innerHTML =
        '<div class="ri-distance">' + result.total_distance + ' km</div>' +
        '<div class="ri-row"><span>经过节点</span><strong>' +
            result.node_count + ' 个</strong></div>' +
        '<div class="ri-row"><span>路径分段</span><strong>' +
            result.segments.length + ' 段</strong></div>' +
        '<div class="ri-row" style="margin-top:8px;flex-direction:column;">' +
        '<span style="margin-bottom:4px;">漫游路线:</span>' +
        '<small style="color:#636E72;word-break:break-all;">' +
            pathNames + '</small></div>';
}

/**
 * 在地图左下角添加路线图例
 */
function addRouteLegend() {
    const oldLegend = document.querySelector(".route-legend");
    if (oldLegend) oldLegend.remove();

    const legend = document.createElement("div");
    legend.className = "route-legend";
    legend.innerHTML =
        '<div class="legend-title">🗺️ 漫游路线图例</div>' +
        '<div class="legend-item">' +
        '<span class="legend-line" style="background:' +
            CONFIG.ROUTE_LINE_COLOR + '"></span>' +
        '<span>推荐漫游路径</span></div>' +
        '<div class="legend-item">' +
        '<span style="width:14px;height:14px;border-radius:50%;background:' +
            CONFIG.ROUTE_LINE_COLOR +
            ';display:inline-block;border:2px solid #fff;' +
            'box-shadow:0 0 0 4px rgba(255,107,107,0.3);"></span>' +
        '<span>路线节点</span></div>';

    document.getElementById("map-container").appendChild(legend);
}

// ============================================================
// 模块 9: 搜索功能
// ============================================================

function initSearch() {
    const searchInput = document.getElementById("search-input");
    const searchBtn = document.getElementById("search-btn");

    searchBtn.addEventListener("click", function () {
        applyFilters();
    });

    searchInput.addEventListener("keyup", function (e) {
        if (e.key === "Enter") {
            applyFilters();
        }
    });

    // 实时搜索（300ms 防抖）
    let debounceTimer;
    searchInput.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            applyFilters();
        }, 300);
    });
}

// ============================================================
// 模块 10: 事件绑定与启动
// ============================================================

function bindEvents() {
    document.getElementById("plan-route-btn")
        .addEventListener("click", planRoute);
    document.getElementById("clear-route-btn")
        .addEventListener("click", clearAllStops);
    initSearch();
}

/**
 * 应用启动入口
 */
async function bootstrap() {
    console.log("=".repeat(50));
    console.log("  厦门美食漫游导航系统 (百度地图版) 启动中...");
    console.log("=".repeat(50));

    // 检查百度地图 API 是否加载成功
    if (typeof BMap === "undefined") {
        console.error(
            "[启动] 百度地图 JS API 未加载！" +
            "请在 index.html 中配置正确的浏览器端 AK"
        );
        alert(
            "百度地图 JS API 未加载！\n\n" +
            "请按以下步骤配置:\n" +
            "1. 前往 https://lbsyun.baidu.com/apiconsole/key 申请浏览器端 AK\n" +
            "2. 在 frontend/index.html 中将 YOUR_BAIDU_MAP_AK 替换为您的 AK\n" +
            "3. 刷新页面"
        );
        return;
    }

    // 1. 初始化地图
    initMap();

    // 2. 绑定事件
    bindEvents();

    // 3. 加载数据并渲染
    await loadPoiData();

    console.log("[启动] 系统就绪！(BD-09 坐标系)");
    console.log("=".repeat(50));
}

// ============================================================
// 页面加载完成后启动
// ============================================================
window.addEventListener("DOMContentLoaded", bootstrap);
