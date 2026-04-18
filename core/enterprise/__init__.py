"""
企业智能协同系统 (Enterprise Intelligent Collaboration System)
============================================================

核心愿景："从单机工具进化为智能团队操作系统，实现自组织的企业级协同网络"

模块结构:
- EnterpriseModeSwitcher: 企业模式自动切换引擎
- DynamicOrgStructure: 动态组织架构管理
- SmartRoleAssignment: 智能角色权限分配
- EnterprisePublishControl: 企业内发布订阅控制
- ExternalInviteApproval: 外部邀请审批系统
- IntelligentMessageRouter: AI增强智能消息路由
- EnterpriseKnowledgeGraph: 企业知识图谱
- SmartProjectSelfOrg: 智能项目自组织
- EnterpriseMemorySystem: 企业记忆系统
- EnterpriseDigitalTwin: 企业数字孪生
"""

import json
import re
import uuid
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from enum import Enum
from collections import defaultdict
import hashlib


# ============================================================
# 枚举定义
# ============================================================

class AuthLevel(Enum):
    """认证级别"""
    ANONYMOUS = 0        # 匿名用户
    BASIC_VERIFIED = 1   # 基础实名（手机号）
    REAL_NAME = 2        # 完全实名（身份证+人脸）
    ENTERPRISE = 3       # 企业认证


class Role(Enum):
    """企业角色"""
    EXECUTIVE = "executive"           # 高管
    DEPARTMENT_HEAD = "department_head"  # 部门负责人
    TEAM_LEAD = "team_lead"           # 团队领导
    EMPLOYEE = "employee"             # 普通员工
    CONTRACTOR = "contractor"         # 外部协作者


class PublishChannel(Enum):
    """发布频道"""
    ANNOUNCEMENT = "announcement"  # 公告
    DEPARTMENT = "department"      # 部门
    PROJECT = "project"           # 项目
    INNOVATION = "innovation"     # 创新分享


class PublishPriority(Enum):
    """发布优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class InviteStatus(Enum):
    """邀请状态"""
    PENDING = "pending"      # 待审批
    APPROVED = "approved"    # 已批准
    REJECTED = "rejected"    # 已拒绝
    EXPIRED = "expired"      # 已过期
    REVOKED = "revoked"       # 已撤销


class NotificationPriority(Enum):
    """通知优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class NotificationStatus(Enum):
    """通知状态"""
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    DISMISSED = "dismissed"


class EnterprisePermission(Enum):
    """企业权限"""
    # 组织架构权限
    VIEW_ORG = "view_org"                    # 查看组织架构
    EDIT_ORG = "edit_org"                   # 编辑组织架构
    MANAGE_DEPARTMENTS = "manage_departments"  # 管理部门

    # 成员管理权限
    INVITE_MEMBER = "invite_member"         # 邀请成员
    REMOVE_MEMBER = "remove_member"         # 移除成员
    APPROVE_JOIN = "approve_join"          # 审批加入

    # 管理员权限
    MANAGE_ADMINS = "manage_admins"         # 管理管理员
    MANAGE_PERMISSIONS = "manage_permissions"  # 管理权限
    TRANSFER_OWNERSHIP = "transfer_ownership"  # 转让所有权

    # 企业设置权限
    EDIT_SETTINGS = "edit_settings"         # 编辑设置
    DELETE_ENTERPRISE = "delete_enterprise"  # 删除企业

    # 发布权限
    PUBLISH_ANNOUNCEMENT = "publish_announcement"  # 发布公告
    PUBLISH_DEPARTMENT = "publish_department"  # 发布部门内容

    # 投票权限
    INITIATE_VOTE = "initiate_vote"        # 发起投票
    CAST_VOTE = "cast_vote"                # 参与投票


class VoteType(Enum):
    """投票类型"""
    ENTERPRISE_REVOKE = "enterprise_revoke"  # 企业撤销
    MEMBER_REMOVE = "member_remove"         # 成员移除
    POLICY_CHANGE = "policy_change"         # 政策变更
    ADMIN_APPOINT = "admin_appoint"         # 管理员任命


class VoteStatus(Enum):
    """投票状态"""
    PENDING = "pending"        # 进行中
    APPROVED = "approved"      # 通过
    REJECTED = "rejected"     # 拒绝
    EXPIRED = "expired"       # 过期
    CANCELLED = "cancelled"   # 取消


# ============================================================
# 数据模型
# ============================================================

@dataclass
class User:
    """用户模型"""
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    enterprise_id: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    role: Role = Role.EMPLOYEE
    manager_id: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    is_external: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "avatar": self.avatar,
            "auth_level": self.auth_level.value,
            "enterprise_id": self.enterprise_id,
            "department": self.department,
            "team": self.team,
            "role": self.role.value,
            "manager_id": self.manager_id,
            "permissions": self.permissions,
            "is_external": self.is_external,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat()
        }


@dataclass
class Enterprise:
    """企业模型"""
    id: str
    name: str
    business_license: Optional[str] = None
    domain: Optional[str] = None
    admin_id: Optional[str] = None
    departments: List[str] = field(default_factory=list)
    teams: List[str] = field(default_factory=list)
    members: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=lambda: {
        "enterprise_im": True,
        "org_structure": True,
        "internal_publish": True,
        "knowledge_share": True,
        "audit_log": True,
        "compliance_check": True
    })
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "business_license": self.business_license,
            "domain": self.domain,
            "admin_id": self.admin_id,
            "departments": self.departments,
            "teams": self.teams,
            "members": self.members,
            "settings": self.settings,
            "features": self.features,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class OrgNode:
    """组织架构节点"""
    id: str
    name: str
    type: str  # department/team/person
    parent_id: Optional[str] = None
    head_id: Optional[str] = None  # 负责人
    members: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    level: int = 0  # 层级深度
    children: List[str] = field(default_factory=list)  # 子节点ID列表

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "head_id": self.head_id,
            "members": self.members,
            "metadata": self.metadata,
            "level": self.level,
            "children": self.children
        }


@dataclass
class Permission:
    """权限模型"""
    id: str
    name: str
    description: str
    category: str
    level: str  # read/write/admin

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InviteRequest:
    """外部邀请请求"""
    id: str
    inviter_id: str
    invitee_name: str
    invitee_email: str
    invitee_company: Optional[str] = None
    reason: str = ""
    duration_days: int = 30
    project_id: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    status: InviteStatus = InviteStatus.PENDING
    approvers: List[str] = field(default_factory=list)
    approval_history: List[Dict] = field(default_factory=list)
    invite_code: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inviter_id": self.inviter_id,
            "invitee_name": self.invitee_name,
            "invitee_email": self.invitee_email,
            "invitee_company": self.invitee_company,
            "reason": self.reason,
            "duration_days": self.duration_days,
            "project_id": self.project_id,
            "permissions": self.permissions,
            "status": self.status.value,
            "approvers": self.approvers,
            "approval_history": self.approval_history,
            "invite_code": self.invite_code,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


@dataclass
class PublishContent:
    """发布内容"""
    id: str
    channel: PublishChannel
    title: str
    content: str
    publisher_id: str
    publisher_role: Role
    target_departments: List[str] = field(default_factory=list)
    target_teams: List[str] = field(default_factory=list)
    exclude_users: List[str] = field(default_factory=list)
    priority: PublishPriority = PublishPriority.NORMAL
    attachments: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    visibility: str = "internal"  # internal/department/team/public
    created_at: datetime = field(default_factory=datetime.now)
    stats: Dict[str, Any] = field(default_factory=lambda: {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0
    })

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel": self.channel.value,
            "title": self.title,
            "content": self.content,
            "publisher_id": self.publisher_id,
            "publisher_role": self.publisher_role.value,
            "target_departments": self.target_departments,
            "target_teams": self.target_teams,
            "exclude_users": self.exclude_users,
            "priority": self.priority.value,
            "attachments": self.attachments,
            "tags": self.tags,
            "visibility": self.visibility,
            "created_at": self.created_at.isoformat(),
            "stats": self.stats
        }


