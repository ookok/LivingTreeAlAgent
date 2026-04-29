"""
智能提示系统 — 空气UI (全局交互版)
===================================
操作系统级智能伴侣，独立置顶 + 右键三级菜单

特性：
- 全局置顶 QWidget（穿透所有 Dialog）
- 右键点击 → 三级交互菜单
- 呼吸闪烁动画
- 集成 handbook 本地匹配
- 集成 MemPalace 记忆
"""

import threading
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QMenu, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QAction, QCursor

from .models import GeneratedHint, HintLevel, HintConfig, ContextInfo
from .global_signals import HintSignal, HintSignalType, get_signal_bus
from .handbook_matcher import get_handbook_matcher, get_handbook_loader
from .polisher import get_polisher, get_hermes_polisher
from .hint_memory import get_hint_memory


class GlobalAirIcon(QWidget):
    """
    全局空气图标 — 独立置顶 + 右键三级菜单

    状态：
    - 🌿 呼吸闪烁 = 有温馨建议
    - 🌿 常亮 = 正常待命
    - 🌿 灰暗 = 用户选择隐藏
    """

    # 信号
    clicked = pyqtSignal()                              # 左键点击
    menu_signal = pyqtSignal(str, str)                  # (interaction, scene_id)

    COLORS = {
        HintLevel.TRANSPARENT: "#81C784",
        HintLevel.GLOW: "#81C784",       # 淡绿闪烁
        HintLevel.GENTLE: "#4CAF50",     # 正常绿
        HintLevel.IMPORTANT: "#FF9800",  # 橙色
        HintLevel.URGENT: "#F44336",     # 红色
    }

    def __init__(self, config: HintConfig = None, scene_id: str = "global"):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.config = config or HintConfig()
        self.scene_id = scene_id

        # 状态
        self._is_hovered = False
        self._is_hidden = False
        self._current_level = HintLevel.TRANSPARENT
        self._has_hint = False

        # 子系统
        self._memory = get_hint_memory()
        self._polisher = get_polisher()
        self._hermes = get_hermes_polisher()

        self._setup_ui()
        self._setup_animations()
        self._setup_context_menu()

        # 检查是否被隐藏
        self._check_hidden_state()

    def _setup_ui(self):
        """设置UI"""
        self.setFixedSize(44, 44)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 位置：主窗口右上角内侧（延迟设置）
        QTimer.singleShot(100, self._move_to_corner)

        # 透明度
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.6 if not self._has_hint else 0.8)
        self.setGraphicsEffect(self._opacity)

        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # 检查隐藏状态
        if self._memory.is_hidden(self.scene_id):
            self._is_hidden = True
            self._opacity.setOpacity(0.3)

    def _setup_animations(self):
        """设置动画"""
        # 呼吸动画
        self._breath_anim = QPropertyAnimation(self._opacity, b"opacity")
        self._breath_anim.setDuration(2000)
        self._breath_anim.setKeyValueAt(0, 0.4)
        self._breath_anim.setKeyValueAt(0.5, 1.0)
        self._breath_anim.setKeyValueAt(1, 0.4)
        self._breath_anim.setLoopCount(-1)

        # 悬停动画
        self._hover_anim = QPropertyAnimation(self._opacity, b"opacity")
        self._hover_anim.setDuration(150)

    def _setup_context_menu(self):
        """设置右键菜单"""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos: QPoint):
        """显示右键菜单"""
        menu = QMenu(self)

        # 获取当前场景的 handbook
        from .handbook_matcher import get_handbook_matcher
        matcher = get_handbook_matcher()
        chat_intro = matcher.get_chat_intro(self.scene_id)

        # 三个选项
        # 🙈 暂时隐藏
        action_hide = QAction("🙈 暂时隐藏", self)
        action_hide.setToolTip("本次会话停止闪烁")
        action_hide.triggered.connect(lambda: self._on_hide("temp"))

        # 🚫 永久隐藏
        action_perma = QAction("🚫 别在这儿烦我", self)
        action_perma.setToolTip("此场景永不再提示")
        action_perma.triggered.connect(lambda: self._on_hide("perma"))

        # 💬 和它聊聊
        action_chat = QAction(f"💬 和它聊聊", self)
        action_chat.setToolTip("想问点什么")
        action_chat.triggered.connect(lambda: self._on_chat())

        menu.addAction(action_hide)
        menu.addAction(action_perma)
        menu.addSeparator()
        menu.addAction(action_chat)

        # 如果有预设问题，显示它们
        questions = matcher.get_chat_questions(self.scene_id)
        if questions:
            menu.addSeparator()
            submenu = QMenu("💡 常见问题", self)
            for q in questions[:3]:
                action_q = QAction(q, self)
                action_q.triggered.connect(lambda checked, qq=q: self._on_question(qq))
                submenu.addAction(action_q)
            menu.addMenu(submenu)

        menu.exec(QCursor.pos())

    def _on_hide(self, hide_type: str):
        """处理隐藏"""
        matcher = get_handbook_matcher()
        hide_msg = matcher.get_hide_message(self.scene_id, hide_type)

        self._memory.hide_scene(
            self.scene_id,
            hide_type=hide_type,
            remember=(hide_type == "perma")
        )

        if hide_type == "perma":
            self._is_hidden = True
            self._opacity.setOpacity(0.3)
            self._breath_anim.stop()

        # 发送信号
        signal_bus = get_signal_bus()
        signal_bus.emit_simple(
            HintSignalType.HIDE_THIS_SCENE,
            self.scene_id,
            payload={"hide_type": hide_type, "message": hide_msg}
        )

    def _on_chat(self):
        """处理聊天"""
        signal_bus = get_signal_bus()
        signal_bus.emit_simple(
            HintSignalType.SHOW_CHAT_WINDOW,
            self.scene_id,
            payload={"mode": "chat"}
        )

    def _on_question(self, question: str):
        """处理预设问题"""
        # 发送聊天信号
        signal_bus = get_signal_bus()
        signal_bus.emit_simple(
            HintSignalType.HINT_CHAT,
            self.scene_id,
            payload={"mode": "question", "question": question}
        )

    def _move_to_corner(self):
        """移动到角落"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            # 右上角内侧
            x = screen_geo.width() - self.width() - 100
            y = 60  # 避开任务栏
            self.move(x, y)

    def _check_hidden_state(self):
        """检查隐藏状态"""
        if self._memory.is_hidden(self.scene_id):
            self._is_hidden = True
            self._opacity.setOpacity(0.3)
            self._breath_anim.stop()

    # ── 状态更新 ────────────────────────────────────────────

    def set_hint(self, has_hint: bool, level: HintLevel = HintLevel.GLOW):
        """设置提示状态"""
        self._has_hint = has_hint
        self._current_level = level

        if self._is_hidden:
            return

        if has_hint:
            # 启动呼吸动画
            if not self._breath_anim.state():
                self._breath_anim.start()
        else:
            # 停止动画
            self._breath_anim.stop()
            self._opacity.setOpacity(0.7)

    def show_hint(self, hint: GeneratedHint):
        """显示提示"""
        if self._memory.is_hidden(self.scene_id):
            return

        # 更新状态
        self._has_hint = True
        self._current_level = hint.hint_level

        # 发送信号
        signal_bus = get_signal_bus()
        signal_bus.emit_simple(
            HintSignalType.HINT_TRIGGER,
            self.scene_id,
            payload={
                "hint_id": hint.hint_id,
                "content": hint.content,
                "emoji": hint.emoji,
                "level": hint.hint_level.value
            }
        )

    def set_visible(self, visible: bool):
        """设置可见性"""
        super().setVisible(visible)

    # ── 绘制 ────────────────────────────────────────────────

    def paintEvent(self, event):
        """绘制图标"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取颜色
        color_str = self.COLORS.get(self._current_level, "#4CAF50")
        color = QColor(color_str)

        # 根据状态调整
        if self._is_hidden:
            color = QColor("#9E9E9E")  # 灰色
            color.setAlpha(150)
        elif self._is_hovered:
            color.setAlpha(255)
        else:
            color.setAlpha(200)

        # 绘制圆形背景
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))

        # 绘制叶子
        font = QFont("")
        font.setPointSize(18)
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🌿")

    def enterEvent(self, event):
        """鼠标进入"""
        self._is_hovered = True
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._opacity.opacity())
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._opacity.opacity())
        self._hover_anim.setEndValue(0.7)
        self._hover_anim.start()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_context_menu(event.pos())
        super().mousePressEvent(event)


