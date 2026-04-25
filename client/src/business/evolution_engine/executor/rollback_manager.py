"""
Rollback Manager - 回滚管理器
管理提案执行的回滚操作
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RollbackType(Enum):
    """回滚类型"""
    FULL = "full"           # 完全回滚（恢复到执行前状态）
    PARTIAL = "partial"     # 部分回滚（撤销失败的步骤）
    STEP = "step"           # 单步回滚（撤销单个步骤）


@dataclass
class RollbackPoint:
    """回滚点"""
    point_id: str
    proposal_id: str
    created_at: datetime
    snapshot_id: str
    file_snapshots: Dict[str, str]  # 文件路径 -> 备份路径
    status: str  # "active", "rolled_back", "committed"
    description: str


@dataclass
class RollbackResult:
    """回滚结果"""
    success: bool
    rollback_type: RollbackType
    point_id: str
    files_restored: List[str]
    files_removed: List[str]
    error: Optional[str] = None
    executed_at: datetime = None


class RollbackManager:
    """
    回滚管理器
    
    功能：
    1. 创建回滚点
    2. 执行回滚
    3. 提交变更（确认执行成功）
    4. 回滚历史管理
    """
    
    def __init__(self, project_root: str, rollback_root: Optional[str] = None):
        """
        初始化回滚管理器
        
        Args:
            project_root: 项目根目录
            rollback_root: 回滚存储目录，默认为 project_root/.evolution_rollbacks
        """
        self.project_root = Path(project_root)
        self.rollback_root = Path(rollback_root) if rollback_root else \
                            self.project_root / ".evolution_rollbacks"
        
        # 确保回滚目录存在
        self.rollback_root.mkdir(parents=True, exist_ok=True)
        
        # 回滚点存储
        self._rollback_points: Dict[str, RollbackPoint] = {}
        
        # 当前活跃回滚点
        self._active_point: Optional[str] = None
        
        logger.info(f"[RollbackManager] 初始化完成，回滚目录: {self.rollback_root}")
    
    def create_rollback_point(
        self,
        proposal_id: str,
        snapshot_id: str,
        description: str,
        changed_files: List[str]
    ) -> RollbackPoint:
        """
        创建回滚点
        
        Args:
            proposal_id: 提案ID
            snapshot_id: 快照ID
            description: 回滚点描述
            changed_files: 变更文件列表
            
        Returns:
            回滚点信息
        """
        import uuid
        
        point_id = f"rb_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now()
        
        # 创建文件快照
        file_snapshots: Dict[str, str] = {}
        
        for file_path in changed_files:
            abs_path = self.project_root / file_path
            if abs_path.exists():
                backup_path = self._backup_file(abs_path, point_id)
                if backup_path:
                    file_snapshots[str(abs_path)] = backup_path
        
        # 创建回滚点目录
        point_dir = self.rollback_root / point_id
        point_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存回滚点信息
        rollback_point = RollbackPoint(
            point_id=point_id,
            proposal_id=proposal_id,
            created_at=timestamp,
            snapshot_id=snapshot_id,
            file_snapshots=file_snapshots,
            status="active",
            description=description
        )
        
        self._rollback_points[point_id] = rollback_point
        self._active_point = point_id
        
        logger.info(
            f"[RollbackManager] 回滚点创建: {point_id} "
            f"(文件数: {len(file_snapshots)})"
        )
        
        return rollback_point
    
    def rollback(
        self,
        point_id: str,
        rollback_type: RollbackType = RollbackType.FULL
    ) -> RollbackResult:
        """
        执行回滚
        
        Args:
            point_id: 回滚点ID
            rollback_type: 回滚类型
            
        Returns:
            回滚结果
        """
        if point_id not in self._rollback_points:
            return RollbackResult(
                success=False,
                rollback_type=rollback_type,
                point_id=point_id,
                files_restored=[],
                files_removed=[],
                error="回滚点不存在"
            )
        
        rollback_point = self._rollback_points[point_id]
        
        if rollback_point.status == "rolled_back":
            return RollbackResult(
                success=False,
                rollback_type=rollback_type,
                point_id=point_id,
                files_restored=[],
                files_removed=[],
                error="回滚点已经回滚过"
            )
        
        files_restored: List[str] = []
        files_removed: List[str] = []
        
        try:
            if rollback_type == RollbackType.FULL:
                # 完全回滚：恢复到执行前状态
                files_restored, files_removed = self._full_rollback(rollback_point)
            
            elif rollback_type == RollbackType.PARTIAL:
                # 部分回滚：保留已成功步骤
                files_restored, files_removed = self._partial_rollback(rollback_point)
            
            elif rollback_type == RollbackType.STEP:
                # 单步回滚：撤销单个步骤
                files_restored, files_removed = self._step_rollback(rollback_point)
            
            # 更新回滚点状态
            rollback_point.status = "rolled_back"
            self._active_point = None
            
            logger.info(
                f"[RollbackManager] 回滚完成: {point_id} "
                f"(恢复: {len(files_restored)}, 删除: {len(files_removed)})"
            )
            
            return RollbackResult(
                success=True,
                rollback_type=rollback_type,
                point_id=point_id,
                files_restored=files_restored,
                files_removed=files_removed,
                executed_at=datetime.now()
            )
        
        except Exception as e:
            logger.error(f"[RollbackManager] 回滚失败: {e}")
            return RollbackResult(
                success=False,
                rollback_type=rollback_type,
                point_id=point_id,
                files_restored=files_restored,
                files_removed=files_removed,
                error=str(e),
                executed_at=datetime.now()
            )
    
    def commit(self, point_id: str) -> bool:
        """
        提交回滚点（确认变更生效，清理回滚点）
        
        Args:
            point_id: 回滚点ID
            
        Returns:
            是否成功
        """
        if point_id not in self._rollback_points:
            return False
        
        rollback_point = self._rollback_points[point_id]
        
        try:
            # 清理备份文件
            for original_path, backup_path in rollback_point.file_snapshots.items():
                backup = Path(backup_path)
                if backup.exists():
                    shutil.rmtree(backup.parent, ignore_errors=True)
            
            # 清理回滚点目录
            point_dir = self.rollback_root / point_id
            if point_dir.exists():
                shutil.rmtree(point_dir)
            
            # 从存储中移除
            del self._rollback_points[point_id]
            
            if self._active_point == point_id:
                self._active_point = None
            
            logger.info(f"[RollbackManager] 回滚点已提交: {point_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"[RollbackManager] 提交回滚点失败: {e}")
            return False
    
    def get_rollback_point(self, point_id: str) -> Optional[RollbackPoint]:
        """获取回滚点"""
        return self._rollback_points.get(point_id)
    
    def get_active_rollback_point(self) -> Optional[RollbackPoint]:
        """获取当前活跃回滚点"""
        if self._active_point:
            return self._rollback_points.get(self._active_point)
        return None
    
    def get_all_rollback_points(self) -> List[Dict[str, Any]]:
        """获取所有回滚点"""
        return [
            {
                "point_id": p.point_id,
                "proposal_id": p.proposal_id,
                "created_at": p.created_at.isoformat(),
                "snapshot_id": p.snapshot_id,
                "status": p.status,
                "description": p.description,
                "files_count": len(p.file_snapshots),
            }
            for p in self._rollback_points.values()
        ]
    
    def cleanup_old_rollback_points(self, keep_count: int = 10) -> int:
        """
        清理旧的回滚点
        
        Args:
            keep_count: 保留数量
            
        Returns:
            清理数量
        """
        # 按创建时间排序
        sorted_points = sorted(
            self._rollback_points.values(),
            key=lambda p: p.created_at,
            reverse=True
        )
        
        cleaned = 0
        for point in sorted_points[keep_count:]:
            if point.status == "committed":
                self.commit(point.point_id)
                cleaned += 1
            elif point.status == "rolled_back":
                if self.commit(point.point_id):
                    cleaned += 1
        
        if cleaned > 0:
            logger.info(f"[RollbackManager] 清理了 {cleaned} 个旧回滚点")
        
        return cleaned
    
    def _backup_file(self, file_path: Path, point_id: str) -> Optional[str]:
        """备份文件到回滚存储"""
        try:
            from datetime import datetime
            
            backup_dir = self.rollback_root / point_id / "files"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%H%M%S")
            rel_path = file_path.relative_to(self.project_root)
            backup_name = f"{rel_path.as_posix().replace('/', '_')}_{timestamp}"
            backup_path = backup_dir / backup_name
            
            if file_path.is_file():
                shutil.copy2(file_path, backup_path)
            elif file_path.is_dir():
                shutil.copytree(file_path, backup_path, dirs_exist_ok=True)
            
            return str(backup_path)
        
        except Exception as e:
            logger.warning(f"[RollbackManager] 文件备份失败: {file_path} - {e}")
            return None
    
    def _full_rollback(self, rollback_point: RollbackPoint) -> tuple:
        """执行完全回滚"""
        files_restored: List[str] = []
        files_removed: List[str] = []
        
        for original_path, backup_path in rollback_point.file_snapshots.items():
            try:
                orig = Path(original_path)
                backup = Path(backup_path)
                
                if not backup.exists():
                    continue
                
                # 如果原始文件存在，先删除
                if orig.exists():
                    if orig.is_file():
                        orig.unlink()
                    elif orig.is_dir():
                        shutil.rmtree(orig)
                    files_removed.append(original_path)
                
                # 从备份恢复
                if backup.is_file():
                    orig.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, orig)
                elif backup.is_dir():
                    shutil.copytree(backup, orig, dirs_exist_ok=True)
                
                files_restored.append(original_path)
            
            except Exception as e:
                logger.error(f"[RollbackManager] 文件恢复失败: {original_path} - {e}")
        
        return files_restored, files_removed
    
    def _partial_rollback(self, rollback_point: RollbackPoint) -> tuple:
        """执行部分回滚"""
        # 简化实现：与完全回滚相同
        return self._full_rollback(rollback_point)
    
    def _step_rollback(self, rollback_point: RollbackPoint) -> tuple:
        """执行单步回滚"""
        # 简化实现：与完全回滚相同
        # 实际应该根据步骤记录来确定需要回滚哪些文件
        return self._full_rollback(rollback_point)
