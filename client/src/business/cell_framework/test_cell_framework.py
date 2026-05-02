"""
细胞AI框架测试套件

测试覆盖：
1. 细胞创建和基本功能
2. 细胞通信和信号传递
3. 模型组装流水线
4. 涌现引擎
5. 进化引擎
"""

import asyncio
import sys
import os

# 先导入标准库的 platform，避免与项目中的 platform.py 冲突
import platform as std_platform
sys.modules['platform'] = std_platform

# 添加模块路径（放在标准库导入之后）
cell_framework_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cell_framework_path not in sys.path:
    sys.path.append(cell_framework_path)

from cell_framework import (
    Cell, CellType, CellState,
    ReasoningCell, MemoryCell, LearningCell,
    PerceptionCell, ActionCell,
    Signal, SignalType, SignalPriority,
    ModelAssemblyLine, CellRegistry,
    EmergenceEngine, SelfOrganization,
    EvolutionEngine, CellDivision, NaturalSelection,
    create_cell, assemble_model
)


async def test_cell_creation():
    """测试细胞创建"""
    print("\n" + "="*60)
    print("[Test 1] 细胞创建测试")
    print("="*60)
    
    # 创建各种细胞类型
    cells = [
        ReasoningCell(),
        MemoryCell(),
        LearningCell(),
        PerceptionCell(),
        ActionCell(),
    ]
    
    for cell in cells:
        print(f"✓ 创建 {cell.__class__.__name__}[{cell.id}]")
        print(f"  - 类型: {cell.cell_type.value}")
        print(f"  - 专业: {cell.specialization}")
        print(f"  - 状态: {cell.state.value}")
        print(f"  - 能量: {cell.energy_level}")
    
    print("\n✓ 所有细胞创建成功！")


async def test_cell_communication():
    """测试细胞通信"""
    print("\n" + "="*60)
    print("[Test 2] 细胞通信测试")
    print("="*60)
    
    # 创建两个细胞并建立连接
    reasoning_cell = ReasoningCell()
    action_cell = ActionCell()
    
    reasoning_cell.connect(action_cell, initial_weight=0.8)
    print(f"✓ 建立连接: {reasoning_cell.id} -> {action_cell.id} (权重: 0.8)")
    
    # 发送信号
    result = await reasoning_cell.send_signal(action_cell, {
        'type': 'generate',
        'prompt': 'Hello World',
        'format': 'text'
    })
    print(f"✓ 信号发送成功")
    
    # 测试广播
    memory_cell = MemoryCell()
    reasoning_cell.connect(memory_cell, initial_weight=0.5)
    print(f"✓ 建立连接: {reasoning_cell.id} -> {memory_cell.id} (权重: 0.5)")
    
    await reasoning_cell.broadcast_signal({'type': 'heartbeat', 'message': 'ping'})
    print(f"✓ 广播信号发送成功")
    
    print("\n✓ 细胞通信测试完成！")


async def test_signal_system():
    """测试信号系统"""
    print("\n" + "="*60)
    print("[Test 3] 信号系统测试")
    print("="*60)
    
    # 创建信号
    signal = Signal(
        type=SignalType.DATA,
        priority=SignalPriority.HIGH,
        sender_id="test_sender",
        content={'message': 'Hello from signal system'}
    )
    
    print(f"✓ 创建信号: {signal.id}")
    print(f"  - 类型: {signal.type.value}")
    print(f"  - 优先级: {signal.priority.name}")
    print(f"  - TTL: {signal.ttl}")
    
    # 转换为字典
    signal_dict = signal.to_dict()
    print(f"✓ 信号序列化成功 ({len(signal_dict)} 字段)")
    
    # 从字典恢复
    restored = Signal.from_dict(signal_dict)
    print(f"✓ 信号反序列化成功")
    
    print("\n✓ 信号系统测试完成！")


async def test_model_assembly():
    """测试模型组装流水线"""
    print("\n" + "="*60)
    print("[Test 4] 模型组装测试")
    print("="*60)
    
    # 创建组装器
    assembler = ModelAssemblyLine()
    print("✓ 创建模型组装器")
    
    # 组装模型
    model = assembler.assemble("分析用户意图并生成响应")
    print(f"✓ 模型组装完成: {model.model_id}")
    print(f"  - 细胞数量: {len(model.cells)}")
    print(f"  - 细胞类型: {[c.cell_type.value for c in model.cells]}")
    
    # 获取模型统计
    stats = model.get_stats()
    print(f"✓ 模型统计: {stats}")
    
    # 执行模型
    result = await model.execute("分析这个请求")
    print(f"✓ 模型执行成功")
    print(f"  - 结果数量: {len(result['results'])}")
    
    print("\n✓ 模型组装测试完成！")


