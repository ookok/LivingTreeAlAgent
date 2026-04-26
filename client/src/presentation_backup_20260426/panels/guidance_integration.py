"""
追问面板与 EnhancedAgentChat 集成示例
======================================

展示如何在 AgentChat 中集成追问功能

使用方式：
```python
from client.src.presentation.guidance_integration import AgentChatWithGuidance

# 创建带追问功能的 AgentChat
chat = AgentChatWithGuidance(base_chat)

# 或使用工厂函数
chat = create_chat_with_guidance(base_chat)
```

UI 集成方式：
```python
from client.src.presentation.components import GuidancePanel, GuidanceDisplayMode

# 在 AgentChat 的响应区域下方添加追问面板
panel = GuidancePanel(
    items=guidance_items,
    display_mode=GuidanceDisplayMode.BUTTON
)

# 连接信号
panel.guidance_clicked.connect(lambda action, text: chat.send_message(text))
```

作者：LivingTreeAI Team
日期：2026-04-24
"""

from typing import Optional, Callable, List, Any
from dataclasses import dataclass

# PyQt6 imports
try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    from PyQt6.QtCore import pyqtSignal, pyqtSlot
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


# 导入核心组件
try:
    from core.agent_chat_enhancer import (
        EnhancedAgentChat,
        GuidanceResult,
        GuidanceGenerator,
        GuidanceItem as CoreGuidanceItem,
        enhance_agent_chat,
    )
    ENHANCER_AVAILABLE = True
except ImportError:
    ENHANCER_AVAILABLE = False
    print("[Integration] EnhancedAgentChat not available")


# 导入 UI 组件
try:
    from ui.components.guidance_panel import (
        GuidancePanel,
        GuidanceItem,
        GuidanceDisplayMode,
        GuidanceManager,
    )
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    print("[Integration] GuidancePanel not available")


# ============== 集成包装器 ==============

@dataclass
class GuidanceUIConfig:
    """追问UI配置"""
    display_mode: str = "button"      # button / card / inline
    max_visible: int = 3              # 最大可见追问数
    show_title: bool = True          # 显示标题
    title: str = "您可能还想问："    # 标题文本
    auto_show: bool = True            # 自动显示
    animation_enabled: bool = True    # 动画效果
    theme: str = "dark"              # dark / light


