"""Home Screen — card-based module selection."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer

from ..widgets.card import Card
from ..widgets.header import TuiHeader
from ..widgets.footer_bar import StatusBar


class HomeScreen(Screen):
    CSS = """
    HomeScreen {
        align: center middle;
    }
    HomeScreen > VerticalScroll {
        width: 56;
        height: 1fr;
        margin: 1 0;
    }
    HomeScreen #card-row {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield TuiHeader()
        with VerticalScroll():
            with Horizontal(id="card-row"):
                yield Card("💬", "AI 对话", "多模态智能对话助手", "chat")
                yield Card("📝", "代码编辑器", "多标签代码编辑与运行", "code")
                yield Card("📚", "知识库", "AI 知识管理与检索", "docs")
            with Horizontal(id="card-row"):
                yield Card("🔧", "工具箱", "PDF解析、翻译、图表", "tools")
                yield Card("⚙", "系统配置", "API、基因组、训练设置", "settings")
        yield StatusBar()
