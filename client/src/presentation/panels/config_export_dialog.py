"""
配置导入导出对话框
Config Import/Export Dialog

支持系统配置的一键导入导出。
"""

import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QListWidget, QListWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QGroupBox,
    QLineEdit, QComboBox, QTabWidget, QTextBrowser
)
from PyQt6.QtGui import QFont

from core.config_manager import ConfigManager, ExportResult, ImportResult


class ExportWorker(QThread):
    """导出后台线程"""
    finished = pyqtSignal(ExportResult)
    progress = pyqtSignal(str, float)
    
    def __init__(self, manager: ConfigManager, items: list, zip_path: str, include_sessions: bool):
        super().__init__()
        self.manager = manager
        self.items = items
        self.zip_path = zip_path
        self.include_sessions = include_sessions
    
    def run(self):
        if not self.items:
            result = self.manager.export_all(
                self.zip_path,
                self.include_sessions,
                lambda msg, prog: self.progress.emit(msg, prog)
            )
        else:
            result = self.manager.export_items(
                self.items,
                self.zip_path
            )
        self.finished.emit(result)


class ImportWorker(QThread):
    """导入后台线程"""
    finished = pyqtSignal(ImportResult)
    progress = pyqtSignal(str, float)
    
    def __init__(self, manager: ConfigManager, source: str, source_type: str):
        super().__init__()
        self.manager = manager
        self.source = source
        self.source_type = source_type
    
    def run(self):
        if self.source_type == "file":
            result = self.manager.import_from_file(
                self.source,
                merge=True,
                progress_callback=lambda msg, prog: self.progress.emit(msg, prog)
            )
        elif self.source_type == "url":
            result = self.manager.import_from_url(
                self.source,
                progress_callback=lambda msg, prog: self.progress.emit(msg, prog)
            )
        elif self.source_type == "zip":
            result = self.manager.import_from_zip(
                self.source,
                merge=True,
                progress_callback=lambda msg, prog: self.progress.emit(msg, prog)
            )
        else:
            result = ImportResult(success=False, errors=["未知的导入类型"])
        
        self.finished.emit(result)


