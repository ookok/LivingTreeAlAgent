"""LocalToolBus — 本地直接调用替代 MCP 子进程协议。

MCP (Model Context Protocol) 是给 Claude Code/Cursor 等外部工具的接口，
但 LivingTree 内部调用可以通过 LocalToolBus 直接调用 handler，无需子进程开销。

Architecture:
  - 所有 MCP 工具同时注册为本地 handler
  - CapabilityBus 优先走本地调用，外部工具走 MCP 子进程
  - 本地调用：直接 Python 方法调用，<1ms
  - MCP 调用：subprocess + JSON-RPC，100ms+
  - 工具实现写一次，两处可用

Integration:
  bus = get_local_tool_bus()
  result = await bus.invoke("classify_water_quality", cod=30, bod=6, do=5, nh3n=1.5)
  result = await bus.invoke("gaussian_plume", Q=100, u=2, x=500, stability="D")
  result = await bus.invoke("build_code_graph", path=".")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class LocalToolResult:
    success: bool = True
    data: Any = None
    error: str = ""
    elapsed_ms: float = 0.0


class LocalToolBus:
    """Direct-invoke bus for ALL MCP/local tools — zero subprocess overhead.

    Every tool that appears in MCPServer.TOOLS is also directly callable here.
    No subprocess, no JSON-RPC, no serialization. Direct Python call.
    """

    _instance: Optional["LocalToolBus"] = None

    @classmethod
    def instance(cls) -> "LocalToolBus":
        if cls._instance is None:
            cls._instance = LocalToolBus()
        return cls._instance

    def __init__(self):
        self._registry: dict[str, Any] = {}
        self._invoke_count: int = 0
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register ALL 43 built-in tool handlers for direct local invocation."""
        # ── Code Graph (10 tools) ──
        self._registry["build_code_graph"] = self._code_build_graph
        self._registry["blast_radius"] = self._code_blast_radius
        self._registry["get_callers"] = self._code_get_callers
        self._registry["get_callees"] = self._code_get_callees
        self._registry["search_code"] = self._code_search
        self._registry["find_hubs"] = self._code_find_hubs
        self._registry["find_uncovered"] = self._code_find_uncovered
        self._registry["code_incremental"] = self._code_incremental
        self._registry["code_diff"] = self._code_diff
        self._registry["code_impact"] = self._code_impact

        # ── LivingTree unique (6 tools) ──
        self._registry["lookup_standard"] = self._lookup_standard
        self._registry["classify_water_quality"] = self._classify_water
        self._registry["classify_air_quality"] = self._classify_air
        self._registry["classify_noise_level"] = self._classify_noise
        self._registry["redact_pii"] = self._redact_pii
        self._registry["detect_outliers"] = self._detect_outliers

        # ── EIA Models (5 tools) ──
        self._registry["gaussian_plume"] = self._gaussian_plume
        self._registry["streeter_phelps"] = self._streeter_phelps
        self._registry["noise_iso9613"] = self._noise_iso9613
        self._registry["co2_equivalent"] = self._co2_equivalent
        self._registry["hazard_quotient"] = self._hazard_quotient

        # ── Map/GIS (5 tools) ──
        self._registry["geocode"] = self._geocode
        self._registry["buffer_query"] = self._buffer_query
        self._registry["spatial_search"] = self._spatial_search
        self._registry["distance_calc"] = self._distance_calc
        self._registry["coordinate_transform"] = self._coordinate_transform

        # ── API Map (2 tools) ──
        self._registry["search_apis"] = self._search_apis
        self._registry["call_api"] = self._call_api

        # ── CLI Anything (4 tools) ──
        self._registry["cli_wrap_function"] = self._cli_wrap
        self._registry["cli_from_repo"] = self._cli_from_repo
        self._registry["cli_from_manifest"] = self._cli_from_manifest
        self._registry["cli_list_tools"] = self._cli_list

    def register(self, name: str, handler) -> None:
        self._registry[name] = handler

    def unregister(self, name: str) -> None:
        self._registry.pop(name, None)

    async def invoke(self, name: str, **params) -> LocalToolResult:
        """Direct invoke — no subprocess, no JSON-RPC."""
        import time
        t0 = time.time()
        handler = self._registry.get(name)
        if handler is None:
            return LocalToolResult(success=False, error=f"Unknown tool: {name}")

        self._invoke_count += 1
        try:
            result = handler(**params)
            if asyncio.iscoroutine(result):
                result = await result
            return LocalToolResult(
                success=True, data=result,
                elapsed_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            logger.debug(f"LocalToolBus invoke {name}: {e}")
            return LocalToolResult(
                success=False, error=str(e)[:500],
                elapsed_ms=(time.time() - t0) * 1000,
            )

    def list_all(self) -> list[str]:
        return sorted(self._registry.keys())

    def has(self, name: str) -> bool:
        return name in self._registry

    def stats(self) -> dict:
        return {"tools": len(self._registry), "invocations": self._invoke_count}

    # ═══════════════════════════════════════════════════════════════
    # Tool Handlers (extracted from MCPServer for direct invocation)
    # ═══════════════════════════════════════════════════════════════

    # ── Code Graph ──────────────────────────────────────────────

    def _ensure_code_graph(self):
        try:
            from ..capability.code_graph import CodeGraph
            cg = CodeGraph()
            cg.load()
            return cg
        except Exception as e:
            logger.debug(f"CodeGraph init: {e}")
            return None

    async def _code_build_graph(self, path: str = ".", **kw) -> dict:
        try:
            from ..capability.code_graph import CodeGraph
            cg = CodeGraph()
            stats = cg.index(path)
            cg.save()
            return {"files": stats.total_files, "entities": stats.total_entities,
                    "edges": stats.total_edges, "languages": stats.languages}
        except Exception as e:
            return {"error": str(e)}

    async def _code_blast_radius(self, files=None, **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        results = cg.blast_radius(files or [])
        return {"impacted": [{"file": r.file, "reason": r.reason} for r in results]}

    async def _code_get_callers(self, function_name: str = "", **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        callers = cg.get_callers(function_name)
        return {"callers": [{"name": c.name, "file": c.file} for c in callers]}

    async def _code_get_callees(self, function_name: str = "", **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        return {"callees": cg.get_callees(function_name)}

    async def _code_search(self, query: str = "", **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        results = cg.search(query)
        return {"results": [{"name": e.name, "file": e.file} for e in results[:20]]}

    async def _code_find_hubs(self, top_n: int = 10, **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        hubs = cg.find_hubs(top_n)
        return {"hubs": [{"name": h.name, "connections": len(h.dependents) + len(h.dependencies)} for h in hubs]}

    async def _code_find_uncovered(self, **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        uncovered = cg.find_uncovered()
        return {"uncovered": [{"name": e.name, "file": e.file} for e in uncovered[:20]]}

    async def _code_incremental(self, base: str = "HEAD~1", current: str = "HEAD", **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        return cg.incremental_update_from_git(base, current)

    async def _code_diff(self, base_snapshot: dict = None, **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        return cg.diff_export(base_snapshot or {})

    async def _code_impact(self, files=None, max_depth: int = 3, **kw) -> dict:
        cg = self._ensure_code_graph()
        if not cg:
            return {"error": "No code graph built"}
        return {"scores": cg.impact_score(files or [], max_depth)}

    # ── LivingTree Unique ──────────────────────────────────────

    async def _lookup_standard(self, query: str = "", **kw) -> dict:
        try:
            from ..knowledge.learning_sources import get_learning_sources
            return {"result": get_learning_sources().lookup_standard(query)}
        except Exception as e:
            return {"error": str(e)}

    async def _classify_water(self, cod: float = 0, bod: float = 0,
                               do: float = 0, nh3n: float = 0, **kw) -> dict:
        try:
            from ..capability.tabular_reasoner import get_tabular_reasoner
            r = get_tabular_reasoner()
            result = r.classify_water_quality(cod=cod, bod=bod, do=do, nh3n=nh3n)
            return {"grade": result.prediction, "confidence": result.confidence,
                    "reasoning": result.reasoning}
        except Exception as e:
            return {"error": str(e)}

    async def _classify_air(self, so2: float = 0, no2: float = 0,
                             pm10: float = 0, pm25: float = 0, **kw) -> dict:
        try:
            from ..capability.tabular_reasoner import get_tabular_reasoner
            r = get_tabular_reasoner()
            result = r.classify_air_quality(so2=so2, no2=no2, pm10=pm10, pm25=pm25)
            return {"grade": result.prediction, "confidence": result.confidence,
                    "reasoning": result.reasoning}
        except Exception as e:
            return {"error": str(e)}

    async def _classify_noise(self, daytime_db: float = 0,
                               night_db: float = 0, **kw) -> dict:
        try:
            from ..capability.tabular_reasoner import get_tabular_reasoner
            r = get_tabular_reasoner()
            result = r.classify_noise_level(daytime_db=daytime_db, night_db=night_db)
            return {"grade": result.prediction, "confidence": result.confidence,
                    "reasoning": result.reasoning}
        except Exception as e:
            return {"error": str(e)}

    async def _redact_pii(self, text: str = "", **kw) -> dict:
        try:
            from ..knowledge.pii_redactor import get_pii_redactor
            r = get_pii_redactor()
            cleaned, findings = r.redact(text)
            return {"redacted": cleaned, "findings_count": len(findings),
                    "types_found": list(set(f.pii_type for f in findings))}
        except Exception as e:
            return {"error": str(e), "redacted": text}

    async def _detect_outliers(self, values=None, **kw) -> dict:
        try:
            from ..capability.tabular_reasoner import get_tabular_reasoner
            r = get_tabular_reasoner()
            vals = [float(v) for v in (values or [])]
            outliers = r.detect_outliers(vals)
            extreme = [o for o in outliers if o["severity"] == "extreme"]
            mild = [o for o in outliers if o["severity"] == "mild"]
            return {"total": len(vals), "extreme_outliers": len(extreme),
                    "mild_outliers": len(mild), "details": outliers}
        except Exception as e:
            return {"error": str(e)}

    # ── EIA Models ─────────────────────────────────────────────

    async def _gaussian_plume(self, Q: float = 0, u: float = 0, x: float = 0,
                               stability: str = "D", y: float = 0, z: float = 0,
                               He: float = 0, **kw) -> dict:
        try:
            from .eia_models import AtmosphericModels
            result = AtmosphericModels.gaussian_plume(Q, u, x, y, z, He, stability)
            return {"concentration": result.concentration, "effective_height": result.effective_height}
        except Exception as e:
            return {"error": str(e)}

    async def _streeter_phelps(self, DO_sat: float = 0, k1: float = 0,
                                k2: float = 0, L0: float = 0, t: float = 0, **kw) -> dict:
        try:
            from .eia_models import WaterQualityModels
            result = WaterQualityModels.streeter_phelps(DO_sat, k1, k2, L0, t)
            return {"DO": result.DO, "BOD": result.BOD, "deficit": result.deficit}
        except Exception as e:
            return {"error": str(e)}

    async def _noise_iso9613(self, Lw: float = 0, r: float = 0,
                              ground_type: str = "mixed", **kw) -> dict:
        try:
            from .eia_models import NoiseModels
            result = NoiseModels.iso9613(Lw, r, ground_type)
            return result if isinstance(result, dict) else {"Lp": result}
        except Exception as e:
            return {"error": str(e)}

    async def _co2_equivalent(self, masses: dict = None, **kw) -> dict:
        try:
            from .eia_models import CarbonGHGModels
            return {"total_CO2e": CarbonGHGModels.co2_equivalent(masses or {})}
        except Exception as e:
            return {"error": str(e)}

    async def _hazard_quotient(self, exposure: float = 0,
                                reference_dose: float = 0, **kw) -> dict:
        try:
            from .eia_models import EcologicalRiskModels
            result = EcologicalRiskModels.hazard_quotient(exposure, reference_dose)
            return {"HQ": round(result, 3), "risk": "potential" if result > 1 else "acceptable"}
        except Exception as e:
            return {"error": str(e)}

    # ── GIS / Spatial ─────────────────────────────────────────

    async def _geocode(self, address: str = "", **kw) -> dict:
        try:
            from ..capability.tianditu import TiandituAPI
            api = TiandituAPI()
            result = await api.geocode(address)
            return {"location": result} if result else {"error": "Geocoding failed"}
        except Exception as e:
            return {"error": str(e)}

    async def _buffer_query(self, lon: float = 0, lat: float = 0,
                             radius_m: float = 0, **kw) -> dict:
        try:
            from .spatial_analysis import get_spatial_engine
            engine = get_spatial_engine()
            geojson = engine.buffer(lon, lat, radius_m)
            return {"geojson": geojson}
        except Exception as e:
            return {"error": str(e)}

    async def _spatial_search(self, lon: float = 0, lat: float = 0,
                               polygon: dict = None, **kw) -> dict:
        try:
            from .spatial_analysis import get_spatial_engine
            engine = get_spatial_engine()
            inside = engine.point_in_polygon(lon, lat, polygon or {})
            return {"inside": inside}
        except Exception as e:
            return {"error": str(e)}

    async def _distance_calc(self, lon1: float = 0, lat1: float = 0,
                              lon2: float = 0, lat2: float = 0, **kw) -> dict:
        try:
            from .spatial_analysis import get_spatial_engine
            engine = get_spatial_engine()
            dist = engine.haversine_distance(lon1, lat1, lon2, lat2)
            return {"distance_m": dist}
        except Exception as e:
            return {"error": str(e)}

    async def _coordinate_transform(self, lon: float = 0, lat: float = 0,
                                     from_crs: str = "WGS84",
                                     to_crs: str = "GCJ02", **kw) -> dict:
        try:
            from .spatial_analysis import get_spatial_engine
            engine = get_spatial_engine()
            result = engine.transform(lon, lat, from_crs, to_crs)
            return result if isinstance(result, dict) else {"lon": result[0], "lat": result[1]}
        except Exception as e:
            return {"error": str(e)}

    # ── API Map ───────────────────────────────────────────────

    async def _search_apis(self, query: str = "", category: str = "", **kw) -> dict:
        try:
            from .api_map import get_api_map
            results = get_api_map().search(query, category)
            return {"total": len(results), "apis": results}
        except Exception as e:
            return {"error": str(e)}

    async def _call_api(self, name: str = "", params: dict = None,
                         method: str = "GET", **kw) -> dict:
        try:
            from .api_map import get_api_map
            result = await get_api_map().call(name, params or {}, method)
            return {"data": result.data, "status_code": result.status_code,
                    "elapsed_ms": round(result.elapsed_ms, 0), "error": result.error}
        except Exception as e:
            return {"error": str(e)}

    # ── CLI Anything ──────────────────────────────────────────

    async def _cli_wrap(self, function_name: str = "", description: str = "",
                          params_json: str = "[]", **kw) -> dict:
        try:
            import json as _json
            from .cli_anything import get_cli_anything, CLIParam
            cli = get_cli_anything()
            try:
                param_list = _json.loads(params_json)
            except Exception:
                param_list = []
            cli_params = [
                CLIParam(name=p["name"], type=p.get("type", "str"),
                          description=p.get("description", ""),
                          required=p.get("required", False),
                          default=p.get("default"))
                for p in param_list
            ]
            path = cli.wrap_python_func(function_name, description, cli_params)
            return {"status": "created", "path": str(path), "function": function_name}
        except Exception as e:
            return {"error": str(e)}

    async def _cli_from_repo(self, repo_url: str = "",
                              entry_point: str = "", **kw) -> dict:
        try:
            from .cli_anything import get_cli_anything
            cli = get_cli_anything()
            definition = await cli.from_git_repo(repo_url, entry_point)
            return {"name": definition.name, "version": definition.version,
                    "commands": [c.name for c in definition.commands]}
        except Exception as e:
            return {"error": str(e)}

    async def _cli_from_manifest(self, yaml_path: str = "", **kw) -> dict:
        try:
            from .cli_anything import get_cli_anything
            cli = get_cli_anything()
            definition = cli.from_manifest(yaml_path)
            return {"name": definition.name, "commands": [c.name for c in definition.commands]}
        except Exception as e:
            return {"error": str(e)}

    async def _cli_list(self, **kw) -> dict:
        try:
            from .cli_anything import get_cli_anything
            return get_cli_anything().stats()
        except Exception as e:
            return {"error": str(e)}


_bus: Optional[LocalToolBus] = None


def get_local_tool_bus() -> LocalToolBus:
    global _bus
    if _bus is None:
        _bus = LocalToolBus()
    return _bus


__all__ = ["LocalToolBus", "LocalToolResult", "get_local_tool_bus"]
