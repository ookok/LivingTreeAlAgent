"""
性能监控模块
关键指标监控与自适应调优
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from threading import Lock
from collections import deque
import logging


@dataclass
class PerformanceMetrics:
    """性能指标"""
    latency_avg: float = 0
    latency_min: float = 0
    latency_max: float = 0
    latency_p95: float = 0
    latency_p99: float = 0
    hit_rate: float = 0
    throughput: float = 0
    error_rate: float = 0


@dataclass
class AlertThreshold:
    """告警阈值"""
    latency_l1_ms: float = 100
    latency_l2_ms: float = 500
    latency_l3_ms: float = 5000
    latency_l4_ms: float = 10000
    hit_rate_min: float = 0.20
    gpu_util_max: float = 0.90
    memory_max: float = 0.90


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._latencies: Dict[str, deque] = {
            "L1": deque(maxlen=window_size),
            "L2": deque(maxlen=window_size),
            "L3": deque(maxlen=window_size),
            "L4": deque(maxlen=window_size)
        }
        self._cache_hits = {"L1": 0, "L2": 0, "L3": 0}
        self._cache_misses = {"L1": 0, "L2": 0, "L3": 0}
        self._errors = 0
        self._total_requests = 0
        self._start_time = time.time()
        self._lock = Lock()
    
    def record_latency(self, tier: str, latency_ms: float):
        """记录延迟"""
        with self._lock:
            if tier in self._latencies:
                self._latencies[tier].append(latency_ms)
    
    def record_cache_hit(self, tier: str):
        """记录缓存命中"""
        with self._lock:
            if tier in self._cache_hits:
                self._cache_hits[tier] += 1
    
    def record_cache_miss(self, tier: str):
        """记录缓存未命中"""
        with self._lock:
            if tier in self._cache_misses:
                self._cache_misses[tier] += 1
    
    def record_error(self):
        """记录错误"""
        with self._lock:
            self._errors += 1
    
    def record_request(self):
        """记录请求"""
        with self._lock:
            self._total_requests += 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """获取性能指标"""
        with self._lock:
            metrics = PerformanceMetrics()
            
            # 计算各层延迟统计
            for tier, latencies in self._latencies.items():
                if latencies:
                    sorted_lat = sorted(latencies)
                    metrics.latency_avg += sum(sorted_lat) / len(sorted_lat) / 4
                    metrics.latency_min = min(metrics.latency_min or float('inf'), min(sorted_lat))
                    metrics.latency_max = max(metrics.latency_max, max(sorted_lat))
                    if len(sorted_lat) >= 20:
                        metrics.latency_p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
                        metrics.latency_p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
            
            # 计算命中率
            total_hits = sum(self._cache_hits.values())
            total_misses = sum(self._cache_misses.values())
            total = total_hits + total_misses
            if total > 0:
                metrics.hit_rate = total_hits / total
            
            # 吞吐率
            elapsed = time.time() - self._start_time
            if elapsed > 0:
                metrics.throughput = self._total_requests / elapsed
            
            # 错误率
            if self._total_requests > 0:
                metrics.error_rate = self._errors / self._total_requests
            
            return metrics


class PerformanceMonitor:
    """
    性能监控器
    - 关键指标监控
    - 告警机制
    - 自适应调优
    """
    
    def __init__(self, thresholds: AlertThreshold = None):
        self.thresholds = thresholds or AlertThreshold()
        self.collector = MetricsCollector()
        self.logger = logging.getLogger(__name__)
        
        self._alerts: List[Dict] = []
        self._alert_handlers: List[Callable] = []
        self._tuning_rules: Dict[str, Callable] = {}
        self._lock = Lock()
        
        # 监控状态
        self.is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def start(self):
        """启动监控"""
        self.is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("性能监控已启动")
    
    async def stop(self):
        """停止监控"""
        self.is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("性能监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                await self._check_metrics()
                await asyncio.sleep(5)  # 每5秒检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控错误: {e}")
    
    async def _check_metrics(self):
        """检查指标并触发告警/调优"""
        metrics = self.collector.get_metrics()
        
        # 检查延迟告警
        alerts = []
        
        if metrics.latency_p95 > self.thresholds.latency_l1_ms:
            alerts.append({
                "level": "warning",
                "type": "latency",
                "tier": "L1",
                "value": metrics.latency_p95,
                "threshold": self.thresholds.latency_l1_ms,
                "message": f"L1延迟过高: {metrics.latency_p95:.0f}ms > {self.thresholds.latency_l1_ms}ms"
            })
        
        if metrics.hit_rate < self.thresholds.hit_rate_min:
            alerts.append({
                "level": "warning",
                "type": "hit_rate",
                "value": metrics.hit_rate,
                "threshold": self.thresholds.hit_rate_min,
                "message": f"缓存命中率过低: {metrics.hit_rate:.2%} < {self.thresholds.hit_rate_min:.2%}"
            })
        
        if metrics.error_rate > 0.05:
            alerts.append({
                "level": "error",
                "type": "error_rate",
                "value": metrics.error_rate,
                "message": f"错误率过高: {metrics.error_rate:.2%}"
            })
        
        # 处理告警
        for alert in alerts:
            self._handle_alert(alert)
    
    def _handle_alert(self, alert: Dict):
        """处理告警"""
        with self._lock:
            self._alerts.append({
                **alert,
                "timestamp": time.time()
            })
        
        self.logger.warning(alert["message"])
        
        # 调用告警处理器
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"告警处理错误: {e}")
        
        # 触发自动调优
        self._apply_tuning(alert)
    
    def _apply_tuning(self, alert: Dict):
        """应用自动调优"""
        alert_type = alert["type"]
        
        if alert_type == "latency" and alert_type in self._tuning_rules:
            tuning_action = self._tuning_rules[alert_type]
            tuning_action(alert)
            self.logger.info(f"应用自动调优: {alert_type}")
    
    def register_alert_handler(self, handler: Callable):
        """注册告警处理器"""
        self._alert_handlers.append(handler)
    
    def register_tuning_rule(self, alert_type: str, rule: Callable):
        """注册调优规则"""
        self._tuning_rules[alert_type] = rule
    
    def record(self, tier: str, latency_ms: float, cache_hit: bool = False):
        """记录指标"""
        self.collector.record_latency(tier, latency_ms)
        if cache_hit:
            self.collector.record_cache_hit(tier)
        else:
            self.collector.record_cache_miss(tier)
        self.collector.record_request()
    
    def record_error(self):
        """记录错误"""
        self.collector.record_error()
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        metrics = self.collector.get_metrics()
        
        with self._lock:
            recent_alerts = [
                a for a in self._alerts
                if time.time() - a["timestamp"] < 300  # 最近5分钟
            ]
        
        return {
            "monitoring": self.is_monitoring,
            "metrics": {
                "latency_avg": metrics.latency_avg,
                "latency_p95": metrics.latency_p95,
                "hit_rate": metrics.hit_rate,
                "throughput": metrics.throughput,
                "error_rate": metrics.error_rate
            },
            "thresholds": {
                "latency_l1_ms": self.thresholds.latency_l1_ms,
                "hit_rate_min": self.thresholds.hit_rate_min
            },
            "recent_alerts": recent_alerts,
            "alert_count": len(recent_alerts)
        }
    
    def get_historical_metrics(self, hours: int = 24) -> List[Dict]:
        """获取历史指标"""
        with self._lock:
            return [
                {**alert, "timestamp": alert["timestamp"]}
                for alert in self._alerts
                if time.time() - alert["timestamp"] < hours * 3600
            ]
