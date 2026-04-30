"""
L0-L4 层架构创新组件

包含基础设施层、数据层、服务层、应用层、表现层和跨层组件
"""

# L0 - 基础设施层
from .l0_infrastructure import (
    DynamicResourceScheduler,
    SmartFailover,
    EdgeCloudSynergy,
    get_dynamic_resource_scheduler,
    get_smart_failover,
    get_edge_cloud_synergy,
    ResourceType,
    ResourceStatus,
)

# L1 - 数据/存储层
from .l1_data import (
    MultiModalStore,
    AdaptiveStorage,
    SmartDataLifecycle,
    get_multi_modal_store,
    get_adaptive_storage,
    get_smart_data_lifecycle,
    DataModality,
    StorageTier,
    MultiModalData,
)

# L2 - 服务/逻辑层
from .l2_service import (
    AdaptiveServiceComposition,
    SmartAPIGateway,
    get_adaptive_service_composition,
    get_smart_api_gateway,
    ServiceType,
    ServiceDescriptor,
    RouteDecision,
)

# L3 - 应用/业务层
from .l3_application import (
    AdaptiveWorkflowEngine,
    SmartDecisionEngine,
    SelfEvolutionSystem,
    get_adaptive_workflow_engine,
    get_smart_decision_engine,
    get_self_evolution_system,
    WorkflowStatus,
    WorkflowNode,
    DecisionOutcome,
)

# L4 - 表现/交互层
from .l4_presentation import (
    MultiModalInteractionEngine,
    EmotionAwareUI,
    AdaptiveOutput,
    get_multi_modal_interaction_engine,
    get_emotion_aware_ui,
    get_adaptive_output,
    EmotionType,
    OutputFormat,
    InteractionInput,
    InteractionOutput,
    UserEmotion,
)

# 跨层组件
from .cross_layer import (
    VerticalOptimizer,
    SmartObservability,
    SecurityAsService,
    get_vertical_optimizer,
    get_smart_observability,
    get_security_as_service,
    OptimizationTarget,
    OptimizationResult,
    AnomalyDetection,
    SecurityEvent,
)

__all__ = [
    # L0 - 基础设施层
    "DynamicResourceScheduler",
    "SmartFailover",
    "EdgeCloudSynergy",
    "get_dynamic_resource_scheduler",
    "get_smart_failover",
    "get_edge_cloud_synergy",
    "ResourceType",
    "ResourceStatus",
    
    # L1 - 数据/存储层
    "MultiModalStore",
    "AdaptiveStorage",
    "SmartDataLifecycle",
    "get_multi_modal_store",
    "get_adaptive_storage",
    "get_smart_data_lifecycle",
    "DataModality",
    "StorageTier",
    "MultiModalData",
    
    # L2 - 服务/逻辑层
    "AdaptiveServiceComposition",
    "SmartAPIGateway",
    "get_adaptive_service_composition",
    "get_smart_api_gateway",
    "ServiceType",
    "ServiceDescriptor",
    "RouteDecision",
    
    # L3 - 应用/业务层
    "AdaptiveWorkflowEngine",
    "SmartDecisionEngine",
    "SelfEvolutionSystem",
    "get_adaptive_workflow_engine",
    "get_smart_decision_engine",
    "get_self_evolution_system",
    "WorkflowStatus",
    "WorkflowNode",
    "DecisionOutcome",
    
    # L4 - 表现/交互层
    "MultiModalInteractionEngine",
    "EmotionAwareUI",
    "AdaptiveOutput",
    "get_multi_modal_interaction_engine",
    "get_emotion_aware_ui",
    "get_adaptive_output",
    "EmotionType",
    "OutputFormat",
    "InteractionInput",
    "InteractionOutput",
    "UserEmotion",
    
    # 跨层组件
    "VerticalOptimizer",
    "SmartObservability",
    "SecurityAsService",
    "get_vertical_optimizer",
    "get_smart_observability",
    "get_security_as_service",
    "OptimizationTarget",
    "OptimizationResult",
    "AnomalyDetection",
    "SecurityEvent",
]