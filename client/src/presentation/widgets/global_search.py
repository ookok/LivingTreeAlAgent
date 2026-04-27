#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局搜索/替换组件
==================

功能：
1. 在项目范围内搜索文本
2. 支持正则表达式
3. 支持大小写敏感/不敏感
4. 显示搜索结果（文件路径 + 行号 + 内容）
5. 一键替换
6. 搜索结果双击跳转

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor


# ── 搜索工作线程 ──────────────────────────────────────────────

class SearchWorker(QThread):
    """搜索工作线程"""
    
    result_found = pyqtSignal(str, int, str)  # 文件路径, 行号, 匹配内容
    search_finished = pyqtSignal(int)  # 总匹配数
    search_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_path: str = ""
        self.search_text: str = ""
        self.is_regex: bool = False
        self.case_sensitive: bool = False
        self.file_filter: str = "*.py"  # 默认搜索 Python 文件
        self.max_results: int = 1000
        self._stop_requested: bool = False
    
    def run(self):
        """执行搜索"""
        try:
            flags = re.IGNORECASE if not self.case_sensitive else 0
            
            if self.is_regex:
                pattern = re.compile(self.search_text, flags)
            else:
                pattern = re.compile(re.escape(self.search_text), flags)
            
            total_matches = 0
            
            # 遍历文件
            for root, dirs, files in os.walk(self.search_path):
                if self._stop_requested:
                    break
                
                # 跳过无关目录
                dirs[:] = [
                    d for d in dirs
                    if d not in [
                        '__pycache__', '.git', '.pytest_cache',
                        'node_modules', 'dist', 'build', '.workbuddy',
                        '.codebuddy', '.venv', 'venv', 'env'
                    ]
                ]
                
                for file in files:
                    if self._stop_requested:
                        break
                    
                    # 检查文件类型
                    if not self._match_file_filter(file):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_num, line in enumerate(f, 1):
                                if self._stop_requested:
                                    break
                                
                                if pattern.search(line):
                                    total_matches += 1
                                    
                                    # 发送结果
                                    self.result_found.emit(
                                        file_path, line_num, line.rstrip()
                                    )
                                    
                                    if total_matches >= self.max_results:
                                        self.search_finished.emit(total_matches)
                                        return
                    
                    except Exception:
                        continue  # 跳过无法读取的文件
            
            self.search_finished.emit(total_matches)
        
        except Exception as e:
            self.search_error.emit(str(e))
    
    def _match_file_filter(self, file_name: str) -> bool:
        """
        检查文件是否匹配过滤器
        
        Args:
            file_name: 文件名
            
        Returns:
            bool: 是否匹配
        """
        if self.file_filter == "*":
            return True
        
        # 简单通配符匹配
        import fnmatch
        return fnmatch.fnmatch(file_name, self.file_filter)
    
    def stop(self):
        """停止搜索"""
        self._stop_requested = True


class ReplaceWorker(QThread):
    """替换工作线程"""
    
    replace_finished = pyqtSignal(int, int)  # 替换文件数, 替换总数
    replace_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_path: str = ""
        self.search_text: str = ""
        self.replace_text: str = ""
        self.is_regex: bool = False
        self.case_sensitive: bool = False
        self.file_filter: str = "*.py"
        self._stop_requested: bool = False
    
    def run(self):
        """执行替换"""
        try:
            flags = re.IGNORECASE if not self.case_sensitive else 0
            
            if self.is_regex:
                pattern = re.compile(self.search_text, flags)
            else:
                pattern = re.compile(re.escape(self.search_text), flags)
            
            files_modified = 0
            total_replacements = 0
            
            # 遍历文件
            for root, dirs, files in os.walk(self.search_path):
                if self._stop_requested:
                    break
                
                # 跳过无关目录
                dirs[:] = [
                    d for d in dirs
                    if d not in [
                        '__pycache__', '.git', '.pytest_cache',
                        'node_modules', 'dist', 'build', '.workbuddy',
                        '.codebuddy', '.venv', 'venv', 'env'
                    ]
                ]
                
                for file in files:
                    if self._stop_requested:
                        break
                    
                    # 检查文件类型
                    if not self._match_file_filter(file):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    try:
                        # 读取文件
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # 执行替换
                        new_content, replacements = pattern.subn(
                            self.replace_text, content
                        )
                        
                        if replacements > 0:
                            # 写回文件
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            
                            files_modified += 1
                            total_replacements += replacements
                    
                    except Exception:
                        continue  # 跳过无法处理的文件
            
            self.replace_finished.emit(files_modified, total_replacements)
        
        except Exception as e:
            self.replace_error.emit(str(e))
    
    def _match_file_filter(self, file_name: str) -> bool:
        """检查文件是否匹配过滤器"""
        if self.file_filter == "*":
            return True
        
        import fnmatch
        return fnmatch.fnmatch(file_name, self.file_filter)
    
    def stop(self):
        """停止替换"""
        self._stop_requested = True


