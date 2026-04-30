# -*- coding: utf-8 -*-
"""
Evolution Engine Dashboard - PyQt6 进化引擎仪表盘
=================================================

功能：
- 进化摘要概览
- 学习洞察展示
- 模式挖掘可视化
- 决策追踪/根因分析

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
    QInputDialog, QDialog, QPlainTextEdit, QProgressDialog,
    QApplication, QSizePolicy, QSpacerItem, QScrollBar,
    QDateTimeEdit, QSlider, QDial, QLCDNumber, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer, QRegularExpression, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRect
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen, QSyntaxHighlighter, QTextCharFormat, QRegularExpressionValidator, QBrush, QLinearGradient

import asyncio
import json
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

# Evolution Engine 核心模块
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .business.evolution_engine import EvolutionEngine, create_evolution_engine
    from .business.evolution_engine.memory import (
        EvolutionLog, LearningEngine, PatternMiner, DecisionTracker,
        DecisionType, DecisionOutcome
    )
    EVOLUTION_ENGINE_AVAILABLE = True
except ImportError as e:
    EVOLUTION_ENGINE_AVAILABLE = False
    print(f"Evolution Engine 模块不可用: {e}")


# ==================== 数据模型 ====================

@dataclass
class EvolutionMetrics:
    """进化指标"""
    total_scans: int = 0
    total_proposals: int = 0
    proposals_approved: int = 0
    proposals_executed: int = 0
    proposals_failed: int = 0
    total_signals: int = 0
    avg_signal_strength: float = 0.0
    success_rate: float = 0.0


@dataclass
class InsightItem:
    """洞察项"""
    category: str  # 'signal', 'proposal', 'execution'
    title: str
    description: str
    confidence: float  # 0.0 - 1.0
    impact: str  # 'high', 'medium', 'low'


@dataclass
class PatternItem:
    """模式项"""
    pattern_type: str  # 'temporal', 'co_occurrence', 'causal', 'anomaly'
    name: str
    description: str
    frequency: float  # 出现频率
    evidence_count: int  # 证据数量


@dataclass
class DecisionAuditItem:
    """决策审计项"""
    chain_id: str
    proposal_id: str
    decision_type: str
    decision_time: str
    outcome: str  # 'success', 'failure', 'pending'
    reasoning: str


# ==================== 面板组件 ====================

class MetricCard(QFrame):
    """指标卡片组件"""
    
    def __init__(self, title: str, icon: str = "📊", parent=None):
        super().__init__(parent)
        self.title = title
        self.icon = icon
        self._value = "0"
        self._subtitle = ""
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        # 图标 + 标题
        header = QHBoxLayout()
        self.icon_label = QLabel(self.icon)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 20))
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #666;")
        header.addWidget(self.icon_label)
        header.addWidget(self.title_label)
        header.addStretch()
        
        # 数值
        self.value_label = QLabel(self._value)
        self.value_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #2c3e50;")
        
        # 副标题
        self.subtitle_label = QLabel(self._subtitle)
        self.subtitle_label.setFont(QFont("Segoe UI", 9))
        self.subtitle_label.setStyleSheet("color: #999;")
        
        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch()
    
    def _setup_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            MetricCard {
                background: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            MetricCard:hover {
                border: 1px solid #3498db;
            }
        """)
    
    def set_value(self, value: str, subtitle: str = ""):
        self._value = value
        self._subtitle = subtitle
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)