@dataclass
class Notification:
    """通知模型"""
    id: str
    type: str  # workflow/task/approval/vote/system
    title: str
    content: str
    sender_id: Optional[str] = None
    recipient_id: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    action_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    read_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "action_url": self.action_url,
            "metadata": self.metadata,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    id: str
    type: str  # person/project/concept/document/topic
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    expertise_topics: List[str] = field(default_factory=list)
    connections: List[Tuple[str, str, float]] = field(default_factory=list)  # (target_id, relation_type, weight)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties,
            "expertise_topics": self.expertise_topics,
            "connections": self.connections,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class EnterpriseDecision:
    """企业决策记录"""
    id: str
    title: str
    description: str
    context: Dict[str, Any]
    participants: List[str]
    decision: str
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    review_date: Optional[datetime] = None
    status: str = "active"  # active/reviewed/archived
    related_decisions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "participants": self.participants,
            "decision": self.decision,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "tags": self.tags,
            "review_date": self.review_date.isoformat() if self.review_date else None,
            "status": self.status,
            "related_decisions": self.related_decisions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class DigitalTwinState:
    """数字孪生状态"""
    enterprise_id: str
    organization: Dict[str, Any]
    projects: List[Dict[str, Any]]
    knowledge: Dict[str, Any]
    collaboration_network: Dict[str, Any]
    health_metrics: Dict[str, Any]
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "enterprise_id": self.enterprise_id,
            "organization": self.organization,
            "projects": self.projects,
            "knowledge": self.knowledge,
            "collaboration_network": self.collaboration_network,
            "health_metrics": self.health_metrics,
            "last_updated": self.last_updated.isoformat()
        }


# ============================================================
# 企业模式切换引擎
# ============================================================

class EnterpriseModeSwitcher:
    """企业模式智能切换器"""

    def __init__(self):
        self.switch_triggers = {
            "enterprise_auth": self._on_enterprise_auth,
            "team_invite": self._on_team_invite,
            "org_structure": self._on_org_created,
            "workflow_collab": self._on_collab_initiated
        }
        self._enterprise_spaces: Dict[str, Enterprise] = {}
        self._user_enterprise_map: Dict[str, str] = {}  # user_id -> enterprise_id

    async def switch_to_team_mode(self, enterprise_info: dict) -> dict:
        """切换到团队模式"""
        # 1. 创建企业空间
        enterprise = await self._create_enterprise_space(enterprise_info)
        self._enterprise_spaces[enterprise.id] = enterprise

        # 2. 自动组建企业P2P网络
        enterprise_network = await self._setup_enterprise_p2p(enterprise)

        # 3. 建立企业即时通信层
        enterprise_im = await self._create_enterprise_im_layer(enterprise)

        # 4. 同步企业内现有用户
        existing_users = await self._discover_existing_users(enterprise)

        # 5. 初始化企业知识库
        knowledge_base = await self._init_enterprise_kb(enterprise)

        return {
            "enterprise_space": enterprise.to_dict(),
            "network": enterprise_network,
            "im": enterprise_im,
            "users": existing_users,
            "knowledge_base": knowledge_base
        }

    async def _create_enterprise_space(self, enterprise_info: dict) -> Enterprise:
        """创建企业专属空间"""
        enterprise = Enterprise(
            id=f"ent_{uuid.uuid4().hex[:12]}",
            name=enterprise_info.get("name", "未命名企业"),
            business_license=enterprise_info.get("business_license"),
            domain=enterprise_info.get("domain"),
            admin_id=enterprise_info.get("admin_id"),
            settings={
                "default_visibility": "internal",
                "invite_approval": True,
                "data_retention": "7y",
                "backup_policy": "daily"
            }
        )
        return enterprise

    async def _setup_enterprise_p2p(self, enterprise: Enterprise) -> dict:
        """组建企业P2P网络"""
        return {
            "network_id": f"net_{enterprise.id}",
            "nodes": [],
            "topology": "mesh",
            "encryption": "enabled",
            "status": "active"
        }

    async def _create_enterprise_im_layer(self, enterprise: Enterprise) -> dict:
        """建立企业即时通信层"""
        return {
            "im_id": f"im_{enterprise.id}",
            "channels": ["announcement", "department", "project", "general"],
            "features": {
                "group_chat": True,
                "video_conf": True,
                "screen_share": True
            }
        }

    async def _discover_existing_users(self, enterprise: Enterprise) -> List[dict]:
        """发现企业现有用户"""
        # 实际应该从企业目录服务同步
        return []

    async def _init_enterprise_kb(self, enterprise: Enterprise) -> dict:
        """初始化企业知识库"""
        return {
            "kb_id": f"kb_{enterprise.id}",
            "categories": ["policy", "process", "project", "people"],
            "index_status": "ready"
        }

    async def _on_enterprise_auth(self, data: dict):
        """企业认证触发"""
        return await self.switch_to_team_mode(data)

    async def _on_team_invite(self, data: dict):
        """团队邀请触发"""
        pass

    async def _on_org_created(self, data: dict):
        """组织创建触发"""
        pass

    async def _on_collab_initiated(self, data: dict):
        """协作初始化触发"""
        pass

    def get_user_enterprise(self, user_id: str) -> Optional[Enterprise]:
        """获取用户所属企业"""
        ent_id = self._user_enterprise_map.get(user_id)
        return self._enterprise_spaces.get(ent_id) if ent_id else None

    def add_user_to_enterprise(self, user_id: str, enterprise_id: str):
        """将用户添加到企业"""
        self._user_enterprise_map[user_id] = enterprise_id
        if enterprise_id in self._enterprise_spaces:
            ent = self._enterprise_spaces[enterprise_id]
            if user_id not in ent.members:
                ent.members.append(user_id)


# ============================================================
# 动态组织架构管理
# ============================================================

