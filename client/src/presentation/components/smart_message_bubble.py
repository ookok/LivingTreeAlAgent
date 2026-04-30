"""智能消息气泡组件 - 支持多模态消息展示和智能状态指示"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
import asyncio
import time

class MessageType:
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
    ERROR = "error"

class MessageBubble(QFrame):
    """智能消息气泡"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._message_type = MessageType.USER
        self._confidence = 1.0
    
    def _init_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(12, 8, 12, 8)
        self._main_layout.setSpacing(4)
        
        self._content_label = QLabel()
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._main_layout.addWidget(self._content_label)
        
        self._meta_layout = QHBoxLayout()
        self._main_layout.addLayout(self._meta_layout)
        
        self._time_label = QLabel()
        self._time_label.setStyleSheet("color: #888888; font-size: 10px;")
        self._meta_layout.addWidget(self._time_label)
        
        self._meta_layout.addStretch()
        
        self._confidence_bar = QFrame()
        self._confidence_bar.setFixedHeight(4)
        self._confidence_bar.setFixedWidth(60)
        self._confidence_bar.setStyleSheet("border-radius: 2px;")
        self._meta_layout.addWidget(self._confidence_bar)
        
        self._status_icon = QLabel()
        self._status_icon.setFixedSize(16, 16)
        self._meta_layout.addWidget(self._status_icon)
    
    def set_message(self, content, message_type=MessageType.USER, confidence=1.0):
        """设置消息内容"""
        self._message_type = message_type
        self._confidence = confidence
        
        self._content_label.setText(content)
        self._time_label.setText(time.strftime("%H:%M"))
        
        self._update_style()
        self._update_confidence(confidence)
    
    def _update_style(self):
        """更新样式"""
        if self._message_type == MessageType.USER:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                        stop:0 #6366f1, stop:1 #8b5cf6);
                    border-radius: 16px;
                }
                QLabel { color: white; }
            """)
            self._status_icon.setPixmap(QIcon("icons/user.png").pixmap(16, 16))
        
        elif self._message_type == MessageType.AI:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                        stop:0 #374151, stop:1 #1f2937);
                    border: 1px solid #4b5563;
                    border-radius: 16px;
                }
                QLabel { color: #e5e7eb; }
            """)
            self._status_icon.setPixmap(QIcon("icons/bot.png").pixmap(16, 16))
        
        elif self._message_type == MessageType.SYSTEM:
            self.setStyleSheet("""
                QFrame {
                    background: #f3f4f6;
                    border-radius: 8px;
                }
                QLabel { color: #6b7280; }
            """)
        
        elif self._message_type == MessageType.ERROR:
            self.setStyleSheet("""
                QFrame {
                    background: #fee2e2;
                    border: 1px solid #fca5a5;
                    border-radius: 8px;
                }
                QLabel { color: #dc2626; }
            """)
    
    def _update_confidence(self, confidence):
        """更新置信度显示"""
        if confidence >= 0.8:
            color = "#10b981"
        elif confidence >= 0.5:
            color = "#f59e0b"
        else:
            color = "#ef4444"
        
        width = int(confidence * 60)
        self._confidence_bar.setFixedWidth(width)
        self._confidence_bar.setStyleSheet(f"background: {color}; border-radius: 2px;")
    
    def start_typing_animation(self):
        """开始输入动画"""
        self._content_label.setText("🤖 正在思考...")
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._update_typing_dots)
        self._typing_dots = 0
        self._typing_timer.start(500)
    
    def _update_typing_dots(self):
        """更新输入动画"""
        self._typing_dots = (self._typing_dots + 1) % 4
        dots = "." * self._typing_dots
        self._content_label.setText(f"🤖 正在思考{dots}")
    
    def stop_typing_animation(self):
        """停止输入动画"""
        if hasattr(self, '_typing_timer'):
            self._typing_timer.stop()

class CodeMessageBubble(QFrame):
    """代码消息气泡"""
    
    run_code = pyqtSignal(str)
    copy_code = pyqtSignal(str)
    explain_code = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        self._code_edit = QTextEdit()
        self._code_edit.setReadOnly(True)
        self._code_edit.setStyleSheet("""
            QTextEdit {
                background: #0d1117;
                color: #c9d1d9;
                font-family: 'JetBrains Mono', monospace;
                font-size: 13px;
                border: none;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self._code_edit)
        
        buttons_layout = QHBoxLayout()
        
        self._run_btn = QPushButton("▶ 运行")
        self._run_btn.clicked.connect(lambda: self.run_code.emit(self._code_edit.toPlainText()))
        buttons_layout.addWidget(self._run_btn)
        
        self._copy_btn = QPushButton("📋 复制")
        self._copy_btn.clicked.connect(lambda: self.copy_code.emit(self._code_edit.toPlainText()))
        buttons_layout.addWidget(self._copy_btn)
        
        self._explain_btn = QPushButton("💡 解释")
        self._explain_btn.clicked.connect(lambda: self.explain_code.emit(self._code_edit.toPlainText()))
        buttons_layout.addWidget(self._explain_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
    
    def set_code(self, code, language="python"):
        """设置代码内容"""
        self._code_edit.setPlainText(code)

class ImageMessageBubble(QFrame):
    """图片消息气泡"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._image_label = QLabel()
        self._image_label.setScaledContents(True)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum
        )
        layout.addWidget(self._image_label)
        
        self._caption_label = QLabel()
        self._caption_label.setWordWrap(True)
        self._caption_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                padding: 4px;
            }
        """)
        layout.addWidget(self._caption_label)
    
    def set_image(self, image_path, caption=""):
        """设置图片"""
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio)
        self._image_label.setPixmap(scaled_pixmap)
        self._caption_label.setText(caption)