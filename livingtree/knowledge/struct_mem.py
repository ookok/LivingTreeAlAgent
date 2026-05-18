"""StructMem — Structured Hierarchical Memory for Long-Horizon LLM Agents.

Implements the StructMem framework (ACL 2026, ZJU + Ant Group):
- Event-Level Binding: dual-perspective extraction (FACT + RELATION)
- Cross-Event Consolidation: batch semantic synthesis on time triggers
- Temporal Anchoring: all entries timestamped for temporal reasoning
- Natural language storage: no rigid triplets, avoids entity resolution overhead

Configured for LivingTree: uses LivingTree's DualModelConsciousness for LLM
calls and VectorStore for semantic retrieval. Flash model handles extraction
(cheap), pro model handles consolidation (quality).

Usage:
    mem = StructMemory(hub.world)
    
    # Auto-called after every LifeEngine cycle:
    await mem.bind_events(session_id, messages, timestamp)
    
    # Auto-triggered when buffer > time_threshold:
    await mem.consolidate_if_needed()
    
    # Query for context injection:
    entries, synthesis = await mem.retrieve_for_query(query, top_k=60, n_synthesis=5)
"""

from __future__ import annotations

import time
import re
import math
import hashlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# ── RuView Pattern 4: Temporal Compress ──

class MemoryTier(str, Enum):
    """3-tier memory quantization (RuView: hot=8bit, warm=5bit, cold=3bit)."""
    HOT = "hot"       # Recent + frequently accessed — full fidelity
    WARM = "warm"     # Intermediate — compressed summary
    COLD = "cold"     # Stale + rarely accessed — key facts only


@dataclass
class CompressStats:
    """Statistics for temporal compression operations."""
    hot_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    total_compressed: int = 0
    bytes_saved: int = 0
    last_compress: float = 0.0


@dataclass
class CompressedEntry:
    """A compressed version of EventEntry for lower-tier storage."""
    id: str
    original_id: str
    tier: MemoryTier
    summary: str                # Tier-specific compression
    keywords: list[str]
    timestamp: str
    access_count: int = 0
    last_access: float = 0.0
    original_size: int = 0
    compressed_size: int = 0

    def access(self) -> None:
        self.access_count += 1
        self.last_access = time.time()


class TemporalCompressor:
    """RuView-inspired temporal compression: classifies entries by age/access
    and compresses accordingly.

    HOT  (0-30 min, or accessed 5+ times):  full fidelity, 100%
    WARM (30 min-24 hr, or accessed 2-4 times): compressed summary, ~40%
    COLD (>24 hr, or accessed 0-1 time): key facts only, ~15%
    """

    HOT_THRESHOLD_SECONDS = 1800       # 30 minutes
    WARM_THRESHOLD_SECONDS = 86400     # 24 hours
    HOT_ACCESS_MIN = 5
    WARM_ACCESS_MIN = 2

    def __init__(self):
        self._compressed: dict[str, CompressedEntry] = {}
        self.stats = CompressStats()

    def classify(self, entry: EventEntry, access_count: int = 0,
                 last_access: float = 0.0) -> MemoryTier:
        """Classify an entry into a memory tier based on age and access patterns."""
        try:
            ts = datetime.fromisoformat(entry.timestamp)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
        except Exception:
            age = 86400 * 7  # default to old

        if age <= self.HOT_THRESHOLD_SECONDS or access_count >= self.HOT_ACCESS_MIN:
            return MemoryTier.HOT
        elif age <= self.WARM_THRESHOLD_SECONDS or access_count >= self.WARM_ACCESS_MIN:
            return MemoryTier.WARM
        return MemoryTier.COLD

    def compress(self, entry: EventEntry, tier: MemoryTier) -> CompressedEntry:
        """Compress an EventEntry to the appropriate tier fidelity."""
        original_content = (entry.fact_perspective + " " + entry.rel_perspective).strip()
        original_size = len(original_content)
        now = time.time()

        if tier == MemoryTier.HOT:
            summary = original_content
            keywords = self._extract_keywords(original_content, 8)
        elif tier == MemoryTier.WARM:
            summary = self._summarize_warm(original_content)
            keywords = self._extract_keywords(original_content, 5)
        else:  # COLD
            summary = self._summarize_cold(original_content)
            keywords = self._extract_keywords(original_content, 3)

        compressed = CompressedEntry(
            id=f"cmp_{entry.id}",
            original_id=entry.id,
            tier=tier,
            summary=summary,
            keywords=keywords,
            timestamp=entry.timestamp,
            original_size=original_size,
            compressed_size=len(summary),
        )
        self._compressed[compressed.id] = compressed
        self.stats.total_compressed += 1
        self.stats.bytes_saved += max(0, original_size - len(summary))
        self.stats.last_compress = now
        return compressed

    def get_tier(self, entry_id: str) -> MemoryTier | None:
        entry = self._compressed.get(f"cmp_{entry_id}")
        return entry.tier if entry else None

    def restore(self, entry_id: str) -> CompressedEntry | None:
        """Restore a compressed entry, incrementing access counter."""
        entry = self._compressed.get(f"cmp_{entry_id}")
        if entry:
            entry.access()
        return entry

    def reclassify(self, entry_id: str, access_count: int) -> MemoryTier | None:
        """Reclassify based on new access patterns (promote if accessed)."""
        entry = self._compressed.get(f"cmp_{entry_id}")
        if not entry:
            return None
        new_tier = MemoryTier.HOT if access_count >= self.HOT_ACCESS_MIN else (
            MemoryTier.WARM if access_count >= self.WARM_ACCESS_MIN else entry.tier)
        if new_tier != entry.tier:
            old_tier = entry.tier
            entry.tier = new_tier
            logger.debug(f"TemporalCompressor: {entry_id} {old_tier.value}→{new_tier.value}")
        return new_tier

    def get_stats(self) -> dict[str, Any]:
        """Get compression statistics."""
        return {
            "hot_count": sum(1 for e in self._compressed.values() if e.tier == MemoryTier.HOT),
            "warm_count": sum(1 for e in self._compressed.values() if e.tier == MemoryTier.WARM),
            "cold_count": sum(1 for e in self._compressed.values() if e.tier == MemoryTier.COLD),
            "total_compressed": self.stats.total_compressed,
            "bytes_saved": self.stats.bytes_saved,
            "compression_ratio": round(
                1.0 - self.stats.bytes_saved / max(1, sum(e.original_size for e in self._compressed.values())), 3),
        }

    @staticmethod
    def _extract_keywords(text: str, limit: int = 5) -> list[str]:
        """Lightweight keyword extraction from text."""
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if len(w) > 2:
                freq[w] = freq.get(w, 0) + 1
        return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:limit]]

    @staticmethod
    def _summarize_warm(text: str) -> str:
        """Medium compression: first 2 sentences + key phrases."""
        if not text:
            return ""
        sentences = re.split(r'[。.!!\n]', text)
        summary = " ".join(s.strip() for s in sentences[:3] if s.strip())
        if len(summary) > 300:
            summary = summary[:300] + "..."
        return summary

    @staticmethod
    def _summarize_cold(text: str) -> str:
        """Heavy compression: first sentence + essential keywords only."""
        if not text:
            return ""
        first = re.split(r'[。.!!\n]', text, maxsplit=1)[0].strip()
        if len(first) > 150:
            first = first[:150] + "..."
        return first


# ── RuView Pattern 6: Signal Pre-cleaning Pipeline ──


