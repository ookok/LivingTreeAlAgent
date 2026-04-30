"""
简单的 UI 自动化测试脚本

使用 QtTest 和 Page Object 模式
"""

import sys
import os
import time

# 添加项目路径
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, '..', '..'))
sys.path.insert(0, os.path.join(current_dir, '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLineEdit
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

from page_objects import MainWindowPage, SidebarPage, ChatPanelPage, PageFactory


def run_simple_test():
    """运行简单测试"""
    print("\n" + "="*60)
    print("UI 自动化测试 - QtTest + Page Object")
    print("="*60)
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 启动客户端
    import threading
    from src.main import main
    
    def run_client():
        try:
            main()
        except Exception as e:
            print(f"Client error: {e}")
    
    thread = threading.Thread(target=run_client, daemon=True)
    thread.start()
    
    # 等待客户端启动
    print("\n等待客户端启动...")
    time.sleep(15)
    
    # 测试1: 主窗口测试
    print("\n📋 测试1: 主窗口测试")
    
    # 直接使用 QApplication 查找
    top_level_widgets = QApplication.topLevelWidgets()
    print(f"  顶层窗口数量: {len(top_level_widgets)}")
    
    main_window = None
    for widget in top_level_widgets:
        if isinstance(widget, QMainWindow):
            main_window = widget
            break
    
    if main_window:
        print("  ✓ 主窗口存在")
        print(f"  ✓ 窗口标题: {main_window.windowTitle()}")
        print(f"  ✓ 窗口可见: {main_window.isVisible()}")
    else:
        print("  ✗ 主窗口未找到")
        # 打印所有顶层窗口
        for i, widget in enumerate(top_level_widgets):
            print(f"    窗口[{i}]: {type(widget).__name__}, 标题: {getattr(widget, 'windowTitle', lambda: 'N/A')()}")
        return 1
    
    # 测试2: 侧边栏测试
    print("\n📋 测试2: 侧边栏测试")
    sidebar = PageFactory.get_sidebar()
    
    if sidebar.widget:
        print("  ✓ 侧边栏存在")
        buttons = sidebar.nav_buttons
        print(f"  ✓ 导航按钮: {buttons}")
        
        chat_btn = sidebar.get_nav_button("智能对话")
        if chat_btn:
            print("  ✓ 智能对话按钮存在")
        else:
            print("  ✗ 智能对话按钮未找到")
    else:
        print("  ✗ 侧边栏未找到")
    
    # 测试3: 聊天面板测试
    print("\n📋 测试3: 聊天面板测试")
    chat_panel = PageFactory.get_chat_panel()
    
    if chat_panel.widget:
        print("  ✓ 聊天面板存在")
        
        input_field = chat_panel.find_input_field()
        if input_field:
            print("  ✓ 输入框存在")
        else:
            print("  ✗ 输入框未找到")
        
        send_btn = chat_panel.find_send_button()
        if send_btn:
            print("  ✓ 发送按钮存在")
        else:
            print("  ✗ 发送按钮未找到")
    else:
        print("  ✗ 聊天面板未找到")
    
    # 测试4: 导航切换测试
    print("\n📋 测试4: 导航切换测试")
    if sidebar.get_nav_button("知识库"):
        sidebar.click_nav_button("知识库")
        time.sleep(0.5)
        print("  ✓ 切换到知识库")
        
        sidebar.click_nav_button("智能对话")
        time.sleep(0.5)
        print("  ✓ 切换回智能对话")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(run_simple_test())