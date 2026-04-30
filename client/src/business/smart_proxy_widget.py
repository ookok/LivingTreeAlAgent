"""
SmartProxyWidget - 智能代理管理UI组件
=====================================

集成功能：
1. 代理源管理（添加/删除/启用/翻页）
2. 白名单配置（开发/Git/AI/ML/IDE）
3. Git代理配置
4. 应用代理配置
5. 健康监测与状态显示

使用方式：
    from business.smart_proxy_widget import SmartProxyWidget

    widget = SmartProxyWidget()
    layout.addWidget(widget)
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QSpinBox, QListWidget,
    QListWidgetItem, QFormLayout, QGroupBox, QSplitter,
    QFrame, QScrollArea, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class ProxyStatsWidget(QWidget):
    """代理统计显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # 代理池统计
        self.pool_label = QLabel("代理池: 0")
        self.pool_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.pool_label)

        layout.addSpacing(20)

        # 代理源统计
        self.sources_label = QLabel("代理源: 0 (0 启用)")
        layout.addWidget(self.sources_label)

        layout.addSpacing(20)

        # 白名单统计
        self.whitelist_label = QLabel("白名单: 0 条规则")
        layout.addWidget(self.whitelist_label)

        layout.addStretch()

        # 状态指示灯
        self.status_label = QLabel("●")
        self.status_label.setStyleSheet("color: gray; font-size: 20px;")
        layout.addWidget(self.status_label)

        self.status_text = QLabel("未启用")
        layout.addWidget(self.status_text)

    def update_stats(self, stats: Dict[str, Any]):
        """更新统计信息"""
        # 代理池
        total = stats.get("total", 0)
        by_protocol = stats.get("by_protocol", {})
        proto_str = ", ".join([f"{k}: {v}" for k, v in by_protocol.items()])
        self.pool_label.setText(f"代理池: {total} ({proto_str})")

        # 代理源
        enabled = stats.get("enabled_sources", 0)
        total_sources = stats.get("total_sources", 0)
        self.sources_label.setText(f"代理源: {total_sources} ({enabled} 启用)")

        # 白名单（需要传入）
        whitelist_count = stats.get("whitelist_count", 0)
        self.whitelist_label.setText(f"白名单: {whitelist_count} 条规则")

        # 状态
        enable_proxy = stats.get("enable_proxy", False)
        if enable_proxy:
            self.status_label.setStyleSheet("color: green; font-size: 20px;")
            self.status_text.setText("运行中")
        else:
            self.status_label.setStyleSheet("color: gray; font-size: 20px;")
            self.status_text.setText("未启用")


class ProxySourceListWidget(QWidget):
    """代理源列表组件"""

    source_toggled = pyqtSignal(str, bool)  # source_id, enabled
    source_remove = pyqtSignal(str)  # source_id
    source_add = pyqtSignal(dict)  # source config

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sources: List[Dict] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题栏
        header = QHBoxLayout()
        header.addWidget(QLabel("代理源"))
        header.addStretch()

        self.add_btn = QPushButton("+ 添加")
        self.add_btn.clicked.connect(self._on_add_clicked)
        header.addWidget(self.add_btn)

        self.reload_btn = QPushButton("↻ 刷新")
        self.reload_btn.clicked.connect(self._on_reload_clicked)
        header.addWidget(self.reload_btn)

        layout.addLayout(header)

        # 源列表
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

    def set_sources(self, sources: List[Dict]):
        """设置代理源列表"""
        self._sources = sources
        self.list_widget.clear()

        for source in sources:
            item = QListWidgetItem(source.get("name", source.get("id", "Unknown")))
            item.setCheckState(Qt.CheckState.Checked if source.get("enabled", True) else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, source.get("id"))
            self.list_widget.addItem(item)

    def _on_item_changed(self, item):
        """项状态改变"""
        source_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        self.source_toggled.emit(source_id, enabled)

    def _on_add_clicked(self):
        """添加代理源"""
        # 简化实现：使用预定义的源
        from business.smart_proxy_gateway import ProxySource, ProxySourceType

        predefined = [
            {"id": "scdn", "name": "SCDN代理池", "url": "https://proxy.scdn.io/api/get_proxy.php"},
            {"id": "proxyscrape", "name": "ProxyScrape", "url": "https://api.proxyscrape.com/..."},
            {"id": "89ip", "name": "89免费代理", "url": "https://www.89ip.cn/index_{page}.html"},
            {"id": "kuaidaili", "name": "快代理", "url": "https://www.kuaidaili.com/free/inha/{page}/"},
            {"id": "geonode", "name": "Geonode", "url": "https://proxyscrape.pro/api/v2/..."},
            {"id": "proxy-list-download", "name": "Proxy-List", "url": "https://www.proxy-list.download/api/v1/..."},
        ]

        # 发送信号让主窗口处理
        self.source_add.emit({"sources": predefined})

    def _on_reload_clicked(self):
        """刷新代理源"""
        self.reload_btn.setEnabled(False)
        QTimer.singleShot(1000, lambda: self.reload_btn.setEnabled(True))


