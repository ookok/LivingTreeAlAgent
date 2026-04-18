"""
浏览器内即圈即生 (Browser Integration)
========================================

核心理念：所见即所创，无缝上下文注入。

功能：
1. 右键增强：选中代码/文本，右键"让 AI 重构/优化"
2. 视觉生成：圈选 UI 组件，生成相似代码
3. 数据抓取：选中表格，生成可视化图表
4. 上下文注入：自动将页面 HTML/CSS/选中内容作为上下文传给 AI
5. 就地渲染：生成的结果直接在浏览器侧边栏预览
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class SelectionType(Enum):
    """选中内容类型"""
    CODE = "code"             # 代码块
    TEXT = "text"            # 普通文本
    IMAGE = "image"           # 图片
    TABLE = "table"           # 表格
    HTML_ELEMENT = "html"     # HTML 元素
    URL = "url"               # 链接


class GenerationIntent(Enum):
    """生成意图"""
    REFACTOR = "refactor"         # 重构代码
    EXPLAIN = "explain"           # 解释代码
    OPTIMIZE = "optimize"         # 优化性能
    TRANSLATE = "translate"       # 翻译
    SUMMARIZE = "summarize"       # 摘要
    VISUALIZE = "visualize"       # 可视化
    COMPLETE = "complete"         # 补全代码
    GENERATE_SIMILAR = "similar"  # 生成相似内容
    CREATE_CHART = "chart"       # 创建图表


@dataclass
class SelectionContext:
    """选中内容的上下文"""
    selection_type: SelectionType
    selected_text: str
    html_element: Optional[str] = None          # 完整 HTML 元素
    css_styles: Optional[str] = None            # 内联 CSS
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    page_dom_snapshot: Optional[str] = None      # DOM 快照
    parent_elements: list[str] = field(default_factory=list)  # 父元素路径
    sibling_count: int = 0                       # 同级元素数量
    metadata: dict = field(default_factory=dict)

    def to_context_prompt(self) -> str:
        """转换为用于 AI 的上下文提示"""
        parts = []

        if self.selection_type == SelectionType.CODE:
            parts.append(f"代码语言: {self.metadata.get('language', 'unknown')}")
            parts.append(f"代码内容:\n{self.selected_text}")

        elif self.selection_type == SelectionType.TEXT:
            parts.append(f"文本内容:\n{self.selected_text}")

        elif self.selection_type == SelectionType.TABLE:
            parts.append(f"表格数据:\n{self.selected_text}")
            if self.metadata.get("headers"):
                parts.append(f"表头: {', '.join(self.metadata['headers'])}")
            if self.metadata.get("row_count"):
                parts.append(f"数据行数: {self.metadata['row_count']}")

        elif self.selection_type == SelectionType.HTML_ELEMENT:
            parts.append(f"HTML 元素:\n{self.html_element}")
            if self.css_styles:
                parts.append(f"内联样式:\n{self.css_styles}")

        if self.page_url:
            parts.append(f"页面 URL: {self.page_url}")
        if self.page_title:
            parts.append(f"页面标题: {self.page_title}")

        return "\n\n".join(parts)


@dataclass
class GenerationRequest:
    """生成请求"""
    request_id: str
    intent: GenerationIntent
    context: SelectionContext
    user_instruction: str                    # 用户额外指令
    created_at: datetime = field(default_factory=datetime.now)
    preferred_tone: str = "casual"           # 偏好语气

    @classmethod
    def create(
        cls,
        intent: GenerationIntent,
        context: SelectionContext,
        user_instruction: str = "",
        preferred_tone: str = "casual"
    ) -> "GenerationRequest":
        return cls(
            request_id=hashlib.sha256(f"{time.time()}{intent.value}".encode()).hexdigest()[:12],
            intent=intent,
            context=context,
            user_instruction=user_instruction,
            preferred_tone=preferred_tone
        )


@dataclass
class GenerationResponse:
    """生成响应"""
    request_id: str
    content: str
    content_type: str                        # code/html/markdown/chart_url
    preview_html: Optional[str] = None       # 预览 HTML
    execution_command: Optional[str] = None  # 可执行的命令
    language_hint: Optional[str] = None     # 语言提示（用于代码高亮）
    confidence: float = 1.0                  # 置信度
    suggestions: list[str] = field(default_factory=list)  # 后续建议


class BrowserIntegration:
    """
    浏览器内即圈即生集成

    用法:
        integration = BrowserIntegration()

        # 注册到浏览器
        await integration.setup_browser_injection(
            browser_view=webview
        )

        # 或者接收来自网页的消息
        async def handle_js_message(message):
            return await integration.process_js_request(message)
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._intent_classifier: Optional[Callable] = None
        self._generator: Optional[Any] = None
        self._execution_handler: Optional[Callable] = None
        self._preview_renderer: Optional[Callable] = None
        self._history: list[GenerationRequest] = []

    def set_generator(self, generator: Any) -> None:
        """设置生成器（通常是 DistributedGenerator）"""
        self._generator = generator

    def set_intent_classifier(self, classifier: Callable) -> None:
        """设置意图分类器"""
        self._intent_classifier = classifier

    def set_execution_handler(self, handler: Callable) -> None:
        """设置执行处理器"""
        self._execution_handler = handler

    def set_preview_renderer(self, renderer: Callable) -> None:
        """设置预览渲染器"""
        self._preview_renderer = renderer

    def detect_selection_type(self, text: str, html: str = "") -> SelectionType:
        """
        自动检测选中内容的类型

        Args:
            text: 选中的文本
            html: 完整的 HTML 元素（如果有）

        Returns:
            SelectionType: 检测到的类型
        """
        # 代码检测：包含常见代码模式
        code_patterns = [
            r'function\s+\w+\s*\(',
            r'class\s+\w+\s*[:{]',
            r'def\s+\w+\s*\(',
            r'import\s+\w+',
            r'const\s+\w+\s*=',
            r'let\s+\w+\s*=',
            r'var\s+\w+\s*=',
            r'=>\s*{',
            r'->\s*{',
            r'if\s*\(',
            r'for\s*\(',
            r'while\s*\(',
            r'<\w+[^>]*>.*</\w+>',
        ]

        for pattern in code_patterns:
            if re.search(pattern, text) or re.search(pattern, html):
                return SelectionType.CODE

        # HTML 元素检测
        if re.match(r'<[a-z]+[^>]*>.*</[a-z]+>', html, re.DOTALL):
            return SelectionType.HTML_ELEMENT

        # 表格检测：包含制表符或多个分隔符
        if '\t' in text or '|' in text:
            lines = text.strip().split('\n')
            if len(lines) > 1 and all('|' in line or '\t' in line for line in lines[:5]):
                return SelectionType.TABLE

        # 图片 URL 检测
        if re.match(r'https?://.*\.(jpg|jpeg|png|gif|webp|svg)', text, re.I):
            return SelectionType.IMAGE

        # URL 检测
        if re.match(r'https?://', text):
            return SelectionType.URL

        return SelectionType.TEXT

    def classify_intent(self, text: str, instruction: str = "") -> GenerationIntent:
        """
        分类用户意图

        Args:
            text: 选中的文本
            instruction: 用户的额外指令

        Returns:
            GenerationIntent: 分类的意图
        """
        if self._intent_classifier:
            return self._intent_classifier(text, instruction)

        # 简单的关键词匹配分类器
        text_lower = (text + instruction).lower()

        intent_keywords = {
            GenerationIntent.REFACTOR: ["重构", "refactor", "优化代码", "重写"],
            GenerationIntent.EXPLAIN: ["解释", "explain", "这是什么", "什么意思"],
            GenerationIntent.OPTIMIZE: ["优化", "optimize", "性能", "更快"],
            GenerationIntent.TRANSLATE: ["翻译", "translate", "改成英文", "改成中文"],
            GenerationIntent.SUMMARIZE: ["摘要", "summarize", "总结", "概括"],
            GenerationIntent.VISUALIZE: ["可视化", "visualize", "画图", "图表"],
            GenerationIntent.COMPLETE: ["补全", "complete", "完成", "写完"],
            GenerationIntent.GENERATE_SIMILAR: ["类似", "similar", "生成一个", "模仿"],
            GenerationIntent.CREATE_CHART: ["图表", "chart", "折线图", "柱状图", "饼图"],
        }

        for intent, keywords in intent_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return intent

        # 默认基于选中内容类型推断
        if self.detect_selection_type(text) == SelectionType.CODE:
            return GenerationIntent.REFACTOR
        return GenerationIntent.EXPLAIN

    async def process_selection(
        self,
        selected_text: str,
        html_element: str = "",
        page_url: str = "",
        page_title: str = "",
        user_instruction: str = ""
    ) -> GenerationResponse:
        """
        处理选中内容，生成响应

        这是一个完整的处理流程：
        1. 检测类型
        2. 分类意图
        3. 构建上下文
        4. 调用生成器
        5. 构建预览
        """
        # 1. 检测类型
        selection_type = self.detect_selection_type(selected_text, html_element)

        # 2. 构建上下文
        context = SelectionContext(
            selection_type=selection_type,
            selected_text=selected_text,
            html_element=html_element,
            page_url=page_url,
            page_title=page_title,
            metadata=self._extract_metadata(selected_text, html_element)
        )

        # 3. 分类意图
        intent = self.classify_intent(selected_text, user_instruction)

        # 4. 创建请求
        request = GenerationRequest.create(
            intent=intent,
            context=context,
            user_instruction=user_instruction
        )
        self._history.append(request)

        # 5. 生成内容
        content, content_type, language_hint = await self._generate_content(
            intent=intent,
            context=context,
            user_instruction=user_instruction
        )

        # 6. 构建预览
        preview_html = await self._build_preview(
            content=content,
            content_type=content_type,
            intent=intent,
            context=context
        )

        # 7. 构建执行命令
        execution_command = self._build_execution_command(
            content=content,
            content_type=content_type
        )

        return GenerationResponse(
            request_id=request.request_id,
            content=content,
            content_type=content_type,
            preview_html=preview_html,
            execution_command=execution_command,
            language_hint=language_hint,
            suggestions=self._generate_suggestions(intent, content_type)
        )

    def _extract_metadata(self, text: str, html: str) -> dict:
        """提取元数据"""
        metadata = {}

        # 表格元数据
        if '\t' in text or '|' in text:
            lines = text.strip().split('\n')
            if len(lines) > 0:
                first_line = lines[0].strip('| \t')
                headers = [h.strip() for h in re.split(r'[\t|]', first_line)]
                metadata["headers"] = headers
                metadata["row_count"] = len(lines) - 1 if len(lines) > 1 else 0

        # 代码语言检测
        if self.detect_selection_type(text) == SelectionType.CODE:
            language_patterns = {
                "python": [r"def\s+\w+\s*\(", r"import\s+\w+", r"from\s+\w+\s+import"],
                "javascript": [r"const\s+\w+", r"let\s+\w+", r"function\s+\w+", r"=>\s*{"],
                "html": [r"<[a-z]+[^>]*>", r"</[a-z]+>"],
                "css": [r"{\s*[\w-]+\s*:\s*[^;]+;", r"\.[\w-]+\s*{"],
                "rust": [r"fn\s+\w+\s*\(", r"let\s+mut\s+", r"impl\s+\w+"],
                "go": [r"func\s+\w+\s*\(", r"package\s+\w+", r":="],
            }

            for lang, patterns in language_patterns.items():
                if any(re.search(p, text) for p in patterns):
                    metadata["language"] = lang
                    break

        return metadata

    async def _generate_content(
        self,
        intent: GenerationIntent,
        context: SelectionContext,
        user_instruction: str
    ) -> tuple[str, str, Optional[str]]:
        """调用生成器生成内容"""
        if self._generator:
            # 使用分布式生成器
            prompt = self._build_prompt(intent, context, user_instruction)
            result = await self._generator.generate_with_context(
                prompt=prompt,
                context_content=context.to_context_prompt(),
                context_type=context.selection_type.value
            )

            if result.best_version:
                content = result.best_version.content
                content_type = "code" if context.selection_type == SelectionType.CODE else "text"
                return content, content_type, context.metadata.get("language")

        # 默认实现
        return self._default_generation(intent, context, user_instruction)

    def _build_prompt(
        self,
        intent: GenerationIntent,
        context: SelectionContext,
        user_instruction: str
    ) -> str:
        """构建生成提示"""
        intent_prompts = {
            GenerationIntent.REFACTOR: "请重构以下代码，使其更清晰、更高效：\n\n",
            GenerationIntent.EXPLAIN: "请解释以下代码的功能和工作原理：\n\n",
            GenerationIntent.OPTIMIZE: "请优化以下代码的性能：\n\n",
            GenerationIntent.TRANSLATE: "请将以下内容翻译成中文：\n\n",
            GenerationIntent.SUMMARIZE: "请总结以下内容的要点：\n\n",
            GenerationIntent.VISUALIZE: "请为以下数据设计一个可视化方案：\n\n",
            GenerationIntent.COMPLETE: "请补全以下代码：\n\n",
            GenerationIntent.GENERATE_SIMILAR: "请生成一个类似的内容：\n\n",
            GenerationIntent.CREATE_CHART: "请为以下数据生成图表代码（HTML/JavaScript）：\n\n",
        }

        prompt = intent_prompts.get(intent, "请处理以下内容：\n\n")
        if user_instruction:
            prompt += f"用户额外要求：{user_instruction}\n\n"

        return prompt

    def _default_generation(
        self,
        intent: GenerationIntent,
        context: SelectionContext,
        user_instruction: str
    ) -> tuple[str, str, Optional[str]]:
        """默认生成（当没有配置生成器时）"""
        # 简单模拟
        content_type = context.selection_type.value
        language = context.metadata.get("language")

        if intent == GenerationIntent.EXPLAIN:
            content = f"**内容解释**\n\n选中的是{context.selection_type.value}类型的{len(context.selected_text)}字符内容。"
            content += f"\n\n```\n{context.selected_text[:200]}...\n```"
            return content, "markdown", None

        elif intent == GenerationIntent.REFACTOR:
            if context.selection_type == SelectionType.CODE:
                content = f"```{(language or 'javascript')}\n// 重构后的代码\n{context.selected_text}\n```"
                return content, "code", language

        elif intent == GenerationIntent.CREATE_CHART:
            content = """```html
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
new Chart(document.getElementById('chart'), {
    type: 'bar',
    data: { labels: ['A', 'B', 'C'], datasets: [{ data: [10, 20, 30] }] }
});
</script>
```"""
            return content, "html", "html"

        content = f"[AI 生成内容]\n\n基于您的选中内容（{intent.value}）"
        return content, content_type, language

    async def _build_preview(
        self,
        content: str,
        content_type: str,
        intent: GenerationIntent,
        context: SelectionContext
    ) -> Optional[str]:
        """构建预览 HTML"""
        if self._preview_renderer:
            return await self._preview_renderer(content, content_type, intent)

        # 内置预览构建
        if content_type == "code":
            lang = context.metadata.get("language", "javascript")
            return f"""
<div class="preview-container">
    <pre><code class="language-{lang}">{self._escape_html(content)}</code></pre>
</div>
<style>
.preview-container {{ background: #1e1e1e; padding: 16px; border-radius: 8px; }}
pre {{ margin: 0; overflow-x: auto; }}
</style>
"""

        elif content_type == "html":
            return f"""
<div class="preview-container">
    <iframe srcdoc="{self._escape_html(content)}" sandbox="allow-scripts"></iframe>
</div>
<style>
.preview-container {{ border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
iframe {{ width: 100%; height: 300px; border: none; }}
</style>
"""

        return None

    def _build_execution_command(self, content: str, content_type: str) -> Optional[str]:
        """构建执行命令"""
        if content_type == "code":
            # 提取语言
            if "```python" in content:
                return "python -c \"exec(open('temp.py').read())\""
            elif "```javascript" in content:
                return "node -e \"eval(require('fs').readFileSync('temp.js','utf8'))\""
            elif "```bash" in content:
                return "bash temp.sh"

        return None

    def _generate_suggestions(self, intent: GenerationIntent, content_type: str) -> list[str]:
        """生成后续建议"""
        suggestions = []

        if intent == GenerationIntent.REFACTOR:
            suggestions = [
                "在边缘节点运行测试",
                "查看性能对比",
                "提交到 Git"
            ]
        elif intent == GenerationIntent.EXPLAIN:
            suggestions = [
                "生成流程图",
                "创建技术文档"
            ]
        elif intent == GenerationIntent.CREATE_CHART:
            suggestions = [
                "在浏览器中预览",
                "导出为 PNG",
                "调整配色方案"
            ]

        return suggestions

    def _escape_html(self, text: str) -> str:
        """HTML 转义"""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))

    async def setup_browser_injection(self, browser_view) -> str:
        """
        生成注入到浏览器的 JavaScript 代码

        返回要注入的 JavaScript 脚本
        """
        injection_script = """
(function() {
    // 创建 AI 助手侧边栏
    const sidebar = document.createElement('div');
    sidebar.id = 'hyperos-ai-sidebar';
    sidebar.innerHTML = `
        <div class="sidebar-header">
            <span>AI 创作助手</span>
            <button class="close-btn">&times;</button>
        </div>
        <div class="sidebar-content">
            <div class="selection-hint">选中内容后右键使用 AI</div>
        </div>
    `;
    sidebar.style.cssText = `
        position: fixed; top: 0; right: -350px; width: 350px; height: 100vh;
        background: #fff; box-shadow: -2px 0 10px rgba(0,0,0,0.1); z-index: 999999;
        transition: right 0.3s; font-family: system-ui; overflow: hidden;
    `;
    document.body.appendChild(sidebar);

    // 暴露 API
    window.hyperosAI = {
        async generate(options) {
            // 处理生成请求
            const response = await fetch('/hyperos-ai/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });
            return response.json();
        },

        showSidebar() {
            sidebar.style.right = '0';
        },

        hideSidebar() {
            sidebar.style.right = '-350px';
        }
    };

    // 右键菜单
    document.addEventListener('contextmenu', async (e) => {
        const selection = window.getSelection().toString();
        if (!selection) return;

        const menu = document.createElement('div');
        menu.id = 'hyperos-ai-menu';
        menu.innerHTML = `
            <div class="menu-item" data-action="refactor">🔄 AI 重构此代码</div>
            <div class="menu-item" data-action="explain">📖 解释这段内容</div>
            <div class="menu-item" data-action="optimize">⚡ 优化性能</div>
            <div class="menu-item" data-action="translate">🌐 翻译</div>
            <div class="menu-item" data-action="summarize">📝 摘要</div>
            <div class="menu-item" data-action="visualize">📊 可视化</div>
        `;
        menu.style.cssText = `
            position: fixed; left: ${e.clientX}px; top: ${e.clientY}px;
            background: #fff; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 8px 0; min-width: 180px; z-index: 1000000;
        `;

        document.querySelectorAll('.hyperos-ai-menu').forEach(m => m.remove());
        menu.classList.add('hyperos-ai-menu');
        document.body.appendChild(menu);

        menu.querySelectorAll('.menu-item').forEach(item => {
            item.style.cssText = 'padding: 8px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px;';
            item.addEventListener('mouseenter', () => item.style.background = '#f5f5f5');
            item.addEventListener('mouseleave', () => item.style.background = 'transparent');
            item.addEventListener('click', async () => {
                const action = item.dataset.action;
                const html = selection;

                // 调用生成接口
                const result = await window.hyperosAI.generate({
                    intent: action,
                    selected_text: selection,
                    html_element: html,
                    page_url: location.href,
                    page_title: document.title
                });

                // 显示结果
                window.hyperosAI.showResult(result);
                menu.remove();
            });
        });
    });

    console.log('[HyperOS AI] 浏览器集成已加载');
})();
"""
        return injection_script

    def get_history(self, limit: int = 50) -> list[GenerationRequest]:
        """获取历史请求"""
        return self._history[-limit:]


def create_browser_integration(data_dir: str = "./data/creative") -> BrowserIntegration:
    """创建浏览器集成实例"""
    return BrowserIntegration(data_dir=data_dir)