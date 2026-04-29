# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 代币经济系统

实现:
- 代币类型: KNC/RPC/CNC/LNC/GNC
- 代币分配: 30%知识创造, 20%知识验证, 15%传播, 15%学习, 10%系统, 10%生态
- 激励机制: 创建激励、验证激励、传播激励、学习激励、教学激励
"""

import asyncio
import logging
import json
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .models import TokenBalance, TokenTransaction, TokenType

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """代币类型"""
    KNC = "KNC"  # 知识币 - 主要流通代币
    RPC = "RPC"  # 信誉币 - 代表节点信誉
    CNC = "CNC"  # 贡献币 - 代表知识贡献
    LNC = "LNC"  # 学习币 - 代表学习成就
    GNC = "GNC"  # 治理币 - 参与治理权利


@dataclass
class RewardRate:
    """激励比率"""
    knowledge_create: float = 10.0
    knowledge_verify: float = 2.0
    knowledge_spread: float = 1.0
    knowledge_learn: float = 0.5
    teaching: float = 3.0
    collaboration: float = 2.0
    governance: float = 1.0


@dataclass
class TokenDistribution:
    """代币分配配置"""
    knowledge_creator_share: float = 0.30
    verifier_share: float = 0.20
    spreader_share: float = 0.15
    learner_share: float = 0.15
    system_reserve: float = 0.10
    ecosystem_share: float = 0.10


@dataclass
class TransactionRecord:
    """交易记录"""
    tx_id: str
    from_node: Optional[str]
    to_node: str
    token_type: str
    amount: float
    fee: float
    reason: str
    timestamp: datetime
    block_height: int = 0
    status: str = "confirmed"


class TokenEconomy:
    """代币经济系统"""

    def __init__(
        self,
        storage: 'DistributedStorage',
        initial_supply: float = 1_000_000_000
    ):
        """
        初始化代币经济系统
        
        Args:
            storage: 分布式存储
            initial_supply: 初始供应量
        """
        self.storage = storage
        
        # 代币配置
        self.initial_supply = initial_supply
        self.total_supply = initial_supply
        self.circulating_supply = 0.0
        
        # 余额管理
        self.balances: Dict[str, Dict[str, float]] = {}  # node_id -> {token_type: balance}
        
        # 激励配置
        self.reward_rates = RewardRate()
        self.distribution = TokenDistribution()
        
        # 交易记录
        self.transactions: List[TransactionRecord] = []
        self.pending_transactions: List[TransactionRecord] = []
        
        # 储备池
        self.system_reserve: Dict[str, float] = {
            "KNC": 0.0,
            "RPC": 0.0,
            "CNC": 0.0,
            "LNC": 0.0,
            "GNC": 0.0
        }
        
        # 通胀配置
        self.inflation_rate = 0.05  # 5% 年通胀
        self.last_inflation_adjustment = datetime.now()
        
        # 统计
        self.stats = {
            "total_transactions": 0,
            "total_volume": 0.0,
            "avg_transaction_fee": 0.0
        }
        
        logger.info(f"代币经济系统初始化，初始供应量: {initial_supply}")

    async def initialize(self) -> bool:
        """初始化经济系统"""
        try:
            # 加载已有数据
            await self._load_data()
            
            # 如果没有数据，初始化创世分配
            if not self.balances:
                await self._init_genesis_distribution()
            
            logger.info("✅ 代币经济系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"代币经济系统初始化失败: {e}")
            return False

    async def stop(self):
        """停止经济系统"""
        await self._save_data()
        logger.info("代币经济系统已停止")

    # ==================== 余额操作 ====================

    async def get_balance(self, node_id: str) -> Dict[str, float]:
        """
        获取余额
        
        Args:
            node_id: 节点ID
            
        Returns:
            各类代币余额
        """
        if node_id not in self.balances:
            self.balances[node_id] = {
                "KNC": 0.0,
                "RPC": 0.0,
                "CNC": 0.0,
                "LNC": 0.0,
                "GNC": 0.0
            }
        
        return self.balances[node_id]

    async def credit_reward(
        self,
        node_id: str,
        amount: float,
        reason: str,
        token_type: str = "KNC"
    ) -> bool:
        """
        发放奖励
        
        Args:
            node_id: 节点ID
            amount: 金额
            reason: 原因
            token_type: 代币类型
            
        Returns:
            是否成功
        """
        try:
            # 检查储备是否充足
            if self.system_reserve.get(token_type, 0) < amount:
                # 从总供应量获取
                if self.total_supply < amount:
                    logger.warning(f"储备不足，无法发放奖励: {reason}")
                    return False
            
            # 创建交易记录
            tx = TransactionRecord(
                tx_id=self._generate_tx_id(),
                from_node="system",
                to_node=node_id,
                token_type=token_type,
                amount=amount,
                fee=0.0,
                reason=reason,
                timestamp=datetime.now()
            )
            
            # 更新余额
            await self._update_balance(node_id, token_type, amount)
            
            # 记录交易
            self.transactions.append(tx)
            self.stats["total_transactions"] += 1
            self.stats["total_volume"] += amount
            
            logger.debug(f"💰 发放奖励: {node_id} +{amount} {token_type} ({reason})")
            
            return True
            
        except Exception as e:
            logger.error(f"发放奖励失败: {e}")
            return False

    async def transfer(
        self,
        from_node: str,
        to_node: str,
        amount: float,
        token_type: str = "KNC",
        fee: float = 0.0
    ) -> bool:
        """
        转账
        
        Args:
            from_node: 发送者
            to_node: 接收者
            amount: 金额
            token_type: 代币类型
            fee: 手续费
            
        Returns:
            是否成功
        """
        try:
            # 检查余额
            balance = await self.get_balance(from_node)
            if balance.get(token_type, 0) < amount + fee:
                logger.warning(f"余额不足: {from_node}")
                return False
            
            # 创建交易记录
            tx = TransactionRecord(
                tx_id=self._generate_tx_id(),
                from_node=from_node,
                to_node=to_node,
                token_type=token_type,
                amount=amount,
                fee=fee,
                reason="transfer",
                timestamp=datetime.now()
            )
            
            # 更新余额
            await self._update_balance(from_node, token_type, -amount - fee)
            await self._update_balance(to_node, token_type, amount)
            
            # 收取手续费到储备
            if fee > 0:
                self.system_reserve[token_type] = self.system_reserve.get(token_type, 0) + fee
            
            # 记录交易
            self.transactions.append(tx)
            self.stats["total_transactions"] += 1
            self.stats["total_volume"] += amount
            
            logger.debug(f"💸 转账: {from_node} -> {to_node} {amount} {token_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"转账失败: {e}")
            return False

    async def _update_balance(
        self,
        node_id: str,
        token_type: str,
        delta: float
    ):
        """更新余额"""
        if node_id not in self.balances:
            self.balances[node_id] = {
                "KNC": 0.0,
                "RPC": 0.0,
                "CNC": 0.0,
                "LNC": 0.0,
                "GNC": 0.0
            }
        
        self.balances[node_id][token_type] = self.balances[node_id].get(token_type, 0) + delta
        
        # 更新流通量
        if delta > 0:
            self.circulating_supply += delta

    # ==================== 激励分配 ====================

    async def distribute_knowledge_creation_reward(
        self,
        creator_id: str,
        knowledge_value: float
    ) -> Dict[str, float]:
        """
        分配知识创建奖励
        
        Args:
            creator_id: 创建者ID
            knowledge_value: 知识价值
            
        Returns:
            分配结果
        """
        distribution = self.distribution
        
        # 计算各方份额
        creator_share = knowledge_value * distribution.knowledge_creator_share
        verifier_share = knowledge_value * distribution.verifier_share
        spreader_share = knowledge_value * distribution.spreader_share
        learner_share = knowledge_value * distribution.learner_share
        system_share = knowledge_value * distribution.system_reserve
        ecosystem_share = knowledge_value * distribution.ecosystem_share
        
        # 发放创建者奖励
        await self.credit_reward(
            creator_id, creator_share, "knowledge_creation", "KNC"
        )
        
        # 发放贡献币
        await self.credit_reward(
            creator_id, knowledge_value * 0.1, "knowledge_contribution", "CNC"
        )
        
        # 分配到储备
        self.system_reserve["KNC"] += system_share
        
        return {
            "creator": creator_share,
            "verifier_budget": verifier_share,
            "spreader_budget": spreader_share,
            "learner_budget": learner_share,
            "system": system_share,
            "ecosystem": ecosystem_share
        }

    async def distribute_verification_reward(
        self,
        verifier_id: str,
        knowledge_id: str,
        is_valid: bool,
        verifier_share_budget: float,
        total_verifiers: int
    ) -> bool:
        """
        分配验证奖励
        
        Args:
            verifier_id: 验证者ID
            knowledge_id: 知识ID
            is_valid: 验证是否正确
            verifier_share_budget: 验证者总份额
            total_verifiers: 验证者总数
            
        Returns:
            是否成功
        """
        if not is_valid:
            return False
        
        # 按比例分配
        share = verifier_share_budget / total_verifiers
        
        return await self.credit_reward(
            verifier_id, share, f"knowledge_verification:{knowledge_id}", "KNC"
        )

    async def distribute_spread_reward(
        self,
        spreader_id: str,
        knowledge_id: str,
        spread_count: int,
        spreader_share_budget: float
    ) -> bool:
        """
        分配传播奖励
        
        Args:
            spreader_id: 传播者ID
            knowledge_id: 知识ID
            spread_count: 传播次数
            spreader_share_budget: 传播者总份额
            
        Returns:
            是否成功
        """
        # 基于传播效果计算
        effectiveness = min(1.0, spread_count / 10)  # 最多10次传播有效
        share = spreader_share_budget * effectiveness
        
        return await self.credit_reward(
            spreader_id, share, f"knowledge_spread:{knowledge_id}", "KNC"
        )

    async def distribute_learning_reward(
        self,
        learner_id: str,
        knowledge_id: str,
        quiz_score: Optional[float] = None
    ) -> bool:
        """
        分配学习奖励
        
        Args:
            learner_id: 学习者ID
            knowledge_id: 知识ID
            quiz_score: 测试分数
            
        Returns:
            是否成功
        """
        base_reward = self.reward_rates.knowledge_learn
        
        # 基于测试分数调整
        if quiz_score is not None:
            base_reward *= (0.5 + quiz_score * 0.5)
        
        # 发放学习币
        await self.credit_reward(
            learner_id, base_reward, f"knowledge_learn:{knowledge_id}", "LNC"
        )
        
        return await self.credit_reward(
            learner_id, base_reward * 0.5, f"knowledge_learn:{knowledge_id}", "KNC"
        )

    async def distribute_teaching_reward(
        self,
        teacher_id: str,
        student_id: str,
        effectiveness_score: float
    ) -> bool:
        """
        分配教学奖励
        
        Args:
            teacher_id: 教学者ID
            student_id: 学员ID
            effectiveness_score: 教学效果评分
            
        Returns:
            是否成功
        """
        reward = self.reward_rates.teaching * effectiveness_score
        
        return await self.credit_reward(
            teacher_id, reward, f"teaching:{student_id}", "KNC"
        )

    # ==================== 治理代币 ====================

    async def distribute_governance_tokens(
        self,
        node_id: str,
        participation_weight: float
    ) -> bool:
        """
        分配治理代币
        
        Args:
            node_id: 节点ID
            participation_weight: 参与权重
            
        Returns:
            是否成功
        """
        # 根据参与度分配治理代币
        reward = self.reward_rates.governance * participation_weight
        
        return await self.credit_reward(
            node_id, reward, "governance_participation", "GNC"
        )

    async def stake_governance_tokens(
        self,
        node_id: str,
        amount: float
    ) -> bool:
        """
        质押治理代币
        
        Args:
            node_id: 节点ID
            amount: 质押数量
            
        Returns:
            是否成功
        """
        balance = await self.get_balance(node_id)
        
        if balance.get("GNC", 0) < amount:
            return False
        
        # 扣除余额并添加到质押池
        await self._update_balance(node_id, "GNC", -amount)
        
        # 这里应该有一个质押池管理
        # 简化实现
        
        return True

    # ==================== 通胀调整 ====================

    async def adjust_inflation(self):
        """调整通胀"""
        now = datetime.now()
        time_since_adjust = (now - self.last_inflation_adjustment).total_seconds()
        
        # 每年调整一次
        if time_since_adjust < 365 * 24 * 3600:
            return
        
        # 计算新供应量
        new_supply = self.total_supply * (1 + self.inflation_rate)
        inflation_amount = new_supply - self.total_supply
        
        # 添加到系统储备
        self.system_reserve["KNC"] += inflation_amount
        self.total_supply = new_supply
        
        self.last_inflation_adjustment = now
        
        logger.info(f"通胀调整: 新供应量 {self.total_supply:.2f}")

    # ==================== 数据管理 ====================

    async def _init_genesis_distribution(self):
        """初始化创世分配"""
        # 分配初始代币给系统储备
        self.system_reserve = {
            "KNC": self.initial_supply * 0.5,
            "RPC": self.initial_supply * 0.1,
            "CNC": self.initial_supply * 0.1,
            "LNC": self.initial_supply * 0.1,
            "GNC": self.initial_supply * 0.1
        }
        
        self.circulating_supply = self.initial_supply * 0.5
        
        logger.info("创世分配完成")

    async def _save_data(self):
        """保存数据"""
        try:
            data = {
                "total_supply": self.total_supply,
                "circulating_supply": self.circulating_supply,
                "balances": self.balances,
                "system_reserve": self.system_reserve,
                "transactions": [
                    {
                        "tx_id": tx.tx_id,
                        "from_node": tx.from_node,
                        "to_node": tx.to_node,
                        "token_type": tx.token_type,
                        "amount": tx.amount,
                        "fee": tx.fee,
                        "reason": tx.reason,
                        "timestamp": tx.timestamp.isoformat()
                    }
                    for tx in self.transactions[-1000:]  # 只保存最近1000条
                ]
            }
            
            await self.storage.put("economy_data", data)
            
        except Exception as e:
            logger.error(f"保存经济数据失败: {e}")

    async def _load_data(self):
        """加载数据"""
        try:
            data = await self.storage.get("economy_data")
            if data:
                self.total_supply = data.get("total_supply", self.initial_supply)
                self.circulating_supply = data.get("circulating_supply", 0)
                self.balances = data.get("balances", {})
                self.system_reserve = data.get("system_reserve", self.system_reserve)
                
                # 重建交易记录
                for tx_data in data.get("transactions", []):
                    tx = TransactionRecord(
                        tx_id=tx_data["tx_id"],
                        from_node=tx_data["from_node"],
                        to_node=tx_data["to_node"],
                        token_type=tx_data["token_type"],
                        amount=tx_data["amount"],
                        fee=tx_data["fee"],
                        reason=tx_data["reason"],
                        timestamp=datetime.fromisoformat(tx_data["timestamp"])
                    )
                    self.transactions.append(tx)
                    
        except Exception as e:
            logger.error(f"加载经济数据失败: {e}")

    # ==================== 查询 ====================

    def _generate_tx_id(self) -> str:
        """生成交易ID"""
        import time
        import random
        data = f"{time.time()}{random.randint(0, 10000)}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]

    def get_total_supply(self) -> float:
        """获取总供应量"""
        return self.total_supply

    def get_circulating_supply(self) -> float:
        """获取流通量"""
        return self.circulating_supply

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_supply": self.total_supply,
            "circulating_supply": self.circulating_supply,
            "system_reserve": self.system_reserve,
            "total_transactions": self.stats["total_transactions"],
            "total_volume": self.stats["total_volume"],
            "reward_rates": {
                "knowledge_create": self.reward_rates.knowledge_create,
                "knowledge_verify": self.reward_rates.knowledge_verify,
                "knowledge_spread": self.reward_rates.knowledge_spread,
                "knowledge_learn": self.reward_rates.knowledge_learn,
                "teaching": self.reward_rates.teaching
            }
        }
