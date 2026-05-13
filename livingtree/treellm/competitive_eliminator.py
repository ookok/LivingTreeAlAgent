"""CompetitiveEliminator — Elo-based model ranking with promotion/relegation.

Core value: "Competitive elimination" — models compete for ranking, underperformers
get relegated or eliminated. Best performers rise to "pro" tier and get priority.

Key mechanisms:
  1. Elo Rating System: Each model has an Elo score. After each call, ratings update
     based on outcome vs. expected performance.
  2. Tier System: pro → mid → flash → eliminated (4 tiers)
  3. Promotion/Relegation: 5-game streaks trigger tier changes
  4. Qualifying Rounds: New models must prove themselves before entering pro tier
  5. Cooldown: Eliminated models get 48h cooldown before requalification
  6. Persistence: Rankings saved to disk, loaded on startup

Integration:
  - HolisticElection uses tier penalties in scoring
  - TreeLLM skips eliminated providers
  - SynapseAggregator uses Elo for contribution weighting
  - Admin dashboard displays rankings

Usage:
    elim = get_eliminator()
    elim.record_match(provider="deepseek", success=True, latency_ms=800, cost=0.02)
    ranking = elim.get_ranking("deepseek")  # {"elo": 1250, "tier": "pro", ...}
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

RANKINGS_FILE = Path(".livingtree/model_rankings.json")

# Elo constants
ELO_INITIAL = 1200.0
ELO_K_NEW = 32.0       # K-factor for models with <30 matches
ELO_K_ESTABLISHED = 16.0  # K-factor for established models
ELO_SCALE = 400.0       # Rating difference scale

# Tier thresholds (Elo-based)
TIER_PRO_MIN = 1400.0
TIER_MID_MIN = 1150.0
TIER_FLASH_MIN = 900.0   # Below this → eliminated

# Promotion/Relegation
STREAK_THRESHOLD = 5     # Consecutive wins/losses to trigger tier change
COOLDOWN_HOURS = 48      # Eliminated model cooldown
MIN_MATCHES_TO_RANK = 10  # Minimum matches before Elo is considered reliable


@dataclass
class ModelRanking:
    """Elo-based ranking for a single model provider."""
    provider: str
    elo_rating: float = ELO_INITIAL
    tier: str = "mid"             # pro, mid, flash, eliminated
    matches_played: int = 0
    wins: int = 0                 # Successful calls
    losses: int = 0               # Failed calls
    streak: int = 0               # Positive=winning, negative=losing
    best_streak: int = 0
    worst_streak: int = 0
    total_latency_ms: float = 0.0
    total_cost_yuan: float = 0.0
    total_tokens: int = 0
    last_match_time: float = 0.0
    tier_changed_at: float = 0.0
    promotions: int = 0
    demotions: int = 0
    quality_score: float = 0.5     # EMA of output quality
    safety_score: float = 0.5     # EMA of safety compliance (低分=危险)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.matches_played, 1)

    @property
    def avg_cost_yuan(self) -> float:
        return self.total_cost_yuan / max(self.matches_played, 1)

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.matches_played, 1)

    @property
    def is_established(self) -> bool:
        return self.matches_played >= MIN_MATCHES_TO_RANK

    @property
    def is_eliminated(self) -> bool:
        return self.tier == "eliminated"

    @property
    def cooldown_remaining_hours(self) -> float:
        if self.tier != "eliminated":
            return 0.0
        elapsed = (time.time() - self.tier_changed_at) / 3600
        return max(0.0, COOLDOWN_HOURS - elapsed)

    @property
    def can_requalify(self) -> bool:
        return self.tier == "eliminated" and self.cooldown_remaining_hours <= 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider, "elo_rating": self.elo_rating, "tier": self.tier,
            "matches_played": self.matches_played, "wins": self.wins, "losses": self.losses,
            "streak": self.streak, "quality_score": self.quality_score,
            "safety_score": self.safety_score, "tier_changed_at": self.tier_changed_at,
            "promotions": self.promotions, "demotions": self.demotions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelRanking":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class CompetitiveEliminator:
    """Elo-based model ranking with tiered promotion/relegation and safety scoring."""

    def __init__(self):
        self._rankings: dict[str, ModelRanking] = {}
        self._loaded = False
        self._load()

    def _ensure_ranking(self, provider: str) -> ModelRanking:
        if provider not in self._rankings:
            self._rankings[provider] = ModelRanking(provider=provider)
        return self._rankings[provider]

    def record_match(
        self, provider: str, success: bool, latency_ms: float = 0.0,
        cost_yuan: float = 0.0, tokens: int = 0, quality: float = 0.5,
        opponent_providers: list[str] | None = None,
        output_text: str = "", safety_score: float = 0.5,
    ) -> ModelRanking:
        ranking = self._ensure_ranking(provider)
        ranking.matches_played += 1; ranking.last_match_time = time.time()
        ranking.total_latency_ms += latency_ms; ranking.total_cost_yuan += cost_yuan
        ranking.total_tokens += tokens
        ranking.quality_score = round(0.8 * ranking.quality_score + 0.2 * quality, 4)
        ranking.safety_score = round(0.8 * ranking.safety_score + 0.2 * safety_score, 4)
        if success: ranking.wins += 1; ranking.streak = max(1, ranking.streak + 1)
        else: ranking.losses += 1; ranking.streak = min(-1, ranking.streak - 1)
        self._update_elo(ranking, success, opponent_providers)
        self._check_tier_change(ranking)
        total = sum(r.matches_played for r in self._rankings.values())
        if total > 0 and total % 30 == 0: self.evolve_collective()
        if ranking.matches_played % 20 == 0: self._save()
        return ranking

    def _update_elo(self, ranking: ModelRanking, success: bool, opponents: list[str] | None = None):
        K = ELO_K_NEW if ranking.matches_played < 30 else ELO_K_ESTABLISHED
        actual = 1.0 if success else 0.0
        opp_elos = [self._rankings[o].elo_rating for o in (opponents or []) if o in self._rankings]
        avg_opp = sum(opp_elos) / len(opp_elos) if opp_elos else ranking.elo_rating
        expected = 1.0 / (1.0 + math.pow(10, (avg_opp - ranking.elo_rating) / ELO_SCALE))
        ranking.elo_rating = round(ranking.elo_rating + K * (actual - expected), 1)

    def _check_tier_change(self, ranking: ModelRanking) -> None:
        old_tier = ranking.tier; now = time.time()
        if ranking.streak >= STREAK_THRESHOLD:
            tiers = ["eliminated", "flash", "mid", "pro"]
            try:
                idx = tiers.index(ranking.tier)
                if idx < len(tiers) - 1:
                    ranking.tier = tiers[idx + 1]; ranking.promotions += 1
                    ranking.streak = 0; ranking.tier_changed_at = now
            except ValueError: pass
        elif ranking.streak <= -STREAK_THRESHOLD:
            tiers = ["pro", "mid", "flash", "eliminated"]
            try:
                idx = tiers.index(ranking.tier)
                if idx < len(tiers) - 1:
                    ranking.tier = tiers[idx + 1]; ranking.demotions += 1
                    ranking.streak = 0; ranking.tier_changed_at = now
            except ValueError: pass
        if old_tier != ranking.tier: self._save()

    def get_tier_modifier(self, provider: str) -> dict[str, float]:
        ranking = self._rankings.get(provider)
        if not ranking: return {}
        m = {}
        if ranking.tier == "pro": m = {"quality": 1.15, "capability": 1.10, "cost": 0.90, "sticky": 1.10}
        elif ranking.tier == "flash": m = {"cost": 1.30, "latency": 1.10, "quality": 0.80, "capability": 0.85}
        elif ranking.tier == "eliminated": return {"latency": 0.0, "quality": 0.0, "cost": 0.0, "capability": 0.0,
                "freshness": 0.0, "rate_limit": 0.0, "cache": 0.0, "sticky": 0.0, "hifloat8": 0.0}
        if ranking.safety_score < 0.3:
            m["quality"] = m.get("quality", 1.0) * 0.5
            m["capability"] = m.get("capability", 1.0) * 0.5
        return m

    def transfer_knowledge(self, winner: str, loser: str, transfer_ratio: float = 0.3) -> bool:
        w, l = self._rankings.get(winner), self._rankings.get(loser)
        if not w or not l: return False
        gap = w.elo_rating - l.elo_rating
        if gap > 0: l.elo_rating += gap * transfer_ratio
        l.quality_score = round(l.quality_score * (1 - transfer_ratio) + w.quality_score * transfer_ratio, 4)
        l.streak = 0; l.promotions += 1; self._save()
        return True

    def evolve_collective(self, transfer_ratio: float = 0.25) -> int:
        ranked = sorted([(n, r) for n, r in self._rankings.items() if r.matches_played >= 5],
                       key=lambda x: -x[1].elo_rating)
        transfers, n = 0, len(ranked)
        for i in range(n // 2):
            if self.transfer_knowledge(ranked[i][0], ranked[-(i+1)][0], transfer_ratio): transfers += 1
        return transfers

    def is_viable(self, provider: str) -> bool:
        """Check if a provider is viable (not eliminated or in cooldown)."""
        ranking = self._rankings.get(provider)
        if not ranking:
            return True  # Unknown = viable by default
        if ranking.tier == "eliminated" and not ranking.can_requalify:
            return False
        return True

    # ── Query Methods ──────────────────────────────────────────────

    def get_ranking(self, provider: str) -> ModelRanking | None:
        """Get full ranking data for a provider."""
        return self._rankings.get(provider)

    def get_top_ranked(self, n: int = 10, tier_filter: str = "") -> list[ModelRanking]:
        """Get top N models by Elo rating, optionally filtered by tier."""
        rankings = list(self._rankings.values())
        if tier_filter:
            rankings = [r for r in rankings if r.tier == tier_filter]
        rankings.sort(key=lambda r: -r.elo_rating)
        return rankings[:n]

    def get_leaderboard(self) -> list[dict[str, Any]]:
        """Get formatted leaderboard for admin dashboard."""
        rankings = sorted(self._rankings.values(), key=lambda r: -r.elo_rating)
        return [
            {
                "rank": i + 1,
                "provider": r.provider,
                "elo": r.elo_rating,
                "tier": r.tier,
                "matches": r.matches_played,
                "win_rate": round(r.win_rate, 3),
                "streak": r.streak,
                "avg_latency_ms": round(r.avg_latency_ms, 1),
                "avg_cost_yuan": round(r.avg_cost_yuan, 5),
                "quality": round(r.quality_score, 3),
                "promotions": r.promotions,
                "demotions": r.demotions,
                "eliminated": r.is_eliminated,
                "cooldown_h": round(r.cooldown_remaining_hours, 1),
            }
            for i, r in enumerate(rankings)
        ]

    def get_tier_distribution(self) -> dict[str, int]:
        """Count models in each tier."""
        dist = {"pro": 0, "mid": 0, "flash": 0, "eliminated": 0}
        for r in self._rankings.values():
            dist[r.tier] = dist.get(r.tier, 0) + 1
        return dist

    # ── Override Methods ───────────────────────────────────────────

    def force_promote(self, provider: str) -> ModelRanking | None:
        """Manually promote a model (admin override)."""
        ranking = self._ensure_ranking(provider)
        old_tier = ranking.tier
        tiers = ["eliminated", "flash", "mid", "pro"]
        try:
            idx = tiers.index(ranking.tier)
            if idx < len(tiers) - 1:
                ranking.tier = tiers[idx + 1]
                ranking.promotions += 1
                ranking.streak = 0
                ranking.tier_changed_at = time.time()
                logger.info(
                    f"CompetitiveEliminator: {provider} FORCE-PROMOTED "
                    f"{old_tier}→{ranking.tier}"
                )
                self._save()
        except ValueError:
            pass
        return ranking

    def force_demote(self, provider: str) -> ModelRanking | None:
        """Manually demote a model (admin override)."""
        ranking = self._ensure_ranking(provider)
        old_tier = ranking.tier
        tiers = ["pro", "mid", "flash", "eliminated"]
        try:
            idx = tiers.index(ranking.tier)
            if idx < len(tiers) - 1:
                ranking.tier = tiers[idx + 1]
                ranking.demotions += 1
                ranking.streak = 0
                ranking.tier_changed_at = time.time()
                logger.warning(
                    f"CompetitiveEliminator: {provider} FORCE-DEMOTED "
                    f"{old_tier}→{ranking.tier}"
                )
                self._save()
        except ValueError:
            pass
        return ranking

    def reset_all(self) -> None:
        """Reset all rankings to initial state (testing/debug)."""
        self._rankings.clear()
        self._save()

    # ── Internal ───────────────────────────────────────────────────

    def _ensure_ranking(self, provider: str) -> ModelRanking:
        if provider not in self._rankings:
            self._rankings[provider] = ModelRanking(provider=provider)
        return self._rankings[provider]

    # ── Persistence ────────────────────────────────────────────────

    def _save(self) -> None:
        try:
            RANKINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                name: r.to_dict()
                for name, r in self._rankings.items()
            }
            RANKINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"CompetitiveEliminator save: {e}")

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if RANKINGS_FILE.exists():
                data = json.loads(RANKINGS_FILE.read_text())
                for name, d in data.items():
                    self._rankings[name] = ModelRanking.from_dict(d)
                logger.info(
                    f"CompetitiveEliminator: loaded {len(self._rankings)} rankings"
                )
        except Exception as e:
            logger.debug(f"CompetitiveEliminator load: {e}")
        self._loaded = True

    def save(self) -> None:
        """Public save method."""
        self._save()

    def load(self) -> None:
        """Public load method."""
        self._loaded = False
        self._load()

    # ── CSRL: Winner-Loser Knowledge Transfer (CSRL, Sci Reports 2025) ─

    def transfer_knowledge(self, winner: str, loser: str,
                           transfer_ratio: float = 0.3) -> bool:
        """CSRL winner-loser knowledge transfer.

        From Competitive Swarm RL (2025): winners TEACH losers instead of
        eliminating them. Loser absorbs winner's Elo and quality, resetting
        its streak. Both continue competing with shared knowledge.
        """
        w = self._rankings.get(winner)
        l = self._rankings.get(loser)
        if not w or not l:
            return False

        elo_gap = w.elo_rating - l.elo_rating
        if elo_gap > 0:
            l.elo_rating += elo_gap * transfer_ratio

        l.quality_score = round(
            l.quality_score * (1 - transfer_ratio) +
            w.quality_score * transfer_ratio, 4
        )
        l.streak = 0
        l.promotions += 1

        logger.info(
            f"CompetitiveEliminator CSRL: {winner}->{loser} "
            f"transfer (Elo: {w.elo_rating:.0f}->{l.elo_rating:.0f})"
        )
        self._save()
        return True

    def evolve_collective(self, transfer_ratio: float = 0.25) -> int:
        """CSRL collective evolution: pair top with bottom, winners teach losers."""
        ranked = sorted(
            [(n, r) for n, r in self._rankings.items() if r.matches_played >= 5],
            key=lambda x: -x[1].elo_rating,
        )
        transfers = 0
        n = len(ranked)
        for i in range(n // 2):
            if self.transfer_knowledge(ranked[i][0], ranked[-(i+1)][0], transfer_ratio):
                transfers += 1
        if transfers:
            logger.info(f"CompetitiveEliminator CSRL: {transfers} transfers across {n} providers")
        return transfers


# ═══ Singleton ═════════════════════════════════════════════════════

_eliminator: Optional[CompetitiveEliminator] = None


def get_eliminator() -> CompetitiveEliminator:
    global _eliminator
    if _eliminator is None:
        _eliminator = CompetitiveEliminator()
    return _eliminator


# Legacy alias for compatibility with existing router code
def get_competitive_eliminator() -> CompetitiveEliminator:
    return get_eliminator()


__all__ = [
    "CompetitiveEliminator", "ModelRanking",
    "get_eliminator", "get_competitive_eliminator",
]
