# core/social_commerce/credit_network.py
# 去中心化信用网 - 交易即背书，越用越可信
#
# 核心能力：
# 1. 链式评价：每笔成交生成微型凭证
# 2. 信用不可搬运，只能在网络中生长
# 3. 品类专项可信度

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json

from .models import (
    CreditCredential,
    CreditAction,
    NodeProfile,
)


class CreditNetwork:
    """
    去中心化信用网络

    特点：
    1. 信用凭证链式存储，不可篡改
    2. 品类专项评分，不只是综合评分
    3. 信用只能在本网络中积累，无法"购买"
    """

    # 信用分计算权重
    ACTION_WEIGHTS = {
        CreditAction.LISTING: 0.5,      # 上架商品
        CreditAction.VIEWING: 0.1,    # 查看
        CreditAction.INQUIRY: 0.5,    # 询价
        CreditAction.NEGOTIATION: 0.2, # 协商
        CreditAction.DEAL: 2.0,        # 成交 (最重要)
        CreditAction.RATING: 1.5,      # 评价他人
        CreditAction.REFERRAL: 1.0,    # 推荐
    }

    # 信用变化阈值
    INITIAL_SCORE = 50.0    # 初始分数
    MAX_SCORE = 100.0
    MIN_SCORE = 0.0

    def __init__(self):
        # 凭证存储 (credential_id -> Credential)
        self._credentials: Dict[str, CreditCredential] = {}

        # 节点信用历史 (node_id -> [credential_id])
        self._node_credential_history: Dict[str, List[str]] = defaultdict(list)

        # 品类专项评分 (node_id -> {category -> score})
        self._category_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: 50.0))

        # 信任关系 (node_id -> {trusted_node_id -> trust_level})
        self._trust_relations: Dict[str, Dict[str, float]] = defaultdict(dict)

    def add_credential(
        self,
        from_node: str,
        to_node: str,
        action: CreditAction,
        rating: float = 0.0,
        comment: str = "",
        tags: List[str] = None,
        deal_id: str = None,
        deal_category: str = None,
        deal_amount: int = 0,
    ) -> CreditCredential:
        """
        添加信用凭证

        Args:
            from_node: 评价方
            to_node: 被评价方
            action: 行为类型
            rating: 评分 (1-5)
            comment: 评论
            tags: 标签
            deal_id: 关联交易ID
            deal_category: 交易品类
            deal_amount: 交易金额 (分)

        Returns:
            CreditCredential 对象
        """
        # 获取前一个凭证哈希
        prev_hash = None
        history = self._node_credential_history.get(to_node, [])
        if history:
            last_cred = self._credentials.get(history[-1])
            if last_cred:
                prev_hash = last_cred.credential_hash

        # 创建凭证
        credential = CreditCredential(
            from_node=from_node,
            to_node=to_node,
            deal_id=deal_id,
            deal_category=deal_category,
            deal_amount=deal_amount,
            rating=rating,
            comment=comment,
            tags=tags or [],
            previous_credential=prev_hash,
        )

        # 计算哈希
        credential.credential_hash = credential.compute_hash()

        # 存储
        self._credentials[credential.credential_id] = credential
        self._node_credential_history[to_node].append(credential.credential_id)

        # 更新信用分
        self._update_scores(
            to_node,
            action,
            rating,
            deal_category,
        )

        return credential

    def _update_scores(
        self,
        node_id: str,
        action: CreditAction,
        rating: float,
        category: str = None,
    ):
        """更新信用分"""
        # 综合分更新
        weight = self.ACTION_WEIGHTS.get(action, 0)

        # 评分转分数变化
        if rating > 0:
            # rating 是 1-5，转为 -1 到 +1 的变化
            score_delta = (rating - 3) * weight * 2
        else:
            # 无评分的行为
            score_delta = weight * 0.5

        # 基础分更新
        if node_id not in self._category_scores:
            self._category_scores[node_id] = defaultdict(lambda: self.INITIAL_SCORE)

        old_score = self._category_scores[node_id].get("__total__", self.INITIAL_SCORE)
        new_score = max(self.MIN_SCORE, min(self.MAX_SCORE, old_score + score_delta))
        self._category_scores[node_id]["__total__"] = new_score

        # 品类分更新 (如果有)
        if category:
            old_cat_score = self._category_scores[node_id].get(category, self.INITIAL_SCORE)
            new_cat_score = max(
                self.MIN_SCORE,
                min(self.MAX_SCORE, old_cat_score + score_delta * 0.8)
            )
            self._category_scores[node_id][category] = new_cat_score

    def get_credit_score(self, node_id: str) -> float:
        """获取节点综合信用分"""
        return self._category_scores.get(node_id, {}).get("__total__", self.INITIAL_SCORE)

    def get_category_score(self, node_id: str, category: str) -> float:
        """获取节点在特定品类的信用分"""
        scores = self._category_scores.get(node_id, {})
        return scores.get(category, self.INITIAL_SCORE)

    def get_expertise_tags(self, node_id: str) -> List[str]:
        """获取节点专长标签 (基于高评分品类)"""
        scores = self._category_scores.get(node_id, {})
        expertise = []

        for cat, score in scores.items():
            if cat != "__total__" and score >= 70:
                expertise.append(cat)

        return expertise[:10]  # 最多返回10个

    def get_credential_chain(self, node_id: str) -> List[CreditCredential]:
        """获取节点的凭证链 (用于验证)"""
        history = self._node_credential_history.get(node_id, [])
        credentials = []

        for cred_id in history:
            cred = self._credentials.get(cred_id)
            if cred:
                credentials.append(cred)

        return credentials

    def verify_chain(self, node_id: str) -> Tuple[bool, str]:
        """
        验证凭证链完整性

        Returns:
            (is_valid, error_message)
        """
        credentials = self.get_credential_chain(node_id)

        if not credentials:
            return True, "无凭证记录"

        # 验证哈希链
        for i, cred in enumerate(credentials):
            computed_hash = cred.compute_hash()
            if computed_hash != cred.credential_hash:
                return False, f"凭证 {cred.credential_id} 哈希不匹配"

            if i > 0:
                prev_cred = credentials[i - 1]
                if cred.previous_credential != prev_cred.credential_hash:
                    return False, f"凭证链断开于 {cred.credential_id}"

        return True, "验证通过"

    def trust_node(
        self,
        from_node: str,
        to_node: str,
        trust_level: float = 1.0,
    ):
        """
        信任某个节点

        Args:
            from_node: 信任方
            to_node: 被信任方
            trust_level: 信任级别 (0-1)
        """
        self._trust_relations[from_node][to_node] = trust_level

        # 反向信任
        if trust_level >= 0.8:
            self._trust_relations[to_node][from_node] = trust_level * 0.5

    def is_trusted(self, from_node: str, to_node: str) -> bool:
        """检查是否信任某个节点"""
        return self._trust_relations.get(from_node, {}).get(to_node, 0) >= 0.5

    def get_trusted_nodes(self, node_id: str) -> List[str]:
        """获取节点信任的所有节点"""
        trusts = self._trust_relations.get(node_id, {})
        return [n for n, level in trusts.items() if level >= 0.5]

    def compute_trust_score(
        self,
        from_node: str,
        to_node: str,
    ) -> float:
        """
        计算从一方到另一方的信任分

        考虑：
        - 直接信任
        - 共同信任的节点
        - 凭证链长度
        """
        # 直接信任
        direct_trust = self._trust_relations.get(from_node, {}).get(to_node, 0)

        # 共同信任
        from_trusts = set(self.get_trusted_nodes(from_node))
        to_trusts = set(self.get_trusted_nodes(to_node))
        common_trusts = from_trusts & to_trusts

        # 通过共同信任的间接信任
        indirect_trust = len(common_trusts) * 0.1

        # 信用分加成
        to_credit = self.get_credit_score(to_node) / 100.0

        return min(direct_trust + indirect_trust + to_credit * 0.2, 1.0)

    def generate_credit_report(self, node_id: str) -> Dict:
        """生成信用报告"""
        score = self.get_credit_score(node_id)
        credentials = self.get_credential_chain(node_id)
        expertise = self.get_expertise_tags(node_id)

        # 验证链
        is_valid, msg = self.verify_chain(node_id)

        # 统计
        total_deals = sum(1 for c in credentials if c.action == CreditAction.DEAL)
        avg_rating = 0.0
        if credentials:
            ratings = [c.rating for c in credentials if c.rating > 0]
            if ratings:
                avg_rating = sum(ratings) / len(ratings)

        return {
            "node_id": node_id,
            "credit_score": score,
            "is_chain_valid": is_valid,
            "chain_verification": msg,
            "total_credentials": len(credentials),
            "total_deals": total_deals,
            "average_rating": avg_rating,
            "expertise_tags": expertise,
            "trusted_nodes_count": len(self.get_trusted_nodes(node_id)),
        }


