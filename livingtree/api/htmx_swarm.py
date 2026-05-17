"""HTMX Swarm routes — P2P swarm collaboration."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

swarm_router = APIRouter(prefix="/swarm", tags=["swarm"])

@swarm_router.get("/swarm/panel")
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


@swarm_router.post("/swarm/share-cell")
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


@swarm_router.post("/swarm/sync-knowledge")
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



__all__ = ["swarm_router"]
