"""
Bilingual Renderer - 双语对照渲染器
===================================

将原文和译文渲染成双语对照格式。

支持布局：
- 左右对照 (Side-by-Side)
- 上下对照 (Top-Bottom)
- 交替段落 (Interleaved)
- 仅译文 (Translation Only)
- 仅原文 (Original Only)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from pathlib import Path


class RenderFormat(Enum):
    """输出格式"""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"
    TEXT = "text"  # 带标记的纯文本


class RenderLayout(Enum):
    """布局类型"""
    SIDE_BY_SIDE = "side_by_side"     # 左右对照
    TOP_BOTTOM = "top_bottom"         # 上下对照
    INTERLEAVED = "interleaved"       # 交替段落
    TRANSLATION_ONLY = "translation_only"  # 仅译文
    ORIGINAL_ONLY = "original_only"    # 仅原文


@dataclass
class BilingualSegment:
    """双语段落"""
    original: str
    translation: str
    segment_id: int
    page_hint: Optional[int] = None
    segment_type: str = "paragraph"  # paragraph, heading, table, code
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedDocument:
    """渲染后的文档"""
    format: RenderFormat
    layout: RenderLayout
    content: str
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def save(self, path: str) -> bool:
        """保存文档"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.content)
            self.file_path = path
            return True
        except Exception:
            return False


