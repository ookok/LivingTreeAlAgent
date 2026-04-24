"""
技能质量评分系统 - Skill Quality Scorer
=========================================

核心功能：
1. 多维度质量评估（效率、质量、稳定性、可靠性）
2. 动态权重调整
3. 历史评分追踪
4. 质量趋势分析

复用模块：
- TaskSkill (技能数据模型)
- ExecutionRecord (执行记录)
- EvolutionDatabase (技能数据库)

Author: Hermes Desktop Team
"""

import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from core.skill_evolution.models import TaskSkill, ExecutionRecord, SkillEvolutionStatus

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """质量维度枚举"""
    EFFICIENCY = "efficiency"      # 执行效率
    QUALITY = "quality"           # 执行质量
    STABILITY = "stability"       # 稳定性
    RELIABILITY = "reliability"   # 可靠性
    COMPLEXITY = "complexity"     # 复杂度适配


@dataclass
class QualityScore:
    """质量评分"""
    dimension: QualityDimension
    score: float           # 0-100 分制
    weight: float          # 权重 (0-1)
    reason: str = ""       # 打分原因
    details: Dict = field(default_factory=dict)

    def __post_init__(self):
        # 确保分数在 0-100 范围内
        self.score = max(0.0, min(100.0, self.score))
        self.weight = max(0.0, min(1.0, self.weight))

    def to_dict(self) -> Dict:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": round(self.weight, 2),
            "reason": self.reason,
            "details": self.details
        }


@dataclass
class SkillQualityReport:
    """技能质量报告"""
    skill_id: str
    skill_name: str
    
    # 各维度评分
    efficiency_score: QualityScore
    quality_score: QualityScore
    stability_score: QualityScore
    reliability_score: QualityScore
    complexity_score: QualityScore
    
    # 综合评分
    overall_score: float = 0.0
    weighted_score: float = 0.0
    
    # 排名
    rank: int = 0           # 在同类技能中的排名
    percentile: float = 0.0 # 百分位
    
    # 趋势分析
    trend: str = "stable"   # improving / declining / stable
    trend_change: float = 0.0  # 相比上次的评分变化
    
    # 历史记录
    score_history: List[Dict] = field(default_factory=list)
    recent_executions: List[Dict] = field(default_factory=list)
    
    # 时间戳
    evaluated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "efficiency_score": self.efficiency_score.to_dict(),
            "quality_score": self.quality_score.to_dict(),
            "stability_score": self.stability_score.to_dict(),
            "reliability_score": self.reliability_score.to_dict(),
            "complexity_score": self.complexity_score.to_dict(),
            "overall_score": round(self.overall_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "rank": self.rank,
            "percentile": round(self.percentile, 2),
            "trend": self.trend,
            "trend_change": round(self.trend_change, 2),
            "score_history": self.score_history,
            "recent_executions": self.recent_executions[-10:],
            "evaluated_at": self.evaluated_at
        }


