"""Full-screen help overlay with all keyboard shortcuts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button


HELP_TEXT = """
[bright_cyan]🌳 LivingTree AI Agent  —  快捷键参考[/bright_cyan]

[bold]🏠 首页导航[/bold]
  [bold]Tab[/bold] / [bold]Shift+Tab[/bold]    切换卡片焦点
  [bold]Enter[/bold]              进入选中的模块
  [bold]Esc[/bold]                返回首页
  [bold]/[/bold]                   搜索过滤卡片
  [bold]Ctrl+D[/bold]             切换深色/浅色主题

[bold]💬 聊天窗口[/bold]
  [bold]Enter[/bold]              发送消息
  [bold]Shift+Enter[/bold]        换行
  [bold]Ctrl+V[/bold]             粘贴图片/文件
  [bold]📎[/bold]                  选择文件上传
  [bold]🎤[/bold]                  语音输入
  [bold]💾[/bold]                  保存聊天记录

[bold]📝 代码编辑器[/bold]
  [bold]Ctrl+S[/bold]             保存文件
  [bold]Ctrl+F[/bold]             搜索
  [bold]Ctrl+H[/bold]             替换

[bold]📚 知识库 / 🔧 工具箱 / ⚙ 配置[/bold]
  [bold]Esc[/bold]                返回首页

[bold]全局快捷键[/bold]
  [bold]Ctrl+Q[/bold]             退出程序
  [bold]F1[/bold]                 显示此帮助
  [bold]Ctrl+P[/bold]             命令面板
"""


class HelpScreen(ModalScreen):
    """Full-screen keyboard shortcut reference."""

    BINDINGS = [("escape,f1,q", "dismiss", "关闭")]

    def compose(self) -> ComposeResult:
        yield Static(HELP_TEXT, id="help-content")
        yield Button("关闭 (Esc)", variant="primary", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
