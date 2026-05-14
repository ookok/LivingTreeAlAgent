"""TemporalPredictor — Time-series forecasting for system resource usage.

Combines exponential smoothing for short-term prediction with simple
decomposition for seasonal patterns. Predicts: request volume, latency,
budget consumption, error rates over next 24 hours.

Used by SurvivalMode for proactive resource adjustment.

Integration:
  pred = get_temporal_predictor()
  forecast = pred.forecast_requests(hours=24)  # → {hour: predicted}
  anomaly = pred.detect_anomaly(current_value)  # → True/False
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

HISTORY_FILE = Path(".livingtree/temporal_history.json")


@dataclass
class ForecastPoint:
    timestamp: float
    value: float
    lower: float = 0.0
    upper: float = 0.0


class TemporalPredictor:
    """Time-series prediction with exponential smoothing and anomaly detection."""

    _instance: Optional["TemporalPredictor"] = None

    @classmethod
    def instance(cls) -> "TemporalPredictor":
        if cls._instance is None:
            cls._instance = TemporalPredictor()
        return cls._instance

    def __init__(self):
        self._hourly_data: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._forecasts = 0
        self._load()

    # ── Recording ──────────────────────────────────────────────────

    def record(self, metric: str, value: float, hour: int = -1):
        """Record a metric value for a given hour."""
        if hour < 0:
            hour = time.localtime().tm_hour
        self._hourly_data[metric][hour].append(value)
        # Keep last 30 values per hour
        if len(self._hourly_data[metric][hour]) > 30:
            self._hourly_data[metric][hour] = self._hourly_data[metric][hour][-30:]
        if self._forecasts % 50 == 0:
            self._save()

    # ── Forecasting ────────────────────────────────────────────────

    def forecast(self, metric: str, hours: int = 24) -> list[ForecastPoint]:
        """Forecast metric values for the next N hours using double exponential smoothing."""
        self._forecasts += 1
        now = time.time()
        current_hour = time.localtime().tm_hour

        # Get historical hourly averages
        hourly_avg = {}
        for h, values in self._hourly_data[metric].items():
            if values:
                hourly_avg[h] = sum(values) / len(values)

        if not hourly_avg:
            return []

        # Simple exponential smoothing with trend
        recent = self._get_recent_values(metric, 24)
        if not recent:
            return []

        # Double exponential smoothing
        alpha, beta = 0.3, 0.1
        level = recent[0]
        trend = 0.0
        smoothed = []
        for v in recent:
            new_level = alpha * v + (1 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1 - beta) * trend
            level, trend = new_level, new_trend
            smoothed.append(level)

        # Forecast
        current_level = level
        current_trend = trend
        forecasts = []
        std_dev = 0.0
        if len(smoothed) > 1:
            errors = [abs(smoothed[i] - recent[i]) for i in range(len(recent))]
            std_dev = sum(errors) / len(errors) * 2

        for i in range(hours):
            h = (current_hour + i) % 24
            # Blend: smoothed trend + historical hourly pattern
            seasonal = hourly_avg.get(h, current_level)
            base = current_level + current_trend * (i + 1)
            blended = base * 0.6 + seasonal * 0.4

            forecasts.append(ForecastPoint(
                timestamp=now + i * 3600,
                value=round(blended, 2),
                lower=round(max(0, blended - std_dev), 2),
                upper=round(blended + std_dev, 2),
            ))

        return forecasts

    def forecast_requests(self, hours: int = 24) -> list[ForecastPoint]:
        return self.forecast("requests", hours)

    def forecast_latency(self, hours: int = 24) -> list[ForecastPoint]:
        return self.forecast("latency", hours)

    def forecast_budget(self, hours: int = 24) -> list[ForecastPoint]:
        return self.forecast("budget_consumed", hours)

    # ── Anomaly Detection ──────────────────────────────────────────

    def detect_anomaly(self, metric: str, current_value: float,
                       threshold_std: float = 2.5) -> bool:
        """Detect if current value is anomalous (>threshold standard deviations)."""
        recent = self._get_recent_values(metric, 24)
        if len(recent) < 6:
            return False

        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        std = math.sqrt(variance)

        if std < 0.001:
            return False

        z_score = abs(current_value - mean) / std
        if z_score > threshold_std:
            logger.warning(
                f"TemporalPredictor: anomaly detected for '{metric}' "
                f"(value={current_value:.1f}, z={z_score:.1f})"
            )
            return True
        return False

    def peak_prediction(self, metric: str, hours: int = 6) -> ForecastPoint:
        """Predict peak value in the next N hours."""
        forecast = self.forecast(metric, hours)
        if not forecast:
            return ForecastPoint(timestamp=time.time(), value=0)
        return max(forecast, key=lambda f: f.value)

    # ── Helpers ────────────────────────────────────────────────────

    def _get_recent_values(self, metric: str, count: int) -> list[float]:
        """Get recent values across hours, ordered by time."""
        all_values = []
        for h in range(24):
            for v in self._hourly_data[metric].get(h, [])[-3:]:
                all_values.append(v)
        return all_values[-count:]

    def _save(self):
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                metric: {str(h): vals for h, vals in hours.items()}
                for metric, hours in self._hourly_data.items()
            }
            HISTORY_FILE.write_text(json.dumps(data))
        except Exception:
            pass

    def _load(self):
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text())
                for metric, hours in data.items():
                    for h, vals in hours.items():
                        self._hourly_data[metric][int(h)] = vals
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "metrics_tracked": len(self._hourly_data),
            "forecasts": self._forecasts,
        }


_pred: Optional[TemporalPredictor] = None


def get_temporal_predictor() -> TemporalPredictor:
    global _pred
    if _pred is None:
        _pred = TemporalPredictor()
    return _pred


__all__ = ["TemporalPredictor", "ForecastPoint", "get_temporal_predictor"]
