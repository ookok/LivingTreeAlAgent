"""
技能注册中心
===========

管理和注册所有 Agent Skills
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class SkillCategory(Enum):
    """技能类别"""
    PLANNING = "planning"
    DEVELOPMENT = "development"
    TESTING = "testing"
    REVIEW = "review"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    UI_UX = "ui_ux"
    DEBUGGING = "debugging"


@dataclass
class SkillManifest:
    """技能描述清单"""
    id: str
    name: str
    description: str
    category: SkillCategory
    trigger_phrases: List[str] = field(default_factory=list)
    context_required: bool = True
    estimated_tokens: int = 2000
    priority: int = 5  # 1-10，越高越优先
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    """
    技能注册中心
    
    管理所有技能的注册、查询和加载
    """
    
    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._skill_content: Dict[str, str] = {}
        
    def register(self, manifest: SkillManifest, content: str = ""):
        """注册一个技能"""
        self._skills[manifest.id] = manifest
        if content:
            self._skill_content[manifest.id] = content
        logger.info(f"[SkillRegistry] 注册技能: {manifest.name} ({manifest.id})")
        
    def get_skill(self, skill_id: str) -> Optional[SkillManifest]:
        """获取技能清单"""
        return self._skills.get(skill_id)
    
    def get_skill_content(self, skill_id: str) -> Optional[str]:
        """获取技能内容"""
        return self._skill_content.get(skill_id)
    
    def list_skills(self, category: Optional[SkillCategory] = None) -> List[SkillManifest]:
        """列出所有技能（可按类别过滤）"""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return skills
    
    def find_by_trigger(self, text: str) -> List[SkillManifest]:
        """根据触发词查找技能"""
        text_lower = text.lower()
        matched = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            for phrase in skill.trigger_phrases:
                if phrase.lower() in text_lower:
                    matched.append(skill)
                    break
        return matched
    
    def enable_skill(self, skill_id: str, enabled: bool = True):
        """启用/禁用技能"""
        if skill_id in self._skills:
            self._skills[skill_id].enabled = enabled
            
    def get_stats(self) -> Dict[str, Any]:
        """获取注册统计"""
        return {
            "total_skills": len(self._skills),
            "enabled_skills": sum(1 for s in self._skills.values() if s.enabled),
            "categories": list(set(s.category.value for s in self._skills.values())),
        }
