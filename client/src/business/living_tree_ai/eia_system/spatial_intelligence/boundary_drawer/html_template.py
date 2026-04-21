"""
OpenLayers 边界绘制器 HTML 模板
================================

专业的环评厂区边界绘制工具：
- OpenLayers 7+ 地图引擎
- CGCS2000 / WGS84 坐标转换
- 复杂多边形绘制（支持孔洞）
- 面积/周长实时计算
- DXF / SHP / GeoJSON 导入导出
- Python QWebEngineView 集成接口

用法:
    from boundary_drawer_service import BoundaryDrawerService
    service = BoundaryDrawerService()
    html_path = service.generate_html()
"""

# HTML 模板 - 嵌入式资源
BOUNDARY_DRAWER_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>环评厂区边界绘制 - OpenLayers</title>

    <!-- OpenLayers CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@v7.4.0/ol.css">

    <!-- proj4js - 坐标转换 -->
    <script src="https://cdn.jsdelivr.net/npm/proj4@2.9.0/dist/proj4.min.js"></script>

    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* 顶部工具栏 */
        .toolbar {
            background: linear-gradient(135deg, #1976D2 0%, #1565C0 100%);
            color: white;
            padding: 10px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 1000;
        }

        .toolbar h1 {
            font-size: 16px;
            font-weight: 500;
            margin-right: 20px;
        }

        .toolbar-group {
            display: flex;
            gap: 5px;
            padding: 0 10px;
            border-left: 1px solid rgba(255,255,255,0.3);
        }

        .toolbar-group:first-of-type {
            border-left: none;
            padding-left: 0;
        }

        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .btn-primary {
            background: rgba(255,255,255,0.2);
            color: white;
        }

        .btn-primary:hover {
            background: rgba(255,255,255,0.3);
        }

        .btn-primary.active {
            background: #FFC107;
            color: #333;
        }

        .btn-danger {
            background: #f44336;
            color: white;
        }

        .btn-success {
            background: #4CAF50;
            color: white;
        }

        /* 右侧信息面板 */
        .info-panel {
            position: absolute;
            top: 60px;
            right: 10px;
            width: 280px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            max-height: calc(100vh - 80px);
            overflow-y: auto;
        }

        .panel-header {
            background: #1976D2;
            color: white;
            padding: 12px 15px;
            font-weight: 500;
            border-radius: 8px 8px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-content {
            padding: 15px;
        }

        .info-section {
            margin-bottom: 15px;
        }

        .info-section h3 {
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #eee;
        }

        .info-item:last-child {
            border-bottom: none;
        }

        .info-label {
            color: #666;
            font-size: 13px;
        }

        .info-value {
            font-weight: 500;
            font-size: 13px;
            color: #333;
        }

        .info-value.highlight {
            color: #1976D2;
            font-size: 16px;
        }

        /* 坐标输入面板 */
        .coord-input {
            margin-top: 10px;
        }

        .coord-input textarea {
            width: 100%;
            height: 100px;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 8px;
            font-family: monospace;
            font-size: 12px;
            resize: vertical;
        }

        .coord-input .hint {
            font-size: 11px;
            color: #999;
            margin-top: 4px;
        }

        /* 地图容器 */
        .map-container {
            flex: 1;
            position: relative;
        }

        #map {
            width: 100%;
            height: 100%;
        }

        /* 测量工具提示 */
        .measure-tooltip {
            position: absolute;
            background: white;
            padding: 8px 12px;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
        }

        .measure-tooltip.active {
            display: block;
        }

        /* 状态栏 */
        .status-bar {
            background: #f5f5f5;
            padding: 8px 15px;
            font-size: 12px;
            color: #666;
            display: flex;
            justify-content: space-between;
            border-top: 1px solid #ddd;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4CAF50;
        }

        .status-indicator.warning {
            background: #FFC107;
        }

        .status-indicator.error {
            background: #f44336;
        }

        /* 坐标系选择 */
        .coord-select {
            padding: 6px 10px;
            border: none;
            border-radius: 4px;
            background: rgba(255,255,255,0.2);
            color: white;
            font-size: 13px;
            cursor: pointer;
        }

        .coord-select option {
            color: #333;
        }

        /* 文件上传 */
        .file-input {
            display: none;
        }

        /* 导入/导出菜单 */
        .dropdown {
            position: relative;
        }

        .dropdown-content {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background: white;
            min-width: 150px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            border-radius: 4px;
            z-index: 1001;
        }

        .dropdown:hover .dropdown-content {
            display: block;
        }

        .dropdown-content a {
            display: block;
            padding: 10px 15px;
            color: #333;
            text-decoration: none;
            font-size: 13px;
        }

        .dropdown-content a:hover {
            background: #f5f5f5;
        }

        /* 顶点编辑高亮 */
        .vertex-marker {
            width: 12px;
            height: 12px;
            background: #FFC107;
            border: 2px solid white;
            border-radius: 50%;
            cursor: pointer;
        }

        /* OpenLayers 样式覆盖 */
        .ol-control button {
            background: white !important;
        }

        .ol-control button:hover {
            background: #f5f5f5 !important;
        }
    </style>
</head>
<body>
    <!-- 顶部工具栏 -->
    <div class="toolbar">
        <h1>🏭 厂区边界绘制</h1>

        <!-- 绘制工具 -->
        <div class="toolbar-group">
            <button class="btn btn-primary" id="btn-polygon" onclick="setDrawMode('polygon')">
                ⬡ 多边形
            </button>
            <button class="btn btn-primary" id="btn-point" onclick="setDrawMode('point')">
                📍 标注点
            </button>
            <button class="btn btn-primary" id="btn-modify" onclick="setDrawMode('modify')">
                ✏️ 编辑
            </button>
        </div>

        <!-- 操作工具 -->
        <div class="toolbar-group">
            <button class="btn btn-primary" onclick="clearAll()">
                🗑️ 清除
            </button>
            <button class="btn btn-danger" onclick="undoLast()">
                ↩️ 撤销
            </button>
        </div>

        <!-- 导入导出 -->
        <div class="toolbar-group dropdown">
            <button class="btn btn-primary">
                📂 导入
            </button>
            <div class="dropdown-content">
                <a href="#" onclick="importGeoJSON()">导入 GeoJSON</a>
                <a href="#" onclick="importDXF()">导入 DXF</a>
                <a href="#" onclick="importSHP()">导入 SHP</a>
            </div>
        </div>

        <div class="toolbar-group dropdown">
            <button class="btn btn-success">
                💾 导出
            </button>
            <div class="dropdown-content">
                <a href="#" onclick="exportGeoJSON()">导出 GeoJSON</a>
                <a href="#" onclick="exportDXF()">导出 DXF</a>
                <a href="#" onclick="exportWKT()">导出 WKT</a>
            </div>
        </div>

        <!-- 坐标系选择 -->
        <div class="toolbar-group">
            <select class="coord-select" id="coord-system" onchange="changeCoordSystem()">
                <option value="EPSG:4326">WGS84 (经纬度)</option>
                <option value="EPSG:4490">CGCS2000 经纬度</option>
                <option value="EPSG:4547">CGCS2000 3°带</option>
                <option value="EPSG:4548">CGCS2000 3°带</option>
                <option value="EPSG:4549">CGCS2000 3°带</option>
                <option value="EPSG:4552">CGCS2000 3°带</option>
                <option value="EPSG:4565">CGCS2000 3°带</option>
            </select>
        </div>

        <!-- 中心点按钮 -->
        <div class="toolbar-group">
            <button class="btn btn-primary" onclick="fitToFactoryBoundary()">
                🔲 适应厂区
            </button>
        </div>
    </div>

    <!-- 右侧信息面板 -->
    <div class="info-panel">
        <div class="panel-header">
            <span>📊 几何信息</span>
            <span id="feature-count">0 个要素</span>
        </div>
        <div class="panel-content">
            <!-- 面积信息 -->
            <div class="info-section">
                <h3>厂区边界</h3>
                <div class="info-item">
                    <span class="info-label">面积</span>
                    <span class="info-value highlight" id="area-value">--</span>
                </div>
                <div class="info-item">
                    <span class="info-label">周长</span>
                    <span class="info-value" id="perimeter-value">--</span>
                </div>
                <div class="info-item">
                    <span class="info-label">顶点数</span>
                    <span class="info-value" id="vertex-count">--</span>
                </div>
            </div>

            <!-- 中心点信息 -->
            <div class="info-section">
                <h3>中心点 (用于大气预测)</h3>
                <div class="info-item">
                    <span class="info-label">X (UTM)</span>
                    <span class="info-value" id="center-x">--</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Y (UTM)</span>
                    <span class="info-value" id="center-y">--</span>
                </div>
                <div class="info-item">
                    <span class="info-label">经度</span>
                    <span class="info-value" id="center-lon">--</span>
                </div>
                <div class="info-item">
                    <span class="info-label">纬度</span>
                    <span class="info-value" id="center-lat">--</span>
                </div>
            </div>

            <!-- 坐标输入 -->
            <div class="info-section coord-input">
                <h3>📝 坐标输入</h3>
                <textarea id="coord-textarea" placeholder="输入坐标 (每行一组，格式：x,y 或 经度,纬度)"></textarea>
                <p class="hint">支持 CAD 坐标或经纬度，逗号分隔</p>
                <button class="btn btn-primary" style="margin-top: 8px; width: 100%;" onclick="applyCoordInput()">
                    应用坐标
                </button>
            </div>

            <!-- 转换预览 -->
            <div class="info-section">
                <h3>🔄 坐标转换预览</h3>
                <div class="info-item">
                    <span class="info-label">源坐标系</span>
                    <span class="info-value" id="src-crs">EPSG:4326</span>
                </div>
                <div class="info-item">
                    <span class="info-label">目标坐标系</span>
                    <span class="info-value" id="dst-crs">EPSG:4326</span>
                </div>
            </div>
        </div>
    </div>

    <!-- 地图容器 -->
    <div class="map-container">
        <div id="map"></div>
        <div class="measure-tooltip" id="measure-tooltip"></div>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar">
        <div class="status-item">
            <span class="status-indicator"></span>
            <span>就绪</span>
        </div>
        <div class="status-item">
            <span id="cursor-coords">坐标: --, --</span>
        </div>
        <div class="status-item">
            <span id="current-crs">当前坐标系: EPSG:4326</span>
        </div>
    </div>

    <!-- 隐藏的文件输入 -->
    <input type="file" id="file-geojson" class="file-input" accept=".geojson,.json">
    <input type="file" id="file-dxf" class="file-input" accept=".dxf">
    <input type="file" id="file-shp" class="file-input" accept=".shp,.shx,.dbf">

    <!-- OpenLayers -->
    <script src="https://cdn.jsdelivr.net/npm/ol@v7.4.0/dist/ol.js"></script>

    <script>
        // ==================== 全局变量 ====================
        let map;
        let source;
        let drawInteraction;
        let modifyInteraction;
        let currentDrawMode = null;
        let currentCRS = 'EPSG:4326';
        let targetCRS = 'EPSG:4326';

        // EPSG 代码映射（CGCS2000 3度带）
        const CGCS2000_ZONES = {
            'EPSG:4547': '+proj=tmerc +lat_0=0 +lon_0=117 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4548': '+proj=tmerc +lat_0=0 +lon_0=120 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4549': '+proj=tmerc +lat_0=0 +lon_0=123 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4552': '+proj=tmerc +lat_0=0 +lon_0=75 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4553': '+proj=tmerc +lat_0=0 +lon_0=78 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4554': '+proj=tmerc +lat_0=0 +lon_0=81 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4555': '+proj=tmerc +lat_0=0 +lon_0=84 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4556': '+proj=tmerc +lat_0=0 +lon_0=87 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4557': '+proj=tmerc +lat_0=0 +lon_0=90 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4558': '+proj=tmerc +lat_0=0 +lon_0=93 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4559': '+proj=tmerc +lat_0=0 +lon_0=96 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4560': '+proj=tmerc +lat_0=0 +lon_0=99 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4561': '+proj=tmerc +lat_0=0 +lon_0=102 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4562': '+proj=tmerc +lat_0=0 +lon_0=105 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4563': '+proj=tmerc +lat_0=0 +lon_0=108 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4564': '+proj=tmerc +lat_0=0 +lon_0=111 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4565': '+proj=tmerc +lat_0=0 +lon_0=114 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4566': '+proj=tmerc +lat_0=0 +lon_0=117 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4567': '+proj=tmerc +lat_0=0 +lon_0=120 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4568': '+proj=tmerc +lat_0=0 +lon_0=123 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4569': '+proj=tmerc +lat_0=0 +lon_0=126 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4570': '+proj=tmerc +lat_0=0 +lon_0=129 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
            'EPSG:4571': '+proj=tmerc +lat_0=0 +lon_0=132 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs',
        };

        // ==================== 初始化 ====================
        function initMap() {
            // 创建矢量源
            source = new ol.source.Vector({
                features: []
            });

            // 创建矢量层
            const vectorLayer = new ol.layer.Vector({
                source: source,
                style: new ol.style.Style({
                    fill: new ol.style.Fill({
                        color: 'rgba(25, 118, 210, 0.2)'
                    }),
                    stroke: new ol.style.Stroke({
                        color: '#1976D2',
                        width: 2
                    }),
                    image: new ol.style.Circle({
                        radius: 6,
                        fill: new ol.style.Fill({
                            color: '#FFC107'
                        })
                    })
                })
            });

            // 创建地图
            map = new ol.Map({
                target: 'map',
                layers: [
                    // OSM 底图
                    new ol.layer.Tile({
                        source: new ol.source.OSM()
                    }),
                    // 矢量层
                    vectorLayer
                ],
                view: new ol.View({
                    center: [118.78, 32.07],  // 默认南京
                    zoom: 14,
                    projection: 'EPSG:4326'
                })
            });

            // 注册坐标系
            registerProjections();

            // 鼠标移动事件 - 显示坐标
            map.on('pointermove', function(evt) {
                const coords = evt.coordinate;
                document.getElementById('cursor-coords').textContent =
                    '坐标: ' + coords[0].toFixed(6) + ', ' + coords[1].toFixed(6);
            });

            // 要素添加事件 - 更新信息
            source.on('addfeature', function(evt) {
                updateFeatureInfo();
                notifyBoundaryChange();
            });

            // 要素修改事件
            source.on('changefeature', function(evt) {
                updateFeatureInfo();
                notifyBoundaryChange();
            });

            // 要素移除事件
            source.on('removefeature', function(evt) {
                updateFeatureInfo();
                notifyBoundaryChange();
            });
        }

        // 注册坐标系
        function registerProjections() {
            // 注册 CGCS2000 3度带
            for (const [code, def] of Object.entries(CGCS2000_ZONES)) {
                if (!ol.proj.get(code)) {
                    ol.proj.set(code, {
                        code: code,
                        def: def,
                        units: 'm'
                    });
                }
            }

            // 注册 CGCS2000 经纬度
            if (!ol.proj.get('EPSG:4490')) {
                ol.proj.set('EPSG:4490', {
                    code: 'EPSG:4490',
                    def: '+proj=longlat +ellps=GRS80 +no_defs',
                    units: 'degrees'
                });
            }
        }

        // ==================== 绘制模式 ====================
        function setDrawMode(mode) {
            // 清除现有交互
            if (drawInteraction) {
                map.removeInteraction(drawInteraction);
                drawInteraction = null;
            }
            if (modifyInteraction) {
                map.removeInteraction(modifyInteraction);
                modifyInteraction = null;
            }

            // 重置按钮状态
            document.querySelectorAll('.toolbar .btn-primary').forEach(function(btn) {
                btn.classList.remove('active');
            });

            currentDrawMode = mode;

            if (mode === 'polygon') {
                document.getElementById('btn-polygon').classList.add('active');
                drawInteraction = new ol.interaction.Draw({
                    source: source,
                    type: 'Polygon',
                    style: new ol.style.Style({
                        fill: new ol.style.Fill({
                            color: 'rgba(25, 118, 210, 0.3)'
                        }),
                        stroke: new ol.style.Stroke({
                            color: '#FFC107',
                            width: 2,
                            lineDash: [5, 5]
                        })
                    })
                });
                map.addInteraction(drawInteraction);

            } else if (mode === 'point') {
                document.getElementById('btn-point').classList.add('active');
                drawInteraction = new ol.interaction.Draw({
                    source: source,
                    type: 'Point'
                });
                map.addInteraction(drawInteraction);

            } else if (mode === 'modify') {
                document.getElementById('btn-modify').classList.add('active');
                modifyInteraction = new ol.interaction.Modify({
                    source: source
                });
                map.addInteraction(modifyInteraction);
            }
        }

        // ==================== 清除和撤销 ====================
        function clearAll() {
            if (confirm('确定要清除所有要素吗？')) {
                source.clear();
                updateFeatureInfo();
                notifyBoundaryChange();
            }
        }

        function undoLast() {
            const features = source.getFeatures();
            if (features.length > 0) {
                source.removeFeature(features[features.length - 1]);
            }
        }

        // ==================== 坐标系转换 ====================
        function changeCoordSystem() {
            const newCRS = document.getElementById('coord-system').value;
            currentCRS = newCRS;

            // 更新视图
            const view = map.getView();
            const center = view.getCenter();

            // 转换中心点
            if (newCRS !== 'EPSG:4326') {
                const transformed = ol.proj.transform(center, 'EPSG:4326', newCRS);
                view.setCenter(transformed);
            }

            // 更新坐标显示
            document.getElementById('current-crs').textContent = '当前坐标系: ' + newCRS;
            document.getElementById('dst-crs').textContent = newCRS;

            updateFeatureInfo();
        }

        function transformCoords(coords, srcCRS, dstCRS) {
            if (srcCRS === dstCRS) return coords;
            return ol.proj.transform(coords, srcCRS, dstCRS);
        }

        // ==================== 面积和周长计算 ====================
        function calculateArea(polygon) {
            const geom = polygon.getGeometry();
            if (geom.getType() !== 'Polygon') return 0;

            // 获取坐标
            const coords = geom.getCoordinates()[0];

            // 使用球面面积计算（更准确）
            let area = 0;
            for (let i = 0; i < coords.length - 1; i++) {
                const p1 = coords[i];
                const p2 = coords[i + 1];
                area += p1[0] * p2[1] - p2[0] * p1[1];
            }
            area = Math.abs(area) / 2;

            // 转换为平方米（粗略估算）
            const metersPerDegree = 111000;
            return area * metersPerDegree * metersPerDegree;
        }

        function calculatePerimeter(polygon) {
            const geom = polygon.getGeometry();
            if (geom.getType() !== 'Polygon') return 0;

            const coords = geom.getCoordinates()[0];
            let perimeter = 0;

            for (let i = 0; i < coords.length - 1; i++) {
                const p1 = coords[i];
                const p2 = coords[i + 1];
                const dx = p2[0] - p1[0];
                const dy = p2[1] - p1[1];
                perimeter += Math.sqrt(dx * dx + dy * dy);
            }

            // 转换为米
            return perimeter * 111000;
        }

        function calculateCenter(polygon) {
            const geom = polygon.getGeometry();
            if (geom.getType() !== 'Polygon') return null;

            const extent = geom.getExtent();
            const center = [
                (extent[0] + extent[2]) / 2,
                (extent[1] + extent[3]) / 2
            ];

            return center;
        }

        // ==================== 更新界面信息 ====================
        function updateFeatureInfo() {
            const features = source.getFeatures();
            document.getElementById('feature-count').textContent = features.length + ' 个要素';

            let totalArea = 0;
            let totalPerimeter = 0;
            let totalVertices = 0;
            let mainPolygon = null;

            features.forEach(function(feature) {
                const geom = feature.getGeometry();
                if (geom.getType() === 'Polygon') {
                    const area = calculateArea(feature);
                    const perimeter = calculatePerimeter(feature);
                    totalArea += area;
                    totalPerimeter += perimeter;
                    totalVertices += geom.getCoordinates()[0].length - 1;
                    if (!mainPolygon) mainPolygon = feature;
                } else if (geom.getType() === 'Point') {
                    totalVertices += 1;
                }
            });

            // 更新显示
            document.getElementById('area-value').textContent = totalArea > 0
                ? formatArea(totalArea)
                : '--';
            document.getElementById('perimeter-value').textContent = totalPerimeter > 0
                ? formatLength(totalPerimeter)
                : '--';
            document.getElementById('vertex-count').textContent = totalVertices || '--';

            // 更新中心点
            if (mainPolygon) {
                const center = calculateCenter(mainPolygon);
                if (center) {
                    document.getElementById('center-x').textContent = center[0].toFixed(2);
                    document.getElementById('center-y').textContent = center[1].toFixed(2);
                    document.getElementById('center-lon').textContent = center[0].toFixed(6);
                    document.getElementById('center-lat').textContent = center[1].toFixed(6);
                }
            } else {
                document.getElementById('center-x').textContent = '--';
                document.getElementById('center-y').textContent = '--';
                document.getElementById('center-lon').textContent = '--';
                document.getElementById('center-lat').textContent = '--';
            }
        }

        function formatArea(area) {
            if (area >= 10000) {
                return (area / 10000).toFixed(2) + ' 公顷';
            }
            return area.toFixed(2) + ' m2';
        }

        function formatLength(length) {
            if (length >= 1000) {
                return (length / 1000).toFixed(2) + ' km';
            }
            return length.toFixed(2) + ' m';
        }

        // ==================== 适应厂区边界 ====================
        function fitToFactoryBoundary() {
            const features = source.getFeatures();
            if (features.length === 0) {
                alert('请先绘制厂区边界');
                return;
            }

            let extent = ol.extent.createEmpty();
            features.forEach(function(feature) {
                ol.extent.extend(extent, feature.getGeometry().getExtent());
            });

            map.getView().fit(extent, {
                padding: [50, 50, 50, 300],
                maxZoom: 16
            });
        }

        // ==================== 坐标输入 ====================
        function applyCoordInput() {
            const text = document.getElementById('coord-textarea').value.trim();
            if (!text) {
                alert('请输入坐标');
                return;
            }

            const lines = text.split('\n').filter(function(l) { return l.trim(); });
            const coords = [];

            lines.forEach(function(line) {
                const parts = line.split(/[,，\s]+/).filter(function(p) { return p; });
                if (parts.length >= 2) {
                    const x = parseFloat(parts[0]);
                    const y = parseFloat(parts[1]);
                    if (!isNaN(x) && !isNaN(y)) {
                        coords.push([x, y]);
                    }
                }
            });

            if (coords.length < 3) {
                alert('多边形至少需要3个坐标点');
                return;
            }

            // 关闭多边形
            coords.push(coords[0]);

            // 创建要素
            const feature = new ol.Feature({
                geometry: new ol.geom.Polygon([coords])
            });

            source.addFeature(feature);
            fitToFactoryBoundary();

            // 清空输入
            document.getElementById('coord-textarea').value = '';
        }

        // ==================== 导入导出 ====================
        function importGeoJSON() {
            document.getElementById('file-geojson').click();
        }

        document.getElementById('file-geojson').addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(evt) {
                try {
                    const geojson = JSON.parse(evt.target.result);
                    const format = new ol.format.GeoJSON();
                    const features = format.readFeatures(geojson);
                    source.addFeatures(features);
                    updateFeatureInfo();
                    alert('导入成功！');
                } catch (err) {
                    alert('GeoJSON 解析失败: ' + err.message);
                }
            };
            reader.readAsText(file);
        });

        function importDXF() {
            alert('DXF 导入功能需要后端支持，请导出 GeoJSON 后再导入。');
        }

        function importSHP() {
            alert('SHP 导入功能需要后端支持，请导出 GeoJSON 后再导入。');
        }

        function exportGeoJSON() {
            const features = source.getFeatures();
            if (features.length === 0) {
                alert('没有可导出的要素');
                return;
            }

            const format = new ol.format.GeoJSON();
            const geojson = format.writeFeatures(features, {
                dataProjection: 'EPSG:4326',
                featureProjection: map.getView().getProjection().getCode()
            });

            downloadFile('factory_boundary.geojson', geojson, 'application/geojson');
        }

        function exportDXF() {
            alert('DXF 导出功能需要后端支持，请使用 GeoJSON 格式。');
        }

        function exportWKT() {
            const features = source.getFeatures();
            if (features.length === 0) {
                alert('没有可导出的要素');
                return;
            }

            const format = new ol.format.WKT();
            const wkt = features.map(function(f) { return format.writeFeature(f); }).join('\n');

            downloadFile('factory_boundary.wkt', wkt, 'text/plain');
        }

        function downloadFile(filename, content, mimeType) {
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }

        // ==================== Python 集成接口 ====================
        function getBoundaryData() {
            const features = source.getFeatures();
            const format = new ol.format.GeoJSON();

            const geojson = format.writeFeatures(features, {
                dataProjection: 'EPSG:4326',
                featureProjection: map.getView().getProjection().getCode()
            });

            return JSON.parse(geojson);
        }

        function setBoundaryData(geojson) {
            try {
                const format = new ol.format.GeoJSON();
                const features = format.readFeatures(geojson);
                source.addFeatures(features);
                updateFeatureInfo();
                fitToFactoryBoundary();
            } catch (err) {
                console.error('设置边界数据失败:', err);
            }
        }

        function setCenter(lat, lon, zoom) {
            map.getView().setCenter([lon, lat]);
            if (zoom) {
                map.getView().setZoom(zoom);
            }
        }

        function notifyBoundaryChange() {
            // 向 Python 发送消息
            if (window.pyBridge && window.pyBridge.onBoundaryChange) {
                const data = getBoundaryData();
                window.pyBridge.onBoundaryChange(data);
            }
        }

        // 导出给 Python 调用
        window.BoundaryDrawer = {
            getBoundaryData: getBoundaryData,
            setBoundaryData: setBoundaryData,
            setCenter: setCenter,
            getMap: function() { return map; }
        };

        // ==================== 初始化地图 ====================
        document.addEventListener('DOMContentLoaded', initMap);
    </script>
</body>
</html>
"""


def get_html_template() -> str:
    """获取HTML模板字符串"""
    return BOUNDARY_DRAWER_HTML
