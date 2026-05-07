"""DiffusionPlanner — RFdiffusion-inspired progressive plan refinement.

Inspired by RFdiffusion's denoising process in protein design:
just as RFdiffusion starts from random noise and iteratively denoises
into a valid protein backbone (noise → coarse structure → precise atoms),
DiffusionPlanner starts from a vague user intent and progressively refines
it into a concrete, fully-parameterized execution plan.

Three refinement stages:
  1. Skeleton:   intent → high-level action outline (WHAT to accomplish)
  2. Tools:      skeleton → tool assignment per step (WHICH tools to use)
  3. Parameters: tool plan → concrete parameters (HOW exactly to execute)

This staged approach reduces LLM hallucination compared to one-shot planning,
especially for complex multi-step tasks.

Usage:
    planner = get_diffusion_planner(consciousness=llm)
    plan = await planner.refine("Implement JWT auth for the REST API")
    print(plan.final_plan)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ── Diffusion Pipeline Types ─────────────────────────────────────

@dataclass
class DiffusionStep:
    """One stage of the progressive plan refinement."""
    stage: int                     # 1=skeleton, 2=tool_assignment, 3=parameter_binding
    plan_text: str = ""            # The plan at this refinement stage
    tools_used: list[str] = field(default_factory=list)
    confidence: float = 0.5        # 0-1 confidence in this stage's output
    refinement_notes: str = ""     # What changed from the previous stage

    @property
    def stage_name(self) -> str:
        return {1: "skeleton", 2: "tool_assignment", 3: "parameter_binding"}.get(
            self.stage, "unknown")


@dataclass
class RefinedPlan:
    """A fully refined execution plan after 3-stage diffusion."""
    intent: str = ""                    # Original user intent
    domain: str = "general"             # Task domain
    steps: list[DiffusionStep] = field(default_factory=list)
    final_plan: str = ""                # The fully refined plan text
    tools_sequence: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    confidence: float = 0.5             # Aggregate confidence
    refined_at: float = field(default_factory=time.time)

    def summary(self) -> str:
        """One-line summary of the refined plan."""
        n_tools = len(self.tools_sequence)
        n_steps = self.steps[-1].plan_text.count("\n") if self.steps else 0
        return (
            f"[{self.domain}] {self.intent[:60]} → "
            f"{n_tools} tools across ~{n_steps} steps "
            f"(confidence: {self.confidence:.0%})"
        )


class DiffusionPlanner:
    """Progressive plan refinement via 3-stage diffusion (denoising).

    The core insight: LLMs hallucinate less when asked to generate plans
    incrementally. Each stage refines the output from the previous one,
    adding precision while preserving coherence.

    If an LLM consciousness is available, uses it for deep refinement.
    Otherwise falls back to template-based heuristic planning.
    """

    # Domain-specific default tool sets for heuristic fallback
    DOMAIN_TOOLS: dict[str, list[str]] = {
        "code": ["read", "grep", "edit", "lsp_diagnostics", "execute"],
        "code_engineering": ["read", "grep", "edit", "lsp_diagnostics", "execute", "git"],
        "document": ["read", "analyze", "write", "visual_render"],
        "data": ["read", "analyze", "search", "web_fetch", "write"],
        "general": ["read", "analyze", "search", "write"],
    }

    def __init__(self, consciousness: Any = None):
        """Initialize the diffusion planner.

        Args:
            consciousness: Optional LLM consciousness for deep refinement.
                           Must have async query(prompt, max_tokens, temperature).
        """
        self._consciousness = consciousness
        self._plan_count = 0

    async def refine(
        self, intent: str, domain: str = "general",
    ) -> RefinedPlan:
        """Run full 3-stage progressive refinement.

        Args:
            intent: User's natural language intent.
            domain: Task domain for context-aware planning.

        Returns:
            Fully refined RefinedPlan with all 3 stages.
        """
        self._plan_count += 1

        if self._consciousness and hasattr(self._consciousness, 'query'):
            return await self._llm_refine(intent, domain)
        else:
            return self._heuristic_refine(intent, domain)

    async def _llm_refine(
        self, intent: str, domain: str,
    ) -> RefinedPlan:
        """LLM-powered 3-stage refinement."""
        steps: list[DiffusionStep] = []

        # Stage 1: Skeleton
        skeleton = await self._stage_skeleton(intent, domain)
        steps.append(skeleton)

        # Stage 2: Tool Assignment
        tool_plan = await self._stage_tools(skeleton.plan_text, domain)
        steps.append(tool_plan)

        # Stage 3: Parameter Binding
        param_plan = await self._stage_params(tool_plan.plan_text, domain)
        steps.append(param_plan)

        # Aggregate
        all_tools: list[str] = []
        for s in steps:
            all_tools.extend(s.tools_used)
        # Deduplicate preserving order
        seen: set[str] = set()
        tools_seq = [t for t in all_tools if not (t in seen or seen.add(t))]

        avg_conf = sum(s.confidence for s in steps) / max(len(steps), 1)
        est_tokens = len(param_plan.plan_text) // 3 + len(intent) // 3 + 500

        plan = RefinedPlan(
            intent=intent,
            domain=domain,
            steps=steps,
            final_plan=param_plan.plan_text,
            tools_sequence=tools_seq,
            estimated_tokens=est_tokens,
            confidence=round(avg_conf, 3),
        )
        logger.info(
            f"DiffusionPlanner: '{intent[:50]}...' → "
            f"{len(tools_seq)} tools, confidence={plan.confidence:.0%}")
        return plan

    # ── Stage 1: Skeleton ─────────────────────────────────────────

    async def _stage_skeleton(
        self, intent: str, domain: str,
    ) -> DiffusionStep:
        """Generate the high-level structural plan (WHAT to do, not HOW)."""
        prompt = (
            f"You are a planning assistant. Given this user intent in the "
            f"'{domain}' domain, produce a HIGH-LEVEL action plan with 3-7 steps.\n\n"
            f"Focus on WHAT to accomplish, not HOW. Think about the logical "
            f"sequence of actions needed to achieve the goal.\n\n"
            f"User intent: {intent}\n\n"
            f"Output format — numbered list, one step per line:\n"
            f"1. [action description]\n"
            f"2. [action description]\n"
            f"...\n\n"
            f"Keep it high-level — do NOT specify tools or file paths."
        )

        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=400, temperature=0.4)
            return DiffusionStep(
                stage=1,
                plan_text=raw.strip(),
                confidence=0.85,
                refinement_notes="Initial skeleton from intent",
            )
        except Exception as e:
            logger.warning(f"Stage 1 (skeleton) LLM error: {e}")
            return DiffusionStep(
                stage=1,
                plan_text=f"1. Analyze {intent}\n2. Execute solution\n3. Verify result",
                confidence=0.3,
                refinement_notes="Fallback skeleton",
            )

    # ── Stage 2: Tool Assignment ──────────────────────────────────

    async def _stage_tools(
        self, skeleton: str, domain: str,
    ) -> DiffusionStep:
        """Assign specific tools to each skeleton step."""
        prompt = (
            f"You are a tool assignment specialist. Given a high-level action plan "
            f"for domain '{domain}', assign specific tools to each step.\n\n"
            f"Available tool categories: read (file reading), write (file creation), "
            f"edit (file modification), grep (code search), execute (shell commands), "
            f"search (web/knowledge search), analyze (data analysis), "
            f"lsp_diagnostics (code quality checks), git (version control).\n\n"
            f"Skeleton plan:\n{skeleton}\n\n"
            f"Output format — for each step, add tool name in brackets:\n"
            f"1. [tool_name] action description\n"
            f"2. [tool_name] action description\n"
            f"..."
        )

        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=500, temperature=0.3)
            tools = self._parse_tools_from_text(raw)
            return DiffusionStep(
                stage=2,
                plan_text=raw.strip(),
                tools_used=tools,
                confidence=0.80,
                refinement_notes="Tool assignment from skeleton",
            )
        except Exception as e:
            logger.warning(f"Stage 2 (tools) LLM error: {e}")
            return DiffusionStep(
                stage=2,
                plan_text=skeleton,
                tools_used=[],
                confidence=0.3,
                refinement_notes="Fallback: no tool assignment",
            )

    # ── Stage 3: Parameter Binding ────────────────────────────────

    async def _stage_params(
        self, tool_plan: str, domain: str,
    ) -> DiffusionStep:
        """Bind concrete parameters (file paths, values) to tool steps."""
        prompt = (
            f"You are a parameter binding specialist. Given a tool-assigned plan "
            f"for domain '{domain}', add concrete parameters to each step.\n\n"
            f"Tool plan:\n{tool_plan}\n\n"
            f"Output format — for each step, add parameters in parentheses:\n"
            f"1. tool_name(param1='value1', param2='value2') — description\n"
            f"2. tool_name(param1='value1') — description\n"
            f"...\n\n"
            f"Use realistic parameter names and values. For file tools, include "
            f"actual file paths. For search, include query strings."
        )

        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=600, temperature=0.2)
            tools = self._parse_tools_from_text(raw)
            return DiffusionStep(
                stage=3,
                plan_text=raw.strip(),
                tools_used=tools,
                confidence=0.75,
                refinement_notes="Parameter binding from tool plan",
            )
        except Exception as e:
            logger.warning(f"Stage 3 (params) LLM error: {e}")
            return DiffusionStep(
                stage=3,
                plan_text=tool_plan,
                tools_used=[],
                confidence=0.3,
                refinement_notes="Fallback: no parameter binding",
            )

    # ── Heuristic Fallback ────────────────────────────────────────

    def _heuristic_refine(self, intent: str, domain: str) -> RefinedPlan:
        """Template-based heuristic planning (no LLM required)."""
        tools = self.DOMAIN_TOOLS.get(domain, self.DOMAIN_TOOLS["general"])

        # Generate a domain-appropriate skeleton
        if domain in ("code", "code_engineering"):
            skeleton = (
                f"1. Read and understand the relevant code\n"
                f"2. Plan the changes needed\n"
                f"3. Implement the changes\n"
                f"4. Verify correctness\n"
                f"5. Commit changes"
            )
        elif domain == "document":
            skeleton = (
                f"1. Gather source materials\n"
                f"2. Analyze and extract key points\n"
                f"3. Generate document structure\n"
                f"4. Write document content\n"
                f"5. Review and finalize"
            )
        else:
            skeleton = (
                f"1. Understand the task: {intent[:80]}\n"
                f"2. Gather necessary information\n"
                f"3. Execute the core action\n"
                f"4. Verify the result"
            )

        # Stage 1: Skeleton
        s1 = DiffusionStep(
            stage=1, plan_text=skeleton, confidence=0.5,
            refinement_notes="Heuristic skeleton",
        )

        # Stage 2: Tool assignment
        tool_lines = []
        for i, line in enumerate(skeleton.strip().split("\n"), 1):
            tool_name = tools[i % len(tools)] if tools else "analyze"
            tool_lines.append(f"{i}. [{tool_name}] {line.split('. ', 1)[-1]}")
        tool_plan = "\n".join(tool_lines)
        s2 = DiffusionStep(
            stage=2, plan_text=tool_plan, tools_used=list(tools),
            confidence=0.4, refinement_notes="Heuristic tool assignment",
        )

        # Stage 3: Parameter binding
        param_lines = []
        for line in tool_plan.strip().split("\n"):
            param_lines.append(line + " (heuristic params)")
        param_plan = "\n".join(param_lines)
        s3 = DiffusionStep(
            stage=3, plan_text=param_plan, tools_used=list(tools),
            confidence=0.3, refinement_notes="Heuristic parameter binding",
        )

        est_tokens = len(param_plan) // 3 + len(intent) // 3 + 200

        return RefinedPlan(
            intent=intent,
            domain=domain,
            steps=[s1, s2, s3],
            final_plan=param_plan,
            tools_sequence=list(tools),
            estimated_tokens=est_tokens,
            confidence=0.3,
        )

    # ── Tool Parsing ──────────────────────────────────────────────

    @staticmethod
    def _parse_tools_from_text(text: str) -> list[str]:
        """Extract tool names from plan text.

        Patterns: [tool_name], tool_name(, → tool_name, tool_name:
        """
        tools: list[str] = []
        seen: set[str] = set()

        # Pattern 1: [tool_name]
        for match in re.finditer(r'\[([a-z_][a-z0-9_]*)\]', text, re.IGNORECASE):
            t = match.group(1).lower()
            if t not in seen:
                tools.append(t)
                seen.add(t)

        # Pattern 2: tool_name(
        for match in re.finditer(r'([a-z_][a-z0-9_]*)\(', text, re.IGNORECASE):
            t = match.group(1).lower()
            if t not in seen:
                tools.append(t)
                seen.add(t)

        return tools

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "plans_generated": self._plan_count,
            "has_consciousness": self._consciousness is not None,
        }


# ── Singleton ────────────────────────────────────────────────────

_diffusion_planner: DiffusionPlanner | None = None


def get_diffusion_planner(consciousness: Any = None) -> DiffusionPlanner:
    """Get or create the singleton DiffusionPlanner."""
    global _diffusion_planner
    if _diffusion_planner is None:
        _diffusion_planner = DiffusionPlanner(consciousness=consciousness)
    elif consciousness and not _diffusion_planner._consciousness:
        _diffusion_planner._consciousness = consciousness
    return _diffusion_planner


def reset_diffusion_planner() -> None:
    """Test helper."""
    global _diffusion_planner
    _diffusion_planner = None
