#!/usr/bin/env python
"""
测试聊天面板显示
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

def test_chat_display():
    """测试聊天面板显示"""
    app = QApplication(sys.argv)
    
    print('📦 测试聊天面板显示...')
    
    try:
        # 创建主窗口
        window = QMainWindow()
        window.setWindowTitle("Chat Panel Display Test")
        window.resize(1000, 700)
        
        # 创建中心部件
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # 导入并创建聊天面板
        print('🔧 导入聊天面板...')
        from presentation.modules.chat.panel import Panel
        panel = Panel()
        print('✅ 聊天面板创建成功')
        
        layout.addWidget(panel)
        window.setCentralWidget(central_widget)
        
        # 显示窗口
        window.show()
        print('🎉 窗口已显示')
        
        # 运行事件循环
        sys.exit(app.exec())
        
    except Exception as e:
        print('❌ 测试失败')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_chat_display()