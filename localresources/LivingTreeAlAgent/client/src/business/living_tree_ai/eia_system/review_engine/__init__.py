"""
智能审查引擎模块
================

五大创新审查能力：
1. 数字孪生验证 - 预测结果复算、空间验证
2. 知识图谱合规 - 标准合规检查、跨章节推理
3. 智能修复引擎 - 分级建议、自动补丁
4. 对抗性测试 - 不确定性分析、极端情景
5. 分布式审查 - 集体智慧、共识机制
"""

from .digital_twin_verifier import (
    # 数据类
    PredictionInput,
    PredictionResult,
    DistanceVerification,
    VerificationReport,
    VerificationStatus,
    DataSource,
    # 验证器
    DigitalTwinVerifier,
    # 便捷函数
    get_verifier,
    verify_prediction_async,
    verify_distance_async,
    verify_full_report_async,
)

from .knowledge_graph_compliance import (
    # 数据类
    StandardClause,
    KnowledgeNode,
    KnowledgeEdge,
    ComplianceCheckResult,
    CrossChapterInference,
    ComplianceReport,
    ComplianceStatus,
    StandardType,
    RelationType,
    # 引擎
    StandardKnowledgeGraph,
    ComplianceInferenceEngine,
    KnowledgeGraphComplianceEngine,
    # 便捷函数
    get_compliance_engine,
    check_compliance_async,
    get_recommended_standards_async,
)

from .smart_repair_engine import (
    # 数据类
    RepairSuggestion,
    AutoPatch,
    RepairVerification,
    SmartRepairReport,
    IssueLevel,
    IssueCategory,
    RepairAction,
    # 引擎
    SmartRepairEngine,
    # 便捷函数
    get_repair_engine,
    analyze_and_repair_async,
    apply_patch_async,
)

from .adversarial_tester import (
    # 数据类
    MonteCarloResult,
    UncertaintyResult,
    ExtremeScenario,
    SensitivityResult,
    TestReport,
    # 引擎
    AdversarialTester,
    # 便捷函数
    get_tester,
    run_adversarial_test_async,
    run_monte_carlo_async,
    run_sensitivity_analysis_async,
)

from .distributed_review_network import (
    # 数据类
    ReviewNode,
    ReviewTask,
    ReviewVote,
    ConsensusResult,
    ReviewRecord,
    NodeType,
    VoteStatus,
    ConsensusLevel,
    # 网络
    DistributedReviewNetwork,
    # 便捷函数
    get_review_network,
    get_review_network_instance,
)

from .review_master import (
    # 数据类
    ReviewSession,
    IntegratedReviewReport,
    ReviewMode,
    ReviewStage,
    # 引擎
    IntelligentReviewEngine,
    # 便捷函数
    get_review_engine,
    start_review_async,
    generate_integrated_report,
)

# UI面板
from .ui.intelligent_review_panel import (
    IntelligentReviewPanel,
    DigitalTwinVerificationPanel,
    KnowledgeGraphCompliancePanel,
    SmartRepairPanel,
    AdversarialTestPanel,
    DistributedReviewPanel,
    ReviewResultDialog,
    ScoreGauge,
    StatusIndicator,
    IssueLevelBadge,
)

__all__ = [
    # 数字孪生验证
    "PredictionInput",
    "PredictionResult",
    "DistanceVerification",
    "VerificationReport",
    "VerificationStatus",
    "DataSource",
    "DigitalTwinVerifier",
    "get_verifier",
    "verify_prediction_async",
    "verify_distance_async",
    "verify_full_report_async",
    # 知识图谱合规
    "StandardClause",
    "KnowledgeNode",
    "KnowledgeEdge",
    "ComplianceCheckResult",
    "CrossChapterInference",
    "ComplianceReport",
    "ComplianceStatus",
    "StandardType",
    "RelationType",
    "StandardKnowledgeGraph",
    "ComplianceInferenceEngine",
    "KnowledgeGraphComplianceEngine",
    "get_compliance_engine",
    "check_compliance_async",
    "get_recommended_standards_async",
    # 智能修复
    "RepairSuggestion",
    "AutoPatch",
    "RepairVerification",
    "SmartRepairReport",
    "IssueLevel",
    "IssueCategory",
    "RepairAction",
    "SmartRepairEngine",
    "get_repair_engine",
    "analyze_and_repair_async",
    "apply_patch_async",
    # 对抗性测试
    "MonteCarloResult",
    "UncertaintyResult",
    "ExtremeScenario",
    "SensitivityResult",
    "TestReport",
    "AdversarialTester",
    "get_tester",
    "run_adversarial_test_async",
    "run_monte_carlo_async",
    "run_sensitivity_analysis_async",
    # 分布式审查
    "ReviewNode",
    "ReviewTask",
    "ReviewVote",
    "ConsensusResult",
    "ReviewRecord",
    "NodeType",
    "VoteStatus",
    "ConsensusLevel",
    "DistributedReviewNetwork",
    "get_review_network",
    "get_review_network_instance",
    # 主引擎
    "ReviewSession",
    "IntegratedReviewReport",
    "ReviewMode",
    "ReviewStage",
    "IntelligentReviewEngine",
    "get_review_engine",
    "start_review_async",
    "generate_integrated_report",
    # UI面板
    "IntelligentReviewPanel",
    "DigitalTwinVerificationPanel",
    "KnowledgeGraphCompliancePanel",
    "SmartRepairPanel",
    "AdversarialTestPanel",
    "DistributedReviewPanel",
    "ReviewResultDialog",
    "ScoreGauge",
    "StatusIndicator",
    "IssueLevelBadge",
]