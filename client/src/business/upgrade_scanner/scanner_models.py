# scanner_models.py — 升级扫描系统数据模型

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import hashlib
import json


# ============ 枚举定义 ============

class ScanSource(Enum):
    """扫描来源"""
    GITHUB = "github"
    Gitee = "gitee"
    LOCAL_CACHE = "local_cache"
    PRESET_HOT = "preset_hot"  # 离线兜底
    ALIYUN_MIRROR = "aliyun_mirror"
    TINGHUA_MIRROR = "tinghua_mirror"


class CompareDimension(Enum):
    """比对维度"""
    FEATURE_COVERAGE = "feature_coverage"     # 功能覆盖
    RFC_COMPATIBILITY = "rfc_compatibility"   # RFC兼容性
    MEMORY_FOOTPRINT = "memory_footprint"      # 内存占用
    LICENSE_COMPLIANCE = "license_compliance"  # 协议合规
    MAINTENANCE_STATUS = "maintenance_status" # 维护状态
    COMMUNITY活跃度 = "community_activity"     # 社区活跃度
    PERFORMANCE = "performance"               # 性能


class ReplacementDecision(Enum):
    """替换决策"""
    ADOPT = "adopt"           # 采用开源库
    KEEP_CUSTOM = "keep_custom"  # 保留自研
    WRAP_AND_ADOPT = "wrap_and_adopt"  # 封装后采用
    DEFER = "defer"           # 延后决策
    REJECT = "reject"         # 拒绝


class DataVersion(Enum):
    """数据版本"""
    V1 = "v1"  # 旧版格式
    V2 = "v2"  # 新版格式
    JSON = "json"
    JSONL = "jsonl"


class PatchLegacyStatus(Enum):
    """补丁遗留状态"""
    LEGACY_APPLIED = "legacy_applied"     # 已应用，标记为遗留
    LEGACY_REJECTED = "legacy_rejected"  # 已拒绝，标记为遗留
    PENDING_REVIEW = "pending_review"    # 待重审
    ACTIVE = "active"                   # 活动中
    MERGED = "merged"                   # 已合并到开源库


class MirrorSource(Enum):
    """镜像源"""
    GITHUB = "github"
    Gitee = "gitee"
    ALIYUN = "aliyun"
    TINGHUA = "tinghua"
    NJU = "nju"


# ============ 开源库扫描模型 ============

@dataclass
class LibraryInfo:
    """开源库信息"""
    name: str                          # 库名
    version: str                       # 当前版本
    source: ScanSource                  # 来源
    url: str                           # 项目URL
    description: str                   # 描述
    language: str = "Python"           # 语言
    license: str = "MIT"              # 协议
    stars: int = 0                    # Stars数
    forks: int = 0                    # Fork数
    issues: int = 0                   # Open Issues
    last_commit: Optional[str] = None  # 最后提交
    homepage: Optional[str] = None      # 官网
    categories: List[str] = field(default_factory=list)  # 分类
    tags: List[str] = field(default_factory=list)        # 标签

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source.value if isinstance(self.source, ScanSource) else self.source,
            "url": self.url,
            "description": self.description,
            "language": self.language,
            "license": self.license,
            "stars": self.stars,
            "forks": self.forks,
            "issues": self.issues,
            "last_commit": self.last_commit,
            "homepage": self.homepage,
            "categories": self.categories,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LibraryInfo":
        return cls(
            name=data["name"],
            version=data.get("version", "unknown"),
            source=ScanSource(data.get("source", "github")),
            url=data.get("url", ""),
            description=data.get("description", ""),
            language=data.get("language", "Python"),
            license=data.get("license", "MIT"),
            stars=data.get("stars", 0),
            forks=data.get("forks", 0),
            issues=data.get("issues", 0),
            last_commit=data.get("last_commit"),
            homepage=data.get("homepage"),
            categories=data.get("categories", []),
            tags=data.get("tags", []),
        )


@dataclass
class CompareResult:
    """比对结果"""
    dimension: CompareDimension           # 比对维度
    custom_score: float                  # 自研评分 (0-1)
    oss_score: float                    # 开源评分 (0-1)
    winner: str = ""                    # 胜者: "custom" / "oss" / "tie"
    delta: float = 0.0                 # 差异值
    notes: str = ""                    # 备注

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value if isinstance(self.dimension, CompareDimension) else self.dimension,
            "custom_score": self.custom_score,
            "oss_score": self.oss_score,
            "winner": self.winner,
            "delta": self.delta,
            "notes": self.notes,
        }


