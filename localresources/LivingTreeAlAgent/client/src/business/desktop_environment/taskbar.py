# taskbar.py — 任务栏 / Dock / 系统托盘 / 通知中心
# ============================================================================
#
# 负责桌面任务栏、通知中心、系统托盘的UI和交互
#
# ============================================================================

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
from enum import Enum

# ============================================================================
# 配置与枚举
# ============================================================================

class TaskbarPosition(Enum):
    """任务栏位置"""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"

@dataclass
class TaskbarItem:
    """任务栏项"""
    id: str                          # 唯一 ID
    icon: str = ""                   # 图标路径
    title: str = ""                  # 标题
    tooltip: str = ""                 # 提示文本
    is_active: bool = False          # 是否选中
    has_notification: bool = False   # 是否有通知
    notification_count: int = 0      # 通知数量
    window_id: str = ""              # 关联的窗口 ID

@dataclass
class Notification:
    """通知"""
    id: str
    title: str
    message: str
    icon: str = ""
    level: str = "info"  # info, warning, error, success
    timestamp: str = ""
    actions: List[dict] = field(default_factory=list)
    auto_dismiss: bool = True
    dismiss_delay: int = 5000  # 毫秒

# ============================================================================
# 任务栏
# ============================================================================

class Taskbar:
    """
    桌面任务栏

    功能:
    1. 显示运行中的应用图标
    2. 切换应用窗口
    3. 显示系统状态
    4. 快速操作入口
    """

    def __init__(
        self,
        position: TaskbarPosition = TaskbarPosition.BOTTOM,
        height: int = 48,
        auto_hide: bool = False
    ):
        self.position = position
        self.height = height
        self.auto_hide = auto_hide

        # 任务栏项
        self._items: Dict[str, TaskbarItem] = {}

        # 回调
        self._on_item_click: Optional[Callable] = None
        self._on_item_right_click: Optional[Callable] = None

    # --------------------------------------------------------------------------
    # 项管理
    # --------------------------------------------------------------------------

    def add_item(self, item: TaskbarItem) -> bool:
        """添加任务栏项"""
        if item.id in self._items:
            return False
        self._items[item.id] = item
        return True

    def remove_item(self, item_id: str) -> bool:
        """移除任务栏项"""
        if item_id in self._items:
            self._items.pop(item_id)
            return True
        return False

    def get_item(self, item_id: str) -> Optional[TaskbarItem]:
        """获取任务栏项"""
        return self._items.get(item_id)

    def get_all_items(self) -> List[TaskbarItem]:
        """获取所有任务栏项"""
        return list(self._items.values())

    def update_item(self, item_id: str, **kwargs):
        """更新任务栏项"""
        if item_id in self._items:
            item = self._items[item_id]
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)

    # --------------------------------------------------------------------------
    # 快速操作
    # --------------------------------------------------------------------------

    def set_quick_actions(self, actions: List[dict]):
        """设置快速操作按钮"""
        # 存储快速操作
        self._quick_actions = actions

    def get_quick_actions(self) -> List[dict]:
        """获取快速操作"""
        return getattr(self, "_quick_actions", [])

    # --------------------------------------------------------------------------
    # 事件
    # --------------------------------------------------------------------------

    def set_on_item_click(self, callback: Callable[[str], None]):
        """设置项点击回调"""
        self._on_item_click = callback

    def set_on_item_right_click(self, callback: Callable[[str], None]):
        """设置项右键回调"""
        self._on_item_right_click = callback

# ============================================================================
# 系统托盘
# ============================================================================

class SystemTray:
    """
    系统托盘

    功能:
    1. 显示托盘图标
    2. 托盘菜单
    3. 托盘气泡通知
    """

    def __init__(self, icon: str = ""):
        self.icon = icon
        self._menu_items: List[dict] = []
        self._is_visible = True

        # 回调
        self._on_left_click: Optional[Callable] = None
        self._on_right_click: Optional[Callable] = None
        self._on_double_click: Optional[Callable] = None

    def set_icon(self, icon: str):
        """设置托盘图标"""
        self.icon = icon

    def add_menu_item(self, label: str, action: Callable = None, **kwargs):
        """添加菜单项"""
        self._menu_items.append({
            "label": label,
            "action": action,
            **kwargs
        })

    def get_menu_items(self) -> List[dict]:
        """获取菜单项"""
        return self._menu_items

    def show_balloon(
        self,
        title: str,
        message: str,
        icon: str = "",
        timeout: int = 3000
    ):
        """显示气泡通知"""
        # 实现托盘气泡
        pass

    def set_on_left_click(self, callback: Callable):
        """设置左键点击回调"""
        self._on_left_click = callback

    def set_on_right_click(self, callback: Callable):
        """设置右键点击回调"""
        self._on_right_click = callback

    def set_on_double_click(self, callback: Callable):
        """设置双击回调"""
        self._on_double_click = callback

