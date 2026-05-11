"""UserModel — unified user memory integrating 6 scattered modules.

Previously fragmented across:
  persona_memory.py  — 6-domain structured facts (biography/preferences/work/...)
  advanced.py        — implicit habits (DigitalTwin: peak hours, verbosity, negation)
  struct_mem.py      — LLM-extracted opinions and preferences
  session_binding.py — /prefer model lock
  meta_memory.py     — strategy preference tracking
  progressive_trust.py — user trust scoring

Now: single UserModel.inject_into_prompt() builds compact user profile for
system prompt injection. All sources merged, no duplicates, priority-ordered.

Three memory layers:
  L1 指令: user corrections, explicit /prefer, named preferences
  L2 习惯: implicit patterns (verbosity, active hours, domain affinity)
  L3 环境: project context, working directory, model binding

Usage:
    model = get_user_model()
    model.record_correction("不要用高斯烟羽，用AERSCREEN")  # L1
    model.observe_message("帮我分析水质")                     # L2
    profile = model.inject_into_prompt()                      # → system prompt
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

USER_MODEL_DIR = Path(".livingtree/user")
USER_MODEL_FILE = USER_MODEL_DIR / "user_model.json"


@dataclass
class UserCorrection:
    """A user correction: 'don't do X, do Y instead'."""
    trigger: str
    correction: str
    category: str = "general"
    count: int = 1
    last_seen: float = field(default_factory=time.time)
    source: str = "explicit"

    def to_rule(self) -> str:
        return f"用户偏好: {self.correction} (而非{self.trigger})"


@dataclass
class UserHabit:
    """Implicitly learned user habit."""
    name: str
    value: float
    threshold: float = 0.0
    signal: str = ""


@dataclass
class UserProfile:
    corrections: list[UserCorrection] = field(default_factory=list)
    habits: list[UserHabit] = field(default_factory=list)
    domain_affinity: dict[str, int] = field(default_factory=dict)
    preferred_model: str = ""
    verbosity_avg: int = 0
    peak_hour: int = 9
    negation_ratio: float = 0.0
    project_context: str = ""
    last_updated: float = 0.0


