"""UnifiedSearch — multi-engine web search with automatic fallback + parallel meta-search.

LDR-inspired: parallel multi-engine search with Reciprocal Rank Fusion (RRF)
meta-ranking. Searches all available engines simultaneously, merges results
via RRF, and deduplicates by URL.

Fallback chain (7 engines, all free):
  1. SparkSearch (iFlytek ONE Search API — paid, structured results)
  2. DuckDuckGo (DDGSearch — free, privacy-friendly)
  3. BingSearch (HTML scraping — free, no API key)
  4. SearXNGSearcher (public instances — free, meta-engine)
  5. Wikipedia (REST API — free, factual knowledge)
  6. LLMWebSearch (星火Lite/智谱GLM — free but unreliable)

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
    """Multi-engine search dispatcher with automatic failover.

    Engine priority (sequential fallback):
      1. SparkSearch (ONE Search API — paid, structured results)
      2. DuckDuckGo (free, privacy-friendly)
      3. BingSearch (free, HTML scraping)
      4. SearXNGSearcher (free, public meta-search instances)
      5. WikipediaSearch (free, factual knowledge API)
      6. LLMWebSearch (free LLM 联网搜索 — 星火Lite/智谱GLM)
    """

    def __init__(self, spark_search=None, ddg_search=None, llm_search=None,
                 bing_search=None, searxng_search=None, wiki_search=None):
        self._spark = spark_search
        self._ddg = ddg_search
        self._llm = llm_search
        self._bing = bing_search
        self._searxng = searxng_search
        self._wiki = wiki_search
        self._initialized = False

    def _ensure_engines(self):
        if self._initialized:
            return
        if self._spark is None:
            try:
                from .spark_search import create_spark_search
                self._spark = create_spark_search()
            except Exception:
                self._spark = False
        if self._ddg is None:
            try:
                from .ddg_search import DDGSearch
                self._ddg = DDGSearch()
            except Exception:
                self._ddg = False
        if self._bing is None:
            try:
                from .bing_search import BingSearch
                self._bing = BingSearch()
            except Exception:
                self._bing = False
        if self._searxng is None:
            try:
                from .searxng_search import SearXNGSearcher
                self._searxng = SearXNGSearcher()
            except Exception:
                self._searxng = False
        if self._wiki is None:
            try:
                from .wikipedia_search import WikipediaSearch
                self._wiki = WikipediaSearch()
            except Exception:
                self._wiki = False
        if self._llm is None:
            try:
                from .llm_web_search import get_llm_web_search
                self._llm = get_llm_web_search()
            except Exception:
                self._llm = False
        self._initialized = True

    async def _try_engine(self, engine, engine_name: str, q: str,
                          limit: int, result_cls=None) -> list[UnifiedResult] | None:
        """Try one engine, return UnifiedResults on success, None on failure."""
        try:
            raw = await engine.query(q, limit=limit)
            if not raw:
                return None
            results = []
            for r in raw:
                if result_cls and isinstance(r, result_cls):
                    results.append(UnifiedResult(
                        title=r.title, url=r.url,
                        summary=getattr(r, 'snippet', '') or getattr(r, 'summary', ''),
                        source=engine_name,
                    ))
                elif hasattr(r, 'title'):
                    results.append(UnifiedResult(
                        title=r.title, url=r.url,
                        summary=getattr(r, 'snippet', '') or getattr(r, 'summary', ''),
                        source=engine_name,
                    ))
            if results:
                logger.info(f"{engine_name}: {len(results)} results for '{q[:50]}'")
                return self._filter_by_credibility(results)
        except Exception as e:
            logger.debug(f"{engine_name} failed: {e}")
        return None

    @with_resilience(max_retries=2)
    async def query(self, q: str, limit: int = 10) -> list[UnifiedResult]:
        """Search across engines with automatic fallback."""
        self._ensure_engines()

        # Engine 1: SparkSearch (paid, best quality)
        if self._spark and self._spark is not False:
            result = await self._try_engine(self._spark, "spark", q, limit)
            if result:
                return result

        # Engine 2: DuckDuckGo (free, reliable)
        if self._ddg and self._ddg is not False:
            result = await self._try_engine(self._ddg, "ddg", q, limit)
            if result:
                return result

        # Engine 3: BingSearch (free, HTML scraping)
        if self._bing and self._bing is not False:
            result = await self._try_engine(self._bing, "bing", q, limit)
            if result:
                return result

        # Engine 4: SearXNGSearcher (free, meta-engine via public instances)
        if self._searxng and self._searxng is not False:
            result = await self._try_engine(self._searxng, "searxng", q, limit)
            if result:
                return result

        # Engine 5: WikipediaSearch (free, best for factual/knowledge queries)
        if self._wiki and self._wiki is not False:
            result = await self._try_engine(self._wiki, "wiki", q, limit)
            if result:
                return result

        # Engine 6: LLMWebSearch (free but unreliable — last resort)
        if self._llm and self._llm is not False:
            result = await self._try_engine(self._llm, "llm", q, limit)
            if result:
                return result

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
        engine_specs = [
            ("spark", self._spark, None),
            ("ddg", self._ddg, None),
            ("bing", self._bing, None),
            ("searxng", self._searxng, None),
            ("wiki", self._wiki, None),
            ("llm", self._llm, None),
        ]

        engines = [(n, e) for n, e, _ in engine_specs if e and e is not False]

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
            return [UnifiedResult(**r) if isinstance(r, dict) else r for r in raw]
        except Exception as e:
            logger.warning(f"Search engine '{name}' failed: {e}")
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
