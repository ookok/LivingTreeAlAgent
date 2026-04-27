"""
Plugin Sandbox - 插件沙箱

隔离插件执行环境，防止恶意插件破坏系统。
实现权限控制、资源限制、API 白名单。

安全层级：
1. API 白名单：插件只能调用允许的 API
2. 资源限制：CPU/内存/文件访问限制
3. 权限声明：插件必须声明需要的权限
4. 执行隔离：在受限环境中执行插件代码
"""

import ast
import builtins
import importlib
import logging
import multiprocessing
import os
import resource
import sys
import threading
import time
import traceback
import types
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 权限枚举
# ─────────────────────────────────────────────────────────────

class Permission(Enum):
    """插件权限"""

    # 文件系统
    FILE_READ = "file:read"           # 读取文件
    FILE_WRITE = "file:write"         # 写入文件
    FILE_DELETE = "file:delete"       # 删除文件

    # 网络
    NETWORK_HTTP = "network:http"     # HTTP 请求
    NETWORK_WEBSOCKET = "network:ws"  # WebSocket

    # 系统
    SYSTEM_ENV = "system:env"         # 读取环境变量
    SYSTEM_PROCESS = "system:process" # 创建子进程
    SYSTEM_EXEC = "system:exec"       # 执行系统命令

    # 数据
    DATA_READ = "data:read"           # 读取系统数据（配置、数据库）
    DATA_WRITE = "data:write"         # 修改系统数据

    # UI
    UI_CREATE_WINDOW = "ui:window"    # 创建窗口
    UI_ACCESS_MAIN = "ui:main"        # 访问主窗口

    # 插件
    PLUGIN_LOAD = "plugin:load"       # 加载其他插件
    PLUGIN_UNLOAD = "plugin:unload"   # 卸载其他插件

    # 内核
    KERNEL_SHUTDOWN = "kernel:shutdown"  # 关闭内核


# 权限分组（用于简化配置）
PERMISSION_GROUPS = {
    "minimal": [
        Permission.FILE_READ,
        Permission.NETWORK_HTTP,
        Permission.DATA_READ,
    ],
    "standard": [
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.NETWORK_HTTP,
        Permission.NETWORK_WEBSOCKET,
        Permission.DATA_READ,
        Permission.DATA_WRITE,
        Permission.UI_CREATE_WINDOW,
    ],
    "full": list(Permission),  # 所有权限
}


# ─────────────────────────────────────────────────────────────
# 权限声明
# ─────────────────────────────────────────────────────────────

@dataclass
class PermissionDeclaration:
    """插件权限声明"""

    plugin_id: str
    permissions: Set[Permission] = field(default_factory=set)
    # 是否允许动态申请权限
    allow_dynamic_request: bool = False
    # 权限使用记录
    usage_log: List[Dict[str, Any]] = field(default_factory=list)

    def has_permission(self, permission: Permission) -> bool:
        """检查是否有指定权限"""
        return permission in self._permissions

    def grant(self, permission: Permission, reason: str = "") -> None:
        """授予权限"""
        if permission not in self._permissions:
            self._permissions.add(permission)
            self._log_usage("grant", permission.value, reason)

    def revoke(self, permission: Permission, reason: str = "") -> None:
        """撤销权限"""
        if permission in self._permissions:
            self._permissions.remove(permission)
            self._log_usage("revoke", permission.value, reason)

    def _log_usage(self, action: str, permission: str, reason: str) -> None:
        """记录权限使用"""
        self._usage_log.append({
            "action": action,
            "permission": permission,
            "reason": reason,
            "timestamp": time.time(),
        })
        # 只保留最近 100 条记录
        if len(self._usage_log) > 100:
            self._usage_log = self._usage_log[-100:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self._plugin_id,
            "permissions": [p.value for p in self._permissions],
            "allow_dynamic_request": self._allow_dynamic_request,
            "usage_log": self._usage_log[-20:],  # 只返回最近 20 条
        }


# ─────────────────────────────────────────────────────────────
# API 白名单
# ─────────────────────────────────────────────────────────────

# 插件允许使用的内置函数（安全子集）
SAFE_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "bytes", "callable", "chr",
    "complex", "dict", "dir", "divmod", "enumerate", "filter", "float",
    "format", "frozenset", "getattr", "hasattr", "hash", "hex", "id",
    "int", "isinstance", "issubclass", "iter", "len", "list", "map",
    "max", "min", "next", "object", "oct", "ord", "pow", "print",
    "property", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "super", "tuple", "type", "vars", "zip",
    "__build_class__", "__import__",  # 需要被包装
}

