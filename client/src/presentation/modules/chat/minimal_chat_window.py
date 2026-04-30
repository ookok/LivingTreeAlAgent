"""
极简聊天窗口 - Minimal Chat Window

基于极简UI框架实现的现代化聊天界面
"""

import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent/client')

from typing import List, Dict, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QScrollArea, QFrame,
    QToolButton, QSplitter, QSizePolicy, QLineEdit,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QMimeData
from PyQt6.QtGui import QTextCursor, QDragEnterEvent, QDropEvent

from business.function_knowledge import get_knowledge_base, FunctionModule
from presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory, MinimalLayout
)
from presentation.components.voice_input import VoiceInputWidget
from presentation.components.loading_animation import LoadingSpinner, AnimationType
from presentation.components.task_widget import Task, TaskListWidget, create_sample_tasks


class MessageBubble(QFrame):
    """极简消息气泡"""
    
    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        role_label = UIComponentFactory.create_label(
            self, 
            "🧑 用户" if self.role == "user" else "🤖 助手",
            ColorScheme.TEXT_SECONDARY,
            11
        )
        layout.addWidget(role_label)
        
        content_label = UIComponentFactory.create_label(
            self,
            self.content,
            ColorScheme.TEXT_PRIMARY,
            14
        )
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        if self.role == "user":
            self.setStyleSheet("""
                QFrame {
                    background-color: #3B82F6;
                    border-radius: 16px;
                    margin-left: 40px;
                }
                QLabel {
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 16px;
                    margin-right: 40px;
                }
            """)


class ChatArea(QWidget):
    """聊天区域"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #FAFAFA;
            }
        """)
        
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()
        
        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, 1)
    
    def add_message(self, role: str, content: str):
        bubble = MessageBubble(role, content)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()
    
    def add_loading_indicator(self):
        loading_frame = QFrame()
        loading_layout = QHBoxLayout(loading_frame)
        loading_layout.setContentsMargins(0, 16, 0, 16)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = LoadingSpinner()
        spinner.set_size(32)
        spinner.set_animation_type(AnimationType.SPINNER)
        
        loading_layout.addWidget(spinner)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, loading_frame)
        self._scroll_to_bottom()
        
        return loading_frame
    
    def remove_loading_indicator(self, frame: QFrame):
        if frame:
            frame.deleteLater()
    
    def add_task_list(self, tasks: List[Task]):
        task_list = TaskListWidget(tasks)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, task_list)
        self._scroll_to_bottom()
    
    def _scroll_to_bottom(self):
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))


class CommandPalettePopup(QFrame):
    """命令面板弹窗"""
    
    command_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 2px solid #E5E7EB;
                border-radius: 12px;
                padding: 8px;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
    
    def show_suggestions(self, suggestions: List[Dict[str, Any]], position: QPoint):
        while self.layout.count() > 0:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for suggestion in suggestions:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(12, 8, 12, 8)
            item_layout.setSpacing(12)
            
            cmd_label = UIComponentFactory.create_label(
                item_widget,
                suggestion.get("shortcut", ""),
                ColorScheme.PRIMARY,
                14
            )
            
            desc_label = UIComponentFactory.create_label(
                item_widget,
                suggestion.get("description", ""),
                ColorScheme.TEXT_SECONDARY,
                13
            )
            
            item_layout.addWidget(cmd_label)
            item_layout.addWidget(desc_label)
            item_layout.addStretch()
            
            item_widget.setStyleSheet("""
                QWidget:hover {
                    background-color: #FAFAFA;
                    border-radius: 8px;
                }
            """)
            
            item_widget.mousePressEvent = lambda e, s=suggestion: self._on_selected(s)
            
            self.layout.addWidget(item_widget)
        
        self.adjustSize()
        self.move(position)
        self.show()
    
    def _on_selected(self, suggestion: Dict[str, Any]):
        self.command_selected.emit(suggestion.get("shortcut", ""))
        self.hide()


