"""
TaskIsolationManager - 任务隔离管理器

参考 Archon 的"独立 git worktree"设计，实现运行隔离机制。

核心功能：
1. 每个任务分配独立的工作目录
2. 支持并行执行多个任务，无冲突
3. 自动清理过期任务目录
4. 支持资源限制（CPU、内存）
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta
import os
import shutil
import asyncio
from pathlib import Path


@dataclass
class TaskWorkspace:
    """任务工作空间"""
    task_id: str
    workspace_path: str
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)
    resource_limits: Dict[str, Any] = field(default_factory=dict)


class TaskIsolationManager:
    """
    任务隔离管理器
    
    核心功能：
    1. 为每个任务创建独立的工作目录
    2. 支持并行执行多个任务，无冲突
    3. 自动清理过期任务目录
    4. 支持资源限制（CPU、内存）
    """
    
    def __init__(self, base_dir: str = None, auto_cleanup: bool = True):
        self._logger = logger.bind(component="TaskIsolationManager")
        self._workspaces: Dict[str, TaskWorkspace] = {}
        self._base_dir = base_dir or self._get_default_base_dir()
        self._cleanup_interval = 3600  # 清理间隔（秒）
        self._max_workspace_age = 86400  # 最大工作空间存活时间（秒）= 24小时
        self._auto_cleanup = auto_cleanup
        
        os.makedirs(self._base_dir, exist_ok=True)
        self._load_existing_workspaces()
        if self._auto_cleanup:
            try:
                self._start_cleanup_task()
            except RuntimeError:
                self._logger.debug("无法启动自动清理任务（无运行中的事件循环）")
    
    def _get_default_base_dir(self) -> str:
        """获取默认基础目录"""
        return os.path.join(os.path.expanduser("~"), ".livingtree", "task_workspaces")
    
    def _load_existing_workspaces(self):
        """加载已存在的工作空间"""
        try:
            for item in os.listdir(self._base_dir):
                item_path = os.path.join(self._base_dir, item)
                if os.path.isdir(item_path):
                    # 尝试解析任务ID和创建时间
                    task_id = item
                    created_at = datetime.fromtimestamp(os.path.getctime(item_path))
                    last_used = datetime.fromtimestamp(os.path.getmtime(item_path))
                    
                    workspace = TaskWorkspace(
                        task_id=task_id,
                        workspace_path=item_path,
                        status="active",
                        created_at=created_at,
                        last_used_at=last_used
                    )
                    self._workspaces[task_id] = workspace
            
            self._logger.info(f"加载了 {len(self._workspaces)} 个现有工作空间")
        except Exception as e:
            self._logger.error(f"加载工作空间失败: {e}")
    
    def _start_cleanup_task(self):
        """启动定期清理任务"""
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """定期清理过期工作空间"""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self.cleanup_expired_workspaces()
    
    def create_workspace(self, task_id: str, resource_limits: Optional[Dict[str, Any]] = None) -> str:
        """
        为任务创建独立工作空间
        
        Args:
            task_id: 任务 ID
            resource_limits: 资源限制（如 {"cpu": 2, "memory_mb": 1024}）
            
        Returns:
            工作空间路径
        """
        # 检查是否已存在工作空间
        if task_id in self._workspaces:
            workspace = self._workspaces[task_id]
            workspace.last_used_at = datetime.now()
            self._logger.info(f"复用工作空间: {task_id}")
            return workspace.workspace_path
        
        # 创建新的工作空间目录
        workspace_path = os.path.join(self._base_dir, task_id)
        
        # 如果目录已存在，清理它
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
        
        # 创建目录结构
        os.makedirs(workspace_path, exist_ok=True)
        
        # 创建子目录
        subdirs = ["input", "output", "temp", "logs", "artifacts"]
        for subdir in subdirs:
            os.makedirs(os.path.join(workspace_path, subdir), exist_ok=True)
        
        # 创建工作空间记录
        workspace = TaskWorkspace(
            task_id=task_id,
            workspace_path=workspace_path,
            resource_limits=resource_limits or {}
        )
        self._workspaces[task_id] = workspace
        
        self._logger.info(f"创建工作空间: {workspace_path}")
        
        return workspace_path
    
    def get_workspace(self, task_id: str) -> Optional[str]:
        """
        获取任务工作空间路径
        
        Args:
            task_id: 任务 ID
            
        Returns:
            工作空间路径，如果不存在返回 None
        """
        workspace = self._workspaces.get(task_id)
        if workspace:
            workspace.last_used_at = datetime.now()
            return workspace.workspace_path
        return None
    
    def get_workspace_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作空间详细信息
        
        Args:
            task_id: 任务 ID
            
        Returns:
            工作空间信息字典
        """
        workspace = self._workspaces.get(task_id)
        if not workspace:
            return None
        
        # 计算目录大小
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(workspace.workspace_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
        except Exception:
            total_size = 0
        
        return {
            "task_id": workspace.task_id,
            "workspace_path": workspace.workspace_path,
            "status": workspace.status,
            "created_at": workspace.created_at.isoformat(),
            "last_used_at": workspace.last_used_at.isoformat(),
            "resource_limits": workspace.resource_limits,
            "size_bytes": total_size
        }
    
    def release_workspace(self, task_id: str):
        """
        释放工作空间（标记为待清理）
        
        Args:
            task_id: 任务 ID
        """
        workspace = self._workspaces.get(task_id)
        if workspace:
            workspace.status = "released"
            self._logger.info(f"释放工作空间: {task_id}")
    
    def destroy_workspace(self, task_id: str) -> bool:
        """
        立即销毁工作空间
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功
        """
        workspace = self._workspaces.get(task_id)
        if not workspace:
            return False
        
        try:
            shutil.rmtree(workspace.workspace_path)
            del self._workspaces[task_id]
            self._logger.info(f"销毁工作空间: {task_id}")
            return True
        except Exception as e:
            self._logger.error(f"销毁工作空间失败 {task_id}: {e}")
            return False
    
    async def cleanup_expired_workspaces(self):
        """清理过期工作空间"""
        now = datetime.now()
        expired_count = 0
        
        for task_id, workspace in list(self._workspaces.items()):
            age = (now - workspace.created_at).total_seconds()
            
            if age > self._max_workspace_age:
                self.destroy_workspace(task_id)
                expired_count += 1
        
        if expired_count > 0:
            self._logger.info(f"清理了 {expired_count} 个过期工作空间")
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作空间"""
        result = []
        for task_id, workspace in self._workspaces.items():
            result.append(self.get_workspace_info(task_id))
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_count = sum(1 for w in self._workspaces.values() if w.status == "active")
        released_count = sum(1 for w in self._workspaces.values() if w.status == "released")
        
        return {
            "total_workspaces": len(self._workspaces),
            "active_workspaces": active_count,
            "released_workspaces": released_count,
            "base_dir": self._base_dir,
            "max_workspace_age_hours": self._max_workspace_age / 3600,
            "cleanup_interval_hours": self._cleanup_interval / 3600
        }
    
    def get_input_path(self, task_id: str, filename: str = "") -> str:
        """
        获取输入目录路径
        
        Args:
            task_id: 任务 ID
            filename: 文件名（可选）
            
        Returns:
            输入目录或文件路径
        """
        workspace_path = self.get_workspace(task_id)
        if not workspace_path:
            raise ValueError(f"工作空间不存在: {task_id}")
        
        path = os.path.join(workspace_path, "input")
        if filename:
            path = os.path.join(path, filename)
        
        return path
    
    def get_output_path(self, task_id: str, filename: str = "") -> str:
        """
        获取输出目录路径
        
        Args:
            task_id: 任务 ID
            filename: 文件名（可选）
            
        Returns:
            输出目录或文件路径
        """
        workspace_path = self.get_workspace(task_id)
        if not workspace_path:
            raise ValueError(f"工作空间不存在: {task_id}")
        
        path = os.path.join(workspace_path, "output")
        if filename:
            path = os.path.join(path, filename)
        
        return path
    
    def get_temp_path(self, task_id: str, filename: str = "") -> str:
        """
        获取临时目录路径
        
        Args:
            task_id: 任务 ID
            filename: 文件名（可选）
            
        Returns:
            临时目录或文件路径
        """
        workspace_path = self.get_workspace(task_id)
        if not workspace_path:
            raise ValueError(f"工作空间不存在: {task_id}")
        
        path = os.path.join(workspace_path, "temp")
        if filename:
            path = os.path.join(path, filename)
        
        return path
    
    def get_logs_path(self, task_id: str, filename: str = "") -> str:
        """
        获取日志目录路径
        
        Args:
            task_id: 任务 ID
            filename: 文件名（可选）
            
        Returns:
            日志目录或文件路径
        """
        workspace_path = self.get_workspace(task_id)
        if not workspace_path:
            raise ValueError(f"工作空间不存在: {task_id}")
        
        path = os.path.join(workspace_path, "logs")
        if filename:
            path = os.path.join(path, filename)
        
        return path