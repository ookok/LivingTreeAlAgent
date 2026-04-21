"""
Fault Tolerance System - Checkpoint Manager
强容错分布式任务处理系统 - 检查点管理器

实现多种检查点策略，支持增量、差异检查点
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import asdict
from threading import Lock

from .models import (
    Task, TaskStatus, Checkpoint, CheckpointType,
    SchedulerConfig
)


logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    检查点管理器
    
    支持:
    - 完整检查点
    - 增量检查点
    - 差异检查点
    - 内存/磁盘快照
    - 自动清理过期检查点
    """
    
    def __init__(self, config: Optional[SchedulerConfig] = None):
        self.config = config or SchedulerConfig()
        
        # 存储配置
        self._storage_dir = Path(tempfile.gettempdir()) / "hermes_checkpoints"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查点缓存
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._task_checkpoints: Dict[str, List[str]] = {}  # task_id -> checkpoint_ids
        
        # 检查点处理器
        self._serializers: Dict[str, Callable] = {
            'json': self._serialize_json,
            'pickle': self._serialize_pickle,
            'custom': self._serialize_custom,
        }
        
        # 锁
        self._lock = Lock()
        
        # 统计
        self.total_checkpoints = 0
        self.total_recoveries = 0
        self.total_storage_bytes = 0
        
        # 自动清理
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    # ==================== 公共API ====================
    
    def set_storage_dir(self, directory: str) -> None:
        """设置存储目录"""
        self._storage_dir = Path(directory)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Checkpoint storage set to: {self._storage_dir}")
    
    async def start(self) -> None:
        """启动管理器"""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Checkpoint manager started")
    
    async def stop(self) -> None:
        """停止管理器"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Checkpoint manager stopped")
    
    def create_checkpoint(self, task: Task, 
                         checkpoint_type: CheckpointType = CheckpointType.INCREMENTAL,
                         custom_state: Optional[Dict[str, Any]] = None) -> Checkpoint:
        """
        创建检查点
        
        Args:
            task: 任务对象
            checkpoint_type: 检查点类型
            custom_state: 自定义状态数据
            
        Returns:
            Checkpoint: 检查点对象
        """
        checkpoint_id = str(uuid.uuid4())
        
        # 构建检查点状态
        state_data = custom_state or {
            'task_id': task.task_id,
            'status': task.status.value,
            'progress': task.progress,
            'retry_count': task.retry_count,
            'assigned_node': task.assigned_node,
            'payload': task.payload,
            'result': task.result,
            'error_message': task.error_message,
            'fault_history': task.fault_history,
        }
        
        # 获取父检查点
        parent_id = None
        if checkpoint_type == CheckpointType.INCREMENTAL:
            task_checkpoints = self._task_checkpoints.get(task.task_id, [])
            if task_checkpoints:
                parent_id = task_checkpoints[-1]
        
        # 创建检查点对象
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            checkpoint_type=checkpoint_type,
            task_id=task.task_id,
            node_id=task.assigned_node or "unknown",
            state_data=state_data,
            parent_checkpoint_id=parent_id,
            sequence_number=len(self._task_checkpoints.get(task.task_id, [])) + 1,
            created_at=datetime.now(),
        )
        
        # 计算状态大小
        checkpoint.state_size = len(json.dumps(state_data).encode('utf-8'))
        
        # 保存检查点
        self._save_checkpoint(checkpoint)
        
        with self._lock:
            self._checkpoints[checkpoint_id] = checkpoint
            if task.task_id not in self._task_checkpoints:
                self._task_checkpoints[task.task_id] = []
            self._task_checkpoints[task.task_id].append(checkpoint_id)
            
            self.total_checkpoints += 1
            self.total_storage_bytes += checkpoint.state_size
        
        logger.debug(f"Checkpoint created: {checkpoint_id} for task {task.task_id}")
        return checkpoint
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点"""
        with self._lock:
            return self._checkpoints.get(checkpoint_id)
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """获取任务最新检查点"""
        with self._lock:
            checkpoint_ids = self._task_checkpoints.get(task_id, [])
            if not checkpoint_ids:
                return None
            return self._checkpoints.get(checkpoint_ids[-1])
    
    def get_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """获取任务所有检查点"""
        with self._lock:
            checkpoint_ids = self._task_checkpoints.get(task_id, [])
            return [
                self._checkpoints[cid] 
                for cid in checkpoint_ids 
                if cid in self._checkpoints
            ]
    
    def recover_state(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        从检查点恢复状态
        
        对于增量检查点，需要重建完整状态
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return None
        
        # 如果是增量检查点，需要合并所有增量
        if checkpoint.checkpoint_type == CheckpointType.INCREMENTAL:
            return self._reconstruct_incremental_state(checkpoint)
        else:
            return checkpoint.state_data
    
    def _reconstruct_incremental_state(self, checkpoint: Checkpoint) -> Dict[str, Any]:
        """重建增量检查点的完整状态"""
        # 收集所有相关检查点
        checkpoints_to_merge = []
        current = checkpoint
        
        while current:
            checkpoints_to_merge.insert(0, current)
            if current.parent_checkpoint_id:
                current = self._checkpoints.get(current.parent_checkpoint_id)
            else:
                break
        
        # 合并状态
        merged_state = {}
        for cp in checkpoints_to_merge:
            merged_state.update(cp.state_data)
        
        return merged_state
    
    def recover_task(self, checkpoint_id: str) -> Optional[Task]:
        """
        从检查点恢复任务
        
        Returns:
            Task: 恢复后的任务对象(未完成部分)
        """
        state = self.recover_state(checkpoint_id)
        if not state:
            return None
        
        # 重建任务
        task = Task(
            task_id=state.get('task_id', str(uuid.uuid4())),
            status=TaskStatus.PENDING,  # 恢复后重新调度
            payload=state.get('payload', {}),
        )
        
        # 恢复其他状态
        task.progress = state.get('progress', 0)
        task.retry_count = state.get('retry_count', 0) + 1  # 增加重试计数
        
        self.total_recoveries += 1
        logger.info(f"Task recovered from checkpoint: {task.task_id}")
        
        return task
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除检查点"""
        with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                return False
            
            # 删除文件
            self._delete_checkpoint_file(checkpoint)
            
            # 从索引移除
            del self._checkpoints[checkpoint_id]
            
            # 从任务检查点列表移除
            task_id = checkpoint.task_id
            if task_id in self._task_checkpoints:
                try:
                    self._task_checkpoints[task_id].remove(checkpoint_id)
                except ValueError:
                    pass
            
            self.total_storage_bytes -= checkpoint.state_size
        
        logger.debug(f"Checkpoint deleted: {checkpoint_id}")
        return True
    
    def delete_task_checkpoints(self, task_id: str) -> int:
        """删除任务所有检查点"""
        with self._lock:
            checkpoint_ids = self._task_checkpoints.get(task_id, [])
            count = 0
            
            for cp_id in checkpoint_ids:
                checkpoint = self._checkpoints.get(cp_id)
                if checkpoint:
                    self._delete_checkpoint_file(checkpoint)
                    del self._checkpoints[cp_id]
                    count += 1
            
            del self._task_checkpoints[task_id]
        
        logger.info(f"Deleted {count} checkpoints for task {task_id}")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'total_checkpoints': self.total_checkpoints,
                'total_recoveries': self.total_recoveries,
                'total_storage_bytes': self.total_storage_bytes,
                'total_storage_mb': self.total_storage_bytes / (1024 * 1024),
                'active_tasks': len(self._task_checkpoints),
                'storage_dir': str(self._storage_dir),
            }
    
    # ==================== 私有方法 ====================
    
    def _get_checkpoint_path(self, checkpoint: Checkpoint) -> Path:
        """获取检查点文件路径"""
        # 按任务ID分组存储
        task_dir = self._storage_dir / f"task_{checkpoint.task_id[:8]}"
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir / f"{checkpoint.checkpoint_id}.cp"
    
    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """保存检查点到磁盘"""
        file_path = self._get_checkpoint_path(checkpoint)
        checkpoint.storage_path = str(file_path)
        
        try:
            # 序列化状态
            serialized = self._serialize_json(checkpoint.state_data)
            
            # 压缩
            compressed = zlib.compress(serialized)
            
            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(compressed)
            
            checkpoint.is_valid = True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint.checkpoint_id}: {e}")
            checkpoint.is_valid = False
    
    def _load_checkpoint(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """从磁盘加载检查点"""
        try:
            with open(file_path, 'rb') as f:
                compressed = f.read()
            
            # 解压
            serialized = zlib.decompress(compressed)
            
            # 反序列化
            return self._deserialize_json(serialized)
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint from {file_path}: {e}")
            return None
    
    def _delete_checkpoint_file(self, checkpoint: Checkpoint) -> None:
        """删除检查点文件"""
        if checkpoint.storage_path:
            try:
                path = Path(checkpoint.storage_path)
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint file: {e}")
    
    def _serialize_json(self, data: Dict[str, Any]) -> bytes:
        """JSON序列化"""
        return json.dumps(data, default=str).encode('utf-8')
    
    def _deserialize_json(self, data: bytes) -> Dict[str, Any]:
        """JSON反序列化"""
        return json.loads(data.decode('utf-8'))
    
    def _serialize_pickle(self, data: Dict[str, Any]) -> bytes:
        """Pickle序列化"""
        import pickle
        return pickle.dumps(data)
    
    def _deserialize_pickle(self, data: bytes) -> Dict[str, Any]:
        """Pickle反序列化"""
        import pickle
        return pickle.loads(data)
    
    def _serialize_custom(self, data: Dict[str, Any]) -> bytes:
        """自定义序列化"""
        return self._serialize_json(data)
    
    async def _cleanup_loop(self) -> None:
        """清理循环 - 定期清理过期检查点"""
        while self._running:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    def _cleanup_expired(self) -> None:
        """清理过期检查点"""
        now = datetime.now()
        max_age = timedelta(seconds=self.config.max_checkpoint_age_seconds)
        
        with self._lock:
            expired_ids = []
            
            for cp_id, checkpoint in self._checkpoints.items():
                age = now - checkpoint.created_at
                if age > max_age:
                    # 只保留最新检查点
                    task_cps = self._task_checkpoints.get(checkpoint.task_id, [])
                    if cp_id != task_cps[-1] if task_cps else True:
                        expired_ids.append(cp_id)
            
            for cp_id in expired_ids:
                self.delete_checkpoint(cp_id)
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired checkpoints")


class CheckpointContext:
    """
    检查点上下文管理器
    
    简化检查点创建流程
    """
    
    def __init__(self, manager: CheckpointManager, task: Task,
                 checkpoint_type: CheckpointType = CheckpointType.INCREMENTAL):
        self.manager = manager
        self.task = task
        self.checkpoint_type = checkpoint_type
        self.checkpoint: Optional[Checkpoint] = None
    
    async def __aenter__(self) -> 'CheckpointContext':
        # 进入时创建检查点
        self.checkpoint = self.manager.create_checkpoint(
            self.task,
            self.checkpoint_type
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # 退出时更新检查点
        if exc_type is None:
            # 正常退出 - 更新进度
            self.checkpoint.state_data['progress'] = self.task.progress
            self.checkpoint.state_data['result'] = self.task.result
        else:
            # 异常退出 - 记录错误
            self.checkpoint.state_data['error'] = str(exc_val)
            self.checkpoint.state_data['error_type'] = exc_type.__name__


# 全局实例
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager(config: Optional[SchedulerConfig] = None) -> CheckpointManager:
    """获取检查点管理器实例"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager(config)
    return _checkpoint_manager
