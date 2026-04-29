# core/flash_listing/flash_listing_engine.py
# 对话式闪电上架引擎
#
# 整合所有模块，实现五步上架流程：
# 1. 📸 图片特征提取
# 2. 📝 AI 生成商品资料
# 3. 🏷️ 生成商品标签
# 4. 🤝 聊天内嵌购买
# 5. 📦 履约与信任闭环

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from .models import (
    FlashListingSession,
    GeneratedListing,
    ImageFeature,
    ListingStage,
    ProductCondition,
    DeliveryType,
    PaymentMethod,
    InlinePurchase,
)

from .vision_analyzer import VisionAnalyzer
from .listing_generator import ListingGenerator
from .product_link import ProductLinkGenerator, ProductLink
from .inline_purchase import InlinePurchaseManager
from .fulfillment import FulfillmentManager

logger = logging.getLogger(__name__)


class FlashListingEngine:
    """
    对话式闪电上架引擎

    使用流程：
    1. start_session() - 开始上架会话
    2. upload_images() - 上传图片
    3. confirm_listing() - 确认商品资料
    4. publish() - 发布商品
    5. get_product_link() - 获取商品链接
    """

    def __init__(self, node_id: str, config: Optional[Dict] = None):
        """
        Args:
            node_id: 当前节点ID
            config: 配置字典
        """
        self.node_id = node_id
        self.config = config or {}

        # 子模块
        self.vision_analyzer = VisionAnalyzer(config=self.config.get("vision"))
        self.listing_generator = ListingGenerator(config=self.config.get("listing"))
        self.link_generator = ProductLinkGenerator(node_id, config=self.config.get("link"))
        self.purchase_manager = InlinePurchaseManager(node_id, config=self.config.get("purchase"))
        self.fulfillment_manager = FulfillmentManager(node_id, config=self.config.get("fulfillment"))

        # 会话存储
        self.sessions: Dict[str, FlashListingSession] = {}

        # LLM 客户端（可选）
        self.llm_client = None

        # 回调
        self.on_stage_change: Optional[Callable] = None
        self.on_published: Optional[Callable] = None

    def start_session(self, user_id: str) -> FlashListingSession:
        """
        开始上架会话

        Args:
            user_id: 用户ID

        Returns:
            新的会话
        """
        session = FlashListingSession(
            user_id=user_id,
            node_id=self.node_id,
            current_stage=ListingStage.RAW_IMAGE,
        )

        self.sessions[session.session_id] = session

        logger.info(f"[FlashListingEngine] 开始上架会话: {session.session_id}")
        return session

    async def upload_images(
        self,
        session_id: str,
        image_paths: List[str],
    ) -> List[ImageFeature]:
        """
        上传并分析图片

        Args:
            session_id: 会话ID
            image_paths: 图片路径列表

        Returns:
            提取的特征列表
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 添加图片
        session.uploaded_images.extend(image_paths)

        # 分析图片
        features = await self.vision_analyzer.analyze_images_batch(image_paths)

        # 转换并保存
        for i, feat_dict in enumerate(features):
            feature = ImageFeature(**feat_dict) if isinstance(feat_dict, dict) else feat_dict
            session.extracted_features.append(feature)

        # 更新阶段
        session.current_stage = ListingStage.FEATURE_EXTRACTED

        logger.info(f"[FlashListingEngine] 图片分析完成: {len(features)} 张")
        return session.extracted_features

    async def generate_listing(
        self,
        session_id: str,
        user_hints: Optional[Dict] = None,
    ) -> GeneratedListing:
        """
        生成商品资料

        Args:
            session_id: 会话ID
            user_hints: 用户提示

        Returns:
            生成的商品资料
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        if not session.extracted_features:
            raise ValueError("请先上传图片")

        # 使用第一张图片的特征（简化：取第一张）
        primary_feature = session.extracted_features[0]

        # 生成商品资料
        if self.llm_client:
            listing = await self.listing_generator.generate_with_llm(
                primary_feature, user_hints
            )
        else:
            listing = await self.listing_generator.generate(
                primary_feature, user_hints
            )

        # 保存
        session.generated_listing = listing
        session.current_stage = ListingStage.GENERATED

        # 违禁品检查
        if listing.stage == "cancelled":
            session.is_blocked = True
            session.error_message = "商品包含违禁内容，无法发布"

        logger.info(f"[FlashListingEngine] 商品资料生成: {listing.title}")
        return listing

    async def update_listing(
        self,
        session_id: str,
        title: Optional[str] = None,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
        condition: Optional[str] = None,
        delivery_options: Optional[List[str]] = None,
        payment_options: Optional[List[str]] = None,
    ) -> GeneratedListing:
        """
        更新商品资料（用户编辑）

        Args:
            session_id: 会话ID
            title: 新标题
            price: 新价格
            quantity: 新数量
            condition: 新成色
            delivery_options: 交货方式
            payment_options: 支付方式

        Returns:
            更新后的商品资料
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        listing = session.generated_listing
        if not listing:
            raise ValueError("请先生成商品资料")

        # 更新字段
        if title is not None:
            listing.title = title
            session.user_edited_title = title

        if price is not None:
            listing.price = price
            session.user_edited_price = price

        if quantity is not None:
            listing.quantity = quantity
            session.user_edited_quantity = quantity

        if condition:
            listing.condition = ProductCondition(condition)

        if delivery_options:
            listing.delivery_options = [DeliveryType(d) for d in delivery_options]

        if payment_options:
            listing.payment_options = [PaymentMethod(p) for p in payment_options]

        # 用户已确认
        session.user_confirmed = True

        logger.info(f"[FlashListingEngine] 商品资料已更新: {listing.title}")
        return listing

    async def publish(self, session_id: str) -> ProductLink:
        """
        发布商品

        Args:
            session_id: 会话ID

        Returns:
            商品链接
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        if not session.can_publish:
            raise ValueError(f"当前状态无法发布: {session.current_stage.value}")

        listing = session.generated_listing

        # 生成伪域名链接
        product_link = self.link_generator.generate_link(
            listing_id=listing.listing_id,
            title=listing.title,
        )

        # 更新 listing
        listing.product_link = product_link.full_link

        # 更新 session
        session.product_link = product_link
        session.current_stage = ListingStage.PUBLISHED

        # 更新 listing stage
        listing.stage = ListingStage.PUBLISHED

        logger.info(f"[FlashListingEngine] 商品已发布: {product_link.full_link}")

        # 回调
        if self.on_published:
            await self.on_published(session, product_link)

        return product_link

    async def create_purchase(
        self,
        listing_id: str,
        buyer_id: str,
        seller_id: str,
        product_info: Dict[str, Any],
        price: float,
    ) -> InlinePurchase:
        """
        创建购买订单

        Args:
            listing_id: 商品ID
            buyer_id: 买家ID
            seller_id: 卖家ID
            product_info: 商品信息
            price: 价格

        Returns:
            购买订单
        """
        return await self.purchase_manager.create_purchase(
            listing_id, buyer_id, seller_id, product_info, price
        )

    def get_session(self, session_id: str) -> Optional[FlashListingSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_user_sessions(self, user_id: str) -> List[FlashListingSession]:
        """获取用户的所有会话"""
        return [s for s in self.sessions.values() if s.user_id == user_id]

    async def cancel_session(self, session_id: str) -> bool:
        """
        取消会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.current_stage = ListingStage.CANCELLED
        logger.info(f"[FlashListingEngine] 会话已取消: {session_id}")
        return True


# ========== 单例访问 ==========

_flash_engine_instance: Optional[FlashListingEngine] = None


def get_flash_listing_engine(node_id: str = "", config: Optional[Dict] = None) -> FlashListingEngine:
    """
    获取闪电上架引擎单例

    Args:
        node_id: 节点ID（首次必须提供）
        config: 配置

    Returns:
        引擎实例
    """
    global _flash_engine_instance

    if _flash_engine_instance is None:
        if not node_id:
            raise ValueError("首次调用必须提供 node_id")
        _flash_engine_instance = FlashListingEngine(node_id, config)

    return _flash_engine_instance


def reset_flash_listing_engine():
    """重置引擎单例（用于测试）"""
    global _flash_engine_instance
    _flash_engine_instance = None


# ========== 便捷函数 ==========

async def quick_listing(
    node_id: str,
    image_path: str,
    user_hints: Optional[Dict] = None,
) -> tuple:
    """
    快捷上架：一步完成

    Args:
        node_id: 节点ID
        image_path: 图片路径
        user_hints: 用户提示

    Returns:
        (listing, product_link)
    """
    engine = get_flash_listing_engine(node_id)

    # 开始会话
    session = engine.start_session("temp_user")

    try:
        # 上传图片
        await engine.upload_images(session.session_id, [image_path])

        # 生成商品资料
        listing = await engine.generate_listing(session.session_id, user_hints)

        # 更新用户确认
        if user_hints:
            await engine.update_listing(
                session.session_id,
                price=user_hints.get("price"),
                quantity=user_hints.get("quantity"),
                condition=user_hints.get("condition"),
            )
        else:
            listing.price = user_hints.get("price", 0) if user_hints else 0
            session.user_confirmed = True

        # 发布
        product_link = await engine.publish(session.session_id)

        return listing, product_link

    except Exception as e:
        await engine.cancel_session(session.session_id)
        raise


# ========== 使用示例 ==========

async def example_usage():
    """使用示例"""
    # 获取引擎
    engine = get_flash_listing_engine("node_8848")

    # 开始会话
    session = engine.start_session("user_123")

    # 1. 上传图片
    features = await engine.upload_images(
        session.session_id,
        ["/path/to/product.jpg"]
    )
    print(f"识别到: {features[0].category}")

    # 2. 生成商品资料
    listing = await engine.generate_listing(
        session.session_id,
        user_hints={"condition": "new", "highlight": "工厂直供"}
    )
    print(f"生成标题: {listing.title}")
    print(f"生成描述:\n{listing.description}")

    # 3. 用户确认并补充价格
    await engine.update_listing(
        session.session_id,
        price=299.0,
        quantity=100,
        condition="new",
        delivery_options=["express", "face_to_face"],
        payment_options=["wechat_pay", "alipay", "escrow"],
    )

    # 4. 发布
    product_link = await engine.publish(session.session_id)
    print(f"商品链接: {product_link.full_link}")
    print(f"展示文案: {product_link.display_text}")

    # 5. 生成可点击卡片
    card = engine.link_generator.generate_markdown_card(
        product_link,
        title=listing.title,
        price=299.0,
    )
    print(f"商品卡片:\n{card}")


if __name__ == "__main__":
    asyncio.run(example_usage())
