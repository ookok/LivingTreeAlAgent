"""
Collective Intelligence Module
集体智能系统 - 多Agent协作、知识共享、集体学习
"""

from .agent_profiles import (
    AgentRole,
    ExpertiseLevel,
    Expertise,
    AgentProfile,
    Contribution,
    CollectiveDecision,
    CollaborationSession
)

from .knowledge_base import (
    SharedKnowledgeBase,
    KnowledgeEntry,
    KnowledgeQuery,
    KnowledgeResult
)

from .consensus_engine import (
    ConsensusStrategy,
    Vote,
    ConsensusResult,
    DebateRound,
    ConsensusEngine
)

from .collective_memory import (
    MemoryEntry,
    MemoryPattern,
    AgentMemory,
    CollectiveMemory
)

from .collective_intelligence import (
    TaskStatus,
    Task,
    CollaborationResult,
    CollectiveIntelligence
)


__all__ = [
    # Agent Profiles
    "AgentRole",
    "ExpertiseLevel", 
    "Expertise",
    "AgentProfile",
    "Contribution",
    "CollectiveDecision",
    "CollaborationSession",
    
    # Knowledge Base
    "SharedKnowledgeBase",
    "KnowledgeEntry",
    "KnowledgeQuery",
    "KnowledgeResult",
    
    # Consensus Engine
    "ConsensusStrategy",
    "Vote",
    "ConsensusResult",
    "DebateRound",
    "ConsensusEngine",
    
    # Collective Memory
    "MemoryEntry",
    "MemoryPattern",
    "AgentMemory",
    "CollectiveMemory",
    
    # Core System
    "TaskStatus",
    "Task",
    "CollaborationResult",
    "CollectiveIntelligence"
]
