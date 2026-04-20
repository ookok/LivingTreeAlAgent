"""工作流程映射测试"""

import asyncio
from workflow_mapper import WorkflowMapper
from role_manager import RoleManager


async def test_workflow_mapping():
    """测试工作流程映射"""
    print("=== 工作流程映射测试 ===")
    
    # 初始化工作流程映射器
    workflow_mapper = WorkflowMapper()
    
    # 测试获取所有工作流程
    workflows = workflow_mapper.get_all_workflows()
    print(f"\n可用工作流程: {workflows}")
    
    # 测试全栈开发工作流程
    print("\n=== 测试全栈开发工作流程 ===")
    input_data = {
        "requirements": "创建一个简单的待办事项应用，包含添加、删除、标记完成功能"
    }
    
    task_chain = workflow_mapper.map_to_task_chain("full_stack_dev", input_data)
    print(f"生成的任务链长度: {len(task_chain)}")
    
    for i, task in enumerate(task_chain):
        print(f"\n任务 {i+1}:")
        print(f"  ID: {task.task_id}")
        print(f"  类型: {task.task_type}")
        print(f"  优先级: {task.priority}")
        print(f"  步骤: {task.input_data['step_name']}")
        print(f"  描述: {task.input_data['step_description']}")
    
    # 测试UI设计工作流程
    print("\n=== 测试UI设计工作流程 ===")
    input_data = {
        "requirements": "为待办事项应用设计一个现代、简洁的用户界面"
    }
    
    task_chain = workflow_mapper.map_to_task_chain("ui_design", input_data)
    print(f"生成的任务链长度: {len(task_chain)}")
    
    for i, task in enumerate(task_chain):
        print(f"\n任务 {i+1}:")
        print(f"  ID: {task.task_id}")
        print(f"  类型: {task.task_type}")
        print(f"  优先级: {task.priority}")
        print(f"  步骤: {task.input_data['step_name']}")
        print(f"  描述: {task.input_data['step_description']}")
    
    # 测试角色管理器
    print("\n=== 测试角色管理器 ===")
    role_manager = RoleManager()
    
    # 获取所有角色
    roles = role_manager.get_all_roles()
    print(f"可用角色: {roles}")
    
    # 测试创建角色节点
    for role in roles:
        node = role_manager.create_role_node(role)
        if node:
            print(f"\n创建角色节点: {role}")
            print(f"  节点ID: {node.node_id}")
            print(f"  节点类型: {node.node_type.value}")
            print(f"  专业领域: {node.specialization}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_workflow_mapping())
