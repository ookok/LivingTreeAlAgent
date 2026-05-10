"""Locale loader — structured i18n string management (Hermes 0.13 inspired).

Loads locale JSON files from locales/ directory.
Falls back to built-in defaults when locale file is missing.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any, Optional


LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / "locales"
DEFAULT_LOCALE = "zh"


class Locale:
    """Lazy-loaded locale strings."""

    def __init__(self, locale_name: str = DEFAULT_LOCALE):
        self._name = locale_name
        self._data: dict[str, Any] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        path = LOCALES_DIR / f"{self._name}.json"
        try:
            self._data = _json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {}
        self._loaded = True

    def get(self, key: str, default: str = "") -> str:
        self._load()
        parts = key.split(".")
        node = self._data
        for p in parts:
            if isinstance(node, dict):
                node = node.get(p, "")
            else:
                return default
        return str(node) if node else default

    def t(self, key: str, **kwargs) -> str:
        """Translate with optional format parameters."""
        text = self.get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text


_locale: Optional[Locale] = None


def get_locale(name: str = "") -> Locale:
    global _locale
    if _locale is None:
        _locale = Locale(name or DEFAULT_LOCALE)
    return _locale


def t(key: str, default: str = "", **kwargs) -> str:
    """Shortcut: translate a key with fallback."""
    result = get_locale().get(key, default or key)
    if kwargs:
        result = result.format(**kwargs)
    return result
