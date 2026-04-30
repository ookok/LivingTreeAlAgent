"""
依赖注入容器 (Dependency Injection Container)

实现服务的注册、解析和生命周期管理，消除模块间循环依赖。
"""

from typing import Dict, Callable, Any, Optional, Type
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ServiceDefinition:
    """服务定义"""
    factory: Callable[[], Any]
    singleton: bool = True
    instance: Optional[Any] = None


class Container:
    """
    依赖注入容器
    
    功能：
    1. 服务注册：将服务工厂注册到容器
    2. 服务解析：根据名称获取服务实例
    3. 单例管理：支持单例和原型模式
    4. 循环依赖检测
    
    使用方式：
    container = Container()
    container.register("governance", create_industry_governance)
    governance = container.resolve("governance")
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceDefinition] = {}
        self._resolving: set = set()  # 正在解析的服务（用于检测循环依赖）
        self._lock = Lock()
    
    def register(self, name: str, factory: Callable[[], Any], singleton: bool = True):
        """
        注册服务
        
        Args:
            name: 服务名称
            factory: 服务工厂函数
            singleton: 是否单例模式
        """
        with self._lock:
            self._services[name] = ServiceDefinition(
                factory=factory,
                singleton=singleton
            )
        print(f"[Container] 已注册服务: {name}")
    
    def resolve(self, name: str) -> Any:
        """
        解析服务
        
        Args:
            name: 服务名称
            
        Returns:
            服务实例
            
        Raises:
            ValueError: 服务未注册
            RuntimeError: 检测到循环依赖
        """
        # 检测循环依赖
        if name in self._resolving:
            raise RuntimeError(f"检测到循环依赖: {' -> '.join(self._resolving)} -> {name}")
        
        with self._lock:
            if name not in self._services:
                raise ValueError(f"服务未注册: {name}")
            
            definition = self._services[name]
            
            # 如果是单例且已创建实例，直接返回
            if definition.singleton and definition.instance is not None:
                return definition.instance
            
            # 标记正在解析
            self._resolving.add(name)
            
            try:
                # 创建实例
                instance = definition.factory()
                
                # 如果是单例，缓存实例
                if definition.singleton:
                    definition.instance = instance
                
                return instance
            finally:
                # 移除解析标记
                self._resolving.discard(name)
    
    def register_multiple(self, services: Dict[str, Callable[[], Any]]):
        """批量注册服务"""
        for name, factory in services.items():
            self.register(name, factory)
    
    def get_registered_services(self) -> list:
        """获取所有已注册的服务名称"""
        return list(self._services.keys())
    
    def clear(self):
        """清空所有服务（用于测试）"""
        with self._lock:
            self._services.clear()
            self._resolving.clear()
    
    def has_service(self, name: str) -> bool:
        """检查服务是否已注册"""
        return name in self._services


# 全局容器实例
_global_container = Container()


def get_container() -> Container:
    """获取全局容器实例"""
    return _global_container


def register_service(name: str, factory: Callable[[], Any], singleton: bool = True):
    """向全局容器注册服务"""
    _global_container.register(name, factory, singleton)


def resolve_service(name: str) -> Any:
    """从全局容器解析服务"""
    return _global_container.resolve(name)


__all__ = [
    "Container",
    "ServiceDefinition",
    "get_container",
    "register_service",
    "resolve_service"
]