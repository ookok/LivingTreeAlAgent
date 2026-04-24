"""
技能匹配度优化系统 - Skill Matching Optimizer
===============================================

核心功能：
1. 多维度技能匹配（语义、类型、上下文、反馈）
2. 动态权重调整
3. 匹配结果缓存
4. 预测性预加载

复用模块：
- TaskSkill (技能数据模型)
- SkillEvolutionDatabase (技能数据库)
- LLM 客户端 (用于语义匹配)

Author: Hermes Desktop Team
"""

import time
import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class MatchFactor(Enum):
    """匹配因素枚举"""
    SEMANTIC = "semantic"          # 语义相似度
    KEYWORD = "keyword"            # 关键词匹配
    TASK_TYPE = "task_type"        # 任务类型匹配
    TOOL_REQUIREMENT = "tool"      # 工具需求匹配
    COMPLEXITY = "complexity"      # 复杂度匹配
    CONTEXT = "context"            # 上下文匹配
    USER_FEEDBACK = "feedback"     # 用户反馈
    RECENCY = "recency"            # 最近使用


@dataclass
class MatchResult:
    """匹配结果"""
    skill_id: str
    skill_name: str
    score: float              # 总匹配分 (0-100)
    factors: Dict[str, float]  # 各因素得分
    
    # 匹配详情
    matched_keywords: List[str] = field(default_factory=list)
    matched_tools: List[str] = field(default_factory=list)
    missing_tools: List[str] = field(default_factory=list)
    
    # 预测信息
    predicted_success: float = 0.0  # 预测成功率
    estimated_duration: float = 0.0  # 预估时长
    confidence: float = 0.0        # 置信度
    
    # 推荐
    recommended: bool = False       # 是否推荐使用
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 索引
    rank: int = 0                   # 在匹配结果中的排名

    def to_dict(self) -> Dict:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "score": round(self.score, 2),
            "factors": {k: round(v, 2) for k, v in self.factors.items()},
            "matched_keywords": self.matched_keywords,
            "matched_tools": self.matched_tools,
            "missing_tools": self.missing_tools,
            "predicted_success": round(self.predicted_success, 3),
            "estimated_duration": round(self.estimated_duration, 2),
            "confidence": round(self.confidence, 2),
            "recommended": self.recommended,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "rank": self.rank
        }


@dataclass
class MatchRequest:
    """匹配请求"""
    query: str                    # 查询文本
    task_type: str = ""           # 任务类型
    required_tools: List[str] = field(default_factory=list)  # 必需工具
    task_complexity: float = 0.5  # 任务复杂度 (0-1)
    context: Dict[str, Any] = field(default_factory=dict)    # 上下文
    user_id: str = ""             # 用户ID（用于个性化）
    threshold: float = 30.0       # 最低匹配阈值
    top_k: int = 5                # 返回前k个结果
    
    # 可选：用于语义匹配的 embedding
    query_embedding: List[float] = None


