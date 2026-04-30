#!/usr/bin/env python3
"""
模型选择对话框
在首次启动时提示用户选择或下载模型
"""

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QProgressBar, QMessageBox, QFrame, QScrollArea, QCheckBox
)
from PyQt6.QtGui import QFont, QIcon

from .business.model_manager import ModelManager, ModelInfo
from .business.config import AppConfig


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
        info = QLabel("请选择一个或多个模型，或下载新模型")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)
        
        # 全选/取消全选按钮
        select_all_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.on_select_all)
        select_all_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton("取消全选")
        self.deselect_all_button.clicked.connect(self.on_deselect_all)
        select_all_layout.addWidget(self.deselect_all_button)
        select_all_layout.addStretch()
        layout.addLayout(select_all_layout)
        
        # 模型列表
        self.model_list = QListWidget()
        self.model_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
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
        
        self.download_button = QPushButton("下载选中模型")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.on_download)
        button_layout.addWidget(self.download_button)
        
        self.select_button = QPushButton("设置默认模型")
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
        
        # 模型层级使用建议和优先级
        model_layer_suggestions = {
            "qwen2.5:0.5b": {
                "layers": "L0 快反大脑",
                "usage": "轻量级任务、快速响应、意图分类",
                "priority": 1
            },
            "llama3.2:1b": {
                "layers": "L0 快反大脑",
                "usage": "轻量级任务、快速响应",
                "priority": 1
            },
            "qwen2.5:1.5b": {
                "layers": "L0/L1",
                "usage": "轻量级任务、平衡性能和质量",
                "priority": 2
            },
            "qwen2.5:3b": {
                "layers": "L2/L3",
                "usage": "会话缓存、知识库检索、中等复杂度任务",
                "priority": 3
            },
            "llama3.2:3b": {
                "layers": "L2/L3",
                "usage": "会话缓存、知识库检索",
                "priority": 3
            },
            "qwen2.5:7b": {
                "layers": "L4 异构执行",
                "usage": "复杂推理、代码生成、长文本创作",
                "priority": 4
            }
        }
        
        # 按照层级优先级排序模型
        def get_model_priority(model):
            return model_layer_suggestions.get(model.name, {}).get("priority", 999)
        
        models.sort(key=get_model_priority)
        
        for model in models:
            item = QListWidgetItem()
            
            # 创建模型信息框架
            frame = QFrame()
            frame_layout = QVBoxLayout(frame)
            
            # 复选框 + 模型名称
            top_layout = QHBoxLayout()
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            checkbox.stateChanged.connect(lambda state, m=model: self.on_checkbox_changed(state, m))
            top_layout.addWidget(checkbox)
            
            name_label = QLabel(model.name)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            top_layout.addWidget(name_label)
            top_layout.addStretch()
            frame_layout.addLayout(top_layout)
            
            # 模型描述
            desc_label = QLabel(model.description)
            desc_label.setStyleSheet("color: #888;")
            frame_layout.addWidget(desc_label)
            
            # 模型使用层级建议
            layer_info = model_layer_suggestions.get(model.name, {"layers": "通用", "usage": "多种场景"})
            layer_label = QLabel(f"适用层级: {layer_info['layers']}")
            layer_label.setStyleSheet("color: #5a5aff;")
            frame_layout.addWidget(layer_label)
            
            # 模型用途
            usage_label = QLabel(f"用途: {layer_info['usage']}")
            usage_label.setStyleSheet("color: #666;")
            frame_layout.addWidget(usage_label)
            
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
            
            # 存储复选框引用
            item.checkbox = checkbox
            item.model = model
    
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
    
    def on_select_all(self):
        """全选所有模型"""
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if hasattr(item, 'checkbox'):
                item.checkbox.setChecked(True)
        self.update_button_states()
    
    def on_deselect_all(self):
        """取消全选所有模型"""
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if hasattr(item, 'checkbox'):
                item.checkbox.setChecked(False)
        self.update_button_states()
    
    def on_checkbox_changed(self, state, model):
        """复选框状态变化"""
        self.update_button_states()
    
    def update_button_states(self):
        """更新按钮状态"""
        selected_items = [self.model_list.item(i) for i in range(self.model_list.count()) 
                         if hasattr(self.model_list.item(i), 'checkbox') and self.model_list.item(i).checkbox.isChecked()]
        
        has_available = any(hasattr(item, 'model') and item.model.available for item in selected_items)
        has_unavailable = any(hasattr(item, 'model') and not item.model.available for item in selected_items)
        
        self.select_button.setEnabled(has_available)
        self.download_button.setEnabled(has_unavailable)
    
    def on_model_selected(self, item):
        """当选择模型时"""
        if hasattr(item, 'checkbox'):
            item.checkbox.setChecked(not item.checkbox.isChecked())
        self.update_button_states()
    
    def on_download(self):
        """下载模型"""
        # 获取所有选中的未下载模型
        selected_items = [self.model_list.item(i) for i in range(self.model_list.count()) 
                         if hasattr(self.model_list.item(i), 'checkbox') and self.model_list.item(i).checkbox.isChecked()]
        
        models_to_download = [item.model for item in selected_items if hasattr(item, 'model') and not item.model.available]
        
        if not models_to_download:
            QMessageBox.warning(self, "未选择模型", "请选择要下载的模型")
            return
        
        # 批量下载确认
        if len(models_to_download) > 1:
            model_names = "\n".join([model.name for model in models_to_download])
            reply = QMessageBox.question(
                self, "批量下载模型",
                f"确定要下载以下 {len(models_to_download)} 个模型吗？\n\n{model_names}\n\n这可能需要大量时间和网络流量。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 显示批量下载进度对话框
            self._show_batch_download_dialog(models_to_download)
        else:
            # 单个模型下载
            model = models_to_download[0]
            model_name = model.name
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self, "下载模型",
                f"确定要下载模型 {model_name} 吗？\n这可能需要一些时间和网络流量。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 显示下载进度对话框
                from .presentation.panels.model_download_progress import ModelDownloadProgress
                download_progress = ModelDownloadProgress(model_name, self)
                download_progress.download_cancelled.connect(self.on_download_cancelled)
                download_progress.download_paused.connect(self.on_download_paused)
                download_progress.download_resumed.connect(self.on_download_resumed)
                
                # 启动下载线程
                def download_task(m_name, progress_dialog):
                    # 使用新的下载方法
                    success = self.model_manager.download_model(
                        m_name,
                        progress_callback=lambda current, total, status: progress_dialog.update_progress(current, total, status)
                    )
                    # 下载完成后在主线程中调用回调
                    QTimer.singleShot(0, lambda: self.on_download_finished(success, m_name))
                
                import threading
                download_thread = threading.Thread(target=download_task, args=(model_name, download_progress))
                download_thread.daemon = True
                download_thread.start()
                
                # 显示进度对话框
                download_progress.exec()
    
    def on_download_cancelled(self):
        """下载取消"""
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            # 这里可以添加取消下载的逻辑
            pass

    def on_download_paused(self):
        """下载暂停"""
        # 从系统下载中心暂停下载
        from .business.unified_downloader import get_download_center
        download_center = get_download_center()
        tasks = download_center.list_tasks()
        for task in tasks:
            if task.status == "downloading":
                download_center.pause(task.id)
                break

    def on_download_resumed(self):
        """下载继续"""
        # 从系统下载中心继续下载
        from .business.unified_downloader import get_download_center
        download_center = get_download_center()
        tasks = download_center.list_tasks()
        for task in tasks:
            if task.status == "paused":
                download_center.resume(task.id)
                break

    def _show_batch_download_dialog(self, models):
        """显示批量下载进度对话框"""
        from PyQt6.QtCore import Qt, QThread, pyqtSignal
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                   QProgressBar, QPushButton, QListWidget, 
                                   QListWidgetItem, QFrame)
        from PyQt6.QtGui import QFont
        
        class BatchDownloadThread(QThread):
            """批量下载线程"""
            progress_updated = pyqtSignal(str, int, int, str)
            download_finished = pyqtSignal(str, bool)
            all_finished = pyqtSignal()
            
            def __init__(self, models, model_manager):
                super().__init__()
                self.models = models
                self.model_manager = model_manager
                self.is_paused = False
                self.is_cancelled = False
            
            def run(self):
                """执行批量下载"""
                for model in self.models:
                    if self.is_cancelled:
                        break
                    
                    # 等待暂停状态
                    while self.is_paused and not self.is_cancelled:
                        self.msleep(100)
                    
                    if self.is_cancelled:
                        break
                    
                    model_name = model.name
                    
                    # 标记为开始下载
                    self.progress_updated.emit(model_name, 0, 100, "开始下载...")
                    
                    # 使用lambda捕获当前的model_name值，避免闭包问题
                    def make_progress_callback(mn):
                        def progress_callback(current, total, status):
                            if not self.is_cancelled:
                                self.progress_updated.emit(mn, current, total, status)
                        return progress_callback
                    
                    progress_callback = make_progress_callback(model_name)
                    
                    try:
                        # 打印开始下载信息
                        print(f"[BatchDownload] 开始下载模型: {model_name}")
                        
                        # 调用下载方法
                        success = self.model_manager.download_model(
                            model_name,
                            progress_callback=progress_callback
                        )
                        
                        # 打印下载结果
                        print(f"[BatchDownload] 模型 {model_name} 下载结果: {success}")
                        self.download_finished.emit(model_name, success)
                    except Exception as e:
                        # 打印异常信息
                        print(f"[BatchDownload] 模型 {model_name} 下载异常: {e}")
                        import traceback
                        traceback.print_exc()
                        self.download_finished.emit(model_name, False)
                
                if not self.is_cancelled:
                    self.all_finished.emit()
            
            def pause(self):
                """暂停下载"""
                self.is_paused = True
            
            def resume(self):
                """继续下载"""
                self.is_paused = False
            
            def cancel(self):
                """取消下载"""
                self.is_cancelled = True
                self.is_paused = False
        
        class BatchDownloadDialog(QDialog):
            """批量下载进度对话框"""
            def __init__(self, models, model_manager, parent=None):
                super().__init__(parent)
                self.models = models
                self.model_manager = model_manager
                self.init_ui()
                self.start_download()
            
            def init_ui(self):
                """初始化UI"""
                self.setWindowTitle("批量下载模型")
                self.setMinimumWidth(600)
                self.setMinimumHeight(400)
                
                layout = QVBoxLayout(self)
                
                # 标题
                title = QLabel(f"正在批量下载 {len(self.models)} 个模型")
                title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(title)
                
                # 提示信息
                info = QLabel("正在按顺序下载模型，请耐心等待...")
                info.setAlignment(Qt.AlignmentFlag.AlignCenter)
                info.setStyleSheet("color: #888;")
                layout.addWidget(info)
                
                # 模型列表
                self.model_list = QListWidget()
                self.model_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
                layout.addWidget(self.model_list)
                
                # 初始化模型列表
                self.model_widgets = {}
                for model in self.models:
                    item = QListWidgetItem()
                    
                    # 创建模型信息框架
                    frame = QFrame()
                    frame_layout = QVBoxLayout(frame)
                    
                    # 模型名称
                    name_label = QLabel(model.name)
                    name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                    frame_layout.addWidget(name_label)
                    
                    # 进度条
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setValue(0)
                    progress_bar.setFormat("0%")
                    frame_layout.addWidget(progress_bar)
                    
                    # 状态标签
                    status_label = QLabel("等待下载...")
                    status_label.setStyleSheet("color: #666;")
                    frame_layout.addWidget(status_label)
                    
                    item.setSizeHint(frame.sizeHint())
                    self.model_list.addItem(item)
                    self.model_list.setItemWidget(item, frame)
                    
                    self.model_widgets[model.name] = {
                        'progress': progress_bar,
                        'status': status_label
                    }
                
                # 按钮
                button_layout = QHBoxLayout()
                
                self.pause_button = QPushButton("⏸ 暂停")
                self.pause_button.clicked.connect(self.on_pause_resume)
                button_layout.addWidget(self.pause_button)
                
                self.cancel_button = QPushButton("取消")
                self.cancel_button.clicked.connect(self.on_cancel)
                button_layout.addWidget(self.cancel_button)
                
                layout.addLayout(button_layout)
                
                # 线程控制
                self.is_paused = False
                self.download_thread = None
            
            def start_download(self):
                """开始下载"""
                self.download_thread = BatchDownloadThread(self.models, self.model_manager)
                self.download_thread.progress_updated.connect(self.update_progress)
                self.download_thread.download_finished.connect(self.on_model_finished)
                self.download_thread.all_finished.connect(self.on_all_finished)
                self.download_thread.start()
            
            def update_progress(self, model_name, current, total, status):
                """更新进度"""
                try:
                    if model_name in self.model_widgets:
                        widget = self.model_widgets[model_name]
                        # 处理不同类型的进度回调
                        if isinstance(current, int) and isinstance(total, int):
                            if total > 0:
                                if total == 100:
                                    # 百分比进度: (pct, 100, status)
                                    pct = min(100, current)
                                else:
                                    # 字节进度: (current_bytes, total_bytes, status)
                                    pct = min(100, int((current / total) * 100))
                                widget['progress'].setValue(pct)
                                widget['progress'].setFormat(f"{pct}%")
                        widget['status'].setText(status)
                except Exception as e:
                    print(f"[BatchDownloadDialog] 进度更新错误: {e}")
            
            def on_model_finished(self, model_name, success):
                """单个模型下载完成"""
                if model_name in self.model_widgets:
                    widget = self.model_widgets[model_name]
                    if success:
                        widget['status'].setText("✅ 下载完成")
                        widget['status'].setStyleSheet("color: #22c55e;")
                    else:
                        widget['status'].setText("❌ 下载失败")
                        widget['status'].setStyleSheet("color: #ef4444;")
            
            def on_all_finished(self):
                """所有模型下载完成"""
                self.pause_button.setEnabled(False)
                self.cancel_button.setText("关闭")
                
                # 检查下载结果
                success_count = 0
                fail_count = 0
                for model_name, widget in self.model_widgets.items():
                    status_text = widget['status'].text()
                    if "✅" in status_text:
                        success_count += 1
                    elif "❌" in status_text:
                        fail_count += 1
                
                # 显示结果
                msg_box = QMessageBox(self)
                if fail_count == 0:
                    msg_box.setWindowTitle("批量下载完成")
                    msg_box.setText(f"所有 {len(self.models)} 个模型已下载完成！\n\n成功: {success_count} 个\n失败: {fail_count} 个")
                    msg_box.setIcon(QMessageBox.Icon.Information)
                else:
                    msg_box.setWindowTitle("批量下载完成")
                    msg_box.setText(f"批量下载已完成！\n\n成功: {success_count} 个\n失败: {fail_count} 个\n\n失败的模型可以稍后重试。")
                    msg_box.setIcon(QMessageBox.Icon.Warning)
                
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
                
                # 重新加载模型列表
                if success_count > 0:
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, self.parent().load_models)
            
            def on_pause_resume(self):
                """暂停/继续下载"""
                if self.is_paused:
                    # 继续下载
                    self.is_paused = False
                    self.pause_button.setText("⏸ 暂停")
                    if self.download_thread:
                        self.download_thread.resume()
                else:
                    # 暂停下载
                    self.is_paused = True
                    self.pause_button.setText("▶ 继续")
                    if self.download_thread:
                        self.download_thread.pause()
            
            def on_cancel(self):
                """取消下载"""
                if self.download_thread:
                    self.download_thread.cancel()
                self.close()
        
        # 显示批量下载对话框
        dialog = BatchDownloadDialog(models, self.model_manager, self)
        dialog.exec()
    
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
            # 下载成功处理
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("下载完成")
            msg_box.setText(f"模型 {model_name} 下载成功！")
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            
            # 重新加载模型列表
            self.load_models()
            
            # 如果只有一个模型，设置为默认模型
            available_models = self.model_manager.get_available_models()
            for model in available_models:
                if model.name == model_name:
                    self.model_manager.set_default_model(model_name)
                    break
        else:
            # 下载失败处理
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("下载失败")
            msg_box.setText(f"模型 {model_name} 下载失败。\n\n可能的原因：\n1. 网络连接问题\n2. 磁盘空间不足\n3. ModelScope服务不可用\n\n请检查网络连接后重试。")
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Retry)
            result = msg_box.exec()
            
            # 如果用户选择重试，重新触发下载
            if result == QMessageBox.StandardButton.Retry:
                # 重新设置下载状态
                self.download_button.setEnabled(True)
                # 触发下载按钮的点击事件
                self.download_button.click()
        
        # 重置UI
        self.download_button.setEnabled(True)
        self.select_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
    
    def on_select(self):
        """选择模型"""
        selected_items = [self.model_list.item(i) for i in range(self.model_list.count()) 
                         if hasattr(self.model_list.item(i), 'checkbox') and self.model_list.item(i).checkbox.isChecked()]
        
        available_models = [item.model for item in selected_items if hasattr(item, 'model') and item.model.available]
        
        if available_models:
            # 设置第一个可用模型为默认模型
            default_model = available_models[0]
            self.model_manager.set_default_model(default_model.name)
            self.model_selected.emit(default_model.name)
            self.accept()
