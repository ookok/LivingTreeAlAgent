"""
技能匹配引擎 (Skill Matcher)
=============================

参考: github.com/vercel/find-skills

实现技能匹配和推荐功能：
1. 技能匹配 - 将用户需求与可用技能进行智能匹配
2. 技能推荐 - 根据上下文推荐相关技能
3. 技能差距分析 - 分析当前技能与需求之间的差距
4. 技能路径规划 - 规划获取新技能的路径

核心特性：
- 语义匹配 - 基于语义相似度匹配技能
- 上下文感知 - 根据上下文推荐技能
- 差距分析 - 分析技能差距
- 路径规划 - 规划技能获取路径

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class MatchType(Enum):
    """匹配类型"""
    EXACT = "exact"           # 精确匹配
    SEMANTIC = "semantic"     # 语义匹配
    CONTEXTUAL = "contextual" # 上下文匹配
    RELATED = "related"       # 相关匹配


class MatchConfidence(Enum):
    """匹配置信度"""
    HIGH = "high"       # 高
    MEDIUM = "medium"   # 中
    LOW = "low"         # 低


@dataclass
class SkillMatch:
    """技能匹配结果"""
    skill_name: str
    match_type: MatchType
    confidence: MatchConfidence
    score: float
    relevance: float
    explanation: str = ""


@dataclass
class SkillGap:
    """技能差距"""
    required_skill: str
    current_level: str
    required_level: str
    gap_score: float
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class SkillRecommendation:
    """技能推荐"""
    skill_name: str
    category: str
    relevance_score: float
    reason: str
    suggested_use: str = ""


class SkillMatcher:
    """
    技能匹配引擎
    
    功能：
    1. 技能匹配 - 将用户需求与可用技能匹配
    2. 技能推荐 - 根据上下文推荐技能
    3. 差距分析 - 分析技能差距
    4. 路径规划 - 规划技能获取路径
    """
    
    def __init__(self):
        # 技能同义词库
        self._skill_synonyms = {
            "python": ["python", "py", "python3"],
            "javascript": ["javascript", "js", "ecmascript"],
            "typescript": ["typescript", "ts"],
            "pyqt": ["pyqt", "qt", "qt6", "pyqt6"],
            "react": ["react", "reactjs", "react.js"],
            "api": ["api", "rest", "restful", "endpoint"],
            "llm": ["llm", "ai", "chatbot", "gpt", "claude"],
            "rag": ["rag", "retrieval", "vector database", "embedding"],
            "async": ["async", "asyncio", "asynchronous"],
            "database": ["database", "db", "sql", "postgres", "mysql"],
            "docker": ["docker", "container", "containerization"],
            "testing": ["testing", "test", "pytest", "unit test"],
        }
        
        # 技能关系图谱
        self._skill_relations = {
            "llm": ["rag", "embedding", "prompt", "api"],
            "rag": ["llm", "vector database", "embedding", "search"],
            "pyqt": ["qt", "gui", "desktop", "ui"],
            "api": ["rest", "graphql", "websocket", "http"],
            "async": ["asyncio", "concurrency", "parallel"],
            "docker": ["kubernetes", "devops", "container"],
            "testing": ["tdd", "unit test", "integration test"],
        }
        
        # 需求关键词到技能的映射
        self._requirement_mapping = {
            "写代码": ["python", "javascript", "typescript"],
            "创建界面": ["pyqt", "react", "vue"],
            "构建api": ["fastapi", "flask", "api"],
            "数据库": ["database", "sql", "orm"],
            "部署": ["docker", "kubernetes", "devops"],
            "测试": ["testing", "pytest", "tdd"],
            "ai": ["llm", "rag", "ml"],
            "聊天": ["llm", "chatbot", "nlp"],
            "搜索": ["search", "rag", "vector"],
            "优化": ["performance", "optimization", "caching"],
            "安全": ["security", "encryption", "authentication"],
        }
    
    def match(self, requirement: str, available_skills: List[str]) -> List[SkillMatch]:
        """
        匹配技能
        
        Args:
            requirement: 用户需求描述
            available_skills: 可用技能列表
            
        Returns:
            匹配结果列表
        """
        matches = []
        
        # 1. 精确匹配
        exact_matches = self._exact_match(requirement, available_skills)
        matches.extend(exact_matches)
        
        # 2. 语义匹配
        semantic_matches = self._semantic_match(requirement, available_skills)
        matches.extend(semantic_matches)
        
        # 3. 上下文匹配
        contextual_matches = self._contextual_match(requirement, available_skills)
        matches.extend(contextual_matches)
        
        # 去重并排序
        matches = self._deduplicate_matches(matches)
        matches.sort(key=lambda m: m.score, reverse=True)
        
        return matches
    
    def _exact_match(self, requirement: str, available_skills: List[str]) -> List[SkillMatch]:
        """精确匹配"""
        matches = []
        
        requirement_lower = requirement.lower()
        
        for skill in available_skills:
            # 检查技能名称是否在需求中
            if skill.lower() in requirement_lower:
                matches.append(SkillMatch(
                    skill_name=skill,
                    match_type=MatchType.EXACT,
                    confidence=MatchConfidence.HIGH,
                    score=1.0,
                    relevance=0.95,
                    explanation=f"技能 '{skill}' 直接出现在需求中",
                ))
            
            # 检查同义词
            if skill.lower() in self._skill_synonyms:
                for synonym in self._skill_synonyms[skill.lower()]:
                    if synonym.lower() in requirement_lower:
                        matches.append(SkillMatch(
                            skill_name=skill,
                            match_type=MatchType.EXACT,
                            confidence=MatchConfidence.HIGH,
                            score=0.9,
                            relevance=0.9,
                            explanation=f"技能 '{skill}' 的同义词 '{synonym}' 出现在需求中",
                        ))
        
        return matches
    
    def _semantic_match(self, requirement: str, available_skills: List[str]) -> List[SkillMatch]:
        """语义匹配"""
        matches = []
        
        requirement_lower = requirement.lower()
        
        # 基于需求关键词映射
        for keyword, skills in self._requirement_mapping.items():
            if keyword.lower() in requirement_lower:
                for skill in skills:
                    if skill in available_skills:
                        matches.append(SkillMatch(
                            skill_name=skill,
                            match_type=MatchType.SEMANTIC,
                            confidence=MatchConfidence.MEDIUM,
                            score=0.7,
                            relevance=0.8,
                            explanation=f"需求包含关键词 '{keyword}'，推荐技能 '{skill}'",
                        ))
        
        return matches
    
    def _contextual_match(self, requirement: str, available_skills: List[str]) -> List[SkillMatch]:
        """上下文匹配"""
        matches = []
        
        # 基于技能关系图谱
        for skill in available_skills:
            if skill.lower() in self._skill_relations:
                related_skills = self._skill_relations[skill.lower()]
                
                for related in related_skills:
                    if related.lower() in requirement.lower():
                        matches.append(SkillMatch(
                            skill_name=skill,
                            match_type=MatchType.CONTEXTUAL,
                            confidence=MatchConfidence.LOW,
                            score=0.5,
                            relevance=0.6,
                            explanation=f"技能 '{skill}' 与需求中的 '{related}' 相关",
                        ))
        
        return matches
    
    def _deduplicate_matches(self, matches: List[SkillMatch]) -> List[SkillMatch]:
        """去重匹配结果"""
        seen = {}
        
        for match in matches:
            key = match.skill_name.lower()
            if key not in seen or match.score > seen[key].score:
                seen[key] = match
        
        return list(seen.values())
    
    def recommend(self, context: str, available_skills: List[str], count: int = 5) -> List[SkillRecommendation]:
        """
        推荐技能
        
        Args:
            context: 上下文描述
            available_skills: 可用技能列表
            count: 推荐数量
            
        Returns:
            推荐列表
        """
        recommendations = []
        
        # 获取匹配结果
        matches = self.match(context, available_skills)
        
        for match in matches[:count]:
            recommendations.append(SkillRecommendation(
                skill_name=match.skill_name,
                category=self._get_skill_category(match.skill_name),
                relevance_score=match.relevance,
                reason=match.explanation,
                suggested_use=self._get_suggested_use(match.skill_name, context),
            ))
        
        return recommendations
    
    def analyze_gaps(self, required_skills: List[Tuple[str, str]], current_skills: List[Tuple[str, str]]) -> List[SkillGap]:
        """
        分析技能差距
        
        Args:
            required_skills: 所需技能列表 (技能名, 级别)
            current_skills: 当前技能列表 (技能名, 级别)
            
        Returns:
            差距分析结果
        """
        gaps = []
        
        level_order = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        
        for skill_name, required_level in required_skills:
            # 查找当前级别
            current_level = next((cl for sn, cl in current_skills if sn.lower() == skill_name.lower()), "none")
            
            # 计算差距
            current_val = level_order.get(current_level.lower(), 0)
            required_val = level_order.get(required_level.lower(), 0)
            
            if current_val < required_val:
                gap_score = (required_val - current_val) / 4.0
                
                gaps.append(SkillGap(
                    required_skill=skill_name,
                    current_level=current_level,
                    required_level=required_level,
                    gap_score=gap_score,
                    suggested_actions=self._generate_gap_actions(skill_name, current_level, required_level),
                ))
        
        # 按差距分数排序
        gaps.sort(key=lambda g: g.gap_score, reverse=True)
        
        return gaps
    
    def _generate_gap_actions(self, skill_name: str, current_level: str, required_level: str) -> List[str]:
        """生成差距弥补建议"""
        actions = []
        
        level_order = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        current_val = level_order.get(current_level.lower(), 0)
        required_val = level_order.get(required_level.lower(), 0)
        
        if current_val == 0:
            actions.append(f"开始学习 {skill_name} 基础知识")
            actions.append(f"完成 {skill_name} 入门教程")
        elif current_val == 1:
            actions.append(f"深入学习 {skill_name} 核心概念")
            actions.append(f"完成 {skill_name} 实战项目")
        elif current_val == 2:
            actions.append(f"学习 {skill_name} 高级特性")
            actions.append(f"参与 {skill_name} 开源项目")
        elif current_val == 3:
            actions.append(f"深入研究 {skill_name} 源码")
            actions.append(f"分享 {skill_name} 技术经验")
        
        # 添加通用建议
        if required_val - current_val >= 2:
            actions.append(f"制定 {skill_name} 学习计划")
            actions.append(f"寻找 {skill_name} 导师指导")
        
        return actions[:3]
    
    def plan_skill_path(self, target_skill: str, current_level: str = "beginner") -> List[str]:
        """
        规划技能获取路径
        
        Args:
            target_skill: 目标技能
            current_level: 当前级别
            
        Returns:
            学习路径步骤
        """
        paths = {
            "python": [
                "学习 Python 基础语法",
                "掌握 Python 数据结构",
                "学习面向对象编程",
                "掌握异步编程 asyncio",
                "参与实际项目开发",
            ],
            "pyqt": [
                "学习 Qt 框架基础",
                "掌握 PyQt6 控件使用",
                "学习信号槽机制",
                "开发完整桌面应用",
                "优化 UI 性能",
            ],
            "llm": [
                "学习大语言模型原理",
                "掌握 prompt 工程",
                "学习 API 调用",
                "实践 RAG 技术",
                "探索高级应用场景",
            ],
            "rag": [
                "理解 RAG 原理",
                "学习向量数据库",
                "掌握嵌入技术",
                "实践检索优化",
                "构建完整 RAG 系统",
            ],
            "api": [
                "学习 RESTful 设计",
                "掌握 FastAPI 框架",
                "学习认证授权",
                "实践 API 测试",
                "优化 API 性能",
            ],
        }
        
        # 根据当前级别调整路径起点
        level_order = {"beginner": 0, "intermediate": 2, "advanced": 3, "expert": 4}
        start_idx = level_order.get(current_level.lower(), 0)
        
        return paths.get(target_skill.lower(), [f"学习 {target_skill}"])[start_idx:]
    
    def _get_skill_category(self, skill_name: str) -> str:
        """获取技能分类"""
        categories = {
            "python": "编程语言",
            "javascript": "编程语言",
            "typescript": "编程语言",
            "pyqt": "框架",
            "react": "框架",
            "fastapi": "框架",
            "llm": "AI",
            "rag": "AI",
            "asyncio": "库",
            "docker": "工具",
            "api": "领域",
        }
        return categories.get(skill_name.lower(), "其他")
    
    def _get_suggested_use(self, skill_name: str, context: str) -> str:
        """获取建议用途"""
        uses = {
            "python": "用于编写后端逻辑、数据处理、自动化脚本",
            "pyqt": "用于构建桌面 GUI 应用程序",
            "llm": "用于实现 AI 对话、内容生成、智能助手",
            "rag": "用于实现知识库检索增强生成",
            "api": "用于构建 RESTful API 服务",
            "docker": "用于容器化部署和环境管理",
            "asyncio": "用于编写高性能异步代码",
        }
        return uses.get(skill_name.lower(), "")


# 便捷函数
def create_skill_matcher() -> SkillMatcher:
    """创建技能匹配引擎"""
    return SkillMatcher()


__all__ = [
    "MatchType",
    "MatchConfidence",
    "SkillMatch",
    "SkillGap",
    "SkillRecommendation",
    "SkillMatcher",
    "create_skill_matcher",
]
