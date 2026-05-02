"""
Real-time Tracker — Compatibility Stub
"""


class RealtimeTracker:
    def __init__(self):
        self._events = []

    def track(self, event: str, data: dict = None):
        self._events.append({"event": event, "data": data})

    def recent(self, limit: int = 20) -> list:
        return self._events[-limit:]


__all__ = ["RealtimeTracker"]
