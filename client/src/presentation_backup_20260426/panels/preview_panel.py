"""
ui/preview_panel.py - Office 文档实时预览与编辑面板

借鉴 AionUi Preview Panel 的多标签页 + 分屏编辑设计
支持 Markdown / PDF / Word / Excel / PowerPoint / 图片 / 代码的实时预览和编辑
"""

import os
import uuid
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabBar, QStackedWidget,
    QTextEdit, QLabel, QPushButton, QToolButton, QMenu, QLineEdit,
    QFileDialog, QMessageBox, QScrollArea, QSizePolicy, QFrame
)
from PyQt6.QtCore import (
    Qt, QUrl, QSize, QTimer, pyqtSignal, QEvent, QSettings
)
from PyQt6.QtGui import (
    QAction, QIcon, QTextCursor, QPalette, QColor, QFont
)

# WebEngine 可选导入
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None
    QWebEngineSettings = None
    QWebEnginePage = None

from .business.office_preview import (
    PreviewSystem, get_preview_system,
    TabManager, get_tab_manager, FileWatcher, get_file_watcher,
    PreviewFileType, PreviewTab, EditorMode, TabState, FileInfo,
    PreviewConfig, RenderResult, format_file_size
)


class CodeEditor(QTextEdit):
    """代码编辑器组件（用于 Markdown/代码编辑）"""

    def __init__(self, language: str = 'markdown', parent=None):
        super().__init__(parent)
        self.language = language
        self._setup_editor()

    def _setup_editor(self):
        """设置编辑器样式"""
        self.setFont(QFont('Cascadia Code', 13))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 8px;
                selection-background-color: #264f78;
            }
        """)
        # 行号支持可以通过覆盖 paintEvent 实现，这里简化处理


class MarkdownEditor(QWidget):
    """
    Markdown 编辑器 - 分屏编辑 + 实时预览

    支持三种模式：
    - 编辑预览分屏 (split)
    - 仅编辑 (edit)
    - 仅预览 (preview)
    """

    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_system = get_preview_system()
        self._content = ''
        self._mode = 'split'  # split / edit / preview
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QFrame()
        toolbar.setStyleSheet("background: #252525; border-bottom: 1px solid #333;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        self.mode_buttons = {}
        for mode, label in [('split', '📺 分屏'), ('edit', '✏️ 编辑'), ('preview', '👁️ 预览')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(mode == 'split')
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: #888; border: none;
                              padding: 6px 12px; border-radius: 4px; }
                QPushButton:checked { background: #2563eb; color: #fff; }
                QPushButton:hover { background: #333; }
            """)
            btn.clicked.connect(lambda _, m=mode: self.set_mode(m))
            toolbar_layout.addWidget(btn)
            self.mode_buttons[mode] = btn

        toolbar_layout.addStretch()
        self.char_count_label = QLabel("0 字符 · 0 行")
        self.char_count_label.setStyleSheet("color: #666; font-size: 12px; padding: 0 8px;")
        toolbar_layout.addWidget(self.char_count_label)

        layout.addWidget(toolbar)

        # 编辑器和预览区
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = CodeEditor()
        self.editor.textChanged.connect(self._on_text_changed)

        self.preview_view = QWebEngineView()
        self.preview_view.setHtml(self._get_empty_html())

        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview_view)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        layout.addWidget(self.splitter)

    def set_content(self, content: str):
        """设置内容"""
        self._content = content
        self.editor.setPlainText(content)
        self._update_preview()

    def get_content(self) -> str:
        """获取内容"""
        return self.editor.toPlainText()

    def set_mode(self, mode: str):
        """设置编辑模式"""
        self._mode = mode

        # 更新按钮状态
        for m, btn in self.mode_buttons.items():
            btn.setChecked(m == mode)

        # 更新布局
        if mode == 'split':
            self.splitter.widget(0).show()
            self.splitter.widget(1).show()
            self.splitter.setSizes([self.width() // 2, self.width() // 2])
        elif mode == 'edit':
            self.splitter.widget(0).show()
            self.splitter.widget(1).hide()
            self.splitter.setSizes([self.width(), 0])
        else:  # preview
            self.splitter.widget(0).hide()
            self.splitter.widget(1).show()
            self.splitter.setSizes([0, self.width()])

        self.mode_changed.emit(mode)

    def _on_text_changed(self):
        """文本变化"""
        self._content = self.editor.toPlainText()
        self._update_preview()

        # 更新字符统计
        text = self._content
        self.char_count_label.setText(f"{len(text)} 字符 · {text.count(chr(10)) + 1} 行")

        # 防抖预览更新
        QTimer.singleShot(300, self._update_preview)

    def _update_preview(self):
        """更新预览"""
        content = self.editor.toPlainText()
        result = self._preview_system._read_file_content
        md = self._preview_system._renderers.get(PreviewFileType.MARKDOWN)
        if md:
            result_obj = md.render(content, mode='preview')
            if result_obj.success:
                self.preview_view.setHtml(result_obj.html)

    def _get_empty_html(self) -> str:
        return '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{background:#1e1e1e;display:flex;align-items:center;justify-content:center;
height:100vh;margin:0;}p{color:#666;font-family:sans-serif;}</style>
</head><body><p>📝 在左侧编辑器中输入 Markdown...</p></body></html>'''


class FilePreviewView(QWebEngineView if HAS_WEBENGINE else QWidget):
    """文件预览视图 - 支持 HTML/PDF/Office/图片"""

    def __init__(self, parent=None):
        if HAS_WEBENGINE:
            super().__init__(parent)
            self._setup()
        else:
            super().__init__(parent)
            self.setStyleSheet("background:#1e1e1e;")

    def _setup(self):
        if not HAS_WEBENGINE:
            return
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

    def load_file(self, file_path: str, preview_system: PreviewSystem = None):
        """加载文件"""
        if preview_system is None:
            preview_system = get_preview_system()

        file_type = preview_system.get_file_type(file_path) if hasattr(preview_system, 'get_file_type') else None

        # 特殊处理 PDF（QWebEngineView 不直接支持 PDF，需要用其他方式）
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            self.load(QUrl.fromLocalFile(os.path.abspath(file_path)))
            return

        # 直接加载本地文件
        if ext in {'.html', '.htm'}:
            self.load(QUrl.fromLocalFile(os.path.abspath(file_path)))
            return

        # Markdown/代码文件用渲染器
        if ext in {'.md', '.markdown'}:
            ps = preview_system or get_preview_system()
            result = ps.render_file(file_path)
            if result.success:
                self.setHtml(result.html)
            return

        # 图片直接用 data URL
        if ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}:
            import base64
            with open(file_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            mime = {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'
            }.get(ext, 'image/png')
            self.setHtml(f'<html><body style="margin:0;display:flex;align-items:center;'
                          f'justify-content:center;height:100vh;background:#111;">'
                          f'<img src="data:{mime};base64,{data}" style="max-width:100%;"/>'
                          f'</body></html>')
            return

        # Office 文件
        result = preview_system.render_file(file_path)
        if result.success:
            self.setHtml(result.html)
        else:
            self.setHtml(f'<html><body style="padding:32px;font-family:sans-serif;color:#888;">'
                          f'<p>⚠️ {result.error}</p></body></html>')

    def get_file_type(self, file_path: str) -> PreviewFileType:
        """获取文件类型"""
        from core.office_preview.models import get_file_type
        return get_file_type(file_path)


class PreviewPanel(QWidget):
    """
    主预览面板 - AionUi 风格的多标签页预览系统

    功能：
    - 多标签页管理（打开/关闭/切换）
    - 文件类型自动识别和预览
    - Markdown 分屏编辑 + 实时预览
    - PDF/Office/图片预览
    - 键盘快捷键支持
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_system = get_preview_system()
        self._tab_manager = get_tab_manager()
        self._file_watcher = get_file_watcher()
        self._settings = QSettings('HermesDesktop', 'PreviewPanel')

        self._tab_widgets: Dict[str, QWidget] = {}  # tab_id -> widget
        self._tab_views: Dict[str, FilePreviewView] = {}  # tab_id -> view
        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标签栏
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setStyleSheet("""
            QTabBar {
                background: #1e1e1e;
                border-bottom: 1px solid #333;
            }
            QTabBar::tab {
                background: #252525;
                color: #888;
                padding: 8px 16px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                max-width: 200px;
            }
            QTabBar::tab:selected {
                background: #333;
                color: #fff;
            }
            QTabBar::tab:hover {
                background: #2a2a2a;
            }
            QTabBar::close-button {
                image: none;
                border-radius: 2px;
            }
            QTabBar::close-button:hover {
                background: #555;
            }
        """)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)

        # 工具栏
        toolbar = QFrame()
        toolbar.setStyleSheet("background: #1e1e1e; border-bottom: 1px solid #333;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        self.open_btn = QPushButton("📂 打开文件")
        self.open_btn.setStyleSheet("""
            QPushButton { background: #2563eb; color: #fff; border: none;
                          padding: 6px 14px; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self.open_btn.clicked.connect(self._on_open_file)
        toolbar_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setStyleSheet("""
            QPushButton { background: #333; color: #fff; border: none;
                          padding: 6px 14px; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background: #444; }
        """)
        self.save_btn.clicked.connect(self._on_save)
        toolbar_layout.addWidget(self.save_btn)

        self.reload_btn = QPushButton("🔄 刷新")
        self.reload_btn.setStyleSheet("""
            QPushButton { background: #333; color: #fff; border: none;
                          padding: 6px 14px; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background: #444; }
        """)
        self.reload_btn.clicked.connect(self._on_reload)
        toolbar_layout.addWidget(self.reload_btn)

        toolbar_layout.addStretch()

        # 标签页控制
        self.prev_tab_btn = QToolButton()
        self.prev_tab_btn.setText("◀")
        self.prev_tab_btn.clicked.connect(self._tab_manager.activate_prev_tab)
        toolbar_layout.addWidget(self.prev_tab_btn)

        self.next_tab_btn = QToolButton()
        self.next_tab_btn.setText("▶")
        self.next_tab_btn.clicked.connect(self._tab_manager.activate_next_tab)
        toolbar_layout.addWidget(self.next_tab_btn)

        # 内容区
        self.content_stack = QStackedWidget()

        # 欢迎页
        self.welcome_widget = self._create_welcome_widget()
        self.content_stack.addWidget(self.welcome_widget)

        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.tab_bar)
        main_layout.addWidget(self.content_stack)

    def _create_welcome_widget(self) -> QWidget:
        """创建欢迎页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("📄 文档预览")
        title.setStyleSheet("color: #888; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("拖放文件或点击「打开文件」开始预览\n\n支持格式：\n"
                          "Markdown · HTML · PDF · Word · Excel · PowerPoint · 图片 · 代码")
        subtitle.setStyleSheet("color: #555; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # 支持的格式列表
        formats_layout = QHBoxLayout()
        formats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        formats = [
            ("📝 文档", "md, html, pdf"),
            ("📊 Office", "docx, xlsx, pptx"),
            ("🖼️ 图片", "png, jpg, svg"),
            ("💻 代码", "py, js, ts, go"),
        ]
        for icon_label, exts in formats:
            label = QLabel(f"{icon_label}\n{exts}")
            label.setStyleSheet("color: #666; font-size: 12px; padding: 8px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            formats_layout.addWidget(label)

        layout.addLayout(formats_layout)
        return widget

    def _create_tab_widget(self, tab: PreviewTab) -> QWidget:
        """为标签页创建内容组件"""
        file_type = tab.file_info.file_type

        if file_type in (PreviewFileType.MARKDOWN, PreviewFileType.HTML):
            widget = MarkdownEditor()
            widget.set_content(tab.content)
        else:
            # 使用 WebEngineView 预览
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)

            view = FilePreviewView()
            view.load_file(tab.file_path, self._preview_system)
            layout.addWidget(view)
            self._tab_views[tab.tab_id] = view

        return widget

    def open_file(self, file_path: str):
        """打开文件"""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "文件不存在", f"找不到文件:\n{file_path}")
            return

        # 打开标签
        tab = self._tab_manager.open_file(file_path)

        # 检查是否已存在
        existing_index = self._find_tab_index(file_path)
        if existing_index >= 0:
            self.tab_bar.setCurrentIndex(existing_index)
            return

        # 添加标签
        tab_id = tab.tab_id
        display_name = tab.display_name
        icon = self._get_file_icon(tab.file_info.file_type)

        index = self.tab_bar.addTab(icon + " " + display_name)
        self.tab_bar.setTabData(index, tab_id)
        self.tab_bar.setCurrentIndex(index)

        # 创建内容组件
        widget = self._create_tab_widget(tab)
        self._tab_widgets[tab_id] = widget
        self.content_stack.addWidget(widget)

        # 开始监视文件
        self._file_watcher.watch(
            file_path,
            lambda fp, ev, tid=tab_id: self._on_file_changed(tid, fp, ev)
        )

        # 更新内容区
        self.content_stack.setCurrentWidget(widget)

    def _find_tab_index(self, file_path: str) -> int:
        """根据文件路径查找标签索引"""
        abs_path = os.path.abspath(file_path)
        for i in range(self.tab_bar.count()):
            tab_id = self.tab_bar.tabData(i)
            tab = self._tab_manager.get_tab(tab_id)
            if tab and tab.file_path == abs_path:
                return i
        return -1

    def _get_file_icon(self, file_type: PreviewFileType) -> str:
        """获取文件类型图标"""
        icons = {
            PreviewFileType.MARKDOWN: "📝",
            PreviewFileType.HTML: "🌐",
            PreviewFileType.PDF: "📄",
            PreviewFileType.WORD: "📘",
            PreviewFileType.EXCEL: "📗",
            PreviewFileType.POWERPOINT: "📙",
            PreviewFileType.IMAGE: "🖼️",
            PreviewFileType.CODE: "💻",
            PreviewFileType.TEXT: "📃",
        }
        return icons.get(file_type, "📄")

    def _on_tab_close(self, index: int):
        """关闭标签"""
        tab_id = self.tab_bar.tabData(index)

        # 移除组件
        if tab_id in self._tab_widgets:
            widget = self._tab_widgets.pop(tab_id)
            self.content_stack.removeWidget(widget)
            widget.deleteLater()

        self._tab_views.pop(tab_id, None)

        # 停止监视
        tab = self._tab_manager.get_tab(tab_id)
        if tab:
            self._file_watcher.unwatch(tab.file_path)

        # 关闭标签
        self._tab_manager.close_tab(tab_id)
        self.tab_bar.removeTab(index)

        # 如果没有标签了，显示欢迎页
        if self.tab_bar.count() == 0:
            self.content_stack.setCurrentWidget(self.welcome_widget)

    def _on_tab_changed(self, index: int):
        """切换标签"""
        if index < 0:
            return

        tab_id = self.tab_bar.tabData(index)
        tab = self._tab_manager.get_tab(tab_id)

        if tab and tab_id in self._tab_widgets:
            widget = self._tab_widgets[tab_id]
            self.content_stack.setCurrentWidget(widget)
            self._tab_manager.activate_tab(tab_id)

    def _on_file_changed(self, tab_id: str, file_path: str, event: str):
        """文件变化回调"""
        if event == 'changed':
            tab = self._tab_manager.get_tab(tab_id)
            if tab:
                self.reload_tab(tab_id)
        elif event == 'deleted':
            QMessageBox.warning(self, "文件已删除", f"文件已被删除:\n{file_path}")

    def reload_tab(self, tab_id: str = None):
        """重新加载标签"""
        if tab_id is None:
            tab = self._tab_manager.get_active_tab()
        else:
            tab = self._tab_manager.get_tab(tab_id)

        if not tab:
            return

        self._tab_manager.reload_tab(tab_id)

        # 重新加载视图
        if tab.tab_id in self._tab_views:
            view = self._tab_views[tab.tab_id]
            view.load_file(tab.file_path, self._preview_system)

    def _on_open_file(self):
        """打开文件对话框"""
        filters = (
            "所有支持的文件 (*.md *.markdown *.html *.htm *.pdf "
            "*.docx *.xlsx *.pptx *.txt *.py *.js *.ts *.json *.xml *.yaml *.yml "
            "*.png *.jpg *.jpeg *.gif *.svg *.webp);;"
            "Markdown (*.md *.markdown);;"
            "Office 文档 (*.docx *.xlsx *.pptx);;"
            "图片 (*.png *.jpg *.jpeg *.gif *.svg);;"
            "所有文件 (*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(self, "打开文件", "", filters)
        if file_path:
            self.open_file(file_path)

    def _on_save(self):
        """保存当前标签"""
        tab = self._tab_manager.get_active_tab()
        if not tab:
            return

        if tab.file_info.file_type in (PreviewFileType.MARKDOWN, PreviewFileType.HTML):
            # Markdown 编辑器
            widget = self._tab_widgets.get(tab.tab_id)
            if isinstance(widget, MarkdownEditor):
                new_content = widget.get_content()
                self._tab_manager.update_content(tab.tab_id, new_content)

        success = self._tab_manager.save_tab(tab.tab_id)
        if success:
            self._update_tab_label(tab.tab_id)
        else:
            QMessageBox.warning(self, "保存失败", f"无法保存文件:\n{tab.error_message}")

    def _on_reload(self):
        """刷新当前标签"""
        self.reload_tab()

    def _update_tab_label(self, tab_id: str):
        """更新标签名称"""
        tab = self._tab_manager.get_tab(tab_id)
        if not tab:
            return

        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == tab_id:
                icon = self._get_file_icon(tab.file_info.file_type)
                self.tab_bar.setTabText(i, icon + " " + tab.display_name)
                break

    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        from PyQt6.QtGui import QShortcut, QKeySequence

        shortcuts = {
            'Ctrl+O': self._on_open_file,
            'Ctrl+S': self._on_save,
            'Ctrl+R': self._on_reload,
            'Ctrl+W': lambda: self._on_tab_close(self.tab_bar.currentIndex()),
            'Ctrl+Tab': self._tab_manager.activate_next_tab,
            'Ctrl+Shift+Tab': self._tab_manager.activate_prev_tab,
        }

        for seq, handler in shortcuts.items():
            QShortcut(QKeySequence(seq), self, activated=handler)
