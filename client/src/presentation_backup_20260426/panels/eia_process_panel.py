"""
环评工艺面板 (EIA Process Panel)
================================

PyQt6 UI for 环评工艺智能体系统

作者：Hermes Desktop AI Team
"""

import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QComboBox, QLineEdit, QProgressBar,
    QListWidget, QListWidgetItem, QTextBrowser, QSplitter,
    QCheckBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class EIAWorker(QThread):
    """后台工作线程"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, manager, raw_input: str, project_name: str = ""):
        super().__init__()
        self.manager = manager
        self.raw_input = raw_input
        self.project_name = project_name

    def run(self):
        try:
            result = self.manager.generate(
                self.raw_input,
                self.project_name,
                progress_callback=lambda p, m: self.progress.emit(p, m)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class EIAProcessPanel(QWidget):
    """
    环评工艺面板

    功能：
    1. 工艺输入与解析
    2. 完整报告生成
    3. 流程图展示
    4. 污染物表格
    5. 防治措施
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.worker = None
        self.current_report = None
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🏭 环评工艺智能体系统")
        title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：输入面板
        left_widget = self._create_input_panel()
        splitter.addWidget(left_widget)

        # 中间：结果面板
        center_widget = self._create_result_panel()
        splitter.addWidget(center_widget)

        # 右侧：图表面板
        right_widget = self._create_graphics_panel()
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter)

    def _create_input_panel(self) -> QWidget:
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入组
        input_group = QGroupBox("📝 工艺输入")
        input_layout = QVBoxLayout()

        # 项目名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("项目名称:"))
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("可选")
        name_layout.addWidget(self.project_name_input)
        input_layout.addLayout(name_layout)

        # 工艺输入
        self.process_input = QTextEdit()
        self.process_input.setPlaceholderText("输入工艺流程，用顿号分隔\n例如: 上料、喷砂、打磨、喷漆、流平、固化、冷却、检验、包装")
        self.process_input.setMaximumHeight(120)
        input_layout.addWidget(QLabel("工艺流程 (用顿号分隔):"))
        input_layout.addWidget(self.process_input)

        # 快速模板
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("快速模板:"))
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "自定义输入",
            "金属喷砂+喷漆",
            "金属磷化+涂装",
            "焊接加工",
            "机械加工",
            "铸造",
        ])
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        template_layout.addWidget(self.template_combo)
        input_layout.addLayout(template_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 选项组
        options_group = QGroupBox("⚙️ 生成选项")
        options_layout = QVBoxLayout()

        self.include_graphics_cb = QCheckBox("生成流程图")
        self.include_graphics_cb.setChecked(True)
        options_layout.addWidget(self.include_graphics_cb)

        self.include_mitigation_cb = QCheckBox("包含防治措施")
        self.include_mitigation_cb.setChecked(True)
        options_layout.addWidget(self.include_mitigation_cb)

        self.include_risk_cb = QCheckBox("风险评估")
        self.include_risk_cb.setChecked(True)
        options_layout.addWidget(self.include_risk_cb)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)

        # 按钮
        button_layout = QHBoxLayout()

        self.generate_btn = QPushButton("🚀 一键生成")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        button_layout.addWidget(self.generate_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        # 解析预览
        preview_group = QGroupBox("👁️ 解析预览")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextBrowser()
        self.preview_text.setMaximumHeight(100)
        preview_layout.addWidget(self.preview_text)

        self.parse_btn = QPushButton("预览解析")
        self.parse_btn.clicked.connect(self._on_preview_parse)
        preview_layout.addWidget(self.parse_btn)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()

        return widget

    def _create_result_panel(self) -> QWidget:
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 标签页
        self.result_tabs = QTabWidget()

        # 工艺流程页
        process_tab = QWidget()
        process_layout = QVBoxLayout(process_tab)

        self.process_table = QTableWidget()
        self.process_table.setColumns(["序号", "工序名称", "是否原始", "参数"])
        process_layout.addWidget(self.process_table)

        self.result_tabs.addTab(process_tab, "📋 工艺流程")

        # 污染物页
        pollutant_tab = QWidget()
        pollutant_layout = QVBoxLayout(pollutant_tab)

        # 废气
        pollutant_layout.addWidget(QLabel("🌬️ 废气污染物"))
        self.air_table = QTableWidget()
        self.air_table.setColumns(["序号", "污染物", "产生量", "排放标准", "控制措施"])
        pollutant_layout.addWidget(self.air_table)

        # 废水
        pollutant_layout.addWidget(QLabel("💧 废水污染物"))
        self.water_table = QTableWidget()
        self.water_table.setColumns(["序号", "污染物", "产生量", "排放标准"])
        pollutant_layout.addWidget(self.water_table)

        # 固废
        pollutant_layout.addWidget(QLabel("🗑️ 固体废物"))
        self.solid_table = QTableWidget()
        self.solid_table.setColumns(["序号", "废物名称", "产生量", "属性", "处置措施"])
        pollutant_layout.addWidget(self.solid_table)

        self.result_tabs.addTab(pollutant_tab, "☢️ 污染物")

        # 防治措施页
        mitigation_tab = QWidget()
        mitigation_layout = QVBoxLayout(mitigation_tab)

        self.mitigation_table = QTableWidget()
        self.mitigation_table.setColumns(["类型", "措施", "去除效率", "投资估算"])
        mitigation_layout.addWidget(self.mitigation_table)

        self.result_tabs.addTab(mitigation_tab, "🛡️ 防治措施")

        # 风险评估页
        risk_tab = QWidget()
        risk_layout = QVLayout(risk_tab)

        self.risk_text = QTextBrowser()
        risk_layout.addWidget(self.risk_text)

        self.result_tabs.addTab(risk_tab, "⚠️ 风险评估")

        # 完整报告页
        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        report_layout.addWidget(self.report_text)

        button_layout = QHBoxLayout()
        self.export_md_btn = QPushButton("导出 Markdown")
        self.export_md_btn.clicked.connect(self._on_export_md)
        button_layout.addWidget(self.export_md_btn)

        self.export_json_btn = QPushButton("导出 JSON")
        self.export_json_btn.clicked.connect(self._on_export_json)
        button_layout.addWidget(self.export_json_btn)

        report_layout.addLayout(button_layout)

        self.result_tabs.addTab(report_tab, "📄 完整报告")

        layout.addWidget(self.result_tabs)

        return widget

    def _create_graphics_panel(self) -> QWidget:
        """创建图表面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 标题
        title = QLabel("📊 流程图预览")
        title.setFont(QFont("微软雅黑", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # Mermaid 流程图
        self.flowchart_browser = QTextBrowser()
        self.flowchart_browser.setOpenExternalLinks(True)
        layout.addWidget(QLabel("工艺流程图:"))
        layout.addWidget(self.flowchart_browser)

        # 污染物图
        self.pollutant_browser = QTextBrowser()
        layout.addWidget(QLabel("污染物排放图:"))
        layout.addWidget(self.pollutant_browser)

        # 防治措施图
        self.mitigation_browser = QTextBrowser()
        layout.addWidget(QLabel("防治措施图:"))
        layout.addWidget(self.mitigation_browser)

        return widget

    def set_manager(self, manager):
        """设置管理器"""
        self.manager = manager
        logger.info("环评工艺面板已绑定管理器")

    def _on_template_selected(self, template: str):
        """选择模板"""
        templates = {
            "金属喷砂+喷漆": "上料、喷砂、清洁、干燥、喷漆、流平、固化、冷却、检验、包装",
            "金属磷化+涂装": "上料、除油、水洗、除锈、水洗、表调、磷化、水洗、纯水洗、干燥、喷漆、流平、固化、冷却、检验、包装",
            "焊接加工": "上料、下料、焊接、打磨、检验、包装",
            "机械加工": "上料、下料、车削、铣削、磨削、检验、包装",
            "铸造": "上料、熔炼、浇注、造型、清砂、退火、检验、包装",
        }

        if template in templates:
            self.process_input.setText(templates[template])

    def _on_preview_parse(self):
        """预览解析"""
        if not self.manager:
            return

        raw_input = self.process_input.toPlainText().strip()
        if not raw_input:
            return

        try:
            result = self.manager.parse_process(raw_input)

            preview_lines = [
                f"**原始输入**: {result.get('raw_input', '')}",
                f"**解析工序**: {', '.join(result.get('standard_steps', []))}",
                f"**工艺类型**: {result.get('process_type', '')}",
                f"**行业**: {result.get('industry', '')}",
                f"**复杂度**: {result.get('complexity', '')}",
                f"**置信度**: {result.get('confidence', 0):.2%}",
                "",
                "**缺失环节**:",
            ]

            for step in result.get('missing_pre_steps', []):
                preview_lines.append(f"  - 前处理: {step}")
            for step in result.get('missing_post_steps', []):
                preview_lines.append(f"  - 后处理: {step}")

            preview_lines.extend([
                "",
                "**风险工序**:",
                f"  - 高污染: {', '.join(result.get('high_pollution_steps', []))}",
                f"  - 高能耗: {', '.join(result.get('high_energy_steps', []))}",
                f"  - 安全风险: {', '.join(result.get('safety_risk_steps', []))}",
            ])

            self.preview_text.setMarkdown("\n".join(preview_lines))

        except Exception as e:
            logger.error(f"预览解析失败: {e}")
            self.preview_text.setPlainText(f"解析失败: {e}")

    def _on_generate(self):
        """生成报告"""
        if not self.manager:
            logger.error("管理器未设置")
            return

        raw_input = self.process_input.toPlainText().strip()
        if not raw_input:
            logger.warning("请输入工艺流程")
            return

        # 禁用按钮
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备生成...")

        # 启动后台任务
        project_name = self.project_name_input.text().strip()
        self.worker = EIAWorker(self.manager, raw_input, project_name)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, step: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(step * 20)
        self.progress_label.setText(message)

    def _on_finished(self, result: Dict):
        """生成完成"""
        self.progress_bar.setValue(100)
        self.progress_label.setText("生成完成!")
        self.generate_btn.setEnabled(True)

        if "error" in result:
            logger.error(f"生成失败: {result['error']}")
            return

        self.current_report = result
        self._display_result(result)

    def _on_error(self, error: str):
        """错误处理"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.progress_label.setText(f"错误: {error}")
        logger.error(f"生成错误: {error}")

    def _display_result(self, report: Dict):
        """显示结果"""
        # 工艺流程表
        self._update_process_table(report)

        # 污染物表
        self._update_pollutant_tables(report)

        # 防治措施表
        self._update_mitigation_table(report)

        # 风险评估
        self._update_risk_text(report)

        # 完整报告
        self._update_report_text(report)

        # 流程图
        self._update_graphics(report)

    def _update_process_table(self, report: Dict):
        """更新工艺流程表"""
        steps = report.get("process_steps", [])
        self.process_table.setRowCount(len(steps))

        for i, step in enumerate(steps):
            self.process_table.setItem(i, 0, QTableWidgetItem(str(step.get("序号", i + 1))))
            self.process_table.setItem(i, 1, QTableWidgetItem(step.get("工序名称", "")))
            self.process_table.setItem(i, 2, QTableWidgetItem(step.get("是否原始", "")))

            params = step.get("参数", {})
            param_str = ", ".join([f"{k}: {v}" for k, v in params.items()]) if params else ""
            self.process_table.setItem(i, 3, QTableWidgetItem(param_str))

    def _update_pollutant_tables(self, report: Dict):
        """更新污染物表"""
        # 废气
        air = report.get("air_pollutants", [])
        self.air_table.setRowCount(len(air))
        for i, p in enumerate(air):
            self.air_table.setItem(i, 0, QTableWidgetItem(str(p.get("序号", ""))))
            self.air_table.setItem(i, 1, QTableWidgetItem(p.get("污染物名称", "")))
            self.air_table.setItem(i, 2, QTableWidgetItem(p.get("产生量", "")))
            self.air_table.setItem(i, 3, QTableWidgetItem(p.get("排放标准", "")))
            self.air_table.setItem(i, 4, QTableWidgetItem(p.get("控制措施", "")))

        # 废水
        water = report.get("water_pollutants", [])
        self.water_table.setRowCount(len(water))
        for i, p in enumerate(water):
            self.water_table.setItem(i, 0, QTableWidgetItem(str(p.get("序号", ""))))
            self.water_table.setItem(i, 1, QTableWidgetItem(p.get("污染物名称", "")))
            self.water_table.setItem(i, 2, QTableWidgetItem(p.get("产生量", "")))
            self.water_table.setItem(i, 3, QTableWidgetItem(p.get("排放标准", "")))

        # 固废
        solid = report.get("solid_wastes", [])
        self.solid_table.setRowCount(len(solid))
        for i, p in enumerate(solid):
            self.solid_table.setItem(i, 0, QTableWidgetItem(str(p.get("序号", ""))))
            self.solid_table.setItem(i, 1, QTableWidgetItem(p.get("废物名称", "")))
            self.solid_table.setItem(i, 2, QTableWidgetItem(p.get("产生量", "")))
            self.solid_table.setItem(i, 3, QTableWidgetItem(p.get("属性", "")))
            self.solid_table.setItem(i, 4, QTableWidgetItem(p.get("处置措施", "")))

    def _update_mitigation_table(self, report: Dict):
        """更新防治措施表"""
        measures = report.get("mitigation_measures", [])
        self.mitigation_table.setRowCount(len(measures))

        for i, m in enumerate(measures):
            self.mitigation_table.setItem(i, 0, QTableWidgetItem(m.get("类型", "")))
            self.mitigation_table.setItem(i, 1, QTableWidgetItem(m.get("措施", "")))
            self.mitigation_table.setItem(i, 2, QTableWidgetItem(m.get("去除效率", "")))
            self.mitigation_table.setItem(i, 3, QTableWidgetItem(m.get("投资估算", "")))

    def _update_risk_text(self, report: Dict):
        """更新风险评估"""
        ra = report.get("risk_assessment", {})

        lines = [
            f"## 风险评估结果\n",
            f"**风险等级**: {ra.get('风险等级', '未知')}\n",
        ]

        if ra.get("重大风险源"):
            lines.append("\n### 重大风险源")
            for risk in ra["重大风险源"]:
                lines.append(f"- {risk}")

        if ra.get("一般风险"):
            lines.append("\n### 一般风险")
            for risk in ra["一般风险"]:
                lines.append(f"- {risk}")

        self.risk_text.setMarkdown("\n".join(lines))

    def _update_report_text(self, report: Dict):
        """更新完整报告"""
        if self.manager:
            md = self.manager.export_report(report, "markdown")
            self.report_text.setMarkdown(md)

    def _update_graphics(self, report: Dict):
        """更新流程图"""
        graphics = report.get("graphics", {})

        # 工艺流程图
        flowchart = graphics.get("process_flowchart", "")
        if flowchart:
            self.flowchart_browser.setMarkdown(f"```mermaid\n{flowchart}\n```")

        # 污染物图
        pollutant = graphics.get("pollutant_flowchart", "")
        if pollutant:
            self.pollutant_browser.setMarkdown(f"```mermaid\n{pollutant}\n```")

        # 防治措施图
        mitigation = graphics.get("mitigation_flowchart", "")
        if mitigation:
            self.mitigation_browser.setMarkdown(f"```mermaid\n{mitigation}\n```")

    def _on_export_md(self):
        """导出Markdown"""
        if not self.current_report or not self.manager:
            return

        md = self.manager.export_report(self.current_report, "markdown")

        # 保存文件
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown", "", "Markdown (*.md)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md)
                logger.info(f"已导出Markdown: {path}")
            except Exception as e:
                logger.error(f"导出失败: {e}")

    def _on_export_json(self):
        """导出JSON"""
        if not self.current_report or not self.manager:
            return

        json_str = self.manager.export_report(self.current_report, "json")

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 JSON", "", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(json_str)
                logger.info(f"已导出JSON: {path}")
            except Exception as e:
                logger.error(f"导出失败: {e}")

    def _on_clear(self):
        """清空"""
        self.process_input.clear()
        self.project_name_input.clear()
        self.preview_text.clear()
        self.progress_bar.setVisible(False)
        self.progress_label.clear()
        self.current_report = None

        # 清空表格
        self.process_table.setRowCount(0)
        self.air_table.setRowCount(0)
        self.water_table.setRowCount(0)
        self.solid_table.setRowCount(0)
        self.mitigation_table.setRowCount(0)
        self.risk_text.clear()
        self.report_text.clear()

        # 清空图表
        self.flowchart_browser.clear()
        self.pollutant_browser.clear()
        self.mitigation_browser.clear()


# 表格列配置
QTableWidget.setColumns = lambda self, cols: self.setColumnCount(len(cols)) or self.setHorizontalHeaderLabels(cols)