class DynamicOrgStructure:
    """动态组织架构管理"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.org_graph: Dict[str, OrgNode] = {}
        self._load_org_graph()

    def _load_org_graph(self):
        """加载组织图谱"""
        pass

    async def auto_detect_structure(self, employee_data: List[dict]) -> dict:
        """自动检测组织架构"""
        # 1. 从邮箱/手机号模式推断部门
        departments = self._infer_departments_from_contacts(employee_data)

        # 2. 从通信模式推断汇报关系
        reporting_lines = await self._infer_reporting_from_communication(employee_data)

        # 3. 从项目协作推断团队结构
        teams = await self._infer_teams_from_collaboration(employee_data)

        # 4. AI辅助优化架构
        optimized = await self._ai_optimize_org_structure({
            "departments": departments,
            "reporting_lines": reporting_lines,
            "teams": teams
        })

        # 5. 生成可视化组织架构图
        org_chart = self._generate_org_chart(optimized)

        return {
            "auto_detected": optimized,
            "org_chart": org_chart,
            "confidence": self._calculate_detection_confidence(),
            "suggestions": self._generate_optimization_suggestions()
        }

    def _infer_departments_from_contacts(self, employees: List[dict]) -> Dict[str, List[str]]:
        """从联系方式推断部门"""
        department_patterns = {
            r"@([a-z]+)\.com$": "domain_department",
            r"(\d{4})@": "extension_department",
            r"([A-Z]{2,3})-": "employee_id_department"
        }

        departments = defaultdict(list)
        for emp in employees:
            contact = emp.get("contact", "")
            for pattern, dept_type in department_patterns.items():
                match = re.search(pattern, contact)
                if match:
                    dept_key = match.group(1)
                    departments[dept_key].append(emp.get("id"))
                    break

        return dict(departments)

    async def _infer_reporting_from_communication(self, employees: List[dict]) -> Dict[str, str]:
        """从通信模式推断汇报关系"""
        # 实际应该分析邮件/消息往来频率
        return {}

    async def _infer_teams_from_collaboration(self, employees: List[dict]) -> Dict[str, List[str]]:
        """从项目协作推断团队"""
        return {}

    async def _ai_optimize_org_structure(self, structure_data: dict) -> dict:
        """AI优化组织架构"""
        return structure_data

    def _generate_org_chart(self, structure: dict) -> dict:
        """生成组织架构图"""
        return {
            "nodes": [],
            "edges": [],
            "layout": "tree"
        }

    def _calculate_detection_confidence(self) -> float:
        """计算检测置信度"""
        return 0.85

    def _generate_optimization_suggestions(self) -> List[str]:
        """生成优化建议"""
        return ["建议增加跨部门协作通道", "部分团队规模偏大，建议拆分"]

    def add_org_node(self, node: OrgNode):
        """添加组织节点"""
        self.org_graph[node.id] = node

    def get_org_chart(self) -> List[dict]:
        """获取组织架构图"""
        return [node.to_dict() for node in self.org_graph.values()]


# ============================================================
# 智能角色权限分配
# ============================================================

class SmartRoleAssignment:
    """智能角色与权限分配"""

    ROLE_TEMPLATES = {
        "executive": {
            "permissions": ["*"],
            "visibility": "all",
            "approval_power": True
        },
        "department_head": {
            "permissions": ["department.*", "publish.internal", "approve.join"],
            "visibility": "department+up",
            "team_management": True
        },
        "team_lead": {
            "permissions": ["team.*", "publish.team", "invite.external"],
            "visibility": "team+peers",
            "project_management": True
        },
        "employee": {
            "permissions": ["publish.self", "subscribe.internal", "collaborate"],
            "visibility": "team",
            "external_invite": False
        },
        "contractor": {
            "permissions": ["collaborate.limited", "subscribe.approved"],
            "visibility": "project_only",
            "data_access": "restricted"
        }
    }

    def __init__(self):
        self.permission_graph = PermissionGraph()

    async def assign_smart_role(self, user: dict, context: dict) -> str:
        """智能分配角色"""
        # 1. 基于组织位置
        org_position = context.get("org_position")
        if org_position in ["CEO", "CTO", "CFO"]:
            return "executive"

        # 2. 基于管理范围
        if context.get("manages_count", 0) > 5:
            return "department_head"
        elif context.get("manages_count", 0) > 0:
            return "team_lead"

        # 3. 基于协作模式
        collaboration_stats = context.get("collaboration_stats", {})
        if collaboration_stats.get("initiates_collab", 0) > 10:
            return "team_lead"

        # 4. 基于外部身份
        if context.get("is_external"):
            return "contractor"

        return "employee"

    def get_role_permissions(self, role: str) -> List[str]:
        """获取角色权限"""
        template = self.ROLE_TEMPLATES.get(role, {})
        return template.get("permissions", [])

    def calculate_visibility_scope(self, role: str, user_context: dict) -> Set[str]:
        """计算用户可见范围"""
        visibility_rules = {
            "executive": lambda: self._all_enterprise_users(),
            "department_head": lambda: self._department_users(user_context.get("dept", "")),
            "team_lead": lambda: self._team_users(user_context.get("team", "")),
            "employee": lambda: self._team_users(user_context.get("team", "")),
            "contractor": lambda: self._project_members(user_context.get("project_id", ""))
        }

        rule = visibility_rules.get(role)
        return rule() if rule else set()

    def _all_enterprise_users(self) -> Set[str]:
        return set()

    def _department_users(self, dept: str) -> Set[str]:
        return set()

    def _team_users(self, team: str) -> Set[str]:
        return set()

    def _project_members(self, project_id: str) -> Set[str]:
        return set()


class PermissionGraph:
    """权限图谱"""

    def __init__(self):
        self.permissions: Dict[str, Permission] = {}

    def add_permission(self, perm: Permission):
        self.permissions[perm.id] = perm

    def check_permission(self, user_permissions: List[str], required: str) -> bool:
        if "*" in user_permissions:
            return True
        if required in user_permissions:
            return True
        # 检查通配符匹配
        for user_perm in user_permissions:
            if user_perm.endswith(".*") and required.startswith(user_perm[:-2]):
                return True
        return False


# ============================================================
# 企业发布订阅控制
# ============================================================

class EnterprisePublishControl:
    """企业内发布订阅控制"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.channels = self._init_channels()
        self._published_content: Dict[str, PublishContent] = {}

    def _init_channels(self) -> dict:
        """初始化企业频道"""
        return {
            "announcement": {
                "publishers": ["executive", "department_head"],
                "subscribers": "all_employees",
                "moderation": "pre_approval"
            },
            "department": {
                "publishers": ["department_head", "team_lead"],
                "subscribers": "department_members",
                "moderation": "auto"
            },
            "project": {
                "publishers": ["team_lead", "employee"],
                "subscribers": "project_members",
                "moderation": "team_lead_approval"
            },
            "innovation": {
                "publishers": "all_employees",
                "subscribers": "all_employees",
                "moderation": "peer_review"
            }
        }

    async def publish_internal(self, content: dict, publisher: dict) -> dict:
        """企业内发布内容"""
        # 1. 检查发布权限
        if not self._can_publish(publisher, content.get("channel", "department")):
            return {"success": False, "error": "无发布权限"}

        # 2. 确定可见范围
        visibility_scope = self._calculate_visibility(publisher, content)

        # 3. 敏感信息检查
        sensitive_check = await self._check_sensitive_content(content)
        if sensitive_check.get("blocked"):
            return {"success": False, "error": "包含敏感信息", "details": sensitive_check}

        # 4. 创建发布内容
        publish_content = PublishContent(
            id=f"pub_{uuid.uuid4().hex[:12]}",
            channel=PublishChannel(content.get("channel", "department")),
            title=content.get("title", ""),
            content=content.get("content", ""),
            publisher_id=publisher.get("id"),
            publisher_role=Role(publisher.get("role", "employee")),
            target_departments=content.get("target_departments", []),
            target_teams=content.get("target_teams", []),
            exclude_users=content.get("exclude_users", []),
            priority=PublishPriority(content.get("priority", "normal")),
            tags=content.get("tags", [])
        )

        self._published_content[publish_content.id] = publish_content

        # 5. 发布到企业网络
        delivery_nodes = self._calculate_optimal_delivery(visibility_scope)

        return {
            "success": True,
            "publish_id": publish_content.id,
            "recipient_count": len(visibility_scope),
            "delivery_status": "queued"
        }

    def _can_publish(self, publisher: dict, channel: str) -> bool:
        """检查发布权限"""
        channel_config = self.channels.get(channel, {})
        allowed_roles = channel_config.get("publishers", [])

        if allowed_roles == "all_employees":
            return True

        publisher_role = publisher.get("role", "employee")
        return publisher_role in allowed_roles

    def _calculate_visibility(self, publisher: dict, content: dict) -> Set[str]:
        """计算内容可见范围"""
        # 简化实现
        return set(content.get("target_users", []))

    async def _check_sensitive_content(self, content: dict) -> dict:
        """敏感信息检查"""
        sensitive_keywords = ["机密", "秘密", "保密", "内部资料"]
        text = content.get("content", "") + content.get("title", "")

        for keyword in sensitive_keywords:
            if keyword in text:
                return {"blocked": True, "keyword": keyword}

        return {"blocked": False}

    def _calculate_optimal_delivery(self, visibility_scope: Set[str]) -> List[str]:
        """计算最优传递节点"""
        return list(visibility_scope)[:10]  # 最多10个节点

    def get_channel_posts(self, channel: str, user_id: str) -> List[dict]:
        """获取频道帖子"""
        posts = []
        for post in self._published_content.values():
            if post.channel.value == channel:
                if user_id not in post.exclude_users:
                    posts.append(post.to_dict())
        return posts


