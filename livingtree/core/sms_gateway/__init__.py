"""
LivingTree 智能短信网关
======================

Full migration from client/src/business/sms_gateway/

核心功能：统一入口、策略模式多渠道路由、Redis原子计数、熔断机制、邮件兜底。
"""

from .sms_gateway import (
    SmsGateway,
    get_sms_gateway,
    SmsChannel,
    ChannelStatus,
    ChannelConfig,
    EmailConfig,
    SmsResult,
    GatewayStats,
    setup_monthly_reset,
)

__all__ = [
    "SmsGateway",
    "get_sms_gateway",
    "SmsChannel",
    "ChannelStatus",
    "ChannelConfig",
    "EmailConfig",
    "SmsResult",
    "GatewayStats",
    "setup_monthly_reset",
]
