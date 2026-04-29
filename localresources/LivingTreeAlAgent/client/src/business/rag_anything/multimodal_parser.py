"""
多模态文档解析模块

支持多模态文档处理：
- 文本解析
- 图像处理
- 表格解析
- 公式解析
"""

import re
import time
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ============ 内容类型 ============

class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    MIXED = "mixed"


# ============ 解析结果 ============

@dataclass
class TextContent:
    """文本内容"""
    raw_text: str
    paragraphs: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageContent:
    """图像内容"""
    image_id: str
    image_data: Any  # 可以是 bytes 或路径
    caption: str = ""
    description: str = ""
    entities: List[str] = field(default_factory=list)
    relationships: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableContent:
    """表格内容"""
    table_id: str
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    summary: str = ""
    logical_relations: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EquationContent:
    """公式内容"""
    equation_id: str
    latex: str = ""
    description: str = ""
    variables: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultimodalContent:
    """多模态内容"""
    source: str
    content_type: ContentType
    text: Optional[TextContent] = None
    images: List[ImageContent] = field(default_factory=list)
    tables: List[TableContent] = field(default_factory=list)
    equations: List[EquationContent] = field(default_factory=list)
    parsed_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============ 文本解析器 ============

class TextParser:
    """
    文本解析器
    
    提取文本内容、段落和标题
    """
    
    def __init__(self):
        self.min_paragraph_length = 50
    
    def parse(self, text: str, source: str = "") -> TextContent:
        """
        解析文本
        
        Args:
            text: 原始文本
            source: 来源
            
        Returns:
            TextContent: 解析后的文本内容
        """
        # 分割段落
        paragraphs = self._split_paragraphs(text)
        
        # 提取标题
        headings = self._extract_headings(text)
        
        return TextContent(
            raw_text=text,
            paragraphs=paragraphs,
            headings=headings,
            metadata={
                "source": source,
                "paragraph_count": len(paragraphs),
                "heading_count": len(headings),
                "char_count": len(text),
            }
        )
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """分割段落"""
        # 按换行分割
        lines = text.split("\n")
        paragraphs = []
        current = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    para = " ".join(current)
                    if len(para) >= self.min_paragraph_length:
                        paragraphs.append(para)
                    current = []
            else:
                current.append(stripped)
        
        # 处理最后一个段落
        if current:
            para = " ".join(current)
            if len(para) >= self.min_paragraph_length:
                paragraphs.append(para)
        
        return paragraphs
    
    def _extract_headings(self, text: str) -> List[str]:
        """提取标题"""
        headings = []
        
        # Markdown 标题
        md_pattern = r'^#+\s+(.+)$'
        for line in text.split("\n"):
            match = re.match(md_pattern, line.strip())
            if match:
                headings.append(match.group(1).strip())
        
        # 数字标题 (1. xxx, 1.1 xxx)
        num_pattern = r'^\d+(?:\.\d+)*\s+(.+)$'
        for line in text.split("\n"):
            match = re.match(num_pattern, line.strip())
            if match and len(line.strip()) < 100:  # 标题不会太长
                headings.append(match.group(1).strip())
        
        return headings


# ============ 图像解析器 ============

