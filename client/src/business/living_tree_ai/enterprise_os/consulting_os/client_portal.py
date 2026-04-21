"""
客户门户模块

为每个项目创建独立的客户协作空间。
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# ==================== 枚举定义 ====================

class PortalUserRole(Enum):
    """门户用户角色"""
    ADMIN = "admin"                   # 客户管理员
    REVIEWER = "reviewer"             # 审核员
    UPLOADER = "uploader"            # 资料上传员
    VIEWER = "viewer"                # 查看者


class PortalPermission(Enum):
    """门户权限"""
    VIEW_DOCUMENTS = "view_documents"
    DOWNLOAD_DOCUMENTS = "download_documents"
    UPLOAD_DOCUMENTS = "upload_documents"
    COMMENT = "comment"
    APPROVE = "approve"
    MANAGE_USERS = "manage_users"


class PortalAccessLevel(Enum):
    """访问级别"""
    PUBLIC = "public"
    PRIVATE = "private"
    INVITE_ONLY = "invite_only"


# ==================== 数据模型 ====================

@dataclass
class PortalUser:
    """门户用户"""
    user_id: str
    portal_id: str

    # 用户信息
    name: str
    email: str
    phone: str = ""

    # 角色
    role: PortalUserRole = PortalUserRole.VIEWER

    # 权限
    permissions: List[PortalPermission] = field(default_factory=list)

    # 状态
    is_active: bool = True
    last_login: Optional[datetime] = None

    # 头像
    avatar_url: str = ""

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PortalProject:
    """门户项目"""
    portal_id: str
    project_id: str
    client_id: str

    # 访问控制
    access_level: PortalAccessLevel = PortalAccessLevel.INVITE_ONLY

    # 可用功能
    features: List[str] = field(default_factory=list)  # documents/comments/upload/approval

    # 状态
    is_active: bool = True
    expires_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PortalDocument:
    """门户文档"""
    doc_id: str
    portal_id: str
    document_id: str

    # 显示信息
    display_name: str
    description: str = ""

    # 版本
    version: str = "v1.0"

    # 访问控制
    require_signature: bool = False    # 需要电子签章
    signature_status: str = "pending"  # pending/signed/rejected

    # 评论
    allow_comments: bool = True

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PortalMessage:
    """门户消息"""
    message_id: str
    portal_id: str
    sender_id: str
    sender_name: str
    sender_type: str = "internal"       # internal/client/system

    # 内容
    title: str = ""
    content: str = ""
    message_type: str = "info"         # info/warning/action/completion

    # 附件
    attachments: List[Dict] = field(default_factory=list)

    # 状态
    is_read: bool = False
    read_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PortalActivity:
    """门户活动"""
    activity_id: str
    portal_id: str

    # 活动信息
    activity_type: str                  # document_upload/review_comment/signature/approval
    description: str = ""

    # 参与者
    actor_id: str = ""
    actor_name: str = ""

    # 关联实体
    entity_type: str = ""              # document/comment/approval
    entity_id: str = ""

    # 元数据
    metadata: Dict = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.now)


# ==================== 访问管理 ====================

class PortalAccessManager:
    """门户访问管理器"""

    ROLE_PERMISSIONS = {
        PortalUserRole.ADMIN: [
            PortalPermission.VIEW_DOCUMENTS,
            PortalPermission.DOWNLOAD_DOCUMENTS,
            PortalPermission.UPLOAD_DOCUMENTS,
            PortalPermission.COMMENT,
            PortalPermission.APPROVE,
            PortalPermission.MANAGE_USERS,
        ],
        PortalUserRole.REVIEWER: [
            PortalPermission.VIEW_DOCUMENTS,
            PortalPermission.DOWNLOAD_DOCUMENTS,
            PortalPermission.COMMENT,
            PortalPermission.APPROVE,
        ],
        PortalUserRole.UPLOADER: [
            PortalPermission.VIEW_DOCUMENTS,
            PortalPermission.UPLOAD_DOCUMENTS,
            PortalPermission.COMMENT,
        ],
        PortalUserRole.VIEWER: [
            PortalPermission.VIEW_DOCUMENTS,
        ],
    }

    @classmethod
    def get_permissions_for_role(cls, role: PortalUserRole) -> List[PortalPermission]:
        """获取角色对应的权限"""
        return cls.ROLE_PERMISSIONS.get(role, [])

    @classmethod
    def has_permission(
        cls,
        user: PortalUser,
        permission: PortalPermission
    ) -> bool:
        """检查用户是否有指定权限"""
        if user.role == PortalUserRole.ADMIN:
            return True
        return permission in user.permissions


# ==================== 客户门户服务 ====================

class ClientPortalService:
    """
    客户门户服务

    核心功能：
    1. 门户创建和管理
    2. 用户管理
    3. 文档共享
    4. 消息通知
    5. 电子签章
    """

    def __init__(self):
        self._portals: Dict[str, PortalProject] = {}
        self._users: Dict[str, PortalUser] = {}
        self._documents: Dict[str, PortalDocument] = {}
        self._messages: Dict[str, PortalMessage] = {}
        self._activities: Dict[str, PortalActivity] = {}
        self._invite_codes: Dict[str, Dict] = {}  # code -> {portal_id, role, expires}

    def _generate_portal_id(self) -> str:
        return f"PORTAL:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_invite_code(self) -> str:
        import secrets
        return secrets.token_urlsafe(16)

    # ==================== 门户管理 ====================

    async def create_portal(
        self,
        project_id: str,
        client_id: str,
        access_level: PortalAccessLevel = PortalAccessLevel.INVITE_ONLY,
        features: List[str] = None
    ) -> PortalProject:
        """创建门户"""
        portal_id = self._generate_portal_id()

        portal = PortalProject(
            portal_id=portal_id,
            project_id=project_id,
            client_id=client_id,
            access_level=access_level,
            features=features or ["documents", "comments", "upload"]
        )

        self._portals[portal_id] = portal
        return portal

    async def get_portal(self, portal_id: str) -> Optional[PortalProject]:
        """获取门户"""
        return self._portals.get(portal_id)

    async def get_portal_by_project(
        self,
        project_id: str
    ) -> Optional[PortalProject]:
        """通过项目ID获取门户"""
        for portal in self._portals.values():
            if portal.project_id == project_id:
                return portal
        return None

    # ==================== 用户管理 ====================

    async def add_user(
        self,
        portal_id: str,
        name: str,
        email: str,
        role: PortalUserRole,
        phone: str = ""
    ) -> PortalUser:
        """添加门户用户"""
        user_id = hashlib.md5(f"{portal_id}:{email}".encode()).hexdigest()[:16]

        user = PortalUser(
            user_id=user_id,
            portal_id=portal_id,
            name=name,
            email=email,
            phone=phone,
            role=role,
            permissions=PortalAccessManager.get_permissions_for_role(role)
        )

        self._users[user_id] = user
        return user

    async def invite_user(
        self,
        portal_id: str,
        email: str,
        role: PortalUserRole,
        invited_by: str,
        expires_hours: int = 72
    ) -> str:
        """邀请用户（生成邀请码）"""
        invite_code = self._generate_invite_code()

        self._invite_codes[invite_code] = {
            "portal_id": portal_id,
            "email": email,
            "role": role,
            "invited_by": invited_by,
            "expires_at": datetime.now().timestamp() + expires_hours * 3600
        }

        return invite_code

    async def accept_invite(
        self,
        invite_code: str,
        name: str,
        phone: str = ""
    ) -> Optional[PortalUser]:
        """接受邀请"""
        invite = self._invite_codes.get(invite_code)
        if not invite:
            return None

        # 检查过期
        if datetime.now().timestamp() > invite["expires_at"]:
            del self._invite_codes[invite_code]
            return None

        portal_id = invite["portal_id"]
        email = invite["email"]
        role = invite["role"]

        # 创建用户
        user = await self.add_user(portal_id, name, email, role, phone)

        # 删除邀请码
        del self._invite_codes[invite_code]

        return user

    async def get_portal_users(self, portal_id: str) -> List[PortalUser]:
        """获取门户用户"""
        return [
            u for u in self._users.values()
            if u.portal_id == portal_id and u.is_active
        ]

    async def remove_user(self, user_id: str) -> bool:
        """移除用户"""
        user = self._users.get(user_id)
        if not user:
            return False

        user.is_active = False
        return True

    # ==================== 文档共享 ====================

    async def share_document(
        self,
        portal_id: str,
        document_id: str,
        display_name: str,
        version: str = "v1.0",
        require_signature: bool = False,
        allow_comments: bool = True
    ) -> PortalDocument:
        """共享文档到门户"""
        doc_id = f"{portal_id}:{document_id}"

        doc = PortalDocument(
            doc_id=doc_id,
            portal_id=portal_id,
            document_id=document_id,
            display_name=display_name,
            version=version,
            require_signature=require_signature,
            allow_comments=allow_comments
        )

        self._documents[doc_id] = doc

        # 记录活动
        await self._log_activity(
            portal_id,
            "document_share",
            f"共享文档: {display_name}",
            entity_type="document",
            entity_id=doc_id
        )

        return doc

    async def get_portal_documents(
        self,
        portal_id: str
    ) -> List[PortalDocument]:
        """获取门户文档"""
        return [
            d for d in self._documents.values()
            if d.portal_id == portal_id
        ]

    # ==================== 消息通知 ====================

    async def send_message(
        self,
        portal_id: str,
        sender_id: str,
        sender_name: str,
        title: str,
        content: str,
        sender_type: str = "internal",
        message_type: str = "info",
        attachments: List[Dict] = None
    ) -> PortalMessage:
        """发送消息"""
        message_id = f"MSG:{datetime.now().timestamp()}"

        message = PortalMessage(
            message_id=message_id,
            portal_id=portal_id,
            sender_id=sender_id,
            sender_name=sender_name,
            title=title,
            content=content,
            sender_type=sender_type,
            message_type=message_type,
            attachments=attachments or []
        )

        self._messages[message_id] = message
        return message

    async def get_unread_messages(
        self,
        portal_id: str
    ) -> List[PortalMessage]:
        """获取未读消息"""
        return [
            m for m in self._messages.values()
            if m.portal_id == portal_id and not m.is_read
        ]

    async def mark_as_read(self, message_id: str) -> bool:
        """标记消息已读"""
        message = self._messages.get(message_id)
        if not message:
            return False

        message.is_read = True
        message.read_at = datetime.now()
        return True

    # ==================== 活动日志 ====================

    async def _log_activity(
        self,
        portal_id: str,
        activity_type: str,
        description: str,
        actor_id: str = "",
        actor_name: str = "",
        entity_type: str = "",
        entity_id: str = "",
        metadata: Dict = None
    ) -> PortalActivity:
        """记录活动"""
        activity_id = f"ACT:{datetime.now().timestamp()}"

        activity = PortalActivity(
            activity_id=activity_id,
            portal_id=portal_id,
            activity_type=activity_type,
            description=description,
            actor_id=actor_id,
            actor_name=actor_name,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {}
        )

        self._activities[activity_id] = activity
        return activity

    async def get_recent_activities(
        self,
        portal_id: str,
        limit: int = 20
    ) -> List[PortalActivity]:
        """获取最近活动"""
        activities = [
            a for a in self._activities.values()
            if a.portal_id == portal_id
        ]

        activities.sort(key=lambda x: x.created_at, reverse=True)
        return activities[:limit]

    # ==================== 电子签章 ====================

    async def request_signature(
        self,
        doc_id: str,
        signer_id: str,
        signer_name: str
    ) -> bool:
        """请求签名"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        doc.signature_status = "pending"
        return True

    async def sign_document(
        self,
        doc_id: str,
        signed_by: str,
        signed_by_name: str,
        signature_data: str = ""
    ) -> bool:
        """签署文档"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        doc.signature_status = "signed"

        # 记录活动
        await self._log_activity(
            doc.portal_id,
            "signature",
            f"{signed_by_name} 已签署文档",
            actor_id=signed_by,
            actor_name=signed_by_name,
            entity_type="document",
            entity_id=doc_id
        )

        return True


# ==================== 单例模式 ====================

_portal_service: Optional[ClientPortalService] = None


def get_portal_service() -> ClientPortalService:
    """获取门户服务单例"""
    global _portal_service
    if _portal_service is None:
        _portal_service = ClientPortalService()
    return _portal_service