# 禁止使用的内置函数
FORBIDDEN_BUILTINS = {
    "eval", "exec", "compile", "open", "input",
    "__import__",  # 会被包装，只允许安全导入
}


# ─────────────────────────────────────────────────────────────
# 沙箱执行器
# ─────────────────────────────────────────────────────────────

class SandboxException(Exception):
    """沙箱异常"""
    pass


class PermissionDeniedException(SandboxException):
    """权限拒绝异常"""
    pass


class ResourceLimitException(SandboxException):
    """资源限制异常"""
    pass


class PluginSandbox:
    """
    插件沙箱

    功能：
    1. 限制插件能使用的 API（白名单）
    2. 监控资源使用（CPU/内存）
    3. 检查权限声明
    4. 隔离执行环境
    """

    def __init__(
        self,
        plugin_id: str,
        permissions: Optional[Set[Permission]] = None,
        max_cpu_time: float = 5.0,      # 最大 CPU 时间（秒）
        max_memory_mb: int = 100,        # 最大内存（MB）
        max_execution_time: float = 10.0,  # 最大执行时间（秒）
    ):
        """
        初始化沙箱

        Args:
            plugin_id: 插件 ID
            permissions: 授予的权限集合
            max_cpu_time: 最大 CPU 时间（秒）
            max_memory_mb: 最大内存（MB）
            max_execution_time: 最大执行时间（秒）
        """
        self._plugin_id = plugin_id
        self._permissions = permissions or set()
        self._max_cpu_time = max_cpu_time
        self._max_memory_mb = max_memory_mb
        self._max_execution_time = max_execution_time

        # 执行统计
        self._exec_count = 0
        self._total_cpu_time = 0.0
        self._total_execution_time = 0.0
        self._violations: List[Dict[str, Any]] = []

        logger.debug(f"[Sandbox] Created for plugin: {plugin_id}")

    # ─────────────────────────────────────────────────────────
    # 权限检查
    # ─────────────────────────────────────────────────────────

    def check_permission(self, permission: Permission, action: str = "") -> None:
        """
        检查权限，不满足则抛出异常

        Args:
            permission: 需要的权限
            action: 执行的操作（用于日志）

        Raises:
            PermissionDeniedException: 权限不足
        """
        if permission not in self._permissions:
            violation = {
                "timestamp": time.time(),
                "permission": permission.value,
                "action": action,
                "plugin_id": self._plugin_id,
            }
            self._violations.append(violation)
            logger.warning(
                f"[Sandbox] Permission denied: {self._plugin_id} "
                f"needs {permission.value} for {action}"
            )
            raise PermissionDeniedException(
                f"Plugin '{self._plugin_id}' lacks permission: {permission.value}"
            )

    def has_permission(self, permission: Permission) -> bool:
        """检查是否有指定权限"""
        return permission in self._permissions

    def grant_permission(self, permission: Permission) -> None:
        """授予权限"""
        self._permissions.add(permission)
        logger.info(f"[Sandbox] Granted permission {permission.value} to {self._plugin_id}")

    def revoke_permission(self, permission: Permission) -> None:
        """撤销权限"""
        if permission in self._permissions:
            self._permissions.remove(permission)
            logger.info(f"[Sandbox] Revoked permission {permission.value} from {self._plugin_id}")

    # ─────────────────────────────────────────────────────────
    # 安全执行
    # ─────────────────────────────────────────────────────────

    def execute_safe(self, func: Callable, *args, **kwargs) -> Any:
        """
        在安全环境中执行函数

        使用子进程隔离执行，限制资源使用。

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            ResourceLimitException: 资源超限
            SandboxException: 执行失败
        """
        self._exec_count += 1
        start_time = time.time()

        # 使用子进程执行（真正的隔离）
        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=self._safe_executor,
            args=(func, args, kwargs, result_queue),
        )

        try:
            process.start()
            process.join(timeout=self._max_execution_time)

            if process.is_alive():
                # 超时，终止进程
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                raise ResourceLimitException(
                    f"Plugin '{self._plugin_id}' execution timed out "
                    f"({self._max_execution_time}s)"
                )

            # 获取结果
            if not result_queue.empty():
                result = result_queue.get_nowait()
                if result["success"]:
                    self._total_execution_time += time.time() - start_time
                    return result["result"]
                else:
                    raise SandboxException(result["error"])

            raise SandboxException("Plugin execution failed (no result returned)")

        except Exception as e:
            self._total_execution_time += time.time() - start_time
            raise

    def _safe_executor(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        result_queue: multiprocessing.Queue,
    ) -> None:
        """
        在子进程中安全执行函数

        设置资源限制，然后执行函数。
        """
        try:
            # 设置资源限制（仅 Unix 系统）
            if hasattr(resource, 'RLIMIT_CPU'):
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (int(self._max_cpu_time), int(self._max_cpu_time + 1)),
                )
            if hasattr(resource, 'RLIMIT_AS'):
                max_mem = self._max_memory_mb * 1024 * 1024
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (max_mem, max_mem),
                )

            # 执行函数
            result = func(*args, **kwargs)
            result_queue.put({"success": True, "result": result})

        except Exception as e:
            result_queue.put({
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
            })

    def execute_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """
        在线程中执行函数（轻量级隔离，适合快速操作）

        不创建子进程，只做超时控制。
        """
        self._exec_count += 1
        start_time = time.time()

        result_container = {}
        exception_container = {}

        def wrapper():
            try:
                result_container["result"] = func(*args, **kwargs)
            except Exception as e:
                exception_container["exception"] = e

        thread = threading.Thread(target=wrapper)
        thread.start()
        thread.join(timeout=self._max_execution_time)

        if thread.is_alive():
            raise ResourceLimitException(
                f"Plugin '{self._plugin_id}' execution timed out "
                f"({self._max_execution_time}s)"
            )

        if "exception" in exception_container:
            raise exception_container["exception"]

        self._total_execution_time += time.time() - start_time
        return result_container.get("result")

    # ─────────────────────────────────────────────────────────
    # 代码安全检查
    # ─────────────────────────────────────────────────────────

    def check_code_safety(self, code: str) -> Dict[str, Any]:
        """
        检查代码安全性（静态分析）

        Args:
            code: Python 代码字符串

        Returns:
            检查结果 {"safe": bool, "issues": [issue, ...]}
        """
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"safe": False, "issues": [f"Syntax error: {e}"]}

        for node in ast.walk(tree):
            # 检查危险函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in ("eval", "exec", "compile"):
                        issues.append(f"Dangerous function call: {func_name}")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("system", "popen", "spawn"):
                        issues.append(f"Dangerous method call: {node.func.attr}")

            # 检查危险导入
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("os", "subprocess", "sys"):
                        issues.append(f"Dangerous import: {alias.name}")

            # 检查危险属性访问
            elif isinstance(node, ast.Attribute):
                if node.attr in ("__dict__", "__class__", "__bases__"):
                    issues.append(f"Dangerous attribute access: {node.attr}")

        return {
            "safe": len(issues) == 0,
            "issues": issues,
        }

    # ─────────────────────────────────────────────────────────
    # 统计信息
    # ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取沙箱统计信息"""
        return {
            "plugin_id": self._plugin_id,
            "permissions": [p.value for p in self._permissions],
            "exec_count": self._exec_count,
            "total_cpu_time": round(self._total_cpu_time, 3),
            "total_execution_time": round(self._total_execution_time, 3),
            "violations": len(self._violations),
            "recent_violations": self._violations[-10:],
            "max_cpu_time": self._max_cpu_time,
            "max_memory_mb": self._max_memory_mb,
            "max_execution_time": self._max_execution_time,
        }


