"""Storage and GC configuration — presets for production, development, and testing.

Maps DisCoGC paper concepts to LivingTree configuration space:
  - DiscardTable: bitmap of reclaimable segments → DiscardStrategy
  - Compaction threshold: stale ratio trigger → CompactionStrategy
  - Policy: DISCARD_ONLY / COMPACT_ONLY / HYBRID / ADAPTIVE → GCPolicy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GCPolicy(str, Enum):
    """GC execution policy selecting between discard and compaction.

    DISCARD_ONLY  — zero-copy reclamation, no data movement (best for low disk pressure)
    COMPACT_ONLY  — traditional compaction, move live data (best for high fragmentation)
    HYBRID        — discard first, compact remainder (balanced)
    ADAPTIVE      — auto-select based on trace analysis (recommended for production)
    """
    DISCARD_ONLY = "discard_only"
    COMPACT_ONLY = "compact_only"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"


class DiscardStrategy(str, Enum):
    """How the discard executor selects segments to reclaim.

    TRACE_BASED   — use I/O trace data to identify cold/read-once segments
    AGE_BASED     — discard oldest segments first (LRU-style)
    SIZE_BASED    — target largest reclaimable segments for maximum space gain
    HYBRID        — weighted combination of trace + age + size
    """
    TRACE_BASED = "trace_based"
    AGE_BASED = "age_based"
    SIZE_BASED = "size_based"
    HYBRID = "hybrid"


class CompactionStrategy(str, Enum):
    """How the compaction executor reorganizes live data.

    TRADITIONAL   — move all live data to new segments (full rewrite)
    INCREMENTAL   — compact only the most fragmented segments
    ADAPTIVE      — apply incremental up to a pressure threshold, then traditional
    """
    TRADITIONAL = "traditional"
    INCREMENTAL = "incremental"
    ADAPTIVE = "adaptive"


@dataclass
class GCConfig:
    """DisCoGC engine configuration.

    Attributes:
        policy: overall GC execution policy
        discard_strategy: how discard executor selects targets
        compaction_strategy: how compaction executor reorganizes data
        stale_threshold: max stale ratio before GC triggers (0.0-1.0)
        space_warning_threshold: disk usage ratio that triggers warning-level GC
        space_critical_threshold: disk usage ratio that triggers critical-level GC
        trace_window_seconds: time window for I/O trace analysis
        min_discard_bytes: minimum reclaimable bytes to trigger a discard round
        cooldown_seconds: minimum interval between GC rounds
        max_write_amplification: tolerated write amp before switching to discard
    """
    policy: GCPolicy = GCPolicy.ADAPTIVE
    discard_strategy: DiscardStrategy = DiscardStrategy.HYBRID
    compaction_strategy: CompactionStrategy = CompactionStrategy.ADAPTIVE

    stale_threshold: float = 0.30
    space_warning_threshold: float = 0.75
    space_critical_threshold: float = 0.90

    trace_window_seconds: int = 3600
    min_discard_bytes: int = 10 * 1024 * 1024  # 10 MB
    cooldown_seconds: int = 300  # 5 minutes
    max_write_amplification: float = 3.0


@dataclass
class StorageConfig:
    """Per-backend storage configuration.

    Attributes:
        backend_name: unique identifier for the storage backend
        max_size_bytes: soft limit for total storage (0 = unlimited)
        segment_size_bytes: segment size for log-structured layout
        gc_config: GC engine configuration for this backend
        wal_enabled: enable write-ahead logging (SQLite-style durability)
        persist_path: filesystem path for persistent storage
    """
    backend_name: str = "default"
    max_size_bytes: int = 0
    segment_size_bytes: int = 64 * 1024 * 1024  # 64 MB
    gc_config: GCConfig = field(default_factory=GCConfig)
    wal_enabled: bool = True
    persist_path: str = ""


def get_default_gc_config(policy: GCPolicy = GCPolicy.ADAPTIVE) -> GCConfig:
    """Factory for GCConfig with sensible production defaults."""
    return GCConfig(policy=policy)


def get_aggressive_gc_config() -> GCConfig:
    """Aggressive GC preset for low-disk-space scenarios."""
    return GCConfig(
        policy=GCPolicy.COMPACT_ONLY,
        stale_threshold=0.10,
        space_warning_threshold=0.50,
        space_critical_threshold=0.70,
        min_discard_bytes=5 * 1024 * 1024,
        cooldown_seconds=120,
    )


def get_conservative_gc_config() -> GCConfig:
    """Conservative GC preset — minimal I/O overhead during GC."""
    return GCConfig(
        policy=GCPolicy.DISCARD_ONLY,
        stale_threshold=0.50,
        space_warning_threshold=0.85,
        space_critical_threshold=0.95,
        min_discard_bytes=50 * 1024 * 1024,
        cooldown_seconds=3600,
    )
