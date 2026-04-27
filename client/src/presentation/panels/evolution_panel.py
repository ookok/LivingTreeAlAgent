"""
进化面板 - 对接真实 EvolutionEngine
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QProgressBar,
    QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QMessageBox
)
from PyQt6.QtGui import QFont, QTextCursor

from client.src.business.nanochat_config import config


# ── 进化面板主界面 ─────────────────────────────────────────────────────

class EvolutionPanel(QWidget):
    """进化面板 - 对接真实 EvolutionEngine"""

    evolution_started = pyqtSignal()
    evolution_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_status)
        self._setup_ui()
        self._init_engine()

    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🧬 进化面板")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 描述
        desc = QLabel("可视化进化引擎 - 监控和控制系统自我进化过程")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 标签页
        tabs = QTabWidget()

        # 标签页1：控制面板
        control_tab = QWidget()
        control_layout = QVBoxLayout(control_tab)
        control_layout.setContentsMargins(0, 16, 0, 0)

        # 控制区域
        control_group = QGroupBox("进化控制")
        control_form = QFormLayout(control_group)

        self.start_btn = QPushButton("开始进化")
        self.start_btn.clicked.connect(self._start_evolution)
        control_form.addRow("控制:", self.start_btn)

        self.stop_btn = QPushButton("停止进化")
        self.stop_btn.clicked.connect(self._stop_evolution)
        self.stop_btn.setEnabled(False)
        control_form.addRow("", self.stop_btn)

        # 状态标签
        self.status_label = QLabel("⚪ 就绪")
        self.status_label.setStyleSheet("font-size: 14px;")
        control_form.addRow("状态:", self.status_label)

        control_layout.addWidget(control_group)

        # 参数配置
        param_group = QGroupBox("进化参数")
        param_layout = QFormLayout(param_group)

        self.population_spin = QSpinBox()
        self.population_spin.setRange(10, 1000)
        self.population_spin.setValue(100)
        param_layout.addRow("种群大小:", self.population_spin)

        self.generations_spin = QSpinBox()
        self.generations_spin.setRange(1, 1000)
        self.generations_spin.setValue(50)
        param_layout.addRow("进化代数:", self.generations_spin)

        self.mutation_spin = QDoubleSpinBox()
        self.mutation_spin.setRange(0.0, 1.0)
        self.mutation_spin.setValue(0.1)
        self.mutation_spin.setSingleStep(0.01)
        param_layout.addRow("变异率:", self.mutation_spin)

        self.crossover_spin = QDoubleSpinBox()
        self.crossover_spin.setRange(0.0, 1.0)
        self.crossover_spin.setValue(0.8)
        self.crossover_spin.setSingleStep(0.01)
        param_layout.addRow("交叉率:", self.crossover_spin)

        control_layout.addWidget(param_group)
        control_layout.addStretch()

        tabs.addTab(control_tab, "控制面板")

        # 标签页2：进化日志
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 16, 0, 0)

        log_group = QGroupBox("进化日志")
        log_inner_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(400)
        log_inner_layout.addWidget(self.log_text)

        log_layout.addWidget(log_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        log_layout.addWidget(self.progress_bar)

        log_layout.addStretch()

        tabs.addTab(log_tab, "进化日志")

        # 标签页3：提案列表
        proposal_tab = QWidget()
        proposal_layout = QVBoxLayout(proposal_tab)
        proposal_layout.setContentsMargins(0, 16, 0, 0)

        proposal_group = QGroupBox("进化提案")
        proposal_inner_layout = QVBoxLayout(proposal_group)

        self.proposal_table = QTableWidget()
        self.proposal_table.setColumnCount(5)
        self.proposal_table.setHorizontalHeaderLabels(["ID", "标题", "优先级", "状态", "创建时间"])
        self.proposal_table.setAlternatingRowColors(True)
        proposal_inner_layout.addWidget(self.proposal_table)

        proposal_layout.addWidget(proposal_group)
        proposal_layout.addStretch()

        tabs.addTab(proposal_tab, "进化提案")

        layout.addWidget(tabs)

    def _init_engine(self):
        """初始化 EvolutionEngine"""
        try:
            from client.src.business.evolution_engine.evolution_engine import EvolutionEngine

            project_root = str(Path(__file__).parent.parent.parent.parent)

            self._engine = EvolutionEngine(
                project_root=project_root,
                config={
                    "sensors": {},
                    "aggregator": {},
                    "scan_interval": 3600,
                }
            )

            self._log("✅ EvolutionEngine 初始化成功")
            self._log(f"   项目目录: {project_root}")

        except Exception as e:
            self._log(f"❌ EvolutionEngine 初始化失败: {e}")
            self._engine = None

    def _start_evolution(self):
        """开始进化"""
        if not self._engine:
            QMessageBox.warning(self, "警告", "EvolutionEngine 未初始化！")
            return

        try:
            # 设置参数
            self._engine.config = {
                "population_size": self.population_spin.value(),
                "generations": self.generations_spin.value(),
                "mutation_rate": self.mutation_spin.value(),
                "crossover_rate": self.crossover_spin.value(),
                "scan_interval": 3600,
            }

            # 启动引擎
            self._engine.start()

            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("🟢 进化中...")

            self._log("开始进化...")
            self._log(f"   种群大小: {self.population_spin.value()}")
            self._log(f"   进化代数: {self.generations_spin.value()}")

            self.evolution_started.emit()

            # 启动定时器（每秒刷新一次状态）
            self._timer.start(1000)

        except Exception as e:
            self._log(f"❌ 启动失败: {e}")
            QMessageBox.warning(self, "错误", f"启动失败: {e}")

    def _stop_evolution(self):
        """停止进化"""
        if not self._engine:
            return

        try:
            self._engine.stop()

            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("⚪ 已停止")

            self._log("进化已停止")

            self.evolution_stopped.emit()

            # 停止定时器
            self._timer.stop()

        except Exception as e:
            self._log(f"❌ 停止失败: {e}")

    def _refresh_status(self):
        """刷新状态（定时器回调）"""
        if not self._engine:
            return

        try:
            # 获取引擎状态
            stats = self._engine._stats

            # 更新日志（如果有新日志）
            # TODO: 从 EvolutionLog 获取最新日志

            # 更新提案列表
            self._refresh_proposals()

            # 更新进度（如果有正在执行的提案）
            executing = self._engine._executing_proposals
            if executing:
                # TODO: 计算进度
                pass

        except Exception as e:
            self._log(f"❌ 刷新状态失败: {e}")

    def _refresh_proposals(self):
        """刷新提案列表"""
        if not self._engine:
            return

        try:
            proposals = self._engine.get_proposals()

            self.proposal_table.setRowCount(len(proposals))

            for row, proposal in enumerate(proposals):
                self.proposal_table.setItem(row, 0, QTableWidgetItem(proposal.get("id", "")))
                self.proposal_table.setItem(row, 1, QTableWidgetItem(proposal.get("title", "")))
                self.proposal_table.setItem(row, 2, QTableWidgetItem(proposal.get("priority", "")))
                self.proposal_table.setItem(row, 3, QTableWidgetItem(proposal.get("status", "")))
                self.proposal_table.setItem(row, 4, QTableWidgetItem(proposal.get("created_at", "")))

        except Exception as e:
            self._log(f"❌ 刷新提案失败: {e}")

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)

        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def get_config(self) -> dict:
        """获取进化配置"""
        return {
            "population_size": self.population_spin.value(),
            "generations": self.generations_spin.value(),
            "mutation_rate": self.mutation_spin.value(),
            "crossover_rate": self.crossover_spin.value(),
        }

    def closeEvent(self, event):
        """关闭事件"""
        if self._engine and self._engine._running:
            self._stop_evolution()
        super().closeEvent(event)
