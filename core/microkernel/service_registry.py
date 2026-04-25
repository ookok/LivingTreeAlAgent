"""
Service Registry - 服务注册表

插件可以注册服务（接口 + 实现），其他插件可以发现和调用服务。
支持服务版本管理、作用域、依赖注入。

设计理念：
1. 面向接口：服务通过接口名标识，而不是具体实现类
2. 版本管理：支持多版本服务共存
3. 作用域：SINGLETON / PROTOTYPE / SCOPED
4. 依赖注入：服务可以依赖其他服务
"""

import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Set
import logging

logger = logging.getLogger(__name__)


class ServiceScope(Enum):
    """服务作用域"""
    SINGLETON = "singleton"   # 全局单例
    PROTOTYPE = "prototype" # 每次获取都创建新实例
    SCOPED = "scoped"       # 作用域内单例（如：每个会话一个实例）


@dataclass
class ServiceDescriptor:
    """
    服务描述符

    Attributes:
        id: 服务唯一ID（格式：interface:version）
        interface: 接口名（如："IntentEngine", "TaskExecutor"）
        version: 版本号（如："1.0.0"）
        implementation: 实现类或工厂函数
        scope: 作用域
        dependencies: 依赖的服务ID列表
        plugin_id: 提供该插件的ID
        priority: 优先级（数值越大优先级越高）
        metadata: 附加元数据
    """
    id: str
    interface: str
    version: str
    implementation: Any  # 类或工厂函数
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[str] = field(default_factory=list)
    plugin_id: str = ""
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            # 自动生成 ID
            self.id = f"{self.interface}:{self.version}"

    @property
    def is_singleton(self) -> bool:
        return self.scope == ServiceScope.SINGLETON

    @property
    def is_prototype(self) -> bool:
        return self.scope == ServiceScope.PROTOTYPE

    @property
    def is_scoped(self) -> bool:
        return self.scope == ServiceScope.SCOPED

    def matches(self, interface: str, version: Optional[str] = None) -> bool:
        """检查是否匹配指定的接口和版本"""
        if self.interface != interface:
            return False
        if version and self.version != version:
            return False
        return True


class ServiceReference:
    """服务引用（用于依赖注入）"""

    def __init__(self, descriptor: ServiceDescriptor, instance: Any):
        self.descriptor = descriptor
        self.instance = instance
        self.created_at = time.time()
        self.access_count = 0

    def get(self) -> Any:
        """获取服务实例"""
        self.access_count += 1
        if self.descriptor.is_prototype:
            # PROTOTYPE：每次创建新实例
            return self._create_new_instance()
        return self.instance

    def _create_new_instance(self) -> Any:
        """创建新实例"""
        impl = self.descriptor.implementation
        if callable(impl):
            return impl()
        return impl

    def __repr__(self) -> str:
        return f"ServiceReference({self.descriptor.id}, access={self.access_count})"