class SkillMatchingOptimizer:
    """
    技能匹配度优化器
    
    多维度匹配策略：
    1. 语义匹配 - 使用 LLM/Embedding 计算语义相似度
    2. 关键词匹配 - 提取关键词重叠度
    3. 任务类型匹配 - 考虑任务分类
    4. 工具需求匹配 - 必需工具是否包含
    5. 复杂度匹配 - 任务复杂度与技能复杂度匹配
    6. 上下文匹配 - 考虑当前上下文
    7. 用户反馈 - 根据历史反馈调整
    8. 最近使用 - 近期使用的技能优先
    
    使用示例：
    ```python
    optimizer = SkillMatchingOptimizer()
    
    # 查找匹配的技能
    request = MatchRequest(
        query="帮我提取财务报表数据",
        task_type="data_extraction",
        required_tools=["file_reader", "parser"]
    )
    results = optimizer.find_matches(request)
    
    # 获取推荐技能
    recommended = optimizer.get_recommended_skill(request)
    ```
    """
    
    # 默认权重配置
    DEFAULT_WEIGHTS = {
        MatchFactor.SEMANTIC: 0.25,      # 语义权重最高
        MatchFactor.KEYWORD: 0.15,
        MatchFactor.TASK_TYPE: 0.15,
        MatchFactor.TOOL_REQUIREMENT: 0.20,
        MatchFactor.COMPLEXITY: 0.10,
        MatchFactor.CONTEXT: 0.05,
        MatchFactor.USER_FEEDBACK: 0.05,
        MatchFactor.RECENCY: 0.05,
    }
    
    # 匹配阈值
    EXCELLENT_MATCH = 85.0
    GOOD_MATCH = 70.0
    FAIR_MATCH = 50.0
    LOW_MATCH = 30.0
    
    def __init__(
        self,
        weights: Dict[MatchFactor, float] = None,
        db = None,  # EvolutionDatabase
        llm_client = None  # LLM 客户端
    ):
        """
        初始化匹配器
        
        Args:
            weights: 自定义权重配置
            db: 技能数据库（用于获取用户反馈等）
            llm_client: LLM 客户端（用于语义匹配）
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.db = db
        self.llm = llm_client
        
        # 匹配缓存
        self._cache: Dict[str, List[MatchResult]] = {}
        self._cache_ttl = 300  # 缓存5分钟
        
        # 用户反馈缓存
        self._feedback_cache: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # 技能复杂度缓存
        self._complexity_cache: Dict[str, float] = {}
    
    def find_matches(
        self,
        request: MatchRequest
    ) -> List[MatchResult]:
        """
        查找匹配的技能
        
        Args:
            request: 匹配请求
        
        Returns:
            List[MatchResult]: 匹配结果列表（按得分降序）
        """
        # 检查缓存
        cache_key = self._generate_cache_key(request)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug(f"匹配缓存命中: {cache_key}")
            return cached
        
        # 获取所有技能
        skills = self._get_all_skills()
        
        if not skills:
            return []
        
        # 计算每个技能的匹配分
        results = []
        for skill in skills:
            result = self._calculate_match(skill, request)
            results.append(result)
        
        # 按得分排序
        results.sort(key=lambda r: r.score, reverse=True)
        
        # 添加排名
        for i, result in enumerate(results):
            result.rank = i + 1
        
        # 缓存结果
        self._cache[cache_key] = results
        
        # 返回 top_k
        return results[:request.top_k]
    
    def get_recommended_skill(
        self,
        request: MatchRequest
    ) -> Optional[MatchResult]:
        """
        获取推荐的技能
        
        策略：
        1. 选择得分最高且 >= 阈值的技能
        2. 如果没有达标，返回 None
        """
        results = self.find_matches(request)
        
        for result in results:
            if result.score >= request.threshold and result.recommended:
                return result
        
        # 如果没有推荐的，返回得分最高的
        if results and results[0].score >= self.LOW_MATCH:
            return results[0]
        
        return None
    
    def find_alternatives(
        self,
        request: MatchRequest,
        exclude_skill_id: str
    ) -> List[MatchResult]:
        """
        查找替代技能（排除指定技能）
        """
        results = self.find_matches(request)
        return [r for r in results if r.skill_id != exclude_skill_id]
    
    def suggest_improvements(
        self,
        skill_id: str,
        request: MatchRequest
    ) -> List[str]:
        """
        建议技能改进方向
        
        基于匹配分析，给出技能需要改进的地方
        """
        # 获取技能
        skill = self._get_skill_by_id(skill_id)
        if not skill:
            return []
        
        suggestions = []
        
        # 检查关键词匹配
        query_keywords = self._extract_keywords(request.query)
        matched = set(query_keywords) & set(skill.trigger_patterns)
        missing = set(query_keywords) - set(skill.trigger_patterns)
        
        if missing:
            suggestions.append(f"建议添加触发关键词: {', '.join(list(missing)[:5])}")
        
        # 检查工具匹配
        if request.required_tools:
            skill_tools = set(skill.tool_sequence)
            required = set(request.required_tools)
            missing_tools = required - skill_tools
            
            if missing_tools:
                suggestions.append(f"建议增加工具: {', '.join(missing_tools)}")
        
        # 检查复杂度
        skill_complexity = self._estimate_skill_complexity(skill)
        if abs(skill_complexity - request.task_complexity) > 0.3:
            if skill_complexity < request.task_complexity:
                suggestions.append("技能复杂度偏低，建议增加更多步骤或工具")
            else:
                suggestions.append("技能过于复杂，可以简化执行流程")
        
        return suggestions
    
    def record_feedback(
        self,
        skill_id: str,
        user_id: str,
        success: bool,
        rating: float = None  # 用户评分 0-5
    ):
        """
        记录用户反馈
        
        用于调整未来匹配权重
        """
        if user_id not in self._feedback_cache:
            self._feedback_cache[user_id] = {}
        
        # 更新反馈
        if skill_id not in self._feedback_cache[user_id]:
            self._feedback_cache[user_id][skill_id] = {
                "total": 0,
                "successes": 0,
                "ratings": []
            }
        
        fb = self._feedback_cache[user_id][skill_id]
        fb["total"] += 1
        if success:
            fb["successes"] += 1
        if rating is not None:
            fb["ratings"].append(rating)
        
        # 清除相关缓存
        self._invalidate_cache_for_skill(skill_id)
    
    def get_match_explanation(
        self,
        result: MatchResult
    ) -> str:
        """
        生成匹配解释
        
        用于向用户解释为什么推荐这个技能
        """
        lines = [
            f"## 技能匹配分析: {result.skill_name}",
            "",
            f"**综合得分**: {result.score:.1f}/100",
            "",
            "### 得分明细",
        ]
        
        for factor, score in result.factors.items():
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            lines.append(f"- {factor}: {bar} {score:.1f}")
        
        if result.matched_keywords:
            lines.append("")
            lines.append("### 匹配关键词")
            lines.append(", ".join(result.matched_keywords))
        
        if result.reasons:
            lines.append("")
            lines.append("### 推荐理由")
            for reason in result.reasons:
                lines.append(f"- {reason}")
        
        if result.warnings:
            lines.append("")
            lines.append("### 注意事项")
            for warning in result.warnings:
                lines.append(f"- {warning}")
        
        return "\n".join(lines)
    
    # ── 私有方法 ─────────────────────────────────────────────────────────────
    
    def _get_all_skills(self) -> List:
        """获取所有技能"""
        if self.db:
            try:
                return self.db.get_all_skills()
            except Exception as e:
                logger.warning(f"获取技能失败: {e}")
        
        return []
    
    def _get_skill_by_id(self, skill_id: str):
        """根据ID获取技能"""
        if self.db:
            try:
                return self.db.get_skill(skill_id)
            except Exception:
                pass
        return None
    
    def _calculate_match(
        self,
        skill,
        request: MatchRequest
    ) -> MatchResult:
        """计算技能匹配度"""
        # 各因素得分
        factor_scores = {}
        
        # 1. 语义匹配
        factor_scores[MatchFactor.SEMANTIC.value] = self._match_semantic(
            skill, request.query
        )
        
        # 2. 关键词匹配
        kw_score, matched_kw = self._match_keywords(
            skill, request.query
        )
        factor_scores[MatchFactor.KEYWORD.value] = kw_score
        
        # 3. 任务类型匹配
        type_score = self._match_task_type(
            skill, request.task_type
        )
        factor_scores[MatchFactor.TASK_TYPE.value] = type_score
        
        # 4. 工具需求匹配
        tool_score, matched_tools, missing_tools = self._match_tools(
            skill, request.required_tools
        )
        factor_scores[MatchFactor.TOOL_REQUIREMENT.value] = tool_score
        
        # 5. 复杂度匹配
        complexity_score = self._match_complexity(
            skill, request.task_complexity
        )
        factor_scores[MatchFactor.COMPLEXITY.value] = complexity_score
        
        # 6. 上下文匹配
        context_score = self._match_context(
            skill, request.context
        )
        factor_scores[MatchFactor.CONTEXT.value] = context_score
        
        # 7. 用户反馈
        feedback_score = self._get_feedback_score(
            skill.skill_id, request.user_id
        )
        factor_scores[MatchFactor.USER_FEEDBACK.value] = feedback_score
        
        # 8. 最近使用
        recency_score = self._calculate_recency(skill)
        factor_scores[MatchFactor.RECENCY.value] = recency_score
        
        # 计算总分
        total_score = self._calculate_weighted_score(factor_scores)
        
        # 预测成功率和时长
        predicted_success = self._predict_success(
            skill, factor_scores
        )
        estimated_duration = skill.avg_duration
        
        # 判断是否推荐
        recommended = (
            total_score >= self.FAIR_MATCH and
            predicted_success >= 0.7 and
            len(missing_tools) == 0
        )
        
        # 生成推荐理由和警告
        reasons = self._generate_reasons(skill, factor_scores, matched_kw)
        warnings = self._generate_warnings(
            skill, missing_tools, predicted_success, total_score
        )
        
        # 计算置信度
        confidence = min(1.0, (total_score / 100) * 0.7 + skill.success_rate * 0.3)
        
        return MatchResult(
            skill_id=skill.skill_id,
            skill_name=skill.name,
            score=total_score,
            factors=factor_scores,
            matched_keywords=matched_kw,
            matched_tools=matched_tools,
            missing_tools=missing_tools,
            predicted_success=predicted_success,
            estimated_duration=estimated_duration,
            confidence=confidence,
            recommended=recommended,
            reasons=reasons,
            warnings=warnings
        )
    
    def _match_semantic(
        self,
        skill,
        query: str
    ) -> float:
        """语义匹配 - 使用关键词 + 简单语义特征计算"""
        skill_text = skill.name + " " + skill.description
        query_lower = query.lower()
        skill_lower = skill_text.lower()
        
        # 简单词重叠
        query_words = set(self._extract_keywords(query))
        skill_words = set(self._extract_keywords(skill_text))
        
        if not query_words or not skill_words:
            return 30.0
        
        overlap = len(query_words & skill_words)
        union = len(query_words | skill_words)
        jaccard = overlap / union if union > 0 else 0
        
        return min(100, jaccard * 150)
    
    def _match_keywords(
        self,
        skill,
        query: str
    ) -> Tuple[float, List[str]]:
        """关键词匹配"""
        query_keywords = self._extract_keywords(query)
        skill_keywords = set(skill.trigger_patterns)
        
        matched = []
        for kw in query_keywords:
            if any(kw.lower() in sk.lower() or sk.lower() in kw.lower() 
                   for sk in skill_keywords):
                matched.append(kw)
        
        if not query_keywords:
            return 50.0, []
        
        match_ratio = len(matched) / len(query_keywords)
        return min(100, match_ratio * 100 + 30), matched
    
    def _match_task_type(
        self,
        skill,
        task_type: str
    ) -> float:
        """任务类型匹配"""
        if not task_type:
            return 50.0
        
        skill_type = skill.metadata.get("task_type", "")
        
        if not skill_type:
            return 40.0
        
        if skill_type.lower() == task_type.lower():
            return 100.0
        
        if skill_type.lower() in task_type.lower() or task_type.lower() in skill_type.lower():
            return 70.0
        
        return 30.0
    
    def _match_tools(
        self,
        skill,
        required_tools: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """工具需求匹配"""
        if not required_tools:
            return 70.0, [], []
        
        skill_tools = set(skill.tool_sequence)
        required = set(required_tools)
        
        matched = list(required & skill_tools)
        missing = list(required - skill_tools)
        
        if not required:
            return 70.0, [], []
        
        match_ratio = len(matched) / len(required)
        
        if not missing:
            return 100.0, matched, []
        
        if matched:
            return max(20, match_ratio * 100 - len(missing) * 10), matched, missing
        
        return 20.0, [], missing
    
    def _match_complexity(
        self,
        skill,
        task_complexity: float
    ) -> float:
        """复杂度匹配"""
        skill_complexity = self._estimate_skill_complexity(skill)
        
        diff = abs(skill_complexity - task_complexity)
        
        if diff <= 0.1:
            return 100.0
        elif diff <= 0.2:
            return 85.0
        elif diff <= 0.3:
            return 70.0
        elif diff <= 0.5:
            return 50.0
        else:
            return 30.0
    
    def _match_context(
        self,
        skill,
        context: Dict[str, Any]
    ) -> float:
        """上下文匹配"""
        if not context:
            return 50.0
        
        score = 50.0
        
        domain = context.get("domain", "")
        if domain:
            skill_domain = skill.metadata.get("domain", "")
            if domain.lower() == skill_domain.lower():
                score += 20
            elif domain.lower() in skill_domain.lower() or skill_domain.lower() in domain.lower():
                score += 10
        
        env = context.get("environment", "")
        if env:
            skill_env = skill.metadata.get("environment", "")
            if env.lower() == skill_env.lower():
                score += 10
        
        return min(100, score)
    
    def _get_feedback_score(
        self,
        skill_id: str,
        user_id: str
    ) -> float:
        """获取用户反馈评分"""
        if not user_id or skill_id not in self._feedback_cache.get(user_id, {}):
            return 50.0
        
        fb = self._feedback_cache[user_id][skill_id]
        
        success_rate = fb["successes"] / fb["total"] if fb["total"] > 0 else 0.5
        avg_rating = sum(fb["ratings"]) / len(fb["ratings"]) if fb["ratings"] else 3.0
        
        score = success_rate * 60 + (avg_rating / 5.0) * 40
        
        return min(100, score)
    
    def _calculate_recency(self, skill) -> float:
        """计算最近使用分数"""
        days_since_use = (time.time() - skill.last_used) / 86400
        
        if days_since_use <= 1:
            return 100.0
        elif days_since_use <= 7:
            return 90.0
        elif days_since_use <= 30:
            return 70.0
        elif days_since_use <= 90:
            return 50.0
        else:
            return max(20, 30 - (days_since_use - 90) / 10)
    
    def _calculate_weighted_score(
        self,
        factor_scores: Dict[str, float]
    ) -> float:
        """计算加权总分"""
        total_weight = sum(self.weights.get(MatchFactor(f), 0.1) 
                          for f in factor_scores.keys())
        
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            factor_scores[f] * self.weights.get(MatchFactor(f), 0.1)
            for f in factor_scores.keys()
        )
        
        return weighted_sum / total_weight
    
    def _predict_success(
        self,
        skill,
        factor_scores: Dict[str, float]
    ) -> float:
        """预测技能成功率"""
        base = skill.success_rate
        
        avg_match = sum(factor_scores.values()) / len(factor_scores) if factor_scores else 50
        match_factor = avg_match / 100
        
        predicted = base * 0.6 + match_factor * 0.4
        
        return min(1.0, max(0.0, predicted))
    
    def _estimate_skill_complexity(self, skill) -> float:
        """估算技能复杂度 (0-1)"""
        if skill.skill_id in self._complexity_cache:
            return self._complexity_cache[skill.skill_id]
        
        tool_count = len(skill.tool_sequence)
        step_count = len(skill.execution_flow)
        
        complexity = (tool_count * 0.05 + step_count * 0.03)
        complexity = min(1.0, complexity)
        
        self._complexity_cache[skill.skill_id] = complexity
        return complexity
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        words = re.findall(r'[\w]+', text.lower())
        
        stopwords = {
            '的', '了', '是', '在', '和', '与', '或', '一个', '这个', '那',
            '帮', '我', '请', '你', '一下', '什么', '怎么', '如何', '可以',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been'
        }
        
        keywords = [w for w in words if len(w) > 1 and w not in stopwords]
        return keywords
    
    def _generate_cache_key(self, request: MatchRequest) -> str:
        """生成缓存键"""
        parts = [
            request.query[:50],
            request.task_type,
            ",".join(sorted(request.required_tools)),
            str(request.task_complexity)
        ]
        return "|".join(parts)
    
    def _generate_reasons(
        self,
        skill,
        factor_scores: Dict[str, float],
        matched_keywords: List[str]
    ) -> List[str]:
        """生成推荐理由"""
        reasons = []
        
        if factor_scores.get(MatchFactor.SEMANTIC.value, 0) >= 70:
            reasons.append("语义高度匹配")
        
        if factor_scores.get(MatchFactor.TOOL_REQUIREMENT.value, 0) >= 80:
            reasons.append("工具需求完全满足")
        
        if matched_keywords and len(matched_keywords) >= 2:
            reasons.append(f"关键词匹配: {', '.join(matched_keywords[:3])}")
        
        if skill.success_rate >= 0.9:
            reasons.append(f"历史成功率高 ({skill.success_rate*100:.0f}%)")
        
        if skill.evolution_status.value == "matured":
            reasons.append("技能已成熟稳定")
        
        return reasons
    
    def _generate_warnings(
        self,
        skill,
        missing_tools: List[str],
        predicted_success: float,
        total_score: float
    ) -> List[str]:
        """生成警告信息"""
        warnings = []
        
        if missing_tools:
            warnings.append(f"缺少必需工具: {', '.join(missing_tools)}")
        
        if predicted_success < 0.6:
            warnings.append(f"预测成功率较低 ({predicted_success*100:.0f}%)")
        
        if total_score < self.GOOD_MATCH:
            warnings.append("整体匹配度一般，可能需要人工介入")
        
        if skill.use_count < 3:
            warnings.append("该技能使用次数较少，效果待验证")
        
        if skill.evolution_status.value == "seed":
            warnings.append("技能尚处于种子阶段，可能不够稳定")
        
        return warnings
    
    def _invalidate_cache_for_skill(self, skill_id: str):
        """清除与技能相关的缓存"""
        self._cache.clear()


# ── 全局实例 ────────────────────────────────────────────────────────────────

_optimizer: Optional[SkillMatchingOptimizer] = None


def get_matching_optimizer() -> SkillMatchingOptimizer:
    """获取全局匹配优化器实例"""
    global _optimizer
    if _optimizer is None:
        _optimizer = SkillMatchingOptimizer()
    return _optimizer


def quick_match(
    query: str,
    task_type: str = "",
    required_tools: List[str] = None,
    threshold: float = 30.0
) -> Optional[MatchResult]:
    """快速匹配技能"""
    optimizer = get_matching_optimizer()
    
    request = MatchRequest(
        query=query,
        task_type=task_type,
        required_tools=required_tools or [],
        threshold=threshold
    )
    
    return optimizer.get_recommended_skill(request)


def batch_match(
    queries: List[str],
    task_type: str = ""
) -> Dict[str, Optional[MatchResult]]:
    """批量匹配技能"""
    optimizer = get_matching_optimizer()
    results = {}
    
    for query in queries:
        request = MatchRequest(
            query=query,
            task_type=task_type
        )
        results[query] = optimizer.get_recommended_skill(request)
    
    return results
