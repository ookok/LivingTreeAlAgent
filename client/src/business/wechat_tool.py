"""
WeChatTool — Compatibility Stub
=================================

已从核心业务中移除（特定平台工具，非核心）。
保留兼容接口。
"""


class WeChatTool:
    def __init__(self, **kwargs):
        pass

    def send_message(self, content: str, **kwargs) -> dict:
        return {"success": False, "error": "WeChat tool disabled - platform-specific feature"}


_global_wechat_tool = None


def get_wechat_tool() -> WeChatTool:
    global _global_wechat_tool
    if _global_wechat_tool is None:
        _global_wechat_tool = WeChatTool()
    return _global_wechat_tool


__all__ = ["WeChatTool", "get_wechat_tool"]
