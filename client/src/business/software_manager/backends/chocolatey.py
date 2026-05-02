import subprocess
import json
from typing import List, Optional
from . import PackageInfo, PackageManager


class ChocolateyBackend(PackageManager):
    """Chocolatey包管理器后端"""
    
    def get_name(self) -> str:
        return 'chocolatey'
    
    def is_available(self) -> bool:
        """检查Chocolatey是否可用"""
        try:
            result = subprocess.run(
                ['choco', '--version'],
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
                ['choco', 'install', package_id, '-y', '--no-progress'],
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
                ['choco', 'uninstall', package_id, '-y'],
                capture_output=True,
                text=True,
                timeout=120
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
                ['choco', 'list', '--local-only'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            packages = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    name = parts[0].strip()
                    version = parts[1].strip() if len(parts) > 1 else ''
                    packages.append(PackageInfo(
                        id=name.lower().replace(' ', '-'),
                        name=name,
                        version=version,
                        source='chocolatey'
                    ))
            
            return packages
        except Exception:
            return []
    
    def search(self, query: str) -> List[PackageInfo]:
        """搜索软件包"""
        try:
            result = subprocess.run(
                ['choco', 'search', query],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            packages = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    name = parts[0].strip()
                    version = parts[1].strip() if len(parts) > 1 else ''
                    packages.append(PackageInfo(
                        id=name.lower().replace(' ', '-'),
                        name=name,
                        version=version,
                        source='chocolatey'
                    ))
            
            return packages
        except Exception:
            return []
    
    def get_version(self, package_id: str) -> Optional[str]:
        """获取软件包版本"""
        try:
            result = subprocess.run(
                ['choco', 'info', package_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            for line in result.stdout.split('\n'):
                if 'version' in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        return parts[1].strip()
            return None
        except Exception:
            return None