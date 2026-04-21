"""
环评智能绘图引擎 (Drawing Engine)
==============================

支持工艺流程图、厂房布置图、防护距离图等环评专用图纸的生成与编辑。
"""

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class LayerType(Enum):
    """图层类型"""
    BUILDING = "building"       # 建筑
    EQUIPMENT = "equipment"    # 设备
    PIPELINE = "pipeline"      # 管道
    POLLUTION_SOURCE = "pollution_source"  # 污染源
    PROTECTION_ZONE = "protection_zone"  # 防护距离
    ANNOTATION = "annotation"  # 标注
    SENSITIVE_TARGET = "sensitive_target"  # 敏感目标


@dataclass
class DrawingLayer:
    """绘图图层"""
    layer_id: str
    name: str
    layer_type: LayerType
    visible: bool = True
    locked: bool = False
    color: str = "#000000"
    elements: list = field(default_factory=list)


@dataclass
class DrawingElement:
    """图形元素"""
    element_id: str
    type: str  # line/rect/circle/polygon/text/arrow
    points: list = field(default_factory=list)  # 坐标点
    style: dict = field(default_factory=dict)  # 样式
    label: str = ""  # 标签
    metadata: dict = field(default_factory=dict)


@dataclass
class FlowChartNode:
    """流程图节点"""
    node_id: str
    name: str                           # 节点名称
    node_type: str = "process"         # process/decision/input/output
    x: float = 0
    y: float = 0
    width: float = 120
    height: float = 60
    pollutants: list[str] = field(default_factory=list)  # 关联污染物
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


@dataclass
class ProtectionZone:
    """防护距离区域"""
    zone_id: str
    source_id: str                       # 关联的污染源
    distance: float                       # 防护距离 (m)
    shape: str = "circle"               # 形状
    center_x: float = 0
    center_y: float = 0
    vertices: list = field(default_factory=list)  # 多边形顶点
    color: str = "rgba(255,0,0,0.2)"   # 填充颜色


