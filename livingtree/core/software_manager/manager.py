import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from .backends import PackageManager, PackageInfo, InstallStatus
from .backends.winget import WingetBackend
from .backends.chocolatey import ChocolateyBackend
from .backends.scoop import ScoopBackend
from .backends.direct_download import DirectDownloadBackend
from .bootstrap import BootstrapInstaller
from .metadata import metadata_manager
from .system_scanner import system_scanner


class SoftwareManager:
    """软件生命周期管理主类"""
    
    def __init__(self):
        self.backends: Dict[str, PackageManager] = {
            'winget': WingetBackend(),
            'chocolatey': ChocolateyBackend(),
            'scoop': ScoopBackend(),
            'direct_download': DirectDownloadBackend()
        }
        self.active_backend: Optional[PackageManager] = None
        self.bootstrap = BootstrapInstaller()
        self.installation_status: Dict[str, Dict[str, Any]] = {}
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        """添加状态回调"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """移除状态回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _notify(self, message: Dict[str, Any]):
        """通知所有回调"""
        for callback in self.callbacks:
            try:
                callback(message)
            except:
                pass
    
    def detect_backend(self) -> Optional[str]:
        """检测并选择合适的包管理器"""
        for name, backend in self.backends.items():
            if backend.is_available():
                self.active_backend = backend
                return name
        
        return None
    
    def bootstrap_backend(self, callback: Optional[Callable] = None) -> Optional[str]:
        """自举安装包管理器"""
        def bootstrap_notify(msg):
            self._notify(msg)
            if callback:
                callback(msg)
        
        result = self.bootstrap.detect_and_install(bootstrap_notify)
        if result:
            self.active_backend = self.backends.get(result)
        return result
    
    def get_available_backends(self) -> List[str]:
        """获取可用的包管理器列表"""
        available = []
        for name, backend in self.backends.items():
            if backend.is_available():
                available.append(name)
        return available
    
    def install_software(self, software_id: str) -> bool:
        """安装软件"""
        software = metadata_manager.get_by_id(software_id)
        if not software:
            self._notify({'type': 'error', 'pkg': software_id, 'message': '软件不存在'})
            return False
        
        if self.active_backend is None:
            self._notify({'type': 'error', 'pkg': software_id, 'message': '没有可用的包管理器'})
            return False
        
        backend_name = software.get('backend', 'winget')
        backend = self.backends.get(backend_name)
        
        if not backend or not backend.is_available():
            backend = self.active_backend
        
        package_id = software.get('package_id', software_id)
        
        self._notify({'type': 'status', 'pkg': software_id, 'state': InstallStatus.DETECTING})
        
        def install_callback(msg):
            if msg.get('type') == 'status':
                self._notify({'type': 'status', 'pkg': software_id, 'state': msg.get('state'), 'message': msg.get('message')})
            elif msg.get('type') == 'progress':
                self._notify({'type': 'progress', 'pkg': software_id, 'progress': msg.get('progress')})
            elif msg.get('type') == 'log':
                self._notify({'type': 'log', 'pkg': software_id, 'message': msg.get('message')})
            elif msg.get('type') == 'error':
                self._notify({'type': 'status', 'pkg': software_id, 'state': InstallStatus.FAILED, 'message': msg.get('message')})
        
        self._notify({'type': 'status', 'pkg': software_id, 'state': InstallStatus.DOWNLOADING})
        
        success = backend.install(package_id, install_callback)
        
        if success:
            self._notify({'type': 'status', 'pkg': software_id, 'state': InstallStatus.COMPLETED})
            metadata_manager.record_install(software_id, True, datetime.now().isoformat())
        else:
            self._notify({'type': 'status', 'pkg': software_id, 'state': InstallStatus.FAILED})
            metadata_manager.record_install(software_id, False, datetime.now().isoformat())
        
        self._notify({'type': 'result', 'pkg': software_id, 'success': success})
        return success
    
    def uninstall_software(self, software_id: str) -> bool:
        """卸载软件"""
        software = metadata_manager.get_by_id(software_id)
        if not software:
            self._notify({'type': 'error', 'pkg': software_id, 'message': '软件不存在'})
            return False
        
        backend_name = software.get('backend', 'winget')
        backend = self.backends.get(backend_name)
        
        if not backend or not backend.is_available():
            if self.active_backend:
                backend = self.active_backend
            else:
                self._notify({'type': 'error', 'pkg': software_id, 'message': '没有可用的包管理器'})
                return False
        
        package_id = software.get('package_id', software_id)
        
        success = backend.uninstall(package_id)
        
        self._notify({'type': 'result', 'pkg': software_id, 'success': success})
        return success
    
    def list_installed(self) -> List[Dict[str, Any]]:
        """列出已安装的软件"""
        installed = []
        
        if self.active_backend:
            packages = self.active_backend.list_installed()
            for pkg in packages:
                installed.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'version': pkg.version,
                    'source': pkg.source,
                    'description': pkg.description
                })
        
        return installed
    
    def search_software(self, query: str) -> List[Dict[str, Any]]:
        """搜索软件"""
        # 先从本地元数据搜索
        local_results = metadata_manager.search(query)
        
        # 再从包管理器搜索
        if self.active_backend:
            backend_results = self.active_backend.search(query)
            for pkg in backend_results:
                exists = any(r.get('id') == pkg.id for r in local_results)
                if not exists:
                    local_results.append({
                        'id': pkg.id,
                        'name': pkg.name,
                        'version': pkg.version,
                        'source': pkg.source,
                        'description': pkg.description
                    })
        
        return local_results
    
    def get_software_info(self, software_id: str) -> Optional[Dict[str, Any]]:
        """获取软件信息"""
        return metadata_manager.get_by_id(software_id)
    
    def get_categories(self) -> Dict[str, Dict[str, str]]:
        """获取所有类别"""
        return metadata_manager.get_categories()
    
    def get_all_software(self) -> List[Dict[str, Any]]:
        """获取所有软件"""
        return metadata_manager.get_all_software()
    
    def get_install_history(self) -> Dict[str, Any]:
        """获取安装历史"""
        return metadata_manager.get_install_history()
    
    def scan_system(self) -> Dict[str, Any]:
        """扫描系统已安装软件"""
        return system_scanner.scan_all()
    
    def match_system_software(self) -> Dict[str, Any]:
        """匹配系统软件与元数据"""
        all_software = self.get_all_software()
        return system_scanner.match_with_metadata(all_software)
    
    def get_system_overview(self) -> Dict[str, Any]:
        """获取系统概览信息"""
        scan_result = self.scan_system()
        match_result = self.match_system_software()
        
        return {
            'total_scanned': len(scan_result['registry_software']),
            'matched_count': len(match_result['matched']),
            'unmatched_count': len(match_result['unmatched']),
            'python_packages_count': len(scan_result['python_packages']),
            'path_executables_count': len(scan_result['path_executables']),
            'matched': match_result['matched'],
            'unmatched': match_result['unmatched'][:20]  # 限制数量
        }


software_manager = SoftwareManager()