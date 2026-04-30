"""
配置精灵助手 - 可爱的AI助手形象提供配置提示
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPropertyAnimation
from PyQt6.QtGui import QFont


class ConfigSprite(QWidget):
    """配置精灵助手"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = False
        self._animation = None
        
        self._build_ui()
    
    def _build_ui(self):
        """构建精灵UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 精灵形象
        self._avatar = QLabel("🧞")
        self._avatar.setFont(QFont("Arial", 32))
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._avatar)
        
        # 对话框
        self._speech_bubble = QLabel()
        self._speech_bubble.setStyleSheet("""
            QLabel {
                background: #fef3c7;
                color: #92400e;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                max-width: 200px;
                word-wrap: break-word;
            }
        """)
        self._speech_bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._speech_bubble)
        
        # 默认隐藏
        self.hide()
    
    def show_hint(self, message: str):
        """显示提示"""
        self._speech_bubble.setText(message)
        self._visible = True
        self.show()
        
        # 添加弹出动画
        self._animate_in()
    
    def hide(self):
        """隐藏"""
        self._visible = False
        self._animate_out()
    
    def _animate_in(self):
        """弹出动画"""
        if self._animation:
            self._animation.stop()
        
        self.setOpacity(0)
        self.show()
        
        self._animation = QPropertyAnimation(self, b"windowOpacity")
        self._animation.setDuration(300)
        self._animation.setStartValue(0)
        self._animation.setEndValue(1)
        self._animation.start()
    
    def _animate_out(self):
        """淡出动画"""
        if self._animation:
            self._animation.stop()
        
        self._animation = QPropertyAnimation(self, b"windowOpacity")
        self._animation.setDuration(300)
        self._animation.setStartValue(1)
        self._animation.setEndValue(0)
        self._animation.finished.connect(self._on_hide_complete)
        self._animation.start()
    
    def _on_hide_complete(self):
        """隐藏完成"""
        super().hide()
        self.setOpacity(1)