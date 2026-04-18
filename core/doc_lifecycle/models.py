"""
数据模型
DocLifecycle 数据模型定义
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class DocumentType(Enum):
    """文档类型"""
    UNKNOWN = "unknown"
    TEXT = "text"          # 纯文本
    MARKDOWN = "markdown"  # Markdown
    PDF = "pdf"            # PDF文档
    DOC = "doc"            # Word文档
    DOCX = "docx"          # Word文档
    XLS = "xls"            # Excel
    XLSX = "xlsx"          # Excel
    PPT = "ppt"            # PowerPoint
    PPTX = "pptx"          # PowerPoint
    CSV = "csv"            # CSV数据
    JSON = "json"          # JSON数据
    XML = "xml"            # XML数据
    HTML = "html"          # HTML
    CODE = "code"          # 代码文件
    IMAGE = "image"        # 图片
    ARCHIVE = "archive"    # 压缩包


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewLevel(Enum):
    """审核级别"""
    QUICK = "quick"        # 快速审核
    STANDARD = "standard" # 标准审核
    DEEP = "deep"         # 深度审核
    PROFESSIONAL = "professional"  # 专业审核


class FileTier(Enum):
    """文件存储层"""
    ACTIVE = "active"      # 活跃层
    STORAGE = "storage"    # 存储层
    ARCHIVE = "archive"    # 归档层


class ActivityLevel(Enum):
    """活跃度等级"""
    HIGH = "high"          # 高活跃度 (80-100)
    MEDIUM_HIGH = "medium_high"  # 中高活跃度 (60-79)
    MEDIUM = "medium"      # 中活跃度 (40-59)
    LOW = "low"           # 低活跃度 (20-39)
    INACTIVE = "inactive"  # 非活跃 (0-19)


class CleanupStatus(Enum):
    """清理状态"""
    NORMAL = "normal"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"
    COMPRESSED = "compressed"
    DELETED = "deleted"
    RECOVERABLE = "recoverable"


@dataclass
class DocumentInfo:
    """文档信息"""
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    file_name: str = ""
    file_type: DocumentType = DocumentType.UNKNOWN
    file_size: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    hash_value: str = ""  # 文件内容哈希
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "hash_value": self.hash_value,
            "metadata": self.metadata
        }


@dataclass
class ReviewTask:
    """审核任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = ""
    doc_info: Optional[DocumentInfo] = None
    review_level: ReviewLevel = ReviewLevel.STANDARD
    status: ReviewStatus = ReviewStatus.PENDING
    priority: int = 5  # 1-10, 10最高
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    result: Optional[Dict[str, Any]] = None
    progress: float = 0.0  # 0.0 - 1.0
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "doc_id": self.doc_id,
            "review_level": self.review_level.value,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "retry_count": self.retry_count
        }


@dataclass
class ReviewResult:
    """审核结果"""
    task_id: str = ""
    doc_id: str = ""
    quality_score: float = 0.0  # 0-100
    accuracy_score: float = 0.0  # 准确性
    completeness_score: float = 0.0  # 完整性
    consistency_score: float = 0.0  # 一致性
    clarity_score: float = 0.0  # 清晰度
    professionalism_score: float = 0.0  # 专业性
    innovation_score: float = 0.0  # 创新性
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    category: str = ""  # 文档分类
    tags: List[str] = field(default_factory=list)
    summary: str = ""
    processing_time: float = 0.0  # 处理时间(秒)
    created_at: datetime = field(default_factory=datetime.now)
    
    # 敏感词相关
    sensitive_words_found: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "doc_id": self.doc_id,
            "quality_score": self.quality_score,
            "accuracy_score": self.accuracy_score,
            "completeness_score": self.completeness_score,
            "consistency_score": self.consistency_score,
            "clarity_score": self.clarity_score,
            "professionalism_score": self.professionalism_score,
            "innovation_score": self.innovation_score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "category": self.category,
            "tags": self.tags,
            "summary": self.summary,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat(),
            "sensitive_words_found": self.sensitive_words_found,
            "risk_level": self.risk_level
        }


