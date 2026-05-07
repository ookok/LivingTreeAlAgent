"""UnifiedSearch — multi-engine web search with automatic fallback + parallel meta-search.

LDR-inspired: parallel multi-engine search with Reciprocal Rank Fusion (RRF)
meta-ranking. Searches all available engines simultaneously, merges results
via RRF, and deduplicates by URL.

Priority: SparkSearch → DDGSearch (fallback, parallel mode disabled).
Parallel mode: runs all engines concurrently, merges via RRF.

Usage:
    from .unified_search import search, search_parallel
    results = await search("Python async best practices", limit=5)
    results = await search_parallel("环评标准 大气扩散", limit=10)  # LDR-style
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from loguru import logger

from ..network.resilience import with_resilience


@dataclass
class UnifiedResult:
    title: str
    url: str
    summary: str = ""
    source: str = ""

    def format_display(self) -> str:
        src = f"[dim]({self.source})[/dim]"
        lines = [f"[bold]{self.title}[/bold] {src}"]
        lines.append(f"  [dim]{self.url}[/dim]")
        if self.summary:
            lines.append(f"  {self.summary[:150]}")
        return "\n".join(lines)


class UnifiedSearch:
    """Multi-engine search dispatcher with automatic failover."""

    def __init__(self, spark_search=None, ddg_search=None):
        self._spark = spark_search
        self._ddg = ddg_search
        self._initialized = False

    def _ensure_engines(self):
        if self._initialized:
            return
        if self._spark is None:
            try:
                from .spark_search import create_spark_search
                self._spark = create_spark_search()
            except Exception:
                self._spark = False  # mark as unavailable
        if self._ddg is None:
            try:
                from .ddg_search import DDGSearch
                self._ddg = DDGSearch()
            except Exception:
                self._ddg = False
        self._initialized = True

    @with_resilience(max_retries=2)
    async def query(self, q: str, limit: int = 10) -> list[UnifiedResult]:
        """Search across engines with automatic fallback."""
        self._ensure_engines()

        # Engine 1: SparkSearch
        if self._spark and self._spark is not False:
            try:
                from .spark_search import SearchResult
                raw = await self._spark.query(q, limit=limit)
                if raw:
                    results = []
                    for r in raw:
                        if isinstance(r, SearchResult):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=r.summary, source="spark",
                            ))
                        elif hasattr(r, 'title'):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=getattr(r, 'summary', ''), source="spark",
                            ))
                    if results:
                        logger.info(f"SparkSearch: {len(results)} results for '{q[:50]}'")
                        return self._filter_by_credibility(results)
            except Exception as e:
                logger.debug(f"SparkSearch failed: {e}")

        # Engine 2: DDGSearch (fallback)
        if self._ddg and self._ddg is not False:
            try:
                from .ddg_search import DDGResult
                raw = await self._ddg.query(q, limit=limit)
                if raw:
                    results = []
                    for r in raw:
                        if isinstance(r, DDGResult):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=r.summary, source="ddg",
                            ))
                        elif hasattr(r, 'title'):
                            results.append(UnifiedResult(
                                title=r.title, url=r.url,
                                summary=getattr(r, 'summary', ''), source="ddg",
                            ))
                    if results:
                        logger.info(f"DDGSearch: {len(results)} results for '{q[:50]}'")
                        return self._filter_by_credibility(results)
            except Exception as e:
                logger.debug(f"DDGSearch failed: {e}")

        return []

    def format_results(self, results: list[UnifiedResult], max_results: int = 10) -> str:
        if not results:
            return "[dim]No results found[/dim]"

        sources = set(r.source for r in results)
        source_str = "+".join(sorted(sources))
        lines = [f"[bold]Search Results ({len(results)}) [{source_str}]:[/bold]"]

        for r in results[:max_results]:
            lines.append(f"  [bold #58a6ff]{r.title[:80]}[/bold #58a6ff]")
            lines.append(f"    [dim]{r.url}[/dim]")
            if r.summary:
                lines.append(f"    {r.summary[:150]}")
            lines.append("")

        return "\n".join(lines)

    # ── LDR-inspired parallel multi-engine search ──

    async def query_parallel(self, q: str, limit: int = 10) -> list[UnifiedResult]:
        """LDR-style: search all engines in parallel, merge with RRF.

        Runs all available engines concurrently. Results are merged via
        Reciprocal Rank Fusion (k=60) and deduplicated by URL.
        Falls back to sequential search on error.
        """
        self._ensure_engines()
        engines = []

        if self._spark and self._spark is not False:
            engines.append(("spark", self._spark))
        if self._ddg and self._ddg is not False:
            engines.append(("ddg", self._ddg))

        if not engines:
            return []

        if len(engines) == 1:
            return await self.query(q, limit)

        tasks = [self._search_engine(name, engine, q, limit)
                 for name, engine in engines]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        engine_results: dict[str, list[UnifiedResult]] = {}
        for i, result in enumerate(all_results):
            name = engines[i][0]
            if isinstance(result, Exception):
                logger.debug(f"Engine {name} failed: {result}")
                continue
            if result:
                engine_results[name] = result

        if not engine_results:
            return []

        if len(engine_results) == 1:
            return list(engine_results.values())[0]

        merged = self._rrf_merge(engine_results, limit)
        logger.info(
            f"Parallel search: {len(all_results)} engines, "
            f"{sum(len(v) for v in engine_results.values())} raw → "
            f"{len(merged)} merged for '{q[:50]}'")
        return merged

    async def _search_engine(self, name: str, engine, q: str,
                              limit: int) -> list[UnifiedResult]:
        try:
            raw = await engine.query(q, limit=limit)
            if not raw:
        return []

    def _filter_by_credibility(self, results: list[UnifiedResult]) -> list[UnifiedResult]:
        """Down-rank low-credibility sources (LDR-inspired source scoring)."""
        try:
            from ..knowledge.source_credibility import get_source_credibility
            scorer = get_source_credibility()
            for r in results:
                cred = scorer.score(r.url, r.title, r.summary)
                if cred.overall < 0.3:
                    r.source += " [low-cred]"
        except Exception:
            pass
        return results

            from .ddg_search import DDGResult
            if name == "spark":
                from .spark_search import SearchResult
            results = []
            for r in raw:
                if hasattr(r, 'title') and hasattr(r, 'url'):
                    results.append(UnifiedResult(
                        title=r.title, url=r.url,
                        summary=getattr(r, 'summary', ''), source=name,
                    ))
            return results
        except Exception as e:
            logger.debug(f"Engine {name} query failed: {e}")
            return []

    @staticmethod
    def _rrf_merge(engine_results: dict[str, list[UnifiedResult]],
                   limit: int = 10, k: int = 60) -> list[UnifiedResult]:
        """Reciprocal Rank Fusion across multiple search engines.

        RRF formula: score(d) = Σ 1/(k + rank_i(d))
        Where k=60 (standard), rank is 1-indexed per engine.
        """
        url_scores: dict[str, float] = {}
        url_data: dict[str, UnifiedResult] = {}

        for source, results in engine_results.items():
            for rank, r in enumerate(results, 1):
                url = r.url
                score = 1.0 / (k + rank)
                url_scores[url] = url_scores.get(url, 0.0) + score
                if url not in url_data:
                    url_data[url] = r

        sorted_urls = sorted(url_scores, key=lambda u: url_scores[u], reverse=True)
        merged = []
        for url in sorted_urls[:limit]:
            r = url_data[url]
            r.summary = f"[{url_scores[url]:.3f}] " + r.summary[:140]
            merged.append(r)

        return merged


# ═══ Global singleton ═══

_unified_search: UnifiedSearch | None = None


def get_unified_search() -> UnifiedSearch:
    global _unified_search
    if _unified_search is None:
        _unified_search = UnifiedSearch()
    return _unified_search


async def search(query: str, limit: int = 10) -> list[UnifiedResult]:
    return await get_unified_search().query(query, limit=limit)


async def search_parallel(query: str, limit: int = 10) -> list[UnifiedResult]:
    """LDR-style: parallel multi-engine search with RRF mergin."""
    return await get_unified_search().query_parallel(query, limit=limit)
