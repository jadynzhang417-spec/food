/**
 * server.cpp - 厦门美食漫游导航系统 C++ HTTP 后端服务
 *
 * 功能：将现有的 C++ 数据结构与算法封装为 RESTful API，
 *       供前端 index.html 调用。严格遵循课程要求的 9 种数据结构。
 *
 * 编译方法:
 *   g++ -std=c++11 -O2 server.cpp ../data_structures.cpp ../algorithms.cpp \
 *       ../data_loader.cpp ../data_saver.cpp -o food_server
 *
 * 启动: ./food_server
 * API 端口: 8080
 *
 * 坐标系: GCJ-02（高德地图），抽象坐标映射到厦门真实 GPS
 */

#include "httplib.h"
#include <iostream>
#include <cstring>
#include <cstdio>
#include <sstream>
#include <cmath>
#include <vector>

// ---- 复用现有 C++ 数据结构和算法（位于上层实训-目录） ----
#include "types.h"
#include "data_structures.h"
#include "algorithms.h"

using namespace std;

// ============================================================
// GPS 坐标映射表：12 个商圈（A-L）→ 厦门真实 GCJ-02 坐标
// ============================================================
struct GpsCoord { double lng, lat; };

const GpsCoord LANDMARK_GPS[] = {
    {118.08942, 24.45715},  // A: 中山路步行街
    {118.08709, 24.46036},  // B: 思明北路/大同路
    {118.08214, 24.45821},  // C: 八市（第八市场）
    {118.07283, 24.45329},  // D: 轮渡码头
    {118.09117, 24.45345},  // E: 中华城/思明南路
    {118.09851, 24.44072},  // F: 厦大西村
    {118.09635, 24.44328},  // G: 南普陀/南华路
    {118.08366, 24.44695},  // H: 沙坡尾
    {118.11097, 24.43763},  // I: 曾厝垵
    {118.12208, 24.43211},  // J: 环岛路/书法广场
    {118.11503, 24.47002},  // K: 火车站/梧村
    {118.12411, 24.50312}   // L: SM城市广场
};

// 商圈颜色（用于前端Marker区分）
const char* LANDMARK_COLORS[] = {
    "#FF6B6B", "#FF9F43", "#FECA57", "#54A0FF",
    "#5F27CD", "#01A3A4", "#10AC84", "#EE5A24",
    "#FF6B6B", "#48DBFB", "#C39BD3", "#F368E0"
};

// ============================================================
// 全局变量
// ============================================================
DynamicArray  g_foodDB;
HashTable     g_hashTable;
Graph         g_graph;
ActionStack   g_history;
FavoritesList g_favorites;
RankingHeap   g_rankingHeap;

// ============================================================
// JSON 构建辅助函数（不依赖第三方库，手动拼接）
// ============================================================

/** JSON 字符串转义 */
string jsonEscape(const string& s) {
    string out;
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:   out += c;
        }
    }
    return out;
}

/** 将坐标映射到 GPS（基于最近商圈 + XY偏移） */
GpsCoord mapToGps(int x, int y) {
    // 找最近商圈
    int nearest = findNearestLandmark(x, y);
    if (nearest < 0 || nearest >= 12) nearest = 0;

    // 基于原始 XY 坐标计算微调偏移（缩放因子）
    // 抽象坐标范围大致 x∈[5,65], y∈[5,42]
    double scaleX = 0.0015;  // 经度缩放
    double scaleY = 0.0015;  // 纬度缩放
    double centerX = 35.0, centerY = 25.0;  // 抽象坐标中心

    GpsCoord gps;
    gps.lng = LANDMARK_GPS[nearest].lng + (x - LANDMARK_X[nearest]) * scaleX;
    gps.lat = LANDMARK_GPS[nearest].lat + (y - LANDMARK_Y[nearest]) * scaleY;
    return gps;
}

