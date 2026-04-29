"""
统一聊天核心数据模型 - Unified Chat Core Models
参考 Element/Discord/Telegram 设计，支持多模态消息类型

消息类型统一接口:
- text: 纯文本消息
- rich_text: 富文本消息 (Markdown/HTML)
- file: 文件消息 (图片/文档/视频等)
- voice: 语音消息
- video: 视频消息
- link: 链接消息 (带预览)
- image: 图片消息 (直接显示)
- system: 系统消息 (加群/退群等)
"""

import uuid
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"           # 纯文本
    RICH_TEXT = "rich_text" # 富文本 (Markdown)
    FILE = "file"           # 文件
    VOICE = "voice"         # 语音
    VIDEO = "video"         # 视频
    LINK = "link"           # 链接预览
    IMAGE = "image"         # 图片
    SYSTEM = "system"       # 系统消息


class MessageStatus(str, Enum):
    """消息状态"""
    SENDING = "sending"      # 发送中
    SENT = "sent"            # 已发送
    DELIVERED = "delivered"  # 已送达
    READ = "read"           # 已读
    FAILED = "failed"       # 发送失败


class SessionType(str, Enum):
    """会话类型"""
    PRIVATE = "private"      # 私聊
    GROUP = "group"          # 群聊
    CHANNEL = "channel"      # 频道


class OnlineStatus(str, Enum):
    """在线状态"""
    ONLINE = "online"        # 在线
    OFFLINE = "offline"      # 离线
    AWAY = "away"            # 离开
    BUSY = "busy"            # 忙碌
    DO_NOT_DISTURB = "dnd"   # 请勿打扰


class ConnectionQuality(str, Enum):
    """连接质量"""
    EXCELLENT = "excellent"  # 优秀 (RTT < 50ms)
    GOOD = "good"           # 良好 (RTT < 150ms)
    FAIR = "fair"           # 一般 (RTT < 300ms)
    POOR = "poor"           # 较差 (RTT >= 300ms)


# ============ 核心数据模型 ============

@dataclass
class LinkPreview:
    """链接预览元数据 (Telegram 式 og: 快照)"""
    url: str
    title: str = ""
    description: str = ""
    image_url: str = ""      # og:image
    site_name: str = ""      # og:site_name
    favicon: str = ""         # 网站图标
    mime_type: str = "text/html"
    loaded: bool = False


@dataclass
class FileMeta:
    """文件/音视频元数据"""
    file_id: str = ""        # 唯一文件ID
    file_name: str = ""      # 文件名
    file_size: int = 0       # 文件大小 (bytes)
    mime_type: str = ""      # MIME类型
    duration: float = 0     # 音视频时长 (秒)
    width: int = 0           # 图片/视频宽度
    height: int = 0          # 图片/视频高度
    thumbnail: Optional[bytes] = None  # 缩略图
    path: str = ""           # 本地路径
    url: str = ""            # 远程URL
    checksum: str = ""       # 文件校验和
    chunks: List[str] = field(default_factory=list)  # 分片列表


@dataclass
class UnifiedMessage:
    """
    统一消息体 - 所有消息类型的父类

    设计参考:
    - Element: m.room.message 结构
    - Telegram: message 对象
    """
    # 基础字段
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.TEXT
    content: Any = ""        # 消息内容 (str/dict/FileMeta)
    sender_id: str = ""      # 发送者节点ID
    sender_name: str = ""    # 发送者显示名
    sender_avatar: str = "" # 发送者头像URL
    session_id: str = ""     # 会话ID
    timestamp: float = field(default_factory=time.time)
    status: MessageStatus = MessageStatus.SENDING

    # 富文本/链接专用
    preview: Optional[LinkPreview] = None

    # 文件/音视频专用
    meta: Optional[FileMeta] = None

    # 回复/引用
    reply_to: Optional[str] = None   # 被回复的消息ID
    reply_preview: str = ""           # 被回复的消息预览

    # 加密相关
    encrypted: bool = False
    encrypted_content: Optional[bytes] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_outgoing(self, my_id: str) -> bool:
        """判断是否是我发送的消息"""
        return self.sender_id == my_id

    def get_display_time(self) -> str:
        """获取显示用时间"""
        import datetime
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        today = datetime.datetime.today().date()
        if dt.date() == today:
            return dt.strftime("%H:%M")
        elif dt.year == today.year:
            return dt.strftime("%m-%d %H:%M")
        else:
            return dt.strftime("%Y-%m-%d %H:%M")

    def get_content_str(self) -> str:
        """获取内容的字符串表示"""
        if isinstance(self.content, str):
            return self.content
        elif self.type == MessageType.FILE and self.meta:
            return f"[文件] {self.meta.file_name}"
        elif self.type == MessageType.VOICE:
            return "[语音消息]"
        elif self.type == MessageType.VIDEO:
            return "[视频消息]"
        elif self.type == MessageType.IMAGE:
            return "[图片]"
        elif self.type == MessageType.LINK and self.preview:
            return f"[链接] {self.preview.title or self.preview.url}"
        elif self.type == MessageType.SYSTEM:
            return str(self.content)
        return "[未知消息]"


