"""
智能网页发布 (Smart Web Publisher)
==================================

提供网页 AI 增强：
1. 静态站点，动态体验
2. 千人千面个性化
3. SEO 优化
4. 多语言摘要
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .workspace import IntelligentWorkspace, ContentType


class PageType(Enum):
    """页面类型"""
    HOMEPAGE = "homepage"
    ARTICLE = "article"
    PRODUCT = "product"
    DOCUMENTATION = "documentation"
    FORUM_POST = "forum_post"
    PROFILE = "profile"


@dataclass
class SEOOptimization:
    """SEO 优化结果"""
    title: str
    meta_description: str
    meta_keywords: list[str]
    og_tags: dict[str, str] = field(default_factory=dict)
    structured_data: dict[str, Any] = field(default_factory=dict)
    sitemap_entry: dict[str, Any] = field(default_factory=dict)
    readability_score: float = 0.0
    suggestions: list[str] = field(default_factory=list)


@dataclass
class PageWidget:
    """页面挂件"""
    widget_id: str
    widget_type: str                    # comment/statistics/recommendation
    position: str                       # sidebar/footer/floating
    content: dict[str, Any] = field(default_factory=dict)
    visibility_rules: dict[str, Any] = field(default_factory=dict)  # 可见性规则


@dataclass
class PersonalizedContent:
    """个性化内容"""
    base_content: str
    personalized_sections: dict[str, str] = field(default_factory=dict)
    visitor_profile: dict[str, Any] = field(default_factory=dict)
    render_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebPage:
    """网页对象"""
    page_id: str
    page_type: PageType
    url_path: str
    title: str
    content: str
    author_node_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    seo: Optional[SEOOptimization] = None
    widgets: list[PageWidget] = field(default_factory=list)
    multi_language: dict[str, str] = field(default_factory=dict)  # lang -> content
    version: int = 1


class WebPublisher:
    """
    智能网页发布

    能力：
    - 静态网页 + AI 动态挂件
    - 千人千面个性化
    - SEO 自动优化
    - 多语言翻译
    """

    def __init__(self, workspace: IntelligentWorkspace):
        self.workspace = workspace
        self.central_brain = workspace.central_brain
        self.local_path = workspace.local_storage_path / "web_pages"
        self.local_path.mkdir(parents=True, exist_ok=True)

    def generate_page_id(self, url_path: str) -> str:
        """生成页面 ID"""
        return hashlib.sha256(url_path.encode()).hexdigest()[:12]

    async def create_page(
        self,
        url_path: str,
        title: str,
        content: str,
        page_type: PageType,
        author_node_id: str,
        language: str = "zh-CN"
    ) -> WebPage:
        """
        创建网页

        Args:
            url_path: URL 路径
            title: 页面标题
            content: 页面内容 (HTML)
            page_type: 页面类型
            author_node_id: 作者节点 ID
            language: 语言

        Returns:
            网页对象
        """
        page_id = self.generate_page_id(url_path)

        page = WebPage(
            page_id=page_id,
            page_type=page_type,
            url_path=url_path,
            title=title,
            content=content,
            author_node_id=author_node_id,
            multi_language={language: content}
        )

        # SEO 优化
        page.seo = await self.optimize_seo(page)

        # 生成 AI 挂件
        page.widgets = await self.generate_widgets(page)

        # 保存页面
        await self._save_page(page)

        return page

    async def optimize_seo(self, page: WebPage) -> SEOOptimization:
        """
        SEO 优化

        包括：
        - 标题优化
        - Meta 标签
        - Open Graph 标签
        - 结构化数据
        - 可读性评分
        """
        if not self.central_brain:
            # 默认 SEO
            return SEOOptimization(
                title=page.title,
                meta_description=page.title,
                meta_keywords=[]
            )

        # 提取正文（去除 HTML 标签）
        text_content = re.sub(r'<[^>]+>', '', page.content)
        text_content = text_content[:500]  # 取前 500 字

        prompt = f"""为以下网页内容生成 SEO 优化方案：

标题：{page.title}
内容摘要：{text_content}
页面类型：{page.page_type.value}

请生成：
1. meta description（不超过 160 字）
2. meta keywords（5-8 个关键词）
3. Open Graph 标签
4. 结构化数据（JSON-LD 格式）
5. 可读性评分（0-100）及改进建议

