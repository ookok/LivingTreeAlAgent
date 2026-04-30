"""
Cognitive Framework - 认知中间件框架

将类人认知能力转化为可执行的软件模块，实现从"聪明的工具"到"懂行的数字同事"的进化。

核心组件：
1. MentalModelBuilder - 心理表征：将文档解析结果转化为"概念图"数据结构
2. AttentionController - 注意力机制：任务队列优先级调度 + 上下文窗口动态分配
3. MetaReasoningEngine - 元认知监控：对生成结果进行置信度打分与逻辑自检
4. ExperienceManager - 经验档案：基于向量数据库的"案例库" + 决策树记录
5. IdeaGenerator - 创意引擎：多模型投票（生成-评审-筛选）工作流

架构定位：
- 位于控制层（Orchestration）与执行层（Execution）之间
- 实现"理解"与"生成"的解耦
- 提供统一的认知中间表示（语义图）

使用示例：
    from client.src.business.cognitive_framework import CognitiveFramework
    
    cf = CognitiveFramework()
    
    # 构建心理模型
    model = cf.mental_model_builder.build_from_text("这是一段需要理解的文本")
    
    # 调度任务
    cf.attention_controller.submit_task(task, priority="high")
    
    # 元认知监控
    confidence = cf.meta_reasoning_engine.evaluate(result)
    
    # 存储经验
    cf.experience_manager.store_case(case_data)
    
    # 创意生成
    ideas = cf.idea_generator.generate(prompt)
"""

from .mental_model_builder import MentalModelBuilder, ConceptGraph, ConceptNode, Relation
from .attention_controller import AttentionController, FocusStack, TaskContext
from .meta_reasoning_engine import MetaReasoningEngine, ValidationPipeline, ConfidenceScore
from .experience_manager import ExperienceManager, CaseRecord, DecisionTree
from .idea_generator import IdeaGenerator, VoteResult
from .cognitive_framework import CognitiveFramework, get_cognitive_framework, init_cognitive_framework

__all__ = [
    # 核心组件
    'MentalModelBuilder',
    'AttentionController',
    'MetaReasoningEngine',
    'ExperienceManager',
    'IdeaGenerator',
    'CognitiveFramework',
    
    # 工厂函数
    'get_cognitive_framework',
    'init_cognitive_framework',
    
    # 数据结构
    'ConceptGraph',
    'ConceptNode',
    'Relation',
    'FocusStack',
    'TaskContext',
    'ValidationPipeline',
    'ConfidenceScore',
    'CaseRecord',
    'DecisionTree',
    'VoteResult',
]

__version__ = '1.0.0'
