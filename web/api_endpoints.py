"""
Web API 端点 - 扩展版本
======================

集成所有核心模块的 Web API 端点

模块:
- Chat API
- Memory API (Cognee)
- Skills API
- RAG API (Disco-RAG)
- vLLM API (Nano-vLLM)
"""

import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

try:
    from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# ==================== 数据模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = ""
    stream: bool = False
    model: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str = ""
    session_id: str = ""
    timestamp: float = 0


class MemorySearchRequest(BaseModel):
    """记忆搜索请求"""
    query: str
    limit: int = 10
    memory_type: Optional[str] = None


class MemoryStoreRequest(BaseModel):
    """记忆存储请求"""
    content: str
    memory_type: str = "permanent"
    metadata: Dict[str, Any] = {}


class SkillExecuteRequest(BaseModel):
    """技能执行请求"""
    skill_id: str
    params: Dict[str, Any] = {}
    stream: bool = False


class RAGQueryRequest(BaseModel):
    """RAG 查询请求"""
    query: str
    top_k: int = 5
    use_discourse: bool = True


class FileUploadRequest(BaseModel):
    """文件上传请求"""
    filename: str
    mime_type: str
    category: str = "general"
    content: str  # Base64


# ==================== API 路由器 ====================

if FASTAPI_AVAILABLE:
    # 聊天 API
    chat_router = APIRouter(prefix="/chat", tags=["chat"])

    @chat_router.post("/completions")
    async def chat_completions(request: ChatRequest):
        """聊天完成"""
        try:
            # 导入核心模块
            from core.agent import HermesAgent

            # 执行聊天
            agent = HermesAgent.get_instance()
            response = await agent.chat(request.message)

            return ChatResponse(
                success=True,
                message=response,
                session_id=request.session_id,
                timestamp=time.time()
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @chat_router.get("/history/{session_id}")
    async def get_chat_history(session_id: str, limit: int = 50):
        """获取聊天历史"""
        try:
            from core.session_db import SessionDB

            db = SessionDB.get_instance()
            history = db.get_history(session_id, limit)

            return {
                "success": True,
                "session_id": session_id,
                "messages": history,
                "count": len(history)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 记忆 API (Cognee)
    memory_router = APIRouter(prefix="/memory", tags=["memory"])

    @memory_router.get("/search")
    async def search_memory(
        query: str,
        limit: int = 10,
        memory_type: Optional[str] = None
    ):
        """搜索记忆"""
        try:
            from core.cognee_memory import CogneeMemory

            memory = CogneeMemory.get_instance()
            results = await memory.recall(query, limit=limit)

            if memory_type:
                results = [r for r in results if r.get("type") == memory_type]

            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @memory_router.post("/store")
    async def store_memory(request: MemoryStoreRequest):
        """存储记忆"""
        try:
            from core.cognee_memory import CogneeMemory

            memory = CogneeMemory.get_instance()
            memory_id = await memory.remember(
                request.content,
                memory_type=request.memory_type,
                metadata=request.metadata
            )

            return {
                "success": True,
                "memory_id": memory_id,
                "timestamp": time.time()
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @memory_router.delete("/{memory_id}")
    async def delete_memory(memory_id: str):
        """删除记忆"""
        try:
            from core.cognee_memory import CogneeMemory

            memory = CogneeMemory.get_instance()
            await memory.forget(memory_id)

            return {
                "success": True,
                "memory_id": memory_id,
                "deleted": True
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @memory_router.post("/improve")
    async def improve_memory(feedback: Dict[str, Any]):
        """改进记忆"""
        try:
            from core.cognee_memory import CogneeMemory

            memory = CogneeMemory.get_instance()
            await memory.improve(feedback)

            return {
                "success": True,
                "improved": True
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 技能 API
    skills_router = APIRouter(prefix="/skills", tags=["skills"])

    @skills_router.get("/list")
    async def list_skills(category: Optional[str] = None):
        """获取技能列表"""
        try:
            from core.skill_market import SkillMarket

            market = SkillMarket.get_instance()
            skills = market.list_skills(category=category)

            return {
                "success": True,
                "skills": skills,
                "count": len(skills)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @skills_router.get("/{skill_id}")
    async def get_skill(skill_id: str):
        """获取技能详情"""
        try:
            from core.skill_market import SkillMarket

            market = SkillMarket.get_instance()
            skill = market.get_skill(skill_id)

            if not skill:
                raise HTTPException(status_code=404, detail="Skill not found")

            return {
                "success": True,
                "skill": skill
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @skills_router.post("/execute")
    async def execute_skill(request: SkillExecuteRequest):
        """执行技能"""
        try:
            from core.skill_market import SkillMarket

            market = SkillMarket.get_instance()
            result = await market.execute_skill(
                request.skill_id,
                params=request.params
            )

            return {
                "success": True,
                "skill_id": request.skill_id,
                "result": result,
                "timestamp": time.time()
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # RAG API (Disco-RAG)
    rag_router = APIRouter(prefix="/rag", tags=["rag"])

    @rag_router.post("/query")
    async def query_rag(request: RAGQueryRequest):
        """RAG 查询"""
        try:
            from core.disco_rag import DiscourseRAG

            rag = DiscourseRAG.get_instance()
            results = await rag.query(
                query=request.query,
                top_k=request.top_k,
                use_discourse=request.use_discourse
            )

            return {
                "success": True,
                "query": request.query,
                "results": results,
                "count": len(results)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @rag_router.post("/index")
    async def index_document(document: Dict[str, Any]):
        """索引文档"""
        try:
            from core.disco_rag import DiscourseRAG

            rag = DiscourseRAG.get_instance()
            doc_id = await rag.index_document(document)

            return {
                "success": True,
                "doc_id": doc_id,
                "timestamp": time.time()
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # vLLM API (Nano-vLLM)
    vllm_router = APIRouter(prefix="/vllm", tags=["vllm"])

    @vllm_router.post("/generate")
    async def generate(
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.6,
        max_tokens: int = 256
    ):
        """生成文本"""
        try:
            from core.nano_vllm import NanoVLLMClient, SamplingParams

            client = NanoVLLMClient.get_instance()
            params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens
            )
            output = await client.generate(prompt, params)

            return {
                "success": True,
                "text": output.text,
                "token_ids": output.token_ids,
                "finish_reason": output.finish_reason
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @vllm_router.get("/models")
    async def list_models():
        """列出可用模型"""
        try:
            from core.nano_vllm import NanoVLLMClient

            client = NanoVLLMClient.get_instance()
            models = client.list_models()

            return {
                "success": True,
                "models": models
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 文件 API
    files_router = APIRouter(prefix="/files", tags=["files"])

    @files_router.post("/upload")
    async def upload_file(request: FileUploadRequest):
        """上传文件"""
        try:
            import base64
            import uuid
            from pathlib import Path
            from core.file_manager import FileManager

            # 解码内容
            content = base64.b64decode(request.content)

            # 生成文件 ID
            file_id = str(uuid.uuid4())

            # 保存文件
            manager = FileManager.get_instance()
            saved_path = await manager.save_file(
                file_id=file_id,
                content=content,
                category=request.category
            )

            return {
                "success": True,
                "file_id": file_id,
                "filename": request.filename,
                "path": str(saved_path),
                "timestamp": time.time()
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @files_router.get("/{file_id}")
    async def download_file(file_id: str):
        """下载文件"""
        try:
            import base64
            from core.file_manager import FileManager

            manager = FileManager.get_instance()
            content = await manager.get_file(file_id)

            if not content:
                raise HTTPException(status_code=404, detail="File not found")

            return {
                "success": True,
                "file_id": file_id,
                "content": base64.b64encode(content).decode()
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @files_router.delete("/{file_id}")
    async def delete_file(file_id: str):
        """删除文件"""
        try:
            from core.file_manager import FileManager

            manager = FileManager.get_instance()
            deleted = await manager.delete_file(file_id)

            return {
                "success": True,
                "file_id": file_id,
                "deleted": deleted
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket 处理 ====================

if FASTAPI_AVAILABLE:
    class ConnectionManager:
        """WebSocket 连接管理器"""

        def __init__(self):
            self.active_connections: Dict[str, List[WebSocket]] = {}

        async def connect(self, websocket: WebSocket, channel: str = "default"):
            """连接"""
            await websocket.accept()
            if channel not in self.active_connections:
                self.active_connections[channel] = []
            self.active_connections[channel].append(websocket)

        def disconnect(self, websocket: WebSocket, channel: str = "default"):
            """断开"""
            if channel in self.active_connections:
                if websocket in self.active_connections[channel]:
                    self.active_connections[channel].remove(websocket)

        async def broadcast(self, channel: str, message: dict):
            """广播"""
            if channel in self.active_connections:
                for connection in self.active_connections[channel]:
                    try:
                        await connection.send_json(message)
                    except:
                        pass

    manager = ConnectionManager()

    @chat_router.websocket("/ws")
    async def chat_websocket(websocket: WebSocket, channel: str = "default"):
        """聊天 WebSocket"""
        await manager.connect(websocket, channel)

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "chat":
                    from core.agent import HermesAgent
                    agent = HermesAgent.get_instance()
                    response = await agent.chat(data.get("message", ""))

                    await websocket.send_json({
                        "type": "response",
                        "message": response,
                        "timestamp": time.time()
                    })

                elif msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })

        except WebSocketDisconnect:
            manager.disconnect(websocket, channel)
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
            manager.disconnect(websocket, channel)


# ==================== Vheer API (多模态) ====================

if FASTAPI_AVAILABLE:
    vheer_router = APIRouter(prefix="/vheer", tags=["vheer"])

    class ImageGenerateRequest(BaseModel):
        """图像生成请求"""
        prompt: str
        model: str = "flux-schnell"
        width: int = 1024
        height: int = 1024
        style: str = "realistic"
        quality: str = "standard"
        seed: Optional[int] = None


    class VideoGenerateRequest(BaseModel):
        """视频生成请求"""
        prompt: Optional[str] = None
        image_path: Optional[str] = None  # Base64 or path
        model: str = "wan-2.1"
        duration: int = 5
        fps: int = 24
        resolution: str = "720p"
        seed: Optional[int] = None


    @vheer_router.post("/image")
    async def generate_image(request: ImageGenerateRequest):
        """文生图"""
        try:
            from core.vheer_client import VheerService, ImageGenerationParams

            service = VheerService()
            params = ImageGenerationParams(
                model=request.model,
                width=request.width,
                height=request.height,
                style=request.style,
                quality=request.quality,
                seed=request.seed
            )

            result = await service.client.text_to_image(request.prompt, params)

            return {
                "success": result.status != "failed",
                "task_id": result.task_id,
                "status": result.status,
                "image_url": result.result_url,
                "error": result.error
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @vheer_router.post("/video")
    async def generate_video(request: VideoGenerateRequest):
        """图生视频/文生视频"""
        try:
            from core.vheer_client import VheerService

            service = VheerService()

            if request.image_path:
                # 图生视频
                result = await service.generate_video_from_image(
                    request.image_path,
                    duration=request.duration
                )
            else:
                # 文生视频
                result = await service.generate_video_from_text(
                    request.prompt,
                    duration=request.duration
                )

            return {
                "success": result is not None,
                "video_url": result,
                "error": None if result else "Generation failed"
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @vheer_router.get("/task/{task_id}")
    async def get_task_status(task_id: str):
        """获取任务状态"""
        try:
            from core.vheer_client import VheerClient

            client = VheerClient()
            result = client.get_task_status(task_id)

            return {
                "success": result.status != "failed",
                "task_id": result.task_id,
                "status": result.status,
                "result_url": result.result_url,
                "preview_url": result.preview_url,
                "error": result.error
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @vheer_router.get("/models")
    async def list_vheer_models(type: str = "image"):
        """列出可用模型"""
        try:
            from core.vheer_client import VheerClient

            client = VheerClient()
            models = client.list_available_models(type)

            return {
                "success": True,
                "type": type,
                "models": models
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ==================== 导出路由器 ====================

if FASTAPI_AVAILABLE:
    __all__ = [
        "chat_router",
        "memory_router",
        "skills_router",
        "rag_router",
        "vllm_router",
        "files_router",
        "vheer_router",
    ]
else:
    __all__ = []
