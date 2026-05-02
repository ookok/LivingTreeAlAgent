"""
自我再生系统 - SelfRegeneration

实现系统的自我修复和再生能力：
1. 受损组件检测
2. 替代细胞创建
3. 知识迁移
4. 连接替换
5. 自我优化

核心思想：当检测到受损或低效的细胞时，自动创建替代细胞并迁移知识。
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import random


class RegenerationStatus(Enum):
    """再生状态"""
    IDLE = "idle"                 # 空闲
    SCANNING = "scanning"         # 扫描中
    REGENERATING = "regenerating" # 再生中
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败


class DamageLevel(Enum):
    """损伤级别"""
    NONE = "none"                 # 无损伤
    MINOR = "minor"               # 轻微损伤
    MODERATE = "moderate"         # 中度损伤
    SEVERE = "severe"             # 严重损伤
    CRITICAL = "critical"         # 危急


class RegenerationRecord:
    """再生记录"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now()
        self.status = RegenerationStatus.IDLE
        self.damaged_cells = []
        self.regenerated_cells = []
        self.knowledge_transferred = False
        self.success = False
        self.message = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'damaged_cells': self.damaged_cells,
            'regenerated_cells': self.regenerated_cells,
            'knowledge_transferred': self.knowledge_transferred,
            'success': self.success,
            'message': self.message
        }


