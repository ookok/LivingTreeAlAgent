"""
Admin Notification Service - 管理员通知服务
============================================

功能：
1. 企业申请序列号时通知系统管理员
2. 随机选择一个在线的管理员节点发送通知
3. 通过 WebSocket 实时推送通知

设计原则：
- 管理员节点在线状态通过心跳追踪
- 随机选择确保负载均衡
- WebSocket 推送确保实时性
"""

import os
import json
import time
import uuid
import asyncio
import random
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
import httpx

from server.relay_server.services.user_auth_service import (
    get_auth_storage,
    get_node_service,
    NodeService,
    NodeStatus,
)
from core.admin_license_system.admin_auth import AdminUser, AdminRole, get_admin_auth


# ============ 通知类型枚举 ============

class NotificationType(str, Enum):
    """通知类型"""
    SERIAL_REQUEST = "serial_request"        # 序列号申请
    PAYMENT_RECEIVED = "payment_received"    # 收到付款
    USER_REGISTERED = "user_registered"      # 新用户注册
    NODE_OFFLINE = "node_offline"           # 节点离线
    SYSTEM_ALERT = "system_alert"           # 系统警告
    VIP_UPGRADE = "vip_upgrade"             # VIP升级


class NotificationPriority(str, Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# ============ 通知消息模型 ============

@dataclass
class NotificationMessage:
    """通知消息"""
    notification_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    title: str
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: Optional[int] = None
    target_admin_ids: List[str] = field(default_factory=list)
    sent_to: List[str] = field(default_factory=list)  # 已发送到的 admin_id 列表

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value if isinstance(self.notification_type, NotificationType) else self.notification_type,
            "priority": self.priority.value if isinstance(self.priority, NotificationPriority) else self.priority,
            "title": self.title,
            "content": self.content,
            "data": self.data,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "target_admin_ids": self.target_admin_ids,
            "sent_to": self.sent_to,
        }


@dataclass
class AdminNodeStatus:
    """管理员节点在线状态"""
    node_id: str
    admin_id: str
    admin_username: str
    relay_url: str
    is_online: bool
    last_heartbeat: int
    websocket_conn_id: Optional[str] = None


# ============ 管理员在线状态管理 ============

