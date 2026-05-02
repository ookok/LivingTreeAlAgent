from .life_engine import (
    LifeEngine,
    Cell,
    PerceptionCell, MemoryCell, ReasoningCell,
    LearningCell, ActionCell,
    Intent, IntentType, Context,
    TaskNode, TaskPlan, ModelBinding,
    ExecutionResult, LearningRecord,
    Stimulus, Response,
)
from .session.manager import (
    SessionManager, SessionInfo, MessageRecord,
    ContextEntry, UnifiedContext,
    get_session_manager,
)
from .knowledge.wiki import (
    DocumentChunk, PaperMetadata,
    LLMDocumentParser, PaperParser, CodeExtractor,
    FeedbackManager, FeedbackRecord, TripletScore,
    KnowledgeGraphSelfEvolver, ShortcutEdge,
    HybridRetriever, RetrievalResult,
)
from .tools.registry import (
    ToolRegistry, ToolDispatcher, ToolDef, SCHEMA, register_all_tools,
)
from .tools.builtin import register_all_builtin_tools

from .agent import (
    MessageSyncService, MessageChannel, MessageStatus, SyncMessage, SendResult,
    ChannelHandler, SMSHandler, WeComHandler, EmailHandler, LANHandler,
    MessageQueue, get_message_sync_service,
    AgentProtocol, AgentMessage, Conversation, MessageType, MessagePriority,
    ProtocolRegistry, get_protocol_registry,
    AgentCapabilities,
    WorkflowStatus, NodeType, WorkflowNode, WorkflowContext, WorkflowResult,
    BaseWorkflow, SequentialWorkflow, DecisionWorkflow, ParallelWorkflow,
    WorkflowBuilder, WorkflowEngine, register_workflow, execute_workflow,
    get_workflow_engine,
    AutomationJob, WorkflowScheduler, AgentActionExecutor, AutoWorkflowGenerator,
    get_workflow_scheduler, get_agent_executor,
)

from .evolution import (
    EvolutionEngine, SelfLearningEngine, Reflector, Optimizer, Repairer,
    AdaptiveCompressionStrategy, EvolutionController, PatternLibrary, SafetyGate,
    ABTestEngine, InteractionSample, PerformanceMetric, KnowledgePattern,
    EvolutionStrategy, ExecutionRecord as EvoExecutionRecord,
    ReflectionReport, ImprovementProposal, EvolutionStatus,
    LearningType, MetricType,
    ChainOfThoughtDistiller, ChainTemplate, ReasoningRecord, ReasoningStep,
    ReasoningType,
    MultiModelComparison, ComparisonMetric, ModelOutput, ComparisonResult,
    AutoModelSelector, IntentClassifier, ComplexityEstimator, PerformanceTracker,
    TaskType, TaskComplexity, ModelCapability, ModelRecommendation,
    KnowledgeConsistencyVerifier, ConsistencyChecker, VotingDecider,
    MultiModelInferrer, ConsensusLevel, VerificationStatus,
    ModelResponse, ConsistencyResult, VerificationReport,
)

from .skills import (
    SkillInfo, SkillRepository, SkillMatcher, SkillDependencyGraph,
    SkillUpdater, ContextQuery, SkillStatus,
    SkillCategory, AgentType, OutputType, SkillEvolution,
    SkillInput, SkillOutput, SkillManifest, SkillRegistry,
    SkillMdLoader, SkillExecutor,
    SlashCommand, SlashCommandRegistry,
    ContextAwareLoader,
    CronScheduler, CronParser, NaturalLanguageScheduler,
    ScheduledTask as CronScheduledTask,
    AutoEvolutionSkill, PatternDetector, SkillSeedGenerator, SkillSeed,
    EvolutionCandidate, InteractionPattern,
    HonchoUserModeling, UserProfile, UserPreference, Dialect, CommunicationStyle,
    DecompositionSkillType, BaseDecompositionSkill,
    ArchitectureDesignerSkill, CodeRefactorerSkill, TaskSplitterProSkill,
    DecompositionSkillFactory, get_architecture_designer,
    get_code_refactorer, get_task_splitter, register_decomposition_skills,
    AgentSkillsInitializer,
)

from .memory import (
    MemoryStore, IMemorySystem, MemoryQuery, MemoryItem, MemoryResult,
    MemoryLevel, SimpleVectorDB, SimpleGraphDB, SessionStore,
    RelevanceScorer, ImportanceScorer, QueryPlanner,
)

from .memory.graph_db import (
    KnowledgeGraph, Entity, Relation, EntityType, RelationType,
    get_knowledge_graph,
)

from .model import (
    UnifiedModelRouter, UnifiedModelClient, ModelRegistry, ModelHealthChecker,
    CircuitBreaker, LoadBalancer, ModelInfo, ComputeTier, TaskCategory,
    RoutingStrategy, EndpointHealth, AIResponse, CostBudget, TierEndpoint,
    get_model_router, get_model_client,
)

