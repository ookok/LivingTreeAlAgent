# core/social_commerce/matchmaking_engine.py
# 撮合引擎 - 整合意图雷达、时空匹配、AI破冰、信用网络
#
# 核心流程：
# 1. 收集候选 (意图雷达筛选)
# 2. 时空过滤 (地理位置+时间窗口)
# 3. 信用排序 (信用分+信任关系)
# 4. AI 破冰 (生成开场白)
# 5. 撮合确认 (成交)

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from .models import (
    NodeProfile,
    NodeType,
    MatchCandidate,
    MatchStrength,
    MatchSession,
    IcebreakerMessage,
    GeoLocation,
    TradeStatus,
)
from .intent_radar import IntentRadar, IntentRadarManager, get_intent_radar
from .spacetime_matcher import SpacetimeMatcher, SpacetimeMatcherManager, get_spacetime_matcher
from .trust_breaker import TrustBreaker, TrustBreakerManager, get_trust_breaker
from .credit_network import CreditNetwork, CreditNetworkManager, get_credit_network


class MatchmakingEngine:
    """
    撮合引擎

    整合四大模块：
    1. IntentRadar - 意图雷达
    2. SpacetimeMatcher - 时空匹配
    3. TrustBreaker - AI 破冰
    4. CreditNetwork - 信用网络
    """

    # 撮合参数
    MIN_MATCH_SCORE = 0.3        # 最小撮合分
    GEO_WEIGHT = 0.3            # 地理权重
    TIME_WEIGHT = 0.2           # 时间权重
    INTENT_WEIGHT = 0.3         # 意图权重
    CREDIT_WEIGHT = 0.2          # 信用权重

    def __init__(self):
        # 依赖的模块
        self._intent_radar = get_intent_radar()
        self._spacetime = get_spacetime_matcher()
        self._trust_breaker = get_trust_breaker()
        self._credit = get_credit_network()

        # 撮合会话
        self._sessions: Dict[str, MatchSession] = {}

        # 撮合历史
        self._match_history: List[Dict] = []

    def find_matches_for_buyer(
        self,
        buyer_id: str,
        limit: int = 20,
    ) -> List[MatchCandidate]:
        """
        为买家寻找匹配候选

        流程：
        1. 意图雷达 → 筛选潜在卖家
        2. 时空匹配 → 过滤地理/时间不合适的
        3. 信用排序 → 按信用分排序
        """
        buyer = self._intent_radar.get_profile(buyer_id)
        if not buyer:
            return []

        # Step 1: 意图雷达匹配
        intent_matches = self._intent_radar.match_buyer_to_sellers(buyer_id)

        candidates = []
        current_hour = datetime.now().hour

        for seller, strength, reasons in intent_matches:
            # Step 2: 时空匹配
            buyer_loc = getattr(buyer, "location", None) or GeoLocation()
            seller_loc = getattr(seller, "location", None) or GeoLocation()

            geo_score = self._spacetime.matcher.compute_geo_score(buyer_loc, seller_loc)
            time_score = self._spacetime.matcher.compute_time_score(
                buyer_loc, seller_loc, current_hour
            )

            # Step 3: 计算综合分
            intent_score = {
                MatchStrength.PERFECT: 1.0,
                MatchStrength.STRONG: 0.8,
                MatchStrength.MEDIUM: 0.5,
                MatchStrength.WEAK: 0.2,
                MatchStrength.NONE: 0.0,
            }.get(strength, 0.0)

            credit_score = self._credit.network.get_credit_score(seller.node_id) / 100.0

            # 综合撮合分
            match_score = (
                intent_score * self.INTENT_WEIGHT +
                geo_score * self.GEO_WEIGHT +
                time_score * self.TIME_WEIGHT +
                credit_score * self.CREDIT_WEIGHT
            )

            if match_score < self.MIN_MATCH_SCORE:
                continue

            # 构建候选
            candidate = MatchCandidate(
                buyer_id=buyer_id,
                seller_id=seller.node_id,
                buyer_wants=buyer.intent_keywords,
                seller_offers=seller.intent_keywords,
                match_strength=strength,
                match_reasons=reasons,
                geo_score=geo_score,
                time_score=time_score,
            )

            # 检查上下游
            if self._is_upstream_downstream(buyer, seller):
                candidate.is上下游 = True

            candidates.append(candidate)

        # 按匹配分排序
        candidates.sort(key=lambda c: c.compute_match_score(), reverse=True)
        return candidates[:limit]

    def _is_upstream_downstream(self, buyer: NodeProfile, seller: NodeProfile) -> bool:
        """检测上下游关系"""
        buyer_kw = set(buyer.intent_keywords)
        seller_cat = set(seller.category_expertise.keys())

        # 简单检查：买家关键词是否包含卖家专长品类
        for cat in seller_cat:
            if cat.lower() in str(list(buyer_kw)).lower():
                return True
        return False

    def create_match_session(
        self,
        candidate: MatchCandidate,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
    ) -> MatchSession:
        """
        创建撮合会话

        自动触发 AI 破冰
        """
        # 创建会话
        session = MatchSession(
            initiator_id=candidate.buyer_id,
            recipient_id=candidate.seller_id,
            candidate=candidate,
            status=TradeStatus.PROPOSED,
        )

        # 生成 AI 破冰消息
        icebreaker = self._trust_breaker.create_match_intro(
            candidate, buyer_profile, seller_profile
        )
        session.icebreaker = icebreaker
        candidate.icebreaker_message = icebreaker.intro_message
        candidate.icebreaker_type = icebreaker.scene_type

        # 存储会话
        self._sessions[session.session_id] = session

        # 更新意图雷达
        self._intent_radar.add_signal(
            candidate.buyer_id,
            "match_proposed",
            {"seller_id": candidate.seller_id, "session_id": session.session_id}
        )

        return session

    def accept_match(
        self,
        session_id: str,
        accepter_id: str,
    ) -> Tuple[bool, str]:
        """
        接受撮合

        触发：
        1. 更新会话状态
        2. 记录信用事件
        3. 通知对方
        """
        session = self._sessions.get(session_id)
        if not session:
            return False, "会话不存在"

        if session.status != TradeStatus.PROPOSED:
            return False, "会话状态不允许接受"

        # 标记接受
        success, msg = self._trust_breaker.accept_intro(
            session.icebreaker.message_id if session.icebreaker else "",
            accepter_id
        )

        if not success:
            return False, msg

        # 更新会话状态
        if accepter_id == session.initiator_id:
            session.status = TradeStatus.NEGOTIATING
        elif accepter_id == session.recipient_id:
            session.status = TradeStatus.NEGOTIATING
        else:
            return False, "你不是会话参与方"

        session.updated_at = datetime.now().timestamp()

        # 添加信用事件
        if session.icebreaker and session.icebreaker.contact_exchanged:
            self._credit.add_deal_credit(
                from_node=session.initiator_id,
                to_node=session.recipient_id,
                rating=4.0,
                comment="通过撮合成交",
            )

        return True, "撮合已确认，可以开始协商"

    def propose_price(
        self,
        session_id: str,
        proposer_id: str,
        price: int,
    ) -> Tuple[bool, str]:
        """
        发起报价/还价
        """
        session = self._sessions.get(session_id)
        if not session:
            return False, "会话不存在"

        if session.status != TradeStatus.NEGOTIATING:
            return False, "会话状态不允许报价"

        if proposer_id == session.initiator_id:
            session.buyer_offer = price
        elif proposer_id == session.recipient_id:
            session.seller_counter = price
        else:
            return False, "你不是会话参与方"

        session.updated_at = datetime.now().timestamp()
        return True, f"报价 {price/100:.2f} 元已记录"

    def confirm_deal(
        self,
        session_id: str,
        confirmer_id: str,
    ) -> Tuple[bool, str]:
        """
        确认成交
        """
        session = self._sessions.get(session_id)
        if not session:
            return False, "会话不存在"

        if not (session.buyer_offer and session.seller_counter):
            return False, "双方尚未报价"

        # 检查是否达成一致 (简化：取平均值)
        final_price = (session.buyer_offer + session.seller_counter) // 2

        session.status = TradeStatus.IN_PROGRESS
        session.updated_at = datetime.now().timestamp()

        # 记录到历史
        self._match_history.append({
            "session_id": session_id,
            "buyer_id": session.initiator_id,
            "seller_id": session.recipient_id,
            "price": final_price,
            "timestamp": datetime.now().timestamp(),
        })

        # 更新节点交易数
        buyer = self._intent_radar.get_profile(session.initiator_id)
        seller = self._intent_radar.get_profile(session.recipient_id)
        if buyer:
            buyer.total_deals += 1
        if seller:
            seller.total_deals += 1

        return True, f"成交价格: {final_price/100:.2f} 元"

    def get_session(self, session_id: str) -> Optional[MatchSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    def get_user_sessions(
        self,
        user_id: str,
        status: TradeStatus = None,
    ) -> List[MatchSession]:
        """获取用户的所有会话"""
        sessions = []

        for session in self._sessions.values():
            if session.initiator_id == user_id or session.recipient_id == user_id:
                if status is None or session.status == status:
                    sessions.append(session)

        # 按更新时间排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_match_statistics(self) -> Dict:
        """获取撮合统计"""
        total = len(self._sessions)
        proposed = sum(1 for s in self._sessions.values() if s.status == TradeStatus.PROPOSED)
        negotiating = sum(1 for s in self._sessions.values() if s.status == TradeStatus.NEGOTIATING)
        completed = sum(1 for s in self._sessions.values() if s.status == TradeStatus.COMPLETED)

        return {
            "total_sessions": total,
            "proposed": proposed,
            "negotiating": negotiating,
            "completed": completed,
            "total_matches": len(self._match_history),
        }


# ========== 碎片产能撮合器 ==========

class FragmentedMatchmaker:
    """
    碎片产能撮合器

    将小订单拆给附近闲散节点，实现分布式柔性制造
    """

    def __init__(self, engine: MatchmakingEngine):
        self._engine = engine

    def split_order(
        self,
        requirement: str,
        quantity: int,
        category: str,
        deadline: float,
        nearby_nodes: List[Tuple[str, float]],
    ) -> List[Dict]:
        """
        拆分订单

        Args:
            requirement: 需求描述
            quantity: 总数量
            category: 品类
            deadline: 截止时间
            nearby_nodes: [(node_id, distance), ...]

        Returns:
            [{"node_id": "xxx", "quantity": 20, "reason": "最近"}, ...]
        """
        if not nearby_nodes:
            return []

        # 简化的分配策略：
        # 1. 按距离排序
        # 2. 优先分配给最近的节点
        # 3. 每个节点最多承接 50% 的量

        fragments = []
        remaining = quantity
        max_per_node = quantity // 2

        for node_id, distance in nearby_nodes:
            if remaining <= 0:
                break

            # 计算分配量
            alloc = min(remaining, max_per_node)

            # 根据距离调整
            if distance > 0.5:  # 远距离节点少分配
                alloc = min(alloc, quantity // 4)

            fragments.append({
                "node_id": node_id,
                "quantity": alloc,
                "reason": f"距离 {distance:.2f}",
            })

            remaining -= alloc

        return fragments

    def find_production_nodes(
        self,
        capability_type: str,
        location: GeoLocation,
        quantity: int,
    ) -> List[Tuple[str, float]]:
        """
        查找生产节点

        Args:
            capability_type: 产能类型 (如 "3d_print")
            location: 位置
            quantity: 需要的数量

        Returns:
            [(node_id, distance), ...]
        """
        # 简化：使用时空匹配器查找附近节点
        matcher = get_spacetime_matcher()

        nearby = matcher.matcher.find_nearby_nodes(
            location,
            datetime.now().hour,
            max_distance=1.0,
        )

        # 过滤可用节点
        results = []
        for node_id, distance in nearby:
            profile = self._engine._intent_radar.get_profile(node_id)
            if profile and profile.category_expertise.get(capability_type, 0) > 0:
                results.append((node_id, distance))

        return results[:10]


# ========== 应急交易网 ==========

class EmergencyTradeNetwork:
    """
    应急交易网

    灾难/短缺期间，优先路由到有存货的附近节点
    """

    def __init__(self, engine: MatchmakingEngine):
        self._engine = engine
        self._emergency_categories: Set[str] = {"药品", "食品", "发电机", "水", "燃油"}

    def is_emergency_category(self, category: str) -> bool:
        """检查是否是应急品类"""
        return any(cat in category for cat in self._emergency_categories)

    def find_emergency_supply(
        self,
        category: str,
        location: GeoLocation,
        urgency: str = "normal",
    ) -> List[Tuple[str, float]]:
        """
        查找应急物资供应

        优先级：
        1. 附近节点
        2. 高信用分节点
        3. 历史无违约节点
        """
        # 使用撮合引擎的匹配逻辑
        candidates = self._engine.find_matches_for_buyer("emergency_buyer", limit=50)

        results = []
        for candidate in candidates:
            if self.is_emergency_category(candidate.seller_id):
                seller = self._engine._intent_radar.get_profile(candidate.seller_id)
                if seller and seller.category_expertise.get(category, 0) > 0:
                    score = candidate.geo_score * 0.5 + candidate.time_score * 0.5
                    results.append((candidate.seller_id, score))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:20]


# ========== 全局管理器 ==========

class MatchmakingManager:
    """撮合管理器"""

    _instance = None

    def __init__(self):
        self._engine = MatchmakingEngine()
        self._fragmented = FragmentedMatchmaker(self._engine)
        self._emergency = EmergencyTradeNetwork(self._engine)

    @classmethod
    def get_instance(cls) -> "MatchmakingManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def find_matches(self, buyer_id: str) -> List[MatchCandidate]:
        """为买家寻找匹配"""
        return self._engine.find_matches_for_buyer(buyer_id)

    def create_match(self, buyer_id: str, seller_id: str) -> Optional[MatchSession]:
        """创建撮合"""
        buyer = get_intent_radar().get_profile(buyer_id)
        seller = get_intent_radar().get_profile(seller_id)

        if not buyer or not seller:
            return None

        # 创建候选
        candidate = MatchCandidate(
            buyer_id=buyer_id,
            seller_id=seller_id,
            buyer_wants=buyer.intent_keywords,
            seller_offers=seller.intent_keywords,
        )

        return self._engine.create_match_session(candidate, buyer, seller)

    def get_session(self, session_id: str) -> Optional[MatchSession]:
        """获取会话"""
        return self._engine.get_session(session_id)

    def get_user_sessions(self, user_id: str) -> List[MatchSession]:
        """获取用户会话"""
        return self._engine.get_user_sessions(user_id)

    def get_stats(self) -> Dict:
        """获取统计"""
        return self._engine.get_match_statistics()

    def split_fragmented_order(
        self,
        requirement: str,
        quantity: int,
        category: str,
        deadline: float,
    ) -> List[Dict]:
        """拆分碎片订单"""
        # 简化：返回空
        return []

    def find_emergency(self, category: str, lat: float, lon: float) -> List[Tuple[str, float]]:
        """查找应急供应"""
        location = GeoLocation.from_coords(lat, lon)
        return self._emergency.find_emergency_supply(category, location)


def get_matchmaking_engine() -> MatchmakingManager:
    """获取撮合引擎"""
    return MatchmakingManager.get_instance()