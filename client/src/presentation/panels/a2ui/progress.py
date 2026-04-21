"""
进度管理器

处理所有资源加载和启动的进度动画或等待提示
"""

import logging
from typing import Dict, Optional, Callable, List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QDialog
from PyQt6.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)


class ProgressDialog(QDialog):
    """
    进度对话框
    """
    
    def __init__(self, title: str, parent=None):
        """
        初始化进度对话框
        
        Args:
            title: 对话框标题
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedSize(400, 150)
        
        layout = QVBoxLayout(self)
        
        self._label = QLabel("加载中...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        layout.addWidget(self._progress_bar)
        
        self._sub_label = QLabel("")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self._sub_label)
    
    def set_progress(self, value: int):
        """
        设置进度值
        
        Args:
            value: 进度值（0-100）
        """
        if self._progress_bar:
            self._progress_bar.setValue(value)
    
    def set_text(self, text: str):
        """
        设置文本
        
        Args:
            text: 文本内容
        """
        if self._label:
            self._label.setText(text)
    
    def set_sub_text(self, text: str):
        """
        设置子文本
        
        Args:
            text: 子文本内容
        """
        if self._sub_label:
            self._sub_label.setText(text)


class ProgressManager:
    """
    进度管理器
    管理所有进度对话框
    """
    
    def __init__(self):
        self._progress_dialogs: Dict[str, ProgressDialog] = {}
        self._global_progress: Optional[ProgressDialog] = None
    
    def create_progress(self, task_id: str, title: str, parent=None) -> ProgressDialog:
        """
        创建进度对话框
        
        Args:
            task_id: 任务 ID
            title: 对话框标题
            parent: 父窗口
            
        Returns:
            ProgressDialog: 进度对话框
        """
        # 如果已经存在，返回现有对话框
        if task_id in self._progress_dialogs:
            return self._progress_dialogs[task_id]
        
        # 创建新对话框
        dialog = ProgressDialog(title, parent)
        self._progress_dialogs[task_id] = dialog
        dialog.show()
        
        return dialog
    
    def update_progress(self, task_id: str, value: int, text: Optional[str] = None, sub_text: Optional[str] = None):
        """
        更新进度
        
        Args:
            task_id: 任务 ID
            value: 进度值（0-100）
            text: 文本内容
            sub_text: 子文本内容
        """
        if task_id in self._progress_dialogs:
            dialog = self._progress_dialogs[task_id]
            dialog.set_progress(value)
            if text:
                dialog.set_text(text)
            if sub_text:
                dialog.set_sub_text(sub_text)
    
    def close_progress(self, task_id: str):
        """
        关闭进度对话框
        
        Args:
            task_id: 任务 ID
        """
        if task_id in self._progress_dialogs:
            dialog = self._progress_dialogs[task_id]
            dialog.close()
            del self._progress_dialogs[task_id]
    
    def create_global_progress(self, title: str, parent=None) -> ProgressDialog:
        """
        创建全局进度对话框
        
        Args:
            title: 对话框标题
            parent: 父窗口
            
        Returns:
            ProgressDialog: 进度对话框
        """
        if not self._global_progress:
            self._global_progress = ProgressDialog(title, parent)
            self._global_progress.show()
        return self._global_progress
    
    def update_global_progress(self, value: int, text: Optional[str] = None, sub_text: Optional[str] = None):
        """
        更新全局进度
        
        Args:
            value: 进度值（0-100）
            text: 文本内容
            sub_text: 子文本内容
        """
        if self._global_progress:
            self._global_progress.set_progress(value)
            if text:
                self._global_progress.set_text(text)
            if sub_text:
                self._global_progress.set_sub_text(sub_text)
    
    def close_global_progress(self):
        """
        关闭全局进度对话框
        """
        if self._global_progress:
            self._global_progress.close()
            self._global_progress = None
    
    def clear(self):
        """
        清空所有进度对话框
        """
        for task_id in list(self._progress_dialogs.keys()):
            self.close_progress(task_id)
        self.close_global_progress()
