"""
邮件客户端窗口 - Mail Client

支持：
- 收件箱管理
- 邮件阅读
- 邮件撰写
- 邮件搜索
"""

from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QDialog, QTabWidget, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from client.src.presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class MailItem(QListWidgetItem):
    """邮件列表项"""
    
    def __init__(self, mail: Dict):
        super().__init__(mail["subject"])
        self._mail = mail
        self._setup_item()
    
    def _setup_item(self):
        """设置列表项样式"""
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsSelectable)
        
        if self._mail.get("unread", False):
            font = self.font()
            font.setBold(True)
            self.setFont(font)


class MailReader(QWidget):
    """邮件阅读组件"""
    
    def __init__(self, mail: Dict, parent=None):
        super().__init__(parent)
        self._mail = mail
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 发件人
        from_frame = QFrame()
        from_layout = QHBoxLayout(from_frame)
        
        from_label = UIComponentFactory.create_label(
            from_frame, "发件人:", ColorScheme.TEXT_SECONDARY, 12
        )
        from_layout.addWidget(from_label)
        
        from_value = UIComponentFactory.create_label(
            from_frame, self._mail["sender"], ColorScheme.TEXT_PRIMARY, 13
        )
        from_layout.addWidget(from_value)
        
        layout.addWidget(from_frame)
        
        # 收件人
        to_frame = QFrame()
        to_layout = QHBoxLayout(to_frame)
        
        to_label = UIComponentFactory.create_label(
            to_frame, "收件人:", ColorScheme.TEXT_SECONDARY, 12
        )
        to_layout.addWidget(to_label)
        
        to_value = UIComponentFactory.create_label(
            to_frame, self._mail["recipient"], ColorScheme.TEXT_PRIMARY, 13
        )
        to_layout.addWidget(to_value)
        
        layout.addWidget(to_frame)
        
        # 主题
        subject_label = UIComponentFactory.create_label(
            self, self._mail["subject"], ColorScheme.TEXT_PRIMARY, 16
        )
        subject_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(subject_label)
        
        # 分隔线
        divider = UIComponentFactory.create_divider(self)
        layout.addWidget(divider)
        
        # 邮件内容
        content_text = QTextEdit()
        content_text.setPlainText(self._mail["content"])
        content_text.setReadOnly(True)
        content_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(content_text, 1)
        
        # 操作按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        reply_btn = UIComponentFactory.create_button(
            self, "回复", variant="secondary", size="sm"
        )
        buttons_layout.addWidget(reply_btn)
        
        forward_btn = UIComponentFactory.create_button(
            self, "转发", variant="secondary", size="sm"
        )
        buttons_layout.addWidget(forward_btn)
        
        delete_btn = UIComponentFactory.create_button(
            self, "删除", variant="error", size="sm"
        )
        buttons_layout.addWidget(delete_btn)
        
        layout.addLayout(buttons_layout)


