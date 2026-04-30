"""智能输入框组件 - 支持AI辅助输入和快捷指令"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QKeySequence

class SmartInputField(QWidget):
    """智能输入框组件"""
    
    send_message = pyqtSignal(str)
    suggestion_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._suggestions = []
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._suggestions_list = QListWidget()
        self._suggestions_list.setFixedHeight(80)
        self._suggestions_list.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background: #eff6ff;
            }
            QListWidget::item:selected {
                background: #dbeafe;
                color: #1d4ed8;
            }
        """)
        self._suggestions_list.itemClicked.connect(self._on_suggestion_clicked)
        self._suggestions_list.hide()
        layout.addWidget(self._suggestions_list)
        
        self._input_frame = QFrame()
        self._input_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
        """)
        
        input_layout = QHBoxLayout(self._input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)
        
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("输入消息...")
        self._input_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 8px 12px;
                font-size: 14px;
            }
        """)
        self._input_edit.returnPressed.connect(self._send_message)
        self._input_edit.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self._input_edit)
        
        self._send_btn = QPushButton()
        self._send_btn.setIcon(QIcon("icons/send.png"))
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #4f46e5;
            }
            QPushButton:pressed {
                background: #4338ca;
            }
        """)
        self._send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self._send_btn)
        
        layout.addWidget(self._input_frame)
    
    def _on_text_changed(self, text):
        """文本变化处理"""
        if text:
            self._fetch_suggestions(text)
        else:
            self._hide_suggestions()
    
    def _fetch_suggestions(self, text):
        """获取输入建议"""
        if hasattr(self, '_suggestion_timer'):
            self._suggestion_timer.stop()
        
        self._suggestion_timer = QTimer()
        self._suggestion_timer.timeout.connect(lambda: self._generate_suggestions(text))
        self._suggestion_timer.start(300)
    
    def _generate_suggestions(self, text):
        """生成建议"""
        text_lower = text.lower()
        
        suggestions = []
        
        if text_lower.startswith('/'):
            suggestions.extend([
                "/code - 生成代码",
                "/search - 搜索",
                "/analyze - 分析",
                "/create - 创建",
            ])
        elif '代码' in text_lower or '编程' in text_lower:
            suggestions.extend([
                "写一段Python代码",
                "优化这段代码",
                "解释这段代码",
            ])
        elif '搜索' in text_lower or '查找' in text_lower:
            suggestions.extend([
                "搜索最新技术资料",
                "搜索相关文档",
            ])
        elif '分析' in text_lower:
            suggestions.extend([
                "分析数据",
                "分析代码质量",
            ])
        
        self._show_suggestions(suggestions)
    
    def _show_suggestions(self, suggestions):
        """显示建议"""
        self._suggestions = suggestions
        
        if suggestions:
            self._suggestions_list.clear()
            for suggestion in suggestions[:4]:
                item = QListWidgetItem(suggestion)
                self._suggestions_list.addItem(item)
            self._suggestions_list.show()
        else:
            self._hide_suggestions()
    
    def _hide_suggestions(self):
        """隐藏建议"""
        self._suggestions_list.hide()
        self._suggestions_list.clear()
    
    def _on_suggestion_clicked(self, item):
        """选择建议"""
        text = item.text().split(' - ')[0] if ' - ' in item.text() else item.text()
        self._input_edit.setText(text)
        self.suggestion_selected.emit(text)
        self._hide_suggestions()
    
    def _send_message(self):
        """发送消息"""
        text = self._input_edit.text().strip()
        if text:
            self.send_message.emit(text)
            self._input_edit.clear()
            self._hide_suggestions()
    
    def set_placeholder(self, text):
        """设置占位文本"""
        self._input_edit.setPlaceholderText(text)
    
    def get_text(self):
        """获取输入文本"""
        return self._input_edit.text()
    
    def clear(self):
        """清空输入"""
        self._input_edit.clear()
    
    def focus(self):
        """获取焦点"""
        self._input_edit.setFocus()