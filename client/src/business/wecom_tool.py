"""
WeComTool — Compatibility Stub
================================

已从核心业务中移除（特定平台工具，非核心）。
保留兼容接口供 skill_integration_service 等过渡使用。
"""


class WeComTool:
    def __init__(self, **kwargs):
        pass

    def send_message(self, content: str, **kwargs) -> dict:
        return {"success": False, "error": "WeCom tool disabled - platform-specific feature"}


_global_wecom_tool = None


def get_wecom_tool() -> WeComTool:
    global _global_wecom_tool
    if _global_wecom_tool is None:
        _global_wecom_tool = WeComTool()
    return _global_wecom_tool


__all__ = ["WeComTool", "get_wecom_tool"]
