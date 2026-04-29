"""
跨平台抽象层 - Platform Abstraction Layer

支持平台：Windows、macOS、Linux
统一接口：进程管理、文件路径、环境变量、系统命令

使用示例：
    from core.platform import platform, run_async, get_temp_dir

    # 获取平台信息
    print(platform.name)        # "windows" / "darwin" / "linux"
    print(platform.is_windows) # True on Windows
    print(platform.arch)       # "x64" / "arm64"

    # 获取跨平台路径
    temp = platform.get_temp_dir()
    cache = platform.get_cache_dir()
    config = platform.get_config_dir()

    # 异步执行
    result = await platform.run_async(["git", "status"])
"""

import os
import sys
import asyncio
import subprocess
import platform as _platform_module
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from functools import lru_cache


# ============================================================================
# 平台检测
# ============================================================================

@dataclass
class PlatformInfo:
    """平台信息"""
    name: str           # "windows", "darwin", "linux"
    is_windows: bool
    is_mac: bool
    is_linux: bool
    arch: str          # "x64", "arm64", "armv7l"
    version: str        # OS version string
    python_path_sep: str  # 路径分隔符
    python_exe: str    # Python 可执行文件路径
    home_dir: Path      # 用户主目录
    temp_dir: Path      # 临时目录


def get_platform_info() -> PlatformInfo:
    """
    获取平台信息（带缓存）

    Returns:
        PlatformInfo: 平台信息
    """
    system = _platform_module.system().lower()

    if system == "windows":
        name = "windows"
    elif system == "darwin":
        name = "darwin"
    else:
        name = "linux"

    # 架构
    arch = _platform_module.machine().lower()
    if arch in ("amd64", "x86_64"):
        arch = "x64"
    elif arch in ("arm64", "aarch64"):
        arch = "arm64"
    elif arch in ("armv7l", "armhf"):
        arch = "arm"

    # 版本
    try:
        if name == "windows":
            version = _platform_module.win32_ver()[0] or ""
        elif name == "darwin":
            version = _platform_module.mac_ver()[0] or ""
        else:
            version = _platform_module.linux_distribution()[0] if hasattr(_platform_module, "linux_distribution") else ""
    except Exception:
        version = ""

    # 主目录
    home = Path.home()

    # 临时目录
    if name == "windows":
        temp = Path(os.environ.get("TEMP", str(home / "AppData" / "Local" / "Temp")))
    elif name == "darwin":
        temp = Path("/tmp")
    else:
        temp = Path("/tmp")

    return PlatformInfo(
        name=name,
        is_windows=name == "windows",
        is_mac=name == "darwin",
        is_linux=name == "linux",
        arch=arch,
        version=version,
        python_path_sep=";" if name == "windows" else ":",
        python_exe=sys.executable,
        home_dir=home,
        temp_dir=temp,
    )


# 全局平台信息
_platform: Optional[PlatformInfo] = None


def get_platform() -> PlatformInfo:
    """获取全局平台信息"""
    global _platform
    if _platform is None:
        _platform = get_platform_info()
    return _platform


# ============================================================================
# 路径抽象
# ============================================================================

class PlatformPaths:
    """
    跨平台路径管理器

    统一各平台的：
    - 配置目录
    - 缓存目录
    - 数据目录
    - 日志目录
    """

    def __init__(self, app_name: str = "hermes-desktop"):
        self.app_name = app_name
        self._platform = get_platform()

    @property
    def platform(self) -> PlatformInfo:
        return self._platform

    @property
    def config_dir(self) -> Path:
        """获取配置目录"""
        if self._platform.is_windows:
            return self._platform.home_dir / "AppData" / "Roaming" / self.app_name
        elif self._platform.is_mac:
            return self._platform.home_dir / "Library" / "Application Support" / self.app_name
        else:
            config_home = os.environ.get("XDG_CONFIG_HOME", str(self._platform.home_dir / ".config"))
            return Path(config_home) / self.app_name

    @property
    def cache_dir(self) -> Path:
        """获取缓存目录"""
        if self._platform.is_windows:
            return self._platform.home_dir / "AppData" / "Local" / self.app_name / "Cache"
        elif self._platform.is_mac:
            return self._platform.home_dir / "Library" / "Caches" / self.app_name
        else:
            cache_home = os.environ.get("XDG_CACHE_HOME", str(self._platform.home_dir / ".cache"))
            return Path(cache_home) / self.app_name

    @property
    def data_dir(self) -> Path:
        """获取数据目录"""
        if self._platform.is_windows:
            return self._platform.home_dir / "AppData" / "Local" / self.app_name
        elif self._platform.is_mac:
            return self._platform.home_dir / "Library" / "Application Support" / self.app_name
        else:
            data_home = os.environ.get("XDG_DATA_HOME", str(self._platform.home_dir / ".local" / "share"))
            return Path(data_home) / self.app_name

    @property
    def log_dir(self) -> Path:
        """获取日志目录"""
        return self.data_dir / "logs"

    @property
    def temp_dir(self) -> Path:
        """获取临时目录"""
        return self._platform.temp_dir / self.app_name

    def ensure_dirs(self):
        """确保所有必要目录存在"""
        for d in [self.config_dir, self.cache_dir, self.data_dir, self.log_dir, self.temp_dir]:
            d.mkdir(parents=True, exist_ok=True)
        return self

    def get_path(self, path_type: str = "config") -> Path:
        """
        获取指定类型的路径

        Args:
            path_type: "config" | "cache" | "data" | "log" | "temp"
        """
        return getattr(self, f"{path_type}_dir")


