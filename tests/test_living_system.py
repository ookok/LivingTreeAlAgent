"""
生命系统测试模块

测试统一生命系统的核心功能：
1. 系统初始化
2. 主动推理循环
3. 自我意识系统
4. 免疫系统
5. 代谢系统
6. 细胞协作
7. 进化引擎
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_living_system_initialization():
    """测试生命系统初始化"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    
    assert system.state.value == 'active'
    assert system.consciousness_level.value in ['conscious', 'self_aware']
    assert system.health >= 0.9
    assert system.energy >= 0.9
    
    # 检查子系统是否初始化
    assert system.life_engine is not None
    assert system.self_consciousness is not None
    assert system.immune_system is not None
    assert system.metabolic_system is not None
    assert system.evolution_engine is not None
    assert system.cell_assembler is not None
    
    print("✅ 生命系统初始化测试通过")


@pytest.mark.asyncio
async def test_living_system_start_stop():
    """测试生命系统启动和停止"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    
    # 启动系统
    await system.start()
    assert system._running is True
    
    # 给系统一点时间运行
    await asyncio.sleep(1)
    
    # 停止系统
    await system.stop()
    assert system._running is False
    assert system.state.value == 'shutdown'
    
    print("✅ 生命系统启动停止测试通过")


@pytest.mark.asyncio
async def test_living_system_set_goal():
    """测试设置目标"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    
    # 设置目标
    goal = {
        'name': '测试目标',
        'description': '这是一个测试目标',
        'priority': 'high'
    }
    await system.set_goal(goal)
    
    assert len(system.goals) == 1
    assert system.current_goal is not None
    assert system.current_goal['name'] == '测试目标'
    assert 'id' in system.current_goal
    
    print("✅ 目标设置测试通过")


