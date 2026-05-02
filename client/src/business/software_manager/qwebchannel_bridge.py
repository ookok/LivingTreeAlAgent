from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QJsonValue
from PyQt6.QtWebChannel import QWebChannel
from typing import Dict, Any, List, Optional
import json

from .manager import software_manager
from .system_scanner import system_scanner


class SoftwareManagerBridge(QObject):
    """Qt WebChannel通信桥接类"""
    
    messageReceived = pyqtSignal(str)
    statusChanged = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._init_callbacks()
    
    def _init_callbacks(self):
        """初始化回调函数"""
        def handle_message(msg: Dict[str, Any]):
            message_json = json.dumps(msg)
            self.messageReceived.emit(message_json)
        
        software_manager.add_callback(handle_message)
    
    @pyqtSlot(str, result=str)
    def call(self, message_json: str) -> str:
        """处理前端调用"""
        try:
            message = json.loads(message_json)
            action = message.get('action')
            
            if action == 'get_software_list':
                return self._handle_get_software_list()
            elif action == 'search_software':
                return self._handle_search_software(message.get('query', ''))
            elif action == 'install_software':
                return self._handle_install_software(message.get('software_id'))
            elif action == 'uninstall_software':
                return self._handle_uninstall_software(message.get('software_id'))
            elif action == 'get_installed':
                return self._handle_get_installed()
            elif action == 'get_categories':
                return self._handle_get_categories()
            elif action == 'get_backend_status':
                return self._handle_get_backend_status()
            elif action == 'scan_system':
                return self._handle_scan_system()
            elif action == 'get_system_overview':
                return self._handle_get_system_overview()
            elif action == 'get_python_packages':
                return self._handle_get_python_packages()
            else:
                return json.dumps({'error': f'Unknown action: {action}'})
        
        except Exception as e:
            return json.dumps({'error': str(e)})
    
    def _handle_get_software_list(self) -> str:
        """获取软件列表"""
        software = software_manager.get_all_software()
        categories = software_manager.get_categories()
        return json.dumps({
            'success': True,
            'software': software,
            'categories': categories
        })
    
    def _handle_search_software(self, query: str) -> str:
        """搜索软件"""
        results = software_manager.search_software(query)
        return json.dumps({
            'success': True,
            'results': results
        })
    
    def _handle_install_software(self, software_id: str) -> str:
        """安装软件"""
        success = software_manager.install_software(software_id)
        return json.dumps({
            'success': success
        })
    
    def _handle_uninstall_software(self, software_id: str) -> str:
        """卸载软件"""
        success = software_manager.uninstall_software(software_id)
        return json.dumps({
            'success': success
        })
    
    def _handle_get_installed(self) -> str:
        """获取已安装软件"""
        installed = software_manager.list_installed()
        return json.dumps({
            'success': True,
            'installed': installed
        })
    
    def _handle_get_categories(self) -> str:
        """获取分类"""
        categories = software_manager.get_categories()
        return json.dumps({
            'success': True,
            'categories': categories
        })
    
    def _handle_get_backend_status(self) -> str:
        """获取包管理器状态"""
        backend = software_manager.detect_backend()
        available = software_manager.get_available_backends()
        return json.dumps({
            'success': True,
            'backend': backend,
            'available': available
        })
    
    def _handle_scan_system(self) -> str:
        """扫描系统"""
        result = software_manager.scan_system()
        return json.dumps({
            'success': True,
            'data': result
        })
    
    def _handle_get_system_overview(self) -> str:
        """获取系统概览"""
        result = software_manager.get_system_overview()
        return json.dumps({
            'success': True,
            'data': result
        })
    
    def _handle_get_python_packages(self) -> str:
        """获取Python包"""
        packages = system_scanner.get_installed_python_packages()
        return json.dumps({
            'success': True,
            'packages': packages
        })


class WebChannelSetup:
    """WebChannel设置助手"""
    
    @staticmethod
    def setup(web_engine_view):
        """设置WebChannel通信"""
        channel = QWebChannel()
        bridge = SoftwareManagerBridge()
        
        channel.registerObject('softwareManager', bridge)
        web_engine_view.page().setWebChannel(channel)
        
        return bridge