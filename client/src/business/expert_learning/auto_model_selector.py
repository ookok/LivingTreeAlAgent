# -*- coding: utf-8 -*-
"""
自动模型选择策略引擎 (Auto Model Selector)
==========================================

根据任务类型自动选择最优模型，平衡质量、成本和延迟。

Author: LivingTreeAI Agent
Date: 2026-04-24
from __future__ import annotations
"""


import json
import time
import re
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
from client.src.business.logger import get_logger
logger = get_logger('expert_learning.auto_model_selector')



# ═══════════════════════════════════════════════════════════════════════════════
# 任务类型定义
# ═══════════════════════════════════════════════════════════════════════════════

class TaskType(Enum):
    """任务类型"""
    GREETING = "greeting"
    CHITCHAT = "chitchat"
    QUESTION = "question"
    REASONING = "reasoning"
    MATHEMATICS = "mathematics"
    ANALYSIS = "analysis"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    WRITING = "writing"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    CREATIVE = "creative"
    SEARCH = "search"
    RESEARCH = "research"
    UNKNOWN = "unknown"


class TaskComplexity(Enum):
    TRIVIAL = 0.2
    LOW = 0.4
    MEDIUM = 0.6
    HIGH = 0.8
    COMPLEX = 1.0


@dataclass
class ModelCapability:
    """模型能力"""
    model_id: str
    model_name: str
    strengths: List[TaskType] = field(default_factory=list)
    weaknesses: List[TaskType] = field(default_factory=list)
    max_tokens: int = 8192
    avg_latency_ms: float = 3000
    success_rate: float = 0.9
    quality_score: float = 0.8
    cost_per_1k_tokens: float = 0


@dataclass
class ModelRecommendation:
    """模型推荐"""
    primary_model: ModelCapability
    fallback_models: List[ModelCapability] = field(default_factory=list)
    batch_models: List[ModelCapability] = field(default_factory=list)
    estimated_latency_ms: float = 0
    estimated_cost: float = 0
    reasoning: str = ""
    confidence: float = 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# 意图分类器
# ═══════════════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """意图分类器"""

    KEYWORD_PATTERNS: Dict[TaskType, List[str]] = {
        TaskType.GREETING: [r'^你好', r'^您好', r'^hi', r'^hello', r'^嗨', r'早上好', r'下午好'],
        TaskType.CHITCHAT: [r'今天', r'天气', r'怎么样', r'最近', r'无聊', r'聊聊'],
        TaskType.QUESTION: [r'是什么', r'为什么', r'怎么', r'如何', r'哪里', r'多少', r'请问'],
        TaskType.REASONING: [r'分析', r'推理', r'判断', r'思考', r'逻辑', r'如果.*那么', r'因为.*所以'],
        TaskType.MATHEMATICS: [r'计算', r'加', r'减', r'乘', r'除', r'数学', r'方程', r'函数'],
        TaskType.CODE_GENERATION: [r'写代码', r'生成代码', r'编程', r'def\s', r'function\s', r'python', r'javascript'],
        TaskType.CODE_REVIEW: [r'审查', r'review', r'检查代码', r'优化代码'],
        TaskType.DEBUGGING: [r'调试', r'debug', r'报错', r'错误', r'bug', r'修复', r'问题'],
        TaskType.WRITING: [r'写', r'创作', r'编写', r'起草', r'文章', r'报告', r'邮件'],
        TaskType.TRANSLATION: [r'翻译', r'translate', r'中译英', r'英译中'],
        TaskType.SUMMARIZATION: [r'总结', r'摘要', r'概括', r'提炼', r'关键点'],
        TaskType.CREATIVE: [r'创意', r'创造', r'想象', r'设计', r'故事', r'诗歌'],
        TaskType.SEARCH: [r'搜索', r'查找', r'查询', r'找一下'],
        TaskType.RESEARCH: [r'研究', r'调研', r'调查', r'探索', r'深入'],
    }

    def classify(self, query: str) -> Tuple[TaskType, float]:
        """分类查询"""
        query_lower = query.lower()
        scores: Dict[TaskType, float] = defaultdict(float)

        for task_type, patterns in self.KEYWORD_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    scores[task_type] += 1

        if not scores:
            return TaskType.UNKNOWN, 0.0

        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]
        confidence = min(max_score / 3, 1.0)

        return best_type, confidence