@dataclass
class CandidateLibrary:
    """候选开源库"""
    library: LibraryInfo                 # 库信息
    compare_results: List[CompareResult] # 比对结果
    overall_recommendation: ReplacementDecision  # 综合建议
    adapter_template: Optional[str] = None  # 适配器模板代码
    migration_guide: Optional[str] = None   # 迁移指南
    confidence: float = 0.0              # 置信度 (0-1)
    risks: List[str] = field(default_factory=list)  # 风险列表
    benefits: List[str] = field(default_factory=list)  # 收益列表
    estimated_effort_hours: float = 0.0  # 预估工作量(小时)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library": self.library.to_dict(),
            "compare_results": [r.to_dict() for r in self.compare_results],
            "overall_recommendation": self.overall_recommendation.value if isinstance(self.overall_recommendation, ReplacementDecision) else self.overall_recommendation,
            "adapter_template": self.adapter_template,
            "migration_guide": self.migration_guide,
            "confidence": self.confidence,
            "risks": self.risks,
            "benefits": self.benefits,
            "estimated_effort_hours": self.estimated_effort_hours,
        }


@dataclass
class ScanTask:
    """扫描任务"""
    id: str                              # 任务ID
    module_name: str                      # 模块名
    scan_sources: List[ScanSource]       # 扫描来源
    status: str = "pending"              # pending/running/completed/failed
    candidates: List[CandidateLibrary] = field(default_factory=list)
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "module_name": self.module_name,
            "scan_sources": [s.value for s in self.scan_sources],
            "status": self.status,
            "candidates": [c.to_dict() for c in self.candidates],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


# ============ 数据迁移模型 ============

@dataclass
class VersionInfo:
    """版本信息"""
    version: DataVersion
    format: str                          # json / jsonl / csv / db
    created_at: int                       # 创建时间戳
    file_pattern: str = "*.json"        # 文件模式
    schema_version: str = "1.0"         # Schema版本

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version.value if isinstance(self.version, DataVersion) else self.version,
            "format": self.format,
            "created_at": self.created_at,
            "file_pattern": self.file_pattern,
            "schema_version": self.schema_version,
        }


@dataclass
class DataMigrationRecord:
    """数据迁移记录"""
    id: str                              # 记录ID
    from_version: DataVersion            # 源版本
    to_version: DataVersion             # 目标版本
    file_path: str                      # 文件路径
    status: str = "pending"             # pending/in_progress/completed/failed/rolled_back
    records_migrated: int = 0          # 已迁移记录数
    records_failed: int = 0             # 失败记录数
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    backup_path: Optional[str] = None   # 备份路径
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_version": self.from_version.value if isinstance(self.from_version, DataVersion) else self.from_version,
            "to_version": self.to_version.value if isinstance(self.to_version, DataVersion) else self.to_version,
            "file_path": self.file_path,
            "status": self.status,
            "records_migrated": self.records_migrated,
            "records_failed": self.records_failed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "backup_path": self.backup_path,
            "error_message": self.error_message,
        }


# ============ 补丁过渡模型 ============

@dataclass
class LegacyPatch:
    """遗留补丁"""
    patch_id: str                         # 补丁ID
    module: str                           # 模块名
    legacy_status: PatchLegacyStatus       # 遗留状态
    original_patch_data: Dict[str, Any]   # 原始补丁数据
    applied_at: Optional[int] = None    # 应用时间
    marked_legacy_at: Optional[int] = None  # 标记为遗留的时间
    review_notes: str = ""               # 审核备注
    conflict_with_oss: bool = False      # 是否与开源库冲突
    suggested_action: str = ""           # 建议操作

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "module": self.module,
            "legacy_status": self.legacy_status.value if isinstance(self.legacy_status, PatchLegacyStatus) else self.legacy_status,
            "original_patch_data": self.original_patch_data,
            "applied_at": self.applied_at,
            "marked_legacy_at": self.marked_legacy_at,
            "review_notes": self.review_notes,
            "conflict_with_oss": self.conflict_with_oss,
            "suggested_action": self.suggested_action,
        }


# ============ 镜像加速模型 ============

@dataclass
class MirrorConfig:
    """镜像配置"""
    source: MirrorSource                  # 镜像源
    base_url: str                         # 基础URL
    priority: int = 0                   # 优先级 (越小越高)
    timeout_seconds: float = 8.0         # 超时秒数
    enabled: bool = True                 # 是否启用
    success_count: int = 0              # 成功次数
    failure_count: int = 0               # 失败次数
    last_check: Optional[int] = None     # 最后检查时间
    health_score: float = 1.0           # 健康评分 (0-1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value if isinstance(self.source, MirrorSource) else self.source,
            "base_url": self.base_url,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_check": self.last_check,
            "health_score": self.health_score,
        }


