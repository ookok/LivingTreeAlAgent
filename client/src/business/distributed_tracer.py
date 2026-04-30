"""
分布式追踪器 - 全链路追踪
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class Span:
    """追踪跨度"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    attributes: Dict[str, Any] = None
    parent_id: Optional[str] = None
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}
    
    def end(self):
        """结束跨度"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


@dataclass
class Trace:
    """追踪信息"""
    trace_id: str
    spans: List[Span] = None
    
    def __post_init__(self):
        if self.spans is None:
            self.spans = []
    
    def add_span(self, span: Span):
        """添加跨度"""
        self.spans.append(span)
    
    def get_total_duration(self) -> float:
        """获取总耗时"""
        if not self.spans:
            return 0.0
        return sum(s.duration_ms or 0 for s in self.spans)


class DistributedTracer:
    """分布式追踪器 - 全链路追踪"""
    
    def __init__(self):
        self._current_trace: Optional[Trace] = None
        self._active_spans: Dict[str, Span] = {}
        self._completed_traces: List[Trace] = []
        self._trace_id_counter = 0
    
    def _generate_trace_id(self) -> str:
        """生成追踪ID"""
        self._trace_id_counter += 1
        return f"trace-{self._trace_id_counter}-{int(time.time())}"
    
    def start_trace(self) -> str:
        """开始新追踪"""
        trace_id = self._generate_trace_id()
        self._current_trace = Trace(trace_id=trace_id)
        return trace_id
    
    def start_span(self, operation_name: str, parent_id: Optional[str] = None) -> str:
        """开始追踪 span"""
        span_id = f"{operation_name}-{int(time.time() * 1000)}"
        
        if self._current_trace:
            span = Span(
                operation_name=operation_name,
                start_time=time.time(),
                parent_id=parent_id,
                attributes={"span_id": span_id}
            )
            self._current_trace.add_span(span)
            self._active_spans[span_id] = span
        
        return span_id
    
    def end_span(self, span_id: str):
        """结束追踪 span"""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end()
    
    def end_trace(self):
        """结束追踪"""
        # 结束所有活跃的span
        for span_id in list(self._active_spans.keys()):
            self.end_span(span_id)
        
        if self._current_trace:
            self._completed_traces.append(self._current_trace)
            
            # 保留最近100条追踪记录
            if len(self._completed_traces) > 100:
                self._completed_traces.pop(0)
            
            self._current_trace = None
    
    async def trace_execution(self, operation_name: str, func, *args, **kwargs) -> Any:
        """追踪执行时间"""
        span_id = self.start_span(operation_name)
        try:
            return await func(*args, **kwargs)
        finally:
            self.end_span(span_id)
    
    def get_recent_traces(self, limit: int = 10) -> List[Trace]:
        """获取最近的追踪记录"""
        return self._completed_traces[-limit:]
    
    def get_slow_traces(self, threshold_ms: float = 1000) -> List[Trace]:
        """获取慢追踪记录"""
        return [t for t in self._completed_traces if t.get_total_duration() > threshold_ms]
    
    def get_trace_by_id(self, trace_id: str) -> Optional[Trace]:
        """根据ID获取追踪记录"""
        for trace in self._completed_traces:
            if trace.trace_id == trace_id:
                return trace
        return None


def get_tracer() -> DistributedTracer:
    """获取分布式追踪器单例"""
    if not hasattr(get_tracer, '_instance'):
        get_tracer._instance = DistributedTracer()
    return get_tracer._instance