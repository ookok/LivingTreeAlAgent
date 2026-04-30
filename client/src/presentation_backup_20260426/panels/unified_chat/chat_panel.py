"""
统一聊天 PyQt6 UI 面板 - Chat Panel

Element/Discord/Telegram 风格的三栏自适应布局:

┌────────────┬─────────────────────────┬──────────────┐
│  会话列表   │       消息区域           │   信息面板    │
│            │                         │              │
│ [会话1]    │  💬 消息气泡              │  用户详情    │
│ [会话2]    │  💬 消息气泡             │  网络诊断    │
│ [会话3]    │  📎 文件卡片             │  传输进度    │
│            │  🔗 链接预览             │  通话状态    │
│            │                         │              │
│            │  ─────────────────────  │              │
│            │  [输入框] [发送] [附件]  │              │
├────────────┴─────────────────────────┴──────────────┤
│              状态栏 (网络/质量/CPU/内存)              │
└─────────────────────────────────────────────────────┘

功能:
1. 三栏自适应布局 (可通过拖拽调整宽度)
2. 统一消息气泡 (文本/文件/链接/语音/视频)
3. 链接预览卡片 (Telegram 风格)
4. 状态监控栏 (底部)
5. 联系人在线状态
6. 消息搜索
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QSizePolicy,
    QLineEdit, QToolButton, QMenu, QInputDialog,
    QDialog, QDialogButtonBox, QProgressBar, QSlider,
    QStatusBar, QGraphicsView, QGraphicsScene
)
from PyQt6.QtCore import (
    Qt, QSize, QRect, QTimer, QPropertyAnimation,
    pyqtSignal, QPoint, QMimeData
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QTextCursor, QPainter,
    QTextDocument, QTextCharFormat, QBrush, QPen,
    QIcon, QAction, QTextFrameFormat, QImage, QPixmap
)

# 导入统一聊天核心
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from .business.unified_chat import (
    get_chat_hub, UnifiedMessage, ChatSession, PeerInfo,
    MessageType, MessageStatus, SessionType, OnlineStatus,
    ChannelType, MESSAGE_TYPE_ICONS, STATUS_ICONS,
    FileMeta, LinkPreview, NetworkStatus
)

# 导入语音消息组件
from .voice_message import (
    VoiceBubble, VoiceRecorder, VoicePlayer,
    RecordButton, RecordingIndicator, WaveformWidget,
    create_voice_message, get_voice_duration
)


# ============ 样式定义 ============

CHAT_STYLE = """
/* 主布局 */
QWidget#chat_panel {
    background-color: #1a1a2e;
    color: #e0e0e0;
}

/* 分割器 */
QSplitter::handle {
    background-color: #2d2d44;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}

/* 会话列表 */
#session_list {
    background-color: #16162a;
    border: none;
    outline: none;
}
#session_list::item {
    padding: 12px 10px;
    border-bottom: 1px solid #1f1f3a;
}
#session_list::item:selected {
    background-color: #2d2d44;
}
#session_list::item:hover {
    background-color: #1f1f35;
}

/* 消息区域 */
#message_area {
    background-color: #1a1a2e;
    border: none;
}

/* 消息气泡 - 发送 */
.message-outgoing {
    background-color: #2563eb;
    border-radius: 16px 16px 4px 16px;
    padding: 10px 14px;
    margin: 4px 60px 4px 20px;
    max-width: 70%;
}
.message-outgoing QLabel {
    color: white;
}

/* 消息气泡 - 接收 */
.message-incoming {
    background-color: #2d2d44;
    border-radius: 16px 16px 16px 4px;
    padding: 10px 14px;
    margin: 4px 20px 4px 60px;
    max-width: 70%;
}
.message-incoming QLabel {
    color: #e0e0e0;
}

/* 系统消息 */
.message-system {
    background-color: transparent;
    border: none;
    padding: 4px;
    margin: 4px auto;
    max-width: 80%;
}
.message-system QLabel {
    color: #888;
    font-size: 12px;
}

/* 文件消息卡片 */
.file-card {
    background-color: #2d2d44;
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 200px;
}
.file-card:hover {
    background-color: #3d3d54;
}

/* 链接预览卡片 */
.link-preview-card {
    background-color: #1f1f35;
    border-radius: 8px;
    padding: 0;
    margin: 4px 0;
    max-width: 350px;
}
.link-preview-card QLabel {
    color: #e0e0e0;
}

/* 输入框 */
#message_input {
    background-color: #2d2d44;
    border: 1px solid #3d3d54;
    border-radius: 20px;
    padding: 10px 16px;
    color: white;
    font-size: 14px;
}
#message_input:focus {
    border-color: #2563eb;
}

/* 按钮 */
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 8px 16px;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #4b5563;
    color: #9ca3af;
}

/* 工具按钮 */
QToolButton {
    background-color: transparent;
    border: none;
    padding: 8px;
    border-radius: 8px;
}
QToolButton:hover {
    background-color: #2d2d44;
}

/* 状态栏 */
#status_bar {
    background-color: #16162a;
    border-top: 1px solid #2d2d44;
    padding: 4px 12px;
    font-size: 12px;
    color: #888;
}
#status_bar QLabel {
    color: #888;
}

/* 头像 */
.avatar {
    border-radius: 20px;
    background-color: #2563eb;
}
.avatar-online {
    border: 2px solid #22c55e;
}
.avatar-offline {
    border: 2px solid #6b7280;
}

/* 未读徽章 */
.unread-badge {
    background-color: #ef4444;
    border-radius: 10px;
    min-width: 20px;
    padding: 2px 6px;
    font-size: 11px;
    color: white;
}

