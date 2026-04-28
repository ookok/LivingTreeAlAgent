"""
A-EVOLVE 独立测试

完全独立测试 A-EVOLVE 核心功能，不依赖项目其他模块
"""

import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


# 模拟必要的模型类
class SkillEvolutionStatus(Enum):
    SEED = "seed"
    GROWING = "growing"
    MATURED = "matured"
    ATROPHIED = "atrophied"
    MERGED = "merged"


@dataclass
class TaskSkill:
    skill_id: str
    name: str
    description: str
    trigger_patterns: List[str] = field(default_factory=list)
    execution_flow: List[Dict[str, Any]] = field(default_factory=list)
    tool_sequence: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    use_count: int = 0
    failed_count: int = 0
    avg_duration: float = 0.0
    total_duration: float = 0.0
    evolution_status: SkillEvolutionStatus = SkillEvolutionStatus.SEED
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


# 模拟数据库类
class MockDatabase:
    def __init__(self):
        self.skills = {}
    
    def get_skill(self, skill_id):
        return self.skills.get(skill_id)
    
    def update_skill(self, skill_id, updates):
        if skill_id in self.skills:
            skill = self.skills[skill_id]
            for key, value in updates.items():
                setattr(skill, key, value)
            return True
        return False
    
    def get_all_skills(self):
        return list(self.skills.values())
    
    def add_skill(self, skill):
        self.skills[skill.skill_id] = skill


# 复制 A-EVOLVE 核心代码
class EvolutionStrategyType(Enum):
    REINFORCEMENT = "reinforcement"
    GENETIC = "genetic"
    GRADIENT = "gradient"
    TARGETED = "targeted"
    SCALING = "scaling"
    OPEN_ENDED = "open_ended"
    MULTI_AGENT = "multi_agent"


class EvolutionGoal(Enum):
    SUCCESS_RATE = "success_rate"
    EFFICIENCY = "efficiency"
    ROBUSTNESS = "robustness"
    GENERALIZATION = "generalization"
    ADAPTABILITY = "adaptability"


class EvolutionStrategy:
    def __init__(self, strategy_type):
        self.strategy_type = strategy_type
        self.config = {}
    
    def evaluate_skill(self, skill):
        raise NotImplementedError
    
    def evolve_skill(self, skill, feedback):
        raise NotImplementedError
    
    def should_evolve(self, skill):
        raise NotImplementedError
    
    def get_name(self):
        return self.strategy_type.value


class TargetedEvolutionStrategy(EvolutionStrategy):
    def __init__(self):
        super().__init__(EvolutionStrategyType.TARGETED)
        self.goals = {
            EvolutionGoal.SUCCESS_RATE: 0.95,
            EvolutionGoal.EFFICIENCY: 0.8,
            EvolutionGoal.ROBUSTNESS: 0.85,
        }
    
    def evaluate_skill(self, skill):
        return {
            "success_rate": skill.success_rate,
            "efficiency": 1.0 / (skill.avg_duration + 1e-6),
            "robustness": 1.0 - (skill.failed_count / (skill.use_count + 1e-6)),
        }
    
    def evolve_skill(self, skill, feedback):
        metrics = self.evaluate_skill(skill)
        gaps = {}
        for goal, target in self.goals.items():
            current = metrics.get(goal.value, 0)
            gaps[goal] = target - current
        
        prioritized_goals = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        
        if prioritized_goals and prioritized_goals[0][1] > 0:
            primary_goal = prioritized_goals[0][0]
            if primary_goal == EvolutionGoal.SUCCESS_RATE:
                self._optimize_success_rate(skill, feedback)
            elif primary_goal == EvolutionGoal.EFFICIENCY:
                self._optimize_efficiency(skill, feedback)
            elif primary_goal == EvolutionGoal.ROBUSTNESS:
                self._optimize_robustness(skill, feedback)
        
        return skill
    
    def should_evolve(self, skill):
        metrics = self.evaluate_skill(skill)
        for goal, target in self.goals.items():
            if metrics.get(goal.value, 0) < target:
                return True
        return False
    
    def _optimize_success_rate(self, skill, feedback):
        error = feedback.get("error", "")
        if error:
            if "error_patterns" not in skill.metadata:
                skill.metadata["error_patterns"] = {}
            error_patterns = skill.metadata["error_patterns"]
            error_patterns[error] = error_patterns.get(error, 0) + 1
    
    def _optimize_efficiency(self, skill, feedback):
        if skill.execution_flow:
            slow_steps = [i for i, step in enumerate(skill.execution_flow) if step.get("duration", 0) > 5.0]
            for step_idx in slow_steps:
                step = skill.execution_flow[step_idx]
                step["needs_optimization"] = True
    
    def _optimize_robustness(self, skill, feedback):
        if skill.execution_flow:
            for step in skill.execution_flow:
                if "error_handling" not in step:
                    step["error_handling"] = True


