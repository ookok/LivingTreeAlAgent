"""
LivingTree FastAPI 服务应用
============================

将 LifeEngine + APIGateway + FrontendChannel + 所有子系统
统一连线到一个 FastAPI 应用中，提供完整的 HTTP/WS API。

启动: python -m livingtree server
"""

import os
import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── 生命周期 ─────────────────────────────────────────────────

_engine = None
_gateway = None
_channel = None
_tool_registry = None
_skill_repo = None
_memory_store = None


def get_engine():
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _gateway, _channel, _tool_registry, _skill_repo, _memory_store

    print("[livingtree] Initializing core subsystems...")

    # 导入核心组件
    from livingtree.infrastructure.config import get_config

    config = get_config()
    print(f"[livingtree] Config v{config.version} loaded")

    # 工具注册表
    from livingtree.core.tools.registry import ToolRegistry, register_all_tools

    _tool_registry = ToolRegistry()
    register_all_tools()
    print(f"[livingtree] ToolRegistry: {ToolRegistry.count()} tools")

    # 技能仓库
    from livingtree.core.skills.matcher import SkillRepository, SkillLoader

    _skill_repo = SkillRepository()
    loader = SkillLoader(_skill_repo)
    loader.load_default_skills()
    print(f"[livingtree] SkillRepository: {_skill_repo.count()} skills")

    # 记忆存储
    from livingtree.core.memory.store import MemoryStore

    _memory_store = MemoryStore()
    print(f"[livingtree] MemoryStore: ready")

    # LifeEngine
    from livingtree.core.life_engine import LifeEngine

    _engine = LifeEngine(config)

    # 注入子系统
    _engine.inject_knowledge_store(_memory_store)
    _engine.inject_skill_matcher(_skill_repo._skills if hasattr(_skill_repo, '_skills') else {})

    # 注入 LLM Client（如果 Ollama 可用则自动注入）
    _auto_inject_llm_client(_engine)

    print(f"[livingtree] LifeEngine v{config.version} ready")
    print(f"[livingtree] Cells: {list(_engine.cells.keys())}")

    # API 网关
    from livingtree.adapters.api.gateway import APIGateway

    _gateway = APIGateway()
    _gateway.bind_engine(_engine)
    _gateway.bind_tools(_tool_registry)
    _gateway.bind_skills(_skill_repo)

    # 前端桥接
    from livingtree.frontend_bridge.channel import FrontendChannel

    _channel = FrontendChannel()
    _channel.bind_life_engine(_engine)
    _channel.register_default_handlers()

    # 指标
    from livingtree.core.observability.metrics import get_metrics
    get_metrics().record_request(success=True, duration_ms=0.0)

    print(f"[livingtree] Server ready on http://0.0.0.0:8100")
    print(f"[livingtree] API docs at http://localhost:8100/docs")

    yield

    print("[livingtree] Shutting down...")


def _auto_inject_llm_client(engine):
    try:
        from livingtree.core.model.client import ProductionLLMClient
        client = ProductionLLMClient()
        engine.inject_llm_client(client)
        if client.available:
            print(f"[livingtree] DeepSeek LLM client injected: {client.default_model}")
        else:
            print(f"[livingtree] DeepSeek API key not configured — using fallback")
    except Exception as e:
        print(f"[livingtree] LLM client init failed: {e}")


# ── FastAPI 应用 ────────────────────────────────────────────

app = FastAPI(
    title="LivingTree AI Agent",
    description="Digital Lifeform — TaskChain Pipeline API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic 模型 ────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(default="")

class ChatResponse(BaseModel):
    id: str
    type: str = "chat_response"
    content: str
    trace_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class HealthResponse(BaseModel):
    status: str
    version: str
    engine: Dict[str, Any] = Field(default_factory=dict)
    tools_count: int = 0
    skills_count: int = 0
    uptime_seconds: float = 0.0

class ToolsResponse(BaseModel):
    tools: List[Dict[str, Any]]
    count: int

class SkillsResponse(BaseModel):
    skills: List[Dict[str, Any]]
    count: int

_start_time = time.time()


# ── REST API 路由 ───────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "LivingTree AI Agent",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    if not _gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    result = await _gateway.handle_chat_async(req.message, req.session_id)
    if "error" in result and result.get("type") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", ""))
    return result


@app.get("/api/health", response_model=HealthResponse)
async def api_health():
    if not _gateway:
        return HealthResponse(
            status="initializing", version="1.0.0",
            uptime_seconds=time.time() - _start_time,
        )

    health = _gateway.handle_health()
    return HealthResponse(
        status=health.get("status", "unknown"),
        version="1.0.0",
        engine=health.get("engine", {}),
        tools_count=health.get("tools_count", 0),
        skills_count=health.get("skills_count", 0),
        uptime_seconds=time.time() - _start_time,
    )


@app.get("/api/tools")
async def api_tools():
    if not _gateway:
        raise HTTPException(status_code=503)
    return _gateway.handle_tools_list()


@app.get("/api/skills")
async def api_skills():
    if not _gateway:
        raise HTTPException(status_code=503)
    return _gateway.handle_skills_list()


@app.post("/api/tools/{tool_name}/call")
async def api_tool_call(tool_name: str, params: Optional[Dict[str, Any]] = None):
    if not _gateway:
        raise HTTPException(status_code=503)
    result = _gateway.handle_tool_call(tool_name, params or {})
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", ""))
    return result


@app.get("/api/metrics")
async def api_metrics():
    from livingtree.core.observability.metrics import get_metrics
    return get_metrics().snapshot()


# ── WebSocket ───────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(f"[livingtree] WebSocket connected")

    try:
        while True:
            raw = await ws.receive_text()

            if _channel:
                result_json = await _channel.handle_message(raw)
            else:
                result_json = json.dumps({"error": "Channel not initialized"})

            await ws.send_text(result_json)
    except WebSocketDisconnect:
        print(f"[livingtree] WebSocket disconnected")
    except Exception as e:
        print(f"[livingtree] WebSocket error: {e}")
        try:
            await ws.close()
        except Exception:
            pass


# ── 静态文件（Vue 前端） ────────────────────────────────────

def _find_frontend_dir() -> Optional[str]:
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "client", "src", "frontend"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "client", "src", "frontend", "dist"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


_frontend_dir = _find_frontend_dir()
if _frontend_dir:
    app.mount("/app", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


# ── 启动入口 ────────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8100, reload: bool = False):
    import uvicorn
    print(f"[livingtree] Starting server on {host}:{port}")
    uvicorn.run(
        "livingtree.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
