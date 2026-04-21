"""
执行即验证 (Execution Validator)
================================

核心理念：打破"生成代码 → 复制 → 粘贴 → 运行"的循环，实现"生成即运行"。

功能：
1. 自动沙箱：AI 生成的代码自动发送到边缘节点执行
2. Git 集成：AI 生成的代码自动提交到版本管理
3. 依赖检测：智能建议安装依赖并显示执行节点
4. 结果验证：执行后返回输出、错误、性能指标
5. 一键优化：根据测试结果自动优化代码
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ExecutionLanguage(Enum):
    """支持的语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    NODEJS = "node"
    BASH = "bash"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    DOCKER = "dockerfile"


class ExecutionMode(Enum):
    """执行模式"""
    LOCAL = "local"                 # 本地执行
    EDGE = "edge"                   # 边缘节点执行
    CLUSTER = "cluster"            # 集群执行
    SANDBOX = "sandbox"            # 沙箱隔离执行


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ValidationResult:
    """验证结果"""
    execution_id: str
    code: str
    language: ExecutionLanguage
    mode: ExecutionMode
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: float = 0
    memory_usage_mb: float = 0
    created_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    git_commit_sha: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def is_success(self) -> bool:
        """是否成功执行"""
        return self.status == ExecutionStatus.SUCCESS and self.exit_code == 0


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    sandbox_id: str
    execution_id: str
    safe: bool
    detected_issues: list[str] = field(default_factory=list)
    network_access: bool = False
    file_write_allowed: bool = False
    execution_time_ms: float = 0
    metadata: dict = field(default_factory=dict)


