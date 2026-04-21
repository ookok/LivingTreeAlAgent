"""
买家客户端 (BuyerClient)
Buyer Client - 发现和连接卖家服务

功能:
- 从Tracker发现商品/服务
- 连接卖家节点
- 管理会话生命周期
"""

from typing import Dict, Any, Optional, List, Callable
import asyncio
import logging
import time
import uuid
import json

from .models import ServiceListing, ServiceType, ServiceStatus, P2PEndpoint, ServiceSession

logger = logging.getLogger(__name__)


class BuyerClient:
    """
    买家客户端

    功能:
    - 浏览商品目录
    - 连接卖家服务
    - 管理会话
    """

    def __init__(
        self,
        user_id: str,
        tracker_url: str = "http://localhost:8765",
    ):
        self.user_id = user_id
        self.tracker_url = tracker_url
        self.buyer_id = str(uuid.uuid4())[:12]

        # 状态
        self._running = False

        # 已发现的服务
        self._discovered_listings: Dict[str, ServiceListing] = {}

        # 活跃会话
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

        # WebSocket连接
        self._ws_connection: Optional[Any] = None

        # 回调
        self._on_listing_discovered: List[Callable] = []
        self._on_session_request: List[Callable] = []
        self._on_message: List[Callable] = []

    @property
    def is_connected(self) -> bool:
        return self._ws_connection is not None

    # ==================== 连接管理 ====================

    async def connect(self) -> bool:
        """连接到Tracker"""
        logger.info(f"[BuyerClient] Connecting to tracker: {self.tracker_url}")

        try:
            import aiohttp

            # 获取服务目录
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.tracker_url}/api/listings",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            listing = ServiceListing.from_dict(item)
                            self._discovered_listings[listing.id] = listing

            logger.info(f"[BuyerClient] Connected, discovered {len(self._discovered_listings)} listings")
            self._running = True
            return True

        except Exception as e:
            logger.error(f"[BuyerClient] Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        self._running = False

        # 关闭所有会话
        for session_id in list(self._active_sessions.keys()):
            await self.end_session(session_id)

        # 关闭WebSocket
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

        logger.info(f"[BuyerClient] Disconnected")

    # ==================== 服务发现 ====================

    async def refresh_catalog(self) -> List[ServiceListing]:
        """刷新服务目录"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.tracker_url}/api/listings",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._discovered_listings.clear()

                        for item in data:
                            listing = ServiceListing.from_dict(item)
                            self._discovered_listings[listing.id] = listing

                        # 触发回调
                        for cb in self._on_listing_discovered:
                            asyncio.create_task(self._safe_call(cb, listing))

        except Exception as e:
            logger.error(f"[BuyerClient] Failed to refresh catalog: {e}")

        return list(self._discovered_listings.values())

    async def search_listings(
        self,
        query: str = "",
        service_type: Optional[ServiceType] = None,
        live_only: bool = False,
    ) -> List[ServiceListing]:
        """搜索商品/服务"""
        results = []

        for listing in self._discovered_listings.values():
            # 过滤下线
            if listing.status != ServiceStatus.ONLINE:
                continue

            # 实时可用过滤
            if live_only and not listing.is_live_available:
                continue

            # 类型过滤
            if service_type and listing.service_type != service_type:
                continue

            # 关键词过滤
            if query:
                q_lower = query.lower()
                if q_lower not in listing.title.lower() and q_lower not in listing.description.lower():
                    continue

            results.append(listing)

        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    def get_listing(self, listing_id: str) -> Optional[ServiceListing]:
        """获取商品详情"""
        return self._discovered_listings.get(listing_id)

    def get_all_listings(self) -> List[ServiceListing]:
        """获取所有已发现的商品"""
        return list(self._discovered_listings.values())

    # ==================== 会话管理 ====================

    async def create_session(
        self,
        listing_id: str,
        seller_endpoint: Optional[P2PEndpoint] = None,
    ) -> Dict[str, Any]:
        """
        创建服务会话

        Args:
            listing_id: 商品ID
            seller_endpoint: 卖家端点信息 (可选,从listing中获取)

        Returns:
            包含session_id, 连接信息等
        """
        listing = self._discovered_listings.get(listing_id)
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")

        # 创建会话ID
        session_id = f"session_{uuid.uuid4().hex[:12]}"

        session_info = {
            "session_id": session_id,
            "listing_id": listing_id,
            "seller_id": listing.seller_id,
            "buyer_id": self.buyer_id,
            "listing": listing,
            "endpoint": seller_endpoint or listing.endpoint,
            "status": "created",
            "created_at": time.time(),
        }

        self._active_sessions[session_id] = session_info

        logger.info(f"[BuyerClient] Created session {session_id} for listing {listing_id}")

        # 触发回调
        for cb in self._on_session_request:
            asyncio.create_task(self._safe_call(cb, session_info))

        return session_info

    async def connect_to_session(
        self,
        session_id: str,
        ice_servers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        连接到卖家的会话

        Args:
            session_id: 会话ID
            ice_servers: ICE服务器配置

        Returns:
            包含WebRTC连接所需信息
        """
        session = self._active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        listing = session["listing"]

        # 构建连接信息
        connection_info = {
            "session_id": session_id,
            "room_id": f"{listing.seller_id}_{listing.id}",
            "ice_servers": ice_servers or listing.endpoint.ice_servers if listing.endpoint else [],
            "seller_endpoint": listing.endpoint.to_dict() if listing.endpoint else None,
        }

        session["status"] = "connecting"

        logger.info(f"[BuyerClient] Connecting to session {session_id}")

        return connection_info

    async def end_session(self, session_id: str) -> None:
        """结束会话"""
        session = self._active_sessions.get(session_id)
        if session:
            session["status"] = "ended"
            session["ended_at"] = time.time()

            # 计算时长
            if "connected_at" in session:
                session["duration"] = time.time() - session["connected_at"]

            # 触发回调
            for cb in self._on_message:
                asyncio.create_task(self._safe_call(cb, "session_ended", session))

            del self._active_sessions[session_id]

        logger.info(f"[BuyerClient] Ended session {session_id}")

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        return self._active_sessions.get(session_id)

    # ==================== 信令 ====================

    async def send_offer(
        self,
        session_id: str,
        sdp: str,
        sdp_type: str = "offer",
    ) -> None:
        """发送SDP Offer/Answer"""
        session = self._active_sessions.get(session_id)
        if not session:
            return

        # 通过Tracker转发
        try:
            import aiohttp
            async with aiohttp.ClientSession() as client:
                await client.post(
                    f"{self.tracker_url}/api/signal",
                    json={
                        "type": sdp_type,
                        "session_id": session_id,
                        "sdp": sdp,
                        "from": self.buyer_id,
                        "to": session["seller_id"],
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except Exception as e:
            logger.error(f"[BuyerClient] Failed to send {sdp_type}: {e}")

    async def send_ice_candidate(
        self,
        session_id: str,
        candidate: Dict[str, Any],
    ) -> None:
        """发送ICE候选"""
        session = self._active_sessions.get(session_id)
        if not session:
            return

        try:
            import aiohttp
            async with aiohttp.ClientSession() as client:
                await client.post(
                    f"{self.tracker_url}/api/signal/ice",
                    json={
                        "session_id": session_id,
                        "candidate": candidate,
                        "from": self.buyer_id,
                        "to": session["seller_id"],
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except Exception as e:
            logger.error(f"[BuyerClient] Failed to send ICE candidate: {e}")

    # ==================== AI计算任务 ====================

    async def submit_ai_job(
        self,
        session_id: str,
        task_type: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """
        提交AI计算任务

        Returns:
            job_id
        """
        session = self._active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        job_id = str(uuid.uuid4())[:12]

        # 通过DataChannel发送任务
        session["pending_job"] = {
            "job_id": job_id,
            "task_type": task_type,
            "prompt": prompt,
            "model": model,
            "submitted_at": time.time(),
        }

        logger.info(f"[BuyerClient] Submitted AI job {job_id} to session {session_id}")

        return job_id

    # ==================== 回调 ====================

    def on_listing_discovered(self, callback: Callable) -> None:
        """监听新商品发现"""
        self._on_listing_discovered.append(callback)

    def on_session_request(self, callback: Callable) -> None:
        """监听会话请求"""
        self._on_session_request.append(callback)

    def on_message(self, callback: Callable) -> None:
        """监听消息"""
        self._on_message.append(callback)

    async def _safe_call(self, callback: Callable, *args, **kwargs) -> None:
        """安全调用回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"[BuyerClient] Callback error: {e}")

    # ==================== 工具 ====================

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取活跃会话列表"""
        return [
            s for s in self._active_sessions.values()
            if s.get("status") not in ("ended", "completed")
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "buyer_id": self.buyer_id,
            "connected": self.is_connected,
            "discovered_listings": len(self._discovered_listings),
            "active_sessions": len(self.get_active_sessions()),
        }