class MarkdownRenderer:
    """Markdown 双语渲染器"""

    def render(self, segments: List[BilingualSegment],
               layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> str:
        """渲染为 Markdown 格式"""

        if layout == RenderLayout.SIDE_BY_SIDE:
            return self._render_side_by_side(segments)
        elif layout == RenderLayout.TOP_BOTTOM:
            return self._render_top_bottom(segments)
        elif layout == RenderLayout.INTERLEAVED:
            return self._render_interleaved(segments)
        elif layout == RenderLayout.TRANSLATION_ONLY:
            return self._render_translation_only(segments)
        elif layout == RenderLayout.ORIGINAL_ONLY:
            return self._render_original_only(segments)
        else:
            return self._render_interleaved(segments)

    def _render_side_by_side(self, segments: List[BilingualSegment]) -> str:
        """左右对照布局"""
        lines = [
            "# 双语对照文档\n",
            "| 原文 (Original) | 译文 (Translation) |",
            "|:---|:---|"
        ]

        for seg in segments:
            if seg.segment_type == "heading":
                lines.append(f"\n## {seg.original}")
                lines.append(f"\n**翻译:** {seg.translation}\n")
            elif seg.segment_type == "code":
                lines.append(f"\n```")
                lines.append(f"原文: {seg.original}")
                lines.append(f"译文: {seg.translation}")
                lines.append(f"```\n")
            else:
                # 转义 Markdown 特殊字符
                orig = self._escape_markdown(seg.original)
                trans = self._escape_markdown(seg.translation)
                lines.append(f"| {orig} | {trans} |")

        return "\n".join(lines)

    def _render_top_bottom(self, segments: List[BilingualSegment]) -> str:
        """上下对照布局"""
        lines = [
            "# 双语对照文档\n",
            "---",
            "## 原文 (Original)",
            "---"
        ]

        for seg in segments:
            if seg.segment_type != "heading":
                lines.append(f"\n{seg.original}")

        lines.extend(["\n---", "## 译文 (Translation)", "---"])

        for seg in segments:
            if seg.segment_type != "heading":
                lines.append(f"\n{seg.translation}")

        return "\n".join(lines)

    def _render_interleaved(self, segments: List[BilingualSegment]) -> str:
        """交替段落布局"""
        lines = ["# 双语对照文档\n"]

        for seg in segments:
            if seg.segment_type == "heading":
                lines.append(f"\n## {seg.original}")
                lines.append(f"\n*{seg.translation}*\n")
            elif seg.segment_type == "code":
                lines.append(f"\n```\n# 原文\n{seg.original}\n# 译文\n{seg.translation}\n```\n")
            else:
                lines.append(f"\n**原文:** {seg.original}")
                lines.append(f"\n**译文:** {seg.translation}\n")

        return "\n".join(lines)

    def _render_translation_only(self, segments: List[BilingualSegment]) -> str:
        """仅译文"""
        lines = ["# 翻译文档\n"]

        for seg in segments:
            if seg.segment_type == "heading":
                lines.append(f"\n## {seg.translation}\n")
            else:
                lines.append(f"\n{seg.translation}\n")

        return "\n".join(lines)

    def _render_original_only(self, segments: List[BilingualSegment]) -> str:
        """仅原文"""
        lines = ["# 原文文档\n"]

        for seg in segments:
            if seg.segment_type == "heading":
                lines.append(f"\n## {seg.original}\n")
            else:
                lines.append(f"\n{seg.original}\n")

        return "\n".join(lines)

    def _escape_markdown(self, text: str) -> str:
        """转义 Markdown 特殊字符"""
        special_chars = ['|', '*', '_', '`', '#', '[', ']', '(', ')', '!']
        for char in special_chars:
            text = text.replace(char, '\\' + char)
        return text


class HTMLRenderer:
    """HTML 双语渲染器"""

    def __init__(self):
        self._css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            .bilingual-container {
                display: flex;
                gap: 20px;
            }
            .original, .translation {
                flex: 1;
                padding: 15px;
                border-radius: 8px;
            }
            .original {
                background: #f5f5f5;
            }
            .translation {
                background: #e8f4e8;
            }
            .segment {
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 5px;
            }
            .heading {
                font-weight: bold;
                font-size: 1.2em;
            }
            .code {
                font-family: 'Consolas', 'Monaco', monospace;
                background: #f0f0f0;
                padding: 10px;
                border-radius: 5px;
            }
            .segment-label {
                font-size: 0.8em;
                color: #666;
                margin-bottom: 5px;
            }
        </style>
        """

    def render(self, segments: List[BilingualSegment],
               layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> str:
        """渲染为 HTML 格式"""

        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>双语对照文档</title>",
            self._css,
            "</head>",
            "<body>",
            "<h1>双语对照文档</h1>"
        ]

        if layout == RenderLayout.SIDE_BY_SIDE:
            html.extend(self._render_side_by_side(segments))
        elif layout == RenderLayout.TOP_BOTTOM:
            html.extend(self._render_top_bottom(segments))
        elif layout == RenderLayout.INTERLEAVED:
            html.extend(self._render_interleaved(segments))
        elif layout == RenderLayout.TRANSLATION_ONLY:
            html.extend(self._render_translation_only(segments))
        elif layout == RenderLayout.ORIGINAL_ONLY:
            html.extend(self._render_original_only(segments))

        html.extend(["</body>", "</html>"])
        return "\n".join(html)

    def _render_side_by_side(self, segments: List[BilingualSegment]) -> List[str]:
        """左右对照"""
        html = [
            "<div class='bilingual-container'>",
            "<div class='original'><h3>原文 (Original)</h3>"
        ]

        for seg in segments:
            if seg.segment_type == "heading":
                html.append(f"<div class='segment heading'><div class='segment-label'>Heading</div>{self._escape_html(seg.original)}</div>")
            elif seg.segment_type == "code":
                html.append(f"<div class='segment code'><pre>{self._escape_html(seg.original)}</pre></div>")
            else:
                html.append(f"<div class='segment'>{self._escape_html(seg.original)}</div>")

        html.extend(["</div>", "<div class='translation'><h3>译文 (Translation)</h3>"])

        for seg in segments:
            if seg.segment_type == "heading":
                html.append(f"<div class='segment heading'><div class='segment-label'>标题</div>{self._escape_html(seg.translation)}</div>")
            elif seg.segment_type == "code":
                html.append(f"<div class='segment code'><pre>{self._escape_html(seg.translation)}</pre></div>")
            else:
                html.append(f"<div class='segment'>{self._escape_html(seg.translation)}</div>")

        html.extend(["</div>", "</div>"])
        return html

    def _render_top_bottom(self, segments: List[BilingualSegment]) -> List[str]:
        """上下对照"""
        html = [
            "<h2>原文 (Original)</h2>"
        ]

        for seg in segments:
            html.append(f"<div class='segment'>{self._escape_html(seg.original)}</div>")

        html.append("<hr>")
        html.append("<h2>译文 (Translation)</h2>")

        for seg in segments:
            html.append(f"<div class='segment'>{self._escape_html(seg.translation)}</div>")

        return html

    def _render_interleaved(self, segments: List[BilingualSegment]) -> List[str]:
        """交替段落"""
        html = []

        for seg in segments:
            html.append("<div class='segment'>")
            html.append(f"<div class='original'><strong>原文:</strong> {self._escape_html(seg.original)}</div>")
            html.append(f"<div class='translation'><strong>译文:</strong> {self._escape_html(seg.translation)}</div>")
            html.append("</div>")

        return html

    def _render_translation_only(self, segments: List[BilingualSegment]) -> List[str]:
        """仅译文"""
        html = ["<h2>译文 (Translation)</h2>"]
        for seg in segments:
            html.append(f"<div class='segment'>{self._escape_html(seg.translation)}</div>")
        return html

    def _render_original_only(self, segments: List[BilingualSegment]) -> List[str]:
        """仅原文"""
        html = ["<h2>原文 (Original)</h2>"]
        for seg in segments:
            html.append(f"<div class='segment'>{self._escape_html(seg.original)}</div>")
        return html

    def _escape_html(self, text: str) -> str:
        """HTML 转义"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


class JSONRenderer:
    """JSON 双语渲染器"""

    def render(self, segments: List[BilingualSegment],
               layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> str:
        """渲染为 JSON 格式"""
        import json

        data = {
            "layout": layout.value,
            "segments": [
                {
                    "id": seg.segment_id,
                    "type": seg.segment_type,
                    "original": seg.original,
                    "translation": seg.translation,
                    "page_hint": seg.page_hint,
                    "metadata": seg.metadata
                }
                for seg in segments
            ]
        }

        return json.dumps(data, ensure_ascii=False, indent=2)


class BilingualRenderer:
    """双语对照渲染器主类"""

    def __init__(self):
        self._renderers = {
            RenderFormat.MARKDOWN: MarkdownRenderer(),
            RenderFormat.HTML: HTMLRenderer(),
            RenderFormat.JSON: JSONRenderer(),
        }

    def render(self, segments: List[BilingualSegment],
               output_format: RenderFormat = RenderFormat.MARKDOWN,
               layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> RenderedDocument:
        """渲染文档"""

        renderer = self._renderers.get(output_format, self._renderers[RenderFormat.MARKDOWN])
        content = renderer.render(segments, layout)

        return RenderedDocument(
            format=output_format,
            layout=layout,
            content=content,
            metadata={
                "segment_count": len(segments),
                "layout": layout.value
            }
        )

    def render_to_file(self, segments: List[BilingualSegment],
                      output_path: str,
                      output_format: RenderFormat = RenderFormat.MARKDOWN,
                      layout: RenderLayout = RenderLayout.SIDE_BY_SIDE) -> bool:
        """渲染并保存文件"""
        rendered = self.render(segments, output_format, layout)
        return rendered.save(output_path)

    def create_segments_from_results(self, originals: List[str],
                                    translations: List[str],
                                    block_types: List[str] = None) -> List[BilingualSegment]:
        """从翻译结果创建双语段落"""
        if block_types is None:
            block_types = ["paragraph"] * len(originals)

        segments = []
        for i, (orig, trans) in enumerate(zip(originals, translations)):
            segments.append(BilingualSegment(
                original=orig,
                translation=trans,
                segment_id=i,
                segment_type=block_types[i] if i < len(block_types) else "paragraph"
            ))

        return segments

    def get_supported_formats(self) -> List[RenderFormat]:
        """获取支持的格式"""
        return list(self._renderers.keys())

    def get_supported_layouts(self) -> List[RenderLayout]:
        """获取支持的布局"""
        return list(RenderLayout)
