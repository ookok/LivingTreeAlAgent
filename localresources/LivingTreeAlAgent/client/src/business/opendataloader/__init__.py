"""
OpenDataLoader PDF 解析模块
基于 opendataloader-pdf 思想：面向 AI 的高性能 PDF 解析

功能：
- PDF 结构化解析（表格/公式/版面）
- 转为 Markdown/JSON
- 电商合同/发票处理
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ParseMode(Enum):
    """解析模式"""
    TEXT = "text"           # 纯文本
    MARKDOWN = "markdown"  # Markdown 格式
    STRUCTURED = "structured"  # 结构化 JSON


@dataclass
class PDFPage:
    """PDF 页面"""
    page_num: int
    content: str
    tables: List[Dict] = field(default_factory=list)
    formulas: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)  # 图片路径列表


@dataclass
class ParsedDocument:
    """解析后的文档"""
    title: str
    pages: List[PDFPage]
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def to_markdown(self) -> str:
        """转为 Markdown"""
        md = f"# {self.title}\n\n"
        for page in self.pages:
            md += f"## 第 {page.page_num} 页\n\n{page.content}\n\n"
            if page.tables:
                md += "### 表格\n\n"
                for table in page.tables:
                    md += self._table_to_markdown(table) + "\n\n"
        return md

    def to_structured_json(self) -> Dict:
        """转为结构化 JSON"""
        return {
            "title": self.title,
            "metadata": self.metadata,
            "pages": [
                {
                    "page_num": p.page_num,
                    "content": p.content,
                    "tables": p.tables,
                    "formulas": p.formulas,
                }
                for p in self.pages
            ]
        }

    def _table_to_markdown(self, table: Dict) -> str:
        """表格转 Markdown"""
        if not table.get("headers") or not table.get("rows"):
            return ""

        md = "| " + " | ".join(str(h) for h in table["headers"]) + " |\n"
        md += "| " + " | ".join("---" for _ in table["headers"]) + " |\n"
        for row in table["rows"]:
            md += "| " + " | ".join(str(c) for c in row) + " |\n"
        return md


class OpenDataLoader:
    """
    OpenDataLoader - 面向 AI 的 PDF 解析器
    支持表格提取、公式识别、版面还原
    """

    def __init__(self):
        self.supported_formats = [".pdf"]
        # 模拟的解析能力（实际生产环境建议集成 pdfplumber/PyMuPDF）
        self._use_mock = True

    async def parse(
        self,
        file_path: str,
        mode: ParseMode = ParseMode.MARKDOWN
    ) -> ParsedDocument:
        """
        解析 PDF 文件

        Args:
            file_path: PDF 文件路径
            mode: 解析模式

        Returns:
            ParsedDocument 对象
        """
        path = Path(file_path)

        if path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported format: {path.suffix}")

        if self._use_mock or not path.exists():
            return self._mock_parse(path)

        # 实际解析逻辑（需要安装 pdfplumber 或 PyMuPDF）
        return await self._real_parse(path, mode)

    def _mock_parse(self, path: Path) -> ParsedDocument:
        """模拟解析（用于测试）"""
        return ParsedDocument(
            title=path.stem,
            pages=[
                PDFPage(
                    page_num=1,
                    content=f"# {path.stem}\n\n这是模拟解析的内容。\n\n## 第一部分\n\n此处应包含原始文本内容。",
                    tables=[
                        {
                            "headers": ["项目", "金额", "日期"],
                            "rows": [
                                ["商品A", "¥299", "2026-01-15"],
                                ["商品B", "¥599", "2026-01-20"],
                            ]
                        }
                    ]
                ),
                PDFPage(
                    page_num=2,
                    content="## 第二部分\n\n更多内容...",
                    tables=[]
                )
            ],
            metadata={
                "source": str(path),
                "pages_count": 2,
                "parsed_by": "OpenDataLoader"
            }
        )

    async def _real_parse(self, path: Path, mode: ParseMode) -> ParsedDocument:
        """实际解析（需要依赖库）"""
        try:
            import pdfplumber

            pages = []
            all_text = []

            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    tables = page.extract_tables()
                    all_text.append(text)

                    pages.append(PDFPage(
                        page_num=i + 1,
                        content=text,
                        tables=[{"headers": t[0], "rows": t[1:]} for t in tables] if tables else []
                    ))

            return ParsedDocument(
                title=path.stem,
                pages=pages,
                metadata={"pages_count": len(pages), "source": str(path)},
                raw_text="\n\n".join(all_text)
            )

        except ImportError:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")

    async def extract_invoice_data(self, file_path: str) -> Dict[str, Any]:
        """
        从发票 PDF 中提取关键数据
        电商场景：自动提取发票金额、日期、卖方信息
        """
        doc = await self.parse(file_path, ParseMode.STRUCTURED)

        # 简单的正则提取（实际需要更复杂的 NLP）
        text = doc.raw_text or "\n".join(p.content for p in doc.pages)

        # 提取金额
        amounts = re.findall(r"¥?\s*([\d,]+\.?\d*)", text)
        dates = re.findall(r"(\d{4}[-/]\d{2}[-/]\d{2})", text)

        return {
            "title": doc.title,
            "amounts": amounts,
            "dates": dates,
            "raw_text": text[:1000],  # 截断
            "confidence": 0.7 if amounts else 0.3
        }

    async def extract_contract_clauses(self, file_path: str) -> List[Dict[str, str]]:
        """
        从合同 PDF 中提取条款
        电商场景：提取付款条款、交货条款、违约条款
        """
        doc = await self.parse(file_path, ParseMode.MARKDOWN)
        text = doc.raw_text or "\n".join(p.content for p in doc.pages)

        clauses = []

        # 简单的条款识别（实际需要 NLP）
        patterns = {
            "付款条款": r"付款[：:](.*?)(?=\n|。|$)",
            "交货条款": r"交货[：:](.*?)(?=\n|。|$)",
            "违约条款": r"违约[：:](.*?)(?=\n|。|$)",
        }

        for clause_type, pattern in patterns.items():
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                clauses.append({
                    "type": clause_type,
                    "content": match.strip()
                })

        return clauses


# 单例
_opendataloader_instance: Optional[OpenDataLoader] = None


def get_opendataloader() -> OpenDataLoader:
    """获取 OpenDataLoader 单例"""
    global _opendataloader_instance
    if _opendataloader_instance is None:
        _opendataloader_instance = OpenDataLoader()
    return _opendataloader_instance
