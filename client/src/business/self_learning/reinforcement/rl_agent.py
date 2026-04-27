"""
PPO Agent 和训练器 (PPO Agent & Trainer)
========================================

简化版PPO实现，不依赖外部深度学习库。
使用查表法 (Tabular PPO) 或简单的神经网络。

注意: 这是一个演示版本。生产环境建议使用:
- PyTorch + stable-baselines3
- TensorFlow + tf-agents
"""

import random
import math
import logging
from typing import List, Tuple, Dict, Any, Optional
from collections import deque
import copy

logger = logging.getLogger(__name__)


class SimplePolicy:
    """
    简化策略网络 (查表法)
    
    适用于离散状态和离散动作的空间。
    对于连续状态空间，建议使用神经网络。
    """
    
    def __init__(self, state_dim: int, action_dim: int, learning_rate: float = 0.01):
        """
        初始化策略
        
        Args:
            state_dim: 状态空间维度 (用于离散化)
            action_dim: 动作空间维度
            learning_rate: 学习率
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        
        # 使用简单的查找表 (state_bucket -> action probabilities)
        # 为了简单，这里使用一个近似的线性策略
        self.weights = [[random.uniform(-0.1, 0.1) for _ in range(state_dim)] 
                        for _ in range(action_dim)]
        
        self.bias = [random.uniform(-0.1, 0.1) for _ in range(action_dim)]
        
        logger.info(f"[SimplePolicy] 初始化完成，状态维度: {state_dim}, 动作维度: {action_dim}")
    
    def forward(self, state: List[float]) -> List[float]:
        """
        前向传播，计算动作概率
        
        Args:
            state: 状态向量
            
        Returns:
            动作概率列表 (softmax)
        """
        # 线性变换
        logits = []
        for a in range(self.action_dim):
            score = self.bias[a]
            for s, w in zip(state, self.weights[a]):
                score += s * w
            logits.append(score)
        
        # Softmax
        max_logit = max(logits)
        exp_logits = [math.exp(l - max_logit) for l in logits]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]
        
        return probs
    
    def select_action(self, state: List[float]) -> Tuple[int, float]:
        """
        选择动作
        
        Returns:
            (action, log_probability)
        """
        probs = self.forward(state)
        
        # 按概率采样
        r = random.random()
        cumulative = 0.0
        action = 0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                action = i
                break
        
        log_prob = math.log(probs[action])
        return action, log_prob
    
    def update(self, states: List[List[float]], actions: List[int], 
                old_log_probs: List[float], advantages: List[float], 
                eps_clip: float = 0.2, epochs: int = 3):
        """
        PPO 策略更新 (简化版)
        
        Args:
            states: 状态列表
            actions: 动作列表
            old_log_probs: 旧策略的log概率
            advantages: 优势函数
            eps_clip: PPO裁剪参数
            epochs: 更新轮数
        """
        for _ in range(epochs):
            total_loss = 0.0
            
            for s, a, old_lp, adv in zip(states, actions, old_log_probs, advantages):
                # 计算当前策略的概率
                probs = self.forward(s)
                new_lp = math.log(probs[a])
                
                # 概率比
                ratio = math.exp(new_lp - old_lp)
                
                # PPO裁剪目标
                surr1 = ratio * adv
                surr2 = max(min(ratio, 1 + eps_clip), 1 - eps_clip) * adv
                loss = -min(surr1, surr2)
                
                total_loss += loss
                
                # 梯度更新 (简化版，直接更新weights)
                # 实际应该使用反向传播
                for i in range(self.action_dim):
                    for j in range(self.state_dim):
                        if i == a:
                            # 增加选中动作的概率
                            self.weights[i][j] += self.lr * adv * s[j] * (1 - probs[i])
                        else:
                            # 减少其他动作的概率
                            self.weights[i][j] -= self.lr * adv * s[j] * probs[i]
            
            avg_loss = total_loss / len(states)
            logger.debug(f"[SimplePolicy] 更新完成，平均损失: {avg_loss:.4f}")


class SimpleValueNetwork:
    """
    简化价值网络
    
    估计状态价值 V(s)
    """
    
    def __init__(self, state_dim: int, learning_rate: float = 0.01):
        """
        初始化价值网络
        
        Args:
            state_dim: 状态空间维度
            learning_rate: 学习率
        """
        self.state_dim = state_dim
        self.lr = learning_rate
        
        # 线性价值函数: V(s) = w^T * s + b
        self.weights = [random.uniform(-0.1, 0.1) for _ in range(state_dim)]
        self.bias = random.uniform(-0.1, 0.1)
        
        logger.info(f"[SimpleValueNetwork] 初始化完成，状态维度: {state_dim}")
    
    def forward(self, state: List[float]) -> float:
        """
        前向传播，计算状态价值
        
        Returns:
            状态价值 (scalar)
        """
        value = self.bias
        for s, w in zip(state, self.weights):
            value += s * w
        return value
    
    def update(self, states: List[List[float]], returns: List[float], epochs: int = 3):
        """
        更新价值网络 (均方误差)
        
        Args:
            states: 状态列表
            returns: 回报列表
            epochs: 更新轮数
        """
        for _ in range(epochs):
            total_loss = 0.0
            
            for s, ret in zip(states, returns):
                pred = self.forward(s)
                error = pred - ret
                loss = error ** 2
                total_loss += loss
                
                # 梯度更新
                self.bias -= self.lr * 2 * error
                for i in range(self.state_dim):
                    self.weights[i] -= self.lr * 2 * error * s[i]
            
            avg_loss = total_loss / len(states)
            logger.debug(f"[SimpleValueNetwork] 更新完成，平均损失: {avg_loss:.4f}")


class PPOAgent:
    """
    PPO 智能体 (简化版)
    
    协调策略网络和价值网络，实现PPO算法。
    """
    
    def __init__(self, state_dim: int, action_dim: int, 
                 learning_rate: float = 0.01, gamma: float = 0.99, 
                 eps_clip: float = 0.2):
        """
        初始化PPO智能体
        
        Args:
            state_dim: 状态空间维度
            action_dim: 动作空间维度
            learning_rate: 学习率
            gamma: 折扣因子
            eps_clip: PPO裁剪参数
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = learning_rate
        self.gamma = gamma
        self.eps_clip = eps_clip
        
        # 策略网络
        self.policy = SimplePolicy(state_dim, action_dim, learning_rate)
        
        # 价值网络
        self.value_net = SimpleValueNetwork(state_dim, learning_rate)
        
        # 经验回放缓存
        self.memory = []
        
        # 训练统计
        self.train_stats = {
            'episodes': 0,
            'total_reward': 0.0,
            'avg_reward': 0.0,
            'policy_loss': 0.0,
            'value_loss': 0.0,
        }
        
        logger.info(f"[PPOAgent] 初始化完成，状态维度: {state_dim}, 动作维度: {action_dim}")
    
    def select_action(self, state: List[float]) -> Tuple[int, float]:
        """
        选择动作
        
        Returns:
            (action, log_probability)
        """
        return self.policy.select_action(state)
    
    def store_transition(self, state: List[float], action: int, 
                        log_prob: float, reward: float, done: bool):
        """
        存储转移
        """
        self.memory.append({
            'state': state,
            'action': action,
            'log_prob': log_prob,
            'reward': reward,
            'done': done,
        })
    
    def train(self):
        """
        训练 (PPO算法)
        """
        if len(self.memory) == 0:
            logger.warning("[PPOAgent] 没有存储的转移，跳过训练")
            return
        
        # 计算回报和优势
        states = []
        actions = []
        old_log_probs = []
        returns = []
        advantages = []
        
        # 计算回报 (returns)
        ret = 0.0
        for i in reversed(range(len(self.memory))):
            if self.memory[i]['done']:
                ret = 0.0
            
            ret = self.memory[i]['reward'] + self.gamma * ret
            returns.insert(0, ret)
            
            states.insert(0, self.memory[i]['state'])
            actions.insert(0, self.memory[i]['action'])
            old_log_probs.insert(0, self.memory[i]['log_prob'])
        
        # 计算优势函数 (advantages = returns - V(s))
        advantages = []
        for s, ret in zip(states, returns):
            value = self.value_net.forward(s)
            adv = ret - value
            advantages.append(adv)
        
        # 归一化优势
        mean_adv = sum(advantages) / len(advantages)
        std_adv = math.sqrt(sum((a - mean_adv) ** 2 for a in advantages) / len(advantages))
        if std_adv > 0:
            advantages = [(a - mean_adv) / (std_adv + 1e-8) for a in advantages]
        
        # 更新策略
        self.policy.update(states, actions, old_log_probs, advantages, self.eps_clip)
        
        # 更新价值网络
        self.value_net.update(states, returns)
        
        # 清空缓存
        self.memory.clear()
        
        # 更新统计
        self.train_stats['episodes'] += 1
        self.train_stats['policy_loss'] = abs(sum(advantages) / len(advantages))
        self.train_stats['value_loss'] = sum((r - self.value_net.forward(s)) ** 2 
                                             for s, r in zip(states, returns)) / len(states)
        
        logger.debug(f"[PPOAgent] 训练完成，回合: {self.train_stats['episodes']}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取训练统计"""
        return copy.deepcopy(self.train_stats)


class TrainingConfig:
    """训练配置"""
    
    def __init__(self, 
                 total_timesteps: int = 100000,
                 max_episode_length: int = 1000,
                 update_epochs: int = 10,
                 batch_size: int = 64,
                 learning_rate: float = 3e-4,
                 gamma: float = 0.99,
                 eps_clip: float = 0.2,
                 value_coef: float = 0.5,
                 entropy_coef: float = 0.01):
        """
        初始化训练配置
        
        Args:
            total_timesteps: 总训练步数
            max_episode_length: 最大回合长度
            update_epochs: 每次更新的轮数
            batch_size: 批次大小
            learning_rate: 学习率
            gamma: 折扣因子
            eps_clip: PPO裁剪参数
            value_coef: 价值损失系数
            entropy_coef: 熵系数
        """
        self.total_timesteps = total_timesteps
        self.max_episode_length = max_episode_length
        self.update_epochs = update_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.eps_clip = eps_clip
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        
        logger.info(f"[TrainingConfig] 初始化完成，总步数: {total_timesteps}")


class RLTrainer:
    """
    强化学习训练器
    
    协调环境、智能体，实现训练循环。
    """
    
    def __init__(self, env, agent, config: Optional[TrainingConfig] = None):
        """
        初始化训练器
        
        Args:
            env: 环境
            agent: 智能体
            config: 训练配置
        """
        self.env = env
        self.agent = agent
        self.config = config or TrainingConfig()
        
        # 训练统计
        self.training_info = {
            'timesteps': 0,
            'episodes': 0,
            'episode_rewards': [],
            'avg_reward': 0.0,
            'best_reward': -float('inf'),
            'recent_rewards': deque(maxlen=10),
        }
        
        logger.info(f"[RLTrainer] 初始化完成")
    
    def train_loop(self, total_timesteps: Optional[int] = None):
        """
        训练循环
        
        Args:
            total_timesteps: 总训练步数 (覆盖配置)
        """
        if total_timesteps:
            self.config.total_timesteps = total_timesteps
        
        logger.info(f"[RLTrainer] 开始训练，总步数: {self.config.total_timesteps}")
        
        state = self.env.reset()
        episode_reward = 0.0
        episode_steps = 0
        
        for timestep in range(1, self.config.total_timesteps + 1):
            # 选择动作
            action, log_prob = self.agent.select_action(state)
            
            # 执行动作
            next_state, reward, done, info = self.env.step(action)
            
            # 存储转移
            self.agent.store_transition(state, action, log_prob, reward, done)
            
            # 更新统计
            episode_reward += reward
            episode_steps += 1
            self.training_info['timesteps'] = timestep
            
            # 检查是否结束
            if done or episode_steps >= self.config.max_episode_length:
                # 训练
                self.agent.train()
                
                # 更新统计
                self.training_info['episodes'] += 1
                self.training_info['episode_rewards'].append(episode_reward)
                self.training_info['recent_rewards'].append(episode_reward)
                self.training_info['avg_reward'] = sum(self.training_info['recent_rewards']) / len(self.training_info['recent_rewards'])
                
                if episode_reward > self.training_info['best_reward']:
                    self.training_info['best_reward'] = episode_reward
                
                # 日志
                if self.training_info['episodes'] % 10 == 0:
                    logger.info(
                        f"[RLTrainer] 回合: {self.training_info['episodes']}, "
                        f"平均奖励: {self.training_info['avg_reward']:.2f}, "
                        f"最佳奖励: {self.training_info['best_reward']:.2f}"
                    )
                    print(
                        f"Episode {self.training_info['episodes']}, "
                        f"Avg Reward: {self.training_info['avg_reward']:.2f}"
                    )
                
                # 重置环境
                state = self.env.reset()
                episode_reward = 0.0
                episode_steps = 0
            else:
                state = next_state
        
        logger.info(f"[RLTrainer] 训练完成")
        print("Training completed!")
    
    def evaluate(self, n_episodes: int = 10, render: bool = False) -> Dict[str, float]:
        """
        评估训练好的智能体
        
        Returns:
            评估统计
        """
        logger.info(f"[RLTrainer] 开始评估，回合: {n_episodes}")
        
        episode_rewards = []
        
        for ep in range(n_episodes):
            state = self.env.reset()
            done = False
            episode_reward = 0.0
            steps = 0
            
            while not done and steps < self.config.max_episode_length:
                # 选择动作 (评估时不采样，选择最优动作)
                probs = self.agent.policy.forward(state)
                action = probs.index(max(probs))
                
                # 执行动作
                state, reward, done, info = self.env.step(action)
                episode_reward += reward
                steps += 1
                
                if render:
                    self.env.render(mode='print')
            
            episode_rewards.append(episode_reward)
            logger.debug(f"[RLTrainer] 评估回合 {ep+1}: 奖励 = {episode_reward:.2f}")
        
        # 计算统计
        avg_reward = sum(episode_rewards) / len(episode_rewards)
        min_reward = min(episode_rewards)
        max_reward = max(episode_rewards)
        
        stats = {
            'avg_reward': avg_reward,
            'min_reward': min_reward,
            'max_reward': max_reward,
            'episodes': n_episodes,
        }
        
        logger.info(f"[RLTrainer] 评估完成，平均奖励: {avg_reward:.2f}")
        return stats


if __name__ == "__main__":
    # 简单测试
    from .rl_environment import CodeEvolutionEnv
    
    # 创建环境和智能体
    env = CodeEvolutionEnv()
    agent = PPOAgent(state_dim=6, action_dim=5)
    config = TrainingConfig(total_timesteps=1000)
    trainer = RLTrainer(env, agent, config)
    
    # 训练
    trainer.train_loop()
    
    # 评估
    stats = trainer.evaluate(n_episodes=5)
    print(f"评估结果: {stats}")
