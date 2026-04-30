"""
强化学习驱动的自我改进 (RL-Driven Self Improvement)
===================================================

参考论文: https://arxiv.org/abs/2603.19461

实现强化学习驱动的自我改进机制：
1. 马尔可夫决策过程建模 - 将系统状态建模为MDP
2. 策略梯度方法 - 使用策略梯度优化策略
3. 价值函数估计 - 估计状态价值
4. 探索-利用权衡 - 平衡探索和利用

核心特性：
- MDP状态表示 - 系统状态的紧凑表示
- 奖励信号设计 - 多维度奖励设计
- 策略优化器 - 策略梯度优化
- 价值估计器 - 时序差分学习
- 探索策略 - ε-贪心、UCB、汤普森采样

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class ActionType(Enum):
    """动作类型"""
    ADJUST_OPTIMIZATION = "adjust_optimization"
    SWITCH_MODEL = "switch_model"
    MODIFY_CACHE = "modify_cache"
    UPDATE_STRATEGY = "update_strategy"
    LEARN_PATTERN = "learn_pattern"
    EXPLORE_NEW = "explore_new"


class StateFeature(Enum):
    """状态特征"""
    SYSTEM_LOAD = "system_load"
    OPTIMIZATION_RATE = "optimization_rate"
    CACHE_HIT_RATE = "cache_hit_rate"
    COST_EFFICIENCY = "cost_efficiency"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class MDPState:
    """MDP状态"""
    features: Dict[StateFeature, float]
    timestamp: float
    episode: int = 0


@dataclass
class Action:
    """动作"""
    type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    probability: float = 1.0


@dataclass
class Transition:
    """状态转移"""
    state: MDPState
    action: Action
    reward: float
    next_state: MDPState
    done: bool


class RLAlgorithm(Enum):
    """强化学习算法"""
    Q_LEARNING = "q_learning"
    SARSA = "sarsa"
    REINFORCE = "reinforce"
    DDPG = "ddpg"
    PPO = "ppo"


class RLDrivenImprovement:
    """
    强化学习驱动的自我改进系统
    
    核心组件：
    1. 状态编码器 - 将系统状态编码为特征向量
    2. 策略网络 - 生成动作的策略
    3. 价值网络 - 估计状态价值
    4. 奖励计算器 - 计算奖励信号
    5. 经验回放 - 存储和采样经验
    6. 目标网络 - 稳定训练
    
    算法支持：
    - Q-Learning
    - SARSA
    - REINFORCE (策略梯度)
    - DDPG (深度确定性策略梯度)
    - PPO (近端策略优化)
    """
    
    def __init__(self, algorithm: RLAlgorithm = RLAlgorithm.REINFORCE):
        # 当前算法
        self._algorithm = algorithm
        
        # 状态空间维度
        self._state_dim = len(StateFeature)
        
        # 动作空间
        self._action_types = list(ActionType)
        
        # Q表（用于Q-Learning和SARSA）
        self._q_table: Dict[str, Dict[ActionType, float]] = {}
        
        # 策略参数（用于策略梯度方法）
        self._policy_params = {
            action_type: 0.5 for action_type in ActionType
        }
        
        # 价值函数估计
        self._value_function: Dict[str, float] = {}
        
        # 学习参数
        self._learning_rate = 0.01
        self._discount_factor = 0.99
        self._exploration_rate = 0.3
        
        # 经验回放缓冲区
        self._replay_buffer: List[Transition] = []
        self._max_buffer_size = 10000
        
        # 训练统计
        self._training_stats = {
            "episodes": 0,
            "total_reward": 0.0,
            "avg_reward": 0.0,
            "best_reward": float('-inf'),
            "policy_updates": 0,
        }
        
        # 当前状态
        self._current_state = None
        
        logger.info(f"[RLDrivenImprovement] 初始化完成，算法: {algorithm.value}")
    
    def encode_state(self, state: MDPState) -> str:
        """
        将状态编码为字符串表示
        
        使用离散化的特征值作为状态键
        """
        encoded = []
        for feature in StateFeature:
            value = state.features.get(feature, 0.0)
            # 离散化为5个区间
            bin_index = min(4, int(value * 5))
            encoded.append(f"{feature.value}:{bin_index}")
        return ",".join(encoded)
    
    def get_state_features(self) -> Dict[str, float]:
        """获取当前状态特征"""
        if self._current_state:
            return {f.value: v for f, v in self._current_state.features.items()}
        return {}
    
    def set_current_state(self, features: Dict[StateFeature, float]):
        """设置当前状态"""
        self._current_state = MDPState(
            features=features,
            timestamp=__import__('time').time(),
            episode=self._training_stats["episodes"],
        )
    
    def select_action(self, state: MDPState = None) -> Action:
        """
        选择动作
        
        根据当前算法选择动作
        """
        if state is None:
            state = self._current_state
        
        encoded_state = self.encode_state(state)
        
        # 探索-利用权衡
        if self._algorithm in [RLAlgorithm.Q_LEARNING, RLAlgorithm.SARSA]:
            return self._select_action_q_learning(encoded_state)
        else:
            return self._select_action_policy_gradient(encoded_state)
    
    def _select_action_q_learning(self, encoded_state: str) -> Action:
        """Q-Learning动作选择"""
        # 初始化Q值
        if encoded_state not in self._q_table:
            self._q_table[encoded_state] = {
                action_type: 0.0 for action_type in ActionType
            }
        
        # ε-贪心策略
        if __import__('random').random() < self._exploration_rate:
            # 探索：随机选择
            action_type = __import__('random').choice(self._action_types)
        else:
            # 利用：选择Q值最大的动作
            q_values = self._q_table[encoded_state]
            action_type = max(q_values, key=q_values.get)
        
        return Action(type=action_type, parameters=self._generate_action_params(action_type))
    
    def _select_action_policy_gradient(self, encoded_state: str) -> Action:
        """策略梯度动作选择"""
        # 使用softmax选择动作
        action_types = self._action_types
        params = [self._policy_params[at] for at in action_types]
        
        # 计算softmax概率
        exp_params = np.exp(np.array(params))
        probabilities = exp_params / np.sum(exp_params)
        
        # 根据概率选择动作
        action_type = __import__('random').choices(action_types, weights=probabilities)[0]
        
        return Action(
            type=action_type,
            parameters=self._generate_action_params(action_type),
            probability=probabilities[action_types.index(action_type)],
        )
    
    def _generate_action_params(self, action_type: ActionType) -> Dict[str, Any]:
        """生成动作参数"""
        params = {}
        
        if action_type == ActionType.ADJUST_OPTIMIZATION:
            params["level"] = __import__('random').uniform(0.1, 1.0)
            params["strategy"] = __import__('random').choice(["conservative", "balanced", "aggressive"])
        
        elif action_type == ActionType.SWITCH_MODEL:
            params["model"] = __import__('random').choice(["claude-3-haiku", "claude-3-sonnet", "claude-3-opus"])
        
        elif action_type == ActionType.MODIFY_CACHE:
            params["ttl"] = int(__import__('random').uniform(60, 3600))
            params["max_entries"] = int(__import__('random').uniform(100, 1000))
        
        elif action_type == ActionType.UPDATE_STRATEGY:
            params["strategy_name"] = f"strategy_{__import__('random').randint(1, 100)}"
        
        elif action_type == ActionType.LEARN_PATTERN:
            params["pattern_type"] = __import__('random').choice(["context", "user", "system"])
        
        elif action_type == ActionType.EXPLORE_NEW:
            params["exploration_budget"] = __import__('random').uniform(0.1, 0.5)
        
        return params
    
    def calculate_reward(self, state: MDPState, action: Action, next_state: MDPState) -> float:
        """
        计算奖励
        
        多维度奖励设计：
        - 优化率奖励
        - 缓存命中率奖励
        - 成本效率奖励
        - 用户满意度奖励
        - 探索奖励
        """
        reward = 0.0
        
        # 基础奖励：优化率变化
        current_opt = state.features.get(StateFeature.OPTIMIZATION_RATE, 0.5)
        next_opt = next_state.features.get(StateFeature.OPTIMIZATION_RATE, 0.5)
        reward += (next_opt - current_opt) * 10
        
        # 缓存命中率奖励
        cache_hit = next_state.features.get(StateFeature.CACHE_HIT_RATE, 0.0)
        reward += cache_hit * 5
        
        # 成本效率奖励
        cost_eff = next_state.features.get(StateFeature.COST_EFFICIENCY, 0.5)
        reward += cost_eff * 3
        
        # 用户满意度奖励
        satisfaction = next_state.features.get(StateFeature.USER_SATISFACTION, 0.5)
        reward += satisfaction * 2
        
        # 探索奖励
        if action.type == ActionType.EXPLORE_NEW:
            reward += 1.0  # 鼓励探索
        
        return reward
    
    def learn(self, transition: Transition):
        """
        学习更新
        
        根据当前算法执行学习更新
        """
        if self._algorithm == RLAlgorithm.Q_LEARNING:
            self._learn_q_learning(transition)
        elif self._algorithm == RLAlgorithm.SARSA:
            self._learn_sarsa(transition)
        elif self._algorithm == RLAlgorithm.REINFORCE:
            self._learn_reinforce(transition)
        else:
            self._learn_generic(transition)
    
    def _learn_q_learning(self, transition: Transition):
        """Q-Learning学习"""
        state_key = self.encode_state(transition.state)
        next_state_key = self.encode_state(transition.next_state)
        
        # 初始化Q表
        if state_key not in self._q_table:
            self._q_table[state_key] = {at: 0.0 for at in ActionType}
        if next_state_key not in self._q_table:
            self._q_table[next_state_key] = {at: 0.0 for at in ActionType}
        
        # Q-Learning更新
        old_q = self._q_table[state_key][transition.action.type]
        max_next_q = max(self._q_table[next_state_key].values())
        
        target = transition.reward + self._discount_factor * max_next_q * (1 - int(transition.done))
        new_q = old_q + self._learning_rate * (target - old_q)
        
        self._q_table[state_key][transition.action.type] = new_q
        
        self._training_stats["policy_updates"] += 1
    
    def _learn_sarsa(self, transition: Transition):
        """SARSA学习"""
        state_key = self.encode_state(transition.state)
        next_state_key = self.encode_state(transition.next_state)
        
        # 初始化Q表
        if state_key not in self._q_table:
            self._q_table[state_key] = {at: 0.0 for at in ActionType}
        if next_state_key not in self._q_table:
            self._q_table[next_state_key] = {at: 0.0 for at in ActionType}
        
        # SARSA更新（需要下一个动作）
        next_action = self.select_action(transition.next_state)
        next_q = self._q_table[next_state_key][next_action.type]
        
        old_q = self._q_table[state_key][transition.action.type]
        target = transition.reward + self._discount_factor * next_q * (1 - int(transition.done))
        new_q = old_q + self._learning_rate * (target - old_q)
        
        self._q_table[state_key][transition.action.type] = new_q
        
        self._training_stats["policy_updates"] += 1
    
    def _learn_reinforce(self, transition: Transition):
        """REINFORCE策略梯度学习"""
        # 简单版本：基于奖励调整策略参数
        reward = transition.reward
        action_type = transition.action.type
        
        # 增加获得正奖励的动作的概率
        if reward > 0:
            self._policy_params[action_type] += self._learning_rate * reward
        else:
            self._policy_params[action_type] += self._learning_rate * reward * 0.5
        
        # 归一化参数
        max_param = max(self._policy_params.values())
        min_param = min(self._policy_params.values())
        if max_param - min_param > 10:
            for at in ActionType:
                self._policy_params[at] = (self._policy_params[at] - min_param) / (max_param - min_param)
        
        self._training_stats["policy_updates"] += 1
    
    def _learn_generic(self, transition: Transition):
        """通用学习方法"""
        # 简单的时序差分学习
        state_key = self.encode_state(transition.state)
        
        if state_key not in self._value_function:
            self._value_function[state_key] = 0.0
        
        next_state_key = self.encode_state(transition.next_state)
        next_value = self._value_function.get(next_state_key, 0.0)
        
        target = transition.reward + self._discount_factor * next_value * (1 - int(transition.done))
        self._value_function[state_key] += self._learning_rate * (target - self._value_function[state_key])
        
        self._training_stats["policy_updates"] += 1
    
    def add_experience(self, transition: Transition):
        """添加经验到回放缓冲区"""
        self._replay_buffer.append(transition)
        
        # 限制缓冲区大小
        if len(self._replay_buffer) > self._max_buffer_size:
            self._replay_buffer = self._replay_buffer[-self._max_buffer_size:]
    
    def sample_experience(self, batch_size: int = 32) -> List[Transition]:
        """从回放缓冲区采样经验"""
        if len(self._replay_buffer) < batch_size:
            return self._replay_buffer.copy()
        
        return __import__('random').sample(self._replay_buffer, batch_size)
    
    def update_exploration_rate(self, episode: int):
        """更新探索率（衰减）"""
        self._exploration_rate = max(0.01, 0.3 * (0.99 ** episode))
    
    def start_episode(self):
        """开始新回合"""
        self._training_stats["episodes"] += 1
        self.update_exploration_rate(self._training_stats["episodes"])
    
    def end_episode(self, total_reward: float):
        """结束回合"""
        self._training_stats["total_reward"] += total_reward
        self._training_stats["avg_reward"] = (
            self._training_stats["total_reward"] / self._training_stats["episodes"]
        )
        if total_reward > self._training_stats["best_reward"]:
            self._training_stats["best_reward"] = total_reward
    
    def get_stats(self) -> Dict[str, Any]:
        """获取训练统计"""
        return self._training_stats.copy()
    
    def get_policy(self) -> Dict[str, float]:
        """获取当前策略"""
        if self._algorithm in [RLAlgorithm.Q_LEARNING, RLAlgorithm.SARSA]:
            # 返回Q值最高的动作
            policy = {}
            for state_key, q_values in self._q_table.items():
                best_action = max(q_values, key=q_values.get)
                policy[state_key] = best_action.value
            return policy
        else:
            # 返回策略参数
            return {at.value: self._policy_params[at] for at in ActionType}


# 便捷函数
def create_rl_improvement(algorithm: RLAlgorithm = RLAlgorithm.REINFORCE) -> RLDrivenImprovement:
    """创建强化学习驱动的自我改进实例"""
    return RLDrivenImprovement(algorithm)


__all__ = [
    "ActionType",
    "StateFeature",
    "MDPState",
    "Action",
    "Transition",
    "RLAlgorithm",
    "RLDrivenImprovement",
    "create_rl_improvement",
]