/** 构建单个 Restaurant → JSON 对象字符串 */
string restaurantToJson(const Restaurant& r, bool includeTags = true) {
    GpsCoord gps = mapToGps(r.x, r.y);
    char buf[2048];

    // 标签数组
    string tagsJson = "[";
    if (includeTags && r.tagCount > 0) {
        for (int i = 0; i < r.tagCount; i++) {
            if (i > 0) tagsJson += ",";
            tagsJson += "\"" + jsonEscape(r.tags[i]) + "\"";
        }
    }
    tagsJson += "]";

    // 寻找最近的商圈
    int nearest = findNearestLandmark(r.x, r.y);
    const char* area = (nearest >= 0) ? LANDMARK_NAMES[nearest] : "未知";
    const char* color = (nearest >= 0) ? LANDMARK_COLORS[nearest] : "#999999";

    snprintf(buf, sizeof(buf),
        "{\"id\":%d,\"name\":\"%s\",\"lng\":%.6f,\"lat\":%.6f,"
        "\"signature\":\"%s\",\"price\":%d,\"rating\":%.1f,"
        "\"tags\":%s,\"food_area\":\"%s\",\"area_color\":\"%s\"}",
        r.id,
        jsonEscape(r.name).c_str(),
        gps.lng, gps.lat,
        jsonEscape(r.signature).c_str(),
        r.price, r.rating,
        tagsJson.c_str(),
        jsonEscape(area).c_str(),
        color
    );
    return string(buf);
}

/** 构建单个 Landmark → JSON 字符串 */
string landmarkToJson(int idx) {
    char buf[512];
    snprintf(buf, sizeof(buf),
        "{\"id\":\"%c\",\"name\":\"%s\",\"lng\":%.6f,\"lat\":%.6f,"
        "\"x\":%d,\"y\":%d,\"color\":\"%s\"}",
        'A' + idx,
        jsonEscape(LANDMARK_NAMES[idx]).c_str(),
        LANDMARK_GPS[idx].lng, LANDMARK_GPS[idx].lat,
        LANDMARK_X[idx], LANDMARK_Y[idx],
        LANDMARK_COLORS[idx]
    );
    return string(buf);
}

// ============================================================
// C++ 后端 → 全局初始化（复用现有 loader）
// ============================================================
#include "data_loader.h"   // loadFoodData, loadRoadData
#include "data_saver.h"

void initBackend() {
    cout << "[C++后端] 正在初始化..." << endl;

    // 1. 初始化所有数据结构
    da_init(&g_foodDB);
    ht_init(&g_hashTable);
    graph_init(&g_graph);
    stack_init(&g_history);
    fav_init(&g_favorites);
    heap_init(&g_rankingHeap, 0);  // 默认按人气排序

    // 2. 加载数据文件（路径相对于可执行文件所在目录）
    string basePath = "../";
    string foodFile = basePath + "food.txt";
    string roadsFile = basePath + "roads.txt";

    if (!loadFoodData(foodFile.c_str(), &g_foodDB, &g_hashTable)) {
        // 尝试其他路径
        foodFile = "food.txt";
        if (!loadFoodData(foodFile.c_str(), &g_foodDB, &g_hashTable)) {
            cerr << "[错误] 无法加载 food.txt" << endl;
            exit(1);
        }
    }

    if (!loadRoadData(roadsFile.c_str(), &g_graph)) {
        roadsFile = "roads.txt";
        if (!loadRoadData(roadsFile.c_str(), &g_graph)) {
            cerr << "[错误] 无法加载 roads.txt" << endl;
            exit(1);
        }
    }

    // 3. 构建排行榜堆
    heap_buildFromArray(&g_rankingHeap, &g_foodDB);

    // 4. 尝试恢复收藏和历史
    string favFile = basePath + "favorite.txt";
    fav_loadFromFile(&g_favorites, favFile.c_str());
    string histFile = basePath + "history.txt";
    stack_loadFromFile(&g_history, histFile.c_str());

    cout << "[C++后端] 初始化完成: " << g_foodDB.size << " 个门店, "
         << g_graph.numNodes << " 个商圈" << endl;
}

void shutdownBackend() {
    cout << "[C++后端] 正在保存数据..." << endl;
    fav_saveToFile(&g_favorites, "favorite.txt");
    stack_saveToFile(&g_history, "history.txt");
    cout << "[C++后端] 数据已保存，服务关闭" << endl;
}

// ============================================================
// HTTP API 路由定义
// ============================================================

