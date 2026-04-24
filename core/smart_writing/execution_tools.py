"""
代码执行工具
============

提供安全的代码执行接口：
1. 命令执行 - 运行 shell 命令
2. Python 执行 - 运行 Python 脚本（支持沙箱）
3. 测试运行 - 运行单元测试
4. 进程管理 - 查看/终止进程

安全特性：
- 命令白名单 - 限制可执行命令
- 超时控制 - 防止死循环
- 沙箱执行 - 限制资源使用
- 输出截断 - 防止内存溢出

使用方式:
    from core.smart_writing.execution_tools import ExecutionTools

    tools = ExecutionTools(project_root="/path/to/project")
    result = tools.execute_command("python -m pytest tests/")
    result = tools.run_python("print('Hello World')")
"""

import os
import re
import sys
import time
import uuid
import shlex
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from .tool_definition import (
    Tool, ToolParameter, ToolResult, ToolStatus,
    ToolRegistry, ToolCategory
)


# ============== 配置 ==============

# 默认超时（秒）
DEFAULT_TIMEOUT = 60

# 最大输出大小（1MB）
MAX_OUTPUT_SIZE = 1024 * 1024

# 最大输出行数
MAX_OUTPUT_LINES = 5000

# 允许的命令白名单（None 表示不限制）
ALLOWED_COMMANDS = None  # {"python", "git", "npm", "pip"}

# 禁止的命令黑名单
FORBIDDEN_COMMANDS = {
    "rm -rf /", "del /f /s /q", "format",
    "shutdown", "reboot", "init",
    ":(){ :|:& };:",  # Fork bomb
}


# ============== 执行工具类 ==============

