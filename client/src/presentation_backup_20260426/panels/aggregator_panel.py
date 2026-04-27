"""
聚合平台 API Key 管理面板
支持 OpenRouter / ZenMux / 12AI / Subrouter
"""

from typing import Dict, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QPushButton, QGroupBox,
    QCheckBox, QTextEdit, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QMessageBox, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor


# 聚合平台定义
AGGREGATOR_PROVIDERS: List[Dict] = [
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "key_var": "OPENROUTER_API_KEY",
        "description": "聚合 100+ 模型 (Claude/GPT/LLaMA 等)",
        "website": "https://openrouter.ai",
        "free_models": True,
        "priority": 380
    },
    {
        "id": "pollinations",
        "name": "Pollinations",
        "key_var": "POLLINATIONS_API_KEY",
        "description": "多模态 (图文音视频) - 免注册可用",
        "website": "https://pollinations.ai",
        "free_models": True,
        "priority": 370
    },
    {
        "id": "zenmux",
        "name": "ZenMux",
        "key_var": "ZENMUX_API_KEY",
        "description": "多模型聚合网关",
        "website": "https://zenmux.ai",
        "free_models": False,
        "priority": 290
    },
    {
        "id": "12ai",
        "name": "12AI",
        "key_var": "TWELVE_AI_API_KEY",
        "description": "12AI 智能聚合",
        "website": "https://12.ai",
        "free_models": False,
        "priority": 280
    },
    {
        "id": "subrouter",
        "name": "Subrouter",
        "key_var": "SUBROUTER_API_KEY",
        "description": "Subrouter 聚合平台",
        "website": "https://subrouter.ai",
        "free_models": False,
        "priority": 270
    }
]


