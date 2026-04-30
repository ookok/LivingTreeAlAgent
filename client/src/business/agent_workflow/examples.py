"""
自动化工作流示例 (Automation Workflow Examples)

展示如何使用自动化集成模块
"""

import asyncio
from datetime import datetime, timedelta
from .automation_integration import (
    AutomationJob,
    WorkflowScheduler,
    AgentActionExecutor,
    AutoWorkflowGenerator,
    get_workflow_scheduler,
    get_agent_executor
)


async def example_periodic_sync():
    """示例：周期性数据同步"""
    print("\n=== 示例1: 周期性数据同步 ===")
    
    # 创建同步工作流
    workflow_id = AutoWorkflowGenerator.create_periodic_sync_workflow(
        source="database",
        target="elasticsearch",
        interval_hours=1
    )
    print(f"创建工作流: {workflow_id}")
    
    # 创建自动化作业
    job = AutomationJob(
        job_id="sync_db_es",
        name="数据库到ES同步",
        description="每小时同步一次数据",
        workflow_id=workflow_id,
        schedule_type="interval",
        schedule_config={"interval": 3600}  # 1小时
    )
    
    # 调度作业
    scheduler = get_workflow_scheduler()
    task_id = scheduler.schedule_workflow(job)
    print(f"调度任务ID: {task_id}")


async def example_daily_report():
    """示例：每日报告生成"""
    print("\n=== 示例2: 每日报告生成 ===")
    
    # 创建报告工作流
    workflow_id = AutoWorkflowGenerator.create_daily_report_workflow(report_type="summary")
    print(f"创建工作流: {workflow_id}")
    
    # 创建自动化作业（每天早上9点）
    job = AutomationJob(
        job_id="daily_summary_report",
        name="每日汇总报告",
        description="每天早上9点生成汇总报告",
        workflow_id=workflow_id,
        schedule_type="cron",
        schedule_config={"cron": "0 9 * * *"}
    )
    
    scheduler = get_workflow_scheduler()
    task_id = scheduler.schedule_workflow(job)
    print(f"调度任务ID: {task_id}")


async def example_health_check():
    """示例：健康检查"""
    print("\n=== 示例3: 健康检查 ===")
    
    # 创建健康检查工作流
    workflow_id = AutoWorkflowGenerator.create_health_check_workflow([
        "数据库连接",
        "API服务",
        "缓存服务",
        "消息队列"
    ])
    print(f"创建工作流: {workflow_id}")
    
    # 创建自动化作业（每5分钟）
    job = AutomationJob(
        job_id="health_check",
        name="系统健康检查",
        description="每5分钟检查一次系统健康状态",
        workflow_id=workflow_id,
        schedule_type="interval",
        schedule_config={"interval": 300}  # 5分钟
    )
    
    scheduler = get_workflow_scheduler()
    task_id = scheduler.schedule_workflow(job)
    print(f"调度任务ID: {task_id}")


async def example_agent_action():
    """示例：Agent 动作执行"""
    print("\n=== 示例4: Agent 动作执行 ===")
    
    executor = get_agent_executor()
    
    # 执行文档生成动作
    result = await executor.execute_action(
        action="auto_document",
        params={
            "code": """def add(a: int, b: int) -> int:
    return a + b""",
            "agent_type": "local"
        }
    )
    
    print(f"执行结果: {result.content[:100]}...")


async def example_one_time_task():
    """示例：一次性任务"""
    print("\n=== 示例5: 一次性任务 ===")
    
    # 创建工作流
    workflow_id = "one_time_task"
    
    def task_action(vars):
        print("[一次性任务] 执行一次性任务")
        return {"completed": True}
    
    from . import WorkflowBuilder, register_workflow
    
    workflow = WorkflowBuilder(workflow_id, "sequential")\
        .start("开始一次性任务")\
        .action("execute", task_action, "执行任务")\
        .end("任务完成")\
        .build()
    
    register_workflow(workflow)
    
    # 创建一次性作业（5分钟后执行）
    job = AutomationJob(
        job_id="one_time_example",
        name="示例一次性任务",
        description="5分钟后执行一次",
        workflow_id=workflow_id,
        schedule_type="once",
        schedule_config={"time": datetime.now() + timedelta(minutes=5)}
    )
    
    scheduler = get_workflow_scheduler()
    task_id = scheduler.schedule_workflow(job)
    print(f"调度一次性任务ID: {task_id}")


async def run_all_examples():
    """运行所有示例"""
    await example_periodic_sync()
    await example_daily_report()
    await example_health_check()
    await example_agent_action()
    await example_one_time_task()
    
    # 启动调度器
    scheduler = get_workflow_scheduler()
    scheduler.start()
    
    # 运行一段时间后停止
    print("\n调度器已启动，按 Ctrl+C 停止...")
    try:
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        pass
    
    scheduler.stop()
    print("调度器已停止")


if __name__ == "__main__":
    asyncio.run(run_all_examples())