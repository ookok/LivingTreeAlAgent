"""
反思式Agent模块测试

测试核心功能
"""

import asyncio
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from business.reflective_agent import (
    ReflectiveAgentLoop,
    ReflectiveLoopConfig,
    ExecutionPlan,
    PlanStep,
    create_reflective_loop
)


async def test_basic_execution():
    """测试基础执行"""
    print("\n" + "="*60)
    print("测试1: 基础执行")
    print("="*60)

    loop = ReflectiveAgentLoop()

    # 注册简单的执行器
    async def echo_handler(step):
        print(f"  [执行器] 处理: {step.params.get('input', 'no input')}")
        return {"result": f"已处理: {step.params.get('input', 'no input')}"}

    loop.register_executor("echo", echo_handler)

    # 简单任务
    result = await loop.execute_with_reflection("测试任务")

    print(f"\n结果状态: {result.status.value}")
    print(f"步骤数: {len(result.steps)}")
    print(f"错误数: {len(result.errors)}")
    print(f"尝试次数: {result.attempt_number}")

    return result.success


async def test_multi_step_execution():
    """测试多步骤执行"""
    print("\n" + "="*60)
    print("测试2: 多步骤执行")
    print("="*60)

    loop = ReflectiveAgentLoop()

    # 注册多个执行器
    async def step1_handler(step):
        await asyncio.sleep(0.1)
        return {"data": "步骤1的结果"}

    async def step2_handler(step):
        await asyncio.sleep(0.1)
        return {"data": "步骤2的结果"}

    loop.register_executor("step1", step1_handler)
    loop.register_executor("step2", step2_handler)

    # 注册规划器
    async def custom_planner(task):
        plan = ExecutionPlan(
            plan_id="test_plan",
            task=task,
            original_task=task
        )
        plan.add_step(PlanStep(
            step_id="s1",
            name="步骤1",
            action="step1",
            params={"input": "test"}
        ))
        plan.add_step(PlanStep(
            step_id="s2",
            name="步骤2",
            action="step2",
            params={"input": "test"},
            dependencies=["s1"]
        ))
        return plan

    loop.register_planner(custom_planner)

    result = await loop.execute_with_reflection("多步骤测试任务")

    print(f"\n结果状态: {result.status.value}")
    print(f"步骤数: {len(result.steps)}")
    for step in result.steps:
        print(f"  - {step.name}: {step.status.value}")

    return result.success


async def test_reflection_loop():
    """测试反思循环"""
    print("\n" + "="*60)
    print("测试3: 反思循环")
    print("="*60)

    loop = ReflectiveAgentLoop(ReflectiveLoopConfig(verbose=True))

    async def success_handler(step):
        return {"result": "成功"}

    loop.register_executor("success", success_handler)

    result = await loop.execute_with_reflection("反思测试")

    # 获取反思洞察
    insights = loop.get_learning_insights()

    print(f"\n执行统计:")
    print(f"  总任务数: {insights['total_tasks']}")
    print(f"  成功率: {insights['success_rate']:.2%}")
    print(f"  平均尝试次数: {insights['average_attempts']:.2f}")

    return result.success


async def main():
    """主测试函数"""
    print("\n" + "#"*60)
    print("# 反思式Agent模块测试")
    print("#"*60)

    results = []

    try:
        results.append(("基础执行", await test_basic_execution()))
        results.append(("多步骤执行", await test_multi_step_execution()))
        results.append(("反思循环", await test_reflection_loop()))
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()

    # 汇总
    print("\n" + "#"*60)
    print("# 测试汇总")
    print("#"*60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "通过" if result else "失败"
        print(f"  {status} - {name}")

    print(f"\n总计: {passed}/{total} 通过")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
