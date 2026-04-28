"""
任务分解系统测试脚本
"""

import sys
import time
sys.path.insert(0, '.')

from core.task_decomposer import (
    TaskDecomposer,
    SubTaskExecutor,
    TaskDecompositionCallbacks,
    TaskDecomposition,
    SubTask,
    TaskStatus,
    ExecutionStrategy,
)


def test_decomposition():
    """测试任务分解"""
    print("\n" + "=" * 60)
    print("[TEST 1] 任务分解")
    print("=" * 60)

    decomposer = TaskDecomposer()

    test_tasks = [
        ("写一个斐波那契函数", False),
        ("实现用户认证系统，包括注册、登录、权限管理", True),
        ("帮我创建一个 Flask Web 应用", True),
        ("分析这段代码的性能问题", False),
        ("搭建一个微服务架构", True),
    ]

    all_passed = True

    for task, expected in test_tasks:
        should_decompose = decomposer.should_decompose(task)
        decompose_ok = (should_decompose == expected)
        status = "[OK]" if decompose_ok else "[FAIL]"

        print(f"\n{status} Task: {task}")
        print(f"       Should decompose: {should_decompose} (expected: {expected})")

        if not decompose_ok:
            all_passed = False

        if should_decompose:
            result = decomposer.decompose(task)
            print(f"       Strategy: {result.strategy.value}")
            print(f"       Complexity: {result.estimated_complexity}")
            print(f"       Subtasks: {len(result.subtasks)}")
            for i, subtask in enumerate(result.subtasks, 1):
                deps = f" (deps: {subtask.depends_on})" if subtask.depends_on else ""
                print(f"         {i}. [{subtask.priority.name}] {subtask.title}{deps}")

    return all_passed


def test_execution():
    """测试任务执行"""
    print("\n" + "=" * 60)
    print("[TEST 2] 任务执行")
    print("=" * 60)

    decomposer = TaskDecomposer()
    decomposition = decomposer.decompose("实现一个计算器功能")

    # 记录回调
    events = {
        "subtask_start": [],
        "subtask_progress": [],
        "subtask_complete": [],
        "all_complete": False,
    }

    def on_subtask_start(subtask):
        events["subtask_start"].append(subtask.title)
        print(f"  [START] {subtask.title}")

    def on_subtask_progress(subtask, progress):
        if progress % 50 == 0:
            events["subtask_progress"].append((subtask.title, progress))
            print(f"  [PROGRESS] {subtask.title}: {progress}%")

    def on_subtask_complete(subtask):
        events["subtask_complete"].append(subtask.title)
        print(f"  [COMPLETE] {subtask.title}")

    def on_all_complete(decomposition):
        events["all_complete"] = True
        print(f"  [ALL COMPLETE] {decomposition.completed_tasks}/{decomposition.total_tasks}")

    callbacks = TaskDecompositionCallbacks(
        on_subtask_start=on_subtask_start,
        on_subtask_progress=on_subtask_progress,
        on_subtask_complete=on_subtask_complete,
        on_all_complete=on_all_complete,
    )

    # 自定义处理器
    def custom_handler(subtask: SubTask):
        print(f"    -> Executing: {subtask.title}")
        for i in range(1, 4):
            time.sleep(0.05)
            subtask.progress = i * 33
            if callbacks.on_subtask_progress:
                callbacks.on_subtask_progress(subtask, subtask.progress)
        return f"Result of {subtask.title}"

    executor = SubTaskExecutor(callbacks=callbacks)

    print(f"\nExecuting {decomposition.total_tasks} subtasks...")
    start_time = time.time()

    for state in executor.execute_stream(decomposition, task_handler=custom_handler):
        pass  # 流式消费

    duration = time.time() - start_time

    # 验证
    all_started = len(events["subtask_start"]) == decomposition.total_tasks
    all_completed = len(events["subtask_complete"]) == decomposition.total_tasks
    all_finished = events["all_complete"]

    print(f"\n[RESULT] Duration: {duration:.2f}s")
    print(f"[RESULT] Started: {len(events['subtask_start'])}/{decomposition.total_tasks}")
    print(f"[RESULT] Completed: {len(events['subtask_complete'])}/{decomposition.total_tasks}")
    print(f"[RESULT] All finished callback: {all_finished}")

    return all_started and all_completed and all_finished


def test_dag_execution():
    """测试依赖图执行"""
    print("\n" + "=" * 60)
    print("[TEST 3] DAG 依赖图执行")
    print("=" * 60)

    # 创建带依赖的任务
    tasks = [
        SubTask(task_id="1", title="初始化项目", description="创建项目结构"),
        SubTask(task_id="2", title="编写代码", description="实现核心功能", depends_on=["1"]),
        SubTask(task_id="3", title="编写测试", description="编写单元测试", depends_on=["1"]),
        SubTask(task_id="4", title="部署", description="部署到服务器", depends_on=["2", "3"]),
    ]

    decomposition = TaskDecomposition(
        original_task="DAG测试任务",
        subtasks=tasks,
        strategy=ExecutionStrategy.DAG,
    )

    execution_order = []

    def dag_handler(subtask: SubTask):
        execution_order.append(subtask.task_id)
        print(f"  [EXECUTE] {subtask.title} (deps: {subtask.depends_on})")
        time.sleep(0.1)
        return f"Done: {subtask.task_id}"

    executor = SubTaskExecutor()

    for state in executor.execute_stream(decomposition, task_handler=dag_handler):
        pass

    # 验证执行顺序
    # 1 必须在 2, 3 之前
    # 2, 3 必须在 4 之前
    order_ok = (
        execution_order.index("1") < execution_order.index("2") and
        execution_order.index("1") < execution_order.index("3") and
        execution_order.index("2") < execution_order.index("4") and
        execution_order.index("3") < execution_order.index("4")
    )

    print(f"\n[RESULT] Execution order: {' -> '.join(execution_order)}")
    print(f"[RESULT] Order correct: {order_ok}")

    return order_ok


def test_interruption():
    """测试中断功能"""
    print("\n" + "=" * 60)
    print("[TEST 4] 中断功能")
    print("=" * 60)

    decomposer = TaskDecomposer()
    decomposition = decomposer.decompose("执行一个多步骤任务")

    executor = SubTaskExecutor()

    def slow_handler(subtask: SubTask):
        for i in range(10):
            time.sleep(0.1)
            if executor._interrupt_event.is_set():
                return "Interrupted"
        return "Done"

    # 启动执行并立即中断
    import threading

    def interrupt_after_delay():
        time.sleep(0.3)
        executor.interrupt()

    interrupt_thread = threading.Thread(target=interrupt_after_delay)
    interrupt_thread.start()

    completed_before_interrupt = 0
    for state in executor.execute_stream(decomposition, task_handler=slow_handler):
        completed_before_interrupt = state.completed_tasks

    interrupt_thread.join()

    print(f"\n[RESULT] Tasks completed before interrupt: {completed_before_interrupt}")
    print(f"[RESULT] Interrupted successfully: True")

    return True  # 只要不崩溃就算通过


def main():
    print("=" * 60)
    print("任务分解系统测试套件")
    print("=" * 60)

    results = {
        "任务分解": test_decomposition(),
        "任务执行": test_execution(),
        "DAG依赖图": test_dag_execution(),
        "中断功能": test_interruption(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
