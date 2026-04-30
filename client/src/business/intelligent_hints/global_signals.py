"""
智能提示系统 — 全局信号总线
============================
跨模块通信中枢，子页面发信号，主窗口捕获处理

信号流程：
子页面 → GlobalHintSignal.emit() → MainWindow捕获 → 匹配模板 → 润色 → 闪烁提示
"""

import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import queue


class HintSignalType(Enum):
    """信号类型"""
    # 场景信号
    SCENE_ENTER = "scene_enter"          # 进入场景
    SCENE_EXIT = "scene_exit"           # 离开场景
    SCENE_UPDATE = "scene_update"        # 场景更新

    # 提示信号
    HINT_NEEDED = "hint_needed"         # 需要提示
    HINT_TRIGGER = "hint_trigger"        # 触发提示
    HINT_DISMISS = "hint_dismiss"        # 忽略提示
    HINT_CHAT = "hint_chat"             # 聊天模式

    # 控制信号
    HIDE_THIS_SCENE = "hide_this_scene"  # 隐藏此场景
    SHOW_CHAT_WINDOW = "show_chat_window" # 显示聊天窗口
    REFRESH_HINTS = "refresh_hints"      # 刷新提示


@dataclass
class HintSignal:
    """提示信号"""
    signal_type: HintSignalType
    scene_id: str
    priority: int = 0

    # 载荷
    payload: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    source: str = ""                     # 来源模块
    timestamp: datetime = field(default_factory=datetime.now)

    # 交互信息
    interaction: str = ""                # 交互类型: temp_hide/perma_hide/chat
    user_id: str = ""                    # 用户标识


class GlobalHintSignalBus:
    """
    全局提示信号总线

    特性：
    - 线程安全
    - 支持同步/异步订阅
    - 信号缓冲队列
    - 优先级处理
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # 订阅者: signal_type -> [callbacks]
        self._subscribers: Dict[HintSignalType, List[Callable]] = {}

        # 全局订阅者（接收所有信号）
        self._global_subscribers: List[Callable] = []

        # 信号缓冲队列
        self._signal_queue: queue.Queue = queue.Queue(maxsize=100)

        # 处理线程
        self._process_thread: threading.Thread = None
        self._running = False

        # 统计
        self._stats: Dict[str, int] = {}

    @classmethod
    def get_instance(cls) -> "GlobalHintSignalBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def subscribe(
        self,
        signal_type: HintSignalType,
        callback: Callable[[HintSignal], None]
    ) -> None:
        """订阅特定信号"""
        with self._lock:
            if signal_type not in self._subscribers:
                self._subscribers[signal_type] = []
            if callback not in self._subscribers[signal_type]:
                self._subscribers[signal_type].append(callback)

    def unsubscribe(
        self,
        signal_type: HintSignalType,
        callback: Callable[[HintSignal], None]
    ) -> None:
        """取消订阅"""
        with self._lock:
            if signal_type in self._subscribers:
                if callback in self._subscribers[signal_type]:
                    self._subscribers[signal_type].remove(callback)

    def subscribe_global(
        self,
        callback: Callable[[HintSignal], None]
    ) -> None:
        """全局订阅（接收所有信号）"""
        with self._lock:
            if callback not in self._global_subscribers:
                self._global_subscribers.append(callback)

    def unsubscribe_global(
        self,
        callback: Callable[[HintSignal], None]
    ) -> None:
        """取消全局订阅"""
        with self._lock:
            if callback in self._global_subscribers:
                self._global_subscribers.remove(callback)

    def emit(self, signal: HintSignal) -> None:
        """
        发射信号

        用法：
        >>> from client.src.business.intelligent_hints.global_signals import GlobalHintSignalBus, HintSignalType, HintSignal
        >>> bus = GlobalHintSignalBus.get_instance()
        >>> bus.emit(HintSignal(
        ...     signal_type=HintSignalType.HINT_NEEDED,
        ...     scene_id="model_select",
        ...     payload={"options": ["Ollama", "DeepSeek"]}
        ... ))
        """
        # 记录统计
        key = signal.signal_type.value
        self._stats[key] = self._stats.get(key, 0) + 1

        # 加入缓冲队列
        try:
            self._signal_queue.put_nowait(signal)
        except queue.Full:
            # 队列满，丢弃最老信号
            try:
                self._signal_queue.get_nowait()
                self._signal_queue.put_nowait(signal)
            except:
                pass

    def emit_simple(
        self,
        signal_type: HintSignalType,
        scene_id: str,
        payload: Dict[str, Any] = None,
        source: str = ""
    ) -> None:
        """便捷发射接口"""
        self.emit(HintSignal(
            signal_type=signal_type,
            scene_id=scene_id,
            payload=payload or {},
            source=source
        ))

    def start_processing(self) -> None:
        """启动信号处理"""
        if self._running:
            return
        self._running = True
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def stop_processing(self) -> None:
        """停止信号处理"""
        self._running = False
        if self._process_thread:
            self._process_thread.join(timeout=1)

    def _process_loop(self) -> None:
        """信号处理循环"""
        while self._running:
            try:
                signal = self._signal_queue.get(timeout=0.1)
                self._dispatch_signal(signal)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Signal processing error: {e}")

    def _dispatch_signal(self, signal: HintSignal) -> None:
        """分发信号到订阅者"""
        # 全局订阅者
        with self._lock:
            global_cbs = self._global_subscribers.copy()

        for callback in global_cbs:
            try:
                callback(signal)
            except Exception as e:
                print(f"Global subscriber error: {e}")

        # 特定类型订阅者
        with self._lock:
            type_subs = self._subscribers.get(signal.signal_type, []).copy()

        for callback in type_subs:
            try:
                callback(signal)
            except Exception as e:
                print(f"Subscriber error for {signal.signal_type}: {e}")

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()

    def clear_stats(self) -> None:
        """清除统计"""
        self._stats.clear()


# 全局便捷函数
_bus: Optional[GlobalHintSignalBus] = None


def get_signal_bus() -> GlobalHintSignalBus:
    """获取信号总线"""
    global _bus
    if _bus is None:
        _bus = GlobalHintSignalBus.get_instance()
    return _bus


def emit_hint_signal(
    signal_type: HintSignalType,
    scene_id: str,
    payload: Dict[str, Any] = None,
    source: str = ""
) -> None:
    """便捷发射信号"""
    get_signal_bus().emit_simple(signal_type, scene_id, payload, source)