class ImageParser:
    """
    图像解析器
    
    提取图像内容和语义信息
    """
    
    def __init__(self, vlm_client: Optional[Callable] = None):
        self.vlm_client = vlm_client
    
    async def parse(
        self,
        image_data: Any,
        context: str = ""
    ) -> ImageContent:
        """
        解析图像
        
        Args:
            image_data: 图像数据
            context: 上下文信息
            
        Returns:
            ImageContent: 解析后的图像内容
        """
        image_id = f"img_{int(time.time() * 1000)}"
        
        # 基础解析
        caption = self._generate_caption(image_data)
        description = await self._generate_description(image_data, context)
        entities = self._extract_entities(description)
        relationships = self._extract_relationships(description)
        
        return ImageContent(
            image_id=image_id,
            image_data=image_data,
            caption=caption,
            description=description,
            entities=entities,
            relationships=relationships,
            metadata={
                "parsed_at": time.time(),
                "has_context": bool(context),
            }
        )
    
    def _generate_caption(self, image_data: Any) -> str:
        """生成图像标题"""
        # 简单实现：基于图像数据生成
        if isinstance(image_data, bytes):
            size = len(image_data)
            return f"Image ({size} bytes)"
        elif isinstance(image_data, str):
            return f"Image from {image_data}"
        else:
            return "Image"
    
    async def _generate_description(self, image_data: Any, context: str) -> str:
        """生成图像描述"""
        if self.vlm_client:
            # 使用 VLM 生成描述
            try:
                description = await self.vlm_client.analyze_image(image_data, context)
                return description
            except Exception as e:
                return f"Image with context: {context[:100]}"
        else:
            return f"Image related to: {context[:100]}" if context else "Image content"
    
    def _extract_entities(self, description: str) -> List[str]:
        """提取实体"""
        # 简单实现：提取名词
        words = description.split()
        entities = [w for w in words if w and w[0].isupper()]
        return list(set(entities))[:10]  # 最多 10 个实体
    
    def _extract_relationships(self, description: str) -> List[Dict[str, str]]:
        """提取关系"""
        # 简单实现：基于动词短语
        relationships = []
        verbs = ["is", "has", "shows", "contains", "displays"]
        words = description.split()
        
        for i, word in enumerate(words):
            if word.lower() in verbs and i + 1 < len(words):
                relationships.append({
                    "subject": " ".join(words[max(0, i-2):i]),
                    "predicate": word,
                    "object": " ".join(words[i+1:min(i+4, len(words))]),
                })
        
        return relationships[:5]  # 最多 5 个关系


# ============ 表格解析器 ============

class TableParser:
    """
    表格解析器
    
    解析表格结构和逻辑关系
    """
    
    def __init__(self):
        self.delimiters = [",", "\t", "|"]
    
    def parse(self, table_text: str) -> TableContent:
        """
        解析表格
        
        Args:
            table_text: 表格文本
            
        Returns:
            TableContent: 解析后的表格内容
        """
        table_id = f"table_{int(time.time() * 1000)}"
        
        # 检测分隔符
        delimiter = self._detect_delimiter(table_text)
        
        # 解析行列
        rows = self._parse_rows(table_text, delimiter)
        
        if not rows:
            return TableContent(
                table_id=table_id,
                headers=[],
                rows=[],
                summary="Empty table",
            )
        
        # 第一行作为表头
        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []
        
        # 生成摘要
        summary = self._generate_summary(headers, data_rows)
        
        # 提取逻辑关系
        logical_relations = self._extract_relations(headers, data_rows)
        
        return TableContent(
            table_id=table_id,
            headers=headers,
            rows=data_rows,
            summary=summary,
            logical_relations=logical_relations,
            metadata={
                "row_count": len(data_rows),
                "col_count": len(headers),
                "delimiter": delimiter,
            }
        )
    
    def _detect_delimiter(self, text: str) -> str:
        """检测分隔符"""
        for delim in self.delimiters:
            if delim in text:
                return delim
        return ","
    
    def _parse_rows(self, text: str, delimiter: str) -> List[List[str]]:
        """解析行列"""
        lines = text.strip().split("\n")
        rows = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 分割单元格
            if delimiter == ",":
                # CSV 格式处理
                cells = self._split_csv_line(line)
            else:
                cells = [c.strip() for c in line.split(delimiter)]
            
            if cells:
                rows.append(cells)
        
        return rows
    
    def _split_csv_line(self, line: str) -> List[str]:
        """分割 CSV 行"""
        cells = []
        in_quotes = False
        current = []
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                cells.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        
        if current:
            cells.append("".join(current).strip())
        
        return cells
    
    def _generate_summary(self, headers: List[str], rows: List[List[str]]) -> str:
        """生成摘要"""
        if not headers:
            return "Empty table"
        
        summary = f"Table with {len(rows)} rows, columns: {', '.join(headers[:5])}"
        if len(headers) > 5:
            summary += f" and {len(headers) - 5} more"
        
        return summary
    
    def _extract_relations(self, headers: List[str], rows: List[List[str]]) -> List[Dict[str, str]]:
        """提取逻辑关系"""
        relations = []
        
        # 基于列名提取关系
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            if "total" in header_lower or "sum" in header_lower:
                # 总计关系
                relations.append({
                    "type": "aggregation",
                    "source": header,
                    "target": f"sum of {', '.join(headers[:i])}",
                })
            elif "average" in header_lower or "avg" in header_lower:
                # 平均关系
                relations.append({
                    "type": "aggregation",
                    "source": header,
                    "target": f"average of {', '.join(headers[:i])}",
                })
            elif "id" in header_lower or "key" in header_lower:
                # 键关系
                relations.append({
                    "type": "key",
                    "source": header,
                    "target": "primary identifier",
                })
        
        return relations


