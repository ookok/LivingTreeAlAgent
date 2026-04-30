"""
BrowserManagerTool - 浏览器管理器工具封装
提供启动/关闭浏览器、获取状态等功能
"""
import logging
from typing import Dict, Any, Optional
from loguru import logger

from business.tools.base_tool import BaseTool, AgentCallResult
from business.chrome_bridge.browser_manager import BrowserManager


class BrowserManagerTool(BaseTool):
    """
    浏览器管理器工具

    功能：
    1. 启动浏览器（自动检测外部浏览器 或 使用内置Chromium）
    2. 关闭浏览器
    3. 获取浏览器状态
    4. 导航到指定URL
    5. 确保浏览器就绪（自动启动）
    """

    TOOL_NAME = "browser_manager"
    TOOL_DESCRIPTION = "浏览器管理器，支持启动/关闭浏览器、管理会话、自动登录"
    TOOL_CATEGORY = "web_automation"
    TOOL_VERSION = "1.0.0"

    # 工具定义（用于注册到ToolRegistry）
    TOOL_DEFINITION = {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "category": TOOL_CATEGORY,
        "version": TOOL_VERSION,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: launch/close/status/navigate/ensure_ready",
                    "enum": ["launch", "close", "status", "navigate", "ensure_ready"]
                },
                "browser_type": {
                    "type": "string",
                    "description": "浏览器类型: chromium/chrome/edge/detect (默认: detect)",
                    "default": "detect"
                },
                "url": {
                    "type": "string",
                    "description": "目标URL（启动或导航时使用）"
                },
                "headless": {
                    "type": "boolean",
                    "description": "是否无头模式（默认: false）",
                    "default": False
                }
            },
            "required": ["action"]
        }
    }

    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        """
        初始化浏览器管理器工具

        Args:
            browser_manager: BrowserManager实例（可选，默认使用单例）
        """
        # 必须先设置属性，再调用super().__init__()
        self._name = self.TOOL_NAME
        self._description = self.TOOL_DESCRIPTION
        self._category = self.TOOL_CATEGORY
        super().__init__()

        # 使用单例模式获取BrowserManager
        self.browser_manager = browser_manager or BrowserManager()

        logger.info(f"BrowserManagerTool初始化完成")

    @property
    def name(self) -> str:
        """工具名称"""
        return self._name

    @property
    def description(self) -> str:
        """工具描述"""
        return self._description

    @property
    def category(self) -> str:
        """工具类别"""
        return self._category

    @property
    def version(self) -> str:
        """工具版本"""
        return self.TOOL_VERSION

    def get_definition(self) -> Dict[str, Any]:
        """
        获取工具定义（用于注册到ToolRegistry）

        Returns:
            工具定义字典
        """
        return self.TOOL_DEFINITION

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        执行浏览器管理操作

        Args:
            action: 操作类型 (launch/close/status/navigate/ensure_ready)
            **kwargs: 其他参数

        Returns:
            操作结果字典
        """
        logger.info(f"执行浏览器管理操作: {action}, 参数: {kwargs}")

        try:
            if action == "launch":
                return self._launch_browser(kwargs)
            elif action == "close":
                return self._close_browser()
            elif action == "status":
                return self._get_status()
            elif action == "navigate":
                return self._navigate(kwargs)
            elif action == "ensure_ready":
                return self._ensure_ready(kwargs)
            else:
                return {
                    "success": False,
                    "error": f"未知操作: {action}",
                    "supported_actions": ["launch", "close", "status", "navigate", "ensure_ready"]
                }

        except Exception as e:
            logger.error(f"执行操作失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _launch_browser(self, params: Dict) -> Dict:
        """启动浏览器"""
        browser_type = params.get("browser_type", "detect")
        url = params.get("url")
        headless = params.get("headless", False)

        # 更新配置
        self.browser_manager.headless = headless

        # 启动浏览器
        result = self.browser_manager.launch_browser(
            browser_type=browser_type,
            url=url
        )

        return result

    def _close_browser(self) -> Dict:
        """关闭浏览器"""
        return self.browser_manager.close_browser()

    def _get_status(self) -> Dict:
        """获取浏览器状态"""
        return self.browser_manager.get_browser_status()

    def _navigate(self, params: Dict) -> Dict:
        """导航到指定URL"""
        url = params.get("url")
        if not url:
            return {
                "success": False,
                "error": "缺少必需参数: url"
            }

        return self.browser_manager.navigate(url)

    def _ensure_ready(self, params: Dict) -> Dict:
        """确保浏览器就绪（未启动时自动启动）"""
        url = params.get("url")
        return self.browser_manager.ensure_browser_ready(url)

    @classmethod
    def auto_register(cls):
        """
        自动注册工具到ToolRegistry

        Returns:
            是否注册成功
        """
        try:
            from business.tool_registry import ToolRegistry

            registry = ToolRegistry.get_instance()

            # 创建工具实例
            tool = cls()

            # 注册工具
            registry.register_tool(cls.TOOL_DEFINITION, tool)

            logger.info(f"BrowserManagerTool已自动注册到ToolRegistry")
            return True

        except Exception as e:
            logger.error(f"自动注册失败: {e}", exc_info=True)
            return False


# 便捷函数
def get_browser_manager_tool() -> BrowserManagerTool:
    """获取BrowserManagerTool实例"""
    return BrowserManagerTool()


# 测试代码
if __name__ == "__main__":
    import time

    print("=" * 60)
    print("测试 BrowserManagerTool")
    print("=" * 60)

    # 1. 创建工具
    tool = get_browser_manager_tool()

    # 2. 启动浏览器
    print("\n1. 启动浏览器（自动检测）...")
    result = tool.execute("launch", browser_type="detect")
    print(f"   结果: {result}")

    if result.get("success"):
        # 3. 获取状态
        print("\n2. 浏览器状态:")
        status = tool.execute("status")
        print(f"   {status}")

        # 4. 等待
        print("\n3. 浏览器已打开，5秒后关闭...")
        time.sleep(5)

        # 5. 关闭
        print("\n4. 关闭浏览器...")
        close_result = tool.execute("close")
        print(f"   结果: {close_result}")
    else:
        print(f"   启动失败: {result.get('error')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
