"""
配置成功横幅 - 配置完成后提供即时反馈
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class ConfigSuccessBanner(QFrame):
    """配置成功横幅"""
    
    test_requested = pyqtSignal(str)
    
    def __init__(self, config_type: str, parent=None):
        super().__init__(parent)
        self._config_type = config_type
        
        self._build_ui()
    
    def _build_ui(self):
        """构建横幅UI"""
        self.setStyleSheet("""
            QFrame {
                background: linear-gradient(90deg, #10b981, #059669);
                border-radius: 8px;
                padding: 12px 16px;
                margin: 8px 0;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        
        # 图标
        check_icon = QLabel("✅")
        check_icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(check_icon)
        
        # 内容
        content = QLabel(f"已成功配置 {self._get_config_name()}！现在可以使用相关功能了。")
        content.setStyleSheet("color: white; font-size: 13px;")
        layout.addWidget(content)
        
        layout.addStretch()
        
        # 测试按钮
        test_btn = QPushButton("立即测试")
        test_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #10b981;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #f0fdf4;
            }
        """)
        test_btn.clicked.connect(self._on_test)
        layout.addWidget(test_btn)
    
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
    
    def _on_test(self):
        """测试配置"""
        self.test_requested.emit(self._config_type)