# -*- coding: utf-8 -*-
"""
任务追踪器 - TaskTracer
========================

解决核心问题：**任务执行过程不可追踪、不可回溯**

当前 Handler 执行后只返回 ActionResult，中间过程完全黑箱。
TaskTracer 提供完整的执行链路追踪：

1. **任务 DAG**: 记录任务的依赖关系（复合意图拆分后的子任务）
2. **执行时间线**: 每个步骤的起止时间 + 耗时
3. **调用链路**: Bridge → Handler → LLMClient → HTTP 完整链路
4. **错误归因**: 哪一步出错，为什么出错，影响范围
5. **性能分析**: 各阶段耗时分布，瓶颈定位

与 IntentActionBridge 的集成方式：
- Bridge.execute() 开始前：tracer.start_trace(intent)
- Handler.handle() 中间：tracer.span(name, data)
- 执行结束后：tracer.end_trace(result)
- 查看结果：tracer.get_report()

Author: LivingTreeAI Team
Version: 1.0.0
from __future__ import annotations
"""


import time
import uuid
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────


class SpanStatus(Enum):
    """Span 状态"""
    STARTED = "started"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class Span:
    """
    一个执行跨度（类似 OpenTelemetry Span）

    记录一个逻辑操作单元的完整生命周期。
    支持嵌套（子 Span）。
    """
    span_id: str
    parent_id: Optional[str]  # None = root span
    name: str                 # 操作名称（如 "LLM Call", "Code Gen", "Parse"）
    
    # 时间
    start_time: float = 0.0
    end_time: float = 0.0
    
    # 状态
    status: SpanStatus = SpanStatus.STARTED
    
    # 数据
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    error_type: str = ""
    
    # 元数据
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 子 span
    children: List["Span"] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000
        if self.start_time > 0:
            return (time.time() - self.start_time) * 1000
        return 0.0

    @property
    def is_complete(self) -> bool:
        return self.status in (SpanStatus.OK, SpanStatus.ERROR, SpanStatus.TIMEOUT, SpanStatus.SKIPPED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id[:8],
            "name": self.name,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error[:80] if self.error else "",
            "tags": self.tags,
            "children_count": len(self.children),
        }


@dataclass
class TaskTrace:
    """一次完整的任务执行追踪记录"""
    trace_id: str
    intent_summary: str       # 用户原始输入摘要
    intent_type: str          # 意图类型
    
    # 根 span
    root_span: Optional[Span] = None
    
    # 整体信息
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "running"   # running / success / failed / partial
    
    # 结果聚合
    final_result: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, str]] = field(default_factory=list)
    tokens_used: int = 0
    
    # 元数据
    model_name: str = ""
    handler_name: str = ""
    session_id: str = ""

    @property
    def duration_ms(self) -> float:
        if self.end_time > 0 and self.start_time > 0:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    @property
    def total_spans(self) -> int:
        return self._count_spans(self.root_span)

    def _count_spans(self, span: Optional[Span]) -> int:
        if not span:
            return 0
        return 1 + sum(self._count_spans(c) for c in span.children)

    def get_critical_path(self) -> List[Span]:
        """获取关键路径（耗时最长的根到叶路径）"""
        if not self.root_span:
            return []
        
        path = [self.root_span]
        current = self.root_span
        
        while current.children:
            slowest = max(current.children, key=lambda s: s.duration_ms)
            path.append(slowest)
            current = slowest
        
        return path

    def to_report(self) -> str:
        """生成可读的追踪报告"""
        lines = [
            f"## 任务追踪: {self.intent_summary[:50]}",
            "",
            f"| 属性 | 值 |",
            f"|------|-----|",
            f"| Trace ID | {self.trace_id[:8]} |",
            f"| 意图类型 | {self.intent_type} |",
            f"| 处理器 | {self.handler_name} |",
            f"| 模型 | {self.model_name} |",
            f"| 总耗时 | {self.duration_ms:.0f}ms |",
            f"| Span 数 | {self.total_spans} |",
            f"| Token 用量 | {self.tokens_used} |",
            f"| 状态 | {self.status} |",
        ]
        
        # 关键路径
        critical = self.get_critical_path()
        if critical:
            lines.append("")
            lines.append("### 关键路径（性能瓶颈）")
            for s in critical:
                icon = "✅" if s.status == SpanStatus.OK else "❌"
                lines.append(f"- {icon} `{s.name}` — {s.duration_ms:.0f}s")
        
        # 错误列表
        if self.errors:
            lines.append("")
            lines.append("### 错误")
            for e in self.errors:
                lines.append(f"- **{e.get('span', '?')}**: {e.get('message', '')[:100]}")
        
        # Span 树
        if self.root_span:
            lines.append("")
            lines.append("### 执行树")
            lines.append(self._format_span_tree(self.root_span, indent=0))
        
        return "\n".join(lines)

    def _format_span_tree(self, span: Span, indent: int) -> str:
        prefix = "  " * indent
        icon = {
            SpanStatus.OK: "✅",
            SpanStatus.ERROR: "❌",
            SpanStatus.TIMEOUT: "⏱️",
            SpanStatus.SKIPPED: "⏭️",
            SpanStatus.RUNNING: "🔄",
        }.get(span.status, "❓")
        
        line = f"{prefix}{icon} {span.name} ({span.duration_ms:.0f}ms)"
        if span.error:
            line += f" ⚠️ {span.error[:40]}"
        
        for child in span.children:
            line += "\n" + self._format_span_tree(child, indent + 1)
        return line