class AdminOnlineManager:
    """
    管理员在线状态管理器

    追踪所有管理员节点的在线状态，
    支持通过心跳更新状态
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "relay_server" / "admin_notifications"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.status_file = data_dir / "admin_online_status.json"
        self.notifications_file = data_dir / "notifications.json"

        self._load_status()
        self._admin_auth = get_admin_auth()

    def _load_status(self):
        """加载状态"""
        if self.status_file.exists():
            try:
                self._status: Dict[str, Dict[str, Any]] = json.loads(self.status_file.read_text(encoding="utf-8"))
            except Exception:
                self._status = {}
        else:
            self._status = {}

    def _save_status(self):
        """保存状态"""
        self.status_file.write_text(json.dumps(self._status, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_heartbeat(self, node_id: str, admin_id: str, relay_url: str = "") -> bool:
        """
        更新管理员节点心跳

        当管理员节点发送心跳时调用此方法更新状态
        """
        self._status[node_id] = {
            "node_id": node_id,
            "admin_id": admin_id,
            "relay_url": relay_url,
            "is_online": True,
            "last_heartbeat": int(time.time()),
        }
        self._save_status()
        return True

    def set_offline(self, node_id: str):
        """设置节点离线"""
        if node_id in self._status:
            self._status[node_id]["is_online"] = False
            self._save_status()

    def get_online_admins(self) -> List[AdminNodeStatus]:
        """
        获取所有在线管理员节点

        在线判定：最近 5 分钟内有心跳
        """
        online_admins = []
        now = int(time.time())
        online_threshold = 300  # 5分钟

        for node_id, status in self._status.items():
            if status.get("is_online") and (now - status.get("last_heartbeat", 0)) < online_threshold:
                # 获取管理员信息
                admin = self._admin_auth.get_admin_by_id(status.get("admin_id"))
                if admin:
                    online_admins.append(AdminNodeStatus(
                        node_id=node_id,
                        admin_id=status["admin_id"],
                        admin_username=admin.username,
                        relay_url=status.get("relay_url", ""),
                        is_online=True,
                        last_heartbeat=status["last_heartbeat"],
                    ))

        return online_admins

    def select_random_online_admin(self) -> Optional[AdminNodeStatus]:
        """随机选择一个在线管理员"""
        online_admins = self.get_online_admins()
        if not online_admins:
            return None
        return random.choice(online_admins)

    def select_online_admins(self, count: int = 1) -> List[AdminNodeStatus]:
        """随机选择指定数量的在线管理员"""
        online_admins = self.get_online_admins()
        if not online_admins:
            return []
        return random.sample(online_admins, min(count, len(online_admins)))


# ============ 通知服务 ============

class AdminNotificationService:
    """
    管理员通知服务

    核心功能：
    1. 发送通知到管理员节点
    2. 记录通知历史
    3. 追踪通知状态
    """

    def __init__(
        self,
        online_manager: Optional[AdminOnlineManager] = None,
        node_service: Optional[NodeService] = None
    ):
        self.online_manager = online_manager or AdminOnlineManager()
        self.node_service = node_service

        # 通知历史
        self.notifications: Dict[str, NotificationMessage] = {}

        # WebSocket 连接（用于推送）
        self._ws_connections: Dict[str, Any] = {}

    def register_ws_connection(self, admin_id: str, node_id: str, conn_id: str):
        """注册 WebSocket 连接"""
        key = f"{admin_id}:{node_id}"
        self._ws_connections[key] = conn_id

    def unregister_ws_connection(self, admin_id: str, node_id: str):
        """注销 WebSocket 连接"""
        key = f"{admin_id}:{node_id}"
        if key in self._ws_connections:
            del self._ws_connections[key]

    async def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        content: str,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        target_admin_count: int = 1,
        admin_ids: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        发送通知到管理员

        Args:
            notification_type: 通知类型
            title: 通知标题
            content: 通知内容
            data: 附加数据
            priority: 优先级
            target_admin_count: 目标管理员数量（当 admin_ids 未指定时）
            admin_ids: 指定的管理员 ID 列表

        Returns:
            (是否成功, 已发送到的 admin_id 列表)
        """
        # 创建通知消息
        notification = NotificationMessage(
            notification_id=f"notif_{uuid.uuid4().hex[:16]}",
            notification_type=notification_type,
            priority=priority,
            title=title,
            content=content,
            data=data or {},
        )

        # 确定目标管理员
        if admin_ids:
            target_admins = []
            for admin_id in admin_ids:
                admin = self.online_manager._admin_auth.get_admin_by_id(admin_id)
                if admin:
                    target_admins.append(admin)
        else:
            # 随机选择在线管理员
            selected = self.online_manager.select_online_admins(target_admin_count)
            target_admins = selected

        if not target_admins:
            return False, []

        # 发送通知
        sent_to = []
        for admin_status in target_admins:
            success = await self._send_to_admin(admin_status, notification)
            if success:
                sent_to.append(admin_status.admin_id)
                notification.sent_to.append(admin_status.admin_id)

        # 记录通知
        self.notifications[notification.notification_id] = notification

        return len(sent_to) > 0, sent_to

    async def _send_to_admin(
        self,
        admin_status: AdminNodeStatus,
        notification: NotificationMessage
    ) -> bool:
        """
        发送通知到单个管理员

        方式：
        1. 优先 WebSocket 推送
        2. 次选 HTTP 回调
        3. 最后记录待发送
        """
        key = f"{admin_status.admin_id}:{admin_status.node_id}"

        # 方式1: WebSocket 推送
        if key in self._ws_connections:
            # TODO: 通过 WebSocket 推送
            # ws_conn = self._ws_connections[key]
            # await ws_conn.send_json(notification.to_dict())
            pass

        # 方式2: HTTP 回调
        if admin_status.relay_url:
            try:
                callback_url = f"{admin_status.relay_url.rstrip('/')}/api/admin/notification"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        callback_url,
                        json=notification.to_dict(),
                        headers={"X-Notification-Type": notification.notification_type.value}
                    )
                    if response.status_code == 200:
                        return True
            except Exception:
                pass

        # 方式3: 记录待发送（后续重试）
        # TODO: 实现待发送队列
        return False

    def get_notification_history(
        self,
        admin_id: Optional[str] = None,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50
    ) -> List[NotificationMessage]:
        """获取通知历史"""
        notifications = list(self.notifications.values())

        # 过滤
        if admin_id:
            notifications = [n for n in notifications if admin_id in n.sent_to]
        if notification_type:
            notifications = [n for n in notifications if n.notification_type == notification_type]

        # 按时间倒序
        notifications.sort(key=lambda x: x.created_at, reverse=True)
        return notifications[:limit]


# ============ 序列号申请通知 ============