class WhiteListConfigWidget(QWidget):
    """白名单配置组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 白名单分类
        tabs = QTabWidget()

        # 开发/问答
        tabs.addTab(self._create_category_widget([
            ("GitHub", "github.com"),
            ("GitLab", "gitlab.com"),
            ("BitBucket", "bitbucket.org"),
            ("StackOverflow", "stackoverflow.com"),
            ("Dev.to", "dev.to"),
            ("Reddit", "reddit.com"),
        ]), "开发/问答")

        # AI/ML
        tabs.addTab(self._create_category_widget([
            ("HuggingFace", "huggingface.co"),
            ("ArXiv", "arxiv.org"),
            ("PapersWithCode", "paperswithcode.com"),
            ("OpenRouter", "openrouter.ai"),
            ("Groq", "groq.com"),
            ("Anthropic", "api.anthropic.com"),
        ]), "AI/ML")

        # 模型市场
        tabs.addTab(self._create_category_widget([
            ("HuggingFace Models", "models.huggingface.co"),
            ("OpenRouter API", "api.openrouter.ai"),
            ("Groq API", "api.groq.com"),
            ("OpenAI API", "api.openai.com"),
            ("Cohere API", "api.cohere.ai"),
            ("Mistral API", "api.mistral.ai"),
        ]), "模型市场")

        # Skills市场
        tabs.addTab(self._create_category_widget([
            ("WorkBuddy Skills", "workbuddy.com"),
            ("CodeBuddy", "codebuddy.cn"),
            ("MCP Servers", "github.com/mcp-servers"),
        ]), "Skills市场")

        # IDE模块（LivingTreeAlAgent）
        tabs.addTab(self._create_category_widget([
            ("LivingTreeAlAgent", "IDE智能模块"),
            ("Ollama (本地模型)", "Ollama API"),
            ("Models API", "IDE模型接口"),
        ]), "IDE模块")

        # Git托管
        tabs.addTab(self._create_category_widget([
            ("GitHub", "github.com, githubusercontent.com"),
            ("GitLab", "gitlab.com"),
            ("BitBucket", "bitbucket.org"),
            ("HuggingFace", "huggingface.co"),
            ("ModelScope", "modelscope.cn"),
            ("Gitee", "gitee.com"),
        ]), "Git托管")

        layout.addWidget(tabs)

    def _create_category_widget(self, items: List[tuple]) -> QWidget:
        """创建分类组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        for name, domain in items:
            row = QHBoxLayout()
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            checkbox.setEnabled(False)  # 只读
            row.addWidget(checkbox)
            row.addWidget(QLabel(domain))
            row.addStretch()
            layout.addLayout(row)

        layout.addStretch()
        return widget


