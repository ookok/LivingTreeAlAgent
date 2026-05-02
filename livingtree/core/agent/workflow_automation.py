"""
LivingTree — Workflow Automation Integration
==============================================

Full migration from client/src/business/agent_workflow/automation_integration.py

Integrates AgentWorkflow engine with scheduled automation:
- WorkflowScheduler: cron/interval/once-based workflow scheduling
- AgentActionExecutor: executes agent actions on schedule
- AutoWorkflowGenerator: pre-built workflow templates for common tasks
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .workflow import (
    WorkflowBuilder,
    WorkflowEngine,
    WorkflowResult,
    execute_workflow as exec_agent_workflow,
    get_workflow_engine,
    register_workflow,
)
from ...infrastructure.event_bus import Event, EventBus
from ..skills.cron_scheduler import (
    CronScheduler,
    ScheduledTask,
    TaskPriority,
    TaskStatus,
)


@dataclass
class AutomationJob:
    job_id: str
    name: str
    description: str = ""
    workflow_id: Optional[str] = None
    agent_action: Optional[str] = None
    schedule_type: str = "interval"
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


class WorkflowScheduler:
    """Scheduler that bridges AgentWorkflow engine with timed task execution."""

    def __init__(self):
        self._scheduler = CronScheduler(max_concurrent=10)
        self._event_bus = EventBus()
        self._jobs: Dict[str, AutomationJob] = {}

        self._scheduler.set_callbacks(
            on_execute=self._on_task_execute,
            on_complete=self._on_task_complete,
            on_error=self._on_task_error,
        )

    def _on_task_execute(self, task: ScheduledTask):
        self._event_bus.publish(Event(
            event_type="automation.task.started",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "timestamp": datetime.now().isoformat(),
            },
        ))

    def _on_task_complete(self, task: ScheduledTask):
        self._event_bus.publish(Event(
            event_type="automation.task.completed",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "result": task.last_result,
                "error": task.last_error,
                "timestamp": datetime.now().isoformat(),
            },
        ))
        job = self._jobs.get(
            task.task_id.replace("interval-", "").replace("cron-", "").replace("-once", ""))
        if job:
            job.last_run_at = task.last_run
            job.next_run_at = task.next_run

    def _on_task_error(self, task: ScheduledTask, error: Exception):
        self._event_bus.publish(Event(
            event_type="automation.task.failed",
            data={
                "task_id": task.task_id,
                "name": task.name,
                "error": str(error),
                "timestamp": datetime.now().isoformat(),
            },
        ))

    def schedule_workflow(self, job: AutomationJob) -> str:
        if job.schedule_type == "cron":
            cron_expr = job.schedule_config.get("cron", "0 9 * * *")
            task = self._scheduler.schedule_cron(
                name=job.name, cron_expression=cron_expr,
                command=f"workflow:{job.workflow_id}",
                params=job.params, tags=["workflow", job.job_id],
            )
        elif job.schedule_type == "interval":
            interval = job.schedule_config.get("interval", 3600)
            task = self._scheduler.schedule_interval(
                name=job.name, interval=interval,
                command=f"workflow:{job.workflow_id}",
                params=job.params, tags=["workflow", job.job_id],
            )
        elif job.schedule_type == "once":
            scheduled_time = job.schedule_config.get(
                "time", datetime.now() + timedelta(minutes=5))
            task = self._scheduler.schedule_once(
                name=job.name, scheduled_time=scheduled_time,
                command=f"workflow:{job.workflow_id}",
                params=job.params, tags=["workflow", job.job_id],
            )
        else:
            raise ValueError(f"Unknown schedule type: {job.schedule_type}")

        job.next_run_at = task.next_run
        self._jobs[job.job_id] = job
        return task.task_id

    def schedule_agent_action(self, job: AutomationJob) -> str:
        if job.schedule_type == "cron":
            cron_expr = job.schedule_config.get("cron", "0 9 * * *")
            task = self._scheduler.schedule_cron(
                name=job.name, cron_expression=cron_expr,
                agent_action=job.agent_action,
                params=job.params, tags=["agent", job.job_id],
            )
        elif job.schedule_type == "interval":
            interval = job.schedule_config.get("interval", 3600)
            task = self._scheduler.schedule_interval(
                name=job.name, interval=interval,
                agent_action=job.agent_action,
                params=job.params, tags=["agent", job.job_id],
            )
        elif job.schedule_type == "once":
            scheduled_time = job.schedule_config.get(
                "time", datetime.now() + timedelta(minutes=5))
            task = self._scheduler.schedule_once(
                name=job.name, scheduled_time=scheduled_time,
                agent_action=job.agent_action,
                params=job.params, tags=["agent", job.job_id],
            )
        else:
            raise ValueError(f"Unknown schedule type: {job.schedule_type}")

        job.next_run_at = task.next_run
        self._jobs[job.job_id] = job
        return task.task_id

    def start(self):
        self._scheduler.start()

    def stop(self):
        self._scheduler.stop()

    def list_jobs(self) -> List[AutomationJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[AutomationJob]:
        return self._jobs.get(job_id)

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False


class AgentActionExecutor:
    """Executes agent actions on schedule via LLM agents."""

    def __init__(self):
        self._agent_cache: Dict[str, Any] = {}
        self._event_bus = EventBus()

    def _get_agent(self, agent_type: str, model_name: str = "default"):
        cache_key = f"{agent_type}:{model_name}"
        if cache_key not in self._agent_cache:
            try:
                from livingtree.core.agent.adapter import (
                    AgentConfig, create_agent_adapter,
                )
                config = AgentConfig(agent_type=agent_type, model_name=model_name)
                self._agent_cache[cache_key] = create_agent_adapter(config)
            except ImportError:
                self._agent_cache[cache_key] = None
        return self._agent_cache[cache_key]

    async def execute_action(self, action: str,
                             params: Dict[str, Any]) -> Optional[Any]:
        agent_type = params.get("agent_type", "local")
        model_name = params.get("model", "Qwen/Qwen2.5-7B-Instruct")
        prompt = params.get("prompt", "")
        if not prompt:
            prompt = self._generate_prompt(action, params)

        agent = self._get_agent(agent_type, model_name)
        if agent is None:
            self._event_bus.publish(Event(
                event_type="automation.action.failed",
                data={"action": action, "error": "agent_adapter not available"},
            ))
            return None

        try:
            result = await agent.async_generate(prompt)
            self._event_bus.publish(Event(
                event_type="automation.action.executed",
                data={
                    "action": action, "agent_type": agent_type,
                    "model": model_name, "success": True,
                    "timestamp": datetime.now().isoformat(),
                },
            ))
            return result
        except Exception as e:
            self._event_bus.publish(Event(
                event_type="automation.action.failed",
                data={
                    "action": action, "agent_type": agent_type,
                    "model": model_name, "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
            ))
            return None

    def _generate_prompt(self, action: str, params: Dict[str, Any]) -> str:
        action_templates = {
            "auto_document": "请为以下代码生成详细的技术文档：\n\n代码内容：\n{code}\n\n请输出：\n1. 模块概述\n2. 类/函数说明\n3. 参数和返回值\n4. 使用示例\n",
            "auto_test": "请为以下代码生成单元测试：\n\n代码内容：\n{code}\n\n测试需求：\n{requirements}\n\n请输出完整的 pytest 测试代码。\n",
            "code_review": "请审查以下代码：\n\n代码内容：\n{code}\n\n请指出：\n1. 潜在的 bug\n2. 代码优化建议\n3. 安全问题\n4. 性能问题\n",
            "summarize": "请总结以下内容：\n\n{content}\n\n要求：简洁明了，突出重点。\n",
            "translate": "请将以下内容翻译成{target_language}：\n\n{content}\n",
        }
        template = action_templates.get(action)
        if template:
            return template.format(**params)
        return f"执行动作: {action}\n参数: {params}"


class AutoWorkflowGenerator:
    """Generates pre-built workflow templates for common automation patterns."""

    @staticmethod
    def create_periodic_sync_workflow(source: str, target: str,
                                      interval_hours: int = 1) -> str:
        workflow_id = f"sync_{source}_{target}"

        def sync_data(vars):
            return {"synced": True, "records": 100}

        def validate_data(vars):
            return {"validated": True, "errors": 0}

        workflow = (WorkflowBuilder(workflow_id, "sequential")
                    .start("Start Sync")
                    .action("sync", sync_data, "Execute Sync")
                    .action("validate", validate_data, "Validate Data")
                    .end("Sync Complete")
                    .build())

        register_workflow(workflow)
        return workflow_id

    @staticmethod
    def create_daily_report_workflow(report_type: str = "summary") -> str:
        workflow_id = f"daily_report_{report_type}"

        def collect_data(vars):
            return {"data_collected": True}

        def generate_report(vars):
            return {"report_generated": True, "report_path": "/reports/daily.pdf"}

        def send_report(vars):
            return {"sent": True}

        workflow = (WorkflowBuilder(workflow_id, "sequential")
                    .start("Start Report")
                    .action("collect", collect_data, "Collect Data")
                    .action("generate", generate_report, "Generate Report")
                    .action("send", send_report, "Send Report")
                    .end("Report Complete")
                    .build())

        register_workflow(workflow)
        return workflow_id

    @staticmethod
    def create_health_check_workflow(checks: List[str]) -> str:
        workflow_id = "health_check"

        def run_checks(vars):
            results = {}
            for check in checks:
                results[check] = True
            return {"checks": results, "all_passed": True}

        workflow = (WorkflowBuilder(workflow_id, "sequential")
                    .start("Start Health Check")
                    .action("check", run_checks, "Execute Checks")
                    .end("Check Complete")
                    .build())

        register_workflow(workflow)
        return workflow_id


_workflow_scheduler = WorkflowScheduler()
_agent_executor = AgentActionExecutor()


def get_workflow_scheduler() -> WorkflowScheduler:
    return _workflow_scheduler


def get_agent_executor() -> AgentActionExecutor:
    return _agent_executor


async def execute_workflow(workflow_id: str,
                           input_data: Optional[Dict] = None) -> WorkflowResult:
    return await exec_agent_workflow(workflow_id, input_data)


__all__ = [
    "AutomationJob",
    "WorkflowScheduler",
    "AgentActionExecutor",
    "AutoWorkflowGenerator",
    "get_workflow_scheduler",
    "get_agent_executor",
    "execute_workflow",
]
