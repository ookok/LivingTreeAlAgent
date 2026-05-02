"""
强化学习训练器
实现 PPO 算法的训练循环
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from collections import deque
import random

from .rl_environment import CodeEvolutionEnv, CodeObservation, CodeAction
from .rl_agent import PPOAgent

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """训练配置"""
    total_timesteps: int = 1_000_000  # 总训练步数
    n_steps: int = 2048  # 每次收集的样本数
    n_epochs: int = 10  # 每次更新的 epoch 数
    batch_size: int = 64  # 批次大小
    learning_rate: float = 3e-4  # 学习率
    gamma: float = 0.99  # 折扣因子
    gae_lambda: float = 0.95  # GAE 参数
    clip_range: float = 0.2  # PPO clip 范围
    ent_coef: float = 0.01  # 熵系数
    vf_coef: float = 0.5  # 价值函数系数
    max_grad_norm: float = 0.5  # 梯度裁剪
    save_freq: int = 10_000  # 保存频率
    eval_freq: int = 5_000  # 评估频率
    n_eval_episodes: int = 10  # 评估 episode 数


@dataclass
class RolloutBuffer:
    """Rollout 缓冲区"""
    observations: List[np.ndarray]
    actions: List[int]
    log_probs: List[float]
    rewards: List[float]
    dones: List[bool]
    values: List[float]
    advantages: Optional[np.ndarray] = None
    returns: Optional[np.ndarray] = None

    def __init__(self):
        self.clear()

    def clear(self):
        """清空缓冲区"""
        self.observations = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.dones = []
        self.values = []
        self.advantages = None
        self.returns = None

    def add(self, obs: np.ndarray, action: int, log_prob: float,
            reward: float, done: bool, value: float):
        """添加样本"""
        self.observations.append(obs)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)

    def compute_returns_and_advantages(self, last_value: float, gamma: float, gae_lambda: float):
        """计算 returns 和 advantages（GAE）"""
        n_steps = len(self.rewards)
        advantages = np.zeros(n_steps, dtype=np.float32)
        last_advantage = 0

        # 反向计算 GAE
        for t in reversed(range(n_steps)):
            if t == n_steps - 1:
                next_value = last_value
                next_non_terminal = 1.0 - self.dones[t]
            else:
                next_value = self.values[t + 1]
                next_non_terminal = 1.0 - self.dones[t]

            delta = self.rewards[t] + gamma * next_value * next_non_terminal - self.values[t]
            advantages[t] = delta + gamma * gae_lambda * next_non_terminal * last_advantage
            last_advantage = advantages[t]

        # 计算 returns
        returns = advantages + np.array(self.values, dtype=np.float32)

        # 归一化 advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        self.advantages = advantages
        self.returns = returns

    def get_batches(self, batch_size: int):
        """获取训练批次"""
        n_samples = len(self.observations)
        indices = np.arange(n_samples)
        np.random.shuffle(indices)

        for start in range(0, n_samples, batch_size):
            end = min(start + batch_size, n_samples)
            batch_indices = indices[start:end]

            yield (
                np.array([self.observations[i] for i in batch_indices]),
                np.array([self.actions[i] for i in batch_indices]),
                np.array([self.log_probs[i] for i in batch_indices]),
                self.advantages[batch_indices],
                self.returns[batch_indices],
            )


class RLTrainer:
    """强化学习训练器"""

    def __init__(self, env: CodeEvolutionEnv, agent: PPOAgent, config: TrainingConfig):
        self.env = env
        self.agent = agent
        self.config = config

        self.rollout_buffer = RolloutBuffer()
        self.training_info = {
            'timesteps': 0,
            'episodes': 0,
            'updates': 0,
            'best_reward': -np.inf,
            'reward_history': [],
            'loss_history': [],
        }

        logger.info(f"RL Trainer 初始化完成，总训练步数: {config.total_timesteps}")

    def collect_rollouts(self) -> Dict[str, float]:
        """收集 rollout 数据"""
        self.rollout_buffer.clear()
        episode_rewards = []

        obs = self.env.reset()
        episode_reward = 0
        episode_length = 0

        for step in range(self.config.n_steps):
            # 获取动作
            action_info = self.agent.get_action(obs)
            action = action_info['action']
            log_prob = action_info['log_prob']
            value = action_info['value']

            # 执行动作
            next_obs, reward, done, info = self.env.step(action)

            # 存储样本
            self.rollout_buffer.add(
                obs.to_vector(),
                action.value,
                log_prob,
                reward,
                done,
                value
            )

            episode_reward += reward
            episode_length += 1

            if done:
                episode_rewards.append(episode_reward)
                self.training_info['episodes'] += 1
                obs = self.env.reset()
                episode_reward = 0
                episode_length = 0
            else:
                obs = next_obs

        # 计算最后状态的价值
        if not done:
            last_value = self.agent.get_value(obs)
        else:
            last_value = 0.0

        # 计算 advantages 和 returns
        self.rollout_buffer.compute_returns_and_advantages(
            last_value,
            self.config.gamma,
            self.config.gae_lambda
        )

        # 更新统计
        self.training_info['timesteps'] += self.config.n_steps

        return {
            'mean_reward': np.mean(episode_rewards) if episode_rewards else 0.0,
            'std_reward': np.std(episode_rewards) if episode_rewards else 0.0,
            'n_episodes': len(episode_rewards),
        }

    def train(self) -> Dict[str, float]:
        """训练一个 epoch"""
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy_loss = 0
        n_batches = 0

        # 多次更新
        for epoch in range(self.config.n_epochs):
            for batch in self.rollout_buffer.get_batches(self.config.batch_size):
                obs_batch, actions_batch, old_log_probs_batch, advantages_batch, returns_batch = batch

                # 前向传播
                action_outputs = self.agent.policy_net(torch.FloatTensor(obs_batch))
                values = self.agent.value_net(torch.FloatTensor(obs_batch)).squeeze()

                # 计算新的 log probabilities
                dist = torch.distributions.Categorical(logits=action_outputs)
                new_log_probs = dist.log_prob(torch.LongTensor(actions_batch))
                entropy = dist.entropy().mean()

                # 计算 ratio
                ratio = torch.exp(new_log_probs - torch.FloatTensor(old_log_probs_batch))

                # PPO clip
                surr1 = ratio * torch.FloatTensor(advantages_batch)
                surr2 = torch.clamp(ratio, 1.0 - self.config.clip_range, 1.0 + self.config.clip_range) * torch.FloatTensor(advantages_batch)
                policy_loss = -torch.min(surr1, surr2).mean()

                # 价值函数损失
                value_loss = nn.MSELoss()(values, torch.FloatTensor(returns_batch))

                # 总损失
                loss = policy_loss - self.config.ent_coef * entropy + self.config.vf_coef * value_loss

                # 反向传播
                self.agent.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.policy_net.parameters(), self.config.max_grad_norm)
                torch.nn.utils.clip_grad_norm_(self.agent.value_net.parameters(), self.config.max_grad_norm)
                self.agent.optimizer.step()

                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy_loss += entropy.item()
                n_batches += 1

        self.training_info['updates'] += 1

        return {
            'loss': total_loss / n_batches,
            'policy_loss': total_policy_loss / n_batches,
            'value_loss': total_value_loss / n_batches,
            'entropy': total_entropy_loss / n_batches,
        }

    def evaluate(self, n_episodes: int = 10) -> Dict[str, float]:
        """评估当前策略"""
        episode_rewards = []

        for episode in range(n_episodes):
            obs = self.env.reset()
            episode_reward = 0
            done = False

            while not done:
                action_info = self.agent.get_action(obs, deterministic=True)
                action = action_info['action']
                obs, reward, done, info = self.env.step(action)
                episode_reward += reward

            episode_rewards.append(episode_reward)

        return {
            'mean_reward': np.mean(episode_rewards),
            'std_reward': np.std(episode_rewards),
            'min_reward': np.min(episode_rewards),
            'max_reward': np.max(episode_rewards),
        }

    def save_checkpoint(self, path: str):
        """保存检查点"""
        checkpoint = {
            'agent_state_dict': self.agent.policy_net.state_dict(),
            'value_state_dict': self.agent.value_net.state_dict(),
            'optimizer_state_dict': self.agent.optimizer.state_dict(),
            'training_info': self.training_info,
        }
        torch.save(checkpoint, path)
        logger.info(f"检查点已保存: {path}")

    def load_checkpoint(self, path: str):
        """加载检查点"""
        checkpoint = torch.load(path)
        self.agent.policy_net.load_state_dict(checkpoint['agent_state_dict'])
        self.agent.value_net.load_state_dict(checkpoint['value_state_dict'])
        self.agent.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.training_info = checkpoint['training_info']
        logger.info(f"检查点已加载: {path}")

    def train_loop(self):
        """完整训练循环"""
        logger.info("开始训练...")

        while self.training_info['timesteps'] < self.config.total_timesteps:
            # 收集 rollout
            rollout_info = self.collect_rollouts()
            logger.info(f"Rollout 完成: mean_reward={rollout_info['mean_reward']:.2f}, "
                       f"timesteps={self.training_info['timesteps']}")

            # 训练
            train_info = self.train()
            logger.info(f"训练完成: loss={train_info['loss']:.4f}, "
                       f"policy_loss={train_info['policy_loss']:.4f}")

            # 评估
            if self.training_info['timesteps'] % self.config.eval_freq == 0:
                eval_info = self.evaluate(self.config.n_eval_episodes)
                logger.info(f"评估: mean_reward={eval_info['mean_reward']:.2f}, "
                           f"std_reward={eval_info['std_reward']:.2f}")

                # 保存最佳模型
                if eval_info['mean_reward'] > self.training_info['best_reward']:
                    self.training_info['best_reward'] = eval_info['mean_reward']
                    self.save_checkpoint("best_model.pth")
                    logger.info(f"最佳模型已保存: {eval_info['mean_reward']:.2f}")

            # 定期保存
            if self.training_info['timesteps'] % self.config.save_freq == 0:
                self.save_checkpoint(f"checkpoint_{self.training_info['timesteps']}.pth")

        logger.info("训练完成！")
        logger.info(f"总步数: {self.training_info['timesteps']}")
        logger.info(f"总 episodes: {self.training_info['episodes']}")
        logger.info(f"最佳奖励: {self.training_info['best_reward']:.2f}")
