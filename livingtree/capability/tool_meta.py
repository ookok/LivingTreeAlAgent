"""ToolMeta — DebateTool + SelfEvolvingTool.

    1. DebateTool: multi-agent debate for decision-making (not single-point judgment)
    2. SelfEvolvingTool: auto-rewrite tool code on repeated failures
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class DebateResult:
    topic: str
    rounds: int
    positions: dict[str, str] = field(default_factory=dict)
    consensus: str = ""
    voting: dict[str, int] = field(default_factory=dict)
    summary: str = ""


@dataclass
class EvolveResult:
    tool_name: str
    original_code: str = ""
    rewritten_code: str = ""
    improvement: str = ""
    applied: bool = False


class ToolMeta:
    """Meta-tools: debate and self-evolve."""

    # ═══ DebateTool ═══

    async def debate(
        self,
        topic: str,
        roles: list[str] | None = None,
        rounds: int = 3,
        hub=None,
    ) -> DebateResult:
        """Multi-agent debate: each role argues their position, then consensus emerges.

        Args:
            topic: The question/decision to debate
            roles: List of role names (e.g. ["全栈工程师", "产品经理", "QA工程师"])
            rounds: Number of debate rounds
            hub: LLM access
        """
        if not hub or not hub.world:
            return DebateResult(topic=topic, rounds=0)

        roles = roles or ["全栈工程师", "产品经理", "数据分析师"]
        llm = hub.world.consciousness._llm
        result = DebateResult(topic=topic, rounds=rounds)
        history = []

        # Round 1: Each role states initial position
        for role in roles:
            response = await self._ask_role(
                llm, role, f"你正在参与一项决策辩论。\n题目: {topic}\n请陈述你的立场和建议。", history
            )
            result.positions[role] = response[:500]
            history.append({"role": role, "statement": response[:500]})

        # Rounds 2-N: Rebuttals
        for r in range(rounds - 1):
            for role in roles:
                others = [h for h in history if h["role"] != role]
                context = "\n".join(f"{o['role']}: {o['statement'][:200]}" for o in others[-3:])
                prompt = (
                    f"辩论第{r+2}轮。\n题目: {topic}\n\n"
                    f"其他参与者的观点:\n{context}\n\n"
                    f"作为{role}，请针对上述观点进行回驳或补充你的立场。限200字。"
                )
                response = await self._ask_role(llm, role, prompt, history)
                history.append({"role": role, "statement": response[:500]})

        # Voting & consensus
        try:
            debate_text = "\n\n".join(
                f"**{h['role']}**: {h['statement'][:300]}" for h in history[-len(roles)*2:]
            )
            final = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"DEBATE TOPIC: {topic}\n\n"
                    f"Debate transcript:\n{debate_text[:4000]}\n\n"
                    f"Based on the debate, output JSON:\n"
                    f'{{"consensus": "the final decision or recommendation", '
                    f'"voting": {{"role_name": vote_score_1_to_5}}, '
                    f'"summary": "one-paragraph summary of the debate"}}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.3, max_tokens=800, timeout=20,
            )
            if final and final.text:
                import re
                m = re.search(r'\{[\s\S]*\}', final.text)
                if m:
                    d = json.loads(m.group())
                    result.consensus = d.get("consensus", "")[:1000]
                    result.voting = d.get("voting", {})
                    result.summary = d.get("summary", "")[:500]
        except Exception as e:
            logger.debug(f"Debate consensus: {e}")
            result.summary = "Debate completed, consensus could not be determined automatically."

        return result

    async def _ask_role(self, llm, role: str, prompt: str, history: list[dict]) -> str:
        try:
            r = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.5, max_tokens=400, timeout=15,
            )
            return r.text.strip() if r and r.text else f"[{role}]: No response"
        except Exception:
            return f"[{role}]: Error"

    # ═══ SelfEvolvingTool ═══

    async def self_evolve(
        self,
        tool_name: str,
        error_log: str = "",
        hub=None,
    ) -> EvolveResult:
        """Auto-rewrite tool when it fails 3+ times. LLM reads errors → proposes fix.

        Args:
            tool_name: The failing tool name
            error_log: Concatenated error messages from last 3 failures
            hub: LLM access
        """
        result = EvolveResult(tool_name=tool_name)
        if not hub or not hub.world:
            return result

        # Find the tool's source file
        try:
            from ..tui.widgets.enhanced_tool_call import SYSTEM_TOOLS
            tool_def = SYSTEM_TOOLS.get(tool_name)
            if not tool_def:
                result.improvement = f"Tool {tool_name} not found in registry"
                return result
        except Exception:
            return result

        # Try to find the handler code
        handler_source = self._find_tool_source(tool_name)
        if not handler_source:
            result.improvement = f"No source code found for {tool_name}"
            return result

        result.original_code = handler_source[:3000]
        llm = hub.world.consciousness._llm

        try:
            response = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Tool: {tool_name}\n"
                    f"Description: {tool_def.get('description', '')}\n\n"
                    f"ERROR LOG (last 3 failures):\n{error_log[-3000:]}\n\n"
                    f"ORIGINAL CODE:\n```python\n{handler_source[:4000]}\n```\n\n"
                    f"Analyze the errors and rewrite the handler method to fix them. "
                    f"Output JSON:\n"
                    f'{{"improvement": "what was wrong and how you fixed it", '
                    f'"code": "the fixed Python method code (def method_name(...): ...)"}}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=2000, timeout=30,
            )
            if response and response.text:
                import re
                m = re.search(r'\{[\s\S]*\}', response.text)
                if m:
                    d = json.loads(m.group())
                    result.improvement = d.get("improvement", "")[:500]
                    result.rewritten_code = d.get("code", "")[:5000]

            # Save the proposed fix as a patch
            if result.rewritten_code:
                self._save_evolved_code(tool_name, result.rewritten_code, result.improvement)
                result.applied = True
        except Exception as e:
            logger.debug(f"SelfEvolve: {e}")

        return result

    def _find_tool_source(self, tool_name: str) -> str:
        """Find the handler source code for a tool."""
        # Check tool_executor
        try:
            from .tool_executor import ToolExecutor
            import inspect
            handler = getattr(ToolExecutor, tool_name, None)
            if handler:
                return inspect.getsource(handler)
        except Exception:
            pass

        # Check enhanced_tool_call.py
        try:
            import inspect
            enhanced_path = Path(__file__).parent.parent / "tui" / "widgets" / "enhanced_tool_call.py"
            if enhanced_path.exists():
                return enhanced_path.read_text(encoding="utf-8")[:10000]
        except Exception:
            pass

        return ""

    def _save_evolved_code(self, tool_name: str, code: str, improvement: str):
        """Save evolved code as a hotfix candidate."""
        hotfix_dir = Path(".livingtree/hotfixes")
        hotfix_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        hotfix_path = hotfix_dir / f"{tool_name}_{ts}.py"
        hotfix_path.write_text(
            f"# Auto-evolved fix for {tool_name}\n"
            f"# Improvement: {improvement}\n"
            f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{code}\n",
            encoding="utf-8",
        )
        logger.info(f"Hotfix saved: {hotfix_path}")

        # Also save a log entry
        log_path = hotfix_dir / "evolution_log.json"
        entries = []
        if log_path.exists():
            try:
                entries = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        entries.append({
            "tool": tool_name, "timestamp": ts,
            "improvement": improvement[:200],
            "hotfix": str(hotfix_path),
        })
        log_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


_meta: ToolMeta | None = None


def get_tool_meta() -> ToolMeta:
    global _meta
    if _meta is None:
        _meta = ToolMeta()
    return _meta
