"""
Chrome Bridge - Chrome 浏览器桥接核心
============================================

将会话复用、反检测、网站适配器集成在一起，
提供简洁的 API 供外部调用。

核心工作流程：
1. 连接/启动 Chrome（会话复用）
2. 导航到目标 URL
3. 应用反检测措施
4. 使用对应网站的适配器提取内容
5. 返回结构化结果

支持：
- 直接连接已有 Chrome（localhost:9222）
- 启动新 Chrome 实例（复用用户 Profile）
- 使用内置 Chromium（playwright，自动下载）
- 自动检测外部浏览器（Chrome/Edge/360/夸克等）
- Headed / Headless 双模式
- 80+ 网站适配器自动匹配
"""

import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
from loguru import logger

from client.src.business.chrome_bridge.cdp_helper import CDPHelper, CDPPage, get_cdp_helper
from client.src.business.chrome_bridge.browser_launcher import BrowserLauncher, get_browser_launcher
from client.src.business.chrome_bridge.anti_detection import AntiDetectionEngine, get_anti_detection_engine
from client.src.business.chrome_bridge.website_adapter_base import BaseWebsiteAdapter
from client.src.business.chrome_bridge.website_adapter_registry import get_adapter_registry
from client.src.business.chrome_bridge.utils.cookie_manager import CookieManager, get_cookie_manager

# 导入新的 BrowserManager
try:
    from client.src.business.chrome_bridge.browser_manager import BrowserManager
    BROWSER_MANAGER_AVAILABLE = True
except ImportError:
    BROWSER_MANAGER_AVAILABLE = False
    logger.warning("BrowserManager 未安装，内置 Chromium 功能不可用")


