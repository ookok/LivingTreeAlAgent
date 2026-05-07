"""WeChat notifier stub."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeChatConfig:
    corp_id: str = ""
    agent_id: str = ""
    secret: str = ""
    enabled: bool = False
    users: list = field(default_factory=list)


class WeChatNotifier:
    def __init__(self, config: Optional[WeChatConfig] = None):
        self.config = config or WeChatConfig()

    async def notify(self, message: str, user: Optional[str] = None) -> bool:
        return False

    def notify_sync(self, message: str, user: Optional[str] = None) -> bool:
        return False


_wechat_notifier: Optional[WeChatNotifier] = None


def get_wechat_notifier(config: Optional[WeChatConfig] = None) -> WeChatNotifier:
    global _wechat_notifier
    if _wechat_notifier is None:
        _wechat_notifier = WeChatNotifier(config)
    return _wechat_notifier
