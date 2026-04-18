"""
可视化智能体 (Visualization Agent)
=================================

职责：
1. 生成工艺流程图 (Mermaid / Draw.io / SVG)
2. 生成污染物排放图
3. 生成控制工艺图
4. 多格式输出支持

作者：Hermes Desktop AI Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class FlowchartNode:
    """流程图节点"""
    id: str
    name: str
    type: str  # process, pollutant, treatment, decision
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 60
    style: Dict[str, str] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowchartEdge:
    """流程图边"""
    source: str
    target: str
    label: str = ""
    style: str = ""


class VisualizationAgent:
    """
    可视化智能体 - 生成专业工艺流程图
    """

    # 节点样式模板
    NODE_STYLES = {
        "process": {
            "shape": "rounded rectangle",
            "fill": "#E3F2FD",
            "stroke": "#1976D2",
            "font-size": "12px",
        },
        "pollutant": {
            "shape": "ellipse",
            "fill": "#FFEBEE",
            "stroke": "#D32F2F",
            "font-size": "11px",
        },
        "treatment": {
            "shape": "rhombus",
            "fill": "#E8F5E9",
            "stroke": "#388E3C",
            "font-size": "11px",
        },
        "decision": {
            "shape": "diamond",
            "fill": "#FFF3E0",
            "stroke": "#F57C00",
            "font-size": "11px",
        },
        "start": {
            "shape": "circle",
            "fill": "#E8EAF6",
            "stroke": "#3F51B5",
        },
        "end": {
            "shape": "circle",
            "fill": "#FCE4EC",
            "stroke": "#E91E63",
        },
        "waste": {
            "shape": "cylinder",
            "fill": "#FBE9E7",
            "stroke": "#BF360C",
            "font-size": "11px",
        },
    }

    # 污染物颜色编码
    POLLUTANT_COLORS = {
        "废气": "#FF5722",
        "粉尘": "#795548",
        "VOCs": "#9C27B0",
        "废水": "#2196F3",
        "COD": "#3F51B5",
        "固废": "#607D8B",
        "噪声": "#9E9E9E",
    }

    def __init__(self):
        self.node_styles = self.NODE_STYLES
        logger.info("可视化智能体初始化完成")

    def generate_flowchart(self, process_chain: List[str],
                          pollutants: List[Dict] = None,
                          mitigation: List[Dict] = None) -> Dict[str, Any]:
        """
        生成工艺流程图

        Args:
            process_chain: 工艺链
            pollutants: 污染物列表
            mitigation: 防治措施列表

        Returns:
            流程图数据（支持多种格式）
        """
        logger.info(f"生成流程图: {len(process_chain)}道工序")

        # 构建节点和边
        nodes, edges = self._build_flowchart_elements(process_chain, pollutants, mitigation)

        # 生成多种格式
        return {
            "mermaid": self._to_mermaid(nodes, edges),
            "drawio": self._to_drawio(nodes, edges),
            "svg": self._to_svg(nodes, edges),
            "json": self._to_json(nodes, edges),
            "nodes": [n.__dict__ for n in nodes],
            "edges": [e.__dict__ for e in edges],
        }

    def _build_flowchart_elements(self, process_chain: List[str],
                                  pollutants: List[Dict] = None,
                                  mitigation: List[Dict] = None) -> Tuple[List[FlowchartNode], List[FlowchartEdge]]:
        """构建流程图元素"""
        nodes = []
        edges = []
        node_id_counter = 1

        # 添加开始节点
        start = FlowchartNode(
            id=f"node_{node_id_counter}",
            name="开始",
            type="start",
            style=self.node_styles["start"]
        )
        nodes.append(start)
        prev_node = start

        # 工艺节点
        for i, step in enumerate(process_chain):
            node_id_counter += 1
            step_node = FlowchartNode(
                id=f"node_{node_id_counter}",
                name=step,
                type="process",
                style=self.node_styles["process"],
                data={"step": step, "index": i}
            )
            nodes.append(step_node)
            edges.append(FlowchartEdge(prev_node.id, step_node.id))
            prev_node = step_node

        # 添加污染物分支
        if pollutants:
            pollutant_node = None
            for poll in pollutants[:3]:  # 最多3个主要污染物
                node_id_counter += 1
                poll_node = FlowchartNode(
                    id=f"node_{node_id_counter}",
                    name=f"{poll.get('name', '污染物')}\n({poll.get('amount', '')}{poll.get('unit', '')})",
                    type="pollutant",
                    style=self.node_styles["pollutant"],
                    data=poll
                )
                nodes.append(poll_node)
                edges.append(FlowchartEdge(prev_node.id, poll_node.id, "产生"))

                if not pollutant_node:
                    pollutant_node = poll_node

            # 污染物处理
            if mitigation and pollutant_node:
                node_id_counter += 1
                treat_node = FlowchartNode(
                    id=f"node_{node_id_counter}",
                    name="处理措施",
                    type="treatment",
                    style=self.node_styles["treatment"],
                    data={"measures": [m.get("measure", "") for m in mitigation[:2]]}
                )
                nodes.append(treat_node)
                edges.append(FlowchartEdge(pollutant_node.id, treat_node.id, "处理"))

                # 达标排放
                node_id_counter += 1
                emit_node = FlowchartNode(
                    id=f"node_{node_id_counter}",
                    name="达标排放",
                    type="process",
                    style={"fill": "#C8E6C9", "stroke": "#4CAF50"}
                )
                nodes.append(emit_node)
                edges.append(FlowchartEdge(treat_node.id, emit_node.id))

        # 结束节点
        node_id_counter += 1
        end = FlowchartNode(
            id=f"node_{node_id_counter}",
            name="结束",
            type="end",
            style=self.node_styles["end"]
        )
        nodes.append(end)
        edges.append(FlowchartEdge(prev_node.id, end.id))

        return nodes, edges

    def _to_mermaid(self, nodes: List[FlowchartNode], edges: List[FlowchartEdge]) -> str:
        """转换为 Mermaid 格式"""
        lines = ["flowchart TD"]

        # 节点定义
        for node in nodes:
            style = self.node_styles.get(node.type, {})
            shape = self._get_mermaid_shape(node.type)
            lines.append(f'    {node.id}["{node.name}"]{shape}')

        # 边定义
        for edge in edges:
            label = f'|{edge.label}|' if edge.label else ""
            lines.append(f'    {edge.source} -->{label} {edge.target}')

        # 添加样式类
        for node_type, style in self.node_styles.items():
            hex_fill = style.get("fill", "#FFFFFF").replace("#", "")
            lines.append(f'    classDef {node_type} fill:#{hex_fill},stroke:#333,stroke-width:2px')

        return "\n".join(lines)

    def _get_mermaid_shape(self, node_type: str) -> str:
        """获取Mermaid形状"""
        shapes = {
            "start": "",
            "end": "",
            "process": "",
            "pollutant": "{::}",
            "treatment": "{()}",
            "decision": "{{}}",
        }
        return shapes.get(node_type, "")

    def _to_drawio(self, nodes: List[FlowchartNode], edges: List[FlowchartEdge]) -> str:
        """转换为 Draw.io XML 格式"""
        xml_lines = ['<mxfile>', '<diagram name="工艺流程图">', '<mxGraphModel>']
        xml_lines.append('<root>')
        xml_lines.append('<mxCell id="0"/>')
        xml_lines.append('<mxCell id="1" parent="0"/>')

        # 节点
        for i, node in enumerate(nodes):
            style = self._get_drawio_style(node)
            xml_lines.append(
                f'<mxCell id="{node.id}" value="{node.name}" style="{style}" '
                f'vertex="1" parent="1">'
            )
            xml_lines.append(f'  <mxGeometry x="{200 + i * 150}" y="200" width="120" height="60" as="geometry"/>')
            xml_lines.append('</mxCell>')

        # 边
        edge_id = 100
        for edge in edges:
            xml_lines.append(
                f'<mxCell id="{edge_id}" source="{edge.source}" target="{edge.target}" '
                f'edge="1" parent="1">'
            )
            xml_lines.append('  <mxGeometry relative="1" as="geometry"/>')
            xml_lines.append('</mxCell>')
            edge_id += 1

        xml_lines.append('</root>')
        xml_lines.append('</mxGraphModel>')
        xml_lines.append('</diagram>')
        xml_lines.append('</mxfile>')

        return "\n".join(xml_lines)

    def _get_drawio_style(self, node: FlowchartNode) -> str:
        """获取Draw.io样式"""
        base_styles = {
            "start": "ellipse;whiteSpace=wrap;html=1;fillColor=#E8EAF6;strokeColor=#3F51B5;",
            "end": "ellipse;whiteSpace=wrap;html=1;fillColor=#FCE4EC;strokeColor=#E91E63;",
            "process": "rounded=1;whiteSpace=wrap;html=1;fillColor=#E3F2FD;strokeColor=#1976D2;",
            "pollutant": "shape=ellipse;whiteSpace=wrap;html=1;fillColor=#FFEBEE;strokeColor=#D32F2F;",
            "treatment": "shape=rhombus;whiteSpace=wrap;html=1;fillColor=#E8F5E9;strokeColor=#388E3C;",
        }
        return base_styles.get(node.type, "rounded=1;whiteSpace=wrap;html=1;")

    def _to_svg(self, nodes: List[FlowchartNode], edges: List[FlowchartEdge]) -> str:
        """生成SVG格式流程图"""
        svg_lines = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600">',
            '<defs>',
            '<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
            '  <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>',
            '</marker>',
            '</defs>',
            '<style>',
            '.node-process { fill: #E3F2FD; stroke: #1976D2; stroke-width: 2; }',
            '.node-pollutant { fill: #FFEBEE; stroke: #D32F2F; stroke-width: 2; }',
            '.node-treatment { fill: #E8F5E9; stroke: #388E3C; stroke-width: 2; }',
            '.edge { stroke: #333; stroke-width: 1.5; fill: none; marker-end: url(#arrowhead); }',
            '.node-text { font-family: Arial; font-size: 12px; text-anchor: middle; dominant-baseline: middle; }',
            '</style>',
        ]

        # 绘制边
        for edge in edges:
            # 简化：只画直线
            svg_lines.append(f'<line class="edge" x1="100" y1="300" x2="200" y2="300"/>')

        # 绘制节点
        for i, node in enumerate(nodes):
            x = 100 + i * 150
            y = 250
            svg_lines.append(
                f'<g class="node-{node.type}">'
                f'<rect x="{x}" y="{y}" width="120" height="60" rx="5"/>'
                f'<text class="node-text" x="{x + 60}" y="{y + 30}">{node.name}</text>'
                f'</g>'
            )

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)

    def _to_json(self, nodes: List[FlowchartNode], edges: List[FlowchartEdge]) -> str:
        """转换为JSON格式"""
        data = {
            "nodes": [n.__dict__ for n in nodes],
            "edges": [e.__dict__ for e in edges],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def generate_pollutant_diagram(self, air_pollutants: List[Dict],
                                   water_pollutants: List[Dict],
                                   solid_wastes: List[Dict]) -> Dict[str, Any]:
        """
        生成污染物排放示意图

        Args:
            air_pollutants: 废气污染物
            water_pollutants: 废水污染物
            solid_wastes: 固体废物

        Returns:
            污染物图数据
        """
        logger.info("生成污染物排放图")

        # 按类型分组
        pollutant_data = {
            "废气": air_pollutants,
            "废水": water_pollutants,
            "固废": solid_wastes,
        }

        # 生成饼图数据
        pie_data = []
        for ptype, polls in pollutant_data.items():
            for poll in polls:
                pie_data.append({
                    "name": poll.get("name", ""),
                    "type": ptype,
                    "amount": poll.get("amount", 0),
                    "unit": poll.get("unit", ""),
                })

        # 生成条形图数据
        bar_data = []
        for poll in (air_pollutants + water_pollutants):
            bar_data.append({
                "name": poll.get("name", ""),
                "value": poll.get("amount", 0),
                "unit": poll.get("unit", ""),
            })

        return {
            "mermaid": self._pollutant_mermaid(pollutant_data),
            "pie_chart": pie_data,
            "bar_chart": bar_data,
            "summary": self._generate_pollutant_summary(pollutant_data),
        }

    def _pollutant_mermaid(self, data: Dict[str, List[Dict]]) -> str:
        """生成污染物Mermaid图"""
        lines = ["flowchart LR"]
        lines.append("    subgraph 废气排放")
        lines.append("    G1[粉尘] --> GT[治理] --> GD[达标排放]")
        lines.append("    G2[VOCs] --> GT")
        lines.append("    end")
        lines.append("    subgraph 废水排放")
        lines.append("    W1[COD] --> WT[处理] --> WD[达标排放]")
        lines.append("    W2[石油类] --> WT")
        lines.append("    end")
        lines.append("    subgraph 固废处置")
        lines.append("    S1[一般固废] --> SC[收集] --> SS[妥善处置]")
        lines.append("    S2[危险废物] --> SH[资质处置]")
        lines.append("    end")
        return "\n".join(lines)

    def _generate_pollutant_summary(self, data: Dict[str, List[Dict]]) -> str:
        """生成污染物摘要"""
        summary_parts = []

        for ptype, polls in data.items():
            if polls:
                total = sum(p.get("amount", 0) for p in polls)
                names = ", ".join(p.get("name", "") for p in polls[:3])
                summary_parts.append(f"{ptype}：{names}，总量约{total:.1f}kg/h")

        return "；".join(summary_parts) if summary_parts else "暂无污染物数据"

    def generate_mitigation_diagram(self, mitigation_measures: List[Dict]) -> str:
        """
        生成防治措施示意图

        Args:
            mitigation_measures: 防治措施列表

        Returns:
            Mermaid格式图
        """
        lines = ["flowchart TD"]
        lines.append("    subgraph 废气治理")
        lines.append("    GA[布袋除尘] --> GV[活性炭吸附] --> GR[RCO催化燃烧] --> GO[达标排放]")
        lines.append("    end")
        lines.append("    subgraph 废水治理")
        lines.append("    WA[格栅] --> WB[隔油池] --> WC[混凝沉淀] --> WBR[生化处理] --> WO[达标排放]")
        lines.append("    end")
        lines.append("    subgraph 固废治理")
        lines.append("    SA[分类收集] --> SH[危险废物暂存] --> SS[资质单位处置]")
        lines.append("    SB[一般固废] --> SR[资源回收/填埋]")
        lines.append("    end")
        lines.append("    subgraph 噪声控制")
        lines.append("    NA[隔声房] --> NB[减振基础] --> NC[消声器] --> NO[厂界达标]")
        lines.append("    end")
        return "\n".join(lines)

    def generate_complete_report_graphics(self, process_chain: List[str],
                                         pollutants: Dict,
                                         mitigation: List[Dict]) -> Dict[str, str]:
        """
        生成完整报告所需的所有图形

        Returns:
            包含所有图形的字典
        """
        logger.info("生成完整报告图形")

        # 工艺流程图
        flowchart = self.generate_flowchart(
            process_chain,
            pollutants.get("air_pollutants", []),
            mitigation
        )

        # 污染物图
        pollutant_diagram = self.generate_pollutant_diagram(
            pollutants.get("air_pollutants", []),
            pollutants.get("water_pollutants", []),
            pollutants.get("solid_wastes", [])
        )

        # 防治措施图
        mitigation_diagram = self.generate_mitigation_diagram(mitigation)

        return {
            "process_flowchart": flowchart["mermaid"],
            "pollutant_flowchart": pollutant_diagram["mermaid"],
            "mitigation_flowchart": mitigation_diagram,
            "svg": flowchart["svg"],
            "drawio": flowchart["drawio"],
        }
