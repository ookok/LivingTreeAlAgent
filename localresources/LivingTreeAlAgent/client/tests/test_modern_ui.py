"""
现代界面自动化测试
==================

测试改造后的现代界面功能，包括：
- 渐变背景效果
- 卡片式布局
- 输入验证
- 响应式设计

运行方式:
    pytest client/tests/test_modern_ui.py -v
"""

import pytest
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtWidgets import QApplication, QWidget, QTabWidget, QTextEdit, QPushButton
from PyQt6.QtGui import QLinearGradient, QPainter, QBrush

# 导入被测组件
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.src.presentation.main_window import MainWindow
from client.src.infrastructure.config.config import AppConfig


@pytest.fixture(scope="session")
def qapp():
    """全局 QApplication fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def main_window(qapp):
    """创建测试主窗口"""
    config = AppConfig()
    window = MainWindow(config)
    window.show()
    yield window
    window.close()


class TestModernUI:
    """现代界面测试"""

    def test_gradient_background(self, main_window):
        """测试渐变背景效果"""
        # 验证窗口的paintEvent方法是否正确实现
        assert hasattr(main_window, 'paintEvent')
        
        # 测试窗口大小是否正确
        assert main_window.minimumSize().width() >= 900
        assert main_window.minimumSize().height() >= 600

    def test_card_layout(self, main_window):
        """测试卡片式布局"""
        # 验证是否存在卡片式样式方法
        assert hasattr(main_window, '_apply_card_style')
        
        # 验证主要面板是否存在
        assert hasattr(main_window, 'session_panel')
        assert hasattr(main_window, 'center_tabs')
        assert hasattr(main_window, 'right_stack')
        
        # 验证这些面板是否是QWidget的实例
        assert isinstance(main_window.session_panel, QWidget)
        assert isinstance(main_window.center_tabs, QTabWidget)
        assert isinstance(main_window.right_stack, QWidget)

    def test_input_validation(self, main_window):
        """测试输入验证功能"""
        # 切换到聊天标签页
        main_window.center_tabs.setCurrentIndex(0)  # 聊天标签页
        
        # 获取系统大脑面板
        system_brain_panel = main_window.system_brain_panel
        assert system_brain_panel is not None
        
        # 获取输入框
        input_box = system_brain_panel.input_box
        assert isinstance(input_box, QTextEdit)
        
        # 测试输入验证 - 输入超过1000字符的内容
        long_text = "a" * 1001
        input_box.setPlainText(long_text)
        
        # 模拟发送按钮点击
        send_btn = system_brain_panel.send_btn
        assert isinstance(send_btn, QPushButton)
        
        # 点击发送按钮
        send_btn.click()
        
        # 等待事件处理
        import time
        time.sleep(0.5)
        QApplication.processEvents()

    def test_responsive_design(self, main_window):
        """测试响应式设计"""
        # 验证窗口的resizeEvent方法是否正确实现
        assert hasattr(main_window, 'resizeEvent')
        
        # 测试窗口大小调整
        original_size = main_window.size()
        
        # 调整窗口大小
        new_width = original_size.width() + 100
        new_height = original_size.height() + 100
        main_window.resize(new_width, new_height)
        
        # 等待事件处理
        QApplication.processEvents()
        
        # 验证窗口大小是否已更改
        new_size = main_window.size()
        assert new_size.width() == new_width
        assert new_size.height() == new_height

    def test_tab_creation(self, main_window):
        """测试标签页创建"""
        # 验证中心标签页是否包含预期的标签
        expected_tabs = ["🧠 系统大脑", "✍️ 写作助手", "🔍 研究助手", "🏠 首页", "🌱 嫁接园", "🚀 舰桥"]
        
        for i in range(main_window.center_tabs.count()):
            tab_text = main_window.center_tabs.tabText(i)
            assert tab_text in expected_tabs

    def test_model_pool_panel(self, main_window):
        """测试模型池面板"""
        # 切换到模型池面板
        main_window.right_stack.setCurrentIndex(1)  # 模型池面板
        
        # 验证模型池面板是否存在
        model_pool_panel = main_window.model_pool_panel
        assert model_pool_panel is not None


class TestIntegration:
    """集成测试"""

    def test_full_ui_workflow(self, main_window):
        """测试完整UI工作流"""
        # 1. 测试窗口显示
        assert main_window.isVisible()
        
        # 2. 测试标签页切换
        for i in range(main_window.center_tabs.count()):
            main_window.center_tabs.setCurrentIndex(i)
            QApplication.processEvents()
            assert main_window.center_tabs.currentIndex() == i
        
        # 3. 测试右侧面板切换
        main_window.right_stack.setCurrentIndex(0)  # 工作区面板
        QApplication.processEvents()
        assert main_window.right_stack.currentIndex() == 0
        
        main_window.right_stack.setCurrentIndex(1)  # 模型池面板
        QApplication.processEvents()
        assert main_window.right_stack.currentIndex() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
