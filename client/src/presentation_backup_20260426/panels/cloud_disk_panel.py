"""
Cloud Disk Panel - 虚拟云盘管理面板

提供多云盘统一管理界面：
- 云盘连接管理
- 虚拟文件浏览
- 上传下载任务
- 配额显示
"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QProgressBar,
    QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QStatusBar,
    QListWidget, QListWidgetItem, QSplitter,
    QProgressDialog, QDialog, QDialogButtonBox,
    QTextEdit
)
from PyQt6.QtCore import QThread, pyqtSignal

import asyncio
from datetime import datetime
from pathlib import Path


# ============= 异步任务线程 =============

class AsyncTaskThread(QThread):
    """异步任务执行线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, coro, *args, **kwargs):
        super().__init__()
        self.coro = coro
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.coro(*self.args, **self.kwargs))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ============= 云盘连接对话框 =============

class CloudConnectDialog(QDialog):
    """云盘连接配置对话框"""

    def __init__(self, parent=None, driver_type="aliyun"):
        super().__init__(parent)
        self.driver_type = driver_type
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"连接 {self.driver_type.upper()} 云盘")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        # 驱动类型
        self.driver_combo = QComboBox()
        self.driver_combo.addItems(["aliyun", "quark", "115", "onedrive"])
        self.driver_combo.setCurrentText(self.driver_type)
        layout.addRow("云盘类型:", self.driver_combo)

        # 连接名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("我的阿里云盘")
        layout.addRow("名称:", self.name_edit)

        # 凭据输入（根据不同驱动）
        if self.driver_type == "aliyun":
            self.token_edit = QTextEdit()
            self.token_edit.setPlaceholderText("请输入阿里云盘 refresh_token\n获取方法:\n1. 打开 aliyundrive.com\n2. 按 F12 打开开发者工具\n3. 在控制台执行: localStorage.token")
            self.token_edit.setMaximumHeight(100)
            layout.addRow("Refresh Token:", self.token_edit)

        elif self.driver_type == "quark":
            self.phone_edit = QLineEdit()
            self.phone_edit.setPlaceholderText("手机号")
            layout.addRow("手机号:", self.phone_edit)
            self.password_edit = QLineEdit()
            self.password_edit.setPlaceholderText("密码")
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("密码:", self.password_edit)

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_config(self) -> dict:
        """获取配置"""
        config = {
            "name": self.name_edit.text() or self.driver_type,
            "type": self.driver_combo.currentText(),
        }

        if self.driver_type == "aliyun":
            config["refresh_token"] = self.token_edit.toPlainText()

        return config


# ============= 虚拟云盘面板 =============

