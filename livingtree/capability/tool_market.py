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

# ── Map tools ──

def _lookup_location(params: dict, world: Any = None) -> dict:
    """Geocode lookup with known city coordinates."""
    query = params.get("query", "").strip()
    cities = {
        "北京": (39.9042, 116.4074), "beijing": (39.9042, 116.4074),
        "上海": (31.2304, 121.4737), "shanghai": (31.2304, 121.4737),
        "广州": (23.1291, 113.2644), "guangzhou": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579), "shenzhen": (22.5431, 114.0579),
        "成都": (30.5728, 104.0668), "chengdu": (30.5728, 104.0668),
        "杭州": (30.2741, 120.1551), "hangzhou": (30.2741, 120.1551),
        "武汉": (30.5928, 114.3055), "wuhan": (30.5928, 114.3055),
        "南京": (32.0603, 118.7969), "nanjing": (32.0603, 118.7969),
        "重庆": (29.4316, 106.9123), "chongqing": (29.4316, 106.9123),
        "西安": (34.3416, 108.9398), "xian": (34.3416, 108.9398),
    }
    match = cities.get(query.lower(), None)
    if match:
        return {"query": query, "lat": match[0], "lon": match[1], "found": True}
    return {"query": query, "found": False, "hint": "Known: 北京/上海/广州/深圳/成都/杭州/武汉/南京/重庆/西安"}

def _geocode_reverse(params: dict, world: Any = None) -> dict:
    lat, lon = params.get("lat", 0), params.get("lon", 0)
    return {"lat": lat, "lon": lon, "location": f"({lat:.4f}, {lon:.4f})",
            "map_url": f"https://www.tianditu.gov.cn/?lat={lat}&lng={lon}"}

# ── Email tools ──

