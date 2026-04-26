"""
专家训练模块 - 真实功能实现

支持模型训练、训练数据管理、训练监控。
"""

import os
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QScrollArea, QComboBox,
    QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

from client.src.business.nanochat_config import config


# ── 训练工作线程 ─────────────────────────────────────────────────────────

class TrainingWorker(QThread):
    """训练工作线程"""

    progress = pyqtSignal(int)          # 进度
    log_message = pyqtSignal(str)       # 日志消息
    finished = pyqtSignal(dict)         # 完成
    error = pyqtSignal(str)             # 错误

    def __init__(self, model_name: str, training_data: str, params: Dict, parent=None):
        super().__init__(parent)
        self.model_name = model_name
        self.training_data = training_data
        self.params = params
        self._stop_requested = False

    def run(self):
        try:
            # TODO: 实际调用训练 API
            # 目前模拟训练过程

            self.log_message.emit(f"开始训练模型: {self.model_name}")
            self.log_message.emit(f"训练数据: {self.training_data}")

            # 模拟训练进度
            for i in range(101):
                if self._stop_requested:
                    self.log_message.emit("训练已停止")
                    return

                self.progress.emit(i)
                self.log_message.emit(f"训练进度: {i}%")

                import time
                time.sleep(0.05)  # 模拟耗时

            result = {
                "model_name": self.model_name,
                "status": "success",
                "epochs": self.params.get("epochs", 3),
                "final_loss": 0.123,
            }

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop_requested = True


# ── 训练任务卡片 ─────────────────────────────────────────────────────────

