"""
去中心化论坛 - PyQt6 UI 面板
三栏布局: 话题列表 | 帖子列表 | 帖子详情

参考: Element/Discord/Telegram 风格
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QTextEdit, QLineEdit, QTabWidget, QScrollArea,
    QFrame, QSizePolicy, QSpacerItem, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QCheckBox, QProgressBar, QToolButton, QMenu
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QAction, QIcon, QTextCursor

try:
    from ..unified_chat.status_monitor import get_status_monitor
except ImportError:
    get_status_monitor = None


class TopicListWidget(QListWidget):
    """话题列表"""

    topic_selected = pyqtSignal(str)  # topic_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(2)
        self.setMinimumWidth(180)
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item):
        topic_id = item.data(Qt.ItemDataRole.UserRole)
        if topic_id:
            self.topic_selected.emit(topic_id)

    def add_topic(self, topic_id: str, name: str, icon: str = "📋",
                  post_count: int = 0, is_subscribed: bool = False):
        """添加话题项"""
        item = QListWidgetItem()
        widget = TopicItemWidget(
            name=name, icon=icon, post_count=post_count,
            is_subscribed=is_subscribed
        )
        item.setData(Qt.ItemDataRole.UserRole, topic_id)
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

    def clear_topics(self):
        """清空话题"""
        self.clear()


class TopicItemWidget(QFrame):
    """话题项组件"""

    def __init__(self, name: str, icon: str = "📋",
                 post_count: int = 0, is_subscribed: bool = False):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                padding: 8px;
            }
            QFrame:hover {
                background: rgba(74, 144, 217, 0.1);
                border-radius: 6px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("", 16))
        layout.addWidget(icon_label)

        # 名称
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #2C3E50; font-weight: 500;")
        layout.addWidget(name_label, 1)

        # 帖子数
        if post_count > 0:
            count_label = QLabel(f"({post_count})")
            count_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
            layout.addWidget(count_label)

        # 订阅标识
        if is_subscribed:
            sub_label = QLabel("✓")
            sub_label.setStyleSheet("color: #27AE60; font-weight: bold;")
            layout.addWidget(sub_label)


class PostListWidget(QListWidget):
    """帖子列表"""

    post_selected = pyqtSignal(str)  # post_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSpacing(3)
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item):
        post_id = item.data(Qt.ItemDataRole.UserRole)
        if post_id:
            self.post_selected.emit(post_id)

    def add_post(self, post_id: str, title: str, author: str,
                 preview: str, upvotes: int, downvotes: int,
                 reply_count: int, created_at: float, tags: List[str] = None):
        """添加帖子项"""
        item = QListWidgetItem()
        widget = PostItemWidget(
            title=title, author=author, preview=preview,
            upvotes=upvotes, downvotes=downvotes,
            reply_count=reply_count, created_at=created_at,
            tags=tags or []
        )
        item.setData(Qt.ItemDataRole.UserRole, post_id)
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

    def clear_posts(self):
        """清空帖子"""
        self.clear()


class PostItemWidget(QFrame):
    """帖子项组件"""

    def __init__(self, title: str, author: str, preview: str,
                 upvotes: int, downvotes: int, reply_count: int,
                 created_at: float, tags: List[str]):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #4A90D9;
                background: #F8F9FA;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 标题行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2C3E50;")
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label, 1)

        # 标签
        for tag in tags[:2]:
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("""
                background: #E8F4FD;
                color: #4A90D9;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
            """)
            title_layout.addWidget(tag_label)

        layout.addLayout(title_layout)

        # 预览
        preview_label = QLabel(preview[:80] + "..." if len(preview) > 80 else preview)
        preview_label.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        preview_label.setWordWrap(True)
        layout.addWidget(preview_label)

        # 元信息行
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        # 作者
        author_label = QLabel(f"👤 {author}")
        author_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
        meta_layout.addWidget(author_label)

        # 时间
        time_str = self._format_time(created_at)
        time_label = QLabel(f"🕐 {time_str}")
        time_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
        meta_layout.addWidget(time_label)

        meta_layout.addStretch()

        # 投票
        vote_layout = QHBoxLayout()
        vote_layout.setSpacing(4)

        up_label = QLabel(f"👍 {upvotes}")
        up_label.setStyleSheet("color: #27AE60; font-size: 11px;")
        vote_layout.addWidget(up_label)

        down_label = QLabel(f"👎 {downvotes}")
        down_label.setStyleSheet("color: #E74C3C; font-size: 11px;")
        vote_layout.addWidget(down_label)

        meta_layout.addLayout(vote_layout)

        # 回复
        reply_label = QLabel(f"💬 {reply_count}")
        reply_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
        meta_layout.addWidget(reply_label)

        layout.addLayout(meta_layout)

    def _format_time(self, timestamp: float) -> str:
        """格式化时间"""
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"


class PostDetailWidget(QFrame):
    """帖子详情组件"""

    reply_clicked = pyqtSignal(str)  # post_id
    vote_clicked = pyqtSignal(str, bool)  # post_id, is_upvote

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_post_id = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: white;
                border-left: 1px solid #E0E0E0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 内容widget
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 输入区域
        self.input_frame = QFrame()
        self.input_frame.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border-top: 1px solid #E0E0E0;
                padding: 10px;
            }
        """)
        input_layout = QVBoxLayout(self.input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.reply_input = QTextEdit()
        self.reply_input.setPlaceholderText("写下你的回复...")
        self.reply_input.setMaximumHeight(100)
        self.reply_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
                background: white;
            }
        """)
        input_layout.addWidget(self.reply_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.send_btn = QPushButton("发送回复")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #4A90D9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #357ABD;
            }
        """)
        self.send_btn.clicked.connect(self._on_send_reply)
        btn_layout.addWidget(self.send_btn)

        input_layout.addLayout(btn_layout)
        layout.addWidget(self.input_frame)

        # 默认空白状态
        self._show_empty()

    def _show_empty(self):
        """显示空白状态"""
        self._clear_content()
        empty_label = QLabel("选择一个帖子查看详情")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #95A5A6; font-size: 14px; padding: 40px;")
        self.content_layout.addWidget(empty_label)
        self.input_frame.hide()

    def _clear_content(self):
        """清空内容"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def set_post(self, post):
        """设置帖子内容"""
        self.current_post_id = post.post_id
        self._clear_content()

        # 标题
        title_label = QLabel(post.title)
        title_label.setFont(QFont("", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2C3E50; padding: 15px 15px 5px;")
        title_label.setWordWrap(True)
        self.content_layout.addWidget(title_label)

        # 元信息
        meta_label = QLabel(
            f"👤 {post.author.display_name}  🕐 {self._format_time(post.created_at)}  💬 {post.reply_count} 回复  👁️ {post.view_count} 浏览"
        )
        meta_label.setStyleSheet("color: #95A5A6; font-size: 12px; padding: 0 15px;")
        self.content_layout.addWidget(meta_label)

        # 标签
        if post.tags:
            tags_layout = QHBoxLayout()
            tags_layout.setSpacing(6)
            tags_layout.addWidget(QLabel("标签:"))
            for tag in post.tags:
                tag_label = QLabel(tag)
                tag_label.setStyleSheet("""
                    background: #E8F4FD;
                    color: #4A90D9;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                """)
                tags_layout.addWidget(tag_label)
            tags_layout.addStretch()
            tags_layout_widget = QWidget()
            tags_layout_widget.setLayout(tags_layout)
            tags_layout_widget.setStyleSheet("padding: 5px 15px;")
            self.content_layout.addWidget(tags_layout_widget)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #E0E0E0; margin: 10px 15px;")
        self.content_layout.addWidget(line)

        # 内容
        content_label = QLabel(post.content.text)
        content_label.setStyleSheet("""
            color: #333;
            font-size: 13px;
            line-height: 1.6;
            padding: 10px 15px;
        """)
        content_label.setWordWrap(True)
        self.content_layout.addWidget(content_label)

        # 投票栏
        vote_frame = QFrame()
        vote_frame.setStyleSheet("""
            background: #F8F9FA;
            border-radius: 8px;
            margin: 10px 15px;
            padding: 10px;
        """)
        vote_layout = QHBoxLayout(vote_frame)
        vote_layout.setContentsMargins(10, 5, 10, 5)

        vote_layout.addStretch()

        self.up_btn = QPushButton(f"👍 顶 ({post.upvotes})")
        self.up_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 6px 12px;
                color: #27AE60;
            }
            QPushButton:hover {
                background: #E8F8E8;
            }
        """)
        self.up_btn.clicked.connect(lambda: self.vote_clicked.emit(self.current_post_id, True))
        vote_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton(f"👎 踩 ({post.downvotes})")
        self.down_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 6px 12px;
                color: #E74C3C;
            }
            QPushButton:hover {
                background: #F8E8E8;
            }
        """)
        self.down_btn.clicked.connect(lambda: self.vote_clicked.emit(self.current_post_id, False))
        vote_layout.addWidget(self.down_btn)

        self.content_layout.addWidget(vote_frame)

        # 回复区域标题
        replies_title = QLabel("💬 回复")
        replies_title.setFont(QFont("", 11, QFont.Weight.Bold))
        replies_title.setStyleSheet("color: #2C3E50; padding: 15px 15px 5px;")
        self.content_layout.addWidget(replies_title)

        # 显示输入框
        self.input_frame.show()

    def set_replies(self, replies: List):
        """显示回复列表"""
        # 在输入框之前添加回复
        for reply in replies:
            reply_widget = self._create_reply_widget(reply)
            self.content_layout.insertWidget(self.content_layout.count() - 1, reply_widget)

    def _create_reply_widget(self, reply):
        """创建回复组件"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                margin: 5px 15px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 头部
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        avatar_label = QLabel("👤")
        avatar_label.setFont(QFont("", 12))
        header_layout.addWidget(avatar_label)

        name_label = QLabel(reply.author.display_name)
        name_label.setStyleSheet("color: #2C3E50; font-weight: 500; font-size: 12px;")
        header_layout.addWidget(name_label)

        time_label = QLabel(self._format_time(reply.created_at))
        time_label.setStyleSheet("color: #BDC3C7; font-size: 11px;")
        header_layout.addWidget(time_label)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 内容
        content_label = QLabel(reply.content.text)
        content_label.setStyleSheet("color: #333; font-size: 12px; line-height: 1.5;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        # 操作
        ops_layout = QHBoxLayout()
        ops_layout.addStretch()

        up_label = QLabel(f"👍 {reply.upvotes}")
        up_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
        ops_layout.addWidget(up_label)

        down_label = QLabel(f"👎 {reply.downvotes}")
        down_label.setStyleSheet("color: #95A5A6; font-size: 11px;")
        ops_layout.addWidget(down_label)

        layout.addLayout(ops_layout)

        return frame

    def _on_send_reply(self):
        """发送回复"""
        if self.current_post_id:
            content = self.reply_input.toPlainText().strip()
            if content:
                self.reply_clicked.emit(self.current_post_id)
                self.reply_input.clear()

    def _format_time(self, timestamp: float) -> str:
        """格式化时间"""
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"


class CreatePostDialog(QDialog):
    """创建帖子对话框"""

    def __init__(self, topics: List, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发布新帖")
        self.setMinimumWidth(500)
        self.topics = topics
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入帖子标题...")
        form.addRow("标题:", self.title_input)

        # 话题选择
        self.topic_combo = QComboBox()
        for topic in self.topics:
            self.topic_combo.addItem(f"{topic.icon} {topic.name}", topic.topic_id)
        form.addRow("话题:", self.topic_combo)

        # 标签
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("标签, 用逗号分隔...")
        form.addRow("标签:", self.tags_input)

        layout.addLayout(form)

        # 内容
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("写下你的内容...")
        self.content_input.setMinimumHeight(200)
        layout.addWidget(QLabel("内容:"))
        layout.addWidget(self.content_input)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> Dict:
        """获取数据"""
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        return {
            "title": self.title_input.text().strip(),
            "topic_id": self.topic_combo.currentData(),
            "content": self.content_input.toPlainText().strip(),
            "tags": tags
        }


class ForumPanel(QWidget):
    """
    去中心化论坛主面板

    三栏布局:
    - 左: 话题列表
    - 中: 帖子列表
    - 右: 帖子详情
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.forum_hub = None
        self.current_topic_id = None
        self.current_post_id = None
        self._setup_ui()
        self._init_forum()

    def _setup_ui(self):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左栏: 话题列表
        left_panel = QFrame()
        left_panel.setStyleSheet("background: #F5F6F7; border-right: 1px solid #E0E0E0;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # 搜索
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索帖子...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px 12px;
                background: white;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        left_layout.addWidget(self.search_input)

        # 新帖按钮
        self.new_post_btn = QPushButton("+ 发布新帖")
        self.new_post_btn.setStyleSheet("""
            QPushButton {
                background: #4A90D9;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: 500;
                margin: 8px 0;
            }
            QPushButton:hover {
                background: #357ABD;
            }
        """)
        self.new_post_btn.clicked.connect(self._on_new_post)
        left_layout.addWidget(self.new_post_btn)

        # 话题列表
        left_layout.addWidget(QLabel("📋 话题"))
        self.topic_list = TopicListWidget()
        self.topic_list.topic_selected.connect(self._on_topic_selected)
        left_layout.addWidget(self.topic_list)

        # 中栏: 帖子列表
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(10, 10, 10, 10)

        self.post_list = PostListWidget()
        self.post_list.post_selected.connect(self._on_post_selected)
        center_layout.addWidget(self.post_list)

        # 右栏: 帖子详情
        self.post_detail = PostDetailWidget()
        self.post_detail.reply_clicked.connect(self._on_reply)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.post_detail)

        splitter.setStretchFactor(0, 1)  # 话题列表
        splitter.setStretchFactor(1, 2)  # 帖子列表
        splitter.setStretchFactor(2, 3)  # 详情

        splitter.setSizes([180, 300, 450])

        layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QFrame()
        self.status_bar.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border-top: 1px solid #E0E0E0;
                padding: 6px 15px;
            }
        """)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("🌐 去中心化论坛 | 离线模式")
        self.status_label.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        layout.addWidget(self.status_bar)

    async def _init_forum(self):
        """初始化论坛"""
        try:
            from .business.forum import get_forum_hub_async
            self.forum_hub = await get_forum_hub_async()

            # 加载话题
            self._load_topics()

            # 注册回调
            self.forum_hub.add_ui_callback("post_created", self._on_forum_post_created)
            self.forum_hub.add_ui_callback("new_post_received", self._on_forum_post_received)

            # 加载所有帖子
            self._load_posts()

            self.status_label.setText("🌐 去中心化论坛 | 已连接")
        except Exception as e:
            self.status_label.setText(f"🌐 去中心化论坛 | 初始化失败: {e}")

    def _load_topics(self):
        """加载话题"""
        self.topic_list.clear_topics()

        # 添加默认话题
        default_topics = [
            ("topic_general", "综合讨论", "📋", 0),
            ("topic_tech", "技术交流", "💻", 0),
            ("topic_ai", "AI & 具身智能", "🤖", 0),
            ("topic_creative", "创意写作", "✍️", 0),
        ]

        for topic_id, name, icon, count in default_topics:
            self.topic_list.add_topic(topic_id, name, icon, count)

        # 如果有更多话题
        if self.forum_hub:
            topics = self.forum_hub.get_all_topics()
            for topic in topics:
                self.topic_list.add_topic(
                    topic.topic_id, topic.name, topic.icon,
                    topic.post_count, self.forum_hub.is_subscribed(topic.topic_id)
                )

    def _load_posts(self, topic_id: str = None):
        """加载帖子"""
        self.post_list.clear_posts()

        if not self.forum_hub:
            return

        posts = self.forum_hub.get_posts(topic_id=topic_id, limit=50)

        for post in posts:
            self.post_list.add_post(
                post.post_id,
                post.title,
                post.author.display_name,
                post.content.text,
                post.upvotes,
                post.downvotes,
                post.reply_count,
                post.created_at,
                post.tags
            )

    @pyqtSlot(str)
    def _on_topic_selected(self, topic_id: str):
        """话题选中"""
        self.current_topic_id = topic_id
        self.current_post_id = None
        self._load_posts(topic_id)

    @pyqtSlot(str)
    def _on_post_selected(self, post_id: str):
        """帖子选中"""
        self.current_post_id = post_id

        if not self.forum_hub:
            return

        post = self.forum_hub.get_post(post_id)
        if post:
            # 增加浏览
            self.forum_hub.increment_post_views(post_id)

            # 显示详情
            self.post_detail.set_post(post)

            # 加载回复
            replies = self.forum_hub.get_replies(post_id)
            self.post_detail.set_replies(replies)

    @pyqtSlot(str)
    def _on_reply(self, post_id: str):
        """回复帖子"""
        if not self.forum_hub:
            return

        content = self.post_detail.reply_input.toPlainText().strip()
        if content and self.current_post_id:
            asyncio.create_task(self.forum_hub.create_reply(self.current_post_id, content))
            self.post_detail.reply_input.clear()

            # 刷新
            replies = self.forum_hub.get_replies(self.current_post_id)
            self.post_detail.set_replies(replies)

    def _on_new_post(self):
        """新建帖子"""
        if not self.forum_hub:
            return

        topics = self.forum_hub.get_all_topics()
        dialog = CreatePostDialog(topics, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"] and data["content"]:
                asyncio.create_task(
                    self.forum_hub.create_post(
                        topic_id=data["topic_id"],
                        title=data["title"],
                        content=data["content"],
                        tags=data["tags"]
                    )
                )
                # 刷新
                self._load_posts(self.current_topic_id)

    def _on_search(self):
        """搜索帖子"""
        query = self.search_input.text().strip()
        if not query or not self.forum_hub:
            self._load_posts(self.current_topic_id)
            return

        self.post_list.clear_posts()
        posts = self.forum_hub.search_posts(query)

        for post in posts:
            self.post_list.add_post(
                post.post_id,
                post.title,
                post.author.display_name,
                post.content.text,
                post.upvotes,
                post.downvotes,
                post.reply_count,
                post.created_at,
                post.tags
            )

    def _on_forum_post_created(self, post):
        """论坛帖子创建回调"""
        self._load_posts(self.current_topic_id)

    def _on_forum_post_received(self, post, msg):
        """收到远程帖子"""
        self._load_posts(self.current_topic_id)
