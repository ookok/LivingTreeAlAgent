"""
office_preview/__init__.py - Office 文档实时预览与编辑系统

借鉴 AionUi Preview Panel 设计，提供多格式文件的实时预览和编辑能力

核心功能：
- 多格式预览：Markdown / HTML / PDF / Word / Excel / PowerPoint / 图片 / 代码
- 实时编辑：Monaco 风格编辑器 + 实时预览同步
- 多标签管理：智能标签复用、版本历史、快捷键支持
- 文件追踪：自动刷新、防抖优化、变更检测
"""

import os
from typing import Optional, Dict, Any

from .models import (
    PreviewFileType, EditorMode, TabState, FileInfo, PreviewTab,
    PreviewConfig, RenderResult, PreviewHistory,
    WordPage, ExcelSheet, PowerPointSlide,
    get_file_type, is_previewable, format_file_size, format_timestamp,
    SUPPORTED_CODE_LANGUAGES
)
from .markdown_preview import MarkdownRenderer
from .office_renderer import OfficeRenderer, WordRenderer, ExcelRenderer, PowerPointRenderer
from .pdf_renderer import PDFRenderer
from .image_renderer import ImageRenderer
from .file_watcher import FileWatcher, get_file_watcher
from .tab_manager import TabManager, TabManagerConfig, get_tab_manager


class PreviewSystem:
    """
    统一预览系统入口

    整合所有渲染器，提供统一的文件预览接口
    借鉴 AionUi 的多格式预览架构
    """

    def __init__(self, config: PreviewConfig = None):
        self.config = config or PreviewConfig()
        self._renderers = {
            PreviewFileType.MARKDOWN: MarkdownRenderer(),
            PreviewFileType.HTML: MarkdownRenderer(),  # HTML 也用 Markdown 渲染器
            PreviewFileType.WORD: OfficeRenderer().word,
            PreviewFileType.EXCEL: OfficeRenderer().excel,
            PreviewFileType.POWERPOINT: OfficeRenderer().powerpoint,
            PreviewFileType.PDF: PDFRenderer(),
            PreviewFileType.IMAGE: ImageRenderer(),
            PreviewFileType.CODE: MarkdownRenderer(),  # 代码用 Markdown 渲染器
            PreviewFileType.TEXT: MarkdownRenderer(),   # 纯文本也用 Markdown
        }

    def render_file(self, file_path: str, **kwargs) -> RenderResult:
        """
        渲染文件为 HTML

        Args:
            file_path: 文件路径
            **kwargs: 传递给特定渲染器的参数
                - page: PDF 页码
                - zoom: 缩放级别
                - mode: Markdown 编辑模式 ('split'/'preview'/'edit')

        Returns:
            RenderResult 对象
        """
        if not os.path.exists(file_path):
            return RenderResult.error(f"文件不存在: {file_path}")

        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > self.config.max_file_size:
            return RenderResult.error(
                f"文件过大 ({format_file_size(file_size)})，"
                f"最大支持 {format_file_size(self.config.max_file_size)}"
            )

        file_type = get_file_type(file_path)
        renderer = self._renderers.get(file_type)

        if renderer is None:
            return RenderResult.error(f"不支持预览此文件类型: {file_type.value}")

        try:
            # 根据不同渲染器调用
            if file_type == PreviewFileType.PDF:
                return renderer.render(
                    file_path,
                    page=kwargs.get('page', 1),
                    zoom=kwargs.get('zoom', self.config.pdf_zoom)
                )
            elif file_type == PreviewFileType.IMAGE:
                return renderer.render(
                    file_path,
                    zoom=kwargs.get('zoom', self.config.image_zoom)
                )
            elif file_type == PreviewFileType.MARKDOWN:
                return renderer.render(
                    self._read_file_content(file_path),
                    mode=kwargs.get('mode', 'split')
                )
            elif file_type in (PreviewFileType.CODE, PreviewFileType.TEXT):
                return renderer.render(
                    self._read_file_content(file_path),
                    mode='edit'
                )
            else:
                return renderer.render(file_path)

        except Exception as e:
            return RenderResult.error(f"渲染失败: {str(e)}")

    def render_code_file(self, file_path: str, language: str = None) -> RenderResult:
        """渲染代码文件（带语法高亮）"""
        content = self._read_file_content(file_path)
        file_info = FileInfo.from_path(file_path)
        lang = language or file_info.language

        # 构建代码 HTML
        lines = content.split('\n')
        html_lines = []
        for i, line in enumerate(lines, 1):
            escaped = self._escape_html(line)
            html_lines.append(
                f'<div class="code-line"><span class="line-num">{i}</span>'
                f'<span class="line-content">{escaped}</span></div>'
            )

        html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
        font-size: 13px; background: #1e1e1e; color: #d4d4d4; line-height: 1.6; }}
.code-line {{ display: flex; }}
.code-line:hover {{ background: #2a2d2e; }}
.line-num {{ width: 50px; text-align: right; padding: 0 16px 0 8px;
             color: #858585; user-select: none; border-right: 1px solid #333;
             flex-shrink: 0; }}
.line-content {{ flex: 1; padding-left: 12px; white-space: pre; }}
</style></head><body>
<div class="code-content">
{chr(10).join(html_lines)}
</div>
</body></html>'''

        return RenderResult.ok(html, {
            'language': lang,
            'lines': len(lines),
            'path': file_path
        })

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return ""

    def _escape_html(self, text: str) -> str:
        return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    def get_supported_formats(self) -> Dict[str, list]:
        """获取支持的格式列表"""
        return {
            '文档': ['md', 'markdown', 'html', 'htm', 'pdf'],
            'Office': ['docx', 'doc', 'xlsx', 'xls', 'csv', 'pptx', 'ppt'],
            '代码': SUPPORTED_CODE_LANGUAGES[:15],
            '图片': ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp'],
        }

    def is_supported(self, file_path: str) -> bool:
        """检查文件是否支持预览"""
        return is_previewable(file_path)


# 全局单例
_global_preview_system: Optional[PreviewSystem] = None


def get_preview_system() -> PreviewSystem:
    """获取全局预览系统"""
    global _global_preview_system
    if _global_preview_system is None:
        _global_preview_system = PreviewSystem()
    return _global_preview_system


# 导出主要类型
__all__ = [
    # 核心系统
    'PreviewSystem', 'get_preview_system',

    # 数据模型
    'PreviewFileType', 'EditorMode', 'TabState', 'FileInfo', 'PreviewTab',
    'PreviewConfig', 'RenderResult', 'PreviewHistory',
    'WordPage', 'ExcelSheet', 'PowerPointSlide',

    # 工具函数
    'get_file_type', 'is_previewable', 'format_file_size', 'format_timestamp',
    'SUPPORTED_CODE_LANGUAGES',

    # 管理器
    'FileWatcher', 'get_file_watcher',
    'TabManager', 'TabManagerConfig', 'get_tab_manager',

    # 渲染器
    'MarkdownRenderer', 'OfficeRenderer', 'PDFRenderer', 'ImageRenderer',
]
