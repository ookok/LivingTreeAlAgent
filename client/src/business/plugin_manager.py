#!/usr/bin/env python3
"""
PluginManager - 插件管理系统
Phase 5 核心：插件生命周期、API扩展、沙箱隔离

Author: LivingTreeAI Team
Version: 1.0.0
"""

import hashlib
import importlib
import importlib.util
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
import threading


class PluginStatus(Enum):
    """插件状态"""
    UNLOADED = "unloaded"     # 未加载
    LOADING = "loading"       # 加载中
    LOADED = "loaded"         # 已加载
    ACTIVE = "active"        # 激活
    DISABLED = "disabled"     # 禁用
    ERROR = "error"          # 错误


class PermissionLevel(Enum):
    """权限级别"""
    NONE = 0          # 无权限
    READ = 1          # 只读
    WRITE = 2         # 读写
    EXECUTE = 3       # 执行
    ADMIN = 4         # 管理员


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    version: str
    author: str
    description: str
    status: PluginStatus = PluginStatus.UNLOADED
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    permission_level: PermissionLevel = PermissionLevel.NONE
    loaded_at: Optional[float] = None
    activated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginHook:
    """插件钩子"""
    name: str
    callback: Callable
    priority: int = 0


class PluginSandbox:
    """插件沙箱"""
    
    def __init__(self, plugin_id: str, permissions: List[str]):
        self._plugin_id = plugin_id
        self._permissions = set(permissions)
        self._allowed_modules: List[str] = []
        self._blocked_modules: List[str] = []
    
    def allow_module(self, module_name: str) -> None:
        """允许模块"""
        self._allowed_modules.append(module_name)
    
    def block_module(self, module_name: str) -> None:
        """阻止模块"""
        self._blocked_modules.append(module_name)
    
    def check_permission(self, action: str) -> bool:
        """检查权限"""
        return action in self._permissions
    
    def can_access_file(self, file_path: str) -> bool:
        """检查文件访问权限"""
        if "file:read" not in self._permissions and "file:write" not in self._permissions:
            return False
        return True
    
    def can_execute_code(self) -> bool:
        """检查代码执行权限"""
        return "execute" in self._permissions


@dataclass
class PluginMetrics:
    """插件指标"""
    plugin_id: str
    calls: int = 0
    errors: int = 0
    total_latency: float = 0.0
    last_call: Optional[float] = None
    
    @property
    def avg_latency(self) -> float:
        return self.total_latency / self.calls if self.calls > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        return self.errors / self.calls if self.calls > 0 else 0.0


