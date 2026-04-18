"""
首次启动引导向导
First Run Welcome Wizard

功能：
1. 多步骤引导界面
2. 按顺序配置必须项和可选项
3. 支持跳过可选配置
4. 验证必须配置
5. 应用配置并启动
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QWizard, QWizardPage, QComboBox, QGroupBox,
    QFormLayout, QTextBrowser, QWidget, QStackedWidget,
    QProgressBar, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

from core.first_run_config import (
    FirstRunConfig, ConfigStep, WizardStep, get_first_run_config
)
from core.config import AppConfig, OllamaConfig, save_config


class WelcomeWizard(QDialog):
    """
    首次启动引导向导
    
    信号:
        finished(config_values: dict) - 向导完成
        skipped() - 用户跳过向导
    """
    
    finished = pyqtSignal(dict)   # 完成的配置
    skipped = pyqtSignal()         # 跳过
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.first_run = get_first_run_config()
        self.config_values = {}
        self.current_step = 0
        
        # 加载之前的状态
        saved_step, saved_config = self.first_run.load_state()
        if saved_step > 0:
            self.current_step = saved_step
            self.config_values = saved_config
        
        self._setup_ui()
        self._show_step(self.current_step)
    
    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("首次启动向导 - Hermes Desktop")
        self.setMinimumSize(700, 550)
        self.setModal(True)
        self.setStyleSheet(self._get_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 顶部区域
        header = self._create_header()
        layout.addWidget(header)
        
        # 步骤指示器
        self.step_indicator = self._create_step_indicator()
        layout.addWidget(self.step_indicator)
        
        # 主内容区
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack, 1)
        
        # 为每个步骤创建页面
        for step in FirstRunConfig.WIZARD_STEPS:
            page = self._create_page(step)
            self.content_stack.addWidget(page)
        
        # 底部按钮区
        footer = self._create_footer()
        layout.addWidget(footer)
    
    def _get_stylesheet(self) -> str:
        """获取样式表"""
        return """
            QDialog {
                background: #1a1a2e;
                color: #e8e8e8;
            }
            QLabel {
                color: #e8e8e8;
            }
            QPushButton {
                background: #252540;
                color: #e8e8e8;
                border: 1px solid #3a3a5a;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3a3a5a;
            }
            QPushButton:pressed {
                background: #1a1a2e;
            }
            QPushButton#PrimaryButton {
                background: #5a5aff;
                border-color: #5a5aff;
                color: white;
                font-weight: bold;
            }
            QPushButton#PrimaryButton:hover {
                background: #4a4aef;
            }
            QPushButton#SkipButton {
                background: transparent;
                border: none;
                color: #888;
            }
            QPushButton#SkipButton:hover {
                color: #aaa;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #252540;
                border: 1px solid #3a3a5a;
                border-radius: 5px;
                padding: 8px 12px;
                color: #e8e8e8;
                min-height: 24px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #5a5aff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #252540;
                border: 1px solid #3a3a5a;
                selection-background-color: #3a3a5a;
            }
            QGroupBox {
                border: 1px solid #3a3a5a;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #888;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #5a5aff;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background: #5a5aff;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background: #252540;
                height: 8px;
            }
            QProgressBar::chunk {
                background: #5a5aff;
                border-radius: 4px;
            }
        """
    
    def _create_header(self) -> QWidget:
        """创建顶部区域"""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("background: #16162a; border-bottom: 1px solid #2a2a4a;")
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 16, 24, 12)
        
        # 标题
        title = QLabel("🚀 欢迎使用 Hermes Desktop")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e8e8e8;")
        layout.addWidget(title)
        
        # 副标题
        subtitle = QLabel("让我们快速配置一下，确保一切正常运行")
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)
        
        return header
    
    def _create_step_indicator(self) -> QWidget:
        """创建步骤指示器"""
        indicator = QWidget()
        indicator.setFixedHeight(50)
        indicator.setStyleSheet("background: #1e1e35;")
        
        layout = QHBoxLayout(indicator)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(12)
        
        self.step_labels = []
        steps = self.first_run.WIZARD_STEPS
        
        for i, step in enumerate(steps):
            # 步骤圆圈
            circle = QLabel(step.icon)
            circle.setFixedSize(32, 32)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setStyleSheet("""
                QLabel {
                    background: #252540;
                    border: 2px solid #3a3a5a;
                    border-radius: 16px;
                    font-size: 14px;
                }
            """)
            circle.setObjectName(f"step_circle_{i}")
            
            # 步骤标签
            label = QLabel(step.title[:6])
            label.setStyleSheet("font-size: 11px; color: #666;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setObjectName(f"step_label_{i}")
            
            self.step_labels.append((circle, label))
            
            # 添加到布局
            layout.addWidget(circle)
            layout.addWidget(label)
            
            # 添加连接线
            if i < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("border: none; border-top: 2px dashed #3a3a5a;")
                layout.addWidget(line, 1)
        
        layout.addStretch()
        
        return indicator
    
    def _create_page(self, step: WizardStep) -> QWidget:
        """创建步骤页面"""
        page = QWidget()
        page.setObjectName(f"page_{step.step_id.value}")
        
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.setSpacing(16)
        
        # 页面标题
        title = QLabel(f"{step.icon} {step.title}")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e8e8e8;")
        layout.addWidget(title)
        
        # 描述
        desc = QLabel(step.description)
        desc.setStyleSheet("font-size: 13px; color: #999; padding: 8px 0;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # 必填标记
        if step.required:
            required = QLabel("⚠️ 此步骤为必填项")
            required.setStyleSheet("color: #f59e0b; font-size: 12px;")
            layout.addWidget(required)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border: none; border-top: 1px solid #2a2a4a; margin: 8px 0;")
        layout.addWidget(line)
        
        # 根据步骤类型创建不同内容
        content = self._create_step_content(step)
        layout.addWidget(content, 1)
        
        return page
    
    def _create_step_content(self, step: WizardStep) -> QWidget:
        """根据步骤类型创建内容"""
        step_id = step.step_id
        
        if step_id == ConfigStep.OLLAMA:
            return self._create_ollama_content(step)
        elif step_id == ConfigStep.MODEL:
            return self._create_model_content(step)
        elif step_id == ConfigStep.KNOWLEDGE_BASE:
            return self._create_knowledge_base_content(step)
        elif step_id == ConfigStep.SEARCH_API:
            return self._create_search_api_content(step)
        elif step_id == ConfigStep.USER_PROFILE:
            return self._create_user_profile_content(step)
        elif step_id == ConfigStep.APPEARANCE:
            return self._create_appearance_content(step)
        else:
            return self._create_default_content(step)
    
    def _create_ollama_content(self, step: WizardStep) -> QWidget:
        """Ollama 配置内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        # 服务地址
        url_group = QGroupBox("服务配置")
        url_layout = QFormLayout(url_group)
        url_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        url_layout.setSpacing(12)
        
        self._ollama_url = QLineEdit(
            self.config_values.get("ollama", {}).get("base_url", "http://localhost:11434")
        )
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        url_layout.addRow("服务地址:", self._ollama_url)
        
        self._ollama_model = QLineEdit(
            self.config_values.get("ollama", {}).get("default_model", "")
        )
        self._ollama_model.setPlaceholderText("例如: qwen2.5:7b, llama3.2:3b, mistral:7b")
        url_layout.addRow("默认模型:", self._ollama_model)
        
        self._ollama_ctx = QSpinBox()
        self._ollama_ctx.setRange(512, 128000)
        self._ollama_ctx.setValue(
            self.config_values.get("ollama", {}).get("num_ctx", 8192)
        )
        self._ollama_ctx.setSuffix(" tokens")
        url_layout.addRow("上下文窗口:", self._ollama_ctx)
        
        self._ollama_keep = QLineEdit(
            self.config_values.get("ollama", {}).get("keep_alive", "5m")
        )
        self._ollama_keep.setPlaceholderText("5m, 10m, 1h, 0")
        url_layout.addRow("保持加载:", self._ollama_keep)
        
        layout.addWidget(url_group)
        
        # 检测按钮
        test_btn = QPushButton("🔍 测试连接")
        test_btn.clicked.connect(self._test_ollama_connection)
        layout.addWidget(test_btn)
        
        self._test_result = QLabel("")
        self._test_result.setStyleSheet("font-size: 12px; padding: 8px;")
        layout.addWidget(self._test_result)
        
        # 帮助信息
        help_text = QTextBrowser()
        help_text.setHtml("""
            <div style="color: #888; font-size: 12px;">
            <b>💡 提示：</b><br>
            • Ollama 服务地址通常是 <code>http://localhost:11434</code><br>
            • 默认模型可以留空，稍后在设置中配置<br>
            • 模型名称必须与 Ollama 中注册的一致（运行 <code>ollama list</code> 查看）<br>
            • 上下文窗口大小影响模型能处理的对话长度<br>
            • 保持加载时间控制模型在内存中的保留时长
            </div>
        """)
        help_text.setStyleSheet("""
            QTextBrowser {
                background: #1e1e35;
                border: 1px solid #3a3a5a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        help_text.setMaximumHeight(150)
        layout.addWidget(help_text)
        
        layout.addStretch()
        return container
    
    def _create_model_content(self, step: WizardStep) -> QWidget:
        """模型选择内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        # 推荐模型
        rec_group = QGroupBox("推荐模型")
        rec_layout = QVBoxLayout(rec_group)
        
        models = [
            ("🤖 qwen2.5:7b", "qwen2.5:7b", "通用型，推荐用于大多数场景，平衡性能和资源消耗"),
            ("🤖 llama3.2:3b", "llama3.2:3b", "轻量级模型，适合资源有限的环境"),
            ("🤖 mistral:7b", "mistral:7b", "高性能模型，适合复杂任务"),
            ("🤖 phi3:3.8b", "phi3:3.8b", "微软小模型，性价比高"),
        ]
        
        self._model_buttons = {}
        for icon_name, model_id, desc in models:
            btn = QPushButton(f"{icon_name}\n{desc}")
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 12px;
                    min-height: 60px;
                }
            """)
            btn.clicked.connect(lambda checked, m=model_id: self._select_model(m))
            rec_layout.addWidget(btn)
            self._model_buttons[model_id] = btn
        
        layout.addWidget(rec_group)
        
        # 自定义模型
        custom_group = QGroupBox("或输入自定义模型名称")
        custom_layout = QFormLayout(custom_group)
        
        self._custom_model = QLineEdit(
            self.config_values.get("model", {}).get("custom_model", "")
        )
        self._custom_model.setPlaceholderText("输入模型名称...")
        self._custom_model.textChanged.connect(self._on_custom_model_changed)
        custom_layout.addRow("模型名称:", self._custom_model)
        
        layout.addWidget(custom_group)
        
        layout.addStretch()
        return container
    
    def _create_knowledge_base_content(self, step: WizardStep) -> QWidget:
        """知识库配置内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        kb_group = QGroupBox("存储路径")
        kb_layout = QFormLayout(kb_group)
        kb_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        kb_layout.setSpacing(12)
        
        self._models_dir = QLineEdit(
            self.config_values.get("knowledge_base", {}).get("models_dir", "")
        )
        self._models_dir.setPlaceholderText("留空使用默认路径")
        kb_layout.addRow("模型目录:", self._models_dir)
        
        self._projects_dir = QLineEdit(
            self.config_values.get("knowledge_base", {}).get("projects_dir", "")
        )
        self._projects_dir.setPlaceholderText("留空使用默认路径")
        kb_layout.addRow("项目目录:", self._projects_dir)
        
        layout.addWidget(kb_group)
        
        info = QTextBrowser()
        info.setHtml("""
            <div style="color: #888; font-size: 12px;">
            <b>💡 路径说明：</b><br>
            • 模型目录：存储下载的 GGUF 模型文件<br>
            • 项目目录：存放您的写作项目和文档<br>
            • 留空将使用系统默认路径，您稍后可在设置中更改
            </div>
        """)
        info.setStyleSheet("""
            QTextBrowser {
                background: #1e1e35;
                border: 1px solid #3a3a5a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        info.setMaximumHeight(100)
        layout.addWidget(info)
        
        layout.addStretch()
        return container
    
    def _create_search_api_content(self, step: WizardStep) -> QWidget:
        """搜索 API 配置内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        info = QLabel("配置搜索 API 可以获得更准确的网络搜索结果。\n留空将使用基础搜索功能（可能有限制）。")
        info.setStyleSheet("color: #999; font-size: 13px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        api_group = QGroupBox("API 配置（可选）")
        api_layout = QFormLayout(api_group)
        api_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        api_layout.setSpacing(12)
        
        self._serper_key = QLineEdit(
            self.config_values.get("search_api", {}).get("serper_key", "")
        )
        self._serper_key.setPlaceholderText("Serper API Key...")
        api_layout.addRow("Serper Key:", self._serper_key)
        
        self._brave_key = QLineEdit(
            self.config_values.get("search_api", {}).get("brave_key", "")
        )
        self._brave_key.setPlaceholderText("Brave Search API Key...")
        api_layout.addRow("Brave Key:", self._brave_key)
        
        layout.addWidget(api_group)
        
        hint = QLabel("💡 API Key 可从以下网站获取：\n• Serper: https://serper.dev\n• Brave: https://brave.com/search/api/")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)
        
        layout.addStretch()
        return container
    
    def _create_user_profile_content(self, step: WizardStep) -> QWidget:
        """用户画像配置内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        info = QLabel("设置您的使用偏好，帮助 AI 提供更个性化的服务。\n此步骤可以跳过，稍后可在个人资料中完善。")
        info.setStyleSheet("color: #999; font-size: 13px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        profile_group = QGroupBox("基本信息")
        profile_layout = QFormLayout(profile_group)
        profile_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        profile_layout.setSpacing(12)
        
        self._display_name = QLineEdit(
            self.config_values.get("user_profile", {}).get("display_name", "")
        )
        self._display_name.setPlaceholderText("您的昵称...")
        profile_layout.addRow("显示名称:", self._display_name)
        
        layout.addWidget(profile_group)
        
        expertise_group = QGroupBox("专业领域（可选）")
        expertise_layout = QVBoxLayout(expertise_group)
        
        areas = ["编程开发", "数据分析", "AI/机器学习", "写作创作", "学术研究", "商业分析"]
        self._expertise_boxes = {}
        
        for area in areas:
            cb = QCheckBox(area)
            cb.setChecked(area in self.config_values.get("user_profile", {}).get("expertise_areas", []))
            expertise_layout.addWidget(cb)
            self._expertise_boxes[area] = cb
        
        layout.addWidget(expertise_group)
        
        layout.addStretch()
        return container
    
    def _create_appearance_content(self, step: WizardStep) -> QWidget:
        """外观设置内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        
        theme_group = QGroupBox("主题")
        theme_layout = QHBoxLayout(theme_group)
        
        self._theme_dark = QPushButton("🌙 深色")
        self._theme_dark.setCheckable(True)
        self._theme_dark.setChecked(
            self.config_values.get("appearance", {}).get("theme", "dark") == "dark"
        )
        self._theme_dark.clicked.connect(lambda: self._select_theme("dark"))
        theme_layout.addWidget(self._theme_dark)
        
        self._theme_light = QPushButton("☀️ 浅色")
        self._theme_light.setCheckable(True)
        self._theme_light.setChecked(
            self.config_values.get("appearance", {}).get("theme", "dark") == "light"
        )
        self._theme_light.clicked.connect(lambda: self._select_theme("light"))
        theme_layout.addWidget(self._theme_light)
        
        layout.addWidget(theme_group)
        
        lang_group = QGroupBox("语言")
        lang_layout = QFormLayout(lang_group)
        
        self._language = QComboBox()
        self._language.addItems(["中文 (简体)", "English", "中文 (繁體)", "日本語"])
        lang_layout.addRow("界面语言:", self._language)
        
        layout.addWidget(lang_group)
        
        layout.addStretch()
        return container
    
    def _create_default_content(self, step: WizardStep) -> QWidget:
        """默认内容"""
        container = QWidget()
        layout = QVBoxLayout(container)
        label = QLabel(f"正在配置: {step.title}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return container
    
    def _create_footer(self) -> QWidget:
        """创建底部按钮区"""
        footer = QWidget()
        footer.setFixedHeight(70)
        footer.setStyleSheet("background: #16162a; border-top: 1px solid #2a2a4a;")
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 12, 24, 12)
        
        # 跳过按钮（某些步骤）
        current_step_obj = self.first_run.WIZARD_STEPS[self.current_step]
        if current_step_obj.skippable:
            self._skip_btn = QPushButton("跳过此步骤 →")
            self._skip_btn.setObjectName("SkipButton")
            self._skip_btn.clicked.connect(self._skip_current_step)
        else:
            self._skip_btn = QLabel()
        
        layout.addWidget(self._skip_btn)
        
        layout.addStretch()
        
        # 上一步
        self._prev_btn = QPushButton("← 上一步")
        self._prev_btn.clicked.connect(self._prev_step)
        if self.current_step == 0:
            self._prev_btn.setEnabled(False)
        layout.addWidget(self._prev_btn)
        
        # 下一步 / 完成
        if self.current_step < len(self.first_run.WIZARD_STEPS) - 1:
            next_text = "下一步 →"
            next_obj_name = ""
        else:
            next_text = "完成 ✓"
            next_obj_name = "PrimaryButton"
        
        self._next_btn = QPushButton(next_text)
        self._next_btn.setObjectName(next_obj_name)
        self._next_btn.clicked.connect(self._next_or_finish)
        layout.addWidget(self._next_btn)
        
        return footer
    
    def _show_step(self, step_index: int):
        """显示指定步骤"""
        self.current_step = step_index
        
        # 更新步骤指示器
        for i, (circle, label) in enumerate(self.step_labels):
            if i < step_index:
                # 已完成
                circle.setStyleSheet("""
                    QLabel {
                        background: #22c55e;
                        border: 2px solid #22c55e;
                        border-radius: 16px;
                        font-size: 14px;
                    }
                """)
                circle.setText("✓")
                label.setStyleSheet("font-size: 11px; color: #22c55e;")
            elif i == step_index:
                # 当前
                circle.setStyleSheet("""
                    QLabel {
                        background: #5a5aff;
                        border: 2px solid #5a5aff;
                        border-radius: 16px;
                        font-size: 14px;
                    }
                """)
                label.setStyleSheet("font-size: 11px; color: #5a5aff;")
            else:
                # 未完成
                circle.setStyleSheet("""
                    QLabel {
                        background: #252540;
                        border: 2px solid #3a3a5a;
                        border-radius: 16px;
                        font-size: 14px;
                    }
                """)
                step_icon = self.first_run.WIZARD_STEPS[i].icon
                circle.setText(step_icon)
                label.setStyleSheet("font-size: 11px; color: #666;")
        
        # 切换页面
        self.content_stack.setCurrentIndex(step_index)
        
        # 更新按钮状态
        self._prev_btn.setEnabled(step_index > 0)
        
        step_obj = self.first_run.WIZARD_STEPS[step_index]
        if step_obj.skippable and hasattr(self, '_skip_btn'):
            self._skip_btn.show()
        elif hasattr(self, '_skip_btn'):
            self._skip_btn.hide()
        
        # 更新下一步按钮
        if step_index < len(self.first_run.WIZARD_STEPS) - 1:
            self._next_btn.setText("下一步 →")
            self._next_btn.setObjectName("")
        else:
            self._next_btn.setText("完成 ✓")
            self._next_btn.setObjectName("PrimaryButton")
        
        # 重新应用样式
        self._next_btn.setStyleSheet(self._get_stylesheet())
    
    def _collect_current_step_config(self):
        """收集当前步骤的配置"""
        step_id = self.first_run.WIZARD_STEPS[self.current_step].step_id
        
        if step_id == ConfigStep.OLLAMA:
            self.config_values["ollama"] = {
                "base_url": self._ollama_url.text().strip() or "http://localhost:11434",
                "default_model": self._ollama_model.text().strip(),
                "num_ctx": self._ollama_ctx.value(),
                "keep_alive": self._ollama_keep.text().strip() or "5m"
            }
        elif step_id == ConfigStep.MODEL:
            self.config_values["model"] = {
                "custom_model": self._custom_model.text().strip()
            }
        elif step_id == ConfigStep.KNOWLEDGE_BASE:
            self.config_values["knowledge_base"] = {
                "models_dir": self._models_dir.text().strip(),
                "projects_dir": self._projects_dir.text().strip()
            }
        elif step_id == ConfigStep.SEARCH_API:
            self.config_values["search_api"] = {
                "serper_key": self._serper_key.text().strip(),
                "brave_key": self._brave_key.text().strip()
            }
        elif step_id == ConfigStep.USER_PROFILE:
            expertise = [k for k, v in self._expertise_boxes.items() if v.isChecked()]
            self.config_values["user_profile"] = {
                "display_name": self._display_name.text().strip(),
                "expertise_areas": expertise
            }
        elif step_id == ConfigStep.APPEARANCE:
            theme = "dark" if self._theme_dark.isChecked() else "light"
            self.config_values["appearance"] = {
                "theme": theme,
                "language": self._language.currentText()
            }
        
        # 保存状态
        self.first_run.save_state(self.current_step, self.config_values)
    
    def _prev_step(self):
        """上一步"""
        self._collect_current_step_config()
        if self.current_step > 0:
            self._show_step(self.current_step - 1)
    
    def _next_or_finish(self):
        """下一步或完成"""
        self._collect_current_step_config()
        
        # 验证当前步骤
        step_obj = self.first_run.WIZARD_STEPS[self.current_step]
        if step_obj.required:
            is_valid, error = self.first_run.validate_required_config(self.config_values)
            if not is_valid:
                QMessageBox.warning(self, "配置不完整", error)
                return
        
        if self.current_step < len(self.first_run.WIZARD_STEPS) - 1:
            self._show_step(self.current_step + 1)
        else:
            self._finish_wizard()
    
    def _skip_current_step(self):
        """跳过当前步骤"""
        self._collect_current_step_config()
        
        # 找到下一个未跳过的步骤
        next_required = self.first_run.get_next_required_step(self.current_step + 1)
        
        if next_required is not None:
            self._show_step(next_required)
        elif self.current_step < len(self.first_run.WIZARD_STEPS) - 1:
            self._show_step(self.current_step + 1)
        else:
            self._finish_wizard()
    
    def _finish_wizard(self):
        """完成向导"""
        # 应用配置
        self._apply_config()
        
        # 标记完成
        self.first_run.mark_wizard_completed()
        self.first_run.clear_state()
        
        # 发送完成信号
        self.finished.emit(self.config_values)
        self.accept()
    
    def _apply_config(self):
        """应用配置到主配置文件"""
        # 构建 AppConfig
        from core.config import (
            OllamaConfig, ModelPathConfig, ModelMarketConfig,
            WritingConfig, SearchConfig, AgentConfig, AppConfig
        )
        
        ollama_data = self.config_values.get("ollama", {})
        kb_data = self.config_values.get("knowledge_base", {})
        search_data = self.config_values.get("search_api", {})
        
        # 构建配置
        config = AppConfig(
            ollama=OllamaConfig(
                base_url=ollama_data.get("base_url", "http://localhost:11434"),
                default_model=ollama_data.get("default_model", ""),
                num_ctx=ollama_data.get("num_ctx", 8192),
                keep_alive=ollama_data.get("keep_alive", "5m")
            ),
            model_path=ModelPathConfig(
                models_dir=kb_data.get("models_dir", ""),
                ollama_home="",
                auto_import=True
            ),
            writing=WritingConfig(
                default_project_dir=kb_data.get("projects_dir", ""),
                auto_save_interval=30,
                enable_file_watch=True
            ),
            search=SearchConfig(
                serper_key=search_data.get("serper_key", ""),
                brave_key=search_data.get("brave_key", ""),
                cache_ttl_minutes=60
            ),
            agent=AgentConfig(
                max_iterations=90,
                max_tokens=4096,
                temperature=0.7,
                enabled_toolsets=["file", "writing", "project", "ollama"],
                streaming=True,
                show_reasoning=False
            ),
            theme=self.config_values.get("appearance", {}).get("theme", "dark"),
            window_width=1400,
            window_height=900
        )
        
        # 保存配置
        save_config(config)
    
    def _test_ollama_connection(self):
        """测试 Ollama 连接"""
        url = self._ollama_url.text().strip() or "http://localhost:11434"
        self._test_result.setText("正在测试连接...")
        self._test_result.setStyleSheet("font-size: 12px; color: #888; padding: 8px;")
        
        import threading
        
        def test():
            try:
                import requests
                resp = requests.get(f"{url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    QTimer.singleShot(0, lambda: self._test_result.setText(
                        f"✅ 连接成功！检测到 {len(models)} 个模型"
                    ))
                    QTimer.singleShot(0, lambda: self._test_result.setStyleSheet(
                        "font-size: 12px; color: #22c55e; padding: 8px;"
                    ))
                else:
                    QTimer.singleShot(0, lambda: self._test_result.setText(
                        f"⚠️ 连接异常: HTTP {resp.status_code}"
                    ))
            except ImportError:
                QTimer.singleShot(0, lambda: self._test_result.setText(
                    "⚠️ 请安装 requests 库以测试连接"
                ))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._test_result.setText(
                    f"❌ 连接失败: {str(e)}"
                ))
                QTimer.singleShot(0, lambda: self._test_result.setStyleSheet(
                    "font-size: 12px; color: #ef4444; padding: 8px;"
                ))
        
        threading.Thread(target=test, daemon=True).start()
    
    def _select_model(self, model_id: str):
        """选择模型"""
        for mid, btn in self._model_buttons.items():
            if mid != model_id:
                btn.setChecked(False)
        
        self._custom_model.clear()
        self._ollama_model.setText(model_id)
    
    def _on_custom_model_changed(self, text: str):
        """自定义模型变化"""
        if text:
            for btn in self._model_buttons.values():
                btn.setChecked(False)
            self._ollama_model.setText(text)
    
    def _select_theme(self, theme: str):
        """选择主题"""
        self._theme_dark.setChecked(theme == "dark")
        self._theme_light.setChecked(theme == "light")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 保存当前状态
        self._collect_current_step_config()
        event.accept()


