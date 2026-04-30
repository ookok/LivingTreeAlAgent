#!/usr/bin/env python
"""
测试现代化主窗口
"""

import sys
sys.path.insert(0, 'client/src')

import sys
from PyQt6.QtWidgets import QApplication

def main():
    app = QApplication(sys.argv)
    
    # 导入并创建现代化主窗口
    from presentation.layouts.modern_main_window import ModernMainWindow
    
    window = ModernMainWindow()
    window.show()
    window.activateWindow()
    window.raise_()
    
    print("🎉 现代化主窗口已显示")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()