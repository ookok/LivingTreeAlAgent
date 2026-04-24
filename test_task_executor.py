# -*- coding: utf-8 -*-
"""
UnifiedTaskExecutor 独立测试脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 避免 core.__init__ 循环导入
import importlib.util

def load_module_directly(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 直接加载 unified_task_executor
ute_path = os.path.join(os.path.dirname(__file__), "core", "unified_task_executor.py")
unified_task_executor = load_module_directly("unified_task_executor", ute_path)

UnifiedTaskExecutor = unified_task_executor.UnifiedTaskExecutor
ExecutionStrategy = unified_task_executor.ExecutionStrategy
TaskContext = unified_task_executor.TaskContext

def test_simple_task():
    print("\n=== Test 1: 简单任务 ===")
    executor = UnifiedTaskExecutor(ollama_url="http://www.mogoo.com.cn:8899/v1")
    result = executor.execute("你好，请用一句话介绍自己")
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output}")
    print(f"Duration: {result.duration:.2f}s")
    return result

def test_complex_task():
    print("\n=== Test 2: 复杂任务（分解） ===")
    executor = UnifiedTaskExecutor(
        ollama_url="http://www.mogoo.com.cn:8899/v1",
        default_strategy=ExecutionStrategy.PARALLEL
    )
    result = executor.execute(
        "帮我分析一下 Python 和 JavaScript 的区别",
        strategy=ExecutionStrategy.PARALLEL
    )
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output[:200]}..." if len(str(result.output)) > 200 else f"Output: {result.output}")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Metadata: {result.metadata}")
    return result

def test_stream():
    print("\n=== Test 3: 流式执行 ===")
    executor = UnifiedTaskExecutor(ollama_url="http://www.mogoo.com.cn:8899/v1")
    print("Output: ", end="", flush=True)
    for chunk in executor.execute_stream("讲一个关于人工智能的笑话"):
        print(chunk, end="", flush=True)
    print()

def test_context():
    print("\n=== Test 4: 上下文传递 ===")
    executor = UnifiedTaskExecutor(ollama_url="http://www.mogoo.com.cn:8899/v1")
    context = TaskContext(task_id="test-001", user_id="user-001")
    context.set_var("language", "Python")
    context.set_var("purpose", "数据分析")

    result = executor.execute(
        "介绍一下变量",
        context=context
    )
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output[:150]}..." if len(str(result.output)) > 150 else f"Output: {result.output}")
    return result

if __name__ == "__main__":
    test_simple_task()
    test_complex_task()
    test_stream()
    test_context()
    print("\n=== All tests completed ===")
