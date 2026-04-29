"""
知识咨询处理器
Knowledge Consultation Handler

一对一专家咨询：音视频通话 + 屏幕共享
"""

from typing import Dict, Any, Optional
import asyncio
import logging
import time
import uuid

from .base import BaseServiceHandler, HandlerConfig, HandlerCapability

logger = logging.getLogger(__name__)


class KnowledgeConsultHandler(BaseServiceHandler):
    """
    知识咨询处理器

    功能:
    - 一对一视频咨询
    - 屏幕共享
    - 聊天消息
    - 咨询计时计费
    """

    def __init__(self, config: Optional[HandlerConfig] = None):
        if config is None:
            config = HandlerConfig(
                max_concurrent=1,  # 一对一咨询
                capabilities=[
                    HandlerCapability.VIDEO.value,
                    HandlerCapability.AUDIO.value,
                    HandlerCapability.SCREEN_SHARE.value,
                ]
            )
        super().__init__(config)

        self._sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def service_type(self) -> str:
        return "knowledge_consult"

    async def create_session(
        self,
        listing_id: str,
        seller_id: str,
        buyer_id: str,
        consultation_topic: str = "",
        duration_limit: int = 3600,  # 默认1小时
        **kwargs
    ) -> str:
        """创建咨询会话"""
        session_id = f"kc_{uuid.uuid4().hex[:12]}"

        room_id = f"kc_{uuid.uuid4().hex[:8]}"
        room_password = str(uuid.uuid4().hex[:6])

        session_data = {
            "listing_id": listing_id,
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "topic": consultation_topic,
            "room_id": room_id,
            "room_password": room_password,
            "duration_limit": duration_limit,
            "created_at": time.time(),
            "billing_start": None,
            "billing_end": None,
            "last_heartbeat": {},
            "messages": [],
            "is_active": False,
        }

        self._sessions[session_id] = session_data

        logger.info(f"[KnowledgeConsult] Created session {session_id}")
        return session_id

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """加入咨询会话"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 开始计费
        if session["billing_start"] is None:
            session["billing_start"] = time.time()
            session["is_active"] = True

        return {
            "session_id": session_id,
            "room_id": session["room_id"],
            "room_password": session["room_password"],
            "topic": session["topic"],
            "duration_limit": session["duration_limit"],
            "ice_servers": kwargs.get("ice_servers", []),
        }

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """结束咨询会话"""
        if session_id not in self._sessions:
            return {}

        session = self._sessions[session_id]
        session["billing_end"] = time.time()
        session["is_active"] = False

        # 计算费用
        duration = 0
        if session["billing_start"] and session["billing_end"]:
            duration = int(session["billing_end"] - session["billing_start"])

        billing_info = {
            "session_id": session_id,
            "duration_seconds": duration,
            "billing_start": session["billing_start"],
            "billing_end": session["billing_end"],
            "messages_count": len(session["messages"]),
        }

        del self._sessions[session_id]
        logger.info(f"[KnowledgeConsult] Ended session {session_id}: {duration}s")

        return billing_info

    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """处理心跳"""
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 检查双方心跳
        required = [session["seller_id"], session["buyer_id"]]
        for uid in required:
            if time.time() - session["last_heartbeat"].get(uid, 0) > self.config.heartbeat_timeout_seconds:
                return False

        # 检查时长限制
        if session["billing_start"]:
            elapsed = time.time() - session["billing_start"]
            if elapsed > session["duration_limit"]:
                return False

        return True

    async def add_message(
        self,
        session_id: str,
        user_id: str,
        message: str,
        msg_type: str = "text"
    ) -> None:
        """添加聊天消息"""
        if session_id in self._sessions:
            self._sessions[session_id]["messages"].append({
                "user_id": user_id,
                "type": msg_type,
                "content": message,
                "timestamp": time.time(),
            })

    def get_session_duration(self, session_id: str) -> int:
        """获取当前咨询时长(秒)"""
        session = self._sessions.get(session_id)
        if not session or not session["billing_start"]:
            return 0

        end = session["billing_end"] or time.time()
        return int(end - session["billing_start"])

    async def pause_session(self, session_id: str) -> bool:
        """暂停咨询(保留现场)"""
        session = self._sessions.get(session_id)
        if session and session["is_active"]:
            session["billing_end"] = time.time()
            session["is_active"] = False
            return True
        return False

    async def resume_session(self, session_id: str) -> bool:
        """恢复咨询"""
        session = self._sessions.get(session_id)
        if session and not session["is_active"]:
            session["billing_start"] = time.time()  # 重置计时
            session["billing_end"] = None
            session["is_active"] = True
            return True
        return False