class ProgressRing(QFrame):
    """进度环组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._color = QColor("#3498db")
        self._bg_color = QColor("#ecf0f1")
        self.setMinimumSize(80, 80)
        self.setMaximumSize(80, 80)
    
    def set_progress(self, value: float, color: str = "#3498db"):
        self._progress = max(0, min(100, value))
        self._color = QColor(color)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景环
        painter.setPen(QPen(self._bg_color, 8))
        painter.drawArc(10, 10, 60, 60, 0, 360 * 16)
        
        # 进度环
        painter.setPen(QPen(self._color, 8))
        angle = int(360 * (self._progress / 100) * 16)
        painter.drawArc(10, 10, 60, 60, -90 * 16, angle)
        
        # 中心文字
        painter.setPen(QPen(QColor("#2c3e50"), 1))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self._progress:.0f}%")


class InsightCard(QFrame):
    """洞察卡片组件"""
    
    def __init__(self, insight: InsightItem, parent=None):
        super().__init__(parent)
        self.insight = insight
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        
        # 类别标签
        category_colors = {
            'signal': '#e74c3c',
            'proposal': '#3498db',
            'execution': '#2ecc71'
        }
        color = category_colors.get(self.insight.category, '#95a5a6')
        
        self.category_label = QLabel(f"【{self.insight.category.upper()}】")
        self.category_label.setStyleSheet(f"""
            color: white;
            background: {color};
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 10px;
        """)
        
        # 标题
        self.title_label = QLabel(self.insight.title)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2c3e50;")
        
        # 描述
        self.desc_label = QLabel(self.insight.description)
        self.desc_label.setFont(QFont("Segoe UI", 9))
        self.desc_label.setStyleSheet("color: #7f8c8d;")
        self.desc_label.setWordWrap(True)
        
        # 置信度条
        conf_layout = QHBoxLayout()
        conf_label = QLabel("置信度:")
        conf_label.setFont(QFont("Segoe UI", 9))
        self.conf_bar = QProgressBar()
        self.conf_bar.setValue(int(self.insight.confidence * 100))
        self.conf_bar.setMaximumHeight(6)
        self.conf_bar.setTextVisible(False)
        conf_layout.addWidget(conf_label)
        conf_layout.addWidget(self.conf_bar, 1)
        
        layout.addWidget(self.category_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addLayout(conf_layout)
    
    def _setup_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            InsightCard {
                background: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            InsightCard:hover {
                border: 1px solid #3498db;
            }
        """)


