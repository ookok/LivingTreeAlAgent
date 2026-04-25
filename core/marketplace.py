#!/usr/bin/env python3
"""
Marketplace - 生态市场
Phase 5 核心：技能市场、代理市场、模板市场、交易系统

Author: LivingTreeAI Team
Version: 1.0.0
"""

import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading


class ListingType(Enum):
    """商品类型"""
    SKILL = "skill"          # 技能
    AGENT = "agent"          # 代理
    TEMPLATE = "template"    # 模板
    DATASET = "dataset"      # 数据集
    MODEL = "model"         # 模型


class ListingStatus(Enum):
    """商品状态"""
    DRAFT = "draft"          # 草稿
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已审核
    REJECTED = "rejected"    # 已拒绝
    PUBLISHED = "published"  # 已发布
    ARCHIVED = "archived"    # 已归档


class PriceModel(Enum):
    """定价模式"""
    FREE = "free"           # 免费
    ONE_TIME = "one_time"   # 一次性
    SUBSCRIPTION = "subscription"  # 订阅
    USAGE = "usage"        # 按量计费


@dataclass
class Seller:
    """卖家"""
    id: str
    name: str
    rating: float = 0.0
    total_sales: int = 0
    joined_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Listing:
    """商品"""
    id: str
    listing_type: ListingType
    name: str
    description: str
    seller_id: str
    price: float = 0.0
    price_model: PriceModel = PriceModel.FREE
    status: ListingStatus = ListingStatus.DRAFT
    tags: List[str] = field(default_factory=list)
    category: str = ""
    version: str = "1.0.0"
    download_count: int = 0
    rating: float = 0.0
    rating_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    published_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_published(self) -> bool:
        return self.status == ListingStatus.PUBLISHED


@dataclass
class Review:
    """评价"""
    id: str
    listing_id: str
    buyer_id: str
    rating: float
    comment: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class Transaction:
    """交易"""
    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount: float
    currency: str = "USD"
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CartItem:
    """购物车项"""
    listing_id: str
    quantity: int = 1
    price_snapshot: float = 0.0  # 下单时的价格


class CategoryManager:
    """分类管理器"""
    
    def __init__(self):
        self._categories: Dict[str, Dict[str, Any]] = {
            "skill": {
                "name": "技能",
                "icon": "🛠️",
                "subcategories": ["写作", "编程", "设计", "营销", "分析"],
            },
            "agent": {
                "name": "代理",
                "icon": "🤖",
                "subcategories": ["助手", "专家", "自动化", "分析"],
            },
            "template": {
                "name": "模板",
                "icon": "📋",
                "subcategories": ["文档", "代码", "设计", "流程"],
            },
            "dataset": {
                "name": "数据集",
                "icon": "📊",
                "subcategories": ["训练数据", "测试数据", "标注数据"],
            },
            "model": {
                "name": "模型",
                "icon": "🧠",
                "subcategories": ["语言模型", "视觉模型", "多模态"],
            },
        }
    
    def get_categories(self, listing_type: Optional[ListingType] = None) -> Dict[str, Any]:
        """获取分类"""
        if listing_type:
            return self._categories.get(listing_type.value, {})
        return self._categories
    
    def get_subcategories(self, listing_type: ListingType) -> List[str]:
        """获取子分类"""
        category = self._categories.get(listing_type.value, {})
        return category.get("subcategories", [])


class SearchEngine:
    """搜索引擎"""
    
    def __init__(self):
        self._index: Dict[str, List[str]] = defaultdict(list)  # term -> listing_ids
    
    def index_listing(self, listing: Listing) -> None:
        """索引商品"""
        terms = self._extract_terms(listing)
        
        for term in terms:
            if listing.id not in self._index[term]:
                self._index[term].append(listing.id)
    
    def _extract_terms(self, listing: Listing) -> List[str]:
        """提取术语"""
        text = f"{listing.name} {listing.description} {' '.join(listing.tags)}"
        # 简单分词
        terms = text.lower().split()
        return list(set(terms))
    
    def search(self, query: str, limit: int = 20) -> List[str]:
        """搜索"""
        query_terms = query.lower().split()
        
        scores: Dict[str, int] = defaultdict(int)
        
        for term in query_terms:
            for indexed_term, listing_ids in self._index.items():
                if term in indexed_term:
                    for listing_id in listing_ids:
                        scores[listing_id] += 1
        
        # 排序
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        return sorted_ids[:limit]


