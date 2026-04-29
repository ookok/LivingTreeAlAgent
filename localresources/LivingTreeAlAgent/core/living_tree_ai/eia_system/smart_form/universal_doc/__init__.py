"""
通用智能文档协作系统 - 核心模块

核心理念：将传统的"填写表单 → 生成文档"模式，
升级为"智能文档编辑 + 结构化数据存储"的一体化体验。

文档即数据库 - 无论环评报告、可研报告还是项目建议书，都能得到一致的智能体验。
"""

from .universal_template_engine import (
    # 模板引擎
    UniversalDocumentTemplate,
    TemplateSchema,
    DocumentSection,
    SectionField,
    TemplateCapability,
    get_template_engine,
    load_template_async,
)

from .smart_field_renderer import (
    # 字段渲染器
    SmartFieldRenderer,
    FieldRenderConfig,
    FieldType,
    render_field_async,
    render_form_async,
)

from .collaborative_document_engine import (
    # 协作引擎
    CollaborativeDocumentEngine,
    Collaborator,
    DocumentOperation,
    OperationType,
    ConflictResolution,
    get_collaborative_engine,
)

from .document_type_registry import (
    # 文档类型注册
    DocumentTypeRegistry,
    DocumentTypeInfo,
    DocumentCategory,
    register_document_type,
    get_document_types,
)

from .document_exporter import (
    # 导出引擎
    DocumentExporter,
    ExportFormat,
    DocumentExporterConfig,
    export_document_async,
    get_exporter,
)

from .universal_doc_controller import (
    # 主控制器
    UniversalDocController,
    UniversalDocConfig,
    DocumentStatus,
    Document,
    Section,
    Field,
    create_universal_doc,
    get_universal_controller,
)


__all__ = [
    # 模板引擎
    "UniversalDocumentTemplate",
    "TemplateSchema",
    "DocumentSection",
    "SectionField",
    "TemplateCapability",
    "get_template_engine",
    "load_template_async",

    # 字段渲染器
    "SmartFieldRenderer",
    "FieldRenderConfig",
    "FieldType",
    "render_field_async",
    "render_form_async",

    # 协作引擎
    "CollaborativeDocumentEngine",
    "Collaborator",
    "DocumentOperation",
    "OperationType",
    "ConflictResolution",
    "get_collaborative_engine",

    # 文档类型注册
    "DocumentTypeRegistry",
    "DocumentTypeInfo",
    "DocumentCategory",
    "register_document_type",
    "get_document_types",

    # 导出引擎
    "DocumentExporter",
    "ExportFormat",
    "DocumentExporterConfig",
    "export_document_async",
    "get_exporter",

    # 主控制器
    "UniversalDocController",
    "UniversalDocConfig",
    "DocumentStatus",
    "Document",
    "Section",
    "Field",
    "create_universal_doc",
    "get_universal_controller",
]