# ============================================================
# 外部邀请审批系统
# ============================================================

class ExternalInviteApproval:
    """外部邀请审批系统"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.invites: Dict[str, InviteRequest] = {}
        self._approval_workflow = self._setup_approval_workflow()

    def _setup_approval_workflow(self) -> dict:
        """设置审批工作流"""
        return {
            "steps": ["department_manager", "security_officer", "it_admin"],
            "timeouts": {"department_manager": 24, "security_officer": 48, "it_admin": 24}
        }

    async def invite_external(self, inviter: dict, invitee_info: dict,
                            reason: str, duration_days: int = 30) -> dict:
        """邀请外部人员"""
        # 1. 生成唯一邀请码
        invite_code = self._generate_invite_code(inviter, invitee_info)

        # 2. 创建审批申请
        invite = InviteRequest(
            id=f"inv_{uuid.uuid4().hex[:12]}",
            inviter_id=inviter.get("id"),
            invitee_name=invitee_info.get("name"),
            invitee_email=invitee_info.get("email"),
            invitee_company=invitee_info.get("company"),
            reason=reason,
            duration_days=duration_days,
            project_id=invitee_info.get("project_id"),
            permissions=invitee_info.get("permissions", []),
            invite_code=invite_code,
            approvers=self._determine_approvers(inviter),
            expires_at=datetime.now() + timedelta(days=duration_days)
        )

        self.invites[invite.id] = invite

        # 3. 创建审批任务
        approval_task = await self._create_approval_task(invite)

        return {
            "invite_code": invite_code,
            "invite_url": f"/invite/{invite_code}",
            "qr_code": None,  # 生成二维码
            "approval_task": approval_task,
            "estimated_time": "1-3个工作日",
            "instructions": self._generate_invite_instructions()
        }

    def _generate_invite_code(self, inviter: dict, invitee_info: dict) -> str:
        """生成邀请码"""
        raw = f"{inviter.get('id')}_{invitee_info.get('email')}_{datetime.now().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _determine_approvers(self, inviter: dict) -> List[str]:
        """确定审批人"""
        # 简化实现
        return ["manager_001", "security_001"]

    async def _create_approval_task(self, invite: InviteRequest) -> dict:
        """创建审批任务"""
        return {
            "task_id": f"task_{invite.id}",
            "invite_id": invite.id,
            "approvers": invite.approvers,
            "status": "pending"
        }

    def _generate_invite_instructions(self) -> dict:
        """生成邀请说明"""
        return {
            "steps": ["审批通过后生成邀请链接", "被邀请人点击链接注册"],
            "注意事项": ["确保提供真实信息", "遵守企业安全规范"]
        }

    async def process_approval(self, task_id: str, approver: dict,
                             decision: str, comments: str = "") -> dict:
        """处理审批"""
        invite_id = task_id.replace("task_", "")
        invite = self.invites.get(invite_id)

        if not invite:
            return {"success": False, "error": "邀请不存在"}

        # 记录审批历史
        invite.approval_history.append({
            "approver_id": approver.get("id"),
            "decision": decision,
            "comments": comments,
            "timestamp": datetime.now().isoformat()
        })

        if decision == "approve":
            # 检查是否所有审批人都通过了
            pending_approvals = len(invite.approvers) - len(invite.approval_history)
            if pending_approvals <= 0:
                invite.status = InviteStatus.APPROVED
                return {
                    "success": True,
                    "decision": "approved",
                    "message": "邀请已获批准"
                }
            return {"success": True, "decision": "approved", "message": "已记录审批，等待其他审批人"}

        elif decision == "reject":
            invite.status = InviteStatus.REJECTED
            return {
                "success": True,
                "decision": "rejected",
                "reason": comments,
                "suggestions": ["可重新发起邀请", "联系审批人了解拒绝原因"]
            }

        return {"success": False, "error": "无效的审批决定"}


# ============================================================
# AI增强智能消息路由
# ============================================================

class IntelligentMessageRouter:
    """智能消息路由"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.routing_history: List[dict] = []

    async def route_message(self, message: dict, context: dict) -> dict:
        """智能路由消息"""
        # 1. AI分析消息内容
        message_analysis = await self._ai_analyze_message(message)

        # 2. 确定最佳接收者
        optimal_recipients = self._determine_best_recipients(message_analysis, context.get("sender"))

        # 3. 智能排序优先级
        prioritized = self._prioritize_recipients(optimal_recipients, message_analysis.get("urgency", 0.5))

        # 4. 选择传递方式
        delivery_method = self._select_delivery_method(
            message_analysis.get("type"),
            prioritized
        )

        # 5. 智能调度传递
        delivery_schedule = self._schedule_delivery(message_analysis, context.get("working_hours"))

        return {
            "recipients": prioritized,
            "delivery_method": delivery_method,
            "schedule": delivery_schedule,
            "estimated_read_time": self._estimate_read_time(message_analysis),
            "follow_up_suggestions": self._generate_follow_up_suggestions(message_analysis)
        }

    async def _ai_analyze_message(self, message: dict) -> dict:
        """AI分析消息内容"""
        content = message.get("content", "")

        # 简单的关键词分析
        analysis = {
            "type": "general",
            "urgency": 0.5,
            "topics": [],
            "requires_approval": False,
            "project_related": None,
            "expertise_needed": []
        }

        # 紧急关键词
        urgent_keywords = ["紧急", "急需", "立刻", "马上", "截止", " deadline"]
        for kw in urgent_keywords:
            if kw in content:
                analysis["urgency"] = 0.9
                break

        # 审批关键词
        approval_keywords = ["审批", "批准", "申请", "请示"]
        for kw in approval_keywords:
            if kw in content:
                analysis["requires_approval"] = True
                analysis["type"] = "approval"
                break

        # 项目关键词
        if "项目" in content:
            analysis["project_related"] = "unknown"
            analysis["type"] = "project"

        return analysis

    def _determine_best_recipients(self, message_analysis: dict, sender: dict) -> List[str]:
        """确定最佳接收者"""
        recipients = set()

        # 基于内容相关性
        if message_analysis.get("project_related"):
            recipients.update(self._get_project_members(message_analysis["project_related"]))

        # 基于专业知识
        for topic in message_analysis.get("expertise_needed", []):
            experts = self._find_domain_experts(topic)
            recipients.update(experts)

        # 基于审批需求
        if message_analysis.get("requires_approval"):
            approvers = self._find_approvers(sender)
            recipients.update(approvers)

        return list(recipients)

    def _prioritize_recipients(self, recipients: List[str], urgency: float) -> List[Tuple[str, float]]:
        """优先级排序"""
        scored = []
        for r in recipients:
            # 简单评分：基础分 + 紧急加成
            score = 0.5 + (urgency * 0.5)
            scored.append((r, score))
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _select_delivery_method(self, msg_type: str, recipients: List[Tuple[str, float]]) -> dict:
        """选择传递方式"""
        if msg_type == "approval":
            return {"method": "direct", "channels": ["in_app", "email"]}
        return {"method": "broadcast", "channels": ["in_app"]}

    def _schedule_delivery(self, message_analysis: dict, working_hours: dict = None) -> dict:
        """调度传递时间"""
        if message_analysis.get("urgency", 0) > 0.8:
            return {"type": "immediate", "delay": 0}

        # 非紧急消息可在非工作时间延迟
        return {"type": "deferred", "delay": 3600}  # 1小时后

    def _estimate_read_time(self, message_analysis: dict) -> int:
        """估算阅读时间（秒）"""
        return 30  # 默认30秒

    def _generate_follow_up_suggestions(self, message_analysis: dict) -> List[str]:
        """生成跟进建议"""
        suggestions = []
        if message_analysis.get("requires_approval"):
            suggestions.append("提醒审批人及时处理")
        if message_analysis.get("urgency", 0) > 0.7:
            suggestions.append("考虑电话跟进")
        return suggestions

    def _get_project_members(self, project_id: str) -> List[str]:
        return []

    def _find_domain_experts(self, topic: str) -> List[str]:
        return []

    def _find_approvers(self, sender: dict) -> List[str]:
        return []


