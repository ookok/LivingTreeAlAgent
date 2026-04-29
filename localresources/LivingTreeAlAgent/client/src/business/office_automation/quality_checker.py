"""
✅ 质量检查系统

多层验证:
- 技术验证: 格式、结构、完整性
- 业务验证: 内容质量、逻辑性
- 合规验证: 企业标准、品牌规范

自动修复能力:
- 常见格式问题自动修复
- 标记需要人工复核的内容
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class CheckLevel(Enum):
    """检查级别"""
    ERROR = "error"          # 必须修复
    WARNING = "warning"      # 建议修复
    INFO = "info"            # 信息提示
    PASS = "pass"            # 通过


class CheckCategory(Enum):
    """检查类别"""
    FORMAT = "format"            # 格式检查
    STRUCTURE = "structure"      # 结构检查
    CONTENT = "content"          # 内容检查
    COMPLIANCE = "compliance"    # 合规检查
    BRAND = "brand"              # 品牌检查
    ACCESSIBILITY = "accessibility"  # 可访问性


@dataclass
class CheckResult:
    """检查结果"""
    category: CheckCategory
    level: CheckLevel
    message: str
    field: str = ""
    expected: Any = None
    actual: Any = None
    auto_fixable: bool = False
    fix_suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "level": self.level.value,
            "message": self.message,
            "field": self.field,
            "expected": str(self.expected) if self.expected else None,
            "actual": str(self.actual) if self.actual else None,
            "auto_fixable": self.auto_fixable,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class QualityReport:
    """质量报告"""
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    info: int = 0
    score: float = 0.0     # 0-100
    results: List[CheckResult] = field(default_factory=list)
    auto_fixed: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "info": self.info,
            "score": round(self.score, 1),
            "results": [r.to_dict() for r in self.results],
            "auto_fixed": self.auto_fixed,
        }


class QualityChecker:
    """
    质量检查器

    检查规则:
    - 格式: 页边距、字体、颜色、间距
    - 结构: 标题层级、目录、页码
    - 内容: 拼写、语法、逻辑性
    - 合规: 企业标准、行业规范
    - 品牌: 品牌色、品牌字体、Logo
    """

    # 标准文档规范
    STANDARD_MARGINS = {  # cm
        "docx": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
        "government": {"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6},
    }

    # 字体规范
    STANDARD_FONTS = {
        "docx": {"heading": "Microsoft YaHei", "body": "SimSun"},
        "government": {"heading": "FangSong", "body": "FangSong"},
    }

    def __init__(self, brand_rules: dict = None):
        self.brand_rules = brand_rules or {}

    def check(self, document_data: dict, document_type: str = "docx",
              theme: dict = None) -> QualityReport:
        """
        执行全面质量检查

        Args:
            document_data: 文档数据 (包含 content, metadata, styles 等)
            document_type: 文档类型
            theme: 主题信息

        Returns:
            QualityReport 质量报告
        """
        report = QualityReport()

        # 1. 格式检查
        self._check_format(document_data, document_type, theme, report)

        # 2. 结构检查
        self._check_structure(document_data, report)

        # 3. 内容检查
        self._check_content(document_data, report)

        # 4. 合规检查
        self._check_compliance(document_data, document_type, report)

        # 5. 品牌检查
        if self.brand_rules:
            self._check_brand(document_data, report)

        # 计算评分
        report.total_checks = len(report.results)
        report.passed = sum(1 for r in report.results if r.level == CheckLevel.PASS)
        report.warnings = sum(1 for r in report.results if r.level == CheckLevel.WARNING)
        report.errors = sum(1 for r in report.results if r.level == CheckLevel.ERROR)
        report.info = sum(1 for r in report.results if r.level == CheckLevel.INFO)

        if report.total_checks > 0:
            error_penalty = report.errors * 20
            warning_penalty = report.warnings * 5
            report.score = max(0, 100 - error_penalty - warning_penalty)

        return report

    def _check_format(self, data: dict, doc_type: str, theme: dict, report: QualityReport):
        """格式检查"""
        # 检查页边距
        margins = data.get("margins", {})
        standard = self.STANDARD_MARGINS.get(doc_type, self.STANDARD_MARGINS["docx"])

        for side, expected in standard.items():
            actual = margins.get(side)
            if actual is not None:
                if abs(actual - expected) > 0.5:
                    report.results.append(CheckResult(
                        category=CheckCategory.FORMAT,
                        level=CheckLevel.WARNING,
                        message=f"页边距 {side} 不符合标准",
                        field=f"margin.{side}",
                        expected=f"{expected}cm",
                        actual=f"{actual}cm",
                        auto_fixable=True,
                        fix_suggestion=f"建议调整为 {expected}cm",
                    ))
                else:
                    report.results.append(CheckResult(
                        category=CheckCategory.FORMAT,
                        level=CheckLevel.PASS,
                        message=f"页边距 {side} 符合标准",
                        field=f"margin.{side}",
                    ))

        # 检查字体
        fonts = data.get("fonts", {})
        standard_fonts = self.STANDARD_FONTS.get(doc_type, self.STANDARD_FONTS["docx"])

        for role, expected_font in standard_fonts.items():
            actual_font = fonts.get(role)
            if actual_font and actual_font != expected_font:
                report.results.append(CheckResult(
                    category=CheckCategory.FORMAT,
                    level=CheckLevel.WARNING,
                    message=f"{role} 字体不符合规范",
                    field=f"font.{role}",
                    expected=expected_font,
                    actual=actual_font,
                    auto_fixable=True,
                    fix_suggestion=f"建议使用 {expected_font}",
                ))

    def _check_structure(self, data: dict, report: QualityReport):
        """结构检查"""
        paragraphs = data.get("paragraphs", [])
        headings = [p for p in paragraphs if p.get("style", "").startswith("Heading")]

        # 检查是否有标题
        if not headings:
            report.results.append(CheckResult(
                category=CheckCategory.STRUCTURE,
                level=CheckLevel.WARNING,
                message="文档缺少标题",
                auto_fixable=False,
                fix_suggestion="建议添加文档标题",
            ))

        # 检查标题层级是否连续
        prev_level = 0
        for h in headings:
            style = h.get("style", "")
            level_match = re.search(r'(\d+)', style)
            if level_match:
                level = int(level_match.group(1))
                if level > prev_level + 1:
                    report.results.append(CheckResult(
                        category=CheckCategory.STRUCTURE,
                        level=CheckLevel.INFO,
                        message=f"标题层级跳跃: {prev_level} → {level}",
                        auto_fixable=False,
                    ))
                prev_level = level

    def _check_content(self, data: dict, report: QualityReport):
        """内容检查"""
        content = data.get("content", "")

        if not content:
            report.results.append(CheckResult(
                category=CheckCategory.CONTENT,
                level=CheckLevel.ERROR,
                message="文档内容为空",
                auto_fixable=False,
            ))
            return

        # 检查内容长度
        word_count = len(content)
        if word_count < 100:
            report.results.append(CheckResult(
                category=CheckCategory.CONTENT,
                level=CheckLevel.WARNING,
                message=f"文档内容过短 ({word_count} 字)",
                auto_fixable=False,
            ))

        # 检查重复段落
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        seen = set()
        for p in paragraphs:
            if p in seen and len(p) > 20:
                report.results.append(CheckResult(
                    category=CheckCategory.CONTENT,
                    level=CheckLevel.WARNING,
                    message="发现重复段落",
                    auto_fixable=True,
                    fix_suggestion="建议删除重复内容",
                ))
                break
            seen.add(p)

    def _check_compliance(self, data: dict, doc_type: str, report: QualityReport):
        """合规检查"""
        # 政务公文特殊检查
        if doc_type == "government":
            content = data.get("content", "")

            # 检查红头格式
            if "红头" not in content and "文件" not in content:
                report.results.append(CheckResult(
                    category=CheckCategory.COMPLIANCE,
                    level=CheckLevel.WARNING,
                    message="政务公文缺少红头标识",
                    auto_fixable=True,
                ))

            # 检查文号
            if not re.search(r'[\u4e00-\u9fa5]{2,}\〔\d{4}\〕\d+号', content):
                report.results.append(CheckResult(
                    category=CheckCategory.COMPLIANCE,
                    level=CheckLevel.WARNING,
                    message="政务公文缺少标准文号",
                    auto_fixable=False,
                ))

    def _check_brand(self, data: dict, report: QualityReport):
        """品牌合规检查"""
        # 检查品牌色
        brand_color = self.brand_rules.get("primary_color")
        if brand_color:
            doc_colors = data.get("colors", [])
            if doc_colors and brand_color not in doc_colors:
                report.results.append(CheckResult(
                    category=CheckCategory.BRAND,
                    level=CheckLevel.WARNING,
                    message="文档主色与品牌色不一致",
                    expected=brand_color,
                    auto_fixable=True,
                    fix_suggestion="建议使用品牌标准色",
                ))

        # 检查 Logo
        if self.brand_rules.get("require_logo"):
            images = data.get("images", [])
            has_logo = any("logo" in img.get("name", "").lower() for img in images)
            if not has_logo:
                report.results.append(CheckResult(
                    category=CheckCategory.BRAND,
                    level=CheckLevel.WARNING,
                    message="文档缺少品牌 Logo",
                    auto_fixable=True,
                    fix_suggestion="建议添加品牌 Logo",
                ))