class DrawingEngine:
    """
    环评智能绘图引擎

    用法:
        engine = DrawingEngine()

        # 生成工艺流程图
        flow_data = await engine.generate_flow_chart(
            project_name="某化工项目",
            processes=[...],
            pollution_sources=[...]
        )

        # 生成防护距离图
        protection_data = await engine.generate_protection_zones(
            pollution_sources=[...],
            building_outlines=[...]
        )
    """

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._canvas_handler: Optional[Callable] = None

    def register_canvas_handler(self, handler: Callable) -> None:
        """注册 Canvas 处理器"""
        self._canvas_handler = handler

    async def generate_flow_chart(
        self,
        project_name: str,
        processes: list,
        pollution_sources: list = None,
        layout: str = "horizontal"  # horizontal/vertical
    ) -> dict:
        """
        生成工艺流程图

        Args:
            project_name: 项目名称
            processes: 工艺单元列表
            pollution_sources: 污染源列表
            layout: 布局方向

        Returns:
            dict: 流程图数据
        """
        nodes = []
        connections = []

        # 转换工艺为节点
        process_map = {}
        for i, process in enumerate(processes):
            node_id = f"node_{i}"
            x = i * 150 + 50 if layout == "horizontal" else 50
            y = 50 if layout == "horizontal" else i * 100 + 50

            # 查找关联的污染源
            pollutants = []
            if pollution_sources:
                for source in pollution_sources:
                    if source.get("process") == process.get("name"):
                        pollutants.extend(source.get("pollutants", []))

            node = FlowChartNode(
                node_id=node_id,
                name=process.get("name", f"工艺{i+1}"),
                node_type="process",
                x=x,
                y=y,
                pollutants=pollutants,
                inputs=[f"input_{i}"],
                outputs=[f"output_{i}"]
            )
            nodes.append(node)
            process_map[node_id] = i

        # 创建连接
        for i in range(len(nodes) - 1):
            connections.append({
                "from": nodes[i].node_id,
                "to": nodes[i + 1].node_id,
                "type": "arrow"
            })

        # 构建图层
        layers = [
            self._create_layer(LayerType.EQUIPMENT, "工艺单元", nodes),
            self._create_annotation_layer(processes)
        ]

        return {
            "type": "flow_chart",
            "title": f"{project_name} 工艺流程图",
            "layers": layers,
            "nodes": [self._node_to_dict(n) for n in nodes],
            "connections": connections,
            "dimensions": {
                "width": len(nodes) * 150 + 100 if layout == "horizontal" else 400,
                "height": 150 if layout == "horizontal" else len(nodes) * 100 + 100
            }
        }

    def _node_to_dict(self, node: FlowChartNode) -> dict:
        """节点转字典"""
        return {
            "id": node.node_id,
            "name": node.name,
            "type": node.node_type,
            "x": node.x,
            "y": node.y,
            "width": node.width,
            "height": node.height,
            "pollutants": node.pollutants
        }

    def _create_layer(self, layer_type: LayerType, name: str, nodes: list) -> dict:
        """创建图层"""
        elements = []
        for node in nodes:
            elements.append(DrawingElement(
                element_id=node.node_id,
                type="rect",
                points=[node.x, node.y, node.x + node.width, node.y + node.height],
                style={
                    "fill": "#E3F2FD",
                    "stroke": "#1976D2",
                    "strokeWidth": 2
                },
                label=node.name,
                metadata={"node_data": node.__dict__}
            ))

            # 添加污染物标签
            if node.pollutants:
                elements.append(DrawingElement(
                    element_id=f"{node.node_id}_pollutants",
                    type="text",
                    points=[node.x, node.y + node.height + 15],
                    style={"fontSize": 10, "fill": "#D32F2F"},
                    label=", ".join(node.pollutants)
                ))

        return {
            "layer_id": layer_type.value,
            "name": name,
            "layer_type": layer_type.value,
            "visible": True,
            "elements": [self._element_to_dict(e) for e in elements]
        }

    def _create_annotation_layer(self, processes: list) -> dict:
        """创建标注图层"""
        elements = []
        for i, process in enumerate(processes):
            if process.get("description"):
                elements.append(DrawingElement(
                    element_id=f"annotation_{i}",
                    type="text",
                    points=[10, i * 20 + 10],
                    style={"fontSize": 9, "fill": "#666"},
                    label=process.get("description", "")[:50]
                ))

        return {
            "layer_id": LayerType.ANNOTATION.value,
            "name": "标注",
            "layer_type": LayerType.ANNOTATION.value,
            "visible": True,
            "elements": [self._element_to_dict(e) for e in elements]
        }

    def _element_to_dict(self, element: DrawingElement) -> dict:
        """元素转字典"""
        return {
            "id": element.element_id,
            "type": element.type,
            "points": element.points,
            "style": element.style,
            "label": element.label,
            "metadata": element.metadata
        }

    async def generate_layout(
        self,
        extracted_data: dict
    ) -> dict:
        """
        生成总平面布置图

        Args:
            extracted_data: 从文档提取的数据

        Returns:
            dict: 布置图数据
        """
        layers = []
        elements = []

        # 建筑物图层
        buildings = extracted_data.get("buildings", [])
        for i, building in enumerate(buildings):
            # 解析尺寸
            size = building.get("size", "20m × 10m")
            match = re.search(r"(\d+(?:\.\d+)?)\s*[m米×x]\s*(\d+(?:\.\d+)?)", size)
            if match:
                width, height = float(match.group(1)), float(match.group(2))
            else:
                width, height = 20, 10

            # 计算位置（简化：网格布局）
            row = i // 4
            col = i % 4
            x = col * 50 + 20
            y = row * 40 + 20

            elements.append(DrawingElement(
                element_id=f"building_{i}",
                type="rect",
                points=[x, y, x + width, y + height],
                style=self._get_building_style(building.get("type", "")),
                label=building.get("name", building.get("type", "建筑")),
                metadata={"building": building}
            ))

        layers.append(self._create_layer(LayerType.BUILDING, "建筑物", []))
        layers[0]["elements"] = [self._element_to_dict(e) for e in elements]

        # 设备图层
        equipment = extracted_data.get("equipment_list", [])
        equip_elements = []
        for i, equip in enumerate(equipment[:10]):  # 限制数量
            x = 400 + (i % 3) * 30
            y = 50 + (i // 3) * 30

            equip_elements.append(DrawingElement(
                element_id=f"equipment_{i}",
                type="rect",
                points=[x, y, x + 20, y + 15],
                style={
                    "fill": "#FFF3E0",
                    "stroke": "#FF9800",
                    "strokeWidth": 1
                },
                label=equip.get("name", "设备"),
                metadata={"equipment": equip}
            ))

        layers.append({
            "layer_id": LayerType.EQUIPMENT.value,
            "name": "设备",
            "layer_type": LayerType.EQUIPMENT.value,
            "visible": True,
            "elements": [self._element_to_dict(e) for e in equip_elements]
        })

        return {
            "type": "layout",
            "title": "总平面布置图",
            "layers": layers,
            "dimensions": {"width": 800, "height": 600}
        }

    def _get_building_style(self, building_type: str) -> dict:
        """获取建筑样式"""
        style_map = {
            "车间": {"fill": "#E3F2FD", "stroke": "#1976D2"},
            "厂房": {"fill": "#E3F2FD", "stroke": "#1976D2"},
            "仓库": {"fill": "#FFF3E0", "stroke": "#FF9800"},
            "办公楼": {"fill": "#E8F5E9", "stroke": "#4CAF50"},
            "罐区": {"fill": "#FCE4EC", "stroke": "#E91E63"},
            "危废": {"fill": "#FFEBEE", "stroke": "#F44336"},
        }

        for key, style in style_map.items():
            if key in building_type:
                style["strokeWidth"] = 2
                return style

        return {"fill": "#F5F5F5", "stroke": "#9E9E9E", "strokeWidth": 1}

    async def generate_protection_zones(
        self,
        pollution_sources: list,
        building_outlines: list = None
    ) -> dict:
        """
        生成卫生防护距离图

        Args:
            pollution_sources: 污染源列表（含计算结果）
            building_outlines: 建筑物轮廓

        Returns:
            dict: 防护距离图数据
        """
        zones = []
        elements = []

        for i, source in enumerate(pollution_sources):
            # 计算防护距离（简化：基于排放量和风速）
            emission_rate = source.get("emission_rate", 1.0)  # g/s
            distance = self._calc_protection_distance(emission_rate)

            # 获取源位置
            x = source.get("x", i * 100 + 100)
            y = source.get("y", 100)

            zone = ProtectionZone(
                zone_id=f"zone_{i}",
                source_id=source.get("source_id", f"source_{i}"),
                distance=distance,
                shape="circle" if source.get("shape") != "rect" else "rect",
                center_x=x,
                center_y=y
            )
            zones.append(zone)

            # 创建区域元素
            if zone.shape == "circle":
                # 圆形防护区
                elements.append(DrawingElement(
                    element_id=zone.zone_id,
                    type="circle",
                    points=[x, y, distance],
                    style={
                        "fill": "rgba(255,0,0,0.15)",
                        "stroke": "#F44336",
                        "strokeWidth": 2,
                        "lineDash": [5, 3]
                    },
                    label=f"{distance}m防护区"
                ))
            else:
                # 矩形防护区
                elements.append(DrawingElement(
                    element_id=zone.zone_id,
                    type="rect",
                    points=[x - distance/2, y - distance/2, x + distance/2, y + distance/2],
                    style={
                        "fill": "rgba(255,0,0,0.15)",
                        "stroke": "#F44336",
                        "strokeWidth": 2,
                        "lineDash": [5, 3]
                    },
                    label=f"{distance}m防护区"
                ))

        # 创建建筑物图层
        building_elements = []
        if building_outlines:
            for i, building in enumerate(building_outlines):
                x = building.get("x", 0)
                y = building.get("y", 0)
                w = building.get("width", 20)
                h = building.get("height", 10)

                building_elements.append(DrawingElement(
                    element_id=f"outline_{i}",
                    type="rect",
                    points=[x, y, x + w, y + h],
                    style={
                        "fill": "#E3F2FD",
                        "stroke": "#1976D2",
                        "strokeWidth": 2
                    },
                    label=building.get("name", "建筑")
                ))

        layers = [
            {
                "layer_id": LayerType.PROTECTION_ZONE.value,
                "name": "防护距离",
                "layer_type": LayerType.PROTECTION_ZONE.value,
                "visible": True,
                "elements": [self._element_to_dict(e) for e in elements]
            },
            {
                "layer_id": LayerType.BUILDING.value,
                "name": "建筑物",
                "layer_type": LayerType.BUILDING.value,
                "visible": True,
                "elements": [self._element_to_dict(e) for e in building_elements]
            }
        ]

        return {
            "type": "protection_zones",
            "title": "卫生防护距离图",
            "layers": layers,
            "zones": [
                {
                    "zone_id": z.zone_id,
                    "distance": z.distance,
                    "center": {"x": z.center_x, "y": z.center_y},
                    "shape": z.shape
                }
                for z in zones
            ],
            "dimensions": {"width": 1000, "height": 800}
        }

    def _calc_protection_distance(self, emission_rate: float) -> float:
        """
        计算防护距离（简化版）

        实际应基于 HJ 2.2-2018 推荐模式计算
        """
        # 简化：基于排放量的估算
        if emission_rate < 0.1:
            return 50
        elif emission_rate < 1:
            return 100
        elif emission_rate < 10:
            return 200
        else:
            return max(500, emission_rate * 30)

    def generate_canvas_html(self, drawing_data: dict) -> str:
        """
        生成 Canvas HTML

        Args:
            drawing_data: 绘图数据

        Returns:
            str: HTML 代码
        """
        drawing_json = json.dumps(drawing_data)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{drawing_data.get('title', '环评图纸')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: system-ui, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .canvas-container {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: auto;
        }}
        canvas {{
            display: block;
        }}
        .toolbar {{
            margin-bottom: 10px;
            padding: 10px;
            background: white;
            border-radius: 8px;
            display: flex;
            gap: 10px;
        }}
        .btn {{
            padding: 6px 12px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }}
        .btn:hover {{ background: #f5f5f5; }}
        .layer-panel {{
            position: absolute;
            right: 10px;
            top: 60px;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <div class="toolbar">
        <button class="btn" onclick="zoomIn()">🔍 放大</button>
        <button class="btn" onclick="zoomOut()">🔍 缩小</button>
        <button class="btn" onclick="resetView()">🏠 重置</button>
        <button class="btn" onclick="exportSVG()">📥 导出SVG</button>
    </div>
    <div class="canvas-container">
        <canvas id="drawing-canvas"></canvas>
    </div>

    <script>
        const drawingData = {drawing_json};

        const canvas = document.getElementById('drawing-canvas');
        const ctx = canvas.getContext('2d');

        let scale = 1;
        let offsetX = 0;
        let offsetY = 0;

        // 初始化画布
        function initCanvas() {{
            const dims = drawingData.dimensions || {{width: 800, height: 600}};
            canvas.width = dims.width;
            canvas.height = dims.height;
            render();
        }}

        // 渲染
        function render() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.save();
            ctx.translate(offsetX, offsetY);
            ctx.scale(scale, scale);

            // 渲染每个图层
            for (const layer of drawingData.layers || []) {{
                if (!layer.visible) continue;

                for (const elem of layer.elements || []) {{
                    drawElement(elem);
                }}
            }}

            ctx.restore();
        }}

        // 绘制元素
        function drawElement(elem) {{
            const style = elem.style || {{}};
            ctx.fillStyle = style.fill || 'transparent';
            ctx.strokeStyle = style.stroke || '#000';
            ctx.lineWidth = style.strokeWidth || 1;

            if (style.lineDash) {{
                ctx.setLineDash(style.lineDash);
            }}

            switch (elem.type) {{
                case 'rect':
                    const [x1, y1, x2, y2] = elem.points;
                    ctx.beginPath();
                    ctx.rect(x1, y1, x2 - x1, y2 - y1);
                    ctx.fill();
                    ctx.stroke();
                    break;

                case 'circle':
                    const [cx, cy, r] = elem.points;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.stroke();
                    break;

                case 'text':
                    ctx.font = `${{style.fontSize || 12}}px system-ui`;
                    ctx.fillStyle = style.fill || '#000';
                    ctx.fillText(elem.label || '', elem.points[0], elem.points[1]);
                    break;

                case 'line':
                    ctx.beginPath();
                    ctx.moveTo(elem.points[0], elem.points[1]);
                    ctx.lineTo(elem.points[2], elem.points[3]);
                    ctx.stroke();
                    break;
            }}

            // 绘制标签
            if (elem.label && elem.type !== 'text') {{
                ctx.font = '12px system-ui';
                ctx.fillStyle = '#333';
                ctx.fillText(elem.label, elem.points[0], elem.points[1] - 5);
            }}
        }}

        // 缩放
        function zoomIn() {{
            scale *= 1.2;
            render();
        }}

        function zoomOut() {{
            scale /= 1.2;
            render();
        }}

        function resetView() {{
            scale = 1;
            offsetX = 0;
            offsetY = 0;
            render();
        }}

        // 导出
        function exportSVG() {{
            // 简化的SVG导出
            alert('SVG导出功能');
        }}

        // 鼠标拖拽
        let isDragging = false;
        let lastX, lastY;

        canvas.addEventListener('mousedown', (e) => {{
            isDragging = true;
            lastX = e.clientX;
            lastY = e.clientY;
        }});

        canvas.addEventListener('mousemove', (e) => {{
            if (!isDragging) return;
            offsetX += e.clientX - lastX;
            offsetY += e.clientY - lastY;
            lastX = e.clientX;
            lastY = e.clientY;
            render();
        }});

        canvas.addEventListener('mouseup', () => {{
            isDragging = false;
        }});

        initCanvas();
    </script>
</body>
</html>
"""


def create_drawing_engine(data_dir: str = "./data/eia") -> DrawingEngine:
    """创建绘图引擎实例"""
    return DrawingEngine(data_dir=data_dir)


# 导入 re 模块
import re