"""
专家复核工作流 (Expert Review Workflow)

核心功能：
1. AI生成初稿 → 初级顾问核对数据 → 高级专家审核逻辑 → 系统记录审核痕迹
2. 保留人工把关环节，符合咨询行业资质要求
3. 多级审批链，确保质量

工作流：
1. 自检 → 2. 同级互审 → 3. 专家审核 → 4. 项目经理审批 → 5. 质量经理抽检
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
import hashlib
import json


class ReviewLevel(Enum):
    """审核级别"""
    SELF_CHECK = "self_check"                 # 自检
    PEER_REVIEW = "peer_review"               # 同级互审
    EXPERT_REVIEW = "expert_review"            # 专家审核
    PROJECT_MANAGER = "project_manager"       # 项目经理审批
    QUALITY_MANAGER = "quality_manager"       # 质量经理抽检


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"                       # 待审核
    IN_PROGRESS = "in_progress"               # 审核中
    APPROVED = "approved"                     # 通过
    REJECTED = "rejected"                     # 拒绝
    REVISION_REQUESTED = "revision_requested"  # 要求修改
    SKIPPED = "skipped"                       # 跳过


class ApprovalStatus(Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"                   # 弃权


@dataclass
class ReviewComment:
    """审核意见"""
    comment_id: str
    task_id: str

    # 审核人
    reviewer_id: str
    reviewer_name: str
    reviewer_role: str

    # 审核级别
    review_level: ReviewLevel

    # 意见内容
    content: str                               # 意见正文
    suggestion: Optional[str] = None           # 修改建议

    # 指出的问题
    issues: List[Dict[str, Any]] = field(default_factory=list)
    # 格式: [{"field": "章节1", "issue": "数据错误", "severity": "high", "position": "第3段"}]

    # 位置信息（用于前端定位）
    section_name: Optional[str] = None
    paragraph_number: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    # 附件
    attachments: List[Dict[str, str]] = field(default_factory=list)
    # 格式: [{"name": "截图.png", "path": "/path/to/file", "type": "image"}]

    # 状态
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "task_id": self.task_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_name": self.reviewer_name,
            "reviewer_role": self.reviewer_role,
            "review_level": self.review_level.value,
            "content": self.content,
            "suggestion": self.suggestion,
            "issues_count": len(self.issues),
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ReviewTask:
    """审核任务"""
    task_id: str
    document_id: str
    document_name: str
    project_id: str

    # 审核级别
    review_level: ReviewLevel
    required_level: ReviewLevel                # 需要达到的级别

    # 状态
    status: ReviewStatus = ReviewStatus.PENDING

    # 审核人
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_at: Optional[datetime] = None

    # 审核记录
    comments: List[ReviewComment] = field(default_factory=list)
    review_history: List[Dict[str, Any]] = field(default_factory=list)

    # 审核结论
    decision: Optional[str] = None             # approved/rejected/revision
    decision_reason: Optional[str] = None

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 截止时间
    due_at: Optional[datetime] None
    is_overdue: bool = False

    # SLA
    sla_hours: int = 24                        # SLA时长（小时）

    # 元数据
    priority: str = "normal"                   # urgent/high/normal/low
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "project_id": self.project_id,
            "review_level": self.review_level.value,
            "required_level": self.required_level.value,
            "status": self.status.value,
            "assigned_to": self.assigned_to_name,
            "decision": self.decision,
            "comments_count": len(self.comments),
            "is_overdue": self.is_overdue,
            "created_at": self.created_at.isoformat(),
            "due_at": self.due_at.isoformat() if self.due_at else None,
        }

    def get_unresolved_comments(self) -> List[ReviewComment]:
        """获取未处理的意见"""
        return [c for c in self.comments if not c.is_resolved]

    def check_overdue(self) -> bool:
        """检查是否超时"""
        if self.due_at and datetime.now() > self.due_at and self.status == ReviewStatus.PENDING:
            self.is_overdue = True
            return True
        return False


@dataclass
class ApprovalChain:
    """审批链"""
    chain_id: str
    document_id: str
    project_id: str

    # 审批级别
    levels: List[ReviewLevel] = field(default_factory=list)

    # 当前级别
    current_level_index: int = 0
    current_level: ReviewLevel = ReviewLevel.SELF_CHECK

    # 审批任务
    tasks: List[ReviewTask] = field(default_factory=list)

    # 总体状态
    is_completed: bool = False
    is_approved: bool = False
    failed_level: Optional[ReviewLevel] = None

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # 配置
    skip_self_check_if_ai: bool = True         # AI生成的文档可跳过自检
    skip_peer_review_for_small_project: bool = True  # 小项目跳过同级审核

    def get_current_task(self) -> Optional[ReviewTask]:
        """获取当前待审核任务"""
        for task in self.tasks:
            if task.status == ReviewStatus.PENDING or task.status == ReviewStatus.IN_PROGRESS:
                return task
        return None

    def get_next_level(self) -> Optional[ReviewLevel]:
        """获取下一审核级别"""
        if self.current_level_index + 1 < len(self.levels):
            return self.levels[self.current_level_index + 1]
        return None

    def is_all_approved(self) -> bool:
        """是否全部通过"""
        return all(t.status == ReviewStatus.APPROVED for t in self.tasks)


class ExpertReviewWorkflow:
    """
    专家复核工作流

    工作流程：
    1. 提交审核 → 2. 自检 → 3. 同级互审 → 4. 专家审核 → 5. 项目经理审批 → 6. 质量经理抽检

    特点：
    1. 可配置审批链
    2. 自动分配审核人
    3. 意见追踪和解决
    4. 审核时效提醒
    5. 审核历史记录
    """

    # 默认审批链配置
    DEFAULT_CHAIN_CONFIG = {
        "standard": [  # 标准审批链
            ReviewLevel.SELF_CHECK,
            ReviewLevel.PEER_REVIEW,
            ReviewLevel.EXPERT_REVIEW,
            ReviewLevel.PROJECT_MANAGER,
        ],
        "simple": [  # 简化审批链（小项目）
            ReviewLevel.SELF_CHECK,
            ReviewLevel.EXPERT_REVIEW,
            ReviewLevel.PROJECT_MANAGER,
        ],
        "strict": [  # 严格审批链（重大项目）
            ReviewLevel.SELF_CHECK,
            ReviewLevel.PEER_REVIEW,
            ReviewLevel.EXPERT_REVIEW,
            ReviewLevel.PROJECT_MANAGER,
            ReviewLevel.QUALITY_MANAGER,
        ],
        "ai_generated": [  # AI生成文档
            ReviewLevel.EXPERT_REVIEW,
            ReviewLevel.PROJECT_MANAGER,
        ],
    }

    # SLA配置（小时）
    SLA_CONFIG = {
        ReviewLevel.SELF_CHECK: 4,
        ReviewLevel.PEER_REVIEW: 24,
        ReviewLevel.EXPERT_REVIEW: 48,
        ReviewLevel.PROJECT_MANAGER: 24,
        ReviewLevel.QUALITY_MANAGER: 72,
    }

    def __init__(self):
        # 审批链存储
        self._chains: Dict[str, ApprovalChain] = {}
        self._tasks: Dict[str, ReviewTask] = {}

        # 用户映射（角色 -> 用户）
        self._reviewer_pool: Dict[ReviewLevel, List[str]] = {}

        # 回调函数
        self._callbacks: Dict[str, Callable] = {}

        # 统计
        self._statistics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "avg_review_time": 0,
            "overdue_rate": 0.0,
        }

    async def create_chain(
        self,
        document_id: str,
        document_name: str,
        project_id: str,
        chain_type: str = "standard",
        is_ai_generated: bool = False,
        project_scale: str = "medium",
        **kwargs
    ) -> ApprovalChain:
        """
        创建审批链

        Args:
            document_id: 文档ID
            document_name: 文档名称
            project_id: 项目ID
            chain_type: 审批链类型（standard/simple/strict/ai_generated）
            is_ai_generated: 是否AI生成
            project_scale: 项目规模（large/medium/small）

        Returns:
            ApprovalChain: 审批链
        """
        # 确定审批级别
        if is_ai_generated and chain_type == "standard":
            levels = self.DEFAULT_CHAIN_CONFIG["ai_generated"]
        elif project_scale == "small":
            levels = self.DEFAULT_CHAIN_CONFIG["simple"]
        elif project_scale == "large":
            levels = self.DEFAULT_CHAIN_CONFIG["strict"]
        else:
            levels = self.DEFAULT_CHAIN_CONFIG["standard"]

        # 创建审批链
        chain = ApprovalChain(
            chain_id=f"CHAIN:{hashlib.md5(f'{document_id}{datetime.now().isoformat()}'.encode()).hexdigest()[:12].upper()}",
            document_id=document_id,
            project_id=project_id,
            levels=levels,
            current_level_index=0,
            current_level=levels[0] if levels else ReviewLevel.SELF_CHECK,
        )

        # 创建审核任务
        for level in levels:
            task = ReviewTask(
                task_id=f"TASK:{chain.chain_id}:{level.value.upper()}",
                document_id=document_id,
                document_name=document_name,
                project_id=project_id,
                review_level=level,
                required_level=level,
                status=ReviewStatus.PENDING,
                sla_hours=self.SLA_CONFIG.get(level, 24),
                due_at=datetime.now() + timedelta(hours=self.SLA_CONFIG.get(level, 24)),
            )
            chain.tasks.append(task)
            self._tasks[task.task_id] = task

        self._chains[chain.chain_id] = chain

        # 触发回调
        await self._trigger_callback("on_chain_created", chain)

        return chain

    async def submit_for_review(
        self,
        chain_id: str,
        submitter_id: str,
        submitter_name: str,
        is_ai_generated: bool = False,
    ) -> ReviewTask:
        """
        提交审核

        启动审批链的第一个任务。
        """
        chain = self._chains.get(chain_id)
        if not chain:
            raise ValueError(f"审批链 {chain_id} 不存在")

        # 查找第一个待处理任务
        current_task = chain.get_current_task()
        if not current_task:
            raise ValueError("没有待处理的审核任务")

        # 更新任务状态
        current_task.status = ReviewStatus.IN_PROGRESS
        current_task.assigned_at = datetime.now()

        # 如果是自检，设置提交人为审核人
        if current_task.review_level == ReviewLevel.SELF_CHECK:
            current_task.assigned_to = submitter_id
            current_task.assigned_to_name = submitter_name

        # 更新统计
        self._statistics["total_tasks"] += 1

        # 触发回调
        await self._trigger_callback("on_task_started", current_task)

        return current_task

    async def complete_review(
        self,
        task_id: str,
        reviewer_id: str,
        decision: str,                          # approved/rejected/revision
        comments: Optional[List[Dict[str, Any]]] = None,
        reason: Optional[str] = None,
    ) -> ApprovalChain:
        """
        完成审核

        Args:
            task_id: 任务ID
            reviewer_id: 审核人ID
            decision: 决定（approved/rejected/revision）
            comments: 审核意见列表
            reason: 决定理由

        Returns:
            ApprovalChain: 更新后的审批链
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        # 更新任务状态
        task.status = ReviewStatus.APPROVED if decision == "approved" else ReviewStatus.REJECTED if decision == "rejected" else ReviewStatus.REVISION_REQUESTED
        task.decision = decision
        task.decision_reason = reason
        task.completed_at = datetime.now()

        # 添加审核意见
        if comments:
            for comment_data in comments:
                comment = ReviewComment(
                    comment_id=f"CMT:{task_id}:{len(task.comments) + 1:03d}",
                    task_id=task_id,
                    reviewer_id=reviewer_id,
                    reviewer_name=comment_data.get("reviewer_name", "审核人"),
                    reviewer_role=comment_data.get("reviewer_role", ""),
                    review_level=task.review_level,
                    content=comment_data.get("content", ""),
                    suggestion=comment_data.get("suggestion"),
                    issues=comment_data.get("issues", []),
                )
                task.comments.append(comment)

        # 添加审核历史
        task.review_history.append({
            "action": "complete",
            "reviewer_id": reviewer_id,
            "decision": decision,
            "completed_at": datetime.now().isoformat(),
        })

        # 更新统计
        self._statistics["completed_tasks"] += 1

        # 获取审批链
        chain = self._chains.get(task.task_id.split(":")[1])
        if chain:
            # 如果是拒绝或要求修改，终止审批链
            if decision in ["rejected", "revision"]:
                chain.is_completed = True
                chain.failed_level = task.review_level
            else:
                # 移动到下一级别
                chain.current_level_index += 1
                if chain.current_level_index < len(chain.levels):
                    chain.current_level = chain.levels[chain.current_level_index]
                else:
                    # 全部通过
                    chain.is_completed = True
                    chain.is_approved = True
                    chain.completed_at = datetime.now()

        # 触发回调
        await self._trigger_callback("on_task_completed", task)

        return chain

    async def add_comment(
        self,
        task_id: str,
        reviewer_id: str,
        reviewer_name: str,
        reviewer_role: str,
        content: str,
        suggestion: Optional[str] = None,
        issues: Optional[List[Dict[str, Any]]] = None,
        section_name: Optional[str] = None,
        paragraph_number: Optional[int] = None,
    ) -> ReviewComment:
        """添加审核意见"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        comment = ReviewComment(
            comment_id=f"CMT:{task_id}:{len(task.comments) + 1:03d}",
            task_id=task_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_role=reviewer_role,
            review_level=task.review_level,
            content=content,
            suggestion=suggestion,
            issues=issues or [],
            section_name=section_name,
            paragraph_number=paragraph_number,
        )

        task.comments.append(comment)
        task.updated_at = datetime.now()

        return comment

    async def resolve_comment(
        self,
        comment_id: str,
        resolver_id: str,
        resolution: str,
    ) -> ReviewComment:
        """标记意见为已解决"""
        # 查找comment
        for task in self._tasks.values():
            for comment in task.comments:
                if comment.comment_id == comment_id:
                    comment.is_resolved = True
                    comment.resolved_by = resolver_id
                    comment.resolved_at = datetime.now()
                    return comment

        raise ValueError(f"意见 {comment_id} 不存在")

    async def get_pending_tasks(
        self,
        user_id: Optional[str] = None,
        review_level: Optional[ReviewLevel] = None,
    ) -> List[ReviewTask]:
        """获取待处理任务"""
        tasks = []

        for task in self._tasks.values():
            if task.status not in [ReviewStatus.PENDING, ReviewStatus.IN_PROGRESS]:
                continue

            if user_id and task.assigned_to and task.assigned_to != user_id:
                continue

            if review_level and task.review_level != review_level:
                continue

            tasks.append(task)

        # 按优先级和截止时间排序
        tasks.sort(key=lambda t: (t.is_overdue, t.priority == "urgent", t.due_at or datetime.max))

        return tasks

    async def get_chain_progress(self, chain_id: str) -> Dict[str, Any]:
        """获取审批链进度"""
        chain = self._chains.get(chain_id)
        if not chain:
            return {}

        completed = sum(1 for t in chain.tasks if t.status == ReviewStatus.APPROVED)
        total = len(chain.tasks)

        return {
            "chain_id": chain_id,
            "document_id": chain.document_id,
            "is_completed": chain.is_completed,
            "is_approved": chain.is_approved,
            "current_level": chain.current_level.value,
            "progress": f"{completed}/{total}",
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
            "tasks": [t.to_dict() for t in chain.tasks],
        }

    def register_callback(self, event: str, callback: Callable) -> None:
        """注册回调函数"""
        self._callbacks[event] = callback

    async def _trigger_callback(self, event: str, data: Any) -> None:
        """触发回调"""
        callback = self._callbacks.get(event)
        if callback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                # 日志记录
                pass

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._statistics["total_tasks"]
        completed = self._statistics["completed_tasks"]

        return {
            **self._statistics,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "active_chains": len([c for c in self._chains.values() if not c.is_completed]),
            "active_tasks": len([t for t in self._tasks.values() if t.status in [ReviewStatus.PENDING, ReviewStatus.IN_PROGRESS]]),
            "overdue_tasks": len([t for t in self._tasks.values() if t.check_overdue()]),
        }


import asyncio

# 全局单例
_expert_workflow: Optional[ExpertReviewWorkflow] = None


def get_expert_workflow() -> ExpertReviewWorkflow:
    """获取专家复核工作流单例"""
    global _expert_workflow
    if _expert_workflow is None:
        _expert_workflow = ExpertReviewWorkflow()
    return _expert_workflow