"""
🎛️ Office 自动化面板 UI

三大核心标签页:
1. 📄 文档创建 - 自然语言 → 专业文档
2. ✏️ 填充编辑 - 模板 → 填充数据 → 输出
3. 🎨 格式化 - 文档 → 主题应用 → 输出

子标签页:
4. 🎯 意图分析 - 预览意图推断结果
5. ⚙️ 设置 - 引擎配置 + 主题管理
"""

import os
import asyncio
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QTabWidget, QGroupBox, QFormLayout,
    QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QListWidgetItem, QSplitter,
    QCheckBox, QSpinBox, QMessageBox, QStatusBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

logger = logging.getLogger(__name__)


class DocumentWorker(QThread):
    """文档处理工作线程"""
    progress = pyqtSignal(int, str)  # progress%, message
    finished = pyqtSignal(dict)       # result
    error = pyqtSignal(str)

    def __init__(self, manager, action: str, **kwargs):
        super().__init__()
        self.manager = manager
        self.action = action
        self.kwargs = kwargs

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if self.action == "create":
                result = loop.run_until_complete(
                    self.manager.create_document(
                        self.kwargs["request"],
                        self.kwargs.get("custom_data"),
                        self.progress.emit,
                    )
                )
            elif self.action == "fill":
                result = loop.run_until_complete(
                    self.manager.fill_document(
                        self.kwargs["template_path"],
                        self.kwargs["fill_data"],
                        self.progress.emit,
                    )
                )
            elif self.action == "format":
                result = loop.run_until_complete(
                    self.manager.format_document(
                        self.kwargs["file_path"],
                        self.kwargs.get("request", ""),
                        self.kwargs.get("theme_id"),
                        self.progress.emit,
                    )
                )
            else:
                result = {}

            self.finished.emit(result)
            loop.close()

        except Exception as e:
            self.error.emit(str(e))


