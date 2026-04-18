# =================================================================
# 事件日志层 - Event Logger (Event Sourcing)
# =================================================================
# 功能：
# 1. 记录所有溯源实体的操作事件
# 2. 支持事件重放还原历史状态
# 3. 事件查询和过滤
# 4. 事件归档和导出
# =================================================================

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import threading


class EventType(Enum):
    """事件类型"""
    # 节点生命周期
    CREATED = "CREATED"           # 创建
    UPDATED = "UPDATED"           # 更新
    DELETED = "DELETED"          # 删除
    RESTORED = "RESTORED"        # 恢复

    # 关系
    LINKED = "LINKED"           # 关联
    UNLINKED = "UNLINKED"       # 取消关联
    MERGED = "MERGED"           # 合并
    SPLIT = "SPLIT"             # 拆分

    # 版本
    VERSION_CREATED = "VERSION_CREATED"    # 新版本创建
    VERSION_SUPERSEDED = "VERSION_SUPERSEDED"  # 版本被替代

    # 溯源
    SOURCE_ADDED = "SOURCE_ADDED"        # 添加来源
    PROVENANCE_TRACED = "PROVENANCE_TRACED"  # 溯源追踪

    # 应用
    APPLIED = "APPLIED"           # 应用到（作为输入）
    OUTPUT = "OUTPUT"            # 输出（作为结果）
    DERIVED = "DERIVED"          # 派生自

    # 权限
    SHARED = "SHARED"           # 分享
    EXPORTED = "EXPORTED"       # 导出
    IMPORTED = "IMPORTED"       # 导入

    # 标签
    TAGGED = "TAGGED"           # 打标签
    UNTAGGED = "UNTAGGED"       # 移除标签


class EntityType(Enum):
    """实体类型"""
    KNOWLEDGE_NODE = "KnowledgeNode"    # 知识节点
    PRODUCT_NODE = "ProductNode"        # 商品节点
    SERVICE_NODE = "ServiceNode"         # 服务节点
    DOCUMENT_NODE = "DocumentNode"       # 文档节点
    ASSEMBLY_RECIPE = "AssemblyRecipe" # 装配配方
    CHUNK = "Chunk"                    # 内容块
    FILE = "File"                      # 文件


