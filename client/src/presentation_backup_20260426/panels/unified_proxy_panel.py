"""
统一代理源面板 - 集成到 Workspace Panel
=======================================

功能：
1. 一处设置代理，无需到处配置
2. 支持 GitHub 搜索源
3. 简洁的 UI 设计

使用方式：
    from .presentation.panels.unified_proxy_panel import UnifiedProxyPanel

    panel = UnifiedProxyPanel()
    layout.addWidget(panel)
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QGroupBox,
    QCheckBox, QComboBox, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class UnifiedProxyPanel(QWidget):
    """
    统一代理源面板

    特性：
    - 单一入口设置代理
    - GitHub 搜索源开关
    - 实时状态显示
    """

    # 信号
    proxy_changed = pyqtSignal(str)  # 代理地址变化
    search_requested = pyqtSignal(str, str)  # 搜索请求 (query, engine)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 延迟导入避免循环依赖
        self._config = None

        self._setup_ui()
        self._load_config()

    def _get_config(self):
        """获取配置实例（延迟加载）"""
        if self._config is None:
            from .business.unified_proxy_config import UnifiedProxyConfig
            self._config = UnifiedProxyConfig.get_instance()
        return self._config

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── 代理设置区 ──────────────────────────────────────────────
        proxy_group = QGroupBox("🌐 代理设置")
        proxy_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        proxy_layout = QVBoxLayout()

        # 代理地址输入
        input_layout = QHBoxLayout()

        proxy_label = QLabel("代理地址:")
        proxy_label.setStyleSheet("font-size: 11px; color: #666;")
        input_layout.addWidget(proxy_label)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://127.0.0.1:7890")
        self.proxy_input.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        self.proxy_input.returnPressed.connect(self._on_proxy_changed)
        input_layout.addWidget(self.proxy_input, 1)

        proxy_layout.addLayout(input_layout)

        # 代理开关和按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.enable_check = QCheckBox("启用代理")
        self.enable_check.setStyleSheet("font-size: 11px;")
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        btn_layout.addWidget(self.enable_check)

        btn_layout.addStretch()

        self.apply_btn = QPushButton("应用")
        self.apply_btn.setFixedSize(60, 28)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.apply_btn.clicked.connect(self._on_proxy_changed)
        btn_layout.addWidget(self.apply_btn)

        self.clear_btn = QPushButton("清除")
        self.clear_btn.setFixedSize(60, 28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                color: #666666;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.clear_btn.clicked.connect(self._on_clear_proxy)
        btn_layout.addWidget(self.clear_btn)

        proxy_layout.addLayout(btn_layout)
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # ── 搜索源设置区 ──────────────────────────────────────────────
        source_group = QGroupBox("🔍 搜索源")
        source_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        source_layout = QVBoxLayout()
        source_layout.setSpacing(6)

        # GitHub 搜索开关
        self.github_check = QCheckBox("GitHub 搜索")
        self.github_check.setStyleSheet("font-size: 11px;")
        self.github_check.setChecked(True)
        self.github_check.stateChanged.connect(self._on_github_changed)
        source_layout.addWidget(self.github_check)

        # GitHub Token 输入
        token_layout = QHBoxLayout()
        token_label = QLabel("Token:")
        token_label.setStyleSheet("font-size: 11px; color: #666;")
        token_label.setFixedWidth(40)
        token_layout.addWidget(token_label)

        self.github_token_input = QLineEdit()
        self.github_token_input.setPlaceholderText("ghp_xxx (可选)")
        self.github_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_input.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        token_layout.addWidget(self.github_token_input, 1)

        self.token_toggle = QPushButton("👁")
        self.token_toggle.setFixedSize(28, 28)
        self.token_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                color: #999;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        self.token_toggle.clicked.connect(self._toggle_token_visibility)
        token_layout.addWidget(self.token_toggle)

        source_layout.addLayout(token_layout)

        # 其他搜索引擎
        other_layout = QHBoxLayout()
        other_layout.setSpacing(8)

        self.duckduckgo_check = QCheckBox("DuckDuckGo")
        self.duckduckgo_check.setStyleSheet("font-size: 11px;")
        self.duckduckgo_check.setChecked(True)
        self.duckduckgo_check.stateChanged.connect(self._on_source_changed)
        other_layout.addWidget(self.duckduckgo_check)

        self.google_check = QCheckBox("Google")
        self.google_check.setStyleSheet("font-size: 11px;")
        self.google_check.stateChanged.connect(self._on_source_changed)
        other_layout.addWidget(self.google_check)

        self.bing_check = QCheckBox("Bing")
        self.bing_check.setStyleSheet("font-size: 11px;")
        self.bing_check.stateChanged.connect(self._on_source_changed)
        other_layout.addWidget(self.bing_check)

        other_layout.addStretch()
        source_layout.addLayout(other_layout)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # ── 快速搜索区 ──────────────────────────────────────────────
        search_group = QGroupBox("⚡ 快速搜索")
        search_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        search_layout = QVBoxLayout()
        search_layout.setSpacing(8)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        # 搜索按钮行
        search_btn_layout = QHBoxLayout()
        search_btn_layout.setSpacing(8)

        self.search_github_btn = QPushButton("🔍 GitHub")
        self.search_github_btn.setFixedHeight(32)
        self.search_github_btn.setStyleSheet("""
            QPushButton {
                background: #24292E;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #444D56;
            }
        """)
        self.search_github_btn.clicked.connect(self._on_search_github)
        search_btn_layout.addWidget(self.search_github_btn)

        self.search_web_btn = QPushButton("🔍 全网")
        self.search_web_btn.setFixedHeight(32)
        self.search_web_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.search_web_btn.clicked.connect(self._on_search_web)
        search_btn_layout.addWidget(self.search_web_btn)

        search_layout.addLayout(search_btn_layout)

        # 搜索结果预览
        self.result_preview = QTextEdit()
        self.result_preview.setReadOnly(True)
        self.result_preview.setMaximumHeight(150)
        self.result_preview.setPlaceholderText("搜索结果将显示在这里...")
        self.result_preview.setStyleSheet("""
            QTextEdit {
                background: #F8F9FA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                color: #333;
            }
        """)
        search_layout.addWidget(self.result_preview)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # ── 状态显示 ──────────────────────────────────────────────
        self.status_label = QLabel("● 代理未设置")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #999;
                padding: 4px;
            }
        """)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _load_config(self):
        """加载配置"""
        config = self._get_config()

        # 加载代理设置
        proxy = config.get_proxy()
        if proxy:
            self.proxy_input.setText(proxy)
            self.enable_check.setChecked(True)
        else:
            self.enable_check.setChecked(False)

        # 加载 GitHub Token
        github_token = config.get_github_token()
        if github_token:
            self.github_token_input.setText(github_token)

        # 加载搜索源
        enabled_sources = config.get_enabled_sources()
        source_values = [s.value for s in enabled_sources]

        self.github_check.setChecked("github" in source_values)
        self.duckduckgo_check.setChecked("duckduckgo" in source_values)
        self.google_check.setChecked("google" in source_values)
        self.bing_check.setChecked("bing" in source_values)

        self._update_status()

    def _update_status(self):
        """更新状态显示"""
        config = self._get_config()
        proxy = config.get_proxy()

        if proxy and config.is_enabled():
            self.status_label.setText("● 代理已启用")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #10B981;
                    padding: 4px;
                }
            """)
        else:
            self.status_label.setText("● 代理未设置")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #999;
                    padding: 4px;
                }
            """)

    # ==================== 事件处理 ====================

    def _on_proxy_changed(self):
        """代理地址变化"""
        proxy = self.proxy_input.text().strip()

        if not proxy:
            self._on_clear_proxy()
            return

        config = self._get_config()
        config.set_proxy(proxy)
        self._update_status()

        self.proxy_changed.emit(proxy)
        self._show_message("提示", "代理设置已应用")

    def _on_enable_changed(self, state):
        """启用状态变化"""
        config = self._get_config()

        if state:
            proxy = self.proxy_input.text().strip()
            if proxy:
                config.set_proxy(proxy)
            else:
                # 使用默认代理或清除
                config.set_proxy(None)
                self.enable_check.setChecked(False)
                self._show_message("提示", "请先输入代理地址")
        else:
            config.set_proxy(None)

        self._update_status()

    def _on_clear_proxy(self):
        """清除代理"""
        self.proxy_input.clear()
        config = self._get_config()
        config.set_proxy(None)
        self.enable_check.setChecked(False)
        self._update_status()
        self._show_message("提示", "代理已清除")

    def _on_github_changed(self, state):
        """GitHub 开关变化"""
        config = self._get_config()
        from .business.unified_proxy_config import SearchSource

        if state:
            config.enable_source(SearchSource.GITHUB)
        else:
            config.disable_source(SearchSource.GITHUB)

    def _on_source_changed(self, state):
        """其他搜索源变化"""
        config = self._get_config()
        from .business.unified_proxy_config import SearchSource

        source_map = {
            self.duckduckgo_check: SearchSource.DUCKDUCKGO,
            self.google_check: SearchSource.GOOGLE,
            self.bing_check: SearchSource.BING,
        }

        for check, source in source_map.items():
            if check.isChecked():
                config.enable_source(source)
            else:
                config.disable_source(source)

    def _toggle_token_visibility(self):
        """切换 Token 可见性"""
        if self.github_token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.github_token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.token_toggle.setText("🔒")
        else:
            self.github_token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.token_toggle.setText("👁")

    def _on_search(self):
        """通用搜索"""
        query = self.search_input.text().strip()
        if not query:
            return

        # 优先使用 GitHub
        if self.github_check.isChecked():
            self._on_search_github()
        else:
            self._on_search_web()

    def _on_search_github(self):
        """GitHub 搜索"""
        query = self.search_input.text().strip()
        if not query:
            self._show_message("提示", "请输入搜索关键词")
            return

        # 保存 Token
        token = self.github_token_input.text().strip()
        if token:
            config = self._get_config()
            config.set_github_token(token)

        self.search_requested.emit(query, "github")
        self._do_github_search(query)

    def _on_search_web(self):
        """全网搜索"""
        query = self.search_input.text().strip()
        if not query:
            self._show_message("提示", "请输入搜索关键词")
            return

        self.search_requested.emit(query, "duckduckgo")
        self._do_web_search(query)

    async def _do_github_search(self, query: str):
        """执行 GitHub 搜索"""
        import asyncio

        self.result_preview.setText("🔍 搜索中...")
        self.search_github_btn.setEnabled(False)

        try:
            config = self._get_config()

            # 获取 Token
            token = self.github_token_input.text().strip()
            if token and not config.get_github_token():
                config.set_github_token(token)

            # 执行搜索
            results = await asyncio.to_thread(config.search_github, query, 5)

            if results:
                lines = [f"✅ GitHub 搜索结果 ({len(results)} 条)\n"]
                for i, r in enumerate(results[:5], 1):
                    lines.append(f"{i}. {r['title']}")
                    if r['snippet']:
                        lines.append(f"   {r['snippet'][:80]}...")
                    lines.append(f"   ⭐ {r['score']} | {r['url']}\n")
            else:
                lines = ["❌ 未找到结果"]

            self.result_preview.setText("\n".join(lines))

        except Exception as e:
            self.result_preview.setText(f"❌ 搜索失败: {str(e)}")
            logger.error(f"GitHub search failed: {e}")

        finally:
            self.search_github_btn.setEnabled(True)

    async def _do_web_search(self, query: str):
        """执行全网搜索"""
        import asyncio

        self.result_preview.setText("🔍 搜索中...")
        self.search_web_btn.setEnabled(False)

        try:
            config = self._get_config()
            from .business.unified_proxy_config import SearchSource

            results = await config.search(query, SearchSource.DUCKDUCKGO, 5)

            if results:
                lines = [f"✅ 全网搜索结果 ({len(results)} 条)\n"]
                for i, r in enumerate(results[:5], 1):
                    lines.append(f"{i}. {r.get('title', '无标题')}")
                    snippet = r.get('snippet', '')
                    if snippet:
                        lines.append(f"   {snippet[:80]}...")
                    lines.append(f"   {r.get('url', '')}\n")
            else:
                lines = ["❌ 未找到结果"]

            self.result_preview.setText("\n".join(lines))

        except Exception as e:
            self.result_preview.setText(f"❌ 搜索失败: {str(e)}")
            logger.error(f"Web search failed: {e}")

        finally:
            self.search_web_btn.setEnabled(True)

    def _show_message(self, title: str, message: str):
        """显示消息提示"""
        QMessageBox.information(self, title, message)

    # ==================== 公共接口 ====================

    def get_proxy(self) -> Optional[str]:
        """获取当前代理"""
        return self._get_config().get_proxy()

    def is_proxy_enabled(self) -> bool:
        """代理是否启用"""
        return self._get_config().is_enabled()

    def refresh(self):
        """刷新配置"""
        self._load_config()


# ── 导出 ──────────────────────────────────────────────────────────────

__all__ = ["UnifiedProxyPanel"]
