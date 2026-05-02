"""
LivingTree Knowledge Wiki - 文档解析器
======================================

包含：
1. LLMDocumentParser - Markdown 文档解析器
2. PaperParser - PDF 论文解析器
3. CodeExtractor - 代码块提取器

从 client/src/business/llm_wiki/parsers.py 迁移而来。
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from loguru import logger

from .models import DocumentChunk, PaperMetadata


class LLMDocumentParser:
    """
    LLM 文档解析器

    功能：
    1. 解析 Markdown 文档
    2. 提取代码块（Python、JavaScript、Bash 等）
    3. 提取 API 接口定义
    4. 识别文档结构（标题、段落、列表）
    """

    def __init__(self):
        self.code_block_pattern = r"```(\w+)?\n(.*?)```"
        self.inline_code_pattern = r"`([^`]+)`"
        self.api_pattern = r"## (API Reference|API 接口|API).*?(?=^## |\Z)"
        self.heading_pattern = r"^(#+)\s+(.+)$"
        self.list_pattern = r"^\s*[-*+]\s+(.+)$"

        logger.info("LLMDocumentParser 初始化完成")

    def parse_markdown(self, file_path: str) -> List[DocumentChunk]:
        logger.info(f"解析 Markdown 文档: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = []
            code_chunks = self._extract_code_blocks(content, file_path)
            chunks.extend(code_chunks)
            api_chunks = self._extract_api_sections(content, file_path)
            chunks.extend(api_chunks)
            text_chunks = self._extract_text_chunks(content, file_path)
            chunks.extend(text_chunks)

            logger.info(f"解析完成: {len(chunks)} 个块")
            return chunks

        except Exception as e:
            logger.error(f"解析 Markdown 失败: {e}")
            return []

    def _extract_code_blocks(self, content: str, source: str) -> List[DocumentChunk]:
        chunks = []
        matches = re.finditer(self.code_block_pattern, content, re.DOTALL)

        for match in matches:
            lang = match.group(1) or "text"
            code = match.group(2).strip()

            if code:
                chunks.append(DocumentChunk(
                    content=code,
                    metadata={
                        "language": lang,
                        "type": "code_block"
                    },
                    chunk_type="code",
                    source=source
                ))

        logger.debug(f"提取到 {len(chunks)} 个代码块")
        return chunks

    def _extract_api_sections(self, content: str, source: str) -> List[DocumentChunk]:
        chunks = []
        matches = re.finditer(self.api_pattern, content, re.DOTALL | re.MULTILINE)

        for match in matches:
            api_text = match.group(0).strip()

            if api_text:
                chunks.append(DocumentChunk(
                    content=api_text,
                    metadata={
                        "section_type": "api",
                        "type": "api_definition"
                    },
                    chunk_type="api",
                    source=source
                ))

        logger.debug(f"提取到 {len(chunks)} 个 API 定义")
        return chunks

    def _extract_text_chunks(self, content: str, source: str) -> List[DocumentChunk]:
        chunks = []
        sections = re.split(r"^## ", content, flags=re.MULTILINE)

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            lines = section.split('\n')
            title = lines[0].strip() if lines else ""
            body = '\n'.join(lines[1:]).strip()

            if body:
                chunks.append(DocumentChunk(
                    content=body,
                    metadata={
                        "section_index": i,
                        "type": "text_section"
                    },
                    chunk_type="text",
                    source=source,
                    title=title,
                    section=f"## {title}"
                ))

        logger.debug(f"提取到 {len(chunks)} 个文本块")
        return chunks

    def parse_rst(self, file_path: str) -> List[DocumentChunk]:
        logger.info(f"解析 RST 文档: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = []
            code_pattern = r"..\s+code-block::\s*(\w+)\n\n((?:    .+\n?)*)"
            matches = re.finditer(code_pattern, content)

            for match in matches:
                lang = match.group(1)
                code = match.group(2).strip()
                code = '\n'.join(
                    line[4:] if line.startswith('    ') else line
                    for line in code.split('\n')
                )

                if code:
                    chunks.append(DocumentChunk(
                        content=code,
                        metadata={
                            "language": lang,
                            "type": "code_block",
                            "format": "rst"
                        },
                        chunk_type="code",
                        source=file_path
                    ))

            paragraphs = re.split(r"\n\n+", content)
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if len(para) > 50 and not para.startswith('..'):
                    chunks.append(DocumentChunk(
                        content=para,
                        metadata={
                            "paragraph_index": i,
                            "type": "text_section",
                            "format": "rst"
                        },
                        chunk_type="text",
                        source=file_path
                    ))

            logger.info(f"解析完成: {len(chunks)} 个块")
            return chunks

        except Exception as e:
            logger.error(f"解析 RST 失败: {e}")
            return []


class PaperParser:
    """
    论文 PDF 解析器

    功能：
    1. 解析 arXiv 论文 PDF
    2. 提取摘要、引言、方法、实验、结论
    3. 提取参考文献
    4. 识别图表标题
    """

    def __init__(self):
        self.available_backends = self._check_backends()
        logger.info(f"PaperParser 初始化完成，可用后端: {self.available_backends}")

    def _check_backends(self) -> List[str]:
        backends = []

        try:
            import PyPDF2
            backends.append("pypdf2")
        except ImportError:
            pass

        try:
            import pdfplumber
            backends.append("pdfplumber")
        except ImportError:
            pass

        return backends

    def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        logger.info(f"解析 PDF: {file_path}")

        if not self.available_backends:
            return {
                "success": False,
                "error": "未安装 PDF 解析库，请运行: pip install PyPDF2 pdfplumber"
            }

        try:
            if "pdfplumber" in self.available_backends:
                return self._parse_with_pdfplumber(file_path)
            else:
                return self._parse_with_pypdf2(file_path)

        except Exception as e:
            logger.error(f"解析 PDF 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_with_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        import pdfplumber

        result = {
            "success": True,
            "text": "",
            "pages": [],
            "metadata": {},
            "chunks": []
        }

        with pdfplumber.open(file_path) as pdf:
            if pdf.metadata:
                result["metadata"] = dict(pdf.metadata)

            full_text = []
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
                    result["pages"].append({
                        "page_number": i + 1,
                        "text": page_text
                    })

            result["text"] = "\n\n".join(full_text)
            result["chunks"] = self._chunk_text(result["text"])

        logger.info(f"解析完成: {len(result['pages'])} 页")
        return result

    def _parse_with_pypdf2(self, file_path: str) -> Dict[str, Any]:
        import PyPDF2

        result = {
            "success": True,
            "text": "",
            "pages": [],
            "metadata": {},
            "chunks": []
        }

        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)

            if reader.metadata:
                result["metadata"] = dict(reader.metadata)

            full_text = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
                    result["pages"].append({
                        "page_number": i + 1,
                        "text": page_text
                    })

            result["text"] = "\n\n".join(full_text)
            result["chunks"] = self._chunk_text(result["text"])

        logger.info(f"解析完成: {len(result['pages'])} 页")
        return result

    def _chunk_text(self, text: str, max_chunk_size: int = 1000) -> List[Dict[str, Any]]:
        chunks = []
        paragraphs = re.split(r"\n\n+", text)

        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "metadata": {"type": "paper_text"}
                    })
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": {"type": "paper_text"}
            })

        return chunks

    def extract_metadata(self, text: str) -> PaperMetadata:
        metadata = PaperMetadata()

        lines = text.split('\n')
        for i, line in enumerate(lines[:20]):
            line = line.strip()
            if len(line) > 10 and not line.startswith('Abstract'):
                metadata.title = line
                break

        abstract_match = re.search(
            r"Abstract\s*(.+?)(?=Introduction|1\s+Introduction|$)",
            text, re.DOTALL | re.IGNORECASE
        )
        if abstract_match:
            metadata.abstract = abstract_match.group(1).strip()

        return metadata


class CodeExtractor:
    """
    代码块提取器

    功能：
    1. 从文档中提取代码块
    2. 识别代码语言
    3. 提取函数/类定义
    4. 生成代码摘要
    """

    def __init__(self):
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "cpp", "c",
            "go", "rust", "bash", "shell", "sql", "html", "css",
            "json", "yaml", "xml", "markdown"
        ]

        logger.info("CodeExtractor 初始化完成")

    def extract_from_markdown(self, file_path: str) -> List[DocumentChunk]:
        logger.info(f"从 Markdown 提取代码块: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = []
            code_pattern = r"```(\w+)?\n(.*?)```"
            matches = re.finditer(code_pattern, content, re.DOTALL)

            for i, match in enumerate(matches):
                lang = match.group(1) or "text"
                code = match.group(2).strip()

                if code and lang in self.supported_languages:
                    definitions = self._extract_definitions(code, lang)

                    chunks.append(DocumentChunk(
                        content=code,
                        metadata={
                            "language": lang,
                            "definitions": definitions,
                            "block_index": i
                        },
                        chunk_type="code",
                        source=file_path
                    ))

            logger.info(f"提取完成: {len(chunks)} 个代码块")
            return chunks

        except Exception as e:
            logger.error(f"提取代码块失败: {e}")
            return []

    def _extract_definitions(self, code: str, language: str) -> List[str]:
        definitions = []

        if language == "python":
            pattern = r"^(def|class)\s+(\w+)"
            for line in code.split('\n'):
                match = re.match(pattern, line.strip())
                if match:
                    definitions.append(f"{match.group(1)} {match.group(2)}")

        elif language in ["javascript", "typescript"]:
            pattern = r"(function|class|const|let|var)\s+(\w+)"
            for line in code.split('\n'):
                match = re.search(pattern, line.strip())
                if match:
                    definitions.append(f"{match.group(1)} {match.group(2)}")

        return definitions

    def extract_from_directory(
        self, dir_path: str, file_extensions: List[str] = None
    ) -> List[DocumentChunk]:
        logger.info(f"从目录提取代码: {dir_path}")

        if file_extensions is None:
            file_extensions = [".py", ".js", ".java", ".cpp", ".go"]

        chunks = []

        try:
            dir_path = Path(dir_path)

            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in file_extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            code = f.read()

                        lang = self._detect_language(file_path.suffix)
                        file_chunks = self._chunk_code_by_definition(
                            code, lang, str(file_path)
                        )
                        chunks.extend(file_chunks)

                    except Exception as e:
                        logger.warning(f"读取文件失败 {file_path}: {e}")

            logger.info(f"提取完成: {len(chunks)} 个代码块")
            return chunks

        except Exception as e:
            logger.error(f"从目录提取代码失败: {e}")
            return []

    def _detect_language(self, extension: str) -> str:
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".sh": "bash",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml"
        }
        return mapping.get(extension, "text")

    def _chunk_code_by_definition(
        self, code: str, language: str, source: str
    ) -> List[DocumentChunk]:
        chunks = []

        chunks.append(DocumentChunk(
            content=code,
            metadata={
                "language": language,
                "type": "file",
                "definitions": self._extract_definitions(code, language)
            },
            chunk_type="code",
            source=source,
            title=Path(source).name
        ))

        return chunks
