"""Agent Capability Panel — Shows skills, tools, MCP, agents, experts in sidebar.

Replaces the old task list with a capability dashboard showing what
the agent can currently do.
"""

from textual.widgets import Static
from textual.containers import Vertical


class AgentCapabilityPanel(Vertical):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._skills = []
        self._tools = []
        self._agents = []
        self._mcp_servers = []
        self._experts = []

    def compose(self):
        yield Static("[bold #58a6ff]Capabilities[/bold #58a6ff]", id="cap-header")
        yield Static("[dim]Loading...[/dim]", id="cap-body")

    def update_from_hub(self, hub) -> None:
        try:
            if hub and hasattr(hub.world, 'tool_market'):
                tools = hub.world.tool_market.discover_tools()
                self._tools = [t.name if hasattr(t, 'name') else str(t)[:30] for t in tools[:10]]
            if hub and hasattr(hub.world, 'skill_factory'):
                self._skills = hub.world.skill_factory.discover_skills()[:10]
            if hub and hasattr(hub.world, 'orchestrator'):
                agents = hub.world.orchestrator._agents if hasattr(hub.world.orchestrator, '_agents') else []
                self._agents = [getattr(a, 'name', str(a))[:20] for a in agents[:8]]
            if hub and hasattr(hub.world, 'expert_config'):
                self._experts = [hub.world.expert_config.name] if hub.world.expert_config else []
        except Exception:
            pass
        self._render()

    def add_task_run(self, task_name: str, status: str = "running") -> None:
        self._active_tasks = getattr(self, '_active_tasks', {})
        self._active_tasks[task_name] = status
        self._render()

    def _render(self) -> None:
        try:
            body = self.query_one("#cap-body", Static)
            sections = []

            if self._skills:
                items = "\n".join(f"  🎯 {s}" for s in self._skills[:5])
                sections.append(f"[#3fb950]Skills:[/#3fb950]\n{items}")

            if self._tools:
                items = "\n".join(f"  🔧 {t}" for t in self._tools[:5])
                sections.append(f"[#fea62b]Tools:[/#fea62b]\n{items}")

            if self._agents:
                items = "\n".join(f"  🤖 {a}" for a in self._agents[:5])
                sections.append(f"[#58a6ff]Agents:[/#58a6ff]\n{items}")

            if self._experts:
                items = "\n".join(f"  👨‍🔬 {e}" for e in self._experts[:3])
                sections.append(f"[#d2a8ff]Experts:[/#d2a8ff]\n{items}")

            active = getattr(self, '_active_tasks', {})
            if active:
                items = "\n".join(
                    f"  {'◐' if s == 'running' else '●' if s == 'done' else '○'} {n}"
                    for n, s in list(active.items())[-5:]
                )
                sections.append(f"[#fea62b]Active Tasks:[/#fea62b]\n{items}")

            body.update("\n\n".join(sections) if sections else "[dim]No capabilities loaded[/dim]")
        except Exception:
            pass
