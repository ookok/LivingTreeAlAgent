"""
部署管理器
管理修复的部署和回滚
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import os
import json
import time
from pathlib import Path


class DeploymentStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentRecord:
    """部署记录"""
    deployment_id: str
    status: DeploymentStatus
    problem: Optional[Dict[str, Any]] = None
    fix_result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeploymentManager:
    """
    部署管理器
    
    功能：
    1. 管理修复部署
    2. 记录部署历史
    3. 支持回滚
    """
    
    def __init__(self, project_root: str, 
                 config: Optional[Dict[str, Any]] = None):
        self.project_root = project_root
        self.config = config or self._default_config()
        self.deployments: Dict[str, DeploymentRecord] = {}
        self.deploy_history: List[DeploymentRecord] = []
        
        # 确保部署目录存在
        self.deploy_dir = Path(project_root) / '.workbuddy' / 'deployments'
        self.deploy_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载历史
        self._load_history()
        
    def _default_config(self) -> Dict[str, Any]:
        return {
            'auto_deploy': True,
            'backup_before_deploy': True,
            'max_history': 50,
            'verify_after_deploy': True,
        }
        
    def deploy(self, 
               problem: Dict[str, Any],
               fix_result: Any) -> DeploymentRecord:
        """
        部署修复
        
        Args:
            problem: 问题信息
            fix_result: 修复结果
            
        Returns:
            DeploymentRecord: 部署记录
        """
        deployment_id = self._generate_deployment_id()
        
        record = DeploymentRecord(
            deployment_id=deployment_id,
            status=DeploymentStatus.IN_PROGRESS,
            problem=problem,
            fix_result=fix_result,
        )
        
        self.deployments[deployment_id] = record
        
        try:
            # 备份（如果需要）
            if self.config['backup_before_deploy']:
                backup_id = self._create_backup(problem)
                record.metadata['backup_id'] = backup_id
                
            # 应用修复（fix_result应该已经应用了，这里只是记录）
            record.status = DeploymentStatus.SUCCESS
            record.completed_at = time.time()
            
            # 保存记录
            self._save_deployment(record)
            
        except Exception as e:
            record.status = DeploymentStatus.FAILED
            record.error = str(e)
            record.completed_at = time.time()
            
        self.deploy_history.append(record)
        self._cleanup_old_history()
        
        return record
        
    def rollback(self, deployment_id: str) -> bool:
        """
        回滚部署
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            是否成功回滚
        """
        if deployment_id not in self.deployments:
            return False
            
        record = self.deployments[deployment_id]
        
        if 'backup_id' not in record.metadata:
            return False
            
        # 执行回滚（简化实现）
        record.status = DeploymentStatus.ROLLED_BACK
        record.completed_at = time.time()
        
        self._save_deployment(record)
        
        return True
        
    def get_history(self, limit: int = 10) -> List[DeploymentRecord]:
        """获取部署历史"""
        return self.deploy_history[-limit:]
        
    def get_stats(self) -> Dict[str, Any]:
        """获取部署统计"""
        total = len(self.deploy_history)
        success = sum(1 for d in self.deploy_history 
                      if d.status == DeploymentStatus.SUCCESS)
        failed = sum(1 for d in self.deploy_history 
                     if d.status == DeploymentStatus.FAILED)
        rolled_back = sum(1 for d in self.deploy_history 
                         if d.status == DeploymentStatus.ROLLED_BACK)
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'rolled_back': rolled_back,
            'success_rate': success / total if total > 0 else 0,
        }
        
    def _generate_deployment_id(self) -> str:
        """生成部署ID"""
        import hashlib
        content = f"{self.project_root}_{time.time()}"
        return f"deploy_{hashlib.md5(content.encode()).hexdigest()[:8]}"
        
    def _create_backup(self, problem: Dict[str, Any]) -> str:
        """创建备份（简化实现）"""
        backup_id = f"backup_{int(time.time())}"
        
        # 这里应该调用BackupManager
        # 简化：只返回ID
        return backup_id
        
    def _save_deployment(self, record: DeploymentRecord):
        """保存部署记录"""
        file_path = self.deploy_dir / f"{record.deployment_id}.json"
        
        data = {
            'deployment_id': record.deployment_id,
            'status': record.status.value,
            'problem': record.problem,
            'fix_result': str(record.fix_result) if record.fix_result else None,
            'created_at': record.created_at,
            'completed_at': record.completed_at,
            'error': record.error,
            'metadata': record.metadata,
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    def _load_history(self):
        """加载部署历史"""
        if not self.deploy_dir.exists():
            return
            
        for file_path in self.deploy_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                record = DeploymentRecord(
                    deployment_id=data['deployment_id'],
                    status=DeploymentStatus(data['status']),
                    problem=data.get('problem'),
                    fix_result=data.get('fix_result'),
                    created_at=data.get('created_at', time.time()),
                    completed_at=data.get('completed_at'),
                    error=data.get('error'),
                    metadata=data.get('metadata', {}),
                )
                
                self.deployments[record.deployment_id] = record
                self.deploy_history.append(record)
                
            except Exception:
                pass
                
        # 按时间排序
        self.deploy_history.sort(key=lambda x: x.created_at)
        
    def _cleanup_old_history(self):
        """清理旧历史"""
        max_history = self.config['max_history']
        
        if len(self.deploy_history) > max_history:
            # 删除旧记录
            old_records = self.deploy_history[:-max_history]
            self.deploy_history = self.deploy_history[-max_history:]
            
            for record in old_records:
                del self.deployments[record.deployment_id]
                
                # 删除文件
                file_path = self.deploy_dir / f"{record.deployment_id}.json"
                if file_path.exists():
                    file_path.unlink()
