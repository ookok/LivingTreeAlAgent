"""
商品发现引擎

基于地理位置和兴趣匹配的商品发现系统
"""

import asyncio
import hashlib
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import random

from .models import (
    Product, ProductCategory, GeoLocation, NodeInfo,
    NetworkMessage, MessageType, TradeParticipant
)
from .dht import ProductIndexManager, ProductIndex
from .network import NodePeer


logger = logging.getLogger(__name__)


class DiscoveryStrategy(Enum):
    """发现策略"""
    CONCENTRIC = "concentric"       # 同心圆扩散
    SMART = "smart"                 # 智能广播
    INTEREST = "interest"            # 兴趣匹配
    HYBRID = "hybrid"               # 混合策略


@dataclass
class DiscoveryQuery:
    """发现查询"""
    # 地理位置
    location: Optional[GeoLocation] = None
    radius_km: float = 5.0          # 搜索半径

    # 分类过滤
    category: Optional[ProductCategory] = None

    # 价格过滤
    price_min: float = 0.0
    price_max: float = float('inf')

    # 信誉过滤
    seller_rep_min: int = 0

    # 关键词
    keywords: List[str] = field(default_factory=list)

    # 排序
    sort_by: str = "distance"       # distance / price / reputation / freshness
    sort_order: str = "asc"         # asc / desc

    # 分页
    limit: int = 20
    offset: int = 0


@dataclass
class DiscoveredProduct:
    """发现的商品"""
    product: Product
    distance_km: float = 0.0
    match_score: float = 0.0         # 匹配度得分
    seller_info: Optional[NodeInfo] = None
    source_node_id: str = ""        # 发现该商品的节点ID