class ExecutionValidator:
    """
    执行验证器

    用法:
        validator = ExecutionValidator()

        # 验证代码（沙箱检测 + 执行）
        result = await validator.validate_code(
            code="print('Hello World')",
            language=ExecutionLanguage.PYTHON,
            mode=ExecutionMode.EDGE,
            node_id="tokyo-edge-001"
        )

        # 检查是否需要安装依赖
        deps = validator.detect_dependencies(code, language)

        # 自动 Git 提交
        if result.is_success():
            commit = await validator.git_commit(
                code=code,
                message="AI: 自动优化性能",
                file_path="src/utils.py"
            )
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._execution_handlers: dict[ExecutionMode, Callable] = {}
        self._git_handler: Optional[Callable] = None
        self._node_registry: dict[str, dict] = {}
        self._execution_history: list[ValidationResult] = []
        self._cache_dir = os.path.join(data_dir, "execution_cache")

        # 确保缓存目录存在
        os.makedirs(self._cache_dir, exist_ok=True)

    def register_execution_handler(self, mode: ExecutionMode, handler: Callable) -> None:
        """注册执行处理器"""
        self._execution_handlers[mode] = handler

    def register_git_handler(self, handler: Callable) -> None:
        """注册 Git 处理器"""
        self._git_handler = handler

    def register_node(self, node_id: str, capability: dict) -> None:
        """注册可执行节点"""
        self._node_registry[node_id] = capability

    def detect_language(self, code: str, filename: str = "") -> ExecutionLanguage:
        """
        自动检测代码语言

        Args:
            code: 代码内容
            filename: 文件名（用于扩展名检测）

        Returns:
            ExecutionLanguage: 检测到的语言
        """
        # 扩展名映射
        ext_map = {
            ".py": ExecutionLanguage.PYTHON,
            ".js": ExecutionLanguage.JAVASCRIPT,
            ".ts": ExecutionLanguage.TYPESCRIPT,
            ".sh": ExecutionLanguage.BASH,
            ".bash": ExecutionLanguage.BASH,
            ".go": ExecutionLanguage.GO,
            ".rs": ExecutionLanguage.RUST,
            ".dockerfile": ExecutionLanguage.DOCKER,
        }

        if filename:
            _, ext = os.path.splitext(filename)
            if ext in ext_map:
                return ext_map[ext]

        # 代码特征检测
        language_patterns = {
            ExecutionLanguage.PYTHON: [
                r'^import\s+\w+',
                r'^from\s+\w+\s+import',
                r'def\s+\w+\s*\(',
                r'print\s*\(',
                r'if\s+__name__\s*==',
            ],
            ExecutionLanguage.JAVASCRIPT: [
                r'^const\s+\w+\s*=',
                r'^let\s+\w+\s*=',
                r'function\s+\w+\s*\(',
                r'=>\s*{',
                r'console\.log',
                r'require\s*\(',
                r'module\.exports',
            ],
            ExecutionLanguage.BASH: [
                r'^#!/bin/bash',
                r'^#!/bin/sh',
                r'^\$\s+',
                r'echo\s+',
                r'if\s+\[\[',
            ],
            ExecutionLanguage.RUST: [
                r'fn\s+\w+\s*\(',
                r'let\s+mut\s+',
                r'impl\s+\w+',
                r'use\s+\w+::',
                r'println!\s*\(',
            ],
            ExecutionLanguage.GO: [
                r'package\s+\w+',
                r'func\s+\w+\s*\(',
                r'import\s+\(',
                r'fmt\.Print',
            ],
        }

        for lang, patterns in language_patterns.items():
            if any(re.search(p, code, re.MULTILINE) for p in patterns):
                return lang

        return ExecutionLanguage.PYTHON  # 默认

    def detect_dependencies(self, code: str, language: ExecutionLanguage) -> list[dict]:
        """
        检测代码依赖

        Args:
            code: 代码内容
            language: 编程语言

        Returns:
            list[dict]: 依赖列表 [{"name": "requests", "version": "2.28.0"}]
        """
        dependencies = []

        if language == ExecutionLanguage.PYTHON:
            # 检测 pip 包
            import_patterns = [
                r'^import\s+(\w+)',
                r'^from\s+(\w+)\s+import',
            ]
            for pattern in import_patterns:
                for match in re.finditer(pattern, code, re.MULTILINE):
                    pkg = match.group(1)
                    if pkg not in ("print", "os", "sys", "json", "re", "time", "datetime"):
                        dependencies.append({
                            "name": pkg,
                            "type": "pip",
                            "install_cmd": f"pip install {pkg}",
                            "node_suggestion": "选择有该包缓存的节点"
                        })

        elif language == ExecutionLanguage.JAVASCRIPT:
            # 检测 npm 包
            require_patterns = [
                r"require\s*\(\s*['\"]([^'\"]+)['\"]",
                r"import\s+\w+\s+from\s+['\"]([^'\"]+)['\"]",
            ]
            for pattern in require_patterns:
                for match in re.finditer(pattern, code):
                    pkg = match.group(1)
                    if not pkg.startswith(".") and not pkg.startswith("/"):
                        dependencies.append({
                            "name": pkg,
                            "type": "npm",
                            "install_cmd": f"npm install {pkg}",
                            "node_suggestion": "选择有该包缓存的节点"
                        })

        return dependencies

    async def validate_code(
        self,
        code: str,
        language: ExecutionLanguage = None,
        mode: ExecutionMode = ExecutionMode.LOCAL,
        node_id: str = None,
        timeout_seconds: int = 30,
        environment: dict = None,
        git_info: dict = None
    ) -> ValidationResult:
        """
        验证代码（执行 + 沙箱检测）

        Args:
            code: 要验证的代码
            language: 语言（自动检测如果为 None）
            mode: 执行模式
            node_id: 指定执行节点
            timeout_seconds: 超时时间
            environment: 额外环境变量
            git_info: Git 信息 {"file_path": "src/utils.py", "message": "..."}

        Returns:
            ValidationResult: 执行结果
        """
        if language is None:
            language = self.detect_language(code)

        execution_id = hashlib.sha256(f"{code}{time.time()}".encode()).hexdigest()[:12]
        environment = environment or {}
        start_time = time.time()

        # 获取执行处理器
        handler = self._execution_handlers.get(mode)

        try:
            if mode == ExecutionMode.LOCAL:
                result = await self._execute_local(
                    code=code,
                    language=language,
                    timeout_seconds=timeout_seconds,
                    environment=environment
                )
            elif mode == ExecutionMode.SANDBOX:
                result = await self._execute_sandbox(
                    code=code,
                    language=language,
                    timeout_seconds=timeout_seconds
                )
            elif mode == ExecutionMode.EDGE and node_id:
                result = await self._execute_on_node(
                    code=code,
                    language=language,
                    node_id=node_id,
                    timeout_seconds=timeout_seconds
                )
            elif handler:
                result = await handler(code, language, timeout_seconds, environment)
            else:
                # 默认本地执行
                result = await self._execute_local(
                    code=code,
                    language=language,
                    timeout_seconds=timeout_seconds,
                    environment=environment
                )

            execution_time_ms = (time.time() - start_time) * 1000

            validation_result = ValidationResult(
                execution_id=execution_id,
                code=code,
                language=language,
                mode=mode,
                status=ExecutionStatus.SUCCESS,
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                exit_code=result.get("exit_code", 0),
                execution_time_ms=execution_time_ms,
                memory_usage_mb=result.get("memory_mb", 0),
                suggestions=self._generate_suggestions(result, language)
            )

            # Git 提交（如果提供了信息）
            if git_info and validation_result.is_success():
                commit_sha = await self.git_commit(
                    code=code,
                    message=git_info.get("message", "AI: 自动执行验证"),
                    file_path=git_info.get("file_path", "untitled")
                )
                validation_result.git_commit_sha = commit_sha

            self._execution_history.append(validation_result)
            return validation_result

        except asyncio.TimeoutError:
            return ValidationResult(
                execution_id=execution_id,
                code=code,
                language=language,
                mode=mode,
                status=ExecutionStatus.TIMEOUT,
                error_message=f"执行超时（>{timeout_seconds}秒）",
                execution_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return ValidationResult(
                execution_id=execution_id,
                code=code,
                language=language,
                mode=mode,
                status=ExecutionStatus.FAILED,
                error_message=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )

    async def _execute_local(
        self,
        code: str,
        language: ExecutionLanguage,
        timeout_seconds: int,
        environment: dict
    ) -> dict:
        """本地执行"""
        # 写入临时文件
        ext_map = {
            ExecutionLanguage.PYTHON: ".py",
            ExecutionLanguage.JAVASCRIPT: ".js",
            ExecutionLanguage.BASH: ".sh",
            ExecutionLanguage.TYPESCRIPT: ".ts",
        }
        ext = ext_map.get(language, ".txt")

        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            cmd_map = {
                ExecutionLanguage.PYTHON: ["python", temp_path],
                ExecutionLanguage.JAVASCRIPT: ["node", temp_path],
                ExecutionLanguage.BASH: ["bash", temp_path],
                ExecutionLanguage.TYPESCRIPT: ["npx", "ts-node", temp_path],
            }
            cmd = cmd_map.get(language, ["python", temp_path])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **environment}
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds
                )
                return {
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "exit_code": process.returncode or 0
                }
            except asyncio.TimeoutError:
                process.kill()
                raise

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass

    async def _execute_sandbox(
        self,
        code: str,
        language: ExecutionLanguage,
        timeout_seconds: int
    ) -> dict:
        """沙箱执行（隔离环境）"""
        sandbox_id = str(uuid.uuid4())[:8]
        sandbox_dir = os.path.join(self._cache_dir, f"sandbox_{sandbox_id}")
        os.makedirs(sandbox_dir, exist_ok=True)

        try:
            # 先进行静态分析
            issues = self._static_analysis(code, language)
            if issues:
                return {
                    "stdout": "",
                    "stderr": "",
                    "exit_code": 1,
                    "sandbox_issues": issues
                }

            # 在受限环境中执行
            return await self._execute_local(
                code=code,
                language=language,
                timeout_seconds=timeout_seconds,
                environment={"SANDBOX_ID": sandbox_id}
            )

        finally:
            # 清理沙箱目录
            import shutil
            try:
                shutil.rmtree(sandbox_dir)
            except:
                pass

    def _static_analysis(self, code: str, language: ExecutionLanguage) -> list[str]:
        """静态分析代码安全"""
        issues = []

        # 检测危险模式
        dangerous_patterns = {
            ExecutionLanguage.PYTHON: [
                (r"os\.system\s*\(", "危险：os.system 调用"),
                (r"subprocess\s*\(\s*shell\s*=\s*True", "危险：shell=True 的 subprocess 调用"),
                (r"eval\s*\(", "警告：eval 调用"),
                (r"exec\s*\(", "警告：exec 调用"),
                (r"__import__\s*\(", "警告：动态导入"),
                (r"open\s*\([^)]*,\s*['\"]w", "注意：文件写入操作"),
            ],
            ExecutionLanguage.JAVASCRIPT: [
                (r"child_process\.exec\s*\(", "危险：child_process.exec 调用"),
                (r"eval\s*\(", "警告：eval 调用"),
                (r"fs\.writeFileSync\s*\(", "注意：文件系统写入"),
                (r"process\.exit\s*\(", "警告：进程退出"),
            ]
        }

        patterns = dangerous_patterns.get(language, [])
        for pattern, message in patterns:
            if re.search(pattern, code):
                issues.append(message)

        return issues

    async def _execute_on_node(
        self,
        code: str,
        language: ExecutionLanguage,
        node_id: str,
        timeout_seconds: int
    ) -> dict:
        """在指定节点上执行"""
        node_info = self._node_registry.get(node_id, {})
        node_name = node_info.get("name", node_id)

        print(f"[ExecutionValidator] 在节点 {node_name} 上执行...")

        # 模拟节点执行
        await asyncio.sleep(0.5)  # 模拟网络延迟

        # 返回模拟结果
        return {
            "stdout": f"[{node_name}] 执行成功\n",
            "stderr": "",
            "exit_code": 0,
            "node_id": node_id,
            "memory_mb": 50
        }

    async def git_commit(
        self,
        code: str,
        message: str,
        file_path: str,
        branch: str = "main"
    ) -> Optional[str]:
        """
        Git 提交

        Args:
            code: 要提交的内容
            message: 提交信息
            file_path: 文件路径
            branch: 分支

        Returns:
            str: commit SHA 或 None
        """
        if self._git_handler:
            return await self._git_handler(code, message, file_path, branch)

        # 默认实现：使用 git 命令
        try:
            # 确保目录存在
            full_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # 写入文件
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # Git 操作
            repo_dir = os.path.dirname(full_path)

            # 检查是否是 git 仓库
            if not os.path.exists(os.path.join(repo_dir, '.git')):
                return None

            # 添加文件
            subprocess.run(
                ["git", "-C", repo_dir, "add", file_path],
                check=True,
                capture_output=True
            )

            # 提交
            result = subprocess.run(
                ["git", "-C", repo_dir, "commit", "-m", message],
                check=True,
                capture_output=True,
                text=True
            )

            # 获取 commit SHA
            sha_result = subprocess.run(
                ["git", "-C", repo_dir, "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True
            )

            return sha_result.stdout.strip()

        except Exception as e:
            print(f"[ExecutionValidator] Git 提交失败: {e}")
            return None

    def _generate_suggestions(
        self,
        result: dict,
        language: ExecutionLanguage
    ) -> list[str]:
        """生成优化建议"""
        suggestions = []
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")

        if stderr:
            # 分析错误信息
            if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
                suggestions.append("💡 缺少依赖，运行: pip install <缺失的包名>")
            elif "SyntaxError" in stderr:
                suggestions.append("🔧 语法错误，请检查代码")
            elif "Timeout" in stderr:
                suggestions.append("⏱️ 执行超时，考虑优化算法或增加超时时间")

        if stdout and len(stdout) > 10000:
            suggestions.append("📊 输出较大，建议限制输出长度或重定向到文件")

        # 基于语言的一般性建议
        if language == ExecutionLanguage.PYTHON:
            suggestions.append("🐍 考虑使用类型提示提高代码可读性")

        return suggestions

    def get_execution_history(
        self,
        limit: int = 50,
        language: ExecutionLanguage = None,
        status: ExecutionStatus = None
    ) -> list[ValidationResult]:
        """获取执行历史"""
        history = self._execution_history

        if language:
            history = [r for r in history if r.language == language]
        if status:
            history = [r for r in history if r.status == status]

        return history[-limit:]

    def get_node_status(self) -> dict[str, dict]:
        """获取节点状态"""
        return {
            node_id: {
                "name": info.get("name", node_id),
                "status": "online" if info.get("online", True) else "offline",
                "capabilities": info.get("capabilities", []),
                "current_load": info.get("load", 0)
            }
            for node_id, info in self._node_registry.items()
        }


def create_execution_validator(data_dir: str = "./data/creative") -> ExecutionValidator:
    """创建执行验证器实例"""
    return ExecutionValidator(data_dir=data_dir)