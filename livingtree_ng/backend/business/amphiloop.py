"""
AmphiLoop 双向循环调度 - 迁移自原系统
"""

import uuid
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    FULL = "full"
    STEP = "step"
    SKILL = "skill"
    STABLE = "stable"


@dataclass
class Checkpoint:
    checkpoint_id: str
    task_id: str
    state: Dict[str, Any]
    timestamp: float
    parent_id: Optional[str] = None


@dataclass
class Task:
    task_id: str
    name: str
    status: str = "pending"
    current_step: int = 0
    total_steps: int = 0
    checkpoints: List[Checkpoint] = None
    created_at: float = None
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.checkpoints is None:
            self.checkpoints = []


class AmphiLoopEngine:
    """
    双向循环调度引擎
    """
    
    def __init__(self, storage_path: str = "data/amphiloop"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._tasks: Dict[str, Task] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._load_tasks()
    
    def create_task(self, name: str, total_steps: int = 0) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            name=name,
            total_steps=total_steps
        )
        self._tasks[task_id] = task
        self._save_task(task)
        logger.info(f"Created task: {name}")
        return task_id
    
    def create_checkpoint(
        self,
        task_id: str,
        state: Dict[str, Any],
        parent_id: Optional[str] = None
    ) -> str:
        """创建检查点"""
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")
        
        checkpoint_id = str(uuid.uuid4())
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            state=state,
            timestamp=time.time(),
            parent_id=parent_id
        )
        
        self._checkpoints[checkpoint_id] = checkpoint
        self._tasks[task_id].checkpoints.append(checkpoint)
        self._save_checkpoint(checkpoint)
        logger.debug(f"Created checkpoint: {checkpoint_id}")
        
        return checkpoint_id
    
    def rollback_to(
        self,
        task_id: str,
        checkpoint_id: Optional[str] = None,
        strategy: RollbackStrategy = RollbackStrategy.STEP
    ) -> Optional[Dict[str, Any]]:
        """回滚到检查点"""
        if task_id not in self._tasks:
            return None
        
        task = self._tasks[task_id]
        
        if checkpoint_id:
            if checkpoint_id not in self._checkpoints:
                return None
            target_checkpoint = self._checkpoints[checkpoint_id]
        else:
            if not task.checkpoints:
                return None
            target_checkpoint = task.checkpoints[-1]
        
        logger.info(f"Rolling back {task_id} to {target_checkpoint.checkpoint_id}")
        task.status = "rolling_back"
        task.current_step = target_checkpoint.state.get("step", 0)
        
        return target_checkpoint.state
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """获取最新检查点"""
        if task_id not in self._tasks:
            return None
        
        task = self._tasks[task_id]
        if not task.checkpoints:
            return None
        
        return task.checkpoints[-1]
    
    def update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        if task_id not in self._tasks:
            return
        
        self._tasks[task_id].status = status
        if status == "completed":
            self._tasks[task_id].completed_at = time.time()
        
        self._save_task(self._tasks[task_id])
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_optimization_suggestions(self, task_id: str) -> List[Dict[str, Any]]:
        """获取优化建议（简化版）"""
        suggestions = [
            {
                "type": "checkpoint_frequency",
                "suggestion": "建议增加检查点频率以提高容错能力",
                "priority": "medium"
            },
            {
                "type": "step_parallelization",
                "suggestion": "部分步骤可以并行执行以提高效率",
                "priority": "low"
            }
        ]
        return suggestions
    
    def _save_task(self, task: Task):
        """保存任务"""
        data = asdict(task)
        file_path = self.storage_path / f"{task.task_id}.json"
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _save_checkpoint(self, checkpoint: Checkpoint):
        """保存检查点"""
        data = asdict(checkpoint)
        file_path = self.storage_path / f"checkpoint_{checkpoint.checkpoint_id}.json"
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_tasks(self):
        """加载任务"""
        import json
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            if file_path.name.startswith("checkpoint_"):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                task = Task(**data)
                self._tasks[task.task_id] = task
            except Exception as e:
                logger.error(f"Load task error: {e}")
        
        # 加载检查点
        for file_path in self.storage_path.glob("checkpoint_*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                checkpoint = Checkpoint(**data)
                self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            except Exception as e:
                logger.error(f"Load checkpoint error: {e}")


# 全局单例
_amphi_loop_instance: Optional[AmphiLoopEngine] = None


def get_amphi_loop_engine() -> AmphiLoopEngine:
    """获取AmphiLoop引擎单例"""
    global _amphi_loop_instance
    if _amphi_loop_instance is None:
        _amphi_loop_instance = AmphiLoopEngine()
    return _amphi_loop_instance
