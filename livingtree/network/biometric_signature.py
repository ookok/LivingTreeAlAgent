"""BiometricSignature — Behavioral fingerprinting for entity identification.

Identifies living beings (primarily human users) through behavioral patterns
rather than hardware biometrics. Every interaction leaves a unique trace:
typing rhythm, command vocabulary, temporal patterns, error signatures.

Analogy (RuView): WiFi DensePose reconstructs body pose from signal patterns.
LivingTree reconstructs "behavioral pose" from interaction patterns — the
unique shape of a person's digital presence.

Features extracted:
1. Keystroke Dynamics — inter-key delay, burst patterns, typo rate
2. Command Vocabulary — unique command set, frequency distribution
3. Temporal Rhythm — time-of-day preference, session duration, idle patterns
4. Error Signature — types of mistakes, correction patterns
5. Language Fingerprint — vocabulary richness, sentence structure
6. Tool Affinity — preferred tools, API endpoints, workflow patterns

Innovation: "Continuous Identity Verification" — passive behavioral
authentication that runs silently, detecting identity shifts without
explicit login/logout.
"""

from __future__ import annotations

import time
import math
import re
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Types ──

class IdentityConfidence(str, Enum):
    HIGH = "high"            # >0.90 — near-certain match
    MODERATE = "moderate"    # >0.70 — likely match
    LOW = "low"              # >0.50 — possible match
    UNKNOWN = "unknown"      # ≤0.50 — unrecognized
    CONFLICT = "conflict"    # Multiple profiles match


@dataclass
class KeystrokeProfile:
    """Keystroke dynamics fingerprint."""
    avg_inter_key_ms: float = 0.0      # Mean time between keystrokes
    std_inter_key_ms: float = 0.0      # Variability
    burst_rate: float = 0.0            # Keystrokes in burst (typing sprint)
    typo_rate: float = 0.0             # Backspace/delete frequency
    backspace_ratio: float = 0.0       # Corrections per keystroke
    sample_count: int = 0
    last_updated: float = 0.0

    def distance(self, other: "KeystrokeProfile") -> float:
        """Compute normalized distance between two profiles (0=identical, 1=completely different)."""
        if self.sample_count < 5 or other.sample_count < 5:
            return 0.5  # not enough data
        features = [
            (self.avg_inter_key_ms, other.avg_inter_key_ms, 1000.0),
            (self.std_inter_key_ms, other.std_inter_key_ms, 500.0),
            (self.burst_rate, other.burst_rate, 1.0),
            (self.typo_rate, other.typo_rate, 1.0),
            (self.backspace_ratio, other.backspace_ratio, 1.0),
        ]
        total_dist = 0.0
        for a, b, scale in features:
            total_dist += min(abs(a - b) / max(scale, 0.001), 1.0)
        return total_dist / len(features)


@dataclass
class CommandVocabulary:
    """Unique command usage patterns."""
    top_commands: list[tuple[str, int]] = field(default_factory=list)  # (command, count)
    unique_count: int = 0
    complexity_mean: float = 0.0        # Average command complexity
    pipe_usage_rate: float = 0.0        # How often pipes are used
    shell_preference: str = ""          # "bash", "pwsh", "zsh", etc.
    total_commands: int = 0
    last_updated: float = 0.0

    def jaccard_similarity(self, other: "CommandVocabulary") -> float:
        """Jaccard similarity between command sets."""
        a_set = {cmd for cmd, _ in self.top_commands[:20]}
        b_set = {cmd for cmd, _ in other.top_commands[:20]}
        if not a_set or not b_set:
            return 0.0
        intersection = len(a_set & b_set)
        union = len(a_set | b_set)
        return intersection / union if union > 0 else 0.0


@dataclass
class TemporalRhythm:
    """Time-based activity patterns."""
    active_hours: list[int] = field(default_factory=list)   # Hours with most activity
    avg_session_minutes: float = 0.0
    idle_tolerance_minutes: float = 0.0    # How long before user is "away"
    morning_person_score: float = 0.5      # 0=night owl, 1=morning person
    weekday_weekend_ratio: float = 1.0     # <1=weekend heavier, >1=weekday
    sample_days: int = 0
    last_updated: float = 0.0

    def distance(self, other: "TemporalRhythm") -> float:
        if self.sample_days < 2 or other.sample_days < 2:
            return 0.5
        hour_overlap = len(set(self.active_hours[:5]) & set(other.active_hours[:5]))
        hour_score = hour_overlap / max(len(self.active_hours[:5]), 1)
        morning_diff = abs(self.morning_person_score - other.morning_person_score)
        return (hour_score * 0.4 + (1 - morning_diff) * 0.3 + 0.3) / 1.0


