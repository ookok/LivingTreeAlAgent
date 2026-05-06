"""Market Opportunity Inference Engine — announcement → downstream demand → match role → generate lead.

Core insight:
  每一份政府公告都是一个市场信号。不同角色看到同一份公告，看到的是不同的商机。

Example chain:
  环评受理  → 环评批复  → 开工建设  → 验收公示  → 正式运营
     ↓           ↓           ↓           ↓           ↓
  环评机构     批复后续    设备采购    监测机构    运维服务
  (报告编制)   (应急预案)   (废气处理)  (在线监测)  (设备维护)

Role inference:
  - 环评工程师: 看到"受理公示" → 竞品分析、同类项目报价参考
  - 环保工程师: 看到"批复" → 应急预案、排污许可申报机会
  - 设备供应商: 看到"新建项目" → 废气/废水处理设备需求
  - 监测公司:   看到"验收公示" → 在线监测设备+运维合同
  - 律师/咨询:  看到"新标准" → 合规咨询、培训服务
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Role Profiles ═══

@dataclass
class RoleProfile:
    """A professional role with its opportunity triggers."""
    name: str
    keywords: list[str] = field(default_factory=list)        # what this role cares about
    opportunity_triggers: dict[str, str] = field(default_factory=dict)  # stage → opportunity description
    competitor_patterns: list[str] = field(default_factory=list)  # who are the competitors
    service_needed_at_stage: dict[str, list[str]] = field(default_factory=dict)  # stage → what they need


# ═══ Pre-built Role Profiles ═══

ROLE_PROFILES = {
    "eia_engineer": RoleProfile(
        name="环评工程师",
        keywords=["环评", "环境影响", "报告表", "报告书", "受理", "评价"],
        opportunity_triggers={
            "受理公示": "同类项目环评报价参考 + 竞争对手分析",
            "拟批准公示": "项目即将获批，跟踪后续验收需求",
            "审批批复": "批复后可跟进应急预案编制",
        },
        competitor_patterns=["环评", "环境科技", "环保科技", "环境工程"],
        service_needed_at_stage={
            "受理公示": ["环评报告编制", "环境现状监测"],
            "审批批复": ["应急预案编制", "排污许可申报", "环保验收"],
        },
    ),
    "env_engineer": RoleProfile(
        name="环保工程师",
        keywords=["治理", "废水", "废气", "噪声", "固废", "污染"],
        opportunity_triggers={
            "审批批复": "项目确定上马，设备采购窗口期",
            "招标公告": "环保设备招投标信息",
            "验收公示": "在线监测设备+运维机会",
        },
        competitor_patterns=["环保", "环境", "治理", "净化"],
        service_needed_at_stage={
            "审批批复": ["废气处理方案设计", "废水处理工艺方案"],
            "招标公告": ["环保设备投标", "工程总包"],
            "验收公示": ["在线监测设备", "运维合同"],
        },
    ),
    "equipment_supplier": RoleProfile(
        name="设备供应商",
        keywords=["设备", "采购", "招标", "施工", "工程", "扩建", "新建"],
        opportunity_triggers={
            "新建项目": "设备采购需求信号",
            "受理公示": "项目启动 → 预算编制阶段",
            "招标公告": "直接投标机会",
            "审批批复": "设备采购窗口期确认",
        },
        competitor_patterns=["设备", "机械", "制造", "装备"],
        service_needed_at_stage={
            "受理公示": ["设备方案推介", "技术交流"],
            "审批批复": ["设备选型报价", "技术参数对接"],
            "招标公告": ["投标文件编制"],
        },
    ),
    "monitoring_company": RoleProfile(
        name="监测公司",
        keywords=["监测", "检测", "采样", "验收", "比对", "在线"],
        opportunity_triggers={
            "受理公示": "环评监测需求",
            "审批批复": "竣工验收监测合同",
            "验收公示": "在线监测设备+运维长期合同",
        },
        competitor_patterns=["监测", "检测", "测试", "检验"],
        service_needed_at_stage={
            "受理公示": ["环评监测方案", "现状监测报价"],
            "审批批复": ["竣工验收监测", "在线监测比对"],
            "验收公示": ["在线监测运维", "定期检测合同"],
        },
    ),
    "consultant": RoleProfile(
        name="咨询顾问",
        keywords=["标准", "政策", "法规", "合规", "管理", "体系"],
        opportunity_triggers={
            "新标准": "合规咨询+培训需求",
            "审批批复": "环境管理体系认证",
            "验收公示": "清洁生产审核",
        },
        competitor_patterns=["咨询", "管理", "认证", "培训"],
        service_needed_at_stage={
            "受理公示": ["合规预评估"],
            "审批批复": ["环境管理体系认证", "清洁生产审核"],
            "验收公示": ["绿色工厂申报", "碳足迹核算"],
        },
    ),
}


# ═══ Opportunity Item ═══

@dataclass
class Opportunity:
    """A single market opportunity inferred from an announcement."""
    project_name: str
    stage: str
    date: str
    role: str
    opportunity_description: str
    urgency: str = "normal"        # "immediate", "normal", "monitor"
    estimated_value_range: str = ""  # "10-50万", "50-200万", etc.
    competitor_risk: str = "low"   # "high", "medium", "low"
    action_items: list[str] = field(default_factory=list)
    source_url: str = ""


@dataclass
class OpportunityReport:
    """Complete market opportunity analysis for a role."""
    role: str
    role_name: str
    generated_at: str = ""
    total_opportunities: int = 0
    by_stage: dict = field(default_factory=dict)
    by_urgency: dict = field(default_factory=dict)
    opportunities: list[Opportunity] = field(default_factory=list)
    competitor_analysis: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    raw_text: str = ""


class OpportunityEngine:
    """Market opportunity inference engine.

    Usage:
        engine = OpportunityEngine()
        opps = engine.infer_from_announcement(
            title="[审批批复] 亚威变压器扩建项目环评批复",
            date="2026-04-28",
            role="eia_engineer",
        )
        # → [Opportunity(project="亚威变压器", stage="审批批复",
        #      description="批复后可跟进应急预案编制", urgency="normal")]

        report = engine.generate_report(opps, "env_engineer")
    """

    def __init__(self):
        self._roles = ROLE_PROFILES

    def infer_from_announcement(
        self,
        title: str,
        date: str,
        source_url: str = "",
        role: str = "eia_engineer",
    ) -> list[Opportunity]:
        """Infer market opportunities from a single announcement for a specific role."""
        profile = self._roles.get(role)
        if not profile:
            return []

        opportunities = []
        stage = self._detect_stage(title)
        project = self._extract_project_name(title)

        if stage in profile.opportunity_triggers:
            desc = profile.opportunity_triggers[stage]
            services = profile.service_needed_at_stage.get(stage, [])

            opp = Opportunity(
                project_name=project or title[:100],
                stage=stage,
                date=date,
                role=role,
                opportunity_description=f"{stage}: {desc}",
                urgency=self._assess_urgency(stage, date),
                estimated_value_range=self._estimate_value(title, role),
                competitor_risk=self._assess_competitor_risk(title, profile),
                action_items=services[:5],
                source_url=source_url,
            )
            opportunities.append(opp)

        # Also check for multi-role cross-opportunities
        if stage in ("审批批复", "验收公示"):
            downstream_stages = self._infer_downstream_stages(stage)
            for d_stage, d_desc in downstream_stages.items():
                opp = Opportunity(
                    project_name=project or title[:100],
                    stage=f"{stage}→{d_stage}",
                    date=date,
                    role=role,
                    opportunity_description=f"前置{stage} → 后续{d_stage}: {d_desc}",
                    urgency="monitor",
                    action_items=[f"跟踪项目{d_stage}阶段"],
                    source_url=source_url,
                )
                opportunities.append(opp)

        return opportunities

    def infer_batch(
        self,
        announcements: list[tuple[str, str, str]],  # [(title, date, url), ...]
        role: str = "eia_engineer",
    ) -> list[Opportunity]:
        """Infer opportunities from multiple announcements."""
        all_opps = []
        for title, date, url in announcements:
            opps = self.infer_from_announcement(title, date, url, role)
            all_opps.extend(opps)
        return sorted(all_opps, key=lambda o: o.urgency == "immediate", reverse=True)

    def generate_report(
        self,
        opportunities: list[Opportunity],
        role: str = "eia_engineer",
    ) -> OpportunityReport:
        """Generate a market opportunity report for a role."""
        profile = self._roles.get(role)
        role_name = profile.name if profile else role

        report = OpportunityReport(
            role=role,
            role_name=role_name,
            generated_at=time.strftime("%Y-%m-%d %H:%M"),
            total_opportunities=len(opportunities),
        )

        by_stage = Counter(o.stage for o in opportunities)
        report.by_stage = dict(by_stage)
        by_urgency = Counter(o.urgency for o in opportunities)
        report.by_urgency = dict(by_urgency)

        # Sort: immediate first, then normal, then monitor
        urgency_order = {"immediate": 0, "normal": 1, "monitor": 2}
        report.opportunities = sorted(opportunities, key=lambda o: urgency_order.get(o.urgency, 3))

        report.competitor_analysis = self._analyze_competitors(opportunities, profile)
        report.recommendations = self._generate_recommendations(report)
        report.raw_text = self._format_report(report)

        return report

    def generate_multi_role_report(
        self,
        announcements: list[tuple[str, str, str]],
        roles: list[str] = None,
    ) -> dict[str, OpportunityReport]:
        """Generate opportunity reports for multiple roles."""
        roles = roles or list(ROLE_PROFILES.keys())
        reports = {}
        for role in roles:
            opps = self.infer_batch(announcements, role)
            reports[role] = self.generate_report(opps, role)
        return reports

    # ═══ Inference Helpers ═══

    @staticmethod
    def _detect_stage(title: str) -> str:
        stage_map = [
            ("受理公示", "受理公示"),
            ("拟批准公示", "拟批准公示"),
            ("审批批复", "审批批复"),
            ("验收公示", "验收公示"),
            ("招标公告", "招标公告"),
            ("新建", "新建项目"),
            ("扩建", "新建项目"),
        ]
        for keyword, stage in stage_map:
            if keyword in title:
                return stage
        return "其他公告"

    @staticmethod
    def _extract_project_name(title: str) -> str:
        name = re.sub(r'\[.*?\]', '', title).strip()
        if "项目" in name:
            name = name[:name.index("项目") + 2]
        return name[:100]

    @staticmethod
    def _infer_downstream_stages(current_stage: str) -> dict[str, str]:
        chains = {
            "审批批复": {"验收公示": "项目投产后需竣工验收", "招标公告": "建设阶段设备采购需求"},
            "验收公示": {"运维服务": "长期设备运维合同机会"},
        }
        return chains.get(current_stage, {})

    @staticmethod
    def _assess_urgency(stage: str, date: str) -> str:
        if stage in ("招标公告", "审批批复"):
            return "immediate"
        if stage in ("受理公示", "拟批准公示"):
            return "normal"
        return "monitor"

    @staticmethod
    def _estimate_value(title: str, role: str) -> str:
        if "扩建" in title or "新建" in title:
            return "50-500万" if role in ("equipment_supplier", "env_engineer") else "10-100万"
        return "5-50万"

    @staticmethod
    def _assess_competitor_risk(title: str, profile: RoleProfile) -> str:
        for pattern in profile.competitor_patterns:
            if pattern in title:
                return "high"
        return "medium"

    @staticmethod
    def _analyze_competitors(opportunities: list[Opportunity], profile: RoleProfile) -> dict:
        companies = set()
        for opp in opportunities:
            m = re.search(r'(?:[\u4e00-\u9fff]{3,20})(?:有限|股份|集团|公司|厂)', opp.project_name)
            if m:
                companies.add(m.group())
        return {
            "active_companies": len(companies),
            "competitive_stages": sorted(set(o.stage for o in opportunities if o.competitor_risk == "high")),
        }

    @staticmethod
    def _generate_recommendations(report: OpportunityReport) -> list[str]:
        recs = []
        immediate = sum(1 for o in report.opportunities if o.urgency == "immediate")
        pending = sum(1 for o in report.opportunities if o.urgency == "monitor")

        if immediate > 0:
            recs.append(f"⚡ {immediate}个立即行动机会，建议本周内跟进")
        if pending > 0:
            recs.append(f"🔭 {pending}个潜在机会，建议每月跟踪一次")
        if "审批批复" in report.by_stage:
            recs.append(f"📋 {report.by_stage['审批批复']}个项目已批复，后续服务窗口期约2-4周")

        return recs

    @staticmethod
    def _format_report(report: OpportunityReport) -> str:
        lines = [
            f"# 💼 市场机会报告 — {report.role_name}",
            f"生成时间: {report.generated_at}",
            f"机会总数: {report.total_opportunities}",
            "",
        ]

        if report.by_stage:
            lines.append("## 按阶段分布")
            for stage, count in sorted(report.by_stage.items()):
                lines.append(f"- {stage}: {count}个机会")

        if report.opportunities:
            lines.append("\n## 机会详情")
            for i, opp in enumerate(report.opportunities[:15], 1):
                urgency_icon = {"immediate": "⚡", "normal": "📌", "monitor": "🔭"}.get(opp.urgency, "")
                lines.append(f"\n{i}. {urgency_icon} [{opp.stage}] {opp.project_name}")
                lines.append(f"   日期: {opp.date} | 紧急程度: {opp.urgency}")
                lines.append(f"   机会: {opp.opportunity_description}")
                if opp.action_items:
                    for action in opp.action_items[:3]:
                        lines.append(f"     → {action}")

        if report.recommendations:
            lines.append("\n## 行动建议")
            for rec in report.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)