@dataclass
class ChatSession:
    """聊天会话"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: SessionType = SessionType.PRIVATE
    name: str = ""                    # 会话名称 (群名/用户名)
    peer_id: str = ""                 # 对端节点ID (私聊用)
    avatar: str = ""                  # 会话头像
    last_message: Optional[UnifiedMessage] = None
    last_message_time: float = 0
    unread_count: int = 0
    is_pinned: bool = False
    is_muted: bool = False
    is_encrypted: bool = True
    created_at: float = field(default_factory=time.time)

    # 群聊专用
    members: List[str] = field(default_factory=list)  # 成员ID列表
    admin_ids: List[str] = field(default_factory=list)  # 管理员ID列表

    # 扩展
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_display_name(self, my_id: str) -> str:
        """获取显示名称"""
        if self.name:
            return self.name
        if self.type == SessionType.PRIVATE:
            return self.peer_id[:12] + "..." if len(self.peer_id) > 12 else self.peer_id
        return "未命名会话"

    def update_last_message(self, msg: UnifiedMessage):
        """更新最后消息"""
        self.last_message = msg
        self.last_message_time = msg.timestamp
        if msg.sender_id != my_id if 'my_id' in dir() else True:
            if msg.status == MessageStatus.DELIVERED or msg.status == MessageStatus.READ:
                self.unread_count += 1


@dataclass
class PeerInfo:
    """对端节点信息"""
    node_id: str = ""
    short_id: str = ""               # 短ID (8-12位)
    name: str = ""
    avatar: str = ""
    status: OnlineStatus = OnlineStatus.OFFLINE
    last_seen: float = 0
    connection_quality: ConnectionQuality = ConnectionQuality.POOR
    public_key: str = ""

    # 能力支持
    capabilities: List[str] = field(default_factory=list)
    # ["text", "file", "voice", "video", "live", "email"]

    def get_status_display(self) -> str:
        """获取状态显示"""
        if self.status == OnlineStatus.ONLINE:
            return "在线"
        elif self.status == OnlineStatus.AWAY:
            return "离开"
        elif self.status == OnlineStatus.BUSY:
            return "忙碌"
        elif self.status == OnlineStatus.DO_NOT_DISTURB:
            return "请勿打扰"
        else:
            if self.last_seen > 0:
                import datetime
                dt = datetime.datetime.fromtimestamp(self.last_seen)
                return f"离线 {dt.strftime('%m-%d %H:%M')}"
            return "离线"

    def get_quality_icon(self) -> str:
        """获取连接质量图标"""
        return {
            ConnectionQuality.EXCELLENT: "🟢",
            ConnectionQuality.GOOD: "🟡",
            ConnectionQuality.FAIR: "🟠",
            ConnectionQuality.POOR: "🔴"
        }.get(self.connection_quality, "⚪")


@dataclass
class NetworkStatus:
    """网络状态"""
    connected: bool = False
    mode: str = "unknown"           # "p2p", "relay", "offline"
    relay_server: str = ""           # 中继服务器地址
    rtt: float = 0                  # 往返延迟 (ms)
    packet_loss: float = 0          # 丢包率 (%)
    jitter: float = 0              # 抖动 (ms)
    bandwidth_up: float = 0         # 上行带宽 (Mbps)
    bandwidth_down: float = 0       # 下行带宽 (Mbps)
    nat_type: str = "unknown"       # NAT类型


@dataclass
class CallSession:
    """通话会话"""
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    peer_id: str = ""
    call_type: str = "voice"         # "voice" / "video"
    status: str = "calling"          # calling / ringing / connected / ended
    started_at: float = 0
    duration: float = 0              # 通话时长 (秒)


# ============ 常量定义 ============

MAX_MESSAGE_LENGTH = 10000          # 最大消息长度
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 最大文件 2GB
THUMBNAIL_SIZE = (200, 200)         # 缩略图尺寸
CHUNK_SIZE = 512 * 1024             # 分片大小 512KB

# 消息类型图标
MESSAGE_TYPE_ICONS = {
    MessageType.TEXT: "💬",
    MessageType.RICH_TEXT: "📝",
    MessageType.FILE: "📎",
    MessageType.VOICE: "🎙️",
    MessageType.VIDEO: "📹",
    MessageType.LINK: "🔗",
    MessageType.IMAGE: "🖼️",
    MessageType.SYSTEM: "ℹ️",
}

# 在线状态图标
STATUS_ICONS = {
    OnlineStatus.ONLINE: "🟢",
    OnlineStatus.OFFLINE: "⚪",
    OnlineStatus.AWAY: "🟡",
    OnlineStatus.BUSY: "🔴",
    OnlineStatus.DO_NOT_DISTURB: "🔴",
}
