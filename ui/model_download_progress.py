#!/usr/bin/env python3
"""
模型下载进度显示组件
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QDialog
)
from PyQt6.QtGui import QFont


class ModelDownloadProgress(QDialog):
    """模型下载进度显示组件"""
    download_cancelled = pyqtSignal()
    
    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.model_name = model_name
        self.is_cancelled = False
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle(f"下载模型 - {self.model_name}")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel(f"正在下载模型: {self.model_name}")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 提示信息
        info = QLabel("首次下载模型可能需要一些时间，请耐心等待...")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("准备下载...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.on_cancel)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def update_progress(self, current, total, status):
        """更新进度
        
        Args:
            current: 当前进度
            total: 总进度
            status: 状态信息
        """
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)
        self.status_label.setText(status)
    
    def on_cancel(self):
        """取消下载"""
        self.is_cancelled = True
        self.download_cancelled.emit()
        self.close()
    
    def closeEvent(self, event):
        """关闭事件"""
        if not self.is_cancelled:
            # 防止用户误关闭
            event.ignore()
        else:
            event.accept()