@dataclass
class ReportInfo:
    """报告信息"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    doc_id: str = ""
    report_type: str = "single"  # single, batch, summary, comparison
    report_format: str = "html"  # html, pdf, word, excel, json
    file_path: str = ""
    file_size: int = 0
    title: str = ""
    download_count: int = 0
    active_score: float = 100.0  # 活跃度评分
    retention_policy: str = "default"
    clean_status: CleanupStatus = CleanupStatus.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    last_access: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "doc_id": self.doc_id,
            "report_type": self.report_type,
            "report_format": self.report_format,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "title": self.title,
            "download_count": self.download_count,
            "active_score": self.active_score,
            "retention_policy": self.retention_policy,
            "clean_status": self.clean_status.value,
            "created_at": self.created_at.isoformat(),
            "last_access": self.last_access.isoformat()
        }


@dataclass
class FileActivity:
    """文件活跃度信息"""
    file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    file_type: DocumentType = DocumentType.UNKNOWN
    tier: FileTier = FileTier.ACTIVE
    
    # 活跃度评分因素
    access_frequency_score: float = 0.0  # 访问频率分 (25%)
    recent_access_score: float = 0.0     # 最近访问分 (25%)
    user_mark_score: float = 0.0         # 用户标记分 (20%)
    relevance_score: float = 0.0        # 关联性分 (15%)
    importance_score: float = 0.0       # 重要性分 (15%)
    
    total_score: float = 0.0           # 总分
    activity_level: ActivityLevel = ActivityLevel.HIGH
    
    # 关联信息
    project_ids: List[str] = field(default_factory=list)
    referenced_by: List[str] = field(default_factory=list)
    user_tags: List[str] = field(default_factory=list)
    is_starred: bool = False
    is_critical: bool = False
    
    # 时间信息
    last_access: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    # 清理信息
    cleanup_status: CleanupStatus = CleanupStatus.NORMAL
    cleanup_scheduled_at: Optional[datetime] = None
    cleanup_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def calculate_total_score(self) -> float:
        """计算总活跃度评分"""
        self.total_score = (
            self.access_frequency_score * 0.25 +
            self.recent_access_score * 0.25 +
            self.user_mark_score * 0.20 +
            self.relevance_score * 0.15 +
            self.importance_score * 0.15
        )
        
        # 确定活跃度等级
        if self.total_score >= 80:
            self.activity_level = ActivityLevel.HIGH
        elif self.total_score >= 60:
            self.activity_level = ActivityLevel.MEDIUM_HIGH
        elif self.total_score >= 40:
            self.activity_level = ActivityLevel.MEDIUM
        elif self.total_score >= 20:
            self.activity_level = ActivityLevel.LOW
        else:
            self.activity_level = ActivityLevel.INACTIVE
            
        return self.total_score
    
    def get_cleanup_action(self) -> str:
        """获取建议的清理操作"""
        if self.activity_level == ActivityLevel.HIGH:
            return "keep"  # 不清理
        elif self.activity_level == ActivityLevel.MEDIUM_HIGH:
            return "archive_after_180d"  # 180天后归档
        elif self.activity_level == ActivityLevel.MEDIUM:
            return "compress_after_90d"  # 90天后压缩归档
        elif self.activity_level == ActivityLevel.LOW:
            return "move_to_archive_after_30d"  # 30天后移动到归档区
        else:
            return "delete_after_7d"  # 7天后自动删除


@dataclass
class CleanupRule:
    """清理规则"""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    
    # 触发条件
    min_activity_score: float = 0.0  # 最小活跃度评分
    max_activity_score: float = 100.0  # 最大活跃度评分
    min_file_age_days: int = 0  # 最小文件年龄(天)
    max_file_size: int = 0  # 最大文件大小(字节), 0表示不限制
    
    # 文件类型过滤
    allowed_extensions: List[str] = field(default_factory=list)  # 空列表表示全部
    excluded_extensions: List[str] = field(default_factory=list)
    excluded_paths: List[str] = field(default_factory=list)  # 排除的路径
    
    # 操作
    action: str = "archive"  # keep, archive, compress, move, delete
    require_confirmation: bool = True
    notification_enabled: bool = True
    
    # 调度
    schedule_type: str = "daily"  # daily, weekly, monthly, manual
    schedule_time: str = "02:00"  # HH:MM
    notification_before_days: int = 7  # 提前多少天通知
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "min_activity_score": self.min_activity_score,
            "max_activity_score": self.max_activity_score,
            "min_file_age_days": self.min_file_age_days,
            "max_file_size": self.max_file_size,
            "allowed_extensions": self.allowed_extensions,
            "excluded_extensions": self.excluded_extensions,
            "excluded_paths": self.excluded_paths,
            "action": self.action,
            "require_confirmation": self.require_confirmation,
            "notification_enabled": self.notification_enabled,
            "schedule_type": self.schedule_type,
            "schedule_time": self.schedule_time,
            "notification_before_days": self.notification_before_days
        }


@dataclass
class CleanupTask:
    """清理任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    file_info: Optional[FileActivity] = None
    action: str = "archive"
    status: str = "pending"  # pending, approved, executing, completed, cancelled, failed
    result: str = ""
    space_freed: int = 0  # 释放的空间(字节)
    executed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: str = ""  # 审批人
    approved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "file_path": self.file_path,
            "action": self.action,
            "status": self.status,
            "result": self.result,
            "space_freed": self.space_freed,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class StorageStats:
    """存储统计"""
    total_space: int = 0
    used_space: int = 0
    available_space: int = 0
    active_space: int = 0
    storage_space: int = 0
    archive_space: int = 0
    
    total_files: int = 0
    active_files: int = 0
    storage_files: int = 0
    archive_files: int = 0
    
    cleanupable_space: int = 0
    cleanupable_files: int = 0
    
    last_cleanup: Optional[datetime] = None
    space_saved_by_cleanup: int = 0
    files_cleaned_count: int = 0