class MailComposer(QDialog):
    """邮件撰写对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("撰写邮件")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 收件人
        to_layout = QHBoxLayout()
        to_label = UIComponentFactory.create_label(self, "收件人:", ColorScheme.TEXT_SECONDARY, 12)
        to_input = QLineEdit()
        to_input.setPlaceholderText("输入收件人邮箱")
        
        to_layout.addWidget(to_label)
        to_layout.addWidget(to_input)
        layout.addLayout(to_layout)
        
        # 主题
        subject_layout = QHBoxLayout()
        subject_label = UIComponentFactory.create_label(self, "主题:", ColorScheme.TEXT_SECONDARY, 12)
        subject_input = QLineEdit()
        
        subject_layout.addWidget(subject_label)
        subject_layout.addWidget(subject_input)
        layout.addLayout(subject_layout)
        
        # 内容
        content_text = QTextEdit()
        content_text.setPlaceholderText("输入邮件内容...")
        layout.addWidget(content_text, 1)
        
        # 附件
        attach_btn = UIComponentFactory.create_button(
            self, "添加附件", variant="secondary", size="sm"
        )
        layout.addWidget(attach_btn)
        
        # 发送按钮
        send_btn = UIComponentFactory.create_button(
            self, "发送", variant="primary", size="md"
        )
        layout.addWidget(send_btn)


class MailClientWindow(QWidget):
    """邮件客户端主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mails = self._load_mails()
        self._setup_ui()
    
    def _load_mails(self) -> List[Dict]:
        """加载邮件列表"""
        return [
            {
                "id": 1,
                "sender": "张三 <zhangsan@example.com>",
                "recipient": "我 <me@example.com>",
                "subject": "关于项目进度的更新",
                "content": "您好，\n\n项目进展顺利，预计下周可以完成第一阶段的开发工作。\n\n请查看附件中的详细报告。\n\n此致",
                "date": "2024-01-15 10:30",
                "unread": True
            },
            {
                "id": 2,
                "sender": "李四 <lisi@example.com>",
                "recipient": "我 <me@example.com>",
                "subject": "会议邀请",
                "content": "您好，\n\n邀请您参加本周三下午2点的技术分享会议。\n\n地点：会议室A\n\n请确认是否参加。",
                "date": "2024-01-14 16:45",
                "unread": True
            },
            {
                "id": 3,
                "sender": "王五 <wangwu@example.com>",
                "recipient": "我 <me@example.com>",
                "subject": "资料已发送",
                "content": "您好，\n\n您需要的资料已经发送到您的邮箱，请查收附件。\n\n如有问题请随时联系我。",
                "date": "2024-01-13 09:20",
                "unread": False
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
            title_bar, "📧 邮件", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        
        # 搜索框
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索邮件...")
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
        
        # 写邮件按钮
        compose_btn = UIComponentFactory.create_button(
            title_bar, "写邮件", variant="primary", size="sm"
        )
        compose_btn.clicked.connect(self._compose_mail)
        title_layout.addWidget(compose_btn)
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 邮件列表
        mail_list = QListWidget()
        mail_list.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border-right: 1px solid #E5E7EB;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #F3F4F6;
            }
            QListWidget::item:hover {
                background-color: #F9FAFB;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
            }
        """)
        mail_list.setFixedWidth(300)
        mail_list.itemClicked.connect(self._on_mail_selected)
        
        for mail in self._mails:
            item = MailItem(mail)
            mail_list.addItem(item)
        
        main_layout.addWidget(mail_list)
        
        # 邮件内容区域
        self.content_area = QStackedWidget()
        self.content_area.setStyleSheet("background-color: #FAFAFA;")
        
        # 默认视图
        default_view = QWidget()
        default_layout = QVBoxLayout(default_view)
        default_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("📧")
        icon_label.setStyleSheet("font-size: 64px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_layout.addWidget(icon_label)
        
        text_label = UIComponentFactory.create_label(
            default_view, "选择一封邮件查看", ColorScheme.TEXT_SECONDARY, 14
        )
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_layout.addWidget(text_label)
        
        self.content_area.addWidget(default_view)
        
        main_layout.addWidget(self.content_area, 1)
        
        layout.addWidget(main_content, 1)
    
    def _on_mail_selected(self, item: QListWidgetItem):
        """邮件选中处理"""
        # 查找对应的邮件
        mail = next((m for m in self._mails if m["subject"] == item.text()), None)
        
        if mail:
            reader = MailReader(mail)
            self.content_area.addWidget(reader)
            self.content_area.setCurrentWidget(reader)
            
            # 标记为已读
            font = item.font()
            font.setBold(False)
            item.setFont(font)
    
    def _compose_mail(self):
        """撰写邮件"""
        dialog = MailComposer(self)
        dialog.exec()


# 全局邮件客户端实例
_mail_client = None

def get_mail_client() -> MailClientWindow:
    """获取邮件客户端实例"""
    global _mail_client
    if _mail_client is None:
        _mail_client = MailClientWindow()
    return _mail_client