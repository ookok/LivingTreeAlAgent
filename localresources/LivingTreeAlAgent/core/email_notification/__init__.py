"""
邮件提醒系统 - Hermes Desktop 邮件监控通知模块
==============================================

技术栈组合：
- IMAPClient: 邮箱协议监听（底层引擎）
- PyQt QSystemTrayIcon: 托盘图标 + 菜单（界面）
- plyer: 跨平台桌面通知（通知）

核心设计：
1. IMAP IDLE 模式监听新邮件
2. 多账户支持
3. 系统托盘最小化
4. 桌面通知提醒
5. 与插件框架集成

Author: Hermes Desktop Team
"""

from .email_account import EmailAccount, EmailMessage, EmailProvider
from .imap_listener import IMAPListener, IMAPListenerManager
from .notification_service import NotificationService
from .tray_manager import TrayManager, EmailTrayIcon
from .config_manager import EmailConfigManager, load_config, save_config

__all__ = [
    # 账户与邮件
    'EmailAccount',
    'EmailMessage',
    'EmailProvider',
    # IMAP监听
    'IMAPListener',
    'IMAPListenerManager',
    # 通知
    'NotificationService',
    # 托盘
    'TrayManager',
    'EmailTrayIcon',
    # 配置
    'EmailConfigManager',
    'load_config',
    'save_config',
]
