"""
测试执行可重复性和运行隔离机制
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试工具链编排器（执行可重复性）
print("测试工具链编排器...")

from business.tool_chain_orchestrator import (
    ToolChainOrchestrator,
    ExecutionPhase,
    PhaseStatus
)

# 创建编排器
orchestrator = ToolChainOrchestrator()

# 列出工具链
chains = orchestrator.list_chains()
print(f"✓ 加载了 {len(chains)} 个工具链")

# 检查环评报告生成流程
chain = orchestrator.get_chain("environment_report")
assert chain is not None
print("✓ 环评报告生成流程已加载")

# 检查阶段定义
phases = chain.phases
assert ExecutionPhase.PLANNING in phases
assert ExecutionPhase.DATA_COLLECTION in phases
assert ExecutionPhase.ANALYSIS in phases
assert ExecutionPhase.REPORT_GENERATION in phases
assert ExecutionPhase.REVIEW in phases
print("✓ 所有阶段都已定义")

# 检查数据收集阶段是确定性的（不允许 AI）
data_phase = phases[ExecutionPhase.DATA_COLLECTION]
assert not data_phase.ai_enabled, "数据收集阶段应该是确定性的"
print("✓ 数据收集阶段是确定性的（不允许 AI）")

# 检查规划阶段允许 AI
plan_phase = phases[ExecutionPhase.PLANNING]
assert plan_phase.ai_enabled, "规划阶段应该允许 AI"
print("✓ 规划阶段允许 AI")

# 创建实例
instance_id = orchestrator.create_instance("environment_report", {"project": "test_project"})
print(f"✓ 创建工具链实例: {instance_id}")

# 测试隔离管理器
print("\n测试任务隔离管理器...")

from business.task_isolation_manager import TaskIsolationManager

# 创建隔离管理器
isolation_manager = TaskIsolationManager()

# 为任务创建工作空间
task_id = "test_task_123"
workspace_path = isolation_manager.create_workspace(task_id)
print(f"✓ 创建工作空间: {workspace_path}")

# 验证目录结构
assert os.path.exists(workspace_path)
assert os.path.exists(os.path.join(workspace_path, "input"))
assert os.path.exists(os.path.join(workspace_path, "output"))
assert os.path.exists(os.path.join(workspace_path, "temp"))
assert os.path.exists(os.path.join(workspace_path, "logs"))
print("✓ 工作空间目录结构完整")

# 获取工作空间信息
info = isolation_manager.get_workspace_info(task_id)
assert info is not None
assert info["task_id"] == task_id
print("✓ 工作空间信息获取成功")

# 创建另一个任务的工作空间（验证隔离）
task_id_2 = "test_task_456"
workspace_path_2 = isolation_manager.create_workspace(task_id_2)
assert workspace_path != workspace_path_2
print("✓ 不同任务有独立的工作空间")

# 获取统计信息
stats = isolation_manager.get_stats()
assert "total_workspaces" in stats
assert stats["total_workspaces"] >= 2
print("✓ 统计信息获取成功")

# 清理测试工作空间
isolation_manager.destroy_workspace(task_id)
isolation_manager.destroy_workspace(task_id_2)
print("✓ 测试工作空间已清理")

print("\n🎉 所有测试通过!")
