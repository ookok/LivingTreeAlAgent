"""
统一商品/服务列表模型

合并自:
- local_market/models.py Product + ProductImage + ProductIndex
- decommerce/models.py ServiceListing + P2PEndpoint
- flash_listing/models.py GeneratedListing + ImageFeature + ProductLink
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json
import hashlib

from .enums import (
    ListingCategory, ListingStatus, ProductCondition,
    DeliveryMethod, PaymentMethod
)
from .location import GeoLocation


# ============================================================================
# 媒体
# ============================================================================

@dataclass
class ListingImage:
    """商品图片"""
    url: str = ""
    ipfs_hash: str = ""
    thumbnail: str = ""
    order: int = 0
    width: int = 0
    height: int = 0
    format: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "ipfs_hash": self.ipfs_hash,
            "thumbnail": self.thumbnail,
            "order": self.order,
            "width": self.width,
            "height": self.height,
            "format": self.format,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ListingImage:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ImageFeature:
    """AI视觉提取特征（来自 flash_listing）"""
    feature_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    category: str = ""
    category_confidence: float = 0.0
    material: Optional[str] = None
    size_estimate: Optional[str] = None
    interface_type: Optional[str] = None
    application: Optional[str] = None
    ocr_text: Optional[str] = None
    model_number: Optional[str] = None
    power_rating: Optional[str] = None
    voltage: Optional[str] = None
    original_image_path: str = ""
    thumbnail_path: Optional[str] = None
    feature_vector: Optional[List[float]] = None
    width: int = 0
    height: int = 0
    format: str = ""

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "category": self.category,
            "category_confidence": self.category_confidence,
            "material": self.material,
            "size_estimate": self.size_estimate,
            "interface_type": self.interface_type,
            "application": self.application,
            "ocr_text": self.ocr_text,
            "model_number": self.model_number,
            "power_rating": self.power_rating,
            "voltage": self.voltage,
            "original_image_path": self.original_image_path,
            "thumbnail_path": self.thumbnail_path,
            "width": self.width,
            "height": self.height,
            "format": self.format,
        }


# ============================================================================
# P2P 端点（来自 decommerce）
# ============================================================================

@dataclass
class P2PEndpoint:
    """P2P连接端点"""
    type: str = "webrtc"
    ice_servers: List[Dict[str, Any]] = field(default_factory=list)
    public_ip: Optional[str] = None
    nat_type: Optional[str] = None
    turn_url: Optional[str] = None
    turn_username: Optional[str] = None
    turn_credential: Optional[str] = None
    quality_score: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "ice_servers": self.ice_servers,
            "public_ip": self.public_ip,
            "nat_type": self.nat_type,
            "turn_url": self.turn_url,
            "turn_username": self.turn_username,
            "turn_credential": self.turn_credential,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> P2PEndpoint:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# 商品标签（来自 flash_listing ProductLink）
# ============================================================================

@dataclass
class ListingLink:
    """商品伪域名标签"""
    link_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    full_link: str = ""
    short_code: str = ""
    qr_code_data: Optional[str] = None
    node_id: str = ""
    seller_id: str = ""
    listing_id: str = ""
    click_count: int = 0
    view_count: int = 0
    is_active: bool = True
    is_blacklisted: bool = False
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None

    @property
    def clickable_link(self) -> str:
        return f"product.{self.node_id}.tree/{self.short_code}"


# ============================================================================
# 统一 Listing
# ============================================================================

@dataclass
class Listing:
    """统一商品/服务列表
    
    合并 Product + ServiceListing + GeneratedListing。
    通过 feature_flags 区分不同类型：
    - is_physical: 实物商品（Product）
    - is_service: P2P服务（ServiceListing）
    - is_ai_service: AI计算服务
    - is_live: 实时流服务
    - is_digital: 数字商品
    - is_flash: 闪电上架（AI生成）
    """
    listing_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    seller_id: str = ""

    # --- 基础信息 ---
    title: str = ""
    description: str = ""
    category: ListingCategory = ListingCategory.OTHER
    tags: List[str] = field(default_factory=list)
    key_attributes: Dict[str, str] = field(default_factory=dict)

    # --- 价格 ---
    price: float = 0.0
    price_unit: str = "CNY"
    negotiable: bool = True
    quantity: int = 1

    # --- 商品属性 ---
    condition: ProductCondition = ProductCondition.NEW

    # --- 媒体 ---
    images: List[ListingImage] = field(default_factory=list)
    media_urls: List[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None

    # --- 交付 ---
    delivery_methods: List[DeliveryMethod] = field(default_factory=list)
    delivery_range: float = 5.0

    # --- 支付 ---
    payment_methods: List[PaymentMethod] = field(default_factory=list)

    # --- 位置 ---
    location: Optional[GeoLocation] = None

    # --- P2P 连接（服务类商品）---
    endpoint: Optional[P2PEndpoint] = None

    # --- AI 服务 ---
    ai_model: Optional[str] = None
    ai_capabilities: List[str] = field(default_factory=list)
    is_live_available: bool = False
    max_concurrent: int = 1

    # --- 闪电上架（AI生成）---
    source_features: Optional[ImageFeature] = None
    product_link: Optional[ListingLink] = None
    is_flash: bool = False

    # --- 分布式存储 ---
    ipfs_hash: str = ""
    local_node_id: str = ""

    # --- 状态 ---
    status: ListingStatus = ListingStatus.DRAFT
    view_count: int = 0
    favorite_count: int = 0
    order_count: int = 0

    # --- 时间戳 ---
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None

    # ========================================================================
    # 类型判断
    # ========================================================================

    @property
    def is_physical(self) -> bool:
        return self.category not in (
            ListingCategory.SERVICE, ListingCategory.DIGITAL,
            ListingCategory.AI_COMPUTING, ListingCategory.KNOWLEDGE,
            ListingCategory.LIVE,
        )

    @property
    def is_service(self) -> bool:
        return self.category in (
            ListingCategory.SERVICE, ListingCategory.AI_COMPUTING,
            ListingCategory.KNOWLEDGE, ListingCategory.LIVE,
        )

    @property
    def is_ai_service(self) -> bool:
        return self.category == ListingCategory.AI_COMPUTING or (
            self.ai_model is not None and len(self.ai_capabilities) > 0
        )

    @property
    def is_active(self) -> bool:
        return self.status in (
            ListingStatus.ONLINE, ListingStatus.LIVE_ACTIVE,
            ListingStatus.LIVE_BUSY, ListingStatus.LIVE_PAUSED,
        )

    # ========================================================================
    # 序列化
    # ========================================================================

    def to_dict(self) -> dict:
        result = {
            "listing_id": self.listing_id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "tags": self.tags,
            "key_attributes": self.key_attributes,
            "price": self.price,
            "price_unit": self.price_unit,
            "negotiable": self.negotiable,
            "quantity": self.quantity,
            "condition": self.condition.value,
            "images": [img.to_dict() for img in self.images],
            "media_urls": self.media_urls,
            "thumbnail_url": self.thumbnail_url,
            "delivery_methods": [d.value for d in self.delivery_methods],
            "delivery_range": self.delivery_range,
            "payment_methods": [p.value for p in self.payment_methods],
            "location": self.location.to_dict() if self.location else None,
            "endpoint": self.endpoint.to_dict() if self.endpoint else None,
            "ai_model": self.ai_model,
            "ai_capabilities": self.ai_capabilities,
            "is_live_available": self.is_live_available,
            "max_concurrent": self.max_concurrent,
            "is_flash": self.is_flash,
            "ipfs_hash": self.ipfs_hash,
            "local_node_id": self.local_node_id,
            "status": self.status.value,
            "view_count": self.view_count,
            "favorite_count": self.favorite_count,
            "order_count": self.order_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Listing:
        location = None
        if data.get("location"):
            location = GeoLocation.from_dict(data["location"])

        endpoint = None
        if data.get("endpoint"):
            endpoint = P2PEndpoint.from_dict(data["endpoint"])

        images = [ListingImage.from_dict(d) for d in data.get("images", [])]

        return cls(
            listing_id=data.get("listing_id", ""),
            seller_id=data.get("seller_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=ListingCategory(data.get("category", "other")),
            tags=data.get("tags", []),
            key_attributes=data.get("key_attributes", {}),
            price=data.get("price", 0.0),
            price_unit=data.get("price_unit", "CNY"),
            negotiable=data.get("negotiable", True),
            quantity=data.get("quantity", 1),
            condition=ProductCondition(data.get("condition", "new")),
            images=images,
            media_urls=data.get("media_urls", []),
            thumbnail_url=data.get("thumbnail_url"),
            delivery_methods=[DeliveryMethod(d) for d in data.get("delivery_methods", [])],
            delivery_range=data.get("delivery_range", 5.0),
            payment_methods=[PaymentMethod(p) for p in data.get("payment_methods", [])],
            location=location,
            endpoint=endpoint,
            ai_model=data.get("ai_model"),
            ai_capabilities=data.get("ai_capabilities", []),
            is_live_available=data.get("is_live_available", False),
            max_concurrent=data.get("max_concurrent", 1),
            is_flash=data.get("is_flash", False),
            ipfs_hash=data.get("ipfs_hash", ""),
            local_node_id=data.get("local_node_id", ""),
            status=ListingStatus(data.get("status", "draft")),
            view_count=data.get("view_count", 0),
            favorite_count=data.get("favorite_count", 0),
            order_count=data.get("order_count", 0),
            created_at=data.get("created_at", datetime.now().timestamp()),
            updated_at=data.get("updated_at", datetime.now().timestamp()),
            expires_at=data.get("expires_at"),
        )

    # ========================================================================
    # 转换工厂
    # ========================================================================

    def to_product_dict(self) -> dict:
        """转换为传统 Product 格式（兼容 local_market）"""
        return {
            "product_id": self.listing_id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "tags": self.tags,
            "price": self.price,
            "price_unit": self.price_unit,
            "negotiable": self.negotiable,
            "condition": self.condition.value,
            "quantity": self.quantity,
            "images": self.images,
            "delivery_type": self.delivery_methods[0].value if self.delivery_methods else "pickup",
            "delivery_range": self.delivery_range,
            "location": self.location.to_dict() if self.location else None,
            "status": "active" if self.is_active else "removed",
            "view_count": self.view_count,
            "favorite_count": self.favorite_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "ipfs_hash": self.ipfs_hash,
            "local_node_id": self.local_node_id,
        }

    def to_broadcast_dict(self) -> dict:
        """转换为发现广播格式"""
        return {
            "listing_id": self.listing_id,
            "title": self.title[:50],
            "price": f"{self.price:.2f}{self.price_unit}",
            "category": self.category.value,
            "condition": self.condition.value,
            "geo_hash": self.location.geohash if self.location else "",
            "seller_id": self.seller_id,
            "is_service": self.is_service,
            "is_flash": self.is_flash,
            "product_link": self.product_link.clickable_link if self.product_link else "",
        }
