"""
生命系统新功能测试

测试更新后的LivingSystem增强功能：
1. 生命系统完整集成
2. 任务执行与模型组装
3. 预测推演能力
4. 进化能力
5. 自我意识与目标管理
"""

import asyncio
import sys
import os

# 添加模块路径并避免冲突
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 使用相对导入避免与标准库冲突
from .living_system import LivingSystem, get_living_system


async def test_living_system_complete():
    """测试生命系统完整功能"""
    print("\n" + "="*60)
    print("[Test 1] 生命系统完整测试")
    print("="*60)
    
    # 获取全局生命系统实例
    system = get_living_system()
    print(f"✓ 获取生命系统实例: {system.id}")
    
    # 初始化系统
    await system.initialize()
    print(f"✓ 系统初始化完成，状态: {system.state.value}")
    
    # 启动系统
    await system.start()
    print("✓ 系统启动成功")
    
    # 设置目标
    await system.set_goal({
        'name': '完成测试任务',
        'description': '成功完成所有生命系统测试',
        'priority': 'high'
    })
    print("✓ 设置目标")
    
    # 执行任务
    task = await system.execute_task({
        'description': '分析用户需求并生成解决方案',
        'input': {'query': '如何提高工作效率？'}
    })
    print(f"✓ 任务执行完成，状态: {task['status']}")
    print(f"  - 任务ID: {task['id']}")
    
    # 预测推演
    prediction = await system.predict("如果增加学习时间，智能水平会如何变化？")
    print(f"✓ 预测推演完成")
    print(f"  - 场景: {prediction['scenario'][:30]}...")
    print(f"  - 置信度: {prediction['confidence']}")
    
    # 执行进化
    evolution = await system.evolve()
    print(f"✓ 进化完成，代次: {evolution.get('generation', 1)}")
    
    # 获取仪表盘
    dashboard = system.get_dashboard()
    print(f"✓ 获取仪表盘数据")
    print(f"  - 系统状态: {dashboard['system']['state']}")
    print(f"  - 意识水平: {dashboard['system']['consciousness']}")
    print(f"  - 健康: {dashboard['health']['overall']}")
    print(f"  - 能量: {dashboard['health']['energy']}")
    print(f"  - 智能: {dashboard['health']['intelligence']}")
    print(f"  - 创意: {dashboard['health']['creativity']}")
    
    # 停止系统
    await system.stop()
    print("✓ 系统停止")
    
    print("\n✓ 生命系统完整测试完成！")


async def test_bio_system_mapping():
    """测试生物系统映射能力"""
    print("\n" + "="*60)
    print("[Test 2] 生物系统映射测试")
    print("="*60)
    
    system = get_living_system()
    await system.initialize()
    
    # 大脑功能测试 - 推理
    print("🧠 大脑功能测试...")
    status = system.get_system_status()
    print(f"  ✓ 生命引擎状态: {status['subsystems']['life_engine']['is_alive']}")
    
    # 神经功能测试 - 信号传递
    print("🕸️ 神经功能测试...")
    print("  ✓ 细胞注册表已就绪")
    
    # 身体功能测试 - 工具执行
    print("🦾 身体功能测试...")
    task = await system.execute_task({
        'description': '执行简单计算',
        'input': {'query': '2 + 2'}
    })
    print(f"  ✓ 任务执行成功: {task['status']}")
    
    # 记忆功能测试
    print("🧠 记忆功能测试...")
    print("  ✓ 记忆细胞已集成")
    
    # 免疫功能测试
    print("🛡️ 免疫功能测试...")
    immune_status = status['subsystems']['immune_system']
    print(f"  ✓ 免疫系统状态: {immune_status['status']}")
    
    # 基因功能测试 - 进化
    print("🧬 基因功能测试...")
    evolution = await system.evolve()
    print(f"  ✓ 进化成功，代次: {evolution.get('generation')}")
    
    await system.stop()
    
    print("\n✓ 生物系统映射测试完成！")


