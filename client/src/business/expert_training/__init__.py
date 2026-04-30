"""
专家训练模块 (Expert Training)

架构升级 (2026-04-30):
- 引入共享基础设施层 (shared/)
- 依赖注入容器、统一术语模型、配置中心、事件总线、缓存层、统一异常体系

工业级渐进式训练体系：
1. 数据构造器 - 构建工业三元组训练数据
2. 思维链构造器 - 生成包含推理步骤的训练样本
3. 任务设计框架 - 四阶段渐进式训练
4. 训练策略 - V100优化的LoRA微调配置
5. 评估体系 - 工业级KPI评估
6. 训练管理器 - 统一入口
7. 自动术语表构建器 - LLM驱动的自动化术语表生成

核心原则：专家训练 = 高质量（行业数据） + 强逻辑（思维链） + 严评估（工程可用性）
"""

# 数据构造器
from .data_constructor import (
    TrainingDataConstructor,
    TrainingSample,
    DataSource,
    create_data_constructor
)

# 思维链构造器
from .reasoning_chain_builder import (
    ReasoningChainBuilder,
    ReasoningChainSample,
    ReasoningStep,
    create_reasoning_chain_builder
)

# 任务设计框架
from .task_framework import (
    TaskFramework,
    TaskDefinition,
    StageConfig,
    create_task_framework
)

# 训练策略
from .training_strategy import (
    TrainingStrategy,
    LORAConfig,
    TrainingHyperParams,
    LossConfig,
    ModelConfig,
    create_training_strategy,
    RECOMMENDED_MODELS
)

# 评估体系
from .evaluation_system import (
    EvaluationSystem,
    TestCase,
    EvaluationResult,
    KPIMetrics,
    create_evaluation_system
)

# 训练管理器
from .train_manager import (
    TrainingManager,
    TrainingProgress,
    TrainingConfig,
    create_train_manager
)

# 环评行业数据模块
from .env_assessment_data import (
    EIA_TERMS,
    EIA_STANDARDS,
    EIA_TRAINING_SAMPLES,
    EIA_REASONING_TEMPLATES,
    EIA_TASKS,
    get_eia_terms,
    get_eia_standards,
    get_eia_training_samples,
    get_eia_reasoning_templates,
    get_eia_tasks,
    add_eia_data_to_trainer
)

# 行业自动构建器
from .industry_auto_builder import (
    IndustryAutoBuilder,
    IndustryConfig,
    IndustryTemplate,
    create_industry_auto_builder,
    EXAMPLE_CONFIG
)

# 全自动训练器
from .full_auto_trainer import (
    FullyAutoTrainer,
    AutoDiscoveryResult,
    AutoTrainingReport,
    create_full_auto_trainer
)

# 基于知识库的自动化训练器
from .kb_based_auto_trainer import (
    KBBasedAutoTrainer,
    KBExtractionResult,
    KBTrainingResult,
    create_kb_based_auto_trainer
)

# 文档驱动的行业方言词典
from .document_driven_dictionary import (
    DocumentDrivenDictionary,
    TermMapping,
    ConflictItem,
    DictionaryStats,
    create_document_driven_dictionary,
    PROJECT_TERMS_TEMPLATE,
    CSV_TEMPLATE
)

# LLM驱动的自动化术语表构建器
from .auto_term_table_builder import (
    AutoTermTableBuilder,
    TermEntry,
    TermTableResult,
    create_auto_term_table_builder
)


__all__ = [
    # 数据构造器
    "TrainingDataConstructor",
    "TrainingSample",
    "DataSource",
    "create_data_constructor",
    
    # 思维链构造器
    "ReasoningChainBuilder",
    "ReasoningChainSample",
    "ReasoningStep",
    "create_reasoning_chain_builder",
    
    # 任务设计框架
    "TaskFramework",
    "TaskDefinition",
    "StageConfig",
    "create_task_framework",
    
    # 训练策略
    "TrainingStrategy",
    "LORAConfig",
    "TrainingHyperParams",
    "LossConfig",
    "ModelConfig",
    "create_training_strategy",
    "RECOMMENDED_MODELS",
    
    # 评估体系
    "EvaluationSystem",
    "TestCase",
    "EvaluationResult",
    "KPIMetrics",
    "create_evaluation_system",
    
    # 训练管理器
    "TrainingManager",
    "TrainingProgress",
    "TrainingConfig",
    "create_train_manager",
    
    # 环评行业数据
    "EIA_TERMS",
    "EIA_STANDARDS",
    "EIA_TRAINING_SAMPLES",
    "EIA_REASONING_TEMPLATES",
    "EIA_TASKS",
    "get_eia_terms",
    "get_eia_standards",
    "get_eia_training_samples",
    "get_eia_reasoning_templates",
    "get_eia_tasks",
    "add_eia_data_to_trainer",
    
    # 行业自动构建器
    "IndustryAutoBuilder",
    "IndustryConfig",
    "IndustryTemplate",
    "create_industry_auto_builder",
    "EXAMPLE_CONFIG",
    
    # 全自动训练器
    "FullyAutoTrainer",
    "AutoDiscoveryResult",
    "AutoTrainingReport",
    "create_full_auto_trainer",
    
    # 基于知识库的自动化训练器
    "KBBasedAutoTrainer",
    "KBExtractionResult",
    "KBTrainingResult",
    "create_kb_based_auto_trainer",
    
    # 文档驱动的行业方言词典
    "DocumentDrivenDictionary",
    "TermMapping",
    "ConflictItem",
    "DictionaryStats",
    "create_document_driven_dictionary",
    "PROJECT_TERMS_TEMPLATE",
    "CSV_TEMPLATE",
    
    # LLM驱动的自动化术语表构建器
    "AutoTermTableBuilder",
    "TermEntry",
    "TermTableResult",
    "create_auto_term_table_builder"
]

__version__ = "1.0.0"
__author__ = "LivingTree AI Team"
__description__ = "Industrial Expert Training System"


# 快速开始示例
def quick_start():
    """快速开始：创建训练管理器并执行训练"""
    # 创建训练管理器
    config = TrainingConfig(
        target_industry="机械制造",
        model_name="Qwen/Qwen2.5-7B-Instruct",
        gpu_memory_gb=64,
        enable_reasoning_chain=True
    )
    
    manager = create_train_manager(config)
    
    # 准备数据
    print("=== 准备训练数据 ===")
    manager.prepare_data(synthetic_count=5000)
    
    # 生成训练计划
    print("\n=== 生成训练计划 ===")
    plan = manager.generate_training_plan()
    print(f"预计总时长: {plan['estimated_duration_weeks']} 周")
    
    # 执行完整训练
    print("\n=== 开始完整训练 ===")
    manager.run_full_training()
    
    # 获取最终统计
    stats = manager.get_stats()
    print(f"\n=== 训练完成 ===")
    print(f"总样本数: {stats['data_constructor']['total_samples']}")
    print(f"思维链样本: {stats['reasoning_builder']['total_samples']}")
    print(f"总体进度: {stats['task_framework']['overall_progress']:.1f}%")
    
    return manager