class GitProxyConfigWidget(QWidget):
    """Git代理配置组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 代理地址输入
        proxy_group = QGroupBox("代理配置")
        proxy_layout = QFormLayout()

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")
        proxy_layout.addRow("代理地址:", self.proxy_input)

        self.apply_btn = QPushButton("应用Git配置")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        proxy_layout.addRow("", self.apply_btn)

        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # Git服务快捷配置
        services_group = QGroupBox("快捷配置")
        services_layout = QVBoxLayout()

        services_layout.addWidget(QLabel("选择要配置代理的Git服务:"))

        self.github_cb = QCheckBox("GitHub (github.com)")
        self.github_cb.setChecked(True)
        services_layout.addWidget(self.github_cb)

        self.gitlab_cb = QCheckBox("GitLab (gitlab.com)")
        services_layout.addWidget(self.gitlab_cb)

        self.huggingface_cb = QCheckBox("HuggingFace (huggingface.co)")
        services_layout.addWidget(self.huggingface_cb)

        self.modelscope_cb = QCheckBox("ModelScope (modelscope.cn)")
        services_layout.addWidget(self.modelscope_cb)

        services_layout.addStretch()
        services_group.setLayout(services_layout)
        layout.addWidget(services_group)

        # 配置预览
        preview_group = QGroupBox("配置预览")
        preview_layout = QVBoxLayout()

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_edit)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        self.preview_edit.setPlainText(
            "# Git配置预览\n"
            "# 配置后将在 ~/.gitconfig 中添加代理设置"
        )

        # 连接信号
        self.proxy_input.textChanged.connect(self._update_preview)

    def _update_preview(self):
        """更新配置预览"""
        proxy = self.proxy_input.text().strip()

        if not proxy:
            self.preview_edit.setPlainText(
                "# Git配置预览\n"
                "# 请输入代理地址"
            )
            return

        preview = f"""# Git Proxy Configuration
# Generated by SmartProxyGateway

[http]
    proxy = {proxy}

[https]
    proxy = {proxy}

# 域名特定配置
[http "https://github.com/"]
    proxy = {proxy}

[http "https://gitlab.com/"]
    proxy = {proxy}

[http "https://huggingface.co/"]
    proxy = {proxy}
