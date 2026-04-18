"""
🌲 Wiki渲染器 (Wiki Renderer)
=============================

伪域名路由 + 静态HTML生成

路由体系：
- wiki.root.tree              → 全行业目录
- wiki.electronics.root.tree → 电子林区
- wiki.view/{industry}/{slug} → 条目页

视觉主题：
- 纸张黄背景 (#f8f3e6)
- 森林绿强调 (#2a6d39)
- 衬线标题 + 无衬线正文
"""

import re
import html
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

# 简单的 Markdown → HTML 转换器
class MarkdownRenderer:
    """轻量级 Markdown 渲染器"""

    def __init__(self):
        self.rules = [
            # 代码块
            (r'```(\w+)?\n(.*?)```', self._render_code_block),
            # 行内代码
            (r'`([^`]+)`', r'<code>\1</code>'),
            # 标题
            (r'^### (.*)$', '<h3>\1</h3>'),
            (r'^## (.*)$', '<h2>\1</h2>'),
            (r'^# (.*)$', '<h1>\1</h1>'),
            # 粗体/斜体
            (r'\*\*\*(.+?)\*\*\*', '<strong><em>\1</em></strong>'),
            (r'\*\*(.+?)\*\*', '<strong>\1</strong>'),
            (r'\*(.+?)\*', '<em>\1</em>'),
            # 链接
            (r'\[([^\]]+)\]\(([^)]+)\)', '<a href="\2" class="wiki-link">\1</a>'),
            # 图片
            (r'!\[([^\]]*)\]\(([^)]+)\)', '<img src="\2" alt="\1" class="wiki-image" loading="lazy">'),
            # 引用
            (r'^> (.*)$', '<blockquote>\1</blockquote>'),
            # 分割线
            (r'^---$', '<hr>'),
            # 表格
            (self._render_table_pattern, self._render_table),
            # 无序列表
            (r'^- (.*)$', '<li>\1</li>'),
            # 有序列表
            (r'^\d+\. (.*)$', '<li>\1</li>'),
        }

    def _render_code_block(self, match) -> str:
        lang = match.group(1) or ""
        code = html.escape(match.group(2))
        return f'<pre class="code-block" data-lang="{lang}"><code>{code}</code></pre>'

    def _render_table_pattern(self, text: str) -> bool:
        return '|' in text and text.strip().startswith('|')

    def _render_table(self, match) -> str:
        lines = match.group(0).strip().split('\n')
        if len(lines) < 2:
            return match.group(0)

        # 解析表头
        headers = [h.strip() for h in lines[0].split('|')[1:-1]]
        header_html = ''.join(f'<th>{h}</th>' for h in headers)

        # 解析数据行
        body_rows = []
        for line in lines[2:]:  # 跳过分隔符行
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if cells:
                body_rows.append(''.join(f'<td>{c}</td>' for c in cells))

        body_html = ''.join(f'<tr>{"".join(body_rows)}</tr>' for row in body_rows if body_rows)

        return f'''<table class="wiki-table">
<thead><tr>{header_html}</tr></thead>
<tbody>{"".join(body_rows)}</tbody>
</table>'''

    def render(self, markdown: str) -> str:
        """渲染 Markdown 为 HTML"""
        lines = markdown.split('\n')
        result = []
        in_list = False
        in_blockquote = False

        for line in lines:
            matched = False

            # 检查是否在列表块中
            if line.strip().startswith('- ') or re.match(r'^\d+\. ', line.strip()):
                if not in_list:
                    result.append('<ul>')
                    in_list = True
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False

            # 检查引用块
            if line.strip().startswith('>'):
                if not in_blockquote:
                    result.append('<blockquote>')
                    in_blockquote = True
            else:
                if in_blockquote:
                    result.append('</blockquote>')
                    in_blockquote = False

            # 应用规则
            for rule, replacement in self.rules:
                if isinstance(rule, str):
                    pattern = rule
                    if re.match(pattern, line, re.MULTILINE):
                        line = re.sub(pattern, replacement, line, flags=re.MULTILINE)
                        matched = True
                        break
                else:
                    if rule(line):
                        line = replacement(line)
                        matched = True
                        break

            if not matched:
                result.append(f'<p>{line}</p>' if line.strip() else '')

        # 关闭未关闭的块
        if in_list:
            result.append('</ul>')
        if in_blockquote:
            result.append('</blockquote>')

        return '\n'.join(result)


