"""
细胞装配器 - CellAssembler

负责细胞的创建、管理、连接和任务执行。

核心功能：
1. 细胞注册和生命周期管理
2. 动态细胞组装
3. 任务驱动的细胞协作
4. 自适应网络构建
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

from .cell import Cell, CellType, CellState
from .reasoning_cell import ReasoningCell, CausalReasoningCell, SymbolicReasoningCell
from .memory_cell import MemoryCell, HippocampusCell, NeocortexCell
from .learning_cell import LearningCell, EWCCell, ProgressiveCell, MetaLearningCell
from .perception_cell import PerceptionCell, MultimodalCell, IntentCell
from .action_cell import ActionCell, CodeCell, ToolCell, GenerationCell
from .prediction_cell import PredictionCell, TimeSeriesPredictor, ResourcePredictor, HealthPredictor

logger = logging.getLogger(__name__)


class AssemblyStrategy(Enum):
    """组装策略"""
    FULLY_CONNECTED = "fully_connected"  # 全连接
    SPARSE = "sparse"                    # 稀疏连接
    HIERARCHICAL = "hierarchical"        # 层次连接
    DYNAMIC = "dynamic"                  # 动态连接


class CellAssembler:
    """
    细胞装配器
    
    负责管理所有细胞的生命周期和协作。
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.cells: Dict[str, Cell] = {}
        self.assembly_strategy = AssemblyStrategy.DYNAMIC
        
        # 细胞类型映射
        self.cell_type_map = {
            'reasoning': ReasoningCell,
            'causal': CausalReasoningCell,
            'symbolic': SymbolicReasoningCell,
            'memory': MemoryCell,
            'hippocampus': HippocampusCell,
            'neocortex': NeocortexCell,
            'learning': LearningCell,
            'ewc': EWCCell,
            'progressive': ProgressiveCell,
            'metalearning': MetaLearningCell,
            'perception': PerceptionCell,
            'multimodal': MultimodalCell,
            'intent': IntentCell,
            'action': ActionCell,
            'code': CodeCell,
            'tool': ToolCell,
            'generation': GenerationCell,
            'prediction': PredictionCell,
            'timeseries': TimeSeriesPredictor,
            'resource': ResourcePredictor,
            'health': HealthPredictor,
        }
        
        # 细胞模板（用于快速创建）
        self.cell_templates: Dict[str, Dict] = {
            'default_reasoning': {'type': 'reasoning', 'specialization': 'general'},
            'deep_reasoning': {'type': 'causal', 'specialization': 'deep'},
            'memory_core': {'type': 'hippocampus', 'specialization': 'core'},
            'knowledge_store': {'type': 'neocortex', 'specialization': 'knowledge'},
            'continuous_learner': {'type': 'progressive', 'specialization': 'continuous'},
            'multimodal_input': {'type': 'multimodal', 'specialization': 'input'},
            'intent_parser': {'type': 'intent', 'specialization': 'nlp'},
            'code_generator': {'type': 'code', 'specialization': 'python'},
            'tool_executor': {'type': 'tool', 'specialization': 'general'},
            'content_writer': {'type': 'generation', 'specialization': 'writing'},
        }
        
        # 事件回调
        self.on_cell_created: Optional[Callable] = None
        self.on_cell_dead: Optional[Callable] = None
        self.on_cell_signal: Optional[Callable] = None
        
        logger.info(f"🧬 细胞装配器 {self.id} 已初始化")
    
    async def initialize_cells(self):
        """初始化基础细胞群"""
        logger.info("🔧 初始化基础细胞群...")
        
        # 创建核心细胞
        await self.create_cell_from_template('default_reasoning')
        await self.create_cell_from_template('memory_core')
        await self.create_cell_from_template('knowledge_store')
        await self.create_cell_from_template('multimodal_input')
        await self.create_cell_from_template('intent_parser')
        await self.create_cell_from_template('content_writer')
        
        # 建立初始连接
        await self._establish_initial_connections()
        
        logger.info(f"✅ 基础细胞群初始化完成，共 {len(self.cells)} 个细胞")
    
    async def create_cell_from_template(self, template_name: str) -> Optional[Cell]:
        """从模板创建细胞"""
        template = self.cell_templates.get(template_name)
        if not template:
            logger.warning(f"模板不存在: {template_name}")
            return None
        
        return await self.create_cell(
            cell_type=template['type'],
            specialization=template['specialization']
        )
    
    async def create_cell(self, cell_type: str, specialization: str = "general") -> Cell:
        """
        创建细胞
        
        Args:
            cell_type: 细胞类型名称
            specialization: 专业领域
        
        Returns:
            创建的细胞
        """
        cell_class = self.cell_type_map.get(cell_type)
        if not cell_class:
            raise ValueError(f"未知细胞类型: {cell_type}")
        
        cell = cell_class(specialization=specialization)
        self.cells[cell.id] = cell
        
        # 触发事件
        if self.on_cell_created:
            self.on_cell_created({'cell_id': cell.id, 'type': cell_type, 'specialization': specialization})
        
        logger.debug(f"🆕 创建细胞: {cell}")
        
        return cell
    
    def get_cell(self, cell_id: str) -> Optional[Cell]:
        """获取细胞"""
        return self.cells.get(cell_id)
    
    def get_cells_by_type(self, cell_type: CellType) -> List[Cell]:
        """按类型获取细胞"""
        return [cell for cell in self.cells.values() if cell.cell_type == cell_type]
    
    def get_all_cells(self) -> List[Cell]:
        """获取所有细胞"""
        return list(self.cells.values())
    
    def get_active_cells(self) -> List[Cell]:
        """获取活跃细胞"""
        return [cell for cell in self.cells.values() if cell.is_active]
    
    def get_dormant_cells(self) -> List[Cell]:
        """获取休眠细胞"""
        return [cell for cell in self.cells.values() if cell.state == CellState.DORMANT]
    
    async def destroy_cell(self, cell_id: str):
        """销毁细胞"""
        cell = self.cells.get(cell_id)
        if not cell:
            return
        
        # 断开所有连接
        for other_cell in self.cells.values():
            other_cell.disconnect(cell_id)
        
        # 杀死细胞
        cell.kill()
        
        # 从注册表移除
        del self.cells[cell_id]
        
        # 触发事件
        if self.on_cell_dead:
            self.on_cell_dead({'cell_id': cell_id})
        
        logger.debug(f"💀 销毁细胞: {cell_id}")
    
    async def connect_cells(self, source_id: str, target_id: str, weight: float = 0.5):
        """建立细胞连接"""
        source = self.cells.get(source_id)
        target = self.cells.get(target_id)
        
        if not source or not target:
            return False
        
        source.connect(target, initial_weight=weight)
        logger.debug(f"🔗 连接建立: {source_id} -> {target_id} (权重: {weight})")
        
        return True
    
    async def disconnect_cells(self, source_id: str, target_id: str):
        """断开细胞连接"""
        source = self.cells.get(source_id)
        if source:
            source.disconnect(target_id)
            logger.debug(f"🔌 连接断开: {source_id} -> {target_id}")
    
    async def send_signal(self, source_id: str, target_id: str, message: Dict):
        """发送信号"""
        source = self.cells.get(source_id)
        target = self.cells.get(target_id)
        
        if not source or not target:
            return None
        
        # 触发事件
        if self.on_cell_signal:
            self.on_cell_signal({
                'source_id': source_id,
                'target_id': target_id,
                'message_type': message.get('type')
            })
        
        return await source.send_signal(target, message)
    
    async def broadcast_signal(self, source_id: str, message: Dict):
        """广播信号"""
        source = self.cells.get(source_id)
        if not source:
            return
        
        await source.broadcast_signal(message)
    
    async def activate_cells(self, cell_type: Optional[CellType] = None):
        """激活细胞"""
        cells_to_activate = self.get_cells_by_type(cell_type) if cell_type else self.get_all_cells()
        
        for cell in cells_to_activate:
            cell.activate()
        
        logger.debug(f"⚡ 激活细胞: {len(cells_to_activate)} 个")
    
    async def deactivate_cells(self, cell_type: Optional[CellType] = None):
        """使细胞休眠"""
        cells_to_deactivate = self.get_cells_by_type(cell_type) if cell_type else self.get_all_cells()
        
        for cell in cells_to_deactivate:
            cell.deactivate()
        
        logger.debug(f"😴 休眠细胞: {len(cells_to_deactivate)} 个")
    
    async def activate_reasoning_cells(self):
        """激活推理细胞"""
        await self.activate_cells(CellType.REASONING)
    
    async def activate_memory_cells(self):
        """激活记忆细胞"""
        await self.activate_cells(CellType.MEMORY)
    
    async def activate_learning_cells(self):
        """激活学习细胞"""
        await self.activate_cells(CellType.LEARNING)
    
    async def activate_perception_cells(self):
        """激活感知细胞"""
        await self.activate_cells(CellType.PERCEPTION)
    
    async def activate_action_cells(self):
        """激活行动细胞"""
        await self.activate_cells(CellType.ACTION)
    
    async def activate_prediction_cells(self):
        """激活预测细胞"""
        await self.activate_cells(CellType.PREDICTION)
    
    async def execute_task(self, task: Dict) -> Dict:
        """
        执行任务
        
        Args:
            task: 任务描述
        
        Returns:
            执行结果
        """
        task_id = task.get('id', str(uuid.uuid4())[:8])
        task_type = task.get('type', 'unknown')
        input_data = task.get('input', {})
        
        logger.info(f"🎯 开始执行任务: {task_id} ({task_type})")
        
        results = []
        execution_path = []
        
        try:
            # 阶段1: 感知处理
            perception_result = await self._process_perception(input_data)
            if perception_result:
                results.append(perception_result)
                execution_path.append('perception')
            
            # 阶段2: 推理分析
            reasoning_result = await self._process_reasoning(input_data)
            if reasoning_result:
                results.append(reasoning_result)
                execution_path.append('reasoning')
            
            # 阶段3: 记忆检索
            memory_result = await self._process_memory(input_data)
            if memory_result:
                results.append(memory_result)
                execution_path.append('memory')
            
            # 阶段4: 行动执行
            action_result = await self._process_action(input_data)
            if action_result:
                results.append(action_result)
                execution_path.append('action')
            
            success = all(r.get('success', False) for r in results)
            
            return {
                'task_id': task_id,
                'success': success,
                'execution_path': execution_path,
                'results': results,
                'summary': self._summarize_results(results),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 任务执行失败 {task_id}: {e}")
            return {
                'task_id': task_id,
                'success': False,
                'execution_path': execution_path,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _process_perception(self, input_data: Dict) -> Optional[Dict]:
        """感知处理"""
        perception_cells = self.get_cells_by_type(CellType.PERCEPTION)
        if not perception_cells:
            return None
        
        results = []
        for cell in perception_cells[:3]:  # 最多使用3个感知细胞
            result = await cell.receive_signal({
                'type': 'parse',
                'input': input_data,
                'timestamp': datetime.now().isoformat()
            })
            results.append({
                'cell_id': cell.id,
                'cell_type': cell.cell_type.value,
                'result': result
            })
        
        return {
            'stage': 'perception',
            'success': True,
            'details': results
        }
    
    async def _process_reasoning(self, input_data: Dict) -> Optional[Dict]:
        """推理分析"""
        reasoning_cells = self.get_cells_by_type(CellType.REASONING)
        if not reasoning_cells:
            return None
        
        results = []
        for cell in reasoning_cells[:2]:  # 最多使用2个推理细胞
            result = await cell.receive_signal({
                'type': 'reason',
                'query': input_data,
                'mode': 'deductive',
                'timestamp': datetime.now().isoformat()
            })
            results.append({
                'cell_id': cell.id,
                'cell_type': cell.cell_type.value,
                'result': result
            })
        
        return {
            'stage': 'reasoning',
            'success': True,
            'details': results
        }
    
    async def _process_memory(self, input_data: Dict) -> Optional[Dict]:
        """记忆检索"""
        memory_cells = self.get_cells_by_type(CellType.MEMORY)
        if not memory_cells:
            return None
        
        results = []
        for cell in memory_cells[:2]:  # 最多使用2个记忆细胞
            result = await cell.receive_signal({
                'type': 'retrieve',
                'query': input_data,
                'timestamp': datetime.now().isoformat()
            })
            results.append({
                'cell_id': cell.id,
                'cell_type': cell.cell_type.value,
                'result': result
            })
        
        return {
            'stage': 'memory',
            'success': True,
            'details': results
        }
    
    async def _process_action(self, input_data: Dict) -> Optional[Dict]:
        """行动执行"""
        action_cells = self.get_cells_by_type(CellType.ACTION)
        if not action_cells:
            return None
        
        results = []
        for cell in action_cells[:2]:  # 最多使用2个行动细胞
            result = await cell.receive_signal({
                'type': 'execute',
                'input': input_data,
                'timestamp': datetime.now().isoformat()
            })
            results.append({
                'cell_id': cell.id,
                'cell_type': cell.cell_type.value,
                'result': result
            })
        
        return {
            'stage': 'action',
            'success': True,
            'details': results
        }
    
    def _summarize_results(self, results: List[Dict]) -> str:
        """总结结果"""
        if not results:
            return "未执行任何操作"
        
        stages = [r['stage'] for r in results if r.get('success')]
        success_count = sum(1 for r in results if r.get('success', False))
        
        return f"完成阶段: {', '.join(stages)} | 成功率: {success_count}/{len(results)}"
    
    async def _establish_initial_connections(self):
        """建立初始连接网络"""
        # 获取核心细胞
        perception_cells = self.get_cells_by_type(CellType.PERCEPTION)
        reasoning_cells = self.get_cells_by_type(CellType.REASONING)
        memory_cells = self.get_cells_by_type(CellType.MEMORY)
        action_cells = self.get_cells_by_type(CellType.ACTION)
        
        # 感知 -> 推理
        for p_cell in perception_cells:
            for r_cell in reasoning_cells:
                await self.connect_cells(p_cell.id, r_cell.id, weight=0.7)
        
        # 推理 -> 记忆
        for r_cell in reasoning_cells:
            for m_cell in memory_cells:
                await self.connect_cells(r_cell.id, m_cell.id, weight=0.6)
        
        # 记忆 -> 推理 (双向连接)
        for m_cell in memory_cells:
            for r_cell in reasoning_cells:
                await self.connect_cells(m_cell.id, r_cell.id, weight=0.5)
        
        # 推理 -> 行动
        for r_cell in reasoning_cells:
            for a_cell in action_cells:
                await self.connect_cells(r_cell.id, a_cell.id, weight=0.8)
        
        logger.debug("🔗 初始连接网络已建立")
    
    def get_status(self) -> Dict[str, Any]:
        """获取装配器状态"""
        stats = {}
        for cell_type in CellType:
            cells = self.get_cells_by_type(cell_type)
            stats[cell_type.value] = {
                'count': len(cells),
                'active': sum(1 for c in cells if c.is_active),
                'dormant': sum(1 for c in cells if c.state == CellState.DORMANT),
                'avg_energy': sum(c.energy_level for c in cells) / len(cells) if cells else 0
            }
        
        return {
            'assembler_id': self.id,
            'total_cells': len(self.cells),
            'active_cells': len(self.get_active_cells()),
            'dormant_cells': len(self.get_dormant_cells()),
            'cells_by_type': stats,
            'assembly_strategy': self.assembly_strategy.value
        }
    
    def get_cell_stats(self, cell_id: str) -> Optional[Dict]:
        """获取单个细胞的统计信息"""
        cell = self.cells.get(cell_id)
        if cell:
            return cell.get_stats()
        return None
    
    async def update_cell_connections(self):
        """动态更新细胞连接（Hebbian学习）"""
        for cell in self.cells.values():
            for conn in cell.connections:
                # 根据使用频率调整连接强度
                if conn.signal_count > 10:
                    conn.strengthen(0.05)
                elif conn.signal_count == 0:
                    conn.weaken(0.02)
    
    async def cleanup_dead_cells(self):
        """清理死亡细胞"""
        dead_cells = [cell for cell in self.cells.values() if cell.state == CellState.DEAD]
        
        for cell in dead_cells:
            await self.destroy_cell(cell.id)
        
        if dead_cells:
            logger.info(f"🧹 清理了 {len(dead_cells)} 个死亡细胞")
    
    def __repr__(self):
        return f"<CellAssembler id={self.id} cells={len(self.cells)}>"
    
    def __str__(self):
        return f"CellAssembler[{self.id}] with {len(self.cells)} cells"