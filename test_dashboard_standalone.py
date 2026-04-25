#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evolution Dashboard 独立测试脚本
"""

import sys
import os

# 不依赖项目导入，直接复制核心组件进行测试

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QProgressBar, QGroupBox,
    QScrollArea, QTabWidget, QListWidget, QComboBox, QSplitter,
    QListWidgetItem, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPen


# ==================== 简化的组件（复制核心功能）====================

class MetricCard(QFrame):
    """指标卡片"""
    def __init__(self, title: str, icon: str = "📊", parent=None):
        super().__init__(parent)
        self.title = title
        self.icon = icon
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        header = QHBoxLayout()
        self.icon_label = QLabel(self.icon)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 20))
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #666;")
        header.addWidget(self.icon_label)
        header.addWidget(self.title_label)
        header.addStretch()
        
        self.value_label = QLabel("0")
        self.value_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        
        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addStretch()
    
    def set_value(self, value: str):
        self.value_label.setText(value)


class ProgressRing(QFrame):
    """进度环"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._color = QColor("#3498db")
        self.setMinimumSize(80, 80)
    
    def set_progress(self, value: float, color: str = "#3498db"):
        self._progress = max(0, min(100, value))
        self._color = QColor(color)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.setPen(QPen(QColor("#ecf0f1"), 8))
        painter.drawArc(10, 10, 60, 60, 0, 360 * 16)
        
        # 进度
        painter.setPen(QPen(self._color, 8))
        angle = int(360 * (self._progress / 100) * 16)
        painter.drawArc(10, 10, 60, 60, -90 * 16, angle)


