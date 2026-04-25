#!/usr/bin/env python3
"""
LivingTreeAI Phase 2 - Agent 性能监控
实时监控智能体性能、任务执行、资源使用
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading
import time


class MetricType(Enum):
    """指标类型"""
    LATENCY = "latency"           # 延迟
    THROUGHPUT = "throughput"     # 吞吐量
    SUCCESS_RATE = "success_rate" # 成功率
    CPU_USAGE = "cpu_usage"       # CPU使用率
    MEMORY_USAGE = "memory_usage" # 内存使用率
    TASK_QUEUE = "task_queue"     # 任务队列长度
    ACTIVE_AGENTS = "active_agents"  # 活跃代理数


@dataclass
class MetricPoint:
    """指标点"""
    metric_type: MetricType
    value: float
    timestamp: float = field(default_factory=datetime.now().timestamp)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """智能体指标"""
    agent_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_latency: float = 0.0
    avg_latency: float = 0.0
    last_task_time: Optional[float] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0


class MetricsCollector:
    """
    指标收集器
    收集和存储各类性能指标
    """
    
    def __init__(self, retention_seconds: int = 3600):
        self.metrics: Dict[MetricType, List[MetricPoint]] = {
            mtype: [] for mtype in MetricType
        }
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.retention_seconds = retention_seconds
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5分钟清理一次
    
    def record_metric(self, metric_type: MetricType, value: float,
                     tags: Dict[str, str] = None) -> None:
        """记录指标"""
        point = MetricPoint(
            metric_type=metric_type,
            value=value,
            tags=tags or {}
        )
        
        with self._lock:
            self.metrics[metric_type].append(point)
            self._cleanup_old_metrics(metric_type)
    
    def _cleanup_old_metrics(self, metric_type: MetricType) -> None:
        """清理过期指标"""
        cutoff = datetime.now().timestamp() - self.retention_seconds
        self.metrics[metric_type] = [
            m for m in self.metrics[metric_type]
            if m.timestamp > cutoff
        ]
    
    def get_metrics(self, metric_type: MetricType,
                    since: float = None) -> List[MetricPoint]:
        """获取指标"""
        with self._lock:
            points = self.metrics.get(metric_type, [])
            if since:
                points = [p for p in points if p.timestamp > since]
            return points
    
    def get_average(self, metric_type: MetricType,
                   since: float = None) -> float:
        """获取平均值"""
        points = self.get_metrics(metric_type, since)
        if not points:
            return 0.0
        return sum(p.value for p in points) / len(points)
    
    def get_percentile(self, metric_type: MetricType, percentile: float,
                      since: float = None) -> float:
        """获取百分位数"""
        points = self.get_metrics(metric_type, since)
        if not points:
            return 0.0
        
        values = sorted(p.value for p in points)
        idx = int(len(values) * percentile / 100)
        return values[min(idx, len(values) - 1)]
    
    # ==================== 智能体指标 ====================
    
    def record_agent_task(self, agent_id: str, success: bool, latency: float) -> None:
        """记录智能体任务"""
        with self._lock:
            if agent_id not in self.agent_metrics:
                self.agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)
            
            metrics = self.agent_metrics[agent_id]
            
            if success:
                metrics.tasks_completed += 1
            else:
                metrics.tasks_failed += 1
            
            metrics.total_latency += latency
            metrics.avg_latency = metrics.total_latency / (metrics.tasks_completed + metrics.tasks_failed)
            metrics.last_task_time = datetime.now().timestamp()
    
    def get_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """获取智能体指标"""
        with self._lock:
            return self.agent_metrics.get(agent_id)
    
    def get_all_agent_metrics(self) -> Dict[str, AgentMetrics]:
        """获取所有智能体指标"""
        with self._lock:
            return self.agent_metrics.copy()


class PerformanceMonitor:
    """
    性能监控器
    实时监控和告警
    """
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.alerts: List[Dict[str, Any]] = []
        self.alert_rules: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def add_alert_rule(self, name: str, condition: Callable,
                      severity: str = "warning") -> None:
        """添加告警规则"""
        self.alert_rules[name] = {
            'condition': condition,
            'severity': severity,
            'last_triggered': None
        }
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """检查告警"""
        alerts = []
        
        with self._lock:
            for name, rule in self.alert_rules.items():
                try:
                    if rule['condition'](self.collector):
                        alert = {
                            'name': name,
                            'severity': rule['severity'],
                            'timestamp': datetime.now().timestamp(),
                            'message': f"Alert triggered: {name}"
                        }
                        alerts.append(alert)
                        rule['last_triggered'] = datetime.now().timestamp()
                except Exception as e:
                    pass
        
        self.alerts.extend(alerts)
        return alerts
    
    def start_monitoring(self, interval: float = 1.0) -> None:
        """开始监控"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self, interval: float) -> None:
        """监控循环"""
        while self._monitoring:
            self.check_alerts()
            time.sleep(interval)
    
    def get_alerts(self, since: float = None) -> List[Dict[str, Any]]:
        """获取告警"""
        with self._lock:
            if since:
                return [a for a in self.alerts if a['timestamp'] > since]
            return self.alerts.copy()
    
    def clear_alerts(self) -> None:
        """清除告警"""
        with self._lock:
            self.alerts.clear()


