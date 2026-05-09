"""HTMX Web Layer — hypermedia-driven UI for 小树 (Tree of Life).

Replaces static SPA with server-rendered Jinja2 templates + HTMX.
Zero JavaScript framework needed. Progressive enhancement.

Routes:
  GET  /tree          → main dashboard
  GET  /tree/chat     → chat interface  
  GET  /tree/health   → health panel (polled)
  GET  /tree/sse      → SSE stream of 小树's heartbeats
  POST /tree/chat/msg → chat message → HTML fragment
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

htmx_router = APIRouter(prefix="/tree", tags=["htmx"])


@htmx_router.get("", response_class=HTMLResponse)
@htmx_router.get("/", response_class=HTMLResponse)
async def tree_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@htmx_router.get("/chat", response_class=HTMLResponse)
async def tree_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@htmx_router.get("/dashboard", response_class=HTMLResponse)
async def tree_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@htmx_router.get("/knowledge", response_class=HTMLResponse)
async def tree_knowledge(request: Request):
    return templates.TemplateResponse("knowledge.html", {"request": request})


@htmx_router.post("/chat/msg", response_class=HTMLResponse)
async def tree_chat_message(request: Request):
    try:
        body = await request.json()
        msg = body.get("message", "")
    except Exception:
        form = await request.form()
        msg = form.get("message", "")

    life = getattr(request.app.state, "life", None)

    if life and hasattr(life, 'ask'):
        result = await life.ask(msg)
        mode = result.get('mode', '?')
        steps = result.get('steps', 0)
        conf = result.get('confidence', 0)
        html = (
            '<div class="msg assistant">'
            f'<div class="who">小树 🌳</div>'
            f'<div class="text">模式:{mode} | {steps}步 | 置信度:{conf:.0%}</div>'
            '</div>'
        )
    else:
        html = (
            '<div class="msg assistant">'
            '<div class="who">小树 🌳</div>'
            '<div class="text">系统仍在启动中，请稍候...</div>'
            '</div>'
        )

    return HTMLResponse(html)


@htmx_router.get("/health", response_class=HTMLResponse)
async def tree_health(request: Request):
    life = getattr(request.app.state, "life", None)
    if not life:
        return HTMLResponse('<div class="panel">系统启动中...</div>')

    health = life.health()
    sp = life.modules.get("synaptic_plasticity")
    xs = life.modules.get("xiaoshu")
    gap = ""
    gs = life.modules.get("godelian_self")
    if gs:
        gap = f'<div class="metric"><span>意识深度</span><span>{gs.compute_consciousness_gap():.3f}</span></div>'

    syn = ""
    if sp:
        s = sp.stats()
        syn = (
            f'<div class="metric"><span>神经连接</span>'
            f'<span>{s["total_synapses"]}条 '
            f'(成熟{s["by_state"]["mature"]} 活跃{s["by_state"]["active"]} '
            f'静默{s["by_state"]["silent"]})</span></div>'
        )

    xs_str = ""
    if xs:
        xs_str = (
            f'<div class="metric"><span>自主生长</span>'
            f'<span>{xs._cycle_count}周期</span></div>'
        )

    return HTMLResponse(
        '<div class="health-panel">'
        f'<h3>系统健康</h3>'
        f'<div class="metric"><span>状态</span><span>{health.get("status","?")}</span></div>'
        f'<div class="metric"><span>评分</span><span>{health.get("score",0):.1%}</span></div>'
        f'{syn}{xs_str}{gap}'
        '</div>'
    )


@htmx_router.get("/health/json")
async def tree_health_json(request: Request):
    """JSON health endpoint for Alpine.js data binding."""
    from fastapi.responses import JSONResponse
    life = getattr(request.app.state, "life", None)
    if not life:
        return JSONResponse({"status": "starting", "score": 0})

    health = life.health()
    sp = life.modules.get("synaptic_plasticity")
    xs = life.modules.get("xiaoshu")
    consc = life.modules.get("consciousness")
    gs = life.modules.get("godelian_self")

    syn_stats = sp.stats() if sp else {}
    return JSONResponse({
        "status": health.get("status", "?"),
        "score": round(health.get("score", 0), 3),
        "synapses": syn_stats.get("total_synapses", 0),
        "synapses_mature": syn_stats.get("by_state", {}).get("mature", 0),
        "synapses_active": syn_stats.get("by_state", {}).get("active", 0),
        "synapses_silent": syn_stats.get("by_state", {}).get("silent", 0),
        "cycles": xs._cycle_count if xs else 0,
        "affect": consc._current_affect.value if consc else "?",
        "consciousness_gap": round(gs.compute_consciousness_gap(), 3) if gs else 0,
        "degraded": health.get("degraded_modules", []),
        "action_items": health.get("action_items", []),
    })


@htmx_router.get("/sse")
async def tree_sse(request: Request):
    async def stream():
        while True:
            life = getattr(request.app.state, "life", None)
            if life:
                h = life.health()
                consc = life.modules.get("consciousness")
                xs = life.modules.get("xiaoshu")
                affect = consc._current_affect.value if consc else "?"
                cycle = xs._cycle_count if xs else 0
                yield f"data: 状态:{h.get('status','?')} 评分:{h.get('score',0):.0%} 💭{affect} 🌱#{cycle}\n\n"
            await asyncio.sleep(5)  # Live heartbeat every 5s

    return StreamingResponse(stream(), media_type="text/event-stream")


def setup_htmx(app) -> None:
    app.include_router(htmx_router)
    logger.info("HTMX web layer registered at /tree")
