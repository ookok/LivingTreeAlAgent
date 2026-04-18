"""
GitHub Store UI Panel
桌面代码仓库 - 发现、安装、管理 GitHub Release 桌面应用
"""

import asyncio
import webbrowser
from datetime import datetime
from typing import Optional, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QListWidget, QListWidgetItem,
    QProgressBar, QSpinner,
    QGroupBox, QComboBox, QCheckBox, QTextBrowser,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QFrame, QSizePolicy, QSplitter,
    QStatusBar, QMenuBar, QMenu,
)
from PyQt6.QtGui import QFont, QAction, QPalette, QColor, QIcon

# 图标 (使用 emoji 作为占位)
ICONS = {
    "windows": "🪟",
    "linux": "🐧",
    "macos": "🍎",
    "android": "📱",
    "star": "⭐",
    "fork": "🍴",
    "download": "⬇️",
    "install": "📦",
    "update": "🔄",
    "search": "🔍",
    "trending": "📈",
    "favorite": "❤️",
    "recent": "🕐",
    "settings": "⚙️",
    "category": "📁",
    "app": "🛍️",
    "info": "ℹ️",
    "check": "✅",
    "error": "❌",
}


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_date(dt: datetime) -> str:
    """格式化日期"""
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d") if dt else ""


# ── 线程工作器 ──────────────────────────────────────────────────────

class WorkerThread(QThread):
    """异步工作线程"""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(dict)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._func(*self._args, **self._kwargs))
            self.finished_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))


# ── 应用卡片 ────────────────────────────────────────────────────────

