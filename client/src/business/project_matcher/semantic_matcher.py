"""
Semantic Matcher - 语义业务匹配引擎
比较业务功能、用户类型、集成需求等业务层面的匹配度
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from .project_analyzer import ProjectData


@dataclass
class FeatureMatch:
    """功能匹配"""
    github_feature: str
    local_feature: str = ""
    similarity: float = 0.0
    match_type: str = 'unknown'  # 'exact', 'similar', 'related', 'needed', 'available'
    local_need_score: float = 0.0  # 本地项目对这个功能的需求程度


@dataclass
class SemanticMatchResult:
    """语义匹配结果"""
    score: float  # 0-100
    feature_coverage: float = 0.0  # GitHub 功能被本地覆盖的比例
    need_satisfaction: float = 0.0  # 本地需求被 GitHub 满足的比例
    
    insights: List[str] = field(default_factory=list)
    feature_matches: List[FeatureMatch] = field(default_factory=list)
    
    reusable_features: List[str] = field(default_factory=list)  # 可复用的功能
    missing_features: List[str] = field(default_factory=list)   # 本地缺失的功能
    reference_features: List[str] = field(default_factory=list) # 可参考的功能
    
    learning_opportunities: List[str] = field(default_factory=list)  # 学习机会


class SemanticMatcher:
    """语义业务匹配器"""
    
    # 功能类别关键词
    FEATURE_CATEGORIES = {
        'user_management': {
            'keywords': ['user', 'account', 'auth', 'login', 'register', 'permission', 'role', 'profile'],
            'weight': 1.2
        },
        'ai_capability': {
            'keywords': ['ai', 'llm', 'gpt', 'model', 'nlp', 'intent', 'agent', 'chatbot', 'assistant', 'reasoning'],
            'weight': 1.5
        },
        'data_processing': {
            'keywords': ['data', 'database', 'storage', 'cache', 'analytics', 'report', 'metric'],
            'weight': 1.0
        },
        'integration': {
            'keywords': ['api', 'webhook', 'integration', 'plugin', 'extension', 'connect', 'sync'],
            'weight': 1.0
        },
        'ui_component': {
            'keywords': ['ui', 'interface', 'panel', 'widget', 'dialog', 'window', 'layout', 'view'],
            'weight': 0.8
        },
        'collaboration': {
            'keywords': ['team', 'share', 'collaborate', 'project', 'workspace', 'organization'],
            'weight': 0.9
        },
        'security': {
            'keywords': ['security', 'encrypt', 'token', 'jwt', 'oauth', 'sso', 'ldap'],
            'weight': 1.1
        },
        'workflow': {
            'keywords': ['workflow', 'automation', 'pipeline', 'task', 'schedule', 'cron'],
            'weight': 0.9
        }
    }
    
    # 功能相似度
    FEATURE_SIMILARITY = {
        ('user', 'auth'): 0.9,
        ('user', 'account'): 0.9,
        ('auth', 'login'): 0.8,
        ('permission', 'role'): 0.8,
        ('ai', 'llm'): 0.9,
        ('ai', 'model'): 0.7,
        ('agent', 'ai'): 0.8,
        ('intent', 'nlp'): 0.7,
        ('panel', 'ui'): 0.8,
        ('widget', 'component'): 0.8,
        ('api', 'integration'): 0.7,
        ('plugin', 'extension'): 0.9,
        ('database', 'storage'): 0.8,
        ('cache', 'storage'): 0.6,
        ('report', 'analytics'): 0.8,
        ('workflow', 'automation'): 0.8,
    }
    
    # 需求强度矩阵 (基于本地项目特征推断)
    NEED_STRENGTH = {
        'user_management': 0.7,  # 大多数项目需要
        'ai_capability': 1.0,   # 如果本地是 AI 项目，强烈需要
        'data_processing': 0.8,
        'integration': 0.9,
        'ui_component': 0.9,
        'collaboration': 0.5,
        'security': 0.8,
        'workflow': 0.6,
    }
    
    def match(self, github: ProjectData, local: ProjectData) -> SemanticMatchResult:
        """执行语义匹配"""
        result = SemanticMatchResult(score=0)
        
        # 1. 功能覆盖分析
        self._analyze_feature_coverage(github, local, result)
        
        # 2. 需求满足分析
        self._analyze_need_satisfaction(github, local, result)
        
        # 3. 提取可复用功能
        self._extract_reusable_features(github, local, result)
        
        # 4. 识别缺失功能
        self._identify_missing_features(github, local, result)
        
        # 5. 发现学习机会
        self._discover_learning_opportunities(github, local, result)
        
        # 计算总分
        result.score = (
            result.feature_coverage * 0.4 +
            result.need_satisfaction * 0.4 +
            min(100, len(result.reusable_features) * 10) * 0.2
        )
        
        return result
    
    def _analyze_feature_coverage(self, github: ProjectData, local: ProjectData,
                                  result: SemanticMatchResult):
        """分析 GitHub 功能在本地项目的覆盖情况"""
        github_features = self._extract_features_with_category(github)
        local_features = self._extract_features_with_category(local)
        
        if not github_features:
            result.insights.append("无法从 GitHub 项目提取功能信息")
            return
        
        covered = 0
        for gh_feature, gh_category in github_features:
            # 检查本地是否有类似功能
            matched = False
            best_match = None
            best_similarity = 0
            
            for local_feature, local_category in local_features:
                sim = self._calculate_feature_similarity(
                    gh_feature, gh_category, local_feature, local_category
                )
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = (local_feature, local_category)
            
            if best_similarity > 0.5:
                covered += 1
                result.feature_matches.append(FeatureMatch(
                    github_feature=gh_feature,
                    local_feature=best_match[0] if best_match else "",
                    similarity=best_similarity,
                    match_type='exact' if best_similarity > 0.8 else 'similar'
                ))
            elif best_similarity > 0.3:
                result.feature_matches.append(FeatureMatch(
                    github_feature=gh_feature,
                    local_feature=best_match[0] if best_match else "",
                    similarity=best_similarity,
                    match_type='related'
                ))
        
        result.feature_coverage = 100 * covered / len(github_features) if github_features else 0
        
        if result.feature_coverage > 50:
            result.insights.append(
                f"功能覆盖良好: {result.feature_coverage:.0f}% "
                f"({covered}/{len(github_features)} 功能相似)"
            )
        elif result.feature_coverage > 20:
            result.insights.append(
                f"部分功能重叠: {result.feature_coverage:.0f}% "
                f"({covered}/{len(github_features)} 功能)"
            )
        else:
            result.insights.append(
                f"功能差异较大: 只有 {result.feature_coverage:.0f}% 功能相似"
            )
    
    def _analyze_need_satisfaction(self, github: ProjectData, local: ProjectData,
                                   result: SemanticMatchResult):
        """分析本地需求被 GitHub 项目满足的程度"""
        local_needed = self._infer_local_needs(local)
        github_available = self._extract_available_capabilities(github)
        
        if not local_needed:
            result.insights.append("无法推断本地项目需求")
            result.need_satisfaction = 50
            return
        
        satisfied = 0
        total_need = 0
        
        for need, category, strength in local_needed:
            total_need += strength
            matched = False
            
            for capability, cap_cat in github_available:
                sim = self._calculate_feature_similarity(need, category, capability, cap_cat)
                if sim > 0.4:
                    matched = True
                    result.feature_matches.append(FeatureMatch(
                        github_feature=capability,
                        local_feature=need,
                        similarity=sim,
                        match_type='needed',
                        local_need_score=strength
                    ))
                    break
            
            if matched:
                satisfied += strength
        
        result.need_satisfaction = 100 * satisfied / total_need if total_need > 0 else 0
        
        if result.need_satisfaction > 70:
            result.insights.append(
                f"高度满足本地需求: {result.need_satisfaction:.0f}%"
            )
        elif result.need_satisfaction > 40:
            result.insights.append(
                f"部分满足本地需求: {result.need_satisfaction:.0f}%"
            )
        else:
            result.insights.append(
                f"GitHub 项目未能满足本地主要需求: {result.need_satisfaction:.0f}%"
            )
    
    def _extract_features_with_category(self, data: ProjectData) -> List[Tuple[str, str]]:
        """提取带类别的功能"""
        features = []
        
        # 从业务特性
        for feature in data.business.features:
            category = self._get_feature_category(feature)
            features.append((feature.lower(), category))
        
        # 从架构组件推断
        for component in data.architecture.components:
            category = self._get_feature_category(component)
            features.append((component.lower(), category))
        
        # 从主要目录推断
        for dir_name in data.structure.main_directories.keys():
            category = self._get_feature_category(dir_name)
            features.append((dir_name.lower(), category))
        
        # 去重
        seen = set()
        unique = []
        for feature, category in features:
            key = (feature, category)
            if key not in seen:
                seen.add(key)
                unique.append((feature, category))
        
        return unique
    
    def _get_feature_category(self, feature: str) -> str:
        """获取功能类别"""
        feature_lower = feature.lower()
        
        best_category = 'other'
        best_score = 0
        
        for category, info in self.FEATURE_CATEGORIES.items():
            score = 0
            for keyword in info['keywords']:
                if keyword in feature_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_category = category
        
        return best_category
    
    def _calculate_feature_similarity(self, f1: str, c1: str, f2: str, c2: str) -> float:
        """计算功能相似度"""
        # 同类别
        if c1 == c2 and c1 != 'other':
            base = 0.6
        else:
            base = 0.3
        
        # 文本相似度
        words1 = set(f1.split())
        words2 = set(f2.split())
        
        if words1 & words2:
            overlap = len(words1 & words2)
            text_sim = overlap / max(len(words1), len(words2))
        else:
            text_sim = 0
        
        # 查表
        lookup_sim = 0
        f1_lower = f1.lower()
        f2_lower = f2.lower()
        
        for (w1, w2), sim in self.FEATURE_SIMILARITY.items():
            if (w1 in f1_lower and w2 in f2_lower) or \
               (w2 in f1_lower and w1 in f2_lower):
                lookup_sim = max(lookup_sim, sim)
        
        # 综合
        similarity = max(base + text_sim * 0.2 + lookup_sim * 0.3, lookup_sim)
        
        return min(1.0, similarity)
    
    def _infer_local_needs(self, local: ProjectData) -> List[Tuple[str, str, float]]:
        """推断本地项目的需求"""
        needs = []
        
        # 基于项目类型推断
        project_type = local.project_type.value.lower()
        
        if 'ai' in project_type or 'ml' in project_type:
            needs.append(('ai_model_integration', 'ai_capability', 1.0))
            needs.append(('intent_understanding', 'ai_capability', 0.9))
        
        if 'desktop' in project_type or 'plugin' in project_type:
            needs.append(('ui_component', 'ui_component', 0.9))
            needs.append(('plugin_system', 'integration', 0.8))
        
        if 'web' in project_type:
            needs.append(('api_design', 'integration', 0.9))
            needs.append(('user_management', 'user_management', 0.8))
        
        # 基于业务特性
        for feature, category in self._extract_features_with_category(local):
            if category != 'other':
                # 本地已有的功能也是"需要保持"的需求
                needs.append((feature, category, 0.5))
        
        # 基于用户类型
        for user_type in local.business.user_types:
            if '开发' in user_type:
                needs.append(('code_editor', 'ui_component', 0.7))
                needs.append(('intellisense', 'ai_capability', 0.6))
        
        # 常见需求
        needs.append(('configuration', 'data_processing', 0.7))
        needs.append(('error_handling', 'security', 0.6))
        
        return needs
    
    def _extract_available_capabilities(self, github: ProjectData) -> List[Tuple[str, str]]:
        """提取 GitHub 项目可用的能力"""
        capabilities = []
        
        # 从 README 特性
        for feature in github.business.features:
            category = self._get_feature_category(feature)
            capabilities.append((feature.lower(), category))
        
        # 从框架推断
        for framework in github.frameworks:
            category = self._get_feature_category(framework)
            capabilities.append((framework.lower(), category))
        
        # 从架构组件
        for component in github.architecture.components:
            category = self._get_feature_category(component)
            capabilities.append((component.lower(), category))
        
        return capabilities
    
    def _extract_reusable_features(self, github: ProjectData, local: ProjectData,
                                  result: SemanticMatchResult):
        """提取可复用的功能"""
        github_features = set(f.lower() for f, _ in self._extract_features_with_category(github))
        local_features = set(f.lower() for f, _ in self._extract_features_with_category(local))
        
        # 完全匹配
        exact_matches = github_features & local_features
        
        # 相似匹配
        similar_matches = []
        for gh_f in github_features:
            if gh_f in exact_matches:
                continue
            for local_f in local_features:
                sim = self._calculate_feature_similarity(
                    gh_f, 'other', local_f, 'other'
                )
                if sim > 0.6:
                    similar_matches.append((gh_f, local_f, sim))
                    break
        
        # 高相似度 (可复用)
        for gh_f, local_f, sim in sorted(similar_matches, key=lambda x: -x[2])[:5]:
            if sim > 0.7:
                result.reusable_features.append(gh_f)
        
        if result.reusable_features:
            result.insights.append(
                f"可复用功能: {', '.join(result.reusable_features[:3])}"
            )
    
    def _identify_missing_features(self, github: ProjectData, local: ProjectData,
                                  result: SemanticMatchResult):
        """识别本地缺失的功能"""
        github_features = set(f.lower() for f, _ in self._extract_features_with_category(github))
        local_features = set(f.lower() for f, _ in self._extract_features_with_category(local))
        
        # GitHub 有但本地没有的
        missing = []
        
        for gh_f in github_features:
            if gh_f not in local_features:
                # 检查是否"需要"
                is_needed = False
                for local_f in local_features:
                    sim = self._calculate_feature_similarity(gh_f, 'other', local_f, 'other')
                    if sim > 0.5:
                        is_needed = True
                        break
                
                if is_needed:
                    missing.append(gh_f)
        
        # 优先显示高权重类别的缺失功能
        weighted_missing = []
        for feature in missing:
            category = self._get_feature_category(feature)
            weight = self.FEATURE_CATEGORIES.get(category, {}).get('weight', 1.0)
            weighted_missing.append((feature, weight))
        
        weighted_missing.sort(key=lambda x: -x[1])
        result.missing_features = [f for f, _ in weighted_missing[:5]]
        
        if result.missing_features:
            result.insights.append(
                f"本地缺失功能 (可参考): {', '.join(result.missing_features[:3])}"
            )
    
    def _discover_learning_opportunities(self, github: ProjectData, local: ProjectData,
                                        result: SemanticMatchResult):
        """发现学习机会"""
        opportunities = []
        
        # GitHub 项目的优势领域
        github_categories = set()
        for feature, category in self._extract_features_with_category(github):
            if category != 'other':
                github_categories.add(category)
        
        local_categories = set()
        for feature, category in self._extract_features_with_category(local):
            if category != 'other':
                local_categories.add(category)
        
        # GitHub 有但本地没有的类别
        new_categories = github_categories - local_categories
        
        category_descriptions = {
            'ai_capability': 'AI 能力 (LLM集成、意图理解)',
            'security': '安全特性 (认证、授权、加密)',
            'workflow': '工作流自动化',
            'collaboration': '团队协作功能',
            'integration': '第三方集成',
        }
        
        for category in new_categories:
            desc = category_descriptions.get(category, category)
            opportunities.append(f"学习 {desc} 的最佳实践")
        
        # GitHub 项目的高分特性
        if github.metadata and github.metadata.stars > 1000:
            opportunities.append(f"参考高星项目 ({github.metadata.stars} stars) 的架构设计")
        
        result.learning_opportunities = opportunities[:5]
        
        if opportunities:
            result.insights.append(
                f"学习机会: {opportunities[0]}"
            )


# 工厂函数
def create_semantic_matcher() -> SemanticMatcher:
    """创建语义匹配器"""
    return SemanticMatcher()


if __name__ == '__main__':
    # 测试
    from project_analyzer import ProjectData, BusinessInfo, ArchitectureInfo, ProjectType
    
    github = ProjectData(
        project_type=ProjectType.AI_ML,
        business=BusinessInfo(
            features=['LLM Integration', 'Intent Engine', 'Code Generation', 'User Authentication'],
            user_types=['Developer', 'Enterprise']
        ),
        architecture=ArchitectureInfo(
            components=['agent', 'intent_classifier', 'llm_adapter'],
        ),
        frameworks={'Transformers', 'LangChain'}
    )
    
    local = ProjectData(
        project_type=ProjectType.IDE_PLUGIN,
        business=BusinessInfo(
            features=['Intent Processing', 'Code Editor', 'Plugin System'],
            user_types=['Developer']
        ),
        architecture=ArchitectureInfo(
            components=['intent_engine', 'plugin_manager'],
        ),
        frameworks={'PyQt6'}
    )
    
    matcher = create_semantic_matcher()
    result = matcher.match(github, local)
    
    print(f"Semantic Match Score: {result.score:.1f}/100")
    print(f"Feature Coverage: {result.feature_coverage:.1f}%")
    print(f"Need Satisfaction: {result.need_satisfaction:.1f}%")
    print("\nInsights:")
    for insight in result.insights:
        print(f"  - {insight}")
    print("\nMissing Features:")
    for feature in result.missing_features:
        print(f"  - {feature}")
