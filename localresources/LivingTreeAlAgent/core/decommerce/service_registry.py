"""
P2P 去中心化电商 - 服务注册与发现
DeCommerce Service Registry

负责商品/服务的发布、发现、管理
"""

from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import hashlib

from .models import (
    ServiceListing, ServiceType, ServiceStatus,
    Seller, P2PEndpoint, ConnectionQuality
)
from .services import (
    get_handler_registry,
    RemoteLiveViewHandler,
    AIComputingHandler,
    RemoteAssistHandler,
    KnowledgeConsultHandler,
)

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    服务注册中心

    功能:
    - 发布商品/服务
    - 发现在线服务
    - 管理卖家状态
    - 连接质量评估
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # 本地存储
        self._listings: Dict[str, ServiceListing] = {}  # listing_id -> ServiceListing
        self._sellers: Dict[str, Seller] = {}  # seller_id -> Seller
        self._sessions: Dict[str, Any] = {}  # session_id -> Session

        # 事件回调
        self._on_listing_updated: List[Callable] = []
        self._on_seller_status_changed: List[Callable] = []
        self._on_session_started: List[Callable] = []
        self._on_session_ended: List[Callable] = []

        # 初始化服务处理器
        self._init_handlers()

    def _init_handlers(self) -> None:
        """初始化服务处理器"""
        registry = get_handler_registry()

        # 注册所有处理器
        registry.register("remote_live_view", RemoteLiveViewHandler())
        registry.register("ai_computing", AIComputingHandler())
        registry.register("remote_assist", RemoteAssistHandler())
        registry.register("knowledge_consult", KnowledgeConsultHandler())

        logger.info("[ServiceRegistry] Initialized service handlers")

    # ==================== 卖家管理 ====================

    async def register_seller(
        self,
        user_id: str,
        name: str,
        endpoint: Optional[P2PEndpoint] = None,
        ai_models: Optional[List[str]] = None,
        **kwargs
    ) -> Seller:
        """注册卖家"""
        seller = Seller(
            user_id=user_id,
            name=name,
            endpoint=endpoint,
            ai_models=ai_models or [],
            has_ai_service=len(ai_models or []) > 0,
        )

        self._sellers[seller.id] = seller
        logger.info(f"[ServiceRegistry] Registered seller: {seller.id} ({name})")

        return seller

    async def update_seller_status(
        self,
        seller_id: str,
        is_online: bool,
        endpoint: Optional[P2PEndpoint] = None
    ) -> bool:
        """更新卖家状态"""
        seller = self._sellers.get(seller_id)
        if not seller:
            return False

        seller.is_online = is_online
        seller.last_seen_at = time.time()

        if endpoint:
            seller.endpoint = endpoint
            seller.connectivity = self._assess_connectivity(endpoint)

        # 触发回调
        for cb in self._on_seller_status_changed:
            asyncio.create_task(self._safe_call(cb, seller_id, is_online))

        return True

    async def get_seller(self, seller_id: str) -> Optional[Seller]:
        """获取卖家信息"""
        return self._sellers.get(seller_id)

    async def get_online_sellers(self) -> List[Seller]:
        """获取在线卖家列表"""
        return [s for s in self._sellers.values() if s.is_online]

    def _assess_connectivity(self, endpoint: P2PEndpoint) -> ConnectionQuality:
        """评估连接质量"""
        if not endpoint.public_ip:
            return ConnectionQuality.POOR

        if endpoint.quality_score >= 90:
            return ConnectionQuality.EXCELLENT
        elif endpoint.quality_score >= 70:
            return ConnectionQuality.GOOD
        elif endpoint.quality_score >= 50:
            return ConnectionQuality.FAIR
        else:
            return ConnectionQuality.POOR

    # ==================== 商品管理 ====================

    async def publish_listing(
        self,
        seller_id: str,
        title: str,
        description: str,
        price: int,  # 分
        service_type: ServiceType,
        delivery_type: str = "instant",
        endpoint: Optional[P2PEndpoint] = None,
        ai_model: Optional[str] = None,
        ai_capabilities: Optional[List[str]] = None,
        thumbnail_url: Optional[str] = None,
        **kwargs
    ) -> ServiceListing:
        """发布商品/服务"""
        seller = self._sellers.get(seller_id)
        if not seller:
            raise ValueError(f"Seller {seller_id} not found")

        # 检查是否支持该类型服务
        if service_type != ServiceType.PHYSICAL_PRODUCT and service_type != ServiceType.DIGITAL_PRODUCT:
            if not endpoint and not seller.endpoint:
                raise ValueError(f"Service type {service_type} requires P2P endpoint")

        # 评估实时可用性
        is_live_available = False
        if service_type != ServiceType.PHYSICAL_PRODUCT and service_type != ServiceType.DIGITAL_PRODUCT:
            ep = endpoint or seller.endpoint
            is_live_available = ep is not None and ep.quality_score >= 50

        listing = ServiceListing(
            seller_id=seller_id,
            title=title,
            description=description,
            price=price,
            service_type=service_type,
            delivery_type=delivery_type,
            endpoint=endpoint or seller.endpoint,
            ai_model=ai_model,
            ai_capabilities=ai_capabilities or [],
            is_live_available=is_live_available,
            status=ServiceStatus.ONLINE,
            thumbnail_url=thumbnail_url,
        )

        self._listings[listing.id] = listing

        # 更新卖家统计
        seller.total_services += 1

        logger.info(f"[ServiceRegistry] Published listing: {listing.id} ({title})")

        # 触发回调
        for cb in self._on_listing_updated:
            asyncio.create_task(self._safe_call(cb, listing))

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

        # 更新字段
        allowed = ["title", "description", "price", "status", "thumbnail_url", "is_live_available"]
        for key, value in updates.items():
            if key in allowed and hasattr(listing, key):
                setattr(listing, key, value)

        listing.updated_at = time.time()

        # 触发回调
        for cb in self._on_listing_updated:
            asyncio.create_task(self._safe_call(cb, listing))

        return listing

    async def unpublish_listing(self, listing_id: str) -> bool:
        """下架商品/服务"""
        listing = self._listings.get(listing_id)
        if not listing:
            return False

        listing.status = ServiceStatus.OFFLINE
        listing.updated_at = time.time()

        logger.info(f"[ServiceRegistry] Unpublished listing: {listing_id}")

        return True

    async def get_listing(self, listing_id: str) -> Optional[ServiceListing]:
        """获取商品/服务"""
        return self._listings.get(listing_id)

    async def get_seller_listings(self, seller_id: str) -> List[ServiceListing]:
        """获取卖家的所有商品"""
        return [
            l for l in self._listings.values()
            if l.seller_id == seller_id and l.status == ServiceStatus.ONLINE
        ]

    async def search_listings(
        self,
        query: str = "",
        service_type: Optional[ServiceType] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        live_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ServiceListing]:
        """
        搜索商品/服务

        Args:
            query: 搜索关键词
            service_type: 服务类型过滤
            min_price: 最低价格(分)
            max_price: 最高价格(分)
            live_only: 仅返回实时可用的服务
            limit: 返回数量限制
            offset: 偏移量
        """
        results = []

        for listing in self._listings.values():
            # 状态过滤
            if listing.status != ServiceStatus.ONLINE:
                continue

            # 类型过滤
            if service_type and listing.service_type != service_type:
                continue

            # 价格过滤
            if min_price is not None and listing.price < min_price:
                continue
            if max_price is not None and listing.price > max_price:
                continue

            # 实时可用过滤
            if live_only and not listing.is_live_available:
                continue

            # 关键词过滤
            if query:
                q_lower = query.lower()
                if q_lower not in listing.title.lower() and q_lower not in listing.description.lower():
                    continue

            results.append(listing)

        # 按更新时间排序
        results.sort(key=lambda x: x.updated_at, reverse=True)

        # 分页
        return results[offset:offset + limit]

    # ==================== 会话管理 ====================

    async def create_session(
        self,
        listing_id: str,
        buyer_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """创建服务会话"""
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")

        if listing.status != ServiceStatus.ONLINE:
            raise ValueError(f"Listing {listing_id} is not available")

        # 获取对应处理器
        registry = get_handler_registry()
        handler_type = self._service_type_to_handler(listing.service_type)
        handler = registry.get(handler_type)

        if not handler:
            raise ValueError(f"No handler for service type: {listing.service_type}")

        # 创建会话
        session_id = await handler.create_session(
            listing_id=listing_id,
            seller_id=listing.seller_id,
            buyer_id=buyer_id,
            **kwargs
        )

        session_data = {
            "session_id": session_id,
            "listing_id": listing_id,
            "seller_id": listing.seller_id,
            "buyer_id": buyer_id,
            "handler_type": handler_type,
            "created_at": time.time(),
        }

        self._sessions[session_id] = session_data

        # 更新订单数
        listing.order_count += 1

        logger.info(f"[ServiceRegistry] Created session: {session_id}")

        # 触发回调
        for cb in self._on_session_started:
            asyncio.create_task(self._safe_call(cb, session_data))

        return session_data

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """加入服务会话"""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        registry = get_handler_registry()
        handler = registry.get(session["handler_type"])

        if not handler:
            raise ValueError(f"Handler {session['handler_type']} not found")

        return await handler.join_session(session_id, user_id, **kwargs)

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """结束服务会话"""
        session = self._sessions.get(session_id)
        if not session:
            return {}

        registry = get_handler_registry()
        handler = registry.get(session["handler_type"])

        result = {}
        if handler:
            result = await handler.end_session(session_id)

        del self._sessions[session_id]

        logger.info(f"[ServiceRegistry] Ended session: {session_id}")

        # 触发回调
        for cb in self._on_session_ended:
            asyncio.create_task(self._safe_call(cb, session_id, result))

        return result

    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """处理会话心跳"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        registry = get_handler_registry()
        handler = registry.get(session["handler_type"])

        if handler:
            return await handler.handle_heartbeat(session_id, user_id)

        return False

    # ==================== 事件回调 ====================

    def on_listing_updated(self, callback: Callable) -> None:
        """监听商品更新"""
        self._on_listing_updated.append(callback)

    def on_seller_status_changed(self, callback: Callable) -> None:
        """监听卖家状态变化"""
        self._on_seller_status_changed.append(callback)

    def on_session_started(self, callback: Callable) -> None:
        """监听会话开始"""
        self._on_session_started.append(callback)

    def on_session_ended(self, callback: Callable) -> None:
        """监听会话结束"""
        self._on_session_ended.append(callback)

    async def _safe_call(self, callback: Callable, *args, **kwargs) -> None:
        """安全调用回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"[ServiceRegistry] Callback error: {e}")

    # ==================== 工具方法 ====================

    def _service_type_to_handler(self, service_type: ServiceType) -> str:
        """服务类型转处理器类型"""
        mapping = {
            ServiceType.REMOTE_LIVE_VIEW: "remote_live_view",
            ServiceType.AI_COMPUTING: "ai_computing",
            ServiceType.REMOTE_ASSIST: "remote_assist",
            ServiceType.KNOWLEDGE_CONSULT: "knowledge_consult",
        }
        return mapping.get(service_type, "remote_live_view")

    def get_handler_registry(self):
        """获取处理器注册表"""
        return get_handler_registry()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_listings": len(self._listings),
            "online_listings": sum(1 for l in self._listings.values() if l.status == ServiceStatus.ONLINE),
            "live_available": sum(1 for l in self._listings.values() if l.is_live_available),
            "total_sellers": len(self._sellers),
            "online_sellers": sum(1 for s in self._sellers.values() if s.is_online),
            "active_sessions": len(self._sessions),
        }


# 全局单例
_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """获取服务注册中心单例"""
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry