"""
智能工作空间 (Intelligent Workspace)
=====================================

内置平台的 AI 增强策略：
1. 内容创作：从"发布"到"共创"
2. 发布网页：动态化与个性化
3. 论坛与邮件：预测性协作
4. 安全与隐私：隐形守护
5. 存储架构：本地本体 + 分布式智能层

存储原则：
- 本地存储（本体）：原始文件始终在你的硬盘里
- 分布式存储（智能层）：AI 系统只处理索引和预览
"""

from .workspace import (
    IntelligentWorkspace,
    create_workspace,
    ContentType,
    PublishStatus,
    ComplianceResult,
)
from .content_creator import (
    ContentCreator,
    create_content_creator,
    WritingTone,
    ContentTemplate,
)
from .web_publisher import (
    WebPublisher,
    create_web_publisher,
    PageType,
    SEOOptimization,
)
from .collaboration import (
    CollaborationEngine,
    create_collaboration_engine,
    ReplyTone,
    KnowledgeEntry,
)
from .security_guard import (
    SecurityGuard,
    create_security_guard,
    ThreatLevel,
    ScanResult,
)
from .storage_engine import (
    StorageEngine,
    create_storage_engine,
    StorageType,
    IndexEntry,
    PreviewCache,
)

__all__ = [
    # 核心工作空间
    "IntelligentWorkspace",
    "create_workspace",
    "ContentType",
    "PublishStatus",
    "ComplianceResult",
    # 内容创作
    "ContentCreator",
    "create_content_creator",
    "WritingTone",
    "ContentTemplate",
    # 网页发布
    "WebPublisher",
    "create_web_publisher",
    "PageType",
    "SEOOptimization",
    # 协作引擎
    "CollaborationEngine",
    "create_collaboration_engine",
    "ReplyTone",
    "KnowledgeEntry",
    # 安全守护
    "SecurityGuard",
    "create_security_guard",
    "ThreatLevel",
    "ScanResult",
    # 存储引擎
    "StorageEngine",
    "create_storage_engine",
    "StorageType",
    "IndexEntry",
    "PreviewCache",
]