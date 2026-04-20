"""
积分经济系统 (Credit Economy System)
==================================

双模式支持：个人模式 + 企业模式
核心理念：平衡积分发放与消耗，构建可持续的P2P经济体系

模块结构:
- DynamicCreditIssuance: 动态积分发放系统
- SmartCreditConsumption: 智能积分消耗模型
- LayeredConsensus: 分层共识机制
- CreditStateChannel: 积分状态通道
- ProbabilisticFinality: 概率性最终性
- DecentralizedSkillMarket: 去中心化技能市场
- IdeaNFTMarketplace: 创意NFT市场
- SkillRevenueTokens: 技能收益权代币化
- CreditPredictionMarket: 积分预测市场
"""

import json
import uuid
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from enum import Enum
from collections import defaultdict
import hashlib
import math


# ============================================================
# 枚举定义
# ============================================================

class CreditTransactionType(Enum):
    """积分交易类型"""
    ISSUE = "issue"                    # 发放
    CONSUME = "consume"                # 消耗
    TRANSFER = "transfer"              # 转账
    TRADE = "trade"                   # 交易
    STAKE = "stake"                   # 抵押
    REWARD = "reward"                 # 奖励
    BURN = "burn"                     # 燃烧
    REVENUE_SHARE = "revenue_share"   # 收益分成


class ConsensusLayer(Enum):
    """共识层"""
    IMMEDIATE = "immediate"  # 即时交易 (<=100积分)
    DAILY = "daily"         # 日终批量 (<=10000积分)
    GLOBAL = "global"       # 全局结算 (>10000积分)


class FinalityLevel(Enum):
    """最终性级别"""
    PENDING = "pending"      # 待确认
    LIKELY = "likely"       # 很可能
    VERY_LIKELY = "very_likely"  # 非常可能
    FINAL = "final"         # 最终确认


class MarketListingType(Enum):
    """市场挂牌类型"""
    SKILL = "skill"          # 技能服务
    CREATION = "creation"    # 创意作品
    NFT = "nft"             # NFT
    FRACTIONAL = "fractional"  # 碎片化权益


class DisputeStatus(Enum):
    """争议状态"""
    NONE = "none"
    OPENED = "opened"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    APPEALED = "appealed"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class CreditAccount:
    """积分账户"""
    id: str
    owner_id: str
    owner_type: str = "user"  # user/enterprise
    balance: int = 0
    locked_balance: int = 0  # 锁定中（抵押等）
    frozen_balance: int = 0  # 冻结（争议等）
    daily_limit: int = 50000  # 日限额
    total_issued: int = 0  # 历史发放
    total_consumed: int = 0  # 历史消耗
    credit_score: float = 1.0  # 信用分
    level: str = "bronze"  # bronze/silver/gold/platinum
    created_at: datetime = field(default_factory=datetime.now)
    last_transaction: Optional[datetime] = None

    @property
    def available_balance(self) -> int:
        return self.balance - self.locked_balance - self.frozen_balance

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "owner_type": self.owner_type,
            "balance": self.balance,
            "locked_balance": self.locked_balance,
            "frozen_balance": self.frozen_balance,
            "available_balance": self.available_balance,
            "daily_limit": self.daily_limit,
            "total_issued": self.total_issued,
            "total_consumed": self.total_consumed,
            "credit_score": self.credit_score,
            "level": self.level,
            "created_at": self.created_at.isoformat(),
            "last_transaction": self.last_transaction.isoformat() if self.last_transaction else None
        }


@dataclass
class CreditTransaction:
    """积分交易"""
    id: str
    tx_type: CreditTransactionType
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    amount: int = 0
    fee: int = 0
    balance_before: int = 0
    balance_after: int = 0
    status: str = "pending"  # pending/confirmed/finalized/failed
    consensus_layer: ConsensusLayer = ConsensusLayer.IMMEDIATE
    confirmations: int = 0
    finality_level: FinalityLevel = FinalityLevel.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tx_type": self.tx_type.value,
            "from_account": self.from_account,
            "to_account": self.to_account,
            "amount": self.amount,
            "fee": self.fee,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "status": self.status,
            "consensus_layer": self.consensus_layer.value,
            "confirmations": self.confirmations,
            "finality_level": self.finality_level.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None
        }


@dataclass
class CreditPolicy:
    """积分政策"""
    id: str
    name: str
    base_daily_credits: int = 1000
    max_daily_credits: int = 5000
    min_daily_credits: int = 100
    network_health_factor: float = 1.0
    inflation_rate: float = 1.0
    credit_velocity_factor: float = 1.0
    total_supply: int = 0
    circulating_supply: int = 0
    active_users: int = 0
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "base_daily_credits": self.base_daily_credits,
            "max_daily_credits": self.max_daily_credits,
            "min_daily_credits": self.min_daily_credits,
            "network_health_factor": self.network_health_factor,
            "inflation_rate": self.inflation_rate,
            "credit_velocity_factor": self.credit_velocity_factor,
            "total_supply": self.total_supply,
            "circulating_supply": self.circulating_supply,
            "active_users": self.active_users,
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class StateChannel:
    """状态通道"""
    id: str
    participant_a: str
    participant_b: str
    balance_a: int = 0
    balance_b: int = 0
    locked_a: int = 0
    locked_b: int = 0
    status: str = "open"  # open/closed/disputed
    sequence_number: int = 0
    state_updates: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "participant_a": self.participant_a,
            "participant_b": self.participant_b,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "locked_a": self.locked_a,
            "locked_b": self.locked_b,
            "status": self.status,
            "sequence_number": self.sequence_number,
            "state_updates": self.state_updates,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None
        }


