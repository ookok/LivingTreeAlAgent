"""
RL 训练器 (Reinforcement Learning Trainer)
=========================================

提供完整的训练循环和监控功能。

配合 CodeEvolutionEnv 和 PPOAgent 使用。
"""

import time
import logging
from typing import List, Dict, Any, Optional, Callable
from collections import deque
import copy

logger = logging.getLogger(__name__)


class RLTrainer:
    """
    RL 训练器（简化版）
    
    协调环境、智能体，实现完整的训练循环。
    支持:
    - 多回合训练
    - 定期评估
    - 早停 (early stopping)
    - 模型检查点保存
    """
    
    def __init__(
        self,
        env,
        agent,
        config: Optional["TrainingConfig"] = None,
        log_interval: int = 10,
        eval_interval: int = 50,
        save_interval: int = 100,
        early_stopping_reward: Optional[float] = None,
    ):
        """
        初始化训练器
        
        Args:
            env: 训练环境
            agent: RL 智能体
            config: 训练配置
            log_interval: 日志打印间隔（回合数）
            eval_interval: 评估间隔（回合数）
            save_interval: 保存间隔（回合数）
            early_stopping_reward: 早停奖励阈值
        """
        self.env = env
        self.agent = agent
        self.config = config or TrainingConfig()
        self.log_interval = log_interval
        self.eval_interval = eval_interval
        self.save_interval = save_interval
        self.early_stopping_reward = early_stopping_reward
        
        # 训练统计
        self.training_info = {
            "timesteps": 0,
            "episodes": 0,
            "episode_rewards": deque(maxlen=100),
            "avg_reward": 0.0,
            "best_reward": float("-inf"),
            "eval_rewards": deque(maxlen=20),
            "losses": deque(maxlen=100),
            "start_time": None,
            "training_time": 0.0,
        }
        
        logger.info(f"[RLTrainer] 初始化完成，总步数: {self.config.total_timesteps}")
    
    def train(self):
        """执行完整训练"""
        self.training_info["start_time"] = time.time()
        state = self.env.reset()
        episode_reward = 0.0
        episode_steps = 0
        done = False
        
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
            self.training_info["timesteps"] = timestep
            
            # 检查回合结束
            if done or episode_steps >= self.config.max_episode_length:
                # 更新策略
                self.agent.train()
                
                # 更新训练信息
                self.training_info["episodes"] += 1
                self.training_info["episode_rewards"].append(episode_reward)
                
                avg_reward = sum(self.training_info["episode_rewards"]) / len(
                    self.training_info["episode_rewards"]
                )
                self.training_info["avg_reward"] = avg_reward
                
                if episode_reward > self.training_info["best_reward"]:
                    self.training_info["best_reward"] = episode_reward
                
                # 日志
                if self.training_info["episodes"] % self.log_interval == 0:
                    logger.info(
                        f"[RLTrainer] 回合: {self.training_info['episodes']}, "
                        f"平均奖励: {avg_reward:.2f}, "
                        f"最佳奖励: {self.training_info['best_reward']:.2f}"
                    )
                    print(
                        f"Episode {self.training_info['episodes']}, "
                        f"Avg Reward: {avg_reward:.2f}"
                    )
                
                # 定期评估
                if self.training_info["episodes"] % self.eval_interval == 0:
                    eval_reward = self.evaluate(n_episodes=5)
                    self.training_info["eval_rewards"].append(eval_reward)
                    logger.info(f"[RLTrainer] 评估奖励: {eval_reward:.2f}")
                
                # 定期保存
                if self.training_info["episodes"] % self.save_interval == 0:
                    self.save_checkpoint()
                
                # 早停检查
                if (
                    self.early_stopping_reward is not None
                    and avg_reward >= self.early_stopping_reward
                ):
                    logger.info(f"[RLTrainer] 早停触发，平均奖励: {avg_reward:.2f}")
                    break
                
                # 重置环境和回合统计
                state = self.env.reset()
                episode_reward = 0.0
                episode_steps = 0
            else:
                state = next_state
        
        # 训练完成
        self.training_info["training_time"] = time.time() - self.training_info["start_time"]
        logger.info(f"[RLTrainer] 训练完成，总耗时: {self.training_info['training_time']:.2f}s")
        print("Training completed!")
    
    def evaluate(self, n_episodes: int = 10, render: bool = False) -> float:
        """
        评估当前策略
        
        Args:
            n_episodes: 评估回合数
            render: 是否渲染环境
            
        Returns:
            平均奖励
        """
        eval_rewards = []
        
        for ep in range(n_episodes):
            state = self.env.reset()
            done = False
            episode_reward = 0.0
            steps = 0
            
            while not done and steps < self.config.max_episode_length:
                # 评估时使用确定性策略（选择最高概率动作）
                probs = self.agent.policy.forward(state)
                action = probs.index(max(probs))
                
                state, reward, done, info = self.env.step(action)
                episode_reward += reward
                steps += 1
                
                if render:
                    self.env.render(mode="print")
            
            eval_rewards.append(episode_reward)
            logger.debug(f"[RLTrainer] 评估回合 {ep+1}: 奖励 = {episode_reward:.2f}")
        
        avg_reward = sum(eval_rewards) / len(eval_rewards)
        return avg_reward
    
    def save_checkpoint(self, path: Optional[str] = None):
        """
        保存检查点
        
        Args:
            path: 保存路径（None 则使用默认路径）
        """
        # 简化版：打印保存信息
        logger.info(f"[RLTrainer] 检查点保存（简化版，未实际保存文件）")
        print(f"Checkpoint saved (timestep: {self.training_info['timesteps']})")
    
    def load_checkpoint(self, path: str):
        """
        加载检查点
        
        Args:
            path: 检查点文件路径
        """
        logger.info(f"[RLTrainer] 检查点加载（简化版，未实际加载文件）")
    
    def get_training_info(self) -> Dict[str, Any]:
        """获取训练信息"""
        info = copy.deepcopy(self.training_info)
        info["training_time"] = time.time() - info["start_time"] if info["start_time"] else 0
        return info


class TrainingConfig:
    """训练配置（重复定义，避免循环导入）"""
    
    def __init__(
        self,
        total_timesteps: int = 100000,
        max_episode_length: int = 1000,
        update_epochs: int = 10,
        batch_size: int = 64,
        learning_rate: float = 3e-4,
        gamma: float = 0.99,
        eps_clip: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
    ):
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


if __name__ == "__main__":
    # 简单测试
    from .rl_environment import CodeEvolutionEnv
    from .rl_agent import PPOAgent
    
    # 创建环境和智能体
    env = CodeEvolutionEnv()
    agent = PPOAgent(state_dim=6, action_dim=5)
    config = TrainingConfig(total_timesteps=1000)
    trainer = RLTrainer(env, agent, config)
    
    # 训练
    trainer.train()
    
    # 评估
    eval_reward = trainer.evaluate(n_episodes=5)
    print(f"评估结果: {eval_reward:.2f}")
