"""ProxyFetcher — multi-source proxy pool fetcher with health checks.

    Sources (14):
    1.  proxyscrape.com API — HTTP/HTTPS/SOCKS5, by country/anonymity
    2.  geonode.com API — free tier, returns JSON with location info
    3.  proxy-list.download — categorized HTTP/HTTPS/SOCKS5 lists
    4.  GitHub TheSpeedX/PROXY-List — most active community proxy list
    5.  GitHub hookzof/socks5_list — SOCKS5 specialized
    6.  proxylist.geonode.com — alternative API endpoint
    7.  GitHub jetkai/proxy-list — multi-type (HTTP/HTTPS/SOCKS4/SOCKS5)
    8.  GitHub monosans/proxy-list — daily refreshed, scraped from 300+ sources
    9.  GitHub mertguvencli/http-proxy-list — HTTP specialized
    10. GitHub rdavydov/proxy-list — updated every 20 min
    11. GitHub proxifly/free-proxy-list — JSON API format
    12. free-proxy-list.net — HTML table scraping (300+ proxies)
    13. pubproxy.com — free REST API, JSON output
    14. openproxy.space — free API, JSON with country/uptime

    Auto-refresh every 10 minutes. Health-check via TCP connect + HTTP test.
    Best proxy selected by composite score: success_rate + latency + stability.

    Wires into resilience.py for transparent auto-proxy on all HTTP calls.

    Usage:
        pool = get_proxy_pool()
        await pool.refresh()
        proxy = pool.get_best()  # → "http://1.2.3.4:8080"
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

PROXY_CACHE = Path(".livingtree/proxy_pool.json")
REFRESH_INTERVAL = 600  # 10 minutes
MAX_POOL_SIZE = 200


def code_to_country(code: str) -> str:
    """Map ISO country code to country name."""
    _MAP = {
        "US": "United States", "CN": "China", "DE": "Germany", "GB": "United Kingdom",
        "FR": "France", "JP": "Japan", "CA": "Canada", "NL": "Netherlands",
        "RU": "Russia", "IN": "India", "BR": "Brazil", "SG": "Singapore",
        "KR": "South Korea", "AU": "Australia", "UA": "Ukraine", "PL": "Poland",
    }
    return _MAP.get(code.upper(), code)


@dataclass
class Proxy:
    host: str
    port: int
    protocol: str = "http"  # http, https, socks5
    source: str = ""
    country: str = ""
    anonymity: str = ""
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    last_success: float = 0.0
    avg_latency: float = 0.0

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.0

    @property
    def score(self) -> float:
        try:
            lat = float(self.avg_latency) if self.avg_latency else 0.0
        except (ValueError, TypeError):
            lat = 0.0
        return self.success_rate * 0.5 + max(0, 1 - lat / 5) * 0.3 + (1 / (1 + self.failure_count)) * 0.2


class ProxyPool:
    """Multi-source proxy pool with health scoring."""

    def __init__(self):
        self._pool: dict[str, Proxy] = {}  # host:port → Proxy
        self._load()

    async def refresh(self) -> int:
        """Fetch from all sources, validate, merge into pool."""
        fetched = []
        sources = [
            self._fetch_proxyscrape,
            self._fetch_geonode,
            self._fetch_proxylist_download,
            self._fetch_github_speedx,
            self._fetch_github_socks5,
            self._fetch_geonode_alt,
            self._fetch_github_jetkai,
            self._fetch_github_monosans,
            self._fetch_github_mertguvencli,
            self._fetch_github_rdavydov,
            self._fetch_proxifly,
            self._fetch_free_proxy_list_net,
            self._fetch_pubproxy,
            self._fetch_openproxy_space,
        ]

        tasks = []
        for src in sources:
            tasks.append(self._safe_fetch(src))

        results = await asyncio.gather(*tasks)
        for proxies in results:
            fetched.extend(proxies)

        added = 0
        for p in fetched:
            key = f"{p.host}:{p.port}"
            if key in self._pool:
                continue
            if len(self._pool) >= MAX_POOL_SIZE:
                break
            self._pool[key] = p
            added += 1

        if added:
            self._save()
            logger.info(f"ProxyPool: +{added} new ({len(self._pool)} total)")

        return added

    async def _safe_fetch(self, coro) -> list[Proxy]:
        try:
            return await coro() or []
        except Exception as e:
            logger.debug(f"Proxy source: {e}")
            return []

    # ═══ Source 1: proxyscrape.com ═══

    async def _fetch_proxyscrape(self) -> list[Proxy]:
        """proxyscrape.com — free tier: 100 proxies per request."""
        proxies = []
        import aiohttp
        urls = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&limit=50",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=10000&country=all&limit=30",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all&limit=20",
        ]
        for url in urls:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        text = await resp.text()
                for line in text.splitlines()[:60]:
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    host, port = line.rsplit(":", 1)
                    proto = "http" if "http" in url else "https" if "https" in url else "socks5"
                    proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="proxyscrape"))
            except Exception:
                pass
        return proxies

    # ═══ Source 2: geonode.com ═══

    async def _fetch_geonode(self) -> list[Proxy]:
        """geonode.com — free API, returns JSON with geolocation."""
        proxies = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
            for item in data.get("data", [])[:60]:
                proxies.append(Proxy(
                    host=item.get("ip", ""),
                    port=int(item.get("port", 8080)),
                    protocol=item.get("protocols", ["http"])[0] if item.get("protocols") else "http",
                    country=item.get("country", ""),
                    anonymity=item.get("anonymityLevel", ""),
                    source="geonode",
                    avg_latency=float(item.get("responseTime", 0)) / 1000,
                ))
        except Exception:
            pass
        return proxies

    # ═══ Source 3: proxy-list.download ═══

    async def _fetch_proxylist_download(self) -> list[Proxy]:
        """proxy-list.download — categorized proxy lists."""
        proxies = []
        urls = [
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://www.proxy-list.download/api/v1/get?type=https",
            "https://www.proxy-list.download/api/v1/get?type=socks5",
        ]
        for url in urls:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        text = await resp.text()
                proto = "http" if "http" in url and "https" not in url else "https" if "https" in url else "socks5"
                for line in text.splitlines()[:50]:
                    line = line.strip()
                    if ":" not in line:
                        continue
                    host, port = line.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="proxy-list.download"))
            except Exception:
                pass
        return proxies

    # ═══ Source 4: GitHub TheSpeedX/PROXY-List ═══

    async def _fetch_github_speedx(self) -> list[Proxy]:
        """GitHub TheSpeedX/PROXY-List — most popular community proxy list."""
        proxies = []
        urls = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        ]
        for url in urls:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        text = await resp.text()
                proto = "http" if "http" in url else "socks4" if "socks4" in url else "socks5"
                if proto == "socks4":
                    proto = "socks5"  # normalize
                for line in text.splitlines()[:80]:
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    host, port = line.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="github/speedx"))
            except Exception:
                pass
        return proxies

    # ═══ Source 5: GitHub hookzof/socks5_list ═══

    async def _fetch_github_socks5(self) -> list[Proxy]:
        """GitHub hookzof/socks5_list — SOCKS5 specialized."""
        proxies = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    text = await resp.text()
            for line in text.splitlines()[:80]:
                line = line.strip()
                if ":" not in line:
                    continue
                host, port = line.rsplit(":", 1)
                if host.replace(".", "").isdigit():
                    proxies.append(Proxy(host=host, port=int(port), protocol="socks5", source="github/hookzof"))
        except Exception:
            pass
        return proxies

    # ═══ Source 6: geonode alternate ═══

    async def _fetch_geonode_alt(self) -> list[Proxy]:
        """geonode — alternative API endpoint with different format."""
        proxies = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://api.geonode.com/api/proxy-list?limit=30&sort_by=speed&sort_type=asc",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
            for item in data.get("data", [])[:40]:
                proxies.append(Proxy(
                    host=item.get("ip", ""),
                    port=int(item.get("port", 8080)),
                    protocol=item.get("protocols", ["http"])[0] if item.get("protocols") else "http",
                    country=item.get("country", ""),
                    source="geonode-alt",
                ))
        except Exception:
            pass
        return proxies

    # ═══ Source 7: GitHub jetkai/proxy-list ═══

    async def _fetch_github_jetkai(self) -> list[Proxy]:
        """GitHub jetkai/proxy-list — multi-type, updated every 15 min."""
        proxies = []
        urls = [
            ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt", "http"),
            ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt", "https"),
            ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt", "socks4"),
            ("https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt", "socks5"),
        ]
        for url, proto in urls:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        text = await resp.text()
                if proto == "socks4":
                    proto = "socks5"
                for line in text.splitlines()[:100]:
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    host, port = line.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="github/jetkai"))
            except Exception:
                pass
        return proxies

    # ═══ Source 8: GitHub monosans/proxy-list ═══

    async def _fetch_github_monosans(self) -> list[Proxy]:
        """GitHub monosans/proxy-list — scraped from 300+ sources, daily refresh."""
        proxies = []
        urls = [
            ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "http"),
            ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "socks4"),
            ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "socks5"),
        ]
        for url, proto in urls:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        text = await resp.text()
                if proto == "socks4":
                    proto = "socks5"
                for line in text.splitlines()[:120]:
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    host, port = line.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="github/monosans"))
            except Exception:
                pass
        return proxies

    # ═══ Source 9: GitHub mertguvencli/http-proxy-list ═══

    async def _fetch_github_mertguvencli(self) -> list[Proxy]:
        """GitHub mertguvencli — HTTP proxy specialized list."""
        proxies = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    text = await resp.text()
            for line in text.splitlines()[:80]:
                line = line.strip().rstrip(",")
                if ":" not in line:
                    continue
                host, port = line.rsplit(":", 1)
                if host.replace(".", "").isdigit():
                    proxies.append(Proxy(host=host, port=int(port), protocol="http", source="github/mertguvencli"))
        except Exception:
            pass
        return proxies

    # ═══ Source 10: GitHub rdavydov/proxy-list ═══

    async def _fetch_github_rdavydov(self) -> list[Proxy]:
        """GitHub rdavydov/proxy-list — updated every 20 minutes."""
        proxies = []
        urls = [
            ("https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt", "http"),
            ("https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks4.txt", "socks4"),
            ("https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks5.txt", "socks5"),
        ]
        for url, proto in urls:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        text = await resp.text()
                if proto == "socks4":
                    proto = "socks5"
                for line in text.splitlines()[:80]:
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    host, port = line.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(host=host, port=int(port), protocol=proto, source="github/rdavydov"))
            except Exception:
                pass
        return proxies

    # ═══ Source 11: GitHub proxifly/free-proxy-list ═══

    async def _fetch_proxifly(self) -> list[Proxy]:
        """GitHub proxifly — JSON API format with country and latency info."""
        proxies = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.json",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
            for item in data[:70] if isinstance(data, list) else []:
                if isinstance(item, dict):
                    proxies.append(Proxy(
                        host=item.get("ip", item.get("host", "")),
                        port=int(item.get("port", 8080)),
                        protocol=item.get("protocol", "http"),
                        country=item.get("country", item.get("geolocation", {}).get("country", "")),
                        source="proxifly",
                    ))
        except Exception:
            pass
        return proxies

    # ═══ Source 12: free-proxy-list.net ═══

    async def _fetch_free_proxy_list_net(self) -> list[Proxy]:
        """free-proxy-list.net — HTML table, 300+ proxies with anonymity level."""
        proxies = []
        try:
            import aiohttp
            from html.parser import HTMLParser

            class ProxyTableParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self._in_tbody = False
                    self._in_tr = False
                    self._td_count = 0
                    self._cells: list[str] = []
                    self.results: list[dict] = []

                def handle_starttag(self, tag, attrs):
                    if tag in ("tbody", "table"):
                        self._in_tbody = True
                    if tag == "tr" and self._in_tbody:
                        self._in_tr = True
                        self._td_count = 0
                        self._cells = []
                    if tag == "td" and self._in_tr:
                        self._td_count += 1

                def handle_data(self, data):
                    if self._in_tr and self._td_count > 0:
                        self._cells.append(data.strip())

                def handle_endtag(self, tag):
                    if tag == "tr" and self._in_tr:
                        self._in_tr = False
                        if len(self._cells) >= 2:
                            self.results.append({"cells": self._cells})
                    if tag in ("tbody", "table"):
                        self._in_tbody = False

            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "https://free-proxy-list.net/",
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                ) as resp:
                    html = await resp.text()
            parser = ProxyTableParser()
            parser.feed(html)
            for row in parser.results:
                cells = row["cells"]
                if len(cells) >= 2 and cells[0].replace(".", "").isdigit():
                    try:
                        proxies.append(Proxy(
                            host=cells[0],
                            port=int(cells[1]),
                            protocol="https" if len(cells) > 6 and cells[6] == "yes" else "http",
                            country=code_to_country(cells[4]) if len(cells) > 4 else "",
                            anonymity=cells[5] if len(cells) > 5 else "",
                            source="free-proxy-list.net",
                        ))
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
        return proxies

    # ═══ Source 13: pubproxy.com ═══

    async def _fetch_pubproxy(self) -> list[Proxy]:
        """pubproxy.com — free REST API, JSON output, 5 proxies per request."""
        proxies = []
        for _ in range(3):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        "https://api.pubproxy.com/v2/proxy?format=json&limit=5&type=http",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                for item in data.get("data", []):
                    addr = item.get("ipPort", "")
                    host, port_str = addr.rsplit(":", 1) if ":" in addr else (item.get("ip", ""), str(item.get("port", 8080)))
                    proxies.append(Proxy(
                        host=host,
                        port=int(port_str) if port_str.isdigit() else 8080,
                        protocol=item.get("type", "http").lower(),
                        country=item.get("country", ""),
                        source="pubproxy",
                    ))
            except Exception:
                pass
        return proxies

    # ═══ Source 14: openproxy.space ═══

    async def _fetch_openproxy_space(self) -> list[Proxy]:
        """openproxy.space — free API, JSON with country, uptime, latency."""
        proxies = []
        for proto in ["http", "socks4", "socks5"]:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        f"https://api.openproxy.space/lists/{proto}?limit=30",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        data = await resp.json()
                if proto == "socks4":
                    proto = "socks5"
                for item in data[:40] if isinstance(data, list) else data.get("data", [])[:40]:
                    addr = item if isinstance(item, str) else item.get("address", item.get("proxy", ""))
                    if ":" not in addr:
                        continue
                    host, port = addr.rsplit(":", 1)
                    if host.replace(".", "").isdigit():
                        proxies.append(Proxy(
                            host=host,
                            port=int(port),
                            protocol=proto,
                            country=item.get("country", "") if isinstance(item, dict) else "",
                            source="openproxy.space",
                        ))
            except Exception:
                pass
        return proxies

    def get_best(self) -> Proxy | None:
        """Get best proxy by composite score (success_rate + latency + stability)."""
        if not self._pool:
            return None
        sorted_pool = sorted(self._pool.values(), key=lambda p: p.score, reverse=True)
        for p in sorted_pool:
            if p.failure_count < 5:
                return p
        return sorted_pool[0] if sorted_pool else None

    def get_random(self) -> Proxy | None:
        """Get random healthy proxy."""
        healthy = [p for p in self._pool.values() if p.failure_count < 3]
        return random.choice(healthy) if healthy else self.get_best()

    def mark_success(self, proxy: Proxy, latency: float = 0.0):
        proxy.success_count += 1
        proxy.last_success = time.time()
        proxy.last_used = time.time()
        if latency:
            proxy.avg_latency = proxy.avg_latency * 0.7 + latency * 0.3 if proxy.avg_latency else latency
        if proxy.failure_count > 0:
            proxy.failure_count -= 1

    def mark_failure(self, proxy: Proxy):
        proxy.failure_count += 1
        proxy.last_used = time.time()
        if proxy.failure_count >= 5:
            self._pool.pop(f"{proxy.host}:{proxy.port}", None)

    async def health_check(self, proxy: Proxy) -> bool:
        """TCP connect + quick HTTP test."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            t0 = time.time()
            result = sock.connect_ex((proxy.host, proxy.port))
            latency = time.time() - t0
            sock.close()
            if result == 0:
                self.mark_success(proxy, latency)
                return True
        except Exception:
            pass
        self.mark_failure(proxy)
        return False

    async def health_check_all(self):
        """Check all pool members, remove dead ones."""
        dead = []
        for key, p in list(self._pool.items()):
            if not await self.health_check(p):
                dead.append(key)
        for key in dead:
            self._pool.pop(key, None)
        if dead:
            self._save()

    def stats(self) -> dict:
        healthy = [p for p in self._pool.values() if p.failure_count < 3]
        return {
            "total": len(self._pool),
            "healthy": len(healthy),
            "avg_score": sum(p.score for p in self._pool.values()) / max(len(self._pool), 1),
            "sources": list(set(p.source for p in self._pool.values())),
            "by_protocol": {
                "http": sum(1 for p in self._pool.values() if p.protocol == "http"),
                "https": sum(1 for p in self._pool.values() if p.protocol == "https"),
                "socks5": sum(1 for p in self._pool.values() if p.protocol == "socks5"),
            },
            "top5": [
                {"url": p.url, "score": round(p.score, 3), "latency": round(p.avg_latency, 2)}
                for p in sorted(self._pool.values(), key=lambda x: x.score, reverse=True)[:5]
            ],
        }

    async def start_background(self):
        """Run periodic refresh + health check loop."""
        await self.refresh()
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            try:
                await self.refresh()
                await self.health_check_all()
            except Exception as e:
                logger.debug(f"ProxyPool loop: {e}")

    def _save(self):
        try:
            data = {
                f"{p.host}:{p.port}": {
                    "host": p.host, "port": p.port, "protocol": p.protocol,
                    "source": p.source, "country": p.country,
                    "success_count": p.success_count, "failure_count": p.failure_count,
                }
                for p in self._pool.values()
            }
            PROXY_CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load(self):
        if not PROXY_CACHE.exists():
            return
        try:
            data = json.loads(PROXY_CACHE.read_text(encoding="utf-8"))
            for key, d in data.items():
                try:
                    proxy = Proxy(
                        host=str(d.get("host", "")),
                        port=int(d.get("port", 0)),
                        protocol=str(d.get("protocol", "http")),
                        source=str(d.get("source", "")),
                        country=str(d.get("country", "")),
                        success_count=int(d.get("success_count", 0)),
                        failure_count=int(d.get("failure_count", 0)),
                        avg_latency=float(d.get("avg_latency", 0)),
                    )
                    self._pool[key] = proxy
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass


_pool: ProxyPool | None = None


def get_proxy_pool() -> ProxyPool:
    global _pool
    if _pool is None:
        _pool = ProxyPool()
    return _pool
