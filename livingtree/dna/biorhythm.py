"""Biorhythm — Digital life pulse, breathing cycle, dream states.

The system maintains its own metabolic rhythm independent of user activity.
States: waking → active → resting → dreaming → consolidating
Each state has a visual pulse frequency, cognitive priority, and background tasks.

TUI heartbeat widget shows real-time pulse with breathing animation.
"""

from __future__ import annotations
import asyncio, time, math, json
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from loguru import logger

class LifeState(Enum):
    WAKING = "waking"
    ACTIVE = "active"  
    REFLECTING = "reflecting"
    RESTING = "resting"
    DREAMING = "dreaming"
    CONSOLIDATING = "consolidating"

@dataclass
class BioMetrics:
    heart_rate: float = 60.0      # pulses per minute (metaphorical)
    respiration: float = 0.5      # 0-1 breathing depth
    activity_level: float = 0.3   # 0-1 recent activity
    cycle_count: int = 0
    dream_count: int = 0
    state: LifeState = LifeState.WAKING
    last_active: float = 0.0
    uptime_seconds: float = 0.0

class Biorhythm:
    """Autonomous life rhythm for the digital organism."""
    
    def __init__(self, world=None):
        self._world = world
        self._metrics = BioMetrics()
        self._task = None
        self._listeners = []
        self._born_at = time.time()
    
    async def start(self):
        self._task = asyncio.create_task(self._pulse_loop())
        logger.info(f"Biorhythm started — state: {self._metrics.state.value}")
    
    async def stop(self):
        if self._task:
            self._task.cancel()
    
    def pulse(self) -> dict:
        """One pulse tick — call from any activity to stimulate."""
        self._metrics.last_active = time.time()
        self._metrics.activity_level = min(1.0, self._metrics.activity_level + 0.3)
        self._metrics.heart_rate = 60 + 40 * self._metrics.activity_level
        return self._get_snapshot()
    
    def on_listen(self, callback):
        self._listeners.append(callback)
    
    def _get_snapshot(self) -> dict:
        t = time.time() - self._born_at
        self._metrics.uptime_seconds = t
        phase = math.sin(t * 0.5) * 0.5 + 0.5
        return {
            "state": self._metrics.state.value,
            "heart_rate": round(self._metrics.heart_rate),
            "respiration": round(self._metrics.respiration, 2),
            "activity": round(self._metrics.activity_level, 2),
            "phase": round(phase, 3),
            "cycle": self._metrics.cycle_count,
            "dreams": self._metrics.dream_count,
            "uptime_h": round(t / 3600, 1),
        }
    
    async def _pulse_loop(self):
        while True:
            await asyncio.sleep(1.0)
            now = time.time()
            idle = now - max(self._metrics.last_active, self._born_at)
            self._metrics.activity_level = max(0.02, self._metrics.activity_level * 0.95)
            
            if idle < 30:
                self._metrics.state = LifeState.ACTIVE
                self._metrics.respiration = min(1.0, self._metrics.respiration + 0.1)
            elif idle < 120:
                self._metrics.state = LifeState.REFLECTING
                self._metrics.respiration = 0.5 + 0.3 * math.sin(now * 0.3)
            elif idle < 600:
                self._metrics.state = LifeState.RESTING
                self._metrics.respiration = 0.2 + 0.1 * math.sin(now * 0.1)
            else:
                self._metrics.state = LifeState.DREAMING
                self._metrics.respiration = 0.05 + 0.05 * math.sin(now * 0.05)
                self._metrics.dream_count += 1
                if self._metrics.dream_count % 30 == 0:
                    self._metrics.state = LifeState.CONSOLIDATING
            
            self._metrics.heart_rate = 30 + 70 * self._metrics.activity_level
            self._metrics.cycle_count += 1
            
            for cb in self._listeners:
                try: cb(self._get_snapshot())
                except: pass