/* 在线状态指示 */
.online-indicator {
    border-radius: 5px;
}
.online-indicator-online { background-color: #22c55e; }
.online-indicator-offline { background-color: #6b7280; }
.online-indicator-away { background-color: #eab308; }
.online-indicator-busy { background-color: #ef4444; }

/* 信息面板 */
#info_panel {
    background-color: #16162a;
    border-left: 1px solid #2d2d44;
}

/* 标签 */
QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: white;
}
QLabel#subtitle {
    font-size: 12px;
    color: #888;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #3d3d54;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4d4d64;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


# ============ 文件卡片组件 ============

# 文件类型图标映射
FILE_TYPE_ICONS = {
    # 文档
    '.pdf': '📄', '.doc': '📝', '.docx': '📝', '.txt': '📃', '.md': '📋',
    '.rtf': '📃', '.odt': '📃', '.tex': '📋', '.epub': '📚',
    # 表格
    '.xls': '📊', '.xlsx': '📊', '.csv': '📊', '.tsv': '📊', '.ods': '📊',
    # 演示
    '.ppt': '🎨', '.pptx': '🎨', '.odp': '🎨', '.key': '🎨',
    # 代码
    '.py': '🐍', '.js': '🌐', '.java': '☕', '.cpp': '⚙️', '.c': '⚙️',
    '.h': '⚙️', '.cs': '💜', '.go': '🔵', '.rs': '🦀', '.rb': '💎',
    '.php': '🐘', '.swift': '🍎', '.kt': '🤖', '.ts': '🌐',
    '.jsx': '⚛️', '.tsx': '⚛️', '.vue': '💚', '.html': '🌐', '.css': '🎨',
    '.scss': '🎨', '.sass': '🎨', '.less': '🎨',
    # 配置
    '.json': '⚙️', '.yml': '⚙️', '.yaml': '⚙️', '.toml': '⚙️',
    '.ini': '⚙️', '.cfg': '⚙️', '.conf': '⚙️', '.env': '🔐', '.gitignore': '📁',
    # 数据
    '.db': '💾', '.sqlite': '💾', '.sqlite3': '💾', '.parquet': '📦',
    '.arrow': '📦', '.feather': '📦', '.pkl': '📦', '.pickle': '📦',
    # 图片
    '.png': '🖼️', '.jpg': '🖼️', '.jpeg': '🖼️', '.gif': '🎞️', '.svg': '📈',
    '.bmp': '🖼️', '.ico': '🖼️', '.tiff': '🖼️', '.webp': '🖼️',
    # 媒体
    '.mp3': '🎵', '.wav': '🎵', '.flac': '🎵', '.aac': '🎵', '.ogg': '🎵',
    '.mp4': '🎬', '.avi': '🎬', '.mkv': '🎬', '.mov': '🎬', '.wmv': '🎬',
    '.webm': '🎬', '.m4v': '🎬',
    # 压缩
    '.zip': '📦', '.rar': '📦', '.7z': '📦', '.tar': '📦', '.gz': '📦',
    '.bz2': '📦', '.xz': '📦',
    # 可执行
    '.exe': '🔧', '.msi': '🔧', '.bat': '🔧', '.sh': '🔧', '.bash': '🔧',
    '.cmd': '🔧', '.ps1': '🔧', '.app': '🍎', '.dmg': '🍎',
    # 其他
    '.log': '📋', '.out': '📋', '.xml': '📄', '.sql': '🗃️',
    '.pptx': '🎨', '.msg': '📧', '.eml': '📧',
}

# 文件类型分组
FILE_CATEGORY_GROUPS = {
    '📁 文档文件': ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt', '.tex', '.epub'],
    '📊 表格文件': ['.xls', '.xlsx', '.csv', '.tsv', '.ods'],
    '🎨 演示文件': ['.ppt', '.pptx', '.odp', '.key'],
    '🐍 代码文件': ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.ts', '.jsx', '.tsx', '.vue', '.html', '.css', '.scss', '.sass', '.less'],
    '⚙️ 配置文件': ['.json', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf', '.env', '.gitignore'],
    '💾 数据文件': ['.db', '.sqlite', '.sqlite3', '.parquet', '.arrow', '.feather', '.pkl', '.pickle'],
    '🖼️ 图片文件': ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.ico', '.tiff', '.webp'],
    '🎵 音频文件': ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
    '🎬 视频文件': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.webm', '.m4v'],
    '📦 压缩文件': ['.zip', '.rar', '7z', '.tar', '.gz', '.bz2', '.xz'],
    '🔧 可执行文件': ['.exe', '.msi', '.bat', '.sh', '.bash', '.cmd', '.ps1', '.app', '.dmg'],
}


def get_file_icon(file_name: str) -> str:
    """根据文件名获取文件图标"""
    ext = Path(file_name).suffix.lower()
    return FILE_TYPE_ICONS.get(ext, '📄')


def get_file_category(file_name: str) -> str:
    """根据文件名获取文件类别"""
    ext = Path(file_name).suffix.lower()
    for category, extensions in FILE_CATEGORY_GROUPS.items():
        if ext in extensions:
            return category
    return '📄 其他文件'


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class FileCard(QFrame):
    """
    文件卡片组件 - 智能文件展示与操作

    支持功能:
    - 文件图标自动识别
    - 文件大小显示
    - 多种操作按钮 (打开/在文件夹中显示/复制路径)
    - 点击文件名打开文件
    - 悬停高亮效果
    - 可配置的操作按钮
    """

    # 文件打开信号
    file_open_requested = pyqtSignal(str, str)  # file_path, operation
    file_operation_requested = pyqtSignal(str, str, dict)  # file_path, operation, params

    def __init__(
        self,
        file_path: str,
        file_name: str = "",
        file_size: int = 0,
        mime_type: str = "",
        operations: list = None,
        parent=None
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = file_name or Path(file_path).name
        self.file_size = file_size
        self.mime_type = mime_type
        self.operations = operations or ["open", "show_in_folder", "copy_path"]
        self.is_processing = False

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """设置UI"""
        # 主卡片样式
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border-radius: 8px;
                padding: 4px;
                margin: 4px 0;
            }
            QFrame:hover {
                background-color: #3d3d54;
            }
            QFrame#file_card_container {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
        """)
        self.setMinimumWidth(200)
        self.setMaximumWidth(350)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(10)

        # 文件图标
        icon_label = QLabel()
        icon_label.setText(get_file_icon(self.file_name))
        icon_label.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(icon_label)

        # 文件信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        # 文件名 (可点击)
        self.name_label = QLabel()
        self.name_label.setText(self.file_name)
        self.name_label.setStyleSheet("""
            color: #e0e0e0;
            font-size: 13px;
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        self.name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.name_label.mousePressEvent = lambda e: self._on_file_click()
        info_layout.addWidget(self.name_label)

        # 文件大小
        if self.file_size > 0:
            size_label = QLabel()
            size_label.setText(format_file_size(self.file_size))
            size_label.setStyleSheet("color: #888; font-size: 11px; background: transparent; border: none;")
            info_layout.addWidget(size_label)

        main_layout.addLayout(info_layout)

        # 操作按钮区域
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(4)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        # 根据配置显示操作按钮
        if "open" in self.operations:
            self._add_action_button(actions_layout, "📂", "打开", "open")
        if "show_in_folder" in self.operations:
            self._add_action_button(actions_layout, "📁", "文件夹", "show_in_folder")
        if "copy_path" in self.operations:
            self._add_action_button(actions_layout, "📋", "复制", "copy_path")
        if "run" in self.operations and self._is_executable():
            self._add_action_button(actions_layout, "▶️", "运行", "run")
        if "edit" in self.operations and self._is_editable():
            self._add_action_button(actions_layout, "✏️", "编辑", "edit")
        if "preview" in self.operations and self._is_previewable():
            self._add_action_button(actions_layout, "👁️", "预览", "preview")

        main_layout.addLayout(actions_layout)

        # 处理中指示器 (默认隐藏)
        self.processing_label = QLabel("⏳")
        self.processing_label.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        self.processing_label.setFixedSize(20, 20)
        self.processing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processing_label.setVisible(False)
        main_layout.addWidget(self.processing_label)

    def _add_action_button(self, layout, icon: str, tooltip: str, operation: str):
        """添加操作按钮"""
        btn = QPushButton()
        btn.setText(icon)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        btn.setToolTip(tooltip)
        btn.clicked.connect(lambda: self._on_operation_click(operation))
        layout.addWidget(btn)

    def _is_executable(self) -> bool:
        """检查是否为可执行文件"""
        ext = Path(self.file_path).suffix.lower()
        return ext in ['.py', '.sh', '.bat', '.cmd', '.ps1', '.js']

    def _is_editable(self) -> bool:
        """检查是否为可编辑文件"""
        ext = Path(self.file_path).suffix.lower()
        editable_exts = ['.txt', '.md', '.json', '.yml', '.yaml', '.xml', '.html',
                        '.css', '.js', '.py', '.java', '.c', '.cpp', '.h', '.cs',
                        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.ts', '.log']
        return ext in editable_exts

    def _is_previewable(self) -> bool:
        """检查是否为可预览文件"""
        ext = Path(self.file_path).suffix.lower()
        previewable_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp',
                           '.mp3', '.wav', '.mp4', '.pdf', '.txt', '.md', '.json']
        return ext in previewable_exts

    def connect_signals(self):
        """连接信号"""
        pass

    def _on_file_click(self):
        """文件名点击 - 打开文件"""
        self._show_processing()
        self.file_open_requested.emit(self.file_path, "open")
        QTimer.singleShot(1000, self._hide_processing)

    def _on_operation_click(self, operation: str):
        """操作按钮点击"""
        self._show_processing()

        if operation == "open":
            self.file_open_requested.emit(self.file_path, "open")
        elif operation == "show_in_folder":
            self._show_in_folder()
        elif operation == "copy_path":
            self._copy_path()
        elif operation == "run":
            self.file_operation_requested.emit(self.file_path, "run", {})
        elif operation == "edit":
            self.file_operation_requested.emit(self.file_path, "edit", {})
        elif operation == "preview":
            self.file_operation_requested.emit(self.file_path, "preview", {})

        QTimer.singleShot(500, self._hide_processing)

    def _show_in_folder(self):
        """在文件夹中显示"""
        import platform
        import subprocess

        file_path = Path(self.file_path)
        if not file_path.exists():
            return

        folder = file_path.parent

        try:
            if platform.system() == "Windows":
                subprocess.run(['explorer', '/select,', str(file_path)])
            elif platform.system() == "Darwin":
                subprocess.run(['open', '-R', str(file_path)])
            else:
                subprocess.run(['xdg-open', str(folder)])
        except Exception:
            pass

    def _copy_path(self):
        """复制文件路径"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(str(self.file_path))

    def _show_processing(self):
        """显示处理中状态"""
        self.is_processing = True
        self.processing_label.setVisible(True)
        self.setEnabled(False)

    def _hide_processing(self):
        """隐藏处理中状态"""
        self.is_processing = False
        self.processing_label.setVisible(False)
        self.setEnabled(True)


class MultiFileCard(QFrame):
    """
    多文件卡片组件 - 展示多个文件分组

    支持功能:
    - 按文件类型自动分组
    - 批量文件操作
    - 分组折叠/展开
    """

    # 信号
    file_open_requested = pyqtSignal(str, str)
    file_operation_requested = pyqtSignal(str, str, dict)
    all_files_selected = pyqtSignal(list)

    def __init__(self, files: list, parent=None):
        """
        files: [{path, name, size, type}, ...]
        """
        super().__init__(parent)
        self.files = files
        self.file_cards = {}
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 4px 0;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # 按类型分组文件
        grouped_files = self._group_files_by_category()

        for category, file_list in grouped_files.items():
            # 分组标题
            group_frame = QFrame()
            group_frame.setStyleSheet("""
                QFrame {
                    background-color: #252540;
                    border-radius: 6px;
                    padding: 4px;
                }
            """)

            group_layout = QVBoxLayout(group_frame)
            group_layout.setContentsMargins(8, 6, 8, 6)
            group_layout.setSpacing(6)

            # 分组标题行
            header_layout = QHBoxLayout()
            header_layout.setSpacing(6)

            category_label = QLabel()
            category_label.setText(f"{category} ({len(file_list)})")
            category_label.setStyleSheet("""
                color: #a0a0c0;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            """)
            header_layout.addWidget(category_label)
            header_layout.addStretch()

            # 全选按钮
            select_all_btn = QPushButton()
            select_all_btn.setText("☑️ 全选")
            select_all_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #60a5fa;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #80b5fa;
                }
            """)
            select_all_btn.clicked.connect(lambda checked, fl=file_list: self._on_select_all(fl))
            header_layout.addWidget(select_all_btn)

            group_layout.addLayout(header_layout)

            # 文件列表
            for file_info in file_list:
                file_path = file_info.get('path', '')
                file_card = FileCard(
                    file_path=file_path,
                    file_name=file_info.get('name', Path(file_path).name),
                    file_size=file_info.get('size', 0),
                    mime_type=file_info.get('type', ''),
                    operations=["open", "show_in_folder", "copy_path"]
                )
                file_card.file_open_requested.connect(self.file_open_requested.emit)
                file_card.file_operation_requested.connect(self.file_operation_requested.emit)
                group_layout.addWidget(file_card)

            main_layout.addWidget(group_frame)

    def _group_files_by_category(self) -> dict:
        """按类型分组文件"""
        grouped = {}
        for file_info in self.files:
            file_path = file_info.get('path', '')
            category = get_file_category(file_path)
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(file_info)
        return grouped

    def _on_select_all(self, file_list: list):
        """全选该分组文件"""
        self.all_files_selected.emit(file_list)


# ============ 消息气泡组件 ============

class MessageBubble(QFrame):
    """消息气泡"""

    def __init__(self, message: UnifiedMessage, is_outgoing: bool, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_outgoing = is_outgoing
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 气泡样式
        if self.is_outgoing:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2563eb;
                    border-radius: 16px 16px 4px 16px;
                    padding: 10px 14px;
                    margin: 4px 60px 4px 20px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2d2d44;
                    border-radius: 16px 16px 16px 4px;
                    padding: 10px 14px;
                    margin: 4px 20px 4px 60px;
                }
            """)

        # 发送者名称 (群聊时显示)
        if not self.is_outgoing and self.message.sender_name:
            sender_label = QLabel(self.message.sender_name)
            sender_label.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: bold;")
            layout.addWidget(sender_label)

        # 消息内容
        content_label = QLabel(self.message.get_content_str())
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(content_label)

        # 链接预览
        if self.message.preview and self.message.preview.loaded:
            self._add_link_preview(layout)

        # 文件/媒体预览
        if self.message.meta:
            self._add_media_preview(layout)

        # 时间戳和状态
        time_layout = QHBoxLayout()
        time_layout.setSpacing(4)

        time_label = QLabel(self.message.get_display_time())
        time_label.setStyleSheet("color: #888; font-size: 11px;")

        # 状态图标
        status_icon = ""
        if self.message.status == MessageStatus.SENDING:
            status_icon = "⏳"
        elif self.message.status == MessageStatus.SENT:
            status_icon = "✓"
        elif self.message.status == MessageStatus.DELIVERED:
            status_icon = "✓✓"
        elif self.message.status == MessageStatus.READ:
            status_icon = "✓✓"
            if self.is_outgoing:
                time_label.setStyleSheet("color: #60a5fa; font-size: 11px;")
        elif self.message.status == MessageStatus.FAILED:
            status_icon = "❌"

        status_label = QLabel(status_icon)
        status_label.setStyleSheet("color: #888; font-size: 11px;")

        time_layout.addWidget(time_label)
        time_layout.addStretch()
        time_layout.addWidget(status_label)

        layout.addLayout(time_layout)

    def _add_link_preview(self, layout: QVBoxLayout):
        """添加链接预览"""
        preview = self.message.preview

        preview_widget = QFrame()
        preview_widget.setStyleSheet("""
            QFrame {
                background-color: #1f1f35;
                border-radius: 8px;
                margin-top: 8px;
            }
        """)
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # 标题
        if preview.title:
            title_label = QLabel(preview.title)
            title_label.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: bold; padding: 8px 12px 4px;")
            title_label.setWordWrap(True)
            preview_layout.addWidget(title_label)

        # 描述
        if preview.description:
            desc_label = QLabel(preview.description[:100] + ("..." if len(preview.description) > 100 else ""))
            desc_label.setStyleSheet("color: #888; font-size: 12px; padding: 0 12px;")
            desc_label.setWordWrap(True)
            preview_layout.addWidget(desc_label)

        # 域名
        domain_label = QLabel(f"🔗 {self.message.preview.url[:50]}")
        domain_label.setStyleSheet("color: #60a5fa; font-size: 11px; padding: 4px 12px 8px;")
        domain_label.setWordWrap(True)
        preview_layout.addWidget(domain_label)

        layout.addWidget(preview_widget)

    def _add_media_preview(self, layout: QVBoxLayout):
        """添加媒体预览"""
        meta = self.message.meta

        if self.message.type == MessageType.IMAGE and meta.path:
            # 图片预览
            try:
                pixmap = QPixmap(meta.path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                    img_label = QLabel()
                    img_label.setPixmap(pixmap)
                    img_label.setStyleSheet("border-radius: 8px;")
                    layout.addWidget(img_label)
            except Exception:
                pass

        elif self.message.type == MessageType.FILE and meta.path:
            # 文件卡片预览 - 使用智能文件卡片组件
            file_card = FileCard(
                file_path=meta.path,
                file_name=meta.file_name or Path(meta.path).name,
                file_size=meta.file_size or 0,
                mime_type=meta.mime_type or "",
                operations=["open", "show_in_folder", "copy_path"]
            )
            # 连接文件打开信号
            file_card.file_open_requested.connect(self._on_file_open_requested)
            layout.addWidget(file_card)

    def _on_file_open_requested(self, file_path: str, operation: str):
        """处理文件打开请求"""
        import platform
        import subprocess
        from PyQt6.QtWidgets import QApplication

        file_path = Path(file_path)

        if not file_path.exists():
            # 文件不存在，发送信号通知父组件
            self.parent().file_not_found.emit(str(file_path))
            return

        try:
            if platform.system() == "Windows":
                os.startfile(str(file_path))
            elif platform.system() == "Darwin":
                subprocess.run(['open', str(file_path)])
            else:
                subprocess.run(['xdg-open', str(file_path)])
        except Exception as e:
            # 打开失败，发送信号通知
            if hasattr(self.parent(), 'file_open_failed'):
                self.parent().file_open_failed.emit(str(file_path), str(e))


class SystemMessageBubble(QFrame):
    """系统消息气泡"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 4px;
                margin: 4px auto;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(self.text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(label)


# ============ 会话列表项组件 ============

class SessionListItem(QWidget):
    """会话列表项"""

    def __init__(self, session: ChatSession, is_current: bool = False, parent=None):
        super().__init__(parent)
        self.session = session
        self.is_current = is_current
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 头像
        avatar_label = QLabel()
        avatar_label.setFixedSize(44, 44)
        avatar_label.setStyleSheet("""
            background-color: #2563eb;
            border-radius: 22px;
        """)

        # 在线状态指示
        status_dot = QLabel()
        status_dot.setFixedSize(12, 12)
        status_dot.move(32, 32)
        status_dot.setStyleSheet("""
            background-color: #6b7280;
            border-radius: 6px;
            border: 2px solid #16162a;
        """)

        # 名称和时间
        name_layout = QVBoxLayout()
        name_layout.setSpacing(2)

        name_label = QLabel(self.session.get_display_name(""))
        name_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")

        # 最后消息
        last_msg = ""
        if self.session.last_message:
            last_msg = self.session.last_message.get_content_str()
            if len(last_msg) > 25:
                last_msg = last_msg[:25] + "..."

        time_label = QLabel("")
        if self.session.last_message_time > 0:
            import datetime
            dt = datetime.datetime.fromtimestamp(self.session.last_message_time)
            today = datetime.datetime.today().date()
            if dt.date() == today:
                time_label.setText(dt.strftime("%H:%M"))
            elif dt.year == today.year:
                time_label.setText(dt.strftime("%m-%d"))
            else:
                time_label.setText(dt.strftime("%Y-%m-%d"))

        time_label.setStyleSheet("color: #666; font-size: 12px;")

        name_layout.addWidget(name_label)
        name_layout.addWidget(time_label)

        # 消息预览
        preview_label = QLabel(last_msg)
        preview_label.setStyleSheet("color: #888; font-size: 13px;")
        preview_label.setMaximumHeight(20)

        # 未读徽章
        if self.session.unread_count > 0:
            badge = QLabel(str(self.session.unread_count) if self.session.unread_count < 100 else "99+")
            badge.setFixedSize(20, 20)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet("""
                background-color: #ef4444;
                border-radius: 10px;
                font-size: 11px;
                color: white;
            """)

        # 置顶图标
        if self.session.is_pinned:
            pin_label = QLabel("📌")
        else:
            pin_label = QLabel("")

        layout.addWidget(avatar_label)
        layout.addLayout(name_layout)
        layout.addWidget(preview_label, 1)
        layout.addWidget(pin_label)
        layout.addStretch()


# ============ 主聊天面板 ============

class ChatPanel(QWidget):
    """
    统一聊天面板 - 三栏布局

    信号:
        session_selected: 选择会话
        message_sent: 发送消息
        call_requested: 请求通话
    """

    session_selected = pyqtSignal(str)  # session_id
    message_sent = pyqtSignal(str, str)  # session_id, content
    call_requested = pyqtSignal(str, str)  # peer_id, call_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chat_hub = get_chat_hub()
        self.current_session_id: Optional[str] = None
        self.voice_player = VoicePlayer(self)  # 语音播放器
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """设置 UI"""
        self.setObjectName("chat_panel")
        self.setStyleSheet(CHAT_STYLE)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 三栏分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ===== 左栏: 会话列表 =====
        self.session_list = QListWidget()
        self.session_list.setObjectName("session_list")
        self.session_list.setSpacing(0)
        splitter.addWidget(self._create_session_panel())

        # ===== 中栏: 消息区域 =====
        splitter.addWidget(self._create_message_panel())

        # ===== 右栏: 信息面板 =====
        self.info_panel = self._create_info_panel()
        splitter.addWidget(self.info_panel)

        # 设置分割比例
        splitter.setSizes([250, 600, 200])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setCollapsible(2, True)

        main_layout.addWidget(splitter, 1)

        # ===== 底栏: 状态栏 =====
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)

    def _create_session_panel(self) -> QWidget:
        """创建会话列表面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("search_input")
        self.search_input.setPlaceholderText("🔍 搜索会话...")
        self.search_input.setStyleSheet("""
            background-color: #2d2d44;
            border: none;
            border-radius: 16px;
            padding: 8px 16px;
            color: white;
        """)

        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # 新建会话按钮
        new_session_btn = QPushButton("➕ 新建会话")
        new_session_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 16px;
                padding: 10px;
                color: white;
                font-size: 14px;
                margin: 8px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        new_session_btn.clicked.connect(self._on_new_session)
        layout.addWidget(new_session_btn)

        # 会话列表
        self.session_list = QListWidget()
        self.session_list.setObjectName("session_list")
        self.session_list.itemClicked.connect(self._on_session_clicked)
        layout.addWidget(self.session_list, 1)

        return panel

    def _create_message_panel(self) -> QWidget:
        """创建消息区域面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部栏
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #1a1a2e; border-bottom: 1px solid #2d2d44;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 8, 16, 8)

        self.session_title = QLabel("选择会话")
        self.session_title.setObjectName("title")
        top_layout.addWidget(self.session_title)

        # 通话按钮
        self.call_btn = QToolButton()
        self.call_btn.setText("📞")
        self.call_btn.setToolTip("语音通话")
        self.call_btn.clicked.connect(lambda: self._on_call_clicked("voice"))
        top_layout.addWidget(self.call_btn)

        self.video_btn = QToolButton()
        self.video_btn.setText("📹")
        self.video_btn.setToolTip("视频通话")
        self.video_btn.clicked.connect(lambda: self._on_call_clicked("video"))
        top_layout.addWidget(self.video_btn)

        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋮")
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu()
        menu.addAction("👥 群聊信息")
        menu.addAction("🔍 搜索消息")
        menu.addAction("📌 置顶会话")
        menu.addAction("🔕 免打扰")
        menu.addAction("🗑️ 删除会话")
        self.menu_btn.setMenu(menu)
        top_layout.addWidget(self.menu_btn)

        layout.addWidget(top_bar)

        # 消息区域
        self.message_area = QScrollArea()
        self.message_area.setObjectName("message_area")
        self.message_area.setWidgetResizable(True)
        self.message_area.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.message_widget = QWidget()
        self.message_layout = QVBoxLayout(self.message_widget)
        self.message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.message_layout.setSpacing(8)
        self.message_area.setWidget(self.message_widget)
        layout.addWidget(self.message_area, 1)

        # 输入区域
        input_panel = QWidget()
        input_panel.setStyleSheet("background-color: #1a1a2e; border-top: 1px solid #2d2d44;")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(12, 8, 12, 12)
        input_layout.setSpacing(8)

        # 附件/预览区
        self.attachment_preview = QWidget()
        self.attachment_preview.hide()
        input_layout.addWidget(self.attachment_preview)

        # 输入框
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.attach_btn = QToolButton()
        self.attach_btn.setText("📎")
        self.attach_btn.setToolTip("发送文件")
        self.attach_btn.clicked.connect(self._on_attach_clicked)
        input_row.addWidget(self.attach_btn)

        # 录音按钮
        self.mic_btn = RecordButton()
        self.mic_btn.recordingFinished.connect(self._on_voice_recorded)
        input_row.addWidget(self.mic_btn)

        self.emoji_btn = QToolButton()
        self.emoji_btn.setText("😊")
        self.emoji_btn.setToolTip("表情")
        input_row.addWidget(self.emoji_btn)

        self.message_input = QTextEdit()
        self.message_input.setObjectName("message_input")
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.setMaximumHeight(100)
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d44;
                border: 1px solid #3d3d54;
                border-radius: 20px;
                padding: 10px 16px;
                color: white;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #2563eb;
            }
        """)
        self.message_input.textChanged.connect(self._on_input_changed)
        input_row.addWidget(self.message_input, 1)

        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(44, 44)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 22px;
                font-size: 18px;
                color: white;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self.send_btn)

        input_layout.addLayout(input_row)
        layout.addWidget(input_panel)

        return panel

    def _create_info_panel(self) -> QWidget:
        """创建信息面板"""
        panel = QWidget()
        panel.setObjectName("info_panel")
        panel.setMaximumWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 用户信息
        user_card = QFrame()
        user_card.setStyleSheet("background-color: #1f1f35; border-radius: 12px; padding: 16px;")
        user_layout = QVBoxLayout(user_card)
        user_layout.setSpacing(12)

        avatar = QLabel("👤")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("font-size: 48px;")
        user_layout.addWidget(avatar)

        self.peer_name = QLabel("未选择")
        self.peer_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.peer_name.setObjectName("title")
        user_layout.addWidget(self.peer_name)

        self.peer_status = QLabel("离线")
        self.peer_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.peer_status.setObjectName("subtitle")
        user_layout.addWidget(self.peer_status)

        layout.addWidget(user_card)

        # 网络诊断
        network_card = QFrame()
        network_card.setStyleSheet("background-color: #1f1f35; border-radius: 12px; padding: 12px;")
        network_layout = QVBoxLayout(network_card)
        network_layout.setSpacing(8)

        network_title = QLabel("🌐 网络诊断")
        network_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        network_layout.addWidget(network_title)

        self.network_info = QLabel("连接中...")
        self.network_info.setStyleSheet("color: #888; font-size: 12px;")
        self.network_info.setWordWrap(True)
        network_layout.addWidget(self.network_info)

        layout.addWidget(network_card)

        # 传输进度
        transfer_card = QFrame()
        transfer_card.setStyleSheet("background-color: #1f1f35; border-radius: 12px; padding: 12px;")
        transfer_layout = QVBoxLayout(transfer_card)
        transfer_layout.setSpacing(8)

        transfer_title = QLabel("📤 传输进度")
        transfer_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        transfer_layout.addWidget(transfer_title)

        self.transfer_info = QLabel("无传输任务")
        self.transfer_info.setStyleSheet("color: #888; font-size: 12px;")
        transfer_layout.addWidget(self.transfer_info)

        self.transfer_progress = QProgressBar()
        self.transfer_progress.setRange(0, 100)
        self.transfer_progress.setValue(0)
        self.transfer_progress.hide()
        transfer_layout.addWidget(self.transfer_progress)

        layout.addWidget(transfer_card)

        # 通话状态
        call_card = QFrame()
        call_card.setStyleSheet("background-color: #1f1f35; border-radius: 12px; padding: 12px;")
        call_layout = QVBoxLayout(call_card)
        call_layout.setSpacing(8)

        call_title = QLabel("📞 通话")
        call_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        call_layout.addWidget(call_title)

        self.call_info = QLabel("无通话")
        self.call_info.setStyleSheet("color: #888; font-size: 12px;")
        call_layout.addWidget(self.call_info)

        self.call_duration = QLabel("")
        self.call_duration.setStyleSheet("color: #22c55e; font-size: 24px; font-weight: bold;")
        self.call_duration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.call_duration.hide()
        call_layout.addWidget(self.call_duration)

        layout.addWidget(call_card)

        layout.addStretch()

        return panel

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        bar = QWidget()
        bar.setObjectName("status_bar")
        bar.setStyleSheet("""
            QWidget {
                background-color: #16162a;
                border-top: 1px solid #2d2d44;
                padding: 4px 16px;
            }
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        # 连接状态
        self.connection_indicator = QLabel("🟢")
        layout.addWidget(self.connection_indicator)

        self.connection_mode = QLabel("P2P直连")
        self.connection_mode.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.connection_mode)

        layout.addSpacing(16)

        # 质量
        self.quality_indicator = QLabel("🟡")
        layout.addWidget(self.quality_indicator)

        self.rtt_label = QLabel("RTT: --ms")
        self.rtt_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.rtt_label)

        layout.addSpacing(16)

        # CPU/内存
        self.cpu_label = QLabel("CPU: --%")
        self.cpu_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.cpu_label)

        layout.addSpacing(8)

        self.memory_label = QLabel("内存: --%")
        self.memory_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.memory_label)

        layout.addStretch()

        # 我的短ID
        my_id_text = f"我的ID: {self.chat_hub.get_my_short_id()}"
        self.my_id_label = QLabel(my_id_text)
        self.my_id_label.setStyleSheet("color: #60a5fa; font-size: 12px;")
        layout.addWidget(self.my_id_label)

        return bar

    def setup_connections(self):
        """设置信号连接"""
        # 添加 UI 回调
        self.chat_hub.add_ui_callback(self._on_chat_hub_event)

        # 定时更新状态栏
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(2000)

    # ============ 事件处理 ============

    def _on_chat_hub_event(self, event: str, data):
        """ChatHub 事件回调"""
        if event == "message_received" or event == "message_sent":
            if data.session_id == self.current_session_id:
                self._append_message(data)
        elif event == "status_changed":
            self._update_status_info(data)

    def _on_session_clicked(self, item: QListWidgetItem):
        """会话列表点击"""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_session_id = session_id
        self.chat_hub.set_current_session(session_id)
        self.session_selected.emit(session_id)
        self._load_messages(session_id)

    def _on_new_session(self):
        """新建会话"""
        peer_id, ok = QInputDialog.getText(self, "新建会话", "输入对方节点ID或短ID:")
        if ok and peer_id:
            session = self.chat_hub.get_or_create_session(peer_id)
            self._refresh_session_list()
            self._select_session(session.session_id)

    def _on_send_clicked(self):
        """发送消息"""
        if not self.current_session_id:
            return

        text = self.message_input.toPlainText().strip()
        if not text:
            return

        asyncio.create_task(self.chat_hub.send_text_message(self.current_session_id, text))
        self.message_input.clear()

    def _on_input_changed(self):
        """输入框内容变化 (检测链接)"""
        text = self.message_input.toPlainText()
        # TODO: 实时检测链接并显示预览

    def _on_attach_clicked(self):
        """点击附件按钮"""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path and self.current_session_id:
            path = Path(file_path)
            asyncio.create_task(self.chat_hub.send_file_message(
                self.current_session_id,
                str(file_path),
                path.name,
                path.stat().st_size
            ))

    def _on_voice_recorded(self, file_path: str):
        """语音录制完成"""
        if not self.current_session_id:
            return
        if not Path(file_path).exists():
            return

        # 获取时长
        duration = get_voice_duration(file_path)

        # 发送语音消息
        asyncio.create_task(self.chat_hub.send_file_message(
            self.current_session_id,
            str(file_path),
            Path(file_path).name,
            Path(file_path).stat().st_size,
            mime_type="audio/wav"
        ))

    def _on_voice_play(self, msg_id: str):
        """播放语音"""
        # 查找消息对应的文件路径
        message = self.chat_hub.session_manager.get_message(msg_id)
        if message and message.meta and message.meta.path:
            self.voice_player.play(msg_id, message.meta.path)

    def _on_voice_pause(self, msg_id: str):
        """暂停语音"""
        self.voice_player.pause()

    def _on_voice_delete(self, msg_id: str):
        """删除语音消息"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "删除消息", "确定要删除这条语音消息吗?")
        if reply == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self.chat_hub.delete_message(msg_id))
            # 从UI移除
            for i in range(self.message_layout.count()):
                item = self.message_layout.itemAt(i)
                if item.widget():
                    widget = item.widget()
                    if hasattr(widget, 'msg_id') and widget.msg_id == msg_id:
                        widget.deleteLater()
                        break

    def _on_voice_transcribe(self, msg_id: str):
        """转写语音为文字"""
        message = self.chat_hub.session_manager.get_message(msg_id)
        if message and message.meta and message.meta.path:
            # TODO: 调用语音识别API
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "转文字", "语音转文字功能开发中...")

    def _on_voice_resend(self, msg_id: str):
        """重发语音消息"""
        asyncio.create_task(self.chat_hub.resend_message(msg_id))

    def _on_call_clicked(self, call_type: str):
        """通话按钮点击"""
        if not self.current_session_id:
            return
        session = self.chat_hub.session_manager.get_session(self.current_session_id)
        if session and session.peer_id:
            self.call_requested.emit(session.peer_id, call_type)

    def _update_status_bar(self):
        """更新状态栏"""
        status = self.chat_hub.get_status_info()

        # 连接状态
        self.connection_indicator.setText(status.get("connection_icon", "⚪"))
        self.connection_mode.setText(status.get("connection_mode", ""))

        # 质量
        self.quality_indicator.setText(status.get("quality_icon", "⚪"))
        self.rtt_label.setText(status.get("rtt", "RTT: --ms"))

        # 系统
        self.cpu_label.setText(status.get("cpu", "CPU: --%"))
        self.memory_label.setText(status.get("memory", "内存: --%"))

    def _update_status_info(self, status: Dict):
        """更新信息面板状态"""
        if "connection_icon" in status:
            self.connection_indicator.setText(status["connection_icon"])
        if "connection_mode" in status:
            self.connection_mode.setText(status["connection_mode"])
        if "quality_icon" in status:
            self.quality_indicator.setText(status["quality_icon"])
        if "rtt" in status:
            self.rtt_label.setText(status["rtt"])

    # ============ 消息显示 ============

    def _load_messages(self, session_id: str):
        """加载会话消息"""
        # 清空现有消息
        while self.message_layout.count():
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 加载消息
        messages = self.chat_hub.session_manager.get_session_messages(session_id, limit=100)
        for msg in reversed(messages):
            self._append_message(msg)

        # 更新标题
        session = self.chat_hub.session_manager.get_session(session_id)
        if session:
            self.session_title.setText(session.get_display_name(""))
            if session.peer_id:
                peer_status = self.chat_hub.get_peer_status(session.peer_id)
                self.peer_status.setText({
                    OnlineStatus.ONLINE: "🟢 在线",
                    OnlineStatus.OFFLINE: "⚪ 离线",
                    OnlineStatus.AWAY: "🟡 离开",
                    OnlineStatus.BUSY: "🔴 忙碌",
                }.get(peer_status, "⚪ 离线"))

        # 滚动到底部
        QTimer.singleShot(100, self.message_area.verticalScrollBar().setValue,
                          self.message_area.verticalScrollBar().maximum())

    def _append_message(self, message: UnifiedMessage):
        """追加消息到显示区域"""
        is_outgoing = message.is_outgoing(self.chat_hub.get_my_id())

        if message.type == MessageType.SYSTEM:
            bubble = SystemMessageBubble(str(message.content))
        elif message.type == MessageType.VOICE:
            # 语音消息使用专门的VoiceBubble
            duration = message.meta.duration if message.meta else 0
            file_path = message.meta.path if message.meta else ""
            status_str = message.status.value if message.status else "sent"
            bubble = create_voice_message(
                msg_id=message.msg_id,
                file_path=file_path,
                duration=duration,
                is_outgoing=is_outgoing,
                status=status_str
            )
            # 连接播放信号
            bubble.playClicked.connect(self._on_voice_play)
            bubble.pauseClicked.connect(self._on_voice_pause)
            bubble.deleteClicked.connect(self._on_voice_delete)
            bubble.transcribeClicked.connect(self._on_voice_transcribe)
            bubble.resendClicked.connect(self._on_voice_resend)
        else:
            bubble = MessageBubble(message, is_outgoing)

        self.message_layout.addWidget(bubble)

        # 滚动到底部
        QTimer.singleShot(50, lambda: self.message_area.verticalScrollBar().setValue(
            self.message_area.verticalScrollBar().maximum()))

    # ============ 会话列表 ============

    def _refresh_session_list(self):
        """刷新会话列表"""
        self.session_list.clear()
        sessions = self.chat_hub.get_all_sessions()

        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)

            # 创建自定义 widget
            widget = SessionListItem(session, session.session_id == self.current_session_id)
            item.setSizeHint(QSize(0, 72))

            self.session_list.addItem(item)
            self.session_list.setItemWidget(item, widget)

    def _select_session(self, session_id: str):
        """选中指定会话"""
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.session_list.setCurrentItem(item)
                self._on_session_clicked(item)
                break

    # ============ 公共接口 ============

    def set_my_identity(self, node_id: str, short_id: str, name: str = ""):
        """设置我的身份"""
        self.chat_hub.set_my_identity(node_id, short_id, name)
        self.my_id_label.setText(f"我的ID: {short_id}")
        self._refresh_session_list()

    def load_sessions(self):
        """加载会话列表"""
        self._refresh_session_list()


