"""
AiToEarn 集成模块

支持多平台内容分发和社交互动：
- 多平台 API 集成
- 内容发布管理
- 社交互动自动化
- 内容工作流编排
"""

from .platform_tools import (
    PlatformType,
    ContentType,
    EngageAction,
    Content,
    PublishResult,
    EngageResult,
    PlatformStats,
    BasePlatformAPI,
    DouyinAPI,
    XiaohongshuAPI,
    BilibiliAPI,
    TikTokAPI,
    YouTubeAPI,
    PlatformFactory,
    MultiPlatformManager,
)

from .social_engage import (
    CommentGenerator,
    EngageAnalyzer,
    SocialEngageSubAgent,
    SocialListener,
)

from .content_workflow import (
    WorkflowStatus,
    TaskType,
    WorkflowTask,
    WorkflowResult,
    ContentPlanner,
    MaterialCollector,
    ContentGenerator,
    ContentWorkflow,
)

__all__ = [
    # 平台工具
    "PlatformType",
    "ContentType",
    "EngageAction",
    "Content",
    "PublishResult",
    "EngageResult",
    "PlatformStats",
    "BasePlatformAPI",
    "DouyinAPI",
    "XiaohongshuAPI",
    "BilibiliAPI",
    "TikTokAPI",
    "YouTubeAPI",
    "PlatformFactory",
    "MultiPlatformManager",
    # 社交互动
    "CommentGenerator",
    "EngageAnalyzer",
    "SocialEngageSubAgent",
    "SocialListener",
    # 内容工作流
    "WorkflowStatus",
    "TaskType",
    "WorkflowTask",
    "WorkflowResult",
    "ContentPlanner",
    "MaterialCollector",
    "ContentGenerator",
    "ContentWorkflow",
]
