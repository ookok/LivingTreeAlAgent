# core/social_commerce/intent_radar.py
# 意图雷达 - 从行为到交易意愿的无感预测
#
# 核心能力：
# 1. 实时打标"潜在B端/大C"
# 2. 动态画像：工贸一体/跨境潜力
# 3. 用户还没上架，系统已纳入撮合池

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import re

from .models import (
    NodeProfile,
    NodeType,
    IntentLevel,
    IntentSignal,
    MatchStrength,
    CreditAction,
)


class IntentRadar:
    """
    意图雷达

    通过分析用户行为，实时打标交易意愿和类型标签：
    - 潜在 B端/大C
    - 工贸一体卖家
    - 跨境潜力
    """

    def __init__(self):
        # B端信号关键词
        self.b2b_keywords = {
            "批发", "货源", "工厂", "经销", "代理", "报关", "样品",
            "MOQ", "批量", "OEM", "ODM", "定制", "加工", "代工",
            "招商", "加盟", "供应商", "供应链", "库存", "尾货",
        }

        # 跨境信号关键词
        self.crossborder_keywords = {
            "进口", "出口", "海关", "清关", "外贸", "跨境", "退税",
            "柜", "集装箱", "FOB", "CIF", "DDP", "EXW", "海运",
            "空运", "报关单", "提单", "原产地", "进口国",
        }

        # 工贸一体信号
        self.manufacturing_keywords = {
            "生产", "制造", "加工", "组装", "产能", "流水线",
            "车间", "工厂", "生产线", "日产能", "月产能",
        }

        # 搜索词到品类的映射
        self.category_mapping = {
            "电机": "机电设备",
            "电机": "机电设备",
            "灯具": "照明",
            "灯管": "照明",
            "ABS": "塑料原料",
            "PC": "塑料原料",
            "钢材": "金属材料",
            "铝材": "金属材料",
            "布料": "纺织",
            "面料": "纺织",
        }

        # 时序模式
        self.time_patterns = {
            "深夜工作": (22, 23, 0, 1, 2, 3, 4),
            "正常工作": (9, 10, 11, 12, 13, 14, 15, 16, 17),
            "周末空闲": (6, 7),  # 周六、周日
        }

    def process_signal(self, profile: NodeProfile, signal: IntentSignal) -> NodeProfile:
        """
        处理意图信号，更新节点画像

        Args:
            profile: 当前节点画像
            signal: 新收到的意图信号

        Returns:
            更新后的画像
        """
        # 提取关键词
        keywords = self._extract_keywords(signal)

        # 更新画像
        profile.update_intent(signal.signal_type, keywords)

        # 推断标签
        tags = self._infer_tags(signal, keywords)
        for tag in tags:
            profile.add_tag(tag)

        # 更新品类专长
        for kw, category in self.category_mapping.items():
            if kw in keywords:
                profile.category_expertise[category] = \
                    profile.category_expertise.get(category, 0) + 1

        # 更新时间特征
        hour = datetime.now().hour
        profile.active_hours.add(hour)

        # 检查是否是工贸一体
        if self._is_manufacturer(profile):
            profile.add_tag("工贸一体")

        # 检查是否是跨境
        if self._is_crossborder(profile):
            profile.add_tag("跨境潜力")

        profile.updated_at = datetime.now().timestamp()

        return profile

    def _extract_keywords(self, signal: IntentSignal) -> List[str]:
        """从信号中提取关键词"""
        keywords = []

        # 从搜索词提取
        if signal.signal_type == "search":
            text = signal.signal_data.get("query", "")
            keywords.extend(self._tokenize(text))

        # 从查看历史提取
        elif signal.signal_type == "view":
            title = signal.signal_data.get("title", "")
            keywords.extend(self._tokenize(title))

        # 从询价提取
        elif signal.signal_type == "inquiry":
            content = signal.signal_data.get("content", "")
            keywords.extend(self._tokenize(content))

        return keywords

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        if not text:
            return []

        # 简单按空格/标点分词
        words = re.split(r'[\s,，、。.!?；;]+', text)
        return [w for w in words if len(w) >= 2]

    def _infer_tags(self, signal: IntentSignal, keywords: List[str]) -> List[str]:
        """推断标签"""
        tags = []
        all_text = str(signal.signal_data)

        # B端检测
        if signal.is_b2b_signal() or any(k in all_text for k in self.b2b_keywords):
            tags.append("B端潜力")

        # 大C检测 (高客单价)
        if signal.signal_type == "inquiry" and signal.signal_data.get("quantity", 0) > 10:
            tags.append("大C")

        # 跨境检测
        if signal.is_crossborder_signal() or any(k in all_text for k in self.crossborder_keywords):
            tags.append("跨境")

        # 紧急需求
        if "急" in all_text or "马上" in all_text or "今天" in all_text:
            tags.append("紧急需求")

        return tags

    def _is_manufacturer(self, profile: NodeProfile) -> bool:
        """判断是否是工贸一体"""
        # 检查是否有制造相关关键词
        text = " ".join(profile.intent_keywords)
        has_mfg = any(k in text for k in self.manufacturing_keywords)

        # 检查时间模式 (白天+晚上都有活动)
        has_both_patterns = (
            any(h in profile.active_hours for h in self.time_patterns["正常工作"]) and
            any(h in profile.active_hours for h in self.time_patterns["深夜工作"])
        )

        return has_mfg and has_both_patterns

    def _is_crossborder(self, profile: NodeProfile) -> bool:
        """判断是否有跨境潜力"""
        text = " ".join(profile.intent_keywords)
        return any(k in text for k in self.crossborder_keywords)

    def assess_intent_level(self, profile: NodeProfile) -> IntentLevel:
        """
        评估意图强度

        逻辑：
        - 搜索 + 比价 + 询价 → 强意图
        - 频繁查看同类商品 → 准备购买
        - 紧急关键词 → 急需
        """
        score = 0

        # 搜索次数
        search_count = len([s for s in profile.search_history if s])
        score += min(search_count * 0.5, 3)

        # 查看次数
        view_count = len(profile.view_history)
        score += min(view_count * 0.3, 2)

        # 询价次数
        score += profile.inquiry_count * 2

        # 比价次数
        score += profile.compare_count * 1.5

        # 紧急标签
        if "紧急需求" in profile.intent_tags:
            score += 3

        # 评分
        if score >= 8:
            return IntentLevel.URGENT
        elif score >= 5:
            return IntentLevel.READY
        elif score >= 2:
            return IntentLevel.COMPARING
        elif score >= 0.5:
            return IntentLevel.BROWSING
        else:
            return IntentLevel.NONE

    def compute_match_strength(
        self,
        buyer: NodeProfile,
        seller: NodeProfile,
    ) -> Tuple[MatchStrength, List[str]]:
        """
        计算买卖双方的匹配强度

        Returns:
            (匹配强度, 匹配原因列表)
        """
        reasons = []
        score = 0

        # 1. 品类匹配
        common_categories = set(buyer.category_expertise.keys()) & set(seller.category_expertise.keys())
        if common_categories:
            score += 3
            reasons.append(f"品类匹配: {', '.join(common_categories)}")

        # 2. 意图关键词重叠
        buyer_kw = set(buyer.intent_keywords)
        seller_kw = set(seller.intent_keywords)
        overlap = buyer_kw & seller_kw
        if overlap:
            score += 2 * min(len(overlap), 3)
            reasons.append(f"意图重叠: {', '.join(list(overlap)[:3])}")

        # 3. 标签匹配
        common_tags = set(buyer.intent_tags) & set(seller.intent_tags)
        if common_tags:
            score += 2
            reasons.append(f"标签匹配: {', '.join(common_tags)}")

        # 4. 上下游检测 (买家关键词是卖家产品的上游)
        if self._is_upstream_downstream(buyer, seller):
            score += 4
            reasons.append("上下游关系")
            buyer.add_tag("上游买家")
            seller.add_tag("下游买家")

        # 5. 拼单可能性 (多个买家想要同类商品)
        # 简化：检查标签相似度
        tag_similarity = len(common_tags) / max(len(set(buyer.intent_tags) | set(seller.intent_tags)), 1)
        if tag_similarity > 0.5:
            score += 2
            reasons.append("可拼单")

        # 转换为匹配强度
        if score >= 8:
            return MatchStrength.PERFECT, reasons
        elif score >= 5:
            return MatchStrength.STRONG, reasons
        elif score >= 3:
            return MatchStrength.MEDIUM, reasons
        elif score >= 1:
            return MatchStrength.WEAK, reasons
        else:
            return MatchStrength.NONE, reasons

    def _is_upstream_downstream(self, buyer: NodeProfile, seller: NodeProfile) -> bool:
        """检测上下游关系"""
        # 简化逻辑：买家的意向关键词包含卖家的专长品类
        buyer_text = " ".join(buyer.intent_keywords).lower()
        seller_categories = list(seller.category_expertise.keys())

        for category in seller_categories:
            # 检查买家是否在找该品类的原料/配件
            if category in buyer_text:
                return True

        return False

    def generate_intent_report(self, profile: NodeProfile) -> Dict:
        """生成意图分析报告"""
        intent_level = self.assess_intent_level(profile)

        return {
            "node_id": profile.node_id,
            "intent_level": intent_level.value,
            "intent_tags": profile.intent_tags,
            "category_expertise": profile.category_expertise,
            "is_b2b": "B端潜力" in profile.intent_tags,
            "is_crossborder": "跨境潜力" in profile.intent_tags,
            "is_manufacturer": "工贸一体" in profile.intent_tags,
            "active_hours": sorted(list(profile.active_hours)),
            "recommendations": self._generate_recommendations(profile),
        }

    def _generate_recommendations(self, profile: NodeProfile) -> List[str]:
        """生成建议"""
        recs = []

        if "B端潜力" in profile.intent_tags and profile.node_type == NodeType.BUYER:
            recs.append("建议标记为潜在 B 端客户")

        if "工贸一体" in profile.intent_tags:
            recs.append("可推荐工贸一体卖家群组")

        if profile.inquiry_count > 10 and profile.total_deals == 0:
            recs.append("高询价但无成交，建议主动推送")

        if IntentLevel.READY in [self.assess_intent_level(profile)]:
            recs.append("意图强烈，建议优先撮合")

        return recs


