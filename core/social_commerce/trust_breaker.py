# core/social_commerce/trust_breaker.py
# AI 信任破冰 - 从沉默到对话的系统级搭讪
#
# 核心能力：
# 1. 场景化开场白生成
# 2. 渐进披露机制
# 3. 消除"陌生推销"抵触

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import random

from .models import (
    NodeProfile,
    MatchCandidate,
    IcebreakerMessage,
    MatchStrength,
)


class TrustBreaker:
    """
    AI 信任破冰器

    根据匹配场景生成自然的开场白，实现买卖双方的破冰对话：
    - 同款搜索 → 拼单/互换渠道
    - 上下游 → 供需对接
    - 地理邻近 → 面交推荐
    """

    # 场景模板
    SCENE_TEMPLATES = {
        "same_search": {
            "intro": [
                "你们都在找「{keyword}」，或许可以拼单降低单价？",
                "看起来你们有相同的需求，要不要考虑一起采购？",
                "发现你们在找同样的东西，或许可以互相分享渠道？",
            ],
            "context": "你们都在关注 {keyword}",
        },
        "上下游": {
            "intro": [
                "你在找「{upstream}」，他在卖「{downstream}」，要不要对接一下？",
                "你们的业务看起来是上下游关系，有机会合作吗？",
                "发现一个潜在的供需匹配，你们的业务可能有互补性",
            ],
            "context": "你关注 {upstream}，他提供 {downstream}",
        },
        "nearby": {
            "intro": [
                "你们都在 {location} 附近，或许可以约面交，省去物流费用",
                "发现你们地理位置很近，要不要考虑当面交易？",
                "你们在同一区域，或许有机会直接见面聊聊",
            ],
            "context": "你们都在 {location} 附近",
        },
        "same_seller": {
            "intro": [
                "你们都对「{seller}」的商品感兴趣，或许可以一起询价",
                "发现你们在看同一家供应商的产品，也许能拿到更好的价格",
            ],
            "context": "你们都关注了 {seller}",
        },
        "urgent": {
            "intro": [
                "你急着找「{keyword}」，他刚好有货源，要不要快速对接？",
                "发现你很急需，而他正好有，可以优先联系",
            ],
            "context": "你的需求比较紧急",
        },
    }

    # 破冰强度等级
    ICE_LEVELS = {
        "gentle": {
            "disclosure": "只透露"你们有相同需求"",
            "contact_exchange": False,
            "info_shared": [],
        },
        "moderate": {
            "disclosure": "透露具体需求关键词",
            "contact_exchange": False,
            "info_shared": ["需求标签"],
        },
        "bold": {
            "disclosure": "直接交换联系方式",
            "contact_exchange": True,
            "info_shared": ["联系方式", "具体需求"],
        },
    }

    def __init__(self):
        self._generated_messages: Dict[str, IcebreakerMessage] = {}

    def generate_icebreaker(
        self,
        candidate: MatchCandidate,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
        scene_type: str = None,
    ) -> IcebreakerMessage:
        """
        生成破冰消息

        Args:
            candidate: 匹配候选
            buyer_profile: 买家画像
            seller_profile: 卖家画像
            scene_type: 场景类型 (不指定则自动判断)

        Returns:
            IcebreakerMessage 对象
        """
        # 自动判断场景
        if scene_type is None:
            scene_type = self._detect_scene(candidate, buyer_profile, seller_profile)

        # 获取模板
        template = self.SCENE_TEMPLATES.get(scene_type, self.SCENE_TEMPLATES["same_search"])

        # 填充变量
        intro = random.choice(template["intro"])
        context = template["context"]

        # 根据场景填充关键词
        keywords = list(set(buyer_profile.intent_keywords + seller_profile.intent_keywords))
        keyword = keywords[0] if keywords else "相关商品"

        intro_filled = intro.format(
            keyword=keyword,
            upstream=", ".join(buyer_profile.intent_keywords[:2]),
            downstream=", ".join(seller_profile.intent_keywords[:2]),
            location=self._get_location_name(buyer_profile),
            seller=seller_profile.name or "该供应商",
        )

        context_filled = context.format(
            keyword=keyword,
            upstream=", ".join(buyer_profile.intent_keywords[:2]),
            downstream=", ".join(seller_profile.intent_keywords[:2]),
            location=self._get_location_name(buyer_profile),
            seller=seller_profile.name or "该供应商",
        )

        # 构建消息
        message = IcebreakerMessage(
            scene_type=scene_type,
            buyer_id=candidate.buyer_id,
            seller_id=candidate.seller_id,
            intro_message=intro_filled,
            shared_context=context_filled,
        )

        # 根据匹配强度决定披露程度
        if candidate.match_strength in (MatchStrength.PERFECT, MatchStrength.STRONG):
            # 强匹配：更积极的破冰
            message.intro_message = message.intro_message.replace("或许", "")
            message.intro_message = message.intro_message.replace("要不要", "建议你们")

        # 存储
        self._generated_messages[message.message_id] = message
        return message

    def _detect_scene(
        self,
        candidate: MatchCandidate,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
    ) -> str:
        """自动检测场景类型"""
        # 上下游关系优先
        if candidate.is上下游:
            return "上下游"

        # 地理邻近
        if candidate.geo_score >= 0.7:
            return "nearby"

        # 紧急需求
        if "紧急需求" in buyer_profile.intent_tags:
            return "urgent"

        # 同行 (相同关键词)
        common_kw = set(buyer_profile.intent_keywords) & set(seller_profile.intent_keywords)
        if common_kw:
            return "same_search"

        return "same_search"

    def _get_location_name(self, profile: NodeProfile) -> str:
        """获取位置名称 (简化)"""
        if hasattr(profile, "location") and profile.location:
            geohash = profile.location.geohash
            if geohash:
                # 简化：返回 GeoHash 前缀
                return f"{geohash[:4]}区域"
        return "同一区域"

    def get_icebreaker(self, message_id: str) -> Optional[IcebreakerMessage]:
        """获取已生成的破冰消息"""
        return self._generated_messages.get(message_id)

    def accept_icebreaker(
        self,
        message_id: str,
        accepter_id: str,
    ) -> Tuple[bool, str]:
        """
        接受破冰

        Args:
            message_id: 消息ID
            accepter_id: 接受者ID

        Returns:
            (success, response_message)
        """
        message = self._generated_messages.get(message_id)
        if not message:
            return False, "消息不存在"

        # 标记接受
        if accepter_id == message.buyer_id:
            message.buyer_accepted = True
        elif accepter_id == message.seller_id:
            message.seller_accepted = True
        else:
            return False, "你不是接收方"

        # 检查是否可以交换联系方式
        if message.can_exchange_contact():
            message.contact_exchanged = True
            return True, "已交换联系方式，可以开始直接沟通了"
        else:
            return True, "已记录，继续等待对方确认"

    def reject_icebreaker(
        self,
        message_id: str,
        rejecter_id: str,
        reason: str = "",
    ) -> IcebreakerMessage:
        """拒绝破冰"""
        message = self._generated_messages.get(message_id)
        if message:
            message.buyer_accepted = False
            message.seller_accepted = False

        return message

    def generate_response_suggestions(
        self,
        message: IcebreakerMessage,
        responder_id: str,
    ) -> List[str]:
        """
        生成响应建议

        根据破冰消息，生成几个可选的响应模板
        """
        suggestions = []

        if responder_id == message.buyer_id:
            # 买家响应
            suggestions = [
                "好的，我可以考虑拼单",
                "我先看看他的商品详情",
                "谢谢推荐，我先联系试试",
            ]
        else:
            # 卖家响应
            suggestions = [
                "欢迎合作，我的商品链接是...",
                "可以拼单，具体需求请联系我",
                "好的，请告诉我您的采购量",
            ]

        return suggestions

    def compute_trust_score(
        self,
        message: IcebreakerMessage,
    ) -> float:
        """
        计算破冰消息的信任分

        基于：
        - 场景匹配度
        - 匹配强度
        - 双方历史信用
        """
        base_score = 0.5

        # 场景加成
        scene_bonus = {
            "上下游": 0.2,
            "nearby": 0.15,
            "urgent": 0.1,
            "same_search": 0.05,
        }.get(message.scene_type, 0)

        # 匹配强度加成 (通过 shared_context 长度间接衡量)
        context_len = len(message.shared_context)
        strength_bonus = min(context_len / 100, 0.2)

        return min(base_score + scene_bonus + strength_bonus, 1.0)


