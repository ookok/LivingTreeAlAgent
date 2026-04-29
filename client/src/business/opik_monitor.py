"""
📊 Opik 生产监控器

为 LivingTreeAI 提供生产环境监控能力：
- Tool 执行监控（成功率、失败率、延迟）
- Token 使用监控
- 成本监控
- 告警规则（失败率、延迟阈值）
- 实时监控数据统计
"""

import logging
import time
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)

# ============= 告警规则配置 =============

@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: str  # "failure_rate", "latency", "token_usage", "cost"
    threshold: float
    window_minutes: int = 10  # 统计窗口（分钟）
    enabled: bool = True
    
    def should_alert(self, current_value: float) -> bool:
        """检查是否应该告警"""
        if not self.enabled:
            return False
        return current_value >= self.threshold


@dataclass
class MonitorConfig:
    """监控配置"""
    enabled: bool = True
    
    # 监控选项
    monitor_tool_calls: bool = True
    monitor_token_usage: bool = True
    monitor_cost: bool = True
    monitor_latency: bool = True
    
    # 告警规则
    alert_rules: List[AlertRule] = field(default_factory=lambda: [
        AlertRule(name="高失败率", metric="failure_rate", threshold=0.3, window_minutes=10),
        AlertRule(name="高延迟", metric="latency", threshold=5.0, window_minutes=10),
        AlertRule(name="高Token使用", metric="token_usage", threshold=100000, window_minutes=60),
        AlertRule(name="高成本", metric="cost", threshold=10.0, window_minutes=60),
    ])
    
    # 统计窗口
    stats_window_size: int = 1000  # 保存最近 N 条记录
    cleanup_interval: int = 3600  # 清理间隔（秒）


# ============= 监控数据统计 =============