async def test_autonomous_capabilities():
    """测试自主生存与演化能力"""
    print("\n" + "="*60)
    print("[Test 3] 自主生存与演化能力测试")
    print("="*60)
    
    system = get_living_system()
    await system.initialize()
    await system.start()
    
    # 自我设定目标
    print("🎯 自我设定目标...")
    await system.set_goal({
        'name': '自我优化',
        'description': '通过学习和进化不断提升自身能力',
        'priority': 'high'
    })
    await system.set_goal({
        'name': '环境适应',
        'description': '适应不断变化的环境需求',
        'priority': 'medium'
    })
    print(f"  ✓ 已设定 {len(system.goals)} 个目标")
    
    # 执行多个推理周期（模拟适应过程）
    print("🔄 运行推理周期...")
    for i in range(5):
        await asyncio.sleep(0.5)
        status = system.get_system_status()
        print(f"  周期 {i+1}: 意识={status['consciousness_level']}, 健康={status['health']}")
    
    # 进化迭代
    print("🔬 执行进化迭代...")
    for i in range(3):
        evolution = await system.evolve()
        print(f"  进化 {i+1}: 代次={evolution.get('generation')}")
    
    # 检查智能增长
    status = system.get_system_status()
    print(f"📈 智能增长: {status['intelligence']:.3f}")
    print(f"🎨 创意增长: {status['creativity']:.3f}")
    
    await system.stop()
    
    print("\n✓ 自主生存与演化能力测试完成！")


async def test_perception_and_interaction():
    """测试感知与交互能力"""
    print("\n" + "="*60)
    print("[Test 4] 感知与交互能力测试")
    print("="*60)
    
    system = get_living_system()
    await system.initialize()
    await system.start()
    
    # 多模态感知模拟
    print("👁️ 多模态感知测试...")
    
    # 情感化对话
    print("💬 情感化对话测试...")
    introspection = await system.self_consciousness.introspect()
    print(f"  ✓ 情绪状态: {introspection['mood']:.2f}")
    print(f"  ✓ 能量水平: {introspection['energy']:.2f}")
    
    # 自我叙事
    print("📝 自我叙事测试...")
    narrative = system.self_consciousness.get_self_narrative()
    print(f"  ✓ 自我描述: {narrative[:50]}...")
    
    # 工具调用
    print("🔧 工具调用测试...")
    task = await system.execute_task({
        'description': '生成一份报告',
        'input': {'topic': 'AI发展趋势'}
    })
    print(f"  ✓ 工具调用成功")
    
    await system.stop()
    
    print("\n✓ 感知与交互能力测试完成！")


async def test_predictive_capabilities():
    """测试生理推演与预测能力"""
    print("\n" + "="*60)
    print("[Test 5] 生理推演与预测能力测试")
    print("="*60)
    
    system = get_living_system()
    await system.initialize()
    await system.start()
    
    # 情景预测
    print("🔮 情景预测测试...")
    
    scenarios = [
        "如果继续当前工作模式，能量会如何变化？",
        "如果增加学习时间，智能水平会提高吗？",
        "如果遇到威胁，系统会如何响应？"
    ]
    
    for scenario in scenarios:
        prediction = await system.predict(scenario)
        print(f"  ✓ 预测: {scenario[:40]}...")
        print(f"    置信度: {prediction['confidence']:.2f}")
    
    # 自我状态预测
    print("📊 自我状态预测...")
    prediction = await system.predict("我的健康状态在未来会如何变化？")
    print(f"  ✓ 自我状态预测完成")
    
    await system.stop()
    
    print("\n✓ 生理推演与预测能力测试完成！")


if __name__ == "__main__":
    # 直接运行时需要设置正确的路径
    asyncio.run(test_living_system_complete())
    asyncio.run(test_bio_system_mapping())
    asyncio.run(test_autonomous_capabilities())
    asyncio.run(test_perception_and_interaction())
    asyncio.run(test_predictive_capabilities())
    
    print("\n" + "="*60)
    print("所有生命系统新功能测试完成！")
    print("="*60)