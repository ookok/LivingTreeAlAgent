"""
知识挖掘引擎

从历史项目中挖掘可复用的知识。
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# ==================== 枚举定义 ====================

class KnowledgeType(Enum):
    """知识类型"""
    BEST_PRACTICE = "best_practice"       # 最佳实践
    COMMON_ISSUE = "common_issue"         # 常见问题
    EXPERT_INSIGHT = "expert_insight"     # 专家见解
    CLIENT_PREFERENCE = "client_preference" # 客户偏好
    REGULATORY_NOTE = "regulatory_note"   # 法规注释
    TEMPLATE_PATTERN = "template_pattern" # 模板模式


class ExtractionMethod(Enum):
    """知识提取方法"""
    MANUAL = "manual"                     # 人工
    AI_EXTRACT = "ai_extract"             # AI提取
    USER_FEEDBACK = "user_feedback"       # 用户反馈
    PATTERN_LEARN = "pattern_learn"       # 模式学习


class TemplateQuality(Enum):
    """模板质量"""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    NEEDS_IMPROVEMENT = "needs_improvement"


# ==================== 数据模型 ====================

@dataclass
class KnowledgeUnit:
    """知识单元"""
    knowledge_id: str
    knowledge_type: KnowledgeType

    # 内容
    title: str
    content: str                           # 核心内容
    summary: str = ""                     # 摘要

    # 来源
    source_type: str = ""                 # project/document/review/manual
    source_id: str = ""
    source_name: str = ""

    # 提取信息
    extraction_method: ExtractionMethod = ExtractionMethod.MANUAL
    extracted_by: str = ""
    extracted_at: datetime = field(default_factory=datetime.now)

    # 应用信息
    usage_count: int = 0                  # 使用次数
    success_count: int = 0                # 成功次数
    last_used_at: Optional[datetime] = None

    # 标签
    tags: List[str] = field(default_factory=list)
    industry: str = ""                    # 适用行业
    project_type: str = ""               # 适用项目类型
    region: str = ""                     # 适用地区

    # 状态
    is_active: bool = True
    is_verified: bool = False             # 是否已验证

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class BestPractice:
    """最佳实践"""
    practice_id: str
    title: str
    description: str

    # 适用范围
    applicable_to: List[str] = field(default_factory=list)  # 适用场景
    industry: List[str] = field(default_factory=list)
    project_types: List[str] = field(default_factory=list)

    # 实践内容
    steps: List[str] = field(default_factory=list)  # 操作步骤
    key_points: List[str] = field(default_factory=list)  # 关键要点
    common_pitfalls: List[str] = field(default_factory=list)  # 常见陷阱

    # 效果
    estimated_time_saving: str = ""       # 预计节省时间
    success_rate: float = 0.0            # 成功率

    # 来源
    source_knowledge_ids: List[str] = field(default_factory=list)
    verified_by: str = ""
    verified_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TemplatePattern:
    """模板模式"""
    pattern_id: str
    name: str
    description: str

    # 适用场景
    document_type: str = ""               # 文档类型
    section_type: str = ""               # 章节类型
    project_type: str = ""              # 项目类型

    # 模式内容
    pattern_text: str = ""               # 模式文本/框架
    variable_fields: List[str] = field(default_factory=list)  # 变量字段
    examples: List[str] = field(default_factory=list)  # 示例

    # 使用统计
    usage_count: int = 0
    avg_completion_time: float = 0.0     # 平均完成时间
    quality_score: TemplateQuality = TemplateQuality.AVERAGE

    # 优化信息
    improvement_suggestions: List[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectSimilarity:
    """项目相似性"""
    project_id_1: str
    project_id_2: str

    # 相似度
    overall_similarity: float = 0.0     # 0-1

    # 维度相似度
    industry_similarity: float = 0.0
    scale_similarity: float = 0.0
    type_similarity: float = 0.0
    region_similarity: float = 0.0

    # 相似特征
    common_features: List[str] = field(default_factory=list)
    differentiators: List[str] = field(default_factory=list)

    # 参考价值
    reference_value: float = 0.0        # 参考价值评分

    calculated_at: datetime = field(default_factory=datetime.now)


# ==================== 知识挖掘引擎 ====================

class KnowledgeMiningEngine:
    """
    知识挖掘引擎

    核心功能：
    1. 从项目中挖掘知识
    2. 提取最佳实践
    3. 识别模板模式
    4. 分析项目相似性
    """

    def __init__(self):
        self._knowledge_units: Dict[str, KnowledgeUnit] = {}
        self._best_practices: Dict[str, BestPractice] = {}
        self._template_patterns: Dict[str, TemplatePattern] = {}
        self._similarities: Dict[str, ProjectSimilarity] = {}

    # ==================== 知识提取 ====================

    async def extract_from_project(
        self,
        project_id: str,
        documents: List[Dict],
        extraction_method: ExtractionMethod = ExtractionMethod.AI_EXTRACT
    ) -> List[KnowledgeUnit]:
        """从项目中提取知识"""
        extracted_knowledge = []

        for doc in documents:
            # 提取文档中的知识
            units = await self._extract_from_document(
                project_id, doc, extraction_method
            )
            extracted_knowledge.extend(units)

        return extracted_knowledge

    async def _extract_from_document(
        self,
        project_id: str,
        document: Dict,
        method: ExtractionMethod
    ) -> List[KnowledgeUnit]:
        """从文档中提取知识"""
        # TODO: 实现实际的AI提取逻辑
        units = []

        # 模拟提取
        if document.get("type") == "eia_report":
            # 提取环评报告中的知识
            unit = KnowledgeUnit(
                knowledge_id=f"KU:{project_id}:{len(self._knowledge_units)}",
                knowledge_type=KnowledgeType.BEST_PRACTICE,
                title="环评报告编制要点",
                content="环境影响报告书应包含...",
                source_type="document",
                source_id=document.get("doc_id", ""),
                extraction_method=method
            )
            units.append(unit)

        return units

    async def extract_from_review(
        self,
        review_id: str,
        reviewer_id: str,
        comments: List[Dict]
    ) -> List[KnowledgeUnit]:
        """从审核评论中提取知识"""
        extracted = []

        for comment in comments:
            if comment.get("type") == "repeated_issue":
                # 重复出现的问题 -> 最佳实践
                unit = KnowledgeUnit(
                    knowledge_id=f"KU:REV:{review_id}:{len(extracted)}",
                    knowledge_type=KnowledgeType.COMMON_ISSUE,
                    title=comment.get("title", "常见问题"),
                    content=comment.get("content", ""),
                    source_type="review",
                    source_id=review_id,
                    extraction_method=ExtractionMethod.USER_FEEDBACK,
                    extracted_by=reviewer_id
                )
                extracted.append(unit)

        return extracted

    # ==================== 最佳实践管理 ====================

    async def create_best_practice(
        self,
        title: str,
        description: str,
        steps: List[str],
        applicable_to: List[str] = None
    ) -> BestPractice:
        """创建最佳实践"""
        practice_id = f"BP:{datetime.now().strftime('%Y%m%d%H%M%S')}"

        practice = BestPractice(
            practice_id=practice_id,
            title=title,
            description=description,
            steps=steps,
            applicable_to=applicable_to or []
        )

        self._best_practices[practice_id] = practice
        return practice

    async def recommend_best_practice(
        self,
        project_type: str,
        industry: str = None,
        region: str = None
    ) -> List[BestPractice]:
        """推荐最佳实践"""
        candidates = list(self._best_practices.values())

        # 过滤适用场景
        relevant = [
            p for p in candidates
            if project_type in p.applicable_to or
               not p.applicable_to or
               any(project_type in t for t in p.project_types if t)
        ]

        # 按成功率排序
        relevant.sort(key=lambda x: x.success_rate, reverse=True)

        return relevant[:5]

    # ==================== 模板优化 ====================

    async def analyze_template_usage(
        self,
        template_id: str,
        usage_data: List[Dict]
    ) -> TemplatePattern:
        """分析模板使用情况"""
        # TODO: 实现模板分析逻辑

        pattern = TemplatePattern(
            pattern_id=f"PAT:{template_id}",
            name="分析后的模板",
            description="基于使用数据的分析结果"
        )

        return pattern

    async def suggest_template_improvement(
        self,
        pattern_id: str
    ) -> List[str]:
        """建议模板改进"""
        pattern = self._template_patterns.get(pattern_id)
        if not pattern:
            return []

        suggestions = []

        # 基于使用统计建议
        if pattern.usage_count > 10:
            if pattern.quality_score == TemplateQuality.NEEDS_IMPROVEMENT:
                suggestions.append("考虑简化模板结构")

            if pattern.avg_completion_time > 3600:  # > 1小时
                suggestions.append("模板可能过于复杂，考虑拆分")

        return suggestions

    # ==================== 项目相似性分析 ====================

    async def calculate_similarity(
        self,
        project_1: Dict,
        project_2: Dict
    ) -> ProjectSimilarity:
        """计算项目相似性"""
        similarity = ProjectSimilarity(
            project_id_1=project_1.get("project_id", ""),
            project_id_2=project_2.get("project_id", "")
        )

        # 行业相似度
        if project_1.get("industry") == project_2.get("industry"):
            similarity.industry_similarity = 1.0
            similarity.common_features.append("相同行业")

        # 规模相似度
        scale_1 = project_1.get("scale", "medium")
        scale_2 = project_2.get("scale", "medium")
        if scale_1 == scale_2:
            similarity.scale_similarity = 1.0

        # 类型相似度
        type_1 = project_1.get("project_type", "")
        type_2 = project_2.get("project_type", "")
        if type_1 == type_2:
            similarity.type_similarity = 1.0
            similarity.common_features.append("相同项目类型")

        # 地区相似度
        if project_1.get("region") == project_2.get("region"):
            similarity.region_similarity = 0.8
            similarity.common_features.append("相同地区")

        # 综合相似度
        similarity.overall_similarity = (
            similarity.industry_similarity * 0.3 +
            similarity.scale_similarity * 0.2 +
            similarity.type_similarity * 0.3 +
            similarity.region_similarity * 0.2
        )

        # 计算参考价值
        similarity.reference_value = similarity.overall_similarity * 0.8

        key = f"{similarity.project_id_1}:{similarity.project_id_2}"
        self._similarities[key] = similarity

        return similarity

    async def find_similar_projects(
        self,
        project_id: str,
        project_data: Dict,
        all_projects: List[Dict],
        top_k: int = 5
    ) -> List[ProjectSimilarity]:
        """查找相似项目"""
        similarities = []

        for other in all_projects:
            if other.get("project_id") == project_id:
                continue

            sim = await self.calculate_similarity(project_data, other)
            similarities.append(sim)

        # 按相似度排序
        similarities.sort(key=lambda x: x.overall_similarity, reverse=True)

        return similarities[:top_k]

    # ==================== 知识查询 ====================

    async def query_knowledge(
        self,
        query: str,
        knowledge_type: KnowledgeType = None,
        project_type: str = None,
        industry: str = None,
        top_k: int = 10
    ) -> List[KnowledgeUnit]:
        """查询知识"""
        candidates = [
            k for k in self._knowledge_units.values()
            if k.is_active
        ]

        # 类型过滤
        if knowledge_type:
            candidates = [
                k for k in candidates
                if k.knowledge_type == knowledge_type
            ]

        # 项目类型过滤
        if project_type:
            candidates = [
                k for k in candidates
                if not k.project_type or k.project_type == project_type
            ]

        # 行业过滤
        if industry:
            candidates = [
                k for k in candidates
                if not k.industry or k.industry == industry
            ]

        # 按使用率排序
        candidates.sort(key=lambda x: x.usage_count, reverse=True)

        return candidates[:top_k]

    async def record_knowledge_usage(
        self,
        knowledge_id: str,
        success: bool = True
    ) -> bool:
        """记录知识使用"""
        unit = self._knowledge_units.get(knowledge_id)
        if not unit:
            return False

        unit.usage_count += 1
        if success:
            unit.success_count += 1

        unit.last_used_at = datetime.now()
        return True


# ==================== 模板优化器 ====================

class TemplateOptimizer:
    """模板优化器"""

    def __init__(self):
        self._templates: Dict[str, Dict] = {}

    async def analyze_template_effectiveness(
        self,
        template_id: str
    ) -> Dict:
        """分析模板有效性"""
        # TODO: 实现模板分析
        return {
            "template_id": template_id,
            "completion_rate": 0.85,
            "avg_time": 3600,
            "quality_score": 4.2,
            "suggestions": [
                "建议增加示例说明",
                "某些字段可设为可选"
            ]
        }

    async def optimize_template(
        self,
        template_id: str,
        optimization_goals: List[str]
    ) -> Dict:
        """优化模板"""
        # TODO: 实现模板优化
        return {
            "template_id": template_id,
            "optimized_sections": ["section_1", "section_3"],
            "estimated_improvement": "20% faster completion"
        }


# ==================== 相似度分析器 ====================

class SimilarityAnalyzer:
    """相似度分析器"""

    @staticmethod
    async def text_similarity(text1: str, text2: str) -> float:
        """文本相似度"""
        # TODO: 实现文本相似度计算
        if text1 == text2:
            return 1.0
        return 0.0

    @staticmethod
    async def feature_similarity(
        features1: Dict,
        features2: Dict
    ) -> float:
        """特征相似度"""
        if not features1 or not features2:
            return 0.0

        common = sum(
            1 for k in features1
            if k in features2 and features1[k] == features2[k]
        )

        total = len(set(list(features1.keys()) + list(features2.keys())))

        return common / total if total > 0 else 0.0


# ==================== 单例模式 ====================

_knowledge_engine: Optional[KnowledgeMiningEngine] = None


def get_knowledge_engine() -> KnowledgeMiningEngine:
    """获取知识挖掘引擎单例"""
    global _knowledge_engine
    if _knowledge_engine is None:
        _knowledge_engine = KnowledgeMiningEngine()
    return _knowledge_engine
