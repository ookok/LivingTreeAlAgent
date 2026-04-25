"""
插件管理器 - Plugin Manager

核心功能：
1. 插件注册与发现
2. 插件生命周期管理
3. 插件依赖解析
4. 插件实例化与销毁

设计理念：
- 插件是懒加载的
- 支持插件依赖图
- 支持可选依赖
- 提供完整的生命周期管理
"""

import json
import os
import importlib
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Type, Set
from PyQt6.QtCore import QObject, pyqtSignal

from .base_plugin import (
    BasePlugin, PluginManifest, PluginType,
    PluginFramework, ViewPreference, ViewMode
)
from .event_bus import EventBus, get_event_bus
from .theme_system import ThemeSystem, get_theme_system
from .layout_manager import LayoutManager, get_layout_manager
from .view_factory import ViewFactory, ViewConfig, get_view_factory


class PluginState(Enum):
    """插件状态"""
    REGISTERED = "registered"   # 已注册
    LOADED = "loaded"          # 已加载（Widget已创建）
    ACTIVE = "active"          # 已激活（正在显示）
    INACTIVE = "inactive"       # 已停用
    ERROR = "error"             # 错误状态


@dataclass
class PluginInfo:
    """插件信息"""
    manifest: PluginManifest
    state: PluginState = PluginState.REGISTERED
    instance: Optional[BasePlugin] = None
    error_message: str = ""
    load_time: float = 0.0  # 加载耗时