@pytest.mark.asyncio
async def test_living_system_execute_task():
    """测试执行任务"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    
    # 执行任务
    task = {
        'type': 'reasoning',
        'input': {'query': '2 + 2 equals what?'},
        'priority': 'normal'
    }
    result = await system.execute_task(task)
    
    assert 'task_id' in result
    assert 'status' in result
    assert result['task_id'] is not None
    
    print("✅ 任务执行测试通过")


@pytest.mark.asyncio
async def test_cell_assembler():
    """测试细胞装配器"""
    from livingtree.core.cells.cell_assembler import CellAssembler
    
    assembler = CellAssembler()
    await assembler.initialize_cells()
    
    # 检查细胞数量
    assert len(assembler.get_all_cells()) >= 5
    
    # 检查各类型细胞
    from livingtree.core.cells.cell import CellType
    assert len(assembler.get_cells_by_type(CellType.PERCEPTION)) >= 1
    assert len(assembler.get_cells_by_type(CellType.REASONING)) >= 1
    assert len(assembler.get_cells_by_type(CellType.MEMORY)) >= 1
    assert len(assembler.get_cells_by_type(CellType.ACTION)) >= 1
    
    # 测试创建细胞
    cell = await assembler.create_cell('reasoning', 'test')
    assert cell is not None
    assert cell.id in assembler.cells
    
    # 测试获取细胞
    retrieved = assembler.get_cell(cell.id)
    assert retrieved is not None
    assert retrieved.id == cell.id
    
    print("✅ 细胞装配器测试通过")


@pytest.mark.asyncio
async def test_life_engine():
    """测试生命引擎"""
    from livingtree.core.cells.life_engine import LifeEngine
    
    engine = LifeEngine()
    
    # 运行推理循环
    result = await engine.run_inference_cycle()
    
    assert 'free_energy' in result
    assert 'prediction_error' in result
    assert 'belief_state' in result
    assert 'awareness_level' in result
    
    # 测试设置目标
    engine.set_goal({'name': 'test', 'description': 'test goal'})
    assert engine.current_goal is not None
    
    # 测试反思
    reflection = engine.reflect()
    assert 'free_energy' in reflection
    assert 'prediction_error' in reflection
    
    print("✅ 生命引擎测试通过")


@pytest.mark.asyncio
async def test_self_consciousness():
    """测试自我意识系统"""
    from livingtree.core.cells.self_consciousness import SelfConsciousness
    
    sc = SelfConsciousness()
    
    # 测试内省
    introspection = await sc.introspect()
    assert 'consciousness_level' in introspection
    assert 'mood' in introspection
    assert 'energy' in introspection
    
    # 测试设置目标
    await sc.set_goal({'name': 'self_test', 'description': 'test'})
    assert len(sc.self_model.goals) == 1
    
    # 测试自我叙事
    narrative = sc.get_self_narrative()
    assert isinstance(narrative, str)
    assert len(narrative) > 0
    
    # 测试自我价值评估
    self_worth = sc.evaluate_self_worth()
    assert 0 <= self_worth <= 1
    
    print("✅ 自我意识系统测试通过")


@pytest.mark.asyncio
async def test_immune_system():
    """测试免疫系统"""
    from livingtree.core.cells.immune_system import ImmuneSystem
    
    immune = ImmuneSystem()
    
    # 测试监控
    report = await immune.monitor()
    assert 'status' in report
    assert 'active_threats' in report
    assert 'metrics' in report
    
    # 测试检测威胁
    threat = await immune.detect_threat({
        'source': 'test',
        'input': '<script>malicious</script>'
    })
    assert threat is not None
    assert threat.level.value == 'high'
    
    # 测试自我修复
    heal_result = await immune.heal()
    assert 'message' in heal_result
    
    print("✅ 免疫系统测试通过")


@pytest.mark.asyncio
async def test_metabolic_system():
    """测试代谢系统"""
    from livingtree.core.cells.metabolic_system import MetabolicSystem
    
    metabolic = MetabolicSystem()
    
    # 测试资源管理
    report = await metabolic.manage_resources()
    assert 'state' in report
    assert 'energy_level' in report
    assert 'resources' in report
    
    # 测试资源分配
    success = await metabolic.allocate_resources('test_task', 'high')
    assert success is True
    
    # 测试资源释放
    metabolic.release_resources('test_task')
    
    # 测试能量效率
    efficiency = metabolic.get_energy_efficiency()
    assert isinstance(efficiency, float)
    
    print("✅ 代谢系统测试通过")


@pytest.mark.asyncio
async def test_evolution_engine():
    """测试进化引擎"""
    from livingtree.core.cells.autonomous_evolution import AutonomousEvolution
    
    evolution = AutonomousEvolution(evolution_interval=1.0)
    
    # 测试进化
    result = await evolution.evolve()
    
    assert 'generation' in result
    assert 'success' in result
    assert result['success'] is True
    
    # 测试获取进化统计
    stats = evolution.get_evolution_stats()
    assert 'generation' in stats
    assert 'total_evolutions' in stats
    assert 'success_rate' in stats
    
    print("✅ 进化引擎测试通过")


@pytest.mark.asyncio
async def test_cell_signaling():
    """测试细胞信号传递"""
    from livingtree.core.cells.cell_assembler import CellAssembler
    
    assembler = CellAssembler()
    
    # 创建两个细胞
    cell1 = await assembler.create_cell('reasoning', 'test1')
    cell2 = await assembler.create_cell('memory', 'test2')
    
    # 建立连接
    await assembler.connect_cells(cell1.id, cell2.id, weight=0.7)
    
    # 发送信号
    result = await assembler.send_signal(
        cell1.id,
        cell2.id,
        {'type': 'test', 'data': 'hello'}
    )
    
    # 验证信号已发送
    assert cell1.get_connection_weight(cell2.id) > 0.7  # Hebbian学习增强
    
    print("✅ 细胞信号传递测试通过")


@pytest.mark.asyncio
async def test_full_integration():
    """测试完整集成"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    await system.start()
    
    # 运行几个推理循环
    for _ in range(3):
        await asyncio.sleep(0.5)
    
    # 设置目标并执行任务
    await system.set_goal({
        'name': 'Integration Test',
        'description': 'Test full system integration',
        'priority': 'high'
    })
    
    result = await system.execute_task({
        'type': 'reasoning',
        'input': {'query': 'What is the meaning of life?'}
    })
    
    assert result['success'] is True
    
    # 获取系统状态
    status = system.get_system_status()
    assert status['state'] == 'active'
    assert status['health'] > 0.8
    
    # 获取仪表盘
    dashboard = system.get_dashboard()
    assert 'system' in dashboard
    assert 'health' in dashboard
    assert 'subsystems' in dashboard
    
    await system.stop()
    
    print("✅ 完整集成测试通过")


if __name__ == "__main__":
    # 运行所有测试
    asyncio.run(test_living_system_initialization())
    asyncio.run(test_living_system_start_stop())
    asyncio.run(test_living_system_set_goal())
    asyncio.run(test_living_system_execute_task())
    asyncio.run(test_cell_assembler())
    asyncio.run(test_life_engine())
    asyncio.run(test_self_consciousness())
    asyncio.run(test_immune_system())
    asyncio.run(test_metabolic_system())
    asyncio.run(test_evolution_engine())
    asyncio.run(test_cell_signaling())
    asyncio.run(test_full_integration())
    
    print("\n🎉 所有测试通过！")