class PatternCard(QFrame):
    """模式卡片组件"""
    
    def __init__(self, pattern: PatternItem, parent=None):
        super().__init__(parent)
        self.pattern = pattern
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # 类型图标
        type_icons = {
            'temporal': '⏰',
            'co_occurrence': '🔗',
            'causal': '🔄',
            'anomaly': '⚠️'
        }
        icon = type_icons.get(self.pattern.pattern_type, '📊')
        
        # 标题行
        header = QHBoxLayout()
        self.icon_label = QLabel(icon)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 16))
        self.title_label = QLabel(self.pattern.name)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.addWidget(self.icon_label)
        header.addWidget(self.title_label)
        header.addStretch()
        
        # 描述
        self.desc_label = QLabel(self.pattern.description)
        self.desc_label.setFont(QFont("Segoe UI", 9))
        self.desc_label.setStyleSheet("color: #7f8c8d;")
        self.desc_label.setWordWrap(True)
        
        # 频率指示器
        freq_layout = QHBoxLayout()
        freq_label = QLabel("频率:")
        freq_label.setFont(QFont("Segoe UI", 9))
        self.freq_bar = QProgressBar()
        self.freq_bar.setValue(int(self.pattern.frequency * 100))
        self.freq_bar.setMaximumHeight(6)
        self.freq_bar.setTextVisible(False)
        freq_layout.addWidget(freq_label)
        freq_layout.addWidget(self.freq_bar, 1)
        
        # 证据计数
        evidence_label = QLabel(f"📋 {self.pattern.evidence_count} 条证据")
        evidence_label.setFont(QFont("Segoe UI", 9))
        evidence_label.setStyleSheet("color: #95a5a6;")
        
        layout.addLayout(header)
        layout.addWidget(self.desc_label)
        layout.addLayout(freq_layout)
        layout.addWidget(evidence_label)
    
    def _setup_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            PatternCard {
                background: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            PatternCard:hover {
                border: 1px solid #9b59b6;
            }
        """)


class TimelineWidget(QFrame):
    """时间线组件 - 用于展示决策历史"""
    
    def __init__(self, decisions: List[DecisionAuditItem], parent=None):
        super().__init__(parent)
        self.decisions = decisions
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 时间线容器
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setSpacing(20)
        
        for i, decision in enumerate(self.decisions):
            item = self._create_timeline_item(decision, i)
            timeline_layout.addWidget(item)
        
        timeline_layout.addStretch()
        scroll.setWidget(timeline_container)
        layout.addWidget(scroll)
    
    def _create_timeline_item(self, decision: DecisionAuditItem, index: int) -> QFrame:
        item = QFrame()
        item_layout = QHBoxLayout(item)
        item_layout.setSpacing(10)
        
        # 时间线节点
        node_color = {
            'success': '#2ecc71',
            'failure': '#e74c3c',
            'pending': '#f39c12'
        }.get(decision.outcome, '#95a5a6')
        
        node = QFrame()
        node.setFixedSize(12, 12)
        node.setStyleSheet(f"""
            background: {node_color};
            border-radius: 6px;
        """)
        
        # 连接线（除了最后一个）
        if index < len(self.decisions) - 1:
            line = QFrame()
            line.setFixedWidth(2)
            line.setStyleSheet(f"background: {node_color};")
            line.setMinimumHeight(40)
        
        # 内容
        content = QVBoxLayout()
        content.setSpacing(3)
        
        time_label = QLabel(decision.decision_time)
        time_label.setFont(QFont("Segoe UI", 8))
        time_label.setStyleSheet("color: #95a5a6;")
        
        type_label = QLabel(f"{decision.decision_type} - {decision.outcome}")
        type_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        type_label.setStyleSheet(f"color: {node_color};")
        
        reasoning_label = QLabel(decision.reasoning[:80] + "..." if len(decision.reasoning) > 80 else decision.reasoning)
        reasoning_label.setFont(QFont("Segoe UI", 9))
        reasoning_label.setStyleSheet("color: #7f8c8d;")
        reasoning_label.setWordWrap(True)
        
        content.addWidget(time_label)
        content.addWidget(type_label)
        content.addWidget(reasoning_label)
        
        item_layout.addWidget(node)
        item_layout.addLayout(content)
        item_layout.addStretch()
        
        return item


class RootCauseAnalysisWidget(QFrame):
    """根因分析组件"""
    
    def __init__(self, analysis: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("🔍 根因分析")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)
        
        # 根因列表
        if 'root_causes' in self.analysis:
            for cause in self.analysis['root_causes']:
                cause_card = self._create_cause_card(cause)
                layout.addWidget(cause_card)
        
        # 建议
        if 'recommendations' in self.analysis:
            rec_title = QLabel("💡 建议")
            rec_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            rec_title.setStyleSheet("color: #3498db;")
            layout.addWidget(rec_title)
            
            for rec in self.analysis['recommendations']:
                rec_label = QLabel(f"• {rec}")
                rec_label.setFont(QFont("Segoe UI", 10))
                rec_label.setStyleSheet("color: #7f8c8d;")
                rec_label.setWordWrap(True)
                layout.addWidget(rec_label)
        
        layout.addStretch()
    
    def _create_cause_card(self, cause: Dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 3px solid #e74c3c;
            padding: 8px;
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)
        
        title = QLabel(cause.get('title', 'Unknown'))
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #e74c3c;")
        
        desc = QLabel(cause.get('description', ''))
        desc.setFont(QFont("Segoe UI", 9))
        desc.setStyleSheet("color: #7f8c8d;")
        desc.setWordWrap(True)
        
        confidence = QLabel(f"置信度: {cause.get('confidence', 0) * 100:.0f}%")
        confidence.setFont(QFont("Segoe UI", 8))
        confidence.setStyleSheet("color: #95a5a6;")
        
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(confidence)
        
        return card


# ==================== 主面板 ====================

class EvolutionDashboard(QWidget):
    """
    Evolution Engine Dashboard - 进化引擎仪表盘
    
    主要功能：
    1. 进化摘要概览
    2. 学习洞察展示
    3. 模式挖掘可视化
    4. 决策追踪/根因分析
    """
    
    # 信号
    scan_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    
    def __init__(self, engine: Optional[EvolutionEngine] = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._init_ui()
        self._init_connections()
        
        # 初始化数据
        if self.engine:
            self._load_data()
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部栏
        header = self._create_header()
        main_layout.addWidget(header)
        
        # 主内容区
        self.content = QTabWidget()
        self.content.setTabPosition(QTabWidget.TabPosition.North)
        self.content.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                background: #f5f6f7;
            }
            QTabBar::tab {
                padding: 8px 20px;
                background: white;
                border: 1px solid #e0e0e0;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)
        
        # 添加标签页
        self.content.addTab(self._create_overview_tab(), "📊 概览")
        self.content.addTab(self._create_insights_tab(), "💡 洞察")
        self.content.addTab(self._create_patterns_tab(), "🔮 模式")
        self.content.addTab(self._create_decisions_tab(), "📜 决策")
        self.content.addTab(self._create_analysis_tab(), "🔍 分析")
        
        main_layout.addWidget(self.content)
        
        # 状态栏
        status = self._create_status_bar()
        main_layout.addWidget(status)
    
    def _create_header(self) -> QFrame:
        """创建顶部栏"""
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2c3e50, stop:1 #34495e);
            padding: 15px;
        """)
        layout = QHBoxLayout(header)
        
        # 标题
        title = QLabel("🧬 Evolution Engine Dashboard")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        
        # 状态指示
        self.status_indicator = QLabel("● 运行中")
        self.status_indicator.setFont(QFont("Segoe UI", 10))
        self.status_indicator.setStyleSheet("color: #2ecc71;")
        
        # 按钮
        self.scan_btn = QPushButton("🔄 扫描")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2980b9; }
        """)
        
        self.refresh_btn = QPushButton("🔃 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #2ecc71;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #27ae60; }
        """)
        
        layout.addWidget(title)
        layout.addWidget(self.status_indicator)
        layout.addStretch()
        layout.addWidget(self.scan_btn)
        layout.addWidget(self.refresh_btn)
        
        return header
    
    def _create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 指标卡片行
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(15)
        
        # 创建指标卡片
        self.total_scans_card = MetricCard("总扫描", "🔍")
        self.total_proposals_card = MetricCard("总提案", "📋")
        self.success_rate_card = MetricCard("成功率", "✅")
        self.total_signals_card = MetricCard("总信号", "📡")
        
        metrics_row.addWidget(self.total_scans_card)
        metrics_row.addWidget(self.total_proposals_card)
        metrics_row.addWidget(self.success_rate_card)
        metrics_row.addWidget(self.total_signals_card)
        metrics_row.addStretch()
        
        layout.addLayout(metrics_row)
        
        # 执行状态区域
        exec_group = QGroupBox("执行状态")
        exec_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        exec_layout = QHBoxLayout(exec_group)
        
        # 成功/失败环
        success_ring = QVBoxLayout()
        self.success_ring = ProgressRing()
        success_label = QLabel("成功率")
        success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_ring.addWidget(self.success_ring)
        success_ring.addWidget(success_label)
        
        failed_ring = QVBoxLayout()
        self.failed_ring = ProgressRing()
        self.failed_ring.set_progress(0)
        self.failed_ring._color = QColor("#e74c3c")
        failed_label = QLabel("失败率")
        failed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        failed_ring.addWidget(self.failed_ring)
        failed_ring.addWidget(failed_label)
        
        exec_layout.addLayout(success_ring)
        exec_layout.addLayout(failed_ring)
        exec_layout.addStretch()
        
        # 最近活动
        activity_group = QGroupBox("最近活动")
        activity_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_list = QListWidget()
        self.activity_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        activity_layout.addWidget(self.activity_list)
        
        # 左右布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(exec_group)
        splitter.addWidget(activity_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        layout.addStretch()
        
        return tab
    
    def _create_insights_tab(self) -> QWidget:
        """创建洞察标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 过滤器
        filter_layout = QHBoxLayout()
        filter_label = QLabel("类别过滤:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "信号", "提案", "执行"])
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        
        # 洞察列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        self.insights_container = QWidget()
        self.insights_layout = QVBoxLayout(self.insights_container)
        self.insights_layout.setSpacing(10)
        self.insights_layout.addStretch()
        
        scroll.setWidget(self.insights_container)
        
        layout.addLayout(filter_layout)
        layout.addWidget(scroll)
        
        return tab
    
    def _create_patterns_tab(self) -> QWidget:
        """创建模式标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 模式类型切换
        type_layout = QHBoxLayout()
        type_label = QLabel("模式类型:")
        
        self.pattern_type_tabs = QTabWidget()
        self.pattern_type_tabs.setTabPosition(QTabWidget.TabPosition.West)
        
        # 创建各类型标签页
        self.temporal_patterns = self._create_pattern_container("temporal")
        self.co_occurrence_patterns = self._create_pattern_container("co_occurrence")
        self.causal_patterns = self._create_pattern_container("causal")
        self.anomaly_patterns = self._create_pattern_container("anomaly")
        
        self.pattern_type_tabs.addTab(self.temporal_patterns, "⏰ 时序")
        self.pattern_type_tabs.addTab(self.co_occurrence_patterns, "🔗 共现")
        self.pattern_type_tabs.addTab(self.causal_patterns, "🔄 因果")
        self.pattern_type_tabs.addTab(self.anomaly_patterns, "⚠️ 异常")
        
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.pattern_type_tabs, 1)
        
        layout.addLayout(type_layout)
        
        return tab
    
    def _create_pattern_container(self, pattern_type: str) -> QWidget:
        """创建模式容器"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        widget = QWidget()
        widget._pattern_type = pattern_type
        vlayout = QVBoxLayout(widget)
        vlayout.setSpacing(10)
        vlayout.addStretch()
        
        scroll.setWidget(widget)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_decisions_tab(self) -> QWidget:
        """创建决策标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 决策统计
        stats_layout = QHBoxLayout()
        self.approved_count = QLabel("已批准: 0")
        self.pending_count = QLabel("待处理: 0")
        self.rejected_count = QLabel("已拒绝: 0")
        
        for label in [self.approved_count, self.pending_count, self.rejected_count]:
            label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            stats_layout.addWidget(label)
        stats_layout.addStretch()
        
        # 时间线
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #e0e0e0; border-radius: 8px;")
        
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setSpacing(15)
        self.timeline_layout.addStretch()
        
        scroll.setWidget(self.timeline_container)
        
        layout.addLayout(stats_layout)
        layout.addWidget(scroll)
        
        return tab
    
    def _create_analysis_tab(self) -> QWidget:
        """创建分析标签页"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 根因分析区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        self.analysis_container = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_container)
        
        # 空状态提示
        empty_label = QLabel("🔍 选择一个提案进行分析...")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("""
            color: #95a5a6;
            font-size: 14px;
            padding: 50px;
        """)
        self.analysis_layout.addWidget(empty_label)
        self.analysis_layout.addStretch()
        
        scroll.setWidget(self.analysis_container)
        
        # 提案列表
        proposals_group = QGroupBox("提案列表")
        proposals_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                min-width: 200px;
            }
        """)
        proposals_layout = QVBoxLayout(proposals_group)
        
        self.proposals_list = QListWidget()
        self.proposals_list.itemClicked.connect(self._on_proposal_selected)
        proposals_layout.addWidget(self.proposals_list)
        
        layout.addWidget(proposals_group, 1)
        layout.addWidget(scroll, 2)
        
        return tab
    
    def _create_status_bar(self) -> QFrame:
        """创建状态栏"""
        status = QFrame()
        status.setStyleSheet("""
            background: #ecf0f1;
            border-top: 1px solid #bdc3c7;
            padding: 5px 15px;
        """)
        layout = QHBoxLayout(status)
        
        self.last_update_label = QLabel("最后更新: --")
        self.last_update_label.setFont(QFont("Segoe UI", 9))
        self.last_update_label.setStyleSheet("color: #7f8c8d;")
        
        self.engine_status_label = QLabel("引擎: 未连接")
        self.engine_status_label.setFont(QFont("Segoe UI", 9))
        self.engine_status_label.setStyleSheet("color: #95a5a6;")
        
        layout.addWidget(self.last_update_label)
        layout.addWidget(self.engine_status_label)
        layout.addStretch()
        
        return status
    
    def _init_connections(self):
        """初始化连接"""
        if hasattr(self, 'scan_btn'):
            self.scan_btn.clicked.connect(self._on_scan_clicked)
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.clicked.connect(self._on_refresh_clicked)
    
    # ==================== 数据加载 ====================
    
    def _load_data(self):
        """加载数据"""
        if not self.engine:
            return
        
        try:
            # 获取进化摘要
            summary = self.engine.get_evolution_summary()
            self._update_metrics(summary)
            self._update_insights(summary)
            self._update_patterns(summary)
            self._update_decisions(summary)
            
            # 更新时间戳
            self.last_update_label.setText(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")
            self.engine_status_label.setText("引擎: ✅ 已连接")
            self.status_indicator.setText("● 运行中")
            self.status_indicator.setStyleSheet("color: #2ecc71;")
            
        except Exception as e:
            self.engine_status_label.setText(f"引擎: ❌ 错误 - {str(e)[:30]}")
            self.status_indicator.setText("● 错误")
            self.status_indicator.setStyleSheet("color: #e74c3c;")
    
    def _update_metrics(self, summary: Dict[str, Any]):
        """更新指标卡片"""
        log_summary = summary.get('log_summary', {})
        learning_stats = summary.get('learning_stats', {})
        
        # 总扫描
        total_scans = log_summary.get('total_scans', 0)
        self.total_scans_card.set_value(str(total_scans))
        
        # 总提案
        total_proposals = log_summary.get('total_proposals', 0)
        self.total_proposals_card.set_value(str(total_proposals))
        
        # 成功率
        success_rate = learning_stats.get('success_rate', 0.0)
        self.success_rate_card.set_value(f"{success_rate * 100:.1f}%")
        self.success_ring.set_progress(success_rate * 100)
        
        # 失败率
        failed_rate = 1.0 - success_rate
        self.failed_ring.set_progress(failed_rate * 100)
        
        # 总信号
        total_signals = log_summary.get('total_signals', 0)
        self.total_signals_card.set_value(str(total_signals))
    
    def _update_insights(self, summary: Dict[str, Any]):
        """更新洞察列表"""
        # 清空现有
        while self.insights_layout.count() > 1:
            item = self.insights_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加洞察卡片
        insights = self.engine.get_learning_insights()
        
        for insight_data in insights[:10]:  # 最多显示10条
            insight = InsightItem(
                category=insight_data.get('category', 'execution'),
                title=insight_data.get('title', '未知洞察'),
                description=insight_data.get('description', ''),
                confidence=insight_data.get('confidence', 0.5),
                impact=insight_data.get('impact', 'medium')
            )
            card = InsightCard(insight)
            self.insights_layout.insertWidget(self.insights_layout.count() - 1, card)
    
    def _update_patterns(self, summary: Dict[str, Any]):
        """更新模式列表"""
        patterns_summary = summary.get('patterns_summary', {})
        
        # 更新各类型模式
        self._update_pattern_container(
            self.temporal_patterns,
            patterns_summary.get('temporal_patterns', [])
        )
        self._update_pattern_container(
            self.co_occurrence_patterns,
            patterns_summary.get('co_occurrence_patterns', [])
        )
        self._update_pattern_container(
            self.causal_patterns,
            patterns_summary.get('causal_patterns', [])
        )
        self._update_pattern_container(
            self.anomaly_patterns,
            patterns_summary.get('anomaly_patterns', [])
        )
    
    def _update_pattern_container(self, container: QWidget, patterns: List[Dict]):
        """更新模式容器"""
        # 找到滚动区域内的widget
        scroll = container.findChild(QScrollArea)
        if not scroll:
            return
        
        widget = scroll.widget()
        if not widget:
            return
        
        # 清空除最后一个stretch外的所有子widget
        layout = widget.layout()
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加模式卡片
        for pattern_data in patterns[:5]:
            pattern = PatternItem(
                pattern_type=pattern_data.get('type', 'temporal'),
                name=pattern_data.get('name', '未知模式'),
                description=pattern_data.get('description', ''),
                frequency=pattern_data.get('frequency', 0.0),
                evidence_count=pattern_data.get('evidence_count', 0)
            )
            card = PatternCard(pattern)
            layout.insertWidget(layout.count() - 1, card)
        
        # 空状态
        if not patterns:
            empty = QLabel("暂无模式数据")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #95a5a6; padding: 30px;")
            layout.insertWidget(0, empty)
    
    def _update_decisions(self, summary: Dict[str, Any]):
        """更新决策时间线"""
        decision_stats = summary.get('decision_stats', {})
        
        # 更新统计
        self.approved_count.setText(f"已批准: {decision_stats.get('approved_count', 0)}")
        self.pending_count.setText(f"待处理: {decision_stats.get('pending_count', 0)}")
        self.rejected_count.setText(f"已拒绝: {decision_stats.get('rejected_count', 0)}")
        
        # 清空时间线
        while self.timeline_layout.count() > 1:
            item = self.timeline_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加空状态
        empty = QLabel("暂无决策记录")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("color: #95a5a6; padding: 30px;")
        self.timeline_layout.insertWidget(0, empty)
    
    # ==================== 事件处理 ====================
    
    def _on_scan_clicked(self):
        """扫描按钮点击"""
        self.scan_requested.emit()
        
        # 显示扫描中状态
        self.status_indicator.setText("● 扫描中...")
        self.status_indicator.setStyleSheet("color: #f39c12;")
        
        # 模拟扫描完成
        QTimer.singleShot(2000, self._on_scan_complete)
    
    def _on_scan_complete(self):
        """扫描完成"""
        self._load_data()
    
    def _on_refresh_clicked(self):
        """刷新按钮点击"""
        self.refresh_requested.emit()
        self._load_data()
    
    def _on_proposal_selected(self, item: QListWidgetItem):
        """提案选中"""
        proposal_id = item.text()
        
        # 获取分析结果
        analysis = self.engine.analyze_root_cause(proposal_id)
        
        # 清空分析容器
        while self.analysis_layout.count():
            item = self.analysis_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加分析结果
        analysis_widget = RootCauseAnalysisWidget(analysis)
        self.analysis_layout.addWidget(analysis_widget)
    
    # ==================== 公共方法 ====================
    
    def set_engine(self, engine: EvolutionEngine):
        """设置引擎"""
        self.engine = engine
        self._load_data()
    
    def refresh(self):
        """刷新数据"""
        self._load_data()


# ==================== 工厂函数 ====================

def create_evolution_dashboard(engine: Optional[EvolutionEngine] = None) -> EvolutionDashboard:
    """创建 Evolution Dashboard"""
    return EvolutionDashboard(engine)


# ==================== 测试 ====================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    dashboard = create_evolution_dashboard()
    dashboard.resize(1200, 800)
    dashboard.show()
    
    sys.exit(app.exec())
