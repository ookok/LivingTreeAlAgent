"""Clarifier — Progressive single-question clarification for complex tasks.

Strategy: ask ONE question at a time, at the moment it becomes blocking.
Modes:
- fill_blank: "Project type? (化工/冶金/电力/其他)" — with options
- confirm_ambiguity: "环境风险 or 安全风险?" — disambiguate
- preview_check: "I plan to do X. Correct?" — confirmation

Answered knowledge is stored in KnowledgeBase for future recall.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger


@dataclass
class Clarification:
    """A single clarification question."""
    id: str
    mode: str  # fill_blank, confirm_ambiguity, preview_check
    question: str
    options: list[str] = field(default_factory=list)
    default_answer: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    answered: bool = False
    answer: str = ""

    def format_for_display(self) -> str:
        if self.mode == "fill_blank" and self.options:
            opts = " / ".join(self.options)
            return f"{self.question}\n[{opts}]"
        return self.question


class Clarifier:
    """Progressive clarification engine.

    Usage:
        clarifier = Clarifier(consciousness, kb)
        questions = await clarifier.analyze(user_input, domain="环评报告")
        for q in questions:
            answer = await hitl.ask(q.question, choices=q.options)
            clarifier.record(q, answer)
    """

    def __init__(self, consciousness: Any = None, kb: Any = None,
                 distillation: Any = None, expert_config: Any = None):
        self.consciousness = consciousness
        self.kb = kb
        self.distillation = distillation
        self.expert_config = expert_config
        self._history: list[Clarification] = []

    async def analyze(self, user_input: str, domain: str = "general",
                      plan: list[dict] | None = None) -> list[Clarification]:
        """Analyze user input and identify missing critical information.

        Returns one clarification question that would most improve execution.
        Returns empty list if no clarification needed.
        """
        # 1. Self-questioning to find knowledge gaps
        if self.consciousness and hasattr(self.consciousness, 'self_questioning'):
            try:
                questions = await self.consciousness.self_questioning(
                    f"Task: {user_input}\nDomain: {domain}\n"
                    "What critical information is missing to execute this task accurately?"
                )
                if questions:
                    # Pick the most critical one and make it a clarification
                    q = self._to_clarification(questions[0], domain)
                    if q:
                        return [q]
            except Exception:
                pass

        # 2. Domain-specific generic detection
        return self._generic_clarifications(user_input, domain)

    async def learn_missing_params(self, domain: str) -> list[str]:
        """Learn what parameters are typically needed for a domain."""
        if self.kb:
            try:
                docs = self.kb.search(f"clarification:{domain}", top_k=10)
                params: set[str] = set()
                for doc in docs:
                    if "params" in doc.metadata:
                        params.update(doc.metadata["params"])
                return list(params)
            except Exception:
                pass

        if self.distillation and self.expert_config:
            try:
                prompt = (
                    f"For tasks in the '{domain}' domain, what key parameters must be clarified "
                    f"with the user before execution? List 3-5 critical questions."
                )
                response = await self.distillation.query_expert(prompt, self.expert_config)
                # Extract questions
                qs = [l.strip("- ").strip() for l in response.split("\n") if "?" in l]
                return qs[:5]
            except Exception:
                pass

        return []

    def record(self, clarification: Clarification) -> None:
        """Record a clarified answer."""
        clarification.answered = True
        self._history.append(clarification)

        # Store in KB for future recall
        if self.kb:
            try:
                from ..knowledge.knowledge_base import Document
                doc = Document(
                    title=f"clarification:{clarification.id}",
                    content=f"Q: {clarification.question}\nA: {clarification.answer}",
                    domain=clarification.context.get("domain", "general"),
                    source="clarifier",
                    metadata={
                        "question": clarification.question,
                        "answer": clarification.answer,
                        "mode": clarification.mode,
                        "params": [clarification.answer],
                    },
                )
                self.kb.add_knowledge(doc)
            except Exception as e:
                logger.debug(f"Clarify KB store: {e}")

    def get_answered(self) -> dict[str, str]:
        """Get all clarified answers as a flat dict."""
        return {c.id: c.answer for c in self._history if c.answered}

    def _to_clarification(self, question: str, domain: str) -> Optional[Clarification]:
        """Convert a self-question into a clarification."""
        import uuid

        # Detect mode from question
        if any(kw in question for kw in ["是否", "is it", "are you"]):
            mode = "confirm_ambiguity"
            options = ["是", "否"]
        elif any(kw in question for kw in ["哪个", "哪种", "what type", "which"]):
            mode = "fill_blank"
            options = []
        else:
            mode = "fill_blank"
            options = []

        return Clarification(
            id=uuid.uuid4().hex[:8],
            mode=mode,
            question=question,
            options=options,
            context={"domain": domain},
        )

    def _generic_clarifications(self, user_input: str, domain: str) -> list[Clarification]:
        """Minimal generic clarifications when no LLM available."""
        import uuid

        domain_checks = {
            "环评": [("项目类型（化工/冶金/电力/其他）？", "fill_blank", ["化工", "冶金", "电力", "其他"])],
            "应急": [("主要风险物质是什么？", "fill_blank", [])],
            "报告": [("报告用途（审批/备案/内部）？", "fill_blank", ["审批", "备案", "内部"])],
        }

        for key, questions in domain_checks.items():
            if key in user_input or key in domain:
                result = []
                for q_text, mode, opts in questions:
                    result.append(Clarification(
                        id=uuid.uuid4().hex[:8], mode=mode,
                        question=q_text, options=opts,
                        context={"domain": domain},
                    ))
                return result
        return []


class ExtendedApproval:
    """Extends HITL binary approval to support answer mode.

    Usage:
        approval = ExtendedApproval(hitl)
        answer = await approval.ask("项目类型？", choices=["化工","冶金","电力","其他"])
        if answer:  # non-empty = answered
            ...
    """

    def __init__(self, hitl: Any):
        self.hitl = hitl

    async def ask(self, question: str, choices: list[str] | None = None,
                  default: str = "") -> str:
        """Ask a question and get a free-text or choice answer.

        Falls back to binary approve/deny if no HITL configured.
        """
        if not self.hitl:
            # No HITL: use first non-empty default
            for choice in (choices or []):
                if choice:
                    return choice
            return default or "generic"

        # Use HITL's approval mechanism, but with the question + options
        context = {"choices": choices, "default": default} if choices else {}
        approved = await self.hitl.request_approval(
            task_name="clarification",
            question=question,
            context=context,
            timeout=300.0,
        )

        if not approved and choices:
            return default or choices[0] if choices else ""
        if not approved:
            return default or "skip"

        # If approved without specific answer, return default
        return default or (choices[0] if choices else "confirmed")
