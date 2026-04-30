"""
配置引导卡片组件 - 交互式配置教程
"""

from typing import List, Dict
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)


class ConfigTutorialCard(QFrame):
    """配置引导卡片组件"""
    
    step_completed = pyqtSignal(int)
    tutorial_finished = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigTutorialCard")
        self._steps: List[Dict] = []
        self._current_step = 0
        
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        self.setStyleSheet("""
            QFrame {
                background: #1e293b;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # 标题区域
        title_layout = QHBoxLayout()
        self._title_label = QLabel("配置引导")
        self._title_label.setStyleSheet("color: #f1f5f9; font-size: 18px; font-weight: 600;")
        title_layout.addWidget(self._title_label)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 20px;
            }
            QPushButton:hover {
                color: #f1f5f9;
            }
        """)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        layout.addLayout(title_layout)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                height: 4px;
                background: #334155;
            }
            QProgressBar::chunk {
                background: #3b82f6;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        # 步骤内容
        self._step_content = QFrame()
        self._step_content.setStyleSheet("""
            QFrame {
                background: #0f172a;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        step_layout = QVBoxLayout(self._step_content)
        
        self._step_title = QLabel("步骤标题")
        self._step_title.setStyleSheet("color: #f1f5f9; font-size: 16px; font-weight: 500;")
        step_layout.addWidget(self._step_title)
        
        self._step_description = QLabel("步骤描述")
        self._step_description.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self._step_description.setWordWrap(True)
        step_layout.addWidget(self._step_description)
        
        self._action_btn = QPushButton("下一步")
        self._action_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        self._action_btn.clicked.connect(self._on_next)
        step_layout.addWidget(self._action_btn)
        
        layout.addWidget(self._step_content)
    
    def add_step(self, title: str, description: str, action: str = "下一步"):
        """添加引导步骤"""
        self._steps.append({
            "title": title,
            "description": description,
            "action": action
        })
    
    def start(self):
        """开始引导"""
        self._current_step = 0
        self._update_step()
    
    def _update_step(self):
        """更新步骤显示"""
        if self._current_step < len(self._steps):
            step = self._steps[self._current_step]
            
            self._title_label.setText(f"配置引导 ({self._current_step + 1}/{len(self._steps)})")
            self._step_title.setText(step["title"])
            self._step_description.setText(step["description"])
            self._action_btn.setText(step["action"])
            
            progress = ((self._current_step + 1) / len(self._steps)) * 100
            self._progress_bar.setValue(int(progress))
            
            if self._current_step == len(self._steps) - 1:
                self._action_btn.setText("完成")
        else:
            self.tutorial_finished.emit()
            self.close()
    
    def _on_next(self):
        """下一步"""
        self.step_completed.emit(self._current_step)
        self._current_step += 1
        self._update_step()
    
    def get_current_step(self) -> int:
        """获取当前步骤"""
        return self._current_step
    
    def get_total_steps(self) -> int:
        """获取总步骤数"""
        return len(self._steps)