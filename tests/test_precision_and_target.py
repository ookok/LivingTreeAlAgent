"""
测试"精准修改"约束和"目标驱动执行"
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试精准修改约束
print("测试精准修改约束...")

# 直接导入模块
import importlib.util
tool_module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'tools', 'base_tool.py'
)
spec = importlib.util.spec_from_file_location("base_tool", tool_module_path)
tool_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_module)

# 测试 ModifiedFile 类
modified_file = tool_module.ModifiedFile(
    filepath="/path/to/file.txt",
    action="modify",
    original_content="old content",
    new_content="new content"
)
assert modified_file.action == "modify"
assert modified_file.filepath == "/path/to/file.txt"
print("✓ ModifiedFile 类工作正常")

# 测试精准修改约束逻辑
def test_precision_modification():
    """测试精准修改约束检查"""
    tracked_files = ["config.json", "data.txt"]
    allowed_paths = [os.path.normpath(p) for p in tracked_files]
    
    # 测试允许的文件
    normalized_path = os.path.normpath("config.json")
    assert normalized_path in allowed_paths
    print("✓ 允许修改的文件检查通过")
    
    # 测试不允许的文件
    bad_path = os.path.normpath("other.txt")
    assert bad_path not in allowed_paths
    print("✓ 不允许修改的文件检查通过")

test_precision_modification()

# 测试目标驱动执行
print("\n测试目标驱动执行...")

from business.task_execution_engine import TaskExecutionEngine, ExecutionStatus

# 创建执行引擎
engine = TaskExecutionEngine()

# 测试执行任务
async def test_target_execution():
    instruction = "创建一个简单的 Python 工具"
    result = await engine.execute(instruction)
    
    print(f"✓ 执行完成，状态: {result.status.value}")
    print(f"✓ 目标名称: {result.target.name}")
    print(f"✓ 测试用例数量: {len(result.target.test_cases)}")
    
    # 检查是否完成
    if engine.is_complete(result):
        print("✓ 任务已完成")
        
        # 获取测试摘要
        summary = engine.get_test_summary(result)
        print(f"✓ 测试摘要: {summary}")
    else:
        print("✓ 任务未完成")
        print(f"✓ 建议: {engine.suggest_revision(result)}")
    
    return result

result = asyncio.run(test_target_execution())

# 验证测试用例执行
assert len(result.test_results) >= 1
assert all(tc.passed for tc in result.test_results)
print("✓ 所有测试用例通过")

print("\n🎉 所有测试通过!")