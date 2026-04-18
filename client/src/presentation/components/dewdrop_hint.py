"""
晨露提示卡 (Dewdrop Hint Card)
位置：附着在相关控件旁（如输入框下方、按钮右侧），非阻塞
场景：表单校验、AI 建议、操作后果说明
行为：3-5 秒渐隐或手动关闭，不要求立即响应
优点：无焦点抢夺，测试可捕获 tooltip-text 属性

🌿 生命之树风格 · 无弹窗组件库 #4
"""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QSize, pyqtSignal, QRect
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QApplication
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen


class DewdropHintCard(QFrame):
    """
    晨露提示卡 — 上下文提示组件

    使用方式:
        # 在控件下方显示提示
        hint = DewdropHintCard.show_below(
            target=input_field,
            message="输入格式：2024-01-01",
            level="info"  # info/warning/error
        )

        # 右侧显示
        hint = DewdropHintCard.show_right_of(
            target=submit_btn,
            message="提交后将发送邮件通知",
            level="info"
        )

        # 自动3秒后消失
        hint.auto_hide(3000)
    """

    # 信号
    dismissed = pyqtSignal()
    action_clicked = pyqtSignal(str)  # 动作ID

    # 提示级别
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"
    LEVEL_SUCCESS = "success"

    # 级别样式
    LEVEL_STYLES = {
        LEVEL_INFO: {
            "bg": "#1e3a5f",
            "border": "#3b82f6",
            "icon": "💡",
            "text_color": "#e0e0e0"
        },
        LEVEL_WARNING: {
            "bg": "#3d2e0a",
            "border": "#f59e0b",
            "icon": "⚠️",
            "text_color": "#e8e8e8"
        },
        LEVEL_ERROR: {
            "bg": "#3d1a1a",
            "border": "#ef4444",
            "icon": "❌",
            "text_color": "#f0f0f0"
        },
        LEVEL_SUCCESS: {
            "bg": "#1a3d2a",
            "border": "#22c55e",
            "icon": "✅",
            "text_color": "#e0e0e0"
        }
    }

    _instances = []  # 跟踪所有实例

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dewdrop-hint")  # 自动化锚点
        self._target_widget = None
        self._anchor_position = "bottom"  # bottom/right/left/top
        self._level = self.LEVEL_INFO
        self._actions = {}
        self._fade_timer = None
        self._is_auto_hide_enabled = True

        DewdropHintCard._instances.append(self)

        self._setup_ui()
        self._setup_animations()

    def __del__(self):
        """析构时移除实例"""
        if self in DewdropHintCard._instances:
            DewdropHintCard._instances.remove(self)

    def _setup_ui(self):
        """初始化UI"""
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(36)
        self.setMinimumWidth(120)
        self.setMaximumWidth(320)

        # 主布局
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 6, 6)
        self._layout.setSpacing(8)

        # 图标
        self._icon = QLabel("💡")
        self._icon.setObjectName("hint-icon")
        self._icon.setFixedWidth(16)

        # 消息文本
        self._message = QLabel()
        self._message.setObjectName("hint-message")
        self._message.setWordWrap(False)

        # 关闭按钮
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("hint-close")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_dismiss)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255,255,255,0.5);
                border: none;
                font-size: 10px;
            }
            QPushButton:hover {
                color: rgba(255,255,255,0.8);
            }
        """)

        self._layout.addWidget(self._icon)
        self._layout.addWidget(self._message, 1)
        self._layout.addWidget(self._close_btn)

        # 默认样式
        self._apply_level_style(self.LEVEL_INFO)

    def _setup_animations(self):
        """设置动画"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)

        self._slide_animation = QPropertyAnimation(self, b"geometry")
        self._slide_animation.setDuration(200)

    def _apply_level_style(self, level: str):
        """应用级别样式"""
        style = self.LEVEL_STYLES.get(level, self.LEVEL_STYLES[self.LEVEL_INFO])
        self._level = level

        self.setStyleSheet(f"""
            #dewdrop-hint {{
                background-color: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: 6px;
            }}
            #hint-icon {{
                color: {style['border']};
                font-size: 12px;
            }}
            #hint-message {{
                color: {style['text_color']};
                font-size: 12px;
            }}
        """)
        self._icon.setText(style["icon"])

    def _calculate_position(self) -> QPoint:
        """计算相对于目标控件的位置"""
        if not self._target_widget:
            return QPoint(0, 0)

        target = self._target_widget
        parent = target.parent()

        if self._anchor_position == "bottom":
            # 在控件下方
            pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(0, target.height()))
            pos += QPoint(0, 8)
        elif self._anchor_position == "right":
            # 在控件右侧
            pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(target.width(), 0))
            pos += QPoint(8, 0)
        elif self._anchor_position == "top":
            # 在控件上方
            pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(0, 0))
            pos -= QPoint(0, self.height() + 8)
        else:  # left
            pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(0, 0))
            pos -= QPoint(self.width() + 8, 0)

        return pos

    def _animate_show(self):
        """显示动画"""
        self.show()

        # 滑入
        start_geom = self.geometry()
        start_geom.translate(0, 10)
        self._slide_animation.stop()
        self._slide_animation.setStartValue(start_geom)
        self._slide_animation.setEndValue(self.geometry())
        self._slide_animation.start()

        # 淡入
        self._fade_animation.stop()
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def _animate_hide(self, callback=None):
        """隐藏动画"""
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self._opacity_effect.opacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(lambda: self._on_hide_finished(callback))
        self._fade_animation.start()

    def _on_hide_finished(self, callback=None):
        """隐藏动画完成"""
        self.hide()
        if callback:
            callback()
        self.dismissed.emit()
        self.deleteLater()

    def _on_dismiss(self):
        """手动关闭"""
        if self._fade_timer and self._fade_timer.isActive():
            self._fade_timer.stop()
        self._animate_hide()

    # ========== 公共接口 ==========

    def set_message(self, message: str):
        """设置消息"""
        self._message.setText(message)

    def set_level(self, level: str):
        """设置级别"""
        self._apply_level_style(level)

    def set_actions(self, actions: list):
        """
        设置操作按钮

        Args:
            actions: [(action_id, text, callback), ...]
        """
        # 清除旧按钮
        while self._layout.count() > 3:  # icon, message, close
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._actions.clear()

        for action_id, text, callback in actions:
            btn = QPushButton(text)
            btn.setObjectName(f"hint-action-{action_id}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.15);
                    color: #e8e8e8;
                    border: 1px solid rgba(255,255,255,0.3);
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.25);
                }
            """)
            self._actions[action_id] = callback
            btn.clicked.connect(lambda checked, aid=action_id: self._on_action(aid))
            self._layout.insertWidget(self._layout.count() - 1, btn)  # before close btn

    def _on_action(self, action_id: str):
        """动作点击"""
        if action_id in self._actions:
            callback = self._actions[action_id]
            if callback:
                callback()
            self.action_clicked.emit(action_id)
        self._animate_hide()

    def auto_hide(self, delay_ms: int = 3000):
        """
        设置自动隐藏

        Args:
            delay_ms: 延迟毫秒数
        """
        if self._fade_timer:
            self._fade_timer.stop()
        else:
            self._fade_timer = QTimer(self)
            self._fade_timer.timeout.connect(self._animate_hide)

        self._fade_timer.setSingleShot(True)
        self._fade_timer.start(delay_ms)
        return self

    def show_below(target: QWidget, message: str, level: str = None, parent: QWidget = None) -> 'DewdropHintCard':
        """
        在目标控件下方显示提示

        Args:
            target: 锚定控件
            message: 提示消息
            level: info/warning/error/success
            parent: 父窗口（可选）

        Returns:
            DewdropHintCard 实例
        """
        hint = DewdropHintCard(parent or target.window())
        hint._target_widget = target
        hint._anchor_position = "bottom"
        hint._message.setText(message)

        if level:
            hint._apply_level_style(level)

        # 计算位置
        hint.adjustSize()
        target_pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(0, target.height()))
        hint.move(target_pos + QPoint(0, 8))

        hint._animate_show()
        return hint

    def show_right_of(target: QWidget, message: str, level: str = None, parent: QWidget = None) -> 'DewdropHintCard':
        """
        在目标控件右侧显示提示

        Args:
            target: 锚定控件
            message: 提示消息
            level: info/warning/error/success
            parent: 父窗口（可选）

        Returns:
            DewdropHintCard 实例
        """
        hint = DewdropHintCard(parent or target.window())
        hint._target_widget = target
        hint._anchor_position = "right"
        hint._message.setText(message)

        if level:
            hint._apply_level_style(level)

        # 计算位置
        hint.adjustSize()
        target_pos = target.mapTo(parent or QApplication.instance().activeWindow(), QPoint(target.width(), 0))
        hint.move(target_pos + QPoint(8, 0))

        hint._animate_show()
        return hint

    @classmethod
    def dismiss_all(cls):
        """关闭所有提示卡"""
        for instance in cls._instances[:]:
            instance._animate_hide()
        cls._instances.clear()


# ========== 便捷函数 ==========

def show_hint_below(target: QWidget, message: str, level: str = DewdropHintCard.LEVEL_INFO) -> DewdropHintCard:
    """在控件下方显示提示"""
    return DewdropHintCard.show_below(target, message, level)


def show_hint_right(target: QWidget, message: str, level: str = DewdropHintCard.LEVEL_INFO) -> DewdropHintCard:
    """在控件右侧显示提示"""
    return DewdropHintCard.show_right_of(target, message, level)


# ========== 自动化测试辅助 ==========

def get_all_hints() -> list:
    """获取所有提示卡实例"""
    return DewdropHintCard._instances.copy()


def get_visible_hints() -> list:
    """获取所有可见的提示卡"""
    return [h for h in DewdropHintCard._instances if h.isVisible()]


def find_hint_by_message(partial_message: str) -> DewdropHintCard:
    """根据消息内容查找提示卡"""
    for hint in DewdropHintCard._instances:
        if partial_message in hint._message.text():
            return hint
    return None
