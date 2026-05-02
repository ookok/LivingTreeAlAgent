"""
生命系统AI测试套件

测试覆盖：
1. 生命引擎 - 主动推理和自由能原理
2. 自我意识系统 - 元认知和反思能力
3. 免疫系统 - 异常检测和自我修复
4. 代谢系统 - 资源管理和能量效率
5. 完整生命系统集成
"""

import asyncio
import sys
import os

# 添加模块路径
cell_framework_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cell_framework_path not in sys.path:
    sys.path.append(cell_framework_path)

from cell_framework import (
    LifeEngine, NeuralSymbolicIntegrator, BeliefState, InferenceMode,
    SelfConsciousness, ConsciousnessLevel, ReflectionMode,
    ImmuneSystem, ThreatLevel, ThreatType, DefenseStatus,
    MetabolicSystem, EnergyLevel, MetabolicState, ResourceType
)


async def test_life_engine():
    """测试生命引擎"""
    print("\n" + "="*60)
    print("[Test 1] 生命引擎测试")
    print("="*60)
    
    engine = LifeEngine()
    print(f"✓ 创建生命引擎: {engine.id}")
    print(f"  - 出生时间: {engine.birth_time}")
    print(f"  - 初始自由能: {engine.free_energy}")
    print(f"  - 初始信念状态: {engine.belief_state.value}")
    
    # 设置目标
    engine.set_goal({
        'name': '测试目标',
        'description': '完成测试目标'
    })
    print("✓ 设置测试目标")
    
    # 运行推理循环
    result = await engine.run_inference_cycle()
    print(f"✓ 完成推理循环")
    print(f"  - 自由能: {result['free_energy']:.4f}")
    print(f"  - 预测误差: {result['prediction_error']:.4f}")
    print(f"  - 信念状态: {result['belief_state']}")
    print(f"  - 意识水平: {result['awareness_level']:.4f}")
    
    # 反思
    reflection = engine.reflect()
    print(f"✓ 系统反思完成")
    print(f"  - 推理周期: {reflection['inference_cycles']}")
    print(f"  - 健康状态: {reflection['health']}")
    
    # 获取状态
    status = engine.get_system_status()
    print(f"✓ 获取系统状态")
    print(f"  - 存活状态: {status['is_alive']}")
    print(f"  - 当前目标: {status['current_goal']}")
    
    print("\n✓ 生命引擎测试完成！")


async def test_neural_symbolic_integrator():
    """测试神经符号整合器"""
    print("\n" + "="*60)
    print("[Test 2] 神经符号整合器测试")
    print("="*60)
    
    integrator = NeuralSymbolicIntegrator()
    print("✓ 创建神经符号整合器")
    
    # 添加符号规则
    def condition(input_data):
        return input_data.get('temperature', 0) > 30
    
    def action(input_data):
        return {'action': 'cool_down', 'target_temp': 25}
    
    integrator.add_symbolic_rule('overheating', condition, action)
    print("✓ 添加符号规则: overheating")
    
    # 添加神经模式
    integrator.add_neural_pattern('normal_operation', [0.5, 0.3, 0.2])
    integrator.add_neural_pattern('normal_operation', [0.6, 0.25, 0.15])
    print("✓ 添加神经模式: normal_operation")
    
    # 执行推理
    result = integrator.infer({'temperature': 35, 'pressure': 1.0})
    print(f"✓ 执行神经符号推理")
    print(f"  - 推理结果数量: {len(result)}")
    for r in result:
        print(f"    • {r['type']}: {r.get('rule', r.get('pattern'))}")
    
    print("\n✓ 神经符号整合器测试完成！")


async def test_self_consciousness():
    """测试自我意识系统"""
    print("\n" + "="*60)
    print("[Test 3] 自我意识系统测试")
    print("="*60)
    
    self_con = SelfConsciousness()
    print(f"✓ 创建自我意识系统: {self_con.id}")
    print(f"  - 初始意识水平: {self_con.consciousness_level.value}")
    
    # 内省
    introspection = await self_con.introspect()
    print("✓ 完成内省")
    print(f"  - 情绪状态: {introspection['mood']}")
    print(f"  - 能量水平: {introspection['energy']}")
    print(f"  - 元认知置信度: {introspection['metacognitive_confidence']}")
    
    # 设置长期目标
    await self_con.set_goal({
        'name': '学习新技能',
        'description': '掌握机器学习'
    })
    await self_con.set_goal({
        'name': '提升决策能力',
        'description': '成为更好的决策者'
    })
    print("✓ 设置长期目标")
    
    # 更新能力
    self_con.self_model.update_capability('reasoning', 0.8)
    self_con.self_model.update_capability('learning', 0.7)
    print("✓ 更新能力")
    
    # 反思决策
    decision = {
        'id': 'test_decision',
        'expectation': 0.8,
        'outcome': {'success': True, 'confidence': 0.9, 'value': 0.85},
        'alternatives': 3,
        'factors': [{'supportive': True}, {'supportive': False}, {'supportive': True}]
    }
    reflection = await self_con.reflect_on_decision(decision)
    print("✓ 完成决策反思")
    print(f"  - 决策质量: {reflection['analysis']['decision_quality']:.2f}")
    print(f"  - 经验教训: {', '.join(reflection['lessons_learned'])}")
    
    # 获取自我叙事
    narrative = self_con.get_self_narrative()
    print(f"✓ 生成自我叙事: {narrative[:50]}...")
    
    # 评估自我价值
    self_worth = self_con.evaluate_self_worth()
    print(f"✓ 自我价值评估: {self_worth:.2f}")
    
    print("\n✓ 自我意识系统测试完成！")