返回 JSON 格式：
{{
    "meta_description": "...",
    "meta_keywords": ["..."],
    "og_tags": {{"og:title": "...", "og:description": "..."}},
    "structured_data": {{"@type": "Article", "headline": "..."}},
    "readability_score": 85,
    "suggestions": ["..."]
}}
"""
        result = await self.central_brain.think(prompt)
        if result:
            try:
                data = json.loads(result)
                return SEOOptimization(
                    title=page.title,
                    meta_description=data.get("meta_description", page.title),
                    meta_keywords=data.get("meta_keywords", []),
                    og_tags=data.get("og_tags", {}),
                    structured_data=data.get("structured_data", {}),
                    readability_score=data.get("readability_score", 0),
                    suggestions=data.get("suggestions", [])
                )
            except json.JSONDecodeError:
                pass

        return SEOOptimization(
            title=page.title,
            meta_description=page.title,
            meta_keywords=[]
        )

    async def generate_widgets(self, page: WebPage) -> list[PageWidget]:
        """
        生成 AI 挂件

        包括：
        - 评论区
        - 访问统计
        - 推荐侧边栏
        - 相关文章
        """
        widgets = []

        # 根据页面类型生成不同挂件
        if page.page_type == PageType.ARTICLE:
            # 文章页：评论区 + 相关文章
            widgets.append(PageWidget(
                widget_id=f"comments_{page.page_id}",
                widget_type="comment",
                position="below_content",
                content={"allow_anonymous": True, "moderation": True}
            ))

            widgets.append(PageWidget(
                widget_id=f"related_{page.page_id}",
                widget_type="recommendation",
                position="sidebar",
                content={"max_items": 5, "type": "related_articles"}
            ))

        elif page.page_type == PageType.HOMEPAGE:
            # 首页：访问统计 + 个性化推荐
            widgets.append(PageWidget(
                widget_id=f"stats_{page.page_id}",
                widget_type="statistics",
                position="footer",
                content={"show_views": True, "show_likes": True}
            ))

            widgets.append(PageWidget(
                widget_id=f"personalized_{page.page_id}",
                widget_type="recommendation",
                position="sidebar",
                content={"max_items": 10, "type": "personalized"}
            ))

        return widgets

    async def personalize_content(
        self,
        page: WebPage,
        visitor_profile: dict[str, Any]
    ) -> PersonalizedContent:
        """
        个性化内容

        根据访客profile返回不同内容：
        - 开发者：显示相关 API 文档
        - 普通用户：显示简介和截图

        Args:
            page: 页面
            visitor_profile: 访客画像

        Returns:
            个性化内容
        """
        visitor_type = visitor_profile.get("type", "general")
        interests = visitor_profile.get("interests", [])

        personalized = PersonalizedContent(
            base_content=page.content,
            visitor_profile=visitor_profile
        )

        if not self.central_brain:
            return personalized

        # 根据访客类型生成个性化区块
        if visitor_type == "developer":
            prompt = f"""为开发者访客生成个性化的侧边栏推荐：

页面主题：{page.title}
访客兴趣：{', '.join(interests)}

请生成一段推荐内容，包含：
1. 相关 API 文档链接
2. 相关代码示例
3. 技术讨论话题

只返回推荐内容 HTML 片段。
"""
        else:
            prompt = f"""为普通用户生成个性化的简介区块：

页面主题：{page.title}

请生成：
1. 简明的产品介绍
2. 用户评价摘要
3. 快速上手指南

只返回推荐内容 HTML 片段。
"""

        result = await self.central_brain.think(prompt)
        if result:
            personalized.personalized_sections["sidebar"] = result

        return personalized

    async def generate_multilingual(
        self,
        page: WebPage,
        target_languages: list[str]
    ) -> dict[str, str]:
        """
        生成多语言版本

        Args:
            page: 页面
            target_languages: 目标语言列表

        Returns:
            语言代码 -> 翻译内容的字典
        """
        translations = {}

        for lang in target_languages:
            if lang == "zh-CN":
                translations[lang] = page.content
                continue

            if not self.central_brain:
                continue

            prompt = f"""将以下网页内容翻译为 {lang}：

标题：{page.title}

内容：
{page.content[:1000]}...

要求：
1. 保持 HTML 格式
2. 保持专业语气
3. 适当本地化
"""
            result = await self.central_brain.think(prompt)
            if result:
                translations[lang] = result

        return translations

    async def preview_for_search_engine(
        self,
        page: WebPage
    ) -> dict[str, Any]:
        """
        模拟搜索引擎预览

        返回搜索引擎结果中页面的展示效果
        """
        seo = page.seo or SEOOptimization(
            title=page.title,
            meta_description=page.title,
            meta_keywords=[]
        )

        return {
            "title": seo.title[:60],
            "url": f"https://example.com{page.url_path}",
            "description": seo.meta_description[:160],
            "keywords": seo.meta_keywords[:5]
        }

    async def _save_page(self, page: WebPage):
        """保存页面到本地"""
        page_path = self.local_path / f"{page.page_id}.json"

        data = {
            "page_id": page.page_id,
            "page_type": page.page_type.value,
            "url_path": page.url_path,
            "title": page.title,
            "content": page.content,
            "author_node_id": page.author_node_id,
            "created_at": page.created_at.isoformat(),
            "updated_at": page.updated_at.isoformat(),
            "seo": {
                "title": page.seo.title if page.seo else page.title,
                "meta_description": page.seo.meta_description if page.seo else "",
                "meta_keywords": page.seo.meta_keywords if page.seo else []
            },
            "widgets": [
                {
                    "widget_id": w.widget_id,
                    "widget_type": w.widget_type,
                    "position": w.position
                }
                for w in page.widgets
            ],
            "multi_language": page.multi_language,
            "version": page.version
        }

        with open(page_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def get_page(self, page_id: str) -> Optional[WebPage]:
        """获取页面"""
        page_path = self.local_path / f"{page_id}.json"
        if not page_path.exists():
            return None

        with open(page_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return WebPage(
            page_id=data["page_id"],
            page_type=PageType(data["page_type"]),
            url_path=data["url_path"],
            title=data["title"],
            content=data["content"],
            author_node_id=data["author_node_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            multi_language=data.get("multi_language", {}),
            version=data.get("version", 1)
        )

    def generate_sitemap(self, pages: list[WebPage]) -> str:
        """生成 sitemap.xml"""
        urls = []
        for page in pages:
            urls.append(f"""  <url>
    <loc>https://example.com{page.url_path}</loc>
    <lastmod>{page.updated_at.strftime('%Y-%m-%d')}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>{0.8 if page.page_type == PageType.HOMEPAGE else 0.6}</priority>
  </url>""")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


def create_web_publisher(workspace: IntelligentWorkspace) -> WebPublisher:
    """创建网页发布器"""
    return WebPublisher(workspace)