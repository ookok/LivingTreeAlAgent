"""
聊天面板 UI 自动化测试

直接测试聊天面板组件
"""

import sys
import os
import unittest

# 添加项目路径
current_dir = os.path.dirname(__file__)
client_dir = os.path.join(current_dir, '..', '..')
src_dir = os.path.join(client_dir, 'src')

# 将 src 目录添加到路径
sys.path.insert(0, src_dir)
sys.path.insert(0, client_dir)
sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QScrollArea, QTextEdit
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt


class TestChatPanel(unittest.TestCase):
    """聊天面板测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication(sys.argv)

    @classmethod
    def tearDownClass(cls):
        """清理测试类"""
        cls.app.quit()

    def test_chat_panel_creation(self):
        """测试聊天面板创建"""
        from presentation.modules.chat.panel import Panel
        
        panel = Panel()
        self.assertIsNotNone(panel)
        print("✓ 聊天面板创建成功")

    def test_chat_panel_has_scroll_area(self):
        """测试聊天面板有滚动区域"""
        from presentation.modules.chat.panel import Panel
        
        panel = Panel()
        # 直接检查对象属性
        self.assertTrue(hasattr(panel, 'scroll_area'))
        self.assertIsNotNone(panel.scroll_area)
        print("✓ 滚动区域存在")

    def test_chat_panel_has_input(self):
        """测试聊天面板有输入框"""
        from presentation.modules.chat.panel import Panel
        
        panel = Panel()
        # 直接检查对象属性
        self.assertTrue(hasattr(panel, 'input_field'))
        self.assertIsNotNone(panel.input_field)
        print("✓ 输入框存在")

    def test_input_field_enabled(self):
        """测试输入框可用"""
        from presentation.modules.chat.panel import Panel
        
        panel = Panel()
        self.assertTrue(hasattr(panel, 'input_field'))
        self.assertTrue(panel.input_field.isEnabled())
        print("✓ 输入框可用")

    def test_send_message(self):
        """测试发送消息"""
        from presentation.modules.chat.panel import Panel
        
        panel = Panel()
        self.assertTrue(hasattr(panel, 'input_field'))
        
        input_field = panel.input_field
        
        # 输入消息
        QTest.keyClicks(input_field, "Hello World")
        self.assertEqual(input_field.toPlainText(), "Hello World")
        print("✓ 消息输入成功")
        
        # 清除消息
        input_field.clear()
        self.assertEqual(input_field.toPlainText(), "")
        print("✓ 消息清除成功")


class TestSidebarNavigation(unittest.TestCase):
    """侧边栏导航测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_nav_button_creation(self):
        """测试导航按钮创建"""
        button = QPushButton("智能对话")
        self.assertEqual(button.text(), "智能对话")
        print("✓ 导航按钮创建成功")

    def test_button_click(self):
        """测试按钮点击"""
        button = QPushButton("测试")
        clicked = []
        
        def on_click():
            clicked.append(True)
        
        button.clicked.connect(on_click)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        
        self.assertTrue(len(clicked) > 0)
        print("✓ 按钮点击测试成功")


def run_tests():
    """运行测试"""
    print("\n" + "="*60)
    print("UI 自动化测试 - 聊天面板测试")
    print("="*60)
    
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestChatPanel))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSidebarNavigation))
    
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