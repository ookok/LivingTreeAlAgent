# -*- coding: utf-8 -*-
"""
Report Generator 报告生成器
Intelligence Center - Automated Report Generator
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    WORD = "word"
    PDF = "pdf"


class ReportType(Enum):
    DAILY = "daily"       # 日报
    WEEKLY = "weekly"     # 周报
    ALERT = "alert"       # 预警报告
    SPECIAL = "special"   # 专题报告


class ReportStatus(Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """报告章节"""
    title: str = ""
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    order: int = 0


@dataclass
class IntelligenceReport:
    """情报报告"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    report_type: ReportType = ReportType.DAILY
    status: ReportStatus = ReportStatus.DRAFT

    # 时间范围
    start_date: datetime = field(default_factory=datetime.now)
    end_date: datetime = field(default_factory=datetime.now)
    generated_at: Optional[datetime] = None

    # 内容
    summary: str = ""
    sections: List[ReportSection] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)

    # 统计数据
    stats: Dict[str, Any] = field(default_factory=dict)

    # 格式与输出
    format: ReportFormat = ReportFormat.MARKDOWN
    output_path: str = ""


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: str = ""):
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "hermes_reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        title: str,
        report_type: ReportType,
        sections: List[ReportSection],
        format: ReportFormat = ReportFormat.MARKDOWN,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> IntelligenceReport:
        """生成报告"""
        report = IntelligenceReport(
            title=title,
            report_type=report_type,
            sections=sorted(sections, key=lambda x: x.order),
            format=format,
            start_date=start_date or datetime.now() - timedelta(days=1),
            end_date=end_date or datetime.now(),
        )

        # 生成摘要
        report.summary = self._generate_summary(report)

        # 统计
        report.stats = self._generate_stats(report)

        return report

    def _generate_summary(self, report: IntelligenceReport) -> str:
        """生成摘要"""
        summaries = {
            ReportType.DAILY: f"今日情报汇总报告 ({report.start_date.strftime('%Y-%m-%d')})",
            ReportType.WEEKLY: f"本周情报周报 ({report.start_date.strftime('%Y-%m-%d')} ~ {report.end_date.strftime('%Y-%m-%d')})",
            ReportType.ALERT: "专项预警报告",
            ReportType.SPECIAL: "专题分析报告",
        }
        return summaries.get(report.report_type, "")

    def _generate_stats(self, report: IntelligenceReport) -> Dict[str, Any]:
        """生成统计"""
        return {
            "total_sections": len(report.sections),
            "key_findings_count": len(report.key_findings),
        }

    def render_markdown(self, report: IntelligenceReport) -> str:
        """渲染为Markdown"""
        lines = []

        # 标题
        lines.append(f"# {report.title}")
        lines.append("")

        # 元信息
        lines.append(f"**报告类型:** {report.report_type.value}")
        lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**时间范围:** {report.start_date.strftime('%Y-%m-%d')} ~ {report.end_date.strftime('%Y-%m-%d')}")
        lines.append("")

        # 摘要
        if report.summary:
            lines.append("## 摘要")
            lines.append(report.summary)
            lines.append("")

        # 关键发现
        if report.key_findings:
            lines.append("## 关键发现")
            for i, finding in enumerate(report.key_findings, 1):
                lines.append(f"{i}. {finding}")
            lines.append("")

        # 章节
        for section in report.sections:
            if section.title:
                lines.append(f"## {section.title}")
            lines.append(section.content)
            lines.append("")

        # 统计
        if report.stats:
            lines.append("## 统计数据")
            for key, value in report.stats.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        return "\n".join(lines)

    def render_html(self, report: IntelligenceReport) -> str:
        """渲染为HTML"""
        md = self.render_markdown(report)
        # 简单的Markdown到HTML转换
        html = md.replace("# ", "<h1>").replace("\n## ", "</h1>\n<h2>")
        html = html.replace("\n### ", "</h2>\n<h3>")
        html = html.replace("\n## ", "</h2>\n<h2>")
        html = html.replace("\n", "<br/>\n")
        html = f"<html><body>{html}</body></html>"
        return html

    def save(self, report: IntelligenceReport) -> str:
        """保存报告"""
        if report.format == ReportFormat.MARKDOWN:
            content = self.render_markdown(report)
            ext = "md"
        elif report.format == ReportFormat.HTML:
            content = self.render_html(report)
            ext = "html"
        else:
            content = self.render_markdown(report)
            ext = "md"

        filename = f"{report.report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        filepath = self.output_dir / filename

        filepath.write_text(content, encoding="utf-8")
        report.output_path = str(filepath)
        report.status = ReportStatus.COMPLETED
        report.generated_at = datetime.now()

        logger.info(f"报告已保存: {filepath}")
        return str(filepath)


