# -*- coding: utf-8 -*-
"""
智能写作多模态内容生成器 - Smart Writing Multimodal Generator
============================================================

职责：
1. 生成结构化表格（对比表、数据表、矩阵表）
2. 生成时间轴和甘特图（Mermaid语法）
3. 生成流程图和架构图
4. 生成图表数据（用于ECharts/Chart.js）
5. 生成公式和数学表达式

支持格式：
- Mermaid 图表
- ECharts JSON 配置
- HTML 表格
- LaTeX 公式
- Markdown 表格

Author: Hermes Desktop Team
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# 内容类型枚举
# =============================================================================

class ContentType(Enum):
    """内容类型"""
    TABLE = "table"                   # 表格
    TIMELINE = "timeline"             # 时间轴
    GANTT = "gantt"                  # 甘特图
    FLOWCHART = "flowchart"          # 流程图
    SEQUENCE = "sequence"             # 时序图
    CLASS_DIAGRAM = "class_diagram"   # 类图
    CHART = "chart"                  # 图表
    FORMULA = "formula"               # 公式
    MATRIX = "matrix"                 # 矩阵
    COMPARISON = "comparison"         # 对比


class ChartType(Enum):
    """图表类型"""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    RADAR = "radar"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    SANKEY = "sankey"


# =============================================================================
# 生成结果
# =============================================================================

@dataclass
class GeneratedContent:
    """生成的内容"""
    content_type: ContentType         # 内容类型
    
    # 原始数据
    title: str = ""                    # 标题
    data: Any = None                   # 原始数据
    
    # 渲染输出
    mermaid_code: str = ""             # Mermaid代码
    echarts_option: Dict = field(default_factory=dict)  # ECharts配置
    html_table: str = ""               # HTML表格
    markdown_table: str = ""           # Markdown表格
    latex_formula: str = ""            # LaTeX公式
    
    # 元数据
    generated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "content_type": self.content_type.value,
            "title": self.title,
            "mermaid_code": self.mermaid_code,
            "echarts_option": self.echarts_option,
            "html_table": self.html_table,
            "markdown_table": self.markdown_table,
            "generated_at": self.generated_at.isoformat(),
        }


# =============================================================================
# 表格生成器
# =============================================================================

class TableGenerator:
    """表格生成器"""
    
    @staticmethod
    def generate_data_table(
        title: str,
        headers: List[str],
        rows: List[List[Any]],
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成数据表格
        
        Args:
            title: 表格标题
            headers: 表头
            rows: 数据行
            options: 配置选项
        """
        options = options or {}
        
        content = GeneratedContent(
            content_type=ContentType.TABLE,
            title=title,
            data={"headers": headers, "rows": rows},
        )
        
        # Markdown表格
        content.markdown_table = TableGenerator._to_markdown(headers, rows)
        
        # HTML表格
        content.html_table = TableGenerator._to_html(headers, rows, options)
        
        # ECharts表格视图
        content.echarts_option = TableGenerator._to_echarts_table(title, headers, rows)
        
        return content
    
    @staticmethod
    def generate_comparison_table(
        title: str,
        items: List[str],
        criteria: List[str],
        matrix: List[List[str]],
    ) -> GeneratedContent:
        """
        生成对比表格
        
        Args:
            title: 表格标题
            items: 对比项
            criteria: 对比维度
            matrix: 对比矩阵
        """
        headers = ["对比项"] + criteria
        
        rows = []
        for i, item in enumerate(items):
            row = [item] + matrix[i]
            rows.append(row)
        
        content = GeneratedContent(
            content_type=ContentType.COMPARISON,
            title=title,
            data={"items": items, "criteria": criteria, "matrix": matrix},
        )
        
        content.markdown_table = TableGenerator._to_markdown(headers, rows)
        content.html_table = TableGenerator._to_html(headers, rows, {"striped": True})
        
        return content
    
    @staticmethod
    def _to_markdown(headers: List[str], rows: List[List[Any]]) -> str:
        """转换为Markdown"""
        lines = []
        
        # 表头
        header_line = "| " + " | ".join(str(h) for h in headers) + " |"
        lines.append(header_line)
        
        # 分隔线
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        lines.append(separator)
        
        # 数据行
        for row in rows:
            row_line = "| " + " | ".join(str(cell) for cell in row) + " |"
            lines.append(row_line)
        
        return "\n".join(lines)
    
    @staticmethod
    def _to_html(
        headers: List[str],
        rows: List[List[Any]],
        options: Dict,
    ) -> str:
        """转换为HTML"""
        parts = ['<table class="data-table">']
        
        # 样式
        if options.get("striped"):
            parts.append('<style>.data-table {border-collapse: collapse; width: 100%;}')
            parts.append('.data-table th, .data-table td {border: 1px solid #ddd; padding: 8px; text-align: left;}')
            parts.append('.data-table th {background-color: #4CAF50; color: white;}')
            parts.append('.data-table tr:nth-child(even) {background-color: #f2f2f2;}</style>')
        
        # 表头
        parts.append("<thead><tr>")
        for h in headers:
            parts.append(f"<th>{h}</th>")
        parts.append("</tr></thead>")
        
        # 数据
        parts.append("<tbody>")
        for row in rows:
            parts.append("<tr>")
            for cell in row:
                parts.append(f"<td>{cell}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")
        
        parts.append("</table>")
        return "\n".join(parts)
    
    @staticmethod
    def _to_echarts_table(
        title: str,
        headers: List[str],
        rows: List[List[Any]],
    ) -> Dict:
        """转换为ECharts表格配置"""
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
            "toolbox": {
                "feature": {
                    "saveAsImage": {},
                }
            },
            "dataset": {
                "dimensions": headers,
                "source": rows,
            },
            "grid": {"containLabel": True},
            "xAxis": {"type": "category", "gridIndex": 0},
            "yAxis": {"type": "value", "gridIndex": 0},
            "series": [
                {"type": "table", "datasetIndex": 0}
            ],
        }


