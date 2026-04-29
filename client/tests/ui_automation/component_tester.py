"""
组件测试器

提供 PyQt6 组件的自动化测试能力：
- 组件存在性检查
- 状态验证
- 交互模拟
- 事件触发
"""

from typing import Optional, Any, List, Callable, Dict
from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QTextEdit, QPushButton,
    QLabel, QComboBox, QCheckBox, QListWidget,
    QTreeWidget, QTabWidget
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest

from .test_base import wait_for, screenshot_on_failure


# ─────────────────────────────────────────────────────────────────────────────
# 断言函数
# ─────────────────────────────────────────────────────────────────────────────

def assert_widget_exists(widget: QWidget, message: str = "") -> bool:
    """断言组件存在"""
    if widget is None:
        raise AssertionError(message or "Widget does not exist")
    return True


def assert_widget_enabled(widget: QWidget, enabled: bool = True,
                          message: str = "") -> bool:
    """断言组件启用状态"""
    actual = widget.isEnabled()
    if actual != enabled:
        raise AssertionError(
            message or f"Widget enabled={actual}, expected={enabled}"
        )
    return True


def assert_widget_visible(widget: QWidget, visible: bool = True,
                           message: str = "") -> bool:
    """断言组件可见性"""
    actual = widget.isVisible()
    if actual != visible:
        raise AssertionError(
            message or f"Widget visible={actual}, expected={visible}"
        )
    return True


def assert_text_contains(widget: QWidget, text: str,
                         message: str = "") -> bool:
    """断言文本包含"""
    actual_text = ""

    if isinstance(widget, (QLineEdit, QTextEdit)):
        actual_text = widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text()
    elif isinstance(widget, QLabel):
        actual_text = widget.text()
    else:
        actual_text = widget.text() if hasattr(widget, 'text') else str(widget)

    if text not in actual_text:
        raise AssertionError(
            message or f"Text '{text}' not found in '{actual_text}'"
        )
    return True