# ── 核心类 ────────────────────────────────────────────────────────


class TaskTracer:
    """
    任务追踪器

    线程安全，支持并发追踪多个任务。
    
    使用模式：
        tracer = TaskTracer()
        
        trace = tracer.start_trace("写登录接口", "code_generation")
        with tracer.span(trace.trace_id, "parse"):
            intent = engine.parse(query)
        with tracer.span(trace.trace_id, "llm_call", {"model": "qwen3.5:4b"}):
            result = handler.handle(ctx)
        tracer.end_trace(trace.trace_id, result.to_dict())
        
        print(tracer.get_trace(trace.trace_id).to_report())
    """

    def __init__(self, max_traces: int = 200):
        self._traces: Dict[str, TaskTrace] = {}
        self._active_spans: Dict[str, Span] = {}  # trace_id → current active span
        self.max_traces = max_traces
        self._lock = threading.Lock()
        self.stats = {
            "total_traces": 0,
            "total_spans": 0,
            "errors": 0,
        }

    # ── 追踪管理 ────────────────────────────────────────────────

    def start_trace(
        self,
        query_or_summary: str,
        intent_type: str = "unknown",
        model_name: str = "",
        handler_name: str = "",
        session_id: str = "",
    ) -> TaskTrace:
        """开始一次新的任务追踪"""
        trace_id = uuid.uuid4().hex[:12]
        now = time.time()
        
        trace = TaskTrace(
            trace_id=trace_id,
            intent_summary=query_or_summary[:200],
            intent_type=intent_type,
            start_time=now,
            model_name=model_name,
            handler_name=handler_name,
            session_id=session_id,
        )
        
        # 创建根 span
        root = Span(
            span_id=uuid.uuid4().hex[:8],
            parent_id=None,
            name="execute",
            start_time=now,
            tags={"intent_type": intent_type},
        )
        trace.root_span = root
        
        with self._lock:
            # 容量控制
            if len(self._traces) >= self.max_traces:
                oldest_key = min(self._traces.keys(), 
                                key=lambda k: self._traces[k].start_time)
                del self._traces[oldest_key]
            
            self._traces[trace_id] = trace
            self._active_spans[trace_id] = root
            self.stats["total_traces"] += 1
        
        logger.debug(f"[Tracer] 开始追踪 {trace_id}: {query_or_summary[:40]}")
        return trace

    def end_trace(
        self,
        trace_id: str,
        result: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> Optional[TaskTrace]:
        """结束一次追踪"""
        with self._lock:
            trace = self._traces.get(trace_id)
            if not trace:
                return None
            
            trace.end_time = time.time()
            trace.final_result = result
            trace.status = status
            
            # 完成根 span
            if trace.root_span:
                trace.root_span.end_time = trace.end_time
                trace.root_span.status = (
                    SpanStatus.OK if status == "success" else SpanStatus.ERROR
                )
            
            # 清理活跃状态
            self._active_spans.pop(trace_id, None)
        
        return trace

    def get_trace(self, trace_id: str) -> Optional[TaskTrace]:
        """获取追踪记录"""
        return self._traces.get(trace_id)

    def list_recent(self, limit: int = 10) -> List[TaskTrace]:
        """最近的任务追踪"""
        traces = sorted(
            self._traces.values(), key=lambda t: t.start_time, reverse=True
        )
        return traces[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """统计信息"""
        by_status = {}
        for t in self._traces.values():
            by_status[t.status] = by_status.get(t.status, 0) + 1
        
        durations = [
            t.duration_ms for t in self._traces.values() if t.duration_ms > 0
        ]
        
        return {
            **self.stats,
            "active_traces": len(self._active_spans),
            "by_status": by_status,
            "avg_duration_ms": sum(durations) / max(len(durations), 1) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)] if len(durations) >= 10 else 0,
        }

    # ── Span 操作 ────────────────────────────────────────────────

    class SpanContext:
        """上下文管理器，用于 with 语句自动记录 span"""
        def __init__(self, tracer: "TaskTracer", trace_id: str, span: Span):
            self.tracer = tracer
            self.trace_id = trace_id
            self.span = span
        
        def __enter__(self) -> Span:
            return self.span
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.tracer.finish_span(
                    self.trace_id, self.span.span_id,
                    error=str(exc_val), error_type=exc_type.__name__
                )
            else:
                self.tracer.finish_span(self.trace_id, self.span.span_id)
            return False  # 不吞异常

    def span(
        self,
        trace_id: str,
        name: str,
        tags: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SpanContext:
        """
        创建一个新的子 span（支持 with 语句）
        
        Usage:
            with tracer.span(tid, "llm_call", {"model": "qwen"}) as sp:
                result = llm.chat(...)
                sp.output_data = {"content": result["content"]}
        """
        span = self.begin_span(trace_id, name, tags, data or {})
        return self.SpanContext(self, trace_id, span)

    def begin_span(
        self,
        trace_id: str,
        name: str,
        tags: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Span]:
        """手动开始一个 span"""
        with self._lock:
            trace = self._traces.get(trace_id)
            if not trace:
                return None
            
            parent = self._active_spans.get(trace_id)
            
            span = Span(
                span_id=uuid.uuid4().hex[:8],
                parent_id=parent.span_id if parent else None,
                name=name,
                start_time=time.time(),
                status=SpanStatus.RUNNING,
                tags=tags or {},
                input_data=data or {},
            )
            
            # 挂载到父 span
            if parent:
                parent.children.append(span)
            elif trace.root_span is None:
                trace.root_span = span
            
            # 设为当前活跃 span
            self._active_spans[trace_id] = span
            self.stats["total_spans"] += 1
        
        return span

    def finish_span(
        self,
        trace_id: str,
        span_id: str,
        *,
        error: str = "",
        error_type: str = "",
        output: Optional[Dict[str, Any]] = None,
    ) -> Optional[Span]:
        """完成一个 span"""
        with self._lock:
            trace = self._traces.get(trace_id)
            if not trace:
                return None
            
            # 在树中查找 span
            span = self._find_span(trace.root_span, span_id)
            if not span:
                return None
            
            span.end_time = time.time()
            span.output_data.update(output or {})
            
            if error:
                span.status = SpanStatus.ERROR
                span.error = error
                span.error_type = error_type
                
                # 记录到 trace 的错误列表
                trace.errors.append({
                    "span": span.name,
                    "message": error,
                    "type": error_type,
                })
                self.stats["errors"] += 1
            else:
                span.status = SpanStatus.OK
            
            # 如果完成的不是当前活跃 span，不切换父级
            current = self._active_spans.get(trace_id)
            if current and current.span_id == span_id:
                # 回退到父级 span
                self._active_spans[trace_id] = (
                    self._find_parent(trace.root_span, span_id)
                    if span.parent_id else span  # root span 保持
                )
        
        return span

    def record_tokens(self, trace_id: str, tokens: int):
        """记录 token 用量"""
        trace = self._traces.get(trace_id)
        if trace:
            trace.tokens_used += tokens

    def record_error(
        self,
        trace_id: str,
        span_name: str,
        error_msg: str,
        error_type: str = "",
    ):
        """直接记录一个错误（不需要 span）"""
        trace = self._traces.get(trace_id)
        if trace:
            trace.errors.append({
                "span": span_name,
                "message": error_msg,
                "type": error_type,
            })
            self.stats["errors"] += 1

    # ── 内部方法 ────────────────────────────────────────────────

    def _find_span(self, root: Optional[Span], span_id: str) -> Optional[Span]:
        if not root:
            return None
        if root.span_id == span_id:
            return root
        for child in root.children:
            found = self._find_span(child, span_id)
            if found:
                return found
        return None

    def _find_parent(self, root: Optional[Span], child_span_id: str) -> Optional[Span]:
        if not root:
            return None
        for c in root.children:
            if c.span_id == child_span_id:
                return root
            found = self._find_parent(c, child_span_id)
            if found:
                return found
        return root


# ── 测试入口 ──────────────────────────────────────────────────────


def _test_tracer():
    print("=" * 60)
    print("TaskTracer 测试")
    print("=" * 60)

    tracer = TaskTracer()

    # 模拟一次完整执行
    trace = tracer.start_trace(
        "帮我写一个 FastAPI 登录接口",
        "code_generation",
        model_name="qwen3.5:4b",
        handler_name="CodeGenerationHandler",
    )

    # Parse 阶段
    with tracer.span(trace.trace_id, "parse_intent") as sp:
        sp.output_data = {"intent_type": "code_generation"}
        import time; time.sleep(0.01)

    # Model Route
    with tracer.span(trace.trace_id, "model_route") as sp:
        sp.output_data = {"selected_model": "qwen3.5:4b"}

    # LLM Call
    try:
        with tracer.span(trace.trace_id, "llm_call", {"model": "qwen3.5:4b", "temperature": 0.3}) as sp:
            # 模拟 LLM 调用
            import time; time.sleep(0.05)
            sp.output_data = {
                "content": "from fastapi import APIRouter...",
                "tokens_used": 450,
            }
            tracer.record_tokens(trace.trace_id, 450)
    except Exception as e:
        tracer.record_error(trace.trace_id, "llm_call", str(e))

    # Post Process
    with tracer.span(trace.trace_id, "post_process") as sp:
        import time; time.sleep(0.01)

    # 结束
    tracer.end_trace(
        trace.trace_id,
        result={"output": "代码已生成", "type": "code"},
        status="success",
    )

    # 打印报告
    print(trace.to_report())

    # 统计
    stats = tracer.get_stats()
    print(f"\n--- 统计 ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _test_tracer()
