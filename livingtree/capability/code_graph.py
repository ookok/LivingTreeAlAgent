"""CodeGraph — Persistent code-level knowledge graph.

Builds a structural map of a codebase: functions, classes, imports,
calls, inheritance, and test coverage. Provides blast-radius analysis
to determine the minimal set of files affected by any change.

Inspired by code-review-graph (14.9k ★).

Usage:
    cg = CodeGraph()
    cg.index("my_project/")
    impacted = cg.blast_radius("src/main.py")
    for f in impacted:
        print(f.file, f.reason, f.risk)
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from typing import Any, Optional

from loguru import logger

from .ast_parser import ASTParser, ASTNode, ASTEdge
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



@dataclass
class CodeEntity:
    """A resolved code entity in the graph."""
    id: str
    name: str
    file: str
    kind: str  # function, class, module, import
    line: int
    end_line: int
    parent_class: str = ""
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    test_coverage: bool = False
    complexity: int = 0
    hash: str = ""


@dataclass
class ImpactResult:
    """Result of blast-radius analysis for a changed file."""
    file: str
    reason: str  # directly_modified, caller, dependent, test, imported_by
    risk: str  # critical, high, medium, low
    affected_entities: list[str] = field(default_factory=list)
    distance: int = 0


@dataclass
class GraphStats:
    total_files: int = 0
    total_entities: int = 0
    total_edges: int = 0
    build_time_ms: float = 0
    languages: dict[str, int] = field(default_factory=dict)


class CodeGraph:
    """Incremental code knowledge graph with blast-radius analysis.

    - Build: parse entire codebase into entities + edges
    - Update: re-parse only changed files (hash-based detection)
    - Query: callers, callees, dependents, imports
    - Blast radius: minimal set of files affected by a change
    """

    def __init__(self, db_path: str = ""):
        self._entities: dict[str, CodeEntity] = {}
        self._file_hash: dict[str, str] = {}
        self._file_entities: dict[str, list[str]] = {}  # file -> entity IDs
        self._parser = ASTParser()
        self._db_path = Path(db_path) if db_path else Path("./data/code_graph.pickle")
        self._stats = GraphStats()

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def file_count(self) -> int:
        return len(self._file_entities)

    # ── Build / Index ──

    def index(self, root_path: str, patterns: list[str] | None = None) -> GraphStats:
        """Parse and index an entire codebase.

        Args:
            root_path: Root directory to scan
            patterns: File patterns (default: ["*.py", "*.js", "*.ts", "*.go", "*.rs"])

        Returns:
            GraphStats with build metrics
        """
        t0 = time.time()
        patterns = patterns or ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.go", "**/*.rs"]
        root = Path(root_path)
        if not root.exists():
            return self._stats

        files = []
        for pat in patterns:
            try:
                files.extend(root.glob(pat))
            except Exception:
                pass

        lang_counts: dict[str, int] = {}
        total_entities = 0

        # Concurrent parsing with ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed
        parse_tasks: list[tuple[str, str]] = []
        for filepath in files:
            if filepath.name.startswith(".") or "__pycache__" in str(filepath):
                continue
            sut = str(filepath)
            if self._is_changed(sut):
                parse_tasks.append((sut, filepath.suffix))

        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as pool:
            futures = {pool.submit(self._parser.parse_file, t[0]): t for t in parse_tasks}
            for future in as_completed(futures):
                sut, ext = futures[future]
                try:
                    nodes, edges = future.result()
                    self._update_file(sut, nodes, edges)
                    lang_counts[ext] = lang_counts.get(ext, 0) + 1
                    total_entities += len(nodes)
                except Exception as e:
                    if total_entities == 0 and lang_counts == {}:
                        logger.warning(f"CodeGraph parse failed for {sut}: {e}")

        total_edges = sum(len(e.dependents) for e in self._entities.values())
        elapsed = (time.time() - t0) * 1000

        # Build O(1) name index once after all files are loaded
        self._build_name_index()

        # Heuristic call detection (runs once, not per-file)
        self._detect_heuristic_calls_all()

        self._stats = GraphStats(
            total_files=len(files),
            total_entities=total_entities,
            total_edges=total_edges,
            build_time_ms=elapsed,
            languages=lang_counts,
        )
        logger.info(f"CodeGraph indexed: {total_entities} entities in {len(files)} files ({elapsed:.0f}ms)")
        return self._stats

    def update_file(self, filepath: str) -> int:
        """Incrementally update a single file. Returns number of new/changed entities."""
        nodes, edges = self._parser.parse_file(filepath)
        return self._update_file(filepath, nodes, edges)

    def _update_file(self, filepath: str, nodes: list[ASTNode], edges: list[ASTEdge]) -> int:
        """Internal: update entities for a single file."""
        # Remove old entities for this file
        old_ids = self._file_entities.get(filepath, [])
        for eid in old_ids:
            self._entities.pop(eid, None)
        self._file_entities[filepath] = []

        count = 0
        for node in nodes:
            eid = node.id
            entity = CodeEntity(
                id=eid,
                name=node.name,
                file=filepath,
                kind=node.kind,
                line=node.line,
                end_line=node.end_line,
                parent_class=node.parent_name,
                hash=self._compute_hash(node.code_snippet),
            )
            self._entities[eid] = entity
            self._file_entities.setdefault(filepath, []).append(eid)
            count += 1

        # Build import → qualified name map for this file
        import_map = self._build_import_map(filepath, nodes)

        # Wire edges: calls, contains, inherits (O(1) via name index)
        GENERIC_NAMES = {"get", "set", "run", "main", "init", "start", "stop",
                         "read", "write", "open", "close", "load", "save",
                         "create", "update", "delete", "list", "find", "search"}

        for edge in edges:
            if edge.target in GENERIC_NAMES:
                continue
            target_qualified = import_map.get(edge.target, edge.target)
            candidates = self._name_index.get(target_qualified, [])
            if not candidates:
                candidates = self._name_index.get(edge.target, [])

            source_id = f"{filepath}:{edge.source}"
            for se in self._file_entities.get(filepath, []):
                if edge.source in se and se in self._entities:
                    for target_id in candidates:
                        if target_id in self._entities and target_id != se:
                            if target_id not in self._entities[se].dependencies:
                                self._entities[se].dependencies.append(target_id)
                                self._entities[target_id].dependents.append(se)
                    # If no import-resolved match, try same-file call
                    if not candidates:
                        for eid in self._file_entities.get(filepath, []):
                            entity = self._entities.get(eid)
                            if entity and entity.name == edge.target and eid != se:
                                if eid not in self._entities[se].dependencies:
                                    self._entities[se].dependencies.append(eid)
                                    self._entities[eid].dependents.append(se)

        # Heuristic: detect string-based calls (e.g., bus.invoke("vfs:read"))
        self._detect_heuristic_calls(filepath)

        # Update file hash
        try:
            raw = Path(filepath).read_bytes()
            self._file_hash[filepath] = hashlib.sha256(raw).hexdigest()
        except Exception:
            pass

        return count

    def _build_name_index(self) -> None:
        """Build O(1) name → [entity_ids] index. Called once lazily."""
        if not hasattr(self, '_name_index') or len(self._name_index) < len(self._entities) * 0.5:
            self._name_index: dict[str, list[str]] = defaultdict(list)
            for eid, entity in self._entities.items():
                self._name_index[entity.name].append(eid)
                # Also index by qualified name: file_basename.funcname
                base = Path(entity.file).stem
                self._name_index[f"{base}.{entity.name}"].append(eid)

    @staticmethod
    def _build_import_map(filepath: str, nodes: list) -> dict[str, str]:
        """Build a map from short names to qualified names using AST import analysis."""
        import_map: dict[str, str] = {}
        try:
            import ast as py_ast
            source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            tree = py_ast.parse(source)
        except Exception:
            return import_map

        for node in py_ast.walk(tree):
            if isinstance(node, py_ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname or alias.name
                    import_map[name] = f"{module}.{alias.name}"
            elif isinstance(node, py_ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    import_map[name] = name

        return import_map

    def _detect_heuristic_calls_all(self) -> None:
        """Batch-detect string-based calls across all indexed files (runs once)."""
        for fpath in list(self._file_entities.keys())[:200]:  # Cap at 200 files
            try:
                source = Path(fpath).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            patterns = [
                (r'\.invoke\s*\(\s*["\']([^"\']+)["\']', "invoke"),
                (r'\.register\s*\(\s*["\']([^"\']+)["\']', "register"),
            ]
            for pattern, kind in patterns:
                for m in re.finditer(pattern, source):
                    target_name = m.group(1)
                    for eid in self._file_entities.get(fpath, []):
                        entity = self._entities.get(eid)
                        if entity:
                            for tid in self._name_index.get(target_name, []):
                                if tid in self._entities and tid != eid:
                                    if tid not in self._entities[eid].dependencies:
                                        self._entities[eid].dependencies.append(tid)
                                        self._entities[tid].dependents.append(eid)

    def _is_changed(self, filepath: str) -> bool:
        """Check if a file has changed since last index."""
        try:
            raw = Path(filepath).read_bytes()
            new_hash = hashlib.sha256(raw).hexdigest()
            old_hash = self._file_hash.get(filepath, "")
            return new_hash != old_hash
        except Exception:
            return True

    # ── Blast Radius ──

    def blast_radius(self, changed_files: list[str], max_depth: int = 3) -> list[ImpactResult]:
        """Compute the blast radius of changed files.

        Traces callers, dependents, and imports to determine
        which files are potentially affected by a change.
        """
        results: list[ImpactResult] = []
        visited: set[str] = set()

        def _traverse(filepath: str, reason: str, depth: int):
            if depth > max_depth or filepath in visited:
                return
            visited.add(filepath)

            entity_ids = self._file_entities.get(filepath, [])
            affected = [eid for eid in entity_ids if eid in self._entities]

            risk = "low"
            if any(e in self._entities and not self._entities[e].test_coverage for e in entity_ids):
                if depth == 0:
                    risk = "critical"
                elif depth == 1:
                    risk = "high"
                else:
                    risk = "medium"

            results.append(ImpactResult(
                file=filepath,
                reason=reason,
                risk=risk,
                affected_entities=affected,
                distance=depth,
            ))

            # Traverse callers and dependents
            for eid in entity_ids:
                entity = self._entities.get(eid)
                if not entity:
                    continue
                for dep_id in entity.dependents:
                    dep_entity = self._entities.get(dep_id)
                    if dep_entity:
                        _traverse(dep_entity.file, f"caller_of:{entity.name}", depth + 1)
                for dep_id in entity.dependencies:
                    dep_entity = self._entities.get(dep_id)
                    if dep_entity:
                        _traverse(dep_entity.file, f"called_by:{entity.name}", depth + 1)

        for f in changed_files:
            _traverse(f, "directly_modified", 0)

        return results

    def get_minimal_context(self, changed_files: list[str]) -> list[dict[str, Any]]:
        """Get the minimal file set needed for reviewing changes."""
        impacted = self.blast_radius(changed_files, max_depth=2)
        return [
            {
                "file": r.file,
                "reason": r.reason,
                "risk": r.risk,
                "entities": r.affected_entities[:10],
            }
            for r in sorted(impacted, key=lambda x: (x.distance, x.risk))
        ]

    # ── Queries ──

    def get_callers(self, function_name: str) -> list[CodeEntity]:
        return [e for e in self._entities.values()
                if function_name in e.dependencies and e.kind == "function"]

    def get_callees(self, function_name: str) -> list[str]:
        for eid, entity in self._entities.items():
            if entity.name == function_name:
                return entity.dependencies
        return []

    def get_dependents(self, filepath: str) -> list[str]:
        entity_ids = self._file_entities.get(filepath, [])
        deps: set[str] = set()
        for eid in entity_ids:
            e = self._entities.get(eid)
            if e:
                for dep_id in e.dependents:
                    dep = self._entities.get(dep_id)
                    if dep:
                        deps.add(dep.file)
        return list(deps)

    def search(self, query: str) -> list[CodeEntity]:
        q = query.lower()
        return [e for e in self._entities.values()
                if q in e.name.lower() or q in e.file.lower()]

    def find_uncovered(self) -> list[CodeEntity]:
        return [e for e in self._entities.values() if not e.test_coverage and e.kind == "function"]

    def find_hubs(self, top_n: int = 10) -> list[CodeEntity]:
        scored = [(e, len(e.dependents) + len(e.dependencies)) for e in self._entities.values()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:top_n]]

    def stats(self) -> GraphStats:
        self._stats.total_entities = len(self._entities)
        self._stats.total_edges = sum(len(e.dependents) for e in self._entities.values())
        self._stats.total_files = len(self._file_entities)
        return self._stats

    # ── Persistence ──

    def save(self, path: str | None = None) -> None:
        p = Path(path) if path else self._db_path.with_suffix(".pickle")
        p.parent.mkdir(parents=True, exist_ok=True)

        # Build integer ID mapping for compact storage
        id_to_int: dict[str, int] = {}
        int_to_id: list[str] = []
        entities_compact: dict[int, tuple] = {}
        for eid, entity in self._entities.items():
            if eid not in id_to_int:
                id_to_int[eid] = len(int_to_id)
                int_to_id.append(eid)
            ei = id_to_int[eid]
            for dep in entity.dependencies:
                if dep not in id_to_int:
                    id_to_int[dep] = len(int_to_id)
                    int_to_id.append(dep)
            for dep in entity.dependents:
                if dep not in id_to_int:
                    id_to_int[dep] = len(int_to_id)
                    int_to_id.append(dep)
        for eid, entity in self._entities.items():
            ei = id_to_int[eid]
            entities_compact[ei] = (
                entity.name, entity.file, entity.kind,
                entity.line, entity.end_line, entity.parent_class,
                entity.test_coverage, entity.complexity, entity.hash,
                tuple(id_to_int[d] for d in entity.dependencies),
                tuple(id_to_int[d] for d in entity.dependents),
            )

        state = {
            "v": 2,
            "id_map": int_to_id,
            "entities": entities_compact,
            "file_entities": {f: [id_to_int[eid] for eid in eids]
                            for f, eids in self._file_entities.items()},
            "file_hash": self._file_hash,
            "file_mtimes": {f: os.path.getmtime(f) if os.path.exists(f) else 0
                           for f in self._file_hash},
        }
        with open(p, "wb") as fh:
            pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)
        size_mb = p.stat().st_size / (1024 * 1024)
        logger.info(f"CodeGraph saved ({len(self._entities)} entities, {size_mb:.1f}MB)")

    def load(self, path: str | None = None) -> bool:
        p = Path(path) if path else self._db_path.with_suffix(".pickle")
        if not p.exists():
            return False
        try:
            with open(p, "rb") as fh:
                state = pickle.load(fh)

            if state.get("v", 1) >= 2:
                int_to_id: list[str] = state["id_map"]
                entities_c: dict[int, tuple] = state["entities"]
                self._entities = {}
                for ei, tup in entities_c.items():
                    self._entities[int_to_id[ei]] = CodeEntity(
                        id=int_to_id[ei], name=tup[0], file=tup[1], kind=tup[2],
                        line=tup[3], end_line=tup[4], parent_class=tup[5],
                        test_coverage=tup[6], complexity=tup[7], hash=tup[8],
                        dependencies=[int_to_id[d] for d in tup[9]],
                        dependents=[int_to_id[d] for d in tup[10]],
                    )
                self._file_entities = defaultdict(list, {
                    f: [int_to_id[ei] for ei in eis]
                    for f, eis in state.get("file_entities", {}).items()
                })
            else:
                # Legacy v1 format: entities as dicts
                for eid, edata in state.get("entities", {}).items():
                    self._entities[eid] = CodeEntity(
                        id=edata["id"], name=edata["name"], file=edata["file"],
                        kind=edata.get("kind", "function"), line=edata.get("line", 0),
                        end_line=edata.get("line", 0),
                        dependencies=edata.get("deps", []),
                        dependents=edata.get("dependents", []),
                    )
                self._file_entities = defaultdict(list, state.get("file_entities", {}))
            self._file_hash = state.get("file_hash", {})
            cached_mtimes = state.get("file_mtimes", {})

            # Check which files changed since last index
            changed = [f for f, ts in cached_mtimes.items()
                       if (not os.path.exists(f)) or (os.path.getmtime(f) != ts)]

            # Rebuild dependents from dependencies (ensure consistency)
            for eid, entity in self._entities.items():
                entity.dependents = []
            for eid, entity in self._entities.items():
                for dep_id in entity.dependencies:
                    if dep_id in self._entities:
                        self._entities[dep_id].dependents.append(eid)

            logger.info(
                f"CodeGraph loaded ({len(self._entities)} entities, "
                f"{len(changed)}/{len(cached_mtimes)} files changed)"
            )
            if changed and len(changed) < len(cached_mtimes) * 0.3:
                logger.info(f"CodeGraph: {len(changed)} files changed — incremental re-index")
                self._file_hash = {k: v for k, v in self._file_hash.items()
                                   if k not in changed}
                self._reindex_files(changed)
                self.save(str(p))  # Persist incremental update
            return True
        except Exception as e:
            logger.warning(f"CodeGraph load failed: {e}")
            return False

    def _reindex_files(self, files: list[str]) -> None:
        """Incrementally re-index changed files without rebuilding entire graph."""
        for fpath in files:
            if not os.path.exists(fpath) or not fpath.endswith(".py"):
                continue
            nodes, edges = self._parser.parse_file(fpath)
            if nodes:
                self._update_file(fpath, nodes, edges)
            content = Path(fpath).read_text(errors="replace")
            self._file_hash[fpath] = self._compute_hash(content)

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ═══ Entity-Level Incremental Tracking ═══

    def diff_entities(self, other: "CodeGraph") -> dict:
        """Compare two graph states. Returns {added, removed, modified} entities.

        Uses entity-level hashing (per function/class) instead of file-level.
        This is the core of "code-review-graph": precise change tracking.
        """
        added = []
        removed = []
        modified = []

        for eid, ent in self._entities.items():
            other_ent = other._entities.get(eid)
            if other_ent is None:
                removed.append({"id": eid, "name": ent.name, "file": ent.file,
                               "kind": ent.kind, "line": ent.line})
            elif ent.end_line != other_ent.end_line or ent.dependencies != other_ent.dependencies:
                modified.append({"id": eid, "name": ent.name, "file": ent.file,
                                "kind": ent.kind, "change": "signature_or_deps"})

        for eid, ent in other._entities.items():
            if eid not in self._entities:
                added.append({"id": eid, "name": ent.name, "file": ent.file,
                             "kind": ent.kind, "line": ent.line})

        return {"added": added, "removed": removed, "modified": modified,
                "total_changes": len(added) + len(removed) + len(modified)}

    def snapshot(self) -> dict:
        """Return a snapshot of the current graph state for comparison."""
        return {
            eid: {"name": ent.name, "file": ent.file, "kind": ent.kind,
                  "deps": sorted(ent.dependencies), "line": ent.line,
                  "end_line": ent.end_line}
            for eid, ent in self._entities.items()
        }

    def incremental_update_from_git(self, base_branch: str = "HEAD~1",
                                     current_branch: str = "HEAD") -> dict:
        """Detect changed files from git diff and only re-parse those.

        Uses `git diff --name-only` to find changed files, then
        re-parses only those files instead of the whole codebase.
        """
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_branch, current_branch],
                capture_output=True, text=True, timeout=10,
            )
            changed_files = [
                f.strip() for f in result.stdout.split("\n")
                if f.strip() and f.strip().endswith((".py", ".js", ".ts", ".go", ".rs"))
            ]
            if not changed_files:
                return {"changed_files": 0, "entities_updated": 0}

            # Only re-parse changed files
            updated = 0
            for filepath in changed_files:
                if Path(filepath).exists():
                    self.update_file(filepath)
                    updated += 1

            return {"changed_files": len(changed_files),
                    "entities_updated": updated}
        except Exception as e:
            logger.debug(f"CodeGraph git incremental: {e}")
            return {"changed_files": 0, "entities_updated": 0, "error": str(e)[:200]}

    def impact_score(self, changed_files: list[str], max_depth: int = 3) -> list[dict]:
        """Compute numeric impact scores (0-100) for blast radius results.

        Enhancement over binary blast_radius(): assigns risk scores based on:
        - Number of dependents (popularity)
        - Call depth (distance from change)
        - Test coverage (uncovered = higher risk)
        """
        results = self.blast_radius(changed_files, max_depth)
        scored = []
        for r in results:
            entity = self._entities.get(r.entity_id) if hasattr(r, 'entity_id') and r.entity_id else None
            deps_count = len(entity.dependencies) if entity else 0
            depth_penalty = max(30 - r.distance * 10, 0) if hasattr(r, 'distance') else 20
            coverage_penalty = 20 if entity and entity.test_coverage is False else 0
            score = min(100, 40 + deps_count * 5 + depth_penalty + coverage_penalty)

            scored.append({
                "file": r.file, "reason": r.reason,
                "risk": r.risk if hasattr(r, 'risk') else "unknown",
                "distance": r.distance if hasattr(r, 'distance') else 1,
                "impact_score": score,
                "affected_entities": r.affected_entities if hasattr(r, 'affected_entities') else [],
            })
        scored.sort(key=lambda x: -x["impact_score"])
        return scored

    def diff_export(self, base_snapshot: dict) -> dict:
        """Export changes since a previous snapshot as structured JSON.

        Perfect for MCP tools: AI assistants get precise, minimal context.
        """
        current = self.snapshot()
        added, removed, modified = [], [], []

        for eid, ent in current.items():
            if eid not in base_snapshot:
                added.append({"id": eid, **ent})
            elif ent != base_snapshot[eid]:
                modified.append({"id": eid, "before": base_snapshot[eid], "after": ent})

        for eid in base_snapshot:
            if eid not in current:
                removed.append({"id": eid, **base_snapshot[eid]})

        return {
            "snapshot_time": time.time(),
            "total_entities": len(current),
            "changes": {"added": len(added), "removed": len(removed), "modified": len(modified)},
            "added": added[:50], "removed": removed[:50], "modified": modified[:50],
        }
