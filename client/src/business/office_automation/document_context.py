"""
📋 文档上下文与意图识别

解析用户自然语言请求，提取：
- 文档类型 (报告/合同/标书/简历/发票...)
- 目标受众 (内部/外部/高管/技术/通用)
- 重要程度 (普通/重要/关键)
- 格式要求 (排版风格/设计偏好/输出格式)
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """文档类型"""
    REPORT = "report"              # 报告
    CONTRACT = "contract"          # 合同
    PROPOSAL = "proposal"          # 标书/方案
    RESUME = "resume"              # 简历
    INVOICE = "invoice"            # 发票
    MEMO = "memo"                  # 备忘录
    LETTER = "letter"              # 信函
    PRESENTATION = "presentation"  # 演示文稿
    SPREADSHEET = "spreadsheet"    # 电子表格
    MANUAL = "manual"              # 手册
    POLICY = "policy"              # 制度
    ANALYSIS = "analysis"          # 分析报告
    PLAN = "plan"                  # 计划
    SUMMARY = "summary"            # 总结
    CERTIFICATE = "certificate"    # 证书
    CUSTOM = "custom"              # 自定义


class Audience(Enum):
    """目标受众"""
    INTERNAL = "internal"       # 内部
    EXTERNAL = "external"       # 外部
    EXECUTIVE = "executive"     # 高管
    TECHNICAL = "technical"     # 技术
    GENERAL = "general"         # 通用
    CLIENT = "client"           # 客户
    GOVERNMENT = "government"   # 政府


class Importance(Enum):
    """重要程度"""
    NORMAL = "normal"
    IMPORTANT = "important"
    CRITICAL = "critical"


class OutputFormat(Enum):
    """输出格式"""
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PDF = "pdf"


@dataclass
class DocumentIntent:
    """文档意图 - 从自然语言中提取"""
    document_type: DocumentType = DocumentType.CUSTOM
    audience: Audience = Audience.GENERAL
    importance: Importance = Importance.NORMAL
    output_format: OutputFormat = OutputFormat.DOCX
    title: str = ""
    subject: str = ""
    keywords: list = field(default_factory=list)
    style_hints: list = field(default_factory=list)
    language: str = "zh-CN"
    requires_brand_compliance: bool = False
    requires_print_ready: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "document_type": self.document_type.value,
            "audience": self.audience.value,
            "importance": self.importance.value,
            "output_format": self.output_format.value,
            "title": self.title,
            "subject": self.subject,
            "keywords": self.keywords,
            "style_hints": self.style_hints,
            "language": self.language,
            "requires_brand_compliance": self.requires_brand_compliance,
            "requires_print_ready": self.requires_print_ready,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class DocumentContext:
    """文档上下文 - 完整的文档环境信息"""
    intent: DocumentIntent = field(default_factory=DocumentIntent)
    source_file: Optional[str] = None
    template_id: Optional[str] = None
    design_system_id: Optional[str] = None
    custom_data: dict = field(default_factory=dict)
    user_preferences: dict = field(default_factory=dict)
    enterprise_rules: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.to_dict(),
            "source_file": self.source_file,
            "template_id": self.template_id,
            "design_system_id": self.design_system_id,
            "custom_data": self.custom_data,
            "metadata": self.metadata,
        }


# ===== 意图识别规则 =====

# 文档类型关键词映射
DOCUMENT_TYPE_KEYWORDS = {
    DocumentType.REPORT: ["报告", "汇报", "总结报告", "report", "调研报告", "考察报告"],
    DocumentType.CONTRACT: ["合同", "协议", "契约", "contract", "协议书", "补充协议"],
    DocumentType.PROPOSAL: ["标书", "方案", "投标", "proposal", "招标", "应标", "建议书"],
    DocumentType.RESUME: ["简历", "履历", "resume", "cv", "求职", "个人简介"],
    DocumentType.INVOICE: ["发票", "收据", "invoice", "报销", "账单"],
    DocumentType.MEMO: ["备忘录", "便签", "memo", "通知", "内部通知"],
    DocumentType.LETTER: ["信函", "公函", "letter", "函件", "邀请函", "感谢信"],
    DocumentType.PRESENTATION: ["演示", "演讲", "汇报", "presentation", "slides", "PPT"],
    DocumentType.SPREADSHEET: ["表格", "数据表", "spreadsheet", "统计表", "清单"],
    DocumentType.MANUAL: ["手册", "指南", "manual", "操作指南", "用户手册", "说明书"],
    DocumentType.POLICY: ["制度", "规范", "policy", "管理办法", "规章制度"],
    DocumentType.ANALYSIS: ["分析", "评估", "analysis", "研究", "洞察"],
    DocumentType.PLAN: ["计划", "规划", "plan", "方案", "路线图"],
    DocumentType.SUMMARY: ["总结", "概要", "summary", "小结", "回顾"],
    DocumentType.CERTIFICATE: ["证书", "证明", "certificate", "资质", "授权书"],
}

# 受众关键词映射
AUDIENCE_KEYWORDS = {
    Audience.EXECUTIVE: ["高管", "领导", "CEO", "董事会", "总裁", "总监", "管理层"],
    Audience.TECHNICAL: ["技术", "开发", "工程师", "架构", "tech", "dev"],
    Audience.CLIENT: ["客户", "甲方", "合作方", "partner", "customer"],
    Audience.GOVERNMENT: ["政府", "监管", "主管部门", "gov"],
    Audience.EXTERNAL: ["外部", "公开", "对外", "public"],
    Audience.INTERNAL: ["内部", "团队", "部门", "对内"],
}

# 重要程度关键词
IMPORTANCE_KEYWORDS = {
    Importance.CRITICAL: ["关键", "紧急", "重要", "critical", "urgent", "加急", "特急"],
    Importance.IMPORTANT: ["注意", "关注", "important", "重点"],
}

# 输出格式关键词
FORMAT_KEYWORDS = {
    OutputFormat.PPTX: ["PPT", "pptx", "演示文稿", "幻灯片", "slides"],
    OutputFormat.XLSX: ["Excel", "xlsx", "电子表格", "数据表", "spreadsheet"],
    OutputFormat.PDF: ["PDF", "pdf", "打印", "正式版"],
    OutputFormat.DOCX: ["Word", "docx", "文档", "文档"],
}


class IntentParser:
    """意图解析器 - 从自然语言提取文档意图"""

    def __init__(self):
        self._type_patterns = self._compile_patterns(DOCUMENT_TYPE_KEYWORDS)
        self._audience_patterns = self._compile_patterns(AUDIENCE_KEYWORDS)
        self._importance_patterns = self._compile_patterns(IMPORTANCE_KEYWORDS)
        self._format_patterns = self._compile_patterns(FORMAT_KEYWORDS)

    @staticmethod
    def _compile_patterns(keyword_map: dict) -> list:
        """编译关键词为正则模式"""
        patterns = []
        for key, words in keyword_map.items():
            for word in words:
                patterns.append((key, re.compile(re.escape(word), re.IGNORECASE)))
        return patterns

    def parse(self, text: str) -> DocumentIntent:
        """解析自然语言，提取文档意图"""
        intent = DocumentIntent()

        # 1. 识别文档类型
        type_scores = {}
        for doc_type, pattern in self._type_patterns:
            matches = pattern.findall(text)
            if matches:
                type_scores[doc_type] = type_scores.get(doc_type, 0) + len(matches)

        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            intent.document_type = best_type
            intent.confidence += 0.3

        # 2. 识别受众
        audience_scores = {}
        for audience, pattern in self._audience_patterns:
            matches = pattern.findall(text)
            if matches:
                audience_scores[audience] = audience_scores.get(audience, 0) + len(matches)

        if audience_scores:
            intent.audience = max(audience_scores, key=audience_scores.get)
            intent.confidence += 0.2

        # 3. 识别重要程度
        for importance, pattern in self._importance_patterns:
            if pattern.search(text):
                intent.importance = importance
                intent.confidence += 0.15
                break

        # 4. 识别输出格式
        for fmt, pattern in self._format_patterns:
            if pattern.search(text):
                intent.output_format = fmt
                intent.confidence += 0.15
                break

        # 5. 提取标题 (引号内容或"关于XXX的"模式)
        title_match = re.search(r'[《"「](.+?)[》"」]', text)
        if title_match:
            intent.title = title_match.group(1)
            intent.confidence += 0.1
        else:
            about_match = re.search(r'关于(.+?)的', text)
            if about_match:
                intent.title = about_match.group(1)
                intent.confidence += 0.1

        # 6. 检测品牌合规需求
        brand_keywords = ["品牌", "规范", "合规", "企业标准", "brand", "compliance"]
        for kw in brand_keywords:
            if kw.lower() in text.lower():
                intent.requires_brand_compliance = True
                intent.confidence += 0.05
                break

        # 7. 检测打印需求
        print_keywords = ["打印", "印刷", "出版", "print", "正式版"]
        for kw in print_keywords:
            if kw.lower() in text.lower():
                intent.requires_print_ready = True
                intent.confidence += 0.05
                break

        # 8. 默认格式推理
        if intent.document_type == DocumentType.PRESENTATION and intent.output_format != OutputFormat.PPTX:
            intent.output_format = OutputFormat.PPTX
        elif intent.document_type == DocumentType.SPREADSHEET and intent.output_format != OutputFormat.XLSX:
            intent.output_format = OutputFormat.XLSX
        elif intent.requires_print_ready and intent.output_format != OutputFormat.PDF:
            intent.output_format = OutputFormat.PDF

        # 置信度上限
        intent.confidence = min(intent.confidence, 1.0)

        logger.info(f"意图解析完成: type={intent.document_type.value}, "
                     f"audience={intent.audience.value}, "
                     f"format={intent.output_format.value}, "
                     f"confidence={intent.confidence:.2f}")

        return intent

    def quick_type(self, text: str) -> DocumentType:
        """快速获取文档类型"""
        intent = self.parse(text)
        return intent.document_type
