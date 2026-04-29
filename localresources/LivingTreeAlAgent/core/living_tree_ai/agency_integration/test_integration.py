"""集成功能测试 - 验证角色节点的执行效果"""

import asyncio
import sys
import os

# 添加必要的路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from role_manager import RoleManager
from workflow_mapper import WorkflowMapper
from knowledge_integration import KnowledgeIntegrator
from knowledge import KnowledgeBase


async def test_role_node_execution():
    """测试角色节点执行"""
    print("=== 角色节点执行测试 ===")
    
    # 初始化角色管理器
    role_manager = RoleManager()
    
    # 初始化工作流程映射器
    workflow_mapper = WorkflowMapper()
    
    # 初始化知识库
    kb = KnowledgeBase("test_node")
    
    # 初始化知识集成器
    integrator = KnowledgeIntegrator(kb, "test_node")
    
    # 测试创建角色节点
    print("\n=== 测试创建角色节点 ===")
    roles = role_manager.get_all_roles()
    print(f"可用角色: {roles}")
    
    role_nodes = {}
    for role in roles:
        node = role_manager.create_role_node(role)
        if node:
            role_nodes[role] = node
            print(f"创建角色节点: {role} (ID: {node.node_id})")
    
    # 测试集成角色知识
    print("\n=== 测试集成角色知识 ===")
    integrator.integrate_all_roles()
    
    # 测试工作流程映射
    print("\n=== 测试工作流程映射 ===")
    workflows = workflow_mapper.get_all_workflows()
    print(f"可用工作流程: {workflows}")
    
    # 测试全栈开发工作流程
    if "full_stack_dev" in workflows:
        print("\n=== 测试全栈开发工作流程 ===")
        input_data = {
            "requirements": "创建一个简单的待办事项应用，包含添加、删除、标记完成功能"
        }
        
        task_chain = workflow_mapper.map_to_task_chain("full_stack_dev", input_data)
        print(f"生成的任务链长度: {len(task_chain)}")
        
        # 启动全栈工程师节点
        if "Full Stack Engineer" in role_nodes:
            node = role_nodes["Full Stack Engineer"]
            await node.start()
            
            # 提交任务
            print("\n提交任务到 Full Stack Engineer 节点:")
            for i, task in enumerate(task_chain):
                task_id = node.submit_task(
                    task_type=task.task_type,
                    input_data=task.input_data,
                    priority=task.priority,
                    required_capability=task.required_capability
                )
                print(f"  任务 {i+1} 提交成功: {task_id}")
            
            # 等待任务执行
            await asyncio.sleep(5)
            
            # 显示节点状态
            status = node.get_status()
            print("\n节点状态:")
            print(f"  节点ID: {status['node_id']}")
            print(f"  状态: {status['status']}")
            print(f"  已完成任务: {status['task_completed']}")
            print(f"  运行任务: {status['running_tasks']}")
            print(f"  队列任务: {status['queue_size']}")
            
            # 停止节点
            await node.stop()
    
    # 测试UI设计工作流程
    if "ui_design" in workflows:
        print("\n=== 测试UI设计工作流程 ===")
        input_data = {
            "requirements": "为待办事项应用设计一个现代、简洁的用户界面"
        }
        
        task_chain = workflow_mapper.map_to_task_chain("ui_design", input_data)
        print(f"生成的任务链长度: {len(task_chain)}")
        
        # 启动UI设计师节点
        if "UI Designer" in role_nodes:
            node = role_nodes["UI Designer"]
            await node.start()
            
            # 提交任务
            print("\n提交任务到 UI Designer 节点:")
            for i, task in enumerate(task_chain):
                task_id = node.submit_task(
                    task_type=task.task_type,
                    input_data=task.input_data,
                    priority=task.priority,
                    required_capability=task.required_capability
                )
                print(f"  任务 {i+1} 提交成功: {task_id}")
            
            # 等待任务执行
            await asyncio.sleep(5)
            
            # 显示节点状态
            status = node.get_status()
            print("\n节点状态:")
            print(f"  节点ID: {status['node_id']}")
            print(f"  状态: {status['status']}")
            print(f"  已完成任务: {status['task_completed']}")
            print(f"  运行任务: {status['running_tasks']}")
            print(f"  队列任务: {status['queue_size']}")
            
            # 停止节点
            await node.stop()
    
    # 测试知识库统计
    print("\n=== 测试知识库统计 ===")
    stats = kb.get_stats()
    print(f"知识库总知识数: {stats.total_knowledge}")
    print(f"按类型统计: {stats.by_type}")
    print(f"按领域统计: {stats.by_domain}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_role_node_execution())
