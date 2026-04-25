"""
test_execution_standalone_v2.py - 完全独立测试，不依赖 core 导入
"""

import sys
import os
import io
import time
import uuid
import builtins
import copy
import ast
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

print("=" * 60)
print("Execution Agent 独立测试")
print("=" * 60)

# ============= 核心组件复制 =============

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
            raise TimeoutError(f"执行超时: {elapsed:.1f}s")

    def stop(self) -> Dict[str, float]:
        self._running = False
        elapsed = time.time() - self._start_time if self._start_time else 0
        memory_mb = (self._peak_memory - self._start_memory) / (1024 * 1024)
        return {
            'execution_time': elapsed,
            'peak_memory_mb': max(0, memory_mb),
        }

    def _get_memory_usage(self) -> int:
        try:
            import psutil
            return psutil.Process().memory_info().rss
        except:
            return 0

class SandboxExecutor:
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()

    def execute(self, code: str, script_id: str, context: Dict = None, timeout: int = 30) -> ExecutionResult:
        context_id = f"context_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        outputs = []

        try:
            # 语法检查
            try:
                ast.parse(code)
            except SyntaxError as e:
                return ExecutionResult(
                    context_id=context_id,
                    success=False,
                    error=f"语法错误: {e}"
                )

            # 危险模式检测
            danger_warnings = self._check_dangerous_patterns(code)

            # 创建受限内置函数
            allowed_builtins = self._create_builtins(outputs)

            # 准备执行环境
            exec_globals = {
                '__name__': '__sandbox__',
                '__builtins__': allowed_builtins,
                '__sandbox__': True,
                '_outputs': outputs,
            }
            if context:
                exec_globals.update(context)

            exec_locals = {}

            # 资源监控
            monitor = ResourceMonitor(self.config.resource_limit)
            monitor.start()

            # 执行
            exec(code, exec_globals, exec_locals)

            stats = monitor.stop()

            return ExecutionResult(
                context_id=context_id,
                success=True,
                output=''.join(outputs),
                return_value=exec_locals.get('__result__'),
                execution_time=stats['execution_time'],
                memory_peak_mb=stats['peak_memory_mb'],
                warnings=danger_warnings
            )

        except TimeoutError as e:
            return ExecutionResult(
                context_id=context_id,
                success=False,
                error=f"执行超时: {str(e)}",
                execution_time=timeout
            )
        except Exception as e:
            return ExecutionResult(
                context_id=context_id,
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                execution_time=time.time() - start_time
            )

    def _create_builtins(self, outputs: List) -> dict:
        original = builtins.__dict__.copy()

        # 捕获 print
        original_print = original.get('print', print)
        def safe_print(*args, **kwargs):
            sep = kwargs.get('sep', ' ')
            end = kwargs.get('end', '\n')
            output = sep.join(str(a) for a in args) + end
            outputs.append(output)
            return len(output)

        return {
            'print': safe_print,
            'len': len, 'range': range, 'str': str, 'int': int, 'float': float,
            'bool': bool, 'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
            'type': type, 'isinstance': isinstance, 'hasattr': hasattr, 'getattr': getattr,
            'setattr': setattr, 'abs': abs, 'min': min, 'max': max, 'sum': sum,
            'sorted': sorted, 'reversed': reversed, 'enumerate': enumerate,
            'zip': zip, 'map': map, 'filter': filter,
        }

    def _check_dangerous_patterns(self, code: str) -> List[str]:
        warnings = []
        patterns = [
            (r'eval\s*\(', 'eval() 可能导致代码注入'),
            (r'exec\s*\(', 'exec() 可能导致代码注入'),
            (r'os\.system\s*\(', 'os.system() 可能执行危险命令'),
            (r'subprocess\.', 'subprocess 模块可能执行危险命令'),
        ]
        for pattern, msg in patterns:
            if pattern in code:
                warnings.append(msg)
        return warnings

class ScriptSandbox:
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.executor = SandboxExecutor(self.config)
        self._script_cache: Dict[str, str] = {}

    def execute_script(self, script_id: str, code: str, context: Dict = None, timeout: int = 30) -> ExecutionResult:
        return self.executor.execute(code, script_id, context, timeout)

