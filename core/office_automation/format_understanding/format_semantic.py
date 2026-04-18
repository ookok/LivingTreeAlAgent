"""
🧠 格式语义理解模型 - Format Semantic Model

专门理解格式的语义含义的模型：

核心能力：
1. 格式模式识别 - 识别常见格式模式
2. 业务语义映射 - 映射到业务含义
3. 设计意图推断 - 推断格式设计意图
4. 合规性检查 - 检查格式合规性

三大维度：
- 视觉格式语义: 字体/颜色/间距传达的重要性
- 结构格式语义: 标题层级/列表传达的逻辑关系
- 业务格式语义: 合同条款/财务表格传达的法律效力
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple, Set

logger = logging.getLogger(__name__)


# ===== 语义类型 =====

class FormatPatternType(Enum):
    """格式模式类型"""
    # 视觉模式
    EMPHASIS = "emphasis"             # 强调模式
    HEADING_HIERARCHY = "heading_hierarchy"  # 标题层级
    LIST_STRUCTURE = "list_structure"  # 列表结构
    QUOTE_BLOCK = "quote_block"       # 引用块
    CODE_BLOCK = "code_block"         # 代码块
    CAPTION = "caption"               # 标题/说明

    # 表格模式
    DATA_TABLE = "data_table"         # 数据表格
    LAYOUT_TABLE = "layout_table"     # 布局表格
    FORM_TABLE = "form_table"         # 表单表格
    GRID_TABLE = "grid_table"         # 网格表格

    # 页面模式
    TITLE_PAGE = "title_page"         # 标题页
    TOC_PAGE = "toc_page"            # 目录页
    SECTION_BREAK = "section_break"   # 分节
    COLUMN_BREAK = "column_break"     # 分栏

    # 业务模式
    CLAUSE = "clause"                 # 合同条款
    SCHEDULE = "schedule"             # 日程/进度
    SIGNATURE = "signature"           # 签名区
    FOOTER_NOTICE = "footer_notice"   # 页脚通知


class BusinessDomain(Enum):
    """业务领域"""
    GENERAL = "general"           # 通用
    LEGAL = "legal"              # 法律/合同
    FINANCIAL = "financial"       # 财务/会计
    TECHNICAL = "technical"       # 技术文档
    ACADEMIC = "academic"         # 学术论文
    GOVERNMENT = "government"      # 政务公文
    COMMERCIAL = "commercial"      # 商业文档
    HR = "hr"                    # 人力资源


@dataclass
class FormatPattern:
    """格式模式"""
    pattern_id: str
    pattern_type: FormatPatternType
    confidence: float = 0.0       # 置信度 0-1
    elements: List[str] = field(default_factory=list)  # 涉及的节点ID
    properties: Dict = field(default_factory=dict)  # 模式特有的属性

    # 语义标签
    semantic_tags: List[str] = field(default_factory=list)
    business_domain: BusinessDomain = BusinessDomain.GENERAL

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "type": self.pattern_type.value,
            "confidence": round(self.confidence, 2),
            "elements": self.elements,
            "tags": self.semantic_tags,
            "domain": self.business_domain.value,
        }


@dataclass
class BusinessSemantic:
    """业务语义"""
    domain: BusinessDomain = BusinessDomain.GENERAL

    # 合同语义
    clause_type: str = ""          # 条款类型 (definition/obligation/condition/...)
    legal_effect: str = ""        # 法律效力 (binding/non-binding/conditional)
    priority: int = 0             # 优先级

    # 财务语义
    accounting_type: str = ""      # 会计类型 (asset/liability/equity/revenue/expense)
    currency: str = "CNY"
    precision: int = 2            # 小数精度

    # 技术语义
    code_language: str = ""       # 编程语言
    api_reference: bool = False   # 是否API参考
    version_info: bool = False    # 是否版本信息

    def to_dict(self) -> dict:
        return {
            "domain": self.domain.value,
            "clause_type": self.clause_type,
            "legal_effect": self.legal_effect,
            "accounting_type": self.accounting_type,
            "currency": self.currency,
            "precision": self.precision,
            "code_language": self.code_language,
        }


@dataclass
class DesignIntent:
    """设计意图"""
    # 整体意图
    overall_intent: str = ""       # 整体设计意图
    target_audience: str = ""     # 目标读者
    communication_style: str = ""  # 沟通风格 (formal/casual/technical)

    # 视觉意图
    visual_hierarchy: List[str] = field(default_factory=list)  # 视觉层次
    color_usage: str = ""         # 颜色使用策略
    spacing_strategy: str = ""    # 间距策略

    # 结构意图
    logical_structure: str = ""   # 逻辑结构类型
    navigation_pattern: str = ""   # 导航模式
    content_density: str = ""     # 内容密度 (dense/sparse/balanced)

    def to_dict(self) -> dict:
        return {
            "overall_intent": self.overall_intent,
            "target_audience": self.target_audience,
            "communication_style": self.communication_style,
            "visual_hierarchy": self.visual_hierarchy,
            "content_density": self.content_density,
        }


@dataclass
class FormatIntent:
    """格式意图 - 单个格式元素的设计意图"""
    element_id: str

    # 这个格式想传达什么
    intended_meaning: str = ""    # 预期含义
    importance_signal: int = 0    # 重要性信号 0-5
    relationship_to_context: str = ""  # 与上下文的关系

    # 应该如何被处理
    should_preserve: bool = True  # 是否应该保留
    can_merge: bool = False       # 是否可以合并
    requires_special_rendering: bool = False  # 是否需要特殊渲染

    def to_dict(self) -> dict:
        return {
            "element_id": self.element_id,
            "meaning": self.intended_meaning,
            "importance": self.importance_signal,
            "preserve": self.should_preserve,
            "mergeable": self.can_merge,
        }


class FormatSemanticModel:
    """
    格式语义理解模型

    输入: 格式上下文 (格式图谱 + 视觉/结构/语义格式)
    输出: 格式的完整语义理解
    """

    # 标题关键词
    HEADING_KEYWORDS = {
        1: ["概述", "前言", "总则", "大纲", "introduction", "overview"],
        2: ["章节", "部分", "section", "chapter"],
        3: ["小节", "要点", "subsection"],
    }

    # 合同条款关键词
    CLAUSE_KEYWORDS = {
        "definition": ["定义", "术语", "definition", "interpretation"],
        "obligation": ["应当", "必须", "不得", "义务", "obligation", "shall"],
        "condition": ["如果", "若", "条件", "condition", "if", "whereas"],
        "payment": ["支付", "付款", "金额", "payment", "price", "consideration"],
        "liability": ["责任", "赔偿", "liability", "indemnify", "warranty"],
        "termination": ["终止", "解除", "结束", "termination", "breach"],
        "confidentiality": ["保密", "机密", "confidential", "proprietary"],
    }

    # 代码块标识
    CODE_INDICATORS = [
        r"^def\s+\w+\(", r"^class\s+\w+:",
        r"^import\s+\w+", r"^from\s+\w+\s+import",
        r"^\s*//", r"^\s*#", r"^\s*/\*",
        r"```\w+", r"<script>", r"<?php",
    ]

    def __init__(self):
        self.patterns: List[FormatPattern] = []
        self.business_semantics: Dict[str, BusinessSemantic] = {}
        self.design_intent = DesignIntent()

    def analyze(self, format_graph, visual_formats: List, structural_formats: List,
                semantic_formats: List) -> Dict:
        """
        完整格式语义分析

        Args:
            format_graph: 格式图谱
            visual_formats: 视觉格式列表
            structural_formats: 结构格式列表
            semantic_formats: 语义格式列表

        Returns:
            语义分析结果
        """
        results = {
            "patterns": [],
            "business_meanings": {},
            "design_intent": {},
            "compliance_status": {},
        }

        # 1. 格式模式识别
        patterns = self._recognize_patterns(
            format_graph, visual_formats, structural_formats
        )
        results["patterns"] = [p.to_dict() for p in patterns]

        # 2. 业务语义映射
        business = self._map_business_semantics(
            patterns, semantic_formats
        )
        results["business_meanings"] = {k: v.to_dict() for k, v in business.items()}

        # 3. 设计意图推断
        intent = self._infer_design_intent(
            patterns, visual_formats, structural_formats
        )
        results["design_intent"] = intent.to_dict()

        # 4. 合规性检查
        compliance = self._check_compliance(
            patterns, business, intent
        )
        results["compliance_status"] = compliance

        return results

    def _recognize_patterns(self, graph, visual_formats: List,
                           structural_formats: List) -> List[FormatPattern]:
        """识别格式模式"""
        patterns = []

        # 1. 标题层级模式
        heading_pattern = self._detect_heading_hierarchy(structural_formats)
        if heading_pattern:
            patterns.append(heading_pattern)

        # 2. 列表结构模式
        list_pattern = self._detect_list_structure(structural_formats)
        if list_pattern:
            patterns.append(list_pattern)

        # 3. 引用块模式
        quote_pattern = self._detect_quote_block(visual_formats, structural_formats)
        if quote_pattern:
            patterns.append(quote_pattern)

        # 4. 代码块模式
        code_pattern = self._detect_code_block(visual_formats, structural_formats)
        if code_pattern:
            patterns.append(code_pattern)

        # 5. 表格模式
        table_pattern = self._detect_table_pattern(graph)
        if table_pattern:
            patterns.append(table_pattern)

        return patterns

    def _detect_heading_hierarchy(self, structural_formats: List) -> Optional[FormatPattern]:
        """检测标题层级模式"""
        headings = [(i, s) for i, s in enumerate(structural_formats)
                   if s.heading_level > 0]

        if len(headings) < 2:
            return None

        # 检查层级连续性
        levels = [h[1].heading_level for h in headings]
        is_hierarchical = all(levels[i] <= levels[i+1] + 1
                              for i in range(len(levels)-1))

        if is_hierarchical:
            return FormatPattern(
                pattern_id="heading_hierarchy_1",
                pattern_type=FormatPatternType.HEADING_HIERARCHY,
                confidence=0.9,
                elements=[f"h_{h[0]}" for h in headings],
                semantic_tags=["structure", "navigation", "outline"],
            )

        return None

    def _detect_list_structure(self, structural_formats: List) -> Optional[FormatPattern]:
        """检测列表结构模式"""
        list_items = [s for s in structural_formats
                     if s.list_info and s.list_info.get("num_id")]

        if len(list_items) >= 2:
            # 检查层级
            levels = [li.list_info.get("level", 0) for li in list_items]
            has_nested = len(set(levels)) > 1

            return FormatPattern(
                pattern_id=f"list_{list_items[0].list_info.get('num_id', 'default')}",
                pattern_type=FormatPatternType.LIST_STRUCTURE,
                confidence=0.85 if has_nested else 0.7,
                elements=[li.element_id for li in list_items],
                semantic_tags=["enumeration", "sequence"],
            )

        return None

    def _detect_quote_block(self, visual_formats: List,
                           structural_formats: List) -> Optional[FormatPattern]:
        """检测引用块模式"""
        quotes = []

        for i, (v, s) in enumerate(zip(visual_formats, structural_formats)):
            # 引用特征: 斜体 或 缩进 + 边框
            is_italic = getattr(v, 'font_italic', False)
            has_indent = getattr(v, 'indent_left', 0) > 20  # > 20pt 缩进

            if is_italic or has_indent:
                quotes.append(i)

        if len(quotes) >= 2:
            return FormatPattern(
                pattern_id="quote_block_1",
                pattern_type=FormatPatternType.QUOTE_BLOCK,
                confidence=0.75,
                elements=[f"q_{i}" for i in quotes],
                semantic_tags=["quotation", "reference"],
            )

        return None

    def _detect_code_block(self, visual_formats: List,
                          structural_formats: List) -> Optional[FormatPattern]:
        """检测代码块模式"""
        code_blocks = []

        for i, s in enumerate(structural_formats):
            if s.text_content:
                # 检查代码特征
                for pattern in self.CODE_INDICATORS:
                    if re.search(pattern, s.text_content, re.MULTILINE):
                        code_blocks.append(i)
                        break

        if code_blocks:
            return FormatPattern(
                pattern_id=f"code_block_{len(code_blocks)}",
                pattern_type=FormatPatternType.CODE_BLOCK,
                confidence=0.8,
                elements=[f"code_{i}" for i in code_blocks],
                semantic_tags=["code", "technical"],
                business_domain=BusinessDomain.TECHNICAL,
            )

        return None

    def _detect_table_pattern(self, graph) -> Optional[FormatPattern]:
        """检测表格模式"""
        table_nodes = graph.get_nodes_by_type(NodeType.TABLE)
        if not table_nodes:
            return None

        # 分析表格内容特征
        for table in table_nodes:
            cells = graph.get_children(table.node_id)
            if len(cells) >= 4:  # 至少2x2
                # 检测是否是数据表格 (有表头风格)
                has_header = any("header" in c.lower() for c in cells)

                pattern_type = FormatPatternType.DATA_TABLE if has_header else FormatPatternType.GRID_TABLE

                return FormatPattern(
                    pattern_id=table.node_id,
                    pattern_type=pattern_type,
                    confidence=0.85 if has_header else 0.7,
                    elements=[table.node_id],
                    semantic_tags=["table", "data"],
                )

        return None

    def _map_business_semantics(self, patterns: List[FormatPattern],
                                 semantic_formats: List) -> Dict[str, BusinessSemantic]:
        """映射业务语义"""
        business_map = {}

        for pattern in patterns:
            if pattern.pattern_type == FormatPatternType.CLAUSE:
                # 合同条款语义
                for sem_format in semantic_formats:
                    if sem_format.text_content:
                        business = self._infer_clause_type(sem_format.text_content)
                        business_map[sem_format.element_id] = business

            elif pattern.pattern_type == FormatPatternType.CODE_BLOCK:
                # 代码语义
                for sem_format in semantic_formats:
                    business = BusinessSemantic(
                        domain=BusinessDomain.TECHNICAL,
                        code_language=self._detect_code_language(sem_format.text_content or ""),
                    )
                    business_map[sem_format.element_id] = business

        return business_map

    def _infer_clause_type(self, text: str) -> BusinessSemantic:
        """推断条款类型"""
        business = BusinessSemantic(domain=BusinessDomain.LEGAL)

        text_lower = text.lower()
        for clause_type, keywords in self.CLAUSE_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                business.clause_type = clause_type
                break

        # 判断法律效力
        if any(w in text for w in ["应当", "必须", "shall", "must"]):
            business.legal_effect = "binding"
        elif any(w in text for w in ["可以", "may", "might"]):
            business.legal_effect = "permissive"
        elif any(w in text for w in ["如果", "若", "if", "whereas"]):
            business.legal_effect = "conditional"

        return business

    def _detect_code_language(self, text: str) -> str:
        """检测编程语言"""
        language_signatures = {
            "python": [r"^def\s+\w+\(", r"^import\s+\w+", r"^from\s+\w+\s+import"],
            "javascript": [r"^const\s+\w+", r"^let\s+\w+", r"^function\s+\w+\("],
            "java": [r"^public\s+class", r"^private\s+\w+", r"System\.out\.println"],
            "c": [r"#include\s*<", r"^int\s+main\(", r"^void\s+\w+\("],
            "sql": [r"^SELECT\s+", r"^FROM\s+", r"^WHERE\s+", r"^INSERT\s+INTO"],
            "html": [r"<html", r"<div", r"<span", r"</\w+>"],
            "css": [r"\{\s*[\w-]+\s*:", r"^\\.", r"@media"],
        }

        for lang, patterns in language_signatures.items():
            for pattern in patterns:
                if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                    return lang

        return "unknown"

    def _infer_design_intent(self, patterns: List[FormatPattern],
                             visual_formats: List,
                             structural_formats: List) -> DesignIntent:
        """推断设计意图"""
        intent = DesignIntent()

        # 分析目标读者
        for pattern in patterns:
            if pattern.business_domain == BusinessDomain.ACADEMIC:
                intent.target_audience = "academic"
                intent.communication_style = "formal"
            elif pattern.business_domain == BusinessDomain.TECHNICAL:
                intent.target_audience = "technical"
                intent.communication_style = "technical"
            elif pattern.business_domain == BusinessDomain.LEGAL:
                intent.target_audience = "legal"
                intent.communication_style = "formal"

        # 分析视觉层次
        heading_levels = [s.heading_level for s in structural_formats if s.heading_level > 0]
        if heading_levels:
            max_level = max(heading_levels)
            intent.visual_hierarchy = [f"h{i}" for i in range(1, max_level + 1)]

        # 分析内容密度
        total_chars = sum(len(s.text_content or "") for s in structural_formats)
        total_elements = len(structural_formats)
        avg_density = total_chars / max(total_elements, 1)

        if avg_density > 200:
            intent.content_density = "dense"
        elif avg_density < 50:
            intent.content_density = "sparse"
        else:
            intent.content_density = "balanced"

        # 整体意图
        if len(heading_levels) >= 3:
            intent.overall_intent = "comprehensive_documentation"
        elif any(p.pattern_type == FormatPatternType.LIST_STRUCTURE for p in patterns):
            intent.overall_intent = "step_by_step_guide"
        else:
            intent.overall_intent = "general_content"

        return intent

    def _check_compliance(self, patterns: List[FormatPattern],
                          business: Dict[str, BusinessSemantic],
                          intent: DesignIntent) -> Dict:
        """检查合规性"""
        compliance = {
            "issues": [],
            "warnings": [],
            "passed": [],
        }

        # 检查标题层级完整性
        heading_patterns = [p for p in patterns
                          if p.pattern_type == FormatPatternType.HEADING_HIERARCHY]
        if heading_patterns:
            hp = heading_patterns[0]
            if hp.confidence < 0.8:
                compliance["warnings"].append({
                    "type": "heading_inconsistency",
                    "message": "标题层级可能不连续",
                })

        # 检查法律文档格式
        if intent.target_audience == "legal":
            # 检查是否包含必要条款
            has_definitions = any(b.clause_type == "definition" for b in business.values())
            has_liability = any(b.clause_type == "liability" for b in business.values())

            if not has_definitions:
                compliance["warnings"].append({
                    "type": "missing_clause",
                    "message": "法律文档缺少定义条款",
                })

        return compliance

    def analyze_single_element(self, element_id: str,
                               visual, structural, semantic) -> FormatIntent:
        """
        分析单个元素的格式意图

        用于格式保持的内容生成
        """
        intent = FormatIntent(element_id=element_id)

        # 推断重要性信号
        importance = 0

        # 视觉信号
        if semantic.font_bold:
            importance += 1
        if semantic.font_size and semantic.font_size > 14:
            importance += 1
        if semantic.font_color and semantic.font_color.upper() not in ["000000", "00000"]:
            importance += 1

        # 结构信号
        if structural.heading_level > 0:
            importance += structural.heading_level
        if structural.list_info:
            importance += 1

        intent.importance_signal = min(importance, 5)

        # 推断预期含义
        if structural.heading_level > 0:
            intent.intended_meaning = "section_header"
            intent.should_preserve = True
        elif semantic.semantic_role == "code":
            intent.intended_meaning = "technical_content"
            intent.should_preserve = True
        elif structural.list_info:
            intent.intended_meaning = "enumerated_item"
            intent.can_merge = True
        else:
            intent.intended_meaning = "body_text"
            intent.can_merge = True

        return intent
