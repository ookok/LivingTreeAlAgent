"""
ActionAuditor - 动作审核器

实现"动作审核"流程：
1. 所有写操作（文件创建/修改/删除）需用户确认
2. 添加审核历史记录
3. 支持审核策略配置

参考 Rowboat 的"显式可执行、可审核"设计。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class ActionType(Enum):
    """动作类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    READ = "read"


class AuditStatus(Enum):
    """审核状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class OperationType(Enum):
    """操作类型"""
    FILE_CREATE = "file_create"
    FILE_UPDATE = "file_update"
    FILE_DELETE = "file_delete"
    DATABASE_WRITE = "database_write"
    API_CALL = "api_call"
    TOOL_EXECUTE = "tool_execute"


@dataclass
class AuditRecord:
    """审核记录"""
    record_id: str
    action_type: ActionType
    operation_type: OperationType
    description: str
    details: Dict[str, Any]
    user_id: str
    status: AuditStatus = AuditStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class ActionAuditor:
    """
    动作审核器
    
    实现"动作审核"流程：
    1. 所有写操作需用户确认
    2. 添加审核历史记录
    3. 支持审核策略配置
    
    审核策略：
    - auto_approve_read: 是否自动批准读操作
    - auto_approve_small_files: 是否自动批准小文件操作
    - require_approval_for_delete: 删除操作是否需要批准
    """

    def __init__(self):
        self._logger = logger.bind(component="ActionAuditor")
        self._audit_records: Dict[str, AuditRecord] = {}
        self._pending_queue: List[str] = []
        
        # 审核策略配置
        self._policies = {
            "auto_approve_read": True,
            "auto_approve_small_files": True,
            "small_file_threshold": 1024 * 1024,  # 1MB
            "require_approval_for_delete": True,
            "require_approval_for_write": True
        }

    async def audit_action(
        self,
        action_type: ActionType,
        operation_type: OperationType,
        description: str,
        details: Dict[str, Any],
        user_id: str = "system"
    ) -> AuditRecord:
        """
        审核动作
        
        Args:
            action_type: 动作类型
            operation_type: 操作类型
            description: 动作描述
            details: 动作详情
            user_id: 用户 ID
            
        Returns:
            审核记录
        """
        record_id = f"audit_{len(self._audit_records) + 1}"
        
        record = AuditRecord(
            record_id=record_id,
            action_type=action_type,
            operation_type=operation_type,
            description=description,
            details=details,
            user_id=user_id
        )

        self._audit_records[record_id] = record

        # 根据策略判断是否需要审核
        if await self._should_auto_approve(record):
            record.status = AuditStatus.AUTO_APPROVED
            record.approved_by = "system"
            record.approved_at = datetime.now()
            self._logger.info(f"自动批准动作: {description}")
        else:
            self._pending_queue.append(record_id)
            self._logger.info(f"动作等待审核: {description}")

        return record

    async def _should_auto_approve(self, record: AuditRecord) -> bool:
        """判断是否应该自动批准"""
        # 读操作自动批准
        if self._policies["auto_approve_read"] and record.action_type == ActionType.READ:
            return True

        # 删除操作需要批准
        if self._policies["require_approval_for_delete"] and record.action_type == ActionType.DELETE:
            return False

        # 写操作需要批准（除非是小文件）
        if self._policies["require_approval_for_write"]:
            if record.action_type in [ActionType.CREATE, ActionType.UPDATE]:
                # 检查文件大小
                file_size = record.details.get("file_size", 0)
                if self._policies["auto_approve_small_files"] and file_size < self._policies["small_file_threshold"]:
                    return True
                return False

        return False

    async def approve_action(self, record_id: str, approver_id: str) -> bool:
        """
        批准动作
        
        Args:
            record_id: 审核记录 ID
            approver_id: 审批人 ID
            
        Returns:
            是否批准成功
        """
        record = self._audit_records.get(record_id)
        if not record:
            return False

        if record.status != AuditStatus.PENDING:
            return False

        record.status = AuditStatus.APPROVED
        record.approved_by = approver_id
        record.approved_at = datetime.now()

        # 从等待队列中移除
        if record_id in self._pending_queue:
            self._pending_queue.remove(record_id)

        self._logger.info(f"动作已批准: {record.description}")
        return True

    async def reject_action(self, record_id: str, approver_id: str, reason: str) -> bool:
        """
        拒绝动作
        
        Args:
            record_id: 审核记录 ID
            approver_id: 审批人 ID
            reason: 拒绝原因
            
        Returns:
            是否拒绝成功
        """
        record = self._audit_records.get(record_id)
        if not record:
            return False

        if record.status != AuditStatus.PENDING:
            return False

        record.status = AuditStatus.REJECTED
        record.approved_by = approver_id
        record.approved_at = datetime.now()
        record.details["rejection_reason"] = reason

        # 从等待队列中移除
        if record_id in self._pending_queue:
            self._pending_queue.remove(record_id)

        self._logger.info(f"动作已拒绝: {record.description}, 原因: {reason}")
        return True

    def get_pending_actions(self) -> List[AuditRecord]:
        """获取待审核的动作"""
        return [self._audit_records[id] for id in self._pending_queue]

    def get_record(self, record_id: str) -> Optional[AuditRecord]:
        """获取审核记录"""
        return self._audit_records.get(record_id)

    def get_records_by_user(self, user_id: str) -> List[AuditRecord]:
        """获取用户的审核记录"""
        return [r for r in self._audit_records.values() if r.user_id == user_id]

    def get_records_by_status(self, status: AuditStatus) -> List[AuditRecord]:
        """获取指定状态的审核记录"""
        return [r for r in self._audit_records.values() if r.status == status]

    def set_policy(self, policy_name: str, value: Any):
        """设置审核策略"""
        if policy_name in self._policies:
            self._policies[policy_name] = value
            self._logger.info(f"更新策略: {policy_name} = {value}")

    def get_policy(self, policy_name: str) -> Any:
        """获取审核策略"""
        return self._policies.get(policy_name)

    def get_policies(self) -> Dict[str, Any]:
        """获取所有审核策略"""
        return self._policies.copy()

    def get_stats(self) -> Dict[str, Any]:
        """获取审核器统计信息"""
        status_counts = {}
        for status in AuditStatus:
            status_counts[status.value] = sum(1 for r in self._audit_records.values() if r.status == status)

        action_counts = {}
        for action in ActionType:
            action_counts[action.value] = sum(1 for r in self._audit_records.values() if r.action_type == action)

        return {
            "total_records": len(self._audit_records),
            "pending_count": len(self._pending_queue),
            "status_counts": status_counts,
            "action_counts": action_counts
        }