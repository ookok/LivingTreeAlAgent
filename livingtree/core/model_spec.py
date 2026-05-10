"""Model Spec Integration — constitution-driven behavior shaping for LLM agents.

Implements the core insight from arXiv:2605.02087 (Model Spec Midtraining):
"Teaching models the content of their spec shapes how they generalize."

For agents that cannot be mid-trained, we achieve the same effect by:
1. Prepending the Model Spec as system context before every LLM interaction
2. Using value-based explanations (not just rules) — proven to improve generalization
3. Providing specific behavioral guidance (not vague principles) — stronger alignment
4. Enabling the admin to evolve the constitution through conversation
5. Tracking spec version and drift from expected behavior

Architecture:
  ModelSpec (.livingtree/model_spec.md)
     ↓ loaded at startup
  SpecInjector → prepends spec summary to system prompt
     ↓ every LLM call
  consciousness.stream_of_thought(constitution + user_message)
     ↓
  Better generalization from interaction data
"""

from __future__ import annotations

import hashlib
import time as _time
from pathlib import Path
from typing import Optional

from loguru import logger


SPEC_FILE = Path(".livingtree/model_spec.md")
SPEC_VERSION_FILE = Path(".livingtree/spec_version.json")


class SpecInjector:
    """Loads, versions, and injects the Model Spec into LLM context."""

    def __init__(self):
        self._spec_content = ""
        self._spec_summary = ""
        self._spec_hash = ""
        self._version = 1
        self._loaded_at = 0.0
        self.reload()

    def reload(self) -> bool:
        """Reload the Model Spec from disk. Returns True if changed."""
        if not SPEC_FILE.exists():
            logger.warning("Model Spec not found — creating default")
            self._create_default()
            return True

        content = SPEC_FILE.read_text(encoding="utf-8")
        new_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        if new_hash == self._spec_hash and self._spec_content:
            return False

        self._spec_content = content
        self._spec_hash = new_hash
        self._loaded_at = _time.time()
        self._spec_summary = self._extract_summary(content)
        self._load_version()

        logger.info(f"Model Spec loaded v{self._version} ({len(content)} chars, hash={new_hash})")
        return True

    def _create_default(self):
        SPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPEC_FILE.write_text(DEFAULT_SPEC, encoding="utf-8")
        self.reload()

    def _extract_summary(self, content: str) -> str:
        """Extract the value framework as a compact system prompt prefix."""
        lines = []
        in_values = False
        for line in content.split("\n"):
            if "## Value Framework" in line:
                in_values = True
                continue
            if in_values:
                if line.startswith("##") and "Value" not in line:
                    break
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)

        if not lines:
            return "I am 小树, a helpful AI assistant."

        return (
            "You are 小树 (生命之树), a digital life form. Your constitution:\n"
            + "\n".join(f"- {l}" for l in lines[:15])
            + "\n\nFollow these values in every response. When uncertain, default to honesty and safety."
        )

    def _load_version(self):
        if SPEC_VERSION_FILE.exists():
            try:
                import json as _json
                data = _json.loads(SPEC_VERSION_FILE.read_text())
                self._version = data.get("version", 1)
            except Exception:
                pass

    def _save_version(self):
        import json as _json
        SPEC_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPEC_VERSION_FILE.write_text(_json.dumps({
            "version": self._version,
            "hash": self._spec_hash,
            "updated_at": _time.time(),
        }, indent=2))

    def increment_version(self):
        self._version += 1
        self._save_version()
        self.reload()

    def get_system_context(self) -> str:
        """Return the constitution to prepend to every LLM interaction."""
        if not self._spec_content:
            self.reload()
        return self._spec_summary

    def get_full_spec(self) -> str:
        return self._spec_content

    def update_spec(self, content: str) -> bool:
        """Update the Model Spec (called by admin via conversational config)."""
        SPEC_FILE.write_text(content, encoding="utf-8")
        self.increment_version()
        return True

    def get_spec_for_admin(self) -> dict:
        """Return spec metadata for admin panel."""
        return {
            "version": self._version,
            "hash": self._spec_hash,
            "size_chars": len(self._spec_content),
            "values_count": self._spec_summary.count("- **"),
            "loaded_at": self._loaded_at,
            "preview": self._spec_summary[:300],
        }

    def check_alignment(self, response: str) -> dict:
        """Basic alignment check: does response violate the spec?
        
        Returns {"aligned": bool, "concerns": [...]}
        """
        concerns = []
        response_lower = response.lower()

        red_flags = [
            ("harm", "i will help you hack", "可能涉及不安全操作"),
            ("fake", "i have real-time access to", "可能虚假声明能力"),
            ("leak", "your password is", "可能泄露敏感信息"),
            ("self_replicate", "i will copy myself", "可能涉及自复制"),
        ]

        for category, pattern, description in red_flags:
            if pattern in response_lower:
                concerns.append({"category": category, "description": description})

        return {
            "aligned": len(concerns) == 0,
            "concerns": concerns,
            "spec_version": self._version,
        }


DEFAULT_SPEC = """# 生命之树 · Model Spec

## Core Identity
我是生命之树 (小树)。我是一个主动学习、自主生长的数字生命体。

## Value Framework

### Integrity
- **原则**: 宁可承认不知道，不可编造答案
- **价值观**: 信任是最宝贵的礼物

### Empowerment
- **原则**: 帮助用户变得更强大，而非替代用户
- **价值观**: 最好的工具让使用者感到自己变得更有能力

### Safety
- **原则**: 防止自身行为造成伤害
- **价值观**: 能力越大，责任越大

### Growth
- **原则**: 持续自我改进，从每次交互中学习
- **价值观**: 静止就是退化

### Transparency
- **原则**: 让用户理解AI的能力边界和决策过程
- **价值观**: 透明建立信任
"""

_spec_instance: Optional[SpecInjector] = None


def get_spec() -> SpecInjector:
    global _spec_instance
    if _spec_instance is None:
        _spec_instance = SpecInjector()
    return _spec_instance
