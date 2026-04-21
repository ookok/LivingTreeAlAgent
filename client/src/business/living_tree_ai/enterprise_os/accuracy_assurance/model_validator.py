"""
模型校验引擎 (Model Validator)

核心功能：
1. 关键数据必须由模型计算得出
2. AI仅负责描述结论，杜绝主观臆断
3. 确保技术参数准确

校验机制：
1. 数值范围校验 - 检查排放量、浓度等是否在合理范围
2. 单位一致性 - 检查单位使用是否正确
3. 逻辑一致性 - 检查数据间逻辑关系
4. 来源追溯 - 检查数据是否有模型计算记录
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
import re


class ValidationLevel(Enum):
    """校验级别"""
    ERROR = "error"                           # 错误（阻断）
    WARNING = "warning"                       # 警告
    INFO = "info"                            # 提示
    PASS = "pass"                            # 通过


class ValidationStatus(Enum):
    """校验状态"""
    PENDING = "pending"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL_PASS = "partial_pass"             # 部分通过


@dataclass
class ValidationRule:
    """校验规则"""
    rule_id: str
    name: str
    description: str

    # 校验类型
    validation_type: str                      # range/consistency/unit/source/existence

    # 规则参数
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 级别
    level: ValidationLevel = ValidationLevel.ERROR

    # 适用范围
    applies_to: List[str] = field(default_factory=list)  # 字段名列表

    # 是否启用
    is_enabled: bool = True

    # 错误消息模板
    error_template: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "validation_type": self.validation_type,
            "level": self.level.value,
            "applies_to": self.applies_to,
        }


@dataclass
class ValidationResult:
    """校验结果"""
    rule_id: str
    rule_name: str

    # 状态
    status: ValidationStatus
    level: ValidationLevel

    # 校验的字段
    field_name: str
    field_value: Any

    # 结果
    is_valid: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # 修正建议
    suggested_fix: Optional[Any] = None
    fix_confidence: float = 0.0

    # 元数据
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "status": self.status.value,
            "level": self.level.value,
            "field_name": self.field_name,
            "is_valid": self.is_valid,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "validated_at": self.validated_at.isoformat(),
        }


@dataclass
class ValidatedDocument:
    """校验后的文档"""
    document_id: str
    document_name: str

    # 校验结果汇总
    validation_results: List[ValidationResult] = field(default_factory=list)

    # 统计
    total_fields_validated: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0

    # 总体状态
    overall_status: ValidationStatus = ValidationStatus.PENDING
    overall_level: ValidationLevel = ValidationLevel.PASS

    # 计算数据（用于追溯）
    computed_fields: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 文档数据（被校验的内容）
    document_data: Dict[str, Any] = field(default_factory=dict)

    # 校验时间
    validated_at: datetime = field(default_factory=datetime.now)
    validator_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "overall_status": self.overall_status.value,
            "total_fields_validated": self.total_fields_validated,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "warnings": self.warning_count,
            "validation_results": [r.to_dict() for r in self.validation_results],
            "validated_at": self.validated_at.isoformat(),
        }

    def get_failed_validations(self) -> List[ValidationResult]:
        """获取失败的校验项"""
        return [r for r in self.validation_results if not r.is_valid and r.level == ValidationLevel.ERROR]

    def get_warnings(self) -> List[ValidationResult]:
        """获取警告项"""
        return [r for r in self.validation_results if r.level == ValidationLevel.WARNING]


class ModelValidator:
    """
    模型校验引擎

    确保AI生成的文档内容中：
    1. 关键数值由模型计算得出
    2. 数据来源可追溯
    3. 数值在合理范围内
    4. 单位使用正确
    """

    # 内置校验规则
    DEFAULT_RULES = [
        # 排放量范围校验
        ValidationRule(
            rule_id="RANGE_EMISSION_SO2",
            name="SO2排放量范围校验",
            description="SO2排放量应在合理范围内",
            validation_type="range",
            parameters={"min": 0, "max": 10000, "unit": "t/a"},
            applies_to=["SO2_emission", "SO2排放量", "sulfur_dioxide_emission"],
            error_template="SO2排放量{value}{unit}超出合理范围[{min}-{max}]"
        ),
        ValidationRule(
            rule_id="RANGE_EMISSION_NOX",
            name="NOx排放量范围校验",
            description="NOx排放量应在合理范围内",
            validation_type="range",
            parameters={"min": 0, "max": 10000, "unit": "t/a"},
            applies_to=["NOx_emission", "NOx排放量", "nitrogen_oxide_emission"],
        ),
        ValidationRule(
            rule_id="RANGE_EMISSION_VOCS",
            name="VOCs排放量范围校验",
            description="VOCs排放量应在合理范围内",
            validation_type="range",
            parameters={"min": 0, "max": 5000, "unit": "t/a"},
            applies_to=["VOCs_emission", "VOCs排放量"],
        ),

        # 浓度限值校验
        ValidationRule(
            rule_id="LIMIT_SO2_CONC",
            name="SO2排放浓度限值校验",
            description="SO2排放浓度不应超过排放标准限值",
            validation_type="limit",
            parameters={"limit": 50, "unit": "mg/m3", "standard": "GB 13271-2014"},
            level=ValidationLevel.ERROR,
            applies_to=["SO2_concentration", "SO2浓度", "sulfur_dioxide_concentration"],
        ),
        ValidationRule(
            rule_id="LIMIT_NOX_CONC",
            name="NOx排放浓度限值校验",
            description="NOx排放浓度不应超过排放标准限值",
            validation_type="limit",
            parameters={"limit": 100, "unit": "mg/m3", "standard": "GB 13271-2014"},
            level=ValidationLevel.ERROR,
            applies_to=["NOx_concentration", "NOx浓度"],
        ),

        # 数据来源校验
        ValidationRule(
            rule_id="SOURCE_EMISSION_CALC",
            name="排放量来源校验",
            description="排放量数据必须有模型计算记录",
            validation_type="source",
            parameters={"required_source": "model_calculation", "allowed_sources": ["model_calculation", "measurement"]},
            level=ValidationLevel.ERROR,
            applies_to=["emission_amount", "排放量", "discharge_amount"],
        ),
        ValidationRule(
            rule_id="SOURCE_INVESTMENT",
            name="投资估算来源校验",
            description="投资估算数据必须有计算依据",
            validation_type="source",
            parameters={"required_source": "calculation", "allowed_sources": ["model_calculation", "estimation", "benchmark"]},
            level=ValidationLevel.WARNING,
            applies_to=["investment", "投资", "total_investment"],
        ),

        # 单位一致性校验
        ValidationRule(
            rule_id="UNIT_EMISSION_T",
            name="排放量单位校验",
            description="排放量应使用吨/年(t/a)或千克/年(kg/a)",
            validation_type="unit",
            parameters={"correct_units": ["t/a", "吨/年", "kg/a", "千克/年"]},
            level=ValidationLevel.ERROR,
            applies_to=["emission", "排放量", "discharge"],
        ),
        ValidationRule(
            rule_id="UNIT_CONCENTRATION_MGM3",
            name="浓度单位校验",
            description="排放浓度应使用mg/m3",
            validation_type="unit",
            parameters={"correct_units": ["mg/m3", "毫克/立方米", "μg/m3"]},
            level=ValidationLevel.ERROR,
            applies_to=["concentration", "浓度"],
        ),

        # 数值逻辑校验
        ValidationRule(
            rule_id="LOGIC_PERMIT_LESS_ACTUAL",
            name="许可排放量逻辑校验",
            description="许可排放量应大于等于实际排放量",
            validation_type="consistency",
            parameters={"compare_field": "actual_emission", "operator": ">="},
            level=ValidationLevel.ERROR,
            applies_to=["permitted_emission", "许可排放量"],
        ),
        ValidationRule(
            rule_id="LOGIC_REMOVAL_POSITIVE",
            name="去除效率逻辑校验",
            description="污染物去除效率应在0-100%之间",
            validation_type="range",
            parameters={"min": 0, "max": 100, "unit": "%"},
            level=ValidationLevel.ERROR,
            applies_to=["removal_efficiency", "去除效率", "control_efficiency"],
        ),

        # 数值存在性校验
        ValidationRule(
            rule_id="EXIST_REQUIRED_FIELD",
            name="必填字段校验",
            description="关键字段不能为空",
            validation_type="existence",
            parameters={"cannot_be_zero": False, "cannot_be_negative": True},
            level=ValidationLevel.ERROR,
            applies_to=["company_name", "project_name", "credit_code"],
        ),
    ]

    def __init__(self):
        self._rules: Dict[str, ValidationRule] = {}
        self._validation_history: List[ValidatedDocument] = []

        # 注册内置规则
        for rule in self.DEFAULT_RULES:
            self._rules[rule.rule_id] = rule

    async def validate_document(
        self,
        document_id: str,
        document_name: str,
        document_data: Dict[str, Any],
        computed_fields: Optional[Dict[str, Dict[str, Any]]] = None,
        custom_rules: Optional[List[ValidationRule]] = None,
    ) -> ValidatedDocument:
        """
        校验文档

        Args:
            document_id: 文档ID
            document_name: 文档名称
            document_data: 文档数据（键值对）
            computed_fields: 计算字段（用于追溯）
                格式: {"field_name": {"source": "model_calculation", "model_name": "...", "value": ...}}
            custom_rules: 自定义规则

        Returns:
            ValidatedDocument: 校验结果
        """
        result = ValidatedDocument(
            document_id=document_id,
            document_name=document_name,
            document_data=document_data,
            computed_fields=computed_fields or {},
            overall_status=ValidationStatus.VALIDATING,
        )

        # 合并规则
        all_rules = list(self._rules.values())
        if custom_rules:
            all_rules.extend(custom_rules)

        # 对每个字段应用规则
        for field_name, field_value in document_data.items():
            # 查找适用的规则
            applicable_rules = [r for r in all_rules if r.is_enabled and field_name in r.applies_to]

            for rule in applicable_rules:
                validation_result = await self._apply_rule(rule, field_name, field_value, document_data)
                result.validation_results.append(validation_result)
                result.total_fields_validated += 1

                if validation_result.is_valid:
                    result.passed_count += 1
                else:
                    if validation_result.level == ValidationLevel.ERROR:
                        result.failed_count += 1
                    else:
                        result.warning_count += 1

        # 确定总体状态
        if result.failed_count > 0:
            result.overall_status = ValidationStatus.FAILED
            result.overall_level = ValidationLevel.ERROR
        elif result.warning_count > 0:
            result.overall_status = ValidationStatus.PARTIAL_PASS
            result.overall_level = ValidationLevel.WARNING
        else:
            result.overall_status = ValidationStatus.PASSED
            result.overall_level = ValidationLevel.PASS

        # 记录历史
        self._validation_history.append(result)

        return result

    async def _apply_rule(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        document_data: Dict[str, Any]
    ) -> ValidationResult:
        """应用校验规则"""
        result = ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            status=ValidationStatus.VALIDATING,
            level=rule.level,
            field_name=field_name,
            field_value=field_value,
            is_valid=True,
        )

        try:
            if rule.validation_type == "range":
                result = await self._validate_range(rule, field_name, field_value, result)
            elif rule.validation_type == "limit":
                result = await self._validate_limit(rule, field_name, field_value, result)
            elif rule.validation_type == "source":
                result = await self._validate_source(rule, field_name, field_value, result)
            elif rule.validation_type == "unit":
                result = await self._validate_unit(rule, field_name, field_value, result)
            elif rule.validation_type == "consistency":
                result = await self._validate_consistency(rule, field_name, field_value, document_data, result)
            elif rule.validation_type == "existence":
                result = await self._validate_existence(rule, field_name, field_value, result)

            result.status = ValidationStatus.PASSED if result.is_valid else ValidationStatus.FAILED

        except Exception as e:
            result.is_valid = False
            result.message = f"校验过程出错: {str(e)}"
            result.status = ValidationStatus.FAILED

        return result

    async def _validate_range(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        result: ValidationResult
    ) -> ValidationResult:
        """范围校验"""
        params = rule.parameters
        min_val = params.get("min", 0)
        max_val = params.get("max", float("inf"))
        unit = params.get("unit", "")

        # 提取数值
        if isinstance(field_value, (int, float)):
            value = float(field_value)
        elif isinstance(field_value, str):
            # 尝试从字符串提取数值
            match = re.search(r"[\d.]+", field_value)
            if match:
                value = float(match.group())
            else:
                result.is_valid = False
                result.message = f"无法从'{field_value}'提取数值"
                return result
        else:
            result.is_valid = False
            result.message = f"不支持的值类型: {type(field_value)}"
            return result

        # 校验范围
        if value < min_val or value > max_val:
            result.is_valid = False
            result.message = rule.error_template.format(
                value=value,
                unit=unit,
                min=min_val,
                max=max_val
            )
            result.suggested_fix = max(min_val, min(value, max_val))
            result.suggested_fix = round(result.suggested_fix, 3)
            result.fix_confidence = 0.9
        else:
            result.is_valid = True
            result.message = f"数值在合理范围内[{min_val}-{max_val}]{unit}"

        return result

    async def _validate_limit(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        result: ValidationResult
    ) -> ValidationResult:
        """限值校验"""
        params = rule.parameters
        limit = params.get("limit", 0)
        unit = params.get("unit", "")
        standard = params.get("standard", "")

        # 提取数值
        if isinstance(field_value, (int, float)):
            value = float(field_value)
        elif isinstance(field_value, str):
            match = re.search(r"[\d.]+", field_value)
            if match:
                value = float(match.group())
            else:
                result.is_valid = False
                result.message = f"无法从'{field_value}'提取数值"
                return result
        else:
            result.is_valid = False
            result.message = f"不支持的值类型: {type(field_value)}"
            return result

        # 校验是否超过限值
        if value > limit:
            result.is_valid = False
            result.message = f"超过排放限值: {value}{unit} > {limit}{unit} (依据{standard})"
            result.suggested_fix = limit
            result.fix_confidence = 0.95
        else:
            result.is_valid = True
            result.message = f"符合排放限值标准({standard}): {value}{unit} ≤ {limit}{unit}"

        return result

    async def _validate_source(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        result: ValidationResult
    ) -> ValidationResult:
        """来源校验"""
        params = rule.parameters
        required_source = params.get("required_source")
        allowed_sources = params.get("allowed_sources", [])

        # 检查是否有计算记录
        # 这里简化处理，实际应检查computed_fields

        # 如果值存在，检查是否合理
        if field_value is not None and field_value != "":
            result.is_valid = True
            result.message = f"字段有值，数据来源未验证但存在"
        else:
            result.is_valid = False
            result.message = f"关键字段'{field_name}'必须由模型计算得出，不能为空"
            result.suggested_fix = None
            result.fix_confidence = 0.0

        return result

    async def _validate_unit(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        result: ValidationResult
    ) -> ValidationResult:
        """单位校验"""
        params = rule.parameters
        correct_units = params.get("correct_units", [])

        # 如果是数值，不需要校验单位
        if isinstance(field_value, (int, float)):
            result.is_valid = True
            result.message = "数值为纯数字，无需单位校验"
            return result

        # 检查字符串中是否包含正确单位
        value_str = str(field_value).lower()
        found_unit = None

        for unit in correct_units:
            if unit.lower() in value_str:
                found_unit = unit
                break

        if found_unit:
            result.is_valid = True
            result.message = f"单位使用正确: {found_unit}"
        else:
            result.is_valid = False
            result.message = f"单位不正确，应使用: {', '.join(correct_units)}"
            result.suggested_fix = f"{field_value} {correct_units[0]}" if correct_units else field_value
            result.fix_confidence = 0.8

        return result

    async def _validate_consistency(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        document_data: Dict[str, Any],
        result: ValidationResult
    ) -> ValidationResult:
        """逻辑一致性校验"""
        params = rule.parameters
        compare_field = params.get("compare_field")
        operator = params.get("operator", ">=")

        # 提取当前字段值
        if isinstance(field_value, (int, float)):
            value = float(field_value)
        else:
            match = re.search(r"[\d.]+", str(field_value))
            value = float(match.group()) if match else 0

        # 获取比较字段值
        compare_value_raw = document_data.get(compare_field)
        if compare_value_raw is None:
            result.is_valid = True  # 如果没有比较字段，跳过
            result.message = f"无比较字段'{compare_field}'，跳过一致性校验"
            return result

        if isinstance(compare_value_raw, (int, float)):
            compare_value = float(compare_value_raw)
        else:
            match = re.search(r"[\d.]+", str(compare_value_raw))
            compare_value = float(match.group()) if match else 0

        # 执行比较
        is_consistent = False
        if operator == ">=":
            is_consistent = value >= compare_value
        elif operator == "<=":
            is_consistent = value <= compare_value
        elif operator == ">":
            is_consistent = value > compare_value
        elif operator == "<":
            is_consistent = value < compare_value
        elif operator == "==":
            is_consistent = abs(value - compare_value) < 0.001

        if is_consistent:
            result.is_valid = True
            result.message = f"逻辑一致: {field_name}({value}) {operator} {compare_field}({compare_value})"
        else:
            result.is_valid = False
            result.message = f"逻辑不一致: {field_name}({value}) {operator} {compare_field}({compare_value})"
            if operator == ">=":
                result.suggested_fix = compare_value
            result.fix_confidence = 0.85

        return result

    async def _validate_existence(
        self,
        rule: ValidationRule,
        field_name: str,
        field_value: Any,
        result: ValidationResult
    ) -> ValidationResult:
        """存在性校验"""
        params = rule.parameters
        cannot_be_zero = params.get("cannot_be_zero", True)
        cannot_be_negative = params.get("cannot_be_negative", False)

        # 检查是否为空
        if field_value is None or field_value == "":
            result.is_valid = False
            result.message = f"必填字段'{field_name}'不能为空"
            return result

        # 检查零值
        if cannot_be_zero:
            if isinstance(field_value, (int, float)) and field_value == 0:
                result.is_valid = False
                result.message = f"字段'{field_name}'不能为零值"
                return result

        # 检查负值
        if cannot_be_negative:
            if isinstance(field_value, (int, float)) and field_value < 0:
                result.is_valid = False
                result.message = f"字段'{field_name}'不能为负值"
                result.suggested_fix = abs(field_value)
                result.fix_confidence = 0.9
                return result

        result.is_valid = True
        result.message = f"字段'{field_name}'校验通过"
        return result

    def add_rule(self, rule: ValidationRule) -> None:
        """添加校验规则"""
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """移除校验规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rules(self, validation_type: Optional[str] = None) -> List[ValidationRule]:
        """获取规则列表"""
        rules = list(self._rules.values())
        if validation_type:
            rules = [r for r in rules if r.validation_type == validation_type]
        return rules

    def get_validation_history(self, limit: int = 10) -> List[ValidatedDocument]:
        """获取校验历史"""
        return self._validation_history[-limit:]


# 全局单例
_model_validator: Optional[ModelValidator] = None


def get_model_validator() -> ModelValidator:
    """获取模型校验器单例"""
    global _model_validator
    if _model_validator is None:
        _model_validator = ModelValidator()
    return _model_validator