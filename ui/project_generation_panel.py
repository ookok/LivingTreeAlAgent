# -*- coding: utf-8 -*-
"""
项目生成面板 - 咨询服务文档生成UI
Project Generation Panel - Consulting Document Generation UI
=============================================================

功能：
- 项目信息输入
- 文档类型选择
- 计算模型配置
- 数据源配置
- 一键生成控制
- 生成进度显示
- 输出文件管理

Author: Hermes Desktop Team
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 后台生成线程
# =============================================================================

class GenerationWorker(QThread):
    """后台生成工作线程"""
    progress_updated = pyqtSignal(int, str)
    generation_completed = pyqtSignal(bool, list, str)
    
    def __init__(self, engine, config, project_data, custom_content=None):
        super().__init__()
        self.engine = engine
        self.config = config
        self.project_data = project_data
        self.custom_content = custom_content or {}
    
    def run(self):
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.progress_updated.emit(20, "正在获取数据...")
            
            self.progress_updated.emit(50, "正在生成内容...")
            
            result = loop.run_until_complete(
                self.engine.generate_project_document(
                    config=self.config,
                    project_data=self.project_data,
                    custom_content=self.custom_content,
                )
            )
            
            loop.close()
            
            self.progress_updated.emit(100, "生成完成！")
            self.generation_completed.emit(
                result.status == "success",
                result.output_files,
                f"耗时: {result.generation_time:.2f}秒"
            )
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            self.generation_completed.emit(False, [], str(e))


# =============================================================================
# 项目生成面板
# =============================================================================

class ProjectGenerationPanel(QWidget):
    """项目生成面板"""
    
    DOCUMENT_TYPES = {
        "商业/规划类": [
            ("feasibility_report", "可行性研究报告"),
            ("project_proposal", "项目建议书"),
            ("business_plan", "商业计划书"),
            ("investment_analysis", "投资分析报告"),
            ("market_research", "市场研究报告"),
            ("strategic_plan", "战略规划"),
            ("due_diligence", "尽职调查报告"),
        ],
        "环保类": [
            ("eia_report", "环境影响评价报告"),
            ("environmental_emergency", "环境应急预案"),
            ("acceptance_monitoring", "竣工验收监测报告"),
            ("acceptance_report", "竣工验收报告"),
            ("pollution_permit", "排污许可证申请"),
            ("pollution_survey", "场地污染调查报告"),
            ("environmental_monitoring", "环境监测报告"),
            ("carbon_assessment", "碳排放评估报告"),
        ],
        "安全类": [
            ("safety_assessment", "安全评价报告"),
            ("occupational_health", "职业健康评价"),
            ("fire_safety", "消防安全评估"),
            ("emergency_response", "应急响应预案"),
            ("risk_assessment", "风险评估报告"),
        ],
        "法律类": [
            ("legal_opinion", "法律意见书"),
            ("compliance_report", "合规审查报告"),
            ("contract_review", "合同审查报告"),
            ("intellectual_property", "知识产权报告"),
        ],
        "财务类": [
            ("financial_analysis", "财务分析报告"),
            ("audit_report", "审计报告"),
            ("budget_plan", "预算方案"),
            ("cost_benefit", "成本效益分析"),
            ("tax_planning", "税务筹划报告"),
        ],
        "技术类": [
            ("technical_scheme", "技术方案"),
            ("design_specification", "设计说明书"),
            ("quality_plan", "质量计划"),
            ("inspection_report", "检验报告"),
        ],
        "能源类": [
            ("energy_assessment", "节能评估报告"),
            ("energy_audit", "能源审计报告"),
            ("clean_production", "清洁生产审核"),
        ],
    }
    
    OUTPUT_FORMATS = {
        "Word文档 (.docx)": "docx",
        "Excel表格 (.xlsx)": "xlsx",
        "PowerPoint (.pptx)": "pptx",
        "PDF文档 (.pdf)": "pdf",
        "HTML网页 (.html)": "html",
        "Markdown (.md)": "md",
        "图片 (.png)": "png",
        "CAD图纸 (.dxf)": "dxf",
        "纯文本 (.txt)": "txt",
        "JSON数据 (.json)": "json",
    }
    
    CALCULATION_MODELS = {
        "排放核算模型": "emission_calculation",
        "风险评价模型": "risk_evaluation",
        "工程经济分析": "economics_analysis",
        "扩散模拟模型": "dispersion_modeling",
        "噪声预测模型": "noise_prediction",
        "水质模型": "water_quality_model",
        "空气质量模型": "air_quality_model",
        "生态影响评估": "ecological_impact",
        "财务预测模型": "financial_forecast",
        "市场分析模型": "market_analysis",
        "统计分析模型": "statistical_analysis",
    }
    
    def __init__(self):
        super().__init__()
        self.engine = None
        self.worker = None
        self._init_engine()
        self._setup_ui()
    
    def _init_engine(self):
        """初始化生成引擎"""
        try:
            from core.smart_writing.project_generation import (
                get_project_generation_engine,
                ConsultingDocumentType,
                OutputFormat,
                CalculationModel,
                DataSourceType,
            )
            self.engine = get_project_generation_engine()
            self.ConsultingDocumentType = ConsultingDocumentType
            self.OutputFormat = OutputFormat
            self.CalculationModel = CalculationModel
            self.DataSourceType = DataSourceType
        except Exception as e:
            logger.warning(f"项目生成引擎加载失败: {e}")
            self.engine = None
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板（输入配置）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        scroll_layout.addWidget(self._create_project_info_group())
        scroll_layout.addWidget(self._create_document_type_group())
        scroll_layout.addWidget(self._create_output_format_group())
        scroll_layout.addWidget(self._create_calculation_group())
        scroll_layout.addWidget(self._create_data_source_group())
        scroll_layout.addWidget(self._create_custom_content_group())
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        layout.addWidget(self._create_action_buttons())
        
        return widget
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（输出和日志）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        progress_group = QGroupBox("生成进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        
        self.time_label = QLabel("")
        progress_layout.addWidget(self.time_label)
        
        layout.addWidget(progress_group)
        
        output_group = QGroupBox("输出文件")
        output_layout = QVBoxLayout(output_group)
        
        self.output_list = QListWidget()
        output_layout.addWidget(self.output_list)
        
        output_btn_layout = QHBoxLayout()
        open_dir_btn = QPushButton("打开输出目录")
        open_dir_btn.clicked.connect(self._open_output_dir)
        output_btn_layout.addWidget(open_dir_btn)
        
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self.output_list.clear)
        output_btn_layout.addWidget(clear_btn)
        
        output_layout.addLayout(output_btn_layout)
        layout.addWidget(output_group)
        
        log_group = QGroupBox("生成日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_project_info_group(self) -> QGroupBox:
        """创建项目信息组"""
        group = QGroupBox("项目信息")
        layout = QFormLayout(group)
        
        self.project_id_edit = QLineEdit()
        self.project_id_edit.setText(f"PRJ{datetime.now().strftime('%Y%m%d%H%M%S')}")
        layout.addRow("项目编号:", self.project_id_edit)
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("请输入项目全称")
        layout.addRow("项目名称:", self.project_name_edit)
        
        self.project_type_combo = QComboBox()
        self.project_type_combo.addItems(["新建", "改建", "扩建", "技术改造"])
        layout.addRow("项目类型:", self.project_type_combo)
        
        self.client_name_edit = QLineEdit()
        self.client_name_edit.setPlaceholderText("客户名称")
        layout.addRow("客户名称:", self.client_name_edit)
        
        self.client_unit_edit = QLineEdit()
        self.client_unit_edit.setPlaceholderText("客户单位")
        layout.addRow("客户单位:", self.client_unit_edit)
        
        self.project_location_edit = QLineEdit()
        self.project_location_edit.setPlaceholderText("项目建设地点")
        layout.addRow("建设地点:", self.project_location_edit)
        
        self.project_scale_edit = QLineEdit()
        self.project_scale_edit.setPlaceholderText("建设规模")
        layout.addRow("建设规模:", self.project_scale_edit)
        
        self.investment_edit = QLineEdit()
        self.investment_edit.setPlaceholderText("总投资金额")
        layout.addRow("总投资(万元):", self.investment_edit)
        
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("项目描述")
        self.description_edit.setMaximumHeight(80)
        layout.addRow("项目描述:", self.description_edit)
        
        return group
    
    def _create_document_type_group(self) -> QGroupBox:
        """创建文档类型组"""
        group = QGroupBox("文档类型")
        layout = QVBoxLayout(group)
        
        self.doc_type_combo = QComboBox()
        
        for category, types in self.DOCUMENT_TYPES.items():
            self.doc_type_combo.addItem(f"--- {category} ---")
            for type_id, type_name in types:
                self.doc_type_combo.addItem(f"  {type_name}", type_id)
        
        self.doc_type_combo.setCurrentIndex(1)
        layout.addWidget(self.doc_type_combo)
        
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("模板:"))
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(["标准模板", "精简模板", "详细模板", "自定义模板"])
        template_layout.addWidget(self.template_combo)
        
        layout.addLayout(template_layout)
        
        return group
    
    def _create_output_format_group(self) -> QGroupBox:
        """创建输出格式组"""
        group = QGroupBox("输出格式")
        layout = QVBoxLayout(group)
        
        self.format_checks = {}
        
        for label, value in list(self.OUTPUT_FORMATS.items())[:6]:
            cb = QCheckBox(label)
            cb.setChecked(value == "docx")
            self.format_checks[value] = cb
            layout.addWidget(cb)
        
        format_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all_formats)
        format_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all_formats)
        format_layout.addWidget(deselect_all_btn)
        
        layout.addLayout(format_layout)
        
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("输出目录:"))
        
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText("./output/projects")
        output_dir_layout.addWidget(self.output_dir_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_dir_layout.addWidget(browse_btn)
        
        layout.addLayout(output_dir_layout)
        
        return group
    
    def _create_calculation_group(self) -> QGroupBox:
        """创建计算模型组"""
        group = QGroupBox("计算模型（可选）")
        layout = QVBoxLayout(group)
        
        self.auto_calc_cb = QCheckBox("启用自动计算")
        self.auto_calc_cb.setChecked(True)
        layout.addWidget(self.auto_calc_cb)
        
        self.calc_list = QListWidget()
        self.calc_list.setSelectionMode(QListWidget.MultiSelection)
        
        for label, value in self.CALCULATION_MODELS.items():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, value)
            self.calc_list.addItem(item)
        
        layout.addWidget(self.calc_list)
        
        return group
    
    def _create_data_source_group(self) -> QGroupBox:
        """创建数据源组"""
        group = QGroupBox("数据来源（可选）")
        layout = QVBoxLayout(group)
        
        self.auto_fetch_cb = QCheckBox("启用自动数据采集")
        self.auto_fetch_cb.setChecked(True)
        layout.addWidget(self.auto_fetch_cb)
        
        data_sources = [
            ("气象数据API", "weather"),
            ("空气质量API", "air_quality"),
            ("水质数据API", "water_quality"),
            ("宏观经济数据API", "economic_data"),
        ]
        
        self.data_source_checks = {}
        for label, value in data_sources:
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.data_source_checks[value] = cb
            layout.addWidget(cb)
        
        return group
    
    def _create_custom_content_group(self) -> QGroupBox:
        """创建自定义内容组"""
        group = QGroupBox("自定义内容（可选）")
        layout = QVBoxLayout(group)
        
        layout.addWidget(QLabel("在此输入需要自定义的章节内容，使用JSON格式:"))
        
        self.custom_content_edit = QPlainTextEdit()
        self.custom_content_edit.setPlaceholderText('{\n  "section_id": "自定义内容"\n}')
        self.custom_content_edit.setMaximumHeight(150)
        layout.addWidget(self.custom_content_edit)
        
        return group
    
    def _create_action_buttons(self) -> QWidget:
        """创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        
        self.generate_btn = QPushButton("🚀 一键生成")
        self.generate_btn.setObjectName("primaryButton")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self.generate_btn.clicked.connect(self._start_generation)
        layout.addWidget(self.generate_btn)
        
        self.ai_review_btn = QPushButton("🤖 AI增强审核")
        self.ai_review_btn.setMinimumHeight(40)
        self.ai_review_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self.ai_review_btn.clicked.connect(self._open_ai_review_panel)
        layout.addWidget(self.ai_review_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        layout.addWidget(self.cancel_btn)
        
        return widget
    
    def _open_ai_review_panel(self):
        """打开AI增强审核面板"""
        try:
            from ui.ai_enhanced_generation_panel import AIEnhancedGenerationPanel
            dialog = QDialog(self)
            dialog.setWindowTitle("AI增强审核")
            dialog.setMinimumSize(900, 700)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)
            panel = AIEnhancedGenerationPanel(dialog)
            layout.addWidget(panel)
            dialog.exec()
        except Exception as e:
            logger.error(f"打开AI增强审核面板失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开AI增强审核面板:\n{e}")
    
    def _select_all_formats(self):
        """全选格式"""
        for cb in self.format_checks.values():
            cb.setChecked(True)
    
    def _deselect_all_formats(self):
        """取消全选格式"""
        for cb in self.format_checks.values():
            cb.setChecked(False)
    
    def _browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_edit.setText(dir_path)
    
    def _open_output_dir(self):
        """打开输出目录"""
        output_dir = self.output_dir_edit.text()
        if os.path.exists(output_dir):
            os.startfile(output_dir)
        else:
            QMessageBox.information(self, "提示", "输出目录不存在")
    
    def _log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def _start_generation(self):
        """开始生成"""
        if not self.engine:
            QMessageBox.warning(self, "错误", "项目生成引擎未加载")
            return
        
        project_name = self.project_name_edit.text().strip()
        if not project_name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            return
        
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在初始化...")
        self.output_list.clear()
        
        try:
            from core.smart_writing.project_generation import (
                GenerationConfig,
                ProjectData,
                ConsultingDocumentType,
                OutputFormat,
                CalculationModel,
                DataSourceConfig,
                DataSourceType,
            )
            
            doc_type_value = self.doc_type_combo.currentData()
            doc_type = ConsultingDocumentType(doc_type_value)
            
            output_formats = []
            for value, cb in self.format_checks.items():
                if cb.isChecked():
                    output_formats.append(OutputFormat(value))
            
            if not output_formats:
                output_formats = [OutputFormat.WORD]
            
            calculation_models = []
            if self.auto_calc_cb.isChecked():
                for i in range(self.calc_list.count()):
                    item = self.calc_list.item(i)
                    if item.isSelected():
                        model_value = item.data(Qt.UserRole)
                        try:
                            calculation_models.append(CalculationModel(model_value))
                        except ValueError:
                            pass
            
            data_sources = []
            if self.auto_fetch_cb.isChecked():
                for value, cb in self.data_source_checks.items():
                    if cb.isChecked():
                        data_sources.append(
                            DataSourceConfig(
                                source_type=DataSourceType.GOVERNMENT_API,
                                source_name=value,
                                is_enabled=True,
                            )
                        )
            
            config = GenerationConfig(
                document_type=doc_type,
                output_formats=output_formats,
                template_name=self.template_combo.currentText(),
                auto_calculate=self.auto_calc_cb.isChecked(),
                auto_fetch_data=self.auto_fetch_cb.isChecked(),
                calculation_models=calculation_models,
                data_sources=data_sources,
                output_dir=self.output_dir_edit.text(),
            )
            
            project_data = ProjectData(
                project_id=self.project_id_edit.text(),
                project_name=project_name,
                project_type=self.project_type_combo.currentText(),
                client_name=self.client_name_edit.text(),
                client_unit=self.client_unit_edit.text(),
                project_location=self.project_location_edit.text(),
                project_scale=self.project_scale_edit.text(),
                total_investment=float(self.investment_edit.text() or 0),
                description=self.description_edit.toPlainText(),
            )
            
            custom_content = {}
            try:
                import json
                custom_text = self.custom_content_edit.toPlainText().strip()
                if custom_text:
                    custom_content = json.loads(custom_text)
            except json.JSONDecodeError as e:
                self._log(f"自定义内容JSON解析失败: {e}")
            
            self.worker = GenerationWorker(self.engine, config, project_data, custom_content)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.generation_completed.connect(self._on_generation_completed)
            self.worker.start()
            
            self._log(f"开始生成: {project_name}")
            self._log(f"文档类型: {doc_type.value}")
            self._log(f"输出格式: {', '.join(f.value for f in output_formats)}")
            
        except Exception as e:
            self._log(f"生成配置错误: {e}")
            QMessageBox.critical(self, "错误", f"生成配置错误:\n{e}")
            self.generate_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
    
    def _cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self._log("生成已取消")
            self.generate_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_label.setText("已取消")
    
    def _on_progress_updated(self, progress: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)
        self._log(message)
    
    def _on_generation_completed(self, success: bool, output_files: List[str], time_info: str):
        """生成完成"""
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        if success:
            self._log(f"✅ 生成成功！{time_info}")
            self.progress_label.setText("生成完成！")
            
            for file_path in output_files:
                self.output_list.addItem(file_path)
            
            QMessageBox.information(
                self,
                "成功",
                f"文档生成成功！\n\n{time_info}\n生成文件: {len(output_files)}个",
            )
        else:
            self._log(f"❌ 生成失败: {time_info}")
            self.progress_label.setText("生成失败")
            QMessageBox.critical(self, "错误", f"生成失败:\n{time_info}")


# =============================================================================
# 导出
# =============================================================================

def create_project_generation_panel() -> ProjectGenerationPanel:
    """创建项目生成面板"""
    return ProjectGenerationPanel()