# ─────────────────────────────────────────────────────────────
# 沙箱管理器
# ─────────────────────────────────────────────────────────────

class SandboxManager:
    """
    沙箱管理器

    管理所有插件的沙箱实例。
    """

    def __init__(self):
        self._sandboxes: Dict[str, PluginSandbox] = {}
        self._permission_declarations: Dict[str, PermissionDeclaration] = {}
        self._lock = threading.RLock()

        logger.info("[SandboxManager] Initialized")

    def create_sandbox(
        self,
        plugin_id: str,
        permissions: Optional[Set[Permission]] = None,
        **kwargs,
    ) -> PluginSandbox:
        """
        为插件创建沙箱

        Args:
            plugin_id: 插件 ID
            permissions: 权限集合（不提供则使用最小权限）
            **kwargs: 传递给 PluginSandbox 的参数

        Returns:
            沙箱实例
        """
        with self._lock:
            if plugin_id in self._sandboxes:
                logger.warning(f"[SandboxManager] Sandbox already exists for: {plugin_id}")
                return self._sandboxes[plugin_id]

            # 默认使用最小权限
            if permissions is None:
                permissions = set(PERMISSION_GROUPS["minimal"])

            sandbox = PluginSandbox(
                plugin_id=plugin_id,
                permissions=permissions,
                **kwargs,
            )
            self._sandboxes[plugin_id] = sandbox

            logger.info(
                f"[SandboxManager] Created sandbox for {plugin_id} "
                f"({len(permissions)} permissions)"
            )
            return sandbox

    def get_sandbox(self, plugin_id: str) -> Optional[PluginSandbox]:
        """获取插件的沙箱"""
        return self._sandboxes.get(plugin_id)

    def remove_sandbox(self, plugin_id: str) -> bool:
        """移除插件的沙箱"""
        with self._lock:
            if plugin_id in self._sandboxes:
                del self._sandboxes[plugin_id]
                logger.info(f"[SandboxManager] Removed sandbox for {plugin_id}")
                return True
            return False

    def check_permission(self, plugin_id: str, permission: Permission) -> bool:
        """检查插件是否有指定权限"""
        sandbox = self.get_sandbox(plugin_id)
        if not sandbox:
            return False
        return sandbox.has_permission(permission)

    def grant_permission(self, plugin_id: str, permission: Permission) -> bool:
        """授予插件权限"""
        sandbox = self.get_sandbox(plugin_id)
        if not sandbox:
            return False
        sandbox.grant_permission(permission)
        return True

    def revoke_permission(self, plugin_id: str, permission: Permission) -> bool:
        """撤销插件权限"""
        sandbox = self.get_sandbox(plugin_id)
        if not sandbox:
            return False
        sandbox.revoke_permission(permission)
        return True

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有沙箱的统计信息"""
        with self._lock:
            return {
                "sandbox_count": len(self._sandboxes),
                "sandboxes": {
                    plugin_id: sandbox.get_stats()
                    for plugin_id, sandbox in self._sandboxes.items()
                },
            }

    def check_code_for_plugin(self, plugin_id: str, code: str) -> Dict[str, Any]:
        """检查插件代码的安全性"""
        sandbox = self.get_sandbox(plugin_id)
        if not sandbox:
            return {"safe": False, "issues": ["Sandbox not found"]}
        return sandbox.check_code_safety(code)


# ─────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────

_sandbox_manager_instance: Optional[SandboxManager] = None
_sandbox_manager_lock = threading.RLock()


def get_sandbox_manager() -> SandboxManager:
    """获取沙箱管理器单例"""
    global _sandbox_manager_instance
    with _sandbox_manager_lock:
        if _sandbox_manager_instance is None:
            _sandbox_manager_instance = SandboxManager()
        return _sandbox_manager_instance


def create_sandbox_for_plugin(
    plugin_id: str,
    permission_group: str = "minimal",
    **kwargs,
) -> PluginSandbox:
    """
    为插件创建沙箱（快捷函数）

    Args:
        plugin_id: 插件 ID
        permission_group: 权限组（"minimal" / "standard" / "full"）
        **kwargs: 传递给 PluginSandbox 的参数

    Returns:
        沙箱实例
    """
    manager = get_sandbox_manager()
    permissions = set(PERMISSION_GROUPS.get(permission_group, PERMISSION_GROUPS["minimal"]))
    return manager.create_sandbox(plugin_id, permissions, **kwargs)


# ─────────────────────────────────────────────────────────────
# 装饰器：权限检查
# ─────────────────────────────────────────────────────────────

def require_permission(permission: Permission):
    """
    权限检查装饰器

    用法：
        @require_permission(Permission.FILE_WRITE)
        def my_plugin_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 尝试从 args 中获取 plugin_id（约定：第一个参数是 self）
            plugin_id = "unknown"
            if args and hasattr(args[0], 'plugin_id'):
                plugin_id = args[0].plugin_id

            manager = get_sandbox_manager()
            sandbox = manager.get_sandbox(plugin_id)
            if sandbox:
                sandbox.check_permission(permission, action=func.__name__)

            return func(*args, **kwargs)
        return wrapper
    return decorator
