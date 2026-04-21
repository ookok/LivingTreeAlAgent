"""
office_preview/markdown_preview.py - Markdown 实时预览引擎

借鉴 AionUi 的 Markdown 分屏编辑 + 实时预览设计
支持三种编辑模式：编辑/预览分屏 / 仅编辑 / 仅预览
"""

import re
import html
from typing import List, Optional, Dict, Tuple
from .models import RenderResult


class MarkdownRenderer:
    """Markdown 渲染引擎 - 支持 GitHub Flavored Markdown + 数学公式 + UML"""

    # 代码块语言映射
    LANG_MAP = {
        'js': 'javascript', 'ts': 'typescript', 'py': 'python',
        'rb': 'ruby', 'cs': 'csharp', 'c++': 'cpp', 'sh': 'bash',
        'yml': 'yaml', 'docker': 'dockerfile', 'md': 'markdown'
    }

    def __init__(self):
        self._setup_regex()

    def _setup_regex(self):
        """编译常用正则表达式"""
        # 代码块
        self.code_block_re = re.compile(
            r'```(\w*)\s*([\s\S]*?)```',
            re.MULTILINE
        )
        # 行内代码
        self.inline_code_re = re.compile(r'`([^`]+)`')
        # 数学公式（行内）
        self.math_inline_re = re.compile(r'\$([^\$]+)\$')
        # 数学公式（块级）
        self.math_block_re = re.compile(r'\$\$([^\$]+)\$\$', re.DOTALL)
        # 表格
        self.table_re = re.compile(
            r'\|(.+)\|[\r\n]+\|[\s\-:|]+\|[\r\n]+((?:\|.+\|[\r\n]*)+)'
        )
        # 链接
        self.link_re = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
        # 图片
        self.image_re = re.compile(r'!\[([^\]]*)\]\(([^\)]+)\)')
        # 标题
        self.heading_re = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        # 任务列表
        self.task_re = re.compile(r'^(\s*[-*+]\s*\[[ xX]\])\s+(.+)$', re.MULTILINE)
        # 引用块
        self.blockquote_re = re.compile(r'^>\s+(.+)$', re.MULTILINE)

    def render(self, content: str, mode: str = 'split') -> RenderResult:
        """
        渲染 Markdown 内容

        mode: 'split' (分屏) / 'preview' (仅预览) / 'edit' (仅编辑源码)
        """
        try:
            if mode == 'edit':
                # 仅编辑模式，返回转义后的 HTML
                html_content = self._render_source(content)
                return RenderResult.ok(html_content)

            # 预处理
            lines = content.split('\n')
            processed = self._preprocess(content)

            # 渲染 HTML
            html_parts = []
            html_parts.append(self._render_header())
            html_parts.append(self._render_body(processed, mode))
            html_parts.append(self._render_footer())

            full_html = '\n'.join(html_parts)
            return RenderResult.ok(full_html, {'mode': mode, 'line_count': len(lines)})

        except Exception as e:
            return RenderResult.error(f"Markdown 渲染错误: {str(e)}")

    def _preprocess(self, content: str) -> str:
        """预处理：处理各种 Markdown 语法"""
        # 转义 HTML
        content = self._escape_html(content)

        # 还原部分 Markdown 符号
        content = self._restore_markdown_symbols(content)

        return content

    def _escape_html(self, content: str) -> str:
        """转义 HTML 特殊字符（保留 Markdown 语法）"""
        # 先处理代码块（代码块内不转义）
        code_blocks = []
        for i, match in enumerate(self.code_block_re.finditer(content)):
            placeholder = f'__CODEBLOCK_{i}__'
            code_blocks.append((placeholder, match.group(0)))
            content = content.replace(match.group(0), placeholder)

        # 转义剩余 HTML
        content = html.escape(content)

        # 还原代码块
        for placeholder, code in code_blocks:
            content = content.replace(placeholder, code)

        return content

    def _restore_markdown_symbols(self, content: str) -> str:
        """还原 Markdown 语法符号"""
        # 还原链接和图片中的 URL
        content = self.link_re.sub(r'<a href="\2">\1</a>', content)
        content = self.image_re.sub(
            r'<img src="\2" alt="\1" style="max-width:100%;border-radius:4px;">',
            content
        )
        return content

    def _render_source(self, content: str) -> str:
        """渲染源码视图（编辑模式）"""
        lines = content.split('\n')
        html_lines = []
        for i, line in enumerate(lines, 1):
            escaped = html.escape(line)
            html_lines.append(
                f'<div class="code-line"><span class="line-num">{i}</span>'
                f'<span class="line-content">{escaped}</span></div>'
            )
        return '\n'.join(html_lines)

    def _render_body(self, content: str, mode: str) -> str:
        """渲染主体内容"""
        lines = content.split('\n')
        html_lines = []
        in_code_block = False
        in_blockquote = False
        in_list = False
        in_table = False
        table_buffer = []

        for line in lines:
            # 代码块处理
            if line.strip().startswith('```'):
                if not in_code_block:
                    lang = line.strip()[3:].strip()
                    lang = self.LANG_MAP.get(lang, lang or 'plaintext')
                    html_lines.append(f'<pre class="code-block" data-lang="{lang}"><code>')
                    in_code_block = True
                else:
                    html_lines.append('</code></pre>')
                    in_code_block = False
                    continue

            if in_code_block:
                escaped = html.escape(line)
                html_lines.append(escaped)
                continue

            # 块引用
            if line.strip().startswith('>'):
                if not in_blockquote:
                    html_lines.append('<blockquote>')
                    in_blockquote = True
                html_lines.append(f'<p>{self._render_inline(line[1:].strip())}</p>')
                continue
            elif in_blockquote:
                html_lines.append('</blockquote>')
                in_blockquote = False

            # 标题
            heading_match = self.heading_re.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                html_lines.append(f'<h{level}>{self._render_inline(text)}</h{level}>')
                continue

            # 水平线
            if re.match(r'^[-*_]{3,}$', line.strip()):
                html_lines.append('<hr/>')
                continue

            # 表格
            if line.strip().startswith('|'):
                table_buffer.append(line)
                continue
            elif table_buffer and not line.strip().startswith('|'):
                html_lines.append(self._render_table(table_buffer))
                table_buffer = []
                in_table = False

            # 列表项
            list_match = re.match(r'^(\s*)([-*+]|(\d+)\.)\s+(.+)$', line)
            if list_match:
                indent = len(list_match.group(1))
                marker = list_match.group(2)
                text = list_match.group(4)

                if marker in ['-', '*', '+']:
                    # 无序列表
                    checked = ''
                    if text.startswith('[ ] ') or text.startswith('[x] ') or text.startswith('[X] '):
                        checked = text[:4]
                        text = text[4:]
                        checked_html = '☐' if 'x' not in checked.lower() else '☑'
                        html_lines.append(
                            f'<div class="task-item"><span class="task-check">{checked_html}</span>'
                            f'<span class="task-text">{self._render_inline(text)}</span></div>'
                        )
                    else:
                        html_lines.append(
                            f'<li class="ul-item">{self._render_inline(text)}</li>'
                        )
                else:
                    # 有序列表
                    html_lines.append(
                        f'<li class="ol-item">{self._render_inline(text)}</li>'
                    )
                continue

            # 分割线判断（基于前后文）
            stripped = line.strip()
            if not stripped:
                html_lines.append('<br/>')
                continue

            # 段落
            html_lines.append(f'<p>{self._render_inline(line)}</p>')

        # 处理未结束的表格
        if table_buffer:
            html_lines.append(self._render_table(table_buffer))

        return '\n'.join(html_lines)

    def _render_inline(self, text: str) -> str:
        """渲染行内元素"""
        # 数学公式（行内）
        text = self.math_inline_re.sub(r'<span class="math-inline">$\1$</span>', text)
        # 数学公式（块级）
        text = self.math_block_re.sub(r'<div class="math-block">$$\1$$</div>', text)

        # 代码（行内）
        text = self.inline_code_re.sub(
            r'<code class="inline-code">\1</code>', text
        )

        # 加粗
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)

        # 斜体
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)

        # 删除线
        text = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', text)

        # 自动链接
        text = re.sub(
            r'<(https?://[^>]+)>',
            r'<a href="\1" target="_blank" class="ext-link">\1</a>',
            text
        )

        return text

    def _render_table(self, table_lines: List[str]) -> str:
        """渲染表格"""
        if len(table_lines) < 2:
            return ''

        # 解析表头
        headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
        html_parts = ['<table class="md-table">']

        # 表头
        html_parts.append('<thead><tr>')
        for h in headers:
            html_parts.append(f'<th>{self._render_inline(h)}</th>')
        html_parts.append('</tr></thead>')

        # 表体（跳过分隔行）
        html_parts.append('<tbody>')
        for line in table_lines[2:]:
            cells = [c.strip() for c in line.strip('|').split('|')]
            html_parts.append('<tr>')
            for cell in cells:
                html_parts.append(f'<td>{self._render_inline(cell)}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody></table>')

        return '\n'.join(html_parts)

    def _render_header(self) -> str:
        """渲染 HTML 头部"""
        return '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
    --bg: #1e1e1e;
    --fg: #d4d4d4;
    --accent: #569cd6;
    --keyword: #569cd6;
    --string: #ce9178;
    --comment: #6a9955;
    --function: #dcdcaa;
    --h1: #569cd6;
    --h2: #4ec9b0;
    --h3: #c586c0;
    --link: #3794ff;
    --border: #333;
    --code-bg: #1e1e1e;
    --inline-code-bg: #2d2d2d;
    --table-alt: #252526;
    --blockquote-border: #569cd6;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 15px;
    line-height: 1.7;
    background: var(--bg);
    color: var(--fg);
    padding: 24px;
    max-width: 900px;
    margin: 0 auto;
}

