"""ProgressiveTrust — per-user expertise model with confidence calibration.

    Like a teacher who knows which students need more guidance in which areas.
    System remembers each user's expertise profile and adjusts its behavior:

    1. Expertise tracking: per-domain, per-section skill level
    2. Confidence calibration: how much can system auto-approve for this user
    3. Intervention threshold: when to ask vs when to auto-proceed
    4. Cross-user learning: colleagues share baseline trust (P2P synced)

    Usage:
        pt = get_progressive_trust()
        pt.record_interaction("user_a", "大气预测", user_corrected=True)
        pt.record_interaction("user_a", "大气预测", user_corrected=False)
        level = pt.expertise_level("user_a", "大气预测")  # → "expert"
        should_ask = pt.should_confirm("user_a", "大气预测")  # → False (expert)
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

TRUST_FILE = Path(".livingtree/user_trust.json")


@dataclass
class DomainSkill:
    domain: str                     # "大气预测", "水环境", "经济评价"...
    total_interactions: int = 0
    user_corrections: int = 0       # times user corrected system output
    user_confirmations: int = 0     # times user confirmed without changes
    user_overrides: int = 0         # times user explicitly overrode
    last_interaction: float = 0.0
    consecutive_correct: int = 0    # streak of unmodified outputs
    skill_level: float = 0.5        # 0.0(novice) → 1.0(expert)
    confidence_threshold: float = 0.8  # below this, system asks user


@dataclass
class UserModel:
    username: str
    first_seen: float = 0.0
    last_seen: float = 0.0
    total_sessions: int = 0
    total_interactions: int = 0
    domains: dict[str, DomainSkill] = field(default_factory=dict)
    colleagues: list[str] = field(default_factory=list)


class ProgressiveTrust:
    """Per-user expertise model controlling system autonomy."""

    def __init__(self):
        TRUST_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, UserModel] = {}
        self._load()

    def record_interaction(
        self,
        username: str,
        domain: str,
        user_corrected: bool = False,
        user_confirmed: bool = False,
        user_overrode: bool = False,
    ):
        """Record a user's interaction with system output in a domain.

        Called every time user accepts or modifies generated content.
        """
        if not username:
            return

        if username not in self._users:
            self._users[username] = UserModel(
                username=username,
                first_seen=time.time(),
            )

        u = self._users[username]
        u.last_seen = time.time()
        u.total_interactions += 1

        if domain not in u.domains:
            u.domains[domain] = DomainSkill(domain=domain)

        ds = u.domains[domain]
        ds.total_interactions += 1
        ds.last_interaction = time.time()

        if user_corrected:
            ds.user_corrections += 1
            ds.consecutive_correct = 0
        elif user_confirmed:
            ds.user_confirmations += 1
            ds.consecutive_correct += 1
        if user_overrode:
            ds.user_overrides += 1

        # Recalculate skill level
        ds.skill_level = self._calc_skill(ds)
        ds.confidence_threshold = self._calc_threshold(ds)

        self._maybe_save()

    def expertise_level(self, username: str, domain: str) -> str:
        """Get human-readable expertise level."""
        ds = self._get_domain(username, domain)
        if not ds or ds.total_interactions < 3:
            return "unknown"
        if ds.skill_level >= 0.8:
            return "expert"
        elif ds.skill_level >= 0.6:
            return "proficient"
        elif ds.skill_level >= 0.3:
            return "learning"
        return "novice"

    def should_confirm(self, username: str, domain: str, confidence: float = 0.5) -> bool:
        """Should system ask for confirmation before proceeding?

        Returns True if the user's expertise in this area is too low
        for the system's confidence level.
        """
        ds = self._get_domain(username, domain)
        if not ds:
            return True  # unknown user, always confirm

        # Expert users: only confirm very low confidence
        if ds.skill_level >= 0.8:
            return confidence < 0.3
        # Proficient: confirm below threshold
        if ds.skill_level >= 0.6:
            return confidence < ds.confidence_threshold
        # Novice/learning: confirm more
        return confidence < max(ds.confidence_threshold, 0.7)

    def get_user_profile(self, username: str) -> dict | None:
        """Get complete user expertise profile."""
        u = self._users.get(username)
        if not u:
            return None

        return {
            "username": u.username,
            "sessions": u.total_sessions,
            "interactions": u.total_interactions,
            "expertise": {
                domain: {
                    "level": self.expertise_level(username, domain),
                    "skill": round(ds.skill_level, 2),
                    "interactions": ds.total_interactions,
                    "correction_rate": round(ds.user_corrections / max(ds.total_interactions, 1) * 100, 1),
                    "consecutive_ok": ds.consecutive_correct,
                }
                for domain, ds in u.domains.items()
                if ds.total_interactions >= 3
            },
            "auto_approval_domains": [
                domain for domain, ds in u.domains.items()
                if self.expertise_level(username, domain) == "expert"
            ],
        }

    def link_colleague(self, username: str, colleague: str):
        """Link two users as colleagues (baseline trust transfer)."""
        if username in self._users and colleague in self._users:
            if colleague not in self._users[username].colleagues:
                self._users[username].colleagues.append(colleague)
            if username not in self._users[colleague].colleagues:
                self._users[colleague].colleagues.append(username)
            self._save()

    def _get_domain(self, username: str, domain: str) -> DomainSkill | None:
        u = self._users.get(username)
        if not u:
            return None
        # Exact match first
        if domain in u.domains:
            return u.domains[domain]
        # Fuzzy match
        for d, ds in u.domains.items():
            if d in domain or domain in d:
                return ds
        return None

    @staticmethod
    def _calc_skill(ds: DomainSkill) -> float:
        total = ds.total_interactions
        if total < 3:
            return 0.5  # neutral for new domains

        correct_rate = ds.user_confirmations / max(total, 1)
        correction_penalty = ds.user_corrections / max(total, 1)
        streak_bonus = min(ds.consecutive_correct / 10, 0.2)

        return min(1.0, correct_rate * 0.7 + (1 - correction_penalty) * 0.3 + streak_bonus)

    @staticmethod
    def _calc_threshold(ds: DomainSkill) -> float:
        if ds.total_interactions < 3:
            return 0.8
        # Expert users: lower threshold (system can auto-approve more)
        return max(0.3, 0.8 - ds.skill_level * 0.5)

    def _save(self):
        data = {}
        for username, u in self._users.items():
            data[username] = {
                "username": u.username,
                "first_seen": u.first_seen, "last_seen": u.last_seen,
                "total_sessions": u.total_sessions, "total_interactions": u.total_interactions,
                "colleagues": u.colleagues,
                "domains": {
                    domain: {
                        "domain": ds.domain,
                        "total_interactions": ds.total_interactions,
                        "user_corrections": ds.user_corrections,
                        "user_confirmations": ds.user_confirmations,
                        "user_overrides": ds.user_overrides,
                        "last_interaction": ds.last_interaction,
                        "consecutive_correct": ds.consecutive_correct,
                        "skill_level": ds.skill_level,
                        "confidence_threshold": ds.confidence_threshold,
                    }
                    for domain, ds in u.domains.items()
                },
            }
        TRUST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not TRUST_FILE.exists():
            return
        try:
            data = json.loads(TRUST_FILE.read_text(encoding="utf-8"))
            for username, ud in data.items():
                u = UserModel(
                    username=username,
                    first_seen=ud.get("first_seen", 0),
                    last_seen=ud.get("last_seen", 0),
                    total_sessions=ud.get("total_sessions", 0),
                    total_interactions=ud.get("total_interactions", 0),
                    colleagues=ud.get("colleagues", []),
                )
                for domain, dd in ud.get("domains", {}).items():
                    u.domains[domain] = DomainSkill(
                        domain=dd.get("domain", domain),
                        total_interactions=dd.get("total_interactions", 0),
                        user_corrections=dd.get("user_corrections", 0),
                        user_confirmations=dd.get("user_confirmations", 0),
                        user_overrides=dd.get("user_overrides", 0),
                        last_interaction=dd.get("last_interaction", 0),
                        consecutive_correct=dd.get("consecutive_correct", 0),
                        skill_level=dd.get("skill_level", 0.5),
                        confidence_threshold=dd.get("confidence_threshold", 0.8),
                    )
                self._users[username] = u
        except Exception:
            pass

    def _maybe_save(self):
        if sum(u.total_interactions for u in self._users.values()) % 20 == 0:
            self._save()


_pt: ProgressiveTrust | None = None


def get_progressive_trust() -> ProgressiveTrust:
    global _pt
    if _pt is None:
        _pt = ProgressiveTrust()
    return _pt
