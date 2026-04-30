"""
性能监控 + 自动调优仪表板
==========================

实时追踪系统性能指标，支持自动调优建议

核心指标:
- 专家调用率 (Expert Call Rate)
- 响应速度 (Response Speed)
- 准确率 (Accuracy)
- 缓存命中率 (Cache Hit Rate)
- 学习效率 (Learning Efficiency)

自动调优:
- 根据历史数据推荐配置调整
- 预测性能趋势
- 生成优化建议
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections import deque, defaultdict
from datetime import datetime, timedelta
import statistics

from enum import Enum
from business.logger import get_logger
logger = get_logger('expert_learning.performance_monitor')



class MetricType(Enum):
    """指标类型"""
    LATENCY = "latency"           # 延迟 (ms)
    ACCURACY = "accuracy"          # 准确率
    THROUGHPUT = "throughput"     # 吞吐量 (req/s)
    CACHE_HIT = "cache_hit"        # 缓存命中率
    EXPERT_USAGE = "expert_usage" # 专家调用率
    ERROR_RATE = "error_rate"      # 错误率


@dataclass
class MetricPoint:
    """单条指标数据点"""
    timestamp: float
    value: float
    metric_type: MetricType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    period: str                          # 时间窗口描述
    start_time: datetime
    end_time: datetime

    # 核心指标
    total_requests: int = 0
    expert_calls: int = 0
    local_calls: int = 0
    cache_hits: int = 0

    # 延迟统计 (ms)
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p90_latency: float = 0.0
    p99_latency: float = 0.0

    # 准确率统计
    avg_accuracy: float = 0.0
    total_corrections: int = 0

    # 错误统计
    total_errors: int = 0
    error_rate: float = 0.0

    # 趋势数据
    latency_trend: str = "stable"  # "improving", "stable", "degrading"
    accuracy_trend: str = "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_requests": self.total_requests,
            "expert_calls": self.expert_calls,
            "local_calls": self.local_calls,
            "expert_rate": f"{self.expert_calls / max(1, self.total_requests) * 100:.1f}%",
            "cache_hit_rate": f"{self.cache_hits / max(1, self.total_requests) * 100:.1f}%",
            "avg_latency_ms": f"{self.avg_latency:.1f}",
            "p50_latency_ms": f"{self.p50_latency:.1f}",
            "p90_latency_ms": f"{self.p90_latency:.1f}",
            "p99_latency_ms": f"{self.p99_latency:.1f}",
            "accuracy": f"{self.avg_accuracy * 100:.1f}%",
            "corrections": self.total_corrections,
            "error_rate": f"{self.error_rate * 100:.2f}%",
            "latency_trend": self.latency_trend,
            "accuracy_trend": self.accuracy_trend,
        }


@dataclass
class TuningRecommendation:
    """调优建议"""
    category: str              # "cache", "model", "routing", "context"
    priority: int               # 1-5, 1=最高
    issue: str                  # 发现的问题
    current_value: Any          # 当前值
    recommended_value: Any      # 推荐值
    expected_improvement: str   # 预期改善
    confidence: float           # 置信度 0-1


class PerformanceMonitor:
    """
    性能监控器 - 实时追踪 + 自动调优建议

    使用示例:
    ```python
    monitor = PerformanceMonitor()

    # 记录请求
    monitor.record_request(
        query="测试问题",
        latency_ms=150,
        source="expert",
        cache_hit=True,
        accuracy=0.92,
        error=None
    )

    # 获取性能快照
    snapshot = monitor.get_snapshot(period="1h")

    # 获取调优建议
    recommendations = monitor.get_recommendations()
    ```
    """

    def __init__(
        self,
        window_size: int = 1000,
        enable_auto_tuning: bool = True
    ):
        self._lock = threading.RLock()

        # 数据窗口
        self._window_size = window_size
        self._requests: deque = deque(maxlen=window_size)
        self._latencies: deque = deque(maxlen=window_size)
        self._accuracies: deque = deque(maxlen=window_size)

        # 分类统计
        self._expert_calls = 0
        self._local_calls = 0
        self._cache_hits = 0
        self._corrections = 0
        self._errors = 0

        # 按领域分类
        self._domain_stats: Dict[str, Dict] = defaultdict(lambda: {
            "requests": 0,
            "expert": 0,
            "local": 0,
            "cache_hit": 0,
            "avg_latency": 0,
            "accuracies": []
        })

        # 按意图分类
        self._intent_stats: Dict[str, Dict] = defaultdict(lambda: {
            "requests": 0,
            "expert": 0,
            "local": 0,
            "cache_hit": 0
        })

        # 时序数据（用于趋势分析）
        self._hourly_stats: Dict[str, List[float]] = defaultdict(list)
        self._daily_stats: Dict[str, List[float]] = defaultdict(list)

        # 自动调优
        self._enable_auto_tuning = enable_auto_tuning
        self._tuning_history: List[TuningRecommendation] = []
        self._last_tuning_check = time.time()

        # 回调函数
        self._on_anomaly: Optional[Callable] = None
        self._on_threshold_exceeded: Optional[Callable] = None

        # 阈值配置
        self._thresholds = {
            "latency_p99_ms": 5000,      # P99 延迟阈值
            "error_rate": 0.05,          # 错误率阈值
            "expert_rate": 0.80,         # 专家调用率过高阈值
            "cache_hit_min": 0.30,       # 缓存命中率最低要求
        }

        logger.info("[PerformanceMonitor] Performance monitoring enabled")

    def record_request(
        self,
        query: str,
        latency_ms: float,
        source: str,  # "expert", "local", "cache"
        cache_hit: bool = False,
        accuracy: Optional[float] = None,
        correction: bool = False,
        error: Optional[str] = None,
        domain: Optional[str] = None,
        intent: Optional[str] = None,
        reasoning_steps: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """记录一次请求"""
        with self._lock:
            now = time.time()
            ts = datetime.now()

            # 基础统计
            self._requests.append({
                "timestamp": now,
                "query": query,
                "latency_ms": latency_ms,
                "source": source,
                "cache_hit": cache_hit,
                "accuracy": accuracy,
                "correction": correction,
                "error": error,
                "domain": domain,
                "intent": intent,
                "reasoning_steps": reasoning_steps,
                "metadata": metadata or {}
            })

            # 延迟记录
            self._latencies.append(latency_ms)

            # 准确率记录
            if accuracy is not None:
                self._accuracies.append(accuracy)

            # 分类统计
            if source == "expert":
                self._expert_calls += 1
            elif source == "local":
                self._local_calls += 1

            if cache_hit:
                self._cache_hits += 1

            if correction:
                self._corrections += 1

            if error:
                self._errors += 1

            # 领域统计
            if domain:
                stats = self._domain_stats[domain]
                stats["requests"] += 1
                stats["source"] = source
                stats["cache_hit"] += 1 if cache_hit else 0
                stats["avg_latency"] = (
                    (stats["avg_latency"] * (stats["requests"] - 1) + latency_ms)
                    / stats["requests"]
                )
                if accuracy is not None:
                    stats["accuracies"].append(accuracy)

            # 意图统计
            if intent:
                stats = self._intent_stats[intent]
                stats["requests"] += 1
                if source == "expert":
                    stats["expert"] += 1
                elif source == "local":
                    stats["local"] += 1
                if cache_hit:
                    stats["cache_hit"] += 1

            # 时序数据（每小时/每天）
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            day_key = ts.strftime("%Y-%m-%d")

            self._hourly_stats[hour_key].append(latency_ms)
            self._daily_stats[day_key].append(latency_ms)

            # 检查异常
            self._check_anomalies(latency_ms, error)

    def _check_anomalies(self, latency_ms: float, error: Optional[str]):
        """检查异常情况"""
        if self._on_anomaly and len(self._latencies) >= 10:
            recent = list(self._latencies)[-10:]
            avg = statistics.mean(recent)
            std = statistics.stdev(recent) if len(recent) > 1 else 0

            # 延迟异常（超过均值+2倍标准差）
            if std > 0 and latency_ms > avg + 2 * std:
                self._on_anomaly({
                    "type": "latency_spike",
                    "value": latency_ms,
                    "expected": avg,
                    "deviation": (latency_ms - avg) / std
                })

        if error and self._on_threshold_exceeded:
            # 检查错误率
            error_rate = self._errors / max(1, self.total_requests)
            if error_rate > self._thresholds["error_rate"]:
                self._on_threshold_exceeded({
                    "type": "error_rate_high",
                    "value": error_rate,
                    "threshold": self._thresholds["error_rate"]
                })

    @property
    def total_requests(self) -> int:
        return len(self._requests)

    def get_snapshot(
        self,
        period: str = "1h"
    ) -> PerformanceSnapshot:
        """
        获取性能快照

        Args:
            period: 时间窗口 "5m", "15m", "1h", "24h", "7d"

        Returns:
            PerformanceSnapshot
        """
        with self._lock:
            now = time.time()

            # 计算时间窗口
            period_seconds = {
                "5m": 300,
                "15m": 900,
                "1h": 3600,
                "24h": 86400,
                "7d": 604800
            }.get(period, 3600)

            start_time = datetime.fromtimestamp(now - period_seconds)
            end_time = datetime.fromtimestamp(now)

            # 过滤时间窗口内的请求
            window_requests = [
                r for r in self._requests
                if r["timestamp"] >= now - period_seconds
            ]

            if not window_requests:
                return PerformanceSnapshot(
                    period=period,
                    start_time=start_time,
                    end_time=end_time
                )

            # 计算统计
            latencies = [r["latency_ms"] for r in window_requests]
            accuracies = [r["accuracy"] for r in window_requests if r["accuracy"] is not None]

            expert_calls = sum(1 for r in window_requests if r["source"] == "expert")
            local_calls = sum(1 for r in window_requests if r["source"] == "local")
            cache_hits = sum(1 for r in window_requests if r["cache_hit"])
            errors = sum(1 for r in window_requests if r["error"])
            corrections = sum(1 for r in window_requests if r["correction"])

            # 延迟分位数
            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)

            def percentile(data, p):
                k = (len(data) - 1) * p
                f = int(k)
                c = f + 1 if f + 1 < len(data) else f
                return data[f] + (k - f) * (data[c] - data[f])

            # 计算趋势
            latency_trend = self._calculate_trend(self._hourly_stats, "latency")
            accuracy_trend = self._calculate_trend(self._hourly_stats, "accuracy")

            return PerformanceSnapshot(
                period=period,
                start_time=start_time,
                end_time=end_time,
                total_requests=len(window_requests),
                expert_calls=expert_calls,
                local_calls=local_calls,
                cache_hits=cache_hits,
                avg_latency=statistics.mean(latencies),
                p50_latency=percentile(sorted_latencies, 0.50),
                p90_latency=percentile(sorted_latencies, 0.90),
                p99_latency=percentile(sorted_latencies, 0.99),
                avg_accuracy=statistics.mean(accuracies) if accuracies else 0.0,
                total_corrections=corrections,
                total_errors=errors,
                error_rate=errors / len(window_requests),
                latency_trend=latency_trend,
                accuracy_trend=accuracy_trend
            )

    def _calculate_trend(
        self,
        stats: Dict[str, List[float]],
        metric: str
    ) -> str:
        """计算趋势（improving/stable/degrading）"""
        if len(stats) < 2:
            return "stable"

        # 获取最近几个时间点的平均值
        recent_hours = sorted(stats.keys())[-4:]

        if len(recent_hours) < 2:
            return "stable"

        recent_values = []
        for hour in recent_hours:
            if stats[hour]:
                recent_values.append(statistics.mean(stats[hour]))

        if len(recent_values) < 2:
            return "stable"

        # 简单线性趋势
        first_half = statistics.mean(recent_values[:len(recent_values)//2])
        second_half = statistics.mean(recent_values[len(recent_values)//2:])

        if metric == "latency":
            # 延迟越低越好
            change_ratio = (first_half - second_half) / max(1, first_half)
        else:
            # 准确率越高越好
            change_ratio = (second_half - first_half) / max(0.01, first_half)

        if change_ratio > 0.1:
            return "improving"
        elif change_ratio < -0.1:
            return "degrading"
        return "stable"

    def get_recommendations(self) -> List[TuningRecommendation]:
        """
        获取自动调优建议

        基于当前性能数据生成优化建议
        """
        recommendations = []

        with self._lock:
            if len(self._requests) < 10:
                return recommendations

            # 获取最近1小时的快照
            snapshot = self.get_snapshot("1h")
            total = snapshot.total_requests

            if total < 5:
                return recommendations

            # 1. 检查专家调用率
            expert_rate = snapshot.expert_calls / total
            if expert_rate > self._thresholds["expert_rate"]:
                recommendations.append(TuningRecommendation(
                    category="routing",
                    priority=1,
                    issue="专家调用率过高",
                    current_value=f"{expert_rate * 100:.1f}%",
                    recommended_value=f"目标: <{self._thresholds['expert_rate'] * 100:.0f}%",
                    expected_improvement="降低延迟50%+，减少API成本",
                    confidence=0.85
                ))

            # 2. 检查缓存命中率
            cache_rate = snapshot.cache_hits / total
            if cache_rate < self._thresholds["cache_hit_min"]:
                recommendations.append(TuningRecommendation(
                    category="cache",
                    priority=2,
                    issue="缓存命中率过低",
                    current_value=f"{cache_rate * 100:.1f}%",
                    recommended_value=f"目标: >{self._thresholds['cache_hit_min'] * 100:.0f}%",
                    expected_improvement="提升缓存TTL或扩展知识库",
                    confidence=0.80
                ))

            # 3. 检查P99延迟
            if snapshot.p99_latency > self._thresholds["latency_p99_ms"]:
                recommendations.append(TuningRecommendation(
                    category="latency",
                    priority=1,
                    issue="P99延迟过高",
                    current_value=f"{snapshot.p99_latency:.0f}ms",
                    recommended_value=f"目标: <{self._thresholds['latency_p99_ms']}ms",
                    expected_improvement="考虑升级模型或启用预加载",
                    confidence=0.90
                ))

            # 4. 检查错误率
            if snapshot.error_rate > self._thresholds["error_rate"]:
                recommendations.append(TuningRecommendation(
                    category="reliability",
                    priority=1,
                    issue="错误率过高",
                    current_value=f"{snapshot.error_rate * 100:.2f}%",
                    recommended_value=f"目标: <{self._thresholds['error_rate'] * 100:.0f}%",
                    expected_improvement="检查模型服务稳定性",
                    confidence=0.95
                ))

            # 5. 检查准确率趋势
            if snapshot.accuracy_trend == "degrading":
                recommendations.append(TuningRecommendation(
                    category="model",
                    priority=2,
                    issue="准确率呈下降趋势",
                    current_value="下降中",
                    recommended_value="稳定或提升",
                    expected_improvement="增加专家监督或更新训练数据",
                    confidence=0.75
                ))

            # 6. 基于领域分析的建议
            for domain, stats in self._domain_stats.items():
                if stats["requests"] < 5:
                    continue

                domain_cache_rate = stats["cache_hit"] / stats["requests"]
                if domain_cache_rate < 0.2 and stats["requests"] > 10:
                    recommendations.append(TuningRecommendation(
                        category="cache",
                        priority=3,
                        issue=f"领域「{domain}」缓存命中率低",
                        current_value=f"{domain_cache_rate * 100:.1f}%",
                        recommended_value="考虑为该领域添加专项知识库",
                        expected_improvement=f"该领域平均延迟 {stats['avg_latency']:.0f}ms 可优化",
                        confidence=0.70
                    ))

        # 按优先级排序
        recommendations.sort(key=lambda x: x.priority)

        return recommendations

    def get_domain_performance(self) -> Dict[str, Dict]:
        """获取各领域的性能表现"""
        with self._lock:
            result = {}
            for domain, stats in self._domain_stats.items():
                if stats["requests"] < 3:
                    continue

                accuracies = stats.get("accuracies", [])
                result[domain] = {
                    "requests": stats["requests"],
                    "expert_rate": stats.get("expert", 0) / stats["requests"],
                    "cache_hit_rate": stats["cache_hit"] / stats["requests"],
                    "avg_latency_ms": stats["avg_latency"],
                    "avg_accuracy": statistics.mean(accuracies) if accuracies else None
                }
            return result

    def get_intent_distribution(self) -> Dict[str, Dict]:
        """获取意图分布"""
        with self._lock:
            return dict(self._intent_stats)

    def get_performance_report(self) -> Dict[str, Any]:
        """生成完整性能报告"""
        snapshots = {
            "5m": self.get_snapshot("5m"),
            "15m": self.get_snapshot("15m"),
            "1h": self.get_snapshot("1h"),
            "24h": self.get_snapshot("24h")
        }

        return {
            "timestamp": datetime.now().isoformat(),
            "snapshots": {k: v.to_dict() for k, v in snapshots.items()},
            "recommendations": [
                {
                    "category": r.category,
                    "priority": r.priority,
                    "issue": r.issue,
                    "current": r.current_value,
                    "recommended": r.recommended_value,
                    "improvement": r.expected_improvement,
                    "confidence": f"{r.confidence * 100:.0f}%"
                }
                for r in self.get_recommendations()
            ],
            "domain_performance": self.get_domain_performance(),
            "intent_distribution": self.get_intent_distribution(),
            "system_health": self._calculate_system_health()
        }

    def _calculate_system_health(self) -> str:
        """计算系统健康度"""
        snapshot = self.get_snapshot("1h")

        score = 100

        # 延迟扣分
        if snapshot.p90_latency > 2000:
            score -= 20
        elif snapshot.p90_latency > 1000:
            score -= 10

        # 错误率扣分
        if snapshot.error_rate > 0.05:
            score -= 30
        elif snapshot.error_rate > 0.01:
            score -= 10

        # 专家调用率扣分
        expert_rate = snapshot.expert_calls / max(1, snapshot.total_requests)
        if expert_rate > 0.8:
            score -= 15
        elif expert_rate > 0.6:
            score -= 5

        # 缓存命中率加分
        cache_rate = snapshot.cache_hits / max(1, snapshot.total_requests)
        if cache_rate > 0.5:
            score += 5

        return max(0, min(100, score))

    def set_threshold(self, key: str, value: float):
        """设置阈值"""
        if key in self._thresholds:
            self._thresholds[key] = value

    def set_anomaly_callback(self, callback: Callable):
        """设置异常回调"""
        self._on_anomaly = callback

    def set_threshold_callback(self, callback: Callable):
        """设置阈值超限回调"""
        self._on_threshold_exceeded = callback

    def reset(self):
        """重置统计数据"""
        with self._lock:
            self._requests.clear()
            self._latencies.clear()
            self._accuracies.clear()
            self._expert_calls = 0
            self._local_calls = 0
            self._cache_hits = 0
            self._corrections = 0
            self._errors = 0
            self._domain_stats.clear()
            self._intent_stats.clear()
            self._hourly_stats.clear()
            self._daily_stats.clear()
            logger.info("[PerformanceMonitor] 统计数据已重置")


# 全局单例
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor
