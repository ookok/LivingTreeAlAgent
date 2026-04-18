"""
Serial Notification Service - 序列号通知服务
=============================================

功能：
1. 短信通知管理员（优先同区域）
2. 邮件通知管理员（短信失败后）
3. 序列号申请记录管理

设计原则：
- 短信为主，确保实时性
- 邮件为备，确保可达性
- 同区域优先，减少延迟
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


# ============ 通知渠道枚举 ============

class NotificationChannel(str, Enum):
    """通知渠道"""
    SMS = "sms"           # 短信
    EMAIL = "email"       # 邮件
    WEBSOCKET = "websocket"  # WebSocket
    HTTP_CALLBACK = "http_callback"  # HTTP回调


class NotificationResult(str, Enum):
    """通知结果"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


# ============ 通知记录模型 ============

@dataclass
class NotificationRecord:
    """通知记录"""
    notification_id: str
    channel: NotificationChannel
    target_admin_id: str
    admin_phone: Optional[str] = None
    admin_email: Optional[str] = None
    subject: str = ""
    content: str = ""
    result: NotificationResult = NotificationResult.PENDING
    error_message: str = ""
    sent_at: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "channel": self.channel.value if isinstance(self.channel, NotificationChannel) else self.channel,
            "target_admin_id": self.target_admin_id,
            "admin_phone": self.admin_phone,
            "admin_email": self.admin_email,
            "subject": self.subject,
            "content": self.content,
            "result": self.result.value if isinstance(self.result, NotificationResult) else self.result,
            "error_message": self.error_message,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }


@dataclass
class SerialRequestRecord:
    """序列号申请记录"""
    request_id: str
    enterprise_name: str
    enterprise_code: str
    license_type: str
    status: str  # pending/approved/rejected/completed
    requested_at: int
    requested_ip: str = ""
    client_id: str = ""
    assigned_admin_id: str = ""
    serial_number: str = ""
    notification_sent: bool = False
    notification_channels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "enterprise_name": self.enterprise_name,
            "enterprise_code": self.enterprise_code,
            "license_type": self.license_type,
            "status": self.status,
            "requested_at": self.requested_at,
            "requested_ip": self.requested_ip,
            "client_id": self.client_id,
            "assigned_admin_id": self.assigned_admin_id,
            "serial_number": self.serial_number,
            "notification_sent": self.notification_sent,
            "notification_channels": self.notification_channels,
        }


# ============ 短信服务接口 ============

class SMSServiceInterface:
    """
    短信服务接口

    定义短信发送的标准接口，具体实现由第三方SDK完成
    """

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        template_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        发送短信

        Args:
            phone_number: 手机号
            message: 短信内容
            template_id: 短信模板ID

        Returns:
            (是否成功, 错误消息)
        """
        raise NotImplementedError


class MockSMSService(SMSServiceInterface):
    """模拟短信服务（用于测试）"""

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        template_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """模拟发送短信"""
        print(f"[SMS Mock] 发送短信到 {phone_number}: {message}")
        # 模拟90%成功率
        if random.random() > 0.1:
            return True, ""
        else:
            return False, "模拟失败：网络异常"


# ============ 邮件服务接口 ============

class EmailServiceInterface:
    """
    邮件服务接口

    定义邮件发送的标准接口，具体实现由第三方SMTP完成
    """

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> Tuple[bool, str]:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件内容
            html: 是否为HTML格式

        Returns:
            (是否成功, 错误消息)
        """
        raise NotImplementedError


class MockEmailService(EmailServiceInterface):
    """模拟邮件服务（用于测试）"""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> Tuple[bool, str]:
        """模拟发送邮件"""
        print(f"[Email Mock] 发送邮件到 {to_email}: {subject}")
        return True, ""


# ============ 序列号通知服务 ============

