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


__all__ = ["sse_router"]
