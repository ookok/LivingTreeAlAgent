"""
指挥官决策 (Commander's Verdict)

目标：用户选择冲突处理策略

选项：
- ✅ 并行共存
- 🔄 替换旧版
- ❌ 取消装配
"""

from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QGroupBox,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon


class ConflictCard(QGroupBox):
    """冲突卡片"""

    def __init__(self, conflict_item, parent=None):
        super().__init__(parent)
        self.conflict_item = conflict_item
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            ConflictCard {
                border: 1px solid #3a3a4a;
                border-radius: 8px;
                background-color: #2a2a3a;
                padding: 10px;
                margin: 5px;
            }
        """)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(f"⚠️ {self.conflict_item.conflict_type.value}")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # 详情
        details = QLabel(
            f"<b>内置模块:</b> {self.conflict_item.builtin.name}<br>"
            f"<b>外部模块:</b> {self.conflict_item.external}<br>"
            f"<b>严重程度:</b> {self.conflict_item.severity}"
        )
        details.setStyleSheet("color: #cccccc;")
        layout.addWidget(details)


class StrategyOption(QWidget):
    """策略选项"""

    clicked = pyqtSignal(str)  # strategy

    def __init__(self, strategy_data: dict, parent=None):
        super().__init__(parent)
        self.strategy_data = strategy_data
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            StrategyOption {
                border: 2px solid #4a4a5a;
                border-radius: 10px;
                background-color: #252535;
                padding: 15px;
                margin: 5px;
            }
            StrategyOption:hover {
                border-color: #6a6a8a;
                background-color: #2a2a4a;
            }
        """)

        layout = QVBoxLayout(self)

        # 图标和标题
        header = QHBoxLayout()
        icon = QLabel(self.strategy_data['icon'])
        icon.setFont(QFont("Segoe UI Symbol", 24))
        header.addWidget(icon)

        title = QLabel(self.strategy_data['title'])
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        header.addWidget(title, 1)

        layout.addLayout(header)

        # 描述
        desc = QLabel(self.strategy_data['description'])
        desc.setStyleSheet("color: #aaaaaa;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 风险标签
        risk = self.strategy_data['risk']
        risk_color = {"low": "#4CAF50", "medium": "#FFC107", "high": "#F44336"}.get(risk, "#888888")
        risk_label = QLabel(f"<span style='color:{risk_color};'>● 风险: {risk}</span>")
        layout.addWidget(risk_label)

        # 点击区域
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = lambda e: self.clicked.emit(self.strategy_data['strategy'])


class CommanderPanel(QWidget):
    """
    指挥官决策面板

    当检测到冲突时，显示冲突报告和解决策略供用户选择
    """

    # 信号
    strategy_selected = pyqtSignal(str)  # ResolutionStrategy.value
    cancelled = pyqtSignal()

    def __init__(self, conflict_report=None, parent=None):
        super().__init__(parent)
        self.conflict_report = conflict_report
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a2a;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #3a3a5a;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a7a;
            }
        """)

        main_layout = QVBoxLayout(self)

        # 标题
        title = QLabel("⚠️ 战术评估报告")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        main_layout.addWidget(title)

        # 冲突详情
        if self.conflict_report and self.conflict_report.has_conflict:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none;")

            conflict_widget = QWidget()
            conflict_layout = QVBoxLayout(conflict_widget)

            for conflict in self.conflict_report.conflicts:
                card = ConflictCard(conflict)
                conflict_layout.addWidget(card)

            conflict_layout.addStretch()
            scroll.setWidget(conflict_widget)
            main_layout.addWidget(scroll, 1)

        # 摘要
        if self.conflict_report:
            summary = QLabel(self.conflict_report.summary or "检测到冲突，请选择处理策略")
            summary.setStyleSheet("color: #ffcc00; padding: 10px;")
            main_layout.addWidget(summary)

        # 策略选项
        strategies_label = QLabel("选择处理策略:")
        strategies_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        main_layout.addWidget(strategies_label)

        from .conflict import ConflictDetector
        detector = ConflictDetector()
        options = detector.get_resolution_options()

        self.strategy_widgets = []
        for strategy_data in options:
            option = StrategyOption(strategy_data)
            option.clicked.connect(self._on_strategy_clicked)
            main_layout.addWidget(option)
            self.strategy_widgets.append(option)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消装配")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

    def _on_strategy_clicked(self, strategy: str):
        """策略被点击"""
        self.strategy_selected.emit(strategy)

    def _on_cancel(self):
        """取消"""
        self.cancelled.emit()

    def update_conflict_report(self, report):
        """更新冲突报告"""
        self.conflict_report = report
        # 重新构建 UI
        # 简化为直接替换
        self.setParent(None)
        self.__init__(conflict_report=report)
        self.show()