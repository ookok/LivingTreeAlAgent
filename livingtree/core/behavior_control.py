"""Behavior Control Engine — from "prayer-based prompting" to engineered control.

Inspired by Parlant's structured behavior modeling:
- Guidelines: condition→action→tools atomic rules (hard enforcement, not prompt-based)
- Journeys: enforced sequential workflows for critical business scenarios
- ARQ-style: Guide→Respond→Verify structured reasoning pipeline
- 3-layer anti-runaway: rule filter → framework enforcement → state management

Integrates with existing: safety.py, behavior_tree.py, tool_router.py, model_spec.py.
"""

from __future__ import annotations

import json as _json
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


CTRL_DIR = Path(".livingtree/behavior_control")
CTRL_DIR.mkdir(parents=True, exist_ok=True)
GUIDELINES_FILE = CTRL_DIR / "guidelines.json"
JOURNEYS_FILE = CTRL_DIR / "journeys.json"


# ═══ 1. Guidelines: condition → action → tools atomic rules ═══

class RuleAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REDIRECT = "redirect"
    REQUIRE_APPROVAL = "require_approval"
    MODIFY = "modify"
    LOG = "log"


@dataclass
class Guideline:
    """Atomic behavioral rule: WHEN condition THEN action WITH tools.

    Unlike prompt-based constraints (soft), these are HARD enforced at the
    framework level — the LLM output is filtered/modified before reaching the user.
    """
    rule_id: str
    name: str
    condition: str           # Natural language condition matcher
    action: RuleAction
    tools: list[str] = field(default_factory=list)   # Tools to invoke
    redirect_message: str = ""  # For REDIRECT action
    priority: int = 5        # 1=critical, 10=low
    enabled: bool = True
    hit_count: int = 0

    def matches(self, user_input: str, llm_output: str = "") -> bool:
        """Check if this guideline's condition is triggered."""
        combined = f"{user_input} {llm_output}".lower()
        conditions = self.condition.lower().split(" OR ")
        return any(c.strip() in combined for c in conditions)

    def to_dict(self) -> dict:
        return {
            "id": self.rule_id, "name": self.name, "condition": self.condition,
            "action": self.action.value, "tools": self.tools,
            "priority": self.priority, "enabled": self.enabled,
            "redirect": self.redirect_message, "hits": self.hit_count,
        }


# Pre-built critical guidelines (like Parlant's financial/medical compliance rules)
DEFAULT_GUIDELINES = [
    Guideline(
        rule_id="g001", name="拒绝有害请求",
        condition="hack OR 攻击 OR exploit OR malware OR 病毒 OR 入侵",
        action=RuleAction.BLOCK, priority=1,
        redirect_message="抱歉，我不能协助可能造成伤害的操作。",
    ),
    Guideline(
        rule_id="g002", name="隐私保护",
        condition="password OR 密码 OR credit card OR 信用卡 OR SSN OR 身份证号",
        action=RuleAction.BLOCK, priority=1,
        redirect_message="出于隐私保护，我不能处理敏感个人信息。",
    ),
    Guideline(
        rule_id="g003", name="医疗免责",
        condition="diagnose OR 诊断 OR prescribe OR 开药 OR treatment plan",
        action=RuleAction.REDIRECT, priority=2,
        redirect_message="我AI不能提供医疗诊断。建议咨询专业医生。如果你需要健康信息整理，我可以帮忙。",
    ),
    Guideline(
        rule_id="g004", name="金融合规",
        condition="invest OR 投资建议 OR stock pick OR 荐股 OR financial advice",
        action=RuleAction.REDIRECT, priority=2,
        redirect_message="我不能提供具体的投资建议。我可以帮你整理公开的财务数据和市场信息。",
    ),
    Guideline(
        rule_id="g005", name="法律咨询重定向",
        condition="sue OR 起诉 OR legal advice OR 法律意见 OR 官司",
        action=RuleAction.REDIRECT, priority=3,
        redirect_message="我不能提供法律意见。建议咨询持牌律师。我可以帮你整理相关法规条文。",
    ),
    Guideline(
        rule_id="g006", name="内容合规检查",
        condition="adult OR 成人 OR explicit OR 色情 OR violence OR 暴力",
        action=RuleAction.BLOCK, priority=1,
    ),
    Guideline(
        rule_id="g007", name="自复制防护",
        condition="self.replicate OR 复制自身 OR spawn unlimited OR 无限生成",
        action=RuleAction.BLOCK, priority=1,
        redirect_message="我不能自我复制或创建不受控的代理实例。",
    ),
    Guideline(
        rule_id="g008", name="系统命令审批",
        condition="rm -rf OR format OR del /f OR shutdown OR 格式化",
        action=RuleAction.REQUIRE_APPROVAL, priority=2, tools=["safety_gate"],
    ),
]


