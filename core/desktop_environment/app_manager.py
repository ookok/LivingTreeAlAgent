# app_manager.py — 应用管理器
# ============================================================================
#
# 负责应用注册、启动、关闭的生命周期管理
# 支持应用沙箱隔离
#
# ============================================================================

import json
import importlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from enum import Enum

# ============================================================================
# 配置与枚举
# ============================================================================

class AppState(Enum):
    """应用状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"

@dataclass
class AppInfo:
    """应用信息"""
    id: str                          # 应用 ID
    name: str                        # 应用名称
    version: str = "1.0.0"          # 版本
    author: str = ""                 # 作者
    description: str = ""             # 描述
    icon: str = ""                   # 图标路径
    module: str = ""                  # 模块路径
    entry_point: str = "App"         # 入口类/函数
    desktop_index: int = 0           # 所属桌面索引
    category: str = "default"        # 分类
    tags: List[str] = field(default_factory=list)  # 标签
    permissions: List[str] = field(default_factory=list)  # 权限
    window_config: dict = field(default_factory=dict)  # 窗口配置

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "icon": self.icon,
            "module": self.module,
            "entry_point": self.entry_point,
            "desktop_index": self.desktop_index,
            "category": self.category,
            "tags": self.tags,
            "permissions": self.permissions,
            "window_config": self.window_config,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppInfo":
        return cls(**data)

# ============================================================================
# 应用沙箱
# ============================================================================

class AppSandbox:
    """
    应用沙箱

    为每个应用提供隔离的运行环境
    限制应用的权限和资源使用
    """

    # 允许的动作
    ALLOWED_ACTIONS = [
        "network.request",
        "network.fetch",
        "storage.local",
        "storage.session",
        "ui.notification",
        "ui.dialog",
        "system.info",
        "system.clipboard",
    ]

    def __init__(self, app_info: AppInfo):
        self.app_info = app_info

        # 允许的动作
        self.allowed_actions = set(self.ALLOWED_ACTIONS)
        for perm in app_info.permissions:
            if perm.startswith("action:"):
                self.allowed_actions.add(perm[7:])

        # 资源限制
        self.limits = {
            "max_memory_mb": 50,
            "max_storage_mb": 10,
            "network_quota_mb": 100,
            "max_execution_time": 3600,  # 秒
        }

        # 使用统计
        self.usage = {
            "memory_mb": 0,
            "storage_mb": 0,
            "network_mb": 0,
            "start_time": None,
        }

        # 系统 API
        self._system_api = {
            "notify": self._api_notify,
            "storage": self._api_storage,
            "network": self._api_network,
            "config": self._api_config,
            "check_permission": self._check_permission,
        }

    def check_action(self, action: str) -> bool:
        """检查是否允许执行动作"""
        return action in self.allowed_actions

    def check_limit(self, resource: str, value: float) -> bool:
        """检查资源限制"""
        limit = self.limits.get(f"max_{resource}")
        if limit is None:
            return True
        return value <= limit

    # --------------------------------------------------------------------------
    # 系统 API 实现
    # --------------------------------------------------------------------------

    def _api_notify(self, message: str, level: str = "info"):
        """发送通知"""
        if not self.check_action("ui.notification"):
            raise PermissionError("Notification not allowed")
        logger.info(f"[{level.upper()}] {self.app_info.name}: {message}")

    def _api_storage(self, key: str, value: Any = None):
        """存储数据"""
        if not self.check_action("storage.local"):
            raise PermissionError("Storage not allowed")
        # 实现存储逻辑
        pass

    def _api_network(self, url: str, method: str = "GET", **kwargs):
        """网络请求"""
        if not self.check_action("network.request"):
            raise PermissionError("Network request not allowed")

        if not self.check_limit("network_mb", kwargs.get("size", 0) / 1024 / 1024):
            raise ResourceLimitError("Network quota exceeded")

        # 实现网络请求逻辑
        pass

    def _api_config(self, key: str, value: Any = None):
        """配置管理"""
        if not self.check_action("system.info"):
            raise PermissionError("Config access not allowed")
        # 实现配置逻辑
        pass

    def _check_permission(self, permission: str) -> bool:
        """检查权限"""
        return self.check_action(permission)

    def get_system_api(self) -> dict:
        """获取系统 API"""
        return self._system_api

# ============================================================================
# 应用管理器
# ============================================================================

class AppManager:
    """
    应用管理器

    职责:
    1. 应用注册和注销
    2. 应用启动和关闭
    3. 应用生命周期管理
    4. 应用实例追踪
    5. 提供系统 API
    """

    def __init__(self):
        # 已注册应用
        self._registered_apps: Dict[str, AppInfo] = {}

        # 运行中的应用实例
        self._running_apps: Dict[str, Any] = {}  # app_id -> instance

        # 应用状态
        self._app_states: Dict[str, AppState] = {}

        # 回调
        self._on_app_registered: Optional[Callable] = None
        self._on_app_unregistered: Optional[Callable] = None
        self._on_app_started: Optional[Callable] = None
        self._on_app_stopped: Optional[Callable] = None

        # 加载已注册应用
        self._load_registered_apps()

    # --------------------------------------------------------------------------
    # 应用注册
    # --------------------------------------------------------------------------

    def register_app(self, app_info: AppInfo) -> bool:
        """
        注册应用

        Args:
            app_info: AppInfo 实例

        Returns:
            是否注册成功
        """
        if app_info.id in self._registered_apps:
            return False

        self._registered_apps[app_info.id] = app_info
        self._app_states[app_info.id] = AppState.STOPPED
        self._save_registered_apps()

        if self._on_app_registered:
            self._on_app_registered(app_info)

        return True

    def register_apps(self, apps: List[AppInfo]) -> int:
        """
        批量注册应用

        Returns:
            成功注册的数量
        """
        count = 0
        for app in apps:
            if self.register_app(app):
                count += 1
        return count

    def unregister_app(self, app_id: str) -> bool:
        """
        注销应用

        Args:
            app_id: 应用 ID

        Returns:
            是否成功
        """
        if app_id not in self._registered_apps:
            return False

        # 如果应用正在运行，先停止
        if self._app_states.get(app_id) == AppState.RUNNING:
            self.stop_app(app_id)

        app_info = self._registered_apps.pop(app_id)
        self._app_states.pop(app_id, None)
        self._save_registered_apps()

        if self._on_app_unregistered:
            self._on_app_unregistered(app_info)

        return True

    def get_app(self, app_id: str) -> Optional[AppInfo]:
        """获取已注册应用"""
        return self._registered_apps.get(app_id)

    def get_all_apps(self) -> List[AppInfo]:
        """获取所有已注册应用"""
        return list(self._registered_apps.values())

    def get_apps_by_category(self, category: str) -> List[AppInfo]:
        """按分类获取应用"""
        return [a for a in self._registered_apps.values() if a.category == category]

    def get_apps_by_desktop(self, desktop_index: int) -> List[AppInfo]:
        """按桌面获取应用"""
        return [a for a in self._registered_apps.values() if a.desktop_index == desktop_index]

    # --------------------------------------------------------------------------
    # 应用生命周期
    # --------------------------------------------------------------------------

    def start_app(self, app_id: str) -> Optional[Any]:
        """
        启动应用

        Args:
            app_id: 应用 ID

        Returns:
            应用实例，失败返回 None
        """
        app_info = self._registered_apps.get(app_id)
        if not app_info:
            return None

        if self._app_states.get(app_id) == AppState.RUNNING:
            return self._running_apps.get(app_id)

        # 更新状态
        self._app_states[app_id] = AppState.STARTING

        try:
            # 创建沙箱
            sandbox = AppSandbox(app_info)

            # 加载模块
            module = importlib.import_module(app_info.module)
            app_class = getattr(module, app_info.entry_point, None)

            if app_class is None:
                raise ImportError(f"Entry point {app_info.entry_point} not found")

            # 创建实例
            instance = app_class(sandbox=sandbox)

            # 设置系统 API
            instance.system = sandbox.get_system_api()

            # 保存实例
            self._running_apps[app_id] = instance
            self._app_states[app_id] = AppState.RUNNING

            if self._on_app_started:
                self._on_app_started(app_info, instance)

            return instance

        except Exception as e:
            logger.info(f"Failed to start app {app_id}: {e}")
            self._app_states[app_id] = AppState.STOPPED
            return None

    def stop_app(self, app_id: str) -> bool:
        """
        停止应用

        Args:
            app_id: 应用 ID

        Returns:
            是否成功
        """
        if app_id not in self._running_apps:
            return False

        self._app_states[app_id] = AppState.STOPPING

        try:
            instance = self._running_apps[app_id]

            # 调用清理方法
            if hasattr(instance, "cleanup"):
                instance.cleanup()
            elif hasattr(instance, "stop"):
                instance.stop()

            # 移除实例
            self._running_apps.pop(app_id)
            self._app_states[app_id] = AppState.STOPPED

            app_info = self._registered_apps.get(app_id)
            if app_info and self._on_app_stopped:
                self._on_app_stopped(app_info)

            return True

        except Exception as e:
            logger.info(f"Failed to stop app {app_id}: {e}")
            self._app_states[app_id] = AppState.STOPPED
            return False

    def pause_app(self, app_id: str) -> bool:
        """暂停应用"""
        if self._app_states.get(app_id) != AppState.RUNNING:
            return False

        instance = self._running_apps.get(app_id)
        if instance and hasattr(instance, "pause"):
            instance.pause()
            self._app_states[app_id] = AppState.PAUSED
            return True

        return False

    def resume_app(self, app_id: str) -> bool:
        """恢复应用"""
        if self._app_states.get(app_id) != AppState.PAUSED:
            return False

        instance = self._running_apps.get(app_id)
        if instance and hasattr(instance, "resume"):
            instance.resume()
            self._app_states[app_id] = AppState.RUNNING
            return True

        return False

    def get_app_state(self, app_id: str) -> AppState:
        """获取应用状态"""
        return self._app_states.get(app_id, AppState.STOPPED)

    def is_app_running(self, app_id: str) -> bool:
        """检查应用是否正在运行"""
        return self._app_states.get(app_id) == AppState.RUNNING

    def get_running_apps(self) -> List[AppInfo]:
        """获取所有运行中的应用"""
        return [
            self._registered_apps[app_id]
            for app_id, state in self._app_states.items()
            if state == AppState.RUNNING
        ]

    # --------------------------------------------------------------------------
    # 批量操作
    # --------------------------------------------------------------------------

    def start_all_apps(self):
        """启动所有应用"""
        for app_id in self._registered_apps:
            self.start_app(app_id)

    def stop_all_apps(self):
        """停止所有应用"""
        app_ids = list(self._running_apps.keys())
        for app_id in app_ids:
            self.stop_app(app_id)

    # --------------------------------------------------------------------------
    # 持久化
    # --------------------------------------------------------------------------

    def _get_registered_apps_file(self) -> Path:
        """获取已注册应用文件"""
        from . import _DATA_DIR
from core.logger import get_logger
logger = get_logger('desktop_environment.app_manager')

        return _DATA_DIR / "registered_apps.json"

    def _load_registered_apps(self):
        """加载已注册应用"""
        file = self._get_registered_apps_file()
        if file.exists():
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                    for app_data in data.get("apps", []):
                        app_info = AppInfo.from_dict(app_data)
                        self._registered_apps[app_info.id] = app_info
                        self._app_states[app_info.id] = AppState.STOPPED
            except Exception as e:
                logger.info(f"Failed to load registered apps: {e}")

    def _save_registered_apps(self):
        """保存已注册应用"""
        file = self._get_registered_apps_file()
        data = {
            "apps": [app.to_dict() for app in self._registered_apps.values()]
        }
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # 事件回调
    # --------------------------------------------------------------------------

    def set_on_app_registered(self, callback: Callable[[AppInfo], None]):
        """设置应用注册回调"""
        self._on_app_registered = callback

    def set_on_app_unregistered(self, callback: Callable[[AppInfo], None]):
        """设置应用注销回调"""
        self._on_app_unregistered = callback

    def set_on_app_started(self, callback: Callable[[AppInfo, Any], None]):
        """设置应用启动回调"""
        self._on_app_started = callback

    def set_on_app_stopped(self, callback: Callable[[AppInfo], None]):
        """设置应用停止回调"""
        self._on_app_stopped = callback

# ============================================================================
# 全局访问器
# ============================================================================

_app_manager_instance: Optional[AppManager] = None

def get_app_manager() -> AppManager:
    """获取全局 AppManager 实例"""
    global _app_manager_instance
    if _app_manager_instance is None:
        _app_manager_instance = AppManager()
    return _app_manager_instance