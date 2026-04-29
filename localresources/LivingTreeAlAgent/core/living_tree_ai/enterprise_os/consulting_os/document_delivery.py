"""
文档交付管理模块

管理咨询项目的交付物，包括：
1. 文档版本管理
2. 文档状态流转
3. 审批流程
4. 文档关系
5. 交付包管理
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


# ==================== 枚举定义 ====================

class DocumentType(Enum):
    """文档类型"""
    # 环评类
    EIA_REPORT = "eia_report"           # 环境影响评价报告
    EIA_TABLE = "eia_table"             # 环境影响评价表
    EIA_APPENDIX = "eia_appendix"        # 环评附件

    # 可研类
    FEASIBILITY_STUDY = "feasibility_study"  # 可行性研究报告
    PROJECT_PROPOSAL = "project_proposal"   # 项目建议书
    PROJECT_APPRAISAL = "project_appraisal" # 项目申请报告

    # 安全类
    SAFETY_ASSESSMENT = "safety_assessment" # 安全评价报告
    SAFETY_PLAN = "safety_plan"             # 安全设施设计
    EMERGENCY_PLAN = "emergency_plan"       # 应急预案

    # 环保类
    POLLUTION_PERMIT_APPLICATION = "pollution_permit_application"  # 排污许可申请表
    MONITORING_PLAN = "monitoring_plan"     # 监测方案
    ACCEPTANCE_REPORT = "acceptance_report" # 验收报告
    ENVIRONMENTAL_REPORT = "environmental_report"  # 环境报告

    # 财务类
    QUOTATION = "quotation"               # 报价单
    CONTRACT = "contract"                 # 合同
    INVOICE = "invoice"                   # 发票

    # 其他
    TECHNICAL_SPEC = "technical_spec"     # 技术规格书
    DESIGN_DRAWING = "design_drawing"     # 设计图
    MEETING_MINUTES = "meeting_minutes"  # 会议纪要
    OTHER = "other"


class DocumentStatus(Enum):
    """文档状态"""
    DRAFT = "draft"                     # 草稿
    REVIEWING = "reviewing"             # 审核中
    REVISION = "revision"              # 修订中
    APPROVED = "approved"               # 已批准
    SUBMITTED = "submitted"             # 已提交
    ACCEPTED = "accepted"               # 客户已接受
    ARCHIVED = "archived"               # 已归档


class DocumentRelationType(Enum):
    """文档关系类型"""
    REFERENCES = "references"           # 引用（参考）
    DEPENDS_ON = "depends_on"           # 依赖
    UPDATED_FROM = "updated_from"       # 由...更新
    PART_OF = "part_of"                 # 组成部分
    RELATED = "related"                 # 相关


class ApprovalStatus(Enum):
    """审批状态"""
    PENDING = "pending"                 # 待审批
    APPROVED = "approved"               # 已批准
    REJECTED = "rejected"              # 已拒绝
    REVISION_REQUESTED = "revision_requested"  # 要求修改


class ApprovalLevel(Enum):
    """审批级别"""
    SELF_CHECK = "self_check"           # 自检
    PEER_REVIEW = "peer_review"         # 同级审核
    EXPERT_REVIEW = "expert_review"     # 专家审核
    PROJECT_MANAGER = "pm_review"       # 项目经理审核
    QUALITY_MANAGER = "qm_review"       # 质量经理审核
    DIRECTOR = "director_review"        # 总监审批
    FINAL_APPROVAL = "final_approval"   # 最终审批


# ==================== 数据模型 ====================

@dataclass
class DocumentVersion:
    """文档版本"""
    version_id: str
    version_number: str                   # 如 "v1.0", "v2.1"
    file_path: str = ""
    file_size: int = 0                  # 字节
    file_hash: str = ""                 # SHA256

    # 变更信息
    changes_summary: str = ""
    change_details: List[str] = field(default_factory=list)

    # 审核
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str = ""
    approved_at: Optional[datetime] = None

    # 元数据
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    comments: str = ""


@dataclass
class DocumentRelation:
    """文档关联"""
    relation_id: str
    source_doc_id: str                   # 源文档
    target_doc_id: str                   # 目标文档
    relation_type: DocumentRelationType

    # 关联说明
    description: str = ""
    auto_sync: bool = False             # 是否自动同步

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ApprovalRecord:
    """审批记录"""
    record_id: str
    approval_level: ApprovalLevel
    approver_id: str
    approver_name: str

    # 审批信息
    status: ApprovalStatus
    decision_at: Optional[datetime] = None

    # 意见
    comments: str = ""
    suggestions: List[str] = field(default_factory=list)

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReviewComment:
    """审核评论"""
    comment_id: str
    reviewer_id: str
    reviewer_name: str

    # 位置
    page_number: int = 0
    paragraph_id: str = ""
    selected_text: str = ""

    # 内容
    comment_type: str = "suggestion"     # suggestion/error/question/praise
    content: str = ""

    # 状态
    resolved: bool = False
    resolved_by: str = ""
    resolved_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Document:
    """
    文档

    咨询项目的交付物
    """
    doc_id: str
    doc_code: str                         # 文档编号

    # 基本信息
    name: str
    document_type: DocumentType
    description: str = ""

    # 所属
    project_id: str                      # 项目ID
    client_id: str = ""                  # 客户ID

    # 版本管理
    versions: List[DocumentVersion] = field(default_factory=list)
    current_version: str = "v0.1"
    version_count: int = 1

    # 状态
    status: DocumentStatus = DocumentStatus.DRAFT
    progress: float = 0.0                # 编写进度 0-100

    # 文档关系
    relations: List[DocumentRelation] = field(default_factory=list)

    # 审批流程
    approval_records: List[ApprovalRecord] = field(default_factory=list)
    current_approval_level: ApprovalLevel = ApprovalLevel.SELF_CHECK

    # 审核评论
    review_comments: List[ReviewComment] = field(default_factory=list)

    # 时间
    planned_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_submit_date: Optional[datetime] = None

    # 页数/规模
    page_count: int = 0
    word_count: int = 0

    # 标签
    tags: List[str] = field(default_factory=list)

    # 备注
    notes: str = ""

    # 客户确认
    client_confirmed: bool = False
    client_confirmed_by: str = ""
    client_confirmed_at: Optional[datetime] = None

    # 元数据
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DeliveryPackage:
    """交付包

    一次交付的文档集合
    """
    package_id: str
    package_code: str                     # 交付包编号

    # 基本信息
    name: str
    description: str = ""

    # 所属
    project_id: str
    client_id: str = ""

    # 文档列表
    documents: List[Dict] = field(default_factory=list)  # [{doc_id, doc_code, version}]

    # 状态
    status: str = "draft"               # draft/pending/submitted/accepted/rejected

    # 交付信息
    delivery_method: str = ""          # email/portal/physical
    delivery_date: Optional[datetime] = None
    recipient: str = ""

    # 签收
    signed: bool = False
    signed_by: str = ""
    signed_at: Optional[datetime] = None

    # 附件
    cover_letter: str = ""
    attachments: List[str] = field(default_factory=list)

    # 元数据
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ==================== 文档工作流 ====================

class DocumentWorkflow:
    """
    文档工作流

    管理文档状态流转和审批流程
    """

    # 状态流转规则
    STATUS_TRANSITIONS = {
        DocumentStatus.DRAFT: [DocumentStatus.REVIEWING],
        DocumentStatus.REVIEWING: [
            DocumentStatus.APPROVED,
            DocumentStatus.REVISION,
            DocumentStatus.DRAFT
        ],
        DocumentStatus.REVISION: [
            DocumentStatus.REVIEWING,
            DocumentStatus.APPROVED
        ],
        DocumentStatus.APPROVED: [DocumentStatus.SUBMITTED],
        DocumentStatus.SUBMITTED: [DocumentStatus.ACCEPTED],
        DocumentStatus.ACCEPTED: [DocumentStatus.ARCHIVED],
    }

    # 审批级别流程
    APPROVAL_FLOW_STANDARD = [
        ApprovalLevel.SELF_CHECK,
        ApprovalLevel.PEER_REVIEW,
        ApprovalLevel.EXPERT_REVIEW,
        ApprovalLevel.PROJECT_MANAGER,
        ApprovalLevel.QUALITY_MANAGER,
    ]

    APPROVAL_FLOW_SIMPLE = [
        ApprovalLevel.SELF_CHECK,
        ApprovalLevel.PROJECT_MANAGER,
    ]

    @classmethod
    def can_transition(
        cls,
        from_status: DocumentStatus,
        to_status: DocumentStatus
    ) -> bool:
        """检查状态是否可以流转"""
        return to_status in cls.STATUS_TRANSITIONS.get(from_status, [])

    @classmethod
    def get_available_transitions(
        cls,
        current_status: DocumentStatus
    ) -> List[DocumentStatus]:
        """获取可用的下一状态"""
        return cls.STATUS_TRANSITIONS.get(current_status, [])

    @classmethod
    def get_approval_flow(
        cls,
        document_type: DocumentType,
        project_type: str = None
    ) -> List[ApprovalLevel]:
        """获取审批流程"""
        # 根据文档类型确定审批级别
        if document_type in [
            DocumentType.EIA_REPORT,
            DocumentType.FEASIBILITY_STUDY,
            DocumentType.SAFETY_ASSESSMENT
        ]:
            return cls.APPROVAL_FLOW_STANDARD.copy()

        return cls.APPROVAL_FLOW_SIMPLE.copy()

    @classmethod
    def get_next_approval_level(
        cls,
        current_level: ApprovalLevel,
        document_type: DocumentType
    ) -> Optional[ApprovalLevel]:
        """获取下一审批级别"""
        flow = cls.get_approval_flow(document_type)

        try:
            idx = flow.index(current_level)
            if idx < len(flow) - 1:
                return flow[idx + 1]
        except ValueError:
            pass

        return None


# ==================== 文档服务 ====================

class DocumentService:
    """
    文档管理服务

    核心功能：
    1. 文档CRUD
    2. 版本管理
    3. 文档关系
    4. 审批流程
    5. 交付包管理
    """

    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._packages: Dict[str, DeliveryPackage] = {}
        self._code_counter = 0

    def _generate_doc_id(self) -> str:
        """生成文档ID"""
        return f"DOC:{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_doc_code(self, doc_type: DocumentType) -> str:
        """生成文档编号"""
        self._code_counter += 1
        type_prefix = {
            DocumentType.EIA_REPORT: "EIA",
            DocumentType.FEASIBILITY_STUDY: "FS",
            DocumentType.SAFETY_ASSESSMENT: "SA",
            DocumentType.POLLUTION_PERMIT_APPLICATION: "PPA",
            DocumentType.MONITORING_PLAN: "MP",
            DocumentType.EMERGENCY_PLAN: "EP",
        }.get(doc_type, "DOC")

        return f"{type_prefix}-{datetime.now().year}-{self._code_counter:04d}"

    async def create_document(
        self,
        name: str,
        document_type: DocumentType,
        project_id: str,
        created_by: str,
        description: str = "",
        client_id: str = "",
        tags: List[str] = None,
        **kwargs
    ) -> Document:
        """创建文档"""
        doc_id = self._generate_doc_id()
        doc_code = self._generate_doc_code(document_type)

        doc = Document(
            doc_id=doc_id,
            doc_code=doc_code,
            name=name,
            document_type=document_type,
            description=description,
            project_id=project_id,
            client_id=client_id,
            tags=tags or [],
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 初始化版本
        initial_version = DocumentVersion(
            version_id=f"{doc_id}:v0.1",
            version_number="v0.1",
            created_by=created_by
        )
        doc.versions.append(initial_version)

        # 设置审批流程
        doc.approval_records.append(ApprovalRecord(
            record_id=f"AR:{doc_id}:self",
            approval_level=ApprovalLevel.SELF_CHECK,
            approver_id=created_by,
            approver_name="创建者",
            status=ApprovalStatus.PENDING
        ))

        self._documents[doc_id] = doc
        return doc

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self._documents.get(doc_id)

    async def list_documents(
        self,
        project_id: str = None,
        document_type: DocumentType = None,
        status: DocumentStatus = None,
        client_id: str = None,
        tags: List[str] = None
    ) -> List[Document]:
        """列出文档"""
        results = list(self._documents.values())

        if project_id:
            results = [d for d in results if d.project_id == project_id]

        if document_type:
            results = [d for d in results if d.document_type == document_type]

        if status:
            results = [d for d in results if d.status == status]

        if client_id:
            results = [d for d in results if d.client_id == client_id]

        if tags:
            results = [
                d for d in results
                if any(tag in d.tags for tag in tags)
            ]

        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    async def update_document(
        self,
        doc_id: str,
        **updates
    ) -> Optional[Document]:
        """更新文档"""
        doc = self._documents.get(doc_id)
        if not doc:
            return None

        for key, value in updates.items():
            if hasattr(doc, key):
                setattr(doc, key, value)

        doc.updated_at = datetime.now()
        return doc

    async def transition_status(
        self,
        doc_id: str,
        to_status: DocumentStatus
    ) -> bool:
        """流转文档状态"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        if not DocumentWorkflow.can_transition(doc.status, to_status):
            return False

        # 如果是提交状态，记录提交时间
        if to_status == DocumentStatus.SUBMITTED:
            doc.actual_submit_date = datetime.now()

        doc.status = to_status
        doc.updated_at = datetime.now()
        return True

    async def add_version(
        self,
        doc_id: str,
        version_number: str,
        file_path: str = "",
        changes_summary: str = "",
        created_by: str = ""
    ) -> Optional[DocumentVersion]:
        """添加新版本"""
        doc = self._documents.get(doc_id)
        if not doc:
            return None

        # 生成版本ID
        version_id = f"{doc_id}:{version_number}"

        # 计算文件信息
        file_hash = ""
        file_size = 0

        version = DocumentVersion(
            version_id=version_id,
            version_number=version_number,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            changes_summary=changes_summary,
            created_by=created_by,
            created_at=datetime.now()
        )

        doc.versions.append(version)
        doc.current_version = version_number
        doc.version_count = len(doc.versions)
        doc.updated_at = datetime.now()

        return version

    async def add_relation(
        self,
        source_doc_id: str,
        target_doc_id: str,
        relation_type: DocumentRelationType,
        description: str = "",
        auto_sync: bool = False
    ) -> bool:
        """添加文档关系"""
        source_doc = self._documents.get(source_doc_id)
        if not source_doc:
            return False

        relation = DocumentRelation(
            relation_id=f"REL:{source_doc_id}:{target_doc_id}",
            source_doc_id=source_doc_id,
            target_doc_id=target_doc_id,
            relation_type=relation_type,
            description=description,
            auto_sync=auto_sync
        )

        source_doc.relations.append(relation)
        source_doc.updated_at = datetime.now()
        return True

    async def get_related_documents(
        self,
        doc_id: str,
        relation_type: DocumentRelationType = None
    ) -> List[Document]:
        """获取关联文档"""
        doc = self._documents.get(doc_id)
        if not doc:
            return []

        related_ids = []
        for rel in doc.relations:
            if relation_type is None or rel.relation_type == relation_type:
                related_ids.append(rel.target_doc_id)

        return [
            self._documents[did]
            for did in related_ids
            if did in self._documents
        ]

    async def submit_for_approval(
        self,
        doc_id: str,
        approval_level: ApprovalLevel,
        approver_id: str,
        approver_name: str
    ) -> bool:
        """提交审批"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        # 获取下一审批级别
        next_level = DocumentWorkflow.get_next_approval_level(
            approval_level,
            doc.document_type
        )

        if next_level:
            doc.current_approval_level = next_level

        # 添加审批记录
        record = ApprovalRecord(
            record_id=f"AR:{doc_id}:{approval_level.value}:{datetime.now().timestamp()}",
            approval_level=approval_level,
            approver_id=approver_id,
            approver_name=approver_name,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now()
        )

        doc.approval_records.append(record)
        doc.updated_at = datetime.now()
        return True

    async def approve(
        self,
        doc_id: str,
        approver_id: str,
        approver_name: str,
        comments: str = ""
    ) -> bool:
        """审批通过"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        # 找到待审批记录
        for record in reversed(doc.approval_records):
            if record.approver_id == approver_id and record.status == ApprovalStatus.PENDING:
                record.status = ApprovalStatus.APPROVED
                record.decision_at = datetime.now()
                record.comments = comments
                break

        # 检查是否完成所有审批
        flow = DocumentWorkflow.get_approval_flow(doc.document_type)
        completed_levels = [
            r.approval_level for r in doc.approval_records
            if r.status == ApprovalStatus.APPROVED
        ]

        if all(level in completed_levels for level in flow):
            doc.status = DocumentStatus.APPROVED

        doc.updated_at = datetime.now()
        return True

    async def add_review_comment(
        self,
        doc_id: str,
        reviewer_id: str,
        reviewer_name: str,
        content: str,
        comment_type: str = "suggestion",
        page_number: int = 0,
        paragraph_id: str = "",
        selected_text: str = ""
    ) -> bool:
        """添加审核评论"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        comment = ReviewComment(
            comment_id=f"CMT:{doc_id}:{datetime.now().timestamp()}",
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            content=content,
            comment_type=comment_type,
            page_number=page_number,
            paragraph_id=paragraph_id,
            selected_text=selected_text,
            created_at=datetime.now()
        )

        doc.review_comments.append(comment)
        doc.updated_at = datetime.now()
        return True

    # ==================== 交付包管理 ====================

    async def create_delivery_package(
        self,
        name: str,
        project_id: str,
        created_by: str,
        description: str = "",
        client_id: str = ""
    ) -> DeliveryPackage:
        """创建交付包"""
        package_id = f"PKG:{datetime.now().strftime('%Y%m%d%H%M%S')}"
        package_code = f"DEL-{datetime.now().year}-{len(self._packages) + 1:04d}"

        package = DeliveryPackage(
            package_id=package_id,
            package_code=package_code,
            name=name,
            description=description,
            project_id=project_id,
            client_id=client_id,
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self._packages[package_id] = package
        return package

    async def add_document_to_package(
        self,
        package_id: str,
        doc_id: str,
        version: str = None
    ) -> bool:
        """添加文档到交付包"""
        package = self._packages.get(package_id)
        if not package:
            return False

        doc = self._documents.get(doc_id)
        if not doc:
            return False

        package.documents.append({
            "doc_id": doc_id,
            "doc_code": doc.doc_code,
            "name": doc.name,
            "version": version or doc.current_version
        })

        package.updated_at = datetime.now()
        return True

    async def get_delivery_package(
        self,
        package_id: str
    ) -> Optional[DeliveryPackage]:
        """获取交付包"""
        return self._packages.get(package_id)

    async def get_project_documents_summary(
        self,
        project_id: str
    ) -> Dict:
        """获取项目文档汇总"""
        docs = await self.list_documents(project_id=project_id)

        summary = {
            "total": len(docs),
            "by_status": {},
            "by_type": {},
            "pending_approvals": 0,
            "ready_for_delivery": 0
        }

        for doc in docs:
            # 按状态统计
            status_key = doc.status.value
            summary["by_status"][status_key] = (
                summary["by_status"].get(status_key, 0) + 1
            )

            # 按类型统计
            type_key = doc.document_type.value
            summary["by_type"][type_key] = (
                summary["by_type"].get(type_key, 0) + 1
            )

            # 待审批
            if doc.status == DocumentStatus.REVIEWING:
                summary["pending_approvals"] += 1

            # 可交付
            if doc.status == DocumentStatus.APPROVED:
                summary["ready_for_delivery"] += 1

        return summary


# ==================== 单例模式 ====================

_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取文档服务单例"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
