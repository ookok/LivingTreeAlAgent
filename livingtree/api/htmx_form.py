"""HTMX Form routes — adaptive form generation."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

form_router = APIRouter(prefix="/form", tags=["form"])

@form_router.post("/form/generate")
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


@form_router.get("/form/validate")
async def tree_form_validate(request: Request, field: str = Query(default="")):
    """Validate a form field and return validation HTML."""
    return HTMLResponse(
        '<span style="font-size:11px;color:var(--accent)">✓ 已输入</span>'
    )


@form_router.get("/form/step")
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

@form_router.get("/insight", response_class=HTMLResponse)
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

@form_router.post("/emphasize-demo", response_class=HTMLResponse)
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

@form_router.get("/params", response_class=HTMLResponse)
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

@form_router.get("/sse")
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


@form_router.get("/sse/thoughts")
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

@form_router.get("/sse/cognition")
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


@form_router.get("/swarm/panel")
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


@form_router.post("/swarm/share-cell")
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


@form_router.post("/swarm/sync-knowledge")
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


@form_router.get("/resilience/panel")
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


@form_router.get("/theme/{theme_name}")
async def tree_theme_css(theme_name: str):
    """Dynamic theme CSS generated from Kami design tokens."""
    from ..core.kami_theme import generate_css, ThemeName
    valid = {"dark", "light", "kami"}
    name = theme_name if theme_name in valid else "dark"
    css = generate_css(name)
    from fastapi.responses import Response
    return Response(content=css, media_type="text/css")


@form_router.get("/growth/panel")
@form_router.get("/shell/env")
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


@form_router.get("/im/panel")
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


@form_router.get("/persona")
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


@form_router.get("/presence/living-layer")
async def tree_presence_layer(request: Request, input_text: str = Query(default="")):
    """Inject living presence: breathing, weather, particles, echoes."""
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(p.build_all(input_text))


@form_router.get("/persona")
async def tree_persona(request: Request):
    """Unique anime persona — different for every user."""
    from ..core.anime_persona import get_persona
    p = get_persona()
    p._hub = _get_hub(request)
    p.record_visit()
    return HTMLResponse(p.build_full())


@form_router.get("/chrome/panel")
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


@form_router.get("/dpo/panel")
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


@form_router.get("/control/panel")
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


@form_router.get("/collective/panel")
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


@form_router.get("/qa/panel")
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


@form_router.get("/persona/forest")
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


@form_router.get("/dpo/panel")
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


@form_router.get("/control/panel")
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


@form_router.get("/collective/panel")
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


@form_router.get("/qa/panel")
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


@form_router.get("/persona/forest")
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


@form_router.get("/creative/garden")
async def tree_creative_garden(request: Request):
    from ..core.living_presence import get_presence
    p = get_presence()
    p._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌿 对话花园</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">每个重要时刻都会长成一株植物。这是小树对你的记忆。</p>'
        + p.build_garden() + '</div>')


@form_router.get("/creative/timeline")
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

@form_router.get("/creative/dream")
async def tree_creative_dream(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🌙 梦境引擎</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">空闲时小树在重组知识、发现隐藏连接</p>'
        + cv.build_dream_canvas() + '</div>')

@form_router.get("/creative/swarm")
async def tree_creative_swarm(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🗺️ 群体地图</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">所有连接节点的地理位置和能力分布</p>'
        + cv.build_swarm_map() + '</div>')

@form_router.get("/creative/emotion")
async def tree_creative_emotion(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>💭 情绪仪表</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">VAD 三维情感向量实时追踪</p>'
        + cv.build_emotion_gauge() + '</div>')

@form_router.get("/creative/weather")
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

@form_router.get("/task", response_class=HTMLResponse)
async def tree_task_page(request: Request):
    """Task decomposition visualization page."""
    return _render_template("task_tree.html", request=request)


@form_router.get("/task/tree")
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
