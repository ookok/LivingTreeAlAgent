"""
进化策略管理系统

实现 A-EVOLVE 框架的核心理念：
- 部署时进化 (Deployment-time evolution)
- 目标导向优化 (Goal-directed optimization)
- 进化缩放 (Evolution-scaling)
- 持续开放适应 (Open-ended adaptation)

管理不同类型的进化策略，支持技能的自主进化
"""

import time
import threading
import random
from typing import List, Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..models import (
    TaskSkill,
    SkillEvolutionStatus,
    ExecutionRecord,
    TaskContext,
)
from ..database import EvolutionDatabase


# ============ 进化策略类型 ============

class EvolutionStrategyType(Enum):
    """进化策略类型"""
    
    # 基础策略
    REINFORCEMENT = "reinforcement"  # 强化学习
    GENETIC = "genetic"            # 遗传算法
    GRADIENT = "gradient"          # 梯度优化
    
    # 高级策略（A-EVOLVE 启发）
    TARGETED = "targeted"          # 目标导向进化
    SCALING = "scaling"            # 进化缩放
    OPEN_ENDED = "open_ended"      # 开放适应
    MULTI_AGENT = "multi_agent"    # 多智能体协同进化


class EvolutionGoal(Enum):
    """进化目标"""
    
    SUCCESS_RATE = "success_rate"    # 成功率
    EFFICIENCY = "efficiency"       # 执行效率
    ROBUSTNESS = "robustness"       # 鲁棒性
    GENERALIZATION = "generalization"  # 泛化能力
    ADAPTABILITY = "adaptability"     # 适应能力


# ============ 进化策略基类 ============

class EvolutionStrategy:
    """
    进化策略基类
    
    所有进化策略都继承自此类，实现特定的进化逻辑
    """
    
    def __init__(self, strategy_type: EvolutionStrategyType):
        self.strategy_type = strategy_type
        self.config = {}
        self.metrics = {}
        self._lock = threading.RLock()
    
    def initialize(self, config: Dict[str, Any]):
        """初始化策略"""
        self.config.update(config)
    
    def evaluate_skill(self, skill: TaskSkill) -> Dict[str, float]:
        """
        评估技能
        
        Returns:
            Dict: 评估指标
        """
        raise NotImplementedError
    
    def evolve_skill(self, skill: TaskSkill, feedback: Dict[str, Any]) -> TaskSkill:
        """
        执行进化
        
        Returns:
            TaskSkill: 进化后的技能
        """
        raise NotImplementedError
    
    def should_evolve(self, skill: TaskSkill) -> bool:
        """
        判断是否需要进化
        
        Returns:
            bool: 是否需要进化
        """
        raise NotImplementedError
    
    def get_name(self) -> str:
        """获取策略名称"""
        return self.strategy_type.value


# ============ 具体进化策略实现 ============

