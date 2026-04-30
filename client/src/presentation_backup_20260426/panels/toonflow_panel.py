"""
Toonflow 管理面板

PyQt6 实现，提供 Toonflow 短剧引擎的图形化管理界面
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QComboBox, QSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QCheckBox, QFileDialog,
    QMessageBox, QListWidget, QListWidgetItem, QTextBrowser,
    QStatusBar, QApplication
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import QObject, pyqtBoundSignal

logger = logging.getLogger(__name__)


# ============= 工作线程 =============

class ToonflowWorker(QThread):
    """Toonflow 后台工作线程"""

    # 信号定义
    status_updated = pyqtSignal(str)  # 状态更新
    progress_updated = pyqtSignal(float, str)  # 进度, 步骤描述
    task_completed = pyqtSignal(dict)  # 任务完成
    error_occurred = pyqtSignal(str)  # 错误

    def __init__(self, runner, client, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.client = client
        self._running = False
        self._task = None

    def run(self):
        self._running = True

    def stop(self):
        self._running = False


# ============= 主面板 =============

class ToonflowPanel(QWidget):
    """
    Toonflow 短剧引擎管理面板

    功能：
    - 服务启动/停止
    - 项目管理
    - 小说/剧本导入
    - 触发生成流水线
    - 进度监控
    """

    # 信号定义
    service_status_changed = pyqtSignal(bool)  # 服务状态变化
    task_progress_updated = pyqtSignal(float, str)  # 进度更新

    def __init__(self, runner=None, client=None, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.client = client
        self._tasks = {}
        self._projects = {}
        self._current_task_id = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_task_status)
        self._setup_ui()
        self._init_components()

    def set_runner(self, runner):
        """设置 Runner 实例"""
        self.runner = runner
        self._update_service_status()

    def set_client(self, client):
        """设置 Client 实例"""
        self.client = client
        self._update_service_status()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🎬 Toonflow 短剧引擎")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("⚡ 未连接")
        self.status_label.setStyleSheet("padding: 5px 10px; background: #fff3e0; border-radius: 4px;")
        status_layout.addWidget(self.status_label)

        self.pid_label = QLabel("PID: -")
        status_layout.addWidget(self.pid_label)

        status_layout.addStretch()

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.clicked.connect(self._update_service_status)
        status_layout.addWidget(self.refresh_btn)

        layout.addLayout(status_layout)

        # Tab 页面
        tabs = QTabWidget()

        # Tab 1: 服务控制
        tabs.addTab(self._create_service_tab(), "⚙️ 服务控制")

        # Tab 2: 创建项目
        tabs.addTab(self._create_project_tab(), "📝 创建项目")

        # Tab 3: 生成流水线
        tabs.addTab(self._create_pipeline_tab(), "🎬 生成流水线")

        # Tab 4: 项目管理
        tabs.addTab(self._create_projects_tab(), "📁 项目列表")

        # Tab 5: 设置
        tabs.addTab(self._create_settings_tab(), "⚡ 设置")

        layout.addWidget(tabs)

    def _create_service_tab(self) -> QWidget:
        """创建服务控制页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 环境检测
        env_group = QGroupBox("环境检测")
        env_layout = QGridLayout()

        self.node_status = QLabel("❌")
        env_layout.addWidget(QLabel("Node.js:"), 0, 0)
        env_layout.addWidget(self.node_status, 0, 1)
        self.node_version_label = QLabel("")
        env_layout.addWidget(self.node_version_label, 0, 2)

        self.yarn_status = QLabel("❌")
        env_layout.addWidget(QLabel("Yarn:"), 1, 0)
        env_layout.addWidget(self.yarn_status, 1, 1)
        self.yarn_version_label = QLabel("")
        env_layout.addWidget(self.yarn_version_label, 1, 2)

        self.toonflow_status = QLabel("❌")
        env_layout.addWidget(QLabel("Toonflow:"), 2, 0)
        env_layout.addWidget(self.toonflow_status, 2, 1)
        self.toonflow_dir_label = QLabel("")
        env_layout.addWidget(self.toonflow_dir_label, 2, 2)

        env_layout.addWidget(QLabel("API 端口:"), 3, 0)
        self.port_label = QLabel("60001")
        env_layout.addWidget(self.port_label, 3, 1)

        env_group.setLayout(env_layout)
        layout.addWidget(env_group)

        # 服务控制
        control_group = QGroupBox("服务控制")
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 启动服务")
        self.start_btn.setStyleSheet("""
            QPushButton { background: #4CAF50; color: white; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.start_btn.clicked.connect(self._start_service)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ 停止服务")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton { background: #f44336; color: white; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #d32f2f; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.stop_btn.clicked.connect(self._stop_service)
        control_layout.addWidget(self.stop_btn)

        self.restart_btn = QPushButton("🔄 重启")
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(self._restart_service)
        control_layout.addWidget(self.restart_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 安装按钮
        install_group = QGroupBox("安装")
        install_layout = QHBoxLayout()

        self.install_btn = QPushButton("📥 安装 Toonflow")
        self.install_btn.clicked.connect(self._install_toonflow)
        install_layout.addWidget(self.install_btn)

        install_group.setLayout(install_layout)
        layout.addWidget(install_group)

        # 日志输出
        log_group = QGroupBox("服务日志")
        log_layout = QVBoxLayout()

        self.log_browser = QTextBrowser()
        self.log_browser.setMaximumHeight(150)
        self.log_browser.setStyleSheet("font-family: monospace; font-size: 10pt;")
        log_layout.addWidget(self.log_browser)

        self.clear_log_btn = QPushButton("清除日志")
        self.clear_log_btn.clicked.connect(lambda: self.log_browser.clear())
        log_layout.addWidget(self.clear_log_btn)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

        return widget

    def _create_project_tab(self) -> QWidget:
        """创建项目创建页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 小说输入
        input_group = QGroupBox("小说/剧本内容")
        input_layout = QGridLayout()

        input_layout.addWidget(QLabel("标题:"), 0, 0)
        self.novel_title_edit = QLineEdit()
        self.novel_title_edit.setPlaceholderText("输入短剧标题...")
        input_layout.addWidget(self.novel_title_edit, 0, 1, 1, 2)

        input_layout.addWidget(QLabel("类型:"), 1, 0)
        self.genre_combo = QComboBox()
        self.genre_combo.addItems(["短剧 (short_drama)", "网文 (web_novel)", "营销 (marketing)"])
        input_layout.addWidget(self.genre_combo, 1, 1, 1, 2)

        input_layout.addWidget(QLabel("风格:"), 2, 0)
        self.style_combo = QComboBox()
        self.style_combo.addItems(["现代 (modern)", "古装 (ancient)", "科幻 (sci-fi)", "卡通 (cartoon)"])
        input_layout.addWidget(self.style_combo, 2, 1, 1, 2)

        input_layout.addWidget(QLabel("时长(秒):"), 3, 0)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 300)
        self.duration_spin.setValue(60)
        input_layout.addWidget(self.duration_spin, 3, 1)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 剧本内容
        content_group = QGroupBox("剧本内容")
        content_layout = QVBoxLayout()

        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText(
            "在这里输入或粘贴剧本内容...\n\n"
            "格式示例:\n"
            "第一场: 清晨 办公室\n"
            "人物: 张三(男,25岁), 李四(女,24岁)\n"
            "张三走进办公室，看到李四已经在工位上了。\n"
            "张: '这么早？'\n"
            "李: '习惯了，早起的鸟儿有虫吃。'"
        )
        self.script_edit.setMinimumHeight(200)
        content_layout.addWidget(self.script_edit)

        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        # 创建按钮
        self.create_project_btn = QPushButton("📋 创建项目并导入剧本")
        self.create_project_btn.setStyleSheet("""
            QPushButton { background: #2196F3; color: white; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #1976D2; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.create_project_btn.clicked.connect(self._create_project)
        layout.addWidget(self.create_project_btn)

        layout.addStretch()

        return widget

    def _create_pipeline_tab(self) -> QWidget:
        """创建生成流水线页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 流水线步骤
        steps_group = QGroupBox("流水线状态")
        steps_layout = QVBoxLayout()

        self.step_labels = {}
        steps = [
            ("novel_import", "📖 1. 小说导入"),
            ("character_extract", "👤 2. 角色提取"),
            ("script_convert", "📝 3. 剧本转换"),
            ("storyboard_gen", "🎞️ 4. 分镜生成"),
            ("image_gen", "🖼️ 5. 图像生成"),
            ("video_compose", "🎬 6. 视频合成"),
        ]

        for step_id, step_label in steps:
            step_layout = QHBoxLayout()
            label = QLabel(step_label)
            label.setStyleSheet("padding: 5px;")
            status = QLabel("⏳")
            status.setObjectName(f"step_{step_id}")
            self.step_labels[step_id] = (label, status)
            step_layout.addWidget(label)
            step_layout.addWidget(status)
            step_layout.addStretch()
            steps_layout.addLayout(step_layout)

        steps_group.setLayout(steps_layout)
        layout.addWidget(steps_group)

        # 进度条
        self.pipeline_progress = QProgressBar()
        self.pipeline_progress.setRange(0, 100)
        self.pipeline_progress.setValue(0)
        layout.addWidget(self.pipeline_progress)

        # 当前状态
        self.pipeline_status_label = QLabel("等待开始...")
        layout.addWidget(self.pipeline_status_label)

        # 控制按钮
        control_layout = QHBoxLayout()

        self.start_pipeline_btn = QPushButton("🎬 开始生成")
        self.start_pipeline_btn.setStyleSheet("""
            QPushButton { background: #4CAF50; color: white; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.start_pipeline_btn.clicked.connect(self._start_pipeline)
        control_layout.addWidget(self.start_pipeline_btn)

        self.cancel_pipeline_btn = QPushButton("❌ 取消")
        self.cancel_pipeline_btn.setEnabled(False)
        self.cancel_pipeline_btn.clicked.connect(self._cancel_pipeline)
        control_layout.addWidget(self.cancel_pipeline_btn)

        self.download_btn = QPushButton("📥 下载结果")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_result)
        control_layout.addWidget(self.download_btn)

        layout.addLayout(control_layout)

        # 输出路径
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("保存目录:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText(os.path.expanduser("~/.hermes-desktop/videos"))
        output_layout.addWidget(self.output_dir_edit)
        self.browse_output_btn = QPushButton("浏览...")
        self.browse_output_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(self.browse_output_btn)
        layout.addLayout(output_layout)

        layout.addStretch()

        return widget

    def _create_projects_tab(self) -> QWidget:
        """创建项目管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.refresh_projects_btn = QPushButton("🔄 刷新列表")
        self.refresh_projects_btn.clicked.connect(self._refresh_projects)
        toolbar_layout.addWidget(self.refresh_projects_btn)

        toolbar_layout.addStretch()

        self.delete_project_btn = QPushButton("🗑️ 删除选中")
        self.delete_project_btn.clicked.connect(self._delete_selected_project)
        toolbar_layout.addWidget(self.delete_project_btn)

        layout.addLayout(toolbar_layout)

        # 项目列表
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels(["ID", "标题", "状态", "任务数", "创建时间"])
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.horizontalHeader().setStretchLastSection(True)
        self.projects_table.itemSelectionChanged.connect(self._on_project_selected)
        layout.addWidget(self.projects_table)

        # 项目详情
        detail_group = QGroupBox("项目详情")
        detail_layout = QGridLayout()

        detail_layout.addWidget(QLabel("选中项目:"), 0, 0)
        self.selected_project_label = QLabel("-")
        detail_layout.addWidget(self.selected_project_label, 0, 1)

        self.open_project_btn = QPushButton("📂 在 Toonflow 中打开")
        self.open_project_btn.setEnabled(False)
        self.open_project_btn.clicked.connect(self._open_in_toonflow)
        detail_layout.addWidget(self.open_project_btn, 1, 0, 1, 2)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模型设置
        model_group = QGroupBox("AI 模型配置")
        model_layout = QGridLayout()

        model_layout.addWidget(QLabel("视频模型:"), 0, 0)
        self.video_model_combo = QComboBox()
        self.video_model_combo.addItems(["seedance2", "kling", "pika", "runway", "sora"])
        model_layout.addWidget(self.video_model_combo, 0, 1)

        model_layout.addWidget(QLabel("图像模型:"), 1, 0)
        self.image_model_combo = QComboBox()
        self.image_model_combo.addItems(["sd15", "sd21", "comfyui", "dalle3"])
        model_layout.addWidget(self.image_model_combo, 1, 1)

        model_layout.addWidget(QLabel("LLM 端点:"), 2, 0)
        self.llm_endpoint_edit = QLineEdit()
        self.llm_endpoint_edit.setText("http://localhost:8080/v1")
        model_layout.addWidget(self.llm_endpoint_edit, 2, 1, 1, 2)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # 服务设置
        service_group = QGroupBox("服务设置")
        service_layout = QGridLayout()

        service_layout.addWidget(QLabel("API 端口:"), 0, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(60001)
        service_layout.addWidget(self.port_spin, 0, 1)

        service_layout.addWidget(QLabel("轮询间隔(秒):"), 1, 0)
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 60)
        self.poll_interval_spin.setValue(5)
        service_layout.addWidget(self.poll_interval_spin, 1, 1)

        service_group.setLayout(service_layout)
        layout.addWidget(service_group)

        # 关于
        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout()
        about_layout.addWidget(QLabel("Toonflow 短剧引擎 v1.0"))
        about_layout.addWidget(QLabel("AI 短剧全流程生成: 小说→剧本→分镜→视频"))
        about_layout.addWidget(QLabel("基于 Node.js + Electron + Vue"))
        about_layout.addWidget(QLabel("项目地址: github.com/HBAI-Ltd/Toonflow-app"))
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)

        layout.addStretch()

        return widget

    # ── 初始化 ─────────────────────────────────────────────────────

    def _init_components(self):
        """初始化组件"""
        # 设置默认输出目录
        output_dir = os.path.expanduser("~/.hermes-desktop/videos")
        self.output_dir_edit.setText(output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 异步检测环境
        asyncio.ensure_future(self._check_environment())

    async def _check_environment(self):
        """检测运行环境"""
        if not self.runner:
            try:
                from .business.toonflow_runner import get_toonflow_runner
                self.runner = get_toonflow_runner()
            except Exception as e:
                logger.error(f"Failed to get runner: {e}")
                return

        try:
            status = await self.runner.check_environment()

            # 更新 UI
            self.node_status.setText("✅" if status["node"] else "❌")
            self.node_version_label.setText(status.get("node_version", ""))
            self.yarn_status.setText("✅" if status["yarn"] else "❌")
            self.yarn_version_label.setText(status.get("yarn_version", ""))
            self.toonflow_status.setText("✅" if status["toonflow"] else "❌")
            self.toonflow_dir_label.setText(
                os.path.basename(status.get("toonflow_dir", "")) if status.get("toonflow_dir") else ""
            )
            self.port_label.setText(str(status.get("port", 60001)))

            # 更新按钮状态
            self.install_btn.setEnabled(not status["toonflow"])

            # 日志
            for issue in status.get("issues", []):
                self._log(f"⚠️ {issue}")

            self._log("环境检测完成")

        except Exception as e:
            self._log(f"环境检测失败: {e}")

    def _update_service_status(self):
        """更新服务状态"""
        if self.runner and self.runner.is_running:
            self.status_label.setText("✅ 运行中")
            self.status_label.setStyleSheet("padding: 5px 10px; background: #c8e6c9; border-radius: 4px;")
            self.pid_label.setText(f"PID: {self.runner.pid}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            self.start_pipeline_btn.setEnabled(True)
        else:
            self.status_label.setText("⏹️ 已停止")
            self.status_label.setStyleSheet("padding: 5px 10px; background: #ffcdd2; border-radius: 4px;")
            self.pid_label.setText("PID: -")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)
            self.start_pipeline_btn.setEnabled(False)

    def _log(self, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_browser.append(f"[{timestamp}] {message}")

    # ── 服务控制 ─────────────────────────────────────────────────────

    async def _do_start_service(self):
        """执行启动服务"""
        if not self.runner:
            self._log("❌ Runner 未初始化")
            return False

        self._log("🚀 正在启动 Toonflow 服务...")
        self.start_btn.setEnabled(False)

        success = await self.runner.start(timeout=60)

        if success:
            self._log("✅ 服务启动成功")
            self._update_service_status()
            self.service_status_changed.emit(True)

            # 初始化客户端
            if not self.client:
                try:
                    from .business.toonflow_client import get_toonflow_client
                    from .business.toonflow_client import ToonflowConfig
                    config = ToonflowConfig(port=self.runner.config.port)
                    self.client = get_toonflow_client(config)
                    await self.client.connect()
                except Exception as e:
                    self._log(f"⚠️ 客户端连接失败: {e}")
        else:
            self._log("❌ 服务启动失败")

        self._update_service_status()
        return success

    def _start_service(self):
        """启动服务（同步包装）"""
        asyncio.ensure_future(self._do_start_service())

    async def _do_stop_service(self):
        """执行停止服务"""
        if not self.runner:
            return

        self._log("⏹️ 正在停止服务...")
        await self.runner.stop()
        self._log("✅ 服务已停止")
        self._update_service_status()
        self.service_status_changed.emit(False)

    def _stop_service(self):
        """停止服务"""
        asyncio.ensure_future(self._do_stop_service())

    def _restart_service(self):
        """重启服务"""
        asyncio.ensure_future(self._do_restart_service())

    async def _do_restart_service(self):
        """执行重启服务"""
        await self._do_stop_service()
        await asyncio.sleep(1)
        await self._do_start_service()

    async def _do_install(self):
        """执行安装"""
        if not self.runner:
            try:
                from .business.toonflow_runner import get_toonflow_runner
                self.runner = get_toonflow_runner()
            except Exception as e:
                self._log(f"❌ 获取 Runner 失败: {e}")
                return

        self._log("📥 开始安装 Toonflow...")
        self.install_btn.setEnabled(False)

        success = await self.runner.install(verbose=True)

        if success:
            self._log("✅ 安装完成")
        else:
            self._log("❌ 安装失败")

        self.install_btn.setEnabled(True)
        await self._check_environment()

    def _install_toonflow(self):
        """安装 Toonflow"""
        asyncio.ensure_future(self._do_install())

    # ── 项目管理 ─────────────────────────────────────────────────────

    async def _do_create_project(self):
        """创建项目"""
        title = self.novel_title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入标题")
            return

        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "错误", "请先启动 Toonflow 服务")
            return

        script_content = self.script_edit.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, "提示", "请输入剧本内容")
            return

        # 获取选项
        genre_map = {"短剧": "short_drama", "网文": "web_novel", "营销": "marketing"}
        style_map = {"现代": "modern", "古装": "ancient", "科幻": "sci-fi", "卡通": "cartoon"}

        genre_text = self.genre_combo.currentText().split(" ")[0]
        style_text = self.style_combo.currentText().split(" ")[0]

        self._log(f"📝 创建项目: {title}")

        try:
            from .business.toonflow_client import NovelContent

            novel = NovelContent(
                title=title,
                content=script_content,
                genre=genre_map.get(genre_text, "short_drama"),
                target_duration=self.duration_spin.value(),
                style=style_map.get(style_text, "modern"),
            )

            # 创建项目
            project = await self.client.create_project(title)
            self._log(f"✅ 项目创建成功: {project.project_id}")

            # 导入小说
            await self.client.import_novel(project.project_id, novel)
            self._log(f"✅ 剧本已导入")

            QMessageBox.information(self, "成功", f"项目创建成功！\nID: {project.project_id}")

            # 刷新项目列表
            await self._do_refresh_projects()

        except Exception as e:
            self._log(f"❌ 创建失败: {e}")
            QMessageBox.critical(self, "错误", f"创建失败: {e}")

    def _create_project(self):
        """创建项目（异步）"""
        asyncio.ensure_future(self._do_create_project())

    async def _do_refresh_projects(self):
        """刷新项目列表"""
        if not self.client or not self.client.is_connected:
            return

        try:
            projects = await self.client.list_projects()
            self._projects = {p.project_id: p for p in projects}

            # 更新表格
            self.projects_table.setRowCount(len(projects))
            for i, project in enumerate(projects):
                self.projects_table.setItem(i, 0, QTableWidgetItem(project.project_id[:8] + "..."))
                self.projects_table.setItem(i, 1, QTableWidgetItem(project.title))
                self.projects_table.setItem(i, 2, QTableWidgetItem(project.status))
                self.projects_table.setItem(i, 3, QTableWidgetItem(str(project.task_count)))
                self.projects_table.setItem(i, 4, QTableWidgetItem(
                    project.created_at.strftime("%Y-%m-%d %H:%M")
                ))

            self._log(f"已刷新 {len(projects)} 个项目")

        except Exception as e:
            self._log(f"刷新失败: {e}")

    def _refresh_projects(self):
        """刷新项目列表"""
        asyncio.ensure_future(self._do_refresh_projects())

    def _on_project_selected(self):
        """项目选中事件"""
        row = self.projects_table.currentRow()
        if row >= 0:
            project_id = self.projects_table.item(row, 0).text().replace("...", "")
            for pid, project in self._projects.items():
                if pid.startswith(project_id):
                    self.selected_project_label.setText(project.title)
                    self.open_project_btn.setEnabled(True)
                    self._current_project_id = pid
                    return
        self.selected_project_label.setText("-")
        self.open_project_btn.setEnabled(False)

    async def _do_delete_project(self, project_id: str):
        """删除项目"""
        if not self.client:
            return

        try:
            await self.client.delete_project(project_id)
            self._log(f"✅ 项目已删除: {project_id[:8]}...")
            await self._do_refresh_projects()
        except Exception as e:
            self._log(f"❌ 删除失败: {e}")

    def _delete_selected_project(self):
        """删除选中项目"""
        if hasattr(self, "_current_project_id"):
            reply = QMessageBox.question(
                self, "确认", "确定要删除这个项目吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                asyncio.ensure_future(self._do_delete_project(self._current_project_id))

    def _open_in_toonflow(self):
        """在 Toonflow 中打开"""
        if hasattr(self, "_current_project_id"):
            import webbrowser
            url = f"http://localhost:{self.runner.config.port}/project/{self._current_project_id}"
            webbrowser.open(url)

    # ── 流水线 ─────────────────────────────────────────────────────

    async def _do_start_pipeline(self):
        """启动生成流水线"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "错误", "请先启动服务并选择项目")
            return

        if not hasattr(self, "_current_project_id"):
            QMessageBox.warning(self, "提示", "请先在项目管理中选择一个项目")
            return

        project_id = self._current_project_id

        # 重置步骤显示
        for step_id, (label, status) in self.step_labels.items():
            status.setText("⏳")
            label.setStyleSheet("padding: 5px; background: transparent;")

        self._log(f"🎬 开始生成: {project_id[:8]}...")

        try:
            # 启动生产
            task = await self.client.start_production(project_id)
            self._current_task_id = task.task_id
            self._tasks[task.task_id] = task

            self._log(f"✅ 任务已创建: {task.task_id}")

            # 启用取消按钮
            self.start_pipeline_btn.setEnabled(False)
            self.cancel_pipeline_btn.setEnabled(True)

            # 开始轮询
            self._poll_timer.start(2000)

            # 更新任务
            await self._poll_task_status()

        except Exception as e:
            self._log(f"❌ 启动失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")

    def _start_pipeline(self):
        """启动流水线"""
        asyncio.ensure_future(self._do_start_pipeline())

    async def _poll_task_status(self):
        """轮询任务状态"""
        if not self._current_task_id or not self.client:
            return

        try:
            task = await self.client.get_task_status(self._current_task_id)

            # 更新进度
            progress = int(task.progress * 100)
            self.pipeline_progress.setValue(progress)

            # 更新当前步骤
            if task.current_step:
                step_id = task.current_step.value
                if step_id in self.step_labels:
                    label, status = self.step_labels[step_id]
                    status.setText("🔄")
                    label.setStyleSheet("padding: 5px; background: #fff9c4;")

                self.pipeline_status_label.setText(f"正在: {task.current_step.value}")

            # 检查完成
            if task.status.value in ("completed", "failed", "cancelled"):
                self._poll_timer.stop()
                self.start_pipeline_btn.setEnabled(True)
                self.cancel_pipeline_btn.setEnabled(False)

                if task.status.value == "completed":
                    self._log("🎉 生成完成！")
                    self.download_btn.setEnabled(True)
                    # 更新所有步骤
                    for step_id, (label, status) in self.step_labels.items():
                        status.setText("✅")
                        label.setStyleSheet("padding: 5px; background: #c8e6c9;")
                else:
                    self._log(f"❌ 生成失败: {task.error}")

        except Exception as e:
            self._log(f"轮询错误: {e}")

    def _cancel_pipeline(self):
        """取消流水线"""
        if self._current_task_id and self.client:
            asyncio.ensure_future(self._cancel_task(self._current_task_id))

    async def _cancel_task(self, task_id: str):
        """取消任务"""
        try:
            await self.client.cancel_task(task_id)
            self._log(f"已取消任务: {task_id[:8]}...")
            self._poll_timer.stop()
            self.start_pipeline_btn.setEnabled(True)
            self.cancel_pipeline_btn.setEnabled(False)
        except Exception as e:
            self._log(f"取消失败: {e}")

    def _browse_output_dir(self):
        """浏览输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.output_dir_edit.setText(path)

    async def _do_download_result(self):
        """下载结果"""
        if not self._current_task_id or not self.client:
            return

        save_dir = self.output_dir_edit.text()
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        self._log(f"📥 正在下载结果到: {save_dir}")

        try:
            save_path = await self.client.download_result(self._current_task_id, save_dir)
            self._log(f"✅ 已保存: {save_path}")
            QMessageBox.information(self, "成功", f"视频已保存:\n{save_path}")
        except Exception as e:
            self._log(f"❌ 下载失败: {e}")
            QMessageBox.critical(self, "错误", f"下载失败: {e}")

    def _download_result(self):
        """下载结果"""
        asyncio.ensure_future(self._do_download_result())
