# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 智能合约引擎

实现:
- 合约类型: 知识合约/治理合约/应用合约
- 合约执行: 沙盒环境、确定性执行、资源限制
- 合约模板: 创建合约/验证合约/传播合约/授权合约
"""

import asyncio
import logging
import json
import hashlib
import re
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .models import (
    SmartContract, ContractMetadata, ContractType,
    KnowledgeUnit
)

logger = logging.getLogger(__name__)


class ContractState(Enum):
    """合约状态"""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ExecutionResult(Enum):
    """执行结果"""
    SUCCESS = "success"
    FAILED = "failed"
    REVERTED = "reverted"
    OUT_OF_GAS = "out_of_gas"


@dataclass
class ContractFunction:
    """合约函数"""
    name: str
    params: List[str]
    code: str
    visibility: str = "public"  # public/private
    mutability: str = "view"  # view/pure/payable


@dataclass
class ExecutionContext:
    """执行上下文"""
    contract_id: str
    caller_id: str
    block_time: datetime
    gas_limit: int = 100000
    gas_used: int = 0
    state_changes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionLog:
    """执行日志"""
    contract_id: str
    function_name: str
    caller_id: str
    result: ExecutionResult
    gas_used: int
    return_value: Any
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class SmartContractEngine:
    """智能合约引擎"""

    def __init__(
        self,
        storage: 'DistributedStorage',
        economy: 'TokenEconomy',
        reputation: 'ReputationSystem'
    ):
        """
        初始化智能合约引擎
        
        Args:
            storage: 分布式存储
            economy: 经济系统
            reputation: 信誉系统
        """
        self.storage = storage
        self.economy = economy
        self.reputation = reputation
        
        # 合约注册表
        self.contracts: Dict[str, SmartContract] = {}
        self.contract_templates: Dict[ContractType, str] = {}
        
        # 执行日志
        self.execution_logs: List[ExecutionLog] = []
        
        # 资源限制
        self.max_gas_per_call = 100000
        self.max_storage_per_contract = 10 * 1024 * 1024  # 10MB
        
        # 初始化模板
        self._init_templates()
        
        logger.info("智能合约引擎初始化完成")

    async def stop(self):
        """停止引擎"""
        await self._save_contracts()
        logger.info("智能合约引擎已停止")

    # ==================== 模板初始化 ====================

    def _init_templates(self):
        """初始化合约模板"""
        self.contract_templates = {
            ContractType.KNOWLEDGE_CREATE: self._knowledge_create_template(),
            ContractType.KNOWLEDGE_VERIFY: self._knowledge_verify_template(),
            ContractType.KNOWLEDGE_SPREAD: self._knowledge_spread_template(),
            ContractType.KNOWLEDGE_LEARN: self._knowledge_learn_template(),
            ContractType.COPYRIGHT: self._copyright_template(),
            ContractType.AUTHORIZATION: self._authorization_template(),
            ContractType.COLLABORATION: self._collaboration_template(),
            ContractType.TEACHING: self._teaching_template(),
            ContractType.GOVERNANCE: self._governance_template()
        }

    def _knowledge_create_template(self) -> str:
        """知识创建合约模板"""
        return """
# 知识创建合约
contract KnowledgeCreate:
    # 参数
    creator: str
    title: str
    content: str
    knowledge_type: str
    domain_tags: list
    
    # 逻辑
    def create():
        # 验证内容
        require(len(self.content) > 0, "内容不能为空")
        require(len(self.title) > 0, "标题不能为空")
        
        # 计算激励
        base_reward = 10
        quality_bonus = calculate_quality(self.content)
        total_reward = base_reward + quality_bonus
        
        # 分配激励
        mint(self.creator, total_reward, "KNC")
        
        return True
    
    def calculate_quality(content: str) -> float:
        # 简化质量计算
        length_factor = min(len(content) / 1000, 1.0)
        return length_factor * 10
"""

    def _knowledge_verify_template(self) -> str:
        """知识验证合约模板"""
        return """
# 知识验证合约
contract KnowledgeVerify:
    # 参数
    knowledge_id: str
    verifier: str
    is_valid: bool
    confidence: float
    
    # 逻辑
    def verify():
        # 检查验证者信誉
        rep = get_reputation(self.verifier)
        require(rep > 30, "信誉不足")
        
        if self.is_valid:
            # 正确验证奖励
            reward = 2 * self.confidence
            mint(self.verifier, reward, "KNC")
        else:
            # 错误验证惩罚
            penalty = 1
            burn(self.verifier, penalty, "KNC")
        
        # 更新知识验证状态
        update_verification_status(self.knowledge_id, self.is_valid)
        
        return True
