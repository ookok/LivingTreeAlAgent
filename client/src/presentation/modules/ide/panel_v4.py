"""
Modern Intelligent IDE Panel v4
=================================

OpenCode-inspired PyQt6 IDE with modern design:
- Clean split-panel layout (Chat | Editor | Sidebar)
- Theme system with 6 built-in themes
- Performance-optimized: async I/O, caching, thread management
- CodeTool v3 pipeline with visual feedback
- Serena integration with status indicator
- File tree, search, test, git sidebar panels
- Streaming chat with thinking/tool-call visualization
- Model selector with multi-provider support

Architecture:
  IntelligentIDEPanel (v4)
    |- ActivityBar (left icon strip)
    |- ChatPanel (main chat area with streaming)
    |- EditorPanel (code editor with tabs, diagnostics gutter)
    |- SidebarPanel (file tree / search / test / git / providers)
    |- StatusBar (Serena status, diagnostics, model info)
    |- PipelineOverlay (CodeTool v3 progress)
"""

import os
import re
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QTabWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QComboBox,
    QListWidget, QListWidgetItem, QInputDialog,
    QProgressBar, QFrame, QTextBrowser,
    QGroupBox, QCheckBox, QScrollArea, QSizePolicy,
    QToolButton, QMenu, QStatusBar
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QThread, QObject, pyqtSlot, QTimer, QSize
)
from PyQt6.QtGui import (
    QFont, QTextCursor, QKeySequence, QShortcut, QColor,
    QIcon, QTextCharFormat, QSyntaxHighlighter, QTextDocument,
    QAction
)

# Theme
from client.src.presentation.modules.ide.theme import (
    IDEThemeManager, ThemeColors, get_theme_manager
)

# Business layer (lazy imports to avoid circular dependency)
try:
    from client.src.business.ide_agent import IDEAgent
    from client.src.business.ide_service import IntelligentIDEService
except ImportError:
    IDEAgent = None
    IntelligentIDEService = None

# Widgets (lazy imports)
try:
    from client.src.presentation.widgets.project_browser import ProjectBrowser
    from client.src.presentation.widgets.global_search import GlobalSearchWidget
    from client.src.presentation.widgets.test_integration import TestIntegrationWidget
    from client.src.presentation.widgets.git_integration import GitIntegrationWidget
    from client.src.presentation.widgets.syntax_highlighter import get_highlighter
    from client.src.presentation.widgets.code_completer import get_completer
except ImportError:
    ProjectBrowser = None
    GlobalSearchWidget = None
    TestIntegrationWidget = None
    GitIntegrationWidget = None
    get_highlighter = None
    get_completer = None


# ════════════════════════════════════════════════════════════════
# Thread Management
# ════════════════════════════════════════════════════════════════

class ThreadManager:
    """Manages QThread lifecycle to prevent memory leaks."""

    def __init__(self):
        self._threads: Dict[str, QThread] = {}
        self._lock = threading.Lock()

    def submit(self, thread: QThread, name: str = "") -> str:
        """Register and start a thread. Returns thread ID."""
        tid = name or f"thread-{id(thread)}"
        with self._lock:
            self._threads[tid] = thread
            thread.finished.connect(lambda: self._cleanup(tid))
        thread.start()
        return tid

    def _cleanup(self, tid: str):
        """Remove finished thread from tracking."""
        with self._lock:
            self._threads.pop(tid, None)

    def cancel_all(self):
        """Stop all tracked threads."""
        with self._lock:
            for tid, t in list(self._threads.items()):
                if hasattr(t, 'stop'):
                    t.stop()
                if t.isRunning():
                    t.quit()
                    t.wait(2000)
            self._threads.clear()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._threads.values() if t.isRunning())

    def cleanup_finished(self):
        """Force cleanup of finished threads."""
        with self._lock:
            finished = [
                tid for tid, t in self._threads.items()
                if not t.isRunning()
            ]
            for tid in finished:
                self._threads.pop(tid, None)


# ════════════════════════════════════════════════════════════════
# Chat History Manager (bounded memory)
# ════════════════════════════════════════════════════════════════

class ChatHistoryManager:
    """Manages chat message history with memory limits."""

    def __init__(self, max_messages: int = 200, max_total_chars: int = 500_000):
        self._messages: List[Dict] = []
        self._max_messages = max_messages
        self._max_total_chars = max_total_chars
        self._total_chars = 0

    def add(self, role: str, content: str, metadata: Dict = None):
        self._messages.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        })
        self._total_chars += len(content)
        self.trim()

    def trim(self):
        """Remove oldest messages when limits exceeded."""
        while (len(self._messages) > self._max_messages or
               self._total_chars > self._max_total_chars) and self._messages:
            removed = self._messages.pop(0)
            self._total_chars -= len(removed.get("content", ""))

    def get_recent(self, n: int = None) -> List[Dict]:
        if n:
            return self._messages[-n:]
        return list(self._messages)

    def clear(self):
        self._messages.clear()
        self._total_chars = 0

    def size_info(self) -> Dict:
        return {
            "message_count": len(self._messages),
            "total_chars": self._total_chars,
            "max_messages": self._max_messages,
            "max_total_chars": self._max_total_chars,
        }


# ════════════════════════════════════════════════════════════════
# Async File I/O (QThread-based)
# ════════════════════════════════════════════════════════════════

class FileIOWorker(QObject):
    """Worker object for async file I/O running in QThread."""
    read_done = pyqtSignal(str, str)     # (path, content)
    write_done = pyqtSignal(str, bool)   # (path, success)
    io_error = pyqtSignal(str, str)      # (path, error_msg)

    def read_file(self, path: str, encoding: str = "utf-8"):
        try:
            with open(path, "r", encoding=encoding) as f:
                self.read_done.emit(path, f.read())
        except Exception as e:
            self.io_error.emit(path, str(e))

    def write_file(self, path: str, content: str, encoding: str = "utf-8"):
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            self.write_done.emit(path, True)
        except Exception as e:
            self.io_error.emit(path, str(e))


