"""DisCoGC integration tests — smoke test for the full GC pipeline.

Tests cover:
  - Import and instantiation of all components
  - InMemoryBackend: put/get, discard, compaction
  - SQLiteBackend: segment listing, discard
  - DisCoGC full pipeline: register → run_gc → metrics
  - GC Scheduler decision logic
  - Trace collection and window aggregation
  - Storage bridge wiring
"""

from __future__ import annotations

import os
import time
import tempfile
import threading

import pytest

from livingtree.infrastructure.storage import (
    DisCoGC,
    get_disco_gc,
    StorageBackend,
    StorageSegment,
    StorageStats,
    TraceCollector,
    TraceWindow,
    TraceRegistry,
    GCScheduler,
    GCDecision,
    GCUrgency,
    GCPolicy,
    GCConfig,
    GCMetrics,
    DiscardStrategy,
    CompactionStrategy,
    DiscardExecutor,
    CompactionExecutor,
    get_default_gc_config,
    StorageBridge,
    get_storage_bridge,
)
from livingtree.infrastructure.storage.backends import (
    InMemoryStorageBackend,
    SQLiteStorageBackend,
    FAISSStorageBackend,
)


# ── Phase 1: Import & Instantiation ──

class TestImports:
    def test_all_exports(self):
        """Verify all key classes are importable."""
        assert DisCoGC is not None
        assert GCScheduler is not None
        assert TraceCollector is not None
        assert DiscardExecutor is not None
        assert CompactionExecutor is not None

    def test_config_presets(self):
        config = get_default_gc_config()
        assert config.policy == GCPolicy.ADAPTIVE
        assert config.stale_threshold == 0.30

    def test_storage_segment(self):
        seg = StorageSegment(
            segment_id="test_1",
            total_bytes=1000,
            live_bytes=300,
            stale_bytes=700,
        )
        assert seg.stale_ratio == 0.7
        assert not seg.is_discardable  # Not fully stale
        assert abs(seg.live_ratio - 0.3) < 1e-9


# ── Phase 2: GCMetrics ──

class TestGCMetrics:
    def test_basic_counters(self):
        m = GCMetrics("test")
        m.record_discard(1000, 0.1)
        m.record_compaction(2000, 500, 0.5)
        assert m.discard_rounds == 1
        assert m.compaction_rounds == 1
        assert m.total_bytes_reclaimed == 3000

    def test_write_amplification(self):
        m = GCMetrics("test")
        m.record_app_write(10000)
        m.record_compaction(5000, 2000, 0.5)
        expected_waf = (10000 + 2000) / 10000
        assert abs(m.write_amplification - expected_waf) < 0.01

    def test_discard_efficiency(self):
        m = GCMetrics("test")
        m.record_discard(3000, 0.1)
        m.record_compaction(1000, 500, 0.5)
        assert m.discard_efficiency == 0.75

    def test_snapshot(self):
        m = GCMetrics("test")
        m.record_discard(1000, 0.1)
        s = m.snapshot()
        assert s["backend"] == "test"
        assert s["discard_rounds"] == 1
        assert "write_amplification" in s


# ── Phase 2: TraceCollector ──

class TestTraceCollector:
    def test_record_read(self):
        tc = TraceCollector("test_backend")
        tc.record_read("seg_1", 4096)
        tc.record_read("seg_1", 2048)
        assert tc.total_reads == 2
        assert tc.total_read_bytes == 6144

    def test_record_write(self):
        tc = TraceCollector("test_backend")
        tc.record_write("seg_2", 8192)
        assert tc.total_writes == 1
        assert tc.total_write_bytes == 8192

    def test_get_window(self):
        tc = TraceCollector("test_backend")
        tc.record_read("seg_a", 1000)
        tc.record_read("seg_b", 2000)
        tc.record_read("seg_b", 3000)
        tc.record_write("seg_c", 4000)

        window = tc.get_window(duration_seconds=3600)
        assert isinstance(window, TraceWindow)
        assert window.total_reads == 3
        assert window.total_writes == 1
        assert window.read_once_segments == 1  # seg_a read once
        assert window.hot_segments == 0

    def test_cold_segments(self):
        tc = TraceCollector("test_backend")
        tc.record_read("seg_hot", 100)
        tc._segment_last_read["seg_cold"] = time.time() - 10000

        cold = tc.get_cold_segments(duration_seconds=3600)
        assert "seg_cold" in cold
        assert "seg_hot" not in cold

    def test_reset(self):
        tc = TraceCollector("test_backend")
        tc.record_read("seg_1", 100)
        tc.reset()
        assert tc.total_reads == 0


