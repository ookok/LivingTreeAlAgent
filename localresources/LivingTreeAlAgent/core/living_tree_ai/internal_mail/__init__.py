"""
内部邮件系统 (Internal Mail System)

基于 P2P WebSocket 的直连架构：
- 无需公网 IP：节点间通过 WebSocket 长连接通信
- 无需 SMTP：直接传输结构化 JSON
- 无需 DNS：通过 Node ID 直接寻址

核心理念：内部邮件是分布式 AI 大脑的协同神经网络
"""

__version__ = "1.0.0"

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import asyncio
import time
import hashlib
import json
import uuid


# ============================================================================
# 身份与地址
# ============================================================================

@dataclass
class NodeIdentity:
    """节点身份"""
    node_id: str                           # 唯一标识 (格式: "user_id@device_id")
    user_id: str                           # 用户ID
    device_id: str                         # 设备ID
    display_name: str                      # 显示名称
    public_key: Optional[str] = None      # 公钥 (用于E2EE)
    email: Optional[str] = None           # 关联外部邮箱
    is_online: bool = False               # 在线状态
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, user_id: str, device_id: str, display_name: str) -> "NodeIdentity":
        """创建新身份"""
        node_id = f"{user_id}@{device_id}"
        return cls(
            node_id=node_id,
            user_id=user_id,
            device_id=device_id,
            display_name=display_name
        )

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "display_name": self.display_name,
            "public_key": self.public_key,
            "email": self.email,
            "is_online": self.is_online,
            "last_seen": self.last_seen,
            "metadata": self.metadata
        }


# ============================================================================
# 邮件消息结构
# ============================================================================

class MessageType(Enum):
    """消息类型"""
    MAIL = "mail"                         # 邮件
    MAIL_RECEIPT = "mail_receipt"         # 回执
    MAIL_READ = "mail_read"               # 已读回执
    MAIL_REPLY = "mail_reply"             # 回复
    MAIL_FORWARD = "mail_forward"         # 转发
    TYPING = "typing"                     # 正在输入
    PRESENCE = "presence"                 # 在线状态


class AttachmentStatus(Enum):
    """附件状态"""
    PENDING = "pending"       # 待上传
    UPLOADING = "uploading"   # 上传中
    AVAILABLE = "available"   # 可用
    FAILED = "failed"         # 失败


@dataclass
class Attachment:
    """附件"""
    file_id: str                          # 文件ID (UUID)
    file_name: str                        # 文件名
    file_size: int                        # 文件大小 (bytes)
    mime_type: str                        # MIME类型
    hash_sha256: str                      # SHA256哈希
    hash_md5: str = ""                    # MD5哈希 (兼容)
    status: AttachmentStatus = AttachmentStatus.PENDING
    url: Optional[str] = None            # 下载URL (DHT地址)

    def to_dict(self) -> Dict:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "hash_sha256": self.hash_sha256,
            "hash_md5": self.hash_md5,
            "status": self.status.value,
            "url": self.url
        }


