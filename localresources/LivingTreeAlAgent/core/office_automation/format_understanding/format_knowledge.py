"""
📚 格式知识库 - Format Knowledge Base

企业级格式知识的存储和管理：

1. 格式规范库
   - 企业样式标准
   - 文档类型规范
   - 品牌视觉规范
   - 行业格式标准

2. 格式模式库
   - 成功格式模式
   - 常见格式问题
   - 格式最佳实践
   - 格式反模式

3. 格式案例库
   - 优秀文档案例
   - 问题文档案例
   - 格式演变案例

4. 个性化格式库
   - 用户偏好格式
   - 项目专用格式
   - 部门特色格式
"""

import os
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ===== 知识库类型 =====

class KnowledgeType(Enum):
    """知识类型"""
    STANDARD = "standard"           # 标准
    PATTERN = "pattern"            # 模式
    CASE = "case"                 # 案例
    PREFERENCE = "preference"      # 偏好


class StandardType(Enum):
    """标准类型"""
    CORPORATE = "corporate"        # 企业标准
    BRAND = "brand"               # 品牌标准
    INDUSTRY = "industry"          # 行业标准
    NATIONAL = "national"          # 国家标准
    INTERNATIONAL = "international"  # 国际标准


@dataclass
class FormatStandard:
    """格式标准"""
    standard_id: str
    name: str
    standard_type: StandardType

    # 适用范围
    document_types: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)

    # 标准内容
    font_rules: Dict = field(default_factory=dict)
    color_rules: Dict = field(default_factory=dict)
    spacing_rules: Dict = field(default_factory=dict)
    structure_rules: Dict = field(default_factory=dict)

    # 元数据
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.standard_id,
            "name": self.name,
            "type": self.standard_type.value,
            "document_types": self.document_types,
            "industries": self.industries,
            "rules": {
                "font": self.font_rules,
                "color": self.color_rules,
                "spacing": self.spacing_rules,
                "structure": self.structure_rules,
            },
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class FormatPattern:
    """格式模式"""
    pattern_id: str
    name: str
    description: str

    # 模式特征
    visual_features: Dict = field(default_factory=dict)
    structural_features: Dict = field(default_factory=list)
    semantic_features: List[str] = field(default_factory=list)

    # 使用场景
    use_cases: List[str] = field(default_factory=list)
    success_indicators: List[str] = field(default_factory=list)

    # 反模式
    anti_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "features": {
                "visual": self.visual_features,
                "structural": self.structural_features,
                "semantic": self.semantic_features,
            },
            "use_cases": self.use_cases,
            "success": self.success_indicators,
            "anti_patterns": self.anti_patterns,
        }


@dataclass
class FormatCase:
    """格式案例"""
    case_id: str
    name: str
    case_type: str  # "good"/"bad"/"evolution"

    # 案例内容
    document_type: str = ""
    description: str = ""
    elements: List[Dict] = field(default_factory=list)

    # 评估
    evaluation: Dict = field(default_factory=dict)
    lessons: List[str] = field(default_factory=list)

    # 来源
    source: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.case_id,
            "name": self.name,
            "type": self.case_type,
            "document_type": self.document_type,
            "description": self.description,
            "evaluation": self.evaluation,
            "lessons": self.lessons,
        }


@dataclass
class UserPreference:
    """用户格式偏好"""
    user_id: str
    preference_id: str

    # 偏好内容
    preferred_fonts: List[str] = field(default_factory=list)
    preferred_colors: List[str] = field(default_factory=list)
    preferred_spacing: Dict = field(default_factory=dict)
    style_tendencies: List[str] = field(default_factory=list)

    # 使用统计
    usage_count: int = 0
    last_used: str = ""
    satisfaction_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "preference_id": self.preference_id,
            "preferred_fonts": self.preferred_fonts,
            "preferred_colors": self.preferred_colors,
            "spacing": self.preferred_spacing,
            "tendencies": self.style_tendencies,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "satisfaction": round(self.satisfaction_score, 2),
        }


