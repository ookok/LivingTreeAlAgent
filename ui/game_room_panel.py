# -*- coding: utf-8 -*-
"""
Game Room Panel - PyQt6 游戏房间与分享 UI
==========================================

功能：
- 游戏房间管理
- 玩家匹配
- 游戏分享（短链接/二维码/邀请码）
- 游戏状态同步

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QRadioButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPixmap

import asyncio
import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, List

from core.smart_ide_game import (
    SmartIDEGameSystem, RoomManager, GameRoom,
    GameShare, ShareLink, ShareMode,
    create_room_settings, GameType
)


# ==================== 房间卡片组件 ====================

class RoomCard(QFrame):
    """房间卡片组件"""

    join_requested = pyqtSignal(str)  # 加入信号
    spectate_requested = pyqtSignal(str)  # 观战信号

    def __init__(self, room: Dict, parent=None):
        super().__init__(parent)
        self.room = room
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 头部：房间名 + 状态
        header_layout = QHBoxLayout()
        
        self.name_label = QLabel(self.room.get('name', 'Unnamed Room'))
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        header_layout.addWidget(self.name_label)
        
        header_layout.addStretch()
        
        status_colors = {
            "waiting": "#2ecc71",
            "playing": "#f39c12",
            "closed": "#95a5a6"
        }
        status = self.room.get('status', 'waiting')
        status_label = QLabel(f"● {status}")
        status_label.setFont(QFont("Microsoft YaHei", 9))
        status_label.setStyleSheet(f"color: {status_colors.get(status, '#95a5a6')};")
        header_layout.addWidget(status_label)
        
        layout.addLayout(header_layout)

        # 游戏信息
        info_layout = QHBoxLayout()
        
        game_label = QLabel(f"🎮 {self.room.get('game_mode', 'Unknown')}")
        game_label.setFont(QFont("Microsoft YaHei", 9))
        info_layout.addWidget(game_label)
        
        players_label = QLabel(f"👥 {self.room.get('player_count', 0)}/{self.room.get('max_players', 8)}")
        players_label.setFont(QFont("Microsoft YaHei", 9))
        info_layout.addWidget(players_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 主机信息
        host_label = QLabel(f"🏠 主机: {self.room.get('host_name', 'Unknown')}")
        host_label.setFont(QFont("Microsoft YaHei", 9))
        host_label.setStyleSheet("color: #888;")
        layout.addWidget(host_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        
        join_btn = QPushButton("🎮 加入游戏")
        join_btn.setFont(QFont("Microsoft YaHei", 9))
        join_btn.clicked.connect(lambda: self.join_requested.emit(self.room.get('id', '')))
        btn_layout.addWidget(join_btn)
        
        spectate_btn = QPushButton("👁️ 观战")
        spectate_btn.setFont(QFont("Microsoft YaHei", 9))
        spectate_btn.clicked.connect(lambda: self.spectate_requested.emit(self.room.get('id', '')))
        btn_layout.addWidget(spectate_btn)
        
        layout.addLayout(btn_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            RoomCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            RoomCard:hover {
                border-color: #1890ff;
                background-color: #fafafa;
            }
        """)


# ==================== 分享卡片组件 ====================