@dataclass
class SkillListing:
    """技能挂牌"""
    id: str
    seller_id: str
    title: str
    description: str
    category: str
    price: int  # 积分价格
    delivery_time: str  # 预计交付时间
    reputation: float = 0.0  # 信誉分
    total_sales: int = 0
    satisfaction: float = 0.0  # 满意度
    tags: List[str] = field(default_factory=list)
    contract_terms: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # active/sold/removed
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "seller_id": self.seller_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "price": self.price,
            "delivery_time": self.delivery_time,
            "reputation": self.reputation,
            "total_sales": self.total_sales,
            "satisfaction": self.satisfaction,
            "tags": self.tags,
            "contract_terms": self.contract_terms,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class IdeaNFT:
    """创意NFT"""
    id: str
    creator_id: str
    title: str
    abstract: str
    content_hash: str
    category: str
    novelty_score: float = 0.0
    potential_value: float = 0.0
    royalties: float = 0.1  # 版税比例
    total_fractions: int = 0  # 碎片总数
    fraction_price: int = 0  # 每个碎片价格
    fraction_holders: Dict[str, int] = field(default_factory=dict)  # holder -> count
    listing_price: Optional[int] = None
    owner_id: str = ""  # 当前所有者
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "title": self.title,
            "abstract": self.abstract,
            "content_hash": self.content_hash,
            "category": self.category,
            "novelty_score": self.novelty_score,
            "potential_value": self.potential_value,
            "royalties": self.royalties,
            "total_fractions": self.total_fractions,
            "fraction_price": self.fraction_price,
            "fraction_holders": self.fraction_holders,
            "listing_price": self.listing_price,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RevenueToken:
    """收益权代币"""
    id: str
    skill_id: str
    owner_id: str
    total_shares: int
    shares_owned: int
    value_per_share: float
    estimated_yield: float  # 预计收益率
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "owner_id": self.owner_id,
            "total_shares": self.total_shares,
            "shares_owned": self.shares_owned,
            "value_per_share": self.value_per_share,
            "estimated_yield": self.estimated_yield,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PredictionMarket:
    """预测市场"""
    id: str
    creator_id: str
    event: str
    description: str
    outcomes: List[str]
    resolution_criteria: str
    resolution_time: datetime
    total_liquidity: int = 0
    outcome_volumes: Dict[str, int] = field(default_factory=dict)  # outcome -> volume
    outcome_prices: Dict[str, float] = field(default_factory=dict)  # outcome -> price
    status: str = "active"  # active/resolved/cancelled
    resolution: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "event": self.event,
            "description": self.description,
            "outcomes": self.outcomes,
            "resolution_criteria": self.resolution_criteria,
            "resolution_time": self.resolution_time.isoformat(),
            "total_liquidity": self.total_liquidity,
            "outcome_volumes": self.outcome_volumes,
            "outcome_prices": self.outcome_prices,
            "status": self.status,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PredictionShare:
    """预测份额"""
    id: str
    market_id: str
    owner_id: str
    outcome: str
    shares: int
    avg_price: float
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "owner_id": self.owner_id,
            "outcome": self.outcome,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "created_at": self.created_at.isoformat()
        }


# ============================================================
# 动态积分发放系统
# ============================================================

class DynamicCreditIssuance:
    """动态积分发放系统"""

    def __init__(self):
        self.base_daily_credits = 1000
        self.policy = CreditPolicy(id="default", name="默认政策")

    async def calculate_daily_credits(self, user_id: str, user_data: dict = None) -> dict:
        """计算用户每日应得积分"""
        user_data = user_data or await self._get_user_data(user_id)
        network_econ = await self._get_network_economics()

        # 多维度计算
        factors = {
            # 基础部分 (40%)
            "base": self.base_daily_credits * 0.4,

            # 贡献奖励 (30%)
            "contribution": self._calculate_contribution_bonus(user_data),

            # 网络活跃度 (20%)
            "activity": self._calculate_activity_bonus(user_data),

            # 稀缺性调节 (10%)
            "scarcity": self._calculate_scarcity_adjustment(network_econ)
        }

        # 计算总和
        total_credits = sum(factors.values())

        # 应用经济调节
        adjusted_credits = self._apply_economic_adjustment(total_credits, network_econ)

        # 确保最小/最大值
        final_credits = self._clamp_credits(
            adjusted_credits,
            min=self.policy.min_daily_credits,
            max=self.policy.max_daily_credits
        )

        return {
            "user_id": user_id,
            "daily_credits": int(final_credits),
            "factors": factors,
            "network_health": network_econ.get("health_score", 1.0),
            "breakdown": {
                "base_contribution": int(factors["base"]),
                "contribution_bonus": int(factors["contribution"]),
                "activity_bonus": int(factors["activity"]),
                "scarcity_adjustment": int(factors["scarcity"])
            }
        }

    async def _get_user_data(self, user_id: str) -> dict:
        """获取用户行为数据"""
        # 简化实现
        return {
            "node_uptime": 0.95,
            "data_shared": 100,
            "tasks_completed": 15,
            "content_created": 5,
            "community_help": 10
        }

    async def _get_network_economics(self) -> dict:
        """获取网络经济状态"""
        return {
            "health_score": 0.85,
            "inflation_rate": 1.02,
            "credit_velocity": 1.1,
            "active_nodes": 1000
        }

    def _calculate_contribution_bonus(self, user_data: dict) -> float:
        """计算贡献奖励"""
        bonus_weights = {
            "node_uptime": 0.3,
            "data_shared": 0.25,
            "tasks_completed": 0.2,
            "content_created": 0.15,
            "community_help": 0.1
        }

        bonus = sum(user_data.get(factor, 0) * weight for factor, weight in bonus_weights.items())
        return bonus * 50

    def _calculate_activity_bonus(self, user_data: dict) -> float:
        """计算活跃度奖励"""
        base_activity = user_data.get("tasks_completed", 0) + user_data.get("content_created", 0)
        return base_activity * 10

    def _calculate_scarcity_adjustment(self, network_econ: dict) -> float:
        """计算稀缺性调节"""
        active_nodes = network_econ.get("active_nodes", 1000)
        scarcity_factor = math.log(active_nodes + 1) / 10
        return self.base_daily_credits * 0.1 * scarcity_factor

    def _apply_economic_adjustment(self, total: float, network_econ: dict) -> float:
        """应用经济调节"""
        health = network_econ.get("health_score", 1.0)
        inflation = network_econ.get("inflation_rate", 1.0)

        # 健康度高时增加发放，膨胀率高时减少
        adjusted = total * health / inflation
        return adjusted

    def _clamp_credits(self, value: float, min_val: int, max_val: int) -> float:
        """限制积分范围"""
        return max(min_val, min(max_val, value))