"""

    def _knowledge_spread_template(self) -> str:
        """知识传播合约模板"""
        return """
# 知识传播合约
contract KnowledgeSpread:
    # 参数
    knowledge_id: str
    spreader: str
    target_count: int
    
    def spread():
        # 检查知识有效性
        k = get_knowledge(self.knowledge_id)
        require(k.is_verified, "知识未验证")
        
        # 计算传播奖励
        effectiveness = min(self.target_count / 10, 1.0)
        reward = 1 * effectiveness
        
        mint(self.spreader, reward, "KNC")
        
        return True
"""

    def _knowledge_learn_template(self) -> str:
        """知识学习合约模板"""
        return """
# 知识学习合约
contract KnowledgeLearn:
    # 参数
    knowledge_id: str
    learner: str
    quiz_score: float
    
    def learn():
        # 检查知识存在
        k = get_knowledge(self.knowledge_id)
        require(k != null, "知识不存在")
        
        # 计算学习奖励
        base_reward = 0.5
        score_bonus = self.quiz_score * 0.5 if self.quiz_score else 0
        
        mint(self.learner, base_reward + score_bonus, "LNC")
        
        # 记录学习
        add_learning_record(self.knowledge_id, self.learner)
        
        return True
"""

    def _copyright_template(self) -> str:
        """版权保护合约模板"""
        return """
# 版权保护合约
contract Copyright:
    # 参数
    creator: str
    knowledge_id: str
    license_type: str
    
    def register():
        # 记录版权信息
        store("copyright", {
            "creator": self.creator,
            "knowledge_id": self.knowledge_id,
            "license": self.license_type,
            "timestamp": now()
        })
        
        return True
    
    def check_permission(user: str, action: str) -> bool:
        copyright = load("copyright", self.knowledge_id)
        
        if copyright.license == "CC0":
            return True
        
        if action == "read":
            return True
        
        if action == "modify" or action == "commercial":
            return copyright.creator == user
        
        return False
"""

    def _authorization_template(self) -> str:
        """知识授权合约模板"""
        return """
# 知识授权合约
contract Authorization:
    # 参数
    knowledge_id: str
    owner: str
    authorized_users: list
    fee: float
    
    def authorize(user: str):
        require(msg.sender == self.owner, "仅所有者可授权")
        
        add_to_list("authorized", self.knowledge_id, user)
        
        return True
    
    def request_access(user: str) -> bool:
        fee = get_storage("fee", self.knowledge_id)
        
        if fee > 0:
            transfer(user, self.owner, fee, "KNC")
        
        add_to_list("authorized", self.knowledge_id, user)
        
        return True
"""

    def _collaboration_template(self) -> str:
        """协作创作合约模板"""
        return """
# 协作创作合约
contract Collaboration:
    # 参数
    collaborators: list
    task: str
    reward_pool: float
    
    def create_task():
        # 分配奖励池
        per_person = self.reward_pool / len(self.collaborators)
        
        for collaborator in self.collaborators:
            reserve(collaborator, per_person, "KNC")
        
        return True
    
    def submit_contribution(contributor: str, content: str):
        require(is_in_list(self.collaborators, contributor), "非协作者")
        
        store("contribution", contributor, content)
        
        return True
    
    def distribute_rewards():
        contributions = load_all("contribution")
        
        total_score = sum(c.score for c in contributions)
        
        for contributor, contribution in contributions.items():
            share = (contribution.score / total_score) * self.reward_pool
            release(contributor, share, "KNC")
        
        return True
"""

    def _teaching_template(self) -> str:
        """教学服务合约模板"""
        return """
# 教学服务合约
contract Teaching:
    # 参数
    teacher: str
    student: str
    knowledge_id: str
    price: float
    effectiveness_threshold: float
    
    def enroll():
        # 学生付款
        transfer(self.student, self.teacher, self.price, "KNC")
        
        # 记录注册
        add_to_list("students", self.teacher, self.student)
        
        return True
    
    def rate_teacher(score: float):
        require(is_in_list("students", self.teacher, msg.sender), "非学生")
        
        # 检查效果
        if score >= self.effectiveness_threshold:
            bonus = self.price * 0.2
            mint(self.teacher, bonus, "KNC")
        
        # 更新评分
        update_teacher_rating(self.teacher, score)
        
        return True
