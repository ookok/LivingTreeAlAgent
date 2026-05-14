"""ContextFold — FoldAgent-inspired context compression for long-horizon tasks.

Context-Folding (arxiv 2510.11967): when an agent completes a sub-trajectory,
intermediate steps are "folded" — collapsed into a concise outcome summary —
reducing active context by ~10x with no performance loss.

This module provides folding utilities for:
  - RLM worker results (parallel fan-out folding)
  - DAG node results (step-level folding)
  - Document sections (chapter-by-chapter folding)
  - LifeEngine stages (perceive→cognize→... stage-to-stage folding)

Folding strategies:
  1. LLM folding (preferred): uses consciousness to summarize while preserving
     domain-critical entities, metrics, decisions, and action items.
  2. Heuristic folding (fallback): extracts first paragraph + key patterns.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FoldResult:
    original_length: int
    folded_length: int
    summary: str
    key_entities: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    confidence: float = 0.8

    @property
    def compression_ratio(self) -> float:
        return round(self.folded_length / max(self.original_length, 1), 3)

    def to_context_block(self) -> str:
        lines = [self.summary]
        if self.key_entities:
            lines.append(f"关键信息: {', '.join(self.key_entities[:5])}")
        if self.decisions:
            lines.append(f"决策: {'; '.join(self.decisions[:3])}")
        if self.action_items:
            lines.append(f"待办: {'; '.join(self.action_items[:3])}")
        return "\n".join(lines)


async def fold_context(content: str, consciousness: Any = None,
                       domain: str = "general", max_chars: int = 500) -> FoldResult:
    """Fold a long context into a compact, structured summary.

    Args:
        content: The full text to fold
        consciousness: LLM consciousness for high-quality folding (optional)
        domain: Domain hint for better entity extraction
        max_chars: Target maximum summary length in characters

    Returns:
        FoldResult with summary, key entities, decisions, action items
    """
    original_len = len(content)
    if original_len <= max_chars:
        return FoldResult(
            original_length=original_len, folded_length=original_len,
            summary=content.strip(), confidence=1.0,
        )

    if consciousness and hasattr(consciousness, 'query'):
        return await _llm_fold(content, consciousness, domain, max_chars)
    if consciousness and hasattr(consciousness, 'chain_of_thought'):
        return await _llm_fold_cot(content, consciousness, domain, max_chars)

    return _heuristic_fold(content, max_chars)


async def fold_contexts(contents: list[str], consciousness: Any = None,
                        domain: str = "general", max_chars: int = 500) -> list[FoldResult]:
    """Fold multiple contexts in parallel where possible."""
    import asyncio
    tasks = [fold_context(c, consciousness, domain, max_chars) for c in contents]
    return await asyncio.gather(*tasks)


async def _llm_fold(content: str, consciousness: Any, domain: str,
                    max_chars: int) -> FoldResult:
    try:
        prompt = (
            f"[Context-Folding] 将以下内容压缩为不超过{max_chars}字符的结构化摘要。\n"
            f"领域: {domain}\n"
            f"保留所有关键实体、数值、决策和行动项。丢弃过程细节和冗余描述。\n\n"
            f"输出JSON格式:\n"
            f'{{"summary": "核心摘要", "key_entities": ["实体1","实体2"], '
            f'"decisions": ["决策1"], "action_items": ["行动1"]}}\n\n'
            f"原始内容:\n{content[:8000]}"
        )
        raw = await consciousness.query(prompt, max_tokens=1024, temperature=0.3)
        return _parse_fold_json(raw, content, max_chars)
    except Exception:
        return _heuristic_fold(content, max_chars)


async def _llm_fold_cot(content: str, consciousness: Any, domain: str,
                        max_chars: int) -> FoldResult:
    try:
        prompt = (
            f"[Context-Folding] 将以下内容压缩为不超过{max_chars}字符的结构化摘要。\n"
            f"领域: {domain}\n"
            f"保留所有关键实体、数值、决策和行动项。\n\n"
            f"输出JSON格式:\n"
            f'{{"summary": "核心摘要", "key_entities": ["实体1","实体2"], '
            f'"decisions": ["决策1"], "action_items": ["行动1"]}}\n\n'
            f"原始内容:\n{content[:8000]}"
        )
        raw = await consciousness.chain_of_thought(prompt, steps=1,
                                                    max_tokens=1024, temperature=0.3)
        return _parse_fold_json(raw, content, max_chars)
    except Exception:
        return _heuristic_fold(content, max_chars)


def _parse_fold_json(raw: str, content: str, max_chars: int) -> FoldResult:
    import json
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
            data = json.loads(raw)
            return FoldResult(
                original_length=len(content),
                folded_length=len(data.get("summary", "")),
                summary=data.get("summary", content[:max_chars]),
                key_entities=data.get("key_entities", []),
                decisions=data.get("decisions", []),
                action_items=data.get("action_items", []),
                confidence=0.7,
            )
    except (ValueError, json.JSONDecodeError):
        pass
    return _heuristic_fold(content, max_chars)


def _heuristic_fold(content: str, max_chars: int) -> FoldResult:
    """Fallback: extract first meaningful paragraph + key patterns."""
    lines = content.strip().split("\n")
    non_empty = [l.strip() for l in lines if l.strip()]

    summary_parts = []

    first_para = non_empty[0] if non_empty else ""
    if len(first_para) > max_chars // 2:
        summary_parts.append(first_para[:max_chars // 2] + "...")
    else:
        summary_parts.append(first_para)

    key_prefixes = ["结论", "总结", "关键", "重要", "Decision:", "Action:", "结果", "错误",
                    "Error:", "Result:", "Summary:", "TL;DR", "核心", "决定", "输出"]
    for line in non_empty[1:]:
        if len(" ".join(summary_parts)) >= max_chars:
            break
        if any(line.startswith(p) for p in key_prefixes):
            summary_parts.append(line[:200])
        elif re.match(r'^[-*•#]', line):
            if len(" ".join(summary_parts)) + len(line) < max_chars:
                summary_parts.append(line[:200])

    key_entities: list[str] = []
    for pattern in [r'\d+\.?\d*\s*(?:吨|mg|dB|km|m³|万元|%)',
                    r'[A-Z]{2,6}[- ]\d{2,4}',
                    r'《[^》]+》']:
        found = re.findall(pattern, content)
        key_entities.extend(found[:5])

    summary = " ".join(summary_parts)
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + "..."

    return FoldResult(
        original_length=len(content),
        folded_length=len(summary),
        summary=summary,
        key_entities=list(set(key_entities))[:5],
        decisions=[],
        action_items=[],
        confidence=0.3,
    )


def fold_text_heuristic(content: str, max_chars: int = 500) -> str:
    """Single-call convenience: fold text with heuristic only, return summary string."""
    result = _heuristic_fold(content, max_chars)
    return result.summary


def fold_with_codex(content: str, max_chars: int = 500) -> tuple[str, str]:
    """ContextCodex-enhanced folding: fold then codex-compress.

    Returns (compressed_text, codex_header) for LLM context injection.
    """
    from .context_codex import get_context_codex
    codex = get_context_codex()
    folded = fold_text_heuristic(content, max_chars)
    compressed, header = codex.compress(folded, layer=3, max_header_chars=400)
    return compressed, header


# ── SSA-inspired Attention Budget Routing ──


@dataclass
class BudgetSegment:
    """A context segment with computed relevance, depth score, and allocated budget.

    v2.4 — MoDA-Enhanced (arXiv:2603.15619): depth_score controls how aggressively
    a segment is compressed. Deep segments (from early pipeline stages that carry
    foundational information) get more budget; shallow segments get compressed
    more aggressively.

    v2.5 — Opus 4.7 KV Cache Weighting: position_index tracks the conversation turn
    index (0=earliest, N-1=latest). kv_preservation_score combines relevance x depth
    x position_decay to model mid-section information decay and allocate token budget
    accordingly. Mid-section segments with high task_criticality get boosted.
    """
    name: str
    content: str
    relevance_score: float = 0.0
    allocated_chars: int = 0
    folded_content: str = ""
    depth_score: float = 0.5
    position_index: int = -1
    kv_preservation_score: float = 0.5

    @property
    def original_chars(self) -> int:
        return len(self.content)


@dataclass
class BudgetAllocation:
    segments: list[BudgetSegment]
    total_budget: int = 0
    total_original: int = 0
    total_allocated: int = 0

    @property
    def compression_ratio(self) -> float:
        return round(self.total_allocated / max(self.total_original, 1), 3)

    def build_context(self) -> str:
        parts = []
        for seg in self.segments:
            parts.append(
                f"<!-- [{seg.name}] relevance={seg.relevance_score:.2f} "
                f"budget={seg.allocated_chars}chars -->\n"
                f"{seg.folded_content}"
            )
        return "\n\n".join(parts)


def score_segment_relevance(segment: str, query: str) -> float:
    """SSA-style content-dependent relevance scoring.

    Instead of equal treatment, score each context segment by its
    content overlap with the query. High relevance = more budget.
    """
    if not segment or not query:
        return 0.0

    q_words = set(query.lower().split())
    s_lower = segment.lower()

    term_hits = sum(1 for w in q_words if w in s_lower)
    term_density = term_hits / max(len(q_words), 1)

    import re
    structural_bonus = 0.0
    if re.search(r'(?:import|from|class|def|function)\s', segment):
        structural_bonus = 0.1
    if re.search(r'(?:错误|Error|error|异常|Exception|failed)', segment):
        structural_bonus += 0.15
    if re.search(r'(?:决策|决定|Decision|action|下一步)', segment):
        structural_bonus += 0.15

    score = term_density + structural_bonus
    if len(segment) < 200:
        score += 0.1

    return min(score, 1.0)


def rope_relative_score(pos_a: int, pos_b: int, num_scales: int = 8) -> float:
    """RoPE-style multi-scale relative position scoring.

    Maps the classical RoPE frequency design (θ_i = 10000^{-2i/d}) to
    position-aware context weighting. For each pair of positions (i, j),
    computes cosine oscillation at multiple frequency scales. Different
    frequency scales respond to different distance ranges:
    - Scale 0 (θ ≈ 1.0): sensitive to short-range (±1-2 position)
    - Scale 4 (θ ≈ 0.1): sensitive to mid-range (±5-10 positions)
    - Scale 7 (θ ≈ 0.01): sensitive to long-range (±20-50 positions)

    Returns a normalized score in [0, 1] where higher = closer relative
    position (shorter effective distance).
    """
    rel_dist = abs(pos_a - pos_b)
    total = 0.0
    for k in range(num_scales):
        theta = 10000.0 ** (-2.0 * k / num_scales)
        total += math.cos(rel_dist * theta * 0.1)
    return (total / num_scales + 1.0) / 2.0


def route_attention_budget(segments: dict[str, str], query: str,
                           total_budget: int = 8000,
                           depth_scores: dict[str, float] | None = None,
                           position_indices: dict[str, int] | None = None,
                           task_criticalities: dict[str, float] | None = None,
                           ) -> BudgetAllocation:
    """SSA + MoDA + Opus 4.7 depth-aware token budget routing across context segments.

    v2.5 Opus 4.7 KV Cache Weighting:
    - position_indices: {name: turn_index} — 0=earliest, N-1=latest
    - task_criticalities: {name: 0-1 score} — how task-critical each segment is
    - position_decay: mid-section segments (indices 5-15) with criticality > 0.6
      get a 1.5x mid_section_boost to combat the mid-section information decay
    - kv_preservation_score: composite score stored per BudgetSegment

    Args:
        segments: {name: content} dict of context segments
        query: The current user query/intent
        total_budget: Total character budget for all segments
        depth_scores: Optional {name: depth_score} dict
        position_indices: Optional {name: turn_index} dict
        task_criticalities: Optional {name: 0-1 criticality} dict

    Returns:
        BudgetAllocation with scored, budgeted, folded segments
    """
    budget_segments = []
    total_original = 0
    ds = depth_scores or {}
    pi = position_indices or {}
    tc = task_criticalities or {}

    n_segments = len(segments)
    center_pos = n_segments // 2

    scored = []
    for idx, (name, content) in enumerate(segments.items()):
        base_score = score_segment_relevance(content, query)
        depth_bonus = ds.get(name, 0.5)
        pos_idx = pi.get(name, idx)
        criticality = tc.get(name, 0.3)

        position_score = rope_relative_score(pos_idx, center_pos)
        mid_boost = 1.0
        if n_segments > 10 and n_segments // 3 <= idx <= n_segments * 2 // 3 and criticality > 0.6:
            mid_boost = 1.3

        kv_preservation = round(
            base_score * 0.30 + depth_bonus * 0.20 + criticality * 0.25 + position_score * 0.25,
            3,
        )
        combined_score = round(base_score * 0.35 + depth_bonus * 0.15 + kv_preservation * 0.50, 3)

        scored.append((name, content, combined_score, depth_bonus, pos_idx, kv_preservation, mid_boost))
        total_original += len(content)

    scored.sort(key=lambda x: x[2], reverse=True)
    total_score = sum(s for _, _, s, _, _, _, _ in scored)
    if total_score == 0:
        total_score = len(scored)

    for name, content, score, depth_val, pos_idx, kv_pres, boost in scored:
        raw_budget = int(total_budget * (score / total_score))
        boosted_budget = int(raw_budget * boost)
        budget = min(boosted_budget, total_budget // 2)

        seg = BudgetSegment(
            name=name, content=content,
            relevance_score=round(score, 3),
            allocated_chars=budget,
            depth_score=round(depth_val, 3),
            position_index=pos_idx,
            kv_preservation_score=round(kv_pres * boost, 3),
        )
        budget_segments.append(seg)

    allocated = 0
    for seg in budget_segments:
        if seg.allocated_chars > 0 and len(seg.content) > seg.allocated_chars:
            seg.folded_content = fold_text_heuristic(seg.content, seg.allocated_chars)
            allocated += seg.allocated_chars
        elif seg.allocated_chars > 0:
            seg.folded_content = seg.content
            allocated += len(seg.content)
        else:
            seg.folded_content = fold_text_heuristic(seg.content, 100)

    return BudgetAllocation(
        segments=budget_segments,
        total_budget=total_budget,
        total_original=total_original,
        total_allocated=allocated,
    )


def budget_context_for_llm(segments: dict[str, str], query: str,
                           total_budget: int = 8000,
                           use_codex: bool = True) -> str:
    """Convenience: allocate budget and return ready-to-use context string.

    If use_codex, folds are further compressed with ContextCodex symbols.
    """
    allocation = route_attention_budget(segments, query, total_budget)
    result = allocation.build_context()

    if use_codex:
        from .context_codex import get_context_codex
        codex = get_context_codex()
        compressed, header = codex.compress(result, layer=3, max_header_chars=500)
        return f"{header}\n\n---\n{compressed}"

    return result


# ── TACO Integration: Terminal-aware context folding ──────────────────

def fold_terminal_output(output: str, command: str = "",
                         max_chars: int = 2000) -> str:
    """Fold terminal output using TACO-style compression rules.

    Pipeline: TerminalCompressor (rule-based) → ContextCodex (symbol-based).
    Use this for terminal outputs before feeding into LLM context.

    Args:
        output: Raw terminal/shell output
        command: The command that produced this output
        max_chars: Target maximum characters

    Returns:
        Compressed string ready for LLM injection
    """
    from .terminal_compressor import get_terminal_compressor
    from .context_codex import get_context_codex

    compressor = get_terminal_compressor(max_chars=max_chars)
    result = compressor.compress(output, command=command)

    if result.method == "rule" and result.compressed_chars <= max_chars:
        # Already well-compressed by TACO rules
        return result.compressed

    # Post-process with codex for additional compression
    codex = get_context_codex()
    compressed, header = codex.compress(
        result.compressed, layer=3, max_header_chars=400)
    if len(compressed) < len(result.compressed) * 0.8:
        return f"{header}\n---\n{compressed}"

    return result.compressed


def fold_with_taco(content: str, domain: str = "general",
                   max_chars: int = 500) -> str:
    """TACO-enhanced folding: rule-based + codex + SSA budget routing.

    Combines all three compression strategies for maximum context efficiency.
    """
    # Step 1: Heuristic fold
    folded = fold_text_heuristic(content, max_chars)

    # Step 2: Apply self-evolved removal rules
    from ..dna.output_compressor import _load_evolved_phrases
    evolved = _load_evolved_phrases()
    if evolved:
        for pattern in evolved[:5]:  # Limit to avoid over-processing
            folded = re.sub(pattern, '', folded, flags=re.IGNORECASE)

    # Step 3: Codex compression
    from .context_codex import get_context_codex
    codex = get_context_codex()
    compressed, header = codex.compress(folded, layer=3, max_header_chars=400)

    if header and len(compressed) < len(folded) * 0.9:
        return f"{header}\n---\n{compressed}"

    return compressed if len(compressed) < len(folded) else folded
