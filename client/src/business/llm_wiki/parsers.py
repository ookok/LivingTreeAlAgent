"""
LLM Wiki 模块 - 文档解析器
==========================

包含：
1. LLMDocumentParser - Markdown 文档解析器
2. PaperParser - PDF 论文解析器
3. CodeExtractor - 代码块提取器

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0 (Phase 1)
"""

import re
import logging
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
        """初始化解析器"""
        # 代码块模式
        self.code_block_pattern = r"```(\w+)?\n(.*?)```"
        self.inline_code_pattern = r"`([^`]+)`"
        
        # API 接口定义模式
        self.api_pattern = r"## (API Reference|API 接口|API).*?(?=^## |\Z)"
        
        # 标题模式
        self.heading_pattern = r"^(#+)\s+(.+)$"
        
        # 列表模式
        self.list_pattern = r"^\s*[-*+]\s+(.+)$"
        
        logger.info("LLMDocumentParser 初始化完成")
    
    def parse_markdown(self, file_path: str) -> List[DocumentChunk]:
        """
        解析 Markdown 文档
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            文档块列表
        """
        logger.info(f"解析 Markdown 文档: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = []
            
            # 1. 提取代码块
            code_chunks = self._extract_code_blocks(content, file_path)
            chunks.extend(code_chunks)
            
            # 2. 提取 API 接口定义
            api_chunks = self._extract_api_sections(content, file_path)
            chunks.extend(api_chunks)
            
            # 3. 提取普通文本（按标题分块）
            text_chunks = self._extract_text_chunks(content, file_path)
            chunks.extend(text_chunks)
            
            logger.info(f"解析完成: {len(chunks)} 个块")
            return chunks
            
        except Exception as e:
            logger.error(f"解析 Markdown 失败: {e}")
            return []
    
    def _extract_code_blocks(self, content: str, source: str) -> List[DocumentChunk]:
        """提取代码块"""
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
        """提取 API 接口定义"""
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
        """提取普通文本块（按标题分块）"""
        chunks = []
        
        # 按 ## 标题分块
        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        
        for i, section in enumerate(sections):
            if not section.strip():
                continue
            
            # 提取标题
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
        """
        解析 reStructuredText 文档
        
        Args:
            file_path: RST 文件路径
            
        Returns:
            文档块列表
        """
        logger.info(f"解析 RST 文档: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = []
            
            # 提取代码块（RST 使用 .. code-block:: 指令）
            code_pattern = r"..\s+code-block::\s*(\w+)\n\n((?:    .+\n?)*)"
            matches = re.finditer(code_pattern, content)
            
            for match in matches:
                lang = match.group(1)
                code = match.group(2).strip()
                # 移除行首的 4 个空格
                code = '\n'.join(line[4:] if line.startswith('    ') else line for line in code.split('\n'))
                
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
            
            # 提取节标题和内容（按 .. section:: 或 = 下划线分割）
            # 简化版：按空行分割段落
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
        """初始化解析器"""
        self.available_backends = self._check_backends()
        logger.info(f"PaperParser 初始化完成，可用后端: {self.available_backends}")
    
    def _check_backends(self) -> List[str]:
        """检查可用的 PDF 解析后端"""
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
        """
        解析 PDF 文件
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            解析结果字典
        """
        logger.info(f"解析 PDF: {file_path}")
        
        if not self.available_backends:
            return {
                "success": False,
                "error": "未安装 PDF 解析库，请运行: pip install PyPDF2 pdfplumber"
            }
        
        try:
            # 优先使用 pdfplumber（更好的文本提取）
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
        """使用 pdfplumber 解析"""
        import pdfplumber
        
        result = {
            "success": True,
            "text": "",
            "pages": [],
            "metadata": {},
            "chunks": []
        }
        
        with pdfplumber.open(file_path) as pdf:
            # 提取元数据
            if pdf.metadata:
                result["metadata"] = dict(pdf.metadata)
            
            # 提取每一页的文本
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
            
            # 分块（按段落）
            result["chunks"] = self._chunk_text(result["text"])
        
        logger.info(f"解析完成: {len(result['pages'])} 页")
        return result
    
    def _parse_with_pypdf2(self, file_path: str) -> Dict[str, Any]:
        """使用 PyPDF2 解析"""
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
            
            # 提取元数据
            if reader.metadata:
                result["metadata"] = dict(reader.metadata)
            
            # 提取每一页的文本
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
            
            # 分块
            result["chunks"] = self._chunk_text(result["text"])
        
        logger.info(f"解析完成: {len(result['pages'])} 页")
        return result
    
    def _chunk_text(self, text: str, max_chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """将文本分块"""
        chunks = []
        
        # 按段落分割
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
        
        # 最后一个块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": {"type": "paper_text"}
            })
        
        return chunks
    
    def extract_metadata(self, text: str) -> PaperMetadata:
        """
        从文本中提取论文元数据
        
        Args:
            text: 论文文本
            
        Returns:
            PaperMetadata 对象
        """
        metadata = PaperMetadata()
        
        # 尝试提取标题（第一行或 Abstract 前的文本）
        lines = text.split('\n')
        for i, line in enumerate(lines[:20]):  # 前 20 行
            line = line.strip()
            if len(line) > 10 and not line.startswith('Abstract'):
                metadata.title = line
                break
        
        # 尝试提取摘要
        abstract_match = re.search(r"Abstract\s*(.+?)(?=Introduction|1\s+Introduction|$)", text, re.DOTALL | re.IGNORECASE)
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
        """初始化提取器"""
        # 支持的语言
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "cpp", "c",
            "go", "rust", "bash", "shell", "sql", "html", "css",
            "json", "yaml", "xml", "markdown"
        ]
        
        logger.info("CodeExtractor 初始化完成")
    
    def extract_from_markdown(self, file_path: str) -> List[DocumentChunk]:
        """
        从 Markdown 文档中提取代码块
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            代码块列表
        """
        logger.info(f"从 Markdown 提取代码块: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = []
            
            # 提取代码块
            code_pattern = r"```(\w+)?\n(.*?)```"
            matches = re.finditer(code_pattern, content, re.DOTALL)
            
            for i, match in enumerate(matches):
                lang = match.group(1) or "text"
                code = match.group(2).strip()
                
                if code and lang in self.supported_languages:
                    # 尝试提取函数/类定义
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
        """提取函数/类定义"""
        definitions = []
        
        if language == "python":
            # 匹配 def 和 class 定义
            pattern = r"^(def|class)\s+(\w+)"
            for line in code.split('\n'):
                match = re.match(pattern, line.strip())
                if match:                    definitions.append(f"{match.group(1)} {match.group(2)}")
        
        elif language in ["javascript", "typescript"]:
            # 匹配 function 和 class 定义
            pattern = r"(function|class|const|let|var)\s+(\w+)"
            for line in code.split('\n'):
                match = re.search(pattern, line.strip())
                if match:
                    definitions.append(f"{match.group(1)} {match.group(2)}")
        
        return definitions
    
    def extract_from_directory(self, dir_path: str, file_extensions: List[str] = None) -> List[DocumentChunk]:
        """
        从目录中提取代码文件
        
        Args:
            dir_path: 目录路径
            file_extensions: 文件扩展名列表（如 [".py", ".js"]）
            
        Returns:
            代码块列表
        """
        logger.info(f"从目录提取代码: {dir_path}")
        
        if file_extensions is None:
            file_extensions = [".py", ".js", ".java", ".cpp", ".go"]
        
        chunks = []
        
        try:
            from pathlib import Path
            dir_path = Path(dir_path)
            
            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in file_extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            code = f.read()
                        
                        # 检测语言
                        lang = self._detect_language(file_path.suffix)
                        
                        # 分块（按函数/类）
                        file_chunks = self._chunk_code_by_definition(code, lang, str(file_path))
                        chunks.extend(file_chunks)
                    
                    except Exception as e:
                        logger.warning(f"读取文件失败 {file_path}: {e}")
            
            logger.info(f"提取完成: {len(chunks)} 个代码块")
            return chunks
            
        except Exception as e:
            logger.error(f"从目录提取代码失败: {e}")
            return []
    
    def _detect_language(self, extension: str) -> str:
        """根据文件扩展名检测语言"""
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
    
    def _chunk_code_by_definition(self, code: str, language: str, source: str) -> List[DocumentChunk]:
        """按函数/类定义分块"""
        chunks = []
        
        # 简化版：整个文件作为一个块
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
