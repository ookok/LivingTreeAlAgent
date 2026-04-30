"""
register_all_tools - 自动注册所有工具

运行此脚本将扫描 tools/ 目录下的所有工具并注册到 ToolRegistry
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from business.unified_tool_registry import ToolRegistry, tool


def register_all_tools():
    """注册所有工具到统一注册中心"""
    
    print("=" * 60)
    print("开始注册所有工具...")
    print("=" * 60)
    
    registry = ToolRegistry.get_instance()
    
    # 扫描 tools/ 目录
    tools_dir = os.path.join(os.path.dirname(__file__))
    
    registered_count = 0
    failed_tools = []
    
    for filename in os.listdir(tools_dir):
        if filename.endswith("_tool.py"):
            module_name = filename[:-3]  # 移除 .py
            
            try:
                # 动态导入模块
                module = __import__(f"client.src.business.tools.{module_name}", fromlist=[module_name])
                
                # 查找模块中的工具类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    
                    # 检查是否是 BaseTool 子类
                    if (isinstance(attr, type) and 
                        hasattr(attr, '__bases__') and
                        any(base.__name__ == 'BaseTool' for base in attr.__mro__)):
                        
                        # 跳过基类
                        if attr_name == 'BaseTool':
                            continue
                        
                        try:
                            # 实例化并注册
                            tool_instance = attr()
                            if registry.register_tool(tool_instance):
                                print(f"[OK] Registered: {attr_name}")
                                registered_count += 1
                        except Exception as e:
                            print(f"[FAIL] {attr_name} - {e}")
                            failed_tools.append((attr_name, str(e)))
                            
            except Exception as e:
                print(f"[ERROR] Module {module_name} - {e}")
                failed_tools.append((module_name, str(e)))
    
    print("=" * 60)
    print(f"Registration complete! Success: {registered_count}, Failed: {len(failed_tools)}")
    
    if failed_tools:
        print("\nFailed tools:")
        for name, error in failed_tools:
            print(f"  - {name}: {error}")
    
    # 显示统计信息
    stats = registry.stats()
    print(f"\n工具统计:")
    print(f"  - 总数: {stats['total_tools']}")
    print(f"  - 启用: {stats['enabled']}")
    print(f"  - 禁用: {stats['disabled']}")
    print(f"  - 分类: {stats['categories']}")
    
    # 列出所有工具
    print(f"\nRegistered tools:")
    for tool_def in registry.list_tools():
        status = "[ON]" if tool_def.is_enabled else "[OFF]"
        print(f"  {status} [{tool_def.category}] {tool_def.name}")
    
    return registered_count


if __name__ == "__main__":
    register_all_tools()