# ============================================================
# 智能积分消耗系统
# ============================================================

class SmartCreditConsumption:
    """智能积分消耗系统"""

    TASK_COSTS = {
        "compute": {
            "light": {"credits": 10, "time": "5min"},
            "medium": {"credits": 50, "time": "30min"},
            "heavy": {"credits": 200, "time": "2h"}
        },
        "storage": {
            "per_gb_per_day": 1,
            "premium_storage": 5
        },
        "ai": {
            "chat": {"per_1k_tokens": 5},
            "image_generation": {"per_image": 20},
            "code_generation": {"per_100_lines": 30}
        },
        "network": {
            "p2p_bandwidth": {"per_gb": 2},
            "priority_routing": {"per_request": 1}
        }
    }

    async def estimate_task_cost(self, task_type: str, task_params: dict) -> dict:
        """预估任务成本"""
        # 1. 基础成本计算
        base_cost = self._get_base_cost(task_type, task_params)

        # 2. 动态定价因子
        dynamic_factors = {
            "network_congestion": self._get_network_congestion(),
            "resource_scarcity": self._get_resource_scarcity(task_type),
            "time_sensitivity": task_params.get("urgency", 1.0),
            "quality_requirement": task_params.get("quality", 1.0)
        }

        # 3. 应用动态因子
        final_cost = base_cost
        for factor, value in dynamic_factors.items():
            final_cost *= value

        # 4. 智能议价
        suggested_price = final_cost
        if task_params.get("allow_negotiation", True):
            suggested_price = await self._negotiate_price(task_type, task_params, final_cost)

        return {
            "task_type": task_type,
            "base_cost": base_cost,
            "suggested_price": int(suggested_price),
            "final_estimate": int(final_cost),
            "confidence": 0.85,
            "breakdown": {
                "factors": dynamic_factors,
                "components": self._get_cost_breakdown(task_type, task_params)
            },
            "alternative_options": await self._suggest_alternatives(task_type, final_cost)
        }

    def _get_base_cost(self, task_type: str, task_params: dict) -> int:
        """获取基础成本"""
        tier = task_params.get("tier", "medium")
        cost_config = self.TASK_COSTS.get(task_type, {})

        if isinstance(cost_config, dict):
            if tier in cost_config:
                return cost_config[tier].get("credits", 0)
            # AI服务类型
            for key, value in cost_config.items():
                if isinstance(value, dict) and "per_" in key:
                    return value.get("credits", 10)

        return 10

    def _get_network_congestion(self) -> float:
        """获取网络拥塞程度"""
        # 简化实现
        return 1.0

    def _get_resource_scarcity(self, task_type: str) -> float:
        """获取资源稀缺度"""
        scarcity_map = {
            "compute": 1.2,
            "storage": 1.0,
            "ai": 1.5,
            "network": 1.1
        }
        return scarcity_map.get(task_type, 1.0)

    async def _negotiate_price(self, task_type: str, task_params: dict, base_price: int) -> int:
        """智能议价"""
        # 简单实现：长期客户95折
        if task_params.get("is_loyal_customer"):
            return int(base_price * 0.95)
        return int(base_price)

    def _get_cost_breakdown(self, task_type: str, task_params: dict) -> dict:
        """获取成本明细"""
        return {
            "compute_cost": self.TASK_COSTS.get("compute", {}).get(task_params.get("tier", "medium"), {}).get("credits", 0),
            "network_cost": self.TASK_COSTS.get("network", {}).get("priority_routing", {}).get("per_request", 1),
            "ai_cost": self.TASK_COSTS.get("ai", {}).get(task_params.get("ai_service", "chat"), {}).get("per_1k_tokens", 5)
        }

    async def _suggest_alternatives(self, task_type: str, current_cost: int) -> List[dict]:
        """建议替代方案"""
        alternatives = []

        if task_type == "compute" and current_cost > 50:
            alternatives.append({
                "option": "light_compute",
                "description": "使用轻量计算",
                "estimated_cost": 10,
                "tradeoff": "速度降低50%"
            })

        if task_type == "ai" and current_cost > 30:
            alternatives.append({
                "option": "batch_processing",
                "description": "批量处理",
                "estimated_cost": int(current_cost * 0.7),
                "tradeoff": "延迟1小时"
            })

        return alternatives


# ============================================================
# 分层共识机制
# ============================================================

class LayeredConsensus:
    """分层共识机制"""

    def __init__(self):
        self.transactions: Dict[str, CreditTransaction] = {}
        self.pending_txs: List[CreditTransaction] = []

    async def process_transaction(self, tx: CreditTransaction) -> dict:
        """处理交易"""
        # 1. 交易验证
        if not await self._validate_transaction(tx):
            return {"success": False, "error": "交易验证失败"}

        # 2. 选择共识层
        consensus_layer = self._select_consensus_layer(tx.amount)
        tx.consensus_layer = consensus_layer

        # 3. 执行共识
        consensus_result = await self._execute_consensus(tx, consensus_layer)

        # 4. 记录交易
        self.transactions[tx.id] = tx

        # 5. 更新状态
        tx.status = "confirmed"
        tx.confirmed_at = datetime.now()
        tx.finality_level = FinalityLevel.LIKELY

        if consensus_layer == ConsensusLayer.IMMEDIATE:
            tx.finality_level = FinalityLevel.VERY_LIKELY
            tx.finalized_at = datetime.now()
            tx.status = "finalized"

        return {
            "success": True,
            "transaction_id": tx.id,
            "consensus_layer": consensus_layer.value,
            "finality": tx.finality_level.value,
            "confirmations": tx.confirmations
        }

    async def _validate_transaction(self, tx: CreditTransaction) -> bool:
        """验证交易"""
        if tx.amount <= 0:
            return False
        # 更多验证逻辑...
        return True

    def _select_consensus_layer(self, amount: int) -> ConsensusLayer:
        """选择共识层"""
        if amount <= 100:
            return ConsensusLayer.IMMEDIATE
        elif amount <= 10000:
            return ConsensusLayer.DAILY
        else:
            return ConsensusLayer.GLOBAL

    async def _execute_consensus(self, tx: CreditTransaction, layer: ConsensusLayer) -> dict:
        """执行共识"""
        if layer == ConsensusLayer.IMMEDIATE:
            return await self._immediate_consensus(tx)
        elif layer == ConsensusLayer.DAILY:
            return await self._daily_batch_consensus(tx)
        else:
            return await self._global_settlement(tx)

    async def _immediate_consensus(self, tx: CreditTransaction) -> dict:
        """即时共识"""
        return {
            "finality": "immediate",
            "confirmations": 3,
            "time": "seconds"
        }

    async def _daily_batch_consensus(self, tx: CreditTransaction) -> dict:
        """日终批量共识"""
        self.pending_txs.append(tx)
        return {
            "finality": "daily_batch",
            "confirmations": 1,
            "time": "24hours"
        }

    async def _global_settlement(self, tx: CreditTransaction) -> dict:
        """全局结算共识"""
        return {
            "finality": "global",
            "confirmations": 6,
            "time": "48hours"
        }

    async def get_transaction_status(self, tx_id: str) -> dict:
        """获取交易状态"""
        tx = self.transactions.get(tx_id)
        if not tx:
            return {"status": "unknown"}

        return {
            "transaction_id": tx_id,
            "status": tx.status,
            "finality_level": tx.finality_level.value,
            "confirmations": tx.confirmations
        }


