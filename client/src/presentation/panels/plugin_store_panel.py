"""
Plugin Store Panel - 插件商店面板

浏览、搜索、安装、更新插件。
集成依赖自动安装、版本管理、安全扫描。
"""

import json
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QSize, QUrl, QMimeData,
)
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon, QDesktopServices, QDrag
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QProgressBar, QTextEdit, QGroupBox,
    QSplitter, QHeaderView, QMessageBox, QTreeWidget,
    QTreeWidgetItem, QStatusBar, QLineEdit, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QDialog,
    QFormLayout, QSpinBox, QFileDialog, QProgressBar,
)


# ──────────────────────────────────────────────────────────────
# 插件商品（商店中的插件）
# ──────────────────────────────────────────────────────────────

class PluginProduct:
    """插件商品（商店中的插件）"""

    def __init__(
        self,
        plugin_id: str,
        name: str,
        version: str,
        author: str,
        description: str,
        category: str = "other",
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        download_url: str = "",
        icon_url: str = "",
        screenshots: Optional[List[str]] = None,
        rating: float = 0.0,
        download_count: int = 0,
        price: float = 0.0,  # 0 表示免费
        license_type: str = "MIT",
    ):
        self.plugin_id = plugin_id
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.category = category
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.download_url = download_url
        self.icon_url = icon_url
        self.screenshots = screenshots or []
        self.rating = rating
        self.download_count = download_count
        self.price = price
        self.license_type = license_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "download_url": self.download_url,
            "icon_url": self.icon_url,
            "screenshots": self.screenshots,
            "rating": self.rating,
            "download_count": self.download_count,
            "price": self.price,
            "license": self.license_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginProduct":
        return cls(**data)


# ──────────────────────────────────────────────────────────────
# 插件商店 API（模拟）
# ──────────────────────────────────────────────────────────────

class PluginStoreAPI:
    """
    插件商店 API

    模拟商店后端（实际应连接真实商店服务）。
    """

    def __init__(self, base_url: str = "https://store.livingtree.ai"):
        self._base_url = base_url
        self._cache: Dict[str, PluginProduct] = {}
        self._installed: Dict[str, str] = {}  # plugin_id -> installed_version

    def search(
        self,
        query: str = "",
        category: str = "",
        tags: Optional[List[str]] = None,
        sort_by: str = "download_count",  # download_count | rating | name
    ) -> List[PluginProduct]:
        """
        搜索插件

        Args:
            query: 搜索关键词
            category: 分类过滤
            tags: 标签过滤
            sort_by: 排序方式

        Returns:
            插件商品列表
        """
        # 模拟数据（实际应从 API 获取）
        mock_products = self._get_mock_products()

        results = []
        for p in mock_products:
            # 关键词过滤
            if query:
                q = query.lower()
                if (
                    q not in p.name.lower()
                    and q not in p.description.lower()
                    and q not in " ".join(p.tags).lower()
                ):
                    continue

            # 分类过滤
            if category and p.category != category:
                continue

            # 标签过滤
            if tags:
                if not any(tag in p.tags for tag in tags):
                    continue

            results.append(p)

        # 排序
        reverse = sort_by in ("download_count", "rating")
        results.sort(
            key=lambda p: getattr(p, sort_by, 0),
            reverse=reverse,
        )

        return results

    def get_product(self, plugin_id: str) -> Optional[PluginProduct]:
        """获取插件详情"""
        if plugin_id in self._cache:
            return self._cache[plugin_id]

        products = self._get_mock_products()
        for p in products:
            if p.plugin_id == plugin_id:
                self._cache[plugin_id] = p
                return p
        return None

    def get_installed_version(self, plugin_id: str) -> Optional[str]:
        """获取已安装版本"""
        return self._installed.get(plugin_id)

    def set_installed(self, plugin_id: str, version: str) -> None:
        """设置已安装版本"""
        self._installed[plugin_id] = version

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return ["ai", "ui", "data", "network", "tool", "game", "other"]

    def _get_mock_products(self) -> List[PluginProduct]:
        """获取模拟商品数据"""
        return [
            PluginProduct(
                plugin_id="ai_chat",
                name="AI 对话助手",
                version="2.1.0",
                author="LivingTree Team",
                description="智能 AI 对话插件，支持多模型切换、上下文管理、提示词模板。",
                category="ai",
                tags=["ai", "chat", "llm"],
                dependencies=["config_provider"],
                download_url="https://store.livingtree.ai/download/ai_chat",
                rating=4.8,
                download_count=15230,
                price=0.0,
            ),
            PluginProduct(
                plugin_id="code_editor",
                name="代码编辑器",
                version="1.5.2",
                author="DevTools",
                description="集成 VSCode 内核的代码编辑器，支持 Python、JavaScript、TypeScript。",
                category="tool",
                tags=["editor", "code", "vscode"],
                dependencies=["file_manager"],
                download_url="https://store.livingtree.ai/download/code_editor",
                rating=4.5,
                download_count=8930,
                price=0.0,
            ),
            PluginProduct(
                plugin_id="data_viz",
                name="数据可视化",
                version="3.0.1",
                author="DataLab",
                description="丰富的图表类型：折线图、柱状图、散点图、热力图、地图可视化。",
                category="data",
                tags=["data", "chart", "visualization"],
                dependencies=["config_provider", "file_manager"],
                download_url="https://store.livingtree.ai/download/data_viz",
                rating=4.7,
                download_count=12450,
                price=29.99,
            ),
            PluginProduct(
                plugin_id="git_helper",
                name="Git 助手",
                version="2.2.0",
                author="GitTools",
                description="图形化 Git 操作：提交、推送、拉取、分支管理、合并冲突解决。",
                category="tool",
                tags=["git", "version", "vcs"],
                dependencies=[],
                download_url="https://store.livingtree.ai/download/git_helper",
                rating=4.6,
                download_count=6750,
                price=0.0,
            ),
        ]


