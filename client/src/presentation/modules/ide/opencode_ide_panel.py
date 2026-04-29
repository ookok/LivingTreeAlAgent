"""
OpenCode IDE Panel - Chat-Driven Development Environment
======================================================

OpenCode-inspired modern IDE with:
- Chat-first design (AI conversation as the primary interface)
- Streaming output with Markdown rendering
- Tool call timeline visualization
- CodeTool v3 pipeline integration
- OpenCode dark theme (GitHub Dark style)
- Split-panel layout (Chat | Editor)

Author: LivingTreeAI
"""

import os
import re
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QTabWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QComboBox,
    QListWidget, QListWidgetItem, QInputDialog,
    QProgressBar, QFrame, QTextBrowser,
    QGroupBox, QCheckBox, QScrollArea, QSizePolicy,
    QToolButton, QMenu, QStatusBar, QApplication,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QThread, QObject, pyqtSlot, QTimer, QSize,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QTextCursor, QKeySequence, QShortcut, QColor,
    QIcon, QTextCharFormat, QSyntaxHighlighter, QTextDocument,
    QAction, QPalette
)

# ─────────────────────────────────────────────────────────────────────────────
# OpenCode Dark Theme
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OpenCodeColors:
    """OpenCode GitHub Dark theme colors"""
    # Core
    background: str = "#0d1117"
    surface: str = "#161b22"
    surface_elevated: str = "#1c2128"
    border: str = "#30363d"
    border_muted: str = "#21262d"

    # Brand
    primary: str = "#58a6ff"
    primary_hover: str = "#79c0ff"
    secondary: str = "#8b949e"

    # Status
    success: str = "#3fb950"
    warning: str = "#d29922"
    error: str = "#f85149"
    info: str = "#58a6ff"

    # Text
    text: str = "#c9d1d9"
    text_muted: str = "#8b949e"
    text_bright: str = "#f0f6fc"

    # User message
    user_bg: str = "#1f6feb"
    user_text: str = "#ffffff"

    # Syntax highlighting
    syntax_keyword: str = "#ff7b72"
    syntax_string: str = "#a5d6ff"
    syntax_comment: str = "#8b949e"
    syntax_function: str = "#d2a8ff"
    syntax_variable: str = "#ffa657"
    syntax_number: str = "#79c0ff"
    syntax_type: str = "#7ee787"
    syntax_operator: str = "#ff7b72"

    # Diff colors
    diff_add: str = "#3fb950"
    diff_add_bg: str = "#0d1117"
    diff_remove: str = "#f85149"
    diff_remove_bg: str = "#0d1117"


# Global theme instance
_opencode_colors = OpenCodeColors()


