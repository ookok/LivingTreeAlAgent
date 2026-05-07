"""OutputCompressor — context-mode inspired LLM output compression.

context-mode rules: drop filler, keep technical substance.
Pattern: [thing] [action] [reason]. [next step].
~65-75% output token reduction while preserving full technical accuracy.

TACO Integration: static PHRASES_TO_REMOVE can be supplemented by
SelfEvolvingRules which discovers new filler patterns from interaction
history and stores them in the GlobalRulePool.

Usage:
    from livingtree.dna.output_compressor import compress_output, CompressResult
    result = compress_output(long_response)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


PHRASES_TO_REMOVE = [
    r'(?i)(Sure!?|Of course!?|Absolutely!?|Certainly!?|Great!?)\s*',
    r"(?i)(I'?d be (happy|glad) to (help|assist)( you)?)\s*",
    r"(?i)(I would be (happy|glad) to (help|assist)( you)?)\s*",
    r"(?i)(I hope (that )?this (helps|is useful|is helpful)\.?)\s*",
    r"(?i)(Let me (know|explain|walk you through|take a look|check)\.?)\s*",
    r"(?i)(Please (let me know|don't hesitate|feel free)\.?)\s*",
    r"(?i)(You'?re welcome!?)\s*",
    r"(?i)(No problem!?)\s*",
]

HEDGING_PATTERNS = [
    r"(?i)(might want to|may want to|could consider|should probably)\s*",
    r"(?i)(it might be|it may be|it could be)\s*",
    r"(?i)(you might|you may|you could)\s*",
]

FILLER_WORDS = {
    "just", "really", "basically", "actually", "literally", "simply",
    "definitely", "certainly", "absolutely", "perhaps", "maybe", "possibly",
    "probably", "somewhat", "rather", "quite", "very",
}

EXPAND_TRIGGERS = [
    "security", "vulnerability", "exploit", "attack",
    "irreversible", "permanent", "cannot be undone",
    "delete all", "drop table", "DROP TABLE", "rm -rf",
    "production", "prod environment",
    "confused", "unsure", "don't understand",
]


@dataclass
class CompressResult:
    original: str
    compressed: str = ""
    original_chars: int = 0
    compressed_chars: int = 0
    phrases_removed: int = 0
    filler_removed: int = 0
    expanded: bool = False
    expansion_reason: str = ""

    @property
    def reduction_pct(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return round((1 - self.compressed_chars / self.original_chars) * 100, 1)

    @property
    def original_tokens(self) -> int:
        return max(1, self.original_chars // 3)

    @property
    def compressed_tokens(self) -> int:
        return max(1, self.compressed_chars // 3)


def compress_output(text: str, force_full: bool = False) -> CompressResult:
    """Compress LLM output by removing filler, then codex semantic substitution.

    Always applies codex compression by default (no config needed).
    Codex header included inline so LLM can decode symbols when needed.
    """
    if not text or not text.strip():
        return CompressResult(original=text, compressed=text)

    result = CompressResult(original=text, original_chars=len(text))

    if force_full:
        result.compressed = text
        result.compressed_chars = len(text)
        result.expanded = True
        result.expansion_reason = "force_full"
        return result

    for trigger in EXPAND_TRIGGERS:
        if trigger.lower() in text.lower():
            result.compressed = text
            result.compressed_chars = len(text)
            result.expanded = True
            result.expansion_reason = f"expand_trigger: {trigger}"
            return result

    compressed = _compress(text, result)

    try:
        from ..execution.context_codex import get_context_codex
        codex = get_context_codex(seed=False)
        codex_compressed, header = codex.compress(compressed, layer=3,
                                                    max_header_chars=500)
        if header and codex_compressed:
            compressed = f"{header}\n---\n{codex_compressed}"
    except Exception:
        pass

    result.compressed = compressed
    result.compressed_chars = len(compressed)
    return result


def compress_with_codex(text: str, force_full: bool = False) -> CompressResult:
    """Compress output with filler removal + ContextCodex semantic substitution.

    Returns CompressResult where compressed includes codex symbols.
    Codex header is available via compressed itself (includes inline symbol defs).
    """
    result = compress_output(text, force_full)
    if result.expanded:
        return result

    from ..execution.context_codex import get_context_codex
    codex = get_context_codex(seed=False)
    codex_compressed, header = codex.compress(result.compressed, layer=3,
                                                max_header_chars=500)
    if header and codex_compressed:
        result.compressed = f"{header}\n---\n{codex_compressed}"
        result.compressed_chars = len(result.compressed)
    return result


def delta_encode_events(events: list[dict]) -> str:
    """Encode structured events as compact delta notation using ContextCodex.

    events: list of {"type": "file_edit"|"git_commit"|"decision"|"error", ...}
    Returns a compact delta block string.
    """
    from ..execution.context_codex import DeltaEncoder, get_context_codex
    codex = get_context_codex(seed=False)
    deltas = []
    for ev in events:
        t = ev.get("type", "")
        if t == "file_edit":
            deltas.append(DeltaEncoder.encode_file_edit(
                ev.get("file", ""), ev.get("line", 0),
                ev.get("before", ""), ev.get("after", ""),
                ev.get("cause", "")))
        elif t == "git_commit":
            deltas.append(DeltaEncoder.encode_git_op("commit", ev.get("target", "")))
        elif t == "decision":
            deltas.append(DeltaEncoder.encode_decision(
                ev.get("what", ""), ev.get("cause", "")))
        elif t == "error":
            deltas.append(DeltaEncoder.encode_error(
                ev.get("target", ""), ev.get("fixed", False)))
    return codex.compress_delta(deltas)


def _compress(text: str, result: CompressResult) -> str:
    code_blocks: list[str] = []
    code_placeholder = "__CODE_BLOCK_{}__"

    def save_code(match):
        code_blocks.append(match.group(0))
        return code_placeholder.format(len(code_blocks) - 1)

    text = re.sub(r'```[\s\S]*?```', save_code, text)
    text = re.sub(r'`[^`]+`', save_code, text)

    for pattern in PHRASES_TO_REMOVE:
        before = text
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        if text != before:
            result.phrases_removed += 1

    for pattern in HEDGING_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    words = text.split()
    filtered = []
    for w in words:
        stripped = re.sub(r'[^\w]', '', w).lower()
        if stripped in FILLER_WORDS:
            result.filler_removed += 1
            continue
        filtered.append(w)
    text = ' '.join(filtered)

    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',(\S)', r', \1', text)
    text = re.sub(r';{2,}', ';', text)

    for i, block in enumerate(code_blocks):
        text = text.replace(code_placeholder.format(i), block)

    lines = text.strip().split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
        elif cleaned and cleaned[-1] != '':
            cleaned.append('')

    text = '\n'.join(cleaned).strip()

    return text


def compress_conversation(messages: list[dict], force_full: bool = False) -> list[dict]:
    """Compress all assistant messages in a conversation.

    Leaves user messages and system prompts unchanged.
    Only compresses assistant (LLM) responses.
    """
    result = []
    for msg in messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            cr = compress_output(content, force_full=force_full)
            msg = dict(msg)
            msg["content"] = cr.compressed
            msg["_compressed"] = True
            msg["_compression_pct"] = cr.reduction_pct
        result.append(msg)
    return result


def batch_compress(texts: list[str]) -> list[CompressResult]:
    """Compress multiple texts in batch."""
    return [compress_output(t) for t in texts]


def stats_from_results(results: list[CompressResult]) -> dict[str, Any]:
    """Get aggregate stats from compression results."""
    if not results:
        return {}
    total_original = sum(r.original_chars for r in results)
    total_compressed = sum(r.compressed_chars for r in results)
    total_filler = sum(r.filler_removed for r in results)
    total_phrases = sum(r.phrases_removed for r in results)
    return {
        "count": len(results),
        "original_chars": total_original,
        "compressed_chars": total_compressed,
        "overall_reduction_pct": round((1 - total_compressed / max(total_original, 1)) * 100, 1),
        "filler_words_removed": total_filler,
        "phrases_removed": total_phrases,
        "expanded_count": sum(1 for r in results if r.expanded),
    }


# ── TACO Integration: Pool-backed evolving phrase removal ────────────

# Cache of dynamically discovered filler phrases from GlobalRulePool
_evolved_phrases: list[str] | None = None
_evolved_phrase_patterns: list[str] | None = None
_evolved_last_load: float = 0.0
_EVOLVED_RELOAD_SECONDS = 300  # Reload from pool every 5 minutes


def _load_evolved_phrases(force: bool = False) -> list[str]:
    """Load self-evolved filler removal patterns from GlobalRulePool.

    Combines static PHRASES_TO_REMOVE with dynamically discovered patterns
    from the TACO rule pool. Cached for 5 minutes between reloads.
    """
    global _evolved_phrases, _evolved_phrase_patterns, _evolved_last_load
    import time as _time

    if not force and _evolved_phrases is not None:
        if _time.time() - _evolved_last_load < _EVOLVED_RELOAD_SECONDS:
            return _evolved_phrases

    patterns = []
    try:
        from ..execution.global_rule_pool import get_global_rule_pool, RuleAction
        pool = get_global_rule_pool(seed=False)

        # Load REMOVE-type rules from the "filler" and "output" namespaces
        for rule in pool._rules.values():
            if rule.is_expired or not rule.is_active:
                continue
            if rule.action == RuleAction.REMOVE and rule.match_pattern:
                if rule.namespace in ("general", "filler", "output", "text"):
                    # Validate regex
                    try:
                        re.compile(rule.match_pattern)
                        patterns.append(rule.match_pattern)
                    except re.error:
                        pass
    except Exception:
        pass

    _evolved_phrase_patterns = patterns
    _evolved_last_load = _time.time()
    return patterns


def compress_output_with_evolved(text: str, force_full: bool = False) -> CompressResult:
    """Compress LLM output with static + pool-evolved rules.

    Extends compress_output() by also applying self-evolved removal rules
    from the GlobalRulePool. Use this when you want the full TACO benefit.
    """
    result = compress_output(text, force_full=force_full)
    if result.expanded:
        return result

    # Apply self-evolved removal rules on top
    evolved = _load_evolved_phrases()
    if evolved:
        compressed = result.compressed
        removed_count = 0
        for pattern in evolved:
            before = compressed
            compressed = re.sub(pattern, '', compressed, flags=re.IGNORECASE)
            if compressed != before:
                removed_count += 1
        if removed_count > 0:
            result.compressed = compressed
            result.compressed_chars = len(compressed)
            result.phrases_removed += removed_count

    return result


def flush_evolved_phrases_cache():
    """Force reload of evolved phrases on next compress call."""
    global _evolved_phrases, _evolved_phrase_patterns, _evolved_last_load
    _evolved_phrases = None
    _evolved_phrase_patterns = None
    _evolved_last_load = 0.0
