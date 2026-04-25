"""
深度反思引擎 (ReflectionEngine)

分析执行结果，生成反思报告
"""

import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .execution_result import (
    ExecutionResult, ExecutionStep, ExecutionStatus, ErrorCategory
)
from .execution_plan import ExecutionPlan


@dataclass
class ReflectionResult:
    """
    反思结果

    包含深度分析的结果
    """

    reflection_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 是否成功
    success: bool = False

    # 问题分析
    problems_found: List[Dict[str, Any]] = field(default_factory=list)

    # 反思总结
    summary: str = ""

    # 改进建议
    improvements: List[str] = field(default_factory=list)

    # 质量评估
    quality_score: float = 0.0

    # 策略建议
    improvement_strategy: str = ""  # no_fix_needed / critical_fix_required / high_priority_fixes / optional_improvements

    # 信心指数
    confidence: float = 0.0

    # 反思时间
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "success": self.success,
            "problems_found": self.problems_found,
            "summary": self.summary,
            "improvements": self.improvements,
            "quality_score": self.quality_score,
            "improvement_strategy": self.improvement_strategy,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


class ReflectionEngine:
    """
    深度反思引擎

    分析执行结果，识别问题，生成改进建议

    反思维度：
    1. 执行质量分析
    2. 错误模式识别
    3. 效率评估
    4. 改进策略生成
    """

    def __init__(self):
        self.reflection_count = 0

    def reflect(
        self,
        result: ExecutionResult,
        plan: ExecutionPlan
    ) -> ReflectionResult:
        """
        深度反思

        Args:
            result: 执行结果
            plan: 执行计划

        Returns:
            反思结果
        """
        self.reflection_count += 1

        # 1. 分析执行质量
        quality_analysis = self._analyze_quality(result)

        # 2. 识别问题模式
        problems = self._identify_problems(result, plan)

        # 3. 评估效率
        efficiency = self._evaluate_efficiency(result)

        # 4. 生成改进建议
        improvements = self._generate_improvements(result, problems, efficiency)

        # 5. 确定改进策略
        strategy = self._determine_strategy(result, quality_analysis, problems)

        # 6. 计算总体质量分数
        quality_score = self._calculate_quality_score(result, quality_analysis)

        # 7. 判断是否成功（基于实际执行质量，而非 result.success）
        # 成功条件：完成率100% 且 无错误 且 质量分数足够高
        is_actually_successful = (
            result.completion_rate >= 1.0 and
            result.error_rate == 0 and
            len(problems) == 0
        )

        # 构建反思结果
        reflection = ReflectionResult(
            reflection_id=str(uuid.uuid4()),
            success=is_actually_successful,
            problems_found=problems,
            summary=self._build_summary(result, problems, improvements),
            improvements=improvements,
            quality_score=quality_score,
            improvement_strategy=strategy,
            confidence=self._calculate_confidence(result, problems)
        )

        return reflection

    def _analyze_quality(self, result: ExecutionResult) -> Dict[str, Any]:
        """分析执行质量"""
        # 完成率
        completion_rate = result.completion_rate

        # 错误率
        error_rate = result.error_rate

        # 步骤成功率
        step_success_rate = 0.0
        if result.metrics.total_steps > 0:
            step_success_rate = result.metrics.completed_steps / result.metrics.total_steps

        return {
            "completion_rate": completion_rate,
            "error_rate": error_rate,
            "step_success_rate": step_success_rate,
            "has_errors": len(result.errors) > 0,
            "error_count": len(result.errors)
        }

    def _identify_problems(
        self,
        result: ExecutionResult,
        plan: ExecutionPlan
    ) -> List[Dict[str, Any]]:
        """识别问题模式"""
        problems = []

        # 检查失败步骤
        for step in result.steps:
            if step.status == ExecutionStatus.FAILED:
                problems.append({
                    "type": "step_failure",
                    "severity": "high",
                    "step_id": step.step_id,
                    "step_name": step.name,
                    "error": step.error,
                    "description": f"步骤 '{step.name}' 执行失败: {step.error}"
                })

            elif step.status == ExecutionStatus.TIMEOUT:
                problems.append({
                    "type": "timeout_error",
                    "severity": "high",
                    "step_id": step.step_id,
                    "step_name": step.name,
                    "description": f"步骤 '{step.name}' 执行超时"
                })

        # 检查错误类型
        error_types = {}
        for error in result.errors:
            cat = error.category.value
            error_types[cat] = error_types.get(cat, 0) + 1

        for error_type, count in error_types.items():
            if count >= 2:
                problems.append({
                    "type": error_type,
                    "severity": "medium",
                    "count": count,
                    "description": f"发现 {count} 个 {error_type} 错误"
                })

        # 检查完成率
        if result.completion_rate < 0.5:
            problems.append({
                "type": "low_completion_rate",
                "severity": "critical",
                "completion_rate": result.completion_rate,
                "description": f"完成率过低: {result.completion_rate:.1%}"
            })

        # 检查错误率
        if result.error_rate > 0.3:
            problems.append({
                "type": "high_error_rate",
                "severity": "high",
                "error_rate": result.error_rate,
                "description": f"错误率过高: {result.error_rate:.1%}"
            })

        # 检查尝试次数
        if result.attempt_number > 2:
            problems.append({
                "type": "multiple_attempts",
                "severity": "low",
                "attempts": result.attempt_number,
                "description": f"执行了 {result.attempt_number} 次尝试"
            })

        return problems

    def _evaluate_efficiency(self, result: ExecutionResult) -> Dict[str, Any]:
        """评估效率"""
        # 计算平均步骤执行时间
        avg_step_time = 0.0
        if result.metrics.total_steps > 0:
            avg_step_time = result.metrics.total_duration_ms / result.metrics.total_steps

        return {
            "total_duration_ms": result.metrics.total_duration_ms,
            "avg_step_time_ms": avg_step_time,
            "steps_count": result.metrics.total_steps,
            "efficiency_score": self._calculate_efficiency_score(result)
        }

    def _calculate_efficiency_score(self, result: ExecutionResult) -> float:
        """计算效率分数"""
        if result.metrics.total_steps == 0:
            return 0.0

        # 基础分数：完成率
        base_score = result.completion_rate * 0.5

        # 惩罚：错误率
        error_penalty = min(result.error_rate * 0.3, 0.3)

        # 惩罚：超时
        timeout_penalty = 0.0
        for step in result.steps:
            if step.status == ExecutionStatus.TIMEOUT:
                timeout_penalty += 0.1

        return max(base_score - error_penalty - timeout_penalty, 0.0)

    def _generate_improvements(
        self,
        result: ExecutionResult,
        problems: List[Dict[str, Any]],
        efficiency: Dict[str, Any]
    ) -> List[str]:
        """生成改进建议"""
        improvements = []

        # 基于问题生成建议
        for problem in problems:
            ptype = problem.get("type", "")

            if ptype == "step_failure":
                improvements.append(f"重新设计步骤 '{problem.get('step_name', '')}' 的执行逻辑")

            elif ptype == "timeout_error":
                improvements.append("增加执行超时时间或优化执行效率")

            elif ptype == "syntax_error":
                improvements.append("修正语法错误")

            elif ptype == "logic_error":
                improvements.append("重新分析任务逻辑")

            elif ptype == "resource_error":
                improvements.append("优化资源使用策略")

            elif ptype == "low_completion_rate":
                improvements.append("简化任务分解或增加步骤优先级")

            elif ptype == "high_error_rate":
                improvements.append("增强错误处理机制")

            elif ptype == "multiple_attempts":
                improvements.append("优化任务规划，减少尝试次数")

        # 基于效率生成建议
        if efficiency.get("efficiency_score", 1.0) < 0.7:
            if efficiency.get("avg_step_time_ms", 0) > 5000:
                improvements.append("优化步骤执行时间")

        # 去重
        seen = set()
        unique_improvements = []
        for imp in improvements:
            if imp not in seen:
                seen.add(imp)
                unique_improvements.append(imp)

        return unique_improvements

    def _determine_strategy(
        self,
        result: ExecutionResult,
        quality: Dict[str, Any],
        problems: List[Dict[str, Any]]
    ) -> str:
        """确定改进策略"""
        # 检查实际执行质量（而非依赖 result.success）
        completion_rate = result.completion_rate
        error_rate = result.error_rate

        # 无问题
        if len(problems) == 0 and completion_rate >= 1.0:
            return "no_fix_needed"

        # 严重问题
        has_critical = any(p.get("severity") == "critical" for p in problems)
        if has_critical:
            return "critical_fix_required"

        # 高优先级问题
        has_high = any(p.get("severity") == "high" for p in problems)
        if has_high:
            return "high_priority_fixes"

        # 可选改进
        if len(problems) > 0:
            return "optional_improvements"

        # 基于质量判断
        if completion_rate >= 1.0 and error_rate == 0:
            return "no_fix_needed"
        elif completion_rate >= 0.8:
            return "optional_improvements"
        elif completion_rate >= 0.5:
            return "high_priority_fixes"
        else:
            return "critical_fix_required"

    def _calculate_quality_score(
        self,
        result: ExecutionResult,
        quality: Dict[str, Any]
    ) -> float:
        """计算质量分数"""
        # 完成率权重
        completion_weight = 0.4
        completion_score = result.completion_rate * completion_weight

        # 步骤成功率权重
        step_weight = 0.3
        step_score = quality.get("step_success_rate", 0) * step_weight

        # 错误率权重（反向）
        error_weight = 0.3
        error_score = (1 - quality.get("error_rate", 0)) * error_weight

        return completion_score + step_score + error_score

    def _calculate_confidence(
        self,
        result: ExecutionResult,
        problems: List[Dict[str, Any]]
    ) -> float:
        """计算反思信心指数"""
        # 基础信心
        confidence = 0.8

        # 问题越多，信心越低
        if len(problems) > 3:
            confidence -= 0.2
        elif len(problems) > 0:
            confidence -= 0.1

        # 尝试次数越多，信心越低
        if result.attempt_number > 2:
            confidence -= 0.1

        return max(confidence, 0.0)

    def _build_summary(
        self,
        result: ExecutionResult,
        problems: List[Dict[str, Any]],
        improvements: List[str]
    ) -> str:
        """构建反思总结"""
        parts = []

        # 执行状态
        if result.success:
            parts.append("任务执行成功")
        else:
            parts.append("任务执行存在问题")

        # 问题总结
        if problems:
            problem_types = set(p.get("type", "") for p in problems)
            parts.append(f"发现 {len(problems)} 个问题: {', '.join(problem_types)}")

        # 改进建议
        if improvements:
            parts.append(f"建议: {'; '.join(improvements[:3])}")

        return ". ".join(parts)
