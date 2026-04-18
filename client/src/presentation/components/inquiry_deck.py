"""
根系询问台 (Root Inquiry Deck)
位置：右侧边栏（固定宽度 320px），平时收起，需要时滑出
场景：装配冲突裁决、补丁应用确认、交易风险提示
结构：标题 + 描述 + 选项按钮组（水平排列，非模态）
优点：控件树稳定，测试脚本可断言 inquiry-deck:visible 状态

🌿 生命之树风格 · 无弹窗组件库 #2
"""

from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, pyqtSignal, QRect
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup,
    QScrollArea, QFrame
)
from PyQt6.QtGui import QColor, QPalette


class RootInquiryDeck(QWidget):
    """
    根系询问台 — 用户确认组件

    使用方式:
        # 显示冲突确认
        self.inquiry_deck.ask_conflict_resolve(
            tool_new="PDFExtractor",
            tool_old="DocParser",
            options=[
                ("分叉共生", "parallel", lambda: ...),
                ("修剪旧枝", "replace", lambda: ...),
                ("取消", "cancel", None)
            ],
            on_confirm=lambda choice: ...
        )

        # 隐藏
        self.inquiry_deck.hide_deck()
    """

    # 信号
    confirmed = pyqtSignal(str, str)  # (choice_id, choice_text)
    cancelled = pyqtSignal()
    option_selected = pyqtSignal(str, str)  # (option_id, option_text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root-inquiry-deck")  # 自动化锚点
        self.setFixedWidth(320)
        self._current_callback = None
        self._options = {}
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        """初始化UI"""
        # 主容器
        self._container = QFrame(self)
        self._container.setObjectName("inquiry-container")
        self._container.setFrameShape(QFrame.Shape.NoFrame)

        # 布局
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._container)

        # 内容布局
        self._content_layout = QVBoxLayout(self._container)
        self._content_layout.setContentsMargins(16, 16, 16, 16)
        self._content_layout.setSpacing(16)

        # 标题区
        self._header = QHBoxLayout()
        self._header.setSpacing(10)

        self._icon = QLabel("🌱")
        self._icon.setObjectName("inquiry-icon")
        self._icon.setFixedWidth(32)

        self._title = QLabel("根系询问")
        self._title.setObjectName("inquiry-title")
        self._title.setStyleSheet("color: #e8e8e8; font-size: 15px; font-weight: 600;")

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("inquiry-close")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_cancel)

        self._header.addWidget(self._icon)
        self._header.addWidget(self._title, 1)
        self._header.addWidget(self._close_btn)

        # 描述区
        self._desc = QLabel()
        self._desc.setObjectName("inquiry-description")
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color: #a0a0a0; font-size: 13px; line-height: 1.5;")
        self._desc.setText("请确认您的选择：")

        # 选项区
        self._options_group = QButtonGroup()
        self._options_group.setExclusive(True)
        self._options_group.buttonClicked.connect(self._on_option_clicked)

        self._options_layout = QVBoxLayout()
        self._options_layout.setSpacing(8)

        # 确认按钮
        self._confirm_btn = QPushButton("确认选择")
        self._confirm_btn.setObjectName("inquiry-confirm")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.clicked.connect(self._on_confirm)
        self._confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:disabled {
                background-color: #2a3a4a;
                color: #606060;
            }
        """)

        # 取消按钮
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("inquiry-cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1e1e1e;
                color: #cccccc;
            }
        """)

        # 按钮行
        self._btn_row = QHBoxLayout()
        self._btn_row.addStretch()
        self._btn_row.addWidget(self._cancel_btn)
        self._btn_row.addWidget(self._confirm_btn)

        # 组装
        self._content_layout.addLayout(self._header)
        self._content_layout.addWidget(self._desc)
        self._content_layout.addLayout(self._options_layout)
        self._content_layout.addStretch()
        self._content_layout.addLayout(self._btn_row)

        # 应用样式
        self.setStyleSheet("""
            #root-inquiry-deck {
                background-color: #1a1a1a;
                border-left: 1px solid #2a2a2a;
            }
            #inquiry-container {
                background-color: transparent;
            }
        """)

        # 初始隐藏
        self.hide()

    def _setup_animation(self):
        """设置滑入动画"""
        self._slide_animation = QPropertyAnimation(self, b"geometry")
        self._slide_animation.setDuration(250)
        self._slide_animation.setEasingCurve(QPropertyAnimation.EasingCurve.Type.OutCubic)

    def _clear_options(self):
        """清除选项"""
        while self._options_layout.count():
            item = self._options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._options_group.buttons().clear()
        self._options.clear()
        self._confirm_btn.setEnabled(False)
        self._current_callback = None

    def _on_option_clicked(self, btn: QRadioButton):
        """选项被点击"""
        self._confirm_btn.setEnabled(True)
        for opt_id, (radio, text) in self._options.items():
            if radio is btn:
                self.option_selected.emit(opt_id, text)
                break

    def _on_confirm(self):
        """确认选择"""
        checked = self._options_group.checkedButton()
        if checked:
            for opt_id, (radio, text) in self._options.items():
                if radio is checked:
                    self.confirmed.emit(opt_id, text)
                    if self._current_callback:
                        self._current_callback(opt_id)
                    self._animate_hide()
                    break

    def _on_cancel(self):
        """取消"""
        self.cancelled.emit()
        self._animate_hide()

    def _animate_show(self):
        """滑入动画"""
        parent = self.parent()
        if parent:
            start_rect = QRect(parent.width(), 0, self.width(), parent.height())
            end_rect = QRect(parent.width() - self.width(), 0, self.width(), parent.height())

            self._slide_animation.stop()
            self._slide_animation.setStartValue(start_rect)
            self._slide_animation.setEndValue(end_rect)
            self._slide_animation.start()

        self.show()

    def _animate_hide(self):
        """滑出动画"""
        parent = self.parent()
        if parent:
            start_rect = self.geometry()
            end_rect = QRect(parent.width(), start_rect.y(), self.width(), parent.height())

            self._slide_animation.stop()
            self._slide_animation.setStartValue(start_rect)
            self._slide_animation.setEndValue(end_rect)
            self._slide_animation.finished.connect(self._on_hide_finished)
            self._slide_animation.start()
        else:
            self.hide()

    def _on_hide_finished(self):
        """隐藏动画完成"""
        self.hide()
        self._slide_animation.finished.disconnect(self._on_hide_finished)
        self._clear_options()

    # ========== 公共接口 ==========

    def show_deck(self):
        """显示询问台（滑入）"""
        self._animate_show()

    def hide_deck(self):
        """隐藏询问台（滑出）"""
        self._animate_hide()

    def ask(
        self,
        title: str = "根系询问",
        description: str = "请确认您的选择：",
        icon: str = "🌱",
        options: list = None,
        on_confirm=None,
        on_cancel=None
    ):
        """
        显示询问

        Args:
            title: 标题
            description: 描述文本
            icon: 图标 emoji
            options: 选项列表 [(id, 文本, 回调), ...]
            on_confirm: 确认回调 (choice_id)
            on_cancel: 取消回调
        """
        self._clear_options()

        # 设置内容
        self._title.setText(title)
        self._desc.setText(description)
        self._icon.setText(icon)
        self._current_callback = on_confirm

        if on_cancel:
            self.cancelled.connect(on_cancel)

        # 添加选项
        if options:
            for opt_id, text, callback in options:
                radio = QRadioButton(text)
                radio.setObjectName(f"inquiry-option-{opt_id}")
                radio.setCursor(Qt.CursorShape.PointingHandCursor)
                radio.setStyleSheet("""
                    QRadioButton {
                        color: #d0d0d0;
                        font-size: 13px;
                        padding: 8px 12px;
                        background-color: #151515;
                        border: 1px solid #2a2a2a;
                        border-radius: 6px;
                        margin: 2px 0;
                    }
                    QRadioButton:hover {
                        background-color: #1e1e1e;
                        border-color: #3a3a3a;
                    }
                    QRadioButton::indicator {
                        width: 16px;
                        height: 16px;
                        margin-right: 8px;
                    }
                    QRadioButton::indicator::checked {
                        background-color: #3b82f6;
                    }
                """)
                self._options_group.addButton(radio)
                self._options_layout.addWidget(radio)
                self._options[opt_id] = (radio, text)

        self.show_deck()

    def ask_conflict_resolve(self, tool_new: str, tool_old: str, options: list, on_confirm=None):
        """
        显示冲突解决询问

        Args:
            tool_new: 新工具名称
            tool_old: 旧工具名称
            options: [(id, text, callback), ...]
            on_confirm: 确认回调
        """
        desc = f"新工具「{tool_new}」与「{tool_old}」功能重叠，请选择处理方式："
        self.ask(
            title="🌱 根系相容提示",
            description=desc,
            icon="⚠️",
            options=options,
            on_confirm=on_confirm
        )

    def ask_risk_confirm(self, action: str, risk_level: str = "medium", on_confirm=None):
        """
        显示风险确认询问

        Args:
            action: 操作描述
            risk_level: 风险等级 low/medium/high
            on_confirm: 确认回调
        """
        icons = {"low": "💡", "medium": "⚠️", "high": "🚨"}
        titles = {"low": "操作确认", "medium": "风险提示", "high": "高危警告"}
        icon = icons.get(risk_level, "⚠️")
        title = titles.get(risk_level, "确认")

        self.ask(
            title=f"{icon} {title}",
            description=action,
            icon=icon,
            options=[
                ("confirm", "确认执行", None),
                ("cancel", "取消", None)
            ],
            on_confirm=on_confirm
        )

    def is_visible_deck(self) -> bool:
        """检查询问台是否正在显示"""
        return self.isVisible()


# ========== 自动化测试辅助 ==========

def get_inquiry_deck(window) -> RootInquiryDeck:
    """通过 ObjectName 获取询问台（用于自动化测试）"""
    return window.findChild(QWidget, "root-inquiry-deck")


def get_visible_inquiry_deck(window) -> RootInquiryDeck:
    """获取当前可见的询问台"""
    deck = get_inquiry_deck(window)
    if deck and deck.is_visible_deck():
        return deck
    return None


def select_inquiry_option(window, option_id: str) -> bool:
    """
    选择询问台选项（用于自动化测试）

    Returns:
        True if option found and selected
    """
    deck = get_visible_inquiry_deck(window)
    if not deck:
        return False

    radio = deck.findChild(QRadioButton, f"inquiry-option-{option_id}")
    if radio:
        radio.setChecked(True)
        return True
    return False