class ServiceRegistry:
    """
    服务注册表

    管理所有服务的注册、发现、依赖解析。

    使用示例：
        registry = ServiceRegistry()

        # 注册服务
        descriptor = ServiceDescriptor(
            interface="IEventListener",
            version="1.0.0",
            implementation=MyListener,
            plugin_id="my_plugin",
        )
        registry.register(descriptor)

        # 发现服务
        listener_class = registry.get_service("IEventListener:1.0.0")

        # 按接口查询（返回最高优先级的实现）
        listener_class = registry.get_service_by_interface("IEventListener")

        # 列出所有服务
        services = registry.list_services("IEventListener")
    """

    def __init__(self):
        self._services: Dict[str, ServiceDescriptor] = {}       # id -> descriptor
        self._interfaces: Dict[str, List[str]] = defaultdict(list)  # interface -> [id, ...]
        self._references: Dict[str, ServiceReference] = {}       # id -> reference（SINGLETON 缓存）
        self._lock = threading.RLock()
        self._logger = logging.getLogger("ServiceRegistry")

    def register(self, descriptor: ServiceDescriptor) -> bool:
        """
        注册服务

        Args:
            descriptor: 服务描述符

        Returns:
            是否成功注册
        """
        with self._lock:
            service_id = descriptor.id

            if service_id in self._services:
                self._logger.warning(f"Service already registered: {service_id}")
                return False

            # 检查依赖是否满足
            for dep_id in descriptor.dependencies:
                if dep_id not in self._services:
                    self._logger.warning(f"Missing dependency: {dep_id} for service {service_id}")
                    return False

            # 注册
            self._services[service_id] = descriptor
            if descriptor.interface not in self._interfaces:
                self._interfaces[descriptor.interface] = []
            self._interfaces[descriptor.interface].append(service_id)

            self._logger.info(f"Registered service: {service_id} (plugin: {descriptor.plugin_id})")
            return True

    def unregister(self, service_id: str) -> bool:
        """
        注销服务

        Args:
            service_id: 服务ID

        Returns:
            是否成功注销
        """
        with self._lock:
            if service_id not in self._services:
                return False

            descriptor = self._services[service_id]

            # 检查是否有其他服务依赖此服务
            dependents = self._find_dependents(service_id)
            if dependents:
                self._logger.warning(f"Cannot unregister {service_id}: still depended by {dependents}")
                return False

            # 注销
            del self._services[service_id]
            if service_id in self._references:
                del self._references[service_id]

            # 从接口索引中移除
            if descriptor.interface in self._interfaces:
                self._interfaces[descriptor.interface] = [
                    sid for sid in self._interfaces[descriptor.interface]
                    if sid != service_id
                ]
                if not self._interfaces[descriptor.interface]:
                    del self._interfaces[descriptor.interface]

            self._logger.info(f"Unregistered service: {service_id}")
            return True

    def get_service(self, service_id: str) -> Optional[Any]:
        """
        获取服务实例

        Args:
            service_id: 服务ID（格式：interface:version）

        Returns:
            服务实例，不存在则返回 None
        """
        with self._lock:
            if service_id not in self._services:
                return None

            descriptor = self._services[service_id]

            # SINGLETON：从缓存获取或创建
            if descriptor.is_singleton:
                if service_id in self._references:
                    return self._references[service_id].get()
                instance = self._create_instance(descriptor)
                if instance is not None:
                    self._references[service_id] = ServiceReference(descriptor, instance)
                    return instance
                return None

            # PROTOTYPE：每次创建新实例
            elif descriptor.is_prototype:
                return self._create_instance(descriptor)

            # SCOPED：暂定为每次创建新实例（完整实现需要 ScopeContext）
            else:
                return self._create_instance(descriptor)

    def get_service_by_interface(self, interface: str, version: Optional[str] = None) -> Optional[Any]:
        """
        按接口获取服务实例（返回最高优先级的实现）

        Args:
            interface: 接口名
            version: 版本号（可选，不指定则返回最新版本）

        Returns:
            服务实例，不存在则返回 None
        """
        with self._lock:
            if interface not in self._interfaces:
                return None

            service_ids = self._interfaces[interface]

            # 按优先级排序（数值越大优先级越高）
            sorted_ids = sorted(
                service_ids,
                key=lambda sid: self._services[sid].priority,
                reverse=True,
            )

            # 如果指定了版本，只返回匹配版本的服务
            if version:
                for sid in sorted_ids:
                    if self._services[sid].version == version:
                        return self.get_service(sid)
                return None

            # 否则返回最高优先级的版本
            if sorted_ids:
                return self.get_service(sorted_ids[0])

            return None

    def list_services(self, interface: Optional[str] = None) -> List[ServiceDescriptor]:
        """
        列出所有服务

        Args:
            interface: 按接口过滤（可选）

        Returns:
            服务描述符列表
        """
        with self._lock:
            if interface:
                if interface not in self._interfaces:
                    return []
                return [self._services[sid] for sid in self._interfaces[interface]]
            return list(self._services.values())

    def has_service(self, service_id: str) -> bool:
        """检查服务是否存在"""
        with self._lock:
            return service_id in self._services

    def has_interface(self, interface: str) -> bool:
        """检查接口是否有实现"""
        with self._lock:
            return interface in self._interfaces and len(self._interfaces[interface]) > 0

    def get_service_count(self) -> int:
        """获取已注册服务数量"""
        with self._lock:
            return len(self._services)

    def get_interface_count(self) -> int:
        """获取已注册接口数量"""
        with self._lock:
            return len(self._interfaces)

    def clear(self) -> None:
        """清空所有服务（关闭内核时调用）"""
        with self._lock:
            self._services.clear()
            self._interfaces.clear()
            self._references.clear()
            self._logger.info("Service registry cleared")

    def _create_instance(self, descriptor: ServiceDescriptor) -> Optional[Any]:
        """创建服务实例"""
        try:
            impl = descriptor.implementation
            if callable(impl):
                # 如果是类，实例化；如果是工厂函数，调用
                if isinstance(impl, type):
                    return impl()
                else:
                    return impl()
            return impl
        except Exception as e:
            self._logger.error(f"Failed to create instance for {descriptor.id}: {e}")
            self._logger.error(traceback.format_exc())
            return None

    def _find_dependents(self, service_id: str) -> List[str]:
        """查找依赖指定服务的其他服务"""
        dependents = []
        for sid, desc in self._services.items():
            if service_id in desc.dependencies:
                dependents.append(sid)
        return dependents

    def get_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        with self._lock:
            return {
                "service_count": len(self._services),
                "interface_count": len(self._interfaces),
                "cached_references": len(self._references),
                "interfaces": list(self._interfaces.keys()),
            }


# ──────────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────────

_registry_instance: Optional[ServiceRegistry] = None
_registry_lock = threading.RLock()


def get_service_registry() -> ServiceRegistry:
    """获取服务注册表单例"""
    global _registry_instance
    with _registry_lock:
        if _registry_instance is None:
            _registry_instance = ServiceRegistry()
        return _registry_instance


def reset_service_registry() -> None:
    """重置服务注册表（测试用）"""
    global _registry_instance
    with _registry_lock:
        if _registry_instance:
            _registry_instance.clear()
        _registry_instance = None
