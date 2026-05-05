"""ContentDedup — scan project for duplicate code/text blocks, suggest consolidation.

    1. Fingerprint-based: rolling hash for N-gram blocks
    2. Cross-file dedup: identical blocks across files → suggest consolidation
    3. Near-duplicate detection: fuzzy similarity (edit distance)
    4. LLM consolidator: propose unified version of near-duplicates
    5. Interactive remove: /dedup → list → /dedup apply → merges

    Usage:
        dedup = get_dedup()
        report = await dedup.scan(".", min_lines=5, hub=hub)
        # report.duplicates = [{files, lines, similarity, suggestion}]
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class DupBlock:
    hash: str
    content: str
    files: list[str] = field(default_factory=list)
    lines: list[tuple[int, int]] = field(default_factory=list)
    similarity: float = 1.0


@dataclass  
class DedupReport:
    path: Path
    scanned_files: int = 0
    scanned_blocks: int = 0
    duplicate_groups: list[DupBlock] = field(default_factory=list)
    near_duplicate_groups: list[DupBlock] = field(default_factory=list)
    estimated_lines_saved: int = 0
    suggestion: str = ""


class ContentDedup:
    """Duplicate content scanner with fingerprinting and LLM consolidation."""

    SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", "dist", "build", ".tox", ".mypy_cache"}
    SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".png", ".jpg", ".zip", ".7z"}
    CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h",
                 ".css", ".html", ".md", ".yaml", ".yml", ".toml", ".json", ".sh", ".bat"}

    def __init__(self, min_lines: int = 5, min_chars: int = 80):
        self.min_lines = min_lines
        self.min_chars = min_chars

    async def scan(
        self,
        root: str | Path = ".",
        include_pattern: str | None = None,
        min_lines: int | None = None,
        hub=None,
    ) -> DedupReport:
        """Scan project for duplicate code blocks.

        Args:
            root: Project root directory
            include_pattern: Only scan files matching glob (e.g. "*.py")
            min_lines: Minimum block size to consider (default 5)
            hub: LLM access for near-duplicate consolidation suggestions
        """
        root = Path(root)
        min_l = min_lines or self.min_lines
        report = DedupReport(path=root)

        # Collect all text blocks
        blocks_map: dict[str, list[tuple[str, int, int, str]]] = {}  # hash → [(file, start, end, content)]

        for fpath in self._iter_files(root, include_pattern):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                if len(lines) < min_l:
                    continue
                report.scanned_files += 1
                self._extract_blocks(fpath, lines, min_l, blocks_map)
            except Exception:
                continue

        # Find exact duplicates
        for blk_hash, entries in blocks_map.items():
            if len(entries) >= 2:
                sample = entries[0]
                block = DupBlock(
                    hash=blk_hash[:12],
                    content=sample[3],
                    files=[e[0] for e in entries],
                    lines=[(e[1], e[2]) for e in entries],
                    similarity=1.0,
                )
                report.duplicate_groups.append(block)
                report.scanned_blocks += 1

        # Near-duplicate detection (fuzzy)
        if hub and hub.world and len(report.duplicate_groups) > 1:
            report.near_duplicate_groups = await self._find_near_dupes(
                report.duplicate_groups, hub
            )

        # Estimate savings
        report.estimated_lines_saved = sum(
            (len(d.files) - 1) * (d.lines[0][1] - d.lines[0][0] + 1)
            for d in report.duplicate_groups
        )
        if report.estimated_lines_saved > 0:
            report.suggestion = (
                f"Found {len(report.duplicate_groups)} duplicate groups "
                f"across {report.scanned_files} files. "
                f"Consolidating could save ~{report.estimated_lines_saved} lines."
            )

        return report

    def _iter_files(self, root: Path, pattern: str | None):
        for fpath in root.rglob("*"):
            if any(part in self.SKIP_DIRS for part in fpath.parts):
                continue
            if fpath.suffix in self.SKIP_EXTS:
                continue
            if pattern and not fpath.match(pattern):
                continue
            if fpath.stat().st_size > 500_000:  # skip >500KB files
                continue
            yield fpath

    def _extract_blocks(
        self,
        filepath: str,
        lines: list[str],
        min_lines: int,
        blocks_map: dict,
    ):
        """Sliding window N-gram extraction with content hash."""
        for start in range(len(lines) - min_lines + 1):
            end = start + min_lines
            block_text = "".join(lines[start:end]).strip()
            if len(block_text) < self.min_chars:
                continue
            # Content hash (normalize whitespace but keep structure)
            normalized = re.sub(r'\s+', ' ', block_text).strip()
            h = hashlib.sha256(normalized[:2000].encode()).hexdigest()
            blocks_map.setdefault(h, []).append((filepath, start + 1, end, normalized))

    async def _find_near_dupes(
        self,
        groups: list[DupBlock],
        hub,
    ) -> list[DupBlock]:
        """LLM-based fuzzy duplicate detection."""
        if len(groups) < 2:
            return []

        # Build a list of block snippets for comparison
        snippets = []
        for i, g in enumerate(groups[:20]):  # max 20 for LLM
            snippets.append(f"[{i}] {g.content[:300]}")

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "I have these code snippets extracted as duplicate candidates. "
                    "Some may be near-duplicates (similar but not identical). "
                    "Identify which pairs/groups are near-duplicates and could be consolidated.\n\n"
                    "SNIPPETS:\n" + "\n---\n".join(snippets) + "\n\n"
                    "Output JSON: [{\"pair\": [idx1, idx2], \"reason\": \"why similar\", "
                    "\"can_merge\": true/false, \"merged_version\": \"unified version\"}]"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=800, timeout=20,
            )
            if result and result.text:
                m = re.search(r'\[[\s\S]*\]', result.text)
                if m:
                    import json
                    dupes = json.loads(m.group())
                    near_groups = []
                    for d in dupes:
                        if d.get("can_merge"):
                            i1, i2 = d["pair"]
                            if i1 < len(groups) and i2 < len(groups):
                                g = DupBlock(
                                    hash=f"near_{i1}_{i2}",
                                    content=d.get("merged_version", ""),
                                    files=groups[i1].files + groups[i2].files,
                                    lines=groups[i1].lines + groups[i2].lines,
                                    similarity=0.85,
                                )
                                near_groups.append(g)
                    return near_groups
        except Exception as e:
            logger.debug(f"Near-dupe detection: {e}")
        return []


_dedup: ContentDedup | None = None


def get_dedup() -> ContentDedup:
    global _dedup
    if _dedup is None:
        _dedup = ContentDedup()
    return _dedup