class CleanStage(str, Enum):
    """Stages in signal pre-cleaning (RuView: Hampel→coherence→dedup)."""
    OUTLIER = "outlier"           # Hampel: reject statistical outliers
    COHERENCE = "coherence"       # SpotFi: check signal coherence and consistency
    DEDUP = "dedup"               # Fresnel/BVP: remove redundant signals


@dataclass
class CleanResult:
    """Result of cleaning a single message."""
    passed: bool
    stage: CleanStage
    reason: str = ""
    quality_score: float = 1.0     # 0.0 (garbage) to 1.0 (clean)


@dataclass
class CleanReport:
    """Report for a batch of cleaned messages."""
    total: int = 0
    passed: int = 0
    rejected: int = 0
    per_stage: dict[str, int] = field(default_factory=dict)
    avg_quality: float = 0.0
    rejections: list[dict] = field(default_factory=list)


class SignalCleaner:
    """RuView-inspired multi-stage signal pre-cleaning pipeline.

    Stage 1: OUTLIER — reject statistically anomalous content (too short/long, bad ratios)
    Stage 2: COHERENCE — check internal consistency (self-contradiction, relevance)
    Stage 3: DEDUP — detect near-duplicate content within session
    """

    # Outlier thresholds
    MIN_CONTENT_LENGTH = 5
    MAX_CONTENT_LENGTH = 50000
    MAX_REPETITION_RATIO = 0.6     # >60% repeated chars = garbage
    MIN_ALPHA_RATIO = 0.05         # <5% alphanumeric = probably noise

    def __init__(self):
        self._seen_hashes: deque[tuple[str, float]] = deque(maxlen=1000)
        self.stats = CleanReport()

    def clean(self, msg: dict, session_id: str = "") -> list[CleanResult]:
        """Run a message through all 3 cleaning stages. Returns list of results.
        A clean message will have all results passed=True.
        """
        results: list[CleanResult] = []
        content = msg.get("content", "")

        # Stage 1: Outlier rejection (Hampel)
        outlier_result = self._check_outlier(content)
        results.append(outlier_result)

        # Stage 2: Coherence check (SpotFi)
        if outlier_result.passed:
            coherence_result = self._check_coherence(content, msg.get("role", ""))
            results.append(coherence_result)
        else:
            results.append(CleanResult(passed=False, stage=CleanStage.COHERENCE,
                                       reason="skipped: outlier", quality_score=0.0))

        # Stage 3: Dedup check (Fresnel)
        prev_passed = all(r.passed for r in results)
        if prev_passed:
            dedup_result = self._check_dedup(content)
            results.append(dedup_result)
        else:
            results.append(CleanResult(passed=False, stage=CleanStage.DEDUP,
                                       reason="skipped: prior failure", quality_score=0.0))

        # Update stats
        self.stats.total += 1
        passed = all(r.passed for r in results)
        if passed:
            self.stats.passed += 1
        else:
            self.stats.rejected += 1
            for r in results:
                if not r.passed:
                    self.stats.per_stage[r.stage.value] = self.stats.per_stage.get(r.stage.value, 0) + 1
                    self.stats.rejections.append({
                        "stage": r.stage.value, "reason": r.reason,
                        "quality": r.quality_score,
                    })

        avg_q = sum(r.quality_score for r in results) / max(len(results), 1)
        self.stats.avg_quality = round(
            (self.stats.avg_quality * (self.stats.total - 1) + avg_q) / self.stats.total, 3)

        return results

    def is_clean(self, results: list[CleanResult]) -> bool:
        """Check if all stages passed."""
        return all(r.passed for r in results)

    def quality_score(self, results: list[CleanResult]) -> float:
        """Get the composite quality score across all stages."""
        if not results:
            return 0.0
        return round(sum(r.quality_score for r in results) / len(results), 3)

    def get_report(self) -> dict[str, Any]:
        """Get the current cleaning report."""
        return {
            "total": self.stats.total,
            "passed": self.stats.passed,
            "rejected": self.stats.rejected,
            "pass_rate": round(self.stats.passed / max(1, self.stats.total), 3),
            "per_stage": dict(self.stats.per_stage),
            "avg_quality": self.stats.avg_quality,
            "recent_rejections": self.stats.rejections[-10:],
        }

    # ── Private stage methods ──

    def _check_outlier(self, content: str) -> CleanResult:
        """Hampel-style: reject statistical outliers based on length, repetition, composition."""
        if not content or not content.strip():
            return CleanResult(passed=False, stage=CleanStage.OUTLIER,
                               reason="empty content", quality_score=0.0)

        length = len(content.strip())

        if length < self.MIN_CONTENT_LENGTH:
            return CleanResult(passed=False, stage=CleanStage.OUTLIER,
                               reason=f"too short ({length} chars)", quality_score=0.2)

        if length > self.MAX_CONTENT_LENGTH:
            return CleanResult(passed=False, stage=CleanStage.OUTLIER,
                               reason=f"too long ({length} chars)", quality_score=0.3)

        # Repetition check: high char repetition = garbage
        if length > 10:
            char_counts = {}
            for c in content:
                char_counts[c] = char_counts.get(c, 0) + 1
            max_repeat = max(char_counts.values(), default=0)
            rep_ratio = max_repeat / length
            if rep_ratio > self.MAX_REPETITION_RATIO:
                return CleanResult(passed=False, stage=CleanStage.OUTLIER,
                                   reason=f"excessive repetition ({rep_ratio:.0%})", quality_score=0.1)

        # Alpha ratio: too few meaningful characters = noise
        alpha_count = sum(1 for c in content if c.isalnum())
        alpha_ratio = alpha_count / max(length, 1)
        if alpha_ratio < self.MIN_ALPHA_RATIO:
            return CleanResult(passed=False, stage=CleanStage.OUTLIER,
                               reason=f"low meaningful content ({alpha_ratio:.0%})", quality_score=0.15)

        return CleanResult(passed=True, stage=CleanStage.OUTLIER,
                           reason="content within normal range", quality_score=0.95)

    def _check_coherence(self, content: str, role: str) -> CleanResult:
        """SpotFi-style: check internal consistency and self-contradiction heuristics."""
        score = 0.9  # start optimistic

        # Check for contradictory markers
        contradictory_patterns = [
            (r'\b(?:yes|no)\b.*\b(?:no|yes)\b', 0.3),     # rapid yes/no oscillation
            (r'\b(?:true|false)\b.*\b(?:false|true)\b', 0.3),
            (r'\b(?:正确|错误)\b.*\b(?:错误|正确)\b', 0.3),
        ]
        for pattern, penalty in contradictory_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= penalty

        # Check for gibberish / unreadable tokens
        gibberish_ratio = len(re.findall(r'\b\w{20,}\b', content)) / max(len(content.split()), 1)
        if gibberish_ratio > 0.1:
            score -= 0.4

        # Check for reasonable sentence structure
        sentences = re.split(r'[。.!?\n]', content)
        short_sentences = sum(1 for s in sentences if 0 < len(s.strip()) < 3)
        if sentences and short_sentences / len(sentences) > 0.5:
            score -= 0.2

        quality = max(0.0, min(1.0, score))
        passed = quality >= 0.4

        return CleanResult(passed=passed, stage=CleanStage.COHERENCE,
                           reason="coherent" if passed else f"low coherence ({quality:.2f})",
                           quality_score=quality)

    def _check_dedup(self, content: str) -> CleanResult:
        """Fresnel-style: detect near-duplicate content via content hashing."""
        content_hash = hashlib.blake2b(content.encode('utf-8', errors='ignore'),
                                       digest_size=8).hexdigest()
        now = time.time()

        # Check recent hashes for duplicates (within last 300 seconds)
        for prev_hash, prev_time in self._seen_hashes:
            if prev_hash == content_hash and (now - prev_time) < 300:
                return CleanResult(passed=False, stage=CleanStage.DEDUP,
                                   reason="near-duplicate content", quality_score=0.05)

        self._seen_hashes.append((content_hash, now))
        return CleanResult(passed=True, stage=CleanStage.DEDUP,
                           reason="unique content", quality_score=1.0)