void setupRoutes(httplib::Server& svr) {

    // ---- CORS 支持 ----
    svr.set_pre_routing_handler([](const httplib::Request& req, httplib::Response& res) {
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type");
        if (req.method == "OPTIONS") {
            res.status = 204;
            return httplib::Server::HandlerResponse::Handled;
        }
        return httplib::Server::HandlerResponse::Unhandled;
    });

    // ============================================================
    // GET /api/health — 健康检查
    // ============================================================
    svr.Get("/api/health", [](const httplib::Request&, httplib::Response& res) {
        char buf[256];
        snprintf(buf, sizeof(buf),
            "{\"status\":\"ok\",\"poi_count\":%d,\"landmark_count\":%d}",
            g_foodDB.size, g_graph.numNodes);
        res.set_content(buf, "application/json");
    });

    // ============================================================
    // GET /api/landmarks — 返回 12 个商圈 GPS 坐标
    // ============================================================
    svr.Get("/api/landmarks", [](const httplib::Request&, httplib::Response& res) {
        string json = "{\"landmarks\":[";
        for (int i = 0; i < 12; i++) {
            if (i > 0) json += ",";
            json += landmarkToJson(i);
        }
        json += "]}";
        res.set_content(json, "application/json");
    });

    // ============================================================
    // GET /api/shops — 获取门店列表
    // 查询参数:
    //   ?tag=沙茶面   — 哈希表标签检索
    //   ?search=黄则和 — 模糊名称搜索
    //   ?landmark=A    — 按最近商圈筛选
    //   ?limit=20      — 限制数量
    // ============================================================
    svr.Get("/api/shops", [](const httplib::Request& req, httplib::Response& res) {
        int indices[100];
        int resultCount = 0;

        if (req.has_param("tag")) {
            // ---- 链地址哈希表 O(1) 检索 ----
            string tag = req.get_param_value("tag");
            // 确保标签带 # 前缀
            string tagWithHash = (tag[0] == '#') ? tag : ("#" + tag);
            resultCount = searchByTag(&g_foodDB, &g_hashTable,
                                      tagWithHash.c_str(), indices, 100);
        } else if (req.has_param("search")) {
            // ---- 模糊名称搜索 ----
            string name = req.get_param_value("search");
            resultCount = searchByName(&g_foodDB, name.c_str(), indices, 100);
        } else {
            // ---- 返回全部（按顺序） ----
            resultCount = g_foodDB.size;
            for (int i = 0; i < resultCount; i++) indices[i] = i;
        }

        // 按商圈筛选
        if (req.has_param("landmark")) {
            string lm = req.get_param_value("landmark");
            int lmIdx = landmarkCharToIndex(lm[0]);
            if (lmIdx >= 0 && lmIdx < 12) {
                int filtered[100], fc = 0;
                for (int i = 0; i < resultCount; i++) {
                    Restaurant* r = da_get(&g_foodDB, indices[i]);
                    if (r && findNearestLandmark(r->x, r->y) == lmIdx) {
                        filtered[fc++] = indices[i];
                    }
                }
                resultCount = fc;
                for (int i = 0; i < fc; i++) indices[i] = filtered[i];
            }
        }

        // 限制数量
        int limit = resultCount;
        if (req.has_param("limit")) {
            limit = atoi(req.get_param_value("limit").c_str());
            if (limit > resultCount) limit = resultCount;
        }

        // 构建 JSON 响应
        string json = "{\"count\":" + to_string(limit) + ",\"shops\":[";
        for (int i = 0; i < limit; i++) {
            if (i > 0) json += ",";
            Restaurant* r = da_get(&g_foodDB, indices[i]);
            if (r) json += restaurantToJson(*r);
        }
        json += "]}";
        res.set_content(json, "application/json");
    });

    // ============================================================
    // GET /api/shops/:id — 单个门店详情
    // ============================================================
    svr.Get(R"(/api/shops/(\d+))", [](const httplib::Request& req, httplib::Response& res) {
        int id = atoi(req.matches[1].str().c_str());
        int idx = da_findById(&g_foodDB, id);
        if (idx < 0) {
            res.set_content("{\"error\":\"门店不存在\"}", "application/json");
            return;
        }
        Restaurant* r = da_get(&g_foodDB, idx);
        res.set_content(restaurantToJson(*r), "application/json");
    });

    // ============================================================
    // POST /api/route — Dijkstra 最短路径规划
    // Body: {"from": "A", "to": "H"}
    // 返回: 路径节点序列 + 总耗时
    // ============================================================
    svr.Post("/api/route", [](const httplib::Request& req, httplib::Response& res) {
        // 解析简易 JSON body
        string body = req.body;
        char fromChar = 0, toChar = 0;

        // 简易解析 "from":"X"
        size_t pos = body.find("\"from\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 7);
            if (pos != string::npos) fromChar = body[pos + 1];
        }
        pos = body.find("\"to\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 5);
            if (pos != string::npos) toChar = body[pos + 1];
        }

        if (!fromChar || !toChar) {
            res.set_content("{\"error\":\"请提供 from 和 to 参数（如 A, H）\"}",
                           "application/json");
            return;
        }

        int start = landmarkCharToIndex(fromChar);
        int end = landmarkCharToIndex(toChar);

        if (start < 0 || end < 0 || start >= 12 || end >= 12) {
            res.set_content("{\"error\":\"无效的商圈编号，请使用 A-L\"}",
                           "application/json");
            return;
        }

        // ---- 运行 Dijkstra 算法（基于邻接表） ----
        int* dist = new int[12];
        int* prev = new int[12];
        graph_dijkstra(&g_graph, start, dist, prev);

        if (dist[end] >= INF) {
            delete[] dist; delete[] prev;
            res.set_content("{\"error\":\"两点之间不可达\"}", "application/json");
            return;
        }

        // ---- 回溯路径 ----
        int pathNodes[12];
        int pathLen = 0;
        int cur = end;
        while (cur != -1) {
            pathNodes[pathLen++] = cur;
            cur = prev[cur];
        }
        // 反转
        for (int i = 0; i < pathLen / 2; i++) {
            swap(pathNodes[i], pathNodes[pathLen - 1 - i]);
        }

        // ---- 构建路径 JSON ----
        string json = "{\"path\":[";
        for (int i = 0; i < pathLen; i++) {
            if (i > 0) json += ",";
            json += landmarkToJson(pathNodes[i]);
        }
        json += "],\"segments\":[";
        for (int i = 0; i < pathLen - 1; i++) {
            if (i > 0) json += ",";
            char seg[256];
            // 从邻接表查找边权
            int segWeight = 0;
            EdgeNode* e = g_graph.adjList[pathNodes[i]];
            while (e) {
                if (e->to == pathNodes[i + 1]) { segWeight = e->weight; break; }
                e = e->next;
            }
            snprintf(seg, sizeof(seg),
                "{\"from\":\"%c\",\"to\":\"%c\",\"weight\":%d}",
                'A' + pathNodes[i], 'A' + pathNodes[i + 1], segWeight);
            json += seg;
        }
        json += "],\"total_time\":" + to_string(dist[end]) +
                ",\"node_count\":" + to_string(pathLen) + "}";

        delete[] dist; delete[] prev;
        res.set_content(json, "application/json");
    });

    // ============================================================
    // GET /api/explore — BFS 限时周边探索（15分钟美食圈）
    // 参数: ?landmark=A&time=15
    // ============================================================
    svr.Get("/api/explore", [](const httplib::Request& req, httplib::Response& res) {
        string lm = req.get_param_value("landmark");
        int start = landmarkCharToIndex(lm.empty() ? 'A' : lm[0]);
        int timeLimit = 15;
        if (req.has_param("time")) timeLimit = atoi(req.get_param_value("time").c_str());

        if (start < 0 || start >= 12) {
            res.set_content("{\"error\":\"无效的商圈编号\"}", "application/json");
            return;
        }

        // ---- BFS 广度搜索 ----
        DynamicArray results;
        da_init(&results);
        graph_bfsFoodCircle(&g_graph, start, timeLimit, &g_foodDB, &results);

        string json = "{\"landmark\":\"" + lm + "\",\"time_limit\":" +
                      to_string(timeLimit) + ",\"count\":" +
                      to_string(results.size) + ",\"shops\":[";
        for (int i = 0; i < results.size; i++) {
            if (i > 0) json += ",";
            json += restaurantToJson(results.data[i]);
        }
        json += "]}";

        da_free(&results);
        res.set_content(json, "application/json");
    });

    // ============================================================
    // GET /api/ranking — Top-K 排行榜（堆排序）
    // 参数: ?mode=0&k=10   (mode: 0=人气, 1=性价比)
    // ============================================================
    svr.Get("/api/ranking", [](const httplib::Request& req, httplib::Response& res) {
        int mode = 0, k = 10;
        if (req.has_param("mode")) mode = atoi(req.get_param_value("mode").c_str());
        if (req.has_param("k"))    k = atoi(req.get_param_value("k").c_str());

        // ---- 堆排序获取 Top-K ----
        if (g_rankingHeap.mode != mode) {
            heap_switchMode(&g_rankingHeap, &g_foodDB, mode);
        }

        // 复制堆数据并排序
        int heapSize = g_rankingHeap.size;
        HeapNode* tmpHeap = new HeapNode[heapSize];
        for (int i = 0; i < heapSize; i++) {
            tmpHeap[i] = g_rankingHeap.data[i];
        }

        // 堆排序（降序）
        for (int i = heapSize - 1; i >= 0; i--) {
            swap(tmpHeap[0], tmpHeap[i]);
            // siftDown on reduced heap
            int idx = 0;
            while (true) {
                int largest = idx;
                int left = 2 * idx + 1;
                int right = 2 * idx + 2;
                if (left < i && tmpHeap[left].key > tmpHeap[largest].key)
                    largest = left;
                if (right < i && tmpHeap[right].key > tmpHeap[largest].key)
                    largest = right;
                if (largest == idx) break;
                swap(tmpHeap[idx], tmpHeap[largest]);
                idx = largest;
            }
        }

        if (k > heapSize) k = heapSize;

        // 构建 JSON
        string json = "{\"mode\":" + to_string(mode) +
                      ",\"mode_name\":\"" + string(mode == 0 ? "人气" : "性价比") +
                      "\",\"count\":" + to_string(k) + ",\"ranking\":[";
        for (int i = 0; i < k; i++) {
            if (i > 0) json += ",";
            Restaurant* r = &tmpHeap[i].data;
            char buf[512];
            snprintf(buf, sizeof(buf),
                "{\"rank\":%d,\"shop\":%s,\"key\":%.2f}",
                i + 1, restaurantToJson(*r, false).c_str(), tmpHeap[i].key);
            json += buf;
        }
        json += "]}";

        delete[] tmpHeap;
        res.set_content(json, "application/json");
    });

    // ============================================================
    // GET /api/favorites — 收藏夹（双向链表遍历）
    // POST /api/favorites — 添加/删除收藏
    //   Body: {"action": "add", "shop_id": 1}
    //         {"action": "remove", "shop_id": 1}
    // ============================================================
    svr.Get("/api/favorites", [](const httplib::Request&, httplib::Response& res) {
        string json = "{\"count\":" + to_string(g_favorites.count) + ",\"favorites\":[";

        // ---- 双向链表前向遍历 ----
        FavNode* node = g_favorites.head;
        bool first = true;
        while (node) {
            if (!first) json += ",";
            json += restaurantToJson(node->data);
            node = node->next;
            first = false;
        }
        json += "]}";
        res.set_content(json, "application/json");
    });

    svr.Post("/api/favorites", [](const httplib::Request& req, httplib::Response& res) {
        string body = req.body;
        string action, shopIdStr;

        // 简易 JSON 解析
        size_t pos = body.find("\"action\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 9);
            if (pos != string::npos) {
                size_t end = body.find("\"", pos + 1);
                action = body.substr(pos + 1, end - pos - 1);
            }
        }
        pos = body.find("\"shop_id\"");
        if (pos != string::npos) {
            pos = body.find(":", pos);
            if (pos != string::npos) {
                while (pos < body.length() &&
                       (body[pos] < '0' || body[pos] > '9')) pos++;
                while (pos < body.length() &&
                       body[pos] >= '0' && body[pos] <= '9') {
                    shopIdStr += body[pos++];
                }
            }
        }

        int shopId = shopIdStr.empty() ? -1 : atoi(shopIdStr.c_str());
        int idx = da_findById(&g_foodDB, shopId);

        if (action == "add" && idx >= 0) {
            Restaurant* r = da_get(&g_foodDB, idx);
            // ---- 双向链表头部插入 ----
            bool ok = fav_add(&g_favorites, *r);
            if (ok) {
                // ---- 顺序栈压入撤销记录 ----
                stack_push(&g_history, ("收藏门店: " + string(r->name)).c_str(),
                          UNDO_FAV_ADD, r->id, r);
                res.set_content("{\"status\":\"ok\",\"action\":\"added\"}",
                               "application/json");
            } else {
                res.set_content("{\"status\":\"duplicate\"}", "application/json");
            }
        } else if (action == "remove" && idx >= 0) {
            Restaurant* r = da_get(&g_foodDB, idx);
            stack_push(&g_history, ("取消收藏: " + string(r->name)).c_str(),
                      UNDO_FAV_REMOVE, r->id, r);
            fav_remove(&g_favorites, shopId);
            res.set_content("{\"status\":\"ok\",\"action\":\"removed\"}",
                           "application/json");
        } else {
            res.set_content("{\"error\":\"无效的请求参数\"}", "application/json");
        }
    });

    // ============================================================
    // POST /api/undo — 撤销操作（顺序栈弹出）
    // ============================================================
    svr.Post("/api/undo", [](const httplib::Request&, httplib::Response& res) {
        if (stack_isEmpty(&g_history)) {
            res.set_content("{\"status\":\"empty\",\"message\":\"无可撤销的操作\"}",
                           "application/json");
            return;
        }

        // ---- 顺序栈弹出 ----
        HistoryNode node;
        if (!stack_pop(&g_history, &node)) {
            res.set_content("{\"status\":\"error\"}", "application/json");
            return;
        }

        // 执行撤销
        switch (node.undoType) {
            case UNDO_FAV_ADD:
                fav_remove(&g_favorites, node.undoId);
                break;
            case UNDO_FAV_REMOVE:
                fav_add(&g_favorites, node.undoRestaurant);
                break;
            case UNDO_FAV_CLEAR:
                // 无法恢复清除操作
                break;
            default:
                break;
        }

        char buf[512];
        snprintf(buf, sizeof(buf),
            "{\"status\":\"ok\",\"undone\":\"%s\"}", node.action);
        res.set_content(buf, "application/json");
    });

    // ============================================================
    // GET /api/history — 操作历史
    // ============================================================
    svr.Get("/api/history", [](const httplib::Request&, httplib::Response& res) {
        string json = "{\"history\":[";

        // 顺序栈从底到顶遍历
        for (int i = 0; i <= g_history.top; i++) {
            if (i > 0) json += ",";
            json += "\"" + jsonEscape(g_history.data[i].action) + "\"";
        }
        json += "]}";
        res.set_content(json, "application/json");
    });

    // ============================================================
    // POST /api/filter — 决策树多条件筛选
    // Body: {"budget": 50, "tag": "海鲜", "landmark": "A"}
    // 返回符合条件的门店
    // ============================================================
    svr.Post("/api/filter", [](const httplib::Request& req, httplib::Response& res) {
        string body = req.body;

        // 解析参数
        int budget = 9999;
        string tagFilter, landmarkFilter;

        size_t pos = body.find("\"budget\"");
        if (pos != string::npos) {
            pos = body.find(":", pos);
            if (pos != string::npos) {
                while (pos < body.length() &&
                       (body[pos] < '0' || body[pos] > '9')) pos++;
                budget = atoi(body.c_str() + pos);
            }
        }

        pos = body.find("\"tag\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 6);
            if (pos != string::npos) {
                size_t end = body.find("\"", pos + 1);
                tagFilter = body.substr(pos + 1, end - pos - 1);
            }
        }

        pos = body.find("\"landmark\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 11);
            if (pos != string::npos) {
                size_t end = body.find("\"", pos + 1);
                landmarkFilter = body.substr(pos + 1, end - pos - 1);
            }
        }

        // ---- 决策树：逐层过滤 ----
        // 第一层：预算
        int indices[100], count = 0;
        for (int i = 0; i < g_foodDB.size; i++) {
            if (g_foodDB.data[i].price <= budget) {
                indices[count++] = i;
            }
        }

        // 第二层：标签（哈希表快速查找）
        if (!tagFilter.empty() && count > 0) {
            int tagIndices[100], tagCount;
            string tagWithHash = (tagFilter[0] == '#') ? tagFilter : ("#" + tagFilter);
            tagCount = searchByTag(&g_foodDB, &g_hashTable,
                                   tagWithHash.c_str(), tagIndices, 100);
            // 取交集
            int newIndices[100], newCount = 0;
            for (int i = 0; i < count; i++) {
                for (int j = 0; j < tagCount; j++) {
                    if (indices[i] == tagIndices[j]) {
                        newIndices[newCount++] = indices[i];
                        break;
                    }
                }
            }
            count = newCount;
            for (int i = 0; i < count; i++) indices[i] = newIndices[i];
        }

        // 第三层：商圈
        if (!landmarkFilter.empty() && count > 0) {
            int lmIdx = landmarkCharToIndex(landmarkFilter[0]);
            if (lmIdx >= 0) {
                int newIndices[100], newCount = 0;
                for (int i = 0; i < count; i++) {
                    if (findNearestLandmark(
                            g_foodDB.data[indices[i]].x,
                            g_foodDB.data[indices[i]].y) == lmIdx) {
                        newIndices[newCount++] = indices[i];
                    }
                }
                count = newCount;
                for (int i = 0; i < count; i++) indices[i] = newIndices[i];
            }
        }

        // 构建响应
        string json = "{\"count\":" + to_string(count) + ",\"shops\":[";
        for (int i = 0; i < count; i++) {
            if (i > 0) json += ",";
            json += restaurantToJson(g_foodDB.data[indices[i]]);
        }
        json += "]}";
        res.set_content(json, "application/json");
    });

    // ============================================================
    // POST /api/smart-route — 智能一日游多分类必经点路线规划
    // Body: {"categories":["#沙茶面","#海鲜","#甜品"],"start":"A"}
    // 每类筛选评分最高的门店作为必经点，链式 Dijkstra 规划
    // ============================================================
    svr.Post("/api/smart-route", [](const httplib::Request& req, httplib::Response& res) {
        string body = req.body;

        // --- 解析 start ---
        char startChar = 'A';
        size_t pos = body.find("\"start\"");
        if (pos != string::npos) {
            pos = body.find("\"", pos + 8);
            if (pos != string::npos && pos + 1 < body.length()) startChar = body[pos + 1];
        }

        // --- 解析 categories 数组 ---
        vector<string> categories;
        pos = body.find("\"categories\"");
        if (pos != string::npos) {
            pos = body.find("[", pos);
            if (pos != string::npos) {
                while (pos < body.length()) {
                    pos = body.find("\"", pos);
                    if (pos == string::npos) break;
                    size_t end = body.find("\"", pos + 1);
                    if (end == string::npos) break;
                    string cat = body.substr(pos + 1, end - pos - 1);
                    if (!cat.empty()) categories.push_back(cat);
                    pos = end + 1;
                    if (body.find("]", end) < body.find("\"", end + 1)) break;
                }
            }
        }

        if (categories.empty()) {
            res.set_content("{\"error\":\"请提供至少1个美食分类\"}", "application/json");
            return;
        }

        int startIdx = landmarkCharToIndex(startChar);
        if (startIdx < 0 || startIdx >= 12) {
            res.set_content("{\"error\":\"无效的起点商圈编号\"}", "application/json");
            return;
        }

        // --- 每类选评分最高的门店 ---
        struct Picked { int shopIdx; string catName; };
        vector<Picked> waypoints;

        for (size_t c = 0; c < categories.size(); c++) {
            string cat = categories[c];
            // 确保 # 前缀
            if (!cat.empty() && cat[0] != '#') cat = "#" + cat;

            int indices[100];
            int count = searchByTag(&g_foodDB, &g_hashTable, cat.c_str(), indices, 100);
            if (count == 0) continue;

            // 找评分最高的
            int bestIdx = indices[0];
            float bestRating = g_foodDB.data[indices[0]].rating;
            for (int i = 1; i < count; i++) {
                if (g_foodDB.data[indices[i]].rating > bestRating) {
                    bestRating = g_foodDB.data[indices[i]].rating;
                    bestIdx = indices[i];
                }
            }
            waypoints.push_back({bestIdx, cat});
        }

        if (waypoints.empty()) {
            res.set_content("{\"error\":\"未找到匹配分类的门店\"}", "application/json");
            return;
        }

        // --- 链式 Dijkstra: start → wp[0] → wp[1] → ... ---
        string json = "{\"categories\":[";
        for (size_t c = 0; c < categories.size(); c++) {
            if (c > 0) json += ",";
            json += "\"" + jsonEscape(categories[c]) + "\"";
        }
        json += "],\"waypoints\":[";

        int totalTime = 0;
        int totalNodes = 0;
        string pathJson = "";
        string segmentsJson = "";

        int prevNode = startIdx;
        for (size_t w = 0; w < waypoints.size(); w++) {
            // 找该门店最近的商圈
            Restaurant* shop = &g_foodDB.data[waypoints[w].shopIdx];
            int nearestLm = findNearestLandmark(shop->x, shop->y);

            // Dijkstra
            int* dist = new int[12];
            int* prev = new int[12];
            graph_dijkstra(&g_graph, prevNode, dist, prev);

            if (dist[nearestLm] >= INF) {
                delete[] dist; delete[] prev;
                // 不可达时跳过该点
                continue;
            }

            // 回溯路径
            int pathNodes[12], pathLen = 0;
            int cur = nearestLm;
            while (cur != -1) {
                pathNodes[pathLen++] = cur;
                cur = prev[cur];
            }
            for (int i = 0; i < pathLen / 2; i++)
                swap(pathNodes[i], pathNodes[pathLen - 1 - i]);

            totalTime += dist[nearestLm];
            totalNodes += pathLen;

            // 构建该段路径 JSON
            for (int i = (w == 0 ? 0 : 1); i < pathLen; i++) {
                if (!pathJson.empty()) pathJson += ",";
                pathJson += landmarkToJson(pathNodes[i]);
            }
            for (int i = 0; i < pathLen - 1; i++) {
                if (!segmentsJson.empty()) segmentsJson += ",";
                int segW = 0;
                EdgeNode* e = g_graph.adjList[pathNodes[i]];
                while (e) { if (e->to == pathNodes[i+1]) { segW = e->weight; break; } e = e->next; }
                char seg[256];
                snprintf(seg, sizeof(seg),
                    "{\"from\":\"%c\",\"to\":\"%c\",\"weight\":%d}",
                    'A' + pathNodes[i], 'A' + pathNodes[i + 1], segW);
                segmentsJson += seg;
            }

            // 中间点 JSON
            if (w > 0) json += ",";
            json += "{\"category\":\"" + jsonEscape(waypoints[w].catName) +
                    "\",\"shop\":" + restaurantToJson(*shop) + "}";

            delete[] dist; delete[] prev;
            prevNode = nearestLm;
        }

        json += "],\"path\":[" + pathJson + "],\"segments\":[" + segmentsJson +
                "],\"total_time\":" + to_string(totalTime) +
                ",\"node_count\":" + to_string(totalNodes) + "}";

        res.set_content(json, "application/json");
    });

    // ============================================================
    // POST /api/save — 立即持久化数据到文件
    // ============================================================
    svr.Post("/api/save", [](const httplib::Request&, httplib::Response& res) {
        fav_saveToFile(&g_favorites, "favorite.txt");
        stack_saveToFile(&g_history, "history.txt");
        cout << "[持久化] 数据已保存至 favorite.txt + history.txt" << endl;
        res.set_content("{\"status\":\"ok\",\"saved\":\"favorites+history\"}", "application/json");
    });

    // ============================================================
    // GET /api/tags — 所有可用标签列表
    // ============================================================
    svr.Get("/api/tags", [](const httplib::Request&, httplib::Response& res) {
        // 收集所有标签（遍历哈希表桶）
        string json = "{\"tags\":[";
        bool first = true;
        for (int i = 0; i < HASH_TABLE_SIZE; i++) {
            HashNode* node = g_hashTable.buckets[i];
            while (node) {
                if (node->count > 0) {
                    if (!first) json += ",";
                    json += "{\"name\":\"" + jsonEscape(node->tag) +
                            "\",\"count\":" + to_string(node->count) + "}";
                    first = false;
                }
                node = node->next;
            }
        }
        json += "]}";
        res.set_content(json, "application/json");
    });
}

