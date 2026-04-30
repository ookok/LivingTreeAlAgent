"""
配置仪表盘组件 - 可视化配置面板
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QGridLayout, QGroupBox, QScrollArea
)


class ConfigDashboard(QWidget):
    """配置仪表盘组件"""
    
    config_clicked = pyqtSignal(str)
    recommendation_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigDashboard")
        self._config_status = {}
        self._recommendations = []
        
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("⚙️ 配置仪表盘"))
        title_layout.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
        """)
        refresh_btn.clicked.connect(self._on_refresh)
        title_layout.addWidget(refresh_btn)
        layout.addLayout(title_layout)
        
        # 配置状态卡片
        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)
        
        self._basic_card = self._create_status_card("基础设置", "90%", "#3b82f6")
        self._model_card = self._create_status_card("模型配置", "60%", "#8b5cf6")
        self._advanced_card = self._create_status_card("高级选项", "30%", "#f59e0b")
        
        cards_layout.addWidget(self._basic_card, 0, 0)
        cards_layout.addWidget(self._model_card, 0, 1)
        cards_layout.addWidget(self._advanced_card, 0, 2)
        
        layout.addLayout(cards_layout)
        
        # 总体进度
        progress_group = QGroupBox("配置进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self._overall_progress = QProgressBar()
        self._overall_progress.setValue(70)
        self._overall_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                height: 8px;
                background: #334155;
            }
            QProgressBar::chunk {
                background: linear-gradient(90deg, #3b82f6, #8b5cf6);
            }
        """)
        progress_layout.addWidget(self._overall_progress)
        
        progress_label = QLabel("已完成 70%")
        progress_label.setStyleSheet("color: #64748b; font-size: 12px;")
        progress_layout.addWidget(progress_label)
        
        layout.addWidget(progress_group)
        
        # 推荐配置
        recommend_group = QGroupBox("🎯 推荐配置")
        recommend_layout = QVBoxLayout(recommend_group)
        
        self._recommend_scroll = QScrollArea()
        self._recommend_scroll.setWidgetResizable(True)
        self._recommend_content = QWidget()
        self._recommend_inner_layout = QVBoxLayout(self._recommend_content)
        self._recommend_scroll.setWidget(self._recommend_content)
        
        recommend_layout.addWidget(self._recommend_scroll)
        layout.addWidget(recommend_group)
        
        # 智能提示
        hint_group = QGroupBox("💡 智能提示")
        hint_layout = QVBoxLayout(hint_group)
        
        self._hint_label = QLabel("检测到您经常使用Python代码生成，建议配置代码执行超时时间。")
        self._hint_label.setStyleSheet("color: #9ca3af;")
        hint_layout.addWidget(self._hint_label)
        
        layout.addWidget(hint_group)
    
    def _create_status_card(self, title: str, value: str, color: str) -> QFrame:
        """创建状态卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #1e293b;
                border-radius: 8px;
                padding: 16px;
                border-left: 3px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        label = QLabel(title)
        label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("color: #f1f5f9; font-size: 24px; font-weight: 600;")
        layout.addWidget(value_label)
        
        return card
    
    def update_config_status(self, status: dict):
        """更新配置状态"""
        self._config_status = status
        
        if "basic" in status:
            self._basic_card.findChild(QLabel, "").setText(status["basic"])
        if "model" in status:
            self._model_card.findChild(QLabel, "").setText(status["model"])
        if "advanced" in status:
            self._advanced_card.findChild(QLabel, "").setText(status["advanced"])
        
        self._update_overall_progress()
    
    def _update_overall_progress(self):
        """更新总体进度"""
        basic = int(self._config_status.get("basic", "0%").replace("%", ""))
        model = int(self._config_status.get("model", "0%").replace("%", ""))
        advanced = int(self._config_status.get("advanced", "0%").replace("%", ""))
        
        overall = (basic + model + advanced) // 3
        self._overall_progress.setValue(overall)
    
    def update_recommendations(self, recommendations: list):
        """更新推荐配置"""
        self._recommendations = recommendations
        
        # 清空现有内容
        while self._recommend_inner_layout.count():
            child = self._recommend_inner_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 添加推荐项
        for rec in recommendations:
            item = QFrame()
            item.setStyleSheet("""
                QFrame {
                    background: #1e293b;
                    border-radius: 4px;
                    padding: 8px;
                    margin-bottom: 8px;
                }
            """)
            
            layout = QHBoxLayout(item)
            
            checkbox = QLabel("[ ]")
            checkbox.setStyleSheet("color: #64748b;")
            layout.addWidget(checkbox)
            
            content = QLabel(f"{rec['config_key']}: {rec['reason']}")
            content.setStyleSheet("color: #e2e8f0; font-size: 12px;")
            content.setWordWrap(True)
            layout.addWidget(content)
            
            priority = QLabel(rec['priority'].upper())
            priority.setStyleSheet(f"""
                color: {'#ef4444' if rec['priority'] == 'high' else '#f59e0b' if rec['priority'] == 'medium' else '#10b981'};
                font-size: 10px;
                font-weight: 600;
            """)
            layout.addWidget(priority)
            
            self._recommend_inner_layout.addWidget(item)
    
    def _on_refresh(self):
        """刷新配置"""
        self.config_clicked.emit("refresh")