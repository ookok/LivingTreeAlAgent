#!/usr/bin/env python3
"""Quick smoke test for DisCoGC storage infrastructure.

Usage:
    python smoke_test_disco_gc.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livingtree.infrastructure.storage.backends import InMemoryStorageBackend, SQLiteStorageBackend
from livingtree.infrastructure.storage import (
    DisCoGC, get_disco_gc,
    GCConfig, GCPolicy,
    GCMetrics,
    TraceCollector,
    GCScheduler,
    StorageStats,
    StorageBridge,
    get_storage_bridge,
)

def test_imports():
    print("1. Import checks...", end=" ")
    assert DisCoGC is not None
    assert GCScheduler is not None
    assert TraceCollector is not None
    print("OK")

def test_config():
    print("2. Config...", end=" ")
    gc = GCConfig(policy=GCPolicy.ADAPTIVE, stale_threshold=0.30)
    assert gc.policy == GCPolicy.ADAPTIVE
    print("OK")

def test_metrics():
    print("3. GCMetrics...", end=" ")
    m = GCMetrics("smoke")
    m.record_discard(1024, 0.01)
    m.record_compaction(2048, 512, 0.05)
    m.record_app_write(10000)
    s = m.snapshot()
    assert s["total_reclaimed"] == 3072
    assert s["write_amplification"] > 1.0
    print("OK")

def test_trace_collector():
    print("4. TraceCollector...", end=" ")
    tc = TraceCollector("smoke")
    tc.record_read("s1", 100)
    tc.record_read("s1", 200)
    tc.record_read("s2", 50)
    tc.record_write("s3", 1000)
    w = tc.get_window(3600)
    assert w.total_reads == 3
    assert w.read_once_segments == 1  # s2 read once
    print("OK")

def test_scheduler():
    print("5. GCScheduler...", end=" ")
    config = GCConfig(stale_threshold=0.3)
    metrics = GCMetrics("smoke")
    scheduler = GCScheduler(config, metrics)
    stats = StorageStats(
        backend_name="smoke", total_bytes=10000, used_bytes=5000,
        stale_bytes=2000, live_bytes=3000,
    )
    decision = scheduler.evaluate(stats)
    assert decision.should_gc
    print("OK")

def test_inmemory_discard():
    print("6. InMemoryBackend discard...", end=" ")
    backend = InMemoryStorageBackend(name="smoke_mem", ttl_seconds=0, segment_entries=3)
    for i in range(100):
        backend.put(f"k_{i}", f"v_{i}")

    time.sleep(0.2)
    segments = backend.list_segments()
    stale_segs = [s for s in segments if s.stale_ratio > 0.5]
    freed = 0
    if stale_segs:
        freed = backend.discard_segments([stale_segs[0].segment_id])
    print(f"OK (freed={freed} bytes)")

def test_disco_gc_full_pipeline():
    print("7. DisCoGC full pipeline...", end=" ")
    backend = InMemoryStorageBackend(name="smoke_full", ttl_seconds=0)
    disco = DisCoGC(backend)
    disco.register()

    for i in range(200):
        backend.put(f"key_{i}", f"value_{i}")

    time.sleep(0.2)
    freed = disco.run_gc()
    stats = disco.get_stats()
    print(f"OK (freed={freed} bytes, WAF={stats['metrics']['write_amplification']})")
    disco.close()

def test_storage_bridge():
    print("8. StorageBridge...", end=" ")
    bridge = StorageBridge()
    disco = bridge.wrap_memory_cache(ttl_seconds=900)
    assert disco is not None
    stats = bridge.get_all_stats()
    assert "memory_cache" in stats
    bridge.close_all()
    print("OK")

def test_sqlite_backend():
    print("9. SQLiteBackend...", end=" ")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        backend = SQLiteStorageBackend(db_path=db_path, table_name="smoke_cache", ttl_seconds=86400)
        stats = backend.get_stats()
        assert stats.backend_name.startswith("sqlite:smoke_cache")
        print("OK")
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

def main():
    print("=" * 60)
    print("  DisCoGC Smoke Test")
    print("=" * 60)

    tests = [
        test_imports,
        test_config,
        test_metrics,
        test_trace_collector,
        test_scheduler,
        test_inmemory_discard,
        test_disco_gc_full_pipeline,
        test_storage_bridge,
        test_sqlite_backend,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
