"""Learning Resource Access — multi-path access to papers, docs, code from restricted networks.

7 strategies for accessing learning resources when direct connections are blocked:
  1. arXiv CN mirror — auto-rewrite arxiv.org → xxx.itp.ac.cn / cn.arxiv.org
  2. Sci-Hub DOI — unlock paywalled papers via DOI through rotating Sci-Hub domains
  3. Wayback Machine — retrieve blocked/deleted content via archive.org
  4. IPFS Gateway — decentralized content addressing via public gateways
  5. Semantic Scholar — academic search with built-in proxy support
  6. Cloudflare Warp — free WireGuard-based VPN tunnel as upstream proxy
  7. Offline pre-caching — background download of Python/JS/Rust docs
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin, urlparse

from loguru import logger

# ═══ Strategy 1: arXiv CN Mirrors ═══

ARXIV_MIRRORS = [
    ("https://arxiv.org", "https://xxx.itp.ac.cn"),
    ("https://export.arxiv.org", "https://xxx.itp.ac.cn"),
    ("http://arxiv.org", "https://xxx.itp.ac.cn"),
    ("https://arxiv.org", "https://cn.arxiv.org"),
]

ARXIV_PDF_MIRRORS = [
    "https://xxx.itp.ac.cn/pdf/{arxiv_id}",
    "https://cn.arxiv.org/pdf/{arxiv_id}",
    "https://export.arxiv.org/pdf/{arxiv_id}",
]


def arxiv_mirror_url(url: str) -> str:
    """Rewrite arXiv URL to use CN mirror automatically."""
    for original, mirror in ARXIV_MIRRORS:
        if url.startswith(original):
            return url.replace(original, mirror, 1)
    return url


def arxiv_pdf_mirror_url(arxiv_id: str) -> str:
    """Get PDF URL for an arXiv paper via mirror."""
    arxiv_id = arxiv_id.strip()
    if arxiv_id.startswith("arxiv:"):
        arxiv_id = arxiv_id[6:]
    return ARXIV_PDF_MIRRORS[0].format(arxiv_id=arxiv_id)


# ═══ Strategy 2: Sci-Hub DOI Integration ═══

SCIHUB_DOMAINS = [
    "sci-hub.se",
    "sci-hub.ru",
    "sci-hub.st",
    "sci-hub.ee",
    "sci-hub.ren",
]


async def scihub_fetch(doi: str, proxy: str | None = None) -> dict[str, Any]:
    """Fetch a paper PDF URL from Sci-Hub via DOI.

    Returns: {"success": bool, "pdf_url": str, "domain": str, "title": str}
    """
    import aiohttp
    doi = doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "", 1)

    for domain in SCIHUB_DOMAINS:
        try:
            target = f"https://{domain}/{doi}"
            kwargs = {"timeout": aiohttp.ClientTimeout(total=15)}
            if proxy:
                kwargs["proxy"] = proxy
            async with aiohttp.ClientSession() as session:
                async with session.get(target, **kwargs) as r:
                    if r.status == 200:
                        text = await r.text()
                        logger.info(f"Sci-Hub {domain}: retrieved DOI {doi[:40]}")
                        return {
                            "success": True,
                            "pdf_url": target,
                            "domain": domain,
                            "title": _extract_scihub_title(text),
                        }
        except Exception:
            continue

    return {"success": False, "pdf_url": "", "domain": "", "title": ""}


def _extract_scihub_title(html: str) -> str:
    m = re.search(r'<title>(.+?)</title>', html, re.IGNORECASE)
    if m:
        t = m.group(1)
        t = re.sub(r'\s*\|\s*Sci-Hub.*$', '', t)
        return t.strip()
    return ""


# ═══ Strategy 3: Wayback Machine (archive.org) ═══

ARCHIVE_API = "https://archive.org/wayback/available"


async def wayback_fetch(url: str, proxy: str | None = None) -> dict[str, Any]:
    """Retrieve page content via Internet Archive Wayback Machine."""
    import aiohttp

    try:
        params = {"url": url}
        kwargs: dict = {"timeout": aiohttp.ClientTimeout(total=15)}
        if proxy:
            kwargs["proxy"] = proxy
        async with aiohttp.ClientSession() as session:
            r = await session.get(ARCHIVE_API, params=params, **kwargs)
            if isinstance(r, dict):
                pass
            else:
                data = await r.json()
            snapshots = data.get("archived_snapshots", {})
            closest = snapshots.get("closest", {})
            if closest and closest.get("available"):
                archive_url = closest.get("url", "")
                if archive_url:
                    r2 = await session.get(archive_url, **kwargs)
                    if isinstance(r2, dict):
                        pass
                    else:
                        text = await r2.text()
                        return {
                            "success": True,
                            "archive_url": archive_url,
                            "timestamp": closest.get("timestamp", ""),
                            "text": text[:50000],
                        }
    except Exception:
        pass

    return {"success": False, "archive_url": "", "timestamp": "", "text": ""}


# ═══ Strategy 4: IPFS Gateway ═══

IPFS_GATEWAYS = [
    "https://ipfs.io/ipfs/",
    "https://cloudflare-ipfs.com/ipfs/",
    "https://dweb.link/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://ipfs.fleek.co/ipfs/",
]


async def ipfs_fetch(cid: str, proxy: str | None = None) -> dict[str, Any]:
    """Fetch content from IPFS via public gateways.

    Args:
        cid: IPFS content identifier (e.g. 'Qm...' or 'bafy...')
        proxy: optional proxy URL

    Returns: {"success": bool, "text": str, "gateway": str}
    """
    import aiohttp

    cid = cid.strip()
    for gateway in IPFS_GATEWAYS:
        try:
            url = gateway + cid
            kwargs: dict = {"timeout": aiohttp.ClientTimeout(total=20)}
            if proxy:
                kwargs["proxy"] = proxy
            async with aiohttp.ClientSession() as session:
                r = await session.get(url, **kwargs)
                if isinstance(r, dict):
                    pass
                elif r.status == 200:
                    text = await r.text()
                    return {"success": True, "text": text[:100000], "gateway": gateway}
        except Exception:
            continue
    return {"success": False, "text": "", "gateway": ""}


# ═══ Strategy 5: Semantic Scholar via proxy ═══

S2_API = "https://api.semanticscholar.org/graph/v1"


async def semantic_scholar_search(query: str, limit: int = 10,
                                   proxy: str | None = None) -> dict[str, Any]:
    """Search Semantic Scholar academic papers via proxy.

    Returns: {"success": bool, "papers": list[dict], "total": int}
    """
    import aiohttp

    try:
        url = f"{S2_API}/paper/search"
        params: dict = {"query": query, "limit": min(limit, 100),
                "fields": "title,url,year,authors,abstract,externalIds,publicationVenue"}
        kwargs: dict = {"timeout": aiohttp.ClientTimeout(total=15)}
        if proxy:
            kwargs["proxy"] = proxy
        async with aiohttp.ClientSession() as session:
            r = await session.get(url, params=params, **kwargs)
            data = await r.json() if not isinstance(r, dict) else r
            papers = []
            for p in data.get("data", []):
                papers.append({
                    "title": p.get("title", ""),
                    "url": p.get("url", ""),
                    "year": p.get("year"),
                    "authors": [a.get("name", "") for a in p.get("authors", [])],
                    "abstract": p.get("abstract", ""),
                    "doi": (p.get("externalIds") or {}).get("DOI", ""),
                })
            return {"success": True, "papers": papers,
                    "total": data.get("total", 0)}
    except Exception as e:
        logger.debug(f"Semantic Scholar search failed: {e}")
        return {"success": False, "papers": [], "total": 0}


# ═══ Strategy 6: Cloudflare Warp ═══

WARP_CLI_PATHS = [
    "warp-cli", "cloudflare-warp",
    "/usr/bin/warp-cli", "/usr/local/bin/warp-cli",
    shutil.which("warp-cli") or "",
]


def warp_is_installed() -> bool:
    for path in WARP_CLI_PATHS:
        if path and shutil.which(path):
            return True
    return False


async def warp_ensure_running(proxy_port: int = 40000) -> dict[str, Any]:
    """Ensure Cloudflare Warp is running as a SOCKS5 proxy.

    Returns: {"running": bool, "proxy_url": str, "message": str}
    """
    if not warp_is_installed():
        return {"running": False, "proxy_url": "", "message": "warp-cli not found"}

    warp_exe = shutil.which("warp-cli") or "warp-cli"

    try:
        try:
            from livingtree.treellm.unified_exec import run
            status_result = await run(f"{warp_exe} status", timeout=10)
            out = status_result.stdout
        except ImportError:
            proc = await asyncio.create_subprocess_exec(
                warp_exe, "status",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            out = stdout.decode(errors="replace")

        if "Connected" in out:
            proxy_url = f"socks5://127.0.0.1:{proxy_port}"
            return {"running": True, "proxy_url": proxy_url,
                    "message": "Warp Connected"}

        proc2 = await asyncio.create_subprocess_exec(
            warp_exe, "connect",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(proc2.communicate(), timeout=15)
        await asyncio.sleep(2)

        proc3 = await asyncio.create_subprocess_exec(
            warp_exe, "proxy-port", str(proxy_port),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(proc3.communicate(), timeout=5)

        proxy_url = f"socks5://127.0.0.1:{proxy_port}"
        return {"running": True, "proxy_url": proxy_url,
                "message": "Warp started"}
    except Exception as e:
        return {"running": False, "proxy_url": "",
                "message": str(e)}


# ═══ Strategy 7: Offline Doc Pre-caching ═══

DOC_CACHE_SOURCES = {
    "python": {
        "base": "https://docs.python.org/3/",
        "pages": ["index.html", "library/index.html", "tutorial/index.html",
                   "reference/index.html", "library/functions.html",
                   "library/stdtypes.html", "reference/datamodel.html",
                   "library/asyncio.html", "library/json.html"],
        "type": "docset",
    },
    "rust": {
        "base": "https://doc.rust-lang.org/stable/",
        "pages": ["std/index.html", "std/vec/struct.Vec.html",
                   "std/string/struct.String.html",
                   "std/option/enum.Option.html",
                   "std/result/enum.Result.html",
                   "std/collections/index.html"],
        "type": "docset",
    },
    "javascript": {
        "base": "https://developer.mozilla.org/en-US/docs/Web/",
        "pages": ["JavaScript/Reference/Global_Objects/Promise",
                   "JavaScript/Reference/Global_Objects/Array",
                   "JavaScript/Reference/Global_Objects/Object"],
        "type": "single",
    },
}


@dataclass
class DocCacheEntry:
    source: str
    url: str
    local_path: str
    size_bytes: int = 0
    cached_at: float = 0.0
    status: str = "pending"


@dataclass
class DocCacheStats:
    total_pages: int = 0
    cached_pages: int = 0
    failed_pages: int = 0
    total_bytes: int = 0
    last_cache: float = 0.0


class DocPreCache:
    """Background pre-caching of popular documentation.

    Downloads docs to data/docs_cache/ for offline access.
    """

    def __init__(self, cache_dir: str | Path = "data/docs_cache"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[DocCacheEntry] = []
        self._stats = DocCacheStats()

    async def pre_cache_all(self, proxy: str | None = None,
                            max_pages: int = 50) -> DocCacheStats:
        import aiohttp
        all_pages: list[tuple[str, str, str]] = []

        for src_name, src_config in DOC_CACHE_SOURCES.items():
            base = src_config["base"]
            for page in src_config["pages"]:
                if len(all_pages) >= max_pages:
                    break
                all_pages.append((src_name, base, page))

        self._stats = DocCacheStats(total_pages=len(all_pages))

        sem = asyncio.Semaphore(5)

        async def download_one(src_name: str, base: str, page: str):
            async with sem:
                url = urljoin(base, page)
                local_name = url.replace("https://", "").replace("/", "_")[:120]
                local_path = self._cache_dir / local_name
                entry = DocCacheEntry(source=src_name, url=url,
                                      local_path=str(local_path))

                if local_path.exists():
                    entry.size_bytes = local_path.stat().st_size
                    entry.status = "cached"
                    entry.cached_at = local_path.stat().st_mtime
                    self._stats.cached_pages += 1
                    self._stats.total_bytes += entry.size_bytes
                    self._entries.append(entry)
                    return

                try:
                    kwargs = {"timeout": aiohttp.ClientTimeout(total=30)}
                    if proxy:
                        kwargs["proxy"] = proxy
                    async with aiohttp.ClientSession() as session:
                        r = await session.get(url, **kwargs)
                        if isinstance(r, dict):
                            pass
                        elif r.status == 200:
                            html = await r.text()
                            local_path.write_text(html, encoding="utf-8")
                            entry.size_bytes = local_path.stat().st_size
                            entry.status = "ok"
                            entry.cached_at = time.time()
                            self._stats.cached_pages += 1
                            self._stats.total_bytes += entry.size_bytes
                            logger.debug(f"DocCache: cached {src_name}/{page}")
                        else:
                            entry.status = f"HTTP {r.status}"
                            self._stats.failed_pages += 1
                except Exception as e:
                    entry.status = str(e)[:80]
                    self._stats.failed_pages += 1

                self._entries.append(entry)

        tasks = [download_one(s, b, p) for s, b, p in all_pages]
        await asyncio.gather(*tasks, return_exceptions=True)

        self._stats.last_cache = time.time()
        self._save_stats()
        logger.info(f"DocCache: {self._stats.cached_pages}/{self._stats.total_pages} "
                     f"cached ({self._stats.total_bytes} bytes)")
        return self._stats

    def get_cache_path(self, url: str) -> str | None:
        local_name = url.replace("https://", "").replace("/", "_")[:120]
        path = self._cache_dir / local_name
        return str(path) if path.exists() else None

    def _save_stats(self):
        sf = self._cache_dir / "cache_stats.json"
        sf.write_text(json.dumps({
            "total_pages": self._stats.total_pages,
            "cached_pages": self._stats.cached_pages,
            "failed_pages": self._stats.failed_pages,
            "total_bytes": self._stats.total_bytes,
            "last_cache": self._stats.last_cache,
        }, indent=2), encoding="utf-8")


# ═══ Unified Learning Access Hub ═══


@dataclass
class LearningResourceResult:
    url: str
    title: str = ""
    text: str = ""
    pdf_url: str = ""
    source: str = ""
    method: str = ""
    success: bool = False


class LearningAccessHub:
    """Unified hub for accessing learning resources through any available path.

    Auto-detects available methods and chains fallbacks:
      1. Direct access (if network is open)
      2. arXiv CN mirror (for arXiv URLs)
      3. Sci-Hub (for paywalled papers via DOI)
      4. Wayback Machine (for blocked/deleted content)
      5. IPFS Gateway (for decentralized content)
      6. Semantic Scholar (for academic search)
      7. Doc pre-cache (for offline access)
    """

    def __init__(self):
        self._doc_cache = DocPreCache()
        self._scinet_proxy: str | None = None
        self._warp_proxy: str | None = None
        self._available_proxy: str | None = None
        self._warp_running = False

    async def ensure_proxy(self) -> str | None:
        """Ensure at least one proxy path is available."""
        if self._available_proxy:
            return self._available_proxy

        scinet_p = self._get_scinet_proxy()
        if scinet_p:
            self._scinet_proxy = scinet_p
            self._available_proxy = scinet_p
            return scinet_p

        if warp_is_installed() and not self._warp_running:
            warp = await warp_ensure_running()
            if warp["running"]:
                self._warp_proxy = warp["proxy_url"]
                self._warp_running = True
                self._available_proxy = warp["proxy_url"]
                return warp["proxy_url"]

        return None

    @staticmethod
    def _get_scinet_proxy() -> str | None:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            result = s.connect_ex(("127.0.0.1", 7890))
            s.close()
            if result == 0:
                return "http://127.0.0.1:7890"
        except Exception:
            pass
        return None

    async def fetch_paper(self, url_or_doi: str) -> LearningResourceResult:
        """Fetch an academic paper through any available path."""
        doi = url_or_doi.strip()

        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "", 1)
        if doi.startswith("10."):
            proxy = await self.ensure_proxy()
            result = await scihub_fetch(doi, proxy)
            if result["success"]:
                return LearningResourceResult(
                    url=doi, pdf_url=result["pdf_url"],
                    title=result.get("title", ""),
                    source="sci-hub", method=result["domain"], success=True)

        if "arxiv.org" in doi:
            mir = arxiv_mirror_url(doi)
            return LearningResourceResult(
                url=mir, source="arxiv", method="cn_mirror",
                success=True,
                pdf_url=arxiv_pdf_mirror_url(
                    doi.split("/abs/")[-1] if "/abs/" in doi else doi.split("/")[-1]))

        archive = await wayback_fetch(doi, await self.ensure_proxy())
        if archive["success"]:
            return LearningResourceResult(
                url=doi, text=archive["text"],
                source="archive.org", method="wayback", success=True)

        return LearningResourceResult(url=doi, method="none", success=False)

    async def search_academic(self, query: str, limit: int = 10) -> list[dict]:
        """Search academic papers via Semantic Scholar (with proxy if needed)."""
        proxy = await self.ensure_proxy()
        result = await semantic_scholar_search(query, limit, proxy)
        return result.get("papers", [])

    async def fetch_content(self, url: str) -> LearningResourceResult:
        """Fetch any blocked content via best available path."""
        import aiohttp

        proxy = await self.ensure_proxy()
        try:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=15)}
            if proxy:
                kwargs["proxy"] = proxy
            async with aiohttp.ClientSession() as session:
                r = await session.get(url, **kwargs)
                if isinstance(r, dict):
                    pass
                elif r.status == 200:
                    return LearningResourceResult(
                        url=url, text=await r.text(),
                        method="direct" if not proxy else "proxy", success=True)
        except Exception:
            pass

        ipfs_m = re.search(r'(Qm[1-9A-HJ-NP-Za-km-z]{44,}|bafy[a-z2-7]{56,})', url)
        if ipfs_m:
            ipfs_r = await ipfs_fetch(ipfs_m.group(1), proxy)
            if ipfs_r["success"]:
                return LearningResourceResult(
                    url=url, text=ipfs_r["text"],
                    method="ipfs", source=ipfs_r["gateway"], success=True)

        archive = await wayback_fetch(url, proxy)
        if archive["success"]:
            return LearningResourceResult(
                url=url, text=archive["text"],
                method="wayback", source="archive.org", success=True)

        return LearningResourceResult(url=url, method="none", success=False)

    async def pre_cache_docs(self, proxy: str | None = None) -> DocCacheStats:
        if proxy is None:
            proxy = await self.ensure_proxy()
        return await self._doc_cache.pre_cache_all(proxy)

    def get_doc_cache(self) -> DocPreCache:
        return self._doc_cache


_learning_access: LearningAccessHub | None = None


def get_learning_access() -> LearningAccessHub:
    global _learning_access
    if _learning_access is None:
        _learning_access = LearningAccessHub()
    return _learning_access


def is_arxiv_url(url: str) -> bool:
    return any(d in url for d in ("arxiv.org", "arxiv.org/abs", "arxiv.org/pdf"))


def mirror_learning_url(url: str) -> str:
    """Rewrite any supported learning resource URL to its mirror."""
    if is_arxiv_url(url):
        return arxiv_mirror_url(url)
    return url