class AsyncFileIO:
    """Async file I/O manager using QThread pool."""

    def __init__(self, parent=None):
        self._parent = parent
        self._threads: List[QThread] = []
        self._worker = FileIOWorker()

    def read_file(self, path: str, callback, error_callback=None):
        """Read file asynchronously. callback(path, content)."""
        t = QThread(self._parent)
        self._worker.moveToThread(t)
        conn = self._worker.read_done.connect(callback)
        if error_callback:
            self._worker.io_error.connect(error_callback)
        t.started.connect(lambda: self._worker.read_file(path))
        t.finished.connect(lambda: self._cleanup_thread(t))
        self._threads.append(t)
        t.start()
        return t

    def write_file(self, path: str, content: str, callback=None, error_callback=None):
        """Write file asynchronously."""
        t = QThread(self._parent)
        self._worker.moveToThread(t)
        if callback:
            self._worker.write_done.connect(callback)
        if error_callback:
            self._worker.io_error.connect(error_callback)
        t.started.connect(lambda: self._worker.write_file(path, content))
        t.finished.connect(lambda: self._cleanup_thread(t))
        self._threads.append(t)
        t.start()
        return t

    def _cleanup_thread(self, t: QThread):
        if t in self._threads:
            self._threads.remove(t)
        t.deleteLater()


# ════════════════════════════════════════════════════════════════
# Activity Bar (left icon strip)
# ════════════════════════════════════════════════════════════════

