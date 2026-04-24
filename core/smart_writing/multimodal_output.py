# -*- coding: utf-8 -*-
"""
多模态交互管理器 - Multimodal Output Manager
============================================

统一管理文本流、进度可视化、错误恢复的多模态输出系统

功能：
1. 统一输出接口（文本/进度/错误/完成）
2. 事件驱动的输出流
3. 输出模式切换（安静/正常/详细）
4. 输出缓冲与批处理
5. 多输出目标支持

Author: Hermes Desktop Team
"""

import time
import threading
import asyncio
from typing import Optional, Callable, Dict, Any, List, Union, Protocol, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from collections import defaultdict
import logging

if TYPE_CHECKING:
    from .streaming_output import StreamConfig, TextStreamer
    from .progress_visualizer import ProgressStage, ProgressTracker
    from .error_recovery import RecoveryContext, RecoverableError

logger = logging.getLogger(__name__)


# =============================================================================
# 输出模式
# =============================================================================

class OutputMode(Enum):
    """输出模式"""
    QUIET = "quiet"      # 静默模式（仅最终结果）
    NORMAL = "normal"    # 正常模式（进度+结果）
    VERBOSE = "verbose"  # 详细模式（所有中间步骤）
    STREAM = "stream"    # 流式模式（打字机效果）


# =============================================================================
# 输出事件
# =============================================================================

class OutputEventType(Enum):
    """输出事件类型"""
    TEXT = "text"
    PROGRESS_START = "progress_start"
    PROGRESS_UPDATE = "progress_update"
    PROGRESS_COMPLETE = "progress_complete"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    COMPLETE = "complete"
    CANCEL = "cancel"


@dataclass
class OutputEvent:
    """输出事件"""
    event_type: OutputEventType
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def __repr__(self) -> str:
        return f"OutputEvent({self.event_type.value}, content={self.content!r:.50})"


# =============================================================================
# 输出处理器接口
# =============================================================================

class OutputHandler(Protocol):
    """输出处理器协议"""
    
    def handle(self, event: OutputEvent) -> None:
        """处理输出事件"""
        ...
    
    def flush(self) -> None:
        """刷新输出"""
        ...
    
    def close(self) -> None:
        """关闭处理器"""
        ...


# =============================================================================
# PyQt 输出处理器
# =============================================================================