"""

    def _governance_template(self) -> str:
        """治理合约模板"""
        return """
# 治理合约
contract Governance:
    # 参数
    proposal_id: str
    proposer: str
    description: str
    voting_deadline: timestamp
    
    def create_proposal():
        # 需要治理代币
        gnc_balance = get_balance(self.proposer, "GNC")
        require(gnc_balance >= 10, "需要至少10个治理代币")
        
        # 锁定代币
        lock(self.proposer, 10, "GNC")
        
        store("proposal", self.proposal_id, {
            "proposer": self.proposer,
            "description": self.description,
            "votes_for": 0,
            "votes_against": 0,
            "deadline": self.voting_deadline
        })
        
        return True
    
    def vote(voter: str, support: bool, weight: float):
        proposal = load("proposal", self.proposal_id)
        
        require(now() < proposal.deadline, "投票已结束")
        require(!has_voted(self.proposal_id, voter), "已投票")
        
        if support:
            proposal.votes_for += weight
        else:
            proposal.votes_against += weight
        
        record_vote(self.proposal_id, voter, support, weight)
        
        return True
    
    def execute():
        proposal = load("proposal", self.proposal_id)
        
        require(now() >= proposal.deadline, "投票未结束")
        
        if proposal.votes_for > proposal.votes_against:
            execute_proposal(self.proposal_id)
        
        # 解锁代币
        unlock(proposal.proposer, 10, "GNC")
        
        return True
