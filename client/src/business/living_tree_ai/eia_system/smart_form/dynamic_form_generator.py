"""
智能表单 - 动态表单模板生成器
根据项目类型、行业、地区动态生成适合的表单模板

核心：从静态模板转变为动态适配
"""

import json
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum


# ==================== 数据模型 ====================

class FormCategory(Enum):
    """表单分类"""
    EIA_BASIC = "eia_basic"                 # 环评基本信息
    COMPANY_INFO = "company_info"            # 企业信息
    POLLUTION_SOURCE = "pollution_source"    # 污染源信息
    ENVIRONMENTAL_MEASURES = "measures"     # 环保措施
    MONITORING_PLAN = "monitoring_plan"     # 监测计划
    EMERGENCY_PLAN = "emergency_plan"       # 应急预案
    LAND_USE = "land_use"                   # 土地利用
    PRODUCT_INFO = "product_info"           # 产品信息
    WASTE_INFO = "waste_info"               # 废物信息


@dataclass
class FieldDefinition:
    """字段定义"""
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    category: str = "basic"
    options: List[Any] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: str = ""
    placeholder: str = ""
    help_text: str = ""
    unit: str = ""
    validation_rules: List[str] = field(default_factory=list)
    default_value: Any = None
    visible_when: Dict[str, Any] = field(default_factory=dict)  # 条件显示


@dataclass
class FormTemplate:
    """表单模板"""
    name: str
    label: str
    category: FormCategory
    description: str = ""
    fields: List[FieldDefinition] = field(default_factory=list)
    sections: List[Dict] = field(default_factory=list)
    version: str = "1.0"
    applicable_industries: List[str] = field(default_factory=list)
    applicable_regions: List[str] = field(default_factory=list)


# ==================== 行业知识库 ====================