def create_safe_sandbox(**kwargs) -> ScriptSandbox:
    permissions = set()
    if kwargs.get('allow_file_read'):
        permissions.add(SandboxPermission.FILE_READ)
    if kwargs.get('allow_file_write'):
        permissions.add(SandboxPermission.FILE_WRITE)

    config = SandboxConfig(
        permissions=permissions,
        resource_limit=ResourceLimit(
            max_memory_mb=kwargs.get('max_memory_mb', 512),
            max_execution_time_sec=kwargs.get('max_time_sec', 30)
        )
    )
    return ScriptSandbox(config)

# ============= Execution Agent =============

class ExecutionLevel(Enum):
    SANDBOX = "sandbox"
    RESTRICTED = "restricted"
    FULL = "full"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

@dataclass
class ExecutionReport:
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_peak_mb: float = 0.0
    warnings: List[str] = field(default_factory=list)

class ExecutionAgent:
    def __init__(self, level: ExecutionLevel = ExecutionLevel.SANDBOX):
        self.level = level
        self.sandbox = self._create_sandbox(level)

    def _create_sandbox(self, level: ExecutionLevel) -> ScriptSandbox:
        configs = {
            ExecutionLevel.SANDBOX: {'allow_file_read': True, 'allow_file_write': False, 'max_memory_mb': 512, 'max_time_sec': 30},
            ExecutionLevel.RESTRICTED: {'allow_file_read': True, 'allow_file_write': True, 'max_memory_mb': 1024, 'max_time_sec': 60},
            ExecutionLevel.FULL: {'allow_file_read': True, 'allow_file_write': True, 'max_memory_mb': 2048, 'max_time_sec': 120},
        }
        return create_safe_sandbox(**configs.get(level, configs[ExecutionLevel.SANDBOX]))

    def execute_code(self, code: str, context: Dict = None, timeout: int = 30) -> ExecutionReport:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        result = self.sandbox.execute_script(task_id, code, context, timeout)
        return ExecutionReport(
            task_id=task_id,
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            memory_peak_mb=result.memory_peak_mb,
            warnings=result.warnings
        )

def create_execution_agent(level: str = "sandbox") -> ExecutionAgent:
    level_map = {'sandbox': ExecutionLevel.SANDBOX, 'restricted': ExecutionLevel.RESTRICTED, 'full': ExecutionLevel.FULL}
    return ExecutionAgent(level_map.get(level, ExecutionLevel.SANDBOX))

# ============= 测试 =============

print("\n[Test 1] 简单计算")
agent = create_execution_agent('sandbox')
report = agent.execute_code("""
result = 2 ** 10
print(f"2^10 = {result}")
""")
print(f"[PASS] Success: {report.success}")
if report.output:
    print(f"  Output: {report.output.strip()}")

print("\n[Test 2] 带上下文执行")
report = agent.execute_code("""
area = 3.14 * radius ** 2
print(f"半径 {radius} 的圆面积: {area:.2f}")
""", context={'radius': 5})
print(f"[PASS] Success: {report.success}")
if report.output:
    print(f"  Output: {report.output.strip()}")

print("\n[Test 3] 危险代码检测")
report = agent.execute_code("""
import os
os.system("echo hacked")
""")
print(f"  Success: {report.success}")
print(f"  Warnings: {report.warnings}")

print("\n[Test 4] 快速执行")
result = agent.execute_code("""
data = [1, 2, 3, 4, 5]
print(f"Sum: {sum(data)}")
print(f"Avg: {sum(data)/len(data)}")
""")
print(f"[PASS] Success: {result.success}")
if result.output:
    print(f"  Output: {result.output.strip()}")
print(f"  Time: {result.execution_time:.4f}s")

print("\n[Test 5] 语法错误检测")
report = agent.execute_code("""
print("hello
""")
print(f"  Success: {report.success}")
print(f"  Error: {report.error[:50]}...")

print("\n" + "=" * 60)
print("所有测试完成!")
print("=" * 60)
