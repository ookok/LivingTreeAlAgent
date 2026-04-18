# -*- coding: utf-8 -*-
"""
MCP Market 面板 - PyQt6 MCP Server 市场 UI
=========================================

功能：
- MCP Server 浏览与搜索
- Server 安装/卸载/更新
- Server 状态监控
- 本地/远程/Market 三种来源

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor
from PyQt6.QtNetwork import QTcpSocket, QHostAddress

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List

from core.mcp_manager import (
    MCPServer, MCPTool, MCPDatabase,
    ServerStatus, ServerSource, MCPProtocol
)


# ==================== MCP Server 卡片组件 ====================

class MCPServerCard(QFrame):
    """MCP Server 卡片组件"""

    connect_requested = pyqtSignal(str)  # 连接信号
    disconnect_requested = pyqtSignal(str)  # 断开信号
    configure_requested = pyqtSignal(str)  # 配置信号
    delete_requested = pyqtSignal(str)  # 删除信号

    def __init__(self, server: MCPServer, parent=None):
        super().__init__(parent)
        self.server = server
        self._setup_ui()
        self._update_style()
        self._update_status()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部：名称 + 状态指示
        header = QHBoxLayout()
        
        # 状态指示灯
        self.status_indicator = QLabel("⚫")
        self.status_indicator.setFont(QFont("Segoe UI Emoji", 14))
        header.addWidget(self.status_indicator)
        
        # 名称和描述
        name_layout = QVBoxLayout()
        self.name_label = QLabel(self.server.name)
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        name_layout.addWidget(self.name_label)
        
        self.desc_label = QLabel(self.server.description[:50] + "..." if len(self.server.description) > 50 else self.server.description)
        self.desc_label.setStyleSheet("color: #888; font-size: 10px;")
        self.desc_label.setWordWrap(True)
        name_layout.addWidget(self.desc_label)
        
        header.addLayout(name_layout)
        header.addStretch()
        
        # 源码标签
        source_label = QLabel(f"[{self.server.source}]")
        source_label.setFont(QFont("Microsoft YaHei", 8))
        source_label.setStyleSheet("""
            background-color: #e8f4fd;
            color: #1890ff;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header.addWidget(source_label)
        
        layout.addLayout(header)

        # 协议和URL
        info_layout = QHBoxLayout()
        self.protocol_label = QLabel(f"🔌 {self.server.protocol}")
        self.protocol_label.setFont(QFont("Microsoft YaHei", 9))
        self.protocol_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.protocol_label)
        
        self.url_label = QLabel(self.server.url[:30] + "..." if len(self.server.url) > 30 else self.server.url)
        self.url_label.setFont(QFont("Consolas", 8))
        self.url_label.setStyleSheet("color: #999;")
        self.url_label.setWordWrap(True)
        info_layout.addWidget(self.url_label)
        info_layout.addStretch()
        
        layout.addLayout(info_layout)

        # 能力标签
        if self.server.capabilities:
            tags_layout = QHBoxLayout()
            for cap in self.server.capabilities[:3]:
                cap_label = QLabel(f"✨ {cap}")
                cap_label.setStyleSheet("""
                    background-color: #f0f0f0;
                    color: #333;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 9px;
                """)
                tags_layout.addWidget(cap_label)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("连接" if self.server.status != "online" else "断开")
        self.connect_btn.setFont(QFont("Microsoft YaHei", 9))
        self.connect_btn.clicked.connect(lambda: self._on_connect_click())
        btn_layout.addWidget(self.connect_btn)
        
        self.config_btn = QPushButton("配置")
        self.config_btn.setFont(QFont("Microsoft YaHei", 9))
        self.config_btn.clicked.connect(lambda: self.configure_requested.emit(self.server.id))
        btn_layout.addWidget(self.config_btn)
        
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setFont(QFont("Microsoft YaHei", 9))
        self.delete_btn.setStyleSheet("color: #e74c3c;")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.server.id))
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(btn_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            MCPServerCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            MCPServerCard:hover {
                border-color: #1890ff;
                background-color: #fafafa;
            }
        """)

    def _update_status(self):
        status_colors = {
            "online": "#2ecc71",
            "offline": "#95a5a6",
            "error": "#e74c3c",
            "connecting": "#f39c12"
        }
        color = status_colors.get(self.server.status, "#95a5a6")
        self.status_indicator.setStyleSheet(f"color: {color};")
        self.connect_btn.setText("断开" if self.server.status == "online" else "连接")

    def _on_connect_click(self):
        if self.server.status == "online":
            self.disconnect_requested.emit(self.server.id)
        else:
            self.connect_requested.emit(self.server.id)

    def update_server(self, server: MCPServer):
        self.server = server
        self.name_label.setText(server.name)
        self.desc_label.setText(server.description[:50] + "..." if len(server.description) > 50 else server.description)
        self.protocol_label.setText(f"🔌 {server.protocol}")
        self.url_label.setText(server.url[:30] + "..." if len(server.url) > 30 else server.url)
        self._update_status()


# ==================== MCP Market Panel ====================

class MCPMarketPanel(QWidget):
    """MCP Server 市场与管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化 MCP 数据库
        self.db_path = "~/.hermes-desktop/mcp_manager.db"
        self.db = MCPDatabase(self.db_path)
        
        # 服务器连接状态
        self._connections: Dict[str, QTcpSocket] = {}
        
        self._setup_ui()
        self._load_servers()
        self._start_status_check()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索 MCP Servers...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 1)
        
        # 来源筛选
        self.source_filter = QComboBox()
        self.source_filter.addItems(["全部来源", "本地", "远程", "市场"])
        self.source_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.source_filter)
        
        # 状态筛选
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部状态", "在线", "离线", "错误"])
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.status_filter)
        
        # 添加按钮
        self.add_btn = QPushButton("➕ 添加 Server")
        self.add_btn.setFont(QFont("Microsoft YaHei", 10))
        self.add_btn.clicked.connect(self._on_add_server)
        toolbar.addWidget(self.add_btn)
        
        main_layout.addLayout(toolbar)

        # 标签页：我的 Servers / 市场
        self.tabs = QTabWidget()
        
        # 我的 Servers 标签
        self.my_servers_tab = QWidget()
        self._setup_my_servers_tab()
        self.tabs.addTab(self.my_servers_tab, "📦 我的 Servers")
        
        # 市场标签
        self.market_tab = QWidget()
        self._setup_market_tab()
        self.tabs.addTab(self.market_tab, "🏪 市场")
        
        # 工具标签
        self.tools_tab = QWidget()
        self._setup_tools_tab()
        self.tabs.addTab(self.tools_tab, "🔧 工具列表")
        
        main_layout.addWidget(self.tabs)

    def _setup_my_servers_tab(self):
        layout = QVBoxLayout(self.my_servers_tab)
        
        # 服务器列表（网格布局）
        self.servers_scroll = QScrollArea()
        self.servers_scroll.setWidgetResizable(True)
        self.servers_scroll.setStyleSheet("border: none;")
        
        self.servers_container = QWidget()
        self.servers_grid = QGridLayout(self.servers_container)
        self.servers_grid.setSpacing(12)
        self.servers_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.servers_scroll.setWidget(self.servers_container)
        layout.addWidget(self.servers_scroll)

    def _setup_market_tab(self):
        layout = QVBoxLayout(self.market_tab)
        
        # 市场信息
        info_label = QLabel("🌐 发现并安装来自社区的 MCP Servers")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 市场服务器列表
        self.market_list = QListWidget()
        self.market_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
            }
        """)
        layout.addWidget(self.market_list)
        
        # 添加市场服务器按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.install_market_btn = QPushButton("📥 安装选中 Server")
        self.install_market_btn.clicked.connect(self._on_install_market)
        btn_layout.addWidget(self.install_market_btn)
        
        layout.addLayout(btn_layout)

    def _setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        
        # 工具列表表格
        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(4)
        self.tools_table.setHorizontalHeaderLabels(["Server", "工具名称", "描述", "参数 Schema"])
        self.tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tools_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.tools_table)

    def _load_servers(self):
        """加载服务器列表"""
        # 从数据库加载
        servers = self.db.get_all_servers()
        
        # 清空现有卡片
        while self.servers_grid.count():
            item = self.servers_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加服务器卡片
        for i, server in enumerate(servers):
            card = MCPServerCard(server)
            card.connect_requested.connect(self._on_connect)
            card.disconnect_requested.connect(self._on_disconnect)
            card.configure_requested.connect(self._on_configure)
            card.delete_requested.connect(self._on_delete)
            
            row = i // 2
            col = i % 2
            self.servers_grid.addWidget(card, row, col)

    def _on_search(self, text: str):
        """搜索过滤"""
        for i in range(self.servers_grid.count()):
            widget = self.servers_grid.itemAt(i).widget()
            if widget and isinstance(widget, MCPServerCard):
                visible = text.lower() in widget.server.name.lower() or text.lower() in widget.server.description.lower()
                widget.setVisible(visible)

    def _on_filter_changed(self):
        """来源/状态过滤"""
        source = self.source_filter.currentText()
        status = self.status_filter.currentText()
        
        for i in range(self.servers_grid.count()):
            widget = self.servers_grid.itemAt(i).widget()
            if widget and isinstance(widget, MCPServerCard):
                visible = True
                
                if source != "全部来源":
                    source_map = {"本地": "local", "远程": "remote", "市场": "market"}
                    visible = visible and widget.server.source == source_map.get(source, "")
                
                if status != "全部状态":
                    status_map = {"在线": "online", "离线": "offline", "错误": "error"}
                    visible = visible and widget.server.status == status_map.get(status, "")
                
                widget.setVisible(visible)

    def _on_add_server(self):
        """添加新 Server"""
        # 简单的输入对话框
        from PyQt6.QtWidgets import QInputDialog, QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle("添加 MCP Server")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Server 名称")
        layout.addRow("名称:", name_input)
        
        desc_input = QLineEdit()
        desc_input.setPlaceholderText("描述")
        layout.addRow("描述:", desc_input)
        
        url_input = QLineEdit()
        url_input.setPlaceholderText("http://localhost:8080")
        layout.addRow("URL:", url_input)
        
        protocol_combo = QComboBox()
        protocol_combo.addItems(["sse", "stdio", "http"])
        layout.addRow("协议:", protocol_combo)
        
        caps_input = QLineEdit()
        caps_input.setPlaceholderText("工具, 资源, 提示 (逗号分隔)")
        layout.addRow("能力:", caps_input)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("添加")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server = MCPServer(
                id=f"local_{int(time.time())}",
                name=name_input.text() or "Unnamed Server",
                description=desc_input.text(),
                url=url_input.text(),
                protocol=protocol_combo.currentText(),
                status="offline",
                source="local",
                capabilities=[c.strip() for c in caps_input.text().split(",") if c.strip()]
            )
            self.db.add_server(server)
            self._load_servers()

    def _on_connect(self, server_id: str):
        """连接 Server"""
        server = self.db.get_server(server_id)
        if not server:
            return
        
        # 尝试连接
        socket = QTcpSocket(self)
        self._connections[server_id] = socket
        
        # 解析 URL 获取主机和端口
        from urllib.parse import urlparse
        parsed = urlparse(server.url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080
        
        socket.connectToHost(host, port)
        socket.connected.connect(lambda: self._on_connected(server_id))
        socket.errorOccurred.connect(lambda e: self._on_connection_error(server_id, e))
        
        server.status = "connecting"
        self.db.update_server(server)
        self._load_servers()

    def _on_connected(self, server_id: str):
        """连接成功"""
        server = self.db.get_server(server_id)
        if server:
            server.status = "online"
            self.db.update_server(server)
            self._load_servers()

    def _on_connection_error(self, server_id: str, error):
        """连接错误"""
        server = self.db.get_server(server_id)
        if server:
            server.status = "error"
            server.last_error = str(error)
            self.db.update_server(server)
            self._load_servers()

    def _on_disconnect(self, server_id: str):
        """断开连接"""
        if server_id in self._connections:
            self._connections[server_id].disconnectFromHost()
            del self._connections[server_id]
        
        server = self.db.get_server(server_id)
        if server:
            server.status = "offline"
            self.db.update_server(server)
            self._load_servers()

    def _on_configure(self, server_id: str):
        """配置 Server"""
        server = self.db.get_server(server_id)
        if not server:
            return
        
        from PyQt6.QtWidgets import QInputDialog, QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"配置 {server.name}")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit(server.name)
        layout.addRow("名称:", name_input)
        
        url_input = QLineEdit(server.url)
        layout.addRow("URL:", url_input)
        
        auto_connect = QCheckBox()
        auto_connect.setChecked(server.auto_connect)
        layout.addRow("自动连接:", auto_connect)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("保存")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server.name = name_input.text()
            server.url = url_input.text()
            server.auto_connect = auto_connect.isChecked()
            server.updated_at = time.time()
            self.db.update_server(server)
            self._load_servers()

    def _on_delete(self, server_id: str):
        """删除 Server"""
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这个 Server 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_server(server_id)
            self._load_servers()

    def _on_install_market(self):
        """安装市场 Server"""
        current_item = self.market_list.currentItem()
        if current_item:
            # 获取市场服务器信息并安装
            pass

    def _start_status_check(self):
        """定期检查连接状态"""
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._check_connection_status)
        self._status_timer.start(5000)

    def _check_connection_status(self):
        """检查连接状态"""
        for server_id, socket in list(self._connections.items()):
            if socket.state() != QTcpSocket.SocketState.ConnectedState:
                server = self.db.get_server(server_id)
                if server and server.status == "online":
                    server.status = "offline"
                    self.db.update_server(server)
                    self._load_servers()


# ==================== 导出 ====================

__all__ = ['MCPMarketPanel', 'MCPServerCard']
