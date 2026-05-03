"""
信誉管理器 — 统一信誉与信任计算

合并增强自:
- local_market/reputation.py ReputationManager
- social_commerce 信用凭证系统
- flash_listing 评价系统

增强:
- 统一信誉模型（整数分 + 信用分 + 浮动评级）
- 直接信任 + 间接信任传播（社交图遍历）
- 链式信用凭证验证
"""

from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List, Set, Callable
from datetime import datetime
from collections import defaultdict

from ..models.reputation import (
    ReputationRecord, ReputationEvent, TrustRelation, CreditCredential
)
from ..models import ReputationAction

logger = logging.getLogger(__name__)


class ReputationManager:
    """统一信誉管理器"""

    # --- 常量 ---
    INITIAL_REPUTATION = 100
    MIN_REPUTATION = 0
    MAX_REPUTATION = 1000
    TRUST_DECAY_FACTOR = 0.8
    MAX_TRUST_HOPS = 3

    # --- 评分映射 ---
    SCORE_MAP: Dict[ReputationAction, int] = {
        ReputationAction.SUCCESSFUL_TRADE: +5,
        ReputationAction.GOOD_REVIEW: +2,
        ReputationAction.QUICK_CONFIRM: +1,
        ReputationAction.DISPUTE_RESOLVE: +3,
        ReputationAction.TRADE_CANCEL: -3,
        ReputationAction.BAD_REVIEW: -5,
        ReputationAction.FALSE_PRODUCT: -20,
        ReputationAction.FRAUD: -100,
    }

    def __init__(self):
        self._records: Dict[str, ReputationRecord] = {}
        self._events: Dict[str, List[ReputationEvent]] = defaultdict(list)
        self._trust_relations: Dict[str, Dict[str, TrustRelation]] = defaultdict(dict)
        self._credentials: Dict[str, CreditCredential] = {}
        self.on_reputation_update: Optional[Callable] = None

    # ========================================================================
    # 信誉操作
    # ========================================================================

    def get_record(self, node_id: str) -> ReputationRecord:
        """获取或创建信誉记录"""
        if node_id not in self._records:
            self._records[node_id] = ReputationRecord(
                node_id=node_id,
                last_active=datetime.now().timestamp(),
            )
        return self._records[node_id]

    def get_reputation(self, node_id: str) -> int:
        return self.get_record(node_id).current_reputation

    def get_reputation_level(self, node_id: str) -> str:
        return self.get_record(node_id).level

    def record_event(self, event: ReputationEvent) -> bool:
        """记录信誉事件"""
        record = self.get_record(event.node_id)
        event.reputation_change = record.apply_event(event.action)
        self._records[event.node_id] = record
        self._events[event.node_id].append(event)

        if self.on_reputation_update:
            try:
                self.on_reputation_update(event.node_id, record.current_reputation)
            except Exception as e:
                logger.error(f"Reputation callback error: {e}")

        logger.info(
            f"Reputation: {event.node_id} {event.action.value} "
            f"→ {record.current_reputation} ({event.reputation_change:+d})"
        )
        return True

    def apply_trade_result(
        self,
        node_id: str,
        counterparty_id: str,
        success: bool,
        rating: Optional[float] = None,
        trade_id: Optional[str] = None,
    ) -> None:
        """应用交易结果（便捷方法）"""
        if success:
            event = ReputationEvent(
                node_id=node_id,
                action=ReputationAction.SUCCESSFUL_TRADE,
                trade_id=trade_id,
                counterparty_id=counterparty_id,
            )
            self.record_event(event)

            # 更新信任关系
            self._update_trust(node_id, counterparty_id, True)
        else:
            event = ReputationEvent(
                node_id=node_id,
                action=ReputationAction.TRADE_CANCEL,
                trade_id=trade_id,
                counterparty_id=counterparty_id,
            )
            self.record_event(event)
            self._update_trust(node_id, counterparty_id, False)

        # 处理评价
        if rating is not None:
            if rating >= 4.0:
                self.record_event(ReputationEvent(
                    node_id=node_id, action=ReputationAction.GOOD_REVIEW,
                    trade_id=trade_id, counterparty_id=counterparty_id,
                ))
            elif rating <= 2.0:
                self.record_event(ReputationEvent(
                    node_id=node_id, action=ReputationAction.BAD_REVIEW,
                    trade_id=trade_id, counterparty_id=counterparty_id,
                ))

    # ========================================================================
    # 信任计算
    # ========================================================================

    def get_trust(self, from_node: str, to_node: str) -> float:
        """获取信任度（直接 + 间接）"""
        if from_node == to_node:
            return 1.0

        self._ensure_trust_relation(from_node, to_node)
        relation = self._trust_relations[from_node][to_node]

        if relation.direct_trust > 0:
            # 有直接交互
            relation.calculate_total_trust(self.TRUST_DECAY_FACTOR)
        else:
            # 通过社交图计算间接信任
            indirect = self._compute_indirect_trust(from_node, to_node)
            relation.indirect_trust = indirect
            relation.total_trust = indirect * self.TRUST_DECAY_FACTOR

        return relation.total_trust

    def is_trusted(self, node_id: str, threshold: float = 0.3) -> bool:
        """判断节点是否可信"""
        return self.get_reputation(node_id) >= 100

    def get_trust_score(self, from_node: str, to_node: str) -> float:
        """获取综合信任分（信誉 + 信任关系）"""
        rep_score = min(self.get_reputation(to_node) / 1000.0, 1.0)
        trust_score = self.get_trust(from_node, to_node)
        return rep_score * 0.4 + trust_score * 0.6

    def _ensure_trust_relation(self, from_node: str, to_node: str) -> None:
        if to_node not in self._trust_relations[from_node]:
            self._trust_relations[from_node][to_node] = TrustRelation(
                from_node=from_node, to_node=to_node,
            )

    def _update_trust(self, node_id: str, counterparty_id: str, success: bool) -> None:
        relation = self._trust_relations[node_id].get(counterparty_id)
        if relation is None:
            relation = TrustRelation(from_node=node_id, to_node=counterparty_id)
            self._trust_relations[node_id][counterparty_id] = relation

        if success:
            relation.successful_trades += 1
            # 每次成功交易增加直接信任
            relation.direct_trust = min(1.0, relation.direct_trust + 0.05)
        else:
            relation.direct_trust = max(0.0, relation.direct_trust - 0.1)

        relation.last_interaction = datetime.now().timestamp()

    def _compute_indirect_trust(
        self, from_node: str, to_node: str, max_hops: int = None
    ) -> float:
        """通过共同联系人计算间接信任（BFS）"""
        if max_hops is None:
            max_hops = self.MAX_TRUST_HOPS

        visited: Set[str] = {from_node}
        current_level = {from_node}
        total_trust = 0.0
        paths_found = 0

        for hop in range(1, max_hops + 1):
            next_level: Set[str] = set()
            decay = self.TRUST_DECAY_FACTOR ** (hop - 1)

            for node in current_level:
                for neighbor, relation in self._trust_relations.get(node, {}).items():
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)

                    if neighbor == to_node:
                        total_trust += relation.direct_trust * decay
                        paths_found += 1
                    elif hop < max_hops:
                        next_level.add(neighbor)

            current_level = next_level

        if paths_found == 0:
            return 0.0
        return total_trust / paths_found

    # ========================================================================
    # 信用凭证（链式）
    # ========================================================================

    def add_credential(self, credential: CreditCredential) -> None:
        """添加信用凭证"""
        credential.credential_hash = credential.compute_hash()
        self._credentials[credential.credential_id] = credential

    def verify_credential(self, credential_id: str) -> bool:
        """验证信用凭证链"""
        cred = self._credentials.get(credential_id)
        if not cred:
            return False

        if cred.previous_credential:
            prev = self._credentials.get(cred.previous_credential)
            if not prev or not prev.is_verified:
                return False

        cred.is_verified = True
        return True

    def get_credentials(self, node_id: str) -> List[CreditCredential]:
        """获取节点的所有信用凭证"""
        return [c for c in self._credentials.values()
                if c.to_node == node_id and c.is_verified]

    # ========================================================================
    # 统计
    # ========================================================================

    def get_stats(self) -> dict:
        records = list(self._records.values())
        return {
            "total_nodes": len(records),
            "avg_reputation": sum(r.current_reputation for r in records) / max(len(records), 1),
            "total_trades": sum(r.total_trades for r in records),
            "total_credentials": sum(1 for c in self._credentials.values() if c.is_verified),
        }


# 模块级单例
_REPUTATION_MANAGER: Optional[ReputationManager] = None


def get_reputation_manager() -> ReputationManager:
    global _REPUTATION_MANAGER
    if _REPUTATION_MANAGER is None:
        _REPUTATION_MANAGER = ReputationManager()
    return _REPUTATION_MANAGER
