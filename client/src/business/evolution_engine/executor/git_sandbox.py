"""
Git Sandbox - Git 沙箱环境
为提案执行提供隔离的 Git 工作环境
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class SandboxSnapshot:
    """沙箱快照"""
    snapshot_id: str
    branch_name: str
    commit_hash: str
    created_at: datetime
    description: str
    file_changes: List[str]


class GitSandbox:
    """
    Git 沙箱环境
    
    功能：
    1. 创建隔离的分支环境
    2. 快照管理
    3. 工作目录操作
    """
    
    def __init__(self, project_root: str, sandbox_root: Optional[str] = None):
        """
        初始化沙箱
        
        Args:
            project_root: 项目根目录
            sandbox_root: 沙箱根目录，默认为 project_root/.evolution_sandbox
        """
        self.project_root = Path(project_root)
        self.sandbox_root = Path(sandbox_root) if sandbox_root else \
                          self.project_root / ".evolution_sandbox"
        
        # 确保沙箱目录存在
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        
        # 快照存储
        self.snapshots: Dict[str, SandboxSnapshot] = {}
        
        # 当前沙箱分支
        self._current_branch: Optional[str] = None
        
        logger.info(f"[GitSandbox] 初始化完成，沙箱目录: {self.sandbox_root}")
    
    def create_snapshot(self, description: str) -> SandboxSnapshot:
        """
        创建快照
        
        Args:
            description: 快照描述
            
        Returns:
            快照信息
        """
        import uuid
        
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now()
        
        # 创建分支
        branch_name = f"evolution/{snapshot_id}"
        
        try:
            # 创建新分支
            self._run_git("checkout", "-b", branch_name)
            
            # 添加所有更改
            self._run_git("add", "-A")
            
            # 创建提交
            commit_message = f"[Evolution] {description}"
            result = self._run_git("commit", "-m", commit_message)
            
            # 获取提交hash
            commit_hash = self._get_current_commit()
            
            # 获取变更文件列表
            file_changes = self._get_changed_files()
            
            # 创建快照对象
            snapshot = SandboxSnapshot(
                snapshot_id=snapshot_id,
                branch_name=branch_name,
                commit_hash=commit_hash,
                created_at=timestamp,
                description=description,
                file_changes=file_changes
            )
            
            self.snapshots[snapshot_id] = snapshot
            self._current_branch = branch_name
            
            logger.info(
                f"[GitSandbox] 快照创建成功: {snapshot_id} "
                f"({branch_name}, {commit_hash[:7]})"
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"[GitSandbox] 创建快照失败: {e}")
            # 恢复到原始分支
            self._restore_main_branch()
            raise
    
    def restore_snapshot(self, snapshot_id: str) -> bool:
        """
        恢复到指定快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            是否成功
        """
        if snapshot_id not in self.snapshots:
            logger.error(f"[GitSandbox] 快照不存在: {snapshot_id}")
            return False
        
        snapshot = self.snapshots[snapshot_id]
        
        try:
            # 切换到快照分支
            self._run_git("checkout", snapshot.branch_name)
            self._current_branch = snapshot.branch_name
            
            logger.info(f"[GitSandbox] 已恢复到快照: {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"[GitSandbox] 恢复快照失败: {e}")
            return False
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        删除快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            是否成功
        """
        if snapshot_id not in self.snapshots:
            return False
        
        snapshot = self.snapshots[snapshot_id]
        
        try:
            # 如果是当前分支，切换到主分支
            if self._current_branch == snapshot.branch_name:
                self._restore_main_branch()
            
            # 删除分支
            self._run_git("branch", "-D", snapshot.branch_name)
            
            # 从存储中移除
            del self.snapshots[snapshot_id]
            
            logger.info(f"[GitSandbox] 快照已删除: {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"[GitSandbox] 删除快照失败: {e}")
            return False
    
    def get_working_changes(self) -> List[str]:
        """
        获取当前工作目录的变更
        
        Returns:
            变更文件列表
        """
        return self._get_changed_files()
    
    def is_clean(self) -> bool:
        """
        检查工作目录是否干净
        
        Returns:
            是否干净
        """
        result = self._run_git("status", "--porcelain")
        return len(result.strip()) == 0
    
    def discard_changes(self) -> bool:
        """
        丢弃当前变更
        
        Returns:
            是否成功
        """
        try:
            self._run_git("checkout", "--", ".")
            self._run_git("clean", "-fd")
            logger.info("[GitSandbox] 已丢弃所有变更")
            return True
        except Exception as e:
            logger.error(f"[GitSandbox] 丢弃变更失败: {e}")
            return False
    
    def _restore_main_branch(self):
        """恢复到主分支"""
        try:
            # 尝试切换到 main 或 master
            for branch in ["main", "master", "develop"]:
                result = self._run_git("rev-parse", "--verify", branch)
                if result.strip():
                    self._run_git("checkout", branch)
                    self._current_branch = branch
                    return
        except Exception:
            pass
        
        # 如果没有主分支，创建 main 分支
        try:
            self._run_git("checkout", "-b", "main")
            self._current_branch = "main"
        except Exception as e:
            logger.warning(f"[GitSandbox] 无法恢复主分支: {e}")
    
    def _run_git(self, *args) -> str:
        """运行 git 命令"""
        cmd = ["git", "-C", str(self.project_root)] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0 and "nothing to commit" not in result.stderr.lower():
            logger.debug(f"[GitSandbox] Git 命令: {' '.join(cmd)}")
            logger.debug(f"[GitSandbox] Git 输出: {result.stdout}")
            logger.debug(f"[GitSandbox] Git 错误: {result.stderr}")
        
        return result.stdout
    
    def _get_current_commit(self) -> str:
        """获取当前提交 hash"""
        result = self._run_git("rev-parse", "HEAD")
        return result.strip()
    
    def _get_changed_files(self) -> List[str]:
        """获取变更文件列表"""
        result = self._run_git("diff", "--name-only", "HEAD")
        return [f.strip() for f in result.strip().split("\n") if f.strip()]
    
    def get_snapshots(self) -> List[Dict[str, Any]]:
        """获取所有快照"""
        return [
            {
                "snapshot_id": s.snapshot_id,
                "branch_name": s.branch_name,
                "commit_hash": s.commit_hash[:7],
                "created_at": s.created_at.isoformat(),
                "description": s.description,
                "file_changes_count": len(s.file_changes),
            }
            for s in self.snapshots.values()
        ]
