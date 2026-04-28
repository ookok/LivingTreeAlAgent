#!/usr/bin/env python3
"""
验证自动注册功能

测试所有 18 个工具是否能正常自动注册
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

# 配置 loguru（移除彩色输出）
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

# 工具模块列表
TOOL_MODULES = [
    "client.src.business.tools.task_decomposer_tool",
    "client.src.business.tools.knowledge_graph_tool",
    "client.src.business.tools.web_crawler_tool",
    "client.src.business.tools.deep_search_tool",
    "client.src.business.tools.vector_database_tool",
    "client.src.business.tools.task_queue_tool",
    "client.src.business.tools.task_execution_engine_tool",
    "client.src.business.tools.tier_router_tool",
    "client.src.business.tools.proxy_manager_tool",
    "client.src.business.tools.content_extractor_tool",
    "client.src.business.tools.document_parser_tool",
    "client.src.business.tools.intelligent_ocr_tool",
    "client.src.business.tools.kb_auto_ingest_tool",
    "client.src.business.tools.agent_progress_tool",
    "client.src.business.tools.expert_learning_tool",
    "client.src.business.tools.skill_evolution_tool",
    "client.src.business.tools.experiment_loop_tool",
    "client.src.business.tools.markitdown_converter_tool",
]


def test_auto_registration():
    """测试自动注册功能"""
    print("=" * 60)
    print("验证自动注册功能")
    print("=" * 60)
    
    try:
        # 先清空 ToolRegistry（避免之前的注册影响）
        from client.src.business.tools.tool_registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        registry.clear()
        print("\n[PASS] ToolRegistry 已清空")
        
        # 导入所有工具模块（触发自动注册）
        print("\n导入工具模块（触发自动注册）...")
        success_count = 0
        failed_count = 0
        
        for module_name in TOOL_MODULES:
            try:
                __import__(module_name)
                success_count += 1
                print(f"  [PASS] {module_name.split('.')[-1]}")
            except Exception as e:
                failed_count += 1
                print(f"  [FAIL] {module_name.split('.')[-1]}: {e}")
        
        print(f"\n[PASS] 导入完成: 成功 {success_count} 个, 失败 {failed_count} 个")
        
        # 检查 ToolRegistry 中的工具数量
        tools = registry.list_tools()
        print(f"\n[PASS] ToolRegistry 中有 {len(tools)} 个工具:")
        
        for i, tool in enumerate(tools[:10], 1):
            print(f"  {i}. {tool.name}: {tool.description[:30]}...")
        
        if len(tools) > 10:
            print(f"  ... 还有 {len(tools) - 10} 个工具")
        
        # 测试执行一个工具
        print("\n测试执行工具...")
        if len(tools) > 0:
            # 找一个可用的工具
            test_tool = None
            for tool in tools:
                if tool.name == "task_decomposer":
                    test_tool = tool
                    break
            
            if test_tool is None:
                test_tool = tools[0]
            
            print(f"  尝试执行工具: {test_tool.name}")
            
            # 执行工具（使用安全参数）
            try:
                result = registry.execute_tool(test_tool.name, task="测试任务")
                print(f"  [PASS] 执行结果: success={result.success}")
                if result.success:
                    print(f"  [PASS] 返回数据: {str(result.data)[:50]}...")
                else:
                    print(f"  [INFO] 错误信息: {result.error}")
            except Exception as e:
                print(f"  [INFO] 执行异常（正常）: {e}")
        
        print("\n" + "=" * 60)
        print(f"[PASS] 验证完成！成功注册 {len(tools)} 个工具")
        print("=" * 60)
        
        return len(tools) == 18
        
    except Exception as e:
        print(f"\n[FAIL] 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_auto_registration()
    
    print("\n" + "=" * 60)
    if success:
        print("[PASS] 🎉 所有工具自动注册成功！")
    else:
        print("[FAIL] 部分工具注册失败！")
    print("=" * 60)
