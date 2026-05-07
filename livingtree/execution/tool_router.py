"""ToolRouter — context-mode inspired PreToolUse routing interception.

context-mode (mksglu/context-mode): intercepts tool calls before execution,
routes large-output tools through sandboxes, blocks dangerous commands.

When a tool call would produce large output (>5KB), it's routed through
sandbox execution: raw data → FTS5 index → only matching snippets enter
context. Small calls pass through normally.

Usage:
    router = ToolRouter(engram_store=None, consciousness=None)
    result, was_intercepted = await router.route(tool_name, args, ctx)
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger

from .context_fold import fold_text_heuristic


@dataclass
class RouteDecision:
    tool_name: str
    intercepted: bool
    reason: str = ""
    original_size: int = 0
    compressed_size: int = 0
    sandboxed: bool = False

    @property
    def savings_pct(self) -> float:
        if self.original_size == 0:
            return 0.0
        return round((1 - self.compressed_size / self.original_size) * 100, 1)


class ToolRouter:
    """PreToolUse interceptor: blocks danger, sandboxes big output.

    context-mode approach: don't let raw tool output enter the conversation.
    Instead, execute in sandbox, index results, return only what's needed.
    """

    SIZING_THRESHOLD = 5000
    DANGEROUS_PATTERNS = [
        r'\brm\s+-rf\b', r'\bcurl\b.*\b\|\s*(ba)?sh\b', r'\bwget\b.*\b\|\s*(ba)?sh\b',
        r'\bchmod\s+777\b', r'\bdd\s+if=', r'\b:(){ :\|:& };:\b',
    ]
    LARGE_OUTPUT_TOOLS = {"Bash", "Read", "Grep", "Glob", "WebFetch", "Task",
                           "read", "grep", "bash", "webfetch"}
    SKIP_TOOLS = {"Write", "Edit", "Todowrite", "Skill"}

    def __init__(self, consciousness: Any = None):
        self.consciousness = consciousness
        self._stats: dict[str, RouteDecision] = {}
        self._total_saved: int = 0
        self._total_intercepted: int = 0

    async def route(self, tool_name: str, args: dict[str, Any] | None = None,
                    execute_fn: Callable | None = None,
                    fold_large: bool = True) -> tuple[Any, RouteDecision]:
        """Route a tool call: danger check → size check → execute or sandbox.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments
            execute_fn: The actual execution function (for sandboxed re-execution)
            fold_large: If True, fold large outputs through context_fold

        Returns:
            (result, RouteDecision) — result may be original, folded, or blocked
        """
        args = args or {}
        decision = RouteDecision(tool_name=tool_name, intercepted=False)

        if tool_name in self.SKIP_TOOLS:
            decision.reason = "skip_tool"
            return args, decision

        command = args.get("command", args.get("prompt", args.get("content", "")))
        if isinstance(command, str):
            for pattern in self.DANGEROUS_PATTERNS:
                if re.search(pattern, command):
                    decision.intercepted = True
                    decision.reason = f"blocked_dangerous: {pattern}"
                    logger.warning(f"ToolRouter BLOCKED {tool_name}: {command[:80]}")
                    return {"blocked": True, "reason": decision.reason}, decision

        if tool_name not in self.LARGE_OUTPUT_TOOLS:
            decision.reason = "pass_through_small_tool"
            return args, decision

        decision.intercepted = fold_large
        decision.reason = "routed_to_sandbox" if fold_large else "pass_through"
        self._total_intercepted += 1

        if execute_fn:
            result = await self._execute_sandboxed(tool_name, args, execute_fn, decision)
        else:
            result = args

        self._stats[self._total_intercepted] = decision
        return result, decision

    async def _execute_sandboxed(self, tool_name: str, args: dict[str, Any],
                                  execute_fn: Callable,
                                  decision: RouteDecision) -> Any:
        """Execute tool in sandbox, fold if output is large."""
        try:
            result = execute_fn(args) if not asyncio.iscoroutinefunction(execute_fn) \
                else await execute_fn(args)

            if isinstance(result, str):
                decision.original_size = len(result)
                if len(result) > self.SIZING_THRESHOLD:
                    folded = fold_text_heuristic(result, 500)
                    decision.compressed_size = len(folded)
                    self._total_saved += decision.original_size - decision.compressed_size
                    decision.sandboxed = True
                    logger.debug(
                        f"ToolRouter folded {tool_name}: "
                        f"{decision.original_size} → {decision.compressed_size} "
                        f"({decision.savings_pct}%)")
                    return folded
                else:
                    decision.compressed_size = decision.original_size
                    return result

            result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
            decision.original_size = len(result_str)
            if len(result_str) > self.SIZING_THRESHOLD:
                folded = fold_text_heuristic(result_str, 500)
                decision.compressed_size = len(folded)
                self._total_saved += decision.original_size - decision.compressed_size
                decision.sandboxed = True
                return decision
            decision.compressed_size = decision.original_size
            return result
        except Exception as e:
            decision.reason = f"execute_failed: {e}"
            return {"error": str(e)}

    def should_intercept(self, tool_name: str, expected_output_size: int = 0) -> bool:
        """Check whether a tool call should be intercepted before execution."""
        if tool_name in self.SKIP_TOOLS:
            return False
        if expected_output_size > self.SIZING_THRESHOLD:
            return True
        if tool_name in self.LARGE_OUTPUT_TOOLS:
            return True
        return False

    def preflight(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Preflight check: inspect args, return routing metadata.
        
        Returns a dict with 'route' key: 'block', 'sandbox', 'passthrough'.
        context-mode style: decide routing before execution.
        """
        if tool_name in self.SKIP_TOOLS:
            return {"route": "passthrough", "reason": "skip_tool"}

        command = args.get("command", args.get("prompt", args.get("content", "")))
        if isinstance(command, str):
            for pattern in self.DANGEROUS_PATTERNS:
                if re.search(pattern, command):
                    return {"route": "block", "reason": f"dangerous: {pattern[:40]}"}

        if tool_name in self.LARGE_OUTPUT_TOOLS:
            return {"route": "sandbox", "reason": f"large_output_tool: {tool_name}"}

        return {"route": "passthrough", "reason": "safe_small_tool"}

    def stats(self) -> dict[str, Any]:
        return {
            "total_intercepted": self._total_intercepted,
            "total_saved_bytes": self._total_saved,
            "total_saved_kb": round(self._total_saved / 1024, 1),
            "recent_decisions": [
                {"tool": d.tool_name, "saved": f"{d.savings_pct}%",
                 "from": d.original_size, "to": d.compressed_size}
                for d in list(self._stats.values())[-5:]
            ],
        }


_tool_router: ToolRouter | None = None


def get_tool_router(consciousness=None) -> ToolRouter:
    global _tool_router
    if _tool_router is None:
        _tool_router = ToolRouter(consciousness)
    return _tool_router
