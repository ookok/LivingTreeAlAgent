"""ContentGraph — Cross-document consistency engine for long-form content.

Analogy: CodeGraph tracks function signatures across files → ContentGraph tracks
entities (characters, locations, events, claims) across documents.

Real-time consistency checking for:
  1. Novel writing — characters, plot, settings, timeline
  2. Multi-chapter reports — claims, data points, references
  3. Multi-file documentation — API names, version numbers, examples
  4. Any VFS-mounted content — auto-scans on file change

VFS-integrated spell correction:
  - Learns from /ram/corrections.txt user-defined typo fixes
  - Persists learned corrections to /disk/.livingtree/spell_dict.json
  - Auto-applies known corrections before any text generation

Architecture:
  VFS files → EntityExtractor → ContentGraph → ConsistencyChecker → Issues
       ↓                                                           ↓
  SpellCorrectionDB ← User fixes ←───────────── SpellChecker.learn()

Usage:
    graph = ContentGraph()
    graph.index_vfs("/disk/novel/", vfs=get_virtual_fs())
    issues = graph.check_consistency("character:张三")
    # → [{file: "ch1.md", property: "eye_color", old: "blue", new: "brown"}]
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════

@dataclass
class ContentEntity:
    """A tracked entity across documents (character, location, event, claim)."""
    id: str
    name: str
    category: str           # character | location | event | claim | object | term
    properties: dict[str, Any] = field(default_factory=dict)
    occurrences: list[EntityOccurrence] = field(default_factory=list)
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class EntityOccurrence:
    """A single occurrence of an entity in a document."""
    file: str
    line: int
    context: str            # Surrounding text
    properties_snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class ConsistencyIssue:
    """A detected cross-document consistency problem."""
    entity: str
    property_name: str
    files: list[str]
    values: list[Any]        # Conflicting values across files
    severity: str            # error | warning | info
    description: str
    suggestion: str


@dataclass
class SpellCorrection:
    """A learned spell correction."""
    wrong: str
    correct: str
    source: str              # "user" | "vfs" | "auto"
    file: str = ""
    count: int = 1
    timestamp: float = 0.0


# ═══ Entity Extractor ══════════════════════════════════════════════

class EntityExtractor:
    """Extract named entities and their properties from text.

    Supports both Chinese and English entity recognition.
    """

    # Chinese name patterns (姓氏+名)
    CN_NAME_RE = re.compile(
        r'(?:[张王李赵刘陈杨黄周吴徐孙马胡朱郭何罗高林]'
        r'[\u4e00-\u9fff]{1,2})'
    )
    # Property patterns: "XXX的YYY是ZZZ"
    CN_PROPERTY_RE = re.compile(
        r'([\u4e00-\u9fff]{1,4})的([\u4e00-\u9fff]{1,4})(?:是|为|：|:)'
        r'\s*([\u4e00-\u9fff\d]+)'
    )
    # Location patterns
    CN_LOCATION_RE = re.compile(
        r'(?:在|位于|于)([\u4e00-\u9fff]{2,8}(?:市|县|镇|村|区|路|街|楼|室|层|号))'
    )
    # Time patterns
    CN_TIME_RE = re.compile(
        r'(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日|第[一二三四五六七八九十]+章)'
    )
    # Numeric claim patterns
    CLAIM_RE = re.compile(
        r'([\u4e00-\u9fff]{2,10})\s*(?:为|是|达到|约|大约|共|合计)'
        r'\s*([\d.]+)\s*(mg|μg|dB|km|m|t|万|亿|元|%|℃|个|家|人)'
    )

    @classmethod
    def extract(cls, text: str, filepath: str = "",
                line_offset: int = 0) -> dict[str, ContentEntity]:
        """Extract all entities and their properties from text."""
        entities: dict[str, ContentEntity] = {}
        lines = text.split('\n')
        now = time.time()

        def _add_entity(name: str, category: str, props: dict, line_num: int, context: str):
            key = f"{category}:{name}"
            if key not in entities:
                entities[key] = ContentEntity(
                    id=key, name=name, category=category,
                    properties=props, first_seen=now, last_seen=now,
                )
            e = entities[key]
            e.last_seen = now
            e.properties.update(props)
            e.occurrences.append(EntityOccurrence(
                file=filepath, line=line_num + line_offset,
                context=context[:200],
                properties_snapshot=dict(props),
                timestamp=now,
            ))
            return e

        for i, line in enumerate(lines, 1):
            # Characters (Chinese names)
            for m in cls.CN_NAME_RE.finditer(line):
                name = m.group()
                _add_entity(name, "character", {}, i, line)

            # Properties
            for m in cls.CN_PROPERTY_RE.finditer(line):
                owner = m.group(1)
                prop = m.group(2)
                value = m.group(3)
                key = f"character:{owner}"
                if key in entities:
                    entities[key].properties[prop] = value
                else:
                    _add_entity(owner, "character", {prop: value}, i, line)

            # Locations
            for m in cls.CN_LOCATION_RE.finditer(line):
                loc = m.group(1)
                _add_entity(loc, "location", {}, i, line)

            # Timeline events
            for m in cls.CN_TIME_RE.finditer(line):
                time_str = m.group()
                _add_entity(time_str, "event", {"time": time_str}, i, line)

            # Claims (numeric)
            for m in cls.CLAIM_RE.finditer(line):
                subject = m.group(1)
                value = float(m.group(2))
                unit = m.group(3)
                _add_entity(subject, "claim",
                          {"value": value, "unit": unit}, i, line)

        return entities


# ═══ Content Graph ═════════════════════════════════════════════════

class ContentGraph:
    """Cross-document entity graph with consistency tracking.

    Like CodeGraph for code, but for content entities across documents.
    """

    def __init__(self):
        self._entities: dict[str, ContentEntity] = {}
        self._file_index: dict[str, list[str]] = defaultdict(list)  # file → entity_ids
        self._file_hashes: dict[str, str] = {}
        self._corrections: list[SpellCorrection] = []
        self._corrections_file = Path(".livingtree/spell_dict.json")
        self._load_corrections()

    # ── Indexing ──────────────────────────────────────────────────

    async def index_vfs(self, mount_path: str, vfs=None,
                        pattern: str = "*.md") -> int:
        """Index all documents in a VFS mount path."""
        if not vfs:
            try:
                from ..capability.virtual_fs import get_virtual_fs
                vfs = get_virtual_fs()
            except Exception:
                return 0

        count = 0
        try:
            entries = await vfs.list_dir(mount_path)
        except Exception:
            return 0

        for entry in entries:
            if entry.is_dir:
                continue
            if not entry.name.endswith(tuple(pattern.replace("*", "").split("|"))):
                continue
            try:
                content = await vfs.read_file(entry.path)
                file_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            except Exception:
                continue

            # Skip if unchanged
            if self._file_hashes.get(entry.path) == file_hash:
                continue

            self._file_hashes[entry.path] = file_hash
            entities = EntityExtractor.extract(content, entry.path)
            self._merge_entities(entities, entry.path)
            count += 1

        return count

    def index_file(self, filepath: str, content: str = "") -> int:
        """Index a single file."""
        if not content and Path(filepath).exists():
            content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        if not content:
            return 0

        file_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        if self._file_hashes.get(filepath) == file_hash:
            return 0

        self._file_hashes[filepath] = file_hash
        entities = EntityExtractor.extract(content, filepath)
        self._merge_entities(entities, filepath)
        return len(entities)

    def _merge_entities(self, new_entities: dict, filepath: str):
        """Merge newly extracted entities into the graph."""
        for key, new_entity in new_entities.items():
            if key in self._entities:
                existing = self._entities[key]
                existing.last_seen = new_entity.last_seen
                existing.properties.update(new_entity.properties)
                existing.occurrences.extend(new_entity.occurrences)
            else:
                self._entities[key] = new_entity
            self._file_index[filepath].append(key)

    # ── Consistency Checking ──────────────────────────────────────

    def check_entity(self, entity_name: str,
                     category: str = "character") -> list[ConsistencyIssue]:
        """Check a single entity for cross-document consistency."""
        key = f"{category}:{entity_name}"
        entity = self._entities.get(key)
        if not entity or len(entity.occurrences) < 2:
            return []

        issues = []
        # Check each property for value changes across files
        prop_values: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for occ in entity.occurrences:
            for prop, val in occ.properties_snapshot.items():
                prop_values[prop][str(val)].append(occ.file)

        for prop, value_files in prop_values.items():
            if len(value_files) > 1:
                values = list(value_files.keys())
                files_per_value = {v: list(set(fs)) for v, fs in value_files.items()}
                issues.append(ConsistencyIssue(
                    entity=entity_name,
                    property_name=prop,
                    files=[f for fs in value_files.values() for f in fs],
                    values=values,
                    severity="warning",
                    description=f"{entity_name}的'{prop}'在不同文档中不一致",
                    suggestion=f"统一为其中一个值: {values}",
                ))

        return issues

    def check_all(self) -> list[ConsistencyIssue]:
        """Check all entities for cross-document consistency."""
        all_issues = []
        for key, entity in self._entities.items():
            if len(entity.occurrences) >= 2:
                issues = self.check_entity(entity.name, entity.category)
                all_issues.extend(issues)
        return sorted(all_issues, key=lambda i: -len(i.files))

    def check_timeline(self) -> list[ConsistencyIssue]:
        """Check chronological consistency of events."""
        events = [(e.name, occ.file, occ.line, occ.properties_snapshot.get("time", ""))
                  for e in self._entities.values()
                  if e.category == "event"
                  for occ in e.occurrences]
        issues = []

        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                name_i, file_i, line_i, time_i = events[i]
                name_j, file_j, line_j, time_j = events[j]
                if time_i and time_j and time_i != time_j:
                    # Simple: same event referenced with different times
                    if name_i == name_j:
                        issues.append(ConsistencyIssue(
                            entity=name_i, property_name="time",
                            files=[file_i, file_j],
                            values=[time_i, time_j],
                            severity="error",
                            description=f"时间矛盾: {name_i} 在 {file_i} 是 {time_i}，在 {file_j} 是 {time_j}",
                            suggestion="核实时间线",
                        ))

        return issues

    # ── Real-time Watch ───────────────────────────────────────────

    async def watch_vfs(self, mount_path: str, vfs=None,
                        callback: callable = None,
                        interval: float = 5.0):
        """Watch VFS for file changes and auto-reindex."""
        while True:
            await asyncio.sleep(interval)
            try:
                changed = await self.index_vfs(mount_path, vfs)
                if changed > 0:
                    issues = self.check_all()
                    if callback and issues:
                        await callback(issues) if asyncio.iscoroutinefunction(callback) else callback(issues)
            except Exception:
                pass

    # ── Spell Correction Learning ─────────────────────────────────

    def learn_correction(self, wrong: str, correct: str,
                         source: str = "user", file: str = ""):
        """Learn a spell correction (from user feedback or VFS records)."""
        # Check if already known
        for c in self._corrections:
            if c.wrong == wrong:
                c.correct = correct
                c.count += 1
                c.timestamp = time.time()
                self._save_corrections()
                return

        self._corrections.append(SpellCorrection(
            wrong=wrong, correct=correct, source=source,
            file=file, timestamp=time.time(),
        ))
        self._save_corrections()

    def load_corrections_from_vfs(self, vfs_path: str = "/ram/corrections.txt",
                                  vfs=None):
        """Load spell corrections from a VFS file.

        Format: wrong → correct (one per line)
        Example: 错别子 → 错别字
        """
        try:
            if not vfs:
                from ..capability.virtual_fs import get_virtual_fs
                vfs = get_virtual_fs()
            content = asyncio.run(vfs.read_file(vfs_path))
        except Exception:
            # Try local file
            local = Path(vfs_path.lstrip("/"))
            if local.exists():
                content = local.read_text(encoding="utf-8")
            else:
                return 0

        count = 0
        for line in content.split('\n'):
            line = line.strip()
            if '→' in line:
                wrong, correct = line.split('→', 1)
                self.learn_correction(wrong.strip(), correct.strip(), "vfs", vfs_path)
                count += 1
            elif '->' in line:
                wrong, correct = line.split('->', 1)
                self.learn_correction(wrong.strip(), correct.strip(), "vfs", vfs_path)
                count += 1

        return count

    def apply_corrections(self, text: str) -> str:
        """Apply all learned corrections to text."""
        result = text
        for c in sorted(self._corrections, key=lambda c: -len(c.wrong)):
            if c.wrong in result:
                result = result.replace(c.wrong, c.correct)
        return result

    def _load_corrections(self):
        try:
            if self._corrections_file.exists():
                data = json.loads(self._corrections_file.read_text())
                self._corrections = [SpellCorrection(**c) for c in data]
        except Exception:
            pass

    def _save_corrections(self):
        try:
            self._corrections_file.parent.mkdir(parents=True, exist_ok=True)
            data = [{"wrong": c.wrong, "correct": c.correct,
                    "source": c.source, "file": c.file,
                    "count": c.count, "timestamp": c.timestamp}
                    for c in self._corrections]
            self._corrections_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def correction_count(self) -> int:
        return len(self._corrections)

    @property
    def stats(self) -> dict:
        return {
            "entities": len(self._entities),
            "files": len(self._file_index),
            "corrections": len(self._corrections),
            "by_category": {
                cat: sum(1 for e in self._entities.values() if e.category == cat)
                for cat in set(e.category for e in self._entities.values())
            },
        }


# ═══ Singleton ════════════════════════════════════════════════════

_content_graph: Optional[ContentGraph] = None


def get_content_graph() -> ContentGraph:
    global _content_graph
    if _content_graph is None:
        _content_graph = ContentGraph()
    return _content_graph


__all__ = [
    "ContentGraph", "ContentEntity", "EntityOccurrence",
    "ConsistencyIssue", "SpellCorrection", "EntityExtractor",
    "get_content_graph",
]
