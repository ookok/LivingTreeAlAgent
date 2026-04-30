"""
论坛窗口 - Forum

支持：
- 帖子列表浏览
- 帖子详情查看
- 发帖功能
- 评论互动
"""

from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QDialog, QTabWidget, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class PostCard(QFrame):
    """帖子卡片"""
    
    post_selected = pyqtSignal(dict)
    
    def __init__(self, post: Dict, parent=None):
        super().__init__(parent)
        self._post = post
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #3B82F6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # 标题
        title_label = UIComponentFactory.create_label(
            self, self._post["title"], ColorScheme.TEXT_PRIMARY, 14
        )
        title_label.setStyleSheet("font-weight: bold;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # 内容预览
        content_preview = self._post["content"][:100] + "..." if len(self._post["content"]) > 100 else self._post["content"]
        content_label = UIComponentFactory.create_label(
            self, content_preview, ColorScheme.TEXT_SECONDARY, 13
        )
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        # 元信息
        meta_layout = QHBoxLayout()
        
        author_label = QLabel(f"👤 {self._post['author']}")
        author_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(author_label)
        
        meta_layout.addStretch()
        
        time_label = QLabel(f"🕐 {self._post['time']}")
        time_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(time_label)
        
        comments_label = QLabel(f"💬 {self._post['comments']}")
        comments_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(comments_label)
        
        layout.addLayout(meta_layout)
    
    def mousePressEvent(self, event):
        self.post_selected.emit(self._post)


class ForumWindow(QWidget):
    """论坛主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._posts = self._load_posts()
        self._setup_ui()
    
    def _load_posts(self) -> List[Dict]:
        """加载帖子列表"""
        return [
            {
                "id": 1,
                "title": "【讨论】AI大模型的未来发展方向",
                "content": "随着GPT-4等大模型的发布，AI技术正在飞速发展。大家认为未来AI会向哪个方向发展呢？欢迎讨论！",
                "author": "AI爱好者",
                "time": "2小时前",
                "comments": 24,
                "category": "技术讨论"
            },
            {
                "id": 2,
                "title": "分享一个好用的Python学习资源",
                "content": "推荐一个非常棒的Python学习网站，从入门到进阶都有详细的教程，适合新手学习。",
                "author": "编程新手",
                "time": "5小时前",
                "comments": 12,
                "category": "资源分享"
            },
            {
                "id": 3,
                "title": "求助：如何优化深度学习模型的训练速度？",
                "content": "最近在训练一个深度学习模型，速度很慢，请问有什么好的优化方法吗？",
                "author": "数据科学家",
                "time": "昨天",
                "comments": 18,
                "category": "问题求助"
            }
        ]
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FAFAFA;
                font-family: 'Segoe UI', 'PingFang SC', sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
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
        
        title_label = UIComponentFactory.create_label(
            title_bar, "💬 论坛", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        
        # 分类筛选
        category_combo = QComboBox()
        category_combo.addItems(["全部", "技术讨论", "资源分享", "问题求助", "经验交流"])
        category_combo.setStyleSheet("""
            QComboBox {
                background-color: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        title_layout.addWidget(category_combo)
        
        title_layout.addStretch()
        
        # 发帖按钮
        post_btn = UIComponentFactory.create_button(
            title_bar, "发帖", variant="primary", size="sm"
        )
        post_btn.clicked.connect(self._create_post)
        title_layout.addWidget(post_btn)
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 帖子列表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        posts_widget = QWidget()
        posts_layout = QVBoxLayout(posts_widget)
        posts_layout.setSpacing(12)
        
        for post in self._posts:
            card = PostCard(post)
            card.post_selected.connect(self._on_post_selected)
            posts_layout.addWidget(card)
        
        scroll_area.setWidget(posts_widget)
        main_layout.addWidget(scroll_area, 1)
        
        # 侧边栏
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        
        # 热门帖子
        hot_card = MinimalCard()
        hot_layout = hot_card.layout()
        
        hot_title = UIComponentFactory.create_label(
            hot_card, "🔥 热门帖子", ColorScheme.TEXT_PRIMARY, 14
        )
        hot_layout.addWidget(hot_title)
        
        hot_list = QListWidget()
        hot_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #F3F4F6;
            }
        """)
        
        hot_posts = ["AI大模型讨论", "Python学习资源", "深度学习优化"]
        for post in hot_posts:
            item = QListWidgetItem(post)
            hot_list.addItem(item)
        
        hot_layout.addWidget(hot_list)
        sidebar_layout.addWidget(hot_card)
        
        # 在线用户
        online_card = MinimalCard()
        online_layout = online_card.layout()
        
        online_title = UIComponentFactory.create_label(
            online_card, "👥 在线用户", ColorScheme.TEXT_PRIMARY, 14
        )
        online_layout.addWidget(online_title)
        
        online_users = ["张三", "李四", "王五", "赵六"]
        for user in online_users:
            user_label = QLabel(f"● {user}")
            user_label.setStyleSheet("font-size: 13px; color: #10B981;")
            online_layout.addWidget(user_label)
        
        sidebar_layout.addWidget(online_card)
        
        main_layout.addWidget(sidebar)
        
        layout.addWidget(main_content, 1)
    
    def _on_post_selected(self, post: Dict):
        """帖子选中处理"""
        dialog = QDialog(self)
        dialog.setWindowTitle(post["title"])
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout(dialog)
        
        # 帖子内容
        content_text = QTextEdit()
        content_text.setPlainText(post["content"])
        content_text.setReadOnly(True)
        content_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: none;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        layout.addWidget(content_text)
        
        # 评论区
        comments_label = UIComponentFactory.create_label(
            dialog, f"评论 ({post['comments']})", ColorScheme.TEXT_PRIMARY, 14
        )
        layout.addWidget(comments_label)
        
        comment_input = QTextEdit()
        comment_input.setPlaceholderText("写下你的评论...")
        comment_input.setMaximumHeight(80)
        layout.addWidget(comment_input)
        
        submit_btn = UIComponentFactory.create_button(
            dialog, "发表评论", variant="primary", size="sm"
        )
        layout.addWidget(submit_btn)
        
        dialog.exec()
    
    def _create_post(self):
        """发帖"""
        dialog = QDialog(self)
        dialog.setWindowTitle("发帖")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        title_input = QLineEdit()
        title_input.setPlaceholderText("标题")
        layout.addWidget(title_input)
        
        category_combo = QComboBox()
        category_combo.addItems(["技术讨论", "资源分享", "问题求助", "经验交流"])
        layout.addWidget(category_combo)
        
        content_text = QTextEdit()
        content_text.setPlaceholderText("内容...")
        layout.addWidget(content_text)
        
        submit_btn = UIComponentFactory.create_button(
            dialog, "发布", variant="primary", size="md"
        )
        layout.addWidget(submit_btn)
        
        dialog.exec()