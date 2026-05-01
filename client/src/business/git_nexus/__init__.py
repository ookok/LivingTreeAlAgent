"""
GitNexus - 代码智能引擎

核心功能：
1. Git 仓库分析
2. 代码结构理解
3. 智能代码搜索
4. 代码质量分析
5. 重构建议
6. 依赖关系分析

模块结构：
- git_analyzer.py: Git仓库分析
- code_analyzer.py: 代码结构分析
- code_searcher.py: 智能代码搜索
- quality_analyzer.py: 代码质量分析
- git_nexus.py: 统一入口
"""

from .git_nexus import GitNexus
from .git_analyzer import GitAnalyzer, CommitInfo, Contributor, FileHistory, RepositoryStats, HotspotInfo
from .code_analyzer import CodeAnalyzer, CodeEntity, CodeRelation
from .code_searcher import CodeSearcher, SearchResult
from .quality_analyzer import QualityAnalyzer, QualityMetrics

__all__ = [
    'GitNexus',
    'GitAnalyzer',
    'CommitInfo',
    'Contributor',
    'FileHistory',
    'RepositoryStats',
    'HotspotInfo',
    'CodeAnalyzer',
    'CodeEntity',
    'CodeRelation',
    'CodeSearcher',
    'SearchResult',
    'QualityAnalyzer',
    'QualityMetrics'
]

def get_git_nexus(repo_path: str = ".") -> GitNexus:
    """获取 GitNexus 实例"""
    return GitNexus(repo_path)