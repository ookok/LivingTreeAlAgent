"""Cone-Precision Prompt Assembly.

Design (#3): Arrange prompt content in a HiFloat8 cone-shaped precision layout.
LLM attention is naturally highest at prompt center ("Lost in the Middle" leveraged).
HiFloat8 assigns more mantissa bits to center, more exponent bits to edges.

Layout:
    [STUB] [SUMMARY] [FULL PRECISION CORE] [SUMMARY] [STUB]
     边缘压缩 ← ← ← ← 注意力最强区 → → → → 边缘压缩

The core (center 40-60%) holds the most critical content at FULL precision.
Edges hold auxiliary context at progressively lower precision tiers.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class ConeAssembler:
    """Assemble prompts with cone-shaped precision distribution.

    Maps HiFloat8's hardware cone precision to prompt token arrangement.
    Center = highest precision (full text), edges = lower precision (compressed).
    """

    # Precision tier → chars per token budget allocation
    TIER_BUDGET = {
        "FULL": 1.0,      # 100% of text, no compression
        "SUMMARY": 0.4,   # 40% of text (semantic summary)
        "STUB": 0.1,      # 10% of text (title + tags only)
    }

    # Default cone shape: [stub?][summary?][core full][summary?][stub?]
    CONE_SEGMENTS = ["STUB_LEFT", "SUMMARY_LEFT", "CORE", "SUMMARY_RIGHT", "STUB_RIGHT"]

    def __init__(self, max_tokens: int = 8192, hifloat8_speedup: float = 1.0):
        self.max_tokens = max_tokens
        self.hifloat8_speedup = hifloat8_speedup
        # Effective max with HiFloat8 speedup
        self.effective_max = int(max_tokens * hifloat8_speedup)

    def set_speedup(self, ratio: float) -> None:
        """Update HiFloat8 speedup ratio → recalculate effective budget."""
        self.hifloat8_speedup = ratio
        self.effective_max = int(self.max_tokens * ratio)

    def assemble(
        self,
        core: list[dict[str, Any]],
        supporting: list[dict[str, Any]] = None,
        cold_zones: list[tuple[int, int]] = None,
    ) -> str:
        """Assemble prompt with cone-shaped precision.

        Args:
            core: Critical content chunks → placed at center (FULL).
            supporting: Auxiliary chunks → placed at SUMMARY edges.
            cold_zones: Token ranges with low attention → placed at STUB edges.

        Returns:
            Assembled prompt string with cone precision distribution.
        """
        supporting = supporting or []
        cold_zones = cold_zones or []

        # Allocate budget across cone segments
        budget = self._allocate_budget(len(core), len(supporting))

        sections = []

        # ── STUB LEFT: compressed low-attention content ──
        if cold_zones and budget.get("STUB_LEFT", 0) > 0:
            stub_text = self._format_stub(cold_zones[:3])
            if stub_text:
                sections.append(f"<!-- auxiliary context (compressed) -->\n{stub_text}")

        # ── SUMMARY LEFT: supporting content at medium precision ──
        left_count = max(1, len(supporting) // 2)
        if left_count > 0 and budget.get("SUMMARY_LEFT", 0) > 0:
            summary_text = self._format_summary(supporting[:left_count])
            if summary_text:
                sections.append(f"<!-- supporting context -->\n{summary_text}")

        # ── CORE: critical content at FULL precision ──
        core_text = self._format_core(core)
        sections.append(f"<!-- CRITICAL CONTEXT (full precision) -->\n{core_text}")

        # ── SUMMARY RIGHT: remaining supporting at medium precision ──
        if len(supporting) > left_count and budget.get("SUMMARY_RIGHT", 0) > 0:
            right_text = self._format_summary(supporting[left_count:])
            if right_text:
                sections.append(f"<!-- additional context -->\n{right_text}")

        # ── STUB RIGHT: remaining cold content ──
        if len(cold_zones) > 3 and budget.get("STUB_RIGHT", 0) > 0:
            stub_text = self._format_stub(cold_zones[3:6])
            if stub_text:
                sections.append(f"<!-- supplementary (compressed) -->\n{stub_text}")

        return "\n\n".join(sections)

    def _allocate_budget(
        self, core_count: int, supporting_count: int
    ) -> dict[str, int]:
        """Allocate token budget across cone segments.

        Center-heavy: 50% to CORE, 20% each to SUMMARY edges, 10% to STUB edges.
        """
        total = max(1, core_count + supporting_count)

        # Cone distribution: core gets highest allocation
        core_pct = 0.50
        summary_pct = 0.20
        stub_pct = 0.05

        return {
            "CORE": int(self.effective_max * core_pct),
            "SUMMARY_LEFT": int(self.effective_max * summary_pct),
            "SUMMARY_RIGHT": int(self.effective_max * summary_pct),
            "STUB_LEFT": int(self.effective_max * stub_pct),
            "STUB_RIGHT": int(self.effective_max * stub_pct),
        }

    def _format_core(self, chunks: list[dict[str, Any]]) -> str:
        """Format core content at FULL precision — no compression."""
        parts = []
        for chunk in chunks:
            text = chunk.get("text", "")
            title = chunk.get("title", "") or chunk.get("source", "")
            score = chunk.get("score", 0)
            if not text:
                continue
            indicator = "★" if score > 0.8 else "●"
            if title:
                parts.append(f"### {indicator} {title}\n{text}")
            else:
                parts.append(text)
        return "\n\n".join(parts) if parts else ""

    def _format_summary(self, chunks: list[dict[str, Any]]) -> str:
        """Format supporting content at SUMMARY precision — 40% compression."""
        parts = []
        for chunk in chunks:
            text = chunk.get("text", "")
            title = chunk.get("title", "") or chunk.get("source", "")
            if not text:
                continue
            # SUMMARY: keep first paragraph + title
            summary = text[: max(200, len(text) // 3)] + "..." if len(text) > 300 else text
            if title:
                parts.append(f"- **{title}**: {summary}")
            else:
                parts.append(f"- {summary}")
        return "\n".join(parts) if parts else ""

    def _format_stub(self, contexts: list[Any]) -> str:
        """Format at STUB precision — title + tags only."""
        lines = []
        for ctx in contexts:
            if isinstance(ctx, dict):
                title = ctx.get("title", "") or ctx.get("source", "reference")
                text_preview = ctx.get("text", "")
                preview = text_preview[:80] + "..." if len(text_preview) > 80 else text_preview
                lines.append(f"- [{title}] {preview}")
            elif isinstance(ctx, tuple):
                # cold zone: (start_token, end_token)
                lines.append(f"- tokens {ctx[0]}-{ctx[1]}: low attention")
            elif isinstance(ctx, str):
                lines.append(f"- {ctx[:100]}")
        return "\n".join(lines[:5]) if lines else ""  # max 5 STUB items

    def adaptive_assemble(
        self,
        query: str,
        retrieved: list[dict[str, Any]],
        cold_zones: list[tuple[int, int]] = None,
        fdac=None,  # FDACCompressor for dynamic compression ratios
    ) -> str:
        """Adaptive assembly: FDAC-learned ratios + cone layout.

        Chunks scored by FDAC → sorted by relevance → core gets top N
        at FULL, remainder distributed to SUMMARY/STUB.

        Args:
            query: User query (for relevance estimation).
            retrieved: All retrieved chunks with text/source/score.
            cold_zones: Low-attention token ranges from previous turn.
            fdac: Optional FDACCompressor for learned compression.

        Returns:
            Assembled prompt with adaptive cone precision.
        """
        if not retrieved:
            return ""

        # Score chunks by relevance if not already scored
        scored = []
        for chunk in retrieved:
            score = chunk.get("score", 0.5)
            if not score:
                score = self._heuristic_score(chunk.get("text", ""), query)
                if fdac:
                    relevance = fdac._estimate_relevance(
                        chunk.get("text", ""), query
                    )
                    score = max(score, relevance)
            scored.append((score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: -x[0])

        # Top 40% → CORE, next 30% → SUMMARY, bottom 30% → STUB
        n = len(scored)
        core_n = max(1, n * 2 // 5)
        summary_n = max(0, n * 1 // 3)

        core_chunks = [c for _, c in scored[:core_n]]
        summary_chunks = [c for _, c in scored[core_n:core_n + summary_n]]
        stub_contexts = [c for _, c in scored[core_n + summary_n:]]

        if stub_contexts:
            cold_zones = (cold_zones or []) + [
                (0, 0) for _ in stub_contexts
            ]

        return self.assemble(
            core=core_chunks,
            supporting=summary_chunks,
            cold_zones=cold_zones,
        )

    @staticmethod
    def _heuristic_score(text: str, query: str) -> float:
        """Simple BM25-like relevance heuristic."""
        if not query or not text:
            return 0.5
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        hits = sum(1 for t in query_terms if t in text_lower)
        # Normalize: 3+ hits → 1.0
        return min(1.0, hits / max(1, len(query_terms)) * 1.5)


# ── Singleton ──

_cone_assembler: ConeAssembler | None = None


def get_cone_assembler(max_tokens: int = 8192) -> ConeAssembler:
    global _cone_assembler
    if _cone_assembler is None:
        _cone_assembler = ConeAssembler(max_tokens=max_tokens)
    return _cone_assembler
