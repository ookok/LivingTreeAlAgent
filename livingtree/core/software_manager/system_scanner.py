import winreg
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess


class InstalledSoftware:
    """已安装软件信息"""
    def __init__(self, name: str, version: str = '', publisher: str = '', install_path: str = '', uninstall_string: str = '', icon_path: str = ''):
        self.name = name
        self.version = version
        self.publisher = publisher
        self.install_path = install_path
        self.uninstall_string = uninstall_string
        self.icon_path = icon_path
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'publisher': self.publisher,
            'install_path': self.install_path,
            'uninstall_string': self.uninstall_string,
            'icon_path': self.icon_path
        }


class SystemScanner:
    """系统软件扫描器"""
    
    def __init__(self):
        self.registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
    
    def scan_registry(self) -> List[InstalledSoftware]:
        """扫描注册表获取已安装软件"""
        software_list = []
        
        for reg_path in self.registry_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ)
                try:
                    index = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, index)
                            subkey = winreg.OpenKey(key, subkey_name)
                            
                            software = self._parse_registry_subkey(subkey)
                            if software and software.name:
                                software_list.append(software)
                            
                            winreg.CloseKey(subkey)
                            index += 1
                        except OSError:
                            break
                finally:
                    winreg.CloseKey(key)
            except WindowsError:
                pass
        
        return software_list
    
    def _parse_registry_subkey(self, subkey) -> Optional[InstalledSoftware]:
        """解析注册表子项"""
        try:
            name = self._get_registry_value(subkey, 'DisplayName')
            if not name or name.startswith('{'):
                return None
            
            version = self._get_registry_value(subkey, 'DisplayVersion', '')
            publisher = self._get_registry_value(subkey, 'Publisher', '')
            install_path = self._get_registry_value(subkey, 'InstallLocation', '')
            uninstall_string = self._get_registry_value(subkey, 'UninstallString', '')
            icon_path = self._get_registry_value(subkey, 'DisplayIcon', '')
            
            return InstalledSoftware(
                name=name,
                version=version,
                publisher=publisher,
                install_path=install_path,
                uninstall_string=uninstall_string,
                icon_path=icon_path
            )
        except Exception:
            return None
    
    def _get_registry_value(self, key, value_name: str, default: str = '') -> str:
        """获取注册表值"""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else default
        except WindowsError:
            return default
    
    def scan_start_menu(self) -> List[Dict[str, str]]:
        """扫描开始菜单快捷方式"""
        start_menu_paths = [
            os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
            os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        ]
        
        shortcuts = []
        
        for path in start_menu_paths:
            if os.path.exists(path):
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.endswith('.lnk'):
                            shortcuts.append({
                                'name': os.path.splitext(file)[0],
                                'path': os.path.join(root, file)
                            })
        
        return shortcuts
    
    def scan_path_executables(self) -> List[str]:
        """扫描系统PATH中的可执行文件"""
        executables = []
        path_dirs = os.environ.get('PATH', '').split(';')
        
        for path_dir in path_dirs:
            if os.path.isdir(path_dir):
                try:
                    for file in os.listdir(path_dir):
                        if file.endswith('.exe'):
                            executables.append(file)
                except PermissionError:
                    pass
        
        return list(set(executables))
    
    def get_installed_python_packages(self) -> List[Dict[str, str]]:
        """获取已安装的Python包"""
        packages = []
        try:
            result = subprocess.run(
                ['pip', 'list', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                import json
                packages = json.loads(result.stdout)
        except Exception:
            pass
        return packages
    
    def scan_all(self) -> Dict[str, Any]:
        """执行全面扫描"""
        return {
            'registry_software': [s.to_dict() for s in self.scan_registry()],
            'start_menu_shortcuts': self.scan_start_menu(),
            'path_executables': self.scan_path_executables(),
            'python_packages': self.get_installed_python_packages()
        }
    
    def match_with_metadata(self, metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将扫描结果与元数据进行匹配"""
        scanned = self.scan_registry()
        matched = []
        unmatched = []
        
        for software in scanned:
            matched_info = None
            
            for metadata in metadata_list:
                metadata_name = metadata.get('name', '').lower()
                software_name = software.name.lower()
                
                if metadata_name in software_name or software_name in metadata_name:
                    matched_info = {
                        **software.to_dict(),
                        'metadata_match': metadata,
                        'match_score': self._calculate_match_score(software.name, metadata.get('name', ''))
                    }
                    break
            
            if matched_info:
                matched.append(matched_info)
            else:
                unmatched.append(software.to_dict())
        
        return {
            'matched': matched,
            'unmatched': unmatched
        }
    
    def _calculate_match_score(self, name1: str, name2: str) -> float:
        """计算名称匹配分数"""
        name1 = name1.lower()
        name2 = name2.lower()
        
        if name1 == name2:
            return 1.0
        
        if name1 in name2 or name2 in name1:
            return 0.8
        
        common_words = set(name1.split()) & set(name2.split())
        if common_words:
            return 0.5 + len(common_words) * 0.1
        
        return 0.0


system_scanner = SystemScanner()