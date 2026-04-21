"""
智能修复引擎 - 审查意见的"智能修复建议"
==========================================

核心思想：不只指出问题，还提供具体、可执行的修复方案。

功能：
1. 分级修复建议 - 根据问题级别提供对应的修复建议
2. 自动补丁生成 - 生成修正后的文本段落
3. 修复验证 - 验证修复是否有效
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class IssueLevel(Enum):
    """问题级别"""
    FATAL = "fatal"                 # 致命：缺少必填数据
    ERROR = "error"                # 错误：数据错误或逻辑矛盾
    WARNING = "warning"            # 警告：缺少推荐信息
    SUGGESTION = "suggestion"     # 建议：可增强内容
    FORMAT = "format"             # 格式：格式问题


class IssueCategory(Enum):
    """问题类别"""
    DATA_MISSING = "data_missing"           # 数据缺失
    DATA_ERROR = "data_error"              # 数据错误
    LOGIC_CONFLICT = "logic_conflict"      # 逻辑矛盾
    COMPLIANCE_ISSUE = "compliance_issue"  # 合规性问题
    FORMAT_ISSUE = "format_issue"          # 格式问题
    REFERENCE_ISSUE = "reference_issue"    # 引用问题
    CONSISTENCY_ISSUE = "consistency_issue"  # 一致性问题


class RepairAction(Enum):
    """修复动作"""
    AUTO_GENERATE = "auto_generate"       # 自动生成
    MANUAL_FILL = "manual_fill"           # 手动填写
    AUTO_REPLACE = "auto_replace"         # 自动替换
    UPLOAD_DOCUMENT = "upload_document"   # 上传文档
    USE_DEFAULT = "use_default"           # 使用默认值
    GENERATE_EXPLANATION = "generate_explanation"  # 生成说明


@dataclass
class RepairSuggestion:
    """修复建议"""
    issue_id: str
    issue_description: str
    issue_level: IssueLevel
    category: IssueCategory

    # 修复建议
    primary_action: RepairAction
    primary_suggestion: str
    primary_button_label: str  # 按钮标签

    # 备选建议（如果主建议不可用）
    alternative_actions: List[Tuple[RepairAction, str, str]] = field(default_factory=list)

    # 上下文信息
    context: Dict[str, Any] = field(default_factory=dict)

    # 自动修复预览
    preview: Optional[str] = None  # 修复后的预览文本

    def to_dict(self) -> Dict:
        return {
            "issue_id": self.issue_id,
            "issue_description": self.issue_description,
            "issue_level": self.issue_level.value,
            "category": self.category.value,
            "primary_action": self.primary_action.value,
            "primary_suggestion": self.primary_suggestion,
            "primary_button_label": self.primary_button_label,
            "alternative_actions": [
                {"action": a.value, "suggestion": s, "button": b}
                for a, s, b in self.alternative_actions
            ],
            "context": self.context,
            "preview": self.preview,
        }


@dataclass
class AutoPatch:
    """自动生成的补丁"""
    patch_id: str
    issue_id: str

    # 补丁内容
    original_text: str             # 原始文本
    patched_text: str             # 修复后的文本

    # 补丁位置
    section: str                  # 章节
    position: str                 # 位置描述

    # 补丁类型
    patch_type: str               # replace, insert, delete, wrap

    # 元数据
    confidence: float = 0.0        # 置信度
    generated_at: datetime = field(default_factory=datetime.now)
    generated_by: str = "smart_repair_engine"

    def to_dict(self) -> Dict:
        return {
            "patch_id": self.patch_id,
            "issue_id": self.issue_id,
            "original_text": self.original_text,
            "patched_text": self.patched_text,
            "section": self.section,
            "position": self.position,
            "patch_type": self.patch_type,
            "confidence": self.confidence,
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
        }


@dataclass
class RepairVerification:
    """修复验证结果"""
    issue_id: str
    repair_action: RepairAction
    success: bool
    message: str
    verified_value: Optional[Any] = None

    def to_dict(self) -> Dict:
        return {
            "issue_id": self.issue_id,
            "repair_action": self.repair_action.value,
            "success": self.success,
            "message": self.message,
            "verified_value": self.verified_value,
        }


@dataclass
class SmartRepairReport:
    """智能修复报告"""
    report_id: str
    project_name: str
    generated_at: datetime
    issues: List[RepairSuggestion] = field(default_factory=list)
    auto_patches: List[AutoPatch] = field(default_factory=list)
    repair_summary: Dict[str, int] = field(default_factory=dict)  # 各级别问题数量

    # 统计
    total_issues: int = 0
    auto_repairable: int = 0
    manual_required: int = 0

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "project_name": self.project_name,
            "generated_at": self.generated_at.isoformat(),
            "issues": [i.to_dict() for i in self.issues],
            "auto_patches": [p.to_dict() for p in self.auto_patches],
            "repair_summary": self.repair_summary,
            "total_issues": self.total_issues,
            "auto_repairable": self.auto_repairable,
            "manual_required": self.manual_required,
        }


class SmartRepairEngine:
    """
    智能修复引擎

    核心能力：
    1. 分析问题并生成分级修复建议
    2. 自动生成补丁（格式、编号等）
    3. 提供修复验证
    """

    def __init__(self):
        self.repair_rules: Dict[str, Dict] = {}
        self._load_repair_rules()

        # 数据源回调（用于自动获取数据）
        self.data_source_callback: Optional[Callable] = None

    def _load_repair_rules(self):
        """加载修复规则"""
        self.repair_rules = {
            "missing_project_name": {
                "level": IssueLevel.FATAL,
                "category": IssueCategory.DATA_MISSING,
                "action": RepairAction.MANUAL_FILL,
                "suggestion": "项目名称是报告的必填项，请提供完整的项目名称",
                "button_label": "直接填写",
                "alternative": [
                    (RepairAction.UPLOAD_DOCUMENT, "上传项目批复文件自动提取", "上传文档"),
                ]
            },
            "missing_monitoring_data": {
                "level": IssueLevel.WARNING,
                "category": IssueCategory.DATA_MISSING,
                "action": RepairAction.AUTO_GENERATE,
                "suggestion": "缺少最近一年的环境监测数据",
                "button_label": "自动获取公开数据",
                "alternative": [
                    (RepairAction.USE_DEFAULT, "使用区域平均值作为估算", "使用默认值"),
                    (RepairAction.MANUAL_FILL, "手动输入监测数据", "手动填写"),
                ]
            },
            "obsolete_standard": {
                "level": IssueLevel.ERROR,
                "category": IssueCategory.COMPLIANCE_ISSUE,
                "action": RepairAction.AUTO_REPLACE,
                "suggestion": "引用的标准已废止，需要更新为现行标准",
                "button_label": "智能替换为最新标准",
                "alternative": [
                    (RepairAction.MANUAL_FILL, "手动选择正确版本", "手动选择"),
                ]
            },
            "table_numbering_error": {
                "level": IssueLevel.FORMAT,
                "category": IssueCategory.FORMAT_ISSUE,
                "action": RepairAction.AUTO_REPLACE,
                "suggestion": "表编号不规范，应按章节编号",
                "button_label": "自动修正编号",
                "alternative": []
            },
            "missing_unit": {
                "level": IssueLevel.ERROR,
                "category": IssueCategory.FORMAT_ISSUE,
                "action": RepairAction.AUTO_REPLACE,
                "suggestion": "数据缺少单位",
                "button_label": "添加单位",
                "alternative": []
            },
            "source_strength_inconsistent": {
                "level": IssueLevel.ERROR,
                "category": IssueCategory.LOGIC_CONFLICT,
                "action": RepairAction.AUTO_GENERATE,
                "suggestion": "污染源强数据前后不一致",
                "button_label": "根据综合数据重新计算",
                "alternative": [
                    (RepairAction.MANUAL_FILL, "手动核对并修正", "手动修正"),
                ]
            },
        }

    def set_data_source_callback(self, callback: Callable):
        """设置数据源回调，用于自动获取数据"""
        self.data_source_callback = callback

    async def analyze_and_repair(
        self,
        report_id: str,
        project_name: str,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> SmartRepairReport:
        """
        分析问题并生成修复建议

        Args:
            report_id: 报告ID
            project_name: 项目名称
            report_content: 报告内容
            project_context: 项目上下文

        Returns:
            SmartRepairReport: 智能修复报告
        """
        repair_report = SmartRepairReport(
            report_id=report_id,
            project_name=project_name,
            generated_at=datetime.now()
        )

        # 1. 检测问题
        issues = await self._detect_issues(report_content, project_context)
        repair_report.issues = issues

        # 2. 生成分级统计
        repair_report.repair_summary = {
            "fatal": sum(1 for i in issues if i.issue_level == IssueLevel.FATAL),
            "error": sum(1 for i in issues if i.issue_level == IssueLevel.ERROR),
            "warning": sum(1 for i in issues if i.issue_level == IssueLevel.WARNING),
            "suggestion": sum(1 for i in issues if i.issue_level == IssueLevel.SUGGESTION),
            "format": sum(1 for i in issues if i.issue_level == IssueLevel.FORMAT),
        }

        repair_report.total_issues = len(issues)
        repair_report.auto_repairable = sum(
            1 for i in issues if i.primary_action in [
                RepairAction.AUTO_GENERATE,
                RepairAction.AUTO_REPLACE,
            ]
        )
        repair_report.manual_required = sum(
            1 for i in issues if i.primary_action in [
                RepairAction.MANUAL_FILL,
                RepairAction.UPLOAD_DOCUMENT,
            ]
        )

        # 3. 生成自动补丁
        for issue in issues:
            if issue.primary_action in [RepairAction.AUTO_REPLACE, RepairAction.AUTO_GENERATE]:
                patch = await self._generate_patch(issue, report_content, project_context)
                if patch:
                    repair_report.auto_patches.append(patch)

        return repair_report

    async def _detect_issues(
        self,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> List[RepairSuggestion]:
        """检测报告中的问题"""
        issues = []

        # 1. 检查必填字段
        basic_info = report_content.get('basic_info', {})
        if not basic_info.get('project_name'):
            issues.append(self._create_repair_suggestion(
                "missing_project_name",
                "项目名称未提供",
                {"location": "报告封面", "suggested_action": "提供完整项目名称"}
            ))

        # 2. 检查数据完整性
        monitoring = report_content.get('monitoring_data', {})
        if not monitoring.get('has_recent_data'):
            issues.append(self._create_repair_suggestion(
                "missing_monitoring_data",
                "缺少最近一年的环境监测数据",
                {
                    "data_type": "环境监测",
                    "suggested_action": "获取最近一年公开监测数据",
                    "location": "现状评价章节"
                }
            ))

        # 3. 检查标准引用
        standards = report_content.get('referenced_standards', [])
        for std in standards:
            code = std.get('code', '')
            if code in ['GB 3095-1996', 'HJ/T 2.2-1993']:
                issues.append(self._create_repair_suggestion(
                    "obsolete_standard",
                    f"引用的{code}已废止",
                    {
                        "current_standard": "GB 3095-2012" if "3095" in code else "HJ 2.2-2018",
                        "suggested_action": "更新为现行标准"
                    }
                ))

        # 4. 检查格式问题
        sections = report_content.get('sections', {})
        for section_name, content in sections.items():
            # 检查表编号
            table_issues = self._check_table_format(section_name, content)
            issues.extend(table_issues)

            # 检查单位
            unit_issues = self._check_unit_format(section_name, content)
            issues.extend(unit_issues)

        # 5. 检查逻辑一致性
        logic_issues = await self._check_logic_consistency(report_content)
        issues.extend(logic_issues)

        return issues

    def _create_repair_suggestion(
        self,
        issue_type: str,
        description: str,
        context: Dict[str, Any]
    ) -> RepairSuggestion:
        """创建修复建议"""
        rule = self.repair_rules.get(issue_type, {})

        return RepairSuggestion(
            issue_id=f"{issue_type}_{hashlib.md5(description.encode()).hexdigest()[:8]}",
            issue_description=description,
            issue_level=rule.get('level', IssueLevel.WARNING),
            category=rule.get('category', IssueCategory.DATA_MISSING),
            primary_action=rule.get('action', RepairAction.MANUAL_FILL),
            primary_suggestion=rule.get('suggestion', description),
            primary_button_label=rule.get('button_label', '修复'),
            alternative_actions=rule.get('alternative', []),
            context=context
        )

    def _check_table_format(
        self,
        section: str,
        content: str
    ) -> List[RepairSuggestion]:
        """检查表格格式问题"""
        issues = []

        # 匹配不规范的表编号，如"表1" 应为 "表3-1"
        matches = re.finditer(r'表\s*(\d+)\s*[：:]\s*', content)
        for match in matches:
            table_num = match.group(1)
            # 检查是否只有数字，没有章节前缀
            if re.match(r'^\d+$', table_num):
                issues.append(self._create_repair_suggestion(
                    "table_numbering_error",
                    f"表格编号'{table_num}'不规范，应按章节编号",
                    {
                        "section": section,
                        "current_number": table_num,
                        "suggested_action": "添加章节前缀"
                    }
                ))

        return issues

    def _check_unit_format(
        self,
        section: str,
        content: str
    ) -> List[RepairSuggestion]:
        """检查单位缺失问题"""
        issues = []

        # 匹配数值但缺少单位的情况
        # 例如 "排放量 100" 但应该是 "排放量 100 t/a"
        number_patterns = [
            (r'排放量\s+([0-9.]+)', '排放量', 't/a 或 kg/h'),
            (r'浓度\s+([0-9.]+)', '浓度', 'mg/m³ 或 μg/m³'),
            (r'排放速率\s+([0-9.]+)', '排放速率', 'g/s 或 kg/h'),
            (r'产生量\s+([0-9.]+)', '产生量', 't/a'),
        ]

        for pattern, param_name, expected_unit in number_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                value = match.group(1)
                # 检查后面是否有单位
                end_pos = match.end()
                if end_pos < len(content):
                    following_text = content[end_pos:end_pos+10]
                    if not re.search(r'(t/a|kg/h|g/s|mg/m³|μg/m³|m³/s)', following_text):
                        issues.append(self._create_repair_suggestion(
                            "missing_unit",
                            f"'{param_name}'数值{value}缺少单位",
                            {
                                "section": section,
                                "parameter": param_name,
                                "value": value,
                                "expected_unit": expected_unit,
                                "suggested_action": "添加单位"
                            }
                        ))

        return issues

    async def _check_logic_consistency(
        self,
        report_content: Dict[str, Any]
    ) -> List[RepairSuggestion]:
        """检查逻辑一致性问题"""
        issues = []

        # 检查污染源强的一致性
        source_data = report_content.get('source_strength', {})

        if source_data:
            vocs_production = source_data.get('vocs_production')  # 产生量
            vocs_emission = source_data.get('vocs_emission')  # 排放量

            if vocs_production and vocs_emission:
                # 检查是否符合物质守恒（排放量 <= 产生量）
                try:
                    prod_val = float(re.search(r'([0-9.]+)', str(vocs_production)).group(1))
                    emis_val = float(re.search(r'([0-9.]+)', str(vocs_emission)).group(1))

                    if emis_val > prod_val:
                        issues.append(self._create_repair_suggestion(
                            "source_strength_inconsistent",
                            f"VOCs产生量({prod_val}t/a)小于排放量({emis_val}t/a)，违反物质守恒",
                            {
                                "vocs_production": prod_val,
                                "vocs_emission": emis_val,
                                "suggested_action": "重新核算源强数据"
                            }
                        ))
                except:
                    pass

        return issues

    async def _generate_patch(
        self,
        issue: RepairSuggestion,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> Optional[AutoPatch]:
        """为问题生成自动补丁"""
        section = issue.context.get('section', '未知章节')
        original_text = ""

        if issue.issue_id == "table_numbering_error":
            # 生成表格编号补丁
            current = issue.context.get('current_number', '')
            chapter_prefix = section.replace('第', '').replace('章', '')

            # 简单的章节编号提取
            chapter_num = re.search(r'(\d+)', section)
            if chapter_num:
                chapter_prefix = chapter_num.group(1)

            new_number = f"表{chapter_prefix}-{current}"

            original_text = f"表 {current}"
            patched_text = new_number

            return AutoPatch(
                patch_id=f"patch_{hashlib.md5((issue.issue_id + original_text).encode()).hexdigest()[:8]}",
                issue_id=issue.issue_id,
                original_text=original_text,
                patched_text=patched_text,
                section=section,
                position="表格标题",
                patch_type="replace",
                confidence=0.95
            )

        elif issue.issue_id == "missing_unit":
            # 生成单位补丁
            param = issue.context.get('parameter', '')
            value = issue.context.get('value', '')
            expected_unit = issue.context.get('expected_unit', '')

            # 找到原始文本位置
            original_text = f"{value}"
            patched_text = f"{value} {expected_unit.split(' 或 ')[0]}"

            return AutoPatch(
                patch_id=f"patch_{hashlib.md5((issue.issue_id + original_text).encode()).hexdigest()[:8]}",
                issue_id=issue.issue_id,
                original_text=original_text,
                patched_text=patched_text,
                section=section,
                position=f"{param}数值后",
                patch_type="replace",
                confidence=0.90
            )

        elif issue.issue_id == "obsolete_standard":
            # 生成标准替换补丁
            current_std = issue.issue_description
            new_std = issue.context.get('current_standard', '')

            return AutoPatch(
                patch_id=f"patch_{hashlib.md5((issue.issue_id + current_std).encode()).hexdigest()[:8]}",
                issue_id=issue.issue_id,
                original_text=current_std,
                patched_text=new_std,
                section="标准引用章节",
                position="标准编号",
                patch_type="replace",
                confidence=0.95
            )

        elif issue.issue_id == "missing_monitoring_data":
            # 尝试从数据源获取数据
            if self.data_source_callback:
                try:
                    data = await self.data_source_callback(
                        "monitoring_data",
                        project_context
                    )
                    if data:
                        # 生成监测数据章节补丁
                        original_text = "缺少监测数据"
                        patched_text = f"根据{project_context.get('location', '')}环境监测站{data.get('year', '2024')}年监测数据..."

                        return AutoPatch(
                            patch_id=f"patch_{hashlib.md5((issue.issue_id + 'monitoring').encode()).hexdigest()[:8]}",
                            issue_id=issue.issue_id,
                            original_text=original_text,
                            patched_text=patched_text,
                            section="环境质量现状",
                            position="监测数据描述段",
                            patch_type="replace",
                            confidence=0.75
                        )
                except:
                    pass

        return None

    async def apply_patch(
        self,
        patch: AutoPatch,
        report_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用补丁到报告内容

        Args:
            patch: 补丁
            report_content: 原始报告内容

        Returns:
            Dict: 应用补丁后的报告内容
        """
        # 深拷贝以避免修改原始内容
        updated_content = json.loads(json.dumps(report_content))

        # 根据补丁类型应用修改
        if patch.patch_type == "replace":
            # 在对应章节中替换文本
            if 'sections' in updated_content:
                for section_name, content in updated_content['sections'].items():
                    if patch.section in section_name or section_name in patch.section:
                        updated_content['sections'][section_name] = content.replace(
                            patch.original_text,
                            patch.patched_text
                        )

        return updated_content

    async def verify_repair(
        self,
        issue: RepairSuggestion,
        repaired_value: Any,
        report_content: Dict[str, Any]
    ) -> RepairVerification:
        """
        验证修复是否有效

        Args:
            issue: 原始问题
            repaired_value: 修复后的值
            report_content: 报告内容

        Returns:
            RepairVerification: 验证结果
        """
        # 根据问题类型进行验证
        if issue.issue_id == "missing_project_name":
            success = bool(repaired_value and len(repaired_value) > 0)
            return RepairVerification(
                issue_id=issue.issue_id,
                repair_action=RepairAction.MANUAL_FILL,
                success=success,
                message="项目名称已填写" if success else "项目名称仍为空"
            )

        elif issue.issue_id == "obsolete_standard":
            # 检查是否替换为现行标准
            success = "2012" in str(repaired_value) or "2018" in str(repaired_value)
            return RepairVerification(
                issue_id=issue.issue_id,
                repair_action=RepairAction.AUTO_REPLACE,
                success=success,
                message="标准已更新" if success else "标准仍为旧版"
            )

        elif issue.issue_id == "missing_monitoring_data":
            # 检查是否有监测数据
            success = bool(report_content.get('monitoring_data', {}).get('has_recent_data'))
            return RepairVerification(
                issue_id=issue.issue_id,
                repair_action=RepairAction.AUTO_GENERATE,
                success=success,
                message="监测数据已补充" if success else "监测数据仍缺失",
                verified_value=report_content.get('monitoring_data')
            )

        else:
            return RepairVerification(
                issue_id=issue.issue_id,
                repair_action=issue.primary_action,
                success=True,
                message="修复完成"
            )


# 全局实例
_repair_engine_instance: Optional[SmartRepairEngine] = None


def get_repair_engine() -> SmartRepairEngine:
    """获取智能修复引擎全局实例"""
    global _repair_engine_instance
    if _repair_engine_instance is None:
        _repair_engine_instance = SmartRepairEngine()
    return _repair_engine_instance


async def analyze_and_repair_async(
    report_id: str,
    project_name: str,
    report_content: Dict[str, Any],
    project_context: Dict[str, Any]
) -> SmartRepairReport:
    """异步执行智能修复的便捷函数"""
    engine = get_repair_engine()
    return await engine.analyze_and_repair(
        report_id, project_name, report_content, project_context
    )


async def apply_patch_async(
    patch: AutoPatch,
    report_content: Dict[str, Any]
) -> Dict[str, Any]:
    """异步应用补丁的便捷函数"""
    engine = get_repair_engine()
    return await engine.apply_patch(patch, report_content)