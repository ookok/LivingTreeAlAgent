"""
Archive Tool 管理面板

PyQt6 实现，提供 NanaZip/7z 压缩工具的图形化管理界面
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
    QMessageBox, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QColor, QFont, QIcon

logger = logging.getLogger(__name__)


class ArchiveToolPanel(QWidget):
    """
    压缩工具管理面板

    功能：
    - 压缩文件/目录
    - 解压压缩包
    - 批量压缩任务
    - 历史记录
    """

    # 信号定义
    task_started = pyqtSignal(str)  # task_id
    task_completed = pyqtSignal(str)  # task_id
    task_failed = pyqtSignal(str, str)  # task_id, error

    def __init__(self, archive_tool=None, parent=None):
        super().__init__(parent)
        self.archive_tool = archive_tool
        self._tasks = {}
        self._setup_ui()
        self._setup_timers()
        self._init_tool()

    def set_archive_tool(self, tool):
        """设置工具实例"""
        self.archive_tool = tool
        self._update_status()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📦 压缩/解压工具")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 状态栏
        self.status_label = QLabel("⚡ 初始化中...")
        self.status_label.setStyleSheet("padding: 5px; background: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.status_label)

        # Tab 页面
        tabs = QTabWidget()

        # Tab 1: 快速压缩
        tabs.addTab(self._create_compress_tab(), "📤 快速压缩")

        # Tab 2: 快速解压
        tabs.addTab(self._create_extract_tab(), "📥 快速解压")

        # Tab 3: 任务管理
        tabs.addTab(self._create_tasks_tab(), "📋 任务管理")

        # Tab 4: 设置
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

    def _create_compress_tab(self) -> QWidget:
        """创建压缩页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 源文件选择
        source_group = QGroupBox("源文件/目录")
        source_layout = QHBoxLayout()

        self.source_path_edit = QLineEdit()
        self.source_path_edit.setPlaceholderText("选择要压缩的文件或文件夹...")
        source_layout.addWidget(self.source_path_edit)

        self.browse_source_btn = QPushButton("浏览...")
        self.browse_source_btn.clicked.connect(self._browse_source)
        source_layout.addWidget(self.browse_source_btn)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QGridLayout()

        # 格式选择
        output_layout.addWidget(QLabel("压缩格式:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "7z (7-zip, 最高压缩率)",
            "zip (通用格式)",
            "tar.gz (Linux/Unix)",
            "tar.bz2 (高压缩率)",
        ])
        output_layout.addWidget(self.format_combo, 0, 1)

        # 压缩级别
        output_layout.addWidget(QLabel("压缩级别:"), 1, 0)
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "标准 (Normal)",
            "最快 (Fast)",
            "最大 (Maximum)",
            "极限 (Ultra)",
        ])
        output_layout.addWidget(self.level_combo, 1, 1)

        # 输出路径
        output_layout.addWidget(QLabel("输出文件:"), 2, 0)
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("输出路径 (留空则自动生成)...")
        output_layout.addWidget(self.output_path_edit, 2, 1)

        self.browse_output_btn = QPushButton("浏览...")
        self.browse_output_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.browse_output_btn, 2, 2)

        # 分卷压缩
        self.split_check = QCheckBox("分卷压缩")
        self.split_size_spin = QSpinBox()
        self.split_size_spin.setSuffix(" MB")
        self.split_size_spin.setRange(1, 1000)
        self.split_size_spin.setValue(10)
        self.split_size_spin.setEnabled(False)
        self.split_check.stateChanged.connect(
            lambda s: self.split_size_spin.setEnabled(s == Qt.CheckState.Checked)
        )
        output_layout.addWidget(self.split_check, 3, 0, 1, 2)
        output_layout.addWidget(self.split_size_spin, 3, 2)

        # 密码保护
        self.password_check = QCheckBox("密码保护")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setEnabled(False)
        self.password_edit.setPlaceholderText("输入密码...")
        self.password_check.stateChanged.connect(
            lambda s: self.password_edit.setEnabled(s == Qt.CheckState.Checked)
        )
        output_layout.addWidget(self.password_check, 4, 0, 1, 2)
        output_layout.addWidget(self.password_edit, 4, 2)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # 进度条
        self.compress_progress = QProgressBar()
        self.compress_progress.setVisible(False)
        layout.addWidget(self.compress_progress)

        # 压缩按钮
        self.compress_btn = QPushButton("🚀 开始压缩")
        self.compress_btn.clicked.connect(self._start_compress)
        self.compress_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #cccccc; }
        """)
        layout.addWidget(self.compress_btn)

        layout.addStretch()

        return widget

    def _create_extract_tab(self) -> QWidget:
        """创建解压页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 压缩包选择
        archive_group = QGroupBox("压缩包")
        archive_layout = QHBoxLayout()

        self.archive_path_edit = QLineEdit()
        self.archive_path_edit.setPlaceholderText("选择要解压的压缩包...")
        archive_layout.addWidget(self.archive_path_edit)

        self.browse_archive_btn = QPushButton("浏览...")
        self.browse_archive_btn.clicked.connect(self._browse_archive)
        archive_layout.addWidget(self.archive_path_edit)
        archive_layout.addWidget(self.browse_archive_btn)

        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)

        # 解压设置
        extract_group = QGroupBox("解压设置")
        extract_layout = QGridLayout()

        # 输出目录
        extract_layout.addWidget(QLabel("输出目录:"), 0, 0)
        self.extract_output_edit = QLineEdit()
        self.extract_output_edit.setPlaceholderText("解压到... (留空则自动生成)...")
        extract_layout.addWidget(self.extract_output_edit, 0, 1)

        self.browse_extract_btn = QPushButton("浏览...")
        self.browse_extract_btn.clicked.connect(self._browse_extract_dir)
        extract_layout.addWidget(self.browse_extract_btn, 0, 2)

        # 密码
        extract_layout.addWidget(QLabel("密码:"), 1, 0)
        self.extract_password_edit = QLineEdit()
        self.extract_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.extract_password_edit.setPlaceholderText("如有密码请输入...")
        extract_layout.addWidget(self.extract_password_edit, 1, 1, 1, 2)

        # 查看内容
        self.list_contents_btn = QPushButton("📋 查看内容")
        self.list_contents_btn.clicked.connect(self._list_archive_contents)
        extract_layout.addWidget(self.list_contents_btn, 2, 0, 1, 3)

        # 内容列表
        self.contents_list = QListWidget()
        self.contents_list.setMaximumHeight(150)
        extract_layout.addWidget(self.contents_list, 3, 0, 1, 3)

        extract_group.setLayout(extract_layout)
        layout.addWidget(extract_group)

        # 进度条
        self.extract_progress = QProgressBar()
        self.extract_progress.setVisible(False)
        layout.addWidget(self.extract_progress)

        # 解压按钮
        self.extract_btn = QPushButton("🚀 开始解压")
        self.extract_btn.clicked.connect(self._start_extract)
        self.extract_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1976D2; }
            QPushButton:disabled { background: #cccccc; }
        """)
        layout.addWidget(self.extract_btn)

        layout.addStretch()

        return widget

    def _create_tasks_tab(self) -> QWidget:
        """创建任务管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 任务统计
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("待处理: 0 | 运行中: 0 | 完成: 0 | 失败: 0")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._refresh_tasks)
        stats_layout.addWidget(self.refresh_btn)

        layout.addLayout(stats_layout)

        # 任务表格
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(6)
        self.tasks_table.setHorizontalHeaderLabels([
            "任务ID", "操作", "源", "状态", "进度", "耗时"
        ])
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tasks_table)

        # 任务操作按钮
        task_btn_layout = QHBoxLayout()

        self.cancel_task_btn = QPushButton("❌ 取消")
        self.cancel_task_btn.clicked.connect(self._cancel_selected_task)
        task_btn_layout.addWidget(self.cancel_task_btn)

        self.clear_completed_btn = QPushButton("🗑️ 清除已完成")
        self.clear_completed_btn.clicked.connect(self._clear_completed)
        task_btn_layout.addWidget(self.clear_completed_btn)

        task_btn_layout.addStretch()

        layout.addLayout(task_btn_layout)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具设置
        tool_group = QGroupBox("工具后端")
        tool_layout = QGridLayout()

        tool_layout.addWidget(QLabel("当前后端:"), 0, 0)
        self.backend_label = QLabel("检测中...")
        tool_layout.addWidget(self.backend_label, 0, 1)

        tool_layout.addWidget(QLabel("线程数:"), 1, 0)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 32)
        self.threads_spin.setSuffix(" (0=自动)")
        self.threads_spin.setToolTip("0 表示使用所有可用 CPU 核心")
        tool_layout.addWidget(self.threads_spin, 1, 1)

        self.test_backend_btn = QPushButton("🔍 检测后端")
        self.test_backend_btn.clicked.connect(self._test_backend)
        tool_layout.addWidget(self.test_backend_btn, 2, 0, 1, 2)

        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)

        # 默认设置
        defaults_group = QGroupBox("默认设置")
        defaults_layout = QGridLayout()

        defaults_layout.addWidget(QLabel("默认压缩格式:"), 0, 0)
        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["7z", "zip", "tar.gz"])
        defaults_layout.addWidget(self.default_format_combo, 0, 1)

        defaults_layout.addWidget(QLabel("默认压缩级别:"), 1, 0)
        self.default_level_combo = QComboBox()
        self.default_level_combo.addItems(["标准", "最快", "最大", "极限"])
        defaults_layout.addWidget(self.default_level_combo, 1, 1)

        defaults_group.setLayout(defaults_layout)
        layout.addWidget(defaults_group)

        # 关于
        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout()
        about_layout.addWidget(QLabel("NanaZip CLI v6.0 - 高性能压缩引擎"))
        about_layout.addWidget(QLabel("基于 7-Zip 优化，适配 Windows 11"))
        about_layout.addWidget(QLabel("支持格式: 7z, zip, tar, gz, bz2, xz, rar 等"))
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)

        layout.addStretch()

        return widget

    def _setup_timers(self):
        """设置定时器"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_task_display)
        self._timer.setInterval(500)

    def _init_tool(self):
        """初始化工具"""
        if self.archive_tool is None:
            try:
                from .business.archive_tool import ArchiveTool
                self.archive_tool = ArchiveTool()
            except Exception as e:
                logger.error(f"Failed to init archive tool: {e}")
                self.status_label.setText(f"❌ 初始化失败: {e}")
                return

        # 异步初始化
        asyncio.ensure_future(self._async_init())

    async def _async_init(self):
        """异步初始化"""
        try:
            await self.archive_tool.initialize()
            self._update_status()
            self._timer.start()
        except Exception as e:
            self.status_label.setText(f"❌ 初始化失败: {e}")

    def _update_status(self):
        """更新状态显示"""
        if self.archive_tool:
            backend = self.archive_tool.backend
            available = self.archive_tool.is_available
            status = "✅ 就绪" if available else "❌ 不可用"
            self.status_label.setText(f"{status} | 后端: {backend}")
            self.backend_label.setText(backend)

    # ── 压缩相关 ──────────────────────────────────────────────────────

    def _browse_source(self):
        """浏览源文件"""
        path = QFileDialog.getExistingDirectory(self, "选择源文件/目录")
        if path:
            self.source_path_edit.setText(path)
            # 自动设置输出路径
            if not self.output_path_edit.text():
                import os
                name = os.path.basename(path)
                self.output_path_edit.setText(f"{name}.7z")

    def _browse_output(self):
        """浏览输出路径"""
        path = QFileDialog.getSaveFileName(
            self, "保存压缩包",
            filter="7z 文件 (*.7z);;zip 文件 (*.zip);;所有文件 (*)"
        )[0]
        if path:
            self.output_path_edit.setText(path)

    def _get_format_and_level(self):
        """获取格式和级别"""
        format_map = {
            0: ("7z", "normal"),
            1: ("7z", "fast"),
            2: ("7z", "maximum"),
            3: ("7z", "ultra"),
        }
        level_map = {
            0: "normal",
            1: "fastest",
            2: "maximum",
            3: "ultra",
        }
        fmt_idx = self.format_combo.currentIndex()
        lvl_idx = self.level_combo.currentIndex()
        return format_map.get(fmt_idx, ("7z", "normal")), level_map.get(lvl_idx, "normal")

    def _start_compress(self):
        """开始压缩"""
        source = self.source_path_edit.text().strip()
        if not source:
            QMessageBox.warning(self, "提示", "请选择要压缩的文件或目录")
            return

        output = self.output_path_edit.text().strip()
        if not output:
            # 自动生成
            import os
            import uuid
            base = os.path.basename(source.rstrip("/\\"))
            output = f"{base}_{uuid.uuid4().hex[:4]}.7z"

        if not self.archive_tool:
            QMessageBox.warning(self, "错误", "压缩工具未初始化")
            return

        # 获取选项
        (fmt, _), lvl = self._get_format_and_level()
        password = self.password_edit.text() if self.password_check.isChecked() else None
        split_size = self.split_size_spin.value() * 1024 * 1024 if self.split_check.isChecked() else None

        # 禁用按钮
        self.compress_btn.setEnabled(False)
        self.compress_progress.setVisible(True)
        self.compress_progress.setRange(0, 100)
        self.compress_progress.setValue(0)

        # 异步执行
        asyncio.ensure_future(self._do_compress(source, output, fmt, lvl, password, split_size))

    async def _do_compress(self, source, output, fmt, lvl, password, split_size):
        """执行压缩"""
        try:
            from .business.archive_tool import ArchiveFormat, CompressionLevel

            fmt_enum = ArchiveFormat.SEVENZ if fmt == "7z" else ArchiveFormat.ZIP
            level_enum = CompressionLevel.NORMAL
            if lvl == "fastest":
                level_enum = CompressionLevel.FASTEST
            elif lvl == "maximum":
                level_enum = CompressionLevel.MAXIMUM
            elif lvl == "ultra":
                level_enum = CompressionLevel.ULTRA

            def progress_callback(p: float):
                self.compress_progress.setValue(int(p * 100))

            task = await self.archive_tool.compress(
                source, output, fmt_enum, level_enum,
                password=password, split_size=split_size,
                progress_callback=progress_callback
            )

            if task.status == "completed":
                self.compress_progress.setValue(100)
                QMessageBox.information(
                    self, "成功",
                    f"压缩完成！\n输出: {output}\n大小: {self.archive_tool.format_size(task.output_size)}"
                )
                self._add_task_to_table(task)
            else:
                QMessageBox.warning(self, "失败", f"压缩失败: {task.error}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"压缩过程出错: {e}")
        finally:
            self.compress_btn.setEnabled(True)
            self.compress_progress.setVisible(False)

    # ── 解压相关 ──────────────────────────────────────────────────────

    def _browse_archive(self):
        """浏览压缩包"""
        path = QFileDialog.getOpenFileName(
            self, "选择压缩包",
            filter="压缩文件 (*.7z *.zip *.tar.gz *.rar *.tar.bz2);;所有文件 (*)"
        )[0]
        if path:
            self.archive_path_edit.setText(path)
            # 自动设置输出目录
            if not self.extract_output_edit.text():
                import os
                base = os.path.splitext(os.path.basename(path))[0]
                self.extract_output_edit.setText(base)

    def _browse_extract_dir(self):
        """浏览解压目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.extract_output_edit.setText(path)

    def _list_archive_contents(self):
        """列出压缩包内容"""
        archive = self.archive_path_edit.text().strip()
        if not archive:
            QMessageBox.warning(self, "提示", "请选择压缩包")
            return

        if not self.archive_tool:
            return

        asyncio.ensure_future(self._do_list_contents(archive))

    async def _do_list_contents(self, archive):
        """执行列出内容"""
        try:
            files = await self.archive_tool.list_contents(archive)
            self.contents_list.clear()
            for f in files[:50]:  # 最多显示50条
                self.contents_list.addItem(f.get("name", ""))
            if len(files) > 50:
                self.contents_list.addItem(f"... 还有 {len(files) - 50} 个文件")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取内容: {e}")

    def _start_extract(self):
        """开始解压"""
        archive = self.archive_path_edit.text().strip()
        if not archive:
            QMessageBox.warning(self, "提示", "请选择压缩包")
            return

        output = self.extract_output_edit.text().strip()
        if not output:
            import os
            base = os.path.splitext(os.path.basename(archive))[0]
            output = base

        if not self.archive_tool:
            QMessageBox.warning(self, "错误", "解压工具未初始化")
            return

        password = self.extract_password_edit.text() or None

        # 禁用按钮
        self.extract_btn.setEnabled(False)
        self.extract_progress.setVisible(True)
        self.extract_progress.setRange(0, 100)

        asyncio.ensure_future(self._do_extract(archive, output, password))

    async def _do_extract(self, archive, output, password):
        """执行解压"""
        try:
            def progress_callback(p: float):
                self.extract_progress.setValue(int(p * 100))

            task = await self.archive_tool.extract(
                archive, output,
                password=password,
                progress_callback=progress_callback
            )

            if task.status == "completed":
                self.extract_progress.setValue(100)
                QMessageBox.information(
                    self, "成功",
                    f"解压完成！\n输出目录: {output}"
                )
                self._add_task_to_table(task)
            else:
                QMessageBox.warning(self, "失败", f"解压失败: {task.error}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"解压过程出错: {e}")
        finally:
            self.extract_btn.setEnabled(True)
            self.extract_progress.setVisible(False)

    # ── 任务管理 ──────────────────────────────────────────────────────

    def _add_task_to_table(self, task):
        """添加任务到表格"""
        import datetime

        row = self.tasks_table.rowCount()
        self.tasks_table.insertRow(row)

        self.tasks_table.setItem(row, 0, QTableWidgetItem(task.task_id))
        self.tasks_table.setItem(row, 1, QTableWidgetItem(task.operation))
        self.tasks_table.setItem(row, 2, QTableWidgetItem(
            os.path.basename(task.source)[:30]
        ))

        status_item = QTableWidgetItem(task.status)
        if task.status == "completed":
            status_item.setBackground(QColor("#c8e6c9"))
        elif task.status == "failed":
            status_item.setBackground(QColor("#ffcdd2"))
        elif task.status == "running":
            status_item.setBackground(QColor("#fff9c4"))
        self.tasks_table.setItem(row, 3, status_item)

        self.tasks_table.setItem(row, 4, QTableWidgetItem(f"{task.progress * 100:.0f}%"))

        if task.started_at and task.completed_at:
            delta = (task.completed_at - task.started_at).total_seconds()
            self.tasks_table.setItem(row, 5, QTableWidgetItem(f"{delta:.1f}s"))

        self._tasks[task.task_id] = task
        self._refresh_stats()

    def _refresh_tasks(self):
        """刷新任务列表"""
        for task_id, task in self._tasks.items():
            self._add_task_to_table(task)  # 简单处理，实际应更新

    def _cancel_selected_task(self):
        """取消选中任务"""
        row = self.tasks_table.currentRow()
        if row >= 0:
            task_id = self.tasks_table.item(row, 0).text()
            if self.archive_tool and self.archive_tool.cancel_task(task_id):
                QMessageBox.information(self, "成功", "任务已取消")
                self._refresh_tasks()

    def _clear_completed(self):
        """清除已完成任务"""
        self.tasks_table.setRowCount(0)
        self._tasks = {k: v for k, v in self._tasks.items()
                       if v.status not in ("completed", "failed", "cancelled")}
        self._refresh_stats()

    def _refresh_stats(self):
        """刷新统计"""
        pending = sum(1 for t in self._tasks.values() if t.status == "pending")
        running = sum(1 for t in self._tasks.values() if t.status == "running")
        completed = sum(1 for t in self._tasks.values() if t.status == "completed")
        failed = sum(1 for t in self._tasks.values() if t.status in ("failed", "cancelled"))
        self.stats_label.setText(f"待处理: {pending} | 运行中: {running} | 完成: {completed} | 失败: {failed}")

    def _update_task_display(self):
        """更新任务显示"""
        # 实时更新正在运行的任务
        pass

    # ── 设置相关 ──────────────────────────────────────────────────────

    def _test_backend(self):
        """测试后端"""
        if self.archive_tool:
            asyncio.ensure_future(self._do_test_backend())

    async def _do_test_backend(self):
        """执行后端测试"""
        try:
            await self.archive_tool.initialize()
            self._update_status()
            QMessageBox.information(
                self, "检测完成",
                f"后端: {self.archive_tool.backend}\n可用: {self.archive_tool.is_available}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检测失败: {e}")
