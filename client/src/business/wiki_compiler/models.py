"""
LLM Wiki 编译层 - 核心数据模型

三层架构：
┌─────────────────────────────────────────────────┐
│           Layer 3: Schema (CLAUDE.md)            │
│    配置文档，定义wiki结构规范、工作流约定         │
├─────────────────────────────────────────────────┤
│              Layer 2: Wiki (LLM操作)             │
│   实体页面│概念页面│主题摘要│对比表格│综合概述   │
├─────────────────────────────────────────────────┤
│            Layer 1: Raw Material (不可变)         │
│        文章│论文│PDF│网页│代码│图片 → raw/       │
└─────────────────────────────────────────────────┘
"""

import json
import time
import hashlib
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from datetime import datetime


class MaterialType(Enum):
    """原材料类型"""
    ARTICLE = "article"           # 文章
    PAPER = "paper"             # 论文
    PDF = "pdf"                  # PDF文档
    WEBPAGE = "webpage"         # 网页
    CODE = "code"               # 代码
    IMAGE = "image"             # 图片
    CONVERSATION = "conversation" # 对话
    API_RESPONSE = "api_response" # API响应
    FILE = "file"               # 通用文件
    UNKNOWN = "unknown"


class WikiPageType(Enum):
    """Wiki页面类型"""
    SOURCE = "source"           # 源摘要页 (一个源一个页面)
    ENTITY = "entity"          # 实体页 (人物/公司/项目)
    CONCEPT = "concept"        # 概念页 (术语/方法/框架)
    TOPIC = "topic"            # 主题页 (综合多个概念)
    COMPARISON = "comparison"  # 对比页
    OVERVIEW = "overview"      # 综合概述
    INDEX = "index"            # 目录页
    LOG = "log"                # 日志页


@dataclass
class RawMaterial:
    """
    Layer 1: 原始素材（不可变）
    作为事实基准，LLM只读，人只写
    """
    id: str = ""                    # 唯一标识
    title: str = ""                  # 标题
    content: str = ""                # 原始内容
    material_type: MaterialType = MaterialType.UNKNOWN
    source_url: str = ""            # 来源URL
    source_path: str = ""           # 本地路径
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """生成唯一ID"""
        raw = f"{self.title or self.source_url or str(time.time())}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "material_type": self.material_type.value,
            "source_url": self.source_url,
            "source_path": self.source_path,
            "created_at": self.created_at,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RawMaterial":
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            content=d.get("content", ""),
            material_type=MaterialType(d.get("material_type", "unknown")),
            source_url=d.get("source_url", ""),
            source_path=d.get("source_path", ""),
            created_at=d.get("created_at", time.time()),
            metadata=d.get("metadata", {})
        )


@dataclass
class CrossReference:
    """交叉引用"""
    target_page_id: str          # 目标页面ID
    link_text: str = ""           # 链接文本
    context: str = ""             # 引用上下文
    anchor: str = ""              # 锚点


@dataclass
class CompiledTruth:
    """
    编译真相 - 当前最佳理解
    与 GBrain 的 CompiledTruth 一致
    """
    summary: str = ""             # 一句话总结
    key_points: List[str] = field(default_factory=list)  # 关键点
    status: str = "active"        # active/archived/outdated/contradiction
    confidence: float = 1.0       # 置信度 0-1
    last_updated: float = field(default_factory=time.time)
    updated_by: str = "system"    # system/compounding/human

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "key_points": self.key_points,
            "status": self.status,
            "confidence": self.confidence,
            "last_updated": self.last_updated,
            "last_updated_str": datetime.fromtimestamp(self.last_updated).strftime("%Y-%m-%d %H:%M"),
            "updated_by": self.updated_by
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompiledTruth":
        return cls(
            summary=d.get("summary", ""),
            key_points=d.get("key_points", []),
            status=d.get("status", "active"),
            confidence=d.get("confidence", 1.0),
            last_updated=d.get("last_updated", time.time()),
            updated_by=d.get("updated_by", "system")
        )


@dataclass
class EvidenceEntry:
    """证据条目 - 时间线上的证据"""
    timestamp: float
    source_id: str               # 原材料ID
    source_title: str             # 原材料标题
    content: str                  # 引用内容
    context: str = ""            # 上下文
    page_relevance: float = 1.0  # 与页面的相关性 0-1

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "content": self.content,
            "context": self.context,
            "page_relevance": self.page_relevance,
            "timestamp_str": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M")
        }


