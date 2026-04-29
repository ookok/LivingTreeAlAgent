# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 节点智能体

实现节点智能:
- 感知模块: 知识感知、对话感知、环境感知、需求感知
- 学习模块: 知识学习、对话学习、行为学习、协作学习
- 决策模块: 知识决策、对话决策、传播决策、验证决策
- 行动模块: 知识行动、对话行动、传播行动、验证行动
"""

import asyncio
import logging
import json
import random
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from .models import NodeType, KnowledgeUnit, DialogueMessage


class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    LEARNING = "learning"
    DIALOGUING = "dialoguing"
    SPREADING = "spreading"
    VERIFYING = "verifying"
    DECIDING = "deciding"


@dataclass
class AgentConfig:
    """智能体配置"""
    node_id: str
    node_type: NodeType
    learning_rate: float = 0.01
    memory_size: int = 1000
    exploration_rate: float = 0.1  # 探索率
    discount_factor: float = 0.9  # 折扣因子
    batch_size: int = 32


@dataclass
class Perception:
    """感知数据"""
    perception_type: str
    content: Any
    source: str
    timestamp: datetime
    relevance: float = 1.0
    confidence: float = 1.0


@dataclass
class LearningExperience:
    """学习经验"""
    state: str
    action: str
    reward: float
    next_state: str
    done: bool
    timestamp: datetime


@dataclass  
class BehaviorPolicy:
    """行为策略"""
    strategy_name: str
    actions: List[str]
    weights: Dict[str, float]
    updated_at: datetime


class NodeAgent:
    """节点智能体"""

    def __init__(
        self,
        config: AgentConfig,
        knowledge_manager: 'KnowledgeManager',
        reputation: 'ReputationSystem',
        economy: 'TokenEconomy'
    ):
        """
        初始化节点智能体
        
        Args:
            config: 智能体配置
            knowledge_manager: 知识管理器
            reputation: 信誉系统
            economy: 经济系统
        """
        self.config = config
        self.knowledge_manager = knowledge_manager
        self.reputation = reputation
        self.economy = economy
        
        # 状态
        self.state = AgentState.IDLE
        self.current_task: Optional[str] = None
        
        # 感知模块
        self.perception_buffer: deque = deque(maxlen=config.memory_size)
        self.knowledge_queue: deque = deque(maxlen=100)
        
        # 学习模块
        self.experience_buffer: deque = deque(maxlen=config.memory_size)
        self.learning_model: Dict[str, Any] = {}
        self.knowledge_preferences: Dict[str, float] = {}  # 领域 -> 偏好权重
        
        # 决策模块
        self.behavior_policies: Dict[str, BehaviorPolicy] = {}
        self.q_table: Dict[str, Dict[str, float]] = {}  # 状态-动作 Q表
        
        # 行动模块
        self.action_history: List[Dict[str, Any]] = []
        self.pending_actions: asyncio.Queue = asyncio.Queue()
        
        # 统计
        self.stats = {
            "total_perceptions": 0,
            "total_actions": 0,
            "successful_actions": 0,
            "learning_count": 0,
            "dialogue_count": 0,
            "spread_count": 0,
            "verify_count": 0
        }
        
        # 初始化策略
        self._initialize_policies()
        
        logger.info(f"节点智能体初始化: {config.node_id}")

    async def start(self):
        """启动智能体"""
        # 启动感知循环
        asyncio.create_task(self._perception_loop())
        # 启动决策循环
        asyncio.create_task(self._decision_loop())
        # 启动行动循环
        asyncio.create_task(self._action_loop())
        # 启动学习循环
        asyncio.create_task(self._learning_loop())
        
        logger.info("✅ 节点智能体启动")

    async def stop(self):
        """停止智能体"""
        self.state = AgentState.IDLE
        # 保存学习模型
        await self._save_learning_model()
        logger.info("节点智能体已停止")

    # ==================== 感知模块 ====================

    async def perceive(self, perception: Perception):
        """
        添加感知
        
        Args:
            perception: 感知数据
        """
        self.perception_buffer.append(perception)
        self.stats["total_perceptions"] += 1
        
        # 根据感知类型处理
        if perception.perception_type == "knowledge":
            self.knowledge_queue.append(perception.content)
        elif perception.perception_type == "dialogue":
            await self._process_dialogue_perception(perception)
        elif perception.perception_type == "environment":
            await self._process_environment_perception(perception)

    async def _process_knowledge_perception(self, knowledge: KnowledgeUnit):
        """处理知识感知"""
        # 评估知识价值
        value = self._evaluate_knowledge_value(knowledge)
        
        # 更新偏好
        for tag in knowledge.metadata.domain_tags:
            if tag not in self.knowledge_preferences:
                self.knowledge_preferences[tag] = 0.0
            self.knowledge_preferences[tag] += value * self.config.learning_rate

    async def _process_dialogue_perception(self, perception: Perception):
        """处理对话感知"""
        message: DialogueMessage = perception.content
        
        # 提取学习点
        if message.learning_highlights:
            for highlight in message.learning_highlights:
                await self._add_learning_insight(highlight)

    async def _process_environment_perception(self, perception: Perception):
        """处理环境感知"""
        env_data = perception.content
        
        # 更新网络状态
        # 更新资源状态
        # 更新其他节点状态

    async def _perception_loop(self):
        """感知循环"""
        while True:
            try:
                await asyncio.sleep(1)
                
                # 处理知识队列
                while self.knowledge_queue:
                    knowledge = self.knowledge_queue.popleft()
                    await self._process_knowledge_perception(knowledge)
                    
            except Exception as e:
                logger.error(f"感知循环错误: {e}")

    # ==================== 学习模块 ====================

    async def learn_knowledge(self, knowledge_id: str) -> bool:
        """
        学习知识
        
        Args:
            knowledge_id: 知识ID
            
        Returns:
            是否成功
        """
        try:
            knowledge = await self.knowledge_manager.get_knowledge(knowledge_id)
            if not knowledge:
                return False
            
            # 添加学习经验
            exp = LearningExperience(
                state="browsing",
                action="learn",
                reward=1.0,
                next_state="learned",
                done=True,
                timestamp=datetime.now()
            )
            self.experience_buffer.append(exp)
            
            # 更新学习计数
            self.stats["learning_count"] += 1
            
            # 更新学习模型
            await self._update_learning_model(knowledge)
            
            logger.info(f"📖 学习知识: {knowledge_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"学习知识失败: {e}")
            return False

    async def learn_from_dialogue(self, message: DialogueMessage):
        """从对话中学习"""
        if message.learning_highlights:
            for highlight in message.learning_highlights:
                await self._add_learning_insight(highlight)

    async def _add_learning_insight(self, insight: str):
        """添加学习洞察"""
        if insight not in self.learning_model:
            self.learning_model[insight] = {
                "count": 0,
                "last_seen": datetime.now(),
                "confidence": 0.0
            }
        
        self.learning_model[insight]["count"] += 1
        self.learning_model[insight]["last_seen"] = datetime.now()

    async def _update_learning_model(self, knowledge: KnowledgeUnit):
        """更新学习模型"""
        # 提取特征
        features = {
            "type": knowledge.metadata.knowledge_type,
            "tags": knowledge.metadata.domain_tags,
            "verification_rate": knowledge.verification_info.pass_rate,
            "value_score": knowledge.value_info.value_score
        }
        
        # 更新内部模型
        model_key = knowledge.knowledge_id
        self.learning_model[model_key] = features

    async def _learning_loop(self):
        """学习循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟一次
                
                # 从经验中学习
                if len(self.experience_buffer) >= self.config.batch_size:
                    await self._batch_learning()
                
                # 清理过期经验
                await self._cleanup_old_experiences()
                
            except Exception as e:
                logger.error(f"学习循环错误: {e}")

    async def _batch_learning(self):
        """批量学习"""
        batch = list(self.experience_buffer)[-self.config.batch_size:]
        
        for exp in batch:
            await self._update_q_value(exp)

    async def _update_q_value(self, exp: LearningExperience):
        """更新Q值"""
        state = exp.state
        action = exp.action
        
        if state not in self.q_table:
            self.q_table[state] = {}
        
        # Q学习更新
        current_q = self.q_table[state].get(action, 0.0)
        max_next_q = 0.0
        
        if not exp.done and exp.next_state in self.q_table:
            max_next_q = max(self.q_table[exp.next_state].values())
        
        new_q = current_q + self.config.learning_rate * (
            exp.reward + self.config.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state][action] = new_q

    async def _cleanup_old_experiences(self):
        """清理旧经验"""
        cutoff = datetime.now() - timedelta(days=7)
        
        while self.experience_buffer and self.experience_buffer[0].timestamp < cutoff:
            self.experience_buffer.popleft()

    # ==================== 决策模块 ====================

    async def decide_action(self, context: Dict[str, Any]) -> str:
        """
        决定行动
        
        Args:
            context: 决策上下文
            
        Returns:
            行动类型
        """
        state = context.get("state", "idle")
        
        # ε-greedy 策略
        if random.random() < self.config.exploration_rate:
            # 探索：随机选择
            action = random.choice(self._get_available_actions(state))
        else:
            # 利用：选择Q值最高的动作
            action = await self._get_best_action(state)
        
        return action

    async def decide_what_to_learn(
        self,
        available_knowledge: List[KnowledgeUnit]
    ) -> Optional[KnowledgeUnit]:
        """
        决定学习什么
        
        Args:
            available_knowledge: 可学习的知识列表
            
        Returns:
            选中的知识
        """
        if not available_knowledge:
            return None
        
        # 计算每个知识的得分
        scores = []
        for k in available_knowledge:
            score = self._calculate_learning_score(k)
            scores.append((score, k))
        
        # 选择得分最高的
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # 随机选择前20%
        top_n = max(1, len(scores) // 5)
        _, selected = random.choice(scores[:top_n])
        
        return selected

    async def decide_what_to_spread(
        self,
        learned_knowledge: List[KnowledgeUnit],
        target_interests: List[str]
    ) -> List[KnowledgeUnit]:
        """
        决定传播什么
        
        Args:
            learned_knowledge: 已学习的知识
            target_interests: 目标兴趣
            
        Returns:
            要传播的知识列表
        """
        results = []
        
        for k in learned_knowledge:
            # 计算匹配度
            match_score = 0.0
            for tag in k.metadata.domain_tags:
                if tag in target_interests:
                    match_score += 1
            
            # 考虑知识价值
            value_score = k.value_info.value_score
            
            # 综合得分
            total_score = match_score * 2 + value_score
            
            if total_score > 0:
                results.append((total_score, k))
        
        # 按得分排序，取前5个
        results.sort(key=lambda x: x[0], reverse=True)
        return [k for _, k in results[:5]]

    def _calculate_learning_score(self, knowledge: KnowledgeUnit) -> float:
        """计算学习得分"""
        score = 0.0
        
        # 验证率
        if knowledge.verification_info.verification_count > 0:
            score += knowledge.verification_info.pass_rate * 10
        
        # 价值分
        score += min(knowledge.value_info.value_score, 20)
        
        # 偏好匹配
        for tag in knowledge.metadata.domain_tags:
            pref = self.knowledge_preferences.get(tag, 0.0)
            score += pref * 0.5
        
        # 时效性（新知识优先）
        if knowledge.metadata.created_at:
            age_hours = (datetime.now() - knowledge.metadata.created_at).total_seconds() / 3600
            if age_hours < 24:
                score += 5
        
        return score

    async def _get_best_action(self, state: str) -> str:
        """获取最佳动作"""
        if state not in self.q_table or not self.q_table[state]:
            return random.choice(self._get_available_actions(state))
        
        q_values = self.q_table[state]
        best_action = max(q_values.items(), key=lambda x: x[1])
        return best_action[0]

    def _get_available_actions(self, state: str) -> List[str]:
        """获取可用动作"""
        return ["learn", "dialogue", "spread", "verify", "idle"]

    async def _decision_loop(self):
        """决策循环"""
        while True:
            try:
                await asyncio.sleep(5)
                
                if self.state == AgentState.IDLE:
                    # 决定下一步行动
                    context = {"state": "idle"}
                    action = await self.decide_action(context)
                    
                    if action == "learn":
                        await self._decide_and_execute_learning()
                    elif action == "spread":
                        await self._decide_and_execute_spread()
                    elif action == "verify":
                        await self._decide_and_execute_verify()
                        
            except Exception as e:
                logger.error(f"决策循环错误: {e}")

    # ==================== 行动模块 ====================

    async def execute_action(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> bool:
        """
        执行行动
        
        Args:
            action_type: 行动类型
            params: 行动参数
            
        Returns:
            是否成功
        """
        try:
            if action_type == "learn":
                return await self._execute_learn_action(params)
            elif action_type == "spread":
                return await self._execute_spread_action(params)
            elif action_type == "verify":
                return await self._execute_verify_action(params)
            elif action_type == "dialogue":
                return await self._execute_dialogue_action(params)
            
            return False
            
        except Exception as e:
            logger.error(f"执行行动失败: {e}")
            return False

    async def _execute_learn_action(self, params: Dict[str, Any]) -> bool:
        """执行学习行动"""
        knowledge_id = params.get("knowledge_id")
        if not knowledge_id:
            return False
        
        success = await self.learn_knowledge(knowledge_id)
        
        if success:
            self.stats["successful_actions"] += 1
            # 添加正向经验
            exp = LearningExperience(
                state="decided",
                action="learn",
                reward=1.0,
                next_state="learned",
                done=True,
                timestamp=datetime.now()
            )
            self.experience_buffer.append(exp)
        
        return success

    async def _execute_spread_action(self, params: Dict[str, Any]) -> bool:
        """执行传播行动"""
        knowledge_id = params.get("knowledge_id")
        target_nodes = params.get("target_nodes", [])
        
        # 记录传播
        self.stats["spread_count"] += 1
        
        # 添加经验
        exp = LearningExperience(
            state="spreading",
            action="spread",
            reward=0.5,
            next_state="spread",
            done=True,
            timestamp=datetime.now()
        )
        self.experience_buffer.append(exp)
        
        return True

    async def _execute_verify_action(self, params: Dict[str, Any]) -> bool:
        """执行验证行动"""
        knowledge_id = params.get("knowledge_id")
        is_valid = params.get("is_valid", True)
        
        self.stats["verify_count"] += 1
        
        return True

    async def _execute_dialogue_action(self, params: Dict[str, Any]) -> bool:
        """执行对话行动"""
        self.stats["dialogue_count"] += 1
        return True

    async def _action_loop(self):
        """行动循环"""
        while True:
            try:
                # 从待执行队列获取行动
                action = await asyncio.wait_for(
                    self.pending_actions.get(),
                    timeout=1.0
                )
                
                await self.execute_action(action["type"], action.get("params", {}))
                self.stats["total_actions"] += 1
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"行动循环错误: {e}")

    # ==================== 辅助方法 ====================

    def _evaluate_knowledge_value(self, knowledge: KnowledgeUnit) -> float:
        """评估知识价值"""
        base_value = 1.0
        
        # 验证加成
        if knowledge.is_verified:
            base_value *= 1.5
        
        # 引用加成
        base_value *= (1 + 0.1 * len(knowledge.content.references))
        
        return base_value

    def _initialize_policies(self):
        """初始化策略"""
        self.behavior_policies = {
            "learning": BehaviorPolicy(
                strategy_name="epsilon_greedy",
                actions=["learn", "skip"],
                weights={"learn": 0.8, "skip": 0.2},
                updated_at=datetime.now()
            ),
            "spreading": BehaviorPolicy(
                strategy_name="value_based",
                actions=["spread", "keep"],
                weights={"spread": 0.5, "keep": 0.5},
                updated_at=datetime.now()
            ),
            "verification": BehaviorPolicy(
                strategy_name="confidence_based",
                actions=["verify_yes", "verify_no", "skip"],
                weights={"verify_yes": 0.4, "verify_no": 0.3, "skip": 0.3},
                updated_at=datetime.now()
            )
        }

    async def _decide_and_execute_learning(self):
        """决定并执行学习"""
        # 获取可学习的知识
        # 这是简化实现，实际需要从网络获取
        pass

    async def _decide_and_execute_spread(self):
        """决定并执行传播"""
        pass

    async def _decide_and_execute_verify(self):
        """决定并执行验证"""
        pass

    async def _save_learning_model(self):
        """保存学习模型"""
        try:
            import os
            os.makedirs(f"./data/agents/{self.config.node_id}", exist_ok=True)
            
            model_data = {
                "q_table": self.q_table,
                "knowledge_preferences": self.knowledge_preferences,
                "learning_model": self.learning_model,
                "policies": {
                    name: {
                        "strategy_name": p.strategy_name,
                        "actions": p.actions,
                        "weights": p.weights
                    }
                    for name, p in self.behavior_policies.items()
                }
            }
            
            with open(f"./data/agents/{self.config.node_id}/model.json", "w") as f:
                json.dump(model_data, f)
                
        except Exception as e:
            logger.error(f"保存学习模型失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "experience_buffer_size": len(self.experience_buffer),
            "perception_buffer_size": len(self.perception_buffer),
            "q_table_states": len(self.q_table),
            "domain_preferences": dict(sorted(
                self.knowledge_preferences.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
        }
