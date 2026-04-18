"""
文献管理器
全学科智能写作助手 - 引用管理模块

功能：
1. BibTeX 格式生成与管理
2. 参考文献解析
3. 多种引用格式支持（IEEE/APA/Chicago/MLA）
4. 文献数据库管理
"""

import re
import json
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CitationType(Enum):
    """文献类型"""
    ARTICLE = "article"           # 期刊文章
    BOOK = "book"                 # 图书
    INPROCEEDINGS = "inproceedings"  # 会议论文
    THESIS = "thesis"             # 学位论文
    WEBSITE = "misc"              # 网页
    TECHNICAL = "techreport"      # 技术报告
    PATENT = "misc"              # 专利


class CitationStyle(Enum):
    """引用格式"""
    IEEE = "ieee"
    APA = "apa"
    CHICAGO = "chicago"
    MLA = "mla"
    NATURE = "nature"
    CHINESE = "chinese"          # 中文 GB/T 7714


@dataclass
class Citation:
    """引用条目"""
    citation_type: CitationType
    key: str                       # BibTeX key
    title: str
    authors: list[str]             # 作者列表
    year: str
    journal: str = ""               # 期刊名
    volume: str = ""
    pages: str = ""
    publisher: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)

    # 额外字段
    issue: str = ""
    month: str = ""
    note: str = ""
    booktitle: str = ""            # 书名（会议论文用）

    def to_bibtex(self) -> str:
        """转换为 BibTeX 格式"""
        lines = [f"@{self.citation_type.value}{{{self.key},"]

        if self.title:
            lines.append(f"  title = {{{self.title}}},")
        if self.authors:
            lines.append(f"  author = {{{' and '.join(self.authors)}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.journal:
            lines.append(f"  journal = {{{self.journal}}},")
        if self.volume:
            lines.append(f"  volume = {{{self.volume}}},")
        if self.issue:
            lines.append(f"  number = {{{self.issue}}},")
        if self.pages:
            lines.append(f"  pages = {{{self.pages}}},")
        if self.publisher:
            lines.append(f"  publisher = {{{self.publisher}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        if self.booktitle:
            lines.append(f"  booktitle = {{{self.booktitle}}},")

        lines.append("}")
        return "\n".join(lines)

    def to_ieee(self) -> str:
        """IEEE 格式"""
        authors = self._format_authors_ieee()
        title = self.title
        journal = f"{self.journal}, " if self.journal else ""
        volume = f"vol. {self.volume}, " if self.volume else ""
        issue = f"no. {self.issue}, " if self.issue else ""
        pages = f"pp. {self.pages}, " if self.pages else ""
        year = f"{self.year}" if self.year else ""

        parts = [authors, title]
        if journal.strip():
            parts.append(f"{journal}{volume}{issue}{pages}{year}")
        elif self.publisher:
            parts.append(f"{self.publisher}, {year}")
        else:
            parts.append(year)

        return ", ".join(filter(None, parts)) + "."

    def to_apa(self) -> str:
        """APA 格式"""
        authors = self._format_authors_apa()
        year = f"({self.year})" if self.year else "(n.d.)"
        title = self.title
        journal = f"{self.journal}" if self.journal else ""
        volume = f", {self.volume}" if self.volume else ""
        issue = f"({self.issue})" if self.issue else ""
        pages = f", {self.pages}" if self.pages else ""

        parts = [f"{authors} {year}.", title]
        if journal:
            parts.append(f"{journal}{volume}{issue}, {pages}.")
        elif self.publisher:
            parts.append(f"{self.publisher}.")

        return " ".join(filter(None, parts))

    def to_chicago(self) -> str:
        """Chicago 格式"""
        authors = self._format_authors_chicago()
        title = f'"{self.title}"' if self.title else ""
        journal = f"{self.journal}" if self.journal else ""
        volume = f" {self.volume}" if self.volume else ""
        issue = f", no. {self.issue}" if self.issue else ""
        year = f" ({self.year})" if self.year else ""

        if journal:
            return f"{authors} {title} {journal}{volume}{issue}{year}."
        elif self.publisher:
            return f"{authors} {title}. {self.publisher}{year}."
        return f"{authors} {title}."

    def _format_authors_ieee(self) -> str:
        """IEEE 作者格式"""
        if not self.authors:
            return ""
        if len(self.authors) == 1:
            return self.authors[0]
        if len(self.authors) == 2:
            return f"{self.authors[0]} and {self.authors[1]}"
        # 3+ 作者
        return ", ".join(self.authors[:-1]) + ", and " + self.authors[-1]

    def _format_authors_apa(self) -> str:
        """APA 作者格式"""
        if not self.authors:
            return ""
        if len(self.authors) == 1:
            return self.authors[0]
        if len(self.authors) == 2:
            return f"{self.authors[0]} & {self.authors[1]}"
        # 3+ 作者
        return ", ".join(self.authors[:-1]) + ", & " + self.authors[-1]

    def _format_authors_chicago(self) -> str:
        """Chicago 作者格式"""
        if not self.authors:
            return ""
        if len(self.authors) == 1:
            return self.authors[0]
        if len(self.authors) == 2:
            return f"{self.authors[0]} and {self.authors[1]}"
        if len(self.authors) == 3:
            return f"{self.authors[0]}, {self.authors[1]}, and {self.authors[2]}"
        # 4+ 作者
        return f"{self.authors[0]} et al."


class CitationManager:
    """
    文献管理器

    功能：
    - BibTeX 管理
    - 参考文献解析
    - 多格式引用生成
    - 文献数据库
    """

    # 解析模式
    PARSE_PATTERNS = {
        'ieee': r'\[(\d+)\]\s*([^\[]+?)(?=\[|$)',
        'apa': r'([A-Z][a-z]+(?:\s+(?:et\s+al\.|and\s+[A-Z][a-z]+))?)\s*\((\d{4})\)\.\s*([^\.]+)\.',
        'numeric': r'(\d+)\.\s*([^\n]+)',
    }

    def __init__(self, db_path: str = None):
        """
        初始化文献管理器

        Args:
            db_path: 文献数据库路径
        """
        self.db_path = Path(db_path) if db_path else None
        self.citations: dict[str, Citation] = {}
        self._load_db()

    def add(self, citation: Citation) -> str:
        """
        添加引用

        Args:
            citation: 引用条目

        Returns:
            str: BibTeX key
        """
        # 生成 key
        if not citation.key:
            citation.key = self._generate_key(citation)

        self.citations[citation.key] = citation
        self._save_db()
        return citation.key

    def add_from_dict(self, data: dict) -> str:
        """
        从字典添加引用

        Args:
            data: 引用数据

        Returns:
            str: BibTeX key
        """
        citation_type = CitationType(data.get('type', 'article'))
        citation = Citation(
            citation_type=citation_type,
            key=data.get('key', ''),
            title=data.get('title', ''),
            authors=data.get('authors', []),
            year=data.get('year', ''),
            journal=data.get('journal', ''),
            volume=data.get('volume', ''),
            pages=data.get('pages', ''),
            publisher=data.get('publisher', ''),
            doi=data.get('doi', ''),
            url=data.get('url', ''),
        )
        return self.add(citation)

    def parse_and_convert(self, ref_text: str, style: CitationStyle = CitationStyle.IEEE) -> str:
        """
        解析参考文献文本并转换为 BibTeX

        Args:
            ref_text: 参考文献文本
            style: 原始格式

        Returns:
            str: BibTeX 格式
        """
        citation = self._parse_ref_text(ref_text, style)
        if citation:
            return citation.to_bibtex()
        return ""

    def _parse_ref_text(self, text: str, style: CitationStyle) -> Optional[Citation]:
        """解析参考文献文本"""
        # 简化实现 - 实际应该更智能
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 尝试提取作者、年份、标题
            # IEEE: [1] Author, "Title," Journal, vol. X, pp. Y-Z, Year.
            # APA: Author (Year). Title. Journal, X(Y), Z-W.

            citation = Citation(
                citation_type=CitationType.ARTICLE,
                key="",
                title="",
                authors=[],
                year="",
            )

            # 提取年份
            year_match = re.search(r'\((\d{4})\)|(\d{4})[a-z]?', line)
            if year_match:
                citation.year = year_match.group(1) or year_match.group(2)

            # 提取 DOI
            doi_match = re.search(r'doi[:\s]+([^\s,]+)', line, re.IGNORECASE)
            if doi_match:
                citation.doi = doi_match.group(1)

            # 提取 URL
            url_match = re.search(r'https?://[^\s]+', line)
            if url_match:
                citation.url = url_match.group(0)

            # 提取标题（引号内或斜体标记）
            title_match = re.search(r'[""]([^""]+)[""]|[\*_]([^\*_]+)[\*_]', line)
            if title_match:
                citation.title = title_match.group(1) or title_match.group(2)

            # 提取作者（在年份或标题之前）
            # 简单实现
            author_match = re.match(r'^[\[\d]+\.]?\s*([A-Z][a-z]+(?:\s*,\s*[A-Z]\.?)?(?:\s*(?:,|and|&)\s*[A-Z][a-z]+)*)', line)
            if author_match:
                author_str = author_match.group(1)
                citation.authors = [a.strip() for a in re.split(r',|and|&', author_str)]

            if citation.title or citation.year:
                return citation

        return None

    def format_citation(self, key: str, style: CitationStyle) -> str:
        """
        格式化引用

        Args:
            key: BibTeX key
            style: 引用格式

        Returns:
            str: 格式化后的引用
        """
        citation = self.citations.get(key)
        if not citation:
            return f"[{key}]"

        if style == CitationStyle.IEEE:
            return citation.to_ieee()
        elif style == CitationStyle.APA:
            return citation.to_apa()
        elif style == CitationStyle.CHICAGO:
            return citation.to_chicago()
        elif style == CitationStyle.GB7714:
            return citation.to_chicago()  # 类似 Chicago

        return citation.to_bibtex()

    def generate_bibliography(self, keys: list[str] = None, style: CitationStyle = CitationStyle.IEEE) -> str:
        """
        生成参考文献列表

        Args:
            keys: 引用的 key 列表（None 表示全部）
            style: 引用格式

        Returns:
            str: 参考文献列表
        """
        if keys:
            citations = [self.citations[k] for k in keys if k in self.citations]
        else:
            citations = list(self.citations.values())

        if style == CitationStyle.IEEE:
            # BibTeX 格式
            return "\n\n".join(c.to_bibtex() for c in citations)
        else:
            # 格式化文本
            lines = []
            for i, c in enumerate(citations, 1):
                if style == CitationStyle.APA:
                    lines.append(f"{c.to_apa()}")
                elif style == CitationStyle.CHICAGO:
                    lines.append(f"{c.to_chicago()}")
                else:
                    lines.append(f"[{i}] {c.to_ieee()}")
            return "\n".join(lines)

    def insert_citation(self, content: str, key: str, style: CitationStyle = CitationStyle.IEEE) -> str:
        """
        在文本中插入引用标记

        Args:
            content: 原文
            key: BibTeX key
            style: 引用格式

        Returns:
            str: 带引用标记的文本
        """
        citation = self.citations.get(key)
        if not citation:
            return content

        if style == CitationStyle.IEEE:
            # IEEE: 使用数字编号 [1]
            # 需要追踪引用顺序
            marker = f"[REF:{key}]"
        elif style == CitationStyle.APA:
            # APA: (Author, Year)
            author = citation.authors[0].split(',')[0] if citation.authors else "Unknown"
            year = citation.year or "n.d."
            marker = f"({author}, {year})"
        else:
            marker = f"[{key}]"

        return content.replace("此处插入引用", marker)

    def _generate_key(self, citation: Citation) -> str:
        """生成 BibTeX key"""
        # 格式: author_year_titleword
        author = ""
        if citation.authors:
            first_author = citation.authors[0].split(',')[0]
            author = re.sub(r'\s+', '', first_author)[:10].lower()

        year = citation.year if citation.year else "nd"

        title_word = ""
        if citation.title:
            words = citation.title.split()
            title_word = words[0][:10].lower() if words else ""

        return f"{author}{year}{title_word}"

    def _load_db(self):
        """加载数据库"""
        if not self.db_path or not self.db_path.exists():
            return

        try:
            data = json.loads(self.db_path.read_text(encoding='utf-8'))
            for item in data.get('citations', []):
                self.add_from_dict(item)
        except Exception:
            pass

    def _save_db(self):
        """保存数据库"""
        if not self.db_path:
            return

        data = {
            'version': '1.0',
            'exported': datetime.now().isoformat(),
            'citations': [
                {
                    'type': c.citation_type.value,
                    'key': c.key,
                    'title': c.title,
                    'authors': c.authors,
                    'year': c.year,
                    'journal': c.journal,
                    'volume': c.volume,
                    'pages': c.pages,
                    'publisher': c.publisher,
                    'doi': c.doi,
                    'url': c.url,
                }
                for c in self.citations.values()
            ]
        }

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# 单例
_manager: Optional[CitationManager] = None


def get_citation_manager(db_path: str = None) -> CitationManager:
    """获取文献管理器单例"""
    global _manager
    if _manager is None:
        _manager = CitationManager(db_path)
    return _manager
