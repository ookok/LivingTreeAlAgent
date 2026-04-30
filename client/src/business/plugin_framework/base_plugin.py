"""
插件基类 - 所有插件的父类

定义插件的基本结构、生命周期和接口规范
"""

import json
import os
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Type
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject


class PluginMeta(type(QObject), ABCMeta):
    """兼容 QObject 和 ABC 的元类"""
    pass


class PluginType(Enum):
    """插件类型枚举"""
    KNOWLEDGE = "knowledge"           # 知识库类
    EDITOR = "editor"                 # 编辑器类
    TOOL = "tool"                     # 工具类
    CHAT = "chat"                     # 聊天类
    MEDIA = "media"                   # 多媒体类
    PROJECT = "project"               # 项目管理类
    COMMUNICATION = "communication"   # 通讯类
    SYSTEM = "system"                 # 系统类
    CUSTOM = "custom"                # 自定义类


class ViewMode(Enum):
    """视图模式枚举"""
    TABBED = "tabbed"      # 标签页视图
    DOCKABLE = "dockable"  # 停靠窗口
    STANDALONE = "standalone"  # 独立窗口


class ViewPreference:
    """视图偏好设置"""

    def __init__(
        self,
        preferred_mode: ViewMode = ViewMode.TABBED,
        dock_area: str = "left",  # left, right, top, bottom
        default_width: int = 400,
        default_height: int = 600,
        min_width: int = 200,
        min_height: int = 150,
        floatable: bool = True,
        auto_hide: bool = False,
        closable: bool = True,
    ):
        self.preferred_mode = preferred_mode
        self.dock_area = dock_area
        self.default_width = default_width
        self.default_height = default_height
        self.min_width = min_width
        self.min_height = min_height
        self.floatable = floatable
        self.auto_hide = auto_hide
        self.closable = closable