class TargetedEvolutionStrategy(EvolutionStrategy):
    """
    目标导向进化策略
    
    A-EVOLVE 核心策略：以明确的目标为导向进行进化
    """
    
    def __init__(self):
        super().__init__(EvolutionStrategyType.TARGETED)
        self.goals = {
            EvolutionGoal.SUCCESS_RATE: 0.95,
            EvolutionGoal.EFFICIENCY: 0.8,
            EvolutionGoal.ROBUSTNESS: 0.85,
        }
    
    def evaluate_skill(self, skill: TaskSkill) -> Dict[str, float]:
        """评估技能"""
        metrics = {
            "success_rate": skill.success_rate,
            "efficiency": 1.0 / (skill.avg_duration + 1e-6),
            "robustness": 1.0 - (skill.failed_count / (skill.use_count + 1e-6)),
        }
        return metrics
    
    def evolve_skill(self, skill: TaskSkill, feedback: Dict[str, Any]) -> TaskSkill:
        """执行目标导向进化"""
        metrics = self.evaluate_skill(skill)
        
        # 分析当前状态与目标的差距
        gaps = {}
        for goal, target in self.goals.items():
            current = metrics.get(goal.value, 0)
            gaps[goal] = target - current
        
        # 优先级排序（差距最大的优先）
        prioritized_goals = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        
        # 针对优先级最高的目标进行优化
        if prioritized_goals and prioritized_goals[0][1] > 0:
            primary_goal = prioritized_goals[0][0]
            
            # 根据目标类型执行不同的优化策略
            if primary_goal == EvolutionGoal.SUCCESS_RATE:
                # 优化执行流程
                self._optimize_success_rate(skill, feedback)
            elif primary_goal == EvolutionGoal.EFFICIENCY:
                # 优化执行效率
                self._optimize_efficiency(skill, feedback)
            elif primary_goal == EvolutionGoal.ROBUSTNESS:
                # 增强鲁棒性
                self._optimize_robustness(skill, feedback)
        
        return skill
    
    def should_evolve(self, skill: TaskSkill) -> bool:
        """判断是否需要进化"""
        metrics = self.evaluate_skill(skill)
        
        # 检查是否有目标未达成
        for goal, target in self.goals.items():
            if metrics.get(goal.value, 0) < target:
                return True
        
        return False
    
    def _optimize_success_rate(self, skill: TaskSkill, feedback: Dict[str, Any]):
        """优化成功率"""
        # 分析失败模式
        error = feedback.get("error", "")
        if error:
            # 记录错误模式
            if "error_patterns" not in skill.metadata:
                skill.metadata["error_patterns"] = {}
            error_patterns = skill.metadata["error_patterns"]
            error_patterns[error] = error_patterns.get(error, 0) + 1
        
        # 优化执行流程
        if skill.execution_flow:
            # 识别失败步骤
            failed_steps = [i for i, step in enumerate(skill.execution_flow) if not step.get("success", True)]
            if failed_steps:
                # 针对失败步骤进行优化
                for step_idx in failed_steps:
                    step = skill.execution_flow[step_idx]
                    # 添加错误处理
                    if "error_handling" not in step:
                        step["error_handling"] = True
    
    def _optimize_efficiency(self, skill: TaskSkill, feedback: Dict[str, Any]):
        """优化执行效率"""
        # 分析执行时间
        if skill.execution_flow:
            # 识别耗时步骤
            slow_steps = [i for i, step in enumerate(skill.execution_flow) if step.get("duration", 0) > 5.0]
            if slow_steps:
                # 优化耗时步骤
                for step_idx in slow_steps:
                    step = skill.execution_flow[step_idx]
                    # 标记为需要优化
                    step["needs_optimization"] = True
    
    def _optimize_robustness(self, skill: TaskSkill, feedback: Dict[str, Any]):
        """增强鲁棒性"""
        # 添加错误处理机制
        if skill.execution_flow:
            for step in skill.execution_flow:
                if "error_handling" not in step:
                    step["error_handling"] = True


class ScalingEvolutionStrategy(EvolutionStrategy):
    """
    进化缩放策略
    
    A-EVOLVE 核心策略：计算资源与进化能力的动态平衡
    """
    
    def __init__(self):
        super().__init__(EvolutionStrategyType.SCALING)
        self.resource_budget = {
            "compute": 1.0,  # 计算资源预算
            "memory": 1.0,   # 内存资源预算
            "time": 1.0,     # 时间资源预算
        }
    
    def evaluate_skill(self, skill: TaskSkill) -> Dict[str, float]:
        """评估技能"""
        # 计算资源使用效率
        resource_efficiency = {
            "compute_efficiency": skill.success_rate / (skill.avg_duration + 1e-6),
            "memory_efficiency": 1.0,  # 简化计算
            "time_efficiency": 1.0 / (skill.avg_duration + 1e-6),
        }
        return resource_efficiency
    
    def evolve_skill(self, skill: TaskSkill, feedback: Dict[str, Any]) -> TaskSkill:
        """执行进化缩放"""
        # 分析资源使用情况
        efficiency = self.evaluate_skill(skill)
        
        # 根据资源效率调整进化策略
        compute_efficiency = efficiency.get("compute_efficiency", 0)
        
        if compute_efficiency < 0.5:
            # 低效率：简化执行流程
            self._simplify_execution_flow(skill)
        elif compute_efficiency > 1.5:
            # 高效率：增强能力
            self._enhance_capabilities(skill)
        
        return skill
    
    def should_evolve(self, skill: TaskSkill) -> bool:
        """判断是否需要进化"""
        efficiency = self.evaluate_skill(skill)
        compute_efficiency = efficiency.get("compute_efficiency", 0)
        
        # 效率过低或过高都需要进化
        return compute_efficiency < 0.3 or compute_efficiency > 2.0
    
    def _simplify_execution_flow(self, skill: TaskSkill):
        """简化执行流程"""
        if skill.execution_flow and len(skill.execution_flow) > 3:
            # 移除冗余步骤
            simplified = []
            seen_tools = set()
            
            for step in skill.execution_flow:
                tool = step.get("tool")
                if tool and tool not in seen_tools:
                    simplified.append(step)
                    seen_tools.add(tool)
            
            if simplified:
                skill.execution_flow = simplified
                skill.tool_sequence = [step.get("tool") for step in simplified if step.get("tool")]
    
    def _enhance_capabilities(self, skill: TaskSkill):
        """增强能力"""
        # 添加更多功能或优化现有步骤
        if skill.execution_flow:
            # 为最后一步添加验证机制
            last_step = skill.execution_flow[-1]
            if "verification" not in last_step:
                last_step["verification"] = True