# ============================================================
# 企业知识图谱
# ============================================================

class EnterpriseKnowledgeGraph:
    """企业知识图谱"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.graph: Dict[str, KnowledgeNode] = {}
        self._relationships: List[Tuple[str, str, str, float]] = []  # source, target, type, weight

    async def build_from_interactions(self, interactions: List[dict]):
        """从交互中构建知识图谱"""
        # 1. 提取实体
        entities = self._extract_entities(interactions)

        # 2. 分析关系
        relationships = self._analyze_relationships(interactions)

        # 3. 添加节点
        for entity in entities:
            self.graph[entity.id] = entity

        # 4. 添加边
        for rel in relationships:
            self._relationships.append((rel["source"], rel["target"], rel["type"], rel["weight"]))

        # 5. AI推理隐藏关系
        hidden_relations = await self._infer_hidden_relationships()
        for rel in hidden_relations:
            self._relationships.append((rel["source"], rel["target"], "inferred", rel["confidence"]))

        return self

    def _extract_entities(self, interactions: List[dict]) -> List[KnowledgeNode]:
        """提取实体"""
        entities = []
        for interaction in interactions:
            if interaction.get("type") == "person":
                entities.append(KnowledgeNode(
                    id=interaction.get("id"),
                    type="person",
                    name=interaction.get("name"),
                    expertise_topics=interaction.get("topics", [])
                ))
        return entities

    def _analyze_relationships(self, interactions: List[dict]) -> List[dict]:
        """分析关系"""
        return []

    async def _infer_hidden_relationships(self) -> List[dict]:
        """AI推理隐藏关系"""
        return []

    def find_expert_for_topic(self, topic: str, min_confidence: float = 0.7) -> List[dict]:
        """查找某个话题的专家"""
        experts = []

        for node in self.graph.values():
            if node.type == "person":
                # 计算专业度得分
                expertise_score = self._calculate_expertise_score(node.id, topic)

                if expertise_score >= min_confidence:
                    responsiveness = self._calculate_responsiveness(node.id)

                    experts.append({
                        "person_id": node.id,
                        "person_name": node.name,
                        "expertise_score": expertise_score,
                        "responsiveness": responsiveness,
                        "recommendation_reason": f"在{topic}领域有{expertise_score:.0%}的专业度"
                    })

        # 按专业度和响应意愿排序
        experts.sort(key=lambda x: (x["expertise_score"], x["responsiveness"]), reverse=True)

        return experts

    def _calculate_expertise_score(self, person_id: str, topic: str) -> float:
        """计算专业度得分"""
        node = self.graph.get(person_id)
        if not node:
            return 0.0

        # 基于话题连接计算
        topic_connections = sum(
            weight for s, t, rel_type, weight in self._relationships
            if (s == person_id or t == person_id) and rel_type == "expert_in"
        )

        return min(1.0, topic_connections)

    def _calculate_responsiveness(self, person_id: str) -> float:
        """计算响应意愿"""
        return 0.8  # 默认值

    def add_node(self, node: KnowledgeNode):
        """添加节点"""
        self.graph[node.id] = node

    def get_graph_data(self) -> dict:
        """获取图谱数据"""
        nodes = [node.to_dict() for node in self.graph.values()]
        edges = [
            {"source": s, "target": t, "type": r, "weight": w}
            for s, t, r, w in self._relationships
        ]
        return {"nodes": nodes, "edges": edges}


# ============================================================
# 智能项目自组织
# ============================================================

class SmartProjectSelfOrg:
    """智能项目自组织"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.projects: Dict[str, dict] = {}

    async def auto_form_project(self, project_idea: dict, initiator: dict) -> dict:
        """自动组建项目团队"""
        # 1. AI分析项目需求
        requirements = await self._ai_analyze_requirements(project_idea)

        # 2. 智能匹配团队成员
        recommended_team = self._match_team_members(requirements, initiator)

        # 3. 自动设置项目空间
        project_space = await self._create_project_space(project_idea, recommended_team)

        # 4. 智能分配角色
        role_assignments = self._assign_smart_roles(recommended_team, requirements)

        # 5. 生成项目计划
        project_plan = self._generate_ai_project_plan(requirements, recommended_team)

        # 6. 启动项目协作
        collaboration_links = self._setup_collaboration_tools(project_space, recommended_team)

        return {
            "project_id": project_space["id"],
            "team": recommended_team,
            "roles": role_assignments,
            "plan": project_plan,
            "collaboration_links": collaboration_links,
            "success_metrics": self._define_success_metrics(project_idea)
        }

    async def _ai_analyze_requirements(self, project_idea: dict) -> dict:
        """AI分析项目需求"""
        return {
            "skills_needed": ["python", "frontend", "ui_design"],
            "team_size": 4,
            "estimated_duration": "3个月",
            "complexity": "medium"
        }

    def _match_team_members(self, requirements: dict, initiator: dict) -> List[dict]:
        """匹配团队成员"""
        # 简化实现
        return [
            {"user_id": initiator.get("id"), "role": "lead", "match_score": 1.0}
        ]

    async def _create_project_space(self, project_idea: dict, team: List[dict]) -> dict:
        """创建项目空间"""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        self.projects[project_id] = {
            "id": project_id,
            "name": project_idea.get("name", "未命名项目"),
            "description": project_idea.get("description", ""),
            "team": team,
            "channels": ["general", "development", "design"],
            "status": "planning"
        }
        return self.projects[project_id]

    def _assign_smart_roles(self, team: List[dict], requirements: dict) -> dict:
        """分配角色"""
        return {
            member["user_id"]: {
                "role": member.get("role", "member"),
                "responsibilities": ["开发"]
            }
            for member in team
        }

    def _generate_ai_project_plan(self, requirements: dict, team: List[dict]) -> dict:
        """生成AI项目计划"""
        return {
            "phases": [
                {"name": "需求分析", "duration": "2周"},
                {"name": "设计", "duration": "2周"},
                {"name": "开发", "duration": "8周"},
                {"name": "测试", "duration": "2周"}
            ],
            "milestones": [
                {"name": "Alpha版本", "date": "6周后"},
                {"name": "Beta版本", "date": "12周后"}
            ]
        }

    def _setup_collaboration_tools(self, project_space: dict, team: List[dict]) -> dict:
        """设置协作工具"""
        return {
            "code_repo": f"/projects/{project_space['id']}/repo",
            "doc_wiki": f"/projects/{project_space['id']}/wiki",
            "chat_channel": f"/projects/{project_space['id']}/chat",
            "kanban_board": f"/projects/{project_space['id']}/board"
        }

    def _define_success_metrics(self, project_idea: dict) -> dict:
        """定义成功指标"""
        return {
            "delivery_time": "按期交付率 > 90%",
            "quality": "缺陷密度 < 1/千行",
            "team_satisfaction": "团队满意度 > 4.5/5"
        }


# ============================================================
# 企业记忆系统
# ============================================================