class ProductDiscoveryEngine:
    """商品发现引擎"""

    # 同心圆扩散半径（公里）
    CONCENTRIC_RADII = [1.0, 5.0, 10.0, 30.0, 100.0]

    def __init__(
        self,
        node_peer: NodePeer,
        index_manager: ProductIndexManager,
        node_info: NodeInfo
    ):
        self.node_peer = node_peer
        self.index_manager = index_manager
        self.node_info = node_info

        # 兴趣匹配权重
        self.interest_weights = {
            "category_match": 0.3,
            "price_match": 0.2,
            "reputation": 0.2,
            "freshness": 0.15,
            "distance": 0.15
        }

        # 缓存
        self.discovery_cache: Dict[str, List[DiscoveredProduct]] = {}
        self.cache_ttl = 300  # 5分钟

        # 统计
        self.stats = {
            "queries": 0,
            "cache_hits": 0,
            "broadcasts_sent": 0,
            "products_found": 0
        }

    def _generate_cache_key(self, query: DiscoveryQuery) -> str:
        """生成查询缓存键"""
        key_parts = []

        if query.location:
            key_parts.append(f"geo:{query.location.geohash[:6]}")

        if query.category:
            key_parts.append(f"cat:{query.category.value}")

        key_parts.append(f"p:{query.price_min}-{query.price_max}")
        key_parts.append(f"r:{query.seller_rep_min}")

        if query.keywords:
            key_parts.append(f"kw:{','.join(sorted(query.keywords))}")

        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    async def discover(
        self,
        query: DiscoveryQuery,
        strategy: DiscoveryStrategy = DiscoveryStrategy.HYBRID
    ) -> List[DiscoveredProduct]:
        """发现商品"""
        self.stats["queries"] += 1

        # 检查缓存
        cache_key = self._generate_cache_key(query)
        if cache_key in self.discovery_cache:
            self.stats["cache_hits"] += 1
            return self.discovery_cache[cache_key]

        results = []

        if strategy == DiscoveryStrategy.CONCENTRIC:
            results = await self._discover_concentric(query)
        elif strategy == DiscoveryStrategy.SMART:
            results = await self._discover_smart(query)
        elif strategy == DiscoveryStrategy.INTEREST:
            results = await self._discover_by_interest(query)
        else:  # HYBRID
            results = await self._discover_hybrid(query)

        # 计算匹配得分
        for product in results:
            product.match_score = await self._calculate_match_score(product, query)

        # 排序
        results = self._sort_results(results, query)

        # 缓存
        self.discovery_cache[cache_key] = results

        self.stats["products_found"] += len(results)
        return results

    async def _discover_concentric(
        self,
        query: DiscoveryQuery
    ) -> List[DiscoveredProduct]:
        """同心圆扩散发现"""
        results = []
        seen_ids: Set[str] = set()

        if not query.location:
            return results

        for radius in self.CONCENTRIC_RADII:
            if len(results) >= query.limit:
                break

            # 通过 DHT 查找附近商品
            nearby = await self.index_manager.find_nearby_products(
                geohash=query.location.geohash,
                category=query.category.value if query.category else None,
                price_max=query.price_max if query.price_max < float('inf') else None,
                seller_rep_min=query.seller_rep_min,
                limit=query.limit * 2
            )

            for index in nearby:
                if index.product_id in seen_ids:
                    continue
                seen_ids.add(index.product_id)

                # 计算实际距离
                dist = self._calculate_distance(query.location.geohash, index.geohash_prefix)

                if dist <= radius:
                    product = await self._load_product_details(index)
                    if product:
                        discovered = DiscoveredProduct(
                            product=product,
                            distance_km=dist,
                            source_node_id=self.node_info.node_id
                        )
                        results.append(discovered)

            # 如果当前半径没找到，继续扩大

        return results

    async def _discover_smart(self, query: DiscoveryQuery) -> List[DiscoveredProduct]:
        """智能广播发现"""
        results = []
        seen_ids: Set[str] = set()

        # 获取活跃时间段匹配的节点
        current_hour = datetime.now().hour
        active_nodes = [
            n for n in self.node_peer.get_alive_nodes()
            if current_hour in n.active_hours or not n.active_hours
        ]

        # 按信誉排序，优先广播给高信誉节点
        active_nodes.sort(key=lambda n: n.reputation, reverse=True)

        # 广播查询消息
        query_msg = NetworkMessage(
            msg_type=MessageType.PRODUCT_QUERY,
            sender_id=self.node_info.node_id,
            sender_name=self.node_info.name,
            payload={
                "query": {
                    "category": query.category.value if query.category else None,
                    "price_min": query.price_min,
                    "price_max": query.price_max,
                    "keywords": query.keywords,
                    "radius_km": query.radius_km
                },
                "source_node": self.node_info.node_id
            },
            ttl=3
        )

        # 发送广播
        self.node_peer.register_handler(MessageType.PRODUCT_QUERY, self._handle_product_response)
        await self._broadcast_query(query_msg, active_nodes[:10])

        self.stats["broadcasts_sent"] += 1

        # 同时本地查询
        if query.location:
            local_results = await self._discover_concentric(query)
            for r in local_results:
                if r.product.product_id not in seen_ids:
                    seen_ids.add(r.product.product_id)
                    results.append(r)

        return results

    async def _discover_by_interest(
        self,
        query: DiscoveryQuery
    ) -> List[DiscoveredProduct]:
        """基于兴趣匹配发现"""
        results = []
        seen_ids: Set[str] = set()

        # 获取买家的历史偏好
        buyer_preferences = self._get_buyer_preferences()

        # 从路由表获取节点
        all_nodes = self.node_peer.get_alive_nodes()

        # 按兴趣匹配度排序节点
        scored_nodes = []
        for node in all_nodes:
            score = self._calculate_node_interest_score(node, buyer_preferences, query)
            scored_nodes.append((score, node))

        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # 向最相关的节点发送定向查询
        for score, node in scored_nodes[:5]:
            if score > 0:
                query_msg = NetworkMessage(
                    msg_type=MessageType.PRODUCT_QUERY,
                    sender_id=self.node_info.node_id,
                    sender_name=self.node_info.name,
                    receiver_id=node.node_id,
                    payload={
                        "query": query.__dict__,
                        "interest_score_threshold": 0.3
                    }
                )

                await self.node_peer.send_tcp_message(node.node_id, query_msg)

        # 本地查询作为补充
        if query.location:
            local = await self._discover_concentric(query)
            results.extend([r for r in local if r.product.product_id not in seen_ids])

        return results

    async def _discover_hybrid(
        self,
        query: DiscoveryQuery
    ) -> List[DiscoveredProduct]:
        """混合发现策略"""
        # 并行执行同心圆和兴趣发现
        concentric_task = asyncio.create_task(self._discover_concentric(query))
        smart_task = asyncio.create_task(self._discover_smart(query))

        concentric_results, smart_results = await asyncio.gather(
            concentric_task, smart_task,
            return_exceptions=True
        )

        results = []
        seen_ids: Set[str] = set()

        # 合并结果，去重
        for r in (concentric_results if isinstance(concentric_results, list) else []):
            if r.product.product_id not in seen_ids:
                seen_ids.add(r.product.product_id)
                results.append(r)

        for r in (smart_results if isinstance(smart_results, list) else []):
            if r.product.product_id not in seen_ids:
                seen_ids.add(r.product.product_id)
                results.append(r)

        return results

    async def _handle_product_response(self, msg: NetworkMessage):
        """处理商品响应消息"""
        try:
            payload = msg.payload
            if "product" in payload:
                product_data = payload["product"]
                product = Product.from_dict(product_data)

                discovered = DiscoveredProduct(
                    product=product,
                    distance_km=payload.get("distance_km", 0),
                    source_node_id=msg.sender_id
                )

                # 添加到缓存或结果集
                logger.debug(f"Received product response: {product.product_id}")

        except Exception as e:
            logger.error(f"Error handling product response: {e}")

    async def _broadcast_query(
        self,
        msg: NetworkMessage,
        nodes: List[NodeInfo]
    ):
        """广播查询到指定节点"""
        for node in nodes:
            if node.node_id != self.node_info.node_id:
                await self.node_peer.send_tcp_message(node.node_id, msg)

    async def _load_product_details(self, index: ProductIndex) -> Optional[Product]:
        """加载商品详情"""
        # 简化实现，实际应该从存储节点获取
        product = Product(
            product_id=index.product_id,
            title=index.title,
            price=index.price,
            category=ProductCategory(index.category) if index.category else ProductCategory.OTHER
        )
        return product

    def _calculate_distance(self, geohash1: str, geohash2: str) -> float:
        """计算两个 geohash 之间的距离（简化）"""
        # 实际应该解析 geohash 为经纬度再计算
        common_prefix = 0
        for c1, c2 in zip(geohash1, geohash2):
            if c1 == c2:
                common_prefix += 1
            else:
                break

        # 每增加一个公共前缀，距离约减半
        # geohash 每个字符约代表 5km / 2^(precision*5)
        return 5.0 / (2 ** (common_prefix * 5))

    def _calculate_match_score(
        self,
        discovered: DiscoveredProduct,
        query: DiscoveryQuery
    ) -> float:
        """计算匹配度得分"""
        score = 0.0
        product = discovered.product

        # 分类匹配
        if query.category and product.category == query.category:
            score += self.interest_weights["category_match"]

        # 价格匹配
        if query.price_min <= product.price <= query.price_max:
            price_range = query.price_max - query.price_min
            if price_range > 0:
                ideal_price = (query.price_min + query.price_max) / 2
                price_score = 1 - abs(product.price - ideal_price) / price_range
                score += price_score * self.interest_weights["price_match"]

        # 信誉加成
        if discovered.seller_info:
            rep_normalized = min(discovered.seller_info.reputation / 200, 1.0)
            score += rep_normalized * self.interest_weights["reputation"]

        # 新鲜度加成
        age_hours = (datetime.now() - product.created_at).total_seconds() / 3600
        freshness_score = max(0, 1 - age_hours / 168)  # 一周内的 freshness
        score += freshness_score * self.interest_weights["freshness"]

        # 距离得分
        if query.location and discovered.distance_km > 0:
            distance_score = max(0, 1 - discovered.distance_km / query.radius_km)
            score += distance_score * self.interest_weights["distance"]

        return min(score, 1.0)

    def _calculate_node_interest_score(
        self,
        node: NodeInfo,
        preferences: Dict[str, Any],
        query: DiscoveryQuery
    ) -> float:
        """计算节点的兴趣匹配得分"""
        score = 0.0

        # 历史交易分类匹配
        node_categories = preferences.get("categories", [])
        if query.category and query.category.value in node_categories:
            score += 0.4

        # 活跃时间匹配
        current_hour = datetime.now().hour
        if current_hour in node.active_hours:
            score += 0.3

        # 信誉加成
        score += min(node.reputation / 200, 1.0) * 0.3

        return score

    def _get_buyer_preferences(self) -> Dict[str, Any]:
        """获取买家偏好（简化）"""
        # 实际应该从 GBrain 记忆系统获取
        return {
            "categories": [],
            "price_ranges": {},
            "active_hours": list(range(24))
        }

    def _sort_results(
        self,
        results: List[DiscoveredProduct],
        query: DiscoveryQuery
    ) -> List[DiscoveredProduct]:
        """排序结果"""
        if query.sort_by == "distance":
            results.sort(key=lambda x: x.distance_km)
        elif query.sort_by == "price":
            results.sort(
                key=lambda x: x.product.price,
                reverse=(query.sort_order == "desc")
            )
        elif query.sort_by == "reputation":
            results.sort(
                key=lambda x: x.seller_info.reputation if x.seller_info else 0,
                reverse=True
            )
        elif query.sort_by == "freshness":
            results.sort(
                key=lambda x: x.product.created_at,
                reverse=True
            )
        elif query.sort_by == "score":
            results.sort(key=lambda x: x.match_score, reverse=True)

        return results[query.offset:query.offset + query.limit]


