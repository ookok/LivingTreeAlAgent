"""
环保模型商店 UI面板 (Model Store Panel)
=======================================

提供模型商店的PyQt6图形界面

功能：
1. 模型浏览与搜索
2. 一键安装/卸载
3. 运行状态监控
4. P2P网络状态

Author: Hermes Desktop AI Assistant
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# PyQt6相关
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QLabel, QComboBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QProgressBar, QGroupBox,
    QListWidget, QListWidgetItem, QTextEdit,
    QSpinBox, QCheckBox, QFrame, QScrollArea, QProgressDialog,
    QMessageBox, QInputDialog, QDialog
)
from .presentation.panels.components import QCardWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette

logger = logging.getLogger(__name__)


class ModelCard(QFrame):
    """模型卡片组件"""

    # 信号：安装、卸载、运行
    install_clicked = pyqtSignal(str)
    uninstall_clicked = pyqtSignal(str)
    run_clicked = pyqtSignal(str)

    def __init__(self, model_data: Dict, parent=None):
        super().__init__(parent)
        self.model_data = model_data
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # 标题行
        title_layout = QHBoxLayout()
        name_label = QLabel(self.model_data.get('name', 'Unknown'))
        name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_layout.addWidget(name_label)

        # 级别标签
        level = self.model_data.get('level', 'light')
        level_colors = {
            'light': '#4CAF50',   # 绿色
            'medium': '#FF9800', # 橙色
            'heavy': '#F44336',  # 红色
            'cloud': '#2196F3',   # 蓝色
        }
        level_label = QLabel(level.upper())
        level_label.setStyleSheet(f"""
            background-color: {level_colors.get(level, '#9E9E9E')};
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        title_layout.addWidget(level_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_layout)

        # 类别
        category_label = QLabel(f"类别: {self.model_data.get('category', 'other')}")
        category_label.setStyleSheet("color: #666;")
        layout.addWidget(category_label)

        # 描述
        desc = self.model_data.get('description', '')[:100]
        if len(self.model_data.get('description', '')) > 100:
            desc += '...'
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 资源需求
        resources = self.model_data.get('resources', {})
        if resources:
            res_text = f"资源: CPU {resources.get('cpu_cores', 1)}核"
            if resources.get('gpu'):
                res_text += " + GPU"
            res_text += f" / 内存 {resources.get('memory_mb', 1024)}MB"
            res_label = QLabel(res_text)
            res_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(res_label)

        # 费用信息
        cost = self.model_data.get('cost', {})
        if cost:
            cost_text = f"费用: {cost.get('free_tier', 'N/A')}"
            if cost.get('hourly_cost'):
                cost_text += f" (${cost.get('hourly_cost')}/小时)"
            cost_label = QLabel(cost_text)
            cost_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(cost_label)

        # 安装状态
        installed = self.model_data.get('installed', False)
        status_text = "✅ 已安装" if installed else "❌ 未安装"
        status_label = QLabel(status_text)
        status_label.setStyleSheet("font-weight: bold; color: #4CAF50;" if installed else "color: #F44336;")
        layout.addWidget(status_label)

        # 按钮行
        btn_layout = QHBoxLayout()

        if installed:
            run_btn = QPushButton("▶ 运行")
            run_btn.clicked.connect(lambda: self.run_clicked.emit(self.model_data['id']))
            btn_layout.addWidget(run_btn)

            uninstall_btn = QPushButton("🗑️ 卸载")
            uninstall_btn.clicked.connect(lambda: self.uninstall_clicked.emit(self.model_data['id']))
            uninstall_btn.setStyleSheet("background-color: #FF5722; color: white;")
            btn_layout.addWidget(uninstall_btn)
        else:
            install_btn = QPushButton("⬇️ 安装")
            install_btn.clicked.connect(lambda: self.install_clicked.emit(self.model_data['id']))
            install_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)


