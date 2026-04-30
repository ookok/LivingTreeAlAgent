#!/usr/bin/env python
"""
调试聊天面板可见性问题
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

def debug_panel_visibility():
    """调试面板可见性"""
    app = QApplication(sys.argv)
    
    print('📦 导入聊天面板...')
    from presentation.modules.chat.panel import Panel
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("Panel Visibility Debug")
    window.resize(1000, 700)
    
    # 创建中心部件
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    
    # 创建聊天面板
    print('🔧 创建聊天面板...')
    panel = Panel()
    
    # 添加到布局
    layout.addWidget(panel)
    window.setCentralWidget(central_widget)
    
    # 显示窗口
    window.show()
    
    # 检查面板状态
    print('\n📊 面板状态检查:')
    print(f'   - 面板对象: {panel}')
    print(f'   - 面板类型: {type(panel).__name__}')
    print(f'   - 面板可见: {panel.isVisible()}')
    print(f'   - 面板尺寸: {panel.size()}')
    print(f'   - 面板最小尺寸: {panel.minimumSize()}')
    print(f'   - 面板最大尺寸: {panel.maximumSize()}')
    
    # 检查布局
    print('\n📊 布局状态检查:')
    print(f'   - 布局: {layout}')
    print(f'   - 布局子部件数量: {layout.count()}')
    
    # 强制更新
    app.processEvents()
    
    # 再次检查
    print('\n📊 更新后的状态:')
    print(f'   - 面板可见: {panel.isVisible()}')
    print(f'   - 面板尺寸: {panel.size()}')
    
    print('\n🎉 调试窗口已显示')
    sys.exit(app.exec())

if __name__ == "__main__":
    debug_panel_visibility()