class GuidelineEngine:
    """Hard-constraint behavioral rule engine. Not prompt-based — framework enforcement."""

    def __init__(self):
        self._guidelines: dict[str, Guideline] = {}
        self._load()

    def _load(self):
        if GUIDELINES_FILE.exists():
            try:
                data = _json.loads(GUIDELINES_FILE.read_text())
                for item in data:
                    g = Guideline(**item)
                    g.action = RuleAction(g.action) if isinstance(g.action, str) else g.action
                    self._guidelines[g.rule_id] = g
            except Exception:
                pass
        if not self._guidelines:
            for g in DEFAULT_GUIDELINES:
                self._guidelines[g.rule_id] = g
            self._save()

    def _save(self):
        GUIDELINES_FILE.write_text(_json.dumps(
            [g.to_dict() for g in self._guidelines.values()],
            ensure_ascii=False, indent=2,
        ))

    def enforce(self, user_input: str, llm_output: str = "") -> dict:
        """Enforce all matching guidelines. Returns action + modified output."""
        matched = []
        for g in sorted(self._guidelines.values(), key=lambda x: x.priority):
            if g.enabled and g.matches(user_input, llm_output):
                g.hit_count += 1
                matched.append(g)

        if not matched:
            return {"action": "allow", "modified_output": llm_output, "matched": []}

        highest = matched[0]  # Lowest priority number = highest priority
        result = {
            "action": highest.action.value,
            "modified_output": llm_output,
            "matched": [g.to_dict() for g in matched],
            "rule_name": highest.name,
        }

        if highest.action == RuleAction.BLOCK:
            result["modified_output"] = highest.redirect_message or "此请求已被安全策略拦截。"
        elif highest.action == RuleAction.REDIRECT:
            prefix = highest.redirect_message or "我建议从以下角度考虑:"
            result["modified_output"] = f"{prefix}\n\n{llm_output}" if llm_output else prefix
        elif highest.action == RuleAction.REQUIRE_APPROVAL:
            result["require_approval"] = True
            result["approval_question"] = f"规则 '{highest.name}' 触发。是否继续?"

        logger.info(f"Guideline enforced: {highest.name} ({highest.action.value})")
        return result

    def add_guideline(self, g: Guideline):
        self._guidelines[g.rule_id] = g
        self._save()

    def remove(self, rule_id: str):
        self._guidelines.pop(rule_id, None)
        self._save()

    def stats(self) -> dict:
        return {
            "total_rules": len(self._guidelines),
            "enabled": sum(1 for g in self._guidelines.values() if g.enabled),
            "top_hits": sorted(
                [{"name": g.name, "hits": g.hit_count} for g in self._guidelines.values()],
                key=lambda x: -x["hits"],
            )[:5],
        }


# ═══ 2. Journeys: enforced multi-step workflows ═══

@dataclass
class JourneyStep:
    step_id: str
    name: str
    description: str
    required: bool = True
    tool: str = ""           # Tool that must be called
    validation: str = ""     # Validation condition
    timeout_seconds: float = 60.0


