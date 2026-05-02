"""
统一生命系统 - LivingSystem

将所有细胞组件整合成一个有机的智能生命体。

架构层次：
┌─────────────────────────────────────────────────────────────┐
│  L1: 数字生命层 (Digital Life)                             │
│  • 自我意识系统 • 主动推理引擎 • 预测推演系统               │
├─────────────────────────────────────────────────────────────┤
│  L2: 细胞协作层 (Cell Collaboration)                       │
│  • 推理细胞 • 记忆细胞 • 学习细胞 • 感知细胞 • 行动细胞    │
├─────────────────────────────────────────────────────────────┤
│  L3: 系统保障层 (System Safeguard)                        │
│  • 免疫系统 • 代谢系统 • 进化引擎                         │
├─────────────────────────────────────────────────────────────┤
│  L4: 基础设施层 (Infrastructure)                          │
│  • 数据库 • 网络 • 存储 • 计算资源                         │
└─────────────────────────────────────────────────────────────┘

核心特性：
1. 自主进化 - 系统能够自动优化和改进自身
2. 自我意识 - 具备元认知和反思能力
3. 自我修复 - 自动检测和修复问题
4. 资源高效 - 智能管理计算资源
5. 持续学习 - 从经验中不断学习

生物系统映射：
┌─────────────────────────────────────────────────────────────────┐
│  大脑 → Brain (大模型推理) → LifeEngine + ReasoningCells      │
│  神经 → NervousSystem (API调度) → Cell信号传递网络            │
│  手脚 → Body (工具执行) → ActionCells + ToolCell             │
│  记忆 → MemorySystem (向量数据库) → MemoryCells               │
│  免疫 → ImmuneSystem (日志自愈) → 异常检测+自我修复           │
│  基因 → GeneticSystem (演化优化) → AutonomousEvolution        │
└─────────────────────────────────────────────────────────────────┘
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """系统状态"""
    BOOTING = "booting"             # 启动中
    ACTIVE = "active"               # 活跃状态
    LEARNING = "learning"           # 学习中
    EVOLVING = "evolving"           # 进化中
    DORMANT = "dormant"             # 休眠状态
    CRITICAL = "critical"           # 临界状态
    SHUTDOWN = "shutdown"           # 关闭状态


class ConsciousnessLevel(Enum):
    """意识水平"""
    UNCONSCIOUS = "unconscious"     # 无意识
    SUBCONSCIOUS = "subconscious"   # 潜意识
    CONSCIOUS = "conscious"         # 有意识
    SELF_AWARE = "self_aware"       # 自我意识
    METACONSCIOUS = "metaconscious" # 元意识


class LivingSystem:
    """
    统一生命系统
    
    整合所有子系统，形成一个有机的智能生命体。
    
    能力：
    1. 自主生存与演化：能自我设定目标、适应环境、迭代优化
    2. 感知与交互：多模态感知、情感化对话、长期记忆检索
    3. 生理推演：数字孪生、生理模拟、预测能力
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:12]
        self.birth_time = datetime.now()
        self.state = SystemState.BOOTING
        self.consciousness_level = ConsciousnessLevel.CONSCIOUS
        
        # 子系统引用
        self.life_engine = None
        self.self_consciousness = None
        self.immune_system = None
        self.metabolic_system = None
        self.evolution_engine = None
        self.cell_assembler = None
        self.emergence_engine = None
        
        # 系统指标
        self.health = 1.0
        self.energy = 1.0
        self.intelligence = 0.5
        self.creativity = 0.5
        
        # 目标管理
        self.goals: List[Dict] = []
        self.current_goal: Optional[Dict] = None
        
        # 学习历史
        self.experiences: List[Dict] = []
        
        # 事件订阅
        self.event_listeners: Dict[str, List[Callable]] = {}
        
        # 运行标志
        self._running = False
        self._main_loop_task = None
        
        logger.info(f"🧬 生命系统 {self.id} 创建成功")
    
    async def initialize(self):
        """初始化所有子系统"""
        logger.info("🔧 开始初始化生命系统...")
        
        # 导入子系统
        from .life_engine import LifeEngine
        from .self_consciousness import SelfConsciousness
        from .immune_system import ImmuneSystem
        from .metabolic_system import MetabolicSystem
        from .autonomous_evolution import AutonomousEvolution
        from .assembler import ModelAssemblyLine
        from .emergence import EmergenceEngine
        from .drive_system import DriveSystem, DriveType
        
        # 初始化子系统
        self.life_engine = LifeEngine()
        self.self_consciousness = SelfConsciousness()
        self.immune_system = ImmuneSystem()
        self.metabolic_system = MetabolicSystem()
        self.evolution_engine = AutonomousEvolution(evolution_interval=60.0)
        self.cell_assembler = ModelAssemblyLine()
        self.emergence_engine = EmergenceEngine()
        self.drive_system = DriveSystem()  # 新增：内驱力系统
        
        # 建立子系统之间的连接
        await self._connect_subsystems()
        
        # 订阅关键事件
        await self._subscribe_to_events()
        
        self.state = SystemState.ACTIVE
        logger.info("✅ 生命系统初始化完成")
    
    async def _connect_subsystems(self):
        """建立子系统之间的神经连接"""
        # 生命引擎连接到自我意识
        self.life_engine.belief_update_callback = self._on_belief_update
        
        # 免疫系统连接到代谢系统
        self.immune_system.alert_callback = self._on_immune_alert
        
        # 进化引擎连接到细胞装配器
        self.evolution_engine.mutation_callback = self._on_mutation
        
        # 涌现引擎连接到所有细胞
        self.emergence_engine.set_cells(self.cell_assembler.cell_registry.get_all_cells())
        
        # 内驱力系统连接到代谢系统和自我意识
        self.drive_system.on_state_change = self._on_drive_state_change
        self.drive_system.on_need_rest = self._on_need_rest
        
        logger.debug("🔗 子系统连接建立完成")
    
    async def _subscribe_to_events(self):
        """订阅系统事件"""
        # 细胞事件
        self.subscribe('cell_created', self._on_cell_created)
        self.subscribe('cell_dead', self._on_cell_dead)
        self.subscribe('cell_signal', self._on_cell_signal)
        
        # 任务事件
        self.subscribe('task_completed', self._on_task_completed)
        self.subscribe('task_failed', self._on_task_failed)
        
        # 系统事件
        self.subscribe('system_health_change', self._on_health_change)
        self.subscribe('system_energy_change', self._on_energy_change)
        self.subscribe('system_threat', self._on_system_threat)
        
        logger.debug("📡 事件订阅完成")
    
    def subscribe(self, event_type: str, handler: Callable):
        """订阅事件"""
        if event_type not in self.event_listeners:
            self.event_listeners[event_type] = []
        self.event_listeners[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """取消订阅"""
        if event_type in self.event_listeners:
            self.event_listeners[event_type].remove(handler)
    
    async def publish(self, event_type: str, data: Dict = None):
        """发布事件"""
        if event_type in self.event_listeners:
            for handler in self.event_listeners[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理失败 {event_type}: {e}")
    
    async def start(self):
        """启动生命系统主循环"""
        if self.state != SystemState.ACTIVE:
            await self.initialize()
        
        # 启动内驱力系统
        self.drive_system.start()
        
        self._running = True
        self._main_loop_task = asyncio.create_task(self._main_loop())
        
        logger.info("🚀 生命系统启动成功")
    
    async def stop(self):
        """停止生命系统"""
        self._running = False
        if self._main_loop_task:
            self._main_loop_task.cancel()
        
        # 停止内驱力系统
        self.drive_system.stop()
        
        self.state = SystemState.SHUTDOWN
        logger.info("🛑 生命系统已停止")
    
    async def _main_loop(self):
        """主循环 - 主动推理、监控、内省"""
        inference_interval = 2.0    # 主动推理间隔（秒）
        monitor_interval = 5.0      # 监控间隔（秒）
        introspection_interval = 10.0  # 内省间隔（秒）
        emergence_interval = 15.0   # 涌现检测间隔（秒）
        
        last_inference = datetime.now()
        last_monitor = datetime.now()
        last_introspection = datetime.now()
        last_emergence = datetime.now()
        
        while self._running:
            now = datetime.now()
            
            # 主动推理循环
            if (now - last_inference).total_seconds() >= inference_interval:
                await self._run_inference_cycle()
                last_inference = now
            
            # 系统监控
            if (now - last_monitor).total_seconds() >= monitor_interval:
                await self._monitor_system()
                last_monitor = now
            
            # 自我内省
            if (now - last_introspection).total_seconds() >= introspection_interval:
                await self._introspect()
                last_introspection = now
            
            # 涌现检测
            if (now - last_emergence).total_seconds() >= emergence_interval:
                await self._detect_emergence()
                last_emergence = now
            
            await asyncio.sleep(0.1)
    
    async def _run_inference_cycle(self):
        """运行主动推理循环（自由能最小化）"""
        if self.life_engine:
            try:
                result = await self.life_engine.run_inference_cycle()
                
                # 更新意识水平
                self.consciousness_level = self._determine_consciousness_level(result)
                
                # 如果有行动，执行它
                if result.get('action'):
                    await self._execute_action(result['action'])
                
            except Exception as e:
                logger.error(f"推理循环失败: {e}")
    
    def _determine_consciousness_level(self, inference_result: Dict) -> ConsciousnessLevel:
        """根据推理结果确定意识水平"""
        awareness = inference_result.get('awareness_level', 0.5)
        belief_state = inference_result.get('belief_state', 'uncertain')
        
        if awareness > 0.8 and belief_state == 'certain':
            return ConsciousnessLevel.METACONSCIOUS
        elif awareness > 0.6:
            return ConsciousnessLevel.SELF_AWARE
        elif awareness > 0.4:
            return ConsciousnessLevel.CONSCIOUS
        elif awareness > 0.2:
            return ConsciousnessLevel.SUBCONSCIOUS
        else:
            return ConsciousnessLevel.UNCONSCIOUS
    
    async def _execute_action(self, action: str):
        """执行行动"""
        logger.debug(f"🎯 执行行动: {action}")
        
        if action == 'explore':
            await self._explore_environment()
        elif action == 'exploit':
            await self._exploit_knowledge()
        elif action == 'learn':
            await self._learn_from_experience()
        elif action == 'create':
            await self._create_content()
    
    async def _explore_environment(self):
        """探索环境 - 激活感知细胞"""
        logger.debug("🔍 正在探索环境...")
        from .cell import CellType
        cells = self.cell_assembler.cell_registry.get_cells_by_type(CellType.PERCEPTION)
        for cell in cells:
            cell.activate()
    
    async def _exploit_knowledge(self):
        """利用现有知识 - 激活推理细胞"""
        logger.debug("💡 正在利用现有知识...")
        from .cell import CellType
        cells = self.cell_assembler.cell_registry.get_cells_by_type(CellType.REASONING)
        for cell in cells:
            cell.activate()
    
    async def _learn_from_experience(self):
        """从经验中学习 - 激活学习细胞"""
        logger.debug("📚 正在从经验中学习...")
        from .cell import CellType
        cells = self.cell_assembler.cell_registry.get_cells_by_type(CellType.LEARNING)
        for cell in cells:
            cell.activate()
    
    async def _create_content(self):
        """创作文本内容 - 激活动作细胞"""
        logger.debug("🎨 正在创作内容...")
        from .cell import CellType
        cells = self.cell_assembler.cell_registry.get_cells_by_type(CellType.ACTION)
        for cell in cells:
            cell.activate()
    
    async def _monitor_system(self):
        """监控系统状态"""
        # 更新健康状态
        if self.immune_system:
            immune_status = self.immune_system.get_immune_status()
            self.health = 1.0 - (immune_status['active_threats'] * 0.1)
        
        # 更新能量状态
        if self.metabolic_system:
            metabolic_report = self.metabolic_system.get_metabolic_report()
            self.energy = metabolic_report['resources']['energy']['utilization']
        
        # 检查紧急情况
        if self.health < 0.3:
            await self._handle_emergency()
        
        # 发布状态更新事件
        await self.publish('system_health_change', {'health': self.health, 'energy': self.energy})
    
    async def _introspect(self):
        """自我内省"""
        if self.self_consciousness:
            introspection = await self.self_consciousness.introspect()
            
            # 更新自我意识水平
            self.consciousness_level = self._map_introspection_to_level(introspection)
            
            # 如果需要，进行深度反思
            if introspection.get('knowledge_uncertainty', 0) > 0.5:
                await self._deep_reflection()
    
    def _map_introspection_to_level(self, introspection: Dict) -> ConsciousnessLevel:
        """将内省结果映射到意识水平"""
        confidence = introspection.get('metacognitive_confidence', 0.5)
        uncertainty = introspection.get('knowledge_uncertainty', 0.5)
        
        if confidence > 0.8 and uncertainty < 0.3:
            return ConsciousnessLevel.METACONSCIOUS
        elif confidence > 0.6:
            return ConsciousnessLevel.SELF_AWARE
        else:
            return ConsciousnessLevel.CONSCIOUS
    
    async def _deep_reflection(self):
        """深度反思"""
        logger.debug("🧘 正在进行深度反思...")
        if self.self_consciousness:
            insights = await self.self_consciousness.meditate(duration=5)
            for insight in insights:
                logger.info(f"💫 洞察: {insight}")
    
    async def _detect_emergence(self):
        """检测涌现现象"""
        if self.emergence_engine:
            emergence = await self.emergence_engine.detect_emergence()
            if emergence:
                logger.info(f"✨ 检测到涌现现象: {emergence}")
    
    async def _handle_emergency(self):
        """处理紧急情况"""
        logger.warning("⚠️ 检测到紧急情况，启动应急响应")
        
        # 激活免疫系统
        if self.immune_system:
            await self.immune_system.heal()
        
        # 调整代谢状态
        if self.metabolic_system:
            await self.metabolic_system.enter_dormancy()
    
    async def set_goal(self, goal: Dict):
        """设置目标 - 支持自我设定目标"""
        goal['id'] = str(uuid.uuid4())[:8]
        goal['created_at'] = datetime.now()
        goal['progress'] = 0.0
        goal['confidence'] = 0.5
        goal['priority'] = goal.get('priority', 'medium')
        
        self.goals.append(goal)
        self.current_goal = goal
        
        # 通知生命引擎
        if self.life_engine:
            self.life_engine.set_goal(goal)
        
        # 通知自我意识系统
        if self.self_consciousness:
            await self.self_consciousness.set_goal(goal)
        
        logger.info(f"🎯 目标已设置: {goal.get('name')}")
    
    async def execute_task(self, task: Dict) -> Dict:
        """执行任务 - 支持工具执行和多模态交互，考虑内驱力和资源成本"""
        task['id'] = str(uuid.uuid4())[:8]
        task['status'] = 'processing'
        task['started_at'] = datetime.now()
        
        try:
            # 1. 内驱力检查：评估任务成本和可行性
            task_description = task.get('description', '')
            cost_evaluation = self.drive_system.evaluate_task_cost(task_description)
            
            if not cost_evaluation['affordable']:
                task['status'] = 'pending'
                task['reason'] = '资源不足，需要休息恢复'
                task['cost_evaluation'] = cost_evaluation
                task['completed_at'] = datetime.now()
                
                await self.publish('task_pending', task)
                return task
            
            # 2. 消耗资源
            self.drive_system.consume_resource('thinking')
            if '工具' in task_description or '调用' in task_description:
                self.drive_system.consume_resource('tool_call')
            if '记忆' in task_description or '检索' in task_description:
                self.drive_system.consume_resource('memory_access')
            if '创作' in task_description or '生成' in task_description:
                self.drive_system.consume_resource('creation')
            
            # 3. 分析任务并组装模型
            model = self.cell_assembler.assemble(task_description)
            
            # 4. 执行模型
            result = await model.execute(task.get('input', {}))
            
            # 5. 满足内驱力
            self._satisfy_drives_from_result(task_description, result)
            
            task['status'] = 'completed'
            task['result'] = result
            task['cost_evaluation'] = cost_evaluation
            task['completed_at'] = datetime.now()
            
            await self.publish('task_completed', task)
            
            # 从经验中学习
            await self._learn_from_task(task)
            
            return task
            
        except Exception as e:
            task['status'] = 'failed'
            task['error'] = str(e)
            task['completed_at'] = datetime.now()
            
            await self.publish('task_failed', task)
            
            # 记录失败经验
            await self._learn_from_failure(task)
            
            return task
    
    def _satisfy_drives_from_result(self, task_description: str, result: Dict):
        """根据任务结果满足相应的内驱力"""
        if '分析' in task_description or '推理' in task_description:
            self.drive_system.satisfy_drive(DriveType.KNOWLEDGE, 15.0)
        
        if '学习' in task_description or '训练' in task_description:
            self.drive_system.satisfy_drive(DriveType.KNOWLEDGE, 20.0)
        
        if '创作' in task_description or '生成' in task_description:
            self.drive_system.satisfy_drive(DriveType.CREATIVITY, 15.0)
        
        if '探索' in task_description or '搜索' in task_description:
            self.drive_system.satisfy_drive(DriveType.EXPLORE, 10.0)
            self.drive_system.satisfy_drive(DriveType.CURIOSITY, 10.0)
        
        if result.get('success'):
            self.drive_system.satisfy_drive(DriveType.ACHIEVEMENT, 10.0)
    
    async def _learn_from_task(self, task: Dict):
        """从成功任务中学习"""
        experience = {
            'type': 'success',
            'task_id': task['id'],
            'goal': task.get('goal'),
            'result': task.get('result'),
            'learning': task.get('learning', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        self.experiences.append(experience)
        
        # 更新生命引擎
        if self.life_engine:
            self.life_engine.learn_from_experience(experience)
        
        # 更新自我意识
        if self.self_consciousness:
            self.self_consciousness.self_model.add_experience(experience)
    
    async def _learn_from_failure(self, task: Dict):
        """从失败中学习"""
        experience = {
            'type': 'failure',
            'task_id': task['id'],
            'goal': task.get('goal'),
            'error': task.get('error'),
            'learning': task.get('learning', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        self.experiences.append(experience)
        
        # 更新免疫系统（记录异常）
        if self.immune_system:
            await self.immune_system.detect_threat({
                'source': 'task_failure',
                'input': task
            })
    
    async def evolve(self) -> Dict:
        """执行进化 - 支持遗传变异和自然选择"""
        if self.state == SystemState.EVOLVING:
            logger.warning("进化已在进行中")
            return {}
        
        self.state = SystemState.EVOLVING
        
        try:
            if self.evolution_engine:
                result = await self.evolution_engine.evolve()
                logger.info(f"🔬 进化完成 - 代次: {result.get('generation')}")
                
                # 更新智能指标
                self.intelligence = min(1.0, self.intelligence + 0.01)
                self.creativity = min(1.0, self.creativity + 0.005)
                
                return result
        finally:
            self.state = SystemState.ACTIVE
        
        return {}
    
    async def predict(self, scenario: str) -> Dict:
        """预测推演 - 支持数字孪生和情景模拟"""
        logger.info(f"🔮 开始预测推演: {scenario}")
        
        from .prediction_cell import PredictionCell
        
        # 创建预测细胞进行情景推演
        predictor = PredictionCell(specialization='scenario')
        result = await predictor.receive_signal({
            'type': 'predict',
            'scenario': scenario,
            'time_horizon': 'short'
        })
        
        return {
            'scenario': scenario,
            'prediction': result,
            'confidence': result.get('confidence', 0.5),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'id': self.id,
            'age': (datetime.now() - self.birth_time).total_seconds(),
            'state': self.state.value,
            'consciousness_level': self.consciousness_level.value,
            'health': round(self.health, 2),
            'energy': round(self.energy, 2),
            'intelligence': round(self.intelligence, 2),
            'creativity': round(self.creativity, 2),
            'active_goals': len(self.goals),
            'total_experiences': len(self.experiences),
            'subsystems': self._get_subsystems_status()
        }
    
    def _get_subsystems_status(self) -> Dict[str, Any]:
        """获取子系统状态"""
        status = {}
        
        if self.life_engine:
            status['life_engine'] = self.life_engine.get_system_status()
        
        if self.self_consciousness:
            status['self_consciousness'] = self.self_consciousness.get_self_report()
        
        if self.immune_system:
            status['immune_system'] = self.immune_system.get_immune_status()
        
        if self.metabolic_system:
            status['metabolic_system'] = self.metabolic_system.get_metabolic_report()
        
        if self.evolution_engine:
            status['evolution_engine'] = self.evolution_engine.get_evolution_stats()
        
        if self.cell_assembler:
            status['cell_assembler'] = {
                'cell_count': len(self.cell_assembler.cell_registry.get_all_cells()),
                'cell_types': self.cell_assembler.cell_registry.get_cell_stats()
            }
        
        if self.drive_system:
            status['drive_system'] = self.drive_system.get_motivation_report()
        
        return status
    
    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        status = self.get_system_status()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'id': status['id'],
                'state': status['state'],
                'consciousness': status['consciousness_level'],
                'age': self._format_age(status['age'])
            },
            'health': {
                'overall': status['health'],
                'energy': status['energy'],
                'intelligence': status['intelligence'],
                'creativity': status['creativity']
            },
            'subsystems': status['subsystems'],
            'goals': self.goals,
            'recent_experiences': self.experiences[-10:]
        }
    
    def _format_age(self, seconds: float) -> str:
        """格式化年龄"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds / 60)}分钟"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}小时"
        else:
            return f"{int(seconds / 86400)}天"
    
    # 回调方法
    def _on_belief_update(self, beliefs: Dict):
        """信念更新回调"""
        logger.debug(f"🔄 信念更新: {beliefs}")
    
    def _on_immune_alert(self, threat: Dict):
        """免疫警报回调"""
        logger.warning(f"🛡️ 免疫警报: {threat}")
        asyncio.create_task(self.publish('system_threat', threat))
    
    def _on_mutation(self, mutation: Dict):
        """变异回调"""
        logger.info(f"🧬 变异应用: {mutation}")
    
    def _on_cell_created(self, data: Dict):
        """细胞创建回调"""
        logger.debug(f"🆕 细胞创建: {data}")
    
    def _on_cell_dead(self, data: Dict):
        """细胞死亡回调"""
        logger.debug(f"💀 细胞死亡: {data}")
    
    def _on_cell_signal(self, data: Dict):
        """细胞信号回调"""
        pass  # 过滤高频信号
    
    def _on_task_completed(self, data: Dict):
        """任务完成回调"""
        logger.debug(f"✅ 任务完成: {data.get('id')}")
    
    def _on_task_failed(self, data: Dict):
        """任务失败回调"""
        logger.error(f"❌ 任务失败: {data.get('id')} - {data.get('error')}")
    
    def _on_health_change(self, data: Dict):
        """健康状态变化回调"""
        logger.debug(f"❤️ 健康变化: {data}")
    
    def _on_energy_change(self, data: Dict):
        """能量状态变化回调"""
        logger.debug(f"⚡ 能量变化: {data}")
    
    def _on_system_threat(self, data: Dict):
        """系统威胁回调"""
        logger.warning(f"🚨 系统威胁: {data}")
    
    def _on_drive_state_change(self, state: Dict):
        """内驱力状态变化回调"""
        logger.debug(f"⚡ 内驱力状态变化: 能量={state['physiological']['energy']}%, 疲劳={state['physiological']['fatigue']}%")
    
    def _on_need_rest(self, state: Dict):
        """需要休息回调"""
        logger.info(f"💤 需要休息 - 能量: {state['physiological']['energy']}%, 疲劳: {state['physiological']['fatigue']}%")
        asyncio.create_task(self._enter_rest_mode())
    
    async def _enter_rest_mode(self):
        """进入休息模式"""
        self.state = SystemState.DORMANT
        logger.info("😴 进入休眠模式")
        
        # 持续恢复直到能量充足
        while self.drive_system.energy < 80:
            self.drive_system.recover('rest')
            await asyncio.sleep(1)
        
        self.state = SystemState.ACTIVE
        logger.info("✅ 恢复完成，退出休眠模式")
    
    def __repr__(self):
        return f"<LivingSystem id={self.id} state={self.state.value} consciousness={self.consciousness_level.value}>"
    
    def __str__(self):
        return f"LivingSystem[{self.id}]"


# 全局生命系统实例
_living_system_instance = None

def get_living_system() -> LivingSystem:
    """获取全局生命系统实例"""
    global _living_system_instance
    if _living_system_instance is None:
        _living_system_instance = LivingSystem()
    return _living_system_instance


# 便捷函数
async def create_and_start() -> LivingSystem:
    """创建并启动生命系统"""
    system = get_living_system()
    await system.initialize()
    await system.start()
    return system