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

# Reach routes extracted to htmx_reach.py (included as sub-router)
from .htmx_reach import reach_router
htmx_router.include_router(reach_router)


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