# ============================================================
# 积分状态通道
# ============================================================

class CreditStateChannel:
    """积分状态通道（用于高频交易）"""

    def __init__(self):
        self.channels: Dict[str, StateChannel] = {}

    async def open_channel(self, participant_a: str, participant_b: str,
                          deposit_a: int, deposit_b: int) -> dict:
        """打开状态通道"""
        channel_id = self._generate_channel_id(participant_a, participant_b)

        channel = StateChannel(
            id=channel_id,
            participant_a=participant_a,
            participant_b=participant_b,
            balance_a=deposit_a,
            balance_b=deposit_b,
            locked_a=deposit_a,
            locked_b=deposit_b
        )

        self.channels[channel_id] = channel

        return {
            "channel_id": channel_id,
            "participants": [participant_a, participant_b],
            "initial_balances": {"a": deposit_a, "b": deposit_b},
            "capacity": deposit_a + deposit_b,
            "status": "open"
        }

    def _generate_channel_id(self, a: str, b: str) -> str:
        """生成通道ID"""
        sorted_participants = sorted([a, b])
        raw = f"{sorted_participants[0]}_{sorted_participants[1]}_{datetime.now().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def update_channel(self, channel_id: str, from_user: str,
                            to_user: str, amount: int) -> dict:
        """更新通道状态"""
        channel = self.channels.get(channel_id)
        if not channel:
            return {"success": False, "error": "通道不存在"}

        # 验证余额
        if from_user == channel.participant_a and channel.balance_a < amount:
            return {"success": False, "error": "余额不足"}
        if from_user == channel.participant_b and channel.balance_b < amount:
            return {"success": False, "error": "余额不足"}

        # 更新余额
        if from_user == channel.participant_a:
            channel.balance_a -= amount
            channel.balance_b += amount
        else:
            channel.balance_b -= amount
            channel.balance_a += amount

        # 记录状态更新
        channel.sequence_number += 1
        update = {
            "sequence": channel.sequence_number,
            "from": from_user,
            "to": to_user,
            "amount": amount,
            "balances": {"a": channel.balance_a, "b": channel.balance_b},
            "timestamp": datetime.now().isoformat()
        }
        channel.state_updates.append(update)

        return {
            "success": True,
            "channel_id": channel_id,
            "update": update,
            "new_balances": {"a": channel.balance_a, "b": channel.balance_b}
        }

    async def close_channel(self, channel_id: str) -> dict:
        """关闭状态通道"""
        channel = self.channels.get(channel_id)
        if not channel:
            return {"success": False, "error": "通道不存在"}

        channel.status = "closed"
        channel.closed_at = datetime.now()

        return {
            "success": True,
            "channel_id": channel_id,
            "final_balances": {"a": channel.balance_a, "b": channel.balance_b},
            "total_transactions": len(channel.state_updates)
        }

    def get_channel(self, channel_id: str) -> Optional[StateChannel]:
        """获取通道"""
        return self.channels.get(channel_id)


# ============================================================
# 概率性最终性
# ============================================================

class ProbabilisticFinality:
    """概率性最终性"""

    CONFIDENCE_LEVELS = {
        FinalityLevel.PENDING: 0.0,
        FinalityLevel.LIKELY: 0.7,
        FinalityLevel.VERY_LIKELY: 0.9,
        FinalityLevel.FINAL: 0.99
    }

    def __init__(self):
        self.tx_confirmations: Dict[str, int] = {}
        self.total_network_nodes = 100

    async def calculate_finality_probability(self, tx_id: str) -> dict:
        """计算交易最终性概率"""
        confirming_nodes = self.tx_confirmations.get(tx_id, 0)

        # 计算概率（伯努利过程模型）
        if confirming_nodes == 0:
            probability = 0.0
        else:
            probability = 1.0 - (0.5 ** confirming_nodes)

        # 确定置信级别
        confidence_level = FinalityLevel.PENDING
        for level, threshold in sorted(self.CONFIDENCE_LEVELS.items(), key=lambda x: x[1]):
            if probability >= threshold:
                confidence_level = level

        return {
            "transaction_id": tx_id,
            "probability": probability,
            "confidence_level": confidence_level.value,
            "confirming_nodes": confirming_nodes,
            "total_nodes": self.total_network_nodes,
            "estimated_time_to_finality": self._estimate_time(confidence_level),
            "recommendation": self._get_recommendation(confidence_level)
        }

    def _estimate_time(self, level: FinalityLevel) -> str:
        """估算达到最终性的时间"""
        time_estimates = {
            FinalityLevel.PENDING: "未知",
            FinalityLevel.LIKELY: "约1分钟",
            FinalityLevel.VERY_LIKELY: "约5分钟",
            FinalityLevel.FINAL: "已最终确认"
        }
        return time_estimates.get(level, "未知")

    def _get_recommendation(self, level: FinalityLevel) -> str:
        """根据置信级别给出建议"""
        recommendations = {
            FinalityLevel.PENDING: "等待更多确认后再操作",
            FinalityLevel.LIKELY: "可进行下一步，但保留回滚可能",
            FinalityLevel.VERY_LIKELY: "可视为已确认",
            FinalityLevel.FINAL: "完全安全，不可逆转"
        }
        return recommendations.get(level, "未知状态")

    def add_confirmation(self, tx_id: str):
        """添加确认"""
        self.tx_confirmations[tx_id] = self.tx_confirmations.get(tx_id, 0) + 1