"""

    # ==================== 合约部署 ====================

    async def deploy(
        self,
        contract_type: ContractType,
        creator_id: str,
        code: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        部署合约
        
        Args:
            contract_type: 合约类型
            creator_id: 创建者ID
            code: 合约代码（可选）
            params: 合约参数
            
        Returns:
            合约ID
        """
        try:
            # 生成合约ID
            contract_id = self._generate_contract_id(creator_id, contract_type)
            
            # 获取代码
            contract_code = code or self.contract_templates.get(contract_type, "")
            
            if not contract_code:
                logger.error(f"未找到合约模板: {contract_type}")
                return None
            
            # 创建合约元数据
            metadata = ContractMetadata(
                contract_id=contract_id,
                contract_type=contract_type.value,
                creator_id=creator_id,
                created_at=datetime.now(),
                version=1,
                status="active"
            )
            
            # 创建合约
            contract = SmartContract(
                metadata=metadata,
                code=contract_code,
                state=params or {}
            )
            
            self.contracts[contract_id] = contract
            
            logger.info(f"✅ 合约部署成功: {contract_id} ({contract_type.value})")
            
            return contract_id
            
        except Exception as e:
            logger.error(f"部署合约失败: {e}")
            return None

    # ==================== 合约执行 ====================

    async def execute(
        self,
        contract_id: str,
        function_name: str,
        args: Dict[str, Any],
        caller_id: str
    ) -> Optional[Any]:
        """
        执行合约
        
        Args:
            contract_id: 合约ID
            function_name: 函数名
            args: 函数参数
            caller_id: 调用者ID
            
        Returns:
            执行结果
        """
        contract = self.contracts.get(contract_id)
        if not contract:
            logger.error(f"合约不存在: {contract_id}")
            return None
        
        # 创建执行上下文
        ctx = ExecutionContext(
            contract_id=contract_id,
            caller_id=caller_id,
            block_time=datetime.now()
        )
        
        # 执行函数
        try:
            result = await self._execute_function(contract, function_name, args, ctx)
            
            # 记录执行日志
            log = ExecutionLog(
                contract_id=contract_id,
                function_name=function_name,
                caller_id=caller_id,
                result=ExecutionResult.SUCCESS,
                gas_used=ctx.gas_used,
                return_value=result
            )
            self.execution_logs.append(log)
            
            # 应用状态变更
            for key, value in ctx.state_changes.items():
                contract.state[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"执行合约失败: {e}")
            
            log = ExecutionLog(
                contract_id=contract_id,
                function_name=function_name,
                caller_id=caller_id,
                result=ExecutionResult.FAILED,
                gas_used=ctx.gas_used,
                error=str(e)
            )
            self.execution_logs.append(log)
            
            return None

    async def _execute_function(
        self,
        contract: SmartContract,
        function_name: str,
        args: Dict[str, Any],
        ctx: ExecutionContext
    ) -> Any:
        """执行合约函数（模拟执行）"""
        # 简化实现：模拟执行合约代码
        gas_cost = 1000  # 模拟gas消耗
        
        if ctx.gas_used + gas_cost > ctx.gas_limit:
            return ExecutionResult.OUT_OF_GAS
        
        ctx.gas_used += gas_cost
        
        # 模拟函数执行
        if function_name == "create":
            return await self._handle_knowledge_create(contract, args, ctx)
        elif function_name == "verify":
            return await self._handle_knowledge_verify(contract, args, ctx)
        elif function_name == "spread":
            return await self._handle_knowledge_spread(contract, args, ctx)
        elif function_name == "learn":
            return await self._handle_knowledge_learn(contract, args, ctx)
        else:
            return {"status": "unknown_function"}

    async def _handle_knowledge_create(
        self,
        contract: SmartContract,
        args: Dict[str, Any],
        ctx: ExecutionContext
    ) -> Dict[str, Any]:
        """处理知识创建"""
        creator = args.get("creator")
        content = args.get("content", "")
        
        # 验证
        if not content:
            raise ValueError("内容不能为空")
        
        # 计算奖励
        base_reward = 10.0
        length_factor = min(len(content) / 1000, 1.0)
        reward = base_reward + length_factor * 10
        
        # 发放奖励
        await self.economy.credit_reward(
            creator, reward, f"contract:{ctx.contract_id}", "KNC"
        )
        
        return {"success": True, "reward": reward}

    async def _handle_knowledge_verify(
        self,
        contract: SmartContract,
        args: Dict[str, Any],
        ctx: ExecutionContext
    ) -> Dict[str, Any]:
        """处理知识验证"""
        verifier = args.get("verifier")
        is_valid = args.get("is_valid", False)
        
        if is_valid:
            reward = 2.0
            await self.economy.credit_reward(
                verifier, reward, f"contract:{ctx.contract_id}", "KNC"
            )
        
        return {"success": True, "reward": reward if is_valid else 0}

    async def _handle_knowledge_spread(
        self,
        contract: SmartContract,
        args: Dict[str, Any],
        ctx: ExecutionContext
    ) -> Dict[str, Any]:
        """处理知识传播"""
        spreader = args.get("spreader")
        target_count = args.get("target_count", 1)
        
        effectiveness = min(target_count / 10, 1.0)
        reward = 1 * effectiveness
        
        await self.economy.credit_reward(
            spreader, reward, f"contract:{ctx.contract_id}", "KNC"
        )
        
        return {"success": True, "reward": reward}

    async def _handle_knowledge_learn(
        self,
        contract: SmartContract,
        args: Dict[str, Any],
        ctx: ExecutionContext
    ) -> Dict[str, Any]:
        """处理知识学习"""
        learner = args.get("learner")
        quiz_score = args.get("quiz_score", 0)
        
        base_reward = 0.5
        score_bonus = quiz_score * 0.5
        
        await self.economy.credit_reward(
            learner, base_reward + score_bonus, f"contract:{ctx.contract_id}", "LNC"
        )
        
        return {"success": True, "reward": base_reward + score_bonus}

    # ==================== 辅助方法 ====================

    def _generate_contract_id(self, creator_id: str, contract_type: ContractType) -> str:
        """生成合约ID"""
        data = f"{creator_id}{contract_type.value}{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def get_contract(self, contract_id: str) -> Optional[SmartContract]:
        """获取合约"""
        return self.contracts.get(contract_id)

    def get_contracts_by_creator(self, creator_id: str) -> List[SmartContract]:
        """获取创建者的所有合约"""
        return [
            c for c in self.contracts.values()
            if c.metadata.creator_id == creator_id
        ]

    def get_contracts_by_type(self, contract_type: ContractType) -> List[SmartContract]:
        """获取指定类型的合约"""
        return [
            c for c in self.contracts.values()
            if c.metadata.contract_type == contract_type.value
        ]

    def get_contract_count(self) -> int:
        """获取合约数量"""
        return len(self.contracts)

    async def _save_contracts(self):
        """保存合约"""
        # 简化实现
        pass

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        total = len(self.execution_logs)
        success = sum(1 for log in self.execution_logs if log.result == ExecutionResult.SUCCESS)
        
        return {
            "total_executions": total,
            "successful": success,
            "failed": total - success,
            "avg_gas_used": sum(log.gas_used for log in self.execution_logs) / total if total > 0 else 0
        }