class SerialRequestNotifier:
    """
    序列号申请通知器

    集成到企业许可证服务，当有新的序列号申请时通知管理员
    """

    def __init__(self, notification_service: Optional[AdminNotificationService] = None):
        self.notification_service = notification_service or AdminNotificationService()

    async def notify_serial_request(
        self,
        enterprise_name: str,
        enterprise_code: str,
        license_type: str,
        requester_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        通知序列号申请

        Args:
            enterprise_name: 企业名称
            enterprise_code: 8位码
            license_type: 许可证类型
            requester_info: 请求者信息（IP、设备等）

        Returns:
            (是否成功, 消息)
        """
        # 构造通知内容
        license_type_names = {
            "trial": "试用版",
            "standard": "标准版",
            "professional": "专业版",
            "enterprise": "企业版",
        }
        type_name = license_type_names.get(license_type, license_type)

        title = f"新的序列号申请 - {enterprise_name}"
        content = f"""企业名称: {enterprise_name}
申请类型: {type_name}
8位码: {enterprise_code}
"""

        if requester_info:
            content += f"""
请求者IP: {requester_info.get('ip_address', '未知')}
设备指纹: {requester_info.get('device_fingerprint', '未知')}
"""

        # 发送通知
        success, sent_to = await self.notification_service.send_notification(
            notification_type=NotificationType.SERIAL_REQUEST,
            title=title,
            content=content,
            data={
                "enterprise_name": enterprise_name,
                "enterprise_code": enterprise_code,
                "license_type": license_type,
                "requester_info": requester_info or {},
            },
            priority=NotificationPriority.HIGH,
            target_admin_count=1,  # 随机选择1个在线管理员
        )

        if success:
            return True, f"已通知管理员: {', '.join(sent_to)}"
        else:
            return False, "没有在线管理员，已记录待发送"


# ============ 积分一致性管理 ============

class CreditConsistencyManager:
    """
    积分一致性管理器

    解决中继服务器和客户端之间的积分数据一致性问题

    策略：
    1. 写操作 → 主节点（中继服务器）
    2. 读操作 → 先读本地缓存，再同步主节点
    3. 冲突解决 → Last-Write-Wins + 版本号
    4. 离线处理 → 本地队列 + 重试机制
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "relay_server" / "credit_consistency"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 版本号计数器
        self.version_file = data_dir / "version_counter.json"
        self._load_version()

        # 待同步队列
        self.sync_queue_file = data_dir / "sync_queue.json"
        self._sync_queue: List[Dict[str, Any]] = []

        # 冲突日志
        self.conflicts_file = data_dir / "conflicts.json"

    def _load_version(self):
        """加载版本号"""
        if self.version_file.exists():
            try:
                self._version = int(self.version_file.read_text(encoding="utf-8"))
            except Exception:
                self._version = 0
        else:
            self._version = 0

    def _save_version(self):
        """保存版本号"""
        self.version_file.write_text(str(self._version), encoding="utf-8")

    def get_next_version(self) -> int:
        """获取下一个版本号"""
        self._version += 1
        self._save_version()
        return self._version

    def add_to_sync_queue(self, operation: Dict[str, Any]):
        """
        添加操作到同步队列

        operation 格式:
        {
            "op_id": str,           # 操作ID
            "op_type": str,         # recharge/consume/daily_bonus
            "user_id": str,
            "amount": int,
            "timestamp": int,
            "version": int,
            "source_node": str,     # 来源节点
            "retry_count": int,
        }
        """
        self._sync_queue.append(operation)
        self._save_sync_queue()

    def _save_sync_queue(self):
        """保存同步队列"""
        self.sync_queue_file.write_text(json.dumps(self._sync_queue, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_pending_sync(self) -> List[Dict[str, Any]]:
        """获取待同步操作"""
        return self._sync_queue

    def remove_from_sync_queue(self, op_id: str):
        """从同步队列移除"""
        self._sync_queue = [op for op in self._sync_queue if op.get("op_id") != op_id]
        self._save_sync_queue()

    def resolve_conflict(
        self,
        local_version: Dict[str, Any],
        remote_version: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解决冲突

        策略: Last-Write-Wins (以时间戳为准)

        Args:
            local_version: 本地版本
            remote_version: 远程版本

        Returns:
            解决后的版本
        """
        # 比较时间戳
        local_time = local_version.get("timestamp", 0)
        remote_time = remote_version.get("timestamp", 0)

        if local_time >= remote_time:
            winner = local_version
        else:
            winner = remote_version

        # 记录冲突
        self._log_conflict(local_version, remote_version, winner)

        return winner

    def _log_conflict(
        self,
        local_version: Dict[str, Any],
        remote_version: Dict[str, Any],
        winner: Dict[str, Any]
    ):
        """记录冲突"""
        conflicts = []
        if self.conflicts_file.exists():
            try:
                conflicts = json.loads(self.conflicts_file.read_text(encoding="utf-8"))
            except Exception:
                conflicts = []

        conflicts.append({
            "timestamp": int(time.time()),
            "local_version": local_version,
            "remote_version": remote_version,
            "winner": winner,
        })

        # 只保留最近100条冲突记录
        conflicts = conflicts[-100:]

        self.conflicts_file.write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")


# ============ 单例 ============

_admin_notification_service: Optional[AdminNotificationService] = None
_admin_online_manager: Optional[AdminOnlineManager] = None
_serial_request_notifier: Optional[SerialRequestNotifier] = None
_credit_consistency_manager: Optional[CreditConsistencyManager] = None


def get_admin_notification_service() -> AdminNotificationService:
    global _admin_notification_service
    if _admin_notification_service is None:
        _admin_notification_service = AdminNotificationService()
    return _admin_notification_service


def get_admin_online_manager() -> AdminOnlineManager:
    global _admin_online_manager
    if _admin_online_manager is None:
        _admin_online_manager = AdminOnlineManager()
    return _admin_online_manager


def get_serial_request_notifier() -> SerialRequestNotifier:
    global _serial_request_notifier
    if _serial_request_notifier is None:
        _serial_request_notifier = SerialRequestNotifier()
    return _serial_request_notifier


def get_credit_consistency_manager() -> CreditConsistencyManager:
    global _credit_consistency_manager
    if _credit_consistency_manager is None:
        _credit_consistency_manager = CreditConsistencyManager()
    return _credit_consistency_manager
