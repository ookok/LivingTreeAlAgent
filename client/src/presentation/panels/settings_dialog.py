"""
设置对话框（升级版）
配置 Ollama 多地址、API 密钥、Agent 参数、L0-L4 分层路由等
所有敏感信息通过 encrypted_config 加密存储
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox,
    QPushButton, QGroupBox, QCheckBox, QTabWidget,
    QWidget, QFormLayout, QScrollArea, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QRadioButton, QButtonGroup,
)
from PyQt6.QtGui import QFont
from pathlib import Path
from typing import List, Dict, Optional

import json

from client.src.business.encrypted_config import (
    load_model_config, save_model_config,
    setup_default_configs
)


class SettingsDialog(QDialog):
    """设置对话框（升级版 - 支持多地址配置）"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings / 设置")
        self.setMinimumSize(950, 700)
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
            QPushButton#DangerButton {
                background: #991B1B;
                color: #FEE2E2;
            }
            QPushButton#DangerButton:hover {
                background: #7F1D1D;
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
            QListWidget {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
                color: #F1F5F9;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: #1E40AF;
                color: white;
            }
            QListWidget::item:hover {
                background: #334155;
            }
            QCheckBox {
                color: #E2E8F0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #475569;
                background: #1E293B;
            }
            QCheckBox::indicator:checked {
                background: #3B82F6;
                border-color: #3B82F6;
            }
        """)
        self._build_ui()
        self._load_from_encrypted_config()

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

        def create_scroll_tab(widget, title):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none;")
            scroll.setWidget(widget)
            tabs.addTab(scroll, title)

        # Tabs
        ollama_tab = self._build_ollama_tab()
        create_scroll_tab(ollama_tab, "Ollama")

        api_tab = self._build_api_tab()
        create_scroll_tab(api_tab, "API 配置")

        router_tab = self._build_router_tab()
        create_scroll_tab(router_tab, "L0-L4 路由")

        agent_tab = self._build_agent_tab()
        create_scroll_tab(agent_tab, "Agent")

        about_tab = self._build_about_tab()
        create_scroll_tab(about_tab, "关于")

        layout.addWidget(tabs, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("DangerButton")
        reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(reset_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("SaveButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    # ===================== Ollama 多地址配置 Tab =====================
    def _build_ollama_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        # 说明
        desc = QLabel(
            "配置 Ollama 服务器地址列表。支持多地址，按优先级自动选择。\n"
            "优先级 0 = 最高（优先使用），数字越大优先级越低。"
        )
        desc.setStyleSheet("color:#64748B;font-size:12px;padding:4px 0 8px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # 服务器列表
        list_group = QGroupBox("服务器地址列表")
        list_lay = QVBoxLayout(list_group)
        list_lay.setSpacing(8)

        self.ollama_list = QListWidget()
        self.ollama_list.setMaximumHeight(200)
        list_lay.addWidget(self.ollama_list)

        # 操作按钮
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(8)

        add_btn = QPushButton("添加服务器")
        add_btn.clicked.connect(self._on_ollama_add)
        btn_lay.addWidget(add_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._on_ollama_edit)
        btn_lay.addWidget(edit_btn)

        remove_btn = QPushButton("删除")
        remove_btn.setObjectName("DangerButton")
        remove_btn.clicked.connect(self._on_ollama_remove)
        btn_lay.addWidget(remove_btn)

        btn_lay.addStretch()

        move_up_btn = QPushButton("↑ 优先级提升")
        move_up_btn.clicked.connect(self._on_ollama_move_up)
        btn_lay.addWidget(move_up_btn)

        move_down_btn = QPushButton("↓ 优先级降低")
        move_down_btn.clicked.connect(self._on_ollama_move_down)
        btn_lay.addWidget(move_down_btn)

        list_lay.addLayout(btn_lay)
        lay.addWidget(list_group)

        # 模型列表（每个服务器对应的模型，用逗号分隔）
        models_group = QGroupBox("模型列表（所有服务器共用）")
        models_lay = QVBoxLayout(models_group)
        models_lay.setSpacing(8)

        models_hint = QLabel(
            "输入模型名称列表（逗号分隔），将应用到所有服务器地址。\n"
            "示例：qwen2.5:1.5b, qwen3.5:2b, qwen3.5:4b, qwen3.6:latest"
        )
        models_hint.setStyleSheet("color:#64748B;font-size:11px;")
        models_lay.addWidget(models_hint)

        self.ollama_models = QLineEdit()
        self.ollama_models.setPlaceholderText("qwen2.5:1.5b, qwen3.5:2b, qwen3.5:4b, ...")
        models_lay.addWidget(self.ollama_models)

        lay.addWidget(models_group)

        # 测试连接按钮
        test_btn = QPushButton("测试所有服务器连接")
        test_btn.clicked.connect(self._on_ollama_test)
        lay.addWidget(test_btn)

        lay.addStretch()
        return w

    def _render_ollama_list(self, servers: List[Dict]):
        """渲染服务器列表到 QListWidget"""
        self.ollama_list.clear()
        for i, srv in enumerate(servers):
            url = srv.get("url", "")
            priority = srv.get("priority", i)
            item_text = f"[优先级 {priority}]  {url}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, srv)
            self.ollama_list.addItem(item)

    def _on_ollama_add(self):
        url, ok = QInputDialog.getText(
            self, "添加 Ollama 服务器",
            "输入服务器地址（含端口）：",
            text="http://localhost:11434"
        )
        if ok and url.strip():
            # 读取当前配置
            cfg = load_model_config("ollama") or {}
            servers = cfg.get("servers", [])
            # 新服务器优先级 = 当前最大 + 1
            max_pri = max([s.get("priority", 0) for s in servers], default=-1)
            new_server = {
                "url": url.strip(),
                "priority": max_pri + 1,
                "models": [],
            }
            servers.append(new_server)
            cfg["servers"] = servers
            save_model_config("ollama", cfg)
            self._render_ollama_list(servers)
            QMessageBox.information(self, "成功", f"已添加服务器：{url}")

    def _on_ollama_edit(self):
        row = self.ollama_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个服务器")
            return
        item = self.ollama_list.item(row)
        srv_data = item.data(Qt.ItemDataRole.UserRole)
        url, ok = QInputDialog.getText(
            self, "编辑服务器地址",
            "修改服务器地址：",
            text=srv_data.get("url", "")
        )
        if ok and url.strip():
            cfg = load_model_config("ollama") or {}
            servers = cfg.get("servers", [])
            for s in servers:
                if s.get("url") == srv_data.get("url"):
                    s["url"] = url.strip()
                    break
            cfg["servers"] = servers
            save_model_config("ollama", cfg)
            self._render_ollama_list(servers)

    def _on_ollama_remove(self):
        row = self.ollama_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个服务器")
            return
        item = self.ollama_list.item(row)
        srv_data = item.data(Qt.ItemDataRole.UserRole)
        url = srv_data.get("url", "")

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除服务器 {url} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            cfg = load_model_config("ollama") or {}
            servers = cfg.get("servers", [])
            servers = [s for s in servers if s.get("url") != url]
            cfg["servers"] = servers
            save_model_config("ollama", cfg)
            self._render_ollama_list(servers)

    def _on_ollama_move_up(self):
        """提升优先级（减小 priority 数字）"""
        row = self.ollama_list.currentRow()
        if row <= 0:
            return
        cfg = load_model_config("ollama") or {}
        servers = cfg.get("servers", [])
        if row < len(servers):
            servers[row]["priority"] = max(servers[row].get("priority", row) - 1, 0)
            # 重新排序
            servers.sort(key=lambda x: x.get("priority", 999))
            cfg["servers"] = servers
            save_model_config("ollama", cfg)
            self._render_ollama_list(servers)
            self.ollama_list.setCurrentRow(max(row - 1, 0))

    def _on_ollama_move_down(self):
        """降低优先级（增大 priority 数字）"""
        row = self.ollama_list.currentRow()
        cfg = load_model_config("ollama") or {}
        servers = cfg.get("servers", [])
        if row < 0 or row >= len(servers) - 1:
            return
        servers[row]["priority"] = servers[row].get("priority", row) + 1
        servers.sort(key=lambda x: x.get("priority", 999))
        cfg["servers"] = servers
        save_model_config("ollama", cfg)
        self._render_ollama_list(servers)
        self.ollama_list.setCurrentRow(min(row + 1, len(servers) - 1))

    def _on_ollama_test(self):
        """测试所有服务器连接"""
        import asyncio
        from client.src.business.ollama_client import OllamaClient

        cfg = load_model_config("ollama") or {}
        servers = cfg.get("servers", [])
        if not servers:
            QMessageBox.warning(self, "提示", "请先添加服务器地址")
            return

        results = []
        for srv in servers:
            url = srv.get("url", "")
            try:
                client = OllamaClient(base_url=url)
                loop = asyncio.new_event_loop()
                ok = loop.run_until_complete(client.check_connection())
                loop.close()
                status = "✅ 连接成功" if ok else "❌ 连接失败"
            except Exception as e:
                status = f"❌ 异常：{e}"
            results.append(f"{url} → {status}")

        QMessageBox.information(self, "连接测试结果", "\n".join(results))

    # ===================== API 配置 Tab =====================
    def _build_api_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        # ── DeepSeek API ────────────────────────────────────
        ds_group = QGroupBox("DeepSeek API")
        ds_lay = QFormLayout(ds_group)
        ds_lay.setSpacing(12)
        ds_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ds_enabled = QCheckBox("启用 DeepSeek API")
        ds_lay.addRow("", self.ds_enabled)

        self.ds_api_key = QLineEdit()
        self.ds_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ds_api_key.setPlaceholderText("sk-...")
        ds_lay.addRow("API Key:", self.ds_api_key)

        self.ds_base_url = QLineEdit("https://api.deepseek.com")
        ds_lay.addRow("Base URL:", self.ds_base_url)

        # 模型配置
        ds_models_hint = QLabel("模型配置（JSON 格式，留空使用默认）")
        ds_models_hint.setStyleSheet("color:#64748B;font-size:11px;")
        ds_lay.addRow(ds_models_hint)

        self.ds_models_json = QLineEdit()
        self.ds_models_json.setPlaceholderText(
            '{"flash": {"model_name": "deepseek-v4-flash", ...}}'
        )
        ds_lay.addRow("模型配置:", self.ds_models_json)

        lay.addWidget(ds_group)

        # ── OpenAI API ─────────────────────────────────────
        oai_group = QGroupBox("OpenAI 兼容 API（可选）")
        oai_lay = QFormLayout(oai_group)
        oai_lay.setSpacing(12)
        oai_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.oai_enabled = QCheckBox("启用 OpenAI API")
        oai_lay.addRow("", self.oai_enabled)

        self.oai_api_key = QLineEdit()
        self.oai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.oai_api_key.setPlaceholderText("sk-... 或空（使用本地模型）")
        oai_lay.addRow("API Key:", self.oai_api_key)

        self.oai_base_url = QLineEdit("https://api.openai.com/v1")
        oai_lay.addRow("Base URL:", self.oai_base_url)

        self.oai_models_json = QLineEdit()
        self.oai_models_json.setPlaceholderText(
            '{"gpt4": {"model_name": "gpt-4o", ...}}'
        )
        oai_lay.addRow("模型配置:", self.oai_models_json)

        lay.addWidget(oai_group)

        lay.addStretch()
        return w

    # ===================== L0-L4 路由 Tab =====================
    def _build_router_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        desc = QLabel(
            "配置 L0-L4 分层路由，指定每个层级使用的模型。\n"
            "留空则使用自动分配（根据模型名称关键词自动匹配）。"
        )
        desc.setStyleSheet("color:#64748B;font-size:12px;padding:4px 0 8px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.router_tier_combos = {}
        tier_names = ["L0（快速路由）", "L1（基础理解）", "L2（中级推理）",
                      "L3（高级推理）", "L4（深度生成）"]

        for i, name in enumerate(tier_names):
            combo = QComboBox()
            combo.addItem("（自动分配）", "")
            self.router_tier_combos[str(i)] = combo
            form.addRow(f"{name}:", combo)

        lay.addLayout(form)

        # 刷新模型列表按钮
        refresh_btn = QPushButton("刷新模型列表")
        refresh_btn.clicked.connect(self._refresh_router_model_list)
        lay.addWidget(refresh_btn)

        lay.addStretch()
        # 初始加载模型列表
        self._refresh_router_model_list()
        return w

    def _refresh_router_model_list(self):
        """从加密配置加载所有模型，填充到 ComboBox"""
        from client.src.business.global_model_router import GlobalModelRouter, ModelCapability

        try:
            router = GlobalModelRouter()
            model_ids = list(router.models.keys())
        except Exception:
            model_ids = []

        for tier_key, combo in self.router_tier_combos.items():
            combo.clear()
            combo.addItem("（自动分配）", "")
            for mid in model_ids:
                combo.addItem(mid, mid)

            # 选中当前值
            cfg = load_model_config("router") or {}
            current = cfg.get(f"tier_{tier_key}", "")
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    # ===================== Agent Tab =====================
    def _build_agent_tab(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(12)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.agent_max_iter = QSpinBox()
        self.agent_max_iter.setRange(1, 100)
        self.agent_max_iter.setValue(10)
        lay.addRow("最大迭代次数:", self.agent_max_iter)

        self.agent_timeout = QSpinBox()
        self.agent_timeout.setRange(10, 600)
        self.agent_timeout.setValue(120)
        self.agent_timeout.setSuffix(" 秒")
        lay.addRow("超时时间:", self.agent_timeout)

        self.agent_verbose = QCheckBox("详细日志")
        lay.addRow("", self.agent_verbose)

        return w

    # ===================== 关于 Tab =====================
    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        info = QLabel(
            "<b>LivingTreeAI</b> — 桌面 AI Agent 平台<br><br>"
            "版本：dev (2026-04)<br>"
            "架构：PyQt6 + Python 3.11+<br>"
            "模型路由：GlobalModelRouter（支持多地址、负载均衡、故障转移）<br><br>"
            "所有敏感配置均通过 Fernet 加密存储在：<br>"
            "<code>C:\\Users\\&lt;用户&gt;\\.livingtree\\config\\encrypted\\</code>"
        )
        info.setStyleSheet("color:#94A3B8;font-size:13px;padding:16px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        reset_all_btn = QPushButton("🔄 重置所有配置为默认")
        reset_all_btn.setObjectName("DangerButton")
        reset_all_btn.clicked.connect(self._on_reset_all)
        lay.addWidget(reset_all_btn)

        lay.addStretch()
        return w

    # ===================== 加载 / 保存 =====================
    def _load_from_encrypted_config(self):
        """从加密配置加载所有设置"""
        # Ollama 服务器列表
        ollama_cfg = load_model_config("ollama") or {}
        servers = ollama_cfg.get("servers", [])
        if not servers:
            # 向后兼容单地址格式
            url = ollama_cfg.get("base_url", "http://localhost:11434")
            models = ollama_cfg.get("models", [])
            servers = [{"url": url, "priority": 0, "models": models}]
        self._render_ollama_list(servers)

        # Ollama 模型列表（逗号分隔）
        all_models = []
        for srv in (ollama_cfg.get("servers") or []):
            all_models.extend(srv.get("models", []))
        # 去重
        seen = set()
        unique_models = []
        for m in all_models:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)
        self.ollama_models.setText(", ".join(unique_models))

        # DeepSeek API
        ds_cfg = load_model_config("deepseek") or {}
        self.ds_enabled.setChecked(bool(ds_cfg.get("api_key")))
        self.ds_api_key.setText(ds_cfg.get("api_key", ""))
        self.ds_base_url.setText(ds_cfg.get("base_url", "https://api.deepseek.com"))
        models_str = json.dumps(ds_cfg.get("models", {}), ensure_ascii=False)
        self.ds_models_json.setText(models_str if ds_cfg.get("models") else "")

        # OpenAI API
        oai_cfg = load_model_config("openai") or {}
        self.oai_enabled.setChecked(oai_cfg.get("enabled", False))
        self.oai_api_key.setText(oai_cfg.get("api_key", ""))
        self.oai_base_url.setText(oai_cfg.get("base_url", "https://api.openai.com/v1"))
        oai_models_str = json.dumps(oai_cfg.get("models", {}), ensure_ascii=False)
        self.oai_models_json.setText(oai_models_str if oai_cfg.get("models") else "")

        # Agent 配置（从 router 配置中读取，或单独存储）
        router_cfg = load_model_config("router") or {}
        self.agent_max_iter.setValue(router_cfg.get("agent_max_iter", 10))
        self.agent_timeout.setValue(router_cfg.get("agent_timeout", 120))
        self.agent_verbose.setChecked(router_cfg.get("agent_verbose", False))

    def _on_save(self):
        """保存所有设置到加密配置"""
        try:
            # ── Ollama 配置 ────────────────────────────────
            servers = []
            for i in range(self.ollama_list.count()):
                item = self.ollama_list.item(i)
                srv_data = item.data(Qt.ItemDataRole.UserRole)
                servers.append(srv_data)

            # 同步模型列表到所有服务器
            models_str = self.ollama_models.text()
            models = [m.strip() for m in models_str.split(",") if m.strip()]
            for srv in servers:
                srv["models"] = models

            ollama_cfg = {"servers": servers}
            save_model_config("ollama", ollama_cfg)

            # ── DeepSeek API ──────────────────────────────
            ds_cfg = {}
            if self.ds_enabled.isChecked() and self.ds_api_key.text().strip():
                ds_cfg["api_key"] = self.ds_api_key.text().strip()
                ds_cfg["base_url"] = self.ds_base_url.text().strip()
                if self.ds_models_json.text().strip():
                    try:
                        ds_cfg["models"] = json.loads(self.ds_models_json.text())
                    except json.JSONDecodeError:
                        pass
                ds_cfg["models"] = ds_cfg.get("models", {
                    "flash": {
                        "model_id": "deepseek_v4_flash",
                        "model_name": "deepseek-v4-flash",
                        "capabilities": ["chat", "content_generation"],
                        "quality_score": 0.9,
                        "speed_score": 0.95,
                        "cost_score": 0.8,
                    }
                })
            save_model_config("deepseek", ds_cfg)

            # ── OpenAI API ────────────────────────────────
            oai_cfg = {"enabled": self.oai_enabled.isChecked()}
            if self.oai_api_key.text().strip():
                oai_cfg["api_key"] = self.oai_api_key.text().strip()
            oai_cfg["base_url"] = self.oai_base_url.text().strip()
            if self.oai_models_json.text().strip():
                try:
                    oai_cfg["models"] = json.loads(self.oai_models_json.text())
                except json.JSONDecodeError:
                    pass
            save_model_config("openai", oai_cfg)

            # ── L0-L4 路由配置 ───────────────────────────
            router_cfg = load_model_config("router") or {}
            for tier_key, combo in self.router_tier_combos.items():
                selected_model_id = combo.currentData()
                if selected_model_id:
                    router_cfg[f"tier_{tier_key}"] = selected_model_id
            router_cfg["agent_max_iter"] = self.agent_max_iter.value()
            router_cfg["agent_timeout"] = self.agent_timeout.value()
            router_cfg["agent_verbose"] = self.agent_verbose.isChecked()
            save_model_config("router", router_cfg)

            QMessageBox.information(self, "保存成功", "所有配置已加密保存！")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时出错：\n{e}")

    def _on_reset(self):
        """恢复默认配置"""
        reply = QMessageBox.question(
            self, "确认恢复默认",
            "确定要恢复所有设置为默认吗？这不会删除加密配置。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            setup_default_configs()
            self._load_from_encrypted_config()
            QMessageBox.information(self, "已恢复", "默认配置已重新初始化！")

    def _on_reset_all(self):
        """重置所有配置（包括删除加密文件）"""
        reply = QMessageBox.warning(
            self, "警告",
            "此操作将删除所有加密配置并恢复默认！\n确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import os
            enc_dir = Path.home() / ".livingtree" / "config" / "encrypted"
            if enc_dir.exists():
                import shutil
                shutil.rmtree(enc_dir)
            setup_default_configs()
            self._load_from_encrypted_config()
            QMessageBox.information(self, "已重置", "所有配置已重置为默认！")
