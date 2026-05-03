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
    """Route to appropriate template based on description type."""
    dtype = _detect_diagram_type(desc)
    if dtype == "eia_process":
        return _eia_process_diagram(desc)
    if dtype == "emergency":
        return _emergency_diagram(desc)
    if dtype == "monitoring":
        return _monitoring_diagram(desc)
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
    kw = desc.lower()
    if any(w in kw for w in ["环评","eia","环境影响","污染","排放"]): return "eia_process"
    if any(w in kw for w in ["应急","emergency","事故","预案"]): return "emergency"
    if any(w in kw for w in ["监测","monitoring","采样"]): return "monitoring"
    if any(w in kw for w in ["时序","sequence","uml"]): return "sequence"
    if any(w in kw for w in ["架构","architecture","系统"]): return "architecture"
    if any(w in kw for w in ["树","tree","层级","组织"]): return "tree"
    if any(w in kw for w in ["表","table","数据"]): return "table"
    return "flowchart"


def _eia_process_diagram(desc: str) -> str:
    """Generate EIA-specific process flow diagram."""
    return (
        f"                     {desc[:40]}\n"
        f"                         │\n"
        f"                         ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│              1. 项目工程分析                  │\n"
        f"│  · 原辅材料消耗  · 生产设备  · 工艺流程       │\n"
        f"└────────────────────┬─────────────────────────┘\n"
        f"                     │\n"
        f"                     ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│              2. 污染源强核算                  │\n"
        f"│  ┌──────────┐ ┌──────────┐ ┌──────────┐      │\n"
        f"│  │ 废气G1-Gn │ │ 废水W1-Wn │ │ 噪声N1-Nn │      │\n"
        f"│  └─────┬────┘ └─────┬────┘ └─────┬────┘      │\n"
        f"└────────┼─────────────┼─────────────┼──────────┘\n"
        f"         │             │             │\n"
        f"         ▼             ▼             ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│           3. 污染防治措施                     │\n"
        f"│  · 废气处理工艺  · 废水处理站  · 降噪措施     │\n"
        f"└────────────────────┬─────────────────────────┘\n"
        f"                     │\n"
        f"                     ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│           4. 环境影响预测与评价               │\n"
        f"│  · 大气扩散模拟  · 水环境预测  · 噪声预测     │\n"
        f"│  · 固体废物影响  · 生态影响  · 环境风险       │\n"
        f"└────────────────────┬─────────────────────────┘\n"
        f"                     │\n"
        f"                     ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│           5. 环境管理与监测计划               │\n"
        f"│  · 监测点位布设  · 监测因子  · 监测频次       │\n"
        f"└────────────────────┬─────────────────────────┘\n"
        f"                     │\n"
        f"                     ▼\n"
        f"┌──────────────────────────────────────────────┐\n"
        f"│           6. 结论与建议                       │\n"
        f"│  · 评价结论  · 环保措施  · 改进建议           │\n"
        f"└──────────────────────────────────────────────┘\n"
    )


def _emergency_diagram(desc: str) -> str:
    """Generate emergency response flowchart."""
    return (
        f"                  {desc[:30]}\n"
        f"                      │\n"
        f"                      ▼\n"
        f"          ┌───────────────────┐\n"
        f"          │   事故/风险发生    │\n"
        f"          └────────┬──────────┘\n"
        f"                   │\n"
        f"                   ▼\n"
        f"          ┌───────────────────┐\n"
        f"          │   1. 风险识别      │\n"
        f"          │   物质/设施/类型   │\n"
        f"          └────────┬──────────┘\n"
        f"                   │\n"
        f"        ┌──────────┼──────────┐\n"
        f"        ▼          ▼          ▼\n"
        f"  ┌──────────┐ ┌────────┐ ┌──────────┐\n"
        f"  │ 2.应急响应│ │3.疏散  │ │4.应急监测│\n"
        f"  │ 分级启动  │ │ 撤离   │ │ 布点采样 │\n"
        f"  └────┬─────┘ └───┬────┘ └────┬─────┘\n"
        f"       └───────────┼───────────┘\n"
        f"                   ▼\n"
        f"          ┌───────────────────┐\n"
        f"          │   5. 后期处置      │\n"
        f"          │   善后/调查/恢复   │\n"
        f"          └───────────────────┘\n"
    )


def _monitoring_diagram(desc: str) -> str:
    """Generate environmental monitoring flowchart."""
    return (
        f"              {desc[:30]}\n"
        f"                  │\n"
        f"                  ▼\n"
        f"  ┌─────────────────────────────────┐\n"
        f"  │        监测方案制定              │\n"
        f"  │  点位/因子/频次/方法             │\n"
        f"  └───────────────┬─────────────────┘\n"
        f"                  │\n"
        f"     ┌────────────┼────────────┐\n"
        f"     ▼            ▼            ▼\n"
        f"  ┌──────┐   ┌──────┐    ┌──────┐\n"
        f"  │ 大气  │   │ 水环境│    │ 噪声  │\n"
        f"  │TSP/PM │   │COD/NH │    │Leq dB│\n"
        f"  │SO2/NOx│   │pH/重金属│   │L10/L90│\n"
        f"  └──┬───┘   └──┬───┘    └──┬───┘\n"
        f"     └──────────┼───────────┘\n"
        f"                ▼\n"
        f"  ┌─────────────────────────────────┐\n"
        f"  │        数据分析与评价            │\n"
        f"  │  达标分析 / 趋势分析 / 对比评价   │\n"
        f"  └───────────────┬─────────────────┘\n"
        f"                  │\n"
        f"                  ▼\n"
        f"  ┌─────────────────────────────────┐\n"
        f"  │        监测报告编制              │\n"
        f"  │  结论 / 建议 / 附件              │\n"
        f"  └─────────────────────────────────┘\n"
    )


def _basic_diagram(desc: str) -> str:
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


def register_seed_tools(market: ToolMarket) -> int:
    seeds = [
        ("gaussian_plume", "Gaussian plume dispersion model", "model",
         {"properties": {"Q":{"type":"number"},"u":{"type":"number"},"x":{"type":"number"}},
          "required": ["Q","u","x"]}, _gaussian_plume),
        ("noise_attenuation", "Noise attenuation GB12348-2008", "model",
         {"properties": {"Lw":{"type":"number"},"r":{"type":"number"}},
          "required": ["Lw","r"]}, _noise_attenuation),
        ("dispersion_coeff", "Pasquill-Gifford stability coefficients", "model",
         {"properties": {"x":{"type":"number"}}, "required": ["x"]}, _dispersion_coeff),
        ("generate_diagram", "Generate ASCII diagram from natural language (flowchart/sequence/architecture/tree/table)", "diagram",
         {"properties": {"description": {"type": "string", "description": "Natural language description of the diagram"}},
          "required": ["description"]}, _generate_diagram),
    ]
    for name, desc, cat, schema, handler in seeds:
        market.register(name, desc, cat, schema, handler)
    logger.info(f"ToolMarket: {len(seeds)} seed physics models registered")
    return len(seeds)