class ChatInputArea(QWidget):
    """聊天输入区域"""
    
    message_sent = pyqtSignal(str)
    file_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.knowledge_base = get_knowledge_base()
        self.command_popup = CommandPalettePopup(self)
        self.command_popup.command_selected.connect(self._on_command_selected)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(Spacing.MD)
        
        self.drop_zone = QFrame()
        self.drop_zone.setFixedSize(44, 44)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_label = QLabel("📁")
        drop_label.setStyleSheet("font-size: 20px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_label)
        
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.dragEnterEvent = self._on_drag_enter
        self.drop_zone.dragLeaveEvent = self._on_drag_leave
        self.drop_zone.dropEvent = self._on_drop
        
        layout.addWidget(self.drop_zone)
        
        cmd_btn = UIComponentFactory.create_button(
            self, "/", variant="secondary", size="sm"
        )
        cmd_btn.setFixedSize(44, 44)
        cmd_btn.clicked.connect(self._show_command_palette)
        layout.addWidget(cmd_btn)
        
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.setMaximumHeight(100)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #3B82F6;
                outline: none;
            }
        """)
        self.input_field.keyPressEvent = self._on_key_press
        self.input_field.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input_field, 1)
        
        self.voice_input = VoiceInputWidget()
        self.voice_input.setFixedSize(44, 44)
        layout.addWidget(self.voice_input)
        
        self.send_btn = UIComponentFactory.create_button(
            self, "发送", variant="primary", size="md"
        )
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)
    
    def _on_key_press(self, event):
        from PyQt6.QtGui import QKeyEvent
        
        if isinstance(event, QKeyEvent):
            if event.key() in (16777221, 16777220) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._send_message()
                return
            if event.key() in (16777221, 16777220) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return
            if event.key() == 16777216 and self.command_popup.isVisible():
                self.command_popup.hide()
                return
        
        QTextEdit.keyPressEvent(self.input_field, event)
    
    def _on_text_changed(self):
        text = self.input_field.toPlainText().strip()
        
        if text.startswith("/"):
            suggestions = self.knowledge_base.suggest_commands(text)
            if suggestions:
                suggestion_list = []
                for cmd in suggestions:
                    help_info = self.knowledge_base.get_command_help(cmd)
                    description = ""
                    if help_info:
                        lines = help_info.split("\n")
                        for line in lines:
                            if "描述 / Description" in line:
                                description = line.split(":")[1].strip()
                                break
                    
                    suggestion_list.append({
                        "shortcut": cmd,
                        "description": description
                    })
                
                cursor_rect = self.input_field.cursorRect()
                global_pos = self.input_field.mapToGlobal(cursor_rect.bottomLeft())
                self.command_popup.show_suggestions(suggestion_list, global_pos)
            else:
                self.command_popup.hide()
        else:
            self.command_popup.hide()
    
    def _send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        
        if text.startswith("/"):
            cmd_parts = text.split()
            cmd = cmd_parts[0]
            
            if len(cmd_parts) == 1:
                help_info = self.knowledge_base.get_command_help(cmd)
                if help_info:
                    self.message_sent.emit(f"show_help:{help_info}")
                else:
                    all_commands = self.knowledge_base.format_all_command_help()
                    self.message_sent.emit(f"show_help:{all_commands}")
                self.input_field.clear()
                return
        
        self.message_sent.emit(text)
        self.input_field.clear()
    
    def _show_command_palette(self):
        self.input_field.insertPlainText("/")
        self.input_field.setFocus()
    
    def _on_command_selected(self, command: str):
        self.input_field.setPlainText(command + " ")
        self.input_field.setFocus()
    
    def _on_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.setStyleSheet("""
                QFrame {
                    background-color: rgba(59, 130, 246, 0.1);
                    border: 2px dashed #3B82F6;
                    border-radius: 12px;
                }
            """)
    
    def _on_drag_leave(self, event: QDragEnterEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
    
    def _on_drop(self, event: QDropEvent):
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            files = [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]
            if files:
                self.file_dropped.emit(files)
        
        event.acceptProposedAction()


class MinimalChatWindow(QWidget):
    """极简聊天窗口主组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FAFAFA;
                font-family: 'Segoe UI', 'PingFang SC', -apple-system, sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        title_bar = QFrame()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_layout.setSpacing(12)
        
        title_label = UIComponentFactory.create_label(
            title_bar, "💬 智能对话", ColorScheme.TEXT_PRIMARY, 16
        )
        
        subtitle_label = UIComponentFactory.create_label(
            title_bar, "基于AI的智能助手", ColorScheme.TEXT_SECONDARY, 12
        )
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()
        
        settings_btn = QToolButton()
        settings_btn.setText("⚙️")
        settings_btn.setStyleSheet("font-size: 18px;")
        title_layout.addWidget(settings_btn)
        
        layout.addWidget(title_bar)
        
        self.chat_area = ChatArea()
        layout.addWidget(self.chat_area, 1)
        
        self.input_area = ChatInputArea()
        self.input_area.message_sent.connect(self._on_message_sent)
        self.input_area.file_dropped.connect(self._on_files_dropped)
        
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E5E7EB;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.input_area)
        
        layout.addWidget(input_frame)
    
    def _on_message_sent(self, text: str):
        if text.startswith("show_help:"):
            help_content = text.replace("show_help:", "")
            self.chat_area.add_message("assistant", help_content)
        else:
            self.chat_area.add_message("user", text)
            
            loading_frame = self.chat_area.add_loading_indicator()
            
            QTimer.singleShot(2000, lambda: self._simulate_response(loading_frame))
    
    def _on_files_dropped(self, files: List[str]):
        for file_path in files[:3]:
            if os.path.isfile(file_path):
                ext = Path(file_path).suffix.lower()
                image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.svg']
                
                if ext in image_exts:
                    self.chat_area.add_message("user", f"📷 图片: {Path(file_path).name}")
                else:
                    self.chat_area.add_message("user", f"📄 文件: {Path(file_path).name}")
            elif os.path.isdir(file_path):
                self.chat_area.add_message("user", f"📂 文件夹: {Path(file_path).name}")
    
    def _simulate_response(self, loading_frame):
        self.chat_area.remove_loading_indicator(loading_frame)
        
        sample_response = "这是一个示例响应。我可以帮助您：\n\n"
        sample_response += "- 执行深度搜索\n"
        sample_response += "- 训练AI专家\n"
        sample_response += "- 创作内容\n"
        sample_response += "- 生成代码\n"
        sample_response += "\n输入 `/` 查看所有可用命令。"
        
        self.chat_area.add_message("assistant", sample_response)


import os

if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent/client')
    
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = MinimalChatWindow()
    window.setWindowTitle("极简聊天窗口")
    window.resize(800, 600)
    window.show()
    
    sys.exit(app.exec())