class SerialNotificationService:
    """
    序列号通知服务

    核心功能：
    1. 离线管理员通知（短信优先，邮件备选）
    2. 同区域优先选择
    3. 序列号申请记录
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        sms_service: Optional[SMSServiceInterface] = None,
        email_service: Optional[EmailServiceInterface] = None
    ):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "relay_server" / "serial_notifications"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 通知记录
        self.notifications_file = data_dir / "notifications.json"
        self.requests_file = data_dir / "serial_requests.json"

        # 服务
        self.sms_service = sms_service or MockSMSService()
        self.email_service = email_service or MockEmailService()

        # 加载数据
        self._notification_records: Dict[str, NotificationRecord] = {}
        self._serial_requests: Dict[str, SerialRequestRecord] = {}
        self._load_data()

    def _load_data(self):
        """加载数据"""
        if self.notifications_file.exists():
            try:
                data = json.loads(self.notifications_file.read_text(encoding="utf-8"))
                self._notification_records = {
                    k: NotificationRecord(**v) for k, v in data.items()
                }
            except Exception:
                pass

        if self.requests_file.exists():
            try:
                data = json.loads(self.requests_file.read_text(encoding="utf-8"))
                self._serial_requests = {
                    k: SerialRequestRecord(**v) for k, v in data.items()
                }
            except Exception:
                pass

    def _save_notifications(self):
        """保存通知记录"""
        data = {k: v.to_dict() for k, v in self._notification_records.items()}
        self.notifications_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_requests(self):
        """保存申请记录"""
        data = {k: v.to_dict() for k, v in self._serial_requests.items()}
        self.requests_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ============ 序列号申请记录 ============

    def add_serial_request(
        self,
        enterprise_name: str,
        enterprise_code: str,
        license_type: str,
        requested_ip: str,
        client_id: str = ""
    ) -> SerialRequestRecord:
        """添加序列号申请记录"""
        request = SerialRequestRecord(
            request_id=f"req_{uuid.uuid4().hex[:16]}",
            enterprise_name=enterprise_name,
            enterprise_code=enterprise_code,
            license_type=license_type,
            status="pending",
            requested_at=int(time.time()),
            requested_ip=requested_ip,
            client_id=client_id,
        )
        self._serial_requests[request.request_id] = request
        self._save_requests()
        return request

    def get_pending_requests(self) -> List[SerialRequestRecord]:
        """获取待处理的申请"""
        return [
            r for r in self._serial_requests.values()
            if r.status == "pending"
        ]

    def update_request_status(
        self,
        request_id: str,
        status: str,
        serial_number: str = ""
    ) -> bool:
        """更新申请状态"""
        if request_id in self._serial_requests:
            self._serial_requests[request_id].status = status
            if serial_number:
                self._serial_requests[request_id].serial_number = serial_number
            self._save_requests()
            return True
        return False

    # ============ 管理员通知 ============

    async def notify_admins_about_request(
        self,
        request: SerialRequestRecord,
        admin_list: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        通知管理员有新的序列号申请

        策略：
        1. 优先选择同区域的在线管理员（WebSocket推送）
        2. 其次选择同区域的离线管理员（短信）
        3. 最后选择其他区域的离线管理员（短信）
        4. 短信失败后尝试邮件

        Args:
            request: 序列号申请记录
            admin_list: 管理员列表（包含 admin_id, phone, email, region 等）

        Returns:
            (是否成功, 通知到的管理员ID列表)
        """
        notified_admins = []
        channels_used = []

        # 构建通知内容
        title = f"新的序列号申请 - {request.enterprise_name}"
        content = f"""您收到一个新的序列号申请：

企业名称：{request.enterprise_name}
8位码：{request.enterprise_code}
许可证类型：{request.license_type}
申请时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(request.requested_at))}
申请IP：{request.requested_ip}

请尽快登录管理后台处理。"""

        # 按区域分组管理员
        online_admins = [a for a in admin_list if a.get("is_online", False)]
        offline_admins = [a for a in admin_list if not a.get("is_online", False)]

        # 同区域管理员
        same_region_online = [a for a in online_admins if a.get("region") == request.requested_ip[:3]]
        same_region_offline = [a for a in offline_admins if a.get("region") == request.requested_ip[:3]]

        # 1. WebSocket 推送（在线管理员）
        for admin in same_region_online[:1]:  # 只通知一个
            success = await self._send_websocket_notification(
                admin, title, content, request
            )
            if success:
                notified_admins.append(admin["admin_id"])
                channels_used.append("websocket")
                request.notification_sent = True
                break

        # 2. 短信通知（离线管理员，优先同区域）
        if not notified_admins:
            for admin in same_region_offline:
                if admin.get("phone"):
                    success, error = await self._send_sms_notification(
                        admin, title, content, request
                    )
                    if success:
                        notified_admins.append(admin["admin_id"])
                        channels_used.append("sms")
                        break
                    # 短信失败，尝试邮件
                    if admin.get("email"):
                        email_success, _ = await self._send_email_notification(
                            admin, title, content, request
                        )
                        if email_success:
                            notified_admins.append(admin["admin_id"])
                            channels_used.append("email")

        # 3. 其他区域管理员（随机选一个）
        if not notified_admins:
            other_admins = [a for a in offline_admins if a not in same_region_offline]
            if other_admins:
                admin = random.choice(other_admins)
                if admin.get("phone"):
                    success, error = await self._send_sms_notification(
                        admin, title, content, request
                    )
                    if success:
                        notified_admins.append(admin["admin_id"])
                        channels_used.append("sms")
                    else:
                        # 短信失败，尝试邮件
                        if admin.get("email"):
                            email_success, _ = await self._send_email_notification(
                                admin, title, content, request
                            )
                            if email_success:
                                notified_admins.append(admin["admin_id"])
                                channels_used.append("email")

        # 4. 记录通知
        request.notification_channels = channels_used
        self._save_requests()

        return len(notified_admins) > 0, notified_admins

    async def _send_websocket_notification(
        self,
        admin: Dict[str, Any],
        title: str,
        content: str,
        request: SerialRequestRecord
    ) -> bool:
        """通过 WebSocket 发送通知"""
        # TODO: 实现 WebSocket 推送
        # 这里需要连接到 AdminOnlineManager 的 WebSocket 连接
        return False  # 暂时返回 False，走短信流程

    async def _send_sms_notification(
        self,
        admin: Dict[str, Any],
        title: str,
        content: str,
        request: SerialRequestRecord
    ) -> Tuple[bool, str]:
        """发送短信通知"""
        if not admin.get("phone"):
            return False, "无手机号"

        notification = NotificationRecord(
            notification_id=f"notif_{uuid.uuid4().hex[:16]}",
            channel=NotificationChannel.SMS,
            target_admin_id=admin["admin_id"],
            admin_phone=admin["phone"],
            subject=title,
            content=content,
        )

        try:
            success, error = await self.sms_service.send_sms(
                phone_number=admin["phone"],
                message=f"【Hermes】{title}\n{content[:200]}..."
            )

            notification.result = NotificationResult.SUCCESS if success else NotificationResult.FAILED
            notification.error_message = error
            if success:
                notification.sent_at = int(time.time())

        except Exception as e:
            notification.result = NotificationResult.FAILED
            notification.error_message = str(e)

        self._notification_records[notification.notification_id] = notification
        self._save_notifications()

        return notification.result == NotificationResult.SUCCESS, notification.error_message

    async def _send_email_notification(
        self,
        admin: Dict[str, Any],
        title: str,
        content: str,
        request: SerialRequestRecord
    ) -> Tuple[bool, str]:
        """发送邮件通知"""
        if not admin.get("email"):
            return False, "无邮箱"

        notification = NotificationRecord(
            notification_id=f"notif_{uuid.uuid4().hex[:16]}",
            channel=NotificationChannel.EMAIL,
            target_admin_id=admin["admin_id"],
            admin_email=admin["email"],
            subject=title,
            content=content,
        )

        try:
            success, error = await self.email_service.send_email(
                to_email=admin["email"],
                subject=title,
                body=content,
            )

            notification.result = NotificationResult.SUCCESS if success else NotificationResult.FAILED
            notification.error_message = error
            if success:
                notification.sent_at = int(time.time())

        except Exception as e:
            notification.result = NotificationResult.FAILED
            notification.error_message = str(e)

        self._notification_records[notification.notification_id] = notification
        self._save_notifications()

        return notification.result == NotificationResult.SUCCESS, notification.error_message

    def get_notification_history(
        self,
        admin_id: Optional[str] = None,
        limit: int = 50
    ) -> List[NotificationRecord]:
        """获取通知历史"""
        records = list(self._notification_records.values())

        if admin_id:
            records = [r for r in records if r.target_admin_id == admin_id]

        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:limit]