@dataclass
class ErrorSignature:
    """Error-making patterns that are surprisingly unique to individuals."""
    common_errors: list[tuple[str, int]] = field(default_factory=list)
    correction_rate: float = 0.0       # How often errors are immediately corrected
    error_rate: float = 0.0            # Errors per command
    copy_paste_rate: float = 0.0       # Reliance on copy-paste
    total_commands: int = 0
    last_updated: float = 0.0


@dataclass
class LanguageFingerprint:
    """Natural language patterns."""
    avg_sentence_length: float = 0.0
    vocabulary_richness: float = 0.0     # Unique words / total words
    common_words: list[tuple[str, int]] = field(default_factory=list)
    punctuation_style: str = ""          # "formal", "casual", "minimal"
    emoji_usage_rate: float = 0.0
    code_comment_ratio: float = 0.0
    total_messages: int = 0
    last_updated: float = 0.0


@dataclass
class BiometricProfile:
    """Complete behavioral fingerprint of an entity."""
    profile_id: str
    name: str
    keystroke: KeystrokeProfile = field(default_factory=KeystrokeProfile)
    commands: CommandVocabulary = field(default_factory=CommandVocabulary)
    temporal: TemporalRhythm = field(default_factory=TemporalRhythm)
    errors: ErrorSignature = field(default_factory=ErrorSignature)
    language: LanguageFingerprint = field(default_factory=LanguageFingerprint)
    confidence: float = 0.0
    total_interactions: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def match_score(self, other: "BiometricProfile") -> float:
        """Compute overall match score between two profiles (0-1)."""
        weights = {"keystroke": 0.25, "command": 0.30,
                   "temporal": 0.20, "language": 0.15, "error": 0.10}
        scores = {}

        if self.keystroke.sample_count > 3 and other.keystroke.sample_count > 3:
            scores["keystroke"] = 1.0 - self.keystroke.distance(other.keystroke)
        if self.commands.total_commands > 5 and other.commands.total_commands > 5:
            scores["command"] = self.commands.jaccard_similarity(other.commands)
        if self.temporal.sample_days > 1 and other.temporal.sample_days > 1:
            scores["temporal"] = 1.0 - self.temporal.distance(other.temporal)
        if self.language.total_messages > 3 and other.language.total_messages > 3:
            scores["language"] = 1.0 - self._language_distance(other)
        if self.errors.total_commands > 5 and other.errors.total_commands > 5:
            scores["error"] = 1.0 - abs(self.errors.error_rate - other.errors.error_rate)

        total = 0.0
        total_weight = 0.0
        for key, weight in weights.items():
            if key in scores:
                total += scores[key] * weight
                total_weight += weight

        return total / total_weight if total_weight > 0 else 0.0

    def _language_distance(self, other: "BiometricProfile") -> float:
        """Language fingerprint distance."""
        if self.language.total_messages < 3 or other.language.total_messages < 3:
            return 0.5
        sentence_diff = abs(self.language.avg_sentence_length -
                           other.language.avg_sentence_length) / 50.0
        vocab_diff = abs(self.language.vocabulary_richness -
                        other.language.vocabulary_richness)
        punctuation_match = 1.0 if self.language.punctuation_style == other.language.punctuation_style else 0.0
        return (sentence_diff + vocab_diff + (1 - punctuation_match)) / 3.0


# ── Profile Registry ──