class CompetitorDailyReportGenerator:
    """竞品监控日报生成器"""

    def __init__(self, output_dir: str = ""):
        self.generator = ReportGenerator(output_dir)

    def generate(
        self,
        competitor_data: Dict[str, Any],
        intel_list: List[Any],
        health_data: Dict[str, Any],
    ) -> IntelligenceReport:
        """生成竞品监控日报"""

        sections = []

        # 概览
        overview = ReportSection(title="竞品概览", order=1)
        overview.content = self._render_overview(competitor_data, health_data)
        sections.append(overview)

        # 动态追踪
        dynamics = ReportSection(title="最新动态", order=2)
        dynamics.content = self._render_dynamics(intel_list)
        sections.append(dynamics)

        # 健康度分析
        health = ReportSection(title="健康度分析", order=3)
        health.content = self._render_health(health_data)
        sections.append(health)

        # 风险预警
        risks = ReportSection(title="风险预警", order=4)
        risks.content = self._render_risks(intel_list)
        sections.append(risks)

        report = self.generator.generate(
            title=f"竞品监控日报 {datetime.now().strftime('%Y-%m-%d')}",
            report_type=ReportType.DAILY,
            sections=sections,
            format=ReportFormat.MARKDOWN,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
        )

        return report

    def _render_overview(self, data: Dict, health: Dict) -> str:
        lines = []
        competitors = data.get("competitors", [])
        lines.append(f"共监控 **{len(competitors)}** 个竞品\n")

        for comp in competitors[:5]:
            health_info = health.get(comp.get("id", ""), {})
            status = health_info.get("status", "unknown")
            score = health_info.get("score", 0)
            lines.append(f"- **{comp.get('name', 'Unknown')}**: 健康度 {score:.0f}/100 ({status})")

        return "\n".join(lines)

    def _render_dynamics(self, intel_list: List) -> str:
        if not intel_list:
            return "今日暂无新动态"

        lines = []
        for intel in intel_list[:10]:
            lines.append(f"### {intel.get('title', 'Unknown')}")
            lines.append(f"来源: {intel.get('source', 'Unknown')}")
            lines.append(f"类型: {intel.get('intel_type', 'Unknown')}")
            lines.append(f"内容: {intel.get('content', '')}")
            lines.append("")

        return "\n".join(lines)

    def _render_health(self, health_data: Dict) -> str:
        if not health_data:
            return "暂无健康度数据"

        lines = []
        for comp_id, health in health_data.items():
            name = health.get("name", comp_id)
            score = health.get("score", 0)
            trend = health.get("trend", "stable")
            lines.append(f"- **{name}**: {score:.0f}/100 (趋势: {trend})")

        return "\n".join(lines)

    def _render_risks(self, intel_list: List) -> str:
        risks = [i for i in intel_list if i.get("intel_type") in ("rumor", "complaint")]

        if not risks:
            return "今日无风险预警"

        lines = []
        for risk in risks:
            lines.append(f"- ⚠️ [{risk.get('title', '风险')}] {risk.get('content', '')}")

        return "\n".join(lines)


__all__ = ["ReportFormat", "ReportType", "ReportStatus", "ReportSection",
           "IntelligenceReport", "ReportGenerator", "CompetitorDailyReportGenerator"]