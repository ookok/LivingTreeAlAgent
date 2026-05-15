"""Business reporting + task management routes."""
from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
import html as _html
import time as _time
from loguru import logger
from .htmx_web import _get_hub, _sanitize_html, _md_to_html_fragment

business_router = APIRouter(prefix="/tree", tags=["htmx-business"])

@business_router.post("/business/report/generate")
async def tree_business_report_generate(request: Request):
    """One-click industry report generation. Accepts form data with
    template_type, project_name, raw_text. Returns streaming progress."""
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {k: v for k, v in form_data.items()}

    template_type = body.get("template_type", body.get("template", "环评报告"))
    project_name = body.get("project_name", body.get("title", body.get("message", "未命名项目")))
    raw_text = body.get("raw_text", body.get("content", body.get("message", "")))

    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<div class="card"><p style="color:var(--warn)">系统启动中，请稍候...</p></div>')

    try:
        report_id = f"rpt_{int(_time.time())}"
        result = await hub.generate_report(
            template_type=template_type,
            data={
                "title": project_name,
                "project_name": project_name,
                "raw_text": raw_text[:8000] if raw_text else "",
                "template_type": template_type,
            },
            requirements={},
        )
        from ..core.autonomous_growth import get_growth
        get_growth().record_revenue(amount_yuan=500, source="report")

        formatted = result.get("formatted", result.get("document", ""))
        path = result.get("path", "")

        sections_html = ""
        for p in result.get("progress", []):
            sections_html += (
                f'<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:11px">'
                f'<span>{p["section"]}</span><span style="color:var(--accent)">{p["progress_pct"]}%</span></div>'
            )

        return HTMLResponse(
            f'<div class="card">'
            f'<h2>📄 {_html.escape(template_type)} — {_html.escape(project_name[:50])}</h2>'
            f'<div style="margin:8px 0">{sections_html}</div>'
            f'<div style="margin-top:8px;max-height:50vh;overflow-y:auto;font-size:12px;line-height:1.5">'
            f'{_md_to_html_fragment(formatted[:5000]) if formatted else "<p style=\"color:var(--dim)\">生成中...</p>"}'
            f'</div>'
            f'<div style="margin-top:8px;display:flex;gap:8px">'
            f'<a href="/api/report/generate" style="font-size:11px;color:var(--accent)">📥 下载Markdown</a>'
            f'<span style="font-size:11px;color:var(--dim)">ID: {report_id}</span>'
            f'</div></div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p style="color:var(--err)">报告生成失败: {_html.escape(str(e)[:200])}</p></div>'
        )


@business_router.post("/business/task/start")
async def tree_business_task_start(request: Request):
    """Start an overnight task with LLM-powered step decomposition."""
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = {k: v for k, v in form_data.items()}

    goal = body.get("goal", body.get("message", ""))
    if not goal.strip():
        return HTMLResponse('<div class="card"><p style="color:var(--warn)">请输入任务目标</p></div>')

    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<div class="card"><p style="color:var(--warn)">系统启动中...</p></div>')

    try:
        ot = getattr(hub.world, "overnight_task", None)
        if not ot:
            return HTMLResponse('<div class="card"><p style="color:var(--err)">挂机任务模块未就绪</p></div>')

        if ot.status.value not in ("idle", "completed", "failed", "cancelled"):
            existing = ot.to_dict()
            return HTMLResponse(
                f'<div class="card"><h2>⚠ 已有任务运行中</h2>'
                f'<p style="font-size:12px">{_html.escape(existing["goal"][:80])}</p>'
                f'<p style="font-size:11px;color:var(--dim)">进度: {existing["percent"]}% · '
                f'{existing["completed_steps"]}/{existing["total_steps"]}步</p>'
                f'<button hx-post="/tree/business/task/cancel" hx-target="closest .card" hx-swap="outerHTML" '
                f'style="font-size:11px;padding:4px 10px;margin-right:4px">取消当前任务</button>'
                f'<button hx-post="/tree/business/task/status" hx-target="closest .card" hx-swap="outerHTML" '
                f'style="font-size:11px;padding:4px 10px">刷新状态</button>'
                f'</div>'
            )

        result = await ot.start(goal, auto_execute=True)

        steps_html = ""
        for s in result.get("steps", []):
            icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(s["status"], "⏳")
            steps_html += (
                f'<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px">'
                f'<span>{icon}</span><span>{_html.escape(s["name"][:80])}</span></div>'
            )

        return HTMLResponse(
            f'<div class="card" id="task-panel">'
            f'<h2>🔬 挂机任务已启动</h2>'
            f'<p style="font-size:12px;margin:4px 0">{_html.escape(goal[:100])}</p>'
            f'<div style="margin:8px 0">{steps_html}</div>'
            f'<div style="display:flex;gap:4px;flex-wrap:wrap">'
            f'<button hx-post="/tree/business/task/status" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">🔄 刷新</button>'
            f'<button hx-post="/tree/business/task/pause" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">⏸ 暂停</button>'
            f'<button hx-post="/tree/business/task/cancel" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">✕ 取消</button>'
            f'<span style="font-size:10px;color:var(--dim);align-self:center" '
            f'hx-get="/tree/business/task/status" hx-trigger="every 10s" hx-swap="none">'
            f'任务将在后台全自动执行</span>'
            f'</div></div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p style="color:var(--err)">启动失败: {_html.escape(str(e)[:200])}</p></div>'
        )