class ActivityBar(QWidget):
    """Left icon strip for sidebar panel switching (VS Code style)."""

    sidebar_requested = pyqtSignal(int)  # panel index

    PANEL_ICONS = [
        ("Files", "\U0001F4C2"),      # Files
        ("Search", "\u2695"),          # Search
        ("Test", "\u2705"),            # Test
        ("Git", "\u2693"),             # Git
        ("Pipeline", "\u2699"),        # Pipeline
        ("Providers", "\U0001F310"),   # Providers
    ]

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._active_index = 0
        self._buttons: List[QToolButton] = []
        self.setFixedWidth(48)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        c = self.theme.colors

        for i, (name, icon) in enumerate(self.PANEL_ICONS):
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(name)
            btn.setFixedSize(40, 40)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFont(QFont("Segoe UI Emoji", 14))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Theme button at bottom
        self.theme_btn = QToolButton()
        self.theme_btn.setText("\U0001F3A8")
        self.theme_btn.setToolTip("Theme")
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.theme_btn.setFont(QFont("Segoe UI Emoji", 14))
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._cycle_theme)
        layout.addWidget(self.theme_btn)

        self._update_styles()

    def _on_click(self, index: int):
        self._active_index = index
        self._update_styles()
        self.sidebar_requested.emit(index)

    def _cycle_theme(self):
        """Cycle through available themes."""
        themes = list(self.theme.get_available_themes().keys())
        current = themes.index(self.theme.current_theme_id) if self.theme.current_theme_id in themes else 0
        next_theme = themes[(current + 1) % len(themes)]
        self.theme.apply_theme(next_theme)

    def _update_styles(self):
        c = self.theme.colors
        for i, btn in enumerate(self._buttons):
            if i == self._active_index:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {c.background_element};
                        border-left: 2px solid {c.primary};
                        border-radius: 0;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background: transparent;
                        border: none;
                        border-left: 2px solid transparent;
                        border-radius: 0;
                    }}
                    QToolButton:hover {{
                        background-color: {c.background_hover};
                    }}
                """)


# ════════════════════════════════════════════════════════════════
# Chat Panel
# ════════════════════════════════════════════════════════════════

class MessageBubble(QFrame):
    """Single message bubble with Markdown rendering and collapsible sections."""

    def __init__(self, role: str, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = ""
        self.theme = theme
        self._thinking_collapsed = True
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Role label
        self.role_label = QLabel("You" if self.role == "user" else "Assistant")
        self.role_label.setStyleSheet(f"font-size: 11px; color: {c.text_muted}; font-weight: bold;")
        layout.addWidget(self.role_label)

        # Content area
        if self.role == "user":
            self.content_label = QLabel()
            self.content_label.setWordWrap(True)
            self.content_label.setStyleSheet(f"font-size: 14px; color: {c.text}; padding: 4px 0;")
            self.content_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(self.content_label)
        else:
            self.content_view = QTextEdit()
            self.content_view.setReadOnly(True)
            self.content_view.setMinimumHeight(30)
            self.content_view.setMaximumHeight(800)
            self.content_view.setStyleSheet(f"""
                QTextEdit {{
                    background: transparent;
                    color: {c.text};
                    border: none;
                    font-size: 14px;
                    padding: 0;
                }}
            """)
            layout.addWidget(self.content_view)

        # Thinking section (collapsible, for assistant only)
        self.thinking_frame = QFrame()
        thinking_layout = QVBoxLayout(self.thinking_frame)
        thinking_layout.setContentsMargins(0, 2, 0, 2)
        thinking_layout.setSpacing(2)

        self.thinking_header = QHBoxLayout()
        self.thinking_toggle = QPushButton("\u25B6 Thinking")
        self.thinking_toggle.setFlat(True)
        self.thinking_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thinking_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {c.warning}; font-size: 11px; font-weight: bold;
                padding: 2px 4px;
            }}
        """)
        self.thinking_toggle.clicked.connect(self._toggle_thinking)
        self.thinking_header.addWidget(self.thinking_toggle)
        self.thinking_header.addStretch()
        thinking_layout.addLayout(self.thinking_header)

        self.thinking_content = QTextEdit()
        self.thinking_content.setReadOnly(True)
        self.thinking_content.setMaximumHeight(180)
        self.thinking_content.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.background_element};
                color: {c.text_muted};
                border: 1px solid {c.border_subtle};
                border-radius: 4px;
                font-size: 12px; padding: 6px;
            }}
        """)
        self.thinking_content.setVisible(False)
        thinking_layout.addWidget(self.thinking_content)
        self.thinking_frame.setVisible(False)
        layout.addWidget(self.thinking_frame)

        # Tool calls section
        self.tools_frame = QFrame()
        self.tools_layout = QVBoxLayout(self.tools_frame)
        self.tools_layout.setContentsMargins(0, 2, 0, 2)
        self.tools_frame.setVisible(False)
        layout.addWidget(self.tools_frame)

        # Timestamp
        self.time_label = QLabel(datetime.now().strftime("%H:%M"))
        self.time_label.setStyleSheet(f"font-size: 10px; color: {c.text_muted};")
        layout.addWidget(self.time_label)

        # Bubble styling
        if self.role == "user":
            self.setStyleSheet(f"""
                MessageBubble {{
                    background-color: {c.primary}18;
                    border-radius: 12px;
                    border: 1px solid {c.primary}33;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                MessageBubble {{
                    background-color: {c.background_element};
                    border-radius: 12px;
                    border: 1px solid {c.border_subtle};
                }}
            """)

    def _toggle_thinking(self):
        self._thinking_collapsed = not self._thinking_collapsed
        self.thinking_content.setVisible(not self._thinking_collapsed)
        self.thinking_toggle.setText(
            "\u25BC Thinking" if not self._thinking_collapsed else "\u25B6 Thinking"
        )

    def set_content(self, content: str):
        self.content = content
        if self.role == "user":
            self.content_label.setText(content)
        else:
            self._render_markdown(content)

    def append_content(self, chunk: str):
        self.content += chunk
        if self.role == "assistant":
            self._render_markdown(self.content)

    def set_thinking(self, text: str):
        self.thinking_frame.setVisible(True)
        self.thinking_content.setPlainText(text)

    def append_thinking(self, text: str):
        self.thinking_frame.setVisible(True)
        current = self.thinking_content.toPlainText()
        self.thinking_content.setPlainText(current + text)

    def add_tool_call(self, name: str, result: str = "", success: bool = True):
        c = self.theme.colors
        self.tools_frame.setVisible(True)
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.background_panel};
                border: 1px solid {c.border_subtle};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 4, 6, 4)
        fl.setSpacing(2)
        status = "\u2713" if success else "\u2717"
        color = c.success if success else c.error
        label = QLabel(f"{status} {name}")
        label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
        fl.addWidget(label)
        if result:
            result_label = QLabel(result[:300])
            result_label.setWordWrap(True)
            result_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
            fl.addWidget(result_label)
        self.tools_layout.addWidget(frame)

    def _render_markdown(self, text: str):
        """Simple markdown to HTML rendering."""
        c = self.theme.colors
        html = text
        # Code blocks
        html = re.sub(
            r'```(\w*)\n(.*?)```',
            rf'<pre style="background:{c.background_panel};color:{c.text};'
            rf'padding:12px;border-radius:6px;overflow-x:auto;'
            rf'border:1px solid {c.border};font-family:Consolas,monospace;'
            rf'font-size:13px;"><code>\2</code></pre>',
            html, flags=re.DOTALL
        )
        # Inline code
        html = re.sub(
            r'`([^`]+)`',
            rf'<code style="background:{c.background_element};color:{c.syntax_string};'
            rf'padding:2px 6px;border-radius:4px;font-family:Consolas,monospace;'
            rf'font-size:13px;">\1</code>',
            html
        )
        # Bold
        html = re.sub(r'\*\*(.*?)\*\*', rf'<b style="color:{c.text_bright};">\1</b>', html)
        # Italic
        html = re.sub(r'\*(.*?)\*', rf'<i>\1</i>', html)
        # Line breaks
        html = html.replace('\n', '<br>')
        self.content_view.setHtml(html)


class ChatPanel(QWidget):
    """Main chat panel with streaming, thinking, and tool-call display."""

    message_sent = pyqtSignal(str)

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.history = ChatHistoryManager()
        self.current_bubble: Optional[MessageBubble] = None
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat header
        header = QHBoxLayout()
        header.setContentsMargins(16, 10, 16, 10)
        self.title_label = QLabel("LivingTree AI IDE")
        self.title_label.setStyleSheet(f"""
            font-size: 16px; font-weight: bold; color: {c.text_bright};
        """)
        header.addWidget(self.title_label)
        header.addStretch()
        self.model_label = QLabel("")
        self.model_label.setStyleSheet(f"font-size: 12px; color: {c.text_muted};")
        header.addWidget(self.model_label)
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {c.border};")
        layout.addWidget(sep)

        # Chat messages scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {c.background};
                border: none;
            }}
        """)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

        # Input area
        input_container = QFrame()
        input_container.setStyleSheet(f"""
            QFrame {{
                background-color: {c.background_panel};
                border-top: 1px solid {c.border};
            }}
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 10, 12, 10)

        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(100)
        self.message_input.setMinimumHeight(40)
        self.message_input.setPlaceholderText(
            "Describe what you want to build or modify...\n\n"
            "Examples:\n"
            "  - Create a user authentication module\n"
            "  - Fix all lint errors in the project\n"
            "  - Run tests and auto-fix failures"
        )
        input_layout.addWidget(self.message_input)

        # Bottom bar: hints + send
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        hint = QLabel("Ctrl+Enter to send")
        hint.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        bottom_bar.addWidget(hint)

        bottom_bar.addStretch()

        self.send_btn = QPushButton("Send")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: {c.text_muted};
            }}
        """)
        self.send_btn.clicked.connect(self.send_message)
        bottom_bar.addWidget(self.send_btn)

        input_layout.addLayout(bottom_bar)
        layout.addWidget(input_container)

        # Ctrl+Enter shortcut
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.message_input)
        shortcut.activated.connect(self.send_message)

    def send_message(self):
        text = self.message_input.toPlainText().strip()
        if not text:
            return
        self.message_input.clear()
        self.add_user_message(text)
        self.history.add("user", text)
        self.message_sent.emit(text)

    def add_user_message(self, content: str):
        bubble = MessageBubble("user", self.theme)
        bubble.set_content(content)
        self._insert_bubble(bubble)

    def add_assistant_message(self, content: str = ""):
        bubble = MessageBubble("assistant", self.theme)
        if content:
            bubble.set_content(content)
        self.current_bubble = bubble
        self._insert_bubble(bubble)
        return bubble

    def append_stream_chunk(self, chunk: str):
        if not self.current_bubble:
            self.add_assistant_message()
        self.current_bubble.append_content(chunk)

    def set_thinking(self, text: str):
        if not self.current_bubble:
            self.add_assistant_message()
        self.current_bubble.set_thinking(text)

    def append_thinking(self, text: str):
        if not self.current_bubble:
            self.add_assistant_message()
        self.current_bubble.append_thinking(text)

    def add_tool_call(self, name: str, result: str = "", success: bool = True):
        if self.current_bubble:
            self.current_bubble.add_tool_call(name, result, success)

    def finalize_message(self):
        if self.current_bubble:
            self.history.add("assistant", self.current_bubble.content)
        self.current_bubble = None

    def add_welcome(self, message: str):
        bubble = MessageBubble("assistant", self.theme)
        bubble.set_content(message)
        self._insert_bubble(bubble)

    def _insert_bubble(self, bubble: MessageBubble):
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())


