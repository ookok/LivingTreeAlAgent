"""GapOrchestrator — Unified knowledge + tool gap handling with auto-retry.

When LLM cannot answer or lacks a tool, chain all fallback mechanisms
synchronously (not async/post-hoc) and retry.

Knowledge gaps:
  ContextMoE(hot/warm/cold/deep) → web_search → explore_domain
  → AutoGoal(async) → ExternalLearner(background) → retry

Tool gaps:
  CapabilityBus → MCP/LocalToolBus → ReactExecutor
  → ToolSynthesizer(auto-generate) → CLIAnything(wrap) → retry

Unified: both gaps detected in a single pass, chained, retried.
Eliminates the 7 disconnected-silo problem identified in audit.

Usage:
    orchestrator = GapOrchestrator()
    result = await orchestrator.handle_gap(query, llm_response, context)
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class GapResult:
    """Result of gap handling attempt."""
    gap_type: str           # "knowledge" | "tool" | "both"
    resolved: bool
    resolution_method: str  # How it was resolved
    enriched_query: str = ""  # Query with injected knowledge
    new_tool_name: str = ""   # Name of synthesized tool
    attempts: list[str] = field(default_factory=list)
    elapsed_ms: float = 0


class GapOrchestrator:
    """Unified knowledge + tool gap detection and auto-resolution."""

    KNOWLEDGE_GAP_PATTERNS = [
        r"I don't know", r"I'm not sure", r"I cannot answer",
        r"我不知道", r"我不确定", r"无法回答",
        r"not familiar with", r"no information about",
        r"超出了我的知识范围", r"没有相关信息",
    ]
    TOOL_GAP_PATTERNS = [
        r"\[tool:(\w+)\] not available",
        r"Tool not in LocalToolBus",
        r"Unknown tool",
        r"not available",
    ]

    def __init__(self):
        self._synthesizer = None
        self._cli_anything = None

    # ═══ Detection ═════════════════════════════════════════════════

    def detect_gaps(self, response_text: str) -> dict[str, list[str]]:
        """Detect knowledge and tool gaps in LLM response.

        Returns: {"knowledge": [...], "tool": [...]}
        """
        gaps = {"knowledge": [], "tool": []}

        for pattern in self.KNOWLEDGE_GAP_PATTERNS:
            if re.search(pattern, response_text, re.IGNORECASE):
                gaps["knowledge"].append(pattern)
                break

        for pattern in self.TOOL_GAP_PATTERNS:
            match = re.search(pattern, response_text)
            if match:
                gaps["tool"].append(match.group(1) if match.lastindex else pattern)

        return gaps

    # ═══ Knowledge Gap Resolution ═════════════════════════════════

    async def resolve_knowledge_gap(self, query: str,
                                     gaps: list[str]) -> GapResult:
        """Chain knowledge fallbacks and enrich query."""
        result = GapResult(gap_type="knowledge", resolved=False,
                          resolution_method="none")
        t0 = time.time()

        # Tier 1: ContextMoE memory
        try:
            from ..treellm.context_moe import get_context_moe
            moe = get_context_moe("gap_resolver")
            moe_result = await moe.query(query, "research")
            if moe_result and (moe_result.hot or moe_result.warm or moe_result.cold):
                enriched = moe.build_enriched_message(query, moe_result)
                if enriched != query:
                    result.enriched_query = enriched
                    result.resolved = True
                    result.resolution_method = "context_moe"
                    result.attempts.append("context_moe: found relevant memories")
                    logger.info(f"GapOrchestrator: ContextMoE filled knowledge gap")
        except Exception as e:
            result.attempts.append(f"context_moe: {e}")

        # Tier 2: Web search
        if not result.resolved:
            try:
                from ..treellm.core import TreeLLM
                llm = TreeLLM.from_config()
                search_result = await llm.chat(
                    [{"role": "user", "content": f"Search for information about: {query[:200]}"}],
                    max_tokens=500, temperature=0.0, task_type="search", tools=True,
                )
                search_text = getattr(search_result, 'text', '') or ""
                if search_text and not any(
                    re.search(p, search_text, re.IGNORECASE)
                    for p in self.KNOWLEDGE_GAP_PATTERNS
                ):
                    result.enriched_query = f"[Web search results]\n{search_text[:1000]}\n\nUser query: {query}"
                    result.resolved = True
                    result.resolution_method = "web_search"
                    result.attempts.append("web_search: found relevant information")
                    logger.info(f"GapOrchestrator: web_search filled knowledge gap")
            except Exception as e:
                result.attempts.append(f"web_search: {e}")

        # Tier 3: Explore domain (deep research)
        if not result.resolved:
            try:
                from ..execution.react_executor import ReactExecutor
                rex = ReactExecutor()
                domain_result = await rex._tool_explore_domain(query[:200])
                if domain_result and len(domain_result) > 50:
                    result.enriched_query = f"[Domain research]\n{domain_result[:1000]}\n\nUser query: {query}"
                    result.resolved = True
                    result.resolution_method = "explore_domain"
                    result.attempts.append("explore_domain: built world knowledge")
                    logger.info(f"GapOrchestrator: explore_domain filled knowledge gap")
            except Exception as e:
                result.attempts.append(f"explore_domain: {e}")

        # Tier 4: Schedule async AutoGoal for persistent learning
        try:
            self._schedule_auto_goal(query, gaps)
            result.attempts.append("auto_goal: scheduled background research")
        except Exception:
            pass

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    # ═══ Tool Gap Resolution ══════════════════════════════════════

    async def resolve_tool_gap(self, query: str, tool_name: str) -> GapResult:
        """Auto-synthesize missing tools on demand."""
        result = GapResult(gap_type="tool", resolved=False,
                          resolution_method="none")
        t0 = time.time()

        if not tool_name:
            return result

        # Tier 1: Try CLIAnything — wrap any system program
        try:
            result.attempts.append("cli_anything: attempting to wrap binary")
            from ..treellm.cli_anything import get_cli_anything
            cli = get_cli_anything()
            # Check if binary exists on PATH
            import shutil
            if shutil.which(tool_name):
                result.new_tool_name = f"cli:{tool_name}"
                result.resolved = True
                result.resolution_method = "cli_anything"
                result.attempts.append(f"cli_anything: wrapped {tool_name}")
                logger.info(f"GapOrchestrator: cli_anything wrapped {tool_name}")
        except Exception as e:
            result.attempts.append(f"cli_anything: {e}")

        # Tier 2: Try ToolSynthesizer — LLM generate tool code
        if not result.resolved:
            try:
                from ..capability.tool_synthesis import ToolSynthesizer
                if not self._synthesizer:
                    self._synthesizer = ToolSynthesizer()
                synth_result = self._synthesizer.synthesize(
                    f"Create a tool to: {query[:200]}", execute=False)
                if synth_result and synth_result.get("tool_name"):
                    result.new_tool_name = synth_result["tool_name"]
                    result.resolved = True
                    result.resolution_method = "tool_synthesis"
                    result.attempts.append(f"tool_synthesis: created {result.new_tool_name}")
                    logger.info(f"GapOrchestrator: synthesized tool {result.new_tool_name}")
            except Exception as e:
                result.attempts.append(f"tool_synthesis: {e}")

        # Tier 3: Try CapabilityBus registration for future use
        if result.resolved and result.new_tool_name:
            try:
                from ..treellm.capability_bus import get_capability_bus, Capability, CapCategory, CapParam
                bus = get_capability_bus()
                bus.register(Capability(
                    id=f"tool:{result.new_tool_name}",
                    name=result.new_tool_name,
                    category=CapCategory.TOOL,
                    description=f"Auto-synthesized tool for: {query[:100]}",
                    params=[CapParam(name="input", type="string")],
                    source="gap_orchestrator",
                    tags=["auto_generated"],
                ))
                result.attempts.append("capability_bus: registered for future use")
            except Exception:
                pass

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    # ═══ Unified Handler ══════════════════════════════════════════

    async def handle_gap(self, query: str, response_text: str,
                         context: dict = None) -> GapResult:
        """Detect and resolve both knowledge and tool gaps in one pass.

        Chain: detect → resolve knowledge → resolve tool → retry-ready.

        Returns GapResult with enriched_query for retry.
        """
        gaps = self.detect_gaps(response_text)
        if not gaps["knowledge"] and not gaps["tool"]:
            return GapResult(gap_type="none", resolved=False,
                           resolution_method="no_gap_detected")

        logger.info(f"GapOrchestrator: detected knowledge={len(gaps['knowledge'])} "
                   f"tool={len(gaps['tool'])} gaps")

        # Resolve knowledge first (enriched query helps tool synthesis too)
        knowledge_result = None
        if gaps["knowledge"]:
            knowledge_result = await self.resolve_knowledge_gap(query, gaps["knowledge"])

        # Resolve tool gaps
        tool_result = None
        if gaps["tool"]:
            tool_name = gaps["tool"][0] if gaps["tool"] else ""
            tool_result = await self.resolve_tool_gap(query, tool_name)

        # Merge results
        merged = GapResult(
            gap_type="both" if knowledge_result and tool_result else
                     "knowledge" if knowledge_result else "tool",
            resolved=(knowledge_result and knowledge_result.resolved) or
                     (tool_result and tool_result.resolved),
            resolution_method=f"{knowledge_result.resolution_method if knowledge_result else ''}+"
                            f"{tool_result.resolution_method if tool_result else ''}",
            enriched_query=knowledge_result.enriched_query if knowledge_result else query,
            new_tool_name=tool_result.new_tool_name if tool_result else "",
            attempts=(knowledge_result.attempts if knowledge_result else []) +
                     (tool_result.attempts if tool_result else []),
            elapsed_ms=(knowledge_result.elapsed_ms if knowledge_result else 0) +
                       (tool_result.elapsed_ms if tool_result else 0),
        )

        if merged.resolved:
            logger.info(f"GapOrchestrator: resolved via {merged.resolution_method} "
                       f"({merged.elapsed_ms:.0f}ms)")

        return merged

    def _schedule_auto_goal(self, query: str, gaps: list[str]) -> None:
        """Schedule async background research for persistent learning."""
        try:
            from ..dna.autonomous_goals import get_autonomous_goal_engine
            engine = get_autonomous_goal_engine()
            engine.add_goal(
                topic=f"Research knowledge gap: {query[:150]}",
                source="gap_detected",
                patterns=gaps[:3],
            )
        except Exception:
            pass


__all__ = ["GapOrchestrator", "GapResult"]