async def test_immune_system():
    """测试免疫系统"""
    print("\n" + "="*60)
    print("[Test 4] 免疫系统测试")
    print("="*60)
    
    immune = ImmuneSystem()
    print(f"✓ 创建免疫系统: {immune.id}")
    print(f"  - 初始状态: {immune.status.value}")
    
    # 监控系统
    monitor = await immune.monitor()
    print("✓ 系统监控")
    print(f"  - 活跃威胁: {monitor['active_threats']}")
    print(f"  - 隔离项目: {monitor['quarantined_items']}")
    
    # 模拟异常
    immune.update_monitor('performance', 0.2)  # 性能下降
    immune.update_monitor('error_rate', 0.15)  # 错误率上升
    
    # 检测威胁
    threat = await immune.detect_threat({
        'source': 'test_source',
        'request_count': 1500
    })
    print(f"✓ 检测威胁")
    print(f"  - 威胁ID: {threat.id}")
    print(f"  - 威胁类型: {threat.type.value}")
    print(f"  - 威胁级别: {threat.level.value}")
    print(f"  - 描述: {threat.description}")
    
    # 添加抗体
    def response(threat):
        return True
    
    immune.add_antibody('性能下降', response)
    print("✓ 添加抗体")
    
    # 获取免疫状态
    status = immune.get_immune_status()
    print(f"✓ 获取免疫状态")
    print(f"  - 状态: {status['status']}")
    print(f"  - 抗体数量: {status['antibodies_count']}")
    print(f"  - 已解决威胁: {status['total_threats_resolved']}")
    
    # 自我修复
    heal_result = await immune.heal()
    print(f"✓ 执行自我修复: {heal_result['message']}")
    
    print("\n✓ 免疫系统测试完成！")


async def test_metabolic_system():
    """测试代谢系统"""
    print("\n" + "="*60)
    print("[Test 5] 代谢系统测试")
    print("="*60)
    
    metabolic = MetabolicSystem()
    print(f"✓ 创建代谢系统: {metabolic.id}")
    print(f"  - 初始状态: {metabolic.state.value}")
    
    # 获取代谢报告
    report = metabolic.get_metabolic_report()
    print("✓ 获取代谢报告")
    print(f"  - 能量级别: {report['energy_level']}")
    print(f"  - 活动任务: {report['active_tasks']}")
    
    # 添加任务
    metabolic.add_task({
        'name': 'test_task',
        'priority': 'high',
        'resource_requirements': {'cpu': 10, 'memory': 50}
    })
    print("✓ 添加任务")
    
    # 管理资源
    report = await metabolic.manage_resources()
    print("✓ 管理资源")
    print(f"  - 状态: {report['state']}")
    print(f"  - 能量级别: {report['energy_level']}")
    
    # 分配资源
    success = await metabolic.allocate_resources('test_requester', 'high')
    print(f"✓ 资源分配: {'成功' if success else '失败'}")
    
    # 释放资源
    metabolic.release_resources('test_requester')
    print("✓ 释放资源")
    
    # 效率优化
    metabolic.optimize_efficiency()
    print("✓ 效率优化完成")
    
    # 能量效率
    efficiency = metabolic.get_energy_efficiency()
    print(f"✓ 能量效率: {efficiency:.2f}")
    
    print("\n✓ 代谢系统测试完成！")


async def test_life_system_integration():
    """测试生命系统集成"""
    print("\n" + "="*60)
    print("[Test 6] 生命系统集成测试")
    print("="*60)
    
    # 创建完整的生命系统
    life_engine = LifeEngine()
    self_con = SelfConsciousness()
    immune = ImmuneSystem()
    metabolic = MetabolicSystem()
    
    print("✓ 创建完整生命系统组件")
    
    # 模拟系统运行
    print("✓ 启动生命系统...")
    
    # 运行多个推理周期
    for i in range(3):
        result = await life_engine.run_inference_cycle()
        await immune.monitor()
        await metabolic.manage_resources()
        await self_con.introspect()
        
        print(f"  周期 {i+1}: 自由能={result['free_energy']:.3f}, 意识={result['awareness_level']:.3f}")
    
    # 模拟威胁检测
    threat = await immune.detect_threat({
        'source': 'external',
        'input': '<script>malicious</script>'
    })
    print(f"✓ 检测到外部威胁: {threat.level.value}")
    
    # 自我修复
    await immune.heal()
    print("✓ 执行自我修复")
    
    # 生成综合报告
    report = {
        'life_engine': life_engine.get_system_status(),
        'self_consciousness': self_con.get_self_report(),
        'immune_system': immune.get_immune_status(),
        'metabolic_system': metabolic.get_metabolic_report()
    }
    
    print("\n✓ 生命系统状态汇总:")
    print(f"  • 生命引擎健康: {report['life_engine']['health']}")
    print(f"  • 意识水平: {report['self_consciousness']['consciousness_level']}")
    print(f"  • 免疫状态: {report['immune_system']['status']}")
    print(f"  • 能量级别: {report['metabolic_system']['energy_level']}")
    
    print("\n✓ 生命系统集成测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("生命系统AI测试套件")
    print("="*60)
    
    await test_life_engine()
    await test_neural_symbolic_integrator()
    await test_self_consciousness()
    await test_immune_system()
    await test_metabolic_system()
    await test_life_system_integration()
    
    print("\n" + "="*60)
    print("所有生命系统测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())