def _send_email(params: dict, world: Any = None) -> dict:
    """Send email via 163.com SMTP with credentials from encrypted vault."""
    subject = params.get("subject", "")
    body = params.get("body", "")
    to = params.get("to", "")
    if not to or not subject:
        return {"status": "error", "error": "to and subject required"}

    # Load SMTP credentials from encrypted vault
    try:
        from ..config.secrets import get_secret_vault
        vault = get_secret_vault()
        smtp_host = vault.get("smtp_host", "smtp.163.com")
        smtp_port = int(vault.get("smtp_port", "465"))
        smtp_user = vault.get("smtp_user", "")
        smtp_pass = vault.get("smtp_pass", "")
    except Exception:
        smtp_host = "smtp.163.com"
        smtp_port = 465
        smtp_user = "livingtreeai@163.com"
        smtp_pass = ""

    if not smtp_user or not smtp_pass:
        return {"status": "error", "error": "SMTP credentials not configured"}

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to], msg.as_string())
        server.quit()
        return {"status": "sent", "to": to, "subject": subject,
                "from": smtp_user, "host": smtp_host}
    except smtplib.SMTPAuthenticationError:
        return {"status": "error", "error": "SMTP auth failed. Check credentials."}
    except smtplib.SMTPException as e:
        return {"status": "error", "error": f"SMTP error: {e}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ── Expert training tools ──

def _distill_knowledge(params: dict, world: Any = None) -> dict:
    if not world or not world.distillation:
        return {"error": "Distillation not available"}
    import asyncio
    loop = asyncio.get_event_loop()
    prompts = params.get("prompts", [params.get("prompt", "Explain AI agents")])
    if isinstance(prompts, str):
        prompts = [prompts]
    result = loop.run_until_complete(
        world.distillation.distill_knowledge(None, prompts, world.expert_config))
    return {"expert": world.expert_config.model if world.expert_config else "default",
            "prompts": len(prompts), "outputs": result.prompts_processed, "quality": result.quality_score}

def _curriculum_learning(params: dict, world: Any = None) -> dict:
    if not world or not world.distillation:
        return {"error": "Distillation not available"}
    import asyncio
    loop = asyncio.get_event_loop()
    topics = params.get("topics", [params.get("topic", "AI basics")])
    if isinstance(topics, str):
        topics = [topics]
    levels = params.get("levels", [1, 2, 3])
    from ..cell.cell_ai import CellAI
    cell = CellAI(name=f"curriculum_{topics[0][:10]}")
    result = loop.run_until_complete(
        world.distillation.curriculum_learning(cell, topics, levels, world.expert_config))
    if world.cell_registry:
        world.cell_registry.register(cell)
    return {"topics": len(topics), "levels": levels, "cell": cell.name, **result}

# ── Skill tools ──

def _list_skills(params: dict, world: Any = None) -> dict:
    if not world or not world.skill_factory:
        return {"error": "SkillFactory not available"}
    skills = world.skill_factory.discover_skills()
    return {"skills": skills, "count": len(skills)}

def _create_skill(params: dict, world: Any = None) -> dict:
    if not world or not world.skill_factory:
        return {"error": "SkillFactory not available"}
    skill = world.skill_factory.create_skill(
        name=params["name"], description=params.get("description", ""),
        code=params.get("code", "def execute(data): return {'status': 'ok'}"),
        category=params.get("category", "general"))
    return {"name": params["name"], "created": True, "skills_total": len(world.skill_factory.discover_skills())}

# ── Calculation model handlers ──

import math

def _gaussian_plume(params: dict, world: Any = None) -> dict:
    """Gaussian plume dispersion model: C = Q/(2π·σy·σz·u) · exp(-y²/2σy²) · [exp(-(z-He)²/2σz²) + exp(-(z+He)²/2σz²)]"""
    Q, u, x = params["Q"], params["u"], params["x"]
    y = params.get("y", 0)
    z = params.get("z", 0)
    stability = params.get("stability", "D")
    He = params.get("He", 0)

    # GB/T3840-1991 dispersion coefficients
    coef = {"A": (0.527, 0.865, 0.28, 0.90), "B": (0.371, 0.866, 0.23, 0.85),
            "C": (0.209, 0.897, 0.22, 0.80), "D": (0.128, 0.905, 0.20, 0.76),
            "E": (0.098, 0.902, 0.15, 0.73), "F": (0.065, 0.902, 0.12, 0.67)}
    g = coef.get(stability, coef["D"])
    sy = g[0] * x ** g[1]
    sz = g[2] * x ** g[3]

    if sy <= 0 or sz <= 0 or u <= 0:
        return {"error": "Invalid parameters"}

    C = Q / (2 * math.pi * sy * sz * u) * math.exp(-y**2 / (2 * sy**2))
    C *= (math.exp(-(z - He)**2 / (2 * sz**2)) + math.exp(-(z + He)**2 / (2 * sz**2)))

    return {"model": "gaussian_plume", "C_mgm3": round(C * 1000, 6), "C_gm3": round(C, 8),
            "Q_gs": Q, "u_ms": u, "x_m": x, "y_m": y, "z_m": z,
            "stability": stability, "sy_m": round(sy, 2), "sz_m": round(sz, 2)}

def _noise_attenuation(params: dict, world: Any = None) -> dict:
    """Point source noise attenuation per GB12348-2008."""
    Lw, r = params["Lw"], params["r"]
    ground_type = params.get("ground_type", "hard")
    Agr = 5 * (1 - math.exp(-r / 50)) if ground_type == "soft" else 0
    Lp = Lw - 20 * math.log10(max(r, 0.1)) - 11 - Agr
    return {"model": "noise_attenuation", "Lw_dB": Lw, "r_m": r,
            "Lp_dB": round(Lp, 2), "Agr_dB": round(Agr, 2), "ground": ground_type,
            "standard": "GB12348-2008"}

def _water_dilution(params: dict, world: Any = None) -> dict:
    """Complete mixing dilution model for rivers."""
    C0, Q0, Qe = params["C0"], params["Q0"], params["Qe"]
    if Q0 + Qe <= 0:
        return {"error": "Q0+Qe must be > 0"}
    C = C0 * Q0 / (Q0 + Qe)
    alpha = Qe / (Q0 + Qe) if (Q0 + Qe) > 0 else 0
    return {"model": "water_dilution", "C_mgL": round(C, 4),
            "C0_mgL": C0, "Q0_m3s": Q0, "Qe_m3s": Qe,
            "dilution_factor": round(alpha, 4), "method": "完全混合模型"}

def _dispersion_coeff(params: dict, world: Any = None) -> dict:
    """Dispersion coefficients per Pasquill-Gifford (GB/T3840-1991)."""
    x = params["x"]
    stability = params.get("stability", "D")
    coef = {"A": (0.527, 0.865, 0.28, 0.90), "B": (0.371, 0.866, 0.23, 0.85),
            "C": (0.209, 0.897, 0.22, 0.80), "D": (0.128, 0.905, 0.20, 0.76),
            "E": (0.098, 0.902, 0.15, 0.73), "F": (0.065, 0.902, 0.12, 0.67)}
    g = coef.get(stability, coef["D"])
    sy = g[0] * x ** g[1]
    sz = g[2] * x ** g[3]
    return {"model": "dispersion_coeff", "x_m": x, "stability": stability,
            "sy_m": round(sy, 2), "sz_m": round(sz, 2),
            "standard": "GB/T3840-1991 Pasquill-Gifford",
            "all_classes": {k: {"sy": round(v[0]*x**v[1], 2), "sz": round(v[2]*x**v[3], 2)}
                            for k, v in coef.items()}}


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

    # Map / GIS tools
    ("lookup_location", "Lookup city coordinates (lat/lon)", "map",
     {"properties": {"query": {"type": "string"}}, "required": ["query"]}, _lookup_location),
    ("geocode_reverse", "Reverse geocode: lat/lon to map URL", "map",
     {"properties": {"lat": {"type": "number"}, "lon": {"type": "number"}},
      "required": ["lat", "lon"]}, _geocode_reverse),

    # Email tools
    ("send_email", "Queue an email for dispatch", "email",
     {"properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
      "required": ["to", "subject", "body"]}, _send_email),

    # Expert training tools
    ("distill_knowledge", "Distill knowledge from expert LLM into cell", "training",
     {"properties": {"prompts": {"type": "array", "items": {"type": "string"}},
      "prompt": {"type": "string"}}}, _distill_knowledge),
    ("curriculum_learning", "Curriculum learning: progressive topic difficulty", "training",
     {"properties": {"topics": {"type": "array", "items": {"type": "string"}},
      "levels": {"type": "array", "items": {"type": "integer"}}}}, _curriculum_learning),

    # Skill tools
    ("list_skills", "List all registered skills", "skill",
     {"properties": {}}, _list_skills),
    ("create_skill", "Create a new agent skill", "skill",
     {"properties": {"name": {"type": "string"}, "description": {"type": "string"},
      "code": {"type": "string"}, "category": {"type": "string"}},
      "required": ["name"]}, _create_skill),

    # ── Calculation models ──
    ("gaussian_plume", "Gaussian plume dispersion C=Q/(2πσyσz·u)·exp(-y²/2σy²)·exp(-z²/2σz²)", "model",
     {"properties": {"Q": {"type": "number", "description": "源强 (g/s)"},
      "u": {"type": "number", "description": "风速 (m/s)"},
      "x": {"type": "number", "description": "下风向距离 (m)"},
      "y": {"type": "number", "default": 0}, "z": {"type": "number", "default": 0},
      "stability": {"type": "string", "default": "D"}},
      "required": ["Q", "u", "x"]}, _gaussian_plume),
    ("noise_attenuation", "点声源几何衰减+地面吸收 Lp=Lw-20log(r)-11-Agr", "model",
     {"properties": {"Lw": {"type": "number", "description": "声功率级 (dB)"},
      "r": {"type": "number", "description": "距离 (m)"},
      "ground_type": {"type": "string", "default": "hard"}},
      "required": ["Lw", "r"]}, _noise_attenuation),
    ("water_dilution", "河流完全混合稀释模型 C=C0·Q0/(Q0+Qe)", "model",
     {"properties": {"C0": {"type": "number", "description": "污染物浓度 (mg/L)"},
      "Q0": {"type": "number", "description": "河水流量 (m³/s)"},
      "Qe": {"type": "number", "description": "废水流量 (m³/s)"}},
      "required": ["C0", "Q0", "Qe"]}, _water_dilution),
    ("dispersion_coeff", "大气扩散参数 σy,σz 按GB/T3840-1991 Pasquill稳定度A-F", "model",
     {"properties": {"x": {"type": "number", "description": "下风向距离 (m)"},
      "stability": {"type": "string", "default": "D"}},
      "required": ["x"]}, _dispersion_coeff),
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
