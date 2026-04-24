"""
工作区面板 — 右侧栏
显示 hermes-agent 的工作目录文件树、文件预览、Agent 记忆、代理源管理
"""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QPushButton,
    QTabWidget, QFrame,
)

# 导入统一代理面板
try:
    from ui.unified_proxy_panel import UnifiedProxyPanel
    HAS_UNIFIED_PROXY = True
except ImportError:
    HAS_UNIFIED_PROXY = False


class WorkspacePanel(QWidget):
    """右侧工作区面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkspacePanel")
        self.setMinimumWidth(200)
        self.setMaximumWidth(380)
        self._workspace_path: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # 标题
        header = QHBoxLayout()
        title = QLabel("工作区")
        title.setObjectName("WorkspaceTitle")
        header.addWidget(title)
        header.addStretch()
        self.refresh_btn = QPushButton("↺")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#666;border:none;font-size:14px;}"
            "QPushButton:hover{color:#ccc;}"
        )
        self.refresh_btn.clicked.connect(self._refresh)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # 选项卡：文件 / 记忆
        self.tabs = QTabWidget()
        self.tabs.setObjectName("TabBar")
        self.tabs.tabBar().setObjectName("TabBar")
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:none;}"
            "QTabBar::tab{background:transparent;color:#666;padding:5px 12px;"
            "border:none;border-bottom:2px solid transparent;font-size:12px;}"
            "QTabBar::tab:selected{color:#e8e8e8;border-bottom-color:#5a5aff;}"
            "QTabBar::tab:hover{color:#bbb;}"
        )
        layout.addWidget(self.tabs, 1)

        # ── 文件选项卡 ──────────────────────────────────────────────
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(0, 4, 0, 0)
        file_layout.setSpacing(4)

        # 工作目录路径
        self.path_lbl = QLabel("（未设置工作目录）")
        self.path_lbl.setStyleSheet("color:#555; font-size:10px; padding:0 4px;")
        self.path_lbl.setWordWrap(True)
        file_layout.addWidget(self.path_lbl)

        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setObjectName("FileTree")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemClicked.connect(self._on_file_clicked)
        file_layout.addWidget(self.file_tree, 1)

        # 文件预览
        preview_lbl = QLabel("预览")
        preview_lbl.setStyleSheet("color:#555; font-size:10px; padding:2px 4px 0;")
        self.file_preview = QTextEdit()
        self.file_preview.setObjectName("FilePreview")
        self.file_preview.setReadOnly(True)
        self.file_preview.setMaximumHeight(200)
        self.file_preview.setPlaceholderText("点击文件预览内容…")
        file_layout.addWidget(preview_lbl)
        file_layout.addWidget(self.file_preview)
        self.tabs.addTab(file_tab, "文件")

        # ── 记忆选项卡 ──────────────────────────────────────────────
        mem_tab = QWidget()
        mem_layout = QVBoxLayout(mem_tab)
        mem_layout.setContentsMargins(0, 4, 0, 0)
        self.memory_view = QTextEdit()
        self.memory_view.setObjectName("MemoryView")
        self.memory_view.setReadOnly(True)
        self.memory_view.setPlaceholderText("Agent 记忆将在此显示…\n(~/.hermes/memory/)")
        mem_layout.addWidget(self.memory_view)
        self.tabs.addTab(mem_tab, "记忆")

        # ── 代理源选项卡 ──────────────────────────────────────────────
        if HAS_UNIFIED_PROXY:
            proxy_tab = QWidget()
            proxy_layout = QVBoxLayout(proxy_tab)
            proxy_layout.setContentsMargins(0, 4, 0, 0)
            self.proxy_panel = UnifiedProxyPanel()
            proxy_layout.addWidget(self.proxy_panel)
            self.tabs.addTab(proxy_tab, "代理源")

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def set_workspace(self, path: str):
        """设置并刷新工作目录"""
        self._workspace_path = path
        self.path_lbl.setText(path or "（未设置）")
        self._refresh_tree()

    def refresh_memory(self):
        """读取 ~/.hermes/memory/MEMORY.md 并展示"""
        memory_file = Path.home() / ".hermes" / "memory" / "MEMORY.md"
        if not memory_file.exists():
            # 尝试旧路径
            memory_file = Path.home() / ".hermes" / "MEMORY.md"
        if memory_file.exists():
            try:
                text = memory_file.read_text(encoding="utf-8")
                self.memory_view.setPlainText(text)
            except Exception as e:
                self.memory_view.setPlainText(f"读取失败: {e}")
        else:
            self.memory_view.setPlainText("未找到记忆文件\n~/.hermes/memory/MEMORY.md")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _refresh(self):
        self._refresh_tree()
        self.refresh_memory()

    def _refresh_tree(self):
        self.file_tree.clear()
        path = self._workspace_path
        if not path or not os.path.isdir(path):
            return
        root_item = QTreeWidgetItem(self.file_tree, [os.path.basename(path) or path])
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)
        self._populate_tree(root_item, path, depth=0)
        root_item.setExpanded(True)

    def _populate_tree(self, parent_item, dir_path: str, depth: int):
        if depth > 3:
            return
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name in ("__pycache__", "node_modules", ".git"):
                continue
            icon = "📁 " if entry.is_dir() else "📄 "
            item = QTreeWidgetItem(parent_item, [icon + entry.name])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
            if entry.is_dir():
                self._populate_tree(item, entry.path, depth + 1)

    def _on_file_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or os.path.isdir(path):
            return
        ext = os.path.splitext(path)[1].lower()
        text_exts = {
            ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
            ".md", ".txt", ".sh", ".bat", ".ps1", ".html", ".css",
            ".cfg", ".ini", ".env", ".csv",
        }
        if ext in text_exts:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(8000)
                self.file_preview.setPlainText(content)
            except Exception as e:
                self.file_preview.setPlainText(f"无法读取: {e}")
        else:
            self.file_preview.setPlainText(f"[二进制文件: {os.path.basename(path)}]")
