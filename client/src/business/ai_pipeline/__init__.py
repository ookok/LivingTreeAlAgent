"""
AI-Centric自动化研发流水线

核心组件：
1. AIWorkflowEngine - AI工作流引擎
2. TaskDecompositionEngine - 任务分解引擎
3. CodeGenerationUnit - 智能代码生成单元
4. AutoTestSystem - 自主测试系统
5. SmartFixEngine - 智能修复引擎
6. QualityGates - 质量门禁系统
7. KnowledgeManagement - 知识管理体系
8. ContextManager - 上下文管理器
9. PipelinePanel - 流水线面板
10. ConversationOrchestrator - 对话编排器
11. ProgressiveThinkingEngine - 渐进式思考引擎
12. AutoConfig - 自动化配置系统
13. AutoDeploy - 自动化部署系统
14. CodeWorkflowEngine - 智能代码工作流引擎
15. SmartScheduler - 智能调度引擎
16. MultimodalProcessor - 多模态输入处理引擎
17. AdaptiveLearningSystem - 自适应学习系统
18. IncrementalCodeGenerator - 增量代码生成器

架构层次：
- 交互层 (Conversation Layer): 自然语言对话接口、多模态输入
- 协调层 (Orchestration Layer): 工作流引擎、上下文管理器、质量门禁、智能调度
- 执行层 (Execution Layer): 开发单元、测试单元、运维单元、知识单元
- 学习层 (Learning Layer): 自适应学习系统、增量生成
"""

# 核心引擎
from .ai_workflow_engine import AIWorkflowEngine, get_ai_workflow_engine
from .task_decomposition_engine import TaskDecompositionEngine, get_task_decomposition_engine
from .code_generation_unit import CodeGenerationUnit, get_code_generation_unit
from .auto_test_system import AutoTestSystem, get_auto_test_system
from .smart_fix_engine import SmartFixEngine, get_smart_fix_engine
from .quality_gates import QualityGates, get_quality_gates
from .knowledge_management import KnowledgeManagement, get_knowledge_management
from .context_manager import ContextManager, get_context_manager
from .ide_pipeline_panel import PipelinePanel, PipelineStage, PipelineTask, ApprovalPoint, TaskStatus, ApprovalStatus, get_pipeline_panel
from .integration_orchestrator import IntegrationOrchestrator, get_integration_orchestrator, AutomationMode, PipelineStatus
from .conversation_orchestrator import ConversationOrchestrator, get_conversation_orchestrator, ConversationState
from .progressive_thinking import ProgressiveThinkingEngine, get_progressive_thinking_engine

# 自动化模块
from .auto_config import AutoConfig, get_auto_config, EnvironmentType, ConfigStatus
from .auto_deploy import AutoDeploy, get_auto_deploy, DeploymentStatus, ServiceType
from .code_workflow import CodeWorkflowEngine, get_code_workflow_engine, WorkflowMode
from .smart_scheduler import SmartScheduler, get_smart_scheduler, TaskPriority, TaskStatus as SchedulerTaskStatus
from .multimodal_processor import MultimodalProcessor, get_multimodal_processor, InputType, FileType, ParsedResult
from .adaptive_learning import AdaptiveLearningSystem, get_adaptive_learning_system, PatternType, LearningMode
from .incremental_generator import IncrementalCodeGenerator, get_incremental_generator

# Opik 可观测性模块
from .opik_observability import (
    OpikObserver,
    get_opik_observer,
    LlmCallTracker,
    track_llm_call,
    DeepSeekClient,
    LlmProvider,
    LlmModel
)

# 代码理解模块（GitNexus风格）
from business.code_understanding import (
    CodeParser,
    LanguageSupport,
    CodeAnalyzer,
    GitAnalyzer,
    PatternRecognizer,
    CodeGraph
)

__all__ = [
    # 引擎类
    "AIWorkflowEngine",
    "TaskDecompositionEngine",
    "CodeGenerationUnit",
    "AutoTestSystem",
    "SmartFixEngine",
    "QualityGates",
    "KnowledgeManagement",
    "ContextManager",
    "PipelinePanel",
    "IntegrationOrchestrator",
    "AutomationMode",
    "PipelineStatus",
    "ConversationOrchestrator",
    "ConversationState",
    "ProgressiveThinkingEngine",
    
    # 自动化模块
    "AutoConfig",
    "EnvironmentType",
    "ConfigStatus",
    "AutoDeploy",
    "DeploymentStatus",
    "ServiceType",
    "CodeWorkflowEngine",
    "WorkflowMode",
    "SmartScheduler",
    "TaskPriority",
    "SchedulerTaskStatus",
    "MultimodalProcessor",
    "InputType",
    "FileType",
    "ParsedResult",
    "AdaptiveLearningSystem",
    "PatternType",
    "LearningMode",
    "IncrementalCodeGenerator",
    
    # 代码理解模块（GitNexus风格）
    "CodeParser",
    "LanguageSupport",
    "CodeAnalyzer",
    "GitAnalyzer",
    "PatternRecognizer",
    "CodeGraph",
    
    # 枚举类型
    "PipelineStage",
    "PipelineTask",
    "ApprovalPoint",
    "TaskStatus",
    "ApprovalStatus",
    
    # 工厂函数
    "get_ai_workflow_engine",
    "get_task_decomposition_engine",
    "get_code_generation_unit",
    "get_auto_test_system",
    "get_smart_fix_engine",
    "get_quality_gates",
    "get_knowledge_management",
    "get_context_manager",
    "get_pipeline_panel",
    "get_integration_orchestrator",
    "get_conversation_orchestrator",
    "get_progressive_thinking_engine",
    "get_auto_config",
    "get_auto_deploy",
    "get_code_workflow_engine",
    "get_smart_scheduler",
    "get_multimodal_processor",
    "get_adaptive_learning_system",
    "get_incremental_generator",
    
    # Opik 可观测性
    "OpikObserver",
    "get_opik_observer",
    "LlmCallTracker",
    "track_llm_call",
    "DeepSeekClient",
    "LlmProvider",
    "LlmModel"
]

__version__ = "2.0.0"

print(f"🔧 AI Pipeline v{__version__} 加载完成")