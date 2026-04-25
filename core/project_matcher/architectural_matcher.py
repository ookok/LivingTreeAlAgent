"""
Architectural Matcher - 架构模式匹配引擎
比较架构设计模式、组件组织、服务通信方式等
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from .project_analyzer import ProjectData


@dataclass
class ComponentComparison:
    """组件对比"""
    github_component: str
    local_component: str
    similarity: float  # 0-1
    match_type: str  # 'exact', 'similar', 'related'


@dataclass
class ArchitectureMatchResult:
    """架构匹配结果"""
    score: float  # 0-100
    pattern_match: float = 0.0
    component_match: float = 0.0
    communication_match: float = 0.0
    design_quality_gap: float = 0.0
    
    insights: List[str] = field(default_factory=list)
    component_comparisons: List[ComponentComparison] = field(default_factory=list)
    
    migration_complexity: str = 'unknown'  # low, medium, high, very_high
    refactoring_suggestions: List[str] = field(default_factory=list)


class ArchitecturalMatcher:
    """架构模式匹配器"""
    
    # 权重配置
    WEIGHTS = {
        'pattern': 40,        # 架构模式匹配
        'component': 35,      # 组件组织匹配
        'communication': 15,  # 通信方式匹配
        'quality': 10,       # 设计质量差距
    }
    
    # 架构模式映射
    ARCHITECTURE_PATTERNS = {
        'plugin': {
            'keywords': ['plugin', 'extension', 'addon', 'add-on', 'module', 'integration'],
            'components': ['plugin_manager', 'extension_point', 'handler', 'adapter', 'loader'],
            'shared_dirs': ['plugins', 'extensions', 'addons', 'modules', 'integrations']
        },
        'mvc': {
            'keywords': ['model', 'view', 'controller', 'presentation'],
            'components': ['model', 'view', 'controller', 'template', 'route'],
            'shared_dirs': ['models', 'views', 'controllers', 'templates']
        },
        'layered': {
            'keywords': ['layer', 'domain', 'application', 'infrastructure', 'service'],
            'components': ['domain', 'service', 'repository', 'gateway'],
            'shared_dirs': ['domain', 'application', 'infrastructure', 'services', 'repositories']
        },
        'monolith': {
            'keywords': ['src', 'app', 'main', 'core'],
            'components': ['main', 'core', 'shared', 'common'],
            'shared_dirs': ['src', 'app', 'core', 'shared']
        },
        'microservices': {
            'keywords': ['service', 'gateway', 'registry', 'container'],
            'components': ['service', 'gateway', 'registry', 'config'],
            'shared_dirs': ['services', 'gateways', 'service-registry', 'containers']
        },
        'event_driven': {
            'keywords': ['event', 'handler', 'listener', 'publisher', 'subscriber'],
            'components': ['event_bus', 'handler', 'listener', 'publisher', 'subscriber'],
            'shared_dirs': ['events', 'handlers', 'listeners', 'publishers']
        },
    }
    
    # 组件相似度矩阵
    COMPONENT_SIMILARITY = {
        # 认证相关
        ('auth', 'authentication'): 0.9,
        ('auth', 'login'): 0.7,
        ('auth', 'user'): 0.6,
        ('session', 'auth'): 0.6,
        
        # API相关
        ('api', 'gateway'): 0.8,
        ('api', 'route'): 0.7,
        ('api', 'controller'): 0.6,
        ('rest', 'api'): 0.8,
        
        # 数据相关
        ('database', 'db'): 0.9,
        ('repository', 'dao'): 0.8,
        ('repository', 'store'): 0.7,
        ('model', 'entity'): 0.8,
        
        # UI相关
        ('view', 'ui'): 0.7,
        ('view', 'component'): 0.6,
        ('panel', 'widget'): 0.8,
        ('window', 'dialog'): 0.7,
        
        # 业务逻辑
        ('service', 'manager'): 0.7,
        ('handler', 'processor'): 0.8,
        ('executor', 'runner'): 0.7,
        
        # 插件相关
        ('plugin', 'extension'): 0.9,
        ('plugin', 'module'): 0.7,
        ('adapter', 'connector'): 0.8,
        
        # AI相关
        ('agent', 'ai'): 0.8,
        ('engine', 'processor'): 0.6,
        ('intent', 'nlp'): 0.7,
        ('llm', 'model'): 0.8,
    }
    
    def match(self, github: ProjectData, local: ProjectData) -> ArchitectureMatchResult:
        """执行架构匹配"""
        result = ArchitectureMatchResult(score=0)
        
        # 1. 架构模式匹配
        result.pattern_match = self._match_patterns(github, local, result)
        
        # 2. 组件组织匹配
        result.component_match = self._match_components(github, local, result)
        
        # 3. 通信方式匹配
        result.communication_match = self._match_communication(github, local, result)
        
        # 4. 设计质量差距
        result.design_quality_gap = self._assess_quality_gap(github, local, result)
        
        # 计算总分
        result.score = (
            result.pattern_match * self.WEIGHTS['pattern'] / 100 +
            result.component_match * self.WEIGHTS['component'] / 100 +
            result.communication_match * self.WEIGHTS['communication'] / 100 +
            result.design_quality_gap * self.WEIGHTS['quality'] / 100
        )
        
        result.score = min(100, max(0, result.score))
        
        # 评估迁移复杂度
        result.migration_complexity = self._assess_migration_complexity(result)
        
        return result
    
    def _match_patterns(self, github: ProjectData, local: ProjectData,
                       result: ArchitectureMatchResult) -> float:
        """匹配架构模式"""
        github_pattern = self._normalize_pattern(github.architecture.pattern)
        local_pattern = self._normalize_pattern(local.architecture.pattern)
        
        if github_pattern == 'unknown' or local_pattern == 'unknown':
            result.insights.append(
                f"无法确定架构模式: GitHub={github_pattern}, 本地={local_pattern}"
            )
            return 50
        
        # 完全匹配
        if github_pattern == local_pattern:
            result.insights.append(f"架构模式一致: {github_pattern}")
            
            # 检查组件完整度
            github_components = set(github.architecture.components)
            local_components = set(local.architecture.components)
            
            if github_components == local_components:
                result.insights.append("组件组织完全一致")
                return 100
            elif github_components & local_components:
                shared = github_components & local_components
                result.insights.append(f"共享组件: {', '.join(shared)}")
                return 80
            return 70
        
        # 相似模式
        similar = self._are_patterns_similar(github_pattern, local_pattern)
        if similar:
            result.insights.append(
                f"架构模式相似: GitHub={github_pattern}, 本地={local_pattern} "
                "(可通过重构迁移)"
            )
            result.refactoring_suggestions.append(
                f"将 {local_pattern} 模式重构为 {github_pattern} 模式"
            )
            return 50
        
        # 不同模式
        result.insights.append(
            f"架构模式不同: GitHub={github_pattern}, 本地={local_pattern}"
        )
        result.refactoring_suggestions.append(
            f"需要架构重构: 从 {local_pattern} 迁移到 {github_pattern}"
        )
        return 25
    
    def _normalize_pattern(self, pattern: str) -> str:
        """规范化架构模式"""
        pattern_lower = pattern.lower()
        
        for name, info in self.ARCHITECTURE_PATTERNS.items():
            for keyword in info['keywords']:
                if keyword in pattern_lower:
                    return name
        
        return pattern_lower if pattern_lower else 'unknown'
    
    def _are_patterns_similar(self, p1: str, p2: str) -> bool:
        """检查两个模式是否相似"""
        similar_pairs = [
            ('monolith', 'layered'),
            ('layered', 'mvc'),
            ('plugin', 'monolith'),
            ('event_driven', 'microservices'),
        ]
        
        return (p1, p2) in similar_pairs or (p2, p1) in similar_pairs
    
    def _match_components(self, github: ProjectData, local: ProjectData,
                          result: ArchitectureMatchResult) -> float:
        """匹配组件组织"""
        github_components = self._extract_component_features(github)
        local_components = self._extract_component_features(local)
        
        if not github_components and not local_components:
            return 50
        
        # 计算组件相似度
        comparisons = []
        total_similarity = 0
        
        # GitHub 组件与本地组件的匹配
        for gh_comp in github_components:
            best_match = None
            best_similarity = 0
            
            for local_comp in local_components:
                sim = self._calculate_component_similarity(gh_comp, local_comp)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = local_comp
            
            if best_match and best_similarity > 0.3:
                comparisons.append(ComponentComparison(
                    github_component=gh_comp,
                    local_component=best_match,
                    similarity=best_similarity,
                    match_type='exact' if best_similarity > 0.8 else 
                               'similar' if best_similarity > 0.5 else 'related'
                ))
                total_similarity += best_similarity
        
        result.component_comparisons = comparisons
        
        # 计算分数
        if comparisons:
            avg_similarity = total_similarity / len(github_components)
            score = 100 * avg_similarity
            
            # 根据匹配数量调整
            match_ratio = len(comparisons) / max(len(github_components), len(local_components))
            score *= (0.5 + 0.5 * match_ratio)
            
            return min(100, score)
        
        return 20
    
    def _extract_component_features(self, data: ProjectData) -> List[str]:
        """提取组件特征"""
        components = []
        
        # 从架构组件
        components.extend(data.architecture.components)
        
        # 从主要目录
        components.extend(data.structure.main_directories.keys())
        
        # 从入口点
        for entry in data.architecture.entry_points:
            parts = entry.replace('/', '.').replace('\\', '.').split('.')
            components.extend([p for p in parts if len(p) > 2])
        
        # 规范化
        normalized = []
        for comp in components:
            comp = comp.lower().replace('_', ' ').replace('-', ' ')
            normalized.append(comp)
        
        return list(set(normalized))
    
    def _calculate_component_similarity(self, comp1: str, comp2: str) -> float:
        """计算组件相似度"""
        # 直接匹配
        if comp1 == comp2:
            return 1.0
        
        # 包含关系
        if comp1 in comp2 or comp2 in comp1:
            return 0.8
        
        # 查表
        comp1_lower = comp1.lower()
        comp2_lower = comp2.lower()
        
        for (c1, c2), sim in self.COMPONENT_SIMILARITY.items():
            if (c1 in comp1_lower and c2 in comp2_lower) or \
               (c2 in comp1_lower and c1 in comp2_lower):
                return sim
        
        # 词级别匹配
        words1 = set(comp1.split())
        words2 = set(comp2.split())
        
        intersection = words1 & words2
        if intersection:
            return len(intersection) / max(len(words1), len(words2))
        
        return 0
    
    def _match_communication(self, github: ProjectData, local: ProjectData,
                            result: ArchitectureMatchResult) -> float:
        """匹配通信方式"""
        # 检测通信模式
        github_comm = self._detect_communication_pattern(github)
        local_comm = self._detect_communication_pattern(local)
        
        # 计算匹配度
        if github_comm == local_comm:
            result.insights.append(f"通信方式一致: {github_comm}")
            return 100
        
        # 部分匹配
        if github_comm in ['http', 'grpc'] and local_comm in ['http', 'grpc']:
            result.insights.append(f"均使用远程通信: GitHub={github_comm}, 本地={local_comm}")
            return 70
        
        result.insights.append(f"通信方式不同: GitHub={github_comm}, 本地={local_comm}")
        return 30
    
    def _detect_communication_pattern(self, data: ProjectData) -> str:
        """检测通信模式"""
        all_text = ' '.join([
            ' '.join(data.frameworks),
            ' '.join(data.architecture.components),
            ' '.join(data.structure.main_directories.keys())
        ]).lower()
        
        # RPC/GRPC
        if 'grpc' in all_text or 'rpc' in all_text:
            return 'grpc'
        
        # HTTP/REST
        if 'rest' in all_text or 'api' in all_text or 'http' in all_text:
            return 'http'
        
        # 消息队列
        if 'mq' in all_text or 'kafka' in all_text or 'rabbit' in all_text:
            return 'message_queue'
        
        # 事件总线
        if 'event' in all_text or 'emit' in all_text:
            return 'event_bus'
        
        # 直接调用 (单体)
        return 'direct_call'
    
    def _assess_quality_gap(self, github: ProjectData, local: ProjectData,
                            result: ArchitectureMatchResult) -> float:
        """评估设计质量差距"""
        github_has_test = len(github.architecture.test_patterns) > 0
        local_has_test = len(local.architecture.test_patterns) > 0
        
        github_has_config = len(github.architecture.config_patterns) > 0
        local_has_config = len(local.architecture.config_patterns) > 0
        
        score = 50
        
        # 测试覆盖
        if github_has_test and not local_has_test:
            result.insights.append("GitHub项目有测试覆盖，本地项目缺失")
            result.refactoring_suggestions.append("添加单元测试和集成测试")
            score -= 10
        elif not github_has_test and local_has_test:
            score += 10
        
        # 配置管理
        if github_has_config and not local_has_config:
            result.insights.append("GitHub项目有配置文件，本地项目缺失")
            result.refactoring_suggestions.append("引入配置文件管理")
            score -= 10
        elif not github_has_config and local_has_config:
            score += 10
        
        # 项目规模
        github_scale = github.structure.file_count
        local_scale = local.structure.file_count
        
        if github_scale > local_scale * 2:
            result.insights.append(
                f"GitHub项目规模较大: {github_scale} vs {local_scale} 文件"
            )
        
        return max(0, min(100, score))
    
    def _assess_migration_complexity(self, result: ArchitectureMatchResult) -> str:
        """评估迁移复杂度"""
        # 基于分数和重构建议数量
        factors = []
        
        # 模式差异
        if result.pattern_match < 30:
            factors.append('high')
        elif result.pattern_match < 60:
            factors.append('medium')
        
        # 组件差异
        if result.component_match < 30:
            factors.append('high')
        elif result.component_match < 60:
            factors.append('medium')
        
        # 重构建议
        if len(result.refactoring_suggestions) > 5:
            factors.append('high')
        elif len(result.refactoring_suggestions) > 2:
            factors.append('medium')
        
        if not factors:
            return 'low'
        
        high_count = factors.count('high')
        if high_count >= 2:
            return 'very_high'
        elif high_count == 1 or factors.count('medium') >= 2:
            return 'high'
        else:
            return 'medium'


# 工厂函数
def create_architectural_matcher() -> ArchitecturalMatcher:
    """创建架构匹配器"""
    return ArchitecturalMatcher()


if __name__ == '__main__':
    # 测试
    from project_analyzer import ProjectData, ArchitectureInfo, CodeStructure, ProjectType
    
    github = ProjectData(
        project_type=ProjectType.DESKTOP,
        architecture=ArchitectureInfo(
            pattern='plugin',
            components=['plugin_manager', 'extension_point', 'handler', 'panel'],
            entry_points=['main.py']
        ),
        structure=CodeStructure(
            main_directories={'plugins': 20, 'core': 15, 'ui': 10}
        )
    )
    
    local = ProjectData(
        project_type=ProjectType.IDE_PLUGIN,
        architecture=ArchitectureInfo(
            pattern='plugin',
            components=['skill_manager', 'handler', 'adapter'],
            entry_points=['main.py']
        ),
        structure=CodeStructure(
            main_directories={'skills': 15, 'core': 10, 'ui': 8}
        )
    )
    
    matcher = create_architectural_matcher()
    result = matcher.match(github, local)
    
    print(f"Architecture Match Score: {result.score:.1f}/100")
    print(f"Migration Complexity: {result.migration_complexity}")
    print("\nInsights:")
    for insight in result.insights:
        print(f"  - {insight}")
    print("\nComponent Comparisons:")
    for comp in result.component_comparisons:
        print(f"  {comp.github_component} <-> {comp.local_component} ({comp.similarity:.2f})")
