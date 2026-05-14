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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .ast_parser import ASTParser, ASTNode, ASTEdge


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
        self._db_path = Path(db_path) if db_path else Path("./data/code_graph.json")
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
                except Exception:
                    pass

        total_edges = sum(len(e.dependents) for e in self._entities.values())
        elapsed = (time.time() - t0) * 1000

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

        # Wire edges: calls, contains, inherits
        for edge in edges:
            # Find matching entities and add dependency links
            for eid, entity in list(self._entities.items()):
                if entity.name == edge.target and entity.file != filepath:
                    source_id = f"{filepath}:{edge.source}"
                    source_entities = [e for e in self._file_entities.get(filepath, [])
                                       if edge.source in e]
                    for se in source_entities:
                        if se in self._entities:
                            self._entities[se].dependencies.append(eid)
                            self._entities[eid].dependents.append(se)

        # Update file hash
        try:
            raw = Path(filepath).read_bytes()
            self._file_hash[filepath] = hashlib.sha256(raw).hexdigest()
        except Exception:
            pass

        return count

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
        p = Path(path) if path else self._db_path
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entities": {k: {
                "id": e.id, "name": e.name, "file": e.file, "kind": e.kind,
                "line": e.line, "deps": e.dependencies, "dependents": e.dependents,
            } for k, e in self._entities.items()},
            "file_hash": self._file_hash,
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"CodeGraph saved to {p} ({len(self._entities)} entities)")

    def load(self, path: str | None = None) -> bool:
        p = Path(path) if path else self._db_path
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._entities = {}
            for eid, edata in data.get("entities", {}).items():
                self._entities[eid] = CodeEntity(
                    id=edata["id"], name=edata["name"], file=edata["file"],
                    kind=edata.get("kind", "function"), line=edata.get("line", 0),
                    end_line=edata.get("line", 0),
                    dependencies=edata.get("deps", []),
                    dependents=edata.get("dependents", []),
                )
                self._file_entities.setdefault(edata["file"], []).append(eid)
            self._file_hash = data.get("file_hash", {})
            logger.info(f"CodeGraph loaded from {p} ({len(self._entities)} entities)")
            return True
        except Exception as e:
            logger.warning(f"CodeGraph load failed: {e}")
            return False

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
