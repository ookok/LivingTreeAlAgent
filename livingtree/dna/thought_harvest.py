"""R1 Thought Harvesting — Scavenge escaped tool-call JSON from <think> tags.

Inspired by Reasonix's scavenge pass. DeepSeek R1 models sometimes leak
tool-call JSON inside <think> tags instead of emitting them as proper
tool_calls in the response. This harvester scans the thinking stream
for these escaped tool calls and extracts them back into the normal
tool execution pipeline.

Usage:
    harvester = ThoughtHarvester()
    result = harvester.harvest(reasoning_content)
    if result.found:
        tool_calls = result.tool_calls
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarvestResult:
    """Result of harvesting thought content for tool calls."""
    found: bool = False
    tool_calls: list[dict] = field(default_factory=list)
    cleaned_text: str = ""
    extracted_json: list[str] = field(default_factory=list)


class ThoughtHarvester:
    """Scavenges escaped tool-call JSON from reasoning/thinking content.

    DeepSeek's thinking mode emits <think>...</think> blocks.
    Sometimes R1/pro models embed tool-call intent inside these
    blocks as JSON fragments. This harvester finds them.
    """

    TOOL_CALL_PATTERNS = [
        r'"name"\s*:\s*"(?P<name>[^"]+)"\s*,\s*"arguments"\s*:\s*(?P<args>\{[^}]+\})',
        r'"function"\s*:\s*\{(?P<body>[^}]+)\}',
        r'"tool"\s*:\s*"(?P<tool_name>[^"]+)"\s*,\s*"params"\s*:\s*(?P<tool_params>\{[^}]+\})',
    ]

    def harvest(self, reasoning_content: str) -> HarvestResult:
        """Scan reasoning content for escaped tool-call JSON.

        Args:
            reasoning_content: The raw reasoning/thinking text from the model

        Returns:
            HarvestResult with extracted tool calls
        """
        result = HarvestResult()

        if not reasoning_content or not reasoning_content.strip():
            return result

        blocks = self._extract_think_blocks(reasoning_content)
        if not blocks:
            result.cleaned_text = reasoning_content
            return result

        all_tool_calls = []
        all_extracted = []

        for block in blocks:
            candidates = self._find_json_candidates(block)
            for candidate in candidates:
                tool_call = self._parse_as_tool_call(candidate)
                if tool_call:
                    all_tool_calls.append(tool_call)
                    all_extracted.append(candidate)

        result.found = len(all_tool_calls) > 0
        result.tool_calls = all_tool_calls
        result.extracted_json = all_extracted

        cleaned = reasoning_content
        if all_extracted:
            cleaned = reasoning_content
            for ext in all_extracted:
                cleaned = cleaned.replace(ext, "")

        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        result.cleaned_text = cleaned

        return result

    def _extract_think_blocks(self, text: str) -> list[str]:
        """Extract content from <think>...</think> blocks."""
        pattern = r'<think>(.*?)</think>'
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return [m.strip() for m in matches]

        if text.strip().startswith("<think>") or "<｜end▁of▁thinking｜>" in text.lower()[:50]:
            cleaned = re.sub(r'</?think>', '', text).strip()
            return [cleaned] if cleaned else []

        return []

    def _find_json_candidates(self, text: str) -> list[str]:
        """Find JSON-like fragments in text."""
        candidates = []

        for pattern in self.TOOL_CALL_PATTERNS:
            for match in re.finditer(pattern, text, re.DOTALL):
                candidates.append(match.group(0))

        brace_pairs = []
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    brace_pairs.append(text[start:i + 1])
                    start = -1

        for pair in brace_pairs:
            if pair not in candidates and len(pair) > 10:
                candidates.append(pair)

        return candidates

    def _parse_as_tool_call(self, json_text: str) -> dict | None:
        """Try to parse a JSON fragment as a tool call."""
        try:
            data = json.loads(json_text)
            if not isinstance(data, dict):
                return None

            name = data.get("name") or data.get("tool") or data.get("function")
            args = data.get("arguments") or data.get("params") or data.get("args")

            if name:
                return {
                    "name": name,
                    "arguments": args if isinstance(args, dict) else {},
                    "source": "harvested_from_thinking",
                }

            if len(data) == 2 and "name" in data:
                return {
                    "name": data["name"],
                    "arguments": {k: v for k, v in data.items() if k != "name"},
                    "source": "harvested_from_thinking",
                }

            return None

        except (json.JSONDecodeError, TypeError):
            return None


def scavenge_thinking(reasoning_content: str) -> list[dict]:
    """Convenience function. Returns list of harvested tool calls."""
    harvester = ThoughtHarvester()
    result = harvester.harvest(reasoning_content)
    return result.tool_calls
