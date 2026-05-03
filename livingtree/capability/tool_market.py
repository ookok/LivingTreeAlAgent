"""ToolMarket — Unified agent tool registry with real implementations.

Tools delegate to existing subsystems: ASTParser, CodeGraph, KnowledgeBase,
DocEngine, CodeEngine, MaterialCollector, etc. No reinvention.

30+ tools in 6 categories: file, code, knowledge, document, web, system.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    type: str = "python"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    category: str = "general"
    handler: Callable | None = Field(default=None, exclude=True)
    rating: float = 0.0


class ToolMarket:
    """Unified tool registry. Tools delegate to existing subsystems."""

    def __init__(self, world: Any = None):
        self._tools: dict[str, ToolSpec] = {}
        self._world = world

    def set_world(self, world) -> None:
        self._world = world

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def discover(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def search(self, query: str) -> list[ToolSpec]:
        q = query.lower()
        return [t for t in self._tools.values()
                if q in t.name.lower() or q in t.description.lower()]

    def list_by_category(self, category: str) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.category == category]

    async def execute(self, name: str, input_data: dict[str, Any]) -> Any:
        """Execute a tool by name, delegating to its handler."""
        spec = self._tools.get(name)
        if not spec:
            return {"error": f"Tool not found: {name}"}
        if spec.handler:
            try:
                result = spec.handler(input_data, world=self._world)
                import asyncio
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as e:
                logger.warning(f"Tool {name} failed: {e}")
                return {"error": str(e)}
        return {"error": f"Tool {name} has no handler"}


# ── Handler functions (delegate to world subsystems) ──

def _read_file(params: dict, world: Any = None) -> dict:
    p = Path(params["path"])
    if not p.exists():
        return {"error": f"File not found: {params['path']}"}
    content = p.read_text(encoding="utf-8", errors="replace")
    limit = params.get("limit", 5000)
    return {"path": str(p), "size": len(content), "content": content[:limit]}

def _write_file(params: dict, world: Any = None) -> dict:
    p = Path(params["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(params["content"], encoding="utf-8")
    return {"path": str(p), "written": len(params["content"])}

def _list_directory(params: dict, world: Any = None) -> dict:
    p = Path(params.get("path", "."))
    if not p.is_dir():
        return {"error": f"Not a directory: {p}"}
    items = []
    for entry in sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name)):
        items.append({
            "name": entry.name,
            "type": "dir" if entry.is_dir() else "file",
            "size": entry.stat().st_size if entry.is_file() else 0,
        })
    return {"path": str(p), "count": len(items), "items": items[:50]}

def _search_files(params: dict, world: Any = None) -> dict:
    import re
    pattern = params.get("pattern", "*.py")
    query = params.get("query", "")
    root = Path(params.get("path", "."))
    results = []
    for f in root.rglob(pattern):
        if f.name.startswith(".") or "__pycache__" in str(f) or ".git" in str(f):
            continue
        if f.is_dir():
            continue
        if query:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                if query.lower() in content.lower():
                    results.append({"path": str(f), "size": len(content)})
            except Exception:
                pass
        else:
            results.append({"path": str(f), "size": f.stat().st_size})
    return {"query": query or pattern, "count": len(results), "results": results[:20]}

def _parse_ast(params: dict, world: Any = None) -> dict:
    if not world or not world.ast_parser:
        return {"error": "ASTParser not available"}
    path = params.get("path", "")
    source = params.get("source", "")
    if path:
        nodes, edges = world.ast_parser.parse_file(path)
    elif source:
        lang = params.get("language", "python")
        nodes, edges = world.ast_parser.parse_source(source, lang)
    else:
        return {"error": "path or source required"}
    return {
        "functions": [{"name": n.name, "line": n.line} for n in nodes if n.kind == "function"],
        "classes": [{"name": n.name, "line": n.line} for n in nodes if n.kind == "class"],
        "imports": [n.name for n in nodes if n.kind == "import"][:20],
        "total_nodes": len(nodes), "total_edges": len(edges),
    }

def _find_callers(params: dict, world: Any = None) -> dict:
    if not world or not world.code_graph:
        return {"error": "CodeGraph not built. Run index_codebase first."}
    name = params["function_name"]
    callers = world.code_graph.get_callers(name)
    return {"function": name, "callers": [{"name": c.name, "file": c.file, "line": c.line} for c in callers[:20]]}

def _find_callees(params: dict, world: Any = None) -> dict:
    if not world or not world.code_graph:
        return {"error": "CodeGraph not built."}
    callees = world.code_graph.get_callees(params["function_name"])
    return {"function": params["function_name"], "callees": callees[:20]}

def _blast_radius(params: dict, world: Any = None) -> dict:
    if not world or not world.code_graph:
        return {"error": "CodeGraph not built."}
    files = params.get("files", [])
    results = world.code_graph.blast_radius(files)
    return {"changed": files, "impacted": [{"file": r.file, "reason": r.reason, "risk": r.risk} for r in results[:30]]}

def _index_codebase(params: dict, world: Any = None) -> dict:
    if not world or not world.code_graph:
        return {"error": "CodeGraph not available"}
    stats = world.code_graph.index(params.get("path", "."))
    world.code_graph.save()
    return {"files": stats.total_files, "entities": stats.total_entities, "edges": stats.total_edges,
            "build_time_ms": stats.build_time_ms, "languages": stats.languages}

def _search_code(params: dict, world: Any = None) -> dict:
    if not world or not world.code_graph:
        return {"error": "CodeGraph not built."}
    results = world.code_graph.search(params["query"])
    return {"query": params["query"], "results": [{"name": e.name, "file": e.file, "kind": e.kind} for e in results[:20]]}

def _search_knowledge(params: dict, world: Any = None) -> dict:
    if not world or not world.knowledge_base:
        return {"error": "KnowledgeBase not available"}
    results = world.knowledge_base.search(params["query"], top_k=params.get("top_k", 10))
    return {"query": params["query"], "results": [{"title": d.title, "domain": d.domain,
              "content": d.content[:200], "valid_from": str(d.valid_from) if d.valid_from else None} for d in results]}

def _add_knowledge(params: dict, world: Any = None) -> dict:
    if not world or not world.knowledge_base:
        return {"error": "KnowledgeBase not available"}
    from .knowledge_base import Document
    doc = Document(title=params["title"], content=params["content"], domain=params.get("domain"), source=params.get("source", "agent"))
    doc_id = world.knowledge_base.add_knowledge(doc)
    return {"id": doc_id, "title": params["title"]}

def _detect_gaps(params: dict, world: Any = None) -> dict:
    if not world or not world.gap_detector or not world.knowledge_base:
        return {"error": "GapDetector not available"}
    plan = world.gap_detector.generate_learning_plan(world.knowledge_base)
    return {"gaps": [{"domain": g.domain, "topic": g.topic, "priority": g.priority} for g in plan[:15]]}

def _discover_formats(params: dict, world: Any = None) -> dict:
    if not world or not world.format_discovery:
        return {"error": "FormatDiscovery not available"}
    template = world.format_discovery.analyze_document(params["path"])
    return {"name": template.name, "formats": list(template.formats), "structure": template.structure}

def _generate_report(params: dict, world: Any = None) -> dict:
    if not world or not world.doc_engine:
        return {"error": "DocEngine not available"}
    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        world.doc_engine.generate_report(params["template_type"], params.get("data", {}), params.get("requirements", {})))
    return {"template": params["template_type"], "sections": len(result.get("sections", [])),
            "document_length": len(result.get("document", "")), "completed": result.get("completed", False)}

def _generate_code(params: dict, world: Any = None) -> dict:
    if not world or not world.code_engine:
        return {"error": "CodeEngine not available"}
    from .code_engine import CodeSpec
    import asyncio
    loop = asyncio.get_event_loop()
    spec = CodeSpec(name=params.get("name", "generated"), description=params["description"],
                    language=params.get("language", "python"), domain=params.get("domain", "general"))
    result = loop.run_until_complete(world.code_engine.generate_with_annotation(spec))
    return {"name": result.name, "code": result.code, "annotations": result.annotations, "language": result.language}

def _fetch_url(params: dict, world: Any = None) -> dict:
    import urllib.request
    url = params["url"]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=params.get("timeout", 30)) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        return {"url": url, "status": 200, "content": content[:params.get("limit", 3000)]}
    except Exception as e:
        return {"url": url, "error": str(e)}

def _get_status(params: dict, world: Any = None) -> dict:
    return {"status": "online", "version": "2.0.0", "generation": 1}

def _list_cells(params: dict, world: Any = None) -> dict:
    if not world or not world.cell_registry:
        return {"error": "CellRegistry not available"}
    cells = world.cell_registry.discover()
    return {"cells": [{"name": getattr(c, "name", str(c)[:30])} for c in cells]}


# ── Tool definitions ──

ALL_TOOLS = [
    # File tools
    ("read_file", "Read a file's content", "file",
     {"properties": {"path": {"type": "string", "description": "File path"}}}, _read_file),
    ("write_file", "Write content to a file", "file",
     {"properties": {"path": {"type": "string"}, "content": {"type": "string"}},
      "required": ["path", "content"]}, _write_file),
    ("list_directory", "List directory contents", "file",
     {"properties": {"path": {"type": "string", "default": "."}}}, _list_directory),
    ("search_files", "Search files by name or content", "file",
     {"properties": {"path": {"type": "string"}, "pattern": {"type": "string"}, "query": {"type": "string"}}}, _search_files),

    # Code tools
    ("parse_ast", "Parse source code AST (functions/classes/imports)", "code",
     {"properties": {"path": {"type": "string"}, "source": {"type": "string"}, "language": {"type": "string"}}}, _parse_ast),
    ("find_callers", "Find all functions that call a given function", "code",
     {"properties": {"function_name": {"type": "string"}}, "required": ["function_name"]}, _find_callers),
    ("find_callees", "Find all functions called by a given function", "code",
     {"properties": {"function_name": {"type": "string"}}, "required": ["function_name"]}, _find_callees),
    ("blast_radius", "Find all files affected by changes", "code",
     {"properties": {"files": {"type": "array", "items": {"type": "string"}}},
      "required": ["files"]}, _blast_radius),
    ("index_codebase", "Build code knowledge graph for a project", "code",
     {"properties": {"path": {"type": "string", "default": "."}}}, _index_codebase),
    ("search_code", "Search code entities by name", "code",
     {"properties": {"query": {"type": "string"}}, "required": ["query"]}, _search_code),

    # Knowledge tools
    ("search_knowledge", "Search the knowledge base with bi-temporal support", "knowledge",
     {"properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 10}},
      "required": ["query"]}, _search_knowledge),
    ("add_knowledge", "Add a document to the knowledge base", "knowledge",
     {"properties": {"title": {"type": "string"}, "content": {"type": "string"},
      "domain": {"type": "string"}}, "required": ["title", "content"]}, _add_knowledge),
    ("detect_gaps", "Detect knowledge gaps in the knowledge base", "knowledge",
     {"properties": {}}, _detect_gaps),
    ("discover_formats", "Discover document format and structure", "knowledge",
     {"properties": {"path": {"type": "string"}}, "required": ["path"]}, _discover_formats),

    # Document tools
    ("generate_report", "Generate industrial report (环评/应急预案/验收/可研)", "document",
     {"properties": {"template_type": {"type": "string"}, "data": {"type": "object"},
      "requirements": {"type": "object"}}, "required": ["template_type"]}, _generate_report),

    # Code generation
    ("generate_code", "Generate annotated code from description", "code",
     {"properties": {"name": {"type": "string"}, "description": {"type": "string"},
      "language": {"type": "string", "default": "python"}, "domain": {"type": "string", "default": "general"}},
      "required": ["description"]}, _generate_code),

    # Web tools
    ("fetch_url", "Fetch content from a URL", "web",
     {"properties": {"url": {"type": "string"}, "timeout": {"type": "integer"}, "limit": {"type": "integer"}},
      "required": ["url"]}, _fetch_url),

    # System tools
    ("get_status", "Get system status summary", "system", {"properties": {}}, _get_status),
    ("list_cells", "List all registered AI cells", "system", {"properties": {}}, _list_cells),
]


def register_all_tools(market: ToolMarket) -> int:
    """Register all built-in tools. Returns count."""
    count = 0
    for name, desc, cat, schema, handler in ALL_TOOLS:
        market.register(ToolSpec(name=name, description=desc, type="python",
                                 input_schema=schema, category=cat, handler=handler))
        count += 1
    logger.info(f"ToolMarket: {count} tools registered")
    return count
