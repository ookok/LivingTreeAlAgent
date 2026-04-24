#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新UI主窗口集成
运行方式: python _test_new_ui.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from client.src.presentation.main_window import MainWindow


def main():
    print("[TEST] Testing Advanced Chat Panel UI...")
    
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = MainWindow()
    window.setMinimumSize(1200, 700)
    window.show()
    
    print("[OK] Window created successfully!")
    print("[TEST] Advanced Chat Panel:")
    print("   1. Center: Advanced chat panel (default display)")
    print("   2. Left area: Task tree panel")
    print("   3. Right area: Streaming output panel")
    print("   4. Bottom: Input box + Send button")
    print("   5. Progress bar at bottom of streaming panel")
    print("   6. Three-column layout with draggable splitters")
    print("   7. Module bar with settings/user buttons")
    print("   8. Left/Right panels collapsible")
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
