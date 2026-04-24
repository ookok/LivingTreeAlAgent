"""
协同编辑器模块
提供实时协同编辑、光标共享、邀请链接等功能
"""
import asyncio
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
import string
from core.logger import get_logger
logger = get_logger('smart_ide_game.collab_editor')



class OperationType(Enum):
    """操作类型"""
    INSERT = "insert"
    DELETE = "delete"
    RETAIN = "retain"
    FORMAT = "format"


@dataclass
class Operation:
    """编辑操作"""
    type: OperationType
    position: int
    length: int = 0
    content: str = ""
    format: Optional[Dict[str, Any]] = None
    user_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    revision: int = 0


@dataclass
class Cursor:
    """用户光标"""
    user_id: str
    username: str
    position: int
    line: int
    column: int
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    color: str = ""
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class Participant:
    """参与者"""
    user_id: str
    username: str
    avatar: Optional[str] = None
    role: str = "editor"  # editor, viewer, admin
    joined_at: datetime = field(default_factory=datetime.now)
    is_online: bool = True
    cursor: Optional[Cursor] = None


@dataclass
class DocumentState:
    """文档状态"""
    content: str
    version: int
    last_modified: datetime = field(default_factory=datetime.now)
    operations: List[Operation] = field(default_factory=list)


class OperationTransformer:
    """操作转换器 (OT算法)"""

    @staticmethod
    def transform(op1: Operation, op2: Operation) -> Operation:
        """转换操作以解决冲突"""
        if op1.type == OperationType.INSERT and op2.type == OperationType.INSERT:
            # 两个插入操作
            if op1.position <= op2.position:
                return Operation(
                    type=op1.type,
                    position=op1.position + len(op2.content),
                    content=op1.content,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )
            else:
                return op1

        elif op1.type == OperationType.DELETE and op2.type == OperationType.DELETE:
            # 两个删除操作
            op1_end = op1.position + op1.length
            op2_end = op2.position + op2.length

            if op1_end <= op2.position:
                # op1 在 op2 之前
                return op1
            elif op1.position >= op2_end:
                # op1 在 op2 之后
                return Operation(
                    type=op1.type,
                    position=op1.position - op2.length,
                    length=op1.length,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )
            else:
                # 重叠
                overlap_start = max(op1.position, op2.position)
                overlap_end = min(op1_end, op2_end)
                new_length = op1.length - (overlap_end - overlap_start)

                return Operation(
                    type=op1.type,
                    position=min(op1.position, op2.position),
                    length=max(new_length, 0),
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )

        elif op1.type == OperationType.INSERT and op2.type == OperationType.DELETE:
            # op1 插入，op2 删除
            if op1.position <= op2.position:
                return Operation(
                    type=op1.type,
                    position=op1.position,
                    content=op1.content,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )
            elif op1.position >= op2.position + op2.length:
                return Operation(
                    type=op1.type,
                    position=op1.position - op2.length,
                    content=op1.content,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )
            else:
                return op1

        elif op1.type == OperationType.DELETE and op2.type == OperationType.INSERT:
            # op1 删除，op2 插入
            if op1.position >= op2.position:
                return Operation(
                    type=op1.type,
                    position=op1.position + len(op2.content),
                    length=op1.length,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )
            else:
                return op1

        return op1

    @staticmethod
    def apply(operation: Operation, content: str) -> str:
        """应用操作到内容"""
        if operation.type == OperationType.INSERT:
            return content[:operation.position] + operation.content + content[operation.position:]

        elif operation.type == OperationType.DELETE:
            return content[:operation.position] + content[operation.position + operation.length:]

        elif operation.type == OperationType.RETAIN:
            return content

        return content

    @staticmethod
    def compose(op1: Operation, op2: Operation) -> Operation:
        """组合两个连续操作"""
        if op1.type == OperationType.INSERT and op2.type == OperationType.INSERT:
            if op1.position + len(op1.content) == op2.position:
                return Operation(
                    type=OperationType.INSERT,
                    position=op1.position,
                    content=op1.content + op2.content,
                    user_id=op1.user_id,
                    revision=max(op1.revision, op2.revision) + 1
                )

        return op2


