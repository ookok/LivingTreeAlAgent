"""
表单适配器引擎

将企业Profile数据映射到政府网站表单字段。

核心功能：
1. 表单字段自动识别
2. 字段智能映射
3. 数据格式转换
4. 映射规则管理
"""

import json
import re
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class FieldType(Enum):
    """表单字段类型"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    FILE = "file"
    TABLE = "table"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"


class MappingQuality(Enum):
    """映射质量"""
    PERFECT = "perfect"          # 100%匹配
    HIGH = "high"               # >80%
    MEDIUM = "medium"           # 50-80%
    LOW = "low"                 # <50%
    UNKNOWN = "unknown"         # 未知


@dataclass
class FormField:
    """表单字段"""
    field_id: str
    name: str                          # 原始字段名
    label: str                         # 显示标签
    field_type: FieldType
    required: bool = False
    max_length: int = 0
    min_value: float = 0
    max_value: float = 0
    options: List[Dict] = field(default_factory=list)  # [{"value": "A", "label": "选项A"}]
    default_value: Any = None
    placeholder: str = ""
    hint: str = ""
    validators: List[str] = field(default_factory=list)
    css_selector: str = ""
    xpath: str = ""
    parent_field: str = ""


@dataclass
class FieldMapping:
    """字段映射"""
    mapping_id: str
    profile_field: str
    form_field_id: str
    form_system: str
    transform: str = ""
    default_value: Any = None
    reverse_transform: str = ""
    quality: MappingQuality = MappingQuality.UNKNOWN
    confidence: float = 0.0
    usage_count: int = 0
    success_count: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None


@dataclass
class MappingRule:
    """映射规则"""
    rule_id: str
    name: str
    description: str = ""
    source_fields: List[str] = field(default_factory=list)
    target_field: str = ""
    transform_func: str = ""
    condition: str = ""
    enabled: bool = True


# ==================== 内置字段映射模板 ====================

BUILTIN_MAPPINGS = {
    "国家税务总局电子税务局": [
        {
            "profile_field": "identity_info.credit_code",
            "form_field": "tyshxydm",
            "label": "统一社会信用代码",
            "transform": "uppercase",
            "quality": "perfect"
        },
        {
            "profile_field": "basic_info.company_name",
            "form_field": "nsrmc",
            "label": "纳税人名称",
            "transform": "none",
            "quality": "perfect"
        },
        {
            "profile_field": "identity_info.legal_person",
            "form_field": "fddbr",
            "label": "法定代表人",
            "transform": "none",
            "quality": "perfect"
        },
        {
            "profile_field": "tax_info.tax_id",
            "form_field": "nsrsbh",
            "label": "纳税人识别号",
            "transform": "none",
            "quality": "perfect"
        },
        {
            "profile_field": "basic_info.registered_capital",
            "form_field": "zczb",
            "label": "注册资本",
            "transform": "currency_yuan",
            "quality": "high"
        }
    ],
    "全国排污许可管理信息平台": [
        {
            "profile_field": "identity_info.credit_code",
            "form_field": "tyshxydm",
            "label": "统一社会信用代码",
            "transform": "uppercase",
            "quality": "perfect"
        },
        {
            "profile_field": "basic_info.company_name",
            "form_field": "dwmc",
            "label": "单位名称",
            "transform": "none",
            "quality": "perfect"
        }
    ]
}


# ==================== 转换函数库 ====================

class TransformFunctions:
    """内置转换函数"""

    @staticmethod
    def uppercase(value: str) -> str:
        return str(value).upper() if value else ""

    @staticmethod
    def lowercase(value: str) -> str:
        return str(value).lower() if value else ""

    @staticmethod
    def currency_yuan(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except:
            return "0.00"

    @staticmethod
    def currency_wan(value: Any) -> str:
        try:
            return f"{float(value) / 10000:.2f}"
        except:
            return "0.00"

    @staticmethod
    def date_format(value: Any, format_str: str = "%Y-%m-%d") -> str:
        if isinstance(value, datetime):
            return value.strftime(format_str)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                return dt.strftime(format_str)
            except:
                return value
        return ""

    @staticmethod
    def address_full(address_dict: Dict) -> str:
        if not address_dict:
            return ""
        parts = []
        for key in ["province", "city", "district", "street", "detail"]:
            if key in address_dict and address_dict[key]:
                parts.append(address_dict[key])
        return "".join(parts)

    @staticmethod
    def facilities_to_table(facilities: List[Dict]) -> List[List[str]]:
        if not facilities:
            return []
        result = []
        for f in facilities:
            result.append([
                f.get("name", ""),
                f.get("model", ""),
                f.get("quantity", ""),
                f.get("capacity", "")
            ])
        return result

    @staticmethod
    def percentage_to_decimal(value: Any) -> str:
        try:
            if isinstance(value, str) and "%" in value:
                value = value.replace("%", "")
            return f"{float(value) / 100:.4f}"
        except:
            return "0.0000"

    @staticmethod
    def phone_format(value: str) -> str:
        if not value:
            return ""
        digits = re.sub(r"\D", "", str(value))
        if len(digits) == 11:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return value


# ==================== 表单适配器引擎 ====================

class FormAdapterEngine:
    """
    表单适配器引擎

    核心功能：
    1. 注册和管理表单模板
    2. 管理字段映射规则
    3. 执行数据映射
    4. 学习新的映射关系
    """

    def __init__(self):
        self._form_templates: Dict[str, Dict] = {}
        self._mappings: Dict[str, List[FieldMapping]] = {}
        self._rules: Dict[str, List[MappingRule]] = {}

        self._transforms: Dict[str, Callable] = {
            "uppercase": TransformFunctions.uppercase,
            "lowercase": TransformFunctions.lowercase,
            "currency_yuan": TransformFunctions.currency_yuan,
            "currency_wan": TransformFunctions.currency_wan,
            "date_format": TransformFunctions.date_format,
            "address_full": TransformFunctions.address_full,
            "facilities_to_table": TransformFunctions.facilities_to_table,
            "percentage_to_decimal": TransformFunctions.percentage_to_decimal,
            "phone_format": TransformFunctions.phone_format,
        }

        self._load_builtin_mappings()

    def _load_builtin_mappings(self):
        """加载内置映射"""
        for system_name, mappings in BUILTIN_MAPPINGS.items():
            for m in mappings:
                self.add_mapping(
                    system_name=system_name,
                    profile_field=m["profile_field"],
                    form_field_id=m["form_field"],
                    label=m.get("label", ""),
                    transform=m.get("transform", "none"),
                    quality=MappingQuality[m["quality"].upper()]
                )

    def register_form_template(
        self,
        system_name: str,
        form_id: str,
        fields: List[FormField],
        metadata: Dict = None
    ):
        """注册表单模板"""
        if system_name not in self._form_templates:
            self._form_templates[system_name] = {}

        self._form_templates[system_name][form_id] = {
            "fields": fields,
            "metadata": metadata or {},
            "registered_at": datetime.now()
        }

    def add_mapping(
        self,
        system_name: str,
        profile_field: str,
        form_field_id: str,
        label: str = "",
        transform: str = "none",
        quality: MappingQuality = MappingQuality.UNKNOWN,
        confidence: float = 0.0
    ) -> str:
        """添加字段映射"""
        mapping_id = self._generate_mapping_id(system_name, form_field_id)

        mapping = FieldMapping(
            mapping_id=mapping_id,
            profile_field=profile_field,
            form_field_id=form_field_id,
            form_system=system_name,
            transform=transform,
            quality=quality,
            confidence=confidence
        )

        if system_name not in self._mappings:
            self._mappings[system_name] = []
        self._mappings[system_name].append(mapping)

        return mapping_id

    def add_mapping_rule(
        self,
        system_name: str,
        name: str,
        source_fields: List[str],
        target_field: str,
        transform_func: str,
        condition: str = ""
    ) -> str:
        """添加映射规则"""
        rule_id = hashlib.md5(
            f"{system_name}:{name}:{time.time()}".encode()
        ).hexdigest()[:12]

        rule = MappingRule(
            rule_id=rule_id,
            name=name,
            source_fields=source_fields,
            target_field=target_field,
            transform_func=transform_func,
            condition=condition
        )

        if system_name not in self._rules:
            self._rules[system_name] = []
        self._rules[system_name].append(rule)

        return rule_id

    async def adapt_form(
        self,
        system_name: str,
        form_id: str,
        profile_data: Dict
    ) -> Dict[str, Any]:
        """执行表单适配"""
        form_template = self._form_templates.get(system_name, {}).get(form_id)
        if not form_template:
            return {
                "filled_fields": {},
                "missing_fields": [],
                "low_confidence": [],
                "mapping_results": [],
                "error": f"Form template not found: {system_name}/{form_id}"
            }

        mappings = self._mappings.get(system_name, [])
        mapping_dict = {m.form_field_id: m for m in mappings}

        filled_fields = {}
        missing_fields = []
        low_confidence = []
        mapping_results = []

        for field in form_template["fields"]:
            field_id = field.field_id
            mapping = mapping_dict.get(field_id)

            if not mapping:
                mapping = await self._auto_match_field(system_name, field, profile_data)

            if mapping:
                value = self._get_nested_value(profile_data, mapping.profile_field)

                if value is not None:
                    if mapping.transform and mapping.transform != "none":
                        value = self._apply_transform(mapping.transform, value)

                    filled_fields[field_id] = {
                        "value": value,
                        "label": field.label,
                        "confidence": mapping.confidence,
                        "quality": mapping.quality.value
                    }

                    mapping_results.append({
                        "field_id": field_id,
                        "profile_field": mapping.profile_field,
                        "status": "filled",
                        "confidence": mapping.confidence
                    })

                    mapping.usage_count += 1
                    mapping.last_used = datetime.now()

                    if mapping.confidence < 0.6:
                        low_confidence.append({
                            "field_id": field_id,
                            "label": field.label,
                            "confidence": mapping.confidence
                        })
                else:
                    missing_fields.append({
                        "field_id": field_id,
                        "label": field.label,
                        "profile_field": mapping.profile_field
                    })
            else:
                missing_fields.append({
                    "field_id": field_id,
                    "label": field.label,
                    "profile_field": None
                })

        return {
            "filled_fields": filled_fields,
            "missing_fields": missing_fields,
            "low_confidence": low_confidence,
            "mapping_results": mapping_results,
            "fill_rate": len(filled_fields) / len(form_template["fields"]) if form_template["fields"] else 0
        }

    async def _auto_match_field(
        self,
        system_name: str,
        field: FormField,
        profile_data: Dict
    ) -> Optional[FieldMapping]:
        """自动匹配字段"""
        label_keywords = {
            "信用代码": ["credit_code", "tyshxydm"],
            "名称": ["company_name", "nsrmc", "dwmc"],
            "法人": ["legal_person", "fddbr"],
            "地址": ["address", "dzdz"],
            "注册资本": ["registered_capital", "zczb"],
            "电话": ["phone", "lxdh"],
        }

        for keyword, profile_keys in label_keywords.items():
            if keyword in field.label:
                for key in profile_keys:
                    value = self._get_nested_value(profile_data, key)
                    if value is not None:
                        return FieldMapping(
                            mapping_id=self._generate_mapping_id(system_name, field.field_id),
                            profile_field=key,
                            form_field_id=field.field_id,
                            form_system=system_name,
                            quality=MappingQuality.MEDIUM,
                            confidence=0.6
                        )

        return None

    async def learn_mapping(
        self,
        system_name: str,
        profile_field: str,
        form_field_id: str,
        success: bool
    ):
        """学习新的映射关系"""
        mappings = self._mappings.get(system_name, [])

        existing = None
        for m in mappings:
            if m.form_field_id == form_field_id:
                existing = m
                break

        if existing:
            existing.usage_count += 1
            if success:
                existing.success_count += 1
                existing.last_success = datetime.now()
                existing.confidence = existing.success_count / existing.usage_count
                existing.quality = self._confidence_to_quality(existing.confidence)
        else:
            self.add_mapping(
                system_name=system_name,
                profile_field=profile_field,
                form_field_id=form_field_id,
                quality=MappingQuality.MEDIUM,
                confidence=0.5
            )

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字典的值"""
        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                index = int(key)
                value = value[index] if index < len(value) else None
            else:
                return None

            if value is None:
                return None

        return value if value != "" else None

    def _apply_transform(self, transform_name: str, value: Any) -> Any:
        """应用转换函数"""
        transform_func = self._transforms.get(transform_name)
        if transform_func:
            try:
                return transform_func(value)
            except:
                return value
        return value

    def _confidence_to_quality(self, confidence: float) -> MappingQuality:
        """置信度转质量等级"""
        if confidence >= 0.95:
            return MappingQuality.PERFECT
        elif confidence >= 0.8:
            return MappingQuality.HIGH
        elif confidence >= 0.5:
            return MappingQuality.MEDIUM
        else:
            return MappingQuality.LOW

    def _generate_mapping_id(self, system_name: str, form_field_id: str) -> str:
        """生成映射ID"""
        raw = f"{system_name}:{form_field_id}"
        return f"MAP:{hashlib.md5(raw.encode()).hexdigest()[:12].upper()}"

    def get_mapping_stats(self, system_name: str = None) -> Dict:
        """获取映射统计"""
        if system_name:
            mappings = self._mappings.get(system_name, [])
            return {
                "total": len(mappings),
                "by_quality": self._count_by_quality(mappings),
                "avg_confidence": sum(m.confidence for m in mappings) / len(mappings) if mappings else 0
            }

        return {
            system: {
                "total": len(mappings),
                "by_quality": self._count_by_quality(mappings)
            }
            for system, mappings in self._mappings.items()
        }

    def _count_by_quality(self, mappings: List[FieldMapping]) -> Dict:
        """按质量统计"""
        counts = {q.value: 0 for q in MappingQuality}
        for m in mappings:
            counts[m.quality.value] += 1
        return counts

    def export_mappings(self, system_name: str = None) -> Dict:
        """导出映射配置"""
        if system_name:
            return {
                "system": system_name,
                "mappings": [
                    {
                        "profile_field": m.profile_field,
                        "form_field_id": m.form_field_id,
                        "transform": m.transform,
                        "quality": m.quality.value,
                        "confidence": m.confidence
                    }
                    for m in self._mappings.get(system_name, [])
                ]
            }

        return {
            system: [
                {
                    "profile_field": m.profile_field,
                    "form_field_id": m.form_field_id,
                    "transform": m.transform,
                    "confidence": m.confidence
                }
                for m in mappings
            ]
            for system, mappings in self._mappings.items()
        }


# ==================== 单例模式 ====================

_form_adapter: Optional[FormAdapterEngine] = None


def get_form_adapter() -> FormAdapterEngine:
    """获取表单适配器单例"""
    global _form_adapter
    if _form_adapter is None:
        _form_adapter = FormAdapterEngine()
    return _form_adapter
