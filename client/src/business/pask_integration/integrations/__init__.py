"""
PASK 集成适配器

将 PASK 主动式智能体系统与现有模块集成：
- MemoryManager 集成
- HermesAgent 集成
- SkillEvolution 集成
- FusionRAG 集成

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

from .memory_integrator import MemoryIntegrator
from .agent_integrator import AgentIntegrator
from .skill_integrator import SkillIntegrator
from .rag_integrator import RAGIntegrator

__all__ = [
    "MemoryIntegrator",
    "AgentIntegrator",
    "SkillIntegrator",
    "RAGIntegrator",
]


def initialize_integrations():
    """初始化所有集成"""
    MemoryIntegrator.get_instance()
    AgentIntegrator.get_instance()
    SkillIntegrator.get_instance()
    RAGIntegrator.get_instance()