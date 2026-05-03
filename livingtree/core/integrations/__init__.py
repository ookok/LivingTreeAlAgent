"""
livingtree.core.integrations — 外部平台集成模块

包含：
- git_nexus: Git 代码智能引擎（仓库分析、AST 解析、代码搜索、质量分析）
- github_store: GitHub 桌面应用商店（发现、下载、安装、管理）
"""
from livingtree.core.integrations.git_nexus import (
    # GitNexus facade
    GitNexus,
    create_git_nexus,
    # Git Analyzer
    GitAnalyzer,
    CommitInfo,
    Contributor,
    FileHistory,
    RepositoryStats,
    HotspotInfo,
    # Code Analyzer
    CodeAnalyzer,
    CodeEntity,
    CodeRelation,
    FileStructure,
    # Code Searcher
    CodeSearcher,
    SearchResult,
    CodeRecommendation,
    # Quality Analyzer
    QualityAnalyzer,
    QualityMetrics,
    RefactoringSuggestion,
)

from livingtree.core.integrations.github_store import (
    # GitHubStore facade
    GitHubStore,
    create_github_store,
    # Enums
    PlatformType,
    AssetType,
    InstallStatus,
    SourceType,
    # Models
    GitHubAsset,
    GitHubRelease,
    RepoInfo,
    InstalledApp,
    DownloadTask,
    CategoryInfo,
    DESKTOP_CATEGORIES,
    # Components
    GitHubAPI,
    GitHubAPIError,
    RepoCache,
    ReleaseDetector,
    Downloader,
    DownloadConfig,
    AppManager,
    # Utilities
    _detect_asset_info,
    _detect_current_platform,
    _detect_current_arch,
)