# ═══════════════════════════════════════════════════════════════════════════════
# 复杂度评估器
# ═══════════════════════════════════════════════════════════════════════════════

class ComplexityEstimator:
    """复杂度评估器"""

    def estimate(self, query: str, task_type: TaskType) -> Tuple[TaskComplexity, Dict]:
        """评估复杂度"""
        factors = {"length_score": 0, "structure_score": 0, "domain_score": 0, "task_score": 0}

        # 长度
        length = len(query)
        if length < 30: factors["length_score"] = 0.1
        elif length < 100: factors["length_score"] = 0.3
        elif length < 300: factors["length_score"] = 0.5
        elif length < 500: factors["length_score"] = 0.7
        else: factors["length_score"] = 0.9

        # 结构
        if re.search(r'\d+[.)、]', query): factors["structure_score"] = 0.3
        if re.search(r'如果.*那么', query): factors["structure_score"] += 0.2
        if re.search(r'因为.*所以', query): factors["structure_score"] += 0.2

        # 领域
        domain_keywords = ['量子', '算法', '架构', '分布式', '微服务', '机器学习', '神经网络']
        for keyword in domain_keywords:
            if keyword in query:
                factors["domain_score"] = max(factors["domain_score"], 0.5)

        # 任务复杂度
        complex_tasks = {TaskType.REASONING: 0.4, TaskType.MATHEMATICS: 0.5, TaskType.CODE_GENERATION: 0.4, TaskType.ANALYSIS: 0.5, TaskType.RESEARCH: 0.6}
        factors["task_score"] = complex_tasks.get(task_type, 0.2)

        # 综合
        total = factors["length_score"] * 0.2 + factors["structure_score"] * 0.2 + factors["domain_score"] * 0.3 + factors["task_score"] * 0.3

        if total < 0.25: complexity = TaskComplexity.TRIVIAL
        elif total < 0.4: complexity = TaskComplexity.LOW
        elif total < 0.55: complexity = TaskComplexity.MEDIUM
        elif total < 0.75: complexity = TaskComplexity.HIGH
        else: complexity = TaskComplexity.COMPLEX

        return complexity, factors


# ═══════════════════════════════════════════════════════════════════════════════
# 性能追踪器
# ═══════════════════════════════════════════════════════════════════════════════

class PerformanceTracker:
    """性能追踪器"""

    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self._lock = threading.RLock()
        self._task_performance: Dict[str, Dict[TaskType, Dict]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "success": 0, "total_latency": 0, "quality_scores": []}))
        self._model_overall: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "success": 0, "total_latency": 0})

    def record(self, model_id: str, task_type: TaskType, latency_ms: float, success: bool, quality_score: Optional[float] = None):
        """记录表现"""
        with self._lock:
            stats = self._task_performance[model_id][task_type]
            stats["count"] += 1
            if success: stats["success"] += 1
            stats["total_latency"] += latency_ms
            if quality_score is not None:
                stats["quality_scores"].append(quality_score)
                if len(stats["quality_scores"]) > 100: stats["quality_scores"].pop(0)

            overall = self._model_overall[model_id]
            overall["count"] += 1
            if success: overall["success"] += 1
            overall["total_latency"] += latency_ms

    def get_stats(self) -> Dict:
        """获取统计"""
        with self._lock:
            return {"tracked_models": len(self._model_overall), "total_records": sum(m["count"] for m in self._model_overall.values())}


