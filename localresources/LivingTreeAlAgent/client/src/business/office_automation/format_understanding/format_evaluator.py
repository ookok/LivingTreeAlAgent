"""
📊 格式质量评估器 - Format Evaluator

评估文档格式质量的多个维度：

1. 可读性评估 (Readability)
   - 字体可读性
   - 对比度适宜性
   - 间距舒适性
   - 视觉流引导

2. 专业性评估 (Professionalism)
   - 企业标准符合度
   - 行业最佳实践
   - 视觉协调性
   - 细节精致度

3. 可访问性评估 (Accessibility)
   - 屏幕阅读器友好
   - 色盲友好
   - 缩放友好
   - 导航友好

输出:
- 综合评分 (0-100)
- 各维度评分
- 具体改进建议
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ===== 评估维度 =====

class QualityDimension(Enum):
    """质量维度"""
    READABILITY = "readability"
    PROFESSIONALISM = "professionalism"
    ACCESSIBILITY = "accessibility"
    CONSISTENCY = "consistency"
    NAVIGATION = "navigation"


@dataclass
class ReadabilityMetrics:
    """可读性指标"""
    # 字体评估
    font_score: float = 50.0        # 0-100
    font_size_appropriate: bool = True
    font_family_appropriate: bool = True

    # 对比度评估
    contrast_ratio: float = 4.5    # WCAG 标准: 4.5:1
    contrast_score: float = 50.0
    low_contrast_elements: List[str] = field(default_factory=list)

    # 间距评估
    line_spacing_score: float = 50.0
    paragraph_spacing_score: float = 50.0
    margins_adequate: bool = True

    # 视觉流
    visual_flow_score: float = 50.0
    hierarchy_clear: bool = True

    # 综合评分
    overall_score: float = 50.0

    def to_dict(self) -> dict:
        return {
            "font": {
                "score": round(self.font_score, 1),
                "size_appropriate": self.font_size_appropriate,
                "family_appropriate": self.font_family_appropriate,
            },
            "contrast": {
                "ratio": round(self.contrast_ratio, 2),
                "score": round(self.contrast_score, 1),
                "low_contrast_elements": self.low_contrast_elements,
            },
            "spacing": {
                "line_score": round(self.line_spacing_score, 1),
                "paragraph_score": round(self.paragraph_spacing_score, 1),
                "margins_adequate": self.margins_adequate,
            },
            "visual_flow": {
                "score": round(self.visual_flow_score, 1),
                "hierarchy_clear": self.hierarchy_clear,
            },
            "overall": round(self.overall_score, 1),
        }


@dataclass
class ProfessionalMetrics:
    """专业性指标"""
    # 企业标准
    brand_compliance_score: float = 50.0
    brand_color_used: bool = True
    brand_font_used: bool = True

    # 行业标准
    industry_standard_score: float = 50.0
    standard_elements_present: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)

    # 视觉协调
    color_harmony_score: float = 50.0
    style_consistency_score: float = 50.0
    professional_appearance_score: float = 50.0

    # 细节
    detail_score: float = 50.0
    spelling_errors: List[str] = field(default_factory=list)
    formatting_errors: List[str] = field(default_factory=list)

    # 综合评分
    overall_score: float = 50.0

    def to_dict(self) -> dict:
        return {
            "brand_compliance": {
                "score": round(self.brand_compliance_score, 1),
                "color_used": self.brand_color_used,
                "font_used": self.brand_font_used,
            },
            "industry_standard": {
                "score": round(self.industry_standard_score, 1),
                "present": self.standard_elements_present,
                "missing": self.missing_elements,
            },
            "visual_harmony": {
                "color_score": round(self.color_harmony_score, 1),
                "style_score": round(self.style_consistency_score, 1),
                "appearance_score": round(self.professional_appearance_score, 1),
            },
            "details": {
                "score": round(self.detail_score, 1),
                "spelling_errors": self.spelling_errors,
                "formatting_errors": self.formatting_errors,
            },
            "overall": round(self.overall_score, 1),
        }


@dataclass
class AccessibilityMetrics:
    """可访问性指标"""
    # 屏幕阅读器
    screen_reader_score: float = 50.0
    alt_text_present: bool = True
    headings_proper: bool = True
    list_structure_correct: bool = True

    # 色盲友好
    colorblind_score: float = 50.0
    sufficient_contrast: bool = True
    color_not_sole_indicator: bool = True

    # 缩放友好
    zoom_score: float = 50.0
    relative_units_used: bool = True
    fixed_sizes_appropriate: bool = True

    # 导航友好
    navigation_score: float = 50.0
    toc_present: bool = False
    page_numbers_present: bool = True
    clear_structure: bool = True

    # 综合评分
    overall_score: float = 50.0

    def to_dict(self) -> dict:
        return {
            "screen_reader": {
                "score": round(self.screen_reader_score, 1),
                "alt_text": self.alt_text_present,
                "headings": self.headings_proper,
                "list_structure": self.list_structure_correct,
            },
            "colorblind": {
                "score": round(self.colorblind_score, 1),
                "contrast_ok": self.sufficient_contrast,
                "not_color_only": self.color_not_sole_indicator,
            },
            "zoom": {
                "score": round(self.zoom_score, 1),
                "relative_units": self.relative_units_used,
            },
            "navigation": {
                "score": round(self.navigation_score, 1),
                "toc": self.toc_present,
                "page_numbers": self.page_numbers_present,
            },
            "overall": round(self.overall_score, 1),
        }


@dataclass
class QualityMetrics:
    """综合质量指标"""
    readability: ReadabilityMetrics = field(default_factory=ReadabilityMetrics)
    professionalism: ProfessionalMetrics = field(default_factory=ProfessionalMetrics)
    accessibility: AccessibilityMetrics = field(default_factory=AccessibilityMetrics)

    # 一致性评估
    consistency_score: float = 50.0
    style_deviations: List[Dict] = field(default_factory=list)

    # 导航评估
    navigation_score: float = 50.0
    structural_issues: List[str] = field(default_factory=list)

    # 综合评分
    overall_score: float = 50.0

    def to_dict(self) -> dict:
        return {
            "readability": self.readability.to_dict(),
            "professionalism": self.professionalism.to_dict(),
            "accessibility": self.accessibility.to_dict(),
            "consistency": {
                "score": round(self.consistency_score, 1),
                "deviations": self.style_deviations,
            },
            "navigation": {
                "score": round(self.navigation_score, 1),
                "issues": self.structural_issues,
            },
            "overall": round(self.overall_score, 1),
        }


@dataclass
class QualityImprovement:
    """质量改进建议"""
    dimension: QualityDimension
    priority: int  # 1-5, 1=最高
    issue: str
    current_state: str
    suggested_fix: str
    impact: str  # "high"/"medium"/"low"

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension.value,
            "priority": self.priority,
            "issue": self.issue,
            "current": self.current_state,
            "suggestion": self.suggested_fix,
            "impact": self.impact,
        }


class FormatEvaluator:
    """
    格式质量评估器

    评估文档格式质量的多个维度，并生成改进建议
    """

    # 标准值
    STANDARD_FONT_SIZES = {
        "heading_1": 26,   # pt
        "heading_2": 22,
        "heading_3": 18,
        "body": 12,
        "caption": 10,
    }

    STANDARD_LINE_SPACING = {
        "compact": 1.2,
        "normal": 1.5,
        "relaxed": 1.8,
    }

    # 颜色对比度标准 (WCAG 2.1)
    CONTRAST_STANDARDS = {
        "aa_normal": 4.5,    # 普通文本
        "aa_large": 3.0,     # 大文本 (18pt+ 或 14pt+ bold)
        "aaa_normal": 7.0,   # 增强
    }

    def __init__(self, brand_rules: Dict = None, industry: str = "general"):
        self.brand_rules = brand_rules or {}
        self.industry = industry

    def evaluate(self, format_info, format_graph=None) -> Tuple[QualityMetrics, List[QualityImprovement]]:
        """
        评估格式质量

        Args:
            format_info: 格式信息 (from FormatParser)
            format_graph: 格式图谱 (optional)

        Returns:
            (QualityMetrics, List[QualityImprovement])
        """
        metrics = QualityMetrics()
        improvements = []

        # 1. 可读性评估
        readability, r_improvements = self._evaluate_readability(format_info)
        metrics.readability = readability
        improvements.extend(r_improvements)

        # 2. 专业性评估
        professional, p_improvements = self._evaluate_professionalism(format_info)
        metrics.professionalism = professional
        improvements.extend(p_improvements)

        # 3. 可访问性评估
        accessibility, a_improvements = self._evaluate_accessibility(format_info)
        metrics.accessibility = accessibility
        improvements.extend(a_improvements)

        # 4. 一致性评估
        consistency, c_improvements = self._evaluate_consistency(format_info, format_graph)
        metrics.consistency_score = consistency
        improvements.extend(c_improvements)

        # 5. 导航评估
        navigation, n_improvements = self._evaluate_navigation(format_info)
        metrics.navigation_score = navigation
        improvements.extend(n_improvements)

        # 计算综合评分
        metrics.overall_score = (
            metrics.readability.overall_score * 0.3 +
            metrics.professionalism.overall_score * 0.3 +
            metrics.accessibility.overall_score * 0.2 +
            metrics.consistency_score * 0.1 +
            metrics.navigation_score * 0.1
        )

        return metrics, improvements

    def _evaluate_readability(self, format_info) -> Tuple[ReadabilityMetrics, List[QualityImprovement]]:
        """评估可读性"""
        metrics = ReadabilityMetrics()
        improvements = []

        total_elements = len(format_info.elements)
        if total_elements == 0:
            metrics.overall_score = 100.0
            return metrics, improvements

        # 字体评估
        font_scores = []
        size_issues = []
        family_issues = []

        for elem in format_info.elements:
            v = elem.visual
            s = elem.structural

            score = 50.0
            issues = []

            # 字体大小检查
            if v.font_size:
                if s.heading_level > 0:
                    expected = self.STANDARD_FONT_SIZES.get(f"heading_{s.heading_level}", 18)
                    if abs(v.font_size - expected) > 6:
                        size_issues.append(elem.element_id)
                        score -= 10
                elif v.font_size < 9:
                    size_issues.append(elem.element_id)
                    score -= 15

            # 字体族检查
            if v.font_name:
                appropriate_fonts = ["Microsoft YaHei", "SimSun", "SimHei", "Arial", "Times New Roman"]
                if not any(f.lower() in v.font_name.lower() for f in appropriate_fonts):
                    family_issues.append(elem.element_id)
                    score -= 5

            font_scores.append(max(score, 0))

        metrics.font_score = sum(font_scores) / len(font_scores) if font_scores else 50.0
        metrics.font_size_appropriate = len(size_issues) < total_elements * 0.1
        metrics.font_family_appropriate = len(family_issues) < total_elements * 0.2

        if size_issues:
            improvements.append(QualityImprovement(
                dimension=QualityDimension.READABILITY,
                priority=3,
                issue="部分元素的字体大小不符合标准",
                current_state=f"{len(size_issues)} 个元素",
                suggested_fix="标题使用 18-26pt，正文使用 10-12pt",
                impact="medium",
            ))

        # 对比度评估
        contrast_scores = []
        low_contrast = []

        for elem in format_info.elements:
            if elem.visual.font_color and elem.visual.font_color != "000000":
                ratio = self._calculate_contrast_ratio(elem.visual.font_color, "FFFFFF")
                if ratio < self.CONTRAST_STANDARDS["aa_normal"]:
                    low_contrast.append(elem.element_id)
                    contrast_scores.append(ratio * 20)  # 转换为分数
                else:
                    contrast_scores.append(80 + min(ratio - 4.5, 3) * 5)
            else:
                contrast_scores.append(100)

        metrics.contrast_ratio = sum(c for c in contrast_scores if c < 100) / max(len([c for c in contrast_scores if c < 100]), 1) if low_contrast else 7.0
        metrics.contrast_score = sum(contrast_scores) / len(contrast_scores)
        metrics.low_contrast_elements = low_contrast[:5]  # 只保留前5个

        if low_contrast:
            improvements.append(QualityImprovement(
                dimension=QualityDimension.READABILITY,
                priority=2,
                issue="部分文本对比度不足",
                current_state=f"{len(low_contrast)} 个元素对比度 < 4.5:1",
                suggested_fix="确保文本与背景的对比度至少为 4.5:1 (WCAG AA)",
                impact="high",
            ))

        # 间距评估
        line_scores = []
        spacing_issues = []

        for elem in format_info.elements:
            if elem.visual.line_spacing:
                if 1.2 <= elem.visual.line_spacing <= 2.0:
                    line_scores.append(100)
                elif elem.visual.line_spacing < 1.2:
                    line_scores.append(60)
                    spacing_issues.append(elem.element_id)
                else:
                    line_scores.append(80)
            else:
                line_scores.append(70)

        metrics.line_spacing_score = sum(line_scores) / len(line_scores)

        if spacing_issues:
            improvements.append(QualityImprovement(
                dimension=QualityDimension.READABILITY,
                priority=3,
                issue="部分段落的行距过密",
                current_state="行距 < 1.2",
                suggested_fix="建议行距设置为 1.5 左右",
                impact="medium",
            ))

        metrics.paragraph_spacing_score = 70.0  # 简化评估

        # 综合评分
        metrics.overall_score = (
            metrics.font_score * 0.3 +
            metrics.contrast_score * 0.3 +
            metrics.line_spacing_score * 0.2 +
            metrics.paragraph_spacing_score * 0.2
        )

        return metrics, improvements

    def _evaluate_professionalism(self, format_info) -> Tuple[ProfessionalMetrics, List[QualityImprovement]]:
        """评估专业性"""
        metrics = ProfessionalMetrics()
        improvements = []

        # 品牌合规检查
        brand_primary = self.brand_rules.get("primary_color", "")
        brand_font = self.brand_rules.get("primary_font", "")

        colors_used = set()
        fonts_used = set()

        for elem in format_info.elements:
            if elem.visual.font_color:
                colors_used.add(elem.visual.font_color)
            if elem.visual.font_name:
                fonts_used.add(elem.visual.font_name)

        # 颜色合规
        if brand_primary and brand_primary.upper() not in [c.upper() for c in colors_used]:
            metrics.brand_color_used = False
            metrics.brand_compliance_score -= 20
            improvements.append(QualityImprovement(
                dimension=QualityDimension.PROFESSIONALISM,
                priority=4,
                issue="未使用品牌主色",
                current_state="文档中未发现品牌主色",
                suggested_fix=f"在关键位置使用品牌主色: {brand_primary}",
                impact="medium",
            ))

        # 字体合规
        if brand_font and brand_font not in fonts_used:
            metrics.brand_font_used = False
            metrics.brand_compliance_score -= 15

        metrics.brand_compliance_score = max(metrics.brand_compliance_score, 0)

        # 样式一致性
        alignment_counts = {}
        for elem in format_info.elements:
            align = elem.visual.alignment
            alignment_counts[align] = alignment_counts.get(align, 0) + 1

        if alignment_counts:
            most_common = max(alignment_counts.values())
            consistency_ratio = most_common / sum(alignment_counts.values())
            metrics.style_consistency_score = consistency_ratio * 100

        # 综合评分
        metrics.overall_score = (
            metrics.brand_compliance_score * 0.3 +
            metrics.industry_standard_score * 0.2 +
            metrics.color_harmony_score * 0.2 +
            metrics.style_consistency_score * 0.2 +
            metrics.detail_score * 0.1
        )

        return metrics, improvements

    def _evaluate_accessibility(self, format_info) -> Tuple[AccessibilityMetrics, List[QualityImprovement]]:
        """评估可访问性"""
        metrics = AccessibilityMetrics()
        improvements = []

        # 检查标题结构
        headings = [e for e in format_info.elements if e.semantic.is_heading]
        if headings:
            levels = [h.semantic.heading_rank for h in headings]
            has_hierarchy = len(set(levels)) > 1 or (len(levels) == 1 and levels[0] > 0)

            if not has_hierarchy:
                metrics.headings_proper = False
                improvements.append(QualityImprovement(
                    dimension=QualityDimension.ACCESSIBILITY,
                    priority=3,
                    issue="缺少标题层级结构",
                    current_state="文档中没有清晰的标题层级",
                    suggested_fix="使用 H1-H3 建立清晰的标题层级",
                    impact="high",
                ))
            metrics.screen_reader_score = 80 if has_hierarchy else 50

        # 检查列表结构
        lists = [e for e in format_info.elements if e.structural.list_info]
        if lists:
            metrics.list_structure_correct = True
            metrics.screen_reader_score += 10

        # 检查替代文本 (图片)
        images = [e for e in format_info.elements if e.element_type.value == "image"]
        if images:
            images_without_alt = [e for e in images if not e.metadata.get("alt_text")]
            if images_without_alt:
                improvements.append(QualityImprovement(
                    dimension=QualityDimension.ACCESSIBILITY,
                    priority=2,
                    issue="部分图片缺少替代文本",
                    current_state=f"{len(images_without_alt)}/{len(images)} 图片",
                    suggested_fix="为所有图片添加描述性替代文本",
                    impact="high",
                ))

        # 色盲友好检查
        color_based_info = []
        for elem in format_info.elements:
            if elem.semantic.color_meaning:  # 颜色有含义
                color_based_info.append(elem.element_id)

        if color_based_info:
            metrics.color_not_sole_indicator = False
            improvements.append(QualityImprovement(
                dimension=QualityDimension.ACCESSIBILITY,
                priority=3,
                issue="颜色被用作唯一信息载体",
                current_state=f"{len(color_based_info)} 个元素",
                suggested_fix="除了颜色外，还应使用文字/图标等载体传达信息",
                impact="medium",
            ))

        metrics.overall_score = (
            metrics.screen_reader_score * 0.4 +
            metrics.colorblind_score * 0.3 +
            metrics.zoom_score * 0.15 +
            metrics.navigation_score * 0.15
        )

        return metrics, improvements

    def _evaluate_consistency(self, format_info, format_graph) -> Tuple[float, List[QualityImprovement]]:
        """评估一致性"""
        score = 70.0
        improvements = []

        if not format_graph:
            return score, improvements

        # 检测格式冲突
        conflicts = format_graph.find_format_conflicts()
        if conflicts:
            score -= min(len(conflicts) * 10, 30)
            improvements.append(QualityImprovement(
                dimension=QualityDimension.CONSISTENCY,
                priority=2,
                issue="文档中存在格式不一致",
                current_state=f"发现 {len(conflicts)} 处格式冲突",
                suggested_fix="统一相同元素的格式设置",
                impact="high",
            ))

        return max(score, 0), improvements

    def _evaluate_navigation(self, format_info) -> Tuple[float, List[QualityImprovement]]:
        """评估导航"""
        score = 70.0
        improvements = []

        # 检查是否有目录
        has_toc = any("目录" in e.text_content or "contents" in e.text_content.lower()
                     for e in format_info.elements[:10])  # 只检查前10个

        if not has_toc and len(format_info.elements) > 20:
            improvements.append(QualityImprovement(
                dimension=QualityDimension.NAVIGATION,
                priority=4,
                issue="长文档缺少目录",
                current_state="未发现目录",
                suggested_fix="建议在文档开头添加目录",
                impact="medium",
            ))
            score -= 10

        # 检查页码
        has_page_numbers = any("page" in e.metadata.get("type", "").lower()
                              for e in format_info.elements)

        return max(score, 0), improvements

    @staticmethod
    def _calculate_contrast_ratio(color1: str, color2: str) -> float:
        """计算颜色对比度 (简化版)"""
        def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = hex_color[0]*2 + hex_color[1]*2 + hex_color[2]*2
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def luminance(rgb: Tuple[int, int, int]) -> float:
            r, g, b = [x/255.0 for x in rgb]
            r = r if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        try:
            rgb1 = hex_to_rgb(color1)
            rgb2 = hex_to_rgb(color2)
            l1 = luminance(rgb1)
            l2 = luminance(rgb2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)
        except Exception:
            return 4.5  # 默认值