# ============ 公式解析器 ============

class EquationParser:
    """
    公式解析器
    
    解析数学公式和逻辑关系
    """
    
    def __init__(self):
        self.latex_patterns = [
            r'\$[^\$]+\$',           # 行内公式
            r'\$\$[^\$]+\$\$',       # 块公式
            r'\\begin\{[^}]+\}.*?\\end\{[^}]+\}',  # LaTeX 环境
        ]
    
    def parse(self, text: str) -> List[EquationContent]:
        """
        解析公式
        
        Args:
            text: 包含公式的文本
            
        Returns:
            List[EquationContent]: 解析后的公式列表
        """
        equations = []
        
        # 提取 LaTeX 公式
        latex_formulas = self._extract_latex(text)
        
        for latex in latex_formulas:
            equation_id = f"eq_{len(equations)}_{int(time.time() * 1000)}"
            
            # 解析变量
            variables = self._extract_variables(latex)
            
            # 提取依赖
            dependencies = self._extract_dependencies(latex, equations)
            
            # 生成描述
            description = self._generate_description(latex, variables)
            
            equations.append(EquationContent(
                equation_id=equation_id,
                latex=latex,
                description=description,
                variables=variables,
                dependencies=dependencies,
                metadata={
                    "length": len(latex),
                    "complexity": self._estimate_complexity(latex),
                }
            ))
        
        return equations
    
    def _extract_latex(self, text: str) -> List[str]:
        """提取 LaTeX 公式"""
        formulas = []
        
        for pattern in self.latex_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            formulas.extend(matches)
        
        # 去重
        return list(set(formulas))
    
    def _extract_variables(self, latex: str) -> List[str]:
        """提取变量"""
        # 匹配字母变量（排除命令）
        variables = re.findall(r'(?<![\\a-zA-Z])([a-zA-Z](?:[a-zA-Z]|\d)*)(?![a-zA-Z])', latex)
        
        # 过滤常见命令
        commands = {"frac", "sqrt", "sum", "int", "lim", "sin", "cos", "tan", "log", "ln", "exp"}
        variables = [v for v in variables if v.lower() not in commands]
        
        return list(set(variables))
    
    def _extract_dependencies(self, latex: str, previous_equations: List[EquationContent]) -> List[str]:
        """提取依赖"""
        deps = []
        
        # 检查是否引用了之前的公式
        for eq in previous_equations:
            for var in eq.variables:
                if var in latex:
                    deps.append(eq.equation_id)
                    break
        
        return deps
    
    def _generate_description(self, latex: str, variables: List[str]) -> str:
        """生成描述"""
        desc = f"Equation with {len(variables)} variables: {', '.join(variables[:5])}"
        if len(variables) > 5:
            desc += f" and {len(variables) - 5} more"
        return desc
    
    def _estimate_complexity(self, latex: str) -> str:
        """估计复杂度"""
        depth = latex.count("{") + latex.count("(")
        
        if depth <= 2:
            return "simple"
        elif depth <= 5:
            return "moderate"
        else:
            return "complex"


# ============ 多模态文档解析器 ============

