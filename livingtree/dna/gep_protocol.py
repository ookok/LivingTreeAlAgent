"""GEP (Genome Evolution Protocol) — Protocol-constrained evolution with structured, auditable assets.

Based on Evolver's auditable evolution framework (EvoMap/evolver, 7.4k stars).
Provides Genes, Capsules, and EvolutionEvents for reproducible self-evolution.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


_VALID_COMMAND_PREFIXES = {"node", "npm", "npx"}
_VALID_STRATEGIES = {"balanced", "innovate", "harden", "repair-only"}
_VALID_EVENT_TYPES = {
    "gene_created", "gene_evolved", "gene_applied", "gene_retired",
    "mutation_proposed", "mutation_applied", "mutation_rolled_back",
}

_SUB_PATTERNS = [
    re.compile(r"\$\(.*\)"),
    re.compile(r"`[^`]*`"),
]
_OPERATOR_PATTERN = re.compile(r"[;&|><]")


def _strip_quoted(text: str) -> str:
    """Remove single-quoted and double-quoted substrings from a command string."""
    result: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double:
            result.append(ch)
        i += 1
    return "".join(result)


@dataclass
class EvolutionEvent:
    """A single auditable evolution event in the GEP audit trail."""

    event_id: str
    event_type: str
    gene_id: str | None
    before_state: dict | None
    after_state: dict | None
    delta_description: str
    success: bool | None = None
    strategy: str = "balanced"
    timestamp: float = field(default_factory=time.time)
    validated: bool = False

    def to_jsonl(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "gene_id": self.gene_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "delta_description": self.delta_description,
            "success": self.success,
            "strategy": self.strategy,
            "timestamp": self.timestamp,
            "validated": self.validated,
        }, ensure_ascii=False) + "\n"

    def summary(self) -> str:
        status = "PENDING" if self.success is None else ("PASS" if self.success else "FAIL")
        return f"[{status}] {self.event_type} gene={self.gene_id} {self.delta_description}"


class GEPProtocol:
    """Genome Evolution Protocol — auditable, protocol-constrained self-evolution.

    Tracks every gene creation, mutation, and evolution event in a structured
    JSONL audit trail. Supports strategy presets from Evolver:
    balanced / innovate / harden / repair-only.
    """

    _DEFAULT_LOG_DIR = ".livingtree"
    _LOG_FILENAME = "evolution_events.jsonl"
    _MAX_BUFFER = 1000
    _LOAD_TAIL = 200

    def __init__(self, event_log_dir: str | Path | None = None):
        base = Path(event_log_dir) if event_log_dir else Path(self._DEFAULT_LOG_DIR)
        self._event_log_path = base / self._LOG_FILENAME
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[EvolutionEvent] = []
        self._strategy: str = "balanced"
        self._gene_pool: Any = None
        self._load()

    # ── Recording ───────────────────────────────────────────────────────

    def record_event(
        self,
        event_type: str,
        gene_id: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        delta: str = "",
        success: bool | None = None,
        strategy: str | None = None,
    ) -> EvolutionEvent:
        if event_type not in _VALID_EVENT_TYPES:
            logger.warning(f"GEP: unknown event_type '{event_type}', proceeding as-is")

        strat = strategy or self._strategy
        if strat not in _VALID_STRATEGIES:
            logger.warning(f"GEP: unknown strategy '{strat}', falling back to balanced")
            strat = "balanced"

        event = EvolutionEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            gene_id=gene_id,
            before_state=before,
            after_state=after,
            delta_description=delta,
            success=success,
            strategy=strat,
        )
        self._events.append(event)
        self._persist(event)
        logger.info(event.summary())
        return event

    def _persist(self, event: EvolutionEvent) -> None:
        try:
            with open(self._event_log_path, "a", encoding="utf-8") as f:
                f.write(event.to_jsonl())
        except Exception as e:
            logger.error(f"GEP: persist failed for {event.event_id}: {e}")

        if len(self._events) > self._MAX_BUFFER:
            self._events = self._events[-self._MAX_BUFFER // 2:]

    # ── Query ────────────────────────────────────────────────────────────

    def get_audit_trail(
        self, gene_id: str | None = None, limit: int = 50
    ) -> list[EvolutionEvent]:
        if gene_id:
            filtered = [e for e in self._events if e.gene_id == gene_id]
            return filtered[-limit:]
        return self._events[-limit:]

    def get_pending_events(self) -> list[EvolutionEvent]:
        return [e for e in self._events if e.success is None]

    def get_recent_failures(self, limit: int = 20) -> list[EvolutionEvent]:
        return [e for e in self._events if e.success is False][-limit:]

    def mark_event_success(
        self, event_id: str, success: bool = True, validated: bool = True
    ) -> bool:
        for e in self._events:
            if e.event_id == event_id:
                e.success = success
                e.validated = validated
                return True
        return False

    # ── Validation ───────────────────────────────────────────────────────

    def validate_gene(
        self, gene: Any, working_dir: str | Path = "."
    ) -> tuple[bool, str]:
        """Run gene.validation_cmd (if any) inside working_dir with safety checks.

        Safety constraints:
        - Only node/npm/npx prefix allowed
        - No command substitution ($( ), backticks)
        - No shell operators (;, &, |, >, <) after quote stripping
        - 180 s timeout

        Returns (passed: bool, output: str).
        """
        cmd = (
            getattr(gene, "validation_cmd", None)
            or getattr(gene, "test_cmd", None)
            or getattr(gene, "verify_cmd", None)
        )
        if not cmd or not isinstance(cmd, str) or not cmd.strip():
            return True, "no validation command"

        cmd = cmd.strip()

        first_token = cmd.split()[0].lower() if cmd else ""
        allowed = False
        for prefix in _VALID_COMMAND_PREFIXES:
            if first_token in (prefix, f"{prefix}.cmd", f"{prefix}.exe"):
                allowed = True
                break
        if not allowed:
            return False, f"blocked: command prefix '{first_token}' not in {_VALID_COMMAND_PREFIXES}"

        bare = _strip_quoted(cmd)

        for pat in _SUB_PATTERNS:
            if pat.search(bare):
                return False, f"blocked: substitution pattern '{pat.pattern}' in command"

        if _OPERATOR_PATTERN.search(bare):
            return False, "blocked: shell operator (;, &, |, >, <) found after quote stripping"

        wd = Path(working_dir)
        if not wd.exists():
            return False, f"working_dir does not exist: {wd}"

        logger.info(f"GEP: validating gene {getattr(gene, 'gene_id', '?')}: {cmd[:100]}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(wd),
                capture_output=True,
                text=True,
                timeout=180,
                env={**os.environ, "GEP_VALIDATING": "1"},
            )
            passed = result.returncode == 0
            output = (
                result.stdout.strip()[:2000]
                or result.stderr.strip()[:2000]
                or "(no output)"
            )
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "timeout: validation exceeded 180s"
        except Exception as e:
            return False, f"exception: {e}"

    # ── Strategy ─────────────────────────────────────────────────────────

    def set_strategy(self, strategy_name: str) -> None:
        if strategy_name not in _VALID_STRATEGIES:
            logger.warning(f"GEP: unknown strategy '{strategy_name}', keeping '{self._strategy}'")
            return
        self._strategy = strategy_name
        logger.info(f"GEP: strategy set to '{strategy_name}'")

    def get_strategy_weights(self) -> dict[str, float]:
        presets: dict[str, dict[str, float]] = {
            "balanced":    {"innovate": 0.5, "optimize": 0.3, "repair": 0.2},
            "innovate":    {"innovate": 0.8, "optimize": 0.15, "repair": 0.05},
            "harden":      {"innovate": 0.2, "optimize": 0.4, "repair": 0.4},
            "repair-only": {"innovate": 0.0, "optimize": 0.2, "repair": 0.8},
        }
        return presets.get(self._strategy, presets["balanced"])

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        total = len(self._events)
        events_by_type: dict[str, int] = {}
        validated_count = 0
        passed_count = 0
        for e in self._events:
            events_by_type[e.event_type] = events_by_type.get(e.event_type, 0) + 1
            if e.validated:
                validated_count += 1
                if e.success:
                    passed_count += 1
        pass_rate = (passed_count / validated_count) if validated_count > 0 else 0.0
        return {
            "total_events": total,
            "events_by_type": events_by_type,
            "validation_pass_rate": round(pass_rate, 3),
            "current_strategy": self._strategy,
        }

    # ── Export ───────────────────────────────────────────────────────────

    def export_audit(self, before_date: float | None = None) -> str:
        if not self._event_log_path.exists():
            return ""
        try:
            with open(self._event_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"GEP: export failed to read audit log: {e}")
            return ""

        if before_date is None:
            return "".join(lines)

        filtered: list[str] = []
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("timestamp", 0) < before_date:
                    filtered.append(line)
            except json.JSONDecodeError:
                filtered.append(line)
        return "".join(filtered)

    # ── Persistence ──────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._event_log_path.exists():
            return
        try:
            with open(self._event_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"GEP: failed to load audit log: {e}")
            return

        for line in lines[-self._LOAD_TAIL:]:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                self._events.append(EvolutionEvent(
                    event_id=data.get("event_id", ""),
                    event_type=data.get("event_type", ""),
                    gene_id=data.get("gene_id"),
                    before_state=data.get("before_state"),
                    after_state=data.get("after_state"),
                    delta_description=data.get("delta_description", ""),
                    success=data.get("success"),
                    strategy=data.get("strategy", "balanced"),
                    timestamp=data.get("timestamp", time.time()),
                    validated=data.get("validated", False),
                ))
            except Exception:
                pass


# ── Singleton ────────────────────────────────────────────────────────────

_GEP_INSTANCE: GEPProtocol | None = None


def get_gep_protocol(event_log_dir: str | Path | None = None) -> GEPProtocol:
    global _GEP_INSTANCE
    if _GEP_INSTANCE is None:
        _GEP_INSTANCE = GEPProtocol(event_log_dir=event_log_dir)
    return _GEP_INSTANCE
