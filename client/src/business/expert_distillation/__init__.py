"""
Expert Distillation Module - 专家蒸馏模块

实现知识蒸馏功能，将 L4 大模型的专业能力蒸馏到小模型，
形成专家级别的垂直领域能力。

架构分层:
阶段1 (短期):
- QueryCollector: 高频查询收集器
- ExpertTrainingPipeline: 专家提示注入（无需训练）

阶段2 (中期):
- DistillationEnhancer: 蒸馏数据增强器
- ExpertTrainingPipeline.collect_and_generate: 收集+生成蒸馏数据

阶段3 (长期):
- DistillationDataGenerator: 蒸馏数据生成器
- ExpertTemplateLibrary: 专家模板库
- FineTuner: 微调引擎
- ExpertTrainingPipeline.train_expert: 训练专家模型

使用方式:
    # 短期方案（无需训练）
    from client.src.business.expert_distillation import ExpertTrainingPipeline
    pipeline = ExpertTrainingPipeline()
    result = pipeline.chat_with_expert_prompt("分析这只股票", domain="金融")

    # 中期方案（收集蒸馏数据）
    pairs = pipeline.collect_and_generate(min_freq=5)

    # 长期方案（训练专家模型）
    pipeline.train_expert(domain="金融", data_path="train.jsonl")
"""

from .data_generator import DistillationDataGenerator, QATriple
from .template_library import ExpertTemplateLibrary
from .router import ExpertRouter, QueryDomain, RoutingDecision, RouteStrategy
from .l4_caller import L4EnhancedCaller
from .pipeline import ExpertDistillationPipeline
from .query_collector import QueryCollector, QueryRecord
from .distillation_pipeline import DistillationEnhancer, DistillationPair, AugmentationStrategy
from .expert_training_pipeline import ExpertTrainingPipeline, PipelineStage, ExpertModel

__all__ = [
    # 原有组件
    "DistillationDataGenerator",
    "QATriple",
    "ExpertTemplateLibrary",
    "ExpertRouter",
    "QueryDomain",
    "RoutingDecision",
    "RouteStrategy",
    "L4EnhancedCaller",
    "ExpertDistillationPipeline",
    # 新增组件
    "QueryCollector",
    "QueryRecord",
    "DistillationEnhancer",
    "DistillationPair",
    "AugmentationStrategy",
    "ExpertTrainingPipeline",
    "PipelineStage",
    "ExpertModel",
]
