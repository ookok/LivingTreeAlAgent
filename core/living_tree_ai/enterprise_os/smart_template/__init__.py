"""
智能模板模块 (Smart Template Module)

实现"文档 → 模板 + 数据 → 新文档"的全自动流程。
无需手动制作模板，AI 自动推理模板骨架和动态数据。

核心模块：
1. document_struct_extractor - 文档结构提取器（Word → JSON AST）
2. ai_template_engine - AI 推理模板引擎（JSON AST → template_config.json）
3. data_driven_renderer - 数据驱动渲染器（template_config + data → 新文档）
4. smart_template_service - 智能模板服务（统一入口）

使用示例：
```python
from smart_template import SmartTemplateService

service = SmartTemplateService()

# 1. 从定稿文档生成模板（零手动）
template = await service.generate_template(
    source_doc="环评报告定稿.docx",
    document_type="environmental_assessment",
    domain_hint="环保"
)

# 2. 生成新报告
result = await service.generate_report(
    template_config=template,
    project_data={
        "company_name": "XX化工有限公司",
        "monitoring_data": [...],
    },
    output_path="output/新项目环评报告.docx"
)
```
"""

# ==================== 文档结构提取器 ====================
from .document_struct_extractor import (
    NodeType,
    ContentType,
    StyleInfo,
    ASTNode,
    DocumentAST,
    TableStructure,
    DocumentStructExtractor,
    get_struct_extractor,
    extract_document_structure,
    extract_to_json,
)

# ==================== AI 推理模板引擎 ====================
from .ai_template_engine import (
    ContentCategory,
    VariablePattern,
    TemplateBlock,
    TableTemplate,
    TemplateConfig,
    AITemplateEngine,
    get_ai_template_engine,
    infer_template,
)

# ==================== 数据驱动渲染器 ====================
from .data_driven_renderer import (
    OutputFormat,
    RenderContext,
    RenderResult,
    DataDrivenRenderer,
    get_data_driven_renderer,
    render_document,
)

# ==================== 智能模板服务 ====================
from .smart_template_service import (
    TemplateStatus,
    TemplateMetadata,
    TemplateFeedback,
    GenerationResult,
    SmartTemplateService,
    get_smart_template_service,
    generate_template_from_document,
    generate_report_from_template,
)

# ==================== 统一导出 ====================
__all__ = [
    # 文档结构提取器
    "NodeType",
    "ContentType",
    "StyleInfo",
    "ASTNode",
    "DocumentAST",
    "TableStructure",
    "DocumentStructExtractor",
    "get_struct_extractor",
    "extract_document_structure",
    "extract_to_json",
    # AI 推理模板引擎
    "ContentCategory",
    "VariablePattern",
    "TemplateBlock",
    "TableTemplate",
    "TemplateConfig",
    "AITemplateEngine",
    "get_ai_template_engine",
    "infer_template",
    # 数据驱动渲染器
    "OutputFormat",
    "RenderContext",
    "RenderResult",
    "DataDrivenRenderer",
    "get_data_driven_renderer",
    "render_document",
    # 智能模板服务
    "TemplateStatus",
    "TemplateMetadata",
    "TemplateFeedback",
    "GenerationResult",
    "SmartTemplateService",
    "get_smart_template_service",
    "generate_template_from_document",
    "generate_report_from_template",
]