"""Site Accelerator tests — FastGithub-style overseas site acceleration.

Tests:
  - DomainIPPool: seed data, get_best, update_ip
  - SiteAccelerator: initialization, optimal IP routing, stats
  - Integration: accelerated fetch, fallback chain
"""

from __future__ import annotations

import pytest
import time

from livingtree.network.domain_ip_pool import DomainIPPool, DomainIP, DomainEntry
from livingtree.network.site_accelerator import SiteAccelerator, get_accelerator


# ═══ DomainIPPool ═══

class TestDomainIPPool:
    @pytest.mark.asyncio
    async def test_initialize(self):
        pool = DomainIPPool()
        await pool.initialize()
        stats = pool.get_stats()
        assert stats["total_domains"] > 0
        assert stats["total_ips"] > 0

    def test_get_best_github(self):
        pool = DomainIPPool()
        pool.add_domain("github.com", ["140.82.121.3", "140.82.121.4"])
        best = pool.get_best("github.com")
        assert best is not None
        assert "140.82" in best.ip

    def test_get_best_nonexistent(self):
        pool = DomainIPPool()
        assert pool.get_best("nonexistent.example.com") is None

    def test_update_ip_success(self):
        pool = DomainIPPool()
        pool.add_domain("test.com", ["1.2.3.4"])
        pool.update_ip("test.com", "1.2.3.4", latency_ms=45.0, success=True)
        best = pool.get_best("test.com")
        assert best.success_rate == 1.0
        assert best.latency_ms == 45.0

    def test_update_ip_failure(self):
        pool = DomainIPPool()
        pool.add_domain("test.com", ["1.2.3.4"])
        pool.update_ip("test.com", "1.2.3.4", latency_ms=999, success=False)
        best = pool.get_best("test.com")
        assert best.success_rate < 0.5

    def test_seed_categories(self):
        pool = DomainIPPool()
        pool._seed_dedicated()
        pool._seed_search()
        pool._seed_cdn()
        pool._seed_video()
        pool._seed_general()

        dev = pool.get_domains_by_category("DEDICATED")
        search = pool.get_domains_by_category("SEARCH")
        cdn = pool.get_domains_by_category("CDN")
        video = pool.get_domains_by_category("VIDEO")
        general = pool.get_domains_by_category("GENERAL")

        assert len(dev) > 0
        assert len(search) > 0
        assert len(cdn) > 0
        assert len(video) > 0
        assert len(general) > 0

    def test_domain_ip_scoring(self):
        ip1 = DomainIP(ip="1.1.1.1", latency_ms=50, success_rate=1.0)
        ip2 = DomainIP(ip="2.2.2.2", latency_ms=300, success_rate=0.5)
        assert ip1.score < ip2.score  # ip1 is better

    @pytest.mark.asyncio
    async def test_save_and_load_cache(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cache_path = f.name

        try:
            pool = DomainIPPool(cache_path=cache_path)
            pool.add_domain("cached.com", ["10.0.0.1", "10.0.0.2"])
            pool.update_ip("cached.com", "10.0.0.1", 30.0, True)
            pool.save_cache()

            pool2 = DomainIPPool(cache_path=cache_path)
            pool2._load_cache()
            best = pool2.get_best("cached.com")
            assert best is not None
        finally:
            try:
                os.unlink(cache_path)
            except OSError:
                pass


# ═══ SiteAccelerator ═══

class TestSiteAccelerator:
    @pytest.mark.asyncio
    async def test_initialize(self):
        accel = SiteAccelerator()
        await accel.initialize()
        stats = accel.get_stats()
        assert stats["total_domains"] > 0

    def test_get_optimal_params_github(self):
        accel = SiteAccelerator()
        accel._ip_pool.add_domain("github.com", ["140.82.121.3"])
        accel._ip_pool.update_ip("github.com", "140.82.121.3", 50.0, True)

        params = accel.get_optimal_connection_params("https://github.com/user/repo")
        assert params.get("resolved_ip") == "140.82.121.3"
        assert params["original_domain"] == "github.com"

    def test_get_optimal_params_unknown(self):
        accel = SiteAccelerator()
        params = accel.get_optimal_connection_params("https://unknown.example.com/path")
        assert params == {} or params.get("resolved_ip") is None

    def test_get_stats_initial(self):
        accel = SiteAccelerator()
        stats = accel.get_stats()
        assert "total_domains" in stats
        assert "accelerated_fetches" in stats

    @pytest.mark.asyncio
    async def test_test_ip_timeout(self):
        accel = SiteAccelerator()
        success, latency = await accel.test_ip("192.0.2.1", "192.0.2.1", timeout=1.0)
        assert not success  # Test network should not be reachable

    def test_mirror_url_fallback(self):
        from livingtree.network.site_accelerator import SiteAccelerator
        mirror = SiteAccelerator._get_mirror_url("https://github.com/user/repo")
        assert mirror and "ghproxy" in mirror

        mirror2 = SiteAccelerator._get_mirror_url("https://huggingface.co/models/test")
        assert mirror2 and "hf-mirror" in mirror2

    def test_singleton(self):
        a1 = get_accelerator()
        a2 = get_accelerator()
        assert a1 is a2


# ═══ Integration ═══

class TestAcceleratorIntegration:
    @pytest.mark.asyncio
    async def test_full_seed_data_integrity(self):
        """All seeded domains should have at least one IP."""
        accel = SiteAccelerator()
        await accel.initialize()
        stats = accel.get_stats()

        for category in ["DEDICATED", "SEARCH", "CDN", "VIDEO", "GENERAL"]:
            domains = accel._ip_pool.get_domains_by_category(category)
            for domain in domains:
                best = accel._ip_pool.get_best(domain)
                assert best is not None, f"{domain} ({category}) has no IPs"

    def test_acceleration_ratio_tracking(self):
        accel = SiteAccelerator()
        accel._total_fetches = 10
        accel._accelerated_fetches = 7
        accel._direct_fetches = 3
        stats = accel.get_stats()
        assert stats["acceleration_ratio"] == 0.7

    def test_latency_saved_tracking(self):
        accel = SiteAccelerator()
        accel._total_latency_saved_ms = 5000
        stats = accel.get_stats()
        assert stats["estimated_latency_saved_ms"] == 5000
