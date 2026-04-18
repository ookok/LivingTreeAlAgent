"""
专家系统模块
基于用户画像的智能专家回答系统
"""

from .user_profile import UserProfileParser, UserProfile, SOCIAL_ROLES, EXPERTISE_LEVELS, DECISION_STYLES
from .persona_dispatcher import PersonaDispatcher, Persona, PersonaLibrary, BUILTIN_PERSONAS
from .smart_expert import PersonalizedExpert, ExpertResponse, InteractionLog
from .repository import ExpertRepository, SkillRepository, ExportManager, Skill, BUILTIN_SKILLS

__all__ = [
    # 用户画像
    "UserProfileParser",
    "UserProfile",
    "SOCIAL_ROLES", 
    "EXPERTISE_LEVELS",
    "DECISION_STYLES",
    # 人格
    "PersonaDispatcher",
    "Persona",
    "PersonaLibrary",
    "BUILTIN_PERSONAS",
    # 专家
    "PersonalizedExpert",
    "ExpertResponse",
    "InteractionLog",
    # 仓库
    "ExpertRepository",
    "SkillRepository",
    "ExportManager",
    "Skill",
    "BUILTIN_SKILLS",
]