@dataclass
class ExcludeRule:
    """A pattern-based rule for excluding entries from memory capture (Clibor-inspires)."""
    pattern: str                      # Regex pattern to match
    description: str = ""             # Why this exclusion exists
    match_field: str = "content"      # Which entry field to match: "content", "role", "fact", "rel", or "all"
    enabled: bool = True
    priority: int = 0                 # Higher = checked first
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0               # How many times this rule was triggered
    last_hit: float = 0.0            # When it was last triggered

    def matches(self, entry) -> bool:
        """Check if this rule matches an EventEntry (or message dict)."""
        if not self.enabled or not self.pattern:
            return False
        try:
            regex = re.compile(self.pattern, re.IGNORECASE)
        except re.error:
            return False
        if isinstance(entry, dict):
            content = entry.get("content", "")
            role = entry.get("role", "")
        else:
            content = getattr(entry, "content", "")
            role = getattr(entry, "role", "")
            fact = getattr(entry, "fact_perspective", "")
            rel = getattr(entry, "rel_perspective", "")

        if self.match_field == "role":
            return bool(regex.search(role))
        elif self.match_field == "fact":
            return bool(regex.search(fact))
        elif self.match_field == "rel":
            return bool(regex.search(rel))
        elif self.match_field == "all":
            return bool(regex.search(content) or regex.search(fact) or regex.search(rel))
        else:  # "content" (default)
            return bool(regex.search(content))


@dataclass
class EventEntry:
    """A single memory entry with dual-perspective content."""
    id: str
    session_id: str
    timestamp: str
    role: str
    content: str
    fact_perspective: str = ""
    rel_perspective: str = ""
    embedding: list[float] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    persona_domain: str = ""
    emotional_valence: float = 0.0

    def text_for_retrieval(self) -> str:
        parts = [self.fact_perspective]
        if self.rel_perspective:
            parts.append(self.rel_perspective)
        return " ".join(parts) or self.content[:200]


@dataclass
class SynthesisBlock:
    """A consolidated cross-event synthesis block."""
    id: str
    timestamp: str
    content: str
    source_entries: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)

    def text_for_retrieval(self) -> str:
        return self.content


@dataclass
class MemoryBuffer:
    """Buffered unconsolidated entries since last consolidation."""
    entries: list[EventEntry] = field(default_factory=list)
    first_timestamp: str = ""
    last_timestamp: str = ""

    def add(self, entry: EventEntry) -> None:
        self.entries.append(entry)
        if not self.first_timestamp:
            self.first_timestamp = entry.timestamp
        self.last_timestamp = entry.timestamp

    def elapsed_seconds(self) -> float:
        if not self.first_timestamp:
            return 0.0
        try:
            first = datetime.fromisoformat(self.first_timestamp)
            return (datetime.now(timezone.utc) - first).total_seconds()
        except Exception:
            return 0.0

    def clear(self) -> None:
        self.entries.clear()
        self.first_timestamp = ""
        self.last_timestamp = ""


# ── Hindsight-inspired Mental Model → Opinion Synthesis ──

@dataclass
class Opinion:
    """A synthesized opinion extracted from consolidated memories (Hindsight pattern)."""
    text: str
    confidence: float            # 0.0-1.0, how strongly held
    evidence_count: int          # Number of supporting memory entries
    category: str = "general"    # "preference", "behavior", "skill", "risk", "relationship"
    sources: list[str] = field(default_factory=list)  # Source entry IDs
    created_at: str = ""
    last_updated: str = ""

    def __post_init__(self):
        from datetime import datetime as _dt
        ts = _dt.now().isoformat()
        if not self.created_at:
            self.created_at = ts
        self.last_updated = ts


@dataclass
class MentalModel:
    """A mental model distilled from conversation patterns and opinions."""
    model_id: str
    name: str
    description: str
    opinions: list[Opinion] = field(default_factory=list)
    category: str = "general"
    confidence: float = 0.0
    evidence_sessions: int = 0
    created_at: str = ""
    last_updated: str = ""

    def __post_init__(self):
        from datetime import datetime as _dt
        ts = _dt.now().isoformat()
        if not self.created_at:
            self.created_at = ts
        self.last_updated = ts


# Opinion synthesis prompt (heuristic extraction from consolidated memory)
OPINION_SYNTHESIS_PROMPT = """From the conversation memories below, extract user opinions, preferences,
behavioral patterns, and risk indicators.

Memory context:
{memory_context}

Extract:
1. Preferences: what tools, languages, approaches does the user prefer?
2. Behavioral patterns: recurring work habits, decision-making style
3. Risk indicators: noted concerns, past failures, areas of caution
4. Skill indicators: what is the user proficient at or learning?

Rules:
- One opinion per line, prefixed with "- "
- Include confidence estimate in [brackets]: [high], [medium], [low]
- Reference specific events when possible
- Keep each opinion under 100 words
- Limit to 8 opinions maximum

Extracted opinions:"""


FACT_EXTRACT_PROMPT = """Extract factual events from the following conversation utterance.
Focus on objective, verifiable facts: who did what, when, where, what was said.

Rules:
- Output one fact per line, prefixed with "- "
- Keep each fact under 80 words
- Use the speaker's actual name (not "User" or "AI")
- Only include facts explicitly stated in the utterance
- Do not infer or speculate

Utterance: {utterance}

Factual entries:"""


REL_EXTRACT_PROMPT = """Extract relational dynamics from the following conversation utterance.
Focus on: interpersonal dynamics, causal influences, emotional tone shifts,
preference changes, temporal dependencies, and decision-making context.

Rules:
- Output one relation per line, prefixed with "- "
- Keep each relation under 60 words
- Describe how this utterance relates to the broader conversation
- Note any changes in: relationship, goal, preference, emotional state
- Only include relations grounded in the utterance

Utterance: {utterance}

Relational entries:"""


CONSOLIDATION_PROMPT = """Synthesize cross-event connections from the following temporally related events.

Below are two groups:
[BUFFER EVENTS] — recent unconsolidated events
[HISTORICAL EVENTS] — semantically similar past events retrieved from memory

Identify connections across time that reveal:
1. Causal chains (X caused Y)
2. Preference evolution (user started wanting X, now wants Y)
3. Repeated patterns (similar situations that recur)
4. Unresolved threads (questions or tasks left incomplete)
5. Temporal progressions (how something changed over time)

Rules:
- Be specific: cite which events you're connecting
- Only assert connections supported by both event groups
- Format: "- [connection type]: specific description"
- Limit to 5-8 synthesized connections
- If no meaningful connections exist, say "NO_CONNECTIONS"

{context}

Cross-event synthesis:"""


