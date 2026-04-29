"""
KnowledgeIngestionPipeline - 多源知识摄入管道

支持从多种来源摄取知识，供自我进化系统学习：
1. 网址 (URL) - 网页内容抓取和解析
2. 纯文本 - 用户直接输入的文本
3. 文档文件 - PDF/Word/Markdown/HTML 等
4. 源代码 - 从代码仓库或文件学习
5. Git 提交记录 - 学习项目变更历史

所有知识通过 GlobalModelRouter 进行语义提取，
构建结构化知识条目，存储到本地知识库。

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class KnowledgeSource(Enum):
    """知识来源类型"""
    URL = "url"
    TEXT = "text"
    DOCUMENT = "document"
    SOURCE_CODE = "source_code"
    GIT_HISTORY = "git_history"
    FEEDBACK = "feedback"


class KnowledgeType(Enum):
    """知识类型"""
    API_DESIGN = "api_design"           # API/接口设计
    ARCHITECTURE = "architecture"       # 架构模式
    CODE_PATTERN = "code_pattern"       # 代码模式/最佳实践
    DOMAIN_KNOWLEDGE = "domain"         # 领域知识
    BUG_FIX = "bug_fix"                 # Bug 修复经验
    PERFORMANCE = "performance"         # 性能优化
    SECURITY = "security"               # 安全实践
    TOOL_USAGE = "tool_usage"           # 工具使用方法
    WORKFLOW = "workflow"               # 工作流
    GENERAL = "general"                 # 通用知识


@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    source: KnowledgeSource
    source_ref: str  # 来源标识（URL / 文件路径 / 用户输入摘要）
    knowledge_type: KnowledgeType
    title: str
    content: str
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    confidence: float = 0.8
    created_at: str = ""
    applied: bool = False  # 是否已应用到项目中

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value,
            "source_ref": self.source_ref,
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "tags": self.tags,
            "related_files": self.related_files,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "applied": self.applied,
        }


@dataclass
class IngestionResult:
    """摄入结果"""
    success: bool
    source_ref: str
    entries_created: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class KnowledgeIngestionPipeline:
    """
    多源知识摄入管道

    工作流程：
    1. 接收输入（URL/文本/文件/代码）
    2. 内容提取（根据类型使用不同提取器）
    3. LLM 语义分析（通过 GlobalModelRouter）
       - 分类知识类型
       - 提取关键信息
       - 生成摘要
       - 推断可应用的项目文件
    4. 去重（基于内容 hash）
    5. 存储到本地知识库
    6. 返回结构化知识条目

    用法：
        pipeline = KnowledgeIngestionPipeline(project_root)
        result = await pipeline.ingest_url("https://docs.python.org/3/library/ast.html")
        result = await pipeline.ingest_text("我发现项目中的缓存策略有问题...", source="user_feedback")
        result = await pipeline.ingest_document("/path/to/document.pdf")
        result = await pipeline.ingest_source_code("/path/to/repo")
    """

    # 知识库存储路径
    KNOWLEDGE_BASE_DIR = ".evolution_knowledge"
    ENTRIES_FILE = "knowledge_entries.json"
    INDEX_FILE = "knowledge_index.json"

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._kb_dir = self._root / self.KNOWLEDGE_BASE_DIR
        self._logger = logger.bind(component="KnowledgeIngestionPipeline")
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._ensure_kb_dir()
        self._load_entries()

    def _ensure_kb_dir(self):
        """确保知识库目录存在"""
        self._kb_dir.mkdir(parents=True, exist_ok=True)

    def _load_entries(self):
        """从磁盘加载已有知识条目"""
        entries_file = self._kb_dir / self.ENTRIES_FILE
        if entries_file.exists():
            try:
                data = json.loads(entries_file.read_text(encoding="utf-8"))
                for eid, entry_data in data.items():
                    entry_data["source"] = KnowledgeSource(entry_data["source"])
                    entry_data["knowledge_type"] = KnowledgeType(entry_data["knowledge_type"])
                    self._entries[eid] = KnowledgeEntry(**entry_data)
                self._logger.info(f"加载 {len(self._entries)} 条知识")
            except Exception as e:
                self._logger.warning(f"加载知识库失败: {e}")

    def _save_entries(self):
        """保存知识条目到磁盘"""
        entries_file = self._kb_dir / self.ENTRIES_FILE
        data = {eid: entry.to_dict() for eid, entry in self._entries.items()}
        entries_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _content_hash(content: str) -> str:
        """计算内容哈希（去重用）"""
        return hashlib.md5(content.strip().encode("utf-8")).hexdigest()[:12]

    # ── 公共摄入接口 ─────────────────────────────────────────────

    async def ingest_url(self, url: str, tags: Optional[List[str]] = None) -> IngestionResult:
        """
        从 URL 摄取知识

        Args:
            url: 网页地址
            tags: 额外标签
        """
        start = time.time()
        self._logger.info(f"从 URL 摄取知识: {url}")
        errors = []

        # 1. 抓取内容
        content = await self._fetch_url_content(url)
        if not content:
            return IngestionResult(
                success=False, source_ref=url,
                errors=[f"无法抓取 URL 内容: {url}"],
                duration_ms=(time.time() - start) * 1000,
            )

        # 2. LLM 语义分析
        entries = await self._analyze_and_create_entries(
            content=content,
            source=KnowledgeSource.URL,
            source_ref=url,
            extra_tags=tags or ["web"],
        )

        # 3. 存储
        count = self._dedup_and_store(entries)

        self._logger.info(f"URL 摄取完成: {count} 条知识")
        return IngestionResult(
            success=True,
            source_ref=url,
            entries_created=count,
            duration_ms=(time.time() - start) * 1000,
        )

    async def ingest_text(
        self,
        text: str,
        source_name: str = "user_input",
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """
        从纯文本摄取知识

        Args:
            text: 文本内容
            source_name: 来源名称
            tags: 额外标签
        """
        start = time.time()
        self._logger.info(f"从文本摄取知识: {source_name} ({len(text)} 字符)")

        if not text.strip():
            return IngestionResult(
                success=False, source_ref=source_name,
                errors=["文本内容为空"],
            )

        entries = await self._analyze_and_create_entries(
            content=text,
            source=KnowledgeSource.TEXT,
            source_ref=source_name,
            extra_tags=tags or ["user_input"],
        )

        count = self._dedup_and_store(entries)

        return IngestionResult(
            success=True,
            source_ref=source_name,
            entries_created=count,
            duration_ms=(time.time() - start) * 1000,
        )

    async def ingest_document(
        self,
        file_path: str,
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """
        从文档文件摄取知识

        支持格式: .md, .txt, .html, .py, .json, .yaml, .toml
        (PDF/Word 可通过扩展 markitdown 集成)

        Args:
            file_path: 文件路径
            tags: 额外标签
        """
        start = time.time()
        fpath = Path(file_path)
        self._logger.info(f"从文档摄取知识: {fpath.name}")

        if not fpath.exists():
            return IngestionResult(
                success=False, source_ref=str(file_path),
                errors=[f"文件不存在: {file_path}"],
            )

        # 读取文件内容
        ext = fpath.suffix.lower()
        content = self._extract_file_content(fpath, ext)

        if not content:
            return IngestionResult(
                success=False, source_ref=str(file_path),
                errors=[f"无法提取文件内容: {file_path}"],
            )

        doc_type_map = {
            ".md": "markdown", ".txt": "plain", ".html": "html",
            ".py": "python", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml", ".rst": "rst",
        }

        entries = await self._analyze_and_create_entries(
            content=content,
            source=KnowledgeSource.DOCUMENT,
            source_ref=str(file_path),
            extra_tags=tags or [f"doc:{doc_type_map.get(ext, 'unknown')}"],
        )

        count = self._dedup_and_store(entries)

        return IngestionResult(
            success=True,
            source_ref=str(file_path),
            entries_created=count,
            duration_ms=(time.time() - start) * 1000,
        )

    async def ingest_source_code(
        self,
        path: str,
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """
        从源代码摄取知识（学习代码模式）

        Args:
            path: 代码文件或目录路径
            tags: 额外标签
        """
        start = time.time()
        code_path = Path(path)
        self._logger.info(f"从源代码摄取知识: {code_path}")

        if not code_path.exists():
            return IngestionResult(
                success=False, source_ref=str(path),
                errors=[f"路径不存在: {path}"],
            )

        # 收集源代码文件
        code_files = []
        if code_path.is_file():
            code_files.append(code_path)
        elif code_path.is_dir():
            for ext in (".py", ".js", ".ts", ".go", ".rs", ".java"):
                code_files.extend(code_path.rglob(f"*{ext}"))

        if not code_files:
            return IngestionResult(
                success=False, source_ref=str(path),
                errors=[f"未找到源代码文件: {path}"],
            )

        # 逐文件分析（合并为一次 LLM 调用）
        combined_content = ""
        for cf in code_files[:20]:  # 限制最多 20 个文件
            try:
                content = cf.read_text(encoding="utf-8", errors="ignore")
                rel = cf.relative_to(code_path) if code_path.is_dir() else cf.name
                combined_content += f"\n--- {rel} ---\n{content[:3000]}\n"
            except Exception:
                pass

        entries = await self._analyze_and_create_entries(
            content=combined_content,
            source=KnowledgeSource.SOURCE_CODE,
            source_ref=str(path),
            extra_tags=tags or ["source_code", "code_pattern"],
        )

        count = self._dedup_and_store(entries)

        return IngestionResult(
            success=True,
            source_ref=str(path),
            entries_created=count,
            duration_ms=(time.time() - start) * 1000,
        )

    async def ingest_git_history(
        self,
        repo_path: str = ".",
        max_commits: int = 50,
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """
        从 Git 提交记录摄取知识（学习变更历史）

        Args:
            repo_path: 仓库路径
            max_commits: 最大分析提交数
            tags: 额外标签
        """
        start = time.time()
        self._logger.info(f"从 Git 历史摄取知识: {repo_path}")

        # 获取最近提交记录
        commits = self._get_git_log(repo_path, max_commits)
        if not commits:
            return IngestionResult(
                success=False, source_ref=repo_path,
                errors=["无法获取 Git 日志"],
            )

        entries = await self._analyze_and_create_entries(
            content=json.dumps(commits, ensure_ascii=False, indent=2),
            source=KnowledgeSource.GIT_HISTORY,
            source_ref=repo_path,
            extra_tags=tags or ["git", "changelog"],
        )

        count = self._dedup_and_store(entries)

        return IngestionResult(
            success=True,
            source_ref=repo_path,
            entries_created=count,
            duration_ms=(time.time() - start) * 1000,
        )

    # ── 查询接口 ─────────────────────────────────────────────

    def list_entries(
        self,
        source: Optional[KnowledgeSource] = None,
        knowledge_type: Optional[KnowledgeType] = None,
        tag: Optional[str] = None,
        applied_only: bool = False,
        limit: int = 50,
    ) -> List[KnowledgeEntry]:
        """查询知识条目"""
        results = list(self._entries.values())

        if source:
            results = [e for e in results if e.source == source]
        if knowledge_type:
            results = [e for e in results if e.knowledge_type == knowledge_type]
        if tag:
            results = [e for e in results if tag in e.tags]
        if applied_only:
            results = [e for e in results if e.applied]

        # 按时间倒序
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_knowledge_summary(self) -> str:
        """获取知识库摘要（用于 LLM 上下文）"""
        if not self._entries:
            return "知识库为空"

        lines = [f"知识库: {len(self._entries)} 条知识"]
        lines.append("")

        # 按类型分组
        type_counts: Dict[str, int] = defaultdict(int)
        source_counts: Dict[str, int] = defaultdict(int)
        for entry in self._entries.values():
            type_counts[entry.knowledge_type.value] += 1
            source_counts[entry.source.value] += 1

        lines.append("按类型:")
        for kt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {kt}: {count}")

        lines.append("")
        lines.append("按来源:")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {src}: {count}")

        lines.append("")
        lines.append("=== 最新知识 ===")
        recent = sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)[:10]
        for entry in recent:
            lines.append(f"  [{entry.knowledge_type.value}] {entry.title}")
            if entry.summary:
                lines.append(f"    {entry.summary[:100]}")

        return "\n".join(lines)

    def mark_applied(self, entry_id: str):
        """标记知识已应用"""
        if entry_id in self._entries:
            self._entries[entry_id].applied = True
            self._save_entries()

    def get_unapplied_entries(self) -> List[KnowledgeEntry]:
        """获取未应用的知识"""
        return [e for e in self._entries.values() if not e.applied]

    # ── 内部方法 ─────────────────────────────────────────────

    async def _fetch_url_content(self, url: str) -> str:
        """抓取 URL 内容"""
        try:
            import urllib.request
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "LivingTreeAI/2.0 (Knowledge Ingestion)"},
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                raw = resp.read(200000).decode("utf-8", errors="ignore")  # 限制 200KB

            # 简单 HTML → 文本
            content = self._html_to_text(raw)
            return content[:50000]  # 限制 50K 字符

        except Exception as e:
            self._logger.error(f"URL 抓取失败: {e}")
            return ""

    @staticmethod
    def _html_to_text(html: str) -> str:
        """简单 HTML 转纯文本"""
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _extract_file_content(fpath: Path, ext: str) -> str:
        """提取文件内容"""
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            # 对大文件截断
            if len(content) > 100000:
                content = content[:100000]
            return content
        except Exception:
            return ""

    @staticmethod
    def _get_git_log(repo_path: str, max_commits: int) -> List[Dict[str, str]]:
        """获取 Git 日志"""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", f"-{max_commits}", "--pretty=format:%H|%ai|%s|%b"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commits = []
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 3)
                    commits.append({
                        "hash": parts[0][:8],
                        "date": parts[1],
                        "subject": parts[2],
                        "body": parts[3] if len(parts) > 3 else "",
                    })
            return commits
        except Exception:
            return []

    async def _analyze_and_create_entries(
        self,
        content: str,
        source: KnowledgeSource,
        source_ref: str,
        extra_tags: List[str] | None = None,
    ) -> List[KnowledgeEntry]:
        """
        使用 LLM 分析内容并创建知识条目

        通过 GlobalModelRouter 调用 LLM 进行语义分析。
        """
        # 截断过长内容
        max_input = 30000
        truncated = content[:max_input] if len(content) > max_input else content

        prompt = f"""你是一个知识提取专家。请从以下内容中提取有价值的知识条目。

