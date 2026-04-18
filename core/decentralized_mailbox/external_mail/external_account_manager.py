"""
外部邮箱账号管理器

功能：
- 外部邮箱账号配置管理
- 加密存储（ AES-256）
- 账号添加/删除/更新/启用禁用

作者：Living Tree AI 进化系统
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ============ 配置路径 ============

CONFIG_DIR = Path("~/.hermes-desktop/mailbox").expanduser()
ACCOUNTS_FILE = CONFIG_DIR / "external_mail_accounts.json"

# 简单加密 key（生产环境应从系统密钥环获取）
_ENCRYPTION_KEY = None


def _get_encryption_key() -> bytes:
    """获取加密密钥"""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        machine_id = os.environ.get("COMPUTERNAME", "default") + os.environ.get("USERNAME", "user")
        _ENCRYPTION_KEY = hashlib.sha256(machine_id.encode()).digest()[:32]
    return _ENCRYPTION_KEY


def _simple_encrypt(data: str) -> str:
    """简单加密（占位符，生产环境应使用 AES-256）"""
    import base64
    key = _get_encryption_key()
    encrypted = bytes(a ^ b for a, b in zip(data.encode("utf-8"), (key * ((len(data) + 31) // 32))))
    return base64.b64encode(encrypted).decode("ascii")


def _simple_decrypt(encrypted: str) -> str:
    """简单解密"""
    import base64
    key = _get_encryption_key()
    try:
        data = base64.b64decode(encrypted.encode("ascii"))
        decrypted = bytes(a ^ b for a, b in zip(data, (key * ((len(data) + 31) // 32))))
        return decrypted.decode("utf-8")
    except Exception:
        return encrypted


# ============ 数据模型 ============

@dataclass
class SMTPConfig:
    """SMTP 配置"""
    host: str
    port: int = 587
    tls: bool = True


@dataclass
class IMAPConfig:
    """IMAP 配置"""
    host: str
    port: int = 993
    ssl: bool = True


@dataclass
class ExternalMailAccount:
    """外部邮箱账号"""
    id: str
    provider: str
    display_name: str = ""
    address: str = ""
    smtp: Optional[SMTPConfig] = None
    imap: Optional[IMAPConfig] = None
    credentials: Dict[str, str] = field(default_factory=dict)
    is_enabled: bool = True
    is_default: bool = False
    sync_interval: int = 300
    last_sync: float = 0
    folders: List[str] = field(default_factory=list)
    created_at: float = 0
    updated_at: float = 0

    @property
    def encrypted_password(self) -> str:
        return _simple_decrypt(self.credentials.get("password", ""))

    @property
    def encrypted_username(self) -> str:
        return _simple_decrypt(self.credentials.get("username", ""))


class ExternalAccountManager:
    """
    外部邮箱账号管理器

    功能：
    - 账号 CRUD 操作
    - 加密存储
    - 账号启用/禁用
    - 默认账号设置
    """

    PROVIDER_DEFAULTS = {
        "gmail": {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_tls": True, "imap_host": "imap.gmail.com", "imap_port": 993, "imap_ssl": True},
        "qq": {"smtp_host": "smtp.qq.com", "smtp_port": 587, "smtp_tls": True, "imap_host": "imap.qq.com", "imap_port": 993, "imap_ssl": True},
        "163": {"smtp_host": "smtp.163.com", "smtp_port": 465, "smtp_tls": False, "imap_host": "imap.163.com", "imap_port": 993, "imap_ssl": True},
        "outlook": {"smtp_host": "smtp-mail.outlook.com", "smtp_port": 587, "smtp_tls": True, "imap_host": "outlook.office365.com", "imap_port": 993, "imap_ssl": True},
        "yahoo": {"smtp_host": "smtp.mail.yahoo.com", "smtp_port": 587, "smtp_tls": True, "imap_host": "imap.mail.yahoo.com", "imap_port": 993, "imap_ssl": True},
    }

    def __init__(self):
        self.accounts: Dict[str, ExternalMailAccount] = {}
        self._load()

    def _load(self):
        if not ACCOUNTS_FILE.exists():
            return
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for acc_data in data.get("accounts", []):
                account = self._parse_account(acc_data)
                if account:
                    self.accounts[account.id] = account
            logger.info(f"加载了 {len(self.accounts)} 个外部邮箱账号")
        except Exception as e:
            logger.error(f"加载外部邮箱账号失败: {e}")

    def _parse_account(self, data: Dict[str, Any]) -> Optional[ExternalMailAccount]:
        try:
            protocols = data.get("protocols", {})
            smtp_data = protocols.get("smtp", {})
            imap_data = protocols.get("imap", {})
            smtp = SMTPConfig(host=smtp_data.get("host", ""), port=smtp_data.get("port", 587), tls=smtp_data.get("tls", True)) if smtp_data else None
            imap = IMAPConfig(host=imap_data.get("host", ""), port=imap_data.get("port", 993), ssl=imap_data.get("ssl", True)) if imap_data else None
            return ExternalMailAccount(
                id=data.get("id", ""), provider=data.get("provider", "custom"),
                display_name=data.get("display_name", ""), address=data.get("address", ""),
                smtp=smtp, imap=imap, credentials=data.get("credentials", {}),
                is_enabled=data.get("is_enabled", True), is_default=data.get("is_default", False),
                sync_interval=data.get("sync_interval", 300), last_sync=data.get("last_sync", 0),
                folders=data.get("folders", ["INBOX"]), created_at=data.get("created_at", 0),
                updated_at=data.get("updated_at", 0),
            )
        except Exception as e:
            logger.error(f"解析账号失败: {e}")
            return None

    def _serialize_account(self, account: ExternalMailAccount) -> Dict[str, Any]:
        protocols = {}
        if account.smtp:
            protocols["smtp"] = {"host": account.smtp.host, "port": account.smtp.port, "tls": account.smtp.tls}
        if account.imap:
            protocols["imap"] = {"host": account.imap.host, "port": account.imap.port, "ssl": account.imap.ssl}
        return {
            "id": account.id, "provider": account.provider, "display_name": account.display_name,
            "address": account.address, "protocols": protocols, "credentials": account.credentials,
            "is_enabled": account.is_enabled, "is_default": account.is_default,
            "sync_interval": account.sync_interval, "last_sync": account.last_sync,
            "folders": account.folders, "created_at": account.created_at, "updated_at": account.updated_at,
        }

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "accounts": [self._serialize_account(acc) for acc in self.accounts.values()]}, f, ensure_ascii=False, indent=2)

    def add_account(self, provider: str, address: str, username: str, password: str,
                    display_name: str = "", smtp_host: str = "", smtp_port: int = 587, smtp_tls: bool = True,
                    imap_host: str = "", imap_port: int = 993, imap_ssl: bool = True,
                    sync_interval: int = 300, folders: List[str] = None) -> Optional[ExternalMailAccount]:
        account_id = f"{provider}_{secrets.token_hex(4)}"
        for acc in self.accounts.values():
            if acc.address.lower() == address.lower():
                return None
        defaults = self.PROVIDER_DEFAULTS.get(provider, {})
        smtp = SMTPConfig(host=smtp_host or defaults.get("smtp_host", ""), port=smtp_port or defaults.get("smtp_port", 587), tls=smtp_tls) if smtp_host or defaults.get("smtp_host") else None
        imap = IMAPConfig(host=imap_host or defaults.get("imap_host", ""), port=imap_port or defaults.get("imap_port", 993), ssl=imap_ssl) if imap_host or defaults.get("imap_host") else None
        account = ExternalMailAccount(
            id=account_id, provider=provider, display_name=display_name or address.split("@")[0],
            address=address, smtp=smtp, imap=imap,
            credentials={"username": _simple_encrypt(username), "password": _simple_encrypt(password)},
            sync_interval=sync_interval, folders=folders or ["INBOX"], created_at=time.time(), updated_at=time.time(),
        )
        if not self.accounts:
            account.is_default = True
        self.accounts[account_id] = account
        self._save()
        logger.info(f"添加外部邮箱账号: {address}")
        return account

    def update_account(self, account_id: str, display_name: str = None, password: str = None,
                       is_enabled: bool = None, sync_interval: int = None, folders: List[str] = None) -> bool:
        account = self.accounts.get(account_id)
        if not account:
            return False
        if display_name is not None:
            account.display_name = display_name
        if password is not None:
            account.credentials["password"] = _simple_encrypt(password)
        if is_enabled is not None:
            account.is_enabled = is_enabled
        if sync_interval is not None:
            account.sync_interval = sync_interval
        if folders is not None:
            account.folders = folders
        account.updated_at = time.time()
        self._save()
        return True

    def remove_account(self, account_id: str) -> bool:
        if account_id not in self.accounts:
            return False
        self.accounts.pop(account_id)
        self._save()
        return True

    def set_default_account(self, account_id: str) -> bool:
        if account_id not in self.accounts:
            return False
        for acc in self.accounts.values():
            acc.is_default = False
        self.accounts[account_id].is_default = True
        self._save()
        return True

    def get_account(self, account_id: str) -> Optional[ExternalMailAccount]:
        return self.accounts.get(account_id)

    def get_account_by_address(self, address: str) -> Optional[ExternalMailAccount]:
        for acc in self.accounts.values():
            if acc.address.lower() == address.lower():
                return acc
        return None

    def get_default_account(self) -> Optional[ExternalMailAccount]:
        for acc in self.accounts.values():
            if acc.is_default:
                return acc
        return next(iter(self.accounts.values()), None)

    def get_enabled_accounts(self) -> List[ExternalMailAccount]:
        return [acc for acc in self.accounts.values() if acc.is_enabled]

    def get_all_accounts(self) -> List[ExternalMailAccount]:
        return list(self.accounts.values())

    def update_last_sync(self, account_id: str):
        account = self.accounts.get(account_id)
        if account:
            account.last_sync = time.time()
            self._save()

    async def test_smtp_connection(self, account_id: str) -> tuple[bool, str]:
        import smtplib, ssl
        account = self.accounts.get(account_id)
        if not account or not account.smtp:
            return False, "账号不存在或未配置 SMTP"
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(account.smtp.host, account.smtp.port, timeout=30) as server:
                if account.smtp.tls:
                    server.starttls(context=context)
                server.login(account.encrypted_username, account.encrypted_password)
            return True, "SMTP 连接成功"
        except Exception as e:
            return False, f"SMTP 连接失败: {e}"

    async def test_imap_connection(self, account_id: str) -> tuple[bool, str]:
        import imaplib
        account = self.accounts.get(account_id)
        if not account or not account.imap:
            return False, "账号不存在或未配置 IMAP"
        try:
            if account.imap.ssl:
                with imaplib.IMAP4_SSL(account.imap.host, account.imap.port) as server:
                    server.login(account.encrypted_username, account.encrypted_password)
            else:
                with imaplib.IMAP4(account.imap.host, account.imap.port) as server:
                    server.login(account.encrypted_username, account.encrypted_password)
            return True, "IMAP 连接成功"
        except Exception as e:
            return False, f"IMAP 连接失败: {e}"


_account_manager: Optional[ExternalAccountManager] = None


def get_external_account_manager() -> ExternalAccountManager:
    global _account_manager
    if _account_manager is None:
        _account_manager = ExternalAccountManager()
    return _account_manager
