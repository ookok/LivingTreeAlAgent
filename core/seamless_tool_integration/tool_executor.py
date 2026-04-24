"""
Tool Executor - 工具执行封装

负责：
1. 异步执行外部工具
2. 进度反馈
3. 实时日志输出
4. 错误处理与重试
5. 资源管理
"""

import os
import sys
import subprocess
import threading
import time
import queue
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
import json


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionMode(Enum):
    """执行模式"""
    LOCAL = "local"           # 本地执行
    DOCKER = "docker"         # Docker容器
    CLOUD = "cloud"           # 云端计算


@dataclass
class ExecutionResult:
    """执行结果"""
    status: ExecutionStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0  # 秒
    output_files: Dict[str, str] = field(default_factory=dict)
    error_message: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED and self.exit_code == 0

    @property
    def execution_time_formatted(self) -> str:
        """格式化执行时间"""
        if self.execution_time < 60:
            return f"{self.execution_time:.1f}秒"
        elif self.execution_time < 3600:
            return f"{self.execution_time/60:.1f}分钟"
        else:
            return f"{self.execution_time/3600:.1f}小时"


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    name: str
    description: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    progress: float = 0.0  # 0-100
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    message: str = ""

    @property
    def duration(self) -> float:
        """持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime
    level: LogLevel
    message: str
    source: str = ""

    def to_string(self) -> str:
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] [{self.level.value}] {self.source}: {self.message}"


class ToolExecutor:
    """
    工具执行器

    封装外部工具的执行过程，提供：
    - 异步执行（不阻塞UI）
    - 进度实时反馈
    - 日志输出
    - 超时控制
    - 错误处理

    使用示例：
    ```python
    executor = ToolExecutor()

    # 定义执行步骤
    executor.add_step("prepare", "准备环境")
    executor.add_step("input", "生成输入文件")
    executor.add_step("run", "运行模型")
    executor.add_step("parse", "解析结果")

    # 设置回调
    executor.on_progress(lambda step: logger.info(f"{step.name}: {step.progress}%"))
    executor.on_log(lambda entry: logger.info(entry.to_string()))

    # 执行
    result = executor.execute(
        tool_path="C:/ProgramData/HermesDesktop/ExternalTools/aermod/aermod.exe",
        args=["input.inp"],
        work_dir="/tmp/aermod",
        timeout=7200  # 2小时超时
    )
    ```
    """

    def __init__(
        self,
        max_retries: int = 0,
        default_timeout: int = 7200  # 2小时
    ):
        self.max_retries = max_retries
        self.default_timeout = default_timeout

        # 执行上下文
        self._current_tool: Optional[str] = None
        self._current_args: List[str] = []
        self._current_work_dir: Optional[str] = None
        self._cancel_flag = False
        self._pause_flag = False

        # 步骤管理
        self._steps: Dict[str, ExecutionStep] = {}
        self._current_step_id: Optional[str] = None

        # 回调函数
        self._progress_callback: Optional[Callable[[ExecutionStep], None]] = None
        self._log_callback: Optional[Callable[[LogEntry], None]] = None
        self._stdout_callback: Optional[Callable[[str], None]] = None

        # 日志队列
        self._log_queue: queue.Queue = queue.Queue()

        # 执行线程
        self._execution_thread: Optional[threading.Thread] = None
        self._result: Optional[ExecutionResult] = None

    def add_step(self, step_id: str, name: str, description: str = "") -> "ToolExecutor":
        """
        添加执行步骤

        Args:
            step_id: 步骤ID
            name: 步骤名称
            description: 步骤描述

        Returns:
            self (支持链式调用)
        """
        self._steps[step_id] = ExecutionStep(
            step_id=step_id,
            name=name,
            description=description
        )
        return self

    def set_progress_callback(self, callback: Callable[[ExecutionStep], None]):
        """设置进度回调"""
        self._progress_callback = callback

    def set_log_callback(self, callback: Callable[[LogEntry], None]):
        """设置日志回调"""
        self._log_callback = callback

    def set_stdout_callback(self, callback: Callable[[str], None]):
        """设置标准输出回调"""
        self._stdout_callback = callback

    def _update_step(self, step_id: str, **kwargs):
        """更新步骤状态"""
        if step_id not in self._steps:
            return

        step = self._steps[step_id]

        for key, value in kwargs.items():
            if hasattr(step, key):
                setattr(step, key, value)

        # 触发回调
        if self._progress_callback:
            self._progress_callback(step)

    def _log(self, level: LogLevel, message: str, source: str = ""):
        """记录日志"""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            source=source
        )

        if self._log_callback:
            self._log_callback(entry)

    def _start_step(self, step_id: str):
        """开始步骤"""
        self._current_step_id = step_id
        self._update_step(
            step_id,
            status=ExecutionStatus.RUNNING,
            start_time=datetime.now(),
            progress=0
        )
        self._log(LogLevel.INFO, f"开始: {self._steps[step_id].name}", "Executor")

    def _finish_step(self, step_id: str, status: ExecutionStatus = ExecutionStatus.COMPLETED, message: str = ""):
        """完成步骤"""
        self._update_step(
            step_id,
            status=status,
            end_time=datetime.now(),
            progress=100 if status == ExecutionStatus.COMPLETED else 0,
            message=message
        )

        level = LogLevel.SUCCESS if status == ExecutionStatus.COMPLETED else LogLevel.ERROR
        self._log(level, f"完成: {self._steps[step_id].name} - {message}", "Executor")

    def _set_step_progress(self, progress: float, message: str = ""):
        """设置当前步骤进度"""
        if self._current_step_id:
            self._update_step(
                self._current_step_id,
                progress=min(progress, 100),
                message=message
            )

    def cancel(self):
        """取消执行"""
        self._cancel_flag = True
        self._log(LogLevel.WARNING, "用户取消执行", "Executor")

        if self._current_step_id:
            self._finish_step(self._current_step_id, ExecutionStatus.CANCELLED, "用户取消")

    def pause(self):
        """暂停执行"""
        self._pause_flag = True
        self._log(LogLevel.INFO, "执行已暂停", "Executor")

    def resume(self):
        """恢复执行"""
        self._pause_flag = False
        self._log(LogLevel.INFO, "执行已恢复", "Executor")

    def _wait_if_paused(self):
        """暂停时等待"""
        while self._pause_flag:
            if self._cancel_flag:
                break
            time.sleep(0.5)

    def execute(
        self,
        tool_path: str,
        args: Optional[List[str]] = None,
        work_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        input_data: Optional[str] = None,
        mode: ExecutionMode = ExecutionMode.LOCAL,
        docker_image: Optional[str] = None
    ) -> ExecutionResult:
        """
        执行工具

        Args:
            tool_path: 工具路径
            args: 命令行参数
            work_dir: 工作目录
            env: 环境变量
            timeout: 超时时间（秒）
            input_data:  stdin输入数据
            mode: 执行模式
            docker_image: Docker镜像（当mode=DOCKER时）

        Returns:
            ExecutionResult
        """
        self._current_tool = tool_path
        self._current_args = args or []
        self._current_work_dir = work_dir or os.getcwd()
        self._cancel_flag = False

        timeout = timeout or self.default_timeout

        # 验证工具路径
        if mode == ExecutionMode.LOCAL:
            if not os.path.exists(tool_path):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error_message=f"工具不存在: {tool_path}"
                )

        # 启动执行线程
        result_queue = queue.Queue()

        def run():
            try:
                result = self._do_execute(
                    tool_path, args, work_dir, env, timeout, input_data, mode, docker_image
                )
                result_queue.put(result)
            except Exception as e:
                result_queue.put(ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error_message=str(e)
                ))

        self._execution_thread = threading.Thread(target=run)
        self._execution_thread.start()

        # 等待结果
        try:
            self._result = result_queue.get(timeout=timeout + 60)
        except queue.Empty:
            self._result = ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error_message=f"执行超时（{timeout}秒）"
            )

        return self._result

    def _do_execute(
        self,
        tool_path: str,
        args: Optional[List[str]],
        work_dir: str,
        env: Optional[Dict[str, str]],
        timeout: int,
        input_data: Optional[str],
        mode: ExecutionMode,
        docker_image: Optional[str]
    ) -> ExecutionResult:

        start_time = datetime.now()
        stdout_data = []
        stderr_data = []

        # 准备命令
        if mode == ExecutionMode.DOCKER:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{work_dir}:/workspace",
                "-w", "/workspace",
                docker_image or "python:3.9",
                tool_path
            ] + (args or [])
        else:
            cmd = [tool_path] + (args or [])

        self._log(LogLevel.INFO, f"执行命令: {' '.join(cmd)}", "Executor")
        self._log(LogLevel.INFO, f"工作目录: {work_dir}", "Executor")

        # 构建环境变量
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_data else None,
                cwd=work_dir,
                env=exec_env,
                text=False  # 字节模式
            )

            # 输入数据
            if input_data:
                process.stdin.write(input_data.encode('utf-8'))
                process.stdin.close()

            # 监控输出
            import select
from core.logger import get_logger
logger = get_logger('seamless_tool_integration.tool_executor')


            while True:
                self._wait_if_paused()

                if self._cancel_flag:
                    process.terminate()
                    return ExecutionResult(
                        status=ExecutionStatus.CANCELLED,
                        error_message="用户取消执行"
                    )

                # 检查进程是否结束
                retcode = process.poll()

                # 读取输出（非阻塞）
                readable, _, _ = select.select([process.stdout, process.stderr], [], [], 1.0)

                for stream in readable:
                    if stream == process.stdout:
                        data = os.read(process.stdout.fileno(), 4096)
                        if data:
                            stdout_data.append(data)
                            if self._stdout_callback:
                                self._stdout_callback(data.decode('utf-8', errors='replace'))
                    elif stream == process.stderr:
                        data = os.read(process.stderr.fileno(), 4096)
                        if data:
                            stderr_data.append(data)
                            self._log(LogLevel.ERROR, data.decode('utf-8', errors='replace'), "Process")

                # 检查是否结束
                if retcode is not None:
                    break

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # 读取剩余输出
            stdout_bytes = b''.join(stdout_data)
            stderr_bytes = b''.join(stderr_data)

            status = ExecutionStatus.COMPLETED if retcode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                status=status,
                exit_code=retcode or 0,
                stdout=stdout_bytes.decode('utf-8', errors='replace'),
                stderr=stderr_bytes.decode('utf-8', errors='replace'),
                execution_time=execution_time,
                error_message="" if retcode == 0 else f"进程返回码: {retcode}"
            )

        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_message=str(e)
            )

    def get_current_step(self) -> Optional[ExecutionStep]:
        """获取当前执行步骤"""
        if self._current_step_id:
            return self._steps.get(self._current_step_id)
        return None

    def get_all_steps(self) -> List[ExecutionStep]:
        """获取所有步骤"""
        return list(self._steps.values())

    def get_logs(self) -> List[LogEntry]:
        """获取所有日志"""
        logs = []
        while not self._log_queue.empty():
            try:
                logs.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        return logs


class WorkflowExecutor:
    """
    工作流执行器 - 执行多步骤工作流

    用于执行需要多个工具协作的复杂任务

    使用示例：
    ```python
    workflow = WorkflowExecutor()

    workflow.add_task(
        task_id="download",
        name="下载模型",
        func=lambda: download_model()
    )

    workflow.add_task(
        task_id="process",
        name="处理数据",
        func=lambda: process_data(),
        depends_on=["download"]
    )

    result = workflow.execute()
    ```
    """

    def __init__(self):
        self._tasks: Dict[str, Dict] = {}
        self._results: Dict[str, Any] = {}
        self._cancel_flag = False

    def add_task(
        self,
        task_id: str,
        name: str,
        func: Callable,
        depends_on: Optional[List[str]] = None,
        description: str = ""
    ):
        """添加任务"""
        self._tasks[task_id] = {
            "id": task_id,
            "name": name,
            "func": func,
            "depends_on": depends_on or [],
            "description": description,
            "status": ExecutionStatus.PENDING
        }

    def execute(self, progress_callback: Optional[Callable[[str, float], None]] = None) -> Dict[str, Any]:
        """执行工作流"""
        self._results = {}
        self._cancel_flag = False

        # 拓扑排序
        execution_order = self._topological_sort()

        total_tasks = len(execution_order)

        for i, task_id in enumerate(execution_order):
            if self._cancel_flag:
                break

            task = self._tasks[task_id]
            task["status"] = ExecutionStatus.RUNNING

            if progress_callback:
                progress_callback(task["name"], (i / total_tasks) * 100)

            try:
                # 等待依赖完成
                for dep_id in task["depends_on"]:
                    if self._tasks[dep_id]["status"] != ExecutionStatus.COMPLETED:
                        raise Exception(f"依赖任务未完成: {dep_id}")

                # 执行任务
                result = task["func"]()
                self._results[task_id] = result
                task["status"] = ExecutionStatus.COMPLETED

            except Exception as e:
                self._results[task_id] = {"error": str(e)}
                task["status"] = ExecutionStatus.FAILED
                break

        return self._results

    def _topological_sort(self) -> List[str]:
        """拓扑排序获取执行顺序"""
        visited = set()
        order = []

        def visit(task_id):
            if task_id in visited:
                return
            visited.add(task_id)

            for dep_id in self._tasks[task_id]["depends_on"]:
                visit(dep_id)

            order.append(task_id)

        for task_id in self._tasks:
            visit(task_id)

        return order

    def cancel(self):
        """取消工作流"""
        self._cancel_flag = True


# 便捷函数
def run_tool(
    tool_path: str,
    args: Optional[List[str]] = None,
    timeout: int = 7200,
    log_callback: Optional[Callable[[LogEntry], None]] = None
) -> ExecutionResult:
    """
    快速运行工具

    使用示例：
    ```python
    result = run_tool("aermod.exe", ["input.inp"], timeout=3600)
    if result.success:
        logger.info(f"执行成功，耗时: {result.execution_time_formatted}")
    ```
    """
    executor = ToolExecutor()
    if log_callback:
        executor.set_log_callback(log_callback)

    return executor.execute(
        tool_path=tool_path,
        args=args,
        timeout=timeout
    )