class HintCardWidget(QWidget):
    """提示卡片"""

    dismissed = pyqtSignal(str)
    actioned = pyqtSignal(str, str)

    COLORS = {
        HintLevel.TRANSPARENT: ("#E8F5E9", "#4CAF50"),
        HintLevel.GLOW: ("#C8E6C9", "#81C784"),
        HintLevel.GENTLE: ("#A5D6A7", "#4CAF50"),
        HintLevel.IMPORTANT: ("#FFE0B2", "#FF9800"),
        HintLevel.URGENT: ("#FFCDD2", "#F44336"),
    }

    def __init__(self, hint: GeneratedHint, config: HintConfig = None):
        super().__init__()
        self.hint = hint
        self.config = config or HintConfig()
        self._setup_ui()

    def _setup_ui(self):
        bg, border = self.COLORS.get(
            self.hint.hint_level,
            ("#E8F5E9", "#4CAF50")
        )

        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(4)

        # 头部
        header = QHBoxLayout()
        header.setSpacing(6)

        emoji = QLabel(self.hint.emoji)
        emoji.setFont(QFont("", 16))
        header.addWidget(emoji)

        if self.hint.title:
            title = QLabel(self.hint.title)
            title.setFont(QFont("", 9, QFont.Weight.Bold))
            header.addWidget(title)

        header.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 14px;
            }
            QPushButton:hover { color: #333; }
        """)
        close_btn.clicked.connect(lambda: self.dismissed.emit(self.hint.hint_id))
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 内容
        content = QLabel(self.hint.content)
        content.setWordWrap(True)
        content.setFont(QFont("", 10))
        content.setStyleSheet("color: #333; background: transparent; border: none;")
        layout.addWidget(content)

        # 自动隐藏
        if self.config.auto_hide_delay > 0:
            QTimer.singleShot(
                self.config.auto_hide_delay,
                lambda: self.dismissed.emit(self.hint.hint_id)
            )


class ChatWindow(QWidget):
    """
    悬浮聊天小窗

    用于"和它聊聊"场景
    """

    closed = pyqtSignal()

    def __init__(self, scene_id: str, context: ContextInfo = None):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.scene_id = scene_id
        self.context = context
        self._hermes = get_hermes_polisher()
        self._matcher = get_handbook_matcher()

        self._setup_ui()
        self._load_intro()

    def _setup_ui(self):
        """设置UI"""
        self.setFixedSize(320, 240)
        self.setStyleSheet("""
            QWidget {
                background-color: #2E7D32;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # 标题栏
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)

        leaf = QLabel("🌿")
        leaf.setFont(QFont("", 14))
        title_bar.addWidget(leaf)

        title = QLabel("小叶子")
        title.setFont(QFont("", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title_bar.addWidget(title)

        title_bar.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                border: none;
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.3); }
        """)
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # 对话区域
        from PyQt6.QtWidgets import QScrollArea
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border-radius: 8px;
                border: none;
            }
        """)
        self.chat_content = QLabel()
        self.chat_content.setWordWrap(True)
        self.chat_content.setStyleSheet("background: transparent; border: none; padding: 8px;")
        self.chat_area.setWidget(self.chat_content)
        layout.addWidget(self.chat_area, 1)

        # 输入框
        from PyQt6.QtWidgets import QTextEdit
        self.input_box = QTextEdit()
        self.input_box.setMaximumHeight(50)
        self.input_box.setPlaceholderText("输入想说的话...")
        self.input_box.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border-radius: 6px;
                border: none;
                padding: 6px;
            }
        """)
        self.input_box.installEventFilter(self)
        layout.addWidget(self.input_box)

        # 发送按钮
        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        send_btn.clicked.connect(self._on_send)
        layout.addWidget(send_btn)

        # 位置：屏幕中央
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.geometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def _load_intro(self):
        """加载引导语"""
        intro = self._matcher.get_chat_intro(self.scene_id)
        self.add_message("bot", intro)

    def add_message(self, who: str, text: str):
        """添加消息"""
        current = self.chat_content.text()
        if current:
            current += "\n\n"
        if who == "bot":
            current += f"<span style='color: #4CAF50;'>🌿 {text}</span>"
        else:
            current += f"<span style='color: #333;'>你: {text}</span>"
        self.chat_content.setText(current)

        # 滚动到底部
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        )

    def _on_send(self):
        """发送消息"""
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        self.add_message("user", text)
        self.input_box.clear()

        # 获取回复
        response = self._hermes.chat(text, self.scene_id, self.context)
        self.add_message("bot", response)

    def eventFilter(self, obj, event):
        """监听回车键"""
        from PyQt6.QtCore import QEvent
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            from PyQt6.QtGui import QKeyEvent
            if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Return:
                self._on_send()
                return True
        return False

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


# ── 便捷函数 ──────────────────────────────────────────────

_air_icon_instance: Optional[GlobalAirIcon] = None
_chat_window_instance: Optional[ChatWindow] = None


def get_global_air_icon(config: HintConfig = None, scene_id: str = "global") -> GlobalAirIcon:
    """获取全局空气图标"""
    global _air_icon_instance
    if _air_icon_instance is None:
        _air_icon_instance = GlobalAirIcon(config, scene_id)
    return _air_icon_instance


def show_chat_window(scene_id: str, context: ContextInfo = None) -> ChatWindow:
    """显示聊天窗口"""
    global _chat_window_instance
    if _chat_window_instance:
        _chat_window_instance.close()
    _chat_window_instance = ChatWindow(scene_id, context)
    _chat_window_instance.show()
    return _chat_window_instance
