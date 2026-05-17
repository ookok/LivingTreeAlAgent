"""CodeGraph tools — expose pre-scanned dependency graph to LLM via tool calls.

LLM can query:
  codegraph_deps(module)  → what this module depends on
  codegraph_callers(func) → who calls this function
  codegraph_callees(func) → what this function calls
  codegraph_impact(file)  → blast radius if this file changes
  codegraph_update()      → re-index changed files (hash-based incremental)

Auto-detects staleness: if a file's mtime > graph build time, marks result as [stale].
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any

from loguru import logger

CACHE_PATH = Path(".livingtree/code_graph.pickle")
_graph: Any = None
_graph_build_time: float = 0.0


def _ensure_loaded():
    global _graph, _graph_build_time
    if _graph is not None:
        return _graph
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "rb") as f:
                _graph = pickle.load(f)
            _graph_build_time = CACHE_PATH.stat().st_mtime
            stats = _graph.stats() if hasattr(_graph, 'stats') else {}
            logger.debug(f"CodeGraph loaded: {stats}")
        except Exception:
            _graph = object()
    else:
        _graph = None
    return _graph


def _check_staleness(hint: str = "") -> str:
    """Check if graph is stale vs filesystem."""
    if not CACHE_PATH.exists():
        return "[stale] CodeGraph not built. Use: codegraph_update"
    g = _ensure_loaded()
    if g is object():
        return "[stale] CodeGraph corrupted. Use: codegraph_update"
    if hint:
        p = Path(hint)
        if p.exists() and p.stat().st_mtime > _graph_build_time:
            return f"[stale] {hint} modified after graph build. Use: codegraph_update"
    return ""


def codegraph_update() -> str:
    """Re-index changed files (hash-based incremental). Zero rescan for unchanged files."""
    try:
        from ..capability.code_graph import CodeGraph
        cg = CodeGraph()
        if hasattr(cg, 'load') and CACHE_PATH.exists():
            cg.load()
        stats = cg.index(".", patterns=["**/*.py"])
        cg.save(str(CACHE_PATH))
        global _graph, _graph_build_time
        _graph = cg
        _graph_build_time = time.time()
        return (
            f"CodeGraph updated: {stats.total_files} files, "
            f"{stats.total_entities} entities, {stats.total_edges} edges, "
            f"{stats.build_time_ms:.0f}ms"
        )
    except Exception as e:
        return f"CodeGraph update failed: {e}"


def codegraph_deps(module: str) -> str:
    g = _ensure_loaded()
    if not g or g is object():
        return "CodeGraph not built. Use: codegraph_update"
    stale = _check_staleness()
    try:
        deps = g.get_deps(module) if hasattr(g, 'get_deps') else []
        result = "\n".join(f"  {d}" for d in deps[:20]) if deps else f"No dependencies found for {module}"
        return f"{stale}\n{result}" if stale else result
    except Exception as e:
        return f"CodeGraph error: {e}"


def codegraph_callers(func: str) -> str:
    """Query: who calls <func>?"""
    g = _ensure_loaded()
    if not g or g is object():
        return "CodeGraph not built. Run: livingtree scan"
    try:
        callers = g.get_callers(func) if hasattr(g, 'get_callers') else []
        if not callers:
            return f"No callers found for {func}"
        return "\n".join(f"  {c}" for c in callers[:20])
    except Exception as e:
        return f"CodeGraph error: {e}"


def codegraph_callees(func: str) -> str:
    """Query: what does <func> call?"""
    g = _ensure_loaded()
    if not g or g is object():
        return "CodeGraph not built. Run: livingtree scan"
    try:
        callees = g.get_callees(func) if hasattr(g, 'get_callees') else []
        if not callees:
            return f"No callees found for {func}"
        return "\n".join(f"  {c}" for c in callees[:20])
    except Exception as e:
        return f"CodeGraph error: {e}"


def codegraph_impact(file: str) -> str:
    """Query: what would be affected if <file> changes?"""
    g = _ensure_loaded()
    if not g or g is object():
        return "CodeGraph not built. Run: livingtree scan"
    try:
        impacted = g.impact_score([file]) if hasattr(g, 'impact_score') else []
        if not impacted:
            return f"No impact data for {file}"
        lines = []
        for fpath, score in impacted[:15]:
            lines.append(f"  {fpath} (impact={score})")
        return f"Blast radius for {file}:\n" + "\n".join(lines)
    except Exception as e:
        return f"CodeGraph error: {e}"


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