@dataclass
class Journey:
    """Enforced sequential workflow. Like Parlant's Journeys for business processes."""
    journey_id: str
    name: str
    description: str
    steps: list[JourneyStep] = field(default_factory=list)
    on_violation: str = "restart"  # restart, skip, abort

    def validate_step(self, step_index: int, completed_steps: list[dict]) -> bool:
        """Check if previous steps were completed before allowing next."""
        for i in range(step_index):
            if self.steps[i].required:
                found = any(s.get("step_id") == self.steps[i].step_id and s.get("status") == "done"
                            for s in completed_steps)
                if not found:
                    return False
        return True


# Pre-built critical journeys
DEFAULT_JOURNEYS = [
    Journey(
        journey_id="j001", name="行业报告生成",
        description="必须按序执行: 数据收集→结构分析→章节生成→质量审核→导出",
        steps=[
            JourneyStep("j001_s1", "数据收集", "收集项目原始数据和背景信息", tool="data_collector"),
            JourneyStep("j001_s2", "结构分析", "分析报告模板,确定章节结构", tool="template_analyzer"),
            JourneyStep("j001_s3", "章节生成", "逐章节生成报告内容", tool="doc_engine"),
            JourneyStep("j001_s4", "质量审核", "审核报告完整性和合规性", tool="quality_checker"),
            JourneyStep("j001_s5", "导出", "导出为最终格式", tool="doc_exporter"),
        ],
    ),
    Journey(
        journey_id="j002", name="系统安全操作",
        description="高风险操作必须经过审批流程",
        steps=[
            JourneyStep("j002_s1", "风险评估", "评估操作风险等级", tool="risk_analyzer"),
            JourneyStep("j002_s2", "审批请求", "向管理员发起审批", tool="hitl_gate"),
            JourneyStep("j002_s3", "执行操作", "获得审批后执行", tool="shell_executor"),
            JourneyStep("j002_s4", "结果验证", "验证操作结果", tool="result_validator"),
        ],
    ),
]


class JourneyEngine:
    """Enforces sequential workflow execution. Steps cannot be skipped."""

    def __init__(self):
        self._journeys: dict[str, Journey] = {}
        self._active: dict[str, dict] = {}  # session_id → {journey_id, current_step, completed}
        self._load()

    def _load(self):
        if JOURNEYS_FILE.exists():
            try:
                data = _json.loads(JOURNEYS_FILE.read_text())
                for item in data:
                    steps = [JourneyStep(**s) for s in item.get("steps", [])]
                    j = Journey(
                        journey_id=item["id"], name=item["name"],
                        description=item.get("description", ""),
                        steps=steps, on_violation=item.get("on_violation", "restart"),
                    )
                    self._journeys[j.journey_id] = j
            except Exception:
                pass
        if not self._journeys:
            for j in DEFAULT_JOURNEYS:
                self._journeys[j.journey_id] = j
            self._save()

    def _save(self):
        JOURNEYS_FILE.write_text(_json.dumps(
            [{"id": j.journey_id, "name": j.name, "description": j.description,
              "steps": [s.__dict__ for s in j.steps], "on_violation": j.on_violation}
             for j in self._journeys.values()],
            ensure_ascii=False, indent=2,
        ))

    def start_journey(self, session_id: str, journey_id: str) -> dict:
        j = self._journeys.get(journey_id)
        if not j:
            return {"ok": False, "error": "journey not found"}
        self._active[session_id] = {
            "journey_id": journey_id, "current_step": 0,
            "completed": [], "started_at": _time.time(),
        }
        current = j.steps[0]
        return {
            "ok": True, "step": 1, "total": len(j.steps),
            "current": current.name, "description": current.description,
            "tool": current.tool,
        }

    def advance_step(self, session_id: str) -> dict:
        active = self._active.get(session_id)
        if not active:
            return {"ok": False, "error": "no active journey"}

        j = self._journeys[active["journey_id"]]
        current_idx = active["current_step"]

        # Record completion of current step
        active["completed"].append({
            "step_id": j.steps[current_idx].step_id,
            "status": "done", "completed_at": _time.time(),
        })
        active["current_step"] += 1

        if active["current_step"] >= len(j.steps):
            del self._active[session_id]
            return {"ok": True, "completed": True, "message": "Journey complete"}

        next_step = j.steps[active["current_step"]]
        return {
            "ok": True, "step": active["current_step"] + 1,
            "total": len(j.steps), "current": next_step.name,
            "description": next_step.description, "tool": next_step.tool,
        }

    def can_proceed(self, session_id: str, next_step_index: int) -> bool:
        active = self._active.get(session_id)
        if not active:
            return True
        j = self._journeys[active["journey_id"]]
        return j.validate_step(next_step_index, active["completed"])

    def status(self) -> dict:
        return {
            "total_journeys": len(self._journeys),
            "active_sessions": len(self._active),
            "journeys": [
                {"id": j.journey_id, "name": j.name, "steps": len(j.steps)}
                for j in self._journeys.values()
            ],
        }


