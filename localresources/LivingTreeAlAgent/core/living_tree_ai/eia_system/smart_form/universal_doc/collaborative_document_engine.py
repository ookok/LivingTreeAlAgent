"""
文档协作引擎

支持多人实时在线编辑的文档协作系统。
"""

import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from enum import Enum
from datetime import datetime
import copy


# ==================== 数据模型 ====================

class OperationType(Enum):
    """操作类型"""
    INSERT = "insert"
    DELETE = "delete"
    UPDATE = "update"
    MOVE = "move"
    FORMAT = "format"


class ConflictResolution(Enum):
    """冲突解决策略"""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    MANUAL = "manual"


@dataclass
class Collaborator:
    """协作者"""
    id: str
    name: str
    avatar: str = ""
    color: str = "#667eea"  # 协作光标颜色
    cursor_position: Dict[str, Any] = field(default_factory=dict)
    last_active: datetime = field(default_factory=datetime.now)
    permissions: List[str] = field(default_factory=lambda: ["edit"])


@dataclass
class DocumentOperation:
    """文档操作"""
    id: str
    collaborator_id: str
    operation_type: OperationType
    field_id: str
    section_id: str
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 0


@dataclass
class CollaborativeDocument:
    """协作文档"""
    doc_id: str
    project_id: str
    template_type: str
    content: Dict[str, Any]  # field_id -> value
    version: int = 0
    collaborators: Dict[str, Collaborator] = field(default_factory=dict)
    operations: List[DocumentOperation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ==================== 协作引擎 ====================

class CollaborativeDocumentEngine:
    """
    协作文档引擎

    支持多人实时在线编辑的文档协作系统。
    """

    def __init__(self, p2p_network=None):
        """
        Args:
            p2p_network: P2P网络实例
        """
        self.p2p_network = p2p_network
        self._use_mock = p2p_network is None

        # 本地文档缓存
        self._documents: Dict[str, CollaborativeDocument] = {}

        # WebSocket连接管理
        self._connections: Dict[str, List[Any]] = {}

        # 冲突解决策略
        self.conflict_resolution = ConflictResolution.LAST_WRITE_WINS

        # 操作处理器
        self._operation_handlers: Dict[OperationType, Callable] = {}

    async def create_document(
        self,
        project_id: str,
        template_type: str,
        initial_content: Dict[str, Any] = None
    ) -> str:
        """
        创建协作文档

        Args:
            project_id: 项目ID
            template_type: 模板类型
            initial_content: 初始内容

        Returns:
            str: 文档ID
        """
        doc_id = self._generate_doc_id(project_id, template_type)

        doc = CollaborativeDocument(
            doc_id=doc_id,
            project_id=project_id,
            template_type=template_type,
            content=initial_content or {}
        )

        self._documents[doc_id] = doc

        # 广播创建事件
        await self._broadcast_event(doc_id, {
            "type": "document_created",
            "doc_id": doc_id,
            "template_type": template_type
        })

        return doc_id

    async def join_document(
        self,
        doc_id: str,
        collaborator: Collaborator
    ) -> bool:
        """
        加入文档协作

        Args:
            doc_id: 文档ID
            collaborator: 协作者

        Returns:
            bool: 是否成功
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        doc.collaborators[collaborator.id] = collaborator

        # 广播加入事件
        await self._broadcast_event(doc_id, {
            "type": "collaborator_joined",
            "collaborator_id": "collaborator.id",
            "collaborator_name": collaborator.name,
            "cursor_color": collaborator.color
        })

        return True

    async def leave_document(
        self,
        doc_id: str,
        collaborator_id: str
    ):
        """
        离开文档协作

        Args:
            doc_id: 文档ID
            collaborator_id: 协作者ID
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return

        collaborator = doc.collaborators.pop(collaborator_id, None)

        if collaborator:
            # 广播离开事件
            await self._broadcast_event(doc_id, {
                "type": "collaborator_left",
                "collaborator_id": collaborator_id,
                "collaborator_name": collaborator.name
            })

    async def apply_operation(
        self,
        doc_id: str,
        operation: DocumentOperation
    ) -> Dict[str, Any]:
        """
        应用文档操作

        Args:
            doc_id: 文档ID
            operation: 操作

        Returns:
            Dict: 操作结果
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return {"success": False, "error": "文档不存在"}

        # 版本检查
        if operation.version < doc.version:
            # 存在冲突，需要解决
            conflict_result = await self._resolve_conflict(doc, operation)
            if not conflict_result["resolved"]:
                return {
                    "success": False,
                    "conflict": True,
                    "message": "操作冲突需要手动解决",
                    "conflicting_operation": conflict_result.get("conflicting_op")
                }

        # 应用操作
        result = await self._apply_operation_to_doc(doc, operation)

        if result["success"]:
            doc.version += 1
            doc.updated_at = datetime.now()
            doc.operations.append(operation)

            # 广播操作
            await self._broadcast_event(doc_id, {
                "type": "operation_applied",
                "operation": {
                    "id": operation.id,
                    "field_id": operation.field_id,
                    "new_value": operation.new_value,
                    "collaborator_id": operation.collaborator_id,
                    "version": doc.version
                }
            })

        return result

    async def _apply_operation_to_doc(
        self,
        doc: CollaborativeDocument,
        operation: DocumentOperation
    ) -> Dict[str, Any]:
        """将操作应用到文档"""
        field_path = operation.field_id

        if operation.operation_type == OperationType.UPDATE:
            doc.content[field_path] = operation.new_value
            return {"success": True, "field_id": field_path, "new_value": operation.new_value}

        elif operation.operation_type == OperationType.DELETE:
            if field_path in doc.content:
                del doc.content[field_path]
            return {"success": True, "field_id": field_path}

        elif operation.operation_type == OperationType.INSERT:
            doc.content[field_path] = operation.new_value
            return {"success": True, "field_id": field_path, "new_value": operation.new_value}

        return {"success": False, "error": "未知操作类型"}

    async def _resolve_conflict(
        self,
        doc: CollaborativeDocument,
        operation: DocumentOperation
    ) -> Dict[str, Any]:
        """解决操作冲突"""
        if self.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
            # 直接应用新操作，覆盖旧值
            return {"resolved": True}

        elif self.conflict_resolution == ConflictResolution.MERGE:
            # 尝试合并
            current_value = doc.content.get(operation.field_id)
            # 简单的合并策略：使用新值
            return {"resolved": True}

        elif self.conflict_resolution == ConflictResolution.MANUAL:
            # 返回冲突信息，等待手动解决
            return {
                "resolved": False,
                "conflicting_op": {
                    "field_id": operation.field_id,
                    "current_value": doc.content.get(operation.field_id),
                    "conflicting_value": operation.new_value
                }
            }

        return {"resolved": False}

    async def update_cursor_position(
        self,
        doc_id: str,
        collaborator_id: str,
        position: Dict[str, Any]
    ):
        """
        更新协作者光标位置

        Args:
            doc_id: 文档ID
            collaborator_id: 协作者ID
            position: 位置信息 {section_id, field_id, offset}
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return

        collaborator = doc.collaborators.get(collaborator_id)
        if collaborator:
            collaborator.cursor_position = position
            collaborator.last_active = datetime.now()

            # 广播光标更新
            await self._broadcast_event(doc_id, {
                "type": "cursor_updated",
                "collaborator_id": collaborator_id,
                "color": collaborator.color,
                "position": position
            })

    async def get_document_state(self, doc_id: str) -> Optional[Dict]:
        """
        获取文档状态

        Args:
            doc_id: 文档ID

        Returns:
            Optional[Dict]: 文档状态
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return None

        return {
            "doc_id": doc.doc_id,
            "project_id": doc.project_id,
            "template_type": doc.template_type,
            "content": doc.content,
            "version": doc.version,
            "collaborators": [
                {
                    "id": c.id,
                    "name": c.name,
                    "color": c.color,
                    "cursor_position": c.cursor_position,
                    "last_active": c.last_active.isoformat()
                }
                for c in doc.collaborators.values()
            ],
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat()
        }

    async def get_document_history(
        self,
        doc_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取文档操作历史

        Args:
            doc_id: 文档ID
            limit: 返回数量限制

        Returns:
            List[Dict]: 操作历史
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return []

        operations = doc.operations[-limit:]

        return [
            {
                "id": op.id,
                "collaborator_id": op.collaborator_id,
                "operation_type": op.operation_type.value,
                "field_id": op.field_id,
                "old_value": op.old_value,
                "new_value": op.new_value,
                "timestamp": op.timestamp.isoformat(),
                "version": op.version
            }
            for op in operations
        ]

    async def _broadcast_event(self, doc_id: str, event: Dict):
        """广播事件到所有连接的客户端"""
        connections = self._connections.get(doc_id, [])
        for ws in connections:
            try:
                await ws.send(json.dumps(event))
            except Exception:
                pass

    def register_connection(self, doc_id: str, websocket):
        """注册WebSocket连接"""
        if doc_id not in self._connections:
            self._connections[doc_id] = []
        self._connections[doc_id].append(websocket)

    def unregister_connection(self, doc_id: str, websocket):
        """取消注册WebSocket连接"""
        if doc_id in self._connections:
            try:
                self._connections[doc_id].remove(websocket)
            except ValueError:
                pass

    def _generate_doc_id(self, project_id: str, template_type: str) -> str:
        """生成文档ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{project_id}_{template_type}_{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ==================== 操作工厂 ====================

def create_operation(
    collaborator_id: str,
    operation_type: OperationType,
    field_id: str,
    section_id: str = "",
    old_value: Any = None,
    new_value: Any = None
) -> DocumentOperation:
    """创建文档操作的工厂函数"""
    return DocumentOperation(
        id=hashlib.md5(f"{collaborator_id}_{field_id}_{datetime.now().timestamp()}".encode()).hexdigest()[:12],
        collaborator_id=collaborator_id,
        operation_type=operation_type,
        field_id=field_id,
        section_id=section_id,
        old_value=old_value,
        new_value=new_value
    )


# ==================== 导出 ====================

_engine_instance: Optional[CollaborativeDocumentEngine] = None


def get_collaborative_engine(p2p_network=None) -> CollaborativeDocumentEngine:
    """获取协作引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CollaborativeDocumentEngine(p2p_network)
    return _engine_instance
