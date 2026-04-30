"""
AI 增强搜索研究面板 - 可信信息代理
支持模式化卡片、双栏对比Modal、文件下载

核心特性：
- 意图自适应：根据查询类型显示不同卡片（下载/代码/新闻/摘要）
- 可信度验证：原文切片 + 语义校验
- 文件下载：点击直接下载到项目目录
- 双栏对比：左侧AI摘要，右侧原文切片
"""

import asyncio
import os
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextBrowser, QLabel, QComboBox, QProgressBar, QMenu, QApplication,
    QFrame, QScrollArea, QCheckBox, QSplitter, QDialog, QDialogButtonBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QToolButton, QGraphicsOpacityEffect, QScrollArea, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QAction, QTextCursor, QIcon, QTextCharFormat, QColor, QPalette, QPainter, QPen

try:
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtCore import QUrl
except ImportError:
    QDesktopServices = None
    QUrl = None

# ── Markdown 渲染器 ─────────────────────────────────────────────────────────

class MarkdownHighlighter:
    """简单的 Markdown 高亮"""
    
    @staticmethod
    def to_html(text: str) -> str:
        """将 Markdown 转换为 HTML"""
        import re
        
        # 转义 HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # 代码块
        text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code class="\1">\2</code></pre>', text, flags=re.DOTALL)
        
        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # 标题
        for i in range(6, 0, -1):
            text = re.sub(rf'^#{i}\s+(.+)$', rf'<h{i}>\1</h{i}>', text, flags=re.MULTILINE)
        
        # 粗体
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        
        # 斜体
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
        
        # 链接
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#58a6ff;text-decoration:none;">\1</a>', text)
        
        # 列表
        text = re.sub(r'^[\*\-]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^(\d+)\.\s+(.+)$', r'<li>\1. \2</li>', text, flags=re.MULTILINE)
        
        # 引用
        text = re.sub(r'^>\s+(.+)$', r'<blockquote style="border-left:3px solid #58a6ff;margin:8px 0;padding-left:12px;color:#8b949e;">\1</blockquote>', text, flags=re.MULTILINE)
        
        # 分隔线
        text = re.sub(r'^---+$', '<hr style="border:none;border-top:1px solid #30363d;margin:16px 0;">', text, flags=re.MULTILINE)
        
        # 段落
        paragraphs = text.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<') and not p.endswith('>'):
                processed.append(f'<p style="margin:8px 0;line-height:1.6;">{p}</p>')
            elif p:
                processed.append(p)
        
        return '<br>'.join(processed)


# ── 下载卡片 ─────────────────────────────────────────────────────────────────

