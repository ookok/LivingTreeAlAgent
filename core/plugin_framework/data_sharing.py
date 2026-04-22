"""
数据共享机制 - Data Sharing

提供三种数据共享方式：
1. 剪贴板增强：支持复杂对象
2. 拖拽传递：插件间直接拖拽
3. 共享工作区：全局变量存储
"""

import json
import copy
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum


class DataFormat(Enum):
    """数据格式"""
    TEXT = "text"
    HTML = "html"
    IMAGE = "image"
    FILE = "file"
    JSON = "json"
    CUSTOM = "custom"


@dataclass
class SharedData:
    """共享数据"""
    key: str
    value: Any
    format: DataFormat = DataFormat.JSON
    source_plugin: str = ""
    timestamp: float = 0
    mime_type: str = "application/json"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ClipboardEnhancer:
    """
    剪贴板增强

    支持复杂对象的复制粘贴
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._history: List[SharedData] = []
        self._max_history = 50

    def register_format(self, format: DataFormat, handler: Callable[[Any], bytes]) -> None:
        """注册格式处理器"""
        self._handlers[format.value] = handler

    def copy(self, data: Any, format: DataFormat = DataFormat.JSON, metadata: Dict = None) -> bool:
        """
        复制数据到剪贴板

        Args:
            data: 数据
            format: 格式
            metadata: 元数据

        Returns:
            是否成功
        """
        try:
            shared = SharedData(
                key="clipboard",
                value=data,
                format=format,
                timestamp=time.time(),
                metadata=metadata or {},
            )

            # 保存到历史
            self._history.append(shared)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            return True
        except Exception:
            return False

    def paste(self, format: DataFormat = None) -> Optional[Any]:
        """
        从剪贴板粘贴

        Args:
            format: 期望的格式

        Returns:
            数据
        """
        if not self._history:
            return None

        shared = self._history[-1]
        if format is None or shared.format == format:
            return shared.value
        return None

    def get_history(self, limit: int = 10) -> List[SharedData]:
        """获取剪贴板历史"""
        return self._history[-limit:]


class DragDropManager:
    """
    拖拽传递管理器

    管理插件间的拖拽操作
    """

    def __init__(self):
        self._drop_targets: Dict[str, Set[str]] = {}  # plugin_id -> accepted_types
        self._drag_callbacks: Dict[str, Callable] = {}

    def register_drop_target(
        self,
        plugin_id: str,
        accepted_types: List[str],
        callback: Callable[[Any, str], bool]
    ) -> None:
        """
        注册拖拽目标

        Args:
            plugin_id: 目标插件ID
            accepted_types: 接受的数据类型
            callback: 接收回调(data, source_plugin) -> bool
        """
        self._drop_targets[plugin_id] = set(accepted_types)
        self._drag_callbacks[plugin_id] = callback

    def unregister_drop_target(self, plugin_id: str) -> None:
        """注销拖拽目标"""
        self._drop_targets.pop(plugin_id, None)
        self._drag_callbacks.pop(plugin_id, None)

    def can_drop(self, target_plugin: str, data_type: str) -> bool:
        """检查是否可以拖拽"""
        if target_plugin not in self._drop_targets:
            return False
        return data_type in self._drop_targets[target_plugin]

    def drop(self, target_plugin: str, data: Any, data_type: str, source_plugin: str) -> bool:
        """
        执行拖拽放置

        Args:
            target_plugin: 目标插件ID
            data: 数据
            data_type: 数据类型
            source_plugin: 源插件ID

        Returns:
            是否成功
        """
        if not self.can_drop(target_plugin, data_type):
            return False

        callback = self._drag_callbacks.get(target_plugin)
        if callback:
            return callback(data, source_plugin)
        return False

    def get_drop_targets(self, data_type: str) -> List[str]:
        """获取可接收指定数据类型的目标"""
        return [
            plugin_id
            for plugin_id, types in self._drop_targets.items()
            if data_type in types
        ]


class SharedWorkspace:
    """
    共享工作区

    提供全局变量存储
    """

    def __init__(self):
        self._data: Dict[str, SharedData] = {}
        self._subscribers: Dict[str, Dict[str, Callable]] = {}  # key -> {plugin_id -> callback}

    def set(self, key: str, value: Any, format: DataFormat = DataFormat.JSON,
            source_plugin: str = "", metadata: Dict = None) -> None:
        """
        设置共享数据

        Args:
            key: 数据键
            value: 数据值
            format: 数据格式
            source_plugin: 来源插件
            metadata: 元数据
        """
        shared = SharedData(
            key=key,
            value=value,
            format=format,
            source_plugin=source_plugin,
            metadata=metadata or {},
        )
        self._data[key] = shared

        # 通知订阅者
        self._notify_subscribers(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """获取共享数据"""
        shared = self._data.get(key)
        return shared.value if shared else default

    def get_with_metadata(self, key: str) -> Optional[SharedData]:
        """获取共享数据（含元数据）"""
        return self._data.get(key)

    def remove(self, key: str) -> bool:
        """移除共享数据"""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def keys(self) -> List[str]:
        """获取所有键"""
        return list(self._data.keys())

    def subscribe(self, key: str, plugin_id: str, callback: Callable[[Any], None]) -> None:
        """
        订阅数据变更

        Args:
            key: 数据键
            plugin_id: 订阅者插件ID
            callback: 回调函数
        """
        if key not in self._subscribers:
            self._subscribers[key] = {}
        self._subscribers[key][plugin_id] = callback

    def unsubscribe(self, key: str, plugin_id: str) -> None:
        """取消订阅"""
        if key in self._subscribers and plugin_id in self._subscribers[key]:
            del self._subscribers[key][plugin_id]

    def _notify_subscribers(self, key: str, value: Any) -> None:
        """通知订阅者"""
        if key in self._subscribers:
            for plugin_id, callback in self._subscribers[key].items():
                try:
                    callback(value)
                except Exception:
                    pass

    def clear(self) -> None:
        """清空所有数据"""
        self._data.clear()
        self._subscribers.clear()


# 全局实例
_clipboard = ClipboardEnhancer()
_drag_drop = DragDropManager()
_workspace = SharedWorkspace()


def get_clipboard() -> ClipboardEnhancer:
    """获取剪贴板增强器"""
    return _clipboard


def get_drag_drop() -> DragDropManager:
    """获取拖拽管理器"""
    return _drag_drop


def get_workspace() -> SharedWorkspace:
    """获取共享工作区"""
    return _workspace
