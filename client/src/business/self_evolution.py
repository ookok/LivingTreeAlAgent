"""
Phase 3: 自主学习与进化系统
=============================

AI 原生 OS 的智能核心能力：
1. 从历史交互中自动学习
2. 自我评估与持续改进
3. 意图预测与主动建议
4. 知识图谱自动构建
5. 自适应压缩策略

Author: AI Native OS Team
"""

from __future__ import annotations

import re
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import defaultdict
from enum import Enum
from client.src.business.logger import get_logger
logger = get_logger('self_evolution')



# ============================================================================
# 进化状态与类型
# ============================================================================

class EvolutionStatus(Enum):
    """进化状态"""
    STABLE = "stable"           # 稳定
    LEARNING = "learning"       # 学习中
    IMPROVING = "improving"     # 改进中
    STAGNANT = "stagnant"       # 停滞
    ADAPTING = "adapting"       # 适应中


class LearningType(Enum):
    """学习类型"""
    SUPERVISED = "supervised"       # 监督学习
    REINFORCEMENT = "reinforcement" # 强化学习
    UNSUPERVISED = "unsupervised"   # 无监督学习
    IMITATION = "imitation"         # 模仿学习


class MetricType(Enum):
    """指标类型"""
    ACCURACY = "accuracy"           # 准确率
    LATENCY = "latency"            # 延迟
    MEMORY_USAGE = "memory_usage"  # 内存使用
    COMPRESSION_RATIO = "compression_ratio"  # 压缩率
    INTENT_RECOGNITION = "intent_recognition"  # 意图识别
    SATISFACTION = "satisfaction"  # 用户满意度


# ============================================================================
# 数据结构
# ============================================================================

class InteractionSample:
    """交互样本"""
    def __init__(
        self,
        sample_id: str = None,
        timestamp: str = None,
        query: str = "",
        context: str = "",
        code: str = "",
        intent_signature: Dict[str, Any] = None,
        compressed_context: str = "",
        verification_status: str = "unknown",
        action_taken: str = "",
        response: str = "",
        success: bool = False,
        user_feedback: str = "",
        feedback_score: float = 0.0,
        improvement: str = "",
        latency_ms: float = 0.0,
        tokens_used: int = 0,
        tags: List[str] = None
    ):
        self.sample_id = sample_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now().isoformat()
        self.query = query
        self.context = context
        self.code = code
        self.intent_signature = intent_signature or {}
        self.compressed_context = compressed_context
        self.verification_status = verification_status
        self.action_taken = action_taken
        self.response = response
        self.success = success
        self.user_feedback = user_feedback
        self.feedback_score = feedback_score
        self.improvement = improvement
        self.latency_ms = latency_ms
        self.tokens_used = tokens_used
        self.tags = tags or []


class PerformanceMetric:
    """性能指标"""
    def __init__(
        self,
        metric_id: str = None,
        twin_id: str = "",
        metric_type: str = "accuracy",
        value: float = 0.0,
        previous_value: float = 0.0,
        delta: float = 0.0,
        trend: str = "stable",
        timestamp: str = None,
        window_size: int = 10,
        min_value: float = 0.0,
        max_value: float = 0.0,
        avg_value: float = 0.0,
        std_value: float = 0.0
    ):
        self.metric_id = metric_id or str(uuid.uuid4())
        self.twin_id = twin_id
        self.metric_type = metric_type
        self.value = value
        self.previous_value = previous_value
        self.delta = delta
        self.trend = trend
        self.timestamp = timestamp or datetime.now().isoformat()
        self.window_size = window_size
        self.min_value = min_value
        self.max_value = max_value
        self.avg_value = avg_value
        self.std_value = std_value