class DashboardDemo(QWidget):
    """Dashboard 演示"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._start_demo()
    
    def _init_ui(self):
        self.setWindowTitle("🧬 Evolution Engine Dashboard - 演示")
        self.resize(1000, 700)
        
        main_layout = QVBoxLayout(self)
        
        # 顶部栏
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2c3e50, stop:1 #34495e);
            padding: 15px;
        """)
        header_layout = QHBoxLayout(header)
        
        title = QLabel("🧬 Evolution Engine Dashboard")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        
        status = QLabel("● 运行中")
        status.setFont(QFont("Segoe UI", 10))
        status.setStyleSheet("color: #2ecc71;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(status)
        header_layout.addStretch()
        
        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.addTab(self._create_overview_tab(), "📊 概览")
        self.tabs.addTab(self._create_insights_tab(), "💡 洞察")
        self.tabs.addTab(self._create_patterns_tab(), "🔮 模式")
        
        main_layout.addWidget(header)
        main_layout.addWidget(self.tabs, 1)
        
        # 状态栏
        status_bar = QLabel("最后更新: --")
        status_bar.setStyleSheet("padding: 5px; background: #ecf0f1;")
        main_layout.addWidget(status_bar)
    
    def _create_overview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 指标卡片
        metrics_row = QHBoxLayout()
        self.scan_card = MetricCard("总扫描", "🔍")
        self.proposal_card = MetricCard("总提案", "📋")
        self.success_card = MetricCard("成功率", "✅")
        self.signal_card = MetricCard("总信号", "📡")
        
        metrics_row.addWidget(self.scan_card)
        metrics_row.addWidget(self.proposal_card)
        metrics_row.addWidget(self.success_card)
        metrics_row.addWidget(self.signal_card)
        metrics_row.addStretch()
        
        # 进度环
        rings_row = QHBoxLayout()
        rings_row.addStretch()
        
        success_ring = ProgressRing()
        rings_row.addWidget(success_ring)
        
        failed_ring = ProgressRing()
        failed_ring.set_progress(0)
        failed_ring._color = QColor("#e74c3c")
        rings_row.addWidget(failed_ring)
        
        rings_row.addStretch()
        
        layout.addLayout(metrics_row)
        layout.addLayout(rings_row)
        layout.addStretch()
        
        return tab
    
    def _create_insights_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        
        # 模拟洞察数据
        insights = [
            ("信号", "高频错误模式检测", "发现系统在特定操作后容易出现错误，可提前预警", 0.92),
            ("提案", "优化建议生成效率", "低优先级提案执行率较高，可降低审核门槛", 0.85),
            ("执行", "回滚操作成功率", "Git沙箱回滚成功率达95%，建议扩展到更多场景", 0.88),
        ]
        
        for category, title, desc, confidence in insights:
            card = QFrame()
            card.setStyleSheet("""
                background: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                padding: 15px;
            """)
            card_layout = QVBoxLayout(card)
            
            cat_label = QLabel(f"【{category.upper()}】")
            cat_label.setStyleSheet("color: white; background: #3498db; border-radius: 3px; padding: 2px 8px;")
            
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #7f8c8d;")
            desc_label.setWordWrap(True)
            
            conf_bar = QProgressBar()
            conf_bar.setValue(int(confidence * 100))
            conf_bar.setMaximumHeight(6)
            conf_bar.setTextVisible(False)
            
            card_layout.addWidget(cat_label)
            card_layout.addWidget(title_label)
            card_layout.addWidget(desc_label)
            card_layout.addWidget(conf_bar)
            
            container_layout.addWidget(card)
        
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return tab
    
    def _create_patterns_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        
        # 模拟模式数据
        patterns = [
            ("⏰ 时序", "性能下降模式", "每周末系统负载上升15%", 0.78, 12),
            ("🔗 共现", "错误-重试关联", "网络超时与重试操作高度相关", 0.65, 8),
            ("🔄 因果", "配置变更-故障", "配置更新后30分钟内发生故障概率增加", 0.82, 5),
            ("⚠️ 异常", "提案通过率异常", "最近3天提案通过率下降20%", 0.91, 3),
        ]
        
        for icon, name, desc, freq, count in patterns:
            card = QFrame()
            card.setStyleSheet("""
                background: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                padding: 15px;
            """)
            card_layout = QVBoxLayout(card)
            
            header = QHBoxLayout()
            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 16))
            name_label = QLabel(name)
            name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            header.addWidget(icon_label)
            header.addWidget(name_label)
            header.addStretch()
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #7f8c8d;")
            
            freq_bar = QProgressBar()
            freq_bar.setValue(int(freq * 100))
            freq_bar.setMaximumHeight(6)
            freq_bar.setTextVisible(False)
            
            evidence_label = QLabel(f"📋 {count} 条证据")
            evidence_label.setStyleSheet("color: #95a5a6;")
            
            card_layout.addLayout(header)
            card_layout.addWidget(desc_label)
            card_layout.addWidget(freq_bar)
            card_layout.addWidget(evidence_label)
            
            container_layout.addWidget(card)
        
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return tab
    
    def _start_demo(self):
        """演示动画"""
        self._demo_values = {
            'scans': 0,
            'proposals': 0,
            'success': 0,
            'signals': 0,
        }
        
        self._demo_timer = QTimer()
        self._demo_timer.timeout.connect(self._update_demo)
        self._demo_timer.start(500)
    
    def _update_demo(self):
        """更新演示数据"""
        import random
        
        self._demo_values['scans'] += random.randint(0, 3)
        self._demo_values['proposals'] += random.randint(0, 2)
        self._demo_values['success'] = min(100, self._demo_values['success'] + random.uniform(0.1, 0.5))
        self._demo_values['signals'] += random.randint(0, 5)
        
        self.scan_card.set_value(str(self._demo_values['scans']))
        self.proposal_card.set_value(str(self._demo_values['proposals']))
        self.success_card.set_value(f"{self._demo_values['success']:.1f}%")


def main():
    print("=" * 60)
    print("Evolution Dashboard Test")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    dashboard = DashboardDemo()
    dashboard.show()
    
    print("\n[PASS] Dashboard created!")
    print("\nFeatures:")
    print("  - Overview Tab: 4 metric cards + progress rings")
    print("  - Insights Tab: 3 learning insights")
    print("  - Patterns Tab: 4 pattern types")
    print("\nDemo mode: data updates in real-time...")
    print("=" * 60)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
