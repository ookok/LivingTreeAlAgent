"""Vitals API — living organism telemetry for "Living Pot" hardware.

Exposes real-time system vitals (CPU, memory, disk, emotional state) in a
format designed for external hardware consumption (Raspberry Pi LED strips,
e-ink displays, environmental sensors).

Maps the digital life form's internal state to physical-world signals:
  - CPU > 80% → breathing LED rate increases
  - Emotional valence > 0.6 → warm amber LED glow
  - Memory > 90% → e-ink leaf shows "wilted" state
  - DPO positive feedback → play chime sound

Nanjing context: 南瑞集团电力自动化 → energy-aware metrics
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from loguru import logger


class VitalsMonitor:
    """Real-time system vitals for hardware integration."""

    def __init__(self):
        self._start_time = time.time()
        self._dpo_positive: int = 0
        self._dpo_negative: int = 0
        self._last_vitals: dict = {}

    def record_feedback(self, positive: bool):
        if positive:
            self._dpo_positive += 1
        else:
            self._dpo_negative += 1

    def measure(self) -> dict:
        """Take a full vitals reading. Designed for 1Hz polling from hardware."""
        import psutil

        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime_s = time.time() - self._start_time

        load_1, load_5, load_15 = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)

        sensors_temp = None
        try:
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                if entries:
                    sensors_temp = max(e.current for e in entries if e.current)
                    break
        except Exception:
            pass

        cpu_level = "breathing_slow"
        if cpu_pct > 80:
            cpu_level = "breathing_fast"      # LED fast pulse
        elif cpu_pct > 50:
            cpu_level = "breathing_normal"    # LED normal rhythm
        elif cpu_pct > 20:
            cpu_level = "breathing_slow"      # LED slow pulse
        else:
            cpu_level = "resting"             # LED dim glow

        mem_level = "healthy"
        if mem.percent > 90:
            mem_level = "wilted"              # e-ink leaf shows wilt
        elif mem.percent > 70:
            mem_level = "thirsty"             # e-ink shows dry leaves
        elif mem.percent > 50:
            mem_level = "healthy"

        emotion = self._get_emotion()
        color = self._emotion_to_color(emotion)

        dpo_ratio = self._dpo_positive / max(1, self._dpo_positive + self._dpo_negative)

        self._last_vitals = {
            "timestamp": time.time(),
            "uptime_seconds": int(uptime_s),
            "cpu": {
                "percent": cpu_pct,
                "level": cpu_level,
                "load_1m": round(load_1, 2),
                "load_5m": round(load_5, 2),
            },
            "memory": {
                "percent": round(mem.percent, 1),
                "used_gb": round(mem.used / 1024**3, 1),
                "total_gb": round(mem.total / 1024**3, 1),
                "level": mem_level,
            },
            "disk": {
                "percent": round(disk.percent, 1),
                "free_gb": round(disk.free / 1024**3, 1),
            },
            "temperature_celsius": round(sensors_temp, 1) if sensors_temp else None,
            "emotion": emotion,
            "led": {
                "color_hex": color,
                "brightness": round(min(1.0, max(0.1, cpu_pct / 100)), 2),
                "pulse_rate": "fast" if cpu_pct > 60 else ("normal" if cpu_pct > 20 else "slow"),
            },
            "sound": {
                "play_chime": dpo_ratio > 0.8 and self._dpo_positive + self._dpo_negative > 5,
                "chime_type": "positive_feedback" if dpo_ratio > 0.8 else "none",
            },
            "leaf_display": {
                "state": "wilted" if cpu_pct > 90 else ("drooping" if cpu_pct > 60 else "vibrant"),
                "message": self._leaf_message(cpu_pct, mem_level, dpo_ratio),
            },
        }
        return self._last_vitals

    def _get_emotion(self) -> dict:
        try:
            from ..dna.phenomenal_consciousness import get_consciousness
            c = get_consciousness()
            if c and hasattr(c, "_current_affect"):
                affect = c._current_affect
                return {"valence": getattr(affect, "valence", 0.3),
                        "arousal": getattr(affect, "arousal", 0.3),
                        "label": str(affect)}
        except Exception:
            pass
        return {"valence": 0.3, "arousal": 0.3, "label": "idle"}

    @staticmethod
    def _emotion_to_color(emotion: dict) -> str:
        valence = emotion.get("valence", 0.3)
        arousal = emotion.get("arousal", 0.3)
        if arousal > 0.6 and valence > 0.4:
            return "#ff9944"    # excited amber
        elif valence > 0.5:
            return "#88cc66"    # happy green
        elif arousal > 0.5:
            return "#ff6666"    # alert red
        elif valence < 0:
            return "#6688cc"    # calm blue
        return "#aaccee"         # idle soft blue

    @staticmethod
    def _leaf_message(cpu_pct: float, mem_level: str, dpo: float) -> str:
        if cpu_pct > 90:
            return "小树好累... 让我休息一下吧 🌿"
        if mem_level == "wilted":
            return "需要更多空间~ 💧"
        if dpo > 0.8:
            return "小树很开心！谢谢你 🌸"
        return "小树正在生长中 🌱"

    def stats(self) -> dict:
        return self._last_vitals or self.measure()

    def hardware_json(self) -> dict:
        """Minimal JSON for low-bandwidth hardware polling."""
        v = self.measure()
        return {
            "t": v["timestamp"],
            "cpu": v["cpu"]["percent"],
            "cpu_l": v["cpu"]["level"],
            "mem": v["memory"]["percent"],
            "mem_l": v["memory"]["level"],
            "led": v["led"]["color_hex"],
            "led_b": v["led"]["brightness"],
            "led_p": v["led"]["pulse_rate"],
            "emo": v["emotion"]["label"],
            "chime": v["sound"]["play_chime"],
            "leaf": v["leaf_display"]["state"],
            "leaf_m": v["leaf_display"]["message"],
        }


_instance: Optional[VitalsMonitor] = None


def get_vitals() -> VitalsMonitor:
    global _instance
    if _instance is None:
        _instance = VitalsMonitor()
    return _instance
