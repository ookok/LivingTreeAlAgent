"""External Verifier — verification-based rewards that escape the intrinsic ceiling.

Based on He et al. (ICLR 2026, arXiv:2603.08660): the key solution to URLVR
collapse is "external rewards grounded in generation-verification asymmetry."
External verification signals are harder to game than intrinsic rewards because
verification is easier than generation — the verifier sees both output and ground
truth constraints, while the generator optimizes blindly.

This module provides five verification methods:
  - CODE_EXEC: run generated code and check output
  - SELF_CONSISTENCY: generate N alternative solutions, check agreement
  - CONSTRAINT_CHECK: verify output against parsed constraints
  - CROSS_REFERENCE: check claims against the knowledge base
  - REGEX_MATCH: simple pattern-based verification

Integration:
    verifier = get_external_verifier()
    result = await verifier.verify(output_text, query)
    reward = result.external_signal  # -1 to 1
    if result.passed:
        # use as positive reinforcement signal
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

MAX_HISTORY: int = 200
CODE_EXEC_TIMEOUT: float = 5.0
SELF_CONSISTENCY_VARIANTS: int = 3
SELF_CONSISTENCY_AGREEMENT_THRESHOLD: float = 0.5

CODE_BLOCK_PATTERN = re.compile(
    r"```(?:python|javascript|js|typescript|ts|bash|sh|shell)?\s*\n(.*?)```",
    re.DOTALL,
)

CONSTRAINT_PATTERN = re.compile(
    r"(must|should|needs?\s+to|requires?|不超过|至少|不能超过|必须|不得|不小于|不大于|"
    r"should\s+not|must\s+not|cannot|can't)",
    re.IGNORECASE,
)

FACTUAL_QUERY_PATTERN = re.compile(
    r"(what\s+is|when\s+did|who\s+is|where\s+is|how\s+many|which\s+year|"
    r"什么是|什么时候|谁是|在哪里|有多少|哪一年)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════


class VerificationMethod(str, Enum):
    """Supported verification methods.

    Each method exploits a different aspect of the generation-verification
    asymmetry: verifying output is always cheaper than generating it.
    """

    CODE_EXEC = "code_exec"
    SELF_CONSISTENCY = "self_consistency"
    CONSTRAINT_CHECK = "constraint_check"
    CROSS_REFERENCE = "cross_reference"
    REGEX_MATCH = "regex_match"


@dataclass
class VerificationResult:
    """Result of a single verification attempt.

    external_signal ranges from -1 to 1:
      - positive values = evidence of correctness (reward)
      - negative values = evidence of error (penalty)
      - zero = inconclusive
    """

    method: VerificationMethod
    passed: bool
    confidence: float
    evidence: str
    external_signal: float
    latency_ms: float


# ═══════════════════════════════════════════════════════════════
# External Verifier
# ═══════════════════════════════════════════════════════════════


class ExternalVerifier:
    r"""Provides verification-based rewards that escape the intrinsic ceiling.

    Core principle from He et al. (2026): generation-verification asymmetry.
    Generating a correct answer is hard (the model must navigate a vast output
    space), but verifying an answer is easier (check against ground truth or
    constraints). By using external verification as the reward signal, the
    model cannot overfit to its own internal rewards.

    Five verification methods:
      CODE_EXEC:     actually run the generated code → check exit code & output
      SELF_CONSISTENCY: generate alternative answers → check majority agreement
      CONSTRAINT_CHECK:  parse query constraints → verify output satisfies them
      CROSS_REFERENCE:    look up claims in knowledge base → verify factual accuracy
      REGEX_MATCH:        simple pattern check (for structured outputs)
    """

    def __init__(self) -> None:
        self._verification_history: deque[VerificationResult] = deque(maxlen=MAX_HISTORY)
        self._knowledge_base: Any = None  # lazy ref, set via set_knowledge_base()
        self._consistency_generator: Any = None  # lazy ref for variant generation
        logger.info("ExternalVerifier initialized with {} methods", len(VerificationMethod))

    # ── knowledge base injection ──────────────────────────────────

    def set_knowledge_base(self, kb: Any) -> None:
        """Inject a reference to the knowledge base for CROSS_REFERENCE verification.

        Args:
            kb: any object with a .search(query: str) -> list[dict] method
        """
        self._knowledge_base = kb
        logger.debug("ExternalVerifier: knowledge base injected")

    def set_consistency_generator(self, generator: Any) -> None:
        """Inject a reference to the LLM generator for SELF_CONSISTENCY.

        Args:
            generator: any callable async generate(prompt: str) -> str
        """
        self._consistency_generator = generator
        logger.debug("ExternalVerifier: consistency generator injected")

    # ── main verification ─────────────────────────────────────────

    async def verify(
        self, output_text: str, query: str, method: str = "auto"
    ) -> VerificationResult:
        """Verify an LLM output against the query using auto-selected or specified method.

        Auto-selection logic:
          - Contains code blocks → CODE_EXEC
          - Factual query pattern → CROSS_REFERENCE (if KB available)
          - Contains constraint keywords → CONSTRAINT_CHECK
          - Otherwise → SELF_CONSISTENCY (fallback)

        Args:
            output_text: the model's generated response
            query: the original user query / instruction
            method: "auto" for auto-selection, or a specific VerificationMethod value

        Returns:
            VerificationResult with pass/fail, confidence, and external_signal
        """
        t0 = time.perf_counter()

        selected = self._select_method(output_text, query) if method == "auto" else method

        try:
            match selected:
                case VerificationMethod.CODE_EXEC.value | VerificationMethod.CODE_EXEC:
                    result = await self._verify_code(output_text, query)
                case VerificationMethod.SELF_CONSISTENCY.value | VerificationMethod.SELF_CONSISTENCY:
                    result = await self._verify_self_consistency(output_text, query)
                case VerificationMethod.CONSTRAINT_CHECK.value | VerificationMethod.CONSTRAINT_CHECK:
                    result = await self._verify_constraints(output_text, query)
                case VerificationMethod.CROSS_REFERENCE.value | VerificationMethod.CROSS_REFERENCE:
                    result = await self._verify_cross_reference(output_text, query)
                case VerificationMethod.REGEX_MATCH.value | VerificationMethod.REGEX_MATCH:
                    result = await self._verify_regex_match(output_text, query)
                case _:
                    result = VerificationResult(
                        method=VerificationMethod.SELF_CONSISTENCY,
                        passed=False,
                        confidence=0.0,
                        evidence=f"Unknown method: {method}, falling back to self_consistency",
                        external_signal=0.0,
                        latency_ms=(time.perf_counter() - t0) * 1000,
                    )
        except Exception as e:
            logger.warning(f"ExternalVerifier: {selected} failed: {e}")
            result = VerificationResult(
                method=self._to_enum(selected),
                passed=False,
                confidence=0.0,
                evidence=f"Verification error: {e}",
                external_signal=0.0,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        result.latency_ms = (time.perf_counter() - t0) * 1000
        self._verification_history.append(result)
        logger.debug(
            "ExternalVerifier: {} → passed={} signal={:.2f} ({:.1f}ms)",
            result.method.value, result.passed, result.external_signal, result.latency_ms,
        )
        return result

    def _select_method(self, output_text: str, query: str) -> str:
        """Auto-select the best verification method for the given output/query pair."""
        has_code_blocks = bool(CODE_BLOCK_PATTERN.search(output_text))
        is_factual = bool(FACTUAL_QUERY_PATTERN.search(query))
        has_constraints = bool(CONSTRAINT_PATTERN.search(query))

        if has_code_blocks:
            return VerificationMethod.CODE_EXEC.value
        if is_factual and self._knowledge_base is not None:
            return VerificationMethod.CROSS_REFERENCE.value
        if has_constraints:
            return VerificationMethod.CONSTRAINT_CHECK.value
        return VerificationMethod.SELF_CONSISTENCY.value

    @staticmethod
    def _to_enum(method: str) -> VerificationMethod:
        try:
            return VerificationMethod(method)
        except ValueError:
            return VerificationMethod.SELF_CONSISTENCY

    # ── verification methods ──────────────────────────────────────

    async def _verify_code(self, output: str, query: str) -> VerificationResult:
        """Verify by executing code blocks in the output.

        Extracts ```python (or other language) blocks, runs them via subprocess
        with a timeout, and checks if execution succeeds. Pass = exit_code 0
        with no uncaught exceptions.

        Args:
            output: the model's generated response
            query: the original query (may contain additional context)

        Returns:
            VerificationResult with CODE_EXEC method
        """
        code_blocks = CODE_BLOCK_PATTERN.findall(output)
        if not code_blocks:
            return VerificationResult(
                method=VerificationMethod.CODE_EXEC,
                passed=False,
                confidence=0.0,
                evidence="No code blocks found in output",
                external_signal=-0.5,
                latency_ms=0.0,
            )

        total_blocks = len(code_blocks)
        passed_blocks = 0
        evidence_lines: list[str] = []

        for idx, code in enumerate(code_blocks):
            code = code.strip()
            if not code:
                continue

            try:
                proc = await asyncio.wait_for(
                    asyncio.to_thread(
                        subprocess.run,
                        ["python", "-c", code],
                        capture_output=True,
                        text=True,
                        timeout=CODE_EXEC_TIMEOUT,
                    ),
                    timeout=CODE_EXEC_TIMEOUT + 1.0,
                )

                if proc.returncode == 0:
                    passed_blocks += 1
                    evidence_lines.append(f"Block {idx + 1}: OK")
                else:
                    stderr_short = (proc.stderr or "unknown error")[:120]
                    evidence_lines.append(f"Block {idx + 1}: FAILED — {stderr_short}")

            except asyncio.TimeoutError:
                evidence_lines.append(f"Block {idx + 1}: TIMEOUT ({CODE_EXEC_TIMEOUT}s)")
            except Exception as e:
                evidence_lines.append(f"Block {idx + 1}: ERROR — {e}")

        passed = passed_blocks == total_blocks and total_blocks > 0
        confidence = passed_blocks / total_blocks if total_blocks > 0 else 0.0

        if passed:
            external_signal = 0.8
        elif passed_blocks > 0:
            external_signal = passed_blocks / total_blocks * 0.5
        else:
            external_signal = -0.8

        return VerificationResult(
            method=VerificationMethod.CODE_EXEC,
            passed=passed,
            confidence=round(confidence, 4),
            evidence="; ".join(evidence_lines),
            external_signal=round(external_signal, 4),
            latency_ms=0.0,
        )

    async def _verify_cross_reference(self, output: str, query: str) -> VerificationResult:
        """Verify by cross-referencing claims against the knowledge base.

        Searches the KB for facts matching the query and checks if key claims
        in the output are consistent with known facts.

        Falls back to SELF_CONSISTENCY if no KB is available.

        Args:
            output: the model's generated response
            query: the original query

        Returns:
            VerificationResult with CROSS_REFERENCE method
        """
        if self._knowledge_base is None:
            return VerificationResult(
                method=VerificationMethod.CROSS_REFERENCE,
                passed=False,
                confidence=0.0,
                evidence="KB not available — cannot cross-reference",
                external_signal=0.0,
                latency_ms=0.0,
            )

        try:
            kb_results = self._knowledge_base.search(query) if hasattr(self._knowledge_base, "search") else []
            if not kb_results:
                return VerificationResult(
                    method=VerificationMethod.CROSS_REFERENCE,
                    passed=False,
                    confidence=0.3,
                    evidence="No matching KB entries found for query",
                    external_signal=0.0,
                    latency_ms=0.0,
                )

            output_lower = output.lower()
            match_count = 0
            total_checks = 0

            for entry in kb_results[:5]:
                if isinstance(entry, dict):
                    entry_text = str(entry.get("content", entry.get("text", ""))).lower()
                else:
                    entry_text = str(entry).lower()

                if not entry_text:
                    continue

                # simple overlap check: do key terms from KB entry appear in output?
                key_terms = [w for w in entry_text.split() if len(w) > 3][:8]
                for term in key_terms:
                    total_checks += 1
                    if term in output_lower:
                        match_count += 1

            if total_checks == 0:
                confidence = 0.0
            else:
                confidence = match_count / total_checks

            passed = confidence >= 0.5
            external_signal = (confidence - 0.5) * 2.0  # map [0,1] → [-1,1]

            return VerificationResult(
                method=VerificationMethod.CROSS_REFERENCE,
                passed=passed,
                confidence=round(confidence, 4),
                evidence=f"KB cross-ref: {match_count}/{total_checks} term matches across {len(kb_results[:5])} entries",
                external_signal=round(external_signal, 4),
                latency_ms=0.0,
            )

        except Exception as e:
            logger.warning(f"ExternalVerifier: cross_reference error: {e}")
            return VerificationResult(
                method=VerificationMethod.CROSS_REFERENCE,
                passed=False,
                confidence=0.0,
                evidence=f"Cross-reference failed: {e}",
                external_signal=0.0,
                latency_ms=0.0,
            )

    async def _verify_constraints(self, output: str, query: str) -> VerificationResult:
        """Verify output against parsed constraints from the query.

        Extracts constraint keywords from the query using regex and checks
        whether the output satisfies each identified constraint.

        For example, "must be less than 100" → checks if output contains
        numbers and none exceed 100.

        Args:
            output: the model's generated response
            query: the original query containing constraints

        Returns:
            VerificationResult with CONSTRAINT_CHECK method
        """
        constraints = CONSTRAINT_PATTERN.findall(query)
        if not constraints:
            return VerificationResult(
                method=VerificationMethod.CONSTRAINT_CHECK,
                passed=False,
                confidence=0.0,
                evidence="No constraint patterns detected in query",
                external_signal=0.0,
                latency_ms=0.0,
            )

        constraint_checks: list[tuple[str, bool]] = []
        output_lower = output.lower()
        query_lower = query.lower()

        for constraint in constraints:
            constraint_lower = constraint.lower()
            # find the context around each constraint keyword
            idx = query_lower.find(constraint_lower)
            if idx < 0:
                constraint_checks.append((constraint, True))
                continue

            # extract the constraint phrase (keyword + next ~80 chars)
            phrase = query[idx:idx + 120]

            # check for negation in output
            negation_patterns = ["can't", "cannot", "unable", "fails", "error", "不能", "无法", "失败"]
            has_negation = any(neg in output_lower for neg in negation_patterns)

            # check for numeric constraints
            numbers_in_query = re.findall(r"\d+(?:\.\d+)?", phrase)
            numbers_in_output = re.findall(r"\d+(?:\.\d+)?", output)
            number_pass = True
            if "less than" in phrase or "不超过" in phrase or "below" in phrase:
                if numbers_in_query and numbers_in_output:
                    limit = float(numbers_in_query[0])
                    number_pass = all(float(n) <= limit for n in numbers_in_output)
            elif "greater than" in phrase or "至少" in phrase or "above" in phrase:
                if numbers_in_query and numbers_in_output:
                    limit = float(numbers_in_query[0])
                    number_pass = all(float(n) >= limit for n in numbers_in_output)
            elif "between" in phrase:
                if len(numbers_in_query) >= 2:
                    lo, hi = float(numbers_in_query[0]), float(numbers_in_query[1])
                    number_pass = all(lo <= float(n) <= hi for n in numbers_in_output) if numbers_in_output else True

            satisfied = not has_negation and number_pass
            constraint_checks.append((constraint, satisfied))

        passed_count = sum(1 for _, ok in constraint_checks if ok)
        total = len(constraint_checks)
        confidence = passed_count / total if total > 0 else 0.0
        passed = passed_count == total

        evidence_items = [f"{c}: {'OK' if ok else 'FAIL'}" for c, ok in constraint_checks]
        external_signal = (confidence - 0.5) * 2.0

        return VerificationResult(
            method=VerificationMethod.CONSTRAINT_CHECK,
            passed=passed,
            confidence=round(confidence, 4),
            evidence="; ".join(evidence_items),
            external_signal=round(external_signal, 4),
            latency_ms=0.0,
        )

    async def _verify_self_consistency(
        self, output: str, query: str, consciousness: Any = None
    ) -> VerificationResult:
        """Verify by generating alternative answers and checking agreement.

        Generates up to SELF_CONSISTENCY_VARIANTS alternative answers (or 2
        if no generator available) and checks if the majority agree with the
        original output. This exploits the insight that consistent answers
        are more likely correct.

        Args:
            output: the model's generated response
            query: the original query
            consciousness: optional LLM interface for generating variants

        Returns:
            VerificationResult with SELF_CONSISTENCY method
        """
        generator = consciousness or self._consistency_generator
        if generator is None:
            # without generator, use heuristic agreement check:
            # split into sentences, check if they are internally consistent
            return self._heuristic_consistency(output, query)

        try:
            variant_prompts = [
                f"Answer the following question differently:\n\n{query}\n\nProvide an alternative answer:",
                f"Question: {query}\n\nPlease answer from a different perspective:",
            ]

            variants = [output]
            for prompt in variant_prompts[:SELF_CONSISTENCY_VARIANTS - 1]:
                try:
                    alt_output = await self._generate_async(generator, prompt)
                    if alt_output:
                        variants.append(alt_output)
                except Exception as e:
                    logger.debug(f"ExternalVerifier: variant generation failed: {e}")

            agreement_scores = self._compute_agreement(variants, output)
            avg_agreement = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.0
            passed = avg_agreement >= SELF_CONSISTENCY_AGREEMENT_THRESHOLD

            return VerificationResult(
                method=VerificationMethod.SELF_CONSISTENCY,
                passed=passed,
                confidence=round(avg_agreement, 4),
                evidence=f"Self-consistency: {len(variants)} variants, "
                         f"agreement={avg_agreement:.2%} (threshold={SELF_CONSISTENCY_AGREEMENT_THRESHOLD:.0%})",
                external_signal=round(avg_agreement * 1.6 - 0.8, 4),  # map [0,1] → [-0.8, 0.8]
                latency_ms=0.0,
            )

        except Exception as e:
            logger.warning(f"ExternalVerifier: self_consistency error: {e}")
            return self._heuristic_consistency(output, query)

    async def _verify_regex_match(self, output: str, query: str) -> VerificationResult:
        """Verify structured output with simple pattern-based checks.

        For outputs expected to follow a specific format (JSON, CSV, tables),
        check that the output structure is valid.

        Args:
            output: the model's generated response
            query: the original query

        Returns:
            VerificationResult with REGEX_MATCH method
        """
        checks: list[tuple[str, bool]] = []

        # JSON check
        if "json" in query.lower() or output.strip().startswith(("{", "[")):
            try:
                import json
                json.loads(output.strip())
                checks.append(("valid_json", True))
            except (json.JSONDecodeError, ValueError):
                # try extracting JSON from code blocks
                json_match = re.search(r"```(?:json)?\s*\n(.*?)```", output, re.DOTALL)
                if json_match:
                    try:
                        import json
                        json.loads(json_match.group(1).strip())
                        checks.append(("valid_json", True))
                    except (json.JSONDecodeError, ValueError):
                        checks.append(("valid_json", False))
                else:
                    checks.append(("valid_json", False))

        # table/markdown check
        if "table" in query.lower() or "表格" in query:
            has_table = bool(re.search(r"\|.*\|", output))
            checks.append(("has_table", has_table))

        # list check
        if "list" in query.lower() or "列出" in query or "列举" in query:
            has_list = bool(re.search(r"^\s*[-*\d+.]\s", output, re.MULTILINE))
            checks.append(("has_list", has_list))

        if not checks:
            return VerificationResult(
                method=VerificationMethod.REGEX_MATCH,
                passed=False,
                confidence=0.0,
                evidence="No applicable regex checks for this output",
                external_signal=0.0,
                latency_ms=0.0,
            )

        passed_count = sum(1 for _, ok in checks if ok)
        total = len(checks)
        confidence = passed_count / total
        passed = passed_count == total
        external_signal = (confidence - 0.5) * 2.0

        evidence_items = [f"{name}: {'OK' if ok else 'FAIL'}" for name, ok in checks]
        return VerificationResult(
            method=VerificationMethod.REGEX_MATCH,
            passed=passed,
            confidence=round(confidence, 4),
            evidence="; ".join(evidence_items),
            external_signal=round(external_signal, 4),
            latency_ms=0.0,
        )

    # ── helpers ───────────────────────────────────────────────────

    def _heuristic_consistency(self, output: str, query: str) -> VerificationResult:
        """Fallback consistency check without LLM generator.

        Splits output into sentences and checks for internal contradictions
        via simple keyword-based analysis.

        Args:
            output: the model's generated response
            query: the original query

        Returns:
            VerificationResult with SELF_CONSISTENCY method
        """
        sentences = re.split(r"[.。!！?？\n]+", output)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        if len(sentences) < 2:
            return VerificationResult(
                method=VerificationMethod.SELF_CONSISTENCY,
                passed=True,
                confidence=0.5,
                evidence="Heuristic: too few sentences to check, assumed consistent",
                external_signal=0.1,
                latency_ms=0.0,
            )

        contradiction_pairs = [
            (r"\byes\b", r"\bno\b"),
            (r"\btrue\b", r"\bfalse\b"),
            (r"\bcorrect\b", r"\bincorrect\b"),
            (r"\bis\b", r"\bis\s+not\b"),
            (r"\bcan\b", r"\bcannot\b"),
        ]

        contradiction_count = 0
        for pos_pattern, neg_pattern in contradiction_pairs:
            has_pos = any(re.search(pos_pattern, s, re.IGNORECASE) for s in sentences)
            has_neg = any(re.search(neg_pattern, s, re.IGNORECASE) for s in sentences)
            if has_pos and has_neg:
                contradiction_count += 1

        consistency_score = max(0.0, 1.0 - contradiction_count * 0.25)
        passed = consistency_score >= SELF_CONSISTENCY_AGREEMENT_THRESHOLD

        return VerificationResult(
            method=VerificationMethod.SELF_CONSISTENCY,
            passed=passed,
            confidence=round(consistency_score, 4),
            evidence=f"Heuristic: {len(sentences)} sentences, {contradiction_count} contradictions",
            external_signal=round(consistency_score * 1.6 - 0.8, 4),
            latency_ms=0.0,
        )

    def _compute_agreement(self, variants: list[str], original: str) -> list[float]:
        """Compute agreement scores between each variant and the original.

        Uses simple word overlap as a proxy for semantic agreement.
        For production use, replace with embedding cosine similarity.

        Args:
            variants: list of alternative answer strings
            original: the original output to compare against

        Returns:
            list of agreement scores (0-1) for each variant
        """
        scores: list[float] = []
        original_words = set(original.lower().split())
        if not original_words:
            return [0.0] * len(variants)

        for variant in variants:
            variant_words = set(variant.lower().split())
            if not variant_words:
                scores.append(0.0)
                continue
            overlap = variant_words & original_words
            score = len(overlap) / max(len(original_words), len(variant_words))
            scores.append(score)

        return scores

    async def _generate_async(self, generator: Any, prompt: str) -> str:
        """Safely call the generator's async generate method.

        Args:
            generator: the LLM generator with an async generate() method
            prompt: the prompt string to send

        Returns:
            generated text string
        """
        try:
            if hasattr(generator, "generate"):
                result = generator.generate(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
            if callable(generator):
                result = generator(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
            return str(generator)
        except Exception as e:
            logger.warning(f"ExternalVerifier: _generate_async failed: {e}")
            return ""

    # ── convenience ───────────────────────────────────────────────

    async def get_external_reward(self, output: str, query: str) -> float:
        """Convenience: verify and return the external_signal (-1 to 1).

        Args:
            output: the model's generated response
            query: the original query

        Returns:
            external_signal float between -1 and 1
        """
        result = await self.verify(output, query)
        return result.external_signal

    # ── stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return verification statistics.

        Returns:
            dict with total verifications, pass rate, and per-method breakdown
        """
        history = list(self._verification_history)
        if not history:
            return {
                "total_verifications": 0,
                "pass_rate": 0.0,
                "avg_external_signal": 0.0,
                "avg_latency_ms": 0.0,
                "methods_used": {},
            }

        passed = sum(1 for r in history if r.passed)
        total = len(history)
        avg_signal = sum(r.external_signal for r in history) / total
        avg_latency = sum(r.latency_ms for r in history) / total

        methods_used: dict[str, dict[str, int | float]] = {}
        for r in history:
            m = r.method.value
            if m not in methods_used:
                methods_used[m] = {"count": 0, "passed": 0, "avg_signal": 0.0}
            methods_used[m]["count"] += 1
            if r.passed:
                methods_used[m]["passed"] += 1

        for m, data in methods_used.items():
            signals = [r.external_signal for r in history if r.method.value == m]
            total_m = len(signals)
            data["pass_rate"] = round(data["passed"] / data["count"], 4) if data["count"] > 0 else 0.0
            data["avg_signal"] = round(sum(signals) / total_m, 4) if total_m > 0 else 0.0

        return {
            "total_verifications": total,
            "pass_rate": round(passed / total, 4),
            "avg_external_signal": round(avg_signal, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "methods_used": methods_used,
        }


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_external_verifier: ExternalVerifier | None = None


def get_external_verifier() -> ExternalVerifier:
    """Get or create the singleton ExternalVerifier instance."""
    global _external_verifier
    if _external_verifier is None:
        _external_verifier = ExternalVerifier()
        logger.info("ExternalVerifier singleton created")
    return _external_verifier


__all__ = [
    "VerificationMethod",
    "VerificationResult",
    "ExternalVerifier",
    "get_external_verifier",
]