# ============================================================================
# 进程管理
# ============================================================================

class ProcessManager:
    """
    跨平台进程管理器

    支持：
    - 同步/异步执行
    - 环境变量传递
    - 工作目录设置
    - 超时控制
    """

    def __init__(self):
        self._platform = get_platform()

    def run_sync(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        同步执行命令

        Args:
            cmd: 命令列表
            cwd: 工作目录
            env: 环境变量
            timeout: 超时秒数
            shell: 是否使用 shell

        Returns:
            subprocess.CompletedProcess
        """
        try:
            return subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                timeout=timeout,
                shell=shell,
                capture_output=True,
                text=True,
                encoding="utf-8" if not self._platform.is_windows else "gbk",
            )
        except UnicodeDecodeError:
            # Windows GBK 解码失败，尝试 binary 模式
            result = subprocess.run(
                cmd, cwd=cwd, env=env, timeout=timeout, shell=shell, capture_output=True
            )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=result.returncode,
                stdout=result.stdout.decode("gbk", errors="replace") if result.stdout else "",
                stderr=result.stderr.decode("gbk", errors="replace") if result.stderr else "",
            )

    async def run_async(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        shell: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        异步执行命令

        Args:
            cmd: 命令列表
            cwd: 工作目录
            env: 环境变量
            timeout: 超时秒数
            shell: 是否使用 shell

        Returns:
            subprocess.CompletedProcess
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=shell,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Command timed out: {' '.join(cmd)}")

    def kill_process(self, pid: int) -> bool:
        """
        终止进程

        Args:
            pid: 进程 ID

        Returns:
            bool: 是否成功
        """
        try:
            if self._platform.is_windows:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
            else:
                os.kill(pid, 9)
            return True
        except Exception:
            return False


# ============================================================================
# 系统信息
# ============================================================================

class SystemInfo:
    """系统信息获取"""

    def __init__(self):
        self._platform = get_platform()
        self._psutil = None  # 延迟导入

    @property
    def cpu_count(self) -> int:
        """CPU 核心数"""
        try:
            import psutil
            return psutil.cpu_count() or os.cpu_count() or 1
        except ImportError:
            return os.cpu_count() or 1

    @property
    def memory_total(self) -> int:
        """总内存（字节）"""
        try:
            import psutil
            return psutil.virtual_memory().total
        except ImportError:
            return 0

    @property
    def memory_available(self) -> int:
        """可用内存（字节）"""
        try:
            import psutil
            return psutil.virtual_memory().available
        except ImportError:
            return 0

    def disk_usage(self, path: str = "/") -> Dict[str, int]:
        """磁盘使用情况"""
        try:
            import psutil
            usage = psutil.disk_usage(path)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        except ImportError:
            return {"total": 0, "used": 0, "free": 0, "percent": 0}


# ============================================================================
# 全局实例
# ============================================================================

# 延迟初始化，避免循环导入
_platform_instance: Optional[PlatformPaths] = None
_process_manager: Optional[ProcessManager] = None
_system_info: Optional[SystemInfo] = None


def get_platform_paths(app_name: str = "hermes-desktop") -> PlatformPaths:
    """获取路径管理器"""
    global _platform_instance
    if _platform_instance is None:
        _platform_instance = PlatformPaths(app_name)
        _platform_instance.ensure_dirs()
    return _platform_instance


def get_process_manager() -> ProcessManager:
    """获取进程管理器"""
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager


def get_system_info() -> SystemInfo:
    """获取系统信息"""
    global _system_info
    if _system_info is None:
        _system_info = SystemInfo()
    return _system_info


# 便捷访问
platform = get_platform()
paths = get_platform_paths()
process = get_process_manager()
sysinfo = get_system_info()
