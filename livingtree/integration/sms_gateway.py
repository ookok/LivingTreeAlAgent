"""SMS gateway stub."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SmsConfig:
    provider: str = ""
    api_key: str = ""
    api_secret: str = ""
    sign_name: str = ""
    template_code: str = ""
    phone_numbers: list = field(default_factory=list)
    enabled: bool = False


class SmsGateway:
    def __init__(self, config: Optional[SmsConfig] = None):
        self.config = config or SmsConfig()

    async def send(self, message: str, phone: Optional[str] = None) -> bool:
        return False

    def send_sync(self, message: str, phone: Optional[str] = None) -> bool:
        return False


_sms_gateway: Optional[SmsGateway] = None


def get_sms_gateway(config: Optional[SmsConfig] = None) -> SmsGateway:
    global _sms_gateway
    if _sms_gateway is None:
        _sms_gateway = SmsGateway(config)
    return _sms_gateway