class KnowledgePattern:
    """知识模式"""
    def __init__(
        self,
        pattern_id: str = None,
        pattern_type: str = "intent",
        pattern_text: str = "",
        pattern_hash: str = "",
        occurrence_count: int = 0,
        success_count: int = 0,
        failure_count: int = 0,
        success_rate: float = 0.0,
        first_seen: str = None,
        last_seen: str = None,
        related_patterns: List[str] = None,
        context_patterns: List[str] = None,
        confidence: float = 0.5,
        importance: float = 0.5
    ):
        self.pattern_id = pattern_id or str(uuid.uuid4())
        self.pattern_type = pattern_type
        self.pattern_text = pattern_text
        self.pattern_hash = pattern_hash
        self.occurrence_count = occurrence_count
        self.success_count = success_count
        self.failure_count = failure_count
        self.success_rate = success_rate
        self.first_seen = first_seen or datetime.now().isoformat()
        self.last_seen = last_seen or datetime.now().isoformat()
        self.related_patterns = related_patterns or []
        self.context_patterns = context_patterns or []
        self.confidence = confidence
        self.importance = importance




class EvolutionStrategy:
    """进化策略"""
    def __init__(
        self,
        strategy_id: str = None,
        name: str = "",
        description: str = "",
        target_metrics: List[str] = None,
        learning_rate: float = 0.1,
        exploration_rate: float = 0.2,
        discount_factor: float = 0.9,
        is_active: bool = False,
        effectiveness_score: float = 0.0,
        trials: int = 0,
        successes: int = 0,
        last_tested: str = ""
    ):
        self.strategy_id = strategy_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.target_metrics = target_metrics or []
        self.learning_rate = learning_rate
        self.exploration_rate = exploration_rate
        self.discount_factor = discount_factor
        self.is_active = is_active
        self.effectiveness_score = effectiveness_score
        self.trials = trials
        self.successes = successes
        self.last_tested = last_tested


# ============================================================================
# 核心类
# ============================================================================