class StructMemory:
    """Hierarchical memory with dual-perspective binding and batch consolidation."""

    CONSOLIDATION_THRESHOLD_SECONDS = 300  # 5 minutes
    SEMANTIC_SEEDS = 15
    DEFAULT_RETRIEVAL_TOP_K = 60
    DEFAULT_SYNTHESIS_BLOCKS = 5

    def __init__(self, world: Any = None):
        self._world = world
        self._entries: dict[str, EventEntry] = {}
        self._synthesis: list[SynthesisBlock] = []
        self._buffer = MemoryBuffer()
        self._last_consolidation: float = 0.0
        self._stats = {
            "entries_total": 0,
            "synthesis_total": 0,
            "consolidation_count": 0,
            "bind_count": 0,
        }
        # Exclusion management (Clibor-inspired)
        self._exclude_rules: list[ExcludeRule] = []
        self._exclude_stats = {"blocked_total": 0, "blocked_by_rule": {}}
        self._seed_default_exclusions()
        # RuView Pattern 4: Temporal Compress — hot/warm/cold memory tiering
        self.temporal_compressor = TemporalCompressor()
        # RuView Pattern 6: Signal Pre-cleaning — multi-stage message cleaning
        self.signal_cleaner = SignalCleaner()

    def _seed_default_exclusions(self) -> None:
        """Pre-configure sensible default exclusion patterns."""
        defaults = [
            ExcludeRule(r"^\s*$", "Empty or whitespace-only content", match_field="content"),
            ExcludeRule(r"^(ok|yes|no|thanks|thank you|got it|sure)[.!]*$",
                        "Single-word acknowledgments", match_field="content"),
            ExcludeRule(r"^[^\w]*$", "Content with no alphanumeric characters", match_field="content"),
        ]
        for rule in defaults:
            self.add_exclude_rule(rule)

    def add_exclude_rule(self, rule_or_pattern, description: str = "", 
                         match_field: str = "content", enabled: bool = True) -> ExcludeRule:
        """Add an exclusion rule. Accepts ExcludeRule or (pattern, description) pair.
        Returns the added rule.
        """
        if isinstance(rule_or_pattern, ExcludeRule):
            rule = rule_or_pattern
        else:
            rule = ExcludeRule(
                pattern=rule_or_pattern, description=description,
                match_field=match_field, enabled=enabled,
            )
        self._exclude_rules.append(rule)
        self._exclude_rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"StructMem: added exclude rule '{rule.description or rule.pattern[:40]}'")
        return rule

    def remove_exclude_rule(self, index: int) -> bool:
        """Remove an exclusion rule by its index in the list."""
        if 0 <= index < len(self._exclude_rules):
            rule = self._exclude_rules.pop(index)
            logger.debug(f"StructMem: removed exclude rule '{rule.description}'")
            return True
        return False

    def list_exclude_rules(self) -> list[dict]:
        """List all exclusion rules with status and hit counts."""
        return [
            {"index": i, "pattern": r.pattern, "description": r.description,
             "match_field": r.match_field, "enabled": r.enabled,
             "hit_count": r.hit_count}
            for i, r in enumerate(self._exclude_rules)
        ]

    def toggle_exclude_rule(self, index: int) -> bool:
        """Toggle an exclusion rule on/off."""
        if 0 <= index < len(self._exclude_rules):
            self._exclude_rules[index].enabled = not self._exclude_rules[index].enabled
            return True
        return False

    def get_exclude_stats(self) -> dict[str, Any]:
        """Get statistics about excluded entries."""
        return {
            "total_blocked": self._exclude_stats["blocked_total"],
            "rules_count": len(self._exclude_rules),
            "rules_enabled": sum(1 for r in self._exclude_rules if r.enabled),
            "top_rules": sorted(
                [{"pattern": r.pattern[:50], "hits": r.hit_count}
                 for r in self._exclude_rules if r.hit_count > 0],
                key=lambda x: x["hits"], reverse=True,
            )[:5],
        }

    def _should_exclude(self, msg: dict) -> tuple[bool, ExcludeRule | None]:
        """Check if a message should be excluded from memory.
        Returns (should_exclude, matched_rule).
        """
        for rule in self._exclude_rules:
            if rule.matches(msg):
                rule.hit_count += 1
                rule.last_hit = time.time()
                self._exclude_stats["blocked_total"] += 1
                rule_name = rule.description or rule.pattern[:30]
                self._exclude_stats["blocked_by_rule"][rule_name] = self._exclude_stats["blocked_by_rule"].get(rule_name, 0) + 1
                return True, rule
        return False, None

    async def bind_events(
        self,
        session_id: str,
        messages: list[dict],
        timestamp: str | None = None,
    ) -> list[EventEntry]:
        """Extract dual-perspective entries from a set of conversation messages.

        Called after each LifeEngine cycle. Extracts FACT and RELATION
        perspectives for user and assistant messages.

        Args:
            session_id: Current session identifier
            messages: List of {"role": "user"|"assistant", "content": "..."}
            timestamp: ISO timestamp (defaults to now)

        Returns:
            List of newly created EventEntry objects
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        new_entries = []

        for msg in messages:
            if msg.get("role") not in ("user", "assistant"):
                continue
            content = msg.get("content", "").strip()
            if not content or len(content) < 10:
                continue
            
            # Exclusion check (Clibor-inspired): skip matching entries
            should_skip, matched_rule = self._should_exclude(msg)
            if should_skip:
                logger.trace(
                    f"StructMem: excluded message matching '{matched_rule.description or matched_rule.pattern[:30]}'"
                )
                continue

            # Signal pre-cleaning (RuView-inspired): Hampel→coherence→dedup
            clean_results = self.signal_cleaner.clean(msg, session_id)
            if not self.signal_cleaner.is_clean(clean_results):
                quality = self.signal_cleaner.quality_score(clean_results)
                if quality < 0.3:  # hard reject
                    logger.trace(f"StructMem: signal rejected (quality={quality:.2f})")
                    continue
                # soft pass: low quality but still bind with reduced processing
                logger.trace(f"StructMem: marginal signal (quality={quality:.2f}), binding anyway")

            entry_id = self._make_id(session_id, ts, msg["role"])
            if entry_id in self._entries:
                continue

            fact = await self._extract_fact(content)
            rel = await self._extract_rel(content)

            embedding = await self._compute_embedding(fact + " " + rel)

            entry = EventEntry(
                id=entry_id,
                session_id=session_id,
                timestamp=ts,
                role=msg["role"],
                content=content,
                fact_perspective=fact,
                rel_perspective=rel,
                embedding=embedding,
                sources=[session_id],
            )

            self._entries[entry_id] = entry
            self._buffer.add(entry)
            new_entries.append(entry)
            self._stats["entries_total"] += 1

        # Cap entries at 10_000 to prevent unbounded memory growth
        if len(self._entries) > 10_000:
            excess = list(self._entries.keys())[:len(self._entries) - 10_000]
            for k in excess:
                self._entries.pop(k, None)
        # Cap synthesis at 500
        if len(self._synthesis) > 500:
            self._synthesis = self._synthesis[-500:]

        self._stats["bind_count"] += 1
        logger.debug(f"StructMem bound {len(new_entries)} entries (total={self._stats['entries_total']})")
        return new_entries

    async def consolidate_if_needed(self) -> list[SynthesisBlock]:
        """Trigger batch consolidation if buffer exceeds time threshold.

        Returns newly created synthesis blocks, or empty list if not yet due.
        """
        if self._buffer.elapsed_seconds() < self.CONSOLIDATION_THRESHOLD_SECONDS:
            return []

        if len(self._buffer.entries) < 3:
            return []

        return await self._consolidate()

    async def _consolidate(self) -> list[SynthesisBlock]:
        """Execute a full consolidation cycle."""
        new_blocks = []

        buf = self._buffer
        if not buf.entries:
            return []

        cons_id = self._make_id("consolidation", datetime.now(timezone.utc).isoformat(), "synth")

        # Build query from all buffer entries
        query_text = " ".join(
            e.fact_perspective + " " + e.rel_perspective
            for e in buf.entries[-10:]
        )
        query_embedding = await self._compute_embedding(query_text)

        # Retrieve semantically similar historical entries
        seeds = await self._semantic_retrieve(query_embedding, top_k=self.SEMANTIC_SEEDS)

        # Reconstruct complete events from seed timestamps
        reconstructed = self._reconstruct_events(seeds, buf.entries)

        if not reconstructed:
            self._buffer.clear()
            return []

        # Synthesize cross-event connections via LLM
        synthesis_text = await self._synthesize(buf.entries, reconstructed)

        if synthesis_text and "NO_CONNECTIONS" not in synthesis_text:
            block = SynthesisBlock(
                id=cons_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                content=synthesis_text,
                source_entries=[s.id for s in seeds] + [e.id for e in buf.entries[:5]],
                session_ids=list(set(e.session_id for e in buf.entries)),
            )
            self._synthesis.append(block)
            new_blocks.append(block)
            self._stats["synthesis_total"] += 1

        self._stats["consolidation_count"] += 1
        self._buffer.clear()
        self._last_consolidation = time.time()

        logger.debug(
            f"StructMem consolidated: {len(buf.entries)}→{len(new_blocks)} "
            f"synthesis (total={self._stats['synthesis_total']})"
        )
        return new_blocks

    async def retrieve_for_query(
        self,
        query: str,
        top_k: int = 60,
        n_synthesis: int = 5,
        user_only: bool = False,
        persona_domain: str = "",
    ) -> tuple[list[EventEntry], list[SynthesisBlock]]:
        """Retrieve entries and synthesis blocks for context injection.

        Args:
            query: The user query
            top_k: Number of entries to retrieve
            n_synthesis: Number of synthesis blocks to retrieve

        Returns:
            (entries, synthesis) — both sorted by relevance
        """
        query_embedding = await self._compute_embedding(query)

        scored_entries = []
        for entry in self._entries.values():
            if user_only and entry.role != "user":
                continue
            if persona_domain and entry.persona_domain != persona_domain:
                continue
            score = self._cosine_similarity(query_embedding, entry.embedding)
            scored_entries.append((score, entry))
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        entries = [e for _, e in scored_entries[:top_k]]

        scored_synth = []
        for block in self._synthesis:
            block_emb = await self._compute_embedding(block.content)
            score = self._cosine_similarity(query_embedding, block_emb)
            scored_synth.append((score, block))
        scored_synth.sort(key=lambda x: x[0], reverse=True)
        synthesis = [b for _, b in scored_synth[:n_synthesis]]

        return entries, synthesis

    def get_context_block(self, query: str = "", entries: list[EventEntry] | None = None,
                          synthesis: list[SynthesisBlock] | None = None) -> str:
        """Format retrieved memory for injection into the model's system prompt.

        Args:
            query: The original query (for context)
            entries: Pre-retrieved entries (auto-retrieves if None)
            synthesis: Pre-retrieved synthesis blocks (auto-retrieves if None)

        Returns:
            Formatted context block string for LLM prompt injection
        """
        parts = []

        if synthesis:
            parts.append("[RELEVANT MEMORY SYNTHESIS]")
            for i, block in enumerate(synthesis[:5]):
                parts.append(f"S{i+1}: {block.content}")

        if entries:
            parts.append("[RELATED PAST EVENTS]")
            for i, entry in enumerate(entries[:20]):
                ts_short = entry.timestamp[:19] if entry.timestamp else "?"
                role = "U" if entry.role == "user" else "A"
                text = entry.fact_perspective or entry.content[:100]
                parts.append(f"[{ts_short}] {role}: {text}")

        return "\n".join(parts) if parts else ""

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "buffer_size": len(self._buffer.entries),
            "buffer_age_s": int(self._buffer.elapsed_seconds()),
            "total_entries_stored": len(self._entries),
            "total_synthesis_stored": len(self._synthesis),
            "exclude_rules": len(self._exclude_rules),
            "exclude_rules_enabled": sum(1 for r in self._exclude_rules if r.enabled),
            "blocked_total": self._exclude_stats["blocked_total"],
        }

    # ── Hindsight-inspired Opinion Synthesis ──

    def synthesize_opinions(self, limit: int = 8) -> list[Opinion]:
        """Extract opinions and preferences from consolidated synthesis blocks.

        Hindsight pattern: opinion synthesis from consolidated memory.
        Uses heuristic extraction from synthesis blocks without LLM calls,
        making it fast and free. For LLM-enhanced extraction, use
        synthesize_opinions_llm().

        Returns:
            List of Opinion objects extracted from memory patterns.
        """
        opinions: list[Opinion] = []

        # Heuristic: extract structured opinions from synthesis content
        for block in self._synthesis:
            content = block.content
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if not line.startswith("- "):
                    continue
                text = line[2:].strip()
                if len(text) < 10:
                    continue

                # Determine category from content keywords
                category = self._opinion_category(text)

                # Estimate confidence from evidence count
                confidence = min(0.9, 0.3 + 0.1 * len(block.session_ids))

                opinions.append(Opinion(
                    text=text,
                    confidence=confidence,
                    evidence_count=len(block.source_entries),
                    category=category,
                    sources=block.source_entries,
                ))

            if len(opinions) >= limit:
                break

        if not opinions:
            # Fallback: generate from entry patterns
            opinions = self._extract_pattern_opinions(limit)

        return opinions[:limit]

    def _opinion_category(self, text: str) -> str:
        """Classify an opinion text into a category based on keywords."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["prefer", "喜欢", "偏好", "常用", "选择"]):
            return "preference"
        if any(kw in text_lower for kw in ["pattern", "习惯", "usually", "总是", "经常"]):
            return "behavior"
        if any(kw in text_lower for kw in ["skill", "proficient", "擅长", "熟练", "精通"]):
            return "skill"
        if any(kw in text_lower for kw in ["risk", "危险", "失败", "错误", "warning", "caution"]):
            return "risk"
        if any(kw in text_lower for kw in ["relationship", "合作", "依赖", "conflict"]):
            return "relationship"
        return "general"

    def _extract_pattern_opinions(self, limit: int = 5) -> list[Opinion]:
        """Fallback: extract pattern-based opinions from raw entry facts."""
        opinions: list[Opinion] = []
        fact_counts: dict[str, int] = {}

        # Count frequently mentioned concepts in fact perspectives
        for entry in list(self._entries.values())[-100:]:
            if entry.fact_perspective:
                words = entry.fact_perspective.lower().split()
                word_pairs = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
                for pair in word_pairs:
                    if len(pair) > 6:
                        fact_counts[pair] = fact_counts.get(pair, 0) + 1

        # Top patterns as opinions
        sorted_patterns = sorted(fact_counts.items(), key=lambda x: x[1], reverse=True)
        for phrase, count in sorted_patterns[:limit]:
            if count >= 2:
                opinions.append(Opinion(
                    text=f"Recurring pattern: {phrase}",
                    confidence=min(0.8, 0.2 + count * 0.1),
                    evidence_count=count,
                    category="behavior",
                ))

        return opinions

    def build_mental_model(self, name: str = "default") -> MentalModel:
        """Build a mental model from synthesized opinions and memory stats.

        Hindsight pattern: distill a coherent mental model from accumulated
        opinions, preferences, and behavioral patterns.

        Returns:
            MentalModel with aggregated opinions and confidence metrics.
        """
        import uuid

        opinions = self.synthesize_opinions(limit=12)
        stats = self.get_stats()

        # Score model confidence from stats density
        evidence_sessions = len(set(
            eid.split("_")[0] for eid in self._entries if hasattr(eid, 'split')
        )) or stats.get("bind_count", 0)

        confidence = min(0.95, 0.1 + len(opinions) * 0.05 + evidence_sessions * 0.01)

        return MentalModel(
            model_id=str(uuid.uuid4())[:8],
            name=name,
            description=f"Mental model built from {stats.get('bind_count', 0)} interactions, "
                        f"{stats.get('synthesis_total', 0)} syntheses, "
                        f"{len(opinions)} opinions",
            opinions=opinions,
            category="user_model",
            confidence=confidence,
            evidence_sessions=evidence_sessions,
        )

    async def synthesize_opinions_llm(self, limit: int = 8) -> list[Opinion]:
        """LLM-enhanced opinion synthesis from consolidated memory (Hindsight).

        Uses the consciousness layer to extract deeper insights from memory
        synthesis blocks. More accurate than heuristic extraction, but costs tokens.
        """
        if not self._world:
            return self.synthesize_opinions(limit)

        consciousness = getattr(self._world, 'consciousness', None)
        if not consciousness:
            return self.synthesize_opinions(limit)

        # Build memory context from synthesis blocks
        context_parts: list[str] = []
        for i, block in enumerate(self._synthesis[-10:]):  # Last 10 blocks
            context_parts.append(f"[Block {i+1}] {block.content}")
        for i, entry in enumerate(list(self._entries.values())[-20:]):  # Last 20 entries
            context_parts.append(f"[Event {i+1}] {entry.fact_perspective or entry.content[:200]}")

        memory_context = "\n".join(context_parts)
        if len(memory_context) < 100:
            return self.synthesize_opinions(limit)

        try:
            prompt = OPINION_SYNTHESIS_PROMPT.format(memory_context=memory_context[:4000])
            result = await consciousness.chain_of_thought(
                prompt, steps=1, temperature=0.3, max_tokens=1024,
            )
            lines = result.strip().split("\n")
            opinions: list[Opinion] = []
            for line in lines:
                line = line.strip()
                if not line.startswith("- "):
                    continue
                text = line[2:].strip()
                # Extract confidence bracket
                confidence = 0.5
                for bracket, val in [("[high]", 0.8), ("[medium]", 0.5), ("[low]", 0.3)]:
                    if bracket in text.lower():
                        confidence = val
                        text = text.lower().replace(bracket, "").strip()
                        break
                if len(text) >= 10:
                    category = self._opinion_category(text)
                    opinions.append(Opinion(
                        text=text,
                        confidence=confidence,
                        evidence_count=min(10, len(self._synthesis)),
                        category=category,
                    ))
            return opinions[:limit]
        except Exception as e:
            logger.debug(f"LLM opinion synthesis: {e}")
            return self.synthesize_opinions(limit)

    # ── Private helpers ──

    async def _extract_fact(self, utterance: str) -> str:
        try:
            engine = getattr(self._world, 'extraction_engine', None) if self._world else None
            if engine and engine._lx_available:
                results = engine.extract(
                    text=utterance[:3000],
                    classes=["fact"],
                    prompt_description=FACT_EXTRACT_PROMPT.format(utterance="{text}"),
                    model_id="",
                )
                if results:
                    return "\n".join(
                        f"- {r.extraction_text}  [{r.char_start}:{r.char_end}]"
                        for r in results[:10]
                    )
        except Exception as e:
            logger.debug(f"StructMem grounded fact: {e}")

        # Fallback: raw LLM extraction
        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    FACT_EXTRACT_PROMPT.format(utterance=utterance[:2000]),
                    steps=1, temperature=0.3, max_tokens=512,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem fact extract: {e}")
        return utterance[:200]

    async def _extract_rel(self, utterance: str) -> str:
        try:
            engine = getattr(self._world, 'extraction_engine', None) if self._world else None
            if engine and engine._lx_available:
                results = engine.extract(
                    text=utterance[:3000],
                    classes=["relation"],
                    prompt_description=REL_EXTRACT_PROMPT.format(utterance="{text}"),
                    model_id="",
                )
                if results:
                    return "\n".join(
                        f"- {r.extraction_text}  [{r.char_start}:{r.char_end}]"
                        for r in results[:10]
                    )
        except Exception as e:
            logger.debug(f"StructMem grounded rel: {e}")

        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    REL_EXTRACT_PROMPT.format(utterance=utterance[:2000]),
                    steps=1, temperature=0.3, max_tokens=512,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem rel extract: {e}")
        return ""

    async def _compute_embedding(self, text: str) -> list[float]:
        if not text:
            return []
        try:
            vs = self._world.vector_store if self._world else None
            if vs and hasattr(vs, 'encode'):
                emb = await vs.encode(text)
                return emb.tolist() if hasattr(emb, 'tolist') else list(emb)
        except Exception as e:
            logger.warning(f"db query: {e}")
            return []

    async def proactive_episodic_extract(
        self,
        messages: list[dict],
        session_id: str = "",
        persona_domains: list[str] = None,
    ) -> list[EventEntry]:
        """PersonaVLM proactive episodic extraction trigger.

        Scans full conversation context (not single utterances) to extract
        user episodic memories tagged with persona domains. Triggered on
        conversation milestones (topic shifts, 5+ turns, session boundaries).

        Args:
            messages: Full conversation history [{role, content}, ...]
            session_id: Session identifier for tagging
            persona_domains: Specific domains to target (core_identity, episodic, etc.)

        Returns:
            Newly extracted episodic EventEntry objects tagged with persona_domain.
        """
        if persona_domains is None:
            persona_domains = ["episodic", "core_identity", "procedural"]

        new_entries: list[EventEntry] = []
        usr_msgs = [m for m in messages if m.get("role") == "user"]
        if len(usr_msgs) < 3:
            return new_entries

        for i, msg in enumerate(usr_msgs):
            content = msg.get("content", "")
            pos_score = min(1.0, (i + 1) / len(usr_msgs))

            for domain in persona_domains:
                signal = persona_domain_signal(content, domain)
                if signal < 0.3:
                    continue

                import uuid
                entry = EventEntry(
                    id=str(uuid.uuid4())[:12],
                    session_id=session_id,
                    timestamp=msg.get("timestamp", ""),
                    role="user",
                    content=content[:500],
                    fact_perspective=extract_fact_perspective(content) if "extract_fact_perspective" in dir() else content[:200],
                    persona_domain=domain,
                    emotional_valence=pos_score,
                )
                if content:
                    entry.embedding = await self._compute_embedding(content[:500])
                new_entries.append(entry)
                self._entries[entry.id] = entry

        return new_entries


