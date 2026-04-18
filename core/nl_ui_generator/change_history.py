"""
Change History - 变更历史管理
==============================

记录所有UI变更，支持撤销/重做和版本回溯。

功能:
- 记录每次变更的完整快照
- 支持撤销/重做栈
- 版本对比和回溯
- 批量变更合并
"""

import uuid
import json
import time
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import copy


class ChangeType(Enum):
    """变更类型"""
    ADD_COMPONENT = "add_component"       # 添加组件
    REMOVE_COMPONENT = "remove_component"  # 移除组件
    MODIFY_COMPONENT = "modify_component"  # 修改组件
    MOVE_COMPONENT = "move_component"     # 移动组件
    RESIZE_COMPONENT = "resize_component"  # 调整大小
    CHANGE_STYLE = "change_style"         # 改变样式
    BIND_ACTION = "bind_action"           # 绑定动作
    CREATE_TEMPLATE = "create_template"    # 创建模板
    DELETE_TEMPLATE = "delete_template"    # 删除模板
    BATCH = "batch"                       # 批量变更


@dataclass
class ChangeRecord:
    """变更记录"""
    id: str
    change_type: ChangeType
    template_id: str

    # 变更详情
    target_id: str = ""           # 目标组件ID
    property_name: str = ""       # 属性名
    old_value: Any = None         # 旧值
    new_value: Any = None         # 新值

    # 状态
    timestamp: float = 0
    user_id: str = "system"
    description: str = ""         # 变更描述

    # 撤销数据
    undo_data: dict = None        # 用于撤销的完整数据

    # 批量变更
    child_changes: list = field(default_factory=list)  # 子变更列表

    def __post_init__(self):
        if isinstance(self.change_type, str):
            self.change_type = ChangeType(self.change_type)
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()
        if self.undo_data is None:
            self.undo_data = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "change_type": self.change_type.value if isinstance(self.change_type, ChangeType) else self.change_type,
            "template_id": self.template_id,
            "target_id": self.target_id,
            "property_name": self.property_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "description": self.description,
            "undo_data": self.undo_data,
            "child_changes": [c.to_dict() if isinstance(c, ChangeRecord) else c for c in self.child_changes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeRecord":
        child_changes = []
        for c in data.get("child_changes", []):
            if isinstance(c, dict):
                child_changes.append(cls.from_dict(c))

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            change_type=ChangeType(data.get("change_type", "add_component")),
            template_id=data.get("template_id", ""),
            target_id=data.get("target_id", ""),
            property_name=data.get("property_name", ""),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            timestamp=data.get("timestamp", time.time()),
            user_id=data.get("user_id", "system"),
            description=data.get("description", ""),
            undo_data=data.get("undo_data", {}),
            child_changes=child_changes,
        )


