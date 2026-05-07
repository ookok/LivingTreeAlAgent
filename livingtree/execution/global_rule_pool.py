"""GlobalRulePool — TACO-inspired cross-session compression rule pool.

Replicates TACO's key innovation: a persistent, self-evolving pool of
compression rules that accumulates knowledge across tasks and sessions.

Rules persist to disk (JSON), track usage statistics, support TTL expiration,
and provide namespace isolation so rules from different domains don't collide.

Architecture:
  GlobalRulePool (singleton, file-backed)
    ├── CompressionRule: individual rule with metadata
    ├── RuleNamespace: isolate rules by origin (e.g. "git", "build")
    ├── CRUD + priority-based querying
    └── Statistics: hit-rate, false-positive tracking, auto-pruning

Integration points:
  - terminal_compressor.py: queries pool for terminal output rules
  - self_evolving_rules.py: writes newly discovered rules
  - context_codex.py: seeds initial domain symbols
  - output_compressor.py: queries filler-removal rules
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

# ── Storage ──────────────────────────────────────────────────────────
POOL_DIR = Path(".livingtree/meta")
POOL_FILE = POOL_DIR / "compression_rules.json"
POOL_MAX_RULES = 500
POOL_MAX_RULES_PER_NAMESPACE = 100


class RuleAction(str, Enum):
    PASS_THROUGH = "pass_through"   # Always include
    TRUNCATE_TAIL = "truncate_tail"  # Keep first N chars/lines
    EXTRACT_PATTERN = "extract_pattern"  # Regex extraction
    REMOVE = "remove"               # Strip entirely
    REPLACE = "replace"             # Regex replacement
    CONDENSE = "condense"           # LLM-based condensation


@dataclass
class CompressionRule:
    """A single compression rule with full metadata for self-evolution.

    Mirrors TACO's 'structured compression rule' concept: each rule has
    a pattern (what to match), action (what to do), context (when to apply),
    and evolution metadata (how well it works).
    """

    id: str                          # Unique identifier (hash-based)
    name: str                        # Human-readable name
    namespace: str = "general"       # e.g. "git", "build", "npm", "shell"
    priority: int = 50               # 0-100, higher = applied first
    action: RuleAction = RuleAction.TRUNCATE_TAIL

    # Pattern matching
    match_pattern: str = ""          # Regex to match against terminal output
    match_context: str = ""          # When to apply (regex on command/context)

    # Action parameters
    truncate_lines: int = 50         # For TRUNCATE_TAIL: keep N lines
    truncate_chars: int = 5000       # For TRUNCATE_TAIL: keep N chars
    extract_regex: str = ""          # For EXTRACT_PATTERN
    replace_pattern: str = ""        # For REPLACE: what to replace
    replace_with: str = ""           # For REPLACE: replacement

    # Evolution metadata (TACO's key contribution)
    hit_count: int = 0
    false_positive_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_hit: float = 0.0
    expires_at: float = 0.0          # 0 = permanent
    origin_task: str = ""            # Which task created this rule
    auto_generated: bool = False     # Was this self-evolved?

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.false_positive_count
        return round(self.hit_count / max(total, 1), 3)

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_expired and (self.hit_count < 1000 or self.hit_rate >= 0.5)

    def record_hit(self) -> None:
        self.hit_count += 1
        self.last_hit = time.time()

    def record_false_positive(self) -> None:
        self.false_positive_count += 1
        self.last_hit = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "namespace": self.namespace,
            "priority": self.priority,
            "action": self.action.value,
            "match_pattern": self.match_pattern,
            "match_context": self.match_context,
            "truncate_lines": self.truncate_lines,
            "truncate_chars": self.truncate_chars,
            "extract_regex": self.extract_regex,
            "replace_pattern": self.replace_pattern,
            "replace_with": self.replace_with,
            "hit_count": self.hit_count,
            "false_positive_count": self.false_positive_count,
            "created_at": self.created_at,
            "last_hit": self.last_hit,
            "expires_at": self.expires_at,
            "origin_task": self.origin_task,
            "auto_generated": self.auto_generated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CompressionRule:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            namespace=data.get("namespace", "general"),
            priority=data.get("priority", 50),
            action=RuleAction(data.get("action", "truncate_tail")),
            match_pattern=data.get("match_pattern", ""),
            match_context=data.get("match_context", ""),
            truncate_lines=data.get("truncate_lines", 50),
            truncate_chars=data.get("truncate_chars", 5000),
            extract_regex=data.get("extract_regex", ""),
            replace_pattern=data.get("replace_pattern", ""),
            replace_with=data.get("replace_with", ""),
            hit_count=data.get("hit_count", 0),
            false_positive_count=data.get("false_positive_count", 0),
            created_at=data.get("created_at", time.time()),
            last_hit=data.get("last_hit", 0.0),
            expires_at=data.get("expires_at", 0.0),
            origin_task=data.get("origin_task", ""),
            auto_generated=data.get("auto_generated", False),
        )


class GlobalRulePool:
    """Cross-session rule pool with CRUD, priority, statistics, and pruning.

    TACO principle: rules discovered in task A automatically transfer to
    task B. The pool persists to disk and supports namespace-scoped queries.
    """

    def __init__(self):
        self._rules: dict[str, CompressionRule] = {}
        self._by_namespace: dict[str, set[str]] = {}
        self._stats = {
            "total_hits": 0,
            "total_applications": 0,
            "rules_created": 0,
            "rules_pruned": 0,
        }
        self._load()

    # ── CRUD ─────────────────────────────────────────────────────

    def add(self, rule: CompressionRule) -> bool:
        if len(self._rules) >= POOL_MAX_RULES:
            self._prune_lru()
        if len(self._rules) >= POOL_MAX_RULES:
            return False

        ns_count = len(self._by_namespace.get(rule.namespace, set()))
        if ns_count >= POOL_MAX_RULES_PER_NAMESPACE:
            self._prune_lru_namespace(rule.namespace)

        self._rules[rule.id] = rule
        self._by_namespace.setdefault(rule.namespace, set()).add(rule.id)
        self._stats["rules_created"] += 1
        self._save()
        return True

    def get(self, rule_id: str) -> CompressionRule | None:
        return self._rules.get(rule_id)

    def update(self, rule_id: str, **kwargs) -> bool:
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        self._save()
        return True

    def remove(self, rule_id: str) -> bool:
        rule = self._rules.pop(rule_id, None)
        if rule:
            ns = self._by_namespace.get(rule.namespace, set())
            ns.discard(rule_id)
            self._save()
            return True
        return False

    # ── Query ────────────────────────────────────────────────────

    def query(self, namespace: str | None = None,
              action: RuleAction | None = None,
              min_priority: int = 0,
              include_auto: bool = True,
              include_expired: bool = False) -> list[CompressionRule]:
        """Query rules by namespace, action, and priority.

        Returns rules sorted by priority (descending) — highest priority first.
        """
        results = []
        for rule in self._rules.values():
            if not include_expired and rule.is_expired:
                continue
            if not include_auto and rule.auto_generated:
                continue
            if namespace and rule.namespace != namespace:
                continue
            if action and rule.action != action:
                continue
            if rule.priority < min_priority:
                continue
            results.append(rule)
        results.sort(key=lambda r: (-r.priority, -r.hit_count))
        return results

    def find_matching(self, text: str, namespace: str | None = None,
                      context: str = "") -> list[CompressionRule]:
        """Find rules whose patterns match the given text.

        Tests match_pattern against text and match_context against context.
        Returns matching rules sorted by priority.
        """
        results = []
        for rule in self._rules.values():
            if rule.is_expired or not rule.is_active:
                continue
            if namespace and rule.namespace != namespace:
                continue

            # Test match_pattern against text
            if rule.match_pattern:
                try:
                    if not re.search(rule.match_pattern, text, re.IGNORECASE | re.DOTALL):
                        continue
                except re.error:
                    continue

            # Test match_context against context
            if rule.match_context and context:
                try:
                    if not re.search(rule.match_context, context, re.IGNORECASE):
                        continue
                except re.error:
                    continue

            results.append(rule)

        results.sort(key=lambda r: (-r.priority, -r.hit_count))
        return results

    def get_by_namespace(self, namespace: str) -> list[CompressionRule]:
        rule_ids = self._by_namespace.get(namespace, set())
        return [self._rules[rid] for rid in rule_ids if rid in self._rules]

    def get_namespaces(self) -> list[str]:
        return sorted(self._by_namespace.keys())

    # ── Application ─────────────────────────────────────────────

    def apply_rule(self, rule: CompressionRule, text: str) -> str:
        """Execute a compression rule against text. Returns compressed text."""
        self._stats["total_applications"] += 1

        try:
            if rule.action == RuleAction.PASS_THROUGH:
                rule.record_hit()
                return text

            elif rule.action == RuleAction.REMOVE:
                rule.record_hit()
                return ""

            elif rule.action == RuleAction.TRUNCATE_TAIL:
                rule.record_hit()
                return self._apply_truncate(rule, text)

            elif rule.action == RuleAction.EXTRACT_PATTERN:
                if rule.extract_regex:
                    return self._apply_extract(rule, text)
                rule.record_hit()
                return text

            elif rule.action == RuleAction.REPLACE:
                if rule.replace_pattern and rule.replace_with:
                    rule.record_hit()
                    result, count = re.subn(
                        rule.replace_pattern, rule.replace_with,
                        text, flags=re.IGNORECASE | re.DOTALL)
                    if count == 0:
                        rule.record_false_positive()
                    return result
                return text

            elif rule.action == RuleAction.CONDENSE:
                rule.record_hit()
                return text  # Condense requires LLM, handled externally

        except re.error:
            logger.debug(f"Rule {rule.id} has invalid regex, disabling")
            rule.record_false_positive()
            return text

        return text

    def apply_best_rule(self, text: str, namespace: str | None = None,
                        context: str = "") -> tuple[str, CompressionRule | None]:
        """Find and apply the best matching rule. Returns (result, rule_used)."""
        matches = self.find_matching(text, namespace, context)
        if not matches:
            self._stats["total_applications"] += 1
            return text, None

        best = matches[0]
        return self.apply_rule(best, text), best

    def apply_all_matching(self, text: str, namespace: str | None = None,
                           context: str = "") -> tuple[str, list[CompressionRule]]:
        """Apply all matching rules in priority order. Returns (result, rules_applied)."""
        matches = self.find_matching(text, namespace, context)
        result = text
        applied = []

        for rule in matches:
            self._stats["total_applications"] += 1
            prev = result
            result = self.apply_rule(rule, result)
            if result != prev or rule.action == RuleAction.PASS_THROUGH:
                applied.append(rule)

        return result, applied

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _apply_truncate(rule: CompressionRule, text: str) -> str:
        lines = text.splitlines()
        char_limit = min(rule.truncate_chars, 50000)

        if rule.truncate_lines > 0 and len(lines) > rule.truncate_lines:
            kept = lines[:rule.truncate_lines]
            text = "\n".join(kept)
            remaining = len(lines) - rule.truncate_lines
            text += f"\n\n[... {remaining} more lines truncated by TACO rule '{rule.name}']"

        if len(text) > char_limit:
            text = text[:char_limit]
            text += f"\n\n[... truncated at {char_limit} chars by TACO rule '{rule.name}']"

        return text

    @staticmethod
    def _apply_extract(rule: CompressionRule, text: str) -> str:
        try:
            matches = re.findall(rule.extract_regex, text,
                                 re.IGNORECASE | re.MULTILINE)
            if matches:
                rule.record_hit()
                # Deduplicate while preserving order
                seen = set()
                unique = []
                for m in matches:
                    s = " ".join(m) if isinstance(m, tuple) else m
                    if s not in seen:
                        seen.add(s)
                        unique.append(s)
                return "\n".join(unique[:100])
            else:
                rule.record_false_positive()
                return text
        except re.error:
            rule.record_false_positive()
            return text

    # ── Pruning ─────────────────────────────────────────────────

    def _prune_lru(self):
        active = [r for r in self._rules.values()
                  if not r.is_expired and r.auto_generated]
        if len(active) < 10:
            return
        active.sort(key=lambda r: (r.last_hit, r.hit_count))
        removed = 0
        for rule in active:
            if len(self._rules) < POOL_MAX_RULES * 0.8:
                break
            if self.remove(rule.id):
                removed += 1
        self._stats["rules_pruned"] += removed
        if removed:
            logger.debug(f"Pruned {removed} LRU rules from pool")

    def _prune_lru_namespace(self, namespace: str):
        rules = self.get_by_namespace(namespace)
        rules.sort(key=lambda r: (r.last_hit, r.hit_count))
        removed = 0
        for rule in rules:
            if len(self._by_namespace.get(namespace, set())) < POOL_MAX_RULES_PER_NAMESPACE * 0.8:
                break
            if self.remove(rule.id):
                removed += 1

    def prune_expired(self) -> int:
        removed = 0
        for rid in list(self._rules.keys()):
            rule = self._rules.get(rid)
            if rule and rule.is_expired:
                if self.remove(rid):
                    removed += 1
        return removed

    # ── Persistence ─────────────────────────────────────────────

    def _save(self):
        try:
            POOL_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 2,
                "updated_at": time.time(),
                "stats": self._stats,
                "rules": [r.to_dict() for r in self._rules.values()],
            }
            POOL_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            logger.debug(f"RulePool save: {e}")

    def _load(self):
        try:
            if POOL_FILE.exists():
                data = json.loads(POOL_FILE.read_text(encoding="utf-8"))
                for rd in data.get("rules", []):
                    rule = CompressionRule.from_dict(rd)
                    self._rules[rule.id] = rule
                    self._by_namespace.setdefault(
                        rule.namespace, set()).add(rule.id)
                self._stats = data.get("stats", self._stats)
                # Clean up stale rules
                self.prune_expired()
        except Exception as e:
            logger.debug(f"RulePool load: {e}")

    # ── Statistics ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        active = sum(1 for r in self._rules.values() if r.is_active)
        return {
            "total_rules": len(self._rules),
            "active_rules": active,
            "expired_rules": len(self._rules) - active,
            "namespaces": self.get_namespaces(),
            "by_namespace": {ns: len(ids) for ns, ids in self._by_namespace.items()},
            "hits": self._stats["total_hits"],
            "applications": self._stats["total_applications"],
            "rules_created": self._stats["rules_created"],
            "rules_pruned": self._stats["rules_pruned"],
        }


# ── TACO Seed Rules ─────────────────────────────────────────────────
# Built-in compression rules for common terminal output patterns.
# These seed the pool on first use — analogous to TACO's "built-in seed rules".

TACO_SEED_RULES: list[dict] = [
    # ── Git outputs ──
    {
        "id": "seed-git-log",
        "name": "git-log-compact",
        "namespace": "git",
        "priority": 90,
        "action": "extract_pattern",
        "match_pattern": r"(?m)^[a-f0-9]{7,40}",
        "extract_regex": r"(?m)^([a-f0-9]{7,40})\s+(.+)",
        "match_context": r"git\s+log",
    },
    {
        "id": "seed-git-status",
        "name": "git-status-compact",
        "namespace": "git",
        "priority": 85,
        "action": "remove",
        "match_pattern": r"^nothing to commit",
        "match_context": r"git\s+status",
    },
    {
        "id": "seed-git-diff-truncate",
        "name": "git-diff-truncate",
        "namespace": "git",
        "priority": 70,
        "action": "truncate_tail",
        "match_pattern": r"(?m)^(diff --git|---|\+\+\+|@@)",
        "truncate_lines": 200,
        "match_context": r"git\s+diff",
    },

    # ── Build outputs ──
    {
        "id": "seed-npm-install",
        "name": "npm-install-tail",
        "namespace": "build",
        "priority": 80,
        "action": "truncate_tail",
        "match_pattern": r"(?mi)(added\s+\d+\s+packages?|removed\s+\d+\s+packages?)",
        "truncate_lines": 30,
        "match_context": r"npm\s+(install|i)\b",
    },
    {
        "id": "seed-pip-install",
        "name": "pip-install-tail",
        "namespace": "build",
        "priority": 80,
        "action": "truncate_tail",
        "match_pattern": r"(?mi)(Successfully installed|Requirement already satisfied)",
        "truncate_lines": 20,
        "match_context": r"pip\s+install",
    },
    {
        "id": "seed-pip-warning",
        "name": "pip-warning-strip",
        "namespace": "build",
        "priority": 95,
        "action": "remove",
        "match_pattern": r"(?i)^WARNING: You are using pip version",
    },
    {
        "id": "seed-cargo-build",
        "name": "cargo-build-truncate",
        "namespace": "build",
        "priority": 75,
        "action": "truncate_tail",
        "match_pattern": r"(?i)Compiling\s+\w+",
        "truncate_lines": 50,
        "match_context": r"cargo\s+(build|check|test)",
    },

    # ── Python tracebacks ──
    {
        "id": "seed-traceback-compact",
        "name": "traceback-compact",
        "namespace": "error",
        "priority": 95,
        "action": "replace",
        "match_pattern": r"(?m)^Traceback\s+\(most recent call last\):",
        "replace_pattern": r"(File \"[^\"]+\", line \d+, in \w+\n(?:\s{2,}.*\n)*)(?=[^F])",
        "replace_with": "",
    },

    # ── Shell outputs ──
    {
        "id": "seed-dir-listing",
        "name": "dir-listing-truncate",
        "namespace": "shell",
        "priority": 60,
        "action": "truncate_tail",
        "match_pattern": r"(?m)^(d[rwx-]{9}|\s*\d{4}/\d{2}/\d{2})",
        "truncate_lines": 40,
        "match_context": r"(ls\s+-la|dir\b)",
    },
    {
        "id": "seed-empty-output",
        "name": "empty-output",
        "namespace": "shell",
        "priority": 100,
        "action": "replace",
        "match_pattern": r"^\s*$",
        "replace_pattern": r"^\s*$",
        "replace_with": "(no output)",
    },

    # ── Test outputs ──
    {
        "id": "seed-test-pass",
        "name": "test-pass-truncate",
        "namespace": "test",
        "priority": 85,
        "action": "truncate_tail",
        "match_pattern": r"(?mi)(passed|PASSED|OK|SUCCESS)",
        "truncate_lines": 20,
        "match_context": r"(pytest|unittest|jest|go test|cargo test)",
    },
    {
        "id": "seed-test-fail",
        "name": "test-fail-keep",
        "namespace": "test",
        "priority": 90,
        "action": "pass_through",
        "match_pattern": r"(?mi)(FAILED|ERROR|AssertionError|FAIL:|error:)",
        "match_context": r"(pytest|unittest|jest|go test|cargo test)",
    },
]


def seed_default_rules(pool: GlobalRulePool | None = None) -> GlobalRulePool:
    """Seed the pool with TACO default compression rules.

    Called on first use — only creates rules that don't already exist.
    Analytics: returns the pool (creates one if needed).
    """
    if pool is None:
        pool = get_global_rule_pool()

    for rule_data in TACO_SEED_RULES:
        rid = rule_data["id"]
        if rid not in pool._rules:
            rule = CompressionRule.from_dict(rule_data)
            pool._rules[rid] = rule
            pool._by_namespace.setdefault(
                rule.namespace, set()).add(rid)
    pool._save()
    logger.info(f"Seeded {len(TACO_SEED_RULES)} default compression rules")
    return pool


# ── Singleton ────────────────────────────────────────────────────────

_global_pool: GlobalRulePool | None = None


def get_global_rule_pool(seed: bool = True) -> GlobalRulePool:
    """Get or create the singleton GlobalRulePool.

    Auto-seeds with TACO default rules on first access (unless seed=False).
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = GlobalRulePool()
        if seed and len(_global_pool._rules) == 0:
            seed_default_rules(_global_pool)
    return _global_pool


def reset_global_rule_pool() -> None:
    """Test helper: reset the singleton. Not for production use."""
    global _global_pool
    _global_pool = None
