"""API routes for the LivingTree server."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from loguru import logger


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    intent: Optional[str] = None
    plan: list[dict[str, Any]] = Field(default_factory=list)
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    mutations: int = 0
    generation: int = 0
    success_rate: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReportRequest(BaseModel):
    template_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)


class TrainRequest(BaseModel):
    cell_name: str
    training_data: list[dict] = Field(default_factory=list)
    epochs: int = 3


class DrillRequest(BaseModel):
    cell_name: str
    model_name: str
    dataset: list[dict] = Field(default_factory=list)
    training_type: str = "lora"
    teacher_model: str = ""
    reward_model: str = ""


class QuantizeRequest(BaseModel):
    model_path: str
    method: str = "awq"


class DeployRequest(BaseModel):
    model_path: str
    port: int = 8000


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float = 0.0
    components: dict[str, str] = Field(default_factory=dict)


def setup_routes(app: FastAPI) -> None:
    """Register all API routes."""

    @app.get("/api/boot/progress")
    async def boot_progress(request: Request) -> dict[str, Any]:
        """Get hub initialization progress for the web UI."""
        hub = request.app.state.hub
        if hub and getattr(hub, '_started', False):
            return {"stage": "ready", "pct": 100, "detail": "系统就绪"}
        bp = getattr(hub, '_boot_progress', None) if hub else None
        return bp or {"stage": "starting", "pct": 0, "detail": "正在初始化..."}

    @app.get("/api/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        """Health check endpoint."""
        hub = getattr(request.app.state, 'hub', None)
        components = {}
        if hub:
            if getattr(hub, '_started', False):
                status = hub.status() if hasattr(hub, 'status') else {}
                components = {
                    "life_engine": "ok" if status.get("life_engine") else "missing",
                    "cells": f"{status.get('cells', {}).get('registered', 0)} registered",
                    "knowledge": "ok" if status.get("knowledge") else "missing",
                    "network": status.get("network", {}).get("status", "unknown"),
                    "orchestrator": f"{status.get('orchestrator', {}).get('total_agents', 0)} agents",
                }
                return HealthResponse(status="healthy", version="2.1.0", components=components)
            else:
                bp = getattr(hub, '_boot_progress', {})
                return HealthResponse(status="starting", version="2.1.0",
                    components={"boot": bp.get("detail", "initializing...")})
        return HealthResponse(status="starting", version="2.1.0",
            components={"boot": "waiting for hub..."})

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request) -> ChatResponse:
        """Send a message to the life engine and get results."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")

        result = await hub.chat(req.message, **req.context)
        return ChatResponse(
            session_id=result["session_id"],
            intent=result.get("intent"),
            plan=result.get("plan", []),
            execution_results=result.get("execution_results", []),
            reflections=result.get("reflections", []),
            mutations=result.get("mutations", 0),
            generation=result.get("generation", 0),
            success_rate=result.get("success_rate", 0.0),
        )

    @app.get("/api/status")
    async def status(request: Request) -> dict[str, Any]:
        """Get the current status of the life form."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        try:
            if hasattr(hub, 'status'):
                return hub.status()
            return hub.get_status() if hasattr(hub, 'get_status') else {"version": "2.1.0", "online": True}
        except Exception as e:
            return {"error": str(e), "version": "2.1.0", "status": "initializing"}

    @app.get("/api/tools")
    async def list_tools(request: Request) -> list[dict[str, Any]]:
        """List all registered tools."""
        hub = request.app.state.hub
        if not hub:
            return []
        try:
            tools = hub.tool_market.discover_tools()
            return [t.model_dump() for t in tools]
        except Exception:
            return []

    @app.get("/api/skills")
    async def list_skills(request: Request) -> list[str]:
        """List all registered skills."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return hub.skill_factory.discover_skills()

    @app.get("/api/metrics")
    async def metrics(request: Request) -> dict[str, Any]:
        """Get runtime metrics."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return hub.metrics.get_snapshot() if hub.metrics else {}

    @app.post("/api/report/generate")
    async def generate_report(req: ReportRequest, request: Request) -> dict[str, Any]:
        """Generate an industrial report."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.generate_report(
            template_type=req.template_type,
            data=req.data,
            requirements=req.requirements,
        )

    @app.post("/api/cell/train")
    async def train_cell(req: TrainRequest, request: Request) -> dict[str, Any]:
        """Train an AI cell."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.train_cell(
            cell_name=req.cell_name,
            training_data=req.training_data,
            epochs=req.epochs,
        )

    @app.post("/api/drill/train")
    async def drill_train(req: DrillRequest, request: Request) -> dict[str, Any]:
        """Train a cell using MS-SWIFT automated drill pipeline."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.drill_train(
            cell_name=req.cell_name,
            model_name=req.model_name,
            dataset=req.dataset,
            training_type=req.training_type,
            teacher_model=req.teacher_model,
            reward_model=req.reward_model,
        )

    @app.get("/api/drill/models")
    async def list_drill_models(request: Request) -> list[str]:
        """List MS-SWIFT supported models."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return hub.drill.SUPPORTED_MODELS if hub.drill else []

    @app.get("/api/drill/system")
    async def drill_system_info(request: Request) -> dict[str, Any]:
        """Get system info for training optimization."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return hub.drill._system_info if hub.drill else {}

    @app.post("/api/drill/evaluate")
    async def drill_evaluate(request: Request, model_path: str = "", benchmarks: str = "") -> dict[str, Any]:
        """Evaluate a trained model."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        bench_list = benchmarks.split(",") if benchmarks else None
        return await hub.drill_evaluate(model_path, bench_list)

    @app.post("/api/drill/quantize")
    async def drill_quantize(req: QuantizeRequest, request: Request) -> dict[str, Any]:
        """Quantize a trained model."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.drill_quantize(req.model_path, req.method)

    @app.post("/api/drill/deploy")
    async def drill_deploy(req: DeployRequest, request: Request) -> dict[str, Any]:
        """Deploy a trained model as API server."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.drill_deploy(req.model_path, req.port)

    @app.get("/api/drill/queue")
    async def drill_queue(request: Request) -> list[dict[str, Any]]:
        jobs = hub.drill.get_queue() if hub.drill else []
        return [{"model_name": j.model_name, "training_type": j.training_type} for j in jobs]

    @app.get("/api/hitl/pending")
    async def hitl_pending(request: Request) -> list[dict[str, Any]]:
        """List pending HITL approval requests."""
        hub = request.app.state.hub
        if not hub or not hub.world.hitl:
            return []
        return [{"id": r.id, "task": r.task_name, "question": r.question,
                 "status": r.status, "created": r.created} for r in hub.world.hitl.get_pending()]

    @app.post("/api/hitl/approve")
    async def hitl_approve(request: Request) -> dict[str, Any]:
        """Approve a HITL request."""
        hub = request.app.state.hub
        body = await request.json()
        req_id = body.get("id", "")
        if hub and hub.world.hitl:
            ok = hub.world.hitl.approve(req_id, body.get("response", ""))
            return {"approved": ok}
        return {"approved": False, "error": "HITL not available"}

    @app.post("/api/hitl/deny")
    async def hitl_deny(request: Request) -> dict[str, Any]:
        hub = request.app.state.hub
        body = await request.json()
        if hub and hub.world.hitl:
            ok = hub.world.hitl.deny(body.get("id", ""), body.get("reason", ""))
            return {"denied": ok}
        return {"denied": False}

    @app.get("/api/cost/status")
    async def cost_status(request: Request) -> dict[str, Any]:
        """Get cost/budget status."""
        hub = request.app.state.hub
        if not hub or not hub.world.cost_aware:
            return {"error": "CostAware not available"}
        st = hub.world.cost_aware.status()
        return {"daily_limit": st.daily_limit, "used": st.used_today,
                "remaining": st.remaining, "usage_pct": st.usage_pct,
                "cost_yuan": round(st.cost_yuan, 4), "degraded": st.degraded}

    @app.get("/api/checkpoint/sessions")
    async def checkpoint_sessions(request: Request) -> list[str]:
        hub = request.app.state.hub
        if not hub or not hub.world.checkpoint:
            return []
        return await hub.world.checkpoint.list_sessions()

    @app.delete("/api/checkpoint/{session_id}")
    async def checkpoint_delete(session_id: str, request: Request) -> dict:
        hub = request.app.state.hub
        if hub and hub.world.checkpoint:
            await hub.world.checkpoint.delete(session_id)
            return {"deleted": True}
        return {"deleted": False}

    @app.get("/api/cells")
    async def list_cells(request: Request) -> list[dict[str, Any]]:
        """List all registered AI cells."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        cells = hub.cell_registry.discover()
        return [c.model_dump() if hasattr(c, 'model_dump') else {"name": getattr(c, 'name', 'unknown')} for c in cells]

    @app.post("/api/phage/absorb")
    async def absorb_repo(request: Request, repo_url: str = "") -> dict[str, Any]:
        """Absorb code patterns from a GitHub repository."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        if not repo_url:
            raise HTTPException(status_code=400, detail="repo_url is required")
        return await hub.absorb_github(repo_url)

    @app.get("/api/peers")
    async def list_peers(request: Request) -> list[dict[str, Any]]:
        """List discovered P2P peers."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        return await hub.discover_peers()

    @app.post("/api/web/chat")
    async def web_chat(request: Request):
        """SSE streaming endpoint for web frontend. Accepts {messages: [...]}."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        messages = body.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="messages required")

        last_msg = messages[-1].get("content", "") if messages else ""

        from fastapi.responses import StreamingResponse
        import json as _json, time as _time

        async def generate():
            sid = f"web_{int(_time.time()*1000)}"
            try:
                if hub.world and hub.world.consciousness:
                    async for token in hub.world.consciousness.stream_of_thought(last_msg):
                        yield f"data: {_json.dumps({'content': token, 'session_id': sid})}\n\n"
                else:
                    raise Exception("No consciousness available")
            except Exception:
                import traceback
                logger.warning(f"Web chat stream failed, using fallback: {traceback.format_exc()[-200:]}")
                reply = _fallback_reply(last_msg)
                for ch in reply:
                    yield f"data: {_json.dumps({'content': ch, 'session_id': sid})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")


def _fallback_reply(msg: str) -> str:
    return f"""你好！我是 LivingTree AI Agent 🌳