class UserModel:
    """Unified user memory with three-layer architecture.

    L1: 指令 → explicit corrections, named preferences, model lock
    L2: 习惯 → implicit patterns from message observation
    L3: 环境 → project context, working directory, trust level
    """

    MAX_CORRECTIONS = 20
    CORRECTION_CONFIDENCE_THRESHOLD = 2

    def __init__(self):
        self.profile = UserProfile()
        self._synced = False
        self._persona = None  # Lazy-init PersonaMemory bridge
        self._load()
    
    @property
    def persona(self):
        """Lazy-init PersonaMemory for 6-domain structured persona extraction."""
        if self._persona is None:
            try:
                from .persona_memory import get_persona_memory
                self._persona = get_persona_memory()
            except Exception:
                self._persona = False  # Sentinel: not available
        return self._persona if self._persona is not False else None

    # ── L1: Explicit User Instructions ──

    def record_correction(self, statement: str, category: str = "general"):
        """Record a user correction: "don't use X, use Y" or "I prefer Z"."""
        trigger, correction = self._parse_correction(statement)

        for c in self.profile.corrections:
            if c.trigger == trigger and c.correction == correction:
                c.count += 1
                c.last_seen = time.time()
                self._save()
                return

        self.profile.corrections.append(UserCorrection(
            trigger=trigger, correction=correction,
            category=category, source="explicit",
        ))

        if len(self.profile.corrections) > self.MAX_CORRECTIONS:
            self.profile.corrections.sort(key=lambda c: -c.count)
            self.profile.corrections = self.profile.corrections[:self.MAX_CORRECTIONS]

        self._save()

    def set_preference(self, key: str, value: str):
        """Generic preference: user_prefs['model'] = 'deepseek'."""
        self.record_correction(f"偏好: {key}={value}", "preference")

    def get_instruction_rules(self) -> list[str]:
        """Get high-confidence user instruction rules for prompt injection."""
        rules = []
        for c in self.profile.corrections:
            if c.count >= self.CORRECTION_CONFIDENCE_THRESHOLD:
                rules.append(c.to_rule())
        return rules

    # ── L2: Implicit Habit Tracking ──

    def observe_message(self, message: str, auto_pro: bool = False):
        """Track implicit preferences from message content and metadata."""
        hour = time.localtime().tm_hour

        domain = self._detect_domain(message)
        if domain:
            self.profile.domain_affinity[domain] = (
                self.profile.domain_affinity.get(domain, 0) + 1)

        n = max(self.profile.verbosity_avg, 1) + 1
        self.profile.verbosity_avg = int(
            self.profile.verbosity_avg + (len(message) - self.profile.verbosity_avg) / n)

        if auto_pro:
            self.profile.habits.append(UserHabit(
                name="pro_model_trigger", value=1.0, signal="complex_query"))

        negations = sum(1 for w in ["不", "没", "别", "错误", "失败", "不行"]
                        if w in message)
        if negations > 0:
            old = self.profile.negation_ratio
            self.profile.negation_ratio = old + (1.0 - old) / n

        self.profile.peak_hour = hour
        self.profile.last_updated = time.time()
        self._save()
        
        # ── PersonaMemory: extract structured 6-domain facts from message ──
        # Wire PersonaMemory into the existing UserModel observe flow
        # (Island fix: PersonaMemory was a complete island with 0 callers)
        pm = self.persona
        if pm and len(message) > 20:
            try:
                pm.ingest(message)
            except Exception:
                pass  # Non-critical: persona extraction failure shouldn't block

    def get_habit_rules(self) -> list[str]:
        """Get implicit habit signals for prompt injection."""
        rules = []
        if self.profile.verbosity_avg < 50:
            rules.append("用户偏好极简回答 (平均消息长度<50字符)")
        elif self.profile.verbosity_avg > 500:
            rules.append("用户偏好详细回答 (平均消息长度>500字符)")

        top_domains = sorted(self.profile.domain_affinity.items(),
                             key=lambda x: -x[1])[:3]
        if top_domains:
            rules.append(f"用户常用领域: {', '.join(d for d, _ in top_domains)}")

        if self.profile.negation_ratio > 0.3:
            rules.append("用户经常否定/修正输出 — 首次回答应更谨慎")

        if self.profile.preferred_model:
            rules.append(f"用户锁定模型: {self.profile.preferred_model}")

        return rules

    # ── L3: Environment Context ──

    def set_project_context(self, path: str, description: str = ""):
        self.profile.project_context = f"{path}"
        if description:
            self.profile.project_context += f" ({description})"
        self._save()

    def set_model_preference(self, model: str):
        self.profile.preferred_model = model
        self._save()

    def get_env_rules(self) -> list[str]:
        rules = []
        if self.profile.project_context:
            rules.append(f"当前项目: {self.profile.project_context}")
        if self.profile.preferred_model:
            rules.append(f"首选模型: {self.profile.preferred_model}")
        return rules

    # ── Unified Prompt Injection ──

    def inject_into_prompt(self, role: str = "") -> str:
        """Build unified user profile for system prompt injection.

        Returns compact profile block for appending to system message.
        Uses ContextCodex symbols for compression when available.
        """
        rules = []
        rules.extend(self.get_instruction_rules())
        rules.extend(self.get_habit_rules())
        rules.extend(self.get_env_rules())
        
        # Enrich with PersonaMemory structured facts (cross-domain user profile)
        pm = self.persona
        if pm:
            try:
                persona_ctx = pm.get_context_for_query(role or "general")
                if persona_ctx:
                    rules.append(f"用户画像: {persona_ctx[:300]}")
            except Exception:
                pass

        if not rules:
            return ""

        lines = ["[UserModel: 用户画像]\n"]
        for r in rules:
            lines.append(f"- {r}")
        lines.append("")

        raw = "\n".join(lines)
        try:
            from ..execution.context_codex import get_context_codex
            codex = get_context_codex(seed=False)
            compressed, header = codex.compress(raw, layer=2, max_header_chars=300)
            if header:
                return f"{header}\n---\n{compressed}"
        except Exception:
            pass
        return raw

    def inject_minimal(self) -> str:
        """Ultra-compact user profile (for tight context budgets)."""
        parts = []
        top_corrections = sorted(self.profile.corrections,
                                  key=lambda c: -c.count)[:3]
        for c in top_corrections:
            if c.count >= self.CORRECTION_CONFIDENCE_THRESHOLD:
                parts.append(c.correction[:80])

        if self.profile.preferred_model:
            parts.append(f"model={self.profile.preferred_model}")

        if not parts:
            return ""
        return "[用户] " + " | ".join(parts)

    # ── Internal ──

    def _parse_correction(self, statement: str) -> tuple[str, str]:
        patterns = [
            (r"不要[用做]?(.+?)[，,]\s*(?:要|用|改用|应该)(.+)", 1, 2),
            (r"(?:别|不要|停止)[用做]?(.+)", 1, 0),
            (r"以后(.+)", 0, 0),
            (r"我(?:喜欢|偏好|希望|习惯)(.+)", 0, 0),
        ]
        for pattern, trigger_group, corr_group in patterns:
            m = re.search(pattern, statement)
            if m:
                trigger = m.group(trigger_group).strip()[:50] if trigger_group > 0 else ""
                correction = m.group(corr_group).strip()[:80] if corr_group > 0 else (
                    m.group(1).strip()[:80])
                if not trigger:
                    trigger = correction
                return trigger, correction
        return statement[:50], statement[:80]

    @staticmethod
    def _detect_domain(message: str) -> str:
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ["环评", "标准", "GB", "HJ", "监测", "排放"]):
            return "EIA"
        if any(kw in msg_lower for kw in ["代码", "bug", "函数", "class", "import"]):
            return "code"
        if any(kw in msg_lower for kw in ["报告", "文档", "生成", "模板"]):
            return "document"
        if any(kw in msg_lower for kw in ["分析", "数据", "统计", "对比"]):
            return "analysis"
        return "general"

    def _save(self):
        try:
            USER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "corrections": [
                    {"trigger": c.trigger, "correction": c.correction,
                     "category": c.category, "count": c.count,
                     "last_seen": c.last_seen}
                    for c in self.profile.corrections
                ],
                "domain_affinity": self.profile.domain_affinity,
                "preferred_model": self.profile.preferred_model,
                "verbosity_avg": self.profile.verbosity_avg,
                "peak_hour": self.profile.peak_hour,
                "negation_ratio": self.profile.negation_ratio,
                "project_context": self.profile.project_context,
                "last_updated": time.time(),
            }
            USER_MODEL_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"UserModel save: {e}")

    def _load(self):
        try:
            if USER_MODEL_FILE.exists():
                data = json.loads(USER_MODEL_FILE.read_text())
                self.profile.corrections = [
                    UserCorrection(**c) for c in data.get("corrections", [])
                ]
                self.profile.domain_affinity = data.get("domain_affinity", {})
                self.profile.preferred_model = data.get("preferred_model", "")
                self.profile.verbosity_avg = data.get("verbosity_avg", 0)
                self.profile.negation_ratio = data.get("negation_ratio", 0.0)
                self.profile.project_context = data.get("project_context", "")
                self.profile.last_updated = data.get("last_updated", 0.0)
                self.profile.peak_hour = data.get("peak_hour", 9)
        except Exception as e:
            logger.debug(f"UserModel load: {e}")


_user_model: UserModel | None = None


def get_user_model() -> UserModel:
    global _user_model
    if _user_model is None:
        _user_model = UserModel()
    return _user_model
