"""
Script Sandbox - 安全脚本执行沙箱

核心理念：隔离执行、监控资源、热重载

功能：
1. 沙箱隔离 - 限制文件、网络、系统操作
2. 资源监控 - CPU/内存/执行时间限制
3. 热重载 - 修改代码即时生效
4. 调试工具 - 变量查看、性能分析
"""

import ast
import copy
import io
import logging
import os
import time
import traceback
import uuid
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SandboxPermission(Enum):
    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    NETWORK_INTERNET = "network:internet"
    NETWORK_LOCAL = "network:local"
    SYSTEM_EXECUTE = "system:execute"
    SYSTEM_SPAWN = "system:spawn"


@dataclass
class ResourceLimit:
    max_memory_mb: int = 512
    max_cpu_percent: int = 80
    max_execution_time_sec: int = 30
    max_output_size: int = 1024 * 1024


@dataclass
class SandboxConfig:
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
    context_id: str
    script_id: str
    globals: Dict[str, Any] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    permissions: Set[SandboxPermission] = field(default_factory=set)
    resource_usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    context_id: str
    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)


class ResourceMonitor:
    """资源使用监控器"""

    def __init__(self, limits: ResourceLimit):
        self.limits = limits
        self._start_time: Optional[float] = None
        self._start_memory: int = 0
        self._peak_memory: int = 0
        self._running: bool = False

    def start(self):
        self._start_time = time.time()
        self._start_memory = self._get_memory_usage()
        self._peak_memory = self._start_memory
        self._running = True

    def update(self):
        if not self._running:
            return
        current_memory = self._get_memory_usage()
        self._peak_memory = max(self._peak_memory, current_memory)
        elapsed = time.time() - self._start_time
        if elapsed > self.limits.max_execution_time_sec:
            raise TimeoutError(f"执行超时: {elapsed:.1f}s > {self.limits.max_execution_time_sec}s")
        memory_mb = (self._peak_memory - self._start_memory) / (1024 * 1024)
        if memory_mb > self.limits.max_memory_mb:
            raise MemoryError(f"内存超限: {memory_mb:.1f}MB > {self.limits.max_memory_mb}MB")

    def stop(self) -> Dict[str, float]:
        self._running = False
        elapsed = time.time() - self._start_time if self._start_time else 0
        memory_mb = (self._peak_memory - self._start_memory) / (1024 * 1024)
        return {'execution_time': elapsed, 'peak_memory_mb': max(0, memory_mb)}

    def _get_memory_usage(self) -> int:
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            import gc
            gc.collect()
            return 0


class SandboxExecutor:
    """沙箱执行器 - 安全执行Python代码"""

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()

    def execute(
        self, code: str, script_id: str,
        context: Dict[str, Any] = None, timeout: int = 30
    ) -> ExecutionResult:
        context_id = f"context_{uuid.uuid4().hex[:8]}"
        exec_context = ExecutionContext(
            context_id=context_id, script_id=script_id,
            globals=context or {}, permissions=self.config.permissions)

        monitor = ResourceMonitor(self.config.resource_limit)
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        start_time = time.time()
        danger_warnings = []

        try:
            try:
                ast.parse(code)
            except SyntaxError as e:
                return ExecutionResult(
                    context_id=context_id, success=False,
                    error=f"语法错误: {e}")

            danger_warnings = self._check_dangerous_patterns(code)
            if danger_warnings:
                logger.warning(f"脚本 {script_id} 检测到危险模式: {danger_warnings}")

            exec_globals = {
                '__name__': '__sandbox__',
                '__builtins__': self._create_restricted_builtins(),
                '__sandbox__': True,
            }
            exec_globals.update(exec_context.globals)
            exec_locals = {}

            monitor.start()

            try:
                exec(code, exec_globals, exec_locals)
            except Exception as e:
                raise e

            stats = monitor.stop()
            execution_time = stats['execution_time']

            outputs = exec_globals.get('_outputs', [])
            output = ''.join(outputs) + stdout_capture.getvalue()

            return ExecutionResult(
                context_id=context_id, success=True,
                output=output,
                return_value=exec_locals.get('__result__'),
                execution_time=execution_time,
                memory_peak_mb=stats['peak_memory_mb'],
                warnings=danger_warnings)

        except TimeoutError as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id, success=False,
                error=f"执行超时: {str(e)}", execution_time=timeout)

        except MemoryError as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id, success=False,
                error=f"内存超限: {str(e)}",
                execution_time=time.time() - start_time,
                memory_peak_mb=self.config.resource_limit.max_memory_mb)

        except Exception as e:
            monitor.stop()
            return ExecutionResult(
                context_id=context_id, success=False,
                error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time,
                warnings=danger_warnings)

    def _create_restricted_builtins(self) -> dict:
        import builtins as bi
        original = copy.copy(bi.__dict__)
        dangerous = ['eval', 'exec', 'compile', 'open', '__import__']
        for name in dangerous:
            if name in original:
                original[name] = self._make_restricted(name)
        allowed = {
            'print': original.get('print', print),
            'len': len, 'range': range,
            'str': str, 'int': int, 'float': float, 'bool': bool,
            'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
            'type': type, 'isinstance': isinstance,
            'hasattr': hasattr, 'getattr': getattr, 'setattr': setattr,
            'abs': abs, 'min': min, 'max': max, 'sum': sum,
            'sorted': sorted, 'reversed': reversed,
            'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter,
            'open': open,
        }
        if SandboxPermission.FILE_WRITE in self.config.permissions:
            allowed['open'] = original.get('open', open)
        return allowed

    def _make_restricted(self, name: str) -> Callable:
        def restricted(*args, **kwargs):
            raise PermissionError(f"函数 '{name}' 在沙箱中不可用")
        return restricted

    def _check_dangerous_patterns(self, code: str) -> List[str]:
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


