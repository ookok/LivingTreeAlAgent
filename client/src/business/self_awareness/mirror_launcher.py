"""
镜像启动器 - 启动项目副本进行沙盒测试
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import os
import shutil
import hashlib
import time
import subprocess
from pathlib import Path


class InstanceStatus(Enum):
    """实例状态"""
    PENDING = "pending"
    LAUNCHING = "launching"
    RUNNING = "running"
    TESTING = "testing"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class MirrorInstance:
    """镜像实例"""
    instance_id: str
    source_path: str
    mirror_path: str
    status: InstanceStatus = InstanceStatus.PENDING
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def age(self) -> float:
        """运行时间（秒）"""
        return time.time() - self.created_at


@dataclass
class LaunchConfig:
    """启动配置"""
    mirror_dir: str = "./mirror_instances"
    max_instances: int = 5
    copy_exclude: List[str] = field(default_factory=lambda: [
        '__pycache__', '*.pyc', '.git', 'node_modules',
        '.venv', 'venv', '*.log', '.cache'
    ])
    timeout: float = 300.0  # 5分钟超时
    auto_cleanup: bool = True


class MirrorLauncher:
    """
    镜像启动器
    
    核心功能：
    1. 创建项目副本作为沙盒环境
    2. 隔离测试，避免影响主项目
    3. 自动清理过期实例
    """
    
    def __init__(self, config: Optional[LaunchConfig] = None):
        self.config = config or LaunchConfig()
        self.instances: Dict[str, MirrorInstance] = {}
        self._ensure_mirror_dir()
        
    def _ensure_mirror_dir(self):
        """确保镜像目录存在"""
        os.makedirs(self.config.mirror_dir, exist_ok=True)
        
    def launch(self, source_path: str, 
              metadata: Optional[Dict[str, Any]] = None) -> MirrorInstance:
        """
        启动镜像实例
        
        Args:
            source_path: 源项目路径
            metadata: 元数据
            
        Returns:
            MirrorInstance: 镜像实例
        """
        # 检查实例数量限制
        if len(self.instances) >= self.config.max_instances:
            self._cleanup_oldest()
            
        # 生成实例ID
        instance_id = self._generate_instance_id(source_path)
        
        # 创建镜像路径
        timestamp = int(time.time())
        mirror_path = os.path.join(
            self.config.mirror_dir,
            f"mirror_{instance_id}_{timestamp}"
        )
        
        # 创建实例
        instance = MirrorInstance(
            instance_id=instance_id,
            source_path=source_path,
            mirror_path=mirror_path,
            status=InstanceStatus.LAUNCHING,
            metadata=metadata or {}
        )
        
        # 复制项目到镜像
        self._copy_project(source_path, mirror_path)
        
        instance.status = InstanceStatus.RUNNING
        self.instances[instance_id] = instance
        
        return instance
    
    def stop(self, instance_id: str) -> bool:
        """
        停止镜像实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            是否成功停止
        """
        if instance_id not in self.instances:
            return False
            
        instance = self.instances[instance_id]
        instance.status = InstanceStatus.STOPPED
        
        # 清理镜像目录
        if self.config.auto_cleanup:
            self._cleanup_instance(instance)
            
        return True
    
    def get_instance(self, instance_id: str) -> Optional[MirrorInstance]:
        """获取实例"""
        return self.instances.get(instance_id)
    
    def list_instances(self) -> List[MirrorInstance]:
        """列出所有实例"""
        return list(self.instances.values())
    
    def execute_in_mirror(self, instance_id: str, 
                         command: str,
                         timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        在镜像中执行命令
        
        Args:
            instance_id: 实例ID
            command: 要执行的命令
            timeout: 超时时间
            
        Returns:
            执行结果
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return {'success': False, 'error': 'Instance not found'}
            
        timeout = timeout or self.config.timeout
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=instance.mirror_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Command timeout after {timeout}s'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_instance_id(self, source_path: str) -> str:
        """生成实例ID"""
        content = f"{source_path}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _copy_project(self, source: str, destination: str):
        """复制项目到镜像"""
        if os.path.exists(destination):
            shutil.rmtree(destination)
            
        # 使用shutil复制，排除指定目录
        for item in os.listdir(source):
            if self._should_copy(item):
                src_path = os.path.join(source, item)
                dst_path = os.path.join(destination, item)
                
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path, 
                                  ignore=shutil.ignore_patterns(*self.config.copy_exclude))
                else:
                    shutil.copy2(src_path, dst_path)
                    
    def _should_copy(self, item: str) -> bool:
        """检查是否应该复制"""
        for pattern in self.config.copy_exclude:
            if pattern.startswith('*'):
                if item.endswith(pattern[1:]):
                    return False
            elif pattern in item:
                return False
        return True
    
    def _cleanup_instance(self, instance: MirrorInstance):
        """清理实例"""
        if os.path.exists(instance.mirror_path):
            shutil.rmtree(instance.mirror_path, ignore_errors=True)
            
    def _cleanup_oldest(self):
        """清理最老的实例"""
        if not self.instances:
            return
            
        oldest = min(self.instances.values(), key=lambda x: x.created_at)
        self.stop(oldest.instance_id)
        
    def cleanup_all(self):
        """清理所有实例"""
        for instance_id in list(self.instances.keys()):
            self.stop(instance_id)
