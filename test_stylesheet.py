#!/usr/bin/env python
"""
测试样式表解析和聊天面板加载
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel

def test_stylesheet():
    """测试样式表解析"""
    app = QApplication(sys.argv)
    
    print('📦 测试样式表解析...')
    try:
        from presentation.theme.theme_manager import theme_manager
        stylesheet = theme_manager.get_stylesheet()
        print(f'✅ 样式表获取成功，长度: {len(stylesheet)}')
        
        # 测试应用样式表到窗口
        window = QMainWindow()
        window.setWindowTitle("Stylesheet Test")
        window.resize(400, 300)
        
        # 设置样式表
        try:
            window.setStyleSheet(stylesheet)
            print('✅ 样式表应用成功')
        except Exception as e:
            print(f'❌ 样式表应用失败: {e}')
        
        window.show()
        
    except Exception as e:
        print('❌ 样式表测试失败')
        import traceback
        traceback.print_exc()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_stylesheet()