def opencode_stylesheet(colors: OpenCodeColors = None) -> str:
    """Generate OpenCode stylesheet"""
    c = colors or _opencode_colors
    return f"""
    /* === Global === */
    QWidget {{
        background-color: {c.background};
        color: {c.text};
        font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans SC", sans-serif;
        font-size: 13px;
    }}

    /* === Scrollbar === */
    QScrollBar:vertical {{
        background: {c.surface};
        width: 8px;
        border: none;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c.border};
        border-radius: 4px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c.secondary};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {c.surface};
        height: 8px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {c.border};
        border-radius: 4px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c.secondary};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* === Push Button === */
    QPushButton {{
        background-color: {c.surface_elevated};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {c.border};
        border-color: {c.secondary};
    }}
    QPushButton:pressed {{
        background-color: {c.primary};
        color: {c.background};
        border-color: {c.primary};
    }}
    QPushButton:disabled {{
        background-color: {c.surface};
        color: {c.text_muted};
        border-color: {c.border_muted};
    }}

    /* Primary button */
    QPushButton[class="primary"] {{
        background-color: {c.primary};
        color: {c.background};
        border: none;
        font-weight: bold;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {c.primary_hover};
    }}

    /* === Line Edit === */
    QLineEdit, QTextEdit {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 10px 12px;
        selection-background-color: {c.primary};
        selection-color: {c.background};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {c.primary};
    }}
    QLineEdit::placeholder, QTextEdit::placeholder {{
        color: {c.text_muted};
    }}

    /* === Combo Box === */
    QComboBox {{
        background-color: {c.surface};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QComboBox:hover {{
        border-color: {c.primary};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.surface_elevated};
        color: {c.text};
        border: 1px solid {c.border};
        selection-background-color: {c.primary};
        selection-color: {c.background};
    }}

    /* === Label === */
    QLabel {{
        background: transparent;
        color: {c.text};
    }}

    /* === Frame === */
    QFrame[frameShape="4"] {{ /* HLine */
        color: {c.border};
    }}
    QFrame[frameShape="5"] {{ /* VLine */
        color: {c.border};
    }}

    /* === Menu === */
    QMenu {{
        background-color: {c.surface_elevated};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {c.primary};
    }}

    /* === Tooltip === */
    QToolTip {{
        background-color: {c.surface_elevated};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: 4px;
        padding: 6px 10px;
    }}

    /* === Status Bar === */
    QStatusBar {{
        background-color: {c.surface};
        color: {c.text_muted};
        border-top: 1px solid {c.border};
        font-size: 12px;
    }}

    /* === Check Box === */
    QCheckBox {{
        spacing: 8px;
        color: {c.text};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c.border};
        border-radius: 4px;
        background-color: {c.surface};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c.primary};
        border-color: {c.primary};
    }}

    /* === Tab Widget === */
    QTabWidget::pane {{
        border: 1px solid {c.border};
        background: {c.background};
    }}
    QTabBar::tab {{
        background: {c.surface};
        color: {c.text_muted};
        padding: 8px 16px;
        border: 1px solid {c.border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        background: {c.background};
        color: {c.text};
        border-bottom: 2px solid {c.primary};
    }}
    QTabBar::tab:hover:!selected {{
        background: {c.surface_elevated};
        color: {c.text};
    }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# Thread Management
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Chat History Manager
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Activity Bar (Left Icon Strip)
# ─────────────────────────────────────────────────────────────────────────────

class ActivityBar(QWidget):
    """Left icon strip for panel switching (VS Code / OpenCode style)."""

    panel_requested = pyqtSignal(int)  # panel index

    PANELS = [
        ("Chat", "💬"),
        ("Editor", "📝"),
        ("Files", "📁"),
        ("Pipeline", "⚙️"),
        ("Settings", "⚙️"),
    ]

    def __init__(self, colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.colors = colors or _opencode_colors
        self._active = 0
        self._buttons: List[QToolButton] = []
        self.setFixedWidth(48)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        for i, (name, icon) in enumerate(self.PANELS):
            btn = QToolButton()
            btn.setText(icon)
            btn.setToolTip(name)
            btn.setFixedSize(40, 40)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setFont(QFont("Segoe UI Emoji", 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Theme toggle at bottom
        self.theme_btn = QToolButton()
        self.theme_btn.setText("🌙")
        self.theme_btn.setToolTip("Toggle Theme")
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.theme_btn.setFont(QFont("Segoe UI Emoji", 16))
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.theme_btn)

        self._update_styles()

    def _select(self, index: int):
        self._active = index
        self._update_styles()
        self.panel_requested.emit(index)

    def _update_styles(self):
        c = self.colors
        for i, btn in enumerate(self._buttons):
            if i == self._active:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {c.primary}22;
                        border-left: 2px solid {c.primary};
                        border-radius: 0;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background: transparent;
                        border-left: 2px solid transparent;
                        border-radius: 0;
                    }}
                    QToolButton:hover {{
                        background-color: {c.surface_elevated};
                    }}
                """)