来源类型: {source.value}
来源标识: {source_ref}

内容:
```
{truncated}
```

请提取 1-5 条知识条目，每条以 JSON 数组格式输出：
[
  {{
    "title": "知识标题",
    "type": "api_design|architecture|code_pattern|domain|bug_fix|performance|security|tool_usage|workflow|general",
    "content": "知识的详细内容（200-500字）",
    "summary": "一句话摘要",
    "tags": ["tag1", "tag2"],
    "related_files": ["可能相关的项目文件路径"],
    "confidence": 0.8
  }}
]

只输出 JSON 数组，不要其他文字。"""

        try:
            analysis = await self._call_llm(prompt)
            entries_data = json.loads(analysis)

            entries = []
            for ed in entries_data if isinstance(entries_data, list) else [entries_data]:
                eid = self._content_hash(ed.get("content", ed.get("title", "")))
                type_map = {
                    "api_design": KnowledgeType.API_DESIGN,
                    "architecture": KnowledgeType.ARCHITECTURE,
                    "code_pattern": KnowledgeType.CODE_PATTERN,
                    "domain": KnowledgeType.DOMAIN_KNOWLEDGE,
                    "bug_fix": KnowledgeType.BUG_FIX,
                    "performance": KnowledgeType.PERFORMANCE,
                    "security": KnowledgeType.SECURITY,
                    "tool_usage": KnowledgeType.TOOL_USAGE,
                    "workflow": KnowledgeType.WORKFLOW,
                    "general": KnowledgeType.GENERAL,
                }
                kt = type_map.get(ed.get("type", "general"), KnowledgeType.GENERAL)

                entry = KnowledgeEntry(
                    id=eid,
                    source=source,
                    source_ref=source_ref,
                    knowledge_type=kt,
                    title=ed.get("title", "未命名知识"),
                    content=ed.get("content", ""),
                    summary=ed.get("summary", ""),
                    tags=ed.get("tags", []) + (extra_tags or []),
                    related_files=ed.get("related_files", []),
                    confidence=float(ed.get("confidence", 0.7)),
                    created_at=datetime.now().isoformat(),
                )
                entries.append(entry)

            return entries

        except json.JSONDecodeError as e:
            self._logger.warning(f"LLM 输出解析失败: {e}")
            # 尝试提取 JSON 块
            match = re.search(r'\[.*\]', analysis, re.DOTALL) if analysis else None
            if match:
                try:
                    entries_data = json.loads(match.group())
                    # 简化处理...
                    return []
                except Exception:
                    pass
            return []
        except Exception as e:
            self._logger.error(f"知识分析失败: {e}")
            return []

    def _dedup_and_store(self, entries: List[KnowledgeEntry]) -> int:
        """去重并存储"""
        count = 0
        for entry in entries:
            if entry.id not in self._entries:
                self._entries[entry.id] = entry
                count += 1
        if count > 0:
            self._save_entries()
        return count

    async def _call_llm(self, prompt: str) -> str:
        """通过 GlobalModelRouter 调用 LLM"""
        try:
            from client.src.business.global_model_router import GlobalModelRouter
            router = GlobalModelRouter.get_instance()

            response = await router.call_model(
                capability="reasoning",
                prompt=prompt,
                temperature=0.2,
            )

            # 处理思考模型
            if hasattr(response, 'thinking') and response.thinking:
                content = response.thinking
            elif hasattr(response, 'content') and response.content:
                content = response.content
            else:
                content = str(response)

            return content

        except Exception as e:
            self._logger.error(f"LLM 调用失败: {e}")
            return "[]"
