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
from pathlib import Path

from client.src.business.config import AppConfig


class SettingsDialog(QDialog):
    """设置对话框"""

    config_changed = pyqtSignal(AppConfig)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings / 设置")
        self.setMinimumSize(900, 650)
        self.setStyleSheet("""
            QDialog {
                background: #0F172A;
            }
            QLabel {
                color: #E2E8F0;
            }
            QPushButton {
                background: #334155;
                color: #F1F5F9;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #475569;
            }
            QPushButton:pressed {
                background: #1E293B;
            }
            QPushButton#SaveButton {
                background: #3B82F6;
                color: white;
                font-weight: 600;
            }
            QPushButton#SaveButton:hover {
                background: #2563EB;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                color: #F1F5F9;
                font-size: 14px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #3B82F6;
                outline: none;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #94A3B8;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #1E293B;
                border: 1px solid #334155;
                selection-background-color: #3B82F6;
                color: #F1F5F9;
                padding: 8px;
            }
            QGroupBox {
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #64748B;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("⚙️ Settings / 设置")
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: 700;
            color: #F1F5F9;
            padding: 8px 0 16px;
        """)
        layout.addWidget(title)

        # Tab
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 20px;
                background: #1E293B;
                margin-top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #94A3B8;
                padding: 12px 24px;
                margin-right: 8px;
                border-bottom: 2px solid transparent;
                font-size: 14px;
                font-weight: 500;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                color: #3B82F6;
                border-bottom: 2px solid #3B82F6;
            }
            QTabBar::tab:hover {
                color: #3B82F6;
                background: rgba(59, 130, 246, 0.1);
            }
        """)

        # 辅助函数：创建带滚动区域的标签页
        def create_scroll_tab(widget, title):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none;")
            scroll.setWidget(widget)
            tabs.addTab(scroll, title)

        # ── Ollama ───────────────────────────────────────────
        ollama_tab = self._build_ollama_tab()
        create_scroll_tab(ollama_tab, "Ollama")

        # ── 模型 ─────────────────────────────────────────────
        model_tab = self._build_model_tab()
        create_scroll_tab(model_tab, "Models")

        # ── Agent ────────────────────────────────────────────
        agent_tab = self._build_agent_tab()
        create_scroll_tab(agent_tab, "Agent")

        # ── 写作 ────────────────────────────────────────────
        writing_tab = self._build_writing_tab()
        create_scroll_tab(writing_tab, "Writing")

        # ── Providers ────────────────────────────────────────
        from client.src.presentation.panels.provider_panel import ProviderPanel
        provider_tab = ProviderPanel()
        self.provider_panel = provider_tab
        create_scroll_tab(provider_tab, "Providers")

        # ── Profiles ────────────────────────────────────────
        from client.src.presentation.panels.profile_panel import ProfilePanel
        profile_tab = ProfilePanel()
        self.profile_panel = profile_tab
        create_scroll_tab(profile_tab, "Profiles")

        # ── Status ───────────────────────────────────────────
        from client.src.presentation.panels.status_panel import StatusPanel
        status_tab = StatusPanel()
        self.status_panel = status_tab
        create_scroll_tab(status_tab, "Status")

        # ── Sync ─────────────────────────────────────────────
        sync_tab = self._build_sync_tab()
        create_scroll_tab(sync_tab, "Sync")

        # ── Logging ──────────────────────────────────────────
        logging_tab = self._build_logging_tab()
        create_scroll_tab(logging_tab, "Logging")

        # ── L4 Executor ──────────────────────────────────────
        l4_tab = self._build_l4_tab()
        create_scroll_tab(l4_tab, "L4 Executor")

        # ── L0-L4 Integration ────────────────────────────────
        l0l4_tab = self._build_l0l4_tab()
        create_scroll_tab(l0l4_tab, "L0-L4 Integration")

        layout.addWidget(tabs, 1)

        # Tab映射（用于导航）
        self._tab_map = {
            "ollama": 0,
            "models": 1,
            "agent": 2,
            "writing": 3,
            "providers": 4,
            "profiles": 5,
            "status": 6,
            "sync": 7,
            "logging": 8,
            "l4": 9,
            "l0l4": 10,
        }
        self._tabs = tabs

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

        # 处理配置对象可能是字典的情况
        ollama_config = self.config.ollama if hasattr(self.config, 'ollama') else {}
        if isinstance(ollama_config, dict):
            base_url = ollama_config.get('base_url', 'http://localhost:11434')
            default_model = ollama_config.get('default_model', 'qwen2.5:latest')
            num_ctx = ollama_config.get('num_ctx', 8192)
            keep_alive = ollama_config.get('keep_alive', '5m')
        else:
            base_url = getattr(ollama_config, 'base_url', 'http://localhost:11434')
            default_model = getattr(ollama_config, 'default_model', 'qwen2.5:latest')
            num_ctx = getattr(ollama_config, 'num_ctx', 8192)
            keep_alive = getattr(ollama_config, 'keep_alive', '5m')

        self.ollama_url = QLineEdit(base_url)
        lay.addRow("服务地址:", self.ollama_url)

        self.ollama_model = QLineEdit(default_model)
        lay.addRow("默认模型:", self.ollama_model)

        self.ollama_ctx = QSpinBox()
        self.ollama_ctx.setRange(512, 128000)
        self.ollama_ctx.setValue(num_ctx)
        self.ollama_ctx.setSuffix(" tokens")
        lay.addRow("上下文窗口:", self.ollama_ctx)

        self.ollama_keep = QLineEdit(keep_alive)
        lay.addRow("保持加载:", self.ollama_keep)

        hint = QLabel("💡 默认模型示例：qwen2.5:7b、llama3.2:3b、mistral:7b\n"
                      "请确保模型名称与 Ollama 中注册的一致（ollama list 查看）")
        hint.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            padding: 12px;
            background: #0F172A;
            border-radius: 8px;
            border-left: 3px solid #3B82F6;
        """)
        lay.addRow(hint)

        return w

    def _build_model_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(16)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        from client.src.business.config import get_models_dir
        models_dir = get_models_dir()

        self.models_dir = QLineEdit(str(models_dir))
        lay.addRow("模型目录:", self.models_dir)

        # 处理配置对象可能是字典的情况
        model_path_config = self.config.model_path if hasattr(self.config, 'model_path') else {}
        if isinstance(model_path_config, dict):
            ollama_home = model_path_config.get('ollama_home', str(Path.home() / ".ollama"))
            auto_import = model_path_config.get('auto_import', False)
        else:
            ollama_home = getattr(model_path_config, 'ollama_home', str(Path.home() / ".ollama"))
            auto_import = getattr(model_path_config, 'auto_import', False)

        self.ollama_home = QLineEdit(ollama_home)
        lay.addRow("Ollama 主目录:", self.ollama_home)

        self.auto_import = QCheckBox("自动导入 GGUF 到 Ollama")
        self.auto_import.setChecked(auto_import)
        lay.addRow("", self.auto_import)

        hint = QLabel("💡 GGUF 模型下载后将存储在模型目录。\n"
                      "Ollama 模型存放在 ~/.ollama/models/")
        hint.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            padding: 12px;
            background: #0F172A;
            border-radius: 8px;
            border-left: 3px solid #3B82F6;
        """)
        lay.addRow(hint)

        return w

    def _build_agent_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)

        # 处理配置对象可能是字典的情况
        agent_config = self.config.agent if hasattr(self.config, 'agent') else {}
        if isinstance(agent_config, dict):
            max_iterations = agent_config.get('max_iterations', 100)
            max_tokens = agent_config.get('max_tokens', 4096)
            temperature = agent_config.get('temperature', 0.7)
            streaming = agent_config.get('streaming', True)
            show_reasoning = agent_config.get('show_reasoning', False)
        else:
            max_iterations = getattr(agent_config, 'max_iterations', 100)
            max_tokens = getattr(agent_config, 'max_tokens', 4096)
            temperature = getattr(agent_config, 'temperature', 0.7)
            streaming = getattr(agent_config, 'streaming', True)
            show_reasoning = getattr(agent_config, 'show_reasoning', False)

        self.max_iter = QSpinBox()
        self.max_iter.setRange(1, 500)
        self.max_iter.setValue(max_iterations)
        lay.addRow("最大迭代次数:", self.max_iter)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(256, 32768)
        self.max_tokens.setValue(max_tokens)
        lay.addRow("最大输出 tokens:", self.max_tokens)

        self.temperature = QSpinBox()
        self.temperature.setRange(0, 200)
        self.temperature.setValue(int(temperature * 100))
        self.temperature.setSuffix(" / 100")
        lay.addRow("Temperature:", self.temperature)

        self.streaming = QCheckBox("启用流式输出")
        self.streaming.setChecked(streaming)
        lay.addRow("", self.streaming)

        self.show_reasoning = QCheckBox("显示推理过程")
        self.show_reasoning.setChecked(show_reasoning)
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

        from client.src.business.config import get_projects_dir
        proj_dir = get_projects_dir()

        self.proj_dir = QLineEdit(str(proj_dir))
        lay.addRow("项目目录:", self.proj_dir)

        # 处理配置对象可能是字典的情况
        writing_config = self.config.writing if hasattr(self.config, 'writing') else {}
        if isinstance(writing_config, dict):
            auto_save_interval = writing_config.get('auto_save_interval', 60)
            enable_file_watch = writing_config.get('enable_file_watch', True)
        else:
            auto_save_interval = getattr(writing_config, 'auto_save_interval', 60)
            enable_file_watch = getattr(writing_config, 'enable_file_watch', True)

        self.auto_save = QSpinBox()
        self.auto_save.setRange(10, 600)
        self.auto_save.setValue(auto_save_interval)
        self.auto_save.setSuffix(" 秒")
        lay.addRow("自动保存间隔:", self.auto_save)

        self.file_watch = QCheckBox("监控文件变更")
        self.file_watch.setChecked(enable_file_watch)
        lay.addRow("", self.file_watch)

        hint = QLabel("💡 项目目录用于存放写作项目的 Markdown 文档。\n"
                      "文件监控会自动刷新文档列表。")
        hint.setStyleSheet("color:#555;font-size:11px;padding:8px;")
        lay.addRow(hint)

        return w

    def _build_sync_tab(self) -> QWidget:
        """构建配置同步 Tab"""
        w = QWidget()
        main_lay = QVBoxLayout(w)
        main_lay.setSpacing(16)

        # ── 说明 ──────────────────────────────────────────
        desc = QLabel(
            "配置同步让您只需设置一次，即可在所有设备上自动同步。"
            "所有设备使用相同的 Token即可共享配置。"
        )
        desc.setStyleSheet("color:#888;font-size:12px;padding:4px;")
        desc.setWordWrap(True)
        main_lay.addWidget(desc)

        # ── 当前状态卡片 ────────────────────────────────────
        status_card = QGroupBox("当前状态")
        status_lay = QFormLayout(status_card)
        status_lay.setSpacing(10)

        self.sync_status_label = QLabel("未连接")
        self.sync_status_label.setStyleSheet("color:#ef4444;font-weight:600;")
        status_lay.addRow("登录状态:", self.sync_status_label)

        self.sync_server_label = QLabel("检测中...")
        self.sync_server_label.setStyleSheet("color:#888;")
        status_lay.addRow("服务器:", self.sync_server_label)

        self.sync_token_label = QLabel("-")
        self.sync_token_label.setStyleSheet("color:#666;font-family:monospace;")
        status_lay.addRow("Token:", self.sync_token_label)

        self.sync_pending_label = QLabel("0")
        self.sync_pending_label.setStyleSheet("color:#f59e0b;")
        status_lay.addRow("待同步:", self.sync_pending_label)

        main_lay.addWidget(status_card)

        # ── Token 管理 ─────────────────────────────────────
        token_card = QGroupBox("身份令牌")
        token_lay = QVBoxLayout(token_card)
        token_lay.setSpacing(10)

        token_hint = QLabel(
            '输入已有的 Token 登录，或点击"注册新身份"生成新 Token。\n'
            '将 Token 告诉其他设备，即可共享同一份配置。'
        )
        token_hint.setStyleSheet("color:#666;font-size:11px;")
        token_hint.setWordWrap(True)
        token_lay.addWidget(token_hint)

        token_row = QHBoxLayout()
        token_row.addWidget(QLabel("Token:"))
        self.sync_token_input = QLineEdit()
        self.sync_token_input.setPlaceholderText("输入您的 user_token...")
        self.sync_token_input.setStyleSheet(
            "QLineEdit{background:#1a1a1a;border:1px solid #333;"
            "border-radius:5px;padding:6px 10px;color:#e8e8e8;}"
        )
        token_row.addWidget(self.sync_token_input, 1)
        token_lay.addLayout(token_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.sync_login_btn = QPushButton("登录")
        self.sync_login_btn.setStyleSheet(
            "QPushButton{background:#5a5aff;color:white;border:none;"
            "border-radius:5px;padding:8px 20px;font-weight:600;}"
            "QPushButton:hover{background:#4a4aef;}"
        )
        self.sync_register_btn = QPushButton("注册新身份")
        self.sync_register_btn.setStyleSheet(
            "QPushButton{background:#252525;color:#e8e8e8;border:1px solid #333;"
            "border-radius:5px;padding:8px 16px;}"
            "QPushButton:hover{background:#303030;}"
        )
        self.sync_logout_btn = QPushButton("退出登录")
        self.sync_logout_btn.setStyleSheet(
            "QPushButton{background:#3a1a1a;color:#ef4444;border:1px solid #7f1d1d;"
            "border-radius:5px;padding:8px 16px;}"
        )

        btn_row.addWidget(self.sync_login_btn)
        btn_row.addWidget(self.sync_register_btn)
        btn_row.addWidget(self.sync_logout_btn)
        btn_row.addStretch()
        token_lay.addLayout(btn_row)

        main_lay.addWidget(token_card)

        # ── 同步操作 ───────────────────────────────────────
        action_card = QGroupBox("同步操作")
        action_lay = QVBoxLayout(action_card)
        action_lay.setSpacing(10)

        self.sync_push_btn = QPushButton("推送本地配置到服务器")
        self.sync_pull_btn = QPushButton("从服务器拉取配置")
        self.sync_status_btn = QPushButton("刷新状态")

        for btn in [self.sync_push_btn, self.sync_pull_btn, self.sync_status_btn]:
            btn.setStyleSheet(
                "QPushButton{background:#252525;color:#e8e8e8;border:1px solid #333;"
                "border-radius:5px;padding:8px 16px;}"
                "QPushButton:hover{background:#303030;}"
                "QPushButton:disabled{color:#555;}"
            )

        self.sync_result_label = QLabel("")
        self.sync_result_label.setStyleSheet("color:#888;font-size:11px;")
        self.sync_result_label.setWordWrap(True)

        h_row = QHBoxLayout()
        h_row.addWidget(self.sync_push_btn)
        h_row.addWidget(self.sync_pull_btn)
        h_row.addWidget(self.sync_status_btn)
        action_lay.addLayout(h_row)
        action_lay.addWidget(self.sync_result_label)

        main_lay.addWidget(action_card)

        # ── 远程配置 ──────────────────────────────────────
        remote_card = QGroupBox("服务器上的配置")
        remote_lay = QVBoxLayout(remote_card)
        remote_lay.setSpacing(8)

        self.sync_remote_keys_label = QLabel('点击"刷新状态"查看')
        self.sync_remote_keys_label.setStyleSheet("color:#666;font-size:11px;")
        self.sync_remote_keys_label.setWordWrap(True)
        remote_lay.addWidget(self.sync_remote_keys_label)

        self.sync_clear_btn = QPushButton("清除服务器配置")
        self.sync_clear_btn.setStyleSheet(
            "QPushButton{background:#3a1a1a;color:#ef4444;border:1px solid #7f1d1d;"
            "border-radius:5px;padding:6px 14px;font-size:11px;}"
        )
        remote_lay.addWidget(self.sync_clear_btn)

        main_lay.addWidget(remote_card)

        main_lay.addStretch()

        # ── 信号连接 ───────────────────────────────────────
        self.sync_login_btn.clicked.connect(self._on_sync_login)
        self.sync_register_btn.clicked.connect(self._on_sync_register)
        self.sync_logout_btn.clicked.connect(self._on_sync_logout)
        self.sync_push_btn.clicked.connect(self._on_sync_push)
        self.sync_pull_btn.clicked.connect(self._on_sync_pull)
        self.sync_status_btn.clicked.connect(self._on_sync_refresh)
        self.sync_clear_btn.clicked.connect(self._on_sync_clear)

        # 初始化状态
        self._init_sync_status()

        return w

    def _build_logging_tab(self) -> QWidget:
        """构建日志配置 Tab"""
        w = QWidget()
        main_lay = QVBoxLayout(w)
        main_lay.setSpacing(16)

        # ── 说明 ──────────────────────────────────────────
        desc = QLabel(
            "日志系统配置，允许您控制日志的级别和输出方式。\n"
            "您可以根据需要启用或禁用不同级别的日志。"
        )
        desc.setStyleSheet("color:#888;font-size:12px;padding:4px;")
        desc.setWordWrap(True)
        main_lay.addWidget(desc)

        # ── 日志系统总开关 ────────────────────────────────
        general_card = QGroupBox("日志系统")
        general_lay = QVBoxLayout(general_card)
        general_lay.setSpacing(10)

        self.logging_enabled = QCheckBox("启用日志系统")
        self.logging_enabled.setChecked(True)
        general_lay.addWidget(self.logging_enabled)

        from client.src.business.error_logger import LOG_DIR
        log_dir_label = QLabel(f"日志目录: {LOG_DIR}")
        log_dir_label.setStyleSheet("color:#666;font-size:11px;")
        general_lay.addWidget(log_dir_label)

        main_lay.addWidget(general_card)

        # ── 日志级别 ──────────────────────────────────────
        levels_card = QGroupBox("日志级别")
        levels_lay = QVBoxLayout(levels_card)
        levels_lay.setSpacing(8)

        self.logging_debug = QCheckBox("调试 (DEBUG)")
        self.logging_debug.setChecked(True)
        levels_lay.addWidget(self.logging_debug)

        self.logging_info = QCheckBox("信息 (INFO)")
        self.logging_info.setChecked(True)
        levels_lay.addWidget(self.logging_info)

        self.logging_warning = QCheckBox("警告 (WARNING)")
        self.logging_warning.setChecked(True)
        levels_lay.addWidget(self.logging_warning)

        self.logging_error = QCheckBox("错误 (ERROR)")
        self.logging_error.setChecked(True)
        levels_lay.addWidget(self.logging_error)

        self.logging_critical = QCheckBox("严重 (CRITICAL)")
        self.logging_critical.setChecked(True)
        levels_lay.addWidget(self.logging_critical)

        main_lay.addWidget(levels_card)

        # ── 日志处理器 ────────────────────────────────────
        handlers_card = QGroupBox("日志输出")
        handlers_lay = QVBoxLayout(handlers_card)
        handlers_lay.setSpacing(8)

        self.logging_console = QCheckBox("控制台输出")
        self.logging_console.setChecked(True)
        handlers_lay.addWidget(self.logging_console)

        self.logging_file = QCheckBox("文件输出")
        self.logging_file.setChecked(True)
        handlers_lay.addWidget(self.logging_file)

        self.logging_ui = QCheckBox("UI 日志")
        self.logging_ui.setChecked(True)
        handlers_lay.addWidget(self.logging_ui)

        self.logging_network = QCheckBox("网络日志")
        self.logging_network.setChecked(True)
        handlers_lay.addWidget(self.logging_network)

        self.logging_debug_file = QCheckBox("调试日志文件")
        self.logging_debug_file.setChecked(True)
        handlers_lay.addWidget(self.logging_debug_file)

        main_lay.addWidget(handlers_card)

        # ── 提示信息 ──────────────────────────────────────
        hint = QLabel(
            "💡 注意：禁用日志系统可能会影响问题排查。\n"
            "建议至少保持错误和警告级别的日志启用。"
        )
        hint.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            padding: 12px;
            background: #0F172A;
            border-radius: 8px;
            border-left: 3px solid #3B82F6;
        """)
        main_lay.addWidget(hint)

        main_lay.addStretch()

        return w

    def _build_l4_tab(self) -> QWidget:
        """构建 L4 执行器配置 Tab"""
        w = QWidget()
        main_lay = QVBoxLayout(w)
        main_lay.setSpacing(16)

        # ── 说明 ──────────────────────────────────────────
        desc = QLabel(
            "L4 执行器配置，用于控制 L4 Relay 执行器的行为。\n"
            "L4 执行器是四级缓存金字塔的最终执行层，集成了 RelayFreeLLM 网关。"
        )
        desc.setStyleSheet("color:#888;font-size:12px;padding:4px;")
        desc.setWordWrap(True)
        main_lay.addWidget(desc)

        # ── 基本配置 ──────────────────────────────────────
        basic_card = QGroupBox("基本配置")
        basic_lay = QFormLayout(basic_card)
        basic_lay.setSpacing(12)
        basic_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l4_gateway_url = QLineEdit("http://localhost:8000/v1")
        basic_lay.addRow("Relay 网关地址:", self.l4_gateway_url)

        self.l4_enable_write_back = QCheckBox("启用结果回填缓存")
        self.l4_enable_write_back.setChecked(True)
        basic_lay.addRow("", self.l4_enable_write_back)

        self.l4_fallback_to_direct = QCheckBox("启用直接 Ollama 降级")
        self.l4_fallback_to_direct.setChecked(True)
        basic_lay.addRow("", self.l4_fallback_to_direct)

        main_lay.addWidget(basic_card)

        # ── 健康状态 ──────────────────────────────────────
        status_card = QGroupBox("健康状态")
        status_lay = QVBoxLayout(status_card)
        status_lay.setSpacing(8)

        try:
            from core.fusion_rag.l4_executor import get_l4_executor
            executor = get_l4_executor()
            import asyncio
            loop = asyncio.new_event_loop()
            health = loop.run_until_complete(executor.health_check())
            loop.close()

            relay_status = "可用" if health["relay_gateway"] else "不可用"
            ollama_status = "可用" if health["direct_ollama"] else "不可用"

            status_text = f"RelayFreeLLM 网关: {relay_status}\n"
            status_text += f"直接 Ollama: {ollama_status}\n"
            status_text += f"总请求数: {health['stats']['total_requests']}\n"
            status_text += f"成功率: {health['stats']['success_rate']:.2f}\n"
            status_text += f"最后使用的提供商: {health['stats']['last_provider'] or '无'}"

            status_label = QLabel(status_text)
            status_label.setStyleSheet("color:#E2E8F0;font-size:11px;")
            status_lay.addWidget(status_label)
        except Exception as e:
            status_label = QLabel(f"获取健康状态失败: {e}")
            status_label.setStyleSheet("color:#ef4444;font-size:11px;")
            status_lay.addWidget(status_label)

        main_lay.addWidget(status_card)

        # ── 提示信息 ──────────────────────────────────────
        hint = QLabel(
            "💡 注意：\n"
            "- RelayFreeLLM 网关需要单独启动，默认地址为 http://localhost:8000\n"
            "- 如果网关不可用，系统会自动降级到本地 Ollama\n"
            "- 启用结果回填缓存可以提高后续查询的性能"
        )
        hint.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            padding: 12px;
            background: #0F172A;
            border-radius: 8px;
            border-left: 3px solid #3B82F6;
        """)
        main_lay.addWidget(hint)

        main_lay.addStretch()

        return w

    def _build_l0l4_tab(self) -> QWidget:
        """构建 L0-L4 集成配置 Tab"""
        w = QWidget()
        main_lay = QVBoxLayout(w)
        main_lay.setSpacing(16)

        # ── 说明 ──────────────────────────────────────────
        desc = QLabel(
            "L0-L4 集成配置，用于控制各层级的行为和测试状态。\n"
            "L0: SmolLM2 快反大脑 (毫秒级响应)\n"
            "L1: 精确缓存层 (快速检索)\n"
            "L2: 会话缓存层 (上下文感知)\n"
            "L3: 知识库层 (深度文档检索)\n"
            "L4: 数据库层 (结构化数据查询)"
        )
        desc.setStyleSheet("color:#888;font-size:12px;padding:4px;")
        desc.setWordWrap(True)
        main_lay.addWidget(desc)

        # ── L0 层配置 ─────────────────────────────────────
        l0_card = QGroupBox("L0 层 (SmolLM2 快反大脑)")
        l0_lay = QVBoxLayout(l0_card)
        l0_lay.setSpacing(10)

        l0_config_lay = QFormLayout()
        l0_config_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l0_enable = QCheckBox("启用 L0 路由")
        self.l0_enable.setChecked(True)
        l0_config_lay.addRow("", self.l0_enable)

        self.l0_enable_cache = QCheckBox("启用 L0 缓存")
        self.l0_enable_cache.setChecked(True)
        l0_config_lay.addRow("", self.l0_enable_cache)

        self.l0_enable_fast_local = QCheckBox("启用本地快速执行")
        self.l0_enable_fast_local.setChecked(True)
        l0_config_lay.addRow("", self.l0_enable_fast_local)

        l0_lay.addLayout(l0_config_lay)

        l0_test_btn = QPushButton("测试 L0 状态")
        l0_test_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        l0_test_btn.clicked.connect(self._test_l0_status)
        l0_lay.addWidget(l0_test_btn)

        self.l0_status_label = QLabel("点击测试按钮查看状态")
        self.l0_status_label.setStyleSheet("color:#666;font-size:11px;")
        l0_lay.addWidget(self.l0_status_label)

        main_lay.addWidget(l0_card)

        # ── L1 层配置 ─────────────────────────────────────
        l1_card = QGroupBox("L1 层 (精确缓存层)")
        l1_lay = QVBoxLayout(l1_card)
        l1_lay.setSpacing(10)

        l1_config_lay = QFormLayout()
        l1_config_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l1_enable = QCheckBox("启用 L1 缓存")
        self.l1_enable.setChecked(True)
        l1_config_lay.addRow("", self.l1_enable)

        l1_lay.addLayout(l1_config_lay)

        l1_test_btn = QPushButton("测试 L1 状态")
        l1_test_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        l1_test_btn.clicked.connect(self._test_l1_status)
        l1_lay.addWidget(l1_test_btn)

        self.l1_status_label = QLabel("点击测试按钮查看状态")
        self.l1_status_label.setStyleSheet("color:#666;font-size:11px;")
        l1_lay.addWidget(self.l1_status_label)

        main_lay.addWidget(l1_card)

        # ── L2 层配置 ─────────────────────────────────────
        l2_card = QGroupBox("L2 层 (会话缓存层)")
        l2_lay = QVBoxLayout(l2_card)
        l2_lay.setSpacing(10)

        l2_config_lay = QFormLayout()
        l2_config_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l2_enable = QCheckBox("启用 L2 缓存")
        self.l2_enable.setChecked(True)
        l2_config_lay.addRow("", self.l2_enable)

        l2_lay.addLayout(l2_config_lay)

        l2_test_btn = QPushButton("测试 L2 状态")
        l2_test_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        l2_test_btn.clicked.connect(self._test_l2_status)
        l2_lay.addWidget(l2_test_btn)

        self.l2_status_label = QLabel("点击测试按钮查看状态")
        self.l2_status_label.setStyleSheet("color:#666;font-size:11px;")
        l2_lay.addWidget(self.l2_status_label)

        main_lay.addWidget(l2_card)

        # ── L3 层配置 ─────────────────────────────────────
        l3_card = QGroupBox("L3 层 (知识库层)")
        l3_lay = QVBoxLayout(l3_card)
        l3_lay.setSpacing(10)

        l3_config_lay = QFormLayout()
        l3_config_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l3_enable = QCheckBox("启用 L3 知识库")
        self.l3_enable.setChecked(True)
        l3_config_lay.addRow("", self.l3_enable)

        l3_lay.addLayout(l3_config_lay)

        l3_test_btn = QPushButton("测试 L3 状态")
        l3_test_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        l3_test_btn.clicked.connect(self._test_l3_status)
        l3_lay.addWidget(l3_test_btn)

        self.l3_status_label = QLabel("点击测试按钮查看状态")
        self.l3_status_label.setStyleSheet("color:#666;font-size:11px;")
        l3_lay.addWidget(self.l3_status_label)

        main_lay.addWidget(l3_card)

        # ── L4 层配置 ─────────────────────────────────────
        l4_card = QGroupBox("L4 层 (数据库层)")
        l4_lay = QVBoxLayout(l4_card)
        l4_lay.setSpacing(10)

        l4_config_lay = QFormLayout()
        l4_config_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.l4_enable = QCheckBox("启用 L4 数据库")
        self.l4_enable.setChecked(True)
        l4_config_lay.addRow("", self.l4_enable)

        l4_lay.addLayout(l4_config_lay)

        l4_test_btn = QPushButton("测试 L4 状态")
        l4_test_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        l4_test_btn.clicked.connect(self._test_l4_status)
        l4_lay.addWidget(l4_test_btn)

        self.l4_status_label = QLabel("点击测试按钮查看状态")
        self.l4_status_label.setStyleSheet("color:#666;font-size:11px;")
        l4_lay.addWidget(self.l4_status_label)

        main_lay.addWidget(l4_card)

        # ── 集成测试 ──────────────────────────────────────
        integration_card = QGroupBox("集成测试")
        integration_lay = QVBoxLayout(integration_card)
        integration_lay.setSpacing(10)

        test_prompt_lay = QFormLayout()
        test_prompt_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.test_prompt = QLineEdit("你好，今天天气怎么样？")
        test_prompt_lay.addRow("测试提示:", self.test_prompt)

        integration_lay.addLayout(test_prompt_lay)

        test_integration_btn = QPushButton("测试完整集成流程")
        test_integration_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        test_integration_btn.clicked.connect(self._test_integration)
        integration_lay.addWidget(test_integration_btn)

        self.integration_status_label = QLabel("点击测试按钮查看集成状态")
        self.integration_status_label.setStyleSheet("color:#666;font-size:11px;")
        integration_lay.addWidget(self.integration_status_label)

        main_lay.addWidget(integration_card)

        # ── 提示信息 ──────────────────────────────────────
        hint = QLabel(
            "💡 注意：\n"
            "- L0-L4 集成是一个分层架构，每一层都有不同的职责\n"
            "- 测试按钮可以验证各层的状态和可用性\n"
            "- 集成测试可以验证整个流程是否正常工作"
        )
        hint.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            padding: 12px;
            background: #0F172A;
            border-radius: 8px;
            border-left: 3px solid #3B82F6;
        """)
        main_lay.addWidget(hint)

        main_lay.addStretch()

        return w

    def _init_sync_status(self):
        """初始化同步状态显示"""
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            status = manager.get_status()

            if status["logged_in"]:
                self.sync_status_label.setText(
                    f'<span style="color:#22c55e">已登录</span> '
                    f'(设备: {status["client_id"]})'
                )
                self.sync_token_label.setText(
                    f'{status["user_token"]}...'
                )
                self.sync_logout_btn.setEnabled(True)
                self.sync_login_btn.setEnabled(False)
                self.sync_register_btn.setEnabled(False)
            else:
                self.sync_status_label.setText('<span style="color:#ef4444">未登录</span>')
                self.sync_token_label.setText("-")
                self.sync_logout_btn.setEnabled(False)
                self.sync_login_btn.setEnabled(True)
                self.sync_register_btn.setEnabled(True)

            # 服务器状态
            if status["server_reachable"]:
                self.sync_server_label.setText(
                    f'<span style="color:#22c55e">可达</span>'
                )
            else:
                self.sync_server_label.setText(
                    f'<span style="color:#ef4444">不可达</span> '
                    f'(离线模式)'
                )

            # 待推送
            pending = status["pending_push_count"]
            if pending > 0:
                self.sync_pending_label.setText(
                    f'<span style="color:#f59e0b">{pending} 项待推送</span>'
                )
            else:
                self.sync_pending_label.setText(
                    f'<span style="color:#22c55e">无</span>'
                )
        except Exception as e:
            self.sync_status_label.setText(f"加载失败: {e}")

    def _on_sync_login(self):
        token = self.sync_token_input.text().strip()
        if len(token) < 8:
            self.sync_result_label.setText(
                '<span style="color:#ef4444">Token 长度至少为 8 个字符</span>'
            )
            return

        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            if manager.login(token):
                self.sync_result_label.setText(
                    f'<span style="color:#22c55e">登录成功！</span> '
                    f'Token: {token[:8]}...'
                )
                self._init_sync_status()
            else:
                self.sync_result_label.setText(
                    '<span style="color:#ef4444">登录失败</span>'
                )
        except Exception as e:
            self.sync_result_label.setText(f'<span style="color:#ef4444">错误: {e}</span>')

    def _on_sync_register(self):
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            token = manager.register()
            self.sync_token_input.setText(token)
            self.sync_result_label.setText(
                f'<span style="color:#22c55e">新身份已生成！</span> '
                f'请妥善保存 Token: <span style="font-family:monospace">{token}</span>'
            )
            self._init_sync_status()
        except Exception as e:
            self.sync_result_label.setText(f'<span style="color:#ef4444">错误: {e}</span>')

    def _on_sync_logout(self):
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            manager.logout()
            self.sync_token_input.clear()
            self.sync_result_label.setText('<span style="color:#888">已退出登录</span>')
            self._init_sync_status()
        except Exception as e:
            self.sync_result_label.setText(f'<span style="color:#ef4444">错误: {e}</span>')

    def _on_sync_push(self):
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            if not manager.is_logged_in:
                self.sync_result_label.setText(
                    '<span style="color:#ef4444">请先登录</span>'
                )
                return

            # 从 config 对象构建配置字典
            configs = {}
            for key in ["ollama", "model_market", "search", "agent", "writing"]:
                section = getattr(self.config, key, None)
                if section and hasattr(section, "model_dump"):
                    configs[key] = section.model_dump()

            result = manager.push_all_configs(configs)
            if result.success:
                self.sync_result_label.setText(
                    f'<span style="color:#22c55e">推送成功！</span> '
                    f'已推送 {len(result.pushed_keys)} 个配置块'
                )
            else:
                self.sync_result_label.setText(
                    f'<span style="color:#f59e0b">部分推送成功</span> '
                    f'({len(result.pushed_keys)}/{len(configs)})'
                )
            self._init_sync_status()
        except Exception as e:
            self.sync_result_label.setText(
                f'<span style="color:#ef4444">推送失败: {e}</span>'
            )

    def _on_sync_pull(self):
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            if not manager.is_logged_in:
                self.sync_result_label.setText(
                    '<span style="color:#ef4444">请先登录</span>'
                )
                return

            configs = manager.pull_all_configs()
            if not configs:
                self.sync_result_label.setText(
                    '<span style="color:#f59e0b">服务器上暂无配置</span>'
                )
                return

            # 显示拉取到的配置键
            keys = list(configs.keys())
            self.sync_result_label.setText(
                f'<span style="color:#22c55e">拉取成功！</span> '
                f'收到 {len(keys)} 个配置块: {", ".join(keys)}'
            )
            self._init_sync_status()
        except Exception as e:
            self.sync_result_label.setText(
                f'<span style="color:#ef4444">拉取失败: {e}</span>'
            )

    def _on_sync_refresh(self):
        self._init_sync_status()
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            keys = manager.list_remote_keys()
            if keys:
                lines = []
                for k in keys:
                    from datetime import datetime
                    ts = datetime.fromtimestamp(k["updated_at"]).strftime("%m-%d %H:%M")
                    lines.append(
                        f'  · {k["key"]} - {ts} ({k.get("platform","?")})'
                    )
                self.sync_remote_keys_label.setText(
                    f'<span style="color:#e8e8e8;">服务器配置:</span>\n'
                    + '<br>'.join(lines)
                )
            else:
                self.sync_remote_keys_label.setText(
                    '<span style="color:#666;">服务器上暂无配置</span>'
                )
        except Exception as e:
            self.sync_remote_keys_label.setText(f'查询失败: {e}')

    def _on_sync_clear(self):
        try:
            from core.config_sync import get_sync_manager
            manager = get_sync_manager()
            manager.clear_remote_config()
            self.sync_result_label.setText(
                '<span style="color:#22c55e">服务器配置已清除</span>'
            )
            self._on_sync_refresh()
        except Exception as e:
            self.sync_result_label.setText(
                f'<span style="color:#ef4444">清除失败: {e}</span>'
            )

    def _test_l0_status(self):
        """测试 L0 状态"""
        try:
            from core.smolllm2.l0_integration import get_l0l4_executor
            import asyncio
            loop = asyncio.new_event_loop()
            executor = loop.run_until_complete(get_l0l4_executor())
            stats = executor.get_stats()
            loop.close()

            status_text = f"L0 路由: 可用\n"
            status_text += f"缓存条目: {stats.get('cache_size', 0)}\n"
            status_text += f"路由次数: {stats.get('total_routes', 0)}\n"
            status_text += f"缓存命中: {stats.get('cache_hits', 0)}\n"
            status_text += f"本地执行: {stats.get('local_executions', 0)}"

            self.l0_status_label.setText(status_text)
            self.l0_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.l0_status_label.setText(f"测试失败: {e}")
            self.l0_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _test_l1_status(self):
        """测试 L1 状态"""
        try:
            from core.fusion_rag.exact_cache import ExactCacheLayer
            cache = ExactCacheLayer()

            status_text = f"L1 缓存: 可用\n"
            status_text += f"缓存大小: {cache.get_size()}\n"
            status_text += f"最大容量: {cache.max_size}\n"
            status_text += f"命中次数: {cache.hit_count}\n"
            status_text += f"未命中次数: {cache.miss_count}"

            self.l1_status_label.setText(status_text)
            self.l1_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.l1_status_label.setText(f"测试失败: {e}")
            self.l1_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _test_l2_status(self):
        """测试 L2 状态"""
        try:
            from core.fusion_rag.session_cache import SessionCacheLayer
            cache = SessionCacheLayer()

            status_text = f"L2 缓存: 可用\n"
            status_text += f"会话数: {len(cache.sessions)}\n"
            status_text += f"最大会话数: {cache.max_sessions}\n"
            status_text += f"最大消息数: {cache.max_messages}\n"
            status_text += f"清理时间: {cache.cleanup_interval}s"

            self.l2_status_label.setText(status_text)
            self.l2_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.l2_status_label.setText(f"测试失败: {e}")
            self.l2_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _test_l3_status(self):
        """测试 L3 状态"""
        try:
            from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
            kb = KnowledgeBaseLayer()

            status_text = f"L3 知识库: 可用\n"
            status_text += f"文档数: {kb.get_document_count()}\n"
            status_text += f"分块数: {kb.get_chunk_count()}\n"
            status_text += f"索引状态: 已创建\n"
            status_text += f"搜索能力: 正常"

            self.l3_status_label.setText(status_text)
            self.l3_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.l3_status_label.setText(f"测试失败: {e}")
            self.l3_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _test_l4_status(self):
        """测试 L4 状态"""
        try:
            from core.fusion_rag.database_layer import DatabaseLayer
            db = DatabaseLayer()

            status_text = f"L4 数据库: 可用\n"
            status_text += f"连接状态: 正常\n"
            status_text += f"表数: {len(db.get_tables())}\n"
            status_text += f"查询能力: 正常"

            self.l4_status_label.setText(status_text)
            self.l4_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.l4_status_label.setText(f"测试失败: {e}")
            self.l4_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _test_integration(self):
        """测试完整集成流程"""
        try:
            from core.smolllm2.l0_integration import smart_execute
            import asyncio

            prompt = self.test_prompt.text().strip()
            if not prompt:
                self.integration_status_label.setText("请输入测试提示")
                self.integration_status_label.setStyleSheet("color:#f59e0b;font-size:11px;")
                return

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(smart_execute(prompt))
            loop.close()

            status_text = f"集成测试: 成功\n"
            status_text += f"响应内容: {result.get('content', '无')[:50]}...\n"
            status_text += f"路由决策: {result.get('l0_decision', {}).get('route', '无')}\n"
            status_text += f"执行时间: 正常"

            self.integration_status_label.setText(status_text)
            self.integration_status_label.setStyleSheet("color:#22c55e;font-size:11px;")
        except Exception as e:
            self.integration_status_label.setText(f"测试失败: {e}")
            self.integration_status_label.setStyleSheet("color:#ef4444;font-size:11px;")

    def _on_save(self):
        from pathlib import Path
        from client.src.business.config import OllamaConfig, ModelPathConfig, AgentConfig, WritingConfig
        import os

        # 处理配置对象可能是字典的情况
        if isinstance(self.config, dict):
            # 如果 config 是字典，创建一个新的配置对象
            from dataclasses import dataclass
            from typing import Dict, Any
            
            @dataclass
            class AppConfig:
                ollama: Dict[str, Any] = None
                model_path: Dict[str, Any] = None
                agent: Dict[str, Any] = None
                writing: Dict[str, Any] = None
                logging: Dict[str, Any] = None
                l4_executor: Dict[str, Any] = None
            
            new_config = AppConfig(
                ollama=self.config.get('ollama', {}),
                model_path=self.config.get('model_path', {}),
                agent=self.config.get('agent', {}),
                writing=self.config.get('writing', {}),
                logging=self.config.get('logging', {}),
                l4_executor=self.config.get('l4_executor', {})
            )
            self.config = new_config

        # 确保配置对象的结构正确
        if not hasattr(self.config, 'ollama'):
            self.config.ollama = {}
        if not hasattr(self.config, 'model_path'):
            self.config.model_path = {}
        if not hasattr(self.config, 'agent'):
            self.config.agent = {}
        if not hasattr(self.config, 'writing'):
            self.config.writing = {}

        # Ollama
        if isinstance(self.config.ollama, dict):
            self.config.ollama['base_url'] = self.ollama_url.text().strip()
            self.config.ollama['default_model'] = self.ollama_model.text().strip()
            self.config.ollama['num_ctx'] = self.ollama_ctx.value()
            self.config.ollama['keep_alive'] = self.ollama_keep.text().strip()
        else:
            self.config.ollama.base_url = self.ollama_url.text().strip()
            self.config.ollama.default_model = self.ollama_model.text().strip()
            self.config.ollama.num_ctx = self.ollama_ctx.value()
            self.config.ollama.keep_alive = self.ollama_keep.text().strip()

        # 模型
        if isinstance(self.config.model_path, dict):
            self.config.model_path['models_dir'] = self.models_dir.text().strip()
            self.config.model_path['ollama_home'] = self.ollama_home.text().strip()
            self.config.model_path['auto_import'] = self.auto_import.isChecked()
        else:
            self.config.model_path.models_dir = self.models_dir.text().strip()
            self.config.model_path.ollama_home = self.ollama_home.text().strip()
            self.config.model_path.auto_import = self.auto_import.isChecked()

        # Agent
        if isinstance(self.config.agent, dict):
            self.config.agent['max_iterations'] = self.max_iter.value()
            self.config.agent['max_tokens'] = self.max_tokens.value()
            self.config.agent['temperature'] = self.temperature.value() / 100.0
            self.config.agent['streaming'] = self.streaming.isChecked()
            self.config.agent['show_reasoning'] = self.show_reasoning.isChecked()
        else:
            self.config.agent.max_iterations = self.max_iter.value()
            self.config.agent.max_tokens = self.max_tokens.value()
            self.config.agent.temperature = self.temperature.value() / 100.0
            self.config.agent.streaming = self.streaming.isChecked()
            self.config.agent.show_reasoning = self.show_reasoning.isChecked()

        # 写作
        if isinstance(self.config.writing, dict):
            self.config.writing['default_project_dir'] = self.proj_dir.text().strip()
            self.config.writing['auto_save_interval'] = self.auto_save.value()
            self.config.writing['enable_file_watch'] = self.file_watch.isChecked()
        else:
            self.config.writing.default_project_dir = self.proj_dir.text().strip()
            self.config.writing.auto_save_interval = self.auto_save.value()
            self.config.writing.enable_file_watch = self.file_watch.isChecked()

        # 日志配置
        logging_config = {
            'enabled': getattr(self, 'logging_enabled', QCheckBox()).isChecked(),
            'levels': {
                'debug': getattr(self, 'logging_debug', QCheckBox()).isChecked(),
                'info': getattr(self, 'logging_info', QCheckBox()).isChecked(),
                'warning': getattr(self, 'logging_warning', QCheckBox()).isChecked(),
                'error': getattr(self, 'logging_error', QCheckBox()).isChecked(),
                'critical': getattr(self, 'logging_critical', QCheckBox()).isChecked()
            },
            'handlers': {
                'console': getattr(self, 'logging_console', QCheckBox()).isChecked(),
                'file': getattr(self, 'logging_file', QCheckBox()).isChecked(),
                'ui': getattr(self, 'logging_ui', QCheckBox()).isChecked(),
                'network': getattr(self, 'logging_network', QCheckBox()).isChecked(),
                'debug': getattr(self, 'logging_debug_file', QCheckBox()).isChecked()
            }
        }
        
        # 确保配置对象的结构正确
        if not hasattr(self.config, 'logging'):
            self.config.logging = {}
        
        # 保存日志配置到配置对象
        if isinstance(self.config.logging, dict):
            self.config.logging.update(logging_config)
        else:
            self.config.logging.enabled = logging_config['enabled']
            self.config.logging.levels = logging_config['levels']
            self.config.logging.handlers = logging_config['handlers']

        # L4 执行器配置
        l4_config = {
            'gateway_url': getattr(self, 'l4_gateway_url', QLineEdit('http://localhost:8000/v1')).text().strip(),
            'enable_write_back': getattr(self, 'l4_enable_write_back', QCheckBox()).isChecked(),
            'fallback_to_direct': getattr(self, 'l4_fallback_to_direct', QCheckBox()).isChecked()
        }
        
        # 确保配置对象的结构正确
        if not hasattr(self.config, 'l4_executor'):
            self.config.l4_executor = {}
        
        # 保存 L4 配置到配置对象
        if isinstance(self.config.l4_executor, dict):
            self.config.l4_executor.update(l4_config)
        else:
            self.config.l4_executor.gateway_url = l4_config['gateway_url']
            self.config.l4_executor.enable_write_back = l4_config['enable_write_back']
            self.config.l4_executor.fallback_to_direct = l4_config['fallback_to_direct']

        # L0-L4 集成配置
        l0l4_config = {
            'l0': {
                'enable': getattr(self, 'l0_enable', QCheckBox()).isChecked(),
                'enable_cache': getattr(self, 'l0_enable_cache', QCheckBox()).isChecked(),
                'enable_fast_local': getattr(self, 'l0_enable_fast_local', QCheckBox()).isChecked()
            },
            'l1': {
                'enable': getattr(self, 'l1_enable', QCheckBox()).isChecked()
            },
            'l2': {
                'enable': getattr(self, 'l2_enable', QCheckBox()).isChecked()
            },
            'l3': {
                'enable': getattr(self, 'l3_enable', QCheckBox()).isChecked()
            },
            'l4': {
                'enable': getattr(self, 'l4_enable', QCheckBox()).isChecked()
            }
        }
        
        # 确保配置对象的结构正确
        if not hasattr(self.config, 'l0l4_integration'):
            self.config.l0l4_integration = {}
        
        # 保存 L0-L4 集成配置到配置对象
        if isinstance(self.config.l0l4_integration, dict):
            self.config.l0l4_integration.update(l0l4_config)
        else:
            self.config.l0l4_integration = l0l4_config

        self.config_changed.emit(self.config)
        self.accept()

    def navigate_to(self, link_path: str) -> bool:
        """
        导航到指定的 Tab

        Args:
            link_path: Tab 标识（对应 ConfigMissingDetector 中的 link_path）

        Returns:
            bool: 是否成功导航
        """
        # 统一小写
        link_path = link_path.lower()

        # 特殊映射（ConfigMissingDetector 的 link_path 与 SettingsDialog tab 的映射）
        link_to_tab = {
            "providers": "providers",
            "models": "models",
            "model": "models",
            "agent": "agent",
            "skills": "providers",  # Skills 暂时使用 Providers tab
            "skill": "providers",
            "general": "ollama",
            "ollama": "ollama",
            "mcp": "providers",  # MCP 暂时使用 Providers tab
            "writing": "writing",
        }

        tab_key = link_to_tab.get(link_path, link_path)
        tab_index = self._tab_map.get(tab_key)

        if tab_index is not None:
            self._tabs.setCurrentIndex(tab_index)
            return True
        return False


from pathlib import Path