async def test_emergence_engine():
    """测试涌现引擎"""
    print("\n" + "="*60)
    print("[Test 5] 涌现引擎测试")
    print("="*60)
    
    # 创建涌现引擎
    engine = EmergenceEngine()
    print("✓ 创建涌现引擎")
    
    # 创建一些细胞
    cells = [
        ReasoningCell(),
        MemoryCell(),
        LearningCell(),
        PerceptionCell(),
        ActionCell(),
    ]
    
    # 注册细胞
    engine.register_cells(cells)
    print(f"✓ 注册 {len(cells)} 个细胞")
    
    # 运行涌现过程
    await engine.run(iterations=5)
    print("✓ 涌现过程运行完成")
    
    # 获取系统状态
    state = engine.get_system_state()
    print(f"✓ 系统状态:")
    print(f"  - 细胞总数: {state['total_cells']}")
    print(f"  - 活跃细胞: {state['active_cells']}")
    print(f"  - 平均能量: {state['avg_energy']}")
    print(f"  - 涌现模式: {state['emergent_patterns']}")
    
    print("\n✓ 涌现引擎测试完成！")


async def test_evolution_engine():
    """测试进化引擎"""
    print("\n" + "="*60)
    print("[Test 6] 进化引擎测试")
    print("="*60)
    
    # 创建进化引擎
    engine = EvolutionEngine()
    print("✓ 创建进化引擎")
    
    # 创建一些细胞并标记为成功
    cells = []
    for _ in range(5):
        cell = ReasoningCell()
        cell.total_processed = 20
        cell.success_rate = 0.9
        cells.append(cell)
    
    # 注册细胞
    for cell in cells:
        engine.energy_monitor.register_cell(cell)
    print(f"✓ 注册 {len(cells)} 个细胞")
    
    # 测试细胞分裂
    division = CellDivision()
    for cell in cells:
        if division.can_divide(cell):
            child = division.divide(cell)
            if child:
                engine.energy_monitor.register_cell(child)
                print(f"✓ 细胞 {cell.id} 分裂产生 {child.id}")
    
    # 运行一代进化
    await engine.run_generation()
    print(f"✓ 完成第 {engine.generation} 代进化")
    
    # 获取进化统计
    stats = engine.get_evolution_stats()
    print(f"✓ 进化统计:")
    print(f"  - 代数: {stats['generation']}")
    print(f"  - 种群大小: {stats['population_size']}")
    print(f"  - 平均成功率: {stats['avg_success_rate']}")
    
    print("\n✓ 进化引擎测试完成！")


async def test_factory_functions():
    """测试工厂函数"""
    print("\n" + "="*60)
    print("[Test 7] 工厂函数测试")
    print("="*60)
    
    # 使用工厂函数创建细胞
    cells = []
    for cell_type in ['reasoning', 'memory', 'learning', 'perception', 'action']:
        cell = create_cell(cell_type)
        cells.append(cell)
        print(f"✓ 创建 {cell_type} 细胞: {cell.id}")
    
    # 使用组装函数
    model = assemble_model("创建一个代码生成器")
    print(f"✓ 组装模型: {model.model_id}")
    
    print("\n✓ 工厂函数测试完成！")


async def test_cell_registry():
    """测试细胞注册表"""
    print("\n" + "="*60)
    print("[Test 8] 细胞注册表测试")
    print("="*60)
    
    # 获取注册表单例
    registry = CellRegistry.get_instance()
    print("✓ 获取细胞注册表")
    
    # 创建并注册细胞
    cells = [ReasoningCell(), MemoryCell(), LearningCell()]
    for cell in cells:
        registry.register_cell(cell)
        print(f"✓ 注册细胞: {cell.id}")
    
    # 获取细胞
    retrieved = registry.get_cell(cells[0].id)
    print(f"✓ 获取细胞: {retrieved.id == cells[0].id}")
    
    # 获取按类型
    reasoning_cells = registry.get_cells_by_type(CellType.REASONING)
    print(f"✓ 获取推理细胞: {len(reasoning_cells)} 个")
    
    # 获取统计
    stats = registry.get_cell_stats()
    print(f"✓ 细胞统计: {stats}")
    
    print("\n✓ 细胞注册表测试完成！")


async def test_cell_lifecycle():
    """测试细胞生命周期"""
    print("\n" + "="*60)
    print("[Test 9] 细胞生命周期测试")
    print("="*60)
    
    # 创建细胞
    cell = ReasoningCell()
    print(f"✓ 创建细胞: {cell.id}, 状态: {cell.state.value}")
    
    # 激活/休眠测试
    cell.deactivate()
    print(f"✓ 休眠细胞: {cell.state.value}")
    
    cell.activate()
    print(f"✓ 激活细胞: {cell.state.value}")
    
    # 能量管理
    initial_energy = cell.energy_level
    cell.consume_energy(0.3)
    print(f"✓ 能量消耗: {initial_energy} -> {cell.energy_level}")
    
    cell.recharge(0.2)
    print(f"✓ 能量补充: {cell.energy_level}")
    
    # 记录成功/错误
    cell.record_success(0.1)
    print(f"✓ 记录成功: 成功率={cell.success_rate}")
    
    cell.record_error()
    print(f"✓ 记录错误: 成功率={cell.success_rate}")
    
    # 获取统计
    stats = cell.get_stats()
    print(f"✓ 细胞统计: {stats}")
    
    print("\n✓ 细胞生命周期测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("细胞AI框架测试套件")
    print("="*60)
    
    await test_cell_creation()
    await test_cell_communication()
    await test_signal_system()
    await test_model_assembly()
    await test_emergence_engine()
    await test_evolution_engine()
    await test_factory_functions()
    await test_cell_registry()
    await test_cell_lifecycle()
    
    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())