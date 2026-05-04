"""Tool-Call Repair — Auto-fix malformed and broken tool calls from DeepSeek.

Inspired by Reasonix's ToolCallRepair. DeepSeek models occasionally produce:
1. Deeply-nested object/array params that get silently dropped
2. Malformed JSON fragments (string="false" style syntax issues)
3. Truncated tool calls mid-stream
4. Parameter storms (too many tool calls at once)

This module heals these common shapes before dispatch so the tool
execution layer receives valid, complete, properly-structured calls.

Usage:
    repair = ToolCallRepair()
    fixed = repair.fix(tool_call_json)
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger


class ToolCallRepair:

    def __init__(self, max_depth: int = 4, max_params: int = 50):
        self.max_depth = max_depth
        self.max_params = max_params

    def fix(self, raw: str | dict) -> dict | None:
        """Repair a tool-call into a valid dict. Returns None if unrepairable."""
        if isinstance(raw, dict):
            return self._validate(raw)

        if not raw or not raw.strip():
            return None

        data = self._parse_json(raw)
        if data is None:
            data = self._heal_malformed(raw)
        if data is None:
            return None

        data = self._flatten_nested(data)
        data = self._truncate_storm(data)

        return self._validate(data)

    def _parse_json(self, text: str) -> dict | None:
        text = text.strip()
        if not text:
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for prefix in ("```json", "```"):
            if text.startswith(prefix):
                inner = text[len(prefix):]
                if inner.endswith("```"):
                    inner = inner[:-3]
                try:
                    return json.loads(inner.strip())
                except json.JSONDecodeError:
                    pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _heal_malformed(self, text: str) -> dict | None:
        """Heal common malformed JSON patterns from DeepSeek."""
        text = text.strip()

        text = re.sub(r'"\s*:\s*"', '": "', text)

        text = re.sub(r'(?<!")(\w+)(?="?\s*:)', r'"\1"', text)
        text = re.sub(r':\s*"(.*?)"\s*[,}]', lambda m: f': "{m.group(1)}"'+ (
            "," if m.group(0).endswith(",") else "}"
        ), text)

        text = re.sub(r'string="false"', '"false"', text)
        text = re.sub(r'string="true"', '"true"', text)

        text = re.sub(r'(?<=:)\s*(\d+)\s*([,}])', r' \1\2', text)

        braces = text.count("{") - text.count("}")
        if braces > 0:
            text += "}" * braces
        elif braces < 0:
            text = "{" + text

        brackets = text.count("[") - text.count("]")
        if brackets > 0:
            text += "]" * brackets

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _flatten_nested(self, data: dict) -> dict:
        """Flatten deeply-nested params to single-level prefixed names.

        DeepSeek sometimes drops deeply-nested object/array params.
        A structure like {"config": {"nested": {"key": "val"}}}
        becomes {"config.nested.key": "val"}.
        """
        if not data:
            return data

        flat: dict[str, Any] = {}
        self._flatten_recursive(data, "", flat, 0)

        if len(flat) > self.max_params:
            flat = dict(list(flat.items())[:self.max_params])

        return flat

    def _flatten_recursive(self, obj: Any, prefix: str, result: dict, depth: int):
        if depth > self.max_depth:
            result[prefix.rstrip(".")] = str(obj)[:500]
            return

        if isinstance(obj, dict):
            for key, val in obj.items():
                new_key = f"{prefix}{key}."
                self._flatten_recursive(val, new_key, result, depth + 1)
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:10]):
                new_key = f"{prefix}{i}."
                self._flatten_recursive(item, new_key, result, depth + 1)
        else:
            result[prefix.rstrip(".")] = obj

    def _truncate_storm(self, data: dict) -> dict:
        """Limit number of top-level keys to prevent tool-call storms."""
        if len(data) <= self.max_params:
            return data
        logger.warning(f"Tool-call storm: {len(data)} params, truncating to {self.max_params}")
        truncated = dict(list(data.items())[:self.max_params])
        truncated["_TRUNCATED"] = f"Original had {len(data)} params, showing first {self.max_params}"
        return truncated

    def _validate(self, data: dict) -> dict | None:
        """Basic validation of repaired tool-call."""
        if not isinstance(data, dict):
            return None
        if not data:
            return None
        return data


def repair_tool_call(raw: str | dict) -> dict | None:
    """Convenience function for single-shot repair."""
    return ToolCallRepair().fix(raw)


def normalize_command(cmd: str) -> str:
    """Normalize shell commands — strips heredoc bodies for pattern matching.

    Recognizes <<DELIM, <<-DELIM, <<'DELIM', <<"DELIM".
    Leaves <<< (here-string) untouched.
    """
    heredoc = re.search(
        r'<<\s*[\'"]?(\w+)[\'"]?\s*\n.*?\n\1',
        cmd, re.DOTALL,
    )
    if heredoc:
        before = cmd[:heredoc.start()]
        delim = heredoc.group(1)
        after = cmd[heredoc.end():]
        cmd = f"{before}<<{delim} ... <<{delim}{after}"
    return cmd