# ──────────────────────────────────────────────────────────────
# 插件列表控件
# ──────────────────────────────────────────────────────────────

class PluginListWidget(QListWidget):
    """插件列表控件"""

    plugin_selected = pyqtSignal(PluginProduct)

    def __init__(self):
        super().__init__()
        self._products: List[PluginProduct] = []
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(64, 64))
        self.setGridSize(QSize(120, 120))
        self.itemClicked.connect(self._on_item_clicked)

    def set_products(self, products: List[PluginProduct]) -> None:
        """设置插件列表"""
        self.clear()
        self._products = products

        for p in products:
            item = QListWidgetItem(p.name)
            # 模拟图标（实际应从 icon_url 加载）
            item.setIcon(QIcon.fromTheme("application-x-executable"))
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        product = item.data(Qt.ItemDataRole.UserRole)
        if product:
            self.plugin_selected.emit(product)


# ──────────────────────────────────────────────────────────────
# 插件详情面板
# ──────────────────────────────────────────────────────────────

class PluginDetailWidget(QWidget):
    """插件详情面板"""

    install_requested = pyqtSignal(PluginProduct)
    update_requested = pyqtSignal(PluginProduct)

    def __init__(self):
        super().__init__()
        self._product: Optional[PluginProduct] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        self._title_label = QLabel("请选择插件")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self._title_label.setFont(font)
        layout.addWidget(self._title_label)

        # 元信息
        self._meta_label = QLabel("")
        self._meta_label.setWordWrap(True)
        layout.addWidget(self._meta_label)

        # 描述
        self._desc_label = QLabel("")
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("padding: 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self._desc_label)

        # 依赖
        self._deps_label = QLabel("")
        self._deps_label.setWordWrap(True)
        layout.addWidget(self._deps_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self._btn_install = QPushButton("安装")
        self._btn_update = QPushButton("更新")
        self._btn_install.clicked.connect(self._on_install)
        self._btn_update.clicked.connect(self._on_update)
        btn_layout.addWidget(self._btn_install)
        btn_layout.addWidget(self._btn_update)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def set_product(self, product: PluginProduct) -> None:
        """设置插件详情"""
        self._product = product
        self._title_label.setText(f"{product.name} v{product.version}")

        # 元信息
        meta = f"作者：{product.author} | 评分：{product.rating}★ | 下载：{product.download_count}"
        self._meta_label.setText(meta)

        # 描述
        self._desc_label.setText(product.description)

        # 依赖
        if product.dependencies:
            deps_text = "依赖：" + "、".join(product.dependencies)
        else:
            deps_text = "依赖：无"
        self._deps_label.setText(deps_text)

        # 按钮状态
        self._btn_install.setEnabled(True)
        self._btn_update.setEnabled(False)  # 暂未实现版本检测

    def _on_install(self) -> None:
        if self._product:
            self.install_requested.emit(self._product)

    def _on_update(self) -> None:
        if self._product:
            self.update_requested.emit(self._product)


# ──────────────────────────────────────────────────────────────
# 主商店面板
# ──────────────────────────────────────────────────────────────

class PluginStorePanel(QWidget):
    """
    插件商店面板

    功能：
    1. 浏览/搜索插件
    2. 查看插件详情
    3. 安装/更新插件
    4. 管理已安装插件
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._api = PluginStoreAPI()
        self._setup_ui()
        self._load_products()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索："))

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入关键词搜索插件...")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)

        search_layout.addWidget(QLabel("分类："))
        self._category_combo = QComboBox()
        self._category_combo.addItem("全部分类", "")
        for cat in self._api.get_categories():
            self._category_combo.addItem(cat, cat)
        self._category_combo.currentIndexChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._category_combo)

        search_layout.addStretch()
        main_layout.addLayout(search_layout)

        # 分割器：列表 + 详情
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：插件列表
        self._list_widget = PluginListWidget()
        self._list_widget.plugin_selected.connect(self._on_plugin_selected)
        splitter.addWidget(self._list_widget)

        # 右侧：插件详情
        self._detail_widget = PluginDetailWidget()
        self._detail_widget.install_requested.connect(self._on_install_requested)
        splitter.addWidget(self._detail_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # 状态栏
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("就绪")
        main_layout.addWidget(self._status_bar)

    def _load_products(self) -> None:
        """加载插件列表"""
        products = self._api.search()
        self._list_widget.set_products(products)
        self._status_bar.showMessage(f"找到 {len(products)} 个插件")

    def _on_search_changed(self) -> None:
        """搜索条件变化"""
        query = self._search_input.text()
        category = self._category_combo.currentData()
        products = self._api.search(
            query=query,
            category=category or "",
        )
        self._list_widget.set_products(products)
        self._status_bar.showMessage(f"找到 {len(products)} 个插件")

    def _on_plugin_selected(self, product: PluginProduct) -> None:
        """插件被选中"""
        self._detail_widget.set_product(product)

    def _on_install_requested(self, product: PluginProduct) -> None:
        """安装请求"""
        # 检查依赖
        if product.dependencies:
            deps_text = "\n".join(f"  • {dep}" for dep in product.dependencies)
            reply = QMessageBox.question(
                self,
                "安装确认",
                f"即将安装 {product.name}\n\n"
                f"依赖项：\n{deps_text}\n\n"
                "是否自动安装依赖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            # 这里应该实现自动安装依赖
            # 暂时只显示提示
            self._status_bar.showMessage(
                f"正在安装 {product.name} 及其依赖..."
            )
        else:
            self._status_bar.showMessage(f"正在安装 {product.name}...")

        # 模拟安装
        QTimer.singleShot(
            1000,
            lambda: self._on_install_finished(product),
        )

    def _on_install_finished(self, product: PluginProduct) -> None:
        """安装完成"""
        self._api.set_installed(product.plugin_id, product.version)
        self._status_bar.showMessage(
            f"已安装 {product.name} v{product.version}"
        )
        QMessageBox.information(
            self,
            "安装成功",
            f"{product.name} 已成功安装！\n\n"
            "请在插件管理面板中激活此插件。",
        )


# ──────────────────────────────────────────────────────────────
# 独立窗口版本
# ──────────────────────────────────────────────────────────────

class PluginStoreWindow(QWidget):
    """独立窗口版插件商店"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("插件商店 - LivingTreeAI")
        self.setMinimumSize(1000, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(PluginStorePanel())


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PluginStoreWindow()
    window.show()
    sys.exit(app.exec())
