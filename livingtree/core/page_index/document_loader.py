"""
DocumentLoader - 通用文档加载器
支持 PDF, HTML, TXT, Markdown, DOCX
"""

import os
import re
from pathlib import Path
from typing import Iterator

from .models import Chunk, ChunkType, DocumentLoaderResult, DocumentType


class DocumentLoader:
    """
    通用文档加载器
    自动识别文件类型并解析
    """

    def __init__(self):
        self._chunk_counter = 0

    def load(self, file_path: str) -> DocumentLoaderResult:
        """
        加载文档并返回内容

        Args:
            file_path: 文件路径

        Returns:
            DocumentLoaderResult: 包含内容和元数据
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = path.suffix.lower()
        doc_type = self._detect_type(ext)

        if doc_type == DocumentType.PDF:
            content, metadata = self._load_pdf(path)
        elif doc_type == DocumentType.HTML:
            content, metadata = self._load_html(path)
        elif doc_type == DocumentType.TXT:
            content, metadata = self._load_txt(path)
        elif doc_type == DocumentType.MARKDOWN:
            content, metadata = self._load_markdown(path)
        elif doc_type == DocumentType.DOCX:
            content, metadata = self._load_docx(path)
        else:
            content, metadata = self._load_txt(path)

        return DocumentLoaderResult(
            content=content,
            doc_type=doc_type,
            metadata={
                "file_path": str(path),
                "file_name": path.name,
                "file_size": path.stat().st_size,
                **metadata
            }
        )

    def _detect_type(self, ext: str) -> DocumentType:
        """根据扩展名检测文档类型"""
        type_map = {
            ".pdf": DocumentType.PDF,
            ".html": DocumentType.HTML,
            ".htm": DocumentType.HTML,
            ".txt": DocumentType.TXT,
            ".md": DocumentType.MARKDOWN,
            ".markdown": DocumentType.MARKDOWN,
            ".docx": DocumentType.DOCX,
        }
        return type_map.get(ext, DocumentType.UNKNOWN)

    def _load_pdf(self, path: Path) -> tuple[str, dict]:
        """加载 PDF 文件"""
        try:
            import pypdf

            chunks = []
            metadata = {}

            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)

                # 获取 PDF 元数据
                if reader.metadata:
                    metadata["title"] = reader.metadata.get("/Title", path.stem)
                    metadata["author"] = reader.metadata.get("/Author", "")

                metadata["total_pages"] = len(reader.pages)

                # 提取每页文本
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        chunks.append({
                            "page_num": page_num,
                            "text": text.strip(),
                            "type": ChunkType.PARAGRAPH
                        })

            # 合并所有文本
            full_content = "\n\n".join([c["text"] for c in chunks])
            return full_content, metadata

        except ImportError:
            # 降级: 尝试用 OCR 或返回错误
            return self._load_txt(path)

    def _load_html(self, path: Path) -> tuple[str, dict]:
        """加载 HTML 文件"""
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self.skip_tags = {"script", "style", "nav", "header", "footer"}

            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    return
                if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                    self.text_parts.append("\n")

            def handle_data(self, data):
                if data.strip():
                    self.text_parts.append(data.strip())

            def get_text(self):
                return "\n".join(self.text_parts)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        parser = TextExtractor()
        try:
            parser.feed(html_content)
            text = parser.get_text()
        except:
            # 降级: 简单去除标签
            text = re.sub(r"<[^>]+>", "", html_content)

        # 提取标题
        title_match = re.search(r"<title>(.*?)</title>", html_content, re.I)
        title = title_match.group(1) if title_match else path.stem

        return text, {"title": title}

    def _load_txt(self, path: Path) -> tuple[str, dict]:
        """加载纯文本文件"""
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]

        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        # 尝试提取标题 (第一行或 # 开头)
        lines = content.split("\n")
        title = path.stem
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith("#"):
                title = first_line.lstrip("#").strip()
            elif len(first_line) < 100:
                title = first_line

        return content, {"title": title}

    def _load_markdown(self, path: Path) -> tuple[str, dict]:
        """加载 Markdown 文件"""
        content, metadata = self._load_txt(path)

        # 提取标题
        title_match = re.search(r"^#\s+(.+)$", content, re.M)
        if title_match:
            metadata["title"] = title_match.group(1)

        return content, metadata

    def _load_docx(self, path: Path) -> tuple[str, dict]:
        """加载 DOCX 文件"""
        try:
            from docx import Document

            doc = Document(path)
            paragraphs = []

            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())

            content = "\n\n".join(paragraphs)
            metadata = {"title": path.stem}

            return content, metadata

        except ImportError:
            # 降级: 按文本处理
            return self._load_txt(path.with_suffix(".txt"))

    def chunk_text(
        self,
        text: str,
        page_num: int = 1,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> Iterator[Chunk]:
        """
        将文本分块

        Args:
            text: 原始文本
            page_num: 页码
            chunk_size: chunk 大小 (字符数)
            overlap: 重叠大小

        Yields:
            Chunk: 文本块
        """
        self._chunk_counter = 0

        # 先尝试按段落分割
        paragraphs = self._split_paragraphs(text)

        current_chunk_text = ""
        current_position = 0

        for para in paragraphs:
            if not para.strip():
                continue

            # 如果当前 chunk 加上这个段落超过大小
            if len(current_chunk_text) + len(para) > chunk_size:
                # 保存当前 chunk
                if current_chunk_text.strip():
                    yield self._create_chunk(
                        current_chunk_text,
                        page_num,
                        current_position,
                        ChunkType.PARAGRAPH
                    )

                # 开始新的 chunk，保留 overlap
                if overlap > 0 and len(current_chunk_text) > overlap:
                    current_chunk_text = current_chunk_text[-overlap:] + "\n" + para
                    current_position += len(current_chunk_text) - len(para)
                else:
                    current_chunk_text = para
                    current_position += len(para)
            else:
                current_chunk_text += "\n" + para

        # 最后一个 chunk
        if current_chunk_text.strip():
            yield self._create_chunk(
                current_chunk_text,
                page_num,
                current_position,
                ChunkType.PARAGRAPH
            )

    def _split_paragraphs(self, text: str) -> list[str]:
        """按段落分割文本"""
        # 按换行分割，过滤空段落
        paragraphs = []
        current = []

        for line in text.split("\n"):
            line = line.strip()
            if line:
                current.append(line)
            elif current:
                paragraphs.append(" ".join(current))
                current = []

        if current:
            paragraphs.append(" ".join(current))

        return paragraphs

    def _create_chunk(
        self,
        text: str,
        page_num: int,
        position: int,
        chunk_type: ChunkType
    ) -> Chunk:
        """创建 Chunk 对象"""
        self._chunk_counter += 1

        # 检测 chunk 类型
        if text.startswith("#"):
            chunk_type = ChunkType.TITLE
        elif re.match(r"^#{1,6}\s", text):
            chunk_type = ChunkType.HEADING

        return Chunk(
            chunk_id=f"chunk_{self._chunk_counter:06d}",
            text=text[:chunk_size] if len(text) > chunk_size else text,
            chunk_type=chunk_type,
            page_num=page_num,
            position=position,
            metadata={"char_count": len(text)}
        )