# ========== 信用评价处理器 ==========

class CreditEvaluator:
    """信用评价处理器"""

    # 评价触发词
    POSITIVE_TAGS = {
        "准时": 0.2,
        "货真价实": 0.3,
        "服务好": 0.2,
        "值得推荐": 0.3,
        "合作愉快": 0.2,
    }

    NEGATIVE_TAGS = {
        "拖延": -0.2,
        "货不对板": -0.3,
        "态度差": -0.2,
        "不建议合作": -0.3,
    }

    @classmethod
    def evaluate_from_comment(
        cls,
        comment: str,
        rating: float,
    ) -> Tuple[float, List[str]]:
        """
        从评论中提取标签并计算调整分

        Returns:
            (adjusted_rating, tags)
        """
        tags = []
        adjustment = 0.0

        # 检测正面标签
        for tag, delta in cls.POSITIVE_TAGS.items():
            if tag in comment:
                tags.append(tag)
                adjustment += delta

        # 检测负面标签
        for tag, delta in cls.NEGATIVE_TAGS.items():
            if tag in comment:
                tags.append(tag)
                adjustment += delta

        # 调整评分
        adjusted = max(1.0, min(5.0, rating + adjustment))

        return adjusted, tags


# ========== 全局管理器 ==========

class CreditNetworkManager:
    """信用网络管理器"""

    _instance = None

    def __init__(self):
        self.network = CreditNetwork()

    @classmethod
    def get_instance(cls) -> "CreditNetworkManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_deal_credit(
        self,
        from_node: str,
        to_node: str,
        rating: float,
        comment: str,
        category: str = None,
        deal_id: str = None,
        deal_amount: int = 0,
    ) -> CreditCredential:
        """添加交易信用"""
        # 评估评论
        adjusted_rating, tags = CreditEvaluator.evaluate_from_comment(comment, rating)

        return self.network.add_credential(
            from_node=from_node,
            to_node=to_node,
            action=CreditAction.DEAL,
            rating=adjusted_rating,
            comment=comment,
            tags=tags,
            deal_id=deal_id,
            deal_category=category,
            deal_amount=deal_amount,
        )

    def add_inquiry_credit(self, from_node: str, to_node: str) -> CreditCredential:
        """添加询价信用 (微小加成)"""
        return self.network.add_credential(
            from_node=from_node,
            to_node=to_node,
            action=CreditAction.INQUIRY,
        )

    def get_node_report(self, node_id: str) -> Dict:
        """获取节点信用报告"""
        return self.network.generate_credit_report(node_id)

    def recommend_trusted_sellers(
        self,
        buyer_id: str,
        category: str = None,
        limit: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        推荐可信任的卖家

        Args:
            buyer_id: 买家ID
            category: 商品品类
            limit: 返回数量

        Returns:
            [(seller_id, trust_score), ...]
        """
        # 简化实现：按信用分排序
        # 实际应考虑信任关系、品类专长等

        candidates = []
        for node_id in self.network._category_scores.keys():
            if node_id == buyer_id:
                continue

            # 检查品类专长
            if category:
                cat_score = self.network.get_category_score(node_id, category)
                if cat_score < 40:
                    continue

            trust = self.network.compute_trust_score(buyer_id, node_id)
            credit = self.network.get_credit_score(node_id)

            # 综合分
            combined = trust * 0.3 + credit / 100 * 0.7

            candidates.append((node_id, combined))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]


def get_credit_network() -> CreditNetworkManager:
    """获取信用网络管理器"""
    return CreditNetworkManager.get_instance()