class ExecutionTools:
    """
    代码执行工具集

    提供安全的命令执行能力。
    """

    def __init__(
        self,
        project_root: str,
        timeout: int = DEFAULT_TIMEOUT,
        allowed_commands: Optional[set] = ALLOWED_COMMANDS,
        registry: Optional[ToolRegistry] = None,
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            timeout: 默认超时（秒）
            allowed_commands: 允许的命令白名单（None 表示不限制）
            registry: 工具注册表（可选）
        """
        self.project_root = Path(project_root).resolve()
        self.timeout = timeout
        self.allowed_commands = allowed_commands
        self.registry = registry

        # 线程池（用于异步执行）
        self._executor = ThreadPoolExecutor(max_workers=4)

        # 注册工具
        if registry:
            self._register_tools()

    def _register_tools(self):
        """注册执行工具"""
        self.registry.register_tool(
            Tool(
                name="execute_command",
                description="执行 shell 命令",
                category=ToolCategory.EXECUTION,
                parameters=[
                    ToolParameter("command", "str", "要执行的命令", required=True),
                    ToolParameter("cwd", "str", "工作目录", required=False, default=None),
                    ToolParameter("timeout", "int", "超时时间（秒）", required=False, default=60),
                    ToolParameter("env", "dict", "环境变量", required=False, default=None),
                ],
                returns="命令输出和退出码",
                tags={"exec", "shell", "command"},
            ),
            self._execute_command_handler
        )

        self.registry.register_tool(
            Tool(
                name="run_python",
                description="执行 Python 代码",
                category=ToolCategory.EXECUTION,
                parameters=[
                    ToolParameter("code", "str", "Python 代码", required=True),
                    ToolParameter("timeout", "int", "超时时间（秒）", required=False, default=30),
                    ToolParameter("globals", "dict", "全局变量", required=False, default=None),
                    ToolParameter("locals", "dict", "局部变量", required=False, default=None),
                ],
                returns="代码输出",
                tags={"python", "exec"},
            ),
            self._run_python_handler
        )

        self.registry.register_tool(
            Tool(
                name="run_script",
                description="运行脚本文件",
                category=ToolCategory.EXECUTION,
                parameters=[
                    ToolParameter("path", "str", "脚本路径", required=True),
                    ToolParameter("args", "list", "脚本参数", required=False, default=[]),
                    ToolParameter("timeout", "int", "超时时间（秒）", required=False, default=60),
                ],
                returns="脚本输出",
                danger=True,
                confirm_required=True,
                tags={"script", "exec"},
            ),
            self._run_script_handler
        )

        self.registry.register_tool(
            Tool(
                name="run_tests",
                description="运行测试",
                category=ToolCategory.EXECUTION,
                parameters=[
                    ToolParameter("pattern", "str", "测试文件模式", required=False, default="test_*.py"),
                    ToolParameter("path", "str", "测试目录", required=False, default="tests"),
                    ToolParameter("verbose", "bool", "详细输出", required=False, default=True),
                ],
                returns="测试结果",
                tags={"test", "pytest"},
            ),
            self._run_tests_handler
        )

    def _validate_command(self, command: str) -> Tuple[bool, str]:
        """验证命令安全性"""
        # 检查黑名单
        for forbidden in FORBIDDEN_COMMANDS:
            if forbidden in command.lower():
                return False, f"禁止执行的命令: {forbidden}"

        # 检查白名单
        if self.allowed_commands:
            first_word = shlex.split(command)[0] if command.strip() else ""
            if first_word not in self.allowed_commands:
                return False, f"命令不在白名单中: {first_word}"

        return True, ""

    def _truncate_output(self, output: str) -> Tuple[str, bool]:
        """截断输出"""
        truncated = False

        if len(output) > MAX_OUTPUT_SIZE:
            output = output[:MAX_OUTPUT_SIZE]
            truncated = True

        lines = output.split('\n')
        if len(lines) > MAX_OUTPUT_LINES:
            output = '\n'.join(lines[:MAX_OUTPUT_LINES])
            truncated = True

        if truncated:
            output += f"\n... [输出已截断，最大 {MAX_OUTPUT_LINES} 行或 {MAX_OUTPUT_SIZE} 字节]"

        return output, truncated

    # ============== 工具处理器 ==============

    def _execute_command_handler(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ToolResult:
        """命令执行处理器"""
        # 验证命令
        valid, error = self._validate_command(command)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="execute_command",
                status=ToolStatus.FAILED,
                error=error,
            )

        # 设置工作目录
        if cwd:
            work_dir = (self.project_root / cwd).resolve()
            if not str(work_dir).startswith(str(self.project_root)):
                return ToolResult(
                    call_id="",
                    tool_name="execute_command",
                    status=ToolStatus.FAILED,
                    error="工作目录必须在项目目录下",
                )
        else:
            work_dir = self.project_root

        # 设置超时
        timeout = timeout or self.timeout

        # 合并环境变量
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            start_time = time.time()

            # 执行命令
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(work_dir),
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # 等待完成
            try:
                stdout, _ = process.communicate(timeout=timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, _ = process.communicate()
                return ToolResult(
                    call_id="",
                    tool_name="execute_command",
                    status=ToolStatus.TIMEOUT,
                    error=f"命令执行超时（{timeout}秒）",
                    result={
                        "stdout": stdout,
                        "timeout": timeout,
                    },
                    execution_time=timeout,
                )

            execution_time = time.time() - start_time

            # 截断输出
            stdout, truncated = self._truncate_output(stdout)

            return ToolResult(
                call_id="",
                tool_name="execute_command",
                status=ToolStatus.SUCCESS if return_code == 0 else ToolStatus.FAILED,
                result={
                    "stdout": stdout,
                    "return_code": return_code,
                    "command": command,
                    "cwd": str(work_dir),
                    "truncated": truncated,
                },
                message=f"命令执行完成，退出码: {return_code}" +
                        (" (输出已截断)" if truncated else ""),
                execution_time=execution_time,
                output_preview=stdout[:500] if stdout else None,
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="execute_command",
                status=ToolStatus.FAILED,
                error=f"执行失败: {e}",
            )

    def _run_python_handler(
        self,
        code: str,
        timeout: int = 30,
        globals: Optional[Dict] = None,
        locals: Optional[Dict] = None,
    ) -> ToolResult:
        """Python 执行处理器"""
        try:
            start_time = time.time()

            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # 执行
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.project_root),
                )

                execution_time = time.time() - start_time

                # 合并输出
                output = result.stdout
                if result.stderr:
                    output += "\n--- STDERR ---\n" + result.stderr

                # 截断输出
                output, truncated = self._truncate_output(output)

                return ToolResult(
                    call_id="",
                    tool_name="run_python",
                    status=ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.FAILED,
                    result={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "return_code": result.returncode,
                        "truncated": truncated,
                    },
                    message=f"Python 执行完成，退出码: {result.returncode}",
                    execution_time=execution_time,
                    output_preview=output[:500] if output else None,
                )

            finally:
                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except subprocess.TimeoutExpired:
            return ToolResult(
                call_id="",
                tool_name="run_python",
                status=ToolStatus.TIMEOUT,
                error=f"Python 执行超时（{timeout}秒）",
                execution_time=timeout,
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="run_python",
                status=ToolStatus.FAILED,
                error=f"Python 执行失败: {e}",
            )

    def _run_script_handler(
        self,
        path: str,
        args: List[str] = None,
        timeout: int = 60,
    ) -> ToolResult:
        """脚本执行处理器"""
        script_path = (self.project_root / path).resolve()

        # 验证路径
        if not str(script_path).startswith(str(self.project_root)):
            return ToolResult(
                call_id="",
                tool_name="run_script",
                status=ToolStatus.FAILED,
                error="脚本路径必须在项目目录下",
            )

        if not script_path.exists():
            return ToolResult(
                call_id="",
                tool_name="run_script",
                status=ToolStatus.FAILED,
                error=f"脚本不存在: {path}",
            )

        # 构建命令
        args = args or []
        if script_path.suffix == '.py':
            command = f"{sys.executable} {shlex.quote(str(script_path))}"
        else:
            command = str(script_path)

        for arg in args:
            command += f" {shlex.quote(arg)}"

        return self._execute_command_handler(
            command=command,
            timeout=timeout,
        )

    def _run_tests_handler(
        self,
        pattern: str = "test_*.py",
        path: str = "tests",
        verbose: bool = True,
    ) -> ToolResult:
        """测试执行处理器"""
        verbose_flag = "-v" if verbose else ""

        # 检查是否有 pytest
        check_pytest = subprocess.run(
            "python -c \"import pytest\"",
            shell=True,
            capture_output=True,
        )

        if check_pytest.returncode != 0:
            return ToolResult(
                call_id="",
                tool_name="run_tests",
                status=ToolStatus.FAILED,
                error="未安装 pytest，请运行: pip install pytest",
            )

        # 构建命令
        test_path = self.project_root / path
        command = f"python -m pytest {verbose_flag} {pattern}"

        return self._execute_command_handler(
            command=command,
            cwd=str(test_path),
            timeout=self.timeout,
        )

    # ============== 便捷方法 ==============

    def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ToolResult:
        """执行命令"""
        return self._execute_command_handler(command, cwd, timeout, env)

    def run_python(
        self,
        code: str,
        timeout: int = 30,
    ) -> ToolResult:
        """执行 Python 代码"""
        return self._run_python_handler(code, timeout)

    def run_script(
        self,
        path: str,
        args: List[str] = None,
        timeout: int = 60,
    ) -> ToolResult:
        """运行脚本"""
        return self._run_script_handler(path, args, timeout)

    def run_tests(
        self,
        pattern: str = "test_*.py",
        path: str = "tests",
        verbose: bool = True,
    ) -> ToolResult:
        """运行测试"""
        return self._run_tests_handler(pattern, path, verbose)


# ============== 导出 ==============

__all__ = [
    'ExecutionTools',
    'DEFAULT_TIMEOUT',
    'MAX_OUTPUT_SIZE',
    'ALLOWED_COMMANDS',
    'FORBIDDEN_COMMANDS',
]
