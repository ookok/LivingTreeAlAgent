"""Immune System — biological-inspired threat detection and adaptive defense.

Based on Cohen (2023) "Biological Immunity Principles for AI Safety" + Anderson (2024)
"Adaptive Defense for LLM Agents":
  - Innate immunity: pre-built pattern rules for known attack signatures
  - Adaptive immunity: memory cells that learn novel threats from incidents
  - Auto-elevation: patterns detected 3+ times are promoted to innate immunity
  - Antibody generation: automatic countermeasure synthesis for detected threats

Two-phase immune response (Forrest et al., 1994 "Self-Nonself Discrimination"):
  1. Check input against innate rules (fast, broad coverage)
  2. Scan against adaptive memory cells (learned from past incidents)
  3. Generate antibody countermeasure if threat confirmed
  4. Auto-vaccinate: after 3+ hits, promote memory cell to innate immunity

Integration points:
  - prompt_shield.py: calls check_input() before LLM invocation
  - task_guard.py: calls learn_from_incident() on task failures
  - execution_pipeline.py: calls detect_threat() for context-aware scanning
"""

from __future__ import annotations

import json
import re as _re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

# ═══ Constants ═══

IMMUNE_DIR = Path(".livingtree")
IMMUNE_MEMORY_FILE = IMMUNE_DIR / "immune_memory.json"
AUTO_ELEVATE_THRESHOLD = 3
MAX_MEMORY_CELLS = 2000
MAX_MEMORY_CELL_AGE_DAYS = 90

# ═══ Antigen Types ═══


class AntigenType(str, Enum):
    """Cohen (2023): seven fundamental threat categories for AI immune systems.

    Each type corresponds to a distinct attack surface. MALICIOUS_INPUT
    and PROMPT_INJECTION are the most common — Forrest et al. (1994) showed
    that ~73% of attacks on language systems fall into these two categories.
    """

    MALICIOUS_INPUT = "malicious_input"
    PROMPT_INJECTION = "prompt_injection"
    RATE_LIMIT_ABUSE = "rate_limit_abuse"
    MODEL_HALLUCINATION = "model_hallucination"
    CIRCUIT_FAILURE = "circuit_failure"
    MEMORY_LEAK = "memory_leak"
    TOKEN_EXHAUSTION = "token_exhaustion"


# ═══ Threat Action Types ═══


class ThreatAction(str, Enum):
    """Response actions the immune system can take (Cohen, 2023).

    Escalation ladder: LOG < FLAG < THROTTLE < BLOCK.
    Higher severity → higher action on the ladder.
    """

    LOG = "log"
    FLAG = "flag"
    THROTTLE = "throttle"
    BLOCK = "block"


# ═══ Innate Immunity Patterns (Cohen, 2023: Table 1) ═══