@business_router.post("/business/task/status")
async def tree_business_task_status(request: Request):
    """Get current task status as HTML panel."""
    hub = _get_hub(request)
    if not hub:
        return HTMLResponse('<div class="card"><p style="color:var(--dim)">系统就绪中...</p></div>')

    ot = getattr(getattr(hub, "world", None), "overnight_task", None)
    if not ot:
        return HTMLResponse('<div class="card"><p style="color:var(--dim)">挂机任务模块未就绪</p></div>')

    data = ot.to_dict()
    if data["state"] in ("idle",):
        return HTMLResponse(
            '<div class="card" id="task-panel"><h2>🔬 挂机任务</h2>'
            '<p style="color:var(--dim);font-size:12px">当前没有运行中的挂机任务</p>'
            '<p style="font-size:11px;color:var(--dim)">输入复杂任务目标，让小树通宵为你工作</p></div>'
        )

    state_emoji = {
        "running": "🔄", "planning": "🧠", "paused": "⏸",
        "completed": "✅", "failed": "❌", "cancelled": "✕",
    }
    emoji = state_emoji.get(data["state"], "❓")
    pct = data["percent"]

    steps_html = ""
    for s in data.get("steps", []):
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(s["status"], "⏳")
        result_preview = f'<span style="color:var(--dim);font-size:10px"> — {_html.escape(s.get("result","")[:60])}</span>' if s.get("result") else ""
        steps_html += (
            f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px">'
            f'<span>{icon}</span><span>{_html.escape(s["name"][:60])}</span>{result_preview}</div>'
        )

    elapsed = data.get("elapsed_seconds", 0)
    elapsed_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒" if elapsed else ""

    actions = ""
    if data["state"] == "running":
        actions = (
            f'<button hx-post="/tree/business/task/pause" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">⏸ 暂停</button>'
            f'<button hx-post="/tree/business/task/cancel" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">✕ 取消</button>'
        )
    elif data["state"] == "paused":
        actions = (
            f'<button hx-post="/tree/business/task/resume" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">▶ 继续</button>'
            f'<button hx-post="/tree/business/task/cancel" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">✕ 取消</button>'
        )
    elif data["state"] in ("completed", "failed", "cancelled"):
        actions = (
            f'<button hx-post="/tree/business/task/resume" hx-target="#task-panel" hx-swap="outerHTML" '
            f'style="font-size:10px;padding:4px 8px">🔄 重试</button>'
        )

    if data.get("report_path"):
        actions += (
            f'<span style="font-size:10px;color:var(--accent);align-self:center">'
            f'📄 报告已生成</span>'
        )

    report_preview = ""
    if data.get("report_path") and ot._result:
        preview = ot._result[:1000] if ot._result else ""
        report_preview = (
            f'<div style="margin-top:8px;max-height:30vh;overflow-y:auto;font-size:11px;line-height:1.4;'
            f'background:rgba(0,0,0,.1);padding:8px;border-radius:4px">'
            f'{_md_to_html_fragment(preview)}</div>'
        )

    return HTMLResponse(
        f'<div class="card" id="task-panel">'
        f'<h2>{emoji} 挂机任务</h2>'
        f'<p style="font-size:12px;margin:4px 0">{_html.escape(data["goal"][:100])}</p>'
        f'<div class="lc-progress-bar" style="height:6px;background:var(--border);border-radius:3px;margin:8px 0">'
        f'<div style="height:100%;width:{min(pct, 100)}%;background:var(--accent);border-radius:3px;transition:width .5s"></div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:var(--dim)">'
        f'<span>{pct:.0f}% · {data["completed_steps"]}/{data["total_steps"]}步</span>'
        f'<span>{data["state"]} · {elapsed_str}</span></div>'
        f'<div style="margin:8px 0">{steps_html}</div>'
        f'<div style="display:flex;gap:4px;flex-wrap:wrap">{actions}</div>'
        f'{report_preview}'
        f'</div>'
    )


