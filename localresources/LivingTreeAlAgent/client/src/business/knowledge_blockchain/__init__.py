# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 (Decentralized Knowledge Blockchain System)

核心模块整合:
- 知识区块链: 知识单元存储、区块管理、共识机制
- 节点智能体: 感知、学习、决策、行动
- 对话系统: 节点间对话、协作学习、进化
- 分布式存储: DHT网络、碎片存储、智能检索
- 经济系统: 代币经济、信誉系统、激励分配
- 智能合约: 知识合约、治理合约
- 安全模块: 加密、隐私、攻击防护
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .models import (
    NodeType, KnowledgeType, KnowledgeUnit, Block, Transaction,
    NodeProfile, ReputationScore, DialogueMessage, SmartContract
)
from .blockchain import KnowledgeBlockchain
from .consensus import ConsensusEngine, ConsensusResult
from .knowledge_unit import KnowledgeManager
from .node_agent import NodeAgent, AgentConfig
from .dialogue_system import DialogueSystem, DialogueSession
from .storage import DistributedStorage
from .economy import TokenEconomy, TokenType
from .reputation import ReputationSystem
from .smart_contracts import SmartContractEngine, ContractType
from .security import SecurityModule

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """系统运行状态"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SYNCING = "syncing"
    SHUTDOWN = "shutdown"


@dataclass
class SystemStats:
    """系统统计信息"""
    total_knowledge_units: int = 0
    total_blocks: int = 0
    total_nodes: int = 0
    active_nodes: int = 0
    total_transactions: int = 0
    total_dialogues: int = 0
    total_contracts: int = 0
    total_tokens: int = 0
    avg_reputation: float = 0.0
    last_block_time: Optional[datetime] = None


class KnowledgeBlockchainSystem:
    """去中心化知识区块链系统主类"""

    def __init__(
        self,
        node_id: str,
        node_type: NodeType = NodeType.LIGHT,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化系统
        
        Args:
            node_id: 节点唯一标识
            node_type: 节点类型
            config: 配置字典
        """
        self.node_id = node_id
        self.node_type = node_type
        self.config = config or {}
        self.state = SystemState.INITIALIZING

        # 核心组件
        self.blockchain: Optional[KnowledgeBlockchain] = None
        self.consensus: Optional[ConsensusEngine] = None
        self.knowledge_manager: Optional[KnowledgeManager] = None
        self.node_agent: Optional[NodeAgent] = None
        self.dialogue_system: Optional[DialogueSystem] = None
        self.storage: Optional[DistributedStorage] = None
        self.economy: Optional[TokenEconomy] = None
        self.reputation: Optional[ReputationSystem] = None
        self.smart_contracts: Optional[SmartContractEngine] = None
        self.security: Optional[SecurityModule] = None

        # 事件回调
        self._event_handlers: Dict[str, List[callable]] = {}

        logger.info(f"初始化知识区块链系统: {node_id} ({node_type.value})")

    async def start(self) -> bool:
        """
        启动系统
        
        Returns:
            启动是否成功
        """
        try:
            logger.info("正在启动知识区块链系统...")
            self.state = SystemState.INITIALIZING

            # 初始化安全模块（最先启动，依赖最少）
            self.security = SecurityModule(self.config.get("security", {}))
            await self.security.initialize()

            # 初始化分布式存储
            self.storage = DistributedStorage(
                node_id=self.node_id,
                storage_path=self.config.get("storage_path", f"./data/kb_{self.node_id}"),
                max_storage=self.config.get("max_storage", 10 * 1024 * 1024 * 1024)  # 10GB
            )
            await self.storage.start()

            # 初始化区块链
            self.blockchain = KnowledgeBlockchain(
                node_id=self.node_id,
                storage=self.storage
            )
            await self.blockchain.initialize()

            # 初始化共识引擎
            self.consensus = ConsensusEngine(
                blockchain=self.blockchain,
                node_id=self.node_id,
                node_type=self.node_type
            )

            # 初始化知识管理器
            self.knowledge_manager = KnowledgeManager(
                blockchain=self.blockchain,
                storage=self.storage
            )

            # 初始化经济系统
            self.economy = TokenEconomy(
                storage=self.storage,
                initial_supply=self.config.get("initial_supply", 1_000_000_000)
            )
            await self.economy.initialize()

            # 初始化信誉系统
            self.reputation = ReputationSystem(
                storage=self.storage,
                economy=self.economy
            )
            await self.reputation.initialize(self.node_id)

            # 初始化智能合约引擎
            self.smart_contracts = SmartContractEngine(
                storage=self.storage,
                economy=self.economy,
                reputation=self.reputation
            )

            # 初始化节点智能体
            agent_config = AgentConfig(
                node_id=self.node_id,
                node_type=self.node_type,
                learning_rate=self.config.get("learning_rate", 0.01),
                memory_size=self.config.get("memory_size", 1000)
            )
            self.node_agent = NodeAgent(
                config=agent_config,
                knowledge_manager=self.knowledge_manager,
                reputation=self.reputation,
                economy=self.economy
            )
            await self.node_agent.start()

            # 初始化对话系统
            self.dialogue_system = DialogueSystem(
                node_id=self.node_id,
                node_agent=self.node_agent,
                knowledge_manager=self.knowledge_manager
            )
            await self.dialogue_system.start()

            self.state = SystemState.RUNNING
            logger.info("✅ 知识区块链系统启动成功")
            return True

        except Exception as e:
            logger.error(f"❌ 系统启动失败: {e}")
            self.state = SystemState.SHUTDOWN
            return False

    async def stop(self):
        """停止系统"""
        logger.info("正在停止知识区块链系统...")
        self.state = SystemState.SHUTDOWN

        # 按依赖顺序停止组件
        if self.dialogue_system:
            await self.dialogue_system.stop()
        if self.node_agent:
            await self.node_agent.stop()
        if self.smart_contracts:
            await self.smart_contracts.stop()
        if self.reputation:
            await self.reputation.stop()
        if self.economy:
            await self.economy.stop()
        if self.blockchain:
            await self.blockchain.stop()
        if self.storage:
            await self.storage.stop()
        if self.security:
            await self.security.stop()

        logger.info("✅ 系统已停止")

    # ==================== 知识操作 ====================

    async def create_knowledge(
        self,
        title: str,
        content: str,
        knowledge_type: KnowledgeType,
        domain_tags: List[str],
        references: Optional[List[str]] = None,
        attachments: Optional[Dict[str, Any]] = None
    ) -> Optional[KnowledgeUnit]:
        """
        创建新知识
        
        Args:
            title: 知识标题
            content: 知识内容
            knowledge_type: 知识类型
            domain_tags: 领域标签
            references: 引用其他知识ID
            attachments: 附件
            
        Returns:
            创建的知识单元，失败返回None
        """
        try:
            # 创建知识单元
            knowledge = await self.knowledge_manager.create_knowledge(
                creator_id=self.node_id,
                title=title,
                content=content,
                knowledge_type=knowledge_type,
                domain_tags=domain_tags,
                references=references or [],
                attachments=attachments or {}
            )

            # 提交到共识
            tx = self._create_transaction(
                tx_type="knowledge_create",
                data=knowledge.to_dict()
            )

            # 等待共识确认
            result = await self.consensus.propose_and_wait(
                transaction=tx,
                timeout=30
            )

            if result.accepted:
                # 获得创建激励
                await self.economy.credit_reward(
                    node_id=self.node_id,
                    amount=self.economy.reward_rates["knowledge_create"],
                    reason="knowledge_creation"
                )
                logger.info(f"✅ 知识创建成功: {knowledge.knowledge_id}")
                return knowledge
            else:
                logger.warning(f"❌ 知识创建被拒绝: {result.reason}")
                return None

        except Exception as e:
            logger.error(f"创建知识失败: {e}")
            return None

    async def verify_knowledge(
        self,
        knowledge_id: str,
        is_valid: bool,
        comments: Optional[str] = None
    ) -> bool:
        """
        验证知识
        
        Args:
            knowledge_id: 知识ID
            is_valid: 是否有效
            comments: 验证意见
            
        Returns:
            验证是否成功
        """
        try:
            result = await self.consensus.submit_verification(
                verifier_id=self.node_id,
                knowledge_id=knowledge_id,
                is_valid=is_valid,
                comments=comments
            )

            if result.accepted:
                # 获得验证激励
                reward = self.economy.reward_rates["knowledge_verify"]
                if is_valid:
                    await self.economy.credit_reward(
                        node_id=self.node_id,
                        amount=reward,
                        reason="knowledge_verification"
                    )

                # 更新信誉
                await self.reputation.record_verification(
                    node_id=self.node_id,
                    knowledge_id=knowledge_id,
                    is_valid=is_valid
                )

            return result.accepted

        except Exception as e:
            logger.error(f"验证知识失败: {e}")
            return False

    async def learn_knowledge(
        self,
        knowledge_id: str,
        learning_notes: Optional[str] = None
    ) -> bool:
        """
        学习知识
        
        Args:
            knowledge_id: 知识ID
            learning_notes: 学习笔记
            
        Returns:
            学习是否成功
        """
        try:
            # 更新学习记录
            await self.knowledge_manager.record_learning(
                knowledge_id=knowledge_id,
                learner_id=self.node_id,
                notes=learning_notes
            )

            # 更新信誉
            await self.reputation.record_learning(
                node_id=self.node_id,
                knowledge_id=knowledge_id
            )

            # 获得学习激励
            await self.economy.credit_reward(
                node_id=self.node_id,
                amount=self.economy.reward_rates["knowledge_learn"],
                reason="knowledge_learning"
            )

            return True

        except Exception as e:
            logger.error(f"学习知识失败: {e}")
            return False

    async def share_knowledge(
        self,
        knowledge_id: str,
        target_node_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        传播知识
        
        Args:
            knowledge_id: 知识ID
            target_node_ids: 目标节点列表，None表示广播
            
        Returns:
            分享结果
        """
        try:
            # 获取知识
            knowledge = await self.knowledge_manager.get_knowledge(knowledge_id)
            if not knowledge:
                return {"success": False, "reason": "knowledge_not_found"}

            # 更新传播计数
            await self.knowledge_manager.increment_spread_count(knowledge_id)

            # 更新传播者信誉
            await self.reputation.record_spread(
                node_id=self.node_id,
                knowledge_id=knowledge_id
            )

            # 获得传播激励
            await self.economy.credit_reward(
                node_id=self.node_id,
                amount=self.economy.reward_rates["knowledge_spread"],
                reason="knowledge_spread"
            )

            return {
                "success": True,
                "knowledge_id": knowledge_id,
                "shared_by": self.node_id,
                "targets": target_node_ids or ["broadcast"]
            }

        except Exception as e:
            logger.error(f"传播知识失败: {e}")
            return {"success": False, "reason": str(e)}

    async def search_knowledge(
        self,
        query: str,
        search_type: str = "semantic",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[KnowledgeUnit]:
        """
        搜索知识
        
        Args:
            query: 搜索查询
            search_type: 搜索类型 (keyword/semantic/related)
            filters: 过滤条件
            limit: 返回数量限制
            
        Returns:
            匹配的知识单元列表
        """
        try:
            results = await self.knowledge_manager.search(
                query=query,
                search_type=search_type,
                filters=filters,
                limit=limit
            )

            # 根据信誉排序
            if results:
                scored_results = []
                for k in results:
                    rep = await self.reputation.get_node_reputation(k.creator_id)
                    quality = k.verification_info.get("pass_rate", 0.5)
                    score = rep.total_score * 0.3 + quality * 100 * 0.7
                    scored_results.append((score, k))

                scored_results.sort(key=lambda x: x[0], reverse=True)
                return [k for _, k in scored_results[:limit]]

            return []

        except Exception as e:
            logger.error(f"搜索知识失败: {e}")
            return []

    # ==================== 对话系统 ====================

    async def start_dialogue(
        self,
        target_node_id: str,
        dialogue_type: str = "knowledge_query"
    ) -> Optional[DialogueSession]:
        """
        发起对话
        
        Args:
            target_node_id: 目标节点ID
            dialogue_type: 对话类型
            
        Returns:
            对话会话
        """
        try:
            session = await self.dialogue_system.create_session(
                initiator_id=self.node_id,
                target_id=target_node_id,
                dialogue_type=dialogue_type
            )

            if session:
                logger.info(f"✅ 对话会话创建: {session.session_id}")
                return session
            else:
                logger.warning(f"❌ 对话会话创建失败")
                return None

        except Exception as e:
            logger.error(f"创建对话失败: {e}")
            return None

    async def send_message(
        self,
        session_id: str,
        content: str,
        message_type: str = "text"
    ) -> bool:
        """
        发送消息
        
        Args:
            session_id: 会话ID
            content: 消息内容
            message_type: 消息类型
            
        Returns:
            发送是否成功
        """
        try:
            message = DialogueMessage(
                sender_id=self.node_id,
                content=content,
                message_type=message_type,
                timestamp=datetime.now()
            )

            return await self.dialogue_system.send_message(session_id, message)

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def get_dialogue_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[DialogueMessage]:
        """获取对话历史"""
        return await self.dialogue_system.get_history(session_id, limit)

    # ==================== 智能合约 ====================

    async def deploy_contract(
        self,
        contract_type: ContractType,
        code: str,
        params: Dict[str, Any]
    ) -> Optional[str]:
        """
        部署智能合约
        
        Args:
            contract_type: 合约类型
            code: 合约代码
            params: 合约参数
            
        Returns:
            合约ID，失败返回None
        """
        try:
            contract_id = await self.smart_contracts.deploy(
                contract_type=contract_type,
                creator_id=self.node_id,
                code=code,
                params=params
            )

            if contract_id:
                logger.info(f"✅ 合约部署成功: {contract_id}")
                return contract_id
            else:
                logger.warning(f"❌ 合约部署失败")
                return None

        except Exception as e:
            logger.error(f"部署合约失败: {e}")
            return None

    async def execute_contract(
        self,
        contract_id: str,
        function_name: str,
        args: Dict[str, Any]
    ) -> Optional[Any]:
        """
        执行合约
        
        Args:
            contract_id: 合约ID
            function_name: 函数名
            args: 函数参数
            
        Returns:
            执行结果
        """
        try:
            result = await self.smart_contracts.execute(
                contract_id=contract_id,
                function_name=function_name,
                args=args,
                caller_id=self.node_id
            )

            return result

        except Exception as e:
            logger.error(f"执行合约失败: {e}")
            return None

    # ==================== 节点管理 ====================

    async def get_node_profile(self) -> Optional[NodeProfile]:
        """获取当前节点配置"""
        return await self.reputation.get_node_profile(self.node_id)

    async def get_reputation(self) -> Optional[ReputationScore]:
        """获取当前节点信誉"""
        return await self.reputation.get_node_reputation(self.node_id)

    async def get_token_balance(self) -> Dict[str, float]:
        """获取代币余额"""
        return await self.economy.get_balance(self.node_id)

    # ==================== 系统状态 ====================

    def get_system_stats(self) -> SystemStats:
        """获取系统统计"""
        stats = SystemStats()

        if self.blockchain:
            stats.total_blocks = self.blockchain.get_block_count()
            stats.total_transactions = self.blockchain.get_transaction_count()
            stats.last_block_time = self.blockchain.get_last_block_time()

        if self.knowledge_manager:
            stats.total_knowledge_units = self.knowledge_manager.get_knowledge_count()

        if self.dialogue_system:
            stats.total_dialogues = self.dialogue_system.get_session_count()

        if self.smart_contracts:
            stats.total_contracts = self.smart_contracts.get_contract_count()

        if self.economy:
            stats.total_tokens = self.economy.get_total_supply()

        if self.reputation:
            stats.avg_reputation = self.reputation.get_average_reputation()

        return stats

    # ==================== 事件处理 ====================

    def on(self, event_name: str, handler: callable):
        """注册事件处理器"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def off(self, event_name: str, handler: callable):
        """取消注册事件处理器"""
        if event_name in self._event_handlers:
            self._event_handlers[event_name].remove(handler)

    async def _emit(self, event_name: str, data: Any):
        """触发事件"""
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理器错误: {e}")

    # ==================== 内部方法 ====================

    def _create_transaction(
        self,
        tx_type: str,
        data: Dict[str, Any]
    ) -> Transaction:
        """创建交易"""
        return Transaction(
            tx_id=self._generate_tx_id(),
            tx_type=tx_type,
            sender_id=self.node_id,
            data=data,
            timestamp=datetime.now(),
            signature=""
        )

    def _generate_tx_id(self) -> str:
        """生成交易ID"""
        import hashlib
        import time
        content = f"{self.node_id}{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ==================== P2P 网络接口 ====================

    async def connect_to_peer(self, peer_info: Dict[str, Any]) -> bool:
        """连接到对等节点"""
        # 实现P2P连接逻辑
        return True

    async def broadcast_block(self, block: Block) -> int:
        """广播区块到网络"""
        # 实现广播逻辑
        return 0

    async def sync_with_network(self) -> bool:
        """与网络同步"""
        self.state = SystemState.SYNCING
        try:
            # 同步区块链
            await self.blockchain.sync()
            # 同步知识
            await self.knowledge_manager.sync()
            # 同步节点
            await self.reputation.sync()
            self.state = SystemState.RUNNING
            return True
        except Exception as e:
            logger.error(f"网络同步失败: {e}")
            self.state = SystemState.RUNNING
            return False


# ==================== 工厂函数 ====================

async def create_knowledge_blockchain_system(
    node_id: str,
    node_type: NodeType = NodeType.LIGHT,
    config: Optional[Dict[str, Any]] = None
) -> KnowledgeBlockchainSystem:
    """
    创建知识区块链系统实例
    
    Args:
        node_id: 节点ID
        node_type: 节点类型
        config: 配置
        
    Returns:
        系统实例
    """
    system = KnowledgeBlockchainSystem(
        node_id=node_id,
        node_type=node_type,
        config=config
    )
    await system.start()
    return system
