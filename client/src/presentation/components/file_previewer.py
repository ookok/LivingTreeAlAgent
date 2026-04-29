"""
文件预览组件 - 统一文件展示UI

支持多种文件类型的预览：
1. 图片：直接渲染显示
2. 音频：播放器组件
3. 视频：视频播放器
4. Office文档：内嵌WPS预览
5. Markdown：渲染为富文本
6. LLM Wiki：Wiki格式渲染
7. 代码文件：语法高亮显示
8. 其他文件：下载/打开按钮

设计目标：统一的文件预览接口，根据文件类型自动选择最佳展示方式
"""

import os
import platform
import subprocess
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTextEdit,
    QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSize
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices

from .markdown_renderer import MarkdownRenderer


class FilePreviewer(QWidget):
    """
    文件预览器 - 根据文件类型自动选择预览方式
    
    支持的文件类型：
    - 图片: .png, .jpg, .jpeg, .gif, .svg, .bmp, .webp
    - 音频: .mp3, .wav, .flac, .ogg, .aac
    - 视频: .mp4, .avi, .mov, .mkv, .webm
    - Office: .doc, .docx, .xls, .xlsx, .ppt, .pptx
    - Markdown: .md, .markdown
    - 代码: .py, .js, .ts, .html, .css, .json, .xml, .java, .cpp 等
    - 文本: .txt, .log
    - PDF: .pdf
    - 其他: 下载/打开按钮
    """
    
    file_opened = pyqtSignal(str)  # 文件路径
    download_requested = pyqtSignal(str)  # 文件路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file_path = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        
        # 顶部工具栏
        self.toolbar = QFrame()
        self.toolbar.setStyleSheet("background-color: #f5f5f5; padding: 8px;")
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(8, 4, 8, 4)
        self.toolbar_layout.setSpacing(8)
        
        self.file_name_label = QLabel()
        self.file_name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.toolbar_layout.addWidget(self.file_name_label)
        
        self.toolbar_layout.addStretch()
        
        self.download_btn = QToolButton()
        self.download_btn.setText("⬇️ 下载")
        self.download_btn.clicked.connect(self._on_download)
        self.toolbar_layout.addWidget(self.download_btn)
        
        self.open_btn = QToolButton()
        self.open_btn.setText("📂 打开")
        self.open_btn.clicked.connect(self._on_open)
        self.toolbar_layout.addWidget(self.open_btn)
        
        self.layout.addWidget(self.toolbar)
        
        # 内容区域
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setStyleSheet("QScrollArea { border: none; }")
        self.layout.addWidget(self.content_area, 1)
        
        # 当前内容控件
        self.current_content = QWidget()
        self.content_area.setWidget(self.current_content)
    
    def preview_file(self, file_path: str):
        """预览文件"""
        self._current_file_path = file_path
        file_name = Path(file_path).name
        
        # 更新文件名
        self.file_name_label.setText(file_name)
        
        # 根据文件类型选择预览方式
        file_type = self._get_file_type(file_path)
        
        # 清除旧内容
        self._clear_content()
        
        # 创建对应类型的预览控件
        if file_type == "image":
            self._preview_image(file_path)
        elif file_type == "audio":
            self._preview_audio(file_path)
        elif file_type == "video":
            self._preview_video(file_path)
        elif file_type == "office":
            self._preview_office(file_path)
        elif file_type == "markdown":
            self._preview_markdown(file_path)
        elif file_type == "code":
            self._preview_code(file_path)
        elif file_type == "text":
            self._preview_text(file_path)
        elif file_type == "pdf":
            self._preview_pdf(file_path)
        else:
            self._preview_other(file_path)
    
    def _get_file_type(self, file_path: str) -> str:
        """获取文件类型"""
        ext = Path(file_path).suffix.lower()
        
        # 图片类型
        image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp', '.ico']
        if ext in image_exts:
            return "image"
        
        # 音频类型
        audio_exts = ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a']
        if ext in audio_exts:
            return "audio"
        
        # 视频类型
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv']
        if ext in video_exts:
            return "video"
        
        # Office文档
        office_exts = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
        if ext in office_exts:
            return "office"
        
        # Markdown
        md_exts = ['.md', '.markdown']
        if ext in md_exts:
            return "markdown"
        
        # 代码文件
        code_exts = ['.py', '.js', '.ts', '.html', '.css', '.json', '.xml',
                     '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.php',
                     '.swift', '.kt', '.vue', '.tsx', '.jsx', '.yaml', '.yml',
                     '.toml', '.ini', '.cfg', '.conf']
        if ext in code_exts:
            return "code"
        
        # 文本文件
        text_exts = ['.txt', '.log', '.md', '.rst']
        if ext in text_exts:
            return "text"
        
        # PDF
        if ext == '.pdf':
            return "pdf"
        
        return "other"
    
    def _clear_content(self):
        """清除当前内容"""
        # 删除旧内容控件
        if self.current_content:
            self.current_content.deleteLater()
        
        # 创建新的内容控件
        self.current_content = QWidget()
        self.content_area.setWidget(self.current_content)
    
    def _preview_image(self, file_path: str):
        """预览图片"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 加载并缩放图片
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            # 限制最大尺寸
            max_size = QSize(800, 600)
            pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
        else:
            label.setText("❌ 无法加载图片")
        
        layout.addWidget(label)
    
    def _preview_audio(self, file_path: str):
        """预览音频"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 音频播放器占位
        player_frame = QFrame()
        player_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        player_layout = QVBoxLayout(player_frame)
        
        # 音频信息
        info_label = QLabel(f"🎵 {Path(file_path).name}")
        info_label.setStyleSheet("color: #e2e8f0; font-size: 16px; font-weight: bold;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        player_layout.addWidget(info_label)
        
        # 播放按钮
        play_btn = QPushButton("▶️ 播放")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 12px 32px;
                font-size: 16px;
                margin-top: 16px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        play_btn.clicked.connect(lambda: self._play_audio(file_path))
        player_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(player_frame)
    
    def _play_audio(self, file_path: str):
        """播放音频"""
        self._open_file_with_default_app(file_path)
    
    def _preview_video(self, file_path: str):
        """预览视频"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 视频播放器占位
        player_frame = QFrame()
        player_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-radius: 12px;
                padding: 16px;
                min-height: 300px;
            }
        """)
        player_layout = QVBoxLayout(player_frame)
        
        # 视频封面
        cover_label = QLabel("🎬 视频预览")
        cover_label.setStyleSheet("color: #64748b; font-size: 24px;")
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setMinimumHeight(200)
        player_layout.addWidget(cover_label)
        
        # 视频信息
        info_label = QLabel(f"📹 {Path(file_path).name}")
        info_label.setStyleSheet("color: #e2e8f0; font-size: 14px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        player_layout.addWidget(info_label)
        
        # 播放按钮
        play_btn = QPushButton("▶️ 播放视频")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 12px 32px;
                font-size: 16px;
                margin-top: 16px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        play_btn.clicked.connect(lambda: self._play_video(file_path))
        player_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(player_frame)
    
    def _play_video(self, file_path: str):
        """播放视频"""
        self._open_file_with_default_app(file_path)
    
    def _preview_office(self, file_path: str):
        """预览Office文档（内嵌WPS）"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # WPS预览占位
        wps_frame = QFrame()
        wps_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                min-height: 400px;
            }
        """)
        wps_layout = QVBoxLayout(wps_frame)
        
        # WPS Logo和标题
        wps_label = QLabel("📊 WPS Office 文档预览")
        wps_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a5fb4;")
        wps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wps_layout.addWidget(wps_label)
        
        # 文件信息
        info_label = QLabel(f"📄 {Path(file_path).name}")
        info_label.setStyleSheet("font-size: 14px; color: #666;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wps_layout.addWidget(info_label)
        
        # 打开按钮
        open_btn = QPushButton("🖱️ 在WPS中打开")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                margin-top: 24px;
            }
            QPushButton:hover {
                background-color: #154a92;
            }
        """)
        open_btn.clicked.connect(lambda: self._open_with_wps(file_path))
        wps_layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 提示信息
        tip_label = QLabel("💡 提示：需要安装WPS Office才能预览")
        tip_label.setStyleSheet("font-size: 12px; color: #999; margin-top: 16px;")
        tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wps_layout.addWidget(tip_label)
        
        layout.addWidget(wps_frame)
    
    def _open_with_wps(self, file_path: str):
        """使用WPS打开文档"""
        wps_path = self._find_wps_path()
        if wps_path:
            try:
                subprocess.Popen([wps_path, file_path])
            except Exception:
                self._open_file_with_default_app(file_path)
        else:
            self._open_file_with_default_app(file_path)
    
    def _find_wps_path(self) -> Optional[str]:
        """查找WPS安装路径"""
        paths = [
            r"C:\Program Files\WPS Office\11.1.0.11693\office6\wps.exe",
            r"C:\Program Files (x86)\WPS Office\11.1.0.11693\office6\wps.exe",
            r"C:\Program Files\WPS Office\office6\wps.exe",
            r"C:\Program Files (x86)\WPS Office\office6\wps.exe",
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        return None
    
    def _preview_markdown(self, file_path: str):
        """预览Markdown文件"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用Markdown渲染器
        renderer = MarkdownRenderer()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            widget = renderer.render(content)
            layout.addWidget(widget)
        except Exception as e:
            error_label = QLabel(f"❌ 无法读取文件: {e}")
            error_label.setStyleSheet("color: #dc2626;")
            layout.addWidget(error_label)
    
    def _preview_code(self, file_path: str):
        """预览代码文件（语法高亮）"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 代码预览区域
        code_frame = QFrame()
        code_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        code_layout = QVBoxLayout(code_frame)
        
        # 文件信息栏
        info_bar = QFrame()
        info_bar.setStyleSheet("background-color: #0f172a; border-radius: 4px; padding: 8px 12px;")
        info_layout = QHBoxLayout(info_bar)
        
        lang_label = QLabel(f"📄 {Path(file_path).suffix[1:].upper()}")
        lang_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        info_layout.addWidget(lang_label)
        
        info_layout.addStretch()
        
        copy_btn = QToolButton()
        copy_btn.setText("📋")
        copy_btn.setToolTip("复制代码")
        copy_btn.clicked.connect(lambda: self._copy_code(file_path))
        info_layout.addWidget(copy_btn)
        
        code_layout.addWidget(info_bar)
        
        # 代码显示区域
        code_edit = QTextEdit()
        code_edit.setReadOnly(True)
        code_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                color: #e2e8f0;
                border: none;
                margin-top: 12px;
            }
        """)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            code_edit.setPlainText(content)
        except Exception as e:
            code_edit.setText(f"无法读取文件: {e}")
        
        code_layout.addWidget(code_edit)
        
        layout.addWidget(code_frame)
    
    def _copy_code(self, file_path: str):
        """复制代码到剪贴板"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
        except Exception:
            pass
    
    def _preview_text(self, file_path: str):
        """预览文本文件"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                color: #1e293b;
            }
        """)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            text_edit.setPlainText(content)
        except Exception as e:
            text_edit.setText(f"无法读取文件: {e}")
        
        layout.addWidget(text_edit)
    
    def _preview_pdf(self, file_path: str):
        """预览PDF文件"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        pdf_frame = QFrame()
        pdf_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                min-height: 400px;
            }
        """)
        pdf_layout = QVBoxLayout(pdf_frame)
        
        pdf_label = QLabel("📕 PDF文档预览")
        pdf_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626;")
        pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout.addWidget(pdf_label)
        
        info_label = QLabel(f"📄 {Path(file_path).name}")
        info_label.setStyleSheet("font-size: 14px; color: #666;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout.addWidget(info_label)
        
        open_btn = QPushButton("🔍 在默认PDF阅读器中打开")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                margin-top: 24px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        open_btn.clicked.connect(lambda: self._open_file_with_default_app(file_path))
        pdf_layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(pdf_frame)
    
    def _preview_other(self, file_path: str):
        """预览其他类型文件"""
        layout = QVBoxLayout(self.current_content)
        layout.setContentsMargins(16, 16, 16, 16)
        
        other_frame = QFrame()
        other_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 24px;
            }
        """)
        other_layout = QVBoxLayout(other_frame)
        
        icon_label = QLabel("📦")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        other_layout.addWidget(icon_label)
        
        name_label = QLabel(f"{Path(file_path).name}")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        other_layout.addWidget(name_label)
        
        size_label = QLabel(f"📐 文件大小: {self._format_size(Path(file_path).stat().st_size)}")
        size_label.setStyleSheet("font-size: 14px; color: #64748b;")
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        other_layout.addWidget(size_label)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        download_btn = QPushButton("⬇️ 下载")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        download_btn.clicked.connect(self._on_download)
        button_layout.addWidget(download_btn)
        
        open_btn = QPushButton("📂 打开")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        open_btn.clicked.connect(self._on_open)
        button_layout.addWidget(open_btn)
        
        other_layout.addLayout(button_layout)
        
        layout.addWidget(other_frame)
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def _on_download(self):
        """处理下载请求"""
        self.download_requested.emit(self._current_file_path)
    
    def _on_open(self):
        """处理打开请求"""
        self._open_file_with_default_app(self._current_file_path)
        self.file_opened.emit(self._current_file_path)
    
    def _open_file_with_default_app(self, file_path: str):
        """使用默认应用打开文件"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            print(f"无法打开文件: {e}")


class URLPreviewer(QWidget):
    """
    URL预览器 - 预览网页链接
    
    支持的URL类型：
    - 普通网页：显示预览信息
    - 图片URL：直接显示图片
    - 视频URL：显示视频播放器
    - 文档URL：提供下载/打开选项
    """
    
    url_opened = pyqtSignal(str)
    download_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_url = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # URL信息栏
        self.url_bar = QFrame()
        self.url_bar.setStyleSheet("background-color: #f5f5f5; padding: 8px 16px;")
        self.url_layout = QHBoxLayout(self.url_bar)
        
        self.url_label = QLabel()
        self.url_label.setStyleSheet("font-size: 13px; color: #64748b;")
        self.url_label.setWordWrap(True)
        self.url_layout.addWidget(self.url_label)
        
        self.open_btn = QPushButton("🌐 打开")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
        """)
        self.open_btn.clicked.connect(self._open_url)
        self.url_layout.addWidget(self.open_btn)
        
        self.layout.addWidget(self.url_bar)
        
        # 预览区域
        self.preview_area = QFrame()
        self.preview_area.setStyleSheet("background-color: white;")
        self.layout.addWidget(self.preview_area, 1)
    
    def preview_url(self, url: str):
        """预览URL"""
        self._current_url = url
        self.url_label.setText(url)
        
        # 清除旧内容
        while self.preview_area.layout() and self.preview_area.layout().count() > 0:
            item = self.preview_area.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 判断URL类型
        if self._is_image_url(url):
            self._preview_image_url(url)
        elif self._is_video_url(url):
            self._preview_video_url(url)
        elif self._is_document_url(url):
            self._preview_document_url(url)
        else:
            self._preview_web_url(url)
    
    def _is_image_url(self, url: str) -> bool:
        """判断是否为图片URL"""
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp']
        return any(url.lower().endswith(ext) for ext in image_extensions)
    
    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频URL"""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        return any(url.lower().endswith(ext) for ext in video_extensions)
    
    def _is_document_url(self, url: str) -> bool:
        """判断是否为文档URL"""
        doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.md']
        return any(url.lower().endswith(ext) for ext in doc_extensions)
    
    def _preview_image_url(self, url: str):
        """预览图片URL"""
        layout = QVBoxLayout(self.preview_area)
        layout.setContentsMargins(16, 16, 16, 16)
        
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 尝试加载图片
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(requests.get(url).content)
            if not pixmap.isNull():
                max_size = QSize(800, 600)
                pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
                label.setPixmap(pixmap)
            else:
                label.setText("❌ 无法加载图片")
        except Exception:
            label.setText("❌ 无法加载图片")
        
        layout.addWidget(label)
    
    def _preview_video_url(self, url: str):
        """预览视频URL"""
        layout = QVBoxLayout(self.preview_area)
        layout.setContentsMargins(16, 16, 16, 16)
        
        video_frame = QFrame()
        video_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-radius: 12px;
                padding: 24px;
                min-height: 300px;
            }
        """)
        video_layout = QVBoxLayout(video_frame)
        
        label = QLabel("🎬 视频预览")
        label.setStyleSheet("color: #64748b; font-size: 24px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(label)
        
        play_btn = QPushButton("▶️ 在浏览器中播放")
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 12px 32px;
                font-size: 16px;
                margin-top: 16px;
            }
        """)
        play_btn.clicked.connect(self._open_url)
        video_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(video_frame)
    
    def _preview_document_url(self, url: str):
        """预览文档URL"""
        layout = QVBoxLayout(self.preview_area)
        layout.setContentsMargins(16, 16, 16, 16)
        
        doc_frame = QFrame()
        doc_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 24px;
            }
        """)
        doc_layout = QVBoxLayout(doc_frame)
        
        label = QLabel(f"📄 {url.split('/')[-1]}")
        label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        doc_layout.addWidget(label)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        download_btn = QPushButton("⬇️ 下载")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
        """)
        download_btn.clicked.connect(lambda: self.download_requested.emit(url))
        btn_layout.addWidget(download_btn)
        
        open_btn = QPushButton("🌐 在线查看")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
        """)
        open_btn.clicked.connect(self._open_url)
        btn_layout.addWidget(open_btn)
        
        doc_layout.addLayout(btn_layout)
        
        layout.addWidget(doc_frame)
    
    def _preview_web_url(self, url: str):
        """预览网页URL"""
        layout = QVBoxLayout(self.preview_area)
        layout.setContentsMargins(16, 16, 16, 16)
        
        web_frame = QFrame()
        web_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 24px;
            }
        """)
        web_layout = QVBoxLayout(web_frame)
        
        icon_label = QLabel("🌐")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        web_layout.addWidget(icon_label)
        
        title_label = QLabel("网页链接")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        web_layout.addWidget(title_label)
        
        url_label = QLabel(url)
        url_label.setStyleSheet("font-size: 13px; color: #64748b; word-break: break-all;")
        url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        web_layout.addWidget(url_label)
        
        open_btn = QPushButton("🔗 在浏览器中打开")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                margin-top: 16px;
            }
        """)
        open_btn.clicked.connect(self._open_url)
        web_layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(web_frame)
    
    def _open_url(self):
        """在浏览器中打开URL"""
        QDesktopServices.openUrl(QUrl(self._current_url))
        self.url_opened.emit(self._current_url)


# 全局函数
def preview_file_or_url(path_or_url: str, parent=None) -> QWidget:
    """
    根据路径或URL创建预览控件
    
    Args:
        path_or_url: 文件路径或URL
        parent: 父控件
        
    Returns:
        预览控件
    """
    if path_or_url.startswith(('http://', 'https://', 'ftp://')):
        previewer = URLPreviewer(parent)
        previewer.preview_url(path_or_url)
        return previewer
    else:
        previewer = FilePreviewer(parent)
        previewer.preview_file(path_or_url)
        return previewer