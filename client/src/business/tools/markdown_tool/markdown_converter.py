"""
MarkdownConverter - Markdown 转换工具

支持 HTML/PDF/DOCX → Markdown 格式转换。

遵循自我进化原则：
- 自动学习不同格式的转换策略
- 从失败中学习优化转换结果
"""

import os
from typing import Dict, Any
from loguru import logger

try:
    from client.src.business.tools.base_tool import BaseTool, ToolResult
except ImportError:
    from tools.base_tool import BaseTool, ToolResult


class MarkdownConverter(BaseTool):
    """
    Markdown 转换工具
    
    支持将 HTML、PDF、DOCX 等格式转换为 Markdown 格式。
    """

    def __init__(self):
        self._logger = logger.bind(component="MarkdownConverter")
        self._conversion_history = []

    @property
    def name(self) -> str:
        return "markdown_converter"

    @property
    def description(self) -> str:
        return "将 HTML/PDF/DOCX 转换为 Markdown 格式"

    @property
    def category(self) -> str:
        return "document"

    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "input_path": "str",
            "output_format": "str",
            "output_path": "str"
        }

    async def execute(self, input_path: str, output_format: str = "markdown", 
                      output_path: str = None) -> ToolResult:
        """
        执行转换
        
        Args:
            input_path: 输入文件路径
            output_format: 输出格式（markdown/md）
            output_path: 输出文件路径（可选）
            
        Returns:
            ToolResult
        """
        self._logger.info(f"转换文件: {input_path}")

        # 检查文件是否存在
        if not os.path.exists(input_path):
            return ToolResult.error_result(f"文件不存在: {input_path}")

        # 获取文件扩展名
        _, ext = os.path.splitext(input_path)
        ext = ext.lower()

        # 根据扩展名选择转换方法
        try:
            if ext in [".html", ".htm"]:
                result = await self._convert_html_to_markdown(input_path)
            elif ext == ".pdf":
                result = await self._convert_pdf_to_markdown(input_path)
            elif ext in [".docx", ".doc"]:
                result = await self._convert_docx_to_markdown(input_path)
            else:
                return ToolResult.error_result(f"不支持的文件格式: {ext}")

            # 保存输出
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result)
                self._logger.info(f"转换结果已保存: {output_path}")
                return ToolResult.success_result(result, message=f"转换成功，已保存到 {output_path}")
            else:
                return ToolResult.success_result(result, message="转换成功")

        except Exception as e:
            self._logger.error(f"转换失败: {e}")
            return ToolResult.error_result(str(e))

    async def _convert_html_to_markdown(self, input_path: str) -> str:
        """将 HTML 转换为 Markdown"""
        try:
            import markdownify
            with open(input_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # 使用 markdownify 转换
            md_content = markdownify.markdownify(html_content, heading_style="ATX")
            return md_content
        
        except ImportError:
            # 降级方案：简单的 HTML 到 Markdown 转换
            with open(input_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return self._simple_html_to_markdown(html_content)

    async def _convert_pdf_to_markdown(self, input_path: str) -> str:
        """将 PDF 转换为 Markdown"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(input_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return self._text_to_markdown(text)
        
        except ImportError:
            return ToolResult.error_result("需要安装 PyMuPDF (pip install pymupdf)")

    async def _convert_docx_to_markdown(self, input_path: str) -> str:
        """将 DOCX 转换为 Markdown"""
        try:
            from docx import Document
            doc = Document(input_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return self._text_to_markdown(text)
        
        except ImportError:
            return ToolResult.error_result("需要安装 python-docx (pip install python-docx)")

    def _simple_html_to_markdown(self, html_content: str) -> str:
        """简单的 HTML 到 Markdown 转换"""
        import re
        
        # 移除脚本和样式
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        
        # 转换标题
        for i in range(6, 0, -1):
            html_content = re.sub(f'<h{i}[^>]*>(.*?)</h{i}>', '#' * i + r' \1\n\n', html_content)
        
        # 转换段落
        html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content)
        
        # 转换粗体和斜体
        html_content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_content)
        html_content = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html_content)
        html_content = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_content)
        html_content = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html_content)
        
        # 转换链接
        html_content = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', html_content)
        
        # 转换列表
        html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', html_content)
        
        # 移除其他标签
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # 清理空白
        html_content = re.sub(r'\n\s*\n', '\n\n', html_content)
        
        return html_content.strip()

    def _text_to_markdown(self, text: str) -> str:
        """将纯文本转换为 Markdown"""
        # 简单处理：保持原样返回
        return text