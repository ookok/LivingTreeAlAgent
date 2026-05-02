"""
自主系统测试套件

测试覆盖：
1. 自主进化系统
2. 动态组装系统
3. 自我再生系统
"""

import asyncio
import sys
import os

# 添加模块路径
cell_framework_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cell_framework_path not in sys.path:
    sys.path.append(cell_framework_path)

from cell_framework import (
    AutonomousEvolution, EvolutionPhase, MutationType,
    DynamicAssembly, AssemblyStrategy, AssemblyQuality,
    SelfRegeneration, RegenerationStatus, DamageLevel
)


async def test_autonomous_evolution():
    """测试自主进化系统"""
    print("\n" + "="*60)
    print("[Test 1] 自主进化系统测试")
    print("="*60)
    
    evolution = AutonomousEvolution(evolution_interval=1.0)
    print(f"✓ 创建自主进化引擎: {evolution.id}")
    print(f"  - 进化间隔: {evolution.evolution_interval}s")
    print(f"  - 变异率: {evolution.mutation_rate}")
    print(f"  - 选择压力: {evolution.selection_pressure}")
    
    # 执行一次进化
    result = await evolution.evolve()
    print(f"✓ 完成第 {result['generation']} 代进化")
    print(f"  - 成功: {result['success']}")
    print(f"  - 阶段: {result['phase']}")
    
    # 执行多次进化
    for i in range(3):
        result = await evolution.evolve()
        print(f"✓ 完成第 {result['generation']} 代进化")
    
    # 获取进化统计
    stats = evolution.get_evolution_stats()
    print(f"✓ 进化统计:")
    print(f"  - 总进化次数: {stats['total_evolutions']}")
    print(f"  - 成功率: {stats['success_rate']:.2%}")
    print(f"  - 最佳性能: {stats['best_performance']}")
    print(f"  - 平均改进: {stats['avg_improvement']:.4f}")
    
    print("\n✓ 自主进化系统测试完成！")


async def test_dynamic_assembly():
    """测试动态组装系统"""
    print("\n" + "="*60)
    print("[Test 2] 动态组装系统测试")
    print("="*60)
    
    assembler = DynamicAssembly()
    print(f"✓ 创建动态组装器: {assembler.id}")
    print(f"  - 策略: {assembler.strategy.value}")
    
    # 组装不同类型的任务
    tasks = [
        "分析用户意图并生成响应",
        "预测未来销售趋势",
        "学习新知识并记忆",
        "识别图像内容并描述"
    ]
    
    for task in tasks:
        result = await assembler.assemble_for_task(task)
        print(f"✓ 组装任务: '{task[:20]}...'")
        print(f"  - 组装ID: {result.id}")
        print(f"  - 细胞数量: {len(result.cells)}")
        print(f"  - 连接数量: {len(result.connections)}")
        print(f"  - 质量: {result.quality.value}")
        print(f"  - 效率: {result.efficiency:.2f}")
    
    # 获取组装统计
    stats = assembler.get_assembly_stats()
    print(f"\n✓ 组装统计:")
    print(f"  - 总组装数: {stats['total_assemblies']}")
    print(f"  - 平均质量: {stats['avg_quality']:.2f}")
    print(f"  - 平均效率: {stats['avg_efficiency']:.2f}")
    print(f"  - 优秀组装: {stats['excellent_count']}")
    
    print("\n✓ 动态组装系统测试完成！")


async def test_self_regeneration():
    """测试自我再生系统"""
    print("\n" + "="*60)
    print("[Test 3] 自我再生系统测试")
    print("="*60)
    
    regeneration = SelfRegeneration(scan_interval=10.0)
    print(f"✓ 创建自我再生系统: {regeneration.id}")
    print(f"  - 扫描间隔: {regeneration.scan_interval}s")
    
    # 获取损伤报告
    report = regeneration.get_damage_report()
    print(f"✓ 损伤报告:")
    print(f"  - 总细胞数: {report['total_cells']}")
    print(f"  - 受损细胞: {report['damage_summary']['damaged_count']}")
    print(f"  - 健康细胞: {report['damage_summary']['healthy_count']}")
    
    # 执行自我再生
    result = await regeneration.regenerate()
    print(f"✓ 自我再生完成")
    print(f"  - 状态: {result['status']}")
    print(f"  - 成功: {result['success']}")
    print(f"  - 消息: {result['message']}")
    
    # 获取再生统计
    stats = regeneration.get_regeneration_stats()
    print(f"✓ 再生统计:")
    print(f"  - 总再生次数: {stats['total_regenerations']}")
    print(f"  - 成功率: {stats['success_rate']:.2%}")
    print(f"  - 已再生细胞: {stats['cells_regenerated']}")
    
    print("\n✓ 自我再生系统测试完成！")


async def test_integration():
    """测试系统集成"""
    print("\n" + "="*60)
    print("[Test 4] 系统集成测试")
    print("="*60)
    
    # 创建所有系统
    evolution = AutonomousEvolution()
    assembler = DynamicAssembly()
    regeneration = SelfRegeneration()
    
    print("✓ 创建所有自主系统组件")
    
    # 执行完整流程
    print("\n📋 执行完整生命周期:")
    
    # 1. 组装细胞
    assembly = await assembler.assemble_for_task("执行复杂推理任务")
    print(f"✓ 步骤1: 动态组装完成 ({len(assembly.cells)} 个细胞)")
    
    # 2. 自主进化
    for i in range(2):
        await evolution.evolve()
    print(f"✓ 步骤2: 自主进化完成 (第 {evolution.generation} 代)")
    
    # 3. 自我再生检查
    report = regeneration.get_damage_report()
    await regeneration.regenerate()
    print(f"✓ 步骤3: 自我再生完成 (损伤比例: {report['damage_summary']['damage_ratio']:.2%})")
    
    # 汇总状态
    print("\n📊 系统状态汇总:")
    print(f"  • 进化代数: {evolution.generation}")
    print(f"  • 组装数量: {len(assembler.assembly_history)}")
    print(f"  • 再生次数: {len(regeneration.regeneration_history)}")
    
    print("\n✓ 系统集成测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("自主系统测试套件")
    print("="*60)
    
    await test_autonomous_evolution()
    await test_dynamic_assembly()
    await test_self_regeneration()
    await test_integration()
    
    print("\n" + "="*60)
    print("所有自主系统测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())