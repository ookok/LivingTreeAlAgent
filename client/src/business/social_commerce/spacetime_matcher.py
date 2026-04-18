# core/social_commerce/spacetime_matcher.py
# 时空引力匹配 - GeoHash 社交层 + 流动性感知
#
# 核心能力：
# 1. 不广播精确坐标，广播"区域+可交易时段"
# 2. 流动性感知：出差者临时加入当地网格
# 3. 让偶发相遇变成可计算的交易机会

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import math

from .models import (
    GeoLocation,
    GeoPrecision,
    GeoHash,
    NodeProfile,
    MatchCandidate,
    MatchStrength,
)


class SpacetimeMatcher:
    """
    时空引力匹配器

    基于 GeoHash 的模糊地理位置和可用时段进行智能匹配：
    - 地理邻近度
    - 时间兼容性
    - 流动性感知 (出差/旅行)
    """

    # GeoHash 精度与实际距离对应
    PRECISION_DISTANCE = {
        GeoPrecision.EXACT: 0.12,          # ~12m (太精确，不用)
        GeoPrecision.NEIGHBORHOOD: 1.5,     # ~150km
        GeoPrecision.DISTRICT: 15.0,        # ~1500km
        GeoPrecision.CITY: 150.0,           # ~15000km
    }

    def __init__(self):
        # 活跃网格 (geohash -> 节点列表)
        self._grids: Dict[str, Set[str]] = defaultdict(set)

        # 时空索引 (hour -> geohash -> 节点列表)
        self._spacetime_index: Dict[int, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # 出差者临时位置
        self._travelers: Dict[str, GeoLocation] = {}

    def register_location(self, node_id: str, location: GeoLocation):
        """注册节点位置"""
        if not location.geohash:
            return

        # 注册到网格
        self._grids[location.geohash[:6]].add(node_id)

        # 注册到时空索引
        for hour in location.available_hours:
            self._spacetime_index[hour][location.geohash[:6]].add(node_id)

    def unregister_location(self, node_id: str, location: GeoLocation):
        """注销节点位置"""
        if not location.geohash:
            return

        # 从网格移除
        grid = location.geohash[:6]
        if node_id in self._grids.get(grid, set()):
            self._grids[grid].discard(node_id)

        # 从时空索引移除
        for hour in location.available_hours:
            if node_id in self._spacetime_index.get(hour, {}).get(grid, set()):
                self._spacetime_index[hour][grid].discard(node_id)

    def register_traveler(self, node_id: str, destination: GeoLocation):
        """注册出差者"""
        self._travelers[node_id] = destination
        self.register_location(node_id, destination)

    def unregister_traveler(self, node_id: str):
        """注销出差者"""
        if node_id in self._travelers:
            old_loc = self._travelers[node_id]
            self.unregister_location(node_id, old_loc)
            del self._travelers[node_id]

    def find_nearby_nodes(
        self,
        location: GeoLocation,
        hour: int,
        max_distance: float = 1.5,
        node_type: str = None,
        profiles: Dict[str, NodeProfile] = None,
    ) -> List[Tuple[str, float]]:
        """
        查找附近的节点

        Args:
            location: 当前位置
            hour: 当前小时
            max_distance: 最大 GeoHash 距离
            node_type: 节点类型过滤
            profiles: 节点画像字典

        Returns:
            [(node_id, distance), ...]
        """
        if not location.geohash:
            return []

        candidates = set()

        # 1. 检查当前网格及邻居
        neighbors = GeoHash.neighbors(location.geohash[:6])
        search_grids = [location.geohash[:6]] + neighbors

        for grid in search_grids:
            # 检查当前小时的时空索引
            if hour in self._spacetime_index:
                candidates.update(self._spacetime_index[hour].get(grid, set()))

            # 也检查全天可用
            candidates.update(self._grids.get(grid, set()))

        # 2. 计算实际距离并过滤
        results = []
        for node_id in candidates:
            if profiles and node_type:
                profile = profiles.get(node_id)
                if not profile:
                    continue
                if node_type == "buyer" and profile.node_type.value not in ("buyer", "both"):
                    continue
                if node_type == "seller" and profile.node_type.value not in ("seller", "both"):
                    continue

            # 简化：使用 GeoHash 前缀匹配作为距离
            # 实际应使用 Haversine 公式
            results.append((node_id, 0.5))  # 占位

        # 3. 排序并返回
        results.sort(key=lambda x: x[1])
        return results[:50]

    def compute_geo_score(
        self,
        loc1: Optional[GeoLocation],
        loc2: Optional[GeoLocation],
    ) -> float:
        """
        计算地理匹配分

        Returns:
            0-1 之间的分数
        """
        if not loc1 or not loc2:
            return 0.5  # 无法判断时给中间值

        # 计算 GeoHash 距离
        distance = loc1.distance_to(loc2)

        # 转换为分数 (距离越近分数越高)
        if distance < 0.1:
            return 1.0
        elif distance < 0.3:
            return 0.8
        elif distance < 0.5:
            return 0.6
        elif distance < 0.7:
            return 0.4
        else:
            return 0.2

    def compute_time_score(
        self,
        loc1: Optional[GeoLocation],
        loc2: Optional[GeoLocation],
        current_hour: int = None,
    ) -> float:
        """
        计算时间兼容性分数

        Returns:
            0-1 之间的分数
        """
        if current_hour is None:
            current_hour = datetime.now().hour

        if not loc1 or not loc2:
            return 0.5

        # 检查时间重叠
        overlap = loc1.available_hours & loc2.available_hours

        if not overlap:
            return 0.0

        # 重叠越多分数越高
        max_hours = max(len(loc1.available_hours), len(loc2.available_hours))
        overlap_ratio = len(overlap) / max_hours

        # 检查当前时间是否在重叠中
        if current_hour in overlap:
            current_bonus = 0.2
        else:
            current_bonus = 0.0

        return min(overlap_ratio + current_bonus, 1.0)

    def find_match_candidates(
        self,
        buyer_location: GeoLocation,
        seller_location: GeoLocation,
        buyer_id: str,
        seller_id: str,
        buyer_profile: NodeProfile,
        seller_profile: NodeProfile,
        current_hour: int = None,
    ) -> MatchCandidate:
        """
        查找买卖双方的匹配候选

        Returns:
            MatchCandidate 对象
        """
        if current_hour is None:
            current_hour = datetime.now().hour

        candidate = MatchCandidate(
            buyer_id=buyer_id,
            seller_id=seller_id,
            buyer_location=buyer_location,
            seller_location=seller_location,
        )

        # 计算地理分
        candidate.geo_score = self.compute_geo_score(buyer_location, seller_location)

        # 计算时间分
        candidate.time_score = self.compute_time_score(
            buyer_location, seller_location, current_hour
        )

        # 匹配原因
        reasons = []

        # 地理匹配
        if candidate.geo_score >= 0.8:
            reasons.append("地理位置极近")
        elif candidate.geo_score >= 0.6:
            reasons.append("地理位置较近")

        # 时间匹配
        if candidate.time_score >= 0.8:
            reasons.append("时间高度重合")
        elif candidate.time_score >= 0.5:
            reasons.append("时间部分重合")

        # 出差者特殊加成
        if buyer_id in self._travelers or seller_id in self._travelers:
            reasons.append("出差者临时节点")
            candidate.time_score = min(candidate.time_score + 0.2, 1.0)

        candidate.match_reasons = reasons

        # 综合匹配强度
        if candidate.geo_score >= 0.7 and candidate.time_score >= 0.7:
            candidate.match_strength = MatchStrength.STRONG
        elif candidate.geo_score >= 0.5 or candidate.time_score >= 0.5:
            candidate.match_strength = MatchStrength.MEDIUM
        else:
            candidate.match_strength = MatchStrength.WEAK

        return candidate

    def get_grid_statistics(self, geohash_prefix: str) -> Dict:
        """获取网格统计"""
        grid = geohash_prefix[:6]
        nodes = self._grids.get(grid, set())

        # 统计节点类型 (如果有 profiles)
        stats = {
            "grid": grid,
            "total_nodes": len(nodes),
            "travelers": len([n for n in nodes if n in self._travelers]),
            "hours_available": [],
        }

        # 统计各小时的可用节点数
        for hour in range(24):
            count = len(self._spacetime_index[hour].get(grid, set()))
            if count > 0:
                stats["hours_available"].append({"hour": hour, "count": count})

        return stats

    def predict_trade_opportunity(
        self,
        location: GeoLocation,
        hour: int,
        category: str = None,
    ) -> Dict:
        """
        预测交易机会

        基于当前时空状态，预测可能的交易机会
        """
        # 查找附近活跃节点
        nearby = self.find_nearby_nodes(location, hour)

        # 检查是否是交易高峰期
        hour_activity = [
            len(self._spacetime_index[hour].get(g, set()))
            for g in self._grids.keys()
        ]
        avg_activity = sum(hour_activity) / max(len(hour_activity), 1)

        opportunity = {
            "location": location.geohash[:6],
            "hour": hour,
            "nearby_count": len(nearby),
            "is_high_activity": len(nearby) > avg_activity * 1.5,
            "is_traveler_peak": len(self._travelers) > 5,
            "recommendations": [],
        }

        # 生成建议
        if opportunity["is_high_activity"]:
            opportunity["recommendations"].append("当前时段活跃，适合发布需求")

        if opportunity["is_traveler_peak"]:
            opportunity["recommendations"].append("出差者较多，可能有样品展示机会")

        if len(nearby) > 20:
            opportunity["recommendations"].append("附近节点密集，适合批量采购")

        return opportunity


# ========== 时空引力计算器 ==========

class SpacetimeCalculator:
    """时空引力计算器 - 计算节点间的引力强度"""

    # 引力模型参数
    GEOFACTOR = 0.4      # 地理因素权重
    TIMEFACTOR = 0.3     # 时间因素权重
    MATCHFACTOR = 0.3    # 匹配因素权重

    # 时间衰减
    HOUR_DECAY = 0.95    # 每小时衰减

    @classmethod
    def compute_gravity(
        cls,
        buyer_loc: GeoLocation,
        seller_loc: GeoLocation,
        buyer_intent_level: float,
        seller_intent_level: float,
        match_strength: MatchStrength,
    ) -> float:
        """
        计算买卖双方的引力强度

        引力 = G * (m1 * m2) / d^2

        其中:
        - G: 整体引力系数
        - m1, m2: 买卖双方的意图强度
        - d: 地理+时间距离
        """
        # 意图质量
        m1 = buyer_intent_level
        m2 = seller_intent_level

        # 匹配系数
        match_coeff = {
            MatchStrength.PERFECT: 2.0,
            MatchStrength.STRONG: 1.5,
            MatchStrength.MEDIUM: 1.0,
            MatchStrength.WEAK: 0.5,
            MatchStrength.NONE: 0.1,
        }.get(match_strength, 0.1)

        # 距离 (地理 + 时间)
        geo_dist = buyer_loc.distance_to(seller_loc) if (buyer_loc and seller_loc) else 1.0

        # 时间不兼容惩罚
        if buyer_loc and seller_loc:
            time_overlap = len(buyer_loc.available_hours & seller_loc.available_hours)
            time_penalty = 1.0 - (time_overlap / 24.0)
        else:
            time_penalty = 1.0

        d = math.sqrt(geo_dist ** 2 + (time_penalty * 0.5) ** 2)

        # 引力公式
        gravity = (m1 * m2 * match_coeff) / (d ** 2 + 0.01)  # 加 0.01 防止除零

        # 归一化到 0-1
        return min(gravity / 10.0, 1.0)

    @classmethod
    def predict_meeting_probability(
        cls,
        buyer_loc: GeoLocation,
        seller_loc: GeoLocation,
        current_hour: int,
    ) -> float:
        """
        预测买卖双方实际相遇概率

        考虑:
        - 地理距离
        - 时间重叠
        - 出行习惯
        """
        if not buyer_loc or not seller_loc:
            return 0.3

        # 1. 地理概率
        distance = buyer_loc.distance_to(seller_loc)
        if distance < 0.1:
            geo_prob = 0.9
        elif distance < 0.3:
            geo_prob = 0.7
        elif distance < 0.5:
            geo_prob = 0.4
        else:
            geo_prob = 0.1

        # 2. 时间概率
        if current_hour in (buyer_loc.available_hours & seller_loc.available_hours):
            time_prob = 0.8
        else:
            time_prob = 0.2

        # 3. 出行概率 (检查历史)
        # 简化：如果双方都在常住地，比出差者相遇概率低
        is_buyer_traveling = buyer_loc.is_traveling
        is_seller_traveling = seller_loc.is_traveling

        if is_buyer_traveling and not is_seller_traveling:
            travel_prob = 0.6  # 买家来找卖家
        elif not is_buyer_traveling and is_seller_traveling:
            travel_prob = 0.6  # 卖家来找买家
        elif is_buyer_traveling and is_seller_traveling:
            travel_prob = 0.4  # 双方都在外
        else:
            travel_prob = 0.3  # 都在常住地

        # 综合概率
        prob = geo_prob * 0.5 + time_prob * 0.3 + travel_prob * 0.2

        return min(prob, 1.0)


# ========== 全局管理器 ==========

class SpacetimeMatcherManager:
    """时空匹配管理器"""

    _instance = None

    def __init__(self):
        self.matcher = SpacetimeMatcher()
        self._profiles: Dict[str, NodeProfile] = {}

    @classmethod
    def get_instance(cls) -> "SpacetimeMatcherManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_profiles(self, profiles: Dict[str, NodeProfile]):
        """设置节点画像字典"""
        self._profiles = profiles

    def update_location(self, node_id: str, location: GeoLocation):
        """更新节点位置"""
        self.matcher.register_location(node_id, location)

    def find_match(
        self,
        buyer_id: str,
        seller_id: str,
        current_hour: int = None,
    ) -> Optional[MatchCandidate]:
        """查找匹配"""
        if current_hour is None:
            current_hour = datetime.now().hour

        buyer_profile = self._profiles.get(buyer_id)
        seller_profile = self._profiles.get(seller_id)

        if not buyer_profile or not seller_profile:
            return None

        # 简化：从画像中提取位置 (实际应单独存储)
        # 这里使用占位符
        buyer_loc = getattr(buyer_profile, "location", None)
        seller_loc = getattr(seller_profile, "location", None)

        return self.matcher.find_match_candidates(
            buyer_loc or GeoLocation(),
            seller_loc or GeoLocation(),
            buyer_id,
            seller_id,
            buyer_profile,
            seller_profile,
            current_hour,
        )

    def get_grid_stats(self, geohash: str) -> Dict:
        """获取网格统计"""
        return self.matcher.get_grid_statistics(geohash)


def get_spacetime_matcher() -> SpacetimeMatcherManager:
    """获取时空匹配管理器"""
    return SpacetimeMatcherManager.get_instance()