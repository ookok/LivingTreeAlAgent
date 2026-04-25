"""
Unified Chat UI - 统一聊天 PyQt6 UI 模块

参考 Element/Discord/Telegram 设计

主要组件:
- chat_panel: 主聊天面板 (三栏布局)
  - 左栏: 会话列表
  - 中栏: 消息区域 (气泡 + 输入框)
  - 右栏: 信息面板 (用户/网络/传输/通话)
  - 底栏: 状态栏 (连接/质量/系统)

文件智能展示组件:
- FileCard: 单文件卡片 (图标/名称/大小/操作按钮)
- MultiFileCard: 多文件卡片 (按类型分组显示)
- 工具函数: create_file_message_content, create_multi_file_card,
            open_file_with_default_app, show_file_in_folder

使用方式:
    from client.src.presentation.unified_chat import ChatPanel

    panel = ChatPanel()
    panel.set_my_identity(node_id, short_id, name)
    panel.load_sessions()

文件卡片使用:
    from ui.unified_chat.chat_panel import (
        FileCard, MultiFileCard,
        create_file_message_content,
        open_file_with_default_app,
        show_file_in_folder,
        copy_file_path_to_clipboard
    )
"""

from .chat_panel import (
    ChatPanel, get_chat_panel,
    FileCard, MultiFileCard,
    create_file_message_content,
    create_single_file_card,
    create_multi_file_card,
    open_file_with_default_app,
    show_file_in_folder,
    copy_file_path_to_clipboard,
    get_file_icon, get_file_category, format_file_size,
    FILE_TYPE_ICONS, FILE_CATEGORY_GROUPS
)

__all__ = [
    "ChatPanel", "get_chat_panel",
    "FileCard", "MultiFileCard",
    "create_file_message_content",
    "create_single_file_card",
    "create_multi_file_card",
    "open_file_with_default_app",
    "show_file_in_folder",
    "copy_file_path_to_clipboard",
    "get_file_icon", "get_file_category", "format_file_size",
    "FILE_TYPE_ICONS", "FILE_CATEGORY_GROUPS"
]
