"""
Chrome Bridge Tool - Chrome桥接工具封装
==============================================

将ChromeBridge封装为BaseTool，支持：
- 导航到指定URL
- 自动登录（使用加密凭证）
- 提取页面内容
- 截图
- 语义驱动的操作指令执行

注册到ToolRegistry后，可通过HermesAgent统一调用
"""
import asyncio
import json
import base64
import re
from typing import Dict, Any, Optional
from loguru import logger

from business.tools.base_tool import BaseTool, AgentCallResult
from business.tools.tool_registry import ToolRegistry, ToolDefinition
from business.chrome_bridge.chrome_bridge import ChromeBridge, get_chrome_bridge
from business.chrome_bridge.credential_manager import get_credential_manager
from business.chrome_bridge.website_adapter_registry import get_adapter_registry


# 模块级单例（避免重复创建）
_chrome_bridge_tool_instance = None


def get_chrome_bridge_tool():
    """获取ChromeBridgeTool单例"""
    global _chrome_bridge_tool_instance
    if _chrome_bridge_tool_instance is None:
        _chrome_bridge_tool_instance = ChromeBridgeTool()
    return _chrome_bridge_tool_instance


def handle_chrome_bridge(action: str, **kwargs) -> Dict[str, Any]:
    """ChromeBridgeTool的调用入口（供ToolRegistry使用）"""
    tool = get_chrome_bridge_tool()
    return tool.execute(action, **kwargs)


