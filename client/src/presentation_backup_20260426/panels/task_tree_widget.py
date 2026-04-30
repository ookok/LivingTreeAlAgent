"""
PyQt6 任务树可视化组件

功能：
1. 树形显示任务分解结构
2. 实时进度更新
3. 状态颜色区分
4. 失败重试按钮
5. 任务节点展开/折叠
6. 执行时间显示
"""

from __future__ import annotations

from typing import Optional, Callable, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QProgressBar, QStyle, QHeaderView,
    QAbstractItemView, QSplitter, QTextEdit, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor

# 状态颜色
STATUS_COLORS = {
    "pending": QColor("#9E9E9E"),    # 灰色
    "running": QColor("#2196F3"),     # 蓝色
    "completed": QColor("#4CAF50"),   # 绿色
    "failed": QColor("#F44336"),     # 红色
    "retrying": QColor("#FF9800"),   # 橙色
    "skipped": QColor("#607D8B"),    # 蓝灰色
    "waiting": QColor("#FFC107"),     # 黄色
}

STATUS_ICONS = {
    "pending": "⭕",
    "running": "🔄",
    "completed": "✅",
    "failed": "❌",
    "retrying": "🔁",
    "skipped": "⏭️",
    "waiting": "⏳",
}


class TaskTreeWidget(QWidget):
    """
    任务树可视化组件

    Signals:
        task_selected: 任务被选中 (node_id, node_data)
        retry_requested: 重试请求 (node_id)
        skip_requested: 跳过请求 (node_id)
        interrupt_requested: 中断请求
    """

    task_selected = pyqtSignal(str, dict)
    retry_requested = pyqtSignal(str)
    skip_requested = pyqtSignal(str)
    interrupt_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: Dict[str, Any] = {}
        self._tree_items: Dict[str, QTreeWidgetItem] = {}

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar = QHBoxLayout()

        self._title_label = QLabel("任务分解")
        self._title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        toolbar.addWidget(self._title_label)

        toolbar.addStretch()

        # 进度标签
        self._progress_label = QLabel("0/0 完成")
        self._progress_label.setFont(QFont("Consolas", 9))
        toolbar.addWidget(self._progress_label)

        # 重试按钮
        self._retry_btn = QPushButton("🔁 重试失败")
        self._retry_btn.setEnabled(False)
        self._retry_btn.clicked.connect(self._on_retry_failed)
        toolbar.addWidget(self._retry_btn)

        # 跳过按钮
        self._skip_btn = QPushButton("⏭️ 跳过")
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self._on_skip_failed)
        toolbar.addWidget(self._skip_btn)

        # 中断按钮
        self._interrupt_btn = QPushButton("⏹️ 中断")
        self._interrupt_btn.setEnabled(False)
        self._interrupt_btn.clicked.connect(self._on_interrupt)
        toolbar.addWidget(self._interrupt_btn)

        layout.addLayout(toolbar)

        # 任务树
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["状态", "任务", "进度", "耗时", "错误"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemCollapsed.connect(self._on_item_collapsed)

        # 列宽调整
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 120)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 80)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 150)

        layout.addWidget(self._tree)

        # 详情面板
        self._detail_group = QGroupBox("任务详情")
        detail_layout = QVBoxLayout()

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(150)
        detail_layout.addWidget(self._detail_text)

        self._detail_group.setLayout(detail_layout)
        layout.addWidget(self._detail_group)

    def _init_timer(self):
        """初始化定时器"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_running_items)

    def _update_running_items(self):
        """更新正在运行的项目"""
        for node_id, item in self._tree_items.items():
            node = self._nodes.get(node_id)
            if node and node.get("status") == "running":
                # 刷新进度显示
                progress = node.get("progress", 0)
                self._update_item_progress(item, progress)

    def set_title(self, title: str):
        """设置标题"""
        self._title_label.setText(title)

    def set_nodes(self, nodes: List[Any]):
        """
        设置任务节点

        Args:
            nodes: TaskNode 列表
        """
        self._tree.clear()
        self._nodes.clear()
        self._tree_items.clear()

        # 构建映射
        for node in nodes:
            node_dict = node.to_dict() if hasattr(node, 'to_dict') else node
            self._nodes[node_dict["node_id"]] = node_dict

        # 构建树
        root_items = []
        for node in nodes:
            node_dict = node.to_dict() if hasattr(node, 'to_dict') else node
            parent_id = node_dict.get("parent_id")

            if parent_id is None:
                item = self._create_tree_item(node_dict)
                root_items.append(item)
            else:
                parent_item = self._tree_items.get(parent_id)
                if parent_item:
                    item = self._create_tree_item(node_dict)
                    parent_item.addChild(item)

        # 添加到树
        self._tree.addTopLevelItems(root_items)

        # 展开所有
        self._tree.expandAll()

        # 更新按钮状态
        self._update_button_states()

    def _create_tree_item(self, node_dict: Dict) -> QTreeWidgetItem:
        """创建树节点"""
        item = QTreeWidgetItem()

        node_id = node_dict["node_id"]
        self._tree_items[node_id] = item

        # 状态列
        status = node_dict.get("status", "pending")
        status_text = f" {STATUS_ICONS.get(status, '❓')} {status}"
        item.setText(0, status_text)
        item.setForeground(0, STATUS_COLORS.get(status, QColor("#000")))

        # 任务列
        title = node_dict.get("title", "")
        depth = node_dict.get("depth", 0)
        indent = "  " * depth + "└─ " if depth > 0 else ""
        item.setText(1, indent + title)

        # 进度列
        self._update_item_progress(item, node_dict.get("progress", 0))

        # 耗时列
        duration = node_dict.get("duration", 0)
        if duration > 0:
            item.setText(3, f"{duration:.2f}s")

        # 错误列
        if node_dict.get("has_error"):
            error = node_dict.get("error", "未知错误")
            item.setText(4, error[:20] + "..." if len(error) > 20 else error)
            item.setForeground(4, STATUS_COLORS["failed"])

        return item

    def _update_item_progress(self, item: QTreeWidgetItem, progress: float):
        """更新进度列"""
        if progress >= 100:
            progress_text = "██████████ 100%"
        elif progress >= 90:
            progress_text = "█████████░ 90%"
        elif progress >= 80:
            progress_text = "████████░░ 80%"
        elif progress >= 70:
            progress_text = "███████░░░ 70%"
        elif progress >= 60:
            progress_text = "██████░░░░ 60%"
        elif progress >= 50:
            progress_text = "█████░░░░░ 50%"
        elif progress >= 40:
            progress_text = "████░░░░░░ 40%"
        elif progress >= 30:
            progress_text = "███░░░░░░░ 30%"
        elif progress >= 20:
            progress_text = "██░░░░░░░░ 20%"
        elif progress >= 10:
            progress_text = "█░░░░░░░░░ 10%"
        else:
            progress_text = "░░░░░░░░░░ 0%"

        item.setText(2, progress_text)

    def update_node(self, node: Any):
        """更新单个节点"""
        node_dict = node.to_dict() if hasattr(node, 'to_dict') else node
        node_id = node_dict["node_id"]

        self._nodes[node_id] = node_dict

        item = self._tree_items.get(node_id)
        if item:
            # 更新状态
            status = node_dict.get("status", "pending")
            item.setText(0, f" {STATUS_ICONS.get(status, '❓')} {status}")
            item.setForeground(0, STATUS_COLORS.get(status, QColor("#000")))

            # 更新进度
            self._update_item_progress(item, node_dict.get("progress", 0))

            # 更新耗时
            duration = node_dict.get("duration", 0)
            item.setText(3, f"{duration:.2f}s" if duration > 0 else "")

            # 更新错误
            if node_dict.get("has_error"):
                error = node_dict.get("error", "")
                item.setText(4, error[:20] + "..." if len(error) > 20 else error)
                item.setForeground(4, STATUS_COLORS["failed"])

        # 更新详情
        if self._tree.currentItem() == item:
            self._show_detail(node_dict)

        # 更新按钮状态
        self._update_button_states()

    def update_progress(self, summary: Dict[str, Any]):
        """更新总进度"""
        completed = summary.get("completed", 0)
        total = summary.get("total", 0)
        self._progress_label.setText(f"{completed}/{total} 完成")

        # 进度条样式
        if total > 0:
            percentage = int(completed / total * 100)
            self._progress_label.setStyleSheet(
                f"color: {'green' if percentage == 100 else 'blue'};"
            )

    def _update_button_states(self):
        """更新按钮状态"""
        has_failed = any(n.get("status") == "failed" for n in self._nodes.values())
        has_running = any(n.get("status") == "running" for n in self._nodes.values())

        self._retry_btn.setEnabled(has_failed)
        self._skip_btn.setEnabled(has_failed)
        self._interrupt_btn.setEnabled(has_running)

        # 启动/停止定时器
        if has_running and not self._timer.isActive():
            self._timer.start(500)
        elif not has_running and self._timer.isActive():
            self._timer.stop()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """项目被点击"""
        # 找到对应的节点
        for node_id, tree_item in self._tree_items.items():
            if tree_item == item:
                node = self._nodes.get(node_id)
                if node:
                    self._show_detail(node)
                    self.task_selected.emit(node_id, node)
                break

    def _show_detail(self, node: Dict):
        """显示详情"""
        detail = f"""【{node.get('title', '未知')}】

