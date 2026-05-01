"""
视觉文档解析模块 (Visual Document Parser)
基于 Doc-V* 的 OCR-free 视觉理解设计

功能:
- PDF文档解析
- 页面布局分析
- 视觉元素检测
- 多模态内容提取
"""

import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from PIL import Image


class DocumentElementType(Enum):
    """文档元素类型"""
    TEXT = "text"
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    FORMULA = "formula"
    FOOTER = "footer"
    HEADER = "header"


class ReadingDirection(Enum):
    """阅读方向"""
    LEFT_TO_RIGHT = "ltr"
    RIGHT_TO_LEFT = "rtl"
    TOP_TO_BOTTOM = "ttb"


@dataclass
class DocumentElement:
    """文档元素"""
    type: DocumentElementType
    content: str = ""
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x1, y1, x2, y2
    page_number: int = 0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def x1(self) -> int:
        return self.bbox[0]
    
    @property
    def y1(self) -> int:
        return self.bbox[1]
    
    @property
    def x2(self) -> int:
        return self.bbox[2]
    
    @property
    def y2(self) -> int:
        return self.bbox[3]
    
    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]
    
    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


@dataclass
class PageLayout:
    """页面布局"""
    page_number: int
    width: int = 0
    height: int = 0
    elements: List[DocumentElement] = field(default_factory=list)
    reading_direction: ReadingDirection = ReadingDirection.LEFT_TO_RIGHT
    columns: int = 1
    
    def get_elements_by_type(self, element_type: DocumentElementType) -> List[DocumentElement]:
        """按类型获取元素"""
        return [e for e in self.elements if e.type == element_type]
    
    def get_text_elements(self) -> List[DocumentElement]:
        """获取所有文本元素"""
        text_types = [
            DocumentElementType.TEXT,
            DocumentElementType.TITLE,
            DocumentElementType.HEADING,
            DocumentElementType.PARAGRAPH,
            DocumentElementType.LIST
        ]
        return [e for e in self.elements if e.type in text_types]
    
    def get_visual_elements(self) -> List[DocumentElement]:
        """获取所有视觉元素"""
        visual_types = [
            DocumentElementType.IMAGE,
            DocumentElementType.CHART,
            DocumentElementType.TABLE
        ]
        return [e for e in self.elements if e.type in visual_types]


@dataclass
class DocumentInfo:
    """文档信息"""
    filename: str
    file_type: str
    total_pages: int
    title: Optional[str] = None
    author: Optional[str] = None
    language: str = "zh"
    layouts: List[PageLayout] = field(default_factory=list)


