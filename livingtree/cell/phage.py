"""Phage — Absorb code patterns from repositories using Tree-sitter AST.

Enhanced: structured pattern extraction via AST instead of text scanning.
Detects functions, classes, imports, and dependency patterns.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from loguru import logger

from ..capability.ast_parser import ASTParser
from .cell_ai import CellAI, CellCapability


class Phage:
    """Code absorption engine — extracts structured knowledge from source code.

    Uses Tree-sitter AST parsing to identify patterns:
    - Function signatures and implementations
    - Class hierarchies and methods
    - Import dependencies and module structure
    - Algorithmic patterns (loops, recursion, error handling)
    """

    def __init__(self):
        self._parser = ASTParser()

    async def scan_directory(self, path: str, patterns: list[str] | None = None) -> dict:
        """Scan a local directory and extract all code entities.

        Returns structured analysis: {files, functions, classes, imports, patterns}
        """
        root = Path(path)
        if not root.exists():
            return {"error": f"Path not found: {path}"}

        patterns = patterns or ["**/*.py", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs"]
        all_nodes: list[dict] = []
        all_edges: list[dict] = []
        file_count = 0

        for pat in patterns:
            for f in root.glob(pat):
                if f.name.startswith(".") or "__pycache__" in str(f):
                    continue
                file_count += 1
                nodes, edges = self._parser.parse_file(str(f))
                for n in nodes:
                    all_nodes.append({
                        "name": n.name, "kind": n.kind, "file": str(f.relative_to(root)),
                        "line": n.line, "parent": n.parent_name,
                    })
                for e in edges:
                    all_edges.append({
                        "source": e.source, "target": e.target, "kind": e.kind,
                    })

        functions = [n for n in all_nodes if n["kind"] == "function"]
        classes = [n for n in all_nodes if n["kind"] == "class"]
        imports = [n for n in all_nodes if n["kind"] == "import"]
        calls = [e for e in all_edges if e["kind"] == "calls"]

        logger.info(f"Phage scanned {path}: {file_count} files, {len(functions)} functions, {len(classes)} classes")

        return {
            "path": str(root),
            "files": file_count,
            "functions": len(functions),
            "classes": len(classes),
            "imports": len(imports),
            "call_edges": len(calls),
            "top_functions": self._rank_by_connections(all_nodes, all_edges, "function")[:10],
            "top_classes": self._rank_by_connections(all_nodes, all_edges, "class")[:5],
            "entry_points": self._find_entry_points(functions, all_edges),
        }

    async def scan_github(self, repo_url: str) -> dict:
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        try:
            parts = repo_url.rstrip("/").replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                api_url = f"https://api.github.com/repos/{parts[0]}/{parts[1]}"
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(api_url, headers={"User-Agent": "LivingTree/2.1"},
                                     timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {
                                "repo": repo_url, "name": repo_name,
                                "stars": data.get("stargazers_count", 0),
                                "language": data.get("language", ""),
                                "description": data.get("description", "")[:200],
                                "topics": data.get("topics", []),
                                "status": "analyzed",
                            }
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"GitHub scan: {e}")

        return {"repo": repo_url, "name": repo_name, "status": "scanned",
                "message": "Use scan_directory() for full local analysis"}

    async def extract_patterns(self, source: str, language: str = "python") -> list[dict]:
        """Extract code patterns from source string using AST.

        Detects: functions, classes, error handling, loops, imports.
        """
        nodes, edges = self._parser.parse_source(source, language)
        patterns: list[dict] = []
        for node in nodes:
            entry = {"name": node.name, "kind": node.kind, "line": node.line,
                     "code": node.code_snippet[:80]}
            patterns.append(entry)

        # Aggregate pattern types
        pattern_summary = {
            "total_entities": len(nodes),
            "function_count": sum(1 for n in nodes if n.kind == "function"),
            "class_count": sum(1 for n in nodes if n.kind == "class"),
            "import_count": sum(1 for n in nodes if n.kind == "import"),
            "entities": patterns[:20],
        }
        return [pattern_summary]

    async def inject_knowledge(self, cell: CellAI, patterns: list[dict]) -> int:
        """Inject extracted patterns as cell capabilities."""
        count = 0
        for pattern in patterns:
            entities = pattern.get("entities", [])
            for entity in entities:
                cap_name = f"{entity.get('kind', 'entity')}_{entity.get('name', 'unknown')[:30]}"
                cap_desc = f"Absorbed {entity.get('kind')} '{entity.get('name')}' ({entity.get('line')}L)"
                cell.capabilities.append(CellCapability(
                    name=cap_name,
                    description=cap_desc,
                    confidence=0.7,
                ))
                count += 1
            # Also record aggregate patterns
            for key in ["function_count", "class_count", "import_count"]:
                if key in pattern:
                    cell.capabilities.append(CellCapability(
                        name=f"codebase_{key}",
                        description=f"Codebase has {pattern[key]} {key.replace('_count', '')}s",
                        confidence=0.9,
                    ))

        cell.genome.add_mutation(
            f"Phage: absorbed {count} code entities from AST analysis",
            source="phage_ast",
        )
        logger.info(f"Injected {count} code entities into cell {cell.name}")
        return count

    async def absorb_codebase(self, cell: CellAI, repo_path: str) -> dict:
        """Absorb an entire codebase into a cell.

        Scans the directory, extracts patterns via AST, injects into cell.
        """
        logger.info(f"Absorbing codebase: {repo_path}")
        scan_result = await self.scan_directory(repo_path)
        if "error" in scan_result:
            return scan_result

        patterns = [{
            "entities": [],
            "function_count": scan_result["functions"],
            "class_count": scan_result["classes"],
            "import_count": scan_result["imports"],
            "call_edges": scan_result["call_edges"],
        }]

        count = await self.inject_knowledge(cell, patterns)
        return {
            "patterns_absorbed": count,
            "files_scanned": scan_result["files"],
            "functions_found": scan_result["functions"],
            "classes_found": scan_result["classes"],
            "call_graph_edges": scan_result["call_edges"],
            "entry_points": scan_result["entry_points"],
            "status": "completed",
        }

    # ── Helpers ──

    def _rank_by_connections(self, nodes: list[dict], edges: list[dict], kind: str) -> list[dict]:
        """Rank entities by connection count."""
        conn_count: dict[str, int] = {}
        for e in edges:
            conn_count[e["source"]] = conn_count.get(e["source"], 0) + 1
            conn_count[e["target"]] = conn_count.get(e["target"], 0) + 1
        ranked = []
        for n in nodes:
            if n["kind"] == kind:
                ranked.append({**n, "connections": conn_count.get(n["name"], 0)})
        ranked.sort(key=lambda x: x["connections"], reverse=True)
        return ranked

    def _find_entry_points(self, functions: list[dict], edges: list[dict]) -> list[str]:
        """Identify likely entry points: functions that are called but don't call others."""
        callers = set(e["source"] for e in edges if e["kind"] == "calls")
        callees = set(e["target"] for e in edges if e["kind"] == "calls")
        # Entry points: defined functions that call others but aren't called themselves
        entry_candidates = callers - callees
        return [e for e in entry_candidates if any(f["name"] == e for f in functions)][:5]