class AppCard(QFrame):
    """应用卡片组件"""

    clicked = pyqtSignal(str)  # repo_full_name
    install_clicked = pyqtSignal(str, dict)  # repo_full_name, asset_info

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._setup_ui()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题行
        title_layout = QHBoxLayout()
        name_label = QLabel(f"<b>{self.repo.name}</b>")
        name_label.setStyleSheet("font-size: 14px; color: #2c3e50;")
        stars_label = QLabel(f"{ICONS['star']} {self.repo.stars:,}")
        stars_label.setStyleSheet("color: #f39c12; font-size: 12px;")
        title_layout.addWidget(name_label)
        title_layout.addStretch()
        title_layout.addWidget(stars_label)
        layout.addLayout(title_layout)

        # 所有者
        owner_label = QLabel(f"{self.repo.owner}")
        owner_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(owner_label)

        # 描述
        if self.repo.description:
            desc_label = QLabel(self.repo.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #34495e; font-size: 12px;")
            desc_label.setMaximumHeight(40)
            layout.addWidget(desc_label)

        # 平台标签
        platform_layout = QHBoxLayout()
        for plat in self.repo.platform_tags[:4]:
            tag = QLabel(ICONS.get(plat.lower(), "📦"))
            tag.setStyleSheet(
                "background: #ecf0f1; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )
            platform_layout.addWidget(tag)
        platform_layout.addStretch()
        layout.addLayout(platform_layout)

        # 最新版本
        if self.repo.latest_release:
            version_layout = QHBoxLayout()
            version_label = QLabel(f"v{self.repo.latest_release.version}")
            version_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
            date_label = QLabel(format_date(self.repo.latest_release.published_at))
            date_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
            version_layout.addWidget(version_label)
            version_layout.addStretch()
            version_layout.addWidget(date_label)
            layout.addLayout(version_layout)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        open_btn = QPushButton("🌐 主页")
        open_btn.setFixedHeight(28)
        open_btn.clicked.connect(lambda: webbrowser.open(self.repo.html_url))
        btn_layout.addWidget(open_btn)

        if self.repo.latest_release and self.repo.latest_release.assets:
            install_btn = QPushButton(f"{ICONS['download']} 安装")
            install_btn.setFixedHeight(28)
            install_btn.setStyleSheet(
                "background: #27ae60; color: white; border-radius: 4px; font-weight: bold;"
            )
            install_btn.clicked.connect(self._on_install)
            btn_layout.addWidget(install_btn)

        layout.addLayout(btn_layout)

        # 鼠标悬停效果
        self.setStyleSheet(
            "AppCard { background: white; border: 1px solid #ecf0f1; border-radius: 8px; }"
            "AppCard:hover { border-color: #3498db; }"
        )

    def _on_install(self):
        if self.repo.latest_release and self.repo.latest_release.assets:
            asset = self.repo.latest_release.assets[0]
            self.install_clicked.emit(
                self.repo.full_name,
                {
                    "version": self.repo.latest_release.version,
                    "asset_name": asset.name,
                    "download_url": asset.download_url,
                    "size": asset.size,
                    "platform": asset.platform.value if asset.platform else "all",
                }
            )


# ── 主面板 ──────────────────────────────────────────────────────────

class GitHubStorePanel(QWidget):
    """
    GitHub Store 主面板

    标签页:
    1. 发现 - 趋势、分类
    2. 我的应用 - 已安装、收藏、最近
    3. 搜索 - 搜索 GitHub 仓库
    4. 设置 - API Token、下载目录
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = None
        self._current_platform = "all"
        self._search_results = []
        self._worker = None

        self._setup_ui()
        self._init_store()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 顶部搜索栏
        header = self._create_header()
        main_layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_discover_tab(), f"{ICONS['trending']} 发现")
        self.tabs.addTab(self._create_my_apps_tab(), f"{ICONS['app']} 我的应用")
        self.tabs.addTab(self._create_search_tab(), f"{ICONS['search']} 搜索")
        self.tabs.addTab(self._create_settings_tab(), f"{ICONS['settings']} 设置")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            "background: #2c3e50; color: white; padding: 4px 12px; font-size: 11px;"
        )
        main_layout.addWidget(self.status_bar)

    def _create_header(self) -> QWidget:
        """创建顶部搜索栏"""
        header = QFrame()
        header.setStyleSheet("background: #2c3e50; padding: 12px;")
        layout = QHBoxLayout(header)

        # Logo/标题
        title = QLabel("🛍️ GitHub Store")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 平台筛选
        platform_combo = QComboBox()
        platform_combo.addItems([
            "🪟 Windows", "🐧 Linux", "🍎 macOS", "📱 Android", "📦 所有平台"
        ])
        platform_combo.setFixedWidth(140)
        platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        layout.addWidget(platform_combo)

        layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet("border-radius: 18px;")
        refresh_btn.clicked.connect(self._refresh_current_tab)
        layout.addWidget(refresh_btn)

        return header

    def _create_discover_tab(self) -> QWidget:
        """发现标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 子标签: 趋势 / 分类
        sub_tabs = QTabWidget()

        # 趋势页
        trending_widget = QWidget()
        trending_layout = QVBoxLayout(trending_widget)

        # 趋势网格
        self.trending_scroll = QScrollArea()
        self.trending_scroll.setWidgetResizable(True)
        self.trending_scroll.setStyleSheet("border: none;")

        self.trending_content = QWidget()
        self.trending_grid = QGridLayout(self.trending_content)
        self.trending_grid.setSpacing(12)
        self.trending_scroll.setWidget(self.trending_content)

        trending_layout.addWidget(self.trending_scroll)
        sub_tabs.addTab(trending_widget, f"{ICONS['trending']} 趋势")

        # 分类页
        categories_widget = QWidget()
        categories_layout = QVBoxLayout(categories_widget)

        self.categories_scroll = QScrollArea()
        self.categories_scroll.setWidgetResizable(True)

        categories_content = QWidget()
        categories_grid = QGridLayout(categories_content)
        categories_grid.setSpacing(12)

        # 分类卡片
        categories = [
            ("🛠️", "开发者工具", "developer-tools"),
            ("🔧", "实用工具", "utilities"),
            ("🤖", "AI 与机器学习", "ai-ml"),
            ("🎨", "多媒体", "media"),
            ("🌐", "网络工具", "network"),
            ("🎮", "游戏", "games"),
            ("📊", "效率", "productivity"),
            ("🔒", "安全", "security"),
        ]

        for i, (icon, name, cat_id) in enumerate(categories):
            card = self._create_category_card(icon, name, cat_id)
            categories_grid.addWidget(card, i // 4, i % 4)

        self.categories_scroll.setWidget(categories_content)
        categories_layout.addWidget(self.categories_scroll)
        sub_tabs.addTab(categories_widget, f"{ICONS['category']} 分类")

        layout.addWidget(sub_tabs)
        return widget

    def _create_category_card(self, icon: str, name: str, cat_id: str) -> QFrame:
        """创建分类卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet("""
            QFrame { background: white; border: 1px solid #ecf0f1; border-radius: 8px; }
            QFrame:hover { border-color: #3498db; background: #f8f9fa; }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        icon_label = QLabel(f"<h1>{icon}</h1>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        name_label = QLabel(f"<b>{name}</b>")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        layout.addWidget(name_label)

        card.mousePressEvent = lambda e, cid=cat_id: self._on_category_clicked(cid)

        return card

    def _create_my_apps_tab(self) -> QWidget:
        """我的应用标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 子标签
        sub_tabs = QTabWidget()

        # 已安装
        installed_widget = QWidget()
        installed_layout = QVBoxLayout(installed_widget)
        self.installed_list = QListWidget()
        installed_layout.addWidget(self.installed_list)
        sub_tabs.addTab(installed_widget, f"{ICONS['install']} 已安装")

        # 收藏
        favorites_widget = QWidget()
        favorites_layout = QVBoxLayout(favorites_widget)
        self.favorites_list = QListWidget()
        favorites_layout.addWidget(self.favorites_list)
        sub_tabs.addTab(favorites_widget, f"{ICONS['favorite']} 收藏")

        # 最近
        recent_widget = QWidget()
        recent_layout = QVBoxLayout(recent_widget)
        self.recent_list = QListWidget()
        recent_layout.addWidget(self.recent_list)
        sub_tabs.addTab(recent_widget, f"{ICONS['recent']} 最近")

        layout.addWidget(sub_tabs)
        return widget

    def _create_search_tab(self) -> QWidget:
        """搜索标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索框
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索 GitHub 仓库... (例如: VSCode, electron, linux tool)")
        self.search_input.setMinimumHeight(40)
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton(f"{ICONS['search']} 搜索")
        search_btn.setFixedSize(100, 40)
        search_btn.setStyleSheet("background: #3498db; color: white; border-radius: 6px;")
        search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # 搜索结果
        self.search_scroll = QScrollArea()
        self.search_scroll.setWidgetResizable(True)
        self.search_content = QWidget()
        self.search_grid = QGridLayout(self.search_content)
        self.search_grid.setSpacing(12)
        self.search_scroll.setWidget(self.search_content)

        layout.addWidget(self.search_scroll)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # GitHub Token
        token_group = QGroupBox("🔑 GitHub API Token")
        token_layout = QVBoxLayout(token_group)

        token_desc = QLabel(
            "填入 GitHub Personal Access Token 以提高 API 速率限制\n"
            "(未认证: 60次/小时, 已认证: 5000次/小时)"
        )
        token_desc.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        token_layout.addWidget(token_desc)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_layout.addWidget(self.token_input)

        save_token_btn = QPushButton("保存 Token")
        save_token_btn.clicked.connect(self._save_token)
        token_layout.addWidget(save_token_btn)

        layout.addWidget(token_group)

        # 下载设置
        download_group = QGroupBox("📂 下载设置")
        download_layout = QVBoxLayout(download_group)

        download_dir_layout = QHBoxLayout()
        download_dir_layout.addWidget(QLabel("下载目录:"))
        self.download_dir_input = QLineEdit("~/.hermes-desktop/github_store/downloads")
        download_dir_layout.addWidget(self.download_dir_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_download_dir)
        download_dir_layout.addWidget(browse_btn)

        download_layout.addLayout(download_dir_layout)
        layout.addWidget(download_group)

        # 缓存设置
        cache_group = QGroupBox("🗄️ 缓存")
        cache_layout = QVBoxLayout(cache_group)

        clear_cache_btn = QPushButton("清空缓存")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_layout.addWidget(clear_cache_btn)

        layout.addWidget(cache_group)

        layout.addStretch()

        return widget

    # ── 事件处理 ────────────────────────────────────────────────────

    def _init_store(self):
        """初始化商店"""
        try:
            from core.github_store import get_github_store
            self._store = get_github_store()
            self.status_bar.setText("✅ GitHub Store 已就绪")
            self._load_trending()
        except Exception as e:
            self.status_bar.setText(f"❌ 初始化失败: {e}")

    def _load_trending(self):
        """加载趋势"""
        self.status_bar.setText("正在加载趋势项目...")

        def work():
            return asyncio.run(self._store.get_trending(per_page=24))

        self._run_worker(work, self._on_trending_loaded)

    def _on_trending_loaded(self, repos):
        """趋势加载完成"""
        # 清除现有卡片
        while self.trending_grid.count():
            item = self.trending_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新卡片
        for i, repo in enumerate(repos or []):
            card = AppCard(repo)
            card.clicked.connect(lambda r: self._on_repo_clicked(r))
            card.install_clicked.connect(lambda r, a: self._on_install_clicked(r, a))
            self.trending_grid.addWidget(card, i // 3, i % 3)

        self.status_bar.setText(f"已加载 {len(repos or [])} 个趋势项目")

    def _on_category_clicked(self, cat_id: str):
        """分类点击"""
        self.tabs.setCurrentIndex(2)  # 切换到搜索页
        self.search_input.setText(cat_id)
        self._do_search()

    def _on_platform_changed(self, index: int):
        """平台筛选变化"""
        platforms = ["windows", "linux", "macos", "android", None]
        self._current_platform = platforms[index] or "all"
        self._refresh_current_tab()

    def _refresh_current_tab(self):
        """刷新当前标签页"""
        current = self.tabs.currentIndex()
        if current == 0:
            self._load_trending()

    def _do_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            return

        self.status_bar.setText(f"正在搜索: {query}...")

        def work():
            return asyncio.run(
                self._store.search(query, per_page=24)
            )

        self._run_worker(work, self._on_search_finished)

    def _on_search_finished(self, result):
        """搜索完成"""
        repos, total = result

        # 清除现有卡片
        while self.search_grid.count():
            item = self.search_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加新卡片
        for i, repo in enumerate(repos or []):
            card = AppCard(repo)
            card.clicked.connect(lambda r: self._on_repo_clicked(r))
            card.install_clicked.connect(lambda r, a: self._on_install_clicked(r, a))
            self.search_grid.addWidget(card, i // 3, i % 3)

        self.status_bar.setText(f"找到 {total} 个结果，显示 {len(repos or [])} 个")

    def _on_repo_clicked(self, full_name: str):
        """仓库点击"""
        self.status_bar.setText(f"正在加载: {full_name}")
        # 在浏览器中打开
        webbrowser.open(f"https://github.com/{full_name}")

    def _on_install_clicked(self, full_name: str, asset_info: dict):
        """安装点击"""
        self.status_bar.setText(
            f"开始安装 {full_name} v{asset_info['version']}..."
        )

    def _save_token(self):
        """保存 Token"""
        token = self.token_input.text().strip()
        self.status_bar.setText("Token 已保存 (重启后生效)")

    def _browse_download_dir(self):
        """浏览下载目录"""
        # 使用文件管理器打开
        from pathlib import Path
        import os
        path = os.path.expanduser(self.download_dir_input.text() or "~/Downloads")
        os.startfile(path) if os.name == "nt" else os.system(f"xdg-open {path}")

    def _clear_cache(self):
        """清空缓存"""
        if self._store:
            self._store.clear_cache()
        self.status_bar.setText("缓存已清空")

    def _run_worker(self, work_func, callback):
        """运行工作线程"""
        if self._worker and self._worker.isRunning():
            self._worker.wait()

        self._worker = WorkerThread(lambda: work_func())
        self._worker.finished_signal.connect(callback)
        self._worker.error_signal.connect(
            lambda e: self.status_bar.setText(f"错误: {e}")
        )
        self._worker.start()

    def _load_my_apps(self):
        """加载我的应用"""
        if not self._store:
            return

        apps = self._store.get_installed_apps()
        favorites = self._store.get_favorites()
        recent = self._store.get_recent()

        # 已安装
        self.installed_list.clear()
        for app in apps:
            item = QListWidgetItem(
                f"{app.repo_full_name} v{app.installed_version} ({format_size(app.asset_size)})"
            )
            self.installed_list.addItem(item)

        # 收藏
        self.favorites_list.clear()
        for name in favorites:
            item = QListWidgetItem(name)
            self.favorites_list.addItem(item)

        # 最近
        self.recent_list.clear()
        for name in recent:
            item = QListWidgetItem(name)
            self.recent_list.addItem(item)
