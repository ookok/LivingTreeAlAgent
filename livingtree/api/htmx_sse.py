"""HTMX SSE routes — streaming endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from loguru import logger

sse_router = APIRouter(prefix="/sse", tags=["sse"])

@sse_router.get("/sse/chat")
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



@sse_router.get("/sse")
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


@sse_router.get("/sse/thoughts")
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
#  Reach routes — extracted to htmx_reach.py (included via include_router above)
# ═══════════════════════════════════════════════════════════════


# reach routes extracted to htmx_reach.py


# reach routes extracted to htmx_reach.py


# ── Cognition Stream: Visualize AI's thinking process ──

@sse_router.get("/sse/cognition")
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


@sse_router.get("/resilience/panel")
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


@sse_router.get("/theme/{theme_name}")
async def tree_theme_css(theme_name: str):
    """Dynamic theme CSS generated from Kami design tokens."""
    from ..core.kami_theme import generate_css, ThemeName
    valid = {"dark", "light", "kami"}
    name = theme_name if theme_name in valid else "dark"
    css = generate_css(name)
    from fastapi.responses import Response
    return Response(content=css, media_type="text/css")


@sse_router.get("/growth/panel")
@sse_router.get("/shell/env")
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


# Shell routes extracted to htmx_shell.py

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


@sse_router.get("/im/panel")
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


@sse_router.get("/persona")
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


@sse_router.get("/presence/living-layer")
async def tree_presence_layer(request: Request, input_text: str = Query(default="")):
    """Inject living presence: breathing, weather, particles, echoes."""
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(p.build_all(input_text))


@sse_router.get("/persona")
async def tree_persona(request: Request):
    """Unique anime persona — different for every user."""
    from ..core.anime_persona import get_persona
    p = get_persona()
    p._hub = _get_hub(request)
    p.record_visit()
    return HTMLResponse(p.build_full())


@sse_router.get("/chrome/panel")
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


@sse_router.get("/dpo/panel")
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


@sse_router.get("/control/panel")
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


@sse_router.get("/collective/panel")
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


@sse_router.get("/qa/panel")
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


@sse_router.get("/persona/forest")
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


@sse_router.get("/dpo/panel")
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


@sse_router.get("/control/panel")
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


@sse_router.get("/collective/panel")
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


@sse_router.get("/qa/panel")
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


@sse_router.get("/persona/forest")
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


@sse_router.get("/task", response_class=HTMLResponse)
async def tree_task_page(request: Request):
    """Task decomposition visualization page."""
    return _render_template("task_tree.html", request=request)


@sse_router.get("/task/tree")
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
__all__ = ["form_router"]
__all__ = ["sse_router"]
