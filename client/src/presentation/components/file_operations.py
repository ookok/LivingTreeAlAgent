"""文件操作组件 - 支持上传、查看、媒体播放"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QProgressBar,
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QFileDialog, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QIcon, QPixmap
import os

class FileUploader(QWidget):
    """文件上传组件"""
    
    files_uploaded = pyqtSignal(list)
    file_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        self._drop_zone = QFrame()
        self._drop_zone.setStyleSheet("""
            QFrame {
                border: 2px dashed #d1d5db;
                border-radius: 12px;
                background: #f9fafb;
            }
            QFrame:hover {
                border-color: #6366f1;
                background: #f0f1ff;
            }
            QFrame:drop {
                border-color: #6366f1;
                background: #eef2ff;
            }
        """)
        self._drop_zone.setFixedHeight(120)
        self._drop_zone.setAcceptDrops(True)
        
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(24, 24, 24, 24)
        
        icon_label = QLabel()
        icon_label.setPixmap(QIcon("icons/upload.png").pixmap(48, 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(icon_label)
        
        text_label = QLabel("拖拽文件到此处或点击选择")
        text_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
                text-align: center;
            }
        """)
        drop_layout.addWidget(text_label)
        
        self._drop_zone.dragEnterEvent = self._on_drag_enter
        self._drop_zone.dragLeaveEvent = self._on_drag_leave
        self._drop_zone.dropEvent = self._on_drop
        self._drop_zone.mousePressEvent = self._on_click
        
        layout.addWidget(self._drop_zone)
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 8px;
                height: 8px;
                background: #e5e7eb;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 8px;
            }
        """)
        layout.addWidget(self._progress_bar)
    
    def _on_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_zone.setStyleSheet("""
                QFrame {
                    border: 2px dashed #6366f1;
                    border-radius: 12px;
                    background: #eef2ff;
                }
            """)
    
    def _on_drag_leave(self, event):
        self._drop_zone.setStyleSheet("""
            QFrame {
                border: 2px dashed #d1d5db;
                border-radius: 12px;
                background: #f9fafb;
            }
        """)
    
    def _on_drop(self, event):
        self._drop_zone.setStyleSheet("""
            QFrame {
                border: 2px dashed #d1d5db;
                border-radius: 12px;
                background: #f9fafb;
            }
        """)
        
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                files.append(url.toLocalFile())
        
        if files:
            self.files_uploaded.emit(files)
    
    def _on_click(self, event):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if dialog.exec():
            files = dialog.selectedFiles()
            self.files_uploaded.emit(files)
    
    def show_progress(self, progress):
        """显示上传进度"""
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(progress)
        
        if progress >= 100:
            QTimer.singleShot(1000, lambda: self._progress_bar.setVisible(False))

class FileViewer(QWidget):
    """文件查看器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        layout.addWidget(self._scroll_area)
        
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._scroll_area.setWidget(self._content_widget)
    
    def load_file(self, file_path):
        """加载文件"""
        self._clear_content()
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg']:
            self._load_image(file_path)
        elif ext in ['.txt', '.py', '.json', '.md']:
            self._load_text(file_path)
        else:
            self._load_unknown(file_path)
    
    def _load_image(self, file_path):
        """加载图片"""
        label = QLabel()
        pixmap = QPixmap(file_path)
        label.setPixmap(pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(label)
    
    def _load_text(self, file_path):
        """加载文本文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setStyleSheet("""
                QTextEdit {
                    background: #1e1e1e;
                    color: #d4d4d4;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 13px;
                    border: none;
                }
            """)
            text_edit.setPlainText(content)
            self._content_layout.addWidget(text_edit)
        except Exception as e:
            label = QLabel(f"无法读取文件: {str(e)}")
            label.setStyleSheet("color: #ef4444;")
            self._content_layout.addWidget(label)
    
    def _load_unknown(self, file_path):
        """加载未知类型文件"""
        label = QLabel(f"不支持的文件类型: {os.path.basename(file_path)}")
        label.setStyleSheet("color: #6b7280;")
        self._content_layout.addWidget(label)
    
    def _clear_content(self):
        """清空内容"""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

class MediaPlayer(QWidget):
    """媒体播放器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        self._video_frame = QFrame()
        self._video_frame.setStyleSheet("""
            QFrame {
                background: #0d1117;
                border-radius: 8px;
            }
        """)
        self._video_frame.setFixedHeight(300)
        
        video_layout = QVBoxLayout(self._video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        self._play_icon = QLabel()
        self._play_icon.setPixmap(QIcon("icons/play.png").pixmap(64, 64))
        self._play_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(self._play_icon)
        
        layout.addWidget(self._video_frame)
        
        controls_layout = QHBoxLayout()
        
        self._play_btn = QPushButton()
        self._play_btn.setIcon(QIcon("icons/play.png"))
        self._play_btn.setFixedSize(40, 40)
        self._play_btn.setStyleSheet("""
            QPushButton {
                background: #6366f1;
                border: none;
                border-radius: 50%;
            }
            QPushButton:hover {
                background: #4f46e5;
            }
        """)
        controls_layout.addWidget(self._play_btn)
        
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                height: 6px;
                background: #374151;
            }
            QProgressBar::chunk {
                background: #6366f1;
            }
        """)
        controls_layout.addWidget(self._progress)
        
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        controls_layout.addWidget(self._time_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
    
    def play(self):
        """播放"""
        self._play_icon.hide()
    
    def pause(self):
        """暂停"""
        pass

from PyQt6.QtCore import QTimer