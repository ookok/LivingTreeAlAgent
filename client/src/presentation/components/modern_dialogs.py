"""现代化对话框组件 - 支持各种弹窗需求"""

from PyQt6.QtWidgets import (
    QDialog, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSizePolicy, QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

class ModernDialog(QDialog):
    """现代化对话框基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
                border-radius: 12px;
                border: none;
            }
        """)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
    
    def set_title(self, title):
        """设置标题"""
        pass

class ConfirmationDialog(ModernDialog):
    """确认对话框"""
    
    confirmed = pyqtSignal(bool)
    
    def __init__(self, title="", message="", parent=None):
        super().__init__(parent)
        self._init_ui(title, message)
    
    def _init_ui(self, title, message):
        super()._init_ui()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/info.png").pixmap(48, 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 18px;
                font-weight: 600;
                text-align: center;
            }
        """)
        layout.addWidget(title_label)
        
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
                text-align: center;
            }
        """)
        layout.addWidget(message_label)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #f3f4f6;
                color: #374151;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e5e7eb;
            }
        """)
        cancel_btn.clicked.connect(lambda: self._close(False))
        buttons_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #4f46e5;
            }
        """)
        confirm_btn.clicked.connect(lambda: self._close(True))
        buttons_layout.addWidget(confirm_btn)
        
        layout.addLayout(buttons_layout)
        
        self.setFixedSize(320, 220)
    
    def _close(self, confirmed):
        self.confirmed.emit(confirmed)
        self.close()

class ProgressDialog(ModernDialog):
    """进度对话框"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._init_ui(title)
    
    def _init_ui(self, title):
        super()._init_ui()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 16px;
                font-weight: 600;
            }
        """)
        layout.addWidget(title_label)
        
        self._progress = QProgressBar()
        self._progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 8px;
                height: 8px;
                background: #e5e7eb;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 8px;
            }
        """)
        layout.addWidget(self._progress)
        
        self._status_label = QLabel("处理中...")
        self._status_label.setStyleSheet("color: #6b7280; font-size: 13px;")
        layout.addWidget(self._status_label)
        
        self.setFixedSize(320, 140)
    
    def set_progress(self, value):
        """设置进度"""
        self._progress.setValue(value)
    
    def set_status(self, status):
        """设置状态"""
        self._status_label.setText(status)

class ToastNotification(QFrame):
    """Toast通知"""
    
    def __init__(self, message="", type="info", parent=None):
        super().__init__(parent)
        self._init_ui(message, type)
    
    def _init_ui(self, message, type):
        self.setStyleSheet("""
            QFrame {
                background: #1f2937;
                border-radius: 8px;
                padding: 12px 16px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        icon_label = QLabel()
        icons = {
            "info": "info.png",
            "success": "success.png",
            "warning": "warning.png",
            "error": "error.png"
        }
        icon_label.setPixmap(QIcon(f"icons/{icons.get(type, 'info.png')}").pixmap(20, 20))
        layout.addWidget(icon_label)
        
        message_label = QLabel(message)
        message_label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(message_label)
    
    def show(self, duration=3000):
        """显示通知"""
        super().show()
        QTimer.singleShot(duration, self.hide)

from PyQt6.QtCore import QTimer