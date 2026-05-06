"""Goal Planner — TUI visual goal decomposition + progress tracking.

Inspired by Cognitum Goal Planner (goal.ruv.io):
  - Visual goal tree decomposition
  - Per-stage progress bars
  - Timeline visualization
  - Keyboard-driven (Ctrl+G to open)

Uses LivingTree's existing TaskPlanner + SuccessionTracker.
"""

from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Static, Input, Button, Label, RichLog, ProgressBar,
)

from loguru import logger


class GoalPlannerScreen(Screen):
    """Visual goal planer with task tree and progress tracking."""

    BINDINGS = [
        ("escape", "app.pop_screen", "返回"),
        ("ctrl+r", "refresh", "刷新"),
        ("ctrl+d", "decompose_input", "分解"),
        ("ctrl+m", "mark_done", "标记完成"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._goals: list[dict] = []
        self._input = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Static("[dim]Ctrl+R 刷新 | Ctrl+D 分解目标 | Ctrl+M 标记完成 | Esc 返回[/dim]")
        yield Static("# 🎯 目标规划器", id="planner-title")

        with Horizontal(id="planner-input-row"):
            yield Input(placeholder="输入目标: 环评报告编制 → 自动分解", id="goal-input")
            yield Button("分解", id="decompose-btn", variant="primary")

        yield ProgressBar(total=100, show_eta=False, id="overall-progress")
        yield Static("总进度: 0%", id="progress-label")

        with VerticalScroll(id="goal-tree"):
            yield Static("输入目标后，按 Ctrl+D 或点击[分解]自动生成子任务树", id="goal-placeholder")

        with Horizontal(id="bottom-bar"):
            yield Static("项目: 0 | 子任务: 0 | 完成: 0", id="stats-bar")

    def on_mount(self) -> None:
        if self._hub:
            self._refresh_display()

    @on(Button.Pressed, "#decompose-btn")
    async def on_decompose_click(self) -> None:
        await self.action_decompose_input()

    async def action_decompose_input(self) -> None:
        query = self.query_one("#goal-input", Input).value.strip()
        if not query:
            return

        await self._decompose_goal(query)

    async def action_refresh(self) -> None:
        if self._hub:
            self._refresh_display()

    async def action_mark_done(self) -> None:
        if not self._goals:
            return
        # Mark first pending goal as done
        for goal in self._goals:
            if goal.get("progress", 0) < 100:
                goal["progress"] = 100
                goal["status"] = "✅"
                break
        self._refresh_display()

    async def _decompose_goal(self, query: str) -> None:
        """Use LLM to decompose a natural language goal into sub-tasks."""
        if not self._hub:
            # Simple keyword decomposition fallback
            self._goals = self._rule_decompose(query)
            self._refresh_display()
            return

        try:
            prompt = f"""Break down this goal into 4-8 sequential sub-tasks:

Goal: {query}

Return JSON array: [{{"task": "...", "estimate": "X天", "order": 1}}, ...]
Include real tasks for environmental/government/engineering projects."""
            response = self._hub.chat(prompt)
            import json
            if "[" in response:
                response = response[response.index("["):response.rindex("]") + 1]
            tasks = json.loads(response)
            self._goals = [
                {
                    "task": t["task"], "estimate": t.get("estimate", ""),
                    "order": t.get("order", i + 1), "progress": 0, "status": "⬜",
                }
                for i, t in enumerate(tasks)
            ]
        except Exception:
            self._goals = self._rule_decompose(query)

        self._refresh_display()

    @staticmethod
    def _rule_decompose(query: str) -> list[dict]:
        patterns = {
            "环评": [
                ("资料收集与现状调查", "3天"), ("工程分析", "2天"),
                ("环境现状监测", "5天"), ("大气扩散模型预测", "2天"),
                ("噪声预测分析", "1天"), ("水环境影响分析", "2天"),
                ("污染防治措施论证", "2天"), ("报告编制与审核", "3天"),
            ],
            "验收": [
                ("现场踏勘", "1天"), ("监测方案编制", "1天"),
                ("现场采样监测", "2天"), ("数据处理与分析", "2天"),
                ("验收报告编制", "3天"), ("专家评审", "1天"),
                ("公示与备案", "20天"),
            ],
            "应急预案": [
                ("风险识别与评估", "2天"), ("应急资源调查", "1天"),
                ("预案编制", "3天"), ("内部审核", "1天"),
                ("专家评审", "1天"), ("备案与演练", "2天"),
            ],
        }
        for key, tasks in patterns.items():
            if key in query:
                return [
                    {"task": t, "estimate": e, "order": i + 1, "progress": 0, "status": "⬜"}
                    for i, (t, e) in enumerate(tasks)
                ]
        return [{"task": query, "estimate": "", "order": 1, "progress": 0, "status": "⬜"}]

    def _refresh_display(self) -> None:
        try:
            tree = self.query_one("#goal-tree", VerticalScroll)
            tree.remove_children()

            if not self._goals:
                tree.mount(Static("暂无目标 — 输入目标后按 Ctrl+D 分解", id="goal-placeholder"))
                return

            done = sum(1 for g in self._goals if g["progress"] >= 100)
            total = len(self._goals)
            pct = int(done / total * 100) if total else 0

            self.query_one("#overall-progress", ProgressBar).update(progress=pct)
            self.query_one("#progress-label", Static).update(f"总进度: {pct}%")
            self.query_one("#stats-bar", Static).update(
                f"项目: 1 | 子任务: {total} | 完成: {done}"
            )

            for goal in self._goals:
                icon = "✅" if goal["progress"] >= 100 else "⬜"
                bar = "█" * (goal["progress"] // 10) + "░" * (10 - goal["progress"] // 10)
                tree.mount(Static(
                    f"{icon} [{goal['order']}] {goal['task'][:60]} "
                    f"[{bar}] {goal['progress']}% "
                    f"[dim]({goal['estimate']})[/dim]"
                ))
        except Exception:
            pass