class WikiRenderer:
    """
    Wiki渲染器

    负责：
    1. 伪域名路由解析
    2. 静态HTML生成
    3. 目录树构建
    """

    # 主题色
    THEME = {
        "paper": "#f8f3e6",
        "forest": "#2a6d39",
        "forest_light": "#4a9d5b",
        "bark": "#5d4e37",
        "text": "#3d3d3d",
        "text_light": "#6b6b6b",
        "border": "#d4c4a8",
    }

    def __init__(self, grove, cache_dir: Path = None):
        self.grove = grove
        self.cache_dir = cache_dir or (Path.home() / ".hermes-desktop" / "soil_bank" / "wiki_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.md_renderer = MarkdownRenderer()

    # ==================== 路由解析 ====================

    def parse_route(self, url: str) -> Tuple[str, str, Optional[str]]:
        """
        解析伪域名路由

        Returns:
            (route_type, industry, entry_slug)

        Examples:
            "wiki.root.tree" → ("index", None, None)
            "wiki.electronics.root.tree" → ("industry", "electronics", None)
            "wiki.view/electronics/pdf_parse" → ("entry", "electronics", "pdf_parse")
        """
        url = url.strip().lower()

        # 首页
        if url == "wiki.root.tree":
            return ("index", None, None)

        # 行业页
        industry_match = re.match(r'wiki\.(\w+)\.root\.tree', url)
        if industry_match:
            industry = industry_match.group(1)
            return ("industry", industry, None)

        # 条目页
        view_match = re.match(r'wiki\.view/(\w+)/(.+)', url)
        if view_match:
            industry = view_match.group(1)
            slug = view_match.group(2)
            return ("entry", industry, slug)

        return ("unknown", None, None)

    def build_url(self, route_type: str, industry: str = None, entry_id: str = None) -> str:
        """构建伪域名URL"""
        if route_type == "index":
            return "wiki.root.tree"
        elif route_type == "industry" and industry:
            return f"wiki.{industry}.root.tree"
        elif route_type == "entry" and industry and entry_id:
            return f"wiki.view/{industry}/{entry_id}"
        return "wiki.root.tree"

    # ==================== HTML生成 ====================

    def render_index(self) -> str:
        """渲染全行业索引页"""
        industries = self.grove.list_industries()
        stats = self.grove.get_stats()

        industry_cards = []
        for ind in industries:
            if ind.id == "general":
                continue
            entry_count = stats.get("by_industry", {}).get(ind.id, 0)
            industry_cards.append(f'''
                <a href="wiki.{ind.id}.root.tree" class="industry-card" style="--accent: {ind.color}">
                    <div class="industry-icon">{ind.icon}</div>
                    <div class="industry-name">{ind.name.replace("🌲 ", "")}</div>
                    <div class="industry-count">{entry_count} 条知识</div>
                </a>
            ''')

        return self._wrap_html(
            title="🌲 生命之树知识林地",
            nav=self._build_nav(),
            content=f'''
                <div class="grove-header">
                    <h1>🌲 生命之树知识林地</h1>
                    <p class="subtitle">行业化智库 · 可迁徙知识包</p>
                    <div class="stats-bar">
                        <span>📚 {stats.get("total_entries", 0)} 条知识</span>
                        <span>🏛️ {len([i for i in industries if i.id != 'general'])} 个林区</span>
                    </div>
                </div>
                <div class="industry-grid">
                    {"".join(industry_cards)}
                </div>
            '''
        )

    def render_industry(self, industry_id: str) -> str:
        """渲染行业林区页"""
        industry = self.grove.get_industry(industry_id)
        if not industry:
            return self.render_error("林区不存在")

        entries = self.grove.list_entries(industry=industry_id)
        stats = self.grove.get_stats()

        entry_list = []
        for entry in entries:
            tags_html = " ".join(f'<span class="tag">{t}</span>' for t in entry.tags[:5])
            entry_list.append(f'''
                <a href="wiki.view/{industry_id}/{entry.id}" class="entry-card">
                    <div class="entry-title">{entry.title}</div>
                    <div class="entry-summary">{entry.summary[:100]}...</div>
                    <div class="entry-meta">
                        <span class="entry-type">{entry.knowledge_type}</span>
                        {tags_html}
                    </div>
                </a>
            ''')

        return self._wrap_html(
            title=f'{industry.icon} {industry.name}',
            nav=self._build_nav(industry_id),
            content=f'''
                <div class="industry-header" style="--accent: {industry.color}">
                    <div class="industry-icon-large">{industry.icon}</div>
                    <h1>{industry.name}</h1>
                    <p>{industry.description}</p>
                    <div class="industry-stats">
                        <span>{stats.get("by_industry", {}).get(industry_id, 0)} 条知识</span>
                    </div>
                </div>
                <div class="entries-list">
                    {"".join(entry_list) if entry_list else "<p class='empty'>此林区暂无知识，快去播种吧！</p>"}
                </div>
            '''
        )

    def render_entry(self, entry_id: str) -> str:
        """渲染条目页"""
        entry = self.grove.get_entry(entry_id)
        if not entry:
            return self.render_error("知识条目不存在")

        industry = entry.industries[0] if entry.industries else "general"

        # 渲染 Markdown
        content_html = self.md_renderer.render(entry.content_md)

        # 标签
        tags_html = " ".join(f'<a href="wiki.root.tree?tag={t}" class="tag">{t}</a>' for t in entry.tags)

        # 面包屑
        breadcrumb = f'''
            <div class="breadcrumb">
                <a href="wiki.root.tree">🌲 林地首页</a>
                <span class="sep">›</span>
                <a href="wiki.{industry}.root.tree">{INDUSTRY_NAMES.get(industry, industry)}</a>
                <span class="sep">›</span>
                <span class="current">{entry.title}</span>
            </div>
        '''

        return self._wrap_html(
            title=entry.title,
            nav=self._build_nav(industry, entry_id),
            content=f'''
                {breadcrumb}
                <article class="entry-page">
                    <header class="entry-header">
                        <h1>{entry.title}</h1>
                        <div class="entry-meta">
                            <span class="meta-item">🏷️ {tags_html}</span>
                            <span class="meta-item">📅 {entry.created_at[:10]}</span>
                            <span class="meta-item">📖 {entry.usage_count} 次查阅</span>
                        </div>
                        {f'<a href="{entry.source_url}" class="source-link" target="_blank">🔗 来源</a>' if entry.source_url else ''}
                    </header>
                    <div class="entry-summary-box">
                        <strong>📌 摘要：</strong>{entry.summary}
                    </div>
                    <div class="entry-content">
                        {content_html}
                    </div>
                </article>
            '''
        )

    def render_error(self, message: str) -> str:
        """渲染错误页"""
        return self._wrap_html(
            title="错误",
            content=f'''
                <div class="error-page">
                    <div class="error-icon">🌵</div>
                    <h1>出了点问题</h1>
                    <p>{message}</p>
                    <a href="wiki.root.tree" class="back-link">← 返回林地首页</a>
                </div>
            '''
        )

    # ==================== 模板方法 ====================

    def _wrap_html(self, title: str, nav: str, content: str) -> str:
        """包装完整HTML"""
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 生命之树知识林地</title>
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    {nav}
    <main class="wiki-content">
        {content}
    </main>
    <footer class="wiki-footer">
        <p>🌲 生命之树知识林地 · Hermes Desktop</p>
    </footer>
</body>
</html>'''

    def _build_nav(self, current_industry: str = None, current_entry: str = None) -> str:
        """构建导航栏"""
        industries = self.grove.list_industries()

        industry_links = []
        for ind in industries:
            if ind.id == "general":
                continue
            active = "active" if ind.id == current_industry else ""
            industry_links.append(
                f'<a href="wiki.{ind.id}.root.tree" class="nav-item {active}">{ind.icon}</a>'
            )

        return f'''
            <nav class="wiki-nav">
                <a href="wiki.root.tree" class="nav-brand">
                    <span class="brand-icon">🌲</span>
                    <span class="brand-text">知识林地</span>
                </a>
                <div class="nav-industries">
                    {''.join(industry_links)}
                </div>
                <div class="nav-search">
                    <input type="text" id="search-input" placeholder="搜索知识..." />
                    <button onclick="alert('搜索功能开发中')">🔍</button>
                </div>
            </nav>
        '''

    def _get_css(self) -> str:
        """获取主题CSS"""
        t = self.THEME
        return f'''
            :root {{
                --paper: {t["paper"]};
                --forest: {t["forest"]};
                --forest-light: {t["forest_light"]};
                --bark: {t["bark"]};
                --text: {t["text"]};
                --text-light: {t["text_light"]};
                --border: {t["border"]};
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: var(--paper);
                color: var(--text);
                line-height: 1.6;
            }}

            /* 导航 */
            .wiki-nav {{
                position: sticky;
                top: 0;
                z-index: 100;
                display: flex;
                align-items: center;
                gap: 24px;
                padding: 12px 24px;
                background: linear-gradient(135deg, var(--forest) 0%, var(--forest-light) 100%);
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            }}

            .nav-brand {{
                display: flex;
                align-items: center;
                gap: 8px;
                text-decoration: none;
                color: white;
            }}

            .brand-icon {{ font-size: 24px; }}
            .brand-text {{ font-weight: 600; font-size: 16px; }}

            .nav-industries {{
                display: flex;
                gap: 4px;
                flex: 1;
            }}

            .nav-item {{
                padding: 6px 10px;
                border-radius: 6px;
                text-decoration: none;
                font-size: 18px;
                opacity: 0.7;
                transition: all 0.2s;
            }}

            .nav-item:hover, .nav-item.active {{
                opacity: 1;
                background: rgba(255,255,255,0.2);
            }}

            .nav-search {{
                display: flex;
                gap: 4px;
            }}

            .nav-search input {{
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                width: 180px;
                font-size: 13px;
            }}

            .nav-search button {{
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background: rgba(255,255,255,0.2);
                cursor: pointer;
            }}

            /* 主内容 */
            .wiki-content {{
                max-width: 1100px;
                margin: 0 auto;
                padding: 24px;
            }}

            /* 林地首页 */
            .grove-header {{
                text-align: center;
                margin-bottom: 32px;
            }}

            .grove-header h1 {{
                font-size: 28px;
                color: var(--forest);
                margin-bottom: 8px;
            }}

            .subtitle {{
                color: var(--text-light);
                font-size: 14px;
                margin-bottom: 16px;
            }}

            .stats-bar {{
                display: flex;
                justify-content: center;
                gap: 24px;
                color: var(--text-light);
                font-size: 13px;
            }}

            .industry-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 16px;
            }}

            .industry-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 24px 16px;
                background: white;
                border-radius: 12px;
                text-decoration: none;
                color: var(--text);
                border: 2px solid transparent;
                transition: all 0.2s;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }}

            .industry-card:hover {{
                border-color: var(--accent, var(--forest));
                transform: translateY(-2px);
                box-shadow: 0 4px 16px rgba(0,0,0,0.1);
            }}

            .industry-icon {{ font-size: 36px; margin-bottom: 12px; }}
            .industry-name {{ font-weight: 600; font-size: 14px; }}
            .industry-count {{ font-size: 12px; color: var(--text-light); margin-top: 4px; }}

            /* 行业页 */
            .industry-header {{
                text-align: center;
                padding: 32px;
                background: linear-gradient(135deg, var(--accent, var(--forest)) 0%, var(--forest-light) 100%);
                border-radius: 12px;
                color: white;
                margin-bottom: 24px;
            }}

            .industry-icon-large {{ font-size: 48px; margin-bottom: 12px; }}
            .industry-header h1 {{ font-size: 24px; margin-bottom: 8px; }}
            .industry-header p {{ opacity: 0.9; font-size: 14px; }}

            .entries-list {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .entry-card {{
                display: block;
                padding: 16px 20px;
                background: white;
                border-radius: 8px;
                text-decoration: none;
                color: var(--text);
                border-left: 4px solid var(--forest);
                transition: all 0.2s;
                box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            }}

            .entry-card:hover {{
                background: #fafaf5;
                transform: translateX(4px);
            }}

            .entry-title {{
                font-weight: 600;
                font-size: 15px;
                margin-bottom: 6px;
                color: var(--forest);
            }}

            .entry-summary {{
                font-size: 13px;
                color: var(--text-light);
                margin-bottom: 8px;
            }}

            .entry-meta {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }}

            .entry-type {{
                font-size: 11px;
                padding: 2px 8px;
                background: var(--paper);
                border-radius: 4px;
                color: var(--text-light);
            }}

            .tag {{
                font-size: 11px;
                padding: 2px 8px;
                background: var(--forest);
                color: white;
                border-radius: 4px;
                text-decoration: none;
            }}

            /* 条目页 */
            .breadcrumb {{
                padding: 8px 0;
                margin-bottom: 16px;
                font-size: 13px;
                color: var(--text-light);
            }}

            .breadcrumb a {{
                color: var(--forest);
                text-decoration: none;
            }}

            .breadcrumb .sep {{ margin: 0 6px; }}
            .breadcrumb .current {{ color: var(--text); }}

            .entry-page {{
                background: white;
                border-radius: 12px;
                padding: 32px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            }}

            .entry-header {{
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 1px solid var(--border);
            }}

            .entry-header h1 {{
                font-size: 22px;
                color: var(--forest);
                margin-bottom: 12px;
                font-family: Georgia, serif;
            }}

            .entry-meta {{
                display: flex;
                gap: 16px;
                flex-wrap: wrap;
                font-size: 12px;
                color: var(--text-light);
            }}

            .meta-item {{
                display: flex;
                align-items: center;
                gap: 4px;
            }}

            .source-link {{
                display: inline-block;
                margin-top: 12px;
                font-size: 13px;
                color: var(--forest);
            }}

            .entry-summary-box {{
                padding: 16px;
                background: var(--paper);
                border-radius: 8px;
                margin-bottom: 24px;
                font-size: 14px;
                border-left: 4px solid var(--forest);
            }}

            /* 内容样式 */
            .entry-content {{
                font-size: 15px;
                line-height: 1.8;
            }}

            .entry-content h1, .entry-content h2, .entry-content h3 {{
                color: var(--forest);
                margin: 24px 0 12px;
                font-family: Georgia, serif;
            }}

            .entry-content h1 {{ font-size: 20px; }}
            .entry-content h2 {{ font-size: 18px; }}
            .entry-content h3 {{ font-size: 16px; }}

            .entry-content p {{ margin-bottom: 12px; }}

            .entry-content a {{
                color: var(--forest);
            }}

            .entry-content code {{
                background: var(--paper);
                padding: 2px 6px;
                border-radius: 4px;
                font-family: "SF Mono", Consolas, monospace;
                font-size: 13px;
            }}

            .entry-content pre.code-block {{
                background: #2d2d2d;
                color: #f8f8f2;
                padding: 16px;
                border-radius: 8px;
                overflow-x: auto;
                margin: 16px 0;
            }}

            .entry-content pre.code-block code {{
                background: none;
                padding: 0;
                color: inherit;
            }}

            .entry-content blockquote {{
                border-left: 4px solid var(--forest);
                padding-left: 16px;
                margin: 16px 0;
                color: var(--text-light);
                font-style: italic;
            }}

            .entry-content table {{
                width: 100%;
                border-collapse: collapse;
                margin: 16px 0;
            }}

            .entry-content th, .entry-content td {{
                border: 1px solid var(--border);
                padding: 10px 12px;
                text-align: left;
            }}

            .entry-content th {{
                background: var(--paper);
                font-weight: 600;
            }}

            .entry-content li {{
                margin-left: 20px;
                margin-bottom: 4px;
            }}

            /* 错误页 */
            .error-page {{
                text-align: center;
                padding: 64px 32px;
            }}

            .error-icon {{ font-size: 64px; margin-bottom: 16px; }}
            .error-page h1 {{ color: var(--forest); margin-bottom: 8px; }}
            .error-page p {{ color: var(--text-light); margin-bottom: 24px; }}
            .back-link {{ color: var(--forest); }}

            /* 页脚 */
            .wiki-footer {{
                text-align: center;
                padding: 24px;
                color: var(--text-light);
                font-size: 12px;
                border-top: 1px solid var(--border);
                margin-top: 48px;
            }}

            .empty {{
                text-align: center;
                padding: 48px;
                color: var(--text-light);
            }}
        '''


# ==================== 辅助函数 ====================

def get_wiki_renderer(grove=None) -> WikiRenderer:
    """获取Wiki渲染器"""
    if grove is None:
        from .knowledge_grove import KnowledgeGrove
        grove = KnowledgeGrove()
    return WikiRenderer(grove)


# 导入行业名称映射
INDUSTRY_NAMES = {
    "general": "🌐 通用林区",
    "electronics": "💻 电子林区",
    "hardware": "🔧 硬件林区",
    "software": "📝 软件林区",
    "network": "🌐 网络林区",
    "ai_ml": "🤖 AI/ML林区",
    "data": "📊 数据林区",
    "cloud": "☁️ 云服务林区",
    "iot": "📡 物联网林区",
    "automotive": "🚗 汽车林区",
    "industrial": "🏭 工业林区",
    "medical": "🏥 医疗林区",
}