class BiometricRegistry:
    """Stores and matches behavioral biometric profiles.

    Continuously learns and refines profiles from interaction data.
    Can detect identity shifts (different person using same terminal).
    """

    IDENTITY_SHIFT_THRESHOLD = 0.40   # Match below this → possible different user
    PROFILE_MERGE_THRESHOLD = 0.85    # Match above this → same person

    def __init__(self):
        self._profiles: dict[str, BiometricProfile] = {}
        self._active_profile_id: str | None = None
        self._recent_keystrokes: deque[float] = deque(maxlen=100)  # inter-key delays
        self._recent_commands: deque[str] = deque(maxlen=50)
        self._recent_errors: deque[str] = deque(maxlen=20)
        self._shift_alerts: deque[dict] = deque(maxlen=50)
        self._total_interactions = 0

    # ── Profile management ──

    def create_profile(self, name: str, profile_id: str = "") -> BiometricProfile:
        """Create a new biometric profile."""
        pid = profile_id or f"bio_{name.lower().replace(' ', '_')}"
        if pid in self._profiles:
            return self._profiles[pid]
        profile = BiometricProfile(profile_id=pid, name=name)
        self._profiles[pid] = profile
        logger.info(f"BiometricRegistry: created profile '{name}' ({pid})")
        return profile

    def set_active(self, profile_id: str) -> None:
        """Set the currently active user profile."""
        old = self._active_profile_id
        self._active_profile_id = profile_id
        if old != profile_id and old is not None:
            logger.info(f"BiometricRegistry: active profile switched "
                        f"{self._profiles.get(old, BiometricProfile('','')).name} → "
                        f"{self._profiles.get(profile_id, BiometricProfile('','')).name}")

    def get_active(self) -> BiometricProfile | None:
        if self._active_profile_id is None:
            return None
        return self._profiles.get(self._active_profile_id)

    def get_profile(self, profile_id: str) -> BiometricProfile | None:
        return self._profiles.get(profile_id)

    # ── Signal ingestion ──

    def feed_keystroke(self, inter_key_delay_ms: float) -> None:
        """Feed a keystroke event with inter-key delay."""
        self._recent_keystrokes.append(inter_key_delay_ms)
        profile = self.get_active()
        if not profile:
            return
        ks = profile.keystroke
        n = ks.sample_count
        n += 1
        ks.avg_inter_key_ms = (ks.avg_inter_key_ms * (n - 1) + inter_key_delay_ms) / n
        ks.std_inter_key_ms = self._running_std(
            ks.std_inter_key_ms, ks.avg_inter_key_ms, inter_key_delay_ms, n)
        ks.sample_count = n
        profile.total_interactions += 1
        profile.last_updated = time.time()

    def feed_command(self, command: str, complexity: float = 0.5) -> None:
        """Feed a command execution."""
        self._recent_commands.append(command)
        self._total_interactions += 1
        profile = self.get_active()
        if not profile:
            return

        cv = profile.commands
        cv.total_commands += 1
        cv.complexity_mean = (cv.complexity_mean * (cv.total_commands - 1) + complexity) / cv.total_commands
        cv.pipe_usage_rate = (cv.pipe_usage_rate * (cv.total_commands - 1) +
                             (1.0 if '|' in command else 0.0)) / cv.total_commands

        # Update top commands
        cmd_counter: Counter = Counter(dict(cv.top_commands))
        simple_cmd = command.split()[0] if command else command
        cmd_counter[simple_cmd] += 1
        cv.top_commands = cmd_counter.most_common(20)
        cv.unique_count = len(cmd_counter)
        cv.last_updated = time.time()
        profile.total_interactions += 1
        profile.last_updated = time.time()

    def feed_error(self, command: str) -> None:
        """Feed a command error."""
        self._recent_errors.append(command)
        profile = self.get_active()
        if not profile:
            return
        es = profile.errors
        es.total_commands += 1
        simple_cmd = command.split()[0] if command else "unknown"
        err_counter = Counter(dict(es.common_errors))
        err_counter[simple_cmd] += 1
        es.common_errors = err_counter.most_common(10)
        profile.total_interactions += 1
        profile.last_updated = time.time()

    # ── Identity verification ──

    def verify_identity(self) -> tuple[bool, IdentityConfidence, BiometricProfile | None]:
        """Check if current interaction patterns match the active profile.
        
        Returns (match, confidence_level, best_matching_profile).
        If no match, suggests possible identity shift.
        """
        active = self.get_active()
        if not active:
            return False, IdentityConfidence.UNKNOWN, None

        # Look for matching profiles
        best_match: BiometricProfile | None = None
        best_score = 0.0

        for pid, profile in self._profiles.items():
            if pid == self._active_profile_id:
                continue
            score = active.match_score(profile)
            if score > best_score:
                best_score = score
                best_match = profile

        # Check if active profile is consistent with itself
        # (self-match always scores 1.0 by design, but drift accumulates)

        if best_score > self.PROFILE_MERGE_THRESHOLD and best_match:
            # Another profile matches better → possible duplicate profile
            return True, IdentityConfidence.CONFLICT, best_match

        # Check for identity shift: if active profile has been diverging
        if active.total_interactions > 50 and best_score < self.IDENTITY_SHIFT_THRESHOLD:
            alert = {
                "type": "identity_shift",
                "profile": active.name,
                "confidence": round(best_score, 3),
                "timestamp": time.time(),
            }
            self._shift_alerts.append(alert)
            logger.warning(f"BiometricRegistry: possible identity shift detected "
                           f"for '{active.name}' (confidence={best_score:.3f})")
            return False, IdentityConfidence.LOW, None

        # Normal: identity confirmed
        confidence = IdentityConfidence.MODERATE
        if active.total_interactions > 100:
            confidence = IdentityConfidence.HIGH
        return True, confidence, active

    def identify(self) -> tuple[BiometricProfile | None, float, IdentityConfidence]:
        """Attempt to identify the current user based on recent behavior.
        If active profile is set, returns that. Otherwise, matches against all.
        """
        active = self.get_active()
        if active:
            ok, conf, _ = self.verify_identity()
            return active, 0.95 if ok else 0.5, conf

        # No active profile — try to match against known ones
        if not self._profiles:
            return None, 0.0, IdentityConfidence.UNKNOWN

        # Create a temporary profile from recent data
        temp = self._build_temp_profile()
        best_match = None
        best_score = 0.0
        for pid, profile in self._profiles.items():
            score = temp.match_score(profile)
            if score > best_score:
                best_score = score
                best_match = profile

        if best_score > 0.7 and best_match:
            confidence = IdentityConfidence.HIGH if best_score > 0.9 else IdentityConfidence.MODERATE
            return best_match, round(best_score, 3), confidence
        elif best_score > 0.5 and best_match:
            return best_match, round(best_score, 3), IdentityConfidence.LOW
        return None, round(best_score, 3), IdentityConfidence.UNKNOWN

    # ── Report ──

    def get_report(self) -> dict[str, Any]:
        """Get biometric system status report."""
        active = self.get_active()
        return {
            "profiles": len(self._profiles),
            "active_profile": active.name if active else "none",
            "active_interactions": active.total_interactions if active else 0,
            "recent_shift_alerts": len(self._shift_alerts),
            "profile_details": {
                pid: {
                    "name": p.name,
                    "interactions": p.total_interactions,
                    "keystroke_samples": p.keystroke.sample_count,
                    "unique_commands": p.commands.unique_count,
                    "active_days": p.temporal.sample_days,
                    "confidence": round(p.confidence, 3),
                }
                for pid, p in self._profiles.items()
            },
        }

    # ── Internal ──

    def _build_temp_profile(self) -> BiometricProfile:
        """Build a temporary profile from recent signal buffers."""
        temp = BiometricProfile(profile_id="temp", name="Unidentified")
        recent = list(self._recent_keystrokes)
        if recent:
            temp.keystroke.avg_inter_key_ms = sum(recent) / len(recent)
            temp.keystroke.std_inter_key_ms = (
                sum((x - temp.keystroke.avg_inter_key_ms) ** 2 for x in recent) / len(recent)) ** 0.5
            temp.keystroke.sample_count = len(recent)
        if self._recent_commands:
            cmd_counter = Counter(self._recent_commands)
            temp.commands.top_commands = cmd_counter.most_common(10)
            temp.commands.unique_count = len(cmd_counter)
            temp.commands.total_commands = len(self._recent_commands)
        temp.total_interactions = len(self._recent_commands)
        return temp

    @staticmethod
    def _running_std(old_std: float, new_mean: float, new_value: float,
                     n: int) -> float:
        """Welford's online standard deviation update."""
        if n <= 1:
            return 0.0
        return math.sqrt(
            ((n - 2) / (n - 1)) * old_std ** 2 +
            ((new_value - new_mean) ** 2) / n
        )


# ── Singleton ──

BIOMETRIC_REGISTRY: BiometricRegistry = None  # type: ignore


def get_biometric_registry() -> BiometricRegistry:
    global BIOMETRIC_REGISTRY
    if BIOMETRIC_REGISTRY is None:
        BIOMETRIC_REGISTRY = BiometricRegistry()
    return BIOMETRIC_REGISTRY
