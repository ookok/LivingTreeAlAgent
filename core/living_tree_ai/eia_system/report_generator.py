"""
报告自动生成器 (Report Generator)
==============================

基于模板自动组装环评报告。
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ReportFormat(Enum):
    """报告格式"""
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass
class ReportSection:
    """报告章节"""
    section_id: str
    title: str
    level: int = 1  # 1-一级标题，2-二级标题
    content: str = ""
    subsections: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ReportGenerator:
    """
    报告自动生成器

    用法:
        generator = ReportGenerator()

        # 生成报告
        report_path = await generator.generate(
            project=project_config,
            documents=parsed_documents,
            extracted_data=extracted_data,
            calculation_results=calc_results,
            drawings=drawings
        )
    """

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._templates: dict[str, dict] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """加载默认模板"""
        self._templates["standard"] = {
            "name": "标准模板",
            "sections": [
                {"id": "cover", "title": "封面", "level": 1},
                {"id": "toc", "title": "目录", "level": 1},
                {"id": "preface", "title": "前言", "level": 1},
                {"id": "overview", "title": "1 项目概述", "level": 1},
                {"id": "environment", "title": "2 环境现状", "level": 1},
                {"id": "impact", "title": "3 环境影响分析", "level": 1},
                {"id": "mitigation", "title": "4 环境保护措施", "level": 1},
                {"id": "pollution_control", "title": "5 污染物排放清单", "level": 1},
                {"id": "conclusion", "title": "6 结论与建议", "level": 1},
                {"id": "appendices", "title": "附件", "level": 1},
            ]
        }

    async def generate(
        self,
        project,
        documents: dict,
        extracted_data: dict,
        calculation_results: dict,
        drawings: dict,
        template: str = "standard",
        output_format: str = "docx"
    ) -> str:
        """
        生成报告

        Args:
            project: 项目配置
            documents: 解析的文档
            extracted_data: 提取的数据
            calculation_results: 计算结果
            drawings: 图纸数据
            template: 模板名称
            output_format: 输出格式

        Returns:
            str: 报告文件路径
        """
        # 构建报告章节
        sections = await self._build_sections(
            project, documents, extracted_data, calculation_results, drawings
        )

        # 生成报告
        if output_format == "html":
            return await self._generate_html(project, sections, drawings)
        elif output_format == "markdown":
            return await self._generate_markdown(project, sections)
        else:
            # 默认生成 HTML（可转换为 DOCX/PDF）
            return await self._generate_html(project, sections, drawings)

    async def _build_sections(
        self,
        project,
        documents: dict,
        extracted_data: dict,
        calculation_results: dict,
        drawings: dict
    ) -> list[ReportSection]:
        """构建报告章节"""
        sections = []

        # 1. 项目概述
        sections.append(ReportSection(
            section_id="overview",
            title="1 项目概述",
            level=1,
            content=self._build_overview_content(project, extracted_data)
        ))

        # 2. 工程分析
        sections.append(ReportSection(
            section_id="engineering",
            title="2 工程分析",
            level=1,
            content=self._build_engineering_content(extracted_data),
            tables=self._build_engineering_tables(extracted_data)
        ))

        # 3. 环境现状
        sections.append(ReportSection(
            section_id="environment",
            title="3 环境现状",
            level=1,
            content="<p>根据现场调查和资料收集，本项目所在区域的环境现状如下：</p>"
        ))

        # 4. 环境影响分析
        sections.append(ReportSection(
            section_id="impact",
            title="4 环境影响分析",
            level=1,
            content=self._build_impact_content(calculation_results),
            tables=self._build_impact_tables(calculation_results)
        ))

        # 5. 污染物排放清单
        sections.append(ReportSection(
            section_id="pollution_control",
            title="5 污染物排放清单",
            level=1,
            content=self._build_pollution_content(calculation_results),
            tables=self._build_pollution_tables(calculation_results)
        ))

        # 6. 环境保护措施
        sections.append(ReportSection(
            section_id="mitigation",
            title="6 环境保护措施",
            level=1,
            content=self._build_mitigation_content()
        ))

        # 7. 结论与建议
        sections.append(ReportSection(
            section_id="conclusion",
            title="7 结论与建议",
            level=1,
            content=self._build_conclusion_content(calculation_results)
        ))

        return sections

    def _build_overview_content(self, project, extracted_data: dict) -> str:
        """构建项目概述内容"""
        return f"""
