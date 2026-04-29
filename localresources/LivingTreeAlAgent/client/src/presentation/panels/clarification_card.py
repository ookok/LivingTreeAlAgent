"""
需求澄清引导卡片
ClarificationCard - 在聊天中显示引导提示

嵌入到 ChatPanel 中，提供：
1. 引导提示显示
2. 选项按钮
3. 展开/收起头脑风暴详情
"""

from typing import Optional, Callable
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTextBrowser,
    QButtonGroup, QRadioButton, QSizePolicy,
    QApplication
)
from PyQt6.QtGui import QFont, QPalette, QColor


class ClarificationCard(QFrame):
    """
    需求澄清引导卡片

    信号：
    - option_selected(option: str) - 用户选择了一个选项
    - dismissed() - 用户关闭了卡片
    """

    option_selected = pyqtSignal(str)
    dismissed = pyqtSignal()

    def __init__(self, message: str, options: list, parent=None):
        super().__init__(parent)
        self.selected_option: Optional[str] = None
        self._options = options
        self._build_ui(message)

    def _build_ui(self, message: str):
        self.setObjectName("ClarificationCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWindowFlags(Qt.WindowType.ToolTip)

        # 样式
        self.setStyleSheet("""
            QFrame#ClarificationCard {
                background: #1e3a5f;
                border: 2px solid #3b82f6;
                border-radius: 12px;
                padding: 16px;
                margin: 8px;
            }
            QLabel#Title {
                color: #60a5fa;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#Message {
                color: #e0e0e0;
                font-size: 13px;
                line-height: 1.5;
            }
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton#Secondary {
                background: transparent;
                color: #9ca3af;
                border: 1px solid #4b5563;
            }
            QPushButton#Secondary:hover {
                background: #374151;
                color: #e0e0e0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 标题
        title = QLabel("💡 需求澄清")
        title.setObjectName("Title")
        layout.addWidget(title)

        # 消息
        msg_label = QLabel(message)
        msg_label.setObjectName("Message")
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(msg_label)

        # 选项按钮组
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_group = QButtonGroup()
        self.buttons = []

        for i, opt in enumerate(self._options):
            btn = QPushButton(opt)
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked, o=opt: self._on_option_clicked(o))
            self.buttons.append(btn)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 收起/关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        dismiss_btn = QPushButton("收起")
        dismiss_btn.setObjectName("Secondary")
        dismiss_btn.setFixedWidth(60)
        dismiss_btn.clicked.connect(self._on_dismiss)
        close_layout.addWidget(dismiss_btn)

        layout.addLayout(close_layout)

    def _on_option_clicked(self, option: str):
        self.selected_option = option
        self.option_selected.emit(option)
        self._fade_out()

    def _on_dismiss(self):
        self.dismissed.emit()
        self._fade_out()

    def _fade_out(self):
        """淡出动画"""
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        self.setWindowOpacity(1.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.finished.connect(self.deleteLater)
        anim.start()


class InlineClarifyWidget(QWidget):
    """
    内联需求澄清组件 - 嵌入到聊天输入框上方

    提供快速选项按钮
    """

    option_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background: #1e3a5f;
                border-bottom: 1px solid #3b82f6;
                padding: 8px 16px;
            }
            QLabel {
                color: #60a5fa;
                font-size: 12px;
            }
            QPushButton {
                background: transparent;
                color: #9ca3af;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #374151;
                color: #e0e0e0;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        icon = QLabel("💡")
        layout.addWidget(icon)

        hint = QLabel("想要明确需求？")
        layout.addWidget(hint)

        layout.addStretch()

        # 快速按钮
        clarify_btn = QPushButton("🎯 头脑风暴")
        clarify_btn.clicked.connect(lambda: self.option_clicked.emit("clarify"))
        layout.addWidget(clarify_btn)

        later_btn = QPushButton("以后再说")
        later_btn.clicked.connect(lambda: self.option_clicked.emit("later"))
        layout.addWidget(later_btn)

    def showEvent(self, event):
        """显示时带动画"""
        super().showEvent(event)
        self.setWindowOpacity(0)
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()


class MiniClarifyBar(QWidget):
    """
    迷你澄清工具条 - 固定在聊天区域底部

    提供需求澄清的快捷入口，可拖拽调整位置
    """

    clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragging = False
        self._build_ui()

    def _build_ui(self):
        self.setFixedHeight(36)
        self.setWindowFlags(Qt.WindowType.ToolTip)

        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e3a5f, stop:1 #1a1a2e);
                border-top: 1px solid #3b82f6;
            }
            QPushButton {
                background: transparent;
                color: #60a5fa;
                border: none;
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                color: #93c5fd;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        icon = QLabel("🎯")
        layout.addWidget(icon)

        hint = QLabel("需求不明确？试试头脑风暴")
        layout.addWidget(hint)

        layout.addStretch()

        start_btn = QPushButton("开始梳理")
        start_btn.clicked.connect(lambda: self.clicked.emit("start"))
        layout.addWidget(start_btn)

        dismiss_btn = QPushButton("×")
        dismiss_btn.setFixedWidth(24)
        dismiss_btn.clicked.connect(lambda: self.clicked.emit("dismiss"))
        layout.addWidget(dismiss_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._start_pos)

    def mouseReleaseEvent(self, event):
        self._dragging = False