@dataclass
class ProvenanceEvent:
    """
    溯源事件

    事件溯源的核心数据结构
    """
    # 事件标识
    event_id: str
    event_type: EventType

    # 实体信息
    entity_type: EntityType
    entity_id: str
    entity_name: str = ""

    # 操作者
    operator: str = "system"          # user:xxx / agent:xxx / system
    operator_type: str = "system"      # user / agent / system

    # 时间戳
    timestamp: float = field(default_factory=time.time)
    timestamp_str: str = ""           # ISO 格式时间字符串

    # 事件数据
    event_data: Dict[str, Any] = field(default_factory=dict)
    # 包含: 旧值、新值、变更字段列表等

    # 快照哈希
    snapshot_hash: str = ""           # 事件发生时的状态哈希

    # 溯源信息
    sources: List[Dict[str, str]] = field(default_factory=list)
    # [{entity_id, entity_type, relation}]

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1                  # 事件版本号

    def __post_init__(self):
        if not self.timestamp_str:
            self.timestamp_str = datetime.fromtimestamp(self.timestamp).isoformat()

    @property
    def is_critical(self) -> bool:
        """是否是关键事件"""
        return self.event_type in [
            EventType.CREATED,
            EventType.DELETED,
            EventType.MERGED,
            EventType.VERSION_SUPERSEDED,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["entity_type"] = self.entity_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProvenanceEvent':
        """从字典创建"""
        data["event_type"] = EventType(data["event_type"])
        data["entity_type"] = EntityType(data["entity_type"])
        return cls(**data)


class EventLogger:
    """
    事件日志器

    核心功能：
    1. 记录事件到日志
    2. 查询和过滤事件
    3. 重放事件重建状态
    4. 事件归档和导出
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = str(Path.home() / ".hermes-desktop" / "provenance" / "events")

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 内存索引（用于快速查询）
        self._events: List[ProvenanceEvent] = []
        self._entity_index: Dict[str, List[int]] = {}  # entity_id -> event indices
        self._type_index: Dict[str, List[int]] = {}     # entity_type -> event indices

        # 锁（线程安全）
        self._lock = threading.Lock()

        # 加载已有事件
        self._load_events()

    def _load_events(self):
        """加载已有事件"""
        event_file = self.storage_path / "events.jsonl"
        if event_file.exists():
            try:
                with open(event_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            event = ProvenanceEvent.from_dict(data)
                            self._add_to_index(event)
            except Exception as e:
                print(f"[EventLogger] Failed to load events: {e}")

    def _save_event(self, event: ProvenanceEvent):
        """保存事件到磁盘"""
        event_file = self.storage_path / "events.jsonl"
        try:
            with open(event_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[EventLogger] Failed to save event: {e}")

    def _add_to_index(self, event: ProvenanceEvent):
        """添加到索引"""
        self._events.append(event)

        # 实体索引
        if event.entity_id not in self._entity_index:
            self._entity_index[event.entity_id] = []
        self._entity_index[event.entity_id].append(len(self._events) - 1)

        # 类型索引
        type_key = f"{event.entity_type.value}:{event.event_type.value}"
        if type_key not in self._type_index:
            self._type_index[type_key] = []
        self._type_index[type_key].append(len(self._events) - 1)

    # ========== 记录事件 ==========

    def log_event(
        self,
        event_type: EventType,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str = "",
        operator: str = "system",
        event_data: Dict[str, Any] = None,
        snapshot_hash: str = "",
        sources: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None
    ) -> ProvenanceEvent:
        """
        记录事件

        Args:
            event_type: 事件类型
            entity_type: 实体类型
            entity_id: 实体ID
            entity_name: 实体名称
            operator: 操作者
            event_data: 事件数据
            snapshot_hash: 快照哈希
            sources: 来源信息
            metadata: 元数据

        Returns:
            创建的事件
        """
        event = ProvenanceEvent(
            event_id=str(uuid.uuid4())[:12],
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            operator=operator,
            operator_type=self._detect_operator_type(operator),
            event_data=event_data or {},
            snapshot_hash=snapshot_hash,
            sources=sources or [],
            metadata=metadata or {}
        )

        with self._lock:
            self._events.append(event)
            self._add_to_index(event)
            self._save_event(event)

        return event

    def _detect_operator_type(self, operator: str) -> str:
        """检测操作者类型"""
        if operator.startswith("user:"):
            return "user"
        elif operator.startswith("agent:"):
            return "agent"
        return "system"

    # ========== 便捷方法 ==========

    def log_created(
        self,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str = "",
        operator: str = "system",
        initial_data: Dict[str, Any] = None,
        snapshot_hash: str = ""
    ) -> ProvenanceEvent:
        """记录创建事件"""
        return self.log_event(
            EventType.CREATED,
            entity_type,
            entity_id,
            entity_name,
            operator,
            event_data={"initial": initial_data or {}},
            snapshot_hash=snapshot_hash
        )

    def log_updated(
        self,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str = "",
        operator: str = "system",
        old_data: Dict[str, Any] = None,
        new_data: Dict[str, Any] = None,
        changed_fields: List[str] = None,
        snapshot_hash: str = ""
    ) -> ProvenanceEvent:
        """记录更新事件"""
        return self.log_event(
            EventType.UPDATED,
            entity_type,
            entity_id,
            entity_name,
            operator,
            event_data={
                "old": old_data or {},
                "new": new_data or {},
                "changed_fields": changed_fields or []
            },
            snapshot_hash=snapshot_hash
        )

    def log_deleted(
        self,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str = "",
        operator: str = "system",
        final_data: Dict[str, Any] = None,
        snapshot_hash: str = ""
    ) -> ProvenanceEvent:
        """记录删除事件"""
        return self.log_event(
            EventType.DELETED,
            entity_type,
            entity_id,
            entity_name,
            operator,
            event_data={"final": final_data or {}},
            snapshot_hash=snapshot_hash
        )

    def log_linked(
        self,
        source_entity_id: str,
        source_type: EntityType,
        target_entity_id: str,
        target_type: EntityType,
        relation: str,
        operator: str = "system",
        metadata: Dict[str, Any] = None
    ) -> ProvenanceEvent:
        """记录关联事件"""
        return self.log_event(
            EventType.LINKED,
            source_type,
            source_entity_id,
            operator=operator,
            event_data={
                "relation": relation,
                "target_id": target_entity_id,
                "target_type": target_type.value
            },
            sources=[{
                "entity_id": target_entity_id,
                "entity_type": target_type.value,
                "relation": relation
            }],
            metadata=metadata
        )

    def log_applied(
        self,
        recipe_id: str,
        input_entity_ids: List[str],
        output_entity_id: str,
        operator: str = "system",
        metadata: Dict[str, Any] = None
    ) -> ProvenanceEvent:
        """记录应用事件（装配园产出）"""
        return self.log_event(
            EventType.APPLIED,
            EntityType.ASSEMBLY_RECIPE,
            recipe_id,
            operator=operator,
            event_data={
                "input_entities": input_entity_ids,
                "output_entity_id": output_entity_id
            },
            sources=[{"entity_id": eid, "entity_type": "input"} for eid in input_entity_ids],
            metadata=metadata
        )

    # ========== 查询 ==========

    def get_entity_events(
        self,
        entity_id: str,
        event_types: List[EventType] = None,
        limit: int = 100
    ) -> List[ProvenanceEvent]:
        """
        获取实体的所有事件

        Args:
            entity_id: 实体ID
            event_types: 事件类型过滤
            limit: 返回数量限制

        Returns:
            事件列表（按时间倒序）
        """
        indices = self._entity_index.get(entity_id, [])

        events = []
        for idx in reversed(indices[-limit:]):
            event = self._events[idx]
            if event_types is None or event.event_type in event_types:
                events.append(event)

        return events

    def get_events_by_type(
        self,
        entity_type: EntityType,
        event_type: EventType = None,
        limit: int = 100
    ) -> List[ProvenanceEvent]:
        """按类型获取事件"""
        if event_type:
            type_key = f"{entity_type.value}:{event_type.value}"
            indices = self._type_index.get(type_key, [])
        else:
            # 获取该实体类型的所有事件
            type_key_prefix = entity_type.value + ":"
            all_indices = []
            for key, indices in self._type_index.items():
                if key.startswith(type_key_prefix):
                    all_indices.extend(indices)
            indices = sorted(set(all_indices))[-limit:]

        return [self._events[idx] for idx in reversed(indices)]

    def get_events_by_operator(
        self,
        operator: str,
        limit: int = 100
    ) -> List[ProvenanceEvent]:
        """按操作者获取事件"""
        events = [e for e in self._events if e.operator == operator]
        return events[-limit:][::-1]

    def get_events_in_range(
        self,
        start_time: float,
        end_time: float,
        entity_type: EntityType = None
    ) -> List[ProvenanceEvent]:
        """按时间范围获取事件"""
        events = [
            e for e in self._events
            if start_time <= e.timestamp <= end_time
            and (entity_type is None or e.entity_type == entity_type)
        ]
        return events

    def get_latest_events(self, limit: int = 50) -> List[ProvenanceEvent]:
        """获取最新事件"""
        return self._events[-limit:][::-1]

    # ========== 事件重放 ==========

    def replay_to_state(
        self,
        entity_id: str,
        target_timestamp: float
    ) -> Dict[str, Any]:
        """
        重放到指定时间点的状态

        Args:
            entity_id: 实体ID
            target_timestamp: 目标时间戳

        Returns:
            重放后的状态快照
        """
        events = self.get_entity_events(entity_id)

        # 按时间排序（正序）
        events = [e for e in events if e.timestamp <= target_timestamp]
        events.sort(key=lambda x: x.timestamp)

        # 逐步重放
        current_state = {}
        for event in events:
            if event.event_type == EventType.CREATED:
                current_state = event.event_data.get("initial", {})
            elif event.event_type == EventType.UPDATED:
                current_state.update(event.event_data.get("new", {}))
            elif event.event_type == EventType.DELETED:
                current_state = {}

        return current_state

    def replay_full_history(
        self,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取实体的完整历史快照

        Returns:
            每个版本的快照列表
        """
        events = self.get_entity_events(entity_id)

        snapshots = []
        current_state = {}

        for event in events:
            if event.event_type == EventType.CREATED:
                current_state = event.event_data.get("initial", {}).copy()
                snapshots.append({
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "state": current_state.copy()
                })
            elif event.event_type == EventType.UPDATED:
                current_state.update(event.event_data.get("new", {}))
                snapshots.append({
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "state": current_state.copy()
                })
            elif event.event_type == EventType.DELETED:
                snapshots.append({
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "state": None
                })

        return snapshots

    # ========== 统计 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_events = len(self._events)

        by_type: Dict[str, int] = {}
        by_operator: Dict[str, int] = {}

        for event in self._events:
            type_key = event.event_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            by_operator[event.operator] = by_operator.get(event.operator, 0) + 1

        return {
            "total_events": total_events,
            "unique_entities": len(self._entity_index),
            "events_by_type": by_type,
            "events_by_operator": by_operator,
            "first_event": self._events[0].timestamp_str if self._events else None,
            "last_event": self._events[-1].timestamp_str if self._events else None,
        }

    # ========== 归档和导出 ==========

    def archive_old_events(self, days: int = 90) -> int:
        """
        归档旧事件

        将指定天数之前的事件移动到归档文件
        """
        cutoff = time.time() - days * 24 * 3600

        archived = 0
        remaining = []

        for event in self._events:
            if event.timestamp < cutoff and not event.is_critical:
                # 归档
                archive_file = self.storage_path / f"archive_{int(cutoff)}.jsonl"
                with open(archive_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                archived += 1
            else:
                remaining.append(event)

        self._events = remaining
        return archived

    def export_events(
        self,
        entity_ids: List[str] = None,
        event_types: List[EventType] = None,
        filepath: str = None
    ) -> str:
        """
        导出事件

        Args:
            entity_ids: 实体ID列表（None 表示所有）
            event_types: 事件类型列表（None 表示所有）
            filepath: 导出文件路径

        Returns:
            导出文件路径
        """
        if filepath is None:
            filepath = str(self.storage_path / f"export_{int(time.time())}.json")

        events_to_export = self._events

        if entity_ids:
            events_to_export = [
                e for e in events_to_export if e.entity_id in entity_ids
            ]

        if event_types:
            events_to_export = [
                e for e in events_to_export if e.event_type in event_types
            ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in events_to_export],
                f,
                ensure_ascii=False,
                indent=2
            )

        return filepath

    def close(self):
        """关闭日志器"""
        # 暂时无需操作（使用 append 模式）
        pass
