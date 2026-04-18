"""
AI 组件市场 (Component Market)
==============================

基于 Web Components 标准的 AI 组件市场。

核心功能：
1. AI 生成自定义元素：<ai-chart>、<ai-gallery>、<ai-card-3d>
2. 一键导入：AI 生成的组件可以直接插入当前网页
3. 参数化调整：通过属性实时调整组件行为
4. 组件市场：浏览、安装、分享 AI 生成的组件
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ComponentCategory(Enum):
    """组件类别"""
    CHART = "chart"               # 图表
    GALLERY = "gallery"           # 图库
    CARD = "card"                 # 卡片
    FORM = "form"                 # 表单
    ANIMATION = "animation"       # 动画
    DATA_VISUALIZATION = "data_viz"  # 数据可视化
    AI_COMPONENT = "ai_component"  # AI 组件
    GAME = "game"                 # 游戏组件
    MEDIA = "media"               # 媒体组件


@dataclass
class AIComponent:
    """AI 组件"""
    component_id: str
    name: str                              # 组件名称
    tag_name: str                          # HTML 标签名 (如 ai-chart)
    category: ComponentCategory
    description: str
    author: str = "AI"                    # 作者
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 组件定义
    html_template: str = ""                # HTML 模板
    css_styles: str = ""                   # CSS 样式
    js_class: str = ""                     # JavaScript 类定义
    attributes: list[str] = field(default_factory=list)  # 可配置属性

    # 元数据
    preview_url: str = ""                  # 预览地址
    documentation: str = ""                 # 文档
    examples: list[str] = field(default_factory=list)  # 使用示例

    # 统计
    install_count: int = 0                # 安装次数
    rating: float = 0                      # 评分
    tags: list[str] = field(default_factory=list)

    # 依赖
    dependencies: list[str] = field(default_factory=list)  # 外部依赖
    is_ai_generated: bool = True           # 是否是 AI 生成


@dataclass
class ComponentTemplate:
    """组件模板"""
    template_id: str
    name: str
    category: ComponentCategory
    base_html: str                         # 基础 HTML 结构
    base_css: str = ""                     # 基础 CSS
    attribute_schema: dict = field(default_factory=dict)  # 属性模式
    slot_content: str = ""                 # 插槽内容


class ComponentMarket:
    """
    AI 组件市场

    用法:
        market = ComponentMarket()

        # 注册 AI 生成的组件
        component = await market.create_component(
            name="3D卡片",
            tag_name="ai-card-3d",
            category=ComponentCategory.CARD,
            html_template="<div class='card-3d'>{{content}}</div>",
            css_styles=".card-3d { perspective: 1000px; }"
        )

        # 生成组件代码
        code = await market.generate_component_code("ai-card-3d")

        # 获取市场组件列表
        components = market.get_market_components(category=ComponentCategory.CARD)
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._components: dict[str, AIComponent] = {}
        self._templates: dict[str, ComponentTemplate] = {}
        self._installed: set[str] = set()   # 已安装的组件 ID
        self._ai_generator: Optional[Callable] = None

        # 加载内置模板
        self._loadBuiltinTemplates()

    def register_ai_generator(self, generator: Callable) -> None:
        """注册 AI 生成器"""
        self._ai_generator = generator

    def _loadBuiltinTemplates(self) -> None:
        """加载内置模板"""
        builtin_templates = [
            ComponentTemplate(
                template_id="basic-card",
                name="基础卡片",
                category=ComponentCategory.CARD,
                base_html="""
<template id="ai-card-template">
    <div class="ai-card" style="--ai-card-bg: #fff; --ai-card-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <div class="ai-card-media" part="media"></div>
        <div class="ai-card-content">
            <h3 class="ai-card-title" part="title"></h3>
            <div class="ai-card-body" part="body"></div>
        </div>
        <div class="ai-card-footer" part="footer"></div>
    </div>
</template>
""",
                base_css="""
ai-card {
    display: block;
    font-family: system-ui, sans-serif;
}
.ai-card {
    background: var(--ai-card-bg, #fff);
    border-radius: 12px;
    box-shadow: var(--ai-card-shadow, 0 2px 8px rgba(0,0,0,0.1));
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
}
.ai-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
.ai-card-media img {
    width: 100%;
    height: auto;
    display: block;
}
.ai-card-content {
    padding: 16px;
}
.ai-card-title {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 600;
}
.ai-card-body {
    color: #666;
    font-size: 14px;
}
.ai-card-footer {
    padding: 12px 16px;
    border-top: 1px solid #eee;
}
""",
                attribute_schema={
                    "title": {"type": "string", "default": ""},
                    "image": {"type": "url", "default": ""},
                    "elevated": {"type": "boolean", "default": "false"}
                }
            ),
            ComponentTemplate(
                template_id="data-chart",
                name="数据图表",
                category=ComponentCategory.CHART,
                base_html="""
<template id="ai-chart-template">
    <div class="ai-chart-container">
        <canvas id="chart-canvas"></canvas>
    </div>
</template>
""",
                base_css="""
ai-chart {
    display: block;
}
.ai-chart-container {
    position: relative;
    width: 100%;
    height: 300px;
}
#chart-canvas {
    width: 100%;
    height: 100%;
}
""",
                attribute_schema={
                    "type": {"type": "enum", "values": ["line", "bar", "pie", "doughnut"], "default": "line"},
                    "data": {"type": "json", "default": "[]"},
                    "labels": {"type": "json", "default": "[]"},
                    "height": {"type": "number", "default": "300"}
                }
            ),
            ComponentTemplate(
                template_id="image-gallery",
                name="图片画廊",
                category=ComponentCategory.GALLERY,
                base_html="""
<template id="ai-gallery-template">
    <div class="ai-gallery">
        <div class="gallery-grid"></div>
        <div class="gallery-lightbox">
            <button class="close-btn">×</button>
            <img class="lightbox-img" src="" alt="">
        </div>
    </div>
</template>
""",
                base_css="""
ai-gallery {
    display: block;
}
.gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
}
.gallery-grid img {
    width: 100%;
    height: 200px;
    object-fit: cover;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.2s;
}
.gallery-grid img:hover {
    transform: scale(1.05);
}
.gallery-lightbox {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.9);
    z-index: 9999;
    justify-content: center;
    align-items: center;
}
.gallery-lightbox.active {
    display: flex;
}
.gallery-lightbox img {
    max-width: 90%;
    max-height: 90%;
}
""",
                attribute_schema={
                    "images": {"type": "json", "default": "[]"},
                    "columns": {"type": "number", "default": "4"},
                    "lightbox": {"type": "boolean", "default": "true"}
                }
            ),
            ComponentTemplate(
                template_id="card-3d",
                name="3D卡片",
                category=ComponentCategory.CARD,
                base_html="""
<template id="ai-card-3d-template">
    <div class="ai-card-3d">
        <div class="card-inner">
            <div class="card-front">
                <div class="card-media"></div>
                <div class="card-content">
                    <h3 class="card-title"></h3>
                    <p class="card-text"></p>
                </div>
            </div>
            <div class="card-back">
                <div class="card-content">
                    <p class="card-back-text"></p>
                </div>
            </div>
        </div>
    </div>
</template>
""",
                base_css="""
ai-card-3d {
    display: block;
    perspective: 1000px;
}
.ai-card-3d .card-inner {
    position: relative;
    width: 100%;
    height: 300px;
    transform-style: preserve-3d;
    transition: transform 0.6s;
}
.ai-card-3d:hover .card-inner {
    transform: rotateY(180deg);
}
.card-front, .card-back {
    position: absolute;
    width: 100%;
    height: 100%;
    backface-visibility: hidden;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.card-front {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}
.card-back {
    background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    color: white;
    transform: rotateY(180deg);
}
""",
                attribute_schema={
                    "title": {"type": "string", "default": ""},
                    "content": {"type": "string", "default": ""},
                    "back-content": {"type": "string", "default": ""},
                    "image": {"type": "url", "default": ""},
                    "auto-rotate": {"type": "boolean", "default": "false"}
                }
            ),
        ]

        for template in builtin_templates:
            self._templates[template.template_id] = template

    async def create_component(
        self,
        name: str,
        tag_name: str,
        category: ComponentCategory,
        description: str = "",
        template_id: str = None,
        ai_prompt: str = ""
    ) -> AIComponent:
        """
        创建 AI 组件

        Args:
            name: 组件名称
            tag_name: HTML 标签名
            category: 组件类别
            description: 描述
            template_id: 基础模板 ID
            ai_prompt: AI 生成提示

        Returns:
            AIComponent: 创建的组件
        """
        component_id = hashlib.sha256(f"{tag_name}{time.time()}".encode()).hexdigest()[:12]

        # 如果有 AI 生成器，使用它
        if self._ai_generator and ai_prompt:
            generated = await self._ai_generator(ai_prompt)
            component = AIComponent(
                component_id=component_id,
                name=name,
                tag_name=tag_name,
                category=category,
                description=description or generated.get("description", ""),
                html_template=generated.get("html", ""),
                css_styles=generated.get("css", ""),
                js_class=generated.get("js", ""),
                attributes=generated.get("attributes", []),
                is_ai_generated=True
            )
        elif template_id and template_id in self._templates:
            # 使用模板
            template = self._templates[template_id]
            component = AIComponent(
                component_id=component_id,
                name=name,
                tag_name=tag_name,
                category=category,
                description=description,
                html_template=template.base_html,
                css_styles=template.base_css,
                attributes=list(template.attribute_schema.keys())
            )
        else:
            # 空组件
            component = AIComponent(
                component_id=component_id,
                name=name,
                tag_name=tag_name,
                category=category,
                description=description
            )

        self._components[component_id] = component
        return component

    async def generate_component_code(
        self,
        component_id: str,
        include_usage: bool = True
    ) -> str:
        """
        生成组件代码

        Args:
            component_id: 组件 ID
            include_usage: 是否包含使用示例

        Returns:
            str: 可直接使用的 HTML/JS/CSS 代码
        """
        component = self._components.get(component_id)
        if not component:
            raise ValueError(f"Component not found: {component_id}")

        code_parts = []

        # HTML 模板
        if component.html_template:
            code_parts.append(f"<!-- {component.name} HTML Template -->")
            code_parts.append(component.html_template)

        # CSS 样式
        if component.css_styles:
            code_parts.append(f"<style>")
            code_parts.append(f"/* {component.name} Styles */")
            code_parts.append(component.css_styles)
            code_parts.append(f"</style>")

        # JavaScript 类
        if component.js_class:
            code_parts.append(f"<script>")
            code_parts.append(f"// {component.name} JavaScript")
            code_parts.append(component.js_class)
            code_parts.append(f"</script>")

        # 使用示例
        if include_usage:
            code_parts.append(f"\n<!-- {component.name} Usage -->")
            usage = self._generate_usage_example(component)
            code_parts.append(usage)

        return "\n\n".join(code_parts)

    def _generate_usage_example(self, component: AIComponent) -> str:
        """生成使用示例"""
        attrs = []
        for attr in component.attributes[:3]:  # 只显示前 3 个属性
            attrs.append(f'  {attr}=""')

        attrs_str = "\n".join(attrs) if attrs else ""

        return f"""
<{component.tag_name}
{attrs_str}
>
  <!-- Slot content -->
</{component.tag_name}>

<script>
// 注册组件
customElements.define('{component.tag_name}', {component.name.replace('-', '').title().replace('Ai', 'AI')}Component);
</script>
"""

    async def install_component(self, component_id: str) -> str:
        """
        安装组件到本地

        Args:
            component_id: 组件 ID

        Returns:
            str: 安装后的代码片段
        """
        component = self._components.get(component_id)
        if not component:
            raise ValueError(f"Component not found: {component_id}")

        self._installed.add(component_id)
        component.install_count += 1

        return await self.generate_component_code(component_id)

    async def generate_from_ai(
        self,
        prompt: str,
        category: ComponentCategory = ComponentCategory.AI_COMPONENT
    ) -> AIComponent:
        """
        使用 AI 生成组件

        Args:
            prompt: 生成提示
            category: 组件类别

        Returns:
            AIComponent: 生成的组件
        """
        # 生成标签名
        tag_name = f"ai-{prompt.split()[0].lower()[:10]}"
        name = f"AI 生成: {prompt[:20]}"

        if self._ai_generator:
            return await self.create_component(
                name=name,
                tag_name=tag_name,
                category=category,
                ai_prompt=prompt
            )
        else:
            # 默认实现
            return await self.create_component(
                name=name,
                tag_name=tag_name,
                category=category,
                description=prompt
            )

    def get_market_components(
        self,
        category: ComponentCategory = None,
        search: str = "",
        sort_by: str = "install_count"
    ) -> list[AIComponent]:
        """
        获取市场组件列表

        Args:
            category: 类别过滤
            search: 搜索关键词
            sort_by: 排序字段 (install_count/rating/created_at)

        Returns:
            list[AIComponent]: 组件列表
        """
        components = self._components.values()

        # 过滤
        if category:
            components = [c for c in components if c.category == category]

        if search:
            search_lower = search.lower()
            components = [
                c for c in components
                if search_lower in c.name.lower() or search_lower in c.description.lower()
            ]

        # 排序
        if sort_by == "install_count":
            components = sorted(components, key=lambda c: c.install_count, reverse=True)
        elif sort_by == "rating":
            components = sorted(components, key=lambda c: c.rating, reverse=True)
        elif sort_by == "created_at":
            components = sorted(components, key=lambda c: c.created_at, reverse=True)

        return list(components)

    def get_installed(self) -> list[AIComponent]:
        """获取已安装的组件"""
        return [self._components[cid] for cid in self._installed if cid in self._components]

    def get_templates(self) -> list[ComponentTemplate]:
        """获取可用模板列表"""
        return list(self._templates.values())

    def export_component_bundle(self, component_ids: list[str]) -> str:
        """
        导出组件包（包含多个组件）

        Args:
            component_ids: 组件 ID 列表

        Returns:
            str: 打包的代码
        """
        bundle_parts = [
            "<!-- AI Component Bundle -->",
            "<script>window.AI_COMPONENTS = window.AI_COMPONENTS || {};</script>"
        ]

        for cid in component_ids:
            component = self._components.get(cid)
            if component:
                bundle_parts.append(f"\n<!-- {component.name} -->")
                if component.html_template:
                    bundle_parts.append(component.html_template)
                if component.js_class:
                    bundle_parts.append(f"<script>{component.js_class}</script>")

        return "\n\n".join(bundle_parts)

    def generate_installation_script(self, component_ids: list[str]) -> str:
        """
        生成安装脚本

        Args:
            component_ids: 组件 ID 列表

        Returns:
            str: 可在浏览器控制台执行的安装脚本
        """
        scripts = []
        for cid in component_ids:
            component = self._components.get(cid)
            if component:
                scripts.append(f"// {component.name} ({component.tag_name})")
                scripts.append(f"// Installs: {component.install_count}")

                if component.html_template:
                    scripts.append(f"document.write(`{component.html_template}`);")

                if component.js_class:
                    # 提取类名
                    class_match = component.js_class.match(r'class\s+(\w+)\s+extends')
                    if class_match:
                        class_name = class_match.group(1)
                        scripts.append(f"customElements.define('{component.tag_name}', {class_name});")

        return "\n\n".join(scripts)


def create_component_market(data_dir: str = "./data/creative") -> ComponentMarket:
    """创建组件市场实例"""
    return ComponentMarket(data_dir=data_dir)