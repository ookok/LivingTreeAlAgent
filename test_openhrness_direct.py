"""OpenHarness 直接测试"""

import sys
import os

# 添加 core/living_tree_ai 目录到路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "living_tree_ai"))

# 直接从文件路径导入
from openharness_integration.engine import OpenHarnessEngine
from openharness_integration.tools import ToolSystem
from openharness_integration.skills import SkillSystem
from openharness_integration.plugins import PluginSystem
from openharness_integration.permissions import PermissionSystem
from openharness_integration.memory import MemorySystem


async def test_openhrness_direct():
    """直接测试 OpenHarness 功能"""
    print("=== 测试 OpenHarness 核心功能 ===")
    
    # 测试引擎
    print("\n测试引擎:")
    engine = OpenHarnessEngine()
    print("引擎初始化成功")
    
    # 测试工具系统
    print("\n测试工具系统:")
    tool_system = ToolSystem()
    tools = tool_system.get_all_tools()
    print(f"可用工具: {[tool['name'] for tool in tools]}")
    
    # 测试技能系统
    print("\n测试技能系统:")
    skill_system = SkillSystem()
    skills = skill_system.get_all_skills()
    print(f"可用技能: {[skill['name'] for skill in skills]}")
    
    # 测试插件系统
    print("\n测试插件系统:")
    plugin_system = PluginSystem()
    plugins = plugin_system.get_all_plugins()
    print(f"可用插件: {[plugin['name'] for plugin in plugins]}")
    
    # 测试权限系统
    print("\n测试权限系统:")
    permission_system = PermissionSystem()
    permissions = permission_system.get_all_permissions()
    print(f"可用权限: {[perm['name'] for perm in permissions]}")
    
    # 测试内存系统
    print("\n测试内存系统:")
    memory_system = MemorySystem()
    memory_id = memory_system.add_memory(content="测试内存", tags=["test"])
    print(f"添加内存项: {memory_id}")
    memory = memory_system.get_memory(memory_id)
    if memory:
        print(f"获取内存项: {memory.content}")
    
    print("\n测试完成！")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_openhrness_direct())
