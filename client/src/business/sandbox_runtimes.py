"""
Sandbox Runtimes Manager - 统一的多语言运行时管理器

提供 Python (uv)、Rust (Cargo)、Go (Go SDK) 的统一接口，
支持沙盒化部署、环境隔离、任务执行。

定位:
    - Python: AI 模型/脚本主力载体
    - Rust: 高性能 CLI 工具编译
    - Go: 网络/云原生工具
"""

import asyncio
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

# psutil 是可选依赖
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ============= 常量 =============

class RuntimeType(Enum):
    """支持的运行时类型"""
    PYTHON = "python"
    RUST = "rust"
    GO = "go"
    NODE = "node"


@dataclass
class RuntimeInfo:
    """运行时信息"""
    id: str
    type: RuntimeType
    version: str
    installed: bool
    install_dir: Optional[Path] = None
    bin_dir: Optional[Path] = None
    is_sandbox: bool = True


@dataclass
class SandboxEnv:
    """沙盒环境配置"""
    path: Path
    cache_dir: Path
    projects_dir: Path

    def __post_init__(self):
        self.path.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)


# ============= 路径检测 =============

def get_tools_dir() -> Path:
    """获取工具根目录"""
    return Path(os.environ.get("HERMES_TOOLS", "~/.hermes-desktop/tools")).expanduser()


def get_cache_dir() -> Path:
    """获取缓存根目录"""
    return Path(os.environ.get("HERMES_CACHE", "~/.hermes-desktop/cache")).expanduser()


# ============= 运行时检测基类 =============

class RuntimeDetector:
    """运行时检测基类"""

    @staticmethod
    def detect_python() -> RuntimeInfo:
        """检测 Python 运行时"""
        tools_dir = get_tools_dir()

        # uv 检测
        uv_path = tools_dir / "python_runtime" / "uv.exe"
        if platform.system() != "Windows":
            uv_path = tools_dir / "python_runtime" / "uv"

        if uv_path.exists():
            # 获取 uv 版本
            try:
                result = subprocess.run(
                    [str(uv_path), "--version"],
                    capture_output=True, text=True
                )
                version = result.stdout.strip()
            except Exception:
                version = "unknown"

            return RuntimeInfo(
                id="python_runtime",
                type=RuntimeType.PYTHON,
                version=version,
                installed=True,
                install_dir=tools_dir / "python_runtime",
                bin_dir=tools_dir / "python_runtime",
                is_sandbox=True
            )

        # 系统 Python
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True, text=True
            )
            version = result.stdout.strip()
            return RuntimeInfo(
                id="system_python",
                type=RuntimeType.PYTHON,
                version=version,
                installed=True,
                is_sandbox=False
            )
        except Exception:
            return RuntimeInfo(
                id="python_runtime",
                type=RuntimeType.PYTHON,
                version="not installed",
                installed=False
            )

    @staticmethod
    def detect_rust() -> RuntimeInfo:
        """检测 Rust 运行时"""
        tools_dir = get_tools_dir()

        # Cargo 检测
        cargo_path = tools_dir / "rust_toolchain" / "cargo" / "bin" / "cargo.exe"
        if platform.system() != "Windows":
            cargo_path = tools_dir / "rust_toolchain" / "cargo" / "bin" / "cargo"

        if cargo_path.exists():
            try:
                result = subprocess.run(
                    [str(cargo_path), "--version"],
                    capture_output=True, text=True
                )
                version = result.stdout.strip()
            except Exception:
                version = "unknown"

            return RuntimeInfo(
                id="rust_toolchain",
                type=RuntimeType.RUST,
                version=version,
                installed=True,
                install_dir=tools_dir / "rust_toolchain",
                bin_dir=tools_dir / "rust_toolchain" / "cargo" / "bin",
                is_sandbox=True
            )

        # 系统 Rust
        try:
            result = subprocess.run(
                ["cargo", "--version"],
                capture_output=True, text=True
            )
            version = result.stdout.strip()
            return RuntimeInfo(
                id="system_rust",
                type=RuntimeType.RUST,
                version=version,
                installed=True,
                is_sandbox=False
            )
        except Exception:
            return RuntimeInfo(
                id="rust_toolchain",
                type=RuntimeType.RUST,
                version="not installed",
                installed=False
            )

    @staticmethod
    def detect_go() -> RuntimeInfo:
        """检测 Go 运行时"""
        tools_dir = get_tools_dir()

        # Go 检测
        go_path = tools_dir / "go_runtime" / "bin" / "go.exe"
        if platform.system() != "Windows":
            go_path = tools_dir / "go_runtime" / "bin" / "go"

        if go_path.exists():
            try:
                result = subprocess.run(
                    [str(go_path), "version"],
                    capture_output=True, text=True
                )
                version = result.stdout.strip()
            except Exception:
                version = "unknown"

            return RuntimeInfo(
                id="go_runtime",
                type=RuntimeType.GO,
                version=version,
                installed=True,
                install_dir=tools_dir / "go_runtime",
                bin_dir=tools_dir / "go_runtime" / "bin",
                is_sandbox=True
            )

        # 系统 Go
        try:
            result = subprocess.run(
                ["go", "version"],
                capture_output=True, text=True
            )
            version = result.stdout.strip()
            return RuntimeInfo(
                id="system_go",
                type=RuntimeType.GO,
                version=version,
                installed=True,
                is_sandbox=False
            )
        except Exception:
            return RuntimeInfo(
                id="go_runtime",
                type=RuntimeType.GO,
                version="not installed",
                installed=False
            )

    @staticmethod
    def detect_node() -> RuntimeInfo:
        """检测 Node.js 运行时"""
        tools_dir = get_tools_dir()

        # Node 检测
        node_path = tools_dir / "nodejs_runtime" / "bin" / "node.exe"
        if platform.system() != "Windows":
            node_path = tools_dir / "nodejs_runtime" / "bin" / "node"

        if node_path.exists():
            try:
                result = subprocess.run(
                    [str(node_path), "--version"],
                    capture_output=True, text=True
                )
                version = result.stdout.strip()
            except Exception:
                version = "unknown"

            return RuntimeInfo(
                id="nodejs_runtime",
                type=RuntimeType.NODE,
                version=version,
                installed=True,
                install_dir=tools_dir / "nodejs_runtime",
                bin_dir=tools_dir / "nodejs_runtime" / "bin",
                is_sandbox=True
            )

        # 系统 Node
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True
            )
            version = result.stdout.strip()
            return RuntimeInfo(
                id="system_node",
                type=RuntimeType.NODE,
                version=version,
                installed=True,
                is_sandbox=False
            )
        except Exception:
            return RuntimeInfo(
                id="nodejs_runtime",
                type=RuntimeType.NODE,
                version="not installed",
                installed=False
            )

    @classmethod
    def detect_all(cls) -> dict[RuntimeType, RuntimeInfo]:
        """检测所有运行时"""
        return {
            RuntimeType.PYTHON: cls.detect_python(),
            RuntimeType.RUST: cls.detect_rust(),
            RuntimeType.GO: cls.detect_go(),
            RuntimeType.NODE: cls.detect_node(),
        }


