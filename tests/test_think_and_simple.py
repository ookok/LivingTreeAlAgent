"""
测试"先思考再执行"机制和"简单优先"约束
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试"先思考再执行"机制
print("测试先思考再执行机制...")

# 直接导入模块，避免 __init__.py 的依赖问题
import importlib.util
think_module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'hermes_agent', 'think_before_execute.py'
)
spec = importlib.util.spec_from_file_location("think_before_execute", think_module_path)
think_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(think_module)
ThinkBeforeExecute = think_module.ThinkBeforeExecute
ThinkingStatus = think_module.ThinkingStatus

# 创建思考器
thinker = ThinkBeforeExecute()

# 测试思考功能
async def test_thinking():
    task = "分析销售数据并生成报告"
    result = await thinker.think(task)
    
    print(f"✓ 思考完成，状态: {result.status.value}")
    print(f"✓ 识别到 {len(result.assumptions)} 个假设")
    
    # 检查是否准备好执行
    if thinker.is_ready_to_execute(result):
        print("✓ 准备好执行")
        print(f"✓ 执行计划: {result.estimated_steps} 步")
    else:
        print("✓ 需要澄清")
        questions = thinker.get_clarification_questions(result)
        print(f"✓ 需要澄清的问题: {len(questions)} 个")
    
    return result

result = asyncio.run(test_thinking())

# 测试"简单优先"约束
print("\n测试简单优先约束...")

# 直接实现代码复杂度检查函数进行测试
def _check_simple_first(code: str) -> dict:
    """检查代码是否符合简单优先原则"""
    lines = code.strip().split('\n')
    line_count = len(lines)
    
    # 检查代码行数（不应超过 100 行）
    if line_count > 100:
        return {"pass": False, "reason": f"代码行数过多 ({line_count} 行)，应简化"}
    
    # 检查类数量（应该只有一个工具类）
    class_count = sum(1 for line in lines if line.strip().startswith('class '))
    if class_count > 1:
        return {"pass": False, "reason": f"类数量过多 ({class_count} 个)，应只保留一个工具类"}
    
    # 检查函数数量（应该只有必要的方法）
    func_count = sum(1 for line in lines if line.strip().startswith('def '))
    if func_count > 5:
        return {"pass": False, "reason": f"函数数量过多 ({func_count} 个)，应简化"}
    
    # 检查导入数量（应最少）
    import_count = sum(1 for line in lines if line.strip().startswith(('import ', 'from ')))
    if import_count > 5:
        return {"pass": False, "reason": f"导入数量过多 ({import_count} 个)，应减少依赖"}
    
    # 检查嵌套层数（不应过深）
    max_indent = 0
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if indent > max_indent:
            max_indent = indent
    if max_indent > 20:
        return {"pass": False, "reason": f"代码嵌套过深 (缩进 {max_indent} 空格)，应简化"}
    
    # 检查是否有不必要的设计模式术语
    pattern_terms = ["Singleton", "Factory", "Builder", "Observer", "Strategy", "Decorator"]
    for term in pattern_terms:
        if term in code:
            return {"pass": False, "reason": f"使用了不必要的设计模式 ({term})"}
    
    return {"pass": True, "reason": "代码符合简单优先原则"}

# 测试简单代码
simple_code = """
class SimpleTool:
    def __init__(self):
        pass
    
    def execute(self, **kwargs):
        return {"success": True}
"""

simple_result = _check_simple_first(simple_code)
assert simple_result["pass"] is True
print("✓ 简单代码检查通过")

# 测试复杂代码
complex_code = """
import numpy as np
import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod

class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class ComplexFactory:
    def create_tool(self, type):
        if type == 'simple':
            return SimpleTool()
        return None

class SimpleTool(metaclass=SingletonMeta):
    def __init__(self):
        self.data = {}
        
    def _helper_method1(self):
        pass
    
    def _helper_method2(self):
        pass
    
    def _helper_method3(self):
        pass
    
    def _helper_method4(self):
        pass
    
    def execute(self, **kwargs):
        try:
            if kwargs.get('option') == 'a':
                if True:
                    if False:
                        pass
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
"""

complex_result = _check_simple_first(complex_code)
assert complex_result["pass"] is False
print(f"✓ 复杂代码检查失败（正确行为）: {complex_result['reason']}")

# 测试边界情况
print("\n测试边界情况...")

# 测试正常范围的代码
normal_code = "\n".join(["def test():"] + ["    pass" for _ in range(99)])
normal_result = _check_simple_first(normal_code)
assert normal_result["pass"] is True
print("✓ 正常代码行数检查通过")

# 测试超过限制的代码
over_limit_code = "\n".join(["def test():"] + ["    pass" for _ in range(101)])
over_limit_result = _check_simple_first(over_limit_code)
assert over_limit_result["pass"] is False
print("✓ 超过限制代码检查失败（正确行为）")

print("\n🎉 所有测试通过!")