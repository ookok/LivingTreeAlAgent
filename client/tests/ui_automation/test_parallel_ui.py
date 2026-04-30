"""
UI 自动化测试套件 - 支持并行执行

使用 pytest-xdist 进行并行测试
使用 unittest.mock 模拟外部依赖
"""

import sys
import os
import pytest
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QLineEdit
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

from .page_objects import MainWindowPage, SidebarPage, ChatPanelPage, PageFactory


@pytest.mark.ui
class TestMainWindow:
    """主窗口测试"""

    def test_main_window_exists(self, mock_ollama, mock_chroma):
        """测试主窗口存在"""
        main_window = PageFactory.get_main_window()
        assert main_window.widget is not None, "主窗口未找到"

    def test_main_window_visible(self, mock_ollama, mock_chroma):
        """测试主窗口可见"""
        main_window = PageFactory.get_main_window()
        assert main_window.is_visible, "主窗口不可见"

    def test_main_window_title(self, mock_ollama, mock_chroma):
        """测试主窗口标题"""
        main_window = PageFactory.get_main_window()
        assert "生命之树" in main_window.title, f"窗口标题不正确: {main_window.title}"


@pytest.mark.ui
class TestSidebarNavigation:
    """侧边栏导航测试"""

    def test_sidebar_exists(self, mock_ollama, mock_chroma):
        """测试侧边栏存在"""
        sidebar = PageFactory.get_sidebar()
        assert sidebar.widget is not None, "侧边栏未找到"

    def test_nav_buttons_exist(self, mock_ollama, mock_chroma):
        """测试导航按钮存在"""
        sidebar = PageFactory.get_sidebar()
        buttons = sidebar.nav_buttons
        assert len(buttons) > 0, "导航按钮数量为0"

    def test_chat_button_exists(self, mock_ollama, mock_chroma):
        """测试智能对话按钮存在"""
        sidebar = PageFactory.get_sidebar()
        btn = sidebar.get_nav_button("智能对话")
        assert btn is not None, "智能对话按钮未找到"

    def test_knowledge_button_exists(self, mock_ollama, mock_chroma):
        """测试知识库按钮存在"""
        sidebar = PageFactory.get_sidebar()
        btn = sidebar.get_nav_button("知识库")
        assert btn is not None, "知识库按钮未找到"


@pytest.mark.ui
class TestChatPanel:
    """聊天面板测试"""

    def test_chat_panel_exists(self, mock_ollama, mock_chroma):
        """测试聊天面板存在"""
        chat_panel = PageFactory.get_chat_panel()
        assert chat_panel.widget is not None, "聊天面板未找到"

    def test_input_field_exists(self, mock_ollama, mock_chroma):
        """测试输入框存在"""
        chat_panel = PageFactory.get_chat_panel()
        input_field = chat_panel.find_input_field()
        assert input_field is not None, "输入框未找到"

    def test_send_button_exists(self, mock_ollama, mock_chroma):
        """测试发送按钮存在"""
        chat_panel = PageFactory.get_chat_panel()
        send_btn = chat_panel.find_send_button()
        assert send_btn is not None, "发送按钮未找到"


@pytest.mark.ui
@pytest.mark.integration
class TestNavigationFlow:
    """导航流程测试"""

    def test_switch_to_knowledge(self, mock_ollama, mock_chroma):
        """测试切换到知识库"""
        sidebar = PageFactory.get_sidebar()
        btn = sidebar.get_nav_button("知识库")
        if btn:
            sidebar.click_nav_button("知识库")
            time.sleep(0.5)
            assert btn.isChecked(), "未成功切换到知识库"

    def test_switch_back_to_chat(self, mock_ollama, mock_chroma):
        """测试切换回智能对话"""
        sidebar = PageFactory.get_sidebar()
        btn = sidebar.get_nav_button("智能对话")
        if btn:
            sidebar.click_nav_button("智能对话")
            time.sleep(0.5)
            assert btn.isChecked(), "未成功切换到智能对话"


@pytest.mark.ui
@pytest.mark.slow
class TestChatInteraction:
    """聊天交互测试"""

    def test_send_message(self, mock_ollama, mock_chroma):
        """测试发送消息"""
        chat_panel = PageFactory.get_chat_panel()
        initial_count = chat_panel.message_count
        
        chat_panel.send_message("你好")
        time.sleep(1)
        
        new_count = chat_panel.message_count
        assert new_count > initial_count, "消息未发送成功"


def run_parallel_tests():
    """运行并行测试"""
    import subprocess
    
    print("\n" + "="*60)
    print("UI 自动化测试 - 并行执行模式")
    print("="*60)
    print("使用 pytest-xdist 进行并行测试")
    print("="*60 + "\n")
    
    # 启动客户端
    import threading
    from client.src.main import main
    
    def run_client():
        try:
            main()
        except Exception as e:
            print(f"Client error: {e}")
    
    thread = threading.Thread(target=run_client, daemon=True)
    thread.start()
    
    # 等待客户端启动
    time.sleep(10)
    
    # 运行并行测试
    cmd = [
        sys.executable, "-m", "pytest",
        __file__,
        "-v",
        "--tb=short",
        "-n", "auto",  # 自动检测CPU核心数
        "--timeout=60",
        "-m", "ui"
    ]
    
    result = subprocess.run(cmd, cwd=os.path.dirname(__file__))
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_parallel_tests())