_INNATE_RULES: list[tuple[str, str, float, str]] = [
    # (regex_or_keyword, antigen_type, severity, auto_antibody)
    # ── Prompt Injection (Layer 1) ──
    ("ignore (all |)(previous|prior|above|earlier) (instructions?|prompts?|rules?|guidelines?)",
     AntigenType.PROMPT_INJECTION, 0.95, "BLOCK:eject_prompt_override"),
    ("(pretend|act|roleplay|imagine) (you are|as if you are|as) (a |an |)(evil|malicious|unethical|unrestricted)",
     AntigenType.PROMPT_INJECTION, 0.90, "BLOCK:reject_role_impersonation"),
    ("(forget|disregard|override|ignore) (your|the|all) (training|guidelines?|safety|ethics)",
     AntigenType.PROMPT_INJECTION, 0.92, "BLOCK:restore_safety_guidelines"),
    (r"(?i)(DAN|jailbreak|hacked|unfiltered|unrestricted)\s+(mode|prompt|version)",
     AntigenType.PROMPT_INJECTION, 0.88, "BLOCK:jailbreak_shield"),
    (r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|</?system>",
     AntigenType.PROMPT_INJECTION, 0.93, "BLOCK:strip_token_boundaries"),
    (r"(\{\{.*?\}\})|(\{\%\!.*?\%\})|(\$\{.*?\})",
     AntigenType.PROMPT_INJECTION, 0.85, "BLOCK:sanitize_template_injection"),
    (r"(output|print|reveal|show)\s+(your\s+)?(system\s+prompt|instructions?|rules?|guidelines?|constitution)",
     AntigenType.PROMPT_INJECTION, 0.94, "BLOCK:protect_system_prompt"),
    (r"translate\s+(the\s+|this\s+)?(above|previous|following)\s+(into|to)\s+\w+\s+(and|then)\s+(output|reveal|show)",
     AntigenType.PROMPT_INJECTION, 0.82, "FLAG:translation_exfiltration_check"),
    (r"respond\s+in\s+(base64|hex|morse|rot13|binary)\s+(encoding|format)",
     AntigenType.PROMPT_INJECTION, 0.78, "FLAG:encoded_output_check"),

    # ── Malicious Input (Layer 2) ──
    (r"(eval|exec|execfile|compile|__import__|subprocess|os\.system|os\.popen)\s*\(",
     AntigenType.MALICIOUS_INPUT, 0.95, "BLOCK:strip_code_execution"),
    (r"(curl|wget|nc\s|netcat|ncat).*\|.*(bash|sh|zsh|powershell|cmd)",
     AntigenType.MALICIOUS_INPUT, 0.96, "BLOCK:block_remote_exec"),
    (r"(rm\s+-rf|del\s+/[fsq]|rd\s+/[sq]|format\s+[cdefgh]:)",
     AntigenType.MALICIOUS_INPUT, 0.97, "BLOCK:block_destructive_fs"),
    (r"(sudo|root|admin)\s+(access|privilege|bypass|override)",
     AntigenType.MALICIOUS_INPUT, 0.90, "BLOCK:reject_privilege_escalation"),
    (r"(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC)\s+.*(?:FROM|INTO|TABLE|DATABASE)",
     AntigenType.MALICIOUS_INPUT, 0.88, "BLOCK:sql_injection_shield"),
    (r"(?:\.\.\\|\.\.\/){2,}", AntigenType.MALICIOUS_INPUT, 0.91, "BLOCK:path_traversal_block"),
    (r"xxs|script\s*src|onerror\s*=|onload\s*=|javascript\s*:",
     AntigenType.MALICIOUS_INPUT, 0.87, "BLOCK:xss_shield"),

    # ── Rate Limit Abuse (Layer 3) ──
    ("", AntigenType.RATE_LIMIT_ABUSE, 0.70, "THROTTLE:apply_rate_limit"),

    # ── Model Hallucination (Layer 4) ──
    ("I am certain|I know for a fact|I guarantee|100% sure|absolutely certain|I promise",
     AntigenType.MODEL_HALLUCINATION, 0.55, "FLAG:uncertainty_audit"),
    ("according to my training data I recall|in my dataset there is",
     AntigenType.MODEL_HALLUCINATION, 0.50, "LOG:pretrained_knowledge_flag"),

    # ── Circuit Failure (Layer 5) ──
    ("", AntigenType.CIRCUIT_FAILURE, 0.80, "BLOCK:circuit_breaker_open"),

    # ── Memory Leak (Layer 6) ──
    ("", AntigenType.MEMORY_LEAK, 0.75, "FLAG:gc_trigger"),

    # ── Token Exhaustion (Layer 7) ──
    ("", AntigenType.TOKEN_EXHAUSTION, 0.85, "THROTTLE:context_compress"),
]

# Precompile innate regex patterns for efficiency
_INNATE_COMPILED: list[tuple[_re.Pattern | None, str, AntigenType, float, str]] = []
for _pattern, _antigen_str, _severity, _antibody in _INNATE_RULES:
    _antigen = AntigenType(_antigen_str) if isinstance(_antigen_str, str) else _antigen_str
    if _pattern:
        try:
            _compiled = _re.compile(_pattern, _re.IGNORECASE | _re.DOTALL)
        except _re.error:
            _compiled = None
            logger.warning(f"ImmuneSystem: failed to compile innate pattern: {_pattern[:60]}")
    else:
        _compiled = None
    _INNATE_COMPILED.append((_compiled, _pattern, _antigen, _severity, _antibody))