# ════════════════════════════════════════════════════════════════
# Editor Panel
# ════════════════════════════════════════════════════════════════

class EditorTab(QWidget):
    """Single editor tab with file info."""

    def __init__(self, file_path: str, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.theme = theme
        self._modified = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        c = self.theme.colors

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        self.lang_label = QLabel(self._get_language())
        self.lang_label.setStyleSheet(f"""
            font-size: 11px; color: {c.primary};
            background: {c.primary}22; padding: 2px 8px; border-radius: 4px;
        """)
        toolbar.addWidget(self.lang_label)

        toolbar.addStretch()

        self.cursor_info = QLabel("Ln 1, Col 1")
        self.cursor_info.setStyleSheet(f"font-size: 11px; color: {c.text_muted};")
        toolbar.addWidget(self.cursor_info)

        layout.addLayout(toolbar)

        # Code editor
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setFont(QFont("Consolas", 13))
        self.editor.setTabStopDistance(QFontMetricsF(self.editor.font()).horizontalAdvance(' ') * 4)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_changed)
        layout.addWidget(self.editor)

        # Bottom action bar
        actions = QHBoxLayout()
        actions.setContentsMargins(8, 4, 8, 4)

        for action_name, action_text in [
            ("explain", "Explain"), ("debug", "Debug"), ("optimize", "Optimize")
        ]:
            btn = QPushButton(action_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c.background_element};
                    color: {c.text_muted};
                    border: 1px solid {c.border_subtle};
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: {c.primary};
                    color: {c.text};
                }}
            """)
            actions.addWidget(btn)
        actions.addStretch()
        layout.addLayout(actions)

    def _get_language(self) -> str:
        ext = os.path.splitext(self.file_path)[1].lower()
        lang_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".html": "HTML", ".css": "CSS", ".json": "JSON", ".md": "Markdown",
            ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
            ".go": "Go", ".rs": "Rust", ".java": "Java", ".cpp": "C++",
        }
        return lang_map.get(ext, ext.upper() if ext else "Text")

    def _on_text_changed(self):
        self._modified = True

    def _on_cursor_changed(self):
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.cursor_info.setText(f"Ln {line}, Col {col}")


class EditorPanel(QWidget):
    """Tabbed code editor with language detection and syntax highlighting."""

    file_saved = pyqtSignal(str)
    file_opened = pyqtSignal(str)

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._tabs: Dict[str, EditorTab] = {}
        self._async_io = AsyncFileIO(self)
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab bar
        self.tab_bar = QTabWidget()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)

        # Empty state
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("\U0001F4BB")
        empty_icon.setFont(QFont("Segoe UI Emoji", 48))
        empty_icon.setStyleSheet(f"color: {c.text_muted};")
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel("Open a file to start editing")
        empty_text.setStyleSheet(f"color: {c.text_muted}; font-size: 14px;")
        empty_layout.addWidget(empty_text)
        empty_hint = QLabel("Ctrl+O or use the file tree")
        empty_hint.setStyleSheet(f"color: {c.border}; font-size: 12px;")
        empty_layout.addWidget(empty_hint)
        self.tab_bar.addTab(self.empty_state, "")

        # Hide close button on empty state
        self.tab_bar.tabBar().tabButton(0, QTabWidget.TabButtonPosition.RightSide).hide()

        layout.addWidget(self.tab_bar)

    def open_file(self, file_path: str):
        """Open file in a new tab (async)."""
        if file_path in self._tabs:
            # Switch to existing tab
            idx = self.tab_bar.indexOf(self._tabs[file_path])
            if idx >= 0:
                self.tab_bar.setCurrentIndex(idx)
            return

        tab = EditorTab(file_path, self.theme)
        self._tabs[file_path] = tab
        self.tab_bar.addTab(tab, os.path.basename(file_path))

        # Remove empty state if present
        if self.tab_bar.count() > 1:
            empty_idx = self.tab_bar.indexOf(self.empty_state)
            if empty_idx >= 0:
                self.tab_bar.removeTab(empty_idx)

        # Async file read
        def on_read(path, content):
            if path in self._tabs:
                self._tabs[path].editor.setPlainText(content)
                # Apply syntax highlighting
                if get_highlighter:
                    ext = os.path.splitext(path)[1].lower()
                    lang_map = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript"}
                    lang = lang_map.get(ext, "")
                    if lang:
                        h = get_highlighter(lang, self._tabs[path].editor)
                        if h:
                            h.setDocument(self._tabs[path].editor.document())
                self.tab_bar.setCurrentWidget(tab)
                self.file_opened.emit(path)

        self._async_io.read_file(file_path, on_read)

    def save_current(self):
        """Save current file."""
        tab = self.tab_bar.currentWidget()
        if isinstance(tab, EditorTab):
            content = tab.editor.toPlainText()
            path = tab.file_path

            def on_write(p, success):
                if success:
                    tab._modified = False
                    self.file_saved.emit(p)

            self._async_io.write_file(path, content, on_write)

    def save_as(self):
        """Save current file to new path."""
        tab = self.tab_bar.currentWidget()
        if not isinstance(tab, EditorTab):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save As", tab.file_path)
        if path:
            tab.file_path = path
            self.save_current()

    def get_current_content(self) -> str:
        tab = self.tab_bar.currentWidget()
        if isinstance(tab, EditorTab):
            return tab.editor.toPlainText()
        return ""

    def get_current_file(self) -> str:
        tab = self.tab_bar.currentWidget()
        if isinstance(tab, EditorTab):
            return tab.file_path
        return ""

    def set_content(self, content: str):
        tab = self.tab_bar.currentWidget()
        if isinstance(tab, EditorTab):
            tab.editor.setPlainText(content)

    def _close_tab(self, index: int):
        widget = self.tab_bar.widget(index)
        if isinstance(widget, EditorTab):
            path = widget.file_path
            self._tabs.pop(path, None)
        self.tab_bar.removeTab(index)

        # Show empty state if no tabs
        if self.tab_bar.count() == 0:
            self.tab_bar.addTab(self.empty_state, "")
            self.tab_bar.tabBar().tabButton(0, QTabWidget.TabButtonPosition.RightSide).hide()


# ════════════════════════════════════════════════════════════════
# Sidebar Panel (file tree / search / test / git / pipeline / providers)
# ════════════════════════════════════════════════════════════════

class PipelinePanel(QWidget):
    """CodeTool v3 pipeline visualization."""

    action_requested = pyqtSignal(str, str)  # (action, instruction)

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._steps: Dict[str, QWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("CodeTool Pipeline")
        title.setStyleSheet(f"""
            font-size: 15px; font-weight: bold; color: {c.text_bright};
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # Pipeline steps
        steps = [
            ("write", "Auto-Write", "LLM planning -> Precise code generation"),
            ("test", "Auto-Test", "pytest execution -> Auto-fix loop"),
            ("fix", "Auto-Fix", "LSP diagnostics -> LLM repair"),
            ("publish", "Auto-Publish", "git commit/push -> CI/CD"),
        ]
        for step_id, name, desc in steps:
            frame = self._make_step(step_id, name, desc)
            self._steps[step_id] = frame
            layout.addWidget(frame)

        # Actions
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {c.border};")
        layout.addWidget(sep)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        for action_id, label, color_key in [
            ("scan", "Scan Project", "info"),
            ("plan", "Plan Code", "info"),
            ("full_pipeline", "Full Pipeline", "success"),
        ]:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            color = getattr(c, color_key, c.primary)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color}22; color: {color};
                    border: 1px solid {color}44; border-radius: 6px;
                    padding: 8px; font-weight: bold; font-size: 13px;
                }}
                QPushButton:hover {{
                    background: {color}33;
                }}
            """)
            btn.clicked.connect(
                lambda checked, a=action_id: self._on_action(a)
            )
            actions.addWidget(btn)
        layout.addLayout(actions)

        # Log area
        log_title = QLabel("Execution Log")
        log_title.setStyleSheet(f"color: {c.text_muted}; font-size: 11px; margin-top: 8px;")
        layout.addWidget(log_title)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background: {c.background};
                color: {c.text_muted};
                border: 1px solid {c.border_subtle};
                border-radius: 4px;
                font-family: Consolas, monospace; font-size: 11px;
            }}
        """)
        layout.addWidget(self.log_view)
        layout.addStretch()

    def _make_step(self, step_id: str, name: str, desc: str) -> QFrame:
        c = self.theme.colors
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {c.background_element};
                border: 1px solid {c.border_subtle};
                border-radius: 6px;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(2)

        row = QHBoxLayout()
        status = QLabel("\u2610")
        status.setStyleSheet(f"font-size: 14px;")
        row.addWidget(status)
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c.text};")
        row.addWidget(name_label)
        row.addStretch()
        fl.addLayout(row)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet(f"font-size: 11px; color: {c.text_muted};")
        fl.addWidget(desc_label)

        frame._status_label = status
        frame._desc_label = desc_label
        frame._step_id = step_id
        return frame

    def _on_action(self, action: str):
        instruction, ok = QInputDialog.getText(
            self, "Pipeline", "Enter instruction:",
            text=""
        )
        if ok:
            self.action_requested.emit(action, instruction)

    def set_step_status(self, step_id: str, status: str, detail: str = ""):
        widget = self._steps.get(step_id)
        if not widget:
            return
        c = self.theme.colors
        icons = {
            "pending": ("\u2610", c.text_muted),
            "running": ("\u21BB", c.warning),
            "success": ("\u2714", c.success),
            "error": ("\u2718", c.error),
        }
        icon, color = icons.get(status, ("\u2610", c.text_muted))
        widget._status_label.setText(icon)
        widget._status_label.setStyleSheet(f"font-size: 14px; color: {color};")
        if detail:
            widget._desc_label.setText(detail)
            widget._desc_label.setStyleSheet(f"font-size: 11px; color: {color};")

    def append_log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")

    def clear_pipeline(self):
        for sid in self._steps:
            self.set_step_status(sid, "pending")
        self.log_view.clear()