# ═══════════════════════════════════════════════════════════════════════════════
# 自动模型选择器
# ═══════════════════════════════════════════════════════════════════════════════

class AutoModelSelector:
    """
    自动模型选择器

    使用方式:
    ```python
    selector = AutoModelSelector()
    selector.register_model("ollama_9b", "qwen3.5:9b", {"strengths": [TaskType.REASONING]})
    rec = selector.recommend("解释量子计算原理")
    logger.info(rec.primary_model.model_name)
    ```
    """

    def __init__(self, prefer_free: bool = True, latency_budget_ms: float = 5000):
        self.prefer_free = prefer_free
        self.latency_budget_ms = latency_budget_ms
        self._classifier = IntentClassifier()
        self._estimator = ComplexityEstimator()
        self._tracker = PerformanceTracker()
        self._models: Dict[str, ModelCapability] = {}
        self._on_selection: Optional[Callable] = None
        logger.info("[AutoModelSelector] 已初始化")

    def register_model(self, model_id: str, model_name: str, capabilities: Dict[str, Any]):
        """注册模型"""
        strengths = [TaskType(s) if isinstance(s, str) else s for s in capabilities.get("strengths", [])]
        weaknesses = [TaskType(w) if isinstance(w, str) else w for w in capabilities.get("weaknesses", [])]

        model = ModelCapability(
            model_id=model_id, model_name=model_name,
            strengths=strengths, weaknesses=weaknesses,
            max_tokens=capabilities.get("max_tokens", 8192),
            avg_latency_ms=capabilities.get("avg_latency_ms", 3000),
            success_rate=capabilities.get("success_rate", 0.9),
            quality_score=capabilities.get("quality_score", 0.8),
            cost_per_1k_tokens=capabilities.get("cost_per_1k_tokens", 0),
        )
        self._models[model_id] = model
        logger.info(f"[AutoModelSelector] 注册: {model_name}")

    def unregister_model(self, model_id: str) -> bool:
        """注销模型"""
        if model_id in self._models:
            del self._models[model_id]
            return True
        return False

    def recommend(self, query: str, context: Optional[Dict] = None, force_model: Optional[str] = None) -> ModelRecommendation:
        """推荐模型"""
        task_type, task_confidence = self._classifier.classify(query)
        complexity, _ = self._estimator.estimate(query, task_type)

        if force_model and force_model in self._models:
            primary = self._models[force_model]
            return ModelRecommendation(primary_model=primary, fallback_models=self._get_fallback(force_model, task_type), estimated_latency_ms=primary.avg_latency_ms, estimated_cost=0, reasoning=f"强制使用{primary.model_name}", confidence=1.0)

        candidates = self._score_models(query, task_type, complexity)

        if not candidates:
            return self._default_recommendation()

        best_id, best_score = candidates[0]
        primary = self._models[best_id]

        if self._on_selection:
            self._on_selection(primary, task_type, complexity)

        return ModelRecommendation(
            primary_model=primary,
            fallback_models=self._get_fallback(best_id, task_type),
            estimated_latency_ms=primary.avg_latency_ms,
            estimated_cost=0,
            reasoning=self._generate_reasoning(primary, task_type, best_score),
            confidence=best_score,
            alternatives=[self._models[mid].model_name for mid, _ in candidates[1:4]],
        )

    def _score_models(self, query: str, task_type: TaskType, complexity: TaskComplexity) -> List[Tuple[str, float]]:
        """评分模型"""
        candidates = []
        for model_id, model in self._models.items():
            score = self._calculate_score(model, task_type, complexity)
            candidates.append((model_id, score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        if self.prefer_free:
            free = [(mid, s) for mid, s in candidates if self._models[mid].cost_per_1k_tokens == 0]
            if free: candidates = free

        valid = [(mid, s) for mid, s in candidates if self._models[mid].avg_latency_ms <= self.latency_budget_ms]
        return valid if valid else candidates[:5]

    def _calculate_score(self, model: ModelCapability, task_type: TaskType, complexity: TaskComplexity) -> float:
        """计算得分"""
        score = 0.5
        if task_type in model.strengths: score += 0.3
        if task_type in model.weaknesses: score -= 0.3
        if complexity.value <= 0.4 and model.avg_latency_ms < 2000: score += 0.1
        if complexity.value >= 0.8 and model.quality_score > 0.8: score += 0.2
        if model.cost_per_1k_tokens == 0: score += 0.1
        elif self.prefer_free: score -= 0.1
        if model.avg_latency_ms < 2000: score += 0.1
        elif model.avg_latency_ms > 5000: score -= 0.1
        return max(0, min(1, score))

    def _get_fallback(self, primary_id: str, task_type: TaskType) -> List[ModelCapability]:
        """获取备用模型"""
        return [m for mid, m in self._models.items() if mid != primary_id][:3]

    def _default_recommendation(self) -> ModelRecommendation:
        """默认推荐"""
        if not self._models:
            raise ValueError("没有注册任何模型")
        primary = list(self._models.values())[0]
        return ModelRecommendation(primary_model=primary, fallback_models=list(self._models.values())[1:4], estimated_latency_ms=primary.avg_latency_ms, estimated_cost=0, reasoning="默认模型", confidence=0.3)

    def _generate_reasoning(self, model: ModelCapability, task_type: TaskType, score: float) -> str:
        """生成推理"""
        reasons = []
        if task_type in model.strengths: reasons.append(f"擅长{task_type.value}")
        if model.cost_per_1k_tokens == 0: reasons.append("免费")
        if model.avg_latency_ms < 2000: reasons.append("低延迟")
        return "，".join(reasons) if reasons else f"选择{model.model_name}"

    def record_result(self, model_id: str, query: str, latency_ms: float, success: bool, quality_score: Optional[float] = None):
        """记录结果"""
        task_type, _ = self._classifier.classify(query)
        self._tracker.record(model_id, task_type, latency_ms, success, quality_score)

    def get_stats(self) -> Dict:
        """获取统计"""
        return {"registered_models": len(self._models), "tracker": self._tracker.get_stats()}

    def get_model_list(self) -> List[Dict]:
        """获取模型列表"""
        return [{"id": m.model_id, "name": m.model_name, "strengths": [t.value for t in m.strengths]} for m in self._models.values()]


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("自动模型选择策略引擎测试")
    logger.info("=" * 60)

    selector = AutoModelSelector(prefer_free=True)

    selector.register_model("small", "qwen2.5:0.5b", {"strengths": [TaskType.GREETING, TaskType.CHITCHAT], "avg_latency_ms": 500, "cost_per_1k_tokens": 0})
    selector.register_model("balanced", "qwen2.5:1.5b", {"strengths": [TaskType.QUESTION, TaskType.SUMMARIZATION], "avg_latency_ms": 2000, "cost_per_1k_tokens": 0})
    selector.register_model("strong", "qwen3.5:9b", {"strengths": [TaskType.REASONING, TaskType.CODE_GENERATION, TaskType.ANALYSIS], "avg_latency_ms": 5000, "quality_score": 0.9, "cost_per_1k_tokens": 0})

    logger.info("\n[Test 1: 任务分类]")
    classifier = IntentClassifier()
    for q in ["你好", "帮我写代码", "解释量子计算", "总结文章"]:
        task, conf = classifier.classify(q)
        logger.info(f"  '{q}' -> {task.value} ({conf:.2f})")

    logger.info("\n[Test 2: 模型推荐]")
    rec = selector.recommend("帮我写Python快速排序")
    logger.info(f"  推荐: {rec.primary_model.model_name}, 置信度: {rec.confidence:.2f}")
    logger.info(f"  推理: {rec.reasoning}")

    logger.info("\n" + "=" * 60)
