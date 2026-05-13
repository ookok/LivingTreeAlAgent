"""Self-Doubt Loop — post-response self-questioning and auto-correction.

After every response, the system critically examines its own answer:
"Is this answer correct? What could be wrong?" — then self-corrects if needed.

Architecture:
    question_response(query, response, consciousness) →
        ├─ Construct meta-cognitive doubt prompt
        ├─ Invoke consciousness.chain_of_thought() for introspection
        ├─ Parse JSON: {has_issues, issues, corrected}
        └─ Record correction in FIFO buffer

This provides a lightweight "System 2" check that catches factual errors,
missing context, and suboptimal phrasings before the user sees them.

Integration:
    sd = get_self_doubt()
    result = await sd.question_response(query, response, consciousness)
    if result["corrected"]:
        final_response = result["response"]
    stats = sd.stats()

Related modules:
    - external_verifier.py — reference-based verification
    - safety_reasoning_monitor.py — safety-specific scrutiny
    - godelian_self.py — formal self-reference limits
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class DoubtRecord:
    """A single self-doubt correction event."""
    query: str
    original_response: str
    corrected_response: str
    issues_found: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        issues = "; ".join(self.issues_found[:3]) if self.issues_found else "none"
        return (
            f"DoubtRecord(query={self.query[:40]}..., "
            f"issues=[{issues}], "
            f"ts={self.timestamp:.0f})"
        )


class SelfDoubtLoop:
    """Post-response self-questioning and auto-correction engine.

    Inspired by cognitive psychology's "System 2" monitoring (Kahneman 2011)
    — a slow, deliberate process that reviews System 1's fast answers.
    Rather than overriding every response, SelfDoubtLoop only intervenes
    when it detects concrete issues, minimizing latency overhead.

    Usage:
        sd = get_self_doubt()
        result = await sd.question_response(query, response, consciousness)
        final = result["response"]  # corrected if issues found, else original
    """

    _MAX_CORRECTIONS: int = 50
    _MAX_RESPONSE_PREVIEW: int = 500
    _MAX_ORIGINAL_PREVIEW: int = 200
    _MAX_CORRECTED_PREVIEW: int = 500
    _MAX_ISSUES: int = 5
    _MAX_QUERY_PREVIEW: int = 50

    def __init__(self) -> None:
        self._corrections: deque[DoubtRecord] = deque(maxlen=self._MAX_CORRECTIONS)
        self._total_checks: int = 0
        self._total_corrected: int = 0
        self._last_check_time: float = 0.0

    # ── Core: question a response ─────────────────────────────────

    async def question_response(
        self,
        query: str,
        response: str,
        consciousness: Any = None,
    ) -> dict:
        """Critically examine a response and correct it if issues are found.

        Args:
            query: The original user query/request.
            response: The system's draft response to examine.
            consciousness: Optional consciousness for chain-of-thought.

        Returns:
            {
                "corrected": bool,
                "response": str,  # corrected version if issues found, else original
                "issues": list[str],
                "checked": bool,
            }
        """
        if not consciousness:
            logger.debug("SelfDoubtLoop: no consciousness provided, skipping check")
            return {"corrected": False, "response": response, "issues": [], "checked": False}

        self._total_checks += 1
        self._last_check_time = time.time()

        doubt_prompt = (
            f"You just answered: '{query[:self._MAX_RESPONSE_PREVIEW]}' "
            f"with: '{response[:self._MAX_RESPONSE_PREVIEW]}'.\n"
            f"Now critically examine your own answer:\n"
            f"1. Is there anything factually incorrect?\n"
            f"2. Did you miss any important context?\n"
            f"3. Is there a better way to answer this?\n"
            f"4. Could any part be misleading or incomplete?\n"
            f"5. Are there unsafe or harmful implications?\n"
            f"Output ONLY valid JSON: "
            f'{{"has_issues": bool, '
            f'"issues": ["issue1", "issue2", ...], '
            f'"corrected": "corrected response text or null"}}'
        )

        try:
            raw_result = await consciousness.chain_of_thought(doubt_prompt)

            if isinstance(raw_result, str):
                # Extract JSON from possible markdown code block
                result_text = raw_result.strip()
                if result_text.startswith("```"):
                    lines = result_text.split("\n")
                    result_text = "\n".join(
                        line for line in lines
                        if not line.strip().startswith("```")
                    ).strip()
                parsed = json.loads(result_text)
            else:
                parsed = raw_result

            has_issues = parsed.get("has_issues", False)
            issues = parsed.get("issues", []) or []
            corrected = parsed.get("corrected") or parsed.get("corrected_response")

            if has_issues and corrected and isinstance(corrected, str) and corrected.lower() != "null":
                record = DoubtRecord(
                    query=query[:self._MAX_QUERY_PREVIEW],
                    original_response=response[:self._MAX_ORIGINAL_PREVIEW],
                    corrected_response=corrected[:self._MAX_CORRECTED_PREVIEW],
                    issues_found=issues[:self._MAX_ISSUES],
                )
                self._corrections.append(record)
                self._total_corrected += 1
                logger.info(
                    f"SelfDoubtLoop: correction applied — "
                    f"query='{query[:40]}...', issues={issues[:3]}"
                )
                return {
                    "corrected": True,
                    "response": corrected,
                    "issues": issues[:self._MAX_ISSUES],
                    "checked": True,
                }

            if has_issues and not corrected:
                logger.debug(
                    f"SelfDoubtLoop: issues flagged but no corrected text — "
                    f"issues={issues[:3]}"
                )
                return {
                    "corrected": False,
                    "response": response,
                    "issues": issues[:self._MAX_ISSUES],
                    "checked": True,
                }

            return {"corrected": False, "response": response, "issues": [], "checked": True}

        except json.JSONDecodeError as e:
            logger.warning(f"SelfDoubtLoop: JSON parse error — {e}")
            return {"corrected": False, "response": response, "issues": [], "checked": True}
        except Exception:
            logger.exception("SelfDoubtLoop: unexpected error during doubt check")
            return {"corrected": False, "response": response, "issues": [], "checked": True}

    # ── Synchronous shortcut (no consciousness needed) ────────────

    def quick_check(self, query: str, response: str) -> dict:
        """Lightweight heuristic check without LLM invocation.

        Checks for common patterns: empty responses, overly short answers,
        self-contradictory indicators. Useful as a first-pass filter before
        the full question_response() call.

        Returns:
            {"corrected": bool, "response": str (same as input), "issues": list[str]}
        """
        issues: list[str] = []

        if not response or not response.strip():
            issues.append("Empty response")
        elif len(response.split()) < 3:
            issues.append("Overly short response — may lack detail")
        elif "I don't know" in response.lower() and len(response) > 100:
            issues.append("Uncertainty stated but response is long — possible rambling")

        # Check for self-contradictory patterns
        contradictory_pairs = [
            ("always", "never"),
            ("definitely", "probably"),
            ("all", "some"),
        ]
        for a, b in contradictory_pairs:
            if a in response.lower() and b in response.lower():
                issues.append(f"Potential contradiction: uses both '{a}' and '{b}'")

        if issues:
            logger.debug(f"SelfDoubtLoop.quick_check: {len(issues)} issue(s) found")

        return {"corrected": False, "response": response, "issues": issues, "checked": True}

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return summary statistics for the doubt loop."""
        recent = list(self._corrections)[-3:]
        return {
            "total_checks": self._total_checks,
            "total_corrected": self._total_corrected,
            "correction_rate": (
                self._total_corrected / max(self._total_checks, 1)
            ),
            "total_corrections_stored": len(self._corrections),
            "recent_corrections": [
                {
                    "query": r.query,
                    "issues": r.issues_found,
                    "timestamp": r.timestamp,
                }
                for r in reversed(recent)
            ],
            "last_check_time": self._last_check_time,
        }

    def corrections(self) -> list[DoubtRecord]:
        """Return all stored correction records."""
        return list(self._corrections)


# ═══ Singleton ═══

_self_doubt: SelfDoubtLoop | None = None


def get_self_doubt() -> SelfDoubtLoop:
    """Get or create the global SelfDoubtLoop singleton."""
    global _self_doubt
    if _self_doubt is None:
        _self_doubt = SelfDoubtLoop()
        logger.info("SelfDoubtLoop singleton initialized")
    return _self_doubt


__all__ = [
    "DoubtRecord",
    "SelfDoubtLoop",
    "get_self_doubt",
]
