"""
路由表 - 默认路由定义

所有模块在此注册，解决原有200个panel无入口问题。
根据系统重构后的功能重新设计。
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

    # =========================================================================
    # 主模块（显示在左侧导航 - 核心功能）
    # =========================================================================
    main_routes = [
        Route("chat", "智能对话", "💬", _lazy("chat"), category="main"),
        Route("deep_search", "深度搜索", "🔍", _lazy("search"), category="main"),
        Route("knowledge_base", "知识库", "📚", _lazy("knowledge"), category="main"),
        Route("expert_training", "专家训练", "🎓", _lazy("training"), category="main"),
        Route("smart_ide", "智能IDE", "💻", _lazy("ide"), category="main"),
        Route("smart_writing", "智能写作", "✍️", _lazy("writing"), category="main"),
        # 环评助手（P0 新增）
        Route("ei_wizard", "环评助手", "📋", _lazy_ei_wizard(), category="main"),
        # 共脑系统
        Route("shared_brain", "共脑系统", "🧠", _lazy_shared_brain(), category="main"),
    ]

    # =========================================================================
    # 领域面板（显示在左侧导航 - 专业领域）
    # =========================================================================
    domain_routes = [
        Route("finance", "金融中心", "💰", _lazy_finance(), category="domain"),
        Route("game", "游戏中心", "🎮", _lazy_game(), category="domain"),
    ]

    # =========================================================================
    # 工具模块（显示在工具菜单）
    # =========================================================================
    tool_routes = [
        Route("evolution", "进化面板", "🧬", _create_evolution_panel, category="tool"),
        Route("model_router_monitor", "模型监控", "📊", _lazy_model_monitor(), category="tool"),
        Route("plugin_manager", "插件管理", "🔌", _create_plugin_manager_panel, category="tool"),
        Route("marketplace", "生态市场", "🛒", _create_marketplace_panel, category="tool"),
        Route("skills", "技能中心", "🧠", _create_skills_panel, category="tool"),
    ]

    # =========================================================================
    # 设置模块（显示在设置菜单）
    # =========================================================================
    settings_routes = [
        Route("settings", "系统设置", "⚙️", _lazy("settings"), category="settings"),
        Route("profile", "个人资料", "👤", _create_profile_panel, category="settings"),
    ]

    all_routes = main_routes + domain_routes + tool_routes + settings_routes

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


def _lazy_finance() -> type:
    """
    延迟导入金融面板
    """
    class FinancePanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._load_real_panel()

        def _load_real_panel(self):
            """加载真实面板"""
            try:
                from client.src.presentation.panels.finance_hub_panel import FinanceHubPanel

                real_panel = FinanceHubPanel(self)

                # 设置布局
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(real_panel)

            except Exception as e:
                print(f"[FinancePanel] Failed to load: {e}")
                # 显示错误占位符
                from PyQt6.QtWidgets import QLabel
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(f"❌ 金融面板加载失败: {e}"))

    return FinancePanel


def _lazy_game() -> type:
    """
    延迟导入游戏面板
    """
    class GamePanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._load_real_panel()

        def _load_real_panel(self):
            """加载真实面板"""
            try:
                from client.src.presentation.panels.game_hub_panel import GameHubPanel

                real_panel = GameHubPanel(self)

                # 设置布局
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(real_panel)

            except Exception as e:
                print(f"[GamePanel] Failed to load: {e}")
                # 显示错误占位符
                from PyQt6.QtWidgets import QLabel
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(f"❌ 游戏面板加载失败: {e}"))

    return GamePanel


def _lazy_evolution() -> type:
    """
    延迟导入进化面板
    """
    class EvolutionPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_ui()

        def _init_ui(self):
            from PyQt6.QtWidgets import QLabel, QVBoxLayout, QPushButton
            layout = QVBoxLayout(self)

            # 标题
            title = QLabel("🧬 进化面板")
            title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px;")
            layout.addWidget(title)

            # 描述
            desc = QLabel("可视化进化引擎 - 监控和控制系统自我进化过程")
            desc.setStyleSheet("font-size: 14px; color: #666; padding: 0 20px;")
            layout.addWidget(desc)

            # TODO: 集成真实的 EvolutionPanel
            info = QLabel("⚠️ 功能开发中...")
            info.setStyleSheet("font-size: 12px; color: #888; padding: 20px;")
            layout.addWidget(info)

            layout.addStretch()

    return EvolutionPanel


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


def _lazy_plugin_manager() -> type:
    """
    延迟导入插件管理面板
    """
    class PluginManagerPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_ui()

        def _init_ui(self):
            from PyQt6.QtWidgets import QLabel, QVBoxLayout
            layout = QVBoxLayout(self)

            # 标题
            title = QLabel("🔌 插件管理")
            title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px;")
            layout.addWidget(title)

            # 描述
            desc = QLabel("插件管理系统 - 安装、卸载、配置插件")
            desc.setStyleSheet("font-size: 14px; color: #666; padding: 0 20px;")
            layout.addWidget(desc)

            # TODO: 集成真实的 PluginManager
            info = QLabel("⚠️ 功能开发中...")
            info.setStyleSheet("font-size: 12px; color: #888; padding: 20px;")
            layout.addWidget(info)

            layout.addStretch()

    return PluginManagerPanel


def _lazy_marketplace() -> type:
    """
    延迟导入生态市场面板
    """
    class MarketplacePanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_ui()

        def _init_ui(self):
            from PyQt6.QtWidgets import QLabel, QVBoxLayout
            layout = QVBoxLayout(self)

            # 标题
            title = QLabel("🛒 生态市场")
            title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px;")
            layout.addWidget(title)

            # 描述
            desc = QLabel("生态市场 - 浏览、购买、评价插件和技能")
            desc.setStyleSheet("font-size: 14px; color: #666; padding: 0 20px;")
            layout.addWidget(desc)

            # TODO: 集成真实的 Marketplace
            info = QLabel("⚠️ 功能开发中...")
            info.setStyleSheet("font-size: 12px; color: #888; padding: 20px;")
            layout.addWidget(info)

            layout.addStretch()

    return MarketplacePanel


def _lazy_profile() -> type:
    """
    延迟导入个人资料面板
    """
    class ProfilePanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_ui()

        def _init_ui(self):
            from PyQt6.QtWidgets import QLabel, QVBoxLayout
            layout = QVBoxLayout(self)

            # 标题
            title = QLabel("👤 个人资料")
            title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px;")
            layout.addWidget(title)

            # 描述
            desc = QLabel("个人资料 - 查看和编辑个人信息")
            desc.setStyleSheet("font-size: 14px; color: #666; padding: 0 20px;")
            layout.addWidget(desc)

            # TODO: 集成真实的 Profile
            info = QLabel("⚠️ 功能开发中...")
            info.setStyleSheet("font-size: 12px; color: #888; padding: 20px;")
            layout.addWidget(info)

            layout.addStretch()

    return ProfilePanel


# =========================================================================
# 新创建的面板（直接使用，不延迟加载）
# =========================================================================

def _create_evolution_panel() -> type:
    """
    返回 EvolutionPanel 类
    """
    try:
        from client.src.presentation.panels.evolution_panel import EvolutionPanel
        return EvolutionPanel
    except Exception as e:
        print(f"[_create_evolution_panel] Failed to import: {e}")
        return None


def _create_plugin_manager_panel() -> type:
    """
    返回 PluginManagerPanel 类
    """
    try:
        from client.src.presentation.panels.plugin_manager_panel import PluginManagerPanel
        return PluginManagerPanel
    except Exception as e:
        print(f"[_create_plugin_manager_panel] Failed to import: {e}")
        return None


def _create_marketplace_panel() -> type:
    """
    返回 MarketplacePanel 类
    """
    try:
        from client.src.presentation.panels.marketplace_panel import MarketplacePanel
        return MarketplacePanel
    except Exception as e:
        print(f"[_create_marketplace_panel] Failed to import: {e}")
        return None


def _create_profile_panel() -> type:
    """
    返回 ProfilePanel 类
    """
    try:
        from client.src.presentation.panels.profile_panel import ProfilePanel
        return ProfilePanel
    except Exception as e:
        print(f"[_create_profile_panel] Failed to import: {e}")
        return None


def _create_skills_panel() -> type:
    """
    返回 SkillsPanel 类（技能与专家角色管理）
    """
    try:
        from client.src.presentation.panels.skills_panel import SkillsPanel
        return SkillsPanel
    except Exception as e:
        print(f"[_create_skills_panel] Failed to import: {e}")
        return None


def _lazy_ei_wizard() -> type:
    """
    延迟导入环评助手面板（EIWizardChat）
    """
    class EIWizardPanel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._load_real_panel()

        def _load_real_panel(self):
            """加载真实面板"""
            try:
                from client.src.presentation.wizards.ei_wizard_chat import EIWizardChat

                real_panel = EIWizardChat(self)

                # 设置布局
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(real_panel)

            except Exception as e:
                print(f"[EIWizardPanel] Failed to load: {e}")
                # 显示错误占位符
                from PyQt6.QtWidgets import QLabel
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(f"❌ 环评助手加载失败: {e}"))

    return EIWizardPanel

