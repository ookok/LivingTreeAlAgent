"""
浏览器检测器 - 自动检测系统上安装的Chromium系浏览器
支持：Chrome, Edge, 360安全浏览器, 360极速浏览器, 夸克浏览器等
"""
import os
import sys
import platform
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BrowserInfo:
    """浏览器信息类"""

    def __init__(self, name: str, path: str, version: str = "", browser_type: str = "chromium"):
        self.name = name
        self.path = path
        self.version = version
        self.browser_type = browser_type  # chromium, chrome, edge, etc.

    def __repr__(self):
        return f"BrowserInfo(name='{self.name}', path='{self.path}', type='{self.browser_type}')"

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "browser_type": self.browser_type
        }


class BrowserDetector:
    """浏览器检测器"""

    # Windows 注册表路径
    WINDOWS_REG_PATHS = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
    ]

    # 常见浏览器可执行文件名
    BROWSER_EXECUTABLES = {
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "360safe": "360se.exe",  # 360安全浏览器
        "360speed": "360chrome.exe",  # 360极速浏览器
        "quark": "Quark.exe",  # 夸克浏览器
        "brave": "brave.exe",
        "opera": "opera.exe",
        "vivaldi": "vivaldi.exe",
    }

    # 常见安装路径 (Windows)
    WINDOWS_COMMON_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Users\{username}\AppData\Local\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{username}\AppData\Local\Microsoft\Edge\Application\msedge.exe",
        r"C:\Users\{username}\AppData\Local\360 safe\360 se\Application\360se.exe",
        r"C:\Users\{username}\AppData\Local\360Chrome\Chrome\Application\360chrome.exe",
        r"C:\Users\{username}\AppData\Local\Quark\Quark.exe",
    ]

    # 常见安装路径 (macOS)
    MACOS_COMMON_PATHS = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]

    # 常见安装路径 (Linux)
    LINUX_COMMON_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/snap/bin/chromium",
    ]

    def __init__(self):
        self.system = platform.system().lower()  # windows, darwin, linux
        self.detected_browsers: List[BrowserInfo] = []

    def detect_all_browsers(self) -> List[BrowserInfo]:
        """
        检测系统上安装的所有Chromium系浏览器

        Returns:
            浏览器信息列表
        """
        self.detected_browsers = []

        if self.system == "windows":
            self._detect_windows()
        elif self.system == "darwin":
            self._detect_macos()
        elif self.system == "linux":
            self._detect_linux()

        logger.info(f"检测到 {len(self.detected_browsers)} 个浏览器:")
        for browser in self.detected_browsers:
            logger.info(f"  - {browser}")

        return self.detected_browsers

    def _detect_windows(self):
        """检测Windows上的浏览器"""
        # 方法1: 检查常见安装路径
        username = os.getenv("USERNAME", "")
        for path_template in self.WINDOWS_COMMON_PATHS:
            path = path_template.format(username=username)
            if os.path.exists(path):
                browser_info = self._identify_browser(path)
                if browser_info:
                    self.detected_browsers.append(browser_info)

        # 方法2: 检查PATH环境变量
        self._check_path_executables()

    def _detect_macos(self):
        """检测macOS上的浏览器"""
        for path in self.MACOS_COMMON_PATHS:
            if os.path.exists(path):
                browser_info = self._identify_browser(path)
                if browser_info:
                    self.detected_browsers.append(browser_info)

        # 检查 /Applications 目录
        self._check_macos_applications()

    def _detect_linux(self):
        """检测Linux上的浏览器"""
        for path in self.LINUX_COMMON_PATHS:
            if os.path.exists(path):
                browser_info = self._identify_browser(path)
                if browser_info:
                    self.detected_browsers.append(browser_info)

        # 检查 which 命令
        self._check_which_executables()

    def _identify_browser(self, path: str) -> Optional[BrowserInfo]:
        """
        识别浏览器类型

        Args:
            path: 浏览器可执行文件路径

        Returns:
            BrowserInfo 或 None
        """
        path_lower = path.lower()

        if "chrome" in path_lower and "360" not in path_lower:
            if "edge" in path_lower:
                return BrowserInfo("Microsoft Edge", path, browser_type="edge")
            return BrowserInfo("Google Chrome", path, browser_type="chrome")
        elif "360se" in path_lower or "360 safe" in path_lower:
            return BrowserInfo("360安全浏览器", path, browser_type="360safe")
        elif "360chrome" in path_lower or "360 speed" in path_lower:
            return BrowserInfo("360极速浏览器", path, browser_type="360speed")
        elif "quark" in path_lower:
            return BrowserInfo("夸克浏览器", path, browser_type="quark")
        elif "brave" in path_lower:
            return BrowserInfo("Brave浏览器", path, browser_type="brave")
        elif "opera" in path_lower:
            return BrowserInfo("Opera浏览器", path, browser_type="opera")
        elif "vivaldi" in path_lower:
            return BrowserInfo("Vivaldi浏览器", path, browser_type="vivaldi")

        return None

    def _check_path_executables(self):
        """检查PATH中的可执行文件"""
        if self.system == "windows":
            executables = ["chrome.exe", "msedge.exe"]
        else:
            executables = ["google-chrome", "chromium", "microsoft-edge"]

        for exe in executables:
            path = self._which(exe)
            if path:
                browser_info = self._identify_browser(path)
                if browser_info and not self._is_duplicate(browser_info.path):
                    self.detected_browsers.append(browser_info)

    def _check_which_executables(self):
        """使用which命令检查可执行文件"""
        import subprocess

        executables = ["google-chrome", "chromium-browser", "chromium", "microsoft-edge"]
        for exe in executables:
            try:
                result = subprocess.run(["which", exe], capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip()
                    browser_info = self._identify_browser(path)
                    if browser_info and not self._is_duplicate(browser_info.path):
                        self.detected_browsers.append(browser_info)
            except Exception:
                pass

    def _check_macos_applications(self):
        """检查macOS的/Applications目录"""
        import subprocess

        try:
            result = subprocess.run(
                ["ls", "/Applications"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                apps = result.stdout.strip().split("\n")
                for app in apps:
                    if "Chrome" in app or "Edge" in app or "Brave" in app:
                        app_path = f"/Applications/{app}/Contents/MacOS/{app.replace('.app', '')}"
                        # 简化路径处理
                        if "Chrome" in app:
                            app_path = f"/Applications/{app}/Contents/MacOS/Google Chrome"
                        elif "Edge" in app:
                            app_path = f"/Applications/{app}/Contents/MacOS/Microsoft Edge"

                        if os.path.exists(app_path):
                            browser_info = self._identify_browser(app_path)
                            if browser_info and not self._is_duplicate(browser_info.path):
                                self.detected_browsers.append(browser_info)
        except Exception as e:
            logger.warning(f"检查macOS应用程序失败: {e}")

    def _which(self, executable: str) -> Optional[str]:
        """
        模拟which命令

        Args:
            executable: 可执行文件名

        Returns:
            完整路径或None
        """
        import subprocess

        try:
            if self.system == "windows":
                result = subprocess.run(["where", executable], capture_output=True, text=True)
            else:
                result = subprocess.run(["which", executable], capture_output=True, text=True)

            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]  # 取第一个结果
        except Exception:
            pass

        return None

    def _is_duplicate(self, path: str) -> bool:
        """
        检查是否已检测到该浏览器（去重）

        Args:
            path: 浏览器路径

        Returns:
            是否重复
        """
        for browser in self.detected_browsers:
            if self._normalize_path(browser.path) == self._normalize_path(path):
                return True
        return False

    def _normalize_path(self, path: str) -> str:
        """标准化路径（转为小写，去除结尾的.exe）"""
        path = path.lower()
        if path.endswith(".exe"):
            path = path[:-4]
        return path

    def get_default_browser(self) -> Optional[BrowserInfo]:
        """
        获取默认浏览器（优先返回Chrome或Edge）

        Returns:
            默认浏览器信息
        """
        if not self.detected_browsers:
            self.detect_all_browsers()

        # 优先级: Chrome > Edge > 其他
        priority_order = ["chrome", "edge", "brave", "360speed", "360safe", "quark"]

        for browser_type in priority_order:
            for browser in self.detected_browsers:
                if browser.browser_type == browser_type:
                    return browser

        # 如果没有优先浏览器，返回第一个
        return self.detected_browsers[0] if self.detected_browsers else None

    def is_browser_supported(self, browser_info: BrowserInfo) -> bool:
        """
        检查浏览器是否支持远程调试（CDP）

        Args:
            browser_info: 浏览器信息

        Returns:
            是否支持
        """
        # 所有Chromium内核的浏览器都支持 --remote-debugging-port 参数
        supported_types = ["chrome", "edge", "chromium", "brave", "opera", "vivaldi", "360speed", "quark"]
        return browser_info.browser_type in supported_types


def detect_browsers() -> List[BrowserInfo]:
    """
    便捷函数：检测系统上的所有浏览器

    Returns:
        浏览器信息列表
    """
    detector = BrowserDetector()
    return detector.detect_all_browsers()


def get_default_browser() -> Optional[BrowserInfo]:
    """
    便捷函数：获取默认浏览器

    Returns:
        默认浏览器信息
    """
    detector = BrowserDetector()
    return detector.get_default_browser()


if __name__ == "__main__":
    # 测试代码
    print("正在检测系统浏览器...")
    browsers = detect_browsers()

    print(f"\n检测到 {len(browsers)} 个浏览器:")
    for i, browser in enumerate(browsers, 1):
        print(f"{i}. {browser.name} - {browser.path}")

    print("\n默认浏览器:")
    default = get_default_browser()
    if default:
        print(f"  {default.name} - {default.path}")
        print(f"  支持远程调试: {BrowserDetector().is_browser_supported(default)}")
