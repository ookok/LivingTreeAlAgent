"""
任务队列系统演示
Task Queue System Demo

运行方式：
    python examples/demo_task_queue.py
"""

import time
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QTabWidget
from PyQt6.QtCore import Qt

from core.task_queue import (
    TaskQueue, TaskQueuePanel, QueuePriority,
    QueuedTask, get_task_queue, create_task_queue
)


class DemoWindow(QMainWindow):
    """演示窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("任务队列系统演示")
        self.setGeometry(100, 100, 800, 600)

        # 创建任务队列
        self.queue = create_task_queue("demo", max_concurrent=2, persist=False)

        # UI
        self._setup_ui()

        # 连接信号
        self._connect_signals()

    def _setup_ui(self):
        """设置UI"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 控制按钮
        btn_layout = QVBoxLayout()

        add_btn = QPushButton("添加模拟任务（普通）")
        add_btn.clicked.connect(self._add_normal_task)
        btn_layout.addWidget(add_btn)

        add_high_btn = QPushButton("添加高优先级任务")
        add_high_btn.clicked.connect(self._add_high_priority_task)
        btn_layout.addWidget(add_high_btn)

        add_low_btn = QPushButton("添加低优先级任务")
        add_low_btn.clicked.connect(self._add_low_priority_task)
        btn_layout.addWidget(add_low_btn)

        add_batch_btn = QPushButton("批量添加5个任务")
        add_batch_btn.clicked.connect(self._add_batch_tasks)
        btn_layout.addWidget(add_batch_btn)

        btn_layout.addSpacing(20)

        clear_btn = QPushButton("清空已完成")
        clear_btn.clicked.connect(self.queue.clear_completed)
        btn_layout.addWidget(clear_btn)

        pause_btn = QPushButton("暂停/恢复")
        pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(pause_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 队列面板
        self.panel = TaskQueuePanel(self.queue)
        layout.addWidget(self.panel)

    def _connect_signals(self):
        """连接信号"""
        self.queue.task_completed.connect(self._on_task_completed)
        self.queue.task_failed.connect(self._on_task_failed)
        self.queue.all_completed.connect(self._on_all_completed)

    def _add_normal_task(self):
        """添加普通任务"""
        task_id = self.queue.add(
            title=f"任务 #{self.queue._stats['total'] + 1}",
            handler=self._simulate_task,
            description="模拟处理任务",
            priority=QueuePriority.NORMAL,
        )

    def _add_high_priority_task(self):
        """添加高优先级任务"""
        task_id = self.queue.add(
            title=f"[高优] 任务 #{self.queue._stats['total'] + 1}",
            handler=self._simulate_task,
            description="高优先级任务",
            priority=QueuePriority.HIGH,
        )

    def _add_low_priority_task(self):
        """添加低优先级任务"""
        task_id = self.queue.add(
            title=f"[低优] 任务 #{self.queue._stats['total'] + 1}",
            handler=self._simulate_task,
            description="低优先级任务",
            priority=QueuePriority.LOW,
        )

    def _add_batch_tasks(self):
        """批量添加任务"""
        for i in range(5):
            self.queue.add(
                title=f"批量任务 #{i + 1}",
                handler=self._simulate_task,
                description=f"批量处理 #{i + 1}",
                priority=QueuePriority.NORMAL,
            )

    def _toggle_pause(self):
        """切换暂停状态"""
        if self.queue._auto_start:
            self.queue.pause()
        else:
            self.queue.resume()

    def _simulate_task(self):
        """模拟任务处理"""
        import random
        time.sleep(random.uniform(1, 3))
        return {"status": "ok", "timestamp": time.time()}

    def _on_task_completed(self, task_id: str, result):
        """任务完成"""
        print(f"Task {task_id} completed: {result}")

    def _on_task_failed(self, task_id: str, error: str):
        """任务失败"""
        print(f"Task {task_id} failed: {error}")

    def _on_all_completed(self):
        """所有任务完成"""
        print("All tasks completed!")


def demo_cli():
    """命令行演示"""
    print("=" * 50)
    print("任务队列系统 CLI 演示")
    print("=" * 50)

    # 创建队列
    queue = TaskQueue("cli_demo", max_concurrent=2, persist=False)

    # 添加任务
    print("\n1. 添加3个任务...")
    for i in range(3):
        queue.add(
            title=f"CLI任务 #{i + 1}",
            handler=lambda: time.sleep(0.5),
            description=f"命令行测试任务 {i + 1}",
            priority=QueuePriority.NORMAL,
        )
        print(f"   添加任务: CLI任务 #{i + 1}")

    print("\n2. 等待队列处理...")
    stats = {"total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0}
    while not queue.is_empty():
        stats = queue.get_stats()
        print(f"   状态: pending={stats['pending']}, running={stats['running']}, completed={stats['completed']}")
        time.sleep(0.3)

    stats = queue.get_stats()
    print("\n3. 队列处理完成!")
    print(f"   总计: {stats['total']}, 完成: {stats['completed']}, 失败: {stats['failed']}")

    print("\n" + "=" * 50)
    print("CLI 演示完成")
    print("=" * 50)


if __name__ == "__main__":
    # CLI 演示
    demo_cli()

    # GUI 演示（可选）
    # app = QApplication(sys.argv)
    # window = DemoWindow()
    # window.show()
    # sys.exit(app.exec())
