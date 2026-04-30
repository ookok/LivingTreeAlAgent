"""
Agent Chat + 任务分解集成示例

展示如何在聊天界面中集成智能任务分解功能
"""

from __future__ import annotations

import sys
from typing import Optional, Callable, Iterator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QSplitter, QLabel, QGroupBox,
    QApplication, QMainWindow, QStatusBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QTextCursor

# 添加项目路径
sys.path.insert(0, ".")

from .business.task_execution_engine import (
    SmartDecomposer,
    SmartTaskExecutor,
    TaskContext,
    TaskNode,
    TaskStatus,
    DecompositionDecision,
    ExecutionStrategy,
)
from .business.task_decomposer import SubTask
from .business.agent import HermesAgent, AgentCallbacks
from .business.agent_progress import AgentProgress, ProgressPhase
from .presentation.panels.task_tree_widget import TaskTreeWidget


class AgentChatWithTasks(QMainWindow):
    """
    集成任务分解的 Agent 聊天窗口

    功能：
    1. 聊天输入/输出
    2. 任务分解树显示
    3. 执行进度追踪
    4. 失败重试机制
    """

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_agent()
        self._setup_task_system()

    def _setup_ui(self):
        """初始化 UI"""
        self.setWindowTitle("智能 Agent 助手 - 任务分解版")
        self.resize(1200, 800)

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("Agent 助手")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 模型选择
        self._model_label = QLabel("模型: qwen3.6:latest")
        title_layout.addWidget(self._model_label)

        layout.addLayout(title_layout)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 聊天区域
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)

        # 聊天显示
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setFont(QFont("Microsoft YaHei", 10))
        chat_layout.addWidget(self._chat_display)

        # 输入区域
        input_layout = QHBoxLayout()

        self._input_field = QLineEdit()
        self._input_field.setFont(QFont("Microsoft YaHei", 10))
        self._input_field.setPlaceholderText("输入消息... (复杂任务会自动分解)")
        self._input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._input_field)

        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self._send_btn)

        chat_layout.addLayout(input_layout)

        splitter.addWidget(chat_widget)

        # 任务树区域
        self._task_tree = TaskTreeWidget()
        self._task_tree.set_title("任务分解")
        self._task_tree.task_selected.connect(self._on_task_selected)
        self._task_tree.retry_requested.connect(self._on_retry_requested)
        self._task_tree.skip_requested.connect(self._on_skip_requested)
        self._task_tree.interrupt_requested.connect(self._on_interrupt_requested)
        splitter.addWidget(self._task_tree)

        # 设置分割比例
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # 状态栏
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _setup_agent(self):
        """初始化 Agent"""
        try:
            from .business.config import AppConfig
            config = AppConfig.default()

            # 创建 Agent 回调
            self._callbacks = AgentCallbacks(
                stream_delta=self._on_stream_delta,
                thinking=self._on_thinking,
                progress=self._on_progress,
                task_decomposition=self._on_task_decomposition,
                task_progress=self._on_task_progress,
            )

            # 创建 Agent
            self._agent = HermesAgent(config, callbacks=self._callbacks)
            self._append_chat("system", "Agent initialized")

        except Exception as e:
            self._append_chat("error", f"Agent init failed: {e}")
            self._agent = None

    def _setup_task_system(self):
        """初始化任务系统"""
        self._decomposer = SmartDecomposer(max_depth=3)
        self._executor = SmartTaskExecutor(default_retries=3)
        self._task_context: Optional[TaskContext] = None
        self._task_nodes: list = []

        # 设置执行回调
        self._executor.on_node_start = self._on_executor_node_start
        self._executor.on_node_progress = self._on_executor_node_progress
        self._executor.on_node_complete = self._on_executor_node_complete
        self._executor.on_node_error = self._on_executor_node_error
        self._executor.on_all_complete = self._on_executor_all_complete

    def _on_send(self):
        """发送消息"""
        text = self._input_field.text().strip()
        if not text:
            return

        self._input_field.clear()
        self._append_chat("user", text)

        # 检查是否需要分解
        decision = self._decomposer.should_decompose(text)
        self._append_chat("system", f"[Analysis] Decompose: {decision.should_decompose}")
        self._append_chat("system", f"[Analysis] Confidence: {decision.confidence:.0%}")
        self._append_chat("system", f"[Analysis] Reasons: {', '.join(decision.reasons)}")

        if decision.should_decompose:
            # 执行分解
            self._append_chat("system", f"[Decompose] Strategy: {decision.strategy.value}")
            self._append_chat("system", f"[Decompose] Steps: {decision.estimated_subtasks}")

            # 创建上下文
            self._task_context = TaskContext(original_task=text)

            # 分解任务
            self._task_nodes = self._decomposer.decompose(text, self._task_context, decision)

            # 显示任务树
            self._task_tree.set_nodes(self._task_nodes)
            self._task_tree.set_title(f"Tasks ({len(self._task_nodes)} subtasks)")

            # 开始执行
            self._append_chat("system", "[Execute] Starting tasks...")
            self._execute_tasks(decision.strategy)

        else:
            # 直接调用 Agent
            if self._agent:
                self._append_chat("system", "[Agent] Processing...")
                for chunk in self._agent.send_message(text):
                    pass  # Agent outputs via callbacks

    def _execute_tasks(self, strategy: ExecutionStrategy):
        """执行任务"""
        if not self._task_nodes:
            return

        # 设置任务处理器
        def task_handler(node, context):
            # 更新上下文
            context.original_task = self._task_context.original_task
            context.set_var(f"task_{node.node_id}", node.title)

            # 模拟执行
            self._append_chat("system", f"[Execute] {node.title}...")

            # 根据任务类型生成内容
            result = self._generate_task_result(node.title, context)
            return result

        self._executor.task_handler = task_handler

        # 启动执行线程
        self._execution_thread = ExecutionThread(
            self._executor,
            self._task_nodes,
            self._task_context,
            strategy,
        )
        self._execution_thread.progress.connect(self._on_execution_progress)
        self._execution_thread.finished.connect(self._on_execution_finished)
        self._execution_thread.start()

        self._status_bar.showMessage("Executing...")

    def _generate_task_result(self, title: str, context: TaskContext) -> dict:
        """生成任务结果"""
        return {
            "status": "success",
            "title": title,
            "result": f"Completed: {title}",
            "context_vars": context.variables,
        }

    # ── 回调处理 ─────────────────────────────────────────────────────────

    def _append_chat(self, role: str, text: str):
        """追加聊天消息"""
        if role == "user":
            color = "#1976D2"
            prefix = "You"
        elif role == "assistant":
            color = "#388E3C"
            prefix = "Agent"
        elif role == "system":
            color = "#616161"
            prefix = "System"
        elif role == "error":
            color = "#D32F2F"
            prefix = "Error"
        else:
            color = "#000000"
            prefix = role

        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        cursor.insertHtml(f'<p style="color: {color}; margin: 2px 0;">')
        cursor.insertHtml(f'<b>{prefix}:</b> ')
        cursor.insertHtml(text.replace('\n', '<br>'))
        cursor.insertHtml('</p>')

        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _on_stream_delta(self, delta: str):
        """流式文本回调"""
        pass

    def _on_thinking(self, delta: str):
        """Thinking 回调"""
        pass

    def _on_progress(self, progress: AgentProgress):
        """进度回调"""
        pass

    def _on_task_decomposition(self, decomposition):
        """分解完成回调"""
        self._append_chat("system", f"[Decompose] Generated {len(decomposition.subtasks)} subtasks")

    def _on_task_progress(self, state):
        """任务进度回调"""
        self._task_tree.update_node(state)

    def _on_executor_node_start(self, node):
        """节点开始执行"""
        self._append_chat("system", f"[Start] {node.title}")

    def _on_executor_node_progress(self, node, progress: float):
        """节点进度更新"""
        self._task_tree.update_node(node)

    def _on_executor_node_complete(self, node):
        """节点执行完成"""
        self._append_chat("system", f"[Complete] {node.title} ({node.duration:.2f}s)")
        self._task_tree.update_node(node)

    def _on_executor_node_error(self, node, error: str):
        """节点执行错误"""
        self._append_chat("error", f"[Error] {node.title}: {error}")
        self._task_tree.update_node(node)

    def _on_executor_all_complete(self, context: TaskContext):
        """所有任务完成"""
        self._append_chat("system", "[Complete] All tasks finished")

    @pyqtSlot(dict)
    def _on_execution_progress(self, summary: dict):
        """执行进度更新"""
        self._task_tree.update_progress(summary)
        self._status_bar.showMessage(
            f"Executing: {summary['completed']}/{summary['total']} "
            f"({summary['success_rate']:.0%})"
        )

    @pyqtSlot()
    def _on_execution_finished(self):
        """执行完成"""
        self._status_bar.showMessage("Finished")
        summary = self._executor.get_execution_summary(self._task_nodes)
        self._append_chat("system", f"[Summary] Success: {summary['completed']}, Failed: {summary['failed']}")

    def _on_task_selected(self, node_id: str, node_data: dict):
        """任务被选中"""
        pass

    def _on_retry_requested(self, node_id: str):
        """重试请求"""
        for node in self._task_nodes:
            if node.node_id == node_id:
                node.status = TaskStatus.PENDING
                node.retry_count += 1
                node.error = None
                self._task_tree.update_node(node)
                self._append_chat("system", f"[Retry] {node.title}")
                break

    def _on_skip_requested(self, node_id: str):
        """跳过请求"""
        for node in self._task_nodes:
            if node.node_id == node_id:
                node.status = TaskStatus.SKIPPED
                self._task_tree.update_node(node)
                self._append_chat("system", f"[Skip] {node.title}")
                break

    def _on_interrupt_requested(self):
        """中断请求"""
        self._executor.interrupt()
        self._append_chat("system", "[Interrupt] Task interrupted")


class ExecutionThread(QThread):
    """执行线程"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, executor, nodes, context, strategy):
        super().__init__()
        self.executor = executor
        self.nodes = nodes
        self.context = context
        self.strategy = strategy

    def run(self):
        """执行任务"""
        try:
            for state in self.executor.execute_stream(
                self.nodes,
                self.context,
                self.strategy,
            ):
                summary = self.executor.get_execution_summary(self.nodes)
                self.progress.emit(summary)

        finally:
            self.finished.emit()


# ── 入口 ─────────────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    window = AgentChatWithTasks()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
