"""Multi-source material collector with rate limiting and robots.txt support.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
import urllib.parse
import time
from typing import Any, Dict, List, Optional

from loguru import logger


class MaterialCollector:
    def __init__(self, rate_limit_per_sec: int = 2) -> None:
        self._sema = asyncio.Semaphore(rate_limit_per_sec)

    def _is_allowed_by_robots(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            with urllib.request.urlopen(robots_url, timeout=5) as resp:
                content = resp.read().decode("utf-8").lower()
            # Very naive check: if robots.txt blocks all agents, deny
            if "disallow: /" in content:
                return False
            return True
        except Exception:
            # If robots.txt cannot be fetched, be permissive by default
            return True

    async def collect_from_web(self, query: str) -> List[Dict[str, Any]]:
        async with self._sema:
            # Interpret query as a URL for robots.txt evaluation
            if isinstance(query, str) and (query.startswith("http://") or query.startswith("https://")):
                if not self._is_allowed_by_robots(query):
                    logger.info("Blocked by robots.txt for url: {}", query)
                    return []
            await asyncio.sleep(0.1)  # simulate latency
            return [{"source": "web", "query": query, "content": f"stub content for {query}"}]

    async def collect_from_files(self, paths: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for p in paths:
            try:
                if os.path.isdir(p):
                    continue
                with open(p, "rb") as f:
                    content = f.read()
                results.append({"source": "file", "path": p, "size": len(content)})
            except Exception:
                continue
        return results

    async def collect_from_forms(self, form_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.05)
        return [{"source": "form", "schema": form_schema, "data": {}}]

    async def collect_from_api(self, url: str) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        def _fetch():
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    return resp.read().decode("utf-8")
            except Exception:
                return ""
        content = await loop.run_in_executor(None, _fetch)
        return [{"source": "api", "url": url, "content": content}]

    async def aggregate_materials(self, *data_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Flatten and return a combined set
        materials: List[Dict[str, Any]] = []
        for ds in data_sources:
            materials.extend(ds)
        return materials

    def extract_key_info(self, materials: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Simple extraction: collect keys present in materials
        keys = set()
        for m in materials:
            keys.update(m.keys())
        return {"keys": list(keys), "count": len(materials)}
