"""ErrorPatternLearner — Auto-learns from repeated errors to prevent recurrence.

Monitors error fingerprints (query_hash + provider + error_type). When the same
fingerprint appears 3+ times, auto-generates a mitigation rule:
  - timeout → skip that provider for similar queries
  - rate_limit → apply cooldown period  
  - hallucination → force deep_probe(3)
  - http_500 → demote provider

Integrates with existing ErrorInterceptor (capture) and ErrorReplay (manual replay).

Integration:
    epl = get_error_pattern_learner()
    rule = epl.check(query, provider)           # check before call
    if rule: apply_mitigation(rule)
    epl.record(query, provider, error_type)     # record after failure
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from loguru import logger

PATTERNS_FILE = Path(".livingtree/error_patterns.json")


class ErrorPatternLearner:
    """Auto-learns from repeated error patterns."""

    _instance: Optional["ErrorPatternLearner"] = None

    @classmethod
    def instance(cls) -> "ErrorPatternLearner":
        if cls._instance is None:
            cls._instance = ErrorPatternLearner()
        return cls._instance

    def __init__(self):
        self._patterns: dict[str, dict] = {}
        self._rules_applied = 0
        self._load()

    def _fingerprint(self, query: str, provider: str, error_type: str) -> str:
        key = f"{query[:80]}:{provider}:{error_type}"
        return hashlib.md5(key.encode()).hexdigest()[:10]

    def record(self, query: str, provider: str, error_type: str) -> Optional[dict]:
        """Record an error and return a rule if pattern threshold reached."""
        fp = self._fingerprint(query, provider, error_type)
        p = self._patterns.setdefault(fp, {
            "count": 0, "first_seen": time.time(), "rule": None,
            "provider": provider, "error_type": error_type,
        })
        p["count"] += 1

        if p["count"] >= 3 and not p["rule"]:
            p["rule"] = self._generate_rule(provider, error_type)
            self._save()
            logger.warning(
                f"ErrorPattern: learned rule for {provider}/{error_type} "
                f"(count={p['count']}): {p['rule']['action']}"
            )
            return p["rule"]
        return None

    def check(self, query: str, provider: str, error_type: str = "") -> Optional[dict]:
        """Return any matching mitigation rule for this query+provider combo.

        If error_type is empty, checks all known types.
        """
        types = [error_type] if error_type else ["timeout", "rate_limit", "http_500", "hallucination"]
        for et in types:
            fp = self._fingerprint(query, provider, et)
            rule = self._patterns.get(fp, {}).get("rule")
            if rule:
                return rule
        # Also check provider-wide patterns
        for fp, p in self._patterns.items():
            if p.get("provider") == provider and p.get("count", 0) >= 3:
                return p.get("rule")
        return None

    def _generate_rule(self, provider: str, error_type: str) -> dict:
        return {
            "timeout":      {"action": "skip", "provider": provider, "reason": "predicted_timeout"},
            "rate_limit":   {"action": "cooldown", "provider": provider, "seconds": 120},
            "http_500":     {"action": "demote", "provider": provider},
            "hallucination": {"action": "deep_probe", "depth": 3},
        }.get(error_type, {"action": "log"})

    def apply_rule(self, rule: dict) -> Any:
        """Execute a mitigation rule. Returns action result."""
        self._rules_applied += 1
        action = rule.get("action", "log")
        if action == "skip":
            return None  # Caller skips this provider
        if action == "cooldown":
            return {"cooldown_seconds": rule.get("seconds", 60)}
        if action == "demote":
            try:
                from .competitive_eliminator import get_eliminator
                get_eliminator().force_demote(rule["provider"])
            except Exception:
                pass
        if action == "deep_probe":
            return {"deep_probe": True, "depth": rule.get("depth", 3)}
        return None

    def _save(self):
        try:
            PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                fp: {k: v for k, v in p.items() if k != "rule" or v}
                for fp, p in self._patterns.items()
            }
            PATTERNS_FILE.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def _load(self):
        try:
            if PATTERNS_FILE.exists():
                self._patterns = json.loads(PATTERNS_FILE.read_text())
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "patterns": len(self._patterns),
            "rules_active": sum(1 for p in self._patterns.values() if p.get("rule")),
            "rules_applied": self._rules_applied,
        }


_epl: Optional[ErrorPatternLearner] = None


def get_error_pattern_learner() -> ErrorPatternLearner:
    global _epl
    if _epl is None:
        _epl = ErrorPatternLearner()
    return _epl


__all__ = ["ErrorPatternLearner", "get_error_pattern_learner"]
