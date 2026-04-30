"""
自动化集成模块 (Automation Integration)

将 AgentWorkflow 框架与系统自动化机制集成：
1. 工作流定时调度
2. Agent 执行自动化任务
3. 事件驱动的自动化流程
4. 与 CronScheduler 集成
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from business.agent_workflow import (
    WorkflowEngine, 
    WorkflowBuilder, 
    WorkflowResult,
    register_workflow,
    execute_workflow as execute_agent_workflow
)
from business.agent_adapter import (
    create_agent_adapter, 
    AgentConfig, 
    AgentResponse
)
from business.shared.event_bus import EventBus, Event
from business.agent_skills.cron_scheduler import (
    CronScheduler, 
    ScheduledTask, 
    TaskStatus,
    TaskPriority
)


@dataclass
class AutomationJob:
    """自动化作业"""
    job_id: str
    name: str
    description: str = ""
    workflow_id: Optional[str] = None
    agent_action: Optional[str] = None
    schedule_type: str = "interval"  # cron, interval, once
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


class WorkflowScheduler:
    """
    工作流调度器
    
    将 AgentWorkflow 与定时任务系统集成
    """
    
    def __init__(self):
        self._scheduler = CronScheduler(max_concurrent=10)
        self._event_bus = EventBus()
        self._jobs: Dict[str, AutomationJob] = {}
        
        # 设置回调
        self._scheduler.set_callbacks(
            on_execute=self._on_task_execute,
            on_complete=self._on_task_complete,
            on_error=self._on_task_error
        )
        
    def _on_task_execute(self, task: ScheduledTask):
        """任务执行回调"""
        print(f"[WorkflowScheduler] 任务开始执行: {task.name}")
        self._event_bus.publish(Event(
            event_type="automation.task.started",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "timestamp": datetime.now().isoformat()
            }
        ))
    
    def _on_task_complete(self, task: ScheduledTask):
        """任务完成回调"""
        print(f"[WorkflowScheduler] 任务执行完成: {task.name}, 结果: {task.last_result}")
        self._event_bus.publish(Event(
            event_type="automation.task.completed",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "result": task.last_result,
                "error": task.last_error,
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        # 更新作业状态
        job = self._jobs.get(task.task_id.replace("interval-", "").replace("cron-", "").replace("-once", ""))
        if job:
            job.last_run_at = task.last_run
            job.next_run_at = task.next_run
    
    def _on_task_error(self, task: ScheduledTask, error: Exception):
        """任务错误回调"""
        print(f"[WorkflowScheduler] 任务执行失败: {task.name}, 错误: {error}")
        self._event_bus.publish(Event(
            event_type="automation.task.failed",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "error": str(error),
                "timestamp": datetime.now().isoformat()
            }
        ))
    
    def schedule_workflow(self, job: AutomationJob) -> str:
        """
        调度工作流执行
        
        Args:
            job: 自动化作业配置
            
        Returns:
            任务 ID
        """
        # 注册工作流
        if job.workflow_id:
            # 工作流已存在，直接调度
            pass
        
        # 创建定时任务
        if job.schedule_type == "cron":
            cron_expr = job.schedule_config.get("cron", "0 9 * * *")
            task = self._scheduler.schedule_cron(
                name=job.name,
                cron_expression=cron_expr,
                command=f"workflow:{job.workflow_id}",
                params=job.params,
                tags=["workflow", job.job_id]
            )
        elif job.schedule_type == "interval":
            interval = job.schedule_config.get("interval", 3600)  # 默认1小时
            task = self._scheduler.schedule_interval(
                name=job.name,
                interval=interval,
                command=f"workflow:{job.workflow_id}",
                params=job.params,
                tags=["workflow", job.job_id]
            )
        elif job.schedule_type == "once":
            scheduled_time = job.schedule_config.get("time", datetime.now() + timedelta(minutes=5))
            task = self._scheduler.schedule_once(
                name=job.name,
                scheduled_time=scheduled_time,
                command=f"workflow:{job.workflow_id}",
                params=job.params,
                tags=["workflow", job.job_id]
            )
        else:
            raise ValueError(f"未知的调度类型: {job.schedule_type}")
        
        # 保存作业配置
        job.next_run_at = task.next_run
        self._jobs[job.job_id] = job
        
        print(f"[WorkflowScheduler] 已调度工作流作业: {job.name}")
        return task.task_id
    
    def schedule_agent_action(self, job: AutomationJob) -> str:
        """
        调度 Agent 动作执行
        
        Args:
            job: 自动化作业配置
            
        Returns:
            任务 ID
        """
        if job.schedule_type == "cron":
            cron_expr = job.schedule_config.get("cron", "0 9 * * *")
            task = self._scheduler.schedule_cron(
                name=job.name,
                cron_expression=cron_expr,
                agent_action=job.agent_action,
                params=job.params,
                tags=["agent", job.job_id]
            )
        elif job.schedule_type == "interval":
            interval = job.schedule_config.get("interval", 3600)
            task = self._scheduler.schedule_interval(
                name=job.name,
                interval=interval,
                agent_action=job.agent_action,
                params=job.params,
                tags=["agent", job.job_id]
            )
        elif job.schedule_type == "once":
            scheduled_time = job.schedule_config.get("time", datetime.now() + timedelta(minutes=5))
            task = self._scheduler.schedule_once(
                name=job.name,
                scheduled_time=scheduled_time,
                agent_action=job.agent_action,
                params=job.params,
                tags=["agent", job.job_id]
            )
        else:
            raise ValueError(f"未知的调度类型: {job.schedule_type}")
        
        job.next_run_at = task.next_run
        self._jobs[job.job_id] = job
        
        print(f"[WorkflowScheduler] 已调度 Agent 动作: {job.name}")
        return task.task_id
    
    def start(self):
        """启动调度器"""
        self._scheduler.start()
        print("[WorkflowScheduler] 工作流调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self._scheduler.stop()
        print("[WorkflowScheduler] 工作流调度器已停止")
    
    def list_jobs(self) -> List[AutomationJob]:
        """列出所有作业"""
        return list(self._jobs.values())
    
    def get_job(self, job_id: str) -> Optional[AutomationJob]:
        """获取作业"""
        return self._jobs.get(job_id)
    
    def remove_job(self, job_id: str) -> bool:
        """移除作业"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False