class ChromeBridge:
    """
    Chrome 桥接器（核心类）

    统一管理和协调：
    - CDPHelper（CDP 通信）
    - BrowserLauncher（Chrome 启动/连接）
    - AntiDetectionEngine（反检测）
    - Website Adapter（网站适配器）
    - CookieManager（Cookie 管理）
    """

    def __init__(
        self,
        debug_port: int = 9222,
        headless: bool = False,
        auto_launch: bool = True,
        anti_detection_level: str = "normal",
        use_builtin_chromium: bool = False,
    ):
        """
        初始化 Chrome 桥接器

        Args:
            debug_port: Chrome 远程调试端口（默认 9222）
            headless: 是否以 headless 模式启动（仅当 auto_launch=True 时有效）
            auto_launch: 若 Chrome 未运行，是否自动启动
            anti_detection_level: 反检测级别（"normal" | "strict" | "stealth"）
            use_builtin_chromium: 是否使用内置 Chromium（playwright，自动下载）
        """
        self.debug_port = debug_port
        self.headless = headless
        self.auto_launch = auto_launch
        self.use_builtin_chromium = use_builtin_chromium

        # 核心组件
        self._cdp = get_cdp_helper(debug_port=debug_port)
        
        # 选择启动器：内置 Chromium 或 外部浏览器
        if use_builtin_chromium and BROWSER_MANAGER_AVAILABLE:
            self._launcher = None  # 使用 BrowserManager
            self._browser_manager = BrowserManager(
                cdp_port=debug_port,
                headless=headless,
                use_builtin=True
            )
            logger.bind(module="ChromeBridge").info("使用内置 Chromium（BrowserManager）")
        else:
            self._launcher = get_browser_launcher(
                debug_port=debug_port, headless=headless
            )
            self._browser_manager = None
        
        self._anti = get_anti_detection_engine(cdp_helper=self._cdp)
        self._anti.set_level(anti_detection_level)
        self._cookie_mgr = get_cookie_manager()
        self._registry = get_adapter_registry()

        self._current_page_id: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.bind(module="ChromeBridge").info(
            f"ChromeBridge 初始化完成（端口: {debug_port}，"
            f"反检测级别: {anti_detection_level}，"
            f"内置Chromium: {use_builtin_chromium}）"
        )

    # ============================================================
    # 连接/启动 Chrome
    # ============================================================

    async def connect(self, launch_if_needed: bool = None) -> bool:
        """
        连接或启动 Chrome

        Args:
            launch_if_needed: 是否自动启动（覆盖初始化设置）

        Returns:
            是否成功连接
        """
        launch_if_needed = launch_if_needed if launch_if_needed is not None else self.auto_launch
        
        # 1. 尝试连接已有实例
        try:
            pages = self._cdp.discover_pages()
            if pages:
                logger.bind(module="ChromeBridge").info(
                    f"已连接到运行中的 Chrome（{len(pages)} 个页面）"
                )
                return True
        except ConnectionError:
            pass

        # 2. 自动启动
        if launch_if_needed:
            logger.bind(module="ChromeBridge").info("正在启动 Chrome...")
            
            # 使用 BrowserManager（内置 Chromium）
            if self.use_builtin_chromium and self._browser_manager:
                result = await asyncio.to_thread(
                    self._browser_manager.launch_browser,
                    "chromium"
                )
                if result.get("success"):
                    logger.bind(module="ChromeBridge").info("内置 Chromium 启动成功")
                    await asyncio.sleep(2)
                    return True
                else:
                    logger.bind(module="ChromeBridge").error(
                        f"内置 Chromium 启动失败: {result.get('error')}"
                    )
                    return False
            
            # 使用传统 BrowserLauncher
            else:
                try:
                    self._launcher.launch(headless=self.headless)
                    # 等待启动完成
                    await asyncio.sleep(2)
                    # 验证连接
                    pages = self._cdp.discover_pages()
                    logger.bind(module="ChromeBridge").info(
                        f"Chrome 启动成功（{len(pages)} 个页面）"
                    )
                    return True
                except Exception as e:
                    logger.bind(module="ChromeBridge").error(f"Chrome 启动失败: {e}")
                    return False
        else:
            logger.bind(module="ChromeBridge").error(
                "Chrome 未运行，且 auto_launch=False"
            )
            return False

    # ============================================================
    # 导航 & 页面操作
    # ============================================================

    async def navigate(
        self,
        url: str,
        adapter_name: Optional[str] = None,
        apply_anti_detection: bool = True,
    ) -> Dict[str, Any]:
        """
        导航到指定 URL，并应用反检测和适配器

        Args:
            url: 目标 URL
            adapter_name: 指定适配器名称（可选，自动匹配若未指定）
            apply_anti_detection: 是否应用反检测

        Returns:
            页面信息字典
        """
        # 确保已连接
        if not await self.connect():
            raise RuntimeError("无法连接到 Chrome")

        # 获取或创建页面
        page = self._cdp.get_or_create_page(url)
        self._current_page_id = page.id

        # 连接到页面 WebSocket
        await self._cdp.connect_page(page.id)

        # 应用反检测
        if apply_anti_detection:
            await self._anti.apply_to_page(page.id, url)

        # 导航到 URL
        await self._cdp.navigate(page.id, url)

        # 等待页面加载完成
        await asyncio.sleep(2)  # 简单等待，可优化为等待网络空闲

        result = {
            "page_id": page.id,
            "url": url,
            "title": await self._cdp.evaluate(page.id, "document.title"),
            "status": "loaded",
        }

        logger.bind(module="ChromeBridge").info(f"导航完成: {url}")
        return result

    # ============================================================
    # 内容提取（通过适配器）
    # ============================================================

    async def extract_content(
        self,
        url: Optional[str] = None,
        adapter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用适配器提取页面内容

        Args:
            url: 目标 URL（若未指定，使用当前页面）
            adapter_name: 指定适配器（可选，自动匹配）

        Returns:
            提取的内容（结构化字典）
        """
        if not self._current_page_id:
            if not url:
                raise ValueError("需要指定 URL 或先调用 navigate()")
            await self.navigate(url, adapter_name=adapter_name)

        page_id = self._current_page_id
        url = url or await self._cdp.evaluate(page_id, "location.href")

        # 查找匹配的适配器
        adapter = None
        if adapter_name:
            adapter = self._registry.get_adapter(adapter_name)
        else:
            adapter = self._registry.find_adapter_for_url(url)

        if not adapter:
            # 无匹配适配器，使用通用提取
            logger.bind(module="ChromeBridge").warning(
                f"未找到 {url} 的适配器，使用通用提取"
            )
            return await self._generic_extract(page_id, url)

        # 使用适配器提取
        logger.bind(module="ChromeBridge").info(
            f"使用适配器: {adapter.get_name()}"
        )
        return await adapter.extract(self._cdp, page_id, url)

    async def _generic_extract(self, page_id: str, url: str) -> Dict[str, Any]:
        """通用内容提取（无适配器时）"""
        html = await self._cdp.get_content(page_id)
        text = await self._cdp.get_text(page_id)
        title = await self._cdp.evaluate(page_id, "document.title")

        return {
            "url": url,
            "title": title,
            "html": html[:5000],  # 限制长度
            "text": text[:2000],
            "extractor": "generic",
        }

    # ============================================================
    # 表单操作 & 元素交互
    # ============================================================

    async def type_text(self, page_id: str, selector: str, text: str, delay: float = 0.1) -> bool:
        """
        向指定元素输入文本（模拟人工输入）

        Args:
            page_id: 页面ID
            selector: CSS选择器
            text: 要输入的文本
            delay: 字符输入间隔（秒），模拟人工输入速度

        Returns:
            是否输入成功
        """
        try:
            # 先点击元素获取焦点
            await self._cdp.evaluate(
                page_id,
                f"document.querySelector('{selector}')?.click(); true;"
            )
            await asyncio.sleep(0.3)

            # 逐个字符输入（模拟人工）
            for char in text:
                await self._cdp.send_command(
                    page_id,
                    "Input.dispatchKeyEvent",
                    {
                        "type": "char",
                        "text": char,
                        "unmodifiedText": char,
                        "commands": []
                    }
                )
                await asyncio.sleep(delay)

            logger.bind(module="ChromeBridge").debug(f"成功输入文本到: {selector}")
            return True
        except Exception as e:
            logger.bind(module="ChromeBridge").error(f"输入文本失败: {e}")
            return False

    async def click_element(self, page_id: str, selector: str, timeout: float = 5.0) -> bool:
        """
        点击指定元素

        Args:
            page_id: 页面ID
            selector: CSS选择器
            timeout: 等待元素出现的超时时间（秒）

        Returns:
            是否点击成功
        """
        try:
            # 等待元素出现
            await asyncio.wait_for(
                self._wait_for_selector(page_id, selector),
                timeout=timeout
            )

            # 点击元素
            result = await self._cdp.evaluate(
                page_id,
                f"""
                (function() {{
                    const el = document.querySelector('{selector}');
                    if (el) {{
                        el.scrollIntoView({{block: 'center'}});
                        el.click();
                        return true;
                    }}
                    return false;
                }})();
                """
            )

            if result:
                logger.bind(module="ChromeBridge").debug(f"成功点击元素: {selector}")
                return True
            else:
                logger.bind(module="ChromeBridge").warning(f"未找到元素: {selector}")
                return False
        except asyncio.TimeoutError:
            logger.bind(module="ChromeBridge").warning(f"等待元素超时: {selector}")
            return False
        except Exception as e:
            logger.bind(module="ChromeBridge").error(f"点击元素失败: {e}")
            return False

    async def fill_login_form(
        self,
        page_id: str,
        username: str,
        password: str,
        username_selector: str,
        password_selector: str,
        login_button_selector: str,
        extra_selectors: Dict[str, str] = None
    ) -> bool:
        """
        填写登录表单并点击登录按钮

        Args:
            page_id: 页面ID
            username: 用户名
            password: 密码
            username_selector: 用户名输入框选择器
            password_selector: 密码输入框选择器
            login_button_selector: 登录按钮选择器
            extra_selectors: 额外的表单字段（如验证码、记住我等）

        Returns:
            是否登录成功（仅表示操作完成，不表示登录状态）
        """
        try:
            # 1. 填写用户名
            logger.bind(module="ChromeBridge").info("正在填写用户名...")
            if not await self.type_text(page_id, username_selector, username):
                raise RuntimeError(f"无法找到用户名输入框: {username_selector}")

            await asyncio.sleep(0.5)

            # 2. 填写密码
            logger.bind(module="ChromeBridge").info("正在填写密码...")
            if not await self.type_text(page_id, password_selector, password):
                raise RuntimeError(f"无法找到密码输入框: {password_selector}")

            await asyncio.sleep(0.5)

            # 3. 处理额外字段
            if extra_selectors:
                for field_name, (selector, value) in extra_selectors.items():
                    logger.bind(module="ChromeBridge").info(f"正在填写额外字段: {field_name}")
                    if isinstance(value, str):
                        await self.type_text(page_id, selector, value)
                    elif value is True:  # 勾选框
                        await self.click_element(page_id, selector)
                    await asyncio.sleep(0.3)

            # 4. 点击登录按钮
            logger.bind(module="ChromeBridge").info("正在点击登录按钮...")
            if not await self.click_element(page_id, login_button_selector):
                raise RuntimeError(f"无法找到登录按钮: {login_button_selector}")

            # 等待登录完成
            await asyncio.sleep(3)
            logger.bind(module="ChromeBridge").info("登录表单填写完成")
            return True

        except Exception as e:
            logger.bind(module="ChromeBridge").error(f"填写登录表单失败: {e}")
            return False

    async def _wait_for_selector(self, page_id: str, selector: str, timeout: float = 5.0):
        """等待选择器对应的元素出现"""
        js = f"""
        new Promise((resolve, reject) => {{
            const startTime = Date.now();
            const check = () => {{
                if (document.querySelector('{selector}')) {{
                    resolve(true);
                }} else if (Date.now() - startTime > {timeout * 1000}) {{
                    reject(new Error('等待元素超时'));
                }} else {{
                    setTimeout(check, 100);
                }}
            }};
            check();
        }})
        """
        await self._cdp.evaluate(page_id, js)

    # ============================================================
    # 登录状态检测
    # ============================================================

    async def check_login(self, url: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        """
        检测指定网站的登录状态

        Args:
            url: 目标网站 URL
            adapter_name: 指定适配器（可选）

        Returns:
            登录状态字典 {"logged_in": bool, "username": str, ...}
        """
        adapter = None
        if adapter_name:
            adapter = self._registry.get_adapter(adapter_name)
        else:
            adapter = self._registry.find_adapter_for_url(url)

        if not adapter:
            return {"logged_in": None, "reason": "无匹配适配器"}

        # 确保已导航到该网站
        current_url = await self._cdp.evaluate(self._current_page_id, "location.href")
        if url not in current_url:
            await self.navigate(url, adapter_name=adapter_name)

        return await adapter.check_login(self._cdp, self._current_page_id)

    # ============================================================
    # Cookie 管理（会话复用）
    # ============================================================

    async def save_session(self, filepath: str, urls: List[str] = None):
        """
        保存当前会话的 Cookie 到文件

        Args:
            filepath: 保存路径（JSON 格式）
            urls: 限制保存的 URL（可选）
        """
        if not self._current_page_id:
            raise ValueError("没有活动的页面")

        cookies = await self._cookie_mgr.fetch_from_cdp(
            self._cdp, self._current_page_id, urls
        )
        self._cookie_mgr.export_to_json(cookies, filepath)
        logger.bind(module="ChromeBridge").info(f"会话已保存: {filepath}")

    async def restore_session(self, filepath: str):
        """
        从文件恢复会话（注入 Cookie）

        Args:
            filepath: Cookie 文件路径（JSON 格式）
        """
        if not self._current_page_id:
            raise ValueError("没有活动的页面")

        cookies = self._cookie_mgr.import_from_json(filepath)
        await self._cookie_mgr.inject_via_cdp(
            self._cdp, self._current_page_id, cookies
        )
        logger.bind(module="ChromeBridge").info(f"会话已恢复: {filepath}")

    # ============================================================
    # 截图
    # ============================================================

    async def screenshot(
        self,
        filepath: Optional[str] = None,
        format: str = "png"
    ) -> bytes:
        """
        对当前页面截图

        Args:
            filepath: 保存路径（可选，不提供则返回二进制数据）
            format: 图片格式（"png" | "jpeg"）

        Returns:
            图片二进制数据
        """
        if not self._current_page_id:
            raise ValueError("没有活动的页面")

        data = await self._cdp.take_screenshot(self._current_page_id, format=format)

        if filepath:
            with open(filepath, "wb") as f:
                f.write(data)
            logger.bind(module="ChromeBridge").info(f"截图已保存: {filepath}")

        return data

    # ============================================================
    # 关闭
    # ============================================================

    async def close(self):
        """关闭所有连接和启动的 Chrome 进程"""
        # 关闭 CDP 连接
        for page_id in list(self._cdp._ws_connections.keys()):
            await self._cdp.disconnect_page(page_id)
        
        # 关闭传统启动器
        if self._launcher:
            self._launcher.close()
        
        # 关闭 BrowserManager
        if self._browser_manager:
            await asyncio.to_thread(self._browser_manager.close_browser)
        
        logger.bind(module="ChromeBridge").info("ChromeBridge 已关闭")

    # ============================================================
    # 上下文管理器
    # ============================================================

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ============================================================
# 全局单例
# ============================================================

_bridge_instance: Optional[ChromeBridge] = None


def get_chrome_bridge(
    debug_port: int = 9222,
    headless: bool = False,
    anti_detection_level: str = "normal",
    use_builtin_chromium: bool = False,
) -> ChromeBridge:
    """
    获取全局 ChromeBridge 实例

    Args:
        debug_port: CDP 端口
        headless: 是否无头模式
        anti_detection_level: 反检测级别
        use_builtin_chromium: 是否使用内置 Chromium

    Returns:
        ChromeBridge 实例
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ChromeBridge(
            debug_port=debug_port,
            headless=headless,
            anti_detection_level=anti_detection_level,
            use_builtin_chromium=use_builtin_chromium,
        )
    return _bridge_instance