class PluginManager(QObject):
    """
    插件管理器

    管理所有插件的生命周期

    使用示例：
        manager = PluginManager()

        # 注册插件
        manager.register_plugin(MyPluginManifest)

        # 初始化所有插件
        manager.initialize_all()

        # 激活插件
        manager.activate_plugin("my_plugin")

        # 获取插件
        plugin = manager.get_plugin("my_plugin")
    """

    # 信号定义
    plugin_registered = pyqtSignal(str)  # plugin_id
    plugin_loaded = pyqtSignal(str)  # plugin_id
    plugin_activated = pyqtSignal(str)  # plugin_id
    plugin_deactivated = pyqtSignal(str)  # plugin_id
    plugin_error = pyqtSignal(str, str)  # plugin_id, error_message
    plugin_unregistered = pyqtSignal(str)  # plugin_id

    def __init__(self):
        super().__init__()
        self._plugins: Dict[str, PluginInfo] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
        self._event_bus = get_event_bus()
        self._theme_system = get_theme_system()
        self._layout_manager: Optional[LayoutManager] = None
        self._view_factory: Optional[ViewFactory] = None
        self._framework: Optional[PluginFramework] = None
        self._initialized = False
        self._plugin_dirs: List[str] = []

    def initialize(
        self,
        main_window=None,
        plugin_dirs: Optional[List[str]] = None
    ) -> None:
        """
        初始化插件管理器

        Args:
            main_window: 主窗口
            plugin_dirs: 插件目录列表
        """
        if self._initialized:
            return

        # 初始化视图工厂
        if main_window:
            self._view_factory = get_view_factory(main_window)
        else:
            self._view_factory = get_view_factory()

        # 初始化布局管理器
        if main_window:
            self._layout_manager = get_layout_manager(main_window)
            self._layout_manager.set_view_factory(self._view_factory)

        # 创建框架引用
        self._framework = PluginFramework(
            event_bus=self._event_bus,
            theme_system=self._theme_system,
            layout_manager=self._layout_manager,
            plugin_manager=self,
        )

        # 设置插件目录
        if plugin_dirs:
            self._plugin_dirs = plugin_dirs

        self._initialized = True

    def register_plugin_class(
        self,
        plugin_class: Type[BasePlugin],
        manifest: PluginManifest,
    ) -> bool:
        """
        注册插件类

        Args:
            plugin_class: 插件类
            manifest: 插件清单

        Returns:
            是否成功
        """
        plugin_id = manifest.id

        if plugin_id in self._plugins:
            return False  # 已存在

        # 检查依赖
        for dep_id in manifest.dependencies:
            if dep_id not in self._plugins and dep_id not in self._plugin_classes:
                self.plugin_error.emit(plugin_id, f"Missing dependency: {dep_id}")
                return False

        # 注册类
        self._plugin_classes[plugin_id] = plugin_class

        # 创建插件信息
        info = PluginInfo(manifest=manifest)
        self._plugins[plugin_id] = info

        self.plugin_registered.emit(plugin_id)
        return True

    def register_plugin(self, plugin_instance: BasePlugin) -> bool:
        """
        注册插件实例

        Args:
            plugin_instance: 插件实例

        Returns:
            是否成功
        """
        plugin_id = plugin_instance.plugin_id

        if plugin_id in self._plugins:
            return False

        info = PluginInfo(
            manifest=plugin_instance.manifest,
            instance=plugin_instance,
            state=PluginState.REGISTERED,
        )
        self._plugins[plugin_id] = info

        self.plugin_registered.emit(plugin_id)
        return True

    def unregister_plugin(self, plugin_id: str) -> bool:
        """
        注销插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否成功
        """
        if plugin_id not in self._plugins:
            return False

        info = self._plugins[plugin_id]

        # 如果插件处于激活状态，先停用
        if info.state == PluginState.ACTIVE:
            self.deactivate_plugin(plugin_id)

        # 如果插件已加载，销毁它
        if info.state == PluginState.LOADED and info.instance:
            info.instance._do_destroy()
            info.instance = None

        del self._plugins[plugin_id]
        if plugin_id in self._plugin_classes:
            del self._plugin_classes[plugin_id]

        self.plugin_unregistered.emit(plugin_id)
        return True

    # ─────────────────────────────────────────────────────────
    # 热插拔（运行时安装/卸载/重载）
    # ─────────────────────────────────────────────────────────

    def install_plugin_from_directory(self, plugin_dir: str) -> Optional[str]:
        """
        从目录运行时安装插件

        热插拔：无需重启即可使用新插件。

        Args:
            plugin_dir: 插件目录路径（包含 manifest.json）

        Returns:
            成功返回 plugin_id，失败返回 None

        Emits:
            plugin_registered: 注册成功
            plugin_loaded: 加载成功
            plugin_activated: 激活成功
        """
        import importlib.util

        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            logger.error(f"[PluginManager] No manifest.json in: {plugin_dir}")
            return None

        try:
            # 1. 读取 manifest
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            plugin_id = manifest_data.get("id")
            if not plugin_id:
                logger.error("[PluginManager] manifest.json missing 'id' field")
                return None

            if plugin_id in self._plugins:
                logger.warning(f"[PluginManager] Plugin already installed: {plugin_id}")
                return None

            # 2. 检查依赖
            deps = manifest_data.get("dependencies", [])
            missing_deps = [
                dep for dep in deps
                if dep not in self._plugins and dep not in self._plugin_classes
            ]
            if missing_deps:
                logger.error(
                    f"[PluginManager] Missing dependencies for {plugin_id}: "
                    f"{missing_deps}"
                )
                return None

            # 3. 动态导入插件模块
            main_py = os.path.join(plugin_dir, "main.py")
            plugin_class = None

            if os.path.exists(main_py):
                spec = importlib.util.spec_from_file_location(
                    f"plugin_.{plugin_id}", main_py,
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找 BasePlugin 的子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                    ):
                        plugin_class = attr
                        break

            # 4. 创建 manifest 对象
            from .base_plugin import PluginManifest
            manifest = PluginManifest(
                id=manifest_data["id"],
                name=manifest_data.get("name", plugin_id),
                version=manifest_data.get("version", "1.0.0"),
                description=manifest_data.get("description", ""),
                author=manifest_data.get("author", ""),
                dependencies=manifest_data.get("dependencies", []),
                optional_deps=manifest_data.get("optional_deps", []),
                plugin_type=PluginType.MODULE,  # 默认类型
                priority=manifest_data.get("priority", 0),
                lazy_load=manifest_data.get("lazy_load", True),
            )

            # 5. 注册插件类
            if plugin_class:
                self._plugin_classes[plugin_id] = plugin_class

            # 6. 注册插件
            info = PluginInfo(manifest=manifest)
            self._plugins[plugin_id] = info
            self.plugin_registered.emit(plugin_id)

            logger.info(f"[PluginManager] Hot-installed plugin: {plugin_id}")
            return plugin_id

        except Exception as e:
            logger.error(f"[PluginManager] Hot-install failed: {e}")
            logger.error(traceback.format_exc())
            return None

    def uninstall_plugin_runtime(
        self,
        plugin_id: str,
        force: bool = False,
    ) -> bool:
        """
        运行时卸载插件

        热插拔：无需重启即可移除插件。

        Args:
            plugin_id: 插件 ID
            force: 是否强制卸载（忽略依赖检查）

        Returns:
            是否成功卸载

        Emits:
            plugin_deactivated: 停用成功
            plugin_unregistered: 注销成功
        """
        if plugin_id not in self._plugins:
            logger.warning(f"[PluginManager] Plugin not found: {plugin_id}")
            return False

        # 检查是否有其他插件依赖此插件
        if not force:
            dependents = self._find_dependents(plugin_id)
            if dependents:
                logger.error(
                    f"[PluginManager] Cannot uninstall {plugin_id}: "
                    f"still depended by {dependents}"
                )
                return False

        try:
            info = self._plugins[plugin_id]

            # 1. 停用插件
            if info.state == PluginState.ACTIVE:
                self.deactivate_plugin(plugin_id)

            # 2. 销毁插件实例
            if info.instance:
                info.instance._do_destroy()
                info.instance = None

            # 3. 注销插件
            del self._plugins[plugin_id]
            if plugin_id in self._plugin_classes:
                del self._plugin_classes[plugin_id]

            self.plugin_unregistered.emit(plugin_id)

            logger.info(f"[PluginManager] Hot-uninstalled plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"[PluginManager] Hot-uninstall failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def reload_plugin(self, plugin_id: str) -> bool:
        """
        运行时重载插件

        热插拔：重新加载插件代码（用于开发调试）。

        Args:
            plugin_id: 插件 ID

        Returns:
            是否成功重载
        """
        if plugin_id not in self._plugins:
            logger.warning(f"[PluginManager] Plugin not found: {plugin_id}")
            return False

        try:
            info = self._plugins[plugin_id]
            manifest = info.manifest

            # 1. 记录当前状态
            was_active = info.state == PluginState.ACTIVE

            # 2. 停用并销毁
            if info.state == PluginState.ACTIVE:
                self.deactivate_plugin(plugin_id)
            if info.instance:
                info.instance._do_destroy()
                info.instance = None

            # 3. 重新加载（通过 install_plugin_from_directory）
            # 找到插件目录
            plugin_dir = None
            for d in self._plugin_dirs:
                if os.path.exists(os.path.join(d, plugin_id)):
                    plugin_dir = os.path.join(d, plugin_id)
                    break

            if not plugin_dir:
                logger.error(f"[PluginManager] Plugin directory not found: {plugin_id}")
                return False

            # 4. 注销旧插件
            del self._plugins[plugin_id]
            if plugin_id in self._plugin_classes:
                del self._plugin_classes[plugin_id]

            # 5. 重新安装
            new_id = self.install_plugin_from_directory(plugin_dir)
            if not new_id:
                return False

            # 6. 如果之前是激活状态，重新激活
            if was_active:
                self.activate_plugin(new_id)

            logger.info(f"[PluginManager] Hot-reloaded plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"[PluginManager] Hot-reload failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def _find_dependents(self, plugin_id: str) -> List[str]:
        """查找依赖指定插件的其他插件"""
        dependents = []
        for pid, info in self._plugins.items():
            if plugin_id in info.manifest.dependencies:
                dependents.append(pid)
        return dependents

    def initialize_plugin(self, plugin_id: str) -> bool:
        """
        初始化单个插件（创建Widget）

        Args:
            plugin_id: 插件ID

        Returns:
            是否成功
        """
        if plugin_id not in self._plugins:
            return False

        info = self._plugins[plugin_id]

        try:
            # 如果还没有实例，创建实例
            if info.instance is None:
                if plugin_id not in self._plugin_classes:
                    # 尝试懒加载
                    if not self._lazy_load_plugin(plugin_id):
                        return False
                    if plugin_id not in self._plugin_classes:
                        return False

                plugin_class = self._plugin_classes[plugin_id]
                info.instance = plugin_class(info.manifest, self._framework)

            # 调用初始化
            info.instance._do_init()

            # 创建Widget
            info.instance._do_create_widget()

            info.state = PluginState.LOADED
            self.plugin_loaded.emit(plugin_id)
            return True

        except Exception as e:
            info.state = PluginState.ERROR
            info.error_message = str(e)
            self.plugin_error.emit(plugin_id, str(e))
            return False

    def initialize_all(self) -> int:
        """
        初始化所有已注册的插件

        Returns:
            成功初始化的数量
        """
        success_count = 0
        for plugin_id in list(self._plugins.keys()):
            # 只初始化懒加载且未加载的插件
            info = self._plugins[plugin_id]
            if (info.manifest.lazy_load and
                info.state == PluginState.REGISTERED):
                if self.initialize_plugin(plugin_id):
                    success_count += 1
        return success_count

    def activate_plugin(self, plugin_id: str) -> bool:
        """
        激活插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否成功
        """
        if plugin_id not in self._plugins:
            return False

        info = self._plugins[plugin_id]

        try:
            # 确保已初始化
            if info.state == PluginState.REGISTERED:
                if not self.initialize_plugin(plugin_id):
                    return False

            # 激活
            info.instance._do_activate()
            info.state = PluginState.ACTIVE

            # 创建视图
            if info.instance.widget and self._view_factory:
                view_config = ViewConfig(
                    mode=info.manifest.view_preference.preferred_mode,
                    title=info.manifest.name,
                    icon=info.manifest.icon,
                    closable=info.manifest.view_preference.closable,
                    floatable=info.manifest.view_preference.floatable,
                    area=info.manifest.view_preference.dock_area,
                    width=info.manifest.view_preference.default_width,
                    height=info.manifest.view_preference.default_height,
                    min_width=info.manifest.view_preference.min_width,
                    min_height=info.manifest.view_preference.min_height,
                )
                view = self._view_factory.create_view(
                    view_id=f"{plugin_id}_view",
                    config=view_config,
                    content_widget=info.instance.widget,
                )

            self.plugin_activated.emit(plugin_id)
            return True

        except Exception as e:
            info.state = PluginState.ERROR
            info.error_message = str(e)
            self.plugin_error.emit(plugin_id, str(e))
            return False

    def deactivate_plugin(self, plugin_id: str) -> bool:
        """
        停用插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否成功
        """
        if plugin_id not in self._plugins:
            return False

        info = self._plugins[plugin_id]

        if info.state != PluginState.ACTIVE:
            return True  # 已经停用

        try:
            info.instance._do_deactivate()
            info.state = PluginState.INACTIVE
            self.plugin_deactivated.emit(plugin_id)
            return True

        except Exception as e:
            info.state = PluginState.ERROR
            info.error_message = str(e)
            self.plugin_error.emit(plugin_id, str(e))
            return False

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        info = self._plugins.get(plugin_id)
        return info.instance if info else None

    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> Dict[str, PluginInfo]:
        """获取所有插件"""
        return self._plugins.copy()

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        """获取指定类型的所有插件"""
        return [
            info for info in self._plugins.values()
            if info.manifest.plugin_type == plugin_type
        ]

    def get_active_plugins(self) -> List[str]:
        """获取所有已激活插件ID"""
        return [
            plugin_id for plugin_id, info in self._plugins.items()
            if info.state == PluginState.ACTIVE
        ]

    def get_plugin_state(self, plugin_id: str) -> Optional[PluginState]:
        """获取插件状态"""
        info = self._plugins.get(plugin_id)
        return info.state if info else None

    def check_dependencies(self, plugin_id: str) -> Dict[str, bool]:
        """
        检查插件依赖

        Returns:
            依赖ID -> 是否满足
        """
        info = self._plugins.get(plugin_id)
        if not info:
            return {}

        result = {}
        for dep_id in info.manifest.dependencies:
            result[dep_id] = dep_id in self._plugins

        for opt_id in info.manifest.optional_deps:
            result[opt_id] = opt_id in self._plugins

        return result

    # ─────────────────────────────────────────────────────────
    # 依赖拓扑排序
    # ─────────────────────────────────────────────────────────

    def topological_sort_plugins(self) -> List[str]:
        """
        对插件进行拓扑排序（按依赖关系确定加载顺序）

        Returns:
            排序后的插件 ID 列表（被依赖的插件在前）

        Raises:
            ValueError: 存在循环依赖
        """
        # 构建邻接表（plugin_id -> 依赖它的插件列表）
        in_degree: Dict[str, int] = {}
        dependents: Dict[str, List[str]] = {}

        for plugin_id, info in self._plugins.items():
            if plugin_id not in in_degree:
                in_degree[plugin_id] = 0
            # 统计入度（被多少个插件依赖）
            for dep_id in info.manifest.dependencies:
                if dep_id in self._plugins:
                    in_degree[plugin_id] = in_degree.get(plugin_id, 0) + 1
                    if dep_id not in dependents:
                        dependents[dep_id] = []
                    dependents[dep_id].append(plugin_id)

        # Kahn 算法：从入度为 0 的节点开始
        queue = [pid for pid, deg in in_degree.items() if deg == 0]
        sorted_list: List[str] = []

        while queue:
            # 按插件优先级排序（数值越大越先加载）
            queue.sort(key=lambda pid: self._plugins[pid].manifest.priority, reverse=True)

            current = queue.pop(0)
            sorted_list.append(current)

            # 减少依赖当前插件的其他插件的入度
            if current in dependents:
                for dependent in dependents[current]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # 检查是否有循环依赖
        if len(sorted_list) != len(self._plugins):
            remaining = set(self._plugins.keys()) - set(sorted_list)
            raise ValueError(
                f"Circular dependency detected among: {remaining}"
            )

        return sorted_list

    def get_plugin_load_order(self) -> List[str]:
        """
        获取插件加载顺序（考虑依赖和优先级）

        Returns:
            加载顺序列表（从先加载到后加载）
        """
        try:
            return self.topological_sort_plugins()
        except ValueError as e:
            logger.error(f"[PluginManager] {e}")
            # 存在循环依赖时，返回按优先级排序的列表（尽力而为）
            return sorted(
                self._plugins.keys(),
                key=lambda pid: self._plugins[pid].manifest.priority,
                reverse=True,
            )

    def initialize_all_sorted(self) -> Dict[str, bool]:
        """
        按依赖顺序初始化所有插件

        Returns:
            插件 ID -> 是否成功初始化的字典
        """
        load_order = self.get_plugin_load_order()
        results: Dict[str, bool] = {}

        logger.info(
            f"[PluginManager] Initializing plugins in order: {load_order}"
        )

        for plugin_id in load_order:
            info = self._plugins[plugin_id]
            # 跳过已加载的
            if info.state != PluginState.REGISTERED:
                results[plugin_id] = True
                continue
            # 检查必需依赖是否已加载
            deps_met = all(
                dep_id in self._plugins and
                self._plugins[dep_id].state in (
                    PluginState.LOADED, PluginState.ACTIVE, PluginState.INACTIVE,
                )
                for dep_id in info.manifest.dependencies
            )
            if not deps_met:
                logger.warning(
                    f"[PluginManager] Skipping {plugin_id}: dependencies not loaded"
                )
                results[plugin_id] = False
                continue

            success = self.initialize_plugin(plugin_id)
            results[plugin_id] = success

        return results

    def detect_circular_dependency(self) -> List[List[str]]:
        """
        检测循环依赖

        Returns:
            循环依赖链列表（每个子列表是一个循环链）
        """
        cycles = []
        visited = set()
        path = []

        def dfs(pid: str) -> bool:
            """深度优先搜索，返回是否发现环"""
            if pid in path:
                # 发现环
                cycle_start = path.index(pid)
                cycles.append(path[cycle_start:] + [pid])
                return True

            if pid in visited:
                return False

            visited.add(pid)
            path.append(pid)

            info = self._plugins.get(pid)
            if info:
                for dep_id in info.manifest.dependencies:
                    if dep_id in self._plugins:
                        if dfs(dep_id):
                            pass  # 继续收集其他环

            path.pop()
            return False

        for pid in self._plugins:
            if pid not in visited:
                dfs(pid)

        return cycles

    def get_dependency_tree(self, plugin_id: str, indent: int = 0) -> str:
        """
        获取插件的依赖树（文本表示）

        Args:
            plugin_id: 插件 ID
            indent: 缩进级别

        Returns:
            依赖树字符串
        """
        info = self._plugins.get(plugin_id)
        if not info:
            return " " * indent + f"{plugin_id} (not found)"

        lines = []
        prefix = " " * indent
        state_marker = {
            PluginState.REGISTERED: "○",
            PluginState.LOADED: "◐",
            PluginState.ACTIVE: "●",
            PluginState.INACTIVE: "◑",
            PluginState.ERROR: "✗",
        }.get(info.state, "?")

        lines.append(
            f"{prefix}{state_marker} {plugin_id} "
            f"(priority={info.manifest.priority})"
        )

        for dep_id in info.manifest.dependencies:
            lines.append(self.get_dependency_tree(dep_id, indent + 2))

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    # 懒加载辅助
    # ─────────────────────────────────────────────────────────

    def _lazy_load_plugin(self, plugin_id: str) -> bool:
        """懒加载插件类"""
        # 扫描插件目录查找插件类
        for plugin_dir in self._plugin_dirs:
            manifest_path = os.path.join(plugin_dir, plugin_id, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest_data = json.load(f)
                    # 这里应该动态导入模块
                    # 简化实现，实际需要更复杂的动态导入逻辑
                    return True
                except Exception:
                    pass
        return False

    def load_plugins_from_directory(self, directory: str) -> int:
        """
        从目录加载插件

        Args:
            directory: 插件目录

        Returns:
            加载的插件数量
        """
        count = 0
        if not os.path.exists(directory):
            return count

        for item in os.listdir(directory):
            plugin_path = os.path.join(directory, item)
            if os.path.isdir(plugin_path):
                manifest_path = os.path.join(plugin_path, "manifest.json")
                if os.path.exists(manifest_path):
                    # TODO: 实现完整的动态加载逻辑
                    count += 1

        return count

    def save_plugin_states(self) -> Dict[str, Any]:
        """保存插件状态"""
        return {
            plugin_id: {
                "state": info.state.value,
                "error_message": info.error_message,
            }
            for plugin_id, info in self._plugins.items()
        }

    def load_plugin_states(self, data: Dict[str, Any]) -> None:
        """加载插件状态"""
        for plugin_id, state_data in data.items():
            if plugin_id in self._plugins:
                self._plugins[plugin_id].state = PluginState(state_data["state"])
                self._plugins[plugin_id].error_message = state_data.get("error_message", "")


# 全局单例
_plugin_manager_instance: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取插件管理器单例"""
    global _plugin_manager_instance
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginManager()
    return _plugin_manager_instance
