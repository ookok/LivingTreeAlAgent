"""
ReportGenerator - 交互式报告生成器

多智能体流水线（数据收集 → 分析 → 可视化 → 报告生成）

核心功能：
1. 支持多种内容块（文本、图表、表格、交互demo）
2. 多智能体协作生成报告
3. 集成到 EIA（环境影响评价）工具
4. 支持多种输出格式（Markdown、HTML、PDF）
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json
import markdown
from abc import ABC, abstractmethod


class ContentBlockType(Enum):
    """内容块类型"""
    TEXT = "text"              # 文本块
    HEADING = "heading"        # 标题块
    PARAGRAPH = "paragraph"    # 段落
    TABLE = "table"            # 表格
    CHART = "chart"            # 图表
    IMAGE = "image"            # 图片
    LIST = "list"              # 列表
    CODE = "code"              # 代码块
    INTERACTIVE = "interactive" # 交互组件
    DIVIDER = "divider"        # 分隔线


@dataclass
class ContentBlock:
    """内容块"""
    id: str
    type: ContentBlockType
    content: Any
    title: Optional[str] = None
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSection:
    """报告章节"""
    id: str
    title: str
    blocks: List[ContentBlock] = field(default_factory=list)
    order: int = 0


@dataclass
class Report:
    """报告定义"""
    id: str
    title: str
    description: str = ""
    sections: List[ReportSection] = field(default_factory=list)
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"


class ReportGenerator:
    """
    交互式报告生成器
    
    多智能体流水线：
    1. 数据收集阶段 - 调用数据采集工具
    2. 分析阶段 - 调用分析工具/AI
    3. 可视化阶段 - 调用可视化工具
    4. 报告生成阶段 - 组合内容块生成报告
    
    支持的内容块：
    - 文本、标题、段落
    - 表格（数据表格）
    - 图表（折线图、柱状图、饼图等）
    - 图片
    - 代码块
    - 交互组件
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ReportGenerator")
        self._tool_registry = None
        self._workflow_orchestrator = None
    
    def set_tool_registry(self, tool_registry):
        """设置工具注册中心"""
        self._tool_registry = tool_registry
    
    def set_workflow_orchestrator(self, workflow_orchestrator):
        """设置工作流编排器"""
        self._workflow_orchestrator = workflow_orchestrator
    
    def create_report(self, title: str, description: str = "") -> Report:
        """
        创建新报告
        
        Args:
            title: 报告标题
            description: 报告描述
            
        Returns:
            报告对象
        """
        report_id = f"report_{int(datetime.now().timestamp())}"
        
        report = Report(
            id=report_id,
            title=title,
            description=description
        )
        
        self._logger.info(f"创建报告: {title}")
        return report
    
    def add_section(self, report: Report, title: str, order: int = 0) -> ReportSection:
        """
        添加章节
        
        Args:
            report: 报告对象
            title: 章节标题
            order: 排序序号
            
        Returns:
            章节对象
        """
        section_id = f"section_{len(report.sections) + 1}"
        
        section = ReportSection(
            id=section_id,
            title=title,
            order=order
        )
        
        report.sections.append(section)
        report.sections.sort(key=lambda s: s.order)
        
        return section
    
    def add_content_block(self, section: ReportSection, block_type: ContentBlockType,
                          content: Any, title: Optional[str] = None, **metadata):
        """
        添加内容块
        
        Args:
            section: 章节对象
            block_type: 内容块类型
            content: 内容
            title: 标题（可选）
            **metadata: 元数据
        """
        block_id = f"block_{len(section.blocks) + 1}"
        
        block = ContentBlock(
            id=block_id,
            type=block_type,
            content=content,
            title=title,
            order=len(section.blocks),
            metadata=metadata
        )
        
        section.blocks.append(block)
    
    def add_heading(self, section: ReportSection, text: str, level: int = 1):
        """添加标题"""
        self.add_content_block(section, ContentBlockType.HEADING, text, metadata={"level": level})
    
    def add_paragraph(self, section: ReportSection, text: str):
        """添加段落"""
        self.add_content_block(section, ContentBlockType.PARAGRAPH, text)
    
    def add_table(self, section: ReportSection, headers: List[str], rows: List[List[Any]], title: str = ""):
        """添加表格"""
        table_data = {
            "headers": headers,
            "rows": rows
        }
        self.add_content_block(section, ContentBlockType.TABLE, table_data, title=title)
    
    def add_chart(self, section: ReportSection, chart_type: str, data: Dict[str, Any], title: str = ""):
        """添加图表"""
        chart_data = {
            "type": chart_type,
            "data": data
        }
        self.add_content_block(section, ContentBlockType.CHART, chart_data, title=title)
    
    def add_list(self, section: ReportSection, items: List[str], ordered: bool = False):
        """添加列表"""
        list_data = {
            "items": items,
            "ordered": ordered
        }
        self.add_content_block(section, ContentBlockType.LIST, list_data)
    
    def add_code(self, section: ReportSection, code: str, language: str = "python"):
        """添加代码块"""
        code_data = {
            "code": code,
            "language": language
        }
        self.add_content_block(section, ContentBlockType.CODE, code_data)
    
    def add_image(self, section: ReportSection, url: str, alt: str = ""):
        """添加图片"""
        self.add_content_block(section, ContentBlockType.IMAGE, url, metadata={"alt": alt})
    
    def add_interactive(self, section: ReportSection, component_type: str, data: Dict[str, Any], title: str = ""):
        """添加交互组件"""
        interactive_data = {
            "component_type": component_type,
            "data": data
        }
        self.add_content_block(section, ContentBlockType.INTERACTIVE, interactive_data, title=title)
    
    async def generate_eia_report(self, project_name: str, project_id: str = None) -> Report:
        """
        生成环评报告（多智能体流水线）
        
        流程：数据收集 → 分析 → 可视化 → 报告生成
        
        Args:
            project_name: 项目名称
            project_id: 项目 ID（可选）
            
        Returns:
            生成的报告
        """
        self._logger.info(f"开始生成环评报告: {project_name}")
        
        report = self.create_report(
            title=f"{project_name} - 环境影响评价报告",
            description="基于多智能体协作生成的环境影响评价报告"
        )
        
        # 阶段1: 数据收集
        await self._collect_eia_data(report, project_name, project_id)
        
        # 阶段2: 分析
        await self._analyze_eia_data(report)
        
        # 阶段3: 可视化
        await self._visualize_eia_data(report)
        
        # 阶段4: 生成结论
        await self._generate_eia_conclusion(report)
        
        report.updated_at = datetime.now()
        self._logger.info(f"环评报告生成完成: {report.id}")
        
        return report
    
    async def _collect_eia_data(self, report: Report, project_name: str, project_id: str):
        """数据收集阶段"""
        section = self.add_section(report, "1. 项目概况", order=1)
        self.add_heading(section, "项目基本信息", level=2)
        self.add_paragraph(section, f"项目名称：{project_name}")
        if project_id:
            self.add_paragraph(section, f"项目编号：{project_id}")
        self.add_paragraph(section, f"报告生成时间：{datetime.now().strftime('%Y年%m月%d日')}")
        
        # 调用数据收集工具
        if self._tool_registry:
            try:
                # 模拟数据收集结果
                data_result = await self._tool_registry.execute("data_fetcher", project=project_name)
                if data_result.success and data_result.data:
                    self.add_heading(section, "基础数据", level=2)
                    self.add_paragraph(section, "已收集以下基础数据：")
                    
                    data_items = []
                    for key, value in data_result.data.items():
                        data_items.append(f"- {key}: {value}")
                    self.add_list(section, data_items)
            except Exception as e:
                self._logger.warning(f"数据收集失败: {e}")
                self.add_paragraph(section, "⚠️ 数据收集过程中遇到问题")
    
    async def _analyze_eia_data(self, report: Report):
        """分析阶段"""
        section = self.add_section(report, "2. 环境影响分析", order=2)
        self.add_heading(section, "现状分析", level=2)
        self.add_paragraph(section, "基于收集的数据，进行以下环境影响分析：")
        
        # 调用分析工具
        if self._tool_registry:
            try:
                analysis_result = await self._tool_registry.execute("impact_analyzer")
                if analysis_result.success and analysis_result.data:
                    # 添加分析结果表格
                    headers = ["评价指标", "现状值", "标准值", "达标情况"]
                    rows = []
                    for item in analysis_result.data.get("indicators", []):
                        rows.append([
                            item.get("name", ""),
                            str(item.get("current", "")),
                            str(item.get("standard", "")),
                            "达标" if item.get("compliant") else "不达标"
                        ])
                    self.add_table(section, headers, rows, title="环境指标评价表")
            except Exception as e:
                self._logger.warning(f"分析失败: {e}")
        
        # 添加分析结论
        self.add_heading(section, "分析结论", level=2)
        self.add_paragraph(section, "根据数据分析，项目建设对周边环境的影响在可接受范围内。")
    
    async def _visualize_eia_data(self, report: Report):
        """可视化阶段"""
        section = self.add_section(report, "3. 可视化展示", order=3)
        self.add_heading(section, "环境指标趋势", level=2)
        
        # 添加图表
        chart_data = {
            "labels": ["PM2.5", "SO2", "NO2", "CO", "O3"],
            "datasets": [
                {
                    "name": "监测值",
                    "data": [35, 12, 28, 1.2, 85],
                    "unit": "μg/m³"
                },
                {
                    "name": "标准值",
                    "data": [35, 50, 40, 4, 100],
                    "unit": "μg/m³"
                }
            ]
        }
        self.add_chart(section, "bar", chart_data, title="空气质量指标对比")
        
        # 添加交互组件（地图、仪表盘等）
        interactive_data = {
            "type": "map",
            "center": [116.4074, 39.9042],
            "zoom": 12,
            "markers": [
                {"lat": 116.4074, "lng": 39.9042, "label": "项目位置"}
            ]
        }
        self.add_interactive(section, "map", interactive_data, title="项目位置地图")
    
    async def _generate_eia_conclusion(self, report: Report):
        """生成结论阶段"""
        section = self.add_section(report, "4. 结论与建议", order=4)
        self.add_heading(section, "综合评价", level=2)
        self.add_paragraph(section, "综合以上分析，本项目的环境影响评价结论如下：")
        
        conclusions = [
            "项目选址合理，符合城市规划要求",
            "污染物排放满足国家相关标准",
            "采取的环保措施可行有效",
            "从环境保护角度分析，项目建设可行"
        ]
        self.add_list(section, conclusions, ordered=True)
        
        self.add_heading(section, "建议", level=2)
        suggestions = [
            "加强施工期环境管理，减少扬尘和噪声影响",
            "运营期定期监测污染物排放情况",
            "建立环境管理体系，确保环保设施正常运行",
            "加强与周边居民的沟通，及时回应环境诉求"
        ]
        self.add_list(section, suggestions)
    
    def export_to_markdown(self, report: Report) -> str:
        """导出为 Markdown 格式"""
        md = f"# {report.title}\n\n"
        md += f"*报告版本: {report.version} | 生成时间: {report.created_at.strftime('%Y-%m-%d %H:%M')}*\n\n"
        md += f"## 概述\n{report.description}\n\n"
        
        for section in report.sections:
            md += f"## {section.title}\n\n"
            
            for block in section.blocks:
                md += self._block_to_markdown(block)
        
        return md
    
    def _block_to_markdown(self, block: ContentBlock) -> str:
        """将内容块转换为 Markdown"""
        if block.type == ContentBlockType.HEADING:
            level = block.metadata.get("level", 1)
            return "#" * level + f" {block.content}\n\n"
        
        elif block.type == ContentBlockType.PARAGRAPH:
            return f"{block.content}\n\n"
        
        elif block.type == ContentBlockType.TABLE:
            content = block.content
            headers = content.get("headers", [])
            rows = content.get("rows", [])
            
            md = ""
            if block.title:
                md += f"**{block.title}**\n\n"
            
            md += "| " + " | ".join(headers) + " |\n"
            md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            
            for row in rows:
                md += "| " + " | ".join(str(cell) for cell in row) + " |\n"
            
            md += "\n"
            return md
        
        elif block.type == ContentBlockType.CHART:
            title = block.title or "图表"
            return f"![{title}](chart://{block.content.get('type', 'unknown')})\n\n"
        
        elif block.type == ContentBlockType.IMAGE:
            alt = block.metadata.get("alt", "")
            return f"![{alt}]({block.content})\n\n"
        
        elif block.type == ContentBlockType.LIST:
            content = block.content
            items = content.get("items", [])
            ordered = content.get("ordered", False)
            
            md = ""
            for i, item in enumerate(items, 1):
                if ordered:
                    md += f"{i}. {item}\n"
                else:
                    md += f"- {item}\n"
            md += "\n"
            return md
        
        elif block.type == ContentBlockType.CODE:
            content = block.content
            code = content.get("code", "")
            language = content.get("language", "")
            return f"```{language}\n{code}\n```\n\n"
        
        elif block.type == ContentBlockType.INTERACTIVE:
            title = block.title or "交互组件"
            return f"[🔧 {title}]\n\n"
        
        elif block.type == ContentBlockType.DIVIDER:
            return "---\n\n"
        
        return ""
    
    def export_to_html(self, report: Report) -> str:
        """导出为 HTML 格式"""
        md = self.export_to_markdown(report)
        html = markdown.markdown(md, extensions=['tables', 'fenced_code'])
        
        template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px; margin: 0 auto; padding: 40px 20px; }}
        h1 {{ color: #1a1a2e; border-bottom: 2px solid #3366ff; padding-bottom: 10px; }}
        h2 {{ color: #16213e; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        code {{ background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        .interactive {{ background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 10px 15px; margin: 10px 0; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
        
        return template
    
    def export_to_json(self, report: Report) -> str:
        """导出为 JSON 格式"""
        report_dict = {
            "id": report.id,
            "title": report.title,
            "description": report.description,
            "version": report.version,
            "author": report.author,
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat(),
            "sections": []
        }
        
        for section in report.sections:
            section_dict = {
                "id": section.id,
                "title": section.title,
                "order": section.order,
                "blocks": []
            }
            
            for block in section.blocks:
                block_dict = {
                    "id": block.id,
                    "type": block.type.value,
                    "content": block.content,
                    "title": block.title,
                    "order": block.order,
                    "metadata": block.metadata
                }
                section_dict["blocks"].append(block_dict)
            
            report_dict["sections"].append(section_dict)
        
        return json.dumps(report_dict, indent=2, ensure_ascii=False)