class PluginManager:
    """
    插件管理系统
    
    核心功能：
    - 插件加载/卸载
    - 生命周期管理
    - 沙箱隔离
    - 钩子系统
    - API扩展
    - 权限控制
    """
    
    def __init__(self, plugin_dir: Optional[str] = None):
        """
        初始化插件管理器
        
        Args:
            plugin_dir: 插件目录
        """
        # 插件目录
        self._plugin_dir = plugin_dir or "./plugins"
        
        # 插件注册表
        self._plugins: Dict[str, PluginInfo] = {}
        self._plugin_instances: Dict[str, Any] = {}
        self._plugin_modules: Dict[str, Any] = {}
        
        # 沙箱
        self._sandboxes: Dict[str, PluginSandbox] = {}
        
        # 钩子
        self._hooks: Dict[str, List[PluginHook]] = defaultdict(list)
        
        # 指标
        self._metrics: Dict[str, PluginMetrics] = {}
        
        # 事件
        self._event_handlers: Dict[str, List[Callable]] = {
            "plugin_loaded": [],
            "plugin_activated": [],
            "plugin_deactivated": [],
            "plugin_unloaded": [],
            "plugin_error": [],
        }
        
        # 锁
        self._lock = threading.RLock()
    
    def register_plugin(self, plugin_info: PluginInfo) -> None:
        """
        注册插件
        
        Args:
            plugin_info: 插件信息
        """
        with self._lock:
            self._plugins[plugin_info.id] = plugin_info
            self._metrics[plugin_info.id] = PluginMetrics(plugin_id=plugin_info.id)
    
    def load_plugin(self, plugin_id: str) -> bool:
        """
        加载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        with self._lock:
            plugin_info = self._plugins.get(plugin_id)
            if not plugin_info:
                return False
            
            if plugin_info.status != PluginStatus.UNLOADED:
                return False
            
            plugin_info.status = PluginStatus.LOADING
            
            try:
                # 检查依赖
                for dep_id in plugin_info.dependencies:
                    if dep_id not in self._plugins:
                        raise ImportError(f"Missing dependency: {dep_id}")
                    if self._plugins[dep_id].status != PluginStatus.LOADED:
                        self.load_plugin(dep_id)
                
                # 创建沙箱
                sandbox = PluginSandbox(plugin_id, plugin_info.permissions)
                self._sandboxes[plugin_id] = sandbox
                
                # 加载插件模块
                plugin_path = os.path.join(self._plugin_dir, f"{plugin_id}.py")
                if os.path.exists(plugin_path):
                    spec = importlib.util.spec_from_file_location(plugin_id, plugin_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[plugin_id] = module
                        spec.loader.exec_module(module)
                        self._plugin_modules[plugin_id] = module
                
                plugin_info.status = PluginStatus.LOADED
                plugin_info.loaded_at = time.time()
                
                self._emit_event("plugin_loaded", {"plugin_id": plugin_id})
                return True
                
            except Exception as e:
                plugin_info.status = PluginStatus.ERROR
                self._emit_event("plugin_error", {"plugin_id": plugin_id, "error": str(e)})
                return False
    
    def activate_plugin(self, plugin_id: str) -> bool:
        """
        激活插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        with self._lock:
            plugin_info = self._plugins.get(plugin_id)
            if not plugin_info or plugin_info.status != PluginStatus.LOADED:
                return False
            
            try:
                # 调用激活钩子
                module = self._plugin_modules.get(plugin_id)
                if module and hasattr(module, "on_activate"):
                    module.on_activate()
                
                plugin_info.status = PluginStatus.ACTIVE
                plugin_info.activated_at = time.time()
                
                self._emit_event("plugin_activated", {"plugin_id": plugin_id})
                return True
                
            except Exception as e:
                self._emit_event("plugin_error", {"plugin_id": plugin_id, "error": str(e)})
                return False
    
    def deactivate_plugin(self, plugin_id: str) -> bool:
        """
        停用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        with self._lock:
            plugin_info = self._plugins.get(plugin_id)
            if not plugin_info or plugin_info.status != PluginStatus.ACTIVE:
                return False
            
            try:
                # 调用停用钩子
                module = self._plugin_modules.get(plugin_id)
                if module and hasattr(module, "on_deactivate"):
                    module.on_deactivate()
                
                plugin_info.status = PluginStatus.LOADED
                
                self._emit_event("plugin_deactivated", {"plugin_id": plugin_id})
                return True
                
            except Exception as e:
                self._emit_event("plugin_error", {"plugin_id": plugin_id, "error": str(e)})
                return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否成功
        """
        with self._lock:
            plugin_info = self._plugins.get(plugin_id)
            if not plugin_info:
                return False
            
            # 先停用
            if plugin_info.status == PluginStatus.ACTIVE:
                self.deactivate_plugin(plugin_id)
            
            # 清理
            if plugin_id in self._plugin_modules:
                del self._plugin_modules[plugin_id]
            if plugin_id in self._sandboxes:
                del self._sandboxes[plugin_id]
            
            plugin_info.status = PluginStatus.UNLOADED
            
            self._emit_event("plugin_unloaded", {"plugin_id": plugin_id})
            return True
    
    def register_hook(self, hook_name: str, plugin_id: str, callback: Callable, priority: int = 0) -> None:
        """
        注册钩子
        
        Args:
            hook_name: 钩子名称
            plugin_id: 插件ID
            callback: 回调函数
            priority: 优先级
        """
        with self._lock:
            hook = PluginHook(name=hook_name, callback=callback, priority=priority)
            self._hooks[hook_name].append(hook)
            self._hooks[hook_name].sort(key=lambda h: h.priority, reverse=True)
    
    def call_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        调用钩子
        
        Args:
            hook_name: 钩子名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            钩子返回值列表
        """
        results = []
        
        for hook in self._hooks.get(hook_name, []):
            try:
                result = hook.callback(*args, **kwargs)
                results.append(result)
                
                # 记录指标
                metrics = self._metrics.get(hook.name.split(":")[0])
                if metrics:
                    metrics.calls += 1
                    metrics.last_call = time.time()
                    
            except Exception as e:
                results.append(None)
                
                # 记录错误
                metrics = self._metrics.get(hook.name.split(":")[0])
                if metrics:
                    metrics.errors += 1
        
        return results
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        with self._lock:
            return self._plugins.get(plugin_id)
    
    def list_plugins(self, status: Optional[PluginStatus] = None) -> List[PluginInfo]:
        """
        列出插件
        
        Args:
            status: 过滤状态
            
        Returns:
            插件列表
        """
        with self._lock:
            if status:
                return [p for p in self._plugins.values() if p.status == status]
            return list(self._plugins.values())
    
    def get_metrics(self, plugin_id: str) -> Optional[PluginMetrics]:
        """获取插件指标"""
        with self._lock:
            return self._metrics.get(plugin_id)
    
    def get_all_metrics(self) -> Dict[str, PluginMetrics]:
        """获取所有指标"""
        with self._lock:
            return dict(self._metrics)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发事件"""
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                pass
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """注册事件处理"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)
    
    def create_plugin_package(self, plugin_id: str, output_dir: str) -> str:
        """
        创建插件包
        
        Args:
            plugin_id: 插件ID
            output_dir: 输出目录
            
        Returns:
            包文件路径
        """
        import zipfile
        
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        package_path = os.path.join(output_dir, f"{plugin_id}.zip")
        
        with zipfile.ZipFile(package_path, 'w') as zf:
            # 添加插件信息
            info_json = json.dumps(plugin_info.__dict__, indent=2)
            zf.writestr("plugin.json", info_json)
            
            # 添加插件代码
            plugin_path = os.path.join(self._plugin_dir, f"{plugin_id}.py")
            if os.path.exists(plugin_path):
                zf.write(plugin_path, "plugin.py")
        
        return package_path
    
    def install_plugin_package(self, package_path: str) -> bool:
        """
        安装插件包
        
        Args:
            package_path: 包文件路径
            
        Returns:
            是否成功
        """
        import zipfile
        
        try:
            with zipfile.ZipFile(package_path, 'r') as zf:
                # 读取插件信息
                info_json = zf.read("plugin.json")
                info_dict = json.loads(info_json)
                
                plugin_info = PluginInfo(**info_dict)
                
                # 注册插件
                self.register_plugin(plugin_info)
                
                # 提取代码
                if "plugin.py" in zf.namelist():
                    plugin_py = zf.read("plugin.py")
                    os.makedirs(self._plugin_dir, exist_ok=True)
                    with open(os.path.join(self._plugin_dir, f"{plugin_info.id}.py"), "wb") as f:
                        f.write(plugin_py)
                
                return True
                
        except Exception:
            return False


# 全局管理器实例
_global_manager: Optional[PluginManager] = None
_manager_lock = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器"""
    global _global_manager
    
    with _manager_lock:
        if _global_manager is None:
            _global_manager = PluginManager()
        return _global_manager


# 便捷函数
def register_plugin(
    plugin_id: str,
    name: str,
    version: str,
    author: str = "Unknown",
    description: str = "",
) -> PluginInfo:
    """注册插件"""
    info = PluginInfo(
        id=plugin_id,
        name=name,
        version=version,
        author=author,
        description=description,
    )
    get_plugin_manager().register_plugin(info)
    return info


def install_plugin(package_path: str) -> bool:
    """安装插件"""
    return get_plugin_manager().install_plugin_package(package_path)
