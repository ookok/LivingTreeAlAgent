"""
智能审查面板 - PyQt6集成界面
=============================

提供五大审查能力的可视化界面：
1. 数字孪生验证面板
2. 知识图谱合规面板
3. 智能修复建议面板
4. 对抗性测试面板
5. 分布式审查面板
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QTabWidget, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QBadge,
    QCardWidget, QScrollArea, QFrame,
    QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QProgressDialog,
)
from typing import Dict, List, Optional, Any
import json

# 状态颜色
STATUS_COLORS = {
    "passed": "#27ae60",      # 绿色
    "failed": "#e74c3c",      # 红色
    "warning": "#f39c12",     # 橙色
    "pending": "#95a5a6",     # 灰色
    "running": "#3498db",     # 蓝色
    "verified": "#27ae60",   # 绿色
}

ISSUE_LEVEL_COLORS = {
    "fatal": "#e74c3c",       # 红色
    "error": "#e67e22",        # 橙色
    "warning": "#f1c40f",      # 黄色
    "suggestion": "#3498db",   # 蓝色
    "format": "#9b59b6",       # 紫色
}


class StatusIndicator(QLabel):
    """状态指示器"""

    def __init__(self, status: str = "pending", parent=None):
        super().__init__(parent)
        self.status = status
        self._update_style()

    def set_status(self, status: str):
        self.status = status
        self._update_style()

    def _update_style(self):
        color = STATUS_COLORS.get(self.status, "#95a5a6")
        icons = {
            "passed": "✅",
            "failed": "❌",
            "warning": "⚠️",
            "pending": "⏳",
            "running": "🔄",
            "verified": "✓",
        }
        self.setText(icons.get(self.status, "•"))
        self.setStyleSheet(f"color: {color}; font-size: 16px;")


class IssueLevelBadge(QLabel):
    """问题级别徽章"""

    def __init__(self, level: str, parent=None):
        super().__init__(parent)
        self.level = level
        self._update_style()

    def set_level(self, level: str):
        self.level = level
        self._update_style()

    def _update_style(self):
        colors = {
            "fatal": ("#ffffff", "#e74c3c"),
            "error": ("#ffffff", "#e67e22"),
            "warning": ("#000000", "#f1c40f"),
            "suggestion": ("#ffffff", "#3498db"),
            "format": ("#ffffff", "#9b59b6"),
        }
        bg_color = colors.get(self.level, ("#ffffff", "#95a5a6"))[1]
        self.setStyleSheet(
            f"background-color: {bg_color}; color: white; "
            f"padding: 2px 8px; border-radius: 10px; font-size: 11px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class AnimatedProgressBar(QProgressBar):
    """带动画的进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._phase = 0

    def start_animation(self):
        self._timer.start(50)

    def stop_animation(self):
        self._timer.stop()
        self._phase = 0

    def _animate(self):
        self._phase = (self._phase + 2) % 100
        self.setValue(self._phase)


class ScoreGauge(QWidget):
    """评分仪表盘"""

    def __init__(self, score: float = 0.0, label: str = "", parent=None):
        super().__init__(parent)
        self.score = score
        self.label = label
        self.setMinimumSize(80, 80)

    def set_score(self, score: float):
        self.score = score
        self.update()

    def set_label(self, label: str):
        self.label = label
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen, QBrush, QFont, QColor, QPainterPath
        from PyQt6.QtCore import Qt, QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height)

        # 计算颜色
        if self.score >= 90:
            color = QColor(39, 174, 96)  # 绿色
        elif self.score >= 75:
            color = QColor(52, 152, 219)  # 蓝色
        elif self.score >= 60:
            color = QColor(243, 156, 18)  # 橙色
        else:
            color = QColor(231, 76, 60)  # 红色

        # 绘制背景圆弧
        painter.setPen(QPen(QColor(240, 240, 240), 8))
        painter.drawArc(
            (width - size) / 2 + 4, (height - size) / 2 + 4,
            size - 8, size - 8,
            45 * 16, 270 * 16
        )

        # 绘制进度圆弧
        painter.setPen(QPen(color, 8))
        span_angle = int(270 * (self.score / 100) * 16)
        painter.drawArc(
            (width - size) / 2 + 4, (height - size) / 2 + 4,
            size - 8, size - 8,
            45 * 16, span_angle
        )

        # 绘制分数
        font = QFont()
        font.setPointSize(int(size / 4))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            f"{self.score:.0f}"
        )

        # 绘制标签
        if self.label:
            font = QFont()
            font.setPointSize(int(size / 8))
            painter.setFont(font)
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(
                self.rect().adjusted(0, 0, 0, -int(size / 6)),
                Qt.AlignmentFlag.AlignCenter,
                self.label
            )


