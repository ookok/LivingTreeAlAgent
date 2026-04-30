"""
Agent Chat 进度反馈系统
=======================

功能：
1. 实时进度反馈（百分比 + 文字描述）
2. 阶段化处理（意图分类 → 知识库 → 深度搜索 → 模型生成）
3. 流式 thinking 过程输出
4. UI 集成接口

用法：
```python
from business.agent_progress import AgentProgressCallback, get_progress_tracker

# 创建进度跟踪器
tracker = get_progress_tracker()

# 注册回调
def on_progress(progress: AgentProgress):
    print(f"[{progress.percent}%] {progress.message}")
    if progress.thinking:
        print(f"  思考: {progress.thinking}")

tracker.add_callback(on_progress)

# 使用 Agent
agent = HermesAgent(...)
agent.progress_callback = tracker.emit
```
"""

import time
import threading
from typing import Callable, Optional, List, Dict, Any, Iterator
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Iterator as ABCIterator


class ProgressPhase(Enum):
    """处理阶段"""
    IDLE = "空闲"
    INTENT_CLASSIFY = "意图分类"
    KNOWLEDGE_SEARCH = "知识库搜索"
    DEEP_SEARCH = "深度搜索"
    MODEL_ROUTE = "模型路由"
    LLM_GENERATING = "模型生成"
    THINKING = "思考中"
    EXECUTING_TOOL = "执行工具"
    FINALIZING = "生成结果"
    COMPLETED = "完成"


