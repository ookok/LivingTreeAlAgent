"""
ChromeBridgeTool - Chrome 桥接工具（BaseTool 封装）
==================================================

将 ChromeBridge 封装为标准的 BaseTool 子类，
注册到 ToolRegistry，供 Hermes Agent 调用。

支持的 actions：
- navigate：导航到 URL
- extract：提取页面内容
- check_login：检测登录状态
- screenshot：截图
- save_session：保存会话（Cookie）
- restore_session：恢复会话（Cookie）
"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.chrome_bridge.chrome_bridge import ChromeBridge, get_chrome_bridge
from client.src.business.chrome_bridge.website_adapter_registry import get_adapter_registry


class ChromeBridgeTool(BaseTool):
    """
    Chrome 桥接工具

    直接利用用户已登录的 Chrome 浏览器会话，
    通过 CDP 实现无感复用登录状态，内置反检测机制。
    """

    def __init__(
        self,
        debug_port: int = 9222,
        headless: bool = False,
        anti_detection_level: str = "normal",
    ):
        """
        初始化 Chrome 桥接工具

        Args:
            debug_port: Chrome 远程调试端口
            headless: 是否以 headless 模式启动
            anti_detection_level: 反检测级别
        """
        super().__init__(
            name="chrome_bridge",
            description=(
                "通过 CDP 桥接 Chrome 浏览器，复用已登录会话，"
                "支持反检测，内置 80+ 网站适配器。"
                "支持 navigate（导航）、extract（内容提取）、"
                "check_login（登录检测）、screenshot（截图）等动作。"
            ),
            category="web",
            tags=[
                "chrome", "cdp", "browser", "session-reuse",
                "anti-detection", "web-scraping", "adapter",
            ],
            version="1.0.0",
        )
        self._debug_port = debug_port
        self._headless = headless
        self._anti_level = anti_detection_level
        self._bridge: Optional[ChromeBridge] = None

    def _get_bridge(self) -> ChromeBridge:
        """获取或创建 ChromeBridge 实例"""
        if self._bridge is None:
            self._bridge = get_chrome_bridge(
                debug_port=self._debug_port,
                headless=self._headless,
                anti_detection_level=self._anti_level,
            )
        return self._bridge

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        执行 Chrome 桥接操作

        Args:
            action: 操作类型
                - "navigate"：导航到 URL
                - "extract"：提取页面内容
                - "check_login"：检测登录状态
                - "screenshot"：截图
                - "save_session"：保存会话
                - "restore_session"：恢复会话
                - "list_adapters"：列出所有适配器
            **kwargs: 操作参数

        Returns:
            ToolResult 格式的结果字典
        """
        try:
            if action == "navigate":
                return self._run_async(self._do_navigate(**kwargs))
            elif action == "extract":
                return self._run_async(self._do_extract(**kwargs))
            elif action == "check_login":
                return self._run_async(self._do_check_login(**kwargs))
            elif action == "screenshot":
                return self._run_async(self._do_screenshot(**kwargs))
            elif action == "save_session":
                return self._run_async(self._do_save_session(**kwargs))
            elif action == "restore_session":
                return self._run_async(self._do_restore_session(**kwargs))
            elif action == "list_adapters":
                return self._do_list_adapters()
            elif action == "adapter_info":
                return self._do_adapter_info(**kwargs)
            else:
                return {
                    "success": False,
                    "error": f"未知 action: {action}",
                    "available_actions": [
                        "navigate", "extract", "check_login",
                        "screenshot", "save_session", "restore_session",
                        "list_adapters", "adapter_info",
                    ],
                }
        except Exception as e:
            logger.bind(tool="ChromeBridgeTool").error(f"执行失败: {e}")
            return {"success": False, "error": str(e)}

    # ============================================================
    # 异步操作封装
    # ============================================================

    def _run_async(self, coroutine):
        """运行异步操作（兼容同步调用）"""
        try:
            return asyncio.run(coroutine)
        except RuntimeError as e:
            logger.bind(tool="ChromeBridgeTool").warning(f"asyncio.run() 失败，使用兜底方案: {e}")
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coroutine)
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(coroutine)

    # ============================================================
    # Action 实现
    # ============================================================

    async def _do_navigate(self, url: str, adapter: str = None, **_kwargs) -> Dict:
        """导航到 URL"""
        bridge = self._get_bridge()
        result = await bridge.navigate(url=url, adapter_name=adapter)
        return {"success": True, "data": result}

    async def _do_extract(self, url: str = None, adapter: str = None, **_kwargs) -> Dict:
        """提取页面内容"""
        bridge = self._get_bridge()
        result = await bridge.extract_content(url=url, adapter_name=adapter)
        return {"success": True, "data": result}

    async def _do_check_login(self, url: str, adapter: str = None, **_kwargs) -> Dict:
        """检测登录状态"""
        bridge = self._get_bridge()
        result = await bridge.check_login(url=url, adapter_name=adapter)
        return {"success": True, "data": result}

    async def _do_screenshot(
        self, filepath: str = None, format: str = "png", **_kwargs
    ) -> Dict:
        """截图"""
        bridge = self._get_bridge()
        data = await bridge.screenshot(filepath=filepath, format=format)
        result = {"format": format, "size": len(data)}
        if filepath:
            result["filepath"] = filepath
        else:
            result["data_base64"] = data.encode("base64").decode("utf-8")[:100] + "..."
        return {"success": True, "data": result}

    async def _do_save_session(self, filepath: str, urls: list = None, **_kwargs) -> Dict:
        """保存会话"""
        bridge = self._get_bridge()
        await bridge.save_session(filepath=filepath, urls=urls)
        return {"success": True, "filepath": filepath}

    async def _do_restore_session(self, filepath: str, **_kwargs) -> Dict:
        """恢复会话"""
        bridge = self._get_bridge()
        await bridge.restore_session(filepath=filepath)
        return {"success": True, "filepath": filepath}

    def _do_list_adapters(self) -> Dict:
        """列出所有适配器"""
        registry = get_adapter_registry()
        adapters = registry.list_adapters()
        return {
            "success": True,
            "count": len(adapters),
            "adapters": adapters,
        }

    def _do_adapter_info(self, name: str = None, url: str = None, **_kwargs) -> Dict:
        """获取适配器信息"""
        registry = get_adapter_registry()
        if name:
            adapter = registry.get_adapter(name)
            if adapter:
                return {"success": True, "data": adapter.get_meta()}
            return {"success": False, "error": f"适配器不存在: {name}"}
        if url:
            adapter = registry.find_adapter_for_url(url)
            if adapter:
                return {"success": True, "data": adapter.get_meta()}
            return {"success": False, "error": f"未找到匹配 URL 的适配器: {url}"}
        return {"success": False, "error": "需要指定 name 或 url"}

    # ============================================================
    # Agent 调用接口（结构化输出）
    # ============================================================

    def agent_call(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        智能体调用接口（结构化 JSON 输出）

        供 Hermes Agent 直接调用，返回标准格式。
        """
        return self.execute(action=action, **kwargs)


# ============================================================
# 注册到 ToolRegistry
# ============================================================

def register_chrome_bridge_tool():
    """注册 ChromeBridgeTool 到 ToolRegistry"""
    from client.src.business.tools.tool_registry import ToolRegistry
    tool = ChromeBridgeTool()
    registry = ToolRegistry.get_instance()
    registry.register_tool(tool)
    logger.bind(tool="ChromeBridgeTool").info(
        "ChromeBridgeTool 已注册到 ToolRegistry"
    )
    return tool


if __name__ == "__main__":
    # 测试
    tool = ChromeBridgeTool()
    print(tool.execute(action="list_adapters"))
