"""
L4 执行器监控面板
PyQt6 实现，监控 RelayFreeLLM 网关和 L4 执行层
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QFrame, QComboBox, QCheckBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QStatusBar, QMenuBar, QMenu, QToolBar, QScrollArea,
    QGridLayout, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QFont, QColor, QPalette

logger = logging.getLogger(__name__)


class L4StatusWidget(QFrame):
    """L4 执行器状态显示组件"""

    STATUS_COLORS = {
        "healthy": "#4CAF50",
        "degraded": "#FFA500",
        "unhealthy": "#F44336",
        "unknown": "#999999"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "unknown"
        self._last_update = None
        self.setup_ui()
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._refresh_status)
        self._update_timer.start(5000)  # 5秒刷新

    def setup_ui(self):
        """设置 UI"""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        layout = QVBoxLayout()

        # 标题
        title = QLabel("L4 执行器状态")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        # 状态行
        status_layout = QHBoxLayout()

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 20px;")

        self.status_label = QLabel("未知")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # 详情
        self.details_label = QLabel("点击刷新获取状态")
        self.details_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setMaximumWidth(80)
        self.refresh_btn.clicked.connect(self._refresh_status)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setMaximumWidth(60)
        self.settings_btn.clicked.connect(self._open_settings)

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.settings_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def set_status(self, status: str, details: Optional[Dict] = None):
        """设置状态"""
        self._status = status
        self._last_update = datetime.now()

        color = self.STATUS_COLORS.get(status, "#999999")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 20px;")

        status_text = {
            "healthy": "健康",
            "degraded": "降级",
            "unhealthy": "不可用",
            "unknown": "未知"
        }
        self.status_label.setText(status_text.get(status, status))

        if details:
            relay = "✓" if details.get("relay_available") else "✗"
            direct = "✓" if details.get("direct_available") else "✗"
            stats = details.get("stats", {})

            detail_text = (
                f"Relay 网关: {relay} | Direct Ollama: {direct}\n"
                f"总请求: {stats.get('total_requests', 0)} | "
                f"成功率: {stats.get('success_rate', 0)*100:.1f}%"
            )
            self.details_label.setText(detail_text)

    def _refresh_status(self):
        """刷新状态"""
        try:
            from .business.fusion_rag import get_l4_executor
            executor = get_l4_executor()
            stats = executor.get_stats()

            # 判断健康状态
            if stats.get("total_requests", 0) == 0:
                status = "unknown"
            elif stats.get("failures", 0) / stats.get("total_requests", 1) > 0.5:
                status = "unhealthy"
            elif stats.get("failures", 0) > 0:
                status = "degraded"
            else:
                status = "healthy"

            self.set_status(status, stats)
        except Exception as e:
            self.set_status("unknown")
            logger.debug(f"L4 状态刷新失败: {e}")

    def _open_settings(self):
        """打开设置对话框"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "设置", "L4 执行器设置功能开发中...")


