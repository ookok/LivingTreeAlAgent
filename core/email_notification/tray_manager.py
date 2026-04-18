"""
系统托盘管理器
==============

使用 PyQt QSystemTrayIcon 实现托盘功能：
1. 托盘图标
2. 右键菜单
3. 托盘气泡
4. 最小化/恢复
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TrayManager:
    """
    托盘管理器

    封装 QSystemTrayIcon，提供托盘功能。
    """

    def __init__(self, parent=None):
        """
        初始化托盘管理器

        Args:
            parent: 父窗口（用于获取 QApplication）
        """
        self._parent = parent
        self._tray_icon: Optional[Any] = None
        self._menu: Optional[Any] = None
        self._actions: Dict[str, Any] = {}
        self._callbacks: Dict[str, Callable] = {}

        # 获取 QApplication
        self._app = None
        try:
            from PyQt6.QtWidgets import QApplication
            self._app = QApplication.instance()
        except ImportError:
            logger.warning("PyQt6 not available")

    def setup(self, icon_path: str = "", tooltip: str = "Hermes Desktop"):
        """
        设置托盘图标

        Args:
            icon_path: 图标路径（为空使用默认）
            tooltip: 鼠标悬停提示
        """
        if not self._app:
            logger.warning("QApplication not available")
            return

        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon, QAction
            from PyQt6.QtCore import Qt

            # 创建托盘图标
            if icon_path:
                icon = QIcon(icon_path)
            else:
                # 使用默认图标
                icon = self._app.style().standardIcon(
                    self._app.style().StandardPixmap.SP_ComputerIcon
                )

            self._tray_icon = QSystemTrayIcon(icon, self._parent)
            self._tray_icon.setToolTip(tooltip)

            # 创建菜单
            self._menu = QMenu(self._parent)
            self._tray_icon.setContextMenu(self._menu)

            # 添加基础菜单项
            self._add_default_actions()

            # 连接激活信号
            self._tray_icon.activated.connect(self._on_tray_activated)

            # 显示
            self._tray_icon.show()

            logger.info("Tray icon created")

        except Exception as e:
            logger.error(f"Failed to setup tray: {e}")

    def _add_default_actions(self):
        """添加默认菜单项"""
        self.add_action("open", "📂 打开主界面", self._on_open)
        self.add_action("check_mail", "📧 检查新邮件", self._on_check_mail)
        self.add_separator()
        self.add_action("dnd_on", "🔕 开启免打扰", self._on_dnd_on)
        self.add_action("dnd_off", "🔔 关闭免打扰", self._on_dnd_off)
        self.add_separator()
        self.add_action("quit", "❌ 退出", self._on_quit)

    def add_action(
        self,
        action_id: str,
        label: str,
        callback: Callable,
        icon: str = "",
        shortcut: str = "",
    ):
        """
        添加菜单动作

        Args:
            action_id: 动作ID
            label: 显示文本
            callback: 回调函数
            icon: 图标（emoji或资源路径）
            shortcut: 快捷键
        """
        if not self._menu:
            return

        try:
            from PyQt6.QtGui import QAction, QIcon
            from PyQt6.QtCore import Qt

            action = QAction(label, self._parent)
            action.triggered.connect(callback)

            if shortcut:
                action.setShortcut(shortcut)

            self._menu.addAction(action)
            self._actions[action_id] = action
            self._callbacks[action_id] = callback

        except Exception as e:
            logger.error(f"Failed to add action: {e}")

    def add_separator(self):
        """添加分隔符"""
        if self._menu:
            self._menu.addSeparator()

    def remove_action(self, action_id: str):
        """移除菜单动作"""
        if action_id in self._actions:
            action = self._actions[action_id]
            self._menu.removeAction(action)
            del self._actions[action_id]
            del self._callbacks[action_id]

    def _on_tray_activated(self, reason):
        """托盘图标激活处理"""
        from PyQt6.QtCore import QSystemTrayIcon

        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 单击
            self._on_open()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # 双击
            self._on_open()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            # 右键
            pass

    def _on_open(self):
        """打开主界面"""
        if self._parent:
            self._parent.show()
            self._parent.raise_()
            self._parent.activateWindow()

    def _on_check_mail(self):
        """检查新邮件"""
        pass

    def _on_dnd_on(self):
        """开启免打扰"""
        from .notification_service import get_notification_service
        svc = get_notification_service()
        svc.set_do_not_disturb(True)
        self.update_dnd_state()

    def _on_dnd_off(self):
        """关闭免打扰"""
        from .notification_service import get_notification_service
        svc = get_notification_service()
        svc.set_do_not_disturb(False)
        self.update_dnd_state()

    def _on_quit(self):
        """退出应用"""
        self._app.quit()

    def update_dnd_state(self):
        """更新免打扰状态显示"""
        from .notification_service import get_notification_service
        svc = get_notification_service()

        is_dnd = svc.is_do_not_disturb()

        if "dnd_on" in self._actions:
            self._actions["dnd_on"].setVisible(not is_dnd)
        if "dnd_off" in self._actions:
            self._actions["dnd_off"].setVisible(is_dnd)

    def show_notification(
        self,
        title: str,
        message: str,
        icon: str = "information",
        timeout: int = 5000,
    ):
        """
        显示托盘气泡通知

        Args:
            title: 标题
            message: 内容
            icon: 图标类型 (information, warning, error, critical)
            timeout: 显示时长（毫秒）
        """
        if not self._tray_icon:
            return

        try:
            from PyQt6.QtWidgets import QSystemTrayIcon

            icon_map = {
                "information": QSystemTrayIcon.MessageIcon.Information,
                "warning": QSystemTrayIcon.MessageIcon.Warning,
                "error": QSystemTrayIcon.MessageIcon.Critical,
                "critical": QSystemTrayIcon.MessageIcon.Critical,
            }

            self._tray_icon.showMessage(
                title,
                message,
                icon_map.get(icon, QSystemTrayIcon.MessageIcon.Information),
                timeout,
            )
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")

    def set_tooltip(self, tooltip: str):
        """设置提示文本"""
        if self._tray_icon:
            self._tray_icon.setToolTip(tooltip)

    def set_icon(self, icon_path: str):
        """设置图标"""
        if self._tray_icon:
            try:
                from PyQt6.QtGui import QIcon
                self._tray_icon.setIcon(QIcon(icon_path))
            except Exception as e:
                logger.error(f"Failed to set icon: {e}")

    def set_badge_count(self, count: int):
        """设置角标数量（如果有的话）"""
        # 部分系统/主题支持托盘角标
        if count > 0:
            self.set_tooltip(f"Hermes Desktop - {count}封未读邮件")
        else:
            self.set_tooltip("Hermes Desktop")

    def hide(self):
        """隐藏托盘"""
        if self._tray_icon:
            self._tray_icon.hide()

    def show(self):
        """显示托盘"""
        if self._tray_icon:
            self._tray_icon.show()

    def is_visible(self) -> bool:
        """是否可见"""
        return self._tray_icon.isVisible() if self._tray_icon else False


class EmailTrayIcon:
    """
    邮件托盘图标

    专门用于邮件通知的托盘图标管理。
    """

    def __init__(self, tray_manager: TrayManager):
        self._tray = tray_manager
        self._unread_count = 0
        self._accounts: Dict[str, int] = {}  # account_id -> unread_count

    def setup(self):
        """设置邮件菜单"""
        # 找到"检查新邮件"菜单位置，在其前插入邮件账户子菜单
        pass

    def update_unread_count(self, account_id: str, count: int):
        """更新未读数"""
        self._accounts[account_id] = count
        self._unread_count = sum(self._accounts.values())
        self._update_badge()

    def _update_badge(self):
        """更新角标"""
        self._tray.set_badge_count(self._unread_count)

    def show_new_mail_notification(
        self,
        account_id: str,
        sender: str,
        subject: str,
    ):
        """显示新邮件通知"""
        self._tray.show_notification(
            title=f"📧 新邮件: {sender}",
            message=subject,
            icon="information",
            timeout=5000,
        )

    def show_error_notification(self, account_id: str, error: str):
        """显示错误通知"""
        self._tray.show_notification(
            title="❌ 邮件同步失败",
            message=error,
            icon="error",
            timeout=10000,
        )
