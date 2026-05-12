"""PublicAPIsResource — on-demand virtual filesystem for the public-apis directory.

Mounts the public-apis GitHub repository (300K+ stars, 1400+ free APIs in 50+
categories) as a read-only VirtualFS-compatible resource at /public-apis.

Usage:
    from livingtree.capability.public_apis_resource import get_public_apis

    pa = get_public_apis()
    cats = await pa.list_dir("/")           # all categories as directories
    apis = await pa.list_dir("/weather")    # APIs in weather category
    text = await pa.read_file("/weather")   # formatted table of weather APIs
    hits = pa.search("free")               # search all APIs
    stats = pa.stats()                     # cache stats
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from loguru import logger

from .virtual_fs import Resource, VFSEntry


# ══════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════

@dataclass
class APIEntry:
    """A single public API entry parsed from the README table."""
    name: str
    description: str
    auth: str
    https: bool
    cors: str
    url: str
    category: str


# ══════════════════════════════════════════════════════════════════════
# PublicAPIsResource
# ══════════════════════════════════════════════════════════════════════

class PublicAPIsResource(Resource):
    """On-demand virtual filesystem resource backed by the public-apis README.

    Fetches the README.md from GitHub raw on first access, parses markdown
    tables into APIEntry objects organized by category, and keeps everything
    in memory. Never writes to disk. Auto-refreshes after 1 hour TTL.
    """

    _SOURCE_URL = (
        "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
    )

    @property
    def name(self) -> str:
        return "public-apis"

    def __init__(self) -> None:
        self._cache: dict[str, list[APIEntry]] | None = None
        self._raw_md: str | None = None
        self._cache_ttl: float = 3600.0
        self._last_fetch: float = 0.0

    # ── Core: fetch + parse ──────────────────────────────────────────

    async def _ensure_loaded(self) -> None:
        now = time.time()
        if self._cache is not None and (now - self._last_fetch) < self._cache_ttl:
            return

        logger.info("PublicAPIsResource: fetching README.md from GitHub raw ...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._SOURCE_URL,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            f"PublicAPIsResource: HTTP {resp.status} fetching README"
                        )
                        self._init_empty()
                        return
                    self._raw_md = await resp.text()
        except Exception as e:
            logger.warning(f"PublicAPIsResource: fetch failed: {e}")
            self._init_empty()
            return

        if not self._raw_md:
            self._init_empty()
            return

        try:
            self._cache = self._parse_markdown(self._raw_md)
            self._last_fetch = time.time()
            total = sum(len(v) for v in self._cache.values())
            logger.info(
                f"PublicAPIsResource: parsed {total} APIs in "
                f"{len(self._cache)} categories"
            )
        except Exception as e:
            logger.warning(f"PublicAPIsResource: parse failed: {e}")
            self._init_empty()

        self._raw_md = None

    def _init_empty(self) -> None:
        self._cache = {}
        self._raw_md = None
        self._last_fetch = time.time()

    # ── Markdown parser ──────────────────────────────────────────────

    _INDEX_RE = re.compile(r"##\s+Index\b")
    _INDEX_ITEM_RE = re.compile(r"^\*\s+\[([^\]]+)\]\(#[^)]+\)")
    _H3_RE = re.compile(r"^###\s+(.+)$")
    _TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|[\s:|-]+\|[\s:|-]+\|[\s:|-]+\|[\s:|-]+\|$")
    _TABLE_ROW_RE = re.compile(
        r"^\|\s*(?:\[([^\]]+)\]\(([^)]+)\)|([^|]+?))\s*\|\s*([^|]*?)\s*\|"
        r"\s*(`[^`]*`|[^|]*?)\s*\|\s*(Yes|No)\s*\|\s*(Yes|No|Unknown)\s*\|"
    )
    _BACK_LINK = "**[⬆ Back to Index]"

    @staticmethod
    def _parse_markdown(md: str) -> dict[str, list[APIEntry]]:
        lines = md.split("\n")
        cache: dict[str, list[APIEntry]] = {}

        # --- Step 1: extract category names from ## Index section ---
        categories: list[tuple[str, str]] = []
        in_index = False
        for line in lines:
            if PublicAPIsResource._INDEX_RE.match(line):
                in_index = True
                continue
            if in_index:
                m = PublicAPIsResource._INDEX_ITEM_RE.match(line)
                if m:
                    cat_name = m.group(1).strip()
                    cat_slug = re.sub(r"[^a-z0-9]+", "-", cat_name.lower()).strip("-")
                    categories.append((cat_slug, cat_name))
                elif line.startswith("<br") or line.strip() == "":
                    continue
                elif not line.startswith("*"):
                    in_index = False

        # --- Step 2: for each category, find its ### heading + table ---
        parsed_cats: set[str] = set()
        current_cat: str = ""

        i = 0
        while i < len(lines):
            line = lines[i]
            h3 = PublicAPIsResource._H3_RE.match(line)
            if h3:
                cat_raw = h3.group(1).strip()
                cat_slug = (
                    re.sub(r"[^a-z0-9]+", "-", cat_raw.lower()).strip("-")
                )
                current_cat = ""

                for cslug, cname in categories:
                    if cslug == cat_slug:
                        current_cat = cname
                        break
                if not current_cat:
                    current_cat = cat_raw

                i += 1
                # skip content until we find a table separator
                while i < len(lines):
                    nxt = lines[i]
                    if current_cat and PublicAPIsResource._TABLE_SEP_RE.match(nxt):
                        i += 1
                        break
                    if PublicAPIsResource._H3_RE.match(nxt):
                        i -= 1
                        break
                    if nxt.startswith(PublicAPIsResource._BACK_LINK):
                        break
                    i += 1

                # parse table rows until back-link or next heading
                entries: list[APIEntry] = []
                while i < len(lines):
                    row = lines[i]
                    if row.startswith(PublicAPIsResource._BACK_LINK):
                        break
                    if PublicAPIsResource._H3_RE.match(row):
                        break
                    if row.strip() == "":
                        i += 1
                        continue
                    rm = PublicAPIsResource._TABLE_ROW_RE.match(row)
                    if rm:
                        name = (rm.group(1) or rm.group(3) or "").strip()
                        url_val = (rm.group(2) or "").strip()
                        if not url_val and rm.group(3):
                            url_val = ""
                        desc = rm.group(4).strip()
                        auth = rm.group(5).strip().strip("`")
                        https_val = rm.group(6).strip() == "Yes"
                        cors_val = rm.group(7).strip() if rm.group(7) else "Unknown"

                        if name:
                            entries.append(APIEntry(
                                name=name,
                                description=desc,
                                auth=auth,
                                https=https_val,
                                cors=cors_val,
                                url=url_val,
                                category=current_cat,
                            ))
                        i += 1
                        continue

                    # non-matching row — check if it's a table row with no link
                    # (some rows have plain-text name without markdown link)
                    stripped = row.strip()
                    if stripped.startswith("|") and not PublicAPIsResource._TABLE_SEP_RE.match(row):
                        fallback = PublicAPIsResource._parse_fallback_row(row)
                        if fallback:
                            fallback.category = current_cat
                            entries.append(fallback)
                    i += 1

                if current_cat and entries:
                    cache[current_cat] = entries
                    parsed_cats.add(current_cat)
                elif current_cat:
                    cache[current_cat] = []
                    parsed_cats.add(current_cat)
            i += 1

        # Step 3: add any categories from Index that weren't parsed
        for _slug, cname in categories:
            if cname not in parsed_cats:
                cache[cname] = []

        return cache

    _FALLBACK_RE = re.compile(
        r"^\|\s*(.+?)\s*\|\s*([^|]*?)\s*\|\s*(`[^`]*`|[^|]*?)\s*\|\s*(Yes|No)\s*\|\s*(Yes|No|Unknown)\s*\|"
    )

    @staticmethod
    def _parse_fallback_row(row: str) -> APIEntry | None:
        m = PublicAPIsResource._FALLBACK_RE.match(row.strip())
        if not m:
            return None
        name_raw = m.group(1).strip()
        desc = m.group(2).strip()
        auth = m.group(3).strip().strip("`")
        https_val = m.group(4).strip() == "Yes"
        cors_val = m.group(5).strip() if m.group(5) else "Unknown"
        if not name_raw:
            return None
        return APIEntry(
            name=name_raw,
            description=desc,
            auth=auth,
            https=https_val,
            cors=cors_val,
            url="",
            category="",
        )

    _SLUG_MAP: dict[str, str] = {}

    def _resolve_category(self, name_or_slug: str) -> str | None:
        if not self._cache:
            return None
        lower = name_or_slug.strip().lower()
        for cname in self._cache:
            if cname.lower() == lower:
                return cname
            slug = re.sub(r"[^a-z0-9]+", "-", cname.lower()).strip("-")
            if slug == lower:
                return cname
        return None

    # ── Resource interface ───────────────────────────────────────────

    async def list_dir(self, path: str) -> list[VFSEntry]:
        """List entries at a virtual path.

        "/"          → list all categories as directories
        "/category"  → list all APIs in that category as files
        """
        await self._ensure_loaded()
        if self._cache is None:
            return []

        norm = path.replace("\\", "/").strip("/") or "/"

        if norm == "/":
            now = time.time()
            return [
                VFSEntry(
                    name=cat,
                    path=f"/{cat}",
                    is_dir=True,
                    size=len(entries),
                    modified=now,
                    resource_type="public-apis",
                )
                for cat, entries in sorted(self._cache.items())
            ]

        cat = self._resolve_category(norm)
        if cat is None:
            return []

        now = time.time()
        entries = self._cache.get(cat, [])
        return [
            VFSEntry(
                name=entry.name,
                path=f"/{cat}/{entry.name}",
                is_dir=False,
                size=len(entry.description.encode("utf-8")),
                modified=now,
                resource_type="public-apis",
                metadata={
                    "auth": entry.auth,
                    "https": entry.https,
                    "cors": entry.cors,
                    "url": entry.url,
                },
            )
            for entry in entries
        ]

    async def read_file(self, path: str) -> str:
        """Read a virtual file.

        "/category"         → formatted table of all APIs in that category
        "/category/api_name" → single API detail block
        """
        await self._ensure_loaded()
        if self._cache is None:
            raise FileNotFoundError(f"public-apis: cache not loaded")

        norm = path.replace("\\", "/").strip("/")

        parts = norm.split("/") if norm else []
        if len(parts) == 1:
            cat = self._resolve_category(parts[0])
            if cat is None:
                raise FileNotFoundError(f"public-apis: category '{parts[0]}' not found")
            entries = self._cache.get(cat, [])
            return self._format_category_table(cat, entries)

        if len(parts) >= 2:
            cat = self._resolve_category(parts[0])
            if cat is None:
                raise FileNotFoundError(f"public-apis: category '{parts[0]}' not found")
            api_name = "/".join(parts[1:])
            for entry in self._cache.get(cat, []):
                if entry.name.lower() == api_name.lower():
                    return self._format_api_detail(entry)
            raise FileNotFoundError(
                f"public-apis: API '{api_name}' not found in '{cat}'"
            )

        raise FileNotFoundError(f"public-apis: invalid path '{path}'")

    async def exists(self, path: str) -> bool:
        await self._ensure_loaded()
        if self._cache is None:
            return False
        norm = path.replace("\\", "/").strip("/") or "/"
        if norm == "/":
            return True
        parts = norm.split("/")
        cat = self._resolve_category(parts[0])
        if cat is None:
            return False
        if len(parts) == 1:
            return True
        api_name = "/".join(parts[1:])
        for entry in self._cache.get(cat, []):
            if entry.name.lower() == api_name.lower():
                return True
        return False

    # ── Formatting helpers ───────────────────────────────────────────

    @staticmethod
    def _format_category_table(category: str, entries: list[APIEntry]) -> str:
        if not entries:
            return f"# {category}\n\n(no APIs listed)\n"

        lines = [
            f"# {category}  ({len(entries)} APIs)",
            "",
            f"{'API':<35} {'Auth':<12} {'HTTPS':<7} {'Description'}",
            f"{'-' * 35} {'-' * 12} {'-' * 7} {'-' * 40}",
        ]
        for e in entries:
            name = e.name[:34]
            auth = e.auth[:11]
            https_s = "Yes" if e.https else "No"
            desc = e.description[:60]
            lines.append(f"{name:<35} {auth:<12} {https_s:<7} {desc}")
        return "\n".join(lines)

    @staticmethod
    def _format_api_detail(entry: APIEntry) -> str:
        return (
            f"Name:        {entry.name}\n"
            f"Category:    {entry.category}\n"
            f"Description: {entry.description}\n"
            f"Auth:        {entry.auth}\n"
            f"HTTPS:       {'Yes' if entry.https else 'No'}\n"
            f"CORS:        {entry.cors}\n"
            f"URL:         {entry.url or '(none)'}\n"
        )

    # ── Query methods ────────────────────────────────────────────────

    def search(self, query: str, category: str | None = None) -> list[APIEntry]:
        """Search APIs by name or description substring.

        Args:
            query: substring to search for (case-insensitive)
            category: optional category name to restrict search
        """
        if not self._cache:
            return []

        q = query.lower()
        results: list[APIEntry] = []

        cats = [category] if category else list(self._cache.keys())
        for cat in cats:
            resolved = self._resolve_category(cat)
            if resolved is None:
                continue
            for entry in self._cache.get(resolved, []):
                if q in entry.name.lower() or q in entry.description.lower():
                    results.append(entry)

        return results

    def get_categories(self) -> list[str]:
        """Return all available category names."""
        if not self._cache:
            return []
        return sorted(self._cache.keys())

    def stats(self) -> dict[str, Any]:
        """Return cache statistics: total APIs, categories, age, size."""
        if not self._cache:
            return {
                "total_apis": 0,
                "total_categories": 0,
                "cache_age_seconds": 0,
                "cache_size_bytes": 0,
                "loaded": False,
            }

        total_apis = sum(len(v) for v in self._cache.values())
        age = time.time() - self._last_fetch if self._last_fetch else 0

        cache_size = 0
        for entries in self._cache.values():
            for e in entries:
                cache_size += sum(
                    sys.getsizeof(getattr(e, f, ""))
                    for f in ("name", "description", "auth", "cors", "url", "category")
                )
                cache_size += sys.getsizeof(e.https)

        return {
            "total_apis": total_apis,
            "total_categories": len(self._cache),
            "cache_age_seconds": round(age, 1),
            "cache_size_bytes": cache_size,
            "loaded": True,
        }


# ══════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════

_pa: PublicAPIsResource | None = None


def get_public_apis() -> PublicAPIsResource:
    """Get or create the global PublicAPIsResource singleton."""
    global _pa
    if _pa is None:
        _pa = PublicAPIsResource()
        logger.info("PublicAPIsResource singleton created")
    return _pa


def reset_public_apis() -> None:
    """Reset the global PublicAPIsResource singleton."""
    global _pa
    _pa = None


__all__ = [
    "APIEntry",
    "PublicAPIsResource",
    "get_public_apis",
    "reset_public_apis",
]