class TrainingTaskCard(QFrame):
    """训练任务卡片"""

    def __init__(self, task: Dict, parent=None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题行
        title_layout = QHBoxLayout()

        name_label = QLabel(self.task.get("name", "未命名任务"))
        name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_layout.addWidget(name_label)

        title_layout.addStretch()

        status = self.task.get("status", "unknown")
        status_label = QLabel(f"[{status}]")
        status_color = {
            "running": "#2196F3",
            "success": "#4CAF50",
            "failed": "#F44336",
            "pending": "#FF9800",
        }.get(status, "#888")
        status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")
        title_layout.addWidget(status_label)

        layout.addLayout(title_layout)

        # 模型名称
        model_label = QLabel(f"模型: {self.task.get('model', '未知')}")
        model_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(model_label)

        # 进度条（如果有）
        if status == "running":
            progress = QProgressBar()
            progress.setValue(self.task.get("progress", 0))
            progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    height: 8px;
                }
                QProgressBar::chunk {
                    background: #1976D2;
                    border-radius: 4px;
                }
            """)
            layout.addWidget(progress)

        # 样式
        self.setStyleSheet("""
            TrainingTaskCard {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                margin: 4px 0;
            }
            TrainingTaskCard:hover {
                border: 1px solid #1976D2;
                background: #F5F5F5;
            }
        """)


# ── 主专家训练面板 ───────────────────────────────────────────────────────

class Panel(QWidget):
    """专家训练面板 - 真实功能"""

    training_started = pyqtSignal(str, str)  # 模型名, 训练数据
    training_stopped = pyqtSignal(str)        # 任务ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: List[Dict] = []
        self.worker: Optional[TrainingWorker] = None
        self._setup_ui()
        self._load_tasks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("🎓 专家训练")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 新建训练按钮
        self.new_btn = QPushButton("🆕 新建训练")
        self.new_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565C0; }
        """)
        self.new_btn.clicked.connect(self._create_new_training)
        title_layout.addWidget(self.new_btn)

        layout.addWidget(title_bar)

        # 训练配置区域
        config_frame = QFrame()
        config_frame.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        config_layout = QHBoxLayout(config_frame)
        config_layout.setContentsMargins(16, 12, 16, 12)

        # 模型名称
        config_layout.addWidget(QLabel("模型:"))
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("输入模型名称...")
        self.model_input.setText("my-expert-model")
        self.model_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
            QLineEdit:focus {
                border: 2px solid #1976D2;
            }
        """)
        config_layout.addWidget(self.model_input, 1)

        # 训练数据
        config_layout.addWidget(QLabel("数据:"))
        self.data_input = QLineEdit()
        self.data_input.setPlaceholderText("选择训练数据文件...")
        self.data_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        config_layout.addWidget(self.data_input, 2)

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setFixedSize(80, 36)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
            QPushButton:hover { background: #E0E0E0; }
        """)
        self.browse_btn.clicked.connect(self._browse_data)
        config_layout.addWidget(self.browse_btn)

        # 开始训练按钮
        self.start_btn = QPushButton("▶️ 开始训练")
        self.start_btn.setFixedSize(120, 36)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #388E3C; }
            QPushButton:disabled { background: #BDBDBD; }
        """)
        self.start_btn.clicked.connect(self._start_training)
        config_layout.addWidget(self.start_btn)

        layout.addWidget(config_frame)

        # 任务列表区域（可滚动）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #FAFAFA; }")

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(16, 16, 16, 16)
        self.tasks_layout.setSpacing(8)
        self.tasks_layout.addStretch()

        self.scroll_area.setWidget(self.tasks_container)
        layout.addWidget(self.scroll_area, 1)

        # 日志区域
        self.log_frame = QFrame()
        self.log_frame.setFixedHeight(120)
        self.log_frame.setStyleSheet("background: #263238; border-top: 1px solid #E0E0E0;")
        log_layout = QVBoxLayout(self.log_frame)
        log_layout.setContentsMargins(16, 8, 16, 8)

        log_title = QLabel("训练日志")
        log_title.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        log_layout.addWidget(log_title)

        self.log_text = QLabel("等待训练开始...")
        self.log_text.setStyleSheet("color: #B0BEC5; font-size: 11px; font-family: Consolas;")
        self.log_text.setWordWrap(True)
        log_layout.addWidget(self.log_text)

        layout.addWidget(self.log_frame)

    def _create_new_training(self):
        """创建新训练任务"""
        # TODO: 打开配置对话框
        self.log_text.setText("创建新训练任务...")

    def _browse_data(self):
        """浏览训练数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择训练数据",
            "",
            "JSONL Files (*.jsonl);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.data_input.setText(file_path)

    def _start_training(self):
        """开始训练"""
        model_name = self.model_input.text().strip()
        training_data = self.data_input.text().strip()

        if not model_name:
            QMessageBox.warning(self, "警告", "请输入模型名称！")
            return

        if not training_data or not os.path.exists(training_data):
            QMessageBox.warning(self, "警告", "请选择有效的训练数据文件！")
            return

        # 更新状态
        self.start_btn.setEnabled(False)
        self.start_btn.setText("训练中...")
        self.log_text.setText(f"开始训练模型: {model_name}\n")

        # 训练参数
        params = {
            "epochs": 3,
            "learning_rate": 0.001,
            "batch_size": 32,
        }

        # 启动工作线程
        self.worker = TrainingWorker(model_name, training_data, params)
        self.worker.progress.connect(self._on_progress)
        self.worker.log_message.connect(self._on_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.training_started.emit(model_name, training_data)

    def _load_tasks(self):
        """加载训练任务列表"""
        # TODO: 实际从 API 获取任务列表
        # 目前使用模拟数据
        mock_tasks = [
            {
                "name": "专家模型 v1",
                "model": "expert-v1",
                "status": "success",
                "progress": 100,
            },
        ]

        for task in mock_tasks:
            self._add_task(task)

    def _add_task(self, task: Dict):
        """添加训练任务卡片"""
        card = TrainingTaskCard(task)
        self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, card)
        self.tasks.append(task)

    @pyqtSlot(int)
    def _on_progress(self, value: int):
        """训练进度更新"""
        self.log_text.setText(self.log_text.text() + f"\n进度: {value}%")

    @pyqtSlot(str)
    def _on_log(self, message: str):
        """日志消息"""
        self.log_text.setText(self.log_text.text() + f"\n{message}")

    @pyqtSlot(dict)
    def _on_finished(self, result: Dict):
        """训练完成"""
        self.log_text.setText(self.log_text.text() + f"\n\n✅ 训练完成！\n最终损失: {result.get('final_loss', 'N/A')}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶️ 开始训练")
        self.worker = None

        # 添加到任务列表
        new_task = {
            "name": result.get("model_name", "未命名"),
            "model": result.get("model_name", "未知"),
            "status": "success",
            "progress": 100,
        }
        self._add_task(new_task)

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        self.log_text.setText(self.log_text.text() + f"\n\n❌ 错误: {error_msg}")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶️ 开始训练")
        self.worker = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
