"""
上下文感知加载器
==============

根据当前任务上下文，智能加载相关技能
"""

import logging
from typing import Dict, List, Optional, Any, Set
from business.agent_skills.skill_registry import SkillRegistry, SkillManifest, SkillCategory

logger = logging.getLogger(__name__)


class ContextAwareLoader:
    """
    上下文感知技能加载器
    
    根据当前工作上下文（文件类型、任务类型等）
    自动推荐和加载相关技能
    """
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._context_rules: Dict[str, List[str]] = {}
        self._setup_default_rules()
        
    def _setup_default_rules(self):
        """设置默认的上下文规则"""
        # 前端开发上下文
        self._context_rules["frontend"] = [
            "frontend-ui-engineering",
            "component-architecture",
            "design-systems",
            "accessibility",
        ]
        
        # 后端开发上下文
        self._context_rules["backend"] = [
            "api-design",
            "database-schema",
            "authentication",
            "caching-strategies",
        ]
        
        # 测试上下文
        self._context_rules["testing"] = [
            "test-driven-development",
            "browser-testing",
            "unit-testing",
            "integration-testing",
        ]
        
        # 代码审查上下文
        self._context_rules["review"] = [
            "code-review-and-quality",
            "security-and-hardening",
            "performance-review",
        ]
        
    def get_relevant_skills(self, context: Dict[str, Any]) -> List[SkillManifest]:
        """
        根据上下文获取相关技能
        
        Args:
            context: 上下文字典，可能包含：
                - task_type: 任务类型 (frontend/backend/testing/review)
                - file_types: 文件类型列表
                - keywords: 关键词列表
        """
        relevant_skill_ids: Set[str] = set()
        
        # 1. 根据任务类型匹配
        task_type = context.get("task_type", "")
        if task_type in self._context_rules:
            relevant_skill_ids.update(self._context_rules[task_type])
            
        # 2. 根据文件类型匹配
        file_types = context.get("file_types", [])
        for file_type in file_types:
            if "html" in file_type or "css" in file_type or "jsx" in file_type:
                relevant_skill_ids.update(self._context_rules.get("frontend", []))
            elif "py" in file_type or "js" in file_type or "ts" in file_type:
                relevant_skill_ids.update(self._context_rules.get("backend", []))
            elif "test" in file_type:
                relevant_skill_ids.update(self._context_rules.get("testing", []))
                
        # 3. 根据关键词匹配
        keywords = context.get("keywords", [])
        for keyword in keywords:
            matched_skills = self.registry.find_by_trigger(keyword)
            for skill in matched_skills:
                relevant_skill_ids.add(skill.id)
                
        # 4. 转换为 SkillManifest 列表
        skills = []
        for skill_id in relevant_skill_ids:
            skill = self.registry.get_skill(skill_id)
            if skill and skill.enabled:
                skills.append(skill)
                
        # 按优先级排序
        skills.sort(key=lambda s: s.priority, reverse=True)
        
        return skills
    
    def get_context_summary(self, context: Dict[str, Any]) -> str:
        """获取上下文摘要"""
        task_type = context.get("task_type", "unknown")
        file_count = len(context.get("file_types", []))
        keyword_count = len(context.get("keywords", []))
        
        return (
            f"任务类型: {task_type}, "
            f"文件数: {file_count}, "
            f"关键词数: {keyword_count}"
        )