# ============= 沙盒环境构造 =============

class SandboxEnvBuilder:
    """沙盒环境构造器"""

    @staticmethod
    def get_sandbox_env(runtime_type: RuntimeType) -> dict:
        """
        构造指定运行时的沙盒环境变量

        Args:
            runtime_type: 运行时类型

        Returns:
            dict: 沙盒环境变量
        """
        env = os.environ.copy()
        tools_dir = get_tools_dir()
        cache_dir = get_cache_dir()
        sep = ";" if platform.system() == "Windows" else ":"

        if runtime_type == RuntimeType.PYTHON:
            sandbox_dir = tools_dir / "python_runtime"
            if sandbox_dir.exists():
                # PATH 优先
                env["PATH"] = f"{sandbox_dir}{sep}{env.get('PATH', '')}"
                # uv 配置
                env["UV_CACHE_DIR"] = str(cache_dir / "uv")
                env["UV_PROJECT"] = str(tools_dir / "projects")
                # Python 配置
                env["PYTHONPATH"] = str(sandbox_dir / "lib" / "site-packages")

        elif runtime_type == RuntimeType.RUST:
            sandbox_dir = tools_dir / "rust_toolchain"
            if sandbox_dir.exists():
                cargo_bin = sandbox_dir / "cargo" / "bin"
                rustup_home = sandbox_dir / "rustup"
                env["PATH"] = f"{cargo_bin}{sep}{env.get('PATH', '')}"
                env["CARGO_HOME"] = str(sandbox_dir / "cargo")
                env["RUSTUP_HOME"] = str(rustup_home)

        elif runtime_type == RuntimeType.GO:
            sandbox_dir = tools_dir / "go_runtime"
            if sandbox_dir.exists():
                go_bin = sandbox_dir / "bin"
                env["PATH"] = f"{go_bin}{sep}{env.get('PATH', '')}"
                env["GOROOT"] = str(sandbox_dir)
                env["GOPATH"] = str(tools_dir / "go" / "gopath")
                env["GOMODCACHE"] = str(cache_dir / "go" / "mod")
                env["GOPROXY"] = "https://goproxy.cn,direct"

        elif runtime_type == RuntimeType.NODE:
            sandbox_dir = tools_dir / "nodejs_runtime"
            if sandbox_dir.exists():
                node_bin = sandbox_dir / "bin"
                env["PATH"] = f"{node_bin}{sep}{env.get('PATH', '')}"
                env["NPM_CONFIG_USERCONFIG"] = str(sandbox_dir / ".npmrc")
                env["YARN_RC_FILENAME"] = str(sandbox_dir / ".yarnrc.yml")
                env["NPM_CONFIG_CACHE"] = str(cache_dir / "npm")
                env["YARN_CACHE_FOLDER"] = str(cache_dir / "yarn")

        return env


