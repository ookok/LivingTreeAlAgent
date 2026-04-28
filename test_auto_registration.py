#!/usr/bin/env python3
"""
测试自动注册功能

使用 registrar.py 自动扫描并注册所有工具
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

def test_auto_registration():
    """测试自动注册功能"""
    print("=" * 60)
    print("测试自动注册功能")
    print("=" * 60)
    
    try:
        # 导入自动注册函数
        from client.src.business.tools.registrar import auto_register_all
        
        # 扫描并注册 tools 目录下的所有工具
        print("\n扫描并注册工具...")
        count = auto_register_all("client/src/business/tools")
        
        print(f"[PASS] 自动注册完成，共注册 {count} 个工具")
        
        # 验证注册结果
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        
        tools = registry.list_tools()
        print(f"\n[PASS] ToolRegistry 中共有 {len(tools)} 个工具:")
        
        for i, tool in enumerate(tools[:10], 1):  # 只显示前 10 个
            print(f"  {i}. {tool.name}: {tool.description[:40]}...")
        
        if len(tools) > 10:
            print(f"  ... 还有 {len(tools) - 10} 个工具")
        
        # 测试执行一个工具
        print("\n测试执行工具...")
        if len(tools) > 0:
            first_tool = tools[0]
            print(f"  尝试执行工具: {first_tool.name}")
            
            # 获取工具的参数schema
            schema = first_tool.get_parameters_schema()
            print(f"  参数schema: {schema}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_auto_registration()
    
    print("\n" + "=" * 60)
    if success:
        print("[PASS] 自动注册测试通过！")
    else:
        print("[FAIL] 自动注册测试失败！")
    print("=" * 60)
