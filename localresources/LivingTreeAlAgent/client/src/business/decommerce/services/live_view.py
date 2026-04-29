"""
远程实景直播处理器
Remote Live View Handler

通过WebRTC视频穿透，让买家实时查看卖家的现场
"""

from typing import Dict, Any, Optional
import asyncio
import logging
import time

from .base import BaseServiceHandler, HandlerConfig, HandlerCapability

logger = logging.getLogger(__name__)


class RemoteLiveViewHandler(BaseServiceHandler):
    """
    远程实景直播处理器

    功能:
    - 卖家端: 捕获摄像头/屏幕，通过WebRTC广播
    - 买家端: 接收视频流，实时观看
    - 支持多人同时观看(直播模式)
    """

    def __init__(self, config: Optional[HandlerConfig] = None):
        if config is None:
            config = HandlerConfig(
                max_concurrent=10,  # 支持最多10人同时观看
                capabilities=[
                    HandlerCapability.VIDEO.value,
                    HandlerCapability.AUDIO.value,
                    HandlerCapability.SCREEN_SHARE.value,
                ]
            )
        super().__init__(config)

        # 会话数据结构
        # {
        #   session_id: {
        #       "listing_id": str,
        #       "seller_id": str,
        #       "buyer_ids": [str],
        #       "room_id": str,
        #       "room_password": str,
        #       "stream_type": "camera" | "screen",
        #       "created_at": float,
        #       "last_heartbeat": {"seller_id": timestamp, "buyer_id": timestamp}
        #   }
        # }
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def service_type(self) -> str:
        return "remote_live_view"

    async def create_session(
        self,
        listing_id: str,
        seller_id: str,
        buyer_id: str = "",
        stream_type: str = "camera",
        **kwargs
    ) -> str:
        """创建直播会话"""
        import uuid
        session_id = f"live_{uuid.uuid4().hex[:12]}"

        # 生成房间信息
        room_id = f"rv_{uuid.uuid4().hex[:8]}"
        room_password = str(uuid.uuid4().hex[:6])

        session_data = {
            "listing_id": listing_id,
            "seller_id": seller_id,
            "buyer_ids": [],
            "room_id": room_id,
            "room_password": room_password,
            "stream_type": stream_type,
            "created_at": time.time(),
            "last_heartbeat": {},
            "is_broadcasting": False,
        }

        self._sessions[session_id] = session_data

        # 如果有初始买家，先加入
        if buyer_id:
            session_data["buyer_ids"].append(buyer_id)

        logger.info(f"[RemoteLiveView] Created session {session_id} for seller {seller_id}")
        return session_id

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """买家加入直播"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]

        # 检查用户是否已在列表
        if user_id not in session["buyer_ids"]:
            # 检查并发限制
            if len(session["buyer_ids"]) >= self.config.max_concurrent:
                raise RuntimeError("Session is full")
            session["buyer_ids"].append(user_id)

        # 更新心跳
        session["last_heartbeat"][user_id] = time.time()

        return {
            "session_id": session_id,
            "room_id": session["room_id"],
            "room_password": session["room_password"],
            "stream_type": session["stream_type"],
            "ice_servers": kwargs.get("ice_servers", []),
            "is_broadcasting": session["is_broadcasting"],
        }

    async def end_session(self, session_id: str) -> None:
        """结束直播会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"[RemoteLiveView] Ended session {session_id}")

    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """处理心跳"""
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session["last_heartbeat"][user_id] = time.time()

        # 检查对方是否还存活
        if user_id == session["seller_id"]:
            # 卖家心跳
            return True
        else:
            # 买家心跳
            seller_heartbeat = session["last_heartbeat"].get(session["seller_id"], 0)
            if time.time() - seller_heartbeat > self.config.heartbeat_timeout_seconds:
                return False
            return True

    async def start_broadcast(self, session_id: str) -> None:
        """卖家开始广播"""
        if session_id in self._sessions:
            self._sessions[session_id]["is_broadcasting"] = True
            logger.info(f"[RemoteLiveView] Broadcast started: {session_id}")

    async def stop_broadcast(self, session_id: str) -> None:
        """卖家停止广播"""
        if session_id in self._sessions:
            self._sessions[session_id]["is_broadcasting"] = False
            logger.info(f"[RemoteLiveView] Broadcast stopped: {session_id}")

    def get_viewer_count(self, session_id: str) -> int:
        """获取观众数量"""
        if session_id in self._sessions:
            return len(self._sessions[session_id]["buyer_ids"])
        return 0