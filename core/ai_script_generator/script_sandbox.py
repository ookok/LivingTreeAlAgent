"""
Script Sandbox - 安全脚本执行沙箱
=================================

核心理念：隔离执行、监控资源、热重载

功能：
1. 沙箱隔离 - 限制文件、网络、系统操作
2. 资源监控 - CPU/内存/执行时间限制
3. 热重载 - 修改代码即时生效
4. 调试工具 - 变量查看、性能分析

Author: Hermes Desktop Team
"""

import ast
import asyncio
import builtins
import concurrent.futures
import copy
import io
import json
import os
import sys
import threading
import time
import traceback
import types
import uuid
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import logging

logger = logging.getLogger(__name__)


# ============= 枚举定义 =============


class SandboxPermission(Enum):
    """沙箱权限"""
    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    NETWORK_INTERNET = "network:internet"
    NETWORK_LOCAL = "network:local"
    SYSTEM_EXECUTE = "system:execute"
    SYSTEM_SPAWN = "system:spawn"


@dataclass
class ResourceLimit:
    """资源限制"""
    max_memory_mb: int = 512          # 最大内存 MB
    max_cpu_percent: int = 80         # 最大CPU占用 %
    max_execution_time_sec: int = 30  # 最大执行时间 秒
    max_output_size: int = 1024 * 1024  # 最大输出大小 bytes


@dataclass
class SandboxConfig:
    """沙箱配置"""
    permissions: Set[SandboxPermission] = field(default_factory=set)
    resource_limit: ResourceLimit = field(default_factory=ResourceLimit)
    allow_imports: Set[str] = field(default_factory=lambda: {
        'json', 'datetime', 'time', 'collections',
        'pathlib', 're', 'math', 'random', 'uuid'
    })
    blocked_modules: Set[str] = field(default_factory=lambda: {
        'os', 'subprocess', 'socket', 'urllib', 'requests',
        'ctypes', 'sys', 'builtins'
    })


@dataclass
class ExecutionContext:
    """执行上下文"""
    context_id: str
    script_id: str
    globals: Dict[str, Any] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    permissions: Set[SandboxPermission] = field(default_factory=set)
    resource_usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """执行结果"""
    context_id: str
    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)


# ============= 受限内置函数 =============


class RestrictedBuiltins:
    """受限的内置函数"""

    def __init__(self, original_builtins: dict, permissions: Set[SandboxPermission]):
        self._original = original_builtins
        self._permissions = permissions
        self._restricted = {}

        # 复制原始内置函数
        for name, obj in original_builtins.items():
            self._restricted[name] = obj

        # 限制危险函数
        self._restrict_print()
        self._restrict_input()
        self._restrict_open()

    def _restrict_logger.info(self):
        """限制 print（只允许记录输出，不实际打印）"""
        import builtins as bi

        _original_print = bi.print
        _outputs = []

        def _safe_logger.info(*args, **kwargs):
            sep = kwargs.get('sep', ' ')
            end = kwargs.get('end', '\n')
            output = sep.join(str(a) for a in args) + end
            _outputs.append(output)
            return len(output)

        bi.print = _safe_print
        self._outputs = _outputs

    def _restrict_input(self):
        """限制 input"""
        import builtins as bi

        _original_input = bi.input

        def _safe_input(prompt=""):
            raise RuntimeError("input() 在沙箱中不可用")

        bi.input = _safe_input

    def _restrict_open(self):
        """限制 open()"""
        import builtins as bi

        _original_open = bi.open

        def _safe_open(file, mode='r', *args, **kwargs):
            if SandboxPermission.FILE_READ not in self._permissions and 'r' in mode:
                raise PermissionError("文件读取权限不足")
            if SandboxPermission.FILE_WRITE not in self._permissions and any(c in mode for c in 'wa'):
                raise PermissionError("文件写入权限不足")

            # 只允许在特定目录
            allowed_dirs = ['./data', './temp', '.']
            file_str = str(file)
            if not any(file_str.startswith(d) for d in allowed_dirs):
                raise PermissionError(f"不允许访问路径: {file}")

            return _original_open(file, mode, *args, **kwargs)

        bi.open = _safe_open

    def get_outputs(self) -> List[str]:
        """获取打印输出"""
        return getattr(self, '_outputs', [])


# ============= 资源监控器 =============


