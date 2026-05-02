"""
LivingTree AI - 主入口模块

实现完整的生命系统启动、运行和管理功能。

核心功能：
1. 系统初始化和配置加载
2. 生命引擎启动和管理
3. 细胞注册和管理
4. 信号路由和通信
5. 系统监控和状态报告
6. 命令行接口支持
"""

import asyncio
import sys
import os
import argparse
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cell_framework import (
    LifeEngine, SelfConsciousness, ImmuneSystem, MetabolicSystem,
    CellRegistry, ModelAssemblyLine, EmergenceEngine, EvolutionEngine,
    ReasoningCell, MemoryCell, LearningCell, PerceptionCell, ActionCell, PredictionCell,
    ConsciousnessLevel, DefenseStatus, MetabolicState,
    AutonomousEvolution, DynamicAssembly, SelfRegeneration
)


class LivingTree:
    """
    LivingTree AI 主类
    
    负责管理整个生命系统的运行和进化。
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.is_running = False
        self.start_time = None
        self.shutdown_event = asyncio.Event()
        
        # 核心组件
        self.life_engine: Optional[LifeEngine] = None
        self.self_consciousness: Optional[SelfConsciousness] = None
        self.immune_system: Optional[ImmuneSystem] = None
        self.metabolic_system: Optional[MetabolicSystem] = None
        self.emergence_engine: Optional[EmergenceEngine] = None
        self.evolution_engine: Optional[EvolutionEngine] = None
        
        # 自主进化组件
        self.autonomous_evolution: Optional[AutonomousEvolution] = None
        self.dynamic_assembly: Optional[DynamicAssembly] = None
        self.self_regeneration: Optional[SelfRegeneration] = None
        
        # 细胞注册表
        self.cell_registry = CellRegistry.get_instance()
        
        # 任务队列
        self.task_queue: asyncio.Queue = asyncio.Queue()
        
        # 监控数据
        self.metrics: Dict[str, List[Dict]] = {
            'inference_cycles': [],
            'energy_level': [],
            'health_status': [],
            'consciousness_level': [],
            'evolution_generations': [],
            'regeneration_events': []
        }
    
    async def initialize(self):
        """初始化生命系统"""
        print("🌲 正在初始化 LivingTree AI...")
        
        # 创建核心组件
        self.life_engine = LifeEngine()
        self.self_consciousness = SelfConsciousness()
        self.immune_system = ImmuneSystem()
        self.metabolic_system = MetabolicSystem()
        self.emergence_engine = EmergenceEngine()
        self.evolution_engine = EvolutionEngine()
        
        # 创建自主进化组件
        self.autonomous_evolution = AutonomousEvolution()
        self.dynamic_assembly = DynamicAssembly()
        self.self_regeneration = SelfRegeneration()
        
        # 注册基础细胞
        await self._register_base_cells()
        
        # 建立组件间连接
        await self._connect_components()
        
        print("✅ 初始化完成")
    
    async def _register_base_cells(self):
        """注册基础细胞类型"""
        cells = [
            ReasoningCell(),
            MemoryCell(),
            LearningCell(),
            PerceptionCell(),
            ActionCell(),
            PredictionCell()
        ]
        
        for cell in cells:
            self.cell_registry.register_cell(cell)
            self.emergence_engine.register_cells([cell])
        
        print(f"📦 注册了 {len(cells)} 个基础细胞")
    
    async def _connect_components(self):
        """建立组件间的通信连接"""
        print("🔗 建立组件连接...")
    
    async def start(self):
        """启动生命系统"""
        if self.is_running:
            print("⚠️ 系统已在运行")
            return
        
        print("🚀 启动 LivingTree AI...")
        self.is_running = True
        self.start_time = datetime.now()
        
        # 启动各组件
        await self.initialize()
        
        # 创建任务协程
        self.tasks = [
            asyncio.create_task(self._run_inference_loop()),
            asyncio.create_task(self._run_monitoring_loop()),
            asyncio.create_task(self._run_evolution_loop()),
            asyncio.create_task(self._run_task_processor()),
            asyncio.create_task(self._run_immune_monitor()),
            asyncio.create_task(self._run_metabolic_manager())
        ]
        
        print("🌟 LivingTree AI 已启动")
        
        # 等待关闭信号
        await self.shutdown_event.wait()
        
        # 清理
        await self._cleanup()
    
    async def _run_inference_loop(self):
        """运行主动推理循环"""
        while self.is_running:
            try:
                result = await self.life_engine.run_inference_cycle()
                
                # 记录指标
                self.metrics['inference_cycles'].append({
                    'timestamp': datetime.now().isoformat(),
                    'free_energy': result['free_energy'],
                    'prediction_error': result['prediction_error'],
                    'awareness_level': result['awareness_level']
                })
                
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ 推理循环错误: {e}")
                await asyncio.sleep(1)
    
    async def _run_monitoring_loop(self):
        """运行监控循环"""
        while self.is_running:
            try:
                # 获取各组件状态
                status = await self.get_status()
                
                # 记录指标
                self.metrics['energy_level'].append({
                    'timestamp': datetime.now().isoformat(),
                    'level': status['metabolic']['energy_level']
                })
                
                self.metrics['health_status'].append({
                    'timestamp': datetime.now().isoformat(),
                    'status': status['immune']['status']
                })
                
                self.metrics['consciousness_level'].append({
                    'timestamp': datetime.now().isoformat(),
                    'level': status['self_consciousness']['consciousness_level']
                })
                
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ 监控循环错误: {e}")
                await asyncio.sleep(2)
    
    async def _run_evolution_loop(self):
        """运行进化循环"""
        while self.is_running:
            try:
                await self.evolution_engine.run_generation()
                await asyncio.sleep(10)  # 每10秒运行一次进化
            except Exception as e:
                print(f"❌ 进化循环错误: {e}")
                await asyncio.sleep(10)
    
    async def _run_task_processor(self):
        """运行任务处理器"""
        while self.is_running:
            try:
                task = await self.task_queue.get()
                await self._process_task(task)
                self.task_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 任务处理错误: {e}")
    
    async def _run_immune_monitor(self):
        """运行免疫监控"""
        while self.is_running:
            try:
                await self.immune_system.monitor()
                await asyncio.sleep(3)
            except Exception as e:
                print(f"❌ 免疫监控错误: {e}")
                await asyncio.sleep(3)
    
    async def _run_metabolic_manager(self):
        """运行代谢管理器"""
        while self.is_running:
            try:
                await self.metabolic_system.manage_resources()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ 代谢管理错误: {e}")
                await asyncio.sleep(1)
    
    async def _process_task(self, task: Dict):
        """处理任务"""
        task_type = task.get('type')
        
        if task_type == 'predict':
            await self._handle_predict_task(task)
        elif task_type == 'reason':
            await self._handle_reason_task(task)
        elif task_type == 'learn':
            await self._handle_learn_task(task)
        else:
            print(f"⚠️ 未知任务类型: {task_type}")
    
    async def _handle_predict_task(self, task: Dict):
        """处理预测任务"""
        predictor = PredictionCell()
        result = predictor.predict(
            task.get('data_type', 'unknown'),
            horizon=task.get('horizon', 30)
        )
        print(f"📊 预测结果: {result.data_type} -> 置信度 {result.confidence}")
    
    async def _handle_reason_task(self, task: Dict):
        """处理推理任务"""
        reasoner = ReasoningCell()
        signal = {'type': 'reason', 'query': task.get('query', '')}
        await reasoner.process(signal)
        print(f"🧠 推理完成: {task.get('query', '')}")
    
    async def _handle_learn_task(self, task: Dict):
        """处理学习任务"""
        learner = LearningCell()
        await learner.process({'type': 'learn', 'data': task.get('data', {})})
        print(f"📚 学习完成")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'is_running': self.is_running,
            'life_engine': self.life_engine.get_system_status() if self.life_engine else {},
            'self_consciousness': self.self_consciousness.get_self_report() if self.self_consciousness else {},
            'immune': self.immune_system.get_immune_status() if self.immune_system else {},
            'metabolic': self.metabolic_system.get_metabolic_report() if self.metabolic_system else {},
            'autonomous_evolution': self.autonomous_evolution.get_evolution_stats() if self.autonomous_evolution else {},
            'dynamic_assembly': self.dynamic_assembly.get_assembly_stats() if self.dynamic_assembly else {},
            'self_regeneration': self.self_regeneration.get_regeneration_stats() if self.self_regeneration else {},
            'cell_count': len(self.cell_registry.get_all_cells()),
            'evolution_generation': self.evolution_engine.generation if self.evolution_engine else 0
        }
    
    async def shutdown(self):
        """关闭生命系统"""
        print("🛑 正在关闭 LivingTree AI...")
        
        self.is_running = False
        self.shutdown_event.set()
        
        # 取消所有任务
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        print("✅ LivingTree AI 已关闭")
    
    async def _cleanup(self):
        """清理资源"""
        pass
    
    def add_task(self, task: Dict):
        """添加任务到队列"""
        self.task_queue.put_nowait(task)
    
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """执行任务"""
        # 使用模型组装器创建任务处理模型
        assembler = ModelAssemblyLine()
        model = assembler.assemble(task_description)
        result = await model.execute(task_description)
        return result


async def interactive_mode():
    """交互模式"""
    living_tree = LivingTree()
    await living_tree.initialize()
    
    print("\n🤖 LivingTree AI 交互模式")
    print("==============================")
    print("输入 'help' 查看命令")
    print("输入 'exit' 退出")
    print("==============================\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            
            if user_input.lower() == 'exit':
                break
            elif user_input.lower() == 'help':
                print("""
