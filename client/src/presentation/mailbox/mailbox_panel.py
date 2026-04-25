"""
去中心化邮箱 PyQt6 UI 面板

功能:
- 收件箱/发件箱/草稿箱/垃圾箱
- 撰写和发送邮件
- 联系人管理
- 附件管理
- 邮箱地址展示
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QIcon, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
                             QPushButton, QLabel, QComboBox, QTabWidget,
                             QToolBar, QStatusBar, QMenu, QDialog, QDialogButtonBox,
                             QFileDialog, QMessageBox, QCheckBox, QProgressBar,
                             QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate)

logger = logging.getLogger(__name__)


class MailboxPanel(QWidget):
    """
    去中心化邮箱主面板
    
    5个标签页:
    - 收件箱
    - 发件箱  
    - 撰写
    - 联系人
    - 设置
    """
    
    # 信号
    new_message_signal = pyqtSignal(object)
    status_update_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.hub = None  # MailboxHub
        self.current_folder = "unified"  # 默认打开统一收件箱
        self.current_message = None
        self.unified_entry = None  # UnifiedInbox 当前条目

        self._init_ui()
        self._init_timer()
        self._init_unified_inbox()

    def _init_unified_inbox(self):
        """初始化统一收件箱"""
        try:
            from core.decentralized_mailbox import get_unified_inbox
            self.unified_inbox = get_unified_inbox()
            # 加载各来源邮件
            self.unified_inbox.load_internal_messages()
            self.unified_inbox.load_relay_messages()
        except Exception as e:
            logger.error(f"初始化统一收件箱失败: {e}")
            self.unified_inbox = None
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 主内容区 (三栏布局)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左栏: 文件夹列表
        left_panel = self._create_folder_panel()
        main_splitter.addWidget(left_panel)
        main_splitter.setStretchFactor(0, 1)
        
        # 中栏: 邮件列表
        center_panel = self._create_message_list_panel()
        main_splitter.addWidget(center_panel)
        main_splitter.setStretchFactor(1, 2)
        
        # 右栏: 邮件内容/撰写
        right_panel = self._create_content_panel()
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(2, 3)
        
        layout.addWidget(main_splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        self.status_bar.showMessage("未连接")
    
    def _create_toolbar(self) -> QToolBar:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # 我的地址
        self.addr_label = QLabel("未登录")
        self.addr_label.setStyleSheet("QLabel { color: #1890ff; font-weight: bold; }")
        toolbar.addWidget(self.addr_label)
        
        toolbar.addSeparator()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(refresh_btn)
        
        # 新建邮件
        compose_btn = QPushButton("写邮件")
        compose_btn.clicked.connect(lambda: self._switch_folder("compose"))
        toolbar.addWidget(compose_btn)
        
        toolbar.addSeparator()
        
        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索邮件...")
        self.search_box.setFixedWidth(200)
        self.search_box.returnPressed.connect(self._on_search)
        toolbar.addWidget(self.search_box)
        
        return toolbar
    
    def _create_folder_panel(self) -> QWidget:
        """创建文件夹面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 文件夹列表
        self.folder_list = QListWidget()
        self.folder_list.currentItemChanged.connect(self._on_folder_changed)
        
        folders = [
            ("🌐 统一收件箱", "unified"),
            ("📥 收件箱", "inbox"),
            ("📤 已发送", "sent"),
            ("📝 草稿箱", "drafts"),
            ("📬 发件箱", "outbox"),
            ("🗑️ 垃圾箱", "trash"),
        ]
        
        for name, fid in folders:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, fid)
            self.folder_list.addItem(item)
        
        layout.addWidget(self.folder_list)
        
        # 联系人快捷
        contacts_label = QLabel("联系人")
        contacts_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(contacts_label)
        
        self.contact_list = QListWidget()
        self.contact_list.itemDoubleClicked.connect(self._on_contact_double_clicked)
        layout.addWidget(self.contact_list)
        
        return widget
    
    def _create_message_list_panel(self) -> QWidget:
        """创建邮件列表面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.message_list = QListWidget()
        self.message_list.itemClicked.connect(self._on_message_clicked)
        self.message_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_list.customContextMenuRequested.connect(self._on_message_context_menu)
        
        layout.addWidget(self.message_list)
        
        return widget
    
    def _create_content_panel(self) -> QWidget:
        """创建邮件内容面板"""
        self.content_stack = QTabWidget()
        
        # 邮件查看页
        self.view_page = self._create_view_page()
        self.content_stack.addTab(self.view_page, "邮件内容")
        
        # 撰写页
        self.compose_page = self._create_compose_page()
        self.content_stack.addTab(self.compose_page, "撰写邮件")
        
        layout = QVBoxLayout()
        layout.addWidget(self.content_stack)
        
        container = QWidget()
        container.setLayout(layout)
        return container
    
    def _create_view_page(self) -> QWidget:
        """创建邮件查看页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 邮件头
        self.view_header = QLabel()
        self.view_header.setWordWrap(True)
        self.view_header.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.view_header)
        
        # 附件区
        self.attachment_widget = QWidget()
        att_layout = QHBoxLayout(self.attachment_widget)
        att_layout.addWidget(QLabel("附件:"))
        self.attachment_list_label = QLabel("无")
        att_layout.addWidget(self.attachment_list_label)
        self.attachment_widget.setVisible(False)
        layout.addWidget(self.attachment_widget)
        
        # 邮件正文
        self.view_body = QTextEdit()
        self.view_body.setReadOnly(True)
        layout.addWidget(self.view_body)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        reply_btn = QPushButton("回复")
        reply_btn.clicked.connect(self._on_reply)
        forward_btn = QPushButton("转发")
        forward_btn.clicked.connect(self._on_forward)
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(reply_btn)
        btn_layout.addWidget(forward_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_compose_page(self) -> QWidget:
        """创建撰写邮件页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 收件人
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("收件人:"))
        self.compose_to = QLineEdit()
        self.compose_to.setPlaceholderText("user@nodeid.p2p (多个用逗号分隔)")
        to_layout.addWidget(self.compose_to)
        layout.addLayout(to_layout)
        
        # 抄送
        cc_layout = QHBoxLayout()
        cc_layout.addWidget(QLabel("抄送:"))
        self.compose_cc = QLineEdit()
        self.compose_cc.setPlaceholderText("可选")
        cc_layout.addWidget(self.compose_cc)
        layout.addLayout(cc_layout)
        
        # 主题
        subject_layout = QHBoxLayout()
        subject_layout.addWidget(QLabel("主题:"))
        self.compose_subject = QLineEdit()
        subject_layout.addWidget(self.compose_subject)
        layout.addLayout(subject_layout)
        
        # 正文
        self.compose_body = QTextEdit()
        self.compose_body.setPlaceholderText("输入邮件内容...")
        layout.addWidget(self.compose_body)
        
        # 附件
        att_layout = QHBoxLayout()
        att_layout.addWidget(QLabel("附件:"))
        self.compose_attachments = QLabel("无")
        att_layout.addWidget(self.compose_attachments)
        
        attach_btn = QPushButton("添加附件")
        attach_btn.clicked.connect(self._on_attach_file)
        att_layout.addWidget(attach_btn)
        
        self.compose_attachment_paths = []
        att_layout.addStretch()
        layout.addLayout(att_layout)
        
        # 选项
        options_layout = QHBoxLayout()
        self.encrypt_check = QCheckBox("端到端加密")
        self.encrypt_check.setChecked(True)
        options_layout.addWidget(self.encrypt_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # 发送按钮
        send_layout = QHBoxLayout()
        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        send_btn.clicked.connect(self._on_send)
        send_layout.addWidget(send_btn)
        send_layout.addStretch()
        layout.addLayout(send_layout)
        
        return widget
    
    def _create_contacts_page(self) -> QWidget:
        """创建联系人页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具栏
        toolbar = QHBoxLayout()
        add_btn = QPushButton("添加联系人")
        add_btn.clicked.connect(self._on_add_contact)
        toolbar.addWidget(add_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 联系人表格
        self.contacts_table = QTableWidget()
        self.contacts_table.setColumnCount(4)
        self.contacts_table.setHorizontalHeaderLabels(["地址", "昵称", "信任级别", "操作"])
        self.contacts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.contacts_table)
        
        return widget
    
    def _create_settings_page(self) -> QWidget:
        """创建设置页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 身份信息
        identity_group = QLabel("身份信息")
        identity_group.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(identity_group)
        
        self.settings_addr_label = QLabel("地址: -")
        layout.addWidget(self.settings_addr_label)
        
        self.settings_node_id_label = QLabel("节点ID: -")
        layout.addWidget(self.settings_node_id_label)
        
        # 中继服务器
        relay_group = QLabel("中继服务器")
        relay_group.setStyleSheet("font-weight: bold; font-size: 14px;")
        relay_group.setStyleSheet("margin-top: 20px;")
        layout.addWidget(relay_group)
        
        relay_layout = QHBoxLayout()
        relay_layout.addWidget(QLabel("服务器:"))
        self.relay_host = QLineEdit("139.199.124.242")
        relay_layout.addWidget(self.relay_host)
        relay_layout.addWidget(QLabel(":"))
        self.relay_port = QLineEdit("8888")
        self.relay_port.setFixedWidth(60)
        relay_layout.addWidget(self.relay_port)
        layout.addLayout(relay_layout)
        
        # 连接状态
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("连接状态:"))
        self.relay_status = QLabel("未连接")
        self.relay_status.setStyleSheet("color: #999;")
        status_layout.addWidget(self.relay_status)
        
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(self._on_connect_relay)
        status_layout.addWidget(connect_btn)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        layout.addStretch()
        
        return widget
    
    def _init_timer(self):
        """初始化定时器"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._on_refresh)
        self.refresh_timer.start(60000)  # 每分钟刷新
    
    # ========== 事件处理 ==========
    
    def set_hub(self, hub):
        """设置邮箱核心"""
        self.hub = hub
        self._update_status()
        self._refresh_messages()
        self._refresh_contacts()
    
    def _update_status(self):
        """更新状态"""
        if self.hub:
            status = self.hub.get_status()
            addr = status.get("my_address", "未登录")
            self.addr_label.setText(addr)
            self.status_bar.showMessage(f"已连接 | 未读: {status.get('unread_count', 0)}")
    
    def _refresh_messages(self):
        """刷新邮件列表"""
        if not self.hub:
            return

        self.message_list.clear()

        # 统一收件箱
        if self.current_folder == "unified":
            self._refresh_unified_inbox()
            return

        if self.current_folder == "inbox":
            messages = self.hub.get_inbox()
        elif self.current_folder == "sent":
            messages = self.hub.get_sent()
        elif self.current_folder == "drafts":
            messages = self.hub.get_drafts()
        elif self.current_folder == "outbox":
            messages = self.hub.get_outbox()
        elif self.current_folder == "trash":
            messages = self.hub.get_trash()
        else:
            messages = []

        for msg in messages:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, msg.message_id)

            # 显示内容
            sender = msg.from_addr.username if msg.from_addr else "未知"
            time_str = msg.display_time

            text = f"{'[已读] ' if msg.status.value == 'read' else ''}{sender}\n"
            text += f"{msg.subject}\n"
            text += f"<span style='color: #999;'>{msg.preview[:50]}... | {time_str}</span>"

            item.setText(text)
            self.message_list.addItem(item)

    def _refresh_unified_inbox(self):
        """刷新统一收件箱"""
        try:
            from core.decentralized_mailbox import get_unified_inbox

            unified = get_unified_inbox()
            messages = unified.get_inbox(limit=100)

            for entry in messages:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, entry.message_id)

                # 显示内容（含来源标签）
                sender = entry.from_name or entry.from_addr
                time_str = entry.display_time
                source_icon = entry.display_source

                text = f"{source_icon} {entry.display_label}\n"
                text += f"{'[⭐] ' if entry.is_starred else ''}{'[未读] ' if not entry.is_read else ''}{sender}\n"
                text += f"{entry.subject}\n"
                text += f"<span style='color: #999;'>{entry.preview[:40]}... | {time_str}</span>"

                item.setText(text)
                self.message_list.addItem(item)

        except Exception as e:
            logger.error(f"刷新统一收件箱失败: {e}")
            self.message_list.addItem(QListWidgetItem("加载统一收件箱失败"))
    
    def _refresh_contacts(self):
        """刷新联系人"""
        if not self.hub:
            return
        
        self.contact_list.clear()
        contacts = self.hub.get_contacts()
        
        for contact in contacts:
            item = QListWidgetItem(contact.address.username)
            item.setData(Qt.ItemDataRole.UserRole, str(contact.address))
            self.contact_list.addItem(item)
    
    def _switch_folder(self, folder: str):
        """切换文件夹"""
        self.current_folder = folder
        
        if folder == "compose":
            self.content_stack.setCurrentWidget(self.compose_page)
        else:
            self.content_stack.setCurrentWidget(self.view_page)
        
        self._refresh_messages()
    
    def _on_folder_changed(self, item: QListWidgetItem):
        """文件夹选择改变"""
        if item:
            folder = item.data(Qt.ItemDataRole.UserRole)
            self._switch_folder(folder)
    
    def _on_message_clicked(self, item: QListWidgetItem):
        """点击邮件"""
        message_id = item.data(Qt.ItemDataRole.UserRole)

        # 统一收件箱
        if self.current_folder == "unified" and self.unified_inbox:
            entry = self.unified_inbox.get_message(message_id)
            if entry:
                self.current_message = entry
                self._display_unified_entry(entry)
                if not entry.is_read:
                    self.unified_inbox.mark_as_read(message_id)
            return

        # 内部邮件
        if self.hub:
            message = self.hub.get_message(message_id)
            if message:
                self.current_message = message
                self._display_message(message)

                # 标记为已读
                if message.status.value != "read":
                    self.hub.mark_as_read(message_id)

    def _display_unified_entry(self, entry):
        """显示统一收件箱条目"""
        from datetime import datetime

        # 头部（含来源信息）
        header = f"<b>来源:</b> {entry.display_label}<br>"
        header += f"<b>发件人:</b> {entry.from_name or entry.from_addr}<br>"
        header += f"<b>邮箱:</b> {entry.from_addr}<br>"
        header += f"<b>收件人:</b> {', '.join(entry.to_addrs) or 'N/A'}<br>"
        header += f"<b>主题:</b> {entry.subject}<br>"
        header += f"<b>时间:</b> {datetime.fromtimestamp(entry.date).strftime('%Y-%m-%d %H:%M:%S')}"

        self.view_header.setText(header)

        # 正文
        body = entry.body_text or entry.body_html or "[无正文]"
        self.view_body.setText(body)
    
    def _display_message(self, message):
        """显示邮件内容"""
        # 头部
        sender = message.from_addr.username if message.from_addr else "未知"
        to = ", ".join([a.username for a in message.to_addrs])
        
        header = f"<b>发件人:</b> {sender}<br>"
        header += f"<b>收件人:</b> {to}<br>"
        header += f"<b>主题:</b> {message.subject}<br>"
        header += f"<b>时间:</b> {datetime.fromtimestamp(message.created_at)}"
        
        self.view_header.setText(header)
        
        # 正文
        if message.is_encrypted and message.body_plain:
            self.view_body.setText(f"[加密内容]\n\n{message.body_plain}")
        elif message.body_plain:
            self.view_body.setText(message.body_plain)
        else:
            self.view_body.setText("[无正文]")
        
        # 附件
        if message.has_attachments:
            self.attachment_widget.setVisible(True)
            att_names = ", ".join([a.filename for a in message.attachments])
            self.attachment_list_label.setText(att_names)
        else:
            self.attachment_widget.setVisible(False)
    
    def _on_message_context_menu(self, pos):
        """邮件右键菜单"""
        menu = QMenu()
        
        reply_action = menu.addAction("回复")
        forward_action = menu.addAction("转发")
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        
        action = menu.exec(self.message_list.mapToGlobal(pos))
        
        if action == reply_action:
            self._on_reply()
        elif action == forward_action:
            self._on_forward()
        elif action == delete_action:
            self._on_delete()
    
    def _on_refresh(self):
        """刷新"""
        self._refresh_messages()
        self._update_status()
    
    def _on_search(self):
        """搜索"""
        query = self.search_box.text()
        if not query or not self.hub:
            return
        
        results = self.hub.search_messages(query)
        
        self.message_list.clear()
        for msg in results:
            item = QListWidgetItem(f"{msg.subject} - {msg.preview[:30]}...")
            item.setData(Qt.ItemDataRole.UserRole, msg.message_id)
            self.message_list.addItem(item)
    
    def _on_reply(self):
        """回复"""
        if not self.current_message or not self.current_message.from_addr:
            return
        
        self.compose_to.setText(str(self.current_message.from_addr))
        self.compose_subject.setText(f"Re: {self.current_message.subject}")
        self.content_stack.setCurrentWidget(self.compose_page)
    
    def _on_forward(self):
        """转发"""
        if not self.current_message:
            return
        
        self.compose_subject.setText(f"Fw: {self.current_message.subject}")
        self.compose_body.setText(f"\n\n--- 转发的邮件 ---\n{self.current_message.body_plain}")
        self.content_stack.setCurrentWidget(self.compose_page)
    
    def _on_delete(self):
        """删除"""
        if not self.current_message:
            return
        
        reply = QMessageBox.question(self, "确认删除", "确定删除这封邮件?")
        if reply == QMessageBox.StandardButton.Yes:
            self.hub.delete_message(self.current_message.message_id)
            self.current_message = None
            self._refresh_messages()
    
    def _on_send(self):
        """发送邮件"""
        to_text = self.compose_to.text()
        subject = self.compose_subject.text()
        body = self.compose_body.toPlainText()
        cc_text = self.compose_cc.text()
        
        if not to_text or not subject:
            QMessageBox.warning(self, "提示", "请填写收件人和主题")
            return
        
        to_addrs = [a.strip() for a in to_text.split(",")]
        cc_addrs = [a.strip() for a in cc_text.split(",")] if cc_text else []
        
        # 异步发送
        asyncio.create_task(self._send_async(to_addrs, subject, body, cc_addrs))
    
    async def _send_async(self, to_addrs, subject, body, cc_addrs):
        """异步发送"""
        try:
            self.status_bar.showMessage("发送中...")
            
            message_id = await self.hub.send_message(
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                cc_addrs=cc_addrs,
                attachments=self.compose_attachment_paths,
                encrypt=self.encrypt_check.isChecked()
            )
            
            if message_id:
                self.status_bar.showMessage("发送成功!")
                QMessageBox.information(self, "成功", "邮件已发送")
                
                # 清空表单
                self.compose_to.clear()
                self.compose_subject.clear()
                self.compose_body.clear()
                self.compose_attachments.setText("无")
                self.compose_attachment_paths.clear()
                
                # 切换到发件箱
                self._switch_folder("sent")
            else:
                self.status_bar.showMessage("发送失败")
                QMessageBox.warning(self, "失败", "发送失败, 请重试")
                
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self.status_bar.showMessage(f"发送异常: {e}")
    
    def _on_attach_file(self):
        """添加附件"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        if files:
            self.compose_attachment_paths.extend(files)
            self.compose_attachments.setText(f"{len(self.compose_attachment_paths)} 个文件")
    
    def _on_contact_double_clicked(self, item: QListWidgetItem):
        """双击联系人"""
        address = item.data(Qt.ItemDataRole.UserRole)
        self.compose_to.setText(address)
        self.content_stack.setCurrentWidget(self.compose_page)
    
    def _on_add_contact(self):
        """添加联系人"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加联系人")
        layout = QVBoxLayout(dialog)
        
        addr_input = QLineEdit()
        addr_input.setPlaceholderText("user@nodeid.p2p")
        layout.addWidget(QLabel("地址:"))
        layout.addWidget(addr_input)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("显示名称")
        layout.addWidget(QLabel("昵称:"))
        layout.addWidget(name_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            addr = addr_input.text()
            name = name_input.text()
            if addr and self.hub:
                if self.hub.add_contact(addr, name):
                    self._refresh_contacts()
                    QMessageBox.information(self, "成功", "联系人已添加")
                else:
                    QMessageBox.warning(self, "失败", "添加联系人失败")
    
    def _on_connect_relay(self):
        """连接中继服务器"""
        if self.hub and self.hub.router:
            host = self.relay_host.text()
            port = int(self.relay_port.text())
            
            self.hub.router.relay_config["host"] = host
            self.hub.router.relay_config["port"] = port
            
            asyncio.create_task(self.hub.router.check_relay_connection())
            self.status_bar.showMessage(f"正在连接 {host}:{port}...")


# 简化版列表项部件
class MailListItem(QWidget):
    """邮件列表项自定义widget"""
    
    def __init__(self, message, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # 发件人
        sender = QLabel(message.from_addr.username if message.from_addr else "未知")
        sender.setStyleSheet("font-weight: bold;")
        layout.addWidget(sender)
        
        # 主题
        subject = QLabel(message.subject)
        layout.addWidget(subject)
        
        # 预览
        preview = QLabel(message.preview[:50])
        preview.setStyleSheet("color: #999;")
        layout.addWidget(preview)
