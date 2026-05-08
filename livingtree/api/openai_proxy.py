"""LivingTree OpenAI-Compatible API Proxy.

Converts LivingTree's ModelRegistry + TreeLLM into standard OpenAI API.
Any OpenAI-compatible client can use LivingTree's models (free + paid).
Equivalent to opencode2api but in Python, integrated with LivingTree.

Endpoints:
    GET  /v1/models                — List all available models
    POST /v1/chat/completions      — Chat completions (streaming supported)
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from loguru import logger


# ═══ Request Models ═══

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: int = Field(default=4096, ge=1, le=131072)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "livingtree"

# ═══ Proxy Implementation ═══

def setup_openai_proxy(app: FastAPI) -> None:
    """Register OpenAI-compatible endpoints on the FastAPI app."""

    @app.get("/v1/models")
    async def list_models(request: Request) -> dict:
        """List all available models from LivingTree's registry."""
        hub = request.app.state.hub
        models = []

        # From ModelRegistry
        if hub and hasattr(hub, 'model_registry'):
            try:
                registry = hub.model_registry
                for name in registry.get_all_providers():
                    p = registry._providers.get(name)
                    if p and p.models:
                        for m in p.models:
                            models.append({
                                "id": m.id,
                                "object": "model",
                                "created": m.created or int(time.time()),
                                "owned_by": m.owned_by or name,
                                "free": m.free,
                                "tier": m.tier,
                            })
            except Exception as e:
                logger.debug(f"Model registry query failed: {e}")

        # Fallback: direct provider list
        if not models:
            models = [
                {"id": "modelscope/DeepSeek-V4-Flash", "object": "model", "owned_by": "modelscope", "free": True},
                {"id": "modelscope/DeepSeek-R1-0528", "object": "model", "owned_by": "modelscope", "free": True},
                {"id": "modelscope/Qwen3-235B-A22B", "object": "model", "owned_by": "modelscope", "free": True},
                {"id": "deepseek/deepseek-chat", "object": "model", "owned_by": "deepseek", "free": True},
                {"id": "deepseek/deepseek-reasoner", "object": "model", "owned_by": "deepseek", "free": True},
                {"id": "siliconflow/Qwen2.5-7B", "object": "model", "owned_by": "siliconflow", "free": True},
                {"id": "siliconflow/DeepSeek-V3", "object": "model", "owned_by": "siliconflow", "free": True},
                {"id": "zhipu/glm-4-flash", "object": "model", "owned_by": "zhipu", "free": True},
                {"id": "qwen/qwen-turbo", "object": "model", "owned_by": "qwen", "free": True},
                {"id": "spark/spark-lite", "object": "model", "owned_by": "spark", "free": True},
                {"id": "bailing/Baichuan4", "object": "model", "owned_by": "bailing", "free": True},
                {"id": "stepfun/step-1-flash", "object": "model", "owned_by": "stepfun", "free": True},
                {"id": "longcat/longcat-flash", "object": "model", "owned_by": "longcat", "free": True},
                {"id": "minimax/minimax-m2.5-free", "object": "model", "owned_by": "minimax", "free": True},
            ]

        return {"object": "list", "data": models}

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest, request: Request):
        """OpenAI-compatible chat completions using LivingTree's TreeLLM."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")

        # Determine provider from model name
        provider = req.model.split("/")[0] if "/" in req.model else "deepseek"
        model_name = req.model.split("/")[-1] if "/" in req.model else req.model

        # Build prompt from messages
        system_prompts = [m.content for m in req.messages if m.role == "system"]
        user_content = "\n".join(m.content for m in req.messages if m.role != "system")
        if system_prompts:
            user_content = "System: " + "\n".join(system_prompts) + "\n\nUser: " + user_content

        if req.stream:
            return StreamingResponse(
                _stream_response(hub, provider, model_name, user_content, req),
                media_type="text/event-stream",
            )
        else:
            try:
                result = await _complete(hub, provider, model_name, user_content, req)
                return {
                    "id": f"chatcmpl-{int(time.time()*1000)}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": result},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": len(user_content)//3, "completion_tokens": len(result)//3, "total_tokens": (len(user_content)+len(result))//3},
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def _complete(hub, provider: str, model: str, content: str, req: ChatCompletionRequest) -> str:
        """Execute a non-streaming completion."""
        result_text = ""

        # Try via TreeLLM consciousness
        if hasattr(hub, 'world') and hub.world and hasattr(hub.world, 'consciousness'):
            try:
                async for token in hub.world.consciousness.stream_of_thought(content):
                    result_text += token
                    if len(result_text) >= req.max_tokens:
                        break
                if result_text:
                    return result_text
            except Exception as e:
                logger.warning(f"Consciousness stream failed: {e}")

        # Fallback: direct provider call
        try:
            from livingtree.trellm.providers import Provider, ProviderResult
            prov = Provider(provider, "", "", model)
            result = await prov._request_with_retry({
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": req.max_tokens,
                "temperature": req.temperature,
            })
            return result.text or f"[Provider {provider} returned empty response]"
        except Exception as e:
            return f"[Error: {str(e)[:200]}]"

    async def _stream_response(hub, provider: str, model: str, content: str, req: ChatCompletionRequest):
        """SSE stream response."""
        chunk_id = f"chatcmpl-{int(time.time()*1000)}"
        full_content = ""

        try:
            if hasattr(hub, 'world') and hub.world and hasattr(hub.world, 'consciousness'):
                async for token in hub.world.consciousness.stream_of_thought(content):
                    full_content += token
                    yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': req.model, 'choices': [{'index': 0, 'delta': {'content': token}, 'finish_reason': None}]})}\n\n"
                    if len(full_content) >= req.max_tokens:
                        break
                if full_content:
                    yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': req.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
        except Exception as e:
            logger.warning(f"Stream failed: {e}")

        # Fallback: single chunk
        try:
            result = await _complete(hub, provider, model, content, req)
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': req.model, 'choices': [{'index': 0, 'delta': {'content': result}, 'finish_reason': None}]})}\n\n"
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': req.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    logger.info("OpenAI-compatible proxy registered at /v1/models, /v1/chat/completions")