def assert_widget_count(container: QWidget, expected: int,
                        message: str = "") -> bool:
    """断言子组件数量"""
    count = container.count() if hasattr(container, 'count') else len(container.findChildren(QWidget))
    if count != expected:
        raise AssertionError(
            message or f"Widget count={count}, expected={expected}"
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 交互模拟
# ─────────────────────────────────────────────────────────────────────────────

def simulate_click(widget: QWidget, wait: float = 0.1):
    """模拟点击"""
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    QTest.qWait(wait * 1000)


def simulate_double_click(widget: QWidget, wait: float = 0.1):
    """模拟双击"""
    QTest.mouseDClick(widget, Qt.MouseButton.LeftButton)
    QTest.qWait(wait * 1000)


def simulate_type(widget: QWidget, text: str, delay: float = 0.01):
    """模拟输入文本"""
    widget.setFocus()
    for char in text:
        QTest.keyClick(widget, char)
        QTest.qWait(delay * 1000)


def simulate_key_press(widget: QWidget, key: int, modifiers: int = 0):
    """模拟按键"""
    widget.setFocus()
    QTest.keyClick(widget, key, modifiers)


def simulate_mouse_move(widget: QWidget, pos: QPoint = None):
    """模拟鼠标移动"""
    if pos is None:
        pos = QPoint(widget.width() // 2, widget.height() // 2)
    QTest.mouseMove(widget, pos)


def simulate_scroll(widget: QWidget, direction: str = "down", steps: int = 3):
    """模拟滚动"""
    from PyQt6.QtCore import Qt
    key = Qt.Key.Key_Down if direction == "down" else Qt.Key.Key_Up
    for _ in range(steps):
        QTest.keyClick(widget, key)


def simulate_drag_drop(source: QWidget, target: QWidget):
    """模拟拖放"""
    start = QPoint(source.width() // 2, source.height() // 2)
    end = QPoint(target.width() // 2, target.height() // 2)

    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(source, end)
    QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=end)


# ─────────────────────────────────────────────────────────────────────────────
# ComponentTester
# ─────────────────────────────────────────────────────────────────────────────

class ComponentTester:
    """
    PyQt6 组件测试器

    提供组件的自动化测试能力：
    - 组件状态验证
    - 交互模拟
    - 事件监听

    Usage:
        tester = ComponentTester(my_widget)
        tester.assert_visible()
        tester.assert_enabled()
        tester.click()
        tester.type("hello")
    """

    def __init__(self, widget: QWidget, name: str = ""):
        self.widget = widget
        self.name = name or widget.__class__.__name__
        self._event_log: List[Dict[str, Any]] = []

    def assert_visible(self, visible: bool = True, message: str = ""):
        """断言可见性"""
        assert_widget_visible(self.widget, visible, message)
        return self

    def assert_enabled(self, enabled: bool = True, message: str = ""):
        """断言启用状态"""
        assert_widget_enabled(self.widget, enabled, message)
        return self

    def assert_text(self, expected: str, message: str = ""):
        """断言文本"""
        if isinstance(self.widget, (QLineEdit, QTextEdit)):
            actual = self.widget.toPlainText() if isinstance(self.widget, QTextEdit) else self.widget.text()
        elif isinstance(self.widget, QLabel):
            actual = self.widget.text()
        else:
            actual = getattr(self.widget, 'text', lambda: '')()

        if actual != expected:
            raise AssertionError(
                message or f"Expected text '{expected}', got '{actual}'"
            )
        return self

    def assert_contains_text(self, text: str, message: str = ""):
        """断言包含文本"""
        assert_text_contains(self.widget, text, message)
        return self

    def click(self, wait: float = 0.1):
        """点击"""
        simulate_click(self.widget, wait)
        self._log_event("click")
        return self

    def double_click(self, wait: float = 0.1):
        """双击"""
        simulate_double_click(self.widget, wait)
        self._log_event("double_click")
        return self

    def type(self, text: str, delay: float = 0.01):
        """输入文本"""
        simulate_type(self.widget, text, delay)
        self._log_event("type", {"text": text})
        return self

    def key_press(self, key: int, modifiers: int = 0):
        """按键"""
        simulate_key_press(self.widget, key, modifiers)
        self._log_event("key_press", {"key": key, "modifiers": modifiers})
        return self

    def clear(self):
        """清空文本"""
        if isinstance(self.widget, (QLineEdit, QTextEdit)):
            self.widget.clear()
        self._log_event("clear")
        return self

    def get_text(self) -> str:
        """获取文本"""
        if isinstance(self.widget, (QLineEdit, QTextEdit)):
            return self.widget.toPlainText() if isinstance(self.widget, QTextEdit) else self.widget.text()
        elif isinstance(self.widget, QLabel):
            return self.widget.text()
        return ""

    def is_visible(self) -> bool:
        """是否可见"""
        return self.widget.isVisible()

    def is_enabled(self) -> bool:
        """是否启用"""
        return self.widget.isEnabled()

    def wait_for_visible(self, timeout: float = 5.0) -> bool:
        """等待可见"""
        return wait_for(lambda: self.widget.isVisible(), timeout=timeout)

    def wait_for_enabled(self, timeout: float = 5.0) -> bool:
        """等待启用"""
        return wait_for(lambda: self.widget.isEnabled(), timeout=timeout)

    def get_children(self, widget_type: type = QWidget) -> List[QWidget]:
        """获取子组件"""
        return self.widget.findChildren(widget_type)

    def find_child(self, name: str, widget_type: type = QWidget) -> Optional[QWidget]:
        """查找子组件"""
        for child in self.widget.findChildren(widget_type):
            if child.objectName() == name:
                return child
        return None

    def _log_event(self, event_type: str, data: Dict = None):
        """记录事件"""
        self._event_log.append({
            "type": event_type,
            "data": data or {},
            "widget": self.name
        })

    def get_event_log(self) -> List[Dict]:
        """获取事件日志"""
        return self._event_log.copy()

    def clear_event_log(self):
        """清空事件日志"""
        self._event_log.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 便捷测试函数
# ─────────────────────────────────────────────────────────────────────────────

def test_button_clicks(button: QPushButton, expected_calls: int = 1) -> bool:
    """测试按钮点击"""
    click_count = [0]

    def on_click():
        click_count[0] += 1

    button.clicked.connect(on_click)

    for _ in range(expected_calls):
        simulate_click(button)

    return click_count[0] == expected_calls


def test_input_validation(
    input_widget: QLineEdit,
    valid_inputs: List[str],
    invalid_inputs: List[str]
) -> Dict[str, bool]:
    """测试输入验证"""
    results = {"valid_accepted": 0, "invalid_rejected": 0}

    # 测试有效输入（假设有验证逻辑）
    for text in valid_inputs:
        input_widget.setText(text)
        if input_widget.hasAcceptableInput():
            results["valid_accepted"] += 1

    # 测试无效输入
    for text in invalid_inputs:
        input_widget.setText(text)
        if not input_widget.hasAcceptableInput():
            results["invalid_rejected"] += 1

    return results


def test_combo_box_items(combo: QComboBox, expected_items: List[str]) -> bool:
    """测试下拉框选项"""
    for i, item in enumerate(expected_items):
        if i >= combo.count():
            return False
        if combo.itemText(i) != item:
            return False
    return combo.count() == len(expected_items)


def test_list_widget_items(list_widget: QListWidget,
                           expected_items: List[str]) -> bool:
    """测试列表组件"""
    for i, item in enumerate(expected_items):
        if i >= list_widget.count():
            return False
        actual = list_widget.item(i).text()
        if actual != item:
            return False
    return list_widget.count() == len(expected_items)


def test_tree_widget_structure(tree: QTreeWidget,
                               expected_structure: Dict) -> bool:
    """测试树形组件结构"""
    root = tree.invisibleRootItem()

    def compare_item(item: QTreeWidgetItem, expected: Dict) -> bool:
        if item.text(0) != expected.get("name", ""):
            return False
        for i, child_expected in enumerate(expected.get("children", [])):
            if i >= item.childCount():
                return False
            if not compare_item(item.child(i), child_expected):
                return False
        return True

    for i, exp in enumerate(expected_structure.get("roots", [])):
        if i >= root.childCount():
            return False
        if not compare_item(root.child(i), exp):
            return False

    return True
