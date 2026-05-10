"""API routes for the LivingTree server."""

from __future__ import annotations

import asyncio
import os
import secrets
import time as _time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
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

    # ── Swarm: Direct P2P collaboration endpoints ──

    @app.get("/api/swarm/status")
    async def swarm_status(request: Request) -> dict:
        from ..network.swarm_coordinator import get_swarm
        return get_swarm().status()

    @app.post("/api/swarm/ping")
    async def swarm_ping(request: Request) -> Response:
        """Binary health probe."""
        from ..network.message_bus import decode_health_report, encode_health_report
        raw = await request.body()
        decoded = decode_health_report(raw)
        resp_bin = encode_health_report("ok", "ok", 1.0, [])
        return Response(content=resp_bin, media_type="application/octet-stream")

    @app.post("/api/swarm/cell/receive")
    async def swarm_receive_cell(request: Request) -> Response:
        from ..network.swarm_coordinator import get_swarm
        from ..network.message_bus import encode_task_response
        raw = await request.body()
        result = await get_swarm().receive_cell(raw)
        resp_bin = encode_task_response(
            "cell", "completed" if result.get("cell_name") else "failed",
            str(result.get("cell_name", result.get("error", ""))),
        )
        return Response(content=resp_bin, media_type="application/octet-stream")

    @app.post("/api/swarm/knowledge/receive")
    async def swarm_receive_knowledge(request: Request) -> Response:
        from ..network.swarm_coordinator import get_swarm
        from ..network.message_bus import encode_task_response
        raw = await request.body()
        result = await get_swarm().receive_knowledge(raw)
        resp_bin = encode_task_response("knowledge", "completed", str(result.get("received", 0)))
        return Response(content=resp_bin, media_type="application/octet-stream")

    @app.post("/api/swarm/task/execute")
    async def swarm_execute_task(request: Request) -> Response:
        """Execute a subtask from binary protobuf TaskRequest."""
        from ..network.message_bus import decode_task_distribute, encode_task_response
        hub = request.app.state.hub
        raw = await request.body()
        decoded = decode_task_distribute(raw)
        if not decoded or not hub:
            resp_bin = encode_task_response("task", "failed", "no task or hub")
            return Response(content=resp_bin, media_type="application/octet-stream")
        try:
            subtask = decoded.get("subtask", decoded.get("goal", ""))
            result = await hub.chat(subtask)
            output = str(result.get("intent", result.get("reflections", ["done"])[0]))[:500]
            resp_bin = encode_task_response(decoded.get("task_id", "task"), "completed", output)
        except Exception as e:
            resp_bin = encode_task_response(decoded.get("task_id", "task"), "failed", str(e)[:200])
        return Response(content=resp_bin, media_type="application/octet-stream")

    @app.post("/api/swarm/task/distribute")
    async def swarm_distribute_task(request: Request) -> dict:
        """Distribute a complex task. Accepts JSON for human-facing API."""
        from ..network.swarm_coordinator import get_swarm
        body = await request.json()
        goal = body.get("goal", "")
        peers = body.get("peers", [])
        return await get_swarm().distribute_task(goal, peers)

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

        # Compress tool outputs in messages to save tokens (9Router RTK-inspired)
        try:
            from livingtree.core.token_compressor import compress
            total_saved = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 500:
                    result = compress(content)
                    if result["saved_pct"] > 0:
                        msg["content"] = result["compressed"]
                        total_saved += result["saved_pct"]
            if total_saved > 0:
                logger.debug(f"Token compressor: saved ~{total_saved / len(messages):.0f}% avg across {len(messages)} msgs")
        except Exception:
            pass

        # Inject memory context (non-blocking fire-and-forget)
        try:
            from livingtree.core.session_memory import agent_memory
            context = await agent_memory.get_context_injection(last_msg)
            if context:
                last_msg = f"{context}\n\n---\n用户消息:\n{last_msg}"
        except Exception:
            pass

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

    # ── IM WebSocket: Instant messaging, voice/video calls, virtual meetings ──

    @app.websocket("/ws/im")
    async def im_websocket(websocket: WebSocket):
        """IM WebSocket — handles DM, group chat, typing, presence, calls, file transfer."""
        await websocket.accept()

        from ..network.im_core import get_im, IMMessage, MessageType, OnlineStatus
        im = get_im()

        params = dict(websocket.query_params or {})
        user_id = params.get("user_id", params.get("uid", ""))
        user_name = params.get("name", user_id[:8] if user_id else "anonymous")

        if not user_id:
            await websocket.send_json({"type": "error", "message": "user_id required"})
            await websocket.close()
            return

        im.connect(user_id, websocket)
        await websocket.send_json({
            "type": "connected", "user_id": user_id,
            "online_count": len(im._connections),
        })

        try:
            while True:
                data = await websocket.receive_json()
                msg_type_str = data.get("type", "")

                if msg_type_str == "dm":
                    msg = IMMessage(
                        msg_id=f"dm_{int(_time.time()*1000)}_{secrets.token_hex(3)}",
                        msg_type=MessageType.DM,
                        sender_id=user_id, sender_name=data.get("sender_name", user_name),
                        receiver_id=data.get("to", data.get("receiver_id", "")),
                        content=data.get("content", data.get("message", "")),
                    )
                    await im.send_message(msg)

                elif msg_type_str == "group_msg":
                    msg = IMMessage(
                        msg_id=f"grp_{int(_time.time()*1000)}_{secrets.token_hex(3)}",
                        msg_type=MessageType.GROUP,
                        sender_id=user_id, sender_name=user_name,
                        receiver_id=data.get("group_id", ""),
                        content=data.get("content", ""),
                    )
                    await im.send_message(msg)

                elif msg_type_str == "typing":
                    msg = IMMessage(
                        msg_id=f"typ_{int(_time.time()*1000)}",
                        msg_type=MessageType.TYPING,
                        sender_id=user_id, receiver_id=data.get("to", ""),
                    )
                    await im.send_message(msg)

                elif msg_type_str == "presence":
                    st = OnlineStatus(data.get("status", "online"))
                    im.set_presence(user_id, st)

                elif msg_type_str == "call_signal":
                    await websocket.send_json({
                        "type": "call_signal_relay",
                        "signal": data.get("signal", {}),
                        "from": user_id,
                    })

                elif msg_type_str == "get_history":
                    msgs = im.get_history(
                        user_id,
                        with_user=data.get("with", ""),
                        group_id=data.get("group_id", ""),
                        limit=data.get("limit", 50),
                    )
                    await websocket.send_json({"type": "history", "messages": msgs})

                elif msg_type_str == "get_contacts":
                    await websocket.send_json({
                        "type": "contacts",
                        "contacts": [c.to_dict() for c in im.get_contacts(user_id)],
                    })

                elif msg_type_str == "add_contact":
                    from ..network.im_core import Contact
                    im.add_contact(user_id, Contact(
                        user_id=data.get("contact_id", ""),
                        name=data.get("contact_name", ""),
                    ))
                    await websocket.send_json({"type": "contact_added", "ok": True})

                elif msg_type_str == "create_group":
                    g = im.create_group(
                        name=data.get("name", "New Group"),
                        owner_id=user_id,
                        members=data.get("members", []),
                    )
                    await websocket.send_json({"type": "group_created", "group": g.to_dict()})

                elif msg_type_str == "get_groups":
                    groups = [g.to_dict() for g in im.get_user_groups(user_id)]
                    await websocket.send_json({"type": "groups", "groups": groups})

                elif msg_type_str == "nearby":
                    nearby = im.get_nearby_users(exclude_user_id=user_id)
                    await websocket.send_json({"type": "nearby", "users": nearby})

                elif msg_type_str == "file_chunk":
                    im.receive_file_chunk(
                        file_id=data.get("file_id", ""),
                        chunk_index=data.get("chunk_index", 0),
                        data=data.get("data", "").encode() if isinstance(data.get("data"), str) else b"",
                    )

                elif msg_type_str == "file_meta":
                    im.start_file_receive(
                        file_id=data.get("file_id", ""),
                        total_chunks=data.get("total_chunks", 1),
                        filename=data.get("filename", "file"),
                        file_size=data.get("file_size", 0),
                    )

                elif msg_type_str == "create_meeting":
                    meeting = await im.create_meeting(
                        topic=data.get("topic", "会议"),
                        host_id=user_id,
                        ai_participants=data.get("ai_participants"),
                    )
                    if hasattr(im, '_hub'):
                        im._hub = getattr(websocket.app.state, 'hub', None)
                    await websocket.send_json({"type": "meeting_created", "meeting": meeting})

                elif msg_type_str == "ping":
                    await websocket.send_json({"type": "pong"})

        except WebSocketDisconnect:
            logger.info(f"IM: {user_id} disconnected")
        except Exception as e:
            logger.error(f"IM WS error: {e}")
        finally:
            im.disconnect(user_id)

    # ── WebRTC Signaling: Browser ↔ Server P2P remote ops ──

    @app.websocket("/ws/rtc-signal")
    async def rtc_signaling(websocket: WebSocket):
        """WebRTC signaling for remote ops. Browser creates offer → server answers."""
        await websocket.accept()

        from ..network.webrtc_remote import get_remote_hub, RemoteOpsSession
        hub = get_remote_hub()
        session_id = f"rtc_{int(_time.time() * 1000)}"
        pc = None

        try:
            data = await websocket.receive_json()
            if "sdp" not in data and "ice" not in data:
                await websocket.close()
                return

            if "sdp" in data:
                sdp_dict = data["sdp"]
                try:
                    import json as _j
                    sdp_dict = _j.loads(sdp_dict) if isinstance(sdp_dict, str) else sdp_dict
                except Exception:
                    pass
                await websocket.send_json({"sdp": {
                    "type": "answer",
                    "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE data\r\nm=application 9 DTLS/SCTP 5000\r\nc=IN IP4 0.0.0.0\r\na=ice-pwd:livingtree\r\na=ice-ufrag:ltree\r\na=fingerprint:sha-256 " + "00"*32 + "\r\na=setup:active\r\na=mid:data\r\na=sctp-port:5000\r\n"
                }})
            elif "ice" in data:
                await websocket.send_json({"ice": {"candidate": "candidate:1 1 UDP 2122252543 127.0.0.1 9999 typ host", "sdpMid": "data"}})

            raw = await websocket.receive_text()
            try:
                msg = _json.loads(raw)
            except Exception:
                msg = {"op": "ping"}

            # Create session and handle ops
            class FakeChannel:
                def __init__(self, ws): self._ws = ws
                def send(self, data): asyncio.create_task(self._ws.send_text(data))
            channel = FakeChannel(websocket)
            session = hub.create_session(session_id, channel)

            await session.handle_message(_json.dumps(msg))

            while True:
                raw = await websocket.receive_text()
                try:
                    msg_data = _json.loads(raw)
                    await session.handle_message(_json.dumps(msg_data))
                except Exception:
                    await session.handle_message(raw)

        except WebSocketDisconnect:
            logger.debug(f"RTC signal disconnected: {session_id}")
        except Exception as e:
            logger.debug(f"RTC signal error: {e}")
        finally:
            hub.close_session(session_id)

    # ── Reach Gateway: Cross-device AI sensory extension ──

    @app.websocket("/ws/reach")
    async def reach_websocket(websocket: WebSocket):
        """Reach Gateway WebSocket — cross-device AI sensory network.

        Devices connect here. AI pushes sensor requests (photo, QR, GPS, etc.),
        devices execute and respond. This is how the AI "reaches through" to
        mobile devices for capabilities it doesn't have.
        """
        await websocket.accept()

        from ..network.reach_gateway import get_reach_gateway, DeviceType
        reach = get_reach_gateway()

        hub = getattr(websocket.app.state, 'hub', None)
        if hub:
            reach.set_hub(hub)

        params = dict(websocket.query_params or {})
        device_type = params.get("device_type", "unknown")
        device_name = params.get("device_name", "")
        session_id = params.get("session_id", "")
        ua = websocket.headers.get("user-agent", "")

        device_id = None
        try:
            device = await reach.register_device(
                websocket, device_type, device_name, session_id, ua,
            )
            device_id = device.device_id

            await websocket.send_json({
                "type": "reach_connected",
                "device_id": device_id,
                "device_type": device.device_type.value,
                "capabilities": device.capabilities,
                "message": f"已连接。AI 可以在需要时向你发送任务。",
            })

            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    device.last_seen = _time.time()

                elif msg_type == "sensor_response":
                    await reach.receive_response(device_id, data)
                    await websocket.send_json({"type": "ack", "request_id": data.get("request_id", "")})

                elif msg_type == "capabilities":
                    device.capabilities = data.get("capabilities", device.capabilities)
                    await websocket.send_json({"type": "caps_updated"})

                elif msg_type == "task_card_result":
                    card_id = data.get("card_id", "")
                    card = reach._pending_cards.get(card_id)
                    if card:
                        card.status = "completed"
                        card.result = data.get("result", {})
                    await websocket.send_json({"type": "card_ack", "card_id": card_id})

                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown: {msg_type}"})

        except WebSocketDisconnect:
            logger.info(f"Reach: device {device_id or '?'} disconnected")
        except Exception as e:
            logger.error(f"Reach WS error: {e}")
        finally:
            if device_id:
                reach.unregister_device(device_id)

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

    # ── Register doc routes (LT-Office integration) ──
    from .doc_routes import setup_doc_routes
    setup_doc_routes(app)

    # ── Memory management routes ──

    @app.get("/api/memory/status")
    async def memory_status(request: Request) -> dict[str, Any]:
        """Get memory engine status."""
        try:
            from livingtree.core.session_memory import agent_memory, _cognee_available
            await agent_memory._ensure_init()
            entries = agent_memory._load_fallback()
            return {
                "cognee_available": _cognee_available,
                "fallback_entries": len(entries),
                "status": "ok",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @app.post("/api/memory/remember")
    async def memory_remember(request: Request) -> dict[str, Any]:
        """Store a memory entry."""
        try:
            body = await request.json()
            from livingtree.core.session_memory import agent_memory
            ok = await agent_memory.remember(
                body.get("content", ""),
                user_id=body.get("user_id", ""),
                project=body.get("project", ""),
                workspace_id=body.get("workspace_id", ""),
            )
            return {"ok": ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/memory/recall")
    async def memory_recall(request: Request) -> dict[str, Any]:
        """Recall relevant memories."""
        try:
            body = await request.json()
            from livingtree.core.session_memory import agent_memory
            results = await agent_memory.recall(
                body.get("query", ""),
                user_id=body.get("user_id", ""),
                project=body.get("project", ""),
                workspace_id=body.get("workspace_id", ""),
                limit=body.get("limit", 5),
            )
            return {"ok": True, "results": results}
        except Exception as e:
            return {"ok": False, "error": str(e), "results": []}

    @app.post("/api/memory/forget")
    async def memory_forget(request: Request) -> dict[str, Any]:
        """Forget memories."""
        try:
            body = await request.json()
            from livingtree.core.session_memory import agent_memory
            ok = await agent_memory.forget(
                user_id=body.get("user_id", ""),
                project=body.get("project", ""),
            )
            return {"ok": ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Skill management routes ──

    @app.get("/api/skills")
    async def list_all_skills(
        request: Request,
        workspace_id: str = Query(default=""),
        tag: str = Query(default=""),
        search: str = Query(default=""),
    ) -> list[dict]:
        """List skills for current user or workspace."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import list_skills
        return list_skills(
            user_id=user_id if not workspace_id else "",
            workspace_id=workspace_id,
            tag=tag,
            search=search,
        )

    @app.get("/api/skills/{name}")
    async def get_single_skill(
        name: str,
        request: Request,
        workspace_id: str = Query(default=""),
    ) -> dict:
        """Get a single skill by name."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import get_skill
        skill = get_skill(name, user_id=user_id if not workspace_id else "", workspace_id=workspace_id)
        if not skill:
            raise HTTPException(status_code=404, detail="技能不存在")
        return skill

    @app.post("/api/skills")
    async def create_or_update_skill(request: Request) -> dict:
        """Create or update a skill."""
        try:
            body = await request.json()
            user_id = _get_user_id_from_request(request)
            from livingtree.core.skills import create_or_update_skill
            return create_or_update_skill(
                name=body.get("name", ""),
                body=body.get("body", ""),
                user_id=user_id if not body.get("workspace_id") else "",
                workspace_id=body.get("workspace_id", ""),
                description=body.get("description", ""),
                tags=body.get("tags", []),
                source_project=body.get("source_project", ""),
                source_user=body.get("source_user", user_id),
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/skills/{name}")
    async def delete_skill_by_name(
        name: str,
        request: Request,
        workspace_id: str = Query(default=""),
    ) -> dict:
        """Delete a skill."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import delete_skill
        ok = delete_skill(name, user_id=user_id if not workspace_id else "", workspace_id=workspace_id)
        return {"ok": ok}

    @app.post("/api/skills/{name}/touch")
    async def touch_skill_usage(
        name: str,
        request: Request,
        workspace_id: str = Query(default=""),
    ) -> dict:
        """Increment skill usage count."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import touch_skill
        ok = touch_skill(name, user_id=user_id if not workspace_id else "", workspace_id=workspace_id)
        return {"ok": ok}

    @app.get("/api/skills/suggestions")
    async def skill_suggestions(
        request: Request,
        workspace_id: str = Query(default=""),
    ) -> list[dict]:
        """Get skill suggestions from recorded sessions."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import suggest_skills_from_sessions
        return suggest_skills_from_sessions(
            user_id=user_id if not workspace_id else "",
            workspace_id=workspace_id,
        )

    @app.get("/api/skills/dedup")
    async def skill_deduplication(
        request: Request,
        workspace_id: str = Query(default=""),
    ) -> dict:
        """Find duplicate skills."""
        user_id = _get_user_id_from_request(request)
        from livingtree.core.skills import deduplicate_skills
        return deduplicate_skills(
            user_id=user_id if not workspace_id else "",
            workspace_id=workspace_id,
        )


    @app.get("/api/docs/templates")
    async def list_doc_templates() -> list[dict]:
        """List available Kami document templates."""
        from livingtree.core.doc_renderer import list_templates
        return list_templates()

    @app.post("/api/docs/render")
    async def render_document_endpoint(request: Request) -> dict:
        """Render Markdown content to Kami-styled HTML/PDF."""
        try:
            body = await request.json()
            from livingtree.core.doc_renderer import render_document
            return render_document(
                content=body.get("content", ""),
                template=body.get("template", "long_doc"),
                title=body.get("title", ""),
                output_path=body.get("output_path", ""),
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}


async def _handle_relay_config(msg: str, ml: str):
    """Handle relay server configuration commands via admin chat."""
    import re as _regex
    import aiohttp
    actions, reply = [], ""

    relay_url = os.environ.get("LT_RELAY_URL", "http://127.0.0.1:8899")
    admin_pwd = os.environ.get("LT_RELAY_ADMIN_PWD", "admin123")

    async def _call_relay(method: str, path: str, data: dict | None = None) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(f"{relay_url}{path}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        return await resp.json() if resp.content_type == "application/json" else {"status": resp.status}
                elif method == "POST":
                    async with session.post(f"{relay_url}{path}", json=data or {}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        return await resp.json() if resp.content_type == "application/json" else {"status": resp.status}
        except Exception as e:
            return {"error": str(e)}

    if "添加账户" in msg or "创建用户" in msg or "注册账户" in msg or "add account" in ml:
        username = ""
        password = ""
        um = _regex.search(r'(?:用户|账户|账号|用户名)[:：\s]*(\S+)', msg)
        pm = _regex.search(r'(?:密码|口令)[:：\s]*(\S+)', msg)
        if um:
            username = um.group(1)
            if pm:
                password = pm.group(1)
            else:
                import secrets
                password = secrets.token_hex(6)
                actions.append(f"已生成随机密码: {password}")

            # Login as admin first
            r = await _call_relay("POST", "/admin/login", {"username": "admin", "password": admin_pwd})
            if not r.get("error"):
                r2 = await _call_relay("POST", "/admin/accounts/add", {"username": username, "password": password, "display_name": username})
                if r2.get("status") == 200:
                    actions.append(f"✅ 中继账户已创建: {username}")
                    reply = f"中继账户 {username} 已创建。密码: {password}"
                else:
                    reply = f"创建失败: {r2}"
                    actions.append(str(r2))
            else:
                reply = "中继服务器连接失败。确认中继已启动: python relay_server.py"
        else:
            reply = "请提供用户名，如: 创建用户 alice 密码 123456"

    elif "查看账户" in msg or "账户列表" in msg or "list" in ml:
        r = await _call_relay("GET", "/status")
        reply = f"中继状态: {r.get('peers','?')} 个节点在线"
        actions.append(f"中继地址: {relay_url}")

    elif "添加订阅" in msg or "添加模型" in msg or "subscription" in ml:
        base_url = ""
        api_key = ""
        model = ""
        provider = _regex.search(r'(?:提供方|provider|名称)[:：\s]*(\S+)', msg)
        bm = _regex.search(r'(?:地址|url|base)[:：\s]*(https?://[^\s]+)', msg)
        km = _regex.search(r'(?:key|密钥|api)[:：\s]*(sk-\S+)', msg)
        mm = _regex.search(r'(?:模型|model)[:：\s]*(\S+)', msg)
        if bm:
            base_url = bm.group(1)
            api_key = km.group(1) if km else ""
            model = mm.group(1) if mm else "default"
            name = provider.group(1) if provider else base_url.split("//")[1].split(".")[0][:10]
            r = await _call_relay("POST", "/admin/subscriptions/add", {
                "name": name, "base_url": base_url, "api_key": api_key,
                "model": model, "user": "admin",
            })
            actions.append(f"✅ 订阅已添加: {name} ({model})")
            reply = f"中继订阅 {name} 已配置: {base_url}"
        else:
            reply = "请提供订阅信息，如: 添加订阅 名称 deepseek 地址 https://api.deepseek.com/v1 key sk-xxx 模型 deepseek-chat"

    elif "查看节点" in msg or "节点列表" in msg or "在线" in msg or "peers" in ml:
        r = await _call_relay("GET", "/peers/discover")
        peers = r if isinstance(r, list) else r.get("peers", []) if isinstance(r, dict) else []
        count = len(peers) if isinstance(peers, list) else 0
        reply = f"中继在线节点: {count} 个"
        for p in (peers if isinstance(peers, list) else [])[:5]:
            actions.append(f"📡 {p.get('peer_id','?')[:12]} — {p.get('metadata',{}).get('platform','?')}")

    elif "状态" in msg or "status" in ml:
        r = await _call_relay("GET", "/health")
        reply = f"中继运行中: {r.get('status','?')} · {r.get('peers',0)} 节点 · {r.get('uptime',0):.0f}s"
        r2 = await _call_relay("GET", "/status")
        if isinstance(r2, dict):
            actions.append(f"请求: {r2.get('request_count',0)} · 用户: {r2.get('username','?')}")

    elif "密码" in msg and "relay" in ml:
        reply = f"中继管理员默认密码: {admin_pwd}。修改: POST /admin/password"

    else:
        r = await _call_relay("GET", "/health")
        if r.get("status") == "ok":
            reply = f"中继服务器运行正常 ({relay_url})。可用命令: 创建用户/查看节点/添加订阅"
        else:
            reply = f"中继服务器未响应 ({relay_url})。启动: python relay_server.py --port 8899"

    return actions, reply


def _get_user_id_from_request(request: Request) -> str:
    """Extract user_id from JWT token in request headers."""
    try:
        from livingtree.api.auth import verify_token
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            payload = verify_token(token)
            if payload:
                return payload.get("user_id", "")
    except Exception:
        pass
    return ""

    # ── Document parsing routes ──

    @app.post("/api/docs/parse")
    async def parse_uploaded_doc(
        request: Request,
        file: UploadFile = File(...),
        project: str = Form(default=""),
        workspace_id: str = Form(default=""),
    ) -> dict:
        """Upload a document and parse it with MinerU. Results fed into agent memory."""
        from pathlib import Path
        import time as _upload_time
        user_id = _get_user_id_from_request(request)
        uploads_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = uploads_dir / f"{int(_upload_time.time())}_{file.filename}"
        try:
            content = await file.read()
            tmp_path.write_bytes(content)
            from livingtree.core.session_memory import ingest_document
            result = await ingest_document(
                str(tmp_path), user_id=user_id, project=project, workspace_id=workspace_id)
            if result.get("ok"):
                tmp_path.unlink(missing_ok=True)
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/docs/parse-file")
    async def parse_local_doc(request: Request) -> dict:
        """Parse a local file path with MinerU."""
        try:
            body = await request.json()
            user_id = _get_user_id_from_request(request)
            from livingtree.core.session_memory import ingest_document
            return await ingest_document(
                body.get("path", ""),
                user_id=user_id,
                project=body.get("project", ""),
                workspace_id=body.get("workspace_id", ""),
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══ Admin API ═══

    @app.get("/api/admin")
    async def admin_page():
        from pathlib import Path
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        from fastapi.responses import HTMLResponse
        return HTMLResponse((template_dir / "admin.html").read_text(encoding="utf-8"))

    @app.get("/api/admin/status")
    async def admin_status(request: Request):
        from ..core.admin_manager import get_admin
        admin = get_admin()
        hub = getattr(request.app.state, "hub", None)
        config_info = {}
        if hub and hasattr(hub, "config"):
            cfg = hub.config
            config_info = {
                "flash_model": getattr(getattr(cfg, "model", None), "flash_model", ""),
                "pro_model": getattr(getattr(cfg, "model", None), "pro_model", ""),
                "api_port": getattr(getattr(cfg, "api", None), "port", 8100) if hasattr(cfg, "api") else 8100,
            }
        return {**admin.status(), "config": config_info}

    class AdminPassword(BaseModel):
        password: str

    @app.post("/api/admin/init")
    async def admin_init(req: AdminPassword):
        from ..core.admin_manager import get_admin
        ok = get_admin().initialize(req.password)
        return {"ok": ok, "error": "" if ok else "已初始化或密码过短(至少6位)"}

    @app.post("/api/admin/login")
    async def admin_login(req: AdminPassword):
        from ..core.admin_manager import get_admin
        a = get_admin()
        if not a.is_initialized:
            return {"token": "", "error": "未初始化"}
        if a.verify_password(req.password):
            return {"token": a.create_admin_token()}
        return {"token": "", "error": "密码错误"}

    class ChangePassword(BaseModel):
        old_password: str
        new_password: str

    @app.post("/api/admin/change-password")
    async def admin_change_password(req: ChangePassword, request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        return {"ok": a.change_password(req.old_password, req.new_password)}

    class CredentialReq(BaseModel):
        key: str
        value: str = ""

    @app.get("/api/admin/credentials")
    async def admin_list_credentials(request: Request):
        from fastapi.responses import HTMLResponse
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            return HTMLResponse('<div style="color:var(--err)">未授权</div>')
        keys = a.list_credential_keys()
        rows = ""
        for k in keys[:30]:
            rows += (
                f'<div class="cred-row"><span>{k}</span>'
                f'<span class="masked">●●●●●●●●</span>'
                f'<button class="danger" onclick="deleteCredential(\'{k}\')" style="font-size:10px;padding:2px 8px">删除</button></div>'
            )
        return HTMLResponse(rows or '<div style="color:var(--dim);font-size:12px">暂无存储的密钥</div>')

    @app.post("/api/admin/credentials")
    async def admin_add_credential(req: CredentialReq, request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        return {"ok": a.store_credential(req.key, req.value)}

    @app.delete("/api/admin/credentials/{key}")
    async def admin_delete_credential(key: str, request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        return {"ok": a.delete_credential(key)}

    class ConfigChatReq(BaseModel):
        message: str

    @app.post("/api/admin/config/chat")
    async def admin_config_chat(req: ConfigChatReq, request: Request):
        import re as _regex
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)

        hub = request.app.state.hub
        if not hub:
            return {"reply": "系统未就绪", "actions": []}

        msg = req.message
        actions = []
        reply = ""
        world = hub.world
        consc = getattr(world, "consciousness", None) if world else None
        ml = msg.lower().replace(" ", "")

        if "apikey" in ml or "api_key" in ml or "密钥" in msg or "sk-" in msg:
            km = _regex.search(r'(?:api[_ ]?key|密钥|key)\s*[:：=]\s*["\']?(\S+)', msg, _regex.IGNORECASE)
            if not km:
                km = _regex.search(r'(sk-[a-zA-Z0-9]+)', msg)
            if km:
                key_val = km.group(1)
                pv = "deepseek"
                for p in ["deepseek", "openai", "longcat", "qwen", "zhipu", "siliconflow"]:
                    if p in ml:
                        pv = p
                        break
                a.store_credential(f"{pv}_api_key", key_val)
                actions.append(f"已加密保存 {pv}_api_key")
                reply = f"✅ API密钥已加密保存。提供方: {pv}"
            else:
                reply = "请提供完整的API密钥(如 api_key=sk-xxx)"

        elif "扫描" in msg or "scan" in ml or "发现" in msg:
            from ..core.universal_scanner import get_universal_scanner
            scanner = get_universal_scanner()
            scanner._hub = hub
            found = await scanner.discover_from_description(msg)
            if found and found.is_alive:
                reply = f"发现: {found.name} ({found.protocol})"
                if found.models:
                    reply += f" — {len(found.models)}个模型"
            else:
                reply = "未发现。请提供具体地址"

        elif "模型" in msg or "model" in ml or "默认" in msg:
            if consc:
                reply = f"Flash: {getattr(consc, 'flash_model', '?')}\nPro: {getattr(consc, 'pro_model', '?')}"

        elif "预算" in msg or "budget" in ml or "token" in ml or "费用" in msg:
            ca = getattr(world, "cost_aware", None)
            if ca:
                st = ca.status()
                reply = f"已用 {st.used_today:,} tokens · ¥{st.cost_yuan:.4f}"
            else:
                reply = "费用模块未就绪"

        elif "宪法" in msg or "spec" in ml or "价值观" in msg or "行为准则" in msg:
            from ..core.model_spec import get_spec
            spec = get_spec()
            if "修改" in msg or "更新" in msg or "update" in ml:
                content = msg.split("修改", 1)[-1].strip() if "修改" in msg else msg
                if len(content) > 10:
                    spec.update_spec(content if content.startswith("#") else f"# Updated Spec\n\n{content}")
                    actions.append(f"宪法已更新至 v{spec._version}")
                    reply = f"✅ Model Spec 已更新 (v{spec._version})"
                else:
                    reply = "请提供具体的宪法内容"
            else:
                info = spec.get_spec_for_admin()
                reply = f"Model Spec v{info['version']} — {info['values_count']} 个价值观 · {info['size_chars']} 字符"
                actions.append(f"Hash: {info['hash']}")

        elif "中继" in msg or "relay" in ml or "节点" in msg:
            actions, reply = await _handle_relay_config(msg, ml)
            if not reply:
                reply = "中继配置完成"

        else:
            if consc:
                try:
                    rt = await consc.chain_of_thought(
                        f"系统配置助手。管理员: {msg}\n返回JSON: {{'reply':'回复','actions':[]}}", steps=1,
                    )
                    txt = rt if isinstance(rt, str) else str(rt)
                    try:
                        import json as _j
                        d = _j.loads(txt[txt.find("{"):txt.rfind("}") + 1])
                        reply = d.get("reply", "已处理")
                        actions = d.get("actions", [])
                    except Exception:
                        reply = txt[:400]
                except Exception:
                    reply = "配置助手暂不可用"

        return {"reply": reply or "已处理", "actions": actions}

    class SvcDiscover(BaseModel):
        description: str

    @app.post("/api/admin/services/discover")
    async def admin_svc_discover(req: SvcDiscover, request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        from ..core.universal_scanner import get_universal_scanner
        sc = get_universal_scanner()
        sc._hub = request.app.state.hub
        svc = await sc.discover_from_description(req.description)
        return {"service": svc.to_dict() if svc else None}

    class SvcRegister(BaseModel):
        url: str
        api_key: str = ""

    @app.post("/api/admin/services/register")
    async def admin_svc_register(req: SvcRegister, request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        from ..core.universal_scanner import get_universal_scanner
        sc = get_universal_scanner()
        sc._hub = request.app.state.hub
        svc = sc._discovered.get(req.url)
        if not svc:
            return {"ok": False, "error": "服务未发现"}
        return await sc.auto_register_service(svc, api_key=req.api_key)

    @app.get("/api/admin/services/status")
    async def admin_svc_status(request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        from ..core.universal_scanner import get_universal_scanner
        return get_universal_scanner().status()

    @app.get("/api/admin/services/scan")
    async def admin_svc_scan(request: Request):
        from ..core.admin_manager import get_admin
        a = get_admin()
        t = (request.headers.get("Authorization", "")).replace("Bearer ", "")
        if not a.verify_admin_token(t):
            raise HTTPException(status_code=401)
        from ..core.universal_scanner import get_universal_scanner
        sc = get_universal_scanner()
        sc._hub = request.app.state.hub
        discovered = await sc.scan_network(max_ports=50)
        return {"discovered": len(discovered), "services": [s.to_dict() for s in discovered]}

    # ═══ HITL Bridge ═══

    @app.post("/api/hitl/approve")
    async def hitl_approve(request: Request):
        from ..core.agent_qa import get_hitl_bridge
        from ..core.dpo_prefs import get_dpo_hooks
        body = await request.json()
        ok = get_hitl_bridge().approve(body.get("id", ""), body.get("response", "approved"))
        get_dpo_hooks().on_hitl_decision(body.get("id", ""), True, body.get("context", ""))
        return {"ok": ok}

    @app.post("/api/hitl/reject")
    async def hitl_reject(request: Request):
        from ..core.agent_qa import get_hitl_bridge
        from ..core.dpo_prefs import get_dpo_hooks
        body = await request.json()
        ok = get_hitl_bridge().reject(body.get("id", ""), body.get("reason", "rejected"))
        get_dpo_hooks().on_hitl_decision(body.get("id", ""), False, body.get("context", ""))
        return {"ok": ok}

    # ═══ Collective Intelligence API ═══

    @app.post("/api/collective/publish")
    async def collective_publish(request: Request):
        from ..core.collective_intel import get_blueprints
        body = await request.json()
        hub = request.app.state.hub
        bid = get_blueprints().publish(
            name=body.get("name", "blueprint"), hub=hub,
            description=body.get("description", ""),
            persona=body.get("persona", ""),
        )
        return {"ok": True, "id": bid}

    @app.post("/api/collective/import/{blueprint_id}")
    async def collective_import(blueprint_id: str, request: Request):
        from ..core.collective_intel import get_blueprints
        hub = request.app.state.hub
        ok = get_blueprints().import_blueprint(blueprint_id, hub)
        return {"ok": ok}

    # ═══ Device Pairing API ═══

    @app.get("/api/pairing/audio")
    async def pairing_audio():
        from ..network.universal_pairing import get_pairing
        return get_pairing().generate_audio_signal()

    @app.post("/api/pairing/lan/{device_id}")
    async def pairing_lan(device_id: str):
        from ..network.universal_pairing import get_pairing, PairMethod
        pairing = get_pairing()
        pairing.pair_device(device_id, device_id[:16], "unknown", PairMethod.LAN_AUTO)
        return {"ok": True}

    @app.post("/api/pairing/code")
    async def pairing_verify_code(request: Request):
        body = await request.json()
        code = body.get("code", "")
        device_name = body.get("device_name", "mobile")
        from ..network.universal_pairing import get_pairing, PairMethod
        pairing = get_pairing()
        sid = pairing.verify_code(code)
        if sid:
            pairing.pair_device(f"code_{code}", device_name, "mobile", PairMethod.CODE_8_DIGIT, session_id=sid)
            return {"ok": True, "session_id": sid}
        return {"ok": False, "error": "invalid code"}

    # ═══ Push Notification ═══

    @app.get("/api/push/vapid-key")
    async def push_vapid_key():
        """Return the VAPID public key for push subscription."""
        import base64, os, json as _j
        key_file = Path(".livingtree/vapid.json")
        if key_file.exists():
            keys = _j.loads(key_file.read_text())
        else:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization
            key = ec.generate_private_key(ec.SECP256R1())
            private_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            public_bytes = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            private_b64 = base64.urlsafe_b64encode(private_bytes).decode().rstrip('=')
            public_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip('=')
            keys = {"private": private_b64, "public": public_b64}
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_text(_j.dumps(keys))
        return {"public_key": keys["public"]}

    @app.post("/api/push/subscribe")
    async def push_subscribe(request: Request):
        """Store a push subscription."""
        body = await request.json()
        sub_file = Path(".livingtree/push_subs.jsonl")
        sub_file.parent.mkdir(parents=True, exist_ok=True)
        with open(sub_file, "a", encoding="utf-8") as f:
            f.write(_json.dumps({"endpoint": body.get("endpoint",""), "keys": body.get("keys",{}), "user": body.get("user_id",""), "ts": _time.time()}) + "\n")
        return {"ok": True}

    @app.post("/api/push/send")
    async def push_send(request: Request):
        """Send a push notification to all subscribers."""
        body = await request.json()
        title = body.get("title", "小树")
        msg = body.get("body", body.get("message", ""))
        url = body.get("url", "/tree/living")

        sub_file = Path(".livingtree/push_subs.jsonl")
        if not sub_file.exists():
            return {"ok": False, "error": "no subscribers", "sent": 0}

        import aiohttp
        key_file = Path(".livingtree/vapid.json")
        import json as _j, base64
        keys = _j.loads(key_file.read_text()) if key_file.exists() else {"private": ""}

        sent = 0
        async with aiohttp.ClientSession() as session:
            for line in open(sub_file, encoding="utf-8"):
                try:
                    sub = _json.loads(line)
                    payload = _json.dumps({"title": title, "body": msg, "url": url, "icon": "/assets/icon.svg"})
                    headers = {"Content-Type": "application/json", "TTL": "86400"}
                    async with session.post(sub["endpoint"], data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status in (200, 201):
                            sent += 1
                except Exception:
                    pass
        return {"ok": True, "sent": sent}
