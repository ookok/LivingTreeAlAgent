"""
代码进化强化学习环境 (Code Evolution Environment)
=============================================

为EvolutionEngine提供强化学习环境。

状态空间 (State):
- 代码质量评分 (0-1)
- 测试通过率 (0-1)  
- 性能指标 (0-1)
- 错误数量 (0-10)
- 修改文件数 (0-20)
- 执行阶段 (0-4)

动作空间 (Action):
0: modify_parameter - 修改参数
1: switch_strategy - 切换策略
2: add_test_case - 添加测试用例
3: refactor_code - 重构代码
4: rollback_last_change - 回滚上次修改
"""

import random
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EvolutionStage(Enum):
    """进化阶段"""
    INIT = 0      # 初始状态
    ANALYZING = 1  # 分析中
    MODIFYING = 2  # 修改中
    TESTING = 3    # 测试中
    EVALUATING = 4 # 评估中


@dataclass
class EnvState:
    """环境状态"""
    quality_score: float = 0.5      # 代码质量 (0-1)
    test_pass_rate: float = 0.8    # 测试通过率 (0-1)
    performance_score: float = 0.5   # 性能评分 (0-1)
    bug_count: int = 0               # 错误数量
    modified_files: int = 0          # 修改文件数
    stage: int = 0                   # 当前阶段
    steps: int = 0                  # 执行步数
    max_steps: int = 100            # 最大步数
    
    def to_vector(self) -> List[float]:
        """转换为状态向量"""
        return [
            self.quality_score,
            self.test_pass_rate,
            self.performance_score,
            self.bug_count / 10.0,  # 归一化
            min(self.modified_files / 20.0, 1.0),  # 归一化
            self.stage / 4.0,  # 归一化
        ]
    
    def copy(self) -> "EnvState":
        """复制状态"""
        return EnvState(
            quality_score=self.quality_score,
            test_pass_rate=self.test_pass_rate,
            performance_score=self.performance_score,
            bug_count=self.bug_count,
            modified_files=self.modified_files,
            stage=self.stage,
            steps=self.steps,
            max_steps=self.max_steps,
        )


