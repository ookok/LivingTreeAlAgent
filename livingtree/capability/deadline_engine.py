"""Regulatory Deadline Engine — auto-calculate obligations + smart reminders.

Every government announcement triggers a chain of regulatory deadlines.
Missing one can mean fines, re-approval, or project delays.

Core capability:
  Announcement → parse stage/date → query regulatory rulebook → calculate deadlines
  → schedule reminders at T-30d, T-7d, T-1d → auto-alert user

Regulatory knowledge base (built-in):
  环评批复  → 5年内开工, 否则重新报批
  验收公示  → 20个工作日内上传国家平台
  排污许可  → 到期前30天延续, 每年提交执行报告
  应急预案  → 3年修订一次, 演练每年一次
  在线监测  → 每季度比对, 每月至少一次校准
  危废管理  → 每年1月31日前申报管理计划, 季度申报转移联单
  自行监测  → 按排污许可证要求频次执行, 数据公开
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger


# ═══ Regulatory Rulebook ═══

@dataclass
class RegulatoryRule:
    """One regulatory obligation rule."""
    rule_id: str
    trigger_stage: str          # what announcement triggers this
    obligation: str             # what must be done
    deadline_days: int = 0      # days from trigger event
    deadline_desc: str = ""     # human-readable deadline rule
    law_ref: str = ""           # legal reference
    penalty: str = ""           # consequence of missing
    reminder_days_before: list[int] = field(default_factory=lambda: [30, 7, 1])


# ═══ Built-in Regulatory Knowledge ═══

REGULATORY_RULES = [
    RegulatoryRule(
        rule_id="eia_construction_start",
        trigger_stage="审批批复",
        obligation="项目开工建设（环评批复5年内有效）",
        deadline_days=365 * 5,
        deadline_desc="环评批复后5年内必须开工建设，否则需重新报批",
        law_ref="《环境影响评价法》第二十四条",
        penalty="重新报批环评，此前批复作废",
    ),
    RegulatoryRule(
        rule_id="acceptance_upload",
        trigger_stage="验收公示",
        obligation="上传验收报告至全国建设项目竣工环境保护验收信息平台",
        deadline_days=20,   # 20 working days ≈ 28 calendar days
        deadline_desc="验收公示结束后20个工作日内上传验收报告",
        law_ref="《建设项目竣工环境保护验收暂行办法》第十一条",
        penalty="逾期未上传视为未完成验收，责令整改",
    ),
    RegulatoryRule(
        rule_id="permit_renewal",
        trigger_stage="审批批复",
        obligation="排污许可证到期前申请延续",
        deadline_days=365 * 3 - 30,  # 3-year term, apply 30 days before
        deadline_desc="排污许可证有效期通常3年，到期前30天申请延续",
        law_ref="《排污许可管理条例》第十四条",
        penalty="无证排污处20万-100万罚款",
    ),
    RegulatoryRule(
        rule_id="permit_annual_report",
        trigger_stage="审批批复",
        obligation="提交排污许可证年度执行报告",
        deadline_days=365,
        deadline_desc="每年1月15日前提交上年度执行报告",
        law_ref="《排污许可管理条例》第二十二条",
        penalty="处2万-20万罚款",
    ),
    RegulatoryRule(
        rule_id="emergency_plan_revision",
        trigger_stage="审批批复",
        obligation="突发环境事件应急预案修订",
        deadline_days=365 * 3,
        deadline_desc="应急预案至少每3年修订一次，重大变化时及时修订",
        law_ref="《突发环境事件应急管理办法》第十四条",
        penalty="责令改正，处1万-3万罚款",
    ),
    RegulatoryRule(
        rule_id="emergency_drill",
        trigger_stage="审批批复",
        obligation="突发环境事件应急演练",
        deadline_days=365,
        deadline_desc="每年至少组织一次应急演练",
        law_ref="《突发环境事件应急管理办法》第十九条",
        penalty="责令改正",
    ),
    RegulatoryRule(
        rule_id="online_monitoring_calibration",
        trigger_stage="验收公示",
        obligation="在线监测设备定期校准",
        deadline_days=30,
        deadline_desc="在线监测设备至少每月校准一次",
        law_ref="《污染源自动监控管理办法》",
        penalty="监测数据无效，处2万-20万罚款",
    ),
    RegulatoryRule(
        rule_id="online_monitoring_comparison",
        trigger_stage="验收公示",
        obligation="在线监测设备比对监测",
        deadline_days=90,
        deadline_desc="每季度至少进行一次比对监测",
        law_ref="HJ 75-2017/HJ 76-2017",
        penalty="监测数据无效",
    ),
    RegulatoryRule(
        rule_id="hazardous_waste_plan",
        trigger_stage="审批批复",
        obligation="危险废物管理计划备案",
        deadline_days=365,  # annual recurrence
        deadline_desc="每年1月31日前完成当年危废管理计划备案",
        law_ref="《固体废物污染环境防治法》第七十八条",
        penalty="处10万-100万罚款",
    ),
    RegulatoryRule(
        rule_id="hazardous_waste_transfer",
        trigger_stage="审批批复",
        obligation="危险废物转移联单季度申报",
        deadline_days=90,
        deadline_desc="每季度申报危险废物转移联单",
        law_ref="《危险废物转移管理办法》",
        penalty="处10万-100万罚款",
    ),
    RegulatoryRule(
        rule_id="self_monitoring_disclosure",
        trigger_stage="审批批复",
        obligation="企业自行监测信息公开",
        deadline_days=30,
        deadline_desc="按排污许可证要求频次公开自行监测数据",
        law_ref="《排污许可管理条例》第二十三条",
        penalty="处2万-20万罚款, 责令公开",
    ),
    RegulatoryRule(
        rule_id="acceptance_report_prepare",
        trigger_stage="审批批复",
        obligation="编制竣工环境保护验收报告",
        deadline_days=90,  # 3 months after construction
        deadline_desc="项目建成后3个月内完成验收监测和报告编制",
        law_ref="《建设项目竣工环境保护验收暂行办法》第十二条",
        penalty="逾期未验收处20万-100万罚款, 责令停产",
    ),
]


# ═══ Deadline + Reminder ═══

@dataclass
class DeadlineItem:
    """A single regulatory deadline."""
    id: str
    project_name: str
    obligation: str
    due_date: str                  # YYYY-MM-DD
    days_remaining: int = 0
    urgency: str = "normal"        # "overdue", "critical", "warning", "normal"
    law_ref: str = ""
    penalty: str = ""
    trigger_announcement: str = ""
    trigger_date: str = ""
    status: str = "pending"        # "pending", "completed", "overdue"


@dataclass
class ReminderSchedule:
    """Complete reminder schedule for one project."""
    project_name: str
    trigger_stage: str
    trigger_date: str
    deadlines: list[DeadlineItem] = field(default_factory=list)
    next_reminder: Optional[DeadlineItem] = None


@dataclass
class DeadlineReport:
    """Complete deadline report for a user."""
    generated_at: str = ""
    total_deadlines: int = 0
    overdue: int = 0
    due_this_week: int = 0
    due_this_month: int = 0
    items: list[DeadlineItem] = field(default_factory=list)
    raw_text: str = ""


class DeadlineEngine:
    """Regulatory deadline calculator + smart reminder system.

    Usage:
        engine = DeadlineEngine()
        schedule = engine.calculate(
            project="亚威变压器扩建",
            stage="审批批复",
            stage_date="2026-04-28",
        )
        # → 12 deadlines calculated from regulatory rulebook
        # → next_reminder: "验收报告编制 — 2026-07-27 (90天后)"
    """

    def __init__(self):
        self._rules = {r.rule_id: r for r in REGULATORY_RULES}
        self._completed: set[str] = set()  # user-marked completed deadlines

    def calculate(
        self,
        project: str,
        stage: str,
        stage_date: str,
        existing_stages: list[tuple[str, str]] = None,
    ) -> ReminderSchedule:
        """Calculate all regulatory deadlines triggered by an announcement.

        Args:
            project: project name
            stage: announcement stage
            stage_date: date string (YYYY-MM-DD)
            existing_stages: other stages of the same project [(stage, date), ...]
        """
        trigger_date = self._parse_date(stage_date)
        if not trigger_date:
            return ReminderSchedule(project_name=project, trigger_stage=stage, trigger_date=stage_date)

        schedule = ReminderSchedule(project_name=project, trigger_stage=stage, trigger_date=stage_date)
        deadlines = []

        # Find all rules triggered by this stage (or any earlier stage)
        all_stages = existing_stages or []
        all_stages.append((stage, stage_date))

        for rule_stage, rule_date_str in all_stages:
            rule_date = self._parse_date(rule_date_str)
            if not rule_date:
                continue

            for rule in REGULATORY_RULES:
                if rule.trigger_stage == rule_stage:
                    due_date = rule_date + timedelta(days=rule.deadline_days)
                    days_remaining = (due_date - datetime.now()).days

                    deadline = DeadlineItem(
                        id=f"{project}_{rule.rule_id}",
                        project_name=project,
                        obligation=rule.obligation,
                        due_date=due_date.strftime("%Y-%m-%d"),
                        days_remaining=days_remaining,
                        urgency=self._urgency(days_remaining),
                        law_ref=rule.law_ref,
                        penalty=rule.penalty,
                        trigger_announcement=rule_stage,
                        trigger_date=rule_date_str,
                        status="overdue" if days_remaining < 0 else "pending",
                    )
                    deadlines.append(deadline)

        # Sort by days remaining (urgent first)
        deadlines.sort(key=lambda d: d.days_remaining if d.days_remaining > 0 else float('inf') * (-1))
        deadlines.sort(key=lambda d: 0 if d.status == "overdue" else 1)

        schedule.deadlines = deadlines

        if deadlines:
            schedule.next_reminder = deadlines[0]

        return schedule

    def calculate_batch(
        self,
        projects: list[tuple[str, str, str]],  # [(project, stage, date), ...]
    ) -> list[ReminderSchedule]:
        """Calculate deadlines for multiple projects."""
        return [self.calculate(p, s, d) for p, s, d in projects]

    def generate_report(
        self,
        schedules: list[ReminderSchedule],
        lookahead_days: int = 90,
    ) -> DeadlineReport:
        """Generate a deadline report with urgency classification."""
        report = DeadlineReport(generated_at=time.strftime("%Y-%m-%d %H:%M"))
        all_items = []

        for schedule in schedules:
            for item in schedule.deadlines:
                if item.days_remaining <= lookahead_days:
                    all_items.append(item)

        all_items.sort(key=lambda i: i.days_remaining if i.days_remaining > 0 else -999)

        report.total_deadlines = len(all_items)
        report.overdue = sum(1 for i in all_items if i.status == "overdue")
        report.due_this_week = sum(1 for i in all_items if 0 <= i.days_remaining <= 7)
        report.due_this_month = sum(1 for i in all_items if 8 <= i.days_remaining <= 30)
        report.items = all_items
        report.raw_text = self._format_report(report)

        return report

    def mark_completed(self, deadline_id: str) -> None:
        self._completed.add(deadline_id)

    def is_completed(self, deadline_id: str) -> bool:
        return deadline_id in self._completed

    def get_urgent(self, schedules: list[ReminderSchedule]) -> list[DeadlineItem]:
        """Get all items due within 7 days (including overdue)."""
        urgent = []
        for s in schedules:
            for d in s.deadlines:
                if d.days_remaining <= 7 and not self.is_completed(d.id):
                    urgent.append(d)
        urgent.sort(key=lambda d: d.days_remaining if d.days_remaining > 0 else -1)
        return urgent

    # ═══ Helpers ═══

    @staticmethod
    def _urgency(days: int) -> str:
        if days < 0:
            return "overdue"
        if days <= 3:
            return "critical"
        if days <= 7:
            return "warning"
        return "normal"

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m", "%Y"]:
            try:
                return datetime.strptime(date_str[:10], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _format_report(report: DeadlineReport) -> str:
        urgency_icons = {
            "overdue": "🔴", "critical": "🟠", "warning": "🟡", "normal": "🟢",
        }

        lines = [
            "## ⏰ 法规期限提醒报告",
            f"生成时间: {report.generated_at}",
            f"总期限: {report.total_deadlines} | 🔴逾期: {report.overdue} | 🟠本周: {report.due_this_week} | 🟡本月: {report.due_this_month}",
            "",
        ]

        if report.overdue > 0:
            lines.append("### 🔴 已逾期（立即处理）")
            for item in [i for i in report.items if i.status == "overdue"]:
                lines.append(f"- **{item.project_name}**: {item.obligation}")
                lines.append(f"  截止: {item.due_date} (逾期{abs(item.days_remaining)}天) | {item.penalty}")

        due_week = [i for i in report.items if 0 <= i.days_remaining <= 7]
        if due_week:
            lines.append("\n### 🟠 本周截止")
            for item in due_week:
                lines.append(f"- {item.project_name}: {item.obligation} | {item.days_remaining}天后")
                if item.law_ref:
                    lines.append(f"  依据: {item.law_ref}")

        due_month = [i for i in report.items if 8 <= i.days_remaining <= 30]
        if due_month:
            lines.append("\n### 🟡 本月截止")
            for item in due_month[:10]:
                lines.append(f"- {item.project_name}: {item.obligation} | {item.days_remaining}天后")

        later = [i for i in report.items if 30 < i.days_remaining <= 90]
        if later:
            lines.append("\n### 🟢 近期关注")
            for item in later[:5]:
                lines.append(f"- {item.project_name}: {item.obligation} | {item.due_date}")

        return "\n".join(lines)


# ═══ Quick Test ═══

if __name__ == "__main__":
    engine = DeadlineEngine()

    schedule = engine.calculate(
        project="亚威变压器扩建",
        stage="审批批复",
        stage_date="2026-04-28",
        existing_stages=[("受理公示", "2026-04-01")],
    )

    print(f"\n项目: {schedule.project_name}")
    print(f"触发: {schedule.trigger_stage} ({schedule.trigger_date})")
    print(f"总期限: {len(schedule.deadlines)}")
    print(f"\n截止日期列表:")
    for d in schedule.deadlines[:8]:
        icon = {"overdue": "🔴", "critical": "🟠", "warning": "🟡", "normal": "🟢"}.get(d.urgency, "")
        print(f"  {icon} {d.due_date} ({d.days_remaining:+d}d) : {d.obligation}")
        status = " [已完成]" if engine.is_completed(d.id) else ""
        print(f"     {d.law_ref}{status}")


# ═══ Dynamic Rulebook — external config + law update detection + versioning ═══

import json as _json
import os as _os

RULEBOOK_PATH = _os.path.expanduser("~/.livingtree/rulebook.json")

class DynamicRulebook:
    """External regulatory rulebook with auto-update support.

    Rules are stored in ~/.livingtree/rulebook.json and can be:
      - Manually edited by the user
      - Auto-discovered from government announcements about law changes
      - Versioned so changes can be tracked and audited

    Usage:
        book = DynamicRulebook()
        book.load()  # loads from disk
        book.add_custom_rule(...)  # add user-defined rule
        await book.scan_for_updates(forager)  # detect law changes from announcements
        book.save()  # persist
    """

    def __init__(self, path: str = ""):
        self._path = path or RULEBOOK_PATH
        self._rules: dict[str, RegulatoryRule] = {}
        self._version: int = 1
        self._change_log: list[dict] = []
        self._load_builtin()

    def _load_builtin(self) -> None:
        for rule in REGULATORY_RULES:
            self._rules[rule.rule_id] = rule

    def load(self) -> dict[str, RegulatoryRule]:
        try:
            if _os.path.exists(self._path):
                with open(self._path, encoding="utf-8") as f:
                    data = _json.load(f)
                self._version = data.get("version", 1)
                loaded = data.get("rules", {})
                for rid, rdata in loaded.items():
                    if rid not in self._rules:  # Don't override built-in, add as custom
                        self._rules[rid] = RegulatoryRule(
                            rule_id=rid,
                            trigger_stage=rdata.get("trigger_stage", ""),
                            obligation=rdata.get("obligation", ""),
                            deadline_days=rdata.get("deadline_days", 0),
                            deadline_desc=rdata.get("deadline_desc", ""),
                            law_ref=rdata.get("law_ref", ""),
                            penalty=rdata.get("penalty", ""),
                            reminder_days_before=rdata.get("reminder_days_before", [30, 7, 1]),
                        )
                logger.info("Rulebook loaded v%d: %d built-in + %d custom rules",
                           self._version, len(REGULATORY_RULES), len(loaded))
        except Exception as e:
            logger.warning("Rulebook load failed: %s (using built-in)", e)
        return self._rules

    def save(self) -> None:
        _os.makedirs(_os.path.dirname(self._path), exist_ok=True)
        data = {
            "version": self._version,
            "updated_at": time.strftime("%Y-%m-%d %H:%M"),
            "rules": {
                rid: {
                    "trigger_stage": r.trigger_stage,
                    "obligation": r.obligation,
                    "deadline_days": r.deadline_days,
                    "deadline_desc": r.deadline_desc,
                    "law_ref": r.law_ref,
                    "penalty": r.penalty,
                    "reminder_days_before": r.reminder_days_before,
                }
                for rid, r in self._rules.items()
                if rid not in REGULATORY_RULES or r != REGULATORY_RULES.get(rid)
            },
        }
        with open(self._path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)

    def add_custom_rule(self, rule: RegulatoryRule) -> None:
        self._rules[rule.rule_id] = rule
        self._change_log.append({
            "action": "add", "rule_id": rule.rule_id,
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        logger.info("Rulebook: added custom rule '%s'", rule.rule_id)

    def update_rule(self, rule_id: str, **updates) -> bool:
        if rule_id not in self._rules:
            return False
        rule = self._rules[rule_id]
        for key, val in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, val)
        self._version += 1
        self._change_log.append({
            "action": "update", "rule_id": rule_id,
            "updates": {k: v for k, v in updates.items() if k != "penalty"},
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        logger.info("Rulebook: updated rule '%s' (v%d)", rule_id, self._version)
        return True

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        self._change_log.append({
            "action": "delete", "rule_id": rule_id,
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        return True

    async def scan_for_law_updates(self, forager) -> int:
        """Scan for announcements about regulatory changes.

        Searches for: '标准 修订', '法规 更新', '条例 修改', 'GB 发布'
        and prompts user to review if found.
        """
        found = 0
        queries = [
            "环境影响评价 标准 修订",
            "排污许可 条例 修改",
            "固体废物 法规 更新",
            "环境监测 标准 发布",
            "应急预案 管理办法 修订",
        ]
        for query in queries[:3]:
            result = await forager.hunt(query)
            if result.get("found", 0) > 0:
                found += result["found"]

        if found > 0:
            logger.info("Rulebook: detected %d potential law updates — review needed", found)

        return found

    def get_active_rules(self) -> dict[str, RegulatoryRule]:
        return dict(self._rules)

    def get_stats(self) -> dict:
        return {
            "version": self._version,
            "total_rules": len(self._rules),
            "builtin_rules": len(REGULATORY_RULES),
            "custom_rules": len(self._rules) - len(REGULATORY_RULES),
            "changes": len(self._change_log),
        }


# ═══ Task Scheduler — subscription + background reminders ═══

@dataclass
class Subscription:
    """A user's subscription to project deadline tracking."""
    sub_id: str
    project_name: str
    trigger_stage: str
    trigger_date: str
    notification_channel: str = "console"  # "console", "email", "webhook"
    notify_days_before: list[int] = field(default_factory=lambda: [7, 3, 1])
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_notified: dict[str, float] = field(default_factory=dict)  # deadline_id → timestamp


