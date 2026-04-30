"""OpenHarness 集成测试"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from business.living_tree_ai.node import LivingTreeNode, NodeType


async def test_core_engine_integration():
    """测试核心引擎集成"""
    print("=== 测试核心引擎集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    await node.start()
    
    # 测试 Agent Loop
    print("\n测试 Agent Loop:")
    
    # 提交推理任务
    task_id = node.submit_task(
        task_type="inference",
        input_data={"prompt": "你好，我需要帮助"},
        priority=1
    )
    
    print(f"提交推理任务: {task_id}")
    
    # 等待任务完成
    await asyncio.sleep(3)
    
    # 检查任务状态
    print("任务执行完成")
    
    await node.stop()
    print("核心引擎集成测试完成")


async def test_tool_system_integration():
    """测试工具系统集成"""
    print("\n=== 测试工具系统集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    await node.start()
    
    # 获取可用工具
    tools = node.get_available_tools()
    print(f"可用工具: {[tool['name'] for tool in tools]}")
    
    # 测试读取文件工具
    print("\n测试读取文件工具:")
    try:
        # 先创建测试文件
        test_file = "test.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("测试文件内容")
        
        # 执行工具
        result = await node.execute_tool("read_file", file_path=test_file)
        print(f"读取文件结果: {result}")
        
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
    except Exception as e:
        print(f"工具执行失败: {e}")
    
    # 测试列出目录工具
    print("\n测试列出目录工具:")
    try:
        result = await node.execute_tool("list_directory", directory=".")
        print(f"目录内容: {result[:5]}...")  # 只显示前5个
    except Exception as e:
        print(f"工具执行失败: {e}")
    
    await node.stop()
    print("工具系统集成测试完成")


async def test_skill_system_integration():
    """测试技能系统集成"""
    print("\n=== 测试技能系统集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.SPECIALIZED, specialization="engineering")
    await node.start()
    
    # 获取可用技能
    skills = node.get_available_skills()
    print(f"可用技能: {[skill['name'] for skill in skills]}")
    
    # 测试加载技能
    print("\n测试加载技能:")
    skill = node.load_skill("code_generation")
    if skill:
        print(f"加载技能成功: {skill.name}")
        print(f"技能描述: {skill.description}")
    
    # 测试根据工具获取技能
    print("\n测试根据工具获取技能:")
    skills_by_tool = node.get_skill_by_tool("write_file")
    print(f"使用 write_file 工具的技能: {skills_by_tool}")
    
    await node.stop()
    print("技能系统集成测试完成")


async def test_plugin_system_integration():
    """测试插件系统集成"""
    print("\n=== 测试插件系统集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    await node.start()
    
    # 获取可用插件
    plugins = node.get_available_plugins()
    print(f"可用插件: {[plugin['name'] for plugin in plugins]}")
    
    # 测试执行插件
    print("\n测试执行插件:")
    try:
        result = node.execute_plugin("logger", message="测试日志插件")
        print(f"日志插件执行结果: {result}")
    except Exception as e:
        print(f"插件执行失败: {e}")
    
    try:
        result = node.execute_plugin("metrics")
        print(f"metrics 插件执行结果: {result}")
    except Exception as e:
        print(f"插件执行失败: {e}")
    
    await node.stop()
    print("插件系统集成测试完成")


async def test_permission_system_integration():
    """测试权限治理集成"""
    print("\n=== 测试权限治理集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    await node.start()
    
    # 获取所有权限
    permissions = node.get_all_permissions()
    print(f"所有权限: {[perm['name'] for perm in permissions]}")
    
    # 测试权限检查
    print("\n测试权限检查:")
    read_permission = node.check_permission("read_file")
    write_permission = node.check_permission("write_file")
    print(f"read_file 权限: {read_permission}")
    print(f"write_file 权限: {write_permission}")
    
    # 测试授予权限
    print("\n测试授予权限:")
    node.grant_permission("write_file")
    write_permission = node.check_permission("write_file")
    print(f"授予 write_file 权限后: {write_permission}")
    
    # 测试撤销权限
    print("\n测试撤销权限:")
    node.revoke_permission("write_file")
    write_permission = node.check_permission("write_file")
    print(f"撤销 write_file 权限后: {write_permission}")
    
    # 获取所有钩子
    hooks = node.get_all_hooks()
    print(f"\n所有钩子: {[hook['name'] for hook in hooks]}")
    
    await node.stop()
    print("权限治理集成测试完成")


async def test_memory_system_integration():
    """测试内存系统集成"""
    print("\n=== 测试内存系统集成 ===")
    
    # 创建节点
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    await node.start()
    
    # 添加内存项
    print("\n测试添加内存项:")
    memory_id = node.add_memory(
        content="测试内存内容",
        tags=["test", "memory"],
        metadata={"type": "test"}
    )
    print(f"添加内存项: {memory_id}")
    
    # 获取内存项
    print("\n测试获取内存项:")
    memory = node.get_memory(memory_id)
    if memory:
        print(f"获取内存项成功: {memory.content}")
    
    # 搜索内存
    print("\n测试搜索内存:")
    results = node.search_memory("测试")
    print(f"搜索结果数量: {len(results)}")
    if results:
        print(f"搜索结果: {results[0].content}")
    
    # 获取内存统计
    print("\n测试获取内存统计:")
    stats = node.get_memory_stats()
    print(f"内存统计: {stats}")
    
    await node.stop()
    print("内存系统集成测试完成")


async def test_all_integration():
    """测试所有集成功能"""
    print("======================================")
    print("OpenHarness 集成测试")
    print("======================================")
    
    # 测试核心引擎
    await test_core_engine_integration()
    
    # 测试工具系统
    await test_tool_system_integration()
    
    # 测试技能系统
    await test_skill_system_integration()
    
    # 测试插件系统
    await test_plugin_system_integration()
    
    # 测试权限治理
    await test_permission_system_integration()
    
    # 测试内存系统
    await test_memory_system_integration()
    
    print("\n======================================")
    print("所有集成测试完成")
    print("======================================")


if __name__ == "__main__":
    asyncio.run(test_all_integration())