class CodeEvolutionEnv:
    """
    代码进化环境
    
    模拟代码进化过程，为RL Agent提供训练和评估环境。
    这是一个轻量级实现，不依赖外部库。
    """
    
    def __init__(self, project_root: str = "", state_dim: int = 6, action_dim: int = 5):
        """
        初始化环境
        
        Args:
            project_root: 项目根目录
            state_dim: 状态空间维度
            action_dim: 动作空间维度
        """
        self.project_root = project_root
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 动作空间定义
        self.actions = [
            'modify_parameter',
            'switch_strategy',
            'add_test_case',
            'refactor_code',
            'rollback_last_change'
        ]
        
        # 当前状态
        self.state = EnvState()
        self.initial_state = EnvState()
        
        # 执行历史
        self.history = []
        
        logger.info(f"[CodeEvolutionEnv] 初始化完成，项目目录: {project_root}")
    
    def reset(self) -> List[float]:
        """
        重置环境到初始状态
        
        Returns:
            初始状态向量
        """
        self.state = EnvState()
        self.initial_state = self.state.copy()
        self.history = []
        
        logger.debug("[CodeEvolutionEnv] 环境已重置")
        return self.state.to_vector()
    
    def step(self, action: int) -> Tuple[List[float], float, bool, Dict[str, Any]]:
        """
        执行一步动作
        
        Args:
            action: 动作编号 (0-4)
            
        Returns:
            (next_state, reward, done, info)
        """
        if action < 0 or action >= len(self.actions):
            logger.warning(f"[CodeEvolutionEnv] 无效动作: {action}")
            action = 0
        
        action_name = self.actions[action]
        self.state.steps += 1
        
        # 执行动作（模拟）
        result = self._execute_action(action_name)
        
        # 状态转移
        self._transition(action_name, result)
        
        # 计算奖励
        reward = self._calculate_reward(result)
        
        # 检查是否结束
        done = self._is_done(result)
        
        # 记录历史
        self.history.append({
            'step': self.state.steps,
            'action': action_name,
            'result': result,
            'reward': reward,
            'done': done,
        })
        
        info = {
            'result': result,
            'action_name': action_name,
            'steps': self.state.steps,
        }
        
        logger.debug(f"[CodeEvolutionEnv] 步骤 {self.state.steps}: {action_name}, reward={reward:.2f}, done={done}")
        
        return self.state.to_vector(), reward, done, info
    
    def _execute_action(self, action_name: str) -> Dict[str, Any]:
        """
        执行动作（模拟版本）
        
        在实际应用中，这里应该调用EvolutionEngine执行真实动作。
        这里使用模拟结果进行演示。
        """
        result = {
            'success': True,
            'quality_improvement': 0.0,
            'test_pass_rate_change': 0.0,
            'performance_improvement': 0.0,
            'new_bugs': 0,
            'modification_size': 0,
        }
        
        # 模拟不同动作的效果
        if action_name == 'modify_parameter':
            # 修改参数：小幅改善质量，可能引入bug
            result['quality_improvement'] = random.uniform(0.01, 0.05)
            result['performance_improvement'] = random.uniform(0.0, 0.03)
            result['new_bugs'] = 1 if random.random() < 0.2 else 0
            result['modification_size'] = random.randint(1, 5)
            
        elif action_name == 'switch_strategy':
            # 切换策略：可能跳跃性改善
            result['quality_improvement'] = random.uniform(-0.05, 0.1)
            result['test_pass_rate_change'] = random.uniform(-0.1, 0.05)
            result['new_bugs'] = random.randint(0, 2)
            result['modification_size'] = random.randint(5, 15)
            
        elif action_name == 'add_test_case':
            # 添加测试：提高测试覆盖率，不直接改善质量
            result['quality_improvement'] = random.uniform(0.0, 0.02)
            result['test_pass_rate_change'] = random.uniform(0.0, 0.1)
            result['new_bugs'] = 0
            result['modification_size'] = random.randint(1, 3)
            
        elif action_name == 'refactor_code':
            # 重构代码：可能大幅改善质量，但风险高
            result['quality_improvement'] = random.uniform(-0.02, 0.15)
            result['performance_improvement'] = random.uniform(-0.05, 0.1)
            result['new_bugs'] = random.randint(0, 3)
            result['modification_size'] = random.randint(10, 30)
            
        elif action_name == 'rollback_last_change':
            # 回滚：撤销上次修改
            result['quality_improvement'] = random.uniform(-0.05, 0.05)
            result['test_pass_rate_change'] = random.uniform(-0.05, 0.05)
            result['new_bugs'] = 0
            result['modification_size'] = 0
            result['success'] = True
        
        return result
    
    def _transition(self, action_name: str, result: Dict[str, Any]):
        """状态转移"""
        # 更新质量评分
        self.state.quality_score += result['quality_improvement']
        self.state.quality_score = max(0.0, min(1.0, self.state.quality_score))
        
        # 更新测试通过率
        self.state.test_pass_rate += result['test_pass_rate_change']
        self.state.test_pass_rate = max(0.0, min(1.0, self.state.test_pass_rate))
        
        # 更新性能评分
        self.state.performance_score += result['performance_improvement']
        self.state.performance_score = max(0.0, min(1.0, self.state.performance_score))
        
        # 更新错误数量
        self.state.bug_count += result['new_bugs']
        self.state.bug_count = max(0, self.state.bug_count)
        
        # 更新修改文件数
        self.state.modified_files += result['modification_size']
        
        # 更新阶段
        if self.state.quality_score > 0.8 and self.state.test_pass_rate > 0.9:
            self.state.stage = EvolutionStage.EVALUATING.value
        elif self.state.modified_files > 10:
            self.state.stage = EvolutionStage.TESTING.value
        else:
            self.state.stage = EvolutionStage.MODIFYING.value
    
    def _calculate_reward(self, result: Dict[str, Any]) -> float:
        """
        计算奖励（多目标）
        
        奖励设计:
        - 代码质量提升: +10/单位
        - 测试通过率提升: +5/单位
        - 性能提升: +3/单位
        - 引入新bug: -20/个
        - 过度修改: -0.1/单位
        """
        reward = 0.0
        
        # 代码质量提升
        reward += result.get('quality_improvement', 0) * 10.0
        
        # 测试通过率
        reward += result.get('test_pass_rate_change', 0) * 5.0
        
        # 性能提升
        reward += result.get('performance_improvement', 0) * 3.0
        
        # 惩罚：引入新bug
        reward -= result.get('new_bugs', 0) * 20.0
        
        # 惩罚：过度修改
        reward -= result.get('modification_size', 0) * 0.1
        
        # 额外奖励：达到高质量
        if self.state.quality_score > 0.9 and self.state.test_pass_rate > 0.95:
            reward += 50.0
        
        # 惩罚：质量下降过多
        if self.state.quality_score < self.initial_state.quality_score - 0.2:
            reward -= 30.0
        
        return reward
    
    def _is_done(self, result: Dict[str, Any]) -> bool:
        """检查是否结束"""
        # 达到最大步数
        if self.state.steps >= self.state.max_steps:
            return True
        
        # 质量达到目标且测试通过
        if self.state.quality_score > 0.95 and self.state.test_pass_rate > 0.98:
            return True
        
        # 引入过多bug
        if self.state.bug_count > 10:
            return True
        
        return False
    
    def get_state(self) -> List[float]:
        """获取当前状态向量"""
        return self.state.to_vector()
    
    def render(self, mode: str = 'log'):
        """渲染环境状态（用于调试）"""
        if mode == 'log':
            logger.info(
                f"[CodeEvolutionEnv] 步骤: {self.state.steps}, "
                f"质量: {self.state.quality_score:.2f}, "
                f"测试: {self.state.test_pass_rate:.2f}, "
                f"性能: {self.state.performance_score:.2f}, "
                f"Bug: {self.state.bug_count}"
            )
        elif mode == 'print':
            print(
                f"步骤: {self.state.steps}, "
                f"质量: {self.state.quality_score:.2f}, "
                f"测试: {self.state.test_pass_rate:.2f}, "
                f"性能: {self.state.performance_score:.2f}, "
                f"Bug: {self.state.bug_count}"
            )
    
    def close(self):
        """关闭环境"""
        pass


def make_env(project_root: str = "") -> CodeEvolutionEnv:
    """创建环境的工厂函数"""
    return CodeEvolutionEnv(project_root=project_root)


if __name__ == "__main__":
    # 简单测试
    env = CodeEvolutionEnv()
    state = env.reset()
    
    print("初始状态:", state)
    
    for i in range(10):
        action = random.randint(0, 4)
        next_state, reward, done, info = env.step(action)
        print(f"步骤 {i+1}: 动作={info['action_name']}, 奖励={reward:.2f}, 状态={next_state}")
        if done:
            print("结束!")
            break
