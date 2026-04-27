"""
配置管理面板 UI

提供统一的配置管理界面
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QGroupBox, QScrollArea, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox
)


class ConfigPanel(QWidget):
    """配置面板"""
    
    config_changed = pyqtSignal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_config()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # LLM 配置
        self._create_llm_tab()
        
        # 嵌入配置
        self._create_embedding_tab()
        
        # 浏览器配置
        self._create_browser_tab()
        
        # 安全配置
        self._create_security_tab()
        
        # 文档 QA 配置
        self._create_document_qa_tab()
        
        # 系统配置
        self._create_system_tab()
        
        # 保存按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self._save_config)
        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self._reset_config)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(reset_button)
        layout.addLayout(button_layout)
    
    def _create_llm_tab(self):
        """创建 LLM 配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # 提供商
        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["openai", "anthropic", "google", "ollama"])
        form.addRow("提供商:", self.llm_provider)
        
        # 模型
        self.llm_model = QLineEdit()
        self.llm_model.setPlaceholderText("如: gpt-4o, claude-3-opus, gemini-pro")
        form.addRow("模型:", self.llm_model)
        
        # API 密钥
        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_api_key.setPlaceholderText("输入 API 密钥")
        form.addRow("API 密钥:", self.llm_api_key)
        
        # Base URL
        self.llm_base_url = QLineEdit()
        self.llm_base_url.setPlaceholderText("如: https://api.openai.com/v1 (可选)")
        form.addRow("Base URL:", self.llm_base_url)
        
        # Temperature
        self.llm_temperature = QDoubleSpinBox()
        self.llm_temperature.setRange(0, 2)
        self.llm_temperature.setSingleStep(0.1)
        self.llm_temperature.setDecimals(1)
        form.addRow("Temperature:", self.llm_temperature)
        
        # Max Tokens
        self.llm_max_tokens = QSpinBox()
        self.llm_max_tokens.setRange(100, 100000)
        self.llm_max_tokens.setSingleStep(100)
        form.addRow("Max Tokens:", self.llm_max_tokens)
        
        # Timeout
        self.llm_timeout = QSpinBox()
        self.llm_timeout.setRange(10, 600)
        self.llm_timeout.setSingleStep(10)
        self.llm_timeout.setSuffix(" 秒")
        form.addRow("超时:", self.llm_timeout)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "LLM 配置")
    
    def _create_embedding_tab(self):
        """创建嵌入配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # 提供商
        self.embedding_provider = QComboBox()
        self.embedding_provider.addItems(["openai", "huggingface"])
        form.addRow("提供商:", self.embedding_provider)
        
        # 模型
        self.embedding_model = QLineEdit()
        self.embedding_model.setPlaceholderText("如: text-embedding-ada-002, sentence-transformers/all-MiniLM-L6-v2")
        form.addRow("模型:", self.embedding_model)
        
        # API 密钥
        self.embedding_api_key = QLineEdit()
        self.embedding_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.embedding_api_key.setPlaceholderText("输入 API 密钥 (可选)")
        form.addRow("API 密钥:", self.embedding_api_key)
        
        # Dimension
        self.embedding_dimension = QSpinBox()
        self.embedding_dimension.setRange(128, 4096)
        self.embedding_dimension.setSingleStep(128)
        form.addRow("向量维度:", self.embedding_dimension)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "嵌入配置")
    
    def _create_browser_tab(self):
        """创建浏览器配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # 最大会话数
        self.browser_max_sessions = QSpinBox()
        self.browser_max_sessions.setRange(1, 20)
        form.addRow("最大会话数:", self.browser_max_sessions)
        
        # 会话超时
        self.browser_session_timeout = QSpinBox()
        self.browser_session_timeout.setRange(60, 3600)
        self.browser_session_timeout.setSingleStep(60)
        self.browser_session_timeout.setSuffix(" 秒")
        form.addRow("会话超时:", self.browser_session_timeout)
        
        # 使用云浏览器
        self.browser_use_cloud = QCheckBox()
        form.addRow("使用云浏览器:", self.browser_use_cloud)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "浏览器配置")
    
    def _create_security_tab(self):
        """创建安全配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # 允许的域名
        allowed_group = QGroupBox("允许访问的域名")
        allowed_layout = QVBoxLayout()
        
        self.allowed_domains = QListWidget()
        self.allowed_domains.setMaximumHeight(100)
        allowed_layout.addWidget(self.allowed_domains)
        
        allowed_button_layout = QHBoxLayout()
        add_allowed_btn = QPushButton("添加")
        remove_allowed_btn = QPushButton("移除")
        allowed_button_layout.addWidget(add_allowed_btn)
        allowed_button_layout.addWidget(remove_allowed_btn)
        allowed_layout.addLayout(allowed_button_layout)
        
        allowed_group.setLayout(allowed_layout)
        form.addRow(allowed_group)
        
        # 禁止的域名
        blocked_group = QGroupBox("禁止访问的域名")
        blocked_layout = QVBoxLayout()
        
        self.blocked_domains = QListWidget()
        self.blocked_domains.setMaximumHeight(100)
        blocked_layout.addWidget(self.blocked_domains)
        
        blocked_button_layout = QHBoxLayout()
        add_blocked_btn = QPushButton("添加")
        remove_blocked_btn = QPushButton("移除")
        blocked_button_layout.addWidget(add_blocked_btn)
        blocked_button_layout.addWidget(remove_blocked_btn)
        blocked_layout.addLayout(blocked_button_layout)
        
        blocked_group.setLayout(blocked_layout)
        form.addRow(blocked_group)
        
        # 启用审计
        self.security_enable_audit = QCheckBox()
        form.addRow("启用审计:", self.security_enable_audit)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "安全配置")
    
    def _create_document_qa_tab(self):
        """创建文档 QA 配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # 嵌入模型
        self.doc_qa_embedding_model = QLineEdit()
        self.doc_qa_embedding_model.setPlaceholderText("如: text-embedding-ada-002")
        form.addRow("嵌入模型:", self.doc_qa_embedding_model)
        
        # LLM 模型
        self.doc_qa_llm_model = QLineEdit()
        self.doc_qa_llm_model.setPlaceholderText("如: gpt-4o")
        form.addRow("LLM 模型:", self.doc_qa_llm_model)
        
        # Temperature
        self.doc_qa_temperature = QDoubleSpinBox()
        self.doc_qa_temperature.setRange(0, 2)
        self.doc_qa_temperature.setSingleStep(0.1)
        self.doc_qa_temperature.setDecimals(1)
        form.addRow("Temperature:", self.doc_qa_temperature)
        
        # Top K
        self.doc_qa_top_k = QSpinBox()
        self.doc_qa_top_k.setRange(1, 20)
        form.addRow("Top K:", self.doc_qa_top_k)
        
        # Chunk Size
        self.doc_qa_chunk_size = QSpinBox()
        self.doc_qa_chunk_size.setRange(100, 5000)
        self.doc_qa_chunk_size.setSingleStep(100)
        form.addRow("Chunk Size:", self.doc_qa_chunk_size)
        
        # Chunk Overlap
        self.doc_qa_chunk_overlap = QSpinBox()
        self.doc_qa_chunk_overlap.setRange(0, 1000)
        self.doc_qa_chunk_overlap.setSingleStep(50)
        form.addRow("Chunk Overlap:", self.doc_qa_chunk_overlap)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "文档 QA 配置")
    
    def _create_system_tab(self):
        """创建系统配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        
        # Debug 模式
        self.system_debug = QCheckBox()
        form.addRow("Debug 模式:", self.system_debug)
        
        # 日志级别
        self.system_log_level = QComboBox()
        self.system_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        form.addRow("日志级别:", self.system_log_level)
        
        # 数据目录
        self.system_data_dir = QLineEdit()
        self.system_data_dir.setPlaceholderText("./data")
        form.addRow("数据目录:", self.system_data_dir)
        
        # 缓存目录
        self.system_cache_dir = QLineEdit()
        self.system_cache_dir.setPlaceholderText("./cache")
        form.addRow("缓存目录:", self.system_cache_dir)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.tabs.addTab(tab, "系统配置")
    
    def _load_config(self):
        """加载配置"""
        try:
            from core.living_tree_ai.config.config_manager import get_config_manager
            config = get_config_manager()
            
            # LLM 配置
            self.llm_provider.setCurrentText(config.llm.provider)
            self.llm_model.setText(config.llm.model)
            self.llm_api_key.setText(config.llm.api_key)
            self.llm_base_url.setText(config.llm.base_url)
            self.llm_temperature.setValue(config.llm.temperature)
            self.llm_max_tokens.setValue(config.llm.max_tokens)
            self.llm_timeout.setValue(config.llm.timeout)
            
            # 嵌入配置
            self.embedding_provider.setCurrentText(config.embedding.provider)
            self.embedding_model.setText(config.embedding.model)
            self.embedding_api_key.setText(config.embedding.api_key)
            self.embedding_dimension.setValue(config.embedding.dimension)
            
            # 浏览器配置
            self.browser_max_sessions.setValue(config.browser_pool.max_sessions)
            self.browser_session_timeout.setValue(config.browser_pool.session_timeout)
            self.browser_use_cloud.setChecked(config.browser_pool.use_cloud)
            
            # 安全配置
            self.allowed_domains.clear()
            self.allowed_domains.addItems(config.security.allowed_domains)
            self.blocked_domains.clear()
            self.blocked_domains.addItems(config.security.blocked_domains)
            self.security_enable_audit.setChecked(config.security.enable_audit)
            
            # 文档 QA 配置
            self.doc_qa_embedding_model.setText(config.document_qa.embedding_model)
            self.doc_qa_llm_model.setText(config.document_qa.llm_model)
            self.doc_qa_temperature.setValue(config.document_qa.temperature)
            self.doc_qa_top_k.setValue(config.document_qa.top_k)
            self.doc_qa_chunk_size.setValue(config.document_qa.chunk_size)
            self.doc_qa_chunk_overlap.setValue(config.document_qa.chunk_overlap)
            
            # 系统配置
            self.system_debug.setChecked(config.system.debug)
            self.system_log_level.setCurrentText(config.system.log_level)
            self.system_data_dir.setText(config.system.data_dir)
            self.system_cache_dir.setText(config.system.cache_dir)
            
        except Exception as e:
            print(f"加载配置失败: {e}")
    
    def _save_config(self):
        """保存配置"""
        try:
            from core.living_tree_ai.config.config_manager import get_config_manager
            config = get_config_manager()
            
            # LLM 配置
            config.update_llm_config(
                provider=self.llm_provider.currentText(),
                model=self.llm_model.text(),
                api_key=self.llm_api_key.text(),
                base_url=self.llm_base_url.text(),
                temperature=self.llm_temperature.value(),
                max_tokens=self.llm_max_tokens.value(),
                timeout=self.llm_timeout.value()
            )
            
            # 嵌入配置
            config.update_embedding_config(
                provider=self.embedding_provider.currentText(),
                model=self.embedding_model.text(),
                api_key=self.embedding_api_key.text(),
                dimension=self.embedding_dimension.value()
            )
            
            # 浏览器配置
            config.update_browser_pool_config(
                max_sessions=self.browser_max_sessions.value(),
                session_timeout=self.browser_session_timeout.value(),
                use_cloud=self.browser_use_cloud.isChecked()
            )
            
            # 安全配置
            allowed = []
            for i in range(self.allowed_domains.count()):
                allowed.append(self.allowed_domains.item(i).text())
            
            blocked = []
            for i in range(self.blocked_domains.count()):
                blocked.append(self.blocked_domains.item(i).text())
            
            config.update_security_config(
                allowed_domains=allowed,
                blocked_domains=blocked,
                enable_audit=self.security_enable_audit.isChecked()
            )
            
            # 文档 QA 配置
            config.update_document_qa_config(
                embedding_model=self.doc_qa_embedding_model.text(),
                llm_model=self.doc_qa_llm_model.text(),
                temperature=self.doc_qa_temperature.value(),
                top_k=self.doc_qa_top_k.value(),
                chunk_size=self.doc_qa_chunk_size.value(),
                chunk_overlap=self.doc_qa_chunk_overlap.value()
            )
            
            # 系统配置
            config.update_system_config(
                debug=self.system_debug.isChecked(),
                log_level=self.system_log_level.currentText(),
                data_dir=self.system_data_dir.text(),
                cache_dir=self.system_cache_dir.text()
            )
            
            QMessageBox.information(self, "成功", "配置已保存")
            self.config_changed.emit("all", config.to_dict())
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
    
    def _reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(
            self, "确认", "确定要重置所有配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._load_config()
            QMessageBox.information(self, "成功", "配置已重置")


class ConfigDialog(QDialog):
    """配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统配置")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        self.config_panel = ConfigPanel()
        layout.addWidget(self.config_panel)
        
        self.setLayout(layout)
