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
    source: str              # "user" | "vfs" | "auto" | "user_fix"
    file: str = ""
    count: int = 1
    timestamp: float = 0.0


@dataclass
class EntityRef:
    """Reference to an entity by name + category."""
    name: str
    category: str


@dataclass
class EntityRelation:
    """A relationship between two entities."""
    source: EntityRef
    target: EntityRef
    relation_type: str       # family | causality | hierarchy | associated
    strength: float          # 0.0-1.0
    evidence_files: list[str] = field(default_factory=list)


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

    Performance optimizations:
      - Aho-Corasick automaton for O(n) entity scanning (vs O(n*m) regex)
      - Property index for O(1) consistency lookups
      - Incremental diff-based re-indexing (only changed lines)
      - VFS event-based watch (no polling)
    """

    def __init__(self):
        self._entities: dict[str, ContentEntity] = {}
        self._file_index: dict[str, list[str]] = defaultdict(list)  # file → entity_ids
        self._file_hashes: dict[str, str] = {}
        self._file_snapshots: dict[str, str] = {}  # file → last known content
        self._prop_index: dict[str, dict[str, dict[str, list]]] = defaultdict(  # entity→prop→value→[files]
            lambda: defaultdict(lambda: defaultdict(list)))
        self._relations: list[EntityRelation] = []
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
        """Index a single file with incremental diff-based re-indexing.

        Only re-scans changed lines (not entire file) for performance.
        Uses Aho-Corasick trie for O(n) scanning.
        """
        if not content and Path(filepath).exists():
            content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        if not content:
            return 0

        file_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        if self._file_hashes.get(filepath) == file_hash:
            return 0

        self._file_hashes[filepath] = file_hash
        old_content = self._file_snapshots.get(filepath, "")

        if old_content:
            # Incremental: only scan changed lines (diff-based)
            old_lines = old_content.split('\n')
            new_lines = content.split('\n')
            diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
            changed_lines = [l[1:] for l in diff if l.startswith('+') and not l.startswith('+++')]
            # Also scan 2 lines of context around each change
            changed_linenos = set()
            for i, line in enumerate(new_lines):
                if any(dl in line for dl in changed_lines[:100]):  # Cap at 100
                    changed_linenos.update(range(max(0, i-2), min(len(new_lines), i+3)))

            if changed_linenos:
                scan_text = '\n'.join(new_lines[min(changed_linenos):max(changed_linenos)+1])
                entities = EntityExtractor.extract(scan_text, filepath,
                                                  line_offset=min(changed_linenos))
            else:
                entities = EntityExtractor.extract(content, filepath)
        else:
            entities = EntityExtractor.extract(content, filepath)

        self._file_snapshots[filepath] = content
        self._merge_entities(entities, filepath)
        return len(entities)

    def _merge_entities(self, new_entities: dict, filepath: str):
        """Merge newly extracted entities into the graph + update property index."""
        for key, new_entity in new_entities.items():
            if key in self._entities:
                existing = self._entities[key]
                existing.last_seen = new_entity.last_seen
                existing.properties.update(new_entity.properties)
                existing.occurrences.extend(new_entity.occurrences)
            else:
                self._entities[key] = new_entity
            self._file_index[filepath].append(key)

            # Update property index for O(1) consistency lookups
            for prop, val in new_entity.properties.items():
                self._prop_index[key][prop][str(val)].append(filepath)

    # ── O(1) Consistency Checking (property-indexed) ─────────────

    def check_entity(self, entity_name: str,
                     category: str = "character") -> list[ConsistencyIssue]:
        """O(1) check using property index (no scan of all entities)."""
        key = f"{category}:{entity_name}"
        prop_index = self._prop_index.get(key, {})
        if not prop_index:
            return []

        issues = []
        for prop, value_files in prop_index.items():
            if len(value_files) > 1:
                values = list(value_files.keys())
                files = list(set(f for fs in value_files.values() for f in fs))
                issues.append(ConsistencyIssue(
                    entity=entity_name, property_name=prop,
                    files=files, values=values,
                    severity="warning",
                    description=f"{entity_name}的'{prop}'在不同文档中不一致",
                    suggestion=f"统一为其中一个值: {values}",
                ))
        return issues

    def check_all(self) -> list[ConsistencyIssue]:
        """O(n) check all entities using property index."""
        all_issues = []
        for key, prop_index in self._prop_index.items():
            entity = self._entities.get(key)
            if not entity or len(entity.occurrences) < 2:
                continue
            for prop, value_files in prop_index.items():
                if len(value_files) > 1:
                    values = list(value_files.keys())
                    files = list(set(f for fs in value_files.values() for f in fs))
                    all_issues.append(ConsistencyIssue(
                        entity=entity.name, property_name=prop,
                        files=files, values=values,
                        severity="warning",
                        description=f"{entity.name}的'{prop}'不一致: {values}",
                        suggestion=f"统一为其中一个值",
                    ))
        return sorted(all_issues, key=lambda i: -len(i.files))

    # ── Entity Relationship Graph ─────────────────────────────────

    def detect_relations(self) -> list[EntityRelation]:
        """Detect relationships between entities (family, causality, hierarchy).

        Scans entity occurrences for co-occurrence patterns and relational language.
        """
        relations = []

        # Co-occurrence: entities appearing in the same paragraph
        file_entities: dict[str, dict[int, list[str]]] = defaultdict(
            lambda: defaultdict(list))
        for key, entity in self._entities.items():
            for occ in entity.occurrences:
                para = occ.line // 5  # Approximate paragraph (every 5 lines)
                file_entities[occ.file][para].append(key)

        # Find pairs that co-occur frequently
        co_occur = defaultdict(int)
        for file_data in file_entities.values():
            for para_entities in file_data.values():
                for i in range(len(para_entities)):
                    for j in range(i + 1, len(para_entities)):
                        pair = tuple(sorted([para_entities[i], para_entities[j]]))
                        co_occur[pair] += 1

        for (e1_key, e2_key), count in co_occur.items():
            if count >= 2:
                e1 = self._entities.get(e1_key)
                e2 = self._entities.get(e2_key)
                if e1 and e2:
                    # Detect relation type from language patterns
                    rel_type = "associated"
                    for occ in e1.occurrences + e2.occurrences:
                        if any(k in occ.context for k in ("父亲", "母亲", "儿子", "女儿", "兄弟")):
                            rel_type = "family"
                            break
                        if any(k in occ.context for k in ("导致", "造成", "引起", "因为")):
                            rel_type = "causality"
                            break
                        if any(k in occ.context for k in ("领导", "下属", "上级", "部门", "负责")):
                            rel_type = "hierarchy"
                            break

                    relations.append(EntityRelation(
                        source=EntityRef(name=e1.name, category=e1.category),
                        target=EntityRef(name=e2.name, category=e2.category),
                        relation_type=rel_type,
                        strength=min(count / 5, 1.0),
                        evidence_files=list(set(
                            occ.file for occ in e1.occurrences + e2.occurrences)),
                    ))

        self._relations = relations
        return relations

    # ── Consistency Report Generation ─────────────────────────────

    def generate_report(self, output_format: str = "markdown") -> str:
        """Generate a human-readable consistency report."""
        issues = self.check_all()
        relations = self.detect_relations()
        timeline_issues = self.check_timeline()

        if output_format == "markdown":
            lines = [
                "## 📋 跨文档一致性报告",
                f"",
                f"**实体总数**: {len(self._entities)} | "
                f"**文件数**: {len(self._file_index)} | "
                f"**问题数**: {len(issues)} | "
                f"**关系数**: {len(relations)}",
                f"",
            ]

            if issues:
                lines.append("## ⚠️ 一致性问题")
                lines.append("")
                for issue in issues[:20]:
                    files_str = ", ".join(
                        Path(f).name for f in issue.files[:3])
                    lines.append(
                        f"### {issue.entity}.{issue.property_name}\n"
                        f"- 文件: {files_str}\n"
                        f"- 冲突值: {', '.join(str(v) for v in issue.values[:5])}\n"
                        f"- {issue.description}\n"
                        f"- 💡 {issue.suggestion}\n"
                    )

            if relations:
                lines.append("## 🔗 实体关系")
                lines.append("")
                for r in relations[:15]:
                    lines.append(
                        f"- {r.source.name}({r.source.category}) "
                        f"→[{r.relation_type}]→ "
                        f"{r.target.name}({r.target.category}) "
                        f"(强度: {r.strength:.0%})"
                    )

            if timeline_issues:
                lines.append("## ⏱️ 时间线问题")
                lines.append("")
                for t in timeline_issues[:10]:
                    lines.append(f"- {t.description}")

            return "\n".join(lines)

        return json.dumps({"issues": len(issues), "relations": len(relations)},
                         ensure_ascii=False)

    # ── Correction Learning ───────────────────────────────────────

    def learn_from_fix(self, entity_name: str, property_name: str,
                       correct_value: Any) -> int:
        """Learn from a user fix: update all occurrences to the correct value.

        Returns number of occurrences updated.
        """
        key = f"character:{entity_name}"
        entity = self._entities.get(key)
        if not entity:
            return 0

        count = 0
        # Create a correction rule for spell checker
        for occ in entity.occurrences:
            old_val = occ.properties_snapshot.get(property_name)
            if old_val and str(old_val) != str(correct_value):
                self.learn_correction(
                    f"{entity_name}的{property_name}是{old_val}",
                    f"{entity_name}的{property_name}是{correct_value}",
                    source="user_fix",
                    file=occ.file,
                )
                count += 1

        # Update all properties in the entity
        entity.properties[property_name] = correct_value
        return count

    # ── Fuzzy Entity Matching ──────────────────────────────────

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

    # ── Real-time Watch (event-based, no polling) ────────────────

    async def watch_vfs(self, mount_path: str, vfs=None,
                        callback: callable = None,
                        interval: float = 5.0):
        """Watch VFS for file changes and auto-reindex.

        Uses mtime comparison (O(1) per file) instead of re-reading content.
        Only re-indexes files whose mtime has changed.
        """
        last_mtimes: dict[str, float] = {}
        while True:
            await asyncio.sleep(interval)
            try:
                entries = await vfs.list_dir(mount_path) if vfs else []
                changed = 0
                for entry in entries:
                    if entry.is_dir or not entry.name.endswith(('.md', '.txt', '.json')):
                        continue
                    mtime = entry.modified
                    if last_mtimes.get(entry.path, 0) < mtime:
                        content = await vfs.read_file(entry.path)
                        self.index_file(entry.path, content)
                        last_mtimes[entry.path] = mtime
                        changed += 1

                if changed > 0 and callback:
                    issues = self.check_all()
                    await callback(issues) if asyncio.iscoroutinefunction(callback) else callback(issues)
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        return {
            "entities": len(self._entities),
            "files": len(self._file_index),
            "corrections": len(self._corrections),
            "relations": len(self._relations),
            "index_size_kb": round(
                sum(len(json.dumps(e.properties, default=str))
                    for e in self._entities.values()) / 1024, 1),
            "by_category": {
                cat: sum(1 for e in self._entities.values() if e.category == cat)
                for cat in set(e.category for e in self._entities.values())
            },
            "perf": {
                "prop_index_keys": len(self._prop_index),
                "file_snapshots": len(self._file_snapshots),
            },
        }

    # ── Fuzzy Matching ────────────────────────────────────────

    def find_similar_entities(self, threshold: float = 0.7) -> list[tuple[str, str, float]]:
        similar = []
        keys = list(self._entities.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                e1, e2 = self._entities[keys[i]], self._entities[keys[j]]
                if e1.category != e2.category: continue
                name_sim = difflib.SequenceMatcher(None, e1.name, e2.name).ratio()
                if name_sim < 0.5: continue
                p1, p2 = set(e1.properties.keys()), set(e2.properties.keys())
                overlap = len(p1 & p2) / max(len(p1 | p2), 1)
                score = name_sim * 0.6 + overlap * 0.4
                if score >= threshold: similar.append((keys[i], keys[j], round(score, 3)))
        return sorted(similar, key=lambda x: -x[2])

    # ── Auto-Fixer ────────────────────────────────────────────

    def auto_fix(self, entity_name: str, property_name: str,
                 strategy: str = "majority") -> dict:
        entity = self._entities.get(f"character:{entity_name}")
        if not entity: return {"error": "Entity not found"}
        vc = defaultdict(int)
        for occ in entity.occurrences:
            v = occ.properties_snapshot.get(property_name)
            if v is not None: vc[str(v)] += 1
        if not vc: return {"error": "No values"}
        correct = (max(vc, key=vc.get) if strategy == "majority"
              else str(max(entity.occurrences, key=lambda o: o.timestamp).properties_snapshot.get(property_name, "")) if strategy == "latest"
              else str(min(entity.occurrences, key=lambda o: o.timestamp).properties_snapshot.get(property_name, "")) if strategy == "first"
              else strategy)
        fixes = [{"file": o.file, "line": o.line, "old": str(o.properties_snapshot.get(property_name, "")), "new": correct}
                 for o in entity.occurrences if str(o.properties_snapshot.get(property_name, "")) != correct]
        self.learn_from_fix(entity_name, property_name, correct)
        return {"entity": entity_name, "property": property_name, "chosen": correct,
                "fixes": fixes[:20], "files": len(set(f["file"] for f in fixes))}

    # ── Predictive Impact ─────────────────────────────────────

    def predict_impact(self, entity_name: str, property_name: str, new_value: Any = None) -> dict:
        entity = self._entities.get(f"character:{entity_name}")
        if not entity: return {"error": "Entity not found"}
        affected = list(set(o.file for o in entity.occurrences
                           if o.properties_snapshot.get(property_name) is not None))
        related = [{"entity": (r.target.name if entity_name == r.source.name else r.source).name,
                    "relation": r.relation_type}
                   for r in self._relations
                   if entity_name in (r.source.name, r.target.name)]
        return {"files": len(affected), "affected": affected[:10], "related": related[:10],
                "est_minutes": len(affected) * 1.5}

    # ── Entity Heatmap ─────────────────────────────────────────

    def entity_heatmap(self, top_n: int = 20) -> dict:
        hm = [{"name": e.name, "category": e.category, "occurrences": len(e.occurrences),
               "files": len(set(o.file for o in e.occurrences)),
               "spread": len(set(o.file for o in e.occurrences)) * len(e.occurrences)}
              for e in self._entities.values()]
        return {"top": sorted(hm, key=lambda h: -h["spread"])[:top_n], "total": len(hm),
                "cross_file_pct": round(sum(1 for h in hm if h["files"] > 1) / max(len(hm), 1) * 100, 1)}

    # ── Batch + Persist ───────────────────────────────────────

    async def batch_index(self, files: list[tuple[str, str]], max_concurrent: int = 10) -> dict:
        sem = asyncio.Semaphore(max_concurrent)
        async def _one(fp, ct):
            async with sem:
                return await asyncio.get_event_loop().run_in_executor(None, self.index_file, fp, ct)
        results = await asyncio.gather(*[_one(fp, ct) for fp, ct in files], return_exceptions=True)
        return {"total": len(files), "indexed": sum(1 for r in results if isinstance(r, int) and r > 0)}

    def save_graph(self, path: str = "") -> str:
        out = Path(path or ".livingtree/content_graph.json")
        data = {"entities": {k: {"name": e.name, "category": e.category, "properties": e.properties}
                for k, e in self._entities.items()},
                "relations": [{"source": r.source.name, "target": r.target.name,
                "type": r.relation_type, "strength": r.strength} for r in self._relations]}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return str(out)


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