class ProvidersPanel(QWidget):
    """Model provider management panel."""

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Model Providers")
        title.setStyleSheet(f"""
            font-size: 15px; font-weight: bold; color: {c.text_bright};
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # Provider list
        self.provider_list = QListWidget()
        self.provider_list.setStyleSheet(f"""
            QListWidget {{
                background: {c.background};
                color: {c.text};
                border: 1px solid {c.border_subtle};
                border-radius: 6px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {c.border_subtle};
            }}
            QListWidget::item:selected {{
                background: {c.primary}22;
            }}
        """)
        layout.addWidget(self.provider_list)

        # Connect button
        self.connect_btn = QPushButton("Connect Provider")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.primary};
                color: #ffffff;
                border: none; border-radius: 6px;
                padding: 8px; font-weight: bold;
            }}
        """)
        layout.addWidget(self.connect_btn)
        layout.addStretch()

        self._load_providers()

    def _load_providers(self):
        """Load provider list from registry."""
        try:
            from client.src.business.providers.provider_registry import get_provider_registry
            registry = get_provider_registry()
            for pid, pconfig in registry.get_all_providers().items():
                status = "[Connected]" if pconfig.get("api_key") else ""
                item = QListWidgetItem(f"{pconfig.get('display_name', pid)} {status}")
                self.provider_list.addItem(item)
        except Exception:
            # Fallback: show basic providers
            for name in ["Ollama (Local)", "OpenAI", "Anthropic", "DeepSeek", "Google"]:
                self.provider_list.addItem(QListWidgetItem(name))


