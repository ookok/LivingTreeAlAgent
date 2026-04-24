"""
多模态数据摄入模块

支持多种格式数据的摄入：
- PDF 文档
- 图片
- 音频
- 视频
- 网页
"""

import os
import re
import json
import base64
import asyncio
from typing import List, Dict, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod


@dataclass
class DataItem:
    """数据项"""
    item_id: str
    content: str
    source_type: str  # text, pdf, image, audio, video, url
    source_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[str] = field(default_factory=list)


@dataclass
class IngestionConfig:
    """摄入配置"""
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    supported_types: List[str] = field(default_factory=lambda: ["txt", "pdf", "md", "json", "html"])
    extract_images: bool = True
    extract_tables: bool = True


class TextExtractor:
    """文本提取器"""

    @staticmethod
    def extract_from_file(file_path: str) -> str:
        """从文件提取文本"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".txt":
            return TextExtractor._extract_txt(file_path)
        elif ext == ".md":
            return TextExtractor._extract_md(file_path)
        elif ext == ".json":
            return TextExtractor._extract_json(file_path)
        elif ext == ".html":
            return TextExtractor._extract_html(file_path)
        elif ext == ".pdf":
            return TextExtractor._extract_pdf(file_path)
        else:
            return TextExtractor._extract_txt(file_path)

    @staticmethod
    def _extract_txt(file_path: str) -> str:
        """提取纯文本"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    @staticmethod
    def _extract_md(file_path: str) -> str:
        """提取 Markdown"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 移除代码块
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        return content

    @staticmethod
    def _extract_json(file_path: str) -> str:
        """提取 JSON"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def _extract_html(file_path: str) -> str:
        """提取 HTML"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 简单提取文本
        text = re.sub(r'<[^>]+>', '', content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        """提取 PDF"""
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text())
            return "\n".join(text_parts)
        except ImportError:
            return f"[PDF 文件需要 pypdf 库: {file_path}]"


class ChunkProcessor:
    """分块处理器"""

    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()

    def chunk_text(self, text: str, chunk_size: Optional[int] = None) -> List[str]:
        """
        将文本分块

        Args:
            text: 输入文本
            chunk_size: 块大小

        Returns:
            List[str]: 文本块列表
        """
        chunk_size = chunk_size or self.config.chunk_size
        overlap = self.config.chunk_overlap

        # 清理文本
        text = self._clean_text(text)

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 尝试在句子边界分割
            if end < len(text):
                # 找最后一个句号、问号、感叹号
                boundary = max(
                    text.rfind('. ', start, end),
                    text.rfind('。', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('？', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('！', start, end),
                    text.rfind('\n', start, end)
                )
                if boundary > start:
                    end = boundary + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap
            if start <= chunks[-1].find('.') if '.' in chunks[-1] else 0:
                start = end

        return chunks

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符（保留中文、英文、数字、常用标点）
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()（）【】《》""''""''、。！？；：]', '', text)
        return text.strip()


class MultimodalIngester:
    """多模态摄入器"""

    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()
        self.text_extractor = TextExtractor()
        self.chunk_processor = ChunkProcessor(config)
        self._extractors: Dict[str, Callable] = {}
        self._register_default_extractors()

    def _register_default_extractors(self):
        """注册默认提取器"""
        self._extractors[".txt"] = lambda p: self.text_extractor.extract_from_file(p)
        self._extractors[".md"] = lambda p: self.text_extractor.extract_from_file(p)
        self._extractors[".json"] = lambda p: self.text_extractor.extract_from_file(p)
        self._extractors[".html"] = lambda p: self.text_extractor.extract_from_file(p)
        self._extractors[".htm"] = lambda p: self.text_extractor.extract_from_file(p)
        self._extractors[".pdf"] = lambda p: self.text_extractor.extract_from_file(p)

    def register_extractor(self, extension: str, extractor: Callable):
        """注册提取器"""
        self._extractors[extension] = extractor

    async def ingest_file(
        self,
        file_path: str,
        item_id: Optional[str] = None
    ) -> DataItem:
        """
        摄入文件

        Args:
            file_path: 文件路径
            item_id: 数据项 ID

        Returns:
            DataItem: 数据项
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检查文件大小
        if path.stat().st_size > self.config.max_file_size:
            raise ValueError(f"文件过大: {file_path}")

        # 提取文本
        ext = path.suffix.lower()
        extractor = self._extractors.get(ext, self.text_extractor.extract_from_file)

        try:
            content = extractor(str(path))
        except Exception as e:
            content = f"[提取失败: {str(e)}]"

        # 分块
        chunks = self.chunk_processor.chunk_text(content)

        # 创建数据项
        item = DataItem(
            item_id=item_id or self._generate_id(file_path),
            content=content,
            source_type=self._get_source_type(ext),
            source_path=str(path),
            metadata={
                "filename": path.name,
                "extension": ext,
                "size": path.stat().st_size,
                "chunk_count": len(chunks)
            },
            chunks=chunks
        )

        return item

    async def ingest_directory(
        self,
        dir_path: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None
    ) -> List[DataItem]:
        """
        摄入目录

        Args:
            dir_path: 目录路径
            recursive: 是否递归
            extensions: 文件扩展名过滤

        Returns:
            List[DataItem]: 数据项列表
        """
        items = []
        path = Path(dir_path)

        if not path.is_dir():
            raise ValueError(f"不是目录: {dir_path}")

        pattern = "**/*" if recursive else "*"

        for file_path in path.glob(pattern):
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if extensions and ext not in extensions:
                continue

            try:
                item = await self.ingest_file(str(file_path))
                items.append(item)
            except Exception as e:
                logger.info(f"[MultimodalIngester] 摄入失败 {file_path}: {e}")

        return items

    async def ingest_text(
        self,
        text: str,
        item_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataItem:
        """
        摄入纯文本

        Args:
            text: 文本内容
            item_id: 数据项 ID
            metadata: 元数据

        Returns:
            DataItem: 数据项
        """
        chunks = self.chunk_processor.chunk_text(text)

        item = DataItem(
            item_id=item_id or self._generate_id(text[:100]),
            content=text,
            source_type="text",
            source_path="",
            metadata=metadata or {},
            chunks=chunks
        )

        return item

    def _get_source_type(self, extension: str) -> str:
        """获取来源类型"""
        type_map = {
            ".txt": "text",
            ".md": "markdown",
            ".json": "json",
            ".html": "html",
            ".htm": "html",
            ".pdf": "pdf",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".gif": "image",
            ".mp3": "audio",
            ".wav": "audio",
            ".mp4": "video",
            ".avi": "video",
        }
        return type_map.get(extension, "unknown")

    def _generate_id(self, *parts: str) -> str:
        """生成 ID"""
        import hashlib
from core.logger import get_logger
logger = get_logger('cognee_memory.multimodal_ingestion')

        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]


class DataPipeline:
    """数据处理管道"""

    def __init__(self):
        self.processors: List[Callable] = []

    def add_processor(self, processor: Callable):
        """添加处理器"""
        self.processors.append(processor)

    async def process(self, item: DataItem) -> DataItem:
        """处理数据项"""
        for processor in self.processors:
            item = await processor(item)
        return item

    async def process_batch(self, items: List[DataItem]) -> List[DataItem]:
        """批量处理"""
        results = []
        for item in items:
            result = await self.process(item)
            results.append(result)
        return results


# 全局实例
_global_ingester: Optional[MultimodalIngester] = None


def get_multimodal_ingester(config: Optional[IngestionConfig] = None) -> MultimodalIngester:
    """获取多模态摄入器"""
    global _global_ingester
    if _global_ingester is None:
        _global_ingester = MultimodalIngester(config)
    return _global_ingester
