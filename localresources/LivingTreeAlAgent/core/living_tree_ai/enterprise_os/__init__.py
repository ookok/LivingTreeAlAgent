"""
企业全生命周期智能合规与运营数字中台 (Enterprise OS)
=================================================

核心理念：企业的"数字合伙人"
- 预见性运营：提前预见问题并自动解决
- 自适应进化：随企业成长自动调整服务
- 价值创造：不仅避免损失，更能创造价值
- 生态连接：连接企业所需的一切资源

覆盖生命周期：
- 孕育与诞生（工商注册、税务登记）
- 准入与建设（环评、安评、项目申报）
- 运营与生产（排污许可、年度申报）
- 市场与经营（知识产权、合同管理）
- 人力与组织（劳动合同、社保公积金）
- 财税与审计（纳税申报、审计报告）
- 发展升级（高新认证、融资上市）
- 退市与注销（清算注销）

八维数字孪生：
1. 主体身份维度 - 工商、税务、行业、信用、资质身份
2. 物理实体维度 - 场所、设施、环保、安全、信息设施
3. 人员组织维度 - 组织架构、人员花名册、权限体系
4. 业务流程维度 - 核心流程、支持流程、管理流程
5. 资产资源维度 - 有形、无形、金融、数字、关系资产
6. 合规义务维度 - 工商、税务、环保、安全、人社合规
7. 经营数据维度 - 财务、业务、生产、市场人力数据
8. 风险控制维度 - 市场、运营、财务、合规、技术风险
"""

from .enterprise_digital_twin import (
    # 核心模型
    EnterpriseDigitalTwin,
    EnterpriseDimensions,
    IdentityDimension,
    PhysicalDimension,
    PersonnelDimension,
    BusinessProcessDimension,
    AssetDimension,
    ComplianceObligationDimension,
    OperationalDataDimension,
    RiskControlDimension,
    # 工具函数
    get_enterprise_twin,
    create_enterprise_twin_async,
)

from .compliance_knowledge_graph import (
    # 知识图谱
    ComplianceKnowledgeGraph,
    KGNode,
    KGEdge,
    NodeType,
    RelationType,
    ComplianceCheckResult,
    # 查询
    query_compliance_async,
    build_enterprise_graph_async,
)

from .declaration_pipeline import (
    # 申报流水线
    DeclarationPipeline,
    DeclarationTask,
    TaskStep,
    PipelineStatus,
    # 执行
    execute_declaration_async,
    create_pipeline_async,
)

from .gov_site_adapter import (
    # 政府网站适配器
    GovSiteAdapter,
    SiteCapability,
    FormField,
    FormTemplate,
    AutoFillResult,
    # 便捷函数
    get_adapter,
    adapt_site_async,
)

from .risk_early_warning import (
    # 风险预警
    RiskEarlyWarningEngine,
    RiskAlert,
    RiskLevel,
    RiskCategory,
    MonitorSource,
    # 便捷函数
    get_risk_engine,
    check_risks_async,
    subscribe_alerts_async,
)

from .enterprise_os_controller import (
    # 主控制器
    EnterpriseOSController,
    EnterpriseOSConfig,
    LifecycleStage,
    ComplianceTask,
    TaskStatus,
    # 便捷函数
    get_enterprise_os,
    create_enterprise_os_async,
    execute_lifecycle_task_async,
)

# ==================== 企业Profile服务 ====================
from .enterprise_profile_service import (
    # 数据模型
    DataSource,
    DataConfidence,
    DataField,
    AssetNode,
    ComplianceCalendarEvent,
    EnterpriseProfile,
    # 合规日历
    ComplianceCalendarManager,
    # 资产图谱
    AssetGraphManager,
    # Profile服务
    EnterpriseProfileService,
    # 便捷函数
    get_profile_service,
    create_enterprise_profile,
)

# ==================== 政府身份池 ====================
from .identity_pool import (
    # 数据模型
    GovSystemType,
    LoginStatus,
    GovSystemAccount,
    LoginAttempt,
    # 管理器
    IdentityPoolManager,
    # 便捷函数
    get_identity_pool,
)

# ==================== 表单适配器 ====================
from .form_adapter_engine import (
    # 数据模型
    FieldType,
    MappingQuality,
    FormField,
    FieldMapping,
    MappingRule,
    # 引擎
    FormAdapterEngine,
    # 便捷函数
    get_form_adapter,
)

# ==================== 插件注册中心 ====================
from .plugin_registry import (
    # 数据模型
    PluginType,
    PluginStatus,
    PluginInfo,
    PluginInstance,
    PluginMarketItem,
    # 接口
    IDocumentGeneratorPlugin,
    IDeclarationPlugin,
    IDataSyncPlugin,
    IKnowledgePackagePlugin,
    # 注册中心
    PluginRegistry,
    # 便捷函数
    get_plugin_registry,
)

