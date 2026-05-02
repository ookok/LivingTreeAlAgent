import subprocess
import json
from typing import List, Optional
from . import PackageInfo, PackageManager


class ScoopBackend(PackageManager):
    """Scoop包管理器后端"""
    
    def get_name(self) -> str:
        return 'scoop'
    
    def is_available(self) -> bool:
        """检查Scoop是否可用"""
        try:
            result = subprocess.run(
                ['scoop', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
            return False
    
    def install(self, package_id: str, callback=None) -> bool:
        """安装软件包"""
        try:
            result = subprocess.run(
                ['scoop', 'install', package_id],
                capture_output=True,
                text=True,
                timeout=300,
                stderr=subprocess.STDOUT
            )
            
            if callback:
                callback({'type': 'log', 'message': result.stdout})
            
            return result.returncode == 0
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def uninstall(self, package_id: str, callback=None) -> bool:
        """卸载软件包"""
        try:
            result = subprocess.run(
                ['scoop', 'uninstall', package_id],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def list_installed(self) -> List[PackageInfo]:
        """列出已安装的软件"""
        try:
            result = subprocess.run(
                ['scoop', 'list'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            packages = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过表头
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    packages.append(PackageInfo(
                        id=name,
                        name=name,
                        version=version,
                        source='scoop'
                    ))
            
            return packages
        except Exception:
            return []
    
    def search(self, query: str) -> List[PackageInfo]:
        """搜索软件包"""
        try:
            result = subprocess.run(
                ['scoop', 'search', query],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            packages = []
            lines = result.stdout.strip().split('\n')[1:]
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    packages.append(PackageInfo(
                        id=name,
                        name=name,
                        version=version,
                        source='scoop'
                    ))
            
            return packages
        except Exception:
            return []
    
    def get_version(self, package_id: str) -> Optional[str]:
        """获取软件包版本"""
        try:
            result = subprocess.run(
                ['scoop', 'info', package_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            for line in result.stdout.split('\n'):
                if 'Version:' in line:
                    return line.split(':')[1].strip()
            return None
        except Exception:
            return None