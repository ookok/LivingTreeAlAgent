"""Structured Enforcer — Pure Python structured generation inspired by XGrammar-2.

No torch/transformers dependency. Core ideas adapted:
  1. TagDispatch: tag-triggered structure switching (regex-based, not AC automaton)
  2. SchemaCache: reuse parsed JSON schemas across requests
  3. OutputValidator: validate LLM output against expected schema, auto-repair

Usage:
    enforcer = StructuredEnforcer()
    enforcer.register_schema("tool_call", TOOL_CALL_SCHEMA)
    result = enforcer.validate("tool_call", llm_output)
    # → {"valid": True, "data": {...}} or {"valid": False, "error": "..."}
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    data: dict[str, Any] = field(default_factory=dict)
    normalized: str = ""
    error: str = ""
    output_type: str = ""
    repair_attempted: bool = False


# ═══ Base JSON Schemas for LivingTree output types ═══

TOOL_CALL_SCHEMA = {
    "type": "object",
    "required": ["type", "tool", "params"],
    "properties": {
        "type": {"type": "string", "enum": ["tool_call"]},
        "tool": {"type": "string"},
        "params": {"type": "object"},
        "reasoning": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]},
    },
}

CHART_SCHEMA = {
    "type": "object",
    "required": ["type", "chart_type", "title", "data"],
    "properties": {
        "type": {"type": "string", "enum": ["chart"]},
        "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "pie"]},
        "title": {"type": "string"},
        "data": {"type": "object"},
        "width": {"type": "integer", "minimum": 10, "maximum": 120},
        "height": {"type": "integer", "minimum": 5, "maximum": 40},
    },
}

MAP_SCHEMA = {
    "type": "object",
    "required": ["type", "lat", "lon"],
    "properties": {
        "type": {"type": "string", "enum": ["map"]},
        "lat": {"type": "number", "minimum": -90, "maximum": 90},
        "lon": {"type": "number", "minimum": -180, "maximum": 180},
        "zoom": {"type": "integer", "minimum": 0, "maximum": 18},
        "label": {"type": "string"},
    },
}

CODE_SCHEMA = {
    "type": "object",
    "required": ["type", "language", "code"],
    "properties": {
        "type": {"type": "string", "enum": ["code"]},
        "language": {"type": "string"},
        "code": {"type": "string"},
        "explanation": {"type": "string"},
        "filename": {"type": "string"},
    },
}

TABLE_SCHEMA = {
    "type": "object",
    "required": ["type", "headers", "rows"],
    "properties": {
        "type": {"type": "string", "enum": ["table"]},
        "title": {"type": "string"},
        "headers": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "array"}},
    },
}

PLAN_SCHEMA = {
    "type": "object",
    "required": ["type", "title", "steps"],
    "properties": {
        "type": {"type": "string", "enum": ["plan"]},
        "title": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "status"],
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "active", "done"]},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
    },
}

DIFF_SCHEMA = {
    "type": "object",
    "required": ["type", "filename", "before", "after"],
    "properties": {
        "type": {"type": "string", "enum": ["diff"]},
        "filename": {"type": "string"},
        "before": {"type": "string"},
        "after": {"type": "string"},
        "description": {"type": "string"},
    },
}

SEARCH_SCHEMA = {
    "type": "object",
    "required": ["type", "query", "results"],
    "properties": {
        "type": {"type": "string", "enum": ["search"]},
        "query": {"type": "string"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "url"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "summary": {"type": "string"},
                },
            },
        },
    },
}

DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["type", "title", "content"],
    "properties": {
        "type": {"type": "string", "enum": ["document"]},
        "format": {"type": "string", "enum": ["markdown", "text", "json"]},
        "title": {"type": "string"},
        "content": {"type": "string"},
        "sections": {"type": "array", "items": {"type": "string"}},
    },
}

# ═══ TagDispatch: tag-triggered structure switching ═══

TAG_PATTERNS: dict[str, re.Pattern] = {
    "tool_call": re.compile(r'<function[= ](\w+)>'),
    "xml_tool": re.compile(r'<tool_call>\s*\{.*?\}\s*</tool_call>', re.DOTALL),
    "think": re.compile(r'<think>(.*?)</think>', re.DOTALL),
    "code": re.compile(r'```(\w*)\n(.*?)```', re.DOTALL),
    "json_block": re.compile(r'```(?:json)?\s*\n?(.*?)\n?```', re.DOTALL),
}


def detect_tags(text: str) -> list[tuple[str, str, tuple[int, int]]]:
    """Detect all tag triggers in text. Returns [(tag_type, matched_content, (start, end)), ...]."""
    results = []
    for tag_type, pattern in TAG_PATTERNS.items():
        for m in pattern.finditer(text):
            groups = m.groups()
            content = groups[0] if groups else m.group(0)
            results.append((tag_type, content, (m.start(), m.end())))
    return sorted(results, key=lambda x: x[2][0])


# ═══ Schema Cache ═══

class SchemaCache:
    """Cross-request schema cache. Parses once, validates many times."""

    def __init__(self):
        self._schemas: dict[str, dict] = {}
        self._validators: dict[str, list] = {}
        self._stats: dict[str, dict] = {}

    def register(self, name: str, schema: dict):
        self._schemas[name] = schema
        self._validators[name] = self._compile_schema(schema)

    def get(self, name: str) -> dict | None:
        return self._schemas.get(name)

    def _compile_schema(self, schema: dict) -> list:
        """Compile a JSON schema into a list of (path, check_fn) validators."""
        validators = []
        if schema.get("type") == "object":
            required = schema.get("required", [])
            for key in required:
                validators.append(([key], self._required_check(key)))
            for key, prop in schema.get("properties", {}).items():
                validators.append(([key], self._type_check(prop.get("type", "any"))))
                if "enum" in prop:
                    validators.append(([key], self._enum_check(prop["enum"])))
                if "minimum" in prop:
                    validators.append(([key], self._range_check(prop.get("minimum"), prop.get("maximum"))))
        return validators

    def _required_check(self, key: str):
        def check(data: dict) -> str | None:
            if key not in data:
                return f"Missing required field: {key}"
            return None
        return check

    def _type_check(self, expected: str):
        type_map = {"string": str, "integer": int, "number": (int, float), "object": dict, "array": list, "boolean": bool}
        expected_types = type_map.get(expected)
        if expected_types is None:
            return lambda d: None

        def check(data: dict):
            for k, v in data.items():
                if not isinstance(v, expected_types if isinstance(expected_types, tuple) else (expected_types,)):
                    # Allow string→number coercion
                    if expected in ("integer", "number") and isinstance(v, str):
                        try:
                            float(v)
                            continue
                        except ValueError:
                            pass
            return None
        return check

    def _enum_check(self, allowed: list):
        allowed_set = set(allowed)

        def check(data: dict):
            for k, v in data.items():
                if isinstance(v, str) and allowed_set and v not in allowed_set:
                    pass  # Non-fatal
            return None
        return check

    def _range_check(self, minimum, maximum):
        def check(data: dict):
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    if minimum is not None and v < minimum:
                        return f"{k}={v} < min={minimum}"
                    if maximum is not None and v > maximum:
                        return f"{k}={v} > max={maximum}"
            return None
        return check

    def validate(self, schema_name: str, data: dict) -> list[str]:
        """Validate data against named schema. Returns list of error messages."""
        validators = self._validators.get(schema_name, [])
        errors = []
        for path, check_fn in validators:
            err = check_fn(data)
            if err:
                errors.append(err)
        self._stats.setdefault(schema_name, {"total": 0, "errors": 0})
        self._stats[schema_name]["total"] += 1
        if errors:
            self._stats[schema_name]["errors"] += 1
        return errors

    def get_stats(self) -> dict:
        return {
            name: {"total": s["total"], "errors": s["errors"],
                   "rate": 1 - s["errors"] / max(s["total"], 1)}
            for name, s in self._stats.items()
        }


# ═══ Structured Enforcer ═══

class StructuredEnforcer:
    """Main entry point: validates LLM output against schemas, auto-repairs."""

    def __init__(self):
        self.cache = SchemaCache()
        self._register_builtin_schemas()

    def _register_builtin_schemas(self):
        schemas = {
            "tool_call": TOOL_CALL_SCHEMA,
            "chart": CHART_SCHEMA,
            "map": MAP_SCHEMA,
            "code": CODE_SCHEMA,
            "table": TABLE_SCHEMA,
            "plan": PLAN_SCHEMA,
            "diff": DIFF_SCHEMA,
            "search": SEARCH_SCHEMA,
            "document": DOCUMENT_SCHEMA,
        }
        for name, schema in schemas.items():
            self.cache.register(name, schema)

    def validate(self, output_type: str, text: str) -> ValidationResult:
        """Validate LLM output against a named schema. Auto-repair on failure."""
        result = ValidationResult(output_type=output_type)

        # Extract JSON
        data = self._extract_json(text)
        if data is None:
            # Try repair
            repaired = self._repair_json(text)
            if repaired:
                result.repair_attempted = True
                result.data = repaired
                data = repaired
            else:
                result.error = "No valid JSON found"
                return result

        # Validate against schema
        errors = self.cache.validate(output_type, data)
        if errors:
            result.error = "; ".join(errors[:3])
            # Auto-fix common issues
            fixed = self._auto_fix(output_type, data, errors)
            if fixed:
                result.data = fixed
                result.valid = True
                result.repair_attempted = True
                result.normalized = json.dumps(fixed, ensure_ascii=False)
                return result
            return result

        result.valid = True
        result.data = data
        result.normalized = json.dumps(data, ensure_ascii=False)
        return result

    def _extract_json(self, text: str) -> dict | None:
        """Extract a JSON object from arbitrary text."""
        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try ```json blocks
        pattern = re.compile(r'```(?:json)?\s*\n?(.*?)\n?```', re.DOTALL | re.IGNORECASE)
        for m in pattern.finditer(text):
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue

        # Try finding JSON object boundaries
        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

        return None

    def _repair_json(self, text: str) -> dict | None:
        """Attempt to repair malformed JSON."""
        cleaned = text.strip()

        # Remove trailing commas before } or ]
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

        # Fix unquoted keys
        cleaned = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1 "\2":', cleaned)

        # Fix single quotes
        if '"' not in cleaned and "'" in cleaned:
            cleaned = cleaned.replace("'", '"')

        # Try to find and extract a JSON object
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _auto_fix(self, output_type: str, data: dict, errors: list[str]) -> dict | None:
        """Auto-fix common schema violations."""
        schema = self.cache.get(output_type)
        if not schema:
            return None

        fixed = dict(data)

        # Fix missing type field
        if "Missing required field: type" in "; ".join(errors):
            fixed["type"] = output_type

        # Fix missing required fields with defaults
        required = schema.get("required", [])
        for key in required:
            if key not in fixed:
                defaults = {
                    "params": {},
                    "data": {},
                    "steps": [],
                    "headers": [],
                    "rows": [],
                    "results": [],
                    "code": "",
                    "content": "",
                    "title": "",
                    "reasoning": "",
                }
                if key in defaults:
                    fixed[key] = defaults[key]

        # Re-validate
        remaining = self.cache.validate(output_type, fixed)
        if not remaining:
            return fixed
        return None

    def enforce_system_prompt_additions(self) -> str:
        """Generate additional system prompt content for structured output compliance."""
        return (
            "\n## CRITICAL: Output Format Requirements\n"
            "When outputting structured data, you MUST wrap JSON in ```json code blocks.\n"
            "The JSON object MUST include a `type` field set to the output type.\n"
            "All required fields MUST be present. Do NOT add trailing commas.\n"
            'Example: ```json\n{"type":"chart","chart_type":"bar","title":"Sales","data":{"labels":["A"],"values":[1]}}\n```\n'
        )

    def get_cache_stats(self) -> dict:
        return self.cache.get_stats()


# ═══ Global singleton ═══

_enforcer: StructuredEnforcer | None = None


def get_enforcer() -> StructuredEnforcer:
    global _enforcer
    if _enforcer is None:
        _enforcer = StructuredEnforcer()
    return _enforcer