状态: {node.get('status', 'pending')}
进度: {node.get('progress', 0):.0f}%
耗时: {node.get('duration', 0):.2f}s

描述:
{node.get('description', '无')}

"""

        if node.get("has_error"):
            detail += f"错误:\n{node.get('error', '未知错误')}"

        if node.get("result"):
            result = node.get("result")
            if isinstance(result, dict):
                detail += f"\n结果:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
            else:
                detail += f"\n结果:\n{result}"

        self._detail_text.setPlainText(detail)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """项目展开"""
        pass

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """项目折叠"""
        pass

    def _on_retry_failed(self):
        """重试失败任务"""
        for node_id, node in self._nodes.items():
            if node.get("status") == "failed":
                self.retry_requested.emit(node_id)

    def _on_skip_failed(self):
        """跳过失败任务"""
        for node_id, node in self._nodes.items():
            if node.get("status") == "failed":
                self.skip_requested.emit(node_id)

    def _on_interrupt(self):
        """中断执行"""
        self.interrupt_requested.emit()

    def expand_all(self):
        """展开所有"""
        self._tree.expandAll()

    def collapse_all(self):
        """折叠所有"""
        self._tree.collapseAll()


# ── 简化版本：内联显示 ───────────────────────────────────────────────────────


class InlineTaskDisplay(QWidget):
    """
    内联任务显示（用于聊天界面）

    直接在聊天消息中显示任务分解状态
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: List[Dict] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def set_nodes(self, nodes: List[Any]):
        """设置任务节点"""
        self._nodes = [n.to_dict() if hasattr(n, 'to_dict') else n for n in nodes]
        self._update_display()

    def update_node(self, node: Any):
        """更新节点"""
        node_dict = node.to_dict() if hasattr(node, 'to_dict') else node
        node_id = node_dict["node_id"]

        for i, n in enumerate(self._nodes):
            if n["node_id"] == node_id:
                self._nodes[i] = node_dict
                break

        self._update_display()

    def _update_display(self):
        """更新显示"""
        # 清除现有内容
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 构建显示
        for node in self._nodes:
            status = node.get("status", "pending")
            title = node.get("title", "")
            progress = node.get("progress", 0)
            icon = STATUS_ICONS.get(status, "❓")

            # 深度缩进
            depth = node.get("depth", 0)
            indent = "    " * depth

            # 进度条
            bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))

            text = f"{indent}{icon} {title} [{bar}] {progress:.0f}%"

            label = QLabel(text)
            label.setStyleSheet(f"color: {STATUS_COLORS.get(status, '#000').name()};")
            self._layout.addWidget(label)


# ── 测试 ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    import json
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建窗口
    window = TaskTreeWidget()
    window.setWindowTitle("任务树组件测试")
    window.resize(800, 600)

    # 添加测试数据
    from .business.task_execution_engine import TaskNode, TaskStatus

    nodes = [
        TaskNode(node_id="root", title="实现用户认证系统", depth=0),
        TaskNode(node_id="1", title="设计数据库结构", depth=1, parent_id="root"),
        TaskNode(node_id="2", title="实现注册功能", depth=1, parent_id="root"),
        TaskNode(node_id="3", title="实现登录功能", depth=1, parent_id="root", depends_on=["2"]),
        TaskNode(node_id="4", title="实现权限管理", depth=1, parent_id="root", depends_on=["3"]),
    ]

    # 设置一些状态
    nodes[1].status = TaskStatus.COMPLETED
    nodes[1].progress = 100
    nodes[1].duration = 2.5

    nodes[2].status = TaskStatus.RUNNING
    nodes[2].progress = 65

    window.set_nodes(nodes)
    window.set_title("用户认证系统 - 实现中")

    window.show()

    sys.exit(app.exec())