class RecommendationEngine:
    """推荐引擎 - 基于协同过滤和内容推荐"""

    def __init__(self, discovery_engine: ProductDiscoveryEngine):
        self.discovery_engine = discovery_engine

        # 用户-商品交互矩阵
        self.interaction_matrix: Dict[str, Dict[str, float]] = {}

        # 商品相似度缓存
        self.similarity_cache: Dict[str, Dict[str, float]] = {}

    def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str,
        value: float = 1.0
    ):
        """记录用户交互"""
        if user_id not in self.interaction_matrix:
            self.interaction_matrix[user_id] = {}

        # 交互类型权重
        weights = {
            "view": 0.1,
            "favorite": 0.3,
            "inquiry": 0.5,
            "purchase": 1.0
        }

        weight = weights.get(interaction_type, 0.1)
        self.interaction_matrix[user_id][product_id] = value * weight

    async def recommend_for_user(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Product]:
        """为用户推荐商品"""
        if user_id not in self.interaction_matrix:
            # 冷启动：返回热门商品
            return await self._recommend_popular(limit)

        # 找到相似用户
        similar_users = self._find_similar_users(user_id)

        # 收集相似用户喜欢的商品
        candidate_products: Dict[str, float] = {}
        for sim_user_id, similarity in similar_users:
            for product_id, score in self.interaction_matrix.get(sim_user_id, {}).items():
                if product_id not in self.interaction_matrix.get(user_id, {}):
                    candidate_products[product_id] = candidate_products.get(product_id, 0) + similarity * score

        # 排序返回
        sorted_products = sorted(
            candidate_products.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 加载商品详情
        results = []
        for product_id, _ in sorted_products[:limit]:
            # 实际应该从存储加载
            product = Product(product_id=product_id)
            results.append(product)

        return results

    async def _recommend_popular(self, limit: int) -> List[Product]:
        """推荐热门商品"""
        # 简化实现
        return []

    def _find_similar_users(
        self,
        user_id: str,
        k: int = 10
    ) -> List[tuple]:
        """找到 k 个最相似的用户"""
        if user_id not in self.interaction_matrix:
            return []

        user_vector = self.interaction_matrix[user_id]

        similarities = []
        for other_id, other_vector in self.interaction_matrix.items():
            if other_id == user_id:
                continue

            similarity = self._cosine_similarity(user_vector, other_vector)
            if similarity > 0:
                similarities.append((other_id, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def _cosine_similarity(
        self,
        vec1: Dict[str, float],
        vec2: Dict[str, float]
    ) -> float:
        """计算余弦相似度"""
        common_keys = set(vec1.keys()) & set(vec2.keys())
        if not common_keys:
            return 0.0

        dot_product = sum(vec1[k] * vec2[k] for k in common_keys)
        norm1 = sum(v ** 2 for v in vec1.values()) ** 0.5
        norm2 = sum(v ** 2 for v in vec2.values()) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
