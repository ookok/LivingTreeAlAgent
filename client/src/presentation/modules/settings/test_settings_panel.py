"""
测试设置面板 - 模型切换功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from presentation.modules.settings.panel import Panel


def main():
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("系统设置 - 模型切换")
    window.setGeometry(100, 100, 600, 700)
    
    # 创建中心部件
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    
    # 添加设置面板
    settings_panel = Panel()
    layout.addWidget(settings_panel)
    
    window.setCentralWidget(central_widget)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()