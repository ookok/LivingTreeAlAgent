"""
Browser Launcher - Chrome 启动/连接器
============================================

负责启动 Chrome（带远程调试端口）或连接已有 Chrome 实例。

核心特性：
- 自动检测系统中 Chrome 安装路径
- 支持复用用户已登录的 Profile（会话复用核心）
- 支持 headed / headless 双模式
- 支持连接已有 Chrome 实例（无需重新启动）
"""

import os
import sys
import time
import subprocess
import requests
from typing import Optional, Dict, List
from pathlib import Path
from loguru import logger


# ============================================================
# Chrome 安装路径检测
# ============================================================

def detect_chrome_path() -> Optional[str]:
    """
    自动检测 Chrome 可执行文件路径

    Returns:
        Chrome 可执行文件路径，未找到返回 None

    检测顺序：
    - Windows: 注册表 → 常见安装路径
    - macOS: /Applications/Google Chrome.app
    - Linux: which google-chrome / chromium-browser
    """
    if sys.platform == "win32":
        return _detect_chrome_windows()
    elif sys.platform == "darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
    elif sys.platform.startswith("linux"):
        for name in ["google-chrome", "chromium-browser", "chromium"]:
            try:
                result = subprocess.run(
                    ["which", name], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
    return None


def _detect_chrome_windows() -> Optional[str]:
    """Windows 下检测 Chrome 路径"""
    # 1. 从注册表读取
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        )
        path, _ = winreg.QueryValueEx(key, None)
        winreg.CloseKey(key)
        if os.path.exists(path):
            return path
    except Exception:
        pass

    # 2. 常见安装路径
    program_files = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local"),
    ]
    for base in program_files:
        for subpath in [
            r"Google\Chrome\Application\chrome.exe",
            r"Chromium\Application\chrome.exe",
        ]:
            full = os.path.join(base, subpath)
            if os.path.exists(full):
                return full

    return None


def detect_chrome_profile_dir() -> Optional[str]:
    """
    自动检测 Chrome 默认 Profile 目录

    Returns:
        默认 Profile 目录路径（如：C:/Users/用户名/AppData/Local/Google/Chrome/User Data/Default）
    """
    if sys.platform == "win32":
        base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif sys.platform.startswith("linux"):
        base = os.path.expanduser("~/.config/google-chrome")
    else:
        return None

    default_profile = os.path.join(base, "Default")
    if os.path.exists(default_profile):
        return default_profile
    return None


def detect_chrome_user_data_dir() -> Optional[str]:
    """
    检测 Chrome User Data 目录（用于 --user-data-dir 参数）

    Returns:
        User Data 目录路径
    """
    if sys.platform == "win32":
        return os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif sys.platform.startswith("linux"):
        return os.path.expanduser("~/.config/google-chrome")
    return None


# ============================================================
# Browser Launcher 主类
# ============================================================

