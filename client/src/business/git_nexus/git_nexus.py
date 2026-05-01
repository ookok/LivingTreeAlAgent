"""
GitNexus - 统一代码智能引擎入口

整合以下功能：
1. Git仓库分析 (GitAnalyzer)
2. 代码结构分析 (CodeAnalyzer)
3. 智能代码搜索 (CodeSearcher)
4. 代码质量分析 (QualityAnalyzer)
"""

from typing import List, Dict, Any, Optional
import os
from pathlib import Path

# 导入子模块
from .git_analyzer import GitAnalyzer, CommitInfo, Contributor, FileHistory, RepositoryStats, HotspotInfo
from .code_analyzer import CodeAnalyzer, CodeEntity, CodeRelation, FileStructure
from .code_searcher import CodeSearcher, SearchResult, CodeRecommendation
from .quality_analyzer import QualityAnalyzer, QualityMetrics, RefactoringSuggestion

class GitNexus:
    """
    GitNexus - 代码智能引擎
    
    核心功能：
    1. Git仓库分析 - 提交历史、贡献者、热点识别
    2. 代码结构分析 - 函数、类、依赖关系
    3. 智能搜索 - 按名称、内容、文档搜索
    4. 质量分析 - 复杂度、可维护性、重构建议
    """
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        
        # 初始化分析器
        self.git_analyzer: Optional[GitAnalyzer] = None
        self.code_analyzer: Optional[CodeAnalyzer] = None
        self.code_searcher: Optional[CodeSearcher] = None
        self.quality_analyzer: Optional[QualityAnalyzer] = None
        
        # 缓存状态
        self._initialized = False
        self._analysis_timestamp = None
    
    def initialize(self):
        """初始化所有分析器"""
        try:
            # 初始化 Git 分析器
            self.git_analyzer = GitAnalyzer(str(self.repo_path))
            
            # 初始化代码分析器
            self.code_analyzer = CodeAnalyzer(str(self.repo_path))
            self.code_analyzer.analyze_project()
            
            # 初始化代码搜索器
            self.code_searcher = CodeSearcher(self.code_analyzer)
            
            # 初始化质量分析器
            self.quality_analyzer = QualityAnalyzer(str(self.repo_path))
            
            self._initialized = True
            return True
        except Exception as e:
            print(f"GitNexus 初始化失败: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            self.initialize()
    
    # ========== Git 仓库分析 ==========
    
    def get_repo_info(self) -> Dict[str, Any]:
        """获取仓库信息"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_repo_info()
        return {}
    
    def get_commits(self, limit: int = 100) -> List[CommitInfo]:
        """获取提交历史"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_commits(limit)
        return []
    
    def get_contributors(self) -> List[Contributor]:
        """获取贡献者列表"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_contributors()
        return []
    
    def get_file_history(self, file_path: str) -> Optional[FileHistory]:
        """获取文件历史"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_file_history(file_path)
        return None
    
    def get_hotspots(self, threshold: int = 10) -> List[HotspotInfo]:
        """识别代码热点"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_hotspots(threshold)
        return []
    
    def get_repository_stats(self) -> Optional[RepositoryStats]:
        """获取仓库统计"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_repository_stats()
        return None
    
    def search_commits(self, pattern: str) -> List[CommitInfo]:
        """搜索提交"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.search_by_message(pattern)
        return []
    
    def get_blame(self, file_path: str) -> Dict[int, Any]:
        """获取 blame 信息"""
        self.ensure_initialized()
        if self.git_analyzer:
            return self.git_analyzer.get_blame(file_path)
        return {}
    
    # ========== 代码结构分析 ==========
    
    def get_project_overview(self) -> Dict[str, Any]:
        """获取项目概览"""
        self.ensure_initialized()
        if self.code_analyzer:
            return self.code_analyzer.get_project_overview()
        return {}
    
    def get_file_structure(self, file_path: str) -> Optional[FileStructure]:
        """获取文件结构"""
        self.ensure_initialized()
        if self.code_analyzer:
            return self.code_analyzer.get_file_structure(file_path)
        return None
    
    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """获取实体"""
        self.ensure_initialized()
        if self.code_analyzer:
            return self.code_analyzer.get_entity(entity_id)
        return None
    
    def find_by_name(self, name: str) -> List[CodeEntity]:
        """按名称查找实体"""
        self.ensure_initialized()
        if self.code_analyzer:
            return self.code_analyzer.find_by_name(name)
        return []
    
    def get_dependency_graph(self, file_path: str) -> Dict[str, Any]:
        """获取依赖图"""
        self.ensure_initialized()
        if self.code_analyzer:
            return self.code_analyzer.get_dependency_graph(file_path)
        return {}
    
    # ========== 智能代码搜索 ==========
    
    def search_code(self, query: str, limit: int = 10) -> List[SearchResult]:
        """智能搜索代码"""
        self.ensure_initialized()
        if self.code_searcher:
            return self.code_searcher.search(query, limit)
        return []
    
    def recommend_code(self, entity_id: str, limit: int = 5) -> List[CodeRecommendation]:
        """推荐相关代码"""
        self.ensure_initialized()
        if self.code_searcher:
            entity = self.code_analyzer.get_entity(entity_id) if self.code_analyzer else None
            if entity:
                return self.code_searcher.recommend_code(entity, limit)
        return []
    
    def find_similar_code(self, entity_id: str, limit: int = 5) -> List[SearchResult]:
        """查找相似代码"""
        self.ensure_initialized()
        if self.code_searcher:
            entity = self.code_analyzer.get_entity(entity_id) if self.code_analyzer else None
            if entity:
                return self.code_searcher.find_similar_code(entity, limit)
        return []
    
    # ========== 代码质量分析 ==========
    
    def analyze_file_quality(self, file_path: str) -> Optional[QualityMetrics]:
        """分析文件质量"""
        self.ensure_initialized()
        if self.quality_analyzer:
            return self.quality_analyzer.analyze_file(file_path)
        return None
    
    def analyze_project_quality(self) -> Dict[str, QualityMetrics]:
        """分析项目质量"""
        self.ensure_initialized()
        if self.quality_analyzer:
            return self.quality_analyzer.analyze_project()
        return {}
    
    def get_refactoring_suggestions(self, file_path: str) -> List[RefactoringSuggestion]:
        """获取重构建议"""
        self.ensure_initialized()
        if self.quality_analyzer:
            return self.quality_analyzer.get_refactoring_suggestions(file_path)
        return []
    
    def get_project_quality_summary(self) -> Dict[str, Any]:
        """获取项目质量汇总"""
        self.ensure_initialized()
        if self.quality_analyzer:
            return self.quality_analyzer.get_project_quality_summary()
        return {}
    
    # ========== 综合分析 ==========
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """获取综合报告"""
        self.ensure_initialized()
        
        report = {
            'repo_info': self.get_repo_info(),
            'stats': {},
            'quality': {},
            'code_overview': {}
        }
        
        if self.git_analyzer:
            report['stats'] = {
                'commits': len(self.get_commits(1000)),
                'contributors': len(self.get_contributors()),
                'hotspots': len(self.get_hotspots())
            }
        
        if self.code_analyzer:
            report['code_overview'] = self.get_project_overview()
        
        if self.quality_analyzer:
            report['quality'] = self.get_project_quality_summary()
        
        return report
    
    def refresh(self):
        """刷新分析缓存"""
        self._initialized = False
        self.initialize()
    
    def __repr__(self):
        return f"GitNexus(repo_path='{self.repo_path}', initialized={self._initialized})"