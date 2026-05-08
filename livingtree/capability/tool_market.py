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


def _generate_diagram(params: dict, world: Any = None) -> dict:
    """Generate ASCII flowchart/diagram from natural language via LLM."""
    description = params.get("description", "")
    if not description:
        return {"error": "description required"}
    if not world or not world.consciousness:
        return {"diagram": _basic_diagram(description), "source": "template"}

    try:
        import asyncio, json, aiohttp
        loop = asyncio.get_event_loop()
        async def _gen():
            if hasattr(world, 'config'):
                api_key = world.config.model.deepseek_api_key
                base_url = world.config.model.deepseek_base_url
                model = world.config.model.flash_model
                headers = {"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}
                payload = {
                    "model": model,
                    "messages": [{"role":"system","content":(
                        "Generate a text diagram using ASCII box-drawing characters.\n"
                        "Use ┌─┐│└─┘├┤┬┴┼ for boxes and → for arrows.\n"
                        "Output ONLY the diagram, no explanations.\n"
                        "Types: flowchart, sequence, architecture, tree, table."
                    )},{"role":"user","content": f"Generate a diagram for: {description}"}],
                    "temperature":0.3,"max_tokens":2048,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{base_url}/v1/chat/completions",
                        headers=headers,json=payload,timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
            return _basic_diagram(description)
        diagram = loop.run_until_complete(_gen())
        diagram_type = _detect_diagram_type(description)
        return {"diagram": diagram, "source": "llm", "type": diagram_type}
    except Exception as e:
        return {"diagram": _basic_diagram(description), "source": "template", "error": str(e)}


def _basic_diagram(desc: str) -> str:
    """Minimal fallback diagram when LLM unavailable."""
    return (
        f"┌─────────────────────┐\n"
        f"│     {desc[:30]:<30s}   │\n"
        f"└──────────┬──────────┘\n"
        f"           │\n"
        f"           ▼\n"
        f"┌─────────────────────┐\n"
        f"│   Process / Analyze  │\n"
        f"└──────────┬──────────┘\n"
        f"           │\n"
        f"           ▼\n"
        f"┌─────────────────────┐\n"
        f"│      Output / Result │\n"
        f"└─────────────────────┘\n"
    )


def _detect_diagram_type(desc: str) -> str:
    d = desc.lower()
    for kw, tp in [("流程", "flowchart"), ("架构", "architecture"), ("时序", "sequence"),
                   ("树", "tree"), ("表", "table"), ("组件", "component")]:
        if kw in d:
            return tp
    return "flowchart"


def register_seed_tools(market: ToolMarket) -> None:
    """Register fundamental physical models and platform capabilities."""
    market.register("gaussian_plume", "Gaussian plume dispersion model (EIA)",
                    category="physics", handler=_gaussian_plume,
                    input_schema={"Q": "number", "u": "number", "x": "number",
                                  "y": "number", "z": "number", "stability": "string",
                                  "He": "number"})
    market.register("noise_attenuation", "Noise attenuation distance model",
                    category="physics", handler=_noise_attenuation,
                    input_schema={"Lw": "number", "r": "number", "ground_type": "string"})
    market.register("dispersion_coeff",
                    "Pasquill-Gifford dispersion coefficients (GB/T3840-1991)",
                    category="physics", handler=_dispersion_coeff,
                    input_schema={"x": "number", "stability": "string"})
    market.register("generate_diagram", "Generate ASCII diagram from description",
                    category="visualization", handler=_generate_diagram,
                    input_schema={"description": "string"})
    market.register("tabular_reason", "In-context tabular data classification and analysis",
                    category="data", handler=_tabular_reason,
                    input_schema={"cod": "number", "bod": "number", "do": "number",
                                  "nh3n": "number", "task": "string"})

    # ── Browser tools: LLM discovers and orchestrates autonomously ──
    try:
        from .browser_tools import register_browser_tools
        register_browser_tools(market)
    except Exception as e:
        logger.debug("Browser tools not registered: %s", e)


def _tabular_reason(inputs: dict) -> dict:
    """In-context tabular reasoning: classify water/air quality, detect outliers."""
    from .tabular_reasoner import get_tabular_reasoner
    reasoner = get_tabular_reasoner()
    task = inputs.get("task", "classify_water_quality")
    if task == "classify_water_quality":
        result = reasoner.classify_water_quality(
            cod=float(inputs.get("cod", 0)), bod=float(inputs.get("bod", 0)),
            do=float(inputs.get("do", 0)), nh3n=float(inputs.get("nh3n", 0)))
    elif task == "classify_air_quality":
        result = reasoner.classify_air_quality(
            so2=float(inputs.get("so2", 0)), no2=float(inputs.get("no2", 0)),
            pm10=float(inputs.get("pm10", 0)), pm25=float(inputs.get("pm25", 0)))
    elif task == "classify_noise":
        result = reasoner.classify_noise_level(
            daytime_db=float(inputs.get("daytime_db", 0)),
            night_db=float(inputs.get("night_db", 0)))
    elif task == "detect_outliers":
        values = inputs.get("values", [])
        outliers = reasoner.detect_outliers(values)
        return {"outliers": outliers, "count": sum(1 for o in outliers if o["is_outlier"])}
    else:
        return {"error": f"Unknown task: {task}"}
    return {"prediction": result.prediction, "confidence": result.confidence,
            "reasoning": result.reasoning}


