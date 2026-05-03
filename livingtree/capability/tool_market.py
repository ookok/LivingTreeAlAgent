"""ToolMarket — Dynamic tool discovery and registry.

No hardcoded tools (except fundamental physical constants).
Tools are discovered via:
1. SkillDiscoverer (Phage AST scan + SkillFactory)
2. KnowledgeBase (previously discovered)
3. Seed physical models (Pasquill-Gifford, Gaussian plume — physics, not templates)
"""

from __future__ import annotations

import math
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    type: str = "python"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    category: str = "general"
    rating: float = 0.0


class ToolMarket:
    """Dynamic tool registry. Tools discovered at runtime, not hardcoded."""

    def __init__(self, world: Any = None):
        self._tools: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Any] = {}
        self._world = world

    def set_world(self, world) -> None:
        self._world = world

    def register(self, name: str, description: str, category: str = "general",
                 input_schema: dict | None = None, handler: Any = None) -> None:
        spec = ToolSpec(name=name, description=description, type="python",
                        input_schema=input_schema or {}, category=category)
        self._tools[name] = spec
        if handler:
            self._handlers[name] = handler

    def discover(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def search(self, query: str) -> list[ToolSpec]:
        q = query.lower()
        return [t for t in self._tools.values()
                if q in t.name.lower() or q in t.description.lower()]

    async def execute(self, name: str, input_data: dict[str, Any]) -> Any:
        handler = self._handlers.get(name)
        if handler:
            try:
                import asyncio
                result = handler(input_data, world=self._world)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"Tool not found: {name}"}


# ── Fundamental physical models (not templates — laws of nature) ──

def _gaussian_plume(params: dict, world: Any = None) -> dict:
    """Gaussian plume dispersion — fundamental physics, not learned."""
    Q, u, x = params["Q"], params["u"], params["x"]
    y, z = params.get("y", 0), params.get("z", 0)
    stability = params.get("stability", "D")
    He = params.get("He", 0)
    coef = {"A": (0.527, 0.865, 0.28, 0.90), "B": (0.371, 0.866, 0.23, 0.85),
            "C": (0.209, 0.897, 0.22, 0.80), "D": (0.128, 0.905, 0.20, 0.76),
            "E": (0.098, 0.902, 0.15, 0.73), "F": (0.065, 0.902, 0.12, 0.67)}
    g = coef.get(stability, coef["D"])
    sy = g[0] * x ** g[1]; sz = g[2] * x ** g[3]
    if sy <= 0 or sz <= 0 or u <= 0:
        return {"error": "Invalid parameters"}
    C = Q / (2 * math.pi * sy * sz * u) * math.exp(-y**2 / (2 * sy**2))
    C *= (math.exp(-(z - He)**2 / (2 * sz**2)) + math.exp(-(z + He)**2 / (2 * sz**2)))
    return {"C_mgm3": round(C * 1000, 6), "sy_m": round(sy, 2), "sz_m": round(sz, 2),
            "stability": stability, "model": "gaussian_plume"}


def _noise_attenuation(params: dict, world: Any = None) -> dict:
    """Noise attenuation — physical law, not learned."""
    Lw, r = params["Lw"], params["r"]
    Agr = 5 * (1 - math.exp(-r / 50)) if params.get("ground_type") == "soft" else 0
    Lp = Lw - 20 * math.log10(max(r, 0.1)) - 11 - Agr
    return {"Lp_dB": round(Lp, 2), "model": "noise_attenuation"}


def _dispersion_coeff(params: dict, world: Any = None) -> dict:
    """Pasquill-Gifford coefficients — fundamental standard, not learned."""
    x = params["x"]; s = params.get("stability", "D")
    c = {"A": (0.527,0.865,0.28,0.90),"B":(0.371,0.866,0.23,0.85),"C":(0.209,0.897,0.22,0.80),
         "D":(0.128,0.905,0.20,0.76),"E":(0.098,0.902,0.15,0.73),"F":(0.065,0.902,0.12,0.67)}
    g=c.get(s,c["D"]); return {"sy":round(g[0]*x**g[1],2),"sz":round(g[2]*x**g[3],2),"standard":"GB/T3840-1991"}


def register_seed_tools(market: ToolMarket) -> int:
    """Register only fundamental physical models as seed tools."""
    seeds = [
        ("gaussian_plume", "Gaussian plume dispersion model", "model",
         {"properties": {"Q":{"type":"number"},"u":{"type":"number"},"x":{"type":"number"}},
          "required": ["Q","u","x"]}, _gaussian_plume),
        ("noise_attenuation", "Noise attenuation GB12348-2008", "model",
         {"properties": {"Lw":{"type":"number"},"r":{"type":"number"}},
          "required": ["Lw","r"]}, _noise_attenuation),
        ("dispersion_coeff", "Pasquill-Gifford stability coefficients", "model",
         {"properties": {"x":{"type":"number"}}, "required": ["x"]}, _dispersion_coeff),
    ]
    for name, desc, cat, schema, handler in seeds:
        market.register(name, desc, cat, schema, handler)
    logger.info(f"ToolMarket: {len(seeds)} seed physics models registered")
    return len(seeds)
