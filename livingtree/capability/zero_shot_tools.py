"""Zero-Shot Tool Discovery — auto-search PublicAPIs and generate tool code.

When the system encounters a task for which no existing tool exists, it
searches the PublicAPIs directory (1400+ free APIs across 50+ categories),
matches relevant services, and generates HTTP calling code using the
project's existing request infrastructure.

This enables the system to dynamically extend its own capability set
without manual intervention — true zero-shot tool acquisition.

Architecture:
    discover_tool(task_description, consciousness) →
        ├─ Extract keywords from task
        ├─ Search PublicAPIs by keyword
        ├─ Rank results by relevance (name match bonus)
        ├─ Generate calling code stub via consciousness
        └─ Cache discovery in self._discovered

Integration:
    zst = get_zero_shot_tools()
    result = await zst.discover_tool("get weather for Tokyo")
    if result:
        print(f"Discovered {result['api_name']}: {result['api_url']}")
    stats = zst.stats()

Related modules:
    - public_apis_resource.py — searchable directory of 1400+ free APIs
    - skill_discovery.py — existing skill-finding logic
    - tool_synthesis.py — dynamic tool code generation
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolDiscovery:
    """A single tool discovered via zero-shot search."""
    api_name: str
    api_url: str
    auth: str = ""
    description: str = ""
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    generated_code: str = ""
    timestamp: float = field(default_factory=time.time)
    rank_score: float = 0.0

    def summary(self) -> str:
        return (
            f"ToolDiscovery({self.api_name}, "
            f"url={self.api_url[:50]}..., "
            f"score={self.rank_score:.2f})"
        )

    def to_dict(self) -> dict:
        return {
            "api_name": self.api_name,
            "api_url": self.api_url,
            "auth": self.auth,
            "description": self.description,
            "category": self.category,
            "keywords": self.keywords,
            "rank_score": self.rank_score,
        }


class ZeroShotToolDiscovery:
    """Auto-discover tools from PublicAPIs when existing tools cannot help.

    Acts as a fallback mechanism: when the task execution pipeline cannot
    find a suitable registered tool, ZeroShotToolDiscovery searches the
    PublicAPIs catalog for external services that match the task description.
    It then optionally generates calling code using the consciousness LLM.

    Usage:
        zst = get_zero_shot_tools()
        result = await zst.discover_tool("calculate carbon footprint")
        if result:
            api_info = result["info"]
            code = result.get("code")
    """

    _MAX_DISCOVERED: int = 500
    _MAX_KEYWORDS: int = 5
    _MAX_RESULTS: int = 3
    _MAX_TASK_PREVIEW: int = 120
    _MAX_DESC_PREVIEW: int = 200

    # Common stop words to filter from keyword extraction
    _STOP_WORDS: set[str] = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our",
        "their", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "or", "and", "not", "but", "so", "if", "as", "than",
        "that", "this", "what", "which", "who", "how", "when", "where",
        "can", "could", "will", "would", "should", "may", "might",
        "do", "does", "did", "get", "got", "has", "have", "had",
    }

    def __init__(self) -> None:
        self._discovered: dict[str, ToolDiscovery] = {}  # task_key → discovery
        self._total_searches: int = 0
        self._total_discovered: int = 0
        self._last_search_time: float = 0.0
        self._generated_code_cache: dict[str, str] = {}

    # ── Keyword extraction ─────────────────────────────────────────

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from a task description.

        Splits on non-alpha characters, lowercases, removes stop words,
        and deduplicates while preserving order. Returns up to MAX_KEYWORDS.

        Args:
            text: The raw task description.

        Returns:
            Ordered list of unique, meaningful keywords.
        """
        words = re.findall(r"[a-zA-Z]+", text.lower())
        seen: set[str] = set()
        keywords: list[str] = []
        for w in words:
            if w not in self._STOP_WORDS and w not in seen:
                keywords.append(w)
                seen.add(w)
                if len(keywords) >= self._MAX_KEYWORDS:
                    break
        return keywords

    # ── Score / rank results ───────────────────────────────────────

    @staticmethod
    def _score_result(api_entry: Any, keywords: list[str]) -> float:
        """Score an API entry against search keywords.

        Higher score = better match. Scoring factors:
          - Exact name match: +10 per keyword match
          - Description contains keyword: +3 per match
          - Category contains keyword: +1 per match
          - Name length bonus (shorter names are more specific): +0.5 max

        Returns a float score.
        """
        score = 0.0

        name_lower = getattr(api_entry, "name", "").lower()
        desc_lower = getattr(api_entry, "description", "").lower()
        cat_lower = getattr(api_entry, "category", "").lower()

        for kw in keywords:
            if kw in name_lower:
                score += 10.0
            if kw in desc_lower:
                score += 3.0
            if kw in cat_lower:
                score += 1.0

        # Bonus for short, specific names
        if name_lower and len(name_lower) < 20:
            score += 0.5

        return score

    # ── Core: discover tool ────────────────────────────────────────

    async def discover_tool(
        self,
        task_description: str,
        consciousness: Any = None,
    ) -> dict | None:
        """Discover an external tool/API for a given task description.

        Searches PublicAPIs by extracted keywords, ranks results, and
        optionally generates calling code via the consciousness LLM.

        Args:
            task_description: Natural language description of the task.
            consciousness: Optional LLM consciousness for code generation.

        Returns:
            {
                "found": bool,
                "info": {api_name, api_url, auth, description, category},
                "code": str | None,
                "score": float,
            }
            or None if no APIs match.
        """
        self._total_searches += 1
        self._last_search_time = time.time()

        task_key = task_description[:self._MAX_TASK_PREVIEW]

        # ── Check cache first ──
        if task_key in self._discovered:
            logger.debug(f"ZeroShotToolDiscovery: cache hit for '{task_key[:40]}...'")
            cached = self._discovered[task_key]
            return {
                "found": True,
                "info": cached.to_dict(),
                "code": self._generated_code_cache.get(cached.api_name, ""),
                "score": cached.rank_score,
                "cached": True,
            }

        # ── Extract keywords ──
        keywords = self._extract_keywords(task_description)
        if not keywords:
            logger.debug("ZeroShotToolDiscovery: no meaningful keywords extracted")
            return None

        logger.debug(f"ZeroShotToolDiscovery: keywords={keywords}")

        # ── Load PublicAPIs resource ──
        try:
            from .public_apis_resource import get_public_apis
        except ImportError:
            logger.warning("ZeroShotToolDiscovery: public_apis_resource not available")
            return None

        try:
            pa = get_public_apis()
            await pa._ensure_loaded()
        except Exception as e:
            logger.warning(f"ZeroShotToolDiscovery: failed to load PublicAPIs — {e}")
            return None

        # ── Search by each keyword, collect + rank results ──
        all_results: list[tuple[Any, float]] = []
        seen_names: set[str] = set()

        for kw in keywords:
            try:
                hits = pa.search(kw)
                if hits:
                    for entry in hits:
                        name = getattr(entry, "name", "")
                        if name and name not in seen_names:
                            score = self._score_result(entry, keywords)
                            all_results.append((entry, score))
                            seen_names.add(name)
            except Exception:
                logger.debug(f"ZeroShotToolDiscovery: search failed for keyword '{kw}'")
                continue

        if not all_results:
            logger.debug(f"ZeroShotToolDiscovery: no API matches for {keywords}")
            return None

        # ── Sort by score descending, take top N ──
        all_results.sort(key=lambda x: x[1], reverse=True)
        top = all_results[:self._MAX_RESULTS]

        # Use the best match
        best_entry, best_score = top[0]

        discovery = ToolDiscovery(
            api_name=getattr(best_entry, "name", "unknown"),
            api_url=getattr(best_entry, "url", ""),
            auth=getattr(best_entry, "auth", ""),
            description=getattr(best_entry, "description", "")[:self._MAX_DESC_PREVIEW],
            category=getattr(best_entry, "category", ""),
            keywords=keywords,
            rank_score=best_score,
        )

        self._discovered[task_key] = discovery
        self._total_discovered += 1

        # ── Optionally generate calling code ──
        generated_code = ""
        if consciousness:
            try:
                code_prompt = (
                    f"Write a Python async function to call the API '{discovery.api_name}' "
                    f"at URL '{discovery.api_url}'. "
                    f"Auth: {discovery.auth}. "
                    f"Description: {discovery.description}. "
                    f"Use aiohttp. Return JSON. Include error handling."
                )
                raw_code = await consciousness.chain_of_thought(code_prompt)
                if isinstance(raw_code, str):
                    # Extract code block if present
                    code_text = raw_code.strip()
                    if "```python" in code_text:
                        parts = code_text.split("```python", 1)
                        if len(parts) > 1:
                            inner = parts[1].split("```", 1)
                            code_text = inner[0].strip() if inner else code_text
                    elif "```" in code_text:
                        parts = code_text.split("```", 1)
                        if len(parts) > 1:
                            inner = parts[1].split("```", 1)
                            code_text = inner[0].strip() if inner else code_text
                    generated_code = code_text[:2000]
                    self._generated_code_cache[discovery.api_name] = generated_code
                    logger.info(
                        f"ZeroShotToolDiscovery: generated code for "
                        f"'{discovery.api_name}' ({len(generated_code)} chars)"
                    )
            except Exception:
                logger.debug(
                    f"ZeroShotToolDiscovery: code generation failed for "
                    f"'{discovery.api_name}'"
                )

        logger.info(
            f"ZeroShotToolDiscovery: discovered '{discovery.api_name}' "
            f"(score={best_score:.2f}, category={discovery.category})"
        )

        result: dict = {
            "found": True,
            "info": discovery.to_dict(),
            "score": best_score,
            "cached": False,
        }
        if generated_code:
            result["code"] = generated_code
        return result

    # ── Batch discovery ────────────────────────────────────────────

    async def discover_tools(
        self,
        task_descriptions: list[str],
        consciousness: Any = None,
    ) -> list[dict]:
        """Discover tools for multiple task descriptions at once.

        Args:
            task_descriptions: List of task description strings.
            consciousness: Optional LLM consciousness.

        Returns:
            List of result dicts (None entries skipped).
        """
        results: list[dict] = []
        for task in task_descriptions:
            result = await self.discover_tool(task, consciousness=consciousness)
            if result:
                results.append(result)
        return results

    # ── Access discovered tools ────────────────────────────────────

    def get_discovered(self) -> dict[str, dict]:
        """Return all discovered tools as {task_key: discovery_dict}."""
        return {
            task_key: disc.to_dict()
            for task_key, disc in self._discovered.items()
        }

    def get_generated_code(self, api_name: str) -> str:
        """Retrieve generated calling code for a discovered API."""
        return self._generated_code_cache.get(api_name, "")

    def list_discovered_names(self) -> list[str]:
        """Return sorted list of discovered API names."""
        return sorted({d.api_name for d in self._discovered.values()})

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return summary statistics for zero-shot tool discovery."""
        return {
            "total_searches": self._total_searches,
            "total_discovered": self._total_discovered,
            "discovery_rate": (
                self._total_discovered / max(self._total_searches, 1)
            ),
            "unique_apis": len(self.list_discovered_names()),
            "api_names": self.list_discovered_names(),
            "codes_generated": len(self._generated_code_cache),
            "last_search_time": self._last_search_time,
        }


# ═══ Singleton ═══

_zero_shot_tools: ZeroShotToolDiscovery | None = None


def get_zero_shot_tools() -> ZeroShotToolDiscovery:
    """Get or create the global ZeroShotToolDiscovery singleton."""
    global _zero_shot_tools
    if _zero_shot_tools is None:
        _zero_shot_tools = ZeroShotToolDiscovery()
        logger.info("ZeroShotToolDiscovery singleton initialized")
    return _zero_shot_tools


__all__ = [
    "ToolDiscovery",
    "ZeroShotToolDiscovery",
    "get_zero_shot_tools",
]
