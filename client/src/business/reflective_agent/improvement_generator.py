"""
改进策略生成器 (ImprovementGenerator)

基于反思结果生成具体的改进策略
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from .reflection_engine import ReflectionResult
from .execution_plan import ExecutionPlan, PlanStep, StepPriority


@dataclass
class Improvement:
    """
    单个改进建议

    包含具体的改进操作
    """

    improvement_id: str
    description: str                          # 改进描述
    target_step_id: Optional[str] = None       # 目标步骤ID

    # 改进类型
    improvement_type: str = ""                # retry/replace/simplify/split/add_fallback

    # 优先级
    priority: int = 1                         # 1-5, 1是最高

    # 预期效果
    expected_impact: str = ""                  # 预期改进效果
    confidence: float = 0.5                     # 置信度 0.0-1.0

    # 执行信息
    action_plan: List[str] = field(default_factory=list)  # 具体操作步骤

    def to_dict(self) -> Dict[str, Any]:
        return {
            "improvement_id": self.improvement_id,
            "description": self.description,
            "target_step_id": self.target_step_id,
            "improvement_type": self.improvement_type,
            "priority": self.priority,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "action_plan": self.action_plan
        }


@dataclass
class ImprovementPlan:
    """
    改进计划

    包含多个改进建议
    """

    plan_id: str
    source_reflection: str                    # 来源反思结果ID

    # 改进列表
    improvements: List[Improvement] = field(default_factory=list)

    # 执行策略
    strategy: str = "incremental"             # incremental/aggressive/conservative
    max_changes: int = 5                      # 最大改动数量

    # 预估信息
    estimated_success_rate: float = 0.7      # 预估成功率
    estimated_risk: str = "medium"            # low/medium/high

    def add_improvement(self, improvement: Improvement):
        """添加改进"""
        if len(self.improvements) < self.max_changes:
            self.improvements.append(improvement)

    def get_sorted_improvements(self) -> List[Improvement]:
        """按优先级排序"""
        return sorted(self.improvements, key=lambda i: i.priority)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_reflection": self.source_reflection,
            "improvements": [i.to_dict() for i in self.improvements],
            "strategy": self.strategy,
            "max_changes": self.max_changes,
            "estimated_success_rate": self.estimated_success_rate,
            "estimated_risk": self.estimated_risk
        }


class ImprovementGenerator:
    """
    改进策略生成器

    基于反思结果生成具体的改进策略
    """

    # 改进策略模板
    STRATEGY_TEMPLATES = {
        "retry": {
            "description": "重试失败的步骤",
            "actions": [
                "记录失败信息",
                "调整执行参数",
                "执行重试",
                "验证结果"
            ]
        },
        "replace": {
            "description": "替换执行方法",
            "actions": [
                "分析失败原因",
                "寻找替代方案",
                "验证替代方案可行性",
                "执行替换"
            ]
        },
        "simplify": {
            "description": "简化任务",
            "actions": [
                "识别复杂环节",
                "移除非必要步骤",
                "合并相似步骤",
                "验证简化效果"
            ]
        },
        "split": {
            "description": "拆分任务",
            "actions": [
                "识别阻塞点",
                "设计拆分方案",
                "创建子任务",
                "逐个解决"
            ]
        },
        "add_fallback": {
            "description": "添加降级策略",
            "actions": [
                "识别风险点",
                "设计降级方案",
                "实现备用路径",
                "测试降级流程"
            ]
        },
        "decompose": {
            "description": "重新分解任务",
            "actions": [
                "重新分析任务目标",
                "设计新的分解方案",
                "优化步骤依赖",
                "验证新方案"
            ]
        }
    }

    def __init__(self):
        self.improvement_templates = self.STRATEGY_TEMPLATES.copy()

    def generate(
        self,
        reflection: ReflectionResult,
        original_plan: ExecutionPlan
    ) -> ImprovementPlan:
        """
        生成改进计划

        Args:
            reflection: 反思结果
            original_plan: 原始执行计划

        Returns:
            改进计划
        """
        plan = ImprovementPlan(
            plan_id=f"improvement_{original_plan.plan_id}",
            source_reflection=str(reflection.to_dict())[:100]
        )

        # 根据反思结果选择策略
        if reflection.improvement_strategy == "critical_fix_required":
            plan.strategy = "aggressive"
            plan.estimated_risk = "high"
            plan.estimated_success_rate = 0.6
        elif reflection.improvement_strategy == "high_priority_fixes":
            plan.strategy = "incremental"
            plan.estimated_risk = "medium"
            plan.estimated_success_rate = 0.75
        else:
            plan.strategy = "incremental"
            plan.estimated_risk = "low"
            plan.estimated_success_rate = 0.85

        # 基于问题生成改进
        for i, problem in enumerate(reflection.problems_found):
            improvements = self._generate_for_problem(
                problem,
                original_plan,
                i
            )
            for imp in improvements:
                plan.add_improvement(imp)

        # 基于反思建议生成改进
        for i, suggestion in enumerate(reflection.improvements):
            improvement = self._create_from_suggestion(
                suggestion,
                original_plan,
                len(reflection.problems_found) + i
            )
            plan.add_improvement(improvement)

        return plan

    def _generate_for_problem(
        self,
        problem: Dict[str, Any],
        plan: ExecutionPlan,
        index: int
    ) -> List[Improvement]:
        """针对单个问题生成改进"""
        improvements = []
        problem_type = problem.get("type", "")
        severity = problem.get("severity", "medium")

        # 优先级映射
        priority_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        priority = priority_map.get(severity, 3)

        # 根据问题类型生成改进
        if problem_type == "syntax_error":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="修正语法错误",
                improvement_type="replace",
                priority=priority,
                expected_impact="消除语法错误",
                confidence=0.9,
                action_plan=self.improvement_templates["replace"]["actions"]
            ))

        elif problem_type == "logic_error":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="重新设计逻辑流程",
                improvement_type="replace",
                priority=priority,
                expected_impact="修复逻辑缺陷",
                confidence=0.7,
                action_plan=self.improvement_templates["decompose"]["actions"]
            ))

        elif problem_type == "resource_error":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="优化资源使用",
                improvement_type="simplify",
                priority=priority,
                expected_impact="降低资源消耗",
                confidence=0.8,
                action_plan=self.improvement_templates["simplify"]["actions"]
            ))

        elif problem_type == "timeout_error":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="增加超时处理",
                improvement_type="add_fallback",
                priority=priority,
                expected_impact="提高超时容错能力",
                confidence=0.85,
                action_plan=self.improvement_templates["add_fallback"]["actions"]
            ))

        elif problem_type == "step_failure":
            step_name = problem.get("step_name", "unknown")
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description=f"重新设计步骤 '{step_name}'",
                target_step_id=problem.get("step_id"),
                improvement_type="replace",
                priority=priority,
                expected_impact="提高步骤成功率",
                confidence=0.65,
                action_plan=self.improvement_templates["decompose"]["actions"]
            ))

        elif problem_type == "low_completion_rate":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="简化执行计划",
                improvement_type="simplify",
                priority=priority,
                expected_impact="提高完成率",
                confidence=0.75,
                action_plan=self.improvement_templates["simplify"]["actions"]
            ))

        elif problem_type == "high_error_rate":
            improvements.append(Improvement(
                improvement_id=f"imp_{plan.plan_id}_{index}",
                description="增强错误处理",
                improvement_type="add_fallback",
                priority=priority,
                expected_impact="降低错误率",
                confidence=0.8,
                action_plan=self.improvement_templates["add_fallback"]["actions"]
            ))

        return improvements

    def _create_from_suggestion(
        self,
        suggestion: str,
        plan: ExecutionPlan,
        index: int
    ) -> Improvement:
        """从反思建议创建改进"""
        # 识别建议类型
        if "重试" in suggestion:
            imp_type = "retry"
        elif "替换" in suggestion or "重新" in suggestion:
            imp_type = "replace"
        elif "简化" in suggestion:
            imp_type = "simplify"
        elif "拆分" in suggestion or "分解" in suggestion:
            imp_type = "split"
        elif "降级" in suggestion or "备用" in suggestion:
            imp_type = "add_fallback"
        else:
            imp_type = "replace"

        template = self.improvement_templates.get(imp_type, {})

        return Improvement(
            improvement_id=f"imp_{plan.plan_id}_{index}",
            description=suggestion,
            improvement_type=imp_type,
            priority=3,
            expected_impact=template.get("description", ""),
            confidence=0.6,
            action_plan=template.get("actions", [])
        )

    def apply_improvements(
        self,
        plan: ExecutionPlan,
        improvements: List[Improvement]
    ) -> ExecutionPlan:
        """
        将改进应用到执行计划

        Args:
            plan: 原始计划
            improvements: 改进列表

        Returns:
            改进后的新计划
        """
        # 创建新计划
        new_plan = plan.create_corrected_plan(
            [imp.description for imp in improvements]
        )

        # 应用每个改进
        for improvement in improvements:
            new_plan = self._apply_single_improvement(
                new_plan,
                improvement
            )

        return new_plan

    def _apply_single_improvement(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用单个改进到计划"""
        if improvement.improvement_type == "simplify":
            return self._apply_simplify(plan, improvement)
        elif improvement.improvement_type == "split":
            return self._apply_split(plan, improvement)
        elif improvement.improvement_type == "add_fallback":
            return self._apply_add_fallback(plan, improvement)
        elif improvement.improvement_type == "replace":
            return self._apply_replace(plan, improvement)
        elif improvement.improvement_type == "retry":
            return self._apply_retry(plan, improvement)

        return plan

    def _apply_simplify(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用简化改进"""
        # 移除低优先级步骤
        new_steps = []
        for step in plan.steps:
            if step.priority.value <= StepPriority.MEDIUM.value:
                new_steps.append(step)
            else:
                # 记录被移除的步骤
                step.status = "skipped_by_improvement"

        plan.steps = new_steps
        return plan

    def _apply_split(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用拆分改进"""
        # 为复杂步骤添加标记
        for step in plan.steps:
            if step.step_id == improvement.target_step_id:
                step.params["needs_split"] = True
                step.timeout_ms *= 2

        return plan

    def _apply_add_fallback(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用降级策略"""
        # 为所有步骤添加降级参数
        for step in plan.steps:
            step.fallback_action = f"{step.action}_fallback"
            step.retry_on_failure = True
            step.max_retries = min(step.max_retries + 1, 3)

        return plan

    def _apply_replace(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用替换改进"""
        # 重置目标步骤状态
        for step in plan.steps:
            if step.step_id == improvement.target_step_id:
                step.status = "pending"
                step.attempt_count = 0
                step.last_error = None

        return plan

    def _apply_retry(
        self,
        plan: ExecutionPlan,
        improvement: Improvement
    ) -> ExecutionPlan:
        """应用重试改进"""
        # 增加重试次数
        for step in plan.steps:
            if step.step_id == improvement.target_step_id:
                step.retry_on_failure = True
                step.max_retries += 1
                step.timeout_ms = int(step.timeout_ms * 1.5)

        return plan
