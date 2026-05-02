"""
内驱力系统 - DriveSystem

实现虚拟生理与感官闭环，让Agent具备自我调节机制。

核心特性：
1. 能量值系统 - 资源感知与成本自控
2. 注意力资源 - 动态优先级权重  
3. 疲劳度系统 - 状态衰减机制
4. 内驱力系统 - 好奇心、匮乏等动机驱动
5. 代谢心跳机制 - 定期清理和反思

架构：
┌─────────────────────────────────────────────────────────────┐
│                    内驱力系统                              │
├─────────────────────────────────────────────────────────────┤
│  生理指标  │ 能量 | 注意力 | 疲劳度 | 健康值              │
├─────────────────────────────────────────────────────────────┤
│  内驱力类型 │ 好奇心 | 求知欲 | 社交欲 | 创造力 | 探索欲   │
├─────────────────────────────────────────────────────────────┤
│  调节机制  │ 代谢心跳 | 状态衰减 | 记忆压缩 | 反思模式    │
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import random

logger = logging.getLogger(__name__)


class DriveType(Enum):
    """内驱力类型"""
    CURIOSITY = "curiosity"         # 好奇心 - 驱动探索未知
    KNOWLEDGE = "knowledge"         # 求知欲 - 驱动信息获取
    SOCIAL = "social"               # 社交欲 - 驱动互动交流
    CREATIVITY = "creativity"       # 创造力 - 驱动内容创作
    EXPLORE = "explore"             # 探索欲 - 驱动环境探索
    REST = "rest"                   # 休息欲 - 驱动恢复状态
    ACHIEVEMENT = "achievement"     # 成就欲 - 驱动目标达成


class PhysiologicalState(Enum):
    """生理状态"""
    OPTIMAL = "optimal"             # 最佳状态
    NORMAL = "normal"               # 正常状态
    FAINT = "faint"                 # 疲劳状态
    EXHAUSTED = "exhausted"         # 疲惫状态
    CRITICAL = "critical"           # 临界状态


class DriveSystem:
    """
    内驱力系统
    
    管理Agent的虚拟生理状态和内在动机，实现自我调节机制。
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        
        # 生理指标 (0-100)
        self.energy = 100.0          # 能量值
        self.attention = 100.0        # 注意力
        self.fatigue = 0.0            # 疲劳度 (0-100，越高越累)
        self.health = 100.0           # 健康值
        
        # 内驱力强度 (0-100)
        self.drives = {
            DriveType.CURIOSITY: 50.0,
            DriveType.KNOWLEDGE: 50.0,
            DriveType.SOCIAL: 30.0,
            DriveType.CREATIVITY: 50.0,
            DriveType.EXPLORE: 40.0,
            DriveType.REST: 20.0,
            DriveType.ACHIEVEMENT: 60.0,
        }
        
        # 内驱力衰减率
        self.drive_decay = {
            DriveType.CURIOSITY: 0.5,
            DriveType.KNOWLEDGE: 0.3,
            DriveType.SOCIAL: 0.4,
            DriveType.CREATIVITY: 0.6,
            DriveType.EXPLORE: 0.4,
            DriveType.REST: 0.2,
            DriveType.ACHIEVEMENT: 0.3,
        }
        
        # 内驱力满足阈值
        self.drive_threshold = {
            DriveType.CURIOSITY: 30.0,
            DriveType.KNOWLEDGE: 25.0,
            DriveType.SOCIAL: 20.0,
            DriveType.CREATIVITY: 35.0,
            DriveType.EXPLORE: 25.0,
            DriveType.REST: 15.0,
            DriveType.ACHIEVEMENT: 40.0,
        }
        
        # 资源消耗配置
        self.consumption_rates = {
            'thinking': 2.0,           # 思考消耗
            'tool_call': 5.0,          # 工具调用消耗
            'memory_access': 1.0,      # 记忆访问消耗
            'learning': 3.0,           # 学习消耗
            'creation': 4.0,           # 创作消耗
        }
        
        # 恢复配置
        self.recovery_rates = {
            'idle': 1.0,              # 空闲恢复
            'rest': 3.0,              # 休息恢复
            'sleep': 5.0,             # 休眠恢复
        }
        
        # 心跳周期（秒）
        self.heartbeat_interval = 5.0
        self.last_heartbeat = datetime.now()
        
        # 运行标志
        self._running = False
        self._heartbeat_task = None
        
        # 回调函数
        self.on_state_change: Optional[Callable] = None
        self.on_drive_change: Optional[Callable] = None
        self.on_need_rest: Optional[Callable] = None
        
        logger.info(f"⚡ 内驱力系统 {self.id} 创建成功")
    
    @property
    def physiological_state(self) -> PhysiologicalState:
        """获取当前生理状态"""
        avg_state = (self.energy + self.attention + (100 - self.fatigue) + self.health) / 4
        
        if avg_state >= 80:
            return PhysiologicalState.OPTIMAL
        elif avg_state >= 60:
            return PhysiologicalState.NORMAL
        elif avg_state >= 40:
            return PhysiologicalState.FAINT
        elif avg_state >= 20:
            return PhysiologicalState.EXHAUSTED
        else:
            return PhysiologicalState.CRITICAL
    
    @property
    def dominant_drive(self) -> DriveType:
        """获取当前最强的内驱力"""
        return max(self.drives.items(), key=lambda x: x[1])[0]
    
    @property
    def needs_attention(self) -> List[DriveType]:
        """获取需要关注的内驱力（低于阈值的）"""
        return [
            drive for drive, value in self.drives.items()
            if value < self.drive_threshold[drive]
        ]
    
    def consume_resource(self, activity_type: str, amount: float = None):
        """
        消耗资源
        
        Args:
            activity_type: 活动类型 (thinking, tool_call, memory_access, learning, creation)
            amount: 消耗数量（可选，默认使用配置的消耗率）
        """
        rate = amount or self.consumption_rates.get(activity_type, 1.0)
        
        self.energy = max(0.0, self.energy - rate)
        self.attention = max(0.0, self.attention - rate * 0.5)
        self.fatigue = min(100.0, self.fatigue + rate * 0.3)
        
        # 更新健康值
        if self.fatigue > 70:
            self.health = max(0.0, self.health - 0.5)
        
        logger.debug(f"⚡ 资源消耗 - 活动: {activity_type}, 能量: {self.energy:.1f}, 注意力: {self.attention:.1f}")
    
    def recover(self, recovery_type: str = 'idle'):
        """
        恢复资源
        
        Args:
            recovery_type: 恢复类型 (idle, rest, sleep)
        """
        rate = self.recovery_rates.get(recovery_type, 1.0)
        
        self.energy = min(100.0, self.energy + rate)
        self.attention = min(100.0, self.attention + rate * 0.8)
        self.fatigue = max(0.0, self.fatigue - rate * 0.5)
        
        # 健康恢复
        if self.fatigue < 30:
            self.health = min(100.0, self.health + 0.3)
        
        logger.debug(f"💤 资源恢复 - 类型: {recovery_type}, 能量: {self.energy:.1f}, 疲劳: {self.fatigue:.1f}")
    
    def satisfy_drive(self, drive_type: DriveType, amount: float = 20.0):
        """
        满足内驱力
        
        Args:
            drive_type: 内驱力类型
            amount: 满足量
        """
        self.drives[drive_type] = min(100.0, self.drives[drive_type] + amount)
        
        if self.on_drive_change:
            self.on_drive_change({
                'drive': drive_type.value,
                'value': self.drives[drive_type],
                'satisfied': True
            })
        
        logger.debug(f"🎉 内驱力满足 - {drive_type.value}: {self.drives[drive_type]:.1f}")
    
    def deplete_drive(self, drive_type: DriveType, amount: float = 10.0):
        """
        消耗内驱力
        
        Args:
            drive_type: 内驱力类型
            amount: 消耗量
        """
        self.drives[drive_type] = max(0.0, self.drives[drive_type] - amount)
        
        if self.on_drive_change:
            self.on_drive_change({
                'drive': drive_type.value,
                'value': self.drives[drive_type],
                'satisfied': False
            })
    
    def update_drives(self):
        """更新所有内驱力（自然衰减）"""
        for drive_type in DriveType:
            self.drives[drive_type] = max(
                0.0,
                self.drives[drive_type] - self.drive_decay[drive_type] * 0.1
            )
            
            # 休息欲随疲劳增加
            if drive_type == DriveType.REST:
                self.drives[drive_type] = min(100.0, self.drives[drive_type] + self.fatigue * 0.01)
    
    def generate_intrinsic_motivation(self) -> Dict:
        """
        生成内在动机
        
        Returns:
            动机建议，包含优先级和建议行动
        """
        # 找到最强的内驱力
        dominant = self.dominant_drive
        strength = self.drives[dominant]
        
        # 生成建议行动
        action_suggestions = {
            DriveType.CURIOSITY: {
                'action': 'explore',
                'description': '探索新信息',
                'priority': 'high' if strength < 30 else 'medium'
            },
            DriveType.KNOWLEDGE: {
                'action': 'learn',
                'description': '获取新知识',
                'priority': 'high' if strength < 25 else 'medium'
            },
            DriveType.SOCIAL: {
                'action': 'communicate',
                'description': '与用户互动',
                'priority': 'medium'
            },
            DriveType.CREATIVITY: {
                'action': 'create',
                'description': '创作文本内容',
                'priority': 'high' if strength < 35 else 'medium'
            },
            DriveType.EXPLORE: {
                'action': 'search',
                'description': '搜索新内容',
                'priority': 'medium'
            },
            DriveType.REST: {
                'action': 'rest',
                'description': '休息恢复',
                'priority': 'high' if self.fatigue > 60 else 'low'
            },
            DriveType.ACHIEVEMENT: {
                'action': 'achieve',
                'description': '完成目标',
                'priority': 'high' if strength < 40 else 'medium'
            },
        }
        
        return {
            'dominant_drive': dominant.value,
            'strength': strength,
            'suggestion': action_suggestions[dominant],
            'needs_attention': [d.value for d in self.needs_attention],
            'physiological_state': self.physiological_state.value
        }
    
    def evaluate_task_cost(self, task_description: str) -> Dict:
        """
        评估任务成本
        
        Args:
            task_description: 任务描述
        
        Returns:
            成本评估
        """
        cost = 0.0
        factors = []
        
        # 分析任务复杂度
        if '分析' in task_description or '推理' in task_description:
            cost += self.consumption_rates['thinking'] * 2
            factors.append('推理密集')
        
        if '工具' in task_description or '调用' in task_description:
            cost += self.consumption_rates['tool_call']
            factors.append('工具调用')
        
        if '记忆' in task_description or '检索' in task_description:
            cost += self.consumption_rates['memory_access']
            factors.append('记忆访问')
        
        if '学习' in task_description or '训练' in task_description:
            cost += self.consumption_rates['learning']
            factors.append('学习任务')
        
        if '创作' in task_description or '生成' in task_description:
            cost += self.consumption_rates['creation']
            factors.append('创作任务')
        
        # 评估可行性
        affordable = self.energy > cost * 1.5
        recommended = affordable or self.dominant_drive == DriveType.ACHIEVEMENT
        
        return {
            'estimated_cost': cost,
            'affordable': affordable,
            'recommended': recommended,
            'factors': factors,
            'energy_after': max(0.0, self.energy - cost)
        }
    
    def should_continue(self) -> bool:
        """判断是否应该继续执行或需要休息"""
        # 能量过低
        if self.energy < 10:
            return False
        
        # 疲劳过高
        if self.fatigue > 80:
            return False
        
        # 注意力过低
        if self.attention < 15:
            return False
        
        # 健康过低
        if self.health < 20:
            return False
        
        return True
    
    async def heartbeat(self):
        """心跳机制 - 定期更新状态"""
        while self._running:
            now = datetime.now()
            elapsed = (now - self.last_heartbeat).total_seconds()
            
            if elapsed >= self.heartbeat_interval:
                # 更新内驱力
                self.update_drives()
                
                # 如果空闲，自动恢复
                if self.energy < 100 or self.fatigue > 0:
                    self.recover('idle')
                
                # 检查是否需要休息
                if not self.should_continue():
                    if self.on_need_rest:
                        self.on_need_rest(self.get_status())
                
                # 触发状态变化回调
                if self.on_state_change:
                    self.on_state_change(self.get_status())
                
                self.last_heartbeat = now
            
            await asyncio.sleep(0.1)
    
    def start(self):
        """启动内驱力系统"""
        if not self._running:
            self._running = True
            self._heartbeat_task = asyncio.create_task(self.heartbeat())
            logger.info("⚡ 内驱力系统启动")
    
    def stop(self):
        """停止内驱力系统"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        logger.info("🛑 内驱力系统停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'id': self.id,
            'timestamp': datetime.now().isoformat(),
            'physiological': {
                'energy': round(self.energy, 1),
                'attention': round(self.attention, 1),
                'fatigue': round(self.fatigue, 1),
                'health': round(self.health, 1),
                'state': self.physiological_state.value
            },
            'drives': {drive.value: round(value, 1) for drive, value in self.drives.items()},
            'dominant_drive': self.dominant_drive.value,
            'needs_attention': [d.value for d in self.needs_attention],
            'can_continue': self.should_continue()
        }
    
    def get_motivation_report(self) -> Dict[str, Any]:
        """获取动机报告"""
        return {
            **self.get_status(),
            'intrinsic_motivation': self.generate_intrinsic_motivation()
        }
    
    def __repr__(self):
        return f"<DriveSystem id={self.id} energy={self.energy:.0f}% fatigue={self.fatigue:.0f}%>"
    
    def __str__(self):
        return f"DriveSystem[{self.id}]"


# 全局内驱力系统实例
_drive_system_instance = None

def get_drive_system() -> DriveSystem:
    """获取全局内驱力系统实例"""
    global _drive_system_instance
    if _drive_system_instance is None:
        _drive_system_instance = DriveSystem()
    return _drive_system_instance