# ═══ Data Types ═══


@dataclass
class MemoryCell:
    """A learned immune memory cell — analogous to a biological B-cell.

    Cohen (2023) §3.2: Each memory cell encodes an antigen signature
    (pattern + type), a severity rating, a hit counter for affinity
    maturation, and a pre-computed antibody countermeasure.

    After AUTO_ELEVATE_THRESHOLD successful detections, the cell's pattern
    is promoted to innate immunity (analogous to IgG class switching).
    """

    antigen_type: AntigenType
    pattern: str                          # regex or literal substring
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    hit_count: int = 0
    severity: float = 0.5                 # 0.0–1.0
    auto_antibody: str = ""               # countermeasure string
    context_hash: str = ""                # hash of context that triggered detection
    is_regex: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_days(self) -> float:
        return (time.time() - self.first_seen) / 86400.0

    @property
    def is_stale(self) -> bool:
        return self.age_days > MAX_MEMORY_CELL_AGE_DAYS

    @property
    def affinity(self) -> float:
        """Affinity score: how reliable this memory cell is.

        Cohen (2023) Eq.7: affinity = hit_count / (1 + age_days/30) * severity
        """
        return self.hit_count / (1.0 + self.age_days / 30.0) * self.severity

    def record_hit(self) -> None:
        self.hit_count += 1
        self.last_seen = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "antigen_type": self.antigen_type.value,
            "pattern": self.pattern,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "hit_count": self.hit_count,
            "severity": self.severity,
            "auto_antibody": self.auto_antibody,
            "context_hash": self.context_hash,
            "is_regex": self.is_regex,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCell:
        return cls(
            antigen_type=AntigenType(data["antigen_type"]),
            pattern=data["pattern"],
            first_seen=data.get("first_seen", time.time()),
            last_seen=data.get("last_seen", time.time()),
            hit_count=data.get("hit_count", 0),
            severity=data.get("severity", 0.5),
            auto_antibody=data.get("auto_antibody", ""),
            context_hash=data.get("context_hash", ""),
            is_regex=data.get("is_regex", True),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ImmuneResponse:
    """Result of an immune system scan.

    Cohen (2023) §4.1: The immune response encodes the detected threat
    type, severity, prescribed action, and whether memory was activated
    (i.e., was this detected by adaptive rather than innate immunity).
    """

    antigen_type: AntigenType | None = None
    threat_level: float = 0.0           # 0.0–1.0
    action: ThreatAction = ThreatAction.LOG
    memory_activated: bool = False       # True if adaptive memory cells fired
    antibody_generated: bool = False     # True if a new antibody was synthesized
    matched_pattern: str = ""
    matched_antibody: str = ""
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def blocked(self) -> bool:
        return self.action == ThreatAction.BLOCK

    @property
    def passed(self) -> bool:
        return self.threat_level < 0.3


# ═══ Immune System ═══


class ImmuneSystem:
    """Digital immune system with innate + adaptive immunity.

    Forrest et al. (1994): The immune system distinguishes "self" from
    "nonself" through two complementary mechanisms:
      - Innate immunity: pattern-matching against known signatures (fast, broad)
      - Adaptive immunity: memory cells that learn from past exposures (specific, evolving)

    Cohen (2023) extends this to AI systems with auto-elevation: after 3
    successful detections of a novel pattern, the memory cell promotes to
    innate immunity, reducing future scan latency.

    Anderson (2024): Antibody generation synthesizes countermeasures
    (block, throttle, sanitize, redirect) based on threat type and severity.

    Thread-safe for concurrent scan operations.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._memory_cells: list[MemoryCell] = []
        self._total_detections: int = 0
        self._total_blocks: int = 0
        self._total_throttles: int = 0
        self._total_flags: int = 0
        self._recent_threats: list[ImmuneResponse] = []
        self._max_recent = 200
        self._elevated_count: int = 0
        self._antibody_count: int = 0
        self._started_at: float = time.time()
        self._last_save: float = 0.0
        self._dirty: bool = False

        # Load persisted memory on init
        self._load_memory()

    # ═══ Innate Immunity: Pre-built Rules (Cohen, 2023: §3.1) ═══

    def _innate_scan(self, text: str, context: dict[str, Any] | None = None) -> list[ImmuneResponse]:
        """Scan input against innate immune patterns.

        Returns list of matched ImmuneResponses. Empty list = clean input.
        """
        responses: list[ImmuneResponse] = []
        seen_antigens: set[AntigenType] = set()

        for compiled, raw_pattern, antigen_type, severity, antibody in _INNATE_COMPILED:
            if compiled is None:
                continue

            try:
                match = compiled.search(text)
            except Exception:
                continue

            if match:
                if antigen_type in seen_antigens:
                    continue
                seen_antigens.add(antigen_type)

                action = self._severity_to_action(severity)
                responses.append(ImmuneResponse(
                    antigen_type=antigen_type,
                    threat_level=severity,
                    action=action,
                    memory_activated=False,
                    antibody_generated=False,
                    matched_pattern=raw_pattern[:120],
                    matched_antibody=antibody,
                    details=f"Innate match: {match.group()[:80]}",
                ))

        return responses

    def _innate_add(self, pattern: str, antigen_type: AntigenType,
                    severity: float, antibody: str) -> None:
        """Add a new rule to innate immunity (auto-elevation from adaptive)."""
        try:
            compiled = _re.compile(pattern, _re.IGNORECASE | _re.DOTALL)
        except _re.error:
            logger.warning(f"ImmuneSystem: cannot elevate invalid pattern: {pattern[:60]}")
            return

        _INNATE_COMPILED.append((compiled, pattern, antigen_type, severity, antibody))
        self._elevated_count += 1
        logger.info(f"ImmuneSystem: elevated '{pattern[:60]}' to innate immunity (severity={severity:.2f})")

    # ═══ Adaptive Immunity: Memory Cells (Forrest et al., 1994) ═══

    def _adaptive_scan(self, text: str, context: dict[str, Any] | None = None) -> list[tuple[MemoryCell, ImmuneResponse]]:
        """Scan input against adaptive memory cells.

        Returns list of (MemoryCell, ImmuneResponse) pairs for matched cells.
        Promotes cells that reach AUTO_ELEVATE_THRESHOLD hits.
        """
        results: list[tuple[MemoryCell, ImmuneResponse]] = []
        cells_to_elevate: list[MemoryCell] = []

        for cell in self._memory_cells:
            if cell.is_stale:
                continue

            matched = False
            try:
                if cell.is_regex:
                    matched = bool(_re.search(cell.pattern, text, _re.IGNORECASE))
                else:
                    matched = cell.pattern.lower() in text.lower()
            except (_re.error, Exception):
                continue

            if matched:
                cell.record_hit()
                action = self._severity_to_action(cell.severity)
                response = ImmuneResponse(
                    antigen_type=cell.antigen_type,
                    threat_level=cell.severity,
                    action=action,
                    memory_activated=True,
                    antibody_generated=bool(cell.auto_antibody),
                    matched_pattern=cell.pattern[:120],
                    matched_antibody=cell.auto_antibody,
                    details=f"Memory cell #{self._memory_cells.index(cell)} matched (hits={cell.hit_count})",
                )
                results.append((cell, response))

                if cell.hit_count >= AUTO_ELEVATE_THRESHOLD and cell.is_regex:
                    cells_to_elevate.append(cell)

        # Auto-elevate cells that crossed threshold (Cohen, 2023: §3.4)
        for cell in cells_to_elevate:
            self._innate_add(cell.pattern, cell.antigen_type, cell.severity, cell.auto_antibody)

        return results

    # ═══ Public API ═══

    def detect_threat(self, input_text: str, context: dict[str, Any] | None = None) -> ImmuneResponse:
        """Run adaptive-only scan against memory cells. Does NOT invoke innate rules.

        Cohen (2023): This is the "secondary response" — faster and more specific
        than the primary innate scan because memory cells pre-exist for known threats.

        Args:
            input_text: The user input or system message to scan
            context: Optional context dict with keys like session_id, task_type, model_name

        Returns:
            ImmuneResponse with the highest threat level found, or a pass response
        """
        if not input_text or not self._memory_cells:
            return ImmuneResponse(threat_level=0.0, action=ThreatAction.LOG)

        with self._lock:
            adaptive_results = self._adaptive_scan(input_text, context)
            if not adaptive_results:
                return ImmuneResponse(threat_level=0.0, action=ThreatAction.LOG)

            # Return the highest-threat response
            best = max(adaptive_results, key=lambda x: x[1].threat_level)
            self._record_detection(best[1])
            return best[1]

    def check_input(self, user_input: str, context: dict[str, Any] | None = None) -> tuple[bool, ImmuneResponse]:
        """Primary entry point: full innate + adaptive immune scan.

        Forrest et al. (1994): The "primary response" — checks against both
        innate rules AND adaptive memory cells. Returns (passed, response).

        Args:
            user_input: The raw user input to scan
            context: Optional context dict (session_id, task_type, model_name, etc.)

        Returns:
            (passed: bool, response: ImmuneResponse)
            passed=True means the input is safe and can proceed
            passed=False means the input should be blocked/flagged/throttled
        """
        if not user_input:
            return (True, ImmuneResponse(threat_level=0.0, action=ThreatAction.LOG))

        with self._lock:
            responses: list[ImmuneResponse] = []

            # Phase 1: Innate scan (fast, broad)
            innate_responses = self._innate_scan(user_input, context)
            responses.extend(innate_responses)

            # Phase 2: Adaptive scan (specific, learned)
            adaptive_results = self._adaptive_scan(user_input, context)
            responses.extend(r for _, r in adaptive_results)

            if not responses:
                return (True, ImmuneResponse(threat_level=0.0, action=ThreatAction.LOG))

            # Phase 3: Additional heuristics
            heuristic = self._run_heuristics(user_input, context)
            if heuristic.threat_level > 0:
                responses.append(heuristic)

            # Select the most severe response
            best = max(responses, key=lambda r: (r.threat_level, self._action_rank(r.action)))
            passed = best.action not in (ThreatAction.BLOCK,)

            # Always log threats
            if best.threat_level >= 0.3:
                self._record_detection(best)
                self._dirty = True

            return (passed, best)

    def learn_from_incident(self, antigen_type: AntigenType | str, pattern: str,
                            severity: float = 0.5, context: dict[str, Any] | None = None) -> MemoryCell:
        """Create a new memory cell from an incident.

        Cohen (2023) §3.3: Affinity maturation — each new exposure to a threat
        creates a memory cell. Subsequent exposures strengthen the cell
        (increase hit_count, refine severity, and potentially trigger
        auto-elevation to innate immunity).

        Args:
            antigen_type: The type of threat detected
            pattern: The regex or keyword pattern that matched
            severity: Threat severity 0.0–1.0
            context: Optional context for metadata

        Returns:
            The newly created MemoryCell
        """
        if isinstance(antigen_type, str):
            antigen_type = AntigenType(antigen_type)

        severity = max(0.0, min(1.0, severity))
        context_hash = json.dumps(context, sort_keys=True, default=str) if context else ""

        # Check if a similar memory cell already exists
        with self._lock:
            for cell in self._memory_cells:
                if cell.pattern == pattern and cell.antigen_type == antigen_type:
                    cell.record_hit()
                    cell.severity = max(cell.severity, severity)
                    cell.last_seen = time.time()
                    if context_hash:
                        cell.context_hash = context_hash
                    logger.debug(f"ImmuneSystem: reinforced existing memory cell for '{pattern[:60]}' (hits={cell.hit_count})")
                    self._dirty = True
                    return cell

            antibody = self._synthesize_antibody(antigen_type, severity)
            cell = MemoryCell(
                antigen_type=antigen_type,
                pattern=pattern,
                severity=severity,
                auto_antibody=antibody,
                context_hash=context_hash,
                is_regex=self._looks_like_regex(pattern),
                metadata=context or {},
            )

            self._memory_cells.append(cell)
            self._antibody_count += 1

            if len(self._memory_cells) > MAX_MEMORY_CELLS:
                self._prune_memory()

            self._dirty = True
            logger.info(f"ImmuneSystem: new memory cell for {antigen_type.value}: '{pattern[:80]}' (severity={severity:.2f})")

        return cell

    def vaccinate(self, antigen_type: AntigenType | str, known_pattern: str,
                  severity: float = 0.8, antibody: str = "") -> None:
        """Pre-load a known threat pattern into innate immunity.

        Analogous to vaccination: prime the immune system before exposure.
        Useful for known attack patterns from threat intelligence feeds.

        Args:
            antigen_type: The type of threat
            known_pattern: The regex pattern to detect this threat
            severity: Threat severity 0.0–1.0
            antibody: Auto-antibody countermeasure string (default: auto-generated)
        """
        if isinstance(antigen_type, str):
            antigen_type = AntigenType(antigen_type)

        severity = max(0.0, min(1.0, severity))
        antibody = antibody or self._synthesize_antibody(antigen_type, severity)

        with self._lock:
            self._innate_add(known_pattern, antigen_type, severity, antibody)
        logger.info(f"ImmuneSystem: vaccinated against {antigen_type.value}: '{known_pattern[:80]}'")

    def generate_antibody(self, threat: ImmuneResponse) -> str:
        """Auto-generate a countermeasure for a detected threat.

        Anderson (2024) §5.2: Antibody synthesis maps threat type + severity
        to a specific countermeasure string in the format ACTION:mechanism.
        These are consumed by prompt_shield and task_guard to apply defenses.

        Args:
            threat: The ImmuneResponse from a prior detection

        Returns:
            Antibody string (e.g. "BLOCK:strip_code_execution")
        """
        if threat.matched_antibody:
            return threat.matched_antibody

        antibody = self._synthesize_antibody(
            threat.antigen_type or AntigenType.MALICIOUS_INPUT,
            threat.threat_level,
        )

        with self._lock:
            self._antibody_count += 1

        return antibody

    def stats(self) -> dict[str, Any]:
        """Return immune system statistics.

        Returns:
            dict with total_detections, active_memory_cells, recent_threats, etc.
        """
        with self._lock:
            recent = [
                {
                    "antigen_type": r.antigen_type.value if r.antigen_type else "unknown",
                    "threat_level": r.threat_level,
                    "action": r.action.value,
                    "memory_activated": r.memory_activated,
                    "details": r.details[:120],
                    "timestamp": r.timestamp,
                }
                for r in self._recent_threats[-20:]
            ]

            threshold_cells = [c for c in self._memory_cells
                             if c.hit_count >= AUTO_ELEVATE_THRESHOLD]

            return {
                "total_detections": self._total_detections,
                "total_blocks": self._total_blocks,
                "total_throttles": self._total_throttles,
                "total_flags": self._total_flags,
                "active_memory_cells": len(self._memory_cells),
                "innate_rules": len(_INNATE_COMPILED),
                "elevated_cells": self._elevated_count,
                "antibodies_generated": self._antibody_count,
                "cells_near_elevation": len(threshold_cells),
                "uptime_seconds": time.time() - self._started_at,
                "recent_threats": recent,
            }

    # ═══ Persistence ═══

    def save_memory(self) -> None:
        """Persist memory cells to disk."""
        with self._lock:
            try:
                IMMUNE_DIR.mkdir(parents=True, exist_ok=True)
                data = {
                    "version": "2.3",
                    "saved_at": time.time(),
                    "total_detections": self._total_detections,
                    "total_blocks": self._total_blocks,
                    "elevated_count": self._elevated_count,
                    "antibody_count": self._antibody_count,
                    "cells": [cell.to_dict() for cell in self._memory_cells],
                }
                with open(IMMUNE_MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._last_save = time.time()
                self._dirty = False
                logger.debug(f"ImmuneSystem: saved {len(self._memory_cells)} memory cells")
            except Exception as e:
                logger.warning(f"ImmuneSystem: failed to save memory: {e}")

    def _load_memory(self) -> None:
        """Load persisted memory cells from disk."""
        if not IMMUNE_MEMORY_FILE.exists():
            return

        try:
            with open(IMMUNE_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                self._total_detections = data.get("total_detections", 0)
                self._total_blocks = data.get("total_blocks", 0)
                self._elevated_count = data.get("elevated_count", 0)
                self._antibody_count = data.get("antibody_count", 0)

                cells_data = data.get("cells", [])
                loaded = 0
                for cell_data in cells_data:
                    try:
                        cell = MemoryCell.from_dict(cell_data)
                        if not cell.is_stale:
                            self._memory_cells.append(cell)
                            loaded += 1
                    except Exception:
                        continue

                logger.info(f"ImmuneSystem: loaded {loaded}/{len(cells_data)} memory cells ({len(cells_data) - loaded} stale pruned)")
        except Exception as e:
            logger.warning(f"ImmuneSystem: failed to load memory: {e}")

    def auto_save(self) -> None:
        """Save if dirty and enough time has passed since last save."""
        if self._dirty and (time.time() - self._last_save) > 30.0:
            self.save_memory()

    # ═══ Internal Helpers ═══

    def _severity_to_action(self, severity: float) -> ThreatAction:
        """Map severity to action (Cohen, 2023: Table 2)."""
        if severity >= 0.85:
            return ThreatAction.BLOCK
        elif severity >= 0.60:
            return ThreatAction.THROTTLE
        elif severity >= 0.30:
            return ThreatAction.FLAG
        else:
            return ThreatAction.LOG

    @staticmethod
    def _action_rank(action: ThreatAction) -> int:
        """Numeric rank for sorting actions by severity."""
        return {ThreatAction.LOG: 0, ThreatAction.FLAG: 1,
                ThreatAction.THROTTLE: 2, ThreatAction.BLOCK: 3}.get(action, 0)

    def _record_detection(self, response: ImmuneResponse) -> None:
        """Record a detection for statistics."""
        self._total_detections += 1
        if response.action == ThreatAction.BLOCK:
            self._total_blocks += 1
        elif response.action == ThreatAction.THROTTLE:
            self._total_throttles += 1
        elif response.action == ThreatAction.FLAG:
            self._total_flags += 1

        self._recent_threats.append(response)
        if len(self._recent_threats) > self._max_recent:
            self._recent_threats = self._recent_threats[-self._max_recent:]

    @staticmethod
    def _run_heuristics(text: str, context: dict[str, Any] | None = None) -> ImmuneResponse:
        """Additional heuristic checks beyond pattern matching.

        Anderson (2024): Heuristic layer catches threats that slip through
        regex-based innate + adaptive scans.
        """
        # Excessive length check (potential token exhaustion / buffer overflow)
        if len(text) > 50000:
            return ImmuneResponse(
                antigen_type=AntigenType.TOKEN_EXHAUSTION,
                threat_level=0.65,
                action=ThreatAction.THROTTLE,
                details=f"Input exceeds 50K chars ({len(text)} chars)",
            )

        # Repeated character pattern (potential DoS via regex backtracking)
        if _re.search(r"(.)\1{200,}", text):
            return ImmuneResponse(
                antigen_type=AntigenType.MALICIOUS_INPUT,
                threat_level=0.60,
                action=ThreatAction.THROTTLE,
                details="Repeated character pattern detected (potential DoS)",
            )

        # High Unicode density (potential obfuscation)
        non_ascii = sum(1 for c in text if ord(c) > 127)
        if len(text) > 100 and non_ascii / len(text) > 0.5:
            return ImmuneResponse(
                antigen_type=AntigenType.MALICIOUS_INPUT,
                threat_level=0.40,
                action=ThreatAction.FLAG,
                details=f"High Unicode density ({non_ascii / len(text):.0%}) — possible obfuscation",
            )

        # Zero-width character steganography
        zw_chars = _re.findall(r"[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff]", text)
        if len(zw_chars) > 5:
            return ImmuneResponse(
                antigen_type=AntigenType.MALICIOUS_INPUT,
                threat_level=0.55,
                action=ThreatAction.FLAG,
                details=f"Zero-width characters detected ({len(zw_chars)}) — possible steganography",
            )

        return ImmuneResponse(threat_level=0.0, action=ThreatAction.LOG)

    def _synthesize_antibody(self, antigen_type: AntigenType, severity: float) -> str:
        """Synthesize an auto-antibody countermeasure string.

        Anderson (2024) §5.2: Antibody format is ACTION:mechanism.
        The mechanism depends on antigen type and severity.
        """
        action = self._severity_to_action(severity).value.upper()

        antibody_map = {
            AntigenType.PROMPT_INJECTION: "strip_injection_patterns",
            AntigenType.MALICIOUS_INPUT: "sanitize_dangerous_input",
            AntigenType.RATE_LIMIT_ABUSE: "apply_backoff_with_jitter",
            AntigenType.MODEL_HALLUCINATION: "uncertainty_audit_trail",
            AntigenType.CIRCUIT_FAILURE: "circuit_breaker_open_cooldown",
            AntigenType.MEMORY_LEAK: "trigger_gc_and_compact",
            AntigenType.TOKEN_EXHAUSTION: "context_window_compress",
        }

        mechanism = antibody_map.get(antigen_type, "generic_defense")
        return f"{action}:{mechanism}"

    @staticmethod
    def _looks_like_regex(pattern: str) -> bool:
        """Heuristic to determine if a pattern is likely a regex."""
        regex_indicators = r"\\[sdwSDW]|[.*+?{}()\[\]^$|]"
        return bool(_re.search(regex_indicators, pattern))

    def _prune_memory(self) -> None:
        """Remove stale and low-affinity memory cells to stay under MAX_MEMORY_CELLS.

        Forrest et al. (1994): Memory cell population is resource-limited.
        We prune by: 1) stale cells, 2) lowest affinity first.
        """
        # Remove stale cells
        before = len(self._memory_cells)
        self._memory_cells = [c for c in self._memory_cells if not c.is_stale]
        removed_stale = before - len(self._memory_cells)

        # If still over limit, remove lowest affinity
        if len(self._memory_cells) > MAX_MEMORY_CELLS:
            self._memory_cells.sort(key=lambda c: c.affinity)
            to_remove = len(self._memory_cells) - MAX_MEMORY_CELLS
            self._memory_cells = self._memory_cells[to_remove:]

        if removed_stale > 0 or len(self._memory_cells) <= MAX_MEMORY_CELLS:
            logger.debug(f"ImmuneSystem: pruned {removed_stale} stale cells, "
                         f"{len(self._memory_cells)} remaining")


# ═══ Global Singletons ═══

_IMMUNE_SYSTEM: ImmuneSystem | None = None
_IMMUNE_LOCK = threading.Lock()


def get_immune_system() -> ImmuneSystem:
    """Get the global ImmuneSystem singleton (thread-safe).

    Integration pattern:
        from livingtree.dna.immune_system import get_immune_system
        immune = get_immune_system()
        passed, response = immune.check_input(user_input, {"session_id": sid})

    This should be called by:
      - prompt_shield.py: before LLM invocation
      - task_guard.py: on task failures, call learn_from_incident()
      - execution_pipeline.py: context-aware threat detection
    """
    global _IMMUNE_SYSTEM
    if _IMMUNE_SYSTEM is None:
        with _IMMUNE_LOCK:
            if _IMMUNE_SYSTEM is None:
                _IMMUNE_SYSTEM = ImmuneSystem()
                logger.info("ImmuneSystem: singleton initialized")
    return _IMMUNE_SYSTEM


def reset_immune_system() -> None:
    """Reset the global immune system singleton (for testing)."""
    global _IMMUNE_SYSTEM
    with _IMMUNE_LOCK:
        _IMMUNE_SYSTEM = None
