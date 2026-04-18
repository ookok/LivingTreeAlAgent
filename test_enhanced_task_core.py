"""
增强任务管理系统测试 - 简化版
"""

import sys
import time
import os

# 编码设置
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(__file__).rsplit('/', 1)[0] if '/' in __file__ else '.')

from core.enhanced_task import TaskManager, TaskStatus, TaskPriority, get_task_manager


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
                print(f"[{name}] 已暂停")
                time.sleep(0.1)
                continue
            ctx.report_progress((i + 1) * 100 / steps, f"step {i+1}")
            print(f"[{name}] {int((i+1)*100/steps)}%")
            time.sleep(0.2)
        print(f"[{name}] done")
        return f"{name} result"
    
    # Test 1: Create and execute
    print("\n[Test1] Create and execute")
    task_id = manager.create_task(
        title="Test Task",
        handler=sample_task,
        name="Test Task"
    )
    print(f"  Task ID: {task_id}")
    manager.execute_task(task_id)
    time.sleep(2)
    
    # Test 2: Pause
    print("\n[Test2] Pause")
    running = manager.get_running_tasks()
    if running:
        print(f"  Running: {len(running)}")
        manager.pause_task(running[0].id)
        time.sleep(1)
        paused = manager.get_paused_tasks()
        if paused:
            print(f"  After pause: {paused[0].state_text}")
    
    # Test 3: Resume
    print("\n[Test3] Resume")
    paused = manager.get_paused_tasks()
    if paused:
        manager.resume_task(paused[0].id)
        time.sleep(1)
        task = manager.get_task(paused[0].id)
        if task:
            print(f"  After resume: {task.state_text}")
    
    # Test 4: Cancel
    print("\n[Test4] Cancel")
    task_id2 = manager.create_task(
        title="Cancellable Task",
        handler=sample_task,
        name="Cancellable",
        steps=50
    )
    manager.execute_task(task_id2)
    time.sleep(0.5)
    manager.cancel_task(task_id2)
    time.sleep(0.5)
    cancelled = manager.get_tasks_by_status(TaskStatus.CANCELLED)
    if cancelled:
        print(f"  After cancel: {cancelled[0].state_text}")
    
    # Test 5: Edit
    print("\n[Test5] Edit")
    task_id3 = manager.create_task(
        title="Editable Task",
        handler=sample_task,
        name="Edit Test"
    )
    success = manager.edit_task(
        task_id3,
        title="Modified Title",
        description="New description",
        priority=TaskPriority.HIGH
    )
    print(f"  Edit result: {'OK' if success else 'FAIL'}")
    task = manager.get_task(task_id3)
    if task:
        print(f"  New title: {task.title}")
        print(f"  Priority: {task.priority_text}")
    
    # Test 6: Retry
    print("\n[Test6] Retry")
    if cancelled:
        manager.retry_task(cancelled[0].id)
        time.sleep(0.5)
        task = manager.get_task(cancelled[0].id)
        if task:
            print(f"  After retry: {task.state_text}")
    
    # Wait for completion
    time.sleep(3)
    
    # Stats
    print("\n" + "=" * 50)
    print("Final Stats")
    print("=" * 50)
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # History
    print("\nHistory:")
    for record in manager.get_history()[-5:]:
        print(f"  [{record['action']}] {record['task_id']}")
    
    print("\nTEST PASSED!")


if __name__ == "__main__":
    test_task_manager()
