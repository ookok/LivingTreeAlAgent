"""
可观测性仪表盘

提供任务链执行的可视化展示，包括：
- 实时指标面板
- 追踪时间线
- 日志查看器
- 告警列表
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class MetricCard:
    """指标卡片"""
    title: str
    value: str
    unit: str = ""
    trend: Optional[float] = None
    status: str = "normal"  # normal, warning, critical

@dataclass
class TraceNode:
    """追踪节点"""
    span_id: str
    name: str
    duration: float
    status: str
    parent_id: Optional[str] = None
    children: List['TraceNode'] = field(default_factory=list)

class ObservabilityDashboard:
    """
    可观测性仪表盘
    
    提供任务链执行数据的可视化展示。
    """
    
    def __init__(self):
        from .observer import get_observer
        self.observer = get_observer()
    
    def get_metric_cards(self) -> List[MetricCard]:
        """
        获取指标卡片数据
        
        Returns:
            指标卡片列表
        """
        metrics = self.observer.metrics.collect_all()
        counters = metrics.get("counters", {})
        summaries = metrics.get("summaries", {})
        
        cards = []
        
        # 任务链指标
        chain_started = counters.get("task_chain.started", {}).get("value", 0)
        chain_completed = counters.get("task_chain.completed", {}).get("value", 0)
        chain_failed = counters.get("task_chain.failed", {}).get("value", 0)
        
        success_rate = (chain_completed / (chain_completed + chain_failed)) * 100 if (chain_completed + chain_failed) > 0 else 100
        
        cards.append(MetricCard(
            title="任务链总数",
            value=str(chain_started),
            status="normal"
        ))
        
        cards.append(MetricCard(
            title="成功率",
            value=f"{success_rate:.1f}%",
            status="normal" if success_rate >= 90 else "warning" if success_rate >= 70 else "critical"
        ))
        
        # 任务指标
        task_started = counters.get("task.started", {}).get("value", 0)
        task_completed = counters.get("task.completed", {}).get("value", 0)
        
        cards.append(MetricCard(
            title="任务总数",
            value=str(task_started),
            status="normal"
        ))
        
        # 延迟指标
        chain_duration = summaries.get("task_chain.duration", {}).get("summary", {})
        avg_duration = chain_duration.get("avg", 0)
        p99_duration = chain_duration.get("p99", 0)
        
        cards.append(MetricCard(
            title="平均延迟",
            value=f"{avg_duration:.2f}",
            unit="s",
            status="normal" if avg_duration < 5 else "warning" if avg_duration < 30 else "critical"
        ))
        
        cards.append(MetricCard(
            title="P99延迟",
            value=f"{p99_duration:.2f}",
            unit="s",
            status="normal" if p99_duration < 30 else "warning" if p99_duration < 60 else "critical"
        ))
        
        # 活跃任务数
        gauges = metrics.get("gauges", {})
        active_tasks = gauges.get("active_tasks", {}).get("value", 0)
        active_chains = gauges.get("active_chains", {}).get("value", 0)
        
        cards.append(MetricCard(
            title="活跃任务",
            value=str(int(active_tasks)),
            status="normal" if active_tasks < 10 else "warning"
        ))
        
        cards.append(MetricCard(
            title="活跃任务链",
            value=str(int(active_chains)),
            status="normal" if active_chains < 5 else "warning"
        ))
        
        return cards
    
    def get_trace_timeline(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取追踪时间线数据
        
        Args:
            trace_id: 追踪ID（可选，默认获取最新的）
        
        Returns:
            时间线数据
        """
        traces = self.observer.tracer.list_traces(limit=1)
        
        if not traces:
            return {"trace_id": None, "nodes": [], "duration": 0}
        
        trace = traces[0] if not trace_id else self.observer.tracer.get_trace_summary(trace_id)
        
        if not trace:
            return {"trace_id": None, "nodes": [], "duration": 0}
        
        # 构建树形结构
        nodes = []
        span_map = {}
        
        for span in trace.get("spans", []):
            node = TraceNode(
                span_id=span["span_id"],
                name=span["name"],
                duration=span["duration"] or 0,
                status=span["status"],
                parent_id=span["parent_span_id"]
            )
            span_map[span["span_id"]] = node
        
        # 构建父子关系
        root_nodes = []
        for node in span_map.values():
            if node.parent_id and node.parent_id in span_map:
                span_map[node.parent_id].children.append(node)
            else:
                root_nodes.append(node)
        
        return {
            "trace_id": trace["trace_id"],
            "duration": trace.get("duration", 0),
            "start_time": trace.get("start_time", 0),
            "nodes": self._serialize_nodes(root_nodes)
        }
    
    def _serialize_nodes(self, nodes: List[TraceNode]) -> List[Dict[str, Any]]:
        """序列化节点"""
        result = []
        for node in nodes:
            result.append({
                "span_id": node.span_id,
                "name": node.name,
                "duration": node.duration,
                "status": node.status,
                "children": self._serialize_nodes(node.children)
            })
        return result
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取最近日志
        
        Args:
            limit: 返回数量限制
        
        Returns:
            日志列表
        """
        logs = self.observer.logger.get_logs(limit=limit)
        
        # 格式化时间
        for log in logs:
            log["formatted_time"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", 
                time.localtime(log["timestamp"])
            )
        
        return logs
    
    def get_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取告警列表
        
        Args:
            limit: 返回数量限制
        
        Returns:
            告警列表
        """
        alerts = self.observer.get_alerts(limit=limit)
        
        return [{
            "alert_id": a.alert_id,
            "level": a.level.value,
            "message": a.message,
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(a.timestamp)),
            "resolved": a.resolved,
            "metadata": a.metadata
        } for a in alerts]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        获取完整的仪表盘数据
        
        Returns:
            包含所有仪表盘数据的字典
        """
        return {
            "metrics": [card.__dict__ for card in self.get_metric_cards()],
            "timeline": self.get_trace_timeline(),
            "logs": self.get_recent_logs(limit=30),
            "alerts": self.get_alerts(limit=15),
            "timestamp": time.time()
        }
    
    def export_data(self, format_type: str = "json") -> str:
        """
        导出数据
        
        Args:
            format_type: 导出格式（json）
        
        Returns:
            导出的字符串
        """
        data = self.get_dashboard_data()
        
        if format_type == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        
        return str(data)

# 全局仪表盘实例
_dashboard_instance = None

def get_dashboard() -> ObservabilityDashboard:
    """获取全局仪表盘实例"""
    global _dashboard_instance
    if _dashboard_instance is None:
        _dashboard_instance = ObservabilityDashboard()
    return _dashboard_instance