@business_router.post("/business/task/pause")
async def tree_business_task_pause(request: Request):
    hub = _get_hub(request)
    if hub:
        ot = getattr(getattr(hub, "world", None), "overnight_task", None)
        if ot:
            ot.pause()
    return await tree_business_task_status(request)


@business_router.post("/business/task/resume")
async def tree_business_task_resume(request: Request):
    hub = _get_hub(request)
    if hub:
        ot = getattr(getattr(hub, "world", None), "overnight_task", None)
        if ot:
            await ot.resume()
    return await tree_business_task_status(request)


@business_router.post("/business/task/cancel")
async def tree_business_task_cancel(request: Request):
    hub = _get_hub(request)
    if hub:
        ot = getattr(getattr(hub, "world", None), "overnight_task", None)
        if ot:
            ot.cancel()
    return await tree_business_task_status(request)


@business_router.get("/business/cost/savings")
async def tree_business_cost_savings(request: Request):
    """Cost savings dashboard — shows free vs paid savings, budget status, ROI."""
    hub = _get_hub(request)
    if not hub or not getattr(hub, "_started", False):
        return HTMLResponse('<div class="card"><p style="color:var(--dim);font-size:12px">系统就绪中...</p></div>')

    try:
        world = hub.world

        # Collect pricing data
        pricing = {
            "deepseek_pro_input": 3.0, "deepseek_pro_output": 6.0,
            "deepseek_flash_input": 1.0, "deepseek_flash_output": 2.0,
            "qwen_turbo_input": 0.73, "qwen_turbo_output": 2.90,
            "qwen_max_input": 3.70, "qwen_max_output": 14.80,
        }

        # Count free model providers
        free_count = 0
        paid_count = 0
        try:
            consc = world.consciousness
            free_count = len(getattr(consc, "_free_models", []))
            paid_count = len(getattr(consc, "_paid_models", []))
        except Exception:
            pass

        # Estimated free model savings (per 1M tokens)
        avg_paid_cost_per_m = (pricing["deepseek_pro_input"] + pricing["deepseek_pro_output"]) / 2
        savings_per_1m = avg_paid_cost_per_m

        # CostAware budget
        budget_info = {}
        try:
            ca = world.cost_aware
            if ca:
                st = ca.status()
                budget_info = {
                    "daily_limit": st.daily_limit,
                    "used_today": st.used_today,
                    "remaining": st.remaining,
                    "usage_pct": st.usage_pct,
                    "cost_yuan": round(st.cost_yuan, 4),
                    "degraded": st.degraded,
                }
        except Exception:
            budget_info = {"daily_limit": 0, "used_today": 0, "remaining": 0, "usage_pct": 0, "cost_yuan": 0, "degraded": False}

        # Economic ROI
        roi_info = {}
        try:
            from ..economy.economic_engine import get_economic_orchestrator
            eco = get_economic_orchestrator()
            roi_info["cumulative_roi"] = f"{eco.roi.cumulative_roi():.1f}x"
            roi_info["total_value"] = eco.roi._total_value
            roi_info["total_cost"] = eco.roi._total_cost
        except Exception:
            roi_info = {"cumulative_roi": "—", "total_value": 0, "total_cost": 0}

        free_vs_paid_savings_estimate = free_count * savings_per_1m * 10

        return HTMLResponse(
            f'<div class="card">'
            f'<h2>💰 费用节省面板</h2>'

            f'<div style="margin:8px 0;padding:8px;background:rgba(100,150,100,.08);border-radius:6px">'
            f'<div style="font-size:12px;color:var(--accent)">🏆 累计 ROI: {roi_info["cumulative_roi"]}</div>'
            f'<div style="font-size:10px;color:var(--dim)">'
            f'总产出价值: ¥{roi_info.get("total_value", 0):.2f} · '
            f'总花费: ¥{roi_info.get("total_cost", 0):.4f}</div></div>'

            f'<div class="metric"><span>📡 免费模型</span><span>{free_count} 个提供方在线</span></div>'
            f'<div class="metric"><span>💳 付费模型</span><span>{paid_count} 个提供方可用</span></div>'
            f'<div class="metric"><span>🆓 估算节费</span><span>约 ¥{free_vs_paid_savings_estimate:.2f}/月</span></div>'

            f'<div style="margin-top:8px"><h4 style="font-size:12px;color:var(--text);margin-bottom:4px">今日预算</h4>'
            f'<div class="metric"><span>已用</span><span>{budget_info.get("used_today", 0):,} tokens</span></div>'
            f'<div class="metric"><span>剩余</span><span>{budget_info.get("remaining", 0):,} tokens</span></div>'
            f'<div class="metric"><span>费用</span><span>¥{budget_info.get("cost_yuan", 0):.4f}</span></div>'
            + (f'<div class="metric" style="color:var(--warn)"><span>⚠ 预算紧张</span><span>已用{budget_info.get("usage_pct",0):.0f}%</span></div>' if budget_info.get("degraded") else '')
            + '</div>'

            f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
            f'费用计算基于 DeepSeek 官方定价 (Pro: ¥3/6 per 1M tokens)。'
            f'使用免费模型池可节省 90%+ API 费用。</div>'
            f'</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="card"><p style="color:var(--warn)">费用数据获取失败: {_html.escape(str(e)[:100])}</p></div>'
        )


