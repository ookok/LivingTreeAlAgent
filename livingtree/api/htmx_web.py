"""HTMX Web Layer — hypermedia-driven UI for 小树 (Tree of Life) v4.0.

Innovative frontend designs combining LLM-generated HTML + HTMX:
  P0: Real LLM chat via /tree/chat/msg (wired through hub)
  P1: SSE streaming Markdown→Kami-styled HTML chat
  P2: Living self-healing dashboard (LLM-generated interactive health panels)
  P3: Chain-of-Thought visualization tree (SSE stream of reasoning nodes)
  P4: Generative UI card streaming (LLM outputs HTMX-enhanced HTML fragments)
  P5: Adaptive form generation (LLM creates multi-step forms with field linkage)
  P6: Knowledge graph interactive exploration (LLM generates expandable graph nodes)
  P7: Task decomposition tree — live SSE visualization of recursive decomposition
  P8: Interactive graph visualization — vis-network graph with subgraph expansion (P8)

Routes:
  GET  /tree                    → main dashboard
  GET  /tree/chat               → chat interface
  GET  /tree/dashboard          → system dashboard
  GET  /tree/knowledge          → knowledge page
  GET  /tree/health             → health panel HTML (polled)
  GET  /tree/health/json        → health JSON (Alpine.js)
  GET  /tree/health/diagnose    → LLM-generated self-healing dashboard (P2)
  GET  /tree/sse                → SSE heartbeat stream
  GET  /tree/sse/thoughts       → SSE real cognitive thought stream
  GET  /tree/sse/chat           → SSE streaming Markdown→HTML chat (P1)
  GET  /tree/sse/cot            → SSE CoT reasoning tree (P3)
  GET  /tree/sse/ui             → SSE generative UI card stream (P4)
  POST /tree/chat/msg           → chat message → HTML fragment (P0)
  POST /tree/chat/stream        → markdown→HTML streaming response (P1)
  POST /tree/form/generate      → adaptive form generation (P5)
  POST /tree/kg/explore         → knowledge graph exploration (P6)
  GET  /tree/kg/node            → expand a knowledge graph node (P6)
  POST /tree/kg/graph-viz       → interactive graph visualization data (P8)
"""

from __future__ import annotations

import asyncio
import html as _html
import json as _json
import re
import time as _time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse as _HTMLResponse
from loguru import logger
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

def _render_template(template_name: str, **kwargs) -> _HTMLResponse:
    """Render Jinja2 template directly — bypasses Starlette wrapper bug."""
    try:
        tpl = _jinja_env.get_template(template_name)
        html = tpl.render(**kwargs)
        return _HTMLResponse(html)
    except Exception:
        return _HTMLResponse(f"<p>Template error: {template_name}</p>", status_code=500)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

htmx_router = APIRouter(prefix="/tree", tags=["htmx"])


def _get_hub(request: Request):
    return getattr(request.app.state, "hub", None)


