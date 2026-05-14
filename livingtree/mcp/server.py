"""MCP Server — Model Context Protocol server for LivingTree tools.

Exposes LivingTree capabilities to external AI tools (Claude Code, Codex,
Cursor, Windsurf, etc.) via the MCP protocol.

28 tools in 5 categories:
- Code Graph: build_graph, blast_radius, callers, callees, search, hubs, gaps
- Chat/Reasoning: chat, analyze, generate_report
- Code Gen: generate_code, improve_code, mutate_code
- Knowledge: search_knowledge, detect_gaps, discover_formats
- Cell/Train: train_cell, drill_train, list_cells, absorb_codebase
- System: status, metrics, peers, health

Usage:
    python -m livingtree.mcp.server
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from loguru import logger


TOOLS = [
    # ── Code Graph ──
    {
        "name": "build_code_graph",
        "description": "Build or rebuild the code knowledge graph for a project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root directory to index"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "blast_radius",
        "description": "Find all files affected by a set of changed files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {"type": "array", "items": {"type": "string"}, "description": "Changed file paths"},
            },
            "required": ["files"],
        },
    },
    {
        "name": "get_callers",
        "description": "Find all functions that call a given function",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string", "description": "Function name to find callers for"},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "get_callees",
        "description": "Find all functions called by a given function",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string"},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "search_code",
        "description": "Search code entities by name or file path",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_hubs",
        "description": "Find most-connected architectural hotspots",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "description": "Number of hubs to return", "default": 10},
            },
        },
    },
    {
        "name": "find_uncovered",
        "description": "Find functions without test coverage",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── Chat ──
    {
        "name": "chat",
        "description": "Send a message to the LivingTree AI and get a response",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "User message"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "analyze",
        "description": "Deep analyze a topic with chain-of-thought reasoning",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "generate_report",
        "description": "Generate an industrial report (EIA, emergency plan, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_type": {"type": "string", "description": "环评报告, 应急预案, 验收报告, 可行性研究报告"},
                "data": {"type": "object", "description": "Report data"},
            },
            "required": ["template_type"],
        },
    },
    # ── Code Generation ──
    {
        "name": "generate_code",
        "description": "Generate annotated code from natural language description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "language": {"type": "string", "default": "python"},
                "domain": {"type": "string", "default": "general"},
            },
            "required": ["name", "description"],
        },
    },
    {
        "name": "improve_code",
        "description": "Improve existing code with AI suggestions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "requirements": {"type": "object"},
            },
            "required": ["code"],
        },
    },
    # ── Knowledge ──
    {
        "name": "search_knowledge",
        "description": "Search the LivingTree knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "detect_knowledge_gaps",
        "description": "Detect knowledge gaps in the knowledge base",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "discover_formats",
        "description": "Discover document formats in a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    # ── Cell / Training ──
    {
        "name": "train_cell",
        "description": "Train an AI cell on domain data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cell_name": {"type": "string"},
                "data": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["cell_name"],
        },
    },
    {
        "name": "drill_train",
        "description": "Train using MS-SWIFT automated pipeline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cell_name": {"type": "string"},
                "model_name": {"type": "string"},
                "dataset": {"type": "array", "items": {"type": "object"}},
                "training_type": {"type": "string", "default": "lora"},
            },
            "required": ["cell_name", "model_name"],
        },
    },
    {
        "name": "absorb_codebase",
        "description": "Absorb code patterns from a directory into a cell",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    # ── System ──
    {
        "name": "get_status",
        "description": "Get LivingTree system status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_metrics",
        "description": "Get runtime metrics",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "discover_peers",
        "description": "Discover P2P network peers",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── LivingTree Unique Tools ──
    {
        "name": "lookup_standard",
        "description": "O(1) lookup of Chinese environmental standards (GB/HJ). Returns exact standard text with numeric limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Standard name or keyword, e.g. 'GB3095 PM2.5限值' or '噪声标准'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "classify_water_quality",
        "description": "Classify water quality per GB3838-2002 (I-V class). Input COD/BOD/DO/NH3-N values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cod": {"type": "number", "description": "COD mg/L"},
                "bod": {"type": "number", "description": "BOD mg/L"},
                "do": {"type": "number", "description": "Dissolved Oxygen mg/L"},
                "nh3n": {"type": "number", "description": "NH3-N mg/L"},
            },
            "required": ["cod", "bod", "do", "nh3n"],
        },
    },
    {
        "name": "classify_air_quality",
        "description": "Classify air quality per GB3095-2012. Input SO2/NO2/PM10/PM2.5 values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "so2": {"type": "number"}, "no2": {"type": "number"},
                "pm10": {"type": "number"}, "pm25": {"type": "number"},
            },
            "required": ["so2", "no2", "pm10", "pm25"],
        },
    },
    {
        "name": "classify_noise_level",
        "description": "Classify noise level per GB3096-2008. Input daytime and nighttime dB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "daytime_db": {"type": "number"}, "night_db": {"type": "number"},
            },
            "required": ["daytime_db", "night_db"],
        },
    },
    {
        "name": "redact_pii",
        "description": "Redact personally identifiable information from text. Returns cleaned text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to scan and redact"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "detect_outliers",
        "description": "Detect statistical outliers in monitoring data using IQR method.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "number"}, "description": "Numeric monitoring values"},
            },
            "required": ["values"],
        },
    },
    # ═══ Map/GIS Tools ═══
    {
        "name": "geocode",
        "description": "Geocode an address to lat/lon coordinates via Tianditu API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Address to geocode"},
            },
            "required": ["address"],
        },
    },
    {
        "name": "buffer_query",
        "description": "Create a buffer polygon around a point and return GeoJSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lon": {"type": "number"}, "lat": {"type": "number"},
                "radius_m": {"type": "number", "description": "Buffer radius in meters"},
            },
            "required": ["lon", "lat", "radius_m"],
        },
    },
    {
        "name": "spatial_search",
        "description": "Check if a point is inside a polygon. Returns True/False.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lon": {"type": "number"}, "lat": {"type": "number"},
                "polygon": {"type": "object", "description": "GeoJSON polygon"},
            },
            "required": ["lon", "lat", "polygon"],
        },
    },
    {
        "name": "distance_calc",
        "description": "Calculate Haversine distance in meters between two coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lon1": {"type": "number"}, "lat1": {"type": "number"},
                "lon2": {"type": "number"}, "lat2": {"type": "number"},
            },
            "required": ["lon1", "lat1", "lon2", "lat2"],
        },
    },
    {
        "name": "coordinate_transform",
        "description": "Transform coordinates between WGS84, GCJ02, and CGCS2000 systems.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lon": {"type": "number"}, "lat": {"type": "number"},
                "from_crs": {"type": "string", "description": "Source CRS: WGS84|GCJ02|CGCS2000"},
                "to_crs": {"type": "string", "description": "Target CRS: WGS84|GCJ02|CGCS2000"},
            },
            "required": ["lon", "lat", "from_crs", "to_crs"],
        },
    },
    # ═══ EIA Model Tools ═══
    {
        "name": "gaussian_plume",
        "description": "Gaussian plume dispersion per GB/T3840-1991. Q(mg/s),u(m/s),x(m),stability(A-F),He(m)",
        "inputSchema": {"type":"object","properties":{"Q":{"type":"number"},"u":{"type":"number"},"x":{"type":"number"},"stability":{"type":"string"},"y":{"type":"number"},"z":{"type":"number"},"He":{"type":"number"}},"required":["Q","u","x","stability"]},
    },
    {
        "name": "streeter_phelps",
        "description": "Streeter-Phelps DO sag curve. DO_sat(mg/L),k1(1/d),k2(1/d),L0(mg/L),t(d)",
        "inputSchema": {"type":"object","properties":{"DO_sat":{"type":"number"},"k1":{"type":"number"},"k2":{"type":"number"},"L0":{"type":"number"},"t":{"type":"number"}},"required":["DO_sat","k1","k2","L0","t"]},
    },
    {
        "name": "noise_iso9613",
        "description": "ISO 9613-2 noise prediction. Lw(dB),r(m),ground_type(soft|mixed|hard)",
        "inputSchema": {"type":"object","properties":{"Lw":{"type":"number"},"r":{"type":"number"},"ground_type":{"type":"string"}},"required":["Lw","r"]},
    },
    {
        "name": "co2_equivalent",
        "description": "CO2 equivalent IPCC GWP100. masses: {CO2:100,CH4:5,N2O:2}",
        "inputSchema": {"type":"object","properties":{"masses":{"type":"object"}},"required":["masses"]},
    },
    {
        "name": "hazard_quotient",
        "description": "Ecological Hazard Quotient. HQ = exposure / reference_dose",
        "inputSchema": {"type":"object","properties":{"exposure":{"type":"number"},"reference_dose":{"type":"number"}},"required":["exposure","reference_dose"]},
    },
    # ═══ API Map Tools ═══
    {
        "name": "search_apis",
        "description": "Search 1400+ free web APIs by keyword. Returns name, description, URL, auth type.",
        "inputSchema": {"type":"object","properties":{"query":{"type":"string"},"category":{"type":"string"}},"required":["query"]},
    },
    {
        "name": "call_api",
        "description": "Call any discovered web API by name with parameters. Returns structured data.",
        "inputSchema": {"type":"object","properties":{"name":{"type":"string"},"params":{"type":"object"},"method":{"type":"string"}},"required":["name"]},
    },
]


class MCPServer:
    """Model Context Protocol server for LivingTree.

    Implements the MCP JSON-RPC protocol over stdio.
    External AI tools connect via:
        {"mcpServers": {"livingtree": {"command": "python", "args": ["-m", "livingtree.mcp.server"]}}}
    """

    def __init__(self, hub=None):
        self._hub = hub
        self._code_graph = None

    async def handle_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Route an MCP method to the appropriate handler."""
        params = params or {}

        # Initialize hub lazily
        if self._hub is None and method != "initialize":
            try:
                from ..integration.hub import IntegrationHub
                self._hub = IntegrationHub()
                await self._hub.start()
            except Exception as e:
                logger.error(f"MCP hub init failed: {e}")
                return {"error": str(e)}

        # Initialize code graph lazily
        if self._code_graph is None and method.startswith(("build_", "blast_", "get_", "search_code", "find_")):
            try:
                from ..capability.code_graph import CodeGraph
                self._code_graph = CodeGraph()
                self._code_graph.load()
            except Exception:
                pass

        handlers = {
            # Code Graph
            "build_code_graph": self._build_graph,
            "blast_radius": self._blast_radius,
            "get_callers": self._get_callers,
            "get_callees": self._get_callees,
            "search_code": self._search_code,
            "find_hubs": self._find_hubs,
            "find_uncovered": self._find_uncovered,
            "code_incremental": self._code_incremental,
            "code_diff": self._code_diff,
            "code_impact": self._code_impact,
            # Chat
            "chat": self._chat,
            "analyze": self._analyze,
            "generate_report": self._generate_report,
            # Code Gen
            "generate_code": self._gen_code,
            "improve_code": self._improve_code,
            # Knowledge
            "search_knowledge": self._search_knowledge,
            "detect_knowledge_gaps": self._detect_gaps,
            "discover_formats": self._discover_formats,
            # Cell
            "train_cell": self._train_cell,
            "drill_train": self._drill_train,
            "absorb_codebase": self._absorb_codebase,
            # System
            "get_status": self._get_status,
            "get_metrics": self._get_metrics,
            "discover_peers": self._discover_peers,
            # LivingTree unique
            "lookup_standard": self._lookup_standard,
            "classify_water_quality": self._classify_water,
            "classify_air_quality": self._classify_air,
            "classify_noise_level": self._classify_noise,
            "redact_pii": self._redact_pii,
            "detect_outliers": self._detect_outliers,
            # Map/GIS tools
            "geocode": self._mcp_geocode,
            "buffer_query": self._mcp_buffer,
            "spatial_search": self._mcp_spatial_search,
            "distance_calc": self._mcp_distance,
            "coordinate_transform": self._mcp_coord_transform,
            # EIA models
            "gaussian_plume": self._mcp_gaussian_plume,
            "streeter_phelps": self._mcp_streeter_phelps,
            "noise_iso9613": self._mcp_noise_iso9613,
            "co2_equivalent": self._mcp_co2_equivalent,
            "hazard_quotient": self._mcp_hazard_quotient,
            # API Map
            "search_apis": self._mcp_search_apis,
            "call_api": self._mcp_call_api,
        }

        handler = handlers.get(method)
        if not handler:
            return {"error": f"Unknown method: {method}"}
        return await handler(params)

    async def list_tools(self) -> list[dict]:
        return TOOLS

    # ── Code Graph handlers ──

    async def _build_graph(self, params: dict) -> dict:
        path = params.get("path", ".")
        self._code_graph = self._code_graph or CodeGraph()
        stats = self._code_graph.index(path)
        self._code_graph.save()
        return {
            "files": stats.total_files, "entities": stats.total_entities,
            "edges": stats.total_edges, "languages": stats.languages,
            "build_time_ms": stats.build_time_ms,
        }

    async def _blast_radius(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built. Run build_code_graph first."}
        files = params.get("files", [])
        results = self._code_graph.blast_radius(files)
        return {"impacted": [{"file": r.file, "reason": r.reason, "risk": r.risk} for r in results]}

    async def _get_callers(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built."}
        callers = self._code_graph.get_callers(params["function_name"])
        return {"callers": [{"name": c.name, "file": c.file, "line": c.line} for c in callers]}

    async def _get_callees(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built."}
        callees = self._code_graph.get_callees(params["function_name"])
        return {"callees": callees}

    async def _search_code(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built."}
        results = self._code_graph.search(params["query"])
        return {"results": [{"name": e.name, "file": e.file, "kind": e.kind} for e in results[:20]]}

    async def _find_hubs(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built."}
        hubs = self._code_graph.find_hubs(params.get("top_n", 10))
        return {"hubs": [{"name": h.name, "file": h.file, "connections": len(h.dependents) + len(h.dependencies)} for h in hubs]}

    async def _find_uncovered(self, params: dict) -> dict:
        if not self._code_graph:
            return {"error": "No code graph built."}
        uncovered = self._code_graph.find_uncovered()
        return {"uncovered": [{"name": e.name, "file": e.file} for e in uncovered[:20]]}

    async def _code_incremental(self, params: dict) -> dict:
        """Self-calling: update CodeGraph from git diff — only re-parse changed files."""
        if not self._code_graph:
            return {"error": "No code graph built."}
        result = self._code_graph.incremental_update_from_git(
            params.get("base", "HEAD~1"), params.get("current", "HEAD"),
        )
        return result

    async def _code_diff(self, params: dict) -> dict:
        """Self-calling: show entity-level changes since last snapshot."""
        if not self._code_graph:
            return {"error": "No code graph built."}
        return self._code_graph.diff_export(
            params.get("base_snapshot", {}),
        )

    async def _code_impact(self, params: dict) -> dict:
        """Self-calling: compute numeric impact scores for changed files."""
        if not self._code_graph:
            return {"error": "No code graph built."}
        return {"scores": self._code_graph.impact_score(
            params.get("files", []), params.get("max_depth", 3),
        )}

    # ── Chat handlers ──

    async def _chat(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.chat(params["message"])

    async def _analyze(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        result = await self._hub.chat(f"请深度分析: {params['topic']}")
        return result

    async def _generate_report(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.generate_report(
            params["template_type"],
            params.get("data", {}),
        )

    # ── Code gen handlers ──

    async def _gen_code(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.generate_code(
            params["name"],
            params.get("description", ""),
            params.get("domain", "general"),
        )

    async def _improve_code(self, params: dict) -> dict:
        if not self._hub or not self._hub.world.code_engine:
            return {"error": "Code engine not available"}
        result = await self._hub.world.code_engine.improve_code(
            params["code"],
            params.get("requirements", {}),
        )
        return {"code": result.code, "annotations": result.annotations}

    # ── Knowledge handlers ──

    async def _search_knowledge(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        results = self._hub.world.knowledge_base.search(params["query"])
        return {"results": [{"title": d.title, "content": d.content[:200]} for d in results[:10]]}

    async def _detect_gaps(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        plan = self._hub.world.gap_detector.generate_learning_plan(self._hub.world.knowledge_base)
        return {"gaps": [{"domain": g.domain, "topic": g.topic, "priority": g.priority} for g in plan]}

    async def _discover_formats(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        template = self._hub.world.format_discovery.analyze_document(params["path"])
        return {"name": template.name, "formats": list(template.formats), "structure": template.structure}

    # ── Cell handlers ──

    async def _train_cell(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.train_cell(params["cell_name"], params.get("data", []))

    async def _drill_train(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.drill_train(
            params["cell_name"], params["model_name"],
            params.get("dataset", []), params.get("training_type", "lora"),
        )

    async def _absorb_codebase(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return await self._hub.absorb_github(params["path"])

    # ── System handlers ──

    async def _get_status(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return self._hub.status()

    async def _get_metrics(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        return self._hub.world.metrics.get_snapshot() if self._hub.world.metrics else {}

    async def _discover_peers(self, params: dict) -> dict:
        if not self._hub:
            return {"error": "Hub not available"}
        peers = await self._hub.discover_peers()
        return {"peers": peers}

    # ── LivingTree unique tool handlers ──

    async def _lookup_standard(self, params: dict) -> dict:
        try:
            from ..knowledge.engram_store import get_engram_store
            store = get_engram_store(seed=True)
            result = store.lookup(params["query"])
            if result:
                return {"found": True, "content": result, "source": "engram"}
            results = store.search(params["query"], top_k=5)
            return {"found": False, "search_results": results}
        except Exception as e:
            return {"error": str(e)}

    async def _classify_water(self, params: dict) -> dict:
        from ..capability.tabular_reasoner import get_tabular_reasoner
        r = get_tabular_reasoner()
        result = r.classify_water_quality(
            cod=float(params["cod"]), bod=float(params["bod"]),
            do=float(params["do"]), nh3n=float(params["nh3n"]))
        return {"grade": result.prediction, "confidence": result.confidence,
                "reasoning": result.reasoning}

    async def _classify_air(self, params: dict) -> dict:
        from ..capability.tabular_reasoner import get_tabular_reasoner
        r = get_tabular_reasoner()
        result = r.classify_air_quality(
            so2=float(params["so2"]), no2=float(params["no2"]),
            pm10=float(params["pm10"]), pm25=float(params["pm25"]))
        return {"grade": result.prediction, "confidence": result.confidence,
                "reasoning": result.reasoning}

    async def _classify_noise(self, params: dict) -> dict:
        from ..capability.tabular_reasoner import get_tabular_reasoner
        r = get_tabular_reasoner()
        result = r.classify_noise_level(
            daytime_db=float(params["daytime_db"]),
            night_db=float(params["night_db"]))
        return {"grade": result.prediction, "confidence": result.confidence,
                "reasoning": result.reasoning}

    async def _redact_pii(self, params: dict) -> dict:
        from ..knowledge.pii_redactor import get_pii_redactor
        r = get_pii_redactor()
        cleaned, findings = r.redact(params["text"])
        return {"redacted": cleaned, "findings_count": len(findings),
                "types_found": list(set(f.pii_type for f in findings))}

    async def _detect_outliers(self, params: dict) -> dict:
        from ..capability.tabular_reasoner import get_tabular_reasoner
        r = get_tabular_reasoner()
        values = [float(v) for v in params["values"]]
        outliers = r.detect_outliers(values)
        extreme = [o for o in outliers if o["severity"] == "extreme"]
        mild = [o for o in outliers if o["severity"] == "mild"]
        return {"total": len(values), "extreme_outliers": len(extreme),
                "mild_outliers": len(mild), "details": outliers}

    # ── Map/GIS handlers ──

    async def _mcp_geocode(self, params: dict) -> dict:
        from ..capability.tianditu import TiandituAPI
        api = TiandituAPI()
        result = await api.geocode(params["address"])
        return {"location": result} if result else {"error": "Geocoding failed"}

    async def _mcp_buffer(self, params: dict) -> dict:
        from ..treellm.spatial_analysis import get_spatial_engine
        engine = get_spatial_engine()
        geojson = engine.buffer(params["lon"], params["lat"], params["radius_m"])
        return {"geojson": geojson}

    async def _mcp_spatial_search(self, params: dict) -> dict:
        from ..treellm.spatial_analysis import get_spatial_engine
        engine = get_spatial_engine()
        inside = engine.point_in_polygon(params["lon"], params["lat"], params["polygon"])
        return {"inside": inside}

    async def _mcp_distance(self, params: dict) -> dict:
        from ..treellm.spatial_analysis import get_spatial_engine
        engine = get_spatial_engine()
        d = engine.distance_m(params["lon1"], params["lat1"], params["lon2"], params["lat2"])
        return {"distance_m": round(d, 1)}

    async def _mcp_coord_transform(self, params: dict) -> dict:
        from ..treellm.spatial_analysis import CoordinateTransform
        ct = CoordinateTransform()
        from_crs = params["from_crs"].upper()
        to_crs = params["to_crs"].upper()
        lon, lat = params["lon"], params["lat"]
        if from_crs == "WGS84" and to_crs == "GCJ02":
            lon, lat = ct.wgs84_to_gcj02(lon, lat)
        elif from_crs == "GCJ02" and to_crs == "WGS84":
            lon, lat = ct.gcj02_to_wgs84(lon, lat)
        elif from_crs == "WGS84" and to_crs == "CGCS2000":
            lon, lat = ct.wgs84_to_cgcs2000_3deg(lon, lat)
        return {"lon": round(lon, 6), "lat": round(lat, 6), "crs": to_crs}

    # ── EIA Model handlers ──

    async def _mcp_gaussian_plume(self, params: dict) -> dict:
        from ..treellm.eia_models import AtmosphericModels
        C = AtmosphericModels.gaussian_plume(
            params["Q"], params["u"], params["x"],
            params.get("y", 0), params.get("z", 0),
            params["stability"], params.get("He", 0),
        )
        return {"concentration_mg_m3": round(C, 6)}

    async def _mcp_streeter_phelps(self, params: dict) -> dict:
        from ..treellm.eia_models import WaterQualityModels
        DO = WaterQualityModels.streeter_phelps(
            params["DO_sat"], params["k1"], params["k2"],
            params["L0"], params.get("D0", 0), params["t"],
        )
        return {"DO_mg_L": round(DO, 4)}

    async def _mcp_noise_iso9613(self, params: dict) -> dict:
        from ..treellm.eia_models import NoiseModels
        Lp = NoiseModels.point_source(
            params["Lw"], params["r"], params.get("ground_type", "soft"),
        )
        return {"Lp_db": round(Lp, 1)}

    async def _mcp_co2_equivalent(self, params: dict) -> dict:
        from ..treellm.eia_models import CarbonGHGModels
        co2e = CarbonGHGModels.co2_equivalent(params["masses"])
        return {"co2e_tons": round(co2e, 2)}

    async def _mcp_hazard_quotient(self, params: dict) -> dict:
        from ..treellm.eia_models import EcologicalRiskModels
        hq = EcologicalRiskModels.hazard_quotient(
            params["exposure"], params["reference_dose"],
        )
        return {"HQ": round(hq, 3), "risk": "potential" if hq > 1 else "acceptable"}

    # ── API Map handlers ──

    async def _mcp_search_apis(self, params: dict) -> dict:
        from ..treellm.api_map import get_api_map
        results = get_api_map().search(params["query"], params.get("category", ""))
        return {"total": len(results), "apis": results}

    async def _mcp_call_api(self, params: dict) -> dict:
        from ..treellm.api_map import get_api_map
        result = await get_api_map().call(
            params["name"], params.get("params", {}),
            params.get("method", "GET"),
        )
        return {"data": result.data, "status_code": result.status_code,
                "elapsed_ms": round(result.elapsed_ms, 0),
                "cached": result.cached, "error": result.error}


async def serve_stdio(hub=None) -> None:
    """Run MCP server over stdio (JSON-RPC)."""
    server = MCPServer(hub)
    logger.info("LivingTree MCP Server starting on stdio")

    buffer = ""
    while True:
        try:
            chunk = sys.stdin.read(1)
            if not chunk:
                break
            buffer += chunk
            if buffer.strip().endswith("}"):
                try:
                    request = json.loads(buffer)
                    buffer = ""
                    method = request.get("method", "")
                    req_id = request.get("id")

                    if method == "tools/list":
                        tools = await server.list_tools()
                        response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
                    elif method == "tools/call":
                        tool_name = request.get("params", {}).get("name", "")
                        arguments = request.get("params", {}).get("arguments", {})
                        result = await server.handle_request(tool_name, arguments)
                        response = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]}}
                    elif method == "initialize":
                        response = {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "livingtree-mcp", "version": "2.0.0"}}}
                    else:
                        response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

                    sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
                    sys.stdout.flush()
                except json.JSONDecodeError:
                    pass
        except EOFError:
            break
        except Exception as e:
            logger.error(f"MCP error: {e}")


def main():
    """Entry point: python -m livingtree.mcp.server"""
    asyncio.run(serve_stdio())


if __name__ == "__main__":
    main()