# ─────────────────────────────────────────────────────────────────────────────
# Message Bubble
# ─────────────────────────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """Single message bubble with Markdown rendering."""

    def __init__(self, role: str, content: str = "", colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = ""
        self.colors = colors or _opencode_colors
        self._thinking_visible = False
        self._setup_ui()
        if content:
            self.set_content(content)

    def _setup_ui(self):
        c = self.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Role label
        self.role_label = QLabel("You" if self.role == "user" else "Assistant")
        self.role_label.setStyleSheet(f"font-size: 11px; color: {c.text_muted}; font-weight: bold;")
        layout.addWidget(self.role_label)

        # Content area
        if self.role == "user":
            self.content_label = QLabel()
            self.content_label.setWordWrap(True)
            self.content_label.setStyleSheet(f"font-size: 14px; color: {c.user_text}; padding: 4px 0;")
            self.content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(self.content_label)
            self.setStyleSheet(f"""
                MessageBubble {{
                    background-color: {c.user_bg};
                    border-radius: 12px;
                    border: 1px solid {c.primary};
                }}
            """)
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
            self.setStyleSheet(f"""
                MessageBubble {{
                    background-color: {c.surface};
                    border-radius: 12px;
                    border: 1px solid {c.border_muted};
                }}
            """)

        # Thinking section (collapsible, for assistant only)
        self.thinking_frame = QFrame()
        thinking_layout = QVBoxLayout(self.thinking_frame)
        thinking_layout.setContentsMargins(0, 4, 0, 4)
        thinking_layout.setSpacing(4)

        self.thinking_header = QHBoxLayout()
        self.thinking_toggle = QPushButton("▶ Thinking")
        self.thinking_toggle.setFlat(True)
        self.thinking_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thinking_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {c.warning}; font-size: 11px; font-weight: bold;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                color: {c.text};
            }}
        """)
        self.thinking_toggle.clicked.connect(self._toggle_thinking)
        self.thinking_header.addWidget(self.thinking_toggle)
        self.thinking_header.addStretch()
        thinking_layout.addLayout(self.thinking_header)

        self.thinking_content = QTextEdit()
        self.thinking_content.setReadOnly(True)
        self.thinking_content.setMaximumHeight(160)
        self.thinking_content.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.surface_elevated};
                color: {c.text_muted};
                border: 1px solid {c.border_muted};
                border-radius: 6px;
                font-size: 12px; padding: 8px;
            }}
        """)
        self.thinking_content.setVisible(False)
        thinking_layout.addWidget(self.thinking_content)
        self.thinking_frame.setVisible(False)
        self.thinking_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface_elevated}66;
                border-radius: 8px;
                margin-top: 4px;
            }}
        """)
        layout.addWidget(self.thinking_frame)

        # Tool calls section
        self.tools_frame = QFrame()
        self.tools_layout = QVBoxLayout(self.tools_frame)
        self.tools_layout.setContentsMargins(0, 4, 0, 4)
        self.tools_layout.setSpacing(4)
        self.tools_frame.setVisible(False)
        layout.addWidget(self.tools_frame)

        # Timestamp
        self.time_label = QLabel(datetime.now().strftime("%H:%M"))
        self.time_label.setStyleSheet(f"font-size: 10px; color: {c.text_muted};")
        layout.addWidget(self.time_label)

    def _toggle_thinking(self):
        self._thinking_visible = not self._thinking_visible
        self.thinking_content.setVisible(self._thinking_visible)
        self.thinking_toggle.setText("▼ Thinking" if self._thinking_visible else "▶ Thinking")

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

    def _render_markdown(self, text: str):
        """Simple markdown to HTML rendering"""
        c = self.colors
        html = text

        # Code blocks with syntax highlighting placeholder
        def code_block(match):
            lang = match.group(1) or ""
            code = match.group(2)
            return (f'<pre style="background:{c.surface_elevated};color:{c.text};'
                    f'padding:12px;border-radius:8px;overflow-x:auto;'
                    f'border:1px solid {c.border};font-family:Consolas,monospace;'
                    f'font-size:13px;margin:8px 0;"><code>{code}</code></pre>')

        html = re.sub(r'```(\w*)\n(.*?)```', code_block, html, flags=re.DOTALL)

        # Inline code
        html = re.sub(r'`([^`]+)`',
                      f'<code style="background:{c.surface_elevated};color:{c.syntax_string};'
                      f'padding:2px 6px;border-radius:4px;font-family:Consolas,monospace;'
                      f'font-size:13px;">\\1</code>', html)

        # Bold
        html = re.sub(r'\*\*(.*?)\*\*',
                      f'<b style="color:{c.text_bright};">\\1</b>', html)

        # Italic
        html = re.sub(r'\*(.*?)\*', f'<i>\\1</i>', html)

        # Headers
        html = re.sub(r'^### (.*?)$', f'<h3 style="color:{c.primary};margin:8px 0 4px;">\\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', f'<h2 style="color:{c.primary};margin:12px 0 6px;">\\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', f'<h1 style="color:{c.primary};margin:16px 0 8px;">\\1</h1>', html, flags=re.MULTILINE)

        # Line breaks
        html = html.replace('\n\n', '</p><p style="margin:8px 0;">')
        html = f'<p style="margin:8px 0;">{html}</p>'
        html = html.replace('<p style="margin:8px 0;"></p>', '')

        self.content_view.setHtml(html)

    def set_thinking(self, text: str):
        self.thinking_frame.setVisible(True)
        self.thinking_content.setPlainText(text)

    def append_thinking(self, text: str):
        self.thinking_frame.setVisible(True)
        current = self.thinking_content.toPlainText()
        self.thinking_content.setPlainText(current + text)

    def add_tool_call(self, name: str, result: str = "", success: bool = True, duration_ms: int = 0):
        """Add a tool call to the message"""
        c = self.colors
        self.tools_frame.setVisible(True)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface_elevated};
                border: 1px solid {c.border_muted};
                border-radius: 6px;
                padding: 6px;
                margin: 2px 0;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 4, 8, 4)
        fl.setSpacing(2)

        # Header row
        header = QHBoxLayout()
        status_icon = "✅" if success else "❌"
        status_color = c.success if success else c.error
        icon_label = QLabel(status_icon)
        icon_label.setStyleSheet(f"font-size: 12px;")
        header.addWidget(icon_label)

        name_label = QLabel(f"🔧 {name}")
        name_label.setStyleSheet(f"color: {c.primary}; font-size: 12px; font-weight: bold;")
        header.addWidget(name_label)

        header.addStretch()

        if duration_ms > 0:
            duration_label = QLabel(f"{duration_ms}ms")
            duration_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
            header.addWidget(duration_label)

        fl.addLayout(header)

        if result:
            result_label = QLabel(result[:200] + ("..." if len(result) > 200 else ""))
            result_label.setWordWrap(True)
            result_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px; padding-left: 20px;")
            fl.addWidget(result_label)

        self.tools_layout.addWidget(frame)


# ─────────────────────────────────────────────────────────────────────────────
# Chat Panel
# ─────────────────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """Main chat panel with streaming output and tool call visualization."""

    message_sent = pyqtSignal(str)
    run_code_requested = pyqtSignal(str, str)  # (code, language)

    def __init__(self, colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.colors = colors or _opencode_colors
        self.history = ChatHistoryManager()
        self.current_bubble: Optional[MessageBubble] = None
        self._streaming_timer = None
        self._pending_chunks: List[str] = []
        self._setup_ui()

    def _setup_ui(self):
        c = self.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"background-color: {c.surface}; border-bottom: 1px solid {c.border};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel("💬 Chat")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {c.text_bright};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen3.6:35b", "qwen3.5:4b", "gemma4:26b", "deepseek-r1:70b"])
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c.surface_elevated};
                color: {c.text};
                border: 1px solid {c.border};
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 120px;
            }}
        """)
        header_layout.addWidget(self.model_combo)

        layout.addWidget(header)

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
                background-color: {c.surface};
                border-top: 1px solid {c.border};
            }}
        """)
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)

        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(120)
        self.message_input.setMinimumHeight(40)
        self.message_input.setPlaceholderText(
            "Describe what you want to build or modify...\n\n"
            "Examples:\n"
            "  • Create a user authentication module\n"
            "  • Fix all lint errors in the project\n"
            "  • Run tests and auto-fix failures"
        )
        input_layout.addWidget(self.message_input)

        # Bottom bar: hints + send button
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        hint = QLabel("Ctrl+Enter to send")
        hint.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        bottom_bar.addWidget(hint)

        bottom_bar.addStretch()

        # Run code button
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.success}22;
                color: {c.success};
                border: 1px solid {c.success}44;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c.success}33;
            }}
        """)
        self.run_btn.clicked.connect(self._on_run_clicked)
        bottom_bar.addWidget(self.run_btn)

        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setProperty("class", "primary")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.background};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
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

    def _on_run_clicked(self):
        """Handle run code button click"""
        code = self.message_input.toPlainText().strip()
        if code:
            self.run_code_requested.emit(code, "python")

    def send_message(self):
        text = self.message_input.toPlainText().strip()
        if not text:
            return
        self.message_input.clear()
        self.add_user_message(text)
        self.history.add("user", text)
        self.message_sent.emit(text)

    def add_user_message(self, content: str):
        bubble = MessageBubble("user", content, self.colors)
        self._insert_bubble(bubble)

    def add_assistant_message(self, content: str = ""):
        bubble = MessageBubble("assistant", content, self.colors)
        self.current_bubble = bubble
        self._insert_bubble(bubble)
        return bubble

    def append_stream_chunk(self, chunk: str, char_delay: int = 15):
        """Append chunk with streaming animation"""
        if not self.current_bubble:
            self.add_assistant_message()

        self.current_bubble.append_content(chunk)

        # Auto-scroll
        QTimer.singleShot(10, self._scroll_to_bottom)

    def set_thinking(self, text: str):
        if not self.current_bubble:
            self.add_assistant_message()
        self.current_bubble.set_thinking(text)

    def append_thinking(self, text: str):
        if not self.current_bubble:
            self.add_assistant_message()
        self.current_bubble.append_thinking(text)

    def add_tool_call(self, name: str, result: str = "", success: bool = True, duration_ms: int = 0):
        if self.current_bubble:
            self.current_bubble.add_tool_call(name, result, success, duration_ms)
            QTimer.singleShot(10, self._scroll_to_bottom)

    def finalize_message(self):
        if self.current_bubble:
            self.history.add("assistant", self.current_bubble.content)
        self.current_bubble = None

    def add_welcome(self, message: str):
        bubble = MessageBubble("assistant", message, self.colors)
        self._insert_bubble(bubble)

    def _insert_bubble(self, bubble: MessageBubble):
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        QTimer.singleShot(20, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_chat(self):
        """Clear all messages"""
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.history.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Code Editor Panel
# ─────────────────────────────────────────────────────────────────────────────

class EditorPanel(QWidget):
    """Tabbed code editor panel"""

    file_saved = pyqtSignal(str)
    file_opened = pyqtSignal(str)

    def __init__(self, colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.colors = colors or _opencode_colors
        self._tabs: Dict[str, QWidget] = {}
        self._current_lang = "python"
        self._setup_ui()

    def _setup_ui(self):
        c = self.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"background-color: {c.surface}; border-bottom: 1px solid {c.border};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("📝 Editor")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c.text_bright};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Language selector
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "JavaScript", "TypeScript", "HTML", "CSS", "JSON", "Markdown"])
        self.lang_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c.surface_elevated};
                color: {c.text};
                border: 1px solid {c.border};
                border-radius: 4px;
                padding: 4px 8px;
            }}
        """)
        self.lang_combo.currentTextChanged.connect(self._on_lang_changed)
        header_layout.addWidget(self.lang_combo)

        # Action buttons
        for icon, tooltip, callback in [
            ("💾", "Save", self._save_current),
            ("▶", "Run", self._run_current),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {c.surface_elevated};
                }}
            """)
            header_layout.addWidget(btn)

        layout.addWidget(header)

        # Tab bar
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {c.background};
            }}
            QTabBar::tab {{
                background: {c.surface};
                color: {c.text_muted};
                padding: 6px 12px;
                border: none;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: {c.background};
                color: {c.text};
                border-bottom: 2px solid {c.primary};
            }}
            QTabBar::tab:hover:!selected {{
                background: {c.surface_elevated};
            }}
        """)

        # Empty state
        self._empty_state()
        layout.addWidget(self.tab_widget, 1)

        # Status bar
        self.status_bar = QLabel("Ln 1, Col 1 | UTF-8 | Python")
        self.status_bar.setStyleSheet(f"""
            QLabel {{
                background-color: {c.surface};
                color: {c.text_muted};
                border-top: 1px solid {c.border};
                padding: 4px 12px;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.status_bar)

    def _empty_state(self):
        """Show empty state widget"""
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("📄")
        icon.setFont(QFont("Segoe UI Emoji", 48))
        icon.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(icon)

        text = QLabel("No file open")
        text.setStyleSheet(f"color: {c.text_muted}; font-size: 14px;")
        layout.addWidget(text)

        hint = QLabel("Start a conversation to generate code")
        hint.setStyleSheet(f"color: {c.border}; font-size: 12px;")
        layout.addWidget(hint)

        self.tab_widget.addTab(empty, "")
        # Hide close button
        close_btn = self.tab_widget.tabBar().tabButton(0, QTabWidget.TabButtonPosition.RightSide)
        if close_btn:
            close_btn.hide()

    def _on_lang_changed(self, lang: str):
        self._current_lang = lang.lower()
        self._update_status()

    def _update_status(self):
        """Update status bar"""
        c = self.colors
        self.status_bar.setText(
            f"Ln 1, Col 1 | UTF-8 | {self._current_lang.capitalize()}"
        )

    def open_file(self, file_path: str, content: str = ""):
        """Open a file in a new tab"""
        c = self.colors

        # Check if already open
        if file_path in self._tabs:
            idx = self.tab_widget.indexOf(self._tabs[file_path])
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
            return

        # Create editor tab
        tab = QWidget()
        tab.file_path = file_path
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        lang_label = QLabel(self._get_lang_display(file_path))
        lang_label.setStyleSheet(f"""
            font-size: 11px; color: {c.primary};
            background: {c.primary}22;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        toolbar.addWidget(lang_label)
        toolbar.addStretch()

        cursor_label = QLabel("Ln 1, Col 1")
        cursor_label.setStyleSheet(f"font-size: 11px; color: {c.text_muted};")
        cursor_label.setObjectName("cursor_info")
        toolbar.addWidget(cursor_label)
        layout.addLayout(toolbar)

        # Code editor
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setFont(QFont("Consolas", 13))
        editor.setTabStopDistance(QFontMetricsF(editor.font()).horizontalAdvance(' ') * 4)
        editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.background};
                color: {c.text};
                border: none;
                padding: 8px;
                font-family: Consolas, monospace;
                font-size: 13px;
            }}
        """)
        if content:
            editor.setPlainText(content)
        layout.addWidget(editor)

        # Connect cursor position
        editor.cursorPositionChanged.connect(lambda: self._update_cursor(tab, editor))

        self._tabs[file_path] = tab
        self.tab_widget.addTab(tab, os.path.basename(file_path))

        # Remove empty state if present
        if self.tab_widget.count() > 1:
            empty_idx = self.tab_widget.indexOf(self.tab_widget.widget(0))
            if empty_idx >= 0 and self.tab_widget.widget(empty_idx).layout().count() == 3:
                self.tab_widget.removeTab(empty_idx)

        self.tab_widget.setCurrentWidget(tab)
        self.file_opened.emit(file_path)

    def _get_lang_display(self, file_path: str) -> str:
        """Get language display name from file path"""
        ext = os.path.splitext(file_path)[1].lower()
        lang_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".html": "HTML", ".css": "CSS", ".json": "JSON",
            ".md": "Markdown", ".yaml": "YAML", ".yml": "YAML",
        }
        return lang_map.get(ext, ext.upper() if ext else "Text")

    def _update_cursor(self, tab: QWidget, editor: QTextEdit):
        """Update cursor position label"""
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1

        # Find cursor label in toolbar
        for child in tab.findChildren(QLabel):
            if child.objectName() == "cursor_info":
                child.setText(f"Ln {line}, Col {col}")
                break

    def set_content(self, content: str, language: str = "python"):
        """Set content in current editor"""
        current = self.tab_widget.currentWidget()
        if current and hasattr(current, 'layout'):
            for child in current.findChildren(QTextEdit):
                child.setPlainText(content)
                break

    def get_current_content(self) -> str:
        """Get content from current editor"""
        current = self.tab_widget.currentWidget()
        if current and hasattr(current, 'layout'):
            for child in current.findChildren(QTextEdit):
                return child.toPlainText()
        return ""

    def _save_current(self):
        """Save current file"""
        current = self.tab_widget.currentWidget()
        if current and hasattr(current, 'file_path'):
            # Emit signal for parent to handle
            self.file_saved.emit(current.file_path)

    def _run_current(self):
        """Run current code"""
        content = self.get_current_content()
        if content:
            self.run_code_requested.emit(content, self._current_lang)

    def _close_tab(self, index: int):
        """Close a tab"""
        widget = self.tab_widget.widget(index)
        if hasattr(widget, 'file_path'):
            self._tabs.pop(widget.file_path, None)
        self.tab_widget.removeTab(index)

        # Show empty state if no tabs
        if self.tab_widget.count() == 0:
            self._empty_state()

    run_code_requested = pyqtSignal(str, str)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Progress Widget