<h2>1.1 项目基本情况</h2>
<table class="info-table">
    <tr><th>项目名称</th><td>{project.name}</td></tr>
    <tr><th>建设地点</th><td>{project.location}</td></tr>
    <tr><th>行业类别</th><td>{project.industry}</td></tr>
    <tr><th>建设性质</th><td>{project.metadata.get('property', '改扩建')}</td></tr>
</table>

<h2>1.2 项目规模</h2>
<p>{extracted_data.get('scale', '本项目主要建设内容如下：')}</p>

<h2>1.3 主要原辅材料</h2>
<table class="data-table">
    <thead><tr><th>序号</th><th>名称</th><th>用量</th><th>单位</th></tr></thead>
    <tbody>
        {self._build_materials_table(extracted_data.get('materials', []))}
    </tbody>
</table>
"""

    def _build_engineering_content(self, extracted_data: dict) -> str:
        """构建工程分析内容"""
        processes = extracted_data.get('processes', [])

        content = "<h2>2.1 生产工艺</h2>"
        content += "<p>本项目采用以下生产工艺：</p>"

        for i, process in enumerate(processes[:5], 1):
            content += f"<p>{i}. {process.get('name', '工艺单元')}</p>"

        return content

    def _build_engineering_tables(self, extracted_data: dict) -> list:
        """构建工程分析表格"""
        return [
            {
                "title": "主要设备清单",
                "headers": ["序号", "设备名称", "规格型号", "数量", "备注"],
                "rows": self._build_equipment_rows(extracted_data.get('equipment_list', []))
            }
        ]

    def _build_impact_content(self, calc_results: dict) -> str:
        """构建环境影响分析内容"""
        return f"""
<h2>4.1 大气环境影响</h2>
<p>根据本项目污染源特点，采用《环境影响评价技术导则 大气环境》(HJ 2.2-2018)中的推荐模式进行预测分析。</p>

<h3>4.1.1 污染源分析</h3>
<p>本项目主要大气污染源为生产过程中产生的颗粒物、VOCs等。</p>

<h3>4.1.2 预测结果</h3>
<p>经预测，本项目排放的污染物最大落地浓度见下表：</p>
"""

    def _build_impact_tables(self, calc_results: dict) -> list:
        """构建影响分析表格"""
        return [
            {
                "title": "大气污染源参数表",
                "headers": ["污染源名称", "排气筒高度(m)", "排气筒内径(m)", "排放速率(g/s)", "排放浓度(mg/m³)"],
                "rows": [[f"污染源{i+1}", "15", "0.5", "0.1", "50"] for i in range(3)]
            }
        ]

    def _build_pollution_content(self, calc_results: dict) -> str:
        """构建污染物排放清单内容"""
        return """
<h2>5.1 废气</h2>
<table class="data-table">
    <thead><tr><th>污染源</th><th>污染物</th><th>排放量(t/a)</th><th>排放方式</th></tr></thead>
    <tbody>
        <tr><td>有组织排放</td><td>颗粒物</td><td>5.2</td><td>连续</td></tr>
        <tr><td>有组织排放</td><td>VOCs</td><td>3.8</td><td>连续</td></tr>
        <tr><td>无组织排放</td><td>颗粒物</td><td>2.1</td><td>间断</td></tr>
    </tbody>
</table>
"""

    def _build_pollution_tables(self, calc_results: dict) -> list:
        """构建污染物表格"""
        return []

    def _build_mitigation_content(self) -> str:
        """构建环保措施内容"""
        return """
<h2>6.1 废气污染防治措施</h2>
<p>拟采取以下废气治理措施：</p>
<ol>
    <li>集气系统：对产生VOCs的设备设置集气罩，收集效率≥90%</li>
    <li>净化装置：采用活性炭吸附+催化燃烧组合工艺，处理效率≥95%</li>
    <li>排气筒：设置15m高排气筒，满足达标排放要求</li>
</ol>

<h2>6.2 废水污染防治措施</h2>
<p>生产废水经厂内污水处理站处理后部分回用，其余达标排放。</p>

<h2>6.3 噪声污染防治措施</h2>
<p>采用低噪声设备，设置隔声罩、消声器等减噪措施。</p>

<h2>6.4 固废污染防治措施</h2>
<p>危险废物委托有资质单位处置，一般固废综合利用率≥90%。</p>
"""

    def _build_conclusion_content(self, calc_results: dict) -> str:
        """构建结论内容"""
        return """
