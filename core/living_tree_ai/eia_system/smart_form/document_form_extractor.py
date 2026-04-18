"""
智能表单 - 文档解析引擎
从文档中提取结构化数据，生成预填表单

核心理念：业主不再被动填写，而是核对和确认AI从文档中提取的数据
业主上传文档 → AI解析 → 提取关键信息 → 生成预填表单 → 业主核对修改
"""

import re
import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
from pathlib import Path

# ==================== 数据模型 ====================

class DocumentType(Enum):
    """文档类型枚举"""
    BUSINESS_LICENSE = "business_license"           # 营业执照
    FEASIBILITY_STUDY = "feasibility_study"         # 可研报告
    EIA_REPORT = "eia_report"                       # 环评报告
    LAND_USE = "land_use"                           # 土地使用证明
    PROPERTY = "property"                           # 房产证明
    IDENTITY = "identity"                           # 身份证明
    BANK_INFO = "bank_info"                         # 银行信息
    ENVIRONMENTAL_PERMIT = "environmental_permit"   # 环保许可证
    ACCEPTANCE_REPORT = "acceptance_report"         # 验收报告
    MONITORING_DATA = "monitoring_data"             # 监测数据
    UNKNOWN = "unknown"                              # 未知类型


class ExtractionConfidence(Enum):
    """提取置信度"""
    HIGH = "high"      # > 90%
    MEDIUM = "medium"  # 60-90%
    LOW = "low"        # < 60%


@dataclass
class ExtractedField:
    """提取的字段"""
    name: str                          # 字段名
    value: Any                         # 提取的值
    confidence: float                   # 置信度 0-1
    source_position: str = ""          # 来源位置（页码、段落）
    raw_text: str = ""                 # 原始文本
    is_standardized: bool = False      # 是否已标准化


@dataclass
class ValidationResult:
    """验证结果"""
    field_name: str
    extracted_value: Any
    standard_value: Optional[Any] = None
    match: bool = True
    suggestion: Optional[str] = None
    validation_message: str = ""
    is_valid: bool = True


@dataclass
class ExtractionResult:
    """文档提取结果"""
    doc_type: DocumentType
    file_hash: str                      # 文件哈希
    filename: str
    extracted_fields: Dict[str, ExtractedField]
    validation_results: Dict[str, ValidationResult]
    overall_confidence: float
    extraction_time: datetime = field(default_factory=datetime.now)
    warnings: List[str] = field(default_factory=list)


# ==================== 文档类型识别器 ====================

class DocumentTypeIdentifier:
    """文档类型识别器"""

    # 文档类型特征
    TYPE_PATTERNS = {
        DocumentType.BUSINESS_LICENSE: [
            r"统一社会信用代码",
            r"注册资本",
            r"法定代表人",
            r"经营范围",
            r"公司名称",
        ],
        DocumentType.FEASIBILITY_STUDY: [
            r"可行性研究报告",
            r"项目概况",
            r"建设规模",
            r"投资估算",
            r"经济效益分析",
        ],
        DocumentType.EIA_REPORT: [
            r"环境影响评价",
            r"建设项目",
            r"环境保护",
            r"污染源",
            r"排放标准",
        ],
        DocumentType.LAND_USE: [
            r"土地使用权",
            r"地号",
            r"用地性质",
            r"土地面积",
            r"四至",
        ],
        DocumentType.ENVIRONMENTAL_PERMIT: [
            r"排污许可证",
            r"排放许可证",
            r"许可排放量",
            r"排放口",
        ],
    }

    @classmethod
    def identify(cls, text: str, filename: str = "") -> DocumentType:
        """
        识别文档类型

        Args:
            text: 文档文本内容
            filename: 文件名（用于辅助判断）

        Returns:
            DocumentType: 识别的文档类型
        """
        text_lower = text.lower()
        filename_lower = filename.lower()

        scores = {}

        for doc_type, patterns in cls.TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text):
                    score += 1
            # 文件名匹配加权
            if doc_type.value.replace("_", "") in filename_lower:
                score += 2
            scores[doc_type] = score

        # 返回得分最高的类型
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 0:
                return best_type

        return DocumentType.UNKNOWN


