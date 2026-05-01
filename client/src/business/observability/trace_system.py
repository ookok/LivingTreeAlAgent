"""
任务链追踪系统

实现分布式追踪功能，支持：
- 任务链追踪
- 跨度(span)记录
- 父子关系维护
- 延迟统计
- 可视化追踪数据
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

class SpanKind(Enum):
    """跨度类型"""
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"

class SpanStatus(Enum):
    """跨度状态"""
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class Span:
    """追踪跨度"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    duration: Optional[float] = None

    def finish(self, status: SpanStatus = SpanStatus.OK):
        """完成跨度"""
        self.end_time = time.time()
        self.status = status
        self.duration = self.end_time - self.start_time

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })

@dataclass
class Trace:
    """追踪对象"""
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    service_name: str = "livingtree"

    def add_span(self, span: Span):
        """添加跨度"""
        self.spans.append(span)
        if span.end_time:
            self._update_end_time()

    def _update_end_time(self):
        """更新结束时间"""
        end_times = [s.end_time for s in self.spans if s.end_time]
        if end_times:
            self.end_time = max(end_times)

class Tracer:
    """
    追踪器
    
    支持任务链的分布式追踪，记录每个步骤的执行时间、状态和上下文。
    """
    
    def __init__(self, service_name: str = "livingtree"):
        self.service_name = service_name
        self.traces: Dict[str, Trace] = {}
        self.active_spans: Dict[str, Span] = {}
    
    def start_trace(self, trace_id: Optional[str] = None) -> str:
        """
        开始新的追踪
        
        Args:
            trace_id: 追踪ID（可选，自动生成）
        
        Returns:
            追踪ID
        """
        tid = trace_id or str(uuid.uuid4())
        self.traces[tid] = Trace(
            trace_id=tid,
            service_name=self.service_name
        )
        return tid
    
    def start_span(
        self,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        开始新的跨度
        
        Args:
            name: 跨度名称
            trace_id: 追踪ID
            parent_span_id: 父跨度ID
            kind: 跨度类型
            attributes: 自定义属性
        
        Returns:
            跨度ID
        """
        span_id = str(uuid.uuid4())
        
        if trace_id not in self.traces:
            self.start_trace(trace_id)
        
        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            attributes=attributes or {}
        )
        
        self.active_spans[span_id] = span
        self.traces[trace_id].add_span(span)
        
        return span_id
    
    def finish_span(self, span_id: str, status: SpanStatus = SpanStatus.OK):
        """
        完成跨度
        
        Args:
            span_id: 跨度ID
            status: 完成状态
        """
        if span_id in self.active_spans:
            span = self.active_spans[span_id]
            span.finish(status)
            del self.active_spans[span_id]
    
    def add_span_event(self, span_id: str, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        向跨度添加事件
        
        Args:
            span_id: 跨度ID
            name: 事件名称
            attributes: 事件属性
        """
        if span_id in self.active_spans:
            self.active_spans[span_id].add_event(name, attributes)
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """
        获取追踪信息
        
        Args:
            trace_id: 追踪ID
        
        Returns:
            追踪对象
        """
        return self.traces.get(trace_id)
    
    def get_trace_summary(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪摘要
        
        Args:
            trace_id: 追踪ID
        
        Returns:
            追踪摘要字典
        """
        trace = self.traces.get(trace_id)
        if not trace:
            return None
        
        spans = trace.spans
        completed_spans = [s for s in spans if s.end_time]
        
        return {
            "trace_id": trace.trace_id,
            "service_name": trace.service_name,
            "start_time": trace.start_time,
            "end_time": trace.end_time,
            "duration": trace.end_time - trace.start_time if trace.end_time else None,
            "total_spans": len(spans),
            "completed_spans": len(completed_spans),
            "success_rate": sum(1 for s in completed_spans if s.status == SpanStatus.OK) / len(completed_spans) if completed_spans else None,
            "avg_span_duration": sum(s.duration for s in completed_spans if s.duration) / len(completed_spans) if completed_spans else None,
            "spans": [{
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "name": s.name,
                "kind": s.kind.value,
                "status": s.status.value,
                "duration": s.duration,
                "start_time": s.start_time,
                "attributes": s.attributes
            } for s in spans]
        }
    
    def list_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取追踪列表
        
        Args:
            limit: 返回数量限制
        
        Returns:
            追踪摘要列表
        """
        traces = list(self.traces.values())
        traces.sort(key=lambda t: t.start_time, reverse=True)
        
        return [self.get_trace_summary(t.trace_id) for t in traces[:limit]]
    
    def clear_traces(self):
        """清除所有追踪数据"""
        self.traces.clear()
        self.active_spans.clear()

# 全局追踪器实例
_tracer_instance = None

def get_tracer(service_name: str = "livingtree") -> Tracer:
    """获取全局追踪器实例"""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = Tracer(service_name)
    return _tracer_instance