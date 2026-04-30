"""
Proactive Agent - 主动式智能体

实现 DD-MM-PAS 范式中的 Proactive Agent System 组件。

根据检测到的需求，主动执行行动。
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import asyncio


@dataclass
class ProactiveAction:
    """主动行为"""
    action_id: str
    action_type: str  # 行为类型
    description: str  # 行为描述
    confidence: float  # 置信度
    priority: int  # 优先级 (1-10)
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    succeeded: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "confidence": self.confidence,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "succeeded": self.succeeded,
            "metadata": self.metadata
        }


class ProactiveAgent:
    """主动式智能体"""
    
    def __init__(self):
        self._pending_actions: List[ProactiveAction] = []
        self._executed_actions: List[ProactiveAction] = []
        self._last_action_time: Optional[datetime] = None
        self._min_interval = timedelta(seconds=30)
        self._confidence_threshold = 0.8
        self._max_actions_per_session = 5
        self._logger = logger.bind(component="ProactiveAgent")
        
        # 行为类型定义
        self._action_types = {
            "suggestion": {
                "description": "提供建议",
                "priority": 3
            },
            "information": {
                "description": "提供信息",
                "priority": 4
            },
            "reminder": {
                "description": "发送提醒",
                "priority": 7
            },
            "task": {
                "description": "执行任务",
                "priority": 8
            },
            "follow_up": {
                "description": "跟进询问",
                "priority": 2
            },
            "resource": {
                "description": "提供资源",
                "priority": 5
            }
        }
    
    async def generate_actions(self, latent_needs: List[Dict[str, Any]]) -> List[ProactiveAction]:
        """
        根据潜在需求生成主动行为
        
        Args:
            latent_needs: 潜在需求列表
            
        Returns:
            生成的主动行为列表
        """
        actions = []
        
        for need in latent_needs:
            need_id = need.get("need_id", "")
            description = need.get("description", "")
            priority = need.get("priority", 0.5)
            
            # 根据需求类型生成行为
            if "信息解答" in description:
                actions.append(self._create_action(
                    action_type="information",
                    description=f"根据您的问题，我可以提供相关信息和解答",
                    confidence=min(1.0, priority * 0.9),
                    priority=4
                ))
            
            elif "任务管理" in description:
                actions.append(self._create_action(
                    action_type="task",
                    description=f"我可以帮您管理和追踪这些任务",
                    confidence=min(1.0, priority * 0.85),
                    priority=8
                ))
            
            elif "日程管理" in description:
                actions.append(self._create_action(
                    action_type="task",
                    description=f"我可以帮您安排日程和会议",
                    confidence=min(1.0, priority * 0.9),
                    priority=8
                ))
            
            elif "技术支持" in description:
                actions.append(self._create_action(
                    action_type="suggestion",
                    description=f"我注意到您遇到了一些问题，需要帮助排查吗？",
                    confidence=min(1.0, priority * 0.95),
                    priority=7
                ))
            
            elif "学习" in description:
                actions.append(self._create_action(
                    action_type="resource",
                    description=f"我可以推荐相关的学习资源和教程",
                    confidence=min(1.0, priority * 0.8),
                    priority=5
                ))
        
        # 过滤低置信度行为
        actions = [a for a in actions if a.confidence >= self._confidence_threshold]
        
        # 添加到待执行队列
        self._pending_actions.extend(actions)
        self._pending_actions.sort(key=lambda x: (-x.priority, -x.confidence))
        
        # 限制队列大小
        self._pending_actions = self._pending_actions[:self._max_actions_per_session]
        
        return actions
    
    async def execute_next_action(self) -> Optional[ProactiveAction]:
        """
        执行下一个主动行为
        
        Returns:
            执行的行为（如果有的话）
        """
        # 检查时间间隔
        if self._last_action_time:
            elapsed = datetime.now() - self._last_action_time
            if elapsed < self._min_interval:
                self._logger.debug(f"距离上次行为不足 {self._min_interval.total_seconds()} 秒")
                return None
        
        # 检查是否有待执行行为
        if not self._pending_actions:
            return None
        
        # 获取最高优先级行为
        action = self._pending_actions.pop(0)
        
        try:
            # 执行行为
            await self._execute_action(action)
            
            # 更新状态
            action.executed_at = datetime.now()
            action.succeeded = True
            self._last_action_time = datetime.now()
            
            # 移到已执行列表
            self._executed_actions.append(action)
            
            self._logger.info(f"执行主动行为: {action.action_type} - {action.description}")
            
            return action
            
        except Exception as e:
            action.executed_at = datetime.now()
            action.succeeded = False
            self._executed_actions.append(action)
            
            self._logger.error(f"执行主动行为失败: {e}")
            return None
    
    async def _execute_action(self, action: ProactiveAction):
        """
        执行单个行为
        
        Args:
            action: 要执行的行为
        """
        # 模拟执行延迟
        await asyncio.sleep(0.5)
        
        # 根据行为类型执行不同操作
        if action.action_type == "suggestion":
            self._logger.debug(f"提供建议: {action.description}")
        elif action.action_type == "information":
            self._logger.debug(f"提供信息: {action.description}")
        elif action.action_type == "reminder":
            self._logger.debug(f"发送提醒: {action.description}")
        elif action.action_type == "task":
            self._logger.debug(f"执行任务: {action.description}")
        elif action.action_type == "follow_up":
            self._logger.debug(f"跟进询问: {action.description}")
        elif action.action_type == "resource":
            self._logger.debug(f"提供资源: {action.description}")
    
    def get_pending_actions(self) -> List[ProactiveAction]:
        """获取待执行行为列表"""
        return self._pending_actions
    
    def get_executed_actions(self) -> List[ProactiveAction]:
        """获取已执行行为列表"""
        return self._executed_actions
    
    def clear_actions(self):
        """清除所有行为"""
        self._pending_actions.clear()
        self._executed_actions.clear()
        self._logger.debug("行为队列已清除")
    
    def set_min_interval(self, seconds: int):
        """设置行为间隔"""
        self._min_interval = timedelta(seconds=seconds)
    
    def set_confidence_threshold(self, threshold: float):
        """设置置信度阈值"""
        self._confidence_threshold = threshold
    
    def set_max_actions_per_session(self, max_count: int):
        """设置每会话最大行为数"""
        self._max_actions_per_session = max_count
    
    def _create_action(self, action_type: str, description: str, 
                       confidence: float, priority: int) -> ProactiveAction:
        """创建行为对象"""
        import uuid
        return ProactiveAction(
            action_id=f"action_{uuid.uuid4()[:8]}",
            action_type=action_type,
            description=description,
            confidence=confidence,
            priority=priority,
            metadata={"type_info": self._action_types.get(action_type, {})}
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "pending_actions": len(self._pending_actions),
            "executed_actions": len(self._executed_actions),
            "last_action_time": self._last_action_time.isoformat() if self._last_action_time else None,
            "confidence_threshold": self._confidence_threshold,
            "min_interval_seconds": self._min_interval.total_seconds(),
            "max_actions_per_session": self._max_actions_per_session
        }