class SelfRegeneration:
    """
    自我再生系统
    
    负责检测受损组件并进行自我修复。
    """
    
    def __init__(self, scan_interval: float = 60.0):
        self.id = str(uuid.uuid4())[:8]
        self.scan_interval = scan_interval  # 扫描间隔（秒）
        self.regeneration_history: List[RegenerationRecord] = []
        self.status = RegenerationStatus.IDLE
        
        # 损伤检测阈值
        self.damage_thresholds = {
            'energy': 0.2,      # 能量低于20%
            'success_rate': 0.3, # 成功率低于30%
            'errors': 10,        # 错误超过10次
            'response_time': 5.0 # 响应时间超过5秒
        }
    
    async def start_regeneration_loop(self):
        """启动再生循环"""
        while True:
            await self.regenerate()
            await asyncio.sleep(self.scan_interval)
    
    async def regenerate(self) -> Dict[str, Any]:
        """执行自我再生"""
        record = RegenerationRecord()
        record.status = RegenerationStatus.SCANNING
        
        try:
            # 1. 扫描受损组件
            damaged_cells = await self._scan_for_damage()
            record.damaged_cells = [c.id for c in damaged_cells]
            
            if not damaged_cells:
                record.status = RegenerationStatus.COMPLETED
                record.success = True
                record.message = "未检测到受损细胞"
                self.regeneration_history.append(record)
                return record.to_dict()
            
            record.status = RegenerationStatus.REGENERATING
            
            # 2. 对每个受损细胞进行再生
            for cell in damaged_cells:
                await self._regenerate_cell(cell, record)
            
            record.status = RegenerationStatus.COMPLETED
            record.success = True
            record.message = f"成功再生 {len(record.regenerated_cells)} 个细胞"
            
        except Exception as e:
            record.status = RegenerationStatus.FAILED
            record.success = False
            record.message = f"再生失败: {str(e)}"
        
        self.regeneration_history.append(record)
        return record.to_dict()
    
    async def _scan_for_damage(self) -> List['Cell']:
        """扫描受损细胞"""
        from cell_framework import CellRegistry
        
        registry = CellRegistry.get_instance()
        all_cells = registry.get_all_cells()
        damaged_cells = []
        
        for cell in all_cells:
            if self._is_damaged(cell):
                damaged_cells.append(cell)
        
        return damaged_cells
    
    def _is_damaged(self, cell: 'Cell') -> bool:
        """判断细胞是否受损"""
        # 检查能量水平
        if cell.energy_level < self.damage_thresholds['energy']:
            return True
        
        # 检查成功率
        if hasattr(cell, 'success_rate') and cell.success_rate < self.damage_thresholds['success_rate']:
            return True
        
        # 检查错误次数
        if hasattr(cell, 'errors') and cell.errors > self.damage_thresholds['errors']:
            return True
        
        # 检查状态
        if hasattr(cell, 'state') and cell.state.value == 'dead':
            return True
        
        return False
    
    async def _regenerate_cell(self, cell: 'Cell', record: RegenerationRecord):
        """再生单个细胞"""
        try:
            # 1. 创建替代细胞
            replacement = await self._create_replacement(cell)
            
            # 2. 迁移知识
            await self._transfer_knowledge(cell, replacement)
            
            # 3. 替换连接
            await self._replace_connections(cell, replacement)
            
            # 4. 标记旧细胞为死亡
            cell.state = self._get_cell_state_enum()('dead')
            
            record.regenerated_cells.append({
                'old_cell_id': cell.id,
                'new_cell_id': replacement.id,
                'cell_type': cell.cell_type.value
            })
            
            record.knowledge_transferred = True
            
        except Exception as e:
            print(f"❌ 再生细胞失败 {cell.id}: {e}")
    
    async def _create_replacement(self, cell: 'Cell') -> 'Cell':
        """创建替代细胞"""
        from cell_framework import (
            ReasoningCell, MemoryCell, LearningCell,
            PerceptionCell, ActionCell, PredictionCell,
            CellRegistry
        )
        
        cell_map = {
            'reasoning': ReasoningCell,
            'memory': MemoryCell,
            'learning': LearningCell,
            'perception': PerceptionCell,
            'action': ActionCell,
            'prediction': PredictionCell
        }
        
        cell_class = cell_map.get(cell.cell_type.value, ReasoningCell)
        replacement = cell_class()
        
        # 注册新细胞
        registry = CellRegistry.get_instance()
        registry.register_cell(replacement)
        
        return replacement
    
    async def _transfer_knowledge(self, source: 'Cell', target: 'Cell'):
        """迁移知识"""
        # 复制基本属性
        target.specialization = source.specialization
        
        # 迁移记忆
        if hasattr(source, 'memory'):
            target.memory = source.memory.copy()
        
        # 迁移学习参数
        if hasattr(source, 'learning_rate'):
            target.learning_rate = source.learning_rate
        
        # 迁移模型
        if hasattr(source, 'models'):
            target.models = {k: v for k, v in source.models.items()}
        
        await asyncio.sleep(0.05)
    
    async def _replace_connections(self, old_cell: 'Cell', new_cell: 'Cell'):
        """替换连接"""
        from cell_framework import CellRegistry
        
        registry = CellRegistry.get_instance()
        all_cells = registry.get_all_cells()
        
        # 复制旧细胞的连接
        for conn in old_cell.connections:
            target_cell = registry.get_cell(conn.target_cell_id)
            if target_cell:
                new_cell.connect(target_cell, initial_weight=conn.weight)
        
        # 更新其他细胞指向旧细胞的连接
        for cell in all_cells:
            if cell.id == old_cell.id:
                continue
            
            # 检查是否有指向旧细胞的连接
            for conn in cell.connections[:]:
                if conn.target_cell_id == old_cell.id:
                    cell.disconnect(old_cell)
                    cell.connect(new_cell, initial_weight=conn.weight)
    
    def _get_cell_state_enum(self):
        """获取细胞状态枚举"""
        from cell_framework import CellState
        return CellState
    
    def get_regeneration_stats(self) -> Dict[str, Any]:
        """获取再生统计"""
        if not self.regeneration_history:
            return {
                'total_regenerations': 0,
                'success_rate': 0.0,
                'cells_regenerated': 0
            }
        
        successful = sum(1 for r in self.regeneration_history if r.success)
        success_rate = successful / len(self.regeneration_history)
        total_regenerated = sum(len(r.regenerated_cells) for r in self.regeneration_history)
        
        return {
            'total_regenerations': len(self.regeneration_history),
            'success_rate': success_rate,
            'cells_regenerated': total_regenerated,
            'last_regeneration': self.regeneration_history[-1].to_dict() if self.regeneration_history else None
        }
    
    async def emergency_regenerate(self, cell_id: str) -> bool:
        """紧急再生指定细胞"""
        from cell_framework import CellRegistry
        
        registry = CellRegistry.get_instance()
        cell = registry.get_cell(cell_id)
        
        if not cell:
            return False
        
        record = RegenerationRecord()
        record.status = RegenerationStatus.REGENERATING
        record.damaged_cells = [cell_id]
        
        try:
            await self._regenerate_cell(cell, record)
            record.status = RegenerationStatus.COMPLETED
            record.success = True
            record.message = f"紧急再生成功: {cell_id}"
        except Exception as e:
            record.status = RegenerationStatus.FAILED
            record.success = False
            record.message = f"紧急再生失败: {e}"
        
        self.regeneration_history.append(record)
        return record.success
    
    def get_damage_report(self) -> Dict[str, Any]:
        """获取损伤报告"""
        from cell_framework import CellRegistry
        
        registry = CellRegistry.get_instance()
        all_cells = registry.get_all_cells()
        
        damage_report = {
            'total_cells': len(all_cells),
            'damaged_cells': [],
            'healthy_cells': [],
            'damage_summary': {}
        }
        
        for cell in all_cells:
            if self._is_damaged(cell):
                damage_report['damaged_cells'].append({
                    'id': cell.id,
                    'type': cell.cell_type.value,
                    'energy': cell.energy_level,
                    'success_rate': getattr(cell, 'success_rate', 1.0),
                    'errors': getattr(cell, 'errors', 0)
                })
            else:
                damage_report['healthy_cells'].append(cell.id)
        
        damage_report['damage_summary'] = {
            'damaged_count': len(damage_report['damaged_cells']),
            'healthy_count': len(damage_report['healthy_cells']),
            'damage_ratio': len(damage_report['damaged_cells']) / max(len(all_cells), 1)
        }
        
        return damage_report