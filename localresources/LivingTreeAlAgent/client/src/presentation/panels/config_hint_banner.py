"""
配置提示横幅 - ConfigHintBanner

当 ChatPanel 检测到配置缺失错误时，显示可点击的提示横幅，
点击后跳转至设置页面的对应 Tab 进行配置。

使用示例：
    banner = ConfigHintBanner(parent=self)
    banner.show_config_hint(result)  # result 是 MissingConfigResult
    banner.config_clicked.connect(self._open_settings)
"""

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QApplication,
)
from PyQt6.QtGui import QDesktopServices, QCursor

from core.config_missing_detector import MissingConfigResult


class ConfigHintBanner(QFrame):
    """
    配置提示横幅

    信号：
        config_clicked(link_path: str) - 用户点击了配置链接
        dismissed() - 用户关闭了横幅
    """

    config_clicked = pyqtSignal(str)  # link_path
    dismissed = pyqtSignal()

    # Tab 名称到中文映射
    TAB_LABELS = {
        "providers": "Providers",
        "models": "Models",
        "agent": "Agent",
        "skills": "Skills",
        "general": "General",
        "ollama": "Ollama",
        "mcp": "MCP",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: MissingConfigResult | None = None
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("ConfigHintBanner")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(0)  # 隐藏状态
        self._hidden = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 主内容行
        content_row = QHBoxLayout()
        content_row.setSpacing(12)

        # 图标
        self.icon_lbl = QLabel("🔧")
        self.icon_lbl.setFixedWidth(28)
        content_row.addWidget(self.icon_lbl)

        # 提示信息
        self.msg_lbl = QLabel()
        self.msg_lbl.setObjectName("HintMessage")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setStyleSheet("color:#f59e0b; font-size:13px;")
        content_row.addWidget(self.msg_lbl, 1)

        # 配置按钮
        self.config_btn = QPushButton("配置")
        self.config_btn.setObjectName("ConfigButton")
        self.config_btn.setFixedWidth(80)
        self.config_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.config_btn.clicked.connect(self._on_config_clicked)
        content_row.addWidget(self.config_btn)

        # 关闭按钮
        self.dismiss_btn = QPushButton("×")
        self.dismiss_btn.setObjectName("DismissButton")
        self.dismiss_btn.setFixedWidth(28)
        self.dismiss_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.dismiss_btn.clicked.connect(self._on_dismiss)
        content_row.addWidget(self.dismiss_btn)

        layout.addLayout(content_row)

        # 建议操作（可选显示）
        self.suggest_lbl = QLabel()
        self.suggest_lbl.setObjectName("Suggestions")
        self.suggest_lbl.setWordWrap(True)
        self.suggest_lbl.setStyleSheet("color:#888; font-size:11px; padding-left:40px;")
        self.suggest_lbl.hide()
        layout.addWidget(self.suggest_lbl)

        # 设置样式
        self.setStyleSheet("""
            QFrame#ConfigHintBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    from #2d2015, to #1a1a1a);
                border: 1px solid #f59e0b;
                border-radius: 8px;
            }
            QPushButton#ConfigButton {
                background: #f59e0b;
                color: #1a1a1a;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#ConfigButton:hover {
                background: #fbbf24;
            }
            QPushButton#DismissButton {
                background: transparent;
                color: #888;
                border: none;
                font-size: 18px;
                font-weight: 300;
            }
            QPushButton#DismissButton:hover {
                color: #ef4444;
            }
        """)

    def show_config_hint(self, result: MissingConfigResult):
        """
        显示配置提示横幅

        Args:
            result: MissingConfigResult 检测结果
        """
        if not result.is_missing_config:
            return

        self._result = result

        # 更新消息
        tab_name = self.TAB_LABELS.get(result.link_path, result.link_path or "设置")
        self.msg_lbl.setText(
            f"<b>⚠️ 配置缺失：</b>{result.hint} "
            f'<span style="color:#888;">→ 跳转到 <a href="#{result.link_path}" '
            f'style="color:#60a5fa; text-decoration:none;">{tab_name}</a></span>'
        )

        # 更新按钮文本
        self.config_btn.setText(f"配置 {tab_name}")

        # 更新建议
        if result.suggestions:
            suggestions_text = " | ".join(result.suggestions[:3])
            self.suggest_lbl.setText(f"💡 {suggestions_text}")
            self.suggest_lbl.show()
        else:
            self.suggest_lbl.hide()

        # 显示横幅
        self._show()

    def _show(self):
        """显示横幅"""
        if self._hidden:
            self._hidden = False
            self.setFixedHeight(self.sizeHint().height())
            self.setStyle(self.style())  # 刷新样式

    def _hide(self):
        """隐藏横幅"""
        if not self._hidden:
            self._hidden = True
            self.setFixedHeight(0)

    def _on_config_clicked(self):
        """配置按钮点击"""
        if self._result and self._result.link_path:
            self.config_clicked.emit(self._result.link_path)

    def _on_dismiss(self):
        """关闭按钮点击"""
        self._hide()
        self.dismissed.emit()

    def is_visible(self) -> bool:
        """检查横幅是否正在显示"""
        return not self._hidden

    def clear(self):
        """清除横幅"""
        self._result = None
        self._hide()


class ConfigHintManager:
    """
    配置提示管理器

    负责检测错误信息中的配置缺失，并管理横幅的显示。
    """

    def __init__(self, banner: ConfigHintBanner):
        self._banner = banner
        self._last_checked = ""  # 避免重复检测

    def check_and_show(self, error_message: str) -> bool:
        """
        检测错误信息并显示配置提示（如果需要）

        Args:
            error_message: 错误信息

        Returns:
            bool: 是否显示了配置提示
        """
        from core.config_missing_detector import check_config_missing

        # 避免重复检测
        if error_message == self._last_checked:
            return False
        self._last_checked = error_message

        # 检测配置缺失
        result = check_config_missing(error_message)
        if result.is_missing_config:
            self._banner.show_config_hint(result)
            return True

        return False

    def clear(self):
        """清除提示"""
        self._last_checked = ""
        self._banner.clear()