# ─────────────────────────────────────────────────────────────────────────────

class PipelineProgress(QWidget):
    """CodeTool v3 pipeline visualization"""

    def __init__(self, colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.colors = colors or _opencode_colors
        self._steps: Dict[str, Dict] = {}
        self._setup_ui()

    def _setup_ui(self):
        c = self.colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("⚙️ CodeTool Pipeline")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {c.text_bright};")
        layout.addWidget(title)

        # Steps
        steps = [
            ("write", "✏️", "Auto-Write", "LLM planning → code generation"),
            ("test", "🧪", "Auto-Test", "pytest → auto-fix loop"),
            ("fix", "🔧", "Auto-Fix", "LSP diagnostics → LLM repair"),
            ("publish", "🚀", "Auto-Publish", "git commit/push → CI/CD"),
        ]

        for step_id, icon, name, desc in steps:
            frame = self._create_step(step_id, icon, name, desc)
            self._steps[step_id] = {"frame": frame, "status": "pending"}
            layout.addWidget(frame)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {c.border}; margin: 8px 0;")
        layout.addWidget(sep)

        # Actions
        actions_layout = QHBoxLayout()

        for label, callback in [
            ("Scan", self._on_scan),
            ("Plan", self._on_plan),
            ("Run", self._on_run),
        ]:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.surface_elevated};
                    color: {c.text};
                    border: 1px solid {c.border};
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{
                    background-color: {c.border};
                }}
            """)
            actions_layout.addWidget(btn)

        layout.addLayout(actions_layout)

        # Log area
        log_label = QLabel("📜 Log")
        log_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(log_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background: {c.background};
                color: {c.text_muted};
                border: 1px solid {c.border_muted};
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.log_view)

        layout.addStretch()

    def _create_step(self, step_id: str, icon: str, name: str, desc: str) -> QFrame:
        c = self.colors
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {c.surface_elevated};
                border: 1px solid {c.border_muted};
                border-radius: 8px;
            }}
        """)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(4)

        row = QHBoxLayout()
        status_icon = QLabel("⬜")
        status_icon.setStyleSheet(f"font-size: 14px;")
        row.addWidget(status_icon)

        name_label = QLabel(f"{icon} {name}")
        name_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c.text};")
        row.addWidget(name_label)
        row.addStretch()
        fl.addLayout(row)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet(f"font-size: 11px; color: {c.text_muted};")
        fl.addWidget(desc_label)

        # Store references
        frame._status_icon = status_icon
        frame._desc_label = desc_label
        frame._step_id = step_id

        return frame

    def set_step_status(self, step_id: str, status: str, detail: str = ""):
        """Update step status: pending, running, success, error"""
        if step_id not in self._steps:
            return

        c = self.colors
        step = self._steps[step_id]
        frame = step["frame"]

        icons = {
            "pending": "⬜",
            "running": "🔄",
            "success": "✅",
            "error": "❌",
        }
        colors_map = {
            "pending": c.text_muted,
            "running": c.warning,
            "success": c.success,
            "error": c.error,
        }

        frame._status_icon.setText(icons.get(status, "⬜"))
        frame._status_icon.setStyleSheet(f"font-size: 14px;")

        if detail:
            frame._desc_label.setText(detail)
            frame._desc_label.setStyleSheet(f"font-size: 11px; color: {colors_map.get(status, c.text_muted)};")

        step["status"] = status

    def append_log(self, message: str):
        """Append log message"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")

    def clear_pipeline(self):
        """Reset all steps"""
        for step_id in self._steps:
            self.set_step_status(step_id, "pending")

    def _on_scan(self):
        self.append_log("📊 Scanning project...")

    def _on_plan(self):
        self.append_log("📋 Generating plan...")

    def _on_run(self):
        self.append_log("🚀 Starting pipeline...")


# ─────────────────────────────────────────────────────────────────────────────
# Status Bar
# ─────────────────────────────────────────────────────────────────────────────

class IDEStatusBar(QWidget):
    """Bottom status bar with model info and diagnostics"""

    def __init__(self, colors: OpenCodeColors = None, parent=None):
        super().__init__(parent)
        self.colors = colors or _opencode_colors
        self._setup_ui()

    def _setup_ui(self):
        c = self.colors
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(16)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c.surface};
                border-top: 1px solid {c.border};
            }}
        """)

        # Connection status
        self.conn_dot = QLabel("●")
        self.conn_dot.setStyleSheet(f"color: {c.success}; font-size: 12px;")
        layout.addWidget(self.conn_dot)

        self.conn_label = QLabel("Connected")
        self.conn_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.conn_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {c.border};")
        layout.addWidget(sep)

        # Model info
        self.model_label = QLabel("Model: qwen3.6:35b")
        self.model_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.model_label)

        layout.addStretch()

        # Diagnostics
        self.diag_label = QLabel("✓ No issues")
        self.diag_label.setStyleSheet(f"color: {c.success}; font-size: 11px;")
        layout.addWidget(self.diag_label)

        # Token count (optional)
        self.token_label = QLabel("")
        self.token_label.setStyleSheet(f"color: {c.text_muted}; font-size: 11px;")
        layout.addWidget(self.token_label)

        self.setFixedHeight(28)

    def update_connection(self, status: str, color: str = None):
        """Update connection status"""
        c = self.colors
        color = color or (c.success if status == "connected" else c.error)
        self.conn_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.conn_label.setText(status.capitalize())
        self.conn_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def update_model(self, model_name: str):
        self.model_label.setText(f"Model: {model_name}")

    def update_diagnostics(self, count: int):
        c = self.colors
        if count > 0:
            self.diag_label.setText(f"⚠ {count} issues")
            self.diag_label.setStyleSheet(f"color: {c.warning}; font-size: 11px;")
        else:
            self.diag_label.setText("✓ No issues")
            self.diag_label.setStyleSheet(f"color: {c.success}; font-size: 11px;")

    def update_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        if input_tokens > 0 or output_tokens > 0:
            total = input_tokens + output_tokens
            self.token_label.setText(f"📊 {input_tokens} in / {output_tokens} out / {total} total")
        else:
            self.token_label.setText("")