class AgentActionExecutor:
    """
    Agent 动作执行器
    
    通过 Agent 执行自动化任务
    """
    
    def __init__(self):
        self._agent_cache: Dict[str, Any] = {}
        self._event_bus = EventBus()
    
    def _get_agent(self, agent_type: str, model_name: str = "default"):
        """获取或创建 Agent"""
        cache_key = f"{agent_type}:{model_name}"
        
        if cache_key not in self._agent_cache:
            config = AgentConfig(
                agent_type=agent_type,
                model_name=model_name
            )
            self._agent_cache[cache_key] = create_agent_adapter(config)
        
        return self._agent_cache[cache_key]
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> AgentResponse:
        """
        执行 Agent 动作
        
        Args:
            action: 动作名称
            params: 动作参数
            
        Returns:
            Agent 响应
        """
        # 解析动作配置
        agent_type = params.get("agent_type", "local")
        model_name = params.get("model", "Qwen/Qwen2.5-7B-Instruct")
        prompt = params.get("prompt", "")
        
        if not prompt:
            # 根据动作名称生成提示词
            prompt = self._generate_prompt(action, params)
        
        # 获取 Agent
        agent = self._get_agent(agent_type, model_name)
        
        # 执行动作
        print(f"[AgentActionExecutor] 执行动作: {action}, Agent: {agent_type}")
        
        result = await agent.async_generate(prompt)
        
        # 发布事件
        self._event_bus.publish(Event(
            event_type="automation.action.executed",
            data={
                "action": action,
                "agent_type": agent_type,
                "model": model_name,
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        return result
    
    def _generate_prompt(self, action: str, params: Dict[str, Any]) -> str:
        """根据动作生成提示词"""
        action_templates = {
            "auto_document": """请为以下代码生成详细的技术文档：

代码内容：
{code}

请输出：
1. 模块概述
2. 类/函数说明
3. 参数和返回值
4. 使用示例
""",
            "auto_test": """请为以下代码生成单元测试：

代码内容：
{code}

测试需求：
{requirements}

请输出完整的 pytest 测试代码。
""",
            "code_review": """请审查以下代码：

代码内容：
{code}

请指出：
1. 潜在的 bug
2. 代码优化建议
3. 安全问题
4. 性能问题
""",
            "summarize": """请总结以下内容：

{content}

要求：简洁明了，突出重点。
""",
            "translate": """请将以下内容翻译成{target_language}：

{content}
"""
        }
        
        template = action_templates.get(action)
        if template:
            return template.format(**params)
        
        return f"执行动作: {action}\n参数: {params}"


class AutoWorkflowGenerator:
    """
    自动化工作流生成器
    
    根据需求自动生成工作流定义
    """
    
    @staticmethod
    def create_periodic_sync_workflow(source: str, target: str, interval_hours: int = 1) -> str:
        """
        创建周期性数据同步工作流
        
        Args:
            source: 数据源
            target: 数据目标
            interval_hours: 同步间隔（小时）
            
        Returns:
            工作流 ID
        """
        workflow_id = f"sync_{source}_{target}"
        
        def sync_data(vars):
            print(f"[SyncWorkflow] 同步数据: {source} -> {target}")
            return {"synced": True, "records": 100}
        
        def validate_data(vars):
            print(f"[SyncWorkflow] 验证数据")
            return {"validated": True, "errors": 0}
        
        workflow = WorkflowBuilder(workflow_id, "sequential")\
            .start("开始同步")\
            .action("sync", sync_data, "执行同步")\
            .action("validate", validate_data, "验证数据")\
            .end("同步完成")\
            .build()
        
        register_workflow(workflow)
        return workflow_id
    
    @staticmethod
    def create_daily_report_workflow(report_type: str = "summary") -> str:
        """
        创建每日报告工作流
        
        Args:
            report_type: 报告类型
            
        Returns:
            工作流 ID
        """
        workflow_id = f"daily_report_{report_type}"
        
        def collect_data(vars):
            print(f"[ReportWorkflow] 收集数据")
            return {"data_collected": True}
        
        def generate_report(vars):
            print(f"[ReportWorkflow] 生成报告: {report_type}")
            return {"report_generated": True, "report_path": "/reports/daily.pdf"}
        
        def send_report(vars):
            print(f"[ReportWorkflow] 发送报告")
            return {"sent": True}
        
        workflow = WorkflowBuilder(workflow_id, "sequential")\
            .start("开始生成报告")\
            .action("collect", collect_data, "收集数据")\
            .action("generate", generate_report, "生成报告")\
            .action("send", send_report, "发送报告")\
            .end("报告完成")\
            .build()
        
        register_workflow(workflow)
        return workflow_id
    
    @staticmethod
    def create_health_check_workflow(checks: List[str]) -> str:
        """
        创建健康检查工作流
        
        Args:
            checks: 检查项列表
            
        Returns:
            工作流 ID
        """
        workflow_id = "health_check"
        
        def run_checks(vars):
            results = {}
            for check in checks:
                results[check] = True  # 模拟检查通过
                print(f"[HealthCheck] {check}: OK")
            return {"checks": results, "all_passed": True}
        
        workflow = WorkflowBuilder(workflow_id, "sequential")\
            .start("开始健康检查")\
            .action("check", run_checks, "执行检查")\
            .end("检查完成")\
            .build()
        
        register_workflow(workflow)
        return workflow_id


# 创建全局实例
_workflow_scheduler = WorkflowScheduler()
_agent_executor = AgentActionExecutor()


def get_workflow_scheduler() -> WorkflowScheduler:
    """获取工作流调度器实例"""
    return _workflow_scheduler


def get_agent_executor() -> AgentActionExecutor:
    """获取 Agent 执行器实例"""
    return _agent_executor


async def execute_workflow(workflow_id: str, input_data: Optional[Dict] = None) -> WorkflowResult:
    """执行工作流（便捷函数）"""
    return await execute_agent_workflow(workflow_id, input_data)


__all__ = [
    "AutomationJob",
    "WorkflowScheduler",
    "AgentActionExecutor",
    "AutoWorkflowGenerator",
    "get_workflow_scheduler",
    "get_agent_executor",
    "execute_workflow"
]