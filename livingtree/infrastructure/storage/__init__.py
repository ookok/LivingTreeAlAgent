"""LivingTree Storage Infrastructure — DisCoGC-powered distributed log-structured storage.

Implements Discard-Based Garbage Collection (DisCoGC) from ByteDance/Tsinghua FAST'26:
  ByteDance ByteStore: discard reclaims stale data WITHOUT moving valid data,
  complementing traditional compaction to reduce write amplification ~20%.

Exports:
  - StorageBackend: abstract base for pluggable storage backends
  - DiscardExecutor, CompactionExecutor: core GC executors
  - TraceCollector: I/O trace recording for GC decision
  - GCScheduler: adaptive discard vs compact decision engine
  - DisCoGC: main orchestrator
  - storage_config: GC configuration presets
  - gc_metrics: write amp, space reclaimed, operation counters
"""

from .storage_config import (
    StorageConfig,
    GCConfig,
    GCPolicy,
    DiscardStrategy,
    CompactionStrategy,
    get_default_gc_config,
)
from .gc_metrics import GCMetrics, StorageStats, TraceWindow
from .storage_layer import StorageBackend, StorageSegment
from .trace_collector import TraceCollector, IOTrace, TraceRegistry
from .discard_executor import DiscardExecutor
from .compaction_executor import CompactionExecutor
from .gc_scheduler import GCScheduler, GCDecision, GCUrgency
from .disco_gc import DisCoGC, get_disco_gc
from .storage_bridge import StorageBridge, get_storage_bridge

__all__ = [
    "StorageConfig",
    "GCConfig",
    "GCPolicy",
    "DiscardStrategy",
    "CompactionStrategy",
    "get_default_gc_config",
    "GCMetrics",
    "StorageStats",
    "TraceWindow",
    "StorageBackend",
    "StorageSegment",
    "TraceCollector",
    "IOTrace",
    "TraceRegistry",
    "DiscardExecutor",
    "CompactionExecutor",
    "GCScheduler",
    "GCDecision",
    "GCUrgency",
    "DisCoGC",
    "get_disco_gc",
    "StorageBridge",
    "get_storage_bridge",
]