class CloudDiskPanel(QWidget):
    """
    虚拟云盘管理面板

    功能:
    - 云盘连接管理 (添加/删除/刷新)
    - 虚拟文件浏览 (树形视图)
    - 上传下载任务列表
    - 配额显示
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None  # VirtualCloudEngine 实例
        self.current_path = "/"
        self.setup_ui()

    def set_engine(self, engine):
        """设置虚拟云盘引擎"""
        self.engine = engine
        self.refresh_mount_points()

    def setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_browse_tab(), "📁 文件浏览")
        tabs.addTab(self._create_connections_tab(), "☁️ 云盘连接")
        tabs.addTab(self._create_tasks_tab(), "📥 传输任务")
        tabs.addTab(self._create_quota_tab(), "💾 配额信息")
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

    # ── 文件浏览 ─────────────────────────────────────────────────────

    def _create_browse_tab(self) -> QWidget:
        """创建文件浏览标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 路径栏
        path_layout = QHBoxLayout()
        self.path_label = QLabel("/")
        self.path_label.setStyleSheet("font-family: monospace;")
        path_layout.addWidget(QLabel("当前路径:"))
        path_layout.addWidget(self.path_label)

        btn_back = QPushButton("⬆️ 返回上级")
        btn_back.clicked.connect(self.go_up)
        path_layout.addWidget(btn_back)

        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self.refresh_current_dir)
        path_layout.addWidget(btn_refresh)

        layout.addLayout(path_layout)

        # 文件列表
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：目录树
        self.dir_tree = QTreeWidget()
        self.dir_tree.setHeaderLabel("云盘文件")
        self.dir_tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        splitter.addWidget(self._create_group_box("目录", self.dir_tree))

        # 右侧：文件列表
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改时间"])
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.itemDoubleClicked.connect(self.on_file_item_double_clicked)
        splitter.addWidget(self._create_group_box("文件列表", self.file_table))

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_upload = QPushButton("⬆️ 上传")
        btn_upload.clicked.connect(self.upload_file)
        btn_layout.addWidget(btn_upload)

        btn_download = QPushButton("⬇️ 下载")
        btn_download.clicked.connect(self.download_selected)
        btn_layout.addWidget(btn_download)

        btn_delete = QPushButton("🗑️ 删除")
        btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(btn_delete)

        btn_share = QPushButton("🔗 分享")
        btn_share.clicked.connect(self.share_selected)
        btn_layout.addWidget(btn_share)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_group_box(self, title: str, widget: QWidget) -> QWidget:
        """创建分组框"""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    # ── 云盘连接 ─────────────────────────────────────────────────────

    def _create_connections_tab(self) -> QWidget:
        """创建云盘连接标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 连接列表
        self.connections_list = QListWidget()
        self.connections_list.itemSelectionChanged.connect(self.on_connection_selected)
        layout.addWidget(self._create_group_box("已连接的云盘", self.connections_list))

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 添加连接")
        btn_add.clicked.connect(self.add_connection)
        btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("➖ 移除")
        btn_remove.clicked.connect(self.remove_connection)
        btn_layout.addWidget(btn_remove)

        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self.refresh_mount_points)
        btn_layout.addWidget(btn_refresh)

        layout.addLayout(btn_layout)

        # 连接详情
        self.connection_detail = QTextEdit()
        self.connection_detail.setReadOnly(True)
        self.connection_detail.setMaximumHeight(150)
        layout.addWidget(self._create_group_box("连接详情", self.connection_detail))

        return widget

    # ── 传输任务 ─────────────────────────────────────────────────────

    def _create_tasks_tab(self) -> QWidget:
        """创建传输任务标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 任务表格
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(5)
        self.tasks_table.setHorizontalHeaderLabels(["任务ID", "类型", "路径", "进度", "状态"])
        layout.addWidget(self._create_group_box("传输任务", self.tasks_table))

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("❌ 取消")
        btn_cancel.clicked.connect(self.cancel_selected_task)
        btn_layout.addWidget(btn_cancel)

        btn_clear = QPushButton("🗑️ 清除已完成")
        btn_clear.clicked.connect(self.clear_completed_tasks)
        btn_layout.addWidget(btn_clear)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    # ── 配额信息 ─────────────────────────────────────────────────────

    def _create_quota_tab(self) -> QWidget:
        """创建配额信息标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.quota_table = QTableWidget()
        self.quota_table.setColumnCount(5)
        self.quota_table.setHorizontalHeaderLabels(["云盘", "总容量", "已用", "剩余", "使用率"])
        layout.addWidget(self._create_group_box("存储配额", self.quota_table))

        btn_refresh = QPushButton("🔄 刷新配额")
        btn_refresh.clicked.connect(self.refresh_quotas)
        layout.addWidget(btn_refresh)

        layout.addStretch()
        return widget

    # ── 设置 ─────────────────────────────────────────────────────

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # 缓存设置
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(0, 3600)
        self.cache_ttl.setValue(300)
        self.cache_ttl.setSuffix(" 秒")
        layout.addRow("元数据缓存TTL:", self.cache_ttl)

        self.max_cache_size = QSpinBox()
        self.max_cache_size.setRange(100, 10000)
        self.max_cache_size.setValue(1024)
        self.max_cache_size.setSuffix(" MB")
        layout.addRow("最大缓存大小:", self.max_cache_size)

        # 调度策略
        self.read_priority = QComboBox()
        self.read_priority.addItems(["aliyun", "quark", "115", "onedrive"])
        layout.addRow("读操作优先:", self.read_priority)

        self.write_priority = QComboBox()
        self.write_priority.addItems(["aliyun", "quark", "115", "onedrive"])
        layout.addRow("写操作优先:", self.write_priority)

        # 缓存目录
        self.cache_dir = QLineEdit()
        self.cache_dir.setText("./.hermes/clouds_cache")
        layout.addRow("缓存目录:", self.cache_dir)

        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_cache_dir)
        layout.addRow("", btn_browse)

        layout.addRow(QPushButton("💾 保存设置"))

        return widget

    # ── 槽函数 ─────────────────────────────────────────────────────

    async def load_directory(self, path: str):
        """加载目录内容"""
        if not self.engine:
            return

        try:
            entries = await self.engine.list_directory(path)
            self._update_file_table(entries)
            self.path_label.setText(path)
            self.current_path = path
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载目录失败: {e}")

    def _update_file_table(self, entries):
        """更新文件表格"""
        self.file_table.setRowCount(0)

        for entry in entries:
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)

            self.file_table.setItem(row, 0, QTableWidgetItem(entry.name))
            self.file_table.setItem(row, 1, QTableWidgetItem(
                self._format_size(entry.size) if entry.size else "-"
            ))
            self.file_table.setItem(row, 2, QTableWidgetItem(
                "文件夹" if entry.is_folder else "文件"
            ))
            self.file_table.setItem(row, 3, QTableWidgetItem(
                entry.modified_time.strftime("%Y-%m-%d %H:%M") if entry.modified_time else "-"
            ))

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def go_up(self):
        """返回上级目录"""
        if self.current_path == "/":
            return

        parts = self.current_path.strip("/").split("/")
        parent = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"

        thread = AsyncTaskThread(self.load_directory, parent)
        thread.finished.connect(lambda _: self.refresh_current_dir())
        thread.start()

    def on_tree_item_double_clicked(self, item, column):
        """目录树项双击"""
        pass  # 简化实现

    def on_file_item_double_clicked(self, item, column):
        """文件项双击"""
        row = item.row()
        name_item = self.file_table.item(row, 2)
        if name_item and name_item.text() == "文件夹":
            # 进入目录
            name = self.file_table.item(row, 0).text()
            new_path = f"{self.current_path.rstrip('/')}/{name}"
            self.load_directory(new_path)

    def refresh_current_dir(self):
        """刷新当前目录"""
        if self.current_path:
            thread = AsyncTaskThread(self.load_directory, self.current_path)
            thread.start()

    def upload_file(self):
        """上传文件"""
        if not self.engine:
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择要上传的文件")
        if not file_path:
            return

        # 获取目标路径
        dest_path = self.current_path.rstrip("/") + "/" + Path(file_path).name

        try:
            with open(file_path, "rb") as f:
                size = Path(file_path).stat().st_size
                thread = AsyncTaskThread(
                    self.engine.upload,
                    f, dest_path, size
                )
                thread.finished.connect(lambda _: QMessageBox.information(
                    self, "完成", "文件上传成功"
                ))
                thread.error.connect(lambda e: QMessageBox.warning(
                    self, "错误", f"上传失败: {e}"
                ))
                thread.start()

        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法上传: {e}")

    def download_selected(self):
        """下载选中文件"""
        if not self.engine:
            return

        row = self.file_table.currentRow()
        if row < 0:
            return

        name = self.file_table.item(row, 0).text()
        type_ = self.file_table.item(row, 2).text()

        if type_ == "文件夹":
            QMessageBox.information(self, "提示", "文件夹下载功能开发中")
            return

        virtual_path = f"{self.current_path.rstrip('/')}/{name}"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存到", name)

        if save_path:
            try:
                with open(save_path, "wb") as f:
                    thread = AsyncTaskThread(
                        self.engine.download,
                        virtual_path, f
                    )
                    thread.finished.connect(lambda _: QMessageBox.information(
                        self, "完成", "文件下载成功"
                    ))
                    thread.start()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"下载失败: {e}")

    def delete_selected(self):
        """删除选中文件"""
        row = self.file_table.currentRow()
        if row < 0:
            return

        reply = QMessageBox.question(
            self, "确认", "确定要删除选中的文件吗？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        name = self.file_table.item(row, 0).text()
        virtual_path = f"{self.current_path.rstrip('/')}/{name}"

        if self.engine:
            thread = AsyncTaskThread(self.engine.drivers.get_default().delete, virtual_path)
            thread.finished.connect(lambda _: self.refresh_current_dir())
            thread.start()

    def share_selected(self):
        """分享选中文件"""
        row = self.file_table.currentRow()
        if row < 0:
            return

        name = self.file_table.item(row, 0).text()
        virtual_path = f"{self.current_path.rstrip('/')}/{name}"

        if self.engine:
            thread = AsyncTaskThread(self.engine.share, virtual_path)
            thread.finished.connect(self._on_share_created)
            thread.start()

    def _on_share_created(self, result):
        """分享创建完成"""
        url, password = result
        if url:
            QMessageBox.information(
                self, "分享链接",
                f"分享链接: {url}\n密码: {password or '无'}"
            )
        else:
            QMessageBox.warning(self, "错误", "创建分享链接失败")

    def add_connection(self):
        """添加云盘连接"""
        dialog = CloudConnectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            # TODO: 使用配置创建驱动并注册到引擎
            self.refresh_mount_points()

    def remove_connection(self):
        """移除云盘连接"""
        pass

    def on_connection_selected(self):
        """连接选中"""
        pass

    def refresh_mount_points(self):
        """刷新挂载点"""
        if not self.engine:
            return

        mounts = self.engine.get_mount_points()
        self.connections_list.clear()

        for mount in mounts:
            status = "✅" if mount["authenticated"] else "❌"
            item_text = f"{status} {mount['name']} ({mount['provider']})"
            self.connections_list.addItem(item_text)

    def refresh_quotas(self):
        """刷新配额信息"""
        if not self.engine:
            return

        thread = AsyncTaskThread(self.engine.get_all_quotas)
        thread.finished.connect(self._update_quota_table)
        thread.start()

    def _update_quota_table(self, quotas: dict):
        """更新配额表格"""
        self.quota_table.setRowCount(0)

        for name, quota in quotas.items():
            row = self.quota_table.rowCount()
            self.quota_table.insertRow(row)

            self.quota_table.setItem(row, 0, QTableWidgetItem(name))
            self.quota_table.setItem(row, 1, QTableWidgetItem(
                self._format_size(quota.total)
            ))
            self.quota_table.setItem(row, 2, QTableWidgetItem(
                self._format_size(quota.used)
            ))
            self.quota_table.setItem(row, 3, QTableWidgetItem(
                self._format_size(quota.free)
            ))
            self.quota_table.setItem(row, 4, QTableWidgetItem(
                f"{quota.used_percent:.1f}%"
            ))

    def browse_cache_dir(self):
        """浏览缓存目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if dir_path:
            self.cache_dir.setText(dir_path)

    def cancel_selected_task(self):
        """取消选中任务"""
        pass

    def clear_completed_tasks(self):
        """清除已完成任务"""
        pass