class Marketplace:
    """
    生态市场
    
    核心功能：
    - 商品管理
    - 搜索与发现
    - 交易系统
    - 评价系统
    - 卖家管理
    - 分类系统
    """
    
    def __init__(self):
        # 商品
        self._listings: Dict[str, Listing] = {}
        
        # 卖家
        self._sellers: Dict[str, Seller] = {}
        
        # 评价
        self._reviews: Dict[str, List[Review]] = defaultdict(list)
        
        # 交易
        self._transactions: Dict[str, Transaction] = {}
        
        # 购物车
        self._carts: Dict[str, List[CartItem]] = defaultdict(list)
        
        # 搜索引擎
        self._search_engine = SearchEngine()
        
        # 分类
        self._category_manager = CategoryManager()
        
        # 锁
        self._lock = threading.RLock()
        
        # 事件
        self._event_handlers: Dict[str, List[Callable]] = {
            "listing_created": [],
            "listing_published": [],
            "listing_purchased": [],
            "review_submitted": [],
        }
    
    # ========== 卖家管理 ==========
    
    def register_seller(self, seller: Seller) -> None:
        """注册卖家"""
        with self._lock:
            self._sellers[seller.id] = seller
    
    def get_seller(self, seller_id: str) -> Optional[Seller]:
        """获取卖家"""
        with self._lock:
            return self._sellers.get(seller_id)
    
    # ========== 商品管理 ==========
    
    def create_listing(
        self,
        listing_type: ListingType,
        name: str,
        description: str,
        seller_id: str,
        price: float = 0.0,
        price_model: PriceModel = PriceModel.FREE,
        tags: Optional[List[str]] = None,
        category: str = "",
    ) -> Listing:
        """
        创建商品
        
        Args:
            listing_type: 商品类型
            name: 名称
            description: 描述
            seller_id: 卖家ID
            price: 价格
            price_model: 定价模式
            tags: 标签
            category: 分类
            
        Returns:
            商品
        """
        with self._lock:
            listing = Listing(
                id=str(uuid.uuid4()),
                listing_type=listing_type,
                name=name,
                description=description,
                seller_id=seller_id,
                price=price,
                price_model=price_model,
                tags=tags or [],
                category=category,
            )
            
            self._listings[listing.id] = listing
            
            self._emit_event("listing_created", {"listing_id": listing.id})
            
            return listing
    
    def update_listing(self, listing_id: str, **kwargs) -> Optional[Listing]:
        """更新商品"""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                return None
            
            for key, value in kwargs.items():
                if hasattr(listing, key):
                    setattr(listing, key, value)
            
            listing.updated_at = time.time()
            return listing
    
    def publish_listing(self, listing_id: str) -> bool:
        """发布商品"""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing:
                return False
            
            listing.status = ListingStatus.PUBLISHED
            listing.published_at = time.time()
            
            # 索引
            self._search_engine.index_listing(listing)
            
            self._emit_event("listing_published", {"listing_id": listing_id})
            
            return True
    
    def get_listing(self, listing_id: str) -> Optional[Listing]:
        """获取商品"""
        with self._lock:
            return self._listings.get(listing_id)
    
    def list_listings(
        self,
        listing_type: Optional[ListingType] = None,
        status: Optional[ListingStatus] = None,
        seller_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Listing]:
        """列出商品"""
        with self._lock:
            results = list(self._listings.values())
            
            if listing_type:
                results = [l for l in results if l.listing_type == listing_type]
            if status:
                results = [l for l in results if l.status == status]
            if seller_id:
                results = [l for l in results if l.seller_id == seller_id]
            if tags:
                results = [l for l in results if any(t in l.tags for t in tags)]
            
            return sorted(results, key=lambda x: x.created_at, reverse=True)
    
    # ========== 搜索 ==========
    
    def search(self, query: str, listing_type: Optional[ListingType] = None) -> List[Listing]:
        """搜索商品"""
        listing_ids = self._search_engine.search(query)
        
        with self._lock:
            results = []
            for lid in listing_ids:
                listing = self._listings.get(lid)
                if listing and listing.is_published:
                    if listing_type is None or listing.listing_type == listing_type:
                        results.append(listing)
            
            return results
    
    def get_trending(self, listing_type: Optional[ListingType] = None, limit: int = 10) -> List[Listing]:
        """获取热门商品"""
        with self._lock:
            results = list(self._listings.values())
            
            if listing_type:
                results = [l for l in results if l.listing_type == listing_type]
            
            results = [l for l in results if l.is_published]
            
            # 按下载量和评分排序
            results.sort(key=lambda x: (x.download_count * 0.5 + x.rating * 10), reverse=True)
            
            return results[:limit]
    
    def get_new_releases(self, listing_type: Optional[ListingType] = None, limit: int = 10) -> List[Listing]:
        """获取新品"""
        with self._lock:
            results = list(self._listings.values())
            
            if listing_type:
                results = [l for l in results if l.listing_type == listing_type]
            
            results = [l for l in results if l.is_published]
            
            return sorted(results, key=lambda x: x.published_at or 0, reverse=True)[:limit]
    
    # ========== 评价 ==========
    
    def submit_review(self, listing_id: str, buyer_id: str, rating: float, comment: str = "") -> Review:
        """提交评价"""
        with self._lock:
            review = Review(
                id=str(uuid.uuid4()),
                listing_id=listing_id,
                buyer_id=buyer_id,
                rating=rating,
                comment=comment,
            )
            
            self._reviews[listing_id].append(review)
            
            # 更新商品评分
            listing = self._listings.get(listing_id)
            if listing:
                total = sum(r.rating for r in self._reviews[listing_id])
                listing.rating = total / len(self._reviews[listing_id])
                listing.rating_count = len(self._reviews[listing_id])
            
            self._emit_event("review_submitted", {
                "listing_id": listing_id,
                "rating": rating,
            })
            
            return review
    
    def get_reviews(self, listing_id: str) -> List[Review]:
        """获取评价"""
        with self._lock:
            return list(self._reviews.get(listing_id, []))
    
    # ========== 交易 ==========
    
    def add_to_cart(self, buyer_id: str, listing_id: str) -> bool:
        """添加到购物车"""
        with self._lock:
            listing = self._listings.get(listing_id)
            if not listing or not listing.is_published:
                return False
            
            # 检查是否已购买
            for txn in self._transactions.values():
                if txn.buyer_id == buyer_id and txn.listing_id == listing_id:
                    return False
            
            # 添加到购物车
            cart_item = CartItem(
                listing_id=listing_id,
                price_snapshot=listing.price,
            )
            
            # 检查是否已在购物车
            for item in self._carts[buyer_id]:
                if item.listing_id == listing_id:
                    return False
            
            self._carts[buyer_id].append(cart_item)
            return True
    
    def remove_from_cart(self, buyer_id: str, listing_id: str) -> bool:
        """从购物车移除"""
        with self._lock:
            for i, item in enumerate(self._carts[buyer_id]):
                if item.listing_id == listing_id:
                    self._carts[buyer_id].pop(i)
                    return True
            return False
    
    def get_cart(self, buyer_id: str) -> List[Dict[str, Any]]:
        """获取购物车"""
        with self._lock:
            items = []
            for item in self._carts[buyer_id]:
                listing = self._listings.get(item.listing_id)
                if listing:
                    items.append({
                        "listing_id": listing.id,
                        "name": listing.name,
                        "price": item.price_snapshot,
                    })
            return items
    
    def checkout(self, buyer_id: str) -> List[Transaction]:
        """结账"""
        with self._lock:
            transactions = []
            
            for item in self._carts[buyer_id]:
                listing = self._listings.get(item.listing_id)
                if listing:
                    txn = Transaction(
                        id=str(uuid.uuid4()),
                        listing_id=listing.id,
                        buyer_id=buyer_id,
                        seller_id=listing.seller_id,
                        amount=item.price_snapshot,
                    )
                    
                    self._transactions[txn.id] = txn
                    listing.download_count += 1
                    transactions.append(txn)
                    
                    self._emit_event("listing_purchased", {
                        "listing_id": listing.id,
                        "buyer_id": buyer_id,
                        "amount": item.price_snapshot,
                    })
            
            # 清空购物车
            self._carts[buyer_id].clear()
            
            return transactions
    
    def get_purchases(self, buyer_id: str) -> List[Transaction]:
        """获取购买记录"""
        with self._lock:
            return [
                txn for txn in self._transactions.values()
                if txn.buyer_id == buyer_id
            ]
    
    # ========== 分类 ==========
    
    def get_categories(self, listing_type: Optional[ListingType] = None) -> Dict[str, Any]:
        """获取分类"""
        return self._category_manager.get_categories(listing_type)
    
    def get_subcategories(self, listing_type: ListingType) -> List[str]:
        """获取子分类"""
        return self._category_manager.get_subcategories(listing_type)
    
    # ========== 统计 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        with self._lock:
            by_type = {}
            for listing in self._listings.values():
                type_name = listing.listing_type.value
                if type_name not in by_type:
                    by_type[type_name] = {"total": 0, "published": 0}
                by_type[type_name]["total"] += 1
                if listing.is_published:
                    by_type[type_name]["published"] += 1
            
            return {
                "total_listings": len(self._listings),
                "total_sellers": len(self._sellers),
                "total_transactions": len(self._transactions),
                "total_reviews": sum(len(r) for r in self._reviews.values()),
                "by_type": by_type,
            }
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发事件"""
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                pass
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """注册事件处理"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)


# 全局市场实例
_global_marketplace: Optional[Marketplace] = None
_marketplace_lock = threading.Lock()


def get_marketplace() -> Marketplace:
    """获取全局市场实例"""
    global _global_marketplace
    
    with _marketplace_lock:
        if _global_marketplace is None:
            _global_marketplace = Marketplace()
        return _global_marketplace


# 便捷函数
def publish_skill(
    name: str,
    description: str,
    seller_id: str,
    price: float = 0.0,
    tags: Optional[List[str]] = None,
) -> Listing:
    """发布技能"""
    return get_marketplace().create_listing(
        listing_type=ListingType.SKILL,
        name=name,
        description=description,
        seller_id=seller_id,
        price=price,
        tags=tags,
    )


def search_skills(query: str) -> List[Listing]:
    """搜索技能"""
    return get_marketplace().search(query, ListingType.SKILL)
