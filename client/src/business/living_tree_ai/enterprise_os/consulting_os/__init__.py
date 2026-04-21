"""
咨询项目智能工作台 (Consulting OS)

以"项目"为中心的咨询公司业务管理系统。

核心定位：
- 项目是核心资产，企业只是项目的承载背景
- 文档是交付物，项目是组织单元
- 知识是沉淀，模板是复用形式

三层架构：
1. 企业维度（背景层） - 客户档案、合规画像
2. 项目维度（核心层） - 项目管理、工作流、团队
3. 文档维度（交付层） - 交付物、版本、状态

商务价值：
- 单个项目人天减少50%
- 项目周期缩短40%
- 知识沉淀和复用
"""

from .project_core import (
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
)

from .client_management import (
    ClientType,
    ClientLevel,
    ComplianceLevel,
    RelationType,
    Client,
    ComplianceProfile,
    ClientRelation,
    ClientAnalysis,
    ClientPortrait,
    ClientMatch,
    ClientService,
    ClientDeduplicationService,
    ClientRecommendationEngine,
    ClientAnalysisReportGenerator,
    get_client_service,
)

from .document_delivery import (
    DocumentType,
    DocumentStatus,
    DocumentRelationType,
    ApprovalStatus,
    ApprovalLevel,
    Document,
    DocumentVersion,
    DocumentRelation,
    ApprovalRecord,
    ReviewComment,
    DeliveryPackage,
    DocumentWorkflow,
    DocumentService,
    get_document_service,
)

from .project_finance import (
    QuotationStatus,
    InvoiceStatus,
    PaymentStatus,
    TaxRate,
    PriceComponent,
    QuotationItem,
    Quotation,
    Invoice,
    PaymentRecord,
    ProjectFinance,
    QuotationEngine,
    FinanceService,
    get_finance_service,
)

from .client_portal import (
    PortalUserRole,
    PortalPermission,
    PortalAccessLevel,
    PortalUser,
    PortalProject,
    PortalDocument,
    PortalMessage,
    PortalActivity,
    PortalAccessManager,
    ClientPortalService,
    get_portal_service,
)

from .knowledge_mining import (
    KnowledgeType,
    ExtractionMethod,
    TemplateQuality,
    KnowledgeUnit,
    BestPractice,
    TemplatePattern,
    ProjectSimilarity,
    KnowledgeMiningEngine,
    TemplateOptimizer,
    SimilarityAnalyzer,
    get_knowledge_engine,
)

from .smart_quotation import (
    PricingModel,
    ComplexityLevel,
    QuotationFactors,
    PriceComponent as SQPriceComponent,
    HistoricalReference,
    ProjectAnalyzer,
    SmartQuotationEngine,
    get_quotation_engine,
)