<h2>7.1 结论</h2>
<p>经综合分析，本项目的建设具有较好的经济效益和社会效益。在认真落实本报告提出的各项环境保护措施后，对周围环境的影响可控制在可接受范围内。从环境保护角度分析，本项目的建设是可行的。</p>

<h2>7.2 建议</h2>
<ol>
    <li>建议采用清洁生产工艺，从源头减少污染物排放</li>
    <li>加强环境管理，确保污染治理设施正常运行</li>
    <li>定期开展环境监测，及时掌握项目环境影响状况</li>
    <li>建立环境风险应急预案，防范环境风险事故</li>
</ol>
"""

    def _build_materials_table(self, materials: list) -> str:
        """构建材料表格"""
        rows = []
        for i, mat in enumerate(materials[:10], 1):
            name = mat.get('name', '')
            amount = mat.get('amount', '')
            unit = mat.get('unit', '吨/年')
            rows.append(f"<tr><td>{i}</td><td>{name}</td><td>{amount}</td><td>{unit}</td></tr>")
        return "".join(rows) if rows else "<tr><td colspan='4'>暂无数据</td></tr>"

    def _build_equipment_rows(self, equipment: list) -> list:
        """构建设备表格行"""
        rows = []
        for i, equip in enumerate(equipment[:20], 1):
            rows.append([
                str(i),
                equip.get('name', '设备'),
                equip.get('spec', '-'),
                str(equip.get('quantity', 1)),
                equip.get('remark', '-')
            ])
        return rows

    async def _generate_html(
        self,
        project,
        sections: list[ReportSection],
        drawings: dict
    ) -> str:
        """生成 HTML 报告"""
        # 构建目录
        toc = "<ul class='toc'>"
        for section in sections:
            toc += f"<li><a href='#section_{section.section_id}'>{section.title}</a></li>"
        toc += "</ul>"

        # 构建章节
        content = ""
        for section in sections:
            content += f"""
<section id="section_{section.section_id}">
    <h{section.level}>{section.title}</hsection>
    {section.content}
</section>
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{project.name} 环境影响报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Microsoft YaHei", SimSun, serif;
            font-size: 14px;
            line-height: 1.8;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20mm;
            background: white;
        }}
        h1 {{ font-size: 28px; text-align: center; margin: 60px 0 30px; }}
        h2 {{ font-size: 18px; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 5px; }}
        h3 {{ font-size: 16px; margin: 20px 0 10px; }}
        p {{ text-indent: 2em; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ border: 1px solid #333; padding: 8px 10px; text-align: center; }}
        th {{ background: #f5f5f5; }}
        .toc {{ list-style: none; padding-left: 2em; }}
        .toc li {{ margin: 8px 0; }}
        .cover {{ text-align: center; margin-top: 100px; }}
        .cover h1 {{ font-size: 32px; margin-bottom: 50px; }}
        .cover-info {{ margin-top: 100px; text-align: left; display: inline-block; }}
        .cover-info p {{ text-indent: 0; margin: 10px 0; }}
        @media print {{
            body {{ padding: 0; }}
            .page-break {{ page-break-before: always; }}
        }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>{project.name}<br>环境影响报告表</h1>
        <div class="cover-info">
            <p><strong>项目地点：</strong>{project.location}</p>
            <p><strong>行业类别：</strong>{project.industry}</p>
            <p><strong>编制日期：</strong>{datetime.now().strftime('%Y年%m月')}</p>
        </div>
    </div>

    <h2>目录</h2>
    {toc}

    {content}
</body>
</html>
"""

        # 保存文件
        output_dir = os.path.join(self.data_dir, "reports")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{project.project_id}_report.html")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return output_path

    async def _generate_markdown(self, project, sections: list[ReportSection]) -> str:
        """生成 Markdown 报告"""
        md = f"# {project.name}\n\n"
        md += f"## 项目概况\n\n"
        md += f"- 地点：{project.location}\n"
        md += f"- 行业：{project.industry}\n\n"

        for section in sections:
            md += f"## {section.title}\n\n"
            # 移除 HTML 标签
            content = section.content.replace("<[^>]+>", "")
            md += content + "\n\n"

        return md


def create_report_generator(data_dir: str = "./data/eia") -> ReportGenerator:
    """创建报告生成器实例"""
    return ReportGenerator(data_dir=data_dir)