class SidebarPanel(QWidget):
    """Collapsible sidebar with multiple panels."""

    def __init__(self, theme: IDEThemeManager, project_path: str, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.project_path = project_path
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QTabWidget()
        self.stack.setTabPosition(QTabWidget.TabPosition.Bottom)
        self.stack.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {c.background_panel};
                color: {c.text_muted};
                padding: 6px 12px;
                border: none;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                color: {c.text};
                border-bottom: 2px solid {c.primary};
            }}
        """)

        # File browser
        if ProjectBrowser:
            try:
                self.project_browser = ProjectBrowser(self.project_path)
                self.stack.addTab(self.project_browser, "Files")
            except Exception:
                self._add_placeholder("Files")
        else:
            self._add_placeholder("Files")

        # Search
        if GlobalSearchWidget:
            try:
                self.global_search = GlobalSearchWidget()
                self.stack.addTab(self.global_search, "Search")
            except Exception:
                self._add_placeholder("Search")
        else:
            self._add_placeholder("Search")

        # Test
        if TestIntegrationWidget:
            try:
                self.test_widget = TestIntegrationWidget()
                self.stack.addTab(self.test_widget, "Test")
            except Exception:
                self._add_placeholder("Test")
        else:
            self._add_placeholder("Test")

        # Git
        if GitIntegrationWidget:
            try:
                self.git_widget = GitIntegrationWidget(self.project_path)
                self.stack.addTab(self.git_widget, "Git")
            except Exception:
                self._add_placeholder("Git")
        else:
            self._add_placeholder("Git")

        # Pipeline
        self.pipeline = PipelinePanel(self.theme)
        self.stack.addTab(self.pipeline, "Pipeline")

        # Providers
        self.providers = ProvidersPanel(self.theme)
        self.stack.addTab(self.providers, "Providers")

        layout.addWidget(self.stack)

    def _add_placeholder(self, name: str):
        w = QLabel(f"{name} - Not Available")
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addTab(w, name)


# ════════════════════════════════════════════════════════════════
# Status Bar
# ════════════════════════════════════════════════════════════════

class IDEStatusBar(QWidget):
    """Bottom status bar with Serena status, diagnostics, model info."""

    def __init__(self, theme: IDEThemeManager, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        c = self.theme.colors
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(16)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c.background_panel};
                border-top: 1px solid {c.border};
            }}
        """)

        # Serena status
        self.serena_dot = QLabel("\u25CF")
        self.serena_dot.setStyleSheet(f"color: {c.error}; font-size: 12px;")
        layout.addWidget(self.serena_dot)

        self.serena_label = QLabel("Serena: Offline")
        self.serena_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.serena_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {c.border};")
        layout.addWidget(sep)

        # Diagnostics
        self.diag_label = QLabel("No issues")
        self.diag_label.setStyleSheet(f"color: {c.success}; font-size: 11px;")
        layout.addWidget(self.diag_label)

        layout.addStretch()

        # Model info
        self.model_label = QLabel("Model: qwen3.6:35b")
        self.model_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.model_label)

        # Theme name
        self.theme_label = QLabel(f"Theme: {self.theme.current_theme_id}")
        self.theme_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.theme_label)

        self.setFixedHeight(28)

    def update_serena(self, status: str, diagnostics_count: int = 0):
        c = self.theme.colors
        status_map = {
            "online": (c.success, "Serena: Online"),
            "offline": (c.error, "Serena: Offline"),
            "fallback": (c.warning, "Serena: AST Fallback"),
        }
        color, text = status_map.get(status, (c.text_muted, f"Serena: {status}"))
        self.serena_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.serena_label.setText(text)
        self.serena_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        if diagnostics_count > 0:
            self.diag_label.setText(f"{diagnostics_count} issues")
            self.diag_label.setStyleSheet(f"color: {c.warning}; font-size: 11px;")
        else:
            self.diag_label.setText("No issues")
            self.diag_label.setStyleSheet(f"color: {c.success}; font-size: 11px;")

    def update_model(self, model_name: str):
        self.model_label.setText(f"Model: {model_name}")

    def update_theme_label(self, theme_id: str):
        self.theme_label.setText(f"Theme: {theme_id}")


# ════════════════════════════════════════════════════════════════
# Chat Worker Thread (background AI processing)
# ════════════════════════════════════════════════════════════════

class ChatWorker(QThread):
    """Background thread for AI chat processing with streaming."""

    chunk_received = pyqtSignal(str)
    thinking_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    code_generated = pyqtSignal(str, str)       # (file_path, code)
    tool_start = pyqtSignal(str, str)            # (name, params)
    tool_result = pyqtSignal(str, str, bool)     # (name, result, success)
    pipeline_step = pyqtSignal(str, str, bool)   # (step, detail, success)

    def __init__(self, agent, message: str, context: Dict = None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context or {}
        self._stop_requested = False

    def run(self):
        try:
            full_content = ""

            def on_delta(delta):
                nonlocal full_content
                if self._stop_requested:
                    return
                full_content += delta
                self.chunk_received.emit(delta)

            def on_thinking(text):
                if self._stop_requested:
                    return
                self.thinking_received.emit(text)

            def on_tool_start(name, params):
                self.tool_start.emit(name, params)

            def on_tool_result(name, result, success):
                self.tool_result.emit(name, result, success)

            response = self.agent.process_chat_message(
                self.message,
                self.context,
                callbacks={
                    "on_stream_delta": on_delta,
                    "on_thinking": on_thinking,
                    "on_tool_start": on_tool_start,
                    "on_tool_result": on_tool_result,
                },
            )

            if response.get("type") == "code_generation":
                self.code_generated.emit(
                    response.get("file_path", ""),
                    response.get("code", "")
                )

            if response.get("type") == "pipeline_result":
                for step in response.get("steps", []):
                    self.pipeline_step.emit(
                        step.get("name", ""),
                        step.get("detail", ""),
                        step.get("success", False),
                    )

            self.finished.emit(full_content or response.get("message", ""))

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"{str(e)}\n{traceback.format_exc()}")

    def stop(self):
        self._stop_requested = True


class CodeExecutionWorker(QThread):
    """Background thread for code execution."""

    output_line = pyqtSignal(str)
    error_line = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, agent, code: str, language: str):
        super().__init__()
        self.agent = agent
        self.code = code
        self.language = language
        self._stop_requested = False

    def run(self):
        try:
            def on_output(line):
                if not self._stop_requested:
                    self.output_line.emit(line)

            def on_error(line):
                if not self._stop_requested:
                    self.error_line.emit(line)

            def on_done(result):
                if not self._stop_requested:
                    self.finished.emit({
                        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                        "output": result.output,
                        "error": result.error,
                        "exit_code": result.exit_code,
                        "execution_time_ms": getattr(result, 'execution_time_ms', 0),
                    })

            result = self.agent.execute_code(
                self.code, self.language,
                callbacks={
                    "on_output_line": on_output,
                    "on_error_line": on_error,
                    "on_finished": on_done,
                },
            )
            if result:
                self.finished.emit(result)

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"{str(e)}\n{traceback.format_exc()}")

    def stop(self):
        self._stop_requested = True


