"""
实时协同编辑系统
Real-time Collaborative Editing System
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import secrets

logger = logging.getLogger(__name__)


class Permission(Enum):
    """协作权限"""
    READ = "read"       # 只读
    COMMENT = "comment" # 评论
    EDIT = "edit"       # 编辑
    MANAGE = "manage"   # 管理
    OWNER = "owner"     # 所有者


@dataclass
class CollabDocument:
    """协同文档"""
    doc_id: str
    title: str
    content: str = ""
    
    # 所有者
    owner_id: str = ""
    
    # 参与者
    participants: Dict[str, Permission] = field(default_factory=dict)
    
    # 版本信息
    version: int = 1
    last_modified: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    # 邀请链接
    invite_link: Optional[str] = None
    invite_permission: Permission = Permission.EDIT
    invite_expires: Optional[datetime] = None
    
    # 状态
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CursorPosition:
    """用户光标位置"""
    user_id: str
    user_name: str
    position: int
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    color: str = "#3498db"
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class EditOperation:
    """编辑操作"""
    op_id: str
    doc_id: str
    user_id: str
    
    # 操作类型: insert, delete, retain
    op_type: str
    position: int
    content: str = ""  # 插入/删除的内容
    length: int = 0    # 保留长度
    
    # 版本
    base_version: int
    applied_version: Optional[int] = None
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)


class CollabEditorHub:
    """
    实时协同编辑中心
    
    功能：
    - 文档创建与管理
    - 邀请与权限控制
    - 操作转换(OT)
    - 多人光标显示
    - P2P同步
    """
    
    def __init__(self, identity, p2p_node):
        self.identity = identity
        self.p2p_node = p2p_node
        
        # 存储
        self._storage_path = Path.home() / ".hermes-desktop" / "collab"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._documents: Dict[str, CollabDocument] = {}
        self._operations: Dict[str, List[EditOperation]] = {}  # doc_id -> operations
        self._cursors: Dict[str, Dict[str, CursorPosition]] = {}  # doc_id -> {user_id -> cursor}
        
        # 回调
        self._doc_callbacks: Dict[str, List[Callable]] = {}
        self._cursor_callbacks: Dict[str, List[Callable]] = {}
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 颜色池
        self._cursor_colors = [
            "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
            "#9b59b6", "#1abc9c", "#e67e22", "#34495e"
        ]
        self._color_index = 0
        
        # 加载文档
        self._load_documents()
        
        logger.info(f"协同编辑中心初始化完成，{len(self._documents)} 个文档")
    
    def _get_doc_path(self, doc_id: str) -> Path:
        """获取文档存储路径"""
        return self._storage_path / f"{doc_id}.json"
    
    def _load_documents(self) -> None:
        """加载文档"""
        for file_path in self._storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                doc = CollabDocument(
                    doc_id=data['doc_id'],
                    title=data['title'],
                    content=data.get('content', ''),
                    owner_id=data['owner_id'],
                    participants=data.get('participants', {}),
                    version=data.get('version', 1),
                    last_modified=datetime.fromisoformat(data['last_modified']),
                    created_at=datetime.fromisoformat(data['created_at']),
                    invite_link=data.get('invite_link'),
                    invite_permission=Permission(data.get('invite_permission', 'edit')),
                    metadata=data.get('metadata', {})
                )
                
                if data.get('invite_expires'):
                    doc.invite_expires = datetime.fromisoformat(data['invite_expires'])
                
                self._documents[doc.doc_id] = doc
                self._operations[doc.doc_id] = []
                
            except Exception as e:
                logger.error(f"加载文档失败 {file_path}: {e}")
    
    def _save_document(self, doc: CollabDocument) -> None:
        """保存文档"""
        file_path = self._get_doc_path(doc.doc_id)
        
        data = {
            'doc_id': doc.doc_id,
            'title': doc.title,
            'content': doc.content,
            'owner_id': doc.owner_id,
            'participants': {k: v.value for k, v in doc.participants.items()},
            'version': doc.version,
            'last_modified': doc.last_modified.isoformat(),
            'created_at': doc.created_at.isoformat(),
            'invite_link': doc.invite_link,
            'invite_permission': doc.invite_permission.value,
            'invite_expires': doc.invite_expires.isoformat() if doc.invite_expires else None,
            'metadata': doc.metadata
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_next_color(self) -> str:
        """获取下一个光标颜色"""
        color = self._cursor_colors[self._color_index % len(self._cursor_colors)]
        self._color_index += 1
        return color
    
    async def start(self) -> None:
        """启动协同编辑中心"""
        # 启动P2P同步
        if self.p2p_node:
            self.p2p_node.add_message_handler('collab', self._handle_collab_message)
        
        logger.info("协同编辑中心已启动")
    
    async def stop(self) -> None:
        """停止协同编辑中心"""
        # 保存所有文档
        for doc in self._documents.values():
            self._save_document(doc)
        
        logger.info("协同编辑中心已停止")
    
    async def create_document(self, owner_id: str, title: str,
                             initial_content: str = "") -> Optional[str]:
        """
        创建协同文档
        
        Args:
            owner_id: 所有者ID
            title: 标题
            initial_content: 初始内容
        
        Returns:
            str: 文档ID
        """
        async with self._lock:
            doc_id = secrets.token_urlsafe(16)
            
            doc = CollabDocument(
                doc_id=doc_id,
                title=title,
                content=initial_content,
                owner_id=owner_id,
                participants={owner_id: Permission.OWNER}
            )
            
            self._documents[doc_id] = doc
            self._operations[doc_id] = []
            self._cursors[doc_id] = {}
            
            self._save_document(doc)
            
            logger.info(f"创建协同文档: {title} ({doc_id})")
            return doc_id
    
    async def open_document(self, doc_id: str, user_id: str) -> Optional[CollabDocument]:
        """
        打开文档
        
        Args:
            doc_id: 文档ID
            user_id: 用户ID
        
        Returns:
            CollabDocument: 文档对象
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        
        # 检查权限
        permission = doc.participants.get(user_id)
        if not permission:
            # 尝试通过邀请链接加入
            return None
        
        # 初始化光标追踪
        if doc_id not in self._cursors:
            self._cursors[doc_id] = {}
        
        # 注册光标
        user_name = self.identity.get_identity_by_username(user_id)
        self._cursors[doc_id][user_id] = CursorPosition(
            user_id=user_id,
            user_name=user_name.username if user_name else user_id,
            position=0,
            color=self._get_next_color()
        )
        
        return doc
    
    async def close_document(self, doc_id: str, user_id: str) -> None:
        """关闭文档"""
        if doc_id in self._cursors and user_id in self._cursors[doc_id]:
            del self._cursors[doc_id][user_id]
    
    async def apply_operation(self, doc_id: str, user_id: str,
                             op_type: str, position: int,
                             content: str = "", length: int = 0) -> bool:
        """
        应用编辑操作
        
        Args:
            doc_id: 文档ID
            user_id: 用户ID
            op_type: 操作类型
            position: 位置
            content: 内容
            length: 长度
        
        Returns:
            bool: 是否成功
        """
        async with self._lock:
            doc = self._documents.get(doc_id)
            if not doc:
                return False
            
            # 检查权限
            permission = doc.participants.get(user_id)
            if not permission or permission == Permission.READ:
                return False
            
            # 创建操作
            op = EditOperation(
                op_id=secrets.token_urlsafe(16),
                doc_id=doc_id,
                user_id=user_id,
                op_type=op_type,
                position=position,
                content=content,
                length=length,
                base_version=doc.version
            )
            
            # 应用操作到文档
            success = await self._apply_op(doc, op)
            
            if success:
                self._operations[doc_id].append(op)
                doc.version += 1
                doc.last_modified = datetime.now()
                self._save_document(doc)
                
                # 广播操作到其他参与者
                if self.p2p_node:
                    await self._broadcast_operation(doc, op)
                
                # 触发回调
                await self._trigger_callbacks(doc_id, 'update', {
                    'type': 'operation',
                    'operation': op
                })
            
            return success
    
    async def _apply_op(self, doc: CollabDocument, op: EditOperation) -> bool:
        """应用操作到文档"""
        try:
            if op.op_type == 'insert':
                doc.content = doc.content[:op.position] + op.content + doc.content[op.position:]
            
            elif op.op_type == 'delete':
                doc.content = doc.content[:op.position] + doc.content[op.position + op.length:]
            
            elif op.op_type == 'retain':
                # 保留操作，不改变内容
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"应用操作失败: {e}")
            return False
    
    async def _broadcast_operation(self, doc: CollabDocument, 
                                   op: EditOperation) -> None:
        """广播操作到其他参与者"""
        if not self.p2p_node:
            return
        
        message = {
            'type': 'collab_operation',
            'doc_id': doc.doc_id,
            'operation': {
                'op_id': op.op_id,
                'user_id': op.user_id,
                'op_type': op.op_type,
                'position': op.position,
                'content': op.content,
                'length': op.length,
                'version': doc.version
            }
        }
        
        for participant_id in doc.participants.keys():
            if participant_id != op.user_id:
                try:
                    await self.p2p_node.send_message(participant_id, message)
                except Exception as e:
                    logger.error(f"广播操作失败: {e}")
    
    async def update_cursor(self, doc_id: str, user_id: str,
                           position: int, selection_start: Optional[int] = None,
                           selection_end: Optional[int] = None) -> bool:
        """
        更新光标位置
        
        Args:
            doc_id: 文档ID
            user_id: 用户ID
            position: 光标位置
            selection_start: 选区起始
            selection_end: 选区结束
        
        Returns:
            bool: 是否成功
        """
        if doc_id not in self._cursors:
            return False
        
        cursor = self._cursors[doc_id].get(user_id)
        if not cursor:
            return False
        
        cursor.position = position
        cursor.selection_start = selection_start
        cursor.selection_end = selection_end
        cursor.last_update = datetime.now()
        
        # 广播光标更新
        if self.p2p_node:
            await self._broadcast_cursor(doc_id, cursor)
        
        return True
    
    async def _broadcast_cursor(self, doc_id: str, cursor: CursorPosition) -> None:
        """广播光标更新"""
        if not self.p2p_node:
            return
        
        doc = self._documents.get(doc_id)
        if not doc:
            return
        
        message = {
            'type': 'cursor_update',
            'doc_id': doc_id,
            'cursor': {
                'user_id': cursor.user_id,
                'user_name': cursor.user_name,
                'position': cursor.position,
                'selection_start': cursor.selection_start,
                'selection_end': cursor.selection_end,
                'color': cursor.color
            }
        }
        
        for participant_id in doc.participants.keys():
            if participant_id != cursor.user_id:
                try:
                    await self.p2p_node.send_message(participant_id, message)
                except:
                    pass
    
    async def _handle_collab_message(self, sender: str, message: Dict) -> None:
        """处理协作消息"""
        msg_type = message.get('type')
        
        if msg_type == 'collab_operation':
            await self._handle_remote_operation(message['doc_id'], message['operation'])
        
        elif msg_type == 'cursor_update':
            self._handle_remote_cursor(message['doc_id'], message['cursor'])
    
    async def _handle_remote_operation(self, doc_id: str, op_data: Dict) -> None:
        """处理远程操作"""
        doc = self._documents.get(doc_id)
        if not doc:
            return
        
        op = EditOperation(
            op_id=op_data['op_id'],
            doc_id=doc_id,
            user_id=op_data['user_id'],
            op_type=op_data['op_type'],
            position=op_data['position'],
            content=op_data.get('content', ''),
            length=op_data.get('length', 0),
            base_version=op_data['version'],
            applied_version=doc.version
        )
        
        await self._apply_op(doc, op)
        doc.version += 1
        self._operations[doc_id].append(op)
        
        await self._trigger_callbacks(doc_id, 'update', {
            'type': 'operation',
            'operation': op
        })
    
    def _handle_remote_cursor(self, doc_id: str, cursor_data: Dict) -> None:
        """处理远程光标"""
        if doc_id not in self._cursors:
            self._cursors[doc_id] = {}
        
        cursor = CursorPosition(
            user_id=cursor_data['user_id'],
            user_name=cursor_data['user_name'],
            position=cursor_data['position'],
            selection_start=cursor_data.get('selection_start'),
            selection_end=cursor_data.get('selection_end'),
            color=cursor_data.get('color', '#3498db')
        )
        
        self._cursors[doc_id][cursor_data['user_id']] = cursor
        
        asyncio.create_task(self._trigger_callbacks(doc_id, 'cursor', cursor))
    
    def create_invite_link(self, doc_id: str, owner_id: str,
                          permission: str = "edit",
                          expires_hours: int = 24) -> Optional[str]:
        """
        创建邀请链接
        
        Args:
            doc_id: 文档ID
            owner_id: 所有者ID
            permission: 权限
            expires_hours: 过期时间（小时）
        
        Returns:
            str: 邀请链接
        """
        doc = self._documents.get(doc_id)
        if not doc or doc.owner_id != owner_id:
            return None
        
        # 生成邀请码
        invite_code = secrets.token_urlsafe(16)
        doc.invite_link = f"hermes://collab/{doc_id}?invite={invite_code}"
        doc.invite_permission = Permission(permission)
        doc.invite_expires = datetime.now().timestamp() + (expires_hours * 3600)
        
        self._save_document(doc)
        
        return doc.invite_link
    
    async def join_via_invite(self, doc_id: str, invite_code: str,
                             user_id: str) -> bool:
        """
        通过邀请加入
        
        Args:
            doc_id: 文档ID
            invite_code: 邀请码
            user_id: 用户ID
        
        Returns:
            bool: 是否成功
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return False
        
        # 验证邀请链接
        if not doc.invite_link or not doc.invite_link.endswith(f"invite={invite_code}"):
            return False
        
        # 检查过期
        if doc.invite_expires and datetime.now() > doc.invite_expires:
            return False
        
        # 添加参与者
        doc.participants[user_id] = doc.invite_permission
        
        self._save_document(doc)
        
        logger.info(f"用户 {user_id} 通过邀请加入文档 {doc_id}")
        return True
    
    def get_document(self, doc_id: str) -> Optional[CollabDocument]:
        """获取文档"""
        return self._documents.get(doc_id)
    
    def list_documents(self, user_id: str) -> List[CollabDocument]:
        """列出用户可访问的文档"""
        result = []
        for doc in self._documents.values():
            if user_id in doc.participants and not doc.is_deleted:
                result.append(doc)
        return sorted(result, key=lambda d: d.last_modified, reverse=True)
    
    def get_cursors(self, doc_id: str) -> List[CursorPosition]:
        """获取文档的光标列表"""
        if doc_id not in self._cursors:
            return []
        return list(self._cursors[doc_id].values())
    
    def add_callback(self, doc_id: str, event_type: str,
                    callback: Callable) -> None:
        """添加回调"""
        key = f"{doc_id}:{event_type}"
        if key not in self._doc_callbacks:
            self._doc_callbacks[key] = []
        self._doc_callbacks[key].append(callback)
    
    async def _trigger_callbacks(self, doc_id: str, event_type: str,
                                data: Any) -> None:
        """触发回调"""
        key = f"{doc_id}:{event_type}"
        for callback in self._doc_callbacks.get(key, []):
            try:
                await callback(data)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
