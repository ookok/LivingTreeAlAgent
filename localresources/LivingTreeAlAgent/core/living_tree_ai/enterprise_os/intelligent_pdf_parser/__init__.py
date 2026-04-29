"""
智能PDF解析系统 (Intelligent PDF Parser)

三层解析架构 + 自适应学习，实现高精度的免费自动化。

核心模块：
1. intelligent_pdf_parser.py - 核心解析器（LLM + 传统库 + 人机校验）
2. adaptive_parser.py - 自适应解析器（针对不同检测公司）
3. pdf_review_panel.py - 人机校验界面

使用示例：
```python
from intelligent_pdf_parser import (
    IntelligentPDFParser,
    AdaptiveParser,
    ReportType,
    parse_pdf_report
)

# 1. 创建解析器
parser = IntelligentPDFParser(llm_callable=my_llm)

# 2. 解析PDF
result = await parser.parse(ParseRequest(
    file_path="验收监测报告.pdf",
    report_type_hint=ReportType.ACCEPTANCE_MONITORING,
    require_human_review=True
))

# 3. 判断结果
if result.requires_review:
    # 弹出校验界面
    show_review_dialog(result.review_data, "验收监测报告.pdf")
else:
    # 自动入库
    save_to_database(result.parsed_report)
```

## 自适应学习

```python
# 4. 记录反馈，持续优化
adaptive = get_adaptive_parser()
await adaptive.learn_from_correction(
    company_name="华测检测",
    field_key="company_name",
    ai_value="错误的企业名",
    corrected_value="正确的企业名"
)
```
"""

# ==================== 核心解析器 ====================
from .intelligent_pdf_parser import (
    # 枚举
    ReportType,
    ParseConfidence,
    ParseStatus,
    # 数据类
    MonitoringPoint,
    PollutantReading,
    ParsedReport,
    ParseRequest,
    ParseResult,
    # 解析器
    IntelligentPDFParser,
    get_intelligent_pdf_parser,
    parse_pdf_report,
)

# ==================== 自适应解析器 ====================
from .adaptive_parser import (
    # 数据类
    CompanyProfile,
    ParsingFeedback,
    # 解析器
    AdaptiveParser,
    get_adaptive_parser,
)

# ==================== 校验面板 ====================
from .pdf_review_panel import (
    ReviewField,
    ReviewResult,
    PDFReviewPanel,
    show_review_dialog,
)

# ==================== 统一导出 ====================
__all__ = [
    # 枚举
    "ReportType",
    "ParseConfidence",
    "ParseStatus",

    # 核心解析器
    "MonitoringPoint",
    "PollutantReading",
    "ParsedReport",
    "ParseRequest",
    "ParseResult",
    "IntelligentPDFParser",
    "get_intelligent_pdf_parser",
    "parse_pdf_report",

    # 自适应解析器
    "CompanyProfile",
    "ParsingFeedback",
    "AdaptiveParser",
    "get_adaptive_parser",

    # 校验面板
    "ReviewField",
    "ReviewResult",
    "PDFReviewPanel",
    "show_review_dialog",
]