class ScalingEvolutionStrategy(EvolutionStrategy):
    def __init__(self):
        super().__init__(EvolutionStrategyType.SCALING)
    
    def evaluate_skill(self, skill):
        return {
            "compute_efficiency": skill.success_rate / (skill.avg_duration + 1e-6),
        }
    
    def evolve_skill(self, skill, feedback):
        efficiency = self.evaluate_skill(skill)
        compute_efficiency = efficiency.get("compute_efficiency", 0)
        
        if compute_efficiency < 0.5:
            self._simplify_execution_flow(skill)
        elif compute_efficiency > 1.5:
            self._enhance_capabilities(skill)
        
        return skill
    
    def should_evolve(self, skill):
        efficiency = self.evaluate_skill(skill)
        compute_efficiency = efficiency.get("compute_efficiency", 0)
        return compute_efficiency < 0.3 or compute_efficiency > 2.0
    
    def _simplify_execution_flow(self, skill):
        if skill.execution_flow and len(skill.execution_flow) > 3:
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
    
    def _enhance_capabilities(self, skill):
        if skill.execution_flow:
            last_step = skill.execution_flow[-1]
            if "verification" not in last_step:
                last_step["verification"] = True


class OpenEndedEvolutionStrategy(EvolutionStrategy):
    def __init__(self):
        super().__init__(EvolutionStrategyType.OPEN_ENDED)
        self.exploration_rate = 0.3
    
    def evaluate_skill(self, skill):
        return {
            "adaptability": self._calculate_adaptability(skill),
            "innovation": self._calculate_innovation(skill),
            "diversity": self._calculate_diversity(skill),
        }
    
    def evolve_skill(self, skill, feedback):
        if random.random() < self.exploration_rate:
            self._explore_new_paths(skill, feedback)
        self._incorporate_feedback(skill, feedback)
        return skill
    
    def should_evolve(self, skill):
        return True
    
    def _calculate_adaptability(self, skill):
        if skill.use_count > 0:
            return skill.success_rate * min(1.0, skill.use_count / 10.0)
        return 0.0
    
    def _calculate_innovation(self, skill):
        if skill.execution_flow:
            return min(1.0, len(skill.execution_flow) / 10.0)
        return 0.0
    
    def _calculate_diversity(self, skill):
        if skill.tool_sequence:
            unique_tools = len(set(skill.tool_sequence))
            return min(1.0, unique_tools / len(skill.tool_sequence))
        return 0.0
    
    def _explore_new_paths(self, skill, feedback):
        if skill.execution_flow and len(skill.execution_flow) > 1:
            if random.random() < 0.5:
                idx1, idx2 = random.sample(range(len(skill.execution_flow)), 2)
                skill.execution_flow[idx1], skill.execution_flow[idx2] = \
                    skill.execution_flow[idx2], skill.execution_flow[idx1]
    
    def _incorporate_feedback(self, skill, feedback):
        if "feedback_history" not in skill.metadata:
            skill.metadata["feedback_history"] = []
        skill.metadata["feedback_history"].append({
            "timestamp": time.time(),
            "feedback": feedback,
        })


