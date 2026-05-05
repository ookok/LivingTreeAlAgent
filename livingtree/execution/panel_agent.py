"""PanelAgent — self-healing autonomous agent for each TUI panel.

Implements Toad's AgentBase. Each panel (chat/code/knowledge/tools) 
runs as an independent Agent with:
  1. Error interception via ErrorInterceptor
  2. Self-healing via SelfHealer health checks
  3. Auto-restart on failure (exponential backoff)
  4. Lifecycle: init → ready → running → error → healing → restart → running

Seamlessly integrates with Toad's Conversation + SessionTracker.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from ..tui.td.agent import AgentBase, AgentReady, AgentFail


class AgentState(str, Enum):
    INIT = "init"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    HEALING = "healing"
    STOPPED = "stopped"


@dataclass
class AgentHealth:
    state: AgentState = AgentState.INIT
    error_count: int = 0
    restart_count: int = 0
    last_error: str = ""
    last_restart: float = 0.0
    uptime_start: float = 0.0

    @property
    def uptime(self) -> float:
        if self.uptime_start:
            return time.time() - self.uptime_start
        return 0.0


class PanelAgent(AgentBase):
    """Base class for panel-specific autonomous agents.

    Subclass per panel and override `_on_prompt()` and `_on_setup()`.
    """

    MAX_RESTARTS = 5
    RESTART_BACKOFF_BASE = 2.0
    HEALTH_CHECK_INTERVAL = 30.0

    def __init__(self, project_root: Path, panel_name: str, hub=None):
        super().__init__(project_root)
        self.panel_name = panel_name
        self._hub = hub
        self._message_target = None
        self.health = AgentHealth()
        self._running = False
        self._healer_task: asyncio.Task | None = None
        self._restart_lock = asyncio.Lock()

    # ═══ AgentBase interface ═══

    async def start(self, message_target=None):
        self._message_target = message_target
        self._running = True
        self.health.state = AgentState.READY
        self.health.uptime_start = time.time()

        try:
            await self._on_setup()
        except Exception as e:
            self._handle_error("setup", e)

        if message_target:
            message_target.post_message(AgentReady())

        self._healer_task = asyncio.create_task(self._health_loop())

    async def send_prompt(self, prompt: str) -> str | None:
        if self.health.state in (AgentState.ERROR, AgentState.HEALING):
            return "error"
        self.health.state = AgentState.RUNNING
        try:
            await self._on_prompt(prompt)
            return "end_turn"
        except Exception as e:
            self._handle_error("prompt", e)
            return "error"

    async def cancel(self) -> bool:
        return True

    async def set_mode(self, mode_id: str) -> str | None:
        return None

    async def stop(self) -> None:
        self._running = False
        self.health.state = AgentState.STOPPED
        if self._healer_task:
            self._healer_task.cancel()

    def get_info(self):
        from textual.content import Content
        return Content(f"{self.panel_name} [{self.health.state.value}]")

    # ═══ Subclass hooks ═══

    async def _on_setup(self):
        """Override: panel initialization logic."""
        pass

    async def _on_prompt(self, prompt: str):
        """Override: handle a user prompt."""
        pass

    async def _on_heal(self):
        """Override: self-healing logic. Called when error detected."""
        pass

    # ═══ Error handling ═══

    def _handle_error(self, context: str, error: Exception):
        self.health.error_count += 1
        self.health.last_error = f"[{context}] {error}"
        self.health.state = AgentState.ERROR

        # Log to ErrorInterceptor
        try:
            from ..observability.error_interceptor import get_interceptor
            ei = get_interceptor()
            if ei:
                ei.capture(error, context=f"panel:{self.panel_name}:{context}")
        except Exception:
            pass

        logger.error(f"Panel {self.panel_name} error ({context}): {error}")
        asyncio.create_task(self._try_heal_and_restart())

    async def _try_heal_and_restart(self):
        """Self-heal, then restart with exponential backoff."""
        async with self._restart_lock:
            if self.health.restart_count >= self.MAX_RESTARTS:
                logger.error(f"Panel {self.panel_name} max restarts ({self.MAX_RESTARTS}) reached — stopping")
                self.health.state = AgentState.STOPPED
                if self._message_target:
                    self._message_target.post_message(AgentFail(
                        f"Panel {self.panel_name} failed after {self.MAX_RESTARTS} restarts",
                        details=self.health.last_error,
                    ))
                return

            # Phase 1: Self-heal
            self.health.state = AgentState.HEALING
            logger.info(f"Panel {self.panel_name} self-healing...")
            try:
                await self._on_heal()
            except Exception as e:
                logger.debug(f"Panel {self.panel_name} heal failed: {e}")

            # Phase 2: Restart with backoff
            delay = self.RESTART_BACKOFF_BASE ** self.health.restart_count
            self.health.restart_count += 1
            self.health.last_restart = time.time()
            logger.info(f"Panel {self.panel_name} restarting in {delay:.1f}s (attempt {self.health.restart_count})")
            await asyncio.sleep(delay)

            try:
                self.health.state = AgentState.READY
                self.health.uptime_start = time.time()
                await self._on_setup()
                if self._message_target:
                    self._message_target.post_message(AgentReady())
                logger.info(f"Panel {self.panel_name} restarted successfully")
            except Exception as e:
                self._handle_error("restart", e)

    # ═══ Health monitoring ═══

    async def _health_loop(self):
        """Periodic health check. Triggers heal on anomaly."""
        while self._running:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            if self.health.state == AgentState.RUNNING:
                try:
                    healthy = await self._health_check()
                    if not healthy:
                        logger.warning(f"Panel {self.panel_name} health check failed")
                        self._handle_error("health", RuntimeError("Health check failed"))
                except Exception as e:
                    self._handle_error("health", e)

    async def _health_check(self) -> bool:
        """Override: return False if panel is unhealthy."""
        return True


# ═══ Chat Panel Agent ═══

class ChatPanelAgent(PanelAgent):
    """Agent for the chat/conversation panel."""

    def __init__(self, project_root: Path, hub=None):
        super().__init__(project_root, "chat", hub)

    async def _on_prompt(self, prompt: str):
        if not self._hub or not self._hub.world:
            raise RuntimeError("Hub not available")
        await self._hub.chat(prompt)

    async def _on_setup(self):
        if not self._hub:
            from ..integration.hub import IntegrationHub
            self._hub = IntegrationHub(lazy=True)
            await self._hub.start()

    async def _on_heal(self):
        self._hub = None


# ═══ Code Panel Agent ═══

class CodePanelAgent(PanelAgent):
    """Agent for the code editor panel."""

    def __init__(self, project_root: Path, hub=None):
        super().__init__(project_root, "code", hub)

    async def _on_setup(self):
        from pathlib import Path
        self._workspace = Path.cwd()

    async def _on_prompt(self, prompt: str):
        pass  # Code panel has its own interaction model

    async def _health_check(self) -> bool:
        import shutil
        return shutil.which("git") is not None


# ═══ Knowledge Panel Agent ═══

class KnowledgePanelAgent(PanelAgent):
    """Agent for the knowledge base panel."""

    def __init__(self, project_root: Path, hub=None):
        super().__init__(project_root, "knowledge", hub)

    async def _on_setup(self):
        from ..knowledge.document_kb import DocumentKB
        self._kb = DocumentKB()

    async def _on_heal(self):
        if hasattr(self, '_kb'):
            try:
                self._kb.close()
            except Exception:
                pass
        self._kb = None


# ═══ Tools Panel Agent ═══

class ToolsPanelAgent(PanelAgent):
    """Agent for the tools panel."""

    def __init__(self, project_root: Path, hub=None):
        super().__init__(project_root, "tools", hub)

    async def _on_setup(self):
        from ..dna.unified_skill_system import get_skill_system
        self._skills = get_skill_system()
        self._skills.build()

    async def _on_heal(self):
        self._skills = None


# ═══ Agent Manager ═══

class AgentManager:
    """Manages lifecycle of all panel agents."""

    def __init__(self):
        self._agents: dict[str, PanelAgent] = {}

    def register(self, panel: str, agent: PanelAgent):
        self._agents[panel] = agent

    def get(self, panel: str) -> PanelAgent | None:
        return self._agents.get(panel)

    async def start_all(self, message_target=None):
        for name, agent in self._agents.items():
            try:
                await agent.start(message_target)
                logger.info(f"Agent {name} started")
            except Exception as e:
                logger.error(f"Agent {name} failed to start: {e}")

    async def stop_all(self):
        for agent in self._agents.values():
            try:
                await agent.stop()
            except Exception:
                pass

    def get_status(self) -> dict:
        return {
            name: {
                "state": a.health.state.value,
                "errors": a.health.error_count,
                "restarts": a.health.restart_count,
                "uptime": a.health.uptime,
            }
            for name, a in self._agents.items()
        }


# ═══ Global ═══

_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