class DownloadCard(QFrame):
    """文件下载卡片 - 用于文件下载类查询"""
    
    def __init__(self, result, download_manager, parent=None):
        super().__init__(parent)
        self.result = result
        self.download_manager = download_manager
        self.download_task = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        
        # 根据文件类型设置颜色
        colors = {
            "pdf": "#e53935",
            "doc": "#1e88e5",
            "docx": "#1e88e5",
            "xlsx": "#43a047",
            "xls": "#43a047",
            "ppt": "#fb8c00",
            "pptx": "#fb8c00",
            "zip": "#8e24aa",
            "file": "#757575",
        }
        border_color = colors.get(self.result.file_type, "#757575")
        
        self.setStyleSheet(f"""
            DownloadCard {{
                background: #21262d;
                border: 1px solid #30363d;
                border-left: 4px solid {border_color};
                border-radius: 8px;
                padding: 12px;
                margin: 4px 0;
            }}
            DownloadCard:hover {{
                border-color: {border_color};
                background: #262c36;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # 文件图标 + 标题
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(self.download_manager.get_file_icon(self.result.file_type))
        icon_label.setFont(QFont("", 28))
        header_layout.addWidget(icon_label)
        
        title_layout = QVBoxLayout()
        title_label = QLabel(f'<a href="{self.result.url}" style="color:#fff;text-decoration:none;font-weight:600;">{self.result.title}</a>')
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label)
        
        # 文件信息
        file_info = f"{self.result.file_type.upper()}"
        if self.result.file_size:
            file_info += f" · {self.result.file_size}"
        info_label = QLabel(file_info)
        info_label.setStyleSheet("color:#8b949e;font-size:12px;")
        title_layout.addWidget(info_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 来源
        source_label = QLabel(f"来源: {self.result.source}")
        source_label.setStyleSheet("color:#6e7681;font-size:11px;")
        layout.addWidget(source_label)
        
        # 下载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #30363d;
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar::chunk {
                background: #58a6ff;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#8b949e;font-size:11px;")
        layout.addWidget(self.status_label)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.download_btn = QPushButton("📥 下载")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: #238636;
                border: none;
                border-radius: 4px;
                color: white;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2ea043;
            }
            QPushButton:disabled {
                background: #30363d;
                color: #6e7681;
            }
        """)
        self.download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self.download_btn)
        
        open_dir_btn = QPushButton("📂 打开目录")
        open_dir_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #8b949e;
                padding: 6px 12px;
            }
            QPushButton:hover {
                border-color: #58a6ff;
                color: #58a6ff;
            }
        """)
        open_dir_btn.clicked.connect(self._open_download_dir)
        btn_layout.addWidget(open_dir_btn)
        
        layout.addLayout(btn_layout)
    
    def _start_download(self):
        """开始下载"""
        if not self.download_manager:
            self.status_label.setText("❌ 下载管理器未初始化")
            return
        
        self.download_btn.setEnabled(False)
        self.download_btn.setText("下载中...")
        self.progress_bar.setVisible(True)
        
        # 使用新事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            task = loop.run_until_complete(
                self.download_manager.download(
                    url=self.result.url,
                    source=self.result.source,
                )
            )
            
            # 更新进度
            self.progress_bar.setValue(int(task.progress))
            self.status_label.setText(f"{self.download_manager.format_speed(task.speed)}")
            
            if task.status.value == "completed":
                self.download_btn.setText("✅ 完成")
                self.status_label.setText(f"已保存: {task.save_path.name}")
            else:
                self.download_btn.setText("📥 重试")
                self.download_btn.setEnabled(True)
                
        except Exception as e:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("📥 重试")
            self.status_label.setText(f"❌ {str(e)}")
        finally:
            loop.close()
    
    def _open_download_dir(self):
        """打开下载目录"""
        if self.download_manager:
            self.download_manager.open_download_dir()


# ── 代码预览卡片 ─────────────────────────────────────────────────────────────

class CodePreviewCard(QFrame):
    """代码预览卡片 - 用于技术文档类查询"""
    
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            CodePreviewCard {
                background: #21262d;
                border: 1px solid #30363d;
                border-left: 4px solid #f0883e;
                border-radius: 8px;
                padding: 12px;
                margin: 4px 0;
            }
            CodePreviewCard:hover {
                border-color: #f0883e;
                background: #262c36;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # 标题行
        header_layout = QHBoxLayout()
        
        lang_badge = QLabel("💻 代码")
        lang_badge.setStyleSheet("""
            background: #f0883e;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        """)
        header_layout.addWidget(lang_badge)
        
        title_label = QLabel(f'<a href="{self.result.url}" style="color:#fff;text-decoration:none;font-weight:600;">{self.result.title}</a>')
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # 来源
        source_label = QLabel(f"来源: {self.result.source}")
        source_label.setStyleSheet("color:#6e7681;font-size:11px;")
        layout.addWidget(source_label)
        
        # 代码预览
        code_preview = self._extract_code_preview()
        if code_preview:
            code_label = QLabel(f'<pre style="background:#161b22;padding:12px;border-radius:6px;font-family:Consolas,monospace;font-size:12px;color:#c9d1d9;overflow:auto;">{code_preview}</pre>')
            code_label.setWordWrap(False)
            layout.addWidget(code_label)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        copy_btn = QPushButton("📋 复制链接")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #8b949e;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #58a6ff;
                color: #58a6ff;
            }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.result.url))
        btn_layout.addWidget(copy_btn)
        
        layout.addLayout(btn_layout)
    
    def _extract_code_preview(self) -> str:
        """从snippet提取代码预览"""
        import re
        code_patterns = [
            r'`([^`]+)`',
            r'```(\w*)\n(.*?)```',
        ]
        
        snippets = []
        for pattern in code_patterns:
            matches = re.findall(pattern, self.result.snippet, re.DOTALL)
            snippets.extend(matches[:2])
        
        if snippets:
            return snippets[0][:500] if isinstance(snippets[0], str) else snippets[0][1][:500]
        return ""