"""
        self.preview_edit.setPlainText(preview)

    def _on_apply_clicked(self):
        """应用配置"""
        from business.git_proxy_config import GitProxyConfig

        proxy = self.proxy_input.text().strip()
        if not proxy:
            return

        config = GitProxyConfig()

        if self.github_cb.isChecked():
            config.enable_github_proxy(proxy)

        if self.gitlab_cb.isChecked():
            config.enable_gitlab_proxy(proxy)

        if self.huggingface_cb.isChecked():
            config.enable_huggingface_proxy(proxy)

        if self.modelscope_cb.isChecked():
            config.add_domain_proxy("modelscope.cn", proxy)

        success = config.apply_config()

        if success:
            self.preview_edit.setPlainText(
                "# Git配置已成功应用!\n"
                f"# 代理地址: {proxy}\n"
                "# 请重启终端或重新打开Git Bash使配置生效"
            )
        else:
            self.preview_edit.setPlainText("# 配置应用失败，请检查错误信息")


class AppProxyConfigWidget(QWidget):
    """应用代理配置组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 代理地址
        proxy_layout = QFormLayout()
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")
        proxy_layout.addRow("代理地址:", self.proxy_input)

        self.export_btn = QPushButton("导出环境变量")
        self.export_btn.clicked.connect(self._on_export_clicked)
        proxy_layout.addRow("", self.export_btn)

        proxy_group = QGroupBox("环境变量配置")
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # AI服务配置
        ai_group = QGroupBox("AI/ML服务")
        ai_layout = QVBoxLayout()

        self.services = {}
        ai_services = [
            ("openai", "OpenAI API"),
            ("anthropic", "Anthropic"),
            ("groq", "Groq"),
            ("openrouter", "OpenRouter"),
            ("huggingface", "HuggingFace"),
            ("cohere", "Cohere"),
            ("mistral", "Mistral"),
        ]

        for service_id, service_name in ai_services:
            cb = QCheckBox(service_name)
            ai_layout.addWidget(cb)
            self.services[service_id] = cb

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        # Skills/IDE配置
        other_group = QGroupBox("Skills/IDE市场")
        other_layout = QVBoxLayout()

        self.workbuddy_cb = QCheckBox("WorkBuddy Skills")
        other_layout.addWidget(self.workbuddy_cb)

        self.mcp_cb = QCheckBox("MCP Servers")
        other_layout.addWidget(self.mcp_cb)

        self.codebuddy_cb = QCheckBox("CodeBuddy")
        other_layout.addWidget(self.codebuddy_cb)

        # IDE模块
        ide_label = QLabel("IDE模块:")
        ide_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        other_layout.addWidget(ide_label)

        self.living_tree_cb = QCheckBox("LivingTreeAlAgent (IDE)")
        self.living_tree_cb.setChecked(True)
        other_layout.addWidget(self.living_tree_cb)

        self.ollama_cb = QCheckBox("Ollama (本地模型)")
        other_layout.addWidget(self.ollama_cb)

        other_group.setLayout(other_layout)
        layout.addWidget(other_group)

        # 环境变量预览
        preview_group = QGroupBox("环境变量预览")
        preview_layout = QVBoxLayout()

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_edit)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        self.proxy_input.textChanged.connect(self._update_preview)

    def _update_preview(self):
        """更新预览"""
        proxy = self.proxy_input.text().strip()

        if not proxy:
            self.preview_edit.setPlainText("# 请输入代理地址")
            return

        lines = [
            "# Environment Variables",
            f"export HTTP_PROXY=\"{proxy}\"",
            f"export HTTPS_PROXY=\"{proxy}\"",
            "",
        ]

        # AI服务
        enabled_ai = [name for sid, cb in self.services.items() if cb.isChecked()]
        if enabled_ai:
            lines.append("# AI/ML Services")
            for sid in enabled_ai:
                if sid == "openai":
                    lines.append(f"export OPENAI_PROXY=\"{proxy}\"")
                elif sid == "anthropic":
                    lines.append(f"export ANTHROPIC_PROXY=\"{proxy}\"")
                elif sid == "groq":
                    lines.append(f"export GROQ_PROXY=\"{proxy}\"")
                elif sid == "openrouter":
                    lines.append(f"export OPENROUTER_PROXY=\"{proxy}\"")
                elif sid == "huggingface":
                    lines.append(f"export HF_ENDPOINT_PROXY=\"{proxy}\"")

        self.preview_edit.setPlainText("\n".join(lines))

    def _on_export_clicked(self):
        """导出环境变量"""
        from business.app_proxy_config import AppProxyConfig

        proxy = self.proxy_input.text().strip()
        if not proxy:
            return

        config = AppProxyConfig()
        config.set_proxy(proxy)

        # 添加选中的AI服务
        for sid, cb in self.services.items():
            if cb.isChecked():
                config.enable_ai_service(sid)

        # 添加Skills市场
        if self.workbuddy_cb.isChecked():
            config.enable_skill_market("workbuddy")
        if self.mcp_cb.isChecked():
            config.enable_skill_market("mcp")
        if self.codebuddy_cb.isChecked():
            config.enable_skill_market("codebuddy")

        # 添加IDE模块代理
        if self.living_tree_cb.isChecked():
            config.enable_ide_module("living_tree")
        if self.ollama_cb.isChecked():
            config.enable_ide_module("ide_ollama")

        # 导出
        import platform
        if platform.system() == "Windows":
            script = config.export_powershell_script()
        else:
            script = config.export_shell_script()

        self.preview_edit.setPlainText(
            script + "\n\n# 请在终端中执行或添加到配置文件"
        )


