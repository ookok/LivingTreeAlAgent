"""
通知服务
=========

使用 plyer 实现跨平台桌面通知。

功能：
1. 桌面通知弹窗
2. 通知历史记录
3. 通知过滤
4. 免打扰模式
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# plyer - 跨平台桌面通知
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False
    logger.warning("plyer not installed. Desktop notifications disabled.")


class NotificationLevel(Enum):
    """通知级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class Notification:
    """通知对象"""
    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    account_id: str = ""
    email_subject: str = ""
    email_sender: str = ""
    timestamp: float = field(default_factory=time.time)
    icon: str = ""
    timeout: float = 10.0                  # 显示时长（秒）
    click_callback: Optional[Callable] = None
    dismissed: bool = False


class NotificationService:
    """
    通知服务

    管理桌面通知的发送和历史。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._history: List[Notification] = []
        self._max_history = 100
        self._do_not_disturb = False
        self._filters: List[Callable] = []
        self._observers: Dict[str, List[Callable]] = {}

    @classmethod
    def get_instance(cls) -> 'NotificationService':
        return cls()

    # ==================== 通知发送 ====================

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        account_id: str = "",
        timeout: float = 10.0,
        icon: str = "",
    ) -> Notification:
        """
        发送通知

        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            account_id: 账户ID（用于追踪）
            timeout: 显示时长
            icon: 图标路径

        Returns:
            Notification 对象
        """
        # 免打扰模式
        if self._do_not_disturb:
            logger.debug("Notifications muted (Do Not Disturb)")
            return None

        # 应用过滤器
        for f in self._filters:
            if not f(title, message, level):
                logger.debug(f"Notification filtered: {title}")
                return None

        # 创建通知对象
        notification_obj = Notification(
            title=title,
            message=message,
            level=level,
            account_id=account_id,
            timeout=timeout,
            icon=icon,
        )

        # 发送桌面通知
        if HAS_PLYER:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Hermes Desktop",
                    timeout=timeout,
                )
                logger.info(f"Notification sent: {title}")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

        # 记录历史
        self._add_to_history(notification_obj)

        # 通知观察者
        self._notify_observers("notification_sent", notification_obj)

        return notification_obj

    def notify_email(
        self,
        account_id: str,
        sender: str,
        subject: str,
        preview: str = "",
        click_callback: Optional[Callable] = None,
    ) -> Optional[Notification]:
        """
        发送邮件通知

        Args:
            account_id: 账户ID
            sender: 发件人
            subject: 邮件主题
            preview: 预览内容
            click_callback: 点击回调

        Returns:
            Notification 对象
        """
        title = f"📧 新邮件: {sender}"

        # 截断预览
        if len(preview) > 100:
            preview = preview[:100] + "..."

        message = subject
        if preview:
            message = f"{subject}\n{preview}"

        notification_obj = self.notify(
            title=title,
            message=message,
            level=NotificationLevel.INFO,
            account_id=account_id,
            timeout=10.0,
        )

        if notification_obj:
            notification_obj.email_subject = subject
            notification_obj.email_sender = sender
            notification_obj.click_callback = click_callback

        return notification_obj

    def notify_error(
        self,
        title: str,
        message: str,
        account_id: str = "",
    ) -> Notification:
        """发送错误通知"""
        return self.notify(
            title=f"❌ {title}",
            message=message,
            level=NotificationLevel.ERROR,
            account_id=account_id,
            timeout=15.0,
        )

    def notify_success(
        self,
        title: str,
        message: str,
        account_id: str = "",
    ) -> Notification:
        """发送成功通知"""
        return self.notify(
            title=f"✅ {title}",
            message=message,
            level=NotificationLevel.SUCCESS,
            account_id=account_id,
            timeout=5.0,
        )

    # ==================== 历史管理 ====================

    def _add_to_history(self, notification: Notification):
        """添加到历史"""
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 50) -> List[Notification]:
        """获取通知历史"""
        return self._history[-limit:]

    def clear_history(self):
        """清空历史"""
        self._history.clear()

    def mark_dismissed(self, timestamp: float):
        """标记通知已读"""
        for n in reversed(self._history):
            if n.timestamp == timestamp:
                n.dismissed = True
                break

    # ==================== 免打扰 ====================

    def set_do_not_disturb(self, enabled: bool):
        """设置免打扰"""
        self._do_not_disturb = enabled
        logger.info(f"Do Not Disturb: {enabled}")

    def is_do_not_disturb(self) -> bool:
        """是否免打扰"""
        return self._do_not_disturb

    def toggle_do_not_disturb(self) -> bool:
        """切换免打扰状态"""
        self._do_not_disturb = not self._do_not_disturb
        return self._do_not_disturb

    # ==================== 过滤器 ====================

    def add_filter(self, filter_func: Callable[[str, str, NotificationLevel], bool]):
        """添加过滤器"""
        self._filters.append(filter_func)

    def remove_filter(self, filter_func: Callable) -> bool:
        """移除过滤器"""
        try:
            self._filters.remove(filter_func)
            return True
        except ValueError:
            return False

    def clear_filters(self):
        """清空过滤器"""
        self._filters.clear()

    # ==================== 观察者 ====================

    def add_observer(self, event: str, callback: Callable):
        """添加观察者"""
        if event not in self._observers:
            self._observers[event] = []
        self._observers[event].append(callback)

    def _notify_observers(self, event: str, data: Any):
        """通知观察者"""
        for callback in self._observers.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Observer callback error: {e}")

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._history)
        by_level = {}
        for n in self._history:
            level_key = n.level.value
            by_level[level_key] = by_level.get(level_key, 0) + 1

        return {
            "total": total,
            "do_not_disturb": self._do_not_disturb,
            "by_level": by_level,
            "filter_count": len(self._filters),
        }


def get_notification_service() -> NotificationService:
    """获取通知服务单例"""
    return NotificationService.get_instance()
