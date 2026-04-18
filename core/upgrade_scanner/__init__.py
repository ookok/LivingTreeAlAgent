# upgrade_scanner/__init__.py — 升级扫描系统（终极版）

"""
Living Tree AI 客户端升级更新系统

六大核心模块：
1. 开源库扫描与决策 — MultiSourceScanner
2. 择优替换适配器 — AdapterWrapper
3. 数据平滑迁移 — DataMigrationManager
4. 补丁安全过渡 — PatchTransitionManager
5. 多源镜像加速 — MirrorConfigManager + MultiSourceDownloader
6. 社区驱动进化 — HotArticleCollector + ProposalGenerator

核心理念：择优替换 × 平滑迁移 × 安全进化 × 社区共识

架构:
┌──────────────────────────────────────────────────────────────┐
│                   客户端 (升级扫描系统)                       │
│            沙箱自愈 × 群体共生 × 隐身外联 × 中心可控            │
├────────────────────────────────────────────────────────────┤
│  模块一: 开源库扫描器 (scanner.py)                            │
│    - 多源扫描: GitHub/Gitee/本地缓存/预置热点库               │
│    - 智能比对: 功能/性能/协议/活跃度                           │
│    - 结果缓存: TTL 1小时                                      │
│                                                              │
│  模块二: 决策引擎 (decision_engine.py)                         │
│    - 多维度评分加权                                            │
│    - 规则修正 (Stars/协议/黑名单)                            │
│    - 决策输出: ADOPT/WRAP/KEEP/DEFER/REJECT                  │
│                                                              │
│  模块三: 适配器封装 (adapter_wrapper.py)                       │
│    - 模板化代码生成                                           │
│    - 生命周期管理                                             │
│    - 一键安装/激活/停用                                       │
│                                                              │
│  模块四: 数据迁移 (data_migration.py)                         │
│    - 版本检测追踪                                              │
│    - 双读兼容 (新优先，失败回退旧)                            │
│    - 惰性迁移 (用到才转)                                       │
│    - 原子写入 (防断电)                                        │
│    - 断点续传                                                 │
│                                                              │
│  模块五: 补丁过渡 (patch_transition.py)                        │
│    - 已应用补丁 → 标记 legacy                                 │
│    - 未应用补丁 → 重新评估                                      │
│    - 冲突检测                                                 │
│    - 用户确认流程                                             │
│                                                              │
│  模块六: 镜像加速 (mirror_accelerator.py)                     │
│    - 多镜像管理 (GitHub/Gitee/阿里云/清华)                     │
│    - 健康度追踪                                               │
│    - 自动选择最快源                                           │
│    - 断点续传                                                 │
│                                                              │
│  模块七: 社区进化 (community_evolution.py)                     │
│    - 热点采集 (GitHub Trending/HackerNews)                   │
│    - 架构关联分析                                             │
│    - 提案生成                                                │
│    - 社区投票表决                                             │
└──────────────────────────────────────────────────────────────┘
"""

from pathlib import Path

# 数据目录
_DATA_DIR = Path.home() / ".hermes-desktop" / "upgrade_scanner"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 子模块
from .scanner_models import (
    # 枚举
    ScanSource,
    CompareDimension,
    ReplacementDecision,
    DataVersion,
    PatchLegacyStatus,
    MirrorSource,
    # 数据结构
    LibraryInfo,
    CompareResult,
    CandidateLibrary,
    ScanTask,
    VersionInfo,
    DataMigrationRecord,
    LegacyPatch,
    MirrorConfig,
    DownloadTask,
    HotArticle,
    EvolutionProposal,
    UpgradeStats,
    # 工具函数
    generate_task_id,
    generate_migration_id,
    calculate_mirror_health,
)

from .scanner import (
    MultiSourceScanner,
    ScanCache,
    PRESET_HOT_LIBRARIES,
    get_scanner,
)

from .decision_engine import (
    DecisionEngine,
    MirrorHealthManager,
    DEFAULT_DECISION_RULES,
    get_decision_engine,
    get_mirror_manager,
)

from .adapter_wrapper import (
    AdapterWrapper,
    AdapterMetadata,
    ADAPTER_TEMPLATES,
    get_adapter_wrapper,
)

from .data_migration import (
    DataMigrationManager,
    VersionManager,
    AtomicWriter,
    DualReadReader,
    SQLiteMigrationHelper,
    MigrationStrategy,
    get_migration_manager,
    get_version_manager,
)

from .patch_transition import (
    PatchTransitionManager,
    LegacyPatchInfo,
    LegacyStatus,
    ReviewRoomGenerator,
    get_transition_manager,
)

from .mirror_accelerator import (
    MirrorConfigManager,
    MultiSourceDownloader,
    GitHubAccelerator,
    MirrorEndpoint,
    DownloadTask,
    get_mirror_config_manager,
    get_downloader,
    get_github_accelerator,
)

from .community_evolution import (
    HotArticleCollector,
    ProposalGenerator,
    CommunityEvolutionScheduler,
    HotArticle,
    EvolutionProposal,
    get_hot_collector,
    get_proposal_generator,
    get_evolution_scheduler,
)

from .system import (
    UpgradeScannerSystem,
    get_upgrade_system,
    quick_scan,
)

__all__ = [
    # 版本信息
    "__version__",
    "__all_modules__",
    # 枚举
    "ScanSource",
    "CompareDimension",
    "ReplacementDecision",
    "DataVersion",
    "PatchLegacyStatus",
    "MirrorSource",
    # 数据结构
    "LibraryInfo",
    "CompareResult",
    "CandidateLibrary",
    "ScanTask",
    "VersionInfo",
    "DataMigrationRecord",
    "LegacyPatch",
    "MirrorConfig",
    "DownloadTask",
    "HotArticle",
    "EvolutionProposal",
    "UpgradeStats",
    # 工具函数
    "generate_task_id",
    "generate_migration_id",
    "calculate_mirror_health",
    # 子系统
    "MultiSourceScanner",
    "ScanCache",
    "PRESET_HOT_LIBRARIES",
    "DecisionEngine",
    "MirrorHealthManager",
    "DEFAULT_DECISION_RULES",
    "AdapterWrapper",
    "AdapterMetadata",
    "ADAPTER_TEMPLATES",
    "DataMigrationManager",
    "VersionManager",
    "AtomicWriter",
    "DualReadReader",
    "SQLiteMigrationHelper",
    "MigrationStrategy",
    "PatchTransitionManager",
    "LegacyPatchInfo",
    "LegacyStatus",
    "ReviewRoomGenerator",
    "MirrorConfigManager",
    "MultiSourceDownloader",
    "GitHubAccelerator",
    "MirrorEndpoint",
    "HotArticleCollector",
    "ProposalGenerator",
    "CommunityEvolutionScheduler",
    "UpgradeScannerSystem",
    # 全局访问器
    "get_scanner",
    "get_decision_engine",
    "get_mirror_manager",
    "get_adapter_wrapper",
    "get_migration_manager",
    "get_version_manager",
    "get_transition_manager",
    "get_mirror_config_manager",
    "get_downloader",
    "get_github_accelerator",
    "get_hot_collector",
    "get_proposal_generator",
    "get_evolution_scheduler",
    "get_upgrade_system",
    "quick_scan",
]

__version__ = "1.0.0"
__all_modules__ = [
    "scanner",
    "scanner_models",
    "decision_engine",
    "adapter_wrapper",
    "data_migration",
    "patch_transition",
    "mirror_accelerator",
    "community_evolution",
    "system",
]