命令列表:
  status         - 查看系统状态
  introspect     - 内省模式
  predict        - 执行预测
  reason         - 执行推理
  learn          - 学习模式
  evolve         - 执行进化
  autonomous     - 自主进化一次
  assemble       - 动态组装细胞
  regenerate     - 自我再生
  damage         - 检查损伤报告
  heal           - 自我修复
  summary        - 生成摘要
  exit           - 退出
                """)
            elif user_input.lower() == 'status':
                status = await living_tree.get_status()
                print(json.dumps(status, indent=2, ensure_ascii=False))
            elif user_input.lower() == 'introspect':
                report = living_tree.self_consciousness.get_self_report()
                print(f"自我叙事: {report['narrative']}")
                print(f"意识水平: {report['consciousness_level']}")
                print(f"自我价值: {report['self_worth']:.2f}")
            elif user_input.lower().startswith('predict'):
                parts = user_input.split(' ', 1)
                data_type = parts[1] if len(parts) > 1 else 'unknown'
                predictor = PredictionCell()
                result = predictor.predict(data_type, horizon=7)
                print(f"预测类型: {result.data_type}")
                print(f"置信度: {result.confidence}")
                print(f"预测值: {result.predictions[0]['value']}")
            elif user_input.lower().startswith('reason'):
                parts = user_input.split(' ', 1)
                query = parts[1] if len(parts) > 1 else '思考什么?'
                reasoner = ReasoningCell()
                result = await reasoner.process({'type': 'reason', 'query': query})
                print(f"推理完成")
            elif user_input.lower() == 'evolve':
                await living_tree.evolution_engine.run_generation()
                print(f"完成第 {living_tree.evolution_engine.generation} 代进化")
            elif user_input.lower() == 'heal':
                result = await living_tree.immune_system.heal()
                print(result['message'])
            elif user_input.lower() == 'autonomous':
                result = await living_tree.autonomous_evolution.evolve()
                print(f"自主进化完成")
                print(f"  代数: {result['generation']}")
                print(f"  成功: {result['success']}")
                print(f"  性能变化: {result['performance_after']}")
            elif user_input.lower().startswith('assemble'):
                parts = user_input.split(' ', 1)
                task = parts[1] if len(parts) > 1 else '分析任务'
                result = await living_tree.dynamic_assembly.assemble_for_task(task)
                print(f"动态组装完成")
                print(f"  组装ID: {result.id}")
                print(f"  细胞数量: {len(result.cells)}")
                print(f"  连接数量: {len(result.connections)}")
                print(f"  质量: {result.quality.value}")
            elif user_input.lower() == 'regenerate':
                result = await living_tree.self_regeneration.regenerate()
                print(f"自我再生完成")
                print(f"  状态: {result['status']}")
                print(f"  成功: {result['success']}")
                print(f"  消息: {result['message']}")
            elif user_input.lower() == 'damage':
                report = living_tree.self_regeneration.get_damage_report()
                print(f"损伤报告:")
                print(f"  总细胞数: {report['total_cells']}")
                print(f"  受损细胞: {report['damage_summary']['damaged_count']}")
                print(f"  健康细胞: {report['damage_summary']['healthy_count']}")
                print(f"  损伤比例: {report['damage_summary']['damage_ratio']:.2%}")
            elif user_input.lower() == 'summary':
                status = await living_tree.get_status()
                summary = f"""
