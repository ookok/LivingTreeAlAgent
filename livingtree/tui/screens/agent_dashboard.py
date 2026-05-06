"""Agent Dashboard — TUI real-time status monitoring.

Inspired by Cognitum Agent Dashboard (goal.ruv.io/agents):
  - Agent status overview (idle/busy/error)
  - Task queue and completion stats
  - Deadlines overview with urgency indicators
  - Memory usage + storage health
  - Keyboard shortcut: Ctrl+A to open

Uses LivingTree's SystemOrchestrator.get_status().
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, Button, ProgressBar

from loguru import logger


class AgentDashboardScreen(Screen):
    """Real-time agent status monitoring dashboard."""

    BINDINGS = [
        ("escape", "app.pop_screen", "返回"),
        ("ctrl+r", "refresh_dashboard", "刷新"),
        ("ctrl+o", "optimize_now", "优化"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Static("[dim]Ctrl+R 刷新 | Ctrl+O 触发优化 | Esc 返回[/dim]")
        yield Static("# 📊 Agent 仪表盘", id="dashboard-title")

        # Row 1: Agent Status + Task Queue
        with Horizontal(id="status-row"):
            with Vertical(id="agent-status"):
                yield Static("## 🤖 子系统状态", id="agent-status-title")
                yield Static("加载中...", id="agent-status-content")
            with Vertical(id="task-queue"):
                yield Static("## 📋 任务队列", id="task-queue-title")
                yield Static("加载中...", id="task-queue-content")

        # Row 2: Deadlines + Memory
        with Horizontal(id="deadline-row"):
            with Vertical(id="deadlines-panel"):
                yield Static("## ⏰ 法规期限", id="deadlines-title")
                yield Static("加载中...", id="deadlines-content")
            with Vertical(id="memory-panel"):
                yield Static("## 🧠 记忆状态", id="memory-title")
                yield Static("加载中...", id="memory-content")

        # Row 3: Progress bars
        with Vertical(id="progress-row"):
            yield Static("## 📈 运行指标")
            yield ProgressBar(total=100, show_eta=False, id="health-bar")
            yield Static("系统健康度: --", id="health-label")

        yield Button("触发全局优化", id="optimize-btn", variant="primary")

    def on_mount(self) -> None:
        self._refresh()

    async def action_refresh_dashboard(self) -> None:
        self._refresh()

    async def action_optimize_now(self) -> None:
        try:
            from ...core.system_orchestrator import get_orchestrator
            orch = get_orchestrator()
            result = orch.run_optimization_cycle()
            self._refresh()
            self.notify(f"优化完成: {result.get('actions', [])}")
        except Exception as e:
            self.notify(f"优化失败: {e}", severity="error")

    @staticmethod
    def _get_status() -> dict:
        try:
            from ...core.system_orchestrator import get_orchestrator
            return get_orchestrator().get_status()
        except Exception:
            return {}

    def _refresh(self) -> None:
        status = self._get_status()
        try:
            self._update_agent_status(status)
            self._update_task_queue(status)
            self._update_deadlines()
            self._update_memory(status)
            self._update_health(status)
        except Exception:
            pass

    def _update_agent_status(self, status: dict) -> None:
        try:
            content = self.query_one("#agent-status-content", Static)
            lines = ["子系统运行状态:"]
            subsystems = [
                ("🟢 推理引擎", status.get("errors", []) == []),
                ("🟢 记忆系统", status.get("memory_items", 0) > 0),
                ("🟢 站点加速", status.get("accelerator", {}).get("total_domains", 0) > 0),
                ("🟢 知识图谱", True),
            ]
            for label, healthy in subsystems:
                icon = "🟢" if healthy else "🔴"
                lines.append(f"  {icon} {label}")
            content.update("\n".join(lines))
        except Exception:
            pass

    def _update_task_queue(self, status: dict) -> None:
        try:
            content = self.query_one("#task-queue-content", Static)
            lines = [
                f"活跃请求: {status.get('active_requests', 0)}",
                f"已处理: {status.get('total_processed', 0)}",
                f"平均延迟: {status.get('avg_latency_ms', 0):.1f}ms",
                f"幻觉率: {status.get('hallucination_rate', 0):.1%}",
            ]
            content.update("\n".join(lines))
        except Exception:
            pass

    def _update_deadlines(self) -> None:
        try:
            content = self.query_one("#deadlines-content", Static)
            from ...capability.deadline_engine import DynamicRulebook
            book = DynamicRulebook()
            book.load()
            stats = book.get_stats()
            # Also check if there's active scheduler
            lines = [
                f"法规库版本: v{stats['version']}",
                f"内置规则: {stats['builtin_rules']}条",
                f"自定义规则: {stats['custom_rules']}条",
                f"变更记录: {stats['changes']}次",
            ]
            content.update("\n".join(lines))
        except Exception:
            pass

    def _update_memory(self, status: dict) -> None:
        try:
            content = self.query_one("#memory-content", Static)
            lines = [
                f"记忆条目: {status.get('memory_items', 0)}",
                f"保留率: {status.get('memory_retention_rate', 0):.1%}",
                f"存储使用: {status.get('storage_usage_ratio', 0):.1%}",
                f"Protobuf比率: {status.get('protobuf_ratio', 0):.1%}",
            ]
            content.update("\n".join(lines))
        except Exception:
            pass

    def _update_health(self, status: dict) -> None:
        try:
            h = 90
            if status.get("hallucination_rate", 0) > 0.2:
                h -= 30
            if status.get("memory_items", 0) == 0:
                h -= 20
            errors = status.get("errors", [])
            h -= len(errors) * 5
            h = max(0, min(100, h))

            self.query_one("#health-bar", ProgressBar).update(progress=h)
            self.query_one("#health-label", Static).update(
                f"系统健康度: {h}%  {'🟢正常' if h > 70 else '🟡注意' if h > 40 else '🔴异常'}"
            )
        except Exception:
            pass