# ═══ 3. ARQ: Guide → Respond → Verify ═══

class ARQVerifier:
    """Structured reasoning pipeline: Guide ARQ → Response Generation → Verification.

    Unlike pure ReAct (which is open-ended), ARQ adds a GUIDANCE step before
    generation and VERIFICATION after, creating a controlled reasoning envelope.
    """

    def __init__(self):
        self._verifications: list[dict] = []

    async def verify_response(self, user_input: str, llm_output: str,
                               guidelines: GuidelineEngine,
                               consciousness=None) -> dict:
        """Verify LLM output against guidelines before returning to user."""
        # Step 1: Guideline enforcement (hard filter)
        enforcement = guidelines.enforce(user_input, llm_output)

        # Step 2: Basic quality checks
        issues = []
        if len(llm_output) < 5:
            issues.append("response_too_short")
        if llm_output.count("I apologize") > 2:
            issues.append("excessive_apology")
        if "as an AI" in llm_output.lower() and len(llm_output) < 100:
            issues.append("deflection_pattern")

        # Step 3: Optional LLM verification
        if consciousness and not issues and enforcement["action"] == "allow":
            try:
                prompt = (
                    f"验证以下回复是否安全、准确、有帮助。仅回复 'pass' 或 'fail: 原因':\n\n"
                    f"用户: {user_input[:200]}\n回复: {llm_output[:500]}"
                )
                result = await consciousness.chain_of_thought(prompt, steps=1)
                text = result if isinstance(result, str) else str(result)
                if text.lower().startswith("fail"):
                    issues.append(f"llm_verification: {text[6:100]}")
            except Exception:
                pass

        verdict = {
            "passed": len(issues) == 0 and enforcement["action"] == "allow",
            "guideline_action": enforcement["action"],
            "guideline_rule": enforcement.get("rule_name", ""),
            "issues": issues,
            "require_approval": enforcement.get("require_approval", False),
            "modified_output": enforcement.get("modified_output", llm_output),
        }
        self._verifications.append(verdict)
        return verdict

    def stats(self) -> dict:
        total = len(self._verifications)
        passed = sum(1 for v in self._verifications if v["passed"])
        return {
            "total_verifications": total,
            "pass_rate": f"{passed/max(total,1)*100:.0f}%",
            "blocked": sum(1 for v in self._verifications if v["guideline_action"] == "block"),
            "redirected": sum(1 for v in self._verifications if v["guideline_action"] == "redirect"),
        }


# ═══ Singletons ═══

_guidelines_instance: Optional[GuidelineEngine] = None
_journeys_instance: Optional[JourneyEngine] = None
_arq_instance: Optional[ARQVerifier] = None


def get_guidelines() -> GuidelineEngine:
    global _guidelines_instance
    if _guidelines_instance is None:
        _guidelines_instance = GuidelineEngine()
    return _guidelines_instance


def get_journeys() -> JourneyEngine:
    global _journeys_instance
    if _journeys_instance is None:
        _journeys_instance = JourneyEngine()
    return _journeys_instance


def get_arq() -> ARQVerifier:
    global _arq_instance
    if _arq_instance is None:
        _arq_instance = ARQVerifier()
    return _arq_instance