class ProgressDialog(QDialog):
    """进度对话框"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("准备中...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def update_progress(self, progress: float, message: str = ""):
        """更新进度"""
        self.progress_bar.setValue(int(progress))
        if message:
            self.status_label.setText(message)


class ModelStorePanel(QWidget):
    """
    模型商店面板

    包含：
    1. 模型浏览标签页
    2. 已安装标签页
    3. 监控标签页
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store_manager = None
        self._setup_ui()
        self._load_models()

        # 定时刷新
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(30000)  # 30秒刷新

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("🌱 环保模型商店")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_layout.addWidget(title)

        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666;")
        title_layout.addWidget(self.stats_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_layout)

        # 搜索和筛选栏
        filter_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索模型...")
        self.search_input.textChanged.connect(self._on_search)
        filter_layout.addWidget(self.search_input, stretch=2)

        self.category_filter = QComboBox()
        self.category_filter.addItem("全部类别", None)
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.category_filter)

        self.level_filter = QComboBox()
        self.level_filter.addItem("全部级别", None)
        self.level_filter.addItem("🌱 轻量级 (pip)", "light")
        self.level_filter.addItem("⚙️ 中型 (CLI)", "medium")
        self.level_filter.addItem("🏭 重型 (Docker)", "heavy")
        self.level_filter.addItem("☁️ 云端 (API)", "cloud")
        self.level_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.level_filter)

        self.show_installed_only = QCheckBox("只看已安装")
        self.show_installed_only.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.show_installed_only)

        layout.addLayout(filter_layout)

        # 标签页
        self.tabs = QTabWidget()

        # 模型浏览标签页
        self.browse_tab = self._create_browse_tab()
        self.tabs.addTab(self.browse_tab, "📦 模型浏览")

        # 已安装标签页
        self.installed_tab = self._create_installed_tab()
        self.tabs.addTab(self.installed_tab, "✅ 已安装")

        # 监控标签页
        self.monitor_tab = self._create_monitor_tab()
        self.tabs.addTab(self.monitor_tab, "📊 运行监控")

        # P2P标签页
        self.p2p_tab = self._create_p2p_tab()
        self.tabs.addTab(self.p2p_tab, "🌐 P2P网络")

        layout.addWidget(self.tabs)

    def _create_browse_tab(self) -> QWidget:
        """创建浏览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模型卡片网格区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.model_cards_container = QWidget()
        self.model_cards_layout = QGridLayout(self.model_cards_container)
        self.model_cards_layout.setSpacing(10)

        scroll.setWidget(self.model_cards_container)
        layout.addWidget(scroll)

        return widget

    def _create_installed_tab(self) -> QWidget:
        """创建已安装标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 表格
        self.installed_table = QTableWidget()
        self.installed_table.setColumnCount(6)
        self.installed_table.setHorizontalHeaderLabels([
            "模型ID", "名称", "版本", "类别", "运行时状态", "操作"
        ])
        layout.addWidget(self.installed_table)

        return widget

    def _create_monitor_tab(self) -> QWidget:
        """创建监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 运行状态表格
        self.runtime_table = QTableWidget()
        self.runtime_table.setColumnCount(7)
        self.runtime_table.setHorizontalHeaderLabels([
            "模型ID", "类型", "状态", "CPU%", "内存MB", "最后使用", "操作"
        ])
        layout.addWidget(self.runtime_table)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新状态")
        refresh_btn.clicked.connect(self._refresh_status)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return widget

    def _create_p2p_tab(self) -> QWidget:
        """创建P2P标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # P2P统计
        stats_group = QGroupBox("🌐 P2P 网络状态")
        stats_layout = QGridLayout(stats_group)

        self.p2p_nodes_label = QLabel("已知节点: 0")
        stats_layout.addWidget(self.p2p_nodes_label, 0, 0)

        self.p2p_local_label = QLabel("本地模型: 0")
        stats_layout.addWidget(self.p2p_local_label, 0, 1)

        self.p2p_downloading_label = QLabel("下载中: 0")
        stats_layout.addWidget(self.p2p_downloading_label, 0, 2)

        layout.addWidget(stats_group)

        # 节点列表
        nodes_group = QGroupBox("📡 已知节点")
        nodes_layout = QVBoxLayout(nodes_group)

        self.nodes_list = QListWidget()
        nodes_layout.addWidget(self.nodes_list)

        layout.addWidget(nodes_group)

        # 按钮
        btn_layout = QHBoxLayout()

        refresh_p2p_btn = QPushButton("🔍 刷新节点")
        refresh_p2p_btn.clicked.connect(self._refresh_p2p)
        btn_layout.addWidget(refresh_p2p_btn)

        layout.addLayout(btn_layout)

        return widget

    def _load_models(self):
        """加载模型数据"""
        try:
            from .business.model_store import get_store_manager
            from .business.config import load_config

            # 加载配置获取中继服务器
            cfg = load_config()
            store_config = {
                'enable_p2p': cfg.model_store.enable_p2p,
                'relay_servers': cfg.model_store.relay_servers,
                'enable_monitoring': cfg.model_store.enable_monitoring,
                'storage_dir': cfg.model_store.storage_dir,
            }

            self.store_manager = get_store_manager(config=store_config)

            # 加载类别筛选
            categories = self.store_manager.get_categories()
            self.category_filter.clear()
            self.category_filter.addItem("全部类别", None)
            for cat in categories:
                self.category_filter.addItem(cat.capitalize(), cat)

            # 刷新显示
            self._refresh_model_cards()
            self._update_stats()

        except Exception as e:
            logger.error(f"加载模型失败: {e}")

    def _refresh_model_cards(self):
        """刷新模型卡片"""
        if not self.store_manager:
            return

        # 获取筛选条件
        category = self.category_filter.currentData()
        level = self.level_filter.currentData()
        installed_only = self.show_installed_only.isChecked()
        search = self.search_input.text()

        # 获取模型列表
        if search:
            models = self.store_manager.search_models(search)
        else:
            models = self.store_manager.list_models(
                category=category,
                level=level,
                installed_only=installed_only
            )

        # 清空现有卡片
        while self.model_cards_layout.count():
            item = self.model_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加卡片（2列）
        for i, model in enumerate(models):
            row = i // 2
            col = i % 2

            card = ModelCard(model)
            card.install_clicked.connect(self._on_install)
            card.uninstall_clicked.connect(self._on_uninstall)
            card.run_clicked.connect(self._on_run)

            self.model_cards_layout.addWidget(card, row, col)

        # 更新已安装表格
        self._refresh_installed_table()

    def _refresh_installed_table(self):
        """刷新已安装表格"""
        if not self.store_manager:
            return

        installed = self.store_manager.list_models(installed_only=True)

        self.installed_table.setRowCount(len(installed))

        for row, model in enumerate(installed):
            self.installed_table.setItem(row, 0, QTableWidgetItem(model['id']))
            self.installed_table.setItem(row, 1, QTableWidgetItem(model['name']))
            self.installed_table.setItem(row, 2, QTableWidgetItem(model['version']))
            self.installed_table.setItem(row, 3, QTableWidgetItem(model['category']))

            # 运行时状态
            runtime = self.store_manager.get_runtime_status(model['id'])
            status = runtime.get('status', 'unknown') if runtime else '未运行'
            self.installed_table.setItem(row, 4, QTableWidgetItem(status))

            # 操作按钮
            run_btn = QPushButton("▶ 运行")
            run_btn.clicked.connect(lambda _, m=model['id']: self._on_run(m))
            self.installed_table.setCellWidget(row, 5, run_btn)

    def _refresh_status(self):
        """刷新运行状态"""
        if not self.store_manager:
            return

        runtimes = self.store_manager.runtime_manager.list_runtimes()

        self.runtime_table.setRowCount(len(runtimes))

        for row, runtime in enumerate(runtimes):
            self.runtime_table.setItem(row, 0, QTableWidgetItem(runtime.model_id))
            self.runtime_table.setItem(row, 1, QTableWidgetItem(runtime.runtime_type.value))
            self.runtime_table.setItem(row, 2, QTableWidgetItem(runtime.status.value))
            self.runtime_table.setItem(row, 3, QTableWidgetItem(f"{runtime.cpu_percent:.1f}"))
            self.runtime_table.setItem(row, 4, QTableWidgetItem(f"{runtime.memory_mb:.1f}"))
            last_use = runtime.last_use.strftime('%H:%M:%S') if runtime.last_use else 'N/A'
            self.runtime_table.setItem(row, 5, QTableWidgetItem(last_use))

            stop_btn = QPushButton("⏹ 停止")
            stop_btn.clicked.connect(lambda _, r=runtime: self._stop_runtime(r.model_id))
            self.runtime_table.setCellWidget(row, 6, stop_btn)

        self._refresh_p2p()

    def _refresh_p2p(self):
        """刷新P2P状态"""
        if not self.store_manager:
            return

        stats = self.store_manager.p2p_discovery.get_stats()

        self.p2p_nodes_label.setText(f"已知节点: {stats['known_nodes']}")
        self.p2p_local_label.setText(f"本地模型: {stats['local_models']}")
        self.p2p_downloading_label.setText(f"下载中: {stats['downloading']}")

        # 刷新节点列表
        self.nodes_list.clear()
        for node_id, node in self.store_manager.p2p_discovery.nodes.items():
            item_text = f"{node_id} - {len(node.available_models)} 个模型"
            if node.is_trusted:
                item_text += " [信任]"
            self.nodes_list.addItem(item_text)

    def _update_stats(self):
        """更新统计信息"""
        if not self.store_manager:
            return

        stats = self.store_manager.get_stats()
        self.stats_label.setText(
            f"总计: {stats['total_models']} | "
            f"已安装: {stats['installed_models']} | "
            f"运行中: {stats['running_models']}"
        )

    def _on_search(self, text: str):
        """搜索处理"""
        self._refresh_model_cards()

    def _on_filter_changed(self):
        """筛选变化处理"""
        self._refresh_model_cards()

    def _on_install(self, model_id: str):
        """安装模型"""
        if not self.store_manager:
            return

        # 进度对话框
        progress = ProgressDialog(f"安装 {model_id}...")
        progress.show()

        def progress_callback(p):
            if hasattr(p, 'progress'):
                progress.update_progress(p.progress, p.message)
            else:
                progress.update_progress(50, str(p))

        try:
            result = self.store_manager.install(model_id, progress_callback)

            if result['success']:
                progress.accept()
                QMessageBox.information(self, "安装成功", result['message'])
            else:
                progress.reject()
                QMessageBox.warning(self, "安装失败", result.get('error', '未知错误'))

        except Exception as e:
            progress.reject()
            QMessageBox.critical(self, "错误", str(e))

        self._refresh_model_cards()
        self._update_stats()

    def _on_uninstall(self, model_id: str):
        """卸载模型"""
        reply = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载模型 {model_id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.store_manager:
                result = self.store_manager.uninstall(model_id)
                if result['success']:
                    QMessageBox.information(self, "卸载成功", result['message'])
                else:
                    QMessageBox.warning(self, "卸载失败", result.get('error', '未知错误'))

            self._refresh_model_cards()
            self._update_stats()

    def _on_run(self, model_id: str):
        """运行模型"""
        # 弹出输入对话框
        dialog = QInputDialog(self)
        dialog.setWindowTitle(f"运行 {model_id}")
        dialog.setLabelText("输入数据 (JSON格式):")
        dialog.setTextValue('{"input": "data"}')

        if dialog.exec():
            input_text = dialog.textValue()

            try:
                input_data = json.loads(input_text)

                if self.store_manager:
                    result = self.store_manager.run_model(model_id, input_data)

                    if result['success']:
                        output_text = json.dumps(result['output'], ensure_ascii=False, indent=2)
                        QMessageBox.information(
                            self, "执行成功",
                            f"执行时间: {result['execution_time_ms']:.2f}ms\n\n输出:\n{output_text}"
                        )
                    else:
                        QMessageBox.warning(self, "执行失败", result.get('error', '未知错误'))

            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "输入错误", f"JSON格式错误: {e}")

    def _stop_runtime(self, model_id: str):
        """停止运行时"""
        if self.store_manager:
            self.store_manager.runtime_manager.stop_runtime(model_id)
            self._refresh_status()

    def closeEvent(self, event):
        """关闭事件"""
        if self.store_manager:
            self.store_manager.shutdown()
        super().closeEvent(event)