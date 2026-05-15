"""SpecializationTracker — Auto-discovers each provider's real strengths.

Tracks per-task-type performance (depth_grade + latency + success_rate) for each
provider. Over time, builds an empirical capability profile that may differ from
the hand-written PROVIDER_CAPABILITIES labels. Can auto-update the static labels.

Integration:
    st = get_specialization_tracker()
    st.record(provider, task_type, depth, latency, success)
    best = st.best_for("code")  # → [(provider, depth, latency), ...]
    st.auto_update_capabilities(PROVIDER_CAPABILITIES)
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from loguru import logger

SPEC_FILE = Path(".livingtree/specialization_stats.json")


class SpecializationTracker:
    """Empirical provider specialization discovery."""

    _instance: Optional["SpecializationTracker"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "SpecializationTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SpecializationTracker()
        return cls._instance

    def __init__(self):
        self._stats: dict[str, dict] = {}  # "provider:task_type" → {depth_ema, lat_ema, succ_ema, n}
        self._ema_alpha = 0.15
        self._load()

    def record(self, provider: str, task_type: str,
               depth: float, latency_ms: float, success: bool) -> None:
        """Record a single provider call outcome."""
        key = f"{provider}:{task_type}"
        s = self._stats.setdefault(key, {
            "depth_ema": 0.5, "lat_ema": 1000.0, "succ_ema": 0.5, "n": 0,
        })
        a = self._ema_alpha
        s["depth_ema"] = s["depth_ema"] * (1 - a) + depth * a
        s["lat_ema"] = s["lat_ema"] * (1 - a) + latency_ms * a
        s["succ_ema"] = s["succ_ema"] * (1 - a) + (1.0 if success else 0.0) * a
        s["n"] += 1

        if s["n"] % 20 == 0:
            self._save()

    def best_for(self, task_type: str, min_samples: int = 3) -> list[tuple[str, float, float]]:
        """Return providers ranked by empirical depth on this task_type."""
        candidates = []
        for key, s in self._stats.items():
            if key.endswith(f":{task_type}") and s["n"] >= min_samples:
                provider = key.rsplit(":", 1)[0]
                candidates.append((provider, s["depth_ema"], s["lat_ema"]))
        candidates.sort(key=lambda x: (-x[1], x[2]))  # depth desc, latency asc
        return candidates

    def get_empirical_capabilities(self, provider: str) -> list[str]:
        """Get task types this provider empirically excels at."""
        caps = []
        for key, s in self._stats.items():
            if key.startswith(f"{provider}:") and s["n"] >= 3:
                if s["depth_ema"] > 0.5:
                    caps.append(key.split(":", 1)[1])
        return sorted(caps, key=lambda t: self._stats[f"{provider}:{t}"]["depth_ema"], reverse=True)

    def auto_update_capabilities(self, capabilities_dict: dict[str, list[str]]) -> int:
        """Merge empirical findings into hand-written capabilities dict. Returns update count."""
        updated = 0
        for key, s in self._stats.items():
            if s["n"] < 5:
                continue
            provider, task_type = key.rsplit(":", 1)
            if task_type in ("general", "chat"):
                continue
            caps = capabilities_dict.get(provider, [])
            if task_type not in caps and s["depth_ema"] > 0.45:
                caps.append(task_type)
                capabilities_dict[provider] = caps
                updated += 1
                logger.debug(f"SpecializationTracker: {provider} +{task_type} (empirical depth={s['depth_ema']:.2f})")
        return updated

    def stats(self) -> dict:
        return {
            "entries": len(self._stats),
            "providers": len(set(k.split(":", 1)[0] for k in self._stats)),
        }

    def _save(self):
        try:
            SPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
            SPEC_FILE.write_text(json.dumps(self._stats, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"SpecializationTracker save: {e}")

    def _load(self):
        try:
            if SPEC_FILE.exists():
                self._stats = json.loads(SPEC_FILE.read_text())
        except Exception:
            pass


_tracker: Optional[SpecializationTracker] = None
_tracker_lock = threading.Lock()


def get_specialization_tracker() -> SpecializationTracker:
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = SpecializationTracker()
    return _tracker


__all__ = ["SpecializationTracker", "get_specialization_tracker"]