@dataclass
class WikiPage:
    """
    Layer 2: Wiki 页面（LLM读写，人只读）

    结构：
    ┌─────────────────────────────────────┐
    │        COMPILED TRUTH               │  ← 当前最佳理解
    │  （被新证据更新时重写）             │
    ├─────────────────────────────────────┤
    │        EVIDENCE TIMELINE            │  ← 永不修改的证据链
    │  - 证据条目1                        │    Append-only
    │  - 证据条目2                        │
    ├─────────────────────────────────────┤
    │        OUTLINKS / INLINKS           │  ← 交叉引用
    └─────────────────────────────────────┘
    """
    id: str = ""                   # 唯一标识 (slug)
    title: str = ""
    page_type: WikiPageType = WikiPageType.CONCEPT
    compiled_truth: CompiledTruth = field(default_factory=CompiledTruth)
    evidence_timeline: List[EvidenceEntry] = field(default_factory=list)
    cross_references: List[CrossReference] = field(default_factory=list)

    # 关联
    source_material_ids: List[str] = field(default_factory=list)  # 来源原材料
    parent_page_ids: List[str] = field(default_factory=list)     # 父页面
    child_page_ids: List[str] = field(default_factory=list)      # 子页面

    # 元数据
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    version: int = 1              # 版本号
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if isinstance(self.page_type, str):
            self.page_type = WikiPageType(self.page_type)

    def _generate_id(self) -> str:
        """生成唯一ID (slug)"""
        raw = f"{self.title or str(time.time())}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def add_evidence(
        self,
        source_id: str,
        source_title: str,
        content: str,
        context: str = "",
        relevance: float = 1.0
    ) -> EvidenceEntry:
        """追加证据（Append-only）"""
        entry = EvidenceEntry(
            timestamp=time.time(),
            source_id=source_id,
            source_title=source_title,
            content=content,
            context=context,
            page_relevance=relevance
        )
        self.evidence_timeline.append(entry)
        self.last_modified = time.time()
        self.version += 1
        return entry

    def update_compiled_truth(
        self,
        summary: str = None,
        key_points: List[str] = None,
        status: str = None,
        confidence: float = None,
        updated_by: str = "system"
    ) -> CompiledTruth:
        """更新编译真相"""
        if summary is not None:
            self.compiled_truth.summary = summary
        if key_points is not None:
            self.compiled_truth.key_points = key_points
        if status is not None:
            self.compiled_truth.status = status
        if confidence is not None:
            self.compiled_truth.confidence = confidence
        self.compiled_truth.last_updated = time.time()
        self.compiled_truth.updated_by = updated_by
        self.last_modified = time.time()
        self.version += 1
        return self.compiled_truth

    def add_cross_reference(
        self,
        target_id: str,
        link_text: str = "",
        context: str = ""
    ) -> CrossReference:
        """添加交叉引用"""
        ref = CrossReference(
            target_page_id=target_id,
            link_text=link_text or self.title,
            context=context
        )
        if not any(r.target_page_id == target_id for r in self.cross_references):
            self.cross_references.append(ref)
            self.last_modified = time.time()
        return ref

    def to_markdown(self) -> str:
        """转换为 Markdown 格式（Obsidian 兼容）"""
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f"id: {self.id}")
        lines.append(f"title: {self.title}")
        lines.append(f"type: {self.page_type.value}")
        lines.append(f"tags: [{', '.join(self.tags)}]")
        lines.append(f"aliases: [{', '.join(self.aliases)}]")
        lines.append(f"created: {datetime.fromtimestamp(self.created_at).strftime('%Y-%m-%d')}")
        lines.append(f"modified: {datetime.fromtimestamp(self.last_modified).strftime('%Y-%m-%d')}")
        lines.append(f"version: {self.version}")
        if self.source_material_ids:
            lines.append(f"sources: [{', '.join(self.source_material_ids)}]")
        lines.append("---")
        lines.append("")

        # 标题
        lines.append(f"# {self.title or self.id}")
        lines.append("")

        # === COMPILED TRUTH ===
        lines.append("## Compiled Truth")
        lines.append("")
        if self.compiled_truth.summary:
            lines.append(self.compiled_truth.summary)
            lines.append("")
        if self.compiled_truth.key_points:
            lines.append("**关键点**:")
            for point in self.compiled_truth.key_points:
                lines.append(f"- {point}")
            lines.append("")
        if self.compiled_truth.status != "active":
            lines.append(f"⚠️ **状态**: {self.compiled_truth.status}")
            lines.append("")
        lines.append(f"_置信度: {self.compiled_truth.confidence:.0%} | ")
        lines.append(f"最后更新: {datetime.fromtimestamp(self.compiled_truth.last_updated).strftime('%Y-%m-%d %H:%M')} ({self.compiled_truth.updated_by})_")
        lines.append("")

        # === EVIDENCE TIMELINE ===
        lines.append("## Evidence Timeline")
        lines.append("")
        lines.append("> ⚠️ 以下证据永不修改，只追加新证据")
        lines.append("")
        for entry in self.evidence_timeline:
            lines.append(f"- **{entry.timestamp_str}**")
            lines.append(f"  - 来源: [[{entry.source_id}|{entry.source_title}]]")
            if entry.context:
                lines.append(f"  - 上下文: {entry.context}")
            lines.append(f"  - {entry.content}")
            lines.append("")
        lines.append("")

        # === 交叉引用 ===
        if self.cross_references:
            lines.append("## 交叉引用")
            lines.append("")
            outlinks = [r for r in self.cross_references if r.context]  # 有上下文的优先
            inlinks = []  # 需要从反向引用获取
            for ref in outlinks:
                lines.append(f"- [[{ref.target_page_id}|{ref.link_text}]]")
                if ref.context:
                    lines.append(f"  > {ref.context[:100]}...")
            lines.append("")

        # === 子页面 ===
        if self.child_page_ids:
            lines.append("## 子页面")
            lines.append("")
            for child_id in self.child_page_ids:
                lines.append(f"- [[{child_id}]]")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "page_type": self.page_type.value,
            "compiled_truth": self.compiled_truth.to_dict(),
            "evidence_timeline": [e.to_dict() for e in self.evidence_timeline],
            "cross_references": [
                {
                    "target_page_id": r.target_page_id,
                    "link_text": r.link_text,
                    "context": r.context
                }
                for r in self.cross_references
            ],
            "source_material_ids": self.source_material_ids,
            "parent_page_ids": self.parent_page_ids,
            "child_page_ids": self.child_page_ids,
            "tags": self.tags,
            "aliases": self.aliases,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "version": self.version,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WikiPage":
        page = cls(
            id=d["id"],
            title=d.get("title", ""),
            page_type=WikiPageType(d.get("page_type", "concept")),
            compiled_truth=CompiledTruth.from_dict(d.get("compiled_truth", {})),
            source_material_ids=d.get("source_material_ids", []),
            parent_page_ids=d.get("parent_page_ids", []),
            child_page_ids=d.get("child_page_ids", []),
            tags=d.get("tags", []),
            aliases=d.get("aliases", []),
            created_at=d.get("created_at", time.time()),
            last_modified=d.get("last_modified", time.time()),
            version=d.get("version", 1),
            metadata=d.get("metadata", {})
        )
        page.evidence_timeline = [
            EvidenceEntry(**e) for e in d.get("evidence_timeline", [])
        ]
        page.cross_references = [
            CrossReference(**r) for r in d.get("cross_references", [])
        ]
        return page


