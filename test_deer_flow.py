"""
DeerFlow 集成功能测试

测试中间件管道和子智能体系统
"""

import time
import json
import asyncio


def test_middleware_pipeline():
    """测试中间件管道"""
    print("=== 测试中间件管道 ===")
    
    from client.src.business.deer_flow import (
        MiddlewarePipeline,
        PipelineBuilder,
        MiddlewareType,
    )
    
    # 使用构建器创建管道
    builder = PipelineBuilder()
    pipeline = (
        builder
        .add_thread_data()
        .add_guardrail()
        .add_tool_error_handling()
        .add_summarization()
        .add_todo_list()
        .add_subagent_limit(3)
        .add_memory()
        .add_clarification()
        .build()
    )
    
    print(f"管道创建成功，包含 {len(pipeline.middlewares)} 个中间件")
    
    # 显示管道信息
    info = pipeline.get_pipeline_info()
    print("\n管道中间件:")
    for item in info:
        print(f"  {item['order']}. {item['name']} ({item['type']}) - {'启用' if item['enabled'] else '禁用'}")
    
    # 测试状态处理
    initial_state = {
        "thread_id": "test_thread_1",
        "message": {"role": "user", "content": "测试消息"},
        "tool_calls": [
            {"name": "file_read", "arguments": {"path": "/test"}},
        ],
        "messages": ["message1", "message2", "message3"] * 100,  # 模拟大量消息
    }
    
    print("\n测试状态处理...")
    async def run_test():
        result = await pipeline.process(initial_state)
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_test())
    finally:
        loop.close()
    
    print(f"处理后状态键: {list(result.keys())}")
    if "thread_data" in result:
        print(f"线程数据已创建: {bool(result['thread_data'])}")
    if "memory_facts" in result:
        print(f"记忆事实数量: {len(result.get('memory_facts', []))}")
    if "todo_progress" in result:
        print(f"任务进度: {result['todo_progress']}")
    if "was_summarized" in result:
        print(f"是否被缩减: {result['was_summarized']}")
    
    # 测试中间件禁用
    print("\n测试中间件禁用...")
    pipeline.disable("MemoryMiddleware")
    print(f"MemoryMiddleware 启用状态: {pipeline.get('MemoryMiddleware').enabled}")
    pipeline.enable("MemoryMiddleware")
    print(f"MemoryMiddleware 启用状态: {pipeline.get('MemoryMiddleware').enabled}")
    
    print("\n中间件管道测试完成!")


def test_subagent_executor():
    """测试子智能体执行器"""
    print("\n=== 测试子智能体执行器 ===")
    
    from client.src.business.deer_flow import (
        SubAgentExecutor,
        SubAgentType,
    )
    
    # 创建执行器
    executor = SubAgentExecutor(max_concurrent=3)
    print(f"执行器创建成功，最大并发: {executor.max_concurrent}")
    
    # 显示注册的子智能体类型
    types = executor.registry.list_types()
    print(f"注册的子智能体类型: {[t.value for t in types]}")
    
    # 测试执行通用任务
    print("\n测试执行通用任务...")
    
    async def run_general_test():
        result = await executor.execute(
            agent_type=SubAgentType.GENERAL,
            parameters={"description": "测试任务"},
            description="通用任务测试",
        )
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        general_result = loop.run_until_complete(run_general_test())
    finally:
        loop.close()
    
    print(f"通用任务执行结果:")
    print(f"  成功: {general_result.success}")
    print(f"  结果: {general_result.result}")
    print(f"  执行时间: {general_result.execution_time:.4f}秒")
    
    # 测试执行研究任务
    print("\n测试执行研究任务...")
    
    async def run_research_test():
        result = await executor.execute(
            agent_type=SubAgentType.RESEARCH,
            parameters={
                "query": "AI Agent 最新发展",
                "sources": ["arxiv", "techcrunch", "hackernews"],
            },
            description="AI 研究任务",
        )
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        research_result = loop.run_until_complete(run_research_test())
    finally:
        loop.close()
    
    print(f"研究任务执行结果:")
    print(f"  成功: {research_result.success}")
    print(f"  发现: {len(research_result.result.get('findings', []))} 条")
    print(f"  执行时间: {research_result.execution_time:.4f}秒")
    
    # 测试编码任务
    print("\n测试执行编码任务...")
    
    async def run_coding_test():
        result = await executor.execute(
            agent_type=SubAgentType.CODING,
            parameters={
                "code": "def hello(): print('world')",
                "language": "python",
                "task": "review",
            },
            description="代码审查任务",
        )
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        coding_result = loop.run_until_complete(run_coding_test())
    finally:
        loop.close()
    
    print(f"编码任务执行结果:")
    print(f"  成功: {coding_result.success}")
    print(f"  建议: {coding_result.result.get('suggestions', [])}")
    print(f"  执行时间: {coding_result.execution_time:.4f}秒")
    
    # 测试并行执行
    print("\n测试并行执行...")
    
    tasks = [
        {
            "agent_type": SubAgentType.GENERAL,
            "parameters": {"description": f"并行任务 {i}"},
            "description": f"并行任务 {i}",
        }
        for i in range(5)
    ]
    
    async def run_parallel_test():
        results = await executor.execute_parallel(tasks, max_parallel=3)
        return results
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        parallel_results = loop.run_until_complete(run_parallel_test())
    finally:
        loop.close()
    
    print(f"并行执行结果: {len(parallel_results)} 个任务")
    success_count = sum(1 for r in parallel_results if r.success)
    print(f"  成功: {success_count}")
    print(f"  失败: {len(parallel_results) - success_count}")
    
    # 获取统计信息
    stats = executor.get_stats()
    print(f"\n执行器统计:")
    print(f"  总任务数: {stats['total_tasks']}")
    print(f"  活跃任务: {stats['active_tasks']}")
    print(f"  完成任务: {stats['completed_tasks']}")
    print(f"  失败任务: {stats['failed_tasks']}")
    
    # 关闭执行器
    executor.shutdown()
    print("\n子智能体执行器测试完成!")


def test_task_tool():
    """测试任务工具"""
    print("\n=== 测试任务工具 ===")
    
    from client.src.business.deer_flow import (
        SubAgentExecutor,
        SubAgentType,
        TaskTool,
    )
    
    # 创建执行器和工具
    executor = SubAgentExecutor(max_concurrent=2)
    task_tool = TaskTool(executor)
    
    # 获取工具 schema
    schema = task_tool.get_schema()
    print(f"任务工具 schema:")
    print(f"  名称: {schema['name']}")
    print(f"  描述: {schema['description']}")
    print(f"  参数类型: {schema['parameters']['properties']['agent_type']['enum']}")
    
    # 测试执行
    print("\n测试任务工具执行...")
    
    arguments = {
        "agent_type": "general",
        "description": "测试任务",
        "parameters": {"description": "测试参数"},
    }
    
    async def run_tool_test():
        result = await task_tool.execute(arguments)
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        tool_result = loop.run_until_complete(run_tool_test())
    finally:
        loop.close()
    
    print(f"任务工具执行结果:")
    print(f"  成功: {tool_result['success']}")
    print(f"  任务ID: {tool_result['task_id']}")
    print(f"  执行时间: {tool_result['execution_time']:.4f}秒")
    
    executor.shutdown()
    print("\n任务工具测试完成!")


if __name__ == "__main__":
    print("DeerFlow 集成功能测试开始")
    
    try:
        test_middleware_pipeline()
        test_subagent_executor()
        test_task_tool()
        print("\n✅ 所有测试通过!")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
