"""
Page Object 模式 - UI 测试封装

提供：
- PageObject: 页面对象基类
- MainWindowPage: 主窗口页面
- SidebarPage: 侧边栏页面
- ChatPanelPage: 聊天面板页面
"""

import time
from typing import Optional, List, Any
from PyQt6.QtWidgets import QWidget, QMainWindow, QPushButton, QLabel, QLineEdit, QScrollArea
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt, QPoint


class PageObject:
    """页面对象基类"""

    def __init__(self, parent: QWidget = None):
        self.parent = parent
        self._widget = None

    def find_widget(self, widget_type, name: str = None, timeout: float = 5.0) -> Optional[QWidget]:
        """
        查找 widget
        
        Args:
            widget_type: widget 类型
            name: objectName 或 text
            timeout: 超时时间（秒）
        
        Returns:
            找到的 widget，未找到返回 None
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.parent:
                widgets = self.parent.findChildren(widget_type)
            else:
                from PyQt6.QtWidgets import QApplication
                widgets = QApplication.instance().allWidgets()
            
            for widget in widgets:
                if widget.isVisible():
                    if name:
                        # 检查 objectName
                        if hasattr(widget, 'objectName') and widget.objectName() == name:
                            return widget
                        # 检查 text
                        if hasattr(widget, 'text') and widget.text() == name:
                            return widget
                        # 检查 accessibleName
                        if hasattr(widget, 'accessibleName') and widget.accessibleName() == name:
                            return widget
                    else:
                        return widget
            time.sleep(0.1)
        return None

    def find_widgets(self, widget_type) -> List[QWidget]:
        """查找所有指定类型的 widget"""
        if self.parent:
            return [w for w in self.parent.findChildren(widget_type) if w.isVisible()]
        from PyQt6.QtWidgets import QApplication
        return [w for w in QApplication.instance().allWidgets() if isinstance(w, widget_type) and w.isVisible()]

    def wait_for_visible(self, widget: QWidget, timeout: float = 5.0) -> bool:
        """等待 widget 变为可见"""
        start = time.time()
        while time.time() - start < timeout:
            if widget.isVisible():
                return True
            time.sleep(0.1)
        return False

    def wait_for_enabled(self, widget: QWidget, timeout: float = 5.0) -> bool:
        """等待 widget 变为可用"""
        start = time.time()
        while time.time() - start < timeout:
            if widget.isEnabled():
                return True
            time.sleep(0.1)
        return False

    @property
    def widget(self) -> QWidget:
        """获取底层 widget"""
        return self._widget

    def click(self):
        """点击 widget"""
        if self._widget:
            QTest.mouseClick(self._widget, Qt.MouseButton.LeftButton)

    def double_click(self):
        """双击 widget"""
        if self._widget:
            QTest.mouseDClick(self._widget, Qt.MouseButton.LeftButton)


class MainWindowPage(PageObject):
    """主窗口页面"""

    def __init__(self):
        super().__init__()
        self._widget = self._find_main_window()

    def _find_main_window(self) -> Optional[QMainWindow]:
        """查找主窗口"""
        return self.find_widget(QMainWindow)

    @property
    def title(self) -> str:
        """获取窗口标题"""
        if self._widget:
            return self._widget.windowTitle()
        return ""

    @property
    def is_visible(self) -> bool:
        """检查窗口是否可见"""
        return self._widget is not None and self._widget.isVisible()

    @property
    def is_maximized(self) -> bool:
        """检查窗口是否最大化"""
        return self._widget is not None and self._widget.isMaximized()

    def close(self):
        """关闭窗口"""
        if self._widget:
            self._widget.close()


class SidebarPage(PageObject):
    """侧边栏页面"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._widget = self._find_sidebar()

    def _find_sidebar(self) -> Optional[QWidget]:
        """查找侧边栏"""
        # 查找包含导航按钮的容器
        buttons = self.find_widgets(QPushButton)
        for btn in buttons:
            if btn.text() in ["智能对话", "知识库", "深度搜索"]:
                return btn.parent().parent()
        return None

    def get_nav_button(self, name: str) -> Optional[QPushButton]:
        """获取导航按钮"""
        buttons = self._widget.findChildren(QPushButton) if self._widget else []
        for btn in buttons:
            if btn.text() == name:
                return btn
        return None

    def click_nav_button(self, name: str):
        """点击导航按钮"""
        btn = self.get_nav_button(name)
        if btn:
            QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
            time.sleep(0.5)

    @property
    def nav_buttons(self) -> List[str]:
        """获取所有导航按钮名称"""
        if not self._widget:
            return []
        buttons = self._widget.findChildren(QPushButton)
        return [btn.text() for btn in buttons if btn.text()]


class ChatPanelPage(PageObject):
    """聊天面板页面"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._widget = self._find_chat_panel()

    def _find_chat_panel(self) -> Optional[QWidget]:
        """查找聊天面板"""
        # 查找包含消息滚动区域的容器
        scroll_areas = self.find_widgets(QScrollArea)
        for scroll in scroll_areas:
            # 检查是否有消息相关的子控件
            if scroll.findChild(QWidget, "messages_container"):
                return scroll.parent()
        return None

    def find_message_bubbles(self) -> List[QWidget]:
        """查找消息气泡"""
        if not self._widget:
            return []
        from PyQt6.QtWidgets import QFrame
        return self._widget.findChildren(QFrame)

    def find_input_field(self) -> Optional[QLineEdit]:
        """查找输入框"""
        if not self._widget:
            return None
        return self._widget.findChild(QLineEdit)

    def find_send_button(self) -> Optional[QPushButton]:
        """查找发送按钮"""
        if not self._widget:
            return None
        buttons = self._widget.findChildren(QPushButton)
        for btn in buttons:
            if btn.text() in ["发送", "Send"]:
                return btn
            # 检查图标按钮
            if btn.icon().isNull() == False:
                return btn
        return None

    def send_message(self, text: str):
        """发送消息"""
        input_field = self.find_input_field()
        send_btn = self.find_send_button()
        
        if input_field and send_btn:
            # 输入文本
            QTest.keyClicks(input_field, text)
            time.sleep(0.2)
            
            # 点击发送
            QTest.mouseClick(send_btn, Qt.MouseButton.LeftButton)

    @property
    def message_count(self) -> int:
        """获取消息数量"""
        return len(self.find_message_bubbles())


class PageFactory:
    """页面工厂"""

    @staticmethod
    def get_main_window() -> MainWindowPage:
        """获取主窗口页面"""
        return MainWindowPage()

    @staticmethod
    def get_sidebar(parent: QWidget = None) -> SidebarPage:
        """获取侧边栏页面"""
        return SidebarPage(parent)

    @staticmethod
    def get_chat_panel(parent: QWidget = None) -> ChatPanelPage:
        """获取聊天面板页面"""
        return ChatPanelPage(parent)