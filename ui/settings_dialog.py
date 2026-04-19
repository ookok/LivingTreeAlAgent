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

        # ── Sync ─────────────────────────────────────────────
        sync_tab = self._build_sync_tab()
        tabs.addTab(sync_tab, "Sync")

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
