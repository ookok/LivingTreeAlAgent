"""Digital Organism — Circadian Rhythm (used by hormone_signaling for circadian melatonin/cortisol).

Other decorative subsystems (EmotionalBrain, OrganParliament, OrganLifecycle,
PredictiveCascade, DigitalOrganismV2) removed — they were unused/duplicate code.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class TimeOfDay(str, Enum):
    DAWN = "dawn"           # 05:00-08:00 — waking up, low activity
    MORNING = "morning"     # 08:00-12:00 — peak cognitive, high throughput
    AFTERNOON = "afternoon" # 12:00-17:00 — sustained, medium
    DUSK = "dusk"           # 17:00-20:00 — winding down
    NIGHT = "night"         # 20:00-05:00 — consolidation, dreams, garbage collection


class CircadianClock:
    """24-hour biological clock. Used by HormoneNetwork for hormone modulation."""

    PHASE_CONFIG = {
        TimeOfDay.DAWN: {
            "metabolic_rate": 0.3, "exploration": 0.4,
            "temperature": 36.5, "hormone": "cortisol_rising",
            "mode": "warming_up",
        },
        TimeOfDay.MORNING: {
            "metabolic_rate": 1.0, "exploration": 0.8,
            "temperature": 37.0, "hormone": "cortisol_peak",
            "mode": "peak_performance",
        },
        TimeOfDay.AFTERNOON: {
            "metabolic_rate": 0.8, "exploration": 0.5,
            "temperature": 37.0, "hormone": "steady",
            "mode": "sustained",
        },
        TimeOfDay.DUSK: {
            "metabolic_rate": 0.5, "exploration": 0.3,
            "temperature": 36.8, "hormone": "melatonin_rising",
            "mode": "winding_down",
        },
        TimeOfDay.NIGHT: {
            "metabolic_rate": 0.2, "exploration": 0.1,
            "temperature": 36.3, "hormone": "melatonin_peak",
            "mode": "consolidation",
        },
    }

    @staticmethod
    def now() -> TimeOfDay:
        hour = datetime.now().hour
        if 5 <= hour < 8:
            return TimeOfDay.DAWN
        elif 8 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= hour < 20:
            return TimeOfDay.DUSK
        else:
            return TimeOfDay.NIGHT

    @staticmethod
    def config() -> dict:
        return CircadianClock.PHASE_CONFIG[CircadianClock.now()]

    @staticmethod
    def should_dream() -> bool:
        return CircadianClock.now() == TimeOfDay.NIGHT

    @staticmethod
    def should_explore() -> bool:
        return CircadianClock.now() in (TimeOfDay.MORNING, TimeOfDay.AFTERNOON)


__all__ = ["TimeOfDay", "CircadianClock"]
