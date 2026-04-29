# -*- coding: utf-8 -*-
"""
商品管理模块
============

功能：
- 商品发布与更新
- 地理位置发现
- 智能搜索与匹配
- 商品分类体系

核心类：
- Product: 商品数据模型
- ProductManager: 商品管理器
- ProductCategory: 商品分类枚举
- Location: 位置信息
"""

import uuid
import time
import hashlib
import json
import asyncio
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Callable, Any
from collections import defaultdict


class ProductCategory(Enum):
    """商品分类"""
    # 实物商品
    ELECTRONICS = "electronics"           # 电子产品
    FASHION = "fashion"                   # 服装鞋帽
    HOME = "home"                          # 家居用品
    FOOD = "food"                          # 食品生鲜
    BOOKS = "books"                        # 图书文具
    SPORTS = "sports"                      # 运动户外
    CARS = "cars"                          # 二手车/配件
    OTHER = "other"                        # 其他实物

    # 服务
    REPAIR = "repair"                      # 维修服务
    CLEANING = "cleaning"                  # 家政保洁
    DELIVERY = "delivery"                  # 配送服务
    EDUCATION = "education"                # 教育培训
    BEAUTY = "beauty"                      # 美妆美容
    OTHER_SERVICE = "other_service"        # 其他服务

    @property
    def is_physical(self) -> bool:
        """是否为实物商品"""
        return self.name in [
            "ELECTRONICS", "FASHION", "HOME", "FOOD",
            "BOOKS", "SPORTS", "CARS", "OTHER"
        ]

    @property
    def icon(self) -> str:
        """分类图标"""
        icons = {
            "ELECTRONICS": "📱",
            "FASHION": "👕",
            "HOME": "🏠",
            "FOOD": "🍎",
            "BOOKS": "📚",
            "SPORTS": "⚽",
            "CARS": "🚗",
            "OTHER": "📦",
            "REPAIR": "🔧",
            "CLEANING": "🧹",
            "DELIVERY": "📦",
            "EDUCATION": "📖",
            "BEAUTY": "💄",
            "OTHER_SERVICE": "🛠️",
        }
        return icons.get(self.name, "📦")


