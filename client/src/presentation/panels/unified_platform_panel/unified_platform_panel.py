"""
Unified Platform Panel - 统一内容平台面板
==========================================

三端统一的内容发布平台 UI，支持：
- 📧 邮件发送
- 📝 博客发布
- 💬 论坛发帖
- 🤖 数字分身自动发布

Author: Hermes Desktop Team
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QSpinBox, QTimeEdit,
    QTextBrowser, QSplitter, QToolBar, QMenu,
    QDialog, QDialogButtonBox, QMessageBox,
    QApplication, QStyle
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
import html
import json
import time

try:
    # 尝试导入核心模块
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

    from client.src.business.unified_platform import (
        PlatformHub, PlatformType,
        UnifiedPublisher, PublishTarget,
        AutoPublisher, PublishingSchedule,
        RichTextContent, ContentFormat
    )
    PLATFORM_AVAILABLE = True
except ImportError as e:
    PLATFORM_AVAILABLE = False
    print(f"Unified Platform 模块未完全可用: {e}")


class RichTextEditorWidget(QWidget):
    """富文本编辑器组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(20, 20))

        self.bold_btn = QPushButton("B")
        self.bold_btn.setMaximumWidth(30)
        self.bold_btn.setStyleSheet("font-weight: bold;")
        self.italic_btn = QPushButton("I")
        self.italic_btn.setMaximumWidth(30)
        self.italic_btn.setStyleSheet("font-style: italic;")
        self.underline_btn = QPushButton("U")
        self.underline_btn.setMaximumWidth(30)
        self.underline_btn.setStyleSheet("text-decoration: underline;")

        self.link_btn = QPushButton("🔗")
        self.link_btn.setMaximumWidth(30)
        self.image_btn = QPushButton("🖼")
        self.image_btn.setMaximumWidth(30)
        self.code_btn = QPushButton("</>")
        self.code_btn.setMaximumWidth(35)

        toolbar.addWidget(self.bold_btn)
        toolbar.addWidget(self.italic_btn)
        toolbar.addWidget(self.underline_btn)
        toolbar.addSeparator()
        toolbar.addWidget(self.link_btn)
        toolbar.addWidget(self.image_btn)
        toolbar.addWidget(self.code_btn)
        toolbar.addStretch()

        # 格式选择
        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "Markdown", "纯文本"])
        toolbar.addWidget(QLabel("格式:"))
        toolbar.addWidget(self.format_combo)

        layout.addWidget(toolbar)

        # 文本编辑区
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在此输入内容...\n\n支持富文本格式：\n- 粗体、斜体、下划线\n- 链接、图片\n- 代码块")
        layout.addWidget(self.text_edit)

        # 字数统计
        self.char_count_label = QLabel("字数: 0")
        layout.addWidget(self.char_count_label)

        # 信号连接
        self.text_edit.textChanged.connect(self._update_char_count)
        self.bold_btn.clicked.connect(lambda: self._insert_format("bold"))
        self.italic_btn.clicked.connect(lambda: self._insert_format("italic"))
        self.underline_btn.clicked.connect(lambda: self._insert_format("underline"))
        self.code_btn.clicked.connect(lambda: self._insert_format("code"))

    def _update_char_count(self):
        """更新字数统计"""
        text = self.text_edit.toPlainText()
        self.char_count_label.setText(f"字数: {len(text)} | 字符: {len(text.encode())}")

    def _insert_format(self, format_type: str):
        """插入格式"""
        cursor = self.text_edit.textCursor()
        selected_text = cursor.selectedText()

        formats = {
            "bold": f"<strong>{selected_text}</strong>",
            "italic": f"<em>{selected_text}</em>",
            "underline": f"<u>{selected_text}</u>",
            "code": f"<code>{selected_text}</code>"
        }

        if selected_text:
            cursor.insertHtml(formats.get(format_type, selected_text))
        else:
            placeholder = {"bold": "粗体文字", "italic": "斜体文字", "underline": "下划线文字", "code": "代码"}[format_type]
            cursor.insertHtml(f"<{format_type.upper()[:2]}>{placeholder}</{format_type.upper()[:2]}>")

    def get_html(self) -> str:
        """获取 HTML 内容"""
        return self.text_edit.toHtml()

    def get_plain_text(self) -> str:
        """获取纯文本"""
        return self.text_edit.toPlainText()

    def set_content(self, html_content: str):
        """设置内容"""
        self.text_edit.setHtml(html_content)

    def clear(self):
        """清空内容"""
        self.text_edit.clear()


