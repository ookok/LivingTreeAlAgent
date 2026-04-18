"""
设置对话框
配置 Ollama 连接、模型路径、Agent 参数、AI 提供商、Profile 等
参考 hermes-agent 的 Web UI 设计
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox,
    QPushButton, QGroupBox, QCheckBox, QTabWidget,
    QWidget, QFormLayout, QScrollArea,
)
from PyQt6.QtGui import QFont

from core.config import AppConfig


class SettingsDialog(QDialog):
    """设置对话框"""

    config_changed = pyqtSignal(AppConfig)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings / 设置")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(
            "QDialog{background:#1a1a1a;}"
            "QLabel{color:#ccc;}"
            "QPushButton{background:#252525;color:#e8e8e8;border:1px solid #333;"
            "border-radius:5px;padding:7px 16px;}"
            "QPushButton:hover{background:#303030;}"
            "QPushButton:pressed{background:#1e1e1e;}"
            "QPushButton#SaveButton{background:#5a5aff;border-color:#5a5aff;color:white;font-weight:600;}"
            "QPushButton#SaveButton:hover{background:#4a4aef;}"
            "QLineEdit, QSpinBox, QComboBox{background:#252525;border:1px solid #333;"
            "border-radius:5px;padding:6px 10px;color:#e8e8e8;}"
            "QLineEdit:focus, QSpinBox:focus, QComboBox:focus{border-color:#5a5aff;}"
            "QComboBox::drop-down{border:none;width:20px;}"
            "QComboBox QAbstractItemView{background:#252525;border:1px solid #333;"
            "selection-background-color:#353585;color:#e8e8e8;}"
            "QGroupBox{color:#888;border:1px solid #2a2a2a;border-radius:6px;"
            "margin-top:8px;padding-top:12px;font-size:11px;font-weight:600;"
            "text-transform:uppercase;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;color:#666;}"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel("Settings / 设置")
        title.setStyleSheet("font-size:18px;font-weight:700;color:#e8e8e8;padding:8px 0;")
        layout.addWidget(title)

        # Tab
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #252525;border-radius:6px;padding:12px;"
            "background:#151515;}"
            "QTabBar::tab{background:#1e1e1e;color:#666;padding:8px 20px;"
            "border:1px solid #252525;border-radius:5px;margin-right:4px;}"
            "QTabBar::tab:selected{background:#252550;color:#e8e8e8;}"
            "QTabBar::tab:hover{background:#252525;}"
        )

        # ── Ollama ───────────────────────────────────────────
        ollama_tab = self._build_ollama_tab()
        tabs.addTab(ollama_tab, "Ollama")

        # ── 模型 ─────────────────────────────────────────────
        model_tab = self._build_model_tab()
        tabs.addTab(model_tab, "Models")

        # ── Agent ────────────────────────────────────────────
        agent_tab = self._build_agent_tab()
        tabs.addTab(agent_tab, "Agent")

        # ── 写作 ────────────────────────────────────────────
        writing_tab = self._build_writing_tab()
        tabs.addTab(writing_tab, "Writing")

        # ── Providers ────────────────────────────────────────
        from ui.provider_panel import ProviderPanel
        provider_tab = ProviderPanel()
        self.provider_panel = provider_tab
        tabs.addTab(provider_tab, "Providers")

        # ── Profiles ────────────────────────────────────────
        from ui.profile_panel import ProfilePanel
        profile_tab = ProfilePanel()
        self.profile_panel = profile_tab
        tabs.addTab(profile_tab, "Profiles")

        # ── Status ───────────────────────────────────────────
        from ui.status_panel import StatusPanel
        status_tab = StatusPanel()
        self.status_panel = status_tab
        tabs.addTab(status_tab, "Status")

        layout.addWidget(tabs, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("SaveButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _build_ollama_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ollama_url = QLineEdit(self.config.ollama.base_url)
        lay.addRow("服务地址:", self.ollama_url)

        self.ollama_model = QLineEdit(self.config.ollama.default_model)
        lay.addRow("默认模型:", self.ollama_model)

        self.ollama_ctx = QSpinBox()
        self.ollama_ctx.setRange(512, 128000)
        self.ollama_ctx.setValue(self.config.ollama.num_ctx)
        self.ollama_ctx.setSuffix(" tokens")
        lay.addRow("上下文窗口:", self.ollama_ctx)

        self.ollama_keep = QLineEdit(self.config.ollama.keep_alive)
        lay.addRow("保持加载:", self.ollama_keep)

        hint = QLabel("💡 默认模型示例：qwen2.5:7b、llama3.2:3b、mistral:7b\n"
                      "请确保模型名称与 Ollama 中注册的一致（ollama list 查看）")
        hint.setStyleSheet("color:#555;font-size:11px;padding:8px;")
        lay.addRow(hint)

        return w

    def _build_model_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)

        from core.config import get_models_dir
        models_dir = get_models_dir()

        self.models_dir = QLineEdit(str(models_dir))
        lay.addRow("模型目录:", self.models_dir)

        self.ollama_home = QLineEdit(
            self.config.model_path.ollama_home or str(Path.home() / ".ollama")
        )
        lay.addRow("Ollama 主目录:", self.ollama_home)

        self.auto_import = QCheckBox("自动导入 GGUF 到 Ollama")
        self.auto_import.setChecked(self.config.model_path.auto_import)
        lay.addRow("", self.auto_import)

        hint = QLabel("💡 GGUF 模型下载后将存储在模型目录。\n"
                      "Ollama 模型存放在 ~/.ollama/models/")
        hint.setStyleSheet("color:#555;font-size:11px;padding:8px;")
        lay.addRow(hint)

        return w

    def _build_agent_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)

        self.max_iter = QSpinBox()
        self.max_iter.setRange(1, 500)
        self.max_iter.setValue(self.config.agent.max_iterations)
        lay.addRow("最大迭代次数:", self.max_iter)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(256, 32768)
        self.max_tokens.setValue(self.config.agent.max_tokens)
        lay.addRow("最大输出 tokens:", self.max_tokens)

        self.temperature = QSpinBox()
        self.temperature.setRange(0, 200)
        self.temperature.setValue(int(self.config.agent.temperature * 100))
        self.temperature.setSuffix(" / 100")
        lay.addRow("Temperature:", self.temperature)

        self.streaming = QCheckBox("启用流式输出")
        self.streaming.setChecked(self.config.agent.streaming)
        lay.addRow("", self.streaming)

        self.show_reasoning = QCheckBox("显示推理过程")
        self.show_reasoning.setChecked(self.config.agent.show_reasoning)
        lay.addRow("", self.show_reasoning)

        tools_hint = QLabel(
            "💡 启用的工具集：file（文件）、writing（写作）、\n"
            "      project（项目）、ollama（模型管理）、terminal（终端）"
        )
        tools_hint.setStyleSheet("color:#555;font-size:11px;padding:8px;")
        lay.addRow(tools_hint)

        return w

    def _build_writing_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)

        from core.config import get_projects_dir
        proj_dir = get_projects_dir()

        self.proj_dir = QLineEdit(str(proj_dir))
        lay.addRow("项目目录:", self.proj_dir)

        self.auto_save = QSpinBox()
        self.auto_save.setRange(10, 600)
        self.auto_save.setValue(self.config.writing.auto_save_interval)
        self.auto_save.setSuffix(" 秒")
        lay.addRow("自动保存间隔:", self.auto_save)

        self.file_watch = QCheckBox("监控文件变更")
        self.file_watch.setChecked(self.config.writing.enable_file_watch)
        lay.addRow("", self.file_watch)

        hint = QLabel("💡 项目目录用于存放写作项目的 Markdown 文档。\n"
                      "文件监控会自动刷新文档列表。")
        hint.setStyleSheet("color:#555;font-size:11px;padding:8px;")
        lay.addRow(hint)

        return w

    def _on_save(self):
        from pathlib import Path
        from core.config import OllamaConfig, ModelPathConfig, AgentConfig, WritingConfig
        import os

        # Ollama
        self.config.ollama.base_url = self.ollama_url.text().strip()
        self.config.ollama.default_model = self.ollama_model.text().strip()
        self.config.ollama.num_ctx = self.ollama_ctx.value()
        self.config.ollama.keep_alive = self.ollama_keep.text().strip()

        # 模型
        self.config.model_path.models_dir = self.models_dir.text().strip()
        self.config.model_path.ollama_home = self.ollama_home.text().strip()
        self.config.model_path.auto_import = self.auto_import.isChecked()

        # Agent
        self.config.agent.max_iterations = self.max_iter.value()
        self.config.agent.max_tokens = self.max_tokens.value()
        self.config.agent.temperature = self.temperature.value() / 100.0
        self.config.agent.streaming = self.streaming.isChecked()
        self.config.agent.show_reasoning = self.show_reasoning.isChecked()

        # 写作
        self.config.writing.default_project_dir = self.proj_dir.text().strip()
        self.config.writing.auto_save_interval = self.auto_save.value()
        self.config.writing.enable_file_watch = self.file_watch.isChecked()

        self.config_changed.emit(self.config)
        self.accept()


from pathlib import Path
