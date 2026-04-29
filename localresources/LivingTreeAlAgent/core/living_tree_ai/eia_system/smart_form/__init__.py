"""
智能表单系统 - 模块初始化

核心理念：从"填表"到"核验"
业主不再被动填写，而是核对和确认AI从文档中提取的数据

业主上传文档 → AI解析 → 提取关键信息 → 生成预填表单 → 业主核对修改

包含组件：
- document_form_extractor: 文档解析引擎
- wysiwyg_form_generator: 所见即所得表单生成器
- dynamic_form_generator: 动态表单模板生成器
- form_data_synchronizer: P2P数据同步器
- smart_form_controller: 主控制器
"""

# 数据模型
from .document_form_extractor import (
    DocumentType,
    ExtractionConfidence,
    ExtractedField,
    ValidationResult,
    ExtractionResult,
    DocumentTypeIdentifier,
    AIExtractEngine,
    KnowledgeBaseValidator,
    DocumentFormExtractor,
    get_extractor,
    extract_form_data_async,
)

# 表单生成
from .wysiwyg_form_generator import (
    WYSIWYGFormGenerator,
    FieldHTMLGenerator,
    generate_form_html,
    generate_minimal_form,
    get_generator,
)

# 动态生成
from .dynamic_form_generator import (
    FormCategory,
    FieldDefinition,
    FormTemplate,
    IndustryKnowledgeBase,
    DynamicFormGenerator,
    FormValidationEngine,
    get_dynamic_generator,
    generate_dynamic_form_async,
)

# 数据同步
from .form_data_synchronizer import (
    DataSource,
    FormDataChunk,
    SyncMetadata,
    SyncResult,
    DataEncryptor,
    P2PStorageInterface,
    FormDataSynchronizer,
    FormChangeTracker,
    get_synchronizer,
    get_tracker,
    save_form_data_async,
    load_form_data_async,
)

# 主控制器
from .smart_form_controller import (
    SmartFormMode,
    FormStatus,
    SmartFormSession,
    SmartFormConfig,
    SmartFormController,
    SmartFormAPI,
    SmartFormWebSocket,
    get_smart_form_controller,
    create_form_session,
    process_uploaded_document,
    submit_form_data,
)

__all__ = [
    # 数据模型
    "DocumentType",
    "ExtractionConfidence",
    "ExtractedField",
    "ValidationResult",
    "ExtractionResult",
    "DocumentTypeIdentifier",
    "AIExtractEngine",
    "KnowledgeBaseValidator",
    "DocumentFormExtractor",
    "get_extractor",
    "extract_form_data_async",

    # 表单生成
    "WYSIWYGFormGenerator",
    "FieldHTMLGenerator",
    "generate_form_html",
    "generate_minimal_form",
    "get_generator",

    # 动态生成
    "FormCategory",
    "FieldDefinition",
    "FormTemplate",
    "IndustryKnowledgeBase",
    "DynamicFormGenerator",
    "FormValidationEngine",
    "get_dynamic_generator",
    "generate_dynamic_form_async",

    # 数据同步
    "DataSource",
    "FormDataChunk",
    "SyncMetadata",
    "SyncResult",
    "DataEncryptor",
    "P2PStorageInterface",
    "FormDataSynchronizer",
    "FormChangeTracker",
    "get_synchronizer",
    "get_tracker",
    "save_form_data_async",
    "load_form_data_async",

    # 主控制器
    "SmartFormMode",
    "FormStatus",
    "SmartFormSession",
    "SmartFormConfig",
    "SmartFormController",
    "SmartFormAPI",
    "SmartFormWebSocket",
    "get_smart_form_controller",
    "create_form_session",
    "process_uploaded_document",
    "submit_form_data",
]
