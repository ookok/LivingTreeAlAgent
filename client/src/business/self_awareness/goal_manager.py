"""
目标管理模块 - Goal Management

功能：
1. 目标设置
2. 目标追踪
3. 优先级管理
4. 进度更新
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """目标"""
    goal_id: str
    description: str
    priority: float  # 0-1
    progress: float = 0.0
    created_at: float = None
    deadline: Optional[float] = None
    status: str = "active"  # active/completed/canceled
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class GoalManager:
    """
    目标管理器 - 管理系统目标
    
    核心功能：
    1. 设置目标
    2. 更新进度
    3. 优先级排序
    4. 目标完成追踪
    """
    
    def __init__(self, storage_path: str = "data/awareness/goals"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._goals: Dict[str, Goal] = {}
        self._load_goals()
    
    def set_goal(self, description: str, priority: float = 0.5, 
                deadline: Optional[float] = None) -> str:
        """
        设置目标
        
        Args:
            description: 目标描述
            priority: 优先级 (0-1)
            deadline: 截止时间戳
        
        Returns:
            目标ID
        """
        import uuid
        
        goal_id = str(uuid.uuid4())
        
        goal = Goal(
            goal_id=goal_id,
            description=description,
            priority=priority,
            deadline=deadline
        )
        
        self._goals[goal_id] = goal
        self._save_goal(goal)
        
        logger.info(f"设置目标: {description}")
        return goal_id
    
    def update_goal_progress(self, goal_id: str, progress: float):
        """更新目标进度"""
        if goal_id in self._goals:
            self._goals[goal_id].progress = min(1.0, max(0.0, progress))
            
            # 检查是否完成
            if self._goals[goal_id].progress >= 1.0:
                self._goals[goal_id].status = "completed"
            
            self._save_goal(self._goals[goal_id])
    
    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """获取目标"""
        return self._goals.get(goal_id)
    
    def get_all_goals(self) -> List[Dict]:
        """获取所有目标"""
        goals = list(self._goals.values())
        goals.sort(key=lambda g: (-g.priority, g.created_at))
        
        return [
            {
                'goal_id': goal.goal_id,
                'description': goal.description,
                'priority': goal.priority,
                'progress': goal.progress,
                'status': goal.status,
                'created_at': goal.created_at,
                'deadline': goal.deadline,
                'age_hours': (time.time() - goal.created_at) / 3600
            }
            for goal in goals
        ]
    
    def get_active_goals(self) -> List[Dict]:
        """获取活跃目标"""
        return [g for g in self.get_all_goals() if g['status'] == 'active']
    
    def complete_goal(self, goal_id: str):
        """标记目标完成"""
        if goal_id in self._goals:
            self._goals[goal_id].progress = 1.0
            self._goals[goal_id].status = "completed"
            self._save_goal(self._goals[goal_id])
            logger.info(f"完成目标: {self._goals[goal_id].description}")
    
    def cancel_goal(self, goal_id: str):
        """取消目标"""
        if goal_id in self._goals:
            self._goals[goal_id].status = "canceled"
            self._save_goal(self._goals[goal_id])
            logger.info(f"取消目标: {self._goals[goal_id].description}")
    
    def delete_goal(self, goal_id: str) -> bool:
        """删除目标"""
        if goal_id in self._goals:
            del self._goals[goal_id]
            
            # 删除文件
            file_path = self.storage_path / f"{goal_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            logger.info(f"删除目标: {goal_id}")
            return True
        
        return False
    
    def get_prioritized_goals(self, limit: int = 5) -> List[Dict]:
        """获取优先级最高的目标"""
        goals = self.get_active_goals()
        goals.sort(key=lambda g: (-g['priority'], g.get('deadline', float('inf'))))
        return goals[:limit]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        all_goals = self.get_all_goals()
        active = [g for g in all_goals if g['status'] == 'active']
        completed = [g for g in all_goals if g['status'] == 'completed']
        
        avg_progress = sum(g['progress'] for g in active) / len(active) if active else 0
        
        return {
            'total_goals': len(all_goals),
            'active_goals': len(active),
            'completed_goals': len(completed),
            'completion_rate': len(completed) / len(all_goals) if all_goals else 0,
            'avg_progress': avg_progress
        }
    
    def _save_goal(self, goal: Goal):
        """保存目标"""
        data = {
            'goal_id': goal.goal_id,
            'description': goal.description,
            'priority': goal.priority,
            'progress': goal.progress,
            'created_at': goal.created_at,
            'deadline': goal.deadline,
            'status': goal.status
        }
        
        file_path = self.storage_path / f"{goal.goal_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_goals(self):
        """加载目标"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._goals[data['goal_id']] = Goal(**data)
            except Exception as e:
                logger.error(f"加载目标失败: {e}")