class ConfigExportDialog(QWidget):
    """
    配置导入导出对话框
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config_manager = ConfigManager()
        self._worker = None
        
        self._setup_ui()
        self._load_items()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("配置导入导出")
        self.setFixedSize(600, 500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("⚙️ 配置导入导出")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Tab 切换
        tabs = QTabWidget()
        
        # 导出页
        tabs.addTab(self._create_export_tab(), "📤 导出")
        
        # 导入页
        tabs.addTab(self._create_import_tab(), "📥 导入")
        
        # 备份管理页
        tabs.addTab(self._create_backup_tab(), "💾 备份管理")
        
        layout.addWidget(tabs)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #3b82f6;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666;")
        layout.addWidget(self._status_label)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
    
    def _create_export_tab(self) -> QWidget:
        """创建导出页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 可导出项目
        group = QGroupBox("选择要导出的项目")
        group_layout = QVBoxLayout(group)
        
        self._export_items = QListWidget()
        self._export_items.setMaximumHeight(200)
        self._export_items.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        group_layout.addWidget(self._export_items)
        
        # 全选/取消
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(lambda: self._select_all_items(True))
        deselect_btn = QPushButton("取消全选")
        deselect_btn.clicked.connect(lambda: self._select_all_items(False))
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_btn)
        group_layout.addLayout(btn_layout)
        
        layout.addWidget(group)
        
        # 选项
        options_group = QGroupBox("导出选项")
        options_layout = QVBoxLayout(options_group)
        
        self._include_sessions = QCheckBox("包含会话历史（聊天记录）")
        options_layout.addWidget(self._include_sessions)
        
        layout.addWidget(options_group)
        
        # 一键导出全部按钮
        export_all_btn = QPushButton("📦 导出全部配置")
        export_all_btn.setFixedHeight(45)
        export_all_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        export_all_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        export_all_btn.clicked.connect(self._export_all)
        layout.addWidget(export_all_btn)
        
        # 选择导出
        export_sel_btn = QPushButton("📤 导出选中项目")
        export_sel_btn.clicked.connect(self._export_selected)
        layout.addWidget(export_sel_btn)
        
        layout.addStretch()
        
        return widget
    
    def _create_import_tab(self) -> QWidget:
        """创建导入页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 从文件导入
        file_group = QGroupBox("从本地文件导入")
        file_layout = QVBoxLayout(file_group)
        
        file_path_layout = QHBoxLayout()
        self._import_file_path = QLineEdit()
        self._import_file_path.setPlaceholderText("选择文件...")
        self._import_file_path.setReadOnly(True)
        file_path_layout.addWidget(self._import_file_path)
        
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_import_file)
        file_path_layout.addWidget(browse_btn)
        
        file_layout.addLayout(file_path_layout)
        
        import_file_btn = QPushButton("📥 从文件导入")
        import_file_btn.clicked.connect(lambda: self._import_from_source("file"))
        file_layout.addWidget(import_file_btn)
        
        layout.addWidget(file_group)
        
        # 从URL导入
        url_group = QGroupBox("从网络URL导入")
        url_layout = QVBoxLayout(url_group)
        
        self._import_url = QLineEdit()
        self._import_url.setPlaceholderText("输入专家/技能包的URL地址...")
        url_layout.addWidget(self._import_url)
        
        self._import_type = QComboBox()
        self._import_type.addItems(["自动检测", "专家人格", "技能包", "用户画像", "系统配置"])
        url_layout.addWidget(self._import_type)
        
        import_url_btn = QPushButton("🌐 从URL导入")
        import_url_btn.clicked.connect(lambda: self._import_from_source("url"))
        url_layout.addWidget(import_url_btn)
        
        layout.addWidget(url_group)
        
        # 说明
        info = QLabel(
            "支持格式：ZIP压缩包、JSON配置文件、Markdown文档\n"
            "导入会自动合并，不会覆盖已有数据"
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)
        
        layout.addStretch()
        
        return widget
    
    def _create_backup_tab(self) -> QWidget:
        """创建备份管理页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # 创建备份
        backup_group = QGroupBox("创建新备份")
        backup_layout = QVBoxLayout(backup_group)
        
        backup_name_layout = QHBoxLayout()
        backup_name_layout.addWidget(QLabel("备份名称:"))
        self._backup_name = QLineEdit()
        self._backup_name.setPlaceholderText("留空自动生成")
        backup_name_layout.addWidget(self._backup_name)
        backup_layout.addLayout(backup_name_layout)
        
        create_backup_btn = QPushButton("💾 创建备份")
        create_backup_btn.clicked.connect(self._create_backup)
        backup_layout.addWidget(create_backup_btn)
        
        layout.addWidget(backup_group)
        
        # 备份列表
        list_group = QGroupBox("可用备份")
        list_layout = QVBoxLayout(list_group)
        
        self._backup_list = QListWidget()
        list_layout.addWidget(self._backup_list)
        
        list_btn_layout = QHBoxLayout()
        restore_btn = QPushButton("恢复")
        restore_btn.clicked.connect(self._restore_backup)
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self._delete_backup)
        list_btn_layout.addWidget(restore_btn)
        list_btn_layout.addWidget(delete_btn)
        list_layout.addLayout(list_btn_layout)
        
        layout.addWidget(list_group)
        
        self._load_backups()
        
        return widget
    
    def _load_items(self):
        """加载可导出项目"""
        self._export_items.clear()
        
        items = self.config_manager.get_exportable_items()
        
        for item in items:
            list_item = QListWidgetItem(f"☑️ {item.name}  -  {item.description}")
            list_item.setData(Qt.ItemDataRole.UserRole, item.name)
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self._export_items.addItem(list_item)
    
    def _select_all_items(self, select: bool):
        """全选/取消"""
        for i in range(self._export_items.count()):
            item = self._export_items.item(i)
            item.setCheckState(Qt.CheckState.Checked if select else Qt.CheckState.Unchecked)
    
    def _get_selected_items(self) -> list:
        """获取选中的项目"""
        items = []
        for i in range(self._export_items.count()):
            item = self._export_items.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                items.append(item.data(Qt.ItemDataRole.UserRole))
        return items
    
    def _browse_import_file(self):
        """浏览导入文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择导入文件",
            str(Path.home() if 'Path' in dir() else ""),
            "配置文件 (*.zip *.json *.md);;所有文件 (*)"
        )
        
        if path:
            self._import_file_path.setText(path)
    
    def _export_all(self):
        """导出全部"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存备份",
            "",
            "ZIP压缩包 (*.zip)"
        )
        
        if not path:
            return
        
        if not path.endswith('.zip'):
            path += '.zip'
        
        self._set_progress_visible(True, "正在导出...")
        
        self._worker = ExportWorker(
            self.config_manager,
            [],  # 空列表表示全部
            path,
            self._include_sessions.isChecked()
        )
        self._worker.progress.connect(lambda msg, prog: self._update_progress(msg, prog))
        self._worker.finished.connect(self._on_export_finished)
        self._worker.start()
    
    def _export_selected(self):
        """导出选中"""
        items = self._get_selected_items()
        
        if not items:
            QMessageBox.warning(self, "提示", "请选择要导出的项目")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "保存备份",
            "",
            "ZIP压缩包 (*.zip)"
        )
        
        if not path:
            return
        
        if not path.endswith('.zip'):
            path += '.zip'
        
        self._set_progress_visible(True, "正在导出...")
        
        self._worker = ExportWorker(
            self.config_manager,
            items,
            path,
            False
        )
        self._worker.finished.connect(self._on_export_finished)
        self._worker.start()
    
    def _import_from_source(self, source_type: str):
        """从指定源导入"""
        if source_type == "file":
            source = self._import_file_path.text()
        elif source_type == "url":
            source = self._import_url.text()
        else:
            return
        
        if not source:
            QMessageBox.warning(self, "提示", "请指定导入来源")
            return
        
        self._set_progress_visible(True, "正在导入...")
        
        self._worker = ImportWorker(
            self.config_manager,
            source,
            source_type
        )
        self._worker.progress.connect(lambda msg, prog: self._update_progress(msg, prog))
        self._worker.finished.connect(self._on_import_finished)
        self._worker.start()
    
    def _create_backup(self):
        """创建备份"""
        name = self._backup_name.text().strip() or None
        
        self._set_progress_visible(True, "正在创建备份...")
        
        def do_backup():
            result = self.config_manager.create_backup(name)
            self._on_export_finished(result)
            if result.success:
                self._load_backups()
        
        from PyQt6.QtCore import QThread
        thread = QThread()
        thread.run = do_backup
        thread.start()
    
    def _load_backups(self):
        """加载备份列表"""
        self._backup_list.clear()
        
        backups = self.config_manager.list_backups()
        
        for backup in backups:
            item = QListWidgetItem(
                f"💾 {backup['name']}  -  {backup['created_at'][:10]}  ({backup['size']/1024:.1f}KB)"
            )
            item.setData(Qt.ItemDataRole.UserRole, backup['name'])
            self._backup_list.addItem(item)
    
    def _restore_backup(self):
        """恢复备份"""
        current = self._backup_list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请选择要恢复的备份")
            return
        
        name = current.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "确认恢复",
            "恢复备份将覆盖当前配置。确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.config_manager.restore_backup(name)
            
            if result.success:
                QMessageBox.information(self, "成功", f"已恢复 {result.items_imported} 个项目")
            else:
                QMessageBox.warning(self, "失败", "\n".join(result.errors))
    
    def _delete_backup(self):
        """删除备份"""
        current = self._backup_list.currentItem()
        if not current:
            return
        
        name = current.data(Qt.ItemDataRole.UserRole)
        
        # TODO: 实现删除备份
        QMessageBox.information(self, "提示", "删除功能待实现")
    
    def _set_progress_visible(self, visible: bool, msg: str = ""):
        """设置进度条可见性"""
        self._progress_bar.setVisible(visible)
        self._progress_bar.setValue(0)
        self._status_label.setText(msg)
    
    def _update_progress(self, msg: str, progress: float):
        """更新进度"""
        self._status_label.setText(msg)
        if progress >= 0:
            self._progress_bar.setValue(int(progress * 100))
    
    def _on_export_finished(self, result: ExportResult):
        """导出完成"""
        self._progress_bar.setVisible(False)
        
        if result.success:
            self._status_label.setText(f"✅ 导出成功: {result.file_path}")
            QMessageBox.information(
                self, "导出成功",
                f"已导出 {result.items_count} 个项目\n文件: {result.file_path}"
            )
        else:
            self._status_label.setText(f"❌ 导出失败: {result.error}")
            QMessageBox.warning(self, "导出失败", result.error)
    
    def _on_import_finished(self, result: ImportResult):
        """导入完成"""
        self._progress_bar.setVisible(False)
        
        if result.success:
            self._status_label.setText(f"✅ 导入成功: {result.items_imported} 个项目")
            QMessageBox.information(
                self, "导入成功",
                f"已导入 {result.items_imported} 个项目\n"
                f"跳过 {result.items_skipped} 个"
            )
            
            from client.src.presentation.panels.toast_notification import toast_success
            toast_success(f"导入成功: {result.items_imported} 个项目")
        else:
            self._status_label.setText(f"❌ 导入失败")
            QMessageBox.warning(self, "导入失败", "\n".join(result.errors))
