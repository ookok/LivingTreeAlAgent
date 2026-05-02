import subprocess
import json
import re
from typing import List, Optional, Dict, Any
from . import PackageInfo, PackageManager


class WingetBackend(PackageManager):
    """Winget包管理器后端"""
    
    def get_name(self) -> str:
        return 'winget'
    
    def is_available(self) -> bool:
        """检查Winget是否可用"""
        try:
            result = subprocess.run(
                ['winget', '--version'],
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
            process = subprocess.Popen(
                ['winget', 'install', '--id', package_id, '--silent', '--accept-source-agreements', '--accept-package-agreements'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                if callback:
                    callback({'type': 'log', 'message': line.strip()})
                
                if 'Successfully installed' in line:
                    process.wait()
                    return True
            
            process.wait()
            return process.returncode == 0
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def uninstall(self, package_id: str, callback=None) -> bool:
        """卸载软件包"""
        try:
            result = subprocess.run(
                ['winget', 'uninstall', '--id', package_id, '--silent'],
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
                ['winget', 'list'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            packages = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过表头
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    package_id = parts[0]
                    name = parts[1]
                    version = parts[2]
                    packages.append(PackageInfo(
                        id=package_id,
                        name=name,
                        version=version,
                        source='winget'
                    ))
            
            return packages
        except Exception:
            return []
    
    def search(self, query: str) -> List[PackageInfo]:
        """搜索软件包"""
        try:
            result = subprocess.run(
                ['winget', 'search', query],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            packages = []
            lines = result.stdout.strip().split('\n')[1:]
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    package_id = parts[0]
                    name = parts[1]
                    version = parts[2] if len(parts) > 2 else ''
                    packages.append(PackageInfo(
                        id=package_id,
                        name=name,
                        version=version,
                        source='winget'
                    ))
            
            return packages
        except Exception:
            return []
    
    def get_version(self, package_id: str) -> Optional[str]:
        """获取软件包版本"""
        try:
            result = subprocess.run(
                ['winget', 'show', '--id', package_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':')[1].strip()
            return None
        except Exception:
            return None