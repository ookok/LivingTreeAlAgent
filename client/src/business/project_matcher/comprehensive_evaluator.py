"""
Comprehensive Evaluator - 综合评估引擎
整合三层匹配结果，生成最终评分和迁移建议
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from .project_analyzer import ProjectData, GitHubMetadata
from .surface_matcher import SurfaceMatcher, SurfaceMatchResult
from .architectural_matcher import ArchitecturalMatcher, ArchitectureMatchResult
from .semantic_matcher import SemanticMatcher, SemanticMatchResult


class MatchLevel(Enum):
    """匹配级别"""
    EXCELLENT = "excellent"      # 80-100
    GOOD = "good"                # 60-80
    MODERATE = "moderate"        # 40-60
    POOR = "poor"                # 20-40
    INCOMPATIBLE = "incompatible" # 0-20


@dataclass
class MigrationSuggestion:
    """迁移建议"""
    type: str  # 'code', 'architecture', 'reference', 'learning'
    priority: str  # 'high', 'medium', 'low'
    title: str
    description: str
    estimated_effort: str  # 'days', 'weeks', 'months'
    risk_level: str  # 'low', 'medium', 'high'
    steps: List[str] = field(default_factory=list)


@dataclass
class RiskWarning:
    """风险预警"""
    category: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    recommendation: str


@dataclass
class ComprehensiveResult:
    """综合评估结果"""
    # 总体评分
    total_score: float = 0.0
    match_level: MatchLevel = MatchLevel.MODERATE
    
    # 分层评分
    surface_score: float = 0.0
    architectural_score: float = 0.0
    semantic_score: float = 0.0
    
    # 详细结果
    surface_result: Optional[SurfaceMatchResult] = None
    architectural_result: Optional[ArchitectureMatchResult] = None
    semantic_result: Optional[SemanticMatchResult] = None
    
    # 洞察和建议
    insights: List[str] = field(default_factory=list)
    migration_suggestions: List[MigrationSuggestion] = field(default_factory=list)
    risk_warnings: List[RiskWarning] = field(default_factory=list)
    
    # 项目信息
    github_project: Optional[GitHubMetadata] = None
    local_project_type: str = ""
    
    # 报告
    report: Dict = field(default_factory=dict)
    generated_at: str = ""


class ComprehensiveEvaluator:
    """综合评估器"""
    
    # 权重配置
    WEIGHTS = {
        'surface': 0.30,       # 表层技术栈
        'architectural': 0.40, # 架构模式
        'semantic': 0.30,      # 语义业务
    }
    
    # 评分标准
    SCORE_THRESHOLDS = {
        MatchLevel.EXCELLENT: 80,
        MatchLevel.GOOD: 60,
        MatchLevel.MODERATE: 40,
        MatchLevel.POOR: 20,
        MatchLevel.INCOMPATIBLE: 0,
    }
    
    def __init__(self):
        self.surface_matcher = SurfaceMatcher()
        self.architectural_matcher = ArchitecturalMatcher()
        self.semantic_matcher = SemanticMatcher()
    
    def evaluate(self, github_project: ProjectData, local_project: ProjectData) -> ComprehensiveResult:
        """执行综合评估"""
        result = ComprehensiveResult()
        
        # 记录项目信息
        result.github_project = github_project.metadata
        result.local_project_type = local_project.project_type.value
        
        # 1. 表层匹配
        result.surface_result = self.surface_matcher.match(github_project, local_project)
        result.surface_score = result.surface_result.score
        
        # 2. 架构匹配
        result.architectural_result = self.architectural_matcher.match(github_project, local_project)
        result.architectural_score = result.architectural_result.score
        
        # 3. 语义匹配
        result.semantic_result = self.semantic_matcher.match(github_project, local_project)
        result.semantic_score = result.semantic_result.score
        
        # 4. 计算总分
        result.total_score = (
            result.surface_score * self.WEIGHTS['surface'] +
            result.architectural_score * self.WEIGHTS['architectural'] +
            result.semantic_score * self.WEIGHTS['semantic']
        )
        
        # 5. 确定匹配级别
        result.match_level = self._get_match_level(result.total_score)
        
        # 6. 生成洞察
        self._generate_insights(result, github_project, local_project)
        
        # 7. 生成迁移建议
        self._generate_migration_suggestions(result, github_project, local_project)
        
        # 8. 生成风险预警
        self._generate_risk_warnings(result, github_project, local_project)
        
        # 9. 生成报告
        result.report = self._generate_report(result)
        result.generated_at = datetime.now().isoformat()
        
        return result
    
    def _get_match_level(self, score: float) -> MatchLevel:
        """根据分数确定匹配级别"""
        if score >= self.SCORE_THRESHOLDS[MatchLevel.EXCELLENT]:
            return MatchLevel.EXCELLENT
        elif score >= self.SCORE_THRESHOLDS[MatchLevel.GOOD]:
            return MatchLevel.GOOD
        elif score >= self.SCORE_THRESHOLDS[MatchLevel.MODERATE]:
            return MatchLevel.MODERATE
        elif score >= self.SCORE_THRESHOLDS[MatchLevel.POOR]:
            return MatchLevel.POOR
        else:
            return MatchLevel.INCOMPATIBLE
    
    def _generate_insights(self, result: ComprehensiveResult, 
                          github: ProjectData, local: ProjectData):
        """生成洞察"""
        insights = []
        
        # 总体评价
        level_descriptions = {
            MatchLevel.EXCELLENT: "两个项目高度匹配，可以直接借鉴或复用",
            MatchLevel.GOOD: "两个项目有较好的匹配度，部分模块可直接复用",
            MatchLevel.MODERATE: "两个项目有部分相似，需要适配工作",
            MatchLevel.POOR: "两个项目差异较大，建议参考而非直接迁移",
            MatchLevel.INCOMPATIBLE: "两个项目不兼容，不建议进行代码迁移",
        }
        
        insights.append(level_descriptions[result.match_level])
        
        # 关键发现
        if result.surface_score > 70:
            insights.append(f"技术栈高度匹配 ({result.surface_score:.0f}%)")
        elif result.surface_score < 30:
            insights.append(f"技术栈差异较大 ({result.surface_score:.0f}%)")
        
        if result.architectural_score > 70:
            insights.append("架构模式相似，可参考其设计")
        elif result.architectural_score < 40:
            insights.append("架构模式差异大，需要重构")
        
        # GitHub 项目亮点
        if github.metadata:
            if github.metadata.stars > 5000:
                insights.append(f"GitHub 项目为高星项目 ({github.metadata.stars} stars)")
            elif github.metadata.stars > 1000:
                insights.append(f"GitHub 项目较受欢迎 ({github.metadata.stars} stars)")
        
        # 独特优势
        if github.frameworks - local.frameworks:
            unique_fw = github.frameworks - local.frameworks
            insights.append(f"GitHub 独有框架: {', '.join(list(unique_fw)[:3])}")
        
        result.insights = insights
    
    def _generate_migration_suggestions(self, result: ComprehensiveResult,
                                        github: ProjectData, local: ProjectData):
        """生成迁移建议"""
        suggestions = []
        
        # 基于整体评分
        if result.match_level in [MatchLevel.EXCELLENT, MatchLevel.GOOD]:
            # 高匹配度建议
            if result.architectural_result:
                for suggestion in result.architectural_result.refactoring_suggestions[:2]:
                    suggestions.append(MigrationSuggestion(
                        type='architecture',
                        priority='high',
                        title='架构优化',
                        description=suggestion,
                        estimated_effort='weeks',
                        risk_level='medium',
                        steps=[
                            '1. 分析现有架构',
                            '2. 设计目标架构',
                            '3. 渐进式重构',
                            '4. 测试验证'
                        ]
                    ))
            
            # 功能复用
            if result.semantic_result and result.semantic_result.reusable_features:
                suggestions.append(MigrationSuggestion(
                    type='code',
                    priority='medium',
                    title='功能模块复用',
                    description=f"可直接复用的功能: {', '.join(result.semantic_result.reusable_features[:3])}",
                    estimated_effort='days',
                    risk_level='low',
                    steps=[
                        '1. 提取可复用代码',
                        '2. 适配接口',
                        '3. 集成测试'
                    ]
                ))
        
        elif result.match_level == MatchLevel.MODERATE:
            # 中等匹配度建议
            suggestions.append(MigrationSuggestion(
                type='reference',
                priority='high',
                title='设计参考',
                description='建议参考 GitHub 项目的架构设计，而非直接复制代码',
                estimated_effort='weeks',
                risk_level='low',
                steps=[
                    '1. 学习其架构模式',
                    '2. 设计本地化方案',
                    '3. 从零实现'
                ]
            ))
            
            if result.surface_score < 50:
                suggestions.append(MigrationSuggestion(
                    type='architecture',
                    priority='medium',
                    title='技术栈适配',
                    description='需要创建适配层来桥接不同的技术栈',
                    estimated_effort='weeks',
                    risk_level='medium',
                    steps=[
                        '1. 定义统一接口',
                        '2. 实现适配器',
                        '3. 渐进迁移'
                    ]
                ))
        
        else:
            # 低匹配度建议
            suggestions.append(MigrationSuggestion(
                type='learning',
                priority='high',
                title='学习借鉴',
                description='建议学习 GitHub 项目的设计理念和最佳实践，而非迁移代码',
                estimated_effort='ongoing',
                risk_level='low',
                steps=[
                    '1. 阅读源码和文档',
                    '2. 理解设计模式',
                    '3. 应用于本地项目'
                ]
            ))
            
            if result.semantic_result and result.semantic_result.missing_features:
                suggestions.append(MigrationSuggestion(
                    type='learning',
                    priority='medium',
                    title='功能参考',
                    description=f"可参考的功能: {', '.join(result.semantic_result.missing_features[:3])}",
                    estimated_effort='months',
                    risk_level='low',
                    steps=[
                        '1. 研究实现方式',
                        '2. 设计本地方案',
                        '3. 迭代开发'
                    ]
                ))
        
        # 学习机会
        if result.semantic_result and result.semantic_result.learning_opportunities:
            for i, opportunity in enumerate(result.semantic_result.learning_opportunities[:2]):
                suggestions.append(MigrationSuggestion(
                    type='learning',
                    priority='low',
                    title=f'学习机会 {i+1}',
                    description=opportunity,
                    estimated_effort='ongoing',
                    risk_level='none'
                ))
        
        result.migration_suggestions = suggestions
    
    def _generate_risk_warnings(self, result: ComprehensiveResult,
                               github: ProjectData, local: ProjectData):
        """生成风险预警"""
        warnings = []
        
        # 技术栈风险
        if result.surface_score < 30:
            warnings.append(RiskWarning(
                category='technology',
                severity='high',
                message='技术栈差异较大，直接迁移可能导致兼容性问题',
                recommendation='创建适配层或使用桥接模式'
            ))
        
        # 架构风险
        if result.architectural_result:
            if result.architectural_result.migration_complexity in ['high', 'very_high']:
                warnings.append(RiskWarning(
                    category='architecture',
                    severity='critical',
                    message=f'架构迁移复杂度: {result.architectural_result.migration_complexity}',
                    recommendation='进行充分的架构评审，考虑渐进式重构'
                ))
            
            if result.architectural_result.pattern_match < 30:
                warnings.append(RiskWarning(
                    category='architecture',
                    severity='high',
                    message='架构模式完全不同，迁移风险高',
                    recommendation='建议重新设计架构，而非迁移'
                ))
        
        # 规模风险
        if github.structure.file_count > local.structure.file_count * 5:
            warnings.append(RiskWarning(
                category='scope',
                severity='medium',
                message=f'GitHub 项目规模较大 ({github.structure.file_count} vs {local.structure.file_count} 文件)',
                recommendation='分模块逐步迁移，优先迁移核心功能'
            ))
        
        # 依赖风险
        if result.surface_result:
            new_deps = set()
            for dep_info in github.dependencies:
                for dep_name in dep_info.raw_dependencies.keys():
                    found = False
                    for local_dep in local.dependencies:
                        if dep_name in local_dep.raw_dependencies:
                            found = True
                            break
                    if not found:
                        new_deps.add(dep_name)
            
            if len(new_deps) > 10:
                warnings.append(RiskWarning(
                    category='dependency',
                    severity='medium',
                    message=f'需要引入 {len(new_deps)} 个新依赖',
                    recommendation='评估依赖的稳定性和维护状态'
                ))
        
        # 时间风险
        if result.semantic_result and result.semantic_result.need_satisfaction > 70:
            warnings.append(RiskWarning(
                category='timeline',
                severity='low',
                message='GitHub 项目高度满足本地需求，迁移价值高',
                recommendation='可投入资源进行高质量迁移'
            ))
        
        result.risk_warnings = warnings
    
    def _generate_report(self, result: ComprehensiveResult) -> Dict[str, Any]:
        """生成报告"""
        report = {
            'summary': {
                'total_score': result.total_score,
                'match_level': result.match_level.value,
                'surface_score': result.surface_score,
                'architectural_score': result.architectural_score,
                'semantic_score': result.semantic_score,
            },
            'project_info': {
                'github': {
                    'name': result.github_project.name if result.github_project else 'N/A',
                    'owner': result.github_project.owner if result.github_project else 'N/A',
                    'stars': result.github_project.stars if result.github_project else 0,
                    'language': result.github_project.language if result.github_project else 'N/A',
                },
                'local': {
                    'type': result.local_project_type,
                }
            },
            'insights': result.insights,
            'suggestions': [
                {
                    'type': s.type,
                    'priority': s.priority,
                    'title': s.title,
                    'description': s.description,
                    'estimated_effort': s.estimated_effort,
                    'risk_level': s.risk_level,
                }
                for s in result.migration_suggestions
            ],
            'warnings': [
                {
                    'category': w.category,
                    'severity': w.severity,
                    'message': w.message,
                    'recommendation': w.recommendation,
                }
                for w in result.risk_warnings
            ],
            'detailed_scores': {
                'surface': result.surface_result.__dict__ if result.surface_result else {},
                'architectural': {
                    'score': result.architectural_score,
                    'pattern_match': result.architectural_result.pattern_match if result.architectural_result else 0,
                    'component_match': result.architectural_result.component_match if result.architectural_result else 0,
                    'migration_complexity': result.architectural_result.migration_complexity if result.architectural_result else 'unknown',
                },
                'semantic': {
                    'score': result.semantic_score,
                    'feature_coverage': result.semantic_result.feature_coverage if result.semantic_result else 0,
                    'need_satisfaction': result.semantic_result.need_satisfaction if result.semantic_result else 0,
                }
            },
            'generated_at': result.generated_at,
        }
        
        return report
    
    def generate_text_report(self, result: ComprehensiveResult) -> str:
        """生成文本报告"""
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append("项目匹配度分析报告")
        lines.append("=" * 60)
        
        # 项目信息
        if result.github_project:
            lines.append(f"\nGitHub 项目: {result.github_project.owner}/{result.github_project.name}")
            lines.append(f"  Stars: {result.github_project.stars}")
            lines.append(f"  语言: {result.github_project.language}")
        lines.append(f"\n本地项目类型: {result.local_project_type}")
        
        # 总体评分
        lines.append(f"\n总体匹配度: {result.total_score:.1f}/100")
        lines.append(f"匹配级别: {result.match_level.value}")
        
        # 分层评分
        lines.append(f"\n分层评分:")
        lines.append(f"  表层技术栈: {result.surface_score:.1f}%")
        lines.append(f"  架构模式: {result.architectural_score:.1f}%")
        lines.append(f"  语义业务: {result.semantic_score:.1f}%")
        
        # 关键洞察
        lines.append(f"\n关键洞察:")
        for insight in result.insights[:5]:
            lines.append(f"  - {insight}")
        
        # 建议
        if result.migration_suggestions:
            lines.append(f"\n迁移建议:")
            for suggestion in result.migration_suggestions[:3]:
                lines.append(f"  [{suggestion.priority.upper()}] {suggestion.title}")
                lines.append(f"    {suggestion.description}")
        
        # 风险预警
        if result.risk_warnings:
            lines.append(f"\n风险预警:")
            for warning in result.risk_warnings[:3]:
                lines.append(f"  [{warning.severity.upper()}] {warning.message}")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)


# 工厂函数
def create_evaluator() -> ComprehensiveEvaluator:
    """创建综合评估器"""
    return ComprehensiveEvaluator()


async def analyze_projects(github_url: str, local_path: str) -> ComprehensiveResult:
    """便捷函数：分析两个项目"""
    from .project_analyzer import create_github_analyzer, create_local_analyzer
    
    # 采集数据
    github_analyzer = create_github_analyzer()
    local_analyzer = create_local_analyzer(local_path)
    
    github_data = await github_analyzer.analyze(github_url)
    local_data = local_analyzer.analyze()
    
    # 评估
    evaluator = create_evaluator()
    result = evaluator.evaluate(github_data, local_data)
    
    return result


if __name__ == '__main__':
    import asyncio
    
    async def test():
        # 测试
        result = await analyze_projects(
            'https://github.com/example/ai-ide',
            'f:/mhzyapp/LivingTreeAlAgent'
        )
        
        print(f"Total Score: {result.total_score:.1f}")
        print(f"Match Level: {result.match_level.value}")
        print("\n" + evaluator.generate_text_report(result) if hasattr(asyncio, 'get_event_loop') else "")
    
    asyncio.run(test())
