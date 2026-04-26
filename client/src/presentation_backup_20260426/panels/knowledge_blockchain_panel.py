# -*- coding: utf-8 -*-
"""
Knowledge Blockchain Panel - PyQt6 知识区块链 UI
===============================================

功能：
- 知识区块链浏览
- 共识机制可视化
- 知识单元管理
- 代币经济系统
- 信誉评分

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
    QInputDialog, QDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen, QBrush

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List

from client.src.business.knowledge_blockchain import (
    KnowledgeBlockchain, KnowledgeUnit, Block,
    ConsensusEngine, ReputationSystem,
    KnowledgeGraph, DialogueSystem
)


# ==================== 区块卡片组件 ====================

class BlockCard(QFrame):
    """区块卡片组件"""

    def __init__(self, block: Block, parent=None):
        super().__init__(parent)
        self.block = block
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 区块头部
        header_layout = QHBoxLayout()
        
        block_num_label = QLabel(f"区块 #{self.block.block_number}")
        block_num_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        header_layout.addWidget(block_num_label)
        
        header_layout.addStretch()
        
        hash_label = QLabel(f"Hash: {self.block.hash[:16]}...")
        hash_label.setFont(QFont("Consolas", 8))
        hash_label.setStyleSheet("color: #666;")
        header_layout.addWidget(hash_label)
        
        layout.addLayout(header_layout)

        # 时间戳
        time_label = QLabel(f"⏰ {datetime.fromtimestamp(self.block.timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        time_label.setFont(QFont("Microsoft YaHei", 9))
        time_label.setStyleSheet("color: #888;")
        layout.addWidget(time_label)

        # Merkle 根
        merkle_label = QLabel(f"🌳 Merkle: {self.block.merkle_root[:24]}...")
        merkle_label.setFont(QFont("Consolas", 8))
        merkle_label.setStyleSheet("color: #999;")
        merkle_label.setWordWrap(True)
        layout.addWidget(merkle_label)

        # 交易数量
        tx_count = len(self.block.transactions)
        tx_label = QLabel(f"📝 {tx_count} 笔交易")
        tx_label.setFont(QFont("Microsoft YaHei", 9))
        tx_label.setStyleSheet("color: #1890ff;")
        layout.addWidget(tx_label)

        # 验证状态
        verified_label = QLabel("✅ 已验证" if self.block.is_valid else "❌ 未验证")
        verified_label.setFont(QFont("Microsoft YaHei", 9))
        verified_label.setStyleSheet("color: #2ecc71;" if self.block.is_valid else "color: #e74c3c;")
        layout.addWidget(verified_label)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            BlockCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            BlockCard:hover {
                border-color: #1890ff;
            }
        """)


# ==================== 知识单元卡片 ====================

class KnowledgeUnitCard(QFrame):
    """知识单元卡片"""

    def __init__(self, unit: KnowledgeUnit, parent=None):
        super().__init__(parent)
        self.unit = unit
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 头部
        header_layout = QHBoxLayout()
        
        type_label = QLabel(f"[{self.unit.content_type}]")
        type_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        type_label.setStyleSheet("""
            background-color: #e6f7ff;
            color: #1890ff;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header_layout.addWidget(type_label)
        
        header_layout.addStretch()
        
        id_label = QLabel(f"ID: {self.unit.id[:16]}...")
        id_label.setFont(QFont("Consolas", 8))
        id_label.setStyleSheet("color: #888;")
        header_layout.addWidget(id_label)
        
        layout.addLayout(header_layout)

        # 标题
        title_label = QLabel(self.unit.title)
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 摘要
        summary_label = QLabel(self.unit.summary[:100] + "..." if len(self.unit.summary) > 100 else self.unit.summary)
        summary_label.setFont(QFont("Microsoft YaHei", 9))
        summary_label.setStyleSheet("color: #666;")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # 统计
        stats_layout = QHBoxLayout()
        
        author_label = QLabel(f"👤 {self.unit.author[:16]}...")
        author_label.setFont(QFont("Microsoft YaHei", 9))
        author_label.setStyleSheet("color: #888;")
        stats_layout.addWidget(author_label)
        
        votes_label = QLabel(f"👍 {self.unit.votes}")
        votes_label.setFont(QFont("Microsoft YaHei", 9))
        votes_label.setStyleSheet("color: #2ecc71;")
        stats_layout.addWidget(votes_label)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            KnowledgeUnitCard {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            KnowledgeUnitCard:hover {
                border-color: #722ed1;
            }
        """)