class IndustryKnowledgeBase:
    """行业知识库 - 提供各行业的标准字段和验证规则"""

    # 基础字段模板
    BASE_FIELDS = {
        "project_name": FieldDefinition(
            name="project_name",
            label="项目名称",
            field_type="text",
            required=True,
            category="basic",
            placeholder="请输入项目全称"
        ),
        "project_type": FieldDefinition(
            name="project_type",
            label="项目类型",
            field_type="select",
            required=True,
            category="basic",
            options=["新建", "改建", "扩建", "技术改造"]
        ),
        "location": FieldDefinition(
            name="location",
            label="建设地点",
            field_type="text",
            required=True,
            category="basic",
            placeholder="省市区县详细地址"
        ),
        "industry_type": FieldDefinition(
            name="industry_type",
            label="行业类别",
            field_type="select",
            required=True,
            category="basic",
            options=["化工", "电力", "钢铁", "建材", "轻工", "医药", "电子", "其他"]
        ),
        "contact_person": FieldDefinition(
            name="contact_person",
            label="联系人",
            field_type="text",
            required=True,
            category="basic"
        ),
        "contact_phone": FieldDefinition(
            name="contact_phone",
            label="联系电话",
            field_type="text",
            required=True,
            category="basic",
            pattern=r"^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$"
        ),
    }

    # 行业特定字段
    INDUSTRY_SPECIFIC_FIELDS = {
        "化工": [
            FieldDefinition(
                name="main_products",
                label="主要产品",
                field_type="textarea",
                required=True,
                category="technical",
                help_text="包括产品名称、产量"
            ),
            FieldDefinition(
                name="raw_materials",
                label="主要原辅材料",
                field_type="textarea",
                required=True,
                category="technical"
            ),
            FieldDefinition(
                name="hazardous_materials",
                label="危险化学品",
                field_type="textarea",
                required=False,
                category="technical",
                help_text="如有危险化学品请详细列出"
            ),
            FieldDefinition(
                name="production_process",
                label="生产工艺",
                field_type="textarea",
                required=True,
                category="technical"
            ),
        ],
        "电力": [
            FieldDefinition(
                name="fuel_type",
                label="燃料类型",
                field_type="select",
                required=True,
                category="technical",
                options=["燃煤", "燃气", "燃油", "生物质", "其他"]
            ),
            FieldDefinition(
                name="capacity",
                label="装机容量(MW)",
                field_type="number",
                required=True,
                category="technical",
                min_value=0,
                unit="MW"
            ),
            FieldDefinition(
                name="annual_consumption",
                label="年耗量",
                field_type="number",
                required=True,
                category="technical"
            ),
        ],
        "钢铁": [
            FieldDefinition(
                name="production_capacity",
                label="产能(万吨/年)",
                field_type="number",
                required=True,
                category="technical",
                min_value=0,
                unit="万吨/年"
            ),
            FieldDefinition(
                name="main_equipment",
                label="主要设备",
                field_type="textarea",
                required=True,
                category="technical"
            ),
        ],
        "建材": [
            FieldDefinition(
                name="product_type",
                label="产品类型",
                field_type="select",
                required=True,
                category="technical",
                options=["水泥", "玻璃", "陶瓷", "砖瓦", "石材", "其他"]
            ),
            FieldDefinition(
                name="production_scale",
                label="生产规模",
                field_type="text",
                required=True,
                category="technical"
            ),
        ],
        "轻工": [
            FieldDefinition(
                name="product_category",
                label="产品类别",
                field_type="select",
                required=True,
                category="technical",
                options=["造纸", "印刷", "制革", "食品", "酿酒", "其他"]
            ),
            FieldDefinition(
                name="water_consumption",
                label="用水量(m³/d)",
                field_type="number",
                required=True,
                category="technical",
                min_value=0,
                unit="m³/d"
            ),
        ],
        "医药": [
            FieldDefinition(
                name="drug_type",
                label="药品类型",
                field_type="select",
                required=True,
                category="technical",
                options=["化学原料药", "制剂", "中药", "生物制品", "其他"]
            ),
            FieldDefinition(
                name="production_line",
                label="生产线数",
                field_type="number",
                required=True,
                category="technical",
                min_value=0
            ),
        ],
    }

    # 地区特定配置
    REGIONAL_CONFIGS = {
        "江苏": {
            "emission_standards": ["GB16297-1996", "DB32/xxxx-202x"],
            "prompt_template": "江苏省",
            "special_requirements": ["太湖流域要求更严格"]
        },
        "浙江": {
            "emission_standards": ["GB16297-1996", "DB33/xxxx-202x"],
            "prompt_template": "浙江省",
            "special_requirements": ["近海海域有特殊要求"]
        },
        "广东": {
            "emission_standards": ["GB16297-1996", "DB44/xxxx-202x"],
            "prompt_template": "广东省",
            "special_requirements": ["大气排放需考虑珠三角联防联控"]
        },
        "北京": {
            "emission_standards": ["GB16297-1996", "DB11/xxxx-202x"],
            "prompt_template": "北京市",
            "special_requirements": ["PM2.5控制要求严格"]
        },
        "上海": {
            "emission_standards": ["GB16297-1996", "DB31/xxxx-202x"],
            "prompt_template": "上海市",
            "special_requirements": ["排放总量要求严格"]
        },
    }

    @classmethod
    def get_fields_for_industry(cls, industry: str) -> List[FieldDefinition]:
        """获取行业特定字段"""
        return cls.INDUSTRY_SPECIFIC_FIELDS.get(industry, [])

    @classmethod
    def get_regional_config(cls, region: str) -> Optional[Dict]:
        """获取地区配置"""
        # 匹配省份
        for province, config in cls.REGIONAL_CONFIGS.items():
            if province in region:
                return config
        return None

    @classmethod
    def get_all_industries(cls) -> List[str]:
        """获取所有行业列表"""
        return list(cls.INDUSTRY_SPECIFIC_FIELDS.keys())

    @classmethod
    def get_all_regions(cls) -> List[str]:
        """获取所有地区列表"""
        return list(cls.REGIONAL_CONFIGS.keys())


# ==================== 动态表单生成器 ====================