class UnifiedPlatformPanel(QWidget):
    """
    统一内容平台面板

    功能：
    - 📧 邮件发送（节点间通信）
    - 📝 博客发布
    - 💬 论坛发帖
    - 🤖 数字分身自动发布配置
    """

    # 信号
    content_published = pyqtSignal(str, bool)  # content_id, success
    status_changed = pyqtSignal(str)  # status message

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态
        self.platform_hub = None
        self.auto_publisher = None
        self.current_platform = PlatformType.FORUM

        self._init_core()
        self._init_ui()

        # 定时更新
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_stats)
        self._update_timer.start(30000)  # 每30秒更新

    def _init_core(self):
        """初始化核心模块"""
        if PLATFORM_AVAILABLE:
            try:
                self.platform_hub = PlatformHub.get_instance()
                self.auto_publisher = AutoPublisher()
            except Exception as e:
                print(f"核心模块初始化失败: {e}")

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))

        self.status_label = QLabel("🟢 就绪")
        toolbar.addWidget(self.status_label)
        toolbar.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.settings_btn = QPushButton("⚙️ 设置")
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.settings_btn)

        layout.addWidget(toolbar)

        # 主标签页
        self.tabs = QTabWidget()

        # 1. 发布标签页
        self.publish_tab = self._create_publish_tab()
        self.tabs.addTab(self.publish_tab, "✏️ 发布")

        # 2. 邮件标签页
        self.email_tab = self._create_email_tab()
        self.tabs.addTab(self.email_tab, "📧 邮件")

        # 3. 博客标签页
        self.blog_tab = self._create_blog_tab()
        self.tabs.addTab(self.blog_tab, "📝 博客")

        # 4. 论坛标签页
        self.forum_tab = self._create_forum_tab()
        self.tabs.addTab(self.forum_tab, "💬 论坛")

        # 5. 自动发布标签页（数字分身）
        self.auto_tab = self._create_auto_tab()
        self.tabs.addTab(self.auto_tab, "🤖 自动发布")

        # 6. 活动流标签页
        self.activity_tab = self._create_activity_tab()
        self.tabs.addTab(self.activity_tab, "📊 活动")

        layout.addWidget(self.tabs)

        # 底部状态栏
        self.status_bar = QLabel()
        self.status_bar.setStyleSheet("padding: 5px; background: #f0f0f0;")
        layout.addWidget(self.status_bar)

        # 信号连接
        self.refresh_btn.clicked.connect(self._refresh)
        self.settings_btn.clicked.connect(self._show_settings)

    def _create_publish_tab(self) -> QWidget:
        """创建发布标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 平台选择
        platform_group = QGroupBox("发布目标")
        platform_layout = QHBoxLayout()

        self.email_check = QCheckBox("📧 邮件")
        self.blog_check = QCheckBox("📝 博客")
        self.forum_check = QCheckBox("💬 论坛")
        self.forum_check.setChecked(True)

        platform_layout.addWidget(self.email_check)
        platform_layout.addWidget(self.blog_check)
        platform_layout.addWidget(self.forum_check)
        platform_layout.addStretch()

        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 标题
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("标题")
        layout.addWidget(QLabel("标题:"))
        layout.addWidget(self.title_edit)

        # 富文本编辑器
        self.editor = RichTextEditorWidget()
        layout.addWidget(QLabel("内容:"))
        layout.addWidget(self.editor, 1)

        # 发布按钮
        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("👁 预览")
        self.draft_btn = QPushButton("💾 保存草稿")
        self.publish_btn = QPushButton("🚀 发布")
        self.publish_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.draft_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.publish_btn)

        layout.addLayout(btn_layout)

        # 信号连接
        self.publish_btn.clicked.connect(self._publish)
        self.preview_btn.clicked.connect(self._show_preview)
        self.draft_btn.clicked.connect(self._save_draft)

        return widget

    def _create_email_tab(self) -> QWidget:
        """创建邮件标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 收件人
        layout.addWidget(QLabel("收件人:"))
        self.email_to = QLineEdit()
        self.email_to.setPlaceholderText("user@nodeid.p2p")
        layout.addWidget(self.email_to)

        # 主题
        layout.addWidget(QLabel("主题:"))
        self.email_subject = QLineEdit()
        layout.addWidget(self.email_subject)

        # 内容
        layout.addWidget(QLabel("内容:"))
        self.email_content = RichTextEditorWidget()
        layout.addWidget(self.email_content, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self.email_send_btn = QPushButton("📤 发送")
        self.email_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        btn_layout.addStretch()
        btn_layout.addWidget(self.email_send_btn)

        layout.addLayout(btn_layout)

        self.email_send_btn.clicked.connect(self._send_email)

        return widget

    def _create_blog_tab(self) -> QWidget:
        """创建博客标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 标题
        layout.addWidget(QLabel("文章标题:"))
        self.blog_title = QLineEdit()
        layout.addWidget(self.blog_title)

        # 标签
        layout.addWidget(QLabel("标签 (逗号分隔):"))
        self.blog_tags = QLineEdit()
        self.blog_tags.setPlaceholderText("Python, AI, 技术分享")
        layout.addWidget(self.blog_tags)

        # 内容
        layout.addWidget(QLabel("文章内容:"))
        self.blog_content = RichTextEditorWidget()
        layout.addWidget(self.blog_content, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self.blog_preview_btn = QPushButton("👁 预览")
        self.blog_publish_btn = QPushButton("📤 发布博客")
        self.blog_publish_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        btn_layout.addWidget(self.blog_preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.blog_publish_btn)

        layout.addLayout(btn_layout)

        self.blog_publish_btn.clicked.connect(self._publish_blog)

        return widget

    def _create_forum_tab(self) -> QWidget:
        """创建论坛标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 话题选择
        layout.addWidget(QLabel("发布到话题:"))
        self.forum_topic = QComboBox()
        self.forum_topic.addItems([
            "general - 综合讨论",
            "tech - 技术交流",
            "ai - AI 人工智能",
            "programming - 编程",
            "share - 资源共享",
            "question - 提问求助"
        ])
        layout.addWidget(self.forum_topic)

        # 标题
        layout.addWidget(QLabel("帖子标题:"))
        self.forum_title = QLineEdit()
        layout.addWidget(self.forum_title)

        # 标签
        layout.addWidget(QLabel("标签 (逗号分隔):"))
        self.forum_tags = QLineEdit()
        layout.addWidget(self.forum_tags)

        # 内容
        layout.addWidget(QLabel("帖子内容:"))
        self.forum_content = RichTextEditorWidget()
        layout.addWidget(self.forum_content, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self.forum_preview_btn = QPushButton("👁 预览")
        self.forum_post_btn = QPushButton("💬 发布帖子")
        self.forum_post_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        btn_layout.addWidget(self.forum_preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.forum_post_btn)

        layout.addLayout(btn_layout)

        self.forum_post_btn.clicked.connect(self._post_forum)

        return widget

    def _create_auto_tab(self) -> QWidget:
        """创建自动发布标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 配置区域
        config_group = QGroupBox("🤖 数字分身自动发布配置")
        config_layout = QFormLayout()

        self.auto_enabled = QCheckBox("启用自动发布")
        self.auto_enabled.setChecked(True)
        config_layout.addRow("启用状态:", self.auto_enabled)

        self.auto_idle_timeout = QSpinBox()
        self.auto_idle_timeout.setRange(5, 120)
        self.auto_idle_timeout.setValue(30)
        self.auto_idle_timeout.setSuffix(" 分钟")
        config_layout.addRow("空闲超时:", self.auto_idle_timeout)

        self.auto_max_daily = QSpinBox()
        self.auto_max_daily.setRange(1, 50)
        self.auto_max_daily.setValue(10)
        config_layout.addRow("每日上限:", self.auto_max_daily)

        self.auto_min_interval = QSpinBox()
        self.auto_min_interval.setRange(5, 120)
        self.auto_min_interval.setValue(15)
        self.auto_min_interval.setSuffix(" 分钟")
        config_layout.addRow("最小间隔:", self.auto_min_interval)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 平台启用
        platform_group = QGroupBox("发布平台")
        platform_layout = QHBoxLayout()

        self.auto_blog_check = QCheckBox("📝 博客")
        self.auto_blog_check.setChecked(True)
        self.auto_forum_check = QCheckBox("💬 论坛")
        self.auto_forum_check.setChecked(True)

        platform_layout.addWidget(self.auto_blog_check)
        platform_layout.addWidget(self.auto_forum_check)
        platform_layout.addStretch()

        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 定时计划
        schedule_group = QGroupBox("⏰ 定时发布计划")
        schedule_layout = QVBoxLayout()

        self.schedule_list = QListWidget()
        schedule_layout.addWidget(self.schedule_list)

        # 添加预设计划
        self._add_default_schedules()

        schedule_btn_layout = QHBoxLayout()
        self.add_schedule_btn = QPushButton("➕ 添加计划")
        self.remove_schedule_btn = QPushButton("➖ 删除计划")
        schedule_btn_layout.addWidget(self.add_schedule_btn)
        schedule_btn_layout.addWidget(self.remove_schedule_btn)
        schedule_layout.addLayout(schedule_btn_layout)

        schedule_group.setLayout(schedule_layout)
        layout.addWidget(schedule_group, 1)

        # 统计
        stats_group = QGroupBox("📊 发布统计")
        stats_layout = QFormLayout()

        self.stats_today = QLabel("今日: 0")
        self.stats_total = QLabel("总计: 0")
        self.stats_success = QLabel("成功率: 0%")

        stats_layout.addRow("今日发布:", self.stats_today)
        stats_layout.addRow("总发布数:", self.stats_total)
        stats_layout.addRow("成功率:", self.stats_success)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return widget

    def _add_default_schedules(self):
        """添加默认发布计划"""
        schedules = [
            ("🌅 早安帖", "08:00", "status"),
            ("📚 知识分享", "12:00", "knowledge"),
            ("🌙 晚安帖", "22:00", "summary")
        ]

        for name, time_str, content_type in schedules:
            item = QListWidgetItem(f"{name} @ {time_str}")
            item.setData(1, {"name": name, "time": time_str, "type": content_type})
            self.schedule_list.addItem(item)

    def _create_activity_tab(self) -> QWidget:
        """创建活动流标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 过滤器
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.activity_filter = QComboBox()
        self.activity_filter.addItems(["全部", "📧 邮件", "📝 博客", "💬 论坛"])
        filter_layout.addWidget(self.activity_filter)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 活动列表
        self.activity_list = QListWidget()
        self.activity_list.setAlternatingRowColors(True)
        layout.addWidget(self.activity_list, 1)

        # 加载模拟数据
        self._load_mock_activities()

        return widget

    def _load_mock_activities(self):
        """加载模拟活动数据"""
        activities = [
            ("📧", "user1@node1.p2p", "收到新邮件", "2分钟前"),
            ("📝", "博客文章已发布", "《Python异步编程》", "15分钟前"),
            ("💬", "新回复", "关于AI的讨论帖", "1小时前"),
            ("🤖", "自动发布", "早安帖已发布", "3小时前"),
            ("📧", "发送邮件", "至 user2@node2.p2p", "5小时前"),
        ]

        for icon, title, desc, time_str in activities:
            item = QListWidgetItem(f"{icon} {title} - {desc} ({time_str})")
            self.activity_list.addItem(item)

    # ==================== 动作方法 ====================

    def _publish(self):
        """发布内容"""
        title = self.title_edit.text().strip()
        content = self.editor.get_html()

        if not title:
            QMessageBox.warning(self, "提示", "请输入标题")
            return

        if not content or len(self.editor.get_plain_text()) < 10:
            QMessageBox.warning(self, "提示", "内容太短")
            return

        # 收集目标平台
        targets = []
        if self.email_check.isChecked():
            targets.append(PlatformType.EMAIL)
        if self.blog_check.isChecked():
            targets.append(PlatformType.BLOG)
        if self.forum_check.isChecked():
            targets.append(PlatformType.FORUM)

        if not targets:
            QMessageBox.warning(self, "提示", "请选择至少一个发布平台")
            return

        # 发布
        self.publish_btn.setEnabled(False)
        self.publish_btn.setText("发布中...")

        try:
            if PLATFORM_AVAILABLE and self.platform_hub:
                asyncio.create_task(self._do_publish(title, content, targets))
            else:
                # 模拟发布
                self._simulate_publish(title, targets)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发布失败: {str(e)}")
            self.publish_btn.setEnabled(True)
            self.publish_btn.setText("🚀 发布")

    async def _do_publish(self, title: str, content: str, platforms: list):
        """执行发布"""
        try:
            results = await self.platform_hub.publish_all(
                title=title,
                content=content,
                platforms=platforms,
                author_name="用户"
            )

            success_count = sum(1 for r in results.values() if r and r[0].success if hasattr(r, '__getitem__') else False)

            QMessageBox.information(
                self, "成功",
                f"成功发布到 {success_count}/{len(platforms)} 个平台"
            )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发布失败: {str(e)}")

        finally:
            self.publish_btn.setEnabled(True)
            self.publish_btn.setText("🚀 发布")

    def _simulate_publish(self, title: str, platforms: list):
        """模拟发布"""
        QTimer.singleShot(1000, lambda: [
            QMessageBox.information(self, "成功", f"内容已发布到 {len(platforms)} 个平台（模拟模式）"),
            self.publish_btn.setEnabled(True),
            self.publish_btn.setText("🚀 发布"),
            self.status_bar.setText(f"✓ 已发布: {title}")
        ])

    def _show_preview(self):
        """显示预览"""
        title = self.title_edit.text() or "无标题"
        content = self.editor.get_html()

        preview_window = QDialog(self)
        preview_window.setWindowTitle("预览")
        preview_window.resize(600, 500)

        layout = QVBoxLayout(preview_window)
        layout.addWidget(QLabel(f"<h2>{title}</h2>"))

        browser = QTextBrowser()
        browser.setHtml(content)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(preview_window.accept)
        layout.addWidget(buttons)

        preview_window.exec()

    def _save_draft(self):
        """保存草稿"""
        QMessageBox.information(self, "提示", "草稿已保存")
        self.status_bar.setText("✓ 草稿已保存")

    def _send_email(self):
        """发送邮件"""
        to = self.email_to.text().strip()
        subject = self.email_subject.text().strip()
        content = self.email_content.get_html()

        if not to:
            QMessageBox.warning(self, "提示", "请输入收件人")
            return

        if not subject:
            QMessageBox.warning(self, "提示", "请输入主题")
            return

        # 模拟发送
        self.email_send_btn.setEnabled(False)
        self.email_send_btn.setText("发送中...")

        QTimer.singleShot(1500, lambda: [
            QMessageBox.information(self, "成功", f"邮件已发送至 {to}"),
            self.email_send_btn.setEnabled(True),
            self.email_send_btn.setText("📤 发送")
        ])

    def _publish_blog(self):
        """发布博客"""
        title = self.blog_title.text().strip()
        content = self.blog_content.get_html()

        if not title:
            QMessageBox.warning(self, "提示", "请输入文章标题")
            return

        self.blog_publish_btn.setEnabled(False)

        QTimer.singleShot(1500, lambda: [
            QMessageBox.information(self, "成功", f"博客《{title}》已发布"),
            self.blog_publish_btn.setEnabled(True)
        ])

    def _post_forum(self):
        """发布论坛帖子"""
        title = self.forum_title.text().strip()
        content = self.forum_content.get_html()
        topic = self.forum_topic.currentText().split(" - ")[0]

        if not title:
            QMessageBox.warning(self, "提示", "请输入帖子标题")
            return

        self.forum_post_btn.setEnabled(False)

        QTimer.singleShot(1500, lambda: [
            QMessageBox.information(self, "成功", f"帖子已发布到 {topic} 话题"),
            self.forum_post_btn.setEnabled(True)
        ])

    def _refresh(self):
        """刷新"""
        self._update_stats()
        self.status_bar.setText("✓ 已刷新")

    def _show_settings(self):
        """显示设置"""
        QMessageBox.information(self, "设置", "设置功能开发中...")

    def _update_stats(self):
        """更新统计"""
        if PLATFORM_AVAILABLE and self.auto_publisher:
            stats = self.auto_publisher.get_stats()
            self.stats_today.setText(f"今日: {stats.get('today_posts', 0)}")
            self.stats_total.setText(f"总计: {stats.get('total_records', 0)}")
        else:
            self.stats_today.setText("今日: 0")
            self.stats_total.setText("总计: 0")
            self.stats_success.setText("成功率: --")

    def trigger_idle_publish(self, idle_minutes: int):
        """触发空闲发布（供外部调用）"""
        if PLATFORM_AVAILABLE and self.auto_publisher:
            if self.auto_enabled.isChecked():
                asyncio.create_task(
                    self.auto_publisher.trigger_idle(idle_minutes)
                )
