"""Scinet Service tests — local proxy for overseas site access.

Tests:
  - ScinetStatus dataclass
  - ScinetService life cycle (start/stop/get_status)
  - PAC file generation
  - Singleton get_scinet()
  - CLI scinet_command (basic validation)
"""

from __future__ import annotations

import pytest
import asyncio

from livingtree.network.scinet_service import (
    ScinetService, ScinetStatus, get_scinet, PAC_TEMPLATE,
)


# ═══ ScinetStatus ═══

class TestScinetStatus:
    def test_defaults(self):
        s = ScinetStatus()
        assert s.running is False
        assert s.port == 7890
        assert s.total_requests == 0

    def test_running_state(self):
        s = ScinetStatus(running=True, port=7890, uptime_seconds=3600)
        assert s.running
        assert s.uptime_seconds == 3600


# ═══ ScinetService ═══

class TestScinetService:
    def test_init(self):
        scinet = ScinetService(port=7890)
        assert scinet.port == 7890
        assert scinet._running is False

    def test_get_status_stopped(self):
        scinet = ScinetService()
        status = scinet.get_status()
        assert status.running is False

    def test_generate_pac(self):
        scinet = ScinetService(port=7890)
        pac = scinet.generate_pac()
        assert "FindProxyForURL" in pac
        assert "7890" in pac
        assert ".cn" in pac

    def test_generate_pac_with_custom_port(self):
        scinet = ScinetService(port=8888)
        pac = scinet.generate_pac()
        assert "8888" in pac

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        scinet = ScinetService(port=17890)
        try:
            status = await scinet.start()
            assert status.running

            mid_status = scinet.get_status()
            assert mid_status.running

            stopped = await scinet.stop()
            assert not stopped.running
        except RuntimeError as e:
            if "aiohttp" in str(e).lower():
                pytest.skip("aiohttp not available")
            raise
        except OSError:
            pytest.skip("Port binding failed")

    def test_singleton(self):
        s1 = get_scinet(port=17901)
        s2 = get_scinet(port=17901)
        assert s1 is s2


# ═══ PAC Generation ═══

class TestPAC:
    def test_pac_template_format(self):
        """PAC template should have correct proxy format."""
        pac = PAC_TEMPLATE.format(port=7890, accelerated_domains="")
        assert "PROXY 127.0.0.1:7890" in pac
        assert "FindProxyForURL" in pac

    def test_pac_includes_cn_bypass(self):
        """PAC should bypass Chinese domains."""
        pac = PAC_TEMPLATE.format(port=7890, accelerated_domains="")
        assert ".cn" in pac
        assert "DIRECT" in pac

    def test_pac_localhost_bypass(self):
        pac = PAC_TEMPLATE.format(port=7890, accelerated_domains="")
        assert "127.0.0.1" in pac
        assert "localhost" in pac