class ChromeBridgeTool(BaseTool):
    """Chrome桥接工具，支持会话复用、自动登录、内容提取"""

    # 类级常量（对应BaseTool的抽象属性）
    TOOL_NAME = "chrome_bridge"
    TOOL_DESCRIPTION = "通过CDP桥接Chrome浏览器，支持会话复用、自动登录、内容提取、语义操作"
    TOOL_CATEGORY = "web_automation"
    TOOL_VERSION = "1.0.0"

    @property
    def name(self) -> str:
        return self.TOOL_NAME

    @property
    def description(self) -> str:
        return self.TOOL_DESCRIPTION

    @property
    def category(self) -> str:
        return self.TOOL_CATEGORY

    @property
    def version(self) -> str:
        return self.TOOL_VERSION

    @property
    def node_type(self) -> str:
        return "ai"  # 语义操作需要调用LLM

    def __init__(
        self,
        debug_port: int = 9222,
        headless: bool = False,
        anti_detection_level: str = "normal"
    ):
        """
        初始化Chrome桥接工具

        Args:
            debug_port: Chrome远程调试端口
            headless: 是否无头模式
            anti_detection_level: 反检测级别
        """
        # 先调用父类初始化（此时会访问self.name等@property）
        super().__init__()

        self.debug_port = debug_port
        self.headless = headless
        self.anti_detection_level = anti_detection_level

        # 延迟初始化ChromeBridge（避免启动时无Chrome报错）
        self._bridge: Optional[ChromeBridge] = None
        self._credential_mgr = get_credential_manager()
        self._adapter_registry = get_adapter_registry()

        # 注册支持的动作
        self.supported_actions = [
            "navigate", "login", "extract", "screenshot",
            "semantic_operate", "check_login", "save_session", "restore_session",
            "launch_browser", "close_browser", "browser_status"  # 新增：浏览器管理
        ]

        logger.bind(tool="ChromeBridgeTool").info("Chrome桥接工具初始化完成")

    def _get_bridge(self) -> ChromeBridge:
        """获取或创建ChromeBridge实例"""
        if self._bridge is None:
            self._bridge = get_chrome_bridge(
                debug_port=self.debug_port,
                headless=self.headless,
                anti_detection_level=self.anti_detection_level
            )
        return self._bridge

    def _run_async(self, coroutine):
        """运行异步操作（兼容同步调用）"""
        try:
            return asyncio.run(coroutine)
        except RuntimeError as e:
            logger.bind(tool="ChromeBridgeTool").warning(f"asyncio.run() 失败: {e}")
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coroutine)
                    return future.result(timeout=120)
            else:
                return loop.run_until_complete(coroutine)

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        执行指定动作

        Args:
            action: 动作名称，支持：
                   - navigate: 导航到URL
                   - login: 自动登录
                   - extract: 提取页面内容
                   - screenshot: 截图
                   - semantic_operate: 语义驱动操作
                   - check_login: 检查登录状态
                   - save_session: 保存会话
                   - restore_session: 恢复会话
            **kwargs: 动作特定参数

        Returns:
            执行结果字典（AgentCallResult的to_dict()输出）
        """
        if action not in self.supported_actions:
            return AgentCallResult.error(
                error=f"不支持的动作: {action}，支持的动作: {self.supported_actions}"
            ).to_dict()

        try:
            if action == "navigate":
                result = self._run_async(self._do_navigate(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            elif action == "login":
                result = self._run_async(self._do_login(**kwargs))
                return result  # _do_login已返回AgentCallResult.to_dict()
            elif action == "extract":
                result = self._run_async(self._do_extract(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            elif action == "screenshot":
                result = self._run_async(self._do_screenshot(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            elif action == "semantic_operate":
                result = self._run_async(self._do_semantic_operate(**kwargs))
                return result  # _do_semantic_operate已返回AgentCallResult.to_dict()
            elif action == "check_login":
                result = self._run_async(self._do_check_login(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            elif action == "save_session":
                result = self._run_async(self._do_save_session(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            elif action == "restore_session":
                result = self._run_async(self._do_restore_session(**kwargs))
                return AgentCallResult.success(data=result).to_dict()
            # 新增：浏览器管理功能
            elif action == "launch_browser":
                result = self._launch_browser(**kwargs)
                return AgentCallResult.success(data=result).to_dict()
            elif action == "close_browser":
                result = self._close_browser()
                return AgentCallResult.success(data=result).to_dict()
            elif action == "browser_status":
                result = self._get_browser_status()
                return AgentCallResult.success(data=result).to_dict()
            else:
                return AgentCallResult.error(error=f"动作未实现: {action}").to_dict()
        except Exception as e:
            error_msg = f"执行动作 {action} 失败: {str(e)}"
            logger.bind(tool="ChromeBridgeTool").error(error_msg)
            return AgentCallResult.error(error=error_msg).to_dict()

    async def _do_navigate(self, url: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        """导航到指定URL"""
        bridge = self._get_bridge()
        result = await bridge.navigate(url, adapter_name=adapter_name)
        return result

    async def _do_login(
        self,
        domain: Optional[str] = None,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        username_selector: Optional[str] = None,
        password_selector: Optional[str] = None,
        login_button_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """自动登录指定网站"""
        bridge = self._get_bridge()

        # 1. 确定域名
        if not domain and url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc

        if not domain:
            return AgentCallResult.error(error="需要指定domain或url参数").to_dict()

        # 2. 获取凭证（优先使用参数提供的凭证）
        if not username or not password:
            cred = self._credential_mgr.load_credential(domain)
            if not cred:
                return AgentCallResult.error(
                    error=f"未找到域名 {domain} 的凭证，请先保存凭证"
                ).to_dict()
            username, password = cred

        # 3. 获取登录选择器（优先使用参数提供的选择器）
        if not all([username_selector, password_selector, login_button_selector]):
            adapter = self._adapter_registry.find_adapter_for_url(f"https://{domain}")
            if adapter:
                selectors = adapter.get_login_selectors()
                username_selector = username_selector or selectors.get("username")
                password_selector = password_selector or selectors.get("password")
                login_button_selector = login_button_selector or selectors.get("login_button")

        if not all([username_selector, password_selector, login_button_selector]):
            return AgentCallResult.error(
                error="无法获取登录表单选择器，请手动提供或完善适配器"
            ).to_dict()

        # 4. 导航到登录页面（如果未提供URL，使用适配器的登录URL）
        if url:
            await bridge.navigate(url)
        else:
            adapter = self._adapter_registry.find_adapter_for_url(f"https://{domain}")
            if adapter and adapter.get_login_url():
                await bridge.navigate(adapter.get_login_url())
            else:
                return AgentCallResult.error(
                    error="未提供登录URL且适配器未定义登录URL"
                ).to_dict()

        # 5. 填写登录表单
        login_success = await bridge.fill_login_form(
            page_id=bridge._current_page_id,
            username=username,
            password=password,
            username_selector=username_selector,
            password_selector=password_selector,
            login_button_selector=login_button_selector
        )

        if login_success:
            # 检查登录状态
            login_status = await bridge.check_login(f"https://{domain}")
            return AgentCallResult.success(
                data={
                    "logged_in": login_status.get("logged_in", False),
                    "username": login_status.get("username"),
                    "message": "登录成功"
                }
            ).to_dict()
        else:
            return AgentCallResult.error(error="登录表单填写失败").to_dict()

    async def _do_extract(
        self,
        url: Optional[str] = None,
        adapter_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """提取页面内容"""
        bridge = self._get_bridge()
        result = await bridge.extract_content(url=url, adapter_name=adapter_name)
        return result

    async def _do_screenshot(
        self,
        filepath: Optional[str] = None,
        format: str = "png"
    ) -> Dict[str, Any]:
        """截图"""
        bridge = self._get_bridge()
        data = await bridge.screenshot(filepath=filepath, format=format)

        result = {"format": format, "size": len(data)}
        if filepath:
            result["filepath"] = filepath
        else:
            result["data_base64"] = base64.b64encode(data).decode("utf-8")

        return result

    async def _do_semantic_operate(
        self,
        instruction: str,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """语义驱动操作：使用LLM理解自然语言指令，自动操作网页"""
        bridge = self._get_bridge()

        # 导航到目标URL（如果提供）
        if url:
            await bridge.navigate(url)

        page_id = bridge._current_page_id
        if not page_id:
            return AgentCallResult.error(error="没有活动的页面").to_dict()

        # 1. 获取页面可交互元素信息
        elements_js = """
        (function() {
            const elements = [];
            // 输入框
            document.querySelectorAll('input, textarea').forEach(el => {
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    id: el.id || '',
                    name: el.name || '',
                    placeholder: el.placeholder || '',
                    class: el.className || '',
                    selector: el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`
                });
            });
            // 按钮
            document.querySelectorAll('button, [role="button"], input[type="submit"]').forEach(el => {
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    id: el.id || '',
                    text: el.innerText || el.value || '',
                    class: el.className || '',
                    selector: el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`
                });
            });
            // 链接
            document.querySelectorAll('a').forEach(el => {
                if (el.innerText.trim()) {
                    elements.push({
                        tag: 'a',
                        id: el.id || '',
                        text: el.innerText.trim().substring(0, 50),
                        href: el.href || '',
                        class: el.className || '',
                        selector: el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`
                    });
                }
            });
            return elements;
        })();
        """

        elements = await bridge._cdp.evaluate(page_id, elements_js)

        # 2. 调用LLM生成操作序列
        from business.global_model_router import get_model_router

        router = get_model_router()
        prompt = f"""
        你是一个网页操作助手，需要根据用户的自然语言指令，生成一系列操作序列。

        ## 可用元素信息：
        {json.dumps(elements, ensure_ascii=False, indent=2)}

        ## 用户指令：
        {instruction}

        ## 要求：
        1. 生成操作序列，每个操作包含：action（类型）、selector（CSS选择器）、value（可选值）
        2. 支持的操作类型：type（输入文本）、click（点击元素）、wait（等待秒数）
        3. 只返回JSON数组，不要有其他内容

        示例输出：
        [
            {{"action": "type", "selector": "#username", "value": "myuser"}},
            {{"action": "type", "selector": "#password", "value": "mypass"}},
            {{"action": "click", "selector": "#login-btn"}},
            {{"action": "wait", "value": 3}}
        ]
        """

        llm_response = await router.acall_model(
            capability="reasoning",
            prompt=prompt,
            temperature=0.1
        )

        # 解析LLM返回的操作序列
        try:
            # 提取JSON部分
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if not json_match:
                raise ValueError("LLM返回中未找到JSON数组")
            operations = json.loads(json_match.group(0))
        except Exception as e:
            return AgentCallResult.error(
                error=f"解析LLM操作序列失败: {e}，LLM返回: {llm_response}"
            ).to_dict()

        # 3. 执行操作序列
        for op in operations:
            action = op.get("action")
            selector = op.get("selector")
            value = op.get("value", "")

            if action == "type":
                await bridge.type_text(page_id, selector, value)
                await asyncio.sleep(0.5)
            elif action == "click":
                await bridge.click_element(page_id, selector)
                await asyncio.sleep(1)
            elif action == "wait":
                await asyncio.sleep(float(value))
            else:
                logger.bind(tool="ChromeBridgeTool").warning(f"未知操作类型: {action}")

        return AgentCallResult.success(
            data={
                "operations_executed": len(operations),
                "operations": operations
            }
        ).to_dict()

    async def _do_check_login(self, url: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        """检查登录状态"""
        bridge = self._get_bridge()
        result = await bridge.check_login(url, adapter_name=adapter_name)
        return result

    async def _do_save_session(self, filepath: str) -> Dict[str, Any]:
        """保存会话"""
        bridge = self._get_bridge()
        await bridge.save_session(filepath)
        return {"filepath": filepath}

    async def _do_restore_session(self, filepath: str) -> Dict[str, Any]:
        """恢复会话"""
        bridge = self._get_bridge()
        await bridge.restore_session(filepath)
        return {"filepath": filepath}

    # ============================================================
    # 浏览器管理功能（新增）
    # ============================================================

    def _launch_browser(
        self,
        browser_type: str = "detect",
        url: Optional[str] = None,
        headless: bool = False,
        use_builtin: bool = False
    ) -> Dict[str, Any]:
        """
        启动浏览器

        Args:
            browser_type: 浏览器类型 (chromium/chrome/edge/detect)
            url: 启动时打开的URL
            headless: 是否无头模式
            use_builtin: 是否使用内置Chromium

        Returns:
            启动结果
        """
        logger.bind(tool="ChromeBridgeTool").info(f"启动浏览器: {browser_type}, 内置: {use_builtin}")

        try:
            # 方法1: 使用 BrowserManager（如果可用）
            try:
                from business.chrome_bridge.browser_manager import BrowserManager

                browser_manager = BrowserManager(
                    cdp_port=self.debug_port,
                    headless=headless,
                    use_builtin=use_builtin
                )

                result = browser_manager.launch_browser(
                    browser_type=browser_type,
                    url=url or "http://localhost:8000/search"  # 默认打开深度搜索页面
                )

                if result.get("success"):
                    # 同时更新ChromeBridge实例
                    self.anti_detection_level = "normal"  # 重置反检测级别
                    self._bridge = None  # 强制重新创建ChromeBridge

                return result

            except ImportError:
                logger.bind(tool="ChromeBridgeTool").warning("BrowserManager不可用，使用传统方式")

            # 方法2: 使用传统ChromeBridge
            self.headless = headless
            bridge = self._get_bridge()

            # 如果指定了use_builtin，需要重新创建bridge
            if use_builtin:
                from business.chrome_bridge.chrome_bridge import ChromeBridge
                self._bridge = ChromeBridge(
                    debug_port=self.debug_port,
                    headless=headless,
                    anti_detection_level=self.anti_detection_level,
                    use_builtin_chromium=True
                )

            # 导航到URL（如果提供）
            if url:
                import asyncio
                asyncio.run(bridge.navigate(url))

            return {
                "success": True,
                "mode": "traditional",
                "message": "浏览器启动成功（传统模式）"
            }

        except Exception as e:
            error_msg = f"启动浏览器失败: {e}"
            logger.bind(tool="ChromeBridgeTool").error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def _close_browser(self) -> Dict[str, Any]:
        """
        关闭浏览器

        Returns:
            关闭结果
        """
        logger.bind(tool="ChromeBridgeTool").info("关闭浏览器")

        try:
            # 关闭ChromeBridge启动的浏览器
            if self._bridge:
                import asyncio
                asyncio.run(self._bridge.close())
                self._bridge = None

            return {
                "success": True,
                "message": "浏览器已关闭"
            }

        except Exception as e:
            error_msg = f"关闭浏览器失败: {e}"
            logger.bind(tool="ChromeBridgeTool").error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def _get_browser_status(self) -> Dict[str, Any]:
        """
        获取浏览器状态

        Returns:
            状态字典
        """
        try:
            # 尝试使用 BrowserManager
            try:
                from business.chrome_bridge.browser_manager import BrowserManager

                browser_manager = BrowserManager()
                status = browser_manager.get_browser_status()

                return status

            except ImportError:
                pass

            # 使用传统方式检查
            import requests

            try:
                response = requests.get(f"http://localhost:{self.debug_port}/json/version", timeout=2)
                if response.status_code == 200:
                    return {
                        "cdp_available": True,
                        "cdp_url": f"http://localhost:{self.debug_port}",
                        "browser_info": response.json()
                    }
            except Exception:
                pass

            return {
                "cdp_available": False,
                "message": "浏览器未运行"
            }

        except Exception as e:
            return {
                "error": str(e)
            }


def register_chrome_bridge_tool():
    """注册Chrome Bridge工具到ToolRegistry"""
    tool_def = ToolDefinition(
        name=ChromeBridgeTool.TOOL_NAME,
        description=ChromeBridgeTool.TOOL_DESCRIPTION,
        handler=handle_chrome_bridge,  # 使用模块函数，避免实例方法绑定问题
        parameters={
            "action": "动作名称（navigate/login/extract/screenshot/semantic_operate等）",
            "url": "目标URL（可选）",
            "domain": "网站域名（可选，用于登录）",
            "instruction": "语义操作指令（可选）"
        },
        returns="工具执行结果（包含success、data、error等字段）",
        category=ChromeBridgeTool.TOOL_CATEGORY,
        version=ChromeBridgeTool.TOOL_VERSION
    )

    # 注册到ToolRegistry
    registry = ToolRegistry.get_instance()
    registry.register(tool_def)
    logger.bind(tool="ChromeBridgeTool").info("Chrome桥接工具已注册到ToolRegistry")


if __name__ == "__main__":
    # 简单测试
    import logging
    logging.basicConfig(level=logging.INFO)

    tool = get_chrome_bridge_tool()

    # 测试保存凭证
    tool.execute("login", domain="test.com", username="testuser", password="testpass")
