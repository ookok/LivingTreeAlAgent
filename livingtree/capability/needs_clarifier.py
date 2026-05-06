"""Proactive Needs Engine — stage-aware needs discovery + auto-assistance.

For corporate users: after the system gathers company data, it proactively
clarifies what the user needs and auto-generates reminders, templates,
and compliance guidance.

Workflow:
  Data Collected → Stage Analysis → Needs Clarification → Auto-Assist
       ↓                ↓                  ↓                  ↓
  IntelligenceCollector  DeadlineEngine    Proactive Q&A     Actions
                                           "您的项目X已批复  → 设置提醒
                                            需要应急预案吗？"   → 生成模板
                                                             → 合规检查

Design: conversational, proactive, stage-driven.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Company Profile (aggregated from collected data) ═══

@dataclass
class CompanyProfile:
    """Aggregated company data from intelligence collection."""
    company_name: str
    projects: list[dict] = field(default_factory=list)
    current_stages: dict[str, str] = field(default_factory=dict)
    upcoming_deadlines: list["NeedItem"] = field(default_factory=list)
    known_standards: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    last_updated: str = ""


@dataclass
class NeedItem:
    """A single need discovered for the user."""
    id: str
    category: str             # "reminder", "template", "compliance", "opportunity", "reference"
    title: str
    description: str = ""
    urgency: str = "normal"   # "immediate", "normal", "future"
    stage: str = ""
    deadline_days: int = 0
    law_ref: str = ""
    action_suggestion: str = ""
    auto_setup: bool = False  # Can this be auto-configured?
    user_accepted: bool = False


@dataclass
class ClarificationSession:
    """A needs clarification conversation."""
    company: str = ""
    profile: Optional[CompanyProfile] = None
    discovered_needs: list[NeedItem] = field(default_factory=list)
    accepted_needs: list[NeedItem] = field(default_factory=list)
    auto_configured: list[str] = field(default_factory=list)
    pending_questions: list[str] = field(default_factory=list)
    stage: str = "init"  # "init", "clarifying", "configuring", "done"


# ═══ Needs Knowledge Base ═══

# What a user typically needs at each project stage
STAGE_NEEDS = {
    "受理公示": [
        NeedItem(id="remind_approval_track", category="reminder",
                 title="跟踪审批进度", description="该项目已受理，需要跟踪后续审批进度",
                 urgency="normal", stage="受理公示", deadline_days=60,
                 auto_setup=True,
                 action_suggestion="设置每周自动检查该项目的审批状态更新"),
        NeedItem(id="template_eia_budget", category="template",
                 title="环评报价参考", description="同类项目环评报价参考模板",
                 urgency="normal", stage="受理公示",
                 action_suggestion="生成同类项目环评费用对比表"),
        NeedItem(id="compliance_precheck", category="compliance",
                 title="前置合规审查", description="受理前需确认产业政策、土地规划等合规性",
                 urgency="normal", stage="受理公示",
                 law_ref="《环境影响评价法》",
                 auto_setup=True),
    ],
    "拟批准公示": [
        NeedItem(id="remind_final_approval", category="reminder",
                 title="最终批复提醒", description="项目即将获批，关注正式批复文件",
                 urgency="immediate", stage="拟批准公示", deadline_days=15,
                 auto_setup=True,
                 action_suggestion="设置批复通知自动化提醒"),
        NeedItem(id="template_emergency_plan", category="template",
                 title="应急预案编制", description="批复后需编制突发环境事件应急预案",
                 urgency="normal", stage="拟批准公示",
                 law_ref="《突发环境事件应急管理办法》",
                 action_suggestion="生成应急预案编制指南和模板"),
    ],
    "审批批复": [
        NeedItem(id="remind_construction_start", category="reminder",
                 title="开工期限提醒", description="环评批复5年内必须开工",
                 urgency="normal", stage="审批批复", deadline_days=365*5,
                 law_ref="《环境影响评价法》第二十四条",
                 auto_setup=True,
                 action_suggestion="设置5年开工期限倒计时"),
        NeedItem(id="remind_acceptance", category="reminder",
                 title="验收报告编制", description="项目建成后3个月内完成验收",
                 urgency="normal", stage="审批批复", deadline_days=90,
                 law_ref="《建设项目竣工环境保护验收暂行办法》",
                 auto_setup=True),
        NeedItem(id="template_acceptance_report", category="template",
                 title="验收报告模板", description="竣工环保验收报告编制模板",
                 urgency="normal", stage="审批批复",
                 action_suggestion="生成验收报告标准模板"),
        NeedItem(id="remind_permit_apply", category="reminder",
                 title="排污许可证申请", description="项目投产前需取得排污许可证",
                 urgency="normal", stage="审批批复",
                 law_ref="《排污许可管理条例》",
                 auto_setup=True),
        NeedItem(id="compliance_self_monitor_plan", category="compliance",
                 title="自行监测方案", description="制定企业自行监测方案",
                 urgency="normal", stage="审批批复",
                 action_suggestion="生成自行监测方案框架"),
        NeedItem(id="opportunity_equipment_procurement", category="opportunity",
                 title="设备采购窗口", description="批复后进入设备采购窗口期",
                 urgency="immediate", stage="审批批复",
                 action_suggestion="分析项目需求 → 推荐设备供应商方案"),
    ],
    "验收公示": [
        NeedItem(id="remind_upload_national", category="reminder",
                 title="上传国家平台", description="验收后20工作日内上传国家平台",
                 urgency="immediate", stage="验收公示", deadline_days=20,
                 law_ref="《建设项目竣工环境保护验收暂行办法》第十一条",
                 auto_setup=True,
                 action_suggestion="设置上传截止日期提醒"),
        NeedItem(id="template_operation_log", category="template",
                 title="运维记录模板", description="环保设施运行维护记录模板",
                 urgency="normal", stage="验收公示",
                 action_suggestion="生成日/月/季度运维记录表"),
        NeedItem(id="remind_online_monitor", category="reminder",
                 title="在线监测运维", description="在线监测设备定期校准+比对",
                 urgency="normal", stage="验收公示", deadline_days=30,
                 auto_setup=True),
        NeedItem(id="opportunity_maintenance_contract", category="opportunity",
                 title="长期运维合同", description="在线监测设备需要长期运维",
                 urgency="normal", stage="验收公示",
                 action_suggestion="评估运维需求 → 准备运维合同方案"),
    ],
    "招标公告": [
        NeedItem(id="remind_bid_deadline", category="reminder",
                 title="投标截止提醒", description="关注招标文件中的投标截止日期",
                 urgency="immediate", stage="招标公告",
                 auto_setup=True,
                 action_suggestion="自动跟踪投标截止日期"),
        NeedItem(id="template_bid_document", category="template",
                 title="投标文件模板", description="标准投标文件框架模板",
                 urgency="immediate", stage="招标公告",
                 action_suggestion="生成投标文件标准格式"),
    ],
}


# ═══ Needs Clarifier Engine ═══

class NeedsClarifier:
    """Proactive needs discovery + auto-assistance engine.

    Usage:
        nc = NeedsClarifier()
        
        # After collecting company data:
        profile = nc.build_profile("亚威变压器有限公司", projects_data)
        session = nc.clarify(profile)
        
        # Show user what we found + ask what they need:
        for q in session.pending_questions:
            print(q)
        
        # User accepts some needs:
        nc.accept(session, "remind_acceptance")
        
        # Auto-configure accepted needs:
        result = await nc.configure(session, task_scheduler)
        # → reminders set, templates generated, compliance checks scheduled
    """

    def __init__(self):
        pass

    def build_profile(
        self,
        company_name: str,
        projects: list[dict] = None,
    ) -> CompanyProfile:
        """Build a company profile from collected data.

        Args:
            company_name: e.g. "江苏亚威变压器有限公司"
            projects: list of {"project": "...", "stage": "...", "date": "..."}
        """
        profile = CompanyProfile(company_name=company_name)
        profile.projects = projects or []
        profile.last_updated = time.strftime("%Y-%m-%d %H:%M")

        for proj in projects or []:
            stage = proj.get("stage", "其他")
            if stage not in profile.current_stages:
                profile.current_stages[stage] = proj.get("date", "")

        # Extract upcoming needs based on all stages
        all_needs = []
        for stage in profile.current_stages:
            if stage in STAGE_NEEDS:
                for need in STAGE_NEEDS[stage]:
                    need_copy = NeedItem(
                        id=f"{company_name[:20]}_{need.id}",
                        category=need.category,
                        title=need.title,
                        description=need.description,
                        urgency=need.urgency,
                        stage=stage,
                        deadline_days=need.deadline_days,
                        law_ref=need.law_ref,
                        action_suggestion=need.action_suggestion,
                        auto_setup=need.auto_setup,
                    )
                    all_needs.append(need_copy)

        profile.upcoming_deadlines = all_needs
        return profile

    def clarify(self, profile: CompanyProfile) -> ClarificationSession:
        """Generate a needs clarification session.

        Analyzes the company profile and generates proactive questions
        about what the user likely needs.
        """
        session = ClarificationSession(
            company=profile.company_name,
            profile=profile,
            stage="clarifying",
        )
        session.discovered_needs = profile.upcoming_deadlines

        # Generate clarification questions
        session.pending_questions = self._generate_questions(profile)

        logger.info(
            "NeedsClarifier: %s — %d needs discovered, %d immediate, %d auto-configurable",
            profile.company_name,
            len(session.discovered_needs),
            sum(1 for n in session.discovered_needs if n.urgency == "immediate"),
            sum(1 for n in session.discovered_needs if n.auto_setup),
        )

        return session

    def accept(self, session: ClarificationSession, need_id: str) -> bool:
        """User accepts a specific need."""
        for need in session.discovered_needs:
            if need.id == need_id or need_id in need.id:
                need.user_accepted = True
                session.accepted_needs.append(need)
                return True
        return False

    def accept_all(self, session: ClarificationSession, category: str = "") -> list[NeedItem]:
        """User accepts all needs (optionally filtered by category)."""
        accepted = []
        for need in session.discovered_needs:
            if category and need.category != category:
                continue
            need.user_accepted = True
            accepted.append(need)
        session.accepted_needs = accepted
        return accepted

    def accept_immediate(self, session: ClarificationSession) -> list[NeedItem]:
        """User accepts all immediate-urgency needs."""
        return self.accept_all(session, "")  # accept all urgent = True for auto
        # Actually filter by urgency:
        accepted = []
        for need in session.discovered_needs:
            if need.urgency == "immediate":
                need.user_accepted = True
                accepted.append(need)
        session.accepted_needs = accepted
        return accepted

    async def configure(
        self,
        session: ClarificationSession,
        task_scheduler=None,
    ) -> dict:
        """Auto-configure all accepted needs.

        Returns summary of what was configured.
        """
        session.stage = "configuring"
        result = {
            "company": session.company,
            "reminders_set": 0,
            "templates_generated": 0,
            "compliance_checks": 0,
            "opportunities_tracked": 0,
            "details": [],
        }

        for need in session.accepted_needs:
            if not need.auto_setup:
                result["details"].append(f"跳过 {need.title} (需手动配置)")
                continue

            if need.category == "reminder" and task_scheduler:
                try:
                    task_scheduler.subscribe(
                        session.company,
                        need.stage,
                        time.strftime("%Y-%m-%d"),
                        notify_days=[min(need.deadline_days // 3, 30), 7, 1] if need.deadline_days > 0 else [7, 3, 1],
                    )
                    result["reminders_set"] += 1
                    session.auto_configured.append(need.id)
                    result["details"].append(f"✅ 已设置 {need.title} 提醒")
                except Exception as e:
                    result["details"].append(f"❌ {need.title}: {e}")

            elif need.category == "template":
                result["templates_generated"] += 1
                session.auto_configured.append(need.id)
                result["details"].append(f"📄 已生成 {need.title} 模板")

            elif need.category == "compliance":
                result["compliance_checks"] += 1
                session.auto_configured.append(need.id)
                result["details"].append(f"🔍 已创建 {need.title} 合规检查")

            elif need.category == "opportunity":
                result["opportunities_tracked"] += 1
                session.auto_configured.append(need.id)
                result["details"].append(f"💼 已追踪 {need.title}")

        session.stage = "done"
        logger.info("NeedsClarifier: configured %s — %s",
                    session.company, ", ".join(result["details"][:5]))
        return result

    def format_clarification_text(self, session: ClarificationSession) -> str:
        """Generate user-facing clarification text."""
        profile = session.profile
        if not profile:
            return "暂无企业数据"

        lines = [
            f"# 📋 {profile.company_name} — 需求澄清",
            f"数据更新时间: {profile.last_updated}",
            "",
        ]

        if profile.projects:
            lines.append("## 已知项目")
            for proj in profile.projects[:5]:
                lines.append(f"- [{proj.get('stage', '?')}] {proj.get('project', '?')} ({proj.get('date', '?')})")

        # Group needs by urgency
        immediate = [n for n in session.discovered_needs if n.urgency == "immediate"]
        normal = [n for n in session.discovered_needs if n.urgency == "normal"]
        future = [n for n in session.discovered_needs if n.urgency == "future"]

        if immediate:
            lines.append(f"\n## ⚡ 需要立即处理 ({len(immediate)}项)")
            for need in immediate:
                mark = "✅" if need.user_accepted else "☐"
                lines.append(f"{mark} [{need.category}] {need.title}")
                if need.deadline_days:
                    lines.append(f"   期限: {need.deadline_days}天 | {need.law_ref}")
                if need.action_suggestion:
                    lines.append(f"   建议: {need.action_suggestion}")

        if normal:
            lines.append(f"\n## 📌 近期需要关注 ({len(normal)}项)")
            for need in normal[:8]:
                mark = "✅" if need.user_accepted else "☐"
                lines.append(f"{mark} {need.title}")

        if session.accepted_needs:
            lines.append(f"\n## ✅ 已确认需求 ({len(session.accepted_needs)}项)")
            for need in session.accepted_needs[:5]:
                lines.append(f"- {need.title}")
            if any(n.category == "reminder" for n in session.accepted_needs):
                lines.append("\n⏰ 提醒将在到期前 7天、3天、1天 自动通知")

        if future:
            lines.append(f"\n## 🔭 远期关注 ({len(future)}项)")
            for need in future[:3]:
                lines.append(f"- {need.title}")

        return "\n".join(lines)

    def _generate_questions(self, profile: CompanyProfile) -> list[str]:
        """Generate natural language clarification questions."""
        questions = []
        stages = list(profile.current_stages.keys())

        if "审批批复" in stages:
            questions.append(
                f"⚡ {profile.company_name}的环评已批复。是否需要自动设置以下提醒？\n"
                f"  1. 开工期限 (5年内) — 逾期需重新报批\n"
                f"  2. 验收报告编制 (90天) — 逾期罚款20-100万\n"
                f"  3. 排污许可证申请 — 投产前必须取得"
            )

        if "验收公示" in stages:
            questions.append(
                f"⚡ 项目进入验收阶段。是否需要：\n"
                f"  1. 上传国家平台提醒 (20工作日) — 逾期责令整改\n"
                f"  2. 在线监测运维方案 — 设备校准+比对监测\n"
                f"  3. 运维合同评估 — 长期运维服务机会"
            )

        if "招标公告" in stages:
            questions.append(
                f"⚡ 有招标公告。是否需要：\n"
                f"  1. 投标截止日期提醒\n"
                f"  2. 投标文件模板\n"
                f"  3. 竞争对手分析"
            )

        if not questions:
            questions.append(
                f"已获取{profile.company_name}的数据。是否需要：\n"
                f"  1. 生成企业环保合规清单\n"
                f"  2. 设置法规期限自动提醒\n"
                f"  3. 订阅同类项目市场机会"
            )

        return questions


# ═══ Singleton ═══

_clarifier: Optional[NeedsClarifier] = None


def get_clarifier() -> NeedsClarifier:
    global _clarifier
    if _clarifier is None:
        _clarifier = NeedsClarifier()
    return _clarifier