# ==================== 信誉仪表盘 ====================

class ReputationGauge(QFrame):
    """信誉仪表盘"""

    def __init__(self, score: float, level: str, parent=None):
        super().__init__(parent)
        self.score = score
        self.level = level
        self.setMinimumSize(150, 100)
        self.setMaximumSize(150, 100)

    def set_score(self, score: float, level: str):
        self.score = score
        self.level = level
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景半圆
        rect = self.rect().adjusted(10, 10, -10, -20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#f0f0f0")))
        painter.drawPie(rect, 180 * 16, 180 * 16)
        
        # 进度弧
        if self.score > 0:
            progress = min(self.score / 100, 1.0)
            color = QColor("#52c41a") if self.score >= 60 else QColor("#faad14") if self.score >= 30 else QColor("#f5222d")
            painter.setPen(QPen(color, 8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(rect, 180 * 16, -int(progress * 180 * 16))
        
        # 中心文字
        painter.setPen(QPen(QColor("#333")))
        painter.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, 0, 0, -10), Qt.AlignmentFlag.AlignCenter, f"{self.score:.1f}")
        
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QPen(QColor("#888")))
        painter.drawText(self.rect().adjusted(0, 20, 0, 0), Qt.AlignmentFlag.AlignCenter, self.level)


# ==================== 知识区块链面板 ====================