# ==================== 智能路由 ====================
from .intelligent_router import (
    # 数据模型
    TaskType,
    ExecutionMode,
    RoutingDecision,
    TaskIntent,
    RoutingRule,
    RoutingResult,
    HumanReviewTask,
    # 引擎
    IntelligentRouter,
    # 便捷函数
    get_intelligent_router,
)

# ==================== 咨询项目工作台 ====================
from .consulting_os import (
    # 项目管理
    ProjectType,
    ProjectPhase,
    ProjectStatus,
    ProjectPriority,
    Project,
    ProjectMember,
    ProjectTimeline,
    ProjectDeliverable,
    ProjectRelation,
    ProjectService,
    ProjectWorkflow,
    get_project_service,
    # 客户管理
    ClientType,
    ClientLevel,
    ComplianceLevel,
    Client,
    ComplianceProfile,
    ClientRelation,
    ClientService,
    get_client_service,
    # 文档交付
    DocumentType,
    DocumentStatus,
    DocumentRelationType,
    ApprovalStatus,
    Document,
    DocumentVersion,
    DocumentRelation,
    ApprovalRecord,
    DeliveryPackage,
    DocumentService,
    DocumentWorkflow,
    get_document_service,
    # 项目财务
    QuotationStatus,
    InvoiceStatus,
    PaymentStatus,
    Quotation,
    QuotationItem,
    Invoice,
    PaymentRecord,
    ProjectFinance,
    FinanceService,
    QuotationEngine,
    get_finance_service,
    # 客户门户
    PortalUserRole,
    PortalPermission,
    PortalAccessLevel,
    PortalUser,
    PortalProject,
    PortalDocument,
    PortalMessage,
    ClientPortalService,
    get_portal_service,
    # 知识挖掘
    KnowledgeType,
    ExtractionMethod,
    KnowledgeUnit,
    BestPractice,
    TemplatePattern,
    ProjectSimilarity,
    KnowledgeMiningEngine,
    get_knowledge_engine,
    # 智能报价
    PricingModel,
    ComplexityLevel,
    QuotationFactors,
    SmartQuotationEngine,
    ProjectAnalyzer,
    get_quotation_engine,
)

# ==================== 数据获取模块 ====================
from .data_acquisition import (
    # 企业数据获取
    DataSourceType,
    FetchStatus,
    GovernmentSystem,
    EnterpriseBasicInfo,
    EnvironmentalRecord,
    SafetyLicense,
    CreditRiskInfo,
    GovernmentData,
    EnterpriseDataFetcher,
    get_enterprise_fetcher,
    # 项目数据采集
    CollectionChannel,
    DataFormat,
    CollectionStatus,
    ProjectDataItem,
    RawData,
    ProcessedData,
    DataQualityScore,
    ProjectDataCollector,
    DataQualityEngine,
    get_data_collector,
    get_quality_engine,
)

# ==================== 模型计算引擎 ====================
from .model_computing import (
    # 调度器
    ModelType,
    ModelStatus,
    ComputePriority,
    ModelInfo,
    ModelParameter,
    ComputeRequest,
    ComputeResult,
    ModelVersion,
    ModelDispatcher,
    get_model_dispatcher,
    # 排放核算
    EmissionSource,
    PollutantType,
    EmissionFactor,
    CalculatedEmission,
    EmissionCalculator,
    get_emission_calculator,
    # 风险评价
    RiskType,
    RiskLevel,
    RiskScenario,
    RiskConsequence,
    RiskEvaluationResult,
    RiskEvaluator,
    get_risk_evaluator,
    # 工程经济
    CostType,
    CostItem,
    InvestmentEstimate,
    OperatingCost,
    CostBenefitResult,
    EconomicsEngine,
    get_economics_engine,
)

# ==================== 准确性保障 ====================
from .accuracy_assurance import (
    # RAG
    KnowledgeDomain,
    DocumentType as RegDocumentType,
    RetrievalMode,
    KnowledgeChunk,
    RegulationStandard,
    RetrievedKnowledge,
    RAGQuery,
    RAGResult,
    RAGEngine,
    get_rag_engine,
    # 模型校验
    ValidationLevel,
    ValidationStatus,
    ValidationRule,
    ValidationResult,
    ValidatedDocument,
    ModelValidator,
    get_model_validator,
    # 专家复核
    ReviewLevel,
    ReviewStatus,
    ApprovalStatus as ReviewApprovalStatus,
    ReviewTask,
    ReviewComment,
    ApprovalChain,
    ExpertReviewWorkflow,
    get_expert_workflow,
)

