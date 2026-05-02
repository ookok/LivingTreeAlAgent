from typing import List, Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod


class PackageInfo:
    """软件包信息"""
    def __init__(self, id: str, name: str, version: str, source: str, description: str = ""):
        self.id = id
        self.name = name
        self.version = version
        self.source = source
        self.description = description
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'source': self.source,
            'description': self.description
        }


class InstallStatus:
    """安装状态"""
    PENDING = 'pending'
    DETECTING = 'detecting'
    DOWNLOADING = 'downloading'
    INSTALLING = 'installing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class PackageManager(ABC):
    """包管理器抽象接口"""
    
    @abstractmethod
    def get_name(self) -> str:
        """获取包管理器名称"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查包管理器是否可用"""
        pass
    
    @abstractmethod
    def install(self, package_id: str, callback=None) -> bool:
        """安装软件包"""
        pass
    
    @abstractmethod
    def uninstall(self, package_id: str, callback=None) -> bool:
        """卸载软件包"""
        pass
    
    @abstractmethod
    def list_installed(self) -> List[PackageInfo]:
        """列出已安装的软件"""
        pass
    
    @abstractmethod
    def search(self, query: str) -> List[PackageInfo]:
        """搜索软件包"""
        pass
    
    @abstractmethod
    def get_version(self, package_id: str) -> Optional[str]:
        """获取软件包版本"""
        pass


__all__ = ['PackageInfo', 'InstallStatus', 'PackageManager']