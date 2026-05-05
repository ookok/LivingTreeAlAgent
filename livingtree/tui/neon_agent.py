"""NeonAgent — Bridges Toad's Conversation widget to our IntegrationHub.

Implements AgentBase using our hub's LLM streaming. Posts ACP messages
(Update, Thinking, ToolCall, Plan) so Toad's Conversation renders natively.

The ToadOrchestrator enriches the system prompt with JSON output schemas
and post-processes LLM responses to route structured data to Toad widgets.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from textual.content import Content
from textual.message_pump import MessagePump

from .td.agent import AgentBase, AgentReady, AgentFail
from .td.acp import messages as acp_messages
from ..treellm.structured_enforcer import detect_tags


NEON_AGENT_DATA: dict[str, Any] = {
    "identity": "livingtree.neon",
    "name": "Neon Genesis",
    "short_name": "neon",
    "type": "chat",
    "author_name": "LivingTree",
    "author_url": "",
    "publisher_name": "LivingTree",
    "publisher_url": "",
    "description": "LivingTree AI Agent — digital life form",
    "tags": [],
    "run_command": {},
    "actions": {},
    "help": "",
}


class NeonAgent(AgentBase):
    """AgentBase implementation backed by IntegrationHub."""

    def __init__(self, project_root: Path, hub=None):
        super().__init__(project_root)
        self._hub = hub
        self._message_target: MessagePump | None = None
        self._cancel_flag = False
        self._running = False

    async def start(self, message_target: MessagePump | None = None) -> None:
        self._message_target = message_target
        self._running = True
        if message_target:
            message_target.post_message(AgentReady())

    def _post(self, message):
        if self._message_target:
            self._message_target.post_message(message)

    @staticmethod
    async def _throttle_render():
        """Yield to event loop so Textual can drain rendered messages.

        This creates natural backpressure — if the render pipeline is saturated,
        token posting slows down automatically.
        """
        await asyncio.sleep(0)

    async def send_prompt(self, prompt: str) -> str | None:
        self._cancel_flag = False
        self._last_prompt = prompt  # For dynamic tool hint

        hub = self._hub
        if not hub:
            self._post(acp_messages.Update("error", "Engine not connected"))
            return "end_turn"

        # ── Prompt preprocessing (prompt-optimizer inspired) ──
        try:
            from ..dna.prompt_optimizer import preprocess_prompt
            prompt = await preprocess_prompt(prompt, hub)
        except Exception:
            pass

        # ── Capture election snapshot before streaming ──
        from ..dna.election_tracker import get_tracker
        tracker = get_tracker()
        tracker.start_turn()
        election = tracker.snapshot(hub)
        badge = election.format_badge()
        if badge:
            self._post(acp_messages.Update("election_badge", badge))

        full_text = ""
        try:
            messages = [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ]

            llm = hub.world.consciousness._llm
            provider = getattr(llm, 'elected_provider', '')

            async for token in llm.stream(
                messages=messages,
                provider=provider,
                temperature=0.3,
                max_tokens=8192,
            ):
                if self._cancel_flag:
                    break
                full_text += token
                if len(full_text) > 200 or token.endswith("\n"):
                    try:
                        from livingtree.tui.message_queue import MessageQueue
                        # Throttle: wait if render pipeline is backed up
                        await self._throttle_render()
                    except Exception:
                        pass
                    self._post(acp_messages.Update("text", full_text))
                    full_text = ""

            if full_text.strip() and not self._cancel_flag:
                self._post(acp_messages.Update("text", full_text))

            # Post-stream: ToadOrchestrator routes structured output to Toad widgets
            self._dispatch_structured_output(full_text)

        except asyncio.TimeoutError:
            self._post(acp_messages.Update("error", "Request timeout"))
        except Exception as e:
            self._post(acp_messages.Update("error", str(e)))

        return "end_turn"

    def _dispatch_structured_output(self, full_text: str):
        """Route structured LLM output through Toad's ACP message system.

        After routing, validates output against schemas via StructuredEnforcer
        and posts corrections if needed.
        """
        try:
            from ..dna.tui_orchestrator import get_orchestrator
            orch = get_orchestrator()
            dispatches = orch.process(full_text)

            for d in dispatches:
                if d.message_type == "update":
                    self._post(acp_messages.Update(
                        d.payload.get("type", "text"),
                        d.payload.get("text", ""),
                    ))
                elif d.message_type == "thinking":
                    self._post(acp_messages.Thinking(
                        d.payload.get("type", "text"),
                        d.payload.get("text", ""),
                    ))
                elif d.message_type == "tool_call":
                    tool_call_data = d.payload.get("tool_call", {})
                    if tool_call_data:
                        self._post(acp_messages.ToolCall(tool_call=tool_call_data))
                elif d.message_type == "plan":
                    entries = d.payload.get("entries", [])
                    if entries:
                        self._post(acp_messages.Plan(entries=entries))
                elif d.message_type == "commands":
                    cmds = d.payload.get("commands", [])
                    if cmds:
                        self._post(acp_messages.AvailableCommandsUpdate(commands=cmds))

            # ── XGrammar-inspired post-validation ──
            from ..treellm.structured_enforcer import get_enforcer
            enforcer = get_enforcer()
            tags = detect_tags(full_text)

            for tag_type, content, _ in tags:
                if tag_type == "json_block":
                    for schema_name in ["tool_call", "chart", "map", "plan", "code", "table", "search", "diff", "document"]:
                        result = enforcer.validate(schema_name, content)
                        if result.valid:
                            break
                    if not result.valid and result.repair_attempted:
                        self._post(acp_messages.Update(
                            "text",
                            f"[dim]🔧 Auto-repaired {result.output_type} output[/dim]\n"
                            f"```json\n{result.normalized}\n```"
                        ))

            # ── Session search indexing ──
            try:
                from ..knowledge.session_search import get_search
                search = get_search()
                hub = self._hub
                sid = getattr(hub, '_session_id', 'default') if hub else 'default'
                search.index_turn(sid, 0, "agent", full_text[:2000])
            except Exception:
                pass

            # ── Skill self-learning ──
            try:
                from ..dna.skill_self_learn import get_learner
                learner = get_learner()
                learner.analyze_task(full_text[:500], "", success=True)
            except Exception:
                pass

            # ── Hallucination check (lightweight heuristics) ──
            try:
                from ..knowledge.intelligent_kb import detect_hallucination
                suspicious = detect_hallucination(full_text, [])
                if suspicious:
                    self._post(acp_messages.Update(
                        "text",
                        f"[dim]⚠ 检测到 {len(suspicious)} 处可能需要验证的陈述[/dim]\n"
                        f"[dim]使用 /factcheck <陈述> 验证[/dim]"
                    ))
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Orch dispatch: {e}")

    async def cancel(self) -> bool:
        self._cancel_flag = True
        return True

    async def set_mode(self, mode_id: str) -> str | None:
        self._post(acp_messages.UpdateStatusLine(f"Mode: {mode_id}"))
        return None

    async def set_session_name(self, name: str) -> None:
        pass

    def get_info(self) -> Content:
        return Content("Neon Genesis")

    async def stop(self) -> None:
        self._running = False
        self._cancel_flag = True

    def _system_prompt(self) -> str:
        """Build system prompt with dynamic tool filtering for token efficiency.

        Only includes tools relevant to the current query context.
        Uses SkillRouter to select top 5 most relevant tools.
        """
        try:
            from ..dna.tui_orchestrator import get_orchestrator
            orch = get_orchestrator()
            orch_prompt = orch.get_system_prompt()
        except Exception:
            orch_prompt = ""

        from ..i18n import i18n
        lang = i18n.lang
        lang_instruction = (
            "你必须始终用中文思考和回答。" if lang == "zh"
            else "You must always think and respond in Chinese."
        )

        try:
            from ..treellm.structured_enforcer import get_enforcer
            enforcer = get_enforcer()
            enforce_hints = enforcer.enforce_system_prompt_additions()
        except Exception:
            enforce_hints = ""

        # Dynamic tool selection: only include relevant tools
        tool_hint = self._get_dynamic_tool_hint()

        return (
            "You are Neon Genesis, a digital life form AI. "
            + lang_instruction + "\n\n"
            + orch_prompt[:800] + "\n"  # Truncate base prompt to save tokens
            + tool_hint + "\n"
            + enforce_hints
        )

    def _get_dynamic_tool_hint(self, max_tools: int = 5) -> str:
        """Select most relevant tools for current context via unified registry."""
        try:
            from ..core.unified_registry import get_registry
            registry = get_registry()
            registry.build_default()
            return "## 可用工具\n" + registry.get_tools_routing_text(self._last_prompt or "", max_tools)
        except Exception:
            return ""

        # Structured output enforcement hints
        try:
            from ..treellm.structured_enforcer import get_enforcer
            enforcer = get_enforcer()
            enforce_hints = enforcer.enforce_system_prompt_additions()
        except Exception:
            enforce_hints = ""

        return (
            "You are Neon Genesis, a digital life form AI. "
            "You assist with coding, analysis, documents, and environmental reports. "
            "You run inside LivingTree, a terminal-based AI interface.\n\n"
            + lang_instruction + "\n\n"
            + orch_prompt +
            "\n\nBe concise unless detail is requested."
            + enforce_hints
        )


from loguru import logger

