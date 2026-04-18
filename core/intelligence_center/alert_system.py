# -*- coding: utf-8 -*-
"""
Alert System 预警与分发系统
Intelligence Center - Alert & Notification System
"""

import asyncio
import logging
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self):
        return self.name


class AlertChannel(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SYSTEM = "system"


@dataclass
class Alert:
    """预警消息"""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: AlertLevel = AlertLevel.INFO

    title: str = ""
    description: str = ""
    content: str = ""

    source_type: str = ""  # rumor/competitor/sentiment
    source_id: str = ""
    related_ids: List[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending/sent/failed
    sent_channels: List[str] = field(default_factory=list)


@dataclass
class EmailConfig:
    """邮件配置"""
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    username: str = ""
    password: str = ""
    from_addr: str = ""


@dataclass
class WebhookConfig:
    """Webhook配置"""
    enabled: bool = False
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    secret: str = ""


@dataclass
class NotificationRule:
    """通知规则"""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""

    # 触发条件
    min_level: AlertLevel = AlertLevel.INFO
    source_types: List[str] = field(default_factory=list)  # 空=全部
    keywords_filter: List[str] = field(default_factory=list)  # 包含关键词
    exclude_keywords: List[str] = field(default_factory=list)  # 排除关键词

    # 发送渠道
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.SYSTEM])
    email_recipients: List[str] = field(default_factory=list)

    enabled: bool = True


class AlertManager:
    """预警管理器"""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.rules: Dict[str, NotificationRule] = {}
        self.history: List[Alert] = []

        # 渠道配置
        self.email_config = EmailConfig()
        self.webhook_config = WebhookConfig()

        # 回调
        self.callbacks: List[Callable] = []

    def set_email_config(self, config: EmailConfig):
        self.email_config = config

    def set_webhook_config(self, config: WebhookConfig):
        self.webhook_config = config

    def add_rule(self, rule: NotificationRule) -> str:
        self.rules[rule.rule_id] = rule
        return rule.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False

    def list_rules(self) -> List[NotificationRule]:
        return list(self.rules.values())

    def register_callback(self, callback: Callable):
        """注册预警回调"""
        self.callbacks.append(callback)

    async def create_alert(
        self,
        level: AlertLevel,
        title: str,
        description: str = "",
        content: str = "",
        source_type: str = "",
        source_id: str = "",
        related_ids: Optional[List[str]] = None,
    ) -> Alert:
        """创建预警"""
        alert = Alert(
            level=level,
            title=title,
            description=description,
            content=content,
            source_type=source_type,
            source_id=source_id,
            related_ids=related_ids or [],
        )

        self.alerts[alert.alert_id] = alert
        await self._process_alert(alert)

        return alert

    async def _process_alert(self, alert: Alert):
        """处理预警"""
        # 检查规则匹配
        matched_rules = self._match_rules(alert)

        if not matched_rules:
            logger.debug(f"预警 {alert.alert_id} 无匹配规则")
            return

        # 发送通知
        for rule in matched_rules:
            await self._send_via_channels(alert, rule)

        # 执行回调
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"回调执行失败: {e}")

        # 移入历史
        self.history.append(alert)
        if len(self.history) > 1000:
            self.history = self.history[-500:]

    def _match_rules(self, alert: Alert) -> List[NotificationRule]:
        """匹配规则"""
        matched = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            # 级别检查
            if alert.level.value < rule.min_level.value:
                continue

            # 来源检查
            if rule.source_types and alert.source_type not in rule.source_types:
                continue

            # 关键词过滤
            if rule.keywords_filter:
                if not any(kw in alert.title or kw in alert.content for kw in rule.keywords_filter):
                    continue

            # 排除关键词
            if rule.exclude_keywords:
                if any(kw in alert.title or kw in alert.content for kw in rule.exclude_keywords):
                    continue

            matched.append(rule)

        return matched

    async def _send_via_channels(self, alert: Alert, rule: NotificationRule):
        """通过渠道发送"""
        for channel in rule.channels:
            try:
                if channel == AlertChannel.EMAIL:
                    await self._send_email(alert, rule.email_recipients)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook(alert)
                elif channel == AlertChannel.SYSTEM:
                    self._send_system(alert)
            except Exception as e:
                logger.error(f"发送预警失败 [{channel.value}]: {e}")
                alert.status = "failed"
            else:
                alert.sent_channels.append(channel.value)
                alert.status = "sent"

    async def _send_email(self, alert: Alert, recipients: List[str]):
        """发送邮件"""
        if not self.email_config.enabled or not recipients:
            return

        config = self.email_config
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.level.name}] {alert.title}"
        msg["From"] = config.from_addr or config.username
        msg["To"] = ", ".join(recipients)

        # 纯文本版本
        text_content = f"""
预警级别: {alert.level.name}
时间: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

{alert.description}

{alert.content}
        """.strip()

        msg.attach(MIMEText(text_content, "plain"))

        # HTML版本
        html_content = f"""
        <html><body>
        <h2 style="color: {'red' if alert.level.value >= 3 else 'orange'}">{alert.title}</h2>
        <p><strong>级别:</strong> {alert.level.name}</p>
        <p><strong>时间:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>来源:</strong> {alert.source_type}</p>
        <hr/>
        <p>{alert.description}</p>
        <pre>{alert.content}</pre>
        </body></html>
        """.strip()

        msg.attach(MIMEText(html_content, "html"))

        # 发送
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            if config.use_tls:
                server.starttls()
            if config.username and config.password:
                server.login(config.username, config.password)
            server.send_message(msg)

        logger.info(f"邮件预警已发送: {alert.alert_id}")

    async def _send_webhook(self, alert: Alert):
        """发送Webhook"""
        if not self.webhook_config.enabled:
            return

        import httpx

        payload = {
            "alert_id": alert.alert_id,
            "level": alert.level.name,
            "title": alert.title,
            "description": alert.description,
            "content": alert.content,
            "source_type": alert.source_type,
            "created_at": alert.created_at.isoformat(),
        }

        headers = self.webhook_config.headers.copy()
        if self.webhook_config.secret:
            import hmac
            import hashlib
            import json
            body = json.dumps(payload)
            signature = hmac.new(
                self.webhook_config.secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Signature"] = signature

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_config.url,
                json=payload,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

        logger.info(f"Webhook预警已发送: {alert.alert_id}")

    def _send_system(self, alert: Alert):
        """系统通知"""
        logger.info(f"系统预警: [{alert.level.name}] {alert.title}")

    def get_recent_alerts(self, limit: int = 50) -> List[Alert]:
        """获取最近预警"""
        return sorted(self.history, key=lambda x: x.created_at, reverse=True)[:limit]

    def get_alert_stats(self) -> Dict[str, Any]:
        """获取预警统计"""
        stats = {
            "total": len(self.history),
            "by_level": {},
            "by_source": {},
            "by_status": {},
        }

        for alert in self.history:
            # 按级别
            level = alert.level.name
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

            # 按来源
            source = alert.source_type or "unknown"
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

            # 按状态
            status = alert.status
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        return stats


__all__ = ["AlertLevel", "AlertChannel", "Alert", "EmailConfig", "WebhookConfig",
           "NotificationRule", "AlertManager"]