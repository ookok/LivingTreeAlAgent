"""
Superpowers 核心引擎

协调技能系统、子代理调度、工作流管理等组件
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .skills import get_skill_registry, get_skill_executor
from .subagent import get_subagent_manager, get_parallel_dispatcher
from .tdd_workflow import get_tdd_workflow
from .trigger_system import get_trigger_system
from .workflow import get_workflow_manager


class SuperpowersMode(Enum):
    """Superpowers 模式"""
    STANDARD = "standard"      # 标准模式
    DEBUG = "debug"           # 调试模式
    PERFORMANCE = "performance"  # 性能模式


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


@dataclass
class SuperpowersConfig:
    """Superpowers 配置"""
    mode: SuperpowersMode = SuperpowersMode.STANDARD
    max_subagents: int = 5
    skill_timeout: int = 300  # 5分钟
    workflow_timeout: int = 3600  # 1小时
    auto_trigger: bool = True
    parallel_execution: bool = True
    tdd_enabled: bool = True
    skill_registry_path: str = "skills"
    workspace_dir: str = ".superpowers"


@dataclass
class WorkflowState:
    """工作流状态"""
    workflow_id: str
    name: str
    status: TaskStatus
    current_task: Optional[str] = None
    completed_tasks: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AgentConfig:
    """代理配置"""
    agent_id: str
    name: str
    model: str = "claude-3-opus-20240229"
    temperature: float = 0.7
    max_tokens: int = 8192
    tools: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class SkillDefinition:
    """技能定义"""
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "system"
    requires: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


class SuperpowersEngine:
    """
    Superpowers 核心引擎

    协调各个组件，提供完整的开发工作流
    """

    def __init__(self, config: Optional[SuperpowersConfig] = None):
        self.config = config or SuperpowersConfig()
        self.workspace_dir = Path(self.config.workspace_dir)
        self._components = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._init_components()
        self._setup_workspace()

    def _init_components(self):
        """初始化组件"""
        # 技能系统
        self._components['skill_registry'] = get_skill_registry()
        self._components['skill_executor'] = get_skill_executor()

        # 子代理系统
        self._components['subagent_manager'] = get_subagent_manager()
        self._components['parallel_dispatcher'] = get_parallel_dispatcher()

        # TDD 工作流
        if self.config.tdd_enabled:
            self._components['tdd_workflow'] = get_tdd_workflow()

        # 触发系统
        if self.config.auto_trigger:
            self._components['trigger_system'] = get_trigger_system()

        # 工作流管理
        self._components['workflow_manager'] = get_workflow_manager()

    def _setup_workspace(self):
        """设置工作空间"""
        dirs = [
            self.workspace_dir,
            self.workspace_dir / "skills",
            self.workspace_dir / "agents",
            self.workspace_dir / "workflows",
            self.workspace_dir / "tests",
            self.workspace_dir / "logs",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def get_component(self, name: str) -> Any:
        """获取组件"""
        return self._components.get(name)

    async def initialize(self):
        """初始化 Superpowers"""
        # 加载技能
        await self._load_skills()
        
        # 初始化子代理
        await self._init_subagents()
        
        # 初始化工作流
        await self._init_workflows()

        print(f"[Superpowers] 初始化完成，模式: {self.config.mode.value}")

    async def _load_skills(self):
        """加载技能"""
        skill_registry = self.get_component('skill_registry')
        if skill_registry:
            skills_dir = self.workspace_dir / "skills"
            await skill_registry.load_skills(skills_dir)
            print(f"[Superpowers] 加载了 {len(skill_registry.get_all_skills())} 个技能")

    async def _init_subagents(self):
        """初始化子代理"""
        subagent_manager = self.get_component('subagent_manager')
        if subagent_manager:
            for i in range(self.config.max_subagents):
                agent_config = AgentConfig(
                    agent_id=f"subagent_{i+1}",
                    name=f"SubAgent {i+1}"
                )
                await subagent_manager.create_agent(agent_config)
            print(f"[Superpowers] 初始化了 {self.config.max_subagents} 个子代理")

    async def _init_workflows(self):
        """初始化工作流"""
        workflow_manager = self.get_component('workflow_manager')
        if workflow_manager:
            # 创建默认工作流
            await workflow_manager.create_workflow(
                name="默认开发工作流",
                description="标准的开发工作流：计划 → 实现 → 测试 → 审查 → 完成"
            )

    async def run_workflow(
        self,
        workflow_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """
        运行工作流

        Args:
            workflow_name: 工作流名称
            parameters: 工作流参数

        Returns:
            WorkflowState: 工作流状态
        """
        workflow_manager = self.get_component('workflow_manager')
        if not workflow_manager:
            raise RuntimeError("Workflow manager not initialized")

        workflow = await workflow_manager.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        state = await workflow.execute(parameters or {})
        return state

    async def execute_skill(
        self,
        skill_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行技能

        Args:
            skill_name: 技能名称
            parameters: 技能参数

        Returns:
            Dict: 执行结果
        """
        skill_executor = self.get_component('skill_executor')
        if not skill_executor:
            raise RuntimeError("Skill executor not initialized")

        result = await skill_executor.execute(skill_name, parameters or {})
        return result

    async def dispatch_subagent(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调度子代理

        Args:
            task: 任务描述
            context: 上下文

        Returns:
            Dict: 执行结果
        """
        parallel_dispatcher = self.get_component('parallel_dispatcher')
        if not parallel_dispatcher:
            raise RuntimeError("Parallel dispatcher not initialized")

        result = await parallel_dispatcher.dispatch(
            task=task,
            context=context or {},
            timeout=self.config.skill_timeout
        )
        return result

    async def run_tdd_cycle(
        self,
        feature: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        运行 TDD 循环

        Args:
            feature: 功能描述
            test_cases: 测试用例

        Returns:
            Dict: TDD 执行结果
        """
        tdd_workflow = self.get_component('tdd_workflow')
        if not tdd_workflow:
            raise RuntimeError("TDD workflow not initialized")

        result = await tdd_workflow.run_cycle(feature, test_cases)
        return result

    async def analyze_context(
        self,
        context: str
    ) -> List[str]:
        """
        分析上下文并推荐技能

        Args:
            context: 上下文文本

        Returns:
            List[str]: 推荐的技能列表
        """
        trigger_system = self.get_component('trigger_system')
        if not trigger_system:
            raise RuntimeError("Trigger system not initialized")

        skills = await trigger_system.analyze_context(context)
        return skills

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict: 统计信息
        """
        stats = {
            "mode": self.config.mode.value,
            "components": list(self._components.keys()),
            "timestamp": time.time()
        }

        # 技能统计
        skill_registry = self.get_component('skill_registry')
        if skill_registry:
            stats['skills'] = {
                "total": len(skill_registry.get_all_skills()),
                "by_category": skill_registry.get_skills_by_category()
            }

        # 子代理统计
        subagent_manager = self.get_component('subagent_manager')
        if subagent_manager:
            stats['subagents'] = {
                "total": len(subagent_manager.get_agents()),
                "active": subagent_manager.get_active_count()
            }

        # 工作流统计
        workflow_manager = self.get_component('workflow_manager')
        if workflow_manager:
            stats['workflows'] = {
                "total": len(workflow_manager.get_workflows())
            }

        return stats

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    async def _emit(self, event: str, *args):
        """触发事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args)
                else:
                    handler(*args)
            except Exception as e:
                print(f"[Superpowers] Event handler error: {e}")

    def shutdown(self):
        """关闭 Superpowers"""
        print("[Superpowers] 正在关闭...")
        # 清理资源
        for name, component in self._components.items():
            if hasattr(component, 'shutdown'):
                try:
                    component.shutdown()
                except Exception as e:
                    print(f"[Superpowers] 关闭组件 {name} 时出错: {e}")
        print("[Superpowers] 已关闭")


_global_engine: Optional[SuperpowersEngine] = None


def get_superpowers_engine(config: Optional[SuperpowersConfig] = None) -> SuperpowersEngine:
    """获取 Superpowers 引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = SuperpowersEngine(config)
    return _global_engine


def create_superpowers_config(**kwargs) -> SuperpowersConfig:
    """创建 Superpowers 配置"""
    return SuperpowersConfig(**kwargs)


def create_agent_config(**kwargs) -> AgentConfig:
    """创建代理配置"""
    return AgentConfig(**kwargs)


def create_skill_definition(**kwargs) -> SkillDefinition:
    """创建技能定义"""
    return SkillDefinition(**kwargs)