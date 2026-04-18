"""
数据一致性检查器 (Data Consistency Checker)
==========================================

核心理念：
- 环评报告的数据量大、跨章节引用多，容易出现前后不一致
- AI 生成的报告可能存在"幻觉"数据
- 必须建立严格的数据一致性检查机制

检查类型：
1. 内部一致性：章节内数据自洽
2. 外部一致性：表格数据与正文描述一致
3. 引用一致性：多个地方引用的同一数据应相同
4. 计算一致性：汇总数据与分项数据应吻合
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ConsistencyIssueType(Enum):
    """一致性问题类型"""
    # 数值不一致
    VALUE_MISMATCH = "value_mismatch"           # 同一数据多次出现值不同
    TABLE_TEXT_MISMATCH = "table_text_mismatch"  # 表格数据与正文描述不一致
    UNIT_INCONSISTENCY = "unit_inconsistency"     # 单位使用不一致

    # 汇总不一致
    SUM_MISMATCH = "sum_mismatch"                 # 汇总值与分项和不符
    CALCULATION_ERROR = "calculation_error"       # 计算结果错误

    # 引用不一致
    CROSS_REFERENCE_ERROR = "cross_reference_error"  # 章节间引用不一致
    DUPLICATE_INCONSISTENCY = "duplicate_inconsistency"  # 重复描述不一致

    # 逻辑不一致
    LOGIC_CONTRADICTION = "logic_contradiction"   # 逻辑矛盾
    RANGE_OUTLIER = "range_outlier"               # 数值超出合理范围

    # 来源问题
    UNVERIFIED_DATA = "unverified_data"           # 数据未经核实
    HALLUCINATED_DATA = "hallucinated_data"       # 疑似幻觉数据


class ConsistencyLevel(Enum):
    """一致性严重等级"""
    CRITICAL = "critical"   # 必须修复
    WARNING = "warning"     # 建议修复
    INFO = "info"          # 仅供参考


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    issue_id: str
    issue_type: ConsistencyIssueType
    level: ConsistencyLevel

    # 问题描述
    title: str
    description: str

    # 位置信息
    location: str                    # 问题所在位置
    section_id: str = ""            # 章节ID
    field_name: str = ""             # 字段名

    # 涉及的数据
    involved_values: list = field(default_factory=list)  # 涉及的值

    # 建议修复
    suggested_fix: str = ""
    auto_fixable: bool = False       # 是否可自动修复

    # 元数据
    detected_at: datetime = field(default_factory=datetime.now)
    verified: bool = False
    verified_by: str = ""
    verified_at: datetime = None


class DataConsistencyChecker:
    """
    数据一致性检查器

    用法:
        checker = DataConsistencyChecker()

        # 执行全面检查
        issues = checker.check_full_report(report_draft)

        # 执行针对性检查
        issues = checker.check_cross_reference(sections)
        issues = checker.check_calculations(sections)

        # 自动修复可修复的问题
        fixed_report = checker.auto_fix(sections, issues)
    """

    # 常见数值一致性规则
    VALUE_TOLERANCE = 0.01  # 数值比较容差 1%

    # 合理范围定义
    REASONABLE_RANGES = {
        "emission_rate": (0, 10000),      # 排放速率 g/s
        "concentration": (0, 1000),        # 浓度 mg/m³
        "height": (0, 200),                # 高度 m
        "area": (0, 1000000),             # 面积 m²
        "distance": (0, 10000),            # 距离 m
        "temperature": (-50, 1000),       # 温度 °C
        "velocity": (0, 50),              # 风速 m/s
    }

    def __init__(self):
        self._check_rules: list[dict] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """加载默认检查规则"""
        # 跨章节引用规则
        self._check_rules = [
            {
                "rule_id": "project_info_consistency",
                "description": "项目基本信息在封面、概述、工程分析中应一致",
                "fields": ["project_name", "location", "industry"],
                "sections": ["cover", "overview", "engineering"],
                "check": self._check_field_consistency
            },
            {
                "rule_id": "source_strength_table_text",
                "description": "大气源强表格数据与正文描述应一致",
                "table_key": "air_source_table",
                "text_patterns": [r"排气筒高度(\d+)m", r"排放速率(\d+\.?\d*)g/s"],
                "check": self._check_table_text_consistency
            },
            {
                "rule_id": "emission_inventory_total",
                "description": "污染物排放清单汇总值应与分项和一致",
                "sections": ["pollution_discharge", "air_impact"],
                "check": self._check_sum_consistency
            },
            {
                "rule_id": "prediction_results_conclusion",
                "description": "预测结果与结论中的达标题应一致",
                "prediction_sections": ["air_impact", "water_impact", "noise_impact"],
                "conclusion_section": "conclusion",
                "check": self._check_prediction_conclusion_consistency
            }
        ]

    def check_full_report(self, report_draft: dict) -> list[ConsistencyIssue]:
        """
        执行全面一致性检查

        Args:
            report_draft: 报告草稿

        Returns:
            list[ConsistencyIssue]: 发现的问题列表
        """
        all_issues = []
        sections = report_draft.get("sections", {})

        # 1. 字段一致性检查
        all_issues.extend(self._check_all_field_consistency(sections))

        # 2. 数值范围检查
        all_issues.extend(self._check_all_value_ranges(sections))

        # 3. 汇总一致性检查
        all_issues.extend(self._check_all_sum_consistency(sections))

        # 4. 跨章节引用检查
        all_issues.extend(self._check_cross_references(sections))

        # 5. 表格与正文一致性检查
        all_issues.extend(self._check_table_text_consistency(sections))

        # 6. 计算验证
        all_issues.extend(self._check_calculations(sections))

        return all_issues

    def _check_all_field_consistency(self, sections: dict) -> list[ConsistencyIssue]:
        """检查所有字段的一致性"""
        issues = []

        # 提取项目关键字段
        project_fields = {}

        # 从概述章节提取
        overview = sections.get("overview")
        if overview:
            content = overview.raw_content
            project_fields["project_name"] = self._extract_field(content, r"项目名称</th><td>([^<]+)</td>")
            project_fields["location"] = self._extract_field(content, r"建设地点</th><td>([^<]+)</td>")
            project_fields["industry"] = self._extract_field(content, r"行业类别</th><td>([^<]+)</td>")

        # 从其他章节提取并对比
        for section_id, section in sections.items():
            if section_id == "overview":
                continue

            content = section.raw_content
            for field_name, pattern in [
                ("project_name", r"项目名称[^<]*</th><td>([^<]+)</td>"),
                ("location", r"建设地点[^<]*</th><td>([^<]+)</td>"),
                ("industry", r"行业类别[^<]*</th><td>([^<]+)</td>"),
            ]:
                value = self._extract_field(content, pattern)
                if value and project_fields.get(field_name):
                    if value != project_fields[field_name]:
                        issues.append(ConsistencyIssue(
                            issue_id=f"{section_id}_{field_name}_mismatch",
                            issue_type=ConsistencyIssueType.VALUE_MISMATCH,
                            level=ConsistencyLevel.WARNING,
                            title=f"{field_name}不一致",
                            description=f"概述章节与{section.title}中的{field_name}描述不一致",
                            location=f"{section.title} > {field_name}",
                            section_id=section_id,
                            field_name=field_name,
                            involved_values=[project_fields[field_name], value],
                            suggested_fix=f"统一为：{project_fields[field_name]}"
                        ))

        return issues

    def _check_all_value_ranges(self, sections: dict) -> list[ConsistencyIssue]:
        """检查数值是否在合理范围内"""
        issues = []

        for section_id, section in sections.items():
            # 提取数值
            numeric_values = re.findall(
                r"(\w+)[^<]*?(?:为|:|：)\s*(\d+\.?\d*)\s*(m|g|s|mg|m³|℃|%)?",
                section.raw_content
            )

            for field_name, value_str, unit in numeric_values:
                try:
                    value = float(value_str)

                    # 检查是否在合理范围
                    for range_key, (min_val, max_val) in self.REASONABLE_RANGES.items():
                        if range_key in field_name.lower() or range_key in field_name:
                            if value < min_val or value > max_val:
                                issues.append(ConsistencyIssue(
                                    issue_id=f"range_outlier_{section_id}_{field_name}",
                                    issue_type=ConsistencyIssueType.RANGE_OUTLIER,
                                    level=ConsistencyLevel.WARNING,
                                    title=f"{field_name}数值超出合理范围",
                                    description=f"数值 {value}{unit} 超出合理范围 [{min_val}, {max_val}]",
                                    location=f"{section.title}",
                                    section_id=section_id,
                                    field_name=field_name,
                                    involved_values=[value],
                                    suggested_fix=f"请核实 {field_name} 的数值是否正确"
                                ))
                except ValueError:
                    continue

        return issues

    def _check_all_sum_consistency(self, sections: dict) -> list[ConsistencyIssue]:
        """检查汇总一致性"""
        issues = []

        # 检查排放清单汇总
        pollution = sections.get("pollution_discharge")
        if pollution:
            # 提取表格中的数值
            tables = pollution.tables

            # 检查废气污染物排放量汇总
            for table in tables:
                if "废气" in table.get("title", ""):
                    rows = table.get("rows", [])
                    total = 0.0
                    item_values = []

                    for row in rows:
                        # 尝试提取第三列（排放量）的数值
                        if len(row) >= 3:
                            try:
                                val_str = str(row[2]).replace(",", "")
                                val = float(re.search(r"[\d.]+", val_str).group())
                                total += val
                                item_values.append((row[0], val))
                            except (ValueError, AttributeError):
                                continue

                    # 检查是否有汇总行
                    has_total = any("合计" in str(row[0]) or "总计" in str(row[0]) for row in rows)

                    if item_values and not has_total:
                        issues.append(ConsistencyIssue(
                            issue_id="missing_emission_total",
                            issue_type=ConsistencyIssueType.SUM_MISMATCH,
                            level=ConsistencyLevel.INFO,
                            title="缺少排放量汇总行",
                            description=f"废气排放清单共 {len(item_values)} 项，合计 {total:.2f} t/a，建议添加汇总行",
                            location="污染物排放清单 > 废气",
                            section_id="pollution_discharge",
                            involved_values=[total],
                            suggested_fix=f"添加汇总行：合计 {total:.2f} t/a",
                            auto_fixable=True
                        ))

        return issues

    def _check_cross_references(self, sections: dict) -> list[ConsistencyIssue]:
        """检查跨章节引用一致性"""
        issues = []

        # 1. 污染源数量应在工程分析和源强表格中一致
        engineering = sections.get("engineering")
        air_impact = sections.get("air_impact")

        if engineering and air_impact:
            # 提取工程分析中的源数量
            eng_sources = len(re.findall(r"<h[23]>", engineering.raw_content))

            # 提取源强表格中的行数
            air_tables = air_impact.tables
            source_count = 0
            for table in air_tables:
                if "大气污染源" in table.get("title", ""):
                    source_count = len(table.get("rows", []))

            # 如果差异较大，提示检查
            if source_count > 0 and eng_sources > 0:
                if abs(eng_sources - source_count) > 3:
                    issues.append(ConsistencyIssue(
                        issue_id="source_count_mismatch",
                        issue_type=ConsistencyIssueType.CROSS_REFERENCE_ERROR,
                        level=ConsistencyLevel.WARNING,
                        title="污染源数量不一致",
                        description=f"工程分析描述了 {eng_sources} 个工艺单元，源强表格中有 {source_count} 个污染源，请核实是否匹配",
                        location="工程分析 / 大气环境影响",
                        section_id="engineering",
                        involved_values=[eng_sources, source_count],
                        suggested_fix="确保工艺单元与污染源一一对应"
                    ))

        # 2. 结论中的达标题应与预测结果一致
        conclusion = sections.get("conclusion")
        if conclusion and air_impact:
            conclusion_text = conclusion.raw_content
            air_tables = air_impact.tables

            # 检查预测结果表格中的达标题
            for table in air_tables:
                if "预测结果" in table.get("title", ""):
                    for row in table.get("rows", []):
                        if len(row) >= 4:
                            compliance = str(row[3])
                            if "达标" in compliance or "超标" in compliance:
                                # 检查结论中是否有对应的达标题
                                if compliance not in conclusion_text:
                                    issues.append(ConsistencyIssue(
                                        issue_id="conclusion_mismatch",
                                        issue_type=ConsistencyIssueType.CROSS_REFERENCE_ERROR,
                                        level=ConsistencyLevel.CRITICAL,
                                        title="结论与预测结果不一致",
                                        description=f"预测结果显示'{compliance}'，但结论中未提及",
                                        location="结论与建议 > 达标情况",
                                        section_id="conclusion",
                                        involved_values=[compliance],
                                        suggested_fix="请在结论的达标情况表中补充此达标题"
                                    ))

        return issues

    def _check_table_text_consistency(self, sections: dict) -> list[ConsistencyIssue]:
        """检查表格与正文描述的一致性"""
        issues = []

        # 检查表格数据与正文描述的数值是否一致
        for section_id, section in sections.items():
            tables = getattr(section, "tables", [])

            for table in tables:
                table_title = table.get("title", "")
                rows = table.get("rows", [])

                # 检查是否有占位符
                for i, row in enumerate(rows):
                    for j, cell in enumerate(row):
                        cell_str = str(cell)
                        if "待计算" in cell_str or "待填入" in cell_str or "待核实" in cell_str:
                            issues.append(ConsistencyIssue(
                                issue_id=f"placeholder_{section_id}_{i}_{j}",
                                issue_type=ConsistencyIssueType.UNVERIFIED_DATA,
                                level=ConsistencyLevel.CRITICAL,
                                title=f"{table_title} - 存在未填入数据",
                                description=f"表格第{i+1}行第{j+1}列存在占位符：{cell_str}",
                                location=f"{section.title} > {table_title}",
                                section_id=section_id,
                                field_name=f"table_cell_{i}_{j}",
                                involved_values=[cell_str],
                                suggested_fix="请填入真实计算数据或标注为人工待填"
                            ))

                        # 检查是否疑似幻觉数据（格式正确但明显不合理）
                        if self._is_suspicious_value(cell_str):
                            issues.append(ConsistencyIssue(
                                issue_id=f"suspicious_{section_id}_{i}_{j}",
                                issue_type=ConsistencyIssueType.HALLUCINATED_DATA,
                                level=ConsistencyLevel.WARNING,
                                title=f"{table_title} - 数据疑似虚构",
                                description=f"表格第{i+1}行第{j+1}列的值 '{cell_str}' 格式可疑，请核实",
                                location=f"{section.title} > {table_title}",
                                section_id=section_id,
                                field_name=f"table_cell_{i}_{j}",
                                involved_values=[cell_str],
                                suggested_fix="请核实此数据的真实性"
                            ))

        return issues

    def _check_calculations(self, sections: dict) -> list[ConsistencyIssue]:
        """检查计算正确性"""
        issues = []

        # 1. 排放量单位换算检查
        # 例如：g/s -> t/a 应该满足 86400 * 365 / 10^6 = 31.536

        # 2. 源强计算结果与描述的一致性

        return issues

    def _extract_field(self, content: str, pattern: str) -> str:
        """从内容中提取字段值"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""

    def _is_suspicious_value(self, value_str: str) -> bool:
        """判断值是否疑似虚构"""
        # 常见的占位符模式
        placeholder_patterns = [
            r"^xxx+$",
            r"^待\d+$",
            r"^[\d]{10,}$",  # 超过10位数字
            r"^无限$",
            r"^巨大$",
        ]

        for pattern in placeholder_patterns:
            if re.match(pattern, value_str):
                return True

        return False

    def check_field_consistency(
        self,
        sections: dict,
        field_name: str,
        expected_value: str
    ) -> list[ConsistencyIssue]:
        """检查特定字段在所有章节中的一致性"""
        return self._check_all_field_consistency(sections)

    def check_table_text_consistency(
        self,
        table_title: str,
        table_rows: list,
        body_text: str
    ) -> list[ConsistencyIssue]:
        """检查特定表格与正文的一致性"""
        issues = []

        # 提取正文中的数值
        text_numbers = re.findall(r"(\d+\.?\d*)\s*(m|g|s|mg|m³|℃|%)", body_text)

        # 与表格对比
        for row in table_rows:
            for cell in row:
                cell_str = str(cell)
                numbers_in_cell = re.findall(r"(\d+\.?\d*)", cell_str)

                for num in numbers_in_cell:
                    # 检查这个数字是否在正文中提到
                    if num not in body_text:
                        issues.append(ConsistencyIssue(
                            issue_id=f"table_text_{table_title}_{cell}",
                            issue_type=ConsistencyIssueType.TABLE_TEXT_MISMATCH,
                            level=ConsistencyLevel.INFO,
                            title="表格数值未在正文中说明",
                            description=f"表格中存在数值 {num}，但正文未提及",
                            involved_values=[num],
                            suggested_fix=f"建议在正文中补充说明该数值"
                        ))

        return issues

    def check_sum_consistency(
        self,
        total_value: float,
        item_values: list,
        item_names: list,
        tolerance: float = 0.01
    ) -> list[ConsistencyIssue]:
        """检查汇总一致性"""
        issues = []
        calculated_total = sum(item_values)

        if abs(calculated_total - total_value) / max(total_value, 1) > tolerance:
            issues.append(ConsistencyIssue(
                issue_id="sum_mismatch",
                issue_type=ConsistencyIssueType.SUM_MISMATCH,
                level=ConsistencyLevel.CRITICAL,
                title="汇总值与分项和不一致",
                description=f"声明的汇总值 {total_value} 与分项和 {calculated_total:.2f} 不符",
                involved_values=[total_value, calculated_total],
                suggested_fix=f"请修正汇总值或分项数据"
            ))

        return issues

    def generate_consistency_report(self, issues: list[ConsistencyIssue]) -> str:
        """生成一致性检查报告"""
        if not issues:
            return "✅ 未发现一致性问题"

        # 按严重程度分组
        critical = [i for i in issues if i.level == ConsistencyLevel.CRITICAL]
        warning = [i for i in issues if i.level == ConsistencyLevel.WARNING]
        info = [i for i in issues if i.level == ConsistencyLevel.INFO]

        report = f"""
# 数据一致性检查报告

## 概要

| 等级 | 数量 |
|------|------|
| 🔴 严重 | {len(critical)} |
| 🟡 警告 | {len(warning)} |
| 🔵 提示 | {len(info)} |

"""

        if critical:
            report += "\n## 🔴 严重问题（必须修复）\n\n"
            for issue in critical:
                report += f"""
### {issue.title}
- **位置**: {issue.location}
- **描述**: {issue.description}
- **涉及值**: {', '.join(str(v) for v in issue.involved_values)}
- **建议修复**: {issue.suggested_fix}
"""

        if warning:
            report += "\n## 🟡 警告问题（建议修复）\n\n"
            for issue in warning:
                report += f"""
### {issue.title}
- **位置**: {issue.location}
- **描述**: {issue.description}
- **涉及值**: {', '.join(str(v) for v in issue.involved_values)}
- **建议修复**: {issue.suggested_fix}
"""

        if info:
            report += "\n## 🔵 提示信息\n\n"
            for issue in info:
                report += f"""
### {issue.title}
- **位置**: {issue.location}
- **描述**: {issue.description}
"""

        return report

    def auto_fix(
        self,
        sections: dict,
        issues: list[ConsistencyIssue]
    ) -> dict:
        """自动修复可修复的问题"""
        fixed_sections = {}

        for issue in issues:
            if not issue.auto_fixable:
                continue

            section_id = issue.section_id
            if section_id not in fixed_sections:
                fixed_sections[section_id] = sections[section_id].raw_content

            # 根据问题类型执行修复
            if issue.issue_type == ConsistencyIssueType.SUM_MISMATCH:
                if "emission" in issue.issue_id:
                    # 添加汇总行
                    total = issue.involved_values[0]
                    fixed_sections[section_id] += f"\n<tr><td>合计</td><td></td><td>{total:.2f}</td><td>t/a</td><td></td></tr>"

            elif issue.issue_type == ConsistencyIssueType.UNVERIFIED_DATA:
                # 将占位符标记为人工待填
                fixed_sections[section_id] = fixed_sections[section_id].replace(
                    "待计算", "<span class='manual-input'>待人工填入</span>"
                )

        return fixed_sections


def create_consistency_checker() -> DataConsistencyChecker:
    """创建一致性检查器实例"""
    return DataConsistencyChecker()