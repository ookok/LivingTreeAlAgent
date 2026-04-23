"""
Task Decompose Panel - 任务分解面板
集成智能任务分解、树形显示、失败恢复到现有 UI
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QFrame,
    QAbstractItemView, QSizePolicy, QMenu, QToolButton,
)
from PyQt6.QtGui import QFont, QAction, QIcon

from core.task_execution_engine import (
    SmartDecomposer, SmartTaskExecutor, TaskContext,
    TaskNode, ExecutionStrategy, TaskStatus
)

# TaskState 作为 TaskStatus 的别名（兼容旧代码）
TaskState = TaskStatus


class TaskNodeState:
    """任务节点状态枚举（兼容 UI 组件）"""
    PENDING = TaskStatus.PENDING
    RUNNING = TaskStatus.RUNNING
    COMPLETED = TaskStatus.COMPLETED
    FAILED = TaskStatus.FAILED
    SKIPPED = TaskStatus.SKIPPED
    CANCELLED = TaskStatus.SKIPPED  # CANCELLED 映射到 SKIPPED

    @classmethod
    def value(cls, status: TaskStatus = None):
        """获取状态值"""
        if status:
            return status.value
        return "pending"


class TaskTreeItem(QTreeWidgetItem):
    """任务树项"""

    # 状态图标映射
    STATE_ICONS = {
        TaskNodeState.PENDING: "⏳",
        TaskNodeState.RUNNING: "🔄",
        TaskNodeState.COMPLETED: "✅",
        TaskNodeState.FAILED: "❌",
        TaskNodeState.SKIPPED: "⏭️",
        TaskNodeState.CANCELLED: "🚫",
    }

    def __init__(self, node: TaskNode, parent=None):
        super().__init__(parent)
        self.node = node
        self._update_display()

    def _update_display(self):
        """更新显示"""
        # 状态图标
        icon = self.STATE_ICONS.get(self.node.state, "❓")

        # 名称（带缩进表示层级）
        indent = "  " * self.node.depth
        self.setText(0, f"{icon} {indent}{self.node.title}")

        # 状态
        self.setText(1, self.node.state.value)

        # 进度
        if self.node.state == TaskNodeState.RUNNING:
            progress = f"{self.node.progress:.0f}%"
        elif self.node.state == TaskNodeState.COMPLETED:
            progress = "100%"
        else:
            progress = "0%"

        self.setText(2, progress)

        # 耗时
        if self.node.end_time > 0:
            duration = self.node.end_time - self.node.start_time
            self.setText(3, f"{duration:.1f}s")
        else:
            self.setText(3, "-")

        # 错误
        if self.node.error:
            self.setText(4, "⚠️")
            self.setToolTip(4, self.node.error)
        else:
            self.setText(4, "")

    def update_state(self):
        """更新状态"""
        self._update_display()


class TaskDecomposePanel(QFrame):
    """
    任务分解面板

    信号:
        task_selected(node_id: str)
        retry_requested(node_id: str)
        skip_requested(node_id: str)
        interrupt_requested()
        expand_all_requested()
        collapse_all_requested()
    """

    task_selected = pyqtSignal(str)       # 任务节点选中
    retry_requested = pyqtSignal(str)     # 重试请求
    skip_requested = pyqtSignal(str)      # 跳过请求
    interrupt_requested = pyqtSignal()     # 中断请求
    expand_all_requested = pyqtSignal()   # 展开全部
    collapse_all_requested = pyqtSignal() # 折叠全部

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskDecomposePanel")
        self._nodes: dict[str, TaskNode] = {}
        self._items: dict[str, TaskTreeItem] = {}

        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # ── 标题栏 ─────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        self.title_lbl = QLabel("📊 任务分解")
        self.title_lbl.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #F1F5F9;")
        header.addWidget(self.title_lbl)

        header.addStretch()

        # 折叠/展开按钮
        self.expand_btn = QToolButton()
        self.expand_btn.setText("🔽")
        self.expand_btn.setToolTip("展开全部")
        self.expand_btn.clicked.connect(self._expand_all)
        header.addWidget(self.expand_btn)

        # 重试按钮
        self.retry_btn = QPushButton("🔁")
        self.retry_btn.setToolTip("重试失败任务")
        self.retry_btn.setFixedSize(32, 24)
        self.retry_btn.clicked.connect(self._retry_failed)
        header.addWidget(self.retry_btn)

        # 跳过按钮
        self.skip_btn = QPushButton("⏭️")
        self.skip_btn.setToolTip("跳过失败任务")
        self.skip_btn.setFixedSize(32, 24)
        self.skip_btn.clicked.connect(self._skip_failed)
        header.addWidget(self.skip_btn)

        # 中断按钮
        self.stop_btn = QPushButton("⏹️")
        self.stop_btn.setToolTip("中断执行")
        self.stop_btn.setFixedSize(32, 24)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #EF4444;
            }
        """)
        self.stop_btn.clicked.connect(self._interrupt)
        header.addWidget(self.stop_btn)

        layout.addLayout(header)

        # ── 进度条 ─────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E293B;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # ── 统计信息 ─────────────────────────────────────────────────
        self.stats_lbl = QLabel("共 0 个任务 | 已完成 0 | 失败 0 | 进行中 0")
        self.stats_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.stats_lbl)

        # ── 任务树 ─────────────────────────────────────────────────
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["任务", "状态", "进度", "耗时", ""])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setAnimated(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #E2E8F0;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #334155;
            }
            QTreeWidget::item:hover {
                background-color: #263344;
            }
            QTreeWidget::branch {
                background-color: #1E293B;
            }
            QHeaderView::section {
                background-color: #0F172A;
                color: #94A3B8;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.tree)

        # ── 底部操作栏 ─────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(8)

        # 原任务标签
        self.task_lbl = QLabel()
        self.task_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.task_lbl.setWordWrap(True)
        self.task_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        footer.addWidget(self.task_lbl)

        # 策略标签
        self.strategy_lbl = QLabel()
        self.strategy_lbl.setStyleSheet("""
            color: #10B981;
            font-size: 11px;
            background-color: #064E3B;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        footer.addWidget(self.strategy_lbl)

        layout.addLayout(footer)

    def set_task(self, original_task: str, nodes: list[TaskNode] = None):
        """
        设置任务

        Args:
            original_task: 原始任务描述
            nodes: 任务节点列表（可选）
        """
        self._nodes.clear()
        self._items.clear()

        # 设置标题
        self.task_lbl.setText(f"📋 {original_task}")

        if nodes:
            self._build_tree(nodes)

    def _build_tree(self, nodes: list[TaskNode]):
        """构建任务树"""
        self.tree.clear()
        self._nodes = {n.node_id: n for n in nodes}
        self._items.clear()

        # 按层级构建
        root_items = []

        for node in nodes:
            item = TaskTreeItem(node)
            self._items[node.node_id] = item

            if node.parent_id and node.parent_id in self._items:
                self._items[node.parent_id].addChild(item)
            else:
                root_items.append(item)

        self.tree.addTopLevelItems(root_items)

        # 展开第一层
        for item in root_items:
            item.setExpanded(True)

        self._update_stats()

    def update_node(self, node_id: str):
        """更新节点状态"""
        if node_id in self._items:
            self._items[node_id].update_state()

        self._update_stats()
        self._update_progress()

    def _update_stats(self):
        """更新统计信息"""
        if not self._nodes:
            self.stats_lbl.setText("共 0 个任务 | 已完成 0 | 失败 0 | 进行中 0")
            return

        total = len(self._nodes)
        completed = sum(1 for n in self._nodes.values() if n.state == TaskNodeState.COMPLETED)
        failed = sum(1 for n in self._nodes.values() if n.state == TaskNodeState.FAILED)
        running = sum(1 for n in self._nodes.values() if n.state == TaskNodeState.RUNNING)

        self.stats_lbl.setText(
            f"共 {total} 个任务 | 已完成 {completed} | 失败 {failed} | 进行中 {running}"
        )

    def _update_progress(self):
        """更新进度条"""
        if not self._nodes:
            self.progress_bar.setValue(0)
            return

        total = len(self._nodes)
        completed = sum(1 for n in self._nodes.values() if n.state == TaskNodeState.COMPLETED)
        progress = int(completed / total * 100)
        self.progress_bar.setValue(progress)

    def _on_item_clicked(self, item, column):
        """项目点击"""
        if isinstance(item, TaskTreeItem):
            self.task_selected.emit(item.node.node_id)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.tree.itemAt(pos)
        if not isinstance(item, TaskTreeItem):
            return

        menu = QMenu(self)

        # 展开/折叠
        expand_action = QAction("🔽 展开", self)
        expand_action.triggered.connect(lambda: item.setExpanded(True))
        menu.addAction(expand_action)

        collapse_action = QAction("🔼 折叠", self)
        collapse_action.triggered.connect(lambda: item.setExpanded(False))
        menu.addAction(collapse_action)

        menu.addSeparator()

        # 重试
        if item.node.state == TaskNodeState.FAILED:
            retry_action = QAction("🔁 重试此任务", self)
            retry_action.triggered.connect(lambda: self.retry_requested.emit(item.node.node_id))
            menu.addAction(retry_action)

        # 跳过
        if item.node.state in (TaskNodeState.FAILED, TaskNodeState.RUNNING):
            skip_action = QAction("⏭️ 跳过此任务", self)
            skip_action.triggered.connect(lambda: self.skip_requested.emit(item.node.node_id))
            menu.addAction(skip_action)

        # 复制描述
        copy_action = QAction("📋 复制描述", self)
        copy_action.triggered.connect(lambda: self._copy_description(item.node))
        menu.addAction(copy_action)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _copy_description(self, node: TaskNode):
        """复制描述"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(f"{node.title}\n{node.description}")

    def _expand_all(self):
        """展开全部"""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setExpanded(True)
            self._expand_children(item, True)

    def _collapse_all(self):
        """折叠全部"""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setExpanded(False)
            self._expand_children(item, False)

    def _expand_children(self, item, expand: bool):
        """递归设置子项展开状态"""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setExpanded(expand)
            self._expand_children(child, expand)

    def _retry_failed(self):
        """重试失败任务"""
        for node_id, item in self._items.items():
            if item.node.state == TaskNodeState.FAILED:
                self.retry_requested.emit(node_id)

    def _skip_failed(self):
        """跳过失败任务"""
        for node_id, item in self._items.items():
            if item.node.state == TaskNodeState.FAILED:
                self.skip_requested.emit(node_id)

    def _interrupt(self):
        """中断执行"""
        self.interrupt_requested.emit()

    def set_strategy(self, strategy: ExecutionStrategy):
        """设置执行策略标签"""
        strategy_text = {
            ExecutionStrategy.SEQUENTIAL: "📝 串行",
            ExecutionStrategy.PARALLEL: "⚡ 并行",
            ExecutionStrategy.DAG: "🔀 DAG",
        }.get(strategy, "📋 默认")

        self.strategy_lbl.setText(strategy_text)

    def set_readonly(self, readonly: bool):
        """设置只读模式"""
        self.retry_btn.setEnabled(not readonly)
        self.skip_btn.setEnabled(not readonly)
        self.stop_btn.setEnabled(not readonly)


class TaskDecomposeManager:
    """任务分解管理器 - 管理任务分解面板的生命周期"""

    def __init__(self, panel: TaskDecomposePanel, executor: SmartTaskExecutor = None):
        self.panel = panel
        self.executor = executor or SmartTaskExecutor(default_retries=3)
        self.context: TaskContext = None
        self.nodes: list[TaskNode] = []
        self._running = False

        # 连接信号
        self.panel.retry_requested.connect(self._on_retry)
        self.panel.skip_requested.connect(self._on_skip)
        self.panel.interrupt_requested.connect(self._on_interrupt)

    def start_task(self, task: str, nodes: list[TaskNode], strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL):
        """开始任务"""
        self.nodes = nodes
        self.context = TaskContext(original_task=task)
        self._running = True

        self.panel.set_task(task, nodes)
        self.panel.set_strategy(strategy)
        self.panel.set_readonly(False)

    def update_progress(self):
        """更新进度"""
        for node in self.nodes:
            self.panel.update_node(node.node_id)

    def finish_task(self):
        """完成任务"""
        self._running = False
        self.panel.set_readonly(True)

    def _on_retry(self, node_id: str):
        """处理重试"""
        if node_id in {n.node_id for n in self.nodes}:
            node = next(n for n in self.nodes if n.node_id == node_id)
            node.reset()
            self.panel.update_node(node_id)

    def _on_skip(self, node_id: str):
        """处理跳过"""
        if node_id in {n.node_id for n in self.nodes}:
            node = next(n for n in self.nodes if n.node_id == node_id)
            node.skip()
            self.panel.update_node(node_id)

    def _on_interrupt(self):
        """处理中断"""
        self.executor.interrupt()
        self._running = False
