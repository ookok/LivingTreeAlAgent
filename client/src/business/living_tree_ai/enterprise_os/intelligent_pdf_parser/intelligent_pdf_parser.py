"""
智能PDF解析系统 (Intelligent PDF Parser)

三层解析架构：
1. 大模型智能提取 - 理解语义，处理非标准格式
2. 传统库兜底 - pdfplumber 精准提取表格
3. 人机校验 - 确保高精度

核心流程：
PDF → LLM智能解析 → {高置信度→自动入库, 低置信度→传统库+人工} → 入库

适用场景：
- 验收监测报告（环保/安全）
- 检测报告（水质/大气/土壤）
- 排放报告（季度/年度）
- 其他格式多样的检测文档
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class ReportType(Enum):
    """报告类型"""
    ACCEPTANCE_MONITORING = "acceptance_monitoring"  # 验收监测报告
    PERIODIC_MONITORING = "periodic_monitoring"     # 定期监测报告
    SELF_MONITORING = "self_monitoring"           # 自行监测报告
    EMISSION_REPORT = "emission_report"           # 排放报告
    EXTERNAL_AUDIT = "external_audit"             # 外部审计报告
    UNKNOWN = "unknown"


class ParseConfidence(Enum):
    """解析置信度"""
    HIGH = "high"      # > 90%，自动入库
    MEDIUM = "medium"  # 60-90%，需确认
    LOW = "low"        # < 60%，需人工


class ParseStatus(Enum):
    """解析状态"""
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


@dataclass
class MonitoringPoint:
    """监测点位"""
    point_id: str = ""              # 排放口编号，如 "DA001"
    point_name: str = ""            # 点位名称，如 "1#锅炉烟囱"
    location: str = ""              # 位置描述
    parameters: List[Dict] = field(default_factory=list)  # 监测参数列表
    stack_info: Dict = field(default_factory=dict)       # 排气筒参数

    def to_dict(self) -> Dict:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "location": self.location,
            "parameters": self.parameters,
            "stack_info": self.stack_info
        }


@dataclass
class PollutantReading:
    """污染物读数"""
    pollutant: str = ""           # 污染物名称，如 "SO2"
    concentration: float = 0.0    # 监测浓度
    unit: str = "mg/m³"          # 单位
    standard: float = 0.0        # 排放标准限值
    is_compliant: bool = True    # 是否达标
    flow_rate: float = 0.0       # 排放流量
    remarks: str = ""             # 备注

    def to_dict(self) -> Dict:
        return {
            "pollutant": self.pollutant,
            "concentration": self.concentration,
            "unit": self.unit,
            "standard": self.standard,
            "is_compliant": self.is_compliant,
            "flow_rate": self.flow_rate,
            "remarks": self.remarks
        }


@dataclass
class ParsedReport:
    """解析结果"""
    # 基本信息
    report_id: str = ""
    report_type: ReportType = ReportType.UNKNOWN
    report_title: str = ""
    file_path: str = ""
    file_hash: str = ""

    # 企业信息
    company_name: str = ""
    credit_code: str = ""
    address: str = ""

    # 监测信息
    monitoring_date: str = ""           # 监测日期
    monitoring_purpose: str = ""        # 监测目的
    monitoring_agency: str = ""          # 监测机构
    agency_qualification: str = ""      # 资质编号

    # 监测点位
    monitoring_points: List[MonitoringPoint] = field(default_factory=list)

    # 置信度
    confidence: float = 0.0             # 0.0 - 1.0
    confidence_level: ParseConfidence = ParseConfidence.LOW

    # 解析详情
    parse_method: str = ""              # "llm_only" / "hybrid" / "fallback"
    raw_text_length: int = 0
    extracted_fields: int = 0           # 成功提取的字段数
    missing_fields: List[str] = field(default_factory=list)  # 缺失字段

    # 状态
    status: ParseStatus = ParseStatus.PENDING
    parse_time: float = 0.0             # 解析耗时（秒）

    # 元数据
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "report_title": self.report_title,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "company_name": self.company_name,
            "credit_code": self.credit_code,
            "address": self.address,
            "monitoring_date": self.monitoring_date,
            "monitoring_purpose": self.monitoring_purpose,
            "monitoring_agency": self.monitoring_agency,
            "agency_qualification": self.agency_qualification,
            "monitoring_points": [p.to_dict() for p in self.monitoring_points],
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "parse_method": self.parse_method,
            "raw_text_length": self.raw_text_length,
            "extracted_fields": self.extracted_fields,
            "missing_fields": self.missing_fields,
            "status": self.status.value,
            "parse_time": self.parse_time,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class ParseRequest:
    """解析请求"""
    file_path: str
    report_type_hint: Optional[ReportType] = None  # 报告类型提示
    expected_company: Optional[str] = None          # 预期企业名称
    custom_prompt: Optional[str] = None             # 自定义提示词
    require_human_review: bool = True               # 是否需要人工审核
    llm_callable: Optional[Callable] = None          # LLM调用函数


@dataclass
class ParseResult:
    """解析结果（对外接口）"""
    success: bool
    parsed_report: Optional[ParsedReport] = None
    message: str = ""
    requires_review: bool = False
    review_data: Optional[Dict] = None  # 用于界面展示的审核数据

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "parsed_report": self.parsed_report.to_dict() if self.parsed_report else None,
            "message": self.message,
            "requires_review": self.requires_review,
            "review_data": self.review_data
        }


# ==================== 智能PDF解析器 ====================

class IntelligentPDFParser:
    """
    智能PDF解析器

    三层解析策略：
    1. LLM优先 - 使用大模型理解语义
    2. 传统库兜底 - pdfplumber处理表格
    3. 人机校验 - 低置信度时触发人工审核
    """

    def __init__(
        self,
        llm_callable: Optional[Callable] = None,
        pdf_text_extractor: Optional[Callable] = None
    ):
        """
        初始化解析器

        Args:
            llm_callable: LLM调用函数，签名为 (prompt: str) -> str
                         如果不提供，使用内置的请求方式
            pdf_text_extractor: PDF文本提取函数
        """
        self._llm = llm_callable
        self._pdf_extractor = pdf_text_extractor
        self._confidence_thresholds = {
            ParseConfidence.HIGH: 0.90,
            ParseConfidence.MEDIUM: 0.60
        }

    def set_llm_callable(self, llm_callable: Callable):
        """设置LLM调用函数"""
        self._llm = llm_callable

    async def parse(self, request: ParseRequest) -> ParseResult:
        """
        解析PDF报告

        Args:
            request: 解析请求

        Returns:
            ParseResult: 解析结果
        """
        import time
        start_time = time.time()

        try:
            # 1. 验证文件
            if not Path(request.file_path).exists():
                return ParseResult(
                    success=False,
                    message=f"文件不存在: {request.file_path}"
                )

            # 2. 提取PDF文本
            text_content = await self._extract_pdf_text(request.file_path)

            if not text_content.strip():
                return ParseResult(
                    success=False,
                    message="PDF文本提取失败，文件可能为空或已加密"
                )

            # 3. LLM智能解析
            parsed = await self._parse_with_llm(
                text_content,
                request.report_type_hint,
                request.expected_company,
                request.custom_prompt
            )

            # 4. 计算置信度
            confidence = self._calculate_confidence(parsed, text_content)
            parsed.confidence = confidence
            parsed.confidence_level = self._get_confidence_level(confidence)

            # 5. 判断是否需要人工审核
            requires_review = (
                request.require_human_review and
                confidence < self._confidence_thresholds[ParseConfidence.HIGH]
            )

            if requires_review:
                parsed.status = ParseStatus.MANUAL_REVIEW
            else:
                parsed.status = ParseStatus.COMPLETED

            parsed.parse_time = time.time() - start_time

            # 6. 构建审核数据
            review_data = None
            if requires_review:
                review_data = self._build_review_data(parsed, text_content)

            return ParseResult(
                success=True,
                parsed_report=parsed,
                message="解析成功" if not requires_review else "需要人工审核",
                requires_review=requires_review,
                review_data=review_data
            )

        except Exception as e:
            logger.error(f"PDF解析失败: {e}")
            return ParseResult(
                success=False,
                message=f"解析失败: {str(e)}"
            )

    async def _extract_pdf_text(self, file_path: str) -> str:
        """提取PDF文本"""
        if self._pdf_extractor:
            return await self._pdf_extractor(file_path)

        # 默认使用 pdfplumber
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    text_parts.append(f"=== 第 {page_num + 1} 页 ===\n{text}")

            return "\n\n".join(text_parts)

        except ImportError:
            try:
                import pypdf
                with open(file_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                ...
                raise Exception("请安装 pdfplumber 或 pypdf: pip install pdfplumber pypdf")

    async def _parse_with_llm(
        self,
        text_content: str,
        report_type_hint: Optional[ReportType],
        expected_company: Optional[str],
        custom_prompt: Optional[str]
    ) -> ParsedReport:
        """使用LLM解析"""
        # 构建提示词
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = self._build_parse_prompt(
                text_content,
                report_type_hint,
                expected_company
            )

        # 调用LLM
        if self._llm:
            response = await self._llm(prompt)
        else:
            # 如果没有提供LLM，使用规则匹配兜底
            response = await self._fallback_parse(text_content)

        # 解析LLM响应
        return self._parse_llm_response(response, text_content)

    def _build_parse_prompt(
        self,
        text_content: str,
        report_type_hint: Optional[ReportType],
        expected_company: Optional[str]
    ) -> str:
        """构建解析提示词"""
        # 截断过长文本
        max_chars = 8000
        truncated_text = text_content[:max_chars]
        if len(text_content) > max_chars:
            truncated_text += "\n\n[... 内容已截断 ...]"

        report_type_str = report_type_hint.value if report_type_hint else "unknown"

        prompt = f"""你是一名环境监测专家，请从以下{report_type_str}报告中提取结构化数据。

