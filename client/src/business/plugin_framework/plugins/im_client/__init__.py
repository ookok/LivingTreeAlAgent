"""
IM客户端插件

功能：
- 即时通讯
- 群组聊天
- 文件传输
- 联系人管理

视图模式：独立窗口（Standalone）- 多开聊天窗口
"""

from .im_client_plugin import IMClientPlugin

__all__ = ['IMClientPlugin']