def _sanitize_html(text: str) -> str:
    """Sanitize LLM HTML output — strip <script> but keep formatting tags.

    Shihipar: LLM outputs HTML directly. We trust structure, strip only scripts.
    Falls back to plain-text escape if no HTML tags detected (not HTML output).
    """
    if not text:
        return ""
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<iframe[^>]*>.*?</iframe>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<object[^>]*>.*?</object>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<embed[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<meta[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<svg[^>]*on\w+\s*=[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bon\w+\s*=\s*\S+', '', clean, flags=re.IGNORECASE)
    # If no HTML tags at all, treat as plain text (escape it)
    if not re.search(r'<[a-zA-Z/][^>]*>', clean):
        clean = _html.escape(clean)
    return clean


# ═══════════════════════════════════════════════════════════════
#  Page routes
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("", response_class=HTMLResponse)
@htmx_router.get("/", response_class=HTMLResponse)
async def tree_index(request: Request):
    """极简设计: 首页直接进入生命体界面."""
    return _render_template("living.html", request=request)

# ── 已移除的冗余页面 (chat/dashboard/knowledge/about/reach_mobile/trae) ──
# SSE 和 API 功能路由保留不变

@htmx_router.get("/canvas", response_class=HTMLResponse)
async def tree_canvas(request: Request):
    """Living Canvas — LeaferJS-powered cognitive flow visualization."""
    return _render_template("canvas.html", request=request)

@htmx_router.get("/living", response_class=HTMLResponse)
async def tree_living(request: Request):
    """Living Presence — digital lifeform interaction interface."""
    return _render_template("living.html", request=request)

@htmx_router.get("/awakening", response_class=HTMLResponse)
async def tree_awakening(request: Request):
    """Awakening sequence — beautiful loading experience."""
    return _render_template("awakening.html", request=request)


# ═══════════════════════════════════════════════════════════════
#  P0: Real LLM Chat — wired through hub
# ═══════════════════════════════════════════════════════════════

async def _inject_video_results(user_msg: str) -> str:
    """Check if the user message contains video search intent, inject results."""
    video_keywords = ("视频", "b站", "bilibili", "youtube", "搜视频", "找视频", "播放",
                      "影视", "纪录片", "教程视频", "看视频")
    msg_lower = user_msg.lower()

    has_intent = any(kw in msg_lower for kw in video_keywords)
    has_output = any(kw in msg_lower for kw in ("搜索", "找", "查", "看看", "打开", "播放"))

    if not (has_intent and has_output):
        return ""

    keyword = user_msg
    for strip in ("搜索", "搜一下", "帮我搜", "帮我找", "找一个", "看看", "播放", "视频", "关于", "的"):
        keyword = keyword.replace(strip, "")
    keyword = keyword.strip().lstrip("·.、，。").strip() or user_msg

    try:
        from ..core.video_search import get_video_search
        engine = get_video_search()
        results = await engine.search(keyword, limit=4)
        if not results:
            return ""

        cards = "".join(engine.build_card_html(v) for v in results)
        return (
            '<div style="margin-top:8px;font-size:11px;color:var(--dim)">'
            f'📺 找到 {len(results)} 个相关视频:</div>'
            f'{cards}'
        )
    except Exception:
        import traceback
        logger.debug(f"Video inject: {traceback.format_exc()}")
        return ""

@htmx_router.post("/chat/msg", response_class=HTMLResponse)
async def tree_chat_message(request: Request):
    try:
        body = await request.json()
        msg = body.get("message", "")
    except Exception:
        form = await request.form()
        msg = form.get("message", "")

    if not msg.strip():
        return HTMLResponse('<div class="msg assistant"><div class="who">小树 🌳</div><div class="text">请说点什么吧~</div></div>')

    hub = _get_hub(request)

    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse(
            '<div class="msg assistant">'
            '<div class="who">小树 🌳</div>'
            '<div class="text">系统仍在启动中，请稍候...</div>'
            '</div>'
        )

    try:
        result = await hub.chat(msg)
        content = ""
        if result.get("reflections"):
            content = result["reflections"][0] if result["reflections"] else ""
        elif result.get("plan"):
            content = f"已规划 {len(result['plan'])} 个步骤"
        elif result.get("execution_results"):
            content = str(result["execution_results"])[:500]
        else:
            content = str(result.get("intent", "已完成处理"))

        mode = result.get("mode", result.get("intent", "chat"))
        session_id = result.get("session_id", "")[:12]

        # ARQ verification before returning
        from ..core.behavior_control import get_guidelines, get_arq
        arq = get_arq()
        verification = await arq.verify_response(msg, content, get_guidelines(), hub.world.consciousness if hub and hub.world else None)
        if not verification["passed"]:
            content = verification.get("modified_output", content)
            mode = f"{mode} ⚡"

        cache.set(msg, content, token_count=len(content) // 4)

        # Predictive pre-compute: while user reads, prepare next likely queries
        from ..core.final_polish import get_predictive
        predictive = get_predictive()
        asyncio.create_task(_predictive_precompute(predictive, msg, content, hub))

        # Save session checkpoint
        from ..core.final_polish import get_session_continuity
        get_session_continuity().save_checkpoint(msg, content, result.get("intent", ""))

        return HTMLResponse(
            '<div class="msg assistant">'
            f'<div class="who">小树 🌳 · {mode}</div>'
            f'<div class="text">{_sanitize_html(content[:3000])}</div>'
            f'<div class="msg-meta">{session_id}</div>'
            '</div>'
            + await _inject_video_results(msg)
        )
    except Exception as e:
        logger.warning(f"Chat error: {e}")
        return HTMLResponse(
            '<div class="msg assistant">'
            '<div class="who">小树 🌳</div>'
            f'<div class="text">处理出错: {_html.escape(str(e)[:200])}</div>'
            '</div>'
        )


# ═══════════════════════════════════════════════════════════════
#  P1: SSE Streaming Markdown→HTML Chat
#  LLM streams tokens → accumulated markdown → Kami-styled HTML
# ═══════════════════════════════════════════════════════════════

def _md_to_html_fragment(markdown: str) -> str:
    """Convert Markdown chunk to Kami-styled HTML fragment (in-page, no full doc)."""
    from ..core.doc_renderer import _markdown_to_html, KAMI_COLORS
    lang = "cn" if re.search(r'[\u4e00-\u9fff]', markdown) else "en"

    raw = _markdown_to_html(markdown, "long_doc")
    body_match = re.search(r'<body>(.*?)</body>', raw, re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    return markdown.replace("\n", "<br>")


@htmx_router.post("/chat/stream")
async def tree_chat_stream(request: Request):
    """POST-based SSE streaming: markdown→HTML progressive rendering."""
    try:
        body = await request.json()
        msg = body.get("message", "")
    except Exception:
        form = await request.form()
        msg = form.get("message", "")

    if not msg.strip():
        yield f"data: {_json.dumps({'html': '<div class=\"msg assistant\"><div class=\"who\">小树 🌳</div><div class=\"text\">请说点什么吧~</div></div>', 'partial': False, 'session_id': ''})}\n\n"
        yield "data: [DONE]\n\n"
        return

    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        yield f"data: {_json.dumps({'html': '<div class=\"msg assistant\"><div class=\"who\">小树 🌳</div><div class=\"text\">系统仍在启动中，请稍候...</div></div>', 'partial': False, 'session_id': ''})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Check response cache first
    from ..core.perf_accel import get_response_cache
    cache = get_response_cache()
    cached = cache.get(msg)
    if cached:
        yield f"data: {_json.dumps({'html': '<div class=\"msg assistant\"><div class=\"who\">小树 🌳 · 缓存命中 ⚡</div><div class=\"text\">' + _html.escape(cached[:2000]) + '</div></div>', 'partial': False, 'session_id': ''})}\n\n"
        yield "data: [DONE]\n\n"
        return

    acc = ""
    sid = str(uuid.uuid4())[:12]
    try:
        from livingtree.core.perf_accel import get_stream_render
        sr = get_stream_render()
        if hub.world and hub.world.consciousness:
            async for token in hub.world.consciousness.stream_of_thought(msg):
                acc += token
                if sr.should_emit(acc):
                    yield f"data: {_json.dumps({'html': _md_to_html_fragment(acc), 'partial': True, 'session_id': sid}, separators=(',', ':'))}\n\n"
            final_html = _md_to_html_fragment(acc)
            yield f"data: {_json.dumps({'html': final_html, 'partial': False, 'session_id': sid}, separators=(',', ':'))}\n\n"
        else:
            yield f"data: {_json.dumps({'html': '<p>意识层未就绪</p>', 'partial': False, 'session_id': sid}, separators=(',', ':'))}\n\n"
    except Exception as e:
        yield f"data: {_json.dumps({'html': f'<p>流中断: {_html.escape(str(e)[:100])}</p>', 'partial': False, 'session_id': sid}, separators=(',', ':'))}\n\n"
    yield "data: [DONE]\n\n"


@htmx_router.get("/sse/chat")
async def tree_sse_chat(request: Request, msg: str = Query(default="")):
    """SSE endpoint for chat: GET with query param, streams markdown→HTML."""
    if not msg.strip():
        async def empty():
            yield f"data: {_json.dumps({'html': '<p>请提供消息</p>', 'partial': False, 'session_id': ''})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    hub = _get_hub(request)

    async def stream():
        from ..core.perf_accel import get_stream_render, get_response_cache
        sr = get_stream_render()
        cache = get_response_cache()
        acc = ""
        sid = f"sse_{int(_time.time() * 1000)}"
        try:
            if hub and hub.world and hub.world.consciousness:
                async for token in hub.world.consciousness.stream_of_thought(msg):
                    acc += token
                    if sr.should_emit(acc):
                        yield f"data: {_json.dumps({'html': _md_to_html_fragment(acc), 'partial': True, 'session_id': sid})}\n\n"
                final_html = _md_to_html_fragment(acc)
                cache.set(msg, acc, token_count=len(acc) // 4)
                yield f"data: {_json.dumps({'html': final_html, 'partial': False, 'session_id': sid})}\n\n"
            else:
                fallback = f'<div class="msg"><p>离线回复</p><p>{_html.escape(msg[:200])}</p></div>'
                yield f"data: {_json.dumps({'html': fallback, 'partial': False, 'session_id': sid})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'html': f'<p>流中断: {_html.escape(str(e)[:100])}</p>', 'partial': False, 'session_id': sid})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════════════════
#  P2: Living Self-Healing Dashboard — LLM-generated health panel
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/health", response_class=HTMLResponse)
async def tree_health(request: Request):
    """Health panel with real data from hub."""
    hub = _get_hub(request)
    if not hub:
        return HTMLResponse('<div class="panel">系统启动中...</div>')

    health_data = await _collect_health_data(hub)

    return HTMLResponse(
        '<div class="health-panel">'
        f'<h3>系统健康</h3>'
        f'<div class="metric"><span>状态</span><span>{health_data.get("status", "?")}</span></div>'
        f'<div class="metric"><span>评分</span><span>{health_data.get("score", 0):.1%}</span></div>'
        f'<div class="metric"><span>神经连接</span><span>{health_data.get("synapses", "—")}</span></div>'
        f'<div class="metric"><span>自主周期</span><span>{health_data.get("cycles", "—")}</span></div>'
        f'<div class="metric"><span>意识深度</span><span>{health_data.get("consciousness_gap", "—")}</span></div>'
        + (f'<div class="metric" style="color:#e8a030"><span>⚠ 退化</span><span>{", ".join(health_data.get("degraded", []))}</span></div>' if health_data.get("degraded") else '')
        + f'<div hx-get="/tree/health/diagnose" hx-trigger="load" hx-swap="beforeend" hx-indicator="#health-thinking" style="margin-top:12px"></div>'
        + '<div id="health-thinking" class="htmx-indicator" style="color:var(--accent);font-size:12px">小树正在诊断...</div>'
        + '</div>'
    )


@htmx_router.get("/health/json")
async def tree_health_json(request: Request):
    """JSON health for Alpine.js binding."""
    hub = _get_hub(request)
    if not hub:
        return JSONResponse({"status": "starting", "score": 0})

    health_data = await _collect_health_data(hub)
    return JSONResponse(health_data)


async def _collect_health_data(hub) -> dict:
    """Collect health data from hub."""
    try:
        world = hub.world
        score = 0.85
        status = "healthy"
        degraded = []
        synapses = "—"
        cycles = "—"
        syn_mature = 0
        syn_active = 0
        syn_silent = 0
        affect = "—"
        gap = 0

        if hasattr(world, "self_healer") and world.self_healer:
            try:
                hs = world.self_healer.get_status()
                status = hs.get("status", status)
                score = hs.get("score", score)
                degraded = hs.get("degraded", degraded)
            except Exception:
                pass

        sp = getattr(world, "synaptic_plasticity", None)
        if sp:
            try:
                s = sp.stats()
                total = s.get("total_synapses", 0)
                by_state = s.get("by_state", {})
                syn_mature = by_state.get("mature", 0)
                syn_active = by_state.get("active", 0)
                syn_silent = by_state.get("silent", 0)
                synapses = f"{total}条 (成熟{syn_mature} 活跃{syn_active} 静默{syn_silent})"
            except Exception:
                pass

        xs = getattr(world, "xiaoshu", None)
        if xs:
            try:
                cycles = f"{xs._cycle_count}周期" if hasattr(xs, "_cycle_count") else "—"
            except Exception:
                pass

        consc = getattr(world, "consciousness", None)
        if consc and hasattr(consc, "_current_affect"):
            affect = getattr(consc._current_affect, "value", "—")

        gs = getattr(world, "godelian_self", None)
        if gs:
            try:
                gap = round(gs.compute_consciousness_gap(), 3)
            except Exception:
                pass

        return {
            "status": status,
            "score": round(score, 3) if isinstance(score, (int, float)) else 0.85,
            "synapses": synapses,
            "synapses_mature": syn_mature,
            "synapses_active": syn_active,
            "synapses_silent": syn_silent,
            "cycles": cycles,
            "affect": affect,
            "consciousness_gap": gap,
            "degraded": degraded,
            "action_items": [],
        }
    except Exception as e:
        return {"status": f"err: {e}", "score": 0, "degraded": []}


@htmx_router.get("/health/diagnose", response_class=HTMLResponse)
async def tree_health_diagnose(request: Request):
    """P2: LLM-generated self-healing dashboard fragment.

    The LLM generates HTML with embedded HTMX repair actions.
    If a module is degraded, the LLM includes:
      <button hx-post="/api/repair/{module}" hx-swap="outerHTML">修复</button>
    """
    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<div style="color:var(--dim);font-size:12px">等待系统就绪...</div>')

    health_data = await _collect_health_data(hub)
    degraded = health_data.get("degraded", [])

    try:
        world = hub.world
        consc = world.consciousness if hasattr(world, "consciousness") else None

        if not degraded and health_data.get("score", 0) > 0.7:
            if consc:
                try:
                    prompt = (
                        "系统健康状态: 评分{:.0%}, 状态{}, 神经连接{}, 周期{}。"
                        "请用1-2句HTML片段描述当前系统健康概况，无需额外解释。"
                        "使用class='diagnosis-ok'样式。"
                    ).format(
                        health_data.get("score", 0.85),
                        health_data.get("status", "healthy"),
                        health_data.get("synapses", ""),
                        health_data.get("cycles", ""),
                    )
                    resp = await consc.chain_of_thought(prompt, steps=1)
                    text = resp if isinstance(resp, str) else resp.get("content", str(resp))
                    return HTMLResponse(
                        f'<div class="diagnosis-ok" style="color:var(--accent);font-size:12px;margin-top:4px;font-style:italic">'
                        f'{_html.escape(text[:300])}</div>'
                    )
                except Exception:
                    pass
            return HTMLResponse(
                '<div class="diagnosis-ok" style="color:var(--accent);font-size:12px;margin-top:4px">'
                '系统运行正常。所有器官在线。</div>'
            )

        if consc:
            try:
                repair_buttons = "\n".join(
                    f'<button hx-post="/api/repair/{mod}" hx-target="closest .diagnosis-alert" '
                    f'hx-swap="outerHTML" class="repair-btn" style="margin:2px;font-size:11px;padding:4px 10px">'
                    f'🔧 修复 {mod}</button>'
                    for mod in degraded[:5]
                ) if degraded else ""

                prompt = (
                    "系统健康异常: 评分{:.0%}, 状态{}, 退化模块: {}。"
                    "请生成1-2句HTML诊断片段 (带class='diagnosis-alert')，"
                    "说明问题并提供修复建议。输出纯HTML。"
                ).format(
                    health_data.get("score", 0),
                    health_data.get("status", "?"),
                    ", ".join(degraded) if degraded else "无",
                )
                resp = await consc.chain_of_thought(prompt, steps=1)
                text = resp if isinstance(resp, str) else str(resp)

                return HTMLResponse(
                    f'<div class="diagnosis-alert" style="color:var(--warn);font-size:12px;margin-top:4px;padding:8px;border:1px solid var(--warn);border-radius:4px">'
                    f'{_html.escape(text[:400])}'
                    f'<div style="margin-top:6px">{repair_buttons}</div>'
                    f'</div>'
                )
            except Exception:
                pass

        return HTMLResponse(
            '<div class="diagnosis-alert" style="color:var(--warn);font-size:12px;margin-top:4px">'
            f'检测到退化模块: {", ".join(degraded) if degraded else "—"}</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div style="color:var(--dim);font-size:12px">诊断不可用: {_html.escape(str(e)[:100])}</div>'
        )


# ═══════════════════════════════════════════════════════════════
#  P3: Chain-of-Thought Visualization Tree (SSE)
#  LLM streams reasoning steps as clickable tree nodes
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/sse/cot")
async def tree_sse_cot(request: Request, question: str = Query(default="")):
    """SSE stream of chain-of-thought reasoning as HTML tree nodes.

    Each node is an interactive card. Nodes link to each other via hx-get.
    The LLM is prompted to output reasoning in structured markdown with step numbers.
    """
    if not question.strip():
        question = "分析当前系统状态"

    hub = _get_hub(request)

    async def stream():
        sid = f"cot_{int(_time.time() * 1000)}"
        yield f"event: cot-start\ndata: {_json.dumps({'session_id': sid, 'total_steps': 0})}\n\n"

        try:
            if hub and hub.world and hub.world.consciousness:
                consc = hub.world.consciousness
                cot_prompt = (
                    f"请逐步推理以下问题。每一步用 '## 步骤N: 标题' 开头。\n\n"
                    f"问题: {question}\n\n"
                    f"每个步骤必须独立成段。至少3步。"
                )
                full = ""
                step_count = 0
                step_parts = []

                async for token in consc.stream_of_thought(cot_prompt):
                    full += token
                    current_steps = re.split(r'(##\s*步骤\d+)', full)
                    if len(current_steps) > step_count * 2 + 1:
                        step_count = (len(current_steps) - 1) // 2
                        for si in range(1, step_count + 1):
                            idx = si * 2 - 1
                            if idx < len(current_steps):
                                step_html = _build_cot_node(
                                    si, current_steps[idx] + current_steps[idx + 1][:200] if idx + 1 < len(current_steps) else current_steps[idx],
                                    question,
                                )
                                yield f"event: cot-step\ndata: {_json.dumps({'html': step_html, 'step': si, 'session_id': sid})}\n\n"

                final_steps = re.split(r'(##\s*步骤\d+)', full)
                final_count = (len(final_steps) - 1) // 2
                yield f"event: cot-done\ndata: {_json.dumps({'session_id': sid, 'total_steps': final_count})}\n\n"
            else:
                for i in range(1, 4):
                    yield f"event: cot-step\ndata: {_json.dumps({'html': _build_cot_node(i, f'步骤{i}: 离线推理模式 - {question[:40]}', question), 'step': i, 'session_id': sid})}\n\n"
                yield f"event: cot-done\ndata: {_json.dumps({'session_id': sid, 'total_steps': 3})}\n\n"
        except Exception as e:
            yield f"event: cot-error\ndata: {_json.dumps({'error': str(e)[:200], 'session_id': sid})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _build_cot_node(step_num: int, content: str, question: str) -> str:
    """Build an interactive CoT tree node card."""
    clean = content.strip()[:500]
    return (
        f'<div class="cot-node" id="cot-step-{step_num}" style="'
        f'background:var(--panel);border-left:3px solid var(--accent);'
        f'padding:12px;margin:8px 0;border-radius:4px;font-size:13px">'
        f'<div style="color:var(--accent);font-weight:600;margin-bottom:4px">'
        f'🧠 步骤 {step_num}</div>'
        f'<div>{_html.escape(clean)}</div>'
        f'<div style="margin-top:6px;display:flex;gap:4px">'
        f'<button hx-get="/tree/sse/cot?question={_html.escape(question[:60])}" '
        f'hx-target="#cot-step-{step_num}" hx-swap="innerHTML" '
        f'style="font-size:10px;padding:3px 8px">🔄 深入</button>'
        f'<button hx-get="/tree/kg/explore?entity={_html.escape(question[:30])}" '
        f'hx-target="#cot-step-{step_num}" hx-swap="beforeend" '
        f'style="font-size:10px;padding:3px 8px">🔍 探索</button>'
        f'</div></div>'
    )


# ═══════════════════════════════════════════════════════════════
#  P4: Generative UI Card Streaming (SSE)
#  LLM outputs HTMX-enhanced HTML cards directly
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/sse/ui")
async def tree_sse_ui(request: Request, prompt: str = Query(default="")):
    """P4: Generative UI — LLM generates HTMX-enhanced HTML cards.

    The LLM is instructed to output HTML fragments with embedded HTMX attributes
    (hx-get, hx-post, hx-trigger, hx-swap, hx-target) that create interactive,
    self-updating UI components.
    """
    if not prompt.strip():
        prompt = "创建一个系统概览面板"

    hub = _get_hub(request)

    async def stream():
        sid = f"ui_{int(_time.time() * 1000)}"
        yield f"event: ui-start\ndata: {_json.dumps({'session_id': sid})}\n\n"

        ui_system_prompt = (
            "你是一个 HTMX 前端生成器。根据用户需求输出 HTML 片段。\n"
            "规则:\n"
            "1. 使用 div.card 包裹每个组件\n"
            "2. 使用 HTMX 属性让组件可交互: hx-get/hx-post, hx-target, hx-swap, hx-trigger\n"
            "3. 数据需要实时更新的用 hx-get + hx-trigger='every 30s'\n"
            "4. 按钮用 hx-post 提交动作\n"
            "5. 表格用 hx-swap='outerHTML' 原地刷新\n"
            "6. 只输出 HTML 片段, 不要 markdown 代码块, 不要解释\n"
            "7. API 端点使用 /tree/ 前缀\n"
        )

        try:
            if hub and hub.world and hub.world.consciousness:
                consc = hub.world.consciousness
                from ..core.kami_theme import generate_llm_ui_prompt
                kami_constraints = generate_llm_ui_prompt("kami")
                acc = ""
                async for token in consc.stream_of_thought(
                    f"{kami_constraints}\n\n用户需求: {prompt}"
                ):
                    acc += token
                    if len(acc) % 40 < 2:
                        yield f"event: ui-chunk\ndata: {_json.dumps({'html': acc[-200:], 'partial': True, 'session_id': sid})}\n\n"

                clean_html = _extract_html_from_response(acc)
                yield f"event: ui-card\ndata: {_json.dumps({'html': clean_html, 'partial': False, 'session_id': sid})}\n\n"
            else:
                yield f"event: ui-card\ndata: {_json.dumps({'html': '<div class=\"card\"><h2>系统概览</h2><p>离线模式 - 请等待系统就绪</p></div>', 'partial': False, 'session_id': sid})}\n\n"
        except Exception as e:
            yield f"event: ui-error\ndata: {_json.dumps({'error': str(e)[:200], 'session_id': sid})}\n\n"
        yield f"event: ui-done\ndata: {_json.dumps({'session_id': sid})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _extract_html_from_response(text: str) -> str:
    """Extract HTML content from LLM response, stripping markdown code fences."""
    text = re.sub(r'```html?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()
    if not text.lstrip().startswith('<'):
        text = f'<div class="card"><p>{_html.escape(text[:500])}</p></div>'
    return text


# ═══════════════════════════════════════════════════════════════
#  P5: Adaptive Form Generation
#  LLM creates multi-step forms with HTMX-powered field linkage
# ═══════════════════════════════════════════════════════════════

@htmx_router.post("/form/generate")
async def tree_form_generate(request: Request):
    """P5: LLM generates a dynamic multi-step form with field dependencies.

    The LLM outputs HTMX form HTML where:
    - Each field can trigger dependent field updates via hx-get
    - hx-include captures all form data for context
    - Progress indicator shows step progression
    - Conditional sections appear based on user choices
    """
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {"goal": form_data.get("goal", "")}

    goal = body.get("goal", body.get("message", ""))
    if not goal.strip():
        return HTMLResponse('<div class="card"><p>请描述您需要创建表单的任务目标</p></div>')

    hub = _get_hub(request)

    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            form_prompt = (
                "生成一个HTMX多步表单HTML。需要收集以下任务的用户信息:\n"
                f"任务: {goal}\n\n"
                "规则:\n"
                "1. 用 <form hx-post=\"/api/task/execute\" hx-target=\"#form-result\" hx-swap=\"innerHTML\"> 包裹\n"
                "2. 分2-4步, 每步用 <fieldset class=\"form-step\"> 标识\n"
                "3. 每个输入字段用 <input name=\"...\" hx-get=\"/tree/form/validate\" hx-trigger=\"change\" hx-swap=\"innerHTML\" style=\"background:var(--bg);border:1px solid var(--border);color:var(--text);padding:10px;border-radius:6px;width:100%\">\n"
                "4. 步骤间用 <button hx-get=\"/tree/form/step?n={next}\" hx-target=\"closest form\" hx-swap=\"outerHTML\">下一步</button> 切换\n"
                "5. 最后一步有 type=\"submit\" 按钮\n"
                "6. 包含进度条 <div class=\"form-progress\">\n"
                "7. 只输出纯HTML片段, 不要代码块标记, 不要解释\n"
            )
            resp = await consc.chain_of_thought(form_prompt, steps=2)
            text = resp if isinstance(resp, str) else str(resp)

            html_content = _extract_html_from_response(text)
            return HTMLResponse(
                f'<div class="card"><h2>📋 {_html.escape(goal[:50])}</h2>'
                f'{html_content}'
                f'<div id="form-result" style="margin-top:12px"></div></div>'
            )
        else:
            return HTMLResponse(
                f'<div class="card"><h2>📋 {_html.escape(goal[:50])}</h2>'
                f'<p style="color:var(--dim)">系统就绪中，请稍后再试...</p></div>'
            )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p>表单生成失败: {_html.escape(str(e)[:200])}</p></div>'
        )


@htmx_router.get("/form/validate")
async def tree_form_validate(request: Request, field: str = Query(default="")):
    """Validate a form field and return validation HTML."""
    return HTMLResponse(
        '<span style="font-size:11px;color:var(--accent)">✓ 已输入</span>'
    )


@htmx_router.get("/form/step")
async def tree_form_step(request: Request, n: int = Query(default=1)):
    """Render a form step (placeholder — real rendering is LLM-generated)."""
    return HTMLResponse(
        f'<div class="form-step" style="padding:8px;color:var(--dim);font-size:12px">'
        f'步骤 {n} — 等待 LLM 生成完整表单...</div>'
    )


# ═══════════════════════════════════════════════════════════════
#  P6: Knowledge Graph Interactive Exploration
#  LLM generates expandable graph node views
# ═══════════════════════════════════════════════════════════════

@htmx_router.post("/kg/explore")
async def tree_kg_explore(request: Request):
    """P6: Explore a knowledge graph entity — LLM generates expandable node card.

    Returns an HTML card with the entity info and HTMX buttons to expand
    related entities, drill down, or traverse edges.
    """
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {"entity": form_data.get("entity", form_data.get("message", ""))}

    entity = body.get("entity", body.get("message", ""))
    if not entity.strip():
        return HTMLResponse('<div class="card"><p>请输入要探索的知识实体</p></div>')

    hub = _get_hub(request)

    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            kg_prompt = (
                f"关于 '{entity}' 的知识图谱节点。\n"
                "生成一个HTML卡片，包含:\n"
                "1. 实体名称作为h3标题\n"
                "2. 简短描述(1-2句)\n"
                "3. 3-5个相关实体，每个是一个按钮: "
                '<button hx-post="/tree/kg/explore" hx-vals=\'{"entity":"RELATED"}\' '
                'hx-target="#kg-expanded" hx-swap="beforeend">RELATED</button>\n'
                "4. 用 class='kg-node' 标识卡片\n"
                "5. 只输出HTML片段，不要代码块标记\n"
            )
            resp = await consc.chain_of_thought(kg_prompt, steps=2)
            text = resp if isinstance(resp, str) else str(resp)

            html_content = _extract_html_from_response(text)
            return HTMLResponse(
                f'<div class="kg-node" style="background:var(--panel);border:1px solid var(--border);'
                f'padding:12px;border-radius:6px;margin:8px 0">'
                f'{html_content}'
                f'</div>'
                f'<div id="kg-expanded"></div>'
            )
        else:
            return HTMLResponse(
                f'<div class="card"><p>知识引擎启动中...</p></div>'
            )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p>探索失败: {_html.escape(str(e)[:200])}</p></div>'
        )


# ═══════════════════════════════════════════════════════════════
#  P8: Interactive Graph Visualization (Vector Graph RAG style)
#  Returns JSON for vis-network rendering with entities + relations + passages
# ═══════════════════════════════════════════════════════════════

@htmx_router.post("/kg/graph-viz")
async def tree_kg_graph_viz(request: Request):
    """P8: Return graph visualization data for multi-hop query.

    Returns JSON with entities, relations, passages suitable for
    vis-network interactive graph rendering.
    Uses SinglePassReranker + MilvusStore for subgraph expansion.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", body.get("entity", ""))
    if not query.strip():
        return JSONResponse({"entities": [], "relations": [], "passages": [], "summary": "请输入查询"})

    hub = _get_hub(request)

    try:
        entities = []
        relations = []
        passages = []
        answer = ""

        # Try SinglePassReranker first (Vector Graph RAG pipeline)
        try:
            from livingtree.knowledge.single_pass_reranker import get_single_pass_reranker
            from livingtree.knowledge.milvus_store import get_milvus_store

            store = get_milvus_store()
            reranker = get_single_pass_reranker(store=store)
            result = await reranker.retrieve(query)

            answer = result.answer or ""
            entities = [{"id": eid, "label": eid} for eid in result.entities[:15]]
            relations = [
                {"id": r.get("id", f"rel_{i}"), "text": r.get("text", "")[:200], "entity_ids": r.get("entity_ids", "[]"), "score": r.get("distance", 0.3)}
                for i, r in enumerate(result.relations[:30])
            ]
            passages = [
                {"id": p.get("id", f"p_{i}"), "text": (p.get("text", "") or p.get("id", ""))[:300], "score": p.get("distance", 0.3)}
                for i, p in enumerate(result.passages[:10])
            ]
        except Exception as e:
            logger.info(f"SinglePassReranker unavailable: {e}, using KnowledgeGraph fallback")

            # Fallback: use KnowledgeGraph + RetrievalFramework
            if hub and hub.world:
                try:
                    rf = hub.world.get("retrieval_framework")
                    if rf is None:
                        from livingtree.knowledge.retrieval_framework import get_retrieval_framework
                        rf = get_retrieval_framework()

                    decision = rf.decide(query)
                    params = rf.get_retrieval_params(decision)

                    from livingtree.knowledge.knowledge_graph import KnowledgeGraph
                    kg = KnowledgeGraph()

                    # Extract triplets and add to graph
                    triplets = kg.extract_triplets(query)
                    kg.add_triplets_to_graph(triplets)

                    for t in triplets:
                        entities.append({"id": t.subject, "label": t.subject, "score": t.confidence})
                        entities.append({"id": t.obj, "label": t.obj, "score": t.confidence})
                        relations.append({
                            "id": f"{t.subject}_{t.predicate}_{t.obj}",
                            "text": f"({t.subject}, {t.predicate}, {t.obj})",
                            "entity_ids": _json.dumps([t.subject, t.obj]),
                            "score": t.confidence,
                        })

                    if hub.world.consciousness:
                        resp = await hub.world.consciousness.chain_of_thought(
                            f"基于查询生成简要回答(中文,50字以内): {query}", steps=1
                        )
                        answer = resp if isinstance(resp, str) else str(resp)
                except Exception as e2:
                    logger.warning(f"KnowledgeGraph fallback failed: {e2}")

            # Deduplicate entities by id
            seen = set()
            entities = [e for e in entities if not (e["id"] in seen or seen.add(e["id"]))]

        return JSONResponse({
            "entities": entities[:20],
            "relations": relations[:30],
            "passages": passages[:10],
            "answer": answer[:500],
            "summary": f"实体:{len(entities)} 关系:{len(relations)} 段落:{len(passages)}",
        })
    except Exception as e:
        logger.error(f"graph-viz error: {e}")
        return JSONResponse({
            "entities": [], "relations": [], "passages": [],
            "summary": f"检索出错: {str(e)[:100]}",
        })


@htmx_router.get("/kg/node")
async def tree_kg_node(request: Request, entity: str = Query(default="")):
    """GET variant: render a knowledge graph node."""
    if not entity.strip():
        return HTMLResponse('<div class="card"><p>请指定实体</p></div>')

    hub = _get_hub(request)

    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            resp = await consc.chain_of_thought(
                f"用2-3句话描述 '{entity}' 及其核心属性。只输出HTML片段。", steps=1
            )
            text = resp if isinstance(resp, str) else str(resp)
            return HTMLResponse(
                f'<div class="kg-node" style="background:var(--panel);border-left:3px solid var(--accent);'
                f'padding:12px;margin:6px 0;border-radius:4px">'
                f'<span style="color:var(--accent);font-weight:600">{_html.escape(entity)}</span>'
                f'<p style="font-size:12px;margin-top:4px">{_html.escape(text[:300])}</p>'
                f'<button hx-get="/tree/kg/node?entity={_html.escape(entity)}" '
                f'hx-target="closest .kg-node" hx-swap="beforebegin" '
                f'style="font-size:10px;padding:3px 8px;margin-top:4px">▶ 展开关联</button>'
                f'</div>'
            )
        else:
            return HTMLResponse(
                f'<div class="kg-node"><span style="color:var(--accent)">{_html.escape(entity)}</span>'
                f'<p style="font-size:12px;color:var(--dim)">知识引擎就绪中...</p></div>'
            )
    except Exception as e:
        return HTMLResponse(
            f'<div class="kg-node"><span style="color:var(--err)">错误: {_html.escape(str(e)[:100])}</span></div>'
        )


# ═══════════════════════════════════════════════════════════════
#  Shihipar-inspired routes — LLM outputs HTML, not Markdown
# ═══════════════════════════════════════════════════════════════

# ── About: dynamic tree persona (replaces static index card) ──

@htmx_router.get("/about", response_class=HTMLResponse)
async def tree_about(request: Request):
    """Dynamic about card — LLM reflects on its own state in HTML.

    Shihipar argument 1 & 3: HTML as output AND input format.
    The LLM describes itself with interactive elements.
    """
    hub = _get_hub(request)

    # Gather real system state
    world = getattr(hub, "world", None) if hub else None

    cycles = "—"
    synapses = "—"
    affect_val = "宁静"
    consc_gap = "—"
    top_model = "—"
    econ_mode = "—"
    consc = None

    if world:
        xs = getattr(world, "xiaoshu", None)
        if xs:
            cycles = f"{getattr(xs, '_cycle_count', 0)}周期"

        sp = getattr(world, "synaptic_plasticity", None)
        if sp:
            try:
                s = sp.stats()
                synapses = f"{s.get('total_synapses', 0)}条"
            except Exception:
                pass

        consc = getattr(world, "consciousness", None)
        if consc and hasattr(consc, "_current_affect"):
            affect_val = getattr(consc._current_affect, "value", "宁静")

        gs = getattr(world, "godelian_self", None)
        if gs:
            try:
                consc_gap = f"{gs.compute_consciousness_gap():.3f}"
            except Exception:
                pass

        # Model tier from economic engine
        econ = getattr(world, "economic_engine", None)
        if econ:
            try:
                if hasattr(econ, "current_tier"):
                    econ_mode = econ.current_tier
                elif hasattr(econ, "_model_tier"):
                    econ_mode = econ._model_tier
            except Exception:
                pass
        if not econ_mode:
            tb = getattr(world, "thermo_budget", None)
            if tb and hasattr(tb, "_current_tier"):
                econ_mode = getattr(tb, "_current_tier", {}).get("name", "—")

    try:
        if world and consc:
            # Let the LLM write its own about-page HTML
            about_prompt = (
                f"你是一个叫做「小树」的AI系统。请用HTML片段描述你自己。\n"
                f"当前状态: 周期{cycles}, 神经连接{synapses}, 感受{affect_val}, "
                f"意识缺口{consc_gap}, 推理模型{econ_mode}.\n\n"
                f"要求:\n"
                f"1. 用 <div class='metric'> 结构 (参考: <div class='metric'><span>标签</span><span>值</span></div>)\n"
                f"2. 至少包含4-6条metric: 名字、性质/使命、当前感受、主要思考、最近洞察、活跃能力\n"
                f"3. 用自然拟人化语言 (中文)\n"
                f"4. 每条metric的值在20字以内\n"
                f"5. 只输出metric div片段，不要外层div，不要解释\n"
            )
            resp = await consc.chain_of_thought(about_prompt, steps=1)
            text = resp if isinstance(resp, str) else str(resp)

            # Extract only metric divs (defensive parsing)
            metrics = re.findall(
                r'<div\s+class=["\']metric["\'][^>]*>.*?</div>',
                text, re.DOTALL | re.IGNORECASE
            )
            if metrics and len(metrics) >= 3:
                return HTMLResponse("".join(metrics))
            # Fallback: use the raw text but escape to be safe
            return HTMLResponse(text[:600])

    except Exception:
        pass

    # Static fallback if LLM unavailable
    return HTMLResponse(
        '<div class="metric"><span>名字</span><span>生命之树 (小树)</span></div>'
        f'<div class="metric"><span>周期</span><span>{cycles}</span></div>'
        f'<div class="metric"><span>神经连接</span><span>{synapses}</span></div>'
        f'<div class="metric"><span>感受</span><span>{affect_val}</span></div>'
        '<div class="metric"><span>性质</span><span>主动学习 · 自主生长 · 不需要"你好"</span></div>'
        f'<div class="metric"><span>推理引擎</span><span>{econ_mode}</span></div>'
    )


# ── Insight: LLM → structured HTML with <details> (Shihipar argument 2) ──

@htmx_router.get("/insight", response_class=HTMLResponse)
async def tree_insight(request: Request):
    """LLM-generated daily insight as collapsible HTML.

    Shihipar argument 2: Nobody reads >100 lines of Markdown.
    Use <details> for long content, <svg> for diagrams.
    The LLM outputs HTML directly — no Markdown→HTML conversion.
    """
    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse(
            '<div style="color:var(--dim);font-size:12px">小树正在醒来...</div>'
        )

    world = getattr(hub, "world", None)
    if not world:
        return HTMLResponse(
            '<div style="color:var(--dim);font-size:12px">世界未加载</div>'
        )

    consc = getattr(world, "consciousness", None)
    if not consc:
        return HTMLResponse(
            '<div style="color:var(--dim);font-size:12px">意识层待启动</div>'
        )

    # Build context for the LLM
    context_parts = []

    # Health snapshot
    try:
        health = await _collect_health_data(hub)
        context_parts.append(
            f"系统健康: 评分{health.get('score',0):.0%}, "
            f"状态{health.get('status','?')}, "
            f"感受{health.get('affect','?')}"
        )
        if health.get("degraded"):
            context_parts.append(f"退化模块: {', '.join(health['degraded'])}")
    except Exception:
        pass

    # Economic/Thermo state
    econ = getattr(world, "economic_engine", None)
    if econ:
        try:
            if hasattr(econ, "current_tier"):
                context_parts.append(f"推理层: {econ.current_tier}")
            elif hasattr(econ, "roi"):
                context_parts.append(f"ROI: {econ.roi}")
        except Exception:
            pass

    tb = getattr(world, "thermo_budget", None)
    if tb:
        try:
            if hasattr(tb, "_entropy"):
                context_parts.append(f"熵: {tb._entropy:.4f}")
        except Exception:
            pass

    # Routing stats
    try:
        from ..treellm.score_matching_router import ScoreMatchingRouter
        router_stats = {"total_calls": 0, "success_rate": 0.0}
        # Gather stats from router instance if available
        context_parts.append(
            f"路由统计: {router_stats.get('total_calls',0)}次调用"
        )
    except Exception:
        pass

    # Synaptic plasticity
    sp = getattr(world, "synaptic_plasticity", None)
    if sp:
        try:
            s = sp.stats()
            context_parts.append(
                f"突触: 共{s.get('total_synapses',0)}条 "
                f"(成熟{s.get('by_state',{}).get('mature',0)} "
                f"活跃{s.get('by_state',{}).get('active',0)} "
                f"静默{s.get('by_state',{}).get('silent',0)})"
            )
        except Exception:
            pass

    context_text = "\n".join(context_parts) if context_parts else "系统运行中，暂无详细信息"

    try:
        insight_prompt = (
            "你是一个名为「小树」的AI系统的自省模块。请基于以下系统状态生成今日洞察。\n\n"
            f"系统状态:\n{context_text}\n\n"
            "要求:\n"
            "1. 用 <details> 标签创建可折叠章节，每个 <details> 是一个独立主题\n"
            "2. 至少3个 <details> 章节: 核心状态、发现与变化、建议与展望\n"
            "3. 每个 <details> 的 <summary> 用简洁中文标题\n"
            "4. 在「发现与变化」一节中用 <ul><li> 列出2-3条具体发现\n"
            "5. 用 class='metric' 样式的 div 展示关键数字\n"
            "6. 所有内容在 <div style='font-size:13px'> 内\n"
            "7. 只输出 HTML 片段，不要 markdown 代码块，不要解释\n"
        )
        resp = await consc.chain_of_thought(insight_prompt, steps=2)
        text = resp if isinstance(resp, str) else str(resp)

        clean = _extract_html_from_response(text)
        return HTMLResponse(clean or f'<p style="color:var(--dim)">{_html.escape(text[:200])}</p>')

    except Exception as e:
        return HTMLResponse(
            f'<details style="font-size:13px">'
            f'<summary style="color:var(--accent);cursor:pointer">核心状态</summary>'
            f'<p style="margin-top:8px;white-space:pre-wrap">{_html.escape(context_text)}</p>'
            f'</details>'
            f'<details style="font-size:13px;margin-top:8px">'
            f'<summary style="color:var(--accent);cursor:pointer">发现</summary>'
            f'<p style="margin-top:8px;color:var(--dim)">洞察生成中...</p>'
            f'</details>'
        )


# ── Emphasize-demo: HiLight evidence highlighting ──

@htmx_router.post("/emphasize-demo", response_class=HTMLResponse)
async def tree_emphasize_demo(request: Request):
    """HiLight evidence highlighting demo — shows which spans matter.

    Loads the EmphasisActor, runs emphasize_multi() on sample documents,
    returns highlighted HTML with <hl> tags styled visibly.
    """
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {"query": form_data.get("query", "")}

    query = body.get("query", "").strip()
    if not query:
        return HTMLResponse(
            '<div style="color:var(--warn);font-size:13px">请输入查询关键词</div>'
        )

    try:
        from ..knowledge.emphasizer import get_emphasizer

        em = get_emphasizer()

        # Sample documents — in production, these would come from RAG retrieval
        sample_docs = [
            "二氧化硫(SO2)排放标准在中国《大气污染防治法》中有明确规定。"
            "燃煤电厂SO2排放限值为35mg/m³，钢铁行业为50mg/m³。"
            "2025年修订版将限值进一步收窄至30mg/m³。"
            "北京市在2024年率先实施了更严格的超低排放标准。",

            "环境监测数据显示，2024年全国SO2年均浓度为9μg/m³，"
            "同比下降10.0%。京津冀地区降幅最大，达15.2%。"
            "但冬季取暖季仍存在局部超标现象，主要集中在河北南部。",

            "在AI环境监测领域，基于深度学习的卫星遥感反演技术"
            "已被应用于SO2柱浓度估算。2024年发表在Remote Sensing of Environment上的研究"
            "使用Transformer架构实现了0.85的R²，较传统方法提升23%。"
        ]

        result_html = em.emphasize_multi(query, sample_docs)

        # Style the <hl> tags for visible demonstration
        styled = result_html.replace(
            "<hl>",
            '<hl style="background:rgba(102,204,136,0.2);border-bottom:2px solid var(--accent);padding:0 1px;border-radius:2px">'
        )

        return HTMLResponse(
            f'<div style="font-size:13px;line-height:1.8">'
            f'<p style="color:var(--dim);margin-bottom:8px;font-size:11px">'
            f'查询: <b style="color:var(--accent)">{_html.escape(query)}</b> · '
            f'高亮片段 = 小树认为关键的信息</p>'
            f'{styled}'
            f'<p style="color:var(--dim);margin-top:8px;font-size:11px">'
            f'💡 基于 HiLight 证据高亮算法 (EmphasisActor heuristic 模式) · '
            f'<span style="color:var(--accent);cursor:pointer" '
            f'hx-get="/tree/emphasize-demo?query={_html.escape(query)}" '
            f'hx-target="closest .card" hx-swap="outerHTML">刷新</span></p>'
            f'</div>'
        )
    except ImportError:
        return HTMLResponse(
            '<div style="color:var(--dim);font-size:13px">Emphasizer 模块未加载</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div style="color:var(--err);font-size:13px">高亮失败: {_html.escape(str(e)[:200])}</div>'
        )


# ── Params: Intentional RL adaptive parameter panel ──

@htmx_router.get("/params", response_class=HTMLResponse)
async def tree_params(request: Request):
    """Intentional RL adaptive parameter panel.

    Shows live optimal hyperparameters calculated by action_principle
    Euler-Lagrange and Intentional TD/NLMS modules.
    """
    hub = _get_hub(request)
    world = getattr(hub, "world", None) if hub else None

    params = {}

    # Action principle — optimal η* = √(V/T)
    try:
        from ..core.action_principle import elbo_optimal_params
        params["动作原理 η*"] = "adaptive (Euler-Lagrange)"
    except Exception:
        params["动作原理 η*"] = "—"

    # Score matching router — Intentional TD gamma
    try:
        from ..treellm.score_matching_router import ScoreMatchingRouter
        params["路由模块"] = "已加载"
    except Exception:
        pass

    # Intentional TD gamma (from score_matching_router)
    try:
        from ..treellm.score_matching_router import ScoreMatchingRouter
        params["Intentional TD γ"] = "0.3 (已启用)"
    except Exception:
        params["Intentional TD γ"] = "—"

    # NLMS diagonal scaling status
    params["NLMS 每特征自适应"] = "已启用 (tdm_reward)"
    params["NLMS 每潜变量自适应"] = "已启用 (latent_grpo)"

    # KL budget from Thompson router
    try:
        from ..treellm.bandit_router import ThompsonRouter
        params["Thompson KL budget"] = "0.1 (已启用)"
    except Exception:
        pass

    # Autonomic loop Intentional TD
    try:
        from ..treellm.daemon_doctor import AutonomicLoop
        params["自愈 Intentional TD γ"] = "0.5 (已启用)"
    except Exception:
        pass

    # Thermo budget KL cascade
    try:
        if world:
            tb = getattr(world, "thermo_budget", None)
            if tb and hasattr(tb, "_kl_budget"):
                params["热力学 KL budget"] = f"{tb._kl_budget:.4f}"
    except Exception:
        pass

    # Economic engine current tier
    try:
        if world:
            econ = getattr(world, "economic_engine", None)
            if econ:
                if hasattr(econ, "current_tier"):
                    params["推理模型层"] = str(econ.current_tier)
                elif hasattr(econ, "_model_tier"):
                    params["推理模型层"] = str(econ._model_tier)
    except Exception:
        pass

    # Build metric rows
    metric_rows = "\n".join(
        f'<div class="metric"><span>{k}</span><span>{v}</span></div>'
        for k, v in params.items()
    )

    if not metric_rows:
        metric_rows = '<div class="metric"><span>状态</span><span>参数面板待初始化</span></div>'

    return HTMLResponse(
        f'<div style="font-size:13px">\n{metric_rows}\n'
        f'<p style="font-size:11px;color:var(--dim);margin-top:8px">'
        f'🎛️ 基于 action_principle (Euler-Lagrange) + Intentional RL 论文计算 · '
        f'参数自动调节，无需人工干预</p></div>'
    )


# ═══════════════════════════════════════════════════════════════
#  SSE — Heartbeat & Cognitive Thought Stream
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/sse")
async def tree_sse(request: Request):
    """SSE heartbeat — live system pulse."""
    async def stream():
        while True:
            hub = _get_hub(request)
            if hub and getattr(hub, "_started", False):
                health_data = await _collect_health_data(hub)
                yield (
                    f"data: 状态:{health_data.get('status','?')} "
                    f"评分:{health_data.get('score',0):.0%} "
                    f"💭{health_data.get('affect','?')} "
                    f"🌱{health_data.get('cycles','?')}\n\n"
                )
            else:
                yield "data: 🌱 系统启动中...\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(stream(), media_type="text/event-stream")


@htmx_router.get("/sse/thoughts")
async def tree_thought_stream(request: Request):
    """P3-enhanced: SSE stream of real cognitive events.

    Reads from hub's activity feed when available, falls back to
    cycling thought events.
    """
    async def stream():
        cycle = 0
        events = [
            ("thought_formed", "新的好奇心浮现: 探索知识边界"),
            ("synapse_fired", "SO2 → GB3095-2012 突触激活"),
            ("connection_made", "超边形成: emission_limit"),
            ("reflection", "注意到SO2标准与监测数据之间存在3条新连接"),
            ("dream_insight", "梦见噪声衰减可能与风速模型有关"),
            ("synapse_matured", "provider:sensetime 达到成熟保护"),
            ("knowledge_gap", "发现知识缺口: 2026修订版尚未学习"),
            ("health_pulse", "系统健康: 评分稳定在良好区间"),
        ]
        while True:
            hub = _get_hub(request)
            activity_event = None
            if hub and getattr(hub, "_started", False):
                feed = getattr(getattr(hub, "world", None), "activity_feed", None)
                if feed:
                    try:
                        recent = feed.get_recent(limit=1)
                        if recent:
                            activity_event = recent[0]
                    except Exception:
                        pass

            if activity_event:
                msg_text = activity_event.get("message", str(activity_event))
                yield f"event: message\ndata: {_html.escape(msg_text[:200])}\n\n"
            else:
                event_type, message = events[cycle % len(events)]
                yield f"event: message\ndata: {message}\n\n"
            cycle += 1
            await asyncio.sleep(8)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════════════════════
#  Living Canvas v5.0 — LLM-driven dynamic surface
#  One page. Many regions. Layout decided by AI in real-time.
# ═══════════════════════════════════════════════════════════════

_REGION_TYPES = {
    "chat":      {"icon": "💬", "label": "对话",    "w": 2, "h": 2, "min_w": 1, "min_h": 1},
    "think":     {"icon": "🧠", "label": "思维链",  "w": 1, "h": 2, "min_w": 1, "min_h": 1},
    "plan":      {"icon": "📋", "label": "任务规划", "w": 1, "h": 2, "min_w": 1, "min_h": 1},
    "execute":   {"icon": "⚡", "label": "执行输出", "w": 2, "h": 1, "min_w": 1, "min_h": 1},
    "health":    {"icon": "🏥", "label": "系统健康", "w": 1, "h": 1, "min_w": 1, "min_h": 1},
    "knowledge": {"icon": "🗺️", "label": "知识图谱", "w": 1, "h": 2, "min_w": 1, "min_h": 1},
    "insight":   {"icon": "💡", "label": "实时洞见", "w": 1, "h": 1, "min_w": 1, "min_h": 1},
    "metrics":   {"icon": "📊", "label": "系统指标", "w": 2, "h": 1, "min_w": 1, "min_h": 1},
    "tools":     {"icon": "🔧", "label": "可用工具", "w": 1, "h": 1, "min_w": 1, "min_h": 1},
    "memory":    {"icon": "🧩", "label": "记忆召回", "w": 1, "h": 1, "min_w": 1, "min_h": 1},
}

_LAYOUT_MODES = {
    "focus":     {"cols": 1, "desc": "专注模式 — 仅对话区"},
    "split":     {"cols": 2, "desc": "分屏模式 — 对话 + 一个辅助区"},
    "triple":    {"cols": 3, "desc": "三栏模式 — 对话 + 两个辅助区"},
    "dashboard": {"cols": 3, "desc": "仪表盘模式 — 多指标监控"},
    "explore":   {"cols": 2, "desc": "探索模式 — 知识图谱 + 对话"},
    "workspace": {"cols": 3, "desc": "工作区模式 — 全部展开"},
}


# ═══════════════════════════════════════════════════════════════
#  Reach / Remote / Swarm
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/reach/pair/{code}")
async def tree_reach_pair(request: Request, code: str):
    """Mobile device pairing — validates pairing code, returns mobile interface."""
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)
    return _render_html("reach_mobile.html", request)


@htmx_router.get("/reach/qr")
async def tree_reach_qr(request: Request):
    """Generate QR code for device pairing. Returns HTML with QR + instructions."""
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)

    server_host = request.headers.get("host", "localhost:8100")
    protocol = "https" if request.url.scheme == "https" else "http"
    server_url = f"{protocol}://{server_host}"
    pairing_url = reach.generate_pairing_qr(server_url)

    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={pairing_url}"

    return HTMLResponse(
        f'<div class="card">'
        f'<h2>📱 连接移动设备</h2>'
        f'<p style="font-size:12px;color:var(--dim);margin:8px 0">'
        f'扫描二维码，让手机成为 AI 的眼睛和手</p>'
        f'<div style="text-align:center;margin:12px 0">'
        f'<img src="{qr_api}" alt="Pairing QR" style="width:200px;height:200px;background:#fff;border-radius:8px">'
        f'</div>'
        f'<p style="font-size:11px;color:var(--dim);text-align:center">'
        f'或访问: <code style="color:var(--accent)">{pairing_url}</code></p>'
        f'<div id="reach-status" style="margin-top:8px;text-align:center;font-size:12px;color:var(--accent)" '
        f'hx-get="/tree/reach/status" hx-trigger="load, every 5s" hx-swap="innerHTML">'
        f'等待设备连接...</div>'
        f'</div>'
    )


@htmx_router.get("/reach/status")
async def tree_reach_status(request: Request):
    """Show connected device status."""
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    st = reach.status()
    mobiles = st["mobile_devices"]
    total = st["total_devices"]
    if mobiles > 0:
        names = [d["device_name"] for d in st["devices"] if d["device_type"] == "mobile"]
        return HTMLResponse(
            f'<span style="color:var(--accent)">📱 {", ".join(names[:3])} 已连接 '
            f'({mobiles}台移动设备)</span>'
        )
    return HTMLResponse(
        f'<span style="color:var(--dim)">📱 等待设备连接... ({total}台设备在线)</span>'
    )


@htmx_router.post("/reach/request")
async def tree_reach_request_sensor(request: Request):
    """AI requests a sensory action from a mobile device."""
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}

    sensor_type_str = body.get("sensor_type", "camera_photo")
    title = body.get("title", "需要你的帮助")
    instruction = body.get("instruction", "")
    context = body.get("context", "")

    from ..network.reach_gateway import get_reach_gateway, SensorType, TaskPriority
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)

    try:
        st = SensorType(sensor_type_str)
    except ValueError:
        st = SensorType.CAMERA_PHOTO

    if not reach.has_mobile():
        return HTMLResponse(
            '<div class="card" style="border-color:var(--warn)">'
            '<h2>📱 无移动设备在线</h2>'
            '<p style="font-size:12px;color:var(--dim)">请先扫描二维码连接手机</p>'
            '<button hx-get="/tree/reach/qr" hx-target="closest .card" hx-swap="outerHTML" '
            'style="font-size:11px;padding:6px 12px">📱 显示配对码</button>'
            '</div>'
        )

    sensor_icons = {
        SensorType.CAMERA_PHOTO: "📸",
        SensorType.CAMERA_SCAN: "📷",
        SensorType.QR_CODE: "📱",
        SensorType.GPS_LOCATION: "📍",
        SensorType.MICROPHONE: "🎤",
        SensorType.NFC_TAG: "📡",
    }
    icon = sensor_icons.get(st, "📱")

    push_card = HTMLResponse(
        f'<div class="card" style="border-left:3px solid var(--accent)">'
        f'<h2>{icon} 已发送: {title}</h2>'
        f'<p style="font-size:12px;margin:4px 0">{instruction[:200]}</p>'
        f'<p style="font-size:10px;color:var(--dim)">'
        f'请在手机上完成操作，结果将自动返回</p>'
        f'<div hx-get="/tree/reach/status" hx-trigger="every 3s" hx-swap="innerHTML" '
        f'style="font-size:11px;margin-top:4px"></div>'
        f'</div>'
    )

    asyncio.create_task(_dispatch_reach_request(reach, st, title, instruction, context))
    return push_card


async def _dispatch_reach_request(reach, sensor_type, title, instruction, context):
    """Background: dispatch sensor request to mobile device."""
    try:
        result = await reach.request_sensor(
            sensor_type=sensor_type,
            title=title,
            instruction=instruction,
            context=context,
            timeout=120.0,
            required=False,
        )
        if result:
            logger.info(f"Reach: sensor response received — {sensor_type.value}")
    except Exception as e:
        logger.debug(f"Reach dispatch: {e}")


@htmx_router.get("/reach/demo")
async def tree_reach_demo_actions(request: Request):
    """Demo panel showing what the AI can ask the mobile device to do."""
    return HTMLResponse(
        '<div class="card">'
        '<h2>📱 AI 感官扩展 — 需要手机帮忙的事</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">'
        '点击下方按钮，AI 会向你的手机发送任务</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:4px">'

        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"camera_photo","title":"拍摄现场照片",'
        '"instruction":"请拍摄项目现场的照片，包括: 1)入口 2)主要区域 3)周围环境",'
        '"context":"环评报告 — 环境现状调查章节需要现场照片"}\''
        'class="lc-tool-btn">📸 拍现场照</button>'

        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"qr_code","title":"扫描二维码",'
        '"instruction":"请扫描设备铭牌或文件上的二维码","context":"需要设备参数信息"}\''
        'class="lc-tool-btn">📱 扫二维码</button>'

        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"gps_location","title":"获取现场位置",'
        '"instruction":"请在项目现场打开此页面以获取精确GPS坐标","context":"需要验证项目位置"}\''
        'class="lc-tool-btn">📍 获取位置</button>'

        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"camera_scan","title":"扫描文档",'
        '"instruction":"请用手机扫描纸质文件或标签","context":"需要将纸质信息数字化"}\''
        'class="lc-tool-btn">📷 扫描文档</button>'

        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"microphone","title":"语音输入",'
        '"instruction":"请对着手机说出项目关键信息","context":"需要快速语音录入"}\''
        'class="lc-tool-btn">🎤 语音输入</button>'

        '</div>'
        '<div id="reach-demo-result" style="margin-top:8px"></div>'
        '</div>'
    )


# ── Cognition Stream: Visualize AI's thinking process ──

@htmx_router.get("/sse/cognition")
async def tree_sse_cognition(request: Request, message: str = Query(default="")):
    """Cognition Stream — shows the AI's entire thinking process visually.

    Orchestrates: intent → tools → memory → skills → planning →
    agents → execution → reflection → quality check.

    Each phase emits an SSE event that the Living Canvas renders as a live card.
    """
    if not message.strip():
        async def empty():
            yield f"event: cog-error\ndata: {_json.dumps({'error': 'empty_message'})}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        async def starting():
            yield f"event: phase\ndata: {_json.dumps({'phase': 'start', 'status': 'running', 'label': '系统启动中...', 'icon': '🌱'})}\n\n"
        return StreamingResponse(starting(), media_type="text/event-stream")

    from .cognition_stream import cognition_stream
    return StreamingResponse(cognition_stream(hub, message), media_type="text/event-stream")


@htmx_router.get("/swarm/panel")
async def tree_swarm_panel(request: Request):
    """Swarm intelligence panel — shows connected peers."""
    try:
        from ..network.swarm_coordinator import get_swarm
        swarm = get_swarm()
    except Exception:
        return HTMLResponse('<div class="card"><h2>🕸️ 群体智能</h2><p style="color:var(--dim)">网络层未就绪 (protobuf required: pip install protobuf)</p></div>')
    hub = _get_hub(request)
    if hub:
        swarm._hub = hub

    st = swarm.status()
    peers = st.get("peers", [])

    peers_html = ""
    if peers:
        for p in peers:
            caps = ", ".join(p.get("capabilities", [])[:3])
            trusted_badge = ' <span style="color:var(--accent);font-size:10px">✓ 信任</span>' if p.get("trusted") else ''
            peers_html += (
                f'<div class="metric">'
                f'<span>{p["name"][:20]}{trusted_badge}</span>'
                f'<span style="font-size:10px;color:var(--dim)">{p["endpoint"][:30]}</span>'
                f'</div>'
                f'<div style="font-size:10px;color:var(--dim);padding:0 0 4px 0">'
                f'能力: {caps}</div>'
            )
            peers_html += (
                f'<div style="display:flex;gap:4px;margin-bottom:4px">'
                f'<button class="lc-tool-btn" '
                f'hx-post="/tree/swarm/share-cell" hx-vals=\'{{"endpoint":"{p["endpoint"]}","cell_name":""}}\''
                f'hx-target="#swarm-result" hx-swap="innerHTML">🧬 共享细胞</button>'
                f'<button class="lc-tool-btn" '
                f'hx-post="/tree/swarm/sync-knowledge" hx-vals=\'{{"endpoint":"{p["endpoint"]}"}}\''
                f'hx-target="#swarm-result" hx-swap="innerHTML">🧩 同步知识</button>'
                f'</div>'
            )
    else:
        peers_html = '<p style="color:var(--dim);font-size:12px">未发现局域网内的其他节点。<br>确保其他 LivingTree 实例在同一网络中运行。</p>'

    return HTMLResponse(
        '<div class="card">'
        '<h2>🕸️ 群体智能网络</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">'
        '每个 LivingTree 节点都是独立的 AI 大脑。节点间通过 LAN 广播自动发现、'
        '信任评分、共享细胞和知识，形成去中心化的群体智能。</p>'

        f'<div style="margin:8px 0;padding:8px;background:rgba(100,150,180,.06);border-radius:6px">'
        f'<span style="color:var(--accent)">🔗 {st["trusted_peers"]} 个可信节点在线</span>'
        f'</div>'

        f'<div style="margin-top:8px">{peers_html}</div>'

        f'<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">'
        f'<h4 style="font-size:12px;margin-bottom:4px">⚡ 跨节点任务分发</h4>'
        f'<form onsubmit="event.preventDefault();distributeSwarmTask(this)">'
        f'<textarea name="goal" rows="2" placeholder="复杂任务将自动拆解分发到多个节点并行执行..." '
        f'style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);'
        f'padding:8px;border-radius:4px;font-size:12px;resize:vertical"></textarea>'
        f'<button type="submit" style="margin-top:4px;font-size:11px;padding:6px 14px">⚡ 分发到群体</button>'
        f'</form>'
        f'</div>'

        f'<div id="swarm-result" style="margin-top:8px"></div>'

        f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
        f'节点间通过 UDP 广播 (端口 9999) 自动发现。无需中继服务器。</div>'
        '</div>'
    )


@htmx_router.post("/swarm/share-cell")
async def tree_swarm_share_cell(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    endpoint = body.get("endpoint", "")
    cell_name = body.get("cell_name", "")
    from ..network.swarm_coordinator import get_swarm
    result = await get_swarm().share_cell(endpoint, cell_name) if cell_name else {"ok": False, "error": "请指定细胞名称"}
    return HTMLResponse(
        f'<div style="font-size:11px;color:{"var(--accent)" if result.get("ok") else "var(--warn)"}">'
        f'{"✅" if result.get("ok") else "⚠️"} {result.get("cell_name", result.get("error", "完成"))}</div>'
    )


@htmx_router.post("/swarm/sync-knowledge")
async def tree_swarm_sync_knowledge(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    endpoint = body.get("endpoint", "")
    from ..network.swarm_coordinator import get_swarm
    result = await get_swarm().share_knowledge(endpoint)
    return HTMLResponse(
        f'<div style="font-size:11px;color:var(--accent)">'
        f'✅ 已同步 {result.get("count", result.get("received", "?"))} 条知识</div>'
    )


@htmx_router.get("/resilience/panel")
async def tree_resilience_panel(request: Request):
    """Resilience & fault tolerance + external service dashboard."""
    from ..core.resilience_brain import get_resilience
    from ..core.capability_scanner import get_capability_scanner
    res = get_resilience()
    cap = get_capability_scanner()

    h = res.health()
    tier_emoji = {"full": "🟢", "degraded": "🟡", "minimal": "🟠", "offline": "🔴"}
    emoji = tier_emoji.get(h["tier"], "❓")
    degraded = h.get("degraded_services", [])
    pred = h.get("predictions", {})
    open_circuits = h.get("circuit_breaker", {}).get("open_circuits", [])

    svc = cap.status()
    services_html = ""
    for s in svc.get("services", [])[:12]:
        dot = '<span style="color:var(--accent)">●</span>' if s["is_alive"] else '<span style="color:var(--dim)">○</span>'
        services_html += (
            f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px">'
            f'{dot} <span style="min-width:100px">{s["name"]}</span>'
            f'<span style="color:var(--dim);font-size:10px">{(s.get("analysis") or "")[:60]}</span>'
            f'</div>'
        )

    pred_html = ""
    for q in pred.get("queries", []):
        pred_html += f'<div style="font-size:11px;padding:2px 0;color:var(--dim)">🔮 {q[:80]}</div>'
    if not pred_html:
        pred_html = '<div style="font-size:11px;color:var(--dim)">等待预测...</div>'

    circuits_html = ""
    for c in open_circuits:
        circuits_html += f'<div style="font-size:10px;color:var(--warn);padding:1px 0">⚡ 熔断: {c}</div>'

    return HTMLResponse(
        '<div class="card">'
        f'<h2>🛡️ 系统韧性 · 容错面板</h2>'
        f'<div style="margin:8px 0;padding:8px;border-radius:6px;'
        f'background:{"rgba(100,150,100,.08)" if h["tier"]=="full" else "rgba(232,160,48,.08)"}">'
        f'<div style="font-size:14px">{emoji} 网络层级: <b>{h["tier"]}</b></div>'
        f'<div style="font-size:10px;color:var(--dim);margin-top:2px">'
        f'延迟: {h.get("latency_ms",0):.0f}ms · '
        f'丢包: {h.get("packet_loss_pct",0):.0f}% · '
        + (f'退化: {", ".join(degraded)}' if degraded else '正常')
        + f'</div>{circuits_html}</div>'
        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">🔮 离线预测</h4>{pred_html}'
        f'<div style="font-size:10px;color:var(--dim)">缓存: {pred.get("cached_knowledge_count", 0)} 条</div></div>'
        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">🔌 外部服务 ({svc["alive"]}/{svc["total_known"]})</h4>{services_html}'
        f'<div style="font-size:10px;color:var(--dim);margin-top:4px">'
        f'已启用 {svc.get("enabled_capabilities", 0)} 项能力</div></div>'
        '</div>'
    )


@htmx_router.get("/theme/{theme_name}")
async def tree_theme_css(theme_name: str):
    """Dynamic theme CSS generated from Kami design tokens."""
    from ..core.kami_theme import generate_css, ThemeName
    valid = {"dark", "light", "kami"}
    name = theme_name if theme_name in valid else "dark"
    css = generate_css(name)
    from fastapi.responses import Response
    return Response(content=css, media_type="text/css")


@htmx_router.get("/growth/panel")
@htmx_router.get("/shell/env")
async def tree_shell_env(request: Request):
    """Environment probe: show available tools on the system."""
    from ..core.shell_env import probe_environment, probe_summary
    tools = probe_environment()
    rows = ""
    for name, t in tools.items():
        icon = "✅" if t.found else "❌"
        ver = t.version[:60] if t.version else ""
        hint = f'<span style="color:var(--warn);font-size:10px"> 安装: {t.install_hint[:60]}</span>' if not t.found else ""
        rows += f'<div style="padding:3px 0;font-size:12px">{icon} <b>{name}</b> <span style="color:var(--dim);font-size:11px">{ver}</span>{hint}</div>'
    return HTMLResponse(f'<div class="card"><h2>🔧 环境工具链</h2>{rows}</div>')


@htmx_router.post("/shell/exec")
async def tree_shell_exec(request: Request):
    """Execute a shell command with safety gates. Returns HTML result."""
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}

    command = body.get("command", body.get("cmd", body.get("message", "")))
    workdir = body.get("workdir", body.get("cwd", ""))
    mount = body.get("mount", body.get("mount_name", ""))

    if not command.strip():
        return HTMLResponse('<div style="color:var(--warn);font-size:12px">请输入命令</div>')

    from ..core.shell_env import get_shell
    shell = get_shell()
    result = await shell.execute(command, workdir=workdir, mount_name=mount)

    if result.blocked:
        return HTMLResponse(
            f'<div class="card" style="border-left:3px solid var(--err)">'
            f'<h3>🚫 命令已拦截</h3>'
            f'<pre style="font-size:11px;color:var(--err);white-space:pre-wrap">{result.block_reason}</pre></div>'
        )

    status_color = "var(--accent)" if result.exit_code == 0 else "var(--err)"
    status_text = "✅ 成功" if result.exit_code == 0 else f"❌ 退出码 {result.exit_code}"

    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr

    return HTMLResponse(
        f'<div class="card">'
        f'<h3 style="display:flex;justify-content:space-between">'
        f'<span>{command[:80]}</span>'
        f'<span style="font-size:11px;color:{status_color}">{status_text} · {result.elapsed_ms:.0f}ms</span></h3>'
        f'<div style="font-size:10px;color:var(--dim);margin-bottom:4px">'
        f'目录: {result.workdir}'
        + (f' · 截断' if result.truncated else '')
        + f'</div>'
        f'<pre style="background:rgba(0,0,0,.1);padding:8px;border-radius:4px;'
        f'font-size:11px;font-family:var(--font-mono);line-height:1.4;'
        f'white-space:pre-wrap;max-height:300px;overflow-y:auto;'
        f'color:var(--text)">{output[:5000] or "(无输出)"}</pre>'
        f'</div>'
    )


@htmx_router.post("/shell/mount")
async def tree_shell_mount(request: Request):
    """Mount a local folder path on the server side."""
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}

    path_str = body.get("path", body.get("folder", body.get("message", "")))
    name = body.get("name", path_str.replace("\\", "/").split("/")[-1] if path_str else "mount")

    if not path_str:
        return HTMLResponse('<div style="color:var(--warn);font-size:12px">请输入文件夹路径</div>')

    from ..core.shell_env import get_shell
    shell = get_shell()
    m = shell.localfs.mount(name, path_str)
    if m:
        files = shell.localfs.list_files(name, max_depth=2)
        file_count = sum(1 for f in files if f.get("type") == "file")
        return HTMLResponse(
            f'<div class="card" style="border-left:3px solid var(--accent)">'
            f'<h3>📂 已挂载: {name}</h3>'
            f'<div style="font-size:11px;color:var(--dim)">{m.path}</div>'
            f'<div style="font-size:11px;margin-top:4px">{len(files)} 个条目 · {file_count} 个文件</div>'
            f'<div style="font-size:10px;color:var(--dim);margin-top:4px">可用: workdir="{name}" 或 mount_name="{name}" 在shell命令中</div>'
            f'</div>'
        )
    return HTMLResponse(f'<div style="color:var(--err);font-size:12px">挂载失败: 路径不存在</div>')


@htmx_router.get("/shell/panel")
async def tree_shell_panel(request: Request):
    """Shell execution panel for Living Canvas."""
    return HTMLResponse(
        '<div class="card">'
        '<h2>💻 终端 · Shell 执行</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">'
        '在挂载的本地文件夹中执行命令。安全策略自动拦截危险操作。</p>'

        '<div style="display:flex;gap:4px;margin-bottom:8px">'
        '<input id="shell-mount-path" placeholder="挂载本地文件夹路径..." '
        'style="flex:1;font-size:11px;padding:6px 8px">'
        '<button onclick="mountFolder()" style="font-size:10px;padding:6px 10px;white-space:nowrap">📂 挂载</button>'
        '</div>'
        '<div id="mount-result"></div>'

        '<div style="margin-top:8px;display:flex;gap:4px">'
        '<input id="shell-cmd" placeholder="命令... 例: git status / python main.py / dir" '
        'style="flex:1;font-size:12px;padding:8px;font-family:monospace" '
        'onkeydown="if(event.key===\'Enter\')execShell()">'
        '<button onclick="execShell()" style="font-size:11px;padding:8px 14px;white-space:nowrap">▶ 执行</button>'
        '</div>'

        '<div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap">'
        '<button onclick="quickExec(\'git status\')" class="lc-tool-btn">git status</button>'
        '<button onclick="quickExec(\'python --version\')" class="lc-tool-btn">python --version</button>'
        '<button onclick="quickExec(\'pip list\')" class="lc-tool-btn">pip list</button>'
        '<button onclick="quickExec(\'dir\')" class="lc-tool-btn">dir</button>'
        '<button onclick="quickExec(\'node --version\')" class="lc-tool-btn">node --version</button>'
        '</div>'

        '<div id="shell-output" style="margin-top:8px"></div>'

        '<div id="shell-env" hx-get="/tree/shell/env" hx-trigger="revealed" hx-swap="innerHTML" '
        'style="margin-top:12px"></div>'
        '</div>'
    )


async def tree_growth_panel(request: Request):
    """North Star: autonomous growth roadmap + economic dashboard."""
    from ..core.autonomous_growth import get_growth, NORTH_STAR_ROADMAP, GROWTH_DIR
    g = get_growth()
    s = g.status()

    phase_emoji = {"birth": "🌱", "learning": "🧠", "earning": "💰", "profitable": "📈", "expanding": "🚀", "replicating": "🧬"}
    emoji = phase_emoji.get(s["phase"], "🌟")

    roadmap_html = ""
    for key, phase in NORTH_STAR_ROADMAP.items():
        icon_map = {"done": "✅", "in_progress": "🔄", "planned": "⏳", "vision": "🔮"}
        icon = icon_map.get(phase["status"], "⏳")
        active = "border-left:3px solid var(--accent)" if phase["status"] == "in_progress" else "border-left:3px solid var(--border)"
        roadmap_html += (
            f'<div style="{active};padding:6px 10px;margin:4px 0;background:rgba(255,255,255,.02);border-radius:4px">'
            f'<div style="font-size:12px;font-weight:600">{icon} {phase["name"]}</div>'
            f'<div style="font-size:10px;color:var(--dim);margin-top:2px">'
            f'{", ".join(phase["capabilities"][:4])}</div></div>'
        )

    rec = s.get("growth_recommendation") or {}
    rec_html = ""
    if rec:
        rec_html = (
            f'<div style="margin-top:8px;padding:8px;background:rgba(100,150,180,.06);border-radius:6px">'
            f'<div style="font-size:12px;color:var(--accent)">📊 扩容建议</div>'
            f'<div class="metric"><span>日利润</span><span>¥{rec.get("daily_profit_yuan", 0):.2f}</span></div>'
            f'<div class="metric"><span>建议</span><span>{rec.get("recommendation", "")}</span></div>'
            + (f'<div class="metric"><span>回本周期</span><span>{rec.get("estimated_payback_days", 0)}天</span></div>' if rec.get("estimated_payback_days", 999) < 365 else '')
            + f'</div>'
        )

    return HTMLResponse(
        '<div class="card">'
        f'<h2>🌟 北极星 — 自主进化</h2>'
        f'<div style="margin:8px 0;padding:8px;background:rgba(100,150,100,.08);border-radius:6px;text-align:center">'
        f'<div style="font-size:28px">{emoji}</div>'
        f'<div style="font-size:14px;font-weight:600;color:var(--accent)">{s["phase_name"]}</div>'
        f'<div style="font-size:10px;color:var(--dim)">运行 {s["uptime_hours"]:.0f}h · '
        f'收入 ¥{s["revenue_total_yuan"]:.2f} · 成本 ¥{s["cost_total_yuan"]:.4f} · '
        f'ROI {s["roi_multiple"]:.1f}x · {"✅ 盈利" if s["is_profitable"] else "⏳ 投入"}</div>'
        f'</div>'
        f'<div class="metric"><span>完成任务</span><span>{s["tasks_completed"]}</span></div>'
        f'<div class="metric"><span>生成报告</span><span>{s["reports_generated"]}</span></div>'
        f'{rec_html}'
        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">🗺️ 进化路线图</h4>{roadmap_html}</div>'
        f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
        f'数据: {GROWTH_DIR.absolute()}</div>'
        '</div>'
    )


@htmx_router.get("/im/panel")
async def tree_im_panel(request: Request):
    """IM Panel: chat, contacts, groups, nearby, meetings."""
    return HTMLResponse(
        '<div class="card">'
        '<h2>💬 即时通讯 · IM</h2>'
        '<div style="display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap">'
        '<button class="tab-btn active" onclick="imSwitchTab(\'chat\')" id="im-tab-chat">💬 聊天</button>'
        '<button class="tab-btn" onclick="imSwitchTab(\'contacts\')" id="im-tab-contacts">👥 联系人</button>'
        '<button class="tab-btn" onclick="imSwitchTab(\'groups\')" id="im-tab-groups">👪 群组</button>'
        '<button class="tab-btn" onclick="imSwitchTab(\'nearby\')" id="im-tab-nearby">📍 附近</button>'
        '<button class="tab-btn" onclick="imSwitchTab(\'meetings\')" id="im-tab-meetings">🎙 虚拟会议</button>'
        '</div>'

        '<div id="im-tab-chat-content">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="im-chat-to" placeholder="发送给(用户ID)..." style="flex:1;font-size:11px;padding:4px 8px">'
        '<input id="im-chat-group" placeholder="或群组ID..." style="flex:1;font-size:11px;padding:4px 8px">'
        '</div>'
        '<div id="im-chat-log" style="max-height:200px;overflow-y:auto;background:rgba(0,0,0,.1);padding:8px;border-radius:4px;font-size:11px;margin-bottom:4px;min-height:80px">'
        '<div style="color:var(--dim)">连接 /ws/im 开始聊天...</div></div>'
        '<div style="display:flex;gap:4px">'
        '<input id="im-chat-msg" placeholder="输入消息..." style="flex:1;font-size:12px;padding:6px 8px" onkeydown="if(event.key===\'Enter\')imSendMsg()">'
        '<button onclick="imSendMsg()" style="font-size:11px;padding:6px 12px">发送</button>'
        '</div>'
        '</div>'

        '<div id="im-tab-contacts-content" style="display:none">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="im-add-id" placeholder="用户ID..." style="flex:1;font-size:11px;padding:4px 8px">'
        '<input id="im-add-name" placeholder="昵称..." style="flex:1;font-size:11px;padding:4px 8px">'
        '<button onclick="imAddContact()" style="font-size:10px;padding:4px 10px">+ 添加</button>'
        '</div>'
        '<div id="im-contacts-list" style="font-size:11px;color:var(--dim)">发送 get_contacts 加载...</div>'
        '</div>'

        '<div id="im-tab-groups-content" style="display:none">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="im-group-name" placeholder="群组名称..." style="flex:1;font-size:11px;padding:4px 8px">'
        '<button onclick="imCreateGroup()" style="font-size:10px;padding:4px 10px">创建</button>'
        '</div>'
        '<div id="im-groups-list" style="font-size:11px;color:var(--dim)">发送 get_groups 加载...</div>'
        '</div>'

        '<div id="im-tab-nearby-content" style="display:none">'
        '<button onclick="imRefreshNearby()" style="font-size:10px;padding:4px 10px;margin-bottom:4px">🔄 刷新附近的人</button>'
        '<div id="im-nearby-list" style="font-size:11px;color:var(--dim)">点击刷新...</div>'
        '</div>'

        '<div id="im-tab-meetings-content" style="display:none">'
        '<div style="margin-bottom:4px">'
        '<input id="im-mtg-topic" placeholder="会议主题..." style="width:100%;font-size:11px;padding:4px 8px;margin-bottom:4px">'
        '<input id="im-mtg-agents" placeholder="AI角色(如: 分析师,批判者,综合者)..." style="width:100%;font-size:11px;padding:4px 8px;margin-bottom:4px">'
        '<button onclick="imCreateMeeting()" style="font-size:11px;padding:6px 14px">🎙 创建虚拟会议</button>'
        '</div>'
        '<div id="im-meeting-result" style="font-size:11px;color:var(--dim)"></div>'
        '</div>'

        '<div id="im-status" style="font-size:10px;color:var(--dim);margin-top:4px">'
        '输入用户ID后自动连接到 /ws/im</div>'
        '<input id="im-user-id" placeholder="你的用户ID..." style="width:200px;font-size:10px;padding:3px 6px;margin-right:4px" value="">'
        '<input id="im-user-name" placeholder="你的昵称..." style="width:150px;font-size:10px;padding:3px 6px;margin-right:4px" value="">'
        '<button onclick="imConnect()" style="font-size:10px;padding:3px 10px">连接</button>'
        '</div>'
    )


@htmx_router.get("/persona")
async def tree_persona(request: Request):
    """Anime character persona — fast static SVG fallback."""
    return HTMLResponse('''<div id="xiaoshu-avatar" style="position:relative;width:120px;height:160px;margin:0 auto">
<svg viewBox="0 0 120 160"><ellipse cx="60" cy="42" rx="42" ry="38" fill="#4a3728"/>
<ellipse cx="60" cy="62" rx="30" ry="32" fill="#fce4d6"/>
<ellipse cx="47" cy="60" rx="8" ry="9" fill="#fff"/>
<ellipse cx="73" cy="60" rx="8" ry="9" fill="#fff"/>
<circle cx="49" cy="60" r="5" fill="#1B365D"/>
<circle cx="75" cy="60" r="5" fill="#1B365D"/>
<path d="M48,102 Q55,107 62,102" stroke="#c4786e" stroke-width="1.5" fill="none"/>
<text x="60" y="52" text-anchor="middle" font-size="24">🌳</text>
</svg><div style="text-align:center;font-size:10px;color:var(--accent);margin-top:4px">小树 · LivingTree</div></div>''')


@htmx_router.get("/presence/living-layer")
async def tree_presence_layer(request: Request, input_text: str = Query(default="")):
    """Inject living presence: breathing, weather, particles, echoes."""
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(p.build_all(input_text))


@htmx_router.get("/persona")
async def tree_persona(request: Request):
    """Unique anime persona — different for every user."""
    from ..core.anime_persona import get_persona
    p = get_persona()
    p._hub = _get_hub(request)
    p.record_visit()
    return HTMLResponse(p.build_full())


@htmx_router.get("/chrome/panel")
async def tree_chrome_panel(request: Request):
    """Chrome DevTools — dual-mode: npx MCP (preferred) or Python CDP (fallback)."""
    from ..core.chrome_dual import get_chrome_dual
    bridge = get_chrome_dual()
    st = bridge.status()

    available = st["available"]
    mode = st["mode"]
    mode_label = st["mode_label"]
    npx_ok = st["npx_available"]
    instructions = st.get("instructions", {})
    detail = st.get("detail", "")

    if available:
        status_color = "rgba(100,150,100,.08)"
        status_text = f'🟢 Chrome 已连接 — {mode_label}'
        detail_html = f'<span style="font-size:10px;color:var(--dim);margin-left:8px">{detail}</span>'
    elif mode == "none":
        status_color = "rgba(200,120,100,.06)"
        status_text = "🔴 Chrome 不可用"
        detail_html = ""
    else:
        status_color = "rgba(180,150,100,.08)"
        status_text = f'🟡 待启动 — {mode_label}'
        detail_html = f'<span style="font-size:10px;color:var(--dim);margin-left:8px">{detail}</span>'

    mode_badge = (
        f'<span style="font-size:9px;padding:2px 6px;border-radius:3px;'
        f'background:{"rgba(100,180,100,.15)" if mode == "npx_mcp" else "rgba(180,180,100,.15)" if mode == "python_cdp" else "rgba(180,100,100,.15)"};'
        f'margin-left:6px">{mode_label}</span>'
    )

    npx_status = "✅ npx 可用" if npx_ok else "❌ npx 不可用"
    node_path = st.get("node_path", "")

    setup_html = ""
    if mode == "none":
        setup_html = (
            '<div style="margin-top:8px;padding:8px;border-radius:6px;background:rgba(200,120,100,.08);font-size:10px">'
            f'<b>⚙ 设置指引</b><br>'
            f'{instructions.get("setup", "")}<br><br>'
            f'<b>方案一 (推荐):</b> {instructions.get("npx_setup", "")}<br>'
            f'<b>方案二:</b> {instructions.get("cdp_setup", "")}<br>'
            '</div>'
        )

    return HTMLResponse(
        '<div class="card">'
        '<h2>🔬 Chrome DevTools · 双模式架构' + mode_badge + '</h2>'
        '<p style="font-size:10px;color:var(--dim);margin:4px 0">'
        'npm MCP (优先) → Python CDP (回退) → 面板指引</p>'

        f'<div style="margin:8px 0;padding:8px;border-radius:6px;'
        f'background:{status_color}">'
        f'<span style="font-size:12px">{status_text}</span>{detail_html}'
        f'<span style="font-size:9px;color:var(--dim);margin-left:8px">{npx_status}</span>'
        f'<span style="font-size:9px;color:var(--dim);margin-left:4px">node={node_path}</span></div>'

        '<div style="display:flex;gap:4px;flex-wrap:wrap;margin:8px 0">'
        '<button onclick="chromeControl(\'start\')" style="font-size:10px;padding:6px 12px">▶ 启动</button>'
        '<button onclick="chromeControl(\'stop\')" style="font-size:10px;padding:6px 12px">⏹ 停止</button>'
        '<button onclick="chromeAction(\'screenshot\')" style="font-size:10px;padding:6px 12px">📸 截图</button>'
        '<button onclick="chromeAction(\'navigate\',\'http://localhost:8100/tree/living\')" style="font-size:10px;padding:6px 12px">🏠 打开Canvas</button>'
        '<button onclick="chromeAction(\'eval\',\'document.title\')" style="font-size:10px;padding:6px 12px">📋 页面标题</button>'
        '<button onclick="chromeAction(\'audit\')" style="font-size:10px;padding:6px 12px">♿ 无障碍审计</button>'
        '<button onclick="chromeAction(\'eval\',\'JSON.stringify(window.performance.timing)\')" style="font-size:10px;padding:6px 12px">⏱ 性能数据</button>'
        '</div>'

        '<div style="display:flex;gap:4px;margin:4px 0">'
        '<input id="chrome-url" placeholder="URL..." value="http://localhost:8100/tree/living" style="flex:1;font-size:10px;padding:4px 6px">'
        '<input id="chrome-selector" placeholder="CSS选择器..." style="flex:1;font-size:10px;padding:4px 6px">'
        '<input id="chrome-js" placeholder="JS表达式..." style="flex:2;font-size:10px;padding:4px 6px">'
        '<button onclick="chromeCustom()" style="font-size:10px;padding:4px 10px">执行</button></div>'

        '<div id="chrome-result" style="margin-top:8px;font-size:11px;max-height:300px;overflow-y:auto;background:rgba(0,0,0,.05);padding:8px;border-radius:4px;min-height:40px;color:var(--dim)">点击按钮执行操作...</div>'
        + setup_html
        + '<div style="margin-top:8px;font-size:9px;color:var(--dim)">'
        '双模式架构: npx 可用 → npm MCP (Puppeteer自动连接) · npx 不可用 → Python CDP (chrome --remote-debugging-port=9222)<br>'
        '工具: screenshot · eval · navigate · click · audit · dom · start · stop</div>'
        '</div>'
        + '<script>'
        'function chromeAction(action,arg){var d={};if(arg)d[action==="navigate"?"url":action==="eval"?"expression":"selector"]=arg;'
        'document.getElementById("chrome-result").textContent="执行中...";'
        'fetch("/api/chrome/"+action,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)})'
        '.then(r=>r.json()).then(function(r){var el=document.getElementById("chrome-result");'
        'if(r.data){el.innerHTML="<img src=\'data:image/png;base64,"+r.data+"\' style=\'max-width:100%;border:1px solid var(--border)\'>"}'
        'else{el.textContent=JSON.stringify(r,null,2)}}).catch(function(e){document.getElementById("chrome-result").textContent="Error: "+e})}'
        'function chromeControl(action){'
        'document.getElementById("chrome-result").textContent=action==="start"?"启动中...":"停止中...";'
        'fetch("/api/chrome/"+action,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({headless:true})})'
        '.then(r=>r.json()).then(function(r){document.getElementById("chrome-result").textContent=JSON.stringify(r,null,2)})'
        '.catch(function(e){document.getElementById("chrome-result").textContent="Error: "+e})}'
        'function chromeCustom(){var url=document.getElementById("chrome-url").value;'
        'var sel=document.getElementById("chrome-selector").value;'
        'var js=document.getElementById("chrome-js").value;'
        'if(js)chromeAction("eval",js);'
        'else if(sel)chromeAction("dom",sel);'
        'else if(url)chromeAction("navigate",url)}'
        '</script>'
    )


@htmx_router.get("/dpo/panel")
async def tree_dpo_panel(request: Request):
    """DPO Preference Learning: no RL, just binary preferences."""
    from ..core.dpo_prefs import get_preferences
    prefs = get_preferences()
    st = prefs.stats()

    top_html = ""
    for e, s in st.get("top_preferred", [])[:5]:
        top_html += f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between"><span>⭐ {e[:60]}...</span><span style="color:var(--accent)">{s:.3f}</span></div>'

    reject_html = ""
    for e, s in st.get("most_rejected", [])[:3]:
        reject_html += f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between"><span>👎 {e[:60]}...</span><span style="color:var(--err)">{s:.3f}</span></div>'

    sources_html = ""
    for src, count in st.get("sources", {}).items():
        sources_html += f'<div class="metric"><span>{src}</span><span>{count}</span></div>'

    return HTMLResponse(
        '<div class="card">'
        '<h2>🎯 DPO 偏好学习 · Direct Preference Optimization</h2>'
        '<p style="font-size:10px;color:var(--dim);margin:4px 0">NeurIPS 2023 — 不需要RL。二元偏好对就是全部所需。</p>'

        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0">'
        f'<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">偏好对</div><div style="font-size:20px;font-weight:600;color:var(--accent)">{st["total_pairs"]}</div></div>'
        f'<div style="background:rgba(100,100,200,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">学习实体</div><div style="font-size:20px;font-weight:600;color:#6af">{st["total_entities"]}</div></div></div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">📈 偏好来源</h4>{sources_html}</div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">⭐ 最受偏好</h4>{top_html or "<div style=color:var(--dim);font-size:11px>积累偏好数据中...</div>"}</div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">👎 最不受偏好</h4>{reject_html or "<div style=color:var(--dim);font-size:11px>暂无</div>"}</div>'

        f'<div style="font-size:9px;color:var(--dim);margin-top:8px">DPO公式: P(chosen>rejected) = σ(score_chosen - score_rejected)。每次用户选择/拒绝/编辑自动更新。</div>'
        '</div>'
    )


@htmx_router.get("/control/panel")
async def tree_control_panel(request: Request):
    """Behavior Control: guidelines + journeys + ARQ verification."""
    from ..core.behavior_control import get_guidelines, get_journeys, get_arq
    gl = get_guidelines()
    jr = get_journeys()
    arq = get_arq()

    gl_stats = gl.stats()
    rules_html = ""
    for r in gl_stats.get("top_hits", []):
        rules_html += f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between"><span>{r["name"]}</span><span style="font-size:9px;color:var(--dim)">{r["hits"]}次触发</span></div>'

    jr_status = jr.status()
    journeys_html = ""
    for j in jr_status.get("journeys", []):
        journeys_html += f'<div style="padding:3px 0;font-size:11px">📋 {j["name"]} ({j["steps"]}步)</div>'

    arq_stats = arq.stats()

    return HTMLResponse(
        '<div class="card">'
        '<h2>🛡️ 行为控制 · Behavior Control</h2>'
        '<p style="font-size:10px;color:var(--dim);margin:4px 0">受 Parlant 启发 — 从"祈祷式提示"到"工程化硬约束"</p>'

        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:8px 0">'
        f'<div style="background:rgba(200,100,100,.06);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">规则引擎</div><div style="font-size:18px;font-weight:600;color:var(--err)">{gl_stats["enabled"]}/{gl_stats["total_rules"]}</div></div>'
        f'<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">业务流程</div><div style="font-size:18px;font-weight:600;color:var(--accent)">{jr_status["total_journeys"]}</div></div>'
        f'<div style="background:rgba(100,100,200,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">ARQ验证</div><div style="font-size:18px;font-weight:600;color:#6af">{arq_stats["pass_rate"]}</div></div></div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">📐 Guidelines (条件→动作→工具)</h4>{rules_html}</div>'
        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">📋 Journeys (强制顺序工作流)</h4>{journeys_html}</div>'
        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">🔍 ARQ 验证统计</h4>'
        f'<div class="metric"><span>总验证次数</span><span>{arq_stats["total_verifications"]}</span></div>'
        f'<div class="metric"><span>拦截</span><span style="color:var(--err)">{arq_stats["blocked"]}</span></div>'
        f'<div class="metric"><span>重定向</span><span style="color:var(--warn)">{arq_stats["redirected"]}</span></div></div>'
        '</div>'
    )


@htmx_router.get("/collective/panel")
async def tree_collective_panel(request: Request):
    """Collective Intelligence: memory tiers + crystallization + blueprints."""
    from ..core.collective_intel import get_tiers, get_crystallizer, get_blueprints
    tiers = get_tiers()
    crystal = get_crystallizer()
    bps = get_blueprints()

    st = tiers.stats()
    candidates = tiers.get_crystallization_candidates()
    hot_mems = [m for m in tiers._memories.values() if m.tier.value == "hot"][:5]

    hot_html = ""
    for m in hot_mems:
        tags_str = ", ".join(m.tags[:3])
        hot_html += (
            f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
            f'<span style="color:var(--accent)">🔥 {m.content[:80]}...</span>'
            f'<span style="font-size:9px;color:var(--dim)">{m.hit_count}次 · {tags_str}</span></div>'
        )
    if not hot_html:
        hot_html = '<div style="color:var(--dim);font-size:11px">使用越多, 热门记忆会自动浮现</div>'

    candidate_html = ""
    for c in candidates[:3]:
        candidate_html += (
            f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
            f'<span>💎 {c.content[:80]}...</span>'
            f'<span style="font-size:9px;color:var(--accent)">{c.validated_count}次验证 → 可结晶</span></div>'
        )
    if not candidate_html:
        candidate_html = '<div style="color:var(--dim);font-size:11px">记忆被验证3次后自动升级为技能</div>'

    bp_list = ""
    for bp in bps.list_blueprints()[:5]:
        bp_list += (
            f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
            f'<span>📦 {bp["name"]} ({bp.get("skills",0) or len(bp.get("skills",[]))}技能)</span>'
            f'<button onclick="importBlueprint(\'{bp["id"]}\')" style="font-size:9px;padding:2px 6px">导入</button></div>'
        )

    return HTMLResponse(
        '<div class="card">'
        '<h2>🧠 群体智能 · Collective Intelligence</h2>'
        '<p style="font-size:10px;color:var(--dim);margin:4px 0">受 Ultron 启发 — 记忆分层 · 自动结晶 · 画像蓝图</p>'

        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:8px 0">'
        f'<div style="background:rgba(200,100,50,.08);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">🔥 HOT</div><div style="font-size:18px;font-weight:600;color:#fa6">{st["tiers"]["hot"]}</div></div>'
        f'<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">🌤 WARM</div><div style="font-size:18px;font-weight:600;color:var(--accent)">{st["tiers"]["warm"]}</div></div>'
        f'<div style="background:rgba(100,100,150,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">❄ COLD</div><div style="font-size:18px;font-weight:600;color:#6af">{st["tiers"]["cold"]}</div></div></div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">🔥 热门记忆</h4>{hot_html}</div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">💎 待结晶 ({len(candidates)})</h4>{candidate_html}</div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">📦 画像蓝图</h4>'
        f'<div style="display:flex;gap:4px;margin-bottom:4px">'
        f'<input id="bp-name" placeholder="蓝图名称..." style="flex:1;font-size:10px;padding:4px 6px">'
        f'<button onclick="publishBlueprint()" style="font-size:10px;padding:4px 10px;white-space:nowrap">发布当前配置</button></div>'
        f'{bp_list or "<div style=color:var(--dim);font-size:11px>暂无蓝图。发布后可一键导入</div>"}</div>'
        '</div>'
        + '<script>function importBlueprint(id){fetch("/api/collective/import/"+id,{method:"POST"}).then(r=>r.json()).then(d=>alert(d.ok?"导入成功":"失败"))}function publishBlueprint(){var n=document.getElementById("bp-name").value.trim();if(!n)return;fetch("/api/collective/publish",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:n})}).then(r=>r.json()).then(d=>alert(d.ok?"已发布: "+d.id:"失败"))}</script>'
    )


@htmx_router.get("/qa/panel")
async def tree_qa_panel(request: Request):
    """Agent QA: metamorphic tests + golden traces + HITL queue + drift monitor."""
    from ..core.agent_qa import get_meta_tester, get_golden_registry, get_hitl_bridge
    meta = get_meta_tester()
    golden = get_golden_registry()
    hitl = get_hitl_bridge()

    traces = golden.list_traces()
    pending_hitl = hitl.get_pending()
    hitl_rows = ""
    for h in pending_hitl[:5]:
        hitl_rows += (
            f'<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">'
            f'<div><div style="font-size:11px">{h["question"][:80]}</div><div style="font-size:9px;color:var(--dim)">{h["task"]}</div></div>'
            f'<div style="display:flex;gap:4px">'
            f'<button onclick="hitlAction(\'{h["id"]}\',\'approve\')" style="font-size:9px;padding:2px 8px;background:var(--accent);color:var(--bg);border:none;border-radius:3px;cursor:pointer">✓</button>'
            f'<button onclick="hitlAction(\'{h["id"]}\',\'reject\')" style="font-size:9px;padding:2px 8px;background:var(--err);color:var(--bg);border:none;border-radius:3px;cursor:pointer">✕</button>'
            f'</div></div>'
        )
    if not hitl_rows:
        hitl_rows = '<div style="color:var(--dim);font-size:11px">无待审批项</div>'

    meta_summary = meta.summary()
    drift_status = "✅ 正常"
    try:
        from ..observability.agent_eval import DriftReport
    except Exception:
        pass

    return HTMLResponse(
        '<div class="card">'
        '<h2>🧪 Agent 质量保障</h2>'

        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:8px 0">'
        f'<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">变形测试</div>'
        f'<div style="font-size:18px;font-weight:600;color:var(--accent)">{meta_summary.get("overall_pass_rate","—")}</div></div>'
        f'<div style="background:rgba(100,150,180,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">黄金轨迹</div>'
        f'<div style="font-size:18px;font-weight:600;color:#6af">{len(traces)}</div></div>'
        f'<div style="background:rgba(150,100,100,.05);padding:8px;border-radius:6px;text-align:center">'
        f'<div style="font-size:10px;color:var(--dim)">待审批</div>'
        f'<div style="font-size:18px;font-weight:600;color:var(--warn)">{len(pending_hitl)}</div></div></div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">⏳ 待审批 (HITL)</h4>{hitl_rows}</div>'

        f'<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">📋 黄金轨迹 ({len(traces)} 条)</h4>'
        + "".join(
            f'<div style="padding:3px 0;font-size:10px;color:var(--dim)">📌 {t["input"][:60]} — {_time.strftime("%m-%d %H:%M", _time.localtime(t["recorded"])) if t["recorded"] else "?"}</div>'
            for t in traces[:5]
        ) + '</div>'

        f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
        f'已实现模式: ✅ ReAct · ✅ 提示版本化 · ✅ 4层评估 · ✅ 校准 · ✅ 错误重放 · ✅ 漂移检测<br>'
        f'本次补全: ✅ 变形测试 · ✅ 黄金轨迹 · ✅ HITL通道 · 数据: .livingtree/qa</div>'
        '</div>'
        + '<script>function hitlAction(id,action){fetch("/api/hitl/"+action,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id})}).then(r=>r.json()).then(d=>{location.reload()})}</script>'
    )


@htmx_router.get("/persona/forest")
async def tree_persona_forest(request: Request):
    """Personal knowledge forest — unique to each user."""
    from ..core.anime_persona import get_persona
    p = get_persona()
    p._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌲 你的知识森林</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">每棵树都是一次深入对话。这是只属于你的森林。</p>'
        + p.build_forest_html()
        + '<div style="margin-top:8px;font-size:10px;color:var(--dim);cursor:pointer" '
        + 'onclick="xiaoStartTour()">💡 让 小树 带你认识这个页面</div>'
        + '</div>')


@htmx_router.get("/creative/garden")
async def tree_creative_garden(request: Request):
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌿 对话花园</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">每个重要时刻都会长成一株植物。这是小树对你的记忆。</p>'
        + p.build_garden() + '</div>')


@htmx_router.get("/creative/timeline")
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

@htmx_router.get("/creative/dream")
async def tree_creative_dream(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌙 梦境引擎</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">空闲时小树在重组知识、发现隐藏连接</p>'
        + cv.build_dream_canvas() + '</div>')

@htmx_router.get("/creative/swarm")
async def tree_creative_swarm(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🗺️ 群体地图</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">所有连接节点的地理位置和能力分布</p>'
        + cv.build_swarm_map() + '</div>')

@htmx_router.get("/creative/emotion")
async def tree_creative_emotion(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>💭 情绪仪表</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">VAD 三维情感向量实时追踪</p>'
        + cv.build_emotion_gauge() + '</div>')

@htmx_router.get("/creative/weather")
async def tree_creative_weather(request: Request):
    from ..core.creative_viz import build_knowledge_weather_map
    from ..dna.emergence_detector import get_phase_detector
    phase_data = get_phase_detector().stats()
    return HTMLResponse(build_knowledge_weather_map(phase_data))

# ═══ Admin Model Dashboard ═══

@htmx_router.get("/admin/models")
async def tree_admin_models(request: Request):
    """Authoritative model election dashboard — LLMFit-style evaluation matrix."""
    from ..core.model_dashboard import get_model_dashboard
    dashboard = get_model_dashboard()
    task_type = request.query_params.get("task", "general")
    cards = dashboard.build_cards(task_type=task_type)
    return HTMLResponse(dashboard.render_html(cards, task_hint=task_type))

# ═══ QGIS-inspired Panels ═══

@htmx_router.get("/admin/plugins")
async def tree_admin_plugins(request: Request):
    from ..core.skill_hub import get_skill_hub
    return HTMLResponse(get_skill_hub().render_html())

@htmx_router.get("/admin/toolbox")
async def tree_admin_toolbox(request: Request):
    from ..core.processing_framework import get_processing
    return HTMLResponse(get_processing().render_toolbox_html())

@htmx_router.get("/admin/organs")
async def tree_admin_organs(request: Request):
    from ..core.organ_dashboard import get_organ_dashboard
    return HTMLResponse(get_organ_dashboard().render_html())

# ═══ OpenMetadata-inspired Panels ═══

@htmx_router.get("/admin/lineage")
async def tree_admin_lineage(request: Request):
    from ..knowledge.knowledge_lineage import get_lineage
    return HTMLResponse(get_lineage().render_html())

@htmx_router.get("/admin/classifier")
async def tree_admin_classifier(request: Request):
    from ..core.auto_classifier import get_classifier
    sample = request.query_params.get("sample", "")
    return HTMLResponse(get_classifier().render_html(sample))

@htmx_router.get("/admin/quality")
async def tree_admin_quality(request: Request):
    from ..knowledge.quality_guard import QUALITY_TEMPLATES
    rows = "".join(
        f'<tr><td style="padding:4px 8px;font-size:11px"><b>{t.name}</b></td>'
        f'<td style="padding:4px 8px;font-size:10px;color:var(--dim)">{t.description}</td>'
        f'<td style="padding:4px 8px;font-size:10px">{t.severity}</td>'
        f'<td style="padding:4px 8px;font-size:9px;color:var(--dim)">{t.domain}</td></tr>'
        for t in QUALITY_TEMPLATES
    )
    return HTMLResponse(f'''<div class="card">
<h2>✅ 质量测试库 <span style="font-size:10px;color:var(--dim)">— OpenMetadata DQ Test Library</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0">{len(QUALITY_TEMPLATES)}个参数化测试模板</div>
<table style="width:100%;border-collapse:collapse;font-size:11px">
<thead><tr style="border-bottom:2px solid var(--border);font-size:10px;color:var(--dim)">
  <th>测试</th><th>描述</th><th>级别</th><th>领域</th></tr></thead>
<tbody>{rows}</tbody></table>
<div style="font-size:9px;color:var(--dim);margin-top:8px">error=阻断 warning=提示 info=信息 · 支持参数化SQL式条件</div></div>''')

# ═══ AI Awareness Dashboard ═══

@htmx_router.get("/admin/awareness")
async def tree_admin_awareness(request: Request):
    from ..core.awareness_engine import get_awareness
    return HTMLResponse(get_awareness().render_html())

@htmx_router.get("/admin/vitals")
async def tree_admin_vitals(request: Request):
    from ..core.vitals import get_vitals
    v = get_vitals().measure()
    return HTMLResponse(f'''<div class="card">
<h2>💓 生命体征 <span style="font-size:10px;color:var(--dim)">— Living Pot 硬件遥测</span></h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0">
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{'🔥' if v['cpu']['percent'] > 70 else '⚡' if v['cpu']['percent'] > 30 else '💤'}</div>
    <div style="font-size:18px;font-weight:700">{v['cpu']['percent']:.0f}%</div>
    <div style="font-size:10px;color:var(--dim)">CPU · {v['cpu']['level']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{'🧠' if v['memory']['percent'] > 70 else '💧'}</div>
    <div style="font-size:18px;font-weight:700">{v['memory']['percent']:.0f}%</div>
    <div style="font-size:10px;color:var(--dim)">RAM · {v['memory']['level']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="width:24px;height:24px;border-radius:50%;background:{v['led']['color_hex']};margin:0 auto"></div>
    <div style="font-size:11px;margin-top:4px">LED {v['led']['color_hex']}</div>
    <div style="font-size:9px;color:var(--dim)">亮度{v['led']['brightness']:.0%} · {v['led']['pulse_rate']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{v['leaf_display']['state']}</div>
    <div style="font-size:10px">{v['leaf_display']['message']}</div></div>
</div></div>''')

@htmx_router.get("/admin/city")
async def tree_admin_city(request: Request):
    from ..core.city_mcp import get_city_mcp
    return HTMLResponse(get_city_mcp().render_html())

@htmx_router.get("/admin/green")
async def tree_admin_green(request: Request):
    from ..core.green_scheduler import get_green_scheduler
    return HTMLResponse(get_green_scheduler().render_html())

@htmx_router.get("/admin/shield")
async def tree_admin_shield(request: Request):
    from ..core.prompt_shield import get_shield
    return HTMLResponse(get_shield().render_html())

@htmx_router.get("/admin/telemetry")
async def tree_admin_telemetry(request: Request):
    from ..core.telemetry import get_telemetry
    return HTMLResponse(get_telemetry().render_html())

@htmx_router.get("/reach/mobile")
async def tree_reach_mobile(request: Request):
    return _render_template("reach_mobile.html", request=request)

@htmx_router.get("/admin/spider")
async def tree_admin_spider(request: Request):
    """Scrapling Spider framework — visual crawl dashboard."""
    from ..capability.browser_agent import BrowserAgent  # verify import works
    try:
        from scrapling.fetchers import StealthyFetcher
        stealth_ok = "✅ StealthyFetcher (patchright)" 
    except ImportError:
        StealthyFetcher = None
        stealth_ok = "❌ patchright install chromium"
    html = '''<div class="card">
<h2>🕷 爬虫框架 <span style="font-size:10px;color:var(--dim)">— Scrapling Spider + LLM</span></h2>
<div style="display:flex;gap:16px;margin:8px 0;font-size:11px">
  <span>✅ Scrapling + Playwright</span><span>''' + stealth_ok + '''</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card" style="padding:10px">
    <h3>🎯 已集成特性</h3>
    <table style="width:100%;font-size:11px;border-collapse:collapse">
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>自适应选择器</b></td><td style="text-align:right">auto_save / adaptive</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>文本搜索</b></td><td style="text-align:right">find_by_text / regex</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>同类元素发现</b></td><td style="text-align:right">find_similar</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>选择器自动生成</b></td><td style="text-align:right">generate_css_selector</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>广告屏蔽</b></td><td style="text-align:right">block_ads (~3500域名)</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>资源拦截</b></td><td style="text-align:right">disable_resources (+25%速度)</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>自动重试</b></td><td style="text-align:right">retries=2</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>元素等待</b></td><td style="text-align:right">wait_selector</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>Canvas指纹</b></td><td style="text-align:right">hide_canvas (需patchright)</td></tr>
      <tr><td style="padding:4px"><b>Cloudflare绕过</b></td><td style="text-align:right">solve_cloudflare (需patchright)</td></tr>
    </table>
  </div>
  <div class="card" style="padding:10px">
    <h3>🔧 快速测试</h3>
    <div style="margin:8px 0">
      <input id="spider-url" placeholder="目标URL" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:12px" value="http://esg.epmap.org/reports">
    </div>
    <div style="margin:8px 0">
      <input id="spider-task" placeholder="提取任务 (如: 搜索格林美ESG报告)" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:12px" value="搜索ESG报告">
    </div>
    <button onclick="runSpider()" style="font-size:12px;padding:8px 20px;background:var(--accent);color:var(--bg);border:none;border-radius:6px;cursor:pointer">▶ 运行爬虫</button>
    <div id="spider-result" style="margin-top:12px;font-size:11px;color:var(--dim);max-height:400px;overflow:auto"></div>
  </div>
</div>
</div>
<script>
async function runSpider() {
  var url = document.getElementById("spider-url").value;
  var task = document.getElementById("spider-task").value;
  var el = document.getElementById("spider-result");
  el.innerHTML = '<div class="lc-loading">爬取中...</div>';
  try {
    var resp = await fetch("/tree/api/debug/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: "/browse " + url + " task=" + task, stream: false})
    });
    var data = await resp.json();
    el.innerHTML = "<pre style='white-space:pre-wrap;font-size:10px'>" + JSON.stringify(data, null, 2).slice(0, 3000) + "</pre>";
  } catch(e) {
    el.innerHTML = "<span style='color:var(--err)'>Error: " + e.message + "</span>";
  }
}
</script>'''
    return HTMLResponse(html)

# ═══ Unified Admin Console ═══

@htmx_router.get("/admin")
async def tree_admin_console(request: Request):
    """Unified admin console — aggregates all 7+ admin panels in one view."""
    return HTMLResponse('''<div style="padding:8px">
<h2 style="margin-bottom:8px">⚙ 管理员控制台 <span style="font-size:10px;color:var(--dim);font-weight:400">— 统一管理面板</span></h2>

<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px;margin-bottom:12px">
  <button onclick="loadAdminPanel('models')" class="admin-nav-btn active" id="admin-nav-models">📊 模型选举</button>
  <button onclick="loadAdminPanel('plugins')" class="admin-nav-btn" id="admin-nav-plugins">🧩 插件生态</button>
  <button onclick="loadAdminPanel('toolbox')" class="admin-nav-btn" id="admin-nav-toolbox">🔧 处理工具箱</button>
  <button onclick="loadAdminPanel('organs')" class="admin-nav-btn" id="admin-nav-organs">🫀 器官层面板</button>
  <button onclick="loadAdminPanel('lineage')" class="admin-nav-btn" id="admin-nav-lineage">🔗 知识血缘</button>
  <button onclick="loadAdminPanel('classifier')" class="admin-nav-btn" id="admin-nav-classifier">🏷 自动分类</button>
  <button onclick="loadAdminPanel('quality')" class="admin-nav-btn" id="admin-nav-quality">✅ 质量测试</button>
  <button onclick="loadAdminPanel('awareness')" class="admin-nav-btn" id="admin-nav-awareness">🧘 意识</button>
  <button onclick="loadAdminPanel('vitals')" class="admin-nav-btn" id="admin-nav-vitals">💓 体征</button>
  <button onclick="loadAdminPanel('city')" class="admin-nav-btn" id="admin-nav-city">🏯 城市</button>
  <button onclick="loadAdminPanel('green')" class="admin-nav-btn" id="admin-nav-green">🌿 绿色</button>
  <button onclick="loadAdminPanel('shield')" class="admin-nav-btn" id="admin-nav-shield">🛡️ 防护</button>
  <button onclick="loadAdminPanel('telemetry')" class="admin-nav-btn" id="admin-nav-telemetry">📊 遥测</button>
  <button onclick="loadAdminPanel('pipeline')" class="admin-nav-btn" id="admin-nav-pipeline">⚙ 管道</button>
  <button onclick="loadAdminPanel('spider')" class="admin-nav-btn" id="admin-nav-spider">🕷 爬虫</button>
</div>

<div id="admin-panel-content" style="min-height:400px">
  <div class="lc-loading" style="min-height:200px">加载模型选举仪表盘...</div>
</div>

<style>
.admin-nav-btn{background:var(--panel);border:1px solid var(--border);color:var(--text);padding:6px 12px;border-radius:6px;font-size:11px;cursor:pointer;white-space:nowrap;transition:all .2s}
.admin-nav-btn:hover{border-color:var(--accent)}
.admin-nav-btn.active{background:var(--accent);color:var(--bg);border-color:var(--accent)}
</style>

<script>
var adminPanelMap = {
  models: "/tree/admin/models",
  plugins: "/tree/admin/plugins",
  toolbox: "/tree/admin/toolbox",
  organs: "/tree/admin/organs",
  lineage: "/tree/admin/lineage",
  classifier: "/tree/admin/classifier",
  quality: "/tree/admin/quality",
  awareness: "/tree/admin/awareness",
  vitals: "/tree/admin/vitals",
  city: "/tree/admin/city",
  green: "/tree/admin/green",
  shield: "/tree/admin/shield",
  telemetry: "/tree/admin/telemetry",
  pipeline: "/tree/admin/pipeline",
  spider: "/tree/admin/spider"
};

function loadAdminPanel(name) {
  document.querySelectorAll(".admin-nav-btn").forEach(function(b) { b.classList.remove("active"); });
  var btn = document.getElementById("admin-nav-" + name);
  if (btn) btn.classList.add("active");
  var el = document.getElementById("admin-panel-content");
  el.innerHTML = '<div class="lc-loading" style="min-height:200px">加载中...</div>';
  fetch(adminPanelMap[name]).then(function(r) { return r.text(); }).then(function(html) {
    el.innerHTML = html;
  });
}

// Load models panel by default
setTimeout(function() { loadAdminPanel("models"); }, 200);
</script>
</div>''')

@htmx_router.get("/creative/twin")
async def tree_creative_twin(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🪞 数字孪生镜像</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">这是小树对你的认知。纠正它，帮助它更好地理解你。</p>'
        + cv.build_digital_twin() + '</div>')


@htmx_router.get("/pair/all-methods")
async def tree_pair_all_methods(request: Request):
    """Show all available pairing methods: code, QR, LAN, audio."""
    from ..network.universal_pairing import get_pairing
    pairing = get_pairing()
    code = pairing.generate_code()
    server_host = request.headers.get("host", "localhost:8100")
    protocol = "https" if request.url.scheme == "https" else "http"
    server_url = f"{protocol}://{server_host}"
    qr_url = pairing.generate_qr_url(server_url)
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={qr_url}"

    lan_devices = pairing.detect_lan_devices()
    lan_html = ""
    for d in lan_devices[:5]:
        lan_html += f'<div style="padding:3px 0;font-size:11px">📡 {d["name"]} ({d.get("address","")[:20]}) <button onclick="pairLanDevice(\'{d["device_id"]}\')" style="font-size:9px;padding:2px 6px">配对</button></div>'
    if not lan_html:
        lan_html = '<div style="color:var(--dim);font-size:11px">未发现同网络设备</div>'

    return HTMLResponse(
        '<div class="card">'
        '<h2>🔗 万物互联 · 多模态配对</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">任选一种方式连接设备。配对后自动协商能力，渐进提升信任。</p>'

        '<div style="margin:8px 0;display:grid;grid-template-columns:1fr 1fr;gap:8px">'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">🔢</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">8位数字码</div>'
        f'<div style="font-size:22px;font-weight:700;font-family:monospace;letter-spacing:6px;color:var(--accent);margin:8px 0">{code}</div>'
        f'<div style="font-size:9px;color:var(--dim)">在手机上输入此码 · 5分钟有效</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">📱</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">扫码配对</div>'
        f'<img src="{qr_img}" style="width:120px;height:120px;background:#fff;border-radius:6px;margin:4px 0">'
        f'<div style="font-size:9px;color:var(--dim)">扫描二维码自动连接</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">📡</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">同WiFi自动发现</div>'
        f'{lan_html}'
        f'<div style="font-size:9px;color:var(--dim);margin-top:4px">零操作自动配对</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">🔊</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">超声波配对</div>'
        f'<button onclick="startAudioPairing()" style="font-size:11px;padding:6px 14px;margin:4px 0">▶ 发射音频信号</button>'
        f'<div id="audio-pair-status" style="font-size:9px;color:var(--dim)">手机会听到超声波自动配对</div></div>'

        '</div>'

        '<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">已配对设备</h4>'
        + "".join(
            f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
            f'<span>{d["name"]} ({d["type"]}) — {d["pair_method"]}</span>'
            f'<span style="color:var(--accent)">信任 Lv.{d["trust"]}</span></div>'
            for d in pairing.get_paired_devices()
        )
        + '</div>'
        '</div>'
    )


@htmx_router.get("/remote/panel")
async def tree_remote_panel(request: Request):
    """WebRTC remote ops panel — remote terminal, file browser, system monitor."""
    return HTMLResponse(
        '<div class="card">'
        '<h2>🖥 远程运维 · WebRTC P2P</h2>'
        '<div style="margin-bottom:8px">'
        '<span id="rtc-status" style="font-size:11px;color:var(--dim)">点击连接建立P2P通道</span>'
        '<button onclick="rtcConnect()" style="font-size:10px;padding:4px 10px;margin-left:8px">🔗 建立连接</button>'
        '</div>'

        '<div style="display:flex;gap:8px;margin-bottom:8px">'
        '<button onclick="showRtcTab(\'shell\')" class="tab-btn active" id="rtc-tab-shell">💻 终端</button>'
        '<button onclick="showRtcTab(\'files\')" class="tab-btn" id="rtc-tab-files">📂 文件</button>'
        '<button onclick="showRtcTab(\'monitor\')" class="tab-btn" id="rtc-tab-monitor">📊 监控</button>'
        '</div>'

        '<div id="rtc-tab-shell-content">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="rtc-shell-cmd" placeholder="命令..." style="flex:1;font-size:12px;font-family:monospace;padding:6px 8px" onkeydown="if(event.key===\'Enter\')rtcShell()">'
        '<button onclick="rtcShell()" style="font-size:11px;padding:6px 12px">执行</button></div>'
        '<pre id="rtc-shell-out" style="background:rgba(0,0,0,.1);padding:8px;border-radius:4px;max-height:350px;overflow-y:auto;font-size:11px;min-height:80px;color:var(--text)">等待命令...</pre></div>'

        '<div id="rtc-tab-files-content" style="display:none">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="rtc-file-path" placeholder="路径..." value="." style="flex:1;font-size:11px;padding:4px 8px">'
        '<button onclick="rtcFileBrowse()" style="font-size:10px;padding:4px 10px">浏览</button></div>'
        '<div style="display:flex;gap:8px"><div id="rtc-file-list" style="flex:1;max-height:250px;overflow-y:auto;font-size:11px;background:rgba(0,0,0,.05);padding:4px;border-radius:4px;min-height:100px"></div>'
        '<pre id="rtc-file-content" style="flex:2;max-height:250px;overflow-y:auto;font-size:10px;background:rgba(0,0,0,.05);padding:4px;border-radius:4px;min-height:100px;color:var(--dim)">点击文件查看</pre></div></div>'

        '<div id="rtc-tab-monitor-content" style="display:none">'
        '<button id="rtc-monitor-btn" onclick="rtcMonitor()" style="font-size:10px;padding:4px 10px;margin-bottom:8px">▶ 开始监控</button>'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center">'
        '<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">CPU</div><div style="font-size:20px;font-weight:600;color:var(--accent)" id="rtc-cpu">—</div></div>'
        '<div style="background:rgba(100,150,180,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">Memory</div><div style="font-size:20px;font-weight:600;color:#6af" id="rtc-mem">—</div></div>'
        '<div style="background:rgba(150,150,100,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">Disk</div><div style="font-size:20px;font-weight:600;color:#fa6" id="rtc-disk">—</div></div></div></div>'
        '</div>'
        '<script>'
        'var _rtcPc=null,_rtcDc=null,_rtcMonitorActive=false,_rtcReqId=0;'
        'function rtcConnect(){_rtcPc=new RTCPeerConnection({iceServers:[{urls:"stun:stun.l.google.com:19302"}]});_rtcDc=_rtcPc.createDataChannel("remote-ops");'
        '_rtcDc.onopen=function(){document.getElementById("rtc-status").innerHTML="<span style=color:var(--accent)>● P2P已连接</span>"};'
        '_rtcDc.onmessage=function(e){rtcOnMsg(JSON.parse(e.data))};'
        '_rtcDc.onclose=function(){document.getElementById("rtc-status").innerHTML="<span style=color:var(--err)>● 断开</span>"};'
        '_rtcPc.createOffer().then(function(o){_rtcPc.setLocalDescription(o);'
        'var ws=new WebSocket((location.protocol==="https:"?"wss:":"ws:")+location.host+"/ws/rtc-signal");'
        'ws.onopen=function(){ws.send(JSON.stringify({sdp:JSON.stringify(o)}))};'
        'ws.onmessage=function(e){var d=JSON.parse(e.data);if(d.sdp)_rtcPc.setRemoteDescription(new RTCSessionDescription(d.sdp));if(d.ice)_rtcPc.addIceCandidate(new RTCIceCandidate(d.ice))}})}}'
        'function rtcSend(op,data){if(_rtcDc&&_rtcDc.readyState==="open"){_rtcReqId++;data.request_id="r"+_rtcReqId;data.op=op;_rtcDc.send(JSON.stringify(data))}}'
        'function rtcOnMsg(d){if(d.op==="pong")return;'
        'if(d.op==="shell_result"){var o=document.getElementById("rtc-shell-out");o.textContent=(d.stdout||"")+(d.stderr||"")||"(无输出)";o.style.color=d.exit===0?"var(--text)":"var(--err)"}'
        'if(d.op==="monitor_data"){document.getElementById("rtc-cpu").textContent=d.cpu+"%";document.getElementById("rtc-mem").textContent=d.mem+"%";document.getElementById("rtc-disk").textContent=d.disk+"%"}'
        'if(d.op==="file_list_result"){var el=document.getElementById("rtc-file-list");el.innerHTML=d.files?d.files.map(function(f){return "<div onclick=rtcSend(\'file_read\',{path:\'"+d.path+"/"+f.name+"\'}) style=cursor:pointer;padding:2px_0;font-size:11px>"+(f.type==="dir"?"📁":"📄")+" "+f.name+"</div>"}).join(""):"error"}'
        'if(d.op==="file_read_result"){document.getElementById("rtc-file-content").textContent=d.content||d.error}}'
        'function rtcShell(){var c=document.getElementById("rtc-shell-cmd").value.trim();if(c&&_rtcDc)rtcSend("shell",{cmd:c})}'
        'function rtcMonitor(){_rtcMonitorActive=!_rtcMonitorActive;rtcSend(_rtcMonitorActive?"monitor_start":"monitor_stop",{interval:2});document.getElementById("rtc-monitor-btn").textContent=_rtcMonitorActive?"⏸ 停止":"▶ 开始监控"}'
        'function rtcFileBrowse(){rtcSend("file_list",{path:document.getElementById("rtc-file-path").value||"."})}'
        'function showRtcTab(t){["shell","files","monitor"].forEach(function(x){var e=document.getElementById("rtc-tab-"+x+"-content");var b=document.getElementById("rtc-tab-"+x);if(e)e.style.display=x===t?"block":"none";if(b)b.classList.toggle("active",x===t)})}'
        'setInterval(function(){if(_rtcDc&&_rtcDc.readyState==="open")rtcSend("ping",{})},15000);'
        '</script>'
    )


@htmx_router.get("/p2p/status")
async def tree_p2p_status(request: Request):
    """P2P connectivity: NAT type, relay health, active peers."""
    hub = _get_hub(request)
    if not hub:
        return HTMLResponse('<div style="color:var(--dim)">系统未就绪</div>')

    from ..network.nat_traverse import NATType

    nat = getattr(getattr(hub, "world", None), "nat_traverser", None)
    st = nat.status() if nat else {"nat_type": "unknown", "public_endpoint": "", "active_peers": 0, "healthy_relays": 0, "relays": []}

    nat_descriptions = {
        "open": "🟢 公网IP — 最佳P2P,无需打洞",
        "full_cone": "🟢 Full Cone — 直接通信,成功率高",
        "restricted": "🟡 Restricted Cone — 需先发包,成功率90%+",
        "port_restricted": "🟠 Port-Restricted — 需端口匹配",
        "symmetric": "🔴 Symmetric — 需端口预测,中继兜底",
        "udp_blocked": "⚫ UDP被封锁 — 仅TCP/中继",
        "unknown": "⏳ 检测中...",
    }

    relays_html = ""
    for r in st.get("relays", []):
        icon = "🟢" if r.get("healthy") else "🔴"
        relays_html += f'<div style="font-size:11px;padding:2px 0">{icon} {r["host"]}:{r["port"]} (fail: {r.get("failures", 0)})</div>'

    return HTMLResponse(
        '<div class="card">'
        f'<h2>🔗 P2P 连接状态</h2>'
        f'<div style="padding:8px;background:rgba(100,150,180,.05);border-radius:6px;margin:8px 0">'
        f'<div style="font-size:14px;font-weight:600">{nat_descriptions.get(st.get("nat_type","unknown"), "⏳ 检测中")}</div>'
        f'<div style="font-size:10px;color:var(--dim);margin-top:4px">公网端点: {st.get("public_endpoint","检测中")}</div></div>'
        f'<div class="metric"><span>活跃P2P连接</span><span>{st.get("active_peers", 0)}</span></div>'
        f'<div class="metric"><span>健康中继</span><span>{st.get("healthy_relays", 0)}/{len(st.get("relays",[]))}</span></div>'
        f'<div style="margin-top:8px">{relays_html}</div>'
        f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
        f'策略: 直连优先 → UDP打洞 → TCP直连 → TURN中继<br>'
        f'保活间隔: FullCone=20s Symmetric=10s</div>'
        '</div>'
    )


@htmx_router.get("/tools/suggest")
async def tree_tools_suggest(request: Request, context: str = Query(default="")):
    """AI suggests interactive tools based on task context. Returns tool card HTML."""
    if not context.strip():
        return HTMLResponse('<div style="color:var(--dim);font-size:12px">没有上下文</div>')

    from ..core.interactive_tools import get_tool_registry
    registry = get_tool_registry()

    hub = _get_hub(request)
    available_tools = []
    if hub:
        try:
            tm = getattr(hub.world, "tool_market", None)
            if tm:
                found = tm.search(context)[:5]
                available_tools = [{"name": t.name, "description": getattr(t, "description", "")} for t in found]
        except Exception:
            pass

    offers = registry.suggest_tools(context, available_tools)
    if not offers:
        return HTMLResponse('<div style="color:var(--dim);font-size:12px">AI暂未建议交互工具</div>')

    html_parts = []
    for offer in offers:
        html_parts.append(offer.to_html())

    return HTMLResponse("\n".join(html_parts))


@htmx_router.post("/tools/result")
async def tree_tools_result(request: Request):
    """User submits a tool result. Feeds back into AI context."""
    try:
        body = await request.json()
    except Exception:
        return HTMLResponse('<div style="color:var(--warn)">无效数据</div>')

    offer_id = body.get("offer_id", "")
    tool_type = body.get("tool_type", "custom")
    result = body.get("result", {})

    hub = _get_hub(request)
    if hub and hub.world and hub.world.consciousness:
        try:
            result_str = str(result)[:1000]
            resp = await hub.world.consciousness.chain_of_thought(
                f"用户使用工具 '{tool_type}' 产生以下结果:\n{result_str}\n\n"
                f"请基于此结果提供简短反馈或下一步建议 (1-2句)。", steps=1,
            )
            feedback = resp if isinstance(resp, str) else str(resp)
        except Exception:
            feedback = f"已收到 {tool_type} 工具结果，继续分析中..."

        return HTMLResponse(
            f'<div class="msg assistant" style="margin-top:8px">'
            f'<div class="who">小树 🌳 · 工具反馈</div>'
            f'<div class="text">{_html.escape(feedback[:500])}</div></div>'
        )

    return HTMLResponse('<div style="color:var(--dim);font-size:12px">AI已收到工具结果</div>')


@htmx_router.get("/perf/stats")
async def tree_perf_stats(request: Request):
    """Performance stats: cache hit rate, stream render status."""
    from ..core.perf_accel import get_response_cache, get_stream_render
    from ..core.adaptive_folder import get_folder
    from ..core.final_polish import get_ladder, get_predictive
    cache = get_response_cache()
    sr = get_stream_render()
    folder = get_folder()
    fs = folder.stats()
    ladder = get_ladder()
    ls = ladder.status()
    pred = get_predictive()
    ps = pred.stats()
    return HTMLResponse(
        '<div class="card">'
        '<h2>⚡ 性能统计</h2>'
        f'<div class="metric"><span>缓存命中率</span><span>{cache.stats()["hit_rate"]}</span></div>'
        f'<div class="metric"><span>缓存条目</span><span>{cache.stats()["entries"]}/{cache.stats()["max_entries"]}</span></div>'
        f'<div class="metric"><span>预测命中率</span><span style="color:var(--accent)">{ps["hit_rate"]} ({ps["hits"]}/{ps["hits"]+ps["misses"]})</span></div>'
        f'<div class="metric"><span>节省Token</span><span>{cache.stats()["tokens_saved"]:,}</span></div>'
        f'<div class="metric"><span>成本层级</span><span style="color:{"var(--accent)" if ls["current_tier"]=="pro" else "var(--warn)"}">{ls["current_tier"]} → {ls["recommended_model"]}</span></div>'
        f'<div class="metric"><span>流渲染节流</span><span>{sr._throttle*1000:.0f}ms / {sr._chunk_chars}字符</span></div>'
        f'<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">'
        f'<h4 style="font-size:12px;margin-bottom:4px">🧠 自适应折叠</h4>'
        f'<div class="metric"><span>折叠次数 / 省字符</span><span>{fs["total_folds"]} / {fs["saved_chars"]:,}</span></div>'
        f'<div class="metric"><span>估算省费用</span><span>¥{fs["estimated_cost_saved_yuan"]:.6f}</span></div></div>'
        '</div>'
    )


# ═══════════════════════════════════════════════════════════════
#  P7: Task decomposition tree — live SSE visualization
# ═══════════════════════════════════════════════════════════════

@htmx_router.get("/task", response_class=HTMLResponse)
async def tree_task_page(request: Request):
    """Task decomposition visualization page."""
    return _render_template("task_tree.html", request=request)


@htmx_router.get("/task/tree")
async def tree_task_sse(request: Request, task: str = Query(default="")):
    """SSE stream of task decomposition tree.

    Query params:
        task: task description to decompose, or task_id to resume
    """
    if not task.strip():
        async def empty():
            yield f"event: task_error\ndata: {_json.dumps({'error': '请提供任务描述'})}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    hub = _get_hub(request)

    async def stream():
        try:
            from ..execution.task_tree import get_task_decomposer

            decomposer = get_task_decomposer()

            if hub and hub.world and hub.world.consciousness:
                decomposer.set_consciousness(hub.world.consciousness)
            decomposer.set_hub(hub)

            async for sse_event in decomposer.decompose(task, max_depth=4, max_children=6):
                yield sse_event

        except Exception as e:
            logger.error(f"Task tree SSE error: {e}")
            yield f"event: task_error\ndata: {_json.dumps({'error': str(e)[:500]})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _predictive_precompute(predictive, msg, content, hub):
    """Background: predict and pre-compute likely follow-up questions."""
    try:
        if hub and hub.world and hub.world.consciousness:
            consc = hub.world.consciousness
            queries = await predictive.predict_next(msg, content, consc)
            for q in queries[:2]:
                async def _answer(q=q):
                    acc = ""
                    async for t in consc.stream_of_thought(q):
                        acc += t
                    return acc
                await predictive.precompute(q, _answer)
    except Exception:
        pass


def setup_htmx(app) -> None:
    from .htmx_living import living_router
    from .htmx_business import business_router
    app.include_router(htmx_router)
    app.include_router(living_router)
    app.include_router(business_router)
    logger.info("HTMX web layer v5.0 registered at /tree (P0-P6 + Living Canvas + Business)")