# ============ 入口函数 ============

def get_chat_panel() -> ChatPanel:
    """获取聊天面板实例"""
    return ChatPanel()


# ============ 文件消息工具函数 ============

def create_file_message_content(files: list, intro_text: str = "已为您生成以下文件:") -> str:
    """
    创建文件消息的文本内容 (用于消息气泡显示)

    Args:
        files: 文件列表 [{path, name, size}, ...]
        intro_text: 文件列表前的介绍文字

    Returns:
        格式化的文本内容
    """
    if not files:
        return intro_text

    # 按类型分组
    grouped = {}
    for f in files:
        path = f.get('path', '')
        category = get_file_category(path)
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(f)

    lines = [intro_text, ""]

    for category, file_list in grouped.items():
        lines.append(f"**{category}**")
        for f in file_list:
            name = f.get('name', Path(f.get('path', '')).name)
            size = f.get('size', 0)
            size_str = f" ({format_file_size(size)})" if size else ""
            icon = get_file_icon(f.get('path', name))
            lines.append(f"{icon} {name}{size_str}")
        lines.append("")

    return "\n".join(lines)


def create_multi_file_card(files: list, parent=None) -> MultiFileCard:
    """
    创建多文件卡片组件

    Args:
        files: 文件列表 [{path, name, size, type}, ...]
        parent: 父组件

    Returns:
        MultiFileCard 组件实例
    """
    return MultiFileCard(files=files, parent=parent)


