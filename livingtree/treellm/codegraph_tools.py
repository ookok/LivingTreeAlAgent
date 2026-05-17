"""CodeGraph tools — expose pre-scanned dependency graph to LLM via tool calls.

LLM can query:
  codegraph_deps(module)  → what this module depends on
  codegraph_callers(func) → who calls this function
  codegraph_callees(func) → what this function calls
  codegraph_impact(file)  → blast radius if this file changes

All queries read from cached CodeGraph pickle — zero scanning at query time.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from loguru import logger

CACHE_PATH = Path(".livingtree/code_graph.pickle")
_graph: Any = None


def _ensure_loaded():
    global _graph
    if _graph is not None:
        return _graph
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "rb") as f:
                _graph = pickle.load(f)
            logger.debug(f"CodeGraph loaded: {_graph.stats() if hasattr(_graph, 'stats') else 'ok'}")
        except Exception:
            _graph = object()  # Sentinel for "loaded but failed"
    else:
        _graph = None
    return _graph


def codegraph_deps(module: str) -> str:
    """Query: what modules does <module> import/depend on?"""
    g = _ensure_loaded()
    if not g or g is object():
        return "CodeGraph not built. Run: livingtree scan"
    try:
        deps = g.get_deps(module) if hasattr(g, 'get_deps') else []
        if not deps:
            return f"No dependencies found for {module}"
        return "\n".join(f"  {d}" for d in deps[:20])
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
