"""
强化学习环境：代码进化环境
用于训练 RL Agent 优化代码进化决策
"""

import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class EvolutionAction:
    """进化动作"""
    action_type: str  # 'modify_parameter', 'switch_strategy', 'add_test_case', 'refactor_code', 'rollback_last_change'
    action_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionState:
    """进化状态"""
    code_quality: float  # 代码质量 (0-1)
    test_pass_rate: float  # 测试通过率 (0-1)
    performance_score: float  # 性能分数 (0-1)
    bug_count: int  # Bug 数量
    modification_size: int  # 修改规模（行数）
    evolution_progress: float  # 进化进度 (0-1)
    
    def to_vector(self) -> np.ndarray:
        """转换为向量"""
        return np.array([
            self.code_quality,
            self.test_pass_rate,
            self.performance_score,
            self.bug_count / 100.0,  # 归一化
            self.modification_size / 1000.0,  # 归一化
            self.evolution_progress
        ], dtype=np.float32)


class CodeEvolutionEnv:
    """
    代码进化环境（强化学习）
    
    状态空间：
    - 代码质量、测试通过率、性能分数、Bug 数量、修改规模、进化进度
    
    动作空间：
    - modify_parameter: 修改进化参数
    - switch_strategy: 切换进化策略
    - add_test_case: 添加测试用例
    - refactor_code: 重构代码
    - rollback_last_change: 回滚上次修改
    
    奖励函数：
    - 代码质量提升: +10
    - 测试通过率提升: +5
    - 性能提升: +3
    - 引入新 bug: -20
    - 过度修改: -0.1/行
    """
    
    def __init__(self, evolution_engine: Optional[Any] = None):
        self.evolution_engine = evolution_engine
        
        # 状态空间维度
        self.state_dim = 6
        
        # 动作空间
        self.action_types = [
            'modify_parameter',
            'switch_strategy',
            'add_test_case',
            'refactor_code',
            'rollback_last_change'
        ]
        self.action_dim = len(self.action_types)
        
        # 当前状态
        self.current_state = None
        self.steps = 0
        self.max_steps = 100
        
        # 历史记录
        self.history = []
    
    def reset(self) -> np.ndarray:
        """重置环境，返回初始状态"""
        self.current_state = EvolutionState(
            code_quality=0.5,
            test_pass_rate=0.7,
            performance_score=0.5,
            bug_count=5,
            modification_size=0,
            evolution_progress=0.0
        )
        self.steps = 0
        self.history = []
        
        return self.current_state.to_vector()
    
    def step(self, action_idx: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        执行一步动作
        
        Args:
            action_idx: 动作索引（0-4）
            
        Returns:
            (next_state, reward, done, info)
        """
        action_type = self.action_types[action_idx]
        
        # 执行动作
        result = self._execute_action(action_type)
        
        # 计算奖励
        reward = self._calculate_reward(result)
        
        # 更新状态
        self._update_state(result)
        
        # 检查是否结束
        self.steps += 1
        done = self.steps >= self.max_steps or result.get('success', True) == False
        
        # 记录历史
        self.history.append({
            'step': self.steps,
            'action': action_type,
            'reward': reward,
            'state': self.current_state.to_vector().tolist()
        })
        
        info = {
            'result': result,
            'action_type': action_type
        }
        
        return self.current_state.to_vector(), reward, done, info
    
    def _execute_action(self, action_type: str) -> Dict[str, Any]:
        """执行动作"""
        result = {
            'success': True,
            'quality_change': 0.0,
            'test_pass_change': 0.0,
            'performance_change': 0.0,
            'new_bugs': 0,
            'modification_size': 0
        }
        
        if action_type == 'modify_parameter':
            # 模拟修改参数
            result['quality_change'] = np.random.uniform(0.0, 0.05)
            result['test_pass_change'] = np.random.uniform(-0.02, 0.03)
            result['performance_change'] = np.random.uniform(0.0, 0.03)
            result['new_bugs'] = np.random.choice([0, 1], p=[0.9, 0.1])
            result['modification_size'] = np.random.randint(10, 100)
            
        elif action_type == 'switch_strategy':
            # 模拟切换策略
            result['quality_change'] = np.random.uniform(-0.05, 0.1)
            result['test_pass_change'] = np.random.uniform(-0.05, 0.05)
            result['performance_change'] = np.random.uniform(-0.03, 0.08)
            result['new_bugs'] = np.random.choice([0, 1, 2], p=[0.8, 0.15, 0.05])
            result['modification_size'] = np.random.randint(50, 200)
            
        elif action_type == 'add_test_case':
            # 模拟添加测试用例
            result['quality_change'] = np.random.uniform(0.02, 0.08)
            result['test_pass_change'] = np.random.uniform(0.0, 0.05)
            result['performance_change'] = 0.0
            result['new_bugs'] = 0
            result['modification_size'] = np.random.randint(5, 30)
            
        elif action_type == 'refactor_code':
            # 模拟重构代码
            result['quality_change'] = np.random.uniform(0.05, 0.15)
            result['test_pass_change'] = np.random.uniform(-0.05, 0.05)
            result['performance_change'] = np.random.uniform(0.02, 0.1)
            result['new_bugs'] = np.random.choice([0, 1], p=[0.85, 0.15])
            result['modification_size'] = np.random.randint(100, 500)
            
        elif action_type == 'rollback_last_change':
            # 模拟回滚
            if len(self.history) > 0:
                last_action = self.history[-1]
                result['quality_change'] = -0.02  # 略微下降
                result['test_pass_change'] = 0.0
                result['performance_change'] = 0.0
                result['new_bugs'] = 0
                result['modification_size'] = 0
            else:
                result['success'] = False  # 无法回滚
        
        return result
    
    def _calculate_reward(self, result: Dict[str, Any]) -> float:
        """计算奖励（多目标）"""
        reward = 0.0
        
        # 代码质量提升
        reward += result.get('quality_change', 0) * 10.0
        
        # 测试通过率
        reward += result.get('test_pass_change', 0) * 5.0
        
        # 性能提升
        reward += result.get('performance_change', 0) * 3.0
        
        # 惩罚：引入新 bug
        reward -= result.get('new_bugs', 0) * 20.0
        
        # 惩罚：过度修改
        reward -= result.get('modification_size', 0) * 0.1
        
        return reward
    
    def _update_state(self, result: Dict[str, Any]):
        """更新状态"""
        self.current_state.code_quality = np.clip(
            self.current_state.code_quality + result.get('quality_change', 0),
            0.0, 1.0
        )
        self.current_state.test_pass_rate = np.clip(
            self.current_state.test_pass_rate + result.get('test_pass_change', 0),
            0.0, 1.0
        )
        self.current_state.performance_score = np.clip(
            self.current_state.performance_score + result.get('performance_change', 0),
            0.0, 1.0
        )
        self.current_state.bug_count = max(
            0, self.current_state.bug_count + result.get('new_bugs', 0)
        )
        self.current_state.modification_size += result.get('modification_size', 0)
        self.current_state.evolution_progress = np.clip(
            self.steps / self.max_steps, 0.0, 1.0
        )
    
    def render(self, mode='human'):
        """渲染环境（可选）"""
        if mode == 'human':
            print(f"Step {self.steps}:")
            print(f"  Code Quality: {self.current_state.code_quality:.2f}")
            print(f"  Test Pass Rate: {self.current_state.test_pass_rate:.2f}")
            print(f"  Performance Score: {self.current_state.performance_score:.2f}")
            print(f"  Bug Count: {self.current_state.bug_count}")
            print(f"  Modification Size: {self.current_state.modification_size}")
            print(f"  Evolution Progress: {self.current_state.evolution_progress:.2f}")
    
    def close(self):
        """关闭环境"""
        pass
