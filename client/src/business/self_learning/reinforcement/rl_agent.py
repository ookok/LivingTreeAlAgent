"""
强化学习智能体（PPO 算法）
用于优化代码进化决策
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical
from typing import Optional, Tuple, List
import numpy as np


class PolicyNetwork(nn.Module):
    """
    策略网络（Actor）
    输出：动作概率分布
    """
    
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim)
        
        # 初始化权重
        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.xavier_uniform_(self.fc3.weight)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        action_probs = F.softmax(self.fc3(x), dim=-1)
        return action_probs


class ValueNetwork(nn.Module):
    """
    价值网络（Critic）
    输出：状态价值估计
    """
    
    def __init__(self, state_dim: int, hidden_dim: int = 128):
        super(ValueNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)
        
        # 初始化权重
        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.xavier_uniform_(self.fc3.weight)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        value = self.fc3(x)
        return value.squeeze(-1)  # 移除最后一维


class RLAgent:
    """
    强化学习智能体（PPO 算法）
    
    特点：
    - Actor-Critic 架构
    - Clipped Surrogate Objective（PPO-Clip）
    - General Advantage Estimation（GAE）
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        eps_clip: float = 0.2,
        hidden_dim: int = 128
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.eps_clip = eps_clip
        
        # 策略网络（Actor）
        self.policy_net = PolicyNetwork(state_dim, action_dim, hidden_dim)
        
        # 价值网络（Critic）
        self.value_net = ValueNetwork(state_dim, hidden_dim)
        
        # 优化器
        self.optimizer = torch.optim.Adam(
            list(self.policy_net.parameters()) + list(self.value_net.parameters()),
            lr=lr
        )
        
        # 经验回放缓冲区
        self.memory: List[Tuple[np.ndarray, int, float, float, bool]] = []
        
        # 设备
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.policy_net.to(self.device)
        self.value_net.to(self.device)
    
    def select_action(self, state: np.ndarray) -> Tuple[int, float]:
        """
        选择动作
        
        Args:
            state: 状态向量
            
        Returns:
            (action, log_prob)
        """
        state_tensor = torch.tensor(state, dtype=torch.float32, device=self.device)
        
        # 前向传播
        action_probs = self.policy_net(state_tensor)
        
        # 采样动作
        dist = Categorical(action_probs)
        action = dist.sample()
        
        # 计算 log probability
        log_prob = dist.log_prob(action)
        
        return action.item(), log_prob.item()
    
    def store_transition(self, transition: Tuple[np.ndarray, int, float, float, bool]):
        """
        存储转移
        
        Args:
            transition: (state, action, log_prob, reward, done)
        """
        self.memory.append(transition)
    
    def update(self):
        """
        PPO 更新策略
        
        核心思想：
        1. 计算 GAE（Generalized Advantage Estimation）
        2. Clipped Surrogate Objective
        3. Value Function Loss
        4. 总损失 = policy_loss + value_loss + entropy_bonus
        """
        if len(self.memory) == 0:
            return
        
        # 解析经验回放
        states = []
        actions = []
        old_log_probs = []
        rewards = []
        dones = []
        
        for (state, action, log_prob, reward, done) in self.memory:
            states.append(state)
            actions.append(action)
            old_log_probs.append(log_prob)
            rewards.append(reward)
            dones.append(done)
        
        # 转换为 tensor
        states_tensor = torch.tensor(np.array(states), dtype=torch.float32, device=self.device)
        actions_tensor = torch.tensor(actions, dtype=torch.int64, device=self.device)
        old_log_probs_tensor = torch.tensor(old_log_probs, dtype=torch.float32, device=self.device)
        rewards_tensor = torch.tensor(rewards, dtype=torch.float32, device=self.device)
        dones_tensor = torch.tensor(dones, dtype=torch.float32, device=self.device)
        
        # 计算 GAE
        advantages = self._compute_gae(rewards_tensor, dones_tensor)
        returns = advantages + self.value_net(states_tensor).detach()
        
        # 归一化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO Update（K-epochs）
        K_EPOCHS = 10
        for _ in range(K_EPOCHS):
            # 前向传播
            action_probs = self.policy_net(states_tensor)
            dist = Categorical(action_probs)
            new_log_probs = dist.log_prob(actions_tensor)
            entropy = dist.entropy()
            
            # 计算 ratio
            ratios = torch.exp(new_log_probs - old_log_probs_tensor)
            
            # Clipped Surrogate Objective
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            
            # Value Loss
            values = self.value_net(states_tensor)
            value_loss = F.mse_loss(values, returns)
            
            # Entropy Bonus（鼓励探索）
            entropy_bonus = -0.01 * entropy.mean()
            
            # 总损失
            loss = policy_loss + 0.5 * value_loss + entropy_bonus
            
            # 反向传播
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(self.policy_net.parameters()) + list(self.value_net.parameters()),
                max_norm=0.5
            )
            self.optimizer.step()
        
        # 清空缓冲区
        self.memory.clear()
    
    def _compute_gae(self, rewards: torch.Tensor, dones: torch.Tensor, lam: float = 0.95) -> torch.Tensor:
        """
        计算 Generalized Advantage Estimation（GAE）
        
        GAE = sum_{t=0}^{T-t} (lam * gamma)^t * delta_{t+t}
        where delta_t = r_t + gamma * V(s_{t+1}) - V(s_t)
        """
        with torch.no_grad():
            values = self.value_net(torch.tensor(np.array([s for s in rewards]), dtype=torch.float32).to(self.device)).cpu()
        
        gae = 0
        advantages = torch.zeros_like(rewards)
        
        for t in reversed(range(len(rewards))):
            if dones[t]:
                gae = rewards[t] - values[t]
            else:
                delta = rewards[t] + self.gamma * values[t + 1] - values[t]
                gae = delta + self.gamma * lam * gae
            
            advantages[t] = gae
        
        return advantages.to(self.device)
    
    def save(self, path: str):
        """保存模型"""
        torch.save({
            'policy_net_state_dict': self.policy_net.state_dict(),
            'value_net_state_dict': self.value_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
        }, path)
        print(f"[OK] Model saved to {path}")
    
    def load(self, path: str):
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
        self.value_net.load_state_dict(checkpoint['value_net_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        print(f"[OK] Model loaded from {path}")


# 测试代码
if __name__ == '__main__':
    # 测试环境
    from rl_environment import CodeEvolutionEnv
    
    env = CodeEvolutionEnv()
    agent = RLAgent(state_dim=6, action_dim=5)
    
    # 训练循环
    num_episodes = 1000
    max_steps = 100
    
    for episode in range(num_episodes):
        state = env.reset()
        episode_reward = 0
        done = False
        
        for step in range(max_steps):
            # 选择动作
            action, log_prob = agent.select_action(state)
            
            # 执行动作
            next_state, reward, done, info = env.step(action)
            
            # 存储转移
            agent.store_transition((state, action, log_prob, reward, done))
            
            state = next_state
            episode_reward += reward
            
            if done:
                break
        
        # 更新策略
        agent.update()
        
        # 打印进度
        if episode % 100 == 0:
            print(f"Episode {episode}, Reward: {episode_reward:.2f}")
    
    print("\n[OK] Training completed!")
    
    # 保存模型
    agent.save('rl_agent_pretrained.pth')