class KnowledgeBlockchainPanel(QWidget):
    """知识区块链面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化区块链
        self.blockchain = KnowledgeBlockchain()
        self.consensus = ConsensusEngine()
        self.reputation = ReputationSystem()
        self.knowledge_graph = KnowledgeGraph()
        self.dialogue = DialogueSystem()
        
        self._setup_ui()
        self._refresh_chain()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 顶部概览
        overview_layout = QHBoxLayout()
        
        # 区块链概览
        chain_group = QGroupBox("⛓️ 区块链概览")
        chain_layout = QVBoxLayout()
        
        stats_layout = QHBoxLayout()
        self.blocks_count_label = QLabel("区块数: 0")
        stats_layout.addWidget(self.blocks_count_label)
        
        self.units_count_label = QLabel("知识单元: 0")
        stats_layout.addWidget(self.units_count_label)
        
        self.pending_label = QLabel("待验证: 0")
        stats_layout.addWidget(self.pending_label)
        
        chain_layout.addLayout(stats_layout)
        chain_group.setLayout(chain_layout)
        overview_layout.addWidget(chain_group)
        
        # 共识状态
        consensus_group = QGroupBox("⚙️ 共识状态")
        consensus_layout = QVBoxLayout()
        
        self.consensus_status_label = QLabel("🟢 运行中")
        self.consensus_status_label.setFont(QFont("Microsoft YaHei", 10))
        consensus_layout.addWidget(self.consensus_status_label)
        
        self.consensus_rounds_label = QLabel("共识轮次: 0")
        consensus_layout.addWidget(self.consensus_rounds_label)
        
        consensus_group.setLayout(consensus_layout)
        overview_layout.addWidget(consensus_group)
        
        # 信誉仪表盘
        reputation_group = QGroupBox("🏆 我的信誉")
        reputation_layout = QVBoxLayout()
        
        self.reputation_gauge = ReputationGauge(0, "新手")
        reputation_layout.addWidget(self.reputation_gauge)
        
        reputation_group.setLayout(reputation_layout)
        overview_layout.addWidget(reputation_group)
        
        main_layout.addLayout(overview_layout)

        # 标签页
        self.tabs = QTabWidget()
        
        # 区块链浏览器
        self.chain_tab = QWidget()
        self._setup_chain_tab()
        self.tabs.addTab(self.chain_tab, "⛓️ 区块链")
        
        # 知识单元
        self.knowledge_tab = QWidget()
        self._setup_knowledge_tab()
        self.tabs.addTab(self.knowledge_tab, "📚 知识单元")
        
        # 共识治理
        self.consensus_tab = QWidget()
        self._setup_consensus_tab()
        self.tabs.addTab(self.consensus_tab, "⚙️ 共识治理")
        
        # 对话系统
        self.dialogue_tab = QWidget()
        self._setup_dialogue_tab()
        self.tabs.addTab(self.dialogue_tab, "💬 知识对话")
        
        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #888;")
        main_layout.addWidget(self.status_label)

    def _setup_chain_tab(self):
        layout = QVBoxLayout(self.chain_tab)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_chain)
        toolbar.addWidget(refresh_btn)
        
        add_block_btn = QPushButton("➕ 添加区块")
        add_block_btn.clicked.connect(self._on_add_block)
        toolbar.addWidget(add_block_btn)
        
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)
        
        # 区块列表
        self.blocks_scroll = QScrollArea()
        self.blocks_scroll.setWidgetResizable(True)
        self.blocks_scroll.setStyleSheet("border: none;")
        
        self.blocks_container = QWidget()
        self.blocks_grid = QGridLayout(self.blocks_container)
        self.blocks_grid.setSpacing(12)
        self.blocks_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.blocks_scroll.setWidget(self.blocks_container)
        layout.addWidget(self.blocks_scroll)

    def _setup_knowledge_tab(self):
        layout = QVBoxLayout(self.knowledge_tab)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔍 搜索知识...")
        toolbar.addWidget(search_input, 1)
        
        create_btn = QPushButton("➕ 创建知识")
        create_btn.clicked.connect(self._on_create_knowledge)
        toolbar.addWidget(create_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # 知识列表
        self.knowledge_scroll = QScrollArea()
        self.knowledge_scroll.setWidgetResizable(True)
        self.knowledge_scroll.setStyleSheet("border: none;")
        
        self.knowledge_container = QWidget()
        self.knowledge_grid = QGridLayout(self.knowledge_container)
        self.knowledge_grid.setSpacing(12)
        self.knowledge_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.knowledge_scroll.setWidget(self.knowledge_container)
        layout.addWidget(self.knowledge_scroll)

    def _setup_consensus_tab(self):
        layout = QVBoxLayout(self.consensus_tab)
        
        info_label = QLabel("⚙️ 共识治理 - 参与知识验证，获得奖励")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        info_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(info_label)
        
        # 共识选项
        options_group = QGroupBox("🎯 参与共识")
        options_layout = QVBoxLayout()
        
        validate_btn = QPushButton("🔍 验证待定知识")
        validate_btn.clicked.connect(self._on_validate)
        options_layout.addWidget(validate_btn)
        
        propose_btn = QPushButton("📝 提出新知识")
        propose_btn.clicked.connect(self._on_propose)
        options_layout.addWidget(propose_btn)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 投票历史
        votes_group = QGroupBox("📊 投票历史")
        votes_layout = QVBoxLayout()
        
        self.votes_list = QListWidget()
        self.votes_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fff;
            }
        """)
        votes_layout.addWidget(self.votes_list)
        
        votes_group.setLayout(votes_layout)
        layout.addWidget(votes_group)

    def _setup_dialogue_tab(self):
        layout = QVBoxLayout(self.dialogue_tab)
        
        # 对话输入
        input_layout = QHBoxLayout()
        
        self.dialogue_input = QLineEdit()
        self.dialogue_input.setPlaceholderText("输入问题...")
        self.dialogue_input.returnPressed.connect(self._on_dialogue_submit)
        input_layout.addWidget(self.dialogue_input, 1)
        
        submit_btn = QPushButton("💬 提问")
        submit_btn.clicked.connect(self._on_dialogue_submit)
        input_layout.addWidget(submit_btn)
        
        layout.addLayout(input_layout)
        
        # 对话历史
        self.dialogue_history = QListWidget()
        self.dialogue_history.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #fff;
            }
        """)
        layout.addWidget(self.dialogue_history)

    def _refresh_chain(self):
        """刷新区块链"""
        # 清空现有卡片
        while self.blocks_grid.count():
            item = self.blocks_grid.takeAt(0)
            if item.widget():
                item.widget().deleteRight()
        
        # 获取链上区块
        chain = self.blockchain.get_chain()
        
        # 添加区块卡片
        for i, block in enumerate(chain):
            card = BlockCard(block)
            row = i // 2
            col = i % 2
            self.blocks_grid.addWidget(card, row, col)
        
        # 更新统计
        self.blocks_count_label.setText(f"区块数: {len(chain)}")
        self.units_count_label.setText(f"知识单元: {len(self.blockchain.pending_knowledge)}")
        self.pending_label.setText(f"待验证: {len(self.blockchain.pending_knowledge)}")
        
        self.status_label.setText(f"已加载 {len(chain)} 个区块")

    def _refresh_knowledge(self):
        """刷新知识单元"""
        while self.knowledge_grid.count():
            item = self.knowledge_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        units = self.knowledge_graph.get_all_units()
        
        for i, unit in enumerate(units[:20]):
            card = KnowledgeUnitCard(unit)
            row = i // 2
            col = i % 2
            self.knowledge_grid.addWidget(card, row, col)

    def _on_add_block(self):
        """添加区块"""
        # 模拟添加区块
        self.status_label.setText("正在添加区块...")
        QTimer.singleShot(500, lambda: self._refresh_chain())

    def _on_create_knowledge(self):
        """创建知识"""
        from PyQt6.QtWidgets import QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle("创建知识单元")
        dialog.setMinimumWidth(500)
        
        layout = QFormLayout(dialog)
        
        title_input = QLineEdit()
        title_input.setPlaceholderText("知识标题")
        layout.addRow("标题:", title_input)
        
        content_input = QTextEdit()
        content_input.setPlaceholderText("知识内容...")
        content_input.setMinimumHeight(100)
        layout.addRow("内容:", content_input)
        
        type_combo = QComboBox()
        type_combo.addItems(["concept", "fact", "procedure", "explanation", "discussion"])
        layout.addRow("类型:", type_combo)
        
        tags_input = QLineEdit()
        tags_input.setPlaceholderText("标签 (逗号分隔)")
        layout.addRow("标签:", tags_input)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("创建")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_label.setText("正在创建知识单元...")
            QTimer.singleShot(500, lambda: self._refresh_knowledge())

    def _on_validate(self):
        """验证知识"""
        self.status_label.setText("正在验证...")

    def _on_propose(self):
        """提出知识"""
        self._on_create_knowledge()

    def _on_dialogue_submit(self):
        """提交对话"""
        query = self.dialogue_input.text().strip()
        if not query:
            return
        
        # 添加用户问题
        user_item = QListWidgetItem(f"👤 你: {query}")
        user_item.setFont(QFont("Microsoft YaHei", 10))
        self.dialogue_history.addItem(user_item)
        
        # 模拟 AI 回复
        self.dialogue_input.clear()
        
        def generate_response():
            try:
                response = self.dialogue.query(query, context={})
                
                # 添加 AI 回复
                ai_item = QListWidgetItem(f"🤖 AI: {response}")
                ai_item.setFont(QFont("Microsoft YaHei", 10))
                self.dialogue_history.addItem(ai_item)
            except Exception as e:
                error_item = QListWidgetItem(f"❌ 错误: {e}")
                self.dialogue_history.addItem(error_item)
        
        QTimer.singleShot(100, generate_response)


# ==================== 导出 ====================

__all__ = ['KnowledgeBlockchainPanel', 'BlockCard', 'KnowledgeUnitCard', 'ReputationGauge']
