"""
自我意识与自我修复系统
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AutonomyLevel(Enum):
    """自主级别"""
    LEVEL0 = 0  # 完全手动
    LEVEL1 = 1  # 建议辅助
    LEVEL2 = 2  # 执行确认
    LEVEL3 = 3  # 自主执行
    LEVEL4 = 4  # 自主学习
    LEVEL5 = 5  # 完全自主


@dataclass
class Goal:
    """目标"""
    goal_id: str
    description: str
    priority: float
    progress: float = 0.0
    created_at: float = None
    deadline: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class SelfAwareness:
    """
    自我意识系统 - 元认知 + 自我修复 + 自我进化
    """
    
    def __init__(self, storage_path: str = "data/awareness"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._autonomy_level = AutonomyLevel.LEVEL3
        self._goals: Dict[str, Goal] = {}
        self._state = {
            'health': 'good',
            'cognitive_load': 0.5,
            'learning_rate': 0.1,
            'last_reflection': time.time()
        }
        
        self._load_state()
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        return {
            'autonomy_level': self._autonomy_level.value,
            'state': self._state,
            'goals': [
                {
                    'id': g.goal_id,
                    'desc': g.description,
                    'progress': g.progress,
                    'priority': g.priority
                }
                for g in self._goals.values()
            ],
            'timestamp': time.time()
        }
    
    def set_goal(
        self,
        description: str,
        priority: float = 0.5,
        deadline: Optional[float] = None
    ) -> str:
        """设置目标"""
        import uuid
        goal_id = str(uuid.uuid4())
        
        goal = Goal(
            goal_id=goal_id,
            description=description,
            priority=priority,
            deadline=deadline
        )
        
        self._goals[goal_id] = goal
        self._save_state()
        
        logger.info(f"Set goal: {description}")
        return goal_id
    
    def update_goal_progress(self, goal_id: str, progress: float):
        """更新目标进度"""
        if goal_id in self._goals:
            self._goals[goal_id].progress = min(1.0, max(0.0, progress))
            self._save_state()
    
    def reflect(self) -> Dict:
        """
        自我反思 - 回顾决策和结果
        """
        logger.debug("Performing self-reflection...")
        
        reflections = {
            'state_check': self._check_state(),
            'goal_assessment': self._assess_goals(),
            'improvement_suggestions': self._generate_improvements()
        }
        
        self._state['last_reflection'] = time.time()
        self._save_state()
        
        return reflections
    
    def _check_state(self) -> Dict:
        """检查自身状态"""
        return {
            'health': self._state['health'],
            'needs_attention': self._state['cognitive_load'] > 0.8
        }
    
    def _assess_goals(self) -> List[Dict]:
        """评估目标"""
        assessments = []
        for goal_id, goal in self._goals.items():
            status = 'on_track'
            if goal.progress < 0.3 and time.time() - goal.created_at > 3600:
                status = 'at_risk'
            elif goal.progress >= 1.0:
                status = 'completed'
            
            assessments.append({
                'goal_id': goal_id,
                'status': status,
                'description': goal.description
            })
        
        return assessments
    
    def _generate_improvements(self) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if self._state['cognitive_load'] > 0.7:
            suggestions.append("降低并发任务数量")
        
        if len(self._goals) > 5:
            suggestions.append("合并或优先排序目标")
        
        if not suggestions:
            suggestions.append("继续当前状态，运行良好")
        
        return suggestions
    
    def self_optimize(self) -> Dict:
        """
        自我优化 - 自动调整参数和策略
        """
        logger.info("Starting self-optimization...")
        
        optimizations = {
            'learning_rate': self._tune_learning_rate(),
            'memory_retention': self._optimize_memory(),
            'performance': self._adjust_performance()
        }
        
        self._save_state()
        
        return optimizations
    
    def _tune_learning_rate(self) -> float:
        """调整学习率"""
        # 简单的启发式调整
        if self._state['cognitive_load'] > 0.8:
            new_rate = max(0.01, self._state['learning_rate'] * 0.8)
        else:
            new_rate = min(0.2, self._state['learning_rate'] * 1.1)
        
        self._state['learning_rate'] = new_rate
        return new_rate
    
    def _optimize_memory(self) -> Dict:
        """优化记忆策略"""
        return {
            'retention_threshold': 0.6,
            'consolidation_interval': 3600
        }
    
    def _adjust_performance(self) -> Dict:
        """调整性能参数"""
        return {
            'max_tasks': 10 if self._state['cognitive_load'] < 0.5 else 5,
            'timeout': 300
        }
    
    def diagnose(self) -> Dict:
        """自我诊断"""
        issues = []
        
        if self._state['health'] != 'good':
            issues.append({
                'type': 'health',
                'severity': 'medium',
                'description': '系统健康状态异常'
            })
        
        if self._state['cognitive_load'] > 0.9:
            issues.append({
                'type': 'cognitive_overload',
                'severity': 'high',
                'description': '认知负载过高'
            })
        
        return {
            'status': 'ok' if not issues else 'needs_attention',
            'issues': issues,
            'timestamp': time.time()
        }
    
    def set_autonomy_level(self, level: AutonomyLevel):
        """设置自主级别"""
        self._autonomy_level = level
        logger.info(f"Set autonomy level to: {level}")
        self._save_state()
    
    def _save_state(self):
        """保存状态"""
        data = {
            'autonomy_level': self._autonomy_level.value,
            'state': self._state,
            'goals': {
                g.goal_id: {
                    'goal_id': g.goal_id,
                    'description': g.description,
                    'priority': g.priority,
                    'progress': g.progress,
                    'created_at': g.created_at,
                    'deadline': g.deadline
                }
                for g in self._goals.values()
            }
        }
        
        with open(self.storage_path / "state.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_state(self):
        """加载状态"""
        file_path = self.storage_path / "state.json"
        if not file_path.exists():
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._autonomy_level = AutonomyLevel(data.get('autonomy_level', 3))
            self._state = data.get('state', self._state)
            
            for goal_id, goal_data in data.get('goals', {}).items():
                self._goals[goal_id] = Goal(**goal_data)
                
        except Exception as e:
            logger.error(f"Load state error: {e}")
