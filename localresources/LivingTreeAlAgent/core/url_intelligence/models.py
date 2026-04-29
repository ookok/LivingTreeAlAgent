"""
URL智能优化系统数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


class URLType(Enum):
    """URL类型分类"""
    CODE_REPO = "code_repo"           # 代码仓库
    PACKAGE_MANAGER = "package"       # 包管理器
    DOCUMENTATION = "docs"            # 文档站点
    API_DOCS = "api_docs"            # API文档
    PAPER_DATABASE = "paper"         # 论文数据库
    ACADEMIC_JOURNAL = "journal"      # 学术期刊
    PREPRINT = "preprint"             # 预印本平台
    SOCIAL_MEDIA = "social"           # 社交媒体
    VIDEO_PLATFORM = "video"          # 视频平台
    NEWS_MEDIA = "news"              # 新闻媒体
    BLOG = "blog"                    # 博客
    UNKNOWN = "unknown"


class AccessStatus(Enum):
    """访问状态"""
    ACCESSIBLE = "accessible"         # 可访问
    SLOW = "slow"                     # 访问缓慢
    BLOCKED = "blocked"               # 被限制
    NOT_FOUND = "not_found"          # 未找到
    TIMEOUT = "timeout"               # 超时
    UNKNOWN = "unknown"


class MirrorType(Enum):
    """镜像类型"""
    OFFICIAL_MIRROR = "official"     # 官方镜像
    CONTENT_MIRROR = "content"       # 内容镜像
    PROXY = "proxy"                  # 代理


@dataclass
class URLMetadata:
    """URL元数据"""
    original_url: str
    url_type: URLType = URLType.UNKNOWN
    domain: str = ""
    path: str = ""
    is_blocked: bool = False
    last_checked: Optional[datetime] = None
    owner: str = ""
    repo: str = ""
    package_name: str = ""
    package_version: str = ""
    paper_id: str = ""
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MirrorSource:
    """镜像源"""
    name: str
    url: str
    mirror_type: MirrorType
    speed_score: float = 0.0
    reliability_score: float = 0.0
    content_fidelity: float = 100.0
    sync_frequency: str = "实时"
    last_sync: Optional[datetime] = None
    location: str = "中国"
    is_official: bool = False
    latency_ms: float = 0.0
    status: AccessStatus = AccessStatus.UNKNOWN
    
    @property
    def overall_score(self) -> float:
        return self.speed_score * 0.3 + self.reliability_score * 0.4 + self.content_fidelity * 0.3
    
    @property
    def is_recommended(self) -> bool:
        return self.overall_score >= 70 and self.status == AccessStatus.ACCESSIBLE


@dataclass
class URLTestResult:
    """URL检测结果"""
    url: str
    status: AccessStatus
    latency_ms: float = 0.0
    status_code: int = 0
    error_message: str = ""
    test_time: datetime = field(default_factory=datetime.now)


@dataclass
class URLOptimizationResult:
    """URL优化结果"""
    original_url: str
    optimized_url: str
    url_metadata: URLMetadata
    recommended_mirror: Optional[MirrorSource] = None
    alternative_mirrors: List[MirrorSource] = field(default_factory=list)
    all_mirrors_tested: List[MirrorSource] = field(default_factory=list)
    test_results: List[URLTestResult] = field(default_factory=list)
    is_blocked: bool = False
    block_reason: str = ""
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    @property
    def has_better_alternative(self) -> bool:
        return self.recommended_mirror is not None and self.recommended_mirror.is_recommended
    
    def to_markdown(self) -> str:
        status_emoji = "❌ " if self.is_blocked else "✅ "
        lines = [
            f"## 🌐 URL优化建议",
            "",
            f"**原始链接**: {self.original_url}",
            f"**优化链接**: {self.optimized_url}",
            f"**访问状态**: {status_emoji}{'受限' if self.is_blocked else '正常'}",
            "",
        ]
        
        if self.recommended_mirror:
            lines.extend([
                "### 🚀 推荐镜像",
                "",
                f"| 项目 | 内容 |",
                f"|------|------|",
                f"| 名称 | {self.recommended_mirror.name} |",
                f"| 链接 | {self.recommended_mirror.url} |",
                f"| 类型 | {self.recommended_mirror.mirror_type.value} |",
                f"| 延迟 | {self.recommended_mirror.latency_ms:.0f}ms |",
                f"| 综合评分 | {self.recommended_mirror.overall_score:.1f} |",
                "",
            ])
        
        if self.alternative_mirrors:
            lines.extend(["### ⚡ 其他选项", ""])
            for i, mirror in enumerate(self.alternative_mirrors[:3], 1):
                lines.append(f"{i}. **{mirror.name}** - {mirror.url} ({mirror.latency_ms:.0f}ms)")
            lines.append("")
        
        if self.suggestions:
            lines.extend(["### 💡 建议", ""])
            for s in self.suggestions:
                lines.append(f"- {s}")
            lines.append("")
        
        return "\n".join(lines)
