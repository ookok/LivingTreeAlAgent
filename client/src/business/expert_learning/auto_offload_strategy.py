"""
智能卸载策略 (Auto-Offload Strategy)
======================================

根据任务复杂度自动决定：
- 纯本地处理
- 混合模式（本地+专家验证）
- 完全专家模式

核心决策因素：
1. 任务复杂度评分
2. 当前系统负载
3. 用户偏好设置
4. 历史学习效果
"""

import time
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics
from client.src.business.logger import get_logger
logger = get_logger('expert_learning.auto_offload_strategy')


# ── 复杂度等级 ──────────────────────────────────────────────────────────────

class ComplexityLevel(Enum):
    """复杂度等级"""
    TRIVIAL = 0      # 纯格式/简单问答
    LOW = 1          # 基础任务
    MEDIUM = 2       # 需要一定推理
    HIGH = 3         # 复杂推理/专业知识
    EXPERT = 4       # 需要专家级知识


class OffloadDecision(Enum):
    """卸载决策"""
    LOCAL_ONLY = "local"                    # 纯本地处理
    LOCAL_WITH_LEARNING = "local_learn"     # 本地处理+记录学习
    HYBRID = "hybrid"                        # 混合模式（本地生成+专家验证）
    EXPERT_PRIMARY = "expert"               # 专家为主
    EXPERT_ONLY = "expert_only"             # 完全专家模式


# ── 复杂度指标 ──────────────────────────────────────────────────────────────

@dataclass
class ComplexityMetrics:
    """复杂度评估指标"""
    # 文本特征
    query_length: int = 0
    sentence_count: int = 0
    avg_word_length: float = 0.0

    # 语义特征
    technical_terms: int = 0
    numbers_count: int = 0
    question_marks: int = 0
    compound_sentences: int = 0

    # 关键词特征
    has_code: bool = False
    has_math: bool = False
    has_entity: bool = False
    is_creative: bool = False
    is_reasoning: bool = False

    # 综合评分
    complexity_score: float = 0.0
    reasoning_depth: float = 0.0


# ── 卸载策略配置 ─────────────────────────────────────────────────────────────

@dataclass
class OffloadStrategyConfig:
    """卸载策略配置"""
    # 复杂度阈值
    local_threshold: float = 0.3      # < 此值纯本地
    hybrid_threshold: float = 0.6      # < 此值混合模式
    expert_threshold: float = 0.8      # > 此值专家模式

    # 特殊规则
    always_expert_patterns: List[str] = None  # 强制专家的pattern
    always_local_patterns: List[str] = None    # 强制本地的pattern

    # 学习策略
    learning_probability: float = 0.3  # 混合模式下30%用专家学习

    # 性能适应
    auto_adjust_thresholds: bool = True
    performance_window: int = 100      # 性能统计窗口

    def __post_init__(self):
        if self.always_expert_patterns is None:
            self.always_expert_patterns = [
                r"计算\S*积分",
                r"证明\S*定理",
                r"医学",
                r"法律",
                r"金融.*分析",
            ]
        if self.always_local_patterns is None:
            self.always_local_patterns = [
                r"^(你好|hi|hello|嗨)",
                r"翻译",
                r"格式.*转换",
                r"^查.*天气",
            ]


# ── 智能卸载策略 ─────────────────────────────────────────────────────────────

