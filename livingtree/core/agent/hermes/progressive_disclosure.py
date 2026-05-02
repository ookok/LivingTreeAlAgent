"""
ProgressiveDisclosure - 渐进式信息披露

参考 agent-skills 的渐进式信息披露设计，根据任务类型按需加载专家角色，
避免无效内容占用 token。

核心功能：
1. 根据任务类型动态加载专家角色
2. 按阶段披露信息（逐步增加细节）
3. 基于上下文决定披露深度
4. 支持动态扩展和收缩信息范围
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
import json
from datetime import datetime


class DisclosureLevel(Enum):
    """信息披露级别"""
    MINIMAL = "minimal"      # 最小信息（仅核心内容）
    BASIC = "basic"          # 基础信息
    DETAILED = "detailed"    # 详细信息
    FULL = "full"            # 完整信息


class TaskType(Enum):
    """任务类型"""
    CODE = "code"
    TESTING = "testing"
    DESIGN = "design"
    ANALYSIS = "analysis"
    WRITING = "writing"
    RESEARCH = "research"
    DEBUGGING = "debugging"
    OPTIMIZATION = "optimization"


@dataclass
class ExpertRole:
    """专家角色"""
    name: str
    description: str
    skills: List[str]
    task_types: List[TaskType]
    disclosure_templates: Dict[DisclosureLevel, str]
    enabled: bool = True


@dataclass
class DisclosureContext:
    """披露上下文"""
    task_type: TaskType
    current_level: DisclosureLevel
    task_completion: float = 0.0
    user_engagement: float = 1.0
    complexity: float = 0.5


class ProgressiveDisclosure:
    """
    渐进式信息披露管理器
    
    核心功能：
    1. 根据任务类型动态加载专家角色
    2. 按阶段披露信息（逐步增加细节）
    3. 基于上下文决定披露深度
    4. 支持动态扩展和收缩信息范围
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ProgressiveDisclosure")
        self._expert_roles: Dict[str, ExpertRole] = self._load_expert_roles()
        self._active_roles: List[str] = []
        self._disclosure_history: List[Dict[str, Any]] = []
    
    def _load_expert_roles(self) -> Dict[str, ExpertRole]:
        """加载专家角色定义"""
        return {
            "code_expert": ExpertRole(
                name="代码专家",
                description="精通多种编程语言和编程范式",
                skills=["Python", "JavaScript", "TypeScript", "设计模式", "代码优化"],
                task_types=[TaskType.CODE, TaskType.DEBUGGING, TaskType.OPTIMIZATION],
                disclosure_templates={
                    DisclosureLevel.MINIMAL: "代码专家可用",
                    DisclosureLevel.BASIC: "代码专家：精通 Python、JavaScript、TypeScript",
                    DisclosureLevel.DETAILED: "代码专家：精通多种编程语言，擅长设计模式和代码优化",
                    DisclosureLevel.FULL: "代码专家：精通 Python、JavaScript、TypeScript 等语言，擅长设计模式、代码优化、性能调优和代码审查"
                }
            ),
            "testing_expert": ExpertRole(
                name="测试专家",
                description="精通测试策略和实践",
                skills=["单元测试", "集成测试", "TDD", "测试覆盖率"],
                task_types=[TaskType.TESTING, TaskType.DEBUGGING],
                disclosure_templates={
                    DisclosureLevel.MINIMAL: "测试专家可用",
                    DisclosureLevel.BASIC: "测试专家：精通单元测试和集成测试",
                    DisclosureLevel.DETAILED: "测试专家：精通 TDD、测试覆盖率分析",
                    DisclosureLevel.FULL: "测试专家：精通单元测试、集成测试、TDD、BDD、测试覆盖率分析和自动化测试"
                }
            ),
            "design_expert": ExpertRole(
                name="设计专家",
                description="精通系统设计和架构",
                skills=["架构设计", "微服务", "系统设计", "API 设计"],
                task_types=[TaskType.DESIGN, TaskType.ANALYSIS],
                disclosure_templates={
                    DisclosureLevel.MINIMAL: "设计专家可用",
                    DisclosureLevel.BASIC: "设计专家：精通系统架构设计",
                    DisclosureLevel.DETAILED: "设计专家：精通微服务架构和 API 设计",
                    DisclosureLevel.FULL: "设计专家：精通系统架构设计、微服务、分布式系统、API 设计和技术选型"
                }
            ),
            "writing_expert": ExpertRole(
                name="写作专家",
                description="精通技术文档编写",
                skills=["技术写作", "文档架构", "技术翻译"],
                task_types=[TaskType.WRITING, TaskType.RESEARCH],
                disclosure_templates={
                    DisclosureLevel.MINIMAL: "写作专家可用",
                    DisclosureLevel.BASIC: "写作专家：精通技术文档编写",
                    DisclosureLevel.DETAILED: "写作专家：精通技术写作和文档架构",
                    DisclosureLevel.FULL: "写作专家：精通技术文档编写、技术翻译、文档架构和技术传播"
                }
            ),
            "research_expert": ExpertRole(
                name="研究专家",
                description="精通技术研究和分析",
                skills=["文献检索", "技术分析", "趋势预测"],
                task_types=[TaskType.RESEARCH, TaskType.ANALYSIS],
                disclosure_templates={
                    DisclosureLevel.MINIMAL: "研究专家可用",
                    DisclosureLevel.BASIC: "研究专家：精通技术研究",
                    DisclosureLevel.DETAILED: "研究专家：精通文献检索和技术分析",
                    DisclosureLevel.FULL: "研究专家：精通文献检索、技术分析、趋势预测和竞品分析"
                }
            )
        }
    
    def get_relevant_roles(self, task_type: TaskType) -> List[str]:
        """
        获取与任务类型相关的专家角色
        
        Args:
            task_type: 任务类型
            
        Returns:
            相关角色名称列表
        """
        relevant = []
        for role_name, role in self._expert_roles.items():
            if task_type in role.task_types and role.enabled:
                relevant.append(role_name)
        return relevant
    
    def disclose(self, context: DisclosureContext) -> Dict[str, Any]:
        """
        根据上下文披露信息
        
        Args:
            context: 披露上下文
            
        Returns:
            披露的信息
        """
        # 获取相关角色
        relevant_roles = self.get_relevant_roles(context.task_type)
        
        # 决定披露级别
        level = self._determine_disclosure_level(context)
        
        # 构建披露内容
        disclosure = {
            "task_type": context.task_type.value,
            "disclosure_level": level.value,
            "expert_roles": []
        }
        
        for role_name in relevant_roles:
            role = self._expert_roles[role_name]
            disclosure["expert_roles"].append({
                "name": role.name,
                "description": role.disclosure_templates.get(level, ""),
                "skills": self._filter_skills(role.skills, level)
            })
        
        # 记录披露历史
        self._disclosure_history.append({
            "timestamp": datetime.now().isoformat(),
            "task_type": context.task_type.value,
            "level": level.value,
            "roles": relevant_roles
        })
        
        self._logger.debug(f"披露信息: {len(relevant_roles)} 个专家角色，级别: {level.value}")
        
        return disclosure
    
    def _determine_disclosure_level(self, context: DisclosureContext) -> DisclosureLevel:
        """
        根据上下文决定披露级别
        
        决策因素：
        1. 任务完成度（完成度越高，披露越详细）
        2. 用户参与度（参与度越高，披露越详细）
        3. 任务复杂度（复杂度越高，披露越详细）
        """
        score = (context.task_completion * 0.4 + 
                 context.user_engagement * 0.3 + 
                 context.complexity * 0.3)
        
        if score < 0.25:
            return DisclosureLevel.MINIMAL
        elif score < 0.5:
            return DisclosureLevel.BASIC
        elif score < 0.75:
            return DisclosureLevel.DETAILED
        else:
            return DisclosureLevel.FULL
    
    def _filter_skills(self, skills: List[str], level: DisclosureLevel) -> List[str]:
        """
        根据披露级别筛选技能
        
        Args:
            skills: 完整技能列表
            level: 披露级别
            
        Returns:
            筛选后的技能列表
        """
        level_limits = {
            DisclosureLevel.MINIMAL: 1,
            DisclosureLevel.BASIC: 2,
            DisclosureLevel.DETAILED: 3,
            DisclosureLevel.FULL: len(skills)
        }
        
        limit = level_limits.get(level, len(skills))
        return skills[:limit]
    
    def update_disclosure_level(self, task_type: TaskType, new_level: DisclosureLevel):
        """
        更新披露级别
        
        Args:
            task_type: 任务类型
            new_level: 新的披露级别
        """
        self._logger.info(f"更新披露级别: {task_type.value} -> {new_level.value}")
    
    def enable_role(self, role_name: str):
        """启用专家角色"""
        if role_name in self._expert_roles:
            self._expert_roles[role_name].enabled = True
            self._logger.info(f"启用专家角色: {role_name}")
    
    def disable_role(self, role_name: str):
        """禁用专家角色"""
        if role_name in self._expert_roles:
            self._expert_roles[role_name].enabled = False
            self._logger.info(f"禁用专家角色: {role_name}")
    
    def add_custom_role(self, role: ExpertRole):
        """添加自定义专家角色"""
        self._expert_roles[role.name.lower().replace(" ", "_")] = role
        self._logger.info(f"添加自定义角色: {role.name}")
    
    def get_disclosure_history(self) -> List[Dict[str, Any]]:
        """获取披露历史"""
        return self._disclosure_history
    
    def estimate_token_savings(self, context: DisclosureContext) -> Dict[str, Any]:
        """
        估算 token 节省
        
        Args:
            context: 披露上下文
            
        Returns:
            token 节省估算
        """
        full_disclosure = self.disclose(DisclosureContext(
            task_type=context.task_type,
            current_level=DisclosureLevel.FULL,
            task_completion=1.0
        ))
        
        current_disclosure = self.disclose(context)
        
        # 简单估算：基于角色描述长度
        full_chars = sum(len(r["description"]) for r in full_disclosure["expert_roles"])
        current_chars = sum(len(r["description"]) for r in current_disclosure["expert_roles"])
        
        # 粗略估算：1 token ≈ 4 chars
        savings_percent = ((full_chars - current_chars) / max(full_chars, 1)) * 100
        
        return {
            "full_chars": full_chars,
            "current_chars": current_chars,
            "savings_percent": savings_percent,
            "estimated_token_savings": (full_chars - current_chars) // 4
        }
    
    def suggest_next_disclosure(self, task_progress: float) -> Optional[DisclosureLevel]:
        """
        根据任务进度建议下一个披露级别
        
        Args:
            task_progress: 任务进度（0-1）
            
        Returns:
            建议的披露级别
        """
        if task_progress < 0.25:
            return DisclosureLevel.MINIMAL
        elif task_progress < 0.5:
            return DisclosureLevel.BASIC
        elif task_progress < 0.75:
            return DisclosureLevel.DETAILED
        else:
            return DisclosureLevel.FULL