from .intent import (
    IntentParser, ParsedIntent, IntentTracker, IntentSimilarity,
    DialogTurn, SentimentLabel, LanguageHint,
)

from .planning import (
    TaskPlanner, TaskDecomposer,
    ExecutionPlanner, RetryManager, MilestoneTracker,
    COT_TEMPLATES,
)

from .context import (
    ContextAssembler, ContextCompressor, ContextPrioritizer,
    PromptTemplateEngine, TokenCounter,
    AssembledContext, ContextChunk, ContextPriority,
)

from .plugins import (
    PluginManager, Plugin, PluginManifest, PluginStatus,
    PluginSandbox, PluginDiscovery, DependencyResolver,
)

from .world_model import (
    StatePredictor, OutcomeSimulator, BayesianUpdater,
    ScenarioTree, ScenarioNode, CausalAnalyzer,
    PredictedOutcome, ActualOutcome, Action as WorldAction,
    ActionType as WorldActionType, WorldState,
)

from .observability import (
    StructuredLogger, LogEntry, LogLevel, get_logger,
    RequestTracer, TraceContext, Span, get_tracer,
    MetricsCollector, HealthMonitor, ErrorLevel, ErrorRecord,
    RecoveryAttempt, APICallMetrics, get_metrics,
)

from .auditor import (
    AuditorAgent, AuditResult, AuditIssue,
    AuditIssueType, IssueSeverity, get_auditor_agent,
    BlacklistManager, BlacklistEntry,
)

from .formal_verification import (
    FormalVerifier, Constraint, ConstraintType,
    FVVerificationStatus, VerificationResult as FVVerificationResult,
    VerificationReport as FVVerificationReport,
    RulesEngine, BusinessRule, RuleExecutionResult,
    EIA_Rules, FinancialRules,
)

from .sms_gateway import (
    SmsGateway, get_sms_gateway, SmsChannel, ChannelStatus,
    ChannelConfig, EmailConfig, SmsResult, GatewayStats,
    setup_monthly_reset,
)

from .document_parser import (
    DocumentParser, DocumentParserFactory, UnstructuredDocumentParser,
    parse_document,
    DocumentType, SectionType,
    ParsedDocument, DocumentSection, TableData, TableCell, EntityRelation,
)

from .document_generator import (
    DocumentGenerator, DocumentGenerationResult,
    ReportSchema, ReportSection, ReportType, ContentType,
    SchemaValidator, ReportTemplates,
)

from .map_agent import (
    MapGateway, get_map_gateway, MapProvider, ServiceType, CoordinateSystem,
    ProviderConfig, CacheEntry,
    MAP_CONFIG, get_api_key, get_secret_key, get_base_url, get_timeout,
    is_debug_enabled, update_config, validate_config, print_config_summary,
    MapAgentController, MapInteractionMode, get_map_agent_controller,
    PerceptionTool, SpatialIdentity,
    GeometryTool, GeometryOperation,
    OverlayAnalysisTool, OverlayResult,
    MobilityTool, RouteAnalysisResult,
    ExportTool, ExportFormat,
)

from .sica_engine import (
    SICACodeGenerator, CodeGenerationResult, TestResult,
    SelfReflectionEngine, ReflectionResult,
)

from .software_manager import (
    SoftwareManager, MetadataManager, BootstrapInstaller,
    SystemScanner, SoftwareManagerBridge, WebChannelSetup,
    PackageManager, PackageInfo, InstallStatus,
)

from .evolution_extra import (
    EvolutionSystem,
    ExperienceSystem, Experience, SkillUsage, HumanFeedback,
    SkillEvaluator as ExtraSkillEvaluator, Skill as ExtraSkill,
    SkillMetric, SkillExample,
    SkillCategory as ExtraSkillCategory, SkillStatus as ExtraSkillStatus,
    PolicyEngine as ExtraPolicyEngine, Policy as ExtraPolicy,
    PolicyRule, PolicyInsight, PolicyType as ExtraPolicyType,
    PolicyAction as ExtraPolicyAction,
    EvolutionLogger, EvolutionEvent, EvolutionPhase,
    EvolutionEventType, EvolutionImpact,
    SkillDiscoveryEngine as ExtraSkillDiscoveryEngine,
    PatternMatch, DiscoveryResult,
)

from .tool_management import (
    ToolManifest, ToolStatus as TmToolStatus, ToolExecutionResult,
    InputSpec, OutputSpec, ValidationResult as TmValidationResult,
    DocumentSlot, SandboxConfig, ToolPackage,
    ToolResolver, ToolSandbox, ToolValidator,
    ToolSlotter, ToolDownloader, EnvironmentalToolRegistry,
)

from .tool_discovery import (
    ToolDiscoveryEngine, ToolInfo, ToolSearchResult, ToolSource,
)

from .consulting_engineer import (
    ConsultingEngineer, ProjectContext,
    ProjectType as CEProjectType,
    TaskType as CETaskType, TaskResult as CETaskResult,
    get_consulting_engineer,
    create_eia_project, create_feasibility_project,
)