# ============ 序列号发送服务 ============

class SerialDeliveryService:
    """
    序列号发送服务

    负责将生成的序列号发送到客户端
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "relay_server" / "serial_delivery"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 待发送队列
        self.pending_file = data_dir / "pending_delivery.json"
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._load_pending()

    def _load_pending(self):
        """加载待发送队列"""
        if self.pending_file.exists():
            try:
                self._pending = json.loads(self.pending_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_pending(self):
        """保存待发送队列"""
        self.pending_file.write_text(json.dumps(self._pending, ensure_ascii=False, indent=2), encoding="utf-8")

    def queue_serial_for_delivery(
        self,
        request_id: str,
        serial_number: str,
        license_key: str,
        enterprise_name: str,
        enterprise_code: str,
        client_id: str,
        delivery_url: str = ""
    ) -> str:
        """
        将序列号加入发送队列

        Args:
            request_id: 申请ID
            serial_number: 序列号
            license_key: 激活密钥
            enterprise_name: 企业名称
            enterprise_code: 8位码
            client_id: 客户端ID（用于定向发送）
            delivery_url: 客户端回调URL

        Returns:
            delivery_id: 投递ID
        """
        delivery_id = f"del_{uuid.uuid4().hex[:16]}"

        self._pending[delivery_id] = {
            "delivery_id": delivery_id,
            "request_id": request_id,
            "serial_number": serial_number,
            "license_key": license_key,
            "enterprise_name": enterprise_name,
            "enterprise_code": enterprise_code,
            "client_id": client_id,
            "delivery_url": delivery_url,
            "status": "pending",
            "created_at": int(time.time()),
            "sent_at": None,
            "attempts": 0,
        }
        self._save_pending()

        return delivery_id

    async def deliver_serial(self, delivery_id: str) -> Tuple[bool, str]:
        """
        发送序列号到客户端

        方式：
        1. HTTP 回调（优先）
        2. WebSocket 推送
        """
        if delivery_id not in self._pending:
            return False, "投递不存在"

        delivery = self._pending[delivery_id]
        delivery["attempts"] += 1

        # 1. HTTP 回调
        if delivery.get("delivery_url"):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        delivery["delivery_url"],
                        json={
                            "type": "serial_number",
                            "delivery_id": delivery_id,
                            "serial_number": delivery["serial_number"],
                            "license_key": delivery["license_key"],
                            "enterprise_name": delivery["enterprise_name"],
                            "enterprise_code": delivery["enterprise_code"],
                            "timestamp": int(time.time()),
                        }
                    )
                    if response.status_code == 200:
                        delivery["status"] = "delivered"
                        delivery["sent_at"] = int(time.time())
                        self._save_pending()
                        return True, "发送成功"
            except Exception as e:
                delivery["status"] = f"failed: {str(e)}"
                self._save_pending()
                return False, str(e)

        # 2. TODO: WebSocket 推送
        # 需要客户端保持 WebSocket 连接

        delivery["status"] = "pending_client_poll"
        self._save_pending()
        return False, "等待客户端拉取"

    def get_pending_delivery(self, client_id: str) -> List[Dict[str, Any]]:
        """获取指定客户端的待接收序列号"""
        pending = []
        for d in self._pending.values():
            if d.get("client_id") == client_id and d.get("status") == "pending":
                pending.append(d)
        return pending

    def mark_as_delivered(self, delivery_id: str) -> bool:
        """标记为已送达"""
        if delivery_id in self._pending:
            self._pending[delivery_id]["status"] = "delivered"
            self._pending[delivery_id]["sent_at"] = int(time.time())
            self._save_pending()
            return True
        return False


# ============ 单例 ============

_serial_notification_service: Optional[SerialNotificationService] = None
_serial_delivery_service: Optional[SerialDeliveryService] = None


def get_serial_notification_service() -> SerialNotificationService:
    global _serial_notification_service
    if _serial_notification_service is None:
        _serial_notification_service = SerialNotificationService()
    return _serial_notification_service


def get_serial_delivery_service() -> SerialDeliveryService:
    global _serial_delivery_service
    if _serial_delivery_service is None:
        _serial_delivery_service = SerialDeliveryService()
    return _serial_delivery_service
