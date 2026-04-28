"""
测试工作流编排器和工具类型区分功能
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试工作流编排器
print("测试工作流编排器...")

from business.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowNode,
    NodeType,
    ExecutionStatus
)

# 创建编排器
orchestrator = WorkflowOrchestrator()

# 创建工作流
workflow = orchestrator.create_workflow(
    name="测试工作流",
    description="测试工作流编排器功能"
)

# 添加动作节点
action_node = WorkflowNode(
    id="action1",
    type=NodeType.ACTION,
    name="执行动作",
    tool_name="test_tool",
    parameters={"param1": "value1"},
    next_node="end"
)
orchestrator.add_node(workflow.id, action_node)

# 更新开始节点的 next
workflow.nodes["start"].next_node = "action1"

# 保存工作流
orchestrator.save_workflow_to_file(workflow)
print("✓ 工作流创建和保存成功")

# 创建实例
instance_id = orchestrator.create_instance(workflow.id, {"input": "test"})
print(f"✓ 创建工作流实例: {instance_id}")

# 测试工具类型区分
print("\n测试工具类型区分...")

from business.tools.base_tool import BaseTool, ToolNodeType

class DeterministicTool(BaseTool):
    """确定性工具示例（如文件操作）"""
    
    @property
    def name(self) -> str:
        return "file_operations"
    
    @property
    def description(self) -> str:
        return "文件操作工具"
    
    @property
    def category(self) -> str:
        return "document"
    
    @property
    def node_type(self) -> str:
        return ToolNodeType.DETERMINISTIC
    
    async def execute(self, **kwargs):
        return {"success": True, "data": "file operation result"}

class AITool(BaseTool):
    """AI工具示例"""
    
    @property
    def name(self) -> str:
        return "ai_analyzer"
    
    @property
    def description(self) -> str:
        return "AI 分析工具"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    async def execute(self, **kwargs):
        return {"success": True, "data": "ai analysis result"}

# 测试确定性工具
det_tool = DeterministicTool()
assert det_tool.node_type == ToolNodeType.DETERMINISTIC
assert det_tool.get_info()["node_type"] == ToolNodeType.DETERMINISTIC
print("✓ 确定性工具类型正确")

# 测试 AI 工具（默认类型）
ai_tool = AITool()
assert ai_tool.node_type == ToolNodeType.AI
assert ai_tool.get_info()["node_type"] == ToolNodeType.AI
print("✓ AI 工具类型正确")

print("\n🎉 所有测试通过!")