# ========== 渐进披露管理器 ==========

class GradualDisclosure:
    """
    渐进披露管理器

    控制信息交换的节奏，保护隐私：
    Level 1: 仅知道"有人有类似需求"
    Level 2: 知道具体需求标签
    Level 3: 知道具体需求+商品
    Level 4: 交换联系方式
    """

    LEVELS = {
        1: {"name": "匿名匹配", "disclosure": "你们有相同需求"},
        2: {"name": "标签匹配", "disclosure": "需求标签匹配"},
        3: {"name": "商品匹配", "disclosure": "知道具体商品"},
        4: {"name": "完全披露", "disclosure": "交换联系方式"},
    }

    @classmethod
    def get_disclosure_level(
        cls,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
        match_strength: MatchStrength,
    ) -> int:
        """
        确定披露等级

        规则：
        - 完美匹配 → 可快速到 Level 4
        - 强匹配 → Level 3
        - 中等匹配 → Level 2
        - 弱匹配 → Level 1
        """
        # 基于匹配强度
        strength_levels = {
            MatchStrength.PERFECT: 4,
            MatchStrength.STRONG: 3,
            MatchStrength.MEDIUM: 2,
            MatchStrength.WEAK: 1,
            MatchStrength.NONE: 1,
        }

        base_level = strength_levels.get(match_strength, 1)

        # 基于信用调整
        credit_bonus = 0
        if buyer_profile.credit_score >= 80:
            credit_bonus += 1
        if seller_profile.credit_score >= 80:
            credit_bonus += 1

        # 基于交易历史
        history_bonus = 0
        if buyer_profile.total_deals >= 10:
            history_bonus += 1
        if seller_profile.total_deals >= 10:
            history_bonus += 1

        level = base_level + (credit_bonus + history_bonus) // 2
        return min(level, 4)

    @classmethod
    def get_disclosure_message(
        cls,
        level: int,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
    ) -> str:
        """获取对应等级的披露消息"""
        if level == 1:
            return "发现有其他用户有类似需求"
        elif level == 2:
            tags = buyer_profile.intent_tags[:3]
            return f"有用户关注: {', '.join(tags)}"
        elif level == 3:
            keywords = buyer_profile.intent_keywords[:2]
            return f"有人想买: {', '.join(keywords)}"
        elif level >= 4:
            return "双方确认后可交换联系方式"
        return ""


# ========== 全局管理器 ==========

class TrustBreakerManager:
    """信任破冰管理器"""

    _instance = None

    def __init__(self):
        self.breaker = TrustBreaker()

    @classmethod
    def get_instance(cls) -> "TrustBreakerManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_match_intro(
        self,
        candidate: MatchCandidate,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
    ) -> IcebreakerMessage:
        """创建匹配介绍"""
        return self.breaker.generate_icebreaker(
            candidate, buyer_profile, seller_profile
        )

    def accept_intro(
        self,
        message_id: str,
        accepter_id: str,
    ) -> Tuple[bool, str]:
        """接受介绍"""
        return self.breaker.accept_icebreaker(message_id, accepter_id)

    def get_pending_introductions(self, node_id: str) -> List[IcebreakerMessage]:
        """获取待处理的介绍"""
        pending = []
        for msg in self.breaker._generated_messages.values():
            if (msg.buyer_id == node_id or msg.seller_id == node_id):
                if not msg.buyer_accepted or not msg.seller_accepted:
                    pending.append(msg)
        return pending


def get_trust_breaker() -> TrustBreakerManager:
    """获取信任破冰管理器"""
    return TrustBreakerManager.get_instance()