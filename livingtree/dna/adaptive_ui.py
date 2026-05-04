"""Adaptive UI — Living interface that changes with context.

Time-based theming: cool blue morning → warm amber evening → dark night.
Usage-based layout: frequently used features drift to prominence.
Emotion-aware: frustration darkens edges, flow state brightens.
"""

from __future__ import annotations
import time, math
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

@dataclass
class AdaptiveTheme:
    background: str = "#0a0c10"
    accent: str = "#58a6ff"
    text: str = "#c9d1d9"
    surface: str = "#0d1117"
    border: str = "#30363d"
    glow: str = "#58a6ff40"
    warmth: float = 0.0

class AdaptiveUI:
    """Time-aware, usage-aware, emotion-aware UI adaptation."""
    
    def __init__(self, world=None):
        self._world = world
        self._theme = AdaptiveTheme()
        self._usage = {}        # feature → count
        self._frustration = 0.0 # 0-1
        self._flow = 0.0        # 0-1 flow state
        
    def tick(self, hour=None, sun_angle=None) -> AdaptiveTheme:
        h = hour if hour is not None else datetime.now().hour
        t = AdaptiveTheme()
        t.warmth = math.sin((h - 6) / 24 * math.pi) * 0.5 + 0.5
        
        if h < 6:
            t.background = "#0a0c10"; t.accent = "#58a6ff"
        elif h < 10:
            t.background = "#0d1117"; t.accent = "#79c0ff"
        elif h < 14:
            t.background = "#0d1117"; t.accent = "#58a6ff"
            t.glow = "#58a6ff50"
        elif h < 18:
            r = int(0xff - 0x30 * t.warmth); g = int(0xa6 - 0x30 * t.warmth); b = int(0xff - 0x20 * t.warmth)
            t.accent = f"#{r:02x}{max(g,0x60):02x}{b:02x}"
            t.glow = f"#{r:02x}{max(g,0x60):02x}{b:02x}30"
        else:
            t.background = "#0a0c10"; t.accent = "#3fb950"
            t.glow = "#3fb95020"
        
        if self._frustration > 0.3:
            t.accent = "#f85149"; t.glow = "#f8514930"
        if self._flow > 0.5:
            t.glow = t.glow.replace("30","60")
        
        self._theme = t
        return t
    
    def record_usage(self, feature: str):
        self._usage[feature] = self._usage.get(feature, 0) + 1
        
    def detect_frustration(self, rapid_queries=0, negations=0, corrections=0) -> float:
        self._frustration = min(1.0, (rapid_queries * 0.1 + negations * 0.2 + corrections * 0.3))
        return self._frustration
    
    def enter_flow(self, sustained_activity_seconds=0):
        self._flow = min(1.0, sustained_activity_seconds / 600)
        
    def get_prominent_features(self, top_n=5) -> list[str]:
        return sorted(self._usage, key=self._usage.get, reverse=True)[:top_n]
    
    def get_accent_color(self) -> str:
        return self._theme.accent
    
    def get_background(self) -> str:
        return self._theme.background