class CreatePanel(QWidget):
    """📄 文档创建面板"""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 需求输入
        group = QGroupBox("📝 文档需求描述")
        group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 14px; }
        """)
        gl = QVBoxLayout(group)

        self.request_edit = QTextEdit()
        self.request_edit.setPlaceholderText(
            "请用自然语言描述您要创建的文档，例如：\n"
            "• 创建一份关于AI技术趋势的分析报告，面向技术团队\n"
            "• 制作一份融资路演PPT，面向投资方\n"
            "• 生成一份标准商务合同，对方是XX公司\n"
            "• 制作一份个人简历，简约风格"
        )
        self.request_edit.setMaximumHeight(120)
        gl.addWidget(self.request_edit)

        # 快捷选项
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("快捷:"))

        shortcuts = [
            ("📊 报告", "创建一份分析报告，面向管理层"),
            ("📋 合同", "创建一份标准商务合同"),
            ("📊 PPT", "制作一份演示文稿，现代风格"),
            ("📄 简历", "制作一份简约风格的个人简历"),
            ("📑 方案", "创建一份技术方案文档"),
        ]
        for label, text in shortcuts:
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 4px 8px;")
            btn.clicked.connect(lambda _, t=text: self.request_edit.setPlainText(t))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        gl.addLayout(quick_layout)
        layout.addWidget(group)

        # 选项区
        options_group = QGroupBox("⚙️ 选项")
        ol = QFormLayout(options_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("留空则自动推断")
        ol.addRow("标题:", self.title_edit)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["自动推断", "Word (.docx)", "PowerPoint (.pptx)", "Excel (.xlsx)", "PDF (.pdf)"])
        ol.addRow("格式:", self.format_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("自动推荐")
        for t in self.manager.get_themes():
            self.theme_combo.addItem(f"{t['name']} ({t['id']})", t['id'])
        ol.addRow("主题:", self.theme_combo)

        layout.addWidget(options_group)

        # 意图预览
        self.intent_group = QGroupBox("🎯 智能推断结果")
        il = QVBoxLayout(self.intent_group)
        self.intent_label = QLabel("请在上方输入需求描述...")
        self.intent_label.setWordWrap(True)
        self.intent_label.setStyleSheet("color: #666; padding: 8px;")
        il.addWidget(self.intent_label)
        self.intent_group.setVisible(False)
        layout.addWidget(self.intent_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # 按钮
        btn_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("🔍 分析意图")
        self.analyze_btn.setStyleSheet("""
            QPushButton { background-color: #3498DB; color: white;
                          padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #2980B9; }
        """)
        self.analyze_btn.clicked.connect(self._analyze)
        btn_layout.addWidget(self.analyze_btn)

        self.create_btn = QPushButton("📄 创建文档")
        self.create_btn.setStyleSheet("""
            QPushButton { background-color: #27AE60; color: white;
                          padding: 8px 24px; border-radius: 4px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #229954; }
        """)
        self.create_btn.clicked.connect(self._create)
        btn_layout.addWidget(self.create_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _analyze(self):
        """分析意图"""
        request = self.request_edit.toPlainText().strip()
        if not request:
            return

        result = self.manager.analyze_intent(request)
        intent = result.get("intent", {})
        template = result.get("recommended_template", {})
        theme = result.get("recommended_theme", {})

        html = (
            f"<b>文档类型:</b> {intent.get('document_type', '未知')}<br>"
            f"<b>目标受众:</b> {intent.get('audience', '通用')}<br>"
            f"<b>重要程度:</b> {intent.get('importance', '普通')}<br>"
            f"<b>输出格式:</b> {intent.get('output_format', 'docx')}<br>"
            f"<b>置信度:</b> {intent.get('confidence', 0):.0%}<br>"
            f"<b>推荐模板:</b> {template.get('template_id', '默认')}<br>"
            f"<b>推荐主题:</b> {theme.get('name', '企业正式')}"
        )

        self.intent_label.setText(html)
        self.intent_group.setVisible(True)

    def _create(self):
        """创建文档"""
        request = self.request_edit.toPlainText().strip()
        if not request:
            QMessageBox.warning(self, "提示", "请输入文档需求描述")
            return

        custom_data = {}
        if self.title_edit.text().strip():
            custom_data["title"] = self.title_edit.text().strip()

        fmt_idx = self.format_combo.currentIndex()
        if fmt_idx > 0:
            fmt_map = {1: "docx", 2: "pptx", 3: "xlsx", 4: "pdf"}
            custom_data["output_format"] = fmt_map[fmt_idx]

        theme_idx = self.theme_combo.currentIndex()
        if theme_idx > 0:
            custom_data["theme_id"] = self.theme_combo.itemData(theme_idx)

        self._set_running(True)
        self.worker = DocumentWorker(
            self.manager, "create",
            request=request, custom_data=custom_data,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _set_running(self, running: bool):
        self.create_btn.setEnabled(not running)
        self.analyze_btn.setEnabled(not running)
        self.cancel_btn.setVisible(running)
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setValue(0)

    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _on_finished(self, result: dict):
        self._set_running(False)
        status = result.get("status", "unknown")

        if status == "completed":
            output_path = result.get("result", {}).get("output_path")
            if output_path:
                self.status_label.setText(f"✅ 文档已创建: {output_path}")
                QMessageBox.information(self, "成功", f"文档已创建！\n{output_path}")
            else:
                self.status_label.setText("✅ 文档创建完成 (内存中)")
        else:
            errors = result.get("result", {}).get("errors", [])
            self.status_label.setText(f"❌ 创建失败: {', '.join(errors)}")

    def _on_error(self, error: str):
        self._set_running(False)
        self.status_label.setText(f"❌ 错误: {error}")

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        self._set_running(False)


class FillEditPanel(QWidget):
    """✏️ 填充编辑面板"""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 模板选择
        group = QGroupBox("📂 模板文件")
        gl = QHBoxLayout(group)

        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("选择模板文件 (.docx)")
        gl.addWidget(self.template_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_template)
        gl.addWidget(browse_btn)

        layout.addWidget(group)

        # 填充数据
        data_group = QGroupBox("📋 填充数据")
        dl = QVBoxLayout(data_group)

        self.data_table = QTableWidget(0, 2)
        self.data_table.setHorizontalHeaderLabels(["字段名", "值"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        dl.addWidget(self.data_table)

        add_btn = QPushButton("+ 添加字段")
        add_btn.clicked.connect(self._add_field)
        dl.addWidget(add_btn)

        layout.addWidget(data_group)

        # 进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.fill_btn = QPushButton("✏️ 填充文档")
        self.fill_btn.setStyleSheet("""
            QPushButton { background-color: #E67E22; color: white;
                          padding: 8px 24px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #D35400; }
        """)
        self.fill_btn.clicked.connect(self._fill)
        btn_layout.addWidget(self.fill_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _browse_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模板文件", "",
            "Word 文档 (*.docx);;所有文件 (*.*)"
        )
        if path:
            self.template_edit.setText(path)

    def _add_field(self):
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        self.data_table.setItem(row, 0, QTableWidgetItem(f"field_{row+1}"))
        self.data_table.setItem(row, 1, QTableWidgetItem(""))

    def _fill(self):
        template_path = self.template_edit.text().strip()
        if not template_path or not os.path.exists(template_path):
            QMessageBox.warning(self, "提示", "请选择有效的模板文件")
            return

        fill_data = {}
        for row in range(self.data_table.rowCount()):
            key_item = self.data_table.item(row, 0)
            val_item = self.data_table.item(row, 1)
            if key_item and val_item:
                fill_data[key_item.text()] = val_item.text()

        if not fill_data:
            QMessageBox.warning(self, "提示", "请添加至少一个填充字段")
            return

        self.progress_bar.setVisible(True)
        self.fill_btn.setEnabled(False)

        self.worker = DocumentWorker(
            self.manager, "fill",
            template_path=template_path, fill_data=fill_data,
        )
        self.worker.progress.connect(lambda p, m: self.progress_bar.setValue(p))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, result: dict):
        self.progress_bar.setVisible(False)
        self.fill_btn.setEnabled(True)

        if result.get("status") == "completed":
            path = result.get("result", {}).get("output_path", "")
            self.status_label.setText(f"✅ 填充完成: {path}")
        else:
            self.status_label.setText("❌ 填充失败")


class FormatPanel(QWidget):
    """🎨 格式化面板"""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 文档选择
        group = QGroupBox("📂 文档文件")
        gl = QHBoxLayout(group)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("选择要格式化的文档")
        gl.addWidget(self.file_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_file)
        gl.addWidget(browse_btn)

        layout.addWidget(group)

        # 格式化选项
        fmt_group = QGroupBox("🎨 格式化选项")
        fl = QFormLayout(fmt_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("自动推荐")
        for t in self.manager.get_themes():
            self.theme_combo.addItem(f"{t['name']} ({t['id']})", t['id'])
        fl.addRow("主题:", self.theme_combo)

        self.request_edit = QLineEdit()
        self.request_edit.setPlaceholderText("可选：描述格式化需求")
        fl.addRow("需求:", self.request_edit)

        layout.addWidget(fmt_group)

        # 进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # 按钮
        self.format_btn = QPushButton("🎨 应用格式化")
        self.format_btn.setStyleSheet("""
            QPushButton { background-color: #9B59B6; color: white;
                          padding: 8px 24px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #8E44AD; }
        """)
        self.format_btn.clicked.connect(self._format)
        layout.addWidget(self.format_btn)

        layout.addStretch()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "",
            "Word 文档 (*.docx);;PowerPoint (*.pptx);;Excel (*.xlsx);;所有文件 (*.*)"
        )
        if path:
            self.file_edit.setText(path)

    def _format(self):
        file_path = self.file_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "提示", "请选择有效的文档文件")
            return

        theme_id = None
        idx = self.theme_combo.currentIndex()
        if idx > 0:
            theme_id = self.theme_combo.itemData(idx)

        self.progress_bar.setVisible(True)
        self.format_btn.setEnabled(False)

        self.worker = DocumentWorker(
            self.manager, "format",
            file_path=file_path,
            request=self.request_edit.text().strip(),
            theme_id=theme_id,
        )
        self.worker.progress.connect(lambda p, m: self.progress_bar.setValue(p))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, result: dict):
        self.progress_bar.setVisible(False)
        self.format_btn.setEnabled(True)

        if result.get("status") == "completed":
            self.status_label.setText("✅ 格式化完成")
        else:
            self.status_label.setText("❌ 格式化失败")


class SettingsPanel(QWidget):
    """⚙️ 设置面板"""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 引擎依赖
        dep_group = QGroupBox("🔧 引擎依赖")
        dl = QVBoxLayout(dep_group)

        deps = self.manager.check_dependencies()
        dep_table = QTableWidget(len(deps), 3)
        dep_table.setHorizontalHeaderLabels(["依赖包", "状态", "安装命令"])
        dep_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        install_cmds = {
            "python-docx": "pip install python-docx",
            "openpyxl": "pip install openpyxl",
            "python-pptx": "pip install python-pptx",
            "reportlab": "pip install reportlab",
        }

        for row, (pkg, available) in enumerate(deps.items()):
            dep_table.setItem(row, 0, QTableWidgetItem(pkg))
            status = "✅ 已安装" if available else "❌ 未安装"
            dep_table.setItem(row, 1, QTableWidgetItem(status))
            dep_table.setItem(row, 2, QTableWidgetItem(install_cmds.get(pkg, "")))

        dl.addWidget(dep_table)
        layout.addWidget(dep_group)

        # 可用模型
        model_group = QGroupBox("🧠 可用模型")
        ml = QVBoxLayout(model_group)

        models = self.manager.get_models()
        model_table = QTableWidget(len(models), 5)
        model_table.setHorizontalHeaderLabels(["模型", "后端", "质量", "速度", "隐私"])
        model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row, m in enumerate(models):
            model_table.setItem(row, 0, QTableWidgetItem(m.get("name", "")))
            model_table.setItem(row, 1, QTableWidgetItem(m.get("backend", "")))
            model_table.setItem(row, 2, QTableWidgetItem(f"{m.get('quality', 0):.0%}"))
            model_table.setItem(row, 3, QTableWidgetItem(f"{m.get('speed', 0):.0%}"))
            model_table.setItem(row, 4, QTableWidgetItem(f"{m.get('privacy', 0):.0%}"))

        ml.addWidget(model_table)
        layout.addWidget(model_group)

        # 可用主题
        theme_group = QGroupBox("🎨 可用主题")
        tl = QVBoxLayout(theme_group)

        themes = self.manager.get_themes()
        for t in themes:
            tl.addWidget(QLabel(f"  {t['name']} ({t['id']}) - {t['colors']} 色"))

        layout.addWidget(theme_group)

        layout.addStretch()


class OfficeAutomationPanel(QWidget):
    """Office 自动化主面板"""

    def __init__(self, manager=None, parent=None):
        super().__init__(parent)
        self.manager = manager or self._create_default_manager()
        self._setup_ui()

    def _create_default_manager(self):
        """创建默认管理器"""
        from core.office_automation.office_manager import OfficeManager
        return OfficeManager()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel("🏢 Office 自动化系统")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #2C3E50;
            padding: 8px 0;
        """)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("自然语言 → 专业文档 | 三大工作流: Create / Fill / Format")
        subtitle.setStyleSheet("color: #7F8C8D; font-size: 13px; padding-bottom: 8px;")
        layout.addWidget(subtitle)

        # 主标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #BDC3C7; border-radius: 4px; }
            QTabBar::tab { padding: 8px 16px; font-weight: bold; }
        """)

        self.tabs.addTab(CreatePanel(self.manager), "📄 创建文档")
        self.tabs.addTab(FillEditPanel(self.manager), "✏️ 填充编辑")
        self.tabs.addTab(FormatPanel(self.manager), "🎨 格式化")
        self.tabs.addTab(SettingsPanel(self.manager), "⚙️ 设置")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        deps = self.manager.check_dependencies()
        installed = sum(1 for v in deps.values() if v)
        self.status_bar.showMessage(
            f"引擎就绪: {installed}/{len(deps)} | 模型: {len(self.manager.get_models())} | "
            f"主题: {len(self.manager.get_themes())} | 模板: {len(self.manager.get_templates())}"
        )
        layout.addWidget(self.status_bar)