class UndoStack:
    """撤销栈"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.stack: deque = deque(maxlen=max_size)

    def push(self, record: ChangeRecord):
        """压入栈"""
        self.stack.append(record)

    def pop(self) -> Optional[ChangeRecord]:
        """弹出栈"""
        if self.stack:
            return self.stack.pop()
        return None

    def peek(self) -> Optional[ChangeRecord]:
        """查看栈顶"""
        if self.stack:
            return self.stack[-1]
        return None

    def is_empty(self) -> bool:
        """是否为空"""
        return len(self.stack) == 0

    def clear(self):
        """清空栈"""
        self.stack.clear()

    def __len__(self) -> int:
        return len(self.stack)


class ChangeHistory:
    """变更历史管理器"""

    def __init__(self, max_undo_steps: int = 100):
        self.max_undo_steps = max_undo_steps

        # 撤销/重做栈
        self.undo_stack = UndoStack(max_size=max_undo_steps)
        self.redo_stack = UndoStack(max_size=max_undo_steps)

        # 按用户的变更历史
        self.user_histories: dict[str, list[ChangeRecord]] = defaultdict(list)

        # 模板版本历史
        self.template_versions: dict[str, dict[str, ChangeRecord]] = defaultdict(dict)

        # 观察者
        self.observers: list[Callable] = []

        # 批量变更缓冲
        self._batch_buffer: list[ChangeRecord] = []
        self._is_batching = False

    def record_change(
        self,
        change_type: ChangeType,
        template_id: str,
        target_id: str = "",
        property_name: str = "",
        old_value: Any = None,
        new_value: Any = None,
        user_id: str = "system",
        description: str = "",
        undo_data: dict = None,
    ) -> ChangeRecord:
        """
        记录变更

        Args:
            change_type: 变更类型
            template_id: 模板ID
            target_id: 目标组件ID
            property_name: 属性名
            old_value: 旧值
            new_value: 新值
            user_id: 用户ID
            description: 变更描述
            undo_data: 撤销数据

        Returns:
            ChangeRecord: 变更记录
        """
        # 如果正在批量模式，添加到缓冲区
        if self._is_batching:
            record = ChangeRecord(
                change_type=change_type,
                template_id=template_id,
                target_id=target_id,
                property_name=property_name,
                old_value=old_value,
                new_value=new_value,
                user_id=user_id,
                description=description,
                undo_data=undo_data,
            )
            self._batch_buffer.append(record)
            return record

        # 创建变更记录
        record = ChangeRecord(
            change_type=change_type,
            template_id=template_id,
            target_id=target_id,
            property_name=property_name,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
            description=description,
            undo_data=undo_data or {
                "target_id": target_id,
                "property_name": property_name,
                "old_value": old_value,
            },
        )

        # 压入撤销栈
        self.undo_stack.push(record)

        # 清空重做栈（新变更后重做历史失效）
        self.redo_stack.clear()

        # 记录到用户历史
        self.user_histories[user_id].append(record)

        # 通知观察者
        self._notify_observers(record)

        return record

    def start_batch(self):
        """开始批量变更"""
        self._is_batching = True
        self._batch_buffer.clear()

    def end_batch(self, template_id: str, user_id: str = "system", description: str = "批量变更") -> Optional[ChangeRecord]:
        """
        结束批量变更

        Args:
            template_id: 模板ID
            user_id: 用户ID
            description: 批量描述

        Returns:
            批量变更记录
        """
        if not self._is_batching:
            return None

        self._is_batching = False

        if not self._batch_buffer:
            return None

        # 创建批量变更记录
        batch_record = ChangeRecord(
            change_type=ChangeType.BATCH,
            template_id=template_id,
            user_id=user_id,
            description=description,
            child_changes=self._batch_buffer.copy(),
            undo_data={
                "changes": [c.to_dict() for c in self._batch_buffer],
            },
        )

        # 压入撤销栈
        self.undo_stack.push(batch_record)

        # 清空重做栈
        self.redo_stack.clear()

        # 清空缓冲区
        self._batch_buffer.clear()

        # 记录到用户历史
        self.user_histories[user_id].append(batch_record)

        # 通知观察者
        self._notify_observers(batch_record)

        return batch_record

    def undo(self) -> Optional[ChangeRecord]:
        """
        撤销上一次变更

        Returns:
            被撤销的变更记录
        """
        record = self.undo_stack.pop()
        if not record:
            return None

        # 压入重做栈
        self.redo_stack.push(record)

        # 执行撤销
        self._execute_undo(record)

        # 通知观察者
        self._notify_observers(record, is_undo=True)

        return record

    def redo(self) -> Optional[ChangeRecord]:
        """
        重做上一次撤销

        Returns:
            被重做的变更记录
        """
        record = self.redo_stack.pop()
        if not record:
            return None

        # 压入撤销栈
        self.undo_stack.push(record)

        # 执行重做
        self._execute_redo(record)

        # 通知观察者
        self._notify_observers(record, is_redo=True)

        return record

    def _execute_undo(self, record: ChangeRecord):
        """执行撤销操作"""
        if record.change_type == ChangeType.BATCH:
            # 批量撤销（反向执行子变更）
            for child in reversed(record.child_changes):
                self._apply_reverse_change(child)
        else:
            self._apply_reverse_change(record)

    def _execute_redo(self, record: ChangeRecord):
        """执行重做操作"""
        if record.change_type == ChangeType.BATCH:
            # 批量重做
            for child in record.child_changes:
                self._apply_change(child)
        else:
            self._apply_change(record)

    def _apply_reverse_change(self, record: ChangeRecord):
        """应用反向变更"""
        undo_data = record.undo_data
        if not undo_data:
            return

        # 根据变更类型应用反向变更
        if record.change_type == ChangeType.ADD_COMPONENT:
            # 撤销添加 = 删除
            self._publish_change_event("remove", record.template_id, record.target_id)
        elif record.change_type == ChangeType.REMOVE_COMPONENT:
            # 撤销删除 = 添加（使用undo_data中的完整数据）
            self._publish_change_event("add", record.template_id, undo_data.get("old_value"))
        elif record.change_type == ChangeType.MODIFY_COMPONENT:
            # 撤销修改 = 恢复旧值
            self._publish_change_event(
                "modify",
                record.template_id,
                record.target_id,
                record.property_name,
                undo_data.get("old_value")
            )

    def _apply_change(self, record: ChangeRecord):
        """应用变更"""
        if record.change_type == ChangeType.BATCH:
            for child in record.child_changes:
                self._apply_change(child)
        else:
            self._publish_change_event(
                record.change_type.value,
                record.template_id,
                record.target_id,
                record.property_name,
                record.new_value
            )

    def _publish_change_event(self, action: str, template_id: str, target_id: str, property_name: str = "", value: Any = None):
        """发布变更事件（供外部处理）"""
        # 实际应用中，这里会调用模板引擎或UI更新
        pass

    def can_undo(self) -> bool:
        """是否可以撤销"""
        return not self.undo_stack.is_empty()

    def can_redo(self) -> bool:
        """是否可以重做"""
        return not self.redo_stack.is_empty()

    def get_history(self, user_id: str = None, limit: int = 50) -> list[ChangeRecord]:
        """
        获取变更历史

        Args:
            user_id: 用户ID，None表示所有用户
            limit: 返回数量限制

        Returns:
            变更记录列表
        """
        if user_id:
            history = self.user_histories.get(user_id, [])
        else:
            # 合并所有用户历史
            all_histories = []
            for h in self.user_histories.values():
                all_histories.extend(h)
            history = sorted(all_histories, key=lambda x: x.timestamp, reverse=True)

        return history[:limit]

    def get_undo_description(self) -> str:
        """获取撤销操作的描述"""
        record = self.undo_stack.peek()
        if record:
            return f"撤销: {record.description or record.change_type.value}"
        return "无可撤销"

    def get_redo_description(self) -> str:
        """获取重做操作的描述"""
        record = self.redo_stack.peek()
        if record:
            return f"重做: {record.description or record.change_type.value}"
        return "无，可重做"

    def register_observer(self, callback: Callable):
        """注册观察者"""
        self.observers.append(callback)

    def unregister_observer(self, callback: Callable):
        """注销观察者"""
        if callback in self.observers:
            self.observers.remove(callback)

    def _notify_observers(self, record: ChangeRecord, is_undo: bool = False, is_redo: bool = False):
        """通知观察者"""
        for observer in self.observers:
            try:
                observer(record, is_undo=is_undo, is_redo=is_redo)
            except Exception:
                pass


# 全局单例
_history_instance: Optional[ChangeHistory] = None


def get_change_history() -> ChangeHistory:
    """获取变更历史管理器单例"""
    global _history_instance
    if _history_instance is None:
        _history_instance = ChangeHistory()
    return _history_instance