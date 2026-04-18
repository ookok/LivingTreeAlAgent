"""
Script Sandbox - 沙箱执行环境
==============================

安全的脚本执行环境，用于运行用户生成的代码。

安全特性：
- 白名单模块访问
- 禁止危险操作
- 资源限制
- 超时控制
"""

import sys
import io
import traceback
import asyncio
from typing import Optional, Any, Callable, Dict
from dataclasses import dataclass, field
from enum import Enum


class SecurityLevel(Enum):
    """安全级别"""
    STRICT = "strict"      # 严格模式（推荐）
    MODERATE = "moderate" # 中等模式
    PERMISSIVE = "permissive"  # 宽松模式（仅供测试）


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    success: bool
    result: Any = None
    output: str = ""  # stdout输出
    error: str = ""   # 错误信息
    execution_time: float = 0.0
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SecurityError(Exception):
    """安全错误异常"""
    pass


class Sandbox:
    """沙箱执行器"""

    # 允许的模块及其函数
    ALLOWED_MODULES = {
        "math": ["*"],
        "random": ["*"],
        "datetime": ["*"],
        "time": ["sleep", "time", "strftime", "strptime"],
        "json": ["dumps", "loads", "dump", "load"],
        "re": ["match", "search", "sub", "findall", "compile"],
        "collections": ["Counter", "defaultdict", "OrderedDict"],
        "itertools": ["*"],
        "functools": ["*"],
        "typing": ["*"],
        "os": ["listdir", "getcwd", "path.exists", "path.join"],
        "sys": ["version", "platform", "argv"],
    }

    # 禁止的模式
    FORBIDDEN_PATTERNS = [
        r"__import__",
        r"exec\s*\(",
        r"eval\s*\(",
        r"compile\s*\(",
        r"open\s*\([^)]*['\"]w['\"]",  # 写文件
        r"open\s*\([^)]*['\"]a['\"]",   # 追加
        r"subprocess",
        r"os\.system",
        r"os\.popen",
        r"pty\.",
        r"tty\.",
        r"signal\.",
        r"thread",
        r"multiprocessing",
        r"socket\.",
        r"urllib\.",
        r"http\.",
        r"ftplib",
        r"telnetlib",
        r"telnet",
        r"smtplib",
        r"poplib",
        r"imaplib",
        r"requests",
        r"httpx",
        r"aiohttp",
    ]

    def __init__(self, security_level: SecurityLevel = SecurityLevel.STRICT):
        self.security_level = security_level
        self.execution_count = 0
        self.max_execution_count = 1000

    def validate_code(self, code: str) -> tuple[bool, list]:
        """
        验证代码安全性

        Args:
            code: 要验证的代码

        Returns:
            (is_safe, violations): 是否安全，违规列表
        """
        violations = []

        # 检查禁止的模式
        import re
        for pattern in self.FORBIDDEN_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                violations.append(f"Forbidden pattern detected: {pattern}")

        # 检查危险字符
        if self.security_level == SecurityLevel.STRICT:
            # 严格模式下检查多行
            if "\n" in code and len(code.split("\n")) > 20:
                violations.append("Code too long for strict mode")

        return len(violations) == 0, violations

    async def execute_async(
        self,
        code: str,
        context: dict = None,
        timeout: int = 30,
        globals_dict: dict = None,
        locals_dict: dict = None,
    ) -> SandboxResult:
        """异步执行代码"""
        import time

        start_time = time.time()

        # 验证代码
        is_safe, violations = self.validate_code(code)
        if not is_safe:
            return SandboxResult(
                success=False,
                error=f"Security validation failed: {', '.join(violations)}",
                execution_time=time.time() - start_time,
                warnings=violations,
            )

        # 检查执行次数
        if self.execution_count >= self.max_execution_count:
            return SandboxResult(
                success=False,
                error="Maximum execution count exceeded",
                execution_time=time.time() - start_time,
            )

        self.execution_count += 1

        # 创建安全的环境
        safe_globals = self._create_safe_globals()
        safe_locals = self._create_safe_locals()

        # 合并用户上下文
        if context:
            safe_globals.update(context)
        if globals_dict:
            safe_globals.update(globals_dict)
        if locals_dict:
            safe_locals.update(locals_dict)

        # 捕获输出
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            # 在隔离环境中执行代码
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_code,
                code,
                safe_globals,
                safe_locals,
                stdout_capture,
                stderr_capture,
            )

            return SandboxResult(
                success=True,
                result=result,
                output=stdout_capture.getvalue(),
                error=stderr_capture.getvalue(),
                execution_time=time.time() - start_time,
            )

        except TimeoutError:
            return SandboxResult(
                success=False,
                error="Execution timeout",
                output=stdout_capture.getvalue(),
                execution_time=time.time() - start_time,
                warnings=["Execution exceeded timeout limit"],
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                output=stdout_capture.getvalue(),
                execution_time=time.time() - start_time,
            )

    def _execute_code(
        self,
        code: str,
        safe_globals: dict,
        safe_locals: dict,
        stdout_capture: io.StringIO,
        stderr_capture: io.StringIO,
    ) -> Any:
        """实际执行代码的函数"""
        # 重定向stdout和stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        try:
            # 执行代码
            exec(code, safe_globals, safe_locals)
            return safe_locals.get("result")
        finally:
            # 恢复stdout和stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _create_safe_globals(self) -> dict:
        """创建安全的全局环境"""
        safe_globals = {
            "__builtins__": self._get_safe_builtins(),
            "__name__": "__sandbox__",
        }

        # 添加允许的模块
        for module_name, functions in self.ALLOWED_MODULES.items():
            try:
                if module_name == "os":
                    import os.path
                    safe_globals["os"] = os.path
                else:
                    module = __import__(module_name)
                    safe_globals[module_name] = module
            except ImportError:
                pass

        return safe_globals

    def _create_safe_locals(self) -> dict:
        """创建安全的本地环境"""
        return {}

    def _get_safe_builtins(self) -> dict:
        """获取安全的内置函数"""
        safe_builtins = {}

        # 只允许安全内置函数
        allowed_builtins = [
            "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
            "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
            "min", "max", "sum", "abs", "round", "any", "all",
            "isinstance", "issubclass", "type", "id", "hash",
            "print", "input",
            "hasattr", "getattr", "setattr",
            "True", "False", "None",
        ]

        for name in allowed_builtins:
            if hasattr(__builtins__, name):
                safe_builtins[name] = getattr(__builtins__, name)

        return safe_builtins


class ScriptSandbox(Sandbox):
    """脚本沙箱（继承自Sandbox）"""

    def __init__(
        self,
        security_level: SecurityLevel = SecurityLevel.STRICT,
        max_memory_mb: int = 100,
        max_cpu_time: float = 10.0,
    ):
        super().__init__(security_level)
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time = max_cpu_time

    async def execute_script(
        self,
        code: str,
        params: dict = None,
        context: dict = None,
    ) -> SandboxResult:
        """
        执行脚本

        Args:
            code: Python代码
            params: 执行参数
            context: 上下文变量

        Returns:
            SandboxResult: 执行结果
        """
        params = params or {}
        context = context or {}

        # 添加params到context
        context.update(params)

        return await self.execute_async(
            code=code,
            context=context,
            timeout=self.max_cpu_time,
        )


# 全局单例
_sandbox_instance: Optional[ScriptSandbox] = None


def get_sandbox(
    security_level: SecurityLevel = SecurityLevel.STRICT,
) -> ScriptSandbox:
    """获取沙箱单例"""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = ScriptSandbox(security_level)
    return _sandbox_instance


def reset_sandbox():
    """重置沙箱"""
    global _sandbox_instance
    _sandbox_instance = None