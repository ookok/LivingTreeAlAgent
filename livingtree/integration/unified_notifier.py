"""Unified notifier stub — adaptive multi-channel dispatcher."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NotifyResult:
    success: bool = False
    channel: str = ""
    message: str = ""
    error: Optional[str] = None


class UnifiedNotifier:
    def __init__(self):
        self._channels: dict = {}

    @property
    def available_channels(self) -> list:
        return list(self._channels.keys())

    def register_channel(self, name: str, notifier) -> None:
        self._channels[name] = notifier

    async def notify(self, message: str, channel: Optional[str] = None) -> NotifyResult:
        return NotifyResult(success=False, channel=channel or "", message="notifier not configured")

    def notify_sync(self, message: str, channel: Optional[str] = None) -> NotifyResult:
        return NotifyResult(success=False, channel=channel or "", message="notifier not configured")


_unified_notifier: Optional[UnifiedNotifier] = None


def get_unified_notifier() -> UnifiedNotifier:
    global _unified_notifier
    if _unified_notifier is None:
        _unified_notifier = UnifiedNotifier()
    return _unified_notifier
