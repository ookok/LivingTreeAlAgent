"""
A2UI 核心实现

核心组件：
- A2UIManager - 管理所有 A2UI 面板
- A2UIPanel - A2UI 面板基类
- A2UIConfig - A2UI 配置类
"""

import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QStackedWidget

logger = logging.getLogger(__name__)


class A2UIConfig:
    """
    A2UI 配置类
    管理 A2UI 相关的配置
    """
    
    def __init__(self):
        self.auto_load = True  # 自动加载 UI 组件
        self.fallback_enabled = True  # 启用降级方案
        self.progress_enabled = True  # 启用进度提示
        self.config_quick_edit = True  # 启用快捷配置
        self.loading_timeout = 10  # 加载超时时间（秒）
        self.fallback_delay = 2  # 降级延迟（秒）


class A2UIPanel(QWidget):
    """
    A2UI 面板基类
    所有 A2UI 面板都应该继承自此类
    """
    
    # 信号
    panel_loaded = pyqtSignal(str)  # 面板加载完成
    panel_fallback = pyqtSignal(str)  # 面板降级
    panel_error = pyqtSignal(str, str)  # 面板错误
    
    def __init__(self, panel_id: str, title: str):
        """
        初始化 A2UI 面板
        
        Args:
            panel_id: 面板 ID
            title: 面板标题
        """
        super().__init__()
        self.panel_id = panel_id
        self.title = title
        self.loaded = False
        self.fallback_active = False
        self._main_layout = QVBoxLayout(self)
        self._stack = QStackedWidget(self)
        self._main_layout.addWidget(self._stack)
        
        # 创建加载界面
        self._loading_widget = QWidget()
        loading_layout = QVBoxLayout(self._loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(QLabel("加载中..."))
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        loading_layout.addWidget(self._progress_bar)
        self._stack.addWidget(self._loading_widget)
        
        # 创建降级界面
        self._fallback_widget = QWidget()
        fallback_layout = QVBoxLayout(self._fallback_widget)
        fallback_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fallback_layout.addWidget(QLabel("服务不可用，已切换到降级模式"))
        self._fallback_info = QLabel("")
        fallback_layout.addWidget(self._fallback_info)
        self._stack.addWidget(self._fallback_widget)
        
        # 创建主界面
        self._main_widget = QWidget()
        self._main_layout = QVBoxLayout(self._main_widget)
        self._stack.addWidget(self._main_widget)
        
        # 默认显示加载界面
        self._stack.setCurrentWidget(self._loading_widget)
    
    async def load(self) -> bool:
        """
        加载面板
        
        Returns:
            bool: 是否加载成功
        """
        raise NotImplementedError("子类必须实现load方法")
    
    async def fallback(self, reason: str) -> bool:
        """
        降级处理
        
        Args:
            reason: 降级原因
            
        Returns:
            bool: 是否降级成功
        """
        raise NotImplementedError("子类必须实现fallback方法")
    
    def update_progress(self, progress: int):
        """
        更新加载进度
        
        Args:
            progress: 进度值（0-100）
        """
        if self._progress_bar:
            self._progress_bar.setValue(progress)
    
    def show_loading(self):
        """
        显示加载界面
        """
        if self._stack:
            self._stack.setCurrentWidget(self._loading_widget)
    
    def show_fallback(self, info: str = ""):
        """
        显示降级界面
        
        Args:
            info: 降级信息
        """
        if self._fallback_info:
            self._fallback_info.setText(info)
        if self._stack:
            self._stack.setCurrentWidget(self._fallback_widget)
        self.fallback_active = True
        self.panel_fallback.emit(self.panel_id)
    
    def show_content(self):
        """
        显示主内容界面
        """
        if self._stack:
            self._stack.setCurrentWidget(self._main_widget)
        self.loaded = True
        self.panel_loaded.emit(self.panel_id)
    
    def get_main_layout(self) -> QVBoxLayout:
        """
        获取主布局
        
        Returns:
            QVBoxLayout: 主布局
        """
        return self._main_layout
    
    def is_loaded(self) -> bool:
        """
        检查面板是否已加载
        
        Returns:
            bool: 是否已加载
        """
        return self.loaded
    
    def is_fallback_active(self) -> bool:
        """
        检查是否处于降级模式
        
        Returns:
            bool: 是否处于降级模式
        """
        return self.fallback_active


class A2UIManager(QObject):
    """
    A2UI 管理器
    管理所有 A2UI 面板，处理加载、降级等逻辑
    """
    
    # 信号
    panel_loaded = pyqtSignal(str)  # 面板加载完成
    panel_fallback = pyqtSignal(str)  # 面板降级
    panel_error = pyqtSignal(str, str)  # 面板错误
    
    def __init__(self, config: Optional[A2UIConfig] = None):
        """
        初始化 A2UI 管理器
        
        Args:
            config: A2UI 配置
        """
        super().__init__()
        self.config = config or A2UIConfig()
        self._panels: Dict[str, A2UIPanel] = {}
        self._loading_panels: List[str] = []
    
    def register_panel(self, panel: A2UIPanel):
        """
        注册 A2UI 面板
        
        Args:
            panel: A2UI 面板
        """
        self._panels[panel.panel_id] = panel
        panel.panel_loaded.connect(self._on_panel_loaded)
        panel.panel_fallback.connect(self._on_panel_fallback)
        panel.panel_error.connect(self._on_panel_error)
    
    def get_panel(self, panel_id: str) -> Optional[A2UIPanel]:
        """
        获取 A2UI 面板
        
        Args:
            panel_id: 面板 ID
            
        Returns:
            Optional[A2UIPanel]: 面板实例
        """
        return self._panels.get(panel_id)
    
    def list_panels(self) -> List[A2UIPanel]:
        """
        列出所有 A2UI 面板
        
        Returns:
            List[A2UIPanel]: 面板列表
        """
        return list(self._panels.values())
    
    async def load_panel(self, panel_id: str) -> bool:
        """
        加载 A2UI 面板
        
        Args:
            panel_id: 面板 ID
            
        Returns:
            bool: 是否加载成功
        """
        panel = self._panels.get(panel_id)
        if not panel:
            logger.error(f"Panel {panel_id} not found")
            return False
        
        if panel.is_loaded():
            return True
        
        if panel_id in self._loading_panels:
            logger.warning(f"Panel {panel_id} is already loading")
            return False
        
        self._loading_panels.append(panel_id)
        
        try:
            success = await panel.load()
            if success:
                panel.show_content()
            else:
                if self.config.fallback_enabled:
                    await panel.fallback("加载失败")
                else:
                    panel.panel_error.emit(panel_id, "加载失败")
            return success
        except Exception as e:
            logger.error(f"Failed to load panel {panel_id}: {e}")
            if self.config.fallback_enabled:
                await panel.fallback(str(e))
            else:
                panel.panel_error.emit(panel_id, str(e))
            return False
        finally:
            if panel_id in self._loading_panels:
                self._loading_panels.remove(panel_id)
    
    async def load_all_panels(self) -> Dict[str, bool]:
        """
        加载所有 A2UI 面板
        
        Returns:
            Dict[str, bool]: 面板加载结果
        """
        results = {}
        for panel_id in self._panels:
            results[panel_id] = await self.load_panel(panel_id)
        return results
    
    def unload_panel(self, panel_id: str):
        """
        卸载 A2UI 面板
        
        Args:
            panel_id: 面板 ID
        """
        if panel_id in self._panels:
            del self._panels[panel_id]
    
    def clear_panels(self):
        """
        清空所有 A2UI 面板
        """
        self._panels.clear()
        self._loading_panels.clear()
    
    def _on_panel_loaded(self, panel_id: str):
        """
        面板加载完成回调
        
        Args:
            panel_id: 面板 ID
        """
        logger.info(f"Panel {panel_id} loaded successfully")
        self.panel_loaded.emit(panel_id)
    
    def _on_panel_fallback(self, panel_id: str):
        """
        面板降级回调
        
        Args:
            panel_id: 面板 ID
        """
        logger.warning(f"Panel {panel_id} fallback activated")
        self.panel_fallback.emit(panel_id)
    
    def _on_panel_error(self, panel_id: str, error: str):
        """
        面板错误回调
        
        Args:
            panel_id: 面板 ID
            error: 错误信息
        """
        logger.error(f"Panel {panel_id} error: {error}")
        self.panel_error.emit(panel_id, error)
