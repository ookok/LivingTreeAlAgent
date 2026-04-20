"""最终的工作流测试脚本"""

import os
import sys
import json

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 直接导入工作流相关文件，避免触发包的 __init__.py
workflow_dir = os.path.join(current_dir, 'core', 'living_tree_ai', 'workflow')

# 添加工作流目录到路径
sys.path.insert(0, os.path.join(current_dir, 'core'))

# 直接导入工作流模块的具体文件
from living_tree_ai.workflow.models.workflow import Workflow, WorkflowStatus
from living_tree_ai.workflow.models.node import WorkflowNodeModel, NodeType, NodeStatus
from living_tree_ai.workflow.models.connection import NodeConnection
from living_tree_ai.workflow.engine.executor import WorkflowExecutor, ExecutionResult
from living_tree_ai.workflow.registry.node_registry import NodeRegistry, get_registry
from living_tree_ai.workflow.registry.builtin_nodes import register_builtin_nodes
from living_tree_ai.workflow.template_manager import WorkflowTemplate, TemplateManager


def test_workflow_creation():
    """测试工作流创建"""
    print("测试工作流创建...")
    
    # 创建工作流
    workflow = Workflow(
        workflow_id="test_workflow",
        name="测试工作流",
        description="用于测试的工作流"
    )
    
    # 添加节点
    start_node = WorkflowNodeModel(
        node_id="start",
        node_type=NodeType.START,
        name="开始",
        position={"x": 100, "y": 200}
    )
    workflow.add_node(start_node)
    
    llm_node = WorkflowNodeModel(
        node_id="llm",
        node_type=NodeType.LLM,
        name="大语言模型",
        position={"x": 300, "y": 200},
        config={
            "model": "gpt-4",
            "temperature": 0.7
        }
    )
    workflow.add_node(llm_node)
    
    end_node = WorkflowNodeModel(
        node_id="end",
        node_type=NodeType.END,
        name="结束",
        position={"x": 500, "y": 200}
    )
    workflow.add_node(end_node)
    
    # 添加连接
    connection1 = NodeConnection(
        connection_id="conn1",
        source_node_id="start",
        source_port="output",
        target_node_id="llm",
        target_port="prompt"
    )
    workflow.add_connection(connection1)
    
    connection2 = NodeConnection(
        connection_id="conn2",
        source_node_id="llm",
        source_port="response",
        target_node_id="end",
        target_port="input"
    )
    workflow.add_connection(connection2)
    
    print(f"工作流创建成功，包含 {len(workflow.nodes)} 个节点和 {len(workflow.connections)} 个连接")
    return workflow


def test_workflow_execution(workflow):
    """测试工作流执行"""
    print("测试工作流执行...")
    
    # 创建执行器
    executor = WorkflowExecutor()
    
    # 执行回调
    def execution_callback(node_id, status, result):
        print(f"节点 {node_id} 状态: {status}")
        if result:
            print(f"  结果: {result}")
    
    # 执行工作流
    import asyncio
    async def run():
        result = await executor.execute(
            workflow,
            callback=execution_callback
        )
        print(f"执行结果: {'成功' if result.success else '失败'}")
        if not result.success:
            print(f"错误: {result.error}")
    
    asyncio.run(run())


def test_template_management():
    """测试模板管理"""
    print("测试模板管理...")
    
    # 创建工作流
    workflow = Workflow(
        workflow_id="template_workflow",
        name="模板测试工作流",
        description="用于模板测试的工作流"
    )
    
    # 添加节点
    start_node = WorkflowNodeModel(
        node_id="start",
        node_type=NodeType.START,
        name="开始",
        position={"x": 100, "y": 200}
    )
    workflow.add_node(start_node)
    
    end_node = WorkflowNodeModel(
        node_id="end",
        node_type=NodeType.END,
        name="结束",
        position={"x": 300, "y": 200}
    )
    workflow.add_node(end_node)
    
    # 创建模板
    template = WorkflowTemplate(
        template_id="test_template",
        name="测试模板",
        description="用于测试的模板",
        workflow=workflow,
        tags=["test", "demo"]
    )
    
    # 保存模板
    manager = TemplateManager()
    template_path = manager.save_template(template)
    print(f"模板保存成功: {template_path}")
    
    # 列出模板
    templates = manager.list_templates()
    print(f"模板列表: {[t.name for t in templates]}")
    
    # 加载模板
    loaded_template = manager.load_template("test_template")
    if loaded_template:
        print(f"模板加载成功: {loaded_template.name}")
    
    # 导出模板
    export_path = "test_template_export.json"
    success = manager.export_template("test_template", export_path)
    if success:
        print(f"模板导出成功: {export_path}")
    
    # 导入模板
    imported_template = manager.import_template(export_path)
    if imported_template:
        print(f"模板导入成功: {imported_template.name}")
    
    # 清理
    manager.delete_template("test_template")
    if os.path.exists(export_path):
        os.remove(export_path)
    
    print("模板管理测试完成")


def test_node_registry():
    """测试节点注册表"""
    print("测试节点注册表...")
    
    # 注册内置节点
    register_builtin_nodes()
    
    # 获取注册表
    registry = get_registry()
    
    # 列出所有节点
    nodes = registry.get_all()
    print(f"注册的节点数量: {len(nodes)}")
    
    # 按类别列出节点
    categories = registry.get_categories()
    print(f"节点类别: {categories}")
    
    for category in categories:
        category_nodes = registry.get_by_category(category)
        print(f"  {category}: {[node.name for node in category_nodes]}")


def main():
    """主测试函数"""
    print("开始测试工作流功能...")
    
    try:
        # 测试工作流创建
        workflow = test_workflow_creation()
        
        # 测试工作流执行
        test_workflow_execution(workflow)
        
        # 测试模板管理
        test_template_management()
        
        # 测试节点注册表
        test_node_registry()
        
        print("所有测试完成！")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
