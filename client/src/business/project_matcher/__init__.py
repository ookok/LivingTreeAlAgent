"""
Project Matcher - 项目匹配度分析引擎
三层匹配: 表层技术栈 / 架构模式 / 语义业务
"""

from .project_analyzer import (
    ProjectData,
    ProjectType,
    GitHubMetadata,
    CodeStructure,
    ArchitectureInfo,
    BusinessInfo,
    DependencyInfo,
    create_github_analyzer,
    create_local_analyzer,
)

from .surface_matcher import (
    SurfaceMatcher,
    SurfaceMatchResult,
    create_surface_matcher,
)

from .architectural_matcher import (
    ArchitecturalMatcher,
    ArchitectureMatchResult,
    ComponentComparison,
    create_architectural_matcher,
)

from .semantic_matcher import (
    SemanticMatcher,
    SemanticMatchResult,
    FeatureMatch,
    create_semantic_matcher,
)

from .comprehensive_evaluator import (
    ComprehensiveEvaluator,
    ComprehensiveResult,
    MatchLevel,
    MigrationSuggestion,
    RiskWarning,
    create_evaluator,
    analyze_projects,
)

__all__ = [
    # 核心数据类型
    'ProjectData',
    'ProjectType',
    'GitHubMetadata',
    'CodeStructure',
    'ArchitectureInfo',
    'BusinessInfo',
    'DependencyInfo',
    
    # 匹配器
    'SurfaceMatcher',
    'SurfaceMatchResult',
    'ArchitecturalMatcher',
    'ArchitectureMatchResult',
    'ComponentComparison',
    'SemanticMatcher',
    'SemanticMatchResult',
    'FeatureMatch',
    'ComprehensiveEvaluator',
    'ComprehensiveResult',
    'MatchLevel',
    'MigrationSuggestion',
    'RiskWarning',
    
    # 工厂函数
    'create_github_analyzer',
    'create_local_analyzer',
    'create_surface_matcher',
    'create_architectural_matcher',
    'create_semantic_matcher',
    'create_evaluator',
    'analyze_projects',
]

__version__ = '1.0.0'
