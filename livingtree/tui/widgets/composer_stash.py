"""Composer Stash — Park and restore drafts (Ctrl+S, /stash).

Saves drafts to ~/.livingtree/composer_stash.jsonl with LIFO restore.
200-entry cap. Self-healing JSONL parser.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class StashedDraft:
    text: str
    timestamp: str = ""
    workspace: str = ""

    def to_dict(self) -> dict:
        return {"text": self.text, "timestamp": self.timestamp, "workspace": self.workspace}

    @classmethod
    def from_dict(cls, d: dict) -> "StashedDraft":
        return cls(
            text=d.get("text", ""),
            timestamp=d.get("timestamp", ""),
            workspace=d.get("workspace", ""),
        )


class ComposerStash:
    """LIFO draft stash backed by JSONL file."""

    MAX_ENTRIES = 200
    STASH_FILE = ".livingtree/composer_stash.jsonl"

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace).resolve()
        self._stash_path = self._workspace / self.STASH_FILE
        self._drafts: list[StashedDraft] = []
        self._load()

    def push(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        draft = StashedDraft(
            text=text,
            timestamp=datetime.now(timezone.utc).isoformat(),
            workspace=str(self._workspace),
        )
        self._drafts.append(draft)
        if len(self._drafts) > self.MAX_ENTRIES:
            self._drafts = self._drafts[-self.MAX_ENTRIES:]
        self._save()
        logger.debug(f"Draft stashed ({len(text)} chars)")
        return True

    def pop(self) -> Optional[StashedDraft]:
        if not self._drafts:
            return None
        draft = self._drafts.pop()
        self._save()
        return draft

    def list(self) -> list[dict]:
        return [
            {
                "index": i,
                "preview": d.text[:80] + ("..." if len(d.text) > 80 else ""),
                "timestamp": d.timestamp,
                "workspace": d.workspace,
            }
            for i, d in enumerate(reversed(self._drafts))
        ]

    def clear(self) -> int:
        count = len(self._drafts)
        self._drafts.clear()
        self._save()
        return count

    def _load(self) -> None:
        if not self._stash_path.exists():
            return
        try:
            for line in self._stash_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    self._drafts.append(StashedDraft.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
            self._drafts = self._drafts[-self.MAX_ENTRIES:]
            logger.debug(f"Loaded {len(self._drafts)} stashed drafts")
        except Exception as e:
            logger.warning(f"Stash load error: {e}")

    def _save(self) -> None:
        self._stash_path.parent.mkdir(parents=True, exist_ok=True)
        self._stash_path.write_text(
            "\n".join(json.dumps(d.to_dict(), ensure_ascii=False) for d in self._drafts),
            encoding="utf-8",
        )