报告内容：
{truncated_text}

{f"注意：预期企业名称为：{expected_company}" if expected_company else ""}

请提取以下信息并以JSON格式返回：
{{
    "report_title": "报告标题",
    "company_name": "企业名称",
    "credit_code": "统一信用代码（如有）",
    "address": "企业地址",
    "monitoring_date": "监测日期，格式YYYY-MM-DD",
    "monitoring_purpose": "监测目的",
    "monitoring_agency": "监测机构名称",
    "agency_qualification": "资质编号",
    "monitoring_points": [
        {{
            "point_id": "排放口编号，如 DA001",
            "point_name": "点位名称，如 1#锅炉烟囱",
            "location": "位置描述",
            "parameters": [
                {{
                    "pollutant": "污染物名称，如 SO2",
                    "concentration": 监测浓度数值,
                    "unit": "单位，如 mg/m³",
                    "standard": 排放标准限值,
                    "is_compliant": true或false,
                    "flow_rate": 排放流量（可选）,
                    "remarks": "备注（可选）"
                }}
            ],
            "stack_info": {{
                "height": 排气筒高度（米）,
                "diameter": 直径（米）,
                "temperature": 烟气温度（℃）,
                "flow_rate": 流速（m/s，可选）
            }}
        }}
    ],
    "extracted_fields": ["已成功提取的字段列表"],
    "missing_fields": ["缺失的字段列表"],
    "confidence": 0.0-1.0之间的置信度数值
}}

