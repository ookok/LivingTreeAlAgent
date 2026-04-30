"""
四层AI模型配置面板
Layered AI Model Configuration Panel

支持配置：
- L0 快反大脑 (SmolLM2)
- L1 精确缓存层
- L2 会话缓存层
- L3 知识库层
- L4 异构执行层

功能：
- 模型状态检测
- 缺失模型下载引导
- 自动路由配置
"""

import subprocess
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QComboBox, QFormLayout, QScrollArea, QTabWidget, QTextEdit,
    QMessageBox, QStackedWidget, QProgressBar
)
from PyQt6.QtGui import QFont, QColor


class LayeredAIConfigPanel(QWidget):
    """四层AI模型配置面板"""

    config_changed = pyqtSignal(dict)  # 配置变更信号

    # 推荐模型列表
    RECOMMENDED_MODELS = {
        "l0": [
            {"name": "qwen2.5:0.5b", "display": "Qwen 2.5 0.5B (推荐)", "size": "~390MB", "desc": "中文支持好，有GGUF版本"},
        ],
        "l4": [
            {"name": "qwen2.5:7b", "display": "Qwen 2.5 7B (推荐)", "size": "~4.4GB", "desc": "均衡之选"},
            {"name": "qwen2.5:14b", "display": "Qwen 2.5 14B", "size": "~8.2GB", "desc": "更强推理"},
            {"name": "deepseek-r1:7b", "display": "DeepSeek-R1 7B", "size": "~4.7GB", "desc": "深度推理"},
            {"name": "llama3.1:8b", "display": "Llama 3.1 8B", "size": "~4.9GB", "desc": "通用强大"},
        ],
        "l3_embed": [
            {"name": "nomic-embed-text", "display": "Nomic Embed Text (推荐)", "size": "~274MB", "desc": "高性能向量化"},
            {"name": "mxbai-embed-large", "display": "MXBAI Embed Large", "size": "~665MB", "desc": "超大维度"},
        ]
    }

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._downloading_models = set()  # 正在下载的模型
        self._build_ui()
        self._load_config()
        QTimer.singleShot(500, self._check_all_models)  # 延迟检测模型状态

    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title = QLabel("🧠 四层AI模型配置")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "配置分层AI架构：L0快反路由 → L1精确缓存 → L2会话上下文 → L3知识库 → L4深度推理"
        )
        desc.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(desc)

        # 模型状态总览
        self._build_model_status_overview(layout)

        # Tab 页
        tabs = QTabWidget()
        tabs.addTab(self._create_l0_tab(), "🚀 L0 快反大脑")
        tabs.addTab(self._create_l1_tab(), "⚡ L1 精确缓存")
        tabs.addTab(self._create_l2_tab(), "💬 L2 会话缓存")
        tabs.addTab(self._create_l3_tab(), "📚 L3 知识库")
        tabs.addTab(self._create_l4_tab(), "🧠 L4 异构执行")
        tabs.addTab(self._create_global_tab(), "🌐 全局设置")

        layout.addWidget(tabs)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("💾 保存配置")
        self.save_btn.clicked.connect(self._save_config)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3d9d56; }
        """)
        btn_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("🔄 重置")
        self.reset_btn.clicked.connect(self._load_config)
        btn_layout.addWidget(self.reset_btn)

        layout.addLayout(btn_layout)

    def _build_model_status_overview(self, parent_layout):
        """构建模型状态总览卡片"""
        card = QGroupBox("📊 模型状态总览")
        card.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QHBoxLayout(card)

        # L0 状态
        self.l0_status_widget = self._create_status_card("L0 快反", "检测中...")
        layout.addWidget(self.l0_status_widget)

        # L3 Embed 状态
        self.l3_embed_status_widget = self._create_status_card("L3 向量", "检测中...")
        layout.addWidget(self.l3_embed_status_widget)

        # L4 状态
        self.l4_status_widget = self._create_status_card("L4 推理", "检测中...")
        layout.addWidget(self.l4_status_widget)

        # Ollama 服务状态
        self.ollama_status_widget = self._create_status_card("Ollama", "检测中...")
        layout.addWidget(self.ollama_status_widget)

        parent_layout.addWidget(card)

    def _create_status_card(self, title: str, initial_text: str) -> QWidget:
        """创建状态卡片"""
        card = QWidget()
        card.setFixedSize(120, 70)
        card.setStyleSheet("""
            QWidget {
                background-color: #333;
                border-radius: 6px;
                border: 1px solid #555;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #aaa; font-size: 11px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self._status_labels = getattr(self, f'_{title.replace(" ", "_").replace("/", "_")}_label', None)
        status_label = QLabel(initial_text)
        status_label.setObjectName(f"status_{title}")
        status_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        return card

    def _check_all_models(self):
        """检测所有模型状态"""
        def check():
            # 检测 Ollama 服务
            self._check_ollama_service()
            # 检测 L0 模型
            l0_model = self.config.layered_ai.l0.model_name
            self._check_model_status("l0", l0_model)
            # 检测 L3 向量化模型
            l3_embed = self.config.layered_ai.l3.embedding_model
            self._check_model_status("l3_embed", l3_embed)
            # 检测 L4 模型
            l4_model = self.config.layered_ai.l4.model_name
            self._check_model_status("l4", l4_model)

        threading.Thread(target=check, daemon=True).start()

    def _check_ollama_service(self):
        """检测 Ollama 服务状态"""
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                self._update_status("Ollama", "✅ 已连接", "#4caf50")
                # 获取已安装模型列表
                models = resp.json().get("models", [])
                self._update_installed_models(models)
            else:
                self._update_status("Ollama", "⚠️ 异常", "#ff9800")
        except Exception:
            self._update_status("Ollama", "❌ 未运行", "#f44336")

    def _update_installed_models(self, models: list):
        """更新已安装模型列表"""
        self._installed_models = {m.get("name", "") for m in models}

    def _check_model_status(self, layer: str, model_name: str):
        """检测单个模型状态"""
        if not model_name:
            self._update_status(f"{layer.replace('_', ' ').title()}", "⚠️ 未配置", "#ff9800")
            return

        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                installed = any(m.get("name", "").startswith(model_name.split(":")[0]) for m in models)
                if installed:
                    self._update_status(layer, "✅ 已安装", "#4caf50")
                else:
                    self._update_status(layer, "⏬ 未下载", "#2196f3")
            else:
                self._update_status(layer, "⚠️ 检测失败", "#ff9800")
        except Exception:
            self._update_status(layer, "❌ Ollama离线", "#f44336")

    def _update_status(self, layer: str, status: str, color: str):
        """更新状态标签"""
        def update():
            label_names = {
                "l0": "status_L0 快反",
                "l3_embed": "status_L3 向量",
                "l4": "status_L4 推理",
                "ollama": "status_Ollama",
            }
            label_name = label_names.get(layer, f"status_{layer}")
            label = self.findChild(QLabel, label_name)
            if label:
                label.setText(status)
                label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
        QTimer.singleShot(0, update)

    def _create_l0_tab(self) -> QWidget:
        """L0 快反大脑配置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("🚀 L0 快反大脑 (SmolLM2)")
        group.setCheckable(True)
        form = QFormLayout(group)

        self.l0_enabled = QCheckBox("启用 L0 快反路由")
        form.addRow("启用状态:", self.l0_enabled)

        # 模型选择
        self.l0_model = QLineEdit()
        self.l0_model.setPlaceholderText("smollm2-135m-instruct")
        form.addRow("模型名称:", self.l0_model)

        # 推荐模型下拉
        self.l0_combo = QComboBox()
        self.l0_combo.addItem(" - 选择推荐模型 -", "")
        for m in self.RECOMMENDED_MODELS["l0"]:
            self.l0_combo.addItem(f"{m['display']} ({m['size']})", m["name"])
        self.l0_combo.currentIndexChanged.connect(self._on_l0_model_selected)
        form.addRow("推荐模型:", self.l0_combo)

        self.l0_url = QLineEdit()
        self.l0_url.setPlaceholderText("http://localhost:11434")
        form.addRow("服务地址:", self.l0_url)

        # 下载按钮
        self.l0_download_btn = QPushButton("⏬ 下载模型")
        self.l0_download_btn.clicked.connect(self._on_l0_download_clicked)
        self.l0_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        form.addRow("", self.l0_download_btn)

        # 下载进度条
        self.l0_progress = QProgressBar()
        self.l0_progress.setVisible(False)
        form.addRow("下载进度:", self.l0_progress)
        
        # 暂停/继续按钮
        self.l0_pause_btn = QPushButton("⏸ 暂停")
        self.l0_pause_btn.setVisible(False)
        self.l0_pause_btn.clicked.connect(lambda: self._toggle_download("l0"))
        form.addRow("", self.l0_pause_btn)

        desc = QLabel(
            "L0 负责意图分类与轻量任务路由，响应时间 <1s\n"
            "适用：cache/local/search 类型的快速响应"
        )
        desc.setStyleSheet("color: #888; padding: 10px;")
        form.addRow("", desc)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _on_l0_model_selected(self, index):
        """L0 推荐模型选中"""
        model_name = self.l0_combo.currentData()
        if model_name:
            self.l0_model.setText(model_name)

    def _create_l1_tab(self) -> QWidget:
        """L1 精确缓存配置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("⚡ L1 精确缓存层")
        group.setCheckable(True)
        form = QFormLayout(group)

        self.l1_enabled = QCheckBox("启用 L1 精确缓存")
        form.addRow("启用状态:", self.l1_enabled)

        self.l1_ttl = QSpinBox()
        self.l1_ttl.setRange(60, 3600)
        self.l1_ttl.setSuffix(" 秒")
        form.addRow("缓存TTL:", self.l1_ttl)

        desc = QLabel(
            "L1 提供毫秒级精确匹配缓存\n"
            "适用：重复查询、精确配置、静态知识\n\n"
            "✅ 无需下载模型，仅配置参数即可"
        )
        desc.setStyleSheet("color: #888; padding: 10px; line-height: 1.6;")
        form.addRow("", desc)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _create_l2_tab(self) -> QWidget:
        """L2 会话缓存配置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("💬 L2 会话缓存层")
        group.setCheckable(True)
        form = QFormLayout(group)

        self.l2_enabled = QCheckBox("启用 L2 会话缓存")
        form.addRow("启用状态:", self.l2_enabled)

        self.l2_ctx = QSpinBox()
        self.l2_ctx.setRange(1024, 128000)
        self.l2_ctx.setSingleStep(1024)
        self.l2_ctx.setSuffix(" tokens")
        form.addRow("上下文大小:", self.l2_ctx)

        desc = QLabel(
            "L2 基于当前会话上下文进行检索\n"
            "适用：多轮对话、上下文关联任务\n\n"
            "✅ 无需下载模型，共享 L4 的模型"
        )
        desc.setStyleSheet("color: #888; padding: 10px; line-height: 1.6;")
        form.addRow("", desc)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _create_l3_tab(self) -> QWidget:
        """L3 知识库配置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("📚 L3 知识库层")
        group.setCheckable(True)
        form = QFormLayout(group)

        self.l3_enabled = QCheckBox("启用 L3 知识库检索")
        form.addRow("启用状态:", self.l3_enabled)

        # 向量化模型
        self.l3_embed = QLineEdit()
        self.l3_embed.setPlaceholderText("nomic-embed-text")
        form.addRow("向量化模型:", self.l3_embed)

        # 推荐向量化模型
        self.l3_embed_combo = QComboBox()
        self.l3_embed_combo.addItem(" - 选择推荐模型 -", "")
        for m in self.RECOMMENDED_MODELS["l3_embed"]:
            self.l3_embed_combo.addItem(f"{m['display']} ({m['size']})", m["name"])
        self.l3_embed_combo.currentIndexChanged.connect(self._on_l3_embed_selected)
        form.addRow("推荐模型:", self.l3_embed_combo)

        # 下载按钮
        self.l3_download_btn = QPushButton("⏬ 下载模型")
        self.l3_download_btn.clicked.connect(self._on_l3_download_clicked)
        self.l3_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        form.addRow("", self.l3_download_btn)

        # 下载进度条
        self.l3_progress = QProgressBar()
        self.l3_progress.setVisible(False)
        form.addRow("下载进度:", self.l3_progress)
        
        # 暂停/继续按钮
        self.l3_pause_btn = QPushButton("⏸ 暂停")
        self.l3_pause_btn.setVisible(False)
        self.l3_pause_btn.clicked.connect(lambda: self._toggle_download("l3_embed"))
        form.addRow("", self.l3_pause_btn)

        self.l3_path = QLineEdit()
        self.l3_path.setPlaceholderText("D:/mhzyapp/knowledge")
        form.addRow("知识库路径:", self.l3_path)

        browse_btn = QPushButton("🔄 切换知识库")
        browse_btn.clicked.connect(self._browse_knowledge_path)
        form.addRow("", browse_btn)

        desc = QLabel(
            "L3 通过向量检索从知识库中匹配相关内容\n"
            "适用：文档问答、技术文档、专业知识"
        )
        desc.setStyleSheet("color: #888; padding: 10px;")
        form.addRow("", desc)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _on_l3_embed_selected(self, index):
        """L3 推荐模型选中"""
        model_name = self.l3_embed_combo.currentData()
        if model_name:
            self.l3_embed.setText(model_name)

    def _on_l3_download_clicked(self):
        """L3 下载按钮点击"""
        model_name = self.l3_embed.text().strip()
        if not model_name:
            model_name = self.l3_embed_combo.currentData()
        if not model_name:
            QMessageBox.warning(self, "未选择模型", "请输入模型名称或从下拉列表选择")
            return
        self._download_model("l3_embed", model_name)

    def _on_l0_download_clicked(self):
        """L0 下载按钮点击"""
        model_name = self.l0_model.text().strip()
        if not model_name:
            model_name = self.l0_combo.currentData()
        if not model_name:
            QMessageBox.warning(self, "未选择模型", "请输入模型名称或从下拉列表选择")
            return
        self._download_model("l0", model_name)

    def _on_l4_download_clicked(self):
        """L4 下载按钮点击"""
        model_name = self.l4_model.text().strip()
        if not model_name:
            model_name = self.l4_combo.currentData()
        if not model_name:
            QMessageBox.warning(self, "未选择模型", "请输入模型名称或从下拉列表选择")
            return
        self._download_model("l4", model_name)

    def _create_l4_tab(self) -> QWidget:
        """L4 异构执行配置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("🧠 L4 异构执行层")
        group.setCheckable(True)
        form = QFormLayout(group)

        self.l4_enabled = QCheckBox("启用 L4 深度推理")
        form.addRow("启用状态:", self.l4_enabled)

        # 模型选择
        self.l4_model = QLineEdit()
        self.l4_model.setPlaceholderText("qwen2.5:7b")
        form.addRow("模型名称:", self.l4_model)

        # 推荐模型下拉
        self.l4_combo = QComboBox()
        self.l4_combo.addItem(" - 选择推荐模型 -", "")
        for m in self.RECOMMENDED_MODELS["l4"]:
            self.l4_combo.addItem(f"{m['display']} ({m['size']})", m["name"])
        self.l4_combo.currentIndexChanged.connect(self._on_l4_model_selected)
        form.addRow("推荐模型:", self.l4_combo)

        self.l4_url = QLineEdit()
        self.l4_url.setPlaceholderText("http://localhost:11434")
        form.addRow("服务地址:", self.l4_url)

        self.l4_tokens = QSpinBox()
        self.l4_tokens.setRange(1024, 128000)
        self.l4_tokens.setSingleStep(1024)
        self.l4_tokens.setSuffix(" tokens")
        form.addRow("最大Token:", self.l4_tokens)

        self.l4_temp = QDoubleSpinBox()
        self.l4_temp.setRange(0.0, 2.0)
        self.l4_temp.setSingleStep(0.1)
        self.l4_temp.setDecimals(1)
        form.addRow("Temperature:", self.l4_temp)

        # 下载按钮
        self.l4_download_btn = QPushButton("⏬ 下载模型")
        self.l4_download_btn.clicked.connect(self._on_l4_download_clicked)
        self.l4_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        form.addRow("", self.l4_download_btn)

        # 下载进度条
        self.l4_progress = QProgressBar()
        self.l4_progress.setVisible(False)
        form.addRow("下载进度:", self.l4_progress)
        
        # 暂停/继续按钮
        self.l4_pause_btn = QPushButton("⏸ 暂停")
        self.l4_pause_btn.setVisible(False)
        self.l4_pause_btn.clicked.connect(lambda: self._toggle_download("l4"))
        form.addRow("", self.l4_pause_btn)

        desc = QLabel(
            "L4 处理复杂推理、深度分析任务\n"
            "适用：代码生成、长文本创作、复杂推理"
        )
        desc.setStyleSheet("color: #888; padding: 10px;")
        form.addRow("", desc)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _on_l4_model_selected(self, index):
        """L4 推荐模型选中"""
        model_name = self.l4_combo.currentData()
        if model_name:
            self.l4_model.setText(model_name)

    def _create_global_tab(self) -> QWidget:
        """全局设置"""
        w = QWidget()
        layout = QVBoxLayout(w)

        group = QGroupBox("🌐 全局AI路由设置")
        form = QFormLayout(group)

        self.auto_route = QCheckBox("启用自动路由")
        self.auto_route.setChecked(True)
        form.addRow("自动路由:", self.auto_route)

        desc = QLabel(
            "开启后，系统将根据任务类型自动选择合适的AI层级：\n"
            "• 简单查询 → L0/L1 (毫秒响应)\n"
            "• 对话任务 → L2 (上下文感知)\n"
            "• 文档问答 → L3 (知识库检索)\n"
            "• 复杂推理 → L4 (深度模型)"
        )
        desc.setStyleSheet("color: #888; padding: 10px; line-height: 1.8;")
        form.addRow("", desc)

        # Ollama 安装引导
        ollama_group = QGroupBox("📦 Ollama 安装指南")
        ollama_form = QFormLayout(ollama_group)

        install_desc = QLabel(
            "1. 访问 https://ollama.com 下载安装\n"
            "2. 安装完成后，在终端运行：\n"
            "   ollama pull qwen2.5:7b\n\n"
            "3. 启动服务：ollama serve"
        )
        install_desc.setStyleSheet("color: #aaa; padding: 10px; line-height: 1.8;")
        ollama_form.addRow("", install_desc)

        layout.addWidget(group)
        layout.addWidget(ollama_group)
        layout.addStretch()
        return w

    def _browse_knowledge_path(self):
        """浏览知识库路径"""
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            self, "选择知识库目录", self.l3_path.text()
        )
        if path:
            self.l3_path.setText(path)

    def _toggle_download(self, layer: str):
        """切换下载状态（暂停/继续）"""
        if not hasattr(self, '_download_tasks') or layer not in self._download_tasks:
            return
        
        task_info = self._download_tasks[layer]
        pause_btn = getattr(self, f"{layer}_pause_btn", None)
        
        if not pause_btn:
            return
        
        # 对于向量化模型（使用Ollama拉取），不支持暂停/继续
        if task_info['model_name'] in ["nomic-embed-text", "mxbai-embed-large"]:
            QMessageBox.information(
                self, "提示",
                "向量化模型使用Ollama拉取，暂不支持暂停/继续功能。"
            )
            return
        
        # 对于GGUF模型，使用系统下载中心的暂停/继续功能
        download_center = task_info.get('download_center')
        if not download_center:
            return
        
        # 切换暂停/继续状态
        if task_info.get('paused', False):
            # 继续下载
            try:
                # 获取所有任务
                tasks = download_center.list_tasks()
                for task in tasks:
                    if task.status in ["paused"]:
                        download_center.resume(task.id)
                        task_info['paused'] = False
                        pause_btn.setText("⏸ 暂停")
                        QMessageBox.information(
                            self, "下载继续",
                            f"模型 {task_info['model_name']} 下载已继续。"
                        )
                        break
            except Exception as e:
                QMessageBox.error(
                    self, "操作失败",
                    f"继续下载失败：{str(e)}"
                )
        else:
            # 暂停下载
            try:
                # 获取所有任务
                tasks = download_center.list_tasks()
                for task in tasks:
                    if task.status in ["downloading"]:
                        download_center.pause(task.id)
                        task_info['paused'] = True
                        pause_btn.setText("▶ 继续")
                        QMessageBox.information(
                            self, "下载暂停",
                            f"模型 {task_info['model_name']} 下载已暂停。"
                        )
                        break
            except Exception as e:
                QMessageBox.error(
                    self, "操作失败",
                    f"暂停下载失败：{str(e)}"
                )

    def _download_model(self, layer: str, model_name: str):
        """下载模型 - 使用系统统一下载中心"""
        if not model_name:
            QMessageBox.warning(self, "未指定模型", "请输入或选择要下载的模型名称")
            return

        if layer in self._downloading_models:
            return

        self._downloading_models.add(layer)

        # 获取对应的进度条和按钮
        progress = getattr(self, f"{layer}_progress", None)
        download_btn = getattr(self, f"{layer}_download_btn", None)
        pause_btn = getattr(self, f"{layer}_pause_btn", None)

        if progress:
            progress.setVisible(True)
            progress.setValue(0)
            progress.setFormat("0%")
        if download_btn:
            download_btn.setEnabled(False)
            download_btn.setText("下载中...")
        if pause_btn:
            pause_btn.setVisible(True)
            pause_btn.setText("⏸ 暂停")
        
        # 存储下载任务信息
        self._download_tasks = getattr(self, '_download_tasks', {})
        self._download_tasks[layer] = {
            'model_name': model_name,
            'task_id': None,
            'paused': False
        }

        def do_download():
            try:
                # 使用系统统一下载中心
                from .business.unified_downloader import get_download_center
                from .business.unified_downloader import DownloadStatus, SourceType
                
                # 根据模型类型选择下载链接
                model_downloads = {
                    "nomic-embed-text": {
                        "huggingface": "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/resolve/main/model.onnx",
                        "name": "Nomic Embed Text"
                    },
                    "mxbai-embed-large": {
                        "huggingface": "https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1/resolve/main/model.onnx",
                        "name": "MXBAI Embed Large"
                    }
                }
                
                # 为向量化模型使用 Ollama 拉取
                # 对于其他模型，使用系统下载中心
                if model_name in ["nomic-embed-text", "mxbai-embed-large"]:
                    # 使用 ollama pull 下载向量化模型
                    process = subprocess.Popen(
                        ["ollama", "pull", model_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            print(f"[OLLAMA] {line}", flush=True)
                        # 解析进度
                        if "%" in line or "Downloading" in line or "verifying" in line:
                            try:
                                parts = line.split()
                                for p in parts:
                                    if "%" in p:
                                        pct_str = p.replace("%", "")
                                        pct = int(float(pct_str))
                                        if progress:
                                            def update_progress(val):
                                                progress.setValue(val)
                                                progress.setFormat(f"{val}%")
                                            QTimer.singleShot(0, lambda v=pct: update_progress(v))
                                    break
                            except Exception as e:
                                print(f"[PROGRESS PARSE ERROR] {e}", flush=True)
                                pass

                    process.wait()
                    
                    if process.returncode == 0:
                        success = True
                    else:
                        success = False
                else:
                    # 使用系统下载中心下载 GGUF 模型
                    from .business.model_manager import ModelManager
                    from .business.config import AppConfig
                    from .business.unified_downloader import get_download_center
                    
                    config = AppConfig()
                    model_manager = ModelManager(config)
                    download_center = get_download_center()
                    
                    # 存储下载中心实例
                    self._download_tasks[layer]['download_center'] = download_center
                    
                    def progress_callback(current, total, status):
                        if progress:
                            if total > 0:
                                pct = int((current / total) * 100)
                                def update_progress(val):
                                    progress.setValue(val)
                                    progress.setFormat(f"{val}% - {status}")
                                QTimer.singleShot(0, lambda v=pct: update_progress(v))
                    
                    success = model_manager.download_model(model_name, progress_callback)

                # 下载完成
                def on_complete():
                    self._downloading_models.discard(layer)
                    if progress:
                        progress.setVisible(False)
                    if download_btn:
                        download_btn.setEnabled(True)
                        download_btn.setText("⏬ 下载模型")
                    if pause_btn:
                        pause_btn.setVisible(False)

                    # 更新状态
                    self._check_model_status(layer, model_name)
                    self._check_ollama_service()

                    if success:
                        QMessageBox.information(
                            self, "下载完成",
                            f"模型 {model_name} 下载成功！"
                        )
                    else:
                        QMessageBox.error(
                            self, "下载失败",
                            f"模型 {model_name} 下载失败，请检查网络连接或Ollama服务状态。"
                        )
                    
                    # 清理任务信息
                    if hasattr(self, '_download_tasks') and layer in self._download_tasks:
                        del self._download_tasks[layer]

                QTimer.singleShot(0, on_complete)

            except FileNotFoundError:
                def on_error():
                    self._downloading_models.discard(layer)
                    if progress:
                        progress.setVisible(False)
                    if download_btn:
                        download_btn.setEnabled(True)
                        download_btn.setText("⏬ 下载模型")
                    QMessageBox.critical(
                        self, "Ollama 未安装",
                        "请先安装 Ollama：\n\n"
                        "1. 访问 https://ollama.com\n"
                        "2. 下载并安装 Ollama\n"
                        "3. 重启本应用"
                    )
                QTimer.singleShot(0, on_error)

            except Exception as e:
                def on_error():
                    self._downloading_models.discard(layer)
                    if progress:
                        progress.setVisible(False)
                    if download_btn:
                        download_btn.setEnabled(True)
                        download_btn.setText("⏬ 下载模型")
                    import traceback
                    traceback.print_exc()
                    QMessageBox.critical(
                        self, "下载失败",
                        f"下载过程中出现错误：{str(e)}\n\n"
                        "请检查：\n"
                        "1. 网络连接是否正常\n"
                        "2. Ollama 服务是否运行\n"
                        "3. 磁盘空间是否充足"
                    )
                QTimer.singleShot(0, on_error)

        threading.Thread(target=do_download, daemon=True).start()

    def _load_config(self):
        """加载配置到UI"""
        la = self.config.layered_ai

        # L0
        self.l0_enabled.setChecked(la.l0.enabled)
        self.l0_model.setText(la.l0.model_name)
        self.l0_url.setText(la.l0.base_url)

        # L1
        self.l1_enabled.setChecked(la.l1.enabled)
        self.l1_ttl.setValue(la.l1.cache_ttl_seconds)

        # L2
        self.l2_enabled.setChecked(la.l2.enabled)
        self.l2_ctx.setValue(la.l2.max_context_tokens)

        # L3
        self.l3_enabled.setChecked(la.l3.enabled)
        self.l3_embed.setText(la.l3.embedding_model)
        self.l3_path.setText(la.l3.knowledge_base_path)

        # L4
        self.l4_enabled.setChecked(la.l4.enabled)
        self.l4_model.setText(la.l4.model_name)
        self.l4_url.setText(la.l4.base_url)
        self.l4_tokens.setValue(la.l4.max_tokens)
        self.l4_temp.setValue(la.l4.temperature)

        # Global
        self.auto_route.setChecked(la.auto_route)

    def _save_config(self):
        """保存配置"""
        from .infrastructure.config.config import save_config

        la = self.config.layered_ai

        # L0
        la.l0.enabled = self.l0_enabled.isChecked()
        la.l0.model_name = self.l0_model.text().strip() or "smollm2-135m-instruct"
        la.l0.base_url = self.l0_url.text().strip() or "http://localhost:11434"

        # L1
        la.l1.enabled = self.l1_enabled.isChecked()
        la.l1.cache_ttl_seconds = self.l1_ttl.value()

        # L2
        la.l2.enabled = self.l2_enabled.isChecked()
        la.l2.max_context_tokens = self.l2_ctx.value()

        # L3
        la.l3.enabled = self.l3_enabled.isChecked()
        la.l3.embedding_model = self.l3_embed.text().strip() or "nomic-embed-text"
        la.l3.knowledge_base_path = self.l3_path.text().strip()

        # L4
        la.l4.enabled = self.l4_enabled.isChecked()
        la.l4.model_name = self.l4_model.text().strip() or "qwen2.5:7b"
        la.l4.base_url = self.l4_url.text().strip() or "http://localhost:11434"
        la.l4.max_tokens = self.l4_tokens.value()
        la.l4.temperature = self.l4_temp.value()

        # Global
        la.auto_route = self.auto_route.isChecked()

        save_config(self.config)
        self.config_changed.emit(self.config.model_dump())

        QMessageBox.information(self, "保存成功", "四层AI模型配置已保存！")

    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config.model_dump()