我收到了你的消息。当前模型服务正在初始化中，这是我的离线回复：

> "{msg[:100]}{'...' if len(msg) > 100 else ''}"

**可用功能：**
- 知识库检索
- 代码生成与编辑
- 文档撰写
- 多智能体协作

请稍后再试流式对话，或通过 Web UI 使用本地功能。"""

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time communication."""
        await websocket.accept()
        hub = getattr(websocket.app.state, 'hub', None)

        if not hub:
            await websocket.send_json({"type": "error", "message": "Hub not initialized"})
            await websocket.close()
            return

        await websocket.send_json({
            "type": "connected",
            "node_id": hub.node.info.id if hub.node else "unknown",
            "version": "2.0.0",
        })

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "chat")

                if msg_type == "chat":
                    message = data.get("message", "")
                    if not message:
                        await websocket.send_json({"type": "error", "message": "Empty message"})
                        continue

                    result = await hub.chat(message)
                    await websocket.send_json({
                        "type": "chat_response",
                        **result,
                    })

                elif msg_type == "status":
                    status = hub.status() if hasattr(hub, 'status') else {}
                    await websocket.send_json({"type": "status", **status})

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

                elif msg_type == "generate_report":
                    template = data.get("template_type", "环评报告")
                    report_data = data.get("data", {})
                    requirements = data.get("requirements", {})
                    result = await hub.generate_report(template, report_data, requirements)
                    await websocket.send_json({"type": "report_response", **result})

                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

    # ── OpenAI-compatible relay for external tools (opencode, Claude Code, etc.) ──

    @app.post("/v1/chat/completions")
    async def openai_chat_completions(request: Request):
        """OpenAI-compatible endpoint. Routes through LivingTree's auto-election."""
        hub = getattr(request.app.state, 'hub', None)
        if not hub:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Hub not initialized")

        try:
            body = await request.json()
        except Exception:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid JSON")

        messages = body.get("messages", [])
        if not messages:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="messages required")

        last_msg = messages[-1].get("content", "") if messages else ""
        stream = body.get("stream", False)

        if stream:
            from fastapi.responses import StreamingResponse
            import json as _json

            async def generate():
                try:
                    async for token in hub.world.consciousness.stream_of_thought(last_msg):
                        chunk = _json.dumps({
                            "choices": [{"delta": {"content": token}, "index": 0}],
                            "object": "chat.completion.chunk",
                        })
                        yield f"data: {chunk}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    error_chunk = _json.dumps({"error": str(e)})
                    yield f"data: {error_chunk}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        result = await hub.chat(last_msg)
        reply = str(result.get("intent", "") or result.get("reflections", [""])[0] or "")
        return {
            "id": f"livingtree-{result.get('session_id', '')}",
            "object": "chat.completion",
            "created": int(__import__('time').time()),
            "model": "livingtree-dual",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": len(last_msg),
                "completion_tokens": len(reply),
                "total_tokens": len(last_msg) + len(reply),
            },
        }

    @app.get("/v1/models")
    async def openai_list_models(request: Request):
        return {
            "object": "list",
            "data": [
                {"id": "livingtree-dual", "object": "model"},
                {"id": "livingtree-flash", "object": "model"},
                {"id": "longcat-flash-lite", "object": "model"},
                {"id": "longcat-flash-chat", "object": "model"},
            ],
        }

    # ═══ Scinet Service ═══

    @app.get("/api/scinet/status")
    async def scinet_status(request: Request):
        from ..network.scinet_service import get_scinet
        s = get_scinet().get_status()
        return {
            "running": s.running,
            "port": s.port,
            "pac_url": s.pac_url,
            "uptime_seconds": s.uptime_seconds,
            "total_requests": s.total_requests,
            "success_requests": s.success_requests,
            "failed_requests": s.failed_requests,
            "bandwidth_mb": round(s.bandwidth_bytes / 1024 / 1024, 2),
        }

    @app.post("/api/scinet/start")
    async def scinet_start(request: Request):
        from ..network.scinet_service import get_scinet
        s = await get_scinet().start()
        return {"status": "started", "port": s.port, "pac_url": s.pac_url}

    @app.post("/api/scinet/stop")
    async def scinet_stop(request: Request):
        from ..network.scinet_service import get_scinet
        s = await get_scinet().stop()
        return {"status": "stopped", "uptime_seconds": s.uptime_seconds, "total_requests": s.total_requests}

    @app.get("/api/scinet/pac")
    async def scinet_pac(request: Request):
        from ..network.scinet_service import get_scinet
        return Response(
            content=get_scinet().generate_pac(),
            media_type="application/x-ns-proxy-autoconfig",
        )

    @app.get("/api/scinet/test")
    async def scinet_test(request: Request):
        from ..network.scinet_service import get_scinet
        import aiohttp, time
        results = {}
        for url in ["https://github.com", "https://huggingface.co", "https://stackoverflow.com"]:
            try:
                async with aiohttp.ClientSession() as session:
                    start = time.time()
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        results[url] = f"OK ({resp.status}, {(time.time()-start)*1000:.0f}ms)"
            except Exception as e:
                results[url] = f"FAIL ({e})"
        return results

    # ── Register doc routes (OnlyOffice integration) ──
    from .doc_routes import setup_doc_routes
    setup_doc_routes(app)
