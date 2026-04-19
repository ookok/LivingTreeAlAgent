#!/usr/bin/env python3
"""
模型选择对话框
在首次启动时提示用户选择或下载模型
"""

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QProgressBar, QMessageBox, QFrame, QScrollArea
)
from PyQt6.QtGui import QFont, QIcon

from core.model_manager import ModelManager, ModelInfo
from core.config import AppConfig


class DownloadThread(QThread):
    """下载线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, model_manager, model_name):
        super().__init__()
        self.model_manager = model_manager
        self.model_name = model_name
    
    def run(self):
        def progress_callback(current, total, status):
            self.progress.emit(current, total, status)
        
        success = self.model_manager.download_model(self.model_name, progress_callback)
        self.finished.emit(success, self.model_name)


class ModelSelectorDialog(QDialog):
    """模型选择对话框"""
    model_selected = pyqtSignal(str)
    
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.model_manager = ModelManager(config)
        self.download_thread = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("选择模型")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("选择模型")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 提示信息
        info = QLabel("请选择一个模型，或下载新模型")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)
        
        # 模型列表
        self.model_list = QListWidget()
        self.model_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.model_list.itemClicked.connect(self.on_model_selected)
        layout.addWidget(self.model_list)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.download_button = QPushButton("下载模型")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.on_download)
        button_layout.addWidget(self.download_button)
        
        self.select_button = QPushButton("选择")
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self.on_select)
        button_layout.addWidget(self.select_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 加载模型列表
        self.load_models()
    
    def load_models(self):
        """加载模型列表"""
        self.model_list.clear()
        
        models = self.model_manager.get_available_models()
        
        for model in models:
            item = QListWidgetItem()
            
            # 创建模型信息框架
            frame = QFrame()
            frame_layout = QVBoxLayout(frame)
            
            # 模型名称
            name_label = QLabel(model.name)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            frame_layout.addWidget(name_label)
            
            # 模型描述
            desc_label = QLabel(model.description)
            desc_label.setStyleSheet("color: #888;")
            frame_layout.addWidget(desc_label)
            
            # 模型状态
            status_label = QLabel()
            if model.available:
                status_label.setText("✅ 可用")
                status_label.setStyleSheet("color: #22c55e;")
            else:
                status_label.setText("📥 未下载")
                status_label.setStyleSheet("color: #f59e0b;")
            frame_layout.addWidget(status_label)
            
            # 模型大小
            if model.size:
                size_label = QLabel(f"大小: {self.format_size(model.size)}")
                size_label.setStyleSheet("color: #666;")
                frame_layout.addWidget(size_label)
            
            item.setSizeHint(frame.sizeHint())
            self.model_list.addItem(item)
            self.model_list.setItemWidget(item, frame)
    
    def format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def on_model_selected(self, item):
        """当选择模型时"""
        index = self.model_list.row(item)
        models = self.model_manager.get_available_models()
        if 0 <= index < len(models):
            model = models[index]
            self.selected_model = model
            
            # 更新按钮状态
            if model.available:
                self.select_button.setEnabled(True)
                self.download_button.setEnabled(False)
            else:
                self.select_button.setEnabled(False)
                self.download_button.setEnabled(True)
    
    def on_download(self):
        """下载模型"""
        if hasattr(self, 'selected_model') and not self.selected_model.available:
            model_name = self.selected_model.name
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self, "下载模型",
                f"确定要下载模型 {model_name} 吗？\n这可能需要一些时间和网络流量。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 显示下载进度对话框
                from ui.model_download_progress import ModelDownloadProgress
                self.download_progress = ModelDownloadProgress(model_name, self)
                self.download_progress.download_cancelled.connect(self.on_download_cancelled)
                
                # 启动下载线程
                def download_task():
                    # 使用新的下载方法
                    success = self.model_manager.download_model(
                        model_name,
                        progress_callback=lambda current, total, status: self.download_progress.update_progress(current, total, status)
                    )
                    # 下载完成后调用回调
                    self.on_download_finished(success, model_name)
                
                import threading
                self.download_thread = threading.Thread(target=download_task)
                self.download_thread.daemon = True
                self.download_thread.start()
                
                # 显示进度对话框
                self.download_progress.exec()
    
    def on_download_cancelled(self):
        """下载取消"""
        if self.download_thread and self.download_thread.isRunning():
            # 这里可以添加取消下载的逻辑
            pass
    
    def on_progress(self, current, total, status):
        """下载进度更新"""
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)
        self.status_label.setText(status)
    
    def on_download_finished(self, success, model_name):
        """下载完成"""
        # 关闭下载进度对话框
        if hasattr(self, 'download_progress'):
            self.download_progress.close()
        
        if success:
            QMessageBox.information(self, "下载完成", f"模型 {model_name} 下载成功！")
            # 重新加载模型列表
            self.load_models()
        else:
            QMessageBox.error(self, "下载失败", f"模型 {model_name} 下载失败，请检查网络连接。")
        
        # 重置UI
        self.download_button.setEnabled(True)
        self.select_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
    
    def on_select(self):
        """选择模型"""
        if hasattr(self, 'selected_model') and self.selected_model.available:
            model_name = self.selected_model.name
            self.model_manager.set_default_model(model_name)
            self.model_selected.emit(model_name)
            self.accept()