@dataclass
class CompiledAnswer:
    """
    编译后的答案 - 查询结果
    包含引用和推理过程
    """
    query: str                    # 原始查询
    answer: str                    # 生成的答案
    confidence: float = 1.0       # 置信度

    # 引用的 Wiki 页面
    referenced_pages: List[str] = field(default_factory=list)  # 页面ID列表
    referenced_sources: List[str] = field(default_factory=list)  # 原材料ID列表

    # 推理链
    reasoning_chain: List[str] = field(default_factory=list)  # 推理步骤

    # 统计
    compiled_at: float = field(default_factory=time.time)
    query_embedding: List[float] = field(default_factory=list)  # 查询向量

    # 是否可以编译为新页面
    worth_saving: bool = False
    suggested_title: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "confidence": self.confidence,
            "referenced_pages": self.referenced_pages,
            "referenced_sources": self.referenced_sources,
            "reasoning_chain": self.reasoning_chain,
            "compiled_at": self.compiled_at,
            "worth_saving": self.worth_saving,
            "suggested_title": self.suggested_title
        }


@dataclass
class Schema:
    """
    Layer 3: Schema 配置
    定义 wiki 的结构规范和工作流约定
    """
    name: str = "Hermes Desktop Wiki"
    version: str = "1.0"

    # 目录结构
    directories: Dict[str, str] = field(default_factory=dict)

    # 命名约定
    naming_conventions: Dict[str, str] = field(default_factory=dict)

    # 工作流
    ingest_workflow: List[str] = field(default_factory=list)
    query_workflow: List[str] = field(default_factory=list)
    check_workflow: List[str] = field(default_factory=list)

    # 页面模板
    page_templates: Dict[str, str] = field(default_factory=dict)

    # 标签规范
    allowed_tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.directories:
            self._init_default_schema()

    def _init_default_schema(self):
        """初始化默认 Schema"""
        self.directories = {
            "raw": "raw/",                    # 原始素材
            "sources": "sources/",            # 源摘要页
            "entities": "entities/",          # 实体页
            "concepts": "concepts/",          # 概念页
            "topics": "topics/",             # 主题页
            "comparisons": "comparisons/",   # 对比页
            "overview": "overview.md",        # 综合概述
            "index": "index.md",             # 目录
            "log": "log.md"                  # 日志
        }

        self.naming_conventions = {
            "page_id": "kebab-case",
            "tags": "lowercase-hyphenated",
            "aliases": "title-case"
        }

        self.ingest_workflow = [
            "1. 将新来源放入 raw/",
            "2. LLM 读取内容，提取关键信息",
            "3. 编写 sources/[name].md 摘要页",
            "4. 更新 entities/ 相关实体页",
            "5. 更新 concepts/ 相关概念页",
            "6. 更新 topics/ 相关主题页",
            "7. 更新 overview.md 综合摘要",
            "8. 更新 index.md 目录",
            "9. 追加 log.md 日志条目",
            "10. 检查交叉引用完整性"
        ]

        self.query_workflow = [
            "1. 读取 index.md 定位相关页面",
            "2. 深入具体页面，跨页面综合信息",
            "3. 生成带引用的答案",
            "4. 好答案可归档为新 wiki 页面"
        ]

        self.check_workflow = [
            "1. 发现页面间矛盾 → 标记 ⚠️",
            "2. 标记过时内容 → 更新状态",
            "3. 识别孤立页面（无入站链接）",
            "4. 找出缺失的交叉引用",
            "5. 检查未更新的长期页面"
        ]

        self.page_templates = {
            "entity": "templates/entity.md",
            "concept": "templates/concept.md",
            "topic": "templates/topic.md",
            "comparison": "templates/comparison.md"
        }

        self.allowed_tags = [
            "人物", "公司", "项目", "产品", "技术", "概念", "方法",
            "论文", "文章", "视频", "代码", "工具", "教程", "思考",
            "决策", "事实", "偏好", "创意", "待验证", "重要"
        ]

    def to_markdown(self) -> str:
        """导出为 CLAUDE.md 格式"""
        lines = []
        lines.append(f"# {self.name} - Schema v{self.version}")
        lines.append("")
        lines.append("## 目录结构")
        for name, path in self.directories.items():
            lines.append(f"- {name}: {path}")
        lines.append("")
        lines.append("## 命名约定")
        for k, v in self.naming_conventions.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
        lines.append("## Ingest 工作流")
        for step in self.ingest_workflow:
            lines.append(step)
        lines.append("")
        lines.append("## Query 工作流")
        for step in self.query_workflow:
            lines.append(step)
        lines.append("")
        lines.append("## Check 工作流")
        for step in self.check_workflow:
            lines.append(step)
        lines.append("")
        lines.append("## 允许的标签")
        lines.append(f"[{', '.join(self.allowed_tags)}]")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "directories": self.directories,
            "naming_conventions": self.naming_conventions,
            "ingest_workflow": self.ingest_workflow,
            "query_workflow": self.query_workflow,
            "check_workflow": self.check_workflow,
            "page_templates": self.page_templates,
            "allowed_tags": self.allowed_tags
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Schema":
        return cls(
            name=d.get("name", "Hermes Desktop Wiki"),
            version=d.get("version", "1.0"),
            directories=d.get("directories", {}),
            naming_conventions=d.get("naming_conventions", {}),
            ingest_workflow=d.get("ingest_workflow", []),
            query_workflow=d.get("query_workflow", []),
            check_workflow=d.get("check_workflow", []),
            page_templates=d.get("page_templates", {}),
            allowed_tags=d.get("allowed_tags", [])
        )


@dataclass
class IngestResult:
    """摄入结果"""
    success: bool
    material_id: str = ""
    created_pages: List[str] = field(default_factory=list)  # 创建的页面ID
    updated_pages: List[str] = field(default_factory=list)  # 更新的页面ID
    cross_references_added: int = 0
    error: str = ""
    log_entry: str = ""


@dataclass
class CheckResult:
    """检查结果"""
    contradictions: List[Dict] = field(default_factory=list)      # 矛盾页面
    outdated_pages: List[Dict] = field(default_factory=list)    # 过时页面
    orphan_pages: List[Dict] = field(default_factory=list)       # 孤立页面
    missing_links: List[Dict] = field(default_factory=list)      # 缺失链接
    suggestions: List[str] = field(default_factory=list)        # 建议


@dataclass
class QueryStats:
    """查询统计"""
    total_queries: int = 0
    cache_hits: int = 0
    wiki_hits: int = 0
    compounding_bonus: float = 0.0  # 复利加成
    avg_confidence: float = 0.0

    @property
    def cache_hit_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries

    @property
    def compounding_rate(self) -> float:
        """复利率 = 知识库因复利效应变聪明的程度"""
        if self.total_queries == 0:
            return 0.0
        return self.compounding_bonus / self.total_queries