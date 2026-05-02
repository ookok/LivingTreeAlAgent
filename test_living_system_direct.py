"""
生命系统测试模块 - 直接导入版本

直接从文件导入，避免复杂的包导入链
"""

import asyncio
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    print("🧬 开始测试生命系统...")
    
    # 测试1: 直接导入细胞基础模块
    print("\n1. 测试细胞基础模块...")
    cell_path = os.path.join('client', 'src', 'business', 'cell_framework', 'cell.py')
    exec(open(cell_path, 'r', encoding='utf-8').read())
    
    # 创建细胞类型实例
    print(f"   ✅ 细胞类型: {[ct.value for ct in CellType]}")
    print(f"   ✅ 细胞状态: {[cs.value for cs in CellState]}")
    
    # 创建细胞实例
    cell = Cell(specialization='test')
    print(f"   ✅ 创建细胞: {cell}")
    print(f"   ✅ 细胞ID: {cell.id}")
    print(f"   ✅ 细胞状态: {cell.state.value}")
    
    # 测试2: 测试推理细胞
    print("\n2. 测试推理细胞...")
    reasoning_path = os.path.join('client', 'src', 'business', 'cell_framework', 'reasoning_cell.py')
    exec(open(reasoning_path, 'r', encoding='utf-8').read())
    
    reasoning_cell = ReasoningCell(specialization='causal')
    print(f"   ✅ 创建推理细胞: {reasoning_cell}")
    
    # 测试3: 测试生命引擎
    print("\n3. 测试生命引擎...")
    life_engine_path = os.path.join('client', 'src', 'business', 'cell_framework', 'life_engine.py')
    exec(open(life_engine_path, 'r', encoding='utf-8').read())
    
    engine = LifeEngine()
    result = await engine.run_inference_cycle()
    print(f"   ✅ 推理循环完成")
    print(f"   ✅ 自由能: {result['free_energy']:.3f}")
    print(f"   ✅ 预测误差: {result['prediction_error']:.3f}")
    print(f"   ✅ 信念状态: {result['belief_state']}")
    
    # 测试4: 测试自我意识系统
    print("\n4. 测试自我意识系统...")
    self_consciousness_path = os.path.join('client', 'src', 'business', 'cell_framework', 'self_consciousness.py')
    exec(open(self_consciousness_path, 'r', encoding='utf-8').read())
    
    sc = SelfConsciousness()
    introspection = await sc.introspect()
    print(f"   ✅ 内省完成")
    print(f"   ✅ 意识水平: {introspection['consciousness_level']}")
    print(f"   ✅ 情绪: {introspection['mood']:.2f}")
    
    # 测试5: 测试免疫系统
    print("\n5. 测试免疫系统...")
    immune_path = os.path.join('client', 'src', 'business', 'cell_framework', 'immune_system.py')
    exec(open(immune_path, 'r', encoding='utf-8').read())
    
    immune = ImmuneSystem()
    report = await immune.monitor()
    print(f"   ✅ 免疫监控完成")
    print(f"   ✅ 状态: {report['status']}")
    print(f"   ✅ 活跃威胁: {report['active_threats']}")
    
    # 测试6: 测试代谢系统
    print("\n6. 测试代谢系统...")
    metabolic_path = os.path.join('client', 'src', 'business', 'cell_framework', 'metabolic_system.py')
    exec(open(metabolic_path, 'r', encoding='utf-8').read())
    
    metabolic = MetabolicSystem()
    report = await metabolic.manage_resources()
    print(f"   ✅ 资源管理完成")
    print(f"   ✅ 状态: {report['state']}")
    print(f"   ✅ 能量级别: {report['energy_level']}")
    
    # 测试7: 测试进化引擎
    print("\n7. 测试进化引擎...")
    evolution_path = os.path.join('client', 'src', 'business', 'cell_framework', 'autonomous_evolution.py')
    exec(open(evolution_path, 'r', encoding='utf-8').read())
    
    evolution = AutonomousEvolution(evolution_interval=1.0)
    result = await evolution.evolve()
    print(f"   ✅ 进化完成")
    print(f"   ✅ 代次: {result['generation']}")
    print(f"   ✅ 成功: {result['success']}")
    
    # 测试8: 测试细胞装配器
    print("\n8. 测试细胞装配器...")
    assembler_path = os.path.join('client', 'src', 'business', 'cell_framework', 'cell_assembler.py')
    exec(open(assembler_path, 'r', encoding='utf-8').read())
    
    assembler = CellAssembler()
    await assembler.initialize_cells()
    status = assembler.get_status()
    print(f"   ✅ 装配器初始化完成")
    print(f"   ✅ 细胞总数: {status['total_cells']}")
    print(f"   ✅ 活跃细胞: {status['active_cells']}")
    
    # 测试9: 测试生命系统
    print("\n9. 测试生命系统...")
    living_system_path = os.path.join('client', 'src', 'business', 'cell_framework', 'living_system.py')
    exec(open(living_system_path, 'r', encoding='utf-8').read())
    
    system = LivingSystem()
    await system.initialize()
    status = system.get_system_status()
    print(f"   ✅ 生命系统初始化完成")
    print(f"   ✅ 状态: {status['state']}")
    print(f"   ✅ 意识水平: {status['consciousness_level']}")
    print(f"   ✅ 健康: {status['health']:.2f}")
    print(f"   ✅ 能量: {status['energy']:.2f}")
    
    # 设置目标
    await system.set_goal({
        'name': '测试目标',
        'description': '完成测试',
        'priority': 'high'
    })
    print(f"   ✅ 目标设置完成")
    
    # 执行任务
    result = await system.execute_task({
        'type': 'reasoning',
        'input': {'query': '2 + 2'}
    })
    print(f"   ✅ 任务执行完成")
    print(f"   ✅ 任务ID: {result['task_id']}")
    print(f"   ✅ 成功: {result['success']}")
    
    # 获取仪表盘
    dashboard = system.get_dashboard()
    print(f"   ✅ 仪表盘获取完成")
    print(f"   ✅ 子系统数量: {len(dashboard['subsystems'])}")
    
    await system.stop()
    
    print("\n🎉 所有测试通过！")


if __name__ == "__main__":
    asyncio.run(main())