"""
实时网络质量监控

延迟监控、带宽监控、丢包检测、智能预警
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import deque
import threading
import time
import logging
import statistics

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"    # 绿色
    GOOD = "good"             # 蓝色
    FAIR = "fair"             # 黄色
    POOR = "poor"             # 橙色
    BAD = "bad"               # 红色


@dataclass
class QualityMetrics:
    """质量指标"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 延迟指标
    latency_avg: float = 0      # 平均延迟 ms
    latency_min: float = 0       # 最小延迟 ms
    latency_max: float = 0       # 最大延迟 ms
    latency_p50: float = 0       # P50延迟 ms
    latency_p95: float = 0       # P95延迟 ms
    latency_p99: float = 0       # P99延迟 ms
    latency_std: float = 0       # 延迟标准差
    
    # 带宽指标
    bandwidth_up: float = 0     # 上行带宽 Mbps
    bandwidth_down: float = 0    # 下行带宽 Mbps
    bandwidth_utilization: float = 0  # 带宽利用率
    
    # 丢包指标
    packet_loss_rate: float = 0  # 丢包率 0-1
    retransmit_rate: float = 0   # 重传率 0-1
    jitter: float = 0            # 网络抖动 ms
    
    # 连接指标
    connection_success: float = 1.0  # 连接成功率 0-1
    reconnect_count: int = 0     # 重连次数
    
    # 综合评分
    quality_score: float = 100   # 0-100
    
    def get_quality_level(self) -> QualityLevel:
        """获取质量等级"""
        if self.quality_score >= 90:
            return QualityLevel.EXCELLENT
        elif self.quality_score >= 75:
            return QualityLevel.GOOD
        elif self.quality_score >= 60:
            return QualityLevel.FAIR
        elif self.quality_score >= 40:
            return QualityLevel.POOR
        else:
            return QualityLevel.BAD
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "latency_avg": round(self.latency_avg, 1),
            "latency_p95": round(self.latency_p95, 1),
            "latency_p99": round(self.latency_p99, 1),
            "packet_loss_rate": round(self.packet_loss_rate * 100, 2),
            "jitter": round(self.jitter, 2),
            "bandwidth_up": round(self.bandwidth_up, 1),
            "bandwidth_down": round(self.bandwidth_down, 1),
            "quality_score": round(self.quality_score, 1),
            "quality_level": self.get_quality_level().value,
        }


class QualityAlert:
    """质量告警"""
    
    def __init__(
        self,
        level: str,  # info, warning, error, critical
        title: str,
        message: str,
        metrics: Optional[QualityMetrics] = None,
        suggestions: List[str] = None
    ):
        self.id = f"alert_{int(time.time() * 1000)}"
        self.level = level
        self.title = title
        self.message = message
        self.metrics = metrics
        self.suggestions = suggestions or []
        self.timestamp = datetime.now()
        self.acknowledged = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
        }