class EnterpriseMemorySystem:
    """企业记忆系统"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.decisions: Dict[str, EnterpriseDecision] = {}

    async def record_decision(self, decision: dict, context: dict) -> str:
        """记录企业决策"""
        decision_entry = EnterpriseDecision(
            id=f"dec_{uuid.uuid4().hex[:12]}",
            title=decision.get("title", ""),
            description=decision.get("description", ""),
            context=context,
            participants=decision.get("participants", []),
            decision=decision.get("decision", ""),
            expected_outcome=decision.get("expected_outcome"),
            tags=decision.get("tags", []),
            review_date=decision.get("review_date")
        )

        self.decisions[decision_entry.id] = decision_entry

        # 设置复查提醒
        if decision_entry.review_date:
            await self._schedule_decision_review(decision_entry.id, decision_entry.review_date)

        return decision_entry.id

    async def _schedule_decision_review(self, decision_id: str, review_date: datetime):
        """安排决策复查"""
        pass

    async def recall_similar_decisions(self, current_situation: dict) -> dict:
        """回忆类似决策"""
        # 语义搜索历史决策
        similar = self._semantic_search_decisions(current_situation)

        # AI分析历史结果
        insights = await self._ai_analyze_historical_outcomes(similar)

        # 生成建议
        recommendations = self._generate_recommendations(insights, current_situation)

        return {
            "similar_past_cases": [d.to_dict() for d in similar],
            "historical_insights": insights,
            "recommendations": recommendations,
            "confidence": self._calculate_recommendation_confidence(insights)
        }

    def _semantic_search_decisions(self, situation: dict) -> List[EnterpriseDecision]:
        """语义搜索决策"""
        # 简化实现：基于标签匹配
        tags = situation.get("tags", [])
        results = []

        for decision in self.decisions.values():
            if any(tag in decision.tags for tag in tags):
                results.append(decision)

        return results

    async def _ai_analyze_historical_outcomes(self, decisions: List[EnterpriseDecision]) -> dict:
        """AI分析历史成果"""
        return {
            "success_rate": 0.75,
            "common_patterns": ["需求变更频繁", "团队沟通不足"],
            "lessons_learned": ["早期风险评估很重要"]
        }

    def _generate_recommendations(self, insights: dict, current_situation: dict) -> List[str]:
        """生成建议"""
        recommendations = []

        if insights.get("success_rate", 0) < 0.8:
            recommendations.append("建议加强项目风险管控")

        for pattern in insights.get("common_patterns", []):
            if "需求变更" in pattern:
                recommendations.append("建议实施需求变更管理流程")

        return recommendations

    def _calculate_recommendation_confidence(self, insights: dict) -> float:
        """计算建议置信度"""
        return min(1.0, len(insights.get("lessons_learned", [])) / 5)


# ============================================================
# 企业数字孪生
# ============================================================

class EnterpriseDigitalTwin:
    """企业数字孪生"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.twin_state: Optional[DigitalTwinState] = None

    async def update_twin(self, real_world_data: dict) -> DigitalTwinState:
        """更新数字孪生状态"""
        self.twin_state = DigitalTwinState(
            enterprise_id=self.enterprise_id,
            organization=real_world_data.get("org_structure", {}),
            projects=real_world_data.get("active_projects", []),
            knowledge=real_world_data.get("knowledge_base", {}),
            collaboration_network=real_world_data.get("collab_graph", {}),
            health_metrics=await self._analyze_enterprise_health(real_world_data)
        )

        return self.twin_state

    async def _analyze_enterprise_health(self, data: dict) -> dict:
        """分析企业健康度"""
        return {
            "overall_score": 0.85,
            "dimensions": {
                "financial": 0.90,
                "operational": 0.82,
                "organizational": 0.88,
                "innovation": 0.75
            },
            "risks": [],
            "opportunities": ["数字化转型加速", "团队协作增强"]
        }

    async def simulate_scenario(self, scenario: dict) -> dict:
        """模拟企业决策场景"""
        # 1. 复制当前状态
        simulation_state = self._copy_state()

        # 2. 应用场景变化
        self._apply_scenario_changes(simulation_state, scenario)

        # 3. AI模拟结果
        simulation_results = await self._ai_simulate_outcomes(simulation_state)

        # 4. 生成影响报告
        impact_report = self._generate_impact_report(simulation_results)

        # 5. 提供决策建议
        recommendations = self._generate_simulation_recommendations(impact_report)

        return {
            "simulation_id": f"sim_{uuid.uuid4().hex[:12]}",
            "scenario": scenario,
            "results": simulation_results,
            "impact_report": impact_report,
            "recommendations": recommendations,
            "confidence": self._calculate_simulation_confidence()
        }

    def _copy_state(self) -> dict:
        """复制当前状态"""
        if not self.twin_state:
            return {}
        return {
            "organization": self.twin_state.organization.copy(),
            "projects": self.twin_state.projects.copy(),
            "knowledge": self.twin_state.knowledge.copy(),
            "collaboration_network": self.twin_state.collaboration_network.copy()
        }

    def _apply_scenario_changes(self, state: dict, scenario: dict):
        """应用场景变化"""
        pass

    async def _ai_simulate_outcomes(self, state: dict) -> dict:
        """AI模拟结果"""
        return {
            "predicted_metrics": {
                "efficiency": 0.92,
                "cost": -0.05,
                "satisfaction": 0.88
            },
            "timeline": [
                {"month": 1, "metrics": {"efficiency": 0.85}},
                {"month": 3, "metrics": {"efficiency": 0.90}},
                {"month": 6, "metrics": {"efficiency": 0.92}}
            ]
        }

    def _generate_impact_report(self, results: dict) -> dict:
        """生成影响报告"""
        return {
            "positive_impacts": ["效率提升5%", "员工满意度提高"],
            "negative_impacts": [],
            "neutral_impacts": ["短期调整成本"]
        }

    def _generate_simulation_recommendations(self, impact_report: dict) -> List[str]:
        """生成模拟建议"""
        recommendations = []

        for positive in impact_report.get("positive_impacts", []):
            recommendations.append(f"✓ {positive}")

        return recommendations

    def _calculate_simulation_confidence(self) -> float:
        """计算模拟置信度"""
        return 0.85

    def get_twin_state(self) -> Optional[DigitalTwinState]:
        """获取孪生状态"""
        return self.twin_state


# ============================================================
# 全局实例管理
# ============================================================

_enterprise_switcher: Optional[EnterpriseModeSwitcher] = None
_enterprise_stores: Dict[str, dict] = {}


def get_enterprise_switcher() -> EnterpriseModeSwitcher:
    """获取企业模式切换器"""
    global _enterprise_switcher
    if _enterprise_switcher is None:
        _enterprise_switcher = EnterpriseModeSwitcher()
    return _enterprise_switcher


def get_enterprise_store(enterprise_id: str) -> dict:
    """获取企业存储"""
    if enterprise_id not in _enterprise_stores:
        _enterprise_stores[enterprise_id] = {
            "org_structure": DynamicOrgStructure(enterprise_id),
            "role_assignment": SmartRoleAssignment(),
            "publish_control": EnterprisePublishControl(enterprise_id),
            "invite_approval": ExternalInviteApproval(enterprise_id),
            "message_router": IntelligentMessageRouter(enterprise_id),
            "knowledge_graph": EnterpriseKnowledgeGraph(enterprise_id),
            "project_self_org": SmartProjectSelfOrg(enterprise_id),
            "memory_system": EnterpriseMemorySystem(enterprise_id),
            "digital_twin": EnterpriseDigitalTwin(enterprise_id)
        }
    return _enterprise_stores[enterprise_id]


# ============================================================
# 企业权限管理系统
# ============================================================