# ── 新闻时间线卡片 ───────────────────────────────────────────────────────────

class NewsTimelineCard(QFrame):
    """新闻时间线卡片 - 用于新闻资讯类查询"""
    
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("NewsTimelineCard { background: transparent; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QLabel("📰 时间线视图")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("color:#c9d1d9;padding:8px 0;")
        layout.addWidget(header)
        
        for i, result in enumerate(self.results[:10]):
            item = self._create_timeline_item(result, i)
            layout.addWidget(item)
        
        layout.addStretch()
    
    def _create_timeline_item(self, result, index: int) -> QFrame:
        """创建时间线项"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background: #21262d;
                border-radius: 8px;
                padding: 12px;
                margin: 4px 0;
            }
            QFrame:hover {
                background: #262c36;
            }
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        date_label = QLabel(result.date or "")
        date_label.setStyleSheet("color: #58a6ff;font-size: 11px;font-weight: 600;min-width: 60px;")
        layout.addWidget(date_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("background:#30363d;")
        layout.addWidget(line)
        
        content_layout = QVBoxLayout()
        
        title_label = QLabel(f'<a href="{result.url}" style="color:#fff;text-decoration:none;">{result.title}</a>')
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size:13px;")
        content_layout.addWidget(title_label)
        
        source_label = QLabel(result.source)
        source_label.setStyleSheet("color:#6e7681;font-size:11px;")
        content_layout.addWidget(source_label)
        
        layout.addLayout(content_layout, 1)
        
        if result.trust_score > 0.8:
            badge = QLabel("✓ 多方确认")
            badge.setStyleSheet("background: #238636;color: white;padding: 2px 6px;border-radius: 4px;font-size: 10px;")
            layout.addWidget(badge)
        
        return item


# ── 双栏对比 Modal ───────────────────────────────────────────────────────────

class ComparisonModal(QDialog):
    """
    双栏对比 Modal - 原文切片 vs AI摘要
    
    三层可信度验证：
    1. 摘要约束机制
    2. 原文对比视图
    3. 语义一致性校验
    """
    
    def __init__(self, result, summary: str = "", parent=None):
        super().__init__(parent)
        self.result = result
        self.summary = summary
        self.raw_content = ""
        self._setup_ui()
        self._load_raw_content()
    
    def _setup_ui(self):
        self.setWindowTitle("🔍 可信度验证")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("QDialog { background: #0d1117; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题区
        header_layout = QHBoxLayout()
        
        title = QLabel(f'<b style="color:#fff;font-size:14px;">{self.result.title}</b>')
        title.setWordWrap(True)
        header_layout.addWidget(title, 1)
        
        trust_badge = QLabel()
        trust_score = self.result.trust_score
        if trust_score >= 0.8:
            trust_badge.setText("✅ 高可信")
            trust_badge.setStyleSheet("background:#238636;color:white;padding:4px 8px;border-radius:4px;font-size:12px;")
        elif trust_score >= 0.5:
            trust_badge.setText("⚠️ 中可信")
            trust_badge.setStyleSheet("background:#fb8c00;color:white;padding:4px 8px;border-radius:4px;font-size:12px;")
        else:
            trust_badge.setText("❌ 低可信")
            trust_badge.setStyleSheet("background:#f85149;color:white;padding:4px 8px;border-radius:4px;font-size:12px;")
        header_layout.addWidget(trust_badge)
        
        layout.addLayout(header_layout)
        
        # 语义偏差警告
        if self.result.semantic_distance > 0.7:
            warning = QLabel(f"⚠️ 语义偏差较大（{self.result.semantic_distance:.2f}），摘要可能偏离原文")
            warning.setStyleSheet("background: #fb8c00;color: white;padding: 8px 12px;border-radius: 6px;font-size: 12px;")
            layout.addWidget(warning)
        
        # 双栏视图
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #30363d;width: 2px; }")
        
        left_widget = self._create_summary_panel()
        splitter.addWidget(left_widget)
        
        right_widget = self._create_raw_content_panel()
        splitter.addWidget(right_widget)
        
        splitter.setSizes([450, 450])
        
        layout.addWidget(splitter, 1)
        
        # 底部操作
        footer_layout = QHBoxLayout()
        
        source_label = QLabel(f"来源: <a href='{self.result.url}' style='color:#58a6ff;'>{self.result.url[:50]}...</a>")
        source_label.setOpenExternalLinks(True)
        source_label.setStyleSheet("color:#8b949e;font-size:12px;")
        footer_layout.addWidget(source_label)
        
        footer_layout.addStretch()
        
        wrong_btn = QPushButton("👎 内容有误")
        wrong_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #f85149;
                border-radius: 4px;
                color: #f85149;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #f8514922;
            }
        """)
        wrong_btn.clicked.connect(self._report_error)
        footer_layout.addWidget(wrong_btn)
        
        confirm_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        confirm_btn.accepted.connect(self.accept)
        confirm_btn.button(QDialogButtonBox.StandardButton.Ok).setText("✓ 确认可信")
        confirm_btn.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet("""
            QPushButton {
                background: #238636;
                border: none;
                border-radius: 4px;
                color: white;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2ea043;
            }
        """)
        footer_layout.addWidget(confirm_btn)
        
        layout.addLayout(footer_layout)
    
    def _create_summary_panel(self) -> QWidget:
        """创建摘要面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 8, 0)
        
        header = QLabel("🤖 AI 摘要")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("color:#58a6ff;padding:4px 0;")
        layout.addWidget(header)
        
        hint = QLabel("（仅提取，不生成）")
        hint.setStyleSheet("color:#6e7681;font-size:11px;margin-bottom:8px;")
        layout.addWidget(hint)
        
        text_browser = QTextBrowser()
        text_browser.setPlaceholderText("AI 摘要将显示在这里...")
        
        if self.summary:
            text_browser.setHtml(MarkdownHighlighter.to_html(self.summary))
        elif self.result.snippet:
            text_browser.setText(self.result.snippet)
        
        text_browser.setStyleSheet("""
            QTextBrowser {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 12px;
                color: #c9d1d9;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(text_browser, 1)
        
        # 约束检查
        constraint_frame = QFrame()
        constraint_frame.setStyleSheet("QFrame { background: #21262d;border-radius: 6px;padding: 8px;margin-top: 8px; }")
        constraint_layout = QVBoxLayout(constraint_frame)
        
        constraint_header = QLabel("📋 摘要约束检查")
        constraint_header.setStyleSheet("color:#8b949e;font-size:11px;font-weight:600;")
        constraint_layout.addWidget(constraint_header)
        
        checks = [
            ("🔇 禁用生成指令", self._check_forbidden_words()),
            ("📝 保留否定表述", self._check_negation()),
            ("📏 语义距离", f"{self.result.semantic_distance:.2f} (阈值: 0.7)"),
        ]
        
        for check_name, check_result in checks:
            check_label = QLabel(f"{check_name}: {check_result}")
            check_label.setStyleSheet("color:#8b949e;font-size:11px;")
            constraint_layout.addWidget(check_label)
        
        layout.addWidget(constraint_frame)
        
        return widget
    
    def _create_raw_content_panel(self) -> QWidget:
        """创建原文切片面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 0, 0, 0)
        
        header = QLabel("📄 原文切片")
        header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.setStyleSheet("color:#3fb950;padding:4px 0;")
        layout.addWidget(header)
        
        hint = QLabel("（净化后的原文）")
        hint.setStyleSheet("color:#6e7681;font-size:11px;margin-bottom:8px;")
        layout.addWidget(hint)
        
        self.raw_text_browser = QTextBrowser()
        self.raw_text_browser.setPlaceholderText("正在加载原文...")
        self.raw_text_browser.setStyleSheet("""
            QTextBrowser {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 12px;
                color: #c9d1d9;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.raw_text_browser, 1)
        
        self.loading_label = QLabel("⏳ 加载原文...")
        self.loading_label.setStyleSheet("color:#6e7681;font-size:11px;")
        layout.addWidget(self.loading_label)
        
        return widget
    
    def _check_forbidden_words(self) -> str:
        """检查禁用词汇"""
        forbidden = ["generate", "create", "invent", "编造", "虚构"]
        summary_text = (self.summary or self.result.snippet or "").lower()
        
        found = [w for w in forbidden if w.lower() in summary_text]
        if found:
            return f"⚠️ 发现 {found}"
        return "✅ 无"
    
    def _check_negation(self) -> str:
        """检查否定表述"""
        negations = ["不", "否", "无", "未", "非", "暂", "不支持", "无法", "没有"]
        raw = self.result.raw_content or self.result.snippet or ""
        
        found = [n for n in negations if n in raw]
        if found:
            return f"✅ 保留 {found[:3]}"
        return "⚪ 无否定词"
    
    def _load_raw_content(self):
        """加载原文内容"""
        import httpx
        import re
        
        async def fetch():
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    r = await client.get(self.result.url, headers=headers, follow_redirects=True)
                    r.raise_for_status()
                    
                    content = r.text
                    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<[^>]+>', ' ', content)
                    content = re.sub(r'\s+', ' ', content).strip()
                    
                    self.raw_content = content[:3000]
                    self.result.raw_content = self.raw_content
                    
                    self.raw_text_browser.setText(self.raw_content)
                    self.loading_label.setVisible(False)
                    
            except Exception as e:
                self.loading_label.setText(f"❌ 加载失败: {str(e)}")
        
        asyncio.create_task(fetch())
    
    def _report_error(self):
        """报告错误"""
        QMessageBox.information(self, "反馈", "感谢您的反馈！我们会持续优化摘要质量。")


# ── 标准结果卡片 ─────────────────────────────────────────────────────────────

class ResultCard(QFrame):
    """通用搜索结果卡片"""
    
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            ResultCard {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 12px;
                margin: 4px 0;
            }
            ResultCard:hover {
                border-color: #58a6ff;
                background: #262c36;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel(f'<a href="{self.result.url}" style="color:#58a6ff;text-decoration:none;font-weight:600;">{self.result.title}</a>')
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        layout.addWidget(title_label)
        
        # 来源和时间
        meta_layout = QHBoxLayout()
        source_label = QLabel(f'<span style="color:#8b949e;font-size:11px;">{self.result.source}</span>')
        if self.result.date:
            date_label = QLabel(f'<span style="color:#8b949e;font-size:11px;">{self.result.date}</span>')
            meta_layout.addWidget(date_label)
        meta_layout.addWidget(source_label)
        
        if self.result.trust_score >= 0.8:
            trust_badge = QLabel("✓")
            trust_badge.setStyleSheet("color:#238636;font-size:12px;")
            meta_layout.addWidget(trust_badge)
        
        meta_layout.addStretch()
        layout.addLayout(meta_layout)
        
        # 摘要
        snippet_label = QLabel(self.result.snippet)
        snippet_label.setWordWrap(True)
        snippet_label.setStyleSheet("color:#c9d1d9;line-height:1.5;")
        layout.addWidget(snippet_label)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        copy_btn = QPushButton("📋 复制链接")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #30363d;
                color: #8b949e;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #58a6ff;
                color: #58a6ff;
            }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.result.url))
        btn_layout.addWidget(copy_btn)
        
        layout.addLayout(btn_layout)


