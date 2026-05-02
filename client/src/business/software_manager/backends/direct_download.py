import subprocess
import json
import requests
import tempfile
import zipfile
import tarfile
import os
from pathlib import Path
from typing import List, Optional
from . import PackageInfo, PackageManager


class DirectDownloadBackend(PackageManager):
    """直接下载安装后端（备用方案）"""
    
    def __init__(self):
        self.download_dir = Path(tempfile.gettempdir()) / 'software_manager'
        self.download_dir.mkdir(exist_ok=True)
    
    def get_name(self) -> str:
        return 'direct_download'
    
    def is_available(self) -> bool:
        """直接下载总是可用"""
        return True
    
    def install(self, package_id: str, callback=None) -> bool:
        """安装软件包（直接下载）"""
        try:
            from ..metadata import software_metadata
            
            pkg_info = software_metadata.get(package_id)
            if not pkg_info or 'download_url' not in pkg_info:
                if callback:
                    callback({'type': 'error', 'message': f'No download URL for {package_id}'})
                return False
            
            url = pkg_info['download_url']
            filename = url.split('/')[-1]
            download_path = self.download_dir / filename
            
            if callback:
                callback({'type': 'status', 'state': 'downloading', 'message': f'Downloading {filename}...'})
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and callback:
                            progress = int((downloaded / total_size) * 100)
                            callback({'type': 'progress', 'progress': progress})
            
            if callback:
                callback({'type': 'status', 'state': 'installing', 'message': f'Installing {filename}...'})
            
            if filename.endswith('.exe'):
                result = subprocess.run(
                    [str(download_path), '/S'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                success = result.returncode == 0
            elif filename.endswith('.zip'):
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    install_dir = Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / pkg_info.get('name', package_id)
                    install_dir.mkdir(exist_ok=True)
                    zip_ref.extractall(install_dir)
                success = True
            else:
                success = False
            
            if success and callback:
                callback({'type': 'status', 'state': 'completed', 'message': 'Installation completed'})
            
            return success
            
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def uninstall(self, package_id: str, callback=None) -> bool:
        """卸载软件包"""
        try:
            from ..metadata import software_metadata
            
            pkg_info = software_metadata.get(package_id)
            if pkg_info and 'uninstall_path' in pkg_info:
                uninstall_path = Path(pkg_info['uninstall_path'])
                if uninstall_path.exists():
                    result = subprocess.run(
                        [str(uninstall_path), '/S'],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    return result.returncode == 0
            
            return False
        except Exception as e:
            if callback:
                callback({'type': 'error', 'message': str(e)})
            return False
    
    def list_installed(self) -> List[PackageInfo]:
        """列出已安装的软件"""
        return []
    
    def search(self, query: str) -> List[PackageInfo]:
        """搜索软件包"""
        return []
    
    def get_version(self, package_id: str) -> Optional[str]:
        """获取软件包版本"""
        return None