class DynamicFormGenerator:
    """
    动态表单模板生成器

    根据项目类型、行业、地区动态生成适合的表单
    """

    def __init__(self, kb_client=None):
        """
        Args:
            kb_client: 知识库客户端（可选）
        """
        self.kb_client = kb_client
        self._use_mock = kb_client is None

        # 缓存生成的模板
        self._template_cache: Dict[str, FormTemplate] = {}

    async def generate_form_for_project(
        self,
        project_type: str,
        industry: str,
        region: str,
        additional_categories: List[FormCategory] = None
    ) -> FormTemplate:
        """
        为项目动态生成表单模板

        Args:
            project_type: 项目类型 (新建/改建/扩建)
            industry: 行业类别
            region: 地区
            additional_categories: 额外的表单分类

        Returns:
            FormTemplate: 动态生成的表单模板
        """
        # 生成缓存键
        cache_key = f"{project_type}_{industry}_{region}"
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        # 1. 获取基础字段
        fields = []

        # 添加基础字段
        for name, field_def in IndustryKnowledgeBase.BASE_FIELDS.items():
            fields.append(FieldDefinition(
                name=field_def.name,
                label=field_def.label,
                field_type=field_def.field_type,
                required=field_def.required,
                category=field_def.category,
                options=field_def.options.copy() if field_def.options else [],
                placeholder=field_def.placeholder,
                pattern=field_def.pattern
            ))

        # 2. 添加行业特定字段
        industry_fields = IndustryKnowledgeBase.get_fields_for_industry(industry)
        fields.extend(industry_fields)

        # 3. 添加项目类型特定字段
        type_fields = self._get_type_specific_fields(project_type)
        fields.extend(type_fields)

        # 4. 添加额外分类字段
        if additional_categories:
            for cat in additional_categories:
                cat_fields = self._get_category_fields(cat)
                fields.extend(cat_fields)

        # 5. 应用地区特定配置
        regional_config = IndustryKnowledgeBase.get_regional_config(region)
        if regional_config:
            # 添加地区标准选择
            fields.append(FieldDefinition(
                name="applicable_standards",
                label="适用排放标准",
                field_type="select",
                required=True,
                category="technical",
                options=regional_config.get("emission_standards", [])
            ))

        # 6. 构建模板
        template = FormTemplate(
            name=f"dynamic_{cache_key}",
            label=f"{industry}项目环境信息表",
            category=FormCategory.EIA_BASIC,
            description=f"适用于{region}{industry}行业的{project_type}项目",
            fields=fields,
            sections=self._generate_sections(fields),
            applicable_industries=[industry],
            applicable_regions=[region]
        )

        # 缓存
        self._template_cache[cache_key] = template

        return template

    def _get_type_specific_fields(self, project_type: str) -> List[FieldDefinition]:
        """获取项目类型特定的字段"""
        fields = []

        if project_type == "改建" or project_type == "扩建":
            fields.append(FieldDefinition(
                name="existing_project_info",
                label="现有项目基本情况",
                field_type="textarea",
                required=True,
                category="technical",
                help_text="包括现有项目的规模、污染物排放情况等"
            ))
            fields.append(FieldDefinition(
                name="modification_content",
                label="改扩建内容",
                field_type="textarea",
                required=True,
                category="technical"
            ))

        return fields

    def _get_category_fields(self, category: FormCategory) -> List[FieldDefinition]:
        """获取分类特定的字段"""
        category_field_map = {
            FormCategory.POLLUTION_SOURCE: [
                FieldDefinition(
                    name="pollutant_type",
                    label="污染物类型",
                    field_type="select",
                    required=True,
                    category="technical",
                    options=["废气", "废水", "固体废物", "噪声", "辐射"]
                ),
                FieldDefinition(
                    name="pollutant_name",
                    label="污染物名称",
                    field_type="text",
                    required=True,
                    category="technical"
                ),
                FieldDefinition(
                    name="emission_amount",
                    label="排放量",
                    field_type="number",
                    required=True,
                    category="technical",
                    min_value=0
                ),
                FieldDefinition(
                    name="emission_concentration",
                    label="排放浓度",
                    field_type="number",
                    required=True,
                    category="technical",
                    min_value=0
                ),
                FieldDefinition(
                    name="discharge_standard",
                    label="执行标准",
                    field_type="text",
                    required=True,
                    category="technical"
                ),
            ],
            FormCategory.MONITORING_PLAN: [
                FieldDefinition(
                    name="monitoring_points",
                    label="监测点位",
                    field_type="number",
                    required=True,
                    category="technical",
                    min_value=1
                ),
                FieldDefinition(
                    name="monitoring_items",
                    label="监测项目",
                    field_type="textarea",
                    required=True,
                    category="technical"
                ),
                FieldDefinition(
                    name="monitoring_frequency",
                    label="监测频次",
                    field_type="select",
                    required=True,
                    category="technical",
                    options=["每年1次", "每年2次", "每年4次", "每月1次", "连续监测"]
                ),
            ],
            FormCategory.EMERGENCY_PLAN: [
                FieldDefinition(
                    name="hazardous_materials",
                    label="危险物质及最大存在量",
                    field_type="textarea",
                    required=True,
                    category="technical"
                ),
                FieldDefinition(
                    name="potential_accidents",
                    label="潜在事故类型",
                    field_type="textarea",
                    required=True,
                    category="technical"
                ),
                FieldDefinition(
                    name="emergency_resources",
                    label="应急资源配备",
                    field_type="textarea",
                    required=False,
                    category="technical"
                ),
            ],
        }

        return category_field_map.get(category, [])

    def _generate_sections(self, fields: List[FieldDefinition]) -> List[Dict]:
        """生成分组"""
        # 按category分组
        categories = {}
        for field in fields:
            cat = field.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(field)

        # 翻译和排序
        section_names = {
            "basic": ("基本信息", 1),
            "technical": ("技术参数", 2),
            "other": ("其他信息", 3),
        }

        sections = []
        for cat, field_list in categories.items():
            name, order = section_names.get(cat, (cat, 99))
            sections.append({
                "title": name,
                "category": cat,
                "order": order,
                "fields": [f.name for f in field_list]
            })

        sections.sort(key=lambda x: x["order"])

        return sections

    async def get_form_template_dict(
        self,
        project_type: str,
        industry: str,
        region: str
    ) -> Dict:
        """
        获取表单模板字典（用于前端渲染）

        Args:
            project_type: 项目类型
            industry: 行业类别
            region: 地区

        Returns:
            Dict: 表单模板字典
        """
        template = await self.generate_form_for_project(
            project_type, industry, region
        )

        return self._template_to_dict(template)

    def _template_to_dict(self, template: FormTemplate) -> Dict:
        """将模板转换为字典"""
        return {
            "name": template.name,
            "label": template.label,
            "description": template.description,
            "fields": [
                {
                    "name": f.name,
                    "label": f.label,
                    "type": f.field_type,
                    "required": f.required,
                    "category": f.category,
                    "options": f.options,
                    "min": f.min_value,
                    "max": f.max_value,
                    "pattern": f.pattern,
                    "placeholder": f.placeholder,
                    "help_text": f.help_text,
                    "unit": f.unit,
                }
                for f in template.fields
            ],
            "sections": template.sections
        }

    def get_standard_form_templates(self) -> Dict[str, Dict]:
        """
        获取标准表单模板列表

        Returns:
            Dict[str, Dict]: 模板字典
        """
        templates = {
            "eia_basic": {
                "name": "eia_basic",
                "label": "环评基本信息",
                "category": FormCategory.EIA_BASIC.value,
                "description": "适用于一般建设项目环境影响评价",
            },
            "company_info": {
                "name": "company_info",
                "label": "企业基本信息",
                "category": FormCategory.COMPANY_INFO.value,
                "description": "用于收集企业基本信息",
            },
            "pollution_source": {
                "name": "pollution_source",
                "label": "污染源信息",
                "category": FormCategory.POLLUTION_SOURCE.value,
                "description": "用于填写污染源及排放信息",
            },
            "monitoring_plan": {
                "name": "monitoring_plan",
                "label": "监测计划",
                "category": FormCategory.MONITORING_PLAN.value,
                "description": "用于制定环境监测计划",
            },
            "emergency_plan": {
                "name": "emergency_plan",
                "label": "应急预案",
                "category": FormCategory.EMERGENCY_PLAN.value,
                "description": "用于编制环境应急预案",
            },
        }

        return templates


