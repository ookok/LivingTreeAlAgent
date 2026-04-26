"""
路由表 - 默认路由定义

所有模块在此注册，解决原有200个panel无入口问题。
"""

from typing import Callable, Type
from PyQt6.QtWidgets import QWidget

from .router import Route, Router


def register_default_routes(router: Router, module_map: dict = None):
    """
    注册默认路由

    Args:
        router: Router实例
        module_map: 模块类映射（延迟导入，避免循环依赖）
                   格式: {"chat": ChatPanelClass, ...}
    """

    # 主模块（显示在左侧导航）
    main_routes = [
        Route("chat", "聊天", "💬", _lazy("chat"), category="main"),
        Route("deep_search", "深度搜索", "🔍", _lazy("deep_search"), category="main"),
        Route("knowledge_base", "知识库", "📚", _lazy("knowledge_base"), category="main"),
        Route("expert_training", "专家训练", "🎓", _lazy("expert_training"), category="main"),
        Route("smart_ide", "智能IDE", "💻", _lazy("smart_ide"), category="main"),
        Route("smart_writing", "智能写作", "✍️", _lazy("smart_writing"), category="main"),
        # 共脑系统
        Route("shared_brain", "共脑系统", "🧠", _lazy_shared_brain(), category="main"),
    ]

    # 工具模块（显示在工具菜单）
    tool_routes = [
        Route("settings", "设置", "⚙️", _lazy("settings"), category="settings"),
        Route("profile", "个人资料", "👤", _lazy("profile"), category="settings"),
        Route("evolution", "进化面板", "🧬", _lazy("evolution"), category="tool"),
        Route("finance", "金融面板", "💰", _lazy("finance"), category="tool"),
        Route("game", "游戏面板", "🎮", _lazy("game"), category="tool"),
        # Model Router 监控
        Route("model_router_monitor", "模型监控", "📊", _lazy_model_monitor(), category="tool"),
    ]

    all_routes = main_routes + tool_routes

    for route in all_routes:
        router.register(route)


def _lazy(module_name: str) -> type:
    """
    延迟导入 - 返回代理类

    实际使用时才导入模块，加快启动速度。
    """
    class LazyPanel(QWidget):
        _real_class = None
        _module_name = module_name

        def __init__(self, parent=None):
            super().__init__(parent)
            self._real_instance = None
            self._init_ui()

        def _init_ui(self):
            from PyQt6.QtWidgets import QLabel, QVBoxLayout
            layout = QVBoxLayout(self)
            self.placeholder = QLabel(f"🚀 {self._module_name} 加载中...")
            self.placeholder.setStyleSheet("""
                color: #888888;
                font-size: 16px;
                padding: 40px;
            """)
            self.placeholder.setAlignment(0x0004)  # Qt.AlignCenter
            layout.addWidget(self.placeholder)
            layout.addStretch()

        def _load_real_panel(self):
            """延迟加载真实面板"""
            if self._real_instance is not None:
                return self._real_instance

            # 动态导入
            import importlib
            try:
                module = importlib.import_module(
                    f"client.src.presentation.modules.{self._module_name}.panel"
                )
                panel_class = getattr(module, "Panel", None)
                if panel_class:
                    self._real_instance = panel_class(self.parent())
                    # 替换当前widget
                    layout = self.layout()
                    layout.removeWidget(self.placeholder)
                    self.placeholder.hide()
                    layout.addWidget(self._real_instance)
                    layout.addStretch()
            except Exception as e:
                print(f"[LazyPanel] Failed to load {self._module_name}: {e}")

            return self._real_instance

    return LazyPanel


def _lazy_shared_brain() -> type:
    """
    延迟导入共脑系统面板
    """
    class SharedBrainPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._load_real_panel()

        def _load_real_panel(self):
            """加载真实面板"""
            try:
                from client.src.business.global_model_router import get_global_router
                from client.src.presentation.panels.streaming_thought_demo_panel import StreamingThoughtDemoPanel
                
                model_router = get_global_router()
                real_panel = StreamingThoughtDemoPanel(model_router, self)
                
                # 设置布局
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(real_panel)
                
            except Exception as e:
                print(f"[SharedBrainPanel] Failed to load: {e}")
                # 显示错误占位符
                from PyQt6.QtWidgets import QLabel
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(f"❌ 共脑系统加载失败: {e}"))

    return SharedBrainPanel


def _lazy_model_monitor() -> type:
    """
    延迟导入 Model Router 监控面板
    """
    class ModelMonitorPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._load_real_panel()

        def _load_real_panel(self):
            """加载真实面板"""
            try:
                from client.src.presentation.panels.model_router_monitor_panel import ModelRouterMonitorPanel
                
                real_panel = ModelRouterMonitorPanel(self)
                
                # 设置布局
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(real_panel)
                
            except Exception as e:
                print(f"[ModelMonitorPanel] Failed to load: {e}")
                # 显示错误占位符
                from PyQt6.QtWidgets import QLabel
                error_layout = QVBoxLayout(self)
                error_layout.addWidget(QLabel(f"❌ 监控面板加载失败: {e}"))

    return ModelMonitorPanel
