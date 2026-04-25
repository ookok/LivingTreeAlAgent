"""
WebSocket 中继面板 UI
WebSocket Relay Panel UI

功能：
- 服务器连接管理
- 会话创建/加入
- 消息发送与接收
- 连接状态显示
- 二维码生成（会话分享）
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QFrame, QDialog, QDialogButtonBox, QMessageBox,
    QComboBox, QSpinBox, QCheckBox, QTabWidget, QScrollArea,
    QStatusBar, QMenuBar, QMenu, QToolBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QAction, QPainter, QPixmap, QImage

logger = logging.getLogger(__name__)


# QR Code generation (optional dependency)
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    logger.warning("qrcode library not available. Install with: pip install qrcode[pil]")


class ConnectionStatusWidget(QWidget):
    """连接状态显示组件"""
    
    STATUS_COLORS = {
        "disconnected": "#999999",
        "connecting": "#FFA500",
        "connected": "#4CAF50",
        "authenticated": "#2196F3",
        "error": "#F44336"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "disconnected"
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {self.STATUS_COLORS['disconnected']}; font-size: 16px;")
        
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #666666; font-size: 12px;")
        
        layout.addWidget(self.status_dot)
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_status(self, status: str):
        """设置连接状态"""
        self._status = status
        color = self.STATUS_COLORS.get(status, "#999999")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        
        status_text = {
            "disconnected": "未连接",
            "connecting": "连接中...",
            "connected": "已连接",
            "authenticated": "已认证",
            "error": "连接错误"
        }
        self.status_label.setText(status_text.get(status, status))
    
    def get_status(self) -> str:
        return self._status


class ServerConfigDialog(QDialog):
    """服务器配置对话框"""
    
    def __init__(self, parent=None, current_config: Optional[Dict] = None):
        super().__init__(parent)
        self.current_config = current_config or {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("服务器配置")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 服务器地址
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("服务器地址:"))
        self.addr_input = QLineEdit()
        self.addr_input.setText(self.current_config.get("server_url", "ws://localhost:8765"))
        addr_layout.addWidget(self.addr_input)
        layout.addLayout(addr_layout)
        
        # 客户端名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("客户端名称:"))
        self.name_input = QLineEdit()
        self.name_input.setText(self.current_config.get("client_name", ""))
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 客户端类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("客户端类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["桌面端", "移动端", "网页端"])
        type_map = {"desktop": 0, "mobile": 1, "web": 2}
        self.type_combo.setCurrentIndex(type_map.get(self.current_config.get("client_type", "desktop"), 0))
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # 自动重连
        self.auto_reconnect = QCheckBox("自动重连")
        self.auto_reconnect.setChecked(self.current_config.get("auto_reconnect", True))
        layout.addWidget(self.auto_reconnect)
        
        # 确定/取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_config(self) -> Dict[str, Any]:
        type_map = {0: "desktop", 1: "mobile", 2: "web"}
        return {
            "server_url": self.addr_input.text(),
            "client_name": self.name_input.text(),
            "client_type": type_map.get(self.type_combo.currentIndex(), "desktop"),
            "auto_reconnect": self.auto_reconnect.isChecked()
        }


class SessionCreateDialog(QDialog):
    """创建会话对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("创建会话")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout()
        
        # 会话名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("会话名称:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("可选")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 会话密码
        pwd_layout = QHBoxLayout()
        pwd_layout.addWidget(QLabel("会话密码:"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("可选")
        pwd_layout.addWidget(self.pwd_input)
        layout.addLayout(pwd_layout)
        
        # 最大客户端数
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("最大人数:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(2, 100)
        self.max_spin.setValue(10)
        max_layout.addWidget(self.max_spin)
        layout.addLayout(max_layout)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_session_config(self) -> Dict[str, Any]:
        return {
            "name": self.name_input.text(),
            "password": self.pwd_input.text(),
            "max_clients": self.max_spin.value()
        }


class QRCodeDialog(QDialog):
    """二维码显示对话框"""
    
    def __init__(self, session_id: str, server_url: str, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.server_url = server_url
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("分享会话")
        self.setMinimumSize(400, 450)
        
        layout = QVBoxLayout()
        
        # 会话ID
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("会话ID:"))
        self.session_id_label = QLabel(f"<b>{self.session_id}</b>")
        self.session_id_label.setStyleSheet("color: #2196F3; font-size: 16px;")
        id_layout.addWidget(self.session_id_label)
        id_layout.addStretch()
        layout.addLayout(id_layout)
        
        # 二维码
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumSize(300, 300)
        layout.addWidget(self.qr_label)
        
        # 生成二维码
        self._generate_qr_code()
        
        # 说明
        info_label = QLabel("使用移动端扫码加入会话")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(info_label)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def _generate_qr_code(self):
        """生成二维码"""
        if QRCODE_AVAILABLE:
            # 生成连接信息
            connect_info = json.dumps({
                "session_id": self.session_id,
                "server": self.server_url
            })
            
            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(connect_info)
            qr.make(fit=True)
            
            # 转换为Pixmap
            img = qr.make_image(fill_color="black", back_color="white")
            qt_image = QImage(img.size[0], img.size[1], QImage.Format.Format_RGB32)
            
            for y in range(img.size[1]):
                for x in range(img.size[0]):
                    qt_image.setPixelColor(x, y, img.getpixel((x, y)) or 0xFFFFFF)
            
            pixmap = QPixmap.fromImage(qt_image)
            self.qr_label.setPixmap(pixmap.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.qr_label.setText("请安装 qrcode 库以生成二维码\npip install qrcode[pil]")
            self.qr_label.setStyleSheet("color: #F44336; font-size: 14px;")


class RelayPanel(QWidget):
    """中继面板主组件"""
    
    # 信号定义
    message_sent = pyqtSignal(dict)       # 发送消息
    session_created = pyqtSignal(str)     # 会话创建
    session_joined = pyqtSignal(str)       # 加入会话
    connected = pyqtSignal(dict)          # 连接成功
    disconnected = pyqtSignal()           # 断开连接
    
    def __init__(self, relay_client=None, parent=None):
        super().__init__(parent)
        self.relay_client = relay_client
        self.setup_ui()
        self._setup_timer()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout()
        
        # ===== 连接状态栏 =====
        status_bar = QFrame()
        status_bar.setStyleSheet("background-color: #f5f5f5; border-radius: 4px;")
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_widget = ConnectionStatusWidget()
        status_layout.addWidget(self.status_widget)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self._on_connect_click)
        status_layout.addWidget(self.connect_btn)
        
        self.config_btn = QPushButton("配置")
        self.config_btn.setFixedWidth(60)
        self.config_btn.clicked.connect(self._on_config_click)
        status_layout.addWidget(self.config_btn)
        
        status_bar.setLayout(status_layout)
        main_layout.addWidget(status_bar)
        
        # ===== 标签页 =====
        self.tabs = QTabWidget()
        
        # ----- 会话标签 -----
        session_tab = QWidget()
        session_layout = QVBoxLayout()
        
        # 会话操作
        ops_group = QGroupBox("会话操作")
        ops_layout = QHBoxLayout()
        
        self.create_session_btn = QPushButton("创建会话")
        self.create_session_btn.clicked.connect(self._on_create_session)
        self.create_session_btn.setEnabled(False)
        ops_layout.addWidget(self.create_session_btn)
        
        self.join_session_btn = QPushButton("加入会话")
        self.join_session_btn.clicked.connect(self._on_join_session)
        self.join_session_btn.setEnabled(False)
        ops_layout.addWidget(self.join_session_btn)
        
        self.share_btn = QPushButton("分享")
        self.share_btn.clicked.connect(self._on_share_session)
        self.share_btn.setEnabled(False)
        ops_layout.addWidget(self.share_btn)
        
        ops_group.setLayout(ops_layout)
        session_layout.addWidget(ops_group)
        
        # 加入会话输入
        join_layout = QHBoxLayout()
        self.join_id_input = QLineEdit()
        self.join_id_input.setPlaceholderText("输入会话ID")
        join_layout.addWidget(self.join_id_input)
        self.join_btn = QPushButton("加入")
        self.join_btn.clicked.connect(self._on_join_by_id)
        self.join_btn.setEnabled(False)
        join_layout.addWidget(self.join_btn)
        session_layout.addLayout(join_layout)
        
        # 当前会话信息
        self.session_info = QLabel("未加入任何会话")
        self.session_info.setStyleSheet("color: #666666; padding: 10px;")
        session_layout.addWidget(self.session_info)
        
        # 成员列表
        members_label = QLabel("会话成员:")
        session_layout.addWidget(members_label)
        
        self.members_list = QListWidget()
        session_layout.addWidget(self.members_list)
        
        session_tab.setLayout(session_layout)
        self.tabs.addTab(session_tab, "会话")
        
        # ----- 消息标签 -----
        msg_tab = QWidget()
        msg_layout = QVBoxLayout()
        
        # 消息显示
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        self.message_area.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        msg_layout.addWidget(self.message_area)
        
        # 发送区域
        send_layout = QHBoxLayout()
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("输入消息...")
        self.send_input.returnPressed.connect(self._on_send_message)
        send_layout.addWidget(self.send_input)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._on_send_message)
        self.send_btn.setEnabled(False)
        send_layout.addWidget(self.send_btn)
        
        msg_layout.addLayout(send_layout)
        
        msg_tab.setLayout(msg_layout)
        self.tabs.addTab(msg_tab, "消息")
        
        # ----- 设置标签 -----
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        
        # 自动重连
        self.auto_reconnect = QCheckBox("连接断开时自动重连")
        self.auto_reconnect.setChecked(True)
        settings_layout.addWidget(self.auto_reconnect)
        
        # 心跳间隔
        heartbeat_layout = QHBoxLayout()
        heartbeat_layout.addWidget(QLabel("心跳间隔(秒):"))
        self.heartbeat_spin = QSpinBox()
        self.heartbeat_spin.setRange(10, 300)
        self.heartbeat_spin.setValue(30)
        heartbeat_layout.addWidget(self.heartbeat_spin)
        heartbeat_layout.addStretch()
        settings_layout.addLayout(heartbeat_layout)
        
        # 清空消息按钮
        clear_btn = QPushButton("清空消息记录")
        clear_btn.clicked.connect(self._on_clear_messages)
        settings_layout.addWidget(clear_btn)
        
        settings_layout.addStretch()
        settings_tab.setLayout(settings_layout)
        self.tabs.addTab(settings_tab, "设置")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
    
    def _setup_timer(self):
        """设置定时器"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)
    
    def _update_status(self):
        """更新状态显示"""
        if self.relay_client:
            status = self.relay_client.state.value
            self.status_widget.set_status(status)
            
            # 更新按钮状态
            is_connected = status in ["connected", "authenticated"]
            self.create_session_btn.setEnabled(is_connected)
            self.join_session_btn.setEnabled(is_connected)
            self.join_btn.setEnabled(is_connected)
            self.send_btn.setEnabled(is_connected and self.relay_client.current_session)
            self.share_btn.setEnabled(bool(self.relay_client.current_session))
            
            if status == "disconnected":
                self.connect_btn.setText("连接")
            else:
                self.connect_btn.setText("断开")
    
    def _on_connect_click(self):
        """连接/断开按钮点击"""
        if self.relay_client and self.relay_client.state.value != "disconnected":
            # 断开连接
            self.relay_client.disconnect()
            self._add_system_message("已断开连接")
        else:
            # 显示配置对话框
            config, ok = ServerConfigDialog.getConfig(self)
            if ok:
                self._connect_with_config(config)
    
    def _connect_with_config(self, config: Dict[str, Any]):
        """使用配置连接"""
        if not self.relay_client:
            from client.src.business.relay_client import create_relay_client, ClientType
            
            type_map = {"desktop": ClientType.DESKTOP, "mobile": ClientType.MOBILE, "web": ClientType.WEB}
            
            self.relay_client = create_relay_client(
                server_url=config["server_url"],
                client_name=config["client_name"],
                client_type=type_map.get(config["client_type"], ClientType.DESKTOP),
                auto_reconnect=config["auto_reconnect"]
            )
            
            # 设置回调
            self.relay_client.on_connected = self._on_connected
            self.relay_client.on_disconnected = self._on_disconnected
            self.relay_client.on_message = self._on_message_received
            self.relay_client.on_session_created = self._on_session_created
            self.relay_client.on_session_joined = self._on_session_joined
            self.relay_client.on_session_left = self._on_session_left
        
        try:
            self.relay_client.connect()
            self.status_widget.set_status("connecting")
            self._add_system_message(f"正在连接 {config['server_url']}...")
        except Exception as e:
            self._add_system_message(f"连接失败: {e}", is_error=True)
    
    def _on_config_click(self):
        """配置按钮点击"""
        config, ok = ServerConfigDialog.get_current_config(self) if hasattr(ServerConfigDialog, 'get_current_config') else ServerConfigDialog(self).exec()
        if ok:
            pass  # 配置已保存，下次连接时使用
    
    def _on_create_session(self):
        """创建会话"""
        dialog = SessionCreateDialog(self)
        if dialog.exec():
            config = dialog.get_session_config()
            if self.relay_client:
                self.relay_client.create_session(**config)
                self._add_system_message("正在创建会话...")
    
    def _on_join_session(self):
        """加入会话按钮点击"""
        # 显示会话ID输入
        self.join_id_input.setFocus()
    
    def _on_join_by_id(self):
        """通过ID加入会话"""
        session_id = self.join_id_input.text().strip().upper()
        if session_id and self.relay_client:
            self.relay_client.join_session(session_id)
            self._add_system_message(f"正在加入会话 {session_id}...")
    
    def _on_share_session(self):
        """分享会话"""
        if self.relay_client and self.relay_client.current_session:
            dialog = QRCodeDialog(
                self.relay_client.current_session,
                self.relay_client.server_url,
                self
            )
            dialog.exec()
    
    def _on_send_message(self):
        """发送消息"""
        text = self.send_input.text().strip()
        if text and self.relay_client and self.relay_client.current_session:
            self.relay_client.broadcast({"text": text})
            self._add_message("我", text, is_me=True)
            self.send_input.clear()
    
    def _on_clear_messages(self):
        """清空消息"""
        self.message_area.clear()
    
    def _on_connected(self, data: Dict):
        """连接成功回调"""
        self.status_widget.set_status("authenticated")
        self._add_system_message(f"连接成功! 客户端ID: {data.get('client_id', 'N/A')}")
        self.connected.emit(data)
    
    def _on_disconnected(self):
        """断开连接回调"""
        self.status_widget.set_status("disconnected")
        self._add_system_message("连接已断开")
        self.disconnected.emit()
    
    def _on_message_received(self, data: Dict):
        """消息接收回调"""
        sender = data.get("from_name", data.get("from", "Unknown"))
        text = data.get("text", "")
        self._add_message(sender, text)
        self.message_received.emit(data)
    
    def _on_session_created(self, data: Dict):
        """会话创建回调"""
        session_id = data.get("session_id")
        self._add_system_message(f"会话已创建: {session_id}")
        self.session_info.setText(f"当前会话: {session_id}")
        self.members_list.clear()
        self.members_list.addItem(f"我 (主持人)")
        self.session_created.emit(session_id)
    
    def _on_session_joined(self, data: Dict):
        """加入会话回调"""
        session_id = data.get("session_id")
        members = data.get("members", [])
        self._add_system_message(f"已加入会话: {session_id}")
        self.session_info.setText(f"当前会话: {session_id}")
        self.members_list.clear()
        for m in members:
            self.members_list.addItem(f"{m.get('name', 'Unknown')} ({m.get('client_type', 'unknown')})")
        self.session_joined.emit(session_id)
    
    def _on_session_left(self, data: Dict):
        """离开会话回调"""
        self._add_system_message("已离开会话")
        self.session_info.setText("未加入任何会话")
        self.members_list.clear()
    
    def _add_message(self, sender: str, text: str, is_me: bool = False):
        """添加消息到显示区域"""
        color = "#2196F3" if is_me else "#4CAF50"
        time_str = time.strftime("%H:%M:%S")
        self.message_area.append(
            f'<span style="color: #999999;">[{time_str}]</span> '
            f'<span style="color: {color};"><b>{sender}:</b></span> {text}'
        )
    
    def _add_system_message(self, text: str, is_error: bool = False):
        """添加系统消息"""
        color = "#F44336" if is_error else "#FF9800"
        time_str = time.strftime("%H:%M:%S")
        self.message_area.append(
            f'<span style="color: #999999;">[{time_str}]</span> '
            f'<span style="color: {color};"><b>[系统]</b></span> {text}'
        )
    
    def set_client(self, client):
        """设置中继客户端"""
        self.relay_client = client


def show_relay_panel_demo():
    """演示入口"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("WebSocket 中继面板演示")
    window.setMinimumSize(500, 600)
    
    layout = QVBoxLayout()
    
    # 标题
    title = QLabel("<h2>WebSocket 中继面板</h2>")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    
    # 说明
    info = QLabel("""
    <p>演示说明：</p>
    <ol>
        <li>点击"配置"设置服务器地址</li>
        <li>点击"连接"连接到中继服务器</li>
        <li>创建或加入会话</li>
        <li>在消息标签发送消息</li>
    </ol>
    <p><b>注意：</b>需要先运行中继服务器<br/>
    <code>python -m core.relay_server</code></p>
    """)
    info.setWordWrap(True)
    layout.addWidget(info)
    
    # 中继面板
    panel = RelayPanel()
    layout.addWidget(panel)
    
    window.setLayout(layout)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    show_relay_panel_demo()
