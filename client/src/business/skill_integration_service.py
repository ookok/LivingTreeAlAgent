"""
技能集成服务 (Skill Integration Service)
=======================================

参考: github.com/vercel/find-skills

将技能发现、匹配和图谱整合到系统中：
1. 技能注册中心 - 管理系统技能
2. 技能匹配服务 - 匹配用户需求与技能
3. 技能图谱服务 - 管理技能关系
4. 技能推荐服务 - 推荐相关技能

核心特性：
- 统一技能管理
- 智能技能匹配
- 技能关系图谱
- 个性化推荐

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = __import__('logging').getLogger(__name__)


@dataclass
class RegisteredSkill:
    """注册的技能"""
    name: str
    category: str
    level: str
    score: float = 0.0
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    last_used: float = 0.0
    usage_count: int = 0


@dataclass
class SkillMatchResult:
    """技能匹配结果"""
    matches: List[dict]
    recommendations: List[dict]
    gaps: List[dict]
    suggested_plan: List[str]


class SkillIntegrationService:
    """
    技能集成服务
    
    统一管理系统中的技能，提供：
    1. 技能注册和管理
    2. 技能匹配
    3. 技能推荐
    4. 技能路径规划
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 延迟加载组件
        self._skill_discovery = None
        self._skill_matcher = None
        self._skill_graph = None
        
        # 已注册技能
        self._registered_skills: Dict[str, RegisteredSkill] = {}
        
        # 技能索引
        self._skill_index = {}
        
        # 初始化默认技能
        self._initialize_default_skills()
        
        self._initialized = True
        logger.info("[SkillIntegrationService] 技能集成服务初始化完成")
    
    def _initialize_default_skills(self):
        """初始化默认技能"""
        default_skills = [
            RegisteredSkill(
                name="python",
                category="language",
                level="expert",
                score=10.0,
                description="Python 编程语言",
                capabilities=["代码编写", "数据处理", "自动化"],
            ),
            RegisteredSkill(
                name="pyqt",
                category="framework",
                level="advanced",
                score=8.0,
                description="PyQt6 GUI 框架",
                capabilities=["桌面应用", "UI设计", "界面开发"],
            ),
            RegisteredSkill(
                name="llm",
                category="ai",
                level="advanced",
                score=9.0,
                description="大语言模型",
                capabilities=["对话", "内容生成", "智能助手"],
            ),
            RegisteredSkill(
                name="rag",
                category="ai",
                level="intermediate",
                score=7.0,
                description="检索增强生成",
                capabilities=["知识检索", "问答系统", "文档分析"],
            ),
            RegisteredSkill(
                name="api",
                category="domain",
                level="advanced",
                score=8.0,
                description="API 开发",
                capabilities=["REST API", "后端服务", "数据接口"],
            ),
            RegisteredSkill(
                name="asyncio",
                category="library",
                level="advanced",
                score=7.0,
                description="异步编程",
                capabilities=["高性能", "并发处理", "异步IO"],
            ),
            RegisteredSkill(
                name="docker",
                category="tool",
                level="intermediate",
                score=6.0,
                description="容器化部署",
                capabilities=["部署", "环境管理", "CI/CD"],
            ),
            RegisteredSkill(
                name="testing",
                category="methodology",
                level="advanced",
                score=7.0,
                description="测试方法论",
                capabilities=["单元测试", "集成测试", "TDD"],
            ),
        ]
        
        for skill in default_skills:
            self._registered_skills[skill.name] = skill
    
    def register_skill(self, skill: RegisteredSkill):
        """
        注册技能
        
        Args:
            skill: 技能对象
        """
        self._registered_skills[skill.name] = skill
        logger.info(f"[SkillIntegrationService] 注册技能: {skill.name}")
    
    def unregister_skill(self, skill_name: str):
        """
        注销技能
        
        Args:
            skill_name: 技能名称
        """
        if skill_name in self._registered_skills:
            del self._registered_skills[skill_name]
            logger.info(f"[SkillIntegrationService] 注销技能: {skill_name}")
    
    def get_skill(self, skill_name: str) -> Optional[RegisteredSkill]:
        """
        获取技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能对象
        """
        return self._registered_skills.get(skill_name)
    
    def get_all_skills(self) -> List[RegisteredSkill]:
        """获取所有技能"""
        return list(self._registered_skills.values())
    
    def get_skills_by_category(self, category: str) -> List[RegisteredSkill]:
        """按分类获取技能"""
        return [s for s in self._registered_skills.values() if s.category == category]
    
    async def discover_skills(self, repo_path: str = "client/src") -> List[dict]:
        """
        发现代码库中的技能
        
        Args:
            repo_path: 代码库路径
            
        Returns:
            发现的技能列表
        """
        self._lazy_load_components()
        
        if self._skill_discovery:
            result = self._skill_discovery.analyze_repo(repo_path)
            
            # 更新注册的技能
            for skill in result.skills:
                if skill.name in self._registered_skills:
                    self._registered_skills[skill.name].score = skill.score
                    self._registered_skills[skill.name].level = skill.level.value
            
            return [self._skill_to_dict(s) for s in result.skills]
        
        return []
    
    async def match_skills(self, requirement: str) -> SkillMatchResult:
        """
        匹配用户需求与技能
        
        Args:
            requirement: 用户需求描述
            
        Returns:
            匹配结果
        """
        self._lazy_load_components()
        
        available_skills = list(self._registered_skills.keys())
        
        # 匹配技能
        matches = []
        if self._skill_matcher:
            skill_matches = self._skill_matcher.match(requirement, available_skills)
            matches = [self._match_to_dict(m) for m in skill_matches]
        
        # 推荐技能
        recommendations = []
        if self._skill_matcher:
            recs = self._skill_matcher.recommend(requirement, available_skills)
            recommendations = [self._recommendation_to_dict(r) for r in recs]
        
        # 分析差距（简化版本）
        gaps = []
        
        # 生成建议计划
        suggested_plan = self._generate_plan(requirement, matches)
        
        return SkillMatchResult(
            matches=matches,
            recommendations=recommendations,
            gaps=gaps,
            suggested_plan=suggested_plan,
        )
    
    def _generate_plan(self, requirement: str, matches: List[dict]) -> List[str]:
        """生成建议计划"""
        plan = []
        
        if matches:
            plan.append(f"根据需求分析，推荐使用以下技能:")
            for match in matches[:3]:
                plan.append(f"  • {match['skill_name']} (匹配度: {match['confidence']})")
            
            plan.append("")
            plan.append("建议执行步骤:")
            plan.append("1. 分析任务需求")
            plan.append("2. 选择合适的技能")
            plan.append("3. 执行任务")
            plan.append("4. 评估结果")
        
        return plan
    
    async def recommend_skills(self, context: str) -> List[dict]:
        """
        推荐技能
        
        Args:
            context: 上下文描述
            
        Returns:
            推荐列表
        """
        self._lazy_load_components()
        
        available_skills = list(self._registered_skills.keys())
        
        if self._skill_matcher:
            recs = self._skill_matcher.recommend(context, available_skills)
            return [self._recommendation_to_dict(r) for r in recs]
        
        return []
    
    async def build_graph(self):
        """构建技能图谱"""
        self._lazy_load_components()
        
        if self._skill_graph:
            # 从注册技能构建图谱
            skills_data = [
                {
                    "name": s.name,
                    "category": s.category,
                    "level": s.level,
                    "score": s.score,
                }
                for s in self._registered_skills.values()
            ]
            self._skill_graph.build_from_skills(skills_data)
            
            logger.info("[SkillIntegrationService] 技能图谱构建完成")
    
    def find_skill_path(self, source: str, target: str) -> Optional[dict]:
        """
        查找技能路径
        
        Args:
            source: 源技能
            target: 目标技能
            
        Returns:
            路径信息
        """
        self._lazy_load_components()
        
        if self._skill_graph:
            path = self._skill_graph.find_shortest_path(source, target)
            if path:
                return {
                    "path": path.path,
                    "distance": path.distance,
                }
        
        return None
    
    def get_skill_clusters(self) -> List[dict]:
        """获取技能聚类"""
        self._lazy_load_components()
        
        if self._skill_graph:
            clusters = self._skill_graph.cluster()
            return [self._cluster_to_dict(c) for c in clusters]
        
        return []
    
    def analyze_influence(self) -> Dict[str, float]:
        """分析技能影响力"""
        self._lazy_load_components()
        
        if self._skill_graph:
            return self._skill_graph.analyze_influence()
        
        return {}
    
    def _lazy_load_components(self):
        """延迟加载组件"""
        if self._skill_discovery is None:
            from business.skill_discovery import create_skill_discovery
            self._skill_discovery = create_skill_discovery()
        
        if self._skill_matcher is None:
            from business.skill_matcher import create_skill_matcher
            self._skill_matcher = create_skill_matcher()
        
        if self._skill_graph is None:
            from business.skill_graph import create_skill_graph
            self._skill_graph = create_skill_graph()
    
    def _skill_to_dict(self, skill) -> dict:
        """技能转字典"""
        return {
            "name": skill.name,
            "category": skill.category.value if hasattr(skill.category, 'value') else skill.category,
            "level": skill.level.value if hasattr(skill.level, 'value') else skill.level,
            "score": skill.score,
            "evidence": skill.evidence,
            "files": skill.files,
        }
    
    def _match_to_dict(self, match) -> dict:
        """匹配结果转字典"""
        return {
            "skill_name": match.skill_name,
            "match_type": match.match_type.value,
            "confidence": match.confidence.value,
            "score": match.score,
            "relevance": match.relevance,
            "explanation": match.explanation,
        }
    
    def _recommendation_to_dict(self, rec) -> dict:
        """推荐转字典"""
        return {
            "skill_name": rec.skill_name,
            "category": rec.category,
            "relevance_score": rec.relevance_score,
            "reason": rec.reason,
            "suggested_use": rec.suggested_use,
        }
    
    def _cluster_to_dict(self, cluster) -> dict:
        """聚类转字典"""
        return {
            "name": cluster.name,
            "skills": cluster.skills,
            "centroid": cluster.centroid,
            "cohesion": cluster.cohesion,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "registered_skills": len(self._registered_skills),
            "categories": len(set(s.category for s in self._registered_skills.values())),
        }
        
        if self._skill_graph:
            stats.update(self._skill_graph.get_stats())
        
        return stats


# 便捷函数
def get_skill_integration_service() -> SkillIntegrationService:
    """获取技能集成服务单例"""
    return SkillIntegrationService()


__all__ = [
    "RegisteredSkill",
    "SkillMatchResult",
    "SkillIntegrationService",
    "get_skill_integration_service",
]
