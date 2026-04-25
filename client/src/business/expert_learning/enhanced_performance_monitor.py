# -*- coding: utf-8 -*-
"""
增强的模型性能监控 (Enhanced Performance Monitor)
================================================

实时监控模型响应质量和延迟，提供全面的性能分析。

功能:
1. 实时监控 - 监控延迟、质量、错误率
2. 异常检测 - 自动检测性能异常
3. 趋势分析 - 分析性能趋势
4. 告警机制 - 异常时自动告警
5. 性能报告 - 生成详细性能报告

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import json
import time
import threading
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from dataclasses import asdict
from core.logger import get_logger
logger = get_logger('expert_learning.enhanced_performance_monitor')



class MetricType(Enum):
    """指标类型"""
    LATENCY = "latency"
    QUALITY = "quality"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    TOKEN_USAGE = "token_usage"


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: float
    metric_type: str
    value: float
    model_id: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """性能告警"""
    timestamp: float
    alert_type: str  # latency_high/quality_low/error_spike
    model_id: str
    message: str
    severity: str  # info/warning/critical
    value: float
    threshold: float


@dataclass
class ModelPerformance:
    """模型性能"""
    model_id: str
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0
    p50_latency_ms: float = 0
    p95_latency_ms: float = 0
    p99_latency_ms: float = 0
    avg_quality: float = 0
    error_rate: float = 0
    last_request_time: float = 0
    health_score: float = 1.0  # 0-1


@dataclass
class PerformanceReport:
    """性能报告"""
    period: str
    start_time: float
    end_time: float
    total_requests: int
    overall_health: float
    model_performances: List[ModelPerformance]
    alerts: List[PerformanceAlert]
    recommendations: List[str]


class EnhancedPerformanceMonitor:
    """
    增强的模型性能监控

    使用方式:
    ```python
    monitor = EnhancedPerformanceMonitor()

    # 记录请求
    monitor.record_request(
        model_id="qwen3.5:9b",
        latency_ms=1500,
        success=True,
        quality_score=0.9,
        tokens=500
    )

    # 获取报告
    report = monitor.get_report(period="1h")
    logger.info(f"健康度: {report.overall_health}")
    ```
    """

    def __init__(
        self,
        latency_threshold_ms: float = 5000,
        quality_threshold: float = 0.6,
        error_rate_threshold: float = 0.1,
    ):
        # 配置
        self.latency_threshold_ms = latency_threshold_ms
        self.quality_threshold = quality_threshold
        self.error_rate_threshold = error_rate_threshold

        # 数据存储
        self._lock = threading.RLock()
        self._requests: deque = deque(maxlen=10000)
        self._model_stats: Dict[str, Dict] = defaultdict(lambda: {
            "latencies": deque(maxlen=1000),
            "qualities": deque(maxlen=1000),
            "errors": deque(maxlen=100),
            "tokens": [],
            "total": 0,
            "success": 0,
            "fail": 0,
        })

        # 告警
        self._alerts: List[PerformanceAlert] = []
        self._alert_history: deque = deque(maxlen=500)

        # 回调
        self._on_alert: Optional[Callable] = None
        self._on_threshold_breach: Optional[Callable] = None

        # 健康度追踪
        self._health_history: deque = deque(maxlen=100)

        logger.info(f"[EnhancedMonitor] 已初始化 (延迟阈值:{latency_threshold_ms}ms, 质量阈值:{quality_threshold})")

    def record_request(
        self,
        model_id: str,
        model_name: str = "",
        latency_ms: float = 0,
        success: bool = True,
        quality_score: float = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error_message: str = "",
        metadata: Optional[Dict] = None,
    ):
        """记录请求"""
        timestamp = time.time()

        with self._lock:
            # 存储请求
            request = {
                "timestamp": timestamp,
                "model_id": model_id,
                "model_name": model_name,
                "latency_ms": latency_ms,
                "success": success,
                "quality_score": quality_score,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "error_message": error_message,
                "metadata": metadata or {},
            }
            self._requests.append(request)

            # 更新模型统计
            stats = self._model_stats[model_id]
            stats["total"] += 1
            stats["latencies"].append(latency_ms)
            if success:
                stats["success"] += 1
                if quality_score > 0:
                    stats["qualities"].append(quality_score)
            else:
                stats["fail"] += 1
                if error_message:
                    stats["errors"].append(error_message)

            if input_tokens or output_tokens:
                stats["tokens"].append({"input": input_tokens, "output": output_tokens, "timestamp": timestamp})

            stats["last_request_time"] = timestamp

        # 检查告警条件
        self._check_alerts(model_id, latency_ms, quality_score, success)

    def _check_alerts(
        self,
        model_id: str,
        latency_ms: float,
        quality_score: float,
        success: bool,
    ):
        """检查告警条件"""
        with self._lock:
            alerts = []

            # 延迟告警
            if latency_ms > self.latency_threshold_ms:
                alerts.append(PerformanceAlert(
                    timestamp=time.time(),
                    alert_type="latency_high",
                    model_id=model_id,
                    message=f"延迟过高: {latency_ms:.0f}ms (阈值: {self.latency_threshold_ms}ms)",
                    severity="warning" if latency_ms < self.latency_threshold_ms * 2 else "critical",
                    value=latency_ms,
                    threshold=self.latency_threshold_ms,
                ))

            # 质量告警
            if quality_score > 0 and quality_score < self.quality_threshold:
                alerts.append(PerformanceAlert(
                    timestamp=time.time(),
                    alert_type="quality_low",
                    model_id=model_id,
                    message=f"质量过低: {quality_score:.2f} (阈值: {self.quality_threshold})",
                    severity="warning",
                    value=quality_score,
                    threshold=self.quality_threshold,
                ))

            # 错误告警
            stats = self._model_stats[model_id]
            if stats["total"] >= 10:
                recent = list(self._requests)[-10:]
                recent_errors = sum(1 for r in recent if not r["success"])
                error_rate = recent_errors / 10

                if error_rate > self.error_rate_threshold:
                    alerts.append(PerformanceAlert(
                        timestamp=time.time(),
                        alert_type="error_spike",
                        model_id=model_id,
                        message=f"错误率上升: {error_rate:.1%} (阈值: {self.error_rate_threshold:.1%})",
                        severity="critical" if error_rate > 0.3 else "warning",
                        value=error_rate,
                        threshold=self.error_rate_threshold,
                    ))

            # 触发回调
            for alert in alerts:
                self._alerts.append(alert)
                self._alert_history.append(alert)
                if self._on_alert:
                    self._on_alert(alert)

    def get_model_performance(self, model_id: str) -> Optional[ModelPerformance]:
        """获取模型性能"""
        with self._lock:
            stats = self._model_stats.get(model_id)
            if not stats or stats["total"] == 0:
                return None

            latencies = sorted(stats["latencies"])
            qualities = list(stats["qualities"])

            total = stats["total"]
            success = stats["success"]
            fail = stats["fail"]

            return ModelPerformance(
                model_id=model_id,
                model_name=stats.get("model_name", model_id),
                total_requests=total,
                successful_requests=success,
                failed_requests=fail,
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
                p50_latency_ms=latencies[len(latencies) // 2] if latencies else 0,
                p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
                p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
                avg_quality=sum(qualities) / len(qualities) if qualities else 0,
                error_rate=fail / total if total > 0 else 0,
                last_request_time=stats["last_request_time"],
                health_score=self._calculate_health_score(latencies, qualities, fail, total),
            )

    def _calculate_health_score(
        self,
        latencies: List[float],
        qualities: List[float],
        failures: int,
        total: int,
    ) -> float:
        """计算健康分数"""
        score = 1.0

        # 延迟影响
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            if avg_latency > self.latency_threshold_ms:
                score -= 0.3
            elif avg_latency > self.latency_threshold_ms * 0.7:
                score -= 0.1

        # 质量影响
        if qualities:
            avg_quality = sum(qualities) / len(qualities)
            if avg_quality < self.quality_threshold:
                score -= 0.3
            elif avg_quality < 0.8:
                score -= 0.1

        # 错误率影响
        if total > 0:
            error_rate = failures / total
            if error_rate > 0.1:
                score -= 0.3
            elif error_rate > 0.05:
                score -= 0.1

        return max(0, min(score, 1.0))

    def get_all_performances(self) -> List[ModelPerformance]:
        """获取所有模型性能"""
        with self._lock:
            return [
                self.get_model_performance(model_id)
                for model_id in self._model_stats.keys()
            ]

    def get_report(
        self,
        period: str = "1h",
        model_id: Optional[str] = None,
    ) -> PerformanceReport:
        """生成性能报告"""
        with self._lock:
            cutoff = self._get_period_start(period)
            recent_requests = [r for r in self._requests if r["timestamp"] >= cutoff]

            # 获取模型性能
            if model_id:
                performances = [self.get_model_performance(model_id)] if model_id in self._model_stats else []
            else:
                performances = self.get_all_performances()

            # 过滤无效
            performances = [p for p in performances if p]

            # 计算整体健康度
            overall_health = 1.0
            if performances:
                overall_health = sum(p.health_score for p in performances) / len(performances)

            # 获取告警
            alerts = [a for a in self._alerts if a.timestamp >= cutoff]

            # 生成建议
            recommendations = self._generate_recommendations(performances, alerts)

            return PerformanceReport(
                period=period,
                start_time=cutoff,
                end_time=time.time(),
                total_requests=len(recent_requests),
                overall_health=overall_health,
                model_performances=performances,
                alerts=alerts,
                recommendations=recommendations,
            )

    def _generate_recommendations(
        self,
        performances: List[ModelPerformance],
        alerts: List[PerformanceAlert],
    ) -> List[str]:
        """生成建议"""
        recommendations = []

        # 基于告警
        alert_types = defaultdict(int)
        for alert in alerts:
            alert_types[alert.alert_type] += 1

        if alert_types.get("latency_high", 0) > 3:
            recommendations.append("多个请求延迟过高，考虑升级硬件或优化模型")

        if alert_types.get("quality_low", 0) > 3:
            recommendations.append("质量评分持续偏低，可能需要使用更大的模型")

        if alert_types.get("error_spike", 0) > 1:
            recommendations.append("错误率异常，请检查模型服务状态")

        # 基于性能
        for perf in performances:
            if perf.avg_latency_ms > self.latency_threshold_ms:
                recommendations.append(f"{perf.model_id}平均延迟{perf.avg_latency_ms:.0f}ms，考虑优化")

            if perf.error_rate > 0.1:
                recommendations.append(f"{perf.model_id}错误率{perf.error_rate:.1%}，需要排查")

        if not recommendations:
            recommendations.append("系统运行正常，无需特殊处理")

        return recommendations

    def get_trend(
        self,
        metric: MetricType,
        model_id: str = "",
        period: str = "1h",
    ) -> Dict[str, Any]:
        """获取趋势数据"""
        with self._lock:
            cutoff = self._get_period_start(period)
            recent = [r for r in self._requests if r["timestamp"] >= cutoff]

            if model_id:
                recent = [r for r in recent if r["model_id"] == model_id]

            if not recent:
                return {"data_points": [], "trend": "stable"}

            # 提取指标
            if metric == MetricType.LATENCY:
                values = [r["latency_ms"] for r in recent if r["latency_ms"] > 0]
            elif metric == MetricType.QUALITY:
                values = [r["quality_score"] for r in recent if r["quality_score"] > 0]
            elif metric == MetricType.ERROR_RATE:
                values = [1 if not r["success"] else 0 for r in recent]
            else:
                values = []

            # 计算趋势
            trend = "stable"
            if len(values) >= 10:
                first_half = sum(values[:len(values)//2]) / (len(values)//2)
                second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                if second_half > first_half * 1.1:
                    trend = "increasing"
                elif second_half < first_half * 0.9:
                    trend = "decreasing"

            return {
                "metric": metric.value,
                "data_points": values,
                "trend": trend,
                "current": values[-1] if values else 0,
                "average": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
            }

    def _get_period_start(self, period: str) -> float:
        """获取周期开始时间"""
        now = time.time()
        if period == "5m":
            return now - 300
        elif period == "15m":
            return now - 900
        elif period == "1h":
            return now - 3600
        elif period == "6h":
            return now - 21600
        elif period == "24h":
            return now - 86400
        else:
            return 0

    def clear_alerts(self):
        """清除告警"""
        with self._lock:
            self._alerts = []

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """获取活跃告警"""
        return list(self._alerts)

    def set_callbacks(
        self,
        on_alert: Callable = None,
        on_threshold_breach: Callable = None,
    ):
        """设置回调"""
        self._on_alert = on_alert
        self._on_threshold_breach = on_threshold_breach

    def get_stats(self) -> Dict:
        """获取统计"""
        with self._lock:
            return {
                "total_requests": len(self._requests),
                "tracked_models": len(self._model_stats),
                "active_alerts": len(self._alerts),
                "alert_history": len(self._alert_history),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("增强的性能监控测试")
    logger.info("=" * 60)

    monitor = EnhancedPerformanceMonitor(latency_threshold_ms=3000)

    logger.info("\n[Test 1: 记录请求]")
    monitor.record_request("qwen3.5:9b", "Qwen 9B", latency_ms=1500, success=True, quality_score=0.9, input_tokens=100, output_tokens=200)
    monitor.record_request("qwen3.5:9b", "Qwen 9B", latency_ms=2000, success=True, quality_score=0.85, input_tokens=150, output_tokens=250)
    monitor.record_request("qwen2.5:1.5b", "Qwen 1.5B", latency_ms=800, success=True, quality_score=0.7, input_tokens=100, output_tokens=150)
    monitor.record_request("qwen3.5:9b", "Qwen 9B", latency_ms=4500, success=False, error_message="Timeout")
    logger.info("  已记录4个请求")

    logger.info("\n[Test 2: 模型性能]")
    perf = monitor.get_model_performance("qwen3.5:9b")
    if perf:
        logger.info(f"  模型: {perf.model_id}")
        logger.info(f"  请求数: {perf.total_requests}")
        logger.info(f"  平均延迟: {perf.avg_latency_ms:.0f}ms")
        logger.info(f"  错误率: {perf.error_rate:.1%}")
        logger.info(f"  健康度: {perf.health_score:.2f}")

    logger.info("\n[Test 3: 性能报告]")
    report = monitor.get_report(period="1h")
    logger.info(f"  周期: {report.period}")
    logger.info(f"  总请求: {report.total_requests}")
    logger.info(f"  整体健康: {report.overall_health:.2f}")
    logger.info(f"  告警数: {len(report.alerts)}")
    logger.info(f"  建议: {report.recommendations}")

    logger.info("\n[Test 4: 趋势分析]")
    trend = monitor.get_trend(MetricType.LATENCY, "qwen3.5:9b")
    logger.info(f"  延迟趋势: {trend['trend']}")
    logger.info(f"  当前: {trend['current']:.0f}ms")
    logger.info(f"  平均: {trend['average']:.0f}ms")

    logger.info("\n" + "=" * 60)
