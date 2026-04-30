#!/usr/bin/env python
"""
UI自动化测试框架 - 测试4个核心面板
"""

import sys
sys.path.insert(0, 'client/src')

import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

class UITestFramework:
    """UI自动化测试框架"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = None
        self.test_results = []
        self.current_test = 0
        
    def start(self):
        """启动测试框架"""
        print("🚀 启动UI自动化测试框架...")
        
        # 导入并创建主窗口
        from presentation.layouts.modern_main_window import ModernMainWindow
        self.window = ModernMainWindow()
        self.window.show()
        self.window.activateWindow()
        self.window.raise_()
        
        # 延迟启动测试
        QTimer.singleShot(3000, self.run_tests)
        
        sys.exit(self.app.exec())
    
    def run_tests(self):
        """运行所有测试"""
        tests = [
            ("测试智能对话面板", self.test_chat_panel),
            ("测试代码开发面板", self.test_ide_panel),
            ("测试系统设置面板", self.test_settings_panel),
            ("测试用户设置面板", self.test_profile_panel),
        ]
        
        for name, test_func in tests:
            print(f"\n📋 {name}")
            try:
                result = test_func()
                if result:
                    self.test_results.append((name, "✅ 通过"))
                    print("✅ 通过")
                else:
                    self.test_results.append((name, "❌ 失败"))
                    print("❌ 失败")
            except Exception as e:
                self.test_results.append((name, f"❌ 异常: {e}"))
                print(f"❌ 异常: {e}")
            
            # 延迟切换
            QTimer.singleShot(1000, lambda: None)
            self.app.processEvents()
            time.sleep(1)
        
        self.show_report()
    
    def test_chat_panel(self) -> bool:
        """测试智能对话面板"""
        print("   导航到聊天面板...")
        self.window._navigate_to("chat")
        self.app.processEvents()
        time.sleep(1)
        
        # 检查工作区是否有内容
        panel = self.window._workspace.currentWidget()
        if panel:
            print(f"   ✅ 聊天面板已加载: {type(panel).__name__}")
            return True
        return False
    
    def test_ide_panel(self) -> bool:
        """测试代码开发面板"""
        print("   导航到代码开发面板...")
        self.window._navigate_to("smart_ide")
        self.app.processEvents()
        time.sleep(2)
        
        panel = self.window._workspace.currentWidget()
        if panel:
            print(f"   ✅ 代码开发面板已加载: {type(panel).__name__}")
            return True
        return False
    
    def test_settings_panel(self) -> bool:
        """测试系统设置面板"""
        print("   导航到系统设置面板...")
        self.window._navigate_to("settings")
        self.app.processEvents()
        time.sleep(2)
        
        panel = self.window._workspace.currentWidget()
        if panel:
            print(f"   ✅ 系统设置面板已加载: {type(panel).__name__}")
            return True
        return False
    
    def test_profile_panel(self) -> bool:
        """测试用户设置面板"""
        print("   导航到用户设置面板...")
        self.window._navigate_to("profile")
        self.app.processEvents()
        time.sleep(2)
        
        panel = self.window._workspace.currentWidget()
        if panel:
            print(f"   ✅ 用户设置面板已加载: {type(panel).__name__}")
            return True
        return False
    
    def show_report(self):
        """显示测试报告"""
        print("\n" + "="*60)
        print("📊 UI自动化测试报告")
        print("="*60)
        
        passed = sum(1 for _, result in self.test_results if "通过" in result)
        total = len(self.test_results)
        
        for name, result in self.test_results:
            print(f"  {result} {name}")
        
        print("-"*60)
        print(f"  总计: {passed}/{total} 通过")
        print("="*60)
        
        # 延迟退出
        QTimer.singleShot(2000, self.app.quit)

if __name__ == "__main__":
    tester = UITestFramework()
    tester.start()