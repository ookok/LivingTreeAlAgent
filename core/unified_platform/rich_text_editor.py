"""
Rich Text Editor - 富文本编辑器
===============================

支持富文本内容的编辑、解析和转换。

功能：
- HTML / Markdown / Plain Text 三种模式
- 常用格式：粗体、斜体、链接、图片、代码块、引用
- 实时预览
- 剪贴板集成

Author: Hermes Desktop Team
"""

import json
import re
import uuid
import html
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ContentFormat(Enum):
    """内容格式"""
    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN = "plain"


class TextStyle(Enum):
    """文本样式"""
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    CODE = "code"
    LINK = "link"


@dataclass
class TextSpan:
    """文本片段"""
    text: str
    style: List[TextStyle] = field(default_factory=list)
    url: Optional[str] = None  # 用于链接
    color: Optional[str] = None  # 文字颜色


@dataclass
class RichTextContent:
    """
    富文本内容

    支持三种格式：
    - HTML: <b>粗体</b>, <i>斜体</i>, <a href="">链接</a>
    - Markdown: **粗体**, *斜体*, [链接](url)
    - Plain: 无格式纯文本
    """

    content_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    format: ContentFormat = ContentFormat.HTML

    # 文本结构
    spans: List[TextSpan] = field(default_factory=list)
    paragraphs: List[List[TextSpan]] = field(default_factory=list)  # 段落列表

    # 元数据
    title: str = ""
    language: str = "zh"
    word_count: int = 0
    char_count: int = 0

    # 附件
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self._update_counts()

    def _update_counts(self):
        """更新字数统计"""
        all_text = self.plain_text
        self.char_count = len(all_text)
        self.word_count = len(re.findall(r'\w+', all_text))

    @property
    def plain_text(self) -> str:
        """获取纯文本"""
        parts = []
        for para in self.paragraphs:
            for span in para:
                parts.append(span.text)
            parts.append("\n")
        return "".join(parts).strip()

    @property
    def html(self) -> str:
        """转换为 HTML"""
        html_parts = []
        for para in self.paragraphs:
            para_html = []
            for span in para:
                text = html.escape(span.text)
                if TextStyle.BOLD in span.style:
                    text = f"<strong>{text}</strong>"
                if TextStyle.ITALIC in span.style:
                    text = f"<em>{text}</em>"
                if TextStyle.UNDERLINE in span.style:
                    text = f"<u>{text}</u>"
                if TextStyle.STRIKETHROUGH in span.style:
                    text = f"<del>{text}</del>"
                if TextStyle.CODE in span.style:
                    text = f"<code>{text}</code>"
                if TextStyle.LINK in span.style and span.url:
                    text = f'<a href="{span.url}">{text}</a>'
                if span.color:
                    text = f'<span style="color:{span.color}">{text}</span>'
                para_html.append(text)
            if para_html:
                html_parts.append("<p>" + "".join(para_html) + "</p>")
        return "\n".join(html_parts)

    @property
    def markdown(self) -> str:
        """转换为 Markdown"""
        md_parts = []
        for para in self.paragraphs:
            para_md = []
            for span in para:
                text = span.text
                if TextStyle.BOLD in span.style:
                    text = f"**{text}**"
                if TextStyle.ITALIC in span.style:
                    text = f"*{text}*"
                if TextStyle.CODE in span.style:
                    text = f"`{text}`"
                if TextStyle.LINK in span.style and span.url:
                    text = f"[{text}]({span.url})"
                para_md.append(text)
            if para_md:
                md_parts.append("".join(para_md))
        return "\n\n".join(md_parts)

    @classmethod
    def from_html(cls, html_content: str) -> "RichTextContent":
        """从 HTML 解析"""
        content = cls(format=ContentFormat.HTML)
        content.paragraphs = cls._parse_html(html_content)
        content._update_counts()
        return content

    @classmethod
    def from_markdown(cls, md_content: str) -> "RichTextContent":
        """从 Markdown 解析"""
        content = cls(format=ContentFormat.MARKDOWN)
        content.paragraphs = cls._parse_markdown(md_content)
        content._update_counts()
        return content

    @classmethod
    def from_plain(cls, plain_text: str) -> "RichTextContent":
        """从纯文本创建"""
        content = cls(format=ContentFormat.PLAIN)
        lines = plain_text.split("\n")
        content.paragraphs = [[TextSpan(text=line)] for line in lines if line.strip()]
        content._update_counts()
        return content

    @staticmethod
    def _parse_html(html_content: str) -> List[List[TextSpan]]:
        """解析 HTML 为段落列表"""
        paragraphs = []
        # 移除多余空白
        html_content = re.sub(r'\s+', ' ', html_content)
        # 按段落分割
        para_pattern = r'<p[^>]*>(.*?)</p>'
        paras = re.findall(para_pattern, html_content, re.DOTALL | re.IGNORECASE)

        for para in paras:
            spans = []
            # 解析 HTML 标签
            # 简化处理：提取纯文本
            text = re.sub(r'<[^>]+>', '', para)
            text = html.unescape(text).strip()
            if text:
                spans.append(TextSpan(text=text))
            if spans:
                paragraphs.append(spans)
        return paragraphs

    @staticmethod
    def _parse_markdown(md_content: str) -> List[List[TextSpan]]:
        """解析 Markdown 为段落列表"""
        paragraphs = []
        paras = md_content.split("\n\n")

        for para in paras:
            para = para.strip()
            if not para:
                continue

            spans = []
            # 处理行内样式
            # 1. 链接 [text](url)
            para = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f"\x00LINK_START\x00{m.group(1)}\x00LINK_END\x00[\x00URL\x00{m.group(2)}\x00URL_END\x00]", para)

            # 2. 代码 `code`
            para = re.sub(r'`([^`]+)`', lambda m: f"\x00CODE_START\x00{m.group(1)}\x00CODE_END\x00", para)

            # 3. 粗体 **text**
            para = re.sub(r'\*\*([^*]+)\*\*', lambda m: f"\x00BOLD_START\x00{m.group(1)}\x00BOLD_END\x00", para)

            # 4. 斜体 *text*
            para = re.sub(r'\*([^*]+)\*', lambda m: f"\x00ITALIC_START\x00{m.group(1)}\x00ITALIC_END\x00", para)

            # 处理纯文本片段
            parts = re.split(r'\x00', para)
            current_text = ""
            current_styles = []

            for part in parts:
                if part == "LINK_START":
                    current_styles.append(TextStyle.LINK)
                elif part == "LINK_END":
                    current_styles.remove(TextStyle.LINK)
                elif part == "CODE_START":
                    current_styles.append(TextStyle.CODE)
                elif part == "CODE_END":
                    current_styles.remove(TextStyle.CODE)
                elif part == "BOLD_START":
                    current_styles.append(TextStyle.BOLD)
                elif part == "BOLD_END":
                    current_styles.remove(TextStyle.BOLD)
                elif part == "ITALIC_START":
                    current_styles.append(TextStyle.ITALIC)
                elif part == "ITALIC_END":
                    current_styles.remove(TextStyle.ITALIC)
                elif part == "URL":
                    # 下一个文本片段是 URL
                    continue
                elif part == "URL_END":
                    continue
                elif part:
                    # 移除临时标记
                    clean = part.replace("\x00", "")
                    if clean:
                        spans.append(TextSpan(text=clean, style=list(current_styles)))

            if spans:
                paragraphs.append(spans)
        return paragraphs

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "content_id": self.content_id,
            "format": self.format.value,
            "title": self.title,
            "language": self.language,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "html": self.html,
            "markdown": self.markdown,
            "plain_text": self.plain_text,
            "attachments": self.attachments
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RichTextContent":
        """从字典反序列化"""
        content = cls()
        content.content_id = data.get("content_id", content.content_id)
        content.format = ContentFormat(data.get("format", "html"))
        content.title = data.get("title", "")
        content.language = data.get("language", "zh")
        content.attachments = data.get("attachments", [])

        # 根据 format 解析内容
        if content.format == ContentFormat.HTML:
            content.paragraphs = cls._parse_html(data.get("html", ""))
        elif content.format == ContentFormat.MARKDOWN:
            content.paragraphs = cls._parse_markdown(data.get("markdown", ""))
        else:
            content.paragraphs = [[TextSpan(text=t)] for t in data.get("plain_text", "").split("\n") if t.strip()]

        content._update_counts()
        return content