# ========== 意图雷达管理器 ==========

class IntentRadarManager:
    """意图雷达管理器 - 管理所有节点的意图"""

    _instance = None

    def __init__(self):
        self._profiles: Dict[str, NodeProfile] = {}
        self._signals: List[IntentSignal] = []
        self._radar = IntentRadar()
        self._max_signals = 10000

    @classmethod
    def get_instance(cls) -> "IntentRadarManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_create_profile(self, node_id: str) -> NodeProfile:
        """获取或创建节点画像"""
        if node_id not in self._profiles:
            self._profiles[node_id] = NodeProfile(node_id=node_id)
        return self._profiles[node_id]

    def add_signal(self, node_id: str, signal_type: str, data: Dict) -> NodeProfile:
        """添加意图信号"""
        signal = IntentSignal(
            node_id=node_id,
            signal_type=signal_type,
            signal_data=data,
            extracted_keywords=self._radar._extract_keywords(signal) if signal_type else [],
        )

        self._signals.append(signal)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[-self._max_signals:]

        profile = self.get_or_create_profile(node_id)
        return self._radar.process_signal(profile, signal)

    def get_profile(self, node_id: str) -> Optional[NodeProfile]:
        """获取节点画像"""
        return self._profiles.get(node_id)

    def get_all_profiles(self, min_intent: IntentLevel = IntentLevel.NONE) -> List[NodeProfile]:
        """获取所有画像 (按意图过滤)"""
        result = []
        for profile in self._profiles.values():
            if self._radar.assess_intent_level(profile).value >= min_intent.value:
                result.append(profile)
        return result

    def get_potential_buyers(self) -> List[NodeProfile]:
        """获取潜在买家 (有意图但未成交)"""
        return [
            p for p in self._profiles.values()
            if p.node_type in (NodeType.BUYER, NodeType.BOTH)
            and self._radar.assess_intent_level(p) >= IntentLevel.BROWSING
            and p.total_deals == 0
        ]

    def get_potential_sellers(self) -> List[NodeProfile]:
        """获取潜在卖家"""
        return [
            p for p in self._profiles.values()
            if p.node_type in (NodeType.SELLER, NodeType.BOTH)
            and len(p.category_expertise) > 0
        ]

    def match_buyer_to_sellers(self, buyer_id: str) -> List[Tuple[NodeProfile, MatchStrength, List[str]]]:
        """为买家匹配合适的卖家"""
        buyer = self._profiles.get(buyer_id)
        if not buyer:
            return []

        matches = []
        sellers = self.get_potential_sellers()

        for seller in sellers:
            if seller.node_id == buyer_id:
                continue

            strength, reasons = self._radar.compute_match_strength(buyer, seller)
            if strength != MatchStrength.NONE:
                matches.append((seller, strength, reasons))

        # 按匹配强度排序
        matches.sort(key=lambda x: x[1].value, reverse=True)
        return matches

    def analyze_time_pattern(self, node_id: str) -> Dict:
        """分析时间模式"""
        profile = self._profiles.get(node_id)
        if not profile:
            return {}

        active = profile.active_hours

        patterns = []
        for pattern_name, hours in self.time_patterns.items():
            if any(h in active for h in hours):
                patterns.append(pattern_name)

        return {
            "active_hours": sorted(list(active)),
            "patterns": patterns,
            "is_night_owl": any(h in active for h in self.time_patterns["深夜工作"]),
            "is_weekend_available": any(h in active for h in self.time_patterns["周末空闲"]),
        }


def get_intent_radar() -> IntentRadarManager:
    """获取意图雷达管理器"""
    return IntentRadarManager.get_instance()