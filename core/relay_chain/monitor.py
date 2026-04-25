"""
监控系统 - Monitoring System

节点健康监控、交易异常检测、性能指标

核心功能：
1. 节点健康检查（心跳、延迟、负载）
2. 交易异常检测（高频交易、大额交易）
3. 账本一致性监控
4. 告警通知
"""

import time
import threading
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from decimal import Decimal

# 导入配置
try:
    from core.config.unified_config import get_config
except ImportError:
    get_config = None

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """告警"""
    level: AlertLevel
    category: str  # node_health, tx_anomaly, chain_consistency, performance
    message: str
    details: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['level'] = self.level.value
        d['timestamp'] = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return d


@dataclass
class NodeMetrics:
    """节点指标"""
    relay_id: str
    state: str = "unknown"

    # 性能指标
    latency_ms: float = 0  # 到其他节点的延迟
    throughput: float = 0  # TPS
    queue_size: int = 0  # 待处理队列

    # 健康状态
    heartbeat_age: float = 0  # 最后心跳距今秒数
    error_rate: float = 0  # 错误率
    sync_lag: float = 0  # 同步延迟

    # 时间
    updated_at: float = field(default_factory=time.time)


class MonitoringService:
    """
    监控服务

    职责：
    1. 节点健康监控
    2. 交易异常检测
    3. 性能指标收集
    4. 告警管理
    """

    def __init__(self):
        # 节点指标
        self._node_metrics: Dict[str, NodeMetrics] = {}

        # 告警
        self._alerts: deque = deque(maxlen=1000)
        self._active_alerts: Dict[str, Alert] = {}

        # 交易统计
        self._tx_stats = {
            "total": 0,
            "recharge": 0,
            "consume": 0,
            "transfer": 0,
            "failed": 0
        }
        self._tx_per_minute: deque = deque(maxlen=60)  # 每分钟交易数

        # 大额交易阈值
        self._large_tx_threshold = Decimal("10000")

        # 回调
        self._alert_callbacks: List[Callable] = []

        # 启动
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ─────────────────────────────────────────────────────────────
    # 节点监控
    # ─────────────────────────────────────────────────────────────

    def record_node_heartbeat(self, relay_id: str, state: str = "online", latency_ms: float = 0):
        """记录节点心跳"""
        if relay_id not in self._node_metrics:
            self._node_metrics[relay_id] = NodeMetrics(relay_id=relay_id)

        metrics = self._node_metrics[relay_id]
        metrics.state = state
        metrics.latency_ms = latency_ms
        metrics.heartbeat_age = 0
        metrics.updated_at = time.time()

    def record_node_error(self, relay_id: str, error_type: str):
        """记录节点错误"""
        if relay_id not in self._node_metrics:
            self._node_metrics[relay_id] = NodeMetrics(relay_id=relay_id)

        metrics = self._node_metrics[relay_id]
        metrics.error_rate = min(1.0, metrics.error_rate + 0.1)

        # 触发告警
        if metrics.error_rate > 0.5:
            self.create_alert(
                AlertLevel.ERROR,
                "node_health",
                f"节点 {relay_id} 错误率过高",
                {"relay_id": relay_id, "error_rate": metrics.error_rate, "error_type": error_type}
            )

    def get_node_health(self) -> Dict:
        """获取节点健康状态"""
        now = time.time()
        health_data = {}

        for relay_id, metrics in self._node_metrics.items():
            health_data[relay_id] = {
                "state": metrics.state,
                "latency_ms": metrics.latency_ms,
                "error_rate": metrics.error_rate,
                "heartbeat_age": now - metrics.heartbeat_age if metrics.heartbeat_age > 0 else 0,
                "throughput": metrics.throughput,
                "queue_size": metrics.queue_size
            }

        return health_data

    def check_node_health(self):
        """检查节点健康状态"""
        config = get_config() if get_config else None
        heartbeat_timeout = 60
        if config:
            heartbeat_timeout = config.get("relay.heartbeat_timeout", 60)
            
        now = time.time()

        for relay_id, metrics in self._node_metrics.items():
            # 检查心跳超时
            if now - metrics.updated_at > heartbeat_timeout:
                self.create_alert(
                    AlertLevel.WARNING,
                    "node_health",
                    f"节点 {relay_id} 心跳超时",
                    {"relay_id": relay_id, "last_heartbeat": now - metrics.updated_at}
                )

            # 检查高延迟
            if metrics.latency_ms > 500:
                self.create_alert(
                    AlertLevel.WARNING,
                    "node_health",
                    f"节点 {relay_id} 延迟过高",
                    {"relay_id": relay_id, "latency_ms": metrics.latency_ms}
                )

    # ─────────────────────────────────────────────────────────────
    # 交易监控
    # ─────────────────────────────────────────────────────────────

    def record_transaction(self, tx_type: str, amount: Decimal, user_id: str):
        """记录交易"""
        self._tx_stats["total"] += 1

        if tx_type == "RECHARGE":
            self._tx_stats["recharge"] += 1
        elif tx_type == "CONSUME":
            self._tx_stats["consume"] += 1
        else:
            self._tx_stats["transfer"] += 1

        # 检查大额交易
        if amount >= self._large_tx_threshold:
            self.create_alert(
                AlertLevel.INFO,
                "tx_anomaly",
                f"大额交易: 用户 {user_id} 交易 {amount}",
                {"user_id": user_id, "amount": float(amount), "tx_type": tx_type}
            )

        # 更新每分钟统计
        current_minute = int(time.time() / 60)
        if not self._tx_per_minute or self._tx_per_minute[-1]["minute"] != current_minute:
            self._tx_per_minute.append({"minute": current_minute, "count": 1})
        else:
            self._tx_per_minute[-1]["count"] += 1

    def record_failed_transaction(self, reason: str):
        """记录失败交易"""
        self._tx_stats["failed"] += 1

        if "balance" in reason.lower():
            self.create_alert(
                AlertLevel.INFO,
                "tx_anomaly",
                f"余额不足交易",
                {"reason": reason}
            )

    def get_transaction_stats(self) -> Dict:
        """获取交易统计"""
        # 计算近5分钟交易量
        now = int(time.time() / 60)
        recent_txs = sum(item["count"] for item in self._tx_per_minute if now - item["minute"] <= 5)

        return {
            **self._tx_stats,
            "tx_per_minute_5m": recent_txs,
            "success_rate": (
                (self._tx_stats["total"] - self._tx_stats["failed"]) / max(1, self._tx_stats["total"]) * 100
            )
        }

    def check_tx_anomaly(self, user_id: str):
        """
        检查交易异常

        检测同一用户的高频交易
        """
        # 简化实现：实际应该跟踪每个用户的交易频率
        pass

    # ─────────────────────────────────────────────────────────────
    # 告警管理
    # ─────────────────────────────────────────────────────────────

    def create_alert(
        self,
        level: AlertLevel,
        category: str,
        message: str,
        details: Dict = None
    ) -> Alert:
        """创建告警"""
        alert = Alert(
            level=level,
            category=category,
            message=message,
            details=details or {}
        )

        self._alerts.append(alert)

        # 追踪活跃告警
        key = f"{category}:{message}"
        self._active_alerts[key] = alert

        logger.log(
            logging.WARNING if level in (AlertLevel.WARNING, AlertLevel.ERROR) else logging.INFO,
            f"[{level.value}] {category}: {message}"
        )

        # 触发回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")

        return alert

    def resolve_alert(self, category: str, message: str):
        """解决告警"""
        key = f"{category}:{message}"
        if key in self._active_alerts:
            self._active_alerts[key].resolved = True
            del self._active_alerts[key]
            logger.info(f"告警已解决: {message}")

    def get_active_alerts(self, category: str = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = [a for a in self._active_alerts.values() if not a.resolved]
        if category:
            alerts = [a for a in alerts if a.category == category]
        return alerts

    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """获取告警历史"""
        return [a.to_dict() for a in list(self._alerts)[-limit:]]

    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    # ─────────────────────────────────────────────────────────────
    # 系统健康
    # ─────────────────────────────────────────────────────────────

    def get_system_health(self) -> Dict:
        """获取系统健康状态"""
        node_health = self.get_node_health()
        tx_stats = self.get_transaction_stats()

        # 计算健康分数
        health_score = 100

        # 节点扣分
        offline_nodes = sum(1 for n in node_health.values() if n["state"] == "offline")
        if offline_nodes > 0:
            health_score -= min(30, offline_nodes * 10)

        # 交易失败率扣分
        if tx_stats["total"] > 0:
            fail_rate = tx_stats["failed"] / tx_stats["total"]
            health_score -= fail_rate * 40

        # 活跃告警扣分
        critical_alerts = sum(1 for a in self._active_alerts.values()
                              if a.level in (AlertLevel.ERROR, AlertLevel.CRITICAL))
        health_score -= min(20, critical_alerts * 10)

        return {
            "score": max(0, health_score),
            "status": (
                "healthy" if health_score >= 80 else
                "degraded" if health_score >= 50 else
                "unhealthy"
            ),
            "node_count": len(node_health),
            "online_nodes": sum(1 for n in node_health.values() if n["state"] == "online"),
            "tx_stats": tx_stats,
            "active_alerts": len(self._active_alerts),
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ─────────────────────────────────────────────────────────────
    # 调度
    # ─────────────────────────────────────────────────────────────

    def start(self, interval: int = 30):
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self._thread.start()
        logger.info("监控服务已启动")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("监控服务已停止")

    def _monitor_loop(self, interval: int):
        """监控循环"""
        # 如果未指定间隔，从配置读取
        if interval is None and get_config:
            config = get_config()
            interval = config.get("polling.monitor_interval", 30)
        
        while self._running:
            try:
                self.check_node_health()
                # 可以添加更多定期检查
            except Exception as e:
                logger.error(f"监控检查失败: {e}")

            time.sleep(interval)


class MetricsCollector:
    """指标收集器（用于导出到Prometheus等）"""

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

    def inc_counter(self, name: str, value: float = 1):
        """增加计数器"""
        self._counters[name] += value

    def set_gauge(self, name: str, value: float):
        """设置仪表值"""
        self._gauges[name] = value

    def observe_histogram(self, name: str, value: float):
        """记录直方图值"""
        self._histograms[name].append(value)

    def get_prometheus_metrics(self) -> str:
        """生成Prometheus格式指标"""
        lines = []

        # 计数器
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        # 仪表
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # 直方图
        for name, values in self._histograms.items():
            if values:
                avg = sum(values) / len(values)
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_avg {avg}")

        return "\n".join(lines)