class AutoOffloadStrategy:
    """
    智能卸载决策器

    根据多种因素自动决定最优处理模式

    使用示例:
    ```python
    strategy = AutoOffloadStrategy()

    # 评估查询
    metrics = strategy.evaluate_complexity("解释一下量子计算原理")
    decision = strategy.decide(
        query="解释一下量子计算原理",
        metrics=metrics,
        system_state={"cpu_usage": 0.3, "memory_usage": 0.5}
    )

    # decision.local_mode = False
    # decision.offload_level = 0.8
    # decision.reason = "需要深度专业知识"
    ```
    """

    def __init__(self, config: Optional[OffloadStrategyConfig] = None):
        self.config = config or OffloadStrategyConfig()

        # 历史决策记录（用于自适应调整）
        self._decision_history: List[Dict] = []
        self._complexity_history: List[float] = []

        # 性能监控
        self._latency_by_decision: Dict[str, List[float]] = {
            "local": [],
            "hybrid": [],
            "expert": []
        }

        # 关键词模式
        self._technical_keywords = {
            # 编程
            "代码", "函数", "算法", "编程", "开发", "api",
            "class", "def ", "import", "async", "await",
            # 数学
            "计算", "公式", "方程", "矩阵", "概率", "统计",
            "积分", "微分", "函数", "算法",
            # 专业领域
            "医学", "法律", "金融", "物理", "化学", "生物",
            # 推理
            "分析", "推理", "论证", "证明", "解释", "原因",
            # 创意
            "创作", "写", "生成", "故事", "小说", "诗歌",
        }

        self._reasoning_keywords = [
            "为什么", "原因", "分析", "解释",
            "如何", "怎样", "方法", "步骤",
            "区别", "比较", "对比",
            "如果", "假设", "推理",
            "证明", "论证", "逻辑",
        ]

        logger.info("[AutoOffload] Strategy initialized")

    def evaluate_complexity(self, query: str) -> ComplexityMetrics:
        """
        评估查询复杂度

        返回详细的复杂度指标
        """
        metrics = ComplexityMetrics()

        # 基础文本特征
        metrics.query_length = len(query)
        metrics.sentence_count = self._count_sentences(query)

        # 词频统计
        words = query.split()
        if words:
            metrics.avg_word_length = statistics.mean(len(w) for w in words)

        # 技术术语计数
        metrics.technical_terms = sum(
            1 for kw in self._technical_keywords
            if kw in query
        )

        # 数字计数
        metrics.numbers_count = len(re.findall(r'\d+', query))

        # 问号数量
        metrics.question_marks = query.count('?') + query.count('？')

        # 复合句识别（分号、逗号连接）
        metrics.compound_sentences = query.count('；') + query.count(';')

        # 特殊模式识别
        metrics.has_code = bool(re.search(r'代码|function|class|def |```', query))
        metrics.has_math = bool(re.search(r'[=+\-*/^]|\^|sqrt|积分|微分', query))
        metrics.has_entity = bool(re.search(r'公司|组织|人物|事件|时间', query))

        # 创意/推理识别
        metrics.is_creative = any(kw in query for kw in ["创作", "写", "生成", "故事"])
        metrics.is_reasoning = any(kw in query for kw in self._reasoning_keywords)

        # 计算综合复杂度评分 (0-1)
        metrics.complexity_score = self._calculate_complexity_score(metrics, query)

        # 推理深度评估
        metrics.reasoning_depth = self._estimate_reasoning_depth(metrics, query)

        return metrics

    def _count_sentences(self, text: str) -> int:
        """估算句子数量"""
        # 中英文句号/问号/感叹号
        count = len(re.findall(r'[。！？.!?]+', text))
        return max(1, count)

    def _calculate_complexity_score(
        self,
        metrics: ComplexityMetrics,
        query: str
    ) -> float:
        """
        计算综合复杂度评分 (0-1)

        评分因素:
        - 长度权重: 30%
        - 技术术语权重: 25%
        - 推理特征权重: 25%
        - 特殊模式权重: 20%
        """
        # 1. 长度评分 (0-1)
        length_score = min(1.0, metrics.query_length / 500)  # 500字为满分

        # 2. 技术术语评分 (0-1)
        tech_score = min(1.0, metrics.technical_terms / 5)    # 5个术语为满分

        # 3. 推理特征评分 (0-1)
        reasoning_indicators = (
            metrics.is_reasoning * 0.4 +
            min(1.0, metrics.question_marks / 3) * 0.3 +
            min(1.0, metrics.compound_sentences / 3) * 0.3
        )

        # 4. 特殊模式评分
        special_score = (
            metrics.has_code * 0.3 +
            metrics.has_math * 0.3 +
            metrics.is_creative * 0.2 +
            (1 if metrics.reasoning_depth > 0.5 else 0) * 0.2
        )

        # 综合评分
        total_score = (
            length_score * 0.20 +
            tech_score * 0.30 +
            reasoning_indicators * 0.30 +
            special_score * 0.20
        )

        return round(total_score, 3)

    def _estimate_reasoning_depth(
        self,
        metrics: ComplexityMetrics,
        query: str
    ) -> float:
        """估计推理深度"""
        depth = 0.0

        # 简单推理指示
        if any(kw in query for kw in ["为什么", "原因", "如何"]):
            depth += 0.2

        # 多步骤推理指示
        if "首先" in query and "然后" in query:
            depth += 0.2
        if "第一" in query and ("第二" in query or "第三" in query):
            depth += 0.2

        # 复杂推理指示
        if any(kw in query for kw in ["分析", "论证", "证明"]):
            depth += 0.3

        # 极端复杂
        if any(kw in query for kw in ["证明", "推导", "计算", "数学"]):
            depth += 0.1

        return min(1.0, depth)

    def decide(
        self,
        query: str,
        metrics: Optional[ComplexityMetrics] = None,
        system_state: Optional[Dict[str, float]] = None,
        user_preference: Optional[str] = None,
        learning_mode: bool = False
    ) -> 'OffloadDecisionResult':
        """
        做出卸载决策

        Args:
            query: 用户查询
            metrics: 预计算的复杂度指标（可选）
            system_state: 系统状态 {"cpu_usage": 0-1, "memory_usage": 0-1}
            user_preference: 用户偏好 "fast", "balanced", "accurate"
            learning_mode: 是否启用学习模式

        Returns:
            OffloadDecisionResult
        """
        # 评估复杂度
        if metrics is None:
            metrics = self.evaluate_complexity(query)

        system_state = system_state or {}

        # ── 规则1: 强制本地 ─────────────────────────────────────
        for pattern in self.config.always_local_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return self._make_decision(
                    OffloadDecision.LOCAL_ONLY,
                    query,
                    metrics,
                    "匹配本地模式pattern",
                    learning_mode
                )

        # ── 规则2: 强制专家 ─────────────────────────────────────
        for pattern in self.config.always_expert_patterns:
            if re.search(pattern, query):
                return self._make_decision(
                    OffloadDecision.EXPERT_PRIMARY,
                    query,
                    metrics,
                    "匹配专家模式pattern",
                    learning_mode
                )

        # ── 规则3: 系统负载适应 ─────────────────────────────────
        load_penalty = 0.0
        if system_state:
            cpu = system_state.get("cpu_usage", 0.5)
            memory = system_state.get("memory_usage", 0.5)

            if cpu > 0.8 or memory > 0.85:
                load_penalty = 0.2  # 高负载时降低专家调用
            elif cpu > 0.6 or memory > 0.7:
                load_penalty = 0.1

        # ── 规则4: 用户偏好适应 ─────────────────────────────────
        preference_adjustment = 0.0
        if user_preference:
            if user_preference == "fast":
                preference_adjustment = -0.15  # 更快响应
            elif user_preference == "accurate":
                preference_adjustment = 0.15   # 更准确
            # "balanced" 无调整

        # ── 计算最终决策分数 ─────────────────────────────────────
        final_score = metrics.complexity_score - load_penalty + preference_adjustment

        # ── 根据阈值决策 ────────────────────────────────────────
        if final_score < self.config.local_threshold:
            decision = OffloadDecision.LOCAL_ONLY
            reason = "低复杂度，本地处理足够"

        elif final_score < self.config.hybrid_threshold:
            # 混合模式
            if learning_mode:
                # 学习模式下更倾向用专家
                decision = OffloadDecision.HYBRID
                reason = f"中等复杂度启用混合学习 (score={final_score:.2f})"
            else:
                decision = OffloadDecision.LOCAL_WITH_LEARNING
                reason = f"中等复杂度本地优先 (score={final_score:.2f})"

        elif final_score < self.config.expert_threshold:
            decision = OffloadDecision.HYBRID
            reason = f"较高复杂度混合处理 (score={final_score:.2f})"

        else:
            decision = OffloadDecision.EXPERT_PRIMARY
            reason = f"高复杂度需要专家支持 (score={final_score:.2f})"

        # 记录历史
        self._record_decision(query, metrics, decision, final_score)

        return self._make_decision(decision, query, metrics, reason, learning_mode)

    def _make_decision(
        self,
        decision: OffloadDecision,
        query: str,
        metrics: ComplexityMetrics,
        reason: str,
        learning_mode: bool
    ) -> 'OffloadDecisionResult':
        """构建决策结果"""

        # 计算推荐模型层级
        if decision == OffloadDecision.LOCAL_ONLY:
            recommended_model = "L0"
            offload_ratio = 0.0
        elif decision == OffloadDecision.LOCAL_WITH_LEARNING:
            recommended_model = "L1"
            offload_ratio = 0.1
        elif decision == OffloadDecision.HYBRID:
            recommended_model = "L3"
            offload_ratio = 0.5
        elif decision == OffloadDecision.EXPERT_PRIMARY:
            recommended_model = "L4"
            offload_ratio = 0.8
        else:
            recommended_model = "L4"
            offload_ratio = 1.0

        return OffloadDecisionResult(
            decision=decision,
            recommended_model=recommended_model,
            offload_ratio=offload_ratio,
            complexity_score=metrics.complexity_score,
            reasoning_depth=metrics.reasoning_depth,
            reason=reason,
            use_expert=decision in [
                OffloadDecision.HYBRID,
                OffloadDecision.EXPERT_PRIMARY,
                OffloadDecision.EXPERT_ONLY
            ],
            learn_from_expert=learning_mode or decision in [
                OffloadDecision.HYBRID,
                OffloadDecision.LOCAL_WITH_LEARNING
            ],
            metadata={
                "query_length": metrics.query_length,
                "technical_terms": metrics.technical_terms,
                "is_reasoning": metrics.is_reasoning,
                "has_code": metrics.has_code,
            }
        )

    def _record_decision(
        self,
        query: str,
        metrics: ComplexityMetrics,
        decision: OffloadDecision,
        score: float
    ):
        """记录决策历史"""
        self._decision_history.append({
            "timestamp": time.time(),
            "query": query[:50],
            "score": score,
            "decision": decision.value
        })

        self._complexity_history.append(score)

        # 保持历史记录在合理范围
        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-500:]
            self._complexity_history = self._complexity_history[-500:]

    def get_stats(self) -> Dict[str, Any]:
        """获取策略统计"""
        if not self._decision_history:
            return {"message": "No decisions recorded yet"}

        recent = self._decision_history[-100:] if len(self._decision_history) > 100 else self._decision_history

        decision_counts = {}
        for d in recent:
            dv = d["decision"]
            decision_counts[dv] = decision_counts.get(dv, 0) + 1

        return {
            "total_decisions": len(self._decision_history),
            "recent_decisions": len(recent),
            "decision_distribution": decision_counts,
            "avg_complexity_score": statistics.mean(self._complexity_history[-100:]) if self._complexity_history else 0,
            "current_thresholds": {
                "local": self.config.local_threshold,
                "hybrid": self.config.hybrid_threshold,
                "expert": self.config.expert_threshold,
            }
        }

    def adjust_thresholds(
        self,
        performance_feedback: Dict[str, float]
    ):
        """
        根据性能反馈自动调整阈值

        performance_feedback: {
            "local_accuracy": 0-1,
            "expert_accuracy": 0-1,
            "expert_latency_penalty": ms,
            ...
        }
        """
        if not self.config.auto_adjust_thresholds:
            return

        # 如果本地准确率高，可以提高本地阈值
        local_acc = performance_feedback.get("local_accuracy", 0.8)
        if local_acc > 0.9:
            self.config.local_threshold = min(0.5, self.config.local_threshold + 0.05)
        elif local_acc < 0.7:
            self.config.local_threshold = max(0.2, self.config.local_threshold - 0.05)

        # 如果专家延迟过高，可以降低专家阈值
        expert_latency = performance_feedback.get("expert_latency_penalty", 0)
        if expert_latency > 3000:  # 超过3秒
            self.config.expert_threshold = min(0.95, self.config.expert_threshold + 0.05)
        elif expert_latency < 1000:  # 低于1秒
            self.config.expert_threshold = max(0.7, self.config.expert_threshold - 0.05)

        logger.info(f"[AutoOffload] Thresholds adjusted: local<{self.config.local_threshold:.2f}, "
              f"hybrid<{self.config.hybrid_threshold:.2f}, expert<{self.config.expert_threshold:.2f}")


@dataclass
class OffloadDecisionResult:
    """卸载决策结果"""
    decision: OffloadDecision
    recommended_model: str           # "L0", "L1", "L3", "L4"
    offload_ratio: float              # 0-1, 卸载到专家的比例
    complexity_score: float           # 复杂度评分
    reasoning_depth: float             # 推理深度
    reason: str                        # 决策原因
    use_expert: bool                  # 是否使用专家
    learn_from_expert: bool           # 是否从专家学习
    metadata: Dict[str, Any]          # 额外元数据


# ── 便捷函数 ──────────────────────────────────────────────────────────────

_default_strategy: Optional[AutoOffloadStrategy] = None


def get_offload_strategy(config: Optional[OffloadStrategyConfig] = None) -> AutoOffloadStrategy:
    """获取默认卸载策略"""
    global _default_strategy
    if _default_strategy is None:
        _default_strategy = AutoOffloadStrategy(config)
    return _default_strategy


def quick_decide(
    query: str,
    system_state: Optional[Dict] = None,
    user_preference: str = "balanced"
) -> OffloadDecisionResult:
    """快速决策（一行代码）"""
    strategy = get_offload_strategy()
    return strategy.decide(
        query,
        system_state=system_state,
        user_preference=user_preference
    )