class FormatKnowledgeBase:
    """
    格式知识库

    管理企业格式知识，支持：
    - 标准的存储、查询、匹配
    - 模式的发现、推荐、复用
    - 案例的收集、分类、检索
    - 偏好的学习、适应、推荐
    """

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or os.path.join(
            os.path.expanduser("~"),
            ".hermes",
            "format_knowledge"
        )
        os.makedirs(self.storage_dir, exist_ok=True)

        # 知识存储
        self.standards: Dict[str, FormatStandard] = {}
        self.patterns: Dict[str, FormatPattern] = {}
        self.cases: Dict[str, FormatCase] = {}
        self.preferences: Dict[str, UserPreference] = {}

        # 加载已有知识
        self._load_knowledge()

        # 内置知识
        self._init_builtin_knowledge()

    def _load_knowledge(self):
        """加载已存储的知识"""
        # 加载标准
        standards_file = os.path.join(self.storage_dir, "standards.json")
        if os.path.exists(standards_file):
            try:
                with open(standards_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        std = self._dict_to_standard(item)
                        self.standards[std.standard_id] = std
            except Exception as e:
                logger.warning(f"加载标准失败: {e}")

        # 加载模式
        patterns_file = os.path.join(self.storage_dir, "patterns.json")
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        pat = self._dict_to_pattern(item)
                        self.patterns[pat.pattern_id] = pat
            except Exception as e:
                logger.warning(f"加载模式失败: {e}")

        # 加载偏好
        prefs_dir = os.path.join(self.storage_dir, "preferences")
        if os.path.exists(prefs_dir):
            for fname in os.listdir(prefs_dir):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(prefs_dir, fname), "r", encoding="utf-8") as f:
                            data = json.load(f)
                            pref = self._dict_to_preference(data)
                            self.preferences[pref.preference_id] = pref
                    except Exception as e:
                        logger.warning(f"加载偏好失败: {e}")

    def _save_knowledge(self):
        """保存知识到磁盘"""
        # 保存标准
        standards_file = os.path.join(self.storage_dir, "standards.json")
        with open(standards_file, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.standards.values()], f, ensure_ascii=False, indent=2)

        # 保存模式
        patterns_file = os.path.join(self.storage_dir, "patterns.json")
        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in self.patterns.values()], f, ensure_ascii=False, indent=2)

        # 保存偏好
        prefs_dir = os.path.join(self.storage_dir, "preferences")
        os.makedirs(prefs_dir, exist_ok=True)
        for pref in self.preferences.values():
            pref_file = os.path.join(prefs_dir, f"{pref.preference_id}.json")
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(pref.to_dict(), f, ensure_ascii=False, indent=2)

    def _init_builtin_knowledge(self):
        """初始化内置知识"""
        if not self.standards:
            self._init_corporate_standard()

        if not self.patterns:
            self._init_common_patterns()

    def _init_corporate_standard(self):
        """初始化企业标准"""
        std = FormatStandard(
            standard_id="corporate_standard_v1",
            name="企业通用文档标准",
            standard_type=StandardType.CORPORATE,
            document_types=["report", "contract", "proposal", "memo"],
            industries=["general"],
            font_rules={
                "heading_1": {"family": "Microsoft YaHei", "size": 22, "bold": True},
                "heading_2": {"family": "Microsoft YaHei", "size": 16, "bold": True},
                "heading_3": {"family": "Microsoft YaHei", "size": 14, "bold": True},
                "body": {"family": "SimSun", "size": 12},
                "caption": {"family": "SimSun", "size": 10},
            },
            color_rules={
                "primary": "#1B3A5C",
                "secondary": "#4A7FB5",
                "accent": "#E8A838",
                "text_primary": "#1A1A2E",
                "text_secondary": "#6B7280",
            },
            spacing_rules={
                "page_margin": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
                "paragraph_spacing": {"before": 6, "after": 12},
                "line_spacing": 1.5,
            },
            structure_rules={
                "required_sections": ["title", "date", "author"],
                "optional_sections": ["toc", "appendix", "references"],
                "heading_depth": 3,
            },
            version="1.0",
            created_at=datetime.now().isoformat(),
        )
        self.standards[std.standard_id] = std

    def _init_common_patterns(self):
        """初始化常见模式"""
        patterns = [
            FormatPattern(
                pattern_id="modern_minimal",
                name="现代简约风格",
                description="大量留白，简洁排版，强调内容",
                visual_features={
                    "font": {"family": "Arial", "size": 12},
                    "colors": {"background": "#FFFFFF", "text": "#333333"},
                    "spacing": {"margins": 40, "paragraph_gap": 20},
                },
                structural_features=["clear_headings", "bullet_lists"],
                semantic_features=["professional", "clean", "focused"],
                use_cases=["presentation", "proposal"],
                success_indicators=["高可读性", "专业感"],
                anti_patterns=["过度装饰", "颜色过多"],
            ),
            FormatPattern(
                pattern_id="traditional_corporate",
                name="传统企业风格",
                description="正式、权威、结构清晰",
                visual_features={
                    "font": {"family": "SimSun", "size": 12},
                    "colors": {"primary": "#1B3A5C", "accent": "#E8A838"},
                    "spacing": {"margins": 30, "paragraph_gap": 15},
                },
                structural_features=["numbered_headings", "table_of_contents"],
                semantic_features=["formal", "authoritative", "structured"],
                use_cases=["report", "contract", "policy"],
                success_indicators=["符合规范", "层次分明"],
                anti_patterns=["过于花哨", "结构混乱"],
            ),
            FormatPattern(
                pattern_id="creative_colorful",
                name="创意彩色风格",
                description="大胆用色，动感排版，强调视觉冲击",
                visual_features={
                    "font": {"family": "Microsoft YaHei", "size": 14},
                    "colors": {"primary": "#6C5CE7", "accent": "#FD79A8"},
                    "spacing": {"margins": 25, "paragraph_gap": 18},
                },
                structural_features=["section_breaks", "visual_elements"],
                semantic_features=["creative", "dynamic", "engaging"],
                use_cases=["presentation", "marketing", "creative"],
                success_indicators=["吸引眼球", "印象深刻"],
                anti_patterns=["难以阅读", "喧宾夺主"],
            ),
        ]

        for pat in patterns:
            self.patterns[pat.pattern_id] = pat

    # ===== 查询方法 =====

    def find_matching_standards(self, document_type: str = None,
                                industry: str = None) -> List[FormatStandard]:
        """查找匹配的标准"""
        results = []

        for std in self.standards.values():
            # 匹配文档类型
            if document_type and std.document_types:
                if document_type not in std.document_types:
                    continue

            # 匹配行业
            if industry and std.industries:
                if industry not in std.industries:
                    continue

            results.append(std)

        return results

    def find_similar_patterns(self, features: Dict,
                              limit: int = 5) -> List[FormatPattern]:
        """查找相似模式"""
        scored = []

        for pat in self.patterns.values():
            score = 0.0

            # 视觉特征匹配
            if "visual" in features:
                for key in ["font", "colors", "spacing"]:
                    if key in pat.visual_features and key in features["visual"]:
                        if pat.visual_features[key] == features["visual"][key]:
                            score += 1.0

            # 语义特征匹配
            if "semantic" in features:
                for sem in features["semantic"]:
                    if sem in pat.semantic_features:
                        score += 0.5

            if score > 0:
                scored.append((pat, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in scored[:limit]]

    def get_user_preference(self, user_id: str) -> Optional[UserPreference]:
        """获取用户偏好"""
        return self.preferences.get(user_id)

    def learn_preference(self, user_id: str, format_info: Dict):
        """学习用户偏好"""
        pref_id = f"pref_{user_id}"

        if pref_id in self.preferences:
            pref = self.preferences[pref_id]
            pref.usage_count += 1
        else:
            pref = UserPreference(
                user_id=user_id,
                preference_id=pref_id,
            )
            self.preferences[pref_id] = pref

        # 更新偏好内容
        if "fonts" in format_info:
            for font in format_info["fonts"]:
                if font not in pref.preferred_fonts:
                    pref.preferred_fonts.append(font)

        if "colors" in format_info:
            for color in format_info["colors"]:
                if color not in pref.preferred_colors:
                    pref.preferred_colors.append(color)

        pref.last_used = datetime.now().isoformat()
        self._save_knowledge()

    # ===== 添加/更新知识 =====

    def add_standard(self, standard: FormatStandard):
        """添加标准"""
        self.standards[standard.standard_id] = standard
        self._save_knowledge()

    def add_pattern(self, pattern: FormatPattern):
        """添加模式"""
        self.patterns[pattern.pattern_id] = pattern
        self._save_knowledge()

    def add_case(self, case: FormatCase):
        """添加案例"""
        self.cases[case.case_id] = case

    def record_feedback(self, preference_id: str, rating: float):
        """记录反馈"""
        if preference_id in self.preferences:
            pref = self.preferences[preference_id]
            # 更新满意度
            if pref.satisfaction_score == 0:
                pref.satisfaction_score = rating
            else:
                pref.satisfaction_score = pref.satisfaction_score * 0.8 + rating * 0.2
            self._save_knowledge()

    # ===== 辅助方法 =====

    @staticmethod
    def _dict_to_standard(d: dict) -> FormatStandard:
        """字典转标准"""
        return FormatStandard(
            standard_id=d["id"],
            name=d["name"],
            standard_type=StandardType(d.get("type", "corporate")),
            document_types=d.get("document_types", []),
            industries=d.get("industries", []),
            font_rules=d.get("rules", {}).get("font", {}),
            color_rules=d.get("rules", {}).get("color", {}),
            spacing_rules=d.get("rules", {}).get("spacing", {}),
            structure_rules=d.get("rules", {}).get("structure", {}),
            version=d.get("version", "1.0"),
            created_at=d.get("created_at", ""),
        )

    @staticmethod
    def _dict_to_pattern(d: dict) -> FormatPattern:
        """字典转模式"""
        return FormatPattern(
            pattern_id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            visual_features=d.get("features", {}).get("visual", {}),
            structural_features=d.get("features", {}).get("structural", []),
            semantic_features=d.get("features", {}).get("semantic", []),
            use_cases=d.get("use_cases", []),
            success_indicators=d.get("success", []),
            anti_patterns=d.get("anti_patterns", []),
        )

    @staticmethod
    def _dict_to_preference(d: dict) -> UserPreference:
        """字典转偏好"""
        return UserPreference(
            user_id=d["user_id"],
            preference_id=d["preference_id"],
            preferred_fonts=d.get("preferred_fonts", []),
            preferred_colors=d.get("preferred_colors", []),
            preferred_spacing=d.get("spacing", {}),
            style_tendencies=d.get("tendencies", []),
            usage_count=d.get("usage_count", 0),
            last_used=d.get("last_used", ""),
            satisfaction_score=d.get("satisfaction", 0.0),
        )

    def export_knowledge(self, export_path: str):
        """导出知识库"""
        knowledge = {
            "standards": [s.to_dict() for s in self.standards.values()],
            "patterns": [p.to_dict() for p in self.patterns.values()],
            "cases": [c.to_dict() for c in self.cases.values()],
            "exported_at": datetime.now().isoformat(),
        }

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)
