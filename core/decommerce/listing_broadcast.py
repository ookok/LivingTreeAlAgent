"""
P2P 去中心化电商 - 商品广播注册
Listing Broadcast & Discovery Protocol

卖家不把商品传到云端，而是存在本地，通过穿透网络广播"我有什么"。
Broker只转发元数据，不建商品库，数据在卖买双方。

核心流程:
1. 卖家本地生成商品哈希指纹
2. 通过Broker广播给附近/关注买家
3. 买家按需通过P2P拉取详情
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import hashlib
import json

logger = logging.getLogger(__name__)


class BroadcastType(Enum):
    """广播类型"""
    NEW_LISTING = "new_listing"           # 新商品
    UPDATE_LISTING = "update_listing"     # 商品更新
    REMOVE_LISTING = "remove_listing"     # 商品下架
    SELLER_ONLINE = "seller_online"       # 卖家上线
    SELLER_OFFLINE = "seller_offline"     # 卖家下线
    HEARTBEAT = "heartbeat"               # 心跳


@dataclass
class ListingFingerprint:
    """商品哈希指纹 (不上传到云端)"""
    listing_id: str = ""
    seller_peer_id: str = ""

    # 哈希指纹 (内容的脱敏摘要)
    content_hash: str = ""        # 商品内容的SHA256
    title_hash: str = ""          # 标题的SHA256 (用于搜索匹配)
    price_hash: str = ""          # 价格信息哈希

    # 预览信息 (可选, 用于搜索结果展示)
    preview_title: str = ""       # 脱敏后的标题
    preview_price: str = ""       # 脱敏后的价格
    preview_category: str = ""    # 分类

    # P2P穿透信息
    p2p_hint: Dict[str, Any] = field(default_factory=dict)  # STUN/TURN可达地址
    relay_config: Dict[str, Any] = field(default_factory=dict)  # 中继配置

    # 时间戳
    timestamp: float = 0
    expires_at: float = 0         # 过期时间

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "seller_peer_id": self.seller_peer_id,
            "content_hash": self.content_hash,
            "title_hash": self.title_hash,
            "price_hash": self.price_hash,
            "preview_title": self.preview_title,
            "preview_price": self.preview_price,
            "preview_category": self.preview_category,
            "p2p_hint": self.p2p_hint,
            "relay_config": self.relay_config,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
        }


@dataclass
class FullListing:
    """完整商品信息 (按需从卖家P2P拉取)"""
    listing_id: str = ""
    seller_peer_id: str = ""

    # 完整内容
    title: str = ""
    description: str = ""
    price: int = 0  # 分
    currency: str = "CNY"

    # 服务类型
    service_type: str = "physical_product"
    delivery_type: str = "instant"  # instant | scheduled | live | download

    # 媒体信息
    thumbnail_url: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)

    # AI服务特定
    ai_model: Optional[str] = None
    ai_capabilities: List[str] = field(default_factory=list)

    # 实时可用性
    is_live_available: bool = False
    max_concurrent: int = 1

    # 验证
    content_hash: str = ""  # 内容哈希

    # 时间戳
    created_at: float = 0
    updated_at: float = 0

    def compute_fingerlogger.info(self) -> ListingFingerprint:
        """计算商品指纹"""
        content = f"{self.listing_id}|{self.title}|{self.description}|{self.price}|{self.service_type}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        title_hash = hashlib.sha256(self.title.encode()).hexdigest()
        price_hash = hashlib.sha256(f"{self.price}|{self.currency}".encode()).hexdigest()

        return ListingFingerlogger.info(
            listing_id=self.listing_id,
            seller_peer_id=self.seller_peer_id,
            content_hash=content_hash,
            title_hash=title_hash,
            price_hash=price_hash,
            preview_title=self._anonymize_title(self.title),
            preview_price=f"{self.price/100:.2f}元" if self.currency == "CNY" else f"{self.price/100:.2f}",
            preview_category=self.service_type,
            timestamp=time.time(),
            expires_at=time.time() + 3600,  # 1小时过期
        )

    def _anonymize_title(self, title: str) -> str:
        """脱敏标题 (只显示前20字符)"""
        if len(title) <= 20:
            return title
        return title[:20] + "..."

    def verify_hash(self) -> bool:
        """验证内容哈希"""
        content = f"{self.listing_id}|{self.title}|{self.description}|{self.price}|{self.service_type}"
        computed = hashlib.sha256(content.encode()).hexdigest()
        return computed == self.content_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "seller_peer_id": self.seller_peer_id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "service_type": self.service_type,
            "delivery_type": self.delivery_type,
            "thumbnail_url": self.thumbnail_url,
            "media_urls": self.media_urls,
            "ai_model": self.ai_model,
            "ai_capabilities": self.ai_capabilities,
            "is_live_available": self.is_live_available,
            "max_concurrent": self.max_concurrent,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ListingBroadcast:
    """
    商品广播注册表 (本地)

    卖家端使用，管理本地商品广播
    """

    def __init__(self, peer_id: str):
        self.peer_id = peer_id

        # 本地商品存储
        self._listings: Dict[str, FullListing] = {}

        # 活跃广播的商品指纹
        self._active_fingerprints: Dict[str, ListingFingerprint] = {}

        # 广播回调
        self._on_broadcast: List[Callable] = []

    def register_listing(self, listing: FullListing) -> ListingFingerprint:
        """注册商品并生成广播指纹"""
        listing.seller_peer_id = self.peer_id
        listing.content_hash = hashlib.sha256(
            f"{listing.listing_id}|{listing.title}|{listing.description}|{listing.price}|{listing.service_type}".encode()
        ).hexdigest()
        listing.created_at = time.time()
        listing.updated_at = time.time()

        self._listings[listing.listing_id] = listing

        # 生成指纹
        fingerprint = listing.compute_fingerprint()
        self._active_fingerprints[listing.listing_id] = fingerprint

        logger.info(f"[ListingBroadcast] Registered listing {listing.listing_id}")
        return fingerprint

    def update_listing(self, listing_id: str, **updates) -> Optional[ListingFingerprint]:
        """更新商品"""
        listing = self._listings.get(listing_id)
        if not listing:
            return None

        # 更新字段
        for key, value in updates.items():
            if hasattr(listing, key):
                setattr(listing, key, value)

        listing.updated_at = time.time()

        # 重新生成指纹
        fingerprint = listing.compute_fingerprint()
        self._active_fingerprints[listing_id] = fingerprint

        return fingerprint

    def remove_listing(self, listing_id: str) -> bool:
        """下架商品"""
        if listing_id in self._listings:
            del self._listings[listing_id]

        if listing_id in self._active_fingerprints:
            del self._active_fingerprints[listing_id]

        logger.info(f"[ListingBroadcast] Removed listing {listing_id}")
        return True

    def get_listing(self, listing_id: str) -> Optional[FullListing]:
        """获取完整商品信息"""
        return self._listings.get(listing_id)

    def get_fingerprints(self) -> List[ListingFingerprint]:
        """获取所有活跃广播的商品指纹"""
        result = []
        for fp in self._active_fingerprints.values():
            if not fp.is_expired():
                result.append(fp)
        return result

    def get_public_fingerprints(self) -> List[Dict[str, Any]]:
        """获取公开广播的商品指纹 (不含P2P穿透信息)"""
        result = []
        for fp in self._active_fingerprints.values():
            if not fp.is_expired():
                result.append({
                    "listing_id": fp.listing_id,
                    "preview_title": fp.preview_title,
                    "preview_price": fp.preview_price,
                    "preview_category": fp.preview_category,
                    "timestamp": fp.timestamp,
                })
        return result

    def refresh_fingerprints(self) -> None:
        """刷新所有指纹 (延长过期时间)"""
        now = time.time()
        for fp in self._active_fingerprints.values():
            fp.timestamp = now
            fp.expires_at = now + 3600

    def set_p2p_hint(self, listing_id: str, p2p_hint: Dict[str, Any]) -> bool:
        """设置P2P穿透信息"""
        fp = self._active_fingerprints.get(listing_id)
        if fp:
            fp.p2p_hint = p2p_hint
            return True
        return False

    def set_relay_config(self, listing_id: str, relay_config: Dict[str, Any]) -> bool:
        """设置中继配置"""
        fp = self._active_fingerprints.get(listing_id)
        if fp:
            fp.relay_config = relay_config
            return True
        return False

    def on_broadcast(self, callback: Callable) -> None:
        """监听广播事件"""
        self._on_broadcast.append(callback)

    async def broadcast(self, broadcast_type: BroadcastType, listing_id: str = "") -> None:
        """触发广播"""
        fingerprints = self.get_fingerprints()
        payload = {
            "type": broadcast_type.value,
            "peer_id": self.peer_id,
            "listing_id": listing_id,
            "fingerprints": [fp.to_dict() for fp in fingerprints],
            "timestamp": time.time(),
        }

        for cb in self._on_broadcast:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(payload)
                else:
                    cb(payload)
            except Exception as e:
                logger.error(f"[ListingBroadcast] Broadcast callback error: {e}")


class ListingDiscovery:
    """
    商品发现客户端 (买家端)

    从Broker获取商品指纹列表，按需从卖家拉取详情
    """

    def __init__(self, peer_id: str, broker_url: str = ""):
        self.peer_id = peer_id
        self.broker_url = broker_url

        # 缓存的商品指纹
        self._fingerprint_cache: Dict[str, ListingFingerprint] = {}

        # 缓存的完整商品信息 (按需拉取)
        self._full_listings: Dict[str, FullListing] = {}

        # 关注列表
        self._watched_sellers: List[str] = []

        # 搜索结果
        self._search_results: List[ListingFingerprint] = []

        # 回调
        self._on_new_listing: List[Callable] = []
        self._on_seller_online: List[Callable] = []
        self._on_seller_offline: List[Callable] = []

    async def refresh_catalog(self) -> List[Dict[str, Any]]:
        """从Broker刷新商品目录"""
        if not self.broker_url:
            return []

        try:
            import aiohttp
from core.logger import get_logger
logger = get_logger('decommerce.listing_broadcast')

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.broker_url}/api/catalog",
                    params={"watched": ",".join(self._watched_sellers)},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fingerprints = []
                        for item in data.get("fingerprints", []):
                            fp = ListingFingerlogger.info(**item)
                            self._fingerprint_cache[fp.listing_id] = fp
                            fingerprints.append(fp)

                        logger.info(f"[ListingDiscovery] Refreshed {len(fingerprints)} fingerprints")
                        return fingerprints

        except Exception as e:
            logger.error(f"[ListingDiscovery] Failed to refresh catalog: {e}")

        return []

    async def search(self, query: str) -> List[ListingFingerprint]:
        """搜索商品 (基于指纹匹配)"""
        query_lower = query.lower()
        results = []

        for fp in self._fingerprint_cache.values():
            if fp.is_expired():
                continue

            # 标题匹配
            if query_lower in fp.preview_title.lower():
                results.append(fp)
                continue

            # 分类匹配
            if query_lower in fp.preview_category.lower():
                results.append(fp)

        self._search_results = results
        return results

    async def fetch_full_listing(self, listing_id: str, seller_peer_id: str) -> Optional[FullListing]:
        """从卖家P2P拉取完整商品信息"""
        # 先检查缓存
        if listing_id in self._full_listings:
            return self._full_listings[listing_id]

        fp = self._fingerprint_cache.get(listing_id)
        if not fp:
            logger.warning(f"[ListingDiscovery] Fingerprint not found for {listing_id}")
            return None

        # 通过P2P或中继获取完整信息
        try:
            # 尝试通过中继获取
            if fp.relay_config:
                listing = await self._fetch_via_relay(fp)
                if listing:
                    self._full_listings[listing_id] = listing
                    return listing

        except Exception as e:
            logger.error(f"[ListingDiscovery] Failed to fetch listing {listing_id}: {e}")

        return None

    async def _fetch_via_relay(self, fp: ListingFingerprint) -> Optional[FullListing]:
        """通过中继获取完整商品信息"""
        # TODO: 实现P2P拉取逻辑
        # 这里应该通过WebRTC DataChannel或HTTP请求从卖家获取
        return None

    def get_fingerlogger.info(self, listing_id: str) -> Optional[ListingFingerprint]:
        """获取商品指纹"""
        return self._fingerprint_cache.get(listing_id)

    def get_all_fingerprints(self) -> List[ListingFingerprint]:
        """获取所有缓存的指纹"""
        return [fp for fp in self._fingerprint_cache.values() if not fp.is_expired()]

    def get_watched_sellers(self) -> List[str]:
        """获取关注的卖家列表"""
        return self._watched_sellers.copy()

    def add_watched_seller(self, seller_peer_id: str) -> None:
        """添加关注的卖家"""
        if seller_peer_id not in self._watched_sellers:
            self._watched_sellers.append(seller_peer_id)

    def remove_watched_seller(self, seller_peer_id: str) -> None:
        """移除关注的卖家"""
        if seller_peer_id in self._watched_sellers:
            self._watched_sellers.remove(seller_peer_id)

    def on_new_listing(self, callback: Callable) -> None:
        """监听新商品"""
        self._on_new_listing.append(callback)

    def on_seller_online(self, callback: Callable) -> None:
        """监听卖家上线"""
        self._on_seller_online.append(callback)

    def on_seller_offline(self, callback: Callable) -> None:
        """监听卖家下线"""
        self._on_seller_offline.append(callback)


# ==================== 工具函数 ====================

def compute_listing_hash(listing_data: Dict[str, Any]) -> str:
    """计算商品数据的哈希"""
    content = json.dumps(listing_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def create_listing_fingerlogger.info(
    listing_id: str,
    seller_peer_id: str,
    title: str,
    price: int,
    service_type: str,
    p2p_hint: Optional[Dict[str, Any]] = None,
    relay_config: Optional[Dict[str, Any]] = None,
) -> ListingFingerprint:
    """创建商品指纹的快捷函数"""
    content = f"{listing_id}|{title}|{price}|{service_type}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    title_hash = hashlib.sha256(title.encode()).hexdigest()
    price_hash = hashlib.sha256(f"{price}".encode()).hexdigest()

    return ListingFingerlogger.info(
        listing_id=listing_id,
        seller_peer_id=seller_peer_id,
        content_hash=content_hash,
        title_hash=title_hash,
        price_hash=price_hash,
        preview_title=title[:20] + "..." if len(title) > 20 else title,
        preview_price=f"{price/100:.2f}元",
        preview_category=service_type,
        p2p_hint=p2p_hint or {},
        relay_config=relay_config or {},
        timestamp=time.time(),
        expires_at=time.time() + 3600,
    )
