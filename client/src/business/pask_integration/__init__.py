"""
PASK Integration - 主动式智能体系统集成

参考论文: PASK: Toward Intent-Aware Proactive Agents with Long-Term Memory
arXiv: https://arxiv.org/abs/2604.08000

实现 DD-MM-PAS 范式：
- Demand Detection (需求检测)
- Memory Modeling (记忆建模)
- Proactive Agent System (主动式智能体系统)

集成模块：
- MemoryIntegrator: 与 MemoryManager 集成
- AgentIntegrator: 与 HermesAgent 集成
- SkillIntegrator: 与 SkillEvolution 集成
- RAGIntegrator: 与 FusionRAG 集成

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from .demand_detector import DemandDetector, IntentFlow
from .memory_model import HybridMemory, WorkspaceMemory, UserMemory, GlobalMemory
from .proactive_agent import ProactiveAgent, ProactiveAction
from .pask_config import PASKConfig
from .enhanced_memory import EnhancedGlobalMemory
from .enhanced_intent import EnhancedIntentDetector, StreamingIntentDetector, IntentHierarchy, IntentEvolution
from .integrations import (
    MemoryIntegrator,
    AgentIntegrator,
    SkillIntegrator,
    RAGIntegrator,
    initialize_integrations
)

__all__ = [
    # 核心组件
    "DemandDetector",
    "IntentFlow",
    "HybridMemory",
    "WorkspaceMemory",
    "UserMemory",
    "GlobalMemory",
    "ProactiveAgent",
    "ProactiveAction",
    "PASKConfig",
    
    # 增强组件
    "EnhancedGlobalMemory",
    "EnhancedIntentDetector",
    "StreamingIntentDetector",
    "IntentHierarchy",
    "IntentEvolution",
    
    # 集成组件
    "MemoryIntegrator",
    "AgentIntegrator",
    "SkillIntegrator",
    "RAGIntegrator",
    "initialize_integrations",
]

# 创建全局实例
pask_config = PASKConfig()
hybrid_memory = HybridMemory()
demand_detector = DemandDetector()
proactive_agent = ProactiveAgent()


def get_pask_config() -> PASKConfig:
    """获取 PASK 配置"""
    return pask_config


def get_hybrid_memory() -> HybridMemory:
    """获取混合记忆系统"""
    return hybrid_memory


def get_demand_detector() -> DemandDetector:
    """获取需求检测器"""
    return demand_detector


def get_proactive_agent() -> ProactiveAgent:
    """获取主动式智能体"""
    return proactive_agent


# 自动初始化集成
try:
    initialize_integrations()
except Exception as e:
    import logging
    logging.warning(f"PASK 集成初始化失败（可能在初始化阶段）: {e}")