class EvolutionStrategyManager:
    def __init__(self, database):
        self.db = database
        self.strategies = {
            EvolutionStrategyType.TARGETED: TargetedEvolutionStrategy(),
            EvolutionStrategyType.SCALING: ScalingEvolutionStrategy(),
            EvolutionStrategyType.OPEN_ENDED: OpenEndedEvolutionStrategy(),
        }
    
    def select_strategy(self, skill):
        if skill.evolution_status == SkillEvolutionStatus.SEED:
            return self.strategies[EvolutionStrategyType.OPEN_ENDED]
        elif skill.evolution_status == SkillEvolutionStatus.GROWING:
            return self.strategies[EvolutionStrategyType.TARGETED]
        elif skill.evolution_status == SkillEvolutionStatus.MATURED:
            return self.strategies[EvolutionStrategyType.SCALING]
        else:
            return self.strategies[EvolutionStrategyType.TARGETED]
    
    def evolve_skill(self, skill_id, feedback):
        skill = self.db.get_skill(skill_id)
        if not skill:
            return False
        
        strategy = self.select_strategy(skill)
        if not strategy.should_evolve(skill):
            return False
        
        evolved_skill = strategy.evolve_skill(skill, feedback)
        
        updates = {
            "execution_flow": evolved_skill.execution_flow,
            "tool_sequence": evolved_skill.tool_sequence,
            "metadata": evolved_skill.metadata,
            "updated_at": time.time(),
        }
        
        return self.db.update_skill(skill_id, updates)
    
    def get_evolution_suggestions(self, skill):
        suggestions = []
        strategy = self.select_strategy(skill)
        metrics = strategy.evaluate_skill(skill)
        
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


class AEvolveConfig:
    def __init__(self, enabled=True, verbose=True, evolution_interval=3600):
        self.enabled = enabled
        self.verbose = verbose
        self.evolution_interval = evolution_interval


class AEvolveIntegrator:
    def __init__(self, database, config):
        self.db = database
        self.config = config
        self.strategy_manager = EvolutionStrategyManager(database)
    
    def evolve_skill(self, skill_id, feedback=None):
        if not self.config.enabled:
            return False
        feedback = feedback or {}
        return self.strategy_manager.evolve_skill(skill_id, feedback)
    
    def get_evolution_suggestions(self, skill):
        return self.strategy_manager.get_evolution_suggestions(skill)
    
    def optimize_resource_allocation(self):
        skills = self.db.get_all_skills()
        total_use = sum(skill.use_count for skill in skills)
        
        if total_use == 0:
            return {
                "compute": 0.5,
                "memory": 0.5,
                "time": 0.5,
            }
        
        active_skills = [s for s in skills if s.use_count > 0]
        if active_skills:
            resource_factor = min(1.0, total_use / 100.0)
        else:
            resource_factor = 0.3
        
        return {
            "compute": min(1.0, 0.3 + resource_factor * 0.7),
            "memory": min(1.0, 0.4 + resource_factor * 0.6),
            "time": min(1.0, 0.5 + resource_factor * 0.5),
        }
    
    def shutdown(self):
        pass


