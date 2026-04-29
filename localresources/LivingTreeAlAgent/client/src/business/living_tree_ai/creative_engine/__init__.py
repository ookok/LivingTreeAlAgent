"""
分布式创作引擎 (Distributed Creative Engine)
============================================

核心理念：AI 是分布式创作网络中的一个特殊节点，而非外部服务。
你的网络提供数据、计算与验证，AI 提供灵感与自动化。

创作闭环：
1. AI 生成内容（代码/文本/图片）
2. 网络验证执行（在节点上跑通代码）
3. 浏览器呈现结果（直接预览效果）
4. 版本管理记录（自动 Git）

模块结构：
- DistributedGenerator: 多节点协同创作引擎
- BrowserIntegration: 浏览器内即圈即生
- ExecutionValidator: 执行即验证（生成即运行）
- StyleMigrator: P2P 知识库与风格迁移
- CreativeGamification: 游戏化与三维创作空间
"""

from .distributed_generator import (
    CreativeGenerator,
    GenerationNode,
    NodeCapability,
    GenerationResult,
    GenerationVersion,
    create_distributed_generator,
)
from .browser_integration import (
    BrowserIntegration,
    SelectionContext,
    GenerationRequest,
    create_browser_integration,
)
from .execution_validator import (
    ExecutionValidator,
    ValidationResult,
    SandboxResult,
    create_execution_validator,
)
from .style_migrator import (
    StyleMigrator,
    StyleProfile,
    KnowledgeEntry,
    create_style_migrator,
)
from .gamification import (
    CreativeGamification,
    CreativeSpace,
    CreativeNode,
    Achievement,
    create_gamification,
)

__all__ = [
    # 分布式生成器
    "CreativeGenerator",
    "GenerationNode",
    "NodeCapability",
    "GenerationResult",
    "GenerationVersion",
    "create_distributed_generator",
    # 浏览器集成
    "BrowserIntegration",
    "SelectionContext",
    "GenerationRequest",
    "create_browser_integration",
    # 执行验证器
    "ExecutionValidator",
    "ValidationResult",
    "SandboxResult",
    "create_execution_validator",
    # 风格迁移
    "StyleMigrator",
    "StyleProfile",
    "KnowledgeEntry",
    "create_style_migrator",
    # 游戏化
    "CreativeGamification",
    "CreativeSpace",
    "CreativeNode",
    "Achievement",
    "create_gamification",
]