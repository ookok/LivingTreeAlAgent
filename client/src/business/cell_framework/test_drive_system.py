"""
内驱力系统测试

测试虚拟生理与感官闭环功能：
1. 生理指标管理（能量、注意力、疲劳度、健康值）
2. 内驱力系统（好奇心、求知欲、社交欲、创造力等）
3. 资源成本评估
4. 内在动机生成
5. 自动休息机制
"""

import asyncio
import sys
import os

# 直接导入，避免循环导入问题
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接从文件导入，不经过 __init__
from drive_system import DriveSystem, DriveType, PhysiologicalState


async def test_drive_system_basic():
    """测试内驱力系统基础功能"""
    print("\n" + "="*60)
    print("[Test 1] 内驱力系统基础测试")
    print("="*60)
    
    drive_system = DriveSystem()
    print(f"✓ 创建内驱力系统: {drive_system.id}")
    
    # 检查初始状态
    status = drive_system.get_status()
    print(f"✓ 初始能量: {status['physiological']['energy']}%")
    print(f"✓ 初始注意力: {status['physiological']['attention']}%")
    print(f"✓ 初始疲劳度: {status['physiological']['fatigue']}%")
    print(f"✓ 初始健康: {status['physiological']['health']}%")
    print(f"✓ 生理状态: {status['physiological']['state']}")
    
    # 检查内驱力
    print(f"\n✓ 内驱力初始值:")
    for drive, value in status['drives'].items():
        print(f"  • {drive}: {value}%")
    
    print("\n✓ 内驱力系统基础测试完成！")


async def test_resource_consumption():
    """测试资源消耗机制"""
    print("\n" + "="*60)
    print("[Test 2] 资源消耗测试")
    print("="*60)
    
    drive_system = DriveSystem()
    initial_energy = drive_system.energy
    
    # 模拟思考消耗
    drive_system.consume_resource('thinking')
    print(f"✓ 思考消耗后能量: {drive_system.energy:.1f}%")
    
    # 模拟工具调用消耗
    drive_system.consume_resource('tool_call')
    print(f"✓ 工具调用消耗后能量: {drive_system.energy:.1f}%")
    
    # 模拟记忆访问消耗
    drive_system.consume_resource('memory_access')
    print(f"✓ 记忆访问消耗后能量: {drive_system.energy:.1f}%")
    
    # 模拟创作消耗
    drive_system.consume_resource('creation')
    print(f"✓ 创作消耗后能量: {drive_system.energy:.1f}%")
    
    # 检查疲劳度增加
    print(f"✓ 当前疲劳度: {drive_system.fatigue:.1f}%")
    
    # 检查生理状态变化
    print(f"✓ 当前生理状态: {drive_system.physiological_state.value}")
    
    print("\n✓ 资源消耗测试完成！")


async def test_resource_recovery():
    """测试资源恢复机制"""
    print("\n" + "="*60)
    print("[Test 3] 资源恢复测试")
    print("="*60)
    
    drive_system = DriveSystem()
    
    # 先消耗资源
    for _ in range(10):
        drive_system.consume_resource('thinking')
    
    print(f"✓ 消耗后能量: {drive_system.energy:.1f}%")
    print(f"✓ 消耗后疲劳度: {drive_system.fatigue:.1f}%")
    
    # 启动心跳恢复
    drive_system.start()
    
    # 等待恢复
    await asyncio.sleep(3)
    
    print(f"✓ 恢复后能量: {drive_system.energy:.1f}%")
    print(f"✓ 恢复后疲劳度: {drive_system.fatigue:.1f}%")
    
    drive_system.stop()
    
    print("\n✓ 资源恢复测试完成！")


async def test_drive_satisfaction():
    """测试内驱力满足机制"""
    print("\n" + "="*60)
    print("[Test 4] 内驱力满足测试")
    print("="*60)
    
    drive_system = DriveSystem()
    
    # 初始内驱力
    initial_curiosity = drive_system.drives[DriveType.CURIOSITY]
    print(f"✓ 初始好奇心: {initial_curiosity}%")
    
    # 满足好奇心
    drive_system.satisfy_drive(DriveType.CURIOSITY, 30.0)
    print(f"✓ 满足后好奇心: {drive_system.drives[DriveType.CURIOSITY]}%")
    
    # 消耗好奇心
    drive_system.deplete_drive(DriveType.CURIOSITY, 15.0)
    print(f"✓ 消耗后好奇心: {drive_system.drives[DriveType.CURIOSITY]}%")
    
    # 检查优势内驱力
    print(f"✓ 当前优势内驱力: {drive_system.dominant_drive.value}")
    
    # 检查需要关注的内驱力
    needs = drive_system.needs_attention
    print(f"✓ 需要关注的内驱力: {[d.value for d in needs]}")
    
    print("\n✓ 内驱力满足测试完成！")


