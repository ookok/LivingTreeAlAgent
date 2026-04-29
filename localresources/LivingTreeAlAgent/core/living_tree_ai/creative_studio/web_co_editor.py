"""
网页内嵌的实时 AI 协同编辑器 (Web Co-Editor)
============================================

核心功能：
1. 实时协同：用户在网页编辑器中打字，AI 实时提供补全、修正、建议
2. 代码可视化：编写代码时，右侧实时渲染结果
3. 风格转移：AI 分析页面 CSS，生成匹配风格的 HTML 组件
4. AI 直接操作 DOM：AI 可以直接修改预览区来示范效果
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


class EditorLanguage(Enum):
    """编辑器语言"""
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    PYTHON = "python"
    MARKDOWN = "markdown"
    JSON = "json"


class SuggestionType(Enum):
    """建议类型"""
    COMPLETION = "completion"       # 自动补全
    CORRECTION = "correction"      # 错误修正
    OPTIMIZATION = "optimization"  # 性能优化
    EXPLANATION = "explanation"    # 解释说明
    REFACTOR = "refactor"          # 重构建议
    VISUALIZATION = "visualization"  # 可视化建议


@dataclass
class EditorState:
    """编辑器状态"""
    document_id: str
    content: str
    language: EditorLanguage
    cursor_position: int = 0
    selection_start: int = 0
    selection_end: int = 0
    version: int = 0
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class Suggestion:
    """AI 建议"""
    suggestion_id: str
    suggestion_type: SuggestionType
    content: str                      # 建议内容
    original_text: str = ""          # 被替换的原文
    replacement_text: str = ""       # 替换文本
    confidence: float = 1.0          # 置信度
    position: tuple[int, int] = (0, 0)  # 在文档中的位置
    applies_to_selection: bool = False
    preview_html: str = ""           # 可选的预览 HTML
    apply_mode: str = "replace"       # replace/insert/before/after
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class WebCoEditor:
    """
    网页内嵌的实时 AI 协同编辑器

    用法:
        editor = WebCoEditor()

        # 生成编辑器 HTML
        editor_html = editor.generate_editor_html(
            language=EditorLanguage.HTML,
            initial_code="<div>Hello World</div>"
        )

        # 处理来自网页的消息
        async def handle_message(msg):
            return await editor.process_message(msg)

        # 注册 AI 处理器
        editor.register_ai_handler(my_ai_handler)
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._ai_handler: Optional[Callable] = None
        self._dom_manipulator: Optional[Callable] = None
        self._documents: dict[str, EditorState] = {}
        self._suggestions: dict[str, list[Suggestion]] = {}
        self._history: list[dict] = []

    def register_ai_handler(self, handler: Callable) -> None:
        """注册 AI 处理器"""
        self._ai_handler = handler

    def register_dom_manipulator(self, manipulator: Callable) -> None:
        """注册 DOM 操作器"""
        self._dom_manipulator = manipulator

    async def process_message(self, message: dict) -> dict:
        """
        处理来自网页编辑器的消息

        Args:
            message: 消息格式 {"type": "...", "payload": {...}}

        Returns:
            dict: 响应
        """
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type == "content_change":
            return await self._handle_content_change(payload)
        elif msg_type == "cursor_change":
            return await self._handle_cursor_change(payload)
        elif msg_type == "request_suggestion":
            return await self._handle_suggestion_request(payload)
        elif msg_type == "apply_suggestion":
            return await self._handle_apply_suggestion(payload)
        elif msg_type == "preview_update":
            return await self._handle_preview_update(payload)
        elif msg_type == "style_transfer":
            return await self._handle_style_transfer(payload)
        else:
            return {"type": "error", "message": f"Unknown message type: {msg_type}"}

    async def _handle_content_change(self, payload: dict) -> dict:
        """处理内容变化"""
        doc_id = payload.get("document_id")
        content = payload.get("content", "")
        version = payload.get("version", 0)

        if doc_id not in self._documents:
            language = self._detect_language(content)
            self._documents[doc_id] = EditorState(
                document_id=doc_id,
                content=content,
                language=language
            )
        else:
            doc = self._documents[doc_id]
            doc.content = content
            doc.version = version
            doc.updated_at = datetime.now()

        return {"type": "ack", "document_id": doc_id, "version": version}

    async def _handle_cursor_change(self, payload: dict) -> dict:
        """处理光标变化"""
        doc_id = payload.get("document_id")
        cursor = payload.get("cursor_position", 0)
        selection = payload.get("selection", {})

        if doc_id in self._documents:
            doc = self._documents[doc_id]
            doc.cursor_position = cursor
            doc.selection_start = selection.get("start", 0)
            doc.selection_end = selection.get("end", 0)

        # 触发上下文感知的 AI 分析
        if self._ai_handler:
            context = self._get_cursor_context(doc_id, cursor)
            asyncio.create_task(self._ai_handler(context))

        return {"type": "ack", "cursor_position": cursor}

    async def _handle_suggestion_request(self, payload: dict) -> dict:
        """处理建议请求"""
        doc_id = payload.get("document_id")
        request_type = payload.get("request_type", "general")  # general/completion/explanation

        if doc_id not in self._documents:
            return {"type": "error", "message": "Document not found"}

        doc = self._documents[doc_id]

        if self._ai_handler:
            suggestions = await self._ai_handler({
                "type": request_type,
                "document": doc.__dict__,
                "context": self._get_cursor_context(doc_id, doc.cursor_position)
            })

            # 缓存建议
            self._suggestions[doc_id] = suggestions
            return {
                "type": "suggestions",
                "suggestions": [s.__dict__ for s in suggestions]
            }

        return {"type": "suggestions", "suggestions": []}

    async def _handle_apply_suggestion(self, payload: dict) -> dict:
        """应用建议"""
        doc_id = payload.get("document_id")
        suggestion_id = payload.get("suggestion_id")
        action = payload.get("action", "apply")  # apply/preview/cancel

        suggestions = self._suggestions.get(doc_id, [])
        suggestion = next((s for s in suggestions if s.suggestion_id == suggestion_id), None)

        if not suggestion:
            return {"type": "error", "message": "Suggestion not found"}

        if action == "apply":
            return {
                "type": "apply_suggestion",
                "original_text": suggestion.original_text,
                "replacement_text": suggestion.replacement_text,
                "apply_mode": suggestion.apply_mode
            }
        elif action == "preview":
            return {
                "type": "preview_suggestion",
                "preview_html": suggestion.preview_html or self._generate_preview(
                    suggestion.replacement_text
                )
            }

        return {"type": "ack"}

    async def _handle_preview_update(self, payload: dict) -> dict:
        """处理预览更新"""
        html = payload.get("html", "")
        css = payload.get("css", "")
        js = payload.get("js", "")

        # 生成预览 HTML
        preview_html = self._generate_preview(html, css, js)

        return {
            "type": "preview_update",
            "preview_html": preview_html,
            "sandbox": self._generate_sandbox_html()
        }

    async def _handle_style_transfer(self, payload: dict) -> dict:
        """处理风格迁移"""
        source_html = payload.get("source_html", "")
        target_style = payload.get("target_style", {})  # CSS 属性

        # 提取源 HTML 的样式
        extracted_styles = self._extract_styles(source_html)

        # 生成匹配目标风格的新 HTML
        if self._ai_handler:
            result = await self._ai_handler({
                "type": "style_transfer",
                "source_html": source_html,
                "source_styles": extracted_styles,
                "target_styles": target_style
            })
            return {
                "type": "style_transfer_result",
                "generated_html": result.get("html", ""),
                "generated_css": result.get("css", "")
            }

        return {"type": "error", "message": "AI handler not configured"}

    def _detect_language(self, content: str) -> EditorLanguage:
        """检测语言"""
        content_lower = content.lower()

        if re.match(r'<\w+[^>]*>.*</\w+>', content, re.DOTALL):
            return EditorLanguage.HTML
        elif re.search(r'<\w+[^>]*>', content):
            return EditorLanguage.HTML
        elif '{' in content and ':' in content and 'px' in content or 'em' in content:
            return EditorLanguage.CSS
        elif 'function' in content or 'const' in content or 'let' in content or '=>' in content:
            return EditorLanguage.JAVASCRIPT
        elif 'def ' in content and ':' in content:
            return EditorLanguage.PYTHON
        elif '#' in content and '##' in content:
            return EditorLanguage.MARKDOWN

        return EditorLanguage.JAVASCRIPT

    def _get_cursor_context(self, doc_id: str, cursor: int) -> dict:
        """获取光标上下文"""
        if doc_id not in self._documents:
            return {}

        doc = self._documents[doc_id]
        content = doc.content

        # 获取光标前后各 100 个字符
        start = max(0, cursor - 100)
        end = min(len(content), cursor + 100)

        before = content[start:cursor]
        after = content[cursor:end]

        # 尝试确定当前上下文（函数、标签等）
        context_type = "text"
        context_name = ""

        if doc.language == EditorLanguage.JAVASCRIPT:
            func_match = re.search(r'(function|class|const|let|var)\s+(\w+)', before)
            if func_match:
                context_type = "function"
                context_name = func_match.group(2)

        elif doc.language == EditorLanguage.HTML:
            tag_match = re.search(r'<(\w+)[^>]*>$', before)
            if tag_match:
                context_type = "tag"
                context_name = tag_match.group(1)

        return {
            "document_id": doc_id,
            "language": doc.language.value,
            "cursor_position": cursor,
            "before": before,
            "after": after,
            "context_type": context_type,
            "context_name": context_name,
            "selected_text": doc.content[doc.selection_start:doc.selection_end] if doc.selection_start != doc.selection_end else ""
        }

    def _extract_styles(self, html: str) -> dict:
        """从 HTML 中提取样式"""
        styles = {
            "colors": [],
            "fonts": [],
            "spacing": [],
            "borders": [],
            "animations": []
        }

        # 提取颜色
        colors = re.findall(r'color:\s*([^;]+)', html)
        styles["colors"].extend(colors)

        # 提取字体
        fonts = re.findall(r'font-family:\s*([^;]+)', html)
        styles["fonts"].extend(fonts)

        # 提取间距
        spacing = re.findall(r'(margin|padding):\s*([^;]+)', html)
        styles["spacing"].extend([f"{k}: {v}" for k, v in spacing])

        return styles

    def _generate_preview(self, html: str, css: str = "", js: str = "") -> str:
        """生成预览 HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            margin: 0; 
            padding: 16px; 
            font-family: system-ui, -apple-system, sans-serif;
        }}
        {css}
    </style>
</head>
<body>
    {html}
    <script>
        try {{
            {js}
        }} catch (e) {{
            console.error('Script error:', e);
        }}
    </script>
</body>
</html>
"""

    def _generate_sandbox_html(self) -> str:
        """生成沙箱 HTML"""
        return """
<iframe id="preview-sandbox" sandbox="allow-scripts allow-forms"
    style="width: 100%; height: 100%; border: none;"></iframe>
"""

    def generate_editor_html(
        self,
        language: EditorLanguage = EditorLanguage.HTML,
        initial_code: str = "",
        theme: str = "light",
        show_preview: bool = True,
        show_ai_sidebar: bool = True
    ) -> str:
        """
        生成编辑器 HTML

        Args:
            language: 编程语言
            initial_code: 初始代码
            theme: 主题 (light/dark)
            show_preview: 是否显示预览区
            show_ai_sidebar: 是否显示 AI 侧边栏

        Returns:
            str: 编辑器 HTML
        """
        theme_vars = {
            "light": {
                "bg": "#ffffff",
                "fg": "#1a1a1a",
                "accent": "#4A90D9",
                "border": "#e0e0e0",
                "sidebar_bg": "#f5f5f5"
            },
            "dark": {
                "bg": "#1e1e1e",
                "fg": "#d4d4d4",
                "accent": "#569CD6",
                "border": "#404040",
                "sidebar_bg": "#252526"
            }
        }.get(theme, {})

        return f"""
<div class="creative-studio" data-language="{language.value}">
    <div class="studio-toolbar">
        <div class="toolbar-left">
            <span class="lang-badge">{language.value.upper()}</span>
            <button class="btn" id="btn-run" title="运行 (Ctrl+Enter)">
                ▶ 运行
            </button>
            <button class="btn" id="btn-format" title="格式化">
                ⋄ 格式化
            </button>
        </div>
        <div class="toolbar-right">
            <button class="btn" id="btn-ai" title="AI 助手">
                🤖 AI
            </button>
            <button class="btn" id="btn-settings" title="设置">
                ⚙
            </button>
        </div>
    </div>

    <div class="studio-main">
        <div class="code-editor" id="editor">
            <textarea id="code-input" spellcheck="false">{initial_code}</textarea>
            <div class="line-numbers" id="line-numbers"></div>
            <div class="suggestions-overlay" id="suggestions-overlay"></div>
        </div>

        {'<div class="live-preview" id="preview">' + '''
            <iframe id="preview-frame" sandbox="allow-scripts"></iframe>
        </div>''' if show_preview else ''}

        {'''<div class="ai-sidebar" id="ai-sidebar">
            <div class="sidebar-header">
                <span>🤖 AI 助手</span>
                <button class="close-btn" id="close-sidebar">×</button>
            </div>
            <div class="sidebar-content" id="ai-content">
                <div class="ai-status">等待输入...</div>
            </div>
            <div class="sidebar-input">
                <textarea id="ai-prompt" placeholder="向 AI 提问或下达指令..."></textarea>
                <button class="btn-send" id="btn-send">发送</button>
            </div>
        </div>''' if show_ai_sidebar else ''}
    </div>

    <style>
        .creative-studio {{
            display: flex;
            flex-direction: column;
            height: 100vh;
            font-family: system-ui, -apple-system, sans-serif;
            background: {theme_vars.get("bg", "#fff")};
            color: {theme_vars.get("fg", "#1a1a1a")};
        }}
        .studio-toolbar {{
            display: flex;
            justify-content: space-between;
            padding: 8px 16px;
            background: {theme_vars.get("sidebar_bg", "#f5f5f5")};
            border-bottom: 1px solid {theme_vars.get("border", "#e0e0e0")};
        }}
        .toolbar-left, .toolbar-right {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        .lang-badge {{
            padding: 4px 8px;
            background: {theme_vars.get("accent", "#4A90D9")};
            color: white;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .btn {{
            padding: 6px 12px;
            border: 1px solid {theme_vars.get("border", "#e0e0e0")};
            background: {theme_vars.get("bg", "#fff")};
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }}
        .btn:hover {{
            background: {theme_vars.get("sidebar_bg", "#f5f5f5")};
        }}
        .studio-main {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        .code-editor {{
            flex: 1;
            position: relative;
            display: flex;
        }}
        #code-input {{
            flex: 1;
            padding: 16px;
            padding-left: 50px;
            border: none;
            resize: none;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
            line-height: 1.5;
            background: transparent;
            color: {theme_vars.get("fg", "#1a1a1a")};
            outline: none;
            white-space: pre;
            overflow-x: auto;
        }}
        .line-numbers {{
            position: absolute;
            left: 0;
            top: 16px;
            width: 40px;
            text-align: right;
            padding-right: 8px;
            color: #888;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
            line-height: 1.5;
            user-select: none;
        }}
        .live-preview {{
            flex: 1;
            border-left: 1px solid {theme_vars.get("border", "#e0e0e0")};
        }}
        #preview-frame {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        .ai-sidebar {{
            width: 320px;
            border-left: 1px solid {theme_vars.get("border", "#e0e0e0")};
            display: flex;
            flex-direction: column;
            background: {theme_vars.get("sidebar_bg", "#f5f5f5")};
        }}
        .sidebar-header {{
            padding: 12px 16px;
            border-bottom: 1px solid {theme_vars.get("border", "#e0e0e0")};
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sidebar-content {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}
        .ai-status {{
            color: #888;
            font-size: 13px;
        }}
        .suggestion-item {{
            padding: 8px 12px;
            margin: 4px 0;
            background: {theme_vars.get("bg", "#fff")};
            border: 1px solid {theme_vars.get("border", "#e0e0e0")};
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
        }}
        .suggestion-item:hover {{
            border-color: {theme_vars.get("accent", "#4A90D9")};
        }}
        .suggestion-item.accepted {{
            background: #e8f5e9;
            border-color: #4CAF50;
        }}
        .sidebar-input {{
            padding: 12px;
            border-top: 1px solid {theme_vars.get("border", "#e0e0e0")};
            display: flex;
            gap: 8px;
        }}
        #ai-prompt {{
            flex: 1;
            padding: 8px;
            border: 1px solid {theme_vars.get("border", "#e0e0e0")};
            border-radius: 4px;
            resize: none;
            font-size: 13px;
        }}
        .btn-send {{
            padding: 8px 16px;
            background: {theme_vars.get("accent", "#4A90D9")};
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
    </style>

    <script>
        (function() {{
            // 初始化
            const editor = document.getElementById('code-input');
            const lineNumbers = document.getElementById('line-numbers');

            // 更新行号
            function updateLineNumbers() {{
                const lines = editor.value.split('\\n');
                lineNumbers.innerHTML = lines.map((_, i) =>
                    '<div>' + (i + 1) + '</div>'
                ).join('');
            }}
            editor.addEventListener('input', updateLineNumbers);
            editor.addEventListener('scroll', () => {{
                lineNumbers.scrollTop = editor.scrollTop;
            }});
            updateLineNumbers();

            // 发送消息到 AI
            function sendToAI(type, payload) {{
                window.parent.postMessage({{
                    type: 'creative-studio',
                    studio_type: 'web_co_editor',
                    action: type,
                    payload: payload
                }}, '*');
            }};

            // 监听 AI 响应
            window.addEventListener('message', (event) => {{
                const msg = event.data;
                if (msg.type !== 'creative-studio-response') return;

                const action = msg.action;
                const data = msg.data;

                if (action === 'suggestions') {{
                    showSuggestions(data.suggestions);
                }} else if (action === 'preview_update') {{
                    updatePreview(data.preview_html);
                }}
            }});

            // 显示建议
            function showSuggestions(suggestions) {{
                const overlay = document.getElementById('suggestions-overlay');
                if (!overlay) return;

                overlay.innerHTML = suggestions.map(s => `
                    <div class="suggestion-item" data-id="${{s.suggestion_id}}">
                        <span class="suggestion-type">[${{s.suggestion_type}}]</span>
                        ${{s.content.substring(0, 100)}}...
                    </div>
                `).join('');

                overlay.querySelectorAll('.suggestion-item').forEach(item => {{
                    item.addEventListener('click', () => {{
                        sendToAI('apply_suggestion', {{
                            suggestion_id: item.dataset.id
                        }});
                    }});
                }});
            }}

            // 更新预览
            function updatePreview(html) {{
                const frame = document.getElementById('preview-frame');
                if (frame && html) {{
                    frame.srcdoc = html;
                }}
            }}

            // 初始化 AI 通信
            window.aiAssistant = {{
                suggest: function(code) {{
                    sendToAI('request_suggestion', {{ code: code }});
                }},
                applySuggestion: function(id) {{
                    sendToAI('apply_suggestion', {{ suggestion_id: id }});
                }},
                updatePreview: function(html, css, js) {{
                    sendToAI('preview_update', {{ html, css, js }});
                }},
                transferStyle: function(sourceHtml, targetStyle) {{
                    sendToAI('style_transfer', {{
                        source_html: sourceHtml,
                        target_style: targetStyle
                    }});
                }}
            }};

            console.log('[Creative Studio] Web Co-Editor loaded');
        }})();
    </script>
</div>
"""

    async def generate_completion_handler(self, context: dict) -> list[Suggestion]:
        """生成补全建议的默认处理器"""
        suggestions = []

        cursor_context = context.get("context", {})
        language = cursor_context.get("language", "javascript")
        before = cursor_context.get("before", "")
        after = cursor_context.get("after", "")

        # 简单的模板补全
        if language == "html":
            if before.endswith("<"):
                suggestions.append(Suggestion(
                    suggestion_id="html-tag",
                    suggestion_type=SuggestionType.COMPLETION,
                    content="建议标签",
                    replacement_text="div>",
                    confidence=0.9
                ))
            if "</" in before and not after:
                # 自动闭合标签
                tag_match = re.search(r'<(\w+)[^>]*>$', before)
                if tag_match:
                    tag_name = tag_match.group(1)
                    suggestions.append(Suggestion(
                        suggestion_id="close-tag",
                        suggestion_type=SuggestionType.COMPLETION,
                        content=f"闭合标签 </{tag_name}>",
                        replacement_text=f"</{tag_name}>",
                        confidence=1.0
                    ))

        return suggestions

    def get_document(self, doc_id: str) -> Optional[EditorState]:
        """获取文档状态"""
        return self._documents.get(doc_id)

    def get_suggestions(self, doc_id: str) -> list[Suggestion]:
        """获取文档的建议"""
        return self._suggestions.get(doc_id, [])


def create_web_co_editor(data_dir: str = "./data/creative") -> WebCoEditor:
    """创建网页协同编辑器实例"""
    return WebCoEditor(data_dir=data_dir)