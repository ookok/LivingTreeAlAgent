#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目浏览器 - 文件树组件
============================

功能：
1. 显示项目目录结构（树形视图）
2. 点击文件在编辑器中打开
3. 右键菜单（新建/删除/重命名）
4. 自动刷新
5. 文件图标（根据类型）

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox,
    QInputDialog, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QDir
from PyQt6.QtGui import QIcon, QFont

from business.nanochat_config import config


# ── 文件类型图标映射 ──────────────────────────────────────────────

FILE_ICONS = {
    '.py': '🐍',
    '.js': '📜',
    '.ts': '📘',
    '.html': '🌐',
    '.css': '🎨',
    '.json': '📋',
    '.md': '📝',
    '.txt': '📄',
    '.yaml': '⚙️',
    '.yml': '⚙️',
    '.toml': '⚙️',
    '.ini': '⚙️',
    '.cfg': '⚙️',
    '.sh': '🔧',
    '.bat': '🔧',
    '.ps1': '🔧',
    '.sql': '🗃️',
    '.db': '🗃️',
    '.sqlite': '🗃️',
    '.jpg': '🖼️',
    '.png': '🖼️',
    '.gif': '🖼️',
    '.svg': '🖼️',
    '.pdf': '📕',
    '.docx': '📘',
    '.xlsx': '📗',
    '.pptx': '📙',
}

FOLDER_ICON = '📁'
FOLDER_OPEN_ICON = '📂'
FILE_ICON = '📄'


# ── 项目浏览器 ─────────────────────────────────────────────────