class DigitalTwinVerificationPanel(QWidget):
    """数字孪生验证面板"""

    sig_verify_clicked = pyqtSignal(str)  # 验证点击信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🔄 数字孪生验证")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 验证概览
        overview_group = QGroupBox("验证概览")
        overview_layout = QHBoxLayout()

        self.total_count = QLabel("0")
        self.pass_count = QLabel("0")
        self.fail_count = QLabel("0")

        overview_layout.addWidget(QLabel("总计:"))
        overview_layout.addWidget(self.total_count)
        overview_layout.addWidget(QLabel("通过:"))
        overview_layout.addWidget(self.pass_count)
        overview_layout.addWidget(QLabel("失败:"))
        overview_layout.addWidget(self.fail_count)
        overview_layout.addStretch()

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 验证结果列表
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["项目", "报告值", "复算值", "误差", "状态"])
        self.result_tree.setAlternatingRowColors(True)
        layout.addWidget(self.result_tree)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.verify_btn = QPushButton("🔍 验证选中项")
        self.verify_all_btn = QPushButton("🚀 验证全部")
        self.export_btn = QPushButton("📥 导出报告")

        self.verify_btn.clicked.connect(lambda: self.sig_verify_clicked.emit("selected"))
        self.verify_all_btn.clicked.connect(lambda: self.sig_verify_clicked.emit("all"))

        btn_layout.addWidget(self.verify_btn)
        btn_layout.addWidget(self.verify_all_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

    def update_data(self, verification_report: Dict):
        """更新验证数据"""
        if not verification_report:
            return

        predictions = verification_report.get('predictions', [])
        distance_verifications = verification_report.get('distance_verifications', [])

        total = len(predictions) + len(distance_verifications)
        passed = sum(1 for p in predictions if p.get('status') == 'passed')
        passed += sum(1 for d in distance_verifications if d.get('status') == 'passed')

        self.total_count.setText(str(total))
        self.pass_count.setText(str(passed))
        self.fail_count.setText(str(total - passed))

        # 更新列表
        self.result_tree.clear()

        for pred in predictions:
            item = QTreeWidgetItem([
                f"预测-{pred.get('compound', '未知')}",
                str(pred.get('original_value', '')),
                str(pred.get('recalculated_value', '')),
                f"{pred.get('relative_error', 0):.2f}%" if pred.get('relative_error') else "-",
                pred.get('status', 'pending'),
            ])
            item.setForeground(4, QColor(STATUS_COLORS.get(pred.get('status', 'pending'), 'gray')))
            self.result_tree.addTopLevelItem(item)

        for dist in distance_verifications:
            item = QTreeWidgetItem([
                f"距离-{dist.get('sensitive_point', '敏感点')}",
                f"{dist.get('claimed_distance', 0)}m",
                f"{dist.get('actual_distance', 0)}m",
                f"{dist.get('relative_error_percent', 0):.1f}%" if dist.get('relative_error_percent') else "-",
                dist.get('status', 'pending'),
            ])
            item.setForeground(4, QColor(STATUS_COLORS.get(dist.get('status', 'pending'), 'gray')))
            self.result_tree.addTopLevelItem(item)


class KnowledgeGraphCompliancePanel(QWidget):
    """知识图谱合规面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📋 知识图谱合规检查")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 合规评分
        score_layout = QHBoxLayout()
        self.compliance_gauge = ScoreGauge(label="合规评分")
        self.compliance_gauge.setMinimumSize(100, 100)
        score_layout.addWidget(self.compliance_gauge)

        self.risk_label = QLabel("风险等级: 未知")
        self.risk_label.setStyleSheet("font-size: 14px;")
        score_layout.addWidget(self.risk_label)
        score_layout.addStretch()

        layout.addLayout(score_layout)

        # 标准检查列表
        self.standard_table = QTableWidget()
        self.standard_table.setColumnCount(4)
        self.standard_table.setHorizontalHeaderLabels(["标准", "类型", "状态", "描述"])
        self.standard_table.setAlternatingRowColors(True)
        layout.addWidget(self.standard_table)

        # 跨章节推理
        cross_group = QGroupBox("跨章节一致性检查")
        cross_layout = QVBoxLayout()

        self.cross_tree = QTreeWidget()
        self.cross_tree.setHeaderLabels(["推理类型", "章节1", "章节2", "一致性", "建议"])
        cross_layout.addWidget(self.cross_tree)

        cross_group.setLayout(cross_layout)
        layout.addWidget(cross_group)

    def update_data(self, compliance_report: Dict):
        """更新合规数据"""
        if not compliance_report:
            return

        # 更新评分
        risk_level = compliance_report.get('risk_level', 'UNKNOWN')
        score_map = {"LOW": 100, "MEDIUM": 75, "HIGH": 50, "CRITICAL": 25, "UNKNOWN": 0}
        score = score_map.get(risk_level, 0)
        self.compliance_gauge.set_score(score)
        self.risk_label.setText(f"风险等级: {risk_level}")

        # 更新标准表格
        standard_checks = compliance_report.get('standard_checks', [])
        self.standard_table.setRowCount(len(standard_checks))

        for i, check in enumerate(standard_checks):
            self.standard_table.setItem(i, 0, QTableWidgetItem(check.get('standard_code', '')))
            self.standard_table.setItem(i, 1, QTableWidgetItem(check.get('check_type', '')))
            status_item = QTableWidgetItem(check.get('status', ''))
            status_item.setForeground(QColor(STATUS_COLORS.get(check.get('status', 'unknown'), 'gray')))
            self.standard_table.setItem(i, 2, status_item)
            self.standard_table.setItem(i, 3, QTableWidgetItem(check.get('description', '')))

        # 更新跨章节检查
        self.cross_tree.clear()
        cross_checks = compliance_report.get('cross_chapter_checks', [])
        for check in cross_checks:
            item = QTreeWidgetItem([
                check.get('inference_type', ''),
                check.get('chapter1', ''),
                check.get('chapter2', ''),
                check.get('status', ''),
                check.get('suggestion', ''),
            ])
            self.cross_tree.addTopLevelItem(item)


class SmartRepairPanel(QWidget):
    """智能修复面板"""

    sig_apply_patch = pyqtSignal(dict)  # 应用补丁信号
    sig_fill_manual = pyqtSignal(str, dict)  # 手动填写信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🔧 智能修复建议")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 统计
        stats_layout = QHBoxLayout()
        self.fatal_count = QLabel("0")
        self.error_count = QLabel("0")
        self.warning_count = QLabel("0")

        stats_layout.addWidget(QLabel("🔴 致命:"))
        stats_layout.addWidget(self.fatal_count)
        stats_layout.addWidget(QLabel("🟠 错误:"))
        stats_layout.addWidget(self.error_count)
        stats_layout.addWidget(QLabel("🟡 警告:"))
        stats_layout.addWidget(self.warning_count)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # 修复建议列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.suggestion_container = QWidget()
        self.suggestion_layout = QVBoxLayout(self.suggestion_container)
        self.suggestion_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.suggestion_container)
        layout.addWidget(scroll)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.apply_all_btn = QPushButton("✨ 应用所有自动修复")
        self.export_btn = QPushButton("📋 导出修复报告")

        self.apply_all_btn.clicked.connect(self._on_apply_all)
        self.export_btn.clicked.connect(self._on_export)

        btn_layout.addWidget(self.apply_all_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

    def _on_apply_all(self):
        """应用所有自动修复"""
        patches = []
        for i in range(self.suggestion_layout.count()):
            widget = self.suggestion_layout.itemAt(i).widget()
            if hasattr(widget, 'get_patch'):
                patch = widget.get_patch()
                if patch:
                    patches.append(patch)
        if patches:
            self.sig_apply_patch.emit({"patches": patches})

    def _on_export(self):
        """导出修复报告"""
        pass

    def update_data(self, repair_report: Dict):
        """更新修复数据"""
        if not repair_report:
            return

        summary = repair_report.get('repair_summary', {})

        self.fatal_count.setText(str(summary.get('fatal', 0)))
        self.error_count.setText(str(summary.get('error', 0)))
        self.warning_count.setText(str(summary.get('warning', 0)))

        # 清空并重建建议列表
        while self.suggestion_layout.count():
            child = self.suggestion_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 添加问题卡片
        issues = repair_report.get('issues', [])
        for issue in issues:
            card = RepairSuggestionCard(issue)
            card.sig_action_clicked.connect(self._on_action_clicked)
            self.suggestion_layout.addWidget(card)

    def _on_action_clicked(self, issue_id: str, action: str):
        """处理动作点击"""
        self.sig_fill_manual.emit(issue_id, {"action": action})


class RepairSuggestionCard(QWidget):
    """修复建议卡片"""

    sig_action_clicked = pyqtSignal(str, str)  # issue_id, action

    def __init__(self, issue: Dict, parent=None):
        super().__init__(parent)
        self.issue = issue
        self.issue_id = issue.get('issue_id', '')
        self.patch = None
        self._init_ui()

    def _init_ui(self):
        self.setMinimumHeight(80)
        self.setStyleSheet(
            "RepairSuggestionCard { background-color: #f8f9fa; "
            "border: 1px solid #dee2e6; border-radius: 8px; padding: 8px; }"
        )

        layout = QVBoxLayout(self)

        # 标题行
        header_layout = QHBoxLayout()
        level = self.issue.get('issue_level', 'warning')
        level_badge = IssueLevelBadge(level)
        level_badge.setText(level.upper())

        title = QLabel(self.issue.get('issue_description', ''))
        title.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(level_badge)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 描述
        desc = QLabel(self.issue.get('primary_suggestion', ''))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 操作按钮
        btn_layout = QHBoxLayout()

        primary_btn = QPushButton(self.issue.get('primary_button_label', '修复'))
        primary_btn.clicked.connect(lambda: self.sig_action_clicked.emit(
            self.issue_id, self.issue.get('primary_action', '')
        ))
        btn_layout.addWidget(primary_btn)

        # 备选操作
        alternatives = self.issue.get('alternative_actions', [])
        for alt in alternatives[:2]:
            alt_btn = QPushButton(alt.get('button', ''))
            alt_btn.clicked.connect(lambda checked, a=alt: self.sig_action_clicked.emit(
                self.issue_id, a.get('action', '')
            ))
            btn_layout.addWidget(alt_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def get_patch(self) -> Optional[Dict]:
        """获取补丁"""
        return self.patch


class AdversarialTestPanel(QWidget):
    """对抗性测试面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🎯 对抗性测试")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 鲁棒性评分
        score_layout = QHBoxLayout()
        self.robustness_gauge = ScoreGauge(label="鲁棒性评分")
        self.robustness_gauge.setMinimumSize(100, 100)
        score_layout.addWidget(self.robustness_gauge)

        self.uncertainty_label = QLabel("平均不确定度: -%")
        score_layout.addWidget(self.uncertainty_label)
        score_layout.addStretch()

        layout.addLayout(score_layout)

        # 不确定性分析
        uncertainty_group = QGroupBox("不确定性分析")
        uncertainty_layout = QVBoxLayout()

        self.uncertainty_table = QTableWidget()
        self.uncertainty_table.setColumnCount(4)
        self.uncertainty_table.setHorizontalHeaderLabels(["参数", "基准值", "变化范围", "不确定度"])
        self.uncertainty_table.setAlternatingRowColors(True)
        uncertainty_layout.addWidget(self.uncertainty_table)

        uncertainty_group.setLayout(uncertainty_layout)
        layout.addWidget(uncertainty_group)

        # 极端情景
        extreme_group = QGroupBox("极端情景推演")
        extreme_layout = QVBoxLayout()

        self.extreme_tree = QTreeWidget()
        self.extreme_tree.setHeaderLabels(["情景", "描述", "结论变化", "是否可接受"])
        extreme_layout.addWidget(self.extreme_tree)

        extreme_group.setLayout(extreme_layout)
        layout.addWidget(extreme_group)

    def update_data(self, test_report: Dict):
        """更新测试数据"""
        if not test_report:
            return

        # 更新鲁棒性评分
        robustness_score = test_report.get('robustness_score', 0)
        self.robustness_gauge.set_score(robustness_score)

        # 更新不确定性表格
        uncertainty_results = test_report.get('uncertainty_results', [])
        self.uncertainty_table.setRowCount(len(uncertainty_results))

        total_uncertainty = 0
        for i, result in enumerate(uncertainty_results):
            self.uncertainty_table.setItem(i, 0, QTableWidgetItem(result.get('parameter', '')))
            self.uncertainty_table.setItem(i, 1, QTableWidgetItem(str(result.get('baseline_value', ''))))
            self.uncertainty_table.setItem(i, 2, QTableWidgetItem(
                f"[{result.get('min_value', '')}, {result.get('max_value', '')}]"
            ))
            uncertainty_item = QTableWidgetItem(f"{result.get('uncertainty_percent', 0):.1f}%")
            self.uncertainty_table.setItem(i, 3, uncertainty_item)
            total_uncertainty += result.get('uncertainty_percent', 0)

        if uncertainty_results:
            avg_uncertainty = total_uncertainty / len(uncertainty_results)
            self.uncertainty_label.setText(f"平均不确定度: {avg_uncertainty:.1f}%")

        # 更新极端情景
        self.extreme_tree.clear()
        extreme_scenarios = test_report.get('extreme_scenarios', [])
        for scenario in extreme_scenarios:
            item = QTreeWidgetItem([
                scenario.get('scenario_type', ''),
                scenario.get('description', ''),
                scenario.get('conclusion_change', ''),
                scenario.get('acceptable', '未知'),
            ])
            # 设置颜色
            color = "#27ae60" if scenario.get('acceptable') == "是" else "#e74c3c"
            item.setForeground(3, QColor(color))
            self.extreme_tree.addTopLevelItem(item)


class DistributedReviewPanel(QWidget):
    """分布式审查面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌐 分布式集体审查")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 共识评分
        score_layout = QHBoxLayout()
        self.consensus_gauge = ScoreGauge(label="共识评分")
        self.consensus_gauge.setMinimumSize(100, 100)
        score_layout.addWidget(self.consensus_gauge)

        self.consensus_level_label = QLabel("共识级别: 等待中")
        score_layout.addWidget(self.consensus_level_label)
        score_layout.addStretch()

        layout.addLayout(score_layout)

        # 投票统计
        stats_layout = QHBoxLayout()
        self.agreed_count = QLabel("0")
        self.objected_count = QLabel("0")
        self.abstained_count = QLabel("0")

        stats_layout.addWidget(QLabel("✅ 同意:"))
        stats_layout.addWidget(self.agreed_count)
        stats_layout.addWidget(QLabel("❌ 反对:"))
        stats_layout.addWidget(self.objected_count)
        stats_layout.addWidget(QLabel("⏸️ 弃权:"))
        stats_layout.addWidget(self.abstained_count)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # 参与节点
        nodes_group = QGroupBox("参与节点")
        nodes_layout = QVBoxLayout()

        self.nodes_tree = QTreeWidget()
        self.nodes_tree.setHeaderLabels(["节点", "类型", "信誉", "投票"])
        nodes_layout.addWidget(self.nodes_tree)

        nodes_group.setLayout(nodes_layout)
        layout.addWidget(nodes_group)

        # 审查历史
        history_group = QGroupBox("审查历史追溯")
        history_layout = QVBoxLayout()

        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["时间", "节点", "结论", "评分", "哈希"])
        history_layout.addWidget(self.history_tree)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

    def update_data(self, task: Dict, votes: List[Dict], consensus: Dict = None):
        """更新审查数据"""
        if not task:
            return

        # 更新共识评分
        if consensus:
            consensus_score = consensus.get('consensus_score', 0) * 100
            self.consensus_gauge.set_score(consensus_score)

            level = consensus.get('consensus_level', 'pending')
            self.consensus_level_label.setText(f"共识级别: {level}")

            self.agreed_count.setText(str(consensus.get('agreed', 0)))
            self.objected_count.setText(str(consensus.get('objected', 0)))
            self.abstained_count.setText(str(consensus.get('abstained', 0)))

        # 更新节点列表
        self.nodes_tree.clear()
        assigned_nodes = task.get('assigned_nodes', [])
        for node_id in assigned_nodes:
            item = QTreeWidgetItem([
                node_id[:12],
                "工程师",
                "-",
                "待投票",
            ])
            self.nodes_tree.addTopLevelItem(item)

        # 更新投票列表
        for vote in votes:
            item = QTreeWidgetItem([
                vote.get('node_name', ''),
                vote.get('verdict', ''),
                f"{vote.get('overall_score', 0):.1f}",
                vote.get('comments', '')[:50],
            ])
            self.nodes_tree.addTopLevelItem(item)


class IntelligentReviewPanel(QWidget):
    """
    智能审查主面板

    整合所有审查能力的综合界面
    """

    sig_start_review = pyqtSignal(dict)  # 开始审查信号
    sig_apply_patch = pyqtSignal(dict)  # 应用补丁信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 标题栏
        header_layout = QHBoxLayout()

        title = QLabel("🧠 智能审查系统")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 模式选择
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["全自动审查", "半自动审查", "分布式审查"])
        header_layout.addWidget(self.mode_combo)

        # 开始按钮
        self.start_btn = QPushButton("🚀 开始审查")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white; "
            "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
        )
        self.start_btn.clicked.connect(self._on_start_review)
        header_layout.addWidget(self.start_btn)

        main_layout.addLayout(header_layout)

        # 整体评分
        score_layout = QHBoxLayout()
        self.verification_gauge = ScoreGauge(label="验证")
        self.compliance_gauge = ScoreGauge(label="合规")
        self.robustness_gauge = ScoreGauge(label="鲁棒性")
        self.overall_gauge = ScoreGauge(label="综合")

        for gauge in [self.verification_gauge, self.compliance_gauge,
                       self.robustness_gauge, self.overall_gauge]:
            gauge.setMinimumSize(100, 100)
            score_layout.addWidget(gauge)

        main_layout.addLayout(score_layout)

        # Tab页面
        self.tabs = QTabWidget()

        # 数字孪生验证
        self.digital_twin_panel = DigitalTwinVerificationPanel()
        self.tabs.addTab(self.digital_twin_panel, "🔄 数字孪生")

        # 知识图谱合规
        self.compliance_panel = KnowledgeGraphCompliancePanel()
        self.tabs.addTab(self.compliance_panel, "📋 合规检查")

        # 智能修复
        self.repair_panel = SmartRepairPanel()
        self.repair_panel.sig_apply_patch.connect(self._on_apply_patch)
        self.tabs.addTab(self.repair_panel, "🔧 智能修复")

        # 对抗性测试
        self.adversarial_panel = AdversarialTestPanel()
        self.tabs.addTab(self.adversarial_panel, "🎯 对抗测试")

        # 分布式审查
        self.distributed_panel = DistributedReviewPanel()
        self.tabs.addTab(self.distributed_panel, "🌐 分布式")

        main_layout.addWidget(self.tabs)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        main_layout.addLayout(status_layout)

    def _on_start_review(self):
        """开始审查"""
        mode = ["auto", "semi_auto", "distributed"][self.mode_combo.currentIndex()]
        self.sig_start_review.emit({"mode": mode})
        self.start_btn.setEnabled(False)
        self.status_label.setText("审查中...")
        self.progress_bar.start_animation()

    def _on_apply_patch(self, patches: Dict):
        """应用补丁"""
        self.sig_apply_patch.emit(patches)

    def update_session(self, session: Dict):
        """更新会话数据"""
        # 更新各模块数据
        if 'verification_report' in session:
            self.digital_twin_panel.update_data(session['verification_report'])

        if 'compliance_report' in session:
            self.compliance_panel.update_data(session['compliance_report'])

        if 'repair_report' in session:
            self.repair_panel.update_data(session['repair_report'])

        if 'test_report' in session:
            self.adversarial_panel.update_data(session['test_report'])

        if 'distributed_task' in session:
            votes = session.get('votes', [])
            consensus = session.get('consensus_result')
            self.distributed_panel.update_data(session['distributed_task'], votes, consensus)

        # 更新评分
        overall_score = session.get('overall_score', 0)
        self.overall_gauge.set_score(overall_score)

        verification_score = session.get('verification_score', 0)
        self.verification_gauge.set_score(verification_score)

        compliance_score = session.get('compliance_score', 0)
        self.compliance_gauge.set_score(compliance_score)

        robustness_score = session.get('robustness_score', 0)
        self.robustness_gauge.set_score(robustness_score)

        # 更新状态
        self.progress_bar.stop_animation()
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.status_label.setText(f"审查完成，综合评分: {overall_score:.1f}")

    def show_review_result(self, report: Dict):
        """显示审查结果"""
        # 显示综合报告对话框
        dialog = ReviewResultDialog(report, self)
        dialog.exec()


class ReviewResultDialog(QDialog):
    """审查结果对话框"""

    def __init__(self, report: Dict, parent=None):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle("审查结果")
        self.setMinimumSize(600, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📊 综合审查报告")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 综合评分
        score_layout = QHBoxLayout()
        overall = self.report.get('overall_score', 0)
        score_label = QLabel(f"综合评分: {overall:.1f}")

        risk = self.report.get('risk_level', 'UNKNOWN')
        risk_colors = {"LOW": "green", "MEDIUM": "blue", "HIGH": "orange", "CRITICAL": "red"}
        risk_label = QLabel(f"风险等级: {risk}")
        risk_label.setStyleSheet(f"color: {risk_colors.get(risk, 'gray')};")

        score_layout.addWidget(score_label)
        score_layout.addWidget(risk_label)
        score_layout.addStretch()
        layout.addLayout(score_layout)

        # 结论
        conclusion = QLabel(f"结论: {self.report.get('conclusion', '')}")
        conclusion.setWordWrap(True)
        layout.addWidget(conclusion)

        # 建议
        recommendation = self.report.get('recommendation', '')
        rec_colors = {"ACCEPT": "green", "REVISE": "orange", "REJECT": "red"}
        rec_label = QLabel(f"建议: {recommendation}")
        rec_label.setStyleSheet(f"font-weight: bold; color: {rec_colors.get(recommendation, 'black')};")

        # 问题汇总
        issues_text = QTextEdit()
        issues_text.setReadOnly(True)

        fatal = self.report.get('fatal_issues', [])
        errors = self.report.get('error_issues', [])
        warnings = self.report.get('warnings', [])

        report_text = "🔴 致命问题:\n"
        report_text += "\n".join(f"  • {i}" for i in fatal) or "  无\n"
        report_text += "\n🟠 错误:\n"
        report_text += "\n".join(f"  • {i}" for i in errors) or "  无\n"
        report_text += "\n🟡 警告:\n"
        report_text += "\n".join(f"  • {i}" for i in warnings) or "  无"

        issues_text.setPlainText(report_text)
        layout.addWidget(issues_text)

        # 按钮
        buttons = QDialogButtonBox()
        buttons.addButton("导出报告", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("关闭", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._on_export)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_export(self):
        """导出报告"""
        # TODO: 实现导出功能
        self.accept()