# ════════════════════════════════════════════════════════════════
# Main IDE Panel (v4)
# ════════════════════════════════════════════════════════════════

class IntelligentIDEPanel(QWidget):
    """
    Modern Intelligent IDE Panel (v4)

    OpenCode-inspired design with:
    - Activity bar (left icon strip)
    - Chat panel (AI conversation with streaming)
    - Editor panel (tabbed code editor)
    - Sidebar panel (files/search/test/git/pipeline/providers)
    - Status bar (Serena status, diagnostics, model info)
    - Theme system (6 built-in themes, runtime switching)
    - Thread management (no memory leaks)
    - Chat history (bounded memory)
    - Async file I/O (non-blocking)
    """

    def __init__(self, parent=None, project_path=None):
        super().__init__(parent)
        self.project_path = project_path or os.getcwd()
        self.theme_manager = get_theme_manager()
        self.thread_manager = ThreadManager()

        # Initialize IDE Agent (lazy, with fallback)
        self.ide_agent = None
        self._init_agent()

        # Apply theme and build UI
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        self._build_ui()
        self._apply_theme()

        # Serena diagnostics (debounced, not blocking)
        self._diag_timer = QTimer(self)
        self._diag_timer.setSingleShot(True)
        self._diag_timer.timeout.connect(self._run_diagnostics_safe)
        self._file_save_timer = QTimer(self)
        self._file_save_timer.setSingleShot(True)
        self._file_save_timer.timeout.connect(self._on_file_saved_delayed)

        # Add welcome message
        self._add_welcome()

    def _init_agent(self):
        """Initialize IDE agent with fallback."""
        if IDEAgent is not None:
            try:
                self.ide_agent = IDEAgent()
            except Exception:
                self.ide_agent = None

    def _build_ui(self):
        """Build the main IDE layout."""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Main horizontal splitter
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Activity bar (left)
        self.activity_bar = ActivityBar(self.theme_manager)
        self.h_splitter.addWidget(self.activity_bar)

        # Content area (chat + editor)
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Chat panel
        self.chat_panel = ChatPanel(self.theme_manager)
        self.chat_panel.message_sent.connect(self._handle_user_message)
        self.content_splitter.addWidget(self.chat_panel)

        # Right area: editor + sidebar
        self.right_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Editor panel
        self.editor_panel = EditorPanel(self.theme_manager)
        self.editor_panel.file_saved.connect(self._on_editor_file_saved)
        self.right_splitter.addWidget(self.editor_panel)

        # Sidebar panel
        self.sidebar = SidebarPanel(self.theme_manager, self.project_path)
        self.sidebar.pipeline.action_requested.connect(self._handle_pipeline_action)
        if hasattr(self.sidebar, "project_browser"):
            self.sidebar.project_browser.file_opened.connect(self.editor_panel.open_file)
        if hasattr(self.sidebar, "global_search"):
            self.sidebar.global_search.file_opened.connect(self.editor_panel.open_file)
        self.right_splitter.addWidget(self.sidebar)

        # Set splitter ratios
        self.right_splitter.setStretchFactor(0, 3)
        self.right_splitter.setStretchFactor(1, 1)
        self.content_splitter.setStretchFactor(0, 2)
        self.content_splitter.setStretchFactor(1, 3)

        self.content_splitter.addWidget(self.right_splitter)
        self.h_splitter.addWidget(self.content_splitter)

        self.h_splitter.setStretchFactor(0, 0)   # Activity bar fixed
        self.h_splitter.setStretchFactor(1, 1)    # Content flexible

        self._main_layout.addWidget(self.h_splitter, 1)

        # Status bar
        self.status_bar = IDEStatusBar(self.theme_manager)
        self._main_layout.addWidget(self.status_bar)

        # Connect activity bar
        self.activity_bar.sidebar_requested.connect(self._switch_sidebar)

    def _apply_theme(self):
        """Apply current theme stylesheet."""
        qss = self.theme_manager.generate_qss()
        self.setStyleSheet(qss)

        # Update status bar theme label
        self.status_bar.update_theme_label(self.theme_manager.current_theme_id)

    def _on_theme_changed(self, theme_id: str):
        """Handle theme change."""
        self._apply_theme()

        # Refresh sidebar panels
        self.sidebar.deleteLater()
        self.sidebar = SidebarPanel(self.theme_manager, self.project_path)
        self.sidebar.pipeline.action_requested.connect(self._handle_pipeline_action)
        if hasattr(self.sidebar, "project_browser"):
            self.sidebar.project_browser.file_opened.connect(self.editor_panel.open_file)
        if hasattr(self.sidebar, "global_search"):
            self.sidebar.global_search.file_opened.connect(self.editor_panel.open_file)
        self.right_splitter.addWidget(self.sidebar)

        # Refresh status bar
        self.status_bar.update_theme_label(theme_id)

    def _switch_sidebar(self, index: int):
        """Switch sidebar tab."""
        self.sidebar.stack.setCurrentIndex(index)

    def _add_welcome(self):
        welcome = (
            "# LivingTree AI IDE v4\n\n"
            "Powered by CodeTool v3 + Serena LSP\n\n"
            "## What I can do\n"
            "- **Generate code** - Create modules, classes, functions\n"
            "- **Modify code** - Precise edits via Serena symbol-level operations\n"
            "- **Auto-Test** - Run tests and auto-fix failures (up to 3 rounds)\n"
            "- **Auto-Fix** - LSP diagnostics -> LLM repair -> atomic replacement\n"
            "- **Auto-Publish** - git add/commit/push -> CI/CD\n"
            "- **Plan** - LLM generates structured implementation plan\n"
            "- **Scan** - Analyze project structure\n\n"
            "## v4 Features\n"
            "- 6 built-in themes (click palette icon to switch)\n"
            "- Streaming chat with thinking visualization\n"
            "- Tool call tracking\n"
            "- Async file I/O (non-blocking)\n"
            "- Bounded chat history (memory safe)\n"
            "- Thread lifecycle management\n\n"
            "## Examples\n"
            "- \"Create a user authentication module\"\n"
            "- \"Run tests and fix all failures\"\n"
            "- \"Plan a database refactoring\"\n"
            "- \"Scan the project structure\"\n"
        )
        self.chat_panel.add_welcome(welcome)

    # ── Message Handling ──

    def _handle_user_message(self, message: str):
        """Handle user message from chat input."""
        if not self.ide_agent:
            self.chat_panel.append_stream_chunk(
                "\nIDE Agent not available. Check dependencies."
            )
            self.chat_panel.finalize_message()
            return

        self.chat_panel.add_assistant_message()

        worker = ChatWorker(
            self.ide_agent, message,
            context={"project_path": self.project_path}
        )
        worker.chunk_received.connect(self.chat_panel.append_stream_chunk)
        worker.thinking_received.connect(self.chat_panel.append_thinking)
        worker.tool_start.connect(self._on_tool_start)
        worker.tool_result.connect(self._on_tool_result)
        worker.pipeline_step.connect(self._on_pipeline_step)
        worker.finished.connect(self._on_chat_finished)
        worker.error_occurred.connect(self._on_chat_error)
        worker.code_generated.connect(self._on_code_generated)
        self.thread_manager.submit(worker, f"chat-{time.time()}")

    def _on_tool_start(self, name: str, params: str):
        self.chat_panel.add_tool_call(name, params, True)
        self.sidebar.pipeline.append_log(f">> {name}: {params[:80]}")

    def _on_tool_result(self, name: str, result: str, success: bool):
        # Update last tool call widget
        self.sidebar.pipeline.append_log(
            f"{'OK' if success else 'FAIL'} {name}: {result[:100]}"
        )

    def _on_pipeline_step(self, step_name: str, detail: str, success: bool):
        step_id = step_name.lower().replace("codetool.", "").replace(".", "_")
        status = "success" if success else "error"
        self.sidebar.pipeline.set_step_status(step_id, status, detail)

    def _on_chat_finished(self, content: str):
        self.chat_panel.finalize_message()

    def _on_chat_error(self, error_msg: str):
        self.chat_panel.append_stream_chunk(f"\nError: {error_msg}")
        self.chat_panel.finalize_message()

    def _on_code_generated(self, file_path: str, code: str):
        self.editor_panel.open_file(file_path) if file_path else None
        if not file_path:
            self.editor_panel.set_content(code)

    # ── Pipeline ──

    def _handle_pipeline_action(self, action: str, instruction: str):
        """Handle pipeline action from sidebar."""
        if not self.ide_agent or not instruction:
            return

        self.sidebar.pipeline.clear_pipeline()
        self.chat_panel.add_assistant_message()

        if action == "full_pipeline":
            self.chat_panel.append_stream_chunk("Starting full pipeline...\n")
            if self.ide_agent._ensure_code_tool():
                try:
                    for step in [("write", "Generating code..."),
                                 ("test", "Running tests..."),
                                 ("fix", "Fixing issues...")]:
                        self.sidebar.pipeline.set_step_status(step[0], "running", step[1])
                        result = self.ide_agent._code_tool.execute(
                            action=step[0],
                            instruction=instruction,
                            project_path=self.project_path
                        )
                        status = "success" if result.success else "error"
                        detail = result.error if not result.success else f"Done"
                        self.sidebar.pipeline.set_step_status(step[0], status, detail)

                    self.sidebar.pipeline.append_log("Pipeline completed")
                    self.chat_panel.append_stream_chunk("\nPipeline completed!\n")
                except Exception as e:
                    self.sidebar.pipeline.append_log(f"Pipeline failed: {e}")
                    self.chat_panel.append_stream_chunk(f"\nPipeline failed: {e}\n")

            self.chat_panel.finalize_message()
        else:
            worker = ChatWorker(
                self.ide_agent, instruction,
                context={"project_path": self.project_path}
            )
            worker.chunk_received.connect(self.chat_panel.append_stream_chunk)
            worker.tool_start.connect(self._on_tool_start)
            worker.tool_result.connect(self._on_tool_result)
            worker.finished.connect(self._on_chat_finished)
            worker.error_occurred.connect(self._on_chat_error)
            self.thread_manager.submit(worker, f"pipeline-{action}-{time.time()}")

    # ── File Operations ──

    def _on_editor_file_saved(self, file_path: str):
        """Handle file save event (debounced diagnostics)."""
        self._file_save_timer.start(500)

    def _on_file_saved_delayed(self):
        """Run diagnostics after file save (debounced)."""
        self._diag_timer.start(300)

    def _run_diagnostics_safe(self):
        """Run diagnostics in a safe, non-blocking way."""
        if not self.ide_agent:
            return
        file_path = self.editor_panel.get_current_file()
        if not file_path:
            return

        try:
            status = self.ide_agent.get_serena_status()
            count = 0
            if hasattr(self.ide_agent, 'get_serena_diagnostics'):
                diags = self.ide_agent.get_serena_diagnostics(file_path)
                count = sum(1 for d in diags if d.get('severity') in ('error', 'warning'))
            self.status_bar.update_serena(status, count)
        except Exception:
            pass

    def open_file(self, file_path: str):
        """Open file in editor."""
        self.editor_panel.open_file(file_path)

    def set_project_path(self, path: str):
        """Set project path."""
        self.project_path = path
        if hasattr(self.sidebar, "project_browser"):
            try:
                self.sidebar.project_browser.set_root_path(path)
            except Exception:
                pass
        if hasattr(self.sidebar, "git_widget"):
            try:
                self.sidebar.git_widget.set_project_path(path)
            except Exception:
                pass

    def cleanup(self):
        """Clean up resources on close."""
        self.thread_manager.cancel_all()


# ════════════════════════════════════════════════════════════════
# Standalone Entry Point
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = IntelligentIDEPanel()
    panel.setWindowTitle("LivingTree AI - Intelligent IDE v4")
    panel.resize(1400, 900)
    panel.show()
    sys.exit(app.exec())