def create_single_file_card(
    file_path: str,
    file_name: str = "",
    file_size: int = 0,
    operations: list = None,
    parent=None
) -> FileCard:
    """
    创建单文件卡片组件

    Args:
        file_path: 文件路径
        file_name: 文件名 (可选，自动从路径提取)
        file_size: 文件大小 (可选)
        operations: 操作列表 (可选，默认 ["open", "show_in_folder", "copy_path"])
        parent: 父组件

    Returns:
        FileCard 组件实例
    """
    return FileCard(
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
        operations=operations,
        parent=parent
    )


def open_file_with_default_app(file_path: str) -> bool:
    """
    使用系统默认程序打开文件

    Args:
        file_path: 文件路径

    Returns:
        是否成功打开
    """
    import platform
    import subprocess

    file_path = Path(file_path)
    if not file_path.exists():
        return False

    try:
        if platform.system() == "Windows":
            os.startfile(str(file_path))
        elif platform.system() == "Darwin":
            subprocess.run(['open', str(file_path)], check=True)
        else:
            subprocess.run(['xdg-open', str(file_path)], check=True)
        return True
    except Exception:
        return False


def show_file_in_folder(file_path: str) -> bool:
    """
    在文件管理器中显示文件

    Args:
        file_path: 文件路径

    Returns:
        是否成功
    """
    import platform
    import subprocess

    file_path = Path(file_path)
    if not file_path.exists():
        return False

    folder = file_path.parent

    try:
        if platform.system() == "Windows":
            subprocess.run(['explorer', '/select,', str(file_path)], check=True)
        elif platform.system() == "Darwin":
            subprocess.run(['open', '-R', str(file_path)], check=True)
        else:
            subprocess.run(['xdg-open', str(folder)], check=True)
        return True
    except Exception:
        return False


def copy_file_path_to_clipboard(file_path: str) -> bool:
    """
    复制文件路径到剪贴板

    Args:
        file_path: 文件路径

    Returns:
        是否成功
    """
    from PyQt6.QtWidgets import QApplication

    try:
        clipboard = QApplication.clipboard()
        clipboard.setText(str(file_path))
        return True
    except Exception:
        return False