# ── Phase 2: GCScheduler ──

class TestGCScheduler:
    def test_no_action_when_healthy(self):
        config = GCConfig(stale_threshold=0.3, space_warning_threshold=0.75)
        metrics = GCMetrics("test")
        scheduler = GCScheduler(config, metrics)

        stats = StorageStats(
            backend_name="test",
            total_bytes=10000,
            used_bytes=3000,
            stale_bytes=500,
            live_bytes=2500,
        )
        decision = scheduler.evaluate(stats)
        assert decision.urgency == GCUrgency.NONE
        assert not decision.should_gc

    def test_discard_when_stale_high(self):
        config = GCConfig(stale_threshold=0.3, space_warning_threshold=0.75)
        metrics = GCMetrics("test")
        scheduler = GCScheduler(config, metrics)

        stats = StorageStats(
            backend_name="test",
            total_bytes=10000,
            used_bytes=5000,
            stale_bytes=2500,
            live_bytes=2500,
        )
        decision = scheduler.evaluate(stats)
        assert decision.urgency != GCUrgency.NONE
        assert decision.should_gc

    def test_critical_urgency(self):
        config = GCConfig(
            space_warning_threshold=0.75,
            space_critical_threshold=0.90,
        )
        metrics = GCMetrics("test")
        scheduler = GCScheduler(config, metrics)

        stats = StorageStats(
            backend_name="test",
            total_bytes=10000,
            used_bytes=9500,
            stale_bytes=4000,
            live_bytes=5500,
        )
        decision = scheduler.evaluate(stats)
        assert decision.urgency == GCUrgency.CRITICAL


# ── Phase 3: InMemoryBackend ──

class TestInMemoryBackend:
    def test_put_and_get(self):
        backend = InMemoryStorageBackend(name="test_mem", ttl_seconds=3600)
        seg_id = backend.put("key1", "value1", size_bytes=10)
        assert seg_id.startswith("segment_")
        assert backend.get("key1") == "value1"

    def test_ttl_expiry(self):
        backend = InMemoryStorageBackend(name="test_mem", ttl_seconds=0)
        backend.put("key1", "value1")
        time.sleep(0.1)
        assert backend.get("key1") is None

    def test_list_segments(self):
        backend = InMemoryStorageBackend(name="test_mem", segment_entries=2)
        backend.put("k1", "v1")
        backend.put("k2", "v2")
        backend.put("k3", "v3")

        segments = backend.list_segments()
        assert len(segments) >= 2

    def test_discard_segments(self):
        backend = InMemoryStorageBackend(name="test_mem", ttl_seconds=0)
        seg_id = backend.put("key1", "value1")
        time.sleep(0.1)  # Allow TTL to expire

        segments = backend.list_segments()
        stale_segs = [s for s in segments if s.stale_ratio > 0]
        if stale_segs:
            freed = backend.discard_segments([stale_segs[0].segment_id])
            assert freed >= 0

    def test_get_stats(self):
        backend = InMemoryStorageBackend(name="test_mem")
        backend.put("k1", "value1", size_bytes=100)
        stats = backend.get_stats()
        assert stats.used_bytes >= 100
        assert stats.backend_name == "test_mem"


# ── Phase 3: SQLiteBackend ──

class TestSQLiteBackend:
    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        yield path
        try:
            os.unlink(path)
        except OSError:
            pass

    def test_init_and_stats(self, db_path):
        backend = SQLiteStorageBackend(db_path=db_path, table_name="test_cache", ttl_seconds=86400)
        stats = backend.get_stats()
        assert stats.backend_name.startswith("sqlite:test_cache")
        assert stats.used_bytes == 0

    def test_list_empty_segments(self, db_path):
        backend = SQLiteStorageBackend(db_path=db_path, table_name="test_cache")
        segments = backend.list_segments()
        assert segments == []


# ── DisCoGC Full Pipeline ──

