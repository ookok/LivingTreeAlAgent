"""
增强任务管理系统测试
"""

import sys
import time
import asyncio
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTabWidget
from PyQt6.QtCore import QTimer

from core.enhanced_task import TaskManager, TaskStatus, TaskPriority, get_task_manager
from client.src.presentation.panels.enhanced_task_panel import EnhancedTaskPanel


class TestWindow(QMainWindow):
    """测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("增强任务管理系统测试")
        self.setMinimumSize(800, 600)
        
        # 任务管理器
        self.manager = get_task_manager()
        
        # 主容器
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # 测试按钮
        btn_layout = QVBoxLayout()
        
        # 添加任务按钮
        add_btn = QPushButton("➕ 添加测试任务")
        add_btn.clicked.connect(self._add_tasks)
        btn_layout.addWidget(add_btn)
        
        # 添加长任务
        long_btn = QPushButton("⏱️ 添加长时间任务")
        long_btn.clicked.connect(self._add_long_task)
        btn_layout.addWidget(long_btn)
        
        # 批量添加
        batch_btn = QPushButton("📦 批量添加任务")
        batch_btn.clicked.connect(self._add_batch_tasks)
        btn_layout.addWidget(batch_btn)
        
        # 显示统计
        self._stats_label = QLabel("统计: -")
        btn_layout.addWidget(self._stats_label)
        
        layout.addLayout(btn_layout)
        
        # 任务面板
        self._panel = EnhancedTaskPanel(self.manager)
        layout.addWidget(self._panel, 1)
        
        # 刷新统计
        self._update_stats()
        QTimer.singleShot(1000, self._update_stats)
    
    def _update_stats(self):
        """更新统计"""
        stats = self.manager.get_stats()
        self._stats_label.setText(
            f"总计: {stats['total']} | "
            f"等待: {stats['pending']} | "
            f"进行: {stats['running']} | "
            f"暂停: {stats['paused']} | "
            f"完成: {stats['completed']} | "
            f"失败: {stats['failed']}"
        )
        QTimer.singleShot(1000, self._update_stats)
    
    def _add_tasks(self):
        """添加测试任务"""
        def quick_task(ctx, name):
            """快速测试任务"""
            for i in range(10):
                if ctx.check_cancelled():
                    return "被取消"
                if ctx.check_paused():
                    continue
                ctx.report_progress(i * 10, f"处理中 {i+1}/10")
                time.sleep(0.2)
            return f"完成 {name}"
        
        # 添加不同优先级的任务
        task_id = self.manager.create_task(
            title="快速任务",
            handler=quick_task,
            description="这是一个快速测试任务",
            priority=TaskPriority.HIGH,
            metadata={"type": "test"},
            name="快速任务"
        )
        self.manager.execute_task(task_id)
    
    def _add_long_task(self):
        """添加长时间任务"""
        def long_task(ctx, steps=50):
            """长时间任务"""
            for i in range(steps):
                if ctx.check_cancelled():
                    return "被取消"
                if ctx.check_paused():
                    continue
                ctx.report_progress((i + 1) * 100 / steps, f"步骤 {i+1}/{steps}")
                time.sleep(0.1)
            return "长时间任务完成"
        
        task_id = self.manager.create_task(
            title="长时间运行任务",
            handler=long_task,
            description="这个任务需要较长时间完成",
            priority=TaskPriority.NORMAL,
            steps=100
        )
        self.manager.execute_task(task_id)
    
    def _add_batch_tasks(self):
        """批量添加任务"""
        def simple_task(ctx, num):
            """简单任务"""
            for i in range(5):
                if ctx.check_cancelled():
                    return
                ctx.report_progress((i + 1) * 20, f"处理 {i+1}/5")
                time.sleep(0.1)
        
        for i in range(5):
            task_id = self.manager.create_task(
                title=f"批量任务 #{i+1}",
                handler=simple_task,
                description=f"第 {i+1} 个批量任务",
                priority=[TaskPriority.LOW, TaskPriority.NORMAL, TaskPriority.HIGH][i % 3],
                num=i+1
            )
            self.manager.execute_task(task_id)


def test_task_manager():
    """测试任务管理器"""
    print("=" * 50)
    print("测试任务管理器")
    print("=" * 50)
    
    manager = TaskManager(max_concurrent=3)
    
    def sample_task(ctx, name, steps=10):
        """示例任务"""
        for i in range(steps):
            if ctx.check_cancelled():
                print(f"[{name}] 被取消")
                return
            if ctx.check_paused():
                print(f"[{name}] 已暂停，等待恢复...")
                time.sleep(0.1)
                continue
            ctx.report_progress((i + 1) * 100 / steps, f"步骤 {i+1}")
            print(f"[{name}] 进度: {(i+1)*100//steps}%")
            time.sleep(0.2)
        print(f"[{name}] 完成")
        return f"{name} 结果"
    
    # 测试1: 基本创建和执行
    print("\n[测试1] 基本创建和执行")
    task_id = manager.create_task(
        title="测试任务",
        handler=sample_task,
        name="测试任务"
    )
    print(f"  创建任务: {task_id}")
    manager.execute_task(task_id)
    time.sleep(2)
    
    # 测试2: 暂停
    print("\n[测试2] 暂停任务")
    running = manager.get_running_tasks()
    if running:
        print(f"  运行中任务: {len(running)}")
        manager.pause_task(running[0].id)
        time.sleep(1)
        paused = manager.get_paused_tasks()
        print(f"  暂停后状态: {paused[0].state_text if paused else 'N/A'}")
    
    # 测试3: 恢复
    print("\n[测试3] 恢复任务")
    paused = manager.get_paused_tasks()
    if paused:
        manager.resume_task(paused[0].id)
        time.sleep(1)
        print(f"  恢复后状态: {manager.get_task(paused[0].id).state_text}")
    
    # 测试4: 取消
    print("\n[测试4] 取消任务")
    task_id2 = manager.create_task(
        title="可取消任务",
        handler=sample_task,
        name="可取消任务",
        steps=50
    )
    manager.execute_task(task_id2)
    time.sleep(0.5)
    manager.cancel_task(task_id2)
    time.sleep(0.5)
    cancelled = manager.get_tasks_by_status(TaskStatus.CANCELLED)
    print(f"  取消后状态: {cancelled[0].state_text if cancelled else 'N/A'}")
    
    # 测试5: 编辑
    print("\n[测试5] 编辑任务")
    task_id3 = manager.create_task(
        title="可编辑任务",
        handler=sample_task,
        name="编辑测试"
    )
    success = manager.edit_task(
        task_id3,
        title="修改后的标题",
        description="新的描述",
        priority=TaskPriority.HIGH
    )
    print(f"  编辑结果: {'成功' if success else '失败'}")
    task = manager.get_task(task_id3)
    print(f"  新标题: {task.title}")
    print(f"  新优先级: {task.priority_text}")
    
    # 测试6: 重试
    print("\n[测试6] 重试任务")
    if cancelled:
        manager.retry_task(cancelled[0].id)
        time.sleep(0.5)
        print(f"  重试后状态: {manager.get_task(cancelled[0].id).state_text}")
    
    # 等待完成
    time.sleep(3)
    
    # 统计
    print("\n" + "=" * 50)
    print("最终统计")
    print("=" * 50)
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 历史
    print("\n操作历史:")
    for record in manager.get_history()[-5:]:
        print(f"  [{record['action']}] {record['task_id']}")
    
    print("\n✅ 测试完成!")


def test_ui():
    """测试UI"""
    print("\n启动UI测试...")
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    # 先测试核心功能
    test_task_manager()
    
    # 然后测试UI（需要X服务器或Windows）
    # test_ui()
