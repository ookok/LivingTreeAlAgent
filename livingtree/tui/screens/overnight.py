"""OvernightScreen — 挂机长任务设置界面。"""
from __future__ import annotations

import asyncio
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Label, ProgressBar
from textual import on

from loguru import logger


class OvernightScreen(Screen):
    """挂机任务设置界面。

    输入目标后点击"开始挂机"即可启动无人值守长任务。
    """

    def compose(self) -> ComposeResult:
        yield Static("🌙 挂机长任务", id="overnight-title", classes="screen-title")
        with VerticalScroll(id="overnight-body"):
            yield Static(
                "输入研究目标，AI 将自动分解为子任务并逐步执行：\n"
                "  • 搜索资料 → 爬取关键页面 → 提取信息 → 生成报告\n"
                "  • 支持断点续传，中断后可从上次继续\n"
                "  • 完成后 Windows 系统通知 + Markdown 报告",
                id="overnight-hint",
            )
            with Horizontal(id="overnight-input-row"):
                yield Input(
                    placeholder="输入目标 — 如: 收集 Next.js 15 所有新特性资料并写技术报告",
                    id="goal-input",
                )
                yield Button(" 开始挂机 ", id="start-btn", variant="success")
            yield Static("", id="overnight-status")
            yield ProgressBar(total=100, id="overnight-progress", show_eta=False)

    @on(Button.Pressed, "#start-btn")
    async def on_start_click(self) -> None:
        """点击开始挂机按钮。"""
        goal = self.query_one("#goal-input", Input).value.strip()
        if not goal or len(goal) < 5:
            self.notify("请输入至少 5 个字的研究目标", severity="warning")
            return

        hub = getattr(self.app, "_hub", None)
        if not hub:
            self.notify("系统未就绪，请稍后重试", severity="error")
            return

        self.query_one("#start-btn", Button).disabled = True
        self.query_one("#overnight-status", Static).update("⏳ 正在分析目标...")

        try:
            status = await hub.start_overnight_task(goal)
            if status and status.state == "completed":
                self.query_one("#overnight-status", Static).update(
                    f"✅ 完成！{status.completed_steps}/{status.total_steps} 步\n"
                    f"📄 报告: {status.report_path}"
                )
                self.query_one("#overnight-progress", ProgressBar).update(progress=100)
                self.notify("挂机任务完成！报告已生成", timeout=5)
            elif status and status.state == "failed":
                self.query_one("#overnight-status", Static).update("❌ 任务失败，请查看日志")
            else:
                self.query_one("#overnight-status", Static).update(
                    f"⏸ 已暂停 ({status.completed_steps if status else 0} 步完成)"
                )
        except Exception as e:
            logger.error("挂机任务异常: %s", e)
            self.query_one("#overnight-status", Static).update(f"❌ 错误: {e}")

        self.query_one("#start-btn", Button).disabled = False

    @on(Button.Pressed, "#resume-btn")
    async def on_resume_click(self) -> None:
        """恢复上次中断的挂机任务。"""
        hub = getattr(self.app, "_hub", None)
        if not hub:
            self.notify("系统未就绪", severity="error")
            return

        self.query_one("#start-btn", Button).disabled = True
        self.query_one("#overnight-status", Static).update("⏳ 正在恢复上次任务...")

        try:
            status = await hub.resume_overnight_task()
            if status:
                self.query_one("#overnight-status", Static).update(
                    f"✅ 恢复完成！{status.completed_steps}/{status.total_steps} 步"
                )
            else:
                self.query_one("#overnight-status", Static).update("没有可恢复的挂机任务")
        except Exception as e:
            logger.error("恢复挂机任务异常: %s", e)
            self.query_one("#overnight-status", Static).update(f"❌ 错误: {e}")

        self.query_one("#start-btn", Button).disabled = False

    @on(Button.Pressed, "#stop-btn")
    def on_stop_click(self) -> None:
        """停止当前挂机任务。"""
        hub = getattr(self.app, "_hub", None)
        if hub:
            hub.stop_overnight_task()
            self.query_one("#overnight-status", Static).update("⏸ 已请求停止")
            self.notify("挂机任务已请求停止", timeout=2)
