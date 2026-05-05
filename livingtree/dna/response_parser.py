"""ResponseParser — extracts structured JSON from LLM output for TUI rendering.

Parses ```json blocks, detects output types, routes to appropriate TUI widgets.
Tracks success/failure for self-learning feedback loop.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .response_schemas import OutputType, get_schema


@dataclass
class ParsedOutput:
    output_type: OutputType
    data: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    error: str = ""
    is_valid: bool = False

    def __bool__(self):
        return self.is_valid


class ResponseParser:
    """Parse LLM output text into structured TUI-ready data."""

    JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)
    TYPE_DETECT_RE = re.compile(r'"type"\s*:\s*"(\w+)"')

    def __init__(self):
        self._stats: dict[OutputType, dict[str, int]] = {}
        self._learned_patterns: list[tuple[str, OutputType]] = []

    def parse(self, text: str) -> list[ParsedOutput]:
        """Parse LLM output text into structured outputs.

        Returns a list of ParsedOutput objects. Plain text is returned as CHAT type.
        """
        results = []

        # Extract JSON blocks
        json_blocks = self.JSON_BLOCK_RE.findall(text)
        if json_blocks:
            for block in json_blocks:
                parsed = self._parse_block(block.strip())
                if parsed.is_valid:
                    results.append(parsed)

        # If no structured blocks found, wrap remaining text as chat
        if not results and text.strip():
            results.append(ParsedOutput(
                output_type=OutputType.CHAT,
                data={"type": "chat", "content": text.strip()},
                raw_text=text,
                is_valid=True,
            ))

        # Track stats for self-learning
        for r in results:
            self._track(r)

        return results

    def _parse_block(self, block: str) -> ParsedOutput:
        """Parse a single code block. Detects type from content."""
        raw = block

        # Try JSON parse
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            # Try fixing common issues
            data = self._repair_json(block)
            if data is None:
                return ParsedOutput(
                    output_type=OutputType.ERROR,
                    raw_text=block,
                    error=f"Invalid JSON: {e}",
                )

        # Detect type from data
        output_type = self._detect_type(data)

        return ParsedOutput(
            output_type=output_type,
            data=data,
            raw_text=raw,
            is_valid=True,
        )

    def _detect_type(self, data: dict) -> OutputType:
        """Detect output type from JSON data."""
        type_str = data.get("type", "").lower()

        # Direct type field
        type_map = {
            "chat": OutputType.CHAT,
            "tool_call": OutputType.TOOL_CALL,
            "code": OutputType.CODE,
            "diff": OutputType.DIFF,
            "chart": OutputType.CHART,
            "map": OutputType.MAP,
            "document": OutputType.DOCUMENT,
            "table": OutputType.TABLE,
            "search": OutputType.SEARCH,
            "plan": OutputType.PLAN,
            "error": OutputType.ERROR,
        }
        if type_str in type_map:
            return type_map[type_str]

        # Heuristic detection based on fields present
        if "tool" in data and "params" in data:
            return OutputType.TOOL_CALL
        if "code" in data and "language" in data:
            return OutputType.CODE
        if "chart_type" in data and "data" in data:
            return OutputType.CHART
        if "lat" in data and "lon" in data:
            return OutputType.MAP
        if "rows" in data and "headers" in data:
            return OutputType.TABLE
        if "before" in data and "after" in data:
            return OutputType.DIFF
        if "results" in data:
            return OutputType.SEARCH
        if "steps" in data:
            return OutputType.PLAN
        if "content" in data:
            return OutputType.CHAT

        # Learned patterns
        for pattern, ptype in self._learned_patterns:
            if pattern in str(data).lower():
                return ptype

        return OutputType.CHAT

    def _repair_json(self, text: str) -> dict | None:
        """Attempt to repair common JSON formatting issues."""
        # Remove trailing commas
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Try unescaping
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting just the object
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return None

    def _track(self, output: ParsedOutput):
        """Track parsing stats for self-learning."""
        if output.output_type not in self._stats:
            self._stats[output.output_type] = {"total": 0, "success": 0}
        self._stats[output.output_type]["total"] += 1
        if output.is_valid:
            self._stats[output.output_type]["success"] += 1

    def get_stats(self) -> dict:
        return {
            k.value: {"total": v["total"], "success": v["success"],
                      "rate": v["success"] / max(v["total"], 1)}
            for k, v in self._stats.items()
        }

    def learn_pattern(self, response_text: str, expected_type: OutputType):
        """Learn a new detection pattern from user feedback."""
        keywords = _extract_keywords(response_text)
        for kw in keywords:
            self._learned_patterns.append((kw, expected_type))
        self._learned_patterns = self._learned_patterns[-50:]
        logger.debug(f"Learned pattern: {expected_type.value} ← '{response_text[:60]}'")


def _extract_keywords(text: str, max_kw: int = 5) -> list[str]:
    """Extract distinct keywords for pattern learning."""
    words = re.findall(r'\b[a-zA-Z_]{4,}\b', text.lower())
    stop = {"this", "that", "with", "from", "have", "been", "were", "they", "will", "when"}
    filtered = [w for w in words if w not in stop]
    seen = set()
    result = []
    for w in filtered:
        if w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= max_kw:
            break
    return result