class SelfLearningEngine:
    """自主学习引擎"""
    
    def __init__(self, twin_id: str):
        self.twin_id = twin_id
        
        # 样本存储
        self.samples: List[InteractionSample] = []
        self.max_samples = 10000
        
        # 指标跟踪
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.metric_history: List[PerformanceMetric] = []
        
        # 知识模式
        self.patterns: Dict[str, KnowledgePattern] = {}
        
        # 进化策略
        self.strategies: List[EvolutionStrategy] = []
        self.current_strategy: Optional[EvolutionStrategy] = None
        
        # 状态
        self.evolution_status = EvolutionStatus.STABLE
        self.learning_type = LearningType.REINFORCEMENT
        
        # 配置
        self.min_samples_for_learning = 10
        self.improvement_threshold = 0.05
        
    def add_sample(self, sample: InteractionSample) -> None:
        """添加交互样本"""
        self.samples.append(sample)
        
        # 限制样本数量
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]
        
        # 更新指标
        self._update_metrics(sample)
        
        # 学习模式
        if len(self.samples) >= self.min_samples_for_learning:
            self._learn_from_sample(sample)
    
    def _update_metrics(self, sample: InteractionSample) -> None:
        """更新指标"""
        # 准确率
        if sample.success:
            self.metrics["accuracy"].append(1.0)
        else:
            self.metrics["accuracy"].append(0.0)
        
        # 延迟
        if sample.latency_ms > 0:
            self.metrics["latency"].append(sample.latency_ms)
        
        # 压缩率
        if sample.context and sample.compressed_context:
            ratio = len(sample.compressed_context) / len(sample.context)
            self.metrics["compression_ratio"].append(ratio)
        
        # 满意度
        self.metrics["satisfaction"].append(sample.feedback_score)
        
        # 保持最近 N 个指标
        for key in self.metrics:
            if len(self.metrics[key]) > 100:
                self.metrics[key] = self.metrics[key][-100:]
    
    def _learn_from_sample(self, sample: InteractionSample) -> None:
        """从样本学习"""
        if sample.intent_signature:
            self._learn_intent_pattern(sample)
        
        if sample.code:
            self._learn_code_pattern(sample)
        
        if sample.success:
            self._reinforce_success_pattern(sample)
        else:
            self._learn_from_failure(sample)
    
    def _learn_intent_pattern(self, sample: InteractionSample) -> None:
        """学习意图模式"""
        intent_type = sample.intent_signature.get("type", "unknown")
        intent_action = sample.intent_signature.get("action", "")
        
        pattern_key = f"intent:{intent_type}:{intent_action}"
        
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            pattern.occurrence_count += 1
            pattern.last_seen = sample.timestamp
            if sample.success:
                pattern.success_count += 1
                pattern.success_rate = pattern.success_count / pattern.occurrence_count
        else:
            self.patterns[pattern_key] = KnowledgePattern(
                pattern_type="intent",
                pattern_text=pattern_key,
                pattern_hash=hashlib.md5(pattern_key.encode()).hexdigest(),
                occurrence_count=1,
                success_count=1 if sample.success else 0,
                failure_count=0 if sample.success else 1,
                success_rate=1.0 if sample.success else 0.0,
                confidence=0.5
            )
    
    def _learn_code_pattern(self, sample: InteractionSample) -> None:
        """学习代码模式"""
        # 提取函数/类名
        functions = re.findall(r'def\s+(\w+)|class\s+(\w+)', sample.code)
        
        for func in functions:
            func_name = func[0] or func[1]
            pattern_key = f"code:{func_name}"
            
            if pattern_key in self.patterns:
                pattern = self.patterns[pattern_key]
                pattern.occurrence_count += 1
                if sample.success:
                    pattern.success_count += 1
            else:
                self.patterns[pattern_key] = KnowledgePattern(
                    pattern_type="code",
                    pattern_text=pattern_key,
                    pattern_hash=hashlib.md5(pattern_key.encode()).hexdigest(),
                    occurrence_count=1,
                    success_count=1 if sample.success else 0
                )
    
    def _reinforce_success_pattern(self, sample: InteractionSample) -> None:
        """强化成功模式"""
        # 增加相关模式的置信度
        if sample.intent_signature:
            intent_type = sample.intent_signature.get("type", "unknown")
            pattern_key = f"intent:{intent_type}"
            
            if pattern_key in self.patterns:
                pattern = self.patterns[pattern_key]
                # 强化学习: 缓慢增加置信度
                pattern.confidence = min(1.0, pattern.confidence + 0.05)
                pattern.success_count += 1
                pattern.occurrence_count += 1
                pattern.success_rate = pattern.success_count / pattern.occurrence_count
    
    def _learn_from_failure(self, sample: InteractionSample) -> None:
        """从失败中学习"""
        # 记录失败模式
        if sample.intent_signature:
            intent_type = sample.intent_signature.get("type", "unknown")
            pattern_key = f"intent:{intent_type}"
            
            if pattern_key in self.patterns:
                pattern = self.patterns[pattern_key]
                # 降低置信度
                pattern.confidence = max(0.1, pattern.confidence - 0.1)
                pattern.failure_count += 1
                pattern.occurrence_count += 1
                pattern.success_rate = pattern.success_count / pattern.occurrence_count
    
    def predict_intent(self, query: str) -> Dict[str, Any]:
        """预测意图"""
        # 简单规则匹配
        intent = {
            "type": "unknown",
            "action": "unknown",
            "confidence": 0.0
        }
        
        # 查询分析
        query_lower = query.lower()
        
        # 动作识别
        if any(k in query_lower for k in ["create", "create", "新建", "创建"]):
            intent["action"] = "create"
        elif any(k in query_lower for k in ["modify", "update", "edit", "修改", "编辑"]):
            intent["action"] = "modify"
        elif any(k in query_lower for k in ["delete", "remove", "删除", "移除"]):
            intent["action"] = "delete"
        elif any(k in query_lower for k in ["search", "find", "查询", "搜索", "查找"]):
            intent["action"] = "search"
        elif any(k in query_lower for k in ["explain", "understand", "理解", "解释"]):
            intent["action"] = "understand"
        else:
            intent["action"] = "general"
        
        # 类型识别
        if any(k in query_lower for k in ["class", "function", "method", "类", "函数"]):
            intent["type"] = "code"
        elif any(k in query_lower for k in ["test", "测试", "unit"]):
            intent["type"] = "test"
        elif any(k in query_lower for k in ["document", "doc", "文档"]):
            intent["type"] = "document"
        elif any(k in query_lower for k in ["bug", "error", "issue", "bug", "错误"]):
            intent["type"] = "debug"
        else:
            intent["type"] = "general"
        
        # 查找历史模式
        pattern_key = f"intent:{intent['type']}:{intent['action']}"
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            intent["confidence"] = pattern.confidence
            intent["success_rate"] = pattern.success_rate
            intent["occurrence_count"] = pattern.occurrence_count
        else:
            intent["confidence"] = 0.5
        
        return intent
    
    def suggest_context(self, intent: Dict[str, Any]) -> List[str]:
        """建议相关上下文"""
        suggestions = []
        
        intent_type = intent.get("type", "unknown")
        intent_action = intent.get("action", "")
        
        # 基于意图查找相关模式
        pattern_key = f"intent:{intent_type}:{intent_action}"
        
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            
            # 高频成功的相关模式
            related_patterns = pattern.related_patterns[:3]
            suggestions.extend(related_patterns)
        
        # 查找同类型的其他成功模式
        for pattern_id, pattern in self.patterns.items():
            if pattern.pattern_type == "intent" and pattern.pattern_type == "code":
                if pattern.success_rate > 0.7 and pattern.occurrence_count > 5:
                    suggestions.append(pattern.pattern_text)
        
        # 去重并限制数量
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
        
        return unique_suggestions[:5]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        summary = {
            "total_samples": len(self.samples),
            "evolution_status": self.evolution_status.value,
            "patterns_learned": len(self.patterns),
            "metrics": {}
        }
        
        # 计算各指标统计
        for metric_name, values in self.metrics.items():
            if values:
                summary["metrics"][metric_name] = {
                    "current": values[-1] if values else 0,
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "trend": self._calculate_trend(values)
                }
        
        return summary
    
    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势"""
        if len(values) < 2:
            return "stable"
        
        # 最近 5 个值
        recent = values[-5:] if len(values) >= 5 else values
        
        # 计算斜率
        n = len(recent)
        if n < 2:
            return "stable"
        
        # 简单趋势判断
        first_half = sum(recent[:n//2]) / (n//2)
        second_half = sum(recent[n//2:]) / (n - n//2)
        
        if second_half > first_half * 1.05:
            return "up"
        elif second_half < first_half * 0.95:
            return "down"
        else:
            return "stable"
    
    def evolve(self) -> Dict[str, Any]:
        """执行进化"""
        self.evolution_status = EvolutionStatus.IMPROVING
        
        evolution_result = {
            "status": "completed",
            "improvements": [],
            "new_patterns": 0,
            "optimized_strategies": 0
        }
        
        # 检查停滞
        accuracy_trend = self._calculate_trend(self.metrics.get("accuracy", []))
        if accuracy_trend == "stable" and len(self.metrics.get("accuracy", [])) > 20:
            self.evolution_status = EvolutionStatus.STAGNANT
            evolution_result["improvements"].append({
                "type": "stagnation_detected",
                "action": "increase_exploration"
            })
        
        # 检查是否需要适应
        if len(self.samples) > 100:
            recent_accuracy = self.metrics.get("accuracy", [])[-20:]
            if recent_accuracy and sum(recent_accuracy) / len(recent_accuracy) < 0.7:
                self.evolution_status = EvolutionStatus.ADAPTING
                evolution_result["improvements"].append({
                    "type": "low_accuracy",
                    "action": "adjust_parameters"
                })
        
        # 清理低质量模式
        patterns_before = len(self.patterns)
        self.patterns = {
            k: v for k, v in self.patterns.items()
            if v.occurrence_count >= 2 or v.confidence > 0.3
        }
        patterns_removed = patterns_before - len(self.patterns)
        
        if patterns_removed > 0:
            evolution_result["improvements"].append({
                "type": "pattern_cleanup",
                "count": patterns_removed
            })
        
        # 合并相似模式
        self._merge_similar_patterns()
        
        self.evolution_status = EvolutionStatus.STABLE
        
        return evolution_result
    
    def _merge_similar_patterns(self) -> None:
        """合并相似模式"""
        # 基于哈希相似度合并
        pattern_list = list(self.patterns.items())
        
        for i, (key1, pattern1) in enumerate(pattern_list):
            for key2, pattern2 in pattern_list[i+1:]:
                # 检查是否相似
                if pattern1.pattern_type == pattern2.pattern_type:
                    # 合并高相似度模式
                    if pattern1.confidence > pattern2.confidence:
                        pattern1.occurrence_count += pattern2.occurrence_count
                        pattern1.success_count += pattern2.success_count
                        pattern1.failure_count += pattern2.failure_count
                        pattern1.success_rate = pattern1.success_count / pattern1.occurrence_count if pattern1.occurrence_count > 0 else 0
                        del self.patterns[key2]


class AdaptiveCompressionStrategy:
    """自适应压缩策略"""
    
    def __init__(self):
        self.strategies = {
            "aggressive": {
                "max_tokens_ratio": 0.1,
                "preserve_structure": False,
                "aggressive_deduplication": True
            },
            "balanced": {
                "max_tokens_ratio": 0.2,
                "preserve_structure": True,
                "aggressive_deduplication": False
            },
            "conservative": {
                "max_tokens_ratio": 0.3,
                "preserve_structure": True,
                "aggressive_deduplication": False
            }
        }
        
        self.current_strategy = "balanced"
        self.performance_history: Dict[str, List[float]] = defaultdict(list)
    
    def select_strategy(self, intent: Dict[str, Any], 
                       context_history: List[Dict]) -> str:
        """选择压缩策略"""
        intent_type = intent.get("type", "general")
        intent_action = intent.get("action", "general")
        
        # 基于意图选择
        if intent_type in ["code", "debug"]:
            return "conservative"  # 代码需要保留更多细节
        elif intent_type in ["test"]:
            return "aggressive"   # 测试可以更激进
        else:
            return "balanced"
    
    def adjust_strategy(self, strategy_name: str, success: bool) -> None:
        """根据结果调整策略"""
        if strategy_name not in self.performance_history:
            self.performance_history[strategy_name] = []
        
        self.performance_history[strategy_name].append(1.0 if success else 0.0)
        
        # 保持最近 20 个结果
        if len(self.performance_history[strategy_name]) > 20:
            self.performance_history[strategy_name] = \
                self.performance_history[strategy_name][-20:]
        
        # 切换到成功率更高的策略
        best_strategy = max(
            self.performance_history.keys(),
            key=lambda k: sum(self.performance_history[k]) / len(self.performance_history[k])
            if self.performance_history[k] else 0
        )
        
        if best_strategy != self.current_strategy:
            self.current_strategy = best_strategy
    
    def get_current_strategy(self) -> Dict[str, Any]:
        """获取当前策略配置"""
        return {
            "name": self.current_strategy,
            "config": self.strategies[self.current_strategy],
            "performance": {
                k: sum(v) / len(v) if v else 0
                for k, v in self.performance_history.items()
            }
        }


class EvolutionController:
    """进化控制器"""
    
    def __init__(self, twin_id: str):
        self.twin_id = twin_id
        
        # 组件
        self.learning_engine = SelfLearningEngine(twin_id)
        self.compression_strategy = AdaptiveCompressionStrategy()
        
        # 进化周期
        self.evolution_interval = 100  # 每 N 个样本执行一次进化
        self.last_evolution_count = 0
        
        # 知识图谱
        self.knowledge_graph: Dict[str, List[str]] = defaultdict(list)
        
    def process_and_learn(self, query: str, context: str, code: str,
                          response: str, success: bool,
                          feedback_score: float = 0.0) -> Dict[str, Any]:
        """处理交互并学习"""
        # 预测意图
        intent = self.learning_engine.predict_intent(query)
        
        # 选择压缩策略
        strategy_name = self.compression_strategy.select_strategy(
            intent, 
            []  # 上下文历史
        )
        
        # 创建样本
        sample = InteractionSample(
            query=query,
            context=context,
            code=code,
            intent_signature=intent,
            action_taken=strategy_name,
            response=response,
            success=success,
            feedback_score=feedback_score
        )
        
        # 学习
        self.learning_engine.add_sample(sample)
        
        # 更新压缩策略
        self.compression_strategy.adjust_strategy(strategy_name, success)
        
        # 检查是否需要进化
        should_evolve = (
            len(self.learning_engine.samples) - self.last_evolution_count 
            >= self.evolution_interval
        )
        
        evolution_result = {}
        if should_evolve:
            evolution_result = self.learning_engine.evolve()
            self.last_evolution_count = len(self.learning_engine.samples)
        
        # 建议上下文
        context_suggestions = self.learning_engine.suggest_context(intent)
        
        return {
            "intent": intent,
            "compression_strategy": strategy_name,
            "context_suggestions": context_suggestions,
            "performance_summary": self.learning_engine.get_performance_summary(),
            "evolution_result": evolution_result
        }
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """获取学习洞察"""
        insights = {
            "patterns": [],
            "recommendations": [],
            "performance": self.learning_engine.get_performance_summary()
        }
        
        # 高价值模式
        high_value_patterns = [
            p for p in self.learning_engine.patterns.values()
            if p.success_rate > 0.8 and p.occurrence_count >= 5
        ]
        
        for pattern in sorted(high_value_patterns, 
                              key=lambda x: x.success_rate * x.occurrence_count,
                              reverse=True)[:5]:
            insights["patterns"].append({
                "type": pattern.pattern_type,
                "text": pattern.pattern_text,
                "success_rate": pattern.success_rate,
                "confidence": pattern.confidence
            })
        
        # 改进建议
        performance = insights["performance"]
        
        if performance["metrics"].get("accuracy", {}).get("trend") == "down":
            insights["recommendations"].append(
                "准确率下降，建议检查最近的失败案例"
            )
        
        if performance["metrics"].get("latency", {}).get("current", 0) > 5000:
            insights["recommendations"].append(
                "延迟较高，考虑优化压缩策略"
            )
        
        if performance["patterns_learned"] == 0:
            insights["recommendations"].append(
                "还没有学习到足够的模式，继续使用以积累经验"
            )
        
        return insights


# ============================================================================
# 便捷函数
# ============================================================================

def create_evolution_controller(twin_id: str) -> EvolutionController:
    """创建进化控制器"""
    return EvolutionController(twin_id)


def quick_learn(twin_id: str, query: str, success: bool,
                feedback_score: float = 0.0) -> Dict[str, Any]:
    """快速学习"""
    controller = EvolutionController(twin_id)
    return controller.process_and_learn(
        query=query,
        context="",
        code="",
        response="",
        success=success,
        feedback_score=feedback_score
    )


def get_learning_insights(twin_id: str) -> Dict[str, Any]:
    """获取学习洞察"""
    controller = EvolutionController(twin_id)
    return controller.get_learning_insights()


def predict_and_suggest(twin_id: str, query: str) -> Dict[str, Any]:
    """预测并建议"""
    controller = EvolutionController(twin_id)
    intent = controller.learning_engine.predict_intent(query)
    suggestions = controller.learning_engine.suggest_context(intent)
    
    return {
        "predicted_intent": intent,
        "context_suggestions": suggestions
    }


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("[TEST] Phase 3: Self-Learning and Evolution System")
    logger.info("=" * 60)
    
    # Test 1: Create Evolution Controller
    logger.info("\n[Test 1] Create Evolution Controller")
    controller = create_evolution_controller("twin_001")
    logger.info(f"  Twin ID: {controller.twin_id}")
    logger.info(f"  Status: {controller.evolution_status.value}")
    
    # Test 2: Process and Learn
    logger.info("\n[Test 2] Process and Learn")
    test_samples = [
        ("create a user manager class", True, 0.8),
        ("add login method", True, 0.9),
        ("implement logout", True, 0.7),
        ("fix the bug in login", False, -0.2),
        ("add password reset", True, 0.6),
    ]
    
    for query, success, score in test_samples:
        result = controller.process_and_learn(
            query=query,
            context="Python code context",
            code="class UserManager:\n    def login(self):\n        pass",
            response="Action completed",
            success=success,
            feedback_score=score
        )
        logger.info(f"  Query: {query[:30]}...")
        logger.info(f"    Intent: {result['intent']['type']}/{result['intent']['action']}")
        logger.info(f"    Strategy: {result['compression_strategy']}")
        logger.info(f"    Success: {success}")
    
    # Test 3: Get Performance Summary
    logger.info("\n[Test 3] Performance Summary")
    summary = controller.learning_engine.get_performance_summary()
    logger.info(f"  Total Samples: {summary['total_samples']}")
    logger.info(f"  Patterns Learned: {summary['patterns_learned']}")
    logger.info(f"  Status: {summary['evolution_status']}")
    
    for metric_name, metric_data in summary.get("metrics", {}).items():
        logger.info(f"  {metric_name}: {metric_data}")
    
    # Test 4: Predict Intent
    logger.info("\n[Test 4] Intent Prediction")
    predictions = [
        "create a new database connection",
        "fix the authentication error",
        "write unit tests for the service"
    ]
    
    for query in predictions:
        intent = controller.learning_engine.predict_intent(query)
        logger.info(f"  Query: {query}")
        logger.info(f"    Predicted: {intent['type']}/{intent['action']}")
        logger.info(f"    Confidence: {intent['confidence']:.2f}")
    
    # Test 5: Context Suggestions
    logger.info("\n[Test 5] Context Suggestions")
    intent = {"type": "code", "action": "create"}
    suggestions = controller.learning_engine.suggest_context(intent)
    logger.info(f"  Intent: {intent}")
    logger.info(f"  Suggestions: {suggestions}")
    
    # Test 6: Learning Insights
    logger.info("\n[Test 6] Learning Insights")
    insights = controller.get_learning_insights()
    logger.info(f"  Patterns Found: {len(insights['patterns'])}")
    for pattern in insights.get("patterns", [])[:3]:
        logger.info(f"    {pattern['type']}: {pattern['text']}")
        logger.info(f"      Success Rate: {pattern['success_rate']:.2f}")
    
    logger.info(f"  Recommendations: {len(insights['recommendations'])}")
    for rec in insights.get("recommendations", []):
        logger.info(f"    - {rec}")
    
    # Test 7: Quick Learn
    logger.info("\n[Test 7] Quick Learn")
    result = quick_learn("twin_002", "optimize database query", True, 0.9)
    logger.info(f"  Intent: {result['intent']['type']}/{result['intent']['action']}")
    logger.info(f"  Suggestions: {result['context_suggestions']}")
    
    # Test 8: Predict and Suggest
    logger.info("\n[Test 8] Predict and Suggest")
    result = predict_and_suggest("twin_003", "implement caching layer")
    logger.info(f"  Predicted Intent: {result['predicted_intent']}")
    logger.info(f"  Context Suggestions: {result['context_suggestions']}")
    
    # Test 9: Adaptive Compression Strategy
    logger.info("\n[Test 9] Adaptive Compression Strategy")
    strategy = AdaptiveCompressionStrategy()
    
    intents = [
        {"type": "code", "action": "create"},
        {"type": "test", "action": "create"},
        {"type": "general", "action": "understand"}
    ]
    
    for intent in intents:
        selected = strategy.select_strategy(intent, [])
        logger.info(f"  Intent: {intent} -> Strategy: {selected}")
    
    # Test 10: Evolution Trigger
    logger.info("\n[Test 10] Evolution Trigger")
    for i in range(105):
        controller.process_and_learn(
            query=f"test query {i}",
            context="",
            code="",
            response="",
            success=i % 10 < 8,
            feedback_score=0.5
        )
    
    logger.info(f"  Total samples processed: {len(controller.learning_engine.samples)}")
    logger.info(f"  Evolution triggered: {len(controller.learning_engine.samples) >= 100}")
    
    logger.info("\n" + "=" * 60)
    logger.info("[COMPLETE] Phase 3 Tests")
    logger.info("=" * 60)
