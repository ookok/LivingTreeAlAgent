"""
卖家节点 (SellerNode)
Seller Node - P2P微服务器

每个卖家桌面运行一个SellerNode,相当于一个"微服务器":
- 向Tracker注册商品/服务
- 维护P2P连接能力
- 处理买家的实时连接请求
"""

from typing import Dict, Any, Optional, List, Callable
import asyncio
import logging
import time
import uuid
import json

from .models import (
    ServiceListing, ServiceType, ServiceStatus,
    Seller, P2PEndpoint, ConnectionQuality, ServiceSession
)
from .service_registry import get_service_registry
from .services import get_handler_registry
from ..webrtc import IceSelector

logger = logging.getLogger(__name__)


class SellerNode:
    """
    卖家节点

    功能:
    - 维护卖家信息与连接能力
    - 发布/管理商品服务
    - 监听并处理买家连接
    - 启动WebRTC信令服务
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        tracker_url: str = "http://localhost:8765",
        http_port: int = 8766,
    ):
        self.user_id = user_id
        self.name = name
        self.tracker_url = tracker_url
        self.http_port = http_port

        # 卖家信息
        self.seller_id = str(uuid.uuid4())[:12]
        self._seller: Optional[Seller] = None

        # 连接能力
        self._endpoint: Optional[P2PEndpoint] = None
        self._ice_selector: Optional[IceSelector] = None

        # 本地服务
        self._listings: Dict[str, ServiceListing] = {}
        self._active_sessions: Dict[str, ServiceSession] = {}

        # HTTP服务器
        self._http_server = None
        self._ws_connections: Dict[str, Any] = {}  # session_id -> ws

        # 状态
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

        # 回调
        self._on_listing_request: List[Callable] = []
        self._on_session_request: List[Callable] = []
        self._on_message: List[Callable] = []

    @property
    def seller(self) -> Optional[Seller]:
        return self._seller

    @property
    def endpoint(self) -> Optional[P2PEndpoint]:
        return self._endpoint

    @property
    def is_online(self) -> bool:
        return self._running and self._endpoint is not None

    # ==================== 初始化 ====================

    async def initialize(
        self,
        cloud_turn_url: Optional[str] = None,
        cloud_turn_user: Optional[str] = None,
        cloud_turn_credential: Optional[str] = None,
    ) -> bool:
        """
        初始化卖家节点

        1. 探测网络能力
        2. 创建ICE配置
        3. 注册到Tracker
        """
        logger.info(f"[SellerNode] Initializing for user {self.user_id}")

        # 探测网络能力
        self._ice_selector = IceSelector()
        ice_config = await self._ice_selector.select_best_config(
            cloud_turn_url=cloud_turn_url,
            cloud_turn_user=cloud_turn_user,
            cloud_turn_credential=cloud_turn_credential,
        )

        # 构建端点信息
        self._endpoint = P2PEndpoint(
            type="webrtc",
            ice_servers=ice_config.get("iceServers", []),
            public_ip=ice_config.get("public_ip"),
            nat_type=ice_config.get("nat_type"),
            turn_url=cloud_turn_url,
            turn_username=cloud_turn_user,
            turn_credential=cloud_turn_credential,
            quality_score=ice_config.get("quality_score", 50),
        )

        # 评估连接质量
        connectivity = ConnectionQuality.EXCELLENT if self._endpoint.quality_score >= 90 else \
            ConnectionQuality.GOOD if self._endpoint.quality_score >= 70 else \
            ConnectionQuality.FAIR if self._endpoint.quality_score >= 50 else \
            ConnectionQuality.POOR

        # 创建卖家对象
        self._seller = Seller(
            id=self.seller_id,
            user_id=self.user_id,
            name=self.name,
            connectivity=connectivity,
            endpoint=self._endpoint,
            is_online=True,
        )

        # 获取可用的AI模型
        try:
            from ..system_brain import get_system_brain
            brain = get_system_brain()
            if brain:
                self._seller.ai_models = brain.get_available_models() or []
                self._seller.has_ai_service = len(self._seller.ai_models) > 0
        except Exception as e:
            logger.warning(f"[SellerNode] Could not detect AI models: {e}")

        # 注册到Tracker
        await self._register_to_tracker()

        # 启动HTTP服务
        await self._start_http_server()

        logger.info(f"[SellerNode] Initialized successfully")
        logger.info(f"  - Seller ID: {self.seller_id}")
        logger.info(f"  - Public IP: {self._endpoint.public_ip}")
        logger.info(f"  - NAT Type: {self._endpoint.nat_type}")
        logger.info(f"  - Quality Score: {self._endpoint.quality_score}")

        return True

    async def shutdown(self) -> None:
        """关闭卖家节点"""
        logger.info(f"[SellerNode] Shutting down...")

        self._running = False

        # 停止心跳
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 下线所有商品
        for listing in self._listings.values():
            listing.status = ServiceStatus.OFFLINE

        # 从Tracker注销
        await self._unregister_from_tracker()

        # 停止HTTP服务
        if self._http_server:
            self._http_server.close()
            await self._http_server.wait_closed()

        # 关闭所有会话
        self._active_sessions.clear()

        logger.info(f"[SellerNode] Shutdown complete")

    # ==================== 服务发布 ====================

    async def publish_listing(
        self,
        title: str,
        description: str,
        price: int,
        service_type: ServiceType,
        delivery_type: str = "instant",
        ai_model: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        **kwargs
    ) -> ServiceListing:
        """
        发布商品/服务

        Args:
            title: 商品标题
            description: 商品描述
            price: 价格(分)
            service_type: 服务类型
            delivery_type: 交付方式
            ai_model: AI模型 (用于AI计算服务)
            thumbnail_url: 缩略图URL
        """
        listing = ServiceListing(
            seller_id=self.seller_id,
            title=title,
            description=description,
            price=price,
            service_type=service_type,
            delivery_type=delivery_type,
            endpoint=self._endpoint,
            ai_model=ai_model,
            is_live_available=self._endpoint is not None and self._endpoint.quality_score >= 50,
            status=ServiceStatus.ONLINE,
            thumbnail_url=thumbnail_url,
        )

        self._listings[listing.id] = listing

        # 更新Seller统计
        if self._seller:
            self._seller.total_services += 1

        # 向Tracker注册
        await self._register_listing_to_tracker(listing)

        logger.info(f"[SellerNode] Published listing: {listing.id} ({title})")

        return listing

    async def update_listing(
        self,
        listing_id: str,
        **updates
    ) -> Optional[ServiceListing]:
        """更新商品/服务"""
        listing = self._listings.get(listing_id)
        if not listing:
            return None

        allowed = ["title", "description", "price", "status", "thumbnail_url"]
        for key, value in updates.items():
            if key in allowed and hasattr(listing, key):
                setattr(listing, key, value)

        listing.updated_at = time.time()

        # 向Tracker更新
        await self._register_listing_to_tracker(listing)

        return listing

    async def unpublish_listing(self, listing_id: str) -> bool:
        """下架商品/服务"""
        listing = self._listings.get(listing_id)
        if not listing:
            return False

        listing.status = ServiceStatus.OFFLINE
        listing.updated_at = time.time()

        # 通知Tracker
        await self._unregister_listing_from_tracker(listing_id)

        return True

    def get_listing(self, listing_id: str) -> Optional[ServiceListing]:
        """获取商品/服务"""
        return self._listings.get(listing_id)

    def get_all_listings(self) -> List[ServiceListing]:
        """获取所有商品/服务"""
        return list(self._listings.values())

    def get_online_listings(self) -> List[ServiceListing]:
        """获取在线商品/服务"""
        return [
            l for l in self._listings.values()
            if l.status == ServiceStatus.ONLINE
        ]

    # ==================== 会话处理 ====================

    async def handle_connection_request(
        self,
        session_id: str,
        buyer_id: str,
        listing_id: str,
    ) -> Dict[str, Any]:
        """
        处理买家的连接请求

        Returns:
            包含room_id, sdp_offer等信息
        """
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")

        # 创建会话
        session = ServiceSession(
            id=session_id,
            listing_id=listing_id,
            seller_id=self.seller_id,
            buyer_id=buyer_id,
            session_type=listing.service_type,
            room_id=f"room_{uuid.uuid4().hex[:8]}",
            room_password=str(uuid.uuid4().hex[:6]),
            status="connecting",
        )

        self._active_sessions[session_id] = session

        # 触发回调
        for cb in self._on_session_request:
            asyncio.create_task(self._safe_call(cb, session))

        return {
            "session_id": session_id,
            "room_id": session.room_id,
            "room_password": session.room_password,
            "ice_servers": self._endpoint.ice_servers if self._endpoint else [],
            "endpoint": self._endpoint.to_dict() if self._endpoint else None,
        }

    async def accept_session(self, session_id: str) -> None:
        """卖家接受会话"""
        session = self._active_sessions.get(session_id)
        if session:
            session.status = "active"

    async def reject_session(self, session_id: str, reason: str = "") -> None:
        """卖家拒绝会话"""
        session = self._active_sessions.get(session_id)
        if session:
            session.status = "rejected"
            # 通知买家
            await self._notify_session_rejected(session_id, reason)

    async def end_session(self, session_id: str) -> None:
        """结束会话"""
        session = self._active_sessions.get(session_id)
        if session:
            session.status = "completed"
            session.billing_end = time.time()

            if session.billing_start:
                session.billing_duration_seconds = int(
                    session.billing_end - session.billing_start
                )

            # 触发回调
            for cb in self._on_message:
                asyncio.create_task(self._safe_call(cb, "session_ended", session))

        if session_id in self._active_sessions:
            del self._active_sessions[session_id]

    # ==================== HTTP服务 ====================

    async def _start_http_server(self) -> None:
        """启动本地HTTP服务 (供买家访问)"""
        from aiohttp import web

        async def handle_index(request):
            return web.FileResponse("./assets/webrtc/index.html")

        async def handle_listings(request):
            """返回卖家当前在线的商品"""
            listings = self.get_online_listings()
            return web.json_response([l.to_dict() for l in listings])

        async def handle_ws(request):
            """WebSocket连接 - 处理信令"""
            ws = web.WebSocketResponse()
            await ws.prepare(request)

            session_id = None
            try:
                async for msg in ws:
                    if msg.type == web.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        result = await self._handle_ws_message(ws, data)
                        if result:
                            await ws.send_json(result)
                    elif msg.type == web.WSMsgType.ERROR:
                        logger.warning(f"[SellerNode] WS error: {ws.exception()}")
            finally:
                if session_id and session_id in self._ws_connections:
                    del self._ws_connections[session_id]

            return ws

        app = web.Application()
        app.router.add_get("/", handle_index)
        app.router.add_get("/api/listings", handle_listings)
        app.router.add_get("/ws", handle_ws)

        self._http_server = await web._run_app(
            app,
            host="0.0.0.0",
            port=self.http_port,
            print=None,
        )

        logger.info(f"[SellerNode] HTTP server started on port {self.http_port}")

    async def _handle_ws_message(self, ws, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理WebSocket消息"""
        msg_type = data.get("type")

        if msg_type == "join":
            # 买家请求加入会话
            session_id = data.get("session_id")
            listing_id = data.get("listing_id")
            buyer_id = data.get("buyer_id")

            if session_id in self._active_sessions:
                self._ws_connections[session_id] = ws
                return {
                    "type": "joined",
                    "session_id": session_id,
                    "room_id": self._active_sessions[session_id].room_id,
                }

        elif msg_type == "offer":
            # 转发SDP Offer
            session_id = data.get("session_id")
            sdp = data.get("sdp")

            # 通知卖家
            for cb in self._on_message:
                asyncio.create_task(self._safe_call(cb, "offer_received", {
                    "session_id": session_id,
                    "sdp": sdp,
                }))

        elif msg_type == "answer":
            # 转发SDP Answer
            session_id = data.get("session_id")
            sdp = data.get("sdp")

            # 转发给发起方
            if session_id in self._ws_connections:
                await self._ws_connections[session_id].send_json({
                    "type": "answer",
                    "sdp": sdp,
                })

        elif msg_type == "ice_candidate":
            # 转发ICE候选
            session_id = data.get("session_id")
            candidate = data.get("candidate")

            if session_id in self._ws_connections:
                await self._ws_connections[session_id].send_json({
                    "type": "ice_candidate",
                    "candidate": candidate,
                })

        return None

    async def _notify_session_rejected(self, session_id: str, reason: str) -> None:
        """通知买家会话被拒绝"""
        if session_id in self._ws_connections:
            await self._ws_connections[session_id].send_json({
                "type": "session_rejected",
                "session_id": session_id,
                "reason": reason,
            })

    # ==================== Tracker通信 ====================

    async def _register_to_tracker(self) -> None:
        """注册到Tracker服务器"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tracker_url}/api/sellers/register",
                    json={
                        "seller": self._seller.to_dict() if self._seller else None,
                        "endpoint": self._endpoint.to_dict() if self._endpoint else None,
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"[SellerNode] Registered to tracker")
                    else:
                        logger.warning(f"[SellerNode] Tracker registration failed: {resp.status}")
        except Exception as e:
            logger.warning(f"[SellerNode] Could not register to tracker: {e}")

    async def _unregister_from_tracker(self) -> None:
        """从Tracker注销"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tracker_url}/api/sellers/unregister",
                    json={"seller_id": self.seller_id},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    pass
        except Exception:
            pass

    async def _register_listing_to_tracker(self, listing: ServiceListing) -> None:
        """向Tracker注册商品"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tracker_url}/api/listings/register",
                    json=listing.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    pass
        except Exception as e:
            logger.warning(f"[SellerNode] Could not register listing to tracker: {e}")

    async def _unregister_listing_from_tracker(self, listing_id: str) -> None:
        """从Tracker注销商品"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tracker_url}/api/listings/unregister",
                    json={"listing_id": listing_id},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    pass
        except Exception:
            pass

    # ==================== 心跳 ====================

    async def _start_heartbeat(self) -> None:
        """启动心跳"""
        async def heartbeat_loop():
            while self._running:
                try:
                    await self._send_heartbeat()
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[SellerNode] Heartbeat error: {e}")
                    await asyncio.sleep(5)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _send_heartbeat(self) -> None:
        """发送心跳到Tracker"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tracker_url}/api/heartbeat",
                    json={
                        "seller_id": self.seller_id,
                        "endpoint": self._endpoint.to_dict() if self._endpoint else None,
                        "active_sessions": len(self._active_sessions),
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    pass
        except Exception:
            pass

    # ==================== 回调管理 ====================

    def on_listing_request(self, callback: Callable) -> None:
        """监听商品请求"""
        self._on_listing_request.append(callback)

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
            logger.error(f"[SellerNode] Callback error: {e}")

    # ==================== 工具 ====================

    def get_public_url(self) -> str:
        """获取卖家服务的公开访问URL"""
        if self._endpoint and self._endpoint.public_ip:
            return f"http://{self._endpoint.public_ip}:{self.http_port}"
        return f"http://localhost:{self.http_port}"

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "seller_id": self.seller_id,
            "name": self.name,
            "is_online": self.is_online,
            "endpoint": self._endpoint.to_dict() if self._endpoint else None,
            "total_listings": len(self._listings),
            "online_listings": len(self.get_online_listings()),
            "active_sessions": len(self._active_sessions),
            "ai_models": self._seller.ai_models if self._seller else [],
        }