"""
追问面板组件 - 为 AI 回答追加智能追问按钮
==========================================

实现 Phase 2：UI追问按钮+交互功能

功能：
1. GuidancePanel - 追问面板容器
2. GuidanceButton - 追问按钮（点击发送）
3. GuidanceCard - 追问卡片（选项式）
4. GuidanceStyleManager - 样式管理器

设计特点：
- 支持多种展示模式：按钮式/卡片式/内联式
- 悬停动画效果
- 点击回调集成
- 主题适配（深色/浅色）
"""

from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# PyQt6 imports
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QFrame, QSizePolicy, QGraphicsOpacityEffect
    )
    from PyQt6.QtCore import (
        Qt, QSize, QPoint, QPropertyAnimation, QEasingCurve,
        QParallelAnimationGroup, pyqtSignal, pyqtSlot, QTimer
    )
    from PyQt6.QtGui import (
        QFont, QEnterEvent, QMouseEvent, QPainter, QColor, QBrush, QPen
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("[GuidancePanel] PyQt6 not available, using text mode")


# ============== 展示模式枚举 ==============

class GuidanceDisplayMode(Enum):
    """追问展示模式"""
    BUTTON = "button"       # 按钮式（横排）
    CARD = "card"           # 卡片式（选项）
    INLINE = "inline"       # 内联式（文本链接）


class GuidancePosition(Enum):
    """追问位置"""
    BELOW = "below"         # 在回答下方
    RIGHT = "right"         # 在回答右侧
    FLOATING = "floating"   # 浮动提示


# ============== 样式定义 ==============

DARK_THEME_STYLES = """
/* 追问面板 - 深色主题 */
.GuidancePanel {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

.GuidancePanel:hover {
    border-color: #007acc;
}

/* 追问标题 */
.GuidanceTitle {
    color: #cccccc;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 8px;
}

/* 追问按钮 */
.GuidanceButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 8px 16px;
    color: #ffffff;
    font-size: 13px;
    min-width: 120px;
    max-width: 200px;
}

.GuidanceButton:hover {
    background-color: #007acc;
    border-color: #007acc;
}

.GuidanceButton:pressed {
    background-color: #005a9e;
}

.GuidanceButton:disabled {
    background-color: #2d2d30;
    color: #666666;
    border-color: #3e3e42;
}

/* 追问卡片 */
.GuidanceCard {
    background-color: #333337;
    border: 1px solid #3e3e42;
    border-radius: 8px;
    padding: 12px;
    min-width: 150px;
    max-width: 250px;
}

.GuidanceCard:hover {
    background-color: #3e3e42;
    border-color: #007acc;
}

/* 内联追问 */
.GuidanceInline {
    color: #007acc;
    font-size: 13px;
    text-decoration: none;
    padding: 4px 8px;
}

.GuidanceInline:hover {
    color: #1e90ff;
    text-decoration: underline;
}
"""

LIGHT_THEME_STYLES = """
/* 追问面板 - 浅色主题 */
.GuidancePanel {
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

.GuidancePanel:hover {
    border-color: #0078d4;
}

/* 追问标题 */
.GuidanceTitle {
    color: #333333;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 8px;
}

/* 追问按钮 */
.GuidanceButton {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 6px;
    padding: 8px 16px;
    color: #333333;
    font-size: 13px;
    min-width: 120px;
    max-width: 200px;
}

.GuidanceButton:hover {
    background-color: #0078d4;
    border-color: #0078d4;
    color: #ffffff;
}

.GuidanceButton:pressed {
    background-color: #005a9e;
}

.GuidanceButton:disabled {
    background-color: #f0f0f0;
    color: #999999;
    border-color: #e0e0e0;
}

/* 追问卡片 */
.GuidanceCard {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    min-width: 150px;
    max-width: 250px;
}

.GuidanceCard:hover {
    background-color: #f0f5ff;
    border-color: #0078d4;
}

/* 内联追问 */
.GuidanceInline {
    color: #0078d4;
    font-size: 13px;
    text-decoration: none;
    padding: 4px 8px;
}

.GuidanceInline:hover {
    color: #005a9e;
    text-decoration: underline;
}
"""


# ============== 追问数据 ==============

@dataclass
class GuidanceItem:
    """追问项"""
    text: str                    # 追问文本
    action: str = ""            # 操作标识
    icon: str = ""              # 图标
    enabled: bool = True         # 是否启用
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """显示文本（带图标）"""
        if self.icon:
            return f"{self.icon} {self.text}"
        return self.text


# ============== 追问按钮 ==============

class GuidanceButton(QPushButton if PYQT6_AVAILABLE else object):
    """
    追问按钮组件

    信号：
    - clicked_with_action(action: str, text: str): 点击追问时触发
    - hovered(item: GuidanceItem): 悬停时触发
    """

    if PYQT6_AVAILABLE:
        clicked_with_action = pyqtSignal(str, str)
        hovered = pyqtSignal(object)

    def __init__(
        self,
        item: 'GuidanceItem',
        parent: Optional[QWidget] = None
    ):
        if not PYQT6_AVAILABLE:
            self.item = item
            return

        super().__init__(item.display_text, parent)
        self.item = item
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("GuidanceButton")

        # 设置样式
        self.setStyleSheet("""
            QPushButton#GuidanceButton {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 8px 16px;
                color: #ffffff;
                font-size: 13px;
                min-width: 120px;
                max-width: 200px;
            }
            QPushButton#GuidanceButton:hover {
                background-color: #007acc;
                border-color: #007acc;
            }
            QPushButton#GuidanceButton:pressed {
                background-color: #005a9e;
            }
        """)

        # 禁用状态
        if not self.item.enabled:
            self.setEnabled(False)

        # 点击信号
        self.clicked.connect(self._on_clicked)

        # 悬停效果
        self.setMouseTracking(True)

    def _on_clicked(self):
        """点击处理"""
        if self.item.action:
            self.clicked_with_action.emit(self.item.action, self.item.text)
        else:
            # 使用文本作为action
            self.clicked_with_action.emit(self.item.text, self.item.text)

    def enterEvent(self, event):
        """鼠标进入"""
        if PYQT6_AVAILABLE:
            super().enterEvent(event)
            self.hovered.emit(self.item)

    def set_hover_style(self, hovered: bool):
        """设置悬停样式"""
        if hovered:
            self.setStyleSheet("""
                QPushButton#GuidanceButton {
                    background-color: #007acc;
                    border: 1px solid #007acc;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #ffffff;
                    font-size: 13px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton#GuidanceButton {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #ffffff;
                    font-size: 13px;
                    min-width: 120px;
                    max-width: 200px;
                }
            """)


# ============== 追问卡片 ==============

class GuidanceCard(QFrame if PYQT6_AVAILABLE else object):
    """
    追问卡片组件

    信号：
    - selected(action: str, text: str): 选中追问时触发
    """

    if PYQT6_AVAILABLE:
        selected = pyqtSignal(str, str)

    def __init__(
        self,
        item: 'GuidanceItem',
        parent: Optional[QWidget] = None
    ):
        if not PYQT6_AVAILABLE:
            self.item = item
            return

        super().__init__(parent)
        self.item = item
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setObjectName("GuidanceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 图标 + 文本
        if self.item.icon:
            icon_label = QLabel(self.item.icon)
            icon_label.setStyleSheet("font-size: 16px;")
            layout.addWidget(icon_label)

        # 主文本
        text_label = QLabel(self.item.text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            line-height: 1.4;
        """)
        layout.addWidget(text_label)

        # 样式
        self.setStyleSheet("""
            QFrame#GuidanceCard {
                background-color: #333337;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                padding: 12px;
                min-width: 150px;
                max-width: 250px;
            }
            QFrame#GuidanceCard:hover {
                background-color: #3e3e42;
                border-color: #007acc;
            }
        """)

        # 点击
        self.setMouseTracking(True)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤"""
        if PYQT6_AVAILABLE and isinstance(event, QMouseEvent):
            if event.type() == QMouseEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._on_clicked()
        return super().eventFilter(obj, event)

    def _on_clicked(self):
        """点击处理"""
        if self.item.action:
            self.selected.emit(self.item.action, self.item.text)
        else:
            self.selected.emit(self.item.text, self.item.text)


# ============== 追问面板 ==============

class GuidancePanel(QFrame if PYQT6_AVAILABLE else object):
    """
    追问面板组件

    支持多种展示模式：
    - BUTTON: 按钮式（横排）
    - CARD: 卡片式（网格）
    - INLINE: 内联式（文本链接）

    信号：
    - guidance_clicked(action: str, text: str): 追问被点击
    - guidance_dismissed(): 追问被关闭
    - all_guidance_used(): 所有追问都被使用过
    """

    if PYQT6_AVAILABLE:
        guidance_clicked = pyqtSignal(str, str)
        guidance_dismissed = pyqtSignal()
        all_guidance_used = pyqtSignal()

    def __init__(
        self,
        items: Optional[List['GuidanceItem']] = None,
        display_mode: GuidanceDisplayMode = GuidanceDisplayMode.BUTTON,
        title: str = "您可能还想问：",
        show_title: bool = True,
        parent: Optional[QWidget] = None
    ):
        if not PYQT6_AVAILABLE:
            self.items = items or []
            self.display_mode = display_mode
            return

        super().__init__(parent)
        self.items = items or []
        self.display_mode = display_mode
        self.title = title
        self.show_title_flag = show_title
        self._used_actions: set = set()  # 已使用的action

        self._setup_ui()
        self._build_items()

    def _setup_ui(self):
        """设置UI"""
        self.setObjectName("GuidancePanel")
        self.setStyleSheet(DARK_THEME_STYLES)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # 标题
        if self.show_title_flag:
            self.title_label = QLabel(self.title)
            self.title_label.setObjectName("GuidanceTitle")
            self.title_label.setStyleSheet("""
                color: #cccccc;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 8px;
            """)
            self.main_layout.addWidget(self.title_label)

        # 内容区域（根据模式）
        if self.display_mode == GuidanceDisplayMode.BUTTON:
            self._setup_button_mode()
        elif self.display_mode == GuidanceDisplayMode.CARD:
            self._setup_card_mode()
        else:
            self._setup_inline_mode()

    def _setup_button_mode(self):
        """按钮模式"""
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(8)
        self.main_layout.addLayout(self.content_layout)

    def _setup_card_mode(self):
        """卡片模式"""
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.content_layout)

    def _setup_inline_mode(self):
        """内联模式"""
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(4)
        self.main_layout.addLayout(self.content_layout)

    def _build_items(self):
        """构建追问项"""
        if not PYQT6_AVAILABLE:
            return

        # 清除现有项
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for guidance_item in self.items:
            if self.display_mode == GuidanceDisplayMode.BUTTON:
                self._add_button(guidance_item)
            elif self.display_mode == GuidanceDisplayMode.CARD:
                self._add_card(guidance_item)
            else:
                self._add_inline(guidance_item)

    def _add_button(self, item: 'GuidanceItem'):
        """添加按钮"""
        btn = GuidanceButton(item, self)
        btn.clicked_with_action.connect(self._on_guidance_clicked)
        self.content_layout.addWidget(btn)

    def _add_card(self, item: 'GuidanceItem'):
        """添加卡片"""
        card = GuidanceCard(item, self)
        card.selected.connect(self._on_guidance_clicked)
        self.content_layout.addWidget(card)

    def _add_inline(self, item: 'GuidanceItem'):
        """添加内联文本"""
        from PyQt6.QtWidgets import QLabel, QPushButton

        inline_widget = QWidget()
        inline_layout = QHBoxLayout(inline_widget)
        inline_layout.setContentsMargins(0, 0, 0, 0)

        # 箭头图标
        arrow = QLabel("▸ ")
        arrow.setStyleSheet("color: #007acc; font-size: 13px;")

        # 文本按钮
        text_btn = QPushButton(item.text)
        text_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        text_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #007acc;
                font-size: 13px;
                text-align: left;
                padding: 4px 8px;
            }
            QPushButton:hover {
                color: #1e90ff;
                text-decoration: underline;
            }
        """)
        text_btn.clicked.connect(lambda: self._on_guidance_clicked(item.action or item.text, item.text))

        inline_layout.addWidget(arrow)
        inline_layout.addWidget(text_btn)
        inline_layout.addStretch()

        self.content_layout.addWidget(inline_widget)

    def _on_guidance_clicked(self, action: str, text: str):
        """追问被点击"""
        self._used_actions.add(action)
        self.guidance_clicked.emit(action, text)

        # 检查是否所有追问都被使用
        all_actions = {item.action or item.text for item in self.items}
        if self._used_actions >= all_actions:
            self.all_guidance_used.emit()

    def set_items(self, items: List['GuidanceItem']):
        """设置追问项"""
        self.items = items
        self._used_actions.clear()
        self._build_items()

    def append_items(self, items: List['GuidanceItem']):
        """追加追问项"""
        self.items.extend(items)
        self._build_items()

    def clear_used_markers(self):
        """清除已使用标记"""
        self._used_actions.clear()

    def set_theme(self, theme: str = "dark"):
        """设置主题"""
        if theme == "light":
            self.setStyleSheet(LIGHT_THEME_STYLES)
        else:
            self.setStyleSheet(DARK_THEME_STYLES)

    def show_animation(self, duration: int = 300):
        """显示动画"""
        if not PYQT6_AVAILABLE:
            return

        self.show()
        self.setWindowOpacity(0)

        # 淡入动画
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(duration)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.start()

    def hide_animation(self, duration: int = 200):
        """隐藏动画"""
        if not PYQT6_AVAILABLE:
            self.hide()
            return

        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(duration)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.finished.connect(self.hide)
        self.animation.start()


# ============== 追问管理器 ==============

class GuidanceManager:
    """
    追问管理器

    集成 EnhancedAgentChat 的追问功能到 UI
    提供统一的追问显示和交互控制
    """

    def __init__(
        self,
        enhanced_chat=None,
        display_mode: GuidanceDisplayMode = GuidanceDisplayMode.BUTTON,
        max_visible: int = 3
    ):
        """
        Args:
            enhanced_chat: EnhancedAgentChat 实例
            display_mode: 展示模式
            max_visible: 最大可见追问数
        """
        self.enhanced_chat = enhanced_chat
        self.display_mode = display_mode
        self.max_visible = max_visible
        self._current_panel: Optional['GuidancePanel'] = None
        self._on_send_callback: Optional[Callable[[str], None]] = None

    def set_send_callback(self, callback: Callable[[str], None]):
        """设置发送回调"""
        self._on_send_callback = callback

    def display_guidance(self, parent_widget: Optional[QWidget] = None) -> Optional['GuidancePanel']:
        """
        显示追问面板

        Returns:
            GuidancePanel 或 None
        """
        if not self.enhanced_chat:
            return None

        # 获取追问结果
        guidance = self.enhanced_chat.get_guidance()
        if not guidance or not guidance.questions:
            return None

        # 转换为 GuidanceItem
        items = []
        for i, q in enumerate(guidance.questions[:self.max_visible]):
            item = GuidanceItem(
                text=q,
                action=f"guidance_{i}",  # 使用索引作为action
                icon="💬" if i == 0 else None
            )
            items.append(item)

        # 创建面板
        self._current_panel = GuidancePanel(
            items=items,
            display_mode=self.display_mode,
            title="您可能还想问："
        )

        # 连接信号
        self._current_panel.guidance_clicked.connect(self._on_guidance_clicked)

        # 添加到父控件
        if parent_widget and PYQT6_AVAILABLE:
            from PyQt6.QtWidgets import QVBoxLayout
            if parent_widget.layout():
                parent_widget.layout().addWidget(self._current_panel)
            else:
                layout = QVBoxLayout(parent_widget)
                layout.addWidget(self._current_panel)

        # 显示动画
        self._current_panel.show_animation()

        return self._current_panel

    def _on_guidance_clicked(self, action: str, text: str):
        """追问被点击"""
        if self._on_send_callback:
            self._on_send_callback(text)

        # 隐藏面板
        if self._current_panel:
            self._current_panel.hide_animation()

    def clear(self):
        """清除当前追问"""
        if self._current_panel:
            self._current_panel.hide()
            self._current_panel.deleteLater()
            self._current_panel = None


# ============== 便捷函数 ==============

def create_guidance_panel(
    questions: List[str],
    display_mode: GuidanceDisplayMode = GuidanceDisplayMode.BUTTON,
    on_click: Optional[Callable[[str], None]] = None,
    parent: Optional[QWidget] = None
) -> Optional['GuidancePanel']:
    """
    创建追问面板的便捷函数

    Args:
        questions: 追问列表
        display_mode: 展示模式
        on_click: 点击回调，接收追问文本
        parent: 父控件

    Returns:
        GuidancePanel 实例
    """
    if not questions:
        return None

    items = [
        GuidanceItem(text=q, action=q, icon="💬" if i == 0 else "")
        for i, q in enumerate(questions)
    ]

    panel = GuidancePanel(
        items=items,
        display_mode=display_mode,
        parent=parent
    )

    if on_click:
        panel.guidance_clicked.connect(lambda a, t: on_click(t))

    return panel


def quick_guidance_response(
    response_text: str,
    guidance_result,
    mode: GuidanceDisplayMode = GuidanceDisplayMode.BUTTON
) -> str:
    """
    快速生成带追问的响应文本

    Args:
        response_text: 原始响应
        guidance_result: GuidanceResult 实例
        mode: 展示模式

    Returns:
        带追问的响应文本
    """
    if not guidance_result or not guidance_result.questions:
        return response_text

    lines = ["", "---", "**您可能还想问：**"]
    for i, q in enumerate(guidance_result.questions, 1):
        if mode == GuidanceDisplayMode.BUTTON:
            lines.append(f"{i}. {q}")
        else:
            lines.append(f"- {q}")

    return response_text + "\n".join(lines)


# ============== 测试 ==============

if __name__ == "__main__" and PYQT6_AVAILABLE:
    import sys
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton

    app = QApplication(sys.argv)

    # 测试窗口
    window = QWidget()
    window.setWindowTitle("GuidancePanel 测试")
    window.setStyleSheet("background-color: #1e1e1e;")
    window.resize(600, 400)

    layout = QVBoxLayout(window)
    layout.setSpacing(16)

    # 测试数据
    test_questions = [
        "需要我详细解释一下吗？",
        "还有其他方面想了解吗？",
        "这个回答对您有帮助吗？",
    ]

    # 测试按钮模式
    btn_label = QLabel("按钮模式：")
    btn_label.setStyleSheet("color: white; font-size: 14px;")
    layout.addWidget(btn_label)

    btn_panel = create_guidance_panel(
        test_questions,
        display_mode=GuidanceDisplayMode.BUTTON,
        on_click=lambda t: print(f"点击追问: {t}")
    )
    layout.addWidget(btn_panel)

    # 测试卡片模式
    card_label = QLabel("卡片模式：")
    card_label.setStyleSheet("color: white; font-size: 14px;")
    layout.addWidget(card_label)

    card_panel = create_guidance_panel(
        test_questions,
        display_mode=GuidanceDisplayMode.CARD,
        on_click=lambda t: print(f"点击追问: {t}")
    )
    layout.addWidget(card_panel)

    # 测试内联模式
    inline_label = QLabel("内联模式：")
    inline_label.setStyleSheet("color: white; font-size: 14px;")
    layout.addWidget(inline_label)

    inline_panel = create_guidance_panel(
        test_questions,
        display_mode=GuidanceDisplayMode.INLINE,
        on_click=lambda t: print(f"点击追问: {t}")
    )
    layout.addWidget(inline_panel)

    layout.addStretch()

    window.show()
    sys.exit(app.exec())
