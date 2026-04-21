"""
统一聊天核心调度器 - Chat Hub
整合所有聊天子模块, 提供统一的聊天服务接口

模块:
- SessionManager: 会话管理
- LinkPreviewService: 链接预览
- StatusMonitor: 状态监控
- P2PConnector: P2P连接 (复用)
- 去中心化邮箱: 邮件通道 (复用)
"""

import asyncio
import uuid
import time
from typing import Optional, List, Dict, Callable, Any
from pathlib import Path

from .models import (
    UnifiedMessage, ChatSession, PeerInfo,
    MessageType, MessageStatus, SessionType, OnlineStatus,
    FileMeta, LinkPreview, CallSession
)
# 从 p2p_connector 导入 ChannelType (避免循环导入)
from ..p2p_connector.models import ChannelType
from .session_manager import SessionManager, get_session_manager
from .link_preview import LinkPreviewService, get_link_preview_service
from .status_monitor import StatusMonitor, get_status_monitor


class ChatHub:
    """
    统一聊天核心调度器

    设计目标:
    1. 统一接口: 文本/文件/语音/视频/邮件/直播
    2. 统一消息流: 同一套消息存储和展示
    3. 状态共享: 各模块状态实时同步到 UI

    参考 Element/Discord 的统一消息架构:
    - 所有消息类型统一存储和展示
    - 不同通道(text/file/voice)无缝切换
    """

    _instance: Optional['ChatHub'] = None

    def __init__(self):
        """单例模式"""
        if ChatHub._instance is not None:
            raise RuntimeError("ChatHub is singleton, use get_chat_hub()")

        # 子模块
        self.session_manager: SessionManager = get_session_manager()
        self.link_preview: LinkPreviewService = get_link_preview_service()
        self.status_monitor: StatusMonitor = get_status_monitor()

        # 我的节点信息
        self._my_node_id: str = ""
        self._my_short_id: str = ""
        self._my_name: str = ""
        self._my_avatar: str = ""

        # P2P 连接器 (延迟导入避免循环引用)
        self._p2p_connector = None

        # 去中心化邮箱 (延迟导入)
        self._mailbox = None

        # 通道处理器
        self._channel_handlers: Dict[ChannelType, Callable] = {}

        # UI 回调
        self._ui_callbacks: List[Callable] = []

        # 是否已初始化
        self._initialized = False

    async def _init_async(self):
        """异步初始化"""
        # 启动状态监控
        await self.status_monitor.start()

        # 添加状态监控回调
        self.status_monitor.add_callback(self._on_status_changed)
        self._initialized = True

    def ensure_initialized(self):
        """确保已初始化 (在事件循环中调用)"""
        if not self._initialized:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._init_async())
            except RuntimeError:
                pass  # 没有运行中的事件循环

    @classmethod
    def get_chat_hub(cls) -> 'ChatHub':
        """获取 ChatHub 单例"""
        if cls._instance is None:
            cls._instance = ChatHub()
        return cls._instance

    # ============ 身份设置 ============

    def set_my_identity(self, node_id: str, short_id: str, name: str = "", avatar: str = ""):
        """设置我的身份"""
        self._my_node_id = node_id
        self._my_short_id = short_id
        self._my_name = name or f"User_{short_id[-4:]}"
        self._my_avatar = avatar

    def get_my_id(self) -> str:
        """获取我的节点ID"""
        return self._my_node_id

    def get_my_short_id(self) -> str:
        """获取我的短ID"""
        return self._my_short_id

    def get_my_name(self) -> str:
        """获取我的显示名"""
        return self._my_name

    # ============ UI 回调 ============

    def add_ui_callback(self, callback: Callable):
        """添加 UI 回调"""
        self._ui_callbacks.append(callback)

    def remove_ui_callback(self, callback: Callable):
        """移除 UI 回调"""
        if callback in self._ui_callbacks:
            self._ui_callbacks.remove(callback)

    def _notify_ui(self, event: str, data: Any):
        """通知 UI"""
        for cb in self._ui_callbacks:
            try:
                cb(event, data)
            except Exception as e:
                print(f"[ChatHub] UI callback error: {e}")

    def _on_status_changed(self, status_monitor: StatusMonitor):
        """状态监控回调"""
        self._notify_ui("status_changed", status_monitor.get_status_bar_info())

    # ============ P2P 连接 ============

    def set_p2p_connector(self, connector):
        """设置 P2P 连接器 (延迟注入)"""
        self._p2p_connector = connector

    def set_mailbox(self, mailbox):
        """设置邮箱 (延迟注入)"""
        self._mailbox = mailbox

    # ============ 会话管理 ============

    def get_or_create_session(self, peer_id: str, peer_name: str = "") -> ChatSession:
        """
        获取或创建私聊会话

        Args:
            peer_id: 对端节点ID
            peer_name: 对端显示名

        Returns:
            ChatSession 对象
        """
        session = self.session_manager.get_session_by_peer(peer_id)
        if session:
            return session

        return self.session_manager.create_session(
            session_type=SessionType.PRIVATE,
            peer_id=peer_id,
            name=peer_name or peer_id[:12]
        )

    def get_all_sessions(self) -> List[ChatSession]:
        """获取所有会话"""
        return self.session_manager.get_all_sessions()

    def set_current_session(self, session_id: str):
        """设置当前会话"""
        self.session_manager.set_current_session(session_id)
        self._notify_ui("session_changed", session_id)

    def delete_session(self, session_id: str):
        """删除会话"""
        self.session_manager.delete_session(session_id)

    def pin_session(self, session_id: str, pinned: bool = True):
        """置顶会话"""
        self.session_manager.pin_session(session_id, pinned)

    def mute_session(self, session_id: str, muted: bool = True):
        """免打扰"""
        self.session_manager.mute_session(session_id, muted)

    # ============ 消息发送 ============

    async def send_text_message(self,
                               session_id: str,
                               text: str,
                               reply_to: str = "",
                               reply_preview: str = "") -> UnifiedMessage:
        """
        发送文本消息

        Args:
            session_id: 会话ID
            text: 消息内容
            reply_to: 回复的消息ID
            reply_preview: 回复预览

        Returns:
            UnifiedMessage 对象
        """
        # 创建消息
        message = UnifiedMessage(
            msg_id=str(uuid.uuid4()),
            type=MessageType.TEXT,
            content=text,
            sender_id=self._my_node_id,
            sender_name=self._my_name,
            timestamp=time.time(),
            status=MessageStatus.SENDING,
            reply_to=reply_to if reply_to else None,
            reply_preview=reply_preview
        )

        # 检测链接并获取预览
        urls = self.link_preview.extract_urls(text)
        if urls:
            previews = await self.link_preview.fetch_previews(urls)
            if urls[0] in previews:
                message.preview = previews[urls[0]]
                message.type = MessageType.LINK

        # 保存到会话
        self.session_manager.add_message(message)

        # 模拟发送 (实际走 P2P)
        asyncio.create_task(self._send_via_p2p(message))

        # 更新状态
        message.status = MessageStatus.SENT
        self.session_manager.update_message_status(message.msg_id, MessageStatus.SENT)

        self._notify_ui("message_sent", message)
        return message

    async def send_file_message(self,
                               session_id: str,
                               file_path: str,
                               file_name: str = "",
                               file_size: int = 0,
                               mime_type: str = "") -> UnifiedMessage:
        """
        发送文件消息

        Args:
            session_id: 会话ID
            file_path: 文件路径
            file_name: 文件名
            file_size: 文件大小
            mime_type: MIME类型

        Returns:
            UnifiedMessage 对象
        """
        if not file_name:
            file_name = Path(file_path).name
        if not mime_type:
            mime_type = self._guess_mime_type(file_name)

        # 判断消息类型
        msg_type = MessageType.FILE
        if mime_type.startswith("image/"):
            msg_type = MessageType.IMAGE
        elif mime_type.startswith("video/"):
            msg_type = MessageType.VIDEO
        elif mime_type.startswith("audio/"):
            msg_type = MessageType.VOICE

        message = UnifiedMessage(
            msg_id=str(uuid.uuid4()),
            type=msg_type,
            content=f"[文件] {file_name}",
            sender_id=self._my_node_id,
            sender_name=self._my_name,
            timestamp=time.time(),
            status=MessageStatus.SENDING,
            meta=FileMeta(
                file_id=str(uuid.uuid4()),
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                path=file_path
            )
        )

        self.session_manager.add_message(message)

        # 开始传输监控
        transfer_id = message.meta.file_id
        self.status_monitor.start_transfer(transfer_id, file_name, file_size)

        # 模拟上传
        asyncio.create_task(self._upload_file(message))

        self._notify_ui("message_sent", message)
        return message

    async def send_email_message(self,
                               session_id: str,
                               to: str,
                               subject: str,
                               body: str,
                               attachments: List[str] = None) -> UnifiedMessage:
        """
        通过邮箱通道发送邮件

        Args:
            session_id: 会话ID
            to: 收件人
            subject: 主题
            body: 正文
            attachments: 附件列表

        Returns:
            UnifiedMessage 对象
        """
        message = UnifiedMessage(
            msg_id=str(uuid.uuid4()),
            type=MessageType.SYSTEM,
            content=f"[邮件] 收件人: {to}\n主题: {subject}",
            sender_id=self._my_node_id,
            sender_name=self._my_name,
            timestamp=time.time(),
            status=MessageStatus.SENDING,
            metadata={
                "email_to": to,
                "email_subject": subject,
                "email_body": body,
                "email_attachments": attachments or []
            }
        )

        self.session_manager.add_message(message)

        # 通过邮箱发送
        if self._mailbox:
            asyncio.create_task(self._send_via_email(message))

        self._notify_ui("message_sent", message)
        return message

    # ============ 内部发送方法 ============

    async def _send_via_p2p(self, message: UnifiedMessage):
        """通过 P2P 发送消息"""
        try:
            if self._p2p_connector:
                session = self.session_manager.get_session(message.session_id)
                if session:
                    await self._p2p_connector.send_text(
                        peer_id=session.peer_id,
                        text=str(message.content)
                    )

            # 标记已送达
            message.status = MessageStatus.DELIVERED
            self.session_manager.update_message_status(message.msg_id, MessageStatus.DELIVERED)
        except Exception as e:
            message.status = MessageStatus.FAILED
            self.session_manager.update_message_status(message.msg_id, MessageStatus.FAILED)
            print(f"[ChatHub] Send via P2P failed: {e}")

    async def _upload_file(self, message: UnifiedMessage):
        """上传文件"""
        try:
            meta = message.meta
            if not meta:
                return

            # 模拟分片上传
            chunk_size = 64 * 1024  # 64KB
            total_chunks = (meta.file_size + chunk_size - 1) // chunk_size

            for i in range(total_chunks):
                await asyncio.sleep(0.1)  # 模拟网络延迟
                transferred = min((i + 1) * chunk_size, meta.file_size)
                speed = 1024 * 1024  # 1MB/s
                self.status_monitor.update_transfer(meta.file_id, transferred, speed)

            # 完成
            self.status_monitor.complete_transfer(meta.file_id)

            # 标记消息已发送
            message.status = MessageStatus.SENT
            self.session_manager.update_message_status(message.msg_id, MessageStatus.SENT)
        except Exception as e:
            self.status_monitor.fail_transfer(message.meta.file_id, str(e))
            message.status = MessageStatus.FAILED
            self.session_manager.update_message_status(message.msg_id, MessageStatus.FAILED)

    async def _send_via_email(self, message: UnifiedMessage):
        """通过邮箱发送"""
        try:
            if not self._mailbox:
                return

            metadata = message.metadata
            await self._mailbox.send_email(
                to=metadata.get("email_to"),
                subject=metadata.get("email_subject"),
                body=metadata.get("email_body"),
                attachments=metadata.get("email_attachments", [])
            )

            message.status = MessageStatus.SENT
            self.session_manager.update_message_status(message.msg_id, MessageStatus.SENT)
        except Exception as e:
            message.status = MessageStatus.FAILED
            self.session_manager.update_message_status(message.msg_id, MessageStatus.FAILED)
            print(f"[ChatHub] Send via email failed: {e}")

    # ============ 消息接收 ============

    async def receive_message(self, message: UnifiedMessage):
        """
        接收消息 (由 P2P/邮箱通道调用)

        Args:
            message: UnifiedMessage 对象
        """
        # 保存到会话
        self.session_manager.add_message(message)

        # 自动获取链接预览
        if message.type == MessageType.TEXT and isinstance(message.content, str):
            urls = self.link_preview.extract_urls(message.content)
            if urls:
                preview = await self.link_preview.fetch_preview(urls[0])
                if preview:
                    message.preview = preview
                    message.type = MessageType.LINK

        self._notify_ui("message_received", message)

    # ============ 通话 ============

    async def start_call(self, peer_id: str, call_type: str = "voice") -> CallSession:
        """
        开始通话

        Args:
            peer_id: 对端节点ID
            call_type: voice / video

        Returns:
            CallSession 对象
        """
        call = self.status_monitor.start_call(peer_id, call_type)

        if self._p2p_connector:
            try:
                await self._p2p_connector.start_call(peer_id, call_type)
            except Exception as e:
                print(f"[ChatHub] Start call failed: {e}")

        self._notify_ui("call_started", call)
        return call

    async def end_call(self):
        """结束通话"""
        self.status_monitor.end_call()
        self._notify_ui("call_ended", None)

    # ============ 工具方法 ============

    def _guess_mime_type(self, file_name: str) -> str:
        """猜测 MIME 类型"""
        suffix = Path(file_name).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".zip": "application/zip",
        }
        return mime_map.get(suffix, "application/octet-stream")

    # ============ 状态查询 ============

    def get_status_info(self) -> Dict[str, str]:
        """获取状态栏信息"""
        return self.status_monitor.get_status_bar_info()

    def get_peer_status(self, peer_id: str) -> OnlineStatus:
        """获取对端状态"""
        return self.status_monitor.get_peer_status(peer_id)

    def get_peer_status_icon(self, peer_id: str) -> str:
        """获取对端状态图标"""
        return self.status_monitor.get_peer_status_icon(peer_id)

    def get_connection_quality(self) -> str:
        """获取连接质量"""
        return self.status_monitor.get_connection_quality().value

    def get_connection_quality_icon(self) -> str:
        """获取连接质量图标"""
        return self.status_monitor.get_quality_icon()

    # ============ 搜索 ============

    def search_messages(self, query: str, session_id: str = "") -> List:
        """搜索消息"""
        from .session_manager import SearchScope
        if session_id:
            return self.session_manager.search_messages(query, SearchScope.CURRENT_SESSION, session_id)
        return self.session_manager.search_messages(query, SearchScope.ALL_SESSIONS)

    # ============ 生命周期 ============

    async def close(self):
        """关闭"""
        await self.status_monitor.stop()
        await self.link_preview.close()


# 全局访问函数
_chat_hub: Optional[ChatHub] = None


def get_chat_hub() -> ChatHub:
    """获取 ChatHub 单例"""
    global _chat_hub
    if _chat_hub is None:
        _chat_hub = ChatHub.get_chat_hub()
    return _chat_hub