def persona_domain_signal(content: str, domain: str) -> float:
    """Heuristic signal scoring for persona domain classification."""
    signals = {
        "core_identity": ["i am", "my name", "i work", "i live", "my role", "我叫", "我是", "我做"],
        "episodic": ["happened", "yesterday", "last week", "just now", "i did", "i went", "发生", "昨天", "上次"],
        "procedural": ["always", "usually", "i tend", "my workflow", "i prefer to", "习惯", "通常", "一般"],
        "semantic": ["i know", "i learned", "i studied", "my understanding", "我知道", "我学过", "我认为"],
    }
    markers = signals.get(domain, [])
    if not markers:
        return 0.0
    lower = content.lower()
    hits = sum(1 for m in markers if m.lower() in lower)
    return min(1.0, hits * 0.3 + 0.1)


def extract_fact_perspective(content: str) -> str:
    parts = [s.strip() for s in content.replace("!", ".").replace("？", "。").replace("?", ".").split(".") if s.strip()]
    relevant = [p for p in parts if any(kw in p.lower() for kw in
        ["i am", "i work", "i did", "i know", "i need", "i want", "i prefer",
         "我是", "我在", "我做", "我需要", "我想要"])]
    return "; ".join(relevant[:3]) if relevant else content[:200]


# ═══ LightMem-compatible summarize() API ═══