class AgentChatWithGuidance:
    """
    带追问功能的 AgentChat 包装器

    集成 EnhancedAgentChat 的追问功能到 PyQt6 UI

    信号：
    - guidance_requested(text: str): 用户请求追问
    - guidance_displayed(): 追问已显示
    - guidance_hidden(): 追问已隐藏
    """

    if PYQT6_AVAILABLE:
        guidance_requested = pyqtSignal(str)  # 追问文本
        guidance_displayed = pyqtSignal()
        guidance_hidden = pyqtSignal()

    def __init__(
        self,
        base_chat,
        config: Optional[GuidanceUIConfig] = None
    ):
        """
        Args:
            base_chat: 基础 AgentChat 实例
            config: 追问UI配置
        """
        self.base_chat = base_chat
        self.config = config or GuidanceUIConfig()

        # 初始化增强版 AgentChat
        if ENHANCER_AVAILABLE:
            self.enhanced_chat = enhance_agent_chat(
                base_chat,
                enable_guidance=True,
                max_guidance_questions=self.config.max_visible
            )
        else:
            self.enhanced_chat = None

        # 初始化追问管理器
        self._guidance_manager: Optional[GuidanceManager] = None
        self._current_panel = None

        # 回调
        self._on_send_callback: Optional[Callable[[str], None]] = None

    def set_send_callback(self, callback: Callable[[str], None]):
        """设置发送回调"""
        self._on_send_callback = callback

    def chat(self, message: str, **kwargs) -> str:
        """
        发送消息并处理追问

        Args:
            message: 用户消息
            **kwargs: 传递给 base_chat 的参数

        Returns:
            str: Agent 响应
        """
        if not self.enhanced_chat:
            return self.base_chat.chat(message, **kwargs)

        # 调用增强版 chat
        response = self.enhanced_chat.chat(message, **kwargs)

        # 自动显示追问
        if self.config.auto_show:
            self.show_guidance()

        return response

    def show_guidance(self, parent: Optional[QWidget] = None) -> Optional[QWidget]:
        """
        显示追问面板

        Args:
            parent: 父控件

        Returns:
            GuidancePanel 实例
        """
        if not self.enhanced_chat or not UI_AVAILABLE:
            return None

        guidance = self.enhanced_chat.get_guidance()
        if not guidance or not guidance.questions:
            return None

        # 转换为 UI 的 GuidanceItem
        display_mode = GuidanceDisplayMode.BUTTON
        if self.config.display_mode == "card":
            display_mode = GuidanceDisplayMode.CARD
        elif self.config.display_mode == "inline":
            display_mode = GuidanceDisplayMode.INLINE

        items = [
            GuidanceItem(
                text=q,
                action=f"guidance_{i}",
                icon="💬" if i == 0 else ""
            )
            for i, q in enumerate(guidance.questions[:self.config.max_visible])
        ]

        # 创建面板
        self._current_panel = GuidancePanel(
            items=items,
            display_mode=display_mode,
            title=self.config.title,
            show_title=self.config.show_title
        )

        # 设置主题
        self._current_panel.set_theme(self.config.theme)

        # 连接信号
        self._current_panel.guidance_clicked.connect(self._on_guidance_clicked)

        # 添加到父控件
        if parent and PYQT6_AVAILABLE:
            layout = parent.layout()
            if layout is None:
                layout = QVBoxLayout(parent)
                parent.setLayout(layout)
            layout.addWidget(self._current_panel)

        # 显示动画
        if self.config.animation_enabled:
            self._current_panel.show_animation()

        self.guidance_displayed.emit()
        return self._current_panel

    def hide_guidance(self):
        """隐藏追问面板"""
        if self._current_panel:
            if self.config.animation_enabled:
                self._current_panel.hide_animation()
            else:
                self._current_panel.hide()
                self._current_panel.deleteLater()
            self._current_panel = None
            self.guidance_hidden.emit()

    def clear_guidance(self):
        """清除追问"""
        self.hide_guidance()
        if self.enhanced_chat:
            # 清除已使用的标记
            pass  # EnhancedAgentChat 没有 clear 方法

    def _on_guidance_clicked(self, action: str, text: str):
        """追问被点击"""
        self.guidance_requested.emit(text)

        if self._on_send_callback:
            self._on_send_callback(text)

        self.hide_guidance()

    def get_current_guidance(self) -> Optional[GuidanceResult]:
        """获取当前追问"""
        if self.enhanced_chat:
            return self.enhanced_chat.get_guidance()
        return None

    @property
    def guidance_generator(self) -> Optional[GuidanceGenerator]:
        """获取追问生成器"""
        if self.enhanced_chat:
            return self.enhanced_chat._guidance_generator
        return None


# ============== 工厂函数 ==============

def create_chat_with_guidance(
    base_chat,
    display_mode: str = "button",
    max_questions: int = 3,
    theme: str = "dark"
) -> AgentChatWithGuidance:
    """
    创建带追问功能的 AgentChat

    Args:
        base_chat: 基础 AgentChat 实例
        display_mode: 展示模式 (button/card/inline)
        max_questions: 最大追问数
        theme: 主题 (dark/light)

    Returns:
        AgentChatWithGuidance 实例
    """
    config = GuidanceUIConfig(
        display_mode=display_mode,
        max_visible=max_questions,
        theme=theme
    )
    return AgentChatWithGuidance(base_chat, config)


# ============== PyQt6 集成示例 ==============