@dataclass
class DownloadTask:
    """下载任务"""
    id: str                              # 任务ID
    source_url: str                       # 源URL
    mirror_url: Optional[str] = None      # 镜像URL
    dest_path: str                       # 目标路径
    status: str = "pending"             # pending/downloading/completed/failed
    progress: float = 0.0               # 进度 (0-1)
    bytes_downloaded: int = 0           # 已下载字节
    total_bytes: int = 0                # 总字节
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    error_message: Optional[str] = None
    attempts: int = 0                   # 尝试次数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_url": self.source_url,
            "mirror_url": self.mirror_url,
            "dest_path": self.dest_path,
            "status": self.status,
            "progress": self.progress,
            "bytes_downloaded": self.bytes_downloaded,
            "total_bytes": self.total_bytes,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "attempts": self.attempts,
        }


# ============ 社区进化模型 ============

@dataclass
class HotArticle:
    """热点文章"""
    id: str                              # 文章ID
    title: str                           # 标题
    url: str                             # 链接
    source: str                          # 来源 (GitHub Trending/HN/Reddit等)
    summary: str = ""                   # 摘要
    keywords: List[str] = field(default_factory=list)  # 关键词
    relevance_score: float = 0.0        # 与当前架构的相关性评分
    architecture_impact: str = ""       # 架构影响评估
    posted_at: Optional[int] = None     # 发布时间
    collected_at: int = 0               # 采集时间

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "summary": self.summary,
            "keywords": self.keywords,
            "relevance_score": self.relevance_score,
            "architecture_impact": self.architecture_impact,
            "posted_at": self.posted_at,
            "collected_at": self.collected_at,
        }


@dataclass
class EvolutionProposal:
    """进化提案"""
    id: str                              # 提案ID
    title: str                           # 标题
    content: str                         # 提案内容 (Markdown)
    referenced_article_id: Optional[str] = None  # 引用的文章ID
    referenced_library: Optional[str] = None      # 引用的库名
    original_link: str = ""              # 原文链接
    impact_analysis: str = ""            # 影响分析
    risk_assessment: str = ""           # 风险评估
    benefits: List[str] = field(default_factory=list)  # 收益
    status: str = "draft"               # draft/proposed/discussing/approved/rejected
    upvotes: int = 0                    # 点赞数
    author_client_id: str = ""         # 作者ID
    created_at: int = 0                  # 创建时间
    published_at: Optional[int] = None  # 发布时间

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "referenced_article_id": self.referenced_article_id,
            "referenced_library": self.referenced_library,
            "original_link": self.original_link,
            "impact_analysis": self.impact_analysis,
            "risk_assessment": self.risk_assessment,
            "benefits": self.benefits,
            "status": self.status,
            "upvotes": self.upvotes,
            "author_client_id": self.author_client_id,
            "created_at": self.created_at,
            "published_at": self.published_at,
        }


# ============ 升级扫描系统统计 ============

@dataclass
class UpgradeStats:
    """升级扫描统计"""
    total_scans: int = 0                # 总扫描次数
    candidates_found: int = 0          # 发现候选数
    adoptions: int = 0                  # 采用数
    rejections: int = 0                 # 拒绝数
    migrations_completed: int = 0        # 迁移完成数
    legacy_patches_reviewed: int = 0     # 已审核遗留补丁
    proposals_generated: int = 0        # 生成提案数
    proposals_approved: int = 0         # 批准提案数

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============ 工具函数 ============

def generate_task_id(module: str) -> str:
    """生成扫描任务ID"""
    raw = f"{module}:{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def generate_migration_id(file_path: str, from_ver: str, to_ver: str) -> str:
    """生成迁移记录ID"""
    raw = f"{file_path}:{from_ver}:{to_ver}:{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def calculate_mirror_health(config: MirrorConfig) -> float:
    """计算镜像健康评分"""
    total = config.success_count + config.failure_count
    if total == 0:
        return 1.0  # 默认健康

    success_rate = config.success_count / total

    # 综合考虑成功率和最后检查时间
    time_factor = 1.0
    if config.last_check:
        age = datetime.now().timestamp() - config.last_check
        if age > 3600:  # 超过1小时
            time_factor = 0.8
        elif age > 86400:  # 超过1天
            time_factor = 0.5

    return success_rate * time_factor