class RichTextEditor:
    """
    富文本编辑器

    提供编辑器操作接口，支持：
    - 格式化操作
    - 内容验证
    - 粘贴板处理
    """

    def __init__(self):
        self.content: Optional[RichTextContent] = None

    def create_content(
        self,
        text: str,
        format: ContentFormat = ContentFormat.HTML
    ) -> RichTextContent:
        """创建新内容"""
        if format == ContentFormat.HTML:
            self.content = RichTextContent.from_html(text)
        elif format == ContentFormat.MARKDOWN:
            self.content = RichTextContent.from_markdown(text)
        else:
            self.content = RichTextContent.from_plain(text)
        return self.content

    def append_text(
        self,
        text: str,
        styles: List[TextStyle] = None,
        url: str = None
    ):
        """追加文本"""
        if not self.content:
            self.create_content(text)
            return

        styles = styles or []
        spans = self.content.paragraphs[-1] if self.content.paragraphs else []
        spans.append(TextSpan(text=text, style=styles, url=url))

        if not self.content.paragraphs:
            self.content.paragraphs.append(spans)

        self.content._update_counts()

    def new_paragraph(self):
        """新建段落"""
        if self.content:
            self.content.paragraphs.append([])

    def apply_style(self, style: TextStyle, start: int = None, end: int = None):
        """应用样式（指定范围）"""
        if not self.content:
            return

        for para in self.content.paragraphs:
            for span in para:
                if start is None or end is None:
                    if style not in span.style:
                        span.style.append(style)
                # TODO: 实现范围样式
        self.content._update_counts()

    def insert_image(self, image_url: str, alt_text: str = ""):
        """插入图片"""
        if not self.content:
            self.create_content("")

        self.content.attachments.append({
            "type": "image",
            "url": image_url,
            "alt": alt_text
        })

    def insert_link(self, text: str, url: str):
        """插入链接"""
        if not self.content:
            self.create_content("")

        spans = self.content.paragraphs[-1] if self.content.paragraphs else []
        spans.append(TextSpan(text=text, style=[TextStyle.LINK], url=url))

        if not self.content.paragraphs:
            self.content.paragraphs.append(spans)

    def validate(self) -> tuple[bool, List[str]]:
        """验证内容"""
        errors = []

        if not self.content:
            return False, ["内容为空"]

        if self.content.char_count == 0:
            errors.append("内容不能为空")

        if self.content.char_count > 100000:
            errors.append("内容超出最大长度限制 (100000字符)")

        # 检查敏感词（可扩展）
        # ...

        return len(errors) == 0, errors

    def get_preview(self, max_length: int = 200) -> str:
        """获取预览文本"""
        if not self.content:
            return ""
        text = self.content.plain_text
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
