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

from core.unified_downloader import get_download_center, DownloadTask, SourceType
from client.src.business.config import get_models_dir


class ModelMarketEntry:
    """模型市场条目"""
    def __init__(self, org, name, quantization, params, size, url, source, repo_id, file_name):
        self.org = org
        self.name = name
        self.quantization = quantization
        self.params = params
        self.size = size
        self.url = url
        self.source = source
        self.repo_id = repo_id
        self.file_name = file_name


class ModelMarketPanel(QWidget):
    """模型市场面板"""

    download_started = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.download_center = get_download_center()
        self._ms_models: list[ModelMarketEntry] = []
        self._hf_models: list[ModelMarketEntry] = []
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
        # 硬编码的ModelScope模型列表
        self._ms_models = [
            ModelMarketEntry(
                org="LLM-Research",
                name="Qwen2.5-0.5B-Instruct-GGUF",
                quantization="q4_k_m",
                params="0.5B",
                size=1024 * 1024 * 1024,  # 1GB
                url="",
                source="modelscope",
                repo_id="LLM-Research/Qwen2.5-0.5B-Instruct-GGUF",
                file_name="qwen2.5-0_5b-instruct-q4_k_m.gguf"
            ),
            ModelMarketEntry(
                org="LLM-Research",
                name="Qwen2.5-1.5B-Instruct-GGUF",
                quantization="q4_k_m",
                params="1.5B",
                size=2890 * 1024 * 1024,  # 2.89GB
                url="",
                source="modelscope",
                repo_id="LLM-Research/Qwen2.5-1.5B-Instruct-GGUF",
                file_name="qwen2.5-1_5b-instruct-q4_k_m.gguf"
            ),
            ModelMarketEntry(
                org="LLM-Research",
                name="Qwen2.5-3B-Instruct-GGUF",
                quantization="q4_k_m",
                params="3B",
                size=6100 * 1024 * 1024,  # 6.1GB
                url="",
                source="modelscope",
                repo_id="LLM-Research/Qwen2.5-3B-Instruct-GGUF",
                file_name="qwen2.5-3b-instruct-q4_k_m.gguf"
            ),
        ]
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
        # 简单的本地搜索
        results = [m for m in self._ms_models if kw.lower() in f"{m.org} {m.name}".lower()]
        for m in results:
            size_s = self._fmt_size(m.size)
            item = QListWidgetItem(f"{m.org}/{m.name}  [{m.quantization}] {m.params}  {size_s}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.ms_list.addItem(item)

    def _load_hf(self):
        self.hf_list.clear()
        # 硬编码的HuggingFace模型列表
        self._hf_models = [
            ModelMarketEntry(
                org="meta-llama",
                name="Llama-3.2-1B-Instruct-GGUF",
                quantization="q4_k_m",
                params="1B",
                size=1860 * 1024 * 1024,  # 1.86GB
                url="",
                source="huggingface",
                repo_id="meta-llama/Llama-3.2-1B-Instruct-GGUF",
                file_name="llama-3.2-1b-instruct-q4_k_m.gguf"
            ),
            ModelMarketEntry(
                org="meta-llama",
                name="Llama-3.2-3B-Instruct-GGUF",
                quantization="q4_k_m",
                params="3B",
                size=5590 * 1024 * 1024,  # 5.59GB
                url="",
                source="huggingface",
                repo_id="meta-llama/Llama-3.2-3B-Instruct-GGUF",
                file_name="llama-3.2-3b-instruct-q4_k_m.gguf"
            ),
        ]
        for m in self._hf_models:
            size_s = self._fmt_size(m.size)
            item = QListWidgetItem(f"{m.org}/{m.name}  [{m.quantization}]  {size_s}")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self.hf_list.addItem(item)

    def _do_hf_load(self):
        # 已在_load_hf中实现
        pass

    def _on_model_dbl(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, ModelMarketEntry):
            return
        self._start_dl(entry)

    def _start_dl(self, entry: ModelMarketEntry):
        from client.src.business.config import get_models_dir
        models_dir = get_models_dir()
        target = models_dir / entry.file_name
        
        if entry.source == "modelscope":
            url = f"https://modelscope.cn/models/{entry.repo_id}/resolve/master/{entry.file_name}"
            source_type = SourceType.MODELSCOPE
        else:
            url = f"https://huggingface.co/{entry.repo_id}/resolve/main/{entry.file_name}"
            source_type = SourceType.HUGGINGFACE
        
        def on_progress(task):
            """进度回调"""
            self._active_tasks[task.id] = task
            
            # 捕获关键数据，避免后台线程访问 UI 对象
            task_id = task.id
            file_name = task.filename
            status = task.status
            error = task.error
            progress = task.progress
            
            def update_ui():
                for i in range(self.dl_list.count()):
                    it = self.dl_list.item(i)
                    if it.data(Qt.ItemDataRole.UserRole) == task_id:
                        if status == "completed":
                            it.setText(f"✅ {file_name} — 完成！")
                        elif status == "failed":
                            it.setText(f"❌ {file_name} — {error[:40] if error else '未知错误'}")
                        else:
                            it.setText(f"⬇️ {file_name} — {progress:.1f}%")
                        break
            
            # 确保 UI 更新在主线程执行
            QTimer.singleShot(0, update_ui)
        
        task = self.download_center.create_task(
            url=url,
            save_path=target,
            source=source_type,
            source_info=entry.repo_id,
            expected_size=entry.size,
            progress_callback=on_progress
        )
        
        self.download_center.start(task.id)
        self._active_tasks[task.id] = task
        dl_item = QListWidgetItem(f"⬇️ {entry.file_name} — 0%")
        dl_item.setData(Qt.ItemDataRole.UserRole, task.id)
        self.dl_list.insertItem(0, dl_item)

    def _on_progress(self, task: DownloadTask):
        """进度回调（已在_start_dl中实现）"""
        pass

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size == 0:
            return "?"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
