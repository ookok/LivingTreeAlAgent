"""
林冠警报带 (Canopy Alert Band)
位置：主界面顶部（状态栏下方），横贯全宽
场景：升级警告、网络断开、高风险操作预警
视觉：背景色温（黄/红）+ 左侧图标 + 消息正文 + 右侧操作按钮
优点：自动化脚本可通过 ID canopy-alert 稳定定位，无需应对随机弹窗

🌿 生命之树风格 · 无弹窗组件库 #1
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QSize, QParallelAnimationGroup
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect
)
from PyQt6.QtGui import QIcon, QColor


class CanopyAlertBand(QWidget):
    """
    林冠警报带 — 全局提醒组件

    使用方式:
        # 显示警告
        self.canopy_alert.show_alert(
            message="新版本已就绪，建议重启以应用更新。",
            level="info",  # info/warning/error
            actions=[("查看更新", lambda: ...), ("忽略", lambda: ...)]
        )

        # 隐藏
        self.canopy_alert.hide()
    """

    # 信号
    action_clicked = pyqtSignal(str)  # 发出动作ID
    dismissed = pyqtSignal()

    # 警报级别
    LEVEL_STYLES = {
        "info": {
            "bg": "#1a3a5c",      # 深蓝
            "border": "#3b82f6",  # 蓝色边框
            "icon": "🌿",
            "icon_color": "#60a5fa"
        },
        "warning": {
            "bg": "#3d2e0a",      # 深琥珀
            "border": "#f59e0b",  # 琥珀色边框
            "icon": "⚠️",
            "icon_color": "#fbbf24"
        },
        "error": {
            "bg": "#3d1a1a",      # 深红
            "border": "#ef4444", # 红色边框
            "icon": "🚨",
            "icon_color": "#f87171"
        },
        "success": {
            "bg": "#1a3d2e",      # 深绿
            "border": "#22c55e", # 绿色边框
            "icon": "✅",
            "icon_color": "#4ade80"
        }
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canopy-alert-band")  # 自动化锚点
        self._actions = {}
        self._auto_hide_timer = None
        self._setup_ui()
        self._setup_animations()

    def _setup_ui(self):
        """初始化UI"""
        self.setFixedHeight(0)  # 初始隐藏
        self.setMaximumHeight(60)

        # 主布局
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(12)

        # 左侧图标
        self._icon = QLabel("🌿")
        self._icon.setObjectName("canopy-alert-icon")
        self._icon.setFixedWidth(28)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 消息文本
        self._message = QLabel()
        self._message.setObjectName("canopy-alert-message")
        self._message.setWordWrap(False)
        self._message.setStyleSheet("color: #e8e8e8; font-size: 13px;")

        # 右侧操作按钮区域
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(8)
        self._actions_layout.addStretch()

        # 关闭按钮
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("canopy-alert-close")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_dismiss)
        self._close_btn.setToolTip("关闭")

        self._layout.addWidget(self._icon)
        self._layout.addWidget(self._message, 1)  # stretch
        self._layout.addLayout(self._actions_layout)
        self._layout.addWidget(self._close_btn)

        # 初始应用样式
        self._apply_level_style("info")

    def _setup_animations(self):
        """设置动画"""
        self._height_animation = QPropertyAnimation(self, b"maximumHeight")
        self._height_animation.setDuration(300)
        self._height_animation.setEasingCurve(QPropertyAnimation.EasingCurve.Type.OutCubic)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._opacity_animation.setDuration(300)

    def _apply_level_style(self, level: str):
        """应用级别样式"""
        style = self.LEVEL_STYLES.get(level, self.LEVEL_STYLES["info"])
        self.setStyleSheet(f"""
            #canopy-alert-band {{
                background-color: {style['bg']};
                border-bottom: 2px solid {style['border']};
            }}
            #canopy-alert-icon {{
                color: {style['icon_color']};
                font-size: 18px;
            }}
        """)
        self._icon.setText(style["icon"])

    def _on_dismiss(self):
        """关闭警报"""
        self.hide_alert()
        self.dismissed.emit()

    def show_alert(
        self,
        message: str,
        level: str = "info",
        actions: list = None,
        auto_hide_ms: int = 0
    ):
        """
        显示警报

        Args:
            message: 警报消息
            level: 级别 info/warning/error/success
            actions: 操作按钮列表 [(文本, 回调函数), ...]
            auto_hide_ms: 自动隐藏时间(毫秒)，0表示不自动隐藏
        """
        # 清除旧按钮
        while self._actions_layout.count() > 1:
            item = self._actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新按钮
        self._actions.clear()
        if actions:
            for text, callback in actions:
                btn = QPushButton(text)
                btn.setObjectName(f"canopy-action-{text}")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255,255,255,0.15);
                        color: #e8e8e8;
                        border: 1px solid rgba(255,255,255,0.3);
                        border-radius: 4px;
                        padding: 4px 12px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255,255,255,0.25);
                    }
                """)
                action_id = text
                self._actions[action_id] = callback
                btn.clicked.connect(lambda checked, aid=action_id: self._on_action(aid))
                self._actions_layout.insertWidget(0, btn)

        # 设置消息和样式
        self._message.setText(message)
        self._apply_level_style(level)

        # 动画显示
        self._animate_show()

        # 自动隐藏
        if auto_hide_ms > 0:
            if self._auto_hide_timer:
                self._auto_hide_timer.stop()
            self._auto_hide_timer = QTimer.singleShot(auto_hide_ms, self.hide_alert)

    def _on_action(self, action_id: str):
        """处理动作点击"""
        if action_id in self._actions:
            callback = self._actions[action_id]
            if callback:
                callback()
            self.action_clicked.emit(action_id)
            self.hide_alert()

    def _animate_show(self):
        """显示动画"""
        self.show()
        self._height_animation.stop()
        self._height_animation.setStartValue(0)
        self._height_animation.setEndValue(60)
        self._height_animation.start()

    def hide_alert(self):
        """隐藏警报（带动画）"""
        self._height_animation.stop()
        self._height_animation.setStartValue(60)
        self._height_animation.setEndValue(0)
        self._height_animation.finished.connect(self._on_hide_finished)
        self._height_animation.start()

    def _on_hide_finished(self):
        """隐藏动画完成"""
        if self.maximumHeight() == 0:
            self.hide()
        self._height_animation.finished.disconnect(self._on_hide_finished)

    def is_visible_alert(self) -> bool:
        """检查警报是否正在显示"""
        return self.isVisible() and self.maximumHeight() > 0

    # ========== 便捷静态方法 ==========

    @staticmethod
    def create_for_parent(parent) -> 'CanopyAlertBand':
        """为父窗口创建警报带"""
        alert = CanopyAlertBand(parent)
        return alert


# ========== 自动化测试辅助 ==========

def get_alert_band(window) -> CanopyAlertBand:
    """通过 ObjectName 获取警报带（用于自动化测试）"""
    return window.findChild(QWidget, "canopy-alert-band")


def assert_alert_visible(window, timeout_ms: int = 1000) -> bool:
    """断言警报可见（用于测试）"""
    import time
    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        alert = get_alert_band(window)
        if alert and alert.is_visible_alert():
            return True
    return False
