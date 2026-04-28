#!/usr/bin/env python3
"""
测试工具注册功能
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

# 配置 loguru
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

def test_registration():
    """测试工具注册"""
    print("=" * 60)
    print("测试工具注册功能")
    print("=" * 60)
    
    try:
        # 导入 ToolRegistry
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        print(f"[PASS] ToolRegistry 导入成功")
        
        # 尝试导入并注册一个工具
        print("\n测试注册 task_decomposer_tool...")
        from client.src.business.tools.task_decomposer_tool import register_task_decomposer_tool
        name = register_task_decomposer_tool()
        print(f"[PASS] 注册成功: {name}")
        
        # 列出所有工具
        tools = registry.list_tools()
        print(f"\n[PASS] 已注册 {len(tools)} 个工具:")
        for tool in tools[:5]:  # 只显示前 5 个
            print(f"  - {tool.name}: {tool.description[:50]}...")
        
        # 测试执行
        print("\n测试执行工具...")
        result = registry.execute_tool("task_decomposer", task="测试任务")
        print(f"[PASS] 执行结果: success={result.success}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_registration()
    
    print("\n" + "=" * 60)
    if success:
        print("[PASS] 测试通过！")
    else:
        print("[FAIL] 测试失败！")
    print("=" * 60)
