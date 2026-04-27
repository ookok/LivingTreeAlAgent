"""
插件管理面板 - 对接真实 PluginManager
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QLineEdit,
    QMessageBox, QSplitter, QTextEdit,
)
from PyQt6.QtGui import QFont

from client.src.business.plugin_manager import PluginManager, PluginStatus


# ── 插件管理面板 ─────────────────────────────────────────────────────

class PluginManagerPanel(QWidget):
    """插件管理面板 - 对接真实 PluginManager"""

    plugin_installed = pyqtSignal(str)
    plugin_uninstalled = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = None
        self._setup_ui()
        self._init_manager()

    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🔌 插件管理")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 描述
        desc = QLabel("插件管理系统 - 安装、卸载、配置插件")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：插件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入插件名称...")
        self.search_edit.textChanged.connect(self._filter_plugins)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        left_layout.addLayout(search_layout)

        # 插件列表
        self.plugin_list = QListWidget()
        self.plugin_list.itemClicked.connect(self._on_plugin_selected)
        left_layout.addWidget(self.plugin_list)

        # 按钮
        btn_layout = QHBoxLayout()

        self.install_btn = QPushButton("安装插件")
        self.install_btn.clicked.connect(self._install_plugin)
        btn_layout.addWidget(self.install_btn)

        self.uninstall_btn = QPushButton("卸载插件")
        self.uninstall_btn.clicked.connect(self._uninstall_plugin)
        self.uninstall_btn.setEnabled(False)
        btn_layout.addWidget(self.uninstall_btn)

        btn_layout.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._load_plugins)
        btn_layout.addWidget(self.refresh_btn)

        left_layout.addLayout(btn_layout)

        splitter.addWidget(left_widget)

        # 右侧：插件详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        detail_group = QGroupBox("插件详情")
        detail_layout = QFormLayout(detail_group)

        self.name_label = QLabel("-")
        detail_layout.addRow("名称:", self.name_label)

        self.version_label = QLabel("-")
        detail_layout.addRow("版本:", self.version_label)

        self.author_label = QLabel("-")
        detail_layout.addRow("作者:", self.author_label)

        self.status_label = QLabel("-")
        detail_layout.addRow("状态:", self.status_label)

        right_layout.addWidget(detail_group)

        # 描述
        desc_group = QGroupBox("描述")
        desc_layout = QVBoxLayout(desc_group)

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        desc_layout.addWidget(self.desc_text)

        right_layout.addWidget(desc_group)

        # 配置
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout(config_group)

        self.config_text = QTextEdit()
        self.config_text.setMaximumHeight(150)
        config_layout.addWidget(self.config_text)

        right_layout.addWidget(config_group)

        splitter.addWidget(right_widget)

        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _init_manager(self):
        """初始化 PluginManager"""
        try:
            plugin_dir = str(Path(__file__).parent.parent.parent.parent / "plugins")

            self._manager = PluginManager(plugin_dir=plugin_dir)

            # 加载已有插件（如果有的话）
            self._load_plugins()

        except Exception as e:
            QMessageBox.warning(self, "警告", f"PluginManager 初始化失败: {e}")
            self._manager = None

    def _load_plugins(self):
        """加载插件列表（从 PluginManager）"""
        self.plugin_list.clear()

        if not self._manager:
            return

        try:
            plugins = self._manager.list_plugins()

            for plugin_info in plugins:
                item = QListWidgetItem(plugin_info.name)
                # 存储插件信息
                item.setData(1000, {
                    "id": plugin_info.id,
                    "name": plugin_info.name,
                    "version": plugin_info.version,
                    "author": plugin_info.author,
                    "status": plugin_info.status.value,
                    "description": plugin_info.description,
                    "config": "{}",
                })
                self.plugin_list.addItem(item)

        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载插件列表失败: {e}")

    def _filter_plugins(self, text: str):
        """过滤插件列表"""
        for i in range(self.plugin_list.count()):
            item = self.plugin_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_plugin_selected(self, item):
        """插件选中"""
        plugin_data = item.data(1000)

        self.name_label.setText(plugin_data["name"])
        self.version_label.setText(plugin_data["version"])
        self.author_label.setText(plugin_data["author"])
        self.status_label.setText(plugin_data["status"])
        self.desc_text.setText(plugin_data["desc"])
        self.config_text.setText(plugin_data["config"])

        # 更新按钮状态
        self.uninstall_btn.setEnabled(plugin_data["status"] == "loaded")

    def _install_plugin(self):
        """安装插件"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个插件")
            return

        plugin_data = current_item.data(1000)

        if not self._manager:
            QMessageBox.warning(self, "警告", "PluginManager 未初始化")
            return

        try:
            # 调用真实的 PluginManager API
            success = self._manager.load_plugin(plugin_data["id"])

            if success:
                # 更新状态
                plugin_data["status"] = "loaded"
                current_item.setData(1000, plugin_data)

                self.status_label.setText("已安装")
                self.uninstall_btn.setEnabled(True)

                self.plugin_installed.emit(plugin_data["name"])
                QMessageBox.information(self, "成功", f"插件 {plugin_data['name']} 安装成功")
            else:
                QMessageBox.warning(self, "警告", f"插件 {plugin_data['name']} 安装失败")

        except Exception as e:
            QMessageBox.warning(self, "警告", f"安装失败: {e}")

    def _uninstall_plugin(self):
        """卸载插件"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个插件")
            return

        plugin_data = current_item.data(1000)

        if not self._manager:
            QMessageBox.warning(self, "警告", "PluginManager 未初始化")
            return

        try:
            # 调用真实的 PluginManager API
            success = self._manager.unload_plugin(plugin_data["id"])

            if success:
                # 更新状态
                plugin_data["status"] = "unloaded"
                current_item.setData(1000, plugin_data)

                self.status_label.setText("未安装")
                self.uninstall_btn.setEnabled(False)

                self.plugin_uninstalled.emit(plugin_data["name"])
                QMessageBox.information(self, "成功", f"插件 {plugin_data['name']} 卸载成功")
            else:
                QMessageBox.warning(self, "警告", f"插件 {plugin_data['name']} 卸载失败")

        except Exception as e:
            QMessageBox.warning(self, "警告", f"卸载失败: {e}")
