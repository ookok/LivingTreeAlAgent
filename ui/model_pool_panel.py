"""
模型池面板
显示 Ollama 中已注册和已加载的模型
"""

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QScrollArea, QProgressBar, QLineEdit,
)
from models.model_pool import ModelPool, PooledModel


class ModelPoolPanel(QWidget):
    """模型池面板"""

    model_selected = pyqtSignal(str)
    model_unloaded = pyqtSignal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._pool = None
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("WorkspacePanel")
        self.setStyleSheet("#WorkspacePanel{background:#111111;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # 标题
        title = QLabel("🧠 模型池")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#e8e8e8;padding:4px;")
        layout.addWidget(title)

        # 刷新按钮
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("↺ 刷新")
        refresh_btn.setStyleSheet(
            "QPushButton{background:#1e1e1e;color:#aaa;border:1px solid #333;"
            "border-radius:5px;padding:5px 12px;font-size:12px;}"
            "QPushButton:hover{background:#252525;color:#fff;}"
        )
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 已加载模型
        loaded_lbl = QLabel("已加载")
        loaded_lbl.setStyleSheet("color:#555;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;")
        layout.addWidget(loaded_lbl)

        self.loaded_list = QListWidget()
        self.loaded_list.setStyleSheet(
            "QListWidget{background:transparent;border:none;color:#ccc;outline:none;}"
            "QListWidget::item{padding:8px 10px;border-radius:6px;margin:2px 0;}"
            "QListWidget::item:hover{background:#1e1e1e;}"
            "QListWidget::item:selected{background:#252550;color:#fff;}"
        )
        self.loaded_list.itemDoubleClicked.connect(self._on_loaded_dblclick)
        layout.addWidget(self.loaded_list, 1)

        # 分隔
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#252525;margin:4px 0;")
        layout.addWidget(sep)

        # 所有模型
        all_lbl = QLabel("所有模型")
        all_lbl.setStyleSheet("color:#555;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;")
        layout.addWidget(all_lbl)

        self.all_list = QListWidget()
        self.all_list.setStyleSheet(
            "QListWidget{background:transparent;border:none;color:#bbb;outline:none;}"
            "QListWidget::item{padding:6px 10px;border-radius:5px;margin:1px 0;}"
            "QListWidget::item:hover{background:#1e1e1e;}"
            "QListWidget::item:selected{background:#252550;color:#fff;}"
        )
        self.all_list.itemDoubleClicked.connect(self._on_all_dblclick)
        layout.addWidget(self.all_list, 1)

        # 内存信息
        self.mem_label = QLabel()
        self.mem_label.setStyleSheet("color:#555;font-size:10px;padding:2px 4px;")
        layout.addWidget(self.mem_label)

    def set_pool(self, pool: ModelPool):
        self._pool = pool
        self._refresh()

    def _refresh(self):
        if not self._pool:
            return
        models = self._pool.refresh()
        self._update_ui(models)

    @pyqtSlot(list)
    def refresh_models(self, models):
        self._update_ui(models)

    def _update_ui(self, models: list[PooledModel]):
        self.loaded_list.clear()
        self.all_list.clear()

        for m in sorted(models, key=lambda x: x.name):
            # 标签
            if m.loaded:
                label = f"🟢 {m.name}"
            else:
                label = f"⚪ {m.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m.name)
            self.all_list.addItem(item)

            if m.loaded:
                loaded_item = QListWidgetItem(label)
                loaded_item.setData(Qt.ItemDataRole.UserRole, m.name)
                self.loaded_list.addItem(loaded_item)

        # 内存
        if self._pool:
            mem = self._pool.get_memory_usage()
            self.mem_label.setText(
                f"内存: {mem['used_gb']:.1f}GB / {mem['total_gb']:.1f}GB "
                f"({mem['percent']:.0f}%) | 已加载: {mem['loaded_models_count']}个模型"
            )

    def _on_loaded_dblclick(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        if self._pool:
            self._pool.unload(name)
            self._refresh()

    def _on_all_dblclick(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        if self._pool:
            self._pool.load(name)
            self._refresh()
            self.model_selected.emit(name)
