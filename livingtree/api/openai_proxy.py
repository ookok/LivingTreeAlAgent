"""OpenCode → OpenAI compatible proxy (Python).
Communicates with OpenCode serve at localhost:4096.
Only proxies the 'opencode' provider (free models)."""
from __future__ import annotations

import asyncio, json, time, aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

OPENCODE_URL = "http://localhost:4096"

class ChatMsg(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    model: str
    messages: list[ChatMsg]
    stream: bool = False
    max_tokens: int = Field(default=4096, ge=1, le=131072)

def setup_openai_proxy(app: FastAPI):
    @app.get("/v1/models")
    async def list_models(request: Request):
        """List only opencode provider models."""
        async with aiohttp.ClientSession() as s:
            try:
                async with s.get(f"{OPENCODE_URL}/config/providers", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    data = await r.json()
                    providers = data.get("providers", [])
                    models = []
                    for p in providers:
                        if p.get("id") != "opencode": continue
                        for mid, mdata in p.get("models", {}).items():
                            if not isinstance(mdata, dict): continue
                        # Free detection: cost.input == 0 && cost.output == 0
                        cost = mdata.get("cost", {})
                        is_free = cost.get("input", 1) == 0 and cost.get("output", 1) == 0
                            models.append({
                                "id": f"opencode/{mid}",
                                "object": "model",
                                "owned_by": "opencode",
                                "name": mdata.get("name", mid),
                                "free": is_free,
                                "context_length": mdata.get("limit", {}).get("context", 4096),
                            })
                    return {"object": "list", "data": models}
            except Exception as e:
                logger.warning(f"models fetch: {e}")
                return {"object": "list", "data": [
                    {"id": "opencode/minimax-m2.5-free", "object": "model"}, {"id": "opencode/hy3-preview-free", "object": "model"}, {"id": "opencode/nemotron-3-super-free", "object": "model"},
                ]}

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatReq, request: Request):
        """Forward to OpenCode session API, return OpenAI-format response."""
        model = req.model.split("/")[-1] if "/" in req.model else req.model
        user_content = "\n".join(m.content for m in req.messages if m.role != "system")
        system_msgs = [m.content for m in req.messages if m.role == "system"]

        async with aiohttp.ClientSession() as s:
            # Create session
            session_body = {"model": {"providerID": "opencode", "modelID": model}}
            if system_msgs:
                session_body["system"] = system_msgs[0]

            async with s.post(f"{OPENCODE_URL}/session", json=session_body, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 201 and r.status != 200:
                    raise HTTPException(status_code=502, detail=f"Session create failed: {r.status}")
                sid = (await r.json()).get("id") or (await r.json()).get("data", {}).get("id")

            if not sid:
                raise HTTPException(status_code=502, detail="No session ID")

            # Send prompt → POST /session/{id}/message
            async with s.post(f"{OPENCODE_URL}/session/{sid}/message",
                json={"parts": [{"type": "text", "text": user_content}]},
                timeout=aiohttp.ClientTimeout(total=10)) as _:
                pass

            if req.stream:
                return StreamingResponse(_stream(s, sid, model, req), media_type="text/event-stream")
            else:
                result = await _poll(s, sid, req)
                return {
                    "id": f"chatcmpl-{int(time.time()*1000)}",
                    "object": "chat.completion", "created": int(time.time()),
                    "model": req.model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": result}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": len(user_content)//3, "completion_tokens": len(result)//3, "total_tokens": (len(user_content)+len(result))//3},
                }

async def _poll(s, sid, req, max_wait=120):
    """Poll GET /session/{id}/message until assistant responds."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            async with s.get(f"{OPENCODE_URL}/session/{sid}/message", timeout=aiohttp.ClientTimeout(total=10)) as r:
                msgs = await r.json()
                msgs = msgs if isinstance(msgs, list) else msgs.get("data", msgs.get("message", msgs.get("messages", [])))
                for msg in reversed(msgs if isinstance(msgs, list) else []):
                    if msg.get("info", {}).get("role") != "assistant": continue
                    parts = msg.get("parts", [])
                    content = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
                    if content:
                        return content
        except Exception as e:
            logger.warning(f"poll: {e}")
        await asyncio.sleep(0.5)
    return "[Timeout] No response from OpenCode"

async def _stream(s, sid, model, req, max_wait=120):
    """Stream response via SSE."""
    chunk_id = f"chatcmpl-{int(time.time()*1000)}"
    deadline = time.time() + max_wait
    last_len = 0
    while time.time() < deadline:
        try:
            async with s.get(f"{OPENCODE_URL}/session/{sid}/message", timeout=aiohttp.ClientTimeout(total=10)) as r:
                msgs = await r.json()
                msgs = msgs if isinstance(msgs, list) else msgs.get("data", msgs.get("message", msgs.get("messages", [])))
                for msg in reversed(msgs if isinstance(msgs, list) else []):
                    if msg.get("info", {}).get("role") != "assistant": continue
                    parts = msg.get("parts", [])
                    content = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
                    if len(content) > last_len:
                        new = content[last_len:]
                        last_len = len(content)
                        yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': f'opencode/{model}', 'choices': [{'index': 0, 'delta': {'content': new}, 'finish_reason': None}])}\n\n"
                        if msg.get("info", {}).get("finish"):
                            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': f'opencode/{model}', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
        except: pass
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"

    logger.info("OpenAI proxy registered (opencode provider only)")
