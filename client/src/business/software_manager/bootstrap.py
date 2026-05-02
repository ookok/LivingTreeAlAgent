import subprocess
import requests
import tempfile
import os
import sys
import ctypes
from pathlib import Path
from typing import Optional, Callable


class BootstrapInstaller:
    """自举安装器 - 在没有包管理器时自动安装"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / 'software_manager_bootstrap'
        self.temp_dir.mkdir(exist_ok=True)
    
    def _is_admin(self) -> bool:
        """检查是否以管理员身份运行"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def _elevate(self) -> bool:
        """提升权限到管理员"""
        try:
            script_path = sys.argv[0]
            params = ' '.join(sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                f'"{script_path}" {params}',
                None,
                1
            )
            return True
        except Exception as e:
            print(f"Failed to elevate: {e}")
            return False
    
    def install_winget(self, callback: Optional[Callable] = None) -> bool:
        """安装Winget"""
        if not self._is_admin():
            if callback:
                callback({'type': 'error', 'message': '需要管理员权限安装Winget'})
            return False
        
        try:
            if callback:
                callback({'type': 'status', 'state': 'downloading', 'message': '正在下载Winget安装包...'})
            
            url = "https://github.com/microsoft/winget-cli/releases/download/v1.7.10582/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle"
            download_path = self.temp_dir / 'winget.msixbundle'
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if callback:
                callback({'type': 'status', 'state': 'installing', 'message': '正在安装Winget...'})
            
            result = subprocess.run(
                ['powershell', '-Command', f'Add-AppxPackage -Path "{download_path}"'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                if callback:
                    callback({'type': 'status', 'state': 'completed', 'message': 'Winget安装成功'})
                return True
            else:
                if callback:
                    callback({'type': 'error', 'message': f'Winget安装失败: {result.stderr}'})
                return False
                
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def install_chocolatey(self, callback: Optional[Callable] = None) -> bool:
        """安装Chocolatey"""
        if not self._is_admin():
            if callback:
                callback({'type': 'error', 'message': '需要管理员权限安装Chocolatey'})
            return False
        
        try:
            if callback:
                callback({'type': 'status', 'state': 'installing', 'message': '正在安装Chocolatey...'})
            
            result = subprocess.run(
                ['powershell', '-Command', 'Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString(\'https://community.chocolatey.org/install.ps1\'))'],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode == 0:
                if callback:
                    callback({'type': 'status', 'state': 'completed', 'message': 'Chocolatey安装成功'})
                return True
            else:
                if callback:
                    callback({'type': 'error', 'message': f'Chocolatey安装失败: {result.stderr}'})
                return False
                
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def install_scoop(self, callback: Optional[Callable] = None) -> bool:
        """安装Scoop"""
        try:
            if callback:
                callback({'type': 'status', 'state': 'installing', 'message': '正在安装Scoop...'})
            
            result = subprocess.run(
                ['powershell', '-Command', 'Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; irm get.scoop.sh | iex'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                if callback:
                    callback({'type': 'status', 'state': 'completed', 'message': 'Scoop安装成功'})
                return True
            else:
                if callback:
                    callback({'type': 'error', 'message': f'Scoop安装失败: {result.stderr}'})
                return False
                
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def detect_and_install(self, callback: Optional[Callable] = None) -> Optional[str]:
        """检测并安装合适的包管理器"""
        from .backends import WingetBackend, ChocolateyBackend, ScoopBackend
        
        backends = [
            ('winget', WingetBackend(), self.install_winget),
            ('chocolatey', ChocolateyBackend(), self.install_chocolatey),
            ('scoop', ScoopBackend(), self.install_scoop)
        ]
        
        # 检查是否已有包管理器
        for name, backend, installer in backends:
            if backend.is_available():
                if callback:
                    callback({'type': 'status', 'state': 'detected', 'message': f'已检测到{name}'})
                return name
        
        # 如果没有，尝试安装
        for name, backend, installer in backends:
            if callback:
                callback({'type': 'status', 'state': 'bootstrapping', 'message': f'正在安装{name}...'})
            
            success = installer(callback)
            if success and backend.is_available():
                return name
        
        return None


bootstrap = BootstrapInstaller()