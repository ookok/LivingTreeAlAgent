"""QualityScorer — PromptEcho-inspired zero-cost output quality scoring.

PromptEcho (Alibaba, arxiv 2604.12652): use a frozen model's token-level
cross-entropy (CE) loss with original prompt as label to evaluate output
quality. No annotation, no reward model training, zero extra inference.

LivingTree adaptation: scores generated output quality via three methods:
  1. API logprobs (if provider supports) — exact token-level CE
  2. N-gram prompt-output alignment — heuristic proxy when no logprobs
  3. Structural signals — code blocks, citations, standard references

Usage:
    scorer = QualityScorer()
    score = scorer.evaluate(output_text, system_prompt, user_prompt)
    # → ScoreResult with overall, per_segment, flags

Segment-level scoring locates *where* the output is weak, enabling
targeted repair instead of full regeneration. Low-scoring segments
are candidates for self-correction.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SegmentScore:
    text: str
    index: int
    score: float
    start_char: int = 0
    end_char: int = 0
    flags: list[str] = field(default_factory=list)

    @property
    def is_weak(self) -> bool:
        return self.score < 0.4

    @property
    def is_good(self) -> bool:
        return self.score >= 0.7


@dataclass
class ScoreResult:
    output: str
    prompt: str
    overall_score: float
    method: str
    per_segment: list[SegmentScore] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    token_count: int = 0

    @property
    def weak_segments(self) -> list[SegmentScore]:
        return [s for s in self.per_segment if s.is_weak]

    @property
    def strong_segments(self) -> list[SegmentScore]:
        return [s for s in self.per_segment if s.is_good]


class QualityScorer:
    """PromptEcho-style: score output quality using only the prompt and output."""

    def __init__(self):
        pass

    def evaluate(self, output: str, system_prompt: str = "",
                 user_prompt: str = "") -> ScoreResult:
        """Score output quality using prompt-output n-gram alignment.

        The PromptEcho equivalent: instead of feeding output through LLM
        to compute CE, use n-gram overlap as a lightweight alignment proxy.
        Higher overlap = output more faithfully addresses the prompt.
        """
        full_prompt = f"{system_prompt}\n{user_prompt}" if system_prompt else user_prompt

        total_score = self._compute_alignment_score(output, full_prompt)
        structural_score = self._compute_structural_score(output, full_prompt)
        specificity_score = self._compute_specificity_score(output)
        citation_score = self._compute_citation_score(output)

        overall = total_score * 0.30 + structural_score * 0.30 + \
                  specificity_score * 0.25 + citation_score * 0.15

        if len(full_prompt) < 30:
            overall = structural_score * 0.35 + specificity_score * 0.35 + \
                      citation_score * 0.20 + total_score * 0.10

        segments = self._segment_score(output, full_prompt)

        flags = self._detect_flags(output, full_prompt)

        return ScoreResult(
            output=output, prompt=full_prompt,
            overall_score=round(overall, 3), method="ngram_alignment",
            per_segment=segments, flags=flags,
            token_count=len(output.split()),
        )

    def evaluate_batch(self, items: list[dict[str, str]]) -> list[ScoreResult]:
        """Score multiple outputs, useful for candidate ranking in evolution."""
        return [self.evaluate(
            item["output"],
            item.get("system", ""),
            item.get("prompt", ""),
        ) for item in items]

    def select_best(self, items: list[dict[str, str]]) -> tuple[int, ScoreResult]:
        """Select the best candidate by PromptEcho score. Returns (index, result)."""
        results = self.evaluate_batch(items)
        best_idx = max(range(len(results)), key=lambda i: results[i].overall_score)
        return best_idx, results[best_idx]

    def sort_by_quality(self, items: list[dict[str, str]]) -> list[tuple[int, ScoreResult]]:
        """Sort candidates by quality score descending."""
        results = self.evaluate_batch(items)
        indexed = list(enumerate(results))
        indexed.sort(key=lambda x: x[1].overall_score, reverse=True)
        return indexed

    # ── Scoring components ──

    def _compute_alignment_score(self, output: str, prompt: str) -> float:
        """Jaccard n-gram alignment + keyword overlap between prompt and output.

        PromptEcho proxy: higher overlap = output covers more of the
        prompt's semantic territory. Uses Jaccard for balanced scoring
        regardless of prompt/output length asymmetry.
        """
        if not prompt or not output:
            return 0.5

        prompt_lower = prompt.lower()
        output_lower = output.lower()

        prompt_ngrams = self._ngrams(prompt_lower, 3)
        output_ngrams = self._ngrams(output_lower, 3)

        if not prompt_ngrams or not output_ngrams:
            return 0.5

        intersection = len(prompt_ngrams & output_ngrams)
        union = len(prompt_ngrams | output_ngrams)
        jaccard = intersection / union if union > 0 else 0.0

        prompt_keywords = re.findall(r'[\u4e00-\u9fff]{2,}', prompt_lower)
        keyword_hits = sum(1 for kw in prompt_keywords if kw in output_lower)
        keyword_score = keyword_hits / max(len(prompt_keywords), 1) if prompt_keywords else 0.5

        return min(jaccard * 0.6 + keyword_score * 0.4, 1.0)

    def _compute_structural_score(self, output: str, prompt: str) -> float:
        """Evaluate structural quality: headings, code blocks, lists, tables."""
        score = 0.5

        if re.search(r'#+\s', output):
            score += 0.1

        if re.search(r'```', output):
            score += 0.1
            balanced = output.count('```') % 2 == 0
            if not balanced:
                score -= 0.15

        if re.search(r'^\s*[-*]\s', output, re.MULTILINE):
            score += 0.05

        if re.search(r'\|.*\|.*\|', output):
            score += 0.1

        total_chars = len(output)
        blank_ratio = output.count('\n\n') / max(total_chars / 500, 1)
        score += min(blank_ratio * 0.3, 0.1)

        return min(score, 1.0)

    def _compute_specificity_score(self, output: str) -> float:
        """Reward specificity: numbers, standards, concrete values."""
        score = 0.3

        numbers = re.findall(r'\b\d+\.?\d*\b', output)
        if len(numbers) >= 5:
            score += 0.3
        elif len(numbers) >= 2:
            score += 0.15

        standards = re.findall(r'(?:GB\d|HJ\d|ISO\d|GB/T\d)', output)
        if standards:
            score += 0.15 * min(len(set(standards)), 3)

        units = re.findall(r'(?:μg|mg|dB|km|m³|吨|万元|%|m/s)', output)
        if units:
            score += 0.1

        code_refs = re.findall(r'(?:def |class |import |async def )', output)
        if code_refs:
            score += 0.1

        return min(score, 1.0)

    def _compute_citation_score(self, output: str) -> float:
        """Reward citations and source references."""
        score = 0.3

        refs = re.findall(r'(?:https?://|根据|参考|引自|来源)', output)
        score += 0.15 * min(len(refs), 4)

        brackets = re.findall(r'\[[\d,\s]+\]', output)
        if brackets:
            score += 0.15

        statute = re.findall(r'(?:《[^》]+》|第[一二三四五六七八九十百千]+[条章节]|Article\s+\d+)', output)
        if statute:
            score += 0.15

        return min(score, 1.0)

    # ── Segment-level scoring ──

    def _segment_score(self, output: str, prompt: str) -> list[SegmentScore]:
        paragraphs = re.split(r'\n\n+', output)
        if len(paragraphs) <= 1:
            return [SegmentScore(text=output, index=0, score=self._compute_alignment_score(output, prompt),
                                  start_char=0, end_char=len(output))]

        segments = []
        pos = 0
        for i, para in enumerate(paragraphs):
            if not para.strip():
                pos += len(para) + 2
                continue

            end_pos = pos + len(para)
            seg_score = self._score_segment(para, prompt)
            flags = self._segment_flags(para)

            segments.append(SegmentScore(
                text=para.strip(), index=i, score=round(seg_score, 3),
                start_char=pos, end_char=end_pos, flags=flags,
            ))
            pos = end_pos + 2

        return segments

    def _score_segment(self, segment: str, prompt: str) -> float:
        base = self._compute_alignment_score(segment, prompt)
        if len(segment) < 30:
            base *= 0.8
        if re.search(r'(?:错误|Error|error|失败|Failed|异常)', segment):
            base += 0.1
        if re.search(r'(?:结论|总结|建议|综上所述)', segment):
            base += 0.1
        return min(base, 1.0)

    # ── Detection ──

    @staticmethod
    def _detect_flags(output: str, prompt: str) -> list[str]:
        flags = []

        if len(output) < 50:
            flags.append("too_short")
        if len(output) > 15000:
            flags.append("verbose")

        prompt_entities = set(re.findall(r'[A-Z]{2,}[-\d]*|《[^》]+》', prompt))
        output_text = output
        missing = [e for e in prompt_entities if e not in output_text]
        if missing:
            flags.append(f"missing_entities:{','.join(missing[:3])}")

        if re.search(r'(?:不确定|可能|也许|大概)', output):
            flags.append("hedging")

        if "```" in output and output.count("```") % 2 != 0:
            flags.append("unclosed_code_block")

        return flags

    @staticmethod
    def _segment_flags(segment: str) -> list[str]:
        flags = []
        if len(segment) < 20:
            flags.append("short")
        if re.search(r'(?:error|错误|fail)', segment, re.IGNORECASE):
            flags.append("error_mention")
        return flags

    @staticmethod
    def _ngrams(text: str, n: int) -> set:
        text = re.sub(r'\s+', ' ', text)
        return {text[i:i + n] for i in range(len(text) - n + 1)}


_quality_scorer: QualityScorer | None = None


def get_quality_scorer() -> QualityScorer:
    global _quality_scorer
    if _quality_scorer is None:
        _quality_scorer = QualityScorer()
    return _quality_scorer