@dataclass
class AgentProgress:
    """进度信息"""
    phase: ProgressPhase = ProgressPhase.IDLE
    percent: int = 0           # 0-100
    message: str = ""          # 当前阶段的文字描述
    thinking: str = ""          # thinking 过程内容
    detail: str = ""           # 详细信息
    step: int = 0              # 当前步骤
    total_steps: int = 4       # 总步骤数
    elapsed: float = 0.0        # 已用时间（秒）
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（便于 JSON 传输）"""
        return {
            "phase": self.phase.value,
            "phase_key": self.phase.name,
            "percent": self.percent,
            "message": self.message,
            "thinking": self.thinking,
            "detail": self.detail,
            "step": self.step,
            "total_steps": self.total_steps,
            "elapsed": round(self.elapsed, 2),
            **self.metadata
        }


class AgentProgressCallback:
    """
    进度回调管理器
    
    支持多个回调函数，支持链式调用
    """
    
    def __init__(self):
        self._callbacks: List[Callable[[AgentProgress], None]] = []
        self._current_progress: Optional[AgentProgress] = None
        self._lock = threading.Lock()
        self._enabled = True
    
    def add_callback(self, cb: Callable[[AgentProgress], None]) -> 'AgentProgressCallback':
        """添加回调"""
        self._callbacks.append(cb)
        return self
    
    def remove_callback(self, cb: Callable[[AgentProgress], None]) -> bool:
        """移除回调"""
        try:
            self._callbacks.remove(cb)
            return True
        except ValueError:
            return False
    
    def clear_callbacks(self):
        """清空所有回调"""
        self._callbacks.clear()
    
    def emit(self, progress: AgentProgress):
        """触发进度更新"""
        if not self._enabled:
            return
        
        with self._lock:
            self._current_progress = progress
            for cb in self._callbacks:
                try:
                    cb(progress)
                except Exception as e:
                    print(f"[AgentProgress] 回调错误: {e}")
    
    def disable(self):
        """禁用回调"""
        self._enabled = False
    
    def enable(self):
        """启用回调"""
        self._enabled = True
    
    @property
    def current(self) -> Optional[AgentProgress]:
        """获取当前进度"""
        return self._current_progress


# 全局进度跟踪器
_global_tracker: Optional[AgentProgressCallback] = None
_tracker_lock = threading.Lock()


def get_progress_tracker() -> AgentProgressCallback:
    """获取全局进度跟踪器"""
    global _global_tracker
    with _tracker_lock:
        if _global_tracker is None:
            _global_tracker = AgentProgressCallback()
        return _global_tracker


class ProgressEmitter:
    """
    进度发射器 - 用于在 Agent 内部发射进度
    
    用法：
    ```python
    emitter = ProgressEmitter(progress_callback)
    emitter.emit(ProgressPhase.KNOWLEDGE_SEARCH, 30, "搜索知识库...")
    ```
    """
    
    # 阶段权重（用于计算百分比）
    PHASE_WEIGHTS = {
        ProgressPhase.INTENT_CLASSIFY: 5,
        ProgressPhase.KNOWLEDGE_SEARCH: 15,
        ProgressPhase.DEEP_SEARCH: 25,
        ProgressPhase.MODEL_ROUTE: 5,
        ProgressPhase.LLM_GENERATING: 40,
        ProgressPhase.EXECUTING_TOOL: 5,
        ProgressPhase.FINALIZING: 5,
    }
    
    def __init__(
        self,
        callback: Optional[Callable[[AgentProgress], None]] = None,
        auto_emit: bool = False
    ):
        self.callback = callback
        self.auto_emit = auto_emit
        self._start_time: float = 0
        self._phase: ProgressPhase = ProgressPhase.IDLE
        self._percent: int = 0
        self._step: int = 0
        self._thinking_buffer: str = ""
    
    def start(self):
        """开始跟踪"""
        self._start_time = time.time()
        self._phase = ProgressPhase.INTENT_CLASSIFY
        self._step = 1
        self._percent = 0
        self._thinking_buffer = ""
        
        if self.callback:
            self.callback(AgentProgress(
                phase=ProgressPhase.INTENT_CLASSIFY,
                percent=0,
                message="开始处理请求...",
                step=1,
                total_steps=7
            ))
    
    def emit(
        self,
        phase: ProgressPhase,
        percent: int,
        message: str,
        thinking: str = "",
        detail: str = "",
        step: Optional[int] = None,
        **metadata
    ):
        """发射进度"""
        self._phase = phase
        
        progress = AgentProgress(
            phase=phase,
            percent=min(100, max(0, percent)),
            message=message,
            thinking=thinking or self._thinking_buffer,
            detail=detail,
            step=step if step is not None else self._step,
            total_steps=7,
            elapsed=time.time() - self._start_time if self._start_time else 0,
            metadata=metadata
        )
        
        if self.callback:
            self.callback(progress)
        
        return progress
    
    def emit_phase(self, phase: ProgressPhase, message: str = "", **metadata):
        """发射阶段进度（自动计算百分比）"""
        # 计算累计百分比
        cumulative = 0
        for p, weight in self.PHASE_WEIGHTS.items():
            if p == phase:
                break
            cumulative += weight
        
        self._step = list(self.PHASE_WEIGHTS.keys()).index(phase) + 1
        
        return self.emit(
            phase=phase,
            percent=cumulative,
            message=message or f"正在{phase.value}...",
            step=self._step,
            **metadata
        )
    
    def emit_thinking(self, thinking: str):
        """发射 thinking 内容"""
        self._thinking_buffer += thinking
        
        if self.callback:
            self.callback(AgentProgress(
                phase=ProgressPhase.THINKING,
                percent=self._percent,
                message="思考中...",
                thinking=thinking,
                step=self._step,
                total_steps=7,
                elapsed=time.time() - self._start_time if self._start_time else 0
            ))
    
    def emit_stream(self, delta: str, is_thinking: bool = False):
        """发射流式输出"""
        if is_thinking:
            self.emit_thinking(delta)
        else:
            # 更新 LLM 生成进度
            self._percent = 90  # 模型生成进度
        
        if self.callback:
            self.callback(AgentProgress(
                phase=ProgressPhase.LLM_GENERATING if not is_thinking else ProgressPhase.THINKING,
                percent=self._percent,
                message="生成回复..." if not is_thinking else "思考中...",
                thinking=self._thinking_buffer if is_thinking else "",
                detail=delta[-50:] if delta else "",  # 最后50字
                step=self._step,
                total_steps=7,
                elapsed=time.time() - self._start_time if self._start_time else 0
            ))
    
    def complete(self, message: str = "处理完成"):
        """完成"""
        self._percent = 100
        if self.callback:
            self.callback(AgentProgress(
                phase=ProgressPhase.COMPLETED,
                percent=100,
                message=message,
                thinking=self._thinking_buffer,
                step=7,
                total_steps=7,
                elapsed=time.time() - self._start_time if self._start_time else 0
            ))
    
    @property
    def progress(self) -> AgentProgress:
        """获取当前进度"""
        return AgentProgress(
            phase=self._phase,
            percent=self._percent,
            message="",
            thinking=self._thinking_buffer,
            step=self._step,
            total_steps=7,
            elapsed=time.time() - self._start_time if self._start_time else 0
        )


class ProgressIterator(ABCIterator):
    """
    带进度反馈的迭代器封装
    
    用于包装 HermeAgent.send_message() 的返回迭代器
    自动提取 thinking 内容和流式输出
    """
    
    def __init__(
        self,
        iterator: Iterator,
        progress_callback: Callable[[AgentProgress], None],
        start_message: str = "开始生成..."
    ):
        self._iterator = iterator
        self._emitter = ProgressEmitter(progress_callback)
        self._emitter.start()
        self._done = False
        self._thinking_mode = False
        self._thinking_buffer = ""
        self._response_buffer = ""
        
        # 发射初始进度
        self._emitter.emit_phase(
            ProgressPhase.LLM_GENERATING,
            start_message
        )
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._done:
            raise StopIteration
        
        try:
            chunk = next(self._iterator)
            
            if hasattr(chunk, 'done') and chunk.done:
                self._done = True
                self._emitter.complete()
                return chunk
            
            # 处理流式内容
            if hasattr(chunk, 'delta') and chunk.delta:
                delta = chunk.delta
                
                # 检测 thinking 模式
                if '<|think|>' in delta or '<think>' in delta:
                    self._thinking_mode = True
                if '</think>' in delta or '</think>' in delta:
                    self._thinking_mode = False
                
                # 发射对应类型的进度
                if self._thinking_mode:
                    self._emitter.emit_stream(delta, is_thinking=True)
                else:
                    self._response_buffer += delta
                    self._emitter.emit_stream(delta, is_thinking=False)
            
            return chunk
            
        except StopIteration:
            self._done = True
            self._emitter.complete()
            raise


def wrap_with_progress(
    iterator: Iterator,
    progress_callback: Callable[[AgentProgress], None],
    start_message: str = "开始生成..."
) -> ProgressIterator:
    """包装迭代器，添加进度反馈"""
    return ProgressIterator(iterator, progress_callback, start_message)
