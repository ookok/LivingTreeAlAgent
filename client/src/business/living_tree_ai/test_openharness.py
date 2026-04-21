"""OpenHarness 集成测试"""

import asyncio
from node import LivingTreeNode, NodeType


async def test_openharness_integration():
    """测试 OpenHarness 集成"""
    print("=== 测试 OpenHarness 集成 ===")
    
    # 创建节点
    print("创建节点...")
    node = LivingTreeNode(node_type=NodeType.UNIVERSAL)
    
    # 启动节点
    print("启动节点...")
    await node.start()
    
    # 测试工具系统
    print("\n测试工具系统:")
    tools = node.get_available_tools()
    print(f"可用工具: {[tool['name'] for tool in tools]}")
    
    # 测试技能系统
    print("\n测试技能系统:")
    skills = node.get_available_skills()
    print(f"可用技能: {[skill['name'] for skill in skills]}")
    
    # 测试插件系统
    print("\n测试插件系统:")
    plugins = node.get_available_plugins()
    print(f"可用插件: {[plugin['name'] for plugin in plugins]}")
    
    # 测试权限系统
    print("\n测试权限系统:")
    permissions = node.get_all_permissions()
    print(f"可用权限: {[perm['name'] for perm in permissions]}")
    
    # 停止节点
    print("\n停止节点...")
    await node.stop()
    
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_openharness_integration())