# ── 搜索工作线程 ─────────────────────────────────────────────────────────────

class SearchWorker(QThread):
    """异步搜索工作线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, search_tool, query: str, intent: str, num_results: int):
        super().__init__()
        self.search_tool = search_tool
        self.query = query
        self.intent = intent
        self.num_results = num_results
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from .business.search_tool import SearchIntent
            intent_map = {
                "general": SearchIntent.GENERAL,
                "news": SearchIntent.NEWS,
                "technical": SearchIntent.TECHNICAL,
                "academic": SearchIntent.ACADEMIC,
                "policy": SearchIntent.POLICY,
                "product": SearchIntent.PRODUCT,
                "file": SearchIntent.FILE_DOWNLOAD,
                "ambiguous": SearchIntent.AMBIGUOUS,
            }
            intent = intent_map.get(self.intent, SearchIntent.GENERAL)
            
            self.progress.emit("🔍 正在搜索...")
            response = loop.run_until_complete(
                self.search_tool.search_and_summarize(
                    self.query,
                    intent=intent,
                    num_results=self.num_results,
                    verify_trust=True,
                )
            )
            loop.close()
            
            self.finished.emit(response)
            
        except Exception as e:
            self.error.emit(str(e))


# ── 研究面板主类 ─────────────────────────────────────────────────────────────

class ResearchPanel(QWidget):
    """
    AI 增强搜索研究面板 - 可信信息代理
    
    特性：
    - 意图自适应：根据查询类型显示不同卡片
    - 模式化呈现：下载卡片、代码预览、新闻时间线、摘要卡片
    - 可信度验证：双栏对比Modal
    - 文件下载：直接下载到项目目录
    - AI 总结 + 多源聚合
    """
    
    def __init__(self, search_tool=None, download_manager=None, parent=None):
        super().__init__(parent)
        
        self.search_tool = search_tool
        self.download_manager = download_manager
        self._current_response: Optional[object] = None
        self._search_worker: Optional[SearchWorker] = None
        
        self._setup_ui()
    
    def set_search_tool(self, search_tool):
        self.search_tool = search_tool
    
    def set_download_manager(self, download_manager):
        self.download_manager = download_manager
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # 标题区
        header_layout = QHBoxLayout()
        title_label = QLabel("🔍 AI 研究助手")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.engine_label = QLabel("引擎: --")
        self.engine_label.setStyleSheet("color:#8b949e;font-size:11px;")
        header_layout.addWidget(self.engine_label)
        
        download_dir_btn = QToolButton()
        download_dir_btn.setText("📂")
        download_dir_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                border-color: #58a6ff;
            }
        """)
        download_dir_btn.clicked.connect(self._open_download_dir)
        download_dir_btn.setToolTip("打开下载目录")
        header_layout.addWidget(download_dir_btn)
        
        main_layout.addLayout(header_layout)
        
        # 搜索区
        search_layout = QVBoxLayout()
        search_layout.setSpacing(8)
        
        search_input_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入你想了解的话题...")
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 12px;
                color: #c9d1d9;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #58a6ff;
            }
            QLineEdit::placeholder {
                color: #6e7681;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_input_layout.addWidget(self.search_input)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.setMinimumSize(70, 36)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #238636;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #2ea043;
            }
            QPushButton:disabled {
                background: #21262d;
                color: #6e7681;
            }
        """)
        self.search_btn.clicked.connect(self._on_search)
        search_input_layout.addWidget(self.search_btn)
        
        search_layout.addLayout(search_input_layout)
        
        # 选项区
        options_layout = QHBoxLayout()
        
        intent_label = QLabel("意图:")
        intent_label.setStyleSheet("color:#8b949e;")
        options_layout.addWidget(intent_label)
        
        self.intent_combo = QComboBox()
        self.intent_combo.addItems([
            "自动识别", "文件下载", "技术文档", "学术研究", "新闻资讯", "政策法规", "产品评测"
        ])
        self.intent_combo.setCurrentIndex(0)
        self.intent_combo.setStyleSheet("""
            QComboBox {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                color: #c9d1d9;
            }
        """)
        options_layout.addWidget(self.intent_combo)
        
        options_layout.addStretch()
        
        self.cache_checkbox = QCheckBox("使用缓存")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.setStyleSheet("color:#8b949e;")
        options_layout.addWidget(self.cache_checkbox)
        
        clear_cache_btn = QPushButton("清缓存")
        clear_cache_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                color: #8b949e;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #f85149;
                color: #f85149;
            }
        """)
        clear_cache_btn.clicked.connect(self._clear_cache)
        options_layout.addWidget(clear_cache_btn)
        
        search_layout.addLayout(options_layout)
        
        main_layout.addLayout(search_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #21262d;
                border-radius: 4px;
                height: 4px;
            }
            QProgressBar::chunk {
                background: #58a6ff;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#8b949e;font-size:12px;")
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)
        
        # 结果区
        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_area.setStyleSheet("QScrollArea { border: none;background: transparent; }")
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_layout.setSpacing(8)
        
        self.results_area.setWidget(self.results_widget)
        main_layout.addWidget(self.results_area, 1)
        
        self._show_initial_tip()
    
    def _show_initial_tip(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        tip_label = QLabel(
            "<div style='text-align:center;color:#6e7681;padding:40px 20px;'>"
            "<div style='font-size:48px;margin-bottom:16px;'>🔍</div>"
            "<div style='font-size:14px;line-height:1.8;'>"
            "输入问题开始研究之旅<br><br>"
            "<span style='font-size:12px;'>"
            "💡 智能识别搜索意图<br>"
            "📥 支持文件直接下载<br>"
            "🔍 可信度验证确保质量"
            "</span>"
            "</div>"
            "</div>"
        )
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_layout.addWidget(tip_label)
    
    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        
        if not self.search_tool:
            self._show_error("搜索工具未初始化")
            return
        
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("⏳ 正在搜索...")
        
        intent_map = {
            0: "general",
            1: "file",
            2: "technical",
            3: "academic",
            4: "news",
            5: "policy",
            6: "product",
        }
        intent = intent_map.get(self.intent_combo.currentIndex(), "general")
        
        self._search_worker = SearchWorker(self.search_tool, query, intent, 10)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.progress.connect(self._on_search_progress)
        self._search_worker.start()
    
    def _on_search_progress(self, message: str):
        self.status_label.setText(message)
    
    def _on_search_finished(self, response):
        self._current_response = response
        
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if response.engine_used:
            engine_names = {
                "serper": "🌐 Serper",
                "brave": "🦅 Brave",
                "duckduckgo": "🦆 DuckDuckGo",
                "cn_aggregate": "🇨🇳 中文聚合",
            }
            self.engine_label.setText(f"引擎: {engine_names.get(response.engine_used, response.engine_used)}")
        
        if response.cached:
            self.status_label.setText(f"📋 来自缓存 ({datetime.now().strftime('%H:%M')})")
        else:
            self.status_label.setText(f"✅ 找到 {len(response.results)} 条结果")
        
        self._render_results(response)
    
    def _on_search_error(self, error: str):
        self._show_error(f"搜索失败: {error}")
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.progress_bar.setVisible(False)
    
    def _render_results(self, response):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # AI总结
        if response.summary:
            summary_card = QFrame()
            summary_card.setStyleSheet("""
                QFrame {
                    background: linear-gradient(135deg, #1a2332 0%, #21262d 100%);
                    border: 1px solid #30363d;
                    border-left: 3px solid #58a6ff;
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 12px;
                }
            """)
            summary_layout = QVBoxLayout(summary_card)
            
            summary_header = QLabel("📝 AI 总结")
            summary_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            summary_header.setStyleSheet("color:#58a6ff;")
            summary_layout.addWidget(summary_header)
            
            summary_content = QLabel(MarkdownHighlighter.to_html(response.summary))
            summary_content.setWordWrap(True)
            summary_content.setStyleSheet("color:#c9d1d9;line-height:1.8;")
            summary_layout.addWidget(summary_content)
            
            self.results_layout.addWidget(summary_card)
        
        # 根据意图选择卡片类型
        intent = response.intent
        
        if intent.value == "file" or any(r.is_downloadable for r in response.results):
            self._render_download_cards(response)
        elif intent.value == "news":
            self._render_news_timeline(response)
        elif intent.value == "technical":
            self._render_code_cards(response)
        else:
            self._render_standard_cards(response)
        
        # 可信度警告
        if response.verification and response.verification.warnings:
            warning_card = QFrame()
            warning_card.setStyleSheet("""
                QFrame {
                    background: #fb8c0011;
                    border: 1px solid #fb8c00;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 8px;
                }
            """)
            warning_layout = QVBoxLayout(warning_card)
            
            warning_header = QLabel("⚠️ 可信度提示")
            warning_header.setStyleSheet("color:#fb8c00;font-weight:600;")
            warning_layout.addWidget(warning_header)
            
            for warning in response.verification.warnings[:3]:
                w_label = QLabel(warning)
                w_label.setStyleSheet("color:#c9d1d9;font-size:12px;")
                warning_layout.addWidget(w_label)
            
            self.results_layout.addWidget(warning_card)
        
        # 引用区
        if response.sources:
            self.results_layout.addSpacing(16)
            refs_header = QLabel("📎 参考来源")
            refs_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            refs_header.setStyleSheet("color:#8b949e;")
            self.results_layout.addWidget(refs_header)
            
            refs_text = "<br>".join([
                f"[{i+1}] <a href='{url}' style='color:#58a6ff;'>{url[:60]}...</a>"
                if len(url) > 60 else f"[{i+1}] <a href='{url}' style='color:#58a6ff;'>{url}</a>"
                for i, url in enumerate(response.sources[:5])
            ])
            refs_label = QLabel(f"<div style='font-size:11px;line-height:1.6;'>{refs_text}</div>")
            refs_label.setOpenExternalLinks(True)
            refs_label.setWordWrap(True)
            refs_label.setStyleSheet("color:#6e7681;")
            self.results_layout.addWidget(refs_label)
    
    def _render_download_cards(self, response):
        results_header = QLabel("📥 可下载文件")
        results_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        results_header.setStyleSheet("color:#3fb950;margin-top:8px;")
        self.results_layout.addWidget(results_header)
        
        for result in response.results:
            if result.is_downloadable or response.intent.value == "file":
                card = DownloadCard(result, self.download_manager)
                self.results_layout.addWidget(card)
    
    def _render_news_timeline(self, response):
        timeline = NewsTimelineCard(response.results)
        self.results_layout.addWidget(timeline)
    
    def _render_code_cards(self, response):
        results_header = QLabel("💻 代码资源")
        results_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        results_header.setStyleSheet("color:#f0883e;margin-top:8px;")
        self.results_layout.addWidget(results_header)
        
        for result in response.results:
            card = CodePreviewCard(result)
            self.results_layout.addWidget(card)
    
    def _render_standard_cards(self, response):
        results_header = QLabel(f"📚 相关结果 ({len(response.results)})")
        results_header.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        results_header.setStyleSheet("color:#8b949e;margin-top:8px;")
        self.results_layout.addWidget(results_header)
        
        for result in response.results:
            card = ResultCard(result)
            self.results_layout.addWidget(card)
    
    def _open_download_dir(self):
        if self.download_manager:
            self.download_manager.open_download_dir()
    
    def _show_error(self, message: str):
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color:#f85149;font-size:12px;")
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color:#8b949e;font-size:12px;"))
    
    def _clear_cache(self):
        if self.search_tool:
            self.search_tool.clear_cache()
            self.status_label.setText("🗑️ 缓存已清空")
            self.status_label.setStyleSheet("color:#58a6ff;font-size:12px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color:#8b949e;font-size:12px;"))
    
    def get_all_content(self) -> str:
        if not self._current_response:
            return ""
        
        parts = []
        if self._current_response.summary:
            parts.append(f"## AI 总结\n\n{self._current_response.summary}")
        
        if self._current_response.results:
            parts.append("\n## 搜索结果\n")
            for i, r in enumerate(self._current_response.results):
                parts.append(f"{i+1}. **{r.title}**\n   {r.snippet}\n   来源: {r.source}\n")
        
        if self._current_response.sources:
            parts.append("\n## 参考来源\n")
            for i, url in enumerate(self._current_response.sources):
                parts.append(f"{i+1}. {url}\n")
        
        return "\n".join(parts)


# ── 导出 ─────────────────────────────────────────────────────────────────────

__all__ = [
    "ResearchPanel",
    "SearchWorker",
    "ResultCard",
    "DownloadCard",
    "CodePreviewCard",
    "NewsTimelineCard",
    "ComparisonModal",
    "MarkdownHighlighter",
]