@dataclass
class Location:
    """地理位置信息"""
    latitude: float           # 纬度
    longitude: float          # 经度
    address: str = ""         # 地址描述
    district: str = ""        # 行政区
    city: str = ""            # 城市

    def distance_to(self, other: 'Location') -> float:
        """计算两点之间的距离（公里）Haversine公式"""
        import math
        R = 6371  # 地球半径（公里）

        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def get_geo_hash(self, precision: int = 6) -> str:
        """获取地理哈希"""
        # 简化的geohash实现
        BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
        lat_range, lon_range = (-90, 90), (-180, 180)
        geohash = []
        bits = 0
        bit_count = 0
        is_lon = True

        while len(geohash) < precision:
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if self.longitude >= mid:
                    bits = (bits << 1) | 1
                    lon_range = (mid, lon_range[1])
                else:
                    bits = bits << 1
                    lon_range = (lon_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if self.latitude >= mid:
                    bits = (bits << 1) | 1
                    lat_range = (mid, lat_range[1])
                else:
                    bits = bits << 1
                    lat_range = (lat_range[0], mid)

            is_lon = not is_lon
            bit_count += 1

            if bit_count == 5:
                geohash.append(BASE32[bits])
                bits = 0
                bit_count = 0

        return "".join(geohash)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Location':
        return cls(**data)


@dataclass
class Product:
    """商品数据模型"""
    product_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str = ""                      # 卖家ID
    title: str = ""                         # 商品标题
    description: str = ""                   # 详细描述
    category: ProductCategory = ProductCategory.OTHER  # 分类
    price: float = 0.0                     # 价格
    currency: str = "CNY"                   # 货币
    negotiable: bool = True                 # 可否议价

    # 位置信息
    location: Optional[Location] = None    # 位置

    # 媒体
    images: List[str] = field(default_factory=list)  # 图片列表（IPFS哈希）
    videos: List[str] = field(default_factory=list)  # 视频列表

    # 状态
    status: str = "active"                  # active/offline/sold
    views: int = 0                          # 浏览次数
    favorites: int = 0                      # 收藏次数

    # 时间
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = 0                  # 过期时间（0=不过期）

    # 元数据
    tags: List[str] = field(default_factory=list)
    condition: str = "new"                 # new/like_new/used
    quantity: int = 1                       # 数量

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['category'] = self.category.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Product':
        """从字典创建"""
        data = data.copy()
        data['category'] = ProductCategory(data.get('category', 'other'))
        return cls(**data)

    def get_summary(self) -> Dict:
        """获取摘要信息（用于广播）"""
        return {
            "product_id": self.product_id,
            "title": self.title[:50],
            "price": self.price,
            "currency": self.currency,
            "category": self.category.value,
            "geo_hash": self.location.get_geo_hash() if self.location else "",
            "condition": self.condition,
            "seller_reputation": 0,  # 后续从信誉系统获取
            "created_at": self.created_at,
        }

    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = time.time()


class ProductManager:
    """商品管理器"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.products: Dict[str, Product] = {}       # product_id -> Product
        self.favorites: Set[str] = set()              # 收藏的商品ID

        # 索引加速
        self.category_index: Dict[str, Set[str]] = defaultdict(set)
        self.geo_index: Dict[str, Set[str]] = defaultdict(set)  # geohash -> product_ids

        # 广播缓存（防止重复广播）
        self.broadcast_cache: Dict[str, float] = {}

        # 回调
        self.on_product_update: Optional[Callable] = None
        self.on_product_discovered: Optional[Callable] = None

    def publish_product(self, product: Product) -> str:
        """发布商品"""
        product.seller_id = self.node_id
        product.product_id = str(uuid.uuid4())
        product.created_at = time.time()
        product.updated_at = time.time()

        self.products[product.product_id] = product

        # 更新索引
        self._update_indices(product)

        # 广播商品
        asyncio.create_task(self._broadcast_product(product, "new"))

        return product.product_id

    def update_product(self, product_id: str, **kwargs) -> bool:
        """更新商品"""
        if product_id not in self.products:
            return False

        product = self.products[product_id]

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(product, key):
                setattr(product, key, value)

        product.update_timestamp()

        # 重新更新索引
        self._rebuild_indices(product)

        # 广播更新
        asyncio.create_task(self._broadcast_product(product, "update"))

        return True

    def delete_product(self, product_id: str) -> bool:
        """删除商品（下架）"""
        if product_id not in self.products:
            return False

        product = self.products[product_id]
        product.status = "offline"
        product.update_timestamp()

        # 广播下架
        asyncio.create_task(self._broadcast_product(product, "offline"))

        return True

    def mark_sold(self, product_id: str) -> bool:
        """标记为已售"""
        return self.update_product(product_id, status="sold")

    def get_product(self, product_id: str) -> Optional[Product]:
        """获取商品"""
        return self.products.get(product_id)

    def get_my_products(self) -> List[Product]:
        """获取我发布的商品"""
        return [
            p for p in self.products.values()
            if p.seller_id == self.node_id
        ]

    def search_products(
        self,
        query: str = "",
        category: Optional[ProductCategory] = None,
        location: Optional[Location] = None,
        max_distance: float = 10.0,  # 公里
        min_price: float = 0,
        max_price: float = float('inf'),
        limit: int = 50,
    ) -> List[Product]:
        """搜索商品"""
        results = []

        for product in self.products.values():
            # 过滤条件
            if product.status != "active":
                continue

            # 价格过滤
            if not (min_price <= product.price <= max_price):
                continue

            # 分类过滤
            if category and product.category != category:
                continue

            # 关键词过滤
            if query:
                q_lower = query.lower()
                if q_lower not in product.title.lower() and q_lower not in product.description.lower():
                    continue

            # 距离过滤
            if location and product.location:
                distance = location.distance_to(product.location)
                if distance > max_distance:
                    continue

            results.append(product)

        # 按距离排序（如果有位置）
        if location:
            results.sort(key=lambda p: (
                location.distance_to(p.location) if p.location else float('inf')
            ))

        return results[:limit]

    def discover_nearby_products(
        self,
        location: Location,
        radius_km: float = 5.0,
        categories: Optional[List[ProductCategory]] = None,
        limit: int = 100,
    ) -> List[tuple]:
        """发现附近商品（返回商品和距离）"""
        # 按同心圆扩散
        candidates = []

        for product in self.products.values():
            if product.status != "active":
                continue

            if categories and product.category not in categories:
                continue

            if product.location:
                distance = location.distance_to(product.location)
                if distance <= radius_km:
                    candidates.append((product, distance))

        # 按距离排序
        candidates.sort(key=lambda x: x[1])

        return candidates[:limit]

    def add_to_favorites(self, product_id: str) -> bool:
        """添加收藏"""
        if product_id in self.products:
            self.favorites.add(product_id)
            self.products[product_id].favorites += 1
            return True
        return False

    def remove_from_favorites(self, product_id: str) -> bool:
        """移除收藏"""
        if product_id in self.favorites:
            self.favorites.discard(product_id)
            return True
        return False

    def get_favorites(self) -> List[Product]:
        """获取收藏列表"""
        return [
            self.products[pid]
            for pid in self.favorites
            if pid in self.products
        ]

    def increment_views(self, product_id: str):
        """增加浏览次数"""
        if product_id in self.products:
            self.products[product_id].views += 1

    def _update_indices(self, product: Product):
        """更新索引"""
        # 分类索引
        self.category_index[product.category.value].add(product.product_id)

        # 地理索引
        if product.location:
            geohash = product.location.get_geo_hash(precision=6)
            self.geo_index[geohash].add(product.product_id)

    def _rebuild_indices(self, product: Product):
        """重建索引"""
        # 从所有索引中移除
        for pid_set in self.category_index.values():
            pid_set.discard(product.product_id)
        for pid_set in self.geo_index.values():
            pid_set.discard(product.product_id)

        # 重新添加
        self._update_indices(product)

    async def _broadcast_product(self, product: Product, action: str):
        """广播商品到网络"""
        # TODO: 集成LivingTreeAI的P2P网络
        # 目前只是记录
        cache_key = f"{product.product_id}:{action}"
        now = time.time()

        if cache_key in self.broadcast_cache:
            if now - self.broadcast_cache[cache_key] < 300:  # 5分钟内不重复广播
                return

        self.broadcast_cache[cache_key] = now

        # 广播逻辑将在P2P网络集成时实现
        if self.on_product_update:
            await self.on_product_update(product, action)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        active = sum(1 for p in self.products.values() if p.status == "active")
        sold = sum(1 for p in self.products.values() if p.status == "sold")

        category_stats = defaultdict(int)
        for p in self.products.values():
            category_stats[p.category.value] += 1

        return {
            "total": len(self.products),
            "active": active,
            "sold": sold,
            "favorites": len(self.favorites),
            "by_category": dict(category_stats),
        }

    def export_products(self) -> List[Dict]:
        """导出所有商品（用于备份）"""
        return [p.to_dict() for p in self.products.values()]

    def import_products(self, data: List[Dict]):
        """导入商品"""
        for item in data:
            product = Product.from_dict(item)
            self.products[product.product_id] = product
            self._update_indices(product)


# ============================================================
# 地理位置服务（简化实现）
# ============================================================

class GeoService:
    """地理位置服务"""

    # 预定义的测试位置
    TEST_LOCATIONS = {
        "北京": Location(39.9042, 116.4074, "北京市", "朝阳区", "北京"),
        "上海": Location(31.2304, 121.4737, "上海市", "浦东新区", "上海"),
        "广州": Location(23.1291, 113.2644, "广州市", "天河区", "广州"),
        "深圳": Location(22.5431, 114.0579, "深圳市", "南山区", "深圳"),
    }

    @classmethod
    def get_current_location(cls) -> Optional[Location]:
        """获取当前位置（实际应调用系统API）"""
        # 简化实现，返回测试位置
        return cls.TEST_LOCATIONS.get("北京")

    @classmethod
    def calculate_distance(cls, loc1: Location, loc2: Location) -> float:
        """计算距离"""
        return loc1.distance_to(loc2)


if __name__ == "__main__":
    # 简单测试
    manager = ProductManager("test_node")

    # 创建商品
    product = Product(
        title="iPhone 14 Pro Max 256G",
        description="99新无划痕原装配件齐全",
        category=ProductCategory.ELECTRONICS,
        price=6999.0,
        condition="like_new",
        location=Location(39.9042, 116.4074, "北京朝阳区", "朝阳区", "北京"),
    )

    pid = manager.publish_product(product)
    print(f"Published: {pid}")

    # 搜索
    results = manager.search_products(
        query="iPhone",
        max_price=8000,
    )
    print(f"Found {len(results)} products")
