"""
Provider 管理面板 - ProviderPanel
配置 AI 服务提供商和 API Keys
参考 hermes-agent 的 ConfigPage 设计
"""

from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QLineEdit, QComboBox, QCheckBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QStackedWidget, QDialog, QMessageBox,
    QFormLayout, QSpinBox,
)
from PyQt6.QtGui import QFont

import os
from typing import Dict, List, Optional, Any

from core.config import get_hermes_home
from core.providers import (
    list_providers, get_provider, get_label, has_api_key,
    get_api_key, get_recommended_models, PROVIDER_CATEGORIES,
    AuthType, TransportType, ProviderDef,
)


class ProviderCard(QFrame):
    """提供商配置卡片"""
    
    provider_selected = pyqtSignal(str)
    provider_changed = pyqtSignal(str, str)  # provider_id, api_key
    
    def __init__(self, provider: ProviderDef, parent=None):
        super().__init__(parent)
        self.provider = provider
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            ProviderCard {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 12px;
            }
            ProviderCard:hover {
                border-color: #5a5aff;
            }
            ProviderCard:selected {
                border-color: #5a5aff;
                background: #252540;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 头部
        header = QHBoxLayout()
        
        # 提供商名称
        name_label = QLabel(self.provider.name)
        name_label.setStyleSheet("color: #e8e8e8; font-size: 14px; font-weight: 600;")
        header.addWidget(name_label)
        
        # 聚合标记
        if self.provider.is_aggregator:
            agg_badge = QLabel("AGGREGATOR")
            agg_badge.setStyleSheet("""
                background: #5a5aff;
                color: white;
                font-size: 9px;
                padding: 2px 6px;
                border-radius: 3px;
            """)
            header.addWidget(agg_badge)
        
        header.addStretch()
        
        # 状态指示
        if has_api_key(self.provider.id):
            status = QLabel("CONFIGURED")
            status.setStyleSheet("color: #4ade80; font-size: 11px;")
        else:
            status = QLabel("NOT SET")
            status.setStyleSheet("color: #f87171; font-size: 11px;")
        header.addWidget(status)
        
        layout.addLayout(header)
        
        # 描述
        if self.provider.doc:
            doc_label = QLabel(self.provider.doc)
            doc_label.setStyleSheet("color: #888; font-size: 11px;")
            doc_label.setWordWrap(True)
            layout.addWidget(doc_label)
        
        # 环境变量
        env_vars = list(self.provider.api_key_env_vars)
        if env_vars:
            env_label = QLabel(f"ENV: {', '.join(env_vars)}")
            env_label.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(env_label)
        
        # API Key 输入
        key_layout = QHBoxLayout()
        key_layout.setSpacing(8)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText(f"Enter API Key ({env_vars[0] if env_vars else 'key'})")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px 10px;
                color: #ccc;
            }
            QLineEdit:focus {
                border-color: #5a5aff;
            }
        """)
        
        # 预填充已有 Key
        existing_key = get_api_key(self.provider.id)
        if existing_key:
            self.key_input.setText(existing_key)
        
        key_layout.addWidget(self.key_input)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #4a4aef; }
        """)
        self.save_btn.clicked.connect(self._on_save)
        key_layout.addWidget(self.save_btn)
        
        layout.addLayout(key_layout)
    
    def _on_save(self):
        """保存 API Key"""
        key = self.key_input.text().strip()
        if key:
            # 保存到环境变量和 .env 文件
            self._save_to_env(key)
            self.provider_changed.emit(self.provider.id, key)
            
            # 显示保存成功
            self.save_btn.setText("Saved!")
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background: #4ade80;
                    color: #1a1a1a;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: 600;
                }
            """)
        else:
            # 清除
            self._clear_from_env()
    
    def _save_to_env(self, key: str):
        """保存到 .env 文件"""
        hermes_home = get_hermes_home()
        env_file = hermes_home / ".env"
        
        # 读取现有内容
        env_vars = {}
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
        
        # 更新
        for env_var in self.provider.api_key_env_vars:
            env_vars[env_var] = key
            os.environ[env_var] = key
        
        # 写回
        with open(env_file, "w", encoding="utf-8") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
    
    def _clear_from_env(self):
        """从 .env 清除"""
        hermes_home = get_hermes_home()
        env_file = hermes_home / ".env"
        
        if env_file.exists():
            env_vars = {}
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in self.provider.api_key_env_vars:
                            env_vars[k.strip()] = v.strip()
            
            with open(env_file, "w", encoding="utf-8") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")


class ProviderPanel(QWidget):
    """Provider 管理面板主组件"""
    
    provider_configured = pyqtSignal(str)  # provider_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("background: #151515;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题栏
        header = QHBoxLayout()
        
        title = QLabel("AI Providers / AI 提供商")
        title.setStyleSheet("""
            color: #e8e8e8;
            font-size: 20px;
            font-weight: 700;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search providers...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #252525;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ccc;
                min-width: 200px;
            }
            QLineEdit:focus { border-color: #5a5aff; }
        """)
        self.search_input.textChanged.connect(self._on_search)
        header.addWidget(self.search_input)
        
        layout.addLayout(header)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(16)
        
        # 按类别显示提供商
        self._build_provider_list()
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _build_provider_list(self):
        """构建提供商列表"""
        # 清除现有
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        search_text = self.search_input.text().lower() if hasattr(self, 'search_input') else ""
        
        # 按类别显示
        for category, provider_ids in PROVIDER_CATEGORIES.items():
            category_label = QLabel(category)
            category_label.setStyleSheet("""
                color: #888;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 0;
            """)
            self.content_layout.addWidget(category_label)
            
            # 提供商卡片网格
            cards_layout = QGridLayout()
            cards_layout.setSpacing(12)
            
            col = 0
            row = 0
            
            for provider_id in provider_ids:
                provider = get_provider(provider_id)
                if not provider:
                    continue
                
                # 搜索过滤
                if search_text:
                    if search_text not in provider.name.lower() and search_text not in provider_id.lower():
                        continue
                
                card = ProviderCard(provider)
                card.provider_changed.connect(self._on_provider_changed)
                cards_layout.addWidget(card, row, col)
                
                col += 1
                if col >= 2:  # 每行 2 个
                    col = 0
                    row += 1
            
            self.content_layout.addLayout(cards_layout)
    
    def _on_search(self, text: str):
        """搜索"""
        self._build_provider_list()
    
    def _on_provider_changed(self, provider_id: str, api_key: str):
        """提供商配置变更"""
        self.provider_configured.emit(provider_id)


class ProviderSelectDialog(QDialog):
    """Provider 选择对话框"""
    
    provider_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Provider / 选择提供商")
        self.setMinimumSize(500, 400)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 搜索
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)
        
        # 列表
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Provider", "Type", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(self._on_select)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #1e1e1e;
                color: #ccc;
                border: none;
                border-radius: 6px;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background: #353585; }
            QHeaderView::section {
                background: #252525;
                color: #888;
                padding: 8px;
                border: none;
            }
        """)
        layout.addWidget(self.table)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        select_btn = QPushButton("Select")
        select_btn.setStyleSheet("""
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
        """)
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载数据
        self._load_providers()
    
    def _load_providers(self, filter_text: str = ""):
        """加载提供商列表"""
        self.table.setRowCount(0)
        
        providers = list_providers()
        
        for i, provider in enumerate(providers):
            if filter_text:
                if filter_text.lower() not in provider.name.lower():
                    continue
            
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(provider.name))
            
            # 类型
            type_text = "Aggregator" if provider.is_aggregator else "Direct"
            self.table.setItem(i, 1, QTableWidgetItem(type_text))
            
            # 状态
            if has_api_key(provider.id):
                status_item = QTableWidgetItem("Configured")
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                status_item = QTableWidgetItem("Not Set")
                status_item.setForeground(Qt.GlobalColor.darkRed)
            self.table.setItem(i, 2, status_item)
            
            # 保存 provider_id
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, provider.id)
    
    def _on_search(self, text: str):
        """搜索"""
        self._load_providers(text)
    
    def _on_select(self):
        """选择"""
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                provider_id = item.data(Qt.ItemDataRole.UserRole)
                self.provider_selected.emit(provider_id)
                self.accept()


class ModelSelectDialog(QDialog):
    """模型选择对话框"""
    
    model_selected = pyqtSignal(str)
    
    def __init__(self, provider_id: str, parent=None):
        super().__init__(parent)
        self.provider_id = provider_id
        self.setWindowTitle(f"Select Model / 选择模型 ({get_label(provider_id)})")
        self.setMinimumSize(500, 400)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 模型列表
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Model"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(self._on_select)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #1e1e1e;
                color: #ccc;
                border: none;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background: #353585; }
            QHeaderView::section {
                background: #252525;
                color: #888;
                padding: 8px;
                border: none;
            }
        """)
        layout.addWidget(self.table)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        select_btn = QPushButton("Select")
        select_btn.setStyleSheet("""
            QPushButton {
                background: #5a5aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
        """)
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载模型
        self._load_models()
    
    def _load_models(self):
        """加载模型列表"""
        self.table.setRowCount(0)
        
        models = get_recommended_models(self.provider_id)
        
        for i, model in enumerate(models):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(model))
    
    def _on_select(self):
        """选择"""
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.model_selected.emit(item.text())
                self.accept()
