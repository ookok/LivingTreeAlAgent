"""聊天窗口面板 - 整合消息气泡和上下文面板"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QScrollArea,
    QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..components.smart_message_bubble import MessageBubble, CodeMessageBubble, ImageMessageBubble, MessageType
from ..components.context_panel import ContextPanel
from ..components.smart_input_field import SmartInputField

class ChatWindow(QFrame):
    """聊天窗口面板"""
    
    send_message = pyqtSignal(str)
    action_triggered = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._message_bubbles = []
    
    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
            }
        """)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #e5e7eb;
                width: 2px;
            }
        """)
        
        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 4px;
            }
        """)
        
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch()
        
        self._scroll_area.setWidget(self._content_widget)
        chat_layout.addWidget(self._scroll_area)
        
        self._input_field = SmartInputField()
        self._input_field.send_message.connect(self.send_message)
        chat_layout.addWidget(self._input_field)
        
        splitter.addWidget(chat_area)
        
        self._context_panel = ContextPanel()
        self._context_panel.action_triggered.connect(self.action_triggered)
        splitter.addWidget(self._context_panel)
        
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
    
    def add_message(self, content, message_type=MessageType.USER, confidence=1.0, message_type_specific=False):
        """添加消息"""
        if message_type_specific == "code":
            bubble = CodeMessageBubble()
            bubble.set_code(content)
        elif message_type_specific == "image":
            bubble = ImageMessageBubble()
            bubble.set_image(content, "图片描述")
        else:
            bubble = MessageBubble()
            bubble.set_message(content, message_type, confidence)
        
        self._message_bubbles.append(bubble)
        self._content_layout.insertWidget(len(self._content_layout) - 1, bubble)
        
        self._scroll_to_bottom()
    
    def add_typing_indicator(self):
        """添加输入指示器"""
        bubble = MessageBubble()
        bubble.set_message("", MessageType.AI)
        bubble.start_typing_animation()
        self._message_bubbles.append(bubble)
        self._content_layout.insertWidget(len(self._content_layout) - 1, bubble)
        self._scroll_to_bottom()
        
        return len(self._message_bubbles) - 1
    
    def update_message(self, index, content, confidence=1.0, message_type_specific=None):
        """更新消息"""
        if index < len(self._message_bubbles):
            bubble = self._message_bubbles[index]
            
            if isinstance(bubble, MessageBubble):
                bubble.stop_typing_animation()
                bubble.set_message(content, MessageType.AI, confidence)
            elif isinstance(bubble, CodeMessageBubble) and message_type_specific == "code":
                bubble.set_code(content)
            elif isinstance(bubble, ImageMessageBubble) and message_type_specific == "image":
                bubble.set_image(content, "图片描述")
            
            self._scroll_to_bottom()
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        scroll_bar = self._scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
    
    def clear_messages(self):
        """清空消息"""
        for bubble in self._message_bubbles:
            bubble.deleteLater()
        self._message_bubbles.clear()
    
    def set_topics(self, topics):
        """设置主题"""
        self._context_panel.set_topics(topics)
    
    def set_history(self, history):
        """设置历史"""
        self._context_panel.set_history(history)
    
    def add_action(self, action_name, icon_name):
        """添加操作"""
        self._context_panel.add_action_button(action_name, icon_name)
    
    def focus_input(self):
        """聚焦输入框"""
        self._input_field.focus()