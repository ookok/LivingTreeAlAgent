#!/usr/bin/env python3
"""
LivingTreeAlAgent NG - WebEngine + Vue架构
入口文件
"""

import sys
import os
from pathlib import Path

# 添加项目路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QScreen

from backend.infrastructure.bridge.backend_bridge import BackendBridge


class MainWindow(QMainWindow):
    """主窗口 - WebEngine"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LivingTreeAlAgent NG")
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # 设置窗口大小为屏幕的95%，确保有边框可见
        width = int(screen_geometry.width() * 0.95)
        height = int(screen_geometry.height() * 0.95)
        
        # 设置窗口尺寸
        self.setGeometry(
            (screen_geometry.width() - width) // 2,
            (screen_geometry.height() - height) // 2,
            width,
            height
        )
        
        # 设置最小尺寸
        self.setMinimumSize(1024, 768)
        
        # 初始化核心系统
        self.backend_bridge = BackendBridge()
        
        self._init_ui()
        self._init_webchannel()
        self._init_shortcuts()
        
    def _init_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # WebEngine视图
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # 加载Vue前端
        frontend_path = BASE_DIR / "frontend" / "index.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(frontend_path)))
        
    def _init_webchannel(self):
        """初始化WebChannel通信"""
        self.channel = QWebChannel()
        self.channel.registerObject("backend", self.backend_bridge)
        self.web_view.page().setWebChannel(self.channel)
        
    def _init_shortcuts(self):
        """初始化快捷键"""
        # F12打开开发者工具
        dev_tools_shortcut = QShortcut(QKeySequence("F12"), self)
        dev_tools_shortcut.activated.connect(self._toggle_dev_tools)
        
        # Ctrl+Shift+I（Chrome风格）也打开开发者工具
        ctrl_shift_i = QShortcut(QKeySequence("Ctrl+Shift+I"), self)
        ctrl_shift_i.activated.connect(self._toggle_dev_tools)
        
        # 刷新页面
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh_page)
        
    def _toggle_dev_tools(self):
        """切换开发者工具"""
        if hasattr(self, 'dev_tools_window') and self.dev_tools_window.isVisible():
            self.dev_tools_window.close()
        else:
            self.dev_tools_window = QMainWindow(self)
            self.dev_tools_window.setWindowTitle("开发者工具")
            self.dev_tools_window.setMinimumSize(1000, 600)
            self.dev_tools_page = QWebEngineView(self.dev_tools_window)
            self.web_view.page().setDevToolsPage(self.dev_tools_page.page())
            self.dev_tools_window.setCentralWidget(self.dev_tools_page)
            self.dev_tools_window.show()
            
    def _refresh_page(self):
        """刷新页面"""
        self.web_view.reload()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LivingTreeAlAgent NG")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
