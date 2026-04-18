"""
模型市场面板
支持从 ModelScope / HuggingFace 浏览和下载 GGUF 模型
"""

from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QComboBox, QProgressBar, QScrollArea,
    QTabWidget,
)
from PyQt6.QtGui import QFont

from models.market import ModelMarketAPI, ModelEntry
from models.downloader import ModelDownloader, DownloadTask
from core.config import get_models_dir


class ModelMarketPanel(QWidget):
    """模型市场面板"""

    download_started = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = ModelMarketAPI()
        self.downloader = ModelDownloader(get_models_dir(), on_progress=self._on_progress)
        self._ms_models: list[ModelEntry] = []
        self._hf_models: list[ModelEntry] = []
        self._active_tasks: dict[str, DownloadTask] = {}
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("ModelMarketPanel")
        self.setStyleSheet(
            "#ModelMarketPanel{background:#111111;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # 标题
        title = QLabel("📦 模型市场")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#e8e8e8;padding:4px;")
        layout.addWidget(title)

        # 来源切换
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:none;}"
            "QTabBar::tab{background:transparent;color:#666;padding:5px 10px;"
            "border:none;font-size:12px;}"
            "QTabBar::tab:selected{color:#e8e8e8;border-bottom:2px solid #5a5aff;}"
        )
        layout.addWidget(self.tabs)

        # ModelScope 页
        ms_tab = QWidget()
        ms_lay = QVBoxLayout(ms_tab)
        ms_lay.setContentsMargins(0, 6, 0, 0)
        self.ms_search = QLineEdit()
        self.ms_search.setPlaceholderText("搜索 ModelScope 模型…")
        self.ms_search.setStyleSheet(
            "QLineEdit{background:#1e1e1e;border:1px solid #2a2a2a;"
            "border-radius:5px;padding:6px 10px;color:#ccc;}"
            "QLineEdit:focus{border-color:#5a5aff;}"
        )
        self.ms_search.returnPressed.connect(self._do_ms_search)
        ms_lay.addWidget(self.ms_search)
        self.ms_list = QListWidget()
        self.ms_list.setObjectName("FileTree")
        self.ms_list.itemDoubleClicked.connect(self._on_model_dbl)
        ms_lay.addWidget(self.ms_list, 1)
        ms_btn = QPushButton("搜索")
        ms_btn.setStyleSheet(
            "QPushButton{background:#252550;color:#aaa;border:1px solid #333;"
            "border-radius:5px;padding:6px;font-size:12px;}"
            "QPushButton:hover{background:#303070;}"
        )
        ms_btn.clicked.connect(self._do_ms_search)
        ms_lay.addWidget(ms_btn)
        self.tabs.addTab(ms_tab, "🤖 ModelScope")

        # HuggingFace 页
        hf_tab = QWidget()
        hf_lay = QVBoxLayout(hf_tab)
        hf_lay.setContentsMargins(0, 6, 0, 0)
        hf_btn = QPushButton("↺ 加载 HuggingFace GGUF 模型")
        hf_btn.setStyleSheet(
            "QPushButton{background:#1e1e1e;color:#aaa;border:1px solid #333;"
            "border-radius:5px;padding:6px 12px;font-size:12px;}"
            "QPushButton:hover{background:#252525;}"
        )
        hf_btn.clicked.connect(self._load_hf)
        hf_lay.addWidget(hf_btn)
        self.hf_list = QListWidget()
        self.hf_list.setObjectName("FileTree")
        self.hf_list.itemDoubleClicked.connect(self._on_model_dbl)
        hf_lay.addWidget(self.hf_list, 1)
        self.tabs.addTab(hf_tab, "🟡 HuggingFace")

        layout.addWidget(self.tabs)

        # 下载进度
        dl_lbl = QLabel("下载任务")
        dl_lbl.setStyleSheet(
            "color:#555;font-size:10px;text-transform:uppercase;"
            "letter-spacing:0.08em;padding:2px 4px;"
        )
        layout.addWidget(dl_lbl)
        self.dl_list = QListWidget()
        self.dl_list.setStyleSheet(
            "QListWidget{background:#151515;border:none;color:#aaa;border-radius:5px;}"
            "QListWidget::item{padding:6px 8px;border-radius:4px;}"
        )
        layout.addWidget(self.dl_list, 1)

        QTimer.singleShot(500, self._load_preset)

    def _load_preset(self):
        self.ms_list.clear()
        self._ms_models = self.api.list_modelscope_models()
        for m in self._ms_models:
            size_s = self._fmt_size(m.size)
            label = f"{m.org}/{m.name}  [{m.quantization}] {m.params}  {size_s}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.ms_list.addItem(item)

    def _do_ms_search(self):
        kw = self.ms_search.text().strip()
        if not kw:
            return
        self.ms_list.clear()
        self.ms_list.addItem("🔍 搜索中…")
        results = self.api.search_modelscope(kw)
        self.ms_list.clear()
        for m in results:
            item = QListWidgetItem(f"{m.org}/{m.name}  {m.description}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.ms_list.addItem(item)

    def _load_hf(self):
        self.hf_list.clear()
        self.hf_list.addItem("🔄 加载中…")
        QTimer.singleShot(50, self._do_hf_load)

    def _do_hf_load(self):
        models = self.api.list_hf_models()
        self.hf_list.clear()
        self._hf_models = models
        for m in models:
            size_s = self._fmt_size(m.size)
            item = QListWidgetItem(f"{m.org}/{m.name}  [{m.quantization}]  {size_s}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.hf_list.addItem(item)

    def _on_model_dbl(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, ModelEntry):
            return
        self._start_dl(entry)

    def _start_dl(self, entry: ModelEntry):
        from core.config import get_models_dir
        models_dir = get_models_dir()
        target = models_dir / entry.file_name
        url = entry.url
        if entry.source == "modelscope":
            url = f"https://modelscope.cn/models/{entry.repo_id}/resolve/master/{entry.file_name}"
        task = self.downloader.start_download(
            source=entry.source,
            repo_id=entry.repo_id,
            file_name=entry.file_name,
            url=url,
            target_path=str(target),
            expected_size=entry.size,
            sha256=entry.sha256,
        )
        self._active_tasks[task.id] = task
        dl_item = QListWidgetItem(f"⬇️ {entry.file_name} — 0%")
        dl_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self.dl_list.insertItem(0, dl_item)

    def _on_progress(self, task: DownloadTask):
        self._active_tasks[task.id] = task
        for i in range(self.dl_list.count()):
            it = self.dl_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == task.id:
                if task.status == "completed":
                    it.setText(f"✅ {task.file_name} — 完成！")
                elif task.status == "error":
                    it.setText(f"❌ {task.file_name} — {task.error[:40]}")
                else:
                    it.setText(f"⬇️ {task.file_name} — {task.progress_str}")
                break

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size == 0:
            return "?"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
