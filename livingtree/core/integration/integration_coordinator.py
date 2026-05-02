"""
集成协调器 - Integration Coordinator

功能：
1. 跨系统工作流编排
2. 智能决策协调
3. 资源调度与优化
4. 全局状态管理

核心协调场景：
- 记忆-学习-推理闭环
- 自我意识驱动的系统优化
- MCP服务与本地服务的协同
- 故障恢复与系统自愈
"""

import logging
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    system: str
    method: str
    params: Dict = None
    dependencies: List[str] = None
    retry_count: int = 0
    max_retries: int = 2
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class WorkflowInstance:
    """工作流实例"""
    workflow_id: str
    name: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    results: Dict = None
    created_at: float = None
    started_at: float = None
    completed_at: float = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = {}
        if self.created_at is None:
            self.created_at = time.time()


class IntegrationCoordinator:
    """
    集成协调器 - 协调多个系统协作完成复杂任务
    
    核心能力：
    1. 工作流编排
    2. 智能决策
    3. 资源优化
    4. 状态同步
    """
    
    def __init__(self):
        self._caller = None
        self._context = None
        self._workflows: Dict[str, WorkflowInstance] = {}
        
        # 注册默认工作流
        self._register_default_workflows()
    
    def _get_caller(self):
        """延迟获取跨系统调用器"""
        if self._caller is None:
            from .cross_system_caller import get_cross_system_caller
            self._caller = get_cross_system_caller()
        return self._caller
    
    def _get_context(self):
        """延迟获取上下文管理器"""
        if self._context is None:
            from .context_manager import get_context_manager
            self._context = get_context_manager()
        return self._context
    
    def _register_default_workflows(self):
        """注册默认工作流"""
        # 记忆-学习-推理闭环工作流
        self._memory_learning_reasoning_workflow = [
            WorkflowStep(
                id="store_memory",
                system="brain_memory",
                method="store_short_term",
                params={"metadata": {"source": "user_input"}}
            ),
            WorkflowStep(
                id="update_knowledge",
                system="cognitive_reasoning",
                method="update_knowledge",
                dependencies=["store_memory"]
            ),
            WorkflowStep(
                id="learn",
                system="continual_learning",
                method="learn_from_memory",
                dependencies=["store_memory"]
            ),
            WorkflowStep(
                id="reflect",
                system="self_awareness",
                method="reflect",
                dependencies=["learn"]
            )
        ]
        
        # MCP降级工作流
        self._mcp_fallback_workflow = [
            WorkflowStep(
                id="check_mcp",
                system="mcp_service",
                method="get_status"
            ),
            WorkflowStep(
                id="fallback",
                system="self_awareness",
                method="update_system_state",
                params={"mcp_available": False}
            )
        ]
    
    def execute_workflow(self, workflow_name: str, inputs: Dict = None) -> Dict:
        """
        执行工作流
        
        Args:
            workflow_name: 工作流名称
            inputs: 输入参数
        
        Returns:
            执行结果
        """
        workflow_def = self._get_workflow_definition(workflow_name)
        
        if not workflow_def:
            return {"success": False, "error": f"工作流不存在: {workflow_name}"}
        
        workflow_id = f"wf_{int(time.time() * 1000)}"
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            name=workflow_name,
            steps=workflow_def
        )
        
        self._workflows[workflow_id] = instance
        
        return self._execute_workflow_steps(instance, inputs or {})
    
    def _get_workflow_definition(self, name: str) -> Optional[List[WorkflowStep]]:
        """获取工作流定义"""
        workflows = {
            "memory_learning_reasoning": self._memory_learning_reasoning_workflow,
            "mcp_fallback": self._mcp_fallback_workflow
        }
        return workflows.get(name)
    
    def _execute_workflow_steps(self, instance: WorkflowInstance, inputs: Dict) -> Dict:
        """执行工作流步骤"""
        instance.status = WorkflowStatus.RUNNING
        instance.started_at = time.time()
        
        caller = self._get_caller()
        completed_steps = set()
        
        try:
            # 按依赖顺序执行步骤
            while completed_steps != {step.id for step in instance.steps}:
                for step in instance.steps:
                    if step.id in completed_steps:
                        continue
                    
                    # 检查依赖是否完成
                    if not set(step.dependencies).issubset(completed_steps):
                        continue
                    
                    # 执行步骤
                    params = {**step.params, **inputs}
                    result = caller.call(step.system, step.method, **params)
                    
                    instance.results[step.id] = result
                    completed_steps.add(step.id)
                    
                    if not result.get('success', True):
                        # 尝试重试
                        if step.retry_count < step.max_retries:
                            step.retry_count += 1
                            completed_steps.remove(step.id)
                            continue
                        
                        instance.status = WorkflowStatus.FAILED
                        return {
                            "success": False,
                            "error": f"步骤失败: {step.id}",
                            "results": instance.results
                        }
            
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = time.time()
            
            return {
                "success": True,
                "workflow_id": instance.workflow_id,
                "results": instance.results,
                "execution_time": instance.completed_at - instance.started_at
            }
        
        except Exception as e:
            instance.status = WorkflowStatus.FAILED
            logger.error(f"工作流执行失败 {instance.workflow_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": instance.results
            }
    
    def run_memory_learning_reasoning_cycle(self, content: str) -> Dict:
        """
        运行记忆-学习-推理闭环
        
        Args:
            content: 输入内容
        
        Returns:
            执行结果
        """
        return self.execute_workflow("memory_learning_reasoning", {
            "content": content
        })
    
    def handle_mcp_disconnect(self) -> Dict:
        """
        处理MCP断开连接
        
        Returns:
            执行结果
        """
        return self.execute_workflow("mcp_fallback")
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowInstance]:
        """获取工作流状态"""
        return self._workflows.get(workflow_id)
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        workflow = self._workflows.get(workflow_id)
        if workflow and workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.CANCELLED
            return True
        return False
    
    def get_running_workflows(self) -> List[WorkflowInstance]:
        """获取运行中的工作流"""
        return [w for w in self._workflows.values() if w.status == WorkflowStatus.RUNNING]
    
    def clear_completed_workflows(self):
        """清理已完成的工作流"""
        completed = [wf_id for wf_id, wf in self._workflows.items() 
                    if wf.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]]
        
        for wf_id in completed:
            del self._workflows[wf_id]
    
    def orchestrate_task(self, task_type: str, **kwargs) -> Dict:
        """
        编排任务 - 根据任务类型自动选择合适的系统组合
        
        Args:
            task_type: 任务类型
            **kwargs: 任务参数
        
        Returns:
            执行结果
        """
        orchestration_map = {
            "analyze": self._orchestrate_analysis,
            "learn": self._orchestrate_learning,
            "decide": self._orchestrate_decision,
            "create": self._orchestrate_creation,
            "problem_solve": self._orchestrate_problem_solving
        }
        
        handler = orchestration_map.get(task_type)
        if handler:
            return handler(**kwargs)
        else:
            return {"success": False, "error": f"未知任务类型: {task_type}"}
    
    def _orchestrate_analysis(self, **kwargs) -> Dict:
        """编排分析任务"""
        caller = self._get_caller()
        
        # 1. 检索相关记忆
        memory_result = caller.call('brain_memory', 'retrieve', query=kwargs.get('query', ''))
        
        # 2. 执行推理分析
        reasoning_result = caller.call('cognitive_reasoning', 'reason',
                                     query=kwargs.get('query', ''),
                                     reasoning_type='causal')
        
        # 3. 存储分析结果
        caller.call('brain_memory', 'store_short_term',
                   content=reasoning_result.get('data', {}).get('result', ''),
                   metadata={'source': 'analysis'})
        
        return {
            "success": True,
            "memory": memory_result,
            "reasoning": reasoning_result
        }
    
    def _orchestrate_learning(self, **kwargs) -> Dict:
        """编排学习任务"""
        return self.run_memory_learning_reasoning_cycle(kwargs.get('content', ''))
    
    def _orchestrate_decision(self, **kwargs) -> Dict:
        """编排决策任务"""
        caller = self._get_caller()
        
        # 获取当前目标
        goals = caller.call('self_awareness', 'get_active_goals')
        
        # 执行推理
        reasoning_result = caller.call('cognitive_reasoning', 'reason',
                                     query=kwargs.get('question', ''),
                                     reasoning_type='counterfactual')
        
        # 更新目标进度
        caller.call('self_awareness', 'reflect')
        
        return {
            "success": True,
            "goals": goals,
            "decision": reasoning_result
        }
    
    def _orchestrate_creation(self, **kwargs) -> Dict:
        """编排创作任务"""
        caller = self._get_caller()
        
        # 使用MCP工具或本地生成
        mcp_status = caller.call('mcp_service', 'get_status')
        
        if mcp_status.get('data', {}).get('service_status') == 'connected':
            result = caller.call('mcp_service', 'call_tool',
                               tool_name='code_execution',
                               code=kwargs.get('prompt', ''))
        else:
            # 降级到本地推理
            result = caller.call('cognitive_reasoning', 'reason',
                               query=kwargs.get('prompt', ''),
                               reasoning_type='symbolic')
        
        # 存储结果
        caller.call('brain_memory', 'store_long_term',
                   content=str(result.get('data', '')),
                   metadata={'source': 'creation'})
        
        return result
    
    def _orchestrate_problem_solving(self, **kwargs) -> Dict:
        """编排问题解决任务"""
        caller = self._get_caller()
        
        # 1. 检测问题
        problems = caller.call('self_healing', 'detect_problems')
        
        # 2. 分析根因
        root_cause = caller.call('self_healing', 'analyze_root_cause',
                                problems=problems.get('data', []))
        
        # 3. 执行修复
        fix_result = caller.call('self_healing', 'repair',
                                issue=root_cause.get('data', {}))
        
        # 4. 更新系统状态
        caller.call('self_awareness', 'update_system_state',
                   health_status=fix_result.get('data', {}))
        
        return {
            "success": True,
            "problems": problems,
            "root_cause": root_cause,
            "fix_result": fix_result
        }


# 单例模式
_coordinator_instance = None

def get_integration_coordinator() -> IntegrationCoordinator:
    """获取集成协调器实例"""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = IntegrationCoordinator()
    return _coordinator_instance