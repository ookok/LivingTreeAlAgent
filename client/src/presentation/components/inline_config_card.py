"""
聊天内联配置卡片 - 在聊天窗口中直接展示配置表单
"""

from typing import Dict, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QWidget
)


class InlineConfigCard(QFrame):
    """聊天内联配置卡片"""
    
    config_completed = pyqtSignal(str, dict)
    config_skipped = pyqtSignal(str)
    
    def __init__(self, config_type: str, parent=None):
        super().__init__(parent)
        self._config_type = config_type
        self._fields: Dict[str, QLineEdit] = {}
        
        self._build_ui()
    
    def _build_ui(self):
        """构建内联配置卡片"""
        self.setStyleSheet("""
            QFrame {
                background: #1e293b;
                border: 1px solid #3b82f6;
                border-radius: 12px;
                padding: 16px;
                margin: 8px 0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 标题栏
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"⚙️ 配置 {self._get_config_name()}")
        title_label.setStyleSheet("color: #f1f5f9; font-size: 14px; font-weight: 500;")
        header_layout.addWidget(title_label)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                color: #f1f5f9;
            }
        """)
        close_btn.clicked.connect(self._on_skip)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        # 描述
        desc_label = QLabel(self._get_config_description())
        desc_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 配置表单
        self._create_form_fields()
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        skip_btn = QPushButton("稍后配置")
        skip_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                color: #f1f5f9;
            }
        """)
        skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(skip_btn)
        
        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_form_fields(self):
        """创建表单字段"""
        fields = self._get_config_fields()
        
        for field_info in fields:
            field_layout = QHBoxLayout()
            
            label = QLabel(field_info["label"])
            label.setStyleSheet("color: #9ca3af; font-size: 12px; min-width: 80px;")
            field_layout.addWidget(label)
            
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(field_info.get("placeholder", ""))
            line_edit.setStyleSheet("""
                QLineEdit {
                    background: #0f172a;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 6px 8px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border-color: #3b82f6;
                }
            """)
            
            if field_info.get("type") == "password":
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            
            self._fields[field_info["key"]] = line_edit
            field_layout.addWidget(line_edit)
            
            self.layout().addLayout(field_layout)
    
    def _get_config_name(self) -> str:
        """获取配置名称"""
        names = {
            "openai": "OpenAI API",
            "ollama": "Ollama",
            "browser": "浏览器自动化",
            "wecom": "企业微信",
            "wechat": "微信",
            "mcp": "MCP工具",
            "search": "智能搜索",
            "github": "GitHub"
        }
        return names.get(self._config_type, self._config_type)
    
    def _get_config_description(self) -> str:
        """获取配置描述"""
        descriptions = {
            "openai": "使用OpenAI模型需要配置API密钥",
            "ollama": "使用本地Ollama模型需要配置服务地址",
            "browser": "浏览器自动化功能需要配置浏览器路径",
            "wecom": "企业微信功能需要配置API密钥",
            "wechat": "微信功能需要配置本地数据库路径",
            "mcp": "MCP工具需要配置服务器地址",
            "search": "智能搜索功能需要配置搜索引擎",
            "github": "GitHub功能需要配置访问令牌"
        }
        return descriptions.get(self._config_type, "")
    
    def _get_config_fields(self) -> List[Dict]:
        """获取配置字段"""
        fields_map = {
            "openai": [
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "base_url", "label": "Base URL", "placeholder": "https://api.openai.com/v1"}
            ],
            "ollama": [
                {"key": "host", "label": "服务地址", "placeholder": "http://localhost:11434"}
            ],
            "browser": [
                {"key": "chrome_path", "label": "Chrome路径", "placeholder": "C:\\Program Files\\Google\\Chrome\\chrome.exe"}
            ],
            "wecom": [
                {"key": "corp_id", "label": "企业ID"},
                {"key": "corp_secret", "label": "应用密钥", "type": "password"}
            ],
            "wechat": [
                {"key": "db_path", "label": "数据库路径", "placeholder": "~/Documents/WeChat Files/"}
            ],
            "mcp": [
                {"key": "server_url", "label": "服务器地址"},
                {"key": "api_key", "label": "API Key", "type": "password"}
            ],
            "search": [
                {"key": "google_api_key", "label": "Google API Key", "type": "password"},
                {"key": "bing_api_key", "label": "Bing API Key", "type": "password"}
            ],
            "github": [
                {"key": "access_token", "label": "访问令牌", "type": "password"}
            ]
        }
        return fields_map.get(self._config_type, [])
    
    def _on_save(self):
        """保存配置"""
        config_data = {}
        for key, field in self._fields.items():
            config_data[key] = field.text()
        
        self.config_completed.emit(self._config_type, config_data)
        self.hide()
    
    def _on_skip(self):
        """跳过配置"""
        self.config_skipped.emit(self._config_type)
        self.hide()