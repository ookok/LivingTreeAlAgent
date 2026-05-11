"""Living page dynamic region routes."""
from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from loguru import logger

living_router = APIRouter(prefix="/tree", tags=["htmx-living"])

def _decode_layout_intent(message: str) -> str:
    """Decode user intent to determine layout mode without LLM."""
    msg = message.lower().replace(" ", "")
    if any(kw in msg for kw in ["检查", "状态", "健康", "健康吗", "怎么样", "status", "health"]):
        return "dashboard"
    if any(kw in msg for kw in ["什么是", "解释", "介绍一下", "知识", "了解", "explain", "whatis"]):
        return "explore"
    if any(kw in msg for kw in ["写", "生成", "创建", "做", "帮我", "任务", "build", "create", "write", "implement"]):
        return "workspace"
    if any(kw in msg for kw in ["分析", "对比", "比较", "分析一下", "analyze", "compare"]):
        return "triple"
    if len(message) < 30:
        return "focus"
    return "split"


def _regions_for_mode(mode: str, message: str = "") -> list[dict]:
    """Return region configuration for a layout mode."""
    if mode == "focus":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 2},
        ]
    elif mode == "split":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 2},
            {"id": "sidebar", "type": "insight", "col": 2, "row": 1, "w": 1, "h": 2},
        ]
    elif mode == "triple":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 2},
            {"id": "think", "type": "think", "col": 2, "row": 1, "w": 1, "h": 1},
            {"id": "knowledge", "type": "knowledge", "col": 2, "row": 2, "w": 1, "h": 1},
            {"id": "execute", "type": "execute", "col": 3, "row": 1, "w": 1, "h": 2},
        ]
    elif mode == "dashboard":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 1},
            {"id": "health", "type": "health", "col": 1, "row": 2, "w": 1, "h": 1},
            {"id": "metrics", "type": "metrics", "col": 2, "row": 1, "w": 2, "h": 1},
            {"id": "insight", "type": "insight", "col": 2, "row": 2, "w": 1, "h": 1},
            {"id": "memory", "type": "memory", "col": 3, "row": 2, "w": 1, "h": 1},
        ]
    elif mode == "explore":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 1},
            {"id": "knowledge", "type": "knowledge", "col": 1, "row": 2, "w": 1, "h": 1},
            {"id": "think", "type": "think", "col": 2, "row": 1, "w": 1, "h": 2},
        ]
    elif mode == "workspace":
        return [
            {"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 1},
            {"id": "plan", "type": "plan", "col": 1, "row": 2, "w": 1, "h": 1},
            {"id": "execute", "type": "execute", "col": 2, "row": 1, "w": 1, "h": 2},
            {"id": "think", "type": "think", "col": 3, "row": 1, "w": 1, "h": 1},
            {"id": "tools", "type": "tools", "col": 3, "row": 2, "w": 1, "h": 1},
        ]
    return [{"id": "chat", "type": "chat", "col": 1, "row": 1, "w": 1, "h": 2}]


@living_router.get("/living", response_class=HTMLResponse)
@living_router.get("/living/", response_class=HTMLResponse)
async def tree_living(request: Request):
    """Living Canvas — the unified dynamic surface."""
    return _render_template("living.html", request=request)


@living_router.get("/living/layout")
async def tree_living_layout(request: Request, message: str = Query(default="")):
    """Generate the initial layout based on message/context.

    Returns a complete CSS-grid layout with regions, each region is a
    slot that lazily loads its content via hx-get.
    """
    mode = _decode_layout_intent(message)
    regions = _regions_for_mode(mode, message)
    cols = _LAYOUT_MODES.get(mode, {}).get("cols", 2)
    mode_desc = _LAYOUT_MODES.get(mode, {}).get("desc", "")

    region_html_parts = []
    for r in regions:
        rt = _REGION_TYPES.get(r["type"], _REGION_TYPES["chat"])
        region_html_parts.append(
            f'<div class="lc-region lc-{r["type"]}" '
            f'id="lc-{r["id"]}" '
            f'style="grid-column:{r["col"]}/span {r["w"]};grid-row:{r["row"]}/span {r["h"]}" '
            f'hx-get="/tree/living/region/{r["type"]}?context={_html.escape(message[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML" '
            f'hx-indicator="#lc-loading-{r["id"]}">'
            f'<div class="lc-loading" id="lc-loading-{r["id"]}">'
            f'{rt["icon"]} {rt["label"]} 加载中...</div>'
            f'</div>'
        )

    layout_html = (
        f'<div class="lc-layout-info" style="display:none" '
        f'data-mode="{mode}" data-cols="{cols}">{mode_desc}</div>\n'
        + "\n".join(region_html_parts)
    )

    return HTMLResponse(layout_html)


@living_router.get("/living/region/{region_type}")
async def tree_living_region(request: Request, region_type: str, context: str = Query(default="")):
    """Render a single region's content. Each region type has its own
    content generation strategy — some are static templates, some are
    LLM-generated based on context."""
    hub = _get_hub(request)
    started = hub and getattr(hub, "_started", False)

    if region_type == "chat":
        return _render_chat_region(context)
    elif region_type == "think":
        return await _render_think_region(hub, started, context)
    elif region_type == "plan":
        return await _render_plan_region(hub, started, context)
    elif region_type == "execute":
        return _render_execute_region()
    elif region_type == "health":
        return await _render_health_region(hub, started)
    elif region_type == "knowledge":
        return await _render_knowledge_region(hub, started, context)
    elif region_type == "insight":
        return await _render_insight_region(hub, started, context)
    elif region_type == "metrics":
        return await _render_metrics_region(hub, started)
    elif region_type == "tools":
        return await _render_tools_region(hub, started, context)
    elif region_type == "memory":
        return await _render_memory_region(hub, started, context)

    return HTMLResponse(
        f'<div class="lc-region-inner"><div class="lc-region-header">'
        f'{_REGION_TYPES.get(region_type, {}).get("icon", "❓")} {region_type}</div>'
        f'<p style="color:var(--dim);font-size:12px">未知区域类型</p></div>'
    )


def _region_wrap(icon: str, title: str, body: str, region_id: str = "", extra_actions: str = "") -> str:
    """Wrap region content with consistent header + actions."""
    actions_html = (
        f'<div class="lc-region-actions">'
        f'{extra_actions}'
        f'<button class="lc-btn-icon" hx-get="/tree/living/region/{region_id}" '
        f'hx-target="closest .lc-region" hx-swap="outerHTML" title="刷新">🔄</button>'
        f'<button class="lc-btn-icon" hx-swap="delete" hx-target="closest .lc-region" title="关闭">✕</button>'
        f'</div>'
    )
    return (
        f'<div class="lc-region-inner">'
        f'<div class="lc-region-header"><span>{icon} {title}</span>{actions_html}</div>'
        f'<div class="lc-region-body">{body}</div>'
        f'</div>'
    )


# ── Region renderers ──

def _render_chat_region(context: str) -> HTMLResponse:
    body = (
        f'<div id="lc-chat-log" style="max-height:40vh;overflow-y:auto;margin-bottom:8px">'
        f'<div class="msg assistant"><div class="who">小树 🌳</div>'
        f'<div class="text">我是生命之树。有什么可以帮助你的？</div></div>'
        f'</div>'
        f'<form hx-post="/tree/chat/msg" hx-target="#lc-chat-log" hx-swap="beforeend" '
        f'hx-on::after-request="this.reset()">'
        f'<textarea name="message" rows="2" placeholder="告诉小树你想做什么..." '
        f'style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);'
        f'padding:8px;border-radius:4px;font-size:13px;resize:none" '
        f'onkeydown="if(event.key==="Enter"&&!event.shiftKey){{event.preventDefault();'
        f'htmx.trigger("#lc-chat-send","click")}}"></textarea>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-top:4px">'
        f'<button type="submit" id="lc-chat-send" style="font-size:12px;padding:6px 16px">发送</button>'
        f'<span style="font-size:10px;color:var(--dim)">Enter 发送 · Shift+Enter 换行</span>'
        f'</div></form>'
    )
    return HTMLResponse(_region_wrap("💬", "对话", body, "chat"))


async def _render_think_region(hub, started: bool, context: str) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">系统就绪中...</p>'
    elif context.strip():
        body = (
            f'<div id="lc-think-tree">'
            f'<div style="color:var(--dim);font-size:12px;margin-bottom:8px">'
            f'基于当前上下文生成推理树...</div>'
            f'</div>'
            f'<div hx-get="/tree/sse/cot?question={_html.escape(context[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML" hx-target="#lc-think-tree">'
            f'</div>'
        )
    else:
        body = '<p style="color:var(--dim);font-size:12px">输入问题后自动展开推理</p>'
    return HTMLResponse(_region_wrap("🧠", "思维链", body, "think"))


async def _render_plan_region(hub, started: bool, context: str) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">系统就绪中...</p>'
    elif context.strip():
        body = (
            f'<div id="lc-plan-steps" style="font-size:12px">'
            f'<div style="color:var(--dim)">正在为 "{_html.escape(context[:50])}" 规划...</div>'
            f'</div>'
            f'<div hx-get="/tree/living/region-content/plan?context={_html.escape(context[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML" hx-target="#lc-plan-steps">'
            f'</div>'
        )
    else:
        body = '<p style="color:var(--dim);font-size:12px">输入复杂任务后显示规划步骤</p>'
    return HTMLResponse(_region_wrap("📋", "任务规划", body, "plan"))


def _render_execute_region() -> HTMLResponse:
    body = (
        '<div id="lc-execute-output" style="font-size:12px;color:var(--dim)">'
        '执行结果将在此显示</div>'
    )
    return HTMLResponse(_region_wrap("⚡", "执行输出", body, "execute"))


async def _render_health_region(hub, started: bool) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">等待系统...</p>'
    else:
        body = (
            f'<div id="lc-health-content" '
            f'hx-get="/tree/health" hx-trigger="load, every 30s" hx-swap="innerHTML">'
            f'<div style="color:var(--dim)">加载健康数据...</div>'
            f'</div>'
        )
    return HTMLResponse(_region_wrap("🏥", "系统健康", body, "health"))


async def _render_knowledge_region(hub, started: bool, context: str) -> HTMLResponse:
    body = (
        f'<div style="margin-bottom:8px">'
        f'<input id="lc-kg-input" placeholder="搜索知识实体..." '
        f'style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);'
        f'padding:6px 8px;border-radius:4px;font-size:12px" '
        f'onkeydown="if(event.key==="Enter"){{'
        f'const v=this.value.trim();if(v){{'
        f'htmx.ajax("POST","/tree/kg/explore",'
        f'{{target:"#lc-kg-result",swap:"beforeend",values:{{entity:v}}}});'
        f'this.value=""}}}}"'
        f'>'
        f'</div>'
        f'<div id="lc-kg-result" style="max-height:35vh;overflow-y:auto;font-size:12px">'
        f'<div style="color:var(--dim)">搜索知识实体，输入后按 Enter</div>'
        f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">'
    )
    presets = ["神经网络", "强化学习", "Transformer", "注意力机制", "DeepSeek", "HTMX", "SSE"]
    for p in presets:
        body += (
            f'<span class="lc-kg-tag" onclick="'
            f'htmx.ajax(\'POST\',\'/tree/kg/explore\','
            f'{{target:\'#lc-kg-result\',swap:\'beforeend\',values:{{entity:\'{p}\'}}}})'
            f'">{p}</span>'
        )
    body += '</div></div>'
    return HTMLResponse(_region_wrap("🗺️", "知识图谱", body, "knowledge"))


async def _render_insight_region(hub, started: bool, context: str) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">等待系统...</p>'
    elif context.strip():
        body = (
            f'<div id="lc-insight-content">'
            f'<div style="color:var(--dim);font-size:11px">正在生成洞见...</div>'
            f'</div>'
            f'<div hx-get="/tree/living/region-content/insight?context={_html.escape(context[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML" hx-target="#lc-insight-content">'
            f'</div>'
        )
    else:
        body = '<p style="color:var(--dim);font-size:12px">输入问题后显示AI洞见</p>'
    return HTMLResponse(_region_wrap("💡", "实时洞见", body, "insight"))


async def _render_metrics_region(hub, started: bool) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">等待系统...</p>'
    else:
        body = (
            f'<div id="lc-metrics-content" '
            f'hx-get="/tree/living/region-content/metrics" '
            f'hx-trigger="load, every 15s" hx-swap="innerHTML">'
            f'<div style="color:var(--dim)">加载指标...</div>'
            f'</div>'
        )
    return HTMLResponse(_region_wrap("📊", "系统指标", body, "metrics"))


async def _render_tools_region(hub, started: bool, context: str) -> HTMLResponse:
    tool_names = [
        ("📄", "文档生成", "/tree/form/generate"),
        ("🔬", "代码分析", "/tree/kg/explore"),
        ("🌐", "网络搜索", "/tree/chat/stream"),
        ("📊", "数据可视化", "/tree/sse/ui"),
        ("🧪", "模型评测", "/tree/form/generate"),
        ("🔍", "知识检索", "/tree/kg/explore"),
    ]
    body = '<div style="display:flex;flex-wrap:wrap;gap:4px">'
    for icon, name, endpoint in tool_names:
        body += (
            f'<button class="lc-tool-btn" '
            f'hx-post="{endpoint}" hx-target="#lc-execute-output" hx-swap="innerHTML" '
            f'hx-vals=\'{{"goal":"{name}"}}\''
            f'>{icon} {name}</button>'
        )
    body += '</div>'
    return HTMLResponse(_region_wrap("🔧", "可用工具", body, "tools",
        extra_actions='<button class="lc-btn-icon" '
        'hx-get="/tree/living/discover-tools" hx-target="closest .lc-region-body" '
        'hx-swap="innerHTML" title="发现新工具">🔍</button>'))


async def _render_memory_region(hub, started: bool, context: str) -> HTMLResponse:
    if not started:
        body = '<p style="color:var(--dim);font-size:12px">等待系统...</p>'
    elif context.strip():
        body = (
            f'<div id="lc-memory-content">'
            f'<div style="color:var(--dim);font-size:11px">正在召回相关记忆...</div>'
            f'</div>'
            f'<div hx-get="/tree/living/region-content/memory?context={_html.escape(context[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML" hx-target="#lc-memory-content">'
            f'</div>'
        )
    else:
        body = '<p style="color:var(--dim);font-size:12px">输入问题后召回相关记忆</p>'
    return HTMLResponse(_region_wrap("🧩", "记忆召回", body, "memory"))


# ── LLM-generated region content endpoints ──

@living_router.get("/living/region-content/{content_type}")
async def tree_living_region_content(
    request: Request, content_type: str, context: str = Query(default="")
):
    """LLM generates content for a specific region type based on context."""
    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<p style="color:var(--dim);font-size:12px">系统就绪中...</p>')

    if content_type == "plan":
        return await _generate_plan_content(hub, context)
    elif content_type == "insight":
        return await _generate_insight_content(hub, context)
    elif content_type == "metrics":
        return await _generate_metrics_content(hub)
    elif content_type == "memory":
        return await _generate_memory_content(hub, context)

    return HTMLResponse(f'<p style="color:var(--dim)">未知内容类型: {content_type}</p>')


async def _generate_plan_content(hub, context: str) -> HTMLResponse:
    try:
        consc = hub.world.consciousness
        resp = await consc.chain_of_thought(
            f"为以下任务生成3-5个执行步骤。输出JSON: "
            f'{{"steps":["步骤1","步骤2",...]}}。任务: {context}',
            steps=1,
        )
        text = resp if isinstance(resp, str) else ""
        try:
            data = _json.loads(text[text.find("{"):text.rfind("}") + 1])
            steps = data.get("steps", [])
        except Exception:
            steps = [s.strip() for s in text.split("\n") if s.strip() and len(s.strip()) > 5][:5]

        html = '<ol style="margin:0;padding-left:1.2em;font-size:12px;line-height:1.6">'
        for i, step in enumerate(steps[:5]):
            html += (
                f'<li style="margin:4px 0">'
                f'<span style="color:var(--accent)">步骤{i+1}</span> '
                f'{_html.escape(step[:100])}</li>'
            )
        html += '</ol>'
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<p style="color:var(--dim);font-size:11px">规划生成失败: {_html.escape(str(e)[:100])}</p>')


async def _generate_insight_content(hub, context: str) -> HTMLResponse:
    try:
        consc = hub.world.consciousness
        resp = await consc.chain_of_thought(
            f"关于 '{context}'，提供1-2条深刻洞见或反直觉的观察。"
            f"每条约30字，用 • 开头。只输出文本，不要JSON。",
            steps=1,
        )
        text = resp if isinstance(resp, str) else ""
        lines = [l.strip() for l in text.split("\n") if l.strip()][:3]
        html = '<div style="font-size:11px;line-height:1.5;color:var(--text)">'
        for line in lines:
            clean = line.lstrip("•- ").strip()[:150]
            if clean:
                html += f'<div style="margin:4px 0;padding:4px 8px;background:rgba(100,150,100,0.05);border-radius:4px">💡 {_html.escape(clean)}</div>'
        html += '</div>'
        return HTMLResponse(html or '<p style="color:var(--dim);font-size:11px">暂无洞见</p>')
    except Exception as e:
        return HTMLResponse(f'<p style="color:var(--dim);font-size:11px">洞见生成失败</p>')


async def _generate_metrics_content(hub) -> HTMLResponse:
    try:
        health_data = await _collect_health_data(hub)
        html = '<div style="font-size:11px;line-height:1.6">'
        items = [
            ("状态", health_data.get("status", "?"), "var(--accent)"),
            ("评分", f"{health_data.get('score', 0):.0%}", "var(--accent)"),
            ("神经连接", health_data.get("synapses", "—"), "var(--dim)"),
            ("感受", health_data.get("affect", "—"), "var(--dim)"),
            ("周期", health_data.get("cycles", "—"), "var(--dim)"),
            ("意识深度", health_data.get("consciousness_gap", "—"), "var(--dim)"),
        ]
        for label, value, color in items:
            html += (
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:2px 0;border-bottom:1px solid var(--border)">'
                f'<span>{label}</span><span style="color:{color}">{value}</span></div>'
            )
        html += '</div>'
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse('<p style="color:var(--dim);font-size:11px">指标加载失败</p>')


async def _generate_memory_content(hub, context: str) -> HTMLResponse:
    try:
        world = hub.world
        mem = getattr(world, "struct_memory", None)
        if mem:
            entries, synthesis = await mem.retrieve_for_query(context, top_k=3)
            if entries:
                html = '<div style="font-size:11px;line-height:1.5">'
                for e in entries[:3]:
                    content = getattr(e, "content", str(e))[:120]
                    html += (
                        f'<div style="margin:4px 0;padding:4px 6px;'
                        f'background:rgba(100,150,180,0.05);border-radius:3px">'
                        f'🧩 {_html.escape(content)}</div>'
                    )
                html += '</div>'
                return HTMLResponse(html)
        return HTMLResponse('<p style="color:var(--dim);font-size:11px">暂无相关记忆</p>')
    except Exception:
        return HTMLResponse('<p style="color:var(--dim);font-size:11px">记忆召回失败</p>')


# ── Dynamic region management ──

@living_router.get("/living/add-region")
async def tree_living_add_region(
    request: Request,
    region_type: str = Query(default="insight"),
    context: str = Query(default=""),
):
    """Add a new region to the canvas dynamically."""
    rt = _REGION_TYPES.get(region_type, _REGION_TYPES["insight"])
    region_id = f"dyn-{region_type}-{int(_time.time() * 1000) % 10000}"
    html = (
        f'<div class="lc-region lc-{region_type}" id="lc-{region_id}" '
        f'hx-get="/tree/living/region/{region_type}?context={_html.escape(context[:100])}" '
        f'hx-trigger="revealed" hx-swap="innerHTML">'
        f'<div class="lc-loading">{rt["icon"]} {rt["label"]} 加载中...</div>'
        f'</div>'
    )
    return HTMLResponse(html)


@living_router.get("/living/discover-tools")
async def tree_living_discover_tools(request: Request):
    """Discover available tools from the hub."""
    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<p style="color:var(--dim);font-size:11px">系统就绪中...</p>')

    tools_list = []
    try:
        world = hub.world
        tm = getattr(world, "tool_market", None)
        if tm:
            discovered = tm.discover_tools()[:10]
            for t in discovered:
                name = getattr(t, "name", str(t))
                desc = getattr(t, "description", "")[:60]
                tools_list.append(f'<div style="font-size:11px;padding:2px 0">{name}</div>')
    except Exception:
        pass

    if not tools_list:
        tools_list = [
            '<div style="font-size:11px;color:var(--dim)">web_reach · doc_engine · code_engine</div>',
            '<div style="font-size:11px;color:var(--dim)">spark_search · kg_retrieve · skill_factory</div>',
        ]

    return HTMLResponse(
        '<div style="font-size:11px;line-height:1.5;margin-top:4px">'
        + "\n".join(tools_list)
        + '</div>'
    )


# ── Layout switch (OOB — update canvas without reload) ──

@living_router.post("/living/switch-mode")
async def tree_living_switch_mode(request: Request):
    """Switch layout mode. Re-renders the canvas regions.

    Uses OOB (out-of-band) swaps to update multiple regions simultaneously.
    """
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {"mode": form_data.get("mode", "focus"), "context": form_data.get("context", "")}

    mode = body.get("mode", "focus")
    context = body.get("context", "")
    regions = _regions_for_mode(mode, context)

    parts = []
    for r in regions:
        rt = _REGION_TYPES.get(r["type"], _REGION_TYPES["chat"])
        parts.append(
            f'<div class="lc-region lc-{r["type"]}" id="lc-{r["id"]}" '
            f'style="grid-column:{r["col"]}/span {r["w"]};grid-row:{r["row"]}/span {r["h"]}" '
            f'hx-get="/tree/living/region/{r["type"]}?context={_html.escape(context[:100])}" '
            f'hx-trigger="revealed" hx-swap="innerHTML">'
            f'<div class="lc-loading">{rt["icon"]} {rt["label"]} 加载中...</div>'
            f'</div>'
        )

    return HTMLResponse("\n".join(parts))