class L4ProviderTable(QWidget):
    """Provider 列表表格"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()

        # 标题行
        title_layout = QHBoxLayout()
        title = QLabel("已配置厂商")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_layout.addWidget(title)

        title_layout.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setMaximumWidth(60)
        self.refresh_btn.clicked.connect(self._refresh)

        title_layout.addWidget(self.refresh_btn)

        layout.addLayout(title_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["厂商", "状态", "优先级", "可用模型", "最后使用"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.table)

        self.setLayout(layout)
        self._refresh()

    def _refresh(self):
        """刷新表格"""
        try:
            from app.services.relayfree import list_providers
            providers = list_providers()

            self.table.setRowCount(len(providers))
            for row, p in enumerate(providers):
                self.table.setItem(row, 0, QTableWidgetItem(p.get("provider_id", "")))

                status_item = QTableWidgetItem("● " + ("健康" if p.get("is_healthy") else "不可用"))
                status_color = "#4CAF50" if p.get("is_healthy") else "#F44336"
                status_item.setForeground(QColor(status_color))
                self.table.setItem(row, 1, status_item)

                self.table.setItem(row, 2, QTableWidgetItem(str(p.get("priority", 0))))
                self.table.setItem(row, 3, QTableWidgetItem(str(len(p.get("models", [])))))
                self.table.setItem(row, 4, QTableWidgetItem(p.get("last_used", "从未")))

        except Exception as e:
            logger.error(f"刷新 Provider 列表失败: {e}")


class L4ExecutionLog(QWidget):
    """L4 执行日志"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 100
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()

        # 标题行
        title_layout = QHBoxLayout()
        title = QLabel("执行日志")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_layout.addWidget(title)

        title_layout.addStretch()

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMaximumWidth(50)
        self.clear_btn.clicked.connect(self._clear)

        title_layout.addWidget(self.clear_btn)

        layout.addLayout(title_layout)

        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")

        layout.addWidget(self.log_text)

        self.setLayout(layout)

        # 刷新定时器
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(2000)  # 2秒刷新

    def append_log(self, level: str, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": "#4CAF50",
            "WARNING": "#FFA500",
            "ERROR": "#F44336",
            "DEBUG": "#999999"
        }
        color = color_map.get(level, "#d4d4d4")

        html = f'<span style="color: #666666;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{level}</span> '
        html += f'<span style="color: #d4d4d4;">{message}</span>'

        self.log_text.append(html)

        # 限制行数
        doc_block = self.log_text.document().blockCount()
        if doc_block > self._max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(doc_block - self._max_lines):
                cursor.select(cursor.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()

    def _refresh(self):
        """刷新日志"""
        try:
            from .business.fusion_rag import get_l4_executor
            executor = get_l4_executor()
            stats = executor.get_stats()

            if stats.get("total_requests", 0) > 0:
                last_provider = stats.get("last_provider", "unknown")
                self.append_log(
                    "INFO",
                    f"L4 执行: total={stats['total_requests']}, "
                    f"relay={stats['relay_requests']}, "
                    f"direct={stats['direct_requests']}, "
                    f"last={last_provider}"
                )
        except Exception:
            pass

    def _clear(self):
        """清空日志"""
        self.log_text.clear()


class L4TestWidget(QWidget):
    """L4 测试组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_thread = None
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()

        # 标题
        title = QLabel("L4 执行测试")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # 输入
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("消息:"))

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入测试消息...")
        self.input_field.setText("你好，请介绍一下自己")
        input_layout.addWidget(self.input_field)

        layout.addLayout(input_layout)

        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "auto", "deepseek", "zhipu", "dashscope", "ollama",
            "gpt-4", "gpt-3.5", "claude"
        ])
        model_layout.addWidget(self.model_combo)

        model_layout.addStretch()

        self.execute_btn = QPushButton("执行")
        self.execute_btn.clicked.connect(self._execute_test)
        model_layout.addWidget(self.execute_btn)

        layout.addLayout(model_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 结果
        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout()

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(150)
        self.result_text.setPlaceholderText("执行结果将显示在这里...")

        result_layout.addWidget(self.result_text)
        result_group.setLayout(result_layout)

        layout.addWidget(result_group)

        self.setLayout(layout)

    def _execute_test(self):
        """执行测试"""
        message = self.input_field.text().strip()
        if not message:
            return

        model = self.model_combo.currentText()
        self.execute_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.result_text.clear()

        # 异步执行
        asyncio.create_task(self._do_test(message, model))

    async def _do_test(self, message: str, model: str):
        """执行测试"""
        try:
            from .business.fusion_rag import get_l4_executor

            executor = get_l4_executor()
            messages = [{"role": "user", "content": message}]

            result = await executor.execute(
                messages=messages,
                model=model,
                stream=False
            )

            # 显示结果
            content = ""
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")

            self.result_text.setPlainText(content or str(result))

            # 状态
            provider = result.get("_provider", "unknown")
            self.result_text.append(f"\n\n[Provider: {provider}]")

        except Exception as e:
            self.result_text.setPlainText(f"执行失败: {e}")

        finally:
            self.execute_btn.setEnabled(True)
            self.progress_bar.setVisible(False)


class L4ExecutorPanel(QWidget):
    """
    L4 执行器主面板
    四级缓存金字塔的可视化监控界面
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """设置 UI"""
        main_layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("L4 执行器控制台")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)

        title_layout.addStretch()

        version_label = QLabel("v2.0 (四级缓存金字塔)")
        version_label.setStyleSheet("color: #666666; font-size: 11px;")
        title_layout.addWidget(version_label)

        main_layout.addLayout(title_layout)

        # Tab 页面
        tabs = QTabWidget()

        # Tab 1: 概览
        overview_tab = self._create_overview_tab()
        tabs.addTab(overview_tab, "概览")

        # Tab 2: Provider 管理
        provider_tab = self._create_provider_tab()
        tabs.addTab(provider_tab, "厂商管理")

        # Tab 3: 执行日志
        log_tab = self._create_log_tab()
        tabs.addTab(log_tab, "执行日志")

        # Tab 4: 测试
        test_tab = self._create_test_tab()
        tabs.addTab(test_tab, "功能测试")

        main_layout.addWidget(tabs)

        self.setLayout(main_layout)

    def _create_overview_tab(self) -> QWidget:
        """创建概览 Tab"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout()

        # 状态卡片
        status_layout = QHBoxLayout()

        # L4 状态
        self.status_widget = L4StatusWidget()
        status_layout.addWidget(self.status_widget)

        # 统计卡片
        stats_card = self._create_stats_card()
        status_layout.addWidget(stats_card)

        status_layout.addStretch()

        layout.addLayout(status_layout)

        # 架构说明
        arch_group = QGroupBox("四级缓存金字塔架构")
        arch_layout = QVBoxLayout()

        arch_text = QLabel(
            "L1 精确缓存 → L2 会话缓存 → L3 知识库 → L4 Relay 执行\n\n"
            "• L1-L3 未命中时穿透到 L4（RelayFreeLLM 网关）\n"
            "• L4 支持 20+ 国产及国际模型厂商\n"
            "• 零配置裸跑：自动启用本地 Ollama\n"
            "• L4 结果自动回填上层缓存"
        )
        arch_text.setStyleSheet("color: #444444; font-size: 12px; line-height: 1.6;")
        arch_layout.addWidget(arch_text)

        arch_group.setLayout(arch_layout)
        layout.addWidget(arch_group)

        layout.addStretch()
        content.setLayout(layout)
        widget.setWidget(content)

        return widget

    def _create_stats_card(self) -> QWidget:
        """创建统计卡片"""
        card = QGroupBox("执行统计")
        layout = QVBoxLayout()

        self.stats_labels = {}
        stats_fields = [
            ("total", "总请求"),
            ("relay", "Relay 请求"),
            ("direct", "Direct 请求"),
            ("failures", "失败次数"),
            ("write_back", "回填次数")
        ]

        for key, label in stats_fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))

            value_label = QLabel("0")
            value_label.setStyleSheet("color: #2196F3; font-weight: bold;")
            self.stats_labels[key] = value_label

            row.addWidget(value_label)
            row.addStretch()
            layout.addLayout(row)

        # 刷新按钮
        refresh_btn = QPushButton("刷新统计")
        refresh_btn.clicked.connect(self._refresh_stats)
        layout.addWidget(refresh_btn)

        card.setLayout(layout)
        return card

    def _create_provider_tab(self) -> QWidget:
        """创建厂商管理 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Provider 表格
        self.provider_table = L4ProviderTable()
        layout.addWidget(self.provider_table)

        widget.setLayout(layout)
        return widget

    def _create_log_tab(self) -> QWidget:
        """创建日志 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.log_widget = L4ExecutionLog()
        layout.addWidget(self.log_widget)

        widget.setLayout(layout)
        return widget

    def _create_test_tab(self) -> QWidget:
        """创建测试 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.test_widget = L4TestWidget()
        layout.addWidget(self.test_widget)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _refresh_stats(self):
        """刷新统计"""
        try:
            from .business.fusion_rag import get_l4_executor
            executor = get_l4_executor()
            stats = executor.get_stats()

            self.stats_labels["total"].setText(str(stats.get("total_requests", 0)))
            self.stats_labels["relay"].setText(str(stats.get("relay_requests", 0)))
            self.stats_labels["direct"].setText(str(stats.get("direct_requests", 0)))
            self.stats_labels["failures"].setText(str(stats.get("failures", 0)))
            self.stats_labels["write_back"].setText(str(stats.get("write_back_count", 0)))

        except Exception as e:
            logger.error(f"刷新统计失败: {e}")
