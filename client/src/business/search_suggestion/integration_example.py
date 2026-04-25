# -*- coding: utf-8 -*-
"""
智能联想集成示例
展示如何将搜索建议功能集成到 DeepSearchPanel
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton

# 导入建议组件
from client.src.business.search_suggestion import SuggestionController, SearchSuggestionPopup


def integrate_with_deep_search_panel(panel):
    """
    将智能联想集成到 DeepSearchPanel
    
    示例代码：
    
    ```python
    # 在 DeepSearchPanel.__init__ 中:
    self._init_suggestion()
    
    # 在 _setup_search_area 中:
    self.search_input.textChanged.connect(self._on_search_text_changed)
    self.search_input.returnPressed.connect(self._execute_search)
    ```
    """
    
    # 创建建议弹窗
    suggestion_popup = SearchSuggestionPopup()
    
    # 创建控制器
    controller = SuggestionController(panel.search_input, suggestion_popup)
    
    # 连接信号
    controller.popup.suggestion_selected.connect(lambda text: panel._execute_search(text))
    
    return controller


class IntegrationMixin:
    """集成混入类"""
    
    def _init_suggestion(self):
        """初始化搜索建议"""
        from client.src.business.search_suggestion import SuggestionController, SearchSuggestionPopup
        
        # 创建建议弹窗
        self._suggestion_popup = SearchSuggestionPopup()
        
        # 创建控制器
        self._suggestion_controller = SuggestionController(
            self.search_input, 
            self._suggestion_popup
        )
        
        # 连接信号
        self._suggestion_controller.popup.suggestion_selected.connect(
            self._on_suggestion_selected
        )
        
        # 设置防抖延迟（毫秒）
        self._suggestion_controller.debounce_ms = 300
    
    def _on_search_text_changed(self, text: str):
        """搜索框文本变化"""
        if hasattr(self, '_suggestion_controller'):
            self._suggestion_controller.on_text_changed(text)
    
    def _on_suggestion_selected(self, text: str):
        """建议被选中"""
        self.search_input.setText(text)
        self._execute_search()
    
    def _execute_search(self, query: str = None):
        """执行搜索"""
        if query is None:
            query = self.search_input.text().strip()
        
        if not query:
            return
        
        # 添加到历史记录
        if hasattr(self, '_suggestion_controller'):
            self._suggestion_controller.add_to_history(query)
        
        # 执行实际的搜索逻辑...


# 使用示例
def example_usage():
    """
    在现有 DeepSearchPanel 中添加搜索建议的完整示例
    """
    
    # 假设这是你的 DeepSearchPanel
    class MyDeepSearchPanel:
        def __init__(self):
            self.search_input = QLineEdit()
            # ... 其他初始化 ...
            
            # 1. 初始化建议功能
            self._init_suggestion()
        
        def _setup_ui(self):
            # ... 原有 UI 设置 ...
            
            # 2. 连接文本变化信号
            self.search_input.textChanged.connect(self._on_search_text_changed)
            self.search_input.returnPressed.connect(self._do_actual_search)
            
            # 3. 隐藏建议弹窗当输入框失去焦点时
            self.search_input.focusOutEvent = self._on_input_focus_out
        
        def _on_search_text_changed(self, text: str):
            """搜索框文本变化 - 触发建议查询"""
            if hasattr(self, '_suggestion_controller'):
                self._suggestion_controller.on_text_changed(text)
        
        def _on_suggestion_selected(self, text: str):
            """建议被选中 - 填充并搜索"""
            self.search_input.setText(text)
            self._do_actual_search()
        
        def _on_input_focus_out(self, event):
            """输入框失去焦点 - 延迟隐藏建议"""
            # 延迟隐藏，以便点击建议项
            QTimer.singleShot(200, self._suggestion_popup.hidePopup)
            # 调用原有 focusOutEvent
            QLineEdit.focusOutEvent(self.search_input, event)
        
        def _do_actual_search(self):
            """执行实际搜索"""
            query = self.search_input.text().strip()
            if query:
                # 添加到历史
                if hasattr(self, '_suggestion_controller'):
                    self._suggestion_controller.add_to_history(query)
                # 执行搜索...
                print(f"执行搜索: {query}")
    
    return MyDeepSearchPanel
