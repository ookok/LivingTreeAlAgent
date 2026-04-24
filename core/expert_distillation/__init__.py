"""
Expert Distillation Module - 专家蒸馏模块

实现知识蒸馏功能，将 L4 大模型的专业能力蒸馏到小模型，
形成专家级别的垂直领域能力。

架构分层:
- DistillationDataGenerator: 蒸馏数据生成器
- ExpertTemplateLibrary: 专家模板库
- ExpertRouter: 领域路由层
- L4EnhancedCaller: L4 增强调用器
- FineTuner: 微调引擎

使用方式:
    from core.expert_distillation import ExpertDistillationPipeline

    pipeline = ExpertDistillationPipeline()
    result = pipeline.chat("分析这只股票", domain="金融")
"""

from .data_generator import DistillationDataGenerator
from .template_library import ExpertTemplateLibrary
from .router import ExpertRouter
from .l4_caller import L4EnhancedCaller
from .pipeline import ExpertDistillationPipeline

__all__ = [
    "DistillationDataGenerator",
    "ExpertTemplateLibrary",
    "ExpertRouter",
    "L4EnhancedCaller",
    "ExpertDistillationPipeline",
]