# ==================== 智能模板（文档 → 模板 + 数据）====================
from .smart_template import (
    # 文档结构提取器
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
    # AI 推理模板引擎
    ContentCategory,
    VariablePattern,
    TemplateBlock,
    TableTemplate,
    TemplateConfig,
    AITemplateEngine,
    get_ai_template_engine,
    infer_template,
    # 数据驱动渲染器
    OutputFormat,
    RenderContext,
    RenderResult,
    DataDrivenRenderer,
    get_data_driven_renderer,
    render_document,
    # 智能模板服务
    TemplateStatus,
    TemplateMetadata,
    TemplateFeedback,
    GenerationResult,
    SmartTemplateService,
    get_smart_template_service,
    generate_template_from_document,
    generate_report_from_template,
)

# ==================== 智能PDF解析（LLM + 人机校验）====================
from .intelligent_pdf_parser import (
    # 枚举
    ReportType,
    ParseConfidence,
    ParseStatus,
    # 核心解析器
    MonitoringPoint,
    PollutantReading,
    ParsedReport,
    ParseRequest,
    ParseResult,
    IntelligentPDFParser,
    get_intelligent_pdf_parser,
    parse_pdf_report,
    # 自适应解析器
    CompanyProfile,
    ParsingFeedback,
    AdaptiveParser,
    get_adaptive_parser,
    # 校验面板
    ReviewField,
    ReviewResult,
    PDFReviewPanel,
    show_review_dialog,
)