# 测试函数
def test_evolution_strategies():
    print("=== 测试进化策略 ===")
    
    # 创建测试技能
    test_skill = TaskSkill(
        skill_id="test_skill_1",
        name="测试技能",
        description="测试 A-EVOLVE 进化功能",
        trigger_patterns=["测试", "A-EVOLVE"],
        execution_flow=[
            {
                "phase": "execute",
                "tool": "file_read",
                "args": {"path": "."},
                "success": True,
                "duration": 0.5,
            },
        ],
        tool_sequence=["file_read"],
        success_rate=0.8,
        use_count=5,
        failed_count=1,
        avg_duration=0.5,
        total_duration=2.5,
        evolution_status=SkillEvolutionStatus.GROWING,
    )
    
    print(f"测试技能: {test_skill.name}")
    print(f"初始状态: {test_skill.evolution_status.value}")
    print(f"初始成功率: {test_skill.success_rate}")
    
    # 测试目标导向策略
    print("\n1. 目标导向策略:")
    targeted = TargetedEvolutionStrategy()
    metrics = targeted.evaluate_skill(test_skill)
    print(f"评估: {metrics}")
    
    feedback = {"success": True, "duration": 0.4}
    evolved = targeted.evolve_skill(test_skill, feedback)
    print(f"进化后执行流程: {len(evolved.execution_flow)} 步骤")
    print(f"需要进化: {targeted.should_evolve(evolved)}")
    
    # 测试进化缩放策略
    print("\n2. 进化缩放策略:")
    scaling = ScalingEvolutionStrategy()
    metrics = scaling.evaluate_skill(test_skill)
    print(f"资源效率: {metrics}")
    
    evolved = scaling.evolve_skill(test_skill, feedback)
    print(f"进化后工具序列: {evolved.tool_sequence}")
    print(f"需要进化: {scaling.should_evolve(evolved)}")
    
    # 测试开放适应策略
    print("\n3. 开放适应策略:")
    open_ended = OpenEndedEvolutionStrategy()
    metrics = open_ended.evaluate_skill(test_skill)
    print(f"适应能力: {metrics}")
    
    evolved = open_ended.evolve_skill(test_skill, feedback)
    print(f"需要进化: {open_ended.should_evolve(evolved)}")
    print(f"反馈历史: {len(evolved.metadata.get('feedback_history', []))}")


def test_strategy_manager():
    print("\n=== 测试策略管理器 ===")
    
    db = MockDatabase()
    manager = EvolutionStrategyManager(db)
    
    # 测试策略选择
    skill1 = TaskSkill(
        skill_id="skill_1",
        name="种子技能",
        description="种子状态技能",
        evolution_status=SkillEvolutionStatus.SEED,
    )
    strategy = manager.select_strategy(skill1)
    print(f"种子状态选择策略: {strategy.get_name()}")
    
    skill2 = TaskSkill(
        skill_id="skill_2",
        name="成长技能",
        description="成长状态技能",
        evolution_status=SkillEvolutionStatus.GROWING,
    )
    strategy = manager.select_strategy(skill2)
    print(f"成长状态选择策略: {strategy.get_name()}")
    
    skill3 = TaskSkill(
        skill_id="skill_3",
        name="成熟技能",
        description="成熟状态技能",
        evolution_status=SkillEvolutionStatus.MATURED,
    )
    strategy = manager.select_strategy(skill3)
    print(f"成熟状态选择策略: {strategy.get_name()}")
    
    # 测试进化建议
    suggestions = manager.get_evolution_suggestions(skill2)
    print("\n进化建议:")
    for suggestion in suggestions:
        print(f"  - {suggestion['message']} (优先级: {suggestion['priority']})")


def test_a_evolve_integration():
    print("\n=== 测试 A-EVOLVE 集成 ===")
    
    db = MockDatabase()
    config = AEvolveConfig(enabled=True, verbose=True)
    integrator = AEvolveIntegrator(db, config)
    
    # 添加测试技能
    test_skill = TaskSkill(
        skill_id="test_integration",
        name="集成测试技能",
        description="测试 A-EVOLVE 集成",
        evolution_status=SkillEvolutionStatus.GROWING,
    )
    db.add_skill(test_skill)
    
    # 测试进化
    feedback = {"success": True, "duration": 1.0}
    success = integrator.evolve_skill("test_integration", feedback)
    print(f"进化结果: {'成功' if success else '失败'}")
    
    # 测试资源优化
    allocation = integrator.optimize_resource_allocation()
    print(f"资源分配: {allocation}")
    
    # 测试进化建议
    suggestions = integrator.get_evolution_suggestions(test_skill)
    print("\n进化建议:")
    for suggestion in suggestions:
        print(f"  - {suggestion['message']} (优先级: {suggestion['priority']})")
    
    integrator.shutdown()
    print("集成测试完成")


if __name__ == "__main__":
    print("A-EVOLVE 独立测试开始")
    
    try:
        test_evolution_strategies()
        test_strategy_manager()
        test_a_evolve_integration()
        print("\n✅ 所有测试通过!")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
