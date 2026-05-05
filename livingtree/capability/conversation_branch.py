"""ConversationBranch — tree-based conversation explorer.

    Not linear. Fork, explore alternatives, merge, or abandon branches.

    Branch structure:
        trunk ──→ fork "优化方案A" ──→ fork "优化方案B"
          │               │                    │
          │          3 turns             2 turns
          │               │                    │
          └────── merge ←──┘                    └── abandon

    Usage:
        cb = get_conversation_brancher()
        cb.fork("优化方案A", "当前上下文摘要")
        cb.post_turn("方案A", "user", "用lru_cache试试")
        cb.post_turn("方案A", "assistant", "好的，实现如下...")
        cb.merge("方案A", "采用方案A: lru_cache + 异步")
        tree = cb.render_tree()

    Commands:
        /branch fork <名称> — 开新分支
        /branch list — 查看所有分支
        /branch switch <名称> — 切换到分支
        /branch merge <名称> — 合并分支到主干
        /branch abandon <名称> — 放弃分支
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

BRANCH_DIR = Path(".livingtree/branches")
BRANCH_FILE = BRANCH_DIR / "conversation_tree.json"


@dataclass
class Branch:
    name: str
    parent: str = ""  # parent branch name, "" = trunk
    context_snapshot: str = ""  # what was the conversation state at fork point
    turns: list[dict] = field(default_factory=list)  # [{role, content, timestamp}]
    status: str = "active"  # active, merged, abandoned
    merged_into: str = ""  # where this branch was merged
    created_at: float = 0.0
    merged_at: float = 0.0


@dataclass
class ConversationTree:
    branches: dict[str, Branch] = field(default_factory=dict)
    current_branch: str = "trunk"
    trunk_turns: list[dict] = field(default_factory=list)


class ConversationBrancher:
    """Tree-based conversation management."""

    def __init__(self):
        BRANCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tree = ConversationTree()
        self._tree.branches["trunk"] = Branch(
            name="trunk", status="active", created_at=time.time()
        )
        self._load()

    def fork(self, name: str, context_snapshot: str = "") -> Branch:
        """Create a new conversation branch from current trunk state.

        Args:
            name: Branch name (e.g. "优化方案A")
            context_snapshot: Summary of conversation state at fork point
        """
        name = self._sanitize(name)
        if name in self._tree.branches:
            name = f"{name}_{int(time.time())}"

        branch = Branch(
            name=name,
            parent=self._tree.current_branch,
            context_snapshot=context_snapshot,
            created_at=time.time(),
        )
        self._tree.branches[name] = branch
        self._tree.current_branch = name
        self._save()
        logger.info(f"Branch forked: {name} ← {branch.parent}")
        return branch

    def switch(self, name: str) -> Branch | None:
        """Switch to a different branch."""
        if name not in self._tree.branches:
            # Partial match
            for bn in self._tree.branches:
                if name in bn:
                    name = bn
                    break
            else:
                return None
        self._tree.current_branch = name
        self._save()
        return self._tree.branches.get(name)

    def post_turn(self, branch_name: str, role: str, content: str):
        """Add a conversation turn to a branch or trunk."""
        branch = self._tree.branches.get(branch_name)
        if not branch:
            return
        turn = {"role": role, "content": content[:5000], "timestamp": time.time()}
        branch.turns.append(turn)
        if branch_name == "trunk":
            self._tree.trunk_turns.append(turn)
        self._save()

    def merge(self, name: str, summary: str = "") -> Branch | None:
        """Merge a branch back into its parent (or trunk).

        The branch's turns are appended to the parent with a merge marker.
        """
        branch = self._tree.branches.get(name)
        if not branch or branch.status == "merged":
            return None

        parent = self._tree.branches.get(branch.parent, self._tree.branches["trunk"])

        # Insert merge marker with branch turns
        merge_note = {
            "role": "system",
            "content": f"[合并分支: {name}] {summary}" if summary else f"[合并分支: {name}]",
            "timestamp": time.time(),
            "branch_merge": True,
            "branch_name": name,
            "branch_turns": branch.turns,
        }
        parent.turns.append(merge_note)
        if branch.parent in ("trunk", ""):
            self._tree.trunk_turns.append(merge_note)

        branch.status = "merged"
        branch.merged_at = time.time()
        branch.merged_into = branch.parent or "trunk"

        self._tree.current_branch = branch.parent or "trunk"
        self._save()
        logger.info(f"Branch merged: {name} → {branch.merged_into}")
        return branch

    def abandon(self, name: str) -> Branch | None:
        """Mark a branch as abandoned (keeps history)."""
        branch = self._tree.branches.get(name)
        if not branch:
            return None
        branch.status = "abandoned"
        self._tree.current_branch = "trunk"
        self._save()
        return branch

    def render_tree(self) -> str:
        """ASCII tree rendering of branches."""
        lines = ["🌲 对话分支树", ""]
        lines.append(f"  [当前] {'trunk' if self._tree.current_branch == 'trunk' else self._tree.current_branch}")

        for name, b in self._tree.branches.items():
            if name == "trunk":
                continue
            icon = {"active": "🌿", "merged": "✅", "abandoned": "❌"}.get(b.status, "•")
            parent = b.parent or "trunk"
            turn_count = len(b.turns)
            lines.append(
                f"  {icon} {name} ← {parent} | "
                f"{turn_count}轮 | {b.status}"
            )
            if b.context_snapshot:
                lines.append(f"     📎 {b.context_snapshot[:80]}")

        active = sum(1 for b in self._tree.branches.values() if b.status == "active")
        merged = sum(1 for b in self._tree.branches.values() if b.status == "merged")
        abandoned = sum(1 for b in self._tree.branches.values() if b.status == "abandoned")
        lines.append(f"\n{active} 活跃 | {merged} 已合并 | {abandoned} 已放弃")

        return "\n".join(lines)

    def get_conversation(self, branch_name: str = "", include_merged: bool = True) -> list[dict]:
        """Get the full conversation for a branch (including merged sub-branches)."""
        if branch_name and branch_name in self._tree.branches:
            if include_merged:
                return self._flatten_branch(branch_name)
            return self._tree.branches[branch_name].turns
        return self._flatten_branch("trunk")

    def _flatten_branch(self, name: str) -> list[dict]:
        """Recursively flatten a branch including merged children."""
        branch = self._tree.branches.get(name)
        if not branch:
            return []

        turns = list(branch.turns)
        # Include merged sub-branches
        for sub_name, sub in self._tree.branches.items():
            if sub.merged_into == name:
                merge_marker = {
                    "role": "system",
                    "content": f"[合并分支: {sub_name}]",
                    "branch_merge": True,
                    "branch_name": sub_name,
                    "branch_turns": sub.turns,
                }
                turns.append(merge_marker)
        return turns

    def _sanitize(self, name: str) -> str:
        import re
        return re.sub(r'[^\w\u4e00-\u9fff_-]', '_', name)[:40]

    def _save(self):
        data = {
            "current_branch": self._tree.current_branch,
            "trunk_turns": self._tree.trunk_turns[-50:],
            "branches": {
                name: {
                    "name": b.name, "parent": b.parent,
                    "context_snapshot": b.context_snapshot,
                    "turns": b.turns[-30:], "status": b.status,
                    "created_at": b.created_at, "merged_at": b.merged_at,
                    "merged_into": b.merged_into,
                }
                for name, b in self._tree.branches.items()
            },
        }
        BRANCH_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRANCH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not BRANCH_FILE.exists():
            return
        try:
            d = json.loads(BRANCH_FILE.read_text(encoding="utf-8"))
            self._tree.current_branch = d.get("current_branch", "trunk")
            self._tree.trunk_turns = d.get("trunk_turns", [])
            for name, bd in d.get("branches", {}).items():
                self._tree.branches[name] = Branch(**{
                    k: bd.get(k, "") if k != "turns" else bd.get(k, [])
                    for k in Branch.__dataclass_fields__
                })
        except Exception:
            pass


_cb: ConversationBrancher | None = None


def get_conversation_brancher() -> ConversationBrancher:
    global _cb
    if _cb is None:
        _cb = ConversationBrancher()
    return _cb
