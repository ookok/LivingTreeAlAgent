"""
去中心化本地商品交易市场 - 主系统

整合所有模块，提供统一的 API
"""

import asyncio
import json
import os
import sqlite3
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
import uuid

from .models import (
    NodeInfo, NodeType, Product, ProductCategory, GeoLocation,
    Trade, TransactionStatus, DeliveryType, PaymentType,
    NetworkMessage, MessageType, ReputationAction, ReputationEvent,
    ProductImage
)
from .network import NodePeer, Protocol
from .dht import DHTNode, ProductIndexManager
from .discovery import ProductDiscoveryEngine, DiscoveryQuery, DiscoveryStrategy, RecommendationEngine
from .trade import TradeManager, TradeError
from .reputation import ReputationManager, ReputationRecord
from .arbitration import ArbitrationManager, Dispute

logger = logging.getLogger(__name__)


class LocalMarketSystem:
    """去中心化本地商品交易市场主系统"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 节点信息
        self.node_id = self.config.get("node_id", str(uuid.uuid4())[:12])
        self.node_info = NodeInfo(
            node_id=self.node_id,
            node_type=NodeType.SELLER,
            name=self.config.get("node_name", f"Node-{self.node_id[:6]}"),
            location=GeoLocation(
                latitude=self.config.get("latitude", 0.0),
                longitude=self.config.get("longitude", 0.0),
                precision=self.config.get("location_precision", 6)
            )
        )

        # 网络层
        self.network = NodePeer(self.node_id, self.node_info)

        # DHT 层
        self.dht = DHTNode(
            self.node_id,
            local_ip=self.config.get("local_ip", "127.0.0.1"),
            local_port=self.config.get("port", 54322)
        )
        self.index_manager = ProductIndexManager(self.dht, self.node_id)

        # 信誉系统
        self.reputation = ReputationManager(self.node_id, self.node_info)

        # 交易系统
        self.trade_manager = TradeManager(
            self.node_id,
            self.node_info,
            self._send_message
        )

        # 仲裁系统
        self.arbitration = ArbitrationManager(self.node_id, self.reputation)

        # 发现引擎
        self.discovery = ProductDiscoveryEngine(
            self.network,
            self.index_manager,
            self.node_info
        )
        self.recommendation = RecommendationEngine(self.discovery)

        # 本地存储
        self.db_path = self.config.get("db_path", f"./data/local_market_{self.node_id}.db")
        self._init_database()

        # 状态
        self._running = False

        # 回调
        self.on_product_received: Optional[Callable] = None
        self.on_trade_update: Optional[Callable] = None

    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 商品表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                tags TEXT,
                price REAL,
                negotiable INTEGER,
                condition TEXT,
                quantity INTEGER,
                images TEXT,
                delivery_type TEXT,
                delivery_range REAL,
                location_data TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # 我的商品索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_seller ON products(seller_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {self.db_path}")

    # ========================================================================
    # 生命周期
    # ========================================================================

    async def start(self):
        """启动系统"""
        if self._running:
            return

        self._running = True

        # 启动网络层
        await self.network.start()

        # 注册消息处理器
        self.network.register_handler(MessageType.PRODUCT_QUERY, self._handle_product_query)
        self.network.register_handler(MessageType.TRADE_REQUEST, self._handle_trade_request)
        self.network.register_handler(MessageType.TRADE_UPDATE, self._handle_trade_update)
        self.network.register_handler(MessageType.REPUTATION, self._handle_reputation)
        self.network.register_handler(MessageType.ARBITRATION, self._handle_arbitration)

        # 注册为仲裁员
        self.arbitration.register_as_arbitrator()

        logger.info(f"LocalMarketSystem {self.node_id} started")

    async def stop(self):
        """停止系统"""
        if not self._running:
            return

        self._running = False

        await self.network.stop()

        logger.info(f"LocalMarketSystem {self.node_id} stopped")

    # ========================================================================
    # 商品管理
    # ========================================================================

    async def publish_product(
        self,
        title: str,
        description: str,
        price: float,
        category: ProductCategory = ProductCategory.OTHER,
        tags: List[str] = None,
        delivery_type: DeliveryType = DeliveryType.PICKUP,
        condition: str = "new",
        images: List[str] = None,
        negotiable: bool = True
    ) -> Product:
        """发布商品"""
        product = Product(
            product_id=str(uuid.uuid4())[:12],
            seller_id=self.node_id,
            title=title,
            description=description,
            category=category,
            tags=tags or [],
            price=price,
            negotiable=negotiable,
            condition=condition,
            delivery_type=delivery_type,
            location=self.node_info.location,
            images=[ProductImage(url=img) for img in (images or [])]
        )

        # 保存到本地数据库
        await self._save_product(product)

        # 发布到 DHT 索引
        index = self.index_manager.create_index(
            product_id=product.product_id,
            title=product.title,
            price=product.price,
            category=product.category.value,
            geohash=product.location.geohash if product.location else "",
            seller_id=self.node_id,
            seller_rep=self.node_info.reputation
        )
        await self.index_manager.publish_index(index)

        # 广播商品
        await self._broadcast_product(product)

        logger.info(f"Product {product.product_id} published: {title}")
        return product

    async def update_product(
        self,
        product_id: str,
        **kwargs
    ) -> Product:
        """更新商品"""
        product = await self._load_product(product_id)

        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.seller_id != self.node_id:
            raise PermissionError("You can only update your own products")

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(product, key):
                setattr(product, key, value)

        product.updated_at = datetime.now()

        # 保存
        await self._save_product(product)

        # 更新索引
        await self.index_manager.remove_product(product_id)
        index = self.index_manager.create_index(
            product_id=product.product_id,
            title=product.title,
            price=product.price,
            category=product.category.value,
            geohash=product.location.geohash if product.location else "",
            seller_id=self.node_id,
            seller_rep=self.node_info.reputation
        )
        await self.index_manager.publish_index(index)

        return product

    async def remove_product(self, product_id: str) -> bool:
        """删除商品"""
        product = await self._load_product(product_id)

        if not product:
            return False

        if product.seller_id != self.node_id:
            raise PermissionError("You can only remove your own products")

        product.status = "removed"
        await self._save_product(product)

        # 从索引移除
        await self.index_manager.remove_product(product_id)

        logger.info(f"Product {product_id} removed")
        return True

    async def get_my_products(self) -> List[Product]:
        """获取我发布的商品"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT product_id FROM products WHERE seller_id = ? AND status = 'active'",
            (self.node_id,)
        )

        product_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        products = []
        for pid in product_ids:
            product = await self._load_product(pid)
            if product:
                products.append(product)

        return products

    # ========================================================================
    # 商品发现
    # ========================================================================

    async def discover_products(
        self,
        latitude: float = None,
        longitude: float = None,
        category: ProductCategory = None,
        price_max: float = None,
        keywords: List[str] = None,
        radius_km: float = 10.0,
        limit: int = 20,
        strategy: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """发现商品"""
        location = None
        if latitude and longitude:
            location = GeoLocation(latitude=latitude, longitude=longitude)

        query = DiscoveryQuery(
            location=location,
            radius_km=radius_km,
            category=category,
            price_max=price_max or float('inf'),
            keywords=keywords or [],
            limit=limit
        )

        strategy_map = {
            "concentric": DiscoveryStrategy.CONCENTRIC,
            "smart": DiscoveryStrategy.SMART,
            "interest": DiscoveryStrategy.INTEREST,
            "hybrid": DiscoveryStrategy.HYBRID
        }

        results = await self.discovery.discover(
            query,
            strategy=strategy_map.get(strategy, DiscoveryStrategy.HYBRID)
        )

        return [
            {
                "product": r.product.to_dict(),
                "distance_km": r.distance_km,
                "match_score": r.match_score,
                "seller_rep": r.seller_info.reputation if r.seller_info else 0
            }
            for r in results
        ]

    # ========================================================================
    # 交易
    # ========================================================================

    async def initiate_trade(
        self,
        product_id: str,
        buyer_info: Dict[str, Any] = None
    ) -> Trade:
        """发起交易"""
        product = await self._load_product(product_id)

        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.status != "active":
            raise TradeError("Product is not available")

        # 构建买家信息
        if buyer_info:
            buyer_node = NodeInfo(
                node_id=buyer_info.get("node_id", "buyer"),
                name=buyer_info.get("name", "Buyer"),
                reputation=buyer_info.get("reputation", 100)
            )
        else:
            buyer_node = self.node_info

        # 获取卖家信息
        seller_node = NodeInfo(
            node_id=product.seller_id,
            name="Seller",
            reputation=self.reputation.get_reputation(product.seller_id)
        )

        trade = await self.trade_manager.initiate_trade(product, buyer_node, seller_node)

        logger.info(f"Trade {trade.trade_id} initiated for product {product_id}")
        return trade

    async def make_offer(
        self,
        trade_id: str,
        price: float,
        message: str = ""
    ) -> bool:
        """发起报价"""
        await self.trade_manager.make_offer(trade_id, price, message=message)
        return True

    async def accept_offer(self, offer_id: str) -> bool:
        """接受报价"""
        return await self.trade_manager.accept_offer(offer_id)

    async def confirm_payment(self, trade_id: str) -> bool:
        """确认付款"""
        return await self.trade_manager.confirm_payment(trade_id, "payment_confirmed")

    async def confirm_delivery(self, trade_id: str, delivery_code: str = None) -> bool:
        """确认交付"""
        return await self.trade_manager.confirm_delivery(trade_id, delivery_code)

    async def submit_review(
        self,
        trade_id: str,
        rating: int,
        comment: str = ""
    ) -> bool:
        """提交评价"""
        return await self.trade_manager.submit_review(trade_id, rating, comment)

    async def open_dispute(
        self,
        trade_id: str,
        reason: str,
        category: str = "quality"
    ) -> Dispute:
        """发起争议"""
        trade = self.trade_manager.get_trade(trade_id)

        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        return await self.arbitration.open_dispute(trade, reason, category)

    def get_my_trades(self) -> List[Trade]:
        """获取我的交易"""
        return self.trade_manager.get_my_trades()

    # ========================================================================
    # 信誉
    # ========================================================================

    def get_reputation(self, node_id: str = None) -> int:
        """获取信誉分"""
        if node_id is None:
            node_id = self.node_id
        return self.reputation.get_reputation(node_id)

    def get_trust_score(self, to_node_id: str) -> float:
        """获取信任度"""
        return self.reputation.get_trust_score(self.node_id, to_node_id)

    def get_reputation_level(self, node_id: str = None) -> str:
        """获取信誉等级"""
        if node_id is None:
            node_id = self.node_id
        return self.reputation.get_reputation_level(node_id)

    # ========================================================================
    # 数据库操作
    # ========================================================================

    async def _save_product(self, product: Product):
        """保存商品到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO products
            (product_id, seller_id, title, description, category, tags, price,
             negotiable, condition, quantity, images, delivery_type, delivery_range,
             location_data, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product.product_id,
            product.seller_id,
            product.title,
            product.description,
            product.category.value,
            json.dumps(product.tags),
            product.price,
            int(product.negotiable),
            product.condition,
            product.quantity,
            json.dumps([img.__dict__ for img in product.images]),
            product.delivery_type.value,
            product.delivery_range,
            json.dumps(product.location.__dict__ if product.location else None),
            product.status,
            product.created_at.isoformat(),
            product.updated_at.isoformat()
        ))

        conn.commit()
        conn.close()

    async def _load_product(self, product_id: str) -> Optional[Product]:
        """从数据库加载商品"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM products WHERE product_id = ?",
            (product_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))

        return self._row_to_product(data)

    def _row_to_product(self, data: Dict) -> Product:
        """将数据库行转换为 Product 对象"""
        location = None
        if data.get("location_data"):
            loc_data = json.loads(data["location_data"])
            if loc_data:
                location = GeoLocation(
                    latitude=loc_data["latitude"],
                    longitude=loc_data["longitude"],
                    geohash=loc_data.get("geohash", ""),
                    precision=loc_data.get("precision", 6)
                )

        images = []
        if data.get("images"):
            for img_data in json.loads(data["images"]):
                images.append(ProductImage(**img_data))

        return Product(
            product_id=data["product_id"],
            seller_id=data["seller_id"],
            title=data["title"],
            description=data.get("description", ""),
            category=ProductCategory(data.get("category", "other")),
            tags=json.loads(data.get("tags", "[]")),
            price=data.get("price", 0.0),
            negotiable=bool(data.get("negotiable", True)),
            condition=data.get("condition", "new"),
            quantity=data.get("quantity", 1),
            images=images,
            delivery_type=DeliveryType(data.get("delivery_type", "pickup")),
            delivery_range=data.get("delivery_range", 5.0),
            location=location,
            status=data.get("status", "active"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat()))
        )

    # ========================================================================
    # 消息处理
    # ========================================================================

    async def _send_message(self, msg: NetworkMessage):
        """发送网络消息"""
        if msg.receiver_id:
            await self.network.send_tcp_message(msg.receiver_id, msg)
        else:
            # 广播
            await self.network.broadcast_discovery()

    async def _handle_product_query(self, msg: NetworkMessage):
        """处理商品查询"""
        query_data = msg.payload.get("query", {})
        results = await self.discover_products(
            latitude=self.node_info.location.latitude if self.node_info.location else None,
            longitude=self.node_info.location.longitude if self.node_info.location else None,
            category=ProductCategory(query_data.get("category")) if query_data.get("category") else None,
            price_max=query_data.get("price_max"),
            keywords=query_data.get("keywords", []),
            radius_km=query_data.get("radius_km", 10.0)
        )

        # 发送响应
        for result in results[:5]:  # 限制返回数量
            response = NetworkMessage(
                msg_type=MessageType.PRODUCT_QUERY,
                sender_id=self.node_id,
                receiver_id=msg.sender_id,
                payload={
                    "product": result["product"],
                    "distance_km": result["distance_km"]
                }
            )
            await self.network.send_tcp_message(msg.sender_id, response)

    async def _handle_trade_request(self, msg: NetworkMessage):
        """处理交易请求"""
        trade_data = msg.payload
        # 转发给交易管理器
        logger.info(f"Trade request received: {trade_data}")

    async def _handle_trade_update(self, msg: NetworkMessage):
        """处理交易更新"""
        trade_data = msg.payload
        # 转发给交易管理器
        logger.info(f"Trade update received: {trade_data}")

    async def _handle_reputation(self, msg: NetworkMessage):
        """处理信誉事件"""
        event_data = msg.payload.get("event")
        if event_data:
            event = ReputationEvent(**event_data)
            await self.reputation.record_event(event)

    async def _handle_arbitration(self, msg: NetworkMessage):
        """处理仲裁消息"""
        action = msg.payload.get("action")
        logger.info(f"Arbitration message received: {action}")

    # ========================================================================
    # 广播
    # ========================================================================

    async def _broadcast_product(self, product: Product):
        """广播商品"""
        msg = NetworkMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id=self.node_id,
            sender_name=self.node_info.name,
            payload={
                "type": "product",
                "product": product.to_dict()
            },
            ttl=3
        )

        # 实际应该通过 P2P 网络广播
        logger.debug(f"Product {product.product_id} broadcasted")

    # ========================================================================
    # 统计
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "node_id": self.node_id,
            "reputation": self.node_info.reputation,
            "active_trades": len(self.trade_manager.active_trades),
            "my_products": len(asyncio.get_event_loop().run_until_complete(self.get_my_products())),
            "network_peers": len(self.network.get_alive_nodes()),
            "reputation_stats": self.reputation.get_statistics(),
            "arbitration_stats": self.arbitration.get_statistics()
        }


# ========================================================================
# 单例
# ========================================================================

_system_instance: Optional[LocalMarketSystem] = None


def get_local_market_system(config: Dict[str, Any] = None) -> LocalMarketSystem:
    """获取系统单例"""
    global _system_instance

    if _system_instance is None and config is not None:
        _system_instance = LocalMarketSystem(config)

    if _system_instance is None:
        _system_instance = LocalMarketSystem()

    return _system_instance


async def init_local_market_system(config: Dict[str, Any] = None) -> LocalMarketSystem:
    """初始化并启动系统"""
    system = get_local_market_system(config)
    await system.start()
    return system