class CRDTEngine:
    """CRDT引擎 (用于离线协同)"""

    def __init__(self):
        self.vector_clock: Dict[str, int] = {}
        self.pending_ops: List[Operation] = []

    def generate_id(self) -> str:
        """生成唯一ID (LWW-Register)"""
        timestamp = datetime.now().timestamp()
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return f"{timestamp:.6f}-{random_part}"

    def update_vector_clock(self, user_id: str):
        """更新向量时钟"""
        self.vector_clock[user_id] = self.vector_clock.get(user_id, 0) + 1

    def compare_clock(self, other: Dict[str, int]) -> int:
        """比较向量时钟"""
        for user_id in set(self.vector_clock.keys()) | set(other.keys()):
            self_val = self.vector_clock.get(user_id, 0)
            other_val = other.get(user_id, 0)
            if self_val < other_val:
                return -1
            elif self_val > other_val:
                return 1
        return 0

    def merge(self, local_content: str, remote_content: str, local_ops: List[Operation], remote_ops: List[Operation]) -> str:
        """合并内容 (简化版LWW)"""
        # 使用时间戳决定保留哪个版本
        # 实际实现应该使用更复杂的CRDT算法
        if len(remote_ops) > len(local_ops):
            return remote_content
        return local_content


class InviteManager:
    """邀请管理器"""

    def __init__(self):
        self.invites: Dict[str, Dict[str, Any]] = {}

    def create_invite(
        self,
        document_id: str,
        created_by: str,
        role: str = "editor",
        expires_in_hours: int = 24,
        max_uses: int = None
    ) -> str:
        """创建邀请"""
        invite_code = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        self.invites[invite_code] = {
            "document_id": document_id,
            "created_by": created_by,
            "role": role,
            "expires_at": datetime.now().timestamp() + expires_in_hours * 3600,
            "max_uses": max_uses,
            "use_count": 0,
            "created_at": datetime.now()
        }

        return invite_code

    def validate_invite(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """验证邀请"""
        invite = self.invites.get(invite_code)
        if not invite:
            return None

        # 检查过期
        if datetime.now().timestamp() > invite["expires_at"]:
            return None

        # 检查使用次数
        if invite["max_uses"] and invite["use_count"] >= invite["max_uses"]:
            return None

        return invite

    def use_invite(self, invite_code: str) -> bool:
        """使用邀请"""
        invite = self.invites.get(invite_code)
        if invite:
            invite["use_count"] += 1
            return True
        return False

    def revoke_invite(self, invite_code: str) -> bool:
        """撤销邀请"""
        if invite_code in self.invites:
            del self.invites[invite_code]
            return True
        return False


class CollabDocument:
    """协作文档"""

    def __init__(self, document_id: str, title: str = "", initial_content: str = ""):
        self.id = document_id
        self.title = title
        self.content = initial_content
        self.state = DocumentState(
            content=initial_content,
            version=0
        )
        self.participants: Dict[str, Participant] = {}
        self.cursors: Dict[str, Cursor] = {}
        self.operation_log: List[Operation] = []
        self.created_at = datetime.now()
        self.created_by: Optional[str] = None
        self.is_locked: bool = False
        self.locked_by: Optional[str] = None
        self.share_settings: Dict[str, Any] = {
            "public_read": False,
            "public_write": False,
            "invite_required": True
        }
        self.tags: List[str] = []
        self.language: str = "plaintext"

    def add_participant(self, user_id: str, username: str, role: str = "editor") -> Participant:
        """添加参与者"""
        participant = Participant(
            user_id=user_id,
            username=username,
            role=role
        )
        self.participants[user_id] = participant
        return participant

    def remove_participant(self, user_id: str) -> bool:
        """移除参与者"""
        if user_id in self.participants:
            del self.participants[user_id]
            if user_id in self.cursors:
                del self.cursors[user_id]
            return True
        return False

    def update_cursor(self, cursor: Cursor):
        """更新光标"""
        self.cursors[cursor.user_id] = cursor
        if cursor.user_id in self.participants:
            self.participants[cursor.user_id].cursor = cursor
            self.participants[cursor.user_id].is_online = True

    def apply_operation(self, operation: Operation) -> str:
        """应用操作"""
        # 转换操作以解决冲突
        transformed_op = operation
        for pending_op in self.state.operations:
            if pending_op.revision > operation.revision:
                transformed_op = OperationTransformer.transform(transformed_op, pending_op)

        # 应用操作
        new_content = OperationTransformer.apply(transformed_op, self.content)
        
        # 更新状态
        self.content = new_content
        self.state.content = new_content
        self.state.version += 1
        self.state.last_modified = datetime.now()
        operation.revision = self.state.version
        self.state.operations.append(operation)
        self.operation_log.append(operation)

        # 保留最近的100个操作
        if len(self.state.operations) > 100:
            self.state.operations = self.state.operations[-100:]

        return new_content

    def get_snapshot(self) -> Dict[str, Any]:
        """获取快照"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "version": self.state.version,
            "last_modified": self.state.last_modified.isoformat(),
            "participant_count": len(self.participants),
            "online_count": sum(1 for p in self.participants.values() if p.is_online)
        }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史"""
        recent_ops = self.operation_log[-limit:]
        return [
            {
                "type": op.type.value,
                "position": op.position,
                "length": op.length,
                "content": op.content[:50] + "..." if len(op.content) > 50 else op.content,
                "user_id": op.user_id,
                "timestamp": op.timestamp.isoformat(),
                "revision": op.revision
            }
            for op in recent_ops
        ]


class CollabEditor:
    """协同编辑器核心"""

    def __init__(self):
        self.documents: Dict[str, CollabDocument] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> document_id
        self.operation_handlers: Dict[str, Callable] = {}
        self.event_listeners: Dict[str, List[Callable]] = {}
        self.invite_manager = InviteManager()
        self.crdt_engine = CRDTEngine()
        self._running = False

    async def start(self):
        """启动编辑器"""
        self._running = True

    async def stop(self):
        """停止编辑器"""
        self._running = False

    def create_document(
        self,
        title: str = "",
        content: str = "",
        created_by: str = None,
        language: str = "plaintext"
    ) -> CollabDocument:
        """创建文档"""
        doc_id = str(uuid.uuid4())[:8]
        document = CollabDocument(doc_id, title, content)
        document.created_by = created_by
        document.language = language
        self.documents[doc_id] = document
        return document

    def get_document(self, document_id: str) -> Optional[CollabDocument]:
        """获取文档"""
        return self.documents.get(document_id)

    def join_document(
        self,
        document_id: str,
        user_id: str,
        username: str,
        role: str = "editor"
    ) -> Optional[CollabDocument]:
        """加入文档"""
        document = self.documents.get(document_id)
        if not document:
            return None

        # 检查锁定
        if document.is_locked and document.locked_by != user_id:
            return None

        # 添加参与者
        document.add_participant(user_id, username, role)
        self.user_sessions[user_id] = document_id

        return document

    def leave_document(self, user_id: str) -> bool:
        """离开文档"""
        document_id = self.user_sessions.get(user_id)
        if not document_id:
            return False

        document = self.documents.get(document_id)
        if document:
            document.remove_participant(user_id)
            # 标记为离线
            if user_id in document.participants:
                document.participants[user_id].is_online = False

        del self.user_sessions[user_id]
        return True

    def apply_operation(
        self,
        document_id: str,
        operation: Operation
    ) -> Optional[str]:
        """应用操作"""
        document = self.documents.get(document_id)
        if not document:
            return None

        new_content = document.apply_operation(operation)
        
        # 广播事件
        self._emit_event("operation", {
            "document_id": document_id,
            "operation": {
                "type": operation.type.value,
                "position": operation.position,
                "content": operation.content,
                "user_id": operation.user_id
            },
            "new_version": document.state.version
        })

        return new_content

    def update_cursor(
        self,
        document_id: str,
        user_id: str,
        position: int,
        line: int,
        column: int,
        selection_start: Optional[int] = None,
        selection_end: Optional[int] = None
    ) -> bool:
        """更新光标"""
        document = self.documents.get(document_id)
        if not document:
            return False

        # 获取用户颜色
        color = self._get_user_color(user_id)

        cursor = Cursor(
            user_id=user_id,
            username=document.participants.get(user_id, Participant(user_id, "Unknown")).username,
            position=position,
            line=line,
            column=column,
            selection_start=selection_start,
            selection_end=selection_end,
            color=color
        )

        document.update_cursor(cursor)

        # 广播光标更新
        self._emit_event("cursor_update", {
            "document_id": document_id,
            "cursor": {
                "user_id": cursor.user_id,
                "username": cursor.username,
                "position": cursor.position,
                "line": cursor.line,
                "column": cursor.column,
                "color": cursor.color
            }
        })

        return True

    def _get_user_color(self, user_id: str) -> str:
        """获取用户颜色"""
        colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
            "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
            "#BB8FCE", "#85C1E9", "#F8B500", "#00CED1"
        ]
        hash_val = sum(ord(c) for c in user_id)
        return colors[hash_val % len(colors)]

    def create_invite_link(
        self,
        document_id: str,
        created_by: str,
        role: str = "editor",
        expires_in_hours: int = 24
    ) -> Optional[str]:
        """创建邀请链接"""
        document = self.documents.get(document_id)
        if not document:
            return None

        invite_code = self.invite_manager.create_invite(
            document_id, created_by, role, expires_in_hours
        )

        return f"collab://{document_id}/join/{invite_code}"

    def join_by_invite(
        self,
        invite_code: str,
        user_id: str,
        username: str
    ) -> Optional[CollabDocument]:
        """通过邀请加入"""
        invite = self.invite_manager.validate_invite(invite_code)
        if not invite:
            return None

        document = self.join_document(
            invite["document_id"],
            user_id,
            username,
            invite["role"]
        )

        if document:
            self.invite_manager.use_invite(invite_code)

        return document

    def lock_document(self, document_id: str, user_id: str) -> bool:
        """锁定文档"""
        document = self.documents.get(document_id)
        if not document or document.is_locked:
            return False

        document.is_locked = True
        document.locked_by = user_id
        return True

    def unlock_document(self, document_id: str, user_id: str) -> bool:
        """解锁文档"""
        document = self.documents.get(document_id)
        if not document or document.locked_by != user_id:
            return False

        document.is_locked = False
        document.locked_by = None
        return True

    def get_document_snapshot(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档快照"""
        document = self.documents.get(document_id)
        if not document:
            return None
        return document.get_snapshot()

    def get_document_history(self, document_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取文档历史"""
        document = self.documents.get(document_id)
        if not document:
            return []
        return document.get_history(limit)

    def add_event_listener(self, event: str, callback: Callable):
        """添加事件监听"""
        if event not in self.event_listeners:
            self.event_listeners[event] = []
        self.event_listeners[event].append(callback)

    def remove_event_listener(self, event: str, callback: Callable):
        """移除事件监听"""
        if event in self.event_listeners:
            self.event_listeners[event].remove(callback)

    def _emit_event(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        if event in self.event_listeners:
            for callback in self.event_listeners[event]:
                try:
                    callback(event, data)
                except Exception as e:
                    logger.info(f"Event handler error: {e}")

    def get_editor_stats(self) -> Dict[str, Any]:
        """获取编辑器统计"""
        total_docs = len(self.documents)
        total_participants = sum(len(d.participants) for d in self.documents.values())
        online_participants = sum(
            sum(1 for p in d.participants.values() if p.is_online)
            for d in self.documents.values()
        )

        return {
            "total_documents": total_docs,
            "total_participants": total_participants,
            "online_participants": online_participants,
            "active_invites": len(self.invite_manager.invites)
        }


# 便捷函数
def create_collab_document(
    title: str = "",
    content: str = "",
    language: str = "plaintext"
) -> CollabDocument:
    """创建协作文档"""
    doc_id = str(uuid.uuid4())[:8]
    return CollabDocument(doc_id, title, content)