class SkillQualityScorer:
    """
    技能质量评分器
    
    多维度评估技能质量：
    1. 效率评分 - 执行时长是否合理
    2. 质量评分 - 执行步骤成功率
    3. 稳定性评分 - 多次执行结果的一致性
    4. 可靠性评分 - 长期表现的稳定性
    5. 复杂度适配 - 是否适配任务复杂度
    
    使用示例：
    ```python
    scorer = SkillQualityScorer()
    
    # 评估单个技能
    report = scorer.evaluate_skill(skill)
    print(f"综合评分: {report.weighted_score}")
    
    # 批量评估
    reports = scorer.batch_evaluate(skills)
    
    # 获取质量排名
    ranking = scorer.get_quality_ranking(reports)
    ```
    """
    
    # 默认权重配置
    DEFAULT_WEIGHTS = {
        QualityDimension.EFFICIENCY: 0.2,
        QualityDimension.QUALITY: 0.3,
        QualityDimension.STABILITY: 0.2,
        QualityDimension.RELIABILITY: 0.2,
        QualityDimension.COMPLEXITY: 0.1,
    }
    
    # 评分阈值
    EXCELLENT_THRESHOLD = 85.0
    GOOD_THRESHOLD = 70.0
    FAIR_THRESHOLD = 50.0
    
    def __init__(self, weights: Dict[QualityDimension, float] = None):
        """
        初始化评分器
        
        Args:
            weights: 自定义权重配置，默认使用 DEFAULT_WEIGHTS
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._score_history: Dict[str, deque] = {}  # skill_id -> 最近评分历史
        
    def evaluate_skill(
        self,
        skill: TaskSkill,
        execution_history: List[ExecutionRecord] = None,
        task_complexity: float = 0.5
    ) -> SkillQualityReport:
        """
        评估单个技能的质量
        
        Args:
            skill: 技能对象
            execution_history: 执行历史记录（可选）
            task_complexity: 任务复杂度 (0-1)
        
        Returns:
            SkillQualityReport: 质量评估报告
        """
        # 1. 计算效率评分
        efficiency_score = self._evaluate_efficiency(skill, task_complexity)
        
        # 2. 计算质量评分
        quality_score = self._evaluate_quality(skill, execution_history)
        
        # 3. 计算稳定性评分
        stability_score = self._evaluate_stability(skill, execution_history)
        
        # 4. 计算可靠性评分
        reliability_score = self._evaluate_reliability(skill)
        
        # 5. 计算复杂度适配评分
        complexity_score = self._evaluate_complexity_adaptation(skill, task_complexity)
        
        # 6. 计算综合评分
        overall_score = self._calculate_overall_score([
            efficiency_score,
            quality_score,
            stability_score,
            reliability_score,
            complexity_score
        ])
        
        # 7. 计算加权评分
        weighted_score = self._calculate_weighted_score([
            efficiency_score,
            quality_score,
            stability_score,
            reliability_score,
            complexity_score
        ])
        
        # 8. 更新历史记录
        self._update_history(skill.skill_id, weighted_score)
        
        # 9. 计算趋势
        trend, change = self._calculate_trend(skill.skill_id, weighted_score)
        
        # 构建报告
        report = SkillQualityReport(
            skill_id=skill.skill_id,
            skill_name=skill.name,
            efficiency_score=efficiency_score,
            quality_score=quality_score,
            stability_score=stability_score,
            reliability_score=reliability_score,
            complexity_score=complexity_score,
            overall_score=overall_score,
            weighted_score=weighted_score,
            trend=trend,
            trend_change=change,
            score_history=list(self._score_history.get(skill.skill_id, deque()))
        )
        
        logger.debug(f"技能 {skill.name} 质量评分: {weighted_score:.1f} ({trend})")
        return report
    
    def batch_evaluate(
        self,
        skills: List[TaskSkill],
        execution_histories: Dict[str, List[ExecutionRecord]] = None,
        task_complexities: Dict[str, float] = None
    ) -> List[SkillQualityReport]:
        """
        批量评估技能质量
        
        Args:
            skills: 技能列表
            execution_histories: 执行历史记录字典 {skill_id: [records]}
            task_complexities: 任务复杂度字典 {skill_id: complexity}
        
        Returns:
            List[SkillQualityReport]: 评估报告列表
        """
        reports = []
        for skill in skills:
            history = (execution_histories or {}).get(skill.skill_id, [])
            complexity = (task_complexities or {}).get(skill.skill_id, 0.5)
            
            report = self.evaluate_skill(skill, history, complexity)
            reports.append(report)
        
        # 计算排名
        reports = self._calculate_ranking(reports)
        
        return reports
    
    def get_quality_ranking(
        self,
        reports: List[SkillQualityReport] = None,
        skills: List[TaskSkill] = None
    ) -> List[SkillQualityReport]:
        """
        获取技能质量排名
        
        Args:
            reports: 已有评估报告（可选）
            skills: 技能列表（用于生成报告）
        
        Returns:
            List[SkillQualityReport]: 按质量排序的报告列表
        """
        if reports is None and skills:
            reports = self.batch_evaluate(skills)
        elif reports is None:
            return []
        
        # 按加权评分排序
        sorted_reports = sorted(
            reports,
            key=lambda r: r.weighted_score,
            reverse=True
        )
        
        # 更新排名
        for i, report in enumerate(sorted_reports):
            report.rank = i + 1
            report.percentile = (len(sorted_reports) - i) / len(sorted_reports) * 100
        
        return sorted_reports
    
    def compare_skills(
        self,
        skill_a: TaskSkill,
        skill_b: TaskSkill
    ) -> Dict[str, Any]:
        """
        对比两个技能的质量
        
        Returns:
            对比分析结果
        """
        report_a = self.evaluate_skill(skill_a)
        report_b = self.evaluate_skill(skill_b)
        
        diff = {
            "skill_a": skill_a.name,
            "skill_b": skill_b.name,
            "overall_diff": report_a.weighted_score - report_b.weighted_score,
            "dimensions": {}
        }
        
        # 各维度对比
        for dim in QualityDimension:
            score_a = getattr(report_a, f"{dim.value}_score").score
            score_b = getattr(report_b, f"{dim.value}_score").score
            diff["dimensions"][dim.value] = {
                "a": round(score_a, 1),
                "b": round(score_b, 1),
                "diff": round(score_a - score_b, 1),
                "winner": "a" if score_a > score_b else "b" if score_b > score_a else "tie"
            }
        
        return diff
    
    # ── 私有方法 ─────────────────────────────────────────────────────────────
    
    def _evaluate_efficiency(
        self,
        skill: TaskSkill,
        task_complexity: float
    ) -> QualityScore:
        """
        评估执行效率
        
        考虑因素：
        - 实际执行时长
        - 任务复杂度
        - 工具调用数量
        """
        avg_duration = skill.avg_duration
        
        # 根据复杂度计算预期时长
        base_duration = 10.0  # 基础时长（秒）
        expected_duration = base_duration * (1 + task_complexity)
        
        # 计算效率比
        if avg_duration > 0:
            efficiency_ratio = expected_duration / avg_duration
            efficiency_ratio = max(0.1, min(2.0, efficiency_ratio))  # 限制范围
        else:
            efficiency_ratio = 1.0
        
        # 转换为评分 (0-100)
        # ratio=1 表示刚好达到预期，ratio>1 表示高效
        score = min(100, efficiency_ratio * 60 + 40)  # 基础分40，上限100
        
        details = {
            "avg_duration": round(avg_duration, 2),
            "expected_duration": round(expected_duration, 2),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "task_complexity": task_complexity
        }
        
        return QualityScore(
            dimension=QualityDimension.EFFICIENCY,
            score=score,
            weight=self.weights.get(QualityDimension.EFFICIENCY, 0.2),
            reason=f"执行效率比 {efficiency_ratio:.2f}",
            details=details
        )
    
    def _evaluate_quality(
        self,
        skill: TaskSkill,
        execution_history: List[ExecutionRecord] = None
    ) -> QualityScore:
        """
        评估执行质量
        
        考虑因素：
        - 步骤成功率
        - 错误类型分布
        - 重试次数
        """
        success_rate = skill.success_rate
        
        # 基础分 = 成功率 * 100
        base_score = success_rate * 100
        
        # 如果有详细执行记录，考虑错误分布
        bonus = 0.0
        if execution_history:
            # 工具调用成功率
            tool_records = [r for r in execution_history if r.tool_name != "no_tool"]
            if tool_records:
                tool_success_rate = sum(1 for r in tool_records if r.success) / len(tool_records)
                # 工具成功率权重 0.3
                bonus = (tool_success_rate - success_rate) * 30
            
            # 错误恢复能力
            errors = [r for r in execution_history if not r.success]
            if errors:
                # 有错误但最终成功 = 有错误恢复能力
                final_success = execution_history[-1].success if execution_history else False
                if final_success:
                    bonus += 5  # 错误恢复加分
        
        score = min(100, max(0, base_score + bonus))
        
        details = {
            "success_rate": round(success_rate, 3),
            "use_count": skill.use_count,
            "failed_count": skill.failed_count,
            "tool_call_count": len(tool_records) if execution_history else 0
        }
        
        return QualityScore(
            dimension=QualityDimension.QUALITY,
            score=score,
            weight=self.weights.get(QualityDimension.QUALITY, 0.3),
            reason=f"成功率 {success_rate*100:.1f}%",
            details=details
        )
    
    def _evaluate_stability(
        self,
        skill: TaskSkill,
        execution_history: List[ExecutionRecord] = None
    ) -> QualityScore:
        """
        评估执行稳定性
        
        考虑因素：
        - 成功率方差
        - 执行时长方差
        - 结果一致性
        """
        # 基础稳定性基于成功率和历史使用次数
        base_stability = skill.success_rate * 50 + 50 * min(1, skill.use_count / 10)
        
        bonus = 0.0
        if execution_history and len(execution_history) >= 3:
            # 计算成功率的标准差
            window = execution_history[-10:]  # 最近10次
            results = [1.0 if r.success else 0.0 for r in window]
            
            mean = sum(results) / len(results)
            variance = sum((x - mean) ** 2 for x in results) / len(results)
            std_dev = variance ** 0.5
            
            # 低方差 = 高稳定性
            stability_bonus = (1 - std_dev) * 20
            bonus = stability_bonus
            
            # 执行时长稳定性
            durations = [r.duration for r in window if r.duration > 0]
            if durations and len(durations) > 1:
                dur_mean = sum(durations) / len(durations)
                dur_var = sum((d - dur_mean) ** 2 for d in durations) / len(durations)
                dur_std = dur_var ** 0.5
                
                if dur_mean > 0:
                    dur_stability = max(0, 1 - (dur_std / dur_mean)) * 10
                    bonus += dur_stability
        
        score = min(100, max(0, base_stability + bonus))
        
        return QualityScore(
            dimension=QualityDimension.STABILITY,
            score=score,
            weight=self.weights.get(QualityDimension.STABILITY, 0.2),
            reason=f"基础稳定性 {base_stability:.1f} + 波动调整 {bonus:.1f}",
            details={"stability_variance": variance if execution_history else 0}
        )
    
    def _evaluate_reliability(self, skill: TaskSkill) -> QualityScore:
        """
        评估长期可靠性
        
        考虑因素：
        - 使用次数（越多越可靠）
        - 进化状态
        - 距离上次使用的时间
        """
        # 使用次数贡献 (最多 30 分)
        usage_score = min(30, skill.use_count * 2)
        
        # 进化状态贡献 (最多 40 分)
        status_scores = {
            SkillEvolutionStatus.MATURED: 40,
            SkillEvolutionStatus.GROWING: 30,
            SkillEvolutionStatus.SEED: 15,
            SkillEvolutionStatus.ATROPHIED: 5,
            SkillEvolutionStatus.MERGED: 25,
        }
        status_score = status_scores.get(skill.evolution_status, 15)
        
        # 时间衰减 (最多 30 分)
        # 越久没用，分数越低
        days_since_use = (time.time() - skill.last_used) / 86400
        time_score = max(0, 30 - days_since_use * 3)  # 每天下降3分
        
        score = usage_score + status_score + time_score
        score = min(100, score)
        
        details = {
            "use_count": skill.use_count,
            "evolution_status": skill.evolution_status.value,
            "days_since_use": round(days_since_use, 1),
            "usage_score": round(usage_score, 1),
            "status_score": round(status_score, 1),
            "time_score": round(time_score, 1)
        }
        
        return QualityScore(
            dimension=QualityDimension.RELIABILITY,
            score=score,
            weight=self.weights.get(QualityDimension.RELIABILITY, 0.2),
            reason=f"使用{skill.use_count}次，状态{skill.evolution_status.value}",
            details=details
        )
    
    def _evaluate_complexity_adaptation(
        self,
        skill: TaskSkill,
        task_complexity: float
    ) -> QualityScore:
        """
        评估复杂度适配
        
        考虑因素：
        - 技能复杂度（工具数量、步骤数）与任务复杂度的匹配
        - 技能的灵活性
        """
        # 估算技能复杂度
        skill_complexity = len(skill.tool_sequence) * 10 + len(skill.execution_flow) * 5
        
        # 标准化到 0-1
        skill_complexity_normalized = min(1.0, skill_complexity / 50)
        
        # 计算匹配度
        complexity_diff = abs(skill_complexity_normalized - task_complexity)
        match_score = (1 - complexity_diff) * 100
        
        # 工具多样性奖励
        unique_tools = len(set(skill.tool_sequence))
        diversity_bonus = min(10, unique_tools * 2)  # 最多10分
        
        score = min(100, match_score + diversity_bonus)
        
        details = {
            "skill_complexity": round(skill_complexity_normalized, 2),
            "task_complexity": task_complexity,
            "complexity_diff": round(complexity_diff, 2),
            "unique_tools": unique_tools,
            "diversity_bonus": round(diversity_bonus, 1)
        }
        
        return QualityScore(
            dimension=QualityDimension.COMPLEXITY,
            score=score,
            weight=self.weights.get(QualityDimension.COMPLEXITY, 0.1),
            reason=f"复杂度匹配度 {match_score:.1f}，工具多样性 +{diversity_bonus:.1f}",
            details=details
        )
    
    def _calculate_overall_score(
        self,
        scores: List[QualityScore]
    ) -> float:
        """计算简单平均综合评分"""
        if not scores:
            return 0.0
        return sum(s.score for s in scores) / len(scores)
    
    def _calculate_weighted_score(
        self,
        scores: List[QualityScore]
    ) -> float:
        """计算加权综合评分"""
        if not scores:
            return 0.0
        
        total_weight = sum(s.weight for s in scores)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(s.score * s.weight for s in scores)
        return weighted_sum / total_weight
    
    def _update_history(self, skill_id: str, score: float):
        """更新评分历史"""
        if skill_id not in self._score_history:
            self._score_history[skill_id] = deque(maxlen=20)  # 保留最近20条
        
        self._score_history[skill_id].append({
            "score": score,
            "timestamp": time.time()
        })
    
    def _calculate_trend(
        self,
        skill_id: str,
        current_score: float
    ) -> Tuple[str, float]:
        """
        计算评分趋势
        
        Returns:
            (趋势类型, 变化量)
        """
        history = self._score_history.get(skill_id, deque())
        
        if len(history) < 3:
            return "stable", 0.0
        
        # 最近5次评分的平均变化
        recent = list(history)[-5:]
        if len(recent) < 2:
            return "stable", 0.0
        
        # 计算线性趋势
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(h["score"] for h in recent) / n
        
        numerator = sum((i - x_mean) * (recent[i]["score"] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        change = current_score - recent[0]["score"]
        
        if slope > 2:
            return "improving", round(change, 2)
        elif slope < -2:
            return "declining", round(change, 2)
        else:
            return "stable", round(change, 2)
    
    def _calculate_ranking(
        self,
        reports: List[SkillQualityReport]
    ) -> List[SkillQualityReport]:
        """计算排名"""
        sorted_reports = sorted(
            reports,
            key=lambda r: r.weighted_score,
            reverse=True
        )
        
        for i, report in enumerate(sorted_reports):
            report.rank = i + 1
            report.percentile = (len(sorted_reports) - i) / len(sorted_reports) * 100
        
        return sorted_reports
    
    def get_quality_insights(
        self,
        reports: List[SkillQualityReport]
    ) -> Dict[str, Any]:
        """
        从质量评估中提取洞察
        
        Returns:
            质量洞察报告
        """
        if not reports:
            return {"error": "No reports to analyze"}
        
        # 各维度平均分
        dim_averages = {}
        for dim in QualityDimension:
            scores = [getattr(r, f"{dim.value}_score").score for r in reports]
            dim_averages[dim.value] = sum(scores) / len(scores) if scores else 0
        
        # 找出最弱的维度
        weakest_dim = min(dim_averages.items(), key=lambda x: x[1])
        
        # 找出最强的维度
        strongest_dim = max(dim_averages.items(), key=lambda x: x[1])
        
        # 需要改进的技能
        needs_improvement = [r for r in reports if r.weighted_score < self.GOOD_THRESHOLD]
        
        # 优秀技能
        excellent = [r for r in reports if r.weighted_score >= self.EXCELLENT_THRESHOLD]
        
        return {
            "total_skills": len(reports),
            "dimension_averages": {k: round(v, 1) for k, v in dim_averages.items()},
            "weakest_dimension": weakest_dim[0],
            "strongest_dimension": strongest_dim[0],
            "needs_improvement_count": len(needs_improvement),
            "excellent_count": len(excellent),
            "average_score": round(sum(r.weighted_score for r in reports) / len(reports), 1),
            "improving_trend_count": sum(1 for r in reports if r.trend == "improving"),
            "declining_trend_count": sum(1 for r in reports if r.trend == "declining"),
        }


# ── 全局实例 ────────────────────────────────────────────────────────────────

_scorer: Optional[SkillQualityScorer] = None


def get_quality_scorer() -> SkillQualityScorer:
    """获取全局评分器实例"""
    global _scorer
    if _scorer is None:
        _scorer = SkillQualityScorer()
    return _scorer


def quick_evaluate(
    skill: TaskSkill,
    complexity: float = 0.5
) -> SkillQualityReport:
    """快速评估技能质量"""
    scorer = get_quality_scorer()
    return scorer.evaluate_skill(skill, task_complexity=complexity)


def get_top_skills(
    skills: List[TaskSkill],
    top_n: int = 5
) -> List[SkillQualityReport]:
    """获取质量最高的技能"""
    scorer = get_quality_scorer()
    reports = scorer.batch_evaluate(skills)
    ranking = scorer.get_quality_ranking(reports)
    return ranking[:top_n]
