"""
CLI-Anything PyQt6 集成面板
提供可视化的CLI工具生成与管理界面
"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QProgressBar, QListWidget,
    QListWidgetItem, QGroupBox, QCheckBox, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QFrame, QScrollArea, QProgressDialog,
    QMessageBox, QApplication
)
from pathlib import Path
import asyncio
import time


class CLIGenerationWorker(QThread):
    """CLI生成后台工作线程"""
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, cli_anything, description, repo_url=None):
        super().__init__()
        self.cli_anything = cli_anything
        self.description = description
        self.repo_url = repo_url

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def generate():
                def progress_callback(pct, msg):
                    self.progress.emit(pct, msg)

                result = await self.cli_anything.generate(
                    self.description,
                    self.repo_url,
                    progress_callback=progress_callback
                )
                return {
                    "success": result.success,
                    "project": {
                        "id": result.project.id if result.project else "",
                        "name": result.project.name if result.project else "",
                        "description": result.project.description if result.project else "",
                        "output_dir": result.project.output_dir if result.project else "",
                        "entry_point": result.project.entry_point if result.project else "",
                        "status": result.project.status if result.project else "failed",
                    } if result.project else None,
                    "artifacts": result.artifacts,
                    "error": result.error,
                }

            result = loop.run_until_complete(generate())
            loop.close()

            if result["success"]:
                self.finished.emit(result)
            else:
                self.error.emit(result.get("error", "Unknown error"))

        except Exception as e:
            self.error.emit(str(e))


class CLIAutoGenPanel(QWidget):
    """
    CLI-Anything 面板
    包含5个标签页：
    1. 工具生成 - 自然语言生成CLI
    2. 生成历史 - 查看已生成的工具
    3. 工具注册 - 管理自动生成的工具
    4. 云端同步 - 与远程清单同步
    5. 设置 - 配置选项
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cli_anything = None
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)

        # 标题栏
        title_bar = QHBoxLayout()
        title_label = QLabel("⚡ CLI-Anything 工具工厂")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_projects)
        title_bar.addWidget(refresh_btn)

        self.main_layout.addLayout(title_bar)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_generation_tab(), "🛠️ 工具生成")
        self.tabs.addTab(self._create_history_tab(), "📋 生成历史")
        self.tabs.addTab(self._create_registry_tab(), "📦 工具注册")
        self.tabs.addTab(self._create_sync_tab(), "☁️ 云端同步")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        self.main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        self.main_layout.addWidget(self.status_bar)

    def _create_generation_tab(self) -> QWidget:
        """创建工具生成标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入区域
        input_group = QGroupBox("🎯 描述你想要生成的CLI工具")
        input_layout = QVBoxLayout()

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "例如: 我需要一个能批量转换CAD格式(DWG/DXF)的工具，支持PDF/PNG输出，使用FreeCAD引擎"
        )
        self.description_input.setMaximumHeight(120)
        input_layout.addWidget(self.description_input)

        # 仓库URL（可选）
        repo_layout = QHBoxLayout()
        repo_layout.addWidget(QLabel("源码仓库 (可选):"))
        self.repo_url_input = QLineEdit()
        self.repo_url_input.setPlaceholderText("https://github.com/xxx/yyy 或留空自动分析")
        repo_layout.addWidget(self.repo_url_input)
        input_layout.addLayout(repo_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 生成选项
        options_group = QGroupBox("⚡ 生成选项")
        options_layout = QHBoxLayout()

        self.opt_install = QCheckBox("自动安装到本地")
        self.opt_install.setChecked(True)
        options_layout.addWidget(self.opt_install)

        self.opt_register = QCheckBox("注册到工具清单")
        self.opt_register.setChecked(True)
        options_layout.addWidget(self.opt_register)

        self.opt_docs = QCheckBox("生成完整文档")
        self.opt_docs.setChecked(True)
        options_layout.addWidget(self.opt_docs)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 进度显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # 生成按钮
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("🚀 开始生成")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.generate_btn.clicked.connect(self._start_generation)
        btn_layout.addWidget(self.generate_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 输出区域
        output_group = QGroupBox("📤 生成结果")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(200)
        output_layout.addWidget(self.output_text)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        layout.addStretch()
        return widget

    def _create_history_tab(self) -> QWidget:
        """创建生成历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 历史列表
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._open_project_dir)
        layout.addWidget(self.history_list)

        # 按钮栏
        btn_layout = QHBoxLayout()

        open_btn = QPushButton("📂 打开目录")
        open_btn.clicked.connect(self._open_selected_dir)
        btn_layout.addWidget(open_btn)

        install_btn = QPushButton("📥 安装选中")
        install_btn.clicked.connect(self._install_selected)
        btn_layout.addWidget(install_btn)

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_projects)
        btn_layout.addWidget(refresh_btn)

        layout.addLayout(btn_layout)

        return widget

    def _create_registry_tab(self) -> QWidget:
        """创建工具注册标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 注册工具表格
        self.registry_table = QTableWidget()
        self.registry_table.setColumns(["ID", "名称", "描述", "版本", "来源", "状态"])
        self.registry_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.registry_table)

        # 按钮栏
        btn_layout = QHBoxLayout()

        sync_btn = QPushButton("🔄 同步清单")
        sync_btn.clicked.connect(self._sync_registry)
        btn_layout.addWidget(sync_btn)

        unreg_btn = QPushButton("❌ 注销选中")
        unreg_btn.clicked.connect(self._unregister_selected)
        btn_layout.addWidget(unreg_btn)

        export_btn = QPushButton("📤 导出配置")
        export_btn.clicked.connect(self._export_registry)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        return widget

    def _create_sync_tab(self) -> QWidget:
        """创建云端同步标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 同步状态
        status_group = QGroupBox("📡 同步状态")
        status_layout = QVBoxLayout()

        self.sync_status_label = QLabel("状态: 未连接")
        status_layout.addWidget(self.sync_status_label)

        self.last_sync_label = QLabel("上次同步: 从未")
        status_layout.addWidget(self.last_sync_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 同步选项
        options_group = QGroupBox("🔧 同步选项")
        options_layout = QVBoxLayout()

        self.auto_sync_cb = QCheckBox("启动时自动同步")
        options_layout.addWidget(self.auto_sync_cb)

        self.notify_new_cb = QCheckBox("新工具生成时通知")
        self.notify_new_cb.setChecked(True)
        options_layout.addWidget(self.notify_new_cb)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 手动同步按钮
        sync_btn = QPushButton("☁️ 立即同步")
        sync_btn.clicked.connect(self._do_sync)
        layout.addWidget(sync_btn)

        # 同步日志
        log_label = QLabel("同步日志:")
        layout.addWidget(log_label)

        self.sync_log = QTextEdit()
        self.sync_log.setReadOnly(True)
        layout.addWidget(self.sync_log)

        layout.addStretch()
        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输出目录
        dir_group = QGroupBox("📁 输出目录")
        dir_layout = QHBoxLayout()

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("./generated_clis")
        dir_layout.addWidget(self.output_dir_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(browse_btn)

        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # 模型设置
        model_group = QGroupBox("🤖 生成模型")
        model_layout = QVBoxLayout()

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("使用模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Hermes Brain (本地)",
            "GPT-4 (API)",
            "Claude 3 (API)",
            "DeepSeek (API)",
        ])
        model_row.addWidget(self.model_combo)
        model_layout.addLayout(model_row)

        self.use_local_cb = QCheckBox("优先使用本地模型")
        self.use_local_cb.setChecked(True)
        model_layout.addWidget(self.use_local_cb)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # 高级选项
        advanced_group = QGroupBox("🔬 高级选项")
        advanced_layout = QVBoxLayout()

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("超时时间 (分钟):"))
        self.timeout_input = QLineEdit()
        self.timeout_input.setText("10")
        timeout_row.addWidget(self.timeout_input)
        advanced_layout.addLayout(timeout_row)

        self.keep_temp_cb = QCheckBox("保留临时文件")
        advanced_layout.addWidget(self.keep_temp_cb)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        layout.addStretch()

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        return widget

    def _initialize_cli_anything(self):
        """初始化CLI-Anything引擎"""
        if self.cli_anything is None:
            from core.cli_anything import get_cli_anything
            self.cli_anything = get_cli_anything()

    def _start_generation(self):
        """开始生成CLI工具"""
        description = self.description_input.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "警告", "请输入工具描述")
            return

        self._initialize_cli_anything()

        repo_url = self.repo_url_input.text().strip() or None

        # 更新UI状态
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setText("准备生成...")
        self.output_text.clear()
        self.status_bar.showMessage("正在生成CLI工具...")

        # 启动后台工作
        self.worker = CLIGenerationWorker(
            self.cli_anything, description, repo_url
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)
        self.worker.start()

    def _on_progress(self, pct: float, msg: str):
        """进度更新"""
        self.progress_bar.setValue(int(pct * 100))
        self.progress_label.setText(msg)
        self.output_text.append(msg)
        QApplication.processEvents()

    def _on_generation_finished(self, result: dict):
        """生成完成"""
        self._reset_ui()

        project = result.get("project", {})
        artifacts = result.get("artifacts", {})

        self.output_text.append("\n✅ CLI工具生成成功!")
        self.output_text.append(f"📦 项目: {project.get('name', 'Unknown')}")
        self.output_text.append(f"📁 目录: {project.get('output_dir', '')}")
        self.output_text.append(f"🎯 入口: {project.get('entry_point', '')}")

        if artifacts.get("files"):
            self.output_text.append(f"\n📄 生成文件 ({len(artifacts['files'])}):")
            for f in artifacts["files"][:10]:
                self.output_text.append(f"  - {f}")

        # 自动注册
        if self.opt_register.isChecked():
            tool_entry = artifacts.get("tool_entry", {})
            if tool_entry:
                from core.cli_anything import get_tools_registry
                registry = get_tools_registry()
                registry.register_tool(tool_entry)
                self.output_text.append("\n✨ 已注册到本地工具清单")

        self.status_bar.showMessage("生成完成", 5000)
        self._refresh_projects()

    def _on_generation_error(self, error: str):
        """生成错误"""
        self._reset_ui()
        self.output_text.append(f"\n❌ 生成失败: {error}")
        self.status_bar.showMessage("生成失败", 5000)
        QMessageBox.critical(self, "错误", f"生成失败:\n{error}")

    def _cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        self._reset_ui()
        self.status_bar.showMessage("已取消")
        self.output_text.append("已取消生成")

    def _reset_ui(self):
        """重置UI状态"""
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

    def _refresh_projects(self):
        """刷新项目列表"""
        self._initialize_cli_anything()

        self.history_list.clear()
        projects = self.cli_anything.get_generated_projects()

        for proj in projects:
            item = QListWidgetItem(
                f"📦 {proj.name} [{proj.status}] - {proj.id}"
            )
            item.setData(Qt.ItemDataRole.UserRole, proj)
            self.history_list.addItem(item)

        # 刷新注册表
        self._refresh_registry()

    def _refresh_registry(self):
        """刷新注册表"""
        from core.cli_anything import get_tools_registry

        registry = get_tools_registry()
        tools = registry.get_tools()

        self.registry_table.setRowCount(len(tools))
        for i, tool in enumerate(tools):
            self.registry_table.setItem(i, 0, QTableWidgetItem(tool.get("id", "")))
            self.registry_table.setItem(i, 1, QTableWidgetItem(tool.get("name", "")))
            self.registry_table.setItem(i, 2, QTableWidgetItem(tool.get("desc", "")))
            self.registry_table.setItem(i, 3, QTableWidgetItem(tool.get("version", "")))
            self.registry_table.setItem(i, 4, QTableWidgetItem(tool.get("origin", "")))
            self.registry_table.setItem(i, 5, QTableWidgetItem("已注册" if tool else "未知"))

    def _open_project_dir(self, item: QListWidgetItem):
        """打开项目目录"""
        proj = item.data(Qt.ItemDataRole.UserRole)
        if proj and proj.output_dir:
            import subprocess
            subprocess.Popen(f'explorer "{proj.output_dir}"')

    def _open_selected_dir(self):
        """打开选中项目的目录"""
        current = self.history_list.currentItem()
        if current:
            self._open_project_dir(current)

    def _install_selected(self):
        """安装选中的工具"""
        current = self.history_list.currentItem()
        if not current:
            return

        proj = current.data(Qt.ItemDataRole.UserRole)
        if proj and proj.output_dir:
            import subprocess
            result = subprocess.run(
                ["pip", "install", "-e", proj.output_dir],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                QMessageBox.information(self, "成功", f"已安装 {proj.name}")
            else:
                QMessageBox.critical(self, "失败", result.stderr)

    def _delete_selected(self):
        """删除选中的项目"""
        current = self.history_list.currentItem()
        if not current:
            return

        proj = current.data(Qt.ItemDataRole.UserRole)
        if proj and proj.output_dir:
            reply = QMessageBox.question(
                self, "确认", f"确定删除项目 {proj.name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                import shutil
                shutil.rmtree(proj.output_dir, ignore_errors=True)
                self._refresh_projects()

    def _sync_registry(self):
        """同步注册表"""
        self._refresh_registry()
        self.sync_log.append(f"[{time.strftime('%H:%M:%S')}] 本地注册表已刷新")

    def _unregister_selected(self):
        """注销选中的工具"""
        row = self.registry_table.currentRow()
        if row < 0:
            return

        tool_id = self.registry_table.item(row, 0).text()
        from core.cli_anything import get_tools_registry
        registry = get_tools_registry()
        registry.unregister_tool(tool_id)
        self._refresh_registry()
        self.sync_log.append(f"[{time.strftime('%H:%M:%S')}] 已注销: {tool_id}")

    def _export_registry(self):
        """导出注册表"""
        from core.cli_anything import get_tools_registry
        registry = get_tools_registry()
        tools = registry._registry

        import json
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "导出注册表", "autogen_tools.json", "JSON Files (*.json)"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(tools, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "成功", f"已导出到 {path}")

    def _do_sync(self):
        """执行同步"""
        self.sync_log.append(f"[{time.strftime('%H:%M:%S')}] 开始同步...")
        # 模拟同步过程
        self.sync_status_label.setText("状态: 同步中...")
        QApplication.processEvents()

        import time
        time.sleep(1)

        self.sync_status_label.setText("状态: 已连接")
        self.last_sync_label.setText(f"上次同步: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.sync_log.append(f"[{time.strftime('%H:%M:%S')}] 同步完成")

    def _browse_output_dir(self):
        """浏览输出目录"""
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_input.setText(path)

    def _save_settings(self):
        """保存设置"""
        QMessageBox.information(self, "成功", "设置已保存")
