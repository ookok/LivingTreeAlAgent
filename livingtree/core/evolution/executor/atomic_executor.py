"""
Atomic Executor - 原子操作执行器
负责安全地执行代码变更操作
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """操作类型"""
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RENAME_FILE = "rename_file"
    CREATE_DIR = "create_dir"
    DELETE_DIR = "delete_dir"
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"


@dataclass
class Operation:
    """操作定义"""
    op_type: OperationType
    target: str                    # 目标路径
    content: Optional[str] = None  # 新内容（用于创建/修改）
    backup_path: Optional[str] = None  # 备份路径
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OperationResult:
    """操作结果"""
    success: bool
    op_type: OperationType
    target: str
    error: Optional[str] = None
    backup_path: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class AtomicResult:
    """原子操作结果"""
    success: bool
    proposal_id: str
    operations: List[OperationResult]
    snapshot_id: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime = None
    completed_at: datetime = None
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.operations if r.success)
    
    @property
    def total_count(self) -> int:
        return len(self.operations)
    
    @property
    def failed_operations(self) -> List[OperationResult]:
        return [r for r in self.operations if not r.success]


class AtomicExecutor:
    """
    原子操作执行器
    
    特点：
    1. 所有操作要么全部成功，要么全部回滚
    2. 每个操作前自动备份
    3. 支持操作验证
    4. 详细的执行日志
    """
    
    def __init__(self, project_root: str, backup_root: Optional[str] = None):
        """
        初始化执行器
        
        Args:
            project_root: 项目根目录
            backup_root: 备份根目录，默认为 project_root/.evolution_backups
        """
        self.project_root = Path(project_root)
        self.backup_root = Path(backup_root) if backup_root else \
                          self.project_root / ".evolution_backups"
        
        # 确保备份目录存在
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        # 操作历史
        self.operation_history: List[AtomicResult] = []
        
        # 验证钩子
        self.validation_hooks: List[Callable[[Operation], bool]] = []
        
        logger.info(f"[AtomicExecutor] 初始化完成，备份目录: {self.backup_root}")
    
    def add_validation_hook(self, hook: Callable[[Operation], bool]):
        """
        添加验证钩子
        
        Args:
            hook: 验证函数，接收 Operation，返回 bool
        """
        self.validation_hooks.append(hook)
    
    def execute_operations(
        self,
        proposal_id: str,
        operations: List[Dict[str, Any]],
        snapshot_id: Optional[str] = None,
        validate_before: bool = True,
        rollback_on_failure: bool = True
    ) -> AtomicResult:
        """
        执行原子操作
        
        Args:
            proposal_id: 提案ID
            operations: 操作列表
            snapshot_id: 快照ID（用于回滚）
            validate_before: 是否执行前验证
            rollback_on_failure: 失败时是否回滚
            
        Returns:
            原子操作结果
        """
        started_at = datetime.now()
        
        # 解析操作为 Operation 对象
        parsed_ops = []
        for op_dict in operations:
            try:
                op = Operation(
                    op_type=OperationType(op_dict.get("action_type", "modify_file")),
                    target=op_dict.get("target", ""),
                    content=op_dict.get("content"),
                    metadata=op_dict.get("metadata", {})
                )
                parsed_ops.append(op)
            except ValueError as e:
                logger.error(f"[AtomicExecutor] 操作解析失败: {e}")
                continue
        
        if not parsed_ops:
            return AtomicResult(
                success=False,
                proposal_id=proposal_id,
                operations=[],
                error="没有有效的操作",
                started_at=started_at,
                completed_at=datetime.now()
            )
        
        # 执行前验证
        if validate_before:
            for op in parsed_ops:
                if not self._validate_operation(op):
                    return AtomicResult(
                        success=False,
                        proposal_id=proposal_id,
                        operations=[],
                        error=f"操作验证失败: {op.target}",
                        started_at=started_at,
                        completed_at=datetime.now()
                    )
        
        # 执行操作
        results: List[OperationResult] = []
        executed_ops: List[Operation] = []
        
        import time
        for op in parsed_ops:
            start = time.time()
            
            try:
                # 执行操作
                result = self._execute_single_operation(op)
                result.execution_time = time.time() - start
                results.append(result)
                
                if result.success:
                    executed_ops.append(op)
                else:
                    # 操作失败
                    logger.error(f"[AtomicExecutor] 操作失败: {op.op_type.value} - {op.target}")
                    
                    if rollback_on_failure:
                        # 回滚已执行的操作
                        self._rollback_operations(executed_ops)
                        
                        return AtomicResult(
                            success=False,
                            proposal_id=proposal_id,
                            operations=results,
                            snapshot_id=snapshot_id,
                            error=f"操作失败: {result.error}",
                            started_at=started_at,
                            completed_at=datetime.now()
                        )
            
            except Exception as e:
                logger.error(f"[AtomicExecutor] 操作异常: {e}")
                results.append(OperationResult(
                    success=False,
                    op_type=op.op_type,
                    target=op.target,
                    error=str(e),
                    execution_time=time.time() - start
                ))
                
                if rollback_on_failure:
                    self._rollback_operations(executed_ops)
                    
                    return AtomicResult(
                        success=False,
                        proposal_id=proposal_id,
                        operations=results,
                        snapshot_id=snapshot_id,
                        error=f"操作异常: {str(e)}",
                        started_at=started_at,
                        completed_at=datetime.now()
                    )
        
        # 全部成功
        completed_at = datetime.now()
        result = AtomicResult(
            success=True,
            proposal_id=proposal_id,
            operations=results,
            snapshot_id=snapshot_id,
            started_at=started_at,
            completed_at=completed_at
        )
        
        self.operation_history.append(result)
        
        logger.info(
            f"[AtomicExecutor] 提案执行完成: {proposal_id} "
            f"({result.success_count}/{result.total_count} 成功)"
        )
        
        return result
    
    def _validate_operation(self, op: Operation) -> bool:
        """验证操作"""
        # 检查目标路径是否在项目目录内
        try:
            target_path = Path(op.target)
            target_abs = target_path.resolve()
            project_abs = self.project_root.resolve()
            
            if not str(target_abs).startswith(str(project_abs)):
                logger.error(f"[AtomicExecutor] 目标路径在项目目录外: {op.target}")
                return False
        except Exception as e:
            logger.error(f"[AtomicExecutor] 路径验证失败: {e}")
            return False
        
        # 执行验证钩子
        for hook in self.validation_hooks:
            if not hook(op):
                return False
        
        return True
    
    def _execute_single_operation(self, op: Operation) -> OperationResult:
        """执行单个操作"""
        import time
        
        target_path = Path(op.target)
        
        if op.op_type == OperationType.CREATE_FILE:
            return self._create_file(target_path, op.content)
        
        elif op.op_type == OperationType.MODIFY_FILE:
            return self._modify_file(target_path, op.content)
        
        elif op.op_type == OperationType.DELETE_FILE:
            return self._delete_file(target_path)
        
        elif op.op_type == OperationType.RENAME_FILE:
            new_name = op.metadata.get("new_name", "")
            return self._rename_file(target_path, new_name)
        
        elif op.op_type == OperationType.CREATE_DIR:
            return self._create_dir(target_path)
        
        elif op.op_type == OperationType.DELETE_DIR:
            return self._delete_dir(target_path)
        
        elif op.op_type == OperationType.COPY_FILE:
            src = op.metadata.get("source")
            return self._copy_file(Path(src) if src else None, target_path)
        
        elif op.op_type == OperationType.MOVE_FILE:
            src = op.metadata.get("source")
            return self._move_file(Path(src) if src else None, target_path)
        
        else:
            return OperationResult(
                success=False,
                op_type=op.op_type,
                target=op.target,
                error=f"未知操作类型: {op.op_type}"
            )
    
    def _create_file(self, path: Path, content: Optional[str]) -> OperationResult:
        """创建文件"""
        try:
            # 备份（如果存在）
            backup_path = None
            if path.exists():
                backup_path = self._create_backup(path)
            
            # 创建目录
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建文件
            path.write_text(content or "", encoding="utf-8")
            
            logger.info(f"[AtomicExecutor] 文件创建: {path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.CREATE_FILE,
                target=str(path),
                backup_path=backup_path
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.CREATE_FILE,
                target=str(path),
                error=str(e)
            )
    
    def _modify_file(self, path: Path, content: Optional[str]) -> OperationResult:
        """修改文件"""
        try:
            if not path.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.MODIFY_FILE,
                    target=str(path),
                    error="文件不存在"
                )
            
            # 备份
            backup_path = self._create_backup(path)
            
            # 修改文件
            path.write_text(content or "", encoding="utf-8")
            
            logger.info(f"[AtomicExecutor] 文件修改: {path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.MODIFY_FILE,
                target=str(path),
                backup_path=backup_path
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.MODIFY_FILE,
                target=str(path),
                error=str(e)
            )
    
    def _delete_file(self, path: Path) -> OperationResult:
        """删除文件"""
        try:
            if not path.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.DELETE_FILE,
                    target=str(path),
                    error="文件不存在"
                )
            
            # 备份
            backup_path = self._create_backup(path)
            
            # 删除文件
            path.unlink()
            
            logger.info(f"[AtomicExecutor] 文件删除: {path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.DELETE_FILE,
                target=str(path),
                backup_path=backup_path
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.DELETE_FILE,
                target=str(path),
                error=str(e)
            )
    
    def _rename_file(self, path: Path, new_name: str) -> OperationResult:
        """重命名文件"""
        try:
            if not path.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.RENAME_FILE,
                    target=str(path),
                    error="文件不存在"
                )
            
            new_path = path.parent / new_name
            backup_path = self._create_backup(path)
            
            path.rename(new_path)
            
            logger.info(f"[AtomicExecutor] 文件重命名: {path} -> {new_path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.RENAME_FILE,
                target=str(path),
                backup_path=backup_path
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.RENAME_FILE,
                target=str(path),
                error=str(e)
            )
    
    def _create_dir(self, path: Path) -> OperationResult:
        """创建目录"""
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"[AtomicExecutor] 目录创建: {path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.CREATE_DIR,
                target=str(path)
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.CREATE_DIR,
                target=str(path),
                error=str(e)
            )
    
    def _delete_dir(self, path: Path) -> OperationResult:
        """删除目录"""
        try:
            if not path.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.DELETE_DIR,
                    target=str(path),
                    error="目录不存在"
                )
            
            # 备份
            backup_path = self._create_backup(path)
            
            # 删除目录
            shutil.rmtree(path)
            
            logger.info(f"[AtomicExecutor] 目录删除: {path}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.DELETE_DIR,
                target=str(path),
                backup_path=backup_path
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.DELETE_DIR,
                target=str(path),
                error=str(e)
            )
    
    def _copy_file(self, src: Optional[Path], dst: Path) -> OperationResult:
        """复制文件"""
        try:
            if not src or not src.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.COPY_FILE,
                    target=str(dst),
                    error="源文件不存在"
                )
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            
            logger.info(f"[AtomicExecutor] 文件复制: {src} -> {dst}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.COPY_FILE,
                target=str(dst)
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.COPY_FILE,
                target=str(dst),
                error=str(e)
            )
    
    def _move_file(self, src: Optional[Path], dst: Path) -> OperationResult:
        """移动文件"""
        try:
            if not src or not src.exists():
                return OperationResult(
                    success=False,
                    op_type=OperationType.MOVE_FILE,
                    target=str(dst),
                    error="源文件不存在"
                )
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            
            logger.info(f"[AtomicExecutor] 文件移动: {src} -> {dst}")
            
            return OperationResult(
                success=True,
                op_type=OperationType.MOVE_FILE,
                target=str(dst)
            )
        except Exception as e:
            return OperationResult(
                success=False,
                op_type=OperationType.MOVE_FILE,
                target=str(dst),
                error=str(e)
            )
    
    def _create_backup(self, path: Path) -> Optional[str]:
        """创建备份"""
        try:
            from datetime import datetime
            import uuid
            
            backup_dir = self.backup_root / datetime.now().strftime("%Y%m%d")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            backup_name = f"{path.name}_{uuid.uuid4().hex[:8]}.bak"
            backup_path = backup_dir / backup_name
            
            if path.is_file():
                shutil.copy2(path, backup_path)
            elif path.is_dir():
                shutil.copytree(path, backup_path, dirs_exist_ok=True)
            
            return str(backup_path)
        except Exception as e:
            logger.warning(f"[AtomicExecutor] 备份创建失败: {e}")
            return None
    
    def _rollback_operations(self, operations: List[Operation]) -> bool:
        """
        回滚操作
        
        Args:
            operations: 需要回滚的操作列表
            
        Returns:
            是否成功
        """
        logger.info(f"[AtomicExecutor] 开始回滚 {len(operations)} 个操作...")
        
        success = True
        for op in reversed(operations):
            try:
                target_path = Path(op.target)
                
                if op.op_type == OperationType.CREATE_FILE:
                    if target_path.exists():
                        target_path.unlink()
                
                elif op.op_type == OperationType.MODIFY_FILE:
                    if op.backup_path and Path(op.backup_path).exists():
                        shutil.copy2(op.backup_path, target_path)
                
                elif op.op_type == OperationType.DELETE_FILE:
                    if op.backup_path and Path(op.backup_path).exists():
                        shutil.copy2(op.backup_path, target_path)
                
                elif op.op_type == OperationType.RENAME_FILE:
                    if op.backup_path and Path(op.backup_path).exists():
                        shutil.copy2(op.backup_path, target_path)
                
                logger.info(f"[AtomicExecutor] 回滚成功: {op.target}")
                
            except Exception as e:
                logger.error(f"[AtomicExecutor] 回滚失败: {op.target} - {e}")
                success = False
        
        return success
    
    def get_operation_history(self) -> List[Dict[str, Any]]:
        """获取操作历史"""
        return [
            {
                "proposal_id": r.proposal_id,
                "success": r.success,
                "operations_count": r.total_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in self.operation_history
        ]
