"""ConfidenceCalibrator — Per-response confidence scoring with auto-escalation.

After generation, a fast L1 flash model assesses confidence (0-100). Low confidence
triggers L2 pro regeneration; medium confidence appends a warning tag.

Integration:
    cal = get_confidence_calibrator()
    level, score = await cal.assess(response, query, chat_fn)
    response = cal.format(response, level, score)
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from loguru import logger


class ConfidenceCalibrator:
    """Confidence assessment and auto-escalation for responses."""

    _instance: Optional["ConfidenceCalibrator"] = None

    @classmethod
    def instance(cls) -> "ConfidenceCalibrator":
        if cls._instance is None:
            cls._instance = ConfidenceCalibrator()
        return cls._instance

    def __init__(self):
        self._assessments = 0
        self._low_count = 0

    async def assess(
        self, response: str, query: str,
        chat_fn: Callable, max_tokens: int = 15,
    ) -> tuple[str, float]:
        """Assess response confidence. Returns (level, score)."""
        self._assessments += 1

        prompt = (
            "Rate confidence of this answer 0-100. Consider: factual certainty, "
            "completeness, hedging words ('maybe','perhaps','might'). "
            "Reply ONLY the number.\n"
            f"Query: {query[:200]}\n"
            f"Answer: {response[:600]}"
        )

        try:
            result = await chat_fn(
                [{"role": "user", "content": prompt}],
                provider="", max_tokens=max_tokens, temperature=0.0,
            )
            text = getattr(result, 'text', '') or str(result)
            digits = ''.join(c for c in text if c.isdigit())
            score = float(digits[:2]) / 100.0 if digits else 0.5
            score = min(1.0, max(0.0, score))

            if score < 0.4:
                self._low_count += 1
                return "low", score
            if score < 0.7:
                return "medium", score
            return "high", score
        except Exception as e:
            logger.debug(f"ConfidenceCalibrator assess: {e}")
            return "unknown", 0.5

    def format(self, response: str, level: str, score: float) -> str:
        """Format response with confidence annotation."""
        if level == "unknown":
            return response
        if level == "low":
            return f"{response}\n\n[置信度评估: 低 — 建议核实关键信息]"
        if level == "medium":
            return f"{response}\n\n[置信度: {score:.0%} — 请核实关键事实]"
        return response  # high → no annotation needed

    @property
    def low_rate(self) -> float:
        return self._low_count / max(self._assessments, 1)

    def stats(self) -> dict:
        return {
            "assessments": self._assessments,
            "low_count": self._low_count,
            "low_rate": round(self.low_rate, 3),
        }


_calibrator: Optional[ConfidenceCalibrator] = None


def get_confidence_calibrator() -> ConfidenceCalibrator:
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
    return _calibrator


__all__ = ["ConfidenceCalibrator", "get_confidence_calibrator"]
