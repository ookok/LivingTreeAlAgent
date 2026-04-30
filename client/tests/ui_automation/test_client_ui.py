"""
UI 自动化测试 - 客户端集成测试

基于 QtTest 和 Page Object 模式
"""

import sys
import os
import unittest
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

from page_objects import MainWindowPage, SidebarPage, ChatPanelPage, PageFactory


class TestMainWindow(unittest.TestCase):
    """主窗口测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication(sys.argv)
        
        # 启动客户端
        import threading
        
        def run_client():
            from client.src.main import main
            try:
                main()
            except Exception as e:
                print(f"Client error: {e}")
        
        cls.thread = threading.Thread(target=run_client, daemon=True)
        cls.thread.start()
        
        # 等待客户端启动
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        """清理测试类"""
        cls.app.quit()

    def test_main_window_exists(self):
        """测试主窗口存在"""
        main_window = PageFactory.get_main_window()
        self.assertIsNotNone(main_window.widget, "主窗口未找到")

    def test_main_window_visible(self):
        """测试主窗口可见"""
        main_window = PageFactory.get_main_window()
        self.assertTrue(main_window.is_visible, "主窗口不可见")

    def test_main_window_title(self):
        """测试主窗口标题"""
        main_window = PageFactory.get_main_window()
        self.assertIn("生命之树", main_window.title, "窗口标题不正确")


class TestSidebarNavigation(unittest.TestCase):
    """侧边栏导航测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        """设置测试"""
        self.sidebar = PageFactory.get_sidebar()

    def test_sidebar_exists(self):
        """测试侧边栏存在"""
        self.assertIsNotNone(self.sidebar.widget, "侧边栏未找到")

    def test_nav_buttons_exist(self):
        """测试导航按钮存在"""
        buttons = self.sidebar.nav_buttons
        self.assertTrue(len(buttons) > 0, "导航按钮数量为0")

    def test_chat_button_exists(self):
        """测试智能对话按钮存在"""
        btn = self.sidebar.get_nav_button("智能对话")
        self.assertIsNotNone(btn, "智能对话按钮未找到")

    def test_knowledge_button_exists(self):
        """测试知识库按钮存在"""
        btn = self.sidebar.get_nav_button("知识库")
        self.assertIsNotNone(btn, "知识库按钮未找到")


class TestChatPanel(unittest.TestCase):
    """聊天面板测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        """设置测试"""
        self.chat_panel = PageFactory.get_chat_panel()

    def test_chat_panel_exists(self):
        """测试聊天面板存在"""
        self.assertIsNotNone(self.chat_panel.widget, "聊天面板未找到")

    def test_input_field_exists(self):
        """测试输入框存在"""
        input_field = self.chat_panel.find_input_field()
        self.assertIsNotNone(input_field, "输入框未找到")

    def test_send_button_exists(self):
        """测试发送按钮存在"""
        send_btn = self.chat_panel.find_send_button()
        self.assertIsNotNone(send_btn, "发送按钮未找到")


class TestNavigationFlow(unittest.TestCase):
    """导航流程测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        """设置测试"""
        self.sidebar = PageFactory.get_sidebar()
        self.chat_panel = PageFactory.get_chat_panel()

    def test_switch_to_knowledge(self):
        """测试切换到知识库"""
        if self.sidebar.get_nav_button("知识库"):
            self.sidebar.click_nav_button("知识库")
            time.sleep(1)
            # 验证切换成功
            self.assertTrue(self.sidebar.get_nav_button("知识库").isChecked())

    def test_switch_back_to_chat(self):
        """测试切换回智能对话"""
        if self.sidebar.get_nav_button("智能对话"):
            self.sidebar.click_nav_button("智能对话")
            time.sleep(1)
            self.assertTrue(self.sidebar.get_nav_button("智能对话").isChecked())


def run_tests():
    """运行测试"""
    print("\n" + "="*60)
    print("UI 自动化测试 - QtTest + Page Object")
    print("="*60)
    
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加测试用例
    suite.addTest(unittest.makeSuite(TestMainWindow))
    suite.addTest(unittest.makeSuite(TestSidebarNavigation))
    suite.addTest(unittest.makeSuite(TestChatPanel))
    suite.addTest(unittest.makeSuite(TestNavigationFlow))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print(f"测试结果: {result.testsRun} 个测试")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("="*60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())