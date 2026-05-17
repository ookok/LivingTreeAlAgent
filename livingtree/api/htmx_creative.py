"""HTMX Creative routes — garden, timeline, dreams, emotions, swarm, weather."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

creative_router = APIRouter(prefix="/creative", tags=["creative"])

@creative_router.get("/creative/garden")
async def tree_creative_garden(request: Request):
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌿 对话花园</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">每个重要时刻都会长成一株植物。这是小树对你的记忆。</p>'
        + p.build_garden() + '</div>')


@creative_router.get("/creative/timeline")
async def tree_creative_timeline(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is None:
        return HTMLResponse('<div class="card"><h2>⏳ AI 记忆时间线</h2><p style="color:var(--dim)">系统未就绪</p></div>')
    cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>⏳ AI 记忆时间线</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">滚动浏览小树生命中每一个决策、学习和情感时刻</p>'
        + cv.build_timeline() + '</div>')

@creative_router.get("/creative/dream")
async def tree_creative_dream(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌙 梦境引擎</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">空闲时小树在重组知识、发现隐藏连接</p>'
        + cv.build_dream_canvas() + '</div>')

@creative_router.get("/creative/swarm")
async def tree_creative_swarm(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🗺️ 群体地图</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">所有连接节点的地理位置和能力分布</p>'
        + cv.build_swarm_map() + '</div>')

@creative_router.get("/creative/emotion")
async def tree_creative_emotion(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>💭 情绪仪表</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">VAD 三维情感向量实时追踪</p>'
        + cv.build_emotion_gauge() + '</div>')

@creative_router.get("/creative/weather")
async def tree_creative_weather(request: Request):
    from ..core.creative_viz import build_knowledge_weather_map
    from ..dna.emergence_detector import get_phase_detector
    phase_data = get_phase_detector().stats()
    return HTMLResponse(build_knowledge_weather_map(phase_data))

# ═══ Admin Model Dashboard ═══

# Admin routes extracted to htmx_admin.py

# ═══════════════════════════════════════════════════════════════
#  P7: Task decomposition tree — live SSE visualization
# ═══════════════════════════════════════════════════════════════


__all__ = ["creative_router"]
