# core/flash_listing/listing_generator.py
# AI 商品资料生成器
#
# 基于图片特征自动生成：
# - 标题（<=20字，带卖点）
# - 描述（3行）
# - 关键参数表

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import asdict

from .models import (
    ImageFeature,
    GeneratedListing,
    ProductCondition,
    DeliveryType,
    PaymentMethod,
    check_banned_content,
    infer_category,
)

logger = logging.getLogger(__name__)


class ListingGenerator:
    """
    AI 商品资料生成器

    将视觉特征转换为标准商品资料：
    1. 分析特征文本
    2. 生成标题
    3. 生成描述
    4. 提取关键参数
    5. 违禁品检查
    """

    # 品类到标题前缀的映射
    CATEGORY_TITLE_PREFIX = {
        "electronics": "LED",
        "machinery": "工业",
        "plastic": "塑料",
        "metal": "金属材料",
        "chemical": "化工",
        "textile": "纺织",
        "food": "食品",
        "service": "服务",
        "other": "商品",
    }

    # 品类到描述模板的映射
    CATEGORY_DESC_TEMPLATES = {
        "electronics": "{material}材质{application}，功率{size}，{interface}接口，适合{scene}。",
        "machinery": "{material}{category}，规格{size}，{interface}连接，适用{scene}。",
        "plastic": "优质{type}材料，{material}材质，{size}规格，{application}。",
        "metal": "{material}制品，{size}规格，{application}，{interface}。",
        "other": "{application}用{type}，{material}材质，{size}，{interface}。",
    }

    def __init__(self, llm_client=None, config: Optional[Dict] = None):
        """
        Args:
            llm_client: LLM客户端（可选，用于高级生成）
            config: 配置字典
        """
        self.llm_client = llm_client
        self.config = config or {}

        # 回调
        self.on_progress: Optional[Callable] = None

    async def generate(
        self,
        features: ImageFeature,
        user_hints: Optional[Dict] = None,
    ) -> GeneratedListing:
        """
        从图片特征生成商品资料

        Args:
            features: 图片特征
            user_hints: 用户提示（可选），如"这是二手货"、"价格便宜"

        Returns:
            生成的商品资料
        """
        try:
            if self.on_progress:
                await self.on_progress("正在分析商品特征...", 20)

            # 1. 检查违禁品
            is_banned, ban_reason = check_banned_content(
                "", "", features
            )

            # 2. 生成标题
            title = self._generate_title(features, user_hints)
            if self.on_progress:
                await self.on_progress("正在生成标题...", 40)

            # 3. 生成描述
            description = self._generate_description(features, title, user_hints)
            if self.on_progress:
                await self.on_progress("正在生成描述...", 60)

            # 4. 提取关键参数
            key_attributes = self._extract_attributes(features)
            if self.on_progress:
                await self.on_progress("正在整理参数...", 80)

            # 5. 创建商品资料
            listing = GeneratedListing(
                title=title,
                description=description,
                key_attributes=key_attributes,
                source_features=features,
                stage="generated",
            )

            # 6. 违禁品标记
            if is_banned:
                listing.stage = "cancelled"
                logger.warning(f"[ListingGenerator] 商品被封禁: {ban_reason}")

            if self.on_progress:
                await self.on_progress("生成完成", 100)

            logger.info(f"[ListingGenerator] 商品资料生成: {title}")
            return listing

        except Exception as e:
            logger.error(f"[ListingGenerator] 生成失败: {e}")
            raise

    async def generate_with_llm(
        self,
        features: ImageFeature,
        user_hints: Optional[Dict] = None,
    ) -> GeneratedListing:
        """
        使用 LLM 生成更优质的商品资料

        Args:
            features: 图片特征
            user_hints: 用户提示

        Returns:
            生成的商品资料
        """
        if not self.llm_client:
            # 降级到规则生成
            return await self.generate(features, user_hints)

        try:
            # 构建提示词
            prompt = self._build_llm_prompt(features, user_hints)

            if self.on_progress:
                await self.on_progress("正在调用AI生成...", 30)

            # 调用 LLM
            response = await self.llm_client.generate(prompt)
            parsed = json.loads(response)

            # 解析结果
            listing = GeneratedListing(
                title=parsed.get("title", ""),
                description=parsed.get("description", ""),
                key_attributes=parsed.get("attributes", {}),
                source_features=features,
            )

            return listing

        except Exception as e:
            logger.warning(f"[ListingGenerator] LLM生成失败，降级到规则: {e}")
            return await self.generate(features, user_hints)

    def _generate_title(
        self,
        features: ImageFeature,
        user_hints: Optional[Dict] = None,
    ) -> str:
        """
        生成商品标题

        规则：
        - <=20字
        - 带卖点
        - 品类 + 核心特征
        """
        hints = user_hints or {}

        # 品类前缀
        category = features.category or "other"
        prefix = self.CATEGORY_TITLE_PREFIX.get(category, "商品")

        # 核心特征组合
        parts = [prefix]

        # 添加材质
        if features.material:
            parts.append(features.material)

        # 添加功率/尺寸
        if features.power_rating:
            parts.append(features.power_rating)
        elif features.size_estimate:
            parts.append(features.size_estimate)

        # 添加接口
        if features.interface_type:
            parts.append(features.interface_type)

        # 添加卖点（用户提示）
        if hints.get("highlight"):
            parts.append(hints["highlight"])

        # 组合标题
        title = " ".join(parts)

        # 限制长度
        if len(title) > 20:
            # 优先保留核心词
            core_parts = [prefix]
            if features.power_rating:
                core_parts.append(features.power_rating)
            if features.interface_type:
                core_parts.append(features.interface_type)
            title = " ".join(core_parts[:4])

        return title[:20]

    def _generate_description(
        self,
        features: ImageFeature,
        title: str,
        user_hints: Optional[Dict] = None,
    ) -> str:
        """
        生成商品描述

        规则：
        - 3行
        - 用途 + 参数 + 适用场景
        """
        hints = user_hints or {}
        category = features.category or "other"

        # 获取描述模板
        template = self.CATEGORY_DESC_TEMPLATES.get(
            category, self.CATEGORY_DESC_TEMPLATES["other"]
        )

        # 填充参数
        description = template.format(
            material=features.material or "优质",
            size=features.power_rating or features.size_estimate or "标准规格",
            interface=features.interface_type or "通用接口",
            application=features.application or "多种场景",
            scene=self._get_scene_description(features),
            type=features.material or "通用",
        )

        # 格式化：分成3行
        lines = [
            description[:25] + "..." if len(description) > 25 else description,
            f"规格：{features.power_rating or features.size_estimate or '见参数'}",
            f"适用：{self._get_scene_description(features)}",
        ]

        return "\n".join(lines)

    def _get_scene_description(self, features: ImageFeature) -> str:
        """获取适用场景描述"""
        if features.application:
            return features.application

        # 基于品类的默认场景
        default_scenes = {
            "electronics": "工厂/仓库/车间照明",
            "machinery": "机械设备配套",
            "plastic": "注塑/挤出加工",
            "metal": "五金加工/制造",
            "chemical": "化工生产/实验",
            "other": "多种场景",
        }

        return default_scenes.get(features.category, "通用场景")

    def _extract_attributes(self, features: ImageFeature) -> Dict[str, str]:
        """
        提取关键参数

        Returns:
            属性字典
        """
        attrs = {}

        # 基础属性
        if features.category:
            attrs["品类"] = features.category

        if features.material:
            attrs["材质"] = features.material

        if features.size_estimate:
            attrs["尺寸"] = features.size_estimate

        if features.power_rating:
            attrs["功率"] = features.power_rating

        if features.voltage:
            attrs["电压"] = features.voltage

        if features.interface_type:
            attrs["接口"] = features.interface_type

        if features.model_number:
            attrs["型号"] = features.model_number

        return attrs

    def _build_llm_prompt(
        self,
        features: ImageFeature,
        user_hints: Optional[Dict] = None,
    ) -> str:
        """构建LLM提示词"""
        hints = user_hints or {}

        prompt = f"""图片识别到：
- 品类：{features.category}（置信度 {features.category_confidence:.1%}）
- 材质：{features.material or '未知'}
- 尺寸/功率：{features.power_rating or features.size_estimate or '未知'}
- 接口：{features.interface_type or '未知'}
- 适用场景：{features.application or '未知'}
- OCR文本：{features.ocr_text or '无'}

请生成电商商品资料（JSON格式）：
{{
    "title": "标题（<=20字，带卖点）",
    "description": "描述（3行：用途+参数+适用场景）",
    "attributes": {{"型号":"", "规格":"", "材质":"", ...}}
}}

要求：
- 标题简洁有力，突出核心卖点
- 描述专业但易懂
- 属性表包含所有已知信息
"""

        if hints.get("condition"):
            prompt += f"\n用户补充：成色 {hints['condition']}"

        if hints.get("price_range"):
            prompt += f"\n用户期望价格：{hints['price_range']}"

        return prompt

    def validate_listing(self, listing: GeneratedListing) -> tuple:
        """
        验证商品资料

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        # 检查标题
        if not listing.title or len(listing.title) < 3:
            errors.append("标题太短")
        if len(listing.title) > 20:
            errors.append("标题太长（应<=20字）")

        # 检查描述
        if not listing.description:
            errors.append("描述不能为空")

        # 检查违禁品
        is_banned, reason = check_banned_content(
            listing.title, listing.description,
            listing.source_features or ImageFeature()
        )
        if is_banned:
            errors.append(f"违禁内容: {reason}")

        return len(errors) == 0, errors


# ========== 便捷函数 ==========

async def generate_listing(
    features: ImageFeature,
    user_hints: Optional[Dict] = None,
    llm_client=None,
) -> GeneratedListing:
    """快捷函数：生成商品资料"""
    generator = ListingGenerator(llm_client=llm_client)
    return await generator.generate(features, user_hints)