class ProjectBrowser(QTreeWidget):
    """
    项目浏览器组件
    
    功能：
    - 显示项目文件树
    - 双击打开文件
    - 右键菜单操作
    - 自动刷新
    
    Signals:
        file_double_clicked(str): 文件被双击
        file_right_clicked(str): 文件被右键点击
        folder_double_clicked(str): 文件夹被双击
    """
    
    file_double_clicked = pyqtSignal(str)  # 文件路径
    file_right_clicked = pyqtSignal(str, object)  # 文件路径, QPoint
    folder_double_clicked = pyqtSignal(str)  # 文件夹路径
    file_created = pyqtSignal(str)  # 新文件路径
    file_deleted = pyqtSignal(str)  # 删除的文件路径
    file_renamed = pyqtSignal(str, str)  # 旧路径, 新路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_root: Optional[str] = None
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        # 设置列
        self.setHeaderLabels(['项目文件'])
        
        # 设置样式
        self.setStyleSheet("""
            QTreeWidget {
                background: #1E1E1E;
                color: #D4D4D4;
                border: none;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background: #094771;
                color: #FFFFFF;
            }
            QTreeWidget::item:hover {
                background: #2A2D2E;
            }
            QTreeWidget::branch {
                background: #1E1E1E;
            }
        """)
        
        # 设置列宽
        self.setColumnWidth(0, 300)
        
        # 允许右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    
    def _connect_signals(self):
        """连接信号"""
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.customContextMenuRequested.connect(self._on_context_menu)
    
    def set_project_root(self, root_path: str):
        """
        设置项目根目录
        
        Args:
            root_path: 项目根目录路径
        """
        self.project_root = root_path
        self.refresh()
    
    def refresh(self):
        """刷新文件树"""
        if not self.project_root or not os.path.exists(self.project_root):
            return
        
        # 清空现有内容
        self.clear()
        
        # 添加根节点
        root_info = QDir(self.project_root)
        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"📂 {root_info.dirName()}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, self.project_root)
        root_item.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
        )
        
        # 递归添加子项
        self._add_directory_items(root_item, self.project_root)
        
        # 展开根节点
        root_item.setExpanded(True)
    
    def _add_directory_items(self, parent_item: QTreeWidgetItem, path: str):
        """
        递归添加目录项
        
        Args:
            parent_item: 父节点
            path: 目录路径
        """
        try:
            # 获取目录内容
            entries = os.listdir(path)
            
            # 排序：文件夹在前，文件在后
            dirs = []
            files = []
            for entry in entries:
                entry_path = os.path.join(path, entry)
                
                # 跳过隐藏文件和目录
                if entry.startswith('.') and entry not in ['.gitignore', '.env.example']:
                    continue
                
                # 跳过常见的无关目录
                if os.path.isdir(entry_path) and entry in [
                    '__pycache__', '.git', '.pytest_cache', 'node_modules',
                    '.workbuddy', '.codebuddy', 'dist', 'build', '__pycache__'
                ]:
                    continue
                
                if os.path.isdir(entry_path):
                    dirs.append(entry)
                else:
                    files.append(entry)
            
            # 添加文件夹
            for dir_name in sorted(dirs):
                dir_path = os.path.join(path, dir_name)
                dir_item = QTreeWidgetItem(parent_item)
                dir_item.setText(0, f"{FOLDER_ICON} {dir_name}")
                dir_item.setData(0, Qt.ItemDataRole.UserRole, dir_path)
                dir_item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                )
                
                # 递归添加子项（延迟加载）
                # 这里只添加一层，避免加载过慢
            
            # 添加文件
            for file_name in sorted(files):
                file_path = os.path.join(path, file_name)
                file_item = QTreeWidgetItem(parent_item)
                
                # 获取文件图标
                _, ext = os.path.splitext(file_name)
                icon = FILE_ICONS.get(ext.lower(), FILE_ICON)
                
                file_item.setText(0, f"{icon} {file_name}")
                file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        
        except PermissionError:
            pass  # 跳过无权限的目录
        except Exception as e:
            print(f"读取目录失败: {path}, 错误: {e}")
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        处理项目双击
        
        Args:
            item: 被点击的项
            column: 被点击的列
        """
        path = item.data(0, Qt.ItemDataRole.UserRole)
        
        if not path:
            return
        
        if os.path.isfile(path):
            # 文件：发送打开信号
            self.file_double_clicked.emit(path)
        elif os.path.isdir(path):
            # 文件夹：展开/折叠
            if item.isExpanded():
                item.setExpanded(False)
            else:
                # 加载子项（如果还没加载）
                if item.childCount() == 0:
                    self._add_directory_items(item, path)
                item.setExpanded(True)
            self.folder_double_clicked.emit(path)
    
    def _on_context_menu(self, position):
        """
        处理右键菜单
        
        Args:
            position: 菜单位置
        """
        item = self.itemAt(position)
        
        menu = QMenu(self)
        
        if item:
            # 有选中项
            path = item.data(0, Qt.ItemDataRole.UserRole)
            
            if os.path.isfile(path):
                # 文件菜单
                open_action = menu.addAction("📂 打开")
                menu.addSeparator()
                rename_action = menu.addAction("✏️ 重命名")
                delete_action = menu.addAction("🗑️ 删除")
                
                action = menu.exec(self.mapToGlobal(position))
                
                if action == open_action:
                    self.file_double_clicked.emit(path)
                elif action == rename_action:
                    self._rename_file(path)
                elif action == delete_action:
                    self._delete_file(path)
            else:
                # 文件夹菜单
                new_file_action = menu.addAction("📄 新建文件")
                new_folder_action = menu.addAction("📁 新建文件夹")
                menu.addSeparator()
                rename_action = menu.addAction("✏️ 重命名")
                delete_action = menu.addAction("🗑️ 删除")
                
                action = menu.exec(self.mapToGlobal(position))
                
                if action == new_file_action:
                    self._create_new_file(path)
                elif action == new_folder_action:
                    self._create_new_folder(path)
                elif action == rename_action:
                    self._rename_file(path)
                elif action == delete_action:
                    self._delete_folder(path)
        else:
            # 空白区域菜单
            new_file_action = menu.addAction("📄 新建文件")
            new_folder_action = menu.addAction("📁 新建文件夹")
            menu.addSeparator()
            refresh_action = menu.addAction("🔄 刷新")
            
            action = menu.exec(self.mapToGlobal(position))
            
            if action == new_file_action and self.project_root:
                self._create_new_file(self.project_root)
            elif action == new_folder_action and self.project_root:
                self._create_new_folder(self.project_root)
            elif action == refresh_action:
                self.refresh()
    
    def _create_new_file(self, parent_dir: str):
        """
        创建新文件
        
        Args:
            parent_dir: 父目录路径
        """
        file_name, ok = QInputDialog.getText(
            self, "新建文件", "文件名：", text="new_file.py"
        )
        
        if ok and file_name:
            file_path = os.path.join(parent_dir, file_name)
            
            try:
                # 创建空文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
                
                # 刷新
                self.refresh()
                
                # 发送信号
                self.file_created.emit(file_path)
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"创建文件失败：{e}")
    
    def _create_new_folder(self, parent_dir: str):
        """
        创建新文件夹
        
        Args:
            parent_dir: 父目录路径
        """
        folder_name, ok = QInputDialog.getText(
            self, "新建文件夹", "文件夹名：", text="new_folder"
        )
        
        if ok and folder_name:
            folder_path = os.path.join(parent_dir, folder_name)
            
            try:
                os.makedirs(folder_path, exist_ok=True)
                
                # 刷新
                self.refresh()
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"创建文件夹失败：{e}")
    
    def _rename_file(self, path: str):
        """
        重命名文件/文件夹
        
        Args:
            path: 原路径
        """
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(
            self, "重命名", "新名称：", text=old_name
        )
        
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name)
            
            try:
                os.rename(path, new_path)
                
                # 刷新
                self.refresh()
                
                # 发送信号
                self.file_renamed.emit(path, new_path)
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"重命名失败：{e}")
    
    def _delete_file(self, file_path: str):
        """
        删除文件
        
        Args:
            file_path: 文件路径
        """
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文件 '{os.path.basename(file_path)}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(file_path)
                
                # 刷新
                self.refresh()
                
                # 发送信号
                self.file_deleted.emit(file_path)
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除文件失败：{e}")
    
    def _delete_folder(self, folder_path: str):
        """
        删除文件夹
        
        Args:
            folder_path: 文件夹路径
        """
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文件夹 '{os.path.basename(folder_path)}' 及其所有内容吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import shutil
                shutil.rmtree(folder_path)
                
                # 刷新
                self.refresh()
                
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除文件夹失败：{e}")
    
    def get_selected_file_path(self) -> Optional[str]:
        """
        获取当前选中的文件路径
        
        Returns:
            Optional[str]: 文件路径，如果没有选中则返回 None
        """
        items = self.selectedItems()
        if items:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                return path
        return None
    
    def get_selected_folder_path(self) -> Optional[str]:
        """
        获取当前选中的文件夹路径
        
        Returns:
            Optional[str]: 文件夹路径，如果没有选中则返回 None
        """
        items = self.selectedItems()
        if items:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isdir(path):
                return path
        return None


# ── 测试 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("项目浏览器测试")
    window.setGeometry(100, 100, 400, 600)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    
    browser = ProjectBrowser()
    browser.set_project_root(os.getcwd())  # 当前目录
    
    browser.file_double_clicked.connect(lambda p: print(f"打开文件: {p}"))
    browser.file_created.connect(lambda p: print(f"创建文件: {p}"))
    browser.file_deleted.connect(lambda p: print(f"删除文件: {p}"))
    
    layout.addWidget(browser)
    
    window.show()
    sys.exit(app.exec())
