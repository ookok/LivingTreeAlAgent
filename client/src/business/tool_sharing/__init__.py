"""
工具共享模块

支持集体智慧进化循环：
- Agent A 创建工具 → 测试通过 → 上传到 Relay Server
- Agent B 下载工具 → 使用工具 → 评分反馈
- Agent C 下载工具 → 改进工具 → 上传改进版
- 所有 Agent 更新到改进版 → 整体智慧提升
"""

from .tool_sharing_manager import (
    ToolSharingManager,
    ToolRatingSystem,
    ToolDownloader,
    ToolUploader,
    ToolPackage
)

__all__ = [
    "ToolSharingManager",
    "ToolRatingSystem",
    "ToolDownloader",
    "ToolUploader",
    "ToolPackage"
]