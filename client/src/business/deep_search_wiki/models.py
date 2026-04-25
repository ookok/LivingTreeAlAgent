"""
深度搜索Wiki系统数据模型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


class SourceType(Enum):
    """来源类型"""
    OFFICIAL_DOCS = "official_docs"   # 官方文档
    BLOG = "blog"                     # 技术博客
    PAPER = "paper"                   # 学术论文
    QNA = "qna"                       # 问答社区
    VIDEO = "video"                   # 视频教程
    SOCIAL = "social"                 # 社交媒体
    UNKNOWN = "unknown"


class ContentQuality(Enum):
    """内容质量"""
    HIGH = "high"                     # 高质量
    MEDIUM = "medium"                 # 中等质量
    LOW = "low"                       # 低质量


@dataclass
class SourceInfo:
    """来源信息"""
    url: str
    title: str
    source_type: SourceType = SourceType.UNKNOWN
    author: str = ""
    publish_date: Optional[datetime] = None
    domain: str = ""
    
    # 可信度评估
    authority_score: float = 0.0      # 权威性 0-100
    content_score: float = 0.0        # 内容质量 0-100
    technical_score: float = 0.0     # 技术指标 0-100
    
    # 引用信息
    citations: int = 0               # 被引用次数
    views: int = 0                   # 浏览量
    likes: int = 0                   # 点赞数
    
    # 可信度
    credibility: float = 0.0          # 综合可信度 0-100
    
    @property
    def stars(self) -> str:
        """星级评分"""
        score = self.credibility / 20
        full = int(score)
        half = 1 if score - full >= 0.5 else 0
        return "★" * full + ("☆" if half else "") + "☆" * (4 - full - half)
    
    def calculate_credibility(self):
        """计算综合可信度"""
        self.credibility = (
            self.authority_score * 0.4 +
            self.content_score * 0.3 +
            self.technical_score * 0.3
        )


@dataclass
class ContentSegment:
    """内容片段"""
    text: str
    source: Optional[SourceInfo] = None
    start_pos: int = 0
    end_pos: int = 0
    importance: float = 1.0          # 重要性 0-1
    is_verified: bool = False         # 是否已验证


@dataclass
class WikiSection:
    """Wiki章节"""
    title: str
    level: int = 2                    # 标题级别
    content: str = ""
    segments: List[ContentSegment] = field(default_factory=list)
    subs: List['WikiSection'] = field(default_factory=list)
    sources: List[SourceInfo] = field(default_factory=list)
    
    def add_segment(self, text: str, source: Optional[SourceInfo] = None):
        """添加内容片段"""
        segment = ContentSegment(
            text=text,
            source=source,
            start_pos=len(self.content),
            end_pos=len(self.content) + len(text),
        )
        self.segments.append(segment)
        self.content += text


@dataclass
class WikiPage:
    """Wiki页面"""
    topic: str
    generated_at: datetime = field(default_factory=datetime.now)
    
    # 概述
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    
    # 核心信息
    definition: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    applications: List[str] = field(default_factory=list)
    
    # 章节内容
    sections: List[WikiSection] = field(default_factory=list)
    
    # 来源
    sources: List[SourceInfo] = field(default_factory=list)
    
    # 学习资源
    resources: Dict[str, List[str]] = field(default_factory=dict)
    
    # 元数据
    sources_count: int = 0
    credibility_avg: float = 0.0
    confidence: float = 0.0          # 生成置信度
    
    # 版本控制
    version: str = "1.0"
    last_updated: Optional[datetime] = None
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        lines = [
            f"# {self.topic}",
            "",
            f"> 生成时间: {self.generated_at.strftime('%Y-%m-%d %H:%M')} | 来源数: {self.sources_count} | 置信度: {self.confidence:.0%}",
            "",
        ]
        
        # 概述
        if self.summary:
            lines.extend([
                "## 📋 概述",
                "",
                self.summary,
                "",
            ])
        
        # 核心信息表
        if self.key_points:
            lines.extend([
                "## 🔑 核心信息",
                "",
                "| 项目 | 内容 |",
                "|------|------|",
            ])
            if self.definition:
                lines.append(f"| 定义 | {self.definition} |")
            if self.category:
                lines.append(f"| 类别 | {self.category} |")
            if self.tags:
                lines.append(f"| 标签 | {', '.join(self.tags)} |")
            if self.applications:
                lines.append(f"| 应用场景 | {', '.join(self.applications)} |")
            lines.append("")
        
        # 关键要点
        if self.key_points:
            lines.extend([
                "### 📌 关键要点",
                "",
            ])
            for point in self.key_points:
                lines.append(f"- {point}")
            lines.append("")
        
        # 章节内容
        for section in self.sections:
            lines.extend(self._section_to_markdown(section))
        
        # 来源
        if self.sources:
            lines.extend([
                "## 📚 参考来源",
                "",
            ])
            for i, source in enumerate(self.sources, 1):
                cred_emoji = "★" * int(source.credibility / 20)
                lines.extend([
                    f"[{i}] **{source.title}** {cred_emoji}",
                    f"   - URL: {source.url}",
                    f"   - 来源: {source.domain}",
                    f"   - 可信度: {source.credibility:.0f}%",
                    "",
                ])
        
        # 学习资源
        if self.resources:
            lines.extend([
                "## 🔗 学习资源",
                "",
            ])
            for resource_type, urls in self.resources.items():
                lines.append(f"### {resource_type}")
                for url in urls:
                    lines.append(f"- {url}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _section_to_markdown(self, section: WikiSection, indent: str = "") -> List[str]:
        """章节转Markdown"""
        lines = []
        
        # 标题
        if section.title:
            lines.append(f"{indent}{'#' * section.level} {section.title}")
            lines.append("")
        
        # 内容
        if section.content:
            lines.append(section.content)
            lines.append("")
        
        # 子章节
        for sub in section.subs:
            lines.extend(self._section_to_markdown(sub, indent))
        
        return lines


@dataclass
class SearchQuery:
    """搜索查询"""
    original: str                     # 原始查询
    expanded: List[str] = field(default_factory=list)  # 扩展查询
    language: str = "zh-CN"           # 查询语言
    time_range: Optional[str] = None  # 时间范围
    sources_priority: List[str] = field(default_factory=list)  # 优先来源


@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str
    snippet: str
    source_type: SourceType = SourceType.UNKNOWN
    domain: str = ""
    score: float = 0.0               # 相关性评分
    is_verified: bool = False        # 是否已验证
    content: str = ""                # 获取的正文内容（Markdown 格式）
    word_count: int = 0              # 内容字数
