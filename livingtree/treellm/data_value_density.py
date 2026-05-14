"""DataValueDensity — Quantify and enhance the learning value of data.

Implements value density scoring based on:
  1. Information density: unique tokens / total + entropy estimation
  2. Structural complexity: reasoning chains, code blocks, structured outputs
  3. Causal signals: if-then, because-therefore, counterfactuals
  4. Novelty: similarity to existing data (lower similarity = more valuable)
  5. Utility: whether the data produced successful outcomes
  6. Completeness: whether the conversation reached resolution

Automatic integration with existing subsystems:
  ContextMoE: only retain high-density memories
  RecordingEngine: only record high-value traces
  PromptEngine: BootstrapFewShot sorted by density
  Distillation: only distill high-density outputs
  CellAI: density-filtered training data
  SemanticDedupCache: high-density cache extended TTL
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class DensityReport:
    """Multi-dimensional data value density assessment."""
    total_score: float = 0.0       # 0.0-1.0 composite
    information_density: float = 0.0
    structural_complexity: float = 0.0
    causal_signals: float = 0.0
    novelty_score: float = 0.5     # Default neutral
    utility_score: float = 0.5     # Default neutral
    completeness: float = 0.5      # Default neutral
    verdict: str = ""              # "high_value" | "medium" | "low_value" | "noise"
    suggestions: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


# ═══ DataValueDensity ══════════════════════════════════════════════


class DataValueDensity:
    """Quantifies the learning value of any data unit."""

    _instance: Optional["DataValueDensity"] = None

    @classmethod
    def instance(cls) -> "DataValueDensity":
        if cls._instance is None:
            cls._instance = DataValueDensity()
        return cls._instance

    def __init__(self):
        self._seen_hashes: set[int] = set()  # For novelty detection
        self._assess_count = 0

    # ── Main Assessment ────────────────────────────────────────────

    def assess(self, text: str, context: dict = None) -> DensityReport:
        """Assess the learning value density of text or conversation."""
        self._assess_count += 1
        ctx = context or {}

        # 1. Information density: unique tokens / total, entropy proxy
        info_density = self._information_density(text)

        # 2. Structural complexity: reasoning chains, code, structure
        structural = self._structural_complexity(text)

        # 3. Causal signals: if-then, because, counterfactuals
        causal = self._causal_signals(text)

        # 4. Novelty: how different from seen data
        novelty = self._novelty(text)

        # 5. Utility: from context (success, depth_grade, user_signal)
        utility = ctx.get("utility", 0.5)

        # 6. Completeness: did the conversation conclude properly?
        completeness = ctx.get("completeness", self._detect_completeness(text))

        # Composite with dynamic weights
        total = (
            info_density * 0.20 +
            structural * 0.25 +
            causal * 0.20 +
            novelty * 0.15 +
            utility * 0.10 +
            completeness * 0.10
        )

        verdict, suggestions = self._classify(total, info_density, causal, ctx)
        self._seen_hashes.add(hash(text[:200]))

        return DensityReport(
            total_score=round(total, 3),
            information_density=round(info_density, 3),
            structural_complexity=round(structural, 3),
            causal_signals=round(causal, 3),
            novelty_score=round(novelty, 3),
            utility_score=round(utility, 3),
            completeness=round(completeness, 3),
            verdict=verdict,
            suggestions=suggestions,
            metrics={
                "token_count": len(text.split()),
                "unique_ratio": len(set(text.lower().split())) / max(len(text.split()), 1),
                "code_blocks": text.count("```"),
                "reasoning_markers": sum(1 for m in self._get_reasoning_patterns() if m in text),
            },
        )

    def assess_batch(self, items: list[str], context: dict = None) -> list[DensityReport]:
        """Assess multiple items and rank by value density."""
        reports = [self.assess(item, context) for item in items]
        reports.sort(key=lambda r: -r.total_score)
        return reports

    def filter_high_value(self, items: list[str],
                          threshold: float = 0.3) -> list[str]:
        """Filter only high-value items."""
        return [item for item in items
                if self.assess(item).total_score >= threshold]

    def select_top_k(self, items: list[str], k: int = 3) -> list[str]:
        """Select top-K most valuable items."""
        scored = [(item, self.assess(item).total_score) for item in items]
        scored.sort(key=lambda x: -x[1])
        return [item for item, _ in scored[:k]]

    # ── Dimension Scorers ──────────────────────────────────────────

    def _information_density(self, text: str) -> float:
        """Unique token ratio + stopword filtering + entropy proxy."""
        if not text or len(text) < 10:
            return 0.0
        tokens = text.lower().split()
        if len(tokens) < 5:
            return 0.1

        # Unique ratio
        unique_ratio = len(set(tokens)) / len(tokens)

        # Content word ratio (exclude stopwords)
        stopwords = {"的","了","在","是","我","有","和","就","不","人","都","一",
                     "the","a","an","is","are","was","were","be","been","being",
                     "have","has","had","do","does","did","will","would","shall",
                     "may","might","can","could","should","to","of","in","for",
                     "on","with","at","by","from","as","into","than","that","it"}
        content_tokens = [t for t in tokens if t not in stopwords and len(t) > 1]
        content_ratio = len(content_tokens) / max(len(tokens), 1)

        # URL/code detection
        has_code = "```" in text or "import " in text or "def " in text
        has_url = "http" in text

        score = unique_ratio * 0.4 + content_ratio * 0.4 + (0.2 if has_code else 0) - (0.1 if has_url else 0)
        return max(0.0, min(1.0, score))

    def _structural_complexity(self, text: str) -> float:
        """Detect structured reasoning: code blocks, lists, tables, paragraphs."""
        score = 0.0

        # Code blocks
        code_blocks = text.count("```")
        if code_blocks >= 2:
            score += 0.3

        # Numbered/structured lists
        list_patterns = sum(1 for _ in re.finditer(r'^\s*\d+[\.\)]\s', text, re.MULTILINE))
        if list_patterns >= 3:
            score += 0.2

        # Paragraph structure
        paragraphs = [p for p in text.split("\n\n") if len(p.strip()) > 20]
        if len(paragraphs) >= 2:
            score += 0.2

        # Table/content structure
        if "|" in text and text.count("|") >= 4:
            score += 0.15

        # Nested structure (indentation hierarchy)
        indented = sum(1 for line in text.split("\n") if line.startswith(("  ", "\t")))
        if indented >= 5:
            score += 0.15

        return min(1.0, score)

    def _causal_signals(self, text: str) -> float:
        """Detect causal reasoning patterns."""
        patterns = self._get_reasoning_patterns()
        text_lower = text.lower()
        matches = sum(1 for p in patterns if p in text_lower)

        if matches >= 5:
            return 0.9
        if matches >= 3:
            return 0.7
        if matches >= 1:
            return 0.4
        return 0.1

    @staticmethod
    def _get_reasoning_patterns() -> list[str]:
        return [
            "因为", "所以", "因此", "由于", "如果", "那么", "但是", "然而",
            "首先", "其次", "最后", "然后", "接着", "总结", "结论",
            "because", "therefore", "thus", "hence", "consequently",
            "if", "then", "else", "however", "although", "despite",
            "first", "second", "finally", "next", "lastly",
            "in conclusion", "to summarize", "the reason",
            "第一步", "第二步", "第三步",
        ]

    def _novelty(self, text: str) -> float:
        """How different from previously seen data. Higher = more novel = more valuable."""
        text_hash = hash(text[:200])
        if text_hash in self._seen_hashes:
            return 0.0
        # Approximate novelty by cosine of top tokens
        if len(self._seen_hashes) < 5:
            return 0.7
        # Simplified: more unseen data → higher score
        return min(1.0, len(self._seen_hashes) / 1000)

    def _detect_completeness(self, text: str) -> float:
        """Detect if the conversation reached a natural conclusion."""
        endings = ["谢谢", "好的", "明白了", "清楚了", "没问题",
                   "总结", "以上", "完毕", "结束",
                   "thanks", "got it", "understood", "summary"]
        for ending in endings:
            if ending in text.lower()[-200:]:
                return 0.8
        # Question in last 200 chars → incomplete
        if "?" in text[-200:] or "？" in text[-200:]:
            return 0.3
        return 0.5

    @staticmethod
    def _classify(total: float, info: float, causal: float,
                  ctx: dict) -> tuple[str, list[str]]:
        """Classify data into value tiers with improvement suggestions."""
        suggestions = []
        if total >= 0.6:
            verdict = "high_value"
        elif total >= 0.3:
            verdict = "medium"
            if info < 0.3:
                suggestions.append("Increase vocabulary diversity")
            if causal < 0.3:
                suggestions.append("Add reasoning chains (if-then, because)")
        elif total >= 0.1:
            verdict = "low_value"
            suggestions.extend(["Remove redundant content", "Add structure"])
        else:
            verdict = "noise"
            suggestions.append("Discard or heavily compress")
        return verdict, suggestions

    # ── Integration Helpers ────────────────────────────────────────

    def filter_memories(self, blocks: list[Any],
                        threshold: float = 0.3) -> list[Any]:
        """Filter ContextMoE memory blocks by value density."""
        scored = []
        for b in blocks:
            content = getattr(b, 'content', str(b))
            score = self.assess(content[:2000]).total_score
            if score >= threshold:
                b.value_density = score
                scored.append(b)
        return sorted(scored, key=lambda b: getattr(b, 'value_density', 0), reverse=True)

    def rank_examples(self, examples: list[dict],
                      key: str = "output") -> list[dict]:
        """Rank few-shot examples by value density for PromptEngine."""
        scored = [(ex, self.assess(str(ex.get(key, ex))).total_score)
                  for ex in examples]
        scored.sort(key=lambda x: -x[1])
        for ex, s in scored:
            ex["density_score"] = round(s, 3)
        return [ex for ex, _ in scored]

    def stats(self) -> dict:
        return {"assessments": self._assess_count,
                "seen_hashes": len(self._seen_hashes)}


_density: Optional[DataValueDensity] = None


def get_data_value_density() -> DataValueDensity:
    global _density
    if _density is None:
        _density = DataValueDensity()
    return _density


__all__ = ["DataValueDensity", "DensityReport", "get_data_value_density"]