# ==================== AI提取引擎接口 ====================

class AIExtractEngine:
    """AI提取引擎接口（对接系统大脑）"""

    def __init__(self, brain_client=None):
        """
        Args:
            brain_client: 系统大脑客户端，如果为None则使用模拟模式
        """
        self.brain_client = brain_client
        self._use_mock = brain_client is None

    async def extract_structured_data(
        self,
        text: str,
        doc_type: DocumentType,
        expected_fields: List[Dict]
    ) -> Dict[str, ExtractedField]:
        """
        从文本中提取结构化数据

        Args:
            text: 文档文本
            doc_type: 文档类型
            expected_fields: 期望提取的字段列表

        Returns:
            Dict[str, ExtractedField]: 提取的字段字典
        """
        if self._use_mock:
            return await self._mock_extract(text, doc_type, expected_fields)

        # 实际调用系统大脑
        prompt = self._build_extract_prompt(text, doc_type, expected_fields)
        result = await self.brain_client.generate(prompt)

        return self._parse_ai_result(result, expected_fields)

    def _build_extract_prompt(
        self,
        text: str,
        doc_type: DocumentType,
        expected_fields: List[Dict]
    ) -> str:
        """构建提取提示词"""
        fields_desc = "\n".join([
            f"- {f['name']}: {f.get('description', f['label'])}"
            for f in expected_fields
        ])

        return f"""你是一个专业的文档信息提取助手。请从以下{doc_type.value}类型文档中提取关键信息。

需要提取的字段：
{fields_desc}

文档内容：
{text[:8000]}  # 限制长度

请以JSON格式返回提取结果：
{{
  "字段名": {{
    "value": "提取的值",
    "confidence": 0.95,
    "source_position": "第1页第3段",
    "raw_text": "原始匹配文本"
  }}
}}
只返回有效的JSON，不要有其他文字。"""

    async def _mock_extract(
        self,
        text: str,
        doc_type: DocumentType,
        expected_fields: List[Dict]
    ) -> Dict[str, ExtractedField]:
        """模拟提取（无AI引擎时使用）"""
        await asyncio.sleep(0.1)  # 模拟处理时间

        result = {}

        # 根据文档类型进行基础模式匹配
        patterns = self._get_extraction_patterns(doc_type)

        for field_config in expected_fields:
            field_name = field_config["name"]
            field_label = field_config.get("label", field_name)

            # 搜索匹配的模式
            matched = False
            for pattern_name, pattern_regex in patterns.items():
                matches = re.findall(pattern_regex, text, re.IGNORECASE)
                if matches:
                    value = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    result[field_name] = ExtractedField(
                        name=field_name,
                        value=value.strip(),
                        confidence=0.75,
                        source_position=f"通过{pattern_name}匹配",
                        raw_text=matches[0] if isinstance(matches[0], tuple) else value
                    )
                    matched = True
                    break

            if not matched:
                # 尝试模糊匹配字段标签
                label_matches = re.findall(
                    rf"{field_label}[：:]\s*([^\n]{2,50})",
                    text
                )
                if label_matches:
                    result[field_name] = ExtractedField(
                        name=field_name,
                        value=label_matches[0].strip(),
                        confidence=0.5,
                        source_position="模糊匹配",
                        raw_text=label_matches[0]
                    )
                else:
                    result[field_name] = ExtractedField(
                        name=field_name,
                        value="",
                        confidence=0.0,
                        source_position="未找到",
                        raw_text=""
                    )

        return result

    def _get_extraction_patterns(self, doc_type: DocumentType) -> Dict[str, str]:
        """获取文档类型的提取模式"""
        patterns = {
            # 通用模式
            "company_name": r"公司名称[：:]\s*([^\n]{2,50})",
            "contact_person": r"联系人[：:]\s*([^\n]{2,20})",
            "phone": r"电话[：:]\s*([0-9\-]{7,20})",
            "address": r"地址[：:]\s*([^\n]{5,100})",
            "email": r"邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        }

        type_specific = {
            DocumentType.BUSINESS_LICENSE: {
                "credit_code": r"统一社会信用代码[：:]\s*([0-9A-Z]{18})",
                "legal_person": r"法定代表人[：:]\s*([^\n]{2,20})",
                "registered_capital": r"注册资本[：:]\s*([0-9.,]+(?:万元|亿))",
                "business_scope": r"经营范围[：:]\s*([^\n]{10,500})",
            },
            DocumentType.EIA_REPORT: {
                "project_name": r"项目名称[：:]\s*([^\n]{2,100})",
                "construction_scale": r"建设规模[：:]\s*([^\n]{2,500})",
                "pollutant_type": r"污染物[：:]\s*([^\n]{2,200})",
                "discharge_standard": r"排放标准[：:]\s*([GBHJ][^\n]{2,100})",
            },
            DocumentType.ENVIRONMENTAL_PERMIT: {
                "permit_number": r"许可证编号[：:]\s*([^\n]{5,30})",
                "permit_quantity": r"许可排放量[：:]\s*([0-9.,]+\s*(?:吨/年|千克/年|m³/年))",
                "discharge_point": r"排放口[：:]\s*([^\n]{2,50})",
            },
        }

        if doc_type in type_specific:
            patterns.update(type_specific[doc_type])

        return patterns

    def _parse_ai_result(
        self,
        result: str,
        expected_fields: List[Dict]
    ) -> Dict[str, ExtractedField]:
        """解析AI返回的结果"""
        try:
            data = json.loads(result)
            extracted = {}

            for field_config in expected_fields:
                field_name = field_config["name"]
                if field_name in data:
                    field_data = data[field_name]
                    extracted[field_name] = ExtractedField(
                        name=field_name,
                        value=field_data.get("value", ""),
                        confidence=field_data.get("confidence", 0.5),
                        source_position=field_data.get("source_position", ""),
                        raw_text=field_data.get("raw_text", "")
                    )
                else:
                    extracted[field_name] = ExtractedField(
                        name=field_name,
                        value="",
                        confidence=0.0,
                        source_position="未在AI结果中找到"
                    )

            return extracted
        except json.JSONDecodeError:
            # 返回空结果
            return {
                f["name"]: ExtractedField(
                    name=f["name"],
                    value="",
                    confidence=0.0,
                    source_position="JSON解析失败"
                )
                for f in expected_fields
            }


# ==================== 知识库验证器 ====================

class KnowledgeBaseValidator:
    """知识库验证器"""

    def __init__(self, kb_client=None):
        """
        Args:
            kb_client: 知识库客户端
        """
        self.kb_client = kb_client
        self._use_mock = kb_client is None

        # 内置标准值缓存
        self._standard_cache = {
            "province_code": {
                "江苏": "32", "浙江": "33", "上海": "31", "北京": "11",
                "广东": "44", "山东": "37", "河南": "41", "湖北": "42",
            },
            "industry_code": {
                "化工": "C261", "电力": "D44", "钢铁": "C31",
                "建材": "C30", "轻工": "C20", "医药": "C27",
            },
            "pollutant_unit": {
                "SO2": "mg/m³", "NOx": "mg/m³", "COD": "mg/L",
                "氨氮": "mg/L", "VOCs": "mg/m³", "颗粒物": "mg/m³",
            },
        }

    async def validate_field(
        self,
        field_name: str,
        value: Any,
        field_config: Dict
    ) -> ValidationResult:
        """
        验证单个字段

        Args:
            field_name: 字段名
            value: 待验证的值
            field_config: 字段配置

        Returns:
            ValidationResult: 验证结果
        """
        if self._use_mock:
            return await self._mock_validate(field_name, value, field_config)

        # 查询知识库
        kb_result = await self.kb_client.query_standard_value(
            field_name, value, field_config.get("category")
        )

        if kb_result and "standard_value" in kb_result:
            return ValidationResult(
                field_name=field_name,
                extracted_value=value,
                standard_value=kb_result["standard_value"],
                match=value == kb_result["standard_value"],
                suggestion=kb_result.get("suggestion"),
                validation_message=kb_result.get("message", ""),
                is_valid=kb_result.get("is_valid", True)
            )

        return ValidationResult(
            field_name=field_name,
            extracted_value=value,
            is_valid=True
        )

    async def _mock_validate(
        self,
        field_name: str,
        value: Any,
        field_config: Dict
    ) -> ValidationResult:
        """模拟验证（无知识库时使用）"""
        await asyncio.sleep(0.05)

        # 基础格式验证
        if field_config.get("required") and not value:
            return ValidationResult(
                field_name=field_name,
                extracted_value=value,
                is_valid=False,
                validation_message="必填字段不能为空"
            )

        # 类型验证
        field_type = field_config.get("type")
        if field_type == "number" and value:
            try:
                float(value)
            except (ValueError, TypeError):
                return ValidationResult(
                    field_name=field_name,
                    extracted_value=value,
                    is_valid=False,
                    validation_message="请输入有效的数字"
                )

        # 范围验证
        if field_type == "number" and value:
            min_val = field_config.get("min")
            max_val = field_config.get("max")
            if min_val and float(value) < min_val:
                return ValidationResult(
                    field_name=field_name,
                    extracted_value=value,
                    is_valid=False,
                    validation_message=f"值不能小于{min_val}"
                )
            if max_val and float(value) > max_val:
                return ValidationResult(
                    field_name=field_name,
                    extracted_value=value,
                    is_valid=False,
                    validation_message=f"值不能大于{max_val}"
                )

        return ValidationResult(
            field_name=field_name,
            extracted_value=value,
            is_valid=True
        )

    async def batch_validate(
        self,
        fields: Dict[str, ExtractedField],
        field_configs: List[Dict]
    ) -> Dict[str, ValidationResult]:
        """
        批量验证字段

        Args:
            fields: 提取的字段字典
            field_configs: 字段配置列表

        Returns:
            Dict[str, ValidationResult]: 验证结果字典
        """
        configs_map = {c["name"]: c for c in field_configs}
        results = {}

        for field_name, extracted_field in fields.items():
            config = configs_map.get(field_name, {})
            results[field_name] = await self.validate_field(
                field_name,
                extracted_field.value,
                config
            )

        return results


# ==================== 主提取器 ====================

class DocumentFormExtractor:
    """
    文档表单提取器

    核心流程：
    1. 文档类型识别
    2. 调用AI解析
    3. 知识库验证
    4. 生成交互式表单
    """

    def __init__(
        self,
        brain_client=None,
        kb_client=None
    ):
        """
        Args:
            brain_client: 系统大脑客户端
            kb_client: 知识库客户端
        """
        self.ai_engine = AIExtractEngine(brain_client)
        self.kb_validator = KnowledgeBaseValidator(kb_client)

        # 内置表单模板
        self._form_templates = self._load_default_templates()

    def _load_default_templates(self) -> Dict[str, Dict]:
        """加载默认表单模板"""
        return {
            "eia_basic": {
                "name": "eia_basic",
                "label": "环评基本信息",
                "fields": [
                    {"name": "project_name", "label": "项目名称", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "project_type", "label": "项目类型", "type": "select",
                     "options": ["新建", "改建", "扩建", "技术改造"],
                     "required": True, "category": "basic"},
                    {"name": "construction_scale", "label": "建设规模", "type": "textarea",
                     "required": True, "category": "technical"},
                    {"name": "location", "label": "建设地点", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "industry_type", "label": "行业类别", "type": "select",
                     "options": ["化工", "电力", "钢铁", "建材", "轻工", "医药", "其他"],
                     "required": True, "category": "basic"},
                    {"name": "investment", "label": "总投资(万元)", "type": "number",
                     "min": 0, "required": False, "category": "technical"},
                    {"name": "contact_person", "label": "联系人", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "contact_phone", "label": "联系电话", "type": "text",
                     "required": True, "category": "basic"},
                ]
            },
            "company_info": {
                "name": "company_info",
                "label": "企业基本信息",
                "fields": [
                    {"name": "company_name", "label": "企业名称", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "credit_code", "label": "统一社会信用代码", "type": "text",
                     "pattern": r"^[0-9A-Z]{18}$", "required": True, "category": "basic"},
                    {"name": "legal_person", "label": "法定代表人", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "registered_capital", "label": "注册资本", "type": "text",
                     "required": False, "category": "technical"},
                    {"name": "business_scope", "label": "经营范围", "type": "textarea",
                     "required": False, "category": "basic"},
                    {"name": "address", "label": "注册地址", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "contact_person", "label": "联系人", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "phone", "label": "联系电话", "type": "text",
                     "required": True, "category": "basic"},
                ]
            },
            "pollution_source": {
                "name": "pollution_source",
                "label": "污染源信息",
                "fields": [
                    {"name": "source_name", "label": "污染源名称", "type": "text",
                     "required": True, "category": "basic"},
                    {"name": "source_type", "label": "源类型", "type": "select",
                     "options": ["有组织排放", "无组织排放", "事故排放"],
                     "required": True, "category": "basic"},
                    {"name": "pollutant_type", "label": "污染物类型", "type": "select",
                     "options": ["废气", "废水", "固体废物", "噪声"],
                     "required": True, "category": "technical"},
                    {"name": "pollutant_name", "label": "污染物名称", "type": "text",
                     "required": True, "category": "technical"},
                    {"name": "emission_amount", "label": "排放量", "type": "number",
                     "min": 0, "required": True, "category": "technical"},
                    {"name": "emission_concentration", "label": "排放浓度", "type": "number",
                     "min": 0, "required": True, "category": "technical"},
                    {"name": "discharge_standard", "label": "执行标准", "type": "text",
                     "required": True, "category": "technical"},
                    {"name": "treatment_method", "label": "处理方法", "type": "text",
                     "required": False, "category": "technical"},
                ]
            },
        }

    def get_template(self, template_name: str) -> Optional[Dict]:
        """获取表单模板"""
        return self._form_templates.get(template_name)

    def get_all_templates(self) -> List[Dict]:
        """获取所有模板"""
        return list(self._form_templates.values())

    def get_template_for_document(self, doc_type: DocumentType) -> str:
        """根据文档类型推荐表单模板"""
        mapping = {
            DocumentType.BUSINESS_LICENSE: "company_info",
            DocumentType.FEASIBILITY_STUDY: "eia_basic",
            DocumentType.EIA_REPORT: "eia_basic",
            DocumentType.ENVIRONMENTAL_PERMIT: "pollution_source",
        }
        return mapping.get(doc_type, "eia_basic")

    async def extract_form_data(
        self,
        file_data: bytes,
        filename: str,
        form_template: Dict
    ) -> ExtractionResult:
        """
        从文档提取表单数据

        Args:
            file_data: 文件二进制数据
            filename: 文件名
            form_template: 表单模板

        Returns:
            ExtractionResult: 提取结果
        """
        # 1. 计算文件哈希
        file_hash = hashlib.sha256(file_data).hexdigest()

        # 2. 提取文本（根据文件类型）
        text = await self._extract_text(file_data, filename)

        # 3. 识别文档类型
        doc_type = DocumentTypeIdentifier.identify(text, filename)

        # 4. 调用AI提取
        extracted_fields = await self.ai_engine.extract_structured_data(
            text,
            doc_type,
            form_template["fields"]
        )

        # 5. 知识库验证
        validation_results = await self.kb_validator.batch_validate(
            extracted_fields,
            form_template["fields"]
        )

        # 6. 计算总体置信度
        confidences = [f.confidence for f in extracted_fields.values() if f.confidence > 0]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # 7. 生成警告
        warnings = []
        for field_name, result in validation_results.items():
            if not result.is_valid:
                warnings.append(f"{field_name}: {result.validation_message}")

        return ExtractionResult(
            doc_type=doc_type,
            file_hash=file_hash,
            filename=filename,
            extracted_fields=extracted_fields,
            validation_results=validation_results,
            overall_confidence=overall_confidence,
            warnings=warnings
        )

    async def _extract_text(self, file_data: bytes, filename: str) -> str:
        """
        从文件提取文本

        Args:
            file_data: 文件二进制数据
            filename: 文件名

        Returns:
            str: 提取的文本
        """
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            return await self._extract_pdf_text(file_data)
        elif suffix in [".doc", ".docx"]:
            return await self._extract_word_text(file_data)
        elif suffix in [".txt"]:
            return file_data.decode("utf-8", errors="ignore")
        elif suffix in [".jpg", ".jpeg", ".png"]:
            return await self._extract_image_text(file_data)
        else:
            return file_data.decode("utf-8", errors="ignore")

    async def _extract_pdf_text(self, file_data: bytes) -> str:
        """提取PDF文本（需要pdfminer或类似库）"""
        # 简化实现，实际应使用pdfminer.six
        try:
            from pdfminer.high_level import extract_text
            import tempfile
            import os

            # 写入临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(file_data)
                temp_path = f.name

            try:
                text = extract_text(temp_path)
                return text
            finally:
                os.unlink(temp_path)
        except ImportError:
            # 回退到简单文本提取
            return file_data.decode("latin-1", errors="ignore")

    async def _extract_word_text(self, file_data: bytes) -> str:
        """提取Word文本"""
        try:
            from docx import Document
            import tempfile
            import os

            # 写入临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as f:
                f.write(file_data)
                temp_path = f.name

            try:
                doc = Document(temp_path)
                return "\n".join([p.text for p in doc.paragraphs])
            finally:
                os.unlink(temp_path)
        except ImportError:
            return "[Word文档解析失败]"

    async def _extract_image_text(self, file_data: bytes) -> str:
        """提取图片文本（OCR）"""
        # 简化实现，实际应使用pytesseract
        return "[图片文字识别未实现]"

    def calculate_confidence(self, extracted_fields: Dict[str, ExtractedField]) -> float:
        """计算提取置信度"""
        confidences = [f.confidence for f in extracted_fields.values() if f.confidence > 0]
        return sum(confidences) / len(confidences) if confidences else 0.0


# ==================== 导出接口函数 ====================

_extractor_instance: Optional[DocumentFormExtractor] = None


def get_extractor() -> DocumentFormExtractor:
    """获取文档提取器单例"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = DocumentFormExtractor()
    return _extractor_instance


async def extract_form_data_async(
    file_data: bytes,
    filename: str,
    template_name: str = "eia_basic"
) -> ExtractionResult:
    """
    异步提取表单数据的便捷函数

    Args:
        file_data: 文件二进制数据
        filename: 文件名
        template_name: 模板名称

    Returns:
        ExtractionResult: 提取结果
    """
    extractor = get_extractor()
    template = extractor.get_template(template_name)

    if not template:
        raise ValueError(f"未知的模板: {template_name}")

    return await extractor.extract_form_data(file_data, filename, template)
