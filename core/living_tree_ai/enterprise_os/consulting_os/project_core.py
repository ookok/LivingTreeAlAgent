"""
项目管理核心模块

以项目为中心的咨询服务管理。

核心功能：
1. 项目生命周期管理
2. 项目状态机
3. 团队协作
4. 时间线管理
5. 交付物管理
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta


# ==================== 枚举定义 ====================

class ProjectType(Enum):
    """项目类型"""
    EIA = "eia"                         # 环境影响评价
    SAFETY_ASSESSMENT = "safety"         # 安全评价
    ENERGY_ASSESSMENT = "energy"         # 能源评价
    FEASIBILITY = "feasibility"          # 可行性研究
    POLLUTION_PERMIT = "pollution_permit" # 排污许可证
    EMERGENCY_PLAN = "emergency_plan"     # 应急预案
    ACCEPTANCE = "acceptance"            # 验收监测
    COMPLIANCE = "compliance"            # 合规审查
    OTHER = "other"                     # 其他咨询


class ProjectPhase(Enum):
    """项目阶段"""
    BUSINESS = "business"               # 商务阶段
    KICKOFF = "kickoff"                 # 启动阶段
    DATA_COLLECTION = "data_collection"  # 资料收集
    DOCUMENTATION = "documentation"     # 文档编写
    REVIEW = "review"                   # 审核阶段
    DECLARATION = "declaration"         # 申报阶段
    DELIVERY = "delivery"               # 交付阶段
    ARCHIVE = "archive"                 # 归档阶段
    COMPLETED = "completed"             # 已完成


class ProjectStatus(Enum):
    """项目状态"""
    DRAFT = "draft"                     # 草稿
    ACTIVE = "active"                   # 进行中
    ON_HOLD = "on_hold"                 # 暂停
    REVIEWING = "reviewing"             # 审核中
    SUBMITTED = "submitted"              # 已提交
    APPROVED = "approved"               # 已通过
    REJECTED = "rejected"              # 被驳回
    CANCELLED = "cancelled"            # 已取消
    COMPLETED = "completed"             # 已完成


class ProjectPriority(Enum):
    """项目优先级"""
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    URGENT = 10


# ==================== 数据模型 ====================

@dataclass
class ProjectMember:
    """项目成员"""
    member_id: str
    user_id: str
    name: str
    role: str                              # 项目经理/技术负责人/工程师/专家
    responsibilities: List[str] = field(default_factory=list)
    workload_percent: float = 100.0       # 工作量占比
    joined_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class ProjectTimeline:
    """项目时间线"""
    phase: ProjectPhase
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    planned_days: int = 0
    actual_days: int = 0
    status: str = "pending"               # pending/in_progress/completed/delayed
    milestone: str = ""                    # 里程碑
    notes: str = ""


@dataclass
class ProjectDeliverable:
    """项目交付物"""
    deliverable_id: str
    document_id: str                       # 关联的文档ID
    document_type: str                      # 交付物类型
    name: str
    description: str = ""
    required: bool = True                  # 合同是否要求
    optional: bool = False

    # 状态
    status: str = "pending"               # pending/draft/review/approved/submitted
    progress: float = 0.0                  # 0-100

    # 时间
    planned_date: Optional[datetime] = None
    actual_date: Optional[datetime] = None

    # 审核
    reviewer: str = ""
    review_comments: List[str] = field(default_factory=list)
    approval_status: str = "pending"       # pending/approved/rejected

    # 依赖
    depends_on: List[str] = field(default_factory=list)  # 依赖的交付物ID


@dataclass
class ProjectRelation:
    """项目关联"""
    project_id: str
    related_project_id: str
    relation_type: str                      # parent/child/phase/similar/reference
    description: str = ""


@dataclass
class Project:
    """
    咨询项目

    以项目为中心的核心数据模型
    """
    project_id: str
    project_code: str                       # 项目编号，如 "PROJ-2024-001"
    name: str
    project_type: ProjectType

    # 客户信息（关联到企业维度）
    client_id: str                          # 客户ID
    client_name: str                        # 客户名称（冗余便于显示）
    enterprise_profile_id: str = ""          # 关联的企业Profile

    # 项目基本信息
    description: str = ""
    contract_no: str = ""                   # 合同编号
    contract_amount: float = 0.0           # 合同金额
    currency: str = "CNY"

    # 时间
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None

    # 状态
    status: ProjectStatus = ProjectStatus.DRAFT
    current_phase: ProjectPhase = ProjectPhase.BUSINESS
    priority: ProjectPriority = ProjectPriority.MEDIUM

    # 团队
    members: List[ProjectMember] = field(default_factory=list)
    project_manager: str = ""              # 项目经理用户ID

    # 时间线（按阶段）
    timelines: Dict[str, ProjectTimeline] = field(default_factory=dict)

    # 交付物
    deliverables: List[ProjectDeliverable] = field(default_factory=list)

    # 关联项目
    relations: List[ProjectRelation] = field(default_factory=list)

    # 进度
    progress: float = 0.0                   # 0-100

    # 标签
    tags: List[str] = field(default_factory=list)

    # 备注
    notes: str = ""

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""


# ==================== 项目服务 ====================

class ProjectWorkflow:
    """
    项目工作流引擎

    管理项目阶段的流转
    """

    # 阶段流转规则
    PHASE_TRANSITIONS = {
        ProjectPhase.BUSINESS: [ProjectPhase.KICKOFF],
        ProjectPhase.KICKOFF: [ProjectPhase.DATA_COLLECTION, ProjectPhase.CANCELLED],
        ProjectPhase.DATA_COLLECTION: [ProjectPhase.DOCUMENTATION, ProjectPhase.KICKOFF],
        ProjectPhase.DOCUMENTATION: [ProjectPhase.REVIEW, ProjectPhase.DATA_COLLECTION],
        ProjectPhase.REVIEW: [ProjectPhase.DECLARATION, ProjectPhase.DOCUMENTATION],
        ProjectPhase.DECLARATION: [ProjectPhase.DELIVERY, ProjectPhase.REVIEW],
        ProjectPhase.DELIVERY: [ProjectPhase.ARCHIVE],
        ProjectPhase.ARCHIVE: [ProjectPhase.COMPLETED],
        ProjectPhase.COMPLETED: [],
    }

    # 阶段默认工期（天）
    DEFAULT_DURATIONS = {
        ProjectPhase.BUSINESS: 3,
        ProjectPhase.KICKOFF: 2,
        ProjectPhase.DATA_COLLECTION: 14,
        ProjectPhase.DOCUMENTATION: 28,
        ProjectPhase.REVIEW: 14,
        ProjectPhase.DECLARATION: 3,
        ProjectPhase.DELIVERY: 2,
        ProjectPhase.ARCHIVE: 2,
    }

    @classmethod
    def can_transition(cls, from_phase: ProjectPhase, to_phase: ProjectPhase) -> bool:
        """检查阶段是否可以流转"""
        return to_phase in cls.PHASE_TRANSITIONS.get(from_phase, [])

    @classmethod
    def get_available_transitions(cls, current_phase: ProjectPhase) -> List[ProjectPhase]:
        """获取可用的下一阶段"""
        return cls.PHASE_TRANSITIONS.get(current_phase, [])

    @classmethod
    def get_phase_duration(cls, phase: ProjectPhase, project_type: ProjectType = None) -> int:
        """获取阶段默认工期"""
        base_days = cls.DEFAULT_DURATIONS.get(phase, 7)

        # 根据项目类型调整
        if project_type:
            multipliers = {
                ProjectType.EIA: 1.0,
                ProjectType.SAFETY_ASSESSMENT: 0.8,
                ProjectType.FEASIBILITY: 1.2,
                ProjectType.POLLUTION_PERMIT: 0.6,
                ProjectType.EMERGENCY_PLAN: 0.5,
            }
            base_days = int(base_days * multipliers.get(project_type, 1.0))

        return base_days


class ProjectService:
    """
    项目管理服务

    核心功能：
    1. 项目的CRUD
    2. 阶段流转
    3. 团队管理
    4. 交付物管理
    5. 进度计算
    """

    def __init__(self):
        self._projects: Dict[str, Project] = {}
        self._code_counter = 0

    def _generate_project_id(self) -> str:
        """生成项目ID"""
        return f"PRJ:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_project_code(self) -> str:
        """生成项目编号"""
        self._code_counter += 1
        year = datetime.now().year
        return f"PROJ-{year}-{self._code_counter:04d}"

    async def create_project(
        self,
        name: str,
        project_type: ProjectType,
        client_id: str,
        client_name: str,
        created_by: str,
        description: str = "",
        contract_no: str = "",
        contract_amount: float = 0.0,
        start_date: datetime = None,
        end_date: datetime = None,
        priority: ProjectPriority = ProjectPriority.MEDIUM,
        tags: List[str] = None,
        **kwargs
    ) -> Project:
        """
        创建项目

        Args:
            name: 项目名称
            project_type: 项目类型
            client_id: 客户ID
            client_name: 客户名称
            created_by: 创建人
            description: 描述
            contract_no: 合同编号
            contract_amount: 合同金额
            start_date: 开始日期
            end_date: 截止日期
            priority: 优先级
            tags: 标签

        Returns:
            Project
        """
        project_id = self._generate_project_id()
        project_code = self._generate_project_code()

        project = Project(
            project_id=project_id,
            project_code=project_code,
            name=name,
            project_type=project_type,
            client_id=client_id,
            client_name=client_name,
            description=description,
            contract_no=contract_no,
            contract_amount=contract_amount,
            start_date=start_date or datetime.now(),
            end_date=end_date,
            priority=priority,
            tags=tags or [],
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 初始化各阶段时间线
        for phase in ProjectPhase:
            planned_days = ProjectWorkflow.get_phase_duration(phase, project_type)
            project.timelines[phase.value] = ProjectTimeline(
                phase=phase,
                planned_days=planned_days
            )

        self._projects[project_id] = project
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目"""
        return self._projects.get(project_id)

    async def get_project_by_code(self, project_code: str) -> Optional[Project]:
        """通过项目编号获取项目"""
        for project in self._projects.values():
            if project.project_code == project_code:
                return project
        return None

    async def list_projects(
        self,
        client_id: str = None,
        status: ProjectStatus = None,
        project_type: ProjectType = None,
        tags: List[str] = None
    ) -> List[Project]:
        """列出项目"""
        results = list(self._projects.values())

        if client_id:
            results = [p for p in results if p.client_id == client_id]

        if status:
            results = [p for p in results if p.status == status]

        if project_type:
            results = [p for p in results if p.project_type == project_type]

        if tags:
            results = [
                p for p in results
                if any(tag in p.tags for tag in tags)
            ]

        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    async def update_project(
        self,
        project_id: str,
        **updates
    ) -> Optional[Project]:
        """更新项目"""
        project = self._projects.get(project_id)
        if not project:
            return None

        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)

        project.updated_at = datetime.now()
        return project

    async def transition_phase(
        self,
        project_id: str,
        to_phase: ProjectPhase
    ) -> bool:
        """
        流转项目阶段

        Args:
            project_id: 项目ID
            to_phase: 目标阶段

        Returns:
            是否成功
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        if not ProjectWorkflow.can_transition(project.current_phase, to_phase):
            return False

        # 更新阶段时间线
        old_phase = project.current_phase
        timeline = project.timelines.get(old_phase.value)
        if timeline:
            timeline.end_date = datetime.now()
            timeline.actual_days = (timeline.end_date - (timeline.start_date or datetime.now())).days
            timeline.status = "completed"

        # 设置新阶段
        project.current_phase = to_phase
        new_timeline = project.timelines.get(to_phase.value)
        if new_timeline:
            new_timeline.start_date = datetime.now()
            new_timeline.status = "in_progress"

        # 更新状态
        if to_phase == ProjectPhase.COMPLETED:
            project.status = ProjectStatus.COMPLETED
            project.actual_end_date = datetime.now()

        project.updated_at = datetime.now()
        return True

    async def add_member(
        self,
        project_id: str,
        user_id: str,
        name: str,
        role: str,
        responsibilities: List[str] = None,
        workload_percent: float = 100.0
    ) -> bool:
        """添加项目成员"""
        project = self._projects.get(project_id)
        if not project:
            return False

        member = ProjectMember(
            member_id=f"{project_id}:{user_id}",
            user_id=user_id,
            name=name,
            role=role,
            responsibilities=responsibilities or [],
            workload_percent=workload_percent
        )

        project.members.append(member)

        if role == "项目经理":
            project.project_manager = user_id

        project.updated_at = datetime.now()
        return True

    async def remove_member(self, project_id: str, user_id: str) -> bool:
        """移除项目成员"""
        project = self._projects.get(project_id)
        if not project:
            return False

        project.members = [
            m for m in project.members
            if m.user_id != user_id
        ]

        if project.project_manager == user_id:
            project.project_manager = ""

        project.updated_at = datetime.now()
        return True

    async def add_deliverable(
        self,
        project_id: str,
        deliverable_id: str,
        document_type: str,
        name: str,
        required: bool = True,
        planned_date: datetime = None,
        depends_on: List[str] = None,
        **kwargs
    ) -> bool:
        """添加交付物"""
        project = self._projects.get(project_id)
        if not project:
            return False

        deliverable = ProjectDeliverable(
            deliverable_id=deliverable_id,
            document_id=kwargs.get("document_id", ""),
            document_type=document_type,
            name=name,
            required=required,
            planned_date=planned_date,
            depends_on=depends_on or []
        )

        project.deliverables.append(deliverable)
        project.updated_at = datetime.now()
        return True

    async def update_deliverable_status(
        self,
        project_id: str,
        deliverable_id: str,
        status: str,
        progress: float = None,
        **updates
    ) -> bool:
        """更新交付物状态"""
        project = self._projects.get(project_id)
        if not project:
            return False

        for d in project.deliverables:
            if d.deliverable_id == deliverable_id:
                d.status = status
                if progress is not None:
                    d.progress = progress
                for key, value in updates.items():
                    if hasattr(d, key):
                        setattr(d, key, value)
                break

        # 重新计算项目进度
        await self._recalculate_progress(project)

        project.updated_at = datetime.now()
        return True

    async def _recalculate_progress(self, project: Project):
        """重新计算项目进度"""
        if not project.deliverables:
            project.progress = 0.0
            return

        total_weight = sum(100 for d in project.deliverables if d.required)
        if total_weight == 0:
            project.progress = 0.0
            return

        completed_weight = sum(
            d.progress for d in project.deliverables if d.required
        )

        project.progress = (completed_weight / total_weight) * 100

    async def get_project_dashboard(self, project_id: str) -> Dict:
        """
        获取项目仪表盘

        Returns:
            项目仪表盘数据
        """
        project = self._projects.get(project_id)
        if not project:
            return {}

        # 获取阶段进度
        phase_progress = {}
        for phase_value, timeline in project.timelines.items():
            if timeline.status == "completed":
                progress = 100
            elif timeline.status == "in_progress":
                if timeline.start_date and timeline.planned_days:
                    elapsed = (datetime.now() - timeline.start_date).days
                    progress = min(100, int(elapsed / timeline.planned_days * 100))
                else:
                    progress = 50
            else:
                progress = 0
            phase_progress[phase_value] = progress

        # 获取交付物状态
        deliverable_summary = {
            "total": len(project.deliverables),
            "pending": sum(1 for d in project.deliverables if d.status == "pending"),
            "draft": sum(1 for d in project.deliverables if d.status == "draft"),
            "review": sum(1 for d in project.deliverables if d.status == "review"),
            "approved": sum(1 for d in project.deliverables if d.status == "approved"),
            "submitted": sum(1 for d in project.deliverables if d.status == "submitted"),
        }

        # 获取成员工作量
        member_workload = [
            {
                "name": m.name,
                "role": m.role,
                "workload": m.workload_percent
            }
            for m in project.members
        ]

        # 计算剩余时间
        remaining_days = None
        if project.end_date:
            remaining = (project.end_date - datetime.now()).days
            remaining_days = max(0, remaining)

        return {
            "project_id": project.project_id,
            "project_code": project.project_code,
            "name": project.name,
            "status": project.status.value,
            "current_phase": project.current_phase.value,
            "progress": round(project.progress, 1),
            "phase_progress": phase_progress,
            "deliverable_summary": deliverable_summary,
            "member_workload": member_workload,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "remaining_days": remaining_days,
            "contract_amount": project.contract_amount,
        }

    async def add_relation(
        self,
        project_id: str,
        related_project_id: str,
        relation_type: str,
        description: str = ""
    ) -> bool:
        """添加项目关联"""
        project = self._projects.get(project_id)
        if not project:
            return False

        relation = ProjectRelation(
            project_id=project_id,
            related_project_id=related_project_id,
            relation_type=relation_type,
            description=description
        )

        project.relations.append(relation)
        project.updated_at = datetime.now()
        return True

    async def get_project_tree(self, project_id: str) -> Dict:
        """获取项目关联树"""
        project = self._projects.get(project_id)
        if not project:
            return {}

        tree = {
            "project": {
                "project_id": project.project_id,
                "project_code": project.project_code,
                "name": project.name,
                "type": project.project_type.value,
                "status": project.status.value
            },
            "relations": [],
            "children": []
        }

        # 添加关联
        for rel in project.relations:
            related = self._projects.get(rel.related_project_id)
            if related:
                tree["relations"].append({
                    "type": rel.relation_type,
                    "project": {
                        "project_id": related.project_id,
                        "project_code": related.project_code,
                        "name": related.name,
                        "status": related.status.value
                    }
                })

        # 添加子项目
        for other in self._projects.values():
            for rel in other.relations:
                if rel.related_project_id == project_id and rel.relation_type == "child":
                    tree["children"].append({
                        "project_id": other.project_id,
                        "project_code": other.project_code,
                        "name": other.name,
                        "status": other.status.value
                    })

        return tree


# ==================== 单例模式 ====================

_project_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """获取项目服务单例"""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
