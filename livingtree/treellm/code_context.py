"""CodeContext — Sliding-window, auto-compressing code context for LLM interactions.

Solves the max_tokens problem for code tasks:
  1. Sliding window: track recently accessed files, auto-expire old entries
  2. Auto-compress: file skeletons (signatures only) for background, full code for focus
  3. Relevance ranking: CodeGraph impact scores order files by task relevance
  4. Token budget: dynamic allocation across files with hard cap

Not just for auto-improve — used by every LLM chat that touches code files.
Integration point: core.py chat() pipeline, accessible via bus.invoke("code:context", ...)

Usage:
    from livingtree.treellm.code_context import CodeContext
    ctx = CodeContext()
    prompt = ctx.build("修改 livingtree/core.py 的 chat 方法，增加超时重试")
    # → returns ~4000 tokens: 10% header + 40% focused + 30% skeleton + 20% graph
"""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class FileContext:
    """A file in the sliding context window."""
    path: str
    skeleton: str = ""             # Imports + signatures only (~200 chars)
    focused_code: str = ""         # Full content around target lines (~2000 chars)
    tokens: int = 0                # Estimated token count
    last_access: float = 0.0
    access_count: int = 0
    impact_score: int = 0          # From CodeGraph blast_radius


class CodeContext:
    """Sliding-window code context manager for LLM interactions.

    Window = recent files (LRU, max 10) + persistent skeletons (max 50).
    Auto-compress: files not accessed in >5min → skeleton only.
    Token budget: hard cap adjustable, defaults to 8000 (6K remaining for LLM output).
    """

    DEFAULT_TOKEN_BUDGET = 8000

    def __init__(self, token_budget: int = 0):
        self._budget = token_budget or self.DEFAULT_TOKEN_BUDGET
        self._window: OrderedDict[str, FileContext] = OrderedDict()  # LRU
        self._skeletons: dict[str, str] = {}  # Persistent compressed cache
        self._max_window = 10
        self._compress_age = 300  # 5 min → skeleton only
        self._code_graph: Any = None

    # ── Public API ─────────────────────────────────────────────────

    def build(self, task_description: str, focus_files: list[str] | None = None,
              max_tokens: int = 0) -> str:
        """Build optimal LLM context for a code task.

        Args:
            task_description: What the user wants to do (e.g. "fix the timeout bug in chat()")
            focus_files: Specific files to include (from user mention or automatic detection)
            max_tokens: Override token budget (0 = use default)

        Returns:
            Formatted context string ~4000-6000 tokens
        """
        budget = max_tokens or self._budget
        parts = []

        # Header: task
        parts.append(f"## Task\n{task_description[:300]}")
        budget -= 100

        # Detect file paths from task description
        detected = focus_files or []
        if not detected:
            detected = re.findall(r'(\S+\.\w{1,4})', task_description)
        detected = [d for d in detected if Path(d).exists() or
                    any(Path(root) / d for root in ["livingtree", "."] if Path(root).exists())]

        # Resolve paths
        resolved = []
        for f in detected:
            for root in ["livingtree", "."]:
                candidate = Path(root) / f
                if candidate.exists():
                    f = str(candidate)
                    break
            if Path(f).exists():
                resolved.append(f)
        resolved = list(dict.fromkeys(resolved))  # Deduplicate

        # Always include files from sliding window
        for fpath in reversed(list(self._window.keys())):
            if fpath not in resolved and Path(fpath).exists():
                resolved.append(fpath)

        # Add CodeGraph impact-ordered files
        impacted = self._get_impacted_files(task_description, resolved)
        for fpath, score in impacted:
            if fpath not in resolved and Path(fpath).exists():
                resolved.append(fpath)

        # Build context: top files get full code, rest get skeletons
        focus = resolved[:3]   # Full code for top 3
        rest = resolved[3:8]   # Skeletons for next 5

        # Allocate budget
        per_focus = min(2500, (budget - 300) // max(len(focus), 1))
        per_rest = min(400, (budget - sum(min(2500, per_focus) for _ in focus)) // max(len(rest), 1))

        for fpath in focus:
            ctx = self._read_focused(fpath, max_chars=per_focus * 4)
            if ctx:
                parts.append(f"## {fpath}\n```python\n{ctx[:per_focus * 4]}\n```")
                budget -= per_focus
                self._update_window(fpath, focused=ctx)

        if rest:
            skeletons = []
            for fpath in rest:
                skel = self._get_skeleton(fpath)
                if skel:
                    skeletons.append(f"### {fpath}\n{skel[:per_rest * 4]}")
            if skeletons:
                parts.append("## Related Files (signatures)\n" + "\n".join(skeletons))

        # Graph context
        graph = self._get_graph_context(resolved[:5])
        if graph and budget > 150:
            parts.append(f"## Call Graph\n{graph}")

        # Self-compact old entries
        self._compact()

        return "\n\n".join(parts)

    def inject_chat_context(self, messages: list[dict],
                            focus_files: list[str] | None = None) -> list[dict]:
        """Inject code context into chat messages for normal dev interactions.

        Called by core.py chat() before LLM invocation.
        """
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = str(m.get("content", ""))
                break
        if not user_msg:
            return messages

        ctx = self.build(user_msg, focus_files=focus_files, max_tokens=3000)
        if ctx:
            for i, m in enumerate(messages):
                if m.get("role") == "system":
                    messages[i]["content"] = m["content"] + "\n\n" + ctx
                    return messages
            messages.insert(0, {"role": "system", "content": ctx})
        return messages

    # ── Sliding Window ────────────────────────────────────────────

    def _update_window(self, fpath: str, focused: str = "") -> None:
        now = time.time()
        if fpath in self._window:
            del self._window[fpath]
        self._window[fpath] = FileContext(
            path=fpath, focused_code=focused[:10000],
            tokens=len(focused) // 4, last_access=now,
            access_count=self._window.get(fpath, FileContext(path=fpath)).access_count + 1,
        )
        while len(self._window) > self._max_window:
            self._window.popitem(last=False)

    def _compact(self) -> None:
        """Compress old window entries to skeleton-only."""
        now = time.time()
        for fpath, fc in list(self._window.items()):
            if now - fc.last_access > self._compress_age:
                fc.focused_code = ""
                fc.tokens = len(fc.skeleton) // 4

    # ── File I/O ──────────────────────────────────────────────────

    def _get_skeleton(self, fpath: str) -> str:
        if fpath in self._skeletons:
            return self._skeletons[fpath]
        try:
            source = Path(fpath).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        lines = source.split("\n")
        skeleton = []
        for line in lines:
            s = line.strip()
            if (s.startswith(("import ", "from ", "def ", "async def ", "class ")) or
                (s.startswith("@") and len(s) < 60) or
                (s.startswith("#") and len(s) < 120)):
                skeleton.append(line[:120])
        result = "\n".join(skeleton)
        if len(self._skeletons) > 50:
            oldest = min(self._skeletons.keys(), key=lambda k: self._window.get(k, FileContext(path=k)).last_access)
            del self._skeletons[oldest]
        self._skeletons[fpath] = result[:2000]
        return result[:2000]

    def _read_focused(self, fpath: str, max_chars: int = 10000) -> str:
        try:
            return Path(fpath).read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError:
            return ""

    # ── CodeGraph Integration ─────────────────────────────────────

    def _get_impacted_files(self, task: str, known: list[str]) -> list[tuple[str, int]]:
        if not self._code_graph:
            try:
                self._load_code_graph()
            except Exception:
                return []
        if not self._code_graph:
            return []
        try:
            all_files = list(known)
            for word in re.findall(r'\b(\w+\.py)\b', task):
                if word not in all_files:
                    all_files.append(word)
            return self._code_graph.impact_score(all_files)[:10]
        except Exception:
            return []

    def _get_graph_context(self, files: list[str]) -> str:
        if not self._code_graph:
            return ""
        try:
            lines = []
            for fpath in files[:3]:
                callers = self._code_graph.get_callers(fpath)[:3]
                if callers:
                    lines.append(f"  Callers of {Path(fpath).name}: " +
                                ", ".join(c.name for c in callers))
                callees = self._code_graph.get_callees(fpath)[:3]
                if callees:
                    lines.append(f"  Called by {Path(fpath).name}: " +
                                ", ".join(c.name for c in callees))
            return "\n".join(lines)
        except Exception:
            return ""

    def _load_code_graph(self) -> None:
        try:
            from ..capability.code_graph import CodeGraph  # TODO(bridge): via bridge.ToolRegistry
            cg = CodeGraph()
            cache = Path(".livingtree/code_graph.pickle")
            if cache.exists():
                cg.load(str(cache))
                self._code_graph = cg
        except Exception:
            pass


# ═══ Singleton ════════════════════════════════════════════════════

_code_ctx: Optional[CodeContext] = None


def get_code_context() -> CodeContext:
    global _code_ctx
    if _code_ctx is None:
        _code_ctx = CodeContext()
    return _code_ctx


__all__ = ["CodeContext", "FileContext", "get_code_context"]
