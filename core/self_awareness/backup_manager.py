"""
备份管理器
管理修复前的备份
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import os
import shutil
import time
from pathlib import Path


class BackupStatus(Enum):
    """备份状态"""
    CREATED = "created"
    RESTORED = "restored"
    CORRUPTED = "corrupted"


@dataclass
class BackupRecord:
    """备份记录"""
    backup_id: str
    files: List[str]
    backup_path: str
    status: BackupStatus = BackupStatus.CREATED
    created_at: float = field(default_factory=time.time)
    restored_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackupManager:
    """
    备份管理器
    
    功能：
    1. 创建备份
    2. 恢复备份
    3. 管理备份历史
    """
    
    def __init__(self, project_root: str,
                 config: Optional[Dict[str, Any]] = None):
        self.project_root = project_root
        self.config = config or self._default_config()
        
        # 备份目录
        self.backup_root = Path(project_root) / '.workbuddy' / 'backups'
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        # 备份记录
        self.backups: Dict[str, BackupRecord] = {}
        self._load_backups()
        
    def _default_config(self) -> Dict[str, Any]:
        return {
            'max_backups': 20,
            'compress': False,
            'auto_cleanup': True,
        }
        
    def create_backup(self, 
                     files: List[str],
                     metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        创建备份
        
        Args:
            files: 要备份的文件列表
            metadata: 元数据
            
        Returns:
            备份ID，失败返回None
        """
        backup_id = self._generate_backup_id()
        backup_path = self.backup_root / backup_id
        
        try:
            # 创建备份目录
            backup_path.mkdir(exist_ok=True)
            
            # 备份文件
            backed_up_files = []
            for file_path in files:
                if not os.path.exists(file_path):
                    continue
                    
                # 计算相对路径
                rel_path = os.path.relpath(file_path, self.project_root)
                target_path = backup_path / rel_path
                
                # 创建父目录
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制文件
                shutil.copy2(file_path, target_path)
                backed_up_files.append(file_path)
                
            if not backed_up_files:
                # 没有文件被备份
                shutil.rmtree(backup_path, ignore_errors=True)
                return None
                
            # 创建记录
            record = BackupRecord(
                backup_id=backup_id,
                files=backed_up_files,
                backup_path=str(backup_path),
                metadata=metadata or {}
            )
            
            self.backups[backup_id] = record
            self._save_backup_record(record)
            
            # 清理旧备份
            if self.config['auto_cleanup']:
                self._cleanup_old_backups()
                
            return backup_id
            
        except Exception as e:
            print(f"创建备份失败: {e}")
            shutil.rmtree(backup_path, ignore_errors=True)
            return None
            
    def restore_backup(self, backup_id: str) -> bool:
        """
        恢复备份
        
        Args:
            backup_id: 备份ID
            
        Returns:
            是否成功恢复
        """
        if backup_id not in self.backups:
            return False
            
        record = self.backups[backup_id]
        backup_path = Path(record.backup_path)
        
        if not backup_path.exists():
            record.status = BackupStatus.CORRUPTED
            return False
            
        try:
            # 恢复文件
            for file_path in record.files:
                rel_path = os.path.relpath(file_path, self.project_root)
                backup_file = backup_path / rel_path
                
                if backup_file.exists():
                    # 确保目标目录存在
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    # 恢复文件
                    shutil.copy2(backup_file, file_path)
                    
            record.status = BackupStatus.RESTORED
            record.restored_at = time.time()
            self._save_backup_record(record)
            
            return True
            
        except Exception as e:
            print(f"恢复备份失败: {e}")
            return False
            
    def delete_backup(self, backup_id: str) -> bool:
        """
        删除备份
        
        Args:
            backup_id: 备份ID
            
        Returns:
            是否成功删除
        """
        if backup_id not in self.backups:
            return False
            
        record = self.backups[backup_id]
        backup_path = Path(record.backup_path)
        
        try:
            # 删除备份目录
            if backup_path.exists():
                shutil.rmtree(backup_path)
                
            # 删除记录文件
            record_file = self.backup_root / f"{backup_id}.json"
            if record_file.exists():
                record_file.unlink()
                
            del self.backups[backup_id]
            return True
            
        except Exception as e:
            print(f"删除备份失败: {e}")
            return False
            
    def list_backups(self) -> List[BackupRecord]:
        """列出所有备份"""
        return list(self.backups.values())
        
    def get_backup(self, backup_id: str) -> Optional[BackupRecord]:
        """获取备份记录"""
        return self.backups.get(backup_id)
        
    def get_stats(self) -> Dict[str, Any]:
        """获取备份统计"""
        total = len(self.backups)
        active = sum(1 for b in self.backups.values() 
                     if b.status == BackupStatus.CREATED)
        restored = sum(1 for b in self.backups.values() 
                       if b.status == BackupStatus.RESTORED)
        
        return {
            'total': total,
            'active': active,
            'restored': restored,
            'backup_dir': str(self.backup_root),
        }
        
    def _generate_backup_id(self) -> str:
        """生成备份ID"""
        import hashlib
        content = f"{self.project_root}_{time.time()}"
        return f"backup_{hashlib.md5(content.encode()).hexdigest()[:8]}"
        
    def _save_backup_record(self, record: BackupRecord):
        """保存备份记录"""
        record_file = self.backup_root / f"{record.backup_id}.json"
        
        data = {
            'backup_id': record.backup_id,
            'files': record.files,
            'backup_path': record.backup_path,
            'status': record.status.value,
            'created_at': record.created_at,
            'restored_at': record.restored_at,
            'metadata': record.metadata,
        }
        
        with open(record_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    def _load_backups(self):
        """加载备份记录"""
        for record_file in self.backup_root.glob('*.json'):
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    import json
                    data = json.load(f)
                    
                record = BackupRecord(
                    backup_id=data['backup_id'],
                    files=data['files'],
                    backup_path=data['backup_path'],
                    status=BackupStatus(data['status']),
                    created_at=data.get('created_at', time.time()),
                    restored_at=data.get('restored_at'),
                    metadata=data.get('metadata', {}),
                )
                
                self.backups[record.backup_id] = record
                
            except Exception:
                pass
                
    def _cleanup_old_backups(self):
        """清理旧备份"""
        max_backups = self.config['max_backups']
        
        if len(self.backups) <= max_backups:
            return
            
        # 按创建时间排序
        sorted_backups = sorted(
            self.backups.values(),
            key=lambda x: x.created_at
        )
        
        # 删除最旧的
        for record in sorted_backups[:len(self.backups) - max_backups]:
            self.delete_backup(record.backup_id)