class OpenEndedEvolutionStrategy(EvolutionStrategy):
    """
    开放适应策略
    
    A-EVOLVE 核心策略：持续开放的能力提升
    """
    
    def __init__(self):
        super().__init__(EvolutionStrategyType.OPEN_ENDED)
        self.exploration_rate = 0.3  # 探索率
    
    def evaluate_skill(self, skill: TaskSkill) -> Dict[str, float]:
        """评估技能"""
        metrics = {
            "adaptability": self._calculate_adaptability(skill),
            "innovation": self._calculate_innovation(skill),
            "diversity": self._calculate_diversity(skill),
        }
        return metrics
    
    def evolve_skill(self, skill: TaskSkill, feedback: Dict[str, Any]) -> TaskSkill:
        """执行开放适应进化"""
        # 随机探索新的执行路径
        if random.random() < self.exploration_rate:
            self._explore_new_paths(skill, feedback)
        
        # 整合反馈
        self._incorporate_feedback(skill, feedback)
        
        return skill
    
    def should_evolve(self, skill: TaskSkill) -> bool:
        """判断是否需要进化"""
        # 持续进化，总是返回 True
        return True
    
    def _calculate_adaptability(self, skill: TaskSkill) -> float:
        """计算适应能力"""
        # 基于使用次数和成功率
        if skill.use_count > 0:
            return skill.success_rate * min(1.0, skill.use_count / 10.0)
        return 0.0
    
    def _calculate_innovation(self, skill: TaskSkill) -> float:
        """计算创新能力"""
        # 基于执行流程的复杂度
        if skill.execution_flow:
            return min(1.0, len(skill.execution_flow) / 10.0)
        return 0.0
    
    def _calculate_diversity(self, skill: TaskSkill) -> float:
        """计算多样性"""
        # 基于工具使用的多样性
        if skill.tool_sequence:
            unique_tools = len(set(skill.tool_sequence))
            return min(1.0, unique_tools / len(skill.tool_sequence))
        return 0.0
    
    def _explore_new_paths(self, skill: TaskSkill, feedback: Dict[str, Any]):
        """探索新路径"""
        # 随机修改执行流程
        if skill.execution_flow and len(skill.execution_flow) > 1:
            # 随机交换两个步骤
            if random.random() < 0.5:
                idx1, idx2 = random.sample(range(len(skill.execution_flow)), 2)
                skill.execution_flow[idx1], skill.execution_flow[idx2] = \
                    skill.execution_flow[idx2], skill.execution_flow[idx1]
    
    def _incorporate_feedback(self, skill: TaskSkill, feedback: Dict[str, Any]):
        """整合反馈"""
        # 记录反馈
        if "feedback_history" not in skill.metadata:
            skill.metadata["feedback_history"] = []
        skill.metadata["feedback_history"].append({
            "timestamp": time.time(),
            "feedback": feedback,
        })


# ============ 进化策略管理器 ============