class BrowserLauncher:
    """
    Chrome 启动/连接器

    支持两种模式：
    1. 连接已有实例：检测 localhost:9222 是否有 Chrome 在运行
    2. 启动新实例：以 --remote-debugging-port 启动 Chrome（复用用户 Profile）
    """

    def __init__(
        self,
        chrome_path: Optional[str] = None,
        debug_port: int = 9222,
        user_data_dir: Optional[str] = None,
        profile_dir: Optional[str] = None,
        headless: bool = False,
    ):
        """
        初始化浏览器启动器

        Args:
            chrome_path: Chrome 可执行文件路径（自动检测若未提供）
            debug_port: 远程调试端口（默认 9222）
            user_data_dir: Chrome User Data 目录（复用用户 Profile）
            profile_dir: 特定 Profile 目录（如 "Default", "Profile 1"）
            headless: 是否以 headless 模式启动
        """
        self.chrome_path = chrome_path or detect_chrome_path()
        self.debug_port = debug_port
        self.user_data_dir = user_data_dir or detect_chrome_user_data_dir()
        self.profile_dir = profile_dir  # "Default" 或 "Profile 1" 等
        self.headless = headless
        self._process: Optional[subprocess.Popen] = None

        if not self.chrome_path:
            logger.bind(module="BrowserLauncher").warning(
                "未检测到 Chrome 安装路径，请手动指定"
            )

    # ============================================================
    # 连接已有实例
    # ============================================================

    def is_chrome_running(self, host: str = "localhost") -> bool:
        """
        检测是否已有 Chrome 在远程调试模式下运行

        Args:
            host: Chrome 调试主机（默认 localhost）

        Returns:
            是否已有 Chrome 在运行
        """
        try:
            resp = requests.get(f"http://{host}:{self.debug_port}/json/version", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def get_running_chrome_info(self, host: str = "localhost") -> Optional[Dict]:
        """
        获取运行中 Chrome 的信息

        Returns:
            Chrome 版本信息字典，未运行返回 None
        """
        try:
            resp = requests.get(f"http://{host}:{self.debug_port}/json/version", timeout=2)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ============================================================
    # 启动新实例
    # ============================================================

    def launch(
        self,
        url: Optional[str] = None,
        extra_args: Optional[List[str]] = None
    ) -> subprocess.Popen:
        """
        启动 Chrome（带远程调试端口）

        Args:
            url: 启动时打开的 URL（可选）
            extra_args: 额外启动参数

        Returns:
            subprocess.Popen 对象

        Raises:
            RuntimeError: Chrome 路径未找到或启动失败
        """
        if not self.chrome_path:
            raise RuntimeError(
                "Chrome 路径未找到，请安装 Chrome 或手动指定 chrome_path"
            )

        if self.is_chrome_running():
            logger.bind(module="BrowserLauncher").info(
                f"Chrome 已在运行（端口 {self.debug_port}），无需重新启动"
            )
            return self._process

        cmd = [self.chrome_path]

        # 远程调试端口（会话复用核心）
        cmd.append(f"--remote-debugging-port={self.debug_port}")

        # 复用用户 Profile（登录状态复用核心）
        if self.user_data_dir:
            cmd.append(f"--user-data-dir={self.user_data_dir}")

        # 指定 Profile（如 "Default", "Profile 1"）
        if self.profile_dir:
            profile_name = os.path.basename(self.profile_dir)
            cmd.append(f"--profile-directory={profile_name}")

        # Headless 模式
        if self.headless:
            cmd.append("--headless=new")
            cmd.append("--disable-gpu")

        # 常用优化参数
        cmd.extend([
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-breakpad",
            "--disable-client-side-phishing-detection",
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-features=TranslateUI",
            "--disable-extensions",
            "--disable-features=BlinkGenPropertyTrees",
            "--disable-hang-monitor",
            "--disable-ipc-flooding-protection",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-renderer-backgrounding",
            "--disable-sync",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--no-first-run",
            "--enable-automation",   # 注意：这会设置 navigator.webdriver = true
            "--password-store=basic",
            "--use-mock-keychain",
        ])

        # 注意：--enable-automation 会暴露自动化特征
        # 我们通过 JS 注入覆盖 navigator.webdriver，所以保留此参数
        # 如果追求极致隐蔽，可以移除 --enable-automation（但需要额外处理）

        if url:
            cmd.append(url)

        if extra_args:
            cmd.extend(extra_args)

        logger.bind(module="BrowserLauncher").info(
            f"启动 Chrome: {' '.join(cmd[:3])}..."
        )

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

        # 等待 Chrome 启动完成
        self._wait_for_chrome_ready()

        logger.bind(module="BrowserLauncher").info(
            f"Chrome 已启动（PID: {self._process.pid}，端口: {self.debug_port}）"
        )

        return self._process

    def _wait_for_chrome_ready(self, timeout: int = 15):
        """
        等待 Chrome 远程调试端口就绪

        Args:
            timeout: 超时时间（秒）

        Raises:
            TimeoutError: Chrome 启动超时
        """
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.is_chrome_running():
                return
            time.sleep(0.5)
        raise TimeoutError(f"Chrome 启动超时（{timeout}s）")

    # ============================================================
    # 关闭
    # ============================================================

    def close(self):
        """关闭启动的 Chrome 进程"""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                logger.bind(module="BrowserLauncher").info("Chrome 进程已关闭")
            except Exception as e:
                logger.bind(module="BrowserLauncher").error(f"关闭 Chrome 失败: {e}")
            finally:
                self._process = None

    def __del__(self):
        self.close()

    # ============================================================
    # 静态工具方法
    # ============================================================

    @staticmethod
    def launch_headless(
        debug_port: int = 9223,
        user_data_dir: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        快速启动 headless Chrome（静态方法）

        Args:
            debug_port: 远程调试端口
            user_data_dir: 用户数据目录（复用登录状态）

        Returns:
            subprocess.Popen 对象
        """
        launcher = BrowserLauncher(
            debug_port=debug_port,
            user_data_dir=user_data_dir,
            headless=True,
        )
        return launcher.launch()

    @staticmethod
    def launch_headed(
        debug_port: int = 9222,
        user_data_dir: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        快速启动 headed Chrome（静态方法）

        Args:
            debug_port: 远程调试端口
            user_data_dir: 用户数据目录（复用登录状态）

        Returns:
            subprocess.Popen 对象
        """
        launcher = BrowserLauncher(
            debug_port=debug_port,
            user_data_dir=user_data_dir,
            headless=False,
        )
        return launcher.launch()


# ============================================================
# 全局单例
# ============================================================

_launcher_instance: Optional[BrowserLauncher] = None


def get_browser_launcher(
    chrome_path: Optional[str] = None,
    debug_port: int = 9222,
    headless: bool = False,
) -> BrowserLauncher:
    """获取全局 BrowserLauncher 实例"""
    global _launcher_instance
    if _launcher_instance is None:
        _launcher_instance = BrowserLauncher(
            chrome_path=chrome_path,
            debug_port=debug_port,
            headless=headless,
        )
    return _launcher_instance