class EnterprisePermissionManager:
    """企业权限管理系统"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.admins: Dict[str, dict] = {}  # admin_id -> admin_info
        self.role_permissions: Dict[str, List[EnterprisePermission]] = {}
        self.user_roles: Dict[str, str] = {}  # user_id -> role
        self._init_default_permissions()

    def _init_default_permissions(self):
        """初始化默认权限"""
        # 高管权限
        self.role_permissions["executive"] = [
            EnterprisePermission.VIEW_ORG,
            EnterprisePermission.EDIT_ORG,
            EnterprisePermission.MANAGE_DEPARTMENTS,
            EnterprisePermission.INVITE_MEMBER,
            EnterprisePermission.REMOVE_MEMBER,
            EnterprisePermission.APPROVE_JOIN,
            EnterprisePermission.MANAGE_ADMINS,
            EnterprisePermission.MANAGE_PERMISSIONS,
            EnterprisePermission.TRANSFER_OWNERSHIP,
            EnterprisePermission.EDIT_SETTINGS,
            EnterprisePermission.DELETE_ENTERPRISE,
            EnterprisePermission.PUBLISH_ANNOUNCEMENT,
            EnterprisePermission.INITIATE_VOTE,
            EnterprisePermission.CAST_VOTE,
        ]

        # 部门负责人权限
        self.role_permissions["department_head"] = [
            EnterprisePermission.VIEW_ORG,
            EnterprisePermission.EDIT_ORG,
            EnterprisePermission.MANAGE_DEPARTMENTS,
            EnterprisePermission.INVITE_MEMBER,
            EnterprisePermission.APPROVE_JOIN,
            EnterprisePermission.PUBLISH_ANNOUNCEMENT,
            EnterprisePermission.PUBLISH_DEPARTMENT,
            EnterprisePermission.INITIATE_VOTE,
            EnterprisePermission.CAST_VOTE,
        ]

        # 团队领导权限
        self.role_permissions["team_lead"] = [
            EnterprisePermission.VIEW_ORG,
            EnterprisePermission.PUBLISH_DEPARTMENT,
            EnterprisePermission.INITIATE_VOTE,
            EnterprisePermission.CAST_VOTE,
        ]

        # 普通员工权限
        self.role_permissions["employee"] = [
            EnterprisePermission.VIEW_ORG,
            EnterprisePermission.CAST_VOTE,
        ]

        # 外部协作者权限
        self.role_permissions["contractor"] = [
            EnterprisePermission.VIEW_ORG,
        ]

    async def add_admin(self, user_id: str, admin_type: str = "admin") -> dict:
        """添加管理员"""
        if user_id in self.admins:
            return {"success": False, "error": "已是管理员"}

        admin_info = {
            "user_id": user_id,
            "admin_type": admin_type,  # admin/super_admin
            "permissions": self._get_admin_permissions(admin_type),
            "appointed_by": None,  # 任命人
            "appointed_at": datetime.now().isoformat(),
            "can_manage_org": admin_type == "super_admin",
            "can_manage_admins": admin_type == "super_admin",
            "can_delete_enterprise": admin_type == "super_admin"
        }

        self.admins[user_id] = admin_info

        return {
            "success": True,
            "admin": admin_info
        }

    def _get_admin_permissions(self, admin_type: str) -> List[EnterprisePermission]:
        """获取管理员权限"""
        if admin_type == "super_admin":
            return self.role_permissions["executive"]
        return [
            EnterprisePermission.VIEW_ORG,
            EnterprisePermission.EDIT_ORG,
            EnterprisePermission.MANAGE_DEPARTMENTS,
            EnterprisePermission.INVITE_MEMBER,
            EnterprisePermission.APPROVE_JOIN,
            EnterprisePermission.PUBLISH_ANNOUNCEMENT,
        ]

    async def remove_admin(self, user_id: str, removed_by: str) -> dict:
        """移除管理员"""
        if user_id not in self.admins:
            return {"success": False, "error": "不是管理员"}

        if self.admins[user_id]["admin_type"] == "super_admin":
            return {"success": False, "error": "无法移除超级管理员"}

        removed_admin = self.admins.pop(user_id)
        removed_admin["removed_by"] = removed_by
        removed_admin["removed_at"] = datetime.now().isoformat()

        return {
            "success": True,
            "removed_admin": removed_admin
        }

    def is_admin(self, user_id: str) -> bool:
        """检查是否是管理员"""
        return user_id in self.admins

    def is_super_admin(self, user_id: str) -> bool:
        """检查是否是超级管理员"""
        return self.admins.get(user_id, {}).get("admin_type") == "super_admin"

    def has_permission(self, user_id: str, permission: EnterprisePermission) -> bool:
        """检查用户是否有特定权限"""
        # 超级管理员拥有所有权限
        if self.is_super_admin(user_id):
            return True

        # 检查是否是管理员
        if self.is_admin(user_id):
            admin_info = self.admins.get(user_id, {})
            return permission in admin_info.get("permissions", [])

        # 检查角色权限
        role = self.user_roles.get(user_id)
        if role and role in self.role_permissions:
            return permission in self.role_permissions[role]

        return False

    def require_permission(self, user_id: str, permission: EnterprisePermission) -> dict:
        """要求用户有特定权限，否则抛出异常"""
        if not self.has_permission(user_id, permission):
            return {
                "success": False,
                "error": f"权限不足: 需要 {permission.value}",
                "required_permission": permission.value
            }
        return {"success": True}

    async def edit_org_structure(self, user_id: str, changes: dict) -> dict:
        """编辑组织架构（需要EDIT_ORG权限）"""
        # 检查权限
        perm_check = self.require_permission(user_id, EnterprisePermission.EDIT_ORG)
        if not perm_check["success"]:
            return perm_check

        # 执行修改
        return {
            "success": True,
            "changes": changes,
            "editor": user_id,
            "timestamp": datetime.now().isoformat()
        }

    async def transfer_ownership(self, current_owner: str, new_owner: str) -> dict:
        """转让所有权（只有超级管理员可以操作）"""
        if not self.is_super_admin(current_owner):
            return {"success": False, "error": "只有超级管理员可以转让所有权"}

        return {
            "success": True,
            "previous_owner": current_owner,
            "new_owner": new_owner,
            "timestamp": datetime.now().isoformat()
        }

    def get_admins(self) -> List[dict]:
        """获取所有管理员"""
        return list(self.admins.values())

    def get_user_role(self, user_id: str) -> Optional[str]:
        """获取用户角色"""
        return self.user_roles.get(user_id)

    async def assign_role(self, user_id: str, role: str, assigned_by: str) -> dict:
        """分配角色"""
        if role not in self.role_permissions:
            return {"success": False, "error": "无效的角色"}

        self.user_roles[user_id] = role

        return {
            "success": True,
            "user_id": user_id,
            "role": role,
            "assigned_by": assigned_by
        }


# ============================================================
# 企业撤销投票系统
# ============================================================

class EnterpriseRevokeVoting:
    """企业撤销投票系统"""

    def __init__(self, enterprise_id: str):
        self.enterprise_id = enterprise_id
        self.active_votes: Dict[str, dict] = {}
        self.vote_history: List[dict] = []

    async def initiate_revoke_vote(self, initiator_id: str, reason: str,
                                   enterprise_members: List[str]) -> dict:
        """发起企业撤销投票"""
        vote_id = f"vote_{uuid.uuid4().hex[:12]}"

        # 计算投票阈值：2/3多数
        total_members = len(enterprise_members)
        required_approval = int(total_members * 2 / 3) + 1

        vote = {
            "vote_id": vote_id,
            "vote_type": VoteType.ENTERPRISE_REVOKE,
            "initiator_id": initiator_id,
            "reason": reason,
            "status": VoteStatus.PENDING,
            "total_eligible_voters": total_members,
            "required_approval": required_approval,
            "current_approvals": 0,
            "current_rejections": 0,
            "voters": [],  # 已投票的人
            "voter_details": [],  # 投票详情
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),  # 7天投票期
            "enterprise_members": enterprise_members
        }

        self.active_votes[vote_id] = vote

        return {
            "success": True,
            "vote": vote
        }

    async def cast_vote(self, vote_id: str, voter_id: str, approve: bool,
                       reason: str = "") -> dict:
        """投票"""
        vote = self.active_votes.get(vote_id)
        if not vote:
            return {"success": False, "error": "投票不存在"}

        if vote["status"] != VoteStatus.PENDING:
            return {"success": False, "error": "投票已结束"}

        if voter_id in vote["voters"]:
            return {"success": False, "error": "已投过票"}

        if voter_id not in vote["enterprise_members"]:
            return {"success": False, "error": "无投票权"}

        # 记录投票
        vote["voters"].append(voter_id)
        vote["voter_details"].append({
            "voter_id": voter_id,
            "vote": "approve" if approve else "reject",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })

        if approve:
            vote["current_approvals"] += 1
        else:
            vote["current_rejections"] += 1

        # 检查是否达成撤销条件
        if vote["current_approvals"] >= vote["required_approval"]:
            vote["status"] = VoteStatus.APPROVED
            vote["approved_at"] = datetime.now().isoformat()
            return {
                "success": True,
                "vote_result": "approved",
                "message": "企业撤销投票通过"
            }

        if len(vote["voters"]) >= vote["total_eligible_voters"]:
            vote["status"] = VoteStatus.REJECTED
            vote["rejected_at"] = datetime.now().isoformat()
            return {
                "success": True,
                "vote_result": "rejected",
                "message": "企业撤销投票被拒绝"
            }

        return {
            "success": True,
            "vote_result": "pending",
            "current_approvals": vote["current_approvals"],
            "required_approvals": vote["required_approval"]
        }

    async def check_vote_status(self, vote_id: str) -> dict:
        """检查投票状态"""
        vote = self.active_votes.get(vote_id)
        if not vote:
            return {"error": "投票不存在"}

        # 检查是否过期
        if datetime.now() > vote["expires_at"]:
            vote["status"] = VoteStatus.EXPIRED

        return {
            "vote_id": vote_id,
            "status": vote["status"].value if isinstance(vote["status"], VoteStatus) else vote["status"],
            "current_approvals": vote["current_approvals"],
            "current_rejections": vote["current_rejections"],
            "required_approval": vote["required_approval"],
            "voter_count": len(vote["voters"]),
            "total_eligible": vote["total_eligible_voters"],
            "remaining_votes": vote["total_eligible_voters"] - len(vote["voters"])
        }

    async def execute_revoke(self, vote_id: str) -> dict:
        """执行企业撤销"""
        vote = self.active_votes.get(vote_id)
        if not vote:
            return {"success": False, "error": "投票不存在"}

        if vote["status"] != VoteStatus.APPROVED:
            return {"success": False, "error": "投票未通过"}

        # 记录历史
        self.vote_history.append({
            "vote_id": vote_id,
            "enterprise_id": self.enterprise_id,
            "result": "revoked",
            "executed_at": datetime.now().isoformat(),
            "total_approvals": vote["current_approvals"],
            "total_rejections": vote["current_rejections"]
        })

        return {
            "success": True,
            "message": "企业已被撤销",
            "vote_id": vote_id
        }

    def get_active_votes(self) -> List[dict]:
        """获取活跃投票"""
        return [
            {**v, "status": v["status"].value if isinstance(v["status"], VoteStatus) else v["status"]}
            for v in self.active_votes.values()
        ]


# ============================================================
# IDE代码快照系统（测试模式）
# ============================================================

class IDECodeSnapshot:
    """IDE代码快照系统"""

    def __init__(self):
        self.snapshots: Dict[str, dict] = {}  # snapshot_id -> snapshot
        self.current_focus: Optional[dict] = None

    async def capture_focus_window_snapshot(self, window_info: dict,
                                           code_content: str) -> dict:
        """捕获焦点窗口代码快照"""
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"

        snapshot = {
            "snapshot_id": snapshot_id,
            "window_info": {
                "hwnd": window_info.get("hwnd"),
                "title": window_info.get("title"),
                "class_name": window_info.get("class_name"),
                "process_name": window_info.get("process_name")
            },
            "code_content": code_content,
            "content_hash": hashlib.sha256(code_content.encode()).hexdigest()[:16],
            "language": self._detect_language(window_info.get("title", "")),
            "line_count": len(code_content.splitlines()),
            "captured_at": datetime.now(),
            "captured_in_test_mode": True
        }

        self.snapshots[snapshot_id] = snapshot
        self.current_focus = snapshot

        return {
            "success": True,
            "snapshot": snapshot
        }

    def _detect_language(self, title: str) -> str:
        """检测语言"""
        title_lower = title.lower()

        if ".py" in title_lower:
            return "python"
        elif ".js" in title_lower or ".ts" in title_lower:
            return "javascript"
        elif ".java" in title_lower:
            return "java"
        elif ".cpp" in title_lower or ".cc" in title_lower:
            return "cpp"
        elif ".cs" in title_lower:
            return "csharp"
        elif ".go" in title_lower:
            return "go"
        elif ".rs" in title_lower:
            return "rust"
        elif ".rb" in title_lower:
            return "ruby"
        elif ".php" in title_lower:
            return "php"
        elif ".swift" in title_lower:
            return "swift"
        elif ".kt" in title_lower:
            return "kotlin"
        elif ".html" in title_lower:
            return "html"
        elif ".css" in title_lower:
            return "css"
        elif ".sql" in title_lower:
            return "sql"
        elif ".sh" in title_lower:
            return "shell"
        else:
            return "unknown"

    async def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        """获取快照"""
        return self.snapshots.get(snapshot_id)

    async def get_current_focus_snapshot(self) -> Optional[dict]:
        """获取当前焦点快照"""
        return self.current_focus

    async def compare_snapshots(self, snapshot_a: str, snapshot_b: str) -> dict:
        """比较两个快照"""
        snap_a = self.snapshots.get(snapshot_a)
        snap_b = self.snapshots.get(snapshot_b)

        if not snap_a or not snap_b:
            return {"error": "快照不存在"}

        # 计算差异
        lines_a = snap_a["code_content"].splitlines()
        lines_b = snap_b["code_content"].splitlines()

        # 简单差异计算
        added = len([l for l in lines_b if l not in lines_a])
        removed = len([l for l in lines_a if l not in lines_b])

        return {
            "snapshot_a": snapshot_a,
            "snapshot_b": snapshot_b,
            "changes": {
                "lines_added": added,
                "lines_removed": removed,
                "net_change": added - removed
            },
            "comparison_time": datetime.now().isoformat()
        }

    def list_snapshots(self, limit: int = 20) -> List[dict]:
        """列出快照"""
        snapshots = sorted(
            self.snapshots.values(),
            key=lambda x: x["captured_at"],
            reverse=True
        )
        return [
            {
                "snapshot_id": s["snapshot_id"],
                "title": s["window_info"]["title"],
                "language": s["language"],
                "line_count": s["line_count"],
                "captured_at": s["captured_at"].isoformat()
            }
            for s in snapshots[:limit]
        ]


# ============================================================
# 导出
# ============================================================

__all__ = [
    # 枚举
    "AuthLevel", "Role", "PublishChannel", "PublishPriority",
    "InviteStatus", "NotificationPriority", "NotificationStatus",
    "EnterprisePermission", "VoteType", "VoteStatus",

    # 数据模型
    "User", "Enterprise", "OrgNode", "Permission",
    "InviteRequest", "PublishContent", "Notification",
    "KnowledgeNode", "EnterpriseDecision", "DigitalTwinState",

    # 核心类
    "EnterpriseModeSwitcher", "DynamicOrgStructure",
    "SmartRoleAssignment", "EnterprisePublishControl",
    "ExternalInviteApproval", "IntelligentMessageRouter",
    "EnterpriseKnowledgeGraph", "SmartProjectSelfOrg",
    "EnterpriseMemorySystem", "EnterpriseDigitalTwin",
    "PermissionGraph",
    "EnterprisePermissionManager",
    "EnterpriseRevokeVoting",
    "IDECodeSnapshot",

    # 全局函数
    "get_enterprise_switcher", "get_enterprise_store",
]