class SummaryStore:
    """Pluggable summary storage backend (LightMem-compatible).

    Supports:
      - memory: in-memory dict (default)
      - qdrant:  Qdrant vector DB (optional, pip install qdrant-client)
    """

    def __init__(self, backend: str = "memory", **kwargs):
        self._backend = backend
        self._store: dict[str, SynthesisBlock] = {}
        self._qdrant = None
        if backend == "qdrant":
            self._init_qdrant(**kwargs)

    def _init_qdrant(self, collection_name: str = "livingtree_summaries",
                     embedding_dim: int = 384, path: str = ""):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        import os
        store_path = path or os.path.expanduser("~/.livingtree/qdrant_summaries")
        os.makedirs(store_path, exist_ok=True)
        self._qdrant = QdrantClient(path=store_path)
        try:
            self._qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )
        except Exception:
            pass
        logger.info("StructMem: Qdrant summary store initialized at %s", store_path)

    def put(self, block_id: str, block: SynthesisBlock, embedding: list = None):
        if self._backend == "qdrant" and self._qdrant and embedding:
            try:
                from qdrant_client.models import PointStruct
                self._qdrant.upsert(
                    collection_name="livingtree_summaries",
                    points=[PointStruct(id=hash(block_id) % (2**63), vector=embedding, payload={
                        "id": block_id, "content": block.content[:1000],
                        "timestamp": block.timestamp,
                    })],
                )
            except Exception:
                self._store[block_id] = block
        else:
            self._store[block_id] = block

    def search(self, query_vector: list, top_k: int = 10) -> list[SynthesisBlock]:
        if self._backend == "qdrant" and self._qdrant:
            try:
                results = self._qdrant.search(
                    collection_name="livingtree_summaries",
                    query_vector=query_vector, limit=top_k,
                )
                return [
                    SynthesisBlock(
                        id=r.payload.get("id", ""),
                        timestamp=r.payload.get("timestamp", ""),
                        content=r.payload.get("content", ""),
                    )
                    for r in results
                ]
            except Exception:
                pass
        scored = [(bid, 0.0) for bid in self._store.keys()]
        return [self._store[bid] for bid, _ in scored[:top_k]]

    def count(self) -> int:
        return len(self._store)