class EvolutionStrategyManager:
    """
    进化策略管理器
    
    管理不同类型的进化策略，根据技能状态选择合适的策略
    """
    
    def __init__(self, database: EvolutionDatabase):
        self.db = database
        self.strategies = {
            EvolutionStrategyType.TARGETED: TargetedEvolutionStrategy(),
            EvolutionStrategyType.SCALING: ScalingEvolutionStrategy(),
            EvolutionStrategyType.OPEN_ENDED: OpenEndedEvolutionStrategy(),
        }
        self._lock = threading.RLock()
    
    def get_strategy(self, strategy_type: EvolutionStrategyType) -> Optional[EvolutionStrategy]:
        """获取指定策略"""
        return self.strategies.get(strategy_type)
    
    def select_strategy(self, skill: TaskSkill) -> EvolutionStrategy:
        """
        为技能选择合适的进化策略
        
        根据技能状态和需求自动选择策略
        """
        # 基于技能状态选择策略
        if skill.evolution_status == SkillEvolutionStatus.SEED:
            # 种子状态：开放适应策略
            return self.strategies[EvolutionStrategyType.OPEN_ENDED]
        elif skill.evolution_status == SkillEvolutionStatus.GROWING:
            # 成长状态：目标导向策略
            return self.strategies[EvolutionStrategyType.TARGETED]
        elif skill.evolution_status == SkillEvolutionStatus.MATURED:
            # 成熟状态：进化缩放策略
            return self.strategies[EvolutionStrategyType.SCALING]
        else:
            # 其他状态：默认使用目标导向策略
            return self.strategies[EvolutionStrategyType.TARGETED]
    
    def evolve_skill(self, skill_id: str, feedback: Dict[str, Any]) -> bool:
        """
        执行技能进化
        
        Args:
            skill_id: 技能 ID
            feedback: 反馈数据
            
        Returns:
            bool: 是否成功进化
        """
        with self._lock:
            skill = self.db.get_skill(skill_id)
            if not skill:
                return False
            
            # 选择策略
            strategy = self.select_strategy(skill)
            
            # 检查是否需要进化
            if not strategy.should_evolve(skill):
                return False
            
            # 执行进化
            evolved_skill = strategy.evolve_skill(skill, feedback)
            
            # 更新技能
            updates = {
                "execution_flow": evolved_skill.execution_flow,
                "tool_sequence": evolved_skill.tool_sequence,
                "metadata": evolved_skill.metadata,
                "updated_at": time.time(),
            }
            
            return self.db.update_skill(skill_id, updates)
    
    def batch_evolve_skills(self, skill_ids: List[str], feedback: Dict[str, Any]) -> Dict[str, bool]:
        """
        批量进化技能
        
        Returns:
            Dict: 技能 ID -> 进化结果
        """
        results = {}
        for skill_id in skill_ids:
            results[skill_id] = self.evolve_skill(skill_id, feedback)
        return results
    
    def get_evolution_suggestions(self, skill: TaskSkill) -> List[Dict[str, Any]]:
        """
        获取进化建议
        
        Returns:
            List: 进化建议列表
        """
        suggestions = []
        strategy = self.select_strategy(skill)
        metrics = strategy.evaluate_skill(skill)
        
        # 基于评估指标生成建议
        if metrics.get("success_rate", 0) < 0.8:
            suggestions.append({
                "type": "success_rate",
                "message": "建议优化执行流程以提高成功率",
                "priority": "high",
            })
        
        if metrics.get("efficiency", 0) < 0.6:
            suggestions.append({
                "type": "efficiency",
                "message": "建议简化执行流程以提高效率",
                "priority": "medium",
            })
        
        if metrics.get("adaptability", 0) < 0.5:
            suggestions.append({
                "type": "adaptability",
                "message": "建议增加执行路径以提高适应能力",
                "priority": "low",
            })
        
        return suggestions


# ============ 进化监控器 ============

class EvolutionMonitor:
    """
    进化监控器
    
    监控进化过程，提供统计和分析
    """
    
    def __init__(self, database: EvolutionDatabase):
        self.db = database
        self.metrics_history = {}
    
    def record_evolution(self, skill_id: str, strategy: str, metrics: Dict[str, float]):
        """记录进化过程"""
        if skill_id not in self.metrics_history:
            self.metrics_history[skill_id] = []
        
        self.metrics_history[skill_id].append({
            "timestamp": time.time(),
            "strategy": strategy,
            "metrics": metrics,
        })
    
    def get_evolution_trend(self, skill_id: str) -> Dict[str, List[float]]:
        """获取进化趋势"""
        history = self.metrics_history.get(skill_id, [])
        trends = {}
        
        for record in history:
            for metric, value in record["metrics"].items():
                if metric not in trends:
                    trends[metric] = []
                trends[metric].append(value)
        
        return trends
    
    def get_skill_health_score(self, skill: TaskSkill) -> float:
        """计算技能健康分数"""
        metrics = {
            "success_rate": skill.success_rate,
            "efficiency": 1.0 / (skill.avg_duration + 1e-6),
            "activity": min(1.0, skill.use_count / 10.0),
        }
        
        weights = {
            "success_rate": 0.5,
            "efficiency": 0.3,
            "activity": 0.2,
        }
        
        score = 0.0
        for metric, weight in weights.items():
            score += metrics.get(metric, 0) * weight
        
        return score