/* 标题 */
h1, h2, h3, h4, h5, h6 {
    color: #fff;
    margin: 1.5em 0 0.5em;
    font-weight: 600;
    line-height: 1.3;
}
h1 { font-size: 2em; border-bottom: 2px solid var(--accent); padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }
h3 { font-size: 1.25em; color: var(--h3); }
h4 { font-size: 1.1em; color: var(--function); }

/* 段落和行 */
p { margin: 0.8em 0; }
br { display: block; margin: 0.5em 0; content: ''; }

/* 链接 */
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
a.ext-link::after { content: ' ↗'; font-size: 0.8em; opacity: 0.7; }

/* 代码 */
code.inline-code {
    background: var(--inline-code-bg);
    color: #ce9178;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 0.9em;
}

pre.code-block {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    margin: 1em 0;
    overflow-x: auto;
    position: relative;
}

pre.code-block::before {
    content: attr(data-lang);
    position: absolute;
    top: 8px;
    right: 12px;
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
}

pre.code-block code {
    font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 14px;
    line-height: 1.5;
    color: #d4d4d4;
    white-space: pre;
}

/* 表格 */
table.md-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 14px;
}
table.md-table th {
    background: #2d2d30;
    color: #fff;
    padding: 10px 14px;
    text-align: left;
    border: 1px solid var(--border);
    font-weight: 600;
}
table.md-table td {
    padding: 8px 14px;
    border: 1px solid var(--border);
}
table.md-table tr:nth-child(even) { background: var(--table-alt); }
table.md-table tr:hover { background: #37373d; }

/* 引用块 */
blockquote {
    border-left: 4px solid var(--blockquote-border);
    padding: 8px 16px;
    margin: 1em 0;
    background: rgba(86, 156, 214, 0.1);
    border-radius: 0 4px 4px 0;
}
blockquote p { margin: 0.3em 0; }

/* 任务列表 */
.task-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 0.4em 0;
}
.task-check { color: var(--accent); font-size: 1.1em; }
.task-text { flex: 1; }

