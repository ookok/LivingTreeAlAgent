"""
学习浏览器
主界面组件，使用 WebView 渲染富文本内容
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QScrollArea, QFrame
)
from PyQt6.QtGui import QKeyEvent

import json
import os
from pathlib import Path

# 尝试导入 WebEngine，失败时提供降级方案
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebChannel, QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None
    QWebChannel = None
    QWebEngineSettings = None

# 尝试导入标签桥
try:
    from .tag_bridge import TagClickBridge
except ImportError:
    TagClickBridge = None


class LearningBrowser(QWidget):
    """
    学习世界主浏览器
    
    信号:
        query_submitted(query: str) - 用户提交查询
        tag_clicked(tag_text: str, tag_data: dict) - 用户点击标签
        session_updated(stats: dict) - 会话更新
    """
    
    query_submitted = pyqtSignal(str)
    tag_clicked = pyqtSignal(str, dict)
    session_updated = pyqtSignal(dict)
    
    def __init__(self, navigation_engine=None, parent=None):
        super().__init__(parent)
        
        self.navigation_engine = navigation_engine
        self._web_view = None
        self._tag_bridge = None
        
        # 资源路径
        self._resources_dir = Path(__file__).parent / "resources"
        
        self._build_ui()
        
        if WEBENGINE_AVAILABLE:
            self._setup_web_channel()
    
    def _build_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ── 顶部栏 ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background:#1a1a1a; border-bottom:1px solid #333;")
        header.setFixedHeight(50)
        
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 8, 16, 8)
        h_layout.setSpacing(12)
        
        # 返回按钮
        self.back_btn = QPushButton("← 返回")
        self.back_btn.setObjectName("BackButton")
        self.back_btn.setFixedWidth(70)
        self.back_btn.clicked.connect(self._on_back_clicked)
        self.back_btn.setEnabled(False)
        h_layout.addWidget(self.back_btn)
        
        # 面包屑区域
        self.breadcrumb_lbl = QLabel("学习世界")
        self.breadcrumb_lbl.setStyleSheet("color:#888; font-size:13px;")
        h_layout.addWidget(self.breadcrumb_lbl, 1)
        
        # 新建按钮
        self.new_btn = QPushButton("新会话")
        self.new_btn.setObjectName("NewSessionButton")
        self.new_btn.setFixedWidth(70)
        self.new_btn.clicked.connect(self._on_new_session)
        h_layout.addWidget(self.new_btn)
        
        layout.addWidget(header)
        
        # ── WebView 或回退 ──────────────────────────────────────────
        if WEBENGINE_AVAILABLE:
            self._setup_web_view()
        else:
            self._setup_fallback_ui()
        
        # ── 底部输入区 ──────────────────────────────────────────────
        input_area = QWidget()
        input_area.setObjectName("InputArea")
        input_area.setStyleSheet("background:#1a1a1a; border-top:1px solid #333;")
        input_area.setFixedHeight(60)
        
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(16, 10, 16, 10)
        input_layout.setSpacing(12)
        
        self.query_input = QLineEdit()
        self.query_input.setObjectName("QueryInput")
        self.query_input.setPlaceholderText("输入你想探索的知识...")
        self.query_input.setStyleSheet("""
            QLineEdit {
                background:#252525;
                border:1px solid #444;
                border-radius:8px;
                padding:8px 12px;
                color:#e0e0e0;
                font-size:14px;
            }
            QLineEdit:focus {
                border:1px solid #6366f1;
            }
            QLineEdit::placeholder {
                color:#666;
            }
        """)
        self.query_input.returnPressed.connect(self._on_query_submitted)
        input_layout.addWidget(self.query_input, 1)
        
        self.search_btn = QPushButton("探索")
        self.search_btn.setObjectName("SearchButton")
        self.search_btn.setFixedWidth(70)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background:#6366f1;
                color:white;
                border:none;
                border-radius:8px;
                padding:8px 16px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#818cf8;
            }
        """)
        self.search_btn.clicked.connect(self._on_query_submitted)
        input_layout.addWidget(self.search_btn)
        
        layout.addWidget(input_area)
    
    def _setup_web_view(self):
        """设置 WebView"""
        self._web_view = QWebEngineView()
        
        # 设置
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        
        # 加载初始页面
        index_path = self._resources_dir / "index.html"
        if index_path.exists():
            self._web_view.setUrl(QUrl.fromLocalFile(str(index_path.absolute())))
        
        self.layout().insertWidget(1, self._web_view, 1)
    
    def _setup_web_channel(self):
        """设置 JS-Python 通信桥"""
        if not self._web_view:
            return
        
        channel = QWebChannel(self._web_view.page())
        self._tag_bridge = TagClickBridge(self)
        channel.registerObject("bridge", self._tag_bridge)
        self._web_view.page().setWebChannel(channel)
    
    def _setup_fallback_ui(self):
        """设置回退 UI（无 WebEngine 时）"""
        fallback = QScrollArea()
        fallback.setWidgetResizable(True)
        fallback.setStyleSheet("background:#0d0d0d;")
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(16)
        
        # 欢迎消息
        welcome = QLabel("""
            <h2 style='color:#c0c0ff;'>🌌 欢迎来到学习世界</h2>
            <p style='color:#888; font-size:14px; line-height:1.8;'>
                在这里，知识不再是孤立的答案，而是一张可以无限探索的地图。<br>
                输入任何你想了解的主题，开始你的知识探索之旅。
            </p>
            <p style='color:#666; font-size:13px; margin-top:20px;'>
                💡 提示：每个回答都带有可点击的知识标签，点击即可深入探索。
            </p>
        """)
        welcome.setTextFormat(Qt.TextFormat.RichText)
        welcome.setWordWrap(True)
        container_layout.addWidget(welcome)
        
        container_layout.addStretch()
        
        fallback.setWidget(container)
        self.layout().insertWidget(1, fallback, 1)
        
        self._fallback_container = container
        self._fallback_layout = container_layout
    
    def _on_query_submitted(self):
        """处理查询提交"""
        query = self.query_input.text().strip()
        if not query:
            return
        
        self.query_input.clear()
        self.query_submitted.emit(query)
        
        # 如果有导航引擎，开始新会话
        if self.navigation_engine:
            self.navigation_engine.start_new_session(query)
            self._update_breadcrumbs()
    
    def _on_back_clicked(self):
        """处理返回按钮"""
        if self.navigation_engine and self.navigation_engine.can_go_back():
            # 发出返回信号
            self.back_btn.setEnabled(False)
    
    def _on_new_session(self):
        """新建会话"""
        self.clear_content()
        self.query_input.setFocus()
    
    def _update_breadcrumbs(self):
        """更新面包屑"""
        if self.navigation_engine:
            breadcrumbs = self.navigation_engine.get_breadcrumbs()
            if breadcrumbs:
                path = " → ".join(breadcrumbs[-3:])  # 显示最近3级
                self.breadcrumb_lbl.setText(path)
            
            self.back_btn.setEnabled(self.navigation_engine.can_go_back())
    
    # ── 公开接口 ──────────────────────────────────────────────────────
    
    def display_response(self, response_data: dict):
        """
        显示学习响应
        
        Args:
            response_data: 包含 answer, tags, sources 等字段的字典
        """
        if self._web_view and WEBENGINE_AVAILABLE:
            self._display_in_webview(response_data)
        else:
            self._display_in_fallback(response_data)
        
        self._update_breadcrumbs()
    
    def _display_in_webview(self, data: dict):
        """在 WebView 中显示"""
        if not self._web_view:
            return
        
        html = self._render_html(data)
        self._web_view.setHtml(html)
    
    def _display_in_fallback(self, data: dict):
        """在回退 UI 中显示"""
        # 清除旧内容
        while self._fallback_layout.count() > 1:
            item = self._fallback_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 渲染回答
        answer_lbl = QLabel(data.get("answer", ""))
        answer_lbl.setTextFormat(Qt.TextFormat.RichText)
        answer_lbl.setWordWrap(True)
        answer_lbl.setStyleSheet("""
            QLabel {
                color:#e0e0e0;
                font-size:14px;
                line-height:1.8;
                padding:10px;
            }
        """)
        self._fallback_layout.addWidget(answer_lbl)
        
        # 渲染标签
        tags = data.get("tags", [])
        if tags:
            tags_lbl = QLabel("<b style='color:#888;'>🔍 深度探索：</b>")
            self._fallback_layout.addWidget(tags_lbl)
            
            tags_widget = QWidget()
            tags_layout = QHBoxLayout(tags_widget)
            tags_layout.setSpacing(8)
            
            for tag in tags[:8]:
                tag_btn = QPushButton(tag.get("text", ""))
                tag_btn.setStyleSheet("""
                    QPushButton {
                        background:#252525;
                        border:1px solid #444;
                        border-radius:15px;
                        padding:6px 14px;
                        color:#a0a0ff;
                        font-size:12px;
                    }
                    QPushButton:hover {
                        background:#333;
                        border-color:#6366f1;
                    }
                """)
                tag_btn.clicked.connect(
                    lambda checked, t=tag: self.tag_clicked.emit(t.get("text", ""), t)
                )
                tags_layout.addWidget(tag_btn)
            
            tags_layout.addStretch()
            self._fallback_layout.addWidget(tags_widget)
        
        self._fallback_layout.addStretch()
    
    def _render_html(self, data: dict) -> str:
        """渲染 HTML"""
        answer = data.get("answer", "")
        tags = data.get("tags", [])
        sources = data.get("sources", [])
        suggested = data.get("suggested_next", [])
        
        html_content = self._markdown_to_html(answer)
        
        # 标签 HTML
        tags_html = ""
        for tag in tags[:8]:
            icon = self._get_icon_for_type(tag.get("type", "unknown"))
            tag_json = json.dumps(tag, ensure_ascii=False).replace("'", "\\'")
            tags_html += f'<button class="tag-btn" data-tag="{tag_json}"><span class="tag-icon">{icon}</span><span class="tag-text">{tag.get("text", "")}</span></button>'
        
        # 来源 HTML
        sources_html = ""
        for src in sources[:3]:
            url = src.get('url', '#')
            title = src.get('title', '')
            sources_html += f'<a href="{url}" target="_blank" class="source-link">{title}</a>'
        
        # 建议问题 HTML
        suggested_html = ""
        for s in suggested[:3]:
            suggested_html += f'<button class="suggest-btn">{s}</button>'
        
        # 构建完整 HTML
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background:#0d0d0d; color:#e0e0e0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:15px; line-height:1.8; padding:24px; }
        .content { max-width:800px; margin:0 auto; }
        .answer { background:#161616; border-radius:12px; padding:24px; margin-bottom:20px; }
        .answer h1 { color:#c0c0ff; font-size:1.5em; margin-bottom:16px; }
        .answer h2 { color:#a0a0ff; font-size:1.2em; margin:20px 0 10px; }
        .answer p { margin:12px 0; }
        .answer code { background:#252525; padding:2px 6px; border-radius:4px; font-family:Consolas,monospace; color:#a0a0ff; }
        .answer pre { background:#1a1a1a; padding:16px; border-radius:8px; overflow-x:auto; margin:16px 0; }
        .answer pre code { background:none; padding:0; }
        .tags-section { margin:24px 0; }
        .section-title { color:#888; font-size:13px; margin-bottom:12px; }
        .tags-container { display:flex; flex-wrap:wrap; gap:10px; }
        .tag-btn { background:#1e1e2e; border:1px solid #333; border-radius:20px; padding:8px 16px; color:#a0a0ff; cursor:pointer; transition:all 0.2s; font-size:13px; }
        .tag-btn:hover { background:#2a2a4a; border-color:#6366f1; transform:translateY(-2px); }
        .tag-icon { margin-right:6px; }
        .sources-section { margin:20px 0; padding:16px; background:#161616; border-radius:8px; }
        .source-link { color:#6366f1; text-decoration:none; margin-right:16px; }
        .source-link:hover { text-decoration:underline; }
        .suggested-section { margin:20px 0; }
        .suggest-btn { display:block; width:100%; text-align:left; background:#1a1a1a; border:1px solid #333; border-radius:8px; padding:12px 16px; color:#c0c0ff; cursor:pointer; margin-bottom:8px; transition:all 0.2s; }
        .suggest-btn:hover { background:#252525; border-color:#6366f1; }
    </style>
</head>
<body>
    <div class="content">
        <div class="answer">
""" + html_content + """
        </div>
        <div class="tags-section">
            <div class="section-title">🔍 深度探索</div>
            <div class="tags-container">
""" + tags_html + """
            </div>
        </div>
"""
        
        if sources:
            html += """
        <div class="sources-section">
            <div class="section-title">📚 参考资料</div>
""" + sources_html + """
        </div>
"""
        
        if suggested:
            html += """
        <div class="suggested-section">
            <div class="section-title">💡 延伸问题</div>
""" + suggested_html + """
        </div>
"""
        
        html += """
    </div>
    <script>
        document.querySelectorAll('.tag-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var tagData = btn.getAttribute('data-tag');
                if (window.bridge && window.bridge.onTagClick) {
                    var tag = JSON.parse(tagData);
                    window.bridge.onTagClick(tag.text, tagData);
                }
            });
        });
        document.querySelectorAll('.suggest-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (window.bridge && window.bridge.onSuggestionClick) {
                    window.bridge.onSuggestionClick(btn.textContent);
                }
            });
        });
    </script>
</body>
</html>
"""
        return html
    
    def _markdown_to_html(self, text: str) -> str:
        """简单的 Markdown 转 HTML"""
        import re
        
        # 转义 HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 代码块
        text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)
        
        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # 标题
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # 粗体和斜体
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        
        # 列表
        text = re.sub(r'^\s*[-*]\s+(.+)', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text)
        
        # 链接
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        
        # 换行
        text = text.replace('\n\n', '</p><p>')
        text = f'<p>{text}</p>'
        
        # 清理空段落
        text = text.replace('<p></p>', '')
        text = text.replace('<p><br>', '<p>')
        
        return text
    
    def _get_icon_for_type(self, tag_type: str) -> str:
        """获取类型图标"""
        icons = {
            "person": "👤",
            "event": "📅",
            "tech": "🔧",
            "place": "📍",
            "period": "⏰",
            "org": "🏛️",
            "work": "📖",
            "concept": "💡",
            "unknown": "📚",
        }
        return icons.get(tag_type, "📚")
    
    def clear_content(self):
        """清除内容"""
        if self._web_view and WEBENGINE_AVAILABLE:
            index_path = self._resources_dir / "index.html"
            if index_path.exists():
                self._web_view.setUrl(QUrl.fromLocalFile(str(index_path.absolute())))
        else:
            self._setup_fallback_ui()
        
        self.breadcrumb_lbl.setText("学习世界")
        self.back_btn.setEnabled(False)
    
    def set_navigation_engine(self, engine):
        """设置导航引擎"""
        self.navigation_engine = engine