# ─────────────────────────────────────────────────────────────────────────────
# Main OpenCode IDE Panel
# ─────────────────────────────────────────────────────────────────────────────

class OpenCodeIDEPanel(QWidget):
    """
    OpenCode-inspired IDE Panel

    Features:
    - Chat-first design (AI conversation as primary interface)
    - Split-panel layout: Chat (left) | Editor (right)
    - Activity bar for panel switching
    - Streaming output with Markdown rendering
    - Tool call timeline visualization
    - CodeTool v3 pipeline integration
    - OpenCode dark theme (GitHub Dark style)
    """

    def __init__(self, parent=None, project_path: str = None):
        super().__init__(parent)
        self.project_path = project_path or os.getcwd()
        self.colors = _opencode_colors
        self.thread_manager = ThreadManager()

        # Initialize IDE Agent (lazy)
        self.ide_agent = None
        self._init_agent()

        # Build UI
        self._setup_ui()
        self._apply_styles()

        # Welcome message
        self._add_welcome()

    def _init_agent(self):
        """Initialize IDE agent with fallback"""
        try:
            from client.src.business.ide_agent import IDEAgent
            self.ide_agent = IDEAgent()
        except Exception as e:
            print(f"[OpenCodeIDE] IDE Agent init failed: {e}")
            self.ide_agent = None

    def _setup_ui(self):
        """Build the main IDE layout"""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Main horizontal splitter
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Activity bar (left)
        self.activity_bar = ActivityBar(self.colors)
        self.h_splitter.addWidget(self.activity_bar)

        # Content area
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Chat panel (left, takes 60%)
        self.chat_panel = ChatPanel(self.colors)
        self.chat_panel.message_sent.connect(self._handle_user_message)
        self.content_splitter.addWidget(self.chat_panel)

        # Editor panel (right, takes 40%)
        self.editor_panel = EditorPanel(self.colors)
        self.content_splitter.addWidget(self.editor_panel)

        # Set splitter ratios
        self.content_splitter.setStretchFactor(0, 6)
        self.content_splitter.setStretchFactor(1, 4)
        self.content_splitter.setSizes([600, 400])

        self.h_splitter.addWidget(self.content_splitter)
        self.h_splitter.setStretchFactor(0, 0)  # Activity bar fixed
        self.h_splitter.setStretchFactor(1, 1)  # Content flexible

        self._main_layout.addWidget(self.h_splitter, 1)

        # Status bar
        self.status_bar = IDEStatusBar(self.colors)
        self._main_layout.addWidget(self.status_bar)

        # Connect signals
        self.activity_bar.panel_requested.connect(self._switch_panel)

    def _apply_styles(self):
        """Apply OpenCode stylesheet"""
        self.setStyleSheet(opencode_stylesheet(self.colors))

    def _switch_panel(self, index: int):
        """Switch visible panel based on activity bar selection"""
        # 0 = Chat (show chat)
        # 1 = Editor (show editor)
        # 2 = Files
        # 3 = Pipeline
        if index == 0:
            self.content_splitter.setSizes([600, 400])
        elif index == 1:
            self.content_splitter.setSizes([0, 1000])  # Maximize editor
        elif index == 2:
            self.content_splitter.setSizes([400, 600])  # Balance view
        elif index == 3:
            self.content_splitter.setSizes([600, 400])  # Default

    def _add_welcome(self):
        """Add welcome message"""
        welcome = (
            "# 🛠️ OpenCode IDE\n\n"
            "Chat-driven development environment\n\n"
            "## What I can do\n\n"
            "• **Generate code** - Describe what you want, I'll create it\n"
            "• **Modify code** - Ask me to update existing files\n"
            "• **Run & test** - Execute code and fix issues\n"
            "• **Plan & design** - Generate implementation plans\n"
            "• **Debug** - Find and fix bugs automatically\n\n"
            "## Quick start\n\n"
            "1. Type your request in the chat box below\n"
            "2. Press Ctrl+Enter or click Send\n"
            "3. Watch the streaming response with tool calls\n"
            "4. Generated code appears in the editor panel\n\n"
            "## Examples\n\n"
            "• \"Create a REST API endpoint for user authentication\"\n"
            "• \"Add error handling to this function\"\n"
            "• \"Run the tests and fix any failures\"\n"
            "• \"Explain what this code does\"\n"
        )
        self.chat_panel.add_welcome(welcome)

    # ── Message Handling ──

    def _handle_user_message(self, message: str):
        """Handle user message from chat"""
        if not self.ide_agent:
            self.chat_panel.append_stream_chunk(
                "\n⚠️ IDE Agent not available. Check dependencies."
            )
            self.chat_panel.finalize_message()
            return

        self.chat_panel.add_assistant_message()

        # Create worker thread
        worker = IDETalkWorker(
            self.ide_agent, message,
            context={"project_path": self.project_path}
        )
        worker.chunk_received.connect(self.chat_panel.append_stream_chunk)
        worker.thinking_received.connect(self.chat_panel.append_thinking)
        worker.tool_start.connect(self._on_tool_start)
        worker.tool_result.connect(self._on_tool_result)
        worker.finished.connect(self._on_chat_finished)
        worker.error_occurred.connect(self._on_chat_error)
        worker.code_generated.connect(self._on_code_generated)
        self.thread_manager.submit(worker, f"talk-{time.time()}")

    def _on_tool_start(self, name: str, params: str):
        self.chat_panel.add_tool_call(name, params, True)

    def _on_tool_result(self, name: str, result: str, success: bool, duration_ms: int):
        self.chat_panel.add_tool_call(name, result, success, duration_ms)

    def _on_chat_finished(self, content: str):
        self.chat_panel.finalize_message()

    def _on_chat_error(self, error_msg: str):
        self.chat_panel.append_stream_chunk(f"\n❌ Error: {error_msg}")
        self.chat_panel.finalize_message()

    def _on_code_generated(self, file_path: str, code: str):
        """Handle generated code"""
        if file_path:
            self.editor_panel.open_file(file_path, code)
        elif code:
            self.editor_panel.set_content(code)

    def cleanup(self):
        """Clean up resources on close"""
        self.thread_manager.cancel_all()


