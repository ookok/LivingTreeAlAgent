"""
认知框架协作者 PyQt6 UI面板

提供可视化界面让用户使用认知框架协作者功能
"""

import sys
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QFrame, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QToolButton, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette


class CognitiveFrameworkPanel(QWidget):
    """
    认知框架协作者面板
    
    提供问题输入、框架生成、地图可视化等功能
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.framework = None
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        tab_widget.addTab(self._create_input_tab(), "问题输入")
        tab_widget.addTab(self._create_map_tab(), "认知地图")
        tab_widget.addTab(self._create_time_tab(), "时间轴")
        tab_widget.addTab(self._create_compare_tab(), "比较轴")
        tab_widget.addTab(self._create_stats_tab(), "统计分析")
        
        main_layout.addWidget(tab_widget)
        
        # 状态栏
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def _create_input_tab(self) -> QWidget:
        """创建问题输入标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("🧠 认知框架协作者")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 说明
        intro = QLabel(
            "输入您的问题，系统将为您构建「历时+共时」的认知框架，\n"
            "帮助您更高效、更本质地理解问题。"
        )
        intro.setStyleSheet("color: gray;")
        layout.addWidget(intro)
        
        # 问题输入区
        input_group = QGroupBox("问题输入")
        input_layout = QVBoxLayout()
        
        # 问题类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("问题类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "自动检测",
            "概念理解", "流程操作", "比较分析", "因果关系",
            "评价判断", "历史演变", "技术细节", "实践应用"
        ])
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        input_layout.addLayout(type_layout)
        
        # 问题输入框
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText(
            "请输入您的问题...\n\n"
            "示例:\n"
            "• 什么是深度学习？\n"
            "• Python和Java有什么区别？\n"
            "• 人工智能的历史演变是怎样的？\n"
            "• 比特币和以太坊哪个更有投资价值？"
        )
        self.question_input.setMinimumHeight(150)
        input_layout.addWidget(self.question_input)
        
        # 比较对象输入
        compare_layout = QHBoxLayout()
        compare_layout.addWidget(QLabel("比较对象 (可选):"))
        self.compare_a = QLineEdit()
        self.compare_a.setPlaceholderText("对象A")
        compare_layout.addWidget(self.compare_a)
        compare_layout.addWidget(QLabel("vs"))
        self.compare_b = QLineEdit()
        self.compare_b.setPlaceholderText("对象B")
        compare_layout.addWidget(self.compare_b)
        compare_layout.addStretch()
        input_layout.addLayout(compare_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("🚀 生成认知框架")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(self.generate_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 输出区域
        output_group = QGroupBox("认知框架输出")
        output_layout = QVBoxLayout()
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        output_layout.addWidget(self.output_text)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group, 1)  # stretch=1
        
        return widget
    
    def _create_map_tab(self) -> QWidget:
        """创建认知地图标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("🗺️ 认知地图")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 地图显示
        self.map_text = QTextEdit()
        self.map_text.setReadOnly(True)
        layout.addWidget(self.map_text, 1)
        
        return widget
    
    def _create_time_tab(self) -> QWidget:
        """创建时间轴标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("📅 时间轴 (纵向演变)")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 时间轴显示
        self.time_text = QTextEdit()
        self.time_text.setReadOnly(True)
        layout.addWidget(self.time_text, 1)
        
        return widget
    
    def _create_compare_tab(self) -> QWidget:
        """创建比较轴标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("⚖️ 比较轴 (横向差异)")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 比较轴显示
        self.compare_text = QTextEdit()
        self.compare_text.setReadOnly(True)
        layout.addWidget(self.compare_text, 1)
        
        return widget
    
    def _create_stats_tab(self) -> QWidget:
        """创建统计分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题
        title = QLabel("📊 统计分析")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 统计表格
        self.stats_table = QTableWidget(5, 2)
        self.stats_table.setHorizontalHeaderLabels(["统计项", "数值"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.verticalHeader().setVisible(False)
        
        # 填充数据
        stats_data = [
            ("总节点数", "0"),
            ("已验证节点", "0"),
            ("存疑节点", "0"),
            ("整体置信度", "0%"),
            ("风险区域数", "0")
        ]
        for i, (name, value) in enumerate(stats_data):
            self.stats_table.setItem(i, 0, QTableWidgetItem(name))
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))
        
        layout.addWidget(self.stats_table)
        
        # 置信度条
        conf_group = QGroupBox("置信度评估")
        conf_layout = QVBoxLayout()
        
        self.conf_label = QLabel("整体置信度: 0%")
        conf_layout.addWidget(self.conf_label)
        
        self.conf_bar = QLabel()
        self.conf_bar.setStyleSheet("""
            QLabel {
                background-color: #e0e0e0;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        conf_layout.addWidget(self.conf_bar)
        
        conf_group.setLayout(conf_layout)
        layout.addWidget(conf_group)
        
        layout.addStretch()
        
        return widget
    
    @pyqtSlot()
    def _on_generate(self):
        """生成认知框架"""
        question = self.question_input.toPlainText().strip()
        
        if not question:
            self.status_bar.showMessage("请输入问题", 3000)
            return
        
        # 获取比较对象
        compare_a = self.compare_a.text().strip()
        compare_b = self.compare_b.text().strip()
        comparison = (compare_a, compare_b) if compare_a and compare_b else None
        
        # 显示加载状态
        self.status_bar.showMessage("正在生成认知框架...")
        self.generate_btn.setEnabled(False)
        
        try:
            # 调用认知框架协作者
            from client.src.business.cognitive_framework import get_cognitive_collaborator
            collaborator = get_cognitive_collaborator()
            
            self.framework, output = collaborator.collaborate(
                question, comparison, return_framework=True
            )
            
            # 更新输出
            self.output_text.setPlainText(output)
            
            # 更新认知地图
            self._update_map_tab()
            
            # 更新时间轴
            self._update_time_tab()
            
            # 更新比较轴
            self._update_compare_tab()
            
            # 更新统计
            self._update_stats_tab()
            
            self.status_bar.showMessage("认知框架生成完成", 3000)
            
        except Exception as e:
            self.status_bar.showMessage(f"生成失败: {str(e)}", 5000)
            self.output_text.setPlainText(f"错误: {str(e)}")
        
        finally:
            self.generate_btn.setEnabled(True)
    
    def _update_map_tab(self):
        """更新认知地图标签页"""
        if not self.framework:
            return
        
        output = "## 🗺️ 认知地图\n\n"
        
        # 节点列表
        output += "### 节点列表\n\n"
        
        for node_id, node in self.framework.cognitive_map.items():
            # 状态emoji
            status_emoji = {
                "verified": "🟢",
                "likely": "🟡",
                "possible": "🟡",
                "controversial": "🔴",
                "unknown": "⚪"
            }.get(node.status.value, "⚪")
            
            # 类型emoji
            type_emoji = {
                "core": "🔵",
                "key": "🟠",
                "expand": "⚪",
                "risk": "🔴",
                "unknown": "⚫"
            }.get(node.node_type, "⚪")
            
            output += f"{type_emoji} {status_emoji} **{node.title}**\n"
            output += f"   - 类型: {node.node_type} | 优先级: {node.priority}\n"
            output += f"   - 置信度: {node.confidence.value}\n"
            if node.tags:
                output += f"   - 标签: {', '.join(node.tags)}\n"
            output += "\n"
        
        self.map_text.setPlainText(output)
    
    def _update_time_tab(self):
        """更新时间轴标签页"""
        if not self.framework or not self.framework.time_axis:
            self.time_text.setPlainText("暂无时间轴数据\n\n提示: 带有「历史」「演变」「发展」等关键词的问题会自动生成时间轴")
            return
        
        output = "## 📅 时间轴 (纵向演变)\n\n"
        
        for i, node in enumerate(self.framework.time_axis):
            # 置信度emoji
            conf_emoji = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🔴",
                "uncertain": "⚪"
            }.get(node.confidence.value, "⚪")
            
            # 时间范围
            time_range = ""
            if node.start_year:
                time_range = f"({node.start_year}"
                if node.end_year:
                    time_range += f" - {node.end_year}"
                else:
                    time_range += " - 现在"
                time_range += ")"
            
            output += f"### {conf_emoji} {i+1}. {node.period} {time_range}\n\n"
            output += f"**关键事件**: {', '.join(node.key_events)}\n\n"
            output += f"**阶段特征**: {', '.join(node.characteristics)}\n\n"
            output += f"**重要性**: {node.significance}\n"
            
            if node.notes:
                output += f"\n> ⚠️ {node.notes}\n"
            
            output += "\n---\n\n"
        
        self.time_text.setPlainText(output)
    
    def _update_compare_tab(self):
        """更新比较轴标签页"""
        if not self.framework or not self.framework.comparison_axis:
            self.compare_text.setPlainText("暂无比较轴数据\n\n提示: 带有「比较」「区别」「差异」等关键词的问题，或指定了比较对象时会生成比较轴")
            return
        
        output = "## ⚖️ 比较轴 (横向差异)\n\n"
        
        for i, node in enumerate(self.framework.comparison_axis):
            conf_emoji = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🔴",
                "uncertain": "⚪"
            }.get(node.confidence.value, "⚪")
            
            output += f"### {conf_emoji} {i+1}. {node.dimension}\n\n"
            output += f"**{node.subject_a} vs {node.subject_b}**\n\n"
            
            # 表格
            output += "| 维度 | {} | {} |\n".format(node.subject_a, node.subject_b)
            output += "|------|------|------|\n"
            
            for key, val in node.a_features.items():
                output += f"| {key} | {val} | {node.b_features.get(key, '-')} |\n"
            
            output += f"\n**核心差异**: {node.key_difference}\n\n"
            output += f"**共同点**: {node.similarity}\n\n"
            output += f"> 💡 {node.source_hint}\n\n"
            output += "---\n\n"
        
        self.compare_text.setPlainText(output)
    
    def _update_stats_tab(self):
        """更新统计标签页"""
        if not self.framework:
            return
        
        # 更新表格
        stats_data = [
            ("总节点数", str(self.framework.total_nodes)),
            ("已验证节点", str(self.framework.verified_nodes)),
            ("存疑节点", str(self.framework.uncertain_nodes)),
            ("整体置信度", f"{self.framework.confidence_overall:.0%}"),
            ("风险区域数", str(len(self.framework.risk_areas)))
        ]
        
        for i, (name, value) in enumerate(stats_data):
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))
        
        # 更新置信度标签
        conf_percent = int(self.framework.confidence_overall * 100)
        self.conf_label.setText(f"整体置信度: {conf_percent}%")
        
        # 更新置信度条颜色
        if conf_percent >= 70:
            color = "#4CAF50"  # 绿色
        elif conf_percent >= 50:
            color = "#FFC107"  # 黄色
        else:
            color = "#F44336"  # 红色
        
        self.conf_bar.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 5px;
                padding: 5px;
                max-width: {conf_percent * 3}px;
            }}
        """)
    
    @pyqtSlot()
    def _on_clear(self):
        """清空输入"""
        self.question_input.clear()
        self.compare_a.clear()
        self.compare_b.clear()
        self.output_text.clear()
        self.map_text.clear()
        self.time_text.clear()
        self.compare_text.clear()
        self.framework = None
        self.status_bar.showMessage("已清空")
        
        # 重置统计
        self._update_stats_tab()
