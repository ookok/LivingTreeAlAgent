"""Schema-driven Config Editor — Forms-style config editing in the TUI.

Inspired by DeepSeek-TUI's schemaui-based `/config tui` editor. Provides
a schema-driven forms interface for editing configuration sections.
Auto-discovers config schema from pydantic models and renders grouped
fields with live filter and validation.

Usage:
    /config tui  — opens the schema-driven TUI editor
    /config model deepseek-v4-flash — direct key=value setting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class ConfigField:
    key: str
    value: Any
    type_hint: str = "str"
    description: str = ""
    section: str = "general"
    default: Any = None
    required: bool = False
    choices: list[str] = field(default_factory=list)
    editable: bool = True

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "type": self.type_hint,
            "description": self.description,
            "section": self.section,
            "required": self.required,
            "choices": self.choices,
        }


class ConfigSchemaEditor:
    """Schema-driven config editor that discovers fields from pydantic models."""

    SECTIONS = [
        "model", "cell", "network", "knowledge", "observability",
        "evolution", "safety", "execution", "doc_engine", "api",
    ]

    def __init__(self, config: Any = None):
        self._config = config
        self._fields: list[ConfigField] = []
        self._discover_fields()

    def _discover_fields(self) -> None:
        if not self._config:
            return

        if hasattr(self._config, "model_dump"):
            raw = self._config.model_dump()
        elif isinstance(self._config, dict):
            raw = self._config
        else:
            raw = vars(self._config) if hasattr(self._config, "__dict__") else {}

        for section in self.SECTIONS:
            section_obj = raw.get(section, {})
            if isinstance(section_obj, dict):
                for key, value in section_obj.items():
                    self._fields.append(ConfigField(
                        key=key,
                        value=value,
                        type_hint=type(value).__name__,
                        section=section,
                        default=value,
                    ))

    def get_sections(self) -> list[str]:
        return sorted(set(f.section for f in self._fields))

    def get_fields(self, section: str | None = None) -> list[ConfigField]:
        if section:
            return [f for f in self._fields if f.section == section]
        return list(self._fields)

    def search_fields(self, query: str) -> list[ConfigField]:
        q = query.lower()
        return [
            f for f in self._fields
            if q in f.key.lower() or q in f.section.lower()
            or q in f.description.lower()
        ]

    def get_value(self, section: str, key: str) -> Any:
        for f in self._fields:
            if f.section == section and f.key == key:
                return f.value
        return None

    def set_value(self, section: str, key: str, value: Any) -> bool:
        converted = self._convert_value(value)
        for f in self._fields:
            if f.section == section and f.key == key:
                f.value = converted
                if self._config and hasattr(self._config, section):
                    section_obj = getattr(self._config, section)
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, converted)
                    elif isinstance(section_obj, dict):
                        section_obj[key] = converted
                return True
        return False

    def set_value_by_key(self, key: str, value: Any) -> bool:
        for f in self._fields:
            if f.key == key:
                return self.set_value(f.section, f.key, value)
        return False

    def to_dict(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for f in self._fields:
            if f.section not in result:
                result[f.section] = {}
            result[f.section][f.key] = f.value
        return result

    def format_for_display(self, section: str | None = None, filter_query: str = "") -> str:
        fields = self.get_fields(section)
        if filter_query:
            fields = self.search_fields(filter_query)

        lines = [f"[bold]Config: {section or 'all'} ({len(fields)} fields)[/bold]" if section else
                 f"[bold]Config: all sections ({len(fields)} fields)[/bold]"]
        lines.append("")

        current_section = ""
        for f in fields:
            if f.section != current_section:
                current_section = f.section
                lines.append(f"[bold #fea62b]  [{f.section}][/bold #fea62b]")

            val_str = self._format_value(f.value)
            desc = f" [dim]# {f.description}[/dim]" if f.description else ""
            lines.append(f"    {f.key} = {val_str}  ({f.type_hint}){desc}")

        return "\n".join(lines)

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "[dim]None[/dim]"
        if isinstance(value, bool):
            return "[#3fb950]True[/#3fb950]" if value else "[#f85149]False[/#f85149]"
        if isinstance(value, str) and len(value) > 40:
            if any(kw in value for kw in ("key", "secret", "password", "token")):
                return value[:6] + "***"
            return f"[dim]{value[:37]}...[/dim]"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return f"[{len(value)} items]"
        return str(value)[:50]

    @staticmethod
    def _convert_value(value: Any) -> Any:
        if isinstance(value, str) and value.lower() in ("true", "yes"):
            return True
        if isinstance(value, str) and value.lower() in ("false", "no"):
            return False
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
            try:
                return float(value)
            except ValueError:
                pass
        return value