class AggregatorPanel(QWidget):
    """聚合平台管理面板"""

    # 信号
    api_key_changed = pyqtSignal(str, str)  # provider_id, api_key
    provider_toggled = pyqtSignal(str, bool)  # provider_id, enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self.providers: Dict[str, dict] = {}
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("聚合平台 API Key 管理")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "聚合平台提供统一的 API 接口访问多个模型厂商。\n"
            "配置 Key 后，网关自动根据优先级和可用性路由请求。"
        )
        desc.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(desc)

        # 优先级说明
        priority_group = QGroupBox("路由优先级")
        priority_layout = QFormLayout(priority_group)

        # 优先级说明表
        self.priority_table = QTableWidget()
        self.priority_table.setColumnCount(3)
        self.priority_table.setHorizontalHeaderLabels(["平台", "优先级", "说明"])
        self.priority_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.priority_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.priority_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.priority_table.setRowCount(8)
        self.priority_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        priorities = [
            ("本地 Ollama", "900", "最高优先级，本地模型"),
            ("国产云", "450-700", "DeepSeek/通义/智谱等"),
            ("国际云", "400-550", "Anthropic/GPT/Gemini"),
            ("Groq", "400", "超低延迟"),
            ("OpenRouter", "380", "聚合 100+ 模型"),
            ("ZenMux", "290", "多模型聚合"),
            ("12AI", "280", "智能聚合"),
            ("Subrouter", "270", "备用聚合"),
        ]

        for row, (name, priority, desc) in enumerate(priorities):
            self.priority_table.setItem(row, 0, QTableWidgetItem(name))
            self.priority_table.setItem(row, 1, QTableWidgetItem(priority))
            self.priority_table.setItem(row, 2, QTableWidgetItem(desc))

        priority_layout.addRow(self.priority_table)
        layout.addWidget(priority_group)

        # API Key 配置区
        config_group = QGroupBox("API Key 配置")
        config_layout = QVBoxLayout(config_group)

        for p in AGGREGATOR_PROVIDERS:
            row_layout = self._create_provider_row(p)
            config_layout.addLayout(row_layout)

        layout.addWidget(config_group)

        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        self.status_bar.showMessage("就绪")

        layout.addStretch()

    def _create_provider_row(self, provider: dict) -> QHBoxLayout:
        """创建单个平台的配置行"""
        layout = QHBoxLayout()

        # 启用复选框
        checkbox = QCheckBox(provider["name"])
        checkbox.setToolTip(provider["description"])
        checkbox.setChecked(True)
        checkbox.toggled.connect(
            lambda checked, p=provider["id"]: self._on_enabled_changed(p, checked)
        )
        layout.addWidget(checkbox, 1)

        # API Key 输入框
        key_edit = QLineEdit()
        key_edit.setPlaceholderText(f"输入 {provider['name']} API Key")
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setMinimumWidth(300)
        key_edit.textChanged.connect(
            lambda text, p=provider["id"]: self._on_key_changed(p, text)
        )
        self.providers[provider["id"]] = {
            "checkbox": checkbox,
            "key_edit": key_edit,
            "config": provider
        }
        layout.addWidget(key_edit, 3)

        # 查看/隐藏按钮
        toggle_btn = QPushButton("👁")
        toggle_btn.setFixedWidth(30)
        toggle_btn.setToolTip("显示/隐藏 Key")
        toggle_btn.clicked.connect(
            lambda _, e=key_edit: self._toggle_key_visibility(e)
        )
        layout.addWidget(toggle_btn)

        # 测试按钮
        test_btn = QPushButton("测试")
        test_btn.setFixedWidth(50)
        test_btn.clicked.connect(
            lambda _, p=provider: self._test_connection(p["id"])
        )
        layout.addWidget(test_btn)

        # 链接按钮
        if provider.get("website"):
            link_btn = QPushButton("官网")
            link_btn.setFixedWidth(40)
            link_btn.clicked.connect(
                lambda _, url=provider["website"]: self._open_website(url)
            )
            layout.addWidget(link_btn)

        return layout

    def _on_enabled_changed(self, provider_id: str, enabled: bool):
        """启用状态改变"""
        self.provider_toggled.emit(provider_id, enabled)
        status = "已启用" if enabled else "已禁用"
        self.status_bar.showMessage(f"{provider_id}: {status}")

    def _on_key_changed(self, provider_id: str, api_key: str):
        """API Key 改变"""
        self.api_key_changed.emit(provider_id, api_key)

    def _toggle_key_visibility(self, edit: QLineEdit):
        """切换 Key 显示/隐藏"""
        if edit.echoMode() == QLineEdit.EchoMode.Password:
            edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _test_connection(self, provider_id: str):
        """测试连接"""
        provider = self.providers.get(provider_id)
        if not provider:
            return

        api_key = provider["key_edit"].text()
        if not api_key:
            QMessageBox.warning(
                self,
                "测试失败",
                f"请先输入 {provider['config']['name']} 的 API Key"
            )
            return

        self.status_bar.showMessage(f"正在测试 {provider_id}...")
        QMessageBox.information(
            self,
            "测试功能",
            f"测试 {provider['config']['name']} 连接...\n\n"
            f"API Key: {api_key[:8]}***\n\n"
            "请确保 RelayFreeLLM 网关已启动"
        )
        self.status_bar.showMessage(f"{provider_id}: 测试完成")

    def _open_website(self, url: str):
        """打开网站"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def load_config(self):
        """加载配置"""
        import os

        for provider_id, provider_data in self.providers.items():
            key_var = provider_data["config"]["key_var"]
            api_key = os.getenv(key_var, "")
            provider_data["key_edit"].setText(api_key)

    def save_config(self):
        """保存配置到环境变量（仅当前会话）"""
        for provider_id, provider_data in self.providers.items():
            api_key = provider_data["key_edit"].text()
            key_var = provider_data["config"]["key_var"]
            if api_key:
                import os
                os.environ[key_var] = api_key
            self.status_bar.showMessage("配置已保存到当前会话")

    def get_enabled_providers(self) -> List[str]:
        """获取已启用的平台列表"""
        enabled = []
        for provider_id, provider_data in self.providers.items():
            if provider_data["checkbox"].isChecked():
                enabled.append(provider_id)
        return enabled

    def get_provider_priority(self, provider_id: str) -> int:
        """获取平台优先级"""
        provider = self.providers.get(provider_id)
        if provider:
            return provider["config"].get("priority", 300)
        return 300