// ============================================================
// 主函数
// ============================================================
int main(int argc, char* argv[]) {
    // 切换到数据文件所在目录
    // 支持从 backend_cpp/ 目录运行

    cout << "========================================" << endl;
    cout << "  厦门美食漫游导航系统 - C++ 后端服务" << endl;
    cout << "  数据结构: 动态顺序表|哈希表|邻接图|栈|双向链表|堆|决策树" << endl;
    cout << "========================================" << endl;

    initBackend();

    httplib::Server svr;

    setupRoutes(svr);

    int port = 8080;
    if (argc > 1) port = atoi(argv[1]);

    cout << "\n[C++后端] API 端点:" << endl;
    cout << "  GET  /api/health" << endl;
    cout << "  GET  /api/landmarks" << endl;
    cout << "  GET  /api/shops?tag=X&search=X&landmark=X" << endl;
    cout << "  GET  /api/shops/:id" << endl;
    cout << "  POST /api/route     {\"from\":\"A\",\"to\":\"H\"}" << endl;
    cout << "  GET  /api/explore?landmark=A&time=15" << endl;
    cout << "  GET  /api/ranking?mode=0&k=10" << endl;
    cout << "  GET  /api/favorites" << endl;
    cout << "  POST /api/favorites {\"action\":\"add\",\"shop_id\":1}" << endl;
    cout << "  POST /api/undo" << endl;
    cout << "  GET  /api/history" << endl;
    cout << "  POST /api/filter    {\"budget\":50,\"tag\":\"海鲜\",\"landmark\":\"A\"}" << endl;
    cout << "  GET  /api/tags" << endl;
    cout << "\n[C++后端] 监听端口: " << port << endl;

    // 注册退出回调
    atexit(shutdownBackend);

    svr.listen("0.0.0.0", port);

    return 0;
}
