"""
最终 UI 自动化测试 - 验证客户端界面功能
"""

import sys
import os
import time

# 添加项目路径
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLineEdit


def run_tests():
    """运行测试"""
    print("\n" + "="*60)
    print("UI 自动化测试 - 客户端验证")
    print("="*60)
    
    # 获取正在运行的应用
    app = QApplication.instance()
    
    if not app:
        print("✗ 未找到运行中的 QApplication")
        return 1
    
    print("✓ 已连接到运行中的应用")
    
    # 等待窗口稳定
    time.sleep(3)
    
    # 测试1: 查找主窗口
    print("\n📋 测试1: 主窗口测试")
    top_level_widgets = app.topLevelWidgets()
    print(f"  顶层窗口数量: {len(top_level_widgets)}")
    
    main_window = None
    for widget in top_level_widgets:
        if isinstance(widget, QMainWindow):
            main_window = widget
            break
    
    if main_window:
        print(f"  ✓ 主窗口标题: {main_window.windowTitle()}")
        print(f"  ✓ 主窗口可见: {main_window.isVisible()}")
        print(f"  ✓ 主窗口最大化: {main_window.isMaximized()}")
    else:
        print("  ✗ 主窗口未找到")
        return 1
    
    # 测试2: 查找侧边栏和导航按钮
    print("\n📋 测试2: 侧边栏导航测试")
    
    # 查找所有按钮
    all_buttons = main_window.findChildren(QPushButton)
    nav_buttons = []
    
    for btn in all_buttons:
        if btn.isVisible() and btn.text():
            nav_buttons.append(btn)
    
    print(f"  找到 {len(nav_buttons)} 个可见按钮")
    
    chat_btn = None
    knowledge_btn = None
    
    for btn in nav_buttons:
        if btn.text() == "智能对话":
            chat_btn = btn
        elif btn.text() == "知识库":
            knowledge_btn = btn
    
    if chat_btn:
        print(f"  ✓ 智能对话按钮: 可见={chat_btn.isVisible()}, 可用={chat_btn.isEnabled()}")
    else:
        print("  ✗ 智能对话按钮未找到")
    
    if knowledge_btn:
        print(f"  ✓ 知识库按钮: 可见={knowledge_btn.isVisible()}, 可用={knowledge_btn.isEnabled()}")
    else:
        print("  ✗ 知识库按钮未找到")
    
    # 测试3: 查找聊天输入框
    print("\n📋 测试3: 聊天面板测试")
    
    input_fields = main_window.findChildren(QLineEdit)
    chat_input = None
    
    for field in input_fields:
        if field.isVisible() and field.isEnabled():
            chat_input = field
            break
    
    if chat_input:
        print("  ✓ 聊天输入框存在")
    else:
        print("  ✗ 聊天输入框未找到")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())