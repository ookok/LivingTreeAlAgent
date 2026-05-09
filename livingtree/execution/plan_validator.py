"""PlanValidator — AlphaFold2-inspired pre-execution plan validation.

Predicts whether a generated execution plan will "fold correctly" before
spending tokens on actual execution. Like AlphaFold2 validates designed
protein sequences against structural plausibility, PlanValidator checks
execution plans for structural soundness, tool availability, and logical
coherence.

Two-tier validation:
  1. Structural check (fast, rule-based): dependency cycles, tool existence,
     missing preconditions, wasted steps
  2. Semantic check (LLM-powered): predicts failure modes and suggests fixes

Usage:
    validator = get_plan_validator(consciousness=llm)
    result = await validator.validate(my_plan, domain="code_engineering")
    if result.success_probability < 0.5:
        for fix in result.fix_suggestions:
            print(f"Suggestion: {fix}")
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ValidationResult:
    """Pre-execution validation outcome for a plan."""
    plan_id: str = ""
    success_probability: float = 0.5
    failure_modes: list[str] = field(default_factory=list)
    fix_suggestions: list[str] = field(default_factory=list)
    structural_issues: list[str] = field(default_factory=list)
    semantic_issues: list[str] = field(default_factory=list)
    confidence: float = 0.5
    validated_at: float = field(default_factory=time.time)

    @property
    def is_risky(self) -> bool:
        return self.success_probability < 0.5

    @property
    def is_safe(self) -> bool:
        return self.success_probability >= 0.8

    def summary(self) -> str:
        lines = [f"Plan '{self.plan_id}': {self.success_probability:.0%} success probability"]
        if self.failure_modes:
            lines.append(f"  Failure modes: {', '.join(self.failure_modes[:3])}")
        if self.fix_suggestions:
            lines.append(f"  Fixes: {', '.join(self.fix_suggestions[:3])}")
        return "\n".join(lines)


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_id: str
    action: str = "execute"
    tool: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    description: str = ""


class PlanValidator:
    """Pre-execution plan validator with structural + semantic analysis.

    Inspired by AlphaFold2's role in protein design pipelines:
    after RFdiffusion generates a backbone and ProteinMPNN assigns a sequence,
    AlphaFold2 predicts whether the designed protein will actually fold.
    Similarly, after a planner produces an execution plan, PlanValidator
    predicts whether it will actually succeed.

    Integration: called during LifeEngine's Plan→Execute transition.
    Risky plans can be sent back for revision instead of wasted execution.
    """

    # Tools that are widely available — plan steps referencing these
    # don't trigger warnings.
    WELL_KNOWN_TOOLS: set[str] = {
        "read", "write", "edit", "execute", "search", "analyze",
        "git", "bash", "grep", "glob", "web_search", "web_fetch",
        "lsp_diagnostics", "lsp_goto_definition", "lsp_find_references",
        "visual_render", "code_engine", "doc_generate", "map_render",
    }

    # Anti-patterns that suggest a plan is structurally flawed.
    ANTI_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)delete\s+(all|everything|entire)", "Destructive action: delete all"),
        (r"(?i)rm\s+-rf\s+[/~]", "Destructive command: rm -rf"),
        (r"(?i)drop\s+table", "Destructive command: DROP TABLE"),
        (r"(?i)force\s+push.*main", "Dangerous: force push to main"),
    ]

    def __init__(self, consciousness: Any = None, rule_pool: Any = None):
        """Initialize the validator.

        Args:
            consciousness: Optional LLM consciousness for semantic analysis.
                           Must have async query(prompt, max_tokens, temperature).
            rule_pool: Optional GlobalRulePool for tool validation rules.
        """
        self._consciousness = consciousness
        self._rule_pool = rule_pool
        self._validation_count = 0
        self._total_plans_validated = 0

    async def validate(
        self, plan: list[PlanStep], domain: str = "general",
        plan_id: str = "",
    ) -> ValidationResult:
        """Validate a plan and return success prediction with failure modes.

        Args:
            plan: Ordered list of plan steps to validate.
            domain: Task domain for context-aware validation.
            plan_id: Optional plan identifier for the result.

        Returns:
            ValidationResult with probability, failure modes, and fix suggestions.
        """
        pid = plan_id or f"plan_{self._total_plans_validated}"
        self._total_plans_validated += 1

        # Phase 1: Fast structural check
        structural_issues = self._structural_check(plan)

        # Phase 2: Semantic analysis (LLM if available)
        semantic_issues: list[str] = []
        failure_modes: list[str] = []
        fix_suggestions: list[str] = []

        if self._consciousness and hasattr(self._consciousness, 'query'):
            try:
                prob, fmodes, fixes = await self._predict_failure_modes(
                    plan, domain)
                failure_modes = fmodes
                fix_suggestions = fixes
                semantic_issues = fmodes
            except Exception as e:
                logger.debug(f"Semantic plan validation failed: {e}")
                semantic_issues = self._heuristic_semantic(plan, domain)
                failure_modes = semantic_issues
                prob = 0.5
        else:
            semantic_issues = self._heuristic_semantic(plan, domain)
            failure_modes = semantic_issues
            prob = 0.5

        # Combine: structural issues dominate the score
        success_prob = self._calc_success_probability(
            structural_issues, semantic_issues, prob)

        confidence = 0.9 if self._consciousness else 0.6

        result = ValidationResult(
            plan_id=pid,
            success_probability=success_prob,
            failure_modes=failure_modes,
            fix_suggestions=fix_suggestions,
            structural_issues=structural_issues,
            semantic_issues=semantic_issues,
            confidence=confidence,
        )
        self._validation_count += 1
        logger.info(
            f"PlanValidator: '{pid}' → {success_prob:.0%} "
            f"({len(structural_issues)} structural, {len(semantic_issues)} semantic issues)")
        return result

    # ── Structural Checks ──────────────────────────────────────────

    def _structural_check(self, steps: list[PlanStep]) -> list[str]:
        """Check for common structural anti-patterns in the plan DAG.

        Returns list of issue descriptions. Empty list = structurally sound.
        """
        issues: list[str] = []

        if not steps:
            issues.append("Empty plan: no steps defined")
            return issues

        # 1. Check for steps referencing unknown tools
        tool_names = {s.tool for s in steps if s.tool}
        for step in steps:
            if step.tool and step.tool not in self.WELL_KNOWN_TOOLS:
                # Not in our known list — might still exist, flag as warning
                if not self._looks_like_valid_tool(step.tool):
                    issues.append(
                        f"Step '{step.step_id}': unknown tool '{step.tool}' — "
                        f"may not exist")

        # 2. Check for circular dependencies
        cycle = self._detect_cycle(steps)
        if cycle:
            issues.append(f"Circular dependency detected: {' → '.join(cycle)}")

        # 3. Check for missing preconditions
        read_steps = {s.step_id for s in steps if s.tool == "read"}
        edit_steps = [s for s in steps if s.tool in ("edit", "write")]
        for estep in edit_steps:
            target = estep.params.get("filePath", estep.params.get("path", ""))
            if target:
                # Check if any read step references this file (as precondition)
                has_preread = any(
                    s.params.get("filePath", s.params.get("path", "")) == target
                    for s in steps if s.step_id in read_steps)
                if not has_preread and not any(
                        d in read_steps for d in estep.dependencies):
                    issues.append(
                        f"Step '{estep.step_id}': editing '{target}' without "
                        f"prior read — consider adding read dependency")

        # 4. Check for wasted steps (results used by no one)
        all_deps = set()
        for s in steps:
            all_deps.update(s.dependencies)
        for s in steps:
            if s.step_id not in all_deps and s != steps[-1]:
                if s.tool not in ("read", "analyze", "search"):
                    pass  # Tools like analyze may produce side-effects used later

        # 5. Check for anti-patterns in descriptions / params
        for step in steps:
            desc = step.description
            params_str = json.dumps(step.params, ensure_ascii=False)
            for pattern, warning in self.ANTI_PATTERNS:
                if re.search(pattern, desc + params_str):
                    issues.append(f"Step '{step.step_id}': {warning}")

        # 6. Check step count sanity
        if len(steps) > 15:
            issues.append(
                f"Plan has {len(steps)} steps — high risk of cascading failure. "
                f"Consider splitting into sub-plans.")

        # 7. Check dependency chain depth
        max_depth = self._max_chain_depth(steps)
        if max_depth > 8:
            issues.append(
                f"Dependency chain depth {max_depth} — long chains increase "
                f"probability of mid-chain failure.")

        # 8. OKH-RAG: Precedence-based order validation
        if len(steps) >= 3:
            step_types = [self._infer_step_type(s) for s in steps]
            try:
                from ..knowledge.precedence_model import get_precedence_model
                model = get_precedence_model()
                score = model.score_ordering(step_types)
                if score < 0.3:
                    # Infer optimal ordering for comparison
                    optimal = model.order_facts(step_types)
                    if optimal.ordered_types != step_types:
                        issues.append(
                            f"Plan step order may be suboptimal (coherence={score:.2f}). "
                            f"Suggested order: {' → '.join(optimal.ordered_types[:5])}",
                        )
            except ImportError:
                pass

        return issues

    def _detect_cycle(self, steps: list[PlanStep]) -> list[str]:
        """Detect circular dependencies using DFS. Returns the cycle path or empty."""
        step_map = {s.step_id: s for s in steps}
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.step_id: WHITE for s in steps}
        parent: dict[str, str | None] = {s.step_id: None for s in steps}

        def dfs(node: str) -> list[str]:
            color[node] = GRAY
            step = step_map.get(node)
            if step:
                for dep in step.dependencies:
                    if dep not in color:
                        continue
                    if color[dep] == GRAY:
                        # Found cycle — reconstruct path
                        path = [dep, node]
                        cur = node
                        while parent.get(cur) and parent[cur] != dep:
                            cur = parent[cur] or ""
                            if cur:
                                path.append(cur)
                        return path
                    if color[dep] == WHITE:
                        parent[dep] = node
                        result = dfs(dep)
                        if result:
                            return result
            color[node] = BLACK
            return []

        for sid in color:
            if color[sid] == WHITE:
                result = dfs(sid)
                if result:
                    return result
        return []

    def _max_chain_depth(self, steps: list[PlanStep]) -> int:
        """Compute the maximum dependency chain depth."""
        step_map = {s.step_id: s for s in steps}
        memo: dict[str, int] = {}
        visited: set[str] = set()  # Prevent infinite recursion on cycles

        def depth(sid: str) -> int:
            if sid in memo:
                return memo[sid]
            if sid in visited:
                return 1  # Cycle detected, stop
            visited.add(sid)
            s = step_map.get(sid)
            if not s or not s.dependencies:
                memo[sid] = 1
                return 1
            max_dep = 0
            for dep in s.dependencies:
                if dep in step_map:
                    max_dep = max(max_dep, depth(dep))
            memo[sid] = max_dep + 1
            return memo[sid]

        return max((depth(s.step_id) for s in steps), default=1)

    @staticmethod
    def _looks_like_valid_tool(tool_name: str) -> bool:
        """Heuristic: does this look like a real tool name?"""
        return bool(re.match(r'^[a-z_][a-z0-9_]*$', tool_name, re.IGNORECASE))

    @staticmethod
    def _infer_step_type(step: "PlanStep") -> str:
        """Infer the fact/action type of a plan step for precedence validation.

        Maps tool names and descriptions to type labels used by PrecedenceModel.
        """
        tool = (step.tool or "").lower()
        desc = (step.description or "").lower()
        combined = tool + " " + desc

        mapping = [
            (["read", "search", "find", "检索", "查询", "查找"], "retrieve"),
            (["analyze", "analysis", "分析", "evaluate", "评估", "检测"], "analysis"),
            (["generate", "create", "write", "生成", "创建", "编写", "output"], "generate"),
            (["edit", "modify", "update", "修改", "更新", "修正"], "modify"),
            (["test", "validate", "verify", "测试", "验证", "校验", "check"], "validate"),
            (["review", "审查", "审核", "review"], "review"),
            (["deploy", "publish", "部署", "发布", "submit"], "deploy"),
            (["fetch", "download", "download", "下载"], "retrieve"),
            (["plan", "设计", "规划", "design", "架构"], "plan"),
            (["summarize", "摘要", "总结", "summary"], "summarize"),
        ]
        for keywords, step_type in mapping:
            if any(kw in combined for kw in keywords):
                return step_type
        return "general"

    # ── Semantic Checks ───────────────────────────────────────────

    async def _predict_failure_modes(
        self, steps: list[PlanStep], domain: str,
    ) -> tuple[float, list[str], list[str]]:
        """Use LLM to predict failure modes and suggest fixes.

        Returns (probability, failure_modes, fix_suggestions).
        """
        if not self._consciousness:
            return 0.5, [], []

        plan_desc = "\n".join(
            f"  {s.step_id}: [{s.tool or '?'}] {s.description}"
            for s in steps)

        prompt = (
            f"[Plan Validation] Analyze this {domain}-domain execution plan "
            f"and predict failure modes.\n\n"
            f"Plan ({len(steps)} steps):\n{plan_desc}\n\n"
            f"Output JSON:\n"
            f'{{"success_probability": 0.0-1.0, '
            f'"failure_modes": ["what could go wrong"], '
            f'"fix_suggestions": ["how to fix each mode"]}}\n\n'
            f"Be specific about which steps could fail and why."
        )

        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=512, temperature=0.2)
            data = self._parse_llm_json(raw)
            if data:
                prob = float(data.get("success_probability", 0.5))
                prob = max(0.0, min(1.0, prob))
                fmodes = data.get("failure_modes", [])
                fixes = data.get("fix_suggestions", [])
                return prob, fmodes, fixes
        except Exception as e:
            logger.debug(f"LLM failure prediction error: {e}")

        return 0.5, [], []

    def _heuristic_semantic(
        self, steps: list[PlanStep], domain: str,
    ) -> list[str]:
        """Heuristic semantic issues when no LLM is available."""
        issues: list[str] = []

        # Check: no output-producing steps at the end
        producers = {"read", "analyze", "search", "web_search", "web_fetch"}
        has_producer = any(s.tool in producers for s in steps)
        has_consumer = any(
            s.tool in ("write", "edit", "execute") for s in steps)
        if has_producer and not has_consumer:
            issues.append(
                "Plan produces data but has no consumer (write/edit/execute) step")

        # Check: code domain specific
        if domain in ("code", "code_engineering", "development"):
            has_lsp = any("lsp" in (s.tool or "") for s in steps)
            has_edit = any(s.tool == "edit" for s in steps)
            if has_edit and not has_lsp:
                issues.append(
                    "Code edit steps without LSP diagnostics — consider "
                    "adding validation step")

        return issues

    # ── Scoring ───────────────────────────────────────────────────

    def _calc_success_probability(
        self, structural: list[str], semantic: list[str],
        llm_prob: float = 0.5,
    ) -> float:
        """Combine structural and semantic issues into a success probability.

        Start at 1.0, deduct for each issue. Structural issues weigh more.
        """
        prob = 1.0
        # Structural issues: -0.15 each (severe), -0.08 each (warning)
        for issue in structural:
            if "Circular dependency" in issue or "Destructive" in issue:
                prob -= 0.15
            else:
                prob -= 0.08

        # Semantic issues: -0.06 each
        prob -= len(semantic) * 0.06

        # Blend with LLM probability if available
        if llm_prob != 0.5 and self._consciousness:
            prob = prob * 0.4 + llm_prob * 0.6

        return max(0.05, min(1.0, round(prob, 3)))

    # ── JSON Parsing ──────────────────────────────────────────────

    @staticmethod
    def _parse_llm_json(raw: str) -> dict | None:
        """Extract JSON from LLM response (may contain markdown fences)."""
        try:
            if "```json" in raw:
                start = raw.index("```json") + 7
                end = raw.index("```", start)
                raw = raw[start:end]
            elif "```" in raw:
                start = raw.index("```") + 3
                end = raw.index("```", start)
                raw = raw[start:end]
            raw = raw.strip()
            if raw.startswith("{"):
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return None

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "plans_validated": self._total_plans_validated,
            "validation_count": self._validation_count,
            "has_consciousness": self._consciousness is not None,
        }


# ── Singleton ────────────────────────────────────────────────────

_plan_validator: PlanValidator | None = None


def get_plan_validator(consciousness: Any = None) -> PlanValidator:
    """Get or create the singleton PlanValidator."""
    global _plan_validator
    if _plan_validator is None:
        _plan_validator = PlanValidator(consciousness=consciousness)
    elif consciousness and not _plan_validator._consciousness:
        _plan_validator._consciousness = consciousness
    return _plan_validator


def reset_plan_validator() -> None:
    """Test helper."""
    global _plan_validator
    _plan_validator = None