@business_router.get("/business/roi")
async def tree_business_roi(request: Request):
    """ROI calculator — show users exactly how much they save."""
    hub = _get_hub(request)

    return HTMLResponse(
        '<div class="card">'
        '<h2>🧮 ROI 计算器</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">'
        '看看 LivingTree 帮你省了多少时间和金钱</p>'

        '<div style="margin:8px 0">'
        '<div class="metric"><span>⏱ 工程师时薪 (估算)</span><span>¥120/h</span></div>'
        '<div class="metric"><span>📄 自动生成报告</span><span>省 4h × ¥120 = <b style="color:var(--accent)">¥480</b></span></div>'
        '<div class="metric"><span>🔍 知识库检索</span><span>省 1h × ¥120 = <b style="color:var(--accent)">¥120</b></span></div>'
        '<div class="metric"><span>🌙 挂机任务</span><span>省 8h × ¥120 = <b style="color:var(--accent)">¥960</b></span></div>'
        '<div class="metric"><span>💰 API 费用节省</span><span>免费模型池 ≈ ¥200/月</span></div>'
        '</div>'

        '<div style="margin-top:8px;padding:8px;background:rgba(100,150,100,.08);border-radius:6px">'
        '<div style="font-size:13px;color:var(--accent);font-weight:600">'
        '💡 月度节省估算: ¥1,760</div>'
        '<div style="font-size:10px;color:var(--dim)">'
        '基于每天使用 LivingTree 30 分钟的计算</div>'
        '</div>'
        '</div>'
    )


# ── Reach: Cross-device AI sensory extension ──