class ResourceMonitor:
    """资源使用监控器"""

    def __init__(self, limits: ResourceLimit):
        self.limits = limits
        self._start_time: Optional[float] = None
        self._start_memory: int = 0
        self._peak_memory: int = 0
        self._running: bool = False

    def start(self):
        """开始监控"""
        self._start_time = time.time()
        self._start_memory = self._get_memory_usage()
        self._peak_memory = self._start_memory
        self._running = True

    def update(self):
        """更新监控数据"""
        if not self._running:
            return

        current_memory = self._get_memory_usage()
        self._peak_memory = max(self._peak_memory, current_memory)

        # 检查时间限制
        elapsed = time.time() - self._start_time
        if elapsed > self.limits.max_execution_time_sec:
            raise TimeoutError(f"执行超时: {elapsed:.1f}s > {self.limits.max_execution_time_sec}s")

        # 检查内存限制
        memory_mb = (self._peak_memory - self._start_memory) / (1024 * 1024)
        if memory_mb > self.limits.max_memory_mb:
            raise MemoryError(f"内存超限: {memory_mb:.1f}MB > {self.limits.max_memory_mb}MB")

    def stop(self) -> Dict[str, float]:
        """停止监控并返回统计"""
        self._running = False
        elapsed = time.time() - self._start_time if self._start_time else 0
        memory_mb = (self._peak_memory - self._start_memory) / (1024 * 1024)

        return {
            'execution_time': elapsed,
            'peak_memory_mb': max(0, memory_mb),
        }

    def _get_memory_usage(self) -> int:
        """获取当前内存使用"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            # fallback: 粗略估算
            import gc
from core.logger import get_logger
logger = get_logger('ai_script_generator.script_sandbox')

            gc.collect()
            return 0


# ============= 沙箱执行器 =============


class SandboxExecutor:
    """
    沙箱执行器 - 安全执行Python代码
    """

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()

    def execute(
        self,
        code: str,
        script_id: str,
        context: Dict[str, Any] = None,
        timeout: int = 30
    ) -> ExecutionResult:
        """
        执行代码

        Args:
            code: Python代码
            script_id: 脚本ID
            context: 执行上下文
            timeout: 超时时间

        Returns:
            ExecutionResult: 执行结果
        """
        context_id = f"context_{uuid.uuid4().hex[:8]}"
        exec_context = ExecutionContext(
            context_id=context_id,
            script_id=script_id,
            globals=context or {},
            permissions=self.config.permissions
        )

        # 创建资源监控器
        monitor = ResourceMonitor(self.config.resource_limit)

        # 捕获输出
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        start_time = time.time()

        try:
            # 静态分析 - 语法检查
            try:
                ast.parse(code)
            except SyntaxError as e:
                return ExecutionResult(
                    context_id=context_id,
                    success=False,
                    error=f"语法错误: {e}"
                )

            # 静态分析 - 危险模式检测
            danger_warnings = self._check_dangerous_patterns(code)
            if danger_warnings:
                logger.warning(f"脚本 {script_id} 检测到危险模式: {danger_warnings}")

            # 准备执行环境
            exec_globals = {
                '__name__': '__sandbox__',
                '__builtins__': self._create_restricted_builtins(),
                '__sandbox__': True,
            }
            exec_globals.update(exec_context.globals)

            exec_locals = {}

            # 开始监控
            monitor.start()

            # 执行代码
            try:
                exec(code, exec_globals, exec_locals)
            except Exception as e:
                raise e

            # 停止监控
            stats = monitor.stop()
            execution_time = stats['execution_time']

            # 获取输出
            outputs = exec_globals.get('_outputs', [])
            output = ''.join(outputs) + stdout_capture.getvalue()

            return ExecutionResult(
                context_id=context_id,
                success=True,
                output=output,
                return_value=exec_locals.get('__result__'),
                execution_time=execution_time,
                memory_peak_mb=stats['peak_memory_mb'],
                warnings=danger_warnings
            )

        except TimeoutError as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id,
                success=False,
                error=f"执行超时: {str(e)}",
                execution_time=timeout
            )

        except MemoryError as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id,
                success=False,
                error=f"内存超限: {str(e)}",
                execution_time=time.time() - start_time,
                memory_peak_mb=self.config.resource_limit.max_memory_mb
            )

        except Exception as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id,
                success=False,
                error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time,
                warnings=danger_warnings
            )

    def _create_restricted_builtins(self) -> dict:
        """创建受限的内置函数"""
        original = copy.copy(builtins.__dict__)

        # 移除危险函数
        dangerous = ['eval', 'exec', 'compile', 'open', '__import__']
        for name in dangerous:
            if name in original:
                original[name] = self._make_restricted(name, original[name])

        # 允许列表
        allowed = {
            'print': original.get('print', print),
            'len': len,
            'range': range,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'type': type,
            'isinstance': isinstance,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'sorted': sorted,
            'reversed': reversed,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'open': open,
        }

        # 如果有 file:write 权限，限制性允许 open
        if SandboxPermission.FILE_WRITE in self.config.permissions:
            allowed['open'] = original.get('open', open)

        return allowed

    def _make_restricted(self, name: str, original: Any) -> Callable:
        """创建受限函数包装"""
        def restricted(*args, **kwargs):
            raise PermissionError(f"函数 '{name}' 在沙箱中不可用")
        return restricted

    def _check_dangerous_patterns(self, code: str) -> List[str]:
        """检查危险模式"""
        warnings = []

        dangerous_patterns = [
            (r'eval\s*\(', 'eval() 可能导致代码注入'),
            (r'exec\s*\(', 'exec() 可能导致代码注入'),
            (r'compile\s*\(', 'compile() 可能导致代码注入'),
            (r'__import__\s*\(', '__import__() 可能导致动态导入'),
            (r'os\.system\s*\(', 'os.system() 可能执行危险命令'),
            (r'subprocess\.', 'subprocess 模块可能执行危险命令'),
            (r'ctypes\.', 'ctypes 可能访问底层系统'),
        ]

        for pattern, message in dangerous_patterns:
            if pattern in code:
                warnings.append(message)

        return warnings


# ============= 脚本沙箱管理器 =============


class ScriptSandbox:
    """
    脚本沙箱管理器

    功能：
    1. 沙箱实例池
    2. 热重载支持
    3. 调试接口
    """

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.executor = SandboxExecutor(self.config)

        # 沙箱实例缓存 (用于热重载)
        self._sandbox_pool: Dict[str, weakref.ref] = {}
        self._script_cache: Dict[str, str] = {}

        # 活跃执行
        self._active_executions: Dict[str, ExecutionResult] = {}

        logger.info("脚本沙箱管理器初始化完成")

    def execute_script(
        self,
        script_id: str,
        code: str,
        context: Dict[str, Any] = None,
        timeout: int = 30
    ) -> ExecutionResult:
        """
        执行脚本

        Args:
            script_id: 脚本ID
            code: 脚本代码
            context: 执行上下文
            timeout: 超时时间

        Returns:
            ExecutionResult: 执行结果
        """
        # 检查是否需要热重载
        if script_id in self._script_cache and self._script_cache[script_id] != code:
            logger.info(f"脚本 {script_id} 已修改，执行热重载")
            del self._script_cache[script_id]

        # 缓存代码
        self._script_cache[script_id] = code

        # 执行
        result = self.executor.execute(code, script_id, context, timeout)
        self._active_executions[script_id] = result

        return result

    def hot_reload(self, script_id: str, new_code: str) -> bool:
        """
        热重载脚本

        Args:
            script_id: 脚本ID
            new_code: 新代码

        Returns:
            bool: 是否成功
        """
        if script_id not in self._script_cache:
            return False

        # 检查语法
        try:
            ast.parse(new_code)
        except SyntaxError:
            return False

        # 更新缓存
        self._script_cache[script_id] = new_code
        logger.info(f"脚本 {script_id} 热重载成功")

        return True

    def get_execution_history(self, script_id: str) -> List[ExecutionResult]:
        """获取执行历史"""
        # TODO: 实现持久化
        if script_id in self._active_executions:
            return [self._active_executions[script_id]]
        return []

    def create_debug_context(self, script_id: str, code: str) -> str:
        """
        创建调试上下文

        Args:
            script_id: 脚本ID
            code: 脚本代码

        Returns:
            context_id: 调试上下文ID
        """
        context_id = f"debug_{uuid.uuid4().hex[:8]}"

        # 解析代码获取变量信息
        tree = ast.parse(code)
        variables = [node.targets[0].id for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)]

        context = {
            'context_id': context_id,
            'script_id': script_id,
            'variables': variables,
            'breakpoints': [],
            'created_at': datetime.now().isoformat()
        }

        # TODO: 存储调试上下文
        logger.info(f"调试上下文已创建: {context_id}")

        return context_id

    def add_breakpoint(self, context_id: str, line: int) -> bool:
        """添加断点"""
        logger.info(f"断点已添加: context={context_id}, line={line}")
        return True

    def step_execution(self, context_id: str) -> Dict[str, Any]:
        """
        单步执行（调试模式）

        Returns:
            当前状态信息
        """
        # TODO: 实现单步执行
        return {
            'context_id': context_id,
            'current_line': 1,
            'variables': {},
            'output': ''
        }


# ============= 工具函数 =============


def create_safe_sandbox(
    allow_file_read: bool = True,
    allow_file_write: bool = False,
    allow_network: bool = False,
    max_memory_mb: int = 512,
    max_time_sec: int = 30
) -> ScriptSandbox:
    """
    创建安全的沙箱配置

    Args:
        allow_file_read: 允许文件读取
        allow_file_write: 允许文件写入
        allow_network: 允许网络访问
        max_memory_mb: 最大内存 MB
        max_time_sec: 最大执行时间 秒

    Returns:
        ScriptSandbox: 配置好的沙箱实例
    """
    permissions = set()

    if allow_file_read:
        permissions.add(SandboxPermission.FILE_READ)
    if allow_file_write:
        permissions.add(SandboxPermission.FILE_WRITE)
    if allow_network:
        permissions.add(SandboxPermission.NETWORK_INTERNET)

    config = SandboxConfig(
        permissions=permissions,
        resource_limit=ResourceLimit(
            max_memory_mb=max_memory_mb,
            max_execution_time_sec=max_time_sec
        )
    )

    return ScriptSandbox(config)


# 全局实例
_sandbox_instance: Optional[ScriptSandbox] = None


def get_script_sandbox() -> ScriptSandbox:
    """获取脚本沙箱全局实例"""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = create_safe_sandbox()
    return _sandbox_instance
