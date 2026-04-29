"""
GBrain 风格记忆系统 - 核心数据模型
Inspired by: https://github.com/garrytan/gbrain

核心设计理念：
1. Compiled Truth + Timeline - 每页记忆由两部分组成
2. MECE 分类目录 - 互斥且穷尽的分类体系
3. Human Authority - 人类永远是最终权威
4. Brain-First Lookup - 先查大脑再调用外部 API
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


class MemoryCategory(Enum):
    """MECE 记忆分类目录"""
    ORIGINALS = "originals"      # 原创想法（最高优先级）
    PEOPLE = "people"            # 人物档案
    COMPANIES = "companies"      # 公司档案
    PROJECTS = "projects"       # 项目记录
    MEETINGS = "meetings"       # 会议记录
    IDEAS = "ideas"             # 想法/创意
    CONCEPTS = "concepts"       # 概念定义
    FACTS = "facts"            # 事实锚点
    PREFERENCES = "preferences" # 用户偏好
    CONVERSATIONS = "conversations"  # 对话记录
    DOCUMENTS = "documents"     # 文档资料
    UNCLASSIFIED = "unclassified"  # 未分类


class EvidenceSource(Enum):
    """证据来源类型"""
    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    EXTERNAL_API = "external_api"
    MANUAL_ENTRY = "manual_entry"
    DREAM_CYCLE = "dream_cycle"  # 夜间循环生成


@dataclass
class TimelineEntry:
    """时间线条目 - 永不修改的证据链"""
    timestamp: float  # Unix 时间戳
    source: str  # 来源描述
    source_type: EvidenceSource
    content: str  # 原始内容/引用
    context: str = ""  # 上下文

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "timestamp_str": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M"),
            "source": self.source,
            "source_type": self.source_type.value,
            "content": self.content,
            "context": self.context
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimelineEntry":
        return cls(
            timestamp=d["timestamp"],
            source=d["source"],
            source_type=EvidenceSource(d.get("source_type", "manual_entry")),
            content=d["content"],
            context=d.get("context", "")
        )


@dataclass
class CompiledTruth:
    """编译真相 - 当前最佳理解（证据变化时重写）"""
    summary: str = ""  # 一句话总结
    key_points: List[str] = field(default_factory=list)  # 关键点
    status: str = "active"  # active/archived/outdated
    last_updated: float = field(default_factory=time.time)
    updated_by: str = "system"  # system/dream_cycle/human

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "key_points": self.key_points,
            "status": self.status,
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
            last_updated=d.get("last_updated", time.time()),
            updated_by=d.get("updated_by", "system")
        )


@dataclass
class BrainPage:
    """
    记忆页面 - GBrain 的核心数据结构

    结构：
    ┌─────────────────────────────────────┐
    │        COMPILED TRUTH               │  ← 当前最佳理解
    │  （证据变化时重写）                 │    动态更新
    ├─────────────────────────────────────┤
    │        TIMELINE                     │  ← 永不修改的证据链
    │  - 2024-01-15: 来源 + 原始引用      │    Append-only
    │  - 2024-03-20: 来源 + 原始引用      │
    └─────────────────────────────────────┘
    """
    id: str = ""  # 唯一标识 (slug)
    title: str = ""  # 页面标题
    category: MemoryCategory = MemoryCategory.UNCLASSIFIED
    compiled_truth: CompiledTruth = field(default_factory=CompiledTruth)
    timeline: List[TimelineEntry] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)  # 别名/昵称
    cross_references: List[str] = field(default_factory=list)  # 交叉引用页面 ID
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if isinstance(self.category, str):
            self.category = MemoryCategory(self.category)

    def _generate_id(self) -> str:
        """生成唯一 ID (slug)"""
        raw = f"{self.title or str(time.time())}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def add_timeline_entry(
        self,
        content: str,
        source: str,
        source_type: EvidenceSource = EvidenceSource.MANUAL_ENTRY,
        context: str = ""
    ) -> TimelineEntry:
        """追加时间线条目（Append-only）"""
        entry = TimelineEntry(
            timestamp=time.time(),
            source=source,
            source_type=source_type,
            content=content,
            context=context
        )
        self.timeline.append(entry)
        self.last_modified = time.time()
        return entry

    def update_compiled_truth(
        self,
        summary: str = None,
        key_points: List[str] = None,
        updated_by: str = "system"
    ) -> CompiledTruth:
        """更新编译真相"""
        if summary is not None:
            self.compiled_truth.summary = summary
        if key_points is not None:
            self.compiled_truth.key_points = key_points
        self.compiled_truth.last_updated = time.time()
        self.compiled_truth.updated_by = updated_by
        self.last_modified = time.time()
        return self.compiled_truth

    def to_markdown(self) -> str:
        """转换为 GBrain 风格的 Markdown 格式"""
        lines = []

        # 元数据头
        lines.append(f"<!-- BrainPage: {self.id} -->")
        lines.append(f"<!-- Category: {self.category.value} -->")
        if self.aliases:
            lines.append(f"<!-- Aliases: {', '.join(self.aliases)} -->")
        lines.append("")

        # 标题
        lines.append(f"# {self.title or self.id}")

        # 标签
        if self.tags:
            lines.append(f"**标签**: {', '.join(f'#{t}' for t in self.tags)}")
            lines.append("")

        # === COMPILED TRUTH ===
        lines.append("## COMPILED TRUTH")
        lines.append("")
        if self.compiled_truth.summary:
            lines.append(self.compiled_truth.summary)
            lines.append("")
        if self.compiled_truth.key_points:
            lines.append("**关键点**:")
            for point in self.compiled_truth.key_points:
                lines.append(f"- {point}")
            lines.append("")
        lines.append(f"_最后更新: {datetime.fromtimestamp(self.compiled_truth.last_updated).strftime('%Y-%m-%d %H:%M')} ({self.compiled_truth.updated_by})_")
        lines.append("")

        # === TIMELINE ===
        lines.append("## TIMELINE")
        lines.append("")
        lines.append("> ⚠️ 以下条目永不修改，只追加新证据")
        lines.append("")
        for entry in self.timeline:
            ts_str = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M")
            lines.append(f"- **{ts_str}** [{entry.source_type.value}]")
            lines.append(f"  - 来源: {entry.source}")
            if entry.context:
                lines.append(f"  - 上下文: {entry.context}")
            lines.append(f"  - {entry.content}")
            lines.append("")

        # === 交叉引用 ===
        if self.cross_references:
            lines.append("## 相关页面")
            lines.append("")
            for ref_id in self.cross_references:
                lines.append(f"- [[{ref_id}]]")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, markdown: str, page_id: str = None) -> "BrainPage":
        """从 GBrain 风格的 Markdown 解析"""
        page = cls()

        if page_id:
            page.id = page_id

        lines = markdown.split("\n")
        current_section = None
        timeline_buffer = []
        compiled_lines = []
        in_key_points = False

        for line in lines:
            # 解析元数据
            if line.startswith("<!--"):
                if "BrainPage:" in line:
                    page.id = re.search(r"BrainPage:\s*(\S+)", line).group(1) if re.search(r"BrainPage:\s*(\S+)", line) else page.id
                elif "Category:" in line:
                    cat = re.search(r"Category:\s*(\S+)", line)
                    if cat:
                        page.category = MemoryCategory(cat.group(1))
                elif "Aliases:" in line:
                    aliases = re.search(r"Aliases:\s*(.+?)\s*-->", line)
                    if aliases:
                        page.aliases = [a.strip() for a in aliases.group(1).split(",")]
                continue

            # 解析标题
            if line.startswith("# ") and not current_section:
                page.title = line[2:].strip()
                continue

            # 解析标签
            if line.startswith("**标签**:"):
                tags_str = re.search(r"\*\*标签\*\*:\s*(.+)", line).group(1)
                page.tags = [t.strip().lstrip("#") for t in tags_str.split(",")]
                continue

            # 解析章节
            if line.startswith("## "):
                section_name = line[3:].strip()
                if section_name == "COMPILED TRUTH":
                    current_section = "compiled"
                    in_key_points = False
                elif section_name == "TIMELINE":
                    current_section = "timeline"
                elif section_name == "相关页面":
                    current_section = "references"
                continue

            # 收集内容
            if current_section == "compiled":
                if line.startswith("**关键点**:"):
                    in_key_points = True
                    compiled_lines.append(line)
                elif in_key_points and line.startswith("- "):
                    compiled_lines.append(line)
                elif not in_key_points and line.strip():
                    compiled_lines.append(line)

            elif current_section == "timeline":
                timeline_buffer.append(line)

            elif current_section == "references" and line.startswith("- [["):
                ref = re.search(r"\[\[(\S+)\]\]", line)
                if ref:
                    page.cross_references.append(ref.group(1))

        # 解析 Compiled Truth
        if compiled_lines:
            page.compiled_truth = _parse_compiled_truth(compiled_lines)

        # 解析 Timeline
        page.timeline = _parse_timeline(timeline_buffer)

        return page

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "compiled_truth": self.compiled_truth.to_dict(),
            "timeline": [e.to_dict() for e in self.timeline],
            "tags": self.tags,
            "aliases": self.aliases,
            "cross_references": self.cross_references,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BrainPage":
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            category=MemoryCategory(d.get("category", "unclassified")),
            compiled_truth=CompiledTruth.from_dict(d.get("compiled_truth", {})),
            timeline=[TimelineEntry.from_dict(e) for e in d.get("timeline", [])],
            tags=d.get("tags", []),
            aliases=d.get("aliases", []),
            cross_references=d.get("cross_references", []),
            created_at=d.get("created_at", time.time()),
            last_modified=d.get("last_modified", time.time()),
            metadata=d.get("metadata", {})
        )


def _parse_compiled_truth(lines: List[str]) -> CompiledTruth:
    """解析 Compiled Truth 部分"""
    ct = CompiledTruth()
    in_key_points = False
    key_points = []

    for line in lines:
        if line.startswith("**关键点**:"):
            in_key_points = True
            continue
        if in_key_points and line.startswith("- "):
            key_points.append(line[2:].strip())
        elif not in_key_points and line.strip():
            if not ct.summary:
                ct.summary = line.strip()
            else:
                key_points.append(line.strip())

    ct.key_points = key_points
    return ct


def _parse_timeline(buffer: List[str]) -> List[TimelineEntry]:
    """解析 Timeline 部分"""
    entries = []
    current_entry = {}

    for line in buffer:
        line = line.strip()
        if not line:
            if current_entry.get("content"):
                entries.append(TimelineEntry(
                    timestamp=current_entry.get("timestamp", time.time()),
                    source=current_entry.get("source", ""),
                    source_type=EvidenceSource(current_entry.get("source_type", "manual_entry")),
                    content=current_entry.get("content", ""),
                    context=current_entry.get("context", "")
                ))
                current_entry = {}
            continue

        if line.startswith("**"):
            # 时间戳行
            ts_match = re.match(r"\*\*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\*\*", line)
            if ts_match:
                current_entry["timestamp"] = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M").timestamp()
            src_match = re.search(r"\[(\w+)\]", line)
            if src_match:
                current_entry["source_type"] = src_match.group(1)

        elif line.startswith("  - 来源:"):
            current_entry["source"] = line.split("来源:", 1)[1].strip()

        elif line.startswith("  - 上下文:"):
            current_entry["context"] = line.split("上下文:", 1)[1].strip()

        elif line.startswith("- "):
            current_entry["content"] = line[2:].strip()

    return entries


@dataclass
class EntityMention:
    """实体提及"""
    page_id: str
    entity_name: str
    context: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class MemoryQuery:
    """记忆查询"""
    keywords: List[str] = field(default_factory=list)
    category: Optional[MemoryCategory] = None
    tags: List[str] = field(default_factory=list)
    page_id: Optional[str] = None
    time_range: Tuple[Optional[float], Optional[float]] = (None, None)  # (start, end)
    limit: int = 10


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""
    page: BrainPage
    relevance_score: float
    matched_on: List[str]  # 匹配原因
    snippet: str = ""  # 匹配片段


# 分类目录结构 (MECE)
CATEGORY_STRUCTURE = {
    "people": {
        "description": "人物档案、联系人、关系图谱",
        "examples": ["同事、客户、朋友、家人"]
    },
    "companies": {
        "description": "公司组织、机构",
        "examples": ["雇主、客户公司、合作伙伴"]
    },
    "projects": {
        "description": "项目记录、工作进展",
        "examples": ["Hermes Desktop、某个产品开发"]
    },
    "meetings": {
        "description": "会议记录、讨论要点",
        "examples": ["周会、一对一、会议纪要"]
    },
    "originals": {
        "description": "原创想法、思考、洞察（最高优先级）",
        "examples": ["突然的想法、创意、洞察"]
    },
    "ideas": {
        "description": "想法/创意（待验证）",
        "examples": ["产品创意、功能建议"]
    },
    "concepts": {
        "description": "概念定义、知识要点",
        "examples": ["术语解释、技术概念"]
    },
    "facts": {
        "description": "事实锚点、确定的信息",
        "examples": ["电话号码、地址、重要日期"]
    },
    "preferences": {
        "description": "用户偏好、习惯、偏好设置",
        "examples": ["喜欢的咖啡、沟通风格"]
    },
    "conversations": {
        "description": "重要对话记录",
        "examples": ["关键讨论、决定性对话"]
    },
    "documents": {
        "description": "文档资料、文件摘要",
        "examples": ["合同摘要、文档链接"]
    },
    "unclassified": {
        "description": "未分类记忆",
        "examples": []
    }
}
