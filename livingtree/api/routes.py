"""API routes for the LivingTree server."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
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

    @app.get("/api/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        """Health check endpoint."""
        hub = getattr(request.app.state, 'hub', None)
        components = {}
        if hub:
            status = hub.get_status()
            components = {
                "life_engine": "ok" if status.get("life_engine") else "missing",
                "cells": f"{status.get('cells', {}).get('registered', 0)} registered",
                "knowledge": "ok" if status.get("knowledge") else "missing",
                "network": status.get("network", {}).get("status", "unknown"),
                "orchestrator": f"{status.get('orchestrator', {}).get('total_agents', 0)} agents",
            }
        return HealthResponse(
            status="healthy",
            version="2.0.0",
            components=components,
        )

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
        return hub.get_status()

    @app.get("/api/tools")
    async def list_tools(request: Request) -> list[dict[str, Any]]:
        """List all registered tools."""
        hub = request.app.state.hub
        if not hub:
            raise HTTPException(status_code=503, detail="Hub not initialized")
        tools = hub.tool_market.discover_tools()
        return [t.model_dump() for t in tools]

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
                    status = hub.get_status()
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
