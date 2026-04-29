"""
模型计算引擎 (Model Computing Engine)

将咨询报告背后的计算逻辑封装为"模型微服务"，实现"模型即插件"架构。

支持模型类型：
1. 排放核算 - 产排污系数法、物料衡算
2. 环境预测 - AERMOD（大气）、EFDC（水）
3. 风险评价 - 危险度评价（LS）、环境风险扩散
4. 工程经济 - 投资估算、成本效益分析

核心优势：
- 版本可控：环评导则更新时，只需更新模型微服务
- 审计留痕：报告附带"计算参数清单"
- 模型并行：多个计算可同时进行，加速报告生成
"""

from .model_dispatcher import (
    # 枚举
    ModelType,
    ModelStatus,
    ComputePriority,
    # 数据模型
    ModelInfo,
    ModelParameter,
    ComputeRequest,
    ComputeResult,
    ModelVersion,
    # 调度器
    ModelDispatcher,
    get_model_dispatcher,
)

from .emission_calculator import (
    # 排放核算
    EmissionSource,
    PollutantType,
    EmissionFactor,
    CalculatedEmission,
    EmissionCalculator,
    get_emission_calculator,
)

from .risk_evaluator import (
    # 风险评价
    RiskType,
    RiskLevel,
    RiskScenario,
    RiskConsequence,
    RiskEvaluationResult,
    RiskEvaluator,
    get_risk_evaluator,
)

from .economics_engine import (
    # 工程经济
    CostType,
    CostItem,
    InvestmentEstimate,
    OperatingCost,
    CostBenefitResult,
    EconomicsEngine,
    get_economics_engine,
)

__all__ = [
    # 调度器
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
    # 排放核算
    "EmissionSource",
    "PollutantType",
    "EmissionFactor",
    "CalculatedEmission",
    "EmissionCalculator",
    "get_emission_calculator",
    # 风险评价
    "RiskType",
    "RiskLevel",
    "RiskScenario",
    "RiskConsequence",
    "RiskEvaluationResult",
    "RiskEvaluator",
    "get_risk_evaluator",
    # 工程经济
    "CostType",
    "CostItem",
    "InvestmentEstimate",
    "OperatingCost",
    "CostBenefitResult",
    "EconomicsEngine",
    "get_economics_engine",
]