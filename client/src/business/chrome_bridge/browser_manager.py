"""
浏览器管理器 - 统一管理内置Chromium和外部浏览器
支持：
1. 使用playwright管理内置Chromium（自动下载，体积小）
2. 连接外部浏览器（Chrome/Edge/360/夸克等）
3. 持久化用户会话（cookies, localStorage等）
4. 默认打开深度搜索页面
"""
import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

# 尝试导入playwright
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright未安装，内置Chromium功能不可用")

from .browser_detector import BrowserDetector, BrowserInfo


class BrowserManager:
    """
    浏览器管理器（单例模式）

    功能：
    1. 自动检测并启动外部浏览器（Chrome/Edge/360/夸克等）
    2. 使用playwright管理内置Chromium
    3. 持久化用户数据（cookies, localStorage, 登录状态等）
    4. 默认打开深度搜索页面
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
            self,
            data_dir: Optional[str] = None,
            cdp_port: int = 9222,
            headless: bool = False,
            use_builtin: bool = True
    ):
        """
        初始化浏览器管理器

        Args:
            data_dir: 用户数据目录（持久化cookies等）
            cdp_port: CDP远程调试端口
            headless: 是否无头模式
            use_builtin: 是否优先使用内置Chromium
        """
        if self._initialized:
            return

        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".livingtree" / "browser_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.cdp_port = cdp_port
        self.headless = headless
        self.use_builtin = use_builtin

        # 浏览器进程
        self._external_browser_process = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

        # 状态
        self._mode = None  # "builtin" 或 "external"
        self._browser_info = None

        self._initialized = True

        logger.info(f"BrowserManager初始化完成，数据目录: {self.data_dir}")

    def launch_browser(
            self,
            browser_type: str = "chromium",
            url: Optional[str] = None
    ) -> Dict:
        """
        启动浏览器

        Args:
            browser_type: 浏览器类型 ("chromium", "chrome", "edge", "detect")
                          "detect"表示自动检测外部浏览器
            url: 启动时打开的URL（默认打开深度搜索页面）

        Returns:
            启动结果字典
        """
        # 默认URL：深度搜索页面
        if not url:
            url = "http://localhost:8000/search"  # 假设深度搜索页面地址

        logger.info(f"启动浏览器，类型: {browser_type}")

        # 如果已启动，先关闭
        if self._browser or self._external_browser_process:
            logger.warning("浏览器已启动，先关闭现有实例")
            self.close_browser()

        # 尝试使用内置Chromium
        if self.use_builtin and PLAYWRIGHT_AVAILABLE and browser_type == "chromium":
            return self._launch_builtin_chromium(url)

        # 使用外部浏览器
        if browser_type == "detect":
            return self._launch_external_browser_auto(url)
        else:
            return self._launch_external_browser(browser_type, url)

    def _launch_builtin_chromium(self, url: str) -> Dict:
        """
        启动内置Chromium（使用playwright）

        Args:
            url: 启动时打开的URL

        Returns:
            启动结果
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {
                "success": False,
                "error": "playwright未安装，无法启动内置Chromium",
                "instruction": "请运行: pip install playwright && playwright install chromium"
            }

        try:
            logger.info("启动内置Chromium...")

            self._playwright = sync_playwright().start()

            # 启动Chromium，持久化用户数据
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    f"--remote-debugging-port={self.cdp_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            # 创建持久化上下文（保存cookies, localStorage等）
            self._context = self._browser.contexts[0] if self._browser.contexts else None
            if not self._context:
                # 使用用户数据目录
                user_data_dir = str(self.data_dir / "chromium_profile")
                self._context = self._browser.new_context(
                    user_data_dir=user_data_dir if os.path.exists(user_data_dir) else None
                )

            # 打开页面
            self._page = self._context.new_page()
            self._page.goto(url, timeout=30000)

            self._mode = "builtin"

            # 获取CDP地址
            cdp_url = f"http://localhost:{self.cdp_port}"

            logger.info(f"内置Chromium启动成功，CDP地址: {cdp_url}")

            return {
                "success": True,
                "mode": "builtin",
                "cdp_url": cdp_url,
                "browser_type": "chromium",
                "page_url": self._page.url,
                "message": "内置Chromium启动成功"
            }

        except Exception as e:
            logger.error(f"启动内置Chromium失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _launch_external_browser_auto(self, url: str) -> Dict:
        """
        自动检测并启动外部浏览器

        Args:
            url: 启动时打开的URL

        Returns:
            启动结果
        """
        detector = BrowserDetector()
        default_browser = detector.get_default_browser()

        if not default_browser:
            # 没有检测到浏览器，回退到内置Chromium
            logger.warning("未检测到外部浏览器，尝试使用内置Chromium")
            if PLAYWRIGHT_AVAILABLE:
                return self._launch_builtin_chromium(url)
            else:
                return {
                    "success": False,
                    "error": "未检测到浏览器，且playwright未安装"
                }

        logger.info(f"检测到默认浏览器: {default_browser.name}")
        return self._launch_external_browser_by_info(default_browser, url)

    def _launch_external_browser(self, browser_type: str, url: str) -> Dict:
        """
        启动指定的外部浏览器

        Args:
            browser_type: 浏览器类型 ("chrome", "edge", "360safe", etc.)
            url: 启动时打开的URL

        Returns:
            启动结果
        """
        detector = BrowserDetector()
        browsers = detector.detect_all_browsers()

        # 查找匹配的浏览器
        target_browser = None
        for browser in browsers:
            if browser.browser_type == browser_type:
                target_browser = browser
                break

        if not target_browser:
            # 未找到，尝试自动检测
            logger.warning(f"未找到{browser_type}，尝试自动检测")
            return self._launch_external_browser_auto(url)

        return self._launch_external_browser_by_info(target_browser, url)

    def _launch_external_browser_by_info(self, browser_info: BrowserInfo, url: str) -> Dict:
        """
        根据BrowserInfo启动外部浏览器

        Args:
            browser_info: 浏览器信息
            url: 启动时打开的URL

        Returns:
            启动结果
        """
        try:
            logger.info(f"启动外部浏览器: {browser_info.name} ({browser_info.path})")

            # 构建启动命令
            user_data_dir = str(self.data_dir / browser_info.browser_type)
            cmd = [
                browser_info.path,
                f"--remote-debugging-port={self.cdp_port}",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                url
            ]

            # 启动浏览器进程
            self._external_browser_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self._mode = "external"
            self._browser_info = browser_info

            # 等待浏览器启动
            time.sleep(3)

            # 验证CDP端口
            cdp_url = f"http://localhost:{self.cdp_port}"
            if self._verify_cdp_port():
                logger.info(f"外部浏览器启动成功，CDP地址: {cdp_url}")
                return {
                    "success": True,
                    "mode": "external",
                    "cdp_url": cdp_url,
                    "browser_type": browser_info.browser_type,
                    "browser_name": browser_info.name,
                    "message": f"{browser_info.name}启动成功"
                }
            else:
                logger.error("CDP端口验证失败")
                return {
                    "success": False,
                    "error": "浏览器启动失败或CDP端口不可用"
                }

        except Exception as e:
            logger.error(f"启动外部浏览器失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _verify_cdp_port(self, timeout: int = 10) -> bool:
        """
        验证CDP端口是否可用

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否可用
        """
        import requests

        cdp_url = f"http://localhost:{self.cdp_port}/json/version"

        for _ in range(timeout):
            try:
                response = requests.get(cdp_url, timeout=2)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)

        return False

    def close_browser(self) -> Dict:
        """
        关闭浏览器

        Returns:
            关闭结果
        """
        logger.info("关闭浏览器...")

        try:
            # 关闭内置Chromium
            if self._browser:
                self._browser.close()
                self._browser = None

            if self._playwright:
                self._playwright.stop()
                self._playwright = None

            # 关闭外部浏览器
            if self._external_browser_process:
                self._external_browser_process.terminate()
                self._external_browser_process.wait(timeout=5)
                self._external_browser_process = None

            self._mode = None
            self._browser_info = None

            logger.info("浏览器已关闭")
            return {
                "success": True,
                "message": "浏览器已关闭"
            }

        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_browser_status(self) -> Dict:
        """
        获取浏览器状态

        Returns:
            状态字典
        """
        status = {
            "mode": self._mode,
            "cdp_port": self.cdp_port,
            "headless": self.headless,
            "data_dir": str(self.data_dir)
        }

        if self._mode == "builtin":
            status["browser_type"] = "chromium (builtin)"
            status["playwright_available"] = PLAYWRIGHT_AVAILABLE
            if self._page:
                status["current_url"] = self._page.url
                status["title"] = self._page.title()

        elif self._mode == "external":
            status["browser_type"] = self._browser_info.browser_type if self._browser_info else "unknown"
            status["browser_name"] = self._browser_info.name if self._browser_info else "unknown"
            status["process_running"] = self._external_browser_process.poll() is None if self._external_browser_process else False

        # 检查CDP端口
        status["cdp_available"] = self._verify_cdp_port(timeout=2)

        return status

    def navigate(self, url: str) -> Dict:
        """
        导航到指定URL

        Args:
            url: 目标URL

        Returns:
            导航结果
        """
        if self._mode == "builtin" and self._page:
            try:
                self._page.goto(url, timeout=30000)
                return {
                    "success": True,
                    "url": self._page.url,
                    "title": self._page.title()
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # 外部浏览器，通过CDP导航（需要ChromeBridge支持）
            return {
                "success": False,
                "error": "外部浏览器导航需要通过ChromeBridge实现"
            }

    def get_cdp_url(self) -> Optional[str]:
        """
        获取CDP URL

        Returns:
            CDP URL 或 None
        """
        if self._mode:
            return f"http://localhost:{self.cdp_port}"
        return None

    def ensure_browser_ready(self, url: Optional[str] = None) -> Dict:
        """
        确保浏览器已启动并就绪

        Args:
            url: 如果浏览器未启动，启动时打开的URL

        Returns:
            就绪状态
        """
        # 检查CDP端口
        if self._verify_cdp_port(timeout=2):
            return {
                "success": True,
                "message": "浏览器已就绪",
                "cdp_url": f"http://localhost:{self.cdp_port}"
            }

        # 未启动，自动启动
        logger.info("浏览器未启动，自动启动...")
        return self.launch_browser(browser_type="detect", url=url)


# 便捷函数
def get_browser_manager() -> BrowserManager:
    """获取BrowserManager单例"""
    return BrowserManager()


if __name__ == "__main__":
    # 测试代码
    import time

    print("=" * 60)
    print("测试 BrowserManager")
    print("=" * 60)

    # 1. 创建浏览器管理器
    manager = BrowserManager()

    # 2. 检测浏览器
    print("\n1. 检测系统浏览器...")
    from .browser_detector import detect_browsers

    browsers = detect_browsers()
    print(f"   检测到 {len(browsers)} 个浏览器:")
    for i, browser in enumerate(browsers, 1):
        print(f"   {i}. {browser.name} ({browser.browser_type})")

    # 3. 启动浏览器（自动检测）
    print("\n2. 启动浏览器（自动检测）...")
    result = manager.launch_browser(browser_type="detect")
    print(f"   启动结果: {result}")

    if result.get("success"):
        # 4. 获取状态
        print("\n3. 浏览器状态:")
        status = manager.get_browser_status()
        for key, value in status.items():
            print(f"   {key}: {value}")

        # 5. 等待一段时间
        print("\n4. 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 6. 关闭浏览器
        print("\n5. 关闭浏览器...")
        close_result = manager.close_browser()
        print(f"   关闭结果: {close_result}")
    else:
        print(f"   启动失败: {result.get('error')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
