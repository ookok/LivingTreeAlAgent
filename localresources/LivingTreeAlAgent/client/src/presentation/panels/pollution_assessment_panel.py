# -*- coding: utf-8 -*-
"""
场地污染源调查与环境评估报告 UI 面板
Pollution Assessment Report Panel
==========================================

功能：
- 污染源调查数据录入
- 环境评估参数配置
- 报告生成与管理
- 检测结果录入
- 超标分析可视化

Author: Hermes Desktop Team
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import QFont, QIcon, QAction, QColor

from core.doc_lifecycle.pollution_assessment_report import (
    PollutionAssessmentReportGenerator,
    PollutionAssessmentReportData,
    PollutionSource,
    SamplingPoint,
    Sample,
    MediaType,
    PollutionLevel,
    AssessmentReportFormat,
    create_pollution_assessment_report,
    add_pollution_source,
    add_sampling_point,
)


class PollutionSourceDialog(QDialog):
    """污染源信息录入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加污染源")
        self.setMinimumSize(500, 400)
        self._init_ui()
        self.source_data = None

    def _init_ui(self):
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["工业", "农业", "生活", "交通", "储罐", "管网", "堆场", "其他"])
        self.location_edit = QLineEdit()
        self.contaminants_edit = QLineEdit()
        self.contaminants_edit.setPlaceholderText("污染物1, 污染物2, ...")
        self.status_combo = QComboBox()
        self.status_combo.addItems(["在产", "停产", "关闭", "废弃"])
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(["高", "中", "低"])
        self.emission_mode_edit = QLineEdit()
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(80)

        layout.addRow("污染源名称 *", self.name_edit)
        layout.addRow("类型 *", self.type_combo)
        layout.addRow("位置 *", self.location_edit)
        layout.addRow("主要污染物 *", self.contaminants_edit)
        layout.addRow("生产状态", self.status_combo)
        layout.addRow("风险等级", self.risk_combo)
        layout.addRow("排放方式", self.emission_mode_edit)
        layout.addRow("备注", self.remarks_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_ok(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入污染源名称")
            return
        if not self.location_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入污染源位置")
            return
        if not self.contaminants_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入主要污染物")
            return

        contaminants = [c.strip() for c in self.contaminants_edit.text().split(",") if c.strip()]

        self.source_data = {
            "source_name": self.name_edit.text().strip(),
            "source_type": self.type_combo.currentText(),
            "location": self.location_edit.text().strip(),
            "contaminants": contaminants,
            "operation_status": self.status_combo.currentText(),
            "risk_level": self.risk_combo.currentText(),
            "emission_mode": self.emission_mode_edit.text().strip(),
            "remarks": self.remarks_edit.toPlainText().strip(),
        }
        self.accept()


class SamplingPointDialog(QDialog):
    """采样点录入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加采样点")
        self.setMinimumSize(400, 300)
        self._init_ui()
        self.point_data = None

    def _init_ui(self):
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.media_combo = QComboBox()
        self.media_combo.addItems([
            "土壤", "地表水", "地下水", "沉积物", "大气", "噪声"
        ])
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.depth_edit = QLineEdit()
        self.depth_edit.setPlaceholderText("如: 0-0.5m")

        layout.addRow("采样点名称 *", self.name_edit)
        layout.addRow("位置 *", self.location_edit)
        layout.addRow("介质类型 *", self.media_combo)
        layout.addRow("采样日期 *", self.date_edit)
        layout.addRow("采样深度", self.depth_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_ok(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入采样点名称")
            return
        if not self.date_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入采样日期")
            return

        media_map = {
            "土壤": MediaType.SOIL,
            "地表水": MediaType.SURFACE_WATER,
            "地下水": MediaType.GROUNDWATER,
            "沉积物": MediaType.SEDIMENT,
            "大气": MediaType.AIR,
            "噪声": MediaType.NOISE,
        }

        self.point_data = {
            "point_name": self.name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "media_type": media_map.get(self.media_combo.currentText(), MediaType.SOIL),
            "sampling_date": self.date_edit.text().strip(),
            "depth": self.depth_edit.text().strip(),
        }
        self.accept()


class SampleResultDialog(QDialog):
    """样品检测结果录入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加检测结果")
        self.setMinimumSize(450, 350)
        self._init_ui()
        self.sample_data = None

    def _init_ui(self):
        layout = QFormLayout(self)

        self.sample_name_edit = QLineEdit()
        self.parameter_edit = QLineEdit()
        self.value_spin = QSpinBox()
        self.value_spin.setRange(0, 999999)
        self.value_spin.setDecimals(4)
        self.value_spin.setSingleStep(0.001)
        self.value_spin.setSuffix(" mg/L")
        self.unit_edit = QLineEdit()
        self.unit_edit.setText("mg/kg")
        self.standard_spin = QSpinBox()
        self.standard_spin.setRange(0, 999999)
        self.standard_spin.setDecimals(4)
        self.standard_spin.setSingleStep(0.001)
        self.standard_spin.setSuffix(" mg/kg")
        self.method_edit = QLineEdit()

        layout.addRow("样品名称 *", self.sample_name_edit)
        layout.addRow("检测参数 *", self.parameter_edit)
        layout.addRow("检测值 *", self.value_spin)
        layout.addRow("单位 *", self.unit_edit)
        layout.addRow("标准限值 *", self.standard_spin)
        layout.addRow("检测方法", self.method_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_ok(self):
        if not self.sample_name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入样品名称")
            return
        if not self.parameter_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入检测参数")
            return

        self.sample_data = {
            "sample_name": self.sample_name_edit.text().strip(),
            "parameter": self.parameter_edit.text().strip(),
            "value": self.value_spin.value(),
            "unit": self.unit_edit.text().strip(),
            "standard_value": self.standard_spin.value(),
            "detection_method": self.method_edit.text().strip(),
        }
        self.accept()


class ProjectInfoDialog(QDialog):
    """项目基本信息录入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("项目信息")
        self.setMinimumSize(500, 450)
        self._init_ui()
        self.project_data = None

    def _init_ui(self):
        layout = QFormLayout(self)

        self.project_name_edit = QLineEdit()
        self.project_type_edit = QLineEdit()
        self.project_address_edit = QLineEdit()
        self.entrust_unit_edit = QLineEdit()
        self.assessment_unit_edit = QLineEdit()
        self.entrust_contact_edit = QLineEdit()
        self.assessment_license_edit = QLineEdit()
        self.assessment_person_edit = QLineEdit()
        self.report_author_edit = QLineEdit()
        self.area_edit = QLineEdit()
        self.total_investment_edit = QLineEdit()
        self.scale_edit = QLineEdit()

        layout.addRow("项目名称 *", self.project_name_edit)
        layout.addRow("项目地址", self.project_address_edit)
        layout.addRow("项目类别", self.project_type_edit)
        layout.addRow("占地面积", self.area_edit)
        layout.addRow("总投资", self.total_investment_edit)
        layout.addRow("建设规模", self.scale_edit)
        layout.addRow("委托单位 *", self.entrust_unit_edit)
        layout.addRow("委托单位联系人", self.entrust_contact_edit)
        layout.addRow("评估单位 *", self.assessment_unit_edit)
        layout.addRow("评估资质证书号", self.assessment_license_edit)
        layout.addRow("项目负责人", self.assessment_person_edit)
        layout.addRow("报告编制人", self.report_author_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_ok(self):
        if not self.project_name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入项目名称")
            return
        if not self.entrust_unit_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入委托单位")
            return
        if not self.assessment_unit_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入评估单位")
            return

        self.project_data = {
            "project_name": self.project_name_edit.text().strip(),
            "project_address": self.project_address_edit.text().strip(),
            "project_type": self.project_type_edit.text().strip(),
            "area": self.area_edit.text().strip(),
            "total_investment": self.total_investment_edit.text().strip(),
            "construction_scale": self.scale_edit.text().strip(),
            "entrust_unit": self.entrust_unit_edit.text().strip(),
            "entrust_contact": self.entrust_contact_edit.text().strip(),
            "assessment_unit": self.assessment_unit_edit.text().strip(),
            "assessment_license": self.assessment_license_edit.text().strip(),
            "assessment_person": self.assessment_person_edit.text().strip(),
            "report_author": self.report_author_edit.text().strip(),
        }
        self.accept()


class PollutionAssessmentPanel(QWidget):
    """
    场地污染源调查与环境评估报告面板
    """

    # 信号
    report_generated = pyqtSignal(str)  # 报告生成完成信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_data: PollutionAssessmentReportData = None
        self.generator = PollutionAssessmentReportGenerator()
        self._init_ui()
        self._setup_connections()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # ===== 顶部工具栏 =====
        toolbar = QHBoxLayout()

        self.new_report_btn = QPushButton("📄 新建报告")
        self.open_report_btn = QPushButton("📂 打开")
        self.save_report_btn = QPushButton("💾 保存")
        self.generate_btn = QPushButton("📑 生成报告")
        self.generate_btn.setStyleSheet("QPushButton { background-color: #1a5f7a; color: white; font-weight: bold; }")

        toolbar.addWidget(self.new_report_btn)
        toolbar.addWidget(self.open_report_btn)
        toolbar.addWidget(self.save_report_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.generate_btn)

        main_layout.addLayout(toolbar)

        # ===== 主内容区 =====
        content = QHBoxLayout()

        # 左侧导航
        nav_panel = QFrame()
        nav_panel.setFrameShape(QFrame.Shape.StyledPanel)
        nav_layout = QVBoxLayout(nav_panel)

        nav_label = QLabel("📋 报告内容")
        nav_label.setFont(QFont("", 10, QFont.Weight.Bold))
        nav_layout.addWidget(nav_label)

        self.nav_list = QListWidget()
        self.nav_list.addItems([
            "📌 基本信息",
            "🏭 污染源清单",
            "📍 采样点",
            "🧪 检测结果",
            "📊 污染评估",
            "🌿 环境质量",
            "📝 报告预览",
        ])
        self.nav_list.setCurrentRow(0)
        nav_layout.addWidget(self.nav_list)
        nav_layout.addStretch()

        content.addWidget(nav_panel, 1)

        # 右侧内容区
        self.content_stack = QStackedWidget()
        content.addWidget(self.content_stack, 4)

        # 各个页面
        self.content_stack.addWidget(self._create_basic_info_page())
        self.content_stack.addWidget(self._create_pollution_source_page())
        self.content_stack.addWidget(self._create_sampling_point_page())
        self.content_stack.addWidget(self._create_detection_result_page())
        self.content_stack.addWidget(self._create_pollution_assessment_page())
        self.content_stack.addWidget(self._create_env_quality_page())
        self.content_stack.addWidget(self._create_preview_page())

        content.addLayout(content)

        main_layout.addLayout(content, 1)

        # ===== 底部状态栏 =====
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        main_layout.addLayout(status_layout)

    def _create_basic_info_page(self) -> QWidget:
        """创建基本信息页面"""
        page = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 项目信息卡片
        info_group = QGroupBox("项目基本信息")
        info_layout = QFormLayout()

        self.project_name_label = QLabel("-")
        self.project_address_label = QLabel("-")
        self.entrust_unit_label = QLabel("-")
        self.assessment_unit_label = QLabel("-")
        self.area_label = QLabel("-")
        self.investment_label = QLabel("-")

        info_layout.addRow("项目名称:", self.project_name_label)
        info_layout.addRow("项目地址:", self.project_address_label)
        info_layout.addRow("委托单位:", self.entrust_unit_label)
        info_layout.addRow("评估单位:", self.assessment_unit_label)
        info_layout.addRow("占地面积:", self.area_label)
        info_layout.addRow("总投资:", self.investment_label)

        edit_btn = QPushButton("编辑项目信息")
        edit_btn.clicked.connect(self._edit_project_info)
        info_layout.addRow("", edit_btn)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 统计卡片
        stats_group = QGroupBox("数据统计")
        stats_layout = QGridLayout()

        self.source_count_label = QLabel("0")
        self.sampling_count_label = QLabel("0")
        self.sample_count_label = QLabel("0")
        self.exceed_count_label = QLabel("0")

        stats_layout.addWidget(QLabel("污染源数量:"), 0, 0)
        stats_layout.addWidget(self.source_count_label, 0, 1)
        stats_layout.addWidget(QLabel("采样点数量:"), 0, 2)
        stats_layout.addWidget(self.sampling_count_label, 0, 3)
        stats_layout.addWidget(QLabel("检测样品:"), 1, 0)
        stats_layout.addWidget(self.sample_count_label, 1, 1)
        stats_layout.addWidget(QLabel("超标样品:"), 1, 2)
        stats_layout.addWidget(self.exceed_count_label, 1, 3)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        layout.addStretch()
        page.setWidget(widget)
        page.setWidgetResizable(True)
        return page

    def _create_pollution_source_page(self) -> QWidget:
        """创建污染源清单页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QPushButton("➕ 添加污染源"))
        toolbar[0].clicked.connect(self._add_pollution_source)
        toolbar.addStretch()

        self.source_table = QTableWidget()
        self.source_table.setColumnCount(7)
        self.source_table.setHorizontalHeaderLabels(["编号", "名称", "类型", "位置", "状态", "风险", "污染物"])
        self.source_table.setColumnWidth(0, 60)
        self.source_table.setColumnWidth(1, 150)
        self.source_table.setColumnWidth(2, 80)
        self.source_table.setColumnWidth(3, 150)
        self.source_table.setColumnWidth(4, 80)
        self.source_table.setColumnWidth(5, 60)
        self.source_table.setColumnWidth(6, 200)

        layout.addLayout(toolbar)
        layout.addWidget(self.source_table)
        return page

    def _create_sampling_point_page(self) -> QWidget:
        """创建采样点页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("➕ 添加采样点")
        add_btn.clicked.connect(self._add_sampling_point)
        toolbar.addWidget(add_btn)
        toolbar.addStretch()

        self.sampling_table = QTableWidget()
        self.sampling_table.setColumnCount(6)
        self.sampling_table.setHorizontalHeaderLabels(["编号", "名称", "位置", "介质", "日期", "深度"])
        self.sampling_table.setColumnWidth(0, 60)
        self.sampling_table.setColumnWidth(1, 150)
        self.sampling_table.setColumnWidth(2, 150)
        self.sampling_table.setColumnWidth(3, 80)
        self.sampling_table.setColumnWidth(4, 100)
        self.sampling_table.setColumnWidth(5, 80)

        layout.addLayout(toolbar)
        layout.addWidget(self.sampling_table)
        return page

    def _create_detection_result_page(self) -> QWidget:
        """创建检测结果页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        self.sampling_point_combo = QComboBox()
        toolbar.addWidget(QLabel("采样点:"))
        toolbar.addWidget(self.sampling_point_combo)
        add_btn = QPushButton("➕ 添加检测结果")
        add_btn.clicked.connect(self._add_detection_result)
        toolbar.addWidget(add_btn)
        toolbar.addStretch()

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(7)
        self.result_table.setHorizontalHeaderLabels(["样品", "参数", "检测值", "单位", "标准值", "超标倍数", "超标"])
        for i, w in enumerate([80, 120, 80, 60, 80, 80, 50]):
            self.result_table.setColumnWidth(i, w)

        layout.addLayout(toolbar)
        layout.addWidget(self.result_table)
        return page

    def _create_pollution_assessment_page(self) -> QWidget:
        """创建污染评估页面"""
        page = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 污染评估汇总
        assess_group = QGroupBox("污染评估结果汇总")
        assess_layout = QGridLayout()

        self.assess_soils_label = QLabel("-")
        self.assess_water_label = QLabel("-")
        self.assess_groundwater_label = QLabel("-")
        self.assess_air_label = QLabel("-")

        assess_layout.addWidget(QLabel("土壤污染:"), 0, 0)
        assess_layout.addWidget(self.assess_soils_label, 0, 1)
        assess_layout.addWidget(QLabel("地表水污染:"), 0, 2)
        assess_layout.addWidget(self.assess_water_label, 0, 3)
        assess_layout.addWidget(QLabel("地下水污染:"), 1, 0)
        assess_layout.addWidget(self.assess_groundwater_label, 1, 1)
        assess_layout.addWidget(QLabel("大气环境:"), 1, 2)
        assess_layout.addWidget(self.assess_air_label, 1, 3)

        assess_group.setLayout(assess_layout)
        layout.addWidget(assess_group)

        # 超标分析
        exceed_group = QGroupBox("超标参数分析")
        exceed_layout = QFormLayout()
        self.exceed_summary = QTextEdit()
        self.exceed_summary.setReadOnly(True)
        exceed_layout.addRow(self.exceed_summary)
        exceed_group.setLayout(exceed_layout)
        layout.addWidget(exceed_group)

        layout.addStretch()
        page.setWidget(widget)
        page.setWidgetResizable(True)
        return page

    def _create_env_quality_page(self) -> QWidget:
        """创建环境质量页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        tabs = QTabWidget()

        # 大气环境
        air_tab = QWidget()
        air_layout = QFormLayout(air_tab)
        air_layout.addRow("监测日期:", QLineEdit())
        air_layout.addRow("监测点位:", QLineEdit())
        air_layout.addRow("执行标准:", QLineEdit())
        air_layout.addRow("达标情况:", QComboBox())
        tabs.addTab(air_tab, "🌬️ 大气环境")

        # 水环境
        water_tab = QWidget()
        water_layout = QFormLayout(water_tab)
        water_layout.addRow("监测日期:", QLineEdit())
        water_layout.addRow("监测点位:", QLineEdit())
        water_layout.addRow("执行标准:", QLineEdit())
        water_layout.addRow("达标情况:", QComboBox())
        tabs.addTab(water_tab, "💧 水环境")

        # 土壤环境
        soil_tab = QWidget()
        soil_layout = QFormLayout(soil_tab)
        soil_layout.addRow("监测日期:", QLineEdit())
        soil_layout.addRow("监测点位:", QLineEdit())
        soil_layout.addRow("执行标准:", QLineEdit())
        soil_layout.addRow("达标情况:", QComboBox())
        tabs.addTab(soil_tab, "🌍 土壤环境")

        # 声环境
        noise_tab = QWidget()
        noise_layout = QFormLayout(noise_tab)
        noise_layout.addRow("监测日期:", QLineEdit())
        noise_layout.addRow("监测点位:", QLineEdit())
        noise_layout.addRow("执行标准:", QLineEdit())
        noise_layout.addRow("达标情况:", QComboBox())
        tabs.addTab(noise_tab, "🔊 声环境")

        layout.addWidget(tabs)
        return page

    def _create_preview_page(self) -> QWidget:
        """创建报告预览页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("报告预览"))
        toolbar.addStretch()

        format_combo = QComboBox()
        format_combo.addItems(["HTML 预览", "Markdown 原文", "DOCX 报告", "PDF 报告"])
        toolbar.addWidget(QLabel("格式:"))
        toolbar.addWidget(format_combo)

        refresh_btn = QPushButton("🔄 刷新预览")
        toolbar.addWidget(refresh_btn)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)

        layout.addLayout(toolbar)
        layout.addWidget(self.preview_text)
        return page

    def _setup_connections(self):
        """设置信号连接"""
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.new_report_btn.clicked.connect(self._new_report)
        self.generate_btn.clicked.connect(self._generate_report)

    def _edit_project_info(self):
        """编辑项目信息"""
        dialog = ProjectInfoDialog(self)
        if dialog.exec():
            data = dialog.project_data
            self._create_or_update_report_data(
                project_name=data["project_name"],
                project_address=data.get("project_address", ""),
                area=data.get("area", ""),
                total_investment=data.get("total_investment", ""),
                entrust_unit=data["entrust_unit"],
                assessment_unit=data["assessment_unit"],
                assessment_person=data.get("assessment_person", ""),
                report_author=data.get("report_author", ""),
            )
            self._update_basic_info_display()

    def _add_pollution_source(self):
        """添加污染源"""
        if not self.report_data:
            QMessageBox.warning(self, "提示", "请先创建或打开报告")
            return

        dialog = PollutionSourceDialog(self)
        if dialog.exec():
            source = self.generator.add_pollution_source(
                self.report_data,
                **dialog.source_data
            )
            self._update_pollution_source_table()
            self._update_stats()
            self.status_label.setText(f"已添加污染源: {source.source_name}")

    def _add_sampling_point(self):
        """添加采样点"""
        if not self.report_data:
            QMessageBox.warning(self, "提示", "请先创建或打开报告")
            return

        dialog = SamplingPointDialog(self)
        if dialog.exec():
            point = self.generator.add_sampling_point(
                self.report_data,
                **dialog.point_data
            )
            self._update_sampling_point_table()
            self._update_stats()
            self.status_label.setText(f"已添加采样点: {point.point_name}")

    def _add_detection_result(self):
        """添加检测结果"""
        if not self.report_data or not self.report_data.sampling_points:
            QMessageBox.warning(self, "提示", "请先添加采样点")
            return

        dialog = SampleResultDialog(self)
        if dialog.exec():
            current_point = self.report_data.sampling_points[-1]
            self.generator.add_sample(
                current_point,
                **dialog.sample_data
            )
            self._update_detection_result_table()
            self._update_assessment_display()
            self._update_stats()

    def _new_report(self):
        """新建报告"""
        dialog = ProjectInfoDialog(self)
        if dialog.exec():
            data = dialog.project_data
            self.report_data = self._create_or_update_report_data(
                project_name=data["project_name"],
                project_address=data.get("project_address", ""),
                area=data.get("area", ""),
                total_investment=data.get("total_investment", ""),
                entrust_unit=data["entrust_unit"],
                assessment_unit=data["assessment_unit"],
                assessment_person=data.get("assessment_person", ""),
                report_author=data.get("report_author", ""),
            )
            self._update_basic_info_display()
            self.status_label.setText(f"已创建新报告: {data['project_name']}")

    def _generate_report(self):
        """生成报告"""
        if not self.report_data:
            QMessageBox.warning(self, "提示", "请先创建报告")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not output_dir:
            return

        self.status_label.setText("正在生成报告...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        try:
            output_path = self.generator.generate(
                self.report_data,
                format=AssessmentReportFormat.HTML,
                output_dir=output_dir,
            )
            self.preview_text.setHtml(self.generator._render_html_template(
                self.report_data, "standard"
            ))
            self.status_label.setText(f"报告已生成: {output_path}")
            self.progress_bar.setVisible(False)
            QMessageBox.information(self, "成功", f"报告已生成:\n{output_path}")
        except Exception as e:
            self.status_label.setText(f"生成失败: {str(e)}")
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "错误", f"报告生成失败:\n{str(e)}")

    def _create_or_update_report_data(self, **kwargs) -> PollutionAssessmentReportData:
        """创建或更新报告数据"""
        self.report_data = create_pollution_assessment_report(**kwargs)
        self.report_data.report_cover.report_number = f"PAR-{datetime.now().strftime('%Y%m%d%H%M')}"
        return self.report_data

    def _update_basic_info_display(self):
        """更新基本信息显示"""
        if not self.report_data:
            return

        cover = self.report_data.report_cover
        project = self.report_data.project_info

        self.project_name_label.setText(project.project_name)
        self.project_address_label.setText(project.project_address or "-")
        self.entrust_unit_label.setText(cover.entrust_unit)
        self.assessment_unit_label.setText(cover.assessment_unit)
        self.area_label.setText(project.area or "-")
        self.investment_label.setText(project.total_investment or "-")

    def _update_pollution_source_table(self):
        """更新污染源表格"""
        if not self.report_data:
            return

        sources = self.report_data.pollution_sources
        self.source_table.setRowCount(len(sources))

        for i, src in enumerate(sources):
            self.source_table.setItem(i, 0, QTableWidgetItem(src.source_id))
            self.source_table.setItem(i, 1, QTableWidgetItem(src.source_name))
            self.source_table.setItem(i, 2, QTableWidgetItem(src.source_type))
            self.source_table.setItem(i, 3, QTableWidgetItem(src.location))
            self.source_table.setItem(i, 4, QTableWidgetItem(src.operation_status))
            self.source_table.setItem(i, 5, QTableWidgetItem(src.risk_level))
            self.source_table.setItem(i, 6, QTableWidgetItem(", ".join(src.contaminants)))

    def _update_sampling_point_table(self):
        """更新采样点表格"""
        if not self.report_data:
            return

        points = self.report_data.sampling_points
        self.sampling_table.setRowCount(len(points))

        for i, pt in enumerate(points):
            self.sampling_table.setItem(i, 0, QTableWidgetItem(pt.point_id))
            self.sampling_table.setItem(i, 1, QTableWidgetItem(pt.point_name))
            self.sampling_table.setItem(i, 2, QTableWidgetItem(pt.location))
            self.sampling_table.setItem(i, 3, QTableWidgetItem(pt.media_type.value))
            self.sampling_table.setItem(i, 4, QTableWidgetItem(pt.sampling_date))
            self.sampling_table.setItem(i, 5, QTableWidgetItem(pt.depth))

    def _update_detection_result_table(self):
        """更新检测结果表格"""
        if not self.report_data or not self.report_data.sampling_points:
            return

        all_samples = []
        for pt in self.report_data.sampling_points:
            all_samples.extend(pt.samples)

        self.result_table.setRowCount(len(all_samples))

        for i, sample in enumerate(all_samples):
            exceed = "是" if sample.is_exceeded else "否"
            exceed_ratio = f"{sample.exceedance_ratio:.2f}" if sample.exceedance_ratio > 0 else "-"

            self.result_table.setItem(i, 0, QTableWidgetItem(sample.sample_name))
            self.result_table.setItem(i, 1, QTableWidgetItem(sample.parameter))
            self.result_table.setItem(i, 2, QTableWidgetItem(str(sample.value)))
            self.result_table.setItem(i, 3, QTableWidgetItem(sample.unit))
            self.result_table.setItem(i, 4, QTableWidgetItem(str(sample.standard_value)))
            self.result_table.setItem(i, 5, QTableWidgetItem(exceed_ratio))
            item = QTableWidgetItem(exceed)
            if sample.is_exceeded:
                item.setBackground(QColor(255, 200, 200))
            self.result_table.setItem(i, 6, item)

    def _update_assessment_display(self):
        """更新污染评估显示"""
        if not self.report_data:
            return

        summary = self.generator.generate_exceedance_summary(self.report_data)
        self.exceed_count_label.setText(str(summary["exceeded_samples"]))

        if summary["max_exceedance_ratio"] > 0:
            text = f"""超标样品数: {summary['exceeded_samples']} / {summary['total_samples']}
超标率: {summary['exceedance_rate']*100:.1f}%
最大超标参数: {summary['max_exceeded_parameter']}
最大超标倍数: {summary['max_exceedance_ratio']:.2f}
最大超标点位: {summary['max_exceeded_point']}"""
        else:
            text = "未检出超标"

        self.exceed_summary.setPlainText(text)

    def _update_stats(self):
        """更新统计数据"""
        if not self.report_data:
            return

        self.source_count_label.setText(str(len(self.report_data.pollution_sources)))
        self.sampling_count_label.setText(str(len(self.report_data.sampling_points)))

        total_samples = sum(len(pt.samples) for pt in self.report_data.sampling_points)
        self.sample_count_label.setText(str(total_samples))

        exceeded = sum(
            sum(1 for s in pt.samples if s.is_exceeded)
            for pt in self.report_data.sampling_points
        )
        self.exceed_count_label.setText(str(exceeded))


# =============================================================================
# 便捷函数
# =============================================================================

def create_pollution_assessment_panel(parent=None) -> PollutionAssessmentPanel:
    """创建污染评估面板"""
    return PollutionAssessmentPanel(parent)
