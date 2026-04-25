"""
技能注册中心
===========

参考 Hermes Agent SKILL.md 格式增强：
- 统一的技能定义标准
- 自进化技能创建支持
- 增强的元数据字段

Author: Hermes Desktop Team
Date: 2026-04-22
Updated: 2026-04-25 (对齐 Hermes SKILL.md 格式)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime

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
    LEARNING = "learning"  # 新增：自学习技能


class AgentType(Enum):
    """代理类型（对齐 Hermes Agent）"""
    CODE_EXPERT = "CodeExpert"
    PLANNER = "Planner"
    RESEARCHER = "Researcher"
    WRITER = "Writer"
    REVIEWER = "Reviewer"
    GENERAL = "General"
    ORCHESTRATOR = "Orchestrator"


class OutputType(Enum):
    """输出类型（对齐 Hermes Agent）"""
    TEXT = "text"
    TOOL_CALLS = "tool_calls"
    ARTIFACTS = "artifacts"
    CODE = "code"
    FILE = "file"


class SkillEvolution(Enum):
    """技能进化状态"""
    SEED = "seed"           # 种子技能（自动创建）
    LEARNING = "learning"    # 学习中
    STABLE = "stable"        # 稳定
    DEprecated = "deprecated" # 已废弃


@dataclass
class SkillInput:
    """技能输入参数定义"""
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Optional[str] = None


@dataclass
class SkillOutput:
    """技能输出定义"""
    type: OutputType
    description: str = ""


@dataclass
class SkillManifest:
    """
    技能描述清单（对齐 Hermes SKILL.md 格式）
    
    新增字段：
    - agent: 代理类型
    - inputs: 输入参数定义
    - outputs: 输出类型
    - tools: 需要的工具
    - conversation_starters: 对话启动器
    - examples: 使用示例
    - evolution: 进化状态
    """
    # 基础信息
    id: str
    name: str
    description: str
    category: SkillCategory
    trigger_phrases: List[str] = field(default_factory=list)
    context_required: bool = True
    estimated_tokens: int = 2000
    priority: int = 5  # 1-10，越高越优先
    enabled: bool = True
    
    # Hermes SKILL.md 格式扩展
    agent: AgentType = AgentType.GENERAL  # 代理类型
    inputs: List[SkillInput] = field(default_factory=list)  # 输入参数
    outputs: List[SkillOutput] = field(default_factory=list)  # 输出类型
    tools: List[str] = field(default_factory=list)  # 需要的工具
    conversation_starters: List[str] = field(default_factory=list)  # 对话启动器
    examples: List[str] = field(default_factory=list)  # 使用示例
    
    # 自进化支持
    evolution: SkillEvolution = SkillEvolution.STABLE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    success_rate: float = 1.0  # 成功率
    parent_skill: Optional[str] = None  # 父技能（进化来源）
    
    # 原始元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    """
    技能注册中心
    
    管理所有技能的注册、查询、加载和自进化
    支持 Hermes Agent 风格的技能生命周期管理
    """
    
    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._skill_content: Dict[str, str] = {}
        self._evolution_history: Dict[str, List[Dict]] = {}  # 进化历史
        
    def register(self, manifest: SkillManifest, content: str = ""):
        """注册一个技能"""
        self._skills[manifest.id] = manifest
        if content:
            self._skill_content[manifest.id] = content
        logger.info(f"[SkillRegistry] 注册技能: {manifest.name} ({manifest.id})")
        
    def register_from_dict(self, skill_data: Dict[str, Any], content: str = "") -> SkillManifest:
        """
        从字典注册技能（支持 Hermes SKILL.md 格式）
        
        Args:
            skill_data: 技能元数据字典
            content: 技能内容
            
        Returns:
            创建的 SkillManifest
        """
        # 转换枚举值
        category = skill_data.get("category", "development")
        if isinstance(category, str):
            try:
                category = SkillCategory(category)
            except ValueError:
                category = SkillCategory.DEVELOPMENT
        
        agent = skill_data.get("agent", "General")
        if isinstance(agent, str):
            try:
                agent = AgentType(agent)
            except ValueError:
                agent = AgentType.GENERAL
        
        # 解析 inputs
        inputs = []
        for inp in skill_data.get("inputs", []):
            if isinstance(inp, dict):
                inputs.append(SkillInput(**inp))
            elif isinstance(inp, str):
                inputs.append(SkillInput(name=inp, description=""))
        
        # 解析 outputs
        outputs = []
        for out in skill_data.get("outputs", []):
            if isinstance(out, dict):
                outputs.append(SkillOutput(**out))
            elif isinstance(out, str):
                try:
                    outputs.append(SkillOutput(type=OutputType(out)))
                except ValueError:
                    outputs.append(SkillOutput(type=OutputType.TEXT))
        
        # 解析 evolution
        evolution = skill_data.get("evolution", "stable")
        if isinstance(evolution, str):
            try:
                evolution = SkillEvolution(evolution)
            except ValueError:
                evolution = SkillEvolution.STABLE
        
        manifest = SkillManifest(
            id=skill_data["id"],
            name=skill_data["name"],
            description=skill_data.get("description", ""),
            category=category,
            trigger_phrases=skill_data.get("trigger", []),
            agent=agent,
            inputs=inputs,
            outputs=outputs,
            tools=skill_data.get("tools", []),
            conversation_starters=skill_data.get("conversation_starters", []),
            examples=skill_data.get("examples", []),
            evolution=evolution,
            priority=skill_data.get("priority", 5),
            metadata=skill_data,
        )
        
        self.register(manifest, content)
        return manifest
        
    def get_skill(self, skill_id: str) -> Optional[SkillManifest]:
        """获取技能清单"""
        return self._skills.get(skill_id)
    
    def get_skill_content(self, skill_id: str) -> Optional[str]:
        """获取技能内容"""
        return self._skill_content.get(skill_id)
    
    def list_skills(
        self, 
        category: Optional[SkillCategory] = None,
        agent: Optional[AgentType] = None,
        evolution: Optional[SkillEvolution] = None,
    ) -> List[SkillManifest]:
        """列出所有技能（可按类别/代理类型/进化状态过滤）"""
        skills = list(self._skills.values())
        
        if category:
            skills = [s for s in skills if s.category == category]
        if agent:
            skills = [s for s in skills if s.agent == agent]
        if evolution:
            skills = [s for s in skills if s.evolution == evolution]
            
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
            
    def evolve_skill(
        self,
        parent_id: str,
        new_manifest: SkillManifest,
        content: str = "",
        evolution_note: str = ""
    ) -> SkillManifest:
        """
        进化技能（创建新版本）
        
        Args:
            parent_id: 父技能 ID
            new_manifest: 新技能清单
            content: 新技能内容
            evolution_note: 进化说明
            
        Returns:
            创建的新技能
        """
        # 记录进化历史
        if parent_id not in self._evolution_history:
            self._evolution_history[parent_id] = []
        
        self._evolution_history[parent_id].append({
            "evolved_to": new_manifest.id,
            "timestamp": datetime.now().isoformat(),
            "note": evolution_note,
        })
        
        # 设置父子关系
        new_manifest.parent_skill = parent_id
        new_manifest.evolution = SkillEvolution.STABLE
        new_manifest.created_at = datetime.now()
        new_manifest.updated_at = datetime.now()
        
        self.register(new_manifest, content)
        logger.info(f"[SkillRegistry] 技能进化: {parent_id} -> {new_manifest.id}")
        
        return new_manifest
    
    def update_usage_stats(self, skill_id: str, success: bool):
        """更新技能使用统计"""
        skill = self._skills.get(skill_id)
        if not skill:
            return
            
        skill.usage_count += 1
        # 计算新成功率
        total = skill.usage_count
        prev_successes = skill.success_rate * (total - 1)
        skill.success_rate = (prev_successes + (1 if success else 0)) / total
        
        # 如果成功率过低，标记为需要改进
        if skill.success_rate < 0.5 and skill.evolution == SkillEvolution.STABLE:
            skill.evolution = SkillEvolution.LEARNING
            logger.warning(f"[SkillRegistry] 技能 {skill_id} 成功率低，建议改进")
        
        skill.updated_at = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取注册统计"""
        return {
            "total_skills": len(self._skills),
            "enabled_skills": sum(1 for s in self._skills.values() if s.enabled),
            "learning_skills": sum(1 for s in self._skills.values() if s.evolution == SkillEvolution.LEARNING),
            "seed_skills": sum(1 for s in self._skills.values() if s.evolution == SkillEvolution.SEED),
            "categories": list(set(s.category.value for s in self._skills.values())),
            "agent_types": list(set(s.agent.value for s in self._skills.values())),
            "total_evolutions": sum(len(h) for h in self._evolution_history.values()),
        }