/* UL/OL 列表 */
li.ul-item, li.ol-item { margin: 0.3em 0 0.3em 1.5em; }

/* 水平线 */
hr { border: none; border-top: 1px solid var(--border); margin: 1.5em 0; }

/* 数学公式 */
.math-inline { color: #b5cea8; }
.math-block { color: #b5cea8; text-align: center; margin: 1em 0; }

/* 分割线效果 */
p:empty { min-height: 1em; }
</style>
</head>
<body>
'''

    def _render_footer(self) -> str:
        """渲染 HTML 页脚"""
        return '''
<script>
// 任务列表交互
document.querySelectorAll('.task-check').forEach(cb => {
    cb.style.cursor = 'pointer';
    cb.addEventListener('click', () => {
        const checked = cb.textContent === '☑';
        cb.textContent = checked ? '☐' : '☑';
        cb.parentElement.classList.toggle('checked', !checked);
    });
});

// 平滑滚动到锚点
document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
        e.preventDefault();
        const target = document.querySelector(a.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
});
</script>
</body>
</html>'''

    def render_to_plain_text(self, content: str) -> str:
        """将 Markdown 转换为纯文本（用于 Word/Excel 预览）"""
        # 移除代码块
        content = self.code_block_re.sub('', content)
        # 移除行内代码
        content = self.inline_code_re.sub(r'\1', content)
        # 移除标题标记
        content = self.heading_re.sub(r'\2\n', content)
        # 移除加粗斜体
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
        content = re.sub(r'\*([^*]+)\*', r'\1', content)
        content = re.sub(r'__([^_]+)__', r'\1', content)
        content = re.sub(r'_([^_]+)_', r'\1', content)
        # 移除链接，保留文字
        content = self.link_re.sub(r'\1', content)
        # 移除图片
        content = self.image_re.sub('', content)
        # 移除引用标记
        content = self.blockquote_re.sub(r'\1', content)
        # 移除任务列表标记
        content = self.task_re.sub(r'\2', content)
        # 移除数学公式
        content = self.math_inline_re.sub(r'$\1$', content)
        content = self.math_block_re.sub(r'\1', content)
        return content.strip()
