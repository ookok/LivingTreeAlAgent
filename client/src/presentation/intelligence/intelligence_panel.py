# -*- coding: utf-8 -*-
"""
Intelligence Panel 全源情报中心面板
Intelligence Center UI for Hermes Desktop
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QCheckBox, QGroupBox, QFrame, QProgressBar,
    QSpinBox, QDoubleSpinBox, QTextBrowser, QListWidget,
    QListWidgetItem, QSplitter, QStatusBar, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout,
)

logger = logging.getLogger(__name__)


class IntelligencePanel(QWidget):
    """
    全源情报中心面板

    包含5个标签页：
    1. 搜索 - 多源搜索与深度检索
    2. 竞品 - 竞品监控与管理
    3. 谣言 - 谣言检测与舆情分析
    4. 预警 - 预警记录与统计
    5. 报告 - 报告生成与查看
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hub = None  # 延迟初始化
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        header = self._create_header()
        layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_search_tab(), "搜索")
        self.tabs.addTab(self._create_competitor_tab(), "竞品")
        self.tabs.addTab(self._create_rumor_tab(), "谣言")
        self.tabs.addTab(self._create_alert_tab(), "预警")
        self.tabs.addTab(self._create_report_tab(), "报告")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("QFrame { background: #2d5a27; padding: 8px; }")
        layout = QHBoxLayout(header)

        title = QLabel("全源情报中心")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("QPushButton { background: #4a7c43; color: white; border: none; padding: 5px 15px; }")
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        return header

    # ==================== 搜索标签页 ====================

    def _create_search_tab(self) -> QWidget:
        """搜索标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 搜索框
        search_box = QGroupBox("多源搜索")
        search_layout = QHBoxLayout(search_box)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)

        # 搜索类型
        self.search_type = QComboBox()
        self.search_type.addItems(["综合", "竞品", "产品", "新闻", "舆情"])
        search_layout.addWidget(QLabel("类型:"))
        search_layout.addWidget(self.search_type)

        layout.addWidget(search_box)

        # 结果显示
        self.search_results = QTextBrowser()
        self.search_results.setPlaceholderText("搜索结果将显示在这里...")
        layout.addWidget(self.search_results)

        return tab

    @pyqtSlot()
    def _on_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            return

        self.status_bar.showMessage(f"正在搜索: {query}...")
        asyncio.create_task(self._search_async(query))

    async def _search_async(self, query: str):
        """异步搜索"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            search_type_map = {
                "综合": "general",
                "竞品": "competitor",
                "产品": "product",
                "新闻": "news",
                "舆情": "sentiment",
            }

            stype = search_type_map.get(self.search_type.currentText(), "general")

            if stype == "general":
                results = await self.hub.search(query)
            else:
                results = await self.hub.deep_search(query, stype)

            # 显示结果
            self.search_results.clear()
            self.search_results.append(f"**搜索结果: {query}**\n")
            self.search_results.append(f"找到 {len(results.results)} 条结果\n")

            for i, r in enumerate(results.results[:10], 1):
                self.search_results.append(f"{i}. [{r.title}]({r.url})")
                self.search_results.append(f"   来源: {r.source} | 相关度: {r.relevance_score:.2f}")
                self.search_results.append(f"   {r.snippet[:100]}...")
                self.search_results.append("")

            self.status_bar.showMessage(f"搜索完成: {len(results.results)} 条结果")

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            self.status_bar.showMessage(f"搜索失败: {e}")
            self.search_results.append(f"**错误**: {str(e)}")

    # ==================== 竞品标签页 ====================

    def _create_competitor_tab(self) -> QWidget:
        """竞品标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 添加竞品
        add_box = QGroupBox("添加竞品")
        add_layout = QHBoxLayout(add_box)

        self.competitor_name = QLineEdit()
        self.competitor_name.setPlaceholderText("竞品名称")
        add_layout.addWidget(self.competitor_name)

        self.competitor_keywords = QLineEdit()
        self.competitor_keywords.setPlaceholderText("关键词 (逗号分隔)")
        add_layout.addWidget(self.competitor_keywords)

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add_competitor)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_box)

        # 竞品列表
        list_box = QGroupBox("监控中的竞品")
        list_layout = QVBoxLayout(list_box)

        self.competitor_table = QTableWidget()
        self.competitor_table.setColumns(4)
        self.competitor_table.setHeaders(["名称", "关键词", "健康度", "状态"])
        self.competitor_table.setColumnWidth(0, 150)
        self.competitor_table.setColumnWidth(1, 200)
        self.competitor_table.setColumnWidth(2, 80)
        self.competitor_table.setColumnWidth(3, 80)
        list_layout.addWidget(self.competitor_table)

        # 操作按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._on_refresh_competitors)
        btn_layout.addWidget(refresh_btn)

        collect_btn = QPushButton("收集情报")
        collect_btn.clicked.connect(self._on_collect_intel)
        btn_layout.addWidget(collect_btn)

        monitor_btn = QPushButton("运行监控流")
        monitor_btn.clicked.connect(self._on_run_monitoring_flow)
        btn_layout.addWidget(monitor_btn)

        list_layout.addLayout(btn_layout)
        layout.addWidget(list_box)

        return tab

    @pyqtSlot()
    def _on_add_competitor(self):
        """添加竞品"""
        name = self.competitor_name.text().strip()
        if not name:
            return

        keywords = [k.strip() for k in self.competitor_keywords.text().split(",") if k.strip()]

        asyncio.create_task(self._add_competitor_async(name, keywords))

    async def _add_competitor_async(self, name: str, keywords: List[str]):
        """异步添加竞品"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            cid = self.hub.add_competitor(name, keywords)
            self.status_bar.showMessage(f"已添加竞品: {name}")

            # 清空输入
            self.competitor_name.clear()
            self.competitor_keywords.clear()

            # 刷新列表
            self._refresh_competitor_table()

        except Exception as e:
            logger.error(f"添加竞品失败: {e}")
            self.status_bar.showMessage(f"添加失败: {e}")

    @pyqtSlot()
    def _on_refresh_competitors(self):
        """刷新竞品列表"""
        self._refresh_competitor_table()

    def _refresh_competitor_table(self):
        """刷新竞品表格"""
        if not self.hub:
            return

        competitors = self.hub.list_competitors()
        self.competitor_table.setRowCount(len(competitors))

        for i, comp in enumerate(competitors):
            self.competitor_table.setItem(i, 0, QTableWidgetItem(comp["name"]))
            self.competitor_table.setItem(i, 1, QTableWidgetItem(", ".join(comp["keywords"])))
            self.competitor_table.setItem(i, 2, QTableWidgetItem("-"))
            self.competitor_table.setItem(i, 3, QTableWidgetItem("活跃" if comp["is_active"] else "暂停"))

    @pyqtSlot()
    def _on_collect_intel(self):
        """收集情报"""
        row = self.competitor_table.currentRow()
        if row < 0:
            return

        comp_name = self.competitor_table.item(row, 0).text()
        asyncio.create_task(self._collect_intel_async(comp_name))

    async def _collect_intel_async(self, comp_name: str):
        """异步收集情报"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            self.status_bar.showMessage(f"正在收集 {comp_name} 的情报...")

            # 收集情报
            competitors = self.hub.list_competitors()
            for comp in competitors:
                if comp["name"] == comp_name:
                    intel_list = await self.hub.collect_competitor_intel(comp["id"])

                    QMessageBox.information(
                        self,
                        "情报收集完成",
                        f"已收集 {len(intel_list)} 条情报"
                    )
                    break

            self.status_bar.showMessage(f"情报收集完成")

        except Exception as e:
            logger.error(f"收集情报失败: {e}")
            self.status_bar.showMessage(f"收集失败: {e}")

    @pyqtSlot()
    def _on_run_monitoring_flow(self):
        """运行监控流"""
        row = self.competitor_table.currentRow()
        if row < 0:
            return

        comp_name = self.competitor_table.item(row, 0).text()

        reply = QMessageBox.question(
            self,
            "确认",
            f"确定运行 '{comp_name}' 的竞品监控流?\n\n流程: 搜索 -> 谣言检测 -> 舆情分析 -> 生成报告",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self._run_monitoring_flow_async(comp_name))

    async def _run_monitoring_flow_async(self, comp_name: str):
        """异步运行监控流"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            self.status_bar.showMessage(f"正在运行 {comp_name} 的监控流...")

            result = await self.hub.run_competitor_monitoring_flow(comp_name)

            # 显示结果
            msg = f"竞品监控流完成\n\n"
            msg += f"搜索结果: {len(result['search_results'])} 条\n"
            msg += f"谣言风险: {len(result['rumor_results'])} 条\n"
            if result['sentiment']:
                msg += f"情感得分: {result['sentiment'].get('sentiment_score', 0):.2f}\n"
            msg += f"报告路径: {result['report_path']}"

            if result['errors']:
                msg += f"\n错误: {', '.join(result['errors'])}"

            QMessageBox.information(self, "监控流完成", msg)
            self.status_bar.showMessage("监控流完成")

        except Exception as e:
            logger.error(f"监控流失败: {e}")
            self.status_bar.showMessage(f"监控流失败: {e}")

    # ==================== 谣言标签页 ====================

    def _create_rumor_tab(self) -> QWidget:
        """谣言标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 谣言检测
        check_box = QGroupBox("谣言检测")
        check_layout = QHBoxLayout(check_box)

        self.rumor_input = QTextEdit()
        self.rumor_input.setPlaceholderText("输入待检测的文本...")
        self.rumor_input.setMaximumHeight(100)
        check_layout.addWidget(self.rumor_input)

        check_btn = QPushButton("检测")
        check_btn.clicked.connect(self._on_check_rumor)
        check_layout.addWidget(check_btn)

        layout.addWidget(check_box)

        # 结果显示
        result_box = QGroupBox("检测结果")
        result_layout = QVBoxLayout(result_box)

        self.rumor_result = QTextBrowser()
        result_layout.addWidget(self.rumor_result)

        layout.addWidget(result_box)

        # 舆情趋势
        trend_box = QGroupBox("舆情趋势")
        trend_layout = QVBoxLayout(trend_box)

        self.sentiment_trend = QLabel("暂无数据")
        trend_layout.addWidget(self.sentiment_trend)

        layout.addWidget(trend_box)

        return tab

    @pyqtSlot()
    def _on_check_rumor(self):
        """检测谣言"""
        text = self.rumor_input.toPlainText().strip()
        if not text:
            return

        asyncio.create_task(self._check_rumor_async(text))

    async def _check_rumor_async(self, text: str):
        """异步检测谣言"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            self.status_bar.showMessage("正在检测...")
            result = await self.hub.check_rumor(text)

            # 显示结果
            self.rumor_result.clear()
            self.rumor_result.append("**检测结果**\n")

            verdict_colors = {
                "true": "green",
                "mostly_true": "lightgreen",
                "unverified": "gray",
                "partly_false": "orange",
                "false": "red",
                "misleading": "darkred",
            }
            color = verdict_colors.get(result.verdict.value, "black")

            self.rumor_result.append(f"<span style='color: {color}'>判定: {result.verdict.value}</span>")
            self.rumor_result.append(f"置信度: {result.confidence:.2f}")
            self.rumor_result.append(f"真实性评分: {result.truth_score:.2f}")
            self.rumor_result.append("")
            self.rumor_result.append(f"**摘要**: {result.analysis_summary}")

            if result.evidence_for:
                self.rumor_result.append("\n**支持证据**:")
                for e in result.evidence_for:
                    self.rumor_result.append(f"- {e}")

            if result.evidence_against:
                self.rumor_result.append("\n**反驳证据**:")
                for e in result.evidence_against:
                    self.rumor_result.append(f"- {e}")

            self.status_bar.showMessage("检测完成")

        except Exception as e:
            logger.error(f"检测失败: {e}")
            self.status_bar.showMessage(f"检测失败: {e}")

    # ==================== 预警标签页 ====================

    def _create_alert_tab(self) -> QWidget:
        """预警标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计
        stats_box = QGroupBox("预警统计")
        stats_layout = QGridLayout(stats_box)

        self.alert_total = QLabel("0")
        stats_layout.addWidget(QLabel("总数:"), 0, 0)
        stats_layout.addWidget(self.alert_total, 0, 1)

        self.alert_critical = QLabel("0")
        stats_layout.addWidget(QLabel("紧急:"), 0, 2)
        stats_layout.addWidget(self.alert_critical, 0, 3)

        self.alert_high = QLabel("0")
        stats_layout.addWidget(QLabel("高:"), 0, 4)
        stats_layout.addWidget(self.alert_high, 0, 5)

        layout.addWidget(stats_box)

        # 预警列表
        list_box = QGroupBox("预警记录")
        list_layout = QVBoxLayout(list_box)

        self.alert_table = QTableWidget()
        self.alert_table.setColumns(5)
        self.alert_table.setHeaders(["时间", "级别", "标题", "来源", "状态"])
        self.alert_table.setColumnWidth(0, 150)
        self.alert_table.setColumnWidth(1, 60)
        self.alert_table.setColumnWidth(2, 200)
        self.alert_table.setColumnWidth(3, 80)
        self.alert_table.setColumnWidth(4, 60)
        list_layout.addWidget(self.alert_table)

        # 刷新按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._on_refresh_alerts)
        btn_layout.addWidget(refresh_btn)
        list_layout.addLayout(btn_layout)

        layout.addWidget(list_box)

        return tab

    @pyqtSlot()
    def _on_refresh_alerts(self):
        """刷新预警"""
        self._refresh_alert_table()

    def _refresh_alert_table(self):
        """刷新预警表格"""
        if not self.hub:
            return

        alerts = self.hub.get_recent_alerts()
        self.alert_table.setRowCount(len(alerts))

        for i, alert in enumerate(alerts):
            self.alert_table.setItem(i, 0, QTableWidgetItem(alert["created_at"][:19]))
            self.alert_table.setItem(i, 1, QTableWidgetItem(alert["level"]))
            self.alert_table.setItem(i, 2, QTableWidgetItem(alert["title"]))
            self.alert_table.setItem(i, 3, QTableWidgetItem(alert["source_type"]))
            self.alert_table.setItem(i, 4, QTableWidgetItem(alert["status"]))

        # 更新统计
        stats = self.hub.get_alert_stats()
        self.alert_total.setText(str(stats.get("total", 0)))

        by_level = stats.get("by_level", {})
        self.alert_critical.setText(str(by_level.get("CRITICAL", 0)))
        self.alert_high.setText(str(by_level.get("HIGH", 0)))

    # ==================== 报告标签页 ====================

    def _create_report_tab(self) -> QWidget:
        """报告标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 生成报告
        gen_box = QGroupBox("生成报告")
        gen_layout = QFormLayout(gen_box)

        self.report_title = QLineEdit()
        self.report_title.setText(f"竞品监控报告 {datetime.now().strftime('%Y-%m-%d')}")
        gen_layout.addRow("标题:", self.report_title)

        self.report_type = QComboBox()
        self.report_type.addItems(["日报", "周报", "预警报告", "专题报告"])
        gen_layout.addRow("类型:", self.report_type)

        self.report_format = QComboBox()
        self.report_format.addItems(["Markdown", "HTML"])
        gen_layout.addRow("格式:", self.report_format)

        gen_btn = QPushButton("生成报告")
        gen_btn.clicked.connect(self._on_generate_report)
        gen_layout.addRow("", gen_btn)

        layout.addWidget(gen_box)

        # 报告预览
        preview_box = QGroupBox("报告预览")
        preview_layout = QVBoxLayout(preview_box)

        self.report_preview = QTextBrowser()
        preview_layout.addWidget(self.report_preview)

        layout.addWidget(preview_box)

        return tab

    @pyqtSlot()
    def _on_generate_report(self):
        """生成报告"""
        title = self.report_title.text().strip()
        if not title:
            title = f"报告 {datetime.now().strftime('%Y-%m-%d')}"

        asyncio.create_task(self._generate_report_async(title))

    async def _generate_report_async(self, title: str):
        """异步生成报告"""
        try:
            if not self.hub:
                from core.intelligence_center import get_intelligence_hub
                self.hub = get_intelligence_hub()

            self.status_bar.showMessage("正在生成报告...")

            from core.intelligence_center import ReportType

            type_map = {
                "日报": ReportType.DAILY,
                "周报": ReportType.WEEKLY,
                "预警报告": ReportType.ALERT,
                "专题报告": ReportType.SPECIAL,
            }

            report = await self.hub.generate_daily_report()

            # 预览
            from core.intelligence_center import ReportGenerator
            gen = ReportGenerator()
            md_content = gen.render_markdown(report)

            self.report_preview.clear()
            self.report_preview.setMarkdown(md_content)

            self.status_bar.showMessage(f"报告已生成: {report.output_path}")

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            self.status_bar.showMessage(f"生成失败: {e}")

    # ==================== 通用方法 ====================

    @pyqtSlot()
    def _on_refresh(self):
        """刷新"""
        self.status_bar.showMessage("刷新中...")
        # 根据当前标签页刷新
        current_tab = self.tabs.currentIndex()
        if current_tab == 1:  # 竞品
            self._refresh_competitor_table()
        elif current_tab == 3:  # 预警
            self._refresh_alert_table()

        self.status_bar.showMessage("就绪")


def create_intelligence_panel(parent=None) -> QWidget:
    """创建情报中心面板"""
    return IntelligencePanel(parent)


__all__ = ["IntelligencePanel", "create_intelligence_panel"]