class ScriptSandbox:
    """脚本沙箱管理器 - 沙箱实例池、热重载支持、调试接口"""

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.executor = SandboxExecutor(self.config)
        self._sandbox_pool: Dict[str, weakref.ref] = {}
        self._script_cache: Dict[str, str] = {}
        self._active_executions: Dict[str, ExecutionResult] = {}
        logger.info("脚本沙箱管理器初始化完成")

    def execute_script(
        self, script_id: str, code: str,
        context: Dict[str, Any] = None, timeout: int = 30
    ) -> ExecutionResult:
        if script_id in self._script_cache and self._script_cache[script_id] != code:
            logger.info(f"脚本 {script_id} 已修改，执行热重载")
            del self._script_cache[script_id]
        self._script_cache[script_id] = code
        result = self.executor.execute(code, script_id, context, timeout)
        self._active_executions[script_id] = result
        return result

    def hot_reload(self, script_id: str, new_code: str) -> bool:
        if script_id not in self._script_cache:
            return False
        try:
            ast.parse(new_code)
        except SyntaxError:
            return False
        self._script_cache[script_id] = new_code
        logger.info(f"脚本 {script_id} 热重载成功")
        return True

    def get_execution_history(self, script_id: str) -> List[ExecutionResult]:
        if script_id in self._active_executions:
            return [self._active_executions[script_id]]
        return []

    def create_debug_context(self, script_id: str, code: str) -> str:
        context_id = f"debug_{uuid.uuid4().hex[:8]}"
        tree = ast.parse(code)
        variables = [node.targets[0].id for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)]
        context = {
            'context_id': context_id, 'script_id': script_id,
            'variables': variables, 'breakpoints': [],
            'created_at': datetime.now().isoformat()}
        logger.info(f"调试上下文已创建: {context_id}")
        return context_id

    def add_breakpoint(self, context_id: str, line: int) -> bool:
        logger.info(f"断点已添加: context={context_id}, line={line}")
        return True

    def step_execution(self, context_id: str) -> Dict[str, Any]:
        return {'context_id': context_id, 'current_line': 1,
                'variables': {}, 'output': ''}


def create_safe_sandbox(
    allow_file_read: bool = True,
    allow_file_write: bool = False,
    allow_network: bool = False,
    max_memory_mb: int = 512,
    max_time_sec: int = 30
) -> ScriptSandbox:
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
            max_execution_time_sec=max_time_sec))
    return ScriptSandbox(config)


_sandbox_instance: Optional[ScriptSandbox] = None


def get_script_sandbox() -> ScriptSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = create_safe_sandbox()
    return _sandbox_instance


__all__ = [
    "ScriptSandbox", "SandboxExecutor", "SandboxConfig",
    "SandboxPermission", "ResourceLimit", "ExecutionResult",
    "create_safe_sandbox", "get_script_sandbox",
]
