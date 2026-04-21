"""
UI 加载器

按需加载 UI 组件，支持异步加载和错误处理
"""

import logging
import importlib
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class UILoader(QThread):
    """
    UI 加载器
    异步加载 UI 组件
    """
    
    # 信号
    loaded = pyqtSignal(str, object)  # 加载完成
    failed = pyqtSignal(str, str)  # 加载失败
    progress = pyqtSignal(str, int)  # 加载进度
    
    def __init__(self, module_name: str, class_name: str, panel_id: str):
        """
        初始化 UI 加载器
        
        Args:
            module_name: 模块名称
            class_name: 类名称
            panel_id: 面板 ID
        """
        super().__init__()
        self.module_name = module_name
        self.class_name = class_name
        self.panel_id = panel_id
        self._stop_flag = False
    
    def run(self):
        """
        运行加载
        """
        try:
            self.progress.emit(self.panel_id, 10)
            
            # 导入模块
            module = importlib.import_module(self.module_name)
            self.progress.emit(self.panel_id, 50)
            
            # 获取类
            cls = getattr(module, self.class_name)
            self.progress.emit(self.panel_id, 80)
            
            # 实例化
            instance = cls()
            self.progress.emit(self.panel_id, 100)
            
            # 发送加载完成信号
            self.loaded.emit(self.panel_id, instance)
            
        except Exception as e:
            logger.error(f"Failed to load UI component {self.panel_id}: {e}")
            self.failed.emit(self.panel_id, str(e))
    
    def stop(self):
        """
        停止加载
        """
        self._stop_flag = True


class UILoaderManager:
    """
    UI 加载器管理器
    管理多个 UI 加载器
    """
    
    def __init__(self):
        self._loaders: Dict[str, UILoader] = {}
    
    def load_ui(self, panel_id: str, module_name: str, class_name: str, 
                on_loaded: Optional[Callable] = None, 
                on_failed: Optional[Callable] = None, 
                on_progress: Optional[Callable] = None) -> UILoader:
        """
        加载 UI 组件
        
        Args:
            panel_id: 面板 ID
            module_name: 模块名称
            class_name: 类名称
            on_loaded: 加载完成回调
            on_failed: 加载失败回调
            on_progress: 加载进度回调
            
        Returns:
            UILoader: 加载器实例
        """
        # 如果已经在加载，返回现有加载器
        if panel_id in self._loaders:
            return self._loaders[panel_id]
        
        # 创建加载器
        loader = UILoader(module_name, class_name, panel_id)
        
        # 连接信号
        if on_loaded:
            loader.loaded.connect(on_loaded)
        if on_failed:
            loader.failed.connect(on_failed)
        if on_progress:
            loader.progress.connect(on_progress)
        
        # 启动加载
        loader.start()
        
        # 保存加载器
        self._loaders[panel_id] = loader
        
        return loader
    
    def cancel_load(self, panel_id: str):
        """
        取消加载
        
        Args:
            panel_id: 面板 ID
        """
        if panel_id in self._loaders:
            loader = self._loaders[panel_id]
            loader.stop()
            del self._loaders[panel_id]
    
    def clear(self):
        """
        清空所有加载器
        """
        for panel_id in list(self._loaders.keys()):
            self.cancel_load(panel_id)
