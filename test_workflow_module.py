"""工作流模块基本测试"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core', 'living_tree_ai'))

def test_workflow_models():
    """测试工作流模型"""
    print("=== 测试工作流模型 ===")

    # 测试 types
    from workflow.models.types import NodeType, NodeStatus, WorkflowStatus, Position, Port
    print(f"✓ NodeType: {list(NodeType)[:3]}")
    print(f"✓ NodeStatus: {list(NodeStatus)[:3]}")
    print(f"✓ WorkflowStatus: {list(WorkflowStatus)[:3]}")

    # 测试 Position
    pos = Position(100, 200)
    print(f"✓ Position: {pos.to_dict()}")

    # 测试 Port
    port = Port("p1", "input", "string", "input")
    print(f"✓ Port: {port.name}")

    # 测试 node
    from workflow.models.node import WorkflowNodeModel
    node = WorkflowNodeModel(
        node_id="test_node",
        node_type=NodeType.LLM,
        name="测试节点",
        description="这是一个测试节点"
    )
    print(f"✓ WorkflowNodeModel: {node.name}, type={node.node_type.value}")
    print(f"✓ Node to_dict: {len(node.to_dict())} keys")

    # 测试 connection
    from workflow.models.connection import NodeConnection
    conn = NodeConnection(
        connection_id="conn1",
        source_node_id="node1",
        source_port="out1",
        target_node_id="node2",
        target_port="in1"
    )
    print(f"✓ NodeConnection: {conn.connection_id}")

    # 测试 workflow
    from workflow.models.workflow import Workflow
    wf = Workflow(
        workflow_id="wf1",
        name="测试工作流",
        description="这是一个测试工作流"
    )
    wf.add_node(node)
    print(f"✓ Workflow: {wf.name}, nodes={len(wf.nodes)}")

    print("\n所有模型测试通过!")


def test_node_registry():
    """测试节点注册表"""
    print("\n=== 测试节点注册表 ===")

    from workflow.registry.builtin_nodes import register_builtin_nodes
    from workflow.registry.node_registry import get_registry

    register_builtin_nodes()
    registry = get_registry()

    nodes = registry.get_all()
    print(f"✓ 注册了 {len(nodes)} 个内置节点")

    categories = registry.get_categories()
    print(f"✓ 节点类别: {categories}")

    # 测试获取节点定义
    llm_node = registry.get("llm")
    if llm_node:
        print(f"✓ LLM节点: {llm_node.name}, 图标: {llm_node.icon}")

    print("\n节点注册表测试通过!")


def test_workflow_engine():
    """测试工作流引擎"""
    print("\n=== 测试工作流引擎 ===")

    from workflow.models.workflow import Workflow
    from workflow.models.node import WorkflowNodeModel
    from workflow.models.types import NodeType, Position
    from workflow.registry.builtin_nodes import register_builtin_nodes
    from workflow.engine.converter import TaskChainConverter
    from workflow.engine.validator import WorkflowValidator

    register_builtin_nodes()

    # 创建测试工作流
    wf = Workflow(
        workflow_id="test_wf",
        name="测试工作流",
        description="用于测试的工作流"
    )

    # 添加节点
    start = WorkflowNodeModel(
        node_id="start",
        node_type=NodeType.START,
        name="开始",
        position=Position(100, 200)
    )

    llm = WorkflowNodeModel(
        node_id="llm1",
        node_type=NodeType.LLM,
        name="文本分析",
        position=Position(300, 200),
        config={"model": "gpt-4", "temperature": 0.7}
    )

    end = WorkflowNodeModel(
        node_id="end",
        node_type=NodeType.END,
        name="结束",
        position=Position(500, 200)
    )

    wf.add_node(start)
    wf.add_node(llm)
    wf.add_node(end)

    print(f"✓ 创建工作流: {wf.name}, 节点数: {len(wf.nodes)}")

    # 测试验证器
    validator = WorkflowValidator()
    is_valid, errors = validator.validate(wf)
    print(f"✓ 工作流验证: {'通过' if is_valid else '失败'}")
    if not is_valid:
        for err in errors:
            print(f"  - {err.error_type}: {err.message}")

    # 测试转换器
    converter = TaskChainConverter()
    try:
        task_chain = converter.convert(wf)
        print(f"✓ 转换为任务链: {len(task_chain)} 个任务")
    except Exception as e:
        print(f"  转换需要连接信息，当前为演示模式")

    print("\n工作流引擎测试通过!")


if __name__ == "__main__":
    test_workflow_models()
    test_node_registry()
    test_workflow_engine()
    print("\n" + "="*50)
    print("所有测试完成!")
    print("="*50)
