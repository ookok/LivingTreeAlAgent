"""
进化环境模块（Evolutionary Environment）

核心功能：
- 构建可被AI感知的交互环境
- 让AI在与用户的协作中自主发现流程规律
- 支持环评工作模式的自然生长
- 整合 FusionRAG 和 LLM Wiki 知识库

模块结构：
1. 感知层（Perception Layer）：多模态信号捕获、操作行为埋点
2. 记忆层（Memory Layer）：动态知识图谱、自我更新机制
3. 行动层（Action Layer）：动态UI渲染、组件基因库
4. 目标层（Objective Layer）：奖励函数、合规性检查
5. Wiki整合层（Wiki Integration）：与LLM Wiki的无缝集成
6. 进化控制器（Evolution Controller）：整合四层基础设施
"""

from .perception_layer import PerceptionLayer, UserAction, MultimodalContext
from .memory_layer import MemoryLayer, KnowledgeNode, KnowledgeEdge, LearnedPattern
from .action_layer import ActionLayer, ComponentType, UIComponent, RenderSchema, ComponentGenePool
from .objective_layer import ObjectiveLayer, RewardSignal, EvaluationResult
from .wiki_integration import WikiIntegrationLayer, WikiKnowledgeEntry, get_wiki_integration
from .evolution_controller import EvolutionController, EvolutionState, StrategyTestResult

__all__ = [
    # 感知层
    'PerceptionLayer',
    'UserAction',
    'MultimodalContext',
    
    # 记忆层
    'MemoryLayer',
    'KnowledgeNode',
    'KnowledgeEdge',
    'LearnedPattern',
    
    # 行动层
    'ActionLayer',
    'ComponentType',
    'UIComponent',
    'RenderSchema',
    'ComponentGenePool',
    
    # 目标层
    'ObjectiveLayer',
    'RewardSignal',
    'EvaluationResult',
    
    # Wiki整合层
    'WikiIntegrationLayer',
    'WikiKnowledgeEntry',
    'get_wiki_integration',
    
    # 进化控制器
    'EvolutionController',
    'EvolutionState',
    'StrategyTestResult'
]