class QuickConfigDialog(QDialog):
    """
    快速配置对话框（简化版）
    
    仅配置必须项，跳过可选步骤
    """
    
    finished = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.first_run = get_first_run_config()
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("快速配置 - Hermes Desktop")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background: #1a1a2e; color: #e8e8e8; }
            QLabel { color: #e8e8e8; }
            QLineEdit {
                background: #252540;
                border: 1px solid #3a3a5a;
                border-radius: 5px;
                padding: 8px 12px;
                color: #e8e8e8;
            }
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background: #4a4aef; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("🔧 快速配置")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 说明
        info = QLabel("配置 Ollama 服务以开始使用。\n其他设置可以在启动后随时更改。")
        info.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(info)
        
        # Ollama 配置
        form = QFormLayout()
        form.setSpacing(12)
        
        self._url = QLineEdit("http://localhost:11434")
        form.addRow("服务地址:", self._url)
        
        self._model = QLineEdit()
        self._model.setPlaceholderText("例如: qwen2.5:7b")
        form.addRow("默认模型:", self._model)
        
        layout.addLayout(form)
        
        # 提示
        hint = QLabel("💡 提示: 运行 'ollama list' 查看可用模型")
        hint.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(hint)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        skip_btn = QPushButton("跳过")
        skip_btn.setStyleSheet("background: transparent; color: #888;")
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)
        
        start_btn = QPushButton("开始使用 →")
        start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(start_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_start(self):
        """开始使用"""
        # 验证
        if not self._model.text().strip():
            QMessageBox.warning(self, "提示", "请输入默认模型名称")
            return
        
        # 应用配置
        config = {
            "ollama": {
                "base_url": self._url.text().strip(),
                "default_model": self._model.text().strip()
            }
        }
        
        self.first_run.apply_wizard_config(config)
        self.first_run.mark_wizard_completed()
        
        self.finished.emit(config)
        self.accept()


def show_welcome_wizard(parent=None) -> tuple[bool, dict]:
    """
    显示欢迎向导
    
    Args:
        parent: 父窗口
        
    Returns:
        (completed, config_values): 是否完成和配置值
    """
    wizard = WelcomeWizard(parent)
    result = wizard.exec()
    
    if result == QDialog.DialogCode.Accepted:
        return True, wizard.config_values
    else:
        return False, {}


def show_quick_config(parent=None) -> tuple[bool, dict]:
    """
    显示快速配置对话框
    
    Args:
        parent: 父窗口
        
    Returns:
        (completed, config_values): 是否完成和配置值
    """
    dialog = QuickConfigDialog(parent)
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted:
        return True, {}
    else:
        return False, {}