# ============================================================================
# 通知中心
# ============================================================================

class NotificationCenter:
    """
    通知中心

    功能:
    1. 收集和显示通知
    2. 通知历史
    3. 通知操作
    4. 按类型过滤
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history

        # 通知存储
        self._notifications: List[Notification] = []
        self._unread_count: int = 0

        # 回调
        self._on_notification_added: Optional[Callable] = None
        self._on_notification_dismissed: Optional[Callable] = None

    # --------------------------------------------------------------------------
    # 通知管理
    # --------------------------------------------------------------------------

    def add_notification(
        self,
        title: str,
        message: str,
        icon: str = "",
        level: str = "info",
        actions: List[dict] = None,
        auto_dismiss: bool = True,
        dismiss_delay: int = 5000
    ) -> Notification:
        """
        添加通知

        Args:
            title: 标题
            message: 内容
            icon: 图标
            level: 级别 (info, warning, error, success)
            actions: 操作按钮
            auto_dismiss: 是否自动消失
            dismiss_delay: 消失延迟 (毫秒)

        Returns:
            Notification 实例
        """
        notification = Notification(
            id=f"notif_{datetime.now().timestamp()}",
            title=title,
            message=message,
            icon=icon,
            level=level,
            timestamp=datetime.now().isoformat(),
            actions=actions or [],
            auto_dismiss=auto_dismiss,
            dismiss_delay=dismiss_delay
        )

        self._notifications.insert(0, notification)
        self._unread_count += 1

        # 限制历史长度
        if len(self._notifications) > self.max_history:
            self._notifications = self._notifications[:self.max_history]

        if self._on_notification_added:
            self._on_notification_added(notification)

        # 自动消失
        if auto_dismiss:
            asyncio.create_task(self._auto_dismiss(notification))

        return notification

    async def _auto_dismiss(self, notification: Notification):
        """自动消失"""
        await asyncio.sleep(notification.dismiss_delay / 1000)
        self.dismiss_notification(notification.id)

    def dismiss_notification(self, notification_id: str) -> bool:
        """关闭通知"""
        for i, n in enumerate(self._notifications):
            if n.id == notification_id:
                self._notifications.pop(i)
                if self._on_notification_dismissed:
                    self._on_notification_dismissed(n)
                return True
        return False

    def dismiss_all(self):
        """关闭所有通知"""
        self._notifications.clear()
        self._unread_count = 0

    def mark_all_read(self):
        """标记全部已读"""
        self._unread_count = 0

    def get_notifications(
        self,
        level: str = None,
        since: datetime = None
    ) -> List[Notification]:
        """获取通知列表"""
        notifications = self._notifications

        if level:
            notifications = [n for n in notifications if n.level == level]

        if since:
            since_ts = since.timestamp()
            notifications = [
                n for n in notifications
                if datetime.fromisoformat(n.timestamp).timestamp() >= since_ts
            ]

        return notifications

    def get_unread_count(self) -> int:
        """获取未读数量"""
        return self._unread_count

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """获取单个通知"""
        for n in self._notifications:
            if n.id == notification_id:
                return n
        return None

    # --------------------------------------------------------------------------
    # 快捷方法
    # --------------------------------------------------------------------------

    def info(self, title: str, message: str, **kwargs):
        """添加信息通知"""
        return self.add_notification(title, message, level="info", **kwargs)

    def warning(self, title: str, message: str, **kwargs):
        """添加警告通知"""
        return self.add_notification(title, message, level="warning", **kwargs)

    def error(self, title: str, message: str, **kwargs):
        """添加错误通知"""
        kwargs["auto_dismiss"] = kwargs.get("auto_dismiss", False)
        return self.add_notification(title, message, level="error", **kwargs)

    def success(self, title: str, message: str, **kwargs):
        """添加成功通知"""
        return self.add_notification(title, message, level="success", **kwargs)

    # --------------------------------------------------------------------------
    # 事件
    # --------------------------------------------------------------------------

    def set_on_notification_added(
        self,
        callback: Callable[[Notification], None]
    ):
        """设置通知添加回调"""
        self._on_notification_added = callback

    def set_on_notification_dismissed(
        self,
        callback: Callable[[Notification], None]
    ):
        """设置通知关闭回调"""
        self._on_notification_dismissed = callback