@dataclass
class MailMessage:
    """邮件消息"""
    mail_id: str                          # 邮件ID (UUID)
    from_node: str                        # 发件人 node_id
    to_nodes: List[str]                   # 收件人 node_id 列表
    subject: str                          # 主题
    body: str                             # 正文 (可能是加密的)
    body_plain: Optional[str] = None      # 原文 (解密后)
    attachments: List[Attachment] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # 引用邮件ID (用于回复/转发)
    headers: Dict[str, str] = field(default_factory=dict)  # 自定义头
    priority: int = 5                     # 优先级 1-10
    is_encrypted: bool = False            # 是否加密
    is_draft: bool = False                # 是否为草稿
    tags: List[str] = field(default_factory=list)  # 标签
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None       # 发送时间
    read_at: Optional[float] = None        # 阅读时间

    # AI 增强字段
    ai_context: Optional[Dict] = None     # AI 上下文
    ai_summary: Optional[str] = None      # AI 摘要
    is_auto_generated: bool = False       # 是否AI自动生成

    def to_dict(self) -> Dict:
        return {
            "mail_id": self.mail_id,
            "from_node": self.from_node,
            "to_nodes": self.to_nodes,
            "subject": self.subject,
            "body": self.body,
            "body_plain": self.body_plain,
            "attachments": [a.to_dict() for a in self.attachments],
            "references": self.references,
            "headers": self.headers,
            "priority": self.priority,
            "is_encrypted": self.is_encrypted,
            "is_draft": self.is_draft,
            "tags": self.tags,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "read_at": self.read_at,
            "ai_context": self.ai_context,
            "ai_summary": self.ai_summary,
            "is_auto_generated": self.is_auto_generated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MailMessage":
        """从字典创建"""
        data = data.copy()
        data["attachments"] = [Attachment(**a) if isinstance(a, dict) else a for a in data.get("attachments", [])]
        return cls(**data)


# ============================================================================
# 邮件文件夹
# ============================================================================

class MailFolder(Enum):
    """邮件文件夹"""
    INBOX = "inbox"                       # 收件箱
    SENT = "sent"                         # 已发送
    DRAFTS = "drafts"                     # 草稿箱
    TRASH = "trash"                       # 垃圾箱
    ARCHIVE = "archive"                    # 归档
    STARRED = "starred"                    # 星标


# ============================================================================
# 邮件数据库 (本地存储)
# ============================================================================

class MailDatabase:
    """
    邮件本地数据库 (SQLite)
    负责邮件的持久化存储
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 邮件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mails (
                mail_id TEXT PRIMARY KEY,
                from_node TEXT NOT NULL,
                to_nodes TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                body_plain TEXT,
                attachments TEXT,
                references_list TEXT,
                headers TEXT,
                priority INTEGER DEFAULT 5,
                is_encrypted INTEGER DEFAULT 0,
                is_draft INTEGER DEFAULT 0,
                tags TEXT,
                folder TEXT DEFAULT 'inbox',
                is_starred INTEGER DEFAULT 0,
                is_read INTEGER DEFAULT 0,
                ai_context TEXT,
                ai_summary TEXT,
                is_auto_generated INTEGER DEFAULT 0,
                created_at REAL,
                sent_at REAL,
                read_at REAL,
                deleted_at REAL
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_from ON mails(from_node)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_to ON mails(to_nodes)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_folder ON mails(folder)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mails_created ON mails(created_at)")

        conn.commit()
        conn.close()

    def save_mail(self, mail: MailMessage, folder: str = "inbox"):
        """保存邮件"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO mails (
                mail_id, from_node, to_nodes, subject, body, body_plain,
                attachments, references_list, headers, priority, is_encrypted,
                is_draft, tags, folder, is_starred, is_read, ai_context,
                ai_summary, is_auto_generated, created_at, sent_at, read_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mail.mail_id,
            mail.from_node,
            json.dumps(mail.to_nodes),
            mail.subject,
            mail.body,
            mail.body_plain,
            json.dumps([a.to_dict() for a in mail.attachments]),
            json.dumps(mail.references),
            json.dumps(mail.headers),
            mail.priority,
            int(mail.is_encrypted),
            int(mail.is_draft),
            json.dumps(mail.tags),
            folder,
            0,  # is_starred
            0,  # is_read
            json.dumps(mail.ai_context) if mail.ai_context else None,
            mail.ai_summary,
            int(mail.is_auto_generated),
            mail.created_at,
            mail.sent_at,
            mail.read_at
        ))

        conn.commit()
        conn.close()

    def get_mails(self, folder: str, node_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取邮件列表"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 根据文件夹筛选
        if folder == "inbox":
            cursor.execute("""
                SELECT * FROM mails
                WHERE ? IN (SELECT value FROM json_each(to_nodes))
                AND folder = 'inbox' AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (node_id, limit, offset))
        elif folder == "sent":
            cursor.execute("""
                SELECT * FROM mails
                WHERE from_node = ? AND folder = 'sent' AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (node_id, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM mails
                WHERE folder = ? AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (folder, limit, offset))

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def mark_as_read(self, mail_id: str):
        """标记为已读"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE mails SET is_read = 1, read_at = ? WHERE mail_id = ?",
                      (time.time(), mail_id))
        conn.commit()
        conn.close()

    def delete_mail(self, mail_id: str):
        """删除邮件 (软删除)"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE mails SET deleted_at = ? WHERE mail_id = ?",
                      (time.time(), mail_id))
        conn.commit()
        conn.close()


# ============================================================================
# 邮件传输协议
# ============================================================================

class MailTransport:
    """
    邮件传输层
    基于 WebSocket 的 P2P 传输
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.connections: Dict[str, Any] = {}  # node_id -> WebSocket 连接
        self.pending_messages: Dict[str, asyncio.Queue] = {}  # 离线消息队列

    async def send_mail(self, mail: MailMessage, recipient_node_id: str) -> bool:
        """发送邮件到指定节点"""
        if recipient_node_id in self.connections:
            # 在线：直接发送
            ws = self.connections[recipient_node_id]
            await ws.send_json({
                "type": "mail",
                "payload": mail.to_dict()
            })
            return True
        else:
            # 离线：加入离线队列
            if recipient_node_id not in self.pending_messages:
                self.pending_messages[recipient_node_id] = asyncio.Queue()
            await self.pending_messages[recipient_node_id].put(mail)
            return False

    async def broadcast_mail(self, mail: MailMessage) -> Dict[str, bool]:
        """广播邮件到多个收件人"""
        results = {}
        for recipient in mail.to_nodes:
            results[recipient] = await self.send_mail(mail, recipient)
        return results

    async def receive_mail(self, data: Dict) -> MailMessage:
        """接收邮件"""
        return MailMessage.from_dict(data["payload"])

    def add_connection(self, node_id: str, websocket: Any):
        """添加连接"""
        self.connections[node_id] = websocket

        # 发送离线消息
        if node_id in self.pending_messages:
            queue = self.pending_messages[node_id]
            while not queue.empty():
                mail = queue.get_nowait()
                asyncio.create_task(self.send_mail(mail, node_id))

    def remove_connection(self, node_id: str):
        """移除连接"""
        if node_id in self.connections:
            del self.connections[node_id]


# ============================================================================
# DHT 附件存储
# ============================================================================

class DHTAttachmentStore:
    """
    DHT 附件存储
    大文件通过 DHT 网络分发，仅传输 Hash
    """

    def __init__(self, dht_node: Any = None):
        self.dht_node = dht_node
        self.local_files: Dict[str, bytes] = {}  # 本地缓存的文件

    async def store_attachment(self, file_data: bytes, file_name: str) -> Attachment:
        """存储附件，返回 Attachment 对象"""
        # 计算哈希
        sha256_hash = hashlib.sha256(file_data).hexdigest()
        md5_hash = hashlib.md5(file_data).hexdigest()

        # 生成文件ID
        file_id = str(uuid.uuid4())

        # 本地存储
        self.local_files[sha256_hash] = file_data

        # 如果有 DHT 节点，注册到 DHT
        if self.dht_node:
            await self.dht_node.put(sha256_hash, file_data)

        return Attachment(
            file_id=file_id,
            file_name=file_name,
            file_size=len(file_data),
            mime_type=self._guess_mime_type(file_name),
            hash_sha256=sha256_hash,
            hash_md5=md5_hash,
            status=AttachmentStatus.AVAILABLE,
            url=f"dht://{sha256_hash}"
        )

    async def retrieve_attachment(self, hash_sha256: str) -> Optional[bytes]:
        """根据 Hash 检索附件"""
        # 先查本地
        if hash_sha256 in self.local_files:
            return self.local_files[hash_sha256]

        # 查 DHT 网络
        if self.dht_node:
            result = await self.dht_node.get(hash_sha256)
            if result:
                self.local_files[hash_sha256] = result
                return result

        return None

    def _guess_mime_type(self, file_name: str) -> str:
        """猜测 MIME 类型"""
        ext = file_name.split(".")[-1].lower()
        mime_types = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "zip": "application/zip",
            "py": "text/x-python",
            "js": "text/javascript",
            "html": "text/html",
            "css": "text/css",
        }
        return mime_types.get(ext, "application/octet-stream")


# ============================================================================
# AI 增强引擎
# ============================================================================

class MailAIEnhancer:
    """
    邮件 AI 增强引擎
    上下文感知、结构化协作、知识沉淀
    """

    def __init__(self, brain: Any = None):
        self.brain = brain

    async def analyze_context(self, mail: MailMessage, user_context: Dict) -> Dict:
        """
        分析邮件上下文
        返回 AI 增强数据
        """
        context = {
            "related_projects": [],
            "related_documents": [],
            "mentioned_users": [],
            "suggested_actions": [],
            "intent": "general"
        }

        # 分析内容关键词
        body_lower = mail.body.lower()

        # 检测意图
        if any(k in body_lower for k in ["bug", "错误", "崩溃"]):
            context["intent"] = "bug_report"
            context["suggested_actions"].append("create_issue")
        elif any(k in body_lower for k in ["需求", "feature", "建议"]):
            context["intent"] = "feature_request"
            context["suggested_actions"].append("create_ticket")
        elif any(k in body_lower for k in ["问题", "help", "？"]):
            context["intent"] = "question"
            context["suggested_actions"].append("add_to_faq")
        elif any(k in body_lower for k in ["部署", "deploy", "发布"]):
            context["intent"] = "deployment"
            context["suggested_actions"].append("require_approval")

        # 关联项目上下文
        if self.brain and user_context:
            # 从中心大脑获取相关项目
            project = user_context.get("current_project")
            if project:
                context["related_projects"].append(project)

        # 提取 @ 提及的用户
        import re
        mentions = re.findall(r'@(\w+)', mail.body)
        context["mentioned_users"] = mentions

        return context

    async def generate_reply_suggestion(self, mail: MailMessage) -> str:
        """生成回复建议"""
        if mail.ai_context:
            intent = mail.ai_context.get("intent", "general")

            suggestions = {
                "bug_report": f"感谢报告 Bug！我来看看这个问题。",
                "feature_request": f"这个需求很有价值，我会评估后给出反馈。",
                "question": f"根据我的了解，",
                "deployment": f"收到，我会按流程处理部署请求。",
                "general": f"收到您的邮件，我来处理。"
            }

            return suggestions.get(intent, suggestions["general"])

        return "收到您的邮件，我会尽快处理。"

    async def auto_tag(self, mail: MailMessage) -> List[str]:
        """自动打标签"""
        tags = []
        body_lower = mail.body.lower()

        # 基于内容自动打标签
        if any(k in body_lower for k in ["紧急", "urgent", "重要"]):
            tags.append("重要")
        if any(k in body_lower for k in ["个人", "personal"]):
            tags.append("私人")
        if any(k in body_lower for k in ["会议", "meeting"]):
            tags.append("会议")
        if any(k in body_lower for k in ["决策", "决定"]):
            tags.append("待决策")
        if mail.subject.startswith("Re:"):
            tags.append("回复")
        if mail.subject.startswith("Fwd:"):
            tags.append("转发")

        return tags

    async def summarize(self, mail: MailMessage) -> str:
        """生成邮件摘要 (AI)"""
        # 简化实现：取前50字
        body = mail.body_plain or mail.body
        summary = body[:100].strip()
        if len(body) > 100:
            summary += "..."
        return summary


# ============================================================================
# 邮件会话管理
# ============================================================================

class MailSession:
    """
    邮件会话
    管理同一主题的邮件对话
    """

    def __init__(self, session_id: str, root_mail_id: str):
        self.session_id = session_id
        self.root_mail_id = root_mail_id
        self.participants: Set[str] = set()
        self.mail_ids: List[str] = [root_mail_id]
        self.created_at = time.time()
        self.updated_at = time.time()

    def add_participant(self, node_id: str):
        """添加参与者"""
        self.participants.add(node_id)

    def add_reply(self, mail_id: str):
        """添加回复"""
        self.mail_ids.append(mail_id)
        self.updated_at = time.time()

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "root_mail_id": self.root_mail_id,
            "participants": list(self.participants),
            "mail_ids": self.mail_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


# ============================================================================
# 邮件管理器 (核心)
# ============================================================================

class MailManager:
    """
    邮件管理器
    整合所有邮件功能
    """

    def __init__(
        self,
        node_identity: NodeIdentity,
        db_path: str,
        transport: MailTransport,
        dht_store: DHTAttachmentStore = None,
        ai_enhancer: MailAIEnhancer = None
    ):
        self.identity = node_identity
        self.transport = transport
        self.dht_store = dht_store or DHTAttachmentStore()
        self.ai_enhancer = ai_enhancer or MailAIEnhancer()
        self.db = MailDatabase(db_path)
        self.sessions: Dict[str, MailSession] = {}

        # 联系人缓存
        self.contacts: Dict[str, NodeIdentity] = {}

    async def send_mail(
        self,
        to_nodes: List[str],
        subject: str,
        body: str,
        attachments: List[Attachment] = None,
        references: List[str] = None,
        priority: int = 5,
        tags: List[str] = None,
        is_draft: bool = False
    ) -> MailMessage:
        """发送邮件"""

        # 创建邮件
        mail = MailMessage(
            mail_id=str(uuid.uuid4()),
            from_node=self.identity.node_id,
            to_nodes=to_nodes,
            subject=subject,
            body=body,
            attachments=attachments or [],
            references=references or [],
            priority=priority,
            tags=tags or [],
            is_draft=is_draft,
            created_at=time.time()
        )

        # AI 增强
        if not is_draft:
            mail.ai_context = await self.ai_enhancer.analyze_context(mail, {})
            mail.ai_summary = await self.ai_enhancer.summarize(mail)
            mail.tags.extend(await self.ai_enhancer.auto_tag(mail))

        # 发送
        if not is_draft:
            mail.sent_at = time.time()
            results = await self.transport.broadcast_mail(mail)

            # 更新附件状态
            for att in mail.attachments:
                if results.get(att.hash_sha256):
                    att.status = AttachmentStatus.AVAILABLE

        # 保存到本地
        folder = "drafts" if is_draft else "sent"
        self.db.save_mail(mail, folder)

        return mail

    async def reply_to(self, original_mail: MailMessage, body: str) -> MailMessage:
        """回复邮件"""
        # 检查是否有会话
        if original_mail.mail_id in self.sessions:
            session = self.sessions[original_mail.mail_id]
        else:
            # 创建新会话
            session = MailSession(
                session_id=str(uuid.uuid4()),
                root_mail_id=original_mail.mail_id
            )
            self.sessions[original_mail.mail_id] = session

        session.add_participant(self.identity.node_id)
        for node in original_mail.to_nodes:
            session.add_participant(node)

        # 构建回复
        reply = await self.send_mail(
            to_nodes=[original_mail.from_node],
            subject=f"Re: {original_mail.subject}",
            body=body,
            references=[original_mail.mail_id] + original_mail.references,
            tags=["回复"]
        )

        session.add_reply(reply.mail_id)
        return reply

    async def forward(self, original_mail: MailMessage, to_nodes: List[str]) -> MailMessage:
        """转发邮件"""
        forward = await self.send_mail(
            to_nodes=to_nodes,
            subject=f"Fwd: {original_mail.subject}",
            body=f"\n\n--- 转发内容 ---\n\n{original_mail.body}",
            references=original_mail.references,
            tags=["转发"]
        )
        return forward

    async def get_inbox(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取收件箱"""
        return self.db.get_mails("inbox", self.identity.node_id, limit, offset)

    async def get_sent(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取已发送"""
        return self.db.get_mails("sent", self.identity.node_id, limit, offset)

    async def get_drafts(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取草稿箱"""
        return self.db.get_mails("drafts", self.identity.node_id, limit, offset)

    async def receive_mail(self, mail: MailMessage) -> bool:
        """接收邮件"""
        # 保存到收件箱
        self.db.save_mail(mail, "inbox")

        # 发送回执
        await self.transport.send_mail(MailMessage(
            mail_id=str(uuid.uuid4()),
            from_node=self.identity.node_id,
            to_nodes=[mail.from_node],
            subject=f"Re: {mail.subject}",
            body="",
            headers={"in-reply-to": mail.mail_id}
        ), mail.from_node)

        return True

    async def mark_as_read(self, mail_id: str):
        """标记为已读"""
        self.db.mark_as_read(mail_id)

    async def delete_mail(self, mail_id: str):
        """删除邮件"""
        self.db.delete_mail(mail_id)

    async def upload_attachment(self, file_data: bytes, file_name: str) -> Attachment:
        """上传附件"""
        return await self.dht_store.store_attachment(file_data, file_name)


# ============================================================================
# 消息路由器 (中心节点)
# ============================================================================

class MessageRouter:
    """
    消息路由器
    中心节点负责路由转发
    """

    def __init__(self):
        self.node_registry: Dict[str, NodeIdentity] = {}  # node_id -> identity
        self.online_nodes: Set[str] = set()              # 在线节点

    def register_node(self, identity: NodeIdentity):
        """注册节点"""
        self.node_registry[identity.node_id] = identity
        identity.is_online = True
        identity.last_seen = time.time()
        self.online_nodes.add(identity.node_id)

    def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self.online_nodes:
            self.online_nodes.remove(node_id)
        if node_id in self.node_registry:
            self.node_registry[node_id].is_online = False

    def resolve_node(self, node_id: str) -> Optional[NodeIdentity]:
        """解析节点身份"""
        return self.node_registry.get(node_id)

    def find_node_route(self, node_id: str) -> Optional[str]:
        """查找节点路由信息"""
        identity = self.resolve_node(node_id)
        if identity and identity.is_online:
            return f"ws://{identity.metadata.get('host', 'localhost')}:{identity.metadata.get('port', 8080)}"
        return None

    def broadcast_presence(self):
        """广播在线状态"""
        return list(self.online_nodes)


# ============================================================================
# 端到端加密
# ============================================================================

class E2EEncryption:
    """
    端到端加密
    使用 X25519 密钥交换 + ChaCha20 加密
    """

    def __init__(self):
        self.private_key = None
        self.public_key = None

    def generate_keypair(self):
        """生成密钥对"""
        # 简化实现，实际应使用 cryptography 库
        import secrets
        self.private_key = secrets.token_bytes(32)
        self.public_key = hashlib.sha256(self.private_key).digest()
        return self.public_key

    def encrypt(self, message: str, recipient_public_key: bytes) -> str:
        """加密消息"""
        # 简化实现
        import base64
        combined = message.encode() + recipient_public_key
        encrypted = base64.b64encode(combined).decode()
        return encrypted

    def decrypt(self, encrypted_message: str, sender_public_key: bytes) -> str:
        """解密消息"""
        import base64
        combined = base64.b64decode(encrypted_message.encode())
        message = combined[:-32]
        return message.decode()


# ============================================================================
# 工厂函数
# ============================================================================

def create_node_identity(user_id: str, device_id: str, display_name: str) -> NodeIdentity:
    """创建节点身份"""
    return NodeIdentity.create(user_id, device_id, display_name)


def create_mail_manager(
    identity: NodeIdentity,
    db_path: str = "~/.hermes-desktop/mails.db"
) -> MailManager:
    """创建邮件管理器"""
    import os
    db_path = os.path.expanduser(db_path)

    transport = MailTransport(identity.node_id)
    return MailManager(identity, db_path, transport)


def create_message_router() -> MessageRouter:
    """创建消息路由器"""
    return MessageRouter()