if __name__ == "__main__" and PYQT6_AVAILABLE and UI_AVAILABLE:
    import sys
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QPushButton,
        QTextEdit, QLabel, QScrollArea
    )
    from PyQt6.QtCore import Qt

    from client.src.presentation.components import GuidancePanel, GuidanceDisplayMode

    class DemoWindow(QWidget):
        """演示窗口"""

        def __init__(self):
            super().__init__()
            self.setWindowTitle("AgentChat + GuidancePanel 集成演示")
            self.setStyleSheet("background-color: #1e1e1e;")
            self.resize(700, 600)

            self._setup_ui()

            # 模拟的增强版 chat
            self._mock_guidance()

        def _setup_ui(self):
            """设置UI"""
            layout = QVBoxLayout(self)
            layout.setSpacing(16)

            # 标题
            title = QLabel("追问功能集成演示")
            title.setStyleSheet("""
                color: white;
                font-size: 18px;
                font-weight: bold;
            """)
            layout.addWidget(title)

            # 模式选择
            mode_label = QLabel("展示模式：")
            mode_label.setStyleSheet("color: #cccccc; font-size: 14px;")
            layout.addWidget(mode_label)

            # 按钮模式演示
            btn_area = self._create_mode_section(
                "按钮模式 (BUTTON)",
                GuidanceDisplayMode.BUTTON
            )
            layout.addWidget(btn_area)

            # 卡片模式演示
            card_area = self._create_mode_section(
                "卡片模式 (CARD)",
                GuidanceDisplayMode.CARD
            )
            layout.addWidget(card_area)

            # 内联模式演示
            inline_area = self._create_mode_section(
                "内联模式 (INLINE)",
                GuidanceDisplayMode.INLINE
            )
            layout.addWidget(inline_area)

            layout.addStretch()

        def _create_mode_section(self, title: str, mode: GuidanceDisplayMode) -> QWidget:
            """创建模式演示区域"""
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setSpacing(8)

            # 标题
            label = QLabel(title)
            label.setStyleSheet("color: #888888; font-size: 12px;")
            layout.addWidget(label)

            # 追问面板容器
            panel_container = QWidget()
            panel_container.setObjectName("PanelContainer")
            panel_container.setStyleSheet("""
                QWidget#PanelContainer {
                    background-color: #2d2d30;
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            panel_layout = QVBoxLayout(panel_container)
            panel_layout.setContentsMargins(0, 0, 0, 0)

            # 创建追问面板
            from ui.components.guidance_panel import GuidanceItem, create_guidance_panel

            questions = [
                "需要我详细解释一下吗？",
                "还有其他方面想了解吗？",
                "这个回答对您有帮助吗？",
            ]

            panel = create_guidance_panel(
                questions,
                display_mode=mode,
                on_click=lambda t: print(f"点击追问: {t}")
            )
            panel_layout.addWidget(panel)

            layout.addWidget(panel_container)
            return container

        def _mock_guidance(self):
            """模拟追问生成"""
            # 这里可以模拟 EnhancedAgentChat 生成追问
            pass

    # 运行演示
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())


# ============== 非 PyQt6 测试 ==============

elif __name__ == "__main__":
    print("=" * 60)
    print("AgentChat + GuidancePanel 集成示例")
    print("=" * 60)

    if not UI_AVAILABLE:
        print("⚠️ GuidancePanel 不可用（需要 PyQt6）")
    else:
        print("✅ GuidancePanel 可用")

    if not ENHANCER_AVAILABLE:
        print("⚠️ EnhancedAgentChat 不可用")
    else:
        print("✅ EnhancedAgentChat 可用")

    print()
    print("使用方式：")
    print("1. 导入组件：")
    print("   from client.src.presentation.guidance_integration import AgentChatWithGuidance")
    print()
    print("2. 创建实例：")
    print("   chat = AgentChatWithGuidance(base_chat)")
    print()
    print("3. 显示追问：")
    print("   panel = chat.show_guidance(parent_widget)")
    print()
    print("=" * 60)
