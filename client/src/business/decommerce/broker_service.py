"""
P2P 去中心化电商 - 轻量Broker服务
Lightweight Broker Service

Broker是"轻量公证人"，只做:
1. 商品目录广播 (不存储商品内容)
2. 卖家上线/下线通知
3. P2P穿透参数下发 (STUN/TURN配置)
4. 订单哈希锚定 (防篡改)
5. 撮合消息传递 (SDP/ICE信令)

Broker不存储:
- 商品详情
- 买家真实地址/电话
- 支付信息
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import hashlib
import json
from aiohttp import web

logger = logging.getLogger(__name__)


class BrokerMessageType(Enum):
    """Broker消息类型"""
    # 发现层
    REGISTER_SELLER = "register_seller"
    UNREGISTER_SELLER = "unregister_seller"
    BROADCAST_FINGERPRINTS = "broadcast_fingerprints"
    FETCH_CATALOG = "fetch_catalog"

    # 信令层
    SIGNAL_OFFER = "signal_offer"
    SIGNAL_ANSWER = "signal_answer"
    SIGNAL_ICE = "signal_ice"

    # 订单层
    ANCHOR_ORDER = "anchor_order"
    FETCH_ORDER_ANCHOR = "fetch_order_anchor"

    # 穿透层
    REQUEST_RELAY_CONFIG = "request_relay_config"
    RELAY_CONFIG = "relay_config"


@dataclass
class SellerRecord:
    """卖家记录 (最小化信息)"""
    seller_id: str = ""
    peer_id: str = ""

    # 连接能力 (不存真实地址)
    connectivity_score: int = 0  # 0-100
    nat_type: str = ""  # full_cone / restricted / symmetric

    # 指纹列表 (只存哈希指纹)
    listing_fingerprints: List[str] = field(default_factory=list)  # listing_id列表

    # 状态
    is_online: bool = False
    last_heartbeat: float = 0

    # TURN配置 (用于转发给买家)
    turn_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seller_id": self.seller_id,
            "peer_id": self.peer_id,
            "connectivity_score": self.connectivity_score,
            "nat_type": self.nat_type,
            "listing_count": len(self.listing_fingerprints),
            "is_online": self.is_online,
            "last_heartbeat": self.last_heartbeat,
        }


@dataclass
class OrderAnchor:
    """订单哈希锚定 (不上传完整订单)"""
    order_id: str = ""
    anchor_hash: str = ""  # 订单哈希
    buyer_id: str = ""
    seller_id: str = ""

    # 锚定时间
    anchored_at: float = 0
    expires_at: float = 0

    # 状态
    status: str = "anchored"  # anchored | completed | disputed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "anchor_hash": self.anchor_hash,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "anchored_at": self.anchored_at,
            "expires_at": self.expires_at,
            "status": self.status,
        }


@dataclass
class SignalingMessage:
    """信令消息 (用于SDP/ICE转发)"""
    msg_type: str = ""  # offer / answer / ice_candidate
    session_id: str = ""
    from_peer_id: str = ""
    to_peer_id: str = ""

    # 负载
    payload: Dict[str, Any] = field(default_factory=dict)

    # 时间戳
    timestamp: float = 0

    # 过期时间 (信令5秒过期)
    expires_at: float = 0


class LightweightBroker:
    """
    轻量Broker服务

    功能:
    1. 卖家注册与心跳
    2. 商品指纹目录维护
    3. 信令转发 (SDP/ICE)
    4. 订单哈希锚定
    5. 穿透配置下发
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        turn_username: str = "",
        turn_credential: str = "",
    ):
        self.host = host
        self.port = port
        self.turn_username = turn_username
        self.turn_credential = turn_credential

        # 卖家记录
        self._sellers: Dict[str, SellerRecord] = {}
        self._peer_to_seller: Dict[str, str] = {}  # peer_id -> seller_id

        # 商品指纹索引 (listing_id -> seller_id)
        self._listing_index: Dict[str, str] = {}

        # 订单锚定
        self._order_anchors: Dict[str, OrderAnchor] = {}

        # 信令消息缓存 (用于转发)
        self._signaling_cache: Dict[str, SignalingMessage] = {}

        # WebSocket连接 (peer_id -> ws)
        self._ws_connections: Dict[str, web.WebSocketResponse] = {}

        # 应用
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

        # 回调
        self._on_seller_online: List[Callable] = []
        self._on_seller_offline: List[Callable] = []

        logger.info(f"[Broker] Initialized at {host}:{port}")

    # ==================== 卖家管理 ====================

    async def register_seller(
        self,
        seller_id: str,
        peer_id: str,
        listing_ids: List[str],
        connectivity_score: int = 50,
        nat_type: str = "unknown",
        turn_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """注册卖家"""
        seller = SellerRecord(
            seller_id=seller_id,
            peer_id=peer_id,
            connectivity_score=connectivity_score,
            nat_type=nat_type,
            listing_fingerprints=listing_ids,
            is_online=True,
            last_heartbeat=time.time(),
            turn_config=turn_config or {},
        )

        self._sellers[seller_id] = seller
        self._peer_to_seller[peer_id] = seller_id

        # 更新索引
        for lid in listing_ids:
            self._listing_index[lid] = seller_id

        logger.info(f"[Broker] Registered seller {seller_id} with {len(listing_ids)} listings")

        # 触发回调
        for cb in self._on_seller_online:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(seller_id, peer_id)
                else:
                    cb(seller_id, peer_id)
            except Exception as e:
                logger.error(f"[Broker] Seller online callback error: {e}")

        return {
            "success": True,
            "seller_id": seller_id,
            "relay_config": self._get_relay_config(peer_id),
        }

    async def unregister_seller(self, seller_id: str) -> bool:
        """注销卖家"""
        seller = self._sellers.get(seller_id)
        if not seller:
            return False

        # 清理索引
        for lid in seller.listing_fingerprints:
            if lid in self._listing_index:
                del self._listing_index[lid]

        # 清理peer映射
        if seller.peer_id in self._peer_to_seller:
            del self._peer_to_seller[seller.peer_id]

        # 关闭WebSocket
        if seller.peer_id in self._ws_connections:
            ws = self._ws_connections[seller.peer_id]
            await ws.close()
            del self._ws_connections[seller.peer_id]

        del self._sellers[seller_id]

        logger.info(f"[Broker] Unregistered seller {seller_id}")

        # 触发回调
        for cb in self._on_seller_offline:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(seller_id)
                else:
                    cb(seller_id)
            except Exception as e:
                logger.error(f"[Broker] Seller offline callback error: {e}")

        return True

    async def heartbeat(self, seller_id: str) -> bool:
        """卖家心跳"""
        seller = self._sellers.get(seller_id)
        if not seller:
            return False

        seller.last_heartbeat = time.time()
        return True

    def _get_relay_config(self, peer_id: str) -> Dict[str, Any]:
        """获取穿透配置"""
        config = {
            "turn_url": f"turn:{self.host}:{self.port + 1}",
            "turn_username": self.turn_username or peer_id,
            "turn_credential": self.turn_credential or str(uuid.uuid4()),
            "stun_url": f"stun:{self.host}:{self.port + 1}",
        }

        # 如果卖家有公网IP，提供直连配置
        seller_id = self._peer_to_seller.get(peer_id)
        if seller_id:
            seller = self._sellers.get(seller_id)
            if seller and seller.turn_config:
                config.update(seller.turn_config)

        return config

    # ==================== 目录服务 ====================

    def get_catalog(self, watched_sellers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        获取商品目录 (只返回指纹,不返回详情)

        Args:
            watched_sellers: 如果指定,只返回这些卖家的商品
        """
        result = []

        for seller_id, seller in self._sellers.items():
            if not seller.is_online:
                continue

            # 过滤
            if watched_sellers and seller_id not in watched_sellers:
                continue

            # 只返回指纹元数据
            for listing_id in seller.listing_fingerprints:
                result.append({
                    "listing_id": listing_id,
                    "seller_id": seller_id,
                    "seller_peer_id": seller.peer_id,
                    "connectivity_score": seller.connectivity_score,
                    "nat_type": seller.nat_type,
                })

        return result

    async def broadcast_fingerprints(
        self,
        seller_id: str,
        listing_ids: List[str],
    ) -> bool:
        """更新卖家的商品指纹"""
        seller = self._sellers.get(seller_id)
        if not seller:
            return False

        # 清理旧索引
        for lid in seller.listing_fingerprints:
            if lid in self._listing_index:
                del self._listing_index[lid]

        # 更新新索引
        seller.listing_fingerprints = listing_ids
        for lid in listing_ids:
            self._listing_index[lid] = seller_id

        logger.info(f"[Broker] Updated fingerprints for seller {seller_id}: {len(listing_ids)} listings")
        return True

    # ==================== 信令转发 ====================

    async def forward_signal(
        self,
        msg_type: str,
        session_id: str,
        from_peer_id: str,
        to_peer_id: str,
        payload: Dict[str, Any],
    ) -> bool:
        """转发信令消息"""
        # 缓存消息 (5秒过期)
        cache_key = f"{session_id}:{to_peer_id}"
        msg = SignalingMessage(
            msg_type=msg_type,
            session_id=session_id,
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            payload=payload,
            timestamp=time.time(),
            expires_at=time.time() + 5,
        )
        self._signaling_cache[cache_key] = msg

        # 如果目标在线,通过WebSocket发送
        if to_peer_id in self._ws_connections:
            ws = self._ws_connections[to_peer_id]
            try:
                await ws.send_json({
                    "type": "signal",
                    "msg_type": msg_type,
                    "session_id": session_id,
                    "from_peer_id": from_peer_id,
                    "payload": payload,
                })
                return True
            except Exception as e:
                logger.error(f"[Broker] Failed to forward signal: {e}")

        return False

    async def fetch_pending_signals(self, peer_id: str, session_id: str) -> List[Dict[str, Any]]:
        """获取待转发的信令消息"""
        result = []

        # 查找发给该peer的所有消息
        to_remove = []
        for key, msg in self._signaling_cache.items():
            if msg.to_peer_id == peer_id and msg.session_id == session_id:
                if time.time() < msg.expires_at:
                    result.append({
                        "msg_type": msg.msg_type,
                        "session_id": msg.session_id,
                        "from_peer_id": msg.from_peer_id,
                        "payload": msg.payload,
                    })
                to_remove.append(key)

        # 清理过期消息
        for key in to_remove:
            del self._signaling_cache[key]

        return result

    # ==================== 订单锚定 ====================

    async def anchor_order(
        self,
        order_id: str,
        order_hash: str,
        buyer_id: str,
        seller_id: str,
    ) -> OrderAnchor:
        """锚定订单哈希"""
        anchor = OrderAnchor(
            order_id=order_id,
            anchor_hash=order_hash,
            buyer_id=buyer_id,
            seller_id=seller_id,
            anchored_at=time.time(),
            expires_at=time.time() + 7 * 24 * 3600,  # 7天过期
        )

        self._order_anchors[order_id] = anchor

        logger.info(f"[Broker] Anchored order {order_id}: {order_hash[:16]}...")

        return anchor

    async def fetch_order_anchor(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单锚定信息"""
        anchor = self._order_anchors.get(order_id)
        if not anchor:
            return None

        if time.time() > anchor.expires_at:
            del self._order_anchors[order_id]
            return None

        return anchor.to_dict()

    async def update_order_status(self, order_id: str, status: str) -> bool:
        """更新订单状态"""
        anchor = self._order_anchors.get(order_id)
        if not anchor:
            return False

        anchor.status = status
        return True

    # ==================== WebSocket连接 ====================

    async def handle_ws_connection(self, ws: web.WebSocketResponse, peer_id: str) -> None:
        """处理WebSocket连接"""
        self._ws_connections[peer_id] = ws
        logger.info(f"[Broker] WebSocket connected: {peer_id}")

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(peer_id, data)

        except Exception as e:
            logger.error(f"[Broker] WebSocket error for {peer_id}: {e}")

        finally:
            if peer_id in self._ws_connections:
                del self._ws_connections[peer_id]

            # 检查是否需要下线卖家
            seller_id = self._peer_to_seller.get(peer_id)
            if seller_id:
                seller = self._sellers.get(seller_id)
                if seller and seller.peer_id == peer_id:
                    seller.is_online = False
                    for cb in self._on_seller_offline:
                        try:
                            if asyncio.iscoroutinefunction(cb):
                                await cb(seller_id)
                            else:
                                cb(seller_id)
                        except Exception as e:
                            logger.error(f"[Broker] Offline callback error: {e}")

            logger.info(f"[Broker] WebSocket disconnected: {peer_id}")

    async def _handle_ws_message(self, peer_id: str, data: Dict[str, Any]) -> None:
        """处理WebSocket消息"""
        msg_type = data.get("type")

        if msg_type == "heartbeat":
            seller_id = self._peer_to_seller.get(peer_id)
            if seller_id:
                await self.heartbeat(seller_id)

        elif msg_type == "signal":
            to_peer = data.get("to_peer_id")
            await self.forward_signal(
                msg_type=data.get("msg_type"),
                session_id=data.get("session_id"),
                from_peer_id=peer_id,
                to_peer_id=to_peer,
                payload=data.get("payload", {}),
            )

    # ==================== HTTP API ====================

    def create_app(self) -> web.Application:
        """创建aiohttp应用"""
        app = web.Application()

        # 健康检查
        app.router.add_get("/health", self._handle_health)

        # 卖家注册
        app.router.add_post("/api/sellers/register", self._handle_register_seller)
        app.router.add_post("/api/sellers/unregister", self._handle_unregister_seller)
        app.router.add_post("/api/heartbeat", self._handle_heartbeat)

        # 目录
        app.router.add_get("/api/catalog", self._handle_catalog)
        app.router.add_post("/api/fingerprints/broadcast", self._handle_broadcast_fingerprints)

        # 信令
        app.router.add_post("/api/signal", self._handle_signal)
        app.router.add_post("/api/signal/ice", self._handle_signal_ice)
        app.router.add_get("/api/signal/pending/{peer_id}", self._handle_fetch_pending_signals)

        # 订单锚定
        app.router.add_post("/api/orders/anchor", self._handle_anchor_order)
        app.router.add_get("/api/orders/anchor/{order_id}", self._handle_fetch_order_anchor)
        app.router.add_post("/api/orders/status", self._handle_update_order_status)

        # 穿透配置
        app.router.add_get("/api/relay/config/{peer_id}", self._handle_relay_config)

        # WebSocket
        app.router.add_get("/ws", self._handle_ws)

        self._app = app
        return app

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "timestamp": time.time()})

    async def _handle_register_seller(self, request: web.Request) -> web.Response:
        data = await request.json()
        result = await self.register_seller(
            seller_id=data["seller_id"],
            peer_id=data["peer_id"],
            listing_ids=data.get("listing_ids", []),
            connectivity_score=data.get("connectivity_score", 50),
            nat_type=data.get("nat_type", "unknown"),
            turn_config=data.get("turn_config"),
        )
        return web.json_response(result)

    async def _handle_unregister_seller(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.unregister_seller(data["seller_id"])
        return web.json_response({"success": success})

    async def _handle_heartbeat(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.heartbeat(data["seller_id"])
        return web.json_response({"success": success})

    async def _handle_catalog(self, request: web.Request) -> web.Response:
        watched = request.query.get("watched", "")
        watched_list = watched.split(",") if watched else None
        catalog = self.get_catalog(watched_list)
        return web.json_response({"fingerprints": catalog})

    async def _handle_broadcast_fingerprints(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.broadcast_fingerprints(
            seller_id=data["seller_id"],
            listing_ids=data["listing_ids"],
        )
        return web.json_response({"success": success})

    async def _handle_signal(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.forward_signal(
            msg_type=data["type"],
            session_id=data["session_id"],
            from_peer_id=data["from"],
            to_peer_id=data["to"],
            payload={"sdp": data.get("sdp")},
        )
        return web.json_response({"success": success})

    async def _handle_signal_ice(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.forward_signal(
            msg_type="ice_candidate",
            session_id=data["session_id"],
            from_peer_id=data["from"],
            to_peer_id=data["to"],
            payload={"candidate": data.get("candidate")},
        )
        return web.json_response({"success": success})

    async def _handle_fetch_pending_signals(self, request: web.Request) -> web.Response:
        peer_id = request.match_info["peer_id"]
        session_id = request.query.get("session_id", "")
        signals = await self.fetch_pending_signals(peer_id, session_id)
        return web.json_response({"signals": signals})

    async def _handle_anchor_order(self, request: web.Request) -> web.Response:
        data = await request.json()
        anchor = await self.anchor_order(
            order_id=data["order_id"],
            order_hash=data["order_hash"],
            buyer_id=data["buyer_id"],
            seller_id=data["seller_id"],
        )
        return web.json_response(anchor.to_dict())

    async def _handle_fetch_order_anchor(self, request: web.Request) -> web.Response:
        order_id = request.match_info["order_id"]
        anchor = await self.fetch_order_anchor(order_id)
        if anchor:
            return web.json_response(anchor)
        return web.json_response({"error": "not found"}, status=404)

    async def _handle_update_order_status(self, request: web.Request) -> web.Response:
        data = await request.json()
        success = await self.update_order_status(data["order_id"], data["status"])
        return web.json_response({"success": success})

    async def _handle_relay_config(self, request: web.Request) -> web.Response:
        peer_id = request.match_info["peer_id"]
        config = self._get_relay_config(peer_id)
        return web.json_response(config)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        peer_id = request.query.get("peer_id", str(uuid.uuid4()))
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await self.handle_ws_connection(ws, peer_id)
        return ws

    # ==================== 启动/停止 ====================

    async def start(self) -> None:
        """启动Broker服务"""
        if self._app is None:
            self.create_app()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        logger.info(f"[Broker] Started at {self.host}:{self.port}")

    async def stop(self) -> None:
        """停止Broker服务"""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        logger.info("[Broker] Stopped")

    # ==================== 回调 ====================

    def on_seller_online(self, callback: Callable) -> None:
        """监听卖家上线"""
        self._on_seller_online.append(callback)

    def on_seller_offline(self, callback: Callable) -> None:
        """监听卖家下线"""
        self._on_seller_offline.append(callback)

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        online_sellers = sum(1 for s in self._sellers.values() if s.is_online)
        total_listings = sum(len(s.listing_fingerprints) for s in self._sellers.values())

        return {
            "total_sellers": len(self._sellers),
            "online_sellers": online_sellers,
            "total_listings": total_listings,
            "active_listings": len(self._listing_index),
            "order_anchors": len(self._order_anchors),
            "ws_connections": len(self._ws_connections),
        }


# ==================== 全局Broker实例 ====================

_broker: Optional[LightweightBroker] = None


async def start_broker(
    host: str = "0.0.0.0",
    port: int = 8765,
    turn_username: str = "",
    turn_credential: str = "",
) -> LightweightBroker:
    """启动Broker服务"""
    global _broker
    _broker = LightweightBroker(
        host=host,
        port=port,
        turn_username=turn_username,
        turn_credential=turn_credential,
    )
    await _broker.start()
    return _broker


async def stop_broker() -> None:
    """停止Broker服务"""
    global _broker
    if _broker:
        await _broker.stop()
        _broker = None


def get_broker() -> Optional[LightweightBroker]:
    """获取Broker实例"""
    return _broker