@dataclass
class PluginManifest:
    """插件清单 - 插件元数据"""
    id: str                           # 唯一标识符
    name: str                         # 显示名称
    version: str = "1.0.0"            # 版本号
    author: str = ""                   # 作者
    description: str = ""             # 插件描述
    plugin_type: PluginType = PluginType.CUSTOM  # 插件类型
    view_preference: ViewPreference = None  # 视图偏好
    dependencies: List[str] = field(default_factory=list)  # 依赖插件
    optional_deps: List[str] = field(default_factory=list)  # 可选依赖
    provides: List[str] = field(default_factory=list)  # 提供的服务
    icon: str = ""                     # 图标路径
    css: str = ""                      # 自定义CSS
    lazy_load: bool = True            # 是否懒加载
    single_instance: bool = True      # 是否单实例

    def __post_init__(self):
        if self.view_preference is None:
            self.view_preference = ViewPreference()
        # 确保ID符合规范
        self.id = self.id.lower().replace(" ", "_").replace("-", "_")

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PluginManifest':
        if 'view_preference' in data and data['view_preference']:
            data['view_preference'] = ViewPreference(**data['view_preference'])
        if 'plugin_type' in data and isinstance(data['plugin_type'], str):
            data['plugin_type'] = PluginType(data['plugin_type'])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'PluginManifest':
        return cls.from_dict(json.loads(json_str))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class BasePlugin(QObject, ABC, metaclass=PluginMeta):
    """
    插件基类

    所有插件必须继承此类并实现核心方法

    signals:
        initialized: 插件初始化完成
        activated: 插件被激活
        deactivated: 插件被停用
        data_changed: 插件数据变更
        status_changed: 插件状态变更
    """

    # 信号定义
    initialized = pyqtSignal()
    activated = pyqtSignal()
    deactivated = pyqtSignal()
    data_changed = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self, manifest: PluginManifest, framework: 'PluginFramework'):
        """
        初始化插件

        Args:
            manifest: 插件清单
            framework: 插件框架引用
        """
        super().__init__()
        self.manifest = manifest
        self.framework = framework
        self._is_initialized = False
        self._is_active = False
        self._widget = None
        self._state: Dict[str, Any] = {}
        self._event_handlers: Dict[str, Callable] = {}

    @property
    def plugin_id(self) -> str:
        """获取插件ID"""
        return self.manifest.id

    @property
    def plugin_name(self) -> str:
        """获取插件名称"""
        return self.manifest.name

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized

    @property
    def is_active(self) -> bool:
        """是否处于激活状态"""
        return self._is_active

    @property
    def widget(self) -> Optional[QObject]:
        """获取插件的主Widget"""
        return self._widget

    @property
    def state(self) -> Dict[str, Any]:
        """获取插件状态"""
        return self._state.copy()

    # ==================== 生命周期方法 ====================

    @abstractmethod
    def on_init(self) -> None:
        """
        初始化阶段 - 只调用一次
        用于加载配置、初始化资源等轻量级操作
        """
        pass

    @abstractmethod
    def on_create_widget(self) -> Optional[QObject]:
        """
        创建主Widget
        返回插件的主界面Widget（QWidget或QDialog）
        如果返回None，则该插件不需要UI
        """
        pass

    @abstractmethod
    def on_activate(self) -> None:
        """
        激活阶段 - 每次显示插件时调用
        用于恢复状态、启动定时器等
        """
        pass

    @abstractmethod
    def on_deactivate(self) -> None:
        """
        停用阶段 - 每次隐藏插件时调用
        用于保存状态、停止定时器等
        """
        pass

    def on_destroy(self) -> None:
        """
        销毁阶段 - 插件被卸载时调用
        用于释放资源、保存最终状态
        """
        self._event_handlers.clear()
        self._state.clear()

    def on_save_state(self) -> Dict[str, Any]:
        """
        保存状态 - 用于持久化
        返回需要保存的状态字典
        """
        return self._state.copy()

    def on_load_state(self, state: Dict[str, Any]) -> None:
        """
        加载状态 - 从持久化恢复
        Args:
            state: 之前保存的状态字典
        """
        self._state = state.copy()

    def on_event(self, event: 'Event') -> None:
        """
        处理来自事件总线的全局事件
        Args:
            event: 事件对象
        """
        handler = self._event_handlers.get(event.type)
        if handler:
            handler(event.data)

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理器

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        self._event_handlers[event_type] = handler
        self.framework.event_bus.subscribe(event_type, self.plugin_id, handler)

    def unregister_event_handler(self, event_type: str) -> None:
        """
        注销事件处理器

        Args:
            event_type: 事件类型
        """
        if event_type in self._event_handlers:
            self.framework.event_bus.unsubscribe(event_type, self.plugin_id)
            del self._event_handlers[event_type]

    # ==================== 数据共享方法 ====================

    def publish_data(self, key: str, value: Any) -> None:
        """
        发布数据到共享工作区

        Args:
            key: 数据键
            value: 数据值
        """
        self.framework.publish_data(self.plugin_id, key, value)

    def subscribe_data(self, key: str, callback: Callable[[Any], None]) -> None:
        """
        订阅共享数据变更

        Args:
            key: 数据键
            callback: 变更回调函数
        """
        self.framework.subscribe_data(key, self.plugin_id, callback)

    def unsubscribe_data(self, key: str) -> None:
        """
        取消订阅共享数据

        Args:
            key: 数据键
        """
        self.framework.unsubscribe_data(key, self.plugin_id)

    # ==================== 工具方法 ====================

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取插件配置"""
        return self.framework.get_plugin_config(self.plugin_id, key, default)

    def set_config(self, key: str, value: Any) -> None:
        """设置插件配置"""
        self.framework.set_plugin_config(self.plugin_id, key, value)

    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self.framework.log(f"[{self.plugin_name}] {message}", "INFO")

    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self.framework.log(f"[{self.plugin_name}] {message}", "WARNING")

    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self.framework.log(f"[{self.plugin_name}] {message}", "ERROR")

    # ==================== 内部方法（框架调用） ====================

    def _do_init(self) -> None:
        """执行初始化（由框架调用）"""
        if not self._is_initialized:
            self.on_init()
            self._is_initialized = True
            self.initialized.emit()

    def _do_create_widget(self) -> Optional[QObject]:
        """执行Widget创建（由框架调用）"""
        if self._widget is None:
            self._widget = self.on_create_widget()
        return self._widget

    def _do_activate(self) -> None:
        """执行激活（由框架调用）"""
        if not self._is_active:
            self.on_activate()
            self._is_active = True
            self.activated.emit()

    def _do_deactivate(self) -> None:
        """执行停用（由框架调用）"""
        if self._is_active:
            self.on_deactivate()
            self._is_active = False
            self.deactivated.emit()

    def _do_destroy(self) -> None:
        """执行销毁（由框架调用）"""
        self.on_destroy()
        self._is_initialized = False
        self._is_active = False


class PluginFramework:
    """
    插件框架引用类

    提供插件与框架之间的交互接口
    """

    def __init__(
        self,
        event_bus: 'EventBus',
        theme_system: 'ThemeSystem',
        layout_manager: 'LayoutManager',
        plugin_manager: 'PluginManager',
    ):
        self.event_bus = event_bus
        self.theme_system = theme_system
        self.layout_manager = layout_manager
        self.plugin_manager = plugin_manager
        self._shared_data: Dict[str, Dict[str, Any]] = {}
        self._data_subscribers: Dict[str, Dict[str, Callable]] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._logger: Optional[Callable] = None

    def set_logger(self, logger: Callable[[str, str], None]) -> None:
        """设置日志记录器"""
        self._logger = logger

    def log(self, message: str, level: str = "INFO") -> None:
        """记录日志"""
        if self._logger:
            self._logger(message, level)

    def publish_data(self, plugin_id: str, key: str, value: Any) -> None:
        """
        发布共享数据

        Args:
            plugin_id: 发布者插件ID
            key: 数据键
            value: 数据值
        """
        if key not in self._shared_data:
            self._shared_data[key] = {}
        self._shared_data[key][plugin_id] = value

        # 通知订阅者
        if key in self._data_subscribers:
            for subscriber_id, callback in self._data_subscribers[key].items():
                try:
                    callback(value)
                except Exception as e:
                    self.log(f"Data callback error: {e}", "ERROR")

    def subscribe_data(self, key: str, plugin_id: str, callback: Callable[[Any], None]) -> None:
        """
        订阅共享数据

        Args:
            key: 数据键
            plugin_id: 订阅者插件ID
            callback: 回调函数
        """
        if key not in self._data_subscribers:
            self._data_subscribers[key] = {}
        self._data_subscribers[key][plugin_id] = callback

    def unsubscribe_data(self, key: str, plugin_id: str) -> None:
        """
        取消订阅

        Args:
            key: 数据键
            plugin_id: 订阅者插件ID
        """
        if key in self._data_subscribers and plugin_id in self._data_subscribers[key]:
            del self._data_subscribers[key][plugin_id]

    def get_shared_data(self, key: str) -> Optional[Any]:
        """获取共享数据"""
        if key in self._shared_data:
            # 返回最新的值（最后发布的）
            values = self._shared_data[key]
            if values:
                return list(values.values())[-1]
        return None

    def get_plugin_config(self, plugin_id: str, key: str, default: Any = None) -> Any:
        """获取插件配置"""
        return self._plugin_configs.get(plugin_id, {}).get(key, default)

    def set_plugin_config(self, plugin_id: str, key: str, value: Any) -> None:
        """设置插件配置"""
        if plugin_id not in self._plugin_configs:
            self._plugin_configs[plugin_id] = {}
        self._plugin_configs[plugin_id][key] = value


class PluginState(Enum):
    """插件状态枚举"""
    UNLOADED = "unloaded"       # 未加载
    LOADED = "loaded"           # 已加载
    INITIALIZING = "initializing" # 初始化中
    INITIALIZED = "initialized"   # 已初始化
    ACTIVATING = "activating"     # 激活中
    ACTIVE = "active"           # 已激活
    DEACTIVATING = "deactivating" # 停用中
    ERROR = "error"             # 出错
    DISABLED = "disabled"       # 已禁用


@dataclass
class PluginInfo:
    """插件信息"""
    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    plugin_type: PluginType
    state: PluginState
    enabled: bool = True
    has_ui: bool = True


class PluginFramework:
    """插件框架接口"""
    
    def get_plugin_manager(self) -> 'PluginManager':
        """获取插件管理器"""
        raise NotImplementedError
    
    def get_event_bus(self) -> 'EventBus':
        """获取事件总线"""
        raise NotImplementedError
    
    def get_layout_manager(self) -> 'LayoutManager':
        """获取布局管理器"""
        raise NotImplementedError
    
    def get_theme_system(self) -> 'ThemeSystem':
        """获取主题系统"""
        raise NotImplementedError
    
    def get_view_factory(self) -> 'ViewFactory':
        """获取视图工厂"""
        raise NotImplementedError
    
    def get_shared_workspace(self) -> 'SharedWorkspace':
        """获取共享工作区"""
        raise NotImplementedError
