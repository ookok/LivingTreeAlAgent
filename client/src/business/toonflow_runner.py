"""
Toonflow Service Runner - Toonflow 进程管理器

管理 Toonflow Node.js 进程的启动、停止、监控
支持使用沙盒化的 Node.js 运行时，不依赖系统安装
"""

import asyncio
import logging
import os
import platform
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# ============= 常量 =============

DEFAULT_PORT = 60001
DEFAULT_TIMEOUT = 30


@dataclass
class ToonflowRunnerConfig:
    """Runner 配置"""
    toonflow_dir: Optional[str] = None  # Toonflow 安装目录
    nodejs_runtime_dir: Optional[str] = None  # Node.js 沙盒目录
    port: int = DEFAULT_PORT
    node_version: str = "24"
    env: Optional[dict] = None
    log_file: Optional[str] = None
    use_sandbox_node: bool = True  # 是否使用沙盒 Node.js


class ToonflowRunner:
    """
    Toonflow 进程管理器

    功能:
    - 自动检测/安装 Toonflow
    - 启动/停止 API 服务
    - 进程监控与自动重启
    - 健康检查
    """

    def __init__(self, config: Optional[ToonflowRunnerConfig] = None):
        self.config = config or ToonflowRunnerConfig()
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._startup_event: asyncio.Event = asyncio.Event()
        self._status_callback: Optional[Callable[[str], None]] = None

    # ── 路径检测 ─────────────────────────────────────────────────────

    def _get_toonflow_dir(self) -> Optional[Path]:
        """获取 Toonflow 目录"""
        if self.config.toonflow_dir:
            return Path(self.config.toonflow_dir)

        # 从工具目录查找
        base = Path(os.environ.get("HERMES_TOOLS", "~/.hermes-desktop/tools")).expanduser()
        candidates = [
            base / "Toonflow-app",
            base / "toonflow_app",
            base / "Toonflow",
        ]
        for cand in candidates:
            if cand.exists() and (cand / "package.json").exists():
                return cand

        return None

    def _get_nodejs_runtime_dir(self) -> Optional[Path]:
        """获取 Node.js 沙盒目录"""
        if self.config.nodejs_runtime_dir:
            return Path(self.config.nodejs_runtime_dir)

        # 从工具目录查找
        base = Path(os.environ.get("HERMES_TOOLS", "~/.hermes-desktop/tools")).expanduser()
        candidates = [
            base / "nodejs_runtime",
            base / "nodejs-runtime",
        ]
        for cand in candidates:
            if cand.exists():
                # 检查是否有 node 二进制
                if platform.system() == "Windows":
                    node_exe = cand / "bin" / "node.exe"
                else:
                    node_exe = cand / "bin" / "node"
                if node_exe.exists():
                    return cand

        return None

    def _get_node_path(self) -> str:
        """获取 Node.js 路径"""
        # 优先使用沙盒 Node.js
        if self.config.use_sandbox_node:
            nodejs_dir = self._get_nodejs_runtime_dir()
            if nodejs_dir:
                if platform.system() == "Windows":
                    node_path = nodejs_dir / "bin" / "node.exe"
                else:
                    node_path = nodejs_dir / "bin" / "node"
                if node_path.exists():
                    return str(node_path)

        # 备选：nvm 或 volta
        for env_var in ["NVM_HOME", "VOLTA_HOME", "NODEENV_HOME"]:
            node_home = os.environ.get(env_var)
            if node_home:
                node_exe = Path(node_home) / "node.exe"
                if node_exe.exists():
                    return str(node_exe)

        # 系统 node
        return "node"

    def _get_yarn_path(self) -> str:
        """获取 Yarn 路径"""
        # 优先使用沙盒 Node.js 中的 npm
        if self.config.use_sandbox_node:
            nodejs_dir = self._get_nodejs_runtime_dir()
            if nodejs_dir:
                yarn_path = nodejs_dir / "bin" / "yarn"
                if platform.system() == "Windows":
                    yarn_path = nodejs_dir / "bin" / "yarn.cmd"
                if yarn_path.exists():
                    return str(yarn_path)

        # 备选：系统 yarn
        return "yarn"

    def _get_sandbox_env(self) -> dict:
        """
        构造沙盒环境变量，让 Toonflow 使用我们的 Node.js

        Returns:
            dict: 沙盒环境变量
        """
        env = os.environ.copy()
        nodejs_dir = self._get_nodejs_runtime_dir()

        # 1. 将沙盒 Node 加入 PATH 首位
        if nodejs_dir:
            sep = ";" if platform.system() == "Windows" else ":"
            bin_dir = str(nodejs_dir / "bin")
            env["PATH"] = f"{bin_dir}{sep}{env.get('PATH', '')}"

            # 2. 设置 npm/yarn 配置目录到项目内（防全局污染）
            env["NPM_CONFIG_USERCONFIG"] = str(nodejs_dir / ".npmrc")
            env["YARN_RC_FILENAME"] = str(nodejs_dir / ".yarnrc.yml")

            # 3. 全局缓存也挪进来（避免占用 C 盘）
            cache_dir = Path(os.environ.get("HERMES_CACHE", "~/.hermes-desktop/cache"))
            cache_dir.mkdir(parents=True, exist_ok=True)
            env["NPM_CONFIG_CACHE"] = str(cache_dir / "npm")
            env["YARN_CACHE_FOLDER"] = str(cache_dir / "yarn")

        # 4. 强制使用沙盒 Node
        env["NODE_PATH"] = str(nodejs_dir / "lib" / "node_modules") if nodejs_dir else ""

        return env

    # ── 环境检测 ─────────────────────────────────────────────────────

    async def check_environment(self) -> dict:
        """
        检查运行环境

        Returns:
            dict: 环境状态 {"node": bool, "yarn": bool, "toonflow": bool, "port": int}
        """
        status = {
            "node": False,
            "node_sandbox": False,
            "yarn": False,
            "toonflow": False,
            "toonflow_dir": None,
            "nodejs_runtime_dir": None,
            "port": self.config.port,
            "issues": [],
        }

        # 检查沙盒 Node.js
        nodejs_dir = self._get_nodejs_runtime_dir()
        if nodejs_dir:
            status["nodejs_runtime_dir"] = str(nodejs_dir)
            sandbox_node = self._get_node_path()
            if sandbox_node != "node":
                try:
                    proc = await asyncio.create_subprocess_exec(
                        sandbox_node, "--version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await proc.communicate()
                    version = stdout.decode().strip()
                    status["node_sandbox"] = True
                    status["node"] = True
                    status["node_version"] = version

                    # 检查版本
                    major = int(version.lstrip("v").split(".")[0])
                    if major < 24:
                        status["issues"].append(f"沙盒 Node.js {version} 不满足最低要求 v24")
                except Exception as e:
                    status["issues"].append(f"沙盒 Node.js 不可用: {e}")

        # 检查系统 Node（备选）
        if not status["node"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "node", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                version = stdout.decode().strip()
                status["node"] = True
                status["node_version"] = version

                # 检查版本
                major = int(version.lstrip("v").split(".")[0])
                if major < 24:
                    status["issues"].append(f"Node.js {version} 不满足最低要求 v24")
            except Exception as e:
                status["issues"].append(f"Node.js 未安装: {e}")

        # 检查 Yarn
        yarn_path = self._get_yarn_path()
        try:
            proc = await asyncio.create_subprocess_exec(
                yarn_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            status["yarn"] = True
            status["yarn_version"] = stdout.decode().strip()
        except Exception:
            status["issues"].append("Yarn 未安装")

        # 检查 Toonflow
        toonflow_dir = self._get_toonflow_dir()
        if toonflow_dir:
            status["toonflow"] = True
            status["toonflow_dir"] = str(toonflow_dir)

            # 检查依赖
            node_modules = toonflow_dir / "node_modules"
            if not node_modules.exists():
                status["issues"].append("Toonflow 依赖未安装，需要运行 yarn install")
        else:
            status["issues"].append("Toonflow 未安装")

        return status

    # ── 安装 ─────────────────────────────────────────────────────

    async def install(self, verbose: bool = True) -> bool:
        """
        安装 Toonflow

        Args:
            verbose: 是否输出详细日志

        Returns:
            bool: 安装是否成功
        """
        toonflow_dir = self._get_toonflow_dir()

        if toonflow_dir is None:
            # 创建目录
            base = Path(os.environ.get("HERMES_TOOLS", "~/.hermes-desktop/tools")).expanduser()
            toonflow_dir = base / "Toonflow-app"
            toonflow_dir.parent.mkdir(parents=True, exist_ok=True)

            # Git clone
            logger.info(f"Cloning Toonflow from GitHub...")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone",
                    "https://github.com/HBAI-Ltd/Toonflow-app.git",
                    str(toonflow_dir),
                    stdout=asyncio.subprocess.PIPE if not verbose else None,
                    stderr=asyncio.subprocess.PIPE if not verbose else None,
                )
                await proc.communicate()
                if proc.returncode != 0:
                    logger.error("Git clone failed")
                    return False
            except Exception as e:
                logger.error(f"Git clone failed: {e}")
                return False

        # 使用沙盒环境
        sandbox_env = self._get_sandbox_env()
        yarn_path = self._get_yarn_path()

        # Yarn install
        logger.info("Installing dependencies...")
        try:
            proc = await asyncio.create_subprocess_exec(
                yarn_path, "install",
                cwd=str(toonflow_dir),
                env=sandbox_env,
                stdout=asyncio.subprocess.PIPE if not verbose else None,
                stderr=asyncio.subprocess.PIPE if not verbose else None,
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Yarn install failed: {e}")
            return False

    # ── 服务控制 ─────────────────────────────────────────────────────

    async def start(self, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        启动 Toonflow API 服务

        Args:
            timeout: 启动超时秒数

        Returns:
            bool: 启动是否成功
        """
        if self._running and self._process:
            logger.warning("Toonflow is already running")
            return True

        toonflow_dir = self._get_toonflow_dir()
        if not toonflow_dir:
            logger.error("Toonflow not found")
            return False

        # 检查依赖
        if not (toonflow_dir / "node_modules").exists():
            logger.warning("Dependencies not installed, installing...")
            success = await self.install(verbose=False)
            if not success:
                logger.error("Dependency installation failed")
                return False

        # 构建沙盒环境
        env = self._get_sandbox_env()
        env["NODE_ENV"] = "production"
        env["PORT"] = str(self.config.port)
        if self.config.env:
            env.update(self.config.env)

        # 使用沙盒 Node.js 启动
        node_path = self._get_node_path()

        # 启动命令：使用 node 运行 yarn 或直接运行 API
        if self.config.use_sandbox_node and node_path != "node":
            # 方式1: 通过 yarn 启动
            yarn_path = self._get_yarn_path()
            start_cmd = [yarn_path, "start:api"]
        else:
            # 方式2: 直接用 node 运行
            start_cmd = ["yarn", "start:api"]

        try:
            self._process = await asyncio.create_subprocess_exec(
                *start_cmd,
                cwd=str(toonflow_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._pid = self._process.pid
            self._running = True

            logger.info(f"Toonflow started with PID {self._pid}")

            # 等待服务就绪
            await self._wait_for_ready(timeout)

            # 启动监控
            self._monitor_task = asyncio.create_task(self._monitor_process())

            return True

        except Exception as e:
            logger.error(f"Failed to start Toonflow: {e}")
            self._running = False
            return False

    async def stop(self) -> bool:
        """
        停止 Toonflow 服务

        Returns:
            bool: 停止是否成功
        """
        if not self._running or not self._process:
            return True

        try:
            # 停止监控
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

            # 发送停止信号
            if sys.platform == "win32":
                # Windows: 使用 taskkill
                proc = await asyncio.create_subprocess_exec(
                    "taskkill", "/F", "/PID", str(self._pid),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            else:
                # Unix: 发送 SIGTERM
                self._process.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()

            logger.info(f"Toonflow (PID {self._pid}) stopped")
            self._running = False
            self._process = None
            self._pid = None
            return True

        except Exception as e:
            logger.error(f"Error stopping Toonflow: {e}")
            return False

    async def restart(self) -> bool:
        """重启服务"""
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    async def _wait_for_ready(self, timeout: int) -> bool:
        """等待服务就绪"""
        import httpx

        start_time = asyncio.get_event_loop().time()
        url = f"http://localhost:{self.config.port}/api/health"

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        logger.info("Toonflow service is ready")
                        self._startup_event.set()
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.5)

        logger.warning(f"Toonflow service did not become ready within {timeout}s")
        return False

    async def _monitor_process(self):
        """监控子进程"""
        if not self._process:
            return

        while self._running:
            try:
                # 检查进程是否退出
                returncode = await self._process.poll()
                if returncode is not None:
                    logger.warning(f"Toonflow process exited with code {returncode}")
                    self._running = False
                    self._startup_event.clear()

                    # 回调
                    if self._status_callback:
                        self._status_callback("stopped")

                    break

                await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                break

    # ── 状态查询 ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """服务是否运行中"""
        return self._running

    @property
    def pid(self) -> Optional[int]:
        """进程 PID"""
        return self._pid

    def set_status_callback(self, callback: Callable[[str], None]):
        """设置状态回调"""
        self._status_callback = callback


# ============= 全局单例 =============

_toonflow_runner: Optional[ToonflowRunner] = None


def get_toonflow_runner(config: Optional[ToonflowRunnerConfig] = None) -> ToonflowRunner:
    """获取全局 ToonflowRunner 实例"""
    global _toonflow_runner
    if _toonflow_runner is None:
        _toonflow_runner = ToonflowRunner(config)
    return _toonflow_runner