class QualityMonitor:
    """
    实时质量监控器
    
    监控网络质量，生成告警和建议
    """
    
    def __init__(
        self,
        window_size: int = 60,  # 统计窗口大小（秒）
        alert_thresholds: Dict[str, float] = None
    ):
        self.window_size = window_size
        self._alert_thresholds = alert_thresholds or {
            "latency_p95": 200,      # P95延迟阈值 ms
            "packet_loss": 0.05,     # 丢包率阈值
            "jitter": 50,            # 抖动阈值 ms
            "connection_success": 0.8,  # 连接成功率阈值
        }
        
        self._lock = threading.Lock()
        self._running = False
        
        # 原始数据
        self._latency_samples: deque = deque(maxlen=1000)
        self._packet_samples: deque = deque(maxlen=1000)
        self._bandwidth_samples: deque = deque(maxlen=100)
        
        # 告警列表
        self._alerts: deque = deque(maxlen=100)
        
        # 监听器
        self._listeners: List[Callable] = []
        
        # 统计信息
        self._stats = {
            "total_samples": 0,
            "total_packets_sent": 0,
            "total_packets_received": 0,
            "total_reconnects": 0,
        }
    
    def start(self):
        """启动监控"""
        self._running = True
    
    def stop(self):
        """停止监控"""
        self._running = False
    
    def record_latency(self, latency: float):
        """记录延迟样本"""
        with self._lock:
            self._latency_samples.append({
                "value": latency,
                "timestamp": datetime.now(),
            })
            self._stats["total_samples"] += 1
    
    def record_packet(self, sent: bool):
        """记录数据包"""
        with self._lock:
            self._packet_samples.append({
                "sent": sent,
                "timestamp": datetime.now(),
            })
            
            if sent:
                self._stats["total_packets_sent"] += 1
            else:
                self._stats["total_packets_received"] += 1
    
    def record_bandwidth(self, up: float, down: float):
        """记录带宽"""
        with self._lock:
            self._bandwidth_samples.append({
                "up": up,
                "down": down,
                "timestamp": datetime.now(),
            })
    
    def record_reconnect(self):
        """记录重连"""
        with self._lock:
            self._stats["total_reconnects"] += 1
    
    def get_metrics(self) -> QualityMetrics:
        """获取当前质量指标"""
        metrics = QualityMetrics()
        metrics.timestamp = datetime.now()
        
        # 计算延迟统计
        latencies = [s["value"] for s in self._latency_samples]
        if latencies:
            metrics.latency_avg = statistics.mean(latencies)
            metrics.latency_min = min(latencies)
            metrics.latency_max = max(latencies)
            
            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)
            
            metrics.latency_p50 = sorted_latencies[n * 50 // 100]
            metrics.latency_p95 = sorted_latencies[n * 95 // 100]
            metrics.latency_p99 = sorted_latencies[min(n * 99 // 100, n - 1)]
            
            if len(latencies) > 1:
                metrics.latency_std = statistics.stdev(latencies)
        
        # 计算丢包率
        packets = list(self._packet_samples)
        if packets:
            sent = sum(1 for p in packets if p["sent"])
            received = sum(1 for p in packets if not p["sent"])
            total = sent + received
            
            if total > 0:
                metrics.packet_loss_rate = max(0, sent - received) / max(1, sent)
                metrics.connection_success = received / max(1, total)
        
        # 计算带宽
        bandwidths = list(self._bandwidth_samples)
        if bandwidths:
            ups = [s["up"] for s in bandwidths]
            downs = [s["down"] for s in bandwidths]
            
            metrics.bandwidth_up = statistics.mean(ups) if ups else 0
            metrics.bandwidth_down = statistics.mean(downs) if downs else 0
        
        # 计算抖动
        if len(latencies) > 1:
            diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
            metrics.jitter = statistics.mean(diffs) if diffs else 0
        
        # 计算综合评分
        metrics.quality_score = self._calculate_score(metrics)
        
        return metrics
    
    def _calculate_score(self, metrics: QualityMetrics) -> float:
        """计算综合评分"""
        score = 100.0
        
        # 延迟影响 (40%)
        if metrics.latency_avg > 0:
            if metrics.latency_avg < 10:
                score -= 0
            elif metrics.latency_avg < 50:
                score -= (metrics.latency_avg - 10) * 0.2
            elif metrics.latency_avg < 200:
                score -= 8 + (metrics.latency_avg - 50) * 0.1
            else:
                score -= 23 + (metrics.latency_avg - 200) * 0.05
            score = max(0, score)
        
        # 丢包影响 (30%)
        if metrics.packet_loss_rate > 0:
            score -= metrics.packet_loss_rate * 100 * 0.3
        
        # 抖动影响 (15%)
        if metrics.jitter > 0:
            score -= min(15, metrics.jitter * 0.3)
        
        # 连接成功率 (15%)
        score *= (0.5 + metrics.connection_success * 0.5)
        
        return max(0, min(100, score))
    
    def check_alerts(self) -> List[QualityAlert]:
        """检查是否需要生成告警"""
        metrics = self.get_metrics()
        alerts = []
        
        # P95延迟告警
        if metrics.latency_p95 > self._alert_thresholds["latency_p95"]:
            level = "warning"
            if metrics.latency_p95 > self._alert_thresholds["latency_p95"] * 2:
                level = "critical"
            
            alerts.append(QualityAlert(
                level=level,
                title="高延迟告警",
                message=f"P95延迟 {metrics.latency_p95:.0f}ms 超过阈值 {self._alert_thresholds['latency_p95']:.0f}ms",
                metrics=metrics,
                suggestions=["检查网络连接", "尝试切换到更稳定的网络", "考虑使用中继服务器"]
            ))
        
        # 丢包告警
        if metrics.packet_loss_rate > self._alert_thresholds["packet_loss"]:
            alerts.append(QualityAlert(
                level="error",
                title="丢包率过高",
                message=f"丢包率 {metrics.packet_loss_rate * 100:.1f}% 超过阈值 {self._alert_thresholds['packet_loss'] * 100:.1f}%",
                metrics=metrics,
                suggestions=["检查网络稳定性", "尝试切换到有线连接", "降低数据传输量"]
            ))
        
        # 抖动告警
        if metrics.jitter > self._alert_thresholds["jitter"]:
            alerts.append(QualityAlert(
                level="warning",
                title="网络抖动过大",
                message=f"抖动 {metrics.jitter:.0f}ms 超过阈值 {self._alert_thresholds['jitter']:.0f}ms",
                metrics=metrics,
                suggestions=["使用QoS保障", "考虑有线网络"]
            ))
        
        # 连接成功率告警
        if metrics.connection_success < self._alert_thresholds["connection_success"]:
            alerts.append(QualityAlert(
                level="error",
                title="连接成功率低",
                message=f"连接成功率 {metrics.connection_success * 100:.0f}% 低于阈值 {self._alert_thresholds['connection_success'] * 100:.0f}%",
                metrics=metrics,
                suggestions=["检查网络连接", "尝试重新连接", "考虑更换网络环境"]
            ))
        
        # 保存告警
        for alert in alerts:
            self._alerts.append(alert)
            self._notify_listeners(alert)
        
        return alerts
    
    def subscribe(self, callback: Callable):
        """订阅告警"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)
    
    def _notify_listeners(self, alert: QualityAlert):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(alert)
            except Exception as e:
                logger.error(f"Alert listener error: {e}")
    
    def get_alerts(self, unacknowledged_only: bool = False) -> List[Dict]:
        """获取告警列表"""
        alerts = list(self._alerts)
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [a.to_dict() for a in reversed(alerts)]
    
    def acknowledge_alert(self, alert_id: str):
        """确认告警"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                break
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        metrics = self.get_metrics()
        
        return {
            "running": self._running,
            "metrics": metrics.to_dict(),
            "stats": self._stats.copy(),
            "pending_alerts": sum(1 for a in self._alerts if not a.acknowledged),
        }
    
    def reset(self):
        """重置统计"""
        with self._lock:
            self._latency_samples.clear()
            self._packet_samples.clear()
            self._bandwidth_samples.clear()
            self._alerts.clear()
            self._stats = {
                "total_samples": 0,
                "total_packets_sent": 0,
                "total_packets_received": 0,
                "total_reconnects": 0,
            }


# 单例实例
_quality_monitor: Optional[QualityMonitor] = None


def get_quality_monitor() -> QualityMonitor:
    """获取质量监控器"""
    global _quality_monitor
    if _quality_monitor is None:
        _quality_monitor = QualityMonitor()
    return _quality_monitor


__all__ = [
    "QualityLevel",
    "QualityMetrics",
    "QualityAlert",
    "QualityMonitor",
    "get_quality_monitor",
]
