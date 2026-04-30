"""
路由管理器 - 统一管理模块切换

解决原有问题：
- 200个panel平铺无组织
- main_window只注册6个模块，其余194个无入口
- 导航逻辑混乱

新方案：
- 所有模块在路由表中注册
- 支持懒加载（需要时才创建）
- 支持模块分类（左侧导航 + 顶部标签）
"""

from typing import Dict, Type, Optional, Callable, Any
from PyQt6.QtWidgets import QWidget

from ..theme.theme_manager import theme_manager


class Route:
    """路由定义"""

    def __init__(
        self,
        route_id: str,
        name: str,
        emoji: str,
        panel_class: Type[QWidget],
        category: str = "main",  # main | tool | setting
        lazy: bool = True,
    ):
        self.route_id = route_id
        self.name = name
        self.emoji = emoji
        self.panel_class = panel_class
        self.category = category
        self.lazy = lazy  # 是否懒加载
        self._instance: Optional[QWidget] = None

    def get_instance(self, parent: Optional[QWidget] = None) -> QWidget:
        """获取面板实例（懒加载）"""
        if self._instance is None:
            self._instance = self.panel_class(parent)
        return self._instance

    def reset(self):
        """重置实例（释放内存）"""
        self._instance = None


class Router:
    """
    路由管理器（单例）

    使用方式：
        router = get_router()
        router.register(Route("chat", "聊天", "💬", ChatPanel))
        router.navigate_to("chat")
    """

    _instance = None
    _initialized = False
    _route_changed_listeners = []
    _route_registered_listeners = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._routes: Dict[str, Route] = {}
        self._current_route: Optional[str] = None
        self._parent: Optional[QWidget] = None

    def set_parent(self, parent: QWidget):
        """设置父窗口（用于创建面板实例）"""
        self._parent = parent

    def register_route_changed_listener(self, listener):
        """注册路由变更监听器"""
        self._route_changed_listeners.append(listener)

    def register_route_registered_listener(self, listener):
        """注册路由注册监听器"""
        self._route_registered_listeners.append(listener)

    def _emit_route_changed(self, route_id):
        """触发路由变更事件"""
        for listener in self._route_changed_listeners:
            try:
                listener(route_id)
            except:
                pass

    def _emit_route_registered(self, route):
        """触发路由注册事件"""
        for listener in self._route_registered_listeners:
            try:
                listener(route)
            except:
                pass

    def register(self, route: Route):
        """注册路由"""
        self._routes[route.route_id] = route
        self._emit_route_registered(route)

    def register_many(self, routes: list[Route]):
        """批量注册路由"""
        for route in routes:
            self.register(route)

    def navigate_to(self, route_id: str) -> Optional[QWidget]:
        """
        导航到指定路由
        Returns: 目标面板实例
        """
        if route_id not in self._routes:
            print(f"[Router] Route not found: {route_id}")
            return None

        self._current_route = route_id
        route = self._routes[route_id]
        instance = route.get_instance(self._parent)
        self._emit_route_changed(route_id)
        return instance

    def get_route(self, route_id: str) -> Optional[Route]:
        """获取路由定义"""
        return self._routes.get(route_id)

    def get_routes_by_category(self, category: str) -> list[Route]:
        """按分类获取路由"""
        return [r for r in self._routes.values() if r.category == category]

    def get_all_routes(self) -> list[Route]:
        """获取所有路由"""
        return list(self._routes.values())

    @property
    def current_route(self) -> Optional[str]:
        return self._current_route


def get_router() -> Router:
    """获取路由管理器单例"""
    print("    get_router: Creating Router instance...")
    result = Router()
    print("    get_router: Router instance created")
    return result
