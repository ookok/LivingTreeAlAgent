"""
邮件配置管理器
==============

管理邮件账户配置的持久化。
支持从 UnifiedConfig 读取配置。
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from pathlib import Path

from .email_account import EmailAccount

if TYPE_CHECKING:
    from core.config.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)

# 配置路径
CONFIG_DIR = Path.home() / ".workbuddy" / "email_notification"
CONFIG_FILE = CONFIG_DIR / "accounts.json"


class UnifiedConfigMixin:
    """
    统一配置混入类
    
    从 UnifiedConfig 读取邮件配置
    """
    
    _unified_config: Optional["UnifiedConfig"] = None
    
    def _get_unified_config(self) -> "UnifiedConfig":
        """获取统一配置实例"""
        if self._unified_config is None:
            from core.config.unified_config import UnifiedConfig
            self._unified_config = UnifiedConfig.get_instance()
        return self._unified_config
    
    def is_email_enabled(self) -> bool:
        """检查邮件功能是否启用"""
        unified = self._get_unified_config()
        return unified.get("email.enabled", False)
    
    def get_smtp_config(self) -> Dict[str, Any]:
        """获取SMTP配置"""
        unified = self._get_unified_config()
        return unified.get("email.smtp", {})
    
    def get_notification_config(self) -> Dict[str, Any]:
        """获取通知配置"""
        unified = self._get_unified_config()
        return unified.get("email.notification", {})


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> List[EmailAccount]:
    """
    加载配置

    Returns:
        EmailAccount 列表
    """
    if not CONFIG_FILE.exists():
        return []

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        accounts = []
        for acc_data in data.get("accounts", []):
            try:
                accounts.append(EmailAccount.from_dict(acc_data))
            except Exception as e:
                logger.error(f"Failed to load account: {e}")

        return accounts

    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return []


def save_config(accounts: List[EmailAccount]) -> bool:
    """
    保存配置

    Args:
        accounts: EmailAccount 列表

    Returns:
        是否成功
    """
    try:
        ensure_config_dir()

        data = {
            "version": 1,
            "accounts": [acc.to_dict() for acc in accounts],
        }

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(accounts)} accounts")
        return True

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


class EmailConfigManager(UnifiedConfigMixin):
    """
    邮件配置管理器

    提供配置的增删改查操作。
    支持从 UnifiedConfig 读取邮件系统配置。
    """

    def __init__(self):
        self._accounts: List[EmailAccount] = []
        self._load()
    
    def is_system_enabled(self) -> bool:
        """检查邮件系统是否启用（从统一配置）"""
        return self.is_email_enabled()
    
    def get_notification_types(self) -> Dict[str, bool]:
        """获取启用的通知类型"""
        return self.get_notification_config()

    def _load(self):
        """加载配置"""
        self._accounts = load_config()

    def reload(self):
        """重新加载"""
        self._load()

    def get_accounts(self) -> List[EmailAccount]:
        """获取所有账户"""
        return self._accounts.copy()

    def get_account(self, account_id: str) -> Optional[EmailAccount]:
        """获取单个账户"""
        for acc in self._accounts:
            if acc.account_id == account_id:
                return acc
        return None

    def add_account(self, account: EmailAccount) -> bool:
        """
        添加账户

        Args:
            account: EmailAccount 实例

        Returns:
            是否成功
        """
        # 检查是否已存在
        if self.get_account(account.account_id):
            logger.warning(f"Account {account.account_id} already exists")
            return False

        self._accounts.append(account)
        return save_config(self._accounts)

    def update_account(self, account: EmailAccount) -> bool:
        """
        更新账户

        Args:
            account: EmailAccount 实例

        Returns:
            是否成功
        """
        for i, acc in enumerate(self._accounts):
            if acc.account_id == account.account_id:
                self._accounts[i] = account
                return save_config(self._accounts)

        logger.warning(f"Account {account.account_id} not found")
        return False

    def remove_account(self, account_id: str) -> bool:
        """
        移除账户

        Args:
            account_id: 账户ID

        Returns:
            是否成功
        """
        self._accounts = [acc for acc in self._accounts if acc.account_id != account_id]
        return save_config(self._accounts)

    def set_account_active(self, account_id: str, active: bool) -> bool:
        """
        设置账户激活状态

        Args:
            account_id: 账户ID
            active: 是否激活

        Returns:
            是否成功
        """
        account = self.get_account(account_id)
        if account:
            account.is_active = active
            return save_config(self._accounts)
        return False

    def get_active_accounts(self) -> List[EmailAccount]:
        """获取所有激活的账户"""
        return [acc for acc in self._accounts if acc.is_active]

    def get_accounts_by_provider(self, provider) -> List[EmailAccount]:
        """按服务商获取账户"""
        return [acc for acc in self._accounts if acc.provider == provider]


# 全局实例
_config_manager: Optional[EmailConfigManager] = None


def get_config_manager() -> EmailConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = EmailConfigManager()
    return _config_manager
