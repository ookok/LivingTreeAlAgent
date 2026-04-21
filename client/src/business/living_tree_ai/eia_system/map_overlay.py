"""
GIS 地图叠加层 (Map Overlay)
==========================

支持高德/百度/天地图等地图服务，叠加环评图层。
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class MapProvider(Enum):
    """地图服务商"""
    AMAP = "amap"       # 高德
    TENGXUN = "tencent"  # 腾讯
    TIANDITU = "tianditu"  # 天地图
    BING = "bing"       # 微软
    OSM = "osm"         # OpenStreetMap


class CoordinateSystem(Enum):
    """坐标系"""
    WGS84 = "wgs84"           # GPS原始坐标系
    GCJ02 = "gcj02"           # 火星坐标系（高德、腾讯）
    BD09 = "bd09"             # 百度坐标系


@dataclass
class MapMarker:
    """地图标记"""
    marker_id: str
    lat: float
    lng: float
    title: str = ""
    description: str = ""
    icon: str = "marker"
    color: str = "#D32F2F"
    category: str = ""  # pollution_source/sensitive_target/monitoring


@dataclass
class MapPolygon:
    """地图多边形"""
    polygon_id: str
    vertices: list  # [[lng, lat], ...]
    fill_color: str = "rgba(255,0,0,0.2)"
    stroke_color: str = "#F44336"
    stroke_width: int = 2
    label: str = ""
    category: str = ""


@dataclass
class MapCircle:
    """地图圆"""
    circle_id: str
    center: list  # [lng, lat]
    radius: float  # 米
    fill_color: str = "rgba(255,0,0,0.2)"
    stroke_color: str = "#F44336"
    stroke_width: int = 2
    label: str = ""


class MapOverlay:
    """
    地图叠加层

    用法:
        overlay = MapOverlay()

        # 生成地图 HTML
        html = await overlay.generate_map_html(
            center=[118.78, 32.07],  # 南京
            zoom=14,
            providers=["amap"]
        )

        # 添加防护距离圆
        overlay.add_circle(
            center=[118.78, 32.07],
            radius=200,
            label="200m防护区"
        )

        # 获取叠加层数据
        layers = overlay.get_overlay_data()
    """

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._markers: list[MapMarker] = []
        self._polygons: list[MapPolygon] = []
        self._circles: list[MapCircle] = []
        self._api_keys: dict[str, str] = {}

    def set_api_key(self, provider: MapProvider, key: str) -> None:
        """设置 API Key"""
        self._api_keys[provider.value] = key

    def add_marker(self, marker: MapMarker) -> None:
        """添加标记"""
        self._markers.append(marker)

    def add_polygon(self, polygon: MapPolygon) -> None:
        """添加多边形"""
        self._polygons.append(polygon)

    def add_circle(self, center: list, radius: float, label: str = "", **kwargs) -> str:
        """
        添加圆

        Args:
            center: 圆心 [lng, lat]
            radius: 半径（米）
            label: 标签
            **kwargs: 其他参数

        Returns:
            str: 圆 ID
        """
        circle_id = f"circle_{len(self._circles)}"
        circle = MapCircle(
            circle_id=circle_id,
            center=center,
            radius=radius,
            label=label,
            **{k: v for k, v in kwargs.items() if k in ["fill_color", "stroke_color", "stroke_width"]}
        )
        self._circles.append(circle)
        return circle_id

    def clear_overlays(self) -> None:
        """清除所有叠加层"""
        self._markers.clear()
        self._polygons.clear()
        self._circles.clear()

    def get_overlay_data(self) -> dict:
        """获取叠加层数据"""
        return {
            "markers": [
                {
                    "id": m.marker_id,
                    "position": [m.lng, m.lat],
                    "title": m.title,
                    "description": m.description,
                    "icon": m.icon,
                    "color": m.color,
                    "category": m.category
                }
                for m in self._markers
            ],
            "polygons": [
                {
                    "id": p.polygon_id,
                    "path": p.vertices,
                    "fillColor": p.fill_color,
                    "strokeColor": p.stroke_color,
                    "strokeWeight": p.stroke_width,
                    "label": p.label,
                    "category": p.category
                }
                for p in self._polygons
            ],
            "circles": [
                {
                    "id": c.circle_id,
                    "center": c.center,
                    "radius": c.radius,
                    "fillColor": c.fill_color,
                    "strokeColor": c.stroke_color,
                    "strokeWeight": c.stroke_width,
                    "label": c.label
                }
                for c in self._circles
            ]
        }

    async def generate_map_html(
        self,
        center: list = None,
        zoom: int = 14,
        providers: list = None,
        base_layers: bool = True,
        show_overlays: bool = True
    ) -> str:
        """
        生成地图 HTML

        Args:
            center: 中心点 [lng, lat]
            zoom: 缩放级别
            providers: 地图提供商列表
            base_layers: 是否显示底图
            show_overlays: 是否显示叠加层

        Returns:
            str: HTML 代码
        """
        if center is None:
            center = [116.397428, 39.90923]  # 默认北京
        if providers is None:
            providers = ["amap"]

        overlays_json = json.dumps(self.get_overlay_data()) if show_overlays else "{}"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>环评地图</title>
    <style>
        * {{ margin: 0; padding: 0; }}
        body, html {{ width: 100%; height: 100%; }}
        #map-container {{
            width: 100%;
            height: 100%;
            position: relative;
        }}
        #map {{
            width: 100%;
            height: 100%;
        }}
        .toolbar {{
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .toolbar button {{
            display: block;
            width: 100%;
            padding: 8px 16px;
            margin: 5px 0;
            border: 1px solid #ddd;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }}
        .toolbar button:hover {{ background: #f5f5f5; }}
        .info-panel {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-height: 200px;
            overflow-y: auto;
        }}
        .legend {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            margin-right: 8px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div id="map-container">
        <div id="map"></div>

        <div class="toolbar">
            <button onclick="zoomIn()">🔍 放大</button>
            <button onclick="zoomOut()">🔍 缩小</button>
            <button onclick="toggleSatellite()">🛰️ 卫星图</button>
            <button onclick="exportLayers()">📥 导出</button>
        </div>

        <div class="legend" id="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: rgba(255,0,0,0.3); border: 2px solid #F44336;"></div>
                <span>防护距离</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #1976D2;"></div>
                <span>污染源</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #4CAF50;"></div>
                <span>敏感目标</span>
            </div>
        </div>

        <div class="info-panel" id="info-panel">
            <strong>📍 项目位置</strong><br>
            <span id="coords">{center[0]}, {center[1]}</span>
        </div>
    </div>

    <!-- 高德地图 -->
    <script src="https://webapi.amap.com/maps?v=2.0&key={self._api_keys.get('amap', 'YOUR_AMAP_KEY')}"></script>

    <script>
        // 叠加层数据
        const overlayData = {overlays_json};

        // 初始化地图
        const map = new AMap.Map('map', {{
            zoom: {zoom},
            center: {center},
            viewMode: '2D',
            mapStyle: 'amap://styles/normal'
        }});

        // 存储叠加对象
        const overlayObjects = {{}};
        let currentLayerType = 'normal';

        // 渲染叠加层
        function renderOverlays() {{
            // 清除旧对象
            Object.values(overlayObjects).forEach(obj => {{
                if (obj.setMap) obj.setMap(null);
                else if (obj.forEach) obj.forEach(o => o.setMap && o.setMap(null));
            }});

            // 渲染圆
            if (overlayData.circles) {{
                const circles = overlayData.circles.map(c => {{
                    return new AMap.Circle({{
                        center: new AMap.LngLat(c.center[0], c.center[1]),
                        radius: c.radius,
                        fillColor: c.fillColor,
                        borderWeight: c.strokeWeight,
                        strokeColor: c.strokeColor,
                        strokeOpacity: 0.8
                    }});
                }});
                circles.forEach(c => c.setMap(map));
                overlayObjects.circles = circles;
            }}

            // 渲染多边形
            if (overlayData.polygons) {{
                const polygons = overlayData.polygons.map(p => {{
                    return new AMap.Polygon({{
                        path: p.path.map(v => new AMap.LngLat(v[0], v[1])),
                        fillColor: p.fillColor,
                        borderWeight: p.strokeWeight,
                        strokeColor: p.strokeColor
                    }});
                }});
                polygons.forEach(p => p.setMap(map));
                overlayObjects.polygons = polygons;
            }}

            // 渲染标记
            if (overlayData.markers) {{
                const markers = overlayData.markers.map(m => {{
                    return new AMap.Marker({{
                        position: new AMap.LngLat(m.position[0], m.position[1]),
                        title: m.title,
                        content: `<div style="background:${{m.color}};width:12px;height:12px;border-radius:50%;"></div>`
                    }});
                }});
                markers.forEach(m => m.setMap(map));
                overlayObjects.markers = markers;
            }}
        }}

        // 工具函数
        function zoomIn() {{ map.zoomIn(); }}
        function zoomOut() {{ map.zoomOut(); }}

        function toggleSatellite() {{
            if (currentLayerType === 'normal') {{
                map.setMapStyle('amap://styles/satellite');
                currentLayerType = 'satellite';
            }} else {{
                map.setMapStyle('amap://styles/normal');
                currentLayerType = 'normal';
            }}
        }}

        function exportLayers() {{
            const data = JSON.stringify(overlayData, null, 2);
            console.log('导出数据:', data);
            alert('叠加层数据已导出到控制台');
        }}

        // 监听点击事件
        map.on('click', (e) => {{
            document.getElementById('coords').textContent =
                `${{e.lnglat.getLng()}}, ${{e.lnglat.getLat()}}`;
        }});

        // 初始化
        renderOverlays();

        // 暴露 API
        window.mapOverlay = {{
            addMarker: function(data) {{ renderOverlays(); }},
            addCircle: function(center, radius, label) {{ renderOverlays(); }},
            getData: function() {{ return overlayData; }},
            exportData: exportLayers
        }};
    </script>
</body>
</html>
"""

    async def query_nearby_sensitive_targets(
        self,
        center: list,
        radius_km: float = 5,
        keywords: list = None
    ) -> list[dict]:
        """
        查询附近的敏感目标

        Args:
            center: 中心点 [lng, lat]
            radius_km: 查询半径（公里）
            keywords: 关键词列表

        Returns:
            list[dict]: 敏感目标列表
        """
        if keywords is None:
            keywords = ["学校", "医院", "居民区", "幼儿园", "敬老院"]

        # 简化实现：实际应调用地图 API
        return [
            {
                "name": f"{keyword}示例",
                "distance": round(radius_km * 0.5, 1),
                "direction": "NE",
                "category": keyword
            }
            for keyword in keywords
        ]

    def coordinate_convert(
        self,
        coords: list,
        from_sys: CoordinateSystem,
        to_sys: CoordinateSystem
    ) -> list:
        """
        坐标系转换

        Args:
            coords: 坐标 [[lng, lat], ...] 或 [lng, lat]
            from_sys: 源坐标系
            to_sys: 目标坐标系

        Returns:
            list: 转换后的坐标
        """
        # 简化实现
        if from_sys == to_sys:
            return coords

        # WGS84 -> GCJ02
        if from_sys == CoordinateSystem.WGS84 and to_sys == CoordinateSystem.GCJ02:
            return self._wgs84_to_gcj02(coords)

        # GCJ02 -> BD09
        elif from_sys == CoordinateSystem.GCJ02 and to_sys == CoordinateSystem.BD09:
            return self._gcj02_to_bd09(coords)

        return coords

    def _wgs84_to_gcj02(self, coords) -> list:
        """WGS84 转 GCJ02（简化）"""
        # 实际应使用完整的转换算法
        if isinstance(coords[0], list):
            return [[c[0] + 0.0065, c[1] + 0.006] for c in coords]
        return [coords[0] + 0.0065, coords[1] + 0.006]

    def _gcj02_to_bd09(self, coords) -> list:
        """GCJ02 转 BD09（简化）"""
        # 实际应使用完整的转换算法
        if isinstance(coords[0], list):
            return [[c[0] + 0.0065, c[1] + 0.006] for c in coords]
        return [coords[0] + 0.0065, coords[1] + 0.006]


def create_map_overlay(data_dir: str = "./data/eia") -> MapOverlay:
    """创建地图叠加层实例"""
    return MapOverlay(data_dir=data_dir)