class VisualDocumentParser:
    """
    视觉文档解析器
    
    实现 Doc-V* 的 OCR-free 视觉理解思想：
    1. 跳过传统OCR，直接进行视觉理解
    2. 分析页面布局和结构
    3. 提取多模态元素
    4. 支持选择性注意力机制
    
    解析流程:
    File Loading → Layout Analysis → Element Detection → Content Extraction
    """
    
    def __init__(self):
        """初始化视觉文档解析器"""
        self._document_info: Optional[DocumentInfo] = None
        self._parsing_state = "idle"
        self._progress = 0.0
        
        print("[VisualDocumentParser] 初始化完成")
    
    @property
    def progress(self) -> float:
        """解析进度"""
        return self._progress
    
    @property
    def document_info(self) -> Optional[DocumentInfo]:
        """文档信息"""
        return self._document_info
    
    async def parse_document(self, file_path: str) -> DocumentInfo:
        """
        解析文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档信息
        """
        print(f"[VisualDocumentParser] 开始解析文档: {file_path}")
        
        self._parsing_state = "loading"
        self._progress = 0.0
        
        # 检测文件类型
        file_type = self._detect_file_type(file_path)
        print(f"[VisualDocumentParser] 文件类型: {file_type}")
        
        # 初始化文档信息
        self._document_info = DocumentInfo(
            filename=file_path,
            file_type=file_type,
            total_pages=self._estimate_pages(file_path)
        )
        
        self._progress = 0.1
        
        # 解析元数据
        await self._parse_metadata()
        self._progress = 0.2
        
        # 解析每页布局
        self._parsing_state = "analyzing"
        for page_num in range(1, self._document_info.total_pages + 1):
            layout = await self._analyze_page_layout(page_num)
            self._document_info.layouts.append(layout)
            self._progress = 0.2 + (page_num / self._document_info.total_pages) * 0.8
            
            # 模拟处理延迟
            await asyncio.sleep(0.05)
        
        self._parsing_state = "completed"
        self._progress = 1.0
        
        print(f"[VisualDocumentParser] 文档解析完成，共 {self._document_info.total_pages} 页")
        return self._document_info
    
    def _detect_file_type(self, file_path: str) -> str:
        """
        检测文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类型
        """
        if file_path.lower().endswith(".pdf"):
            return "pdf"
        elif file_path.lower().endswith((".docx", ".doc")):
            return "docx"
        elif file_path.lower().endswith((".jpg", ".jpeg", ".png", ".tiff")):
            return "image"
        elif file_path.lower().endswith(".txt"):
            return "txt"
        else:
            return "unknown"
    
    def _estimate_pages(self, file_path: str) -> int:
        """
        估算文档页数
        
        Args:
            file_path: 文件路径
            
        Returns:
            页数
        """
        import random
        # 实际实现中会解析文档获取真实页数
        file_type = self._detect_file_type(file_path)
        if file_type == "image":
            return 1
        elif file_type == "txt":
            # 估算文本文件页数（按每页50行计算）
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    return max(1, (len(lines) // 50) + 1)
            except:
                return 10
        else:
            return random.randint(1, 50)
    
    async def _parse_metadata(self):
        """解析文档元数据"""
        # 模拟元数据解析
        import random
        
        titles = [
            "Doc-V*: Coarse-to-Fine Interactive Visual Reasoning",
            "多页面文档视觉问答研究",
            "Agentic框架在文档理解中的应用",
            "基于深度学习的文档分析方法",
            "视觉问答系统设计与实现"
        ]
        
        authors = [
            "Zheng et al.",
            "研究团队",
            "AI实验室",
            "数据科学小组"
        ]
        
        self._document_info.title = random.choice(titles)
        self._document_info.author = random.choice(authors)
        self._document_info.language = "zh" if random.random() > 0.5 else "en"
    
    async def _analyze_page_layout(self, page_number: int) -> PageLayout:
        """
        分析单页布局
        
        Args:
            page_number: 页码
            
        Returns:
            页面布局
        """
        print(f"[VisualDocumentParser] 分析页面 {page_number}")
        
        # 模拟页面尺寸
        width, height = 600, 800
        
        # 生成页面元素
        elements = await self._generate_page_elements(page_number, width, height)
        
        # 检测阅读方向（默认从左到右）
        reading_direction = ReadingDirection.LEFT_TO_RIGHT
        
        # 检测列数
        columns = 1 if page_number <= 3 else (2 if random.random() > 0.3 else 1)
        
        return PageLayout(
            page_number=page_number,
            width=width,
            height=height,
            elements=elements,
            reading_direction=reading_direction,
            columns=columns
        )
    
    async def _generate_page_elements(self, page_number: int, width: int, height: int) -> List[DocumentElement]:
        """
        生成页面元素（模拟）
        
        Args:
            page_number: 页码
            width: 页面宽度
            height: 页面高度
            
        Returns:
            元素列表
        """
        import random
        import numpy as np
        
        elements = []
        
        # 根据页码生成不同类型的内容
        if page_number == 1:
            # 封面页
            elements.extend([
                DocumentElement(
                    type=DocumentElementType.TITLE,
                    content="Doc-V*: Coarse-to-Fine Interactive Visual Reasoning",
                    bbox=(50, 100, width - 50, 160),
                    page_number=page_number,
                    confidence=0.95
                ),
                DocumentElement(
                    type=DocumentElementType.TEXT,
                    content="Yuanlei Zheng, Pei Fu, Hang Li, et al.",
                    bbox=(50, 180, width - 50, 210),
                    page_number=page_number,
                    confidence=0.9
                ),
                DocumentElement(
                    type=DocumentElementType.TEXT,
                    content="arXiv:2604.13731v1 | April 2026",
                    bbox=(50, 230, width - 50, 260),
                    page_number=page_number,
                    confidence=0.85
                ),
                DocumentElement(
                    type=DocumentElementType.IMAGE,
                    content="图表: 方法架构图",
                    bbox=(100, 300, width - 100, 500),
                    page_number=page_number,
                    confidence=0.8
                )
            ])
        elif page_number == 2:
            # 摘要页
            elements.extend([
                DocumentElement(
                    type=DocumentElementType.HEADING,
                    content="Abstract",
                    bbox=(50, 50, width - 50, 80),
                    page_number=page_number,
                    confidence=0.95
                ),
                DocumentElement(
                    type=DocumentElementType.PARAGRAPH,
                    content="Multi-page Document Visual Question Answering requires reasoning over semantics, layouts, and visual elements in long, visually dense documents. Existing OCR-free methods face a trade-off between capacity and precision.",
                    bbox=(50, 100, width - 50, 180),
                    page_number=page_number,
                    confidence=0.9
                ),
                DocumentElement(
                    type=DocumentElementType.PARAGRAPH,
                    content="We propose Doc-V*, an OCR-free agentic framework that casts multi-page DocVQA as sequential evidence aggregation. Doc-V* begins with a thumbnail overview, then actively navigates via semantic retrieval and targeted page fetching.",
                    bbox=(50, 190, width - 50, 270),
                    page_number=page_number,
                    confidence=0.9
                ),
                DocumentElement(
                    type=DocumentElementType.HEADING,
                    content="1. Introduction",
                    bbox=(50, 300, width - 50, 330),
                    page_number=page_number,
                    confidence=0.95
                )
            ])
        else:
            # 正文页
            y_pos = 50
            
            # 添加标题
            section_titles = [
                "2. Related Work",
                "3. Methodology",
                "4. Experimental Setup",
                "5. Results and Analysis",
                "6. Discussion",
                "7. Conclusion"
            ]
            section_idx = min((page_number - 2) % len(section_titles), len(section_titles) - 1)
            
            elements.append(DocumentElement(
                type=DocumentElementType.HEADING,
                content=section_titles[section_idx],
                bbox=(50, y_pos, width - 50, y_pos + 30),
                page_number=page_number,
                confidence=0.95
            ))
            y_pos += 50
            
            # 添加段落
            num_paragraphs = random.randint(2, 4)
            for _ in range(num_paragraphs):
                elements.append(DocumentElement(
                    type=DocumentElementType.PARAGRAPH,
                    content=self._generate_paragraph(),
                    bbox=(50, y_pos, width - 50, y_pos + 60),
                    page_number=page_number,
                    confidence=round(random.uniform(0.8, 0.95), 2)
                ))
                y_pos += 80
            
            # 随机添加表格或图表
            if random.random() > 0.5:
                elements.append(DocumentElement(
                    type=DocumentElementType.TABLE if random.random() > 0.5 else DocumentElementType.CHART,
                    content="表格/图表内容",
                    bbox=(80, y_pos, width - 80, y_pos + 150),
                    page_number=page_number,
                    confidence=round(random.uniform(0.75, 0.9), 2)
                ))
                y_pos += 170
            
            # 添加列表
            if random.random() > 0.4:
                elements.append(DocumentElement(
                    type=DocumentElementType.LIST,
                    content="• 第一项\n• 第二项\n• 第三项",
                    bbox=(70, y_pos, width - 70, y_pos + 80),
                    page_number=page_number,
                    confidence=round(random.uniform(0.85, 0.95), 2)
                ))
        
        return elements
    
    def _generate_paragraph(self) -> str:
        """生成模拟段落文本"""
        sentences = [
            "This paper introduces a novel approach to document understanding that leverages visual reasoning capabilities.",
            "The proposed method addresses key challenges in multi-page document analysis through an agentic framework.",
            "Experimental results demonstrate significant improvements over existing baseline methods.",
            "The framework combines semantic retrieval with visual analysis for enhanced document comprehension.",
            "Selective attention mechanisms allow the system to focus on relevant information while ignoring noise.",
            "Evidence aggregation across multiple pages enables more robust reasoning and answer generation.",
            "The approach balances computational efficiency with reasoning accuracy through hierarchical processing.",
            "Qualitative analysis shows the system effectively handles complex document structures and layouts."
        ]
        
        import random
        return ' '.join(random.sample(sentences, 3))
    
    def extract_text_content(self, page_number: Optional[int] = None) -> str:
        """
        提取文本内容
        
        Args:
            page_number: 页码（None表示全部页面）
            
        Returns:
            文本内容
        """
        if not self._document_info:
            return ""
        
        result = []
        
        if page_number is not None:
            # 提取指定页面
            layouts = [l for l in self._document_info.layouts if l.page_number == page_number]
        else:
            # 提取全部页面
            layouts = self._document_info.layouts
        
        for layout in layouts:
            text_elements = layout.get_text_elements()
            # 按位置排序
            text_elements.sort(key=lambda e: (e.y1, e.x1))
            for element in text_elements:
                result.append(element.content)
        
        return '\n\n'.join(result)
    
    def extract_visual_elements(self, page_number: Optional[int] = None) -> List[DocumentElement]:
        """
        提取视觉元素
        
        Args:
            page_number: 页码（None表示全部页面）
            
        Returns:
            视觉元素列表
        """
        if not self._document_info:
            return []
        
        result = []
        
        if page_number is not None:
            layouts = [l for l in self._document_info.layouts if l.page_number == page_number]
        else:
            layouts = self._document_info.layouts
        
        for layout in layouts:
            result.extend(layout.get_visual_elements())
        
        return result
    
    def get_page_summary(self, page_number: int) -> Dict[str, Any]:
        """
        获取页面摘要
        
        Args:
            page_number: 页码
            
        Returns:
            页面摘要
        """
        if not self._document_info:
            return {}
        
        layout = next((l for l in self._document_info.layouts if l.page_number == page_number), None)
        if not layout:
            return {}
        
        return {
            "page_number": page_number,
            "element_count": len(layout.elements),
            "text_elements": len(layout.get_text_elements()),
            "visual_elements": len(layout.get_visual_elements()),
            "columns": layout.columns,
            "has_table": any(e.type == DocumentElementType.TABLE for e in layout.elements),
            "has_image": any(e.type == DocumentElementType.IMAGE for e in layout.elements),
            "has_chart": any(e.type == DocumentElementType.CHART for e in layout.elements)
        }


# 单例模式
_visual_parser_instance = None

def get_visual_document_parser() -> VisualDocumentParser:
    """获取全局视觉文档解析器实例"""
    global _visual_parser_instance
    if _visual_parser_instance is None:
        _visual_parser_instance = VisualDocumentParser()
    return _visual_parser_instance