class MultimodalDocumentParser:
    """
    多模态文档解析器
    
    统一处理多模态文档
    """
    
    def __init__(
        self,
        text_parser: Optional[TextParser] = None,
        image_parser: Optional[ImageParser] = None,
        table_parser: Optional[TableParser] = None,
        equation_parser: Optional[EquationParser] = None,
    ):
        self.text_parser = text_parser or TextParser()
        self.image_parser = image_parser or ImageParser()
        self.table_parser = table_parser or TableParser()
        self.equation_parser = equation_parser or EquationParser()
    
    async def parse_document(
        self,
        content: Any,
        content_type: str = "text",
        source: str = "",
        context: str = "",
    ) -> MultimodalContent:
        """
        解析文档
        
        Args:
            content: 文档内容
            content_type: 内容类型 (text, pdf, docx, image)
            source: 来源
            context: 上下文信息
            
        Returns:
            MultimodalContent: 多模态内容
        """
        # 基础文本解析
        text_content = None
        images = []
        tables = []
        equations = []
        
        if content_type in ["text", "pdf", "docx"]:
            # 文本内容解析
            text_str = self._extract_text(content)
            text_content = self.text_parser.parse(text_str, source)
            
            # 提取公式
            equations = self.equation_parser.parse(text_str)
            
            # 尝试提取表格
            tables = self._extract_tables(text_str)
            
            # 检测图像引用
            image_refs = self._extract_image_refs(text_str)
            for ref in image_refs:
                image_content = await self.image_parser.parse(ref, context)
                images.append(image_content)
        
        elif content_type == "image":
            # 图像解析
            image_content = await self.image_parser.parse(content, context)
            images.append(image_content)
        
        # 判断内容类型
        final_content_type = self._determine_content_type(
            text_content, images, tables, equations
        )
        
        return MultimodalContent(
            source=source,
            content_type=final_content_type,
            text=text_content,
            images=images,
            tables=tables,
            equations=equations,
            metadata={
                "content_type_input": content_type,
                "has_text": text_content is not None,
                "image_count": len(images),
                "table_count": len(tables),
                "equation_count": len(equations),
            }
        )
    
    def _extract_text(self, content: Any) -> str:
        """提取文本"""
        if isinstance(content, str):
            return content
        elif hasattr(content, "text"):
            return content.text
        else:
            return str(content)
    
    def _extract_tables(self, text: str) -> List[TableContent]:
        """提取表格"""
        tables = []
        
        # 简单的表格检测：多行类似格式
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 检测是否为表格行（包含多个分隔符）
            if line.count(",") >= 2 or line.count("\t") >= 2:
                # 收集连续的行
                table_lines = [line]
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.count(",") >= 2 or next_line.count("\t") >= 2:
                        table_lines.append(next_line)
                        j += 1
                    else:
                        break
                
                if len(table_lines) >= 2:
                    table_text = "\n".join(table_lines)
                    table = self.table_parser.parse(table_text)
                    tables.append(table)
                
                i = j
            else:
                i += 1
        
        return tables
    
    def _extract_image_refs(self, text: str) -> List[str]:
        """提取图像引用"""
        image_patterns = [
            r'!\[.*?\]\((.*?)\)',      # Markdown 图片
            r'<img.*?src=["\'](.*?)["\']',  # HTML img
            r'(https?://\S+\.(?:jpg|jpeg|png|gif|webp))',  # URL
        ]
        
        refs = []
        for pattern in image_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            refs.extend(matches)
        
        return refs
    
    def _determine_content_type(
        self,
        text: Optional[TextContent],
        images: List[ImageContent],
        tables: List[TableContent],
        equations: List[EquationContent],
    ) -> ContentType:
        """判断内容类型"""
        if text and images and tables:
            return ContentType.MIXED
        elif images:
            return ContentType.IMAGE
        elif tables:
            return ContentType.TABLE
        elif equations:
            return ContentType.EQUATION
        elif text:
            return ContentType.TEXT
        else:
            return ContentType.TEXT


# ============ 导出 ============

__all__ = [
    "ContentType",
    "TextContent",
    "ImageContent",
    "TableContent",
    "EquationContent",
    "MultimodalContent",
    "TextParser",
    "ImageParser",
    "TableParser",
    "EquationParser",
    "MultimodalDocumentParser",
]
