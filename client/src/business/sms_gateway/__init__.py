"""
智能短信网关 (Smart SMS Gateway)

核心功能：
1. 统一入口：对外提供 send_sms() 接口
2. 策略模式：封装阿里云、腾讯云短信服务
3. 额度计数器：利用 Redis 做原子计数
4. 智能路由：自动选择最划算（免费）的渠道
5. 熔断机制：额度耗尽自动切换，触发告警
6. 自动重置：定时任务每月重置额度
7. 邮箱兜底：短信不可用时自动发送邮件通知

目标：将阿里云（100条/月）+ 腾讯云（1000条/月）免费额度无缝叠加。

默认邮箱配置：
- 发件邮箱：okyin666@126.com
- SMTP服务器：smtp.126.com:465

使用方法：
    from business.sms_gateway import get_sms_gateway
    
    gateway = get_sms_gateway()
    
    # 发送短信（自动选择渠道，失败自动切换邮件）
    result = gateway.send_sms("13800138000", code="123456")
    
    # 直接发送邮件
    gateway.send_email("user@example.com", "主题", "内容")
    
    # 添加告警回调
    def alert_callback(message, details):
        print(f"告警: {message}")
    
    gateway.add_alert_callback(alert_callback)
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