from .cells import (
    Cell as CellsCell,
    CellType as CellsCellType,
    CellState, EnergyMonitor,
    Signal, SignalType, SignalPriority,
    CausalReasoningCell, SymbolicReasoningCell,
    HippocampusCell, NeocortexCell,
    EWCCell, ProgressiveCell, MetaLearningCell,
    MultimodalCell, IntentCell,
    CodeCell, ToolCell, GenerationCell,
    PredictionCell, TimeSeriesPredictor, ResourcePredictor, HealthPredictor,
    ScenarioType, PredictionMethod,
    ModelAssemblyLine, CellRegistry,
    EmergenceEngine, SelfOrganization,
    EvolutionEngine as CellsEvolutionEngine, CellDivision, NaturalSelection,
    NeuralSymbolicIntegrator, BayesianPosterior, BeliefState, InferenceMode,
    SelfConsciousness, SelfModel, ConsciousnessLevel, ReflectionMode,
    ImmuneSystem, Threat, Antibody, ThreatLevel, ThreatType, DefenseStatus,
    MetabolicSystem, ResourcePool, EnergyLevel, MetabolicState, ResourceType,
    AutonomousEvolution, EvolutionPhase, MutationType, EvolutionRecord, Mutation,
    DynamicAssembly, AssemblyStrategy, AssemblyQuality, TaskRequirement, AssemblyResult, AssemblyCache,
    SelfRegeneration, RegenerationStatus, DamageLevel, RegenerationRecord,
    DriveSystem, DriveType, get_drive_system,
    LivingSystem, SystemState, get_living_system, create_and_start,
    create_cell, assemble_model,
)

from .integration import (
    EventBus as IntegrationEventBus, Event as IntegrationEvent,
    EventType as IntegrationEventType,
    get_event_bus as get_integration_event_bus,
    subscribe as subscribe_integration, publish as publish_integration,
    CrossSystemCaller, get_cross_system_caller,
    ContextManager, SessionContext, get_context_manager,
    IntegrationCoordinator, get_integration_coordinator,
    UnifiedServiceManager, ServiceIntegration, ServiceStatus, ServiceInfo,
    SystemManager, get_system_manager,
)

from .self_awareness import (
    SelfAwarenessSystem as CoreSelfAwarenessSystem,
    MirrorLauncher, MirrorInstance,
    ComponentScanner, UIComponent, ScanResult, ComponentType,
    ProblemDetector, ProblemReport, ProblemSeverity,
    HotFixEngine, FixResult, FixStrategy,
    AutoTester, TestCase, TestResult,
    RootCauseTracer, RootCause,
    DeploymentManager, DeploymentRecord, DeploymentStatus,
    BackupManager, BackupRecord, BackupStatus,
    SelfReflection, ReflectionResult,
    GoalManager, Goal,
    AutonomyController, AutonomyLevel, AutonomyPolicy,
)

from .self_healing import (
    HealingRouter, HealthMonitor, HealthMetric, MetricType, MetricStatus,
    ProblemDetector as SelfHealingProblemDetector,
    ProblemReport as SelfHealingProblemReport,
    RepairEngine, RepairResult, RepairStatus,
    RestartStrategy, CheckpointRestoreStrategy,
    FallbackStrategy, ParameterOptimizationStrategy, RollbackStrategy,
    get_healing_router, get_system_health, trigger_repair,
)

from .multi_agent import (
    MultiAgentWorkflow, DynamicTaskDecomposer, AgentLifecycleManager,
    AgentMemoryStore, SharedMemorySpace, AgentMemoryBridge,
    TaskScheduler, ResultAggregator, ConflictResolver,
)

from .creative_assistant import (
    IntelligentWritingAssistant, CreativeAssistantSystem,
    ContentType, WritingStyle, WritingContext,
    WritingSuggestion, ContentAnalysis,
    create_writing_assistant, create_creative_assistant_system,
)

from .event_graph import (
    EventGraph, EventNode, EventType,
    CausalLink, CausalRule, CausalConfidence,
    event_graph, get_event_graph,
)

from .cost_aware import (
    CostEvaluator, CostEstimation, CostBreakdown,
    CostDimension, TaskComplexity,
    BudgetManager, Budget, SessionBudget,
    BudgetType, BudgetStatus,
    CostMonitor, CostMetrics, MonitorStatus,
    CostOptimizer, OptimizationResult,
    OptimizationStrategy, ModelTier,
    get_cost_evaluator, get_budget_manager,
    get_cost_monitor, get_cost_optimizer,
)

from .continual_learning import (
    EWCProtection, EWCWeight,
    ProgressiveNetwork, TaskModule,
    MetaLearner, MAMLConfig,
    CurriculumManager, Lesson, CurriculumOrder,
    TaskMemory, LearnedTask,
    LearningRouter, get_learning_router,
)

from .credit_economy import (
    CreditRegistry, CreditEconomyManager,
    TaskEstimator, Scheduler, CreditLearning,
    DAGOrchestrator, TransactionLedger,
    get_credit_economy_manager, get_credit_registry,
)