# =============================================================================
# 图表生成器
# =============================================================================

class ChartGenerator:
    """图表生成器"""
    
    @staticmethod
    def generate_bar_chart(
        title: str,
        categories: List[str],
        series_data: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """生成柱状图"""
        options = options or {}
        
        series = []
        for s in series_data:
            series.append({
                "name": s.get("name", ""),
                "type": "bar",
                "data": s.get("data", []),
            })
        
        echarts_config = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"data": [s.get("name", "") for s in series_data], "top": 30},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 0}},
            "yAxis": {"type": "value"},
            "series": series,
        }
        
        content = GeneratedContent(
            content_type=ContentType.CHART,
            title=title,
            data={"categories": categories, "series": series_data},
            echarts_option=echarts_config,
        )
        
        # Mermaid格式（简化）
        content.mermaid_code = f"%% {title}\nbar chart\n    | {categories[0]} | {series_data[0].get('data', ['N/A'])[0]}"
        
        return content
    
    @staticmethod
    def generate_pie_chart(
        title: str,
        data: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """生成饼图"""
        options = options or {}
        
        echarts_config = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left", "top": 30},
            "series": [{
                "name": title,
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "itemStyle": {
                    "borderRadius": 10,
                    "borderColor": "#fff",
                    "borderWidth": 2,
                },
                "label": {"show": False, "position": "center"},
                "emphasis": {
                    "label": {"show": True, "fontSize": 20, "fontWeight": "bold"},
                },
                "labelLine": {"show": False},
                "data": [{"name": d.get("name", ""), "value": d.get("value", 0)} for d in data],
            }],
        }
        
        content = GeneratedContent(
            content_type=ContentType.CHART,
            title=title,
            data={"slices": data},
            echarts_option=echarts_config,
        )
        
        # 简单文本表示
        total = sum(d.get("value", 0) for d in data)
        summary = "\n".join(f"- {d.get('name', '')}: {d.get('value', 0)} ({d.get('value', 0)/total*100:.1f}%)" for d in data)
        content.mermaid_code = f"## {title}\n{summary}"
        
        return content
    
    @staticmethod
    def generate_line_chart(
        title: str,
        x_data: List[Any],
        series_data: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """生成折线图"""
        options = options or {}
        
        series = []
        for s in series_data:
            series.append({
                "name": s.get("name", ""),
                "type": "line",
                "data": s.get("data", []),
                "smooth": True,
            })
        
        echarts_config = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [s.get("name", "") for s in series_data], "top": 30},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": series,
        }
        
        content = GeneratedContent(
            content_type=ContentType.CHART,
            title=title,
            data={"x_axis": x_data, "series": series_data},
            echarts_option=echarts_config,
        )
        
        return content
    
    @staticmethod
    def generate_radar_chart(
        title: str,
        indicators: List[Dict],
        series_data: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """生成雷达图"""
        options = options or {}
        
        echarts_config = {
            "title": {"text": title, "left": "center"},
            "tooltip": {},
            "legend": {"data": [s.get("name", "") for s in series_data], "top": 30},
            "radar": {
                "indicator": [
                    {"name": ind.get("name", ""), "max": ind.get("max", 100)}
                    for ind in indicators
                ],
                "radius": "65%",
            },
            "series": [{
                "name": title,
                "type": "radar",
                "data": [
                    {"name": s.get("name", ""), "value": s.get("data", [])}
                    for s in series_data
                ],
            }],
        }
        
        content = GeneratedContent(
            content_type=ContentType.CHART,
            title=title,
            data={"indicators": indicators, "series": series_data},
            echarts_option=echarts_config,
        )
        
        return content


# =============================================================================
# 图表生成器（Mermaid）
# =============================================================================

class DiagramGenerator:
    """图表生成器（Mermaid语法）"""
    
    @staticmethod
    def generate_timeline(
        title: str,
        events: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成时间轴
        
        Args:
            title: 标题
            events: 事件列表 [{"date": "", "event": "", "description": ""}]
        """
        content = GeneratedContent(
            content_type=ContentType.TIMELINE,
            title=title,
            data={"events": events},
        )
        
        # Mermaid时间轴
        lines = ["timeline"]
        lines.append(f"    title {title}")
        
        for event in events:
            date = event.get("date", "")
            event_name = event.get("event", "")
            desc = event.get("description", "")
            lines.append(f"    {date}: {event_name}")
        
        content.mermaid_code = "\n".join(lines)
        
        return content
    
    @staticmethod
    def generate_gantt(
        title: str,
        tasks: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成甘特图
        
        Args:
            title: 标题
            tasks: 任务列表 [{"name": "", "start": "", "end": "", "progress": 0-100}]
        """
        options = options or {}
        
        content = GeneratedContent(
            content_type=ContentType.GANTT,
            title=title,
            data={"tasks": tasks},
        )
        
        # Mermaid甘特图
        lines = ["gantt"]
        lines.append(f"    title {title}")
        lines.append("    dateFormat YYYY-MM-DD")
        
        # 分组
        sections = {}
        for task in tasks:
            section = task.get("section", "默认")
            if section not in sections:
                sections[section] = []
            sections[section].append(task)
        
        for section_name, section_tasks in sections.items():
            lines.append(f"    section {section_name}")
            for task in section_tasks:
                name = task.get("name", "")
                start = task.get("start", "")
                end = task.get("end", "")
                done = task.get("progress", 0)
                lines.append(f"        {name}: {done}, {start}, {end}")
        
        content.mermaid_code = "\n".join(lines)
        
        # ECharts甘特图
        content.echarts_option = DiagramGenerator._to_echarts_gantt(title, tasks)
        
        return content
    
    @staticmethod
    def _to_echarts_gantt(title: str, tasks: List[Dict]) -> Dict:
        """转换为ECharts甘特图"""
        categories = [t.get("name", "") for t in tasks]
        
        return {
            "title": {"text": title},
            "tooltip": {"formatter": lambda p: f"{p.name}: {p.value}"},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "time", "axisLabel": {"formatter": "{yyyy-MM}"}},
            "yAxis": {"type": "category", "data": categories},
            "series": [{
                "type": "custom",
                "renderItem": "function(params, api) {}",
                "data": [],
            }],
        }
    
    @staticmethod
    def generate_flowchart(
        title: str,
        nodes: List[Dict],
        edges: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成流程图
        
        Args:
            title: 标题
            nodes: 节点列表 [{"id": "", "label": "", "type": "start/end/process/decision/io"}]
            edges: 边列表 [{"from": "", "to": "", "label": ""}]
        """
        options = options or {}
        direction = options.get("direction", "TB")  # TB/TD/LR/RL
        
        content = GeneratedContent(
            content_type=ContentType.FLOWCHART,
            title=title,
            data={"nodes": nodes, "edges": edges},
        )
        
        # Mermaid流程图
        lines = [f"flowchart {direction}"]
        
        # 节点定义
        node_styles = {}
        for node in nodes:
            node_id = node.get("id", "")
            label = node.get("label", node_id)
            node_type = node.get("type", "process")
            
            # 节点形状
            if node_type == "start":
                shape = f"({label})"
            elif node_type == "end":
                shape = f"([{label}])"
            elif node_type == "decision":
                shape = f"{{{label}}}"
            elif node_type == "io":
                shape = f"[{label}]"
            else:
                shape = f"[{label}]"
            
            lines.append(f"    {node_id}{shape}")
        
        # 边定义
        for edge in edges:
            from_node = edge.get("from", "")
            to_node = edge.get("to", "")
            label = edge.get("label", "")
            
            if label:
                lines.append(f"    {from_node} -->|{label}| {to_node}")
            else:
                lines.append(f"    {from_node} --> {to_node}")
        
        content.mermaid_code = "\n".join(lines)
        
        return content
    
    @staticmethod
    def generate_sequence(
        title: str,
        participants: List[str],
        interactions: List[Dict],
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成时序图
        
        Args:
            title: 标题
            participants: 参与者列表
            interactions: 交互列表 [{"from": "", "to": "", "message": "", "type": "sync/async/response"}]
        """
        content = GeneratedContent(
            content_type=ContentType.SEQUENCE,
            title=title,
            data={"participants": participants, "interactions": interactions},
        )
        
        # Mermaid时序图
        lines = ["sequenceDiagram"]
        
        # 参与者
        for p in participants:
            lines.append(f"    participant {p}")
        
        # 交互
        for i, interaction in enumerate(interactions, 1):
            from_p = interaction.get("from", "")
            to_p = interaction.get("to", "")
            msg = interaction.get("message", "")
            msg_type = interaction.get("type", "sync")
            
            if msg_type == "sync":
                arrow = "->>"
            elif msg_type == "async":
                arrow = "-->>"
            elif msg_type == "response":
                arrow = "<<-"
            else:
                arrow = "->>"
            
            lines.append(f"    {from_p}{arrow}{to_p}: {msg}")
        
        content.mermaid_code = "\n".join(lines)
        
        return content


# =============================================================================
# 公式生成器
# =============================================================================

class FormulaGenerator:
    """公式生成器"""
    
    # 常用公式模板
    FORMULA_TEMPLATES = {
        "npv": {
            "latex": r"NPV = \sum_{t=0}^{n} \frac{C_t}{(1+r)^t}",
            "description": "净现值公式",
            "variables": ["Ct: t年现金流", "r: 折现率", "n: 项目寿命"],
        },
        "irr": {
            "latex": r"\sum_{t=0}^{n} \frac{C_t}{(1+IRR)^t} = 0",
            "description": "内部收益率方程",
            "variables": ["IRR: 内部收益率"],
        },
        "emission": {
            "latex": r"E = A \times EF \times (1 - \eta/100)",
            "description": "排放量计算公式",
            "variables": ["A: 活动水平", "EF: 排放系数", "η: 去除效率(%)"],
        },
        "risk": {
            "latex": r"R = L \times S",
            "description": "LS法风险值",
            "variables": ["L: 可能性", "S: 严重性"],
        },
        "sensitivity": {
            "latex": r"S = \frac{\Delta NPV/NPV}{\Delta X/X}",
            "description": "敏感度公式",
            "variables": ["ΔNPV: NPV变化量", "X: 变量值"],
        },
        "scale_factor": {
            "latex": r"C_2 = C_1 \times (\frac{S_2}{S_1})^n",
            "description": "规模系数法",
            "variables": ["C1: 已知投资", "S1: 已知规模", "S2: 目标规模", "n: 规模指数"],
        },
    }
    
    @classmethod
    def generate_formula(
        cls,
        formula_key: str,
        variables: Dict[str, float] = None,
    ) -> GeneratedContent:
        """生成公式"""
        template = cls.FORMULA_TEMPLATES.get(formula_key, {})
        
        content = GeneratedContent(
            content_type=ContentType.FORMULA,
            title=template.get("description", formula_key),
            latex_formula=template.get("latex", ""),
        )
        
        # 如果提供了变量值，计算结果
        if variables:
            content.data = {"formula_key": formula_key, "variables": variables}
        
        return content
    
    @classmethod
    def generate_custom_formula(
        cls,
        name: str,
        latex: str,
        description: str = "",
        variables: List[str] = None,
    ) -> GeneratedContent:
        """生成自定义公式"""
        content = GeneratedContent(
            content_type=ContentType.FORMULA,
            title=name,
            latex_formula=latex,
            data={"description": description, "variables": variables or []},
        )
        return content


# =============================================================================
# 多模态生成器主类
# =============================================================================

class MultimodalContentGenerator:
    """
    多模态内容生成器
    
    统一接口生成各类可视化内容。
    """
    
    def __init__(self):
        self.table_gen = TableGenerator()
        self.chart_gen = ChartGenerator()
        self.diagram_gen = DiagramGenerator()
        self.formula_gen = FormulaGenerator()
    
    def generate(
        self,
        content_type: ContentType,
        title: str,
        data: Any,
        options: Dict = None,
    ) -> GeneratedContent:
        """
        生成内容
        
        Args:
            content_type: 内容类型
            title: 标题
            data: 数据
            options: 选项
        """
        options = options or {}
        
        if content_type == ContentType.TABLE:
            return self.table_gen.generate_data_table(title, data["headers"], data["rows"], options)
        
        elif content_type == ContentType.COMPARISON:
            return self.table_gen.generate_comparison_table(
                title, data["items"], data["criteria"], data["matrix"]
            )
        
        elif content_type == ContentType.CHART:
            chart_type = options.get("chart_type", ChartType.BAR)
            if chart_type == ChartType.BAR:
                return self.chart_gen.generate_bar_chart(title, data["categories"], data["series"])
            elif chart_type == ChartType.PIE:
                return self.chart_gen.generate_pie_chart(title, data["slices"])
            elif chart_type == ChartType.LINE:
                return self.chart_gen.generate_line_chart(title, data["x_data"], data["series"])
            elif chart_type == ChartType.RADAR:
                return self.chart_gen.generate_radar_chart(title, data["indicators"], data["series"])
        
        elif content_type == ContentType.TIMELINE:
            return self.diagram_gen.generate_timeline(title, data["events"], options)
        
        elif content_type == ContentType.GANTT:
            return self.diagram_gen.generate_gantt(title, data["tasks"], options)
        
        elif content_type == ContentType.FLOWCHART:
            return self.diagram_gen.generate_flowchart(title, data["nodes"], data["edges"], options)
        
        elif content_type == ContentType.SEQUENCE:
            return self.diagram_gen.generate_sequence(
                title, data["participants"], data["interactions"], options
            )
        
        elif content_type == ContentType.FORMULA:
            return self.formula_gen.generate_formula(data.get("key"), data.get("variables"))
        
        raise ValueError(f"不支持的内容类型: {content_type}")
    
    def generate_investment_estimate_table(
        self,
        project_name: str,
        investment: float,
    ) -> GeneratedContent:
        """生成投资估算表"""
        headers = ["序号", "工程或费用名称", "估算金额(万元)", "占比(%)"]
        
        items = [
            ("1", "工程费用", investment * 0.6, 60),
            ("1.1", "  主要生产工程", investment * 0.35, 35),
            ("1.2", "  辅助生产工程", investment * 0.10, 10),
            ("1.3", "  公用工程", investment * 0.10, 10),
            ("1.4", "  环保工程", investment * 0.05, 5),
            ("2", "工程其他费用", investment * 0.25, 25),
            ("3", "预备费", investment * 0.10, 10),
            ("4", "建设期利息", investment * 0.05, 5),
            ("", "合计", investment, 100),
        ]
        
        rows = [[i[0], i[1], f"{i[2]:.2f}" if isinstance(i[2], float) else i[2], i[3]] for i in items]
        
        return self.table_gen.generate_data_table(
            f"{project_name} - 投资估算表",
            headers,
            rows,
            {"striped": True}
        )
    
    def generate_project_schedule(
        self,
        project_name: str,
        phases: List[Dict],
    ) -> GeneratedContent:
        """生成项目进度表（甘特图）"""
        tasks = []
        for phase in phases:
            tasks.append({
                "name": phase.get("name", ""),
                "section": phase.get("section", "默认"),
                "start": phase.get("start", ""),
                "end": phase.get("end", ""),
                "progress": phase.get("progress", 0),
            })
        
        return self.diagram_gen.generate_gantt(f"{project_name} - 项目进度", tasks)
    
    def generate_process_flowchart(
        self,
        process_name: str,
        steps: List[str],
    ) -> GeneratedContent:
        """生成工艺流程图"""
        nodes = [{"id": "start", "label": "开始", "type": "start"}]
        
        for i, step in enumerate(steps, 1):
            nodes.append({
                "id": f"step{i}",
                "label": step,
                "type": "process",
            })
        
        nodes.append({"id": "end", "label": "结束", "type": "end"})
        
        edges = [{"from": "start", "to": "step1"}]
        for i in range(1, len(steps)):
            edges.append({"from": f"step{i}", "to": f"step{i+1}"})
        edges.append({"from": f"step{len(steps)}", "to": "end"})
        
        return self.diagram_gen.generate_flowchart(f"{process_name} - 工艺流程", nodes, edges)


# =============================================================================
# 单例
# =============================================================================

_instance: Optional[MultimodalContentGenerator] = None


def get_multimodal_generator() -> MultimodalContentGenerator:
    """获取多模态生成器单例"""
    global _instance
    if _instance is None:
        _instance = MultimodalContentGenerator()
    return _instance


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    gen = MultimodalContentGenerator()
    
    # 测试表格
    table = gen.generate_investment_estimate_table("某某项目", 5000)
    print("=== 投资估算表 ===")
    print(table.markdown_table)
    
    # 测试甘特图
    gantt = gen.generate_project_schedule("某某项目", [
        {"name": "可行性研究", "start": "2024-01", "end": "2024-03"},
        {"name": "初步设计", "start": "2024-03", "end": "2024-05"},
        {"name": "施工图设计", "start": "2024-05", "end": "2024-07"},
        {"name": "施工建设", "start": "2024-07", "end": "2025-12"},
    ])
    print("\n=== 项目进度甘特图 ===")
    print(gantt.mermaid_code)
    
    # 测试流程图
    flowchart = gen.generate_process_flowchart("生产工艺", [
        "原料预处理", "反应合成", "产品分离", "精制纯化", "成品包装"
    ])
    print("\n=== 工艺流程图 ===")
    print(flowchart.mermaid_code)
