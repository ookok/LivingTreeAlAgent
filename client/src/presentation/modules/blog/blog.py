"""
博客窗口 - Blog

支持：
- 博客文章浏览
- 文章分类
- 文章详情
- 评论功能
"""

from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class BlogPost(QFrame):
    """博客文章卡片"""
    
    post_selected = pyqtSignal(dict)
    
    def __init__(self, post: Dict, parent=None):
        super().__init__(parent)
        self._post = post
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
            }
        """)
        
        # 分类标签
        category_label = QLabel(f"#{self._post['category']}")
        category_label.setStyleSheet("""
            QLabel {
                background-color: #DBEAFE;
                color: #1D4ED8;
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 12px;
            }
        """)
        layout.addWidget(category_label)
        
        # 标题
        title_label = UIComponentFactory.create_label(
            self, self._post["title"], ColorScheme.TEXT_PRIMARY, 18
        )
        title_label.setStyleSheet("font-weight: bold;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # 摘要
        excerpt_label = UIComponentFactory.create_label(
            self, self._post["excerpt"], ColorScheme.TEXT_SECONDARY, 14
        )
        excerpt_label.setWordWrap(True)
        layout.addWidget(excerpt_label)
        
        # 元信息
        meta_layout = QHBoxLayout()
        
        author_label = QLabel(f"👤 {self._post['author']}")
        author_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(author_label)
        
        meta_layout.addStretch()
        
        date_label = QLabel(f"📅 {self._post['date']}")
        date_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(date_label)
        
        read_time_label = QLabel(f"⏱️ {self._post['read_time']}分钟阅读")
        read_time_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        meta_layout.addWidget(read_time_label)
        
        layout.addLayout(meta_layout)
    
    def mousePressEvent(self, event):
        self.post_selected.emit(self._post)


class BlogWindow(QWidget):
    """博客主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._posts = self._load_posts()
        self._setup_ui()
    
    def _load_posts(self) -> List[Dict]:
        """加载博客文章"""
        return [
            {
                "id": 1,
                "title": "深入理解Python装饰器：从入门到精通",
                "excerpt": "装饰器是Python中非常强大的特性，可以在不修改函数代码的情况下扩展其功能。本文将从基础概念开始，深入讲解装饰器的原理和应用。",
                "content": "装饰器是Python中用于修改函数或类行为的一种设计模式...",
                "author": "编程达人",
                "date": "2024-01-15",
                "read_time": "15",
                "category": "Python"
            },
            {
                "id": 2,
                "title": "AI时代的编程：如何与AI协作提高效率",
                "excerpt": "随着AI技术的发展，程序员如何与AI工具协作成为一个重要话题。本文分享一些实用技巧，帮助你更好地利用AI提升编程效率。",
                "content": "在AI时代，编程方式正在发生变革...",
                "author": "AI研究员",
                "date": "2024-01-14",
                "read_time": "12",
                "category": "AI"
            },
            {
                "id": 3,
                "title": "数据可视化入门：使用Matplotlib绘制精美图表",
                "excerpt": "数据可视化是数据科学中不可或缺的一部分。本文介绍如何使用Matplotlib创建各种类型的图表，让你的数据故事更加生动。",
                "content": "数据可视化是将数据转化为图形的过程...",
                "author": "数据工程师",
                "date": "2024-01-13",
                "read_time": "18",
                "category": "数据科学"
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
            title_bar, "📝 博客", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        
        # 搜索框
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索文章...")
        search_input.setStyleSheet("""
            QLineEdit {
                background-color: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        search_input.setFixedWidth(200)
        title_layout.addWidget(search_input)
        
        title_layout.addStretch()
        
        # 写文章按钮
        write_btn = UIComponentFactory.create_button(
            title_bar, "写文章", variant="primary", size="sm"
        )
        write_btn.clicked.connect(self._write_post)
        title_layout.addWidget(write_btn)
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 文章列表
        articles_area = QWidget()
        articles_layout = QVBoxLayout(articles_area)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        posts_grid = QWidget()
        grid_layout = QGridLayout(posts_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(16)
        
        for i, post in enumerate(self._posts):
            card = BlogPost(post)
            card.post_selected.connect(self._on_post_selected)
            grid_layout.addWidget(card, i // 2, i % 2)
        
        scroll_area.setWidget(posts_grid)
        articles_layout.addWidget(scroll_area)
        
        main_layout.addWidget(articles_area, 1)
        
        # 侧边栏
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        
        # 分类
        category_card = MinimalCard()
        category_layout = category_card.layout()
        
        category_title = UIComponentFactory.create_label(
            category_card, "📁 分类", ColorScheme.TEXT_PRIMARY, 14
        )
        category_layout.addWidget(category_title)
        
        categories = ["Python", "AI", "数据科学", "前端开发", "后端开发"]
        for category in categories:
            cat_btn = UIComponentFactory.create_button(
                category_card, category, variant="secondary", size="sm"
            )
            category_layout.addWidget(cat_btn)
        
        sidebar_layout.addWidget(category_card)
        
        # 标签云
        tags_card = MinimalCard()
        tags_layout = tags_card.layout()
        
        tags_title = UIComponentFactory.create_label(
            tags_card, "🏷️ 标签", ColorScheme.TEXT_PRIMARY, 14
        )
        tags_layout.addWidget(tags_title)
        
        tags = ["机器学习", "深度学习", "Web开发", "数据分析", "自动化"]
        tags_frame = QFrame()
        tags_layout_h = QHBoxLayout(tags_frame)
        tags_layout_h.setSpacing(4)
        
        for tag in tags:
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("""
                QLabel {
                    background-color: #F3F4F6;
                    color: #4B5563;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }
            """)
            tags_layout_h.addWidget(tag_label)
        
        tags_layout.addWidget(tags_frame)
        sidebar_layout.addWidget(tags_card)
        
        main_layout.addWidget(sidebar)
        
        layout.addWidget(main_content, 1)
    
    def _on_post_selected(self, post: Dict):
        """文章选中处理"""
        dialog = QDialog(self)
        dialog.setWindowTitle(post["title"])
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        
        # 标题
        title_label = UIComponentFactory.create_label(
            dialog, post["title"], ColorScheme.TEXT_PRIMARY, 20
        )
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)
        
        # 元信息
        meta_layout = QHBoxLayout()
        
        author_label = QLabel(f"👤 {post['author']}")
        author_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        meta_layout.addWidget(author_label)
        
        date_label = QLabel(f"📅 {post['date']}")
        date_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        meta_layout.addWidget(date_label)
        
        read_time_label = QLabel(f"⏱️ {post['read_time']}分钟阅读")
        read_time_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        meta_layout.addWidget(read_time_label)
        
        layout.addLayout(meta_layout)
        
        # 分隔线
        divider = UIComponentFactory.create_divider(dialog)
        layout.addWidget(divider)
        
        # 内容
        content_text = QTextEdit()
        content_text.setPlainText(post["content"])
        content_text.setReadOnly(True)
        content_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: none;
                border-radius: 8px;
                padding: 16px;
                font-size: 15px;
                line-height: 1.8;
            }
        """)
        layout.addWidget(content_text, 1)
        
        dialog.exec()
    
    def _write_post(self):
        """写文章"""
        dialog = QDialog(self)
        dialog.setWindowTitle("写文章")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout(dialog)
        
        title_input = QLineEdit()
        title_input.setPlaceholderText("文章标题")
        layout.addWidget(title_input)
        
        content_text = QTextEdit()
        content_text.setPlaceholderText("文章内容...")
        layout.addWidget(content_text, 1)
        
        publish_btn = UIComponentFactory.create_button(
            dialog, "发布", variant="primary", size="md"
        )
        layout.addWidget(publish_btn)
        
        dialog.exec()