# ─────────────────────────────────────────────────────────────────────────────
# IDE Talk Worker Thread
# ─────────────────────────────────────────────────────────────────────────────

class IDETalkWorker(QThread):
    """Background thread for AI chat processing with streaming."""

    chunk_received = pyqtSignal(str)
    thinking_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    code_generated = pyqtSignal(str, str)
    tool_start = pyqtSignal(str, str)
    tool_result = pyqtSignal(str, str, bool, int)

    def __init__(self, agent, message: str, context: Dict = None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context or {}
        self._stop_requested = False

    def run(self):
        try:
            full_content = ""
            tool_times: Dict[str, int] = {}

            def on_delta(delta: str):
                nonlocal full_content
                if self._stop_requested:
                    return
                full_content += delta
                self.chunk_received.emit(delta)

            def on_thinking(text: str):
                if self._stop_requested:
                    return
                self.thinking_received.emit(text)

            def on_tool_start(name: str, params: str):
                if self._stop_requested:
                    return
                tool_times[name] = int(time.time() * 1000)
                self.tool_start.emit(name, params)

            def on_tool_result(name: str, result: str, success: bool):
                if self._stop_requested:
                    return
                duration = tool_times.get(name, 0)
                if duration:
                    duration = int(time.time() * 1000) - duration
                self.tool_result.emit(name, result, success, duration)

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

            self.finished.emit(full_content or response.get("message", ""))

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"{str(e)}\n{traceback.format_exc()}")

    def stop(self):
        self._stop_requested = True


# ─────────────────────────────────────────────────────────────────────────────
# Standalone Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Apply dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(13, 17, 23))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(201, 209, 217))
    palette.setColor(QPalette.ColorRole.Base, QColor(22, 27, 34))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(28, 33, 40))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(22, 27, 34))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(201, 209, 217))
    palette.setColor(QPalette.ColorRole.Text, QColor(201, 209, 217))
    palette.setColor(QPalette.ColorRole.Button, QColor(28, 33, 40))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(201, 209, 217))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(240, 246, 252))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(88, 166, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(13, 17, 23))
    app.setPalette(palette)

    panel = OpenCodeIDEPanel()
    panel.setWindowTitle("OpenCode IDE")
    panel.resize(1200, 800)
    panel.show()
    sys.exit(app.exec())