# ============= 命令执行封装 =============

class SandboxExecutor:
    """沙盒命令执行器"""

    def __init__(self, runtime_type: RuntimeType):
        self.runtime_type = runtime_type
        self.env = SandboxEnvBuilder.get_sandbox_env(runtime_type)

    def run_sync(
        self,
        cmd: list[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        同步执行命令

        Args:
            cmd: 命令列表
            cwd: 工作目录
            timeout: 超时秒数

        Returns:
            CompletedProcess: 执行结果
        """
        return subprocess.run(
            cmd,
            env=self.env,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout
        )

    async def run_async(
        self,
        cmd: list[str],
        cwd: Optional[Path] = None
    ) -> asyncio.subprocess.Process:
        """
        异步执行命令

        Args:
            cmd: 命令列表
            cwd: 工作目录

        Returns:
            Process: 异步进程
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=self.env,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        return proc


# ============= Python uv 封装 =============

class UvExecutor:
    """uv 包管理器封装"""

    def __init__(self):
        tools_dir = get_tools_dir()
        self.uv_path = tools_dir / "python_runtime" / "uv.exe"
        if platform.system() != "Windows":
            self.uv_path = tools_dir / "python_runtime" / "uv"
        self.executor = SandboxExecutor(RuntimeType.PYTHON)

    def is_available(self) -> bool:
        """uv 是否可用"""
        return self.uv_path.exists()

    def get_version(self) -> str:
        """获取 uv 版本"""
        try:
            result = self.executor.run_sync([str(self.uv_path), "--version"])
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def install_python(self, version: str = "3.12") -> bool:
        """安装指定版本的 Python"""
        if not self.is_available():
            return False
        try:
            result = self.executor.run_sync(
                [str(self.uv_path), "python", "install", version]
            )
            return result.returncode == 0
        except Exception:
            return False

    def create_project(self, path: Path, python_version: str = "3.12") -> bool:
        """创建 uv 项目"""
        if not self.is_available():
            return False
        try:
            result = self.executor.run_sync(
                [str(self.uv_path), "init", "--python", python_version],
                cwd=path
            )
            return result.returncode == 0
        except Exception:
            return False

    def add_package(self, package: str, project_path: Path) -> bool:
        """添加包依赖"""
        if not self.is_available():
            return False
        try:
            result = self.executor.run_sync(
                [str(self.uv_path), "add", package],
                cwd=project_path
            )
            return result.returncode == 0
        except Exception:
            return False

    def run_script(self, script: Path, project_path: Path) -> subprocess.CompletedProcess:
        """运行 Python 脚本"""
        if not self.is_available():
            raise RuntimeError("uv not available")
        return self.executor.run_sync(
            [str(self.uv_path), "run", "python", str(script)],
            cwd=project_path
        )


# ============= Go 封装 =============

class GoExecutor:
    """Go SDK 封装"""

    def __init__(self):
        tools_dir = get_tools_dir()
        self.go_path = tools_dir / "go_runtime" / "bin" / "go.exe"
        if platform.system() != "Windows":
            self.go_path = tools_dir / "go_runtime" / "bin" / "go"
        self.executor = SandboxExecutor(RuntimeType.GO)

    def is_available(self) -> bool:
        """Go 是否可用"""
        return self.go_path.exists()

    def get_version(self) -> str:
        """获取 Go 版本"""
        try:
            result = self.executor.run_sync([str(self.go_path), "version"])
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def build(self, main_file: Path, output: Path) -> bool:
        """编译 Go 程序"""
        if not self.is_available():
            return False
        try:
            result = self.executor.run_sync([
                str(self.go_path), "build", "-o", str(output), str(main_file)
            ])
            return result.returncode == 0
        except Exception:
            return False

    def run(self, main_file: Path) -> subprocess.CompletedProcess:
        """运行 Go 程序"""
        if not self.is_available():
            raise RuntimeError("Go not available")
        return self.executor.run_sync([str(self.go_path), "run", str(main_file)])


# ============= 统一管理器 =============

class SandboxRuntimesManager:
    """
    统一的沙盒运行时管理器

    提供:
    - 运行时检测
    - 环境信息查询
    - 统一执行接口
    """

    def __init__(self):
        self._runtimes: dict[RuntimeType, RuntimeInfo] = {}
        self._refresh()

    def _refresh(self):
        """刷新运行时信息"""
        self._runtimes = RuntimeDetector.detect_all()

    def get_runtime(self, runtime_type: RuntimeType) -> RuntimeInfo:
        """获取运行时信息"""
        return self._runtimes.get(runtime_type)

    def is_installed(self, runtime_type: RuntimeType) -> bool:
        """检查运行时是否已安装"""
        info = self._runtimes.get(runtime_type)
        return info is not None and info.installed

    def is_sandbox(self, runtime_type: RuntimeType) -> bool:
        """检查运行时是否为沙盒模式"""
        info = self._runtimes.get(runtime_type)
        return info is not None and info.is_sandbox

    def get_all_runtimes(self) -> dict[RuntimeType, RuntimeInfo]:
        """获取所有运行时信息"""
        return self._runtimes.copy()

    def get_sandbox_env(self, runtime_type: RuntimeType) -> dict:
        """获取沙盒环境变量"""
        return SandboxEnvBuilder.get_sandbox_env(runtime_type)

    def get_executor(self, runtime_type: RuntimeType) -> SandboxExecutor:
        """获取沙盒执行器"""
        return SandboxExecutor(runtime_type)

    def get_python_executor(self) -> UvExecutor:
        """获取 Python (uv) 执行器"""
        return UvExecutor()

    def get_go_executor(self) -> GoExecutor:
        """获取 Go 执行器"""
        return GoExecutor()

    def get_summary(self) -> dict:
        """获取运行时摘要"""
        summary = {}
        for rt_type, info in self._runtimes.items():
            summary[rt_type.value] = {
                "installed": info.installed,
                "version": info.version,
                "sandbox": info.is_sandbox,
                "install_dir": str(info.install_dir) if info.install_dir else None,
            }
        return summary

    def run_in_sandbox(
        self,
        runtime_type: RuntimeType,
        cmd: list[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        在沙盒环境中执行命令

        Args:
            runtime_type: 运行时类型
            cmd: 命令列表
            cwd: 工作目录
            timeout: 超时秒数

        Returns:
            CompletedProcess: 执行结果
        """
        executor = SandboxExecutor(runtime_type)
        return executor.run_sync(cmd, cwd, timeout)

    async def run_in_sandbox_async(
        self,
        runtime_type: RuntimeType,
        cmd: list[str],
        cwd: Optional[Path] = None
    ) -> asyncio.subprocess.Process:
        """
        异步在沙盒环境中执行命令

        Args:
            runtime_type: 运行时类型
            cmd: 命令列表
            cwd: 工作目录

        Returns:
            Process: 异步进程
        """
        executor = SandboxExecutor(runtime_type)
        return await executor.run_async(cmd, cwd)


# ============= 单例 =============

_sandbox_manager: Optional[SandboxRuntimesManager] = None


def get_sandbox_manager() -> SandboxRuntimesManager:
    """获取沙盒运行时管理器单例"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxRuntimesManager()
    return _sandbox_manager


def get_sandbox_env(runtime_type: RuntimeType) -> dict:
    """快速获取沙盒环境变量"""
    return SandboxEnvBuilder.get_sandbox_env(runtime_type)


def run_in_sandbox(
    runtime_type: RuntimeType,
    cmd: list[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None
) -> subprocess.CompletedProcess:
    """快速在沙盒中执行命令"""
    manager = get_sandbox_manager()
    return manager.run_in_sandbox(runtime_type, cmd, cwd, timeout)