class PerformanceDashboard:
    """
    性能仪表板
    汇总和展示性能数据
    """
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        now = datetime.now().timestamp()
        last_5min = now - 300
        last_1hour = now - 3600
        
        return {
            'timestamp': now,
            'latency': {
                'avg_5min': self.collector.get_average(MetricType.LATENCY, last_5min),
                'avg_1hour': self.collector.get_average(MetricType.LATENCY, last_1hour),
                'p95': self.collector.get_percentile(MetricType.LATENCY, 95, last_1hour),
                'p99': self.collector.get_percentile(MetricType.LATENCY, 99, last_1hour),
            },
            'throughput': {
                'avg_5min': self.collector.get_average(MetricType.THROUGHPUT, last_5min),
                'avg_1hour': self.collector.get_average(MetricType.THROUGHPUT, last_1hour),
            },
            'success_rate': {
                'avg_1hour': self.collector.get_average(MetricType.SUCCESS_RATE, last_1hour),
            },
            'agents': {
                agent_id: {
                    'tasks_completed': m.tasks_completed,
                    'tasks_failed': m.tasks_failed,
                    'avg_latency': m.avg_latency,
                    'last_task': m.last_task_time
                }
                for agent_id, m in self.collector.get_all_agent_metrics().items()
            }
        }
    
    def get_agent_ranking(self, metric: str = "tasks_completed") -> List[Dict[str, Any]]:
        """获取智能体排名"""
        agents = self.collector.get_all_agent_metrics()
        
        ranking = []
        for agent_id, metrics in agents.items():
            if metric == "tasks_completed":
                value = metrics.tasks_completed
            elif metric == "success_rate":
                total = metrics.tasks_completed + metrics.tasks_failed
                value = metrics.tasks_completed / total if total > 0 else 0
            elif metric == "avg_latency":
                value = metrics.avg_latency
            else:
                value = 0
            
            ranking.append({
                'agent_id': agent_id,
                'value': value
            })
        
        ranking.sort(key=lambda x: x['value'], reverse=True)
        return ranking


# ==================== 全局实例 ====================

_metrics_collector: Optional[MetricsCollector] = None
_performance_monitor: Optional[PerformanceMonitor] = None
_performance_dashboard: Optional[PerformanceDashboard] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(get_metrics_collector())
    return _performance_monitor


def get_performance_dashboard() -> PerformanceDashboard:
    """获取全局性能仪表板"""
    global _performance_dashboard
    if _performance_dashboard is None:
        _performance_dashboard = PerformanceDashboard(get_metrics_collector())
    return _performance_dashboard


# ==================== CLI ====================

def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent 性能监控')
    parser.add_argument('--summary', '-s', action='store_true', help='显示性能摘要')
    parser.add_argument('--ranking', '-r', choices=['tasks', 'success', 'latency'],
                       help='显示排名')
    
    args = parser.parse_args()
    
    collector = get_metrics_collector()
    dashboard = get_performance_dashboard()
    
    # 记录测试指标
    collector.record_metric(MetricType.LATENCY, 100.5)
    collector.record_metric(MetricType.THROUGHPUT, 10.2)
    collector.record_metric(MetricType.SUCCESS_RATE, 0.95)
    
    collector.record_agent_task("agent1", True, 100.0)
    collector.record_agent_task("agent2", True, 150.0)
    collector.record_agent_task("agent3", False, 200.0)
    
    if args.summary:
        summary = dashboard.get_summary()
        print("性能摘要:")
        print(f"  延迟 (5min平均): {summary['latency']['avg_5min']:.2f}ms")
        print(f"  吞吐量 (5min平均): {summary['throughput']['avg_5min']:.2f}/s")
        print(f"  成功率 (1hour): {summary['success_rate']['avg_1hour']*100:.1f}%")
    
    if args.ranking:
        if args.ranking == 'tasks':
            ranking = dashboard.get_agent_ranking('tasks_completed')
        elif args.ranking == 'success':
            ranking = dashboard.get_agent_ranking('success_rate')
        else:
            ranking = dashboard.get_agent_ranking('avg_latency')
        
        print(f"智能体排名 ({args.ranking}):")
        for i, item in enumerate(ranking, 1):
            print(f"  {i}. {item['agent_id']}: {item['value']:.2f}")


if __name__ == "__main__":
    main()