class ShareCard(QFrame):
    """分享卡片组件"""

    def __init__(self, share_link: ShareLink, parent=None):
        super().__init__(parent)
        self.share_link = share_link
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 类型标签
        type_label = QLabel(f"[{self.share_link.share_mode.value}]")
        type_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        type_label.setStyleSheet("""
            background-color: #e6f7ff;
            color: #1890ff;
            border-radius: 4px;
            padding: 2px 8px;
        """)
        layout.addWidget(type_label)

        # 分享信息
        info_layout = QVBoxLayout()
        
        id_label = QLabel(f"ID: {self.share_link.id[:16]}...")
        id_label.setFont(QFont("Consolas", 9))
        id_label.setStyleSheet("color: #666;")
        info_layout.addWidget(id_label)
        
        created_label = QLabel(f"创建: {datetime.fromtimestamp(self.share_link.created_at).strftime('%Y-%m-%d %H:%M')}")
        created_label.setFont(QFont("Microsoft YaHei", 9))
        created_label.setStyleSheet("color: #888;")
        info_layout.addWidget(created_label)
        
        expires_label = QLabel(f"过期: {datetime.fromtimestamp(self.share_link.expires_at).strftime('%Y-%m-%d %H:%M') if self.share_link.expires_at else '永不过期'}")
        expires_label.setFont(QFont("Microsoft YaHei", 9))
        expires_label.setStyleSheet("color: #888;")
        info_layout.addWidget(expires_label)
        
        layout.addLayout(info_layout)

        # 链接
        self.link_label = QLabel(self.share_link.short_url if hasattr(self.share_link, 'short_url') else self.share_link.url)
        self.link_label.setFont(QFont("Consolas", 8))
        self.link_label.setStyleSheet("color: #1890ff; word-wrap: break-all;")
        self.link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.link_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 复制链接")
        copy_btn.setFont(QFont("Microsoft YaHei", 9))
        copy_btn.clicked.connect(self._on_copy)
        btn_layout.addWidget(copy_btn)
        
        qr_btn = QPushButton("📱 二维码")
        qr_btn.setFont(QFont("Microsoft YaHei", 9))
        qr_btn.clicked.connect(self._on_show_qr)
        btn_layout.addWidget(qr_btn)
        
        layout.addLayout(btn_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            ShareCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            ShareCard:hover {
                border-color: #52c41a;
            }
        """)

    def _on_copy(self):
        """复制链接"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.link_label.text())
        
    def _on_show_qr(self):
        """显示二维码"""
        pass


# ==================== Game Room Panel ====================

class GameRoomPanel(QWidget):
    """游戏房间面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化系统
        self.storage_path = "~/.hermes-desktop/smart_ide_game"
        self.system = SmartIDEGameSystem(self.storage_path)
        
        # 当前房间
        self.current_room: Optional[GameRoom] = None
        
        self._setup_ui()
        self._refresh_rooms()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新房间")
        refresh_btn.clicked.connect(self._refresh_rooms)
        toolbar.addWidget(refresh_btn)
        
        # 创建房间按钮
        create_btn = QPushButton("➕ 创建房间")
        create_btn.clicked.connect(self._on_create_room)
        toolbar.addWidget(create_btn)
        
        toolbar.addStretch()
        
        # 游戏模式筛选
        mode_label = QLabel("游戏模式:")
        toolbar.addWidget(mode_label)
        
        self.mode_filter = QComboBox()
        self.mode_filter.addItems(["全部", "单人", "多人", "观战"])
        self.mode_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.mode_filter)
        
        main_layout.addLayout(toolbar)

        # 标签页：房间列表 / 我的房间 / 分享管理
        self.tabs = QTabWidget()
        
        # 房间列表
        self.rooms_tab = QWidget()
        self._setup_rooms_tab()
        self.tabs.addTab(self.rooms_tab, "🏠 房间列表")
        
        # 我的房间
        self.my_rooms_tab = QWidget()
        self._setup_my_rooms_tab()
        self.tabs.addTab(self.my_rooms_tab, "📦 我的房间")
        
        # 分享管理
        self.shares_tab = QWidget()
        self._setup_shares_tab()
        self.tabs.addTab(self.shares_tab, "🔗 分享管理")
        
        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #888;")
        main_layout.addWidget(self.status_label)

    def _setup_rooms_tab(self):
        layout = QVBoxLayout(self.rooms_tab)
        
        self.rooms_scroll = QScrollArea()
        self.rooms_scroll.setWidgetResizable(True)
        self.rooms_scroll.setStyleSheet("border: none;")
        
        self.rooms_container = QWidget()
        self.rooms_grid = QGridLayout(self.rooms_container)
        self.rooms_grid.setSpacing(12)
        self.rooms_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.rooms_scroll.setWidget(self.rooms_container)
        layout.addWidget(self.rooms_scroll)

    def _setup_my_rooms_tab(self):
        layout = QVBoxLayout(self.my_rooms_tab)
        
        info_label = QLabel("📦 你创建或加入的房间")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        self.my_rooms_list = QListWidget()
        self.my_rooms_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        layout.addWidget(self.my_rooms_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        leave_btn = QPushButton("🚪 离开房间")
        leave_btn.setStyleSheet("color: #e74c3c;")
        leave_btn.clicked.connect(self._on_leave_room)
        btn_layout.addWidget(leave_btn)
        
        share_btn = QPushButton("🔗 分享房间")
        share_btn.clicked.connect(self._on_share_current_room)
        btn_layout.addWidget(share_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _setup_shares_tab(self):
        layout = QVBoxLayout(self.shares_tab)
        
        info_label = QLabel("🔗 管理你的游戏分享链接")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        self.shares_list = QListWidget()
        self.shares_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        layout.addWidget(self.shares_list)

    def _refresh_rooms(self):
        """刷新房间列表"""
        # 清空现有卡片
        while self.rooms_grid.count():
            item = self.rooms_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取房间列表
        rooms = self.system.get_room_list()
        
        # 添加房间卡片
        for i, room in enumerate(rooms):
            card = RoomCard(room)
            card.join_requested.connect(self._on_join_room)
            card.spectate_requested.connect(self._on_spectate_room)
            
            row = i // 2
            col = i % 2
            self.rooms_grid.addWidget(card, row, col)
        
        self.status_label.setText(f"发现 {len(rooms)} 个房间")

    def _on_filter_changed(self, mode: str):
        """筛选模式"""
        for i in range(self.rooms_grid.count()):
            widget = self.rooms_grid.itemAt(i).widget()
            if widget and isinstance(widget, RoomCard):
                if mode == "全部":
                    widget.setVisible(True)
                elif mode == "单人":
                    widget.setVisible(widget.room.get('game_mode') == 'single')
                elif mode == "多人":
                    widget.setVisible(widget.room.get('game_mode') == 'multiplayer')
                elif mode == "观战":
                    widget.setVisible(widget.room.get('game_mode') == 'spectate')

    def _on_create_room(self):
        """创建房间"""
        from PyQt6.QtWidgets import QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle("创建游戏房间")
        dialog.setMinimumWidth(400)
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("房间名称")
        layout.addRow("房间名:", name_input)
        
        game_mode = QComboBox()
        game_mode.addItems(["deathmatch", "team_battle", "cooperative", "single_player"])
        layout.addRow("游戏模式:", game_mode)
        
        max_players = QSpinBox()
        max_players.setMinimum(2)
        max_players.setMaximum(16)
        max_players.setValue(8)
        layout.addRow("最大玩家:", max_players)
        
        password = QLineEdit()
        password.setPlaceholderText("密码（可选）")
        layout.addRow("密码:", password)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("创建")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            room_name = name_input.text() or "Unnamed Room"
            settings = create_room_settings(
                room_name=room_name,
                max_players=max_players.value(),
                game_mode=game_mode.currentText()
            )
            
            room = self.system.create_game_room(
                host_id="local_user",
                host_name="Me",
                settings=settings
            )
            
            self.current_room = room
            self.status_label.setText(f"已创建房间: {room_name}")
            self._refresh_rooms()
            self._update_my_rooms()

    def _on_join_room(self, room_id: str):
        """加入房间"""
        room = self.system.join_game_room(
            room_id=room_id,
            user_id="local_user",
            username="Me"
        )
        
        if room:
            self.current_room = room
            self.status_label.setText(f"已加入房间: {room.name}")
            self._update_my_rooms()
        else:
            QMessageBox.warning(self, "错误", "无法加入房间")

    def _on_spectate_room(self, room_id: str):
        """观战"""
        self.status_label.setText(f"正在观战房间: {room_id}")

    def _on_leave_room(self):
        """离开房间"""
        if self.current_room:
            success = self.system.leave_game_room("local_user")
            if success:
                self.current_room = None
                self.status_label.setText("已离开房间")
                self._update_my_rooms()
            else:
                QMessageBox.warning(self, "错误", "无法离开房间")

    def _on_share_current_room(self):
        """分享当前房间"""
        if not self.current_room:
            QMessageBox.information(self, "提示", "请先创建一个或加入一个房间")
            return
        
        self._create_share_link(self.current_room.id)

    def _create_share_link(self, room_id: str):
        """创建分享链接"""
        def create():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                share_link = loop.run_until_complete(
                    self.system.share_room(room_id, "local_user", expires_in_hours=24)
                )
                loop.close()
                
                self._add_share_card(share_link)
                self.status_label.setText(f"已创建分享链接")
            except Exception as e:
                self.status_label.setText(f"创建分享链接失败: {e}")
        
        QTimer.singleShot(100, create)

    def _add_share_card(self, share_link: ShareLink):
        """添加分享卡片"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(280, 160))
        self.shares_list.addItem(item)
        
        card = ShareCard(share_link)
        self.shares_list.setItemWidget(item, card)

    def _update_my_rooms(self):
        """更新我的房间列表"""
        self.my_rooms_list.clear()
        
        if self.current_room:
            item = QListWidgetItem()
            item.setSizeHint(QSize(300, 60))
            self.my_rooms_list.addItem(item)
            
            widget = QLabel(f"🏠 {self.current_room.name} ({self.current_room.settings.game_mode})")
            widget.setFont(QFont("Microsoft YaHei", 10))
            self.my_rooms_list.setItemWidget(item, widget)


# ==================== 导出 ====================

__all__ = ['GameRoomPanel', 'RoomCard', 'ShareCard']