# ==================== 表单验证引擎 ====================

class FormValidationEngine:
    """表单验证引擎"""

    # 内置验证规则
    VALIDATION_RULES = {
        "required": lambda v: bool(v),
        "number": lambda v: v == "" or isinstance(v, (int, float)),
        "positive": lambda v: v == "" or float(v) > 0,
        "phone": lambda v: v == "" or bool(
            __import__("re").match(r"^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$", v)
        ),
        "email": lambda v: v == "" or bool(
            __import__("re").match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v)
        ),
        "credit_code": lambda v: v == "" or bool(
            __import__("re").match(r"^[0-9A-Z]{18}$", v)
        ),
    }

    @classmethod
    def validate_field(
        cls,
        value: Any,
        rules: List[str],
        field_config: Dict
    ) -> Dict[str, Any]:
        """
        验证单个字段

        Args:
            value: 字段值
            rules: 验证规则列表
            field_config: 字段配置

        Returns:
            Dict: 验证结果
        """
        errors = []

        for rule in rules:
            validator = cls.VALIDATION_RULES.get(rule)
            if validator and not validator(value):
                errors.append(cls._get_error_message(rule))

        # 范围验证
        if isinstance(value, (int, float)) and value != "":
            min_val = field_config.get("min_value")
            max_val = field_config.get("max_value")

            if min_val is not None and value < min_val:
                errors.append(f"值不能小于{min_val}")
            if max_val is not None and value > max_val:
                errors.append(f"值不能大于{max_val}")

        # 正则验证
        pattern = field_config.get("pattern")
        if pattern and value:
            if not __import__("re").match(pattern, str(value)):
                errors.append("格式不正确")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    @classmethod
    def _get_error_message(cls, rule: str) -> str:
        """获取验证错误消息"""
        messages = {
            "required": "此字段为必填项",
            "number": "请输入有效的数字",
            "positive": "请输入正数",
            "phone": "请输入有效的电话号码",
            "email": "请输入有效的邮箱地址",
            "credit_code": "请输入有效的18位统一社会信用代码",
        }
        return messages.get(rule, f"验证规则'{rule}'未通过")

    @classmethod
    def validate_form(cls, form_data: Dict, template: Dict) -> Dict[str, Any]:
        """
        验证整个表单

        Args:
            form_data: 表单数据
            template: 表单模板

        Returns:
            Dict: 验证结果
        """
        results = {}
        all_valid = True

        for field_config in template.get("fields", []):
            field_name = field_config["name"]
            value = form_data.get(field_name, "")
            rules = field_config.get("validation_rules", [])

            # 添加必填规则
            if field_config.get("required"):
                rules = ["required"] + rules

            result = cls.validate_field(value, rules, field_config)
            results[field_name] = result

            if not result["valid"]:
                all_valid = False

        return {
            "valid": all_valid,
            "field_results": results,
            "error_count": sum(1 for r in results.values() if not r["valid"])
        }


# ==================== 导出 ====================

_generator_instance: Optional[DynamicFormGenerator] = None


def get_dynamic_generator() -> DynamicFormGenerator:
    """获取动态表单生成器单例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = DynamicFormGenerator()
    return _generator_instance


async def generate_dynamic_form_async(
    project_type: str,
    industry: str,
    region: str
) -> Dict:
    """
    异步生成动态表单的便捷函数

    Args:
        project_type: 项目类型
        industry: 行业类别
        region: 地区

    Returns:
        Dict: 表单模板字典
    """
    generator = get_dynamic_generator()
    return await generator.get_form_template_dict(project_type, industry, region)