async def test_task_cost_evaluation():
    """测试任务成本评估"""
    print("\n" + "="*60)
    print("[Test 5] 任务成本评估测试")
    print("="*60)
    
    drive_system = DriveSystem()
    
    # 评估简单任务
    simple_task = "回答问题"
    evaluation = drive_system.evaluate_task_cost(simple_task)
    print(f"✓ 简单任务 '{simple_task}':")
    print(f"  • 预估成本: {evaluation['estimated_cost']:.2f}")
    print(f"  • 负担得起: {evaluation['affordable']}")
    print(f"  • 推荐执行: {evaluation['recommended']}")
    
    # 评估复杂任务
    complex_task = "分析数据并生成详细报告"
    evaluation = drive_system.evaluate_task_cost(complex_task)
    print(f"\n✓ 复杂任务 '{complex_task}':")
    print(f"  • 预估成本: {evaluation['estimated_cost']:.2f}")
    print(f"  • 负担得起: {evaluation['affordable']}")
    print(f"  • 推荐执行: {evaluation['recommended']}")
    print(f"  • 影响因素: {evaluation['factors']}")
    
    # 大量消耗后评估
    for _ in range(20):
        drive_system.consume_resource('thinking')
    
    evaluation = drive_system.evaluate_task_cost(complex_task)
    print(f"\n✓ 资源不足时评估:")
    print(f"  • 能量剩余: {drive_system.energy:.1f}%")
    print(f"  • 负担得起: {evaluation['affordable']}")
    print(f"  • 执行后能量: {evaluation['energy_after']:.1f}%")
    
    print("\n✓ 任务成本评估测试完成！")


async def test_intrinsic_motivation():
    """测试内在动机生成"""
    print("\n" + "="*60)
    print("[Test 6] 内在动机生成测试")
    print("="*60)
    
    drive_system = DriveSystem()
    
    # 获取动机报告
    report = drive_system.get_motivation_report()
    motivation = report['intrinsic_motivation']
    
    print(f"✓ 当前优势内驱力: {motivation['dominant_drive']}")
    print(f"✓ 内驱力强度: {motivation['strength']:.1f}%")
    print(f"✓ 建议行动: {motivation['suggestion']['action']}")
    print(f"✓ 行动描述: {motivation['suggestion']['description']}")
    print(f"✓ 优先级: {motivation['suggestion']['priority']}")
    print(f"✓ 需要关注: {motivation['needs_attention']}")
    print(f"✓ 生理状态: {motivation['physiological_state']}")
    
    # 模拟好奇心驱动探索
    drive_system.drives[DriveType.CURIOSITY] = 80.0
    motivation = drive_system.generate_intrinsic_motivation()
    print(f"\n✓ 高好奇心时建议: {motivation['suggestion']['description']}")
    
    # 模拟疲劳驱动休息
    drive_system.fatigue = 70.0
    motivation = drive_system.generate_intrinsic_motivation()
    print(f"✓ 高疲劳时建议: {motivation['suggestion']['description']}")
    
    print("\n✓ 内在动机生成测试完成！")


async def test_auto_rest_mechanism():
    """测试自动休息机制"""
    print("\n" + "="*60)
    print("[Test 7] 自动休息机制测试")
    print("="*60)
    
    drive_system = DriveSystem()
    
    # 大量消耗资源
    for _ in range(30):
        drive_system.consume_resource('thinking')
    
    print(f"✓ 消耗后状态:")
    print(f"  • 能量: {drive_system.energy:.1f}%")
    print(f"  • 疲劳: {drive_system.fatigue:.1f}%")
    print(f"  • 注意力: {drive_system.attention:.1f}%")
    print(f"  • 能否继续: {drive_system.should_continue()}")
    
    # 启动系统
    drive_system.start()
    
    # 等待恢复
    await asyncio.sleep(5)
    
    print(f"\n✓ 恢复后状态:")
    print(f"  • 能量: {drive_system.energy:.1f}%")
    print(f"  • 疲劳: {drive_system.fatigue:.1f}%")
    print(f"  • 注意力: {drive_system.attention:.1f}%")
    print(f"  • 能否继续: {drive_system.should_continue()}")
    
    drive_system.stop()
    
    print("\n✓ 自动休息机制测试完成！")


async def test_heartbeat_mechanism():
    """测试心跳机制"""
    print("\n" + "="*60)
    print("[Test 8] 心跳机制测试")
    print("="*60)
    
    drive_system = DriveSystem()
    drive_system.start()
    
    # 记录初始状态
    initial_energy = drive_system.energy
    
    # 等待心跳周期
    await asyncio.sleep(7)
    
    # 检查状态变化
    status = drive_system.get_status()
    print(f"✓ 心跳后能量: {status['physiological']['energy']}%")
    print(f"✓ 心跳后疲劳: {status['physiological']['fatigue']}%")
    
    drive_system.stop()
    
    print("\n✓ 心跳机制测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("内驱力系统测试套件")
    print("="*60)
    
    await test_drive_system_basic()
    await test_resource_consumption()
    await test_resource_recovery()
    await test_drive_satisfaction()
    await test_task_cost_evaluation()
    await test_intrinsic_motivation()
    await test_auto_rest_mechanism()
    await test_heartbeat_mechanism()
    
    print("\n" + "="*60)
    print("所有内驱力系统测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())