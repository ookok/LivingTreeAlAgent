"""Code Learner — learn from a codebase like doc_learner learns from documents.

Same architecture as doc_learner.py, but for code:
  1. Scan folder → AST parse all .py files
  2. Build call graph + dependency graph (code_graph.py)
  3. Analyze architecture patterns
  4. Extract coding conventions + patterns
  5. Persist into 6-layer memory

Key difference from doc_learner:
  Documents = linear text with sections
  Code      = graph-structured with AST, imports, calls, inheritance, git history

Uses existing: code_graph.py, code_engine.py, ast_parser.py,
  practical_life.py, self_evolution.py, core_pipelines.py CodePipeline
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class CodeLearner:
    """Orchestrates existing code capabilities for learning from codebases."""

    async def learn_from_codebase(self, folder_path: str, hub=None) -> dict:
        """Point the lifeform at a codebase → it learns the entire code structure."""
        result = {"path": folder_path, "started_at": time.time()}
        folder = Path(folder_path)
        if not folder.exists():
            return {"error": f"Folder not found: {folder_path}"}

        # Step 1: Index code graph (AST parse all files)
        code_structure = await self._build_code_graph(folder)
        result["code_graph"] = code_structure

        # Step 2: Analyze architecture patterns
        architecture = await self._analyze_architecture(folder, code_structure)
        result["architecture"] = architecture

        # Step 3: Learn coding conventions
        conventions = await self._learn_conventions(folder, code_structure)
        result["conventions"] = conventions

        # Step 4: Git history analysis
        git_analysis = await self._analyze_git_history(folder)
        result["git_history"] = git_analysis

        # Step 5: Persist into 6-layer memory
        persisted = await self._persist_code_memory(
            folder, code_structure, architecture, conventions, git_analysis
        )
        result["persisted"] = persisted

        result["duration_ms"] = round((time.time() - result["started_at"]) * 1000)
        return result

    # ── Step 1: Build code graph ──

    async def _build_code_graph(self, folder: Path) -> dict:
        """Use code_graph.py to parse all files into AST entities."""
        try:
            from livingtree.capability.code_graph import CodeGraph
            cg = CodeGraph()
            cg.index(str(folder))
            stats = cg.get_stats()

            # Extract key insights
            return {
                "total_files": stats.total_files,
                "total_entities": stats.total_entities,
                "functions": stats.functions,
                "classes": stats.classes,
                "imports": stats.imports,
                "max_complexity": stats.max_complexity,
                "test_coverage_pct": round(
                    stats.covered_entities / max(1, stats.total_entities) * 100, 1
                ),
            }
        except Exception as e:
            logger.debug(f"CodeLearner: code_graph failed: {e}")
            # Fallback: simple scan
            return self._simple_scan(folder)

    def _simple_scan(self, folder: Path) -> dict:
        """Fallback scan if code_graph fails."""
        import re
        py_files = list(folder.rglob("*.py"))
        functions = 0
        classes = 0
        for f in py_files:
            try:
                content = f.read_text("utf-8")
                functions += len(re.findall(r'def (\w+)\(', content))
                classes += len(re.findall(r'class (\w+)', content))
            except Exception:
                pass
        return {
            "total_files": len(py_files),
            "functions": functions,
            "classes": classes,
        }

    # ── Step 2: Analyze architecture ──

    async def _analyze_architecture(self, folder: Path, code_structure: dict) -> dict:
        """Analyze architecture patterns from code structure."""
        # Detect architecture from folder structure
        top_dirs = [d.name for d in folder.iterdir() if d.is_dir() and not d.name.startswith(".")]

        # Detect patterns
        patterns = []
        if any("api" in d.lower() for d in top_dirs):
            patterns.append("REST API (api/ directory detected)")
        if any("models" in d.lower() for d in top_dirs):
            patterns.append("MVC/Model (models/ detected)")
        if any("services" in d.lower() for d in top_dirs):
            patterns.append("Service Layer (services/ detected)")
        if any("core" in d.lower() for d in top_dirs):
            patterns.append("Core Module (core/ detected)")
        if any("knowledge" in d.lower() for d in top_dirs):
            patterns.append("Knowledge Layer (knowledge/ detected)")

        return {
            "top_level_modules": top_dirs,
            "detected_patterns": patterns,
            "module_count": len(top_dirs),
        }

    # ── Step 3: Learn conventions ──

    async def _learn_conventions(self, folder: Path, code_structure: dict) -> dict:
        """Extract coding conventions from the codebase."""
        py_files = list(folder.rglob("*.py"))[:50]
        conventions = {}

        # Detect common imports
        import_counts = {}
        for f in py_files:
            try:
                for line in f.read_text("utf-8").split("\n")[:20]:
                    if line.startswith("import ") or line.startswith("from "):
                        pkg = line.split()[1].split(".")[0]
                        import_counts[pkg] = import_counts.get(pkg, 0) + 1
            except Exception:
                pass

        conventions["top_imports"] = sorted(
            import_counts.items(), key=lambda x: -x[1]
        )[:10]

        # Detect naming conventions
        conventions["naming"] = self._detect_naming(folder)

        return conventions

    def _detect_naming(self, folder: Path) -> dict:
        """Detect naming conventions (snake_case, CamelCase, etc.)."""
        import re
        snake = 0
        camel = 0
        for f in list(folder.rglob("*.py"))[:30]:
            try:
                funcs = re.findall(r'def (\w+)', f.read_text("utf-8"))
                for name in funcs:
                    if "_" in name:
                        snake += 1
                    elif name[0].isupper():
                        camel += 1
            except Exception:
                pass
        return {
            "functions_snake_case": snake,
            "functions_CamelCase": camel,
            "dominant_style": "snake_case" if snake > camel else "CamelCase",
        }

    # ── Step 4: Git history ──

    async def _analyze_git_history(self, folder: Path) -> dict:
        """Analyze git history for project evolution insights."""
        import subprocess
        try:
            from ..treellm.unified_exec import git as ue_git
            files_result = await ue_git("log --pretty=format: --name-only", timeout=10)
            files_out = files_result.stdout
            log_result = await ue_git("log --oneline -10", timeout=10)
            log_out = log_result.stdout

            files = [f for f in files_out.split("\n") if f.strip()]
            from collections import Counter
            top_files = Counter(files).most_common(10)

            return {
                "most_changed_files": [
                    {"file": f, "changes": c} for f, c in top_files
                ],
                "recent_commits": log_out.strip().split("\n")[:10],
            }
        except Exception:
            return {"note": "No git history available"}

    # ── Step 5: Persist into 6-layer memory ──

    async def _persist_code_memory(
        self, folder: Path, code_structure: dict, architecture: dict,
        conventions: dict, git_history: dict,
    ) -> dict:
        """Persist code knowledge into 6-layer memory."""
        result = {f"layer{i}": 0 for i in range(1, 7)}

        # L1: document_kb — chunk source files
        try:
            from ..knowledge.document_kb import DocumentKB
            kb = DocumentKB()
            count = 0
            for f in list(folder.rglob("*.py"))[:100]:
                try:
                    content = f.read_text("utf-8")
                    kb.add_document(str(f.relative_to(folder)), content)
                    count += 1
                except Exception:
                    pass
            result["layer1"] = count
        except Exception:
            pass

        # L2: engram — top-level module paths
        try:
            from ..knowledge.engram_store import get_engram_store
            engram = get_engram_store(seed=False)
            count = 0
            for module in architecture.get("top_level_modules", []):
                engram.insert(f"module:{module}", module, "code_module")
                count += 1
            result["layer2"] = count
        except Exception:
            pass

        # L3: knowledge_graph — module dependency edges
        try:
            from ..knowledge.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph()
            count = 0
            mods = architecture.get("top_level_modules", [])
            for i in range(len(mods) - 1):
                kg.add_edge(mods[i], mods[i+1], "architectural_layer")
                count += 1
            result["layer3"] = count
        except Exception:
            pass

        # L4: vector_store — module purpose embeddings
        try:
            from ..knowledge.vector_store import VectorStore
            vs = VectorStore()
            count = 0
            for module in architecture.get("top_level_modules", []):
                vs.add(f"Module {module}: source code", metadata={"module": module})
                count += 1
            result["layer4"] = count
        except Exception:
            pass

        # L5: struct_mem — architecture patterns
        try:
            from ..knowledge.struct_mem import get_struct_mem, EventEntry
            mem = get_struct_mem()
            for pattern in architecture.get("detected_patterns", []):
                entry = EventEntry(
                    id=f"arch_{hash(pattern) % 10000}",
                    session_id="code_learner",
                    role="system",
                    content=f"Architecture pattern: {pattern}",
                )
                mem._buffer.add(entry)
            result["layer5"] = len(architecture.get("detected_patterns", []))
        except Exception:
            pass

        # L6: capability_graph — detected patterns as capabilities
        try:
            from ..dna.capability_graph import get_capability_graph
            graph = get_capability_graph()
            count = 0
            for pattern in architecture.get("detected_patterns", []):
                graph.register_tool(f"arch_{pattern[:20]}", pattern)
                count += 1
            result["layer6"] = count
        except Exception:
            pass

        total = sum(result.values())
        logger.info(f"CodeLearner: persisted {total} items across 6 memory layers")
        return result


# ── Singleton ──

_code_learner: Optional[CodeLearner] = None


def get_code_learner() -> CodeLearner:
    global _code_learner
    if _code_learner is None:
        _code_learner = CodeLearner()
    return _code_learner
