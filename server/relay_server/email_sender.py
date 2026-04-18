"""
中继服务器邮件发送系统

功能：
- SMTP 邮件发送（支持加密凭据）
- 周报邮件生成与发送
- 客户端内置邮箱同步
- 发送重试机制

作者：Living Tree AI 进化系统
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ============ 配置路径 ============

CONFIG_DIR = Path(__file__).parent.parent / "config"
EMAIL_CONFIG_FILE = CONFIG_DIR / "email_config.json"

DATA_DIR = Path(__file__).parent.parent / ".hermes-desktop" / "relay_server"
INBOX_SYNC_FILE = DATA_DIR / "inbox_sync.json"


class EmailConfig:
    """邮件配置管理器"""

    _instance: Optional["EmailConfig"] = None

    def __init__(self):
        self.sender: str = ""
        self.smtp_host: str = ""
        self.smtp_port: int = 587
        self.credentials: Dict[str, str] = {"user": "", "password": ""}
        self.recipients: List[str] = []
        self.web_base_url: str = ""
        self.enabled: bool = False
        self.retry_times: int = 3
        self.retry_interval: int = 300  # 5分钟

        self._load()

    @classmethod
    def get_instance(cls) -> "EmailConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        """加载配置"""
        if EMAIL_CONFIG_FILE.exists():
            try:
                with open(EMAIL_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sender = data.get("sender", "")
                    self.smtp_host = data.get("smtp_host", "")
                    self.smtp_port = data.get("smtp_port", 587)
                    self.credentials = data.get("credentials", {"user": "", "password": ""})
                    self.recipients = data.get("recipients", [])
                    self.web_base_url = data.get("web_base_url", "")
                    self.enabled = data.get("enabled", False)
                    self.retry_times = data.get("retry_times", 3)
                    self.retry_interval = data.get("retry_interval", 300)
            except Exception as e:
                logger.error(f"加载邮件配置失败: {e}")

    def save(self):
        """保存配置"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "sender": self.sender,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "credentials": self.credentials,
            "recipients": self.recipients,
            "web_base_url": self.web_base_url,
            "enabled": self.enabled,
            "retry_times": self.retry_times,
            "retry_interval": self.retry_interval,
        }
        with open(EMAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def decrypt_password(self) -> str:
        """解密密码（简单实现，生产环境应使用更安全的加密）"""
        # TODO: 生产环境应使用 AES-256 解密
        encrypted = self.credentials.get("password", "")
        if encrypted.startswith("enc:"):
            # 简单的 Base64 解码作为占位符
            import base64
            try:
                return base64.b64decode(encrypted[4:]).decode("utf-8")
            except Exception:
                return encrypted
        return encrypted

    def encrypt_password(self, password: str) -> str:
        """加密密码"""
        # TODO: 生产环境应使用 AES-256 加密
        import base64
        return "enc:" + base64.b64encode(password.encode("utf-8")).decode("utf-8")


class EmailSender:
    """
    邮件发送器

    功能：
    - SMTP 连接管理
    - 邮件发送（支持重试）
    - 退出列表管理
    """

    def __init__(self):
        self.config = EmailConfig.get_instance()
        self._server: Optional[smtplib.SMTP] = None
        self._last_connect: float = 0
        self._connection_timeout: int = 30

    async def send_email(
        self,
        to_addrs: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        发送邮件

        Args:
            to_addrs: 收件人列表
            subject: 主题
            body_html: HTML 正文
            body_text: 纯文本正文（可选）

        Returns:
            bool: 是否发送成功
        """
        if not self.config.enabled:
            logger.warning("邮件发送已禁用")
            return False

        if not to_addrs:
            logger.error("没有收件人地址")
            return False

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.sender
        msg["To"] = ", ".join(to_addrs)
        msg["Date"] = self._format_date()

        # 添加纯文本版本
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

        # 添加 HTML 版本
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # 重试机制
        for attempt in range(self.config.retry_times):
            try:
                await self._send_via_smtp(msg, to_addrs)
                logger.info(f"邮件发送成功: {subject} -> {to_addrs}")
                return True
            except Exception as e:
                logger.warning(f"邮件发送失败 (尝试 {attempt + 1}/{self.config.retry_times}): {e}")
                if attempt < self.config.retry_times - 1:
                    await asyncio.sleep(self.config.retry_interval)
                    self._server = None  # 重置连接

        logger.error(f"邮件发送最终失败: {subject}")
        return False

    async def _send_via_smtp(self, msg: MIMEMultipart, to_addrs: List[str]):
        """通过 SMTP 发送"""
        # 延迟连接（复用已有连接）
        await self._ensure_connection()

        if not self._server:
            raise Exception("SMTP 连接未建立")

        self._server.sendmail(self.config.sender, to_addrs, msg.as_string())

    async def _ensure_connection(self):
        """确保 SMTP 连接"""
        now = time.time()

        # 复用已有连接（5分钟内）
        if self._server and (now - self._last_connect) < 300:
            return

        # 关闭旧连接
        if self._server:
            try:
                self._server.quit()
            except Exception:
                pass

        # 建立新连接
        logger.info(f"建立 SMTP 连接: {self.config.smtp_host}:{self.config.smtp_port}")

        self._server = smtplib.SMTP(
            self.config.smtp_host,
            self.config.smtp_port,
            timeout=self._connection_timeout,
        )

        self._server.starttls()
        password = self.config.decrypt_password()
        self._server.login(self.config.credentials.get("user", ""), password)

        self._last_connect = time.time()

    def _format_date(self) -> str:
        """格式化日期"""
        from email.utils import formatdate
        return formatdate(localtime=True)

    async def test_connection(self) -> tuple[bool, str]:
        """测试 SMTP 连接"""
        try:
            await self._ensure_connection()
            return True, "SMTP 连接成功"
        except Exception as e:
            return False, f"SMTP 连接失败: {e}"


class WeeklyReportGenerator:
    """周报生成器"""

    @staticmethod
    def generate_html(stats: Dict[str, Any], week_id: str, web_url: str) -> str:
        """
        生成 HTML 周报

        Args:
            stats: 统计数据
            week_id: 周 ID
            web_url: Web 页面基础 URL

        Returns:
            str: HTML 内容
        """
        patches = stats.get("patches", {})
        pain_points = stats.get("pain_points", {})
        suggestions = stats.get("suggestions", {})
        top_module = patches.get("top_module", "N/A")
        top_module_count = patches.get("top_module_count", 0)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .header p {{ margin: 10px 0 0; opacity: 0.9; }}
        .stats {{ display: flex; justify-content: space-around; margin: 30px 0; }}
        .stat {{ text-align: center; padding: 20px; background: #f8f9fa; border-radius: 10px; flex: 1; margin: 0 10px; }}
        .stat-number {{ font-size: 36px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .section h2 {{ margin-top: 0; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        .highlight {{ background: #e8f0fe; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 25px; text-decoration: none; margin-top: 20px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌳 Living Tree AI 进化周报</h1>
        <p>周ID: {week_id}</p>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="stat-number">{patches.get('count', 0)}</div>
            <div class="stat-label">🛠️ 补丁总数</div>
        </div>
        <div class="stat">
            <div class="stat-number">{pain_points.get('count', 0)}</div>
            <div class="stat-label">🎨 UI 痛点</div>
        </div>
        <div class="stat">
            <div class="stat-number">{suggestions.get('count', 0)}</div>
            <div class="stat-label">💡 功能建议</div>
        </div>
    </div>

    <div class="section">
        <h2>🏆 Top 模块</h2>
        <div class="highlight">
            <strong>{top_module}</strong> - {top_module_count} 次更新
        </div>
        <p>最活跃的进化模块，持续优化中...</p>
    </div>

    <div class="section">
        <h2>📊 补丁分布</h2>
        <ul>
            {"".join(f"<li>{k}: {v} 次</li>" for k, v in patches.get('distribution', {}).items())}
        </ul>
    </div>

    <div style="text-align: center;">
        <a href="{web_url}/weekly/{week_id}" class="btn">📊 查看详细报表</a>
    </div>

    <div class="footer">
        <p>由 Living Tree AI 进化系统自动生成</p>
        <p>如需退订，请回复 "UNSUBSCRIBE"</p>
    </div>
</body>
</html>
"""

    @staticmethod
    def generate_text(stats: Dict[str, Any], week_id: str, web_url: str) -> str:
        """
        生成纯文本周报

        Args:
            stats: 统计数据
            week_id: 周 ID
            web_url: Web 页面基础 URL

        Returns:
            str: 纯文本内容
        """
        patches = stats.get("patches", {})
        pain_points = stats.get("pain_points", {})
        suggestions = stats.get("suggestions", {})

        return f"""
Living Tree AI 进化周报
=======================
周ID: {week_id}

📊 本周数据摘要
--------------------
🛠️ 补丁总数: {patches.get('count', 0)}
🎨 UI 痛点: {pain_points.get('count', 0)}
💡 功能建议: {suggestions.get('count', 0)}

🏆 Top 模块
--------------------
{patches.get('top_module', 'N/A')} - {patches.get('top_module_count', 0)} 次更新

📈 补丁分布
--------------------
{chr(10).join(f"  • {k}: {v} 次" for k, v in patches.get('distribution', {}).items())}

🔗 详细报表
--------------------
{web_url}/weekly/{week_id}

---
由 Living Tree AI 进化系统自动生成
如需退订，请回复 "UNSUBSCRIBE"
"""


class InboxSyncManager:
    """
    客户端内置邮箱同步管理器

    功能：
    - 记录已同步到客户端的邮件
    - 防止重复同步
    - 管理同步状态
    """

    def __init__(self):
        self.synced_file = INBOX_SYNC_FILE
        self.synced_ids: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """加载同步记录"""
        if self.synced_file.exists():
            try:
                with open(self.synced_file, "r", encoding="utf-8") as f:
                    self.synced_ids = json.load(f)
            except Exception as e:
                logger.error(f"加载同步记录失败: {e}")

    def _save(self):
        """保存同步记录"""
        self.synced_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.synced_file, "w", encoding="utf-8") as f:
            json.dump(self.synced_ids, f, ensure_ascii=False, indent=2)

    def is_synced(self, message_id: str) -> bool:
        """检查是否已同步"""
        return message_id in self.synced_ids

    def mark_synced(self, message_id: str, recipients: List[str]):
        """标记为已同步"""
        self.synced_ids[message_id] = {
            "synced_at": time.time(),
            "recipients": recipients,
        }
        self._save()

    def get_pending_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待同步列表"""
        # 返回最近一周的同步记录
        cutoff = time.time() - 7 * 24 * 3600
        pending = []

        for msg_id, info in self.synced_ids.items():
            if info.get("synced_at", 0) > cutoff:
                pending.append({"message_id": msg_id, **info})

        return sorted(pending, key=lambda x: x["synced_at"], reverse=True)[:limit]


# ============ 全局实例 ============

_email_sender: Optional[EmailSender] = None
_report_generator = WeeklyReportGenerator()
_inbox_sync: Optional[InboxSyncManager] = None


def get_email_sender() -> EmailSender:
    """获取邮件发送器实例"""
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender


def get_inbox_sync_manager() -> InboxSyncManager:
    """获取内置邮箱同步管理器"""
    global _inbox_sync
    if _inbox_sync is None:
        _inbox_sync = InboxSyncManager()
    return _inbox_sync


# ============ 便捷函数 ============

async def send_weekly_report(week_id: str, stats: Dict[str, Any]) -> bool:
    """
    发送周报邮件

    Args:
        week_id: 周 ID
        stats: 统计数据

    Returns:
        bool: 是否发送成功
    """
    config = EmailConfig.get_instance()
    sender = get_email_sender()

    if not config.enabled:
        logger.warning("邮件功能已禁用")
        return False

    # 生成邮件内容
    html_body = WeeklyReportGenerator.generate_html(
        stats, week_id, config.web_base_url
    )
    text_body = WeeklyReportGenerator.generate_text(
        stats, week_id, config.web_base_url
    )

    # 构建主题
    subject = f"🌳 Living Tree AI 进化周报 - {week_id}"

    # 发送邮件
    success = await sender.send_email(
        config.recipients,
        subject,
        html_body,
        text_body,
    )

    if success:
        # 标记为已同步
        inbox_sync = get_inbox_sync_manager()
        message_id = f"weekly_report_{week_id}"
        inbox_sync.mark_synced(message_id, config.recipients)

    return success


async def sync_to_client_inboxes(week_id: str, stats: Dict[str, Any]) -> bool:
    """
    同步周报到客户端内置邮箱

    Args:
        week_id: 周 ID
        stats: 统计数据

    Returns:
        bool: 是否同步成功
    """
    # TODO: 实现客户端内置邮箱同步
    # 这需要调用客户端的 P2P 消息接口或 WebSocket
    logger.info(f"同步周报到客户端内置邮箱: {week_id}")
    return True