async def structmem_summarize(
    memory: StructMemory,
    time_window: int = 3600,
    top_k: int = 15,
    scope: str = "global",
    summary_store: SummaryStore = None,
) -> list[SynthesisBlock]:
    """LightMem-compatible summarize() — cross-event semantic consolidation.

    Args:
        memory: StructMemory instance
        time_window: time window in seconds for grouping events
        top_k: number of seed events for consolidation
        scope: "global" (all sessions) or "session" (current only)
        summary_store: optional Qdrant/memory store for persistence

    Returns:
        List of SynthesisBlock summary blocks.

    This matches LightMem's summarize() API exactly:
      LightMem: lightmem.summarize(retrieval_scope="global", time_window=3600, top_k=15)
      LivingTree: await structmem_summarize(memory, time_window=3600, top_k=15)
    """
    if scope == "global":
        blocks = await memory.consolidate_window(window_seconds=time_window)
    else:
        blocks = await memory.consolidate_if_needed()

    if summary_store and blocks:
        embeddings = []
        for block in blocks:
            if hasattr(memory, '_vector_store'):
                try:
                    emb = getattr(memory._vector_store, 'embed', lambda x: [])(block.content[:1000])
                    embeddings.append(emb if isinstance(emb, list) else [])
                except Exception:
                    embeddings.append([])
            else:
                embeddings.append([])

        for block, emb in zip(blocks, embeddings):
            summary_store.put(block.id, block, emb)

    logger.info(
        "StructMem: summarized %d blocks (window=%ds, scope=%s)",
        len(blocks), time_window, scope,
    )
    return blocks


    async def _semantic_retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 15,
    ) -> list[EventEntry]:
        if not query_embedding:
            return list(self._entries.values())[-top_k:]

        scored = []
        for entry in self._entries.values():
            if entry.id in {e.id for e in self._buffer.entries}:
                continue
            score = self._cosine_similarity(query_embedding, entry.embedding)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def _reconstruct_events(
        self,
        seeds: list[EventEntry],
        buffer_entries: list[EventEntry],
    ) -> list[EventEntry]:
        seen_ids = {e.id for e in buffer_entries}
        result = list(buffer_entries)

        for seed in seeds:
            if seed.id in seen_ids:
                continue
            for entry in self._entries.values():
                if entry.timestamp == seed.timestamp and entry.id not in seen_ids:
                    result.append(entry)
                    seen_ids.add(entry.id)

        return result

    async def _synthesize(
        self,
        buffer_entries: list[EventEntry],
        reconstructed: list[EventEntry],
    ) -> str:
        buf_text = "\n".join(
            f"[{e.timestamp[:19]}] {e.role}: {e.fact_perspective or e.content[:100]}"
            for e in buffer_entries[-10:]
        )
        hist_text = "\n".join(
            f"[{e.timestamp[:19]}] {e.role}: {e.fact_perspective or e.content[:100]}"
            for e in reconstructed[:15]
            if e not in buffer_entries
        )

        context = (
            f"[BUFFER EVENTS]\n{buf_text}\n\n"
            f"[HISTORICAL EVENTS]\n{hist_text}"
        )

        try:
            consciousness = self._world.consciousness if self._world else None
            if consciousness:
                result = await consciousness.chain_of_thought(
                    CONSOLIDATION_PROMPT.format(context=context),
                    steps=2,
                    temperature=0.5,
                    max_tokens=1024,
                )
                return result.strip()
        except Exception as e:
            logger.debug(f"StructMem synthesis: {e}")

        return ""

    # ── RuView Pattern 4: Temporal Compress integration ──

    def compress_aged_entries(self) -> CompressStats:
        """Compress entries older than WARM_THRESHOLD to save memory.
        HOT entries untouched, WARM→medium compression, COLD→heavy compression.
        """
        count = 0
        for entry_id, entry in list(self._entries.items()):
            tier = self.temporal_compressor.classify(entry)
            if tier == MemoryTier.HOT:
                continue
            if self.temporal_compressor.get_tier(entry_id) is not None:
                continue
            compressed = self.temporal_compressor.compress(entry, tier)
            count += 1
        if count > 0:
            logger.info(f"StructMem: compressed {count} entries")
        return self.temporal_compressor.stats

    def get_temporal_stats(self) -> dict:
        tc_stats = self.temporal_compressor.get_stats()
        return {**tc_stats, "total_entries": len(self._entries),
                "compression_active": tc_stats["total_compressed"] > 0}

    # ── RuView Pattern 6: Memory health report ──

    def get_memory_health(self) -> dict[str, Any]:
        clean_report = self.signal_cleaner.get_report()
        tc_stats = self.temporal_compressor.get_stats()
        return {
            "entries": self._stats["entries_total"],
            "synthesis_blocks": self._stats["synthesis_total"],
            "consolidations": self._stats["consolidation_count"],
            "bind_count": self._stats["bind_count"],
            "excluded": self.get_exclude_stats(),
            "signal_quality": {"pass_rate": clean_report["pass_rate"],
                               "avg_quality": clean_report["avg_quality"],
                               "per_stage": clean_report["per_stage"]},
            "temporal_compress": {"hot": tc_stats["hot_count"],
                                  "warm": tc_stats["warm_count"],
                                  "cold": tc_stats["cold_count"],
                                  "bytes_saved": tc_stats["bytes_saved"],
                                  "ratio": tc_stats["compression_ratio"]},
        }

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _make_id(session: str, ts: str, role: str) -> str:
        import hashlib
        raw = f"{session}:{ts}:{role}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    # ── sql-flow Pattern 2: Tumbling Window Aggregation ──

    async def consolidate_window(self, window_seconds: int = 300,
                                  session_id: str = "") -> list[SynthesisBlock]:
        """sql-flow tumbling window: GROUP BY tumble(timestamp, INTERVAL window).
        Aggregates events within a sliding time window into synthesis blocks.
        Differs from consolidate_if_needed() which uses a simple time threshold.
        """
        if not self._buffer.entries:
            return []
        try:
            window_start = self._buffer.first_timestamp
            window_dt = datetime.fromisoformat(window_start)
            window_end = window_dt.timestamp() + window_seconds
        except Exception:
            return []

        # Group entries within the window
        in_window = []
        beyond_window = []
        for entry in self._buffer.entries:
            try:
                ets = datetime.fromisoformat(entry.timestamp).timestamp()
            except Exception:
                in_window.append(entry)
                continue
            if ets <= window_end:
                in_window.append(entry)
            else:
                beyond_window.append(entry)

        if len(in_window) < 3:  # need minimum events to synthesize
            return []

        consolidated = await self.consolidate_now(force_entries=in_window)

        # Swap buffer: keep beyond-window entries for next window
        self._buffer.clear()
        for entry in beyond_window:
            self._buffer.add(entry)

        return consolidated

    def get_window_stats(self) -> dict:
        """Get tumbling window aggregation statistics."""
        return {
            "buffer_entries": len(self._buffer.entries),
            "buffer_span_sec": self._buffer.elapsed_seconds(),
            "consolidation_count": self._stats["consolidation_count"],
            "synthesis_blocks": self._stats["synthesis_total"],
        }

    # ── sql-flow Pattern 6: Memory Table Persistence ──

    def persist_to_disk(self, path: str | Path = ".livingtree/memory/memory.db") -> str:
        """DuckDB-style: persist in-memory entries to SQLite for cross-session queries.
        sql-flow: DuckDB memory tables → LivingTree: SQLite memory persistence.
        """
        import sqlite3
        import json as _json
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(dest))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_entries (
                id TEXT PRIMARY KEY, session_id TEXT, timestamp TEXT,
                role TEXT, content TEXT, fact_perspective TEXT,
                rel_perspective TEXT, sources TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS synthesis_blocks (
                id TEXT PRIMARY KEY, timestamp TEXT, content TEXT,
                source_entries TEXT, session_ids TEXT
            )
        """)

        count = 0
        for eid, entry in self._entries.items():
            conn.execute(
                "INSERT OR REPLACE INTO event_entries VALUES (?,?,?,?,?,?,?,?)",
                (eid, entry.session_id, entry.timestamp, entry.role,
                 entry.content, entry.fact_perspective, entry.rel_perspective,
                 _json.dumps(entry.sources, ensure_ascii=False)),
            )
            count += 1

        synth_count = 0
        for s in self._synthesis:
            conn.execute(
                "INSERT OR REPLACE INTO synthesis_blocks VALUES (?,?,?,?,?)",
                (s.id, s.timestamp, s.content,
                 _json.dumps(s.source_entries, ensure_ascii=False),
                 _json.dumps(s.session_ids, ensure_ascii=False)),
            )
            synth_count += 1

        conn.commit()
        conn.close()
        logger.info(f"StructMem persisted: {count} entries, {synth_count} synthesis → {dest}")
        return str(dest)

    def load_from_disk(self, path: str | Path = ".livingtree/memory/memory.db") -> int:
        """Restore in-memory state from SQLite persistence."""
        import sqlite3
        import json as _json

        src = Path(path)
        if not src.exists():
            logger.debug(f"StructMem: no persistence file at {src}")
            return 0

        conn = sqlite3.connect(str(src))
        count = 0

        rows = conn.execute("SELECT * FROM event_entries").fetchall()
        for row in rows:
            eid, sid, ts, role, content, fact, rel, sources_json = row
            if eid in self._entries:
                continue
            entry = EventEntry(
                id=eid, session_id=sid, timestamp=ts, role=role,
                content=content, fact_perspective=fact or "",
                rel_perspective=rel or "",
                sources=_json.loads(sources_json) if sources_json else [],
            )
            self._entries[eid] = entry
            count += 1

        rows = conn.execute("SELECT * FROM synthesis_blocks").fetchall()
        for row in rows:
            sid, ts, content, src_json, sess_json = row
            if any(s.id == sid for s in self._synthesis):
                continue
            block = SynthesisBlock(
                id=sid, timestamp=ts, content=content,
                source_entries=_json.loads(src_json) if src_json else [],
                session_ids=_json.loads(sess_json) if sess_json else [],
            )
            self._synthesis.append(block)

        conn.close()
        self._stats["entries_total"] += count
        logger.info(f"StructMem loaded: {count} entries from {src}")
        return count

    def query_memory(self, sql: str) -> list[dict]:
        """DuckDB-style: run SQL queries against in-memory entries.
        Enables analytics like 'SELECT role, COUNT(*) FROM entries GROUP BY role'.
        """
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE entries (id, session_id, timestamp, role, content,
                                  fact_perspective, rel_perspective)
        """)
        for eid, e in self._entries.items():
            conn.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?)",
                         (eid, e.session_id, e.timestamp, e.role,
                          e.content, e.fact_perspective, e.rel_perspective))

        conn.execute("""
            CREATE TABLE synthesis (id, timestamp, content)
        """)
        for s in self._synthesis:
            conn.execute("INSERT INTO synthesis VALUES (?,?,?)",
                         (s.id, s.timestamp, s.content))

        try:
            cursor = conn.execute(sql)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            conn.close()
            logger.warning(f"StructMem SQL query failed: {e}")
            return []


# ═══ Singleton factory (used by execution_pipeline, unified_registry, intelligent_kb) ═══

_struct_mem_instance: StructMemory | None = None


def get_struct_mem() -> StructMemory:
    """Return the singleton StructMemory instance, creating it on first call."""
    global _struct_mem_instance
    if _struct_mem_instance is None:
        _struct_mem_instance = StructMemory()
    return _struct_mem_instance