# ============================================================
# 去中心化技能市场
# ============================================================

class DecentralizedSkillMarket:
    """去中心化技能市场"""

    def __init__(self):
        self.listings: Dict[str, SkillListing] = {}
        self.sales_history: List[dict] = []
        self.disputes: Dict[str, dict] = {}

    async def list_skill(self, seller_id: str, skill_data: dict, pricing: dict) -> dict:
        """挂牌技能"""
        # 1. 技能验证
        validation = await self._validate_skill(skill_data)
        if not validation["valid"]:
            return {"success": False, "error": "技能验证失败", "details": validation}

        # 2. 智能定价建议
        suggested_price = await self._suggest_price(skill_data, pricing)

        # 3. 创建挂牌
        listing = SkillListing(
            id=f"skill_{uuid.uuid4().hex[:12]}",
            seller_id=seller_id,
            title=skill_data.get("title", ""),
            description=skill_data.get("description", ""),
            category=skill_data.get("category", "general"),
            price=pricing.get("price", suggested_price),
            delivery_time=skill_data.get("delivery_time", "7 days"),
            tags=skill_data.get("tags", []),
            contract_terms=skill_data.get("contract_terms", {})
        )

        self.listings[listing.id] = listing

        # 4. 信誉抵押
        reputation_stake = await self._stake_reputation(seller_id, listing.id)

        return {
            "success": True,
            "listing_id": listing.id,
            "validation": validation,
            "suggested_price": suggested_price,
            "final_price": listing.price,
            "reputation_stake": reputation_stake,
            "discovery_tags": self._generate_discovery_tags(skill_data)
        }

    async def _validate_skill(self, skill_data: dict) -> dict:
        """验证技能"""
        issues = []

        if not skill_data.get("title"):
            issues.append("缺少标题")
        if not skill_data.get("description"):
            issues.append("缺少描述")
        if len(skill_data.get("description", "")) < 50:
            issues.append("描述过于简短")

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    async def _suggest_price(self, skill_data: dict, pricing: dict) -> int:
        """建议价格"""
        category = skill_data.get("category", "general")
        experience = skill_data.get("experience_years", 1)

        # 基础价格表
        base_prices = {
            "programming": 500,
            "design": 400,
            "writing": 300,
            "consulting": 600,
            "general": 200
        }

        base = base_prices.get(category, 300)
        return base * (1 + experience * 0.2)

    async def _stake_reputation(self, seller_id: str, listing_id: str) -> dict:
        """信誉抵押"""
        stake_amount = 100  # 抵押100积分
        return {
            "staked_amount": stake_amount,
            "lock_period": "30 days",
            "unlock_conditions": ["完成交易", "无争议"]
        }

    def _generate_discovery_tags(self, skill_data: dict) -> List[str]:
        """生成发现标签"""
        tags = skill_data.get("tags", [])
        tags.append(skill_data.get("category", "general"))
        return list(set(tags))[:5]

    async def purchase_skill(self, listing_id: str, buyer_id: str) -> dict:
        """购买技能"""
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "error": "挂牌不存在"}

        # 1. 创建托管
        escrow = {
            "escrow_id": f"escrow_{uuid.uuid4().hex[:8]}",
            "amount": listing.price,
            "status": "locked",
            "release_conditions": ["买家确认完成", "争议解决"]
        }

        # 2. 建立执行环境
        execution_env = {
            "env_id": f"env_{uuid.uuid4().hex[:8]}",
            "listing_id": listing_id,
            "buyer_id": buyer_id,
            "status": "preparing"
        }

        return {
            "success": True,
            "escrow": escrow,
            "execution_environment": execution_env,
            "next_steps": ["联系卖家", "确认交付", "完成交易"]
        }

    async def complete_sale(self, listing_id: str, rating: int, feedback: str) -> dict:
        """完成销售"""
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "error": "挂牌不存在"}

        # 更新统计数据
        listing.total_sales += 1
        listing.satisfaction = (listing.satisfaction * (listing.total_sales - 1) + rating) / listing.total_sales

        # 记录历史
        self.sales_history.append({
            "listing_id": listing_id,
            "rating": rating,
            "feedback": feedback,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "success": True,
            "new_reputation": listing.reputation,
            "total_sales": listing.total_sales
        }

    def get_listings(self, category: str = None, sort_by: str = "reputation") -> List[dict]:
        """获取挂牌列表"""
        listings = list(self.listings.values())

        if category:
            listings = [l for l in listings if l.category == category]

        if sort_by == "reputation":
            listings.sort(key=lambda x: x.reputation, reverse=True)
        elif sort_by == "price":
            listings.sort(key=lambda x: x.price)
        elif sort_by == "sales":
            listings.sort(key=lambda x: x.total_sales, reverse=True)

        return [l.to_dict() for l in listings]


# ============================================================
# 创意NFT市场
# ============================================================

class IdeaNFTMarketplace:
    """创意NFT市场"""

    def __init__(self):
        self.nfts: Dict[str, IdeaNFT] = {}
        self.fractional_contracts: Dict[str, dict] = {}

    async def mint_idea_nft(self, creator_id: str, idea_data: dict) -> dict:
        """铸造创意NFT"""
        # 1. 创意新颖性验证
        novelty = await self._validate_idea_novelty(idea_data)
        if not novelty["valid"]:
            return {"success": False, "error": "创意新颖性不足"}

        # 2. 生成内容哈希
        content_hash = hashlib.sha256(
            json.dumps(idea_data.get("content", ""), sort_keys=True).encode()
        ).hexdigest()

        # 3. 创建NFT
        nft = IdeaNFT(
            id=f"nft_{uuid.uuid4().hex[:12]}",
            creator_id=creator_id,
            title=idea_data.get("title", ""),
            abstract=idea_data.get("abstract", ""),
            content_hash=content_hash,
            category=idea_data.get("category", "general"),
            novelty_score=novelty["score"],
            potential_value=novelty["estimated_value"],
            royalties=idea_data.get("royalties", 0.1),
            owner_id=creator_id
        )

        self.nfts[nft.id] = nft

        # 4. 生成验证证明
        verification_proof = {
            "nft_id": nft.id,
            "content_hash": content_hash,
            "timestamp": datetime.now().isoformat(),
            "blockchain_proof": hashlib.sha256(f"{nft.id}{content_hash}".encode()).hexdigest()[:16]
        }

        return {
            "success": True,
            "nft_id": nft.id,
            "novelty_score": nft.novelty_score,
            "verification_proof": verification_proof,
            "royalty_terms": {
                "royalty_percentage": nft.royalties * 100,
                "secondary_sales": True
            }
        }

    async def _validate_idea_novelty(self, idea_data: dict) -> dict:
        """验证创意新颖性"""
        content = idea_data.get("content", "")

        # 简化实现：基于内容长度和关键词
        novelty_score = min(1.0, len(content) / 1000)

        return {
            "valid": novelty_score >= 0.3,
            "score": novelty_score,
            "estimated_value": int(novelty_score * 10000)
        }

    async def fractional_ownership(self, nft_id: str, owner_id: str,
                                  fractions: int, price_per_fraction: int) -> dict:
        """碎片化所有权"""
        nft = self.nfts.get(nft_id)
        if not nft:
            return {"success": False, "error": "NFT不存在"}

        if nft.owner_id != owner_id:
            return {"success": False, "error": "无权操作此NFT"}

        # 创建碎片化合约
        contract_id = f"frac_{uuid.uuid4().hex[:8]}"
        contract = {
            "contract_id": contract_id,
            "nft_id": nft_id,
            "total_fractions": fractions,
            "price_per_fraction": price_per_fraction,
            "total_value": fractions * price_per_fraction,
            "fractions_sold": 0,
            "holders": {}
        }

        self.fractional_contracts[contract_id] = contract
        nft.total_fractions = fractions
        nft.fraction_price = price_per_fraction

        # 设置治理机制
        governance = {
            "voting_threshold": fractions // 2 + 1,
            "proposal_types": ["sell", "split", "burn"],
            "quorum_required": 0.5
        }

        return {
            "success": True,
            "contract_id": contract_id,
            "nft_id": nft_id,
            "total_fractions": fractions,
            "initial_offering": {
                "total_value": contract["total_value"],
                "price_per_fraction": price_per_fraction
            },
            "governance": governance
        }

    async def purchase_fraction(self, contract_id: str, buyer_id: str, quantity: int) -> dict:
        """购买碎片"""
        contract = self.fractional_contracts.get(contract_id)
        if not contract:
            return {"success": False, "error": "合约不存在"}

        total_cost = contract["price_per_fraction"] * quantity

        # 更新持有者
        if buyer_id not in contract["holders"]:
            contract["holders"][buyer_id] = 0
        contract["holders"][buyer_id] += quantity
        contract["fractions_sold"] += quantity

        return {
            "success": True,
            "contract_id": contract_id,
            "buyer_id": buyer_id,
            "quantity_purchased": quantity,
            "total_cost": total_cost,
            "new_holding": contract["holders"][buyer_id]
        }

    def get_nft(self, nft_id: str) -> Optional[dict]:
        """获取NFT"""
        nft = self.nfts.get(nft_id)
        return nft.to_dict() if nft else None

    def list_nfts(self, category: str = None, sort_by: str = "novelty") -> List[dict]:
        """列出NFT"""
        nfts = list(self.nfts.values())

        if category:
            nfts = [n for n in nfts if n.category == category]

        if sort_by == "novelty":
            nfts.sort(key=lambda x: x.novelty_score, reverse=True)
        elif sort_by == "value":
            nfts.sort(key=lambda x: x.potential_value, reverse=True)

        return [n.to_dict() for n in nfts]


# ============================================================
# 技能收益权代币化
# ============================================================

class SkillRevenueTokens:
    """技能收益权代币"""

    def __init__(self):
        self.tokens: Dict[str, RevenueToken] = {}
        self.distribution_contracts: Dict[str, dict] = {}

    async def tokenize_skill_revenue(self, skill_id: str, owner_id: str,
                                     revenue_shares: int) -> dict:
        """将技能收益权代币化"""
        # 1. 评估技能价值
        skill_value = await self._evaluate_skill_value(skill_id)

        # 2. 创建收益权代币
        token = RevenueToken(
            id=f"rev_{uuid.uuid4().hex[:8]}",
            skill_id=skill_id,
            owner_id=owner_id,
            total_shares=revenue_shares,
            shares_owned=revenue_shares,
            value_per_share=skill_value["estimated_monthly_revenue"] / revenue_shares,
            estimated_yield=skill_value["estimated_monthly_yield"]
        )

        self.tokens[token.id] = token

        # 3. 创建分配合约
        distribution_contract = {
            "contract_id": f"dist_{uuid.uuid4().hex[:8]}",
            "token_id": token.id,
            "skill_id": skill_id,
            "total_revenue": 0,
            "distributions": []
        }
        self.distribution_contracts[distribution_contract["contract_id"]] = distribution_contract

        return {
            "success": True,
            "token": token.to_dict(),
            "distribution_contract": distribution_contract,
            "estimated_yield": skill_value["estimated_monthly_yield"],
            "risk_assessment": {
                "skill_demand": "stable",
                "market_risk": "medium",
                "overall_rating": "B+"
            }
        }

    async def _evaluate_skill_value(self, skill_id: str) -> dict:
        """评估技能价值"""
        # 简化实现
        return {
            "estimated_monthly_revenue": 1000,
            "estimated_monthly_yield": 0.08,
            "demand_trend": "increasing"
        }

    async def transfer_tokens(self, token_id: str, from_id: str, to_id: str, shares: int) -> dict:
        """转移代币"""
        token = self.tokens.get(token_id)
        if not token:
            return {"success": False, "error": "代币不存在"}

        # 验证持有者
        if token.shares_owned < shares:
            return {"success": False, "error": "余额不足"}

        token.shares_owned -= shares

        return {
            "success": True,
            "token_id": token_id,
            "from": from_id,
            "to": to_id,
            "shares_transferred": shares
        }

    def get_token_holders(self, token_id: str) -> List[dict]:
        """获取代币持有者"""
        # 简化实现
        return []


# ============================================================
# 积分预测市场
# ============================================================

class CreditPredictionMarket:
    """积分预测市场"""

    def __init__(self):
        self.markets: Dict[str, PredictionMarket] = {}
        self.shares: Dict[str, PredictionShare] = {}
        self.liquidity_pools: Dict[str, dict] = {}

    async def create_prediction_market(self, creator_id: str, event: str,
                                     outcomes: List[str], resolution_time: datetime) -> dict:
        """创建预测市场"""
        market_id = f"pred_{uuid.uuid4().hex[:8]}"

        market = PredictionMarket(
            id=market_id,
            creator_id=creator_id,
            event=event,
            description=self._generate_event_description(event),
            outcomes=outcomes,
            resolution_criteria=self._define_resolution_criteria(event),
            resolution_time=resolution_time
        )

        self.markets[market_id] = market

        # 初始化结果价格
        for outcome in outcomes:
            market.outcome_prices[outcome] = 1.0 / len(outcomes)

        # 提供初始流动性
        liquidity_pool = await self._provide_initial_liquidity(market_id)

        return {
            "success": True,
            "market": market.to_dict(),
            "liquidity_pool": liquidity_pool,
            "trading_start_time": datetime.now().isoformat()
        }

    def _generate_event_description(self, event: str) -> str:
        """生成事件描述"""
        return f"预测结果: {event}"

    def _define_resolution_criteria(self, event: str) -> str:
        """定义结算标准"""
        return "由预言机自动结算"

    async def _provide_initial_liquidity(self, market_id: str) -> dict:
        """提供初始流动性"""
        liquidity = 1000
        self.liquidity_pools[market_id] = {
            "total_liquidity": liquidity,
            "liquidity_providers": []
        }
        return self.liquidity_pools[market_id]

    async def trade_prediction_shares(self, market_id: str, trader_id: str,
                                    outcome: str, is_buy: bool, amount: int) -> dict:
        """交易预测份额"""
        market = self.markets.get(market_id)
        if not market:
            return {"success": False, "error": "市场不存在"}

        # 计算价格（简单AMM模型）
        current_price = market.outcome_prices.get(outcome, 0.5)
        if is_buy:
            new_price = current_price * (1 + amount / 1000)
        else:
            new_price = current_price * (1 - amount / 1000)

        total_cost = int(current_price * amount)

        # 更新市场状态
        market.outcome_prices[outcome] = new_price
        market.outcome_volumes[outcome] = market.outcome_volumes.get(outcome, 0) + amount

        # 创建份额记录
        share = PredictionShare(
            id=f"share_{uuid.uuid4().hex[:8]}",
            market_id=market_id,
            owner_id=trader_id,
            outcome=outcome,
            shares=amount if is_buy else -amount,
            avg_price=current_price
        )
        self.shares[share.id] = share

        return {
            "success": True,
            "market_id": market_id,
            "outcome": outcome,
            "action": "buy" if is_buy else "sell",
            "shares": amount,
            "price": new_price,
            "total_cost": total_cost,
            "share_id": share.id
        }

    async def resolve_market(self, market_id: str, winning_outcome: str) -> dict:
        """结算市场"""
        market = self.markets.get(market_id)
        if not market:
            return {"success": False, "error": "市场不存在"}

        market.status = "resolved"
        market.resolution = winning_outcome

        # 计算赢家支付
        winners = []
        for share in self.shares.values():
            if share.market_id == market_id and share.outcome == winning_outcome:
                winners.append(share)

        return {
            "success": True,
            "market_id": market_id,
            "winning_outcome": winning_outcome,
            "total_winners": len(winners),
            "total_volume": sum(s.shares for s in winners)
        }

    def get_markets(self, status: str = None) -> List[dict]:
        """获取市场列表"""
        markets = list(self.markets.values())

        if status:
            markets = [m for m in markets if m.status == status]

        return [m.to_dict() for m in markets]


# ============================================================
# 积分账户管理器
# ============================================================

class CreditAccountManager:
    """积分账户管理器"""

    def __init__(self):
        self.accounts: Dict[str, CreditAccount] = {}
        self.transactions: List[CreditTransaction] = []
        self.issuance = DynamicCreditIssuance()
        self.consumption = SmartCreditConsumption()
        self.consensus = LayeredConsensus()
        self.state_channel = CreditStateChannel()
        self.finality = ProbabilisticFinality()

    async def create_account(self, owner_id: str, owner_type: str = "user") -> CreditAccount:
        """创建账户"""
        account = CreditAccount(
            id=f"acc_{uuid.uuid4().hex[:12]}",
            owner_id=owner_id,
            owner_type=owner_type,
            balance=0,
            level="bronze"
        )
        self.accounts[account.id] = account
        return account

    async def get_or_create_account(self, owner_id: str, owner_type: str = "user") -> CreditAccount:
        """获取或创建账户"""
        for acc in self.accounts.values():
            if acc.owner_id == owner_id:
                return acc
        return await self.create_account(owner_id, owner_type)

    async def issue_daily_credits(self, user_id: str) -> dict:
        """发放每日积分"""
        account = await self.get_or_create_account(user_id)

        # 计算积分
        daily_info = await self.issuance.calculate_daily_credits(user_id)
        credits = daily_info["daily_credits"]

        # 更新账户
        account.balance += credits
        account.total_issued += credits
        account.last_transaction = datetime.now()

        # 创建交易记录
        tx = CreditTransaction(
            id=f"tx_{uuid.uuid4().hex[:12]}",
            tx_type=CreditTransactionType.ISSUE,
            to_account=account.id,
            amount=credits,
            balance_before=account.balance - credits,
            balance_after=account.balance,
            status="finalized",
            consensus_layer=ConsensusLayer.IMMEDIATE,
            finality_level=FinalityLevel.FINAL,
            metadata={"source": "daily_issuance"}
        )

        self.transactions.append(tx)

        return {
            "success": True,
            "account_id": account.id,
            "issued_credits": credits,
            "new_balance": account.balance,
            "transaction_id": tx.id
        }

    async def transfer(self, from_id: str, to_id: str, amount: int, memo: str = "") -> dict:
        """转账"""
        from_account = self.accounts.get(from_id)
        to_account = self.accounts.get(to_id)

        if not from_account or not to_account:
            return {"success": False, "error": "账户不存在"}

        if from_account.available_balance < amount:
            return {"success": False, "error": "余额不足"}

        # 创建交易
        tx = CreditTransaction(
            id=f"tx_{uuid.uuid4().hex[:12]}",
            tx_type=CreditTransactionType.TRANSFER,
            from_account=from_id,
            to_account=to_id,
            amount=amount,
            balance_before=from_account.balance,
            balance_after=from_account.balance - amount
        )

        # 处理交易
        result = await self.consensus.process_transaction(tx)

        if result["success"]:
            from_account.balance -= amount
            to_account.balance += amount
            tx.status = "confirmed"

        self.transactions.append(tx)

        return {
            **result,
            "transaction": tx.to_dict()
        }

    async def consume(self, account_id: str, amount: int, purpose: str) -> dict:
        """消耗积分"""
        account = self.accounts.get(account_id)
        if not account:
            return {"success": False, "error": "账户不存在"}

        if account.available_balance < amount:
            return {"success": False, "error": "余额不足"}

        # 创建消费交易
        tx = CreditTransaction(
            id=f"tx_{uuid.uuid4().hex[:12]}",
            tx_type=CreditTransactionType.CONSUME,
            from_account=account_id,
            amount=amount,
            balance_before=account.balance,
            balance_after=account.balance - amount,
            metadata={"purpose": purpose}
        )

        result = await self.consensus.process_transaction(tx)

        if result["success"]:
            account.balance -= amount
            tx.status = "confirmed"

        self.transactions.append(tx)

        return {
            **result,
            "transaction": tx.to_dict()
        }


# ============================================================ 积分经济系统（新增）
# ============================================================

from .system import (
    TransactionType, AchievementType, BadgeType,
    Transaction, Achievement, Badge, UserCredit,
    CreditEconomySystem, get_credit_system,
    add_credit, deduct_credit, transfer_credit,
    get_user_credit, get_user_stats
)


# 全局实例
_credit_account_manager = None
_credit_account_manager_lock = asyncio.Lock()


async def get_credit_account_manager() -> CreditAccountManager:
    """获取积分账户管理器"""
    global _credit_account_manager
    if _credit_account_manager is None:
        async with _credit_account_manager_lock:
            if _credit_account_manager is None:
                _credit_account_manager = CreditAccountManager()
    return _credit_account_manager


__all__ = [
    # 核心类
    "CreditAccount",
    "CreditTransaction",
    "CreditPolicy",
    "StateChannel",
    "SkillListing",
    "IdeaNFT",
    "RevenueToken",
    "PredictionMarket",
    "PredictionShare",
    "DynamicCreditIssuance",
    "SmartCreditConsumption",
    "LayeredConsensus",
    "CreditStateChannel",
    "ProbabilisticFinality",
    "DecentralizedSkillMarket",
    "IdeaNFTMarketplace",
    "SkillRevenueTokens",
    "CreditPredictionMarket",
    "CreditAccountManager",
    "get_credit_account_manager",
    # 新增系统
    "TransactionType",
    "AchievementType",
    "BadgeType",
    "Transaction",
    "Achievement",
    "Badge",
    "UserCredit",
    "CreditEconomySystem",
    "get_credit_system",
    "add_credit",
    "deduct_credit",
    "transfer_credit",
    "get_user_credit",
    "get_user_stats"
]
                break

        if not account:
            return {"error": "账户不存在"}

        recent_txs = [
            tx.to_dict() for tx in self.transactions[-10:]
            if tx.from_account == account.id or tx.to_account == account.id
        ]

        return {
            "account": account.to_dict(),
            "recent_transactions": recent_txs,
            "stats": {
                "total_issued": account.total_issued,
                "total_consumed": account.total_consumed,
                "net_change": account.total_issued - account.total_consumed
            }
        }


# ============================================================
# 全局实例
# ============================================================

_credit_account_manager: Optional[CreditAccountManager] = None
_skill_market: Optional[DecentralizedSkillMarket] = None
_nft_market: Optional[IdeaNFTMarketplace] = None
_prediction_market: Optional[CreditPredictionMarket] = None


def get_credit_manager() -> CreditAccountManager:
    """获取积分管理器"""
    global _credit_account_manager
    if _credit_account_manager is None:
        _credit_account_manager = CreditAccountManager()
    return _credit_account_manager


def get_skill_market() -> DecentralizedSkillMarket:
    """获取技能市场"""
    global _skill_market
    if _skill_market is None:
        _skill_market = DecentralizedSkillMarket()
    return _skill_market


def get_nft_market() -> IdeaNFTMarketplace:
    """获取NFT市场"""
    global _nft_market
    if _nft_market is None:
        _nft_market = IdeaNFTMarketplace()
    return _nft_market


def get_prediction_market() -> CreditPredictionMarket:
    """获取预测市场"""
    global _prediction_market
    if _prediction_market is None:
        _prediction_market = CreditPredictionMarket()
    return _prediction_market


# ============================================================
# 导出
# ============================================================

__all__ = [
    # 枚举
    "CreditTransactionType", "ConsensusLayer", "FinalityLevel",
    "MarketListingType", "DisputeStatus",

    # 数据模型
    "CreditAccount", "CreditTransaction", "CreditPolicy",
    "StateChannel", "SkillListing", "IdeaNFT",
    "RevenueToken", "PredictionMarket", "PredictionShare",

    # 核心类
    "DynamicCreditIssuance",
    "SmartCreditConsumption",
    "LayeredConsensus",
    "CreditStateChannel",
    "ProbabilisticFinality",
    "DecentralizedSkillMarket",
    "IdeaNFTMarketplace",
    "SkillRevenueTokens",
    "CreditPredictionMarket",
    "CreditAccountManager",

    # 全局函数
    "get_credit_manager",
    "get_skill_market",
    "get_nft_market",
    "get_prediction_market",
]