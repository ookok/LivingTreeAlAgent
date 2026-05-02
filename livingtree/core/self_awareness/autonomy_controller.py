"""
自主控制模块 - Autonomy Controller

功能：
1. 自主级别管理
2. 决策授权
3. 权限控制
4. 行为约束
"""

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

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
class AutonomyPolicy:
    """自主策略"""
    level: AutonomyLevel
    allowed_actions: Dict[str, bool]
    escalation_threshold: float
    review_required: bool


class AutonomyController:
    """
    自主控制器 - 管理系统自主级别和决策权限
    
    自主级别体系：
    - L0: 完全手动 - 所有操作需要人工确认
    - L1: 建议辅助 - 系统提供建议，人工决策
    - L2: 执行确认 - 系统执行前需人工确认
    - L3: 自主执行 - 系统自动执行常规任务
    - L4: 自主学习 - 系统自动学习和优化
    - L5: 完全自主 - 系统完全独立运行
    """
    
    def __init__(self):
        self._current_level = AutonomyLevel.LEVEL3
        self._policy = self._create_policy(self._current_level)
        self._history: Dict[str, Dict] = []
        self._max_history = 100
    
    def _create_policy(self, level: AutonomyLevel) -> AutonomyPolicy:
        """创建自主策略"""
        allowed_actions = {
            'monitor': True,
            'diagnose': True,
            'suggest': True,
            'fix': False,
            'deploy': False,
            'learn': False,
            'evolve': False
        }
        
        escalation_threshold = 0.9  # 高风险阈值
        review_required = True
        
        if level >= AutonomyLevel.LEVEL2:
            allowed_actions['fix'] = True
            review_required = False
        
        if level >= AutonomyLevel.LEVEL3:
            allowed_actions['deploy'] = True
            escalation_threshold = 0.8
        
        if level >= AutonomyLevel.LEVEL4:
            allowed_actions['learn'] = True
            escalation_threshold = 0.7
        
        if level >= AutonomyLevel.LEVEL5:
            allowed_actions['evolve'] = True
            escalation_threshold = 0.6
            review_required = False
        
        return AutonomyPolicy(
            level=level,
            allowed_actions=allowed_actions,
            escalation_threshold=escalation_threshold,
            review_required=review_required
        )
    
    def set_autonomy_level(self, level: AutonomyLevel):
        """设置自主级别"""
        old_level = self._current_level
        self._current_level = level
        self._policy = self._create_policy(level)
        
        # 记录变更
        self._history.append({
            'timestamp': time.time(),
            'old_level': old_level.value,
            'new_level': level.value,
            'action': 'level_change'
        })
        
        # 限制历史大小
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        logger.info(f"自主级别变更: L{old_level.value} -> L{level.value}")
    
    def can_perform_action(self, action: str) -> bool:
        """检查是否可以执行动作"""
        return self._policy.allowed_actions.get(action, False)
    
    def requires_review(self, risk_level: float = 0.0) -> bool:
        """检查是否需要人工审核"""
        if self._policy.review_required:
            return True
        
        # 根据风险级别判断
        if risk_level >= self._policy.escalation_threshold:
            return True
        
        return False
    
    def escalate(self, action: str, details: Dict) -> Dict:
        """升级请求人工干预"""
        self._history.append({
            'timestamp': time.time(),
            'action': 'escalation',
            'details': details
        })
        
        return {
            'escalated': True,
            'action': action,
            'level': self._current_level.value,
            'message': '请人工审核此操作'
        }
    
    def get_policy(self) -> AutonomyPolicy:
        """获取当前策略"""
        return self._policy
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'autonomy_level': self._current_level.value,
            'level_name': self._get_level_name(self._current_level),
            'policy': {
                'allowed_actions': self._policy.allowed_actions,
                'escalation_threshold': self._policy.escalation_threshold,
                'review_required': self._policy.review_required
            },
            'history_count': len(self._history)
        }
    
    def _get_level_name(self, level: AutonomyLevel) -> str:
        """获取级别名称"""
        names = {
            AutonomyLevel.LEVEL0: '完全手动',
            AutonomyLevel.LEVEL1: '建议辅助',
            AutonomyLevel.LEVEL2: '执行确认',
            AutonomyLevel.LEVEL3: '自主执行',
            AutonomyLevel.LEVEL4: '自主学习',
            AutonomyLevel.LEVEL5: '完全自主'
        }
        return names.get(level, '未知')
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取历史记录"""
        return self._history[-limit:]
    
    def request_permission(self, action: str, risk_level: float = 0.0) -> Dict:
        """请求执行权限"""
        if not self.can_perform_action(action):
            return {
                'granted': False,
                'reason': f"当前级别 L{self._current_level.value} 不允许此操作",
                'required_level': self._get_required_level(action)
            }
        
        if self.requires_review(risk_level):
            return {
                'granted': False,
                'reason': '需要人工审核',
                'escalation_needed': True
            }
        
        # 记录授权
        self._history.append({
            'timestamp': time.time(),
            'action': 'permission_granted',
            'details': {'action': action, 'risk_level': risk_level}
        })
        
        return {
            'granted': True,
            'reason': '权限已授予',
            'risk_level': risk_level
        }
    
    def _get_required_level(self, action: str) -> int:
        """获取执行动作所需的级别"""
        level_map = {
            'fix': 2,
            'deploy': 3,
            'learn': 4,
            'evolve': 5
        }
        return level_map.get(action, 3)