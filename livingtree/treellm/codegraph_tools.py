"""CodeGraph tools — expose code dependency graph to LLM via tool calls.

LLM can query:
  codegraph_deps(module)  → what this module depends on
  codegraph_callers(func) → who calls this function
  codegraph_callees(func) → what this function calls
  codegraph_impact(file)  → blast radius if this file changes
  codegraph_update()      → re-index changed files (hash-based incremental)

Storage: SQLite (fast init, indexed queries) with pickle fallback.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any

from loguru import logger

CACHE_PICKLE = Path(".livingtree/code_graph.pickle")
CACHE_DB = Path(".livingtree/codegraph.db")
_graph: Any = None
_db: Any = None
_graph_build_time: float = 0.0
_use_db: bool = False


def _ensure_loaded():
    global _graph, _db, _graph_build_time, _use_db
    if _graph is not None or _db is not None:
        return

    # Try SQLite first (faster init — just connect, no deserialize)
    if CACHE_DB.exists():
        try:
            from ..capability.codegraph_db import CodeGraphDB
            _db = CodeGraphDB(str(CACHE_DB))
            _db.connect()
            _graph_build_time = CACHE_DB.stat().st_mtime
            _use_db = True
            logger.debug(f"CodeGraph SQLite loaded: {_db.stats()}")
            return
        except Exception:
            _db = None

    # Fallback to pickle
    if CACHE_PICKLE.exists():
        try:
            with open(CACHE_PICKLE, "rb") as f:
                _graph = pickle.load(f)
            _graph_build_time = CACHE_PICKLE.stat().st_mtime
            _use_db = False
            logger.debug(f"CodeGraph pickle loaded")
        except Exception:
            _graph = object()


def _check_staleness(hint: str = "") -> str:
    cache = CACHE_DB if _use_db else CACHE_PICKLE
    if not cache.exists():
        return ""
    if hint:
        p = Path(hint)
        if p.exists() and p.stat().st_mtime > _graph_build_time:
            return f"[stale] {hint} modified after graph build."
    return ""


def _not_built_fallback(kind: str, arg: str) -> str:
    """When CodeGraph is not built, suggest fast alternatives."""
    tips = {
        "deps": f"bash: rg \"^from|^import\" livingtree/ | grep {arg.split('.')[-1]}",
        "callers": f"bash: rg \"{arg}\" livingtree/ -l",
        "callees": f"read_file of the source file, then look for function calls",
        "impact": f"git diff --stat, or read_file of the file directly",
    }
    tip = tips.get(kind, "")
    return (
        f"CodeGraph not built. Fast alternatives:\n"
        f"  1. {tip}\n"
        f"  2. read_file to read the file directly\n"
        f"  3. codegraph_update to build the index (5s, one-time)"
    )


def _query_backend(kind: str, arg: str) -> str:
    _ensure_loaded()

    if _use_db and _db:
        if kind == "deps":
            return "\n".join(f"  {d}" for d in _db.get_deps(arg)) or "no results"
        elif kind == "callers":
            return "\n".join(f"  {c}" for c in _db.get_callers(arg)) or "no results"
        elif kind == "callees":
            return "\n".join(f"  {c}" for c in _db.get_callees(arg)) or "no results"
        elif kind == "impact":
            rows = _db.get_impact(arg)
            return "\n".join(f"  {f} (score={s})" for f, s in rows) if rows else "no results"

    if _graph and _graph is not object():
        if kind == "deps" and hasattr(_graph, 'get_deps'):
            return "\n".join(f"  {d}" for d in _graph.get_deps(arg)[:20]) or "no results"
        elif kind == "callers" and hasattr(_graph, 'get_callers'):
            return "\n".join(f"  {c}" for c in _graph.get_callers(arg)[:20]) or "no results"
        elif kind == "callees" and hasattr(_graph, 'get_callees'):
            return "\n".join(f"  {c}" for c in _graph.get_callees(arg)[:20]) or "no results"
        elif kind == "impact" and hasattr(_graph, 'impact_score'):
            rows = _graph.impact_score([arg])[:15]
            return "\n".join(f"  {f} (score={s})" for f, s in rows) if rows else "no results"

    # Not built — suggest fast alternatives
    return _not_built_fallback(kind, arg)


def codegraph_update() -> str:
    """Re-index changed files to SQLite backend."""
    try:
        from ..capability.codegraph_db import CodeGraphDB
        db = CodeGraphDB(str(CACHE_DB))
        db.connect()
        db.begin_batch()

        import ast as _ast
        count = 0
        for py_file in Path("livingtree").rglob("*.py"):
            if "_archive" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")[:30000]
                file_hash = hashlib.md5(content.encode()).hexdigest()
                old_hash = db.get_file_hash(str(py_file))
                if old_hash == file_hash:
                    continue  # unchanged
                db.clear_file(str(py_file))
                tree = _ast.parse(content)
                for node in _ast.walk(tree):
                    if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                        eid = f"{py_file.stem}.{node.name}"
                        db.upsert_entity({
                            "id": eid, "name": node.name, "file": str(py_file),
                            "kind": "function", "line": node.lineno,
                            "end_line": getattr(node, 'end_lineno', node.lineno),
                            "hash": file_hash,
                        })
                        count += 1
                        for child in _ast.walk(node):
                            if isinstance(child, _ast.Call):
                                callee = ""
                                if isinstance(child.func, _ast.Name):
                                    callee = child.func.id
                                elif isinstance(child.func, _ast.Attribute):
                                    callee = _ast.unparse(child.func)
                                if callee and not callee.startswith("_"):
                                    db.add_call(eid, callee, str(py_file), child.lineno)
                    elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
                        if isinstance(node, _ast.ImportFrom) and node.module:
                            db.add_import(str(py_file), node.module)
                        for alias in node.names:
                            db.add_import(str(py_file), alias.name)
                if not db.get_file_hash(str(py_file)):
                    db.set_meta(f"indexed:{py_file}", file_hash)
            except Exception:
                continue

        db.set_meta("build_time", str(time.time()))
        db.set_meta("entity_count", str(db.entity_count()))
        db.commit_batch()

        global _db, _use_db, _graph_build_time
        _db = db
        _use_db = True
        _graph_build_time = time.time()
        stats = db.stats()
        return (
            f"CodeGraph updated (SQLite): {stats['total_entities']} entities, "
            f"{stats['total_files']} files, {stats['total_calls']} calls, "
            f"{stats['total_imports']} imports, {stats['db_size_mb']}MB"
        )
    except Exception as e:
        return f"CodeGraph update failed: {e}"


def codegraph_deps(module: str) -> str:
    stale = _check_staleness()
    result = _query_backend("deps", module)
    return f"{stale}\n{result}" if stale else result


def codegraph_callers(func: str) -> str:
    stale = _check_staleness()
    result = _query_backend("callers", func)
    return f"{stale}\n{result}" if stale else result


def codegraph_callees(func: str) -> str:
    stale = _check_staleness()
    result = _query_backend("callees", func)
    return f"{stale}\n{result}" if stale else result


def codegraph_impact(file: str) -> str:
    stale = _check_staleness(file)
    result = _query_backend("impact", file)
    prefix = f"Blast radius for {file}:\n"
    return f"{stale}\n{prefix}{result}" if stale else f"{prefix}{result}"


# ── Tool registration for CapabilityBus ──

TOOLS = {
    "codegraph_update": {
        "description": "Re-index changed files in the code graph (hash-based incremental, zero rescan for unchanged). Use when graph is stale or after code changes.",
        "func": codegraph_update,
        "params": "",
    },
    "codegraph_deps": {
        "description": "Query the pre-scanned dependency graph: list modules that <module> imports/depends on.",
        "func": codegraph_deps,
        "params": {"module": "Module name, e.g. livingtree.treellm.core"},
    },
    "codegraph_callers": {
        "description": "Query the pre-scanned call graph: list functions/places that call <func>.",
        "func": codegraph_callers,
        "params": {"func": "Function name, e.g. core.chat or TreeLLM.chat"},
    },
    "codegraph_callees": {
        "description": "Query the pre-scanned call graph: list functions that <func> calls.",
        "func": codegraph_callees,
        "params": {"func": "Function name, e.g. core.chat or TreeLLM.chat"},
    },
    "codegraph_impact": {
        "description": "Query the pre-scanned impact analysis: what files would be affected if <file> changes.",
        "func": codegraph_impact,
        "params": {"file": "File path, e.g. livingtree/treellm/core.py"},
    },
}
