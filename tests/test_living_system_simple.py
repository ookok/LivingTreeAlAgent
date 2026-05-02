"""
生命系统测试模块 - 简化版

直接测试细胞框架模块，避免复杂的导入问题
"""

import pytest
import asyncio
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_cell_types():
    """测试细胞类型"""
    from livingtree.core.cells.cell import CellType, CellState
    
    # 检查细胞类型枚举
    assert len(list(CellType)) == 6
    assert CellType.REASONING.value == 'reasoning'
    assert CellType.MEMORY.value == 'memory'
    assert CellType.LEARNING.value == 'learning'
    assert CellType.PERCEPTION.value == 'perception'
    assert CellType.ACTION.value == 'action'
    assert CellType.PREDICTION.value == 'prediction'
    
    # 检查细胞状态枚举
    assert len(list(CellState)) == 5
    
    print("✅ 细胞类型测试通过")


@pytest.mark.asyncio
async def test_reasoning_cell():
    """测试推理细胞"""
    from livingtree.core.cells.reasoning_cell import ReasoningCell
    
    cell = ReasoningCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.REASONING
    assert cell.specialization == 'test'
    assert cell.is_alive is True
    assert cell.is_active is True
    
    # 测试处理信号
    result = await cell.receive_signal({
        'type': 'reason',
        'query': '2 + 2',
        'mode': 'deductive'
    })
    
    assert result is not None
    assert 'success' in result
    
    print("✅ 推理细胞测试通过")


@pytest.mark.asyncio
async def test_memory_cell():
    """测试记忆细胞"""
    from livingtree.core.cells.memory_cell import MemoryCell
    from livingtree.core.cells.cell import CellType
    
    cell = MemoryCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.MEMORY
    assert cell.is_alive is True
    
    # 测试存储和检索
    await cell.receive_signal({
        'type': 'store',
        'key': 'test_key',
        'value': 'test_value',
        'metadata': {'source': 'test'}
    })
    
    result = await cell.receive_signal({
        'type': 'retrieve',
        'query': 'test_key'
    })
    
    assert result is not None
    
    print("✅ 记忆细胞测试通过")


@pytest.mark.asyncio
async def test_perception_cell():
    """测试感知细胞"""
    from livingtree.core.cells.perception_cell import PerceptionCell
    from livingtree.core.cells.cell import CellType
    
    cell = PerceptionCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.PERCEPTION
    
    # 测试解析
    result = await cell.receive_signal({
        'type': 'parse',
        'input': 'Hello world',
        'input_type': 'text'
    })
    
    assert result is not None
    
    print("✅ 感知细胞测试通过")


@pytest.mark.asyncio
async def test_action_cell():
    """测试行动细胞"""
    from livingtree.core.cells.action_cell import ActionCell
    from livingtree.core.cells.cell import CellType
    
    cell = ActionCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.ACTION
    
    print("✅ 行动细胞测试通过")


@pytest.mark.asyncio
async def test_learning_cell():
    """测试学习细胞"""
    from livingtree.core.cells.learning_cell import LearningCell
    from livingtree.core.cells.cell import CellType
    
    cell = LearningCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.LEARNING
    
    print("✅ 学习细胞测试通过")


@pytest.mark.asyncio
async def test_prediction_cell():
    """测试预测细胞"""
    from livingtree.core.cells.prediction_cell import PredictionCell
    from livingtree.core.cells.cell import CellType
    
    cell = PredictionCell(specialization='test')
    
    assert cell.id is not None
    assert cell.cell_type == CellType.PREDICTION
    
    print("✅ 预测细胞测试通过")


@pytest.mark.asyncio
async def test_cell_connections():
    """测试细胞连接"""
    from livingtree.core.cells.reasoning_cell import ReasoningCell
    from livingtree.core.cells.memory_cell import MemoryCell
    
    cell1 = ReasoningCell()
    cell2 = MemoryCell()
    
    # 建立连接
    cell1.connect(cell2, initial_weight=0.5)
    
    assert len(cell1.connections) == 1
    assert cell1.get_connection_weight(cell2.id) == 0.5
    
    # 发送信号（应该增强连接）
    await cell1.send_signal(cell2, {'type': 'test', 'data': 'hello'})
    
    # 连接应该增强
    assert cell1.get_connection_weight(cell2.id) > 0.5
    
    print("✅ 细胞连接测试通过")


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
    
    # 测试反思
    reflection = engine.reflect()
    assert 'free_energy' in reflection
    
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
    
    # 测试自我叙事
    narrative = sc.get_self_narrative()
    assert isinstance(narrative, str)
    
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
    
    print("✅ 进化引擎测试通过")


@pytest.mark.asyncio
async def test_cell_assembler():
    """测试细胞装配器"""
    from livingtree.core.cells.cell_assembler import CellAssembler
    
    assembler = CellAssembler()
    await assembler.initialize_cells()
    
    # 检查细胞数量
    assert len(assembler.get_all_cells()) >= 5
    
    # 测试创建细胞
    cell = await assembler.create_cell('reasoning', 'test')
    assert cell is not None
    assert cell.id in assembler.cells
    
    print("✅ 细胞装配器测试通过")


@pytest.mark.asyncio
async def test_living_system():
    """测试生命系统"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    
    assert system.state.value == 'active'
    assert system.health >= 0.9
    
    # 检查子系统
    assert system.life_engine is not None
    assert system.self_consciousness is not None
    assert system.immune_system is not None
    assert system.metabolic_system is not None
    assert system.evolution_engine is not None
    assert system.cell_assembler is not None
    
    print("✅ 生命系统测试通过")


@pytest.mark.asyncio
async def test_living_system_full():
    """测试生命系统完整功能"""
    from livingtree.core.cells.living_system import LivingSystem
    
    system = LivingSystem()
    await system.initialize()
    await system.start()
    
    # 设置目标
    await system.set_goal({
        'name': 'Test Goal',
        'description': 'Test description',
        'priority': 'high'
    })
    
    assert len(system.goals) == 1
    
    # 执行任务
    result = await system.execute_task({
        'type': 'reasoning',
        'input': {'query': 'test query'}
    })
    
    assert 'task_id' in result
    
    # 获取状态
    status = system.get_system_status()
    assert status['state'] == 'active'
    
    # 获取仪表盘
    dashboard = system.get_dashboard()
    assert 'system' in dashboard
    
    await system.stop()
    
    print("✅ 生命系统完整测试通过")


if __name__ == "__main__":
    # 运行所有测试
    asyncio.run(test_cell_types())
    asyncio.run(test_reasoning_cell())
    asyncio.run(test_memory_cell())
    asyncio.run(test_perception_cell())
    asyncio.run(test_action_cell())
    asyncio.run(test_learning_cell())
    asyncio.run(test_prediction_cell())
    asyncio.run(test_cell_connections())
    asyncio.run(test_life_engine())
    asyncio.run(test_self_consciousness())
    asyncio.run(test_immune_system())
    asyncio.run(test_metabolic_system())
    asyncio.run(test_evolution_engine())
    asyncio.run(test_cell_assembler())
    asyncio.run(test_living_system())
    asyncio.run(test_living_system_full())
    
    print("\n🎉 所有测试通过！")