"""
AI计算服务处理器
AI Computing Handler

通过DataChannel将AI任务发送到卖家的本地Ollama/Hermes模型
"""

from typing import Dict, Any, Optional, List
import asyncio
import logging
import time
import uuid
import json

from .base import BaseServiceHandler, HandlerConfig, HandlerCapability
from ..models import AIJob

logger = logging.getLogger(__name__)


class AIComputingHandler(BaseServiceHandler):
    """
    AI计算服务处理器

    功能:
    - 接收买家的AI任务(文本生成/代码/推理)
    - 通过DataChannel发送到卖家本地Ollama/Hermes
    - 返回AI生成结果
    - 按token量计费
    """

    def __init__(self, config: Optional[HandlerConfig] = None):
        if config is None:
            config = HandlerConfig(
                max_concurrent=5,
                capabilities=[
                    HandlerCapability.DATACHANNEL.value,
                ]
            )
        super().__init__(config)

        # 会话数据结构
        # {
        #   session_id: {
        #       "listing_id": str,
        #       "seller_id": str,
        #       "buyer_id": str,
        #       "room_id": str,
        #       "room_password": str,
        #       "available_models": [str],
        #       "current_model": str,
        #       "jobs": {job_id: AIJob},
        #       "created_at": float,
        #       "last_heartbeat": {},
        #       "billing_start": float,
        #   }
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def service_type(self) -> str:
        return "ai_computing"

    async def create_session(
        self,
        listing_id: str,
        seller_id: str,
        buyer_id: str,
        models: List[str] = None,
        default_model: str = "qwen2.5:0.5b",
        **kwargs
    ) -> str:
        """创建AI计算会话"""
        session_id = f"ai_{uuid.uuid4().hex[:12]}"

        room_id = f"ai_{uuid.uuid4().hex[:8]}"
        room_password = str(uuid.uuid4().hex[:6])

        if models is None:
            models = [default_model]

        session_data = {
            "listing_id": listing_id,
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "room_id": room_id,
            "room_password": room_password,
            "available_models": models,
            "current_model": default_model,
            "jobs": {},  # job_id -> AIJob
            "created_at": time.time(),
            "last_heartbeat": {},
            "billing_start": None,
        }

        self._sessions[session_id] = session_data

        logger.info(f"[AIComputing] Created session {session_id} for seller {seller_id}")
        return session_id

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """买家加入AI计算会话"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 开始计费
        if session["billing_start"] is None:
            session["billing_start"] = time.time()

        return {
            "session_id": session_id,
            "room_id": session["room_id"],
            "room_password": session["room_password"],
            "available_models": session["available_models"],
            "current_model": session["current_model"],
            "ice_servers": kwargs.get("ice_servers", []),
        }

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """结束会话，返回计费信息"""
        if session_id not in self._sessions:
            return {}

        session = self._sessions[session_id]

        # 计算费用
        total_input_tokens = 0
        total_output_tokens = 0
        for job in session["jobs"].values():
            if job.status == "completed":
                total_input_tokens += job.input_tokens
                total_output_tokens += job.output_tokens

        billing_info = {
            "duration_seconds": int(time.time() - session["created_at"]),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
        }

        del self._sessions[session_id]
        logger.info(f"[AIComputing] Ended session {session_id}: {billing_info}")

        return billing_info

    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """处理心跳"""
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 检查双方心跳
        required_users = [session["seller_id"], session["buyer_id"]]
        for uid in required_users:
            last_hb = session["last_heartbeat"].get(uid, 0)
            if time.time() - last_hb > self.config.heartbeat_timeout_seconds:
                return False

        return True

    async def submit_job(
        self,
        session_id: str,
        task_type: str,
        prompt: str,
        model: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        提交AI任务

        Args:
            session_id: 会话ID
            task_type: 任务类型 (chat/complete/embed/reasoning)
            prompt: 输入提示
            model: 使用的模型
            parameters: 额外参数

        Returns:
            job_id: 任务ID
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]

        # 创建任务
        job = AIJob(
            session_id=session_id,
            task_type=task_type,
            prompt=prompt,
            model=model or session["current_model"],
            parameters=parameters or {},
        )

        session["jobs"][job.id] = job

        # 异步执行任务（已迁移到GlobalModelRouter）
        asyncio.create_task(self._execute_job(session_id, job.id))

        logger.info(f"[AIComputing] Submitted job {job.id} to session {session_id}")
        return job.id

    async def _execute_job(self, session_id: str, job_id: str) -> None:
        """执行AI任务"""
        session = self._sessions.get(session_id)
        if not session:
            return

        job = session["jobs"].get(job_id)
        if not job:
            return

        try:
            job.status = "running"
            job.started_at = time.time()

            # 使用全局模型路由器（异步调用）
            from client.src.business.global_model_router import get_global_router, ModelCapability
            router = get_global_router()
            
            result = await router.call_model(
                capability=ModelCapability.CHAT,
                prompt=job.prompt,
                system_prompt="你是一个AI计算服务助手。"
            )
            
            job.result = result if isinstance(result, str) else result.get("response", "")
            # 注意：无法直接获取token数，使用估算
            job.input_tokens = len(job.prompt) // 4
            job.output_tokens = len(job.result) // 4
            
        except Exception as e:
            logger.error(f"[AIComputing] 任务执行失败: {e}")
            job.status = "failed"
            job.result = f"执行失败: {str(e)}"
            
        else:
            job.status = "completed"
            job.completed_at = time.time()

            logger.info(f"[AIComputing] Job {job_id} completed")
            
    async def get_job_result(self, session_id: str, job_id: str) -> Optional[AIJob]:
        """获取任务结果"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session["jobs"].get(job_id)

    async def cancel_job(self, session_id: str, job_id: str) -> bool:
        """取消任务"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        job = session["jobs"].get(job_id)
        if not job:
            return False

        if job.status in ("queued", "running"):
            job.status = "failed"
            job.error = "Cancelled by user"
            return True

        return False

    async def switch_model(self, session_id: str, model: str) -> bool:
        """切换模型"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if model in session["available_models"]:
            session["current_model"] = model
            return True

        return False

    async def on_session_data(self, session_id: str, user_id: str, data: bytes) -> Optional[bytes]:
        """
        处理DataChannel数据

        期望格式:
        - 发送任务: {"type": "job", "task_type": "chat", "prompt": "...", "model": "..."}
        - 接收结果: {"type": "result", "job_id": "...", "status": "completed", "result": "..."}
        """
        try:
            msg = json.loads(data.decode("utf-8"))

            if msg.get("type") == "job":
                # 收到新任务
                job_id = await self.submit_job(
                    session_id=session_id,
                    task_type=msg.get("task_type", "chat"),
                    prompt=msg.get("prompt", ""),
                    model=msg.get("model"),
                    parameters=msg.get("parameters", {}),
                )

                return json.dumps({
                    "type": "job_ack",
                    "job_id": job_id,
                }).encode("utf-8")

            elif msg.get("type") == "result":
                # 收到结果(回传)
                job_id = msg.get("job_id")
                result_data = {
                    "type": "result",
                    "job_id": job_id,
                    "status": msg.get("status"),
                    "result": msg.get("result"),
                }
                return json.dumps(result_data).encode("utf-8")

        except json.JSONDecodeError:
            pass

        return None

    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话统计"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        jobs = session["jobs"]
        completed = sum(1 for j in jobs.values() if j.status == "completed")
        running = sum(1 for j in jobs.values() if j.status == "running")
        failed = sum(1 for j in jobs.values() if j.status == "failed")

        return {
            "session_id": session_id,
            "total_jobs": len(jobs),
            "completed": completed,
            "running": running,
            "failed": failed,
            "total_input_tokens": sum(j.input_tokens for j in jobs.values()),
            "total_output_tokens": sum(j.output_tokens for j in jobs.values()),
        }