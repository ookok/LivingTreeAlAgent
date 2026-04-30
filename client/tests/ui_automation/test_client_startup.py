"""
UI 自动化测试 - 客户端启动测试

测试内容：
1. 客户端启动
2. 侧边栏导航显示
3. 智能对话面板加载
4. 各模块切换
"""

import sys
import os
import time
import traceback

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QMainWindow
import test_base
TestCase = test_base.TestCase
TestRunner = test_base.TestRunner
TestSuite = test_base.TestSuite
wait_for = test_base.wait_for


class TestClientStartup(TestCase):
    """客户端启动测试"""

    def setUp(self):
        """设置测试环境"""
        self.app = None
        self.main_window = None

    def tearDown(self):
        """清理测试环境"""
        if self.main_window:
            try:
                self.main_window.close()
            except:
                pass
        if self.app:
            try:
                self.app.quit()
            except:
                pass

    def test_client_startup(self):
        """测试客户端启动"""
        print("  🚀 启动客户端...")
        
        # 创建应用
        self.app = QApplication(sys.argv)
        
        # 启动客户端
        from src.main import main
        import threading
        
        def run_client():
            try:
                main()
            except Exception as e:
                print(f"    Client error: {e}")
        
        thread = threading.Thread(target=run_client, daemon=True)
        thread.start()
        
        # 等待主窗口出现
        def find_main_window():
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMainWindow):
                    return widget
            return None
        
        self.main_window = wait_for(
            lambda: find_main_window() is not None,
            timeout=30.0,
            description="主窗口出现"
        )
        
        self.assert_not_none(self.main_window, "主窗口未找到")
        print("  ✓ 主窗口已创建")
        
        # 检查窗口标题
        title = self.main_window.windowTitle()
        self.assert_contains(title, "生命之树", f"窗口标题不正确: {title}")
        print("  ✓ 窗口标题正确")
        
        # 检查窗口可见
        self.assert_true(self.main_window.isVisible(), "窗口不可见")
        print("  ✓ 窗口可见")

    def test_sidebar_navigation(self):
        """测试侧边栏导航"""
        print("  🧭 测试侧边栏导航...")
        
        # 等待侧边栏出现
        sidebar = None
        
        def find_sidebar():
            from PyQt6.QtWidgets import QWidget
            for child in self.main_window.findChildren(QWidget):
                if hasattr(child, 'objectName') and 'sidebar' in child.objectName().lower():
                    return child
                # 检查是否有导航按钮
                for btn in child.findChildren(QWidget):
                    if hasattr(btn, 'text') and btn.text() in ["智能对话", "知识库"]:
                        return child.parent()
            return None
        
        sidebar = wait_for(
            lambda: find_sidebar() is not None,
            timeout=10.0,
            description="侧边栏出现"
        )
        
        self.assert_not_none(sidebar, "侧边栏未找到")
        print("  ✓ 侧边栏已加载")
        
        # 检查导航按钮
        from PyQt6.QtWidgets import QPushButton
        nav_buttons = sidebar.findChildren(QPushButton)
        self.assert_true(len(nav_buttons) > 0, "未找到导航按钮")
        print(f"  ✓ 找到 {len(nav_buttons)} 个导航按钮")
        
        # 检查智能对话按钮
        chat_btn = None
        for btn in nav_buttons:
            if hasattr(btn, 'text') and btn.text() == "智能对话":
                chat_btn = btn
                break
        
        self.assert_not_none(chat_btn, "智能对话按钮未找到")
        print("  ✓ 智能对话按钮已找到")

    def test_chat_panel_load(self):
        """测试聊天面板加载"""
        print("  💬 测试聊天面板加载...")
        
        # 等待聊天面板出现
        chat_panel = None
        
        def find_chat_panel():
            from PyQt6.QtWidgets import QWidget
            for child in self.main_window.findChildren(QWidget):
                if hasattr(child, 'objectName') and 'chat' in child.objectName().lower():
                    return child
                # 检查是否有消息容器
                for sub in child.findChildren(QWidget):
                    if hasattr(sub, 'objectName') and 'message' in sub.objectName().lower():
                        return child
            return None
        
        chat_panel = wait_for(
            lambda: find_chat_panel() is not None,
            timeout=15.0,
            description="聊天面板出现"
        )
        
        self.assert_not_none(chat_panel, "聊天面板未找到")
        print("  ✓ 聊天面板已加载")
        
        # 检查消息容器
        from PyQt6.QtWidgets import QScrollArea, QFrame
        scroll_area = None
        for child in chat_panel.findChildren((QScrollArea, QFrame)):
            if hasattr(child, 'objectName') and 'scroll' in child.objectName().lower():
                scroll_area = child
                break
        
        self.assert_not_none(scroll_area, "消息滚动区域未找到")
        print("  ✓ 消息滚动区域已加载")


def run_tests():
    """运行测试"""
    print("\n" + "="*60)
    print("UI 自动化测试 - 客户端启动")
    print("="*60)
    
    runner = TestRunner(
        output_dir="test_results",
        screenshot_dir="test_screenshots",
        verbose=True
    )
    
    # 创建测试套件
    suite = TestSuite("客户端启动测试")
    
    # 添加测试
    test_case = TestClientStartup()
    suite.add_test(test_case.test_client_startup)
    suite.add_test(test_case.test_sidebar_navigation)
    suite.add_test(test_case.test_chat_panel_load)
    
    runner.add_suite(suite)
    
    # 运行测试
    result = runner.run()
    
    print(f"\n{'='*60}")
    print(f"测试结果: {result.passed}/{result.total} 通过")
    print(f"成功率: {result.success_rate:.1f}%")
    print(f"耗时: {result.duration:.2f}s")
    print("="*60)
    
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())