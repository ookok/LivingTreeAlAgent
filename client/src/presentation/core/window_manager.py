"""
窗口管理器 - Window Manager

功能：
1. 多窗口管理
2. 面板布局
3. 自定义标题栏
4. 窗口状态持久化
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from enum import Enum

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLayout, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QToolBar, QFrame
)
from PyQt6.QtCore import Qt, QSize

logger = logging.getLogger(__name__)


class PanelPosition(Enum):
    """面板位置"""
    LEFT = "left"
    RIGHT = "right"
    BOTTOM = "bottom"
    CENTER = "center"


class Panel:
    """面板抽象类"""
    def __init__(self, id: str, title: str):
        self.id = id
        self.title = title
        self._widget: Optional[QWidget] = None
    
    def get_widget(self) -> QWidget:
        """获取面板组件"""
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget
    
    def _create_widget(self) -> QWidget:
        """创建面板组件（子类实现）"""
        return QWidget()
    
    def show(self):
        """显示面板"""
        self.get_widget().show()
    
    def hide(self):
        """隐藏面板"""
        self.get_widget().hide()
    
    def is_visible(self) -> bool:
        """检查面板是否可见"""
        return self.get_widget().isVisible()


class WindowManager:
    """
    窗口管理器 - 管理应用窗口和面板
    
    核心功能：
    1. 多面板布局管理
    2. 自定义标题栏
    3. 窗口状态保存/恢复
    4. 布局调整
    """
    
    def __init__(self, main_window: QMainWindow):
        self._main_window = main_window
        self._panels: Dict[str, Panel] = {}
        self._panel_widgets: Dict[str, QWidget] = {}
        self._splitters: Dict[str, QSplitter] = {}
        
        # 布局结构
        self._central_widget = QWidget()
        self._main_layout = QHBoxLayout(self._central_widget)
        
        # 创建分隔器
        self._create_splitters()
        
        # 窗口状态
        self._window_state = {}
        
        # 加载保存的状态
        self.load_window_state()
    
    def _create_splitters(self):
        """创建面板分隔器"""
        # 主水平分隔器
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧面板容器
        self._left_container = QWidget()
        self._left_layout = QVBoxLayout(self._left_container)
        
        # 中央内容区域
        self._center_container = QWidget()
        self._center_layout = QVBoxLayout(self._center_container)
        
        # 右侧面板容器
        self._right_container = QWidget()
        self._right_layout = QVBoxLayout(self._right_container)
        
        # 添加到主分隔器
        self._main_splitter.addWidget(self._left_container)
        self._main_splitter.addWidget(self._center_container)
        self._main_splitter.addWidget(self._right_container)
        
        # 设置默认比例
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setStretchFactor(2, 1)
        
        # 添加到主布局
        self._main_layout.addWidget(self._main_splitter)
        
        # 设置中央组件
        self._main_window.setCentralWidget(self._central_widget)
    
    def register_panel(self, panel: Panel, position: PanelPosition):
        """注册面板"""
        self._panels[panel.id] = panel
        
        widget = panel.get_widget()
        
        if position == PanelPosition.LEFT:
            self._left_layout.addWidget(widget)
        elif position == PanelPosition.RIGHT:
            self._right_layout.addWidget(widget)
        elif position == PanelPosition.CENTER:
            self._center_layout.addWidget(widget)
        
        self._panel_widgets[panel.id] = widget
        
        logger.info(f"面板注册成功: {panel.id}")
    
    def show_panel(self, panel_id: str):
        """显示面板"""
        if panel_id in self._panel_widgets:
            self._panel_widgets[panel_id].show()
    
    def hide_panel(self, panel_id: str):
        """隐藏面板"""
        if panel_id in self._panel_widgets:
            self._panel_widgets[panel_id].hide()
    
    def toggle_panel(self, panel_id: str):
        """切换面板显示状态"""
        if panel_id in self._panel_widgets:
            widget = self._panel_widgets[panel_id]
            if widget.isVisible():
                widget.hide()
            else:
                widget.show()
    
    def get_panel(self, panel_id: str) -> Optional[Panel]:
        """获取面板"""
        return self._panels.get(panel_id)
    
    def get_panel_position(self, panel_id: str) -> Optional[PanelPosition]:
        """获取面板位置"""
        # 简化实现，实际应根据布局查询
        if panel_id in self._panels:
            return PanelPosition.CENTER
        return None
    
    def save_window_state(self):
        """保存窗口状态"""
        state = {
            'geometry': {
                'x': self._main_window.x(),
                'y': self._main_window.y(),
                'width': self._main_window.width(),
                'height': self._main_window.height()
            },
            'state': self._main_window.saveState().toBase64().data().decode(),
            'splitter_state': self._main_splitter.saveState().toBase64().data().decode(),
            'panels': {
                panel_id: panel.is_visible()
                for panel_id, panel in self._panels.items()
            }
        }
        
        state_path = os.path.join(os.path.expanduser("~"), ".hermes", "window_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info("窗口状态已保存")
    
    def load_window_state(self):
        """加载窗口状态"""
        state_path = os.path.join(os.path.expanduser("~"), ".hermes", "window_state.json")
        
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    state = json.load(f)
                
                # 恢复窗口位置和大小
                geometry = state.get('geometry', {})
                if geometry:
                    self._main_window.setGeometry(
                        geometry.get('x', 100),
                        geometry.get('y', 100),
                        geometry.get('width', 1200),
                        geometry.get('height', 800)
                    )
                
                # 恢复窗口状态
                if 'state' in state:
                    try:
                        from PyQt6.QtCore import QByteArray, QBase64
                        state_bytes = QByteArray.fromBase64(state['state'].encode())
                        self._main_window.restoreState(state_bytes)
                    except Exception as e:
                        logger.warning(f"恢复窗口状态失败: {e}")
                
                # 恢复分隔器状态
                if 'splitter_state' in state:
                    try:
                        from PyQt6.QtCore import QByteArray
                        splitter_bytes = QByteArray.fromBase64(state['splitter_state'].encode())
                        self._main_splitter.restoreState(splitter_bytes)
                    except Exception as e:
                        logger.warning(f"恢复分隔器状态失败: {e}")
                
                # 恢复面板状态
                if 'panels' in state:
                    for panel_id, visible in state['panels'].items():
                        if panel_id in self._panel_widgets:
                            if visible:
                                self._panel_widgets[panel_id].show()
                            else:
                                self._panel_widgets[panel_id].hide()
                
                logger.info("窗口状态已加载")
                
            except Exception as e:
                logger.error(f"加载窗口状态失败: {e}")
    
    def set_layout_ratio(self, left: int, center: int, right: int):
        """设置布局比例"""
        self._main_splitter.setStretchFactor(0, left)
        self._main_splitter.setStretchFactor(1, center)
        self._main_splitter.setStretchFactor(2, right)
    
    def maximize(self):
        """最大化窗口"""
        self._main_window.showMaximized()
    
    def minimize(self):
        """最小化窗口"""
        self._main_window.showMinimized()
    
    def toggle_fullscreen(self):
        """切换全屏"""
        if self._main_window.isFullScreen():
            self._main_window.showNormal()
        else:
            self._main_window.showFullScreen()
    
    def close(self):
        """关闭窗口（先保存状态）"""
        self.save_window_state()
        self._main_window.close()