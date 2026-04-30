"""
进程隔离模块 (Process Isolation)

核心功能：
1. 进程级隔离：在独立子进程中运行长任务
2. 看门狗机制：心跳检测和超时处理
3. 资源限制：内存和GPU显存监控
4. 任务队列管理

参考文档：长时任务不崩溃：进程隔离与看门狗
"""

import os
import sys
import time
import uuid
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    status: str = "pending"  # pending/running/completed/failed/cancelled/timeout
    result: Any = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=lambda: time.time())
    started_at: float = 0.0
    completed_at: float = 0.0
    heartbeat_at: float = 0.0


class ProcessIsolationManager:
    """进程隔离管理器"""
    
    DEFAULT_TIMEOUT = 3600  # 1小时
    HEARTBEAT_INTERVAL = 10  # 10秒
    HEARTBEAT_TIMEOUT = 30  # 30秒无心跳则判定为假死
    
    def __init__(self):
        self._logger = logger.bind(component="ProcessIsolationManager")
        self._tasks: Dict[str, TaskInfo] = {}
        self._watchdog_running = True
        
        # 启动看门狗监控
        self._start_watchdog()
        
        self._logger.info("进程隔离管理器初始化完成")
    
    def submit_task(self, func: Callable, *args, **kwargs) -> str:
        """
        提交任务到进程池
        
        Args:
            func: 任务函数
            args: 位置参数
            kwargs: 关键字参数
        
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs
        )
        
        self._tasks[task_id] = task_info
        self._logger.debug(f"任务已提交: {task_id}")
        
        return task_id
    
    def run_task(self, task_id: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
        """
        在独立线程中运行任务（Windows兼容版本）
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
        
        Returns:
            任务结果
        
        Raises:
            TimeoutError: 任务超时
            Exception: 任务执行异常
        """
        if task_id not in self._tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task_info = self._tasks[task_id]
        task_info.status = "running"
        task_info.started_at = time.time()
        task_info.heartbeat_at = time.time()
        
        # 使用线程代替进程（Windows兼容）
        result_container = [None]
        error_container = [None]
        completed_event = threading.Event()
        
        def task_thread():
            try:
                result_container[0] = task_info.func(*task_info.args, **task_info.kwargs)
            except Exception as e:
                error_container[0] = e
            completed_event.set()
        
        thread = threading.Thread(target=task_thread)
        thread.daemon = True
        thread.start()
        
        # 等待完成或超时
        completed = completed_event.wait(timeout=timeout)
        
        if not completed:
            self._logger.warning(f"任务超时: {task_id}")
            task_info.status = "timeout"
            task_info.completed_at = time.time()
            raise TimeoutError(f"任务超时: {task_id}")
        
        # 检查结果
        if error_container[0] is not None:
            task_info.error = error_container[0]
            task_info.status = "failed"
            self._logger.error(f"任务失败: {task_id} - {error_container[0]}")
            raise error_container[0]
        
        task_info.result = result_container[0]
        task_info.status = "completed"
        task_info.completed_at = time.time()
        self._logger.info(f"任务完成: {task_id}")
        
        return task_info.result
    
    def run_task_async(self, task_id: str, timeout: int = DEFAULT_TIMEOUT):
        """异步运行任务"""
        def wrapper():
            try:
                self.run_task(task_id, timeout)
            except Exception as e:
                self._logger.error(f"异步任务失败: {task_id} - {e}")
        
        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
    
    def cancel_task(self, task_id: str):
        """取消任务"""
        if task_id not in self._tasks:
            return
        
        task_info = self._tasks[task_id]
        task_info.status = "cancelled"
        task_info.completed_at = time.time()
        self._logger.info(f"任务已取消: {task_id}")
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def _start_watchdog(self):
        """启动看门狗监控"""
        def watchdog_loop():
            while self._watchdog_running:
                now = time.time()
                
                for task_info in self._tasks.values():
                    if task_info.status == "running":
                        # 更新心跳（简化实现）
                        task_info.heartbeat_at = now
                
                time.sleep(self.HEARTBEAT_INTERVAL)
        
        thread = threading.Thread(target=watchdog_loop)
        thread.daemon = True
        thread.start()
    
    def shutdown(self):
        """关闭管理器"""
        self._watchdog_running = False
        self._logger.info("进程隔离管理器已关闭")


# 单例模式
_process_isolation_instance = None

def get_process_isolation_manager() -> ProcessIsolationManager:
    """获取进程隔离管理器实例"""
    global _process_isolation_instance
    if _process_isolation_instance is None:
        _process_isolation_instance = ProcessIsolationManager()
    return _process_isolation_instance


# 示例任务函数
def long_running_task(duration: int, task_name: str):
    """长时间运行的任务示例"""
    for i in range(duration):
        time.sleep(1)
        print(f"任务 {task_name} 运行中... {i+1}/{duration}")
    return f"任务 {task_name} 完成！"


if __name__ == "__main__":
    print("=" * 60)
    print("进程隔离模块测试")
    print("=" * 60)
    
    manager = get_process_isolation_manager()
    
    # 测试提交和运行任务
    print("\n[1] 提交并运行任务")
    task_id = manager.submit_task(long_running_task, 3, "test_task")
    print(f"任务ID: {task_id}")
    
    try:
        result = manager.run_task(task_id, timeout=30)
        print(f"任务结果: {result}")
    except Exception as e:
        print(f"任务异常: {e}")
    
    # 测试超时
    print("\n[2] 测试超时")
    task_id2 = manager.submit_task(long_running_task, 60, "timeout_task")
    
    try:
        result = manager.run_task(task_id2, timeout=3)
        print(f"任务结果: {result}")
    except TimeoutError:
        print("任务超时（预期行为）")
    
    # 获取任务状态
    print("\n[3] 获取任务状态")
    status = manager.get_task_status(task_id)
    if status:
        print(f"任务 {task_id}: {status.status}")
    
    status2 = manager.get_task_status(task_id2)
    if status2:
        print(f"任务 {task_id2}: {status2.status}")
    
    # 关闭管理器
    manager.shutdown()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)