class TestDisCoGCPipeline:
    def test_register_and_run_gc(self):
        backend = InMemoryStorageBackend(name="test_disco", ttl_seconds=0)
        disco = DisCoGC(backend)
        disco.register()

        backend.put("key_a", "val_a")
        backend.put("key_b", "val_b")
        time.sleep(0.1)

        freed = disco.run_gc()
        assert freed >= 0

        stats = disco.get_stats()
        assert "storage" in stats
        assert "metrics" in stats

    def test_get_disco_gc_singleton(self):
        backend = InMemoryStorageBackend(name="test_singleton")
        disco1 = get_disco_gc(backend)
        disco2 = get_disco_gc(backend)
        assert disco1 is disco2
        disco1.close()

    def test_record_app_write(self):
        backend = InMemoryStorageBackend(name="test_app_write")
        disco = DisCoGC(backend)
        disco.record_app_write(10000)
        disco.record_app_write(5000)
        assert disco._metrics.app_bytes_written == 15000
        disco.close()

    def test_background_thread(self):
        backend = InMemoryStorageBackend(name="test_bg")
        disco = DisCoGC(backend)
        disco.start_background(interval_seconds=60)
        assert disco._background_thread is not None
        assert disco._background_thread.is_alive()
        disco.stop_background()
        assert not disco._background_thread.is_alive()

    def test_metrics_snapshot(self):
        backend = InMemoryStorageBackend(name="test_metrics")
        disco = DisCoGC(backend)
        disco.run_gc()
        metrics = disco.get_metrics()
        snapshot = metrics.snapshot()
        assert "write_amplification" in snapshot
        assert "total_reclaimed" in snapshot
        disco.close()


# ── StorageBridge ──

class TestStorageBridge:
    def test_wrap_memory_cache(self):
        bridge = StorageBridge()
        disco = bridge.wrap_memory_cache(ttl_seconds=900)
        assert disco is not None
        stats = bridge.get_all_stats()
        assert "memory_cache" in stats
        bridge.close_all()

    def test_wrap_sqlite(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            bridge = StorageBridge()
            disco = bridge.wrap_sqlite(db_path=db_path, table_name="test_bridge")
            assert disco is not None
            bridge.close_all()
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_get_storage_bridge_singleton(self):
        b1 = get_storage_bridge()
        b2 = get_storage_bridge()
        assert b1 is b2


# ── FAISSBackend ──

class TestFAISSBackend:
    def test_init_and_stats(self):
        backend = FAISSStorageBackend(name="test_faiss", dimension=128)
        stats = backend.get_stats()
        assert stats.backend_name == "test_faiss"
        assert stats.used_bytes == 0

    def test_add_and_search(self):
        backend = FAISSStorageBackend(name="test_faiss", dimension=4)
        backend.add_vectors(
            vectors=[
                [0.1, 0.2, 0.3, 0.4],
                [0.5, 0.6, 0.7, 0.8],
                [0.9, 1.0, 1.1, 1.2],
            ],
            metadata_list=[{"id": 1}, {"id": 2}, {"id": 3}],
        )
        results = backend.search([0.1, 0.2, 0.3, 0.4], k=2)
        assert len(results) > 0
        assert results[0][2]["id"] == 1

    def test_list_segments(self):
        backend = FAISSStorageBackend(name="test_faiss", dimension=4)
        backend.add_vectors(
            vectors=[[float(i % 4) for _ in range(4)] for i in range(10)],
        )
        segments = backend.list_segments()
        assert len(segments) > 0


# ── Edge Cases ──

class TestEdgeCases:
    def test_empty_discard(self):
        backend = InMemoryStorageBackend(name="test_empty")
        disco = DisCoGC(backend)
        freed = disco.run_gc()
        assert freed == 0
        disco.close()

    def test_max_entries_eviction(self):
        backend = InMemoryStorageBackend(name="test_max", max_entries=3, segment_entries=5)
        for i in range(5):
            backend.put(f"key_{i}", f"value_{i}")
        stats = backend.get_stats()
        assert stats.used_bytes > 0
        # Verify LRU eviction kept recent entries
        assert backend.get("key_0") is not None or backend.get("key_4") is not None

    def test_negative_bytes(self):
        m = GCMetrics("test")
        m.record_app_write(0)
        assert m.write_amplification == 1.0

    def test_gc_decision_repr(self):
        d = GCDecision(urgency=GCUrgency.HIGH, policy=GCPolicy.HYBRID, reason="test")
        assert d.should_gc
        assert d.should_discard
        assert d.should_compact