class TaskScheduler:
    """Background task scheduler for regulatory reminders.

    Usage:
        scheduler = TaskScheduler(engine)
        scheduler.subscribe("亚威变压器", "审批批复", "2026-04-28")
        await scheduler.check_and_notify()  # check all subscriptions
        scheduler.start_background(interval_hours=24)  # auto-check daily
    """

    def __init__(self, deadline_engine: DeadlineEngine):
        self._engine = deadline_engine
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = _threading.RLock()
        self._bg_thread: Optional[_threading.Thread] = None

    def subscribe(
        self,
        project: str,
        stage: str,
        stage_date: str,
        channel: str = "console",
        notify_days: list[int] = None,
    ) -> Subscription:
        sub_id = f"{project[:30]}_{stage}_{stage_date}"
        sub = Subscription(
            sub_id=sub_id,
            project_name=project,
            trigger_stage=stage,
            trigger_date=stage_date,
            notification_channel=channel,
            notify_days_before=notify_days or [7, 3, 1],
        )
        with self._lock:
            self._subscriptions[sub_id] = sub
        logger.info("Scheduler: subscribed to '%s' (remind %d days before)", project, sub.notify_days_before[0])
        return sub

    def unsubscribe(self, sub_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(sub_id, None)

    async def check_and_notify(self) -> list[str]:
        """Check all subscriptions and send due reminders."""
        notifications = []
        with self._lock:
            subs = list(self._subscriptions.values())

        for sub in subs:
            if not sub.enabled:
                continue

            schedule = self._engine.calculate(
                sub.project_name, sub.trigger_stage, sub.trigger_date,
            )

            for deadline in schedule.deadlines:
                if self._engine.is_completed(deadline.id):
                    continue

                # Check if any reminder day is hit
                for reminder_day in sub.notify_days_before:
                    if 0 <= deadline.days_remaining <= reminder_day:
                        last = sub.last_notified.get(deadline.id, 0)
                        if time.time() - last > 86400:  # Don't re-notify within 24h
                            msg = self._format_notification(deadline, sub)
                            await self._send_notification(msg, sub.notification_channel)
                            sub.last_notified[deadline.id] = time.time()
                            notifications.append(msg)

        return notifications

    def start_background(self, interval_hours: float = 24) -> None:
        if self._bg_thread and self._bg_thread.is_alive():
            return
        self._bg_thread = threading.Thread(
            target=self._bg_loop, args=(interval_hours,), daemon=True,
            name="task-scheduler",
        )
        self._bg_thread.start()
        logger.info("Scheduler: background started (interval=%dh)", interval_hours)

    def stop_background(self) -> None:
        self._bg_thread = None

    def _bg_loop(self, interval_hours: float) -> None:
        import asyncio as _aio
        loop = _aio.new_event_loop()
        while self._bg_thread:
            try:
                loop.run_until_complete(self.check_and_notify())
            except Exception as e:
                logger.error("Scheduler background error: %s", e)
            time.sleep(interval_hours * 3600)

    @staticmethod
    def _format_notification(deadline: DeadlineItem, sub: Subscription) -> str:
        icon = {"overdue": "🔴", "critical": "🟠", "warning": "🟡", "normal": "🟢"}.get(deadline.urgency, "")
        return (
            f"{icon} [期限提醒] {sub.project_name}\n"
            f"  事项: {deadline.obligation}\n"
            f"  截止: {deadline.due_date} (剩余{deadline.days_remaining}天)\n"
            f"  依据: {deadline.law_ref}\n"
            f"  逾期后果: {deadline.penalty}"
        )

    async def _send_notification(self, msg: str, channel: str) -> None:
        if channel == "console":
            print(msg)
        elif channel == "log":
            logger.warning(msg)
        elif channel == "webhook":
            webhook_url = _os.environ.get("LIVINGTREE_WEBHOOK_URL", "")
            if webhook_url:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as s:
                        await s.post(webhook_url, json={"text": msg})
                except Exception:
                    pass

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "subscriptions": len(self._subscriptions),
                "active": sum(1 for s in self._subscriptions.values() if s.enabled),
                "projects": list(set(s.project_name for s in self._subscriptions.values())),
            }


import threading as _threading