class PyQtOutputHandler:
    """PyQt 输出处理器"""
    
    def __init__(
        self,
        text_update_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        self._text_callback = text_update_callback
        self._progress_callback = progress_callback
        self._error_callback = error_callback
        self._buffer = []
        self._buffer_lock = threading.Lock()
    
    def handle(self, event: OutputEvent) -> None:
        """处理输出事件"""
        if event.event_type == OutputEventType.TEXT:
            self._handle_text(event)
        elif event.event_type in (
            OutputEventType.PROGRESS_START,
            OutputEventType.PROGRESS_UPDATE,
            OutputEventType.PROGRESS_COMPLETE,
        ):
            self._handle_progress(event)
        elif event.event_type == OutputEventType.ERROR:
            self._handle_error(event)
        elif event.event_type in (
            OutputEventType.WARNING,
            OutputEventType.INFO,
        ):
            self._handle_info(event)
        elif event.event_type == OutputEventType.COMPLETE:
            self._handle_complete(event)
    
    def _handle_text(self, event: OutputEvent) -> None:
        if self._text_callback and event.content:
            with self._buffer_lock:
                self._buffer.append(event.content)
                full_text = "".join(self._buffer)
            self._text_callback(full_text)
    
    def _handle_progress(self, event: OutputEvent) -> None:
        if self._progress_callback:
            meta = event.metadata
            self._progress_callback(
                meta.get("stage", ""),
                meta.get("progress", 0.0),
                meta.get("message", ""),
            )
    
    def _handle_error(self, event: OutputEvent) -> None:
        if self._error_callback and event.content:
            self._error_callback(str(event.content))
    
    def _handle_info(self, event: OutputEvent) -> None:
        if self._text_callback and event.content:
            prefix = "⚠️ " if event.event_type == OutputEventType.WARNING else "ℹ️ "
            self._text_callback(f"{prefix}{event.content}")
    
    def _handle_complete(self, event: OutputEvent) -> None:
        if self._text_callback:
            self._text_callback(f"\n✅ {event.content or '完成'}")
    
    def flush(self) -> None:
        """刷新缓冲区"""
        with self._buffer_lock:
            self._buffer.clear()
    
    def close(self) -> None:
        """关闭"""
        self.flush()
        self._text_callback = None
        self._progress_callback = None
        self._error_callback = None


# =============================================================================
# Console 输出处理器（用于调试）
# =============================================================================

class ConsoleOutputHandler:
    """Console 输出处理器（调试用）"""
    
    def __init__(self, use_color: bool = True):
        self._use_color = use_color
        self._buffer = []
    
    def handle(self, event: OutputEvent) -> None:
        """处理输出事件"""
        if event.event_type == OutputEventType.TEXT:
            print(event.content or "", end="", flush=True)
        elif event.event_type == OutputEventType.PROGRESS_START:
            print(f"\n🔄 {event.metadata.get('message', '开始')}", flush=True)
        elif event.event_type == OutputEventType.PROGRESS_UPDATE:
            bar = self._make_progress_bar(event.metadata.get("progress", 0))
            stage = event.metadata.get("stage", "")
            msg = event.metadata.get("message", "")
            print(f"\r{bar} {stage} {msg}", end="", flush=True)
        elif event.event_type == OutputEventType.PROGRESS_COMPLETE:
            print(f"\n✅ {event.metadata.get('message', '完成')}", flush=True)
        elif event.event_type == OutputEventType.ERROR:
            msg = f"❌ 错误: {event.content}"
            print(f"\n{msg}", flush=True)
        elif event.event_type == OutputEventType.WARNING:
            print(f"\n⚠️ 警告: {event.content}", flush=True)
        elif event.event_type == OutputEventType.COMPLETE:
            print(f"\n{'='*50}\n✅ {event.content or '完成!'}\n", flush=True)
    
    def _make_progress_bar(self, progress: float, width: int = 30) -> str:
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        pct = f"{progress * 100:.1f}%"
        return f"[{bar}] {pct}"
    
    def flush(self) -> None:
        print(flush=True)
    
    def close(self) -> None:
        print(flush=True)


# =============================================================================
# 事件总线
# =============================================================================

class EventBus:
    """事件总线 - 用于组件间通信"""
    
    def __init__(self):
        self._subscribers: Dict[OutputEventType, List[Callable[[OutputEvent], None]]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def subscribe(
        self, event_type: OutputEventType, callback: Callable[[OutputEvent], None]
    ) -> Callable[[], None]:
        """订阅事件"""
        with self._lock:
            self._subscribers[event_type].append(callback)
        
        def unsubscribe():
            with self._lock:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
        
        return unsubscribe
    
    def publish(self, event: OutputEvent) -> None:
        """发布事件"""
        with self._lock:
            subscribers = self._subscribers.get(event.event_type, []).copy()
            global_subscribers = self._subscribers.get("*", []).copy()
        
        for callback in subscribers + global_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调错误: {e}")
    
    def clear(self) -> None:
        """清除所有订阅"""
        with self._lock:
            self._subscribers.clear()


# =============================================================================
# 多模态输出管理器
# =============================================================================

class MultimodalOutputManager:
    """
    多模态输出管理器
    
    统一管理文本流、进度可视化、错误恢复的输出系统
    
    Example:
        manager = MultimodalOutputManager()
        
        # 设置回调
        manager.set_text_callback(lambda text: ui.update_text(text))
        manager.set_progress_callback(lambda stage, pct, msg: ui.update_progress(stage, pct, msg))
        manager.set_error_callback(lambda err: ui.show_error(err))
        
        # 输出文本（带打字机效果）
        await manager.output_stream("你好，这是一个长文本...")
        
        # 显示进度
        manager.output_progress_start("下载文件", 3)
        manager.output_progress_update("下载中", 0.33, "已下载 1/3")
        ...
        
        # 错误处理
        try:
            await some_operation()
        except Exception as e:
            manager.output_error(e)
    """
    
    def __init__(
        self,
        mode: OutputMode = OutputMode.NORMAL,
        buffer_size: int = 100,
    ):
        self._mode = mode
        self._buffer_size = buffer_size
        self._handlers: List[OutputHandler] = []
        self._event_bus = EventBus()
        self._text_buffer: List[str] = []
        self._text_buffer_lock = threading.Lock()
        self._is_active = True
        self._maintain_buffer = True
        
        # 回调
        self._text_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[str, float, str], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        self._complete_callback: Optional[Callable[[str], None]] = None
    
    # -------------------------------------------------------------------------
    # 配置方法
    # -------------------------------------------------------------------------
    
    def set_mode(self, mode: OutputMode) -> None:
        """设置输出模式"""
        self._mode = mode
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """设置文本更新回调"""
        self._text_callback = callback
        # 添加 PyQt 处理器
        handler = PyQtOutputHandler(
            text_update_callback=callback,
            progress_callback=self._progress_callback,
            error_callback=self._error_callback,
        )
        self._handlers.append(handler)
    
    def set_progress_callback(
        self, callback: Callable[[str, float, str], None]
    ) -> None:
        """设置进度更新回调"""
        self._progress_callback = callback
        # 更新已有处理器
        for h in self._handlers:
            if isinstance(h, PyQtOutputHandler):
                h._progress_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """设置错误回调"""
        self._error_callback = callback
    
    def set_complete_callback(self, callback: Callable[[str], None]) -> None:
        """设置完成回调"""
        self._complete_callback = callback
    
    def add_handler(self, handler: OutputHandler) -> None:
        """添加输出处理器"""
        self._handlers.append(handler)
    
    def subscribe(self, event_type: OutputEventType, callback: Callable[[OutputEvent], None]) -> Callable[[], None]:
        """订阅事件"""
        return self._event_bus.subscribe(event_type, callback)
    
    # -------------------------------------------------------------------------
    # 输出方法
    # -------------------------------------------------------------------------
    
    def output_text(self, text: str, stream: bool = False) -> None:
        """
        输出文本
        
        Args:
            text: 文本内容
            stream: 是否使用流式输出
        """
        if not self._is_active:
            return
        
        if stream and self._mode == OutputMode.STREAM:
            # 流式输出：逐字输出
            self._stream_text(text)
        else:
            # 直接输出
            self._emit(OutputEvent(OutputEventType.TEXT, content=text))
    
    def _stream_text(self, text: str, delay: float = 0.02) -> None:
        """流式输出文本"""
        for char in text:
            if not self._is_active:
                break
            self._emit(OutputEvent(OutputEventType.TEXT, content=char))
            time.sleep(delay)
    
    def output_progress_start(self, stage: str, total_steps: int, message: str = "") -> None:
        """输出进度开始"""
        if not self._is_active or self._mode == OutputMode.QUIET:
            return
        
        self._emit(OutputEvent(
            OutputEventType.PROGRESS_START,
            content=message,
            metadata={
                "stage": stage,
                "total_steps": total_steps,
                "progress": 0.0,
            },
        ))
    
    def output_progress_update(
        self, stage: str, progress: float, message: str = ""
    ) -> None:
        """输出进度更新"""
        if not self._is_active or self._mode == OutputMode.QUIET:
            return
        
        self._emit(OutputEvent(
            OutputEventType.PROGRESS_UPDATE,
            content=message,
            metadata={
                "stage": stage,
                "progress": min(1.0, max(0.0, progress)),
                "message": message,
            },
        ))
    
    def output_progress_complete(self, stage: str, message: str = "完成") -> None:
        """输出进度完成"""
        if not self._is_active:
            return
        
        self._emit(OutputEvent(
            OutputEventType.PROGRESS_COMPLETE,
            content=message,
            metadata={
                "stage": stage,
                "progress": 1.0,
                "message": message,
            },
        ))
    
    def output_error(self, error: Union[str, Exception], recoverable: bool = True) -> None:
        """输出错误"""
        if not self._is_active:
            return
        
        error_msg = str(error)
        self._emit(OutputEvent(
            OutputEventType.ERROR,
            content=error_msg,
            metadata={"recoverable": recoverable},
        ))
        
        if self._error_callback:
            self._error_callback(error_msg)
    
    def output_warning(self, message: str) -> None:
        """输出警告"""
        if not self._is_active or self._mode == OutputMode.QUIET:
            return
        
        self._emit(OutputEvent(OutputEventType.WARNING, content=message))
    
    def output_info(self, message: str) -> None:
        """输出信息"""
        if not self._is_active or self._mode == OutputMode.QUIET:
            return
        
        self._emit(OutputEvent(OutputEventType.INFO, content=message))
    
    def output_complete(self, message: str = "任务完成") -> None:
        """输出完成"""
        if not self._is_active:
            return
        
        self._emit(OutputEvent(OutputEventType.COMPLETE, content=message))
        
        if self._complete_callback:
            self._complete_callback(message)
    
    # -------------------------------------------------------------------------
    # 异步输出方法
    # -------------------------------------------------------------------------
    
    async def output_stream_async(
        self, text: str, delay: float = 0.02
    ) -> None:
        """异步流式输出文本"""
        if not self._is_active:
            return
        
        for char in text:
            if not self._is_active:
                break
            
            self._emit(OutputEvent(OutputEventType.TEXT, content=char))
            
            if asyncio.iscoroutinefunction(self._text_callback):
                await self._text_callback(char)
            
            await asyncio.sleep(delay)
    
    # -------------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------------
    
    def _emit(self, event: OutputEvent) -> None:
        """发送事件到所有处理器"""
        for handler in self._handlers:
            try:
                handler.handle(event)
            except Exception as e:
                logger.error(f"输出处理错误: {e}")
        
        # 发送到事件总线
        self._event_bus.publish(event)
        
        # 维护文本缓冲区
        if event.event_type == OutputEventType.TEXT:
            with self._text_buffer_lock:
                self._text_buffer.append(event.content)
                if len(self._text_buffer) > self._buffer_size:
                    self._text_buffer = self._text_buffer[-self._buffer_size:]
    
    def get_text_buffer(self) -> str:
        """获取文本缓冲区"""
        with self._text_buffer_lock:
            return "".join(self._text_buffer)
    
    def clear_text_buffer(self) -> None:
        """清除文本缓冲区"""
        with self._text_buffer_lock:
            self._text_buffer.clear()
        for handler in self._handlers:
            handler.flush()
    
    def pause(self) -> None:
        """暂停输出"""
        self._is_active = False
    
    def resume(self) -> None:
        """恢复输出"""
        self._is_active = True
    
    def close(self) -> None:
        """关闭管理器"""
        self._is_active = False
        for handler in self._handlers:
            try:
                handler.close()
            except Exception as e:
                logger.error(f"关闭处理器错误: {e}")
        self._handlers.clear()
        self._event_bus.clear()
    
    # -------------------------------------------------------------------------
    # 上下文管理器
    # -------------------------------------------------------------------------
    
    def __enter__(self) -> "MultimodalOutputManager":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# =============================================================================
# 进度追踪器集成
# =============================================================================

class ProgressTracker:
    """进度追踪器（简化版，集成到多模态管理器）"""
    
    def __init__(self, manager: MultimodalOutputManager, stage: str, total_steps: int):
        self._manager = manager
        self._stage = stage
        self._total_steps = total_steps
        self._current_step = 0
        self._started = False
    
    def __enter__(self) -> "ProgressTracker":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.complete()
        else:
            self._manager.output_error(exc_val)
            self.complete()
    
    def start(self) -> None:
        """开始追踪"""
        self._manager.output_progress_start(self._stage, self._total_steps)
        self._started = True
    
    def step(self, message: str = "") -> None:
        """下一步"""
        if not self._started:
            self.start()
        self._current_step += 1
        progress = self._current_step / self._total_steps
        self._manager.output_progress_update(self._stage, progress, message)
    
    def update(self, progress: float, message: str = "") -> None:
        """更新进度"""
        self._manager.output_progress_update(self._stage, progress, message)
    
    def complete(self, message: str = "完成") -> None:
        """完成追踪"""
        if self._started:
            self._manager.output_progress_complete(self._stage, message)
            self._started = False


# =============================================================================
# 全局实例
# =============================================================================

_manager: Optional[MultimodalOutputManager] = None


def get_output_manager() -> MultimodalOutputManager:
    """获取全局输出管理器"""
    global _manager
    if _manager is None:
        _manager = MultimodalOutputManager()
    return _manager


def set_output_manager(manager: MultimodalOutputManager) -> None:
    """设置全局输出管理器"""
    global _manager
    _manager = manager


# =============================================================================
# 便捷函数
# =============================================================================

def output_stream(text: str) -> None:
    """快速流式输出"""
    get_output_manager().output_text(text, stream=True)


def output_progress(stage: str, progress: float, message: str = "") -> None:
    """快速进度输出"""
    get_output_manager().output_progress_update(stage, progress, message)


def output_error(error: Union[str, Exception]) -> None:
    """快速错误输出"""
    get_output_manager().output_error(error)


def output_complete(message: str = "完成") -> None:
    """快速完成输出"""
    get_output_manager().output_complete(message)


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=== 测试多模态输出管理器 ===\n")
    
    # 创建管理器
    manager = MultimodalOutputManager(mode=OutputMode.NORMAL)
    
    # 添加 Console 处理器（调试用）
    console_handler = ConsoleOutputHandler()
    manager.add_handler(console_handler)
    
    # 测试文本输出
    print("\n1. 测试文本输出:")
    manager.output_text("你好，这是一段测试文本。\n")
    
    # 测试进度追踪
    print("\n2. 测试进度追踪:")
    with ProgressTracker(manager, "测试阶段", 5) as tracker:
        for i in range(5):
            time.sleep(0.3)
            tracker.step(f"步骤 {i+1}/5")
    
    # 测试错误输出
    print("\n3. 测试错误输出:")
    manager.output_error("这是一个测试错误")
    
    # 测试完成输出
    print("\n4. 测试完成输出:")
    manager.output_complete("所有测试完成!")
    
    manager.close()
    print("\n完成!")