__all__ = [
    # 企业数字孪生
    "EnterpriseDigitalTwin",
    "EnterpriseDimensions",
    "IdentityDimension",
    "PhysicalDimension",
    "PersonnelDimension",
    "BusinessProcessDimension",
    "AssetDimension",
    "ComplianceObligationDimension",
    "OperationalDataDimension",
    "RiskControlDimension",
    "get_enterprise_twin",
    "create_enterprise_twin_async",

    # 合规知识图谱
    "ComplianceKnowledgeGraph",
    "KGNode",
    "KGEdge",
    "NodeType",
    "RelationType",
    "ComplianceCheckResult",
    "query_compliance_async",
    "build_enterprise_graph_async",

    # 申报流水线
    "DeclarationPipeline",
    "DeclarationTask",
    "TaskStep",
    "PipelineStatus",
    "execute_declaration_async",
    "create_pipeline_async",

    # 政府网站适配
    "GovSiteAdapter",
    "SiteCapability",
    "FormField",
    "FormTemplate",
    "AutoFillResult",
    "get_adapter",
    "adapt_site_async",

    # 风险预警
    "RiskEarlyWarningEngine",
    "RiskAlert",
    "RiskLevel",
    "RiskCategory",
    "MonitorSource",
    "get_risk_engine",
    "check_risks_async",
    "subscribe_alerts_async",

    # 主控制器
    "EnterpriseOSController",
    "EnterpriseOSConfig",
    "LifecycleStage",
    "ComplianceTask",
    "TaskStatus",
    "get_enterprise_os",
    "create_enterprise_os_async",
    "execute_lifecycle_task_async",

    # 企业Profile服务
    "DataSource",
    "DataConfidence",
    "DataField",
    "AssetNode",
    "ComplianceCalendarEvent",
    "EnterpriseProfile",
    "ComplianceCalendarManager",
    "AssetGraphManager",
    "EnterpriseProfileService",
    "get_profile_service",
    "create_enterprise_profile",

    # 政府身份池
    "GovSystemType",
    "LoginStatus",
    "GovSystemAccount",
    "LoginAttempt",
    "IdentityPoolManager",
    "get_identity_pool",

    # 表单适配器
    "FieldType",
    "MappingQuality",
    "FormField",
    "FieldMapping",
    "MappingRule",
    "FormAdapterEngine",
    "get_form_adapter",

    # 插件注册中心
    "PluginType",
    "PluginStatus",
    "PluginInfo",
    "PluginInstance",
    "PluginMarketItem",
    "IDocumentGeneratorPlugin",
    "IDeclarationPlugin",
    "IDataSyncPlugin",
    "IKnowledgePackagePlugin",
    "PluginRegistry",
    "get_plugin_registry",

    # 智能路由
    "TaskType",
    "ExecutionMode",
    "RoutingDecision",
    "TaskIntent",
    "RoutingRule",
    "RoutingResult",
    "HumanReviewTask",
    "IntelligentRouter",
    "get_intelligent_router",

    # 咨询项目工作台
    # 项目管理
    "ProjectType",
    "ProjectPhase",
    "ProjectStatus",
    "ProjectPriority",
    "Project",
    "ProjectMember",
    "ProjectTimeline",
    "ProjectDeliverable",
    "ProjectRelation",
    "ProjectService",
    "ProjectWorkflow",
    "get_project_service",
    # 客户管理
    "ClientType",
    "ClientLevel",
    "ComplianceLevel",
    "Client",
    "ComplianceProfile",
    "ClientRelation",
    "ClientService",
    "get_client_service",
    # 文档交付
    "DocumentType",
    "DocumentStatus",
    "DocumentRelationType",
    "ApprovalStatus",
    "Document",
    "DocumentVersion",
    "DocumentRelation",
    "ApprovalRecord",
    "DeliveryPackage",
    "DocumentService",
    "DocumentWorkflow",
    "get_document_service",
    # 项目财务
    "QuotationStatus",
    "InvoiceStatus",
    "PaymentStatus",
    "Quotation",
    "QuotationItem",
    "Invoice",
    "PaymentRecord",
    "ProjectFinance",
    "FinanceService",
    "QuotationEngine",
    "get_finance_service",
    # 客户门户
    "PortalUserRole",
    "PortalPermission",
    "PortalAccessLevel",
    "PortalUser",
    "PortalProject",
    "PortalDocument",
    "PortalMessage",
    "ClientPortalService",
    "get_portal_service",
    # 知识挖掘
    "KnowledgeType",
    "ExtractionMethod",
    "KnowledgeUnit",
    "BestPractice",
    "TemplatePattern",
    "ProjectSimilarity",
    "KnowledgeMiningEngine",
    "get_knowledge_engine",
    # 智能报价
    "PricingModel",
    "ComplexityLevel",
    "QuotationFactors",
    "SmartQuotationEngine",
    "ProjectAnalyzer",
    "get_quotation_engine",

    # 数据获取
    "DataSourceType",
    "FetchStatus",
    "GovernmentSystem",
    "EnterpriseBasicInfo",
    "EnvironmentalRecord",
    "SafetyLicense",
    "CreditRiskInfo",
    "GovernmentData",
    "EnterpriseDataFetcher",
    "get_enterprise_fetcher",
    "CollectionChannel",
    "DataFormat",
    "CollectionStatus",
    "ProjectDataItem",
    "RawData",
    "ProcessedData",
    "DataQualityScore",
    "ProjectDataCollector",
    "DataQualityEngine",
    "get_data_collector",
    "get_quality_engine",

    # 模型计算
    "ModelType",
    "ModelStatus",
    "ComputePriority",
    "ModelInfo",
    "ModelParameter",
    "ComputeRequest",
    "ComputeResult",
    "ModelVersion",
    "ModelDispatcher",
    "get_model_dispatcher",
    "EmissionSource",
    "PollutantType",
    "EmissionFactor",
    "CalculatedEmission",
    "EmissionCalculator",
    "get_emission_calculator",
    "RiskType",
    "RiskLevel",
    "RiskScenario",
    "RiskConsequence",
    "RiskEvaluationResult",
    "RiskEvaluator",
    "get_risk_evaluator",
    "CostType",
    "CostItem",
    "InvestmentEstimate",
    "OperatingCost",
    "CostBenefitResult",
    "EconomicsEngine",
    "get_economics_engine",

    # 准确性保障
    "KnowledgeDomain",
    "RegDocumentType",
    "RetrievalMode",
    "KnowledgeChunk",
    "RegulationStandard",
    "RetrievedKnowledge",
    "RAGQuery",
    "RAGResult",
    "RAGEngine",
    "get_rag_engine",
    "ValidationLevel",
    "ValidationStatus",
    "ValidationRule",
    "ValidationResult",
    "ValidatedDocument",
    "ModelValidator",
    "get_model_validator",
    "ReviewLevel",
    "ReviewStatus",
    "ReviewApprovalStatus",
    "ReviewTask",
    "ReviewComment",
    "ApprovalChain",
    "ExpertReviewWorkflow",
    "get_expert_workflow",

    # 智能模板
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
    "ContentCategory",
    "VariablePattern",
    "TemplateBlock",
    "TableTemplate",
    "TemplateConfig",
    "AITemplateEngine",
    "get_ai_template_engine",
    "infer_template",
    "OutputFormat",
    "RenderContext",
    "RenderResult",
    "DataDrivenRenderer",
    "get_data_driven_renderer",
    "render_document",
    "TemplateStatus",
    "TemplateMetadata",
    "TemplateFeedback",
    "GenerationResult",
    "SmartTemplateService",
    "get_smart_template_service",
    "generate_template_from_document",
    "generate_report_from_template",

    # 智能PDF解析
    "ReportType",
    "ParseConfidence",
    "ParseStatus",
    "MonitoringPoint",
    "PollutantReading",
    "ParsedReport",
    "ParseRequest",
    "ParseResult",
    "IntelligentPDFParser",
    "get_intelligent_pdf_parser",
    "parse_pdf_report",
    "CompanyProfile",
    "ParsingFeedback",
    "AdaptiveParser",
    "get_adaptive_parser",
    "ReviewField",
    "ReviewResult",
    "PDFReviewPanel",
    "show_review_dialog",
]
