"""
Project Matcher 测试脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

# 导入项目分析器
from client.src.business.project_matcher.project_analyzer import (
    ProjectData, ProjectType, ArchitectureInfo, BusinessInfo,
    CodeStructure
)

# 导入匹配器
from client.src.business.project_matcher.surface_matcher import create_surface_matcher
from client.src.business.project_matcher.architectural_matcher import create_architectural_matcher
from client.src.business.project_matcher.semantic_matcher import create_semantic_matcher
from client.src.business.project_matcher.comprehensive_evaluator import create_evaluator

print("=" * 60)
print("项目匹配度分析引擎测试")
print("=" * 60)

# 创建测试数据
github = ProjectData(
    project_type=ProjectType.AI_ML,
    languages={'Python', 'JavaScript'},
    frameworks={'PyQt6', 'Transformers'},
    databases={'SQLite'},
    structure=CodeStructure(
        main_directories={'plugins': 20, 'core': 15, 'ai': 10, 'ui': 8}
    ),
    architecture=ArchitectureInfo(
        pattern='plugin',
        components=['agent', 'intent_engine', 'llm_adapter', 'panel'],
    ),
    business=BusinessInfo(
        features=['LLM Integration', 'Intent Engine', 'Code Generation', 'User Authentication'],
        user_types=['Developer', 'Enterprise'],
        integrations=['API', 'OAuth']
    )
)

local = ProjectData(
    project_type=ProjectType.IDE_PLUGIN,
    languages={'Python', 'JavaScript'},
    frameworks={'PyQt5'},
    databases={'SQLite', 'PostgreSQL'},
    structure=CodeStructure(
        main_directories={'skills': 15, 'core': 10, 'ui': 8, 'intent': 5}
    ),
    architecture=ArchitectureInfo(
        pattern='plugin',
        components=['intent_engine', 'plugin_manager', 'handler'],
    ),
    business=BusinessInfo(
        features=['Intent Processing', 'Code Editor', 'Plugin System'],
        user_types=['Developer'],
        integrations=['API']
    )
)

# 添加 mock metadata
from client.src.business.project_matcher.project_analyzer import GitHubMetadata
github.metadata = GitHubMetadata(
    url='https://github.com/example/ai-ide',
    owner='example',
    repo='ai-ide',
    name='ai-ide',
    description='An AI-powered IDE with intelligent features',
    stars=5000,
    forks=500,
    language='Python',
    topics=['ai', 'ide', 'python']
)

print("\n[测试数据]")
print(f"GitHub: {github.metadata.owner}/{github.metadata.name} ({github.metadata.stars} stars)")
print(f"GitHub 类型: {github.project_type.value}")
print(f"GitHub 语言: {github.languages}")
print(f"GitHub 框架: {github.frameworks}")
print(f"GitHub 架构: {github.architecture.pattern}")
print()
print(f"本地: {local.project_type.value}")
print(f"本地 语言: {local.languages}")
print(f"本地 框架: {local.frameworks}")
print(f"本地 架构: {local.architecture.pattern}")

print("\n" + "=" * 60)
print("表层技术栈匹配")
print("=" * 60)

surface = create_surface_matcher().match(github, local)
print(f"\n表层匹配得分: {surface.score:.1f}/100")
print(f"  - 语言匹配: {surface.language_match:.1f}%")
print(f"  - 框架匹配: {surface.framework_match:.1f}%")
print(f"  - 数据库匹配: {surface.database_match:.1f}%")
print(f"  - 依赖重叠: {surface.dependency_overlap:.1f}%")
print(f"  - 结构相似: {surface.structure_similarity:.1f}%")
print("\n洞察:")
for insight in surface.insights:
    print(f"  [{insight.status.upper()}] {insight.message}")

print("\n" + "=" * 60)
print("架构模式匹配")
print("=" * 60)

arch = create_architectural_matcher().match(github, local)
print(f"\n架构匹配得分: {arch.score:.1f}/100")
print(f"  - 模式匹配: {arch.pattern_match:.1f}%")
print(f"  - 组件匹配: {arch.component_match:.1f}%")
print(f"  - 通信匹配: {arch.communication_match:.1f}%")
print(f"  - 质量差距: {arch.design_quality_gap:.1f}%")
print(f"迁移复杂度: {arch.migration_complexity}")
print("\n洞察:")
for insight in arch.insights:
    print(f"  - {insight}")
print("\n组件对比:")
for comp in arch.component_comparisons[:5]:
    print(f"  {comp.github_component} <-> {comp.local_component} ({comp.similarity:.2f})")

print("\n" + "=" * 60)
print("语义业务匹配")
print("=" * 60)

semantic = create_semantic_matcher().match(github, local)
print(f"\n语义匹配得分: {semantic.score:.1f}/100")
print(f"  - 功能覆盖: {semantic.feature_coverage:.1f}%")
print(f"  - 需求满足: {semantic.need_satisfaction:.1f}%")
print("\n洞察:")
for insight in semantic.insights:
    print(f"  - {insight}")
print("\n可复用功能:")
for feature in semantic.reusable_features:
    print(f"  + {feature}")
print("\n缺失功能 (可参考):")
for feature in semantic.missing_features:
    print(f"  - {feature}")

print("\n" + "=" * 60)
print("综合评估")
print("=" * 60)

evaluator = create_evaluator()
result = evaluator.evaluate(github, local)

print(f"\n总体得分: {result.total_score:.1f}/100")
print(f"匹配级别: {result.match_level.value}")
print(f"  - 表层技术栈: {result.surface_score:.1f}%")
print(f"  - 架构模式: {result.architectural_score:.1f}%")
print(f"  - 语义业务: {result.semantic_score:.1f}%")

print("\n关键洞察:")
for insight in result.insights:
    print(f"  - {insight}")

print("\n迁移建议:")
for sug in result.migration_suggestions[:5]:
    print(f"  [{sug.priority.upper()}] {sug.title}")
    print(f"    {sug.description[:60]}...")

print("\n风险预警:")
for warn in result.risk_warnings:
    print(f"  [{warn.severity.upper()}] {warn.message}")

print("\n" + "=" * 60)
print("文本报告")
print("=" * 60)
print(evaluator.generate_text_report(result))

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
