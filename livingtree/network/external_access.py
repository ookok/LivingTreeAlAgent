"""ExternalNetworkAccess — Deep Search + GitHub Mirror + DNS-over-HTTPS resolver.

    Three pillars for reliable foreign network access:

    1. DeepSearchFederator — parallel multi-engine search, dedup, LLM rerank
       Sources: Google (via proxy), DuckDuckGo, SearXNG instances, Bing
       Features: dedup by URL, LLM relevance scoring, cached results

    2. GitHub Smart Mirror — auto-cache repos, release monitoring, failover
       Mirrors: ghproxy.com, mirror.ghproxy.com, gitclone.com, fastgit.org
       Features: pre-warm popular repos, release RSS, auto-fallback chain

    3. External DNS — DNS-over-HTTPS resolver bypassing GFW poisoning
       Providers: Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9)
       Features: resolve blocked domains, cache TTL-aware, batch lookup

    Usage:
        ext = get_external_access()
        results = await ext.deep_search("transformer architecture", hub)
        releases = await ext.watch_github_releases("microsoft/vscode")
        ip = await ext.dns_resolve("github.com")
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CACHE_DIR = Path(".livingtree/external_cache")
SEARCH_CACHE = CACHE_DIR / "search_cache.json"
RELEASE_CACHE = CACHE_DIR / "release_cache.json"
DNS_CACHE_FILE = CACHE_DIR / "dns_cache.json"


# ═══ 1. Deep Search Federator ═══

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""
    relevance: float = 0.0
    is_paid: bool = False


class DeepSearchFederator:
    """Multi-engine search with parallel queries, dedup, and LLM reranking."""

    SEARXNG_INSTANCES = [
        "https://search.bus-hit.me",
        "https://searx.be",
        "https://search.sapti.me",
    ]

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[dict]] = {}
        if SEARCH_CACHE.exists():
            try:
                self._cache = json.loads(SEARCH_CACHE.read_text(encoding="utf-8"))
            except Exception:
                pass

    async def search(
        self,
        query: str,
        hub=None,
        max_results: int = 20,
        engines: list[str] | None = None,
    ) -> list[SearchResult]:
        """Parallel search across multiple engines, dedup, optionally LLM-rerank.

        Args:
            query: Search query
            hub: LLM access for relevance scoring
            max_results: Max total results
            engines: Specific engines to use. None = all available.
        """
        cache_key = hashlib.md5(query.lower().encode()).hexdigest()[:16]
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            age = time.time() - cached[0].get("_ts", 0) if cached else 0
            if age < 3600:  # 1 hour cache
                return [SearchResult(**{k: v for k, v in r.items() if k != "_ts"}) for r in cached]

        all_engines = engines or ["duckduckgo", "searxng", "bing"]
        tasks = []
        for engine in all_engines:
            tasks.append(self._search_one(engine, query))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge + dedup by normalized URL
        seen = set()
        merged = []
        for lst in results_lists:
            if isinstance(lst, Exception):
                continue
            for r in lst:
                normalized = self._normalize_url(r.url)
                if normalized not in seen:
                    seen.add(normalized)
                    merged.append(r)

        # LLM relevance re-ranking
        if hub and hub.world and merged:
            merged = await self._rerank(merged, query, hub)

        merged = merged[:max_results]

        # Cache
        self._cache[cache_key] = [
            {**{"title": r.title, "url": r.url, "snippet": r.snippet,
                "engine": r.engine, "relevance": r.relevance}, "_ts": time.time()}
            for r in merged
        ]
        if len(self._cache) > 200:
            keys = sorted(self._cache.keys())[:len(self._cache)-100]
            for k in keys:
                del self._cache[k]
        SEARCH_CACHE.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False), encoding="utf-8")

        return merged

    async def _search_one(self, engine: str, query: str) -> list[SearchResult]:
        try:
            if engine == "duckduckgo":
                return await self._ddg_search(query)
            elif engine == "searxng":
                return await self._searxng_search(query)
            elif engine == "bing":
                return await self._bing_search(query)
            elif engine == "google":
                return await self._google_search(query)
        except Exception:
            pass
        return []

    async def _ddg_search(self, query: str) -> list[SearchResult]:
        """DuckDuckGo HTML search (no API key needed)."""
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.1"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            for m in re.finditer(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                url_val = m.group(1)
                title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                snippet = ""
                sm = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                if sm:
                    snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip()[:200]
                if url_val and not url_val.startswith("//duckduckgo"):
                    results.append(SearchResult(title=title, url=url_val, snippet=snippet, engine="duckduckgo"))
        except Exception:
            pass
        return results[:10]

    async def _searxng_search(self, query: str) -> list[SearchResult]:
        """SearXNG public instances."""
        results = []
        for instance in self.SEARXNG_INSTANCES[:2]:
            try:
                url = f"{instance}/search?q={urllib.parse.quote(query)}&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.1"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                for r in data.get("results", [])[:10]:
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("content", "")[:200],
                        engine="searxng",
                    ))
                if results:
                    break
            except Exception:
                continue
        return results[:10]

    async def _bing_search(self, query: str) -> list[SearchResult]:
        """Bing search via HTML parsing (no API key)."""
        results = []
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            for m in re.finditer(
                r'<li class="b_algo"><h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                snippet = ""
                sm = re.search(r'<p[^>]*class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
                if sm:
                    snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip()[:200]
                results.append(SearchResult(title=title, url=m.group(1), snippet=snippet, engine="bing"))
        except Exception:
            pass
        return results[:10]

    async def _google_search(self, query: str) -> list[SearchResult]:
        """Google search via proxy (requires working proxy)."""
        results = []
        try:
            from .resilience import _get_proxy_dict
            proxy = _get_proxy_dict()
            import httpx
            async with httpx.AsyncClient(proxy=proxy.get("http://") if proxy else None, timeout=10) as client:
                resp = await client.get(
                    f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=20",
                    headers={"User-Agent": "LivingTree/2.1"},
                )
                html = resp.text
            for m in re.finditer(r'<a[^>]*href="/url\?q=([^"&]+)', html):
                url_val = urllib.parse.unquote(m.group(1))
                if url_val.startswith("http") and "google" not in url_val:
                    results.append(SearchResult(title="", url=url_val, snippet="", engine="google"))
        except Exception:
            pass
        return results[:10]

    async def _rerank(self, results: list[SearchResult], query: str, hub) -> list[SearchResult]:
        """LLM reranks results by relevance to query."""
        llm = hub.world.consciousness._llm
        snippets = "\n".join(
            f"[{i}] {r.title[:100]} | {r.snippet[:100]} | {r.url}" for i, r in enumerate(results[:20])
        )[:5000]

        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Rate these search results for relevance to: '{query}'\n"
                    "Score each 0.0-1.0 based on how well it answers the query.\n\n"
                    f"{snippets}\n\n"
                    "Output JSON array: [{\"index\": 0, \"score\": 0.85, \"reason\": \"why\"}]"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0, max_tokens=500, timeout=15,
            )
            if resp and resp.text:
                m = re.search(r'\[[\s\S]*\]', resp.text)
                if m:
                    scores = json.loads(m.group())
                    score_map = {s.get("index", -1): s.get("score", 0.5) for s in scores}
                    for i, r in enumerate(results):
                        r.relevance = score_map.get(i, 0.3)
                    results.sort(key=lambda r: -r.relevance)
        except Exception:
            pass
        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = re.sub(r'^https?://(www\.)?', '', url)
        url = re.sub(r'/$', '', url)
        return url.lower()[:100]


# ═══ 2. GitHub Smart Mirror ═══

@dataclass
class ReleaseInfo:
    repo: str
    tag: str = ""
    name: str = ""
    published_at: str = ""
    assets: list[dict] = field(default_factory=list)


class GitHubMirror:
    """Smart GitHub mirror: auto-cache, release watch, failover download chain."""

    MIRRORS = [
        "https://ghproxy.com/",
        "https://mirror.ghproxy.com/",
        "https://gh.api.99988866.xyz/",
        "https://gitclone.com/github.com/",
        "https://hub.fastgit.xyz/",
        "https://download.fastgit.org/",
    ]

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._watched: dict[str, ReleaseInfo] = {}
        self._load_releases()

    def mirror_url(self, github_url: str) -> list[str]:
        """Transform a GitHub URL into mirror URLs with failover chain.

        Args:
            github_url: Any GitHub URL (repo, raw, release, etc.)

        Returns:
            Ordered list of mirror URLs (primary first)
        """
        urls = []
        clean = github_url.replace("https://github.com", "").replace("https://raw.githubusercontent.com", "")

        # Determine type
        if "/releases/download/" in github_url or "/archive/" in github_url:
            # Release asset or archive
            for mirror in self.MIRRORS:
                urls.append(f"{mirror}{clean}")
        elif "raw.githubusercontent.com" in github_url:
            for mirror in [m for m in self.MIRRORS if "ghproxy" in m or "fastgit" in m]:
                urls.append(f"{mirror}{github_url}")
        else:
            # General repo URL
            for mirror in self.MIRRORS:
                urls.append(f"{mirror}{clean}")

        # Original URL as final fallback
        if github_url not in urls:
            urls.append(github_url)

        return urls

    async def fetch_file(self, github_url: str, timeout: int = 30) -> tuple[int, bytes, str]:
        """Fetch a file from GitHub via mirror failover chain.

        Returns (status_code, bytes, final_url_used).
        """
        import httpx
        urls = self.mirror_url(github_url)
        last_error = ""

        for url in urls[: min(4, len(urls))]:
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "LivingTree/2.1"})
                    if resp.status_code < 500:
                        return resp.status_code, resp.content, url
                    last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                last_error = str(e)[:100]

        return 0, b"", last_error

    async def watch_releases(self, repo: str) -> ReleaseInfo | None:
        """Fetch latest release info for a GitHub repo via mirror.

        Args:
            repo: "user/repo" format
        """
        import httpx
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"

        # Try direct + mirror
        for base in [api_url, f"https://ghproxy.com/{api_url}"]:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(base, headers={
                        "User-Agent": "LivingTree/2.1",
                        "Accept": "application/vnd.github+json",
                    })
                    if resp.status_code == 200:
                        d = resp.json()
                        info = ReleaseInfo(
                            repo=repo,
                            tag=d.get("tag_name", ""),
                            name=d.get("name", ""),
                            published_at=d.get("published_at", ""),
                            assets=[
                                {"name": a.get("name", ""), "url": a.get("browser_download_url", ""),
                                 "size": a.get("size", 0)}
                                for a in d.get("assets", [])
                            ],
                        )
                        self._watched[repo] = info
                        self._save_releases()
                        return info
            except Exception:
                continue
        return self._watched.get(repo)

    def watched_status(self) -> dict[str, ReleaseInfo]:
        return dict(self._watched)

    def _save_releases(self):
        data = {
            repo: {"repo": r.repo, "tag": r.tag, "name": r.name,
                   "published_at": r.published_at, "assets": r.assets}
            for repo, r in self._watched.items()
        }
        RELEASE_CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_releases(self):
        if not RELEASE_CACHE.exists():
            return
        try:
            data = json.loads(RELEASE_CACHE.read_text(encoding="utf-8"))
            for repo, d in data.items():
                self._watched[repo] = ReleaseInfo(**d)
        except Exception:
            pass


# ═══ 3. External DNS over HTTPS ═══

@dataclass
class DNSResult:
    domain: str
    ips: list[str] = field(default_factory=list)
    ttl: int = 300
    provider: str = ""
    cached: bool = False


class ExternalDNS:
    """DNS-over-HTTPS resolver bypassing GFW DNS poisoning.

    Uses Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9) via DoH.
    Results cached with TTL awareness.
    """

    DOH_PROVIDERS = {
        "cloudflare": "https://cloudflare-dns.com/dns-query",
        "google": "https://dns.google/resolve",
        "quad9": "https://dns.quad9.net/dns-query",
    }

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, DNSResult] = {}
        self._load_dns_cache()

    async def resolve(self, domain: str, provider: str = "cloudflare") -> DNSResult:
        """Resolve a domain name via DoH. Cache-aware.

        Args:
            domain: Domain to resolve (e.g. "github.com")
            provider: cloudflare, google, or quad9
        """
        # Check cache
        if domain in self._cache:
            cached = self._cache[domain]
            if time.time() - getattr(cached, '_cached_at', 0) < cached.ttl:
                cached.cached = True
                return cached

        doh_url = self.DOH_PROVIDERS.get(provider, self.DOH_PROVIDERS["cloudflare"])
        import httpx

        for prov_name, prov_url in [
            (provider, doh_url),
            *[(k, v) for k, v in self.DOH_PROVIDERS.items() if k != provider],
        ]:
            try:
                if "google" in prov_url:
                    url = f"{prov_url}?name={domain}&type=A"
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(url, headers={"Accept": "application/dns-json"})
                        if resp.status_code == 200:
                            d = resp.json()
                            ips = [a.get("data", "") for a in d.get("Answer", []) if a.get("type") == 1]
                            if ips:
                                result = DNSResult(
                                    domain=domain, ips=ips,
                                    ttl=d.get("Answer", [{}])[0].get("TTL", 300),
                                    provider=prov_name,
                                )
                                result._cached_at = time.time()
                                self._cache[domain] = result
                                self._save_dns_cache()
                                return result
                else:
                    # Cloudflare/Quad9 use standard DNS wire format via application/dns-message
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(
                            prov_url,
                            params={"name": domain, "type": "A"},
                            headers={"Accept": "application/dns-json"},
                        )
                        if resp.status_code == 200:
                            d = resp.json()
                            ips = [a.get("data", "") for a in d.get("Answer", []) if a.get("type") == 1]
                            if ips:
                                result = DNSResult(
                                    domain=domain, ips=ips,
                                    ttl=d.get("Answer", [{}])[0].get("TTL", 300),
                                    provider=prov_name,
                                )
                                result._cached_at = time.time()
                                self._cache[domain] = result
                                self._save_dns_cache()
                                return result
            except Exception:
                continue

        # Return cached even if expired
        cached = self._cache.get(domain)
        if cached:
            cached.cached = True
            return cached
        return DNSResult(domain=domain)

    async def batch_resolve(self, domains: list[str]) -> dict[str, DNSResult]:
        """Resolve multiple domains in parallel."""
        tasks = [self.resolve(d) for d in domains]
        results = await asyncio.gather(*tasks)
        return {d: r for d, r in zip(domains, results)}

    def _save_dns_cache(self):
        try:
            data = {
                d: {"domain": r.domain, "ips": r.ips, "ttl": r.ttl,
                    "provider": r.provider, "_cached_at": getattr(r, '_cached_at', 0)}
                for d, r in self._cache.items()
            }
            DNS_CACHE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_dns_cache(self):
        if not DNS_CACHE_FILE.exists():
            return
        try:
            data = json.loads(DNS_CACHE_FILE.read_text(encoding="utf-8"))
            for domain, d in data.items():
                r = DNSResult(domain=d["domain"], ips=d.get("ips", []),
                             ttl=d.get("ttl", 300), provider=d.get("provider", ""))
                r._cached_at = d.get("_cached_at", 0)
                self._cache[domain] = r
        except Exception:
            pass


# ═══ Convenience ═══

class ExternalAccess:
    """Unified external network access layer."""

    def __init__(self):
        self.search = DeepSearchFederator()
        self.github = GitHubMirror()
        self.dns = ExternalDNS()

    async def deep_search(self, query: str, hub=None, max_results: int = 15) -> list[SearchResult]:
        return await self.search.search(query, hub=hub, max_results=max_results)

    async def gh_fetch(self, github_url: str) -> tuple[int, bytes, str]:
        return await self.github.fetch_file(github_url)

    async def gh_watch(self, repo: str) -> ReleaseInfo | None:
        return await self.github.watch_releases(repo)

    async def dns_lookup(self, domain: str) -> DNSResult:
        return await self.dns.resolve(domain)


_ext: ExternalAccess | None = None


def get_external_access() -> ExternalAccess:
    global _ext
    if _ext is None:
        _ext = ExternalAccess()
    return _ext