如果某项信息未找到或不确定，请填写 null。
只返回JSON，不要有其他内容。"""
        return prompt

    def _parse_llm_response(self, response: str, raw_text: str) -> ParsedReport:
        """解析LLM响应"""
        import hashlib

        # 提取JSON
        json_str = self._extract_json(response)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("LLM返回的不是有效JSON，使用兜底解析")
            return self._fallback_parse_sync(raw_text)

        # 构建 ParsedReport
        report = ParsedReport()

        # 基本信息
        report.report_title = data.get("report_title", "")
        report.company_name = data.get("company_name", "")
        report.credit_code = data.get("credit_code", "")
        report.address = data.get("address", "")
        report.monitoring_date = data.get("monitoring_date", "")
        report.monitoring_purpose = data.get("monitoring_purpose", "")
        report.monitoring_agency = data.get("monitoring_agency", "")
        report.agency_qualification = data.get("agency_qualification", "")

        # 文件信息
        report.raw_text_length = len(raw_text)

        # 监测点位
        for pt_data in data.get("monitoring_points", []):
            point = MonitoringPoint(
                point_id=pt_data.get("point_id", ""),
                point_name=pt_data.get("point_name", ""),
                location=pt_data.get("location", ""),
                parameters=pt_data.get("parameters", []),
                stack_info=pt_data.get("stack_info", {})
            )
            report.monitoring_points.append(point)

        # 置信度和字段统计
        report.confidence = data.get("confidence", 0.5)
        report.extracted_fields = len(data.get("extracted_fields", []))
        report.missing_fields = data.get("missing_fields", [])

        # 解析方法
        report.parse_method = "llm_only"
        report.status = ParseStatus.PARSING

        # 文件哈希
        report.file_hash = hashlib.md5(raw_text.encode()).hexdigest()[:12]

        # 时间戳
        now = datetime.now().isoformat()
        report.created_at = now
        report.updated_at = now

        return report

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        import re

        # 尝试多种方式提取JSON
        # 1. 寻找 ``` json ... ```
        json_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(1)

        # 2. 寻找 ``` ... ```
        json_pattern = r'```\s*(.*?)\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(1)

        # 3. 寻找 { ... }
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, text)
        if match:
            return match.group(0)

        return text

    async def _fallback_parse(self, text_content: str) -> str:
        """兜底解析（当没有LLM时使用规则匹配）"""
        import re

        # 简单规则匹配
        result = {}

        # 企业名称
        company_patterns = [
            r'企业名称[：:]\s*([^\n]+)',
            r'单位名称[：:]\s*([^\n]+)',
            r'公司名称[：:]\s*([^\n]+)'
        ]
        for pattern in company_patterns:
            match = re.search(pattern, text_content)
            if match:
                result["company_name"] = match.group(1).strip()
                break

        # 监测日期
        date_patterns = [
            r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
            r'(\d{4})/(\d{1,2})/(\d{1,2})'
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text_content)
            if match:
                result["monitoring_date"] = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                break

        # 监测机构
        agency_patterns = [
            r'监测机构[：:]\s*([^\n]+)',
            r'检测单位[：:]\s*([^\n]+)'
        ]
        for pattern in agency_patterns:
            match = re.search(pattern, text_content)
            if match:
                result["monitoring_agency"] = match.group(1).strip()
                break

        result["monitoring_points"] = []
        result["extracted_fields"] = list(result.keys())
        result["missing_fields"] = []
        result["confidence"] = 0.3

        return json.dumps(result, ensure_ascii=False)

    def _fallback_parse_sync(self, text_content: str) -> ParsedReport:
        """同步兜底解析"""
        import hashlib

        report = ParsedReport()
        report.raw_text_length = len(text_content)
        report.confidence = 0.3
        report.parse_method = "fallback"
        report.status = ParseStatus.MANUAL_REVIEW
        report.file_hash = hashlib.md5(text_content.encode()).hexdigest()[:12]

        now = datetime.now().isoformat()
        report.created_at = now
        report.updated_at = now

        return report

    def _calculate_confidence(self, parsed: ParsedReport, raw_text: str) -> float:
        """计算置信度"""
        # 基于提取字段数量
        total_fields = 10  # 期望的总字段数
        extracted_ratio = parsed.extracted_fields / total_fields

        # 基于缺失字段
        missing_penalty = len(parsed.missing_fields) * 0.05

        # 基础置信度
        base_confidence = parsed.confidence

        # 综合计算
        confidence = (base_confidence * 0.4 + extracted_ratio * 0.6) - missing_penalty

        return max(0.0, min(1.0, confidence))

    def _get_confidence_level(self, confidence: float) -> ParseConfidence:
        """获取置信度等级"""
        if confidence >= self._confidence_thresholds[ParseConfidence.HIGH]:
            return ParseConfidence.HIGH
        elif confidence >= self._confidence_thresholds[ParseConfidence.MEDIUM]:
            return ParseConfidence.MEDIUM
        else:
            return ParseConfidence.LOW

    def _build_review_data(
        self,
        parsed: ParsedReport,
        raw_text: str
    ) -> Dict[str, Any]:
        """构建人工审核数据"""
        return {
            "parsed_fields": parsed.to_dict(),
            "raw_text_preview": raw_text[:2000],
            "suggested_fields": [
                {"key": "company_name", "label": "企业名称", "value": parsed.company_name},
                {"key": "monitoring_date", "label": "监测日期", "value": parsed.monitoring_date},
                {"key": "monitoring_agency", "label": "监测机构", "value": parsed.monitoring_agency},
            ],
            "missing_field_hints": parsed.missing_fields
        }


# ==================== 便捷函数 ====================

_parser: Optional[IntelligentPDFParser] = None


def get_intelligent_pdf_parser(
    llm_callable: Optional[Callable] = None
) -> IntelligentPDFParser:
    """获取智能PDF解析器单例"""
    global _parser
    if _parser is None:
        _parser = IntelligentPDFParser(llm_callable)
    elif llm_callable:
        _parser.set_llm_callable(llm_callable)
    return _parser


async def parse_pdf_report(
    file_path: str,
    report_type_hint: Optional[ReportType] = None,
    llm_callable: Optional[Callable] = None,
    require_human_review: bool = True
) -> ParseResult:
    """解析PDF报告"""
    parser = get_intelligent_pdf_parser(llm_callable)

    request = ParseRequest(
        file_path=file_path,
        report_type_hint=report_type_hint,
        require_human_review=require_human_review
    )

    return await parser.parse(request)