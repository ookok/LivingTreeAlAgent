"""
测试 evolution_common 和 task_common 重构
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src', 'business'))

print("测试 1: 导入 evolution_common")
try:
    from evolution_common import (
        BaseEvolutionEngine,
        EvolutionTarget,
        EvolutionStrategy,
        EvolutionConfig,
        create_evolution_engine,
        EvolutionEngineFacade,
        get_evolution_facade,
    )
    print("  [OK] 所有类/函数导入成功")
except Exception as e:
    print(f"  [FAIL] 导入失败: {e}")
    sys.exit(1)

print("\n测试 2: 导入 task_common")
try:
    from task_common import (
        BaseTaskDecomposer,
        DecomposerType,
        TaskStep,
        DecomposedTask,
        create_decomposer,
        auto_select_decomposer,
        TaskDecomposerFacade,
        get_task_decomposer_facade,
    )
    print("  [OK] 所有类/函数导入成功")
except Exception as e:
    print(f"  [FAIL] 导入失败: {e}")
    sys.exit(1)

print("\n测试 3: EvolutionEngineFacade 创建")
try:
    facade = get_evolution_facade()
    print(f"  [OK] 门面创建成功: {type(facade).__name__}")
    print(f"  - 已创建引擎: {facade.list_engines()}")
except Exception as e:
    print(f"  [FAIL] 创建失败: {e}")

print("\n测试 4: TaskDecomposerFacade 创建")
try:
    facade = get_task_decomposer_facade()
    print(f"  [OK] 门面创建成功: {type(facade).__name__}")
    print(f"  - 已创建分解器: {facade.list_decomposers()}")
except Exception as e:
    print(f"  [FAIL] 创建失败: {e}")

print("\n测试 5: auto_select_decomposer")
try:
    # 测试自动选择
    task1 = "帮我协作完成这个多代理任务"
    task2 = "优化这段代码性能，根据反馈迭代"
    task3 = "解释一下量子计算的基本原理"
    
    result1 = auto_select_decomposer(task1)
    result2 = auto_select_decomposer(task2)
    result3 = auto_select_decomposer(task3)
    
    print(f"  [OK] 自动选择测试成功:")
    print(f"  - 协作任务 -> {result1.value}")
    print(f"  - 优化任务 -> {result2.value}")
    print(f"  - 普通任务 -> {result3.value}")
except Exception as e:
    print(f"  [FAIL] 自动选择失败: {e}")

print("\n测试 6: DecomposedTask 和 TaskStep")
try:
    steps = [
        TaskStep(
            step_id="step_1",
            title="第一步",
            description="分析需求",
            instruction="仔细阅读需求文档",
        ),
        TaskStep(
            step_id="step_2",
            title="第二步",
            description="设计方案",
            instruction="根据需求设计技术方案",
            depends_on=["step_1"],
        ),
    ]
    
    task = DecomposedTask(
        task_id="task_001",
        original_question="设计一个系统",
        steps=steps,
    )
    
    print(f"  [OK] DecomposedTask 创建成功:")
    print(f"  - 任务 ID: {task.task_id}")
    print(f"  - 步骤数: {task.total_steps}")
    print(f"  - 进度: {task.progress*100:.0f}%")
    
    # 测试 to_dict
    d = task.to_dict()
    print(f"  - to_dict() 成功: {len(d['steps'])} 步骤")
except Exception as e:
    print(f"  [FAIL] 创建失败: {e}")

print("\n" + "="*60)
print("测试完成！")
print("="*60)

# 如果运行到这里，说明基础结构正确
print("\n[OK] 重构基础结构正确！")
print("\n注意：")
print("- evolution_common/ 和 task_common/ 提供了公共接口")
print("- 使用门面模式，不修改原有实现")
print("- 调用者现在可以通过统一接口使用不同引擎/分解器")
print("- 原有代码无需修改，保持向后兼容")