系统摘要:
┌─────────────────────────────────────┐
│ 运行时间: {status['uptime']:.1f} 秒
│ 状态: {'运行中' if status['is_running'] else '已停止'}
│ 细胞数量: {status['cell_count']}
│ 进化代数: {status['evolution_generation']}
│ 意识水平: {status['self_consciousness'].get('consciousness_level', '未知')}
│ 免疫状态: {status['immune'].get('status', '未知')}
│ 能量级别: {status['metabolic'].get('energy_level', '未知')}
└─────────────────────────────────────┘
                """
                print(summary)
            else:
                # 作为通用任务处理
                result = await living_tree.execute_task(user_input)
                print(f"任务执行完成: {result}")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("\n👋 再见!")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="LivingTree AI - 数字生命系统")
    parser.add_argument('command', choices=['start', 'status', 'interactive', 'stop'], 
                        help='命令: start|status|interactive|stop')
    parser.add_argument('--module', help='启动特定模块')
    
    args = parser.parse_args()
    
    if args.command == 'interactive':
        asyncio.run(interactive_mode())
    elif args.command == 'start':
        living_tree = LivingTree()
        try:
            asyncio.run(living_tree.start())
        except KeyboardInterrupt:
            asyncio.run(living_tree.shutdown())
    elif args.command == 'status':
        # 简化的状态检查
        print("LivingTree AI 状态检查")
        print("需要运行中的实例才能获取详细状态")
    elif args.command == 'stop':
        print("停止命令需要运行中的实例")


if __name__ == '__main__':
    main()