@dataclass
class ToolExecutionRecord:
    """Tool 执行记录"""
    tool_name: str
    success: bool
    latency: float  # 秒
    token_usage: int = 0
    cost: float = 0.0
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MonitorStats:
    """监控统计"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.records: deque = deque(maxlen=window_size)
        self.tool_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total": 0,
            "success": 0,
            "failure": 0,
            "total_latency": 0.0,
            "total_tokens": 0,
            "total_cost": 0.0,
        })
        
    def add_record(self, record: ToolExecutionRecord):
        """添加执行记录"""
        self.records.append(record)
        
        # 更新工具统计
        stats = self.tool_stats[record.tool_name]
        stats["total"] += 1
        if record.success:
            stats["success"] += 1
        else:
            stats["failure"] += 1
        stats["total_latency"] += record.latency
        stats["total_tokens"] += record.token_usage
        stats["total_cost"] += record.cost
    
    def get_failure_rate(self, tool_name: Optional[str] = None, window_minutes: int = 10) -> float:
        """
        获取失败率
        
        Args:
            tool_name: 工具名称，如果为 None 则计算所有工具
            window_minutes: 统计窗口（分钟）
        """
        cutoff_time = time.time() - window_minutes * 60
        relevant_records = [
            r for r in self.records
            if r.timestamp >= cutoff_time and (tool_name is None or r.tool_name == tool_name)
        ]
        
        if not relevant_records:
            return 0.0
        
        failures = sum(1 for r in relevant_records if not r.success)
        return failures / len(relevant_records)
    
    def get_avg_latency(self, tool_name: Optional[str] = None, window_minutes: int = 10) -> float:
        """获取平均延迟"""
        cutoff_time = time.time() - window_minutes * 60
        relevant_records = [
            r for r in self.records
            if r.timestamp >= cutoff_time and (tool_name is None or r.tool_name == tool_name)
        ]
        
        if not relevant_records:
            return 0.0
        
        return sum(r.latency for r in relevant_records) / len(relevant_records)
    
    def get_total_tokens(self, tool_name: Optional[str] = None, window_minutes: int = 10) -> int:
        """获取总 Token 使用"""
        cutoff_time = time.time() - window_minutes * 60
        relevant_records = [
            r for r in self.records
            if r.timestamp >= cutoff_time and (tool_name is None or r.tool_name == tool_name)
        ]
        
        return sum(r.token_usage for r in relevant_records)
    
    def get_total_cost(self, tool_name: Optional[str] = None, window_minutes: int = 10) -> float:
        """获取总成本"""
        cutoff_time = time.time() - window_minutes * 60
        relevant_records = [
            r for r in self.records
            if r.timestamp >= cutoff_time and (tool_name is None or r.tool_name == tool_name)
        ]
        
        return sum(r.cost for r in relevant_records)
    
    def get_tool_stats(self, tool_name: str) -> Dict:
        """获取指定工具的统计"""
        return self.tool_stats.get(tool_name, {
            "total": 0,
            "success": 0,
            "failure": 0,
            "total_latency": 0.0,
            "total_tokens": 0,
            "total_cost": 0.0,
        })
    
    def get_all_stats(self) -> Dict:
        """获取所有统计"""
        return {
            "total_records": len(self.records),
            "tools": dict(self.tool_stats),
            "overall_failure_rate": self.get_failure_rate(),
            "overall_avg_latency": self.get_avg_latency(),
            "overall_total_tokens": self.get_total_tokens(),
            "overall_total_cost": self.get_total_cost(),
        }


# ============= 监控器核心 =============

# 导入 Opik 追踪函数
try:
    from client.src.business.opik_tracer import start_trace, log_trace
    OPIK_TRACE_AVAILABLE = True
except ImportError:
    OPIK_TRACE_AVAILABLE = False
    start_trace = lambda *a, **kw: None
    log_trace = lambda *a, **kw: None


class OpikMonitor:
    """
    Opik 生产监控器
    
    功能：
    - 监控 Tool 执行
    - 检查告警规则
    - 记录监控数据
    - 生成监控报告
    """
    
    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self.stats = MonitorStats(window_size=self.config.stats_window_size)
        self.alert_history: List[Dict] = []
        self._opik_available = False
        
        # 尝试导入 Opik 和追踪函数
        try:
            import opik
            self.opik = opik
            self._opik_available = True
            logger.info("✅ Opik 监控器初始化成功")
        except ImportError:
            logger.warning("Opik SDK 未安装，监控器将以本地模式运行")
    
    def monitor_tool_execution(self, tool_name: str):
        """
        监控 Tool 执行的装饰器
        
        Usage:
            @monitor.monitor_tool_execution("my_tool")
            def execute_tool(...):
                ...
        """
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                if not self.config.enabled:
                    return func(*args, **kwargs)
                
                start_time = time.time()
                success = True
                error = None
                token_usage = 0
                cost = 0.0
                
                try:
                    result = func(*args, **kwargs)
                    
                    # 尝试从结果中提取 token 使用和成本
                    if isinstance(result, dict):
                        token_usage = result.get("token_usage", 0)
                        cost = result.get("cost", 0.0)
                    
                    return result
                
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                
                finally:
                    latency = time.time() - start_time
                    
                    # 创建执行记录
                    record = ToolExecutionRecord(
                        tool_name=tool_name,
                        success=success,
                        latency=latency,
                        token_usage=token_usage,
                        cost=cost,
                        error=error,
                    )
                    
                    # 添加到统计
                    self.stats.add_record(record)
                    
                    # 检查告警规则
                    self._check_alerts(tool_name)
                    
                    # 记录到 Opik（如果可用）
                    if self._opik_available:
                        self._log_to_opik(record)
            
            return wrapper
        return decorator
    
    def _check_alerts(self, tool_name: str):
        """检查告警规则"""
        for rule in self.config.alert_rules:
            if not rule.enabled:
                continue
            
            current_value = self._get_metric_value(rule.metric, tool_name, rule.window_minutes)
            
            if rule.should_alert(current_value):
                alert = {
                    "timestamp": time.time(),
                    "rule_name": rule.name,
                    "metric": rule.metric,
                    "threshold": rule.threshold,
                    "current_value": current_value,
                    "tool_name": tool_name,
                }
                self.alert_history.append(alert)
                logger.warning(f"⚠️ 告警: {rule.name} - {tool_name} - 当前值: {current_value:.2f}")
    
    def _get_metric_value(self, metric: str, tool_name: str, window_minutes: int) -> float:
        """获取指标值"""
        if metric == "failure_rate":
            return self.stats.get_failure_rate(tool_name, window_minutes)
        elif metric == "latency":
            return self.stats.get_avg_latency(tool_name, window_minutes)
        elif metric == "token_usage":
            return float(self.stats.get_total_tokens(tool_name, window_minutes))
        elif metric == "cost":
            return self.stats.get_total_cost(tool_name, window_minutes)
        else:
            return 0.0
    
    def _log_to_opik(self, record: ToolExecutionRecord):
        """记录到 Opik"""
        if not OPIK_TRACE_AVAILABLE:
            return
        
        try:
            trace = start_trace(
                name=f"monitor_{record.tool_name}",
                trace_type="tool",
                metadata={"timestamp": record.timestamp}
            )
            
            if trace is not None:
                log_trace(
                    trace,
                    input_data={"tool_name": record.tool_name},
                    output_data={
                        "success": record.success,
                        "latency": record.latency,
                        "token_usage": record.token_usage,
                        "cost": record.cost,
                        "error": record.error,
                    },
                    metadata={
                        "timestamp": record.timestamp,
                        "tool_name": record.tool_name,
                    }
                )
        except Exception as e:
            logger.warning(f"记录到 Opik 失败: {e}")
    
    def get_monitoring_report(self) -> Dict:
        """获取监控报告"""
        return {
            "timestamp": time.time(),
            "stats": self.stats.get_all_stats(),
            "recent_alerts": self.alert_history[-10:] if self.alert_history else [],
            "alert_count": len(self.alert_history),
        }
    
    def print_monitoring_report(self):
        """打印监控报告"""
        report = self.get_monitoring_report()
        stats = report["stats"]
        
        print("=" * 60)
        print("📊 Opik 监控报告")
        print("=" * 60)
        print(f"总执行次数: {stats['total_records']}")
        print(f"总失败率: {stats['overall_failure_rate']:.2%}")
        print(f"平均延迟: {stats['overall_avg_latency']:.2f}s")
        print(f"总 Token 使用: {stats['overall_total_tokens']}")
        print(f"总成本: ${stats['overall_total_cost']:.4f}")
        print(f"\n告警次数: {report['alert_count']}")
        
        if report["recent_alerts"]:
            print("\n最近告警:")
            for alert in report["recent_alerts"]:
                print(f"  - {alert['rule_name']}: {alert['tool_name']} = {alert['current_value']:.2f}")
        
        print("\n工具统计:")
        for tool_name, tool_stats in stats["tools"].items():
            if tool_stats["total"] > 0:
                failure_rate = tool_stats["failure"] / tool_stats["total"]
                avg_latency = tool_stats["total_latency"] / tool_stats["total"]
                print(f"  {tool_name}:")
                print(f"    执行次数: {tool_stats['total']}")
                print(f"    失败率: {failure_rate:.2%}")
                print(f"    平均延迟: {avg_latency:.2f}s")
        
        print("=" * 60)


# ============= 全局监控器实例 =============

_global_monitor: Optional[OpikMonitor] = None


def get_monitor() -> OpikMonitor:
    """获取全局监控器实例（单例）"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = OpikMonitor()
    return _global_monitor


def configure_monitor(config: MonitorConfig):
    """配置全局监控器"""
    global _global_monitor
    _global_monitor = OpikMonitor(config)


# ============= 便捷装饰器 =============

def monitor_tool(tool_name: Optional[str] = None):
    """
    便捷装饰器：监控 Tool 执行
    
    Usage:
        @monitor_tool("my_tool")
        def execute_tool(...):
            ...
        
        # 或者使用函数名作为 tool_name
        @monitor_tool()
        def my_tool(...):
            ...
    """
    def decorator(func):
        name = tool_name or func.__name__
        monitor = get_monitor()
        return monitor.monitor_tool_execution(name)(func)
    
    if tool_name is None:
        # 如果只传了函数，没有传 tool_name
        return decorator(tool_name)
    
    return decorator


# ============= 导出 =============

__all__ = [
    "MonitorConfig",
    "AlertRule",
    "MonitorStats",
    "OpikMonitor",
    "get_monitor",
    "configure_monitor",
    "monitor_tool",
]