class SmartProxyWidget(QWidget):
    """
    智能代理管理完整UI组件

    集成所有代理配置功能
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gateway = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("🔗 智能代理网关")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        # 主开关
        self.enable_btn = QPushButton("启用代理")
        self.enable_btn.setCheckable(True)
        self.enable_btn.clicked.connect(self._on_enable_changed)
        header.addWidget(self.enable_btn)

        main_layout.addLayout(header)

        # 统计栏
        self.stats_widget = ProxyStatsWidget()
        main_layout.addWidget(self.stats_widget)

        # 主内容区
        tabs = QTabWidget()

        # 代理源管理
        tabs.addTab(self._create_sources_tab(), "代理源")

        # 白名单配置
        tabs.addTab(WhiteListConfigWidget(), "白名单")

        # Git代理
        tabs.addTab(GitProxyConfigWidget(), "Git代理")

        # 应用代理
        tabs.addTab(AppProxyConfigWidget(), "应用代理")

        # 监测状态
        tabs.addTab(self._create_monitor_tab(), "监测状态")

        main_layout.addWidget(tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

    def _create_sources_tab(self) -> QWidget:
        """创建代理源标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel(
            "管理代理来源。SCDN API 每次最多获取 20 个代理，"
            "网页源会自动翻页获取更多代理。"
        )
        info.setStyleSheet("color: gray; padding: 10px;")
        layout.addWidget(info)

        # 代理源列表
        self.source_list = ProxySourceListWidget()
        self.source_list.source_toggled.connect(self._on_source_toggled)
        layout.addWidget(self.source_list, 1)

        return widget

    def _create_monitor_tab(self) -> QWidget:
        """创建监测状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 状态信息
        status_group = QGroupBox("代理池状态")
        status_layout = QFormLayout()

        self.total_proxies = QLabel("0")
        status_layout.addRow("总代理数:", self.total_proxies)

        self.http_count = QLabel("0")
        status_layout.addRow("HTTP代理:", self.http_count)

        self.https_count = QLabel("0")
        status_layout.addRow("HTTPS代理:", self.https_count)

        self.socks_count = QLabel("0")
        status_layout.addRow("SOCKS代理:", self.socks_count)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 日志
        log_group = QGroupBox("最近日志")
        log_layout = QVBoxLayout()

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group, 1)

        return widget

    def _on_enable_changed(self, checked: bool):
        """启用状态改变"""
        if checked:
            self.enable_btn.setText("禁用代理")
            self.status_bar.showMessage("代理已启用")
        else:
            self.enable_btn.setText("启用代理")
            self.status_bar.showMessage("代理已禁用")

        # 更新网关配置
        if self._gateway:
            self._gateway._config["enable_proxy"] = checked
            self._update_stats()

    def _on_source_toggled(self, source_id: str, enabled: bool):
        """代理源启用状态改变"""
        if self._gateway:
            self._gateway.enable_source(source_id, enabled)
            self._update_stats()

    def _update_stats(self):
        """更新统计信息"""
        if not self._gateway:
            from business.smart_proxy_gateway import get_gateway
            self._gateway = get_gateway()

        stats = self._gateway.get_pool_stats()
        whitelist_stats = self._gateway.get_whitelist_stats()

        self.stats_widget.update_stats({
            **stats,
            "whitelist_count": sum(whitelist_stats.values()),
            "enable_proxy": self._gateway._config.get("enable_proxy", False)
        })

        # 更新监测标签页
        self.total_proxies.setText(str(stats.get("total", 0)))

        by_protocol = stats.get("by_protocol", {})
        self.http_count.setText(str(by_protocol.get("http", 0)))
        self.https_count.setText(str(by_protocol.get("https", 0)))
        socks_total = by_protocol.get("socks4", 0) + by_protocol.get("socks5", 0)
        self.socks_count.setText(str(socks_total))
