"""
自我反思模块 - Self Reflection

功能：
1. 自我评估
2. 决策回顾
3. 改进建议生成
4. 学习总结
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """反思结果"""
    state_check: Dict
    goal_assessment: List[Dict]
    improvement_suggestions: List[str]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class SelfReflection:
    """
    自我反思模块 - 元认知能力
    
    核心能力：
    1. 检查自身状态
    2. 评估目标进度
    3. 生成改进建议
    4. 学习经验教训
    """
    
    def __init__(self):
        self._reflection_history: List[ReflectionResult] = []
        self._max_history = 50
    
    def reflect(self, system_state: Dict, goals: List[Dict]) -> ReflectionResult:
        """
        执行自我反思
        
        Args:
            system_state: 系统状态
            goals: 目标列表
        
        Returns:
            反思结果
        """
        logger.debug("执行自我反思...")
        
        # 检查状态
        state_check = self._check_state(system_state)
        
        # 评估目标
        goal_assessment = self._assess_goals(goals)
        
        # 生成改进建议
        suggestions = self._generate_improvements(system_state, goals)
        
        # 创建反思结果
        result = ReflectionResult(
            state_check=state_check,
            goal_assessment=goal_assessment,
            improvement_suggestions=suggestions
        )
        
        # 保存历史
        self._reflection_history.append(result)
        if len(self._reflection_history) > self._max_history:
            self._reflection_history = self._reflection_history[-self._max_history:]
        
        return result
    
    def _check_state(self, system_state: Dict) -> Dict:
        """检查系统状态"""
        health = system_state.get('health', 'good')
        cognitive_load = system_state.get('cognitive_load', 0.5)
        learning_rate = system_state.get('learning_rate', 0.1)
        
        return {
            'health': health,
            'cognitive_load': cognitive_load,
            'learning_rate': learning_rate,
            'needs_attention': cognitive_load > 0.8,
            'optimal_learning': learning_rate > 0.05 and cognitive_load < 0.7
        }
    
    def _assess_goals(self, goals: List[Dict]) -> List[Dict]:
        """评估目标进度"""
        assessments = []
        
        for goal in goals:
            goal_id = goal.get('goal_id', '')
            description = goal.get('description', '')
            progress = goal.get('progress', 0.0)
            priority = goal.get('priority', 0.5)
            created_at = goal.get('created_at', 0)
            
            # 评估状态
            status = 'on_track'
            age_hours = (time.time() - created_at) / 3600 if created_at else 0
            
            if progress < 0.3 and age_hours > 1:
                status = 'at_risk'
            elif progress >= 1.0:
                status = 'completed'
            elif progress >= 0.7:
                status = 'nearly_complete'
            
            assessments.append({
                'goal_id': goal_id,
                'description': description,
                'progress': progress,
                'priority': priority,
                'status': status,
                'age_hours': round(age_hours, 1)
            })
        
        return assessments
    
    def _generate_improvements(self, system_state: Dict, goals: List[Dict]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        cognitive_load = system_state.get('cognitive_load', 0.5)
        
        # 基于认知负载的建议
        if cognitive_load > 0.8:
            suggestions.append("降低并发任务数量以减轻认知负载")
        elif cognitive_load > 0.6:
            suggestions.append("考虑暂停非关键任务")
        
        # 基于目标的建议
        if len(goals) > 5:
            suggestions.append("当前目标较多，建议合并或优先排序")
        
        # 基于学习率的建议
        learning_rate = system_state.get('learning_rate', 0.1)
        if learning_rate < 0.05:
            suggestions.append("学习率较低，考虑增加训练数据")
        
        # 默认建议
        if not suggestions:
            suggestions.append("系统运行状态良好，继续当前策略")
        
        return suggestions
    
    def learn_from_experience(self, experiences: List[Dict]) -> Dict:
        """从经验中学习"""
        if not experiences:
            return {'message': '没有经验数据可学习'}
        
        # 分析成功和失败
        successes = [e for e in experiences if e.get('success')]
        failures = [e for e in experiences if not e.get('success')]
        
        # 提取模式
        success_patterns = []
        failure_patterns = []
        
        for exp in successes:
            if 'strategy' in exp:
                success_patterns.append(exp['strategy'])
        
        for exp in failures:
            if 'error' in exp:
                failure_patterns.append(exp['error'][:30])
        
        return {
            'total_experiences': len(experiences),
            'success_rate': len(successes) / len(experiences),
            'common_strategies': list(set(success_patterns)),
            'common_errors': list(set(failure_patterns)),
            'learning_insights': self._extract_insights(successes, failures)
        }
    
    def _extract_insights(self, successes: List[Dict], failures: List[Dict]) -> List[str]:
        """提取学习洞察"""
        insights = []
        
        if len(successes) > 0:
            strategies_used = set(exp.get('strategy') for exp in successes if 'strategy' in exp)
            if strategies_used:
                insights.append(f"成功策略: {', '.join(strategies_used)}")
        
        if len(failures) > 0:
            error_types = set(exp.get('error_type') for exp in failures if 'error_type' in exp)
            if error_types:
                insights.append(f"常见失败类型: {', '.join(error_types)}")
        
        if len(successes) > len(failures):
            insights.append("整体表现良好，继续当前策略")
        elif len(failures) > len(successes):
            insights.append("失败较多，建议重新评估策略")
        
        return insights
    
    def get_reflection_history(self, limit: int = 10) -> List[ReflectionResult]:
        """获取反思历史"""
        return self._reflection_history[-limit:]
    
    def get_summary(self) -> Dict:
        """获取反思摘要"""
        if not self._reflection_history:
            return {'message': '尚无反思记录'}
        
        recent = self._reflection_history[-1]
        
        return {
            'last_reflection': recent.timestamp,
            'suggestion_count': len(recent.improvement_suggestions),
            'goals_assessed': len(recent.goal_assessment),
            'needs_attention': recent.state_check.get('needs_attention', False)
        }