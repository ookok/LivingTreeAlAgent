#!/usr/bin/env python
"""
测试聊天面板加载问题
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

def test_chat_panel():
    """测试聊天面板加载"""
    app = QApplication(sys.argv)
    
    print('📦 尝试导入聊天面板...')
    try:
        from presentation.modules.chat.panel import Panel
        print('✅ 成功导入 Panel 类')
        
        # 创建主窗口
        window = QMainWindow()
        window.setWindowTitle("Chat Panel Test")
        window.resize(800, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # 创建聊天面板
        print('🔧 尝试创建面板实例...')
        panel = Panel()
        print('✅ 面板实例创建成功')
        print(f'   - 对象类型: {type(panel).__name__}')
        
        layout.addWidget(panel)
        window.setCentralWidget(central_widget)
        
        # 显示窗口
        window.show()
        
        print('🎉 聊天面板加载成功！')
        print('💡 窗口已显示，按 Ctrl+C 或关闭窗口退出')
        
        # 运行事件循环
        sys.exit(app.exec())
        
    except Exception as e:
        print('❌ 加载失败')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_chat_panel()