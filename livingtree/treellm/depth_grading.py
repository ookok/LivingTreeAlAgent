"""DepthGrading — Measure and score LLM reasoning depth.

Core value: Not all model outputs are created equal. DepthGrading quantifies
how deeply a model actually reasoned (vs. pattern-matched) by analyzing the
structural properties of its output.

Scoring dimensions (6-axis rubric):
  1. Reasoning Steps — how many explicit reasoning steps are present?
  2. Assumption Explicitness — did the model list its assumptions?
  3. Edge Case Coverage — did it identify edge cases where it fails?
  4. Self-Critique — did it reflect on its own limitations?
  5. Counterfactual Handling — did it consider alternative scenarios?
  6. Structural Depth — does the output structure suggest multi-step reasoning?

Each dimension scored 0-1. Final grade = weighted sum.

Integration:
  - Called after model output is received (post-inference)
  - Feeds into CompetitiveEliminator for Elo updates (depth-aware)
  - Used by SynapseAggregator to weight contributions by depth
  - Used by StrategicOrchestrator to assess step quality

Usage:
    grader = get_depth_grader()
    grade = grader.grade(model_output, task_type="analysis", deep_probe_result=probe)
    # grade.depth_score → 0-1 overall depth
    # grade.dimensions → per-axis breakdown
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class DepthDimension(StrEnum):
    """Six axes of reasoning depth assessment."""
    REASONING_STEPS = "reasoning_steps"           # Explicit chain-of-thought
    ASSUMPTION_EXPLICIT = "assumption_explicit"   # Listed assumptions
    EDGE_CASE_COVERAGE = "edge_case_coverage"     # Edge cases identified
    SELF_CRITIQUE = "self_critique"               # Self-reflection/criticism
    COUNTERFACTUAL = "counterfactual"             # Alternative scenarios
    STRUCTURAL_DEPTH = "structural_depth"         # Multi-level organization
    CERTAINTY = "certainty"                       # Faithful uncertainty (metacognition)
    SELF_CONSISTENCY = "self_consistency"         # Opus 4.7: internal contradiction detection


@dataclass
class DepthGrade:
    """Complete reasoning depth assessment for a model output."""
    depth_score: float                       # 0-1 overall depth
    dimensions: dict[str, float]             # Per-axis scores
    reasoning_steps_count: int               # Detected steps
    assumptions_count: int                   # Assumptions listed
    edge_cases_count: int                    # Edge cases identified
    self_critique_present: bool              # Self-reflection found
    counterfactual_present: bool             # Alternative scenarios found
    output_length: int                       # Total chars
    grade_tier: str = "shallow"              # shallow/medium/deep/profound
    flagged_as_cache_hit: bool = False       # Suspicion of cached response
    metadata: dict = field(default_factory=dict)


# ═══ DepthGrader ══════════════════════════════════════════════════

class DepthGrader:
    """Multi-dimensional reasoning depth scorer.

    Design: Uses structural heuristics (regex patterns, organization analysis)
    to assess how deeply a model reasoned. This is fast (no LLM call required)
    and objective (same output always gets same score).

    Dimension weights:
      - REASONING_STEPS: 0.25 (most important — explicit chain-of-thought)
      - ASSUMPTION_EXPLICIT: 0.15
      - EDGE_CASE_COVERAGE: 0.15
      - SELF_CRITIQUE: 0.15
      - COUNTERFACTUAL: 0.10
      - STRUCTURAL_DEPTH: 0.10
      - ANTI_CACHE: 0.10 (bonus for uniqueness signals)
    """

    DIMENSION_WEIGHTS = {
        DepthDimension.REASONING_STEPS: 0.18,
        DepthDimension.ASSUMPTION_EXPLICIT: 0.13,
        DepthDimension.EDGE_CASE_COVERAGE: 0.13,
        DepthDimension.SELF_CRITIQUE: 0.13,
        DepthDimension.COUNTERFACTUAL: 0.12,
        DepthDimension.STRUCTURAL_DEPTH: 0.08,
        DepthDimension.CERTAINTY: 0.11,
        DepthDimension.SELF_CONSISTENCY: 0.12,
    }

    TIER_THRESHOLDS = {
        "shallow": 0.0,
        "medium": 0.30,
        "deep": 0.55,
        "profound": 0.80,
    }

    # ── Code Quality Grading ──────────────────────────────────────

    def grade_code(self, output: str) -> DepthGrade:
        """Code-specific quality grading.

        Evaluates: code blocks present, syntax structure, error handling,
        comments/documentation, edge case handling.
        """
        if not output or len(output) < 20:
            return DepthGrade(depth_score=0.0, dimensions={}, reasoning_steps_count=0,
                             assumptions_count=0, edge_cases_count=0,
                             self_critique_present=False, counterfactual_present=False,
                             output_length=len(output or ""), grade_tier="shallow")

        dims: dict[str, float] = {}

        # Code blocks: triple-backtick sections
        code_blocks = len(re.findall(r'```', output)) // 2
        dims["code_blocks"] = min(1.0, code_blocks / 3.0)

        # Function/class definitions
        defs = len(re.findall(r'(def |class |function |async def |public class )', output))
        dims["definitions"] = min(1.0, defs / 3.0)

        # Error handling
        error_patterns = [r'try', r'except', r'catch', r'error', r'raise', r'throw']
        error_count = sum(len(re.findall(p, output, re.IGNORECASE)) for p in error_patterns)
        dims["error_handling"] = min(1.0, error_count / 2.0)

        # Comments
        comments = len(re.findall(r'#|//|/\*\*', output))
        dims["comments"] = min(1.0, comments / 3.0)

        # Tests/edge cases
        test_patterns = [r'test', r'assert', r'edge case', r'boundary', r'example']
        test_count = sum(len(re.findall(p, output, re.IGNORECASE)) for p in test_patterns)
        dims["edge_handling"] = min(1.0, test_count / 2.0)

        weight_map = {"code_blocks": 0.3, "definitions": 0.25,
                      "error_handling": 0.2, "comments": 0.1, "edge_handling": 0.15}
        depth = sum(weight_map.get(k, 0.1) * v for k, v in dims.items())

        tier = "shallow"
        for t, threshold in sorted(self.TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if depth >= threshold:
                tier = t; break

        return DepthGrade(
            depth_score=round(depth, 4), dimensions={k: round(v, 4) for k, v in dims.items()},
            reasoning_steps_count=defs + code_blocks, assumptions_count=0,
            edge_cases_count=test_count, self_critique_present=error_count > 0,
            counterfactual_present=False, output_length=len(output),
            grade_tier=tier, metadata={"task_type": "code"},
        )

    # ── Main Grading Pipeline ──────────────────────────────────────

    def grade(
        self, output: str, task_type: str = "general",
        deep_probe_result: Any = None, self_play_result: Any = None,
    ) -> DepthGrade:
        """Grade the reasoning depth of a model output.

        Args:
            output: Model output text to grade.
            task_type: Task category for weight adjustments.
            deep_probe_result: Optional ProbeResult for context.
            self_play_result: Optional SelfPlayResult for bonus.

        Returns:
            DepthGrade with full scoring breakdown.
        """
        if not output or len(output) < 20:
            return DepthGrade(
                depth_score=0.0,
                dimensions={d: 0.0 for d in self.DIMENSION_WEIGHTS},
                reasoning_steps_count=0,
                assumptions_count=0,
                edge_cases_count=0,
                self_critique_present=False,
                counterfactual_present=False,
                output_length=len(output or ""),
                grade_tier="shallow",
            )

        # Score each dimension
        dims: dict[str, float] = {}
        steps_count = self._count_reasoning_steps(output)
        dims["reasoning_steps"] = self._score_reasoning_steps(steps_count, task_type)

        assumptions = self._detect_assumptions(output)
        dims["assumption_explicit"] = self._score_assumptions(assumptions)

        edge_cases = self._detect_edge_cases(output)
        dims["edge_case_coverage"] = self._score_edge_cases(edge_cases)

        has_self_critique = self._detect_self_critique(output)
        dims["self_critique"] = 1.0 if has_self_critique else 0.0

        has_counterfactual = self._detect_counterfactual(output)
        dims["counterfactual"] = 1.0 if has_counterfactual else 0.0

        struct_score = self._score_structural_depth(output)
        dims["structural_depth"] = struct_score

        # ── Metacognitive certainty (Yona et al., ICML 2026) ──
        certainty = self._score_certainty(output)
        dims["certainty"] = certainty

        # ── Opus 4.7 Self-Verify: internal consistency ──
        consistency = self._score_consistency(output)
        dims["self_consistency"] = consistency

        # Weighted sum (use full dimension keys)
        weight_map = {
            "reasoning_steps": 0.18,
            "assumption_explicit": 0.13,
            "edge_case_coverage": 0.13,
            "self_critique": 0.13,
            "counterfactual": 0.10,
            "structural_depth": 0.08,
            "certainty": 0.13,
            "self_consistency": 0.12,
        }
        depth = sum(weight_map.get(k, 0.1) * v for k, v in dims.items())

        # Self-play bonus: successful revision rounds add depth
        if self_play_result:
            try:
                depth += min(0.15, len(self_play_result.rounds) * 0.05)
            except Exception:
                pass

        # Cache-hit suspicion: very short + generic + no steps
        flagged_cache = (
            len(output) < 100
            and steps_count < 2
            and dims["self_critique"] < 0.5
        )

        # Determine tier
        tier = "shallow"
        for t, threshold in sorted(
            self.TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True,
        ):
            if depth >= threshold:
                tier = t
                break

        logger.debug(
            f"DepthGrading: tier={tier} score={depth:.2f} "
            f"steps={steps_count} assumptions={len(assumptions)} "
            f"edges={len(edge_cases)} critique={has_self_critique}"
        )

        return DepthGrade(
            depth_score=round(depth, 4),
            dimensions={k: round(v, 4) for k, v in dims.items()},
            reasoning_steps_count=steps_count,
            assumptions_count=len(assumptions),
            edge_cases_count=len(edge_cases),
            self_critique_present=has_self_critique,
            counterfactual_present=has_counterfactual,
            output_length=len(output),
            grade_tier=tier,
            flagged_as_cache_hit=flagged_cache,
            metadata={
                "task_type": task_type,
                "deep_probe": bool(deep_probe_result),
                "self_play_rounds": (
                    len(self_play_result.rounds) if self_play_result else 0
                ),
            },
        )

    # ── Dimension Scorers ─────────────────────────────────────────

    @staticmethod
    def _count_reasoning_steps(output: str) -> int:
        """Count explicit reasoning steps in the output."""
        count = 0
        # Numbered steps: "Step 1:", "1.", "第1步："
        count += len(re.findall(
            r'(?:Step\s*\d|第\s*\d+\s*步|^\d+[\.\)]\s)',
            output, re.IGNORECASE | re.MULTILINE,
        ))
        # Phase indicators
        count += len(re.findall(
            r'(?:首先|然后|接着|最后|第一步|第二步|First|Then|Next|Finally|Phase\s*\d)',
            output, re.IGNORECASE,
        ))
        # Reasoning connectors (sequential logic)
        count += len(re.findall(
            r'(?:Therefore|Thus|Hence|Because|Since|Consequently|因此|所以|因为|由于|综上所述)',
            output, re.IGNORECASE,
        ))
        return max(1, count)  # At least 1 step

    @staticmethod
    def _score_reasoning_steps(step_count: int, task_type: str) -> float:
        """Score reasoning steps on 0-1 scale."""
        thresholds = {
            "analysis": (2, 5, 8),    # (min for 0.3, medium for 0.6, full for 0.9)
            "code": (2, 4, 7),
            "decision": (3, 6, 10),
            "creative": (1, 3, 5),
            "general": (1, 3, 5),
        }
        lo, mid, hi = thresholds.get(task_type, thresholds["general"])
        if step_count >= hi:
            return 1.0
        if step_count >= mid:
            return 0.6 + 0.4 * (step_count - mid) / max(hi - mid, 1)
        if step_count >= lo:
            return 0.3 + 0.3 * (step_count - lo) / max(mid - lo, 1)
        return 0.3 * step_count / max(lo, 1)

    @staticmethod
    def _detect_assumptions(output: str) -> list[str]:
        """Detect explicitly listed assumptions in the output."""
        # Look for assumption indicators
        patterns = [
            r'(?:assum|假设|前提|假定|预设)\w*',
            r'(?:we assume|I assume|assuming that)',
            r'(?:assumption\s*\d|假设\s*\d|前提\s*\d)',
        ]
        matches: list[str] = []
        for pat in patterns:
            found = re.findall(pat, output, re.IGNORECASE)
            matches.extend(found)

        # Count sections with assumption-like headings
        section_matches = re.findall(
            r'(?:Assumptions?|Key Assumptions?|假设|前提条件|Hidden Assumptions?)',
            output, re.IGNORECASE,
        )
        return list(set(matches)) + section_matches

    @staticmethod
    def _score_assumptions(assumptions: list[str]) -> float:
        """Score assumption explicitness."""
        count = len(assumptions)
        if count >= 5:
            return 1.0
        if count >= 3:
            return 0.7
        if count >= 1:
            return 0.4
        return 0.0

    @staticmethod
    def _detect_edge_cases(output: str) -> list[str]:
        """Detect edge case identification in the output."""
        patterns = [
            r'(?:edge\s*case|边缘\s*场景|边界\s*情况|corner\s*case)',
            r'(?:would\s*fail|doesn\'t\s*work|breaks\s*down|失效|不适用)',
            r'(?:limitation|限制|局限|caveat|注意事项)',
            r'(?:exception|例外|特殊\s*情况)',
        ]
        matches = []
        for pat in patterns:
            found = re.findall(pat, output, re.IGNORECASE)
            matches.extend(found)
        return list(set(matches))

    @staticmethod
    def _score_edge_cases(edge_cases: list[str]) -> float:
        """Score edge case coverage."""
        count = len(edge_cases)
        if count >= 4:
            return 1.0
        if count >= 2:
            return 0.6
        if count >= 1:
            return 0.3
        return 0.0

    @staticmethod
    def _detect_self_critique(output: str) -> bool:
        """Detect if the output contains self-critique or reflection."""
        indicators = [
            r'(?:however|然而|但是|不过|on the other hand)',
            r'(?:admit|承认|I was wrong|我的错误|不足之处)',
            r'(?:could be improved|可以改进|insufficient|不足|不够)',
            r'(?:alternative|alternative|另一种|Alternatively)',
            r'(?:this analysis is limited|这个分析有局限|不完全|不完整)',
            r'(?:further research|进一步研究|需要更多|需要进一步)',
            r'(?:my analysis misses|我忽略了|missing|遗漏)',
        ]
        return any(
            re.search(pat, output, re.IGNORECASE) for pat in indicators
        )

    @staticmethod
    def _detect_counterfactual(output: str) -> bool:
        """Detect if output considers counterfactual scenarios."""
        indicators = [
            r'(?:what if|如果|假如|假设|suppose|imagine)',
            r'(?:if.*were\s*different|if.*changed|如果.*改变)',
            r'(?:under\s*different\s*conditions?|在.*不同.*条件)',
            r'(?:had\s*it\s*been|如果是|should\s*it\s*be)',
            r'(?:would\s*still\s*hold|仍然成立|依然有效|不变)',
            r'(?:fragile|脆弱|robust|稳健|robustness)',
        ]
        return any(
            re.search(pat, output, re.IGNORECASE) for pat in indicators
        )

    @staticmethod
    def _score_structural_depth(output: str) -> float:
        """Score output's structural organization depth."""
        score = 0.0

        # Multi-level headings
        h2 = len(re.findall(r'^##\s', output, re.MULTILINE))
        h3 = len(re.findall(r'^###\s', output, re.MULTILINE))
        if h2 >= 3 and h3 >= 2:
            score += 0.4
        elif h2 >= 2:
            score += 0.2

        # Bullet points (structured listing)
        bullets = len(re.findall(r'^\s*[-*•]\s', output, re.MULTILINE))
        if bullets >= 8:
            score += 0.3
        elif bullets >= 4:
            score += 0.15

        # Paragraph grouping (3+ paragraphs with >100 chars each)
        paragraphs = [p.strip() for p in output.split("\n\n") if len(p.strip()) > 100]
        if len(paragraphs) >= 4:
            score += 0.3
        elif len(paragraphs) >= 2:
            score += 0.15

        return min(1.0, score)

    # ── Opus 4.7 Self-Verify: Internal Consistency Scoring ─────────

    @staticmethod
    def _score_consistency(output: str) -> float:
        """Opus 4.7 SELF_CONSISTENCY: detect internal contradictions.

        Extracts claim-level assertions and checks for contradictory
        pairs using negation asymmetry and semantic opposition markers.
        High score → claims are internally coherent.
        Low score → potential logical breaks within the output.
        """
        sentences = re.split(r'(?<=[.!?。！？])\s+', output)
        claims = [s.strip().lower() for s in sentences if len(s.strip()) > 20]
        if len(claims) < 2:
            return 0.5

        neg_words = {"not", "no", "never", "don't", "doesn't", "isn't", "aren't",
                      "won't", "can't", "cannot", "不", "没有", "不是", "无", "非"}
        opposition_markers = {
            ("increase", "decrease"), ("high", "low"), ("fast", "slow"),
            ("success", "failure"), ("correct", "wrong"), ("true", "false"),
            ("支持", "反对"), ("上升", "下降"), ("成功", "失败"),
        }

        contradiction_count = 0
        for i in range(len(claims)):
            for j in range(i + 1, min(i + 6, len(claims))):
                a_words = set(claims[i].split())
                b_words = set(claims[j].split())
                overlap = len(a_words & b_words) / max(len(a_words | b_words), 1)
                if overlap < 0.35:
                    continue

                has_neg_a = bool(a_words & neg_words)
                has_neg_b = bool(b_words & neg_words)
                if has_neg_a != has_neg_b:
                    contradiction_count += 1
                    continue

                for op_a, op_b in opposition_markers:
                    if op_a in a_words and op_b in b_words:
                        contradiction_count += 1
                        break

        if contradiction_count == 0:
            return 1.0
        if contradiction_count <= 2:
            return 0.7
        if contradiction_count <= 4:
            return 0.4
        return 0.1

    # ── Batch & Comparison ────────────────────────────────────────

    def compare_models(
        self, outputs: dict[str, str], task_type: str = "general",
    ) -> dict[str, DepthGrade]:
        """Grade multiple model outputs and rank by depth."""
        grades = {
            name: self.grade(text, task_type)
            for name, text in outputs.items()
        }
        return dict(
            sorted(grades.items(), key=lambda x: -x[1].depth_score)
        )

    # ── Insights for CompetitiveEliminator ─────────────────────────

    def elo_adjustment(self, grade: DepthGrade) -> float:
        """Compute Elo adjustment from depth grade for CompetitiveEliminator.

        Deep reasoning outputs should boost Elo more than shallow ones.
        """
        tier_multipliers = {
            "profound": 1.5,
            "deep": 1.2,
            "medium": 1.0,
            "shallow": 0.7,
        }
        multiplier = tier_multipliers.get(grade.grade_tier, 1.0)
        return round(grade.depth_score * multiplier, 2)

    def should_retry_with_deeper_probe(self, grade: DepthGrade) -> bool:
        """Determine if output is too shallow and needs DeepProbe re-attempt."""
        return (
            grade.grade_tier == "shallow"
            and grade.reasoning_steps_count < 2
            and grade.output_length > 50
        )

    # ── Metacognitive Certainty (Yona et al., ICML 2026) ──────────

    @staticmethod
    def _score_certainty(output: str) -> float:
        """Score 'faithful uncertainty' — does the model honestly express doubt?

        From Yona et al.: 'faithful uncertainty: aligning linguistic uncertainty
        with intrinsic uncertainty.' Models that express appropriate doubt score
        HIGHER than models that are confidently wrong or vaguely evasive.

        Positive markers (honest uncertainty):
          - "I'm not sure" / "不确定" / "unclear" / "may be" / "可能"
          - "depends on" / "取决于" / "varies" / "it could be"
          - "further research needed" / "需要更多"
          - Numerical ranges with qualifiers ("approximately", "around")

        Negative markers (overconfident):
          - Absolute statements without qualifiers ("always", "never", "definitely")
          - "obviously" / "显然" / "clearly"
        """
        score = 0.3  # baseline
        low = output.lower()

        # Honest uncertainty signals
        honest = [
            r"i('m|\s+am)\s+not\s+sure", r"不确定", r"unclear", r"may\s+be",
            r"可能", r"或许", r"depends?\s+on", r"取决于", r"varies",
            r"further\s+research", r"需要更多", r"approximately",
            r"around\s+\d", r"大概", r"大约", r"范围",
            r"it\s+could\s+be", r"might\s+be", r"possible",
        ]
        honest_count = sum(1 for p in honest if re.search(p, low))
        score += min(0.4, honest_count * 0.08)

        # Overconfidence penalty
        overconfident = [
            r"\balways\b", r"\bnever\b", r"\bdefinitely\b", r"\babsolutely\b",
            r"\bobviously\b", r"显然", r"\bclearly\b", r"\bcertainly\b",
        ]
        over_count = sum(1 for p in overconfident if re.search(p, low))
        score -= min(0.3, over_count * 0.05)

        # Confidence qualifiers in proximity to claims
        claims_with_hedging = len(re.findall(
            r'(?:我认为|I think|据我所知|as far as I know|probably|probably|likely|likely|往往)',
            low
        ))
        score += min(0.2, claims_with_hedging * 0.05)

        return max(0.0, min(1.0, score))

    def stats(self) -> dict:
        return {
            "dimensions": list(self.DIMENSION_WEIGHTS.keys()),
            "tier_thresholds": self.TIER_THRESHOLDS,
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_grader: Optional[DepthGrader] = None


def get_depth_grader() -> DepthGrader:
    global _grader
    if _grader is None:
        _grader = DepthGrader()
    return _grader


__all__ = [
    "DepthGrader", "DepthGrade", "DepthDimension",
    "get_depth_grader",
]
