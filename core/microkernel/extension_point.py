"""
Extension Point Manager - 扩展点管理

插件可以定义扩展点（接口），其他插件可以提供扩展实现。
支持扩展点优先级、排序、条件过滤。

设计理念：
1. 面向接口：扩展点定义接口，扩展提供实现
2. 优先级排序：高优先级扩展先被调用
3. 条件过滤：扩展可以指定条件（如：只在特定模式下生效）
4. 动态注册：运行时可以动态注册/注销扩展
"""

import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class Extension:
    """
    扩展实现

    Attributes:
        id: 扩展唯一ID（格式：point_id:plugin_id:extension_name）
        point_id: 所属扩展点ID
        plugin_id: 提供该扩展的插件ID
        implementation: 扩展实现（类或函数）
        priority: 优先级（数值越大优先级越高）
        condition: 条件函数（可选，返回 bool 决定是否激活）
        metadata: 附加元数据
    """
    id: str
    point_id: str
    plugin_id: str
    implementation: Any
    priority: int = 0
    condition: Optional[Callable[[], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.point_id}:{self.plugin_id}:{self.__class__.__name__}"

    def is_active(self) -> bool:
        """检查扩展是否激活（条件满足）"""
        if self.condition is None:
            return True
        try:
            return self.condition()
        except Exception as e:
            logger.error(f"Extension condition error: {e}")
            return False

    def get_impl(self) -> Any:
        """获取扩展实现"""
        return self.implementation


@dataclass
class ExtensionPoint:
    """
    扩展点定义

    Attributes:
        id: 扩展点唯一ID
        interface: 接口名（用于类型检查）
        description: 描述
        plugin_id: 定义该扩展点的插件ID
        min_extensions: 最小扩展数（0 表示可选）
        max_extensions: 最大扩展数（0 表示无限制）
        allow_multiple: 是否允许多个扩展同时存在
    """
    id: str
    interface: str
    description: str = ""
    plugin_id: str = ""
    min_extensions: int = 0
    max_extensions: int = 0  # 0 = 无限制
    allow_multiple: bool = True

    def validate_extension(self, extension: Extension) -> bool:
        """验证扩展是否符合扩展点要求"""
        # 检查扩展点 ID 是否匹配
        if extension.point_id != self.id:
            return False

        # 检查最大扩展数
        if self.max_extensions > 0:
            # 注意：这里不检查当前扩展数，由 Manager 负责
            pass

        return True


class ExtensionPointManager:
    """
    扩展点管理器

    管理扩展点的注册、扩展的注册、扩展的查询。

    使用示例：
        manager = ExtensionPointManager()

        # 定义扩展点
        point = ExtensionPoint(
            id="code_generator",
            interface="ICodeGenerator",
            description="代码生成扩展点",
            plugin_id="core",
        )
        manager.register_extension_point(point)

        # 注册扩展
        extension = Extension(
            point_id="code_generator",
            plugin_id="python_plugin",
            implementation=PythonCodeGenerator(),
            priority=10,
        )
        manager.register_extension("code_generator", extension)

        # 获取扩展（按优先级排序）
        extensions = manager.get_extensions("code_generator")
        for ext in extensions:
            generator = ext.get_impl()
            result = generator.generate(code)
    """

    def __init__(self):
        self._points: Dict[str, ExtensionPoint] = {}
        self._extensions: Dict[str, List[Extension]] = {}  # point_id -> [extensions]
        self._lock = threading.RLock()
        self._logger = logging.getLogger("ExtensionPointManager")

    def register_extension_point(self, point: ExtensionPoint) -> bool:
        """
        注册扩展点

        Args:
            point: 扩展点定义

        Returns:
            是否成功注册
        """
        with self._lock:
            if point.id in self._points:
                self._logger.warning(f"Extension point already registered: {point.id}")
                return False

            self._points[point.id] = point
            if point.id not in self._extensions:
                self._extensions[point.id] = []

            self._logger.info(f"Registered extension point: {point.id} (interface: {point.interface})")
            return True

    def unregister_extension_point(self, point_id: str) -> bool:
        """
        注销扩展点

        Args:
            point_id: 扩展点ID

        Returns:
            是否成功注销
        """
        with self._lock:
            if point_id not in self._points:
                return False

            # 检查是否有扩展依赖此扩展点
            if point_id in self._extensions and len(self._extensions[point_id]) > 0:
                self._logger.warning(
                    f"Cannot unregister extension point {point_id}: still has {len(self._extensions[point_id])} extensions"
                )
                return False

            del self._points[point_id]
            if point_id in self._extensions:
                del self._extensions[point_id]

            self._logger.info(f"Unregistered extension point: {point_id}")
            return True

    def register_extension(self, point_id: str, extension: Extension) -> bool:
        """
        注册扩展

        Args:
            point_id: 扩展点ID
            extension: 扩展实现

        Returns:
            是否成功注册
        """
        with self._lock:
            if point_id not in self._points:
                self._logger.warning(f"Extension point not found: {point_id}")
                return False

            point = self._points[point_id]

            # 验证扩展
            if not point.validate_extension(extension):
                self._logger.warning(f"Extension validation failed: {extension.id}")
                return False

            # 检查最大扩展数
            if point.max_extensions > 0 and len(self._extensions[point_id]) >= point.max_extensions:
                self._logger.warning(f"Extension point {point_id} reached max extensions: {point.max_extensions}")
                return False

            # 检查重复
            for existing in self._extensions[point_id]:
                if existing.id == extension.id:
                    self._logger.warning(f"Extension already registered: {extension.id}")
                    return False

            # 注册
            self._extensions[point_id].append(extension)

            # 按优先级排序（数值越大优先级越高）
            self._extensions[point_id].sort(key=lambda ext: ext.priority, reverse=True)

            self._logger.info(f"Registered extension: {extension.id} to point {point_id}")
            return True

    def unregister_extension(self, point_id: str, extension_id: str) -> bool:
        """
        注销扩展

        Args:
            point_id: 扩展点ID
            extension_id: 扩展ID

        Returns:
            是否成功注销
        """
        with self._lock:
            if point_id not in self._extensions:
                return False

            before = len(self._extensions[point_id])
            self._extensions[point_id] = [
                ext for ext in self._extensions[point_id]
                if ext.id != extension_id
            ]
            after = len(self._extensions[point_id])

            if before == after:
                return False

            self._logger.info(f"Unregistered extension: {extension_id} from point {point_id}")
            return True

    def get_extensions(self, point_id: str, active_only: bool = True) -> List[Extension]:
        """
        获取扩展点的所有扩展（按优先级排序）

        Args:
            point_id: 扩展点ID
            active_only: 是否只返回激活的扩展

        Returns:
            扩展列表
        """
        with self._lock:
            if point_id not in self._extensions:
                return []

            extensions = self._extensions[point_id]

            if active_only:
                extensions = [ext for ext in extensions if ext.is_active()]

            return extensions

    def get_first_extension(self, point_id: str, active_only: bool = True) -> Optional[Extension]:
        """
        获取扩展点的第一个（最高优先级）扩展

        Args:
            point_id: 扩展点ID
            active_only: 是否只返回激活的扩展

        Returns:
            扩展，不存在则返回 None
        """
        extensions = self.get_extensions(point_id, active_only)
        return extensions[0] if extensions else None

    def get_extension_point(self, point_id: str) -> Optional[ExtensionPoint]:
        """获取扩展点定义"""
        with self._lock:
            return self._points.get(point_id)

    def list_extension_points(self) -> List[ExtensionPoint]:
        """列出所有扩展点"""
        with self._lock:
            return list(self._points.values())

    def list_extensions(self, point_id: Optional[str] = None) -> List[Extension]:
        """
        列出所有扩展

        Args:
            point_id: 按扩展点过滤（可选）

        Returns:
            扩展列表
        """
        with self._lock:
            if point_id:
                return self._extensions.get(point_id, [])
            else:
                result = []
                for ext_list in self._extensions.values():
                    result.extend(ext_list)
                return result

    def has_extension_point(self, point_id: str) -> bool:
        """检查扩展点是否存在"""
        with self._lock:
            return point_id in self._points

    def has_extension(self, point_id: str, extension_id: str) -> bool:
        """检查扩展是否存在"""
        with self._lock:
            if point_id not in self._extensions:
                return False
            return any(ext.id == extension_id for ext in self._extensions[point_id])

    def get_extension_point_count(self) -> int:
        """获取扩展点数量"""
        with self._lock:
            return len(self._points)

    def get_extension_count(self) -> int:
        """获取扩展总数"""
        with self._lock:
            total = 0
            for ext_list in self._extensions.values():
                total += len(ext_list)
            return total

    def clear(self) -> None:
        """清空所有扩展点和扩展（关闭内核时调用）"""
        with self._lock:
            self._points.clear()
            self._extensions.clear()
            self._logger.info("Extension point manager cleared")

    def validate_all(self) -> Dict[str, List[str]]:
        """
        验证所有扩展点是否满足最小扩展数

        Returns:
            不满足的扩展点ID -> 错误列表
        """
        with self._lock:
            errors: Dict[str, List[str]] = {}
            for point_id, point in self._points.items():
                if point.min_extensions > 0:
                    ext_count = len(self._extensions.get(point_id, []))
                    if ext_count < point.min_extensions:
                        if point_id not in errors:
                            errors[point_id] = []
                        errors[point_id].append(
                            f"Requires at least {point.min_extensions} extensions, but only {ext_count} registered"
                        )
            return errors

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "extension_point_count": len(self._points),
                "extension_count": self.get_extension_count(),
                "extensions_per_point": {
                    point_id: len(ext_list)
                    for point_id, ext_list in self._extensions.items()
                },
            }


# ──────────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────────

_manager_instance: Optional[ExtensionPointManager] = None
_manager_lock = threading.RLock()


def get_extension_point_manager() -> ExtensionPointManager:
    """获取扩展点管理器单例"""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is None:
            _manager_instance = ExtensionPointManager()
        return _manager_instance


def reset_extension_point_manager() -> None:
    """重置扩展点管理器（测试用）"""
    global _manager_instance
    with _manager_lock:
        if _manager_instance:
            _manager_instance.clear()
        _manager_instance = None
