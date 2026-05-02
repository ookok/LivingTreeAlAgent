"""
Document Manager - 文档管理器
=============================

整合解析、检测、翻译、渲染的完整流程。
"""

import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime

from .document_parser import DocumentParser, ParsedDocument, TextBlock
from .bilingual_detector import BilingualDetector, BilingualDecision, BilingualNeed
from .translator import Translator, TranslationResult, TranslationProvider, BatchTranslationResult
from .renderer import (
    BilingualRenderer, BilingualSegment, RenderedDocument,
    RenderFormat, RenderLayout
)


@dataclass
class BilingualDocument:
    """双语文档"""
    document_id: str
    source_file: str
    source_lang: str
    target_lang: str
    original_doc: Optional[ParsedDocument] = None
    bilingual_decision: Optional[BilingualDecision] = None
    translated_segments: List[TranslationResult] = field(default_factory=list)
    bilingual_segments: List[BilingualSegment] = field(default_factory=list)
    output_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return len(self.translated_segments) > 0 and len(self.bilingual_segments) > 0

    @property
    def progress(self) -> float:
        if not self.original_doc:
            return 0.0
        total = len(self.original_doc.text_blocks)
        if total == 0:
            return 0.0
        return min(1.0, len(self.translated_segments) / total)


class DocumentManager:
    """文档管理器"""

    def __init__(self, storage_dir: str = "./bilingual_docs"):
        self.parser = DocumentParser()
        self.detector = BilingualDetector()
        self.translator = Translator()
        self.renderer = BilingualRenderer()
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._documents: Dict[str, BilingualDocument] = {}

    def create_document(self, file_path: str) -> BilingualDocument:
        """创建双语文档对象"""
        doc_id = str(uuid.uuid4())[:8]
        doc = BilingualDocument(
            document_id=doc_id,
            source_file=file_path,
            source_lang="auto",
            target_lang="zh"
        )
        self._documents[doc_id] = doc
        return doc

    def get_document(self, doc_id: str) -> Optional[BilingualDocument]:
        """获取文档"""
        return self._documents.get(doc_id)

    def list_documents(self) -> List[BilingualDocument]:
        """列出所有文档"""
        return list(self._documents.values())

    async def process_document(self,
                               file_path: str,
                               source_lang: Optional[str] = None,
                               target_lang: str = "zh",
                               force_bilingual: bool = False,
                               force_translation: bool = False,
                               progress: Optional[Callable] = None) -> BilingualDocument:
        """
        处理文档的完整流程

        Args:
            file_path: 文件路径
            source_lang: 源语言 (None = 自动检测)
            target_lang: 目标语言
            force_bilingual: 强制双语
            force_translation: 强制翻译
            progress: 进度回调

        Returns:
            BilingualDocument: 处理后的双语文档
        """
        doc = self.create_document(file_path)

        # 1. 解析文档
        if progress:
            progress(0, 100, "解析文档...")

        doc.original_doc = self.parser.parse(file_path)
        if not doc.original_doc:
            raise ValueError(f"无法解析文档: {file_path}")

        # 2. 智能检测是否需要双语
        if progress:
            progress(10, 100, "分析文档特征...")

        text = doc.original_doc.raw_text
        doc.bilingual_decision = self.detector.analyze(text, file_path)

        # 用户强制覆盖
        if force_bilingual:
            doc.bilingual_decision.need_level = BilingualNeed.REQUIRED
        elif force_translation:
            doc.bilingual_decision.need_level = BilingualNeed.RECOMMENDED

        # 确定语言
        doc.source_lang = source_lang or doc.bilingual_decision.source_lang.value
        doc.target_lang = target_lang or doc.bilingual_decision.target_lang.value

        # 3. 翻译文档
        if progress:
            progress(20, 100, "翻译文档...")

        texts_to_translate = []
        block_types = []

        for block in doc.original_doc.text_blocks:
            if block.text.strip():
                texts_to_translate.append(block.text)
                block_types.append(block.block_type.value)

        # 批量翻译
        translation_result = await self.translator.translate_document(
            texts_to_translate,
            doc.source_lang,
            doc.target_lang,
            progress=lambda current, total, msg: progress(
                20 + int(current / total * 60),
                100,
                msg
            ) if progress else None
        )

        doc.translated_segments = translation_result.results

        # 4. 构建双语段落
        if progress:
            progress(85, 100, "构建双语对照...")

        doc.bilingual_segments = self.renderer.create_segments_from_results(
            [r.original_text for r in translation_result.results],
            [r.translated_text for r in translation_result.results],
            block_types
        )

        # 5. 完成
        if progress:
            progress(100, 100, "完成!")

        return doc

    def export_document(self,
                       doc: BilingualDocument,
                       output_format: RenderFormat = RenderFormat.MARKDOWN,
                       layout: RenderLayout = RenderLayout.SIDE_BY_SIDE,
                       output_path: Optional[str] = None) -> str:
        """
        导出文档

        Returns:
            输出文件路径
        """
        if not doc.bilingual_segments:
            raise ValueError("文档没有可导出的内容")

        if output_path is None:
            # 生成默认输出路径
            source_name = Path(doc.source_file).stem
            ext = output_format.value
            output_path = str(self.storage_dir / f"{source_name}_bilingual.{ext}")

        # 渲染
        rendered = self.renderer.render(
            doc.bilingual_segments,
            output_format=output_format,
            layout=layout
        )

        # 保存
        rendered.save(output_path)
        doc.output_path = output_path

        return output_path

    def quick_process(self,
                     file_path: str,
                     output_format: RenderFormat = RenderFormat.MARKDOWN) -> str:
        """
        快速处理文档

        Returns:
            输出文件路径
        """
        doc = asyncio.run(self.process_document(file_path))
        return self.export_document(doc, output_format)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_docs = len(self._documents)
        complete_docs = sum(1 for d in self._documents.values() if d.is_complete)

        return {
            "total_documents": total_docs,
            "completed_documents": complete_docs,
            "storage_dir": str(self.storage_dir)
        }


# 便捷函数
async def translate_document(file_path: str,
                            source_lang: str = "auto",
                            target_lang: str = "zh") -> BilingualDocument:
    """快速翻译文档"""
    manager = DocumentManager()
    return await manager.process_document(
        file_path,
        source_lang=source_lang,
        target_lang=target_lang
    )


def create_bilingual_markdown(file_path: str,
                             layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> str:
    """快速创建双语 Markdown"""
    manager = DocumentManager()
    doc = asyncio.run(manager.process_document(file_path))
    return manager.export_document(doc, RenderFormat.MARKDOWN, layout)