# ── 全局搜索面板 ──────────────────────────────────────────────

class GlobalSearchPanel(QWidget):
    """
    全局搜索/替换面板
    
    功能：
    - 搜索输入框
    - 替换输入框
    - 搜索选项（正则、大小写）
    - 文件过滤器
    - 搜索结果树
    - 操作按钮
    
    Signals:
        file_double_clicked(str, int): 文件被双击（路径, 行号）
    """
    
    file_double_clicked = pyqtSignal(str, int)  # 文件路径, 行号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_path: str = ""
        self.search_worker: Optional[SearchWorker] = None
        self.replace_worker: Optional[ReplaceWorker] = None
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 搜索路径
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        
        path_label = QLabel("搜索路径:")
        path_label.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        path_layout.addWidget(path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择搜索路径...")
        self.path_edit.setStyleSheet("""
            QLineEdit {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        path_layout.addWidget(self.path_edit)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setFixedSize(60, 28)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4A4A4E; }
        """)
        path_layout.addWidget(self.browse_btn)
        
        layout.addLayout(path_layout)
        
        # 搜索输入
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入搜索内容...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
        search_layout.addWidget(self.search_edit)
        
        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedSize(80, 32)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # 替换输入
        replace_layout = QHBoxLayout()
        replace_layout.setContentsMargins(0, 0, 0, 0)
        
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("替换为（可选）...")
        self.replace_edit.setStyleSheet("""
            QLineEdit {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
        replace_layout.addWidget(self.replace_edit)
        
        self.replace_btn = QPushButton("🔄 替换")
        self.replace_btn.setFixedSize(80, 32)
        self.replace_btn.setStyleSheet("""
            QPushButton {
                background: #4B0082;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #5A0099; }
            QPushButton:disabled { background: #555555; }
        """)
        replace_layout.addWidget(self.replace_btn)
        
        layout.addLayout(replace_layout)
        
        # 搜索选项
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        
        self.regex_check = QCheckBox("正则表达式")
        self.regex_check.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        options_layout.addWidget(self.regex_check)
        
        self.case_check = QCheckBox("大小写敏感")
        self.case_check.setStyleSheet("color: #D4D4D4; font-size: 12px;")
        options_layout.addWidget(self.case_check)
        
        options_layout.addStretch()
        
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("文件过滤 (*.py)")
        self.filter_edit.setText("*.py")
        self.filter_edit.setFixedWidth(120)
        self.filter_edit.setStyleSheet("""
            QLineEdit {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        options_layout.addWidget(self.filter_edit)
        
        layout.addLayout(options_layout)
        
        # 搜索结果
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["文件", "行号", "内容"])
        self.result_tree.setColumnWidth(0, 300)
        self.result_tree.setColumnWidth(1, 60)
        self.result_tree.setStyleSheet("""
            QTreeWidget {
                background: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E42;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 2px 4px;
            }
            QTreeWidget::item:selected {
                background: #094771;
                color: #FFFFFF;
            }
            QTreeWidget::item:hover {
                background: #2A2D2E;
            }
        """)
        layout.addWidget(self.result_tree, 1)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #D4D4D4; font-size: 11px; padding: 4px 0;")
        layout.addWidget(self.status_label)
    
    def _connect_signals(self):
        """连接信号"""
        self.search_btn.clicked.connect(self._start_search)
        self.replace_btn.clicked.connect(self._start_replace)
        self.browse_btn.clicked.connect(self._browse_path)
        self.search_edit.returnPressed.connect(self._start_search)
        self.result_tree.itemDoubleClicked.connect(self._on_result_double_clicked)
    
    def set_search_path(self, path: str):
        """
        设置搜索路径
        
        Args:
            path: 搜索路径
        """
        self.search_path = path
        self.path_edit.setText(path)
    
    def _browse_path(self):
        """浏览路径"""
        path = QFileDialog.getExistingDirectory(
            self, "选择搜索路径", self.search_path or os.getcwd()
        )
        
        if path:
            self.set_search_path(path)
    
    def _start_search(self):
        """开始搜索"""
        search_text = self.search_edit.text().strip()
        
        if not search_text:
            QMessageBox.warning(self, "警告", "请输入搜索内容")
            return
        
        if not self.search_path or not os.path.exists(self.search_path):
            QMessageBox.warning(self, "警告", "请选择有效的搜索路径")
            return
        
        # 清空结果
        self.result_tree.clear()
        self.status_label.setText("搜索中...")
        
        # 禁用按钮
        self.search_btn.setEnabled(False)
        self.replace_btn.setEnabled(False)
        
        # 启动搜索线程
        self.search_worker = SearchWorker()
        self.search_worker.search_path = self.search_path
        self.search_worker.search_text = search_text
        self.search_worker.is_regex = self.regex_check.isChecked()
        self.search_worker.case_sensitive = self.case_check.isChecked()
        self.search_worker.file_filter = self.filter_edit.text() or "*"
        
        self.search_worker.result_found.connect(self._on_result_found)
        self.search_worker.search_finished.connect(self._on_search_finished)
        self.search_worker.search_error.connect(self._on_search_error)
        
        self.search_worker.start()
    
    def _start_replace(self):
        """开始替换"""
        search_text = self.search_edit.text().strip()
        replace_text = self.replace_edit.text()
        
        if not search_text:
            QMessageBox.warning(self, "警告", "请输入搜索内容")
            return
        
        if not self.search_path or not os.path.exists(self.search_path):
            QMessageBox.warning(self, "警告", "请选择有效的搜索路径")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认替换",
            f"确定要替换所有匹配项吗？\n\n搜索: {search_text}\n替换: {replace_text}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 禁用按钮
        self.search_btn.setEnabled(False)
        self.replace_btn.setEnabled(False)
        self.status_label.setText("替换中...")
        
        # 启动替换线程
        self.replace_worker = ReplaceWorker()
        self.replace_worker.search_path = self.search_path
        self.replace_worker.search_text = search_text
        self.replace_worker.replace_text = replace_text
        self.replace_worker.is_regex = self.regex_check.isChecked()
        self.replace_worker.case_sensitive = self.case_check.isChecked()
        self.replace_worker.file_filter = self.filter_edit.text() or "*"
        
        self.replace_worker.replace_finished.connect(self._on_replace_finished)
        self.replace_worker.replace_error.connect(self._on_replace_error)
        
        self.replace_worker.start()
    
    def _on_result_found(self, file_path: str, line_num: int, content: str):
        """
        处理搜索结果
        
        Args:
            file_path: 文件路径
            line_num: 行号
            content: 匹配内容
        """
        # 创建文件节点（如果不存在）
        file_rel_path = os.path.relpath(file_path, self.search_path)
        
        # 查找或创建文件节点
        file_item = None
        for i in range(self.result_tree.topLevelItemCount()):
            item = self.result_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == file_path:
                file_item = item
                break
        
        if not file_item:
            file_item = QTreeWidgetItem(self.result_tree)
            file_item.setText(0, f"📄 {file_rel_path}")
            file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        
        # 添加匹配行
        line_item = QTreeWidgetItem(file_item)
        line_item.setText(0, f"  第 {line_num} 行")
        line_item.setText(1, str(line_num))
        line_item.setText(2, content.strip())
        line_item.setData(0, Qt.ItemDataRole.UserRole, (file_path, line_num))
    
    def _on_search_finished(self, total_matches: int):
        """
        搜索完成
        
        Args:
            total_matches: 总匹配数
        """
        self.status_label.setText(f"搜索完成，找到 {total_matches} 个匹配")
        self.search_btn.setEnabled(True)
        self.replace_btn.setEnabled(True)
        self.search_worker = None
    
    def _on_search_error(self, error_msg: str):
        """
        搜索错误
        
        Args:
            error_msg: 错误信息
        """
        self.status_label.setText(f"搜索失败: {error_msg}")
        self.search_btn.setEnabled(True)
        self.replace_btn.setEnabled(True)
        self.search_worker = None
    
    def _on_replace_finished(self, files_modified: int, total_replacements: int):
        """
        替换完成
        
        Args:
            files_modified: 修改的文件数
            total_replacements: 总替换数
        """
        self.status_label.setText(
            f"替换完成，修改 {files_modified} 个文件，共 {total_replacements} 处"
        )
        self.search_btn.setEnabled(True)
        self.replace_btn.setEnabled(True)
        self.replace_worker = None
        
        # 刷新搜索结果
        self._start_search()
    
    def _on_replace_error(self, error_msg: str):
        """
        替换错误
        
        Args:
            error_msg: 错误信息
        """
        self.status_label.setText(f"替换失败: {error_msg}")
        self.search_btn.setEnabled(True)
        self.replace_btn.setEnabled(True)
        self.replace_worker = None
    
    def _on_result_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        处理结果双击
        
        Args:
            item: 被点击的项
            column: 被点击的列
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if isinstance(data, tuple) and len(data) == 2:
            # 匹配行
            file_path, line_num = data
            self.file_double_clicked.emit(file_path, line_num)
        elif isinstance(data, str) and os.path.isfile(data):
            # 文件节点
            self.file_double_clicked.emit(data, 1)


# ── 测试 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("全局搜索测试")
    window.setGeometry(100, 100, 800, 600)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    
    search_panel = GlobalSearchPanel()
    search_panel.set_search_path(os.getcwd())
    search_panel.file_double_clicked.connect(
        lambda p, l: print(f"打开: {p}, 行: {l}")
    )
    
    layout.addWidget(search_panel)
    
    window.show()
    sys.exit(app.exec())
