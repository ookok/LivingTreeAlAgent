"""
调试系统模块
提供多语言调试、变量监视、性能分析等功能
"""
import asyncio
import subprocess
import sys
import os
import re
import signal
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class DebuggerState(Enum):
    """调试器状态"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    STEP_INTO = "step_into"
    STEP_OVER = "step_over"
    STEP_OUT = "step_out"
    TERMINATED = "terminated"


class StepType(Enum):
    """单步执行类型"""
    INTO = "into"  # 进入函数
    OVER = "over"  # 跳过函数
    OUT = "out"    # 跳出函数


@dataclass
class StackFrame:
    """调用栈帧"""
    id: int
    name: str
    file: str
    line: int
    column: int = 0
    locals: Dict[str, Any] = field(default_factory=dict)
    globals: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadInfo:
    """线程信息"""
    id: int
    name: str
    state: str
    is_main: bool = False
    frames: List[StackFrame] = field(default_factory=list)


@dataclass
class Breakpoint:
    """断点"""
    id: int
    file: str
    line: int
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0
    hit_condition: Optional[str] = None  # ">", ">=", "==", "%"
    log_message: Optional[str] = None
    trace: bool = False


@dataclass
class WatchExpression:
    """监视表达式"""
    id: int
    expression: str
    value: Any = None
    error: Optional[str] = None
    type: str = ""
    updated_at: Optional[datetime] = None


@dataclass
class ExceptionInfo:
    """异常信息"""
    type: str
    message: str
    stack_trace: List[StackFrame] = field(default_factory=list)
    handled: bool = False


@dataclass
class DebugEvent:
    """调试事件"""
    type: str  # breakpoint, exception, step, output
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class DebuggerBackend:
    """调试器后端接口"""

    async def start(self, file_path: str, args: List[str] = None, env: Dict = None) -> bool:
        """启动调试会话"""
        raise NotImplementedError

    async def stop(self) -> bool:
        """停止调试"""
        raise NotImplementedError

    async def pause(self) -> bool:
        """暂停"""
        raise NotImplementedError

    async def resume(self) -> bool:
        """继续"""
        raise NotImplementedError

    async def step(self, step_type: StepType) -> bool:
        """单步执行"""
        raise NotImplementedError

    async def add_breakpoint(self, file: str, line: int, condition: Optional[str] = None) -> Breakpoint:
        """添加断点"""
        raise NotImplementedError

    async def remove_breakpoint(self, bp_id: int) -> bool:
        """删除断点"""
        raise NotImplementedError

    async def evaluate(self, expression: str) -> Any:
        """计算表达式"""
        raise NotImplementedError

    async def get_stack_trace(self, thread_id: int = 0) -> List[StackFrame]:
        """获取调用栈"""
        raise NotImplementedError

    async def get_variables(self, frame_id: int = 0) -> Dict[str, Any]:
        """获取变量"""
        raise NotImplementedError


class PythonDebugger(DebuggerBackend):
    """Python调试器 (使用内置pdb)"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.breakpoints: Dict[int, Breakpoint] = {}
        self.next_bp_id = 1
        self.state = DebuggerState.STOPPED
        self.current_file: Optional[str] = None
        self.stack: List[StackFrame] = []
        self.variables: Dict[str, Any] = {}
        self._output_callback: Optional[Callable] = None

    async def start(
        self,
        file_path: str,
        args: List[str] = None,
        env: Dict = None
    ) -> bool:
        """启动Python调试会话"""
        try:
            self.current_file = file_path

            # 构建命令
            cmd = [
                sys.executable,
                '-m', 'pdb',
                file_path
            ]
            if args:
                cmd.extend(args)

            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env or os.environ.copy(),
                cwd=os.path.dirname(file_path) or '.'
            )

            self.state = DebuggerState.RUNNING
            return True

        except Exception as e:
            print(f"Failed to start debugger: {e}")
            return False

    async def stop(self) -> bool:
        """停止调试"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        self.state = DebuggerState.STOPPED
        return True

    async def pause(self) -> bool:
        """暂停"""
        if self.process and self.state == DebuggerState.RUNNING:
            self.process.send_signal(signal.SIGINT)
            self.state = DebuggerState.PAUSED
            return True
        return False

    async def resume(self) -> bool:
        """继续"""
        if self.process and self.state == DebuggerState.PAUSED:
            self.process.stdin.write('c\n')
            self.process.stdin.flush()
            self.state = DebuggerState.RUNNING
            return True
        return False

    async def step(self, step_type: StepType) -> bool:
        """单步执行"""
        if not self.process:
            return False

        commands = {
            StepType.INTO: 's',
            StepType.OVER: 'n',
            StepType.OUT: 'r'
        }

        cmd = commands.get(step_type, 'n')
        self.process.stdin.write(f'{cmd}\n')
        self.process.stdin.flush()

        if step_type == StepType.INTO:
            self.state = DebuggerState.STEP_INTO
        elif step_type == StepType.OVER:
            self.state = DebuggerState.STEP_OVER
        elif step_type == StepType.OUT:
            self.state = DebuggerState.STEP_OUT

        return True

    async def add_breakpoint(
        self,
        file: str,
        line: int,
        condition: Optional[str] = None
    ) -> Breakpoint:
        """添加断点"""
        bp = Breakpoint(
            id=self.next_bp_id,
            file=file,
            line=line,
            condition=condition
        )
        self.next_bp_id += 1
        self.breakpoints[bp.id] = bp

        # 设置断点命令
        if self.process:
            cmd = f"break {file}:{line}"
            if condition:
                cmd += f" if {condition}"
            self.process.stdin.write(f'{cmd}\n')
            self.process.stdin.flush()

        return bp

    async def remove_breakpoint(self, bp_id: int) -> bool:
        """删除断点"""
        if bp_id in self.breakpoints:
            bp = self.breakpoints[bp_id]

            # 删除断点命令
            if self.process:
                self.process.stdin.write(f"clear {bp.file}:{bp.line}\n")
                self.process.stdin.flush()

            del self.breakpoints[bp_id]
            return True
        return False

    async def evaluate(self, expression: str) -> Any:
        """计算表达式"""
        if self.process:
            self.process.stdin.write(f'pp {expression}\n')
            self.process.stdin.flush()
            # 读取输出
            # 简化实现
            return None
        return None

    async def get_stack_trace(self, thread_id: int = 0) -> List[StackFrame]:
        """获取调用栈"""
        # 简化实现
        return self.stack

    async def get_variables(self, frame_id: int = 0) -> Dict[str, Any]:
        """获取变量"""
        # 简化实现
        return self.variables

    def set_output_callback(self, callback: Callable):
        """设置输出回调"""
        self._output_callback = callback


class JavaScriptDebugger(DebuggerBackend):
    """JavaScript调试器 (使用Node.js inspect协议)"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.breakpoints: Dict[int, Breakpoint] = {}
        self.next_bp_id = 1
        self.state = DebuggerState.STOPPED
        self.current_file: Optional[str] = None
        self._debugger_port: int = 9229

    async def start(
        self,
        file_path: str,
        args: List[str] = None,
        env: Dict = None
    ) -> bool:
        """启动JavaScript调试会话"""
        try:
            self.current_file = file_path

            cmd = [
                'node',
                f'--inspect={self._debugger_port}',
                file_path
            ]
            if args:
                cmd.extend(args)

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env or os.environ.copy(),
                cwd=os.path.dirname(file_path) or '.'
            )

            self.state = DebuggerState.RUNNING
            return True

        except Exception as e:
            print(f"Failed to start JS debugger: {e}")
            return False

    async def stop(self) -> bool:
        """停止调试"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        self.state = DebuggerState.STOPPED
        return True

    async def pause(self) -> bool:
        """暂停"""
        if self.process:
            self.process.send_signal(signal.SIGINT)
            self.state = DebuggerState.PAUSED
            return True
        return False

    async def resume(self) -> bool:
        """继续"""
        self.state = DebuggerState.RUNNING
        return True

    async def step(self, step_type: StepType) -> bool:
        """单步执行"""
        return True

    async def add_breakpoint(
        self,
        file: str,
        line: int,
        condition: Optional[str] = None
    ) -> Breakpoint:
        """添加断点"""
        bp = Breakpoint(
            id=self.next_bp_id,
            file=file,
            line=line,
            condition=condition
        )
        self.next_bp_id += 1
        self.breakpoints[bp.id] = bp
        return bp

    async def remove_breakpoint(self, bp_id: int) -> bool:
        """删除断点"""
        if bp_id in self.breakpoints:
            del self.breakpoints[bp_id]
            return True
        return False

    async def evaluate(self, expression: str) -> Any:
        """计算表达式"""
        return None

    async def get_stack_trace(self, thread_id: int = 0) -> List[StackFrame]:
        """获取调用栈"""
        return []

    async def get_variables(self, frame_id: int = 0) -> Dict[str, Any]:
        """获取变量"""
        return {}


class DebuggerManager:
    """调试管理器"""

    def __init__(self):
        self.backends: Dict[str, DebuggerBackend] = {
            "python": PythonDebugger(),
            "javascript": PythonDebugger(),  # 使用通用实现
            "java": PythonDebugger(),
        }
        self.current_backend: Optional[DebuggerBackend] = None
        self.current_language: Optional[str] = None
        self.event_listeners: Dict[str, List[Callable]] = {}
        self._running = False

    def get_backend(self, language: str) -> Optional[DebuggerBackend]:
        """获取调试后端"""
        return self.backends.get(language.lower())

    async def start_debugging(
        self,
        file_path: str,
        language: str,
        args: List[str] = None,
        env: Dict = None
    ) -> bool:
        """启动调试"""
        backend = self.get_backend(language)
        if not backend:
            return False

        self.current_backend = backend
        self.current_language = language
        self._running = True

        success = await backend.start(file_path, args, env)
        if success:
            self._emit_event("debug_started", {"file": file_path, "language": language})

        return success

    async def stop_debugging(self) -> bool:
        """停止调试"""
        if self.current_backend:
            success = await self.current_backend.stop()
            if success:
                self._emit_event("debug_stopped", {})
                self.current_backend = None
                self._running = False
            return success
        return False

    async def pause(self) -> bool:
        """暂停"""
        if self.current_backend:
            success = await self.current_backend.pause()
            if success:
                self._emit_event("debug_paused", {"state": "paused"})
            return success
        return False

    async def resume(self) -> bool:
        """继续"""
        if self.current_backend:
            success = await self.current_backend.resume()
            if success:
                self._emit_event("debug_resumed", {"state": "running"})
            return success
        return False

    async def step_into(self) -> bool:
        """单步进入"""
        if self.current_backend:
            return await self.current_backend.step(StepType.INTO)
        return False

    async def step_over(self) -> bool:
        """单步跳过"""
        if self.current_backend:
            return await self.current_backend.step(StepType.OVER)
        return False

    async def step_out(self) -> bool:
        """单步跳出"""
        if self.current_backend:
            return await self.current_backend.step(StepType.OUT)
        return False

    async def add_breakpoint(
        self,
        file: str,
        line: int,
        condition: Optional[str] = None
    ) -> Optional[Breakpoint]:
        """添加断点"""
        if self.current_backend:
            bp = await self.current_backend.add_breakpoint(file, line, condition)
            if bp:
                self._emit_event("breakpoint_added", {
                    "breakpoint": {
                        "id": bp.id,
                        "file": bp.file,
                        "line": bp.line,
                        "condition": bp.condition
                    }
                })
            return bp
        return None

    async def remove_breakpoint(self, bp_id: int) -> bool:
        """删除断点"""
        if self.current_backend:
            success = await self.current_backend.remove_breakpoint(bp_id)
            if success:
                self._emit_event("breakpoint_removed", {"bp_id": bp_id})
            return success
        return False

    async def evaluate_expression(self, expression: str) -> Any:
        """计算表达式"""
        if self.current_backend:
            return await self.current_backend.evaluate(expression)
        return None

    async def get_stack_trace(self) -> List[StackFrame]:
        """获取调用栈"""
        if self.current_backend:
            return await self.current_backend.get_stack_trace()
        return []

    async def get_variables(self) -> Dict[str, Any]:
        """获取变量"""
        if self.current_backend:
            return await self.current_backend.get_variables()
        return {}

    def add_event_listener(self, event: str, callback: Callable):
        """添加事件监听器"""
        if event not in self.event_listeners:
            self.event_listeners[event] = []
        self.event_listeners[event].append(callback)

    def remove_event_listener(self, event: str, callback: Callable):
        """移除事件监听器"""
        if event in self.event_listeners:
            self.event_listeners[event].remove(callback)

    def _emit_event(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        if event in self.event_listeners:
            debug_event = DebugEvent(type=event, data=data)
            for listener in self.event_listeners[event]:
                try:
                    listener(debug_event)
                except Exception as e:
                    print(f"Event listener error: {e}")

    def get_debugger_state(self) -> Dict[str, Any]:
        """获取调试器状态"""
        state = "stopped"
        if self.current_backend:
            state = self.current_backend.state.value

        return {
            "running": self._running,
            "state": state,
            "language": self.current_language,
            "breakpoints": [
                {"id": bp.id, "file": bp.file, "line": bp.line, "enabled": bp.enabled}
                for bp in (self.current_backend.breakpoints.values() if self.current_backend else [])
            ]
        }


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._profiling = False
        self._start_time: Optional[datetime] = None

    async def start_profiling(self, session_id: str):
        """开始分析"""
        self._profiling = True
        self._start_time = datetime.now()
        self.profiles[session_id] = {
            "start_time": self._start_time,
            "end_time": None,
            "durations": {},
            "memory_samples": [],
            "cpu_samples": []
        }

    async def stop_profiling(self, session_id: str) -> Dict[str, Any]:
        """停止分析"""
        if session_id in self.profiles:
            self.profiles[session_id]["end_time"] = datetime.now()
            self._profiling = False

        return self.profiles.get(session_id, {})

    def record_duration(self, session_id: str, name: str, duration: float):
        """记录执行时间"""
        if session_id in self.profiles:
            if name not in self.profiles[session_id]["durations"]:
                self.profiles[session_id]["durations"][name] = []
            self.profiles[session_id]["durations"][name].append(duration)

    def get_profile_summary(self, session_id: str) -> Dict[str, Any]:
        """获取分析摘要"""
        profile = self.profiles.get(session_id, {})
        durations = profile.get("durations", {})

        summary = {}
        for name, times in durations.items():
            if times:
                summary[name] = {
                    "count": len(times),
                    "total": sum(times),
                    "average": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times)
                }

        return summary

    async def memory_snapshot(self, session_id: str):
        """获取内存快照"""
        import psutil
        process = psutil.Process()

        snapshot = {
            "timestamp": datetime.now(),
            "rss": process.memory_info().rss,
            "vms": process.memory_info().vms,
            "percent": process.memory_percent()
        }

        if session_id in self.profiles:
            self.profiles[session_id]["memory_samples"].append(snapshot)

        return snapshot


class MemoryInspector:
    """内存检查器"""

    def __init__(self):
        self.object_ids: Set[int] = set()
        self.object_types: Dict[int, str] = {}
        self.object_sizes: Dict[int, int] = {}

    def track_object(self, obj: Any) -> int:
        """追踪对象"""
        obj_id = id(obj)
        self.object_ids.add(obj_id)
        self.object_types[obj_id] = type(obj).__name__

        try:
            size = sys.getsizeof(obj)
            self.object_sizes[obj_id] = size
        except:
            self.object_sizes[obj_id] = 0

        return obj_id

    def get_object_info(self, obj_id: int) -> Dict[str, Any]:
        """获取对象信息"""
        return {
            "id": obj_id,
            "type": self.object_types.get(obj_id, "unknown"),
            "size": self.object_sizes.get(obj_id, 0),
            "tracked": obj_id in self.object_ids
        }

    def get_memory_summary(self) -> Dict[str, Any]:
        """获取内存摘要"""
        type_counts: Dict[str, int] = {}
        type_sizes: Dict[str, int] = {}

        for obj_id in self.object_ids:
            obj_type = self.object_types.get(obj_id, "unknown")
            obj_size = self.object_sizes.get(obj_id, 0)

            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
            type_sizes[obj_type] = type_sizes.get(obj_type, 0) + obj_size

        return {
            "total_objects": len(self.object_ids),
            "total_size": sum(self.object_sizes.values()),
            "type_counts": type_counts,
            "type_sizes": type_sizes
        }


class DebugSession:
    """调试会话"""

    def __init__(self, session_id: str):
        self.id = session_id
        self.debugger_manager = DebuggerManager()
        self.profiler = PerformanceProfiler()
        self.memory_inspector = MemoryInspector()
        self.created_at = datetime.now()
        self.watch_expressions: List[WatchExpression] = []
        self.next_watch_id = 1

    async def start(
        self,
        file_path: str,
        language: str,
        args: List[str] = None
    ) -> bool:
        """启动会话"""
        return await self.debugger_manager.start_debugging(
            file_path, language, args
        )

    async def stop(self):
        """停止会话"""
        await self.debugger_manager.stop_debugging()
        await self.profiler.stop_profiling(self.id)

    def add_watch(self, expression: str) -> WatchExpression:
        """添加监视"""
        watch = WatchExpression(
            id=self.next_watch_id,
            expression=expression
        )
        self.next_watch_id += 1
        self.watch_expressions.append(watch)
        return watch

    def remove_watch(self, watch_id: int):
        """移除监视"""
        self.watch_expressions = [
            w for w in self.watch_expressions if w.id != watch_id
        ]

    async def update_watches(self):
        """更新监视表达式"""
        for watch in self.watch_expressions:
            result = await self.debugger_manager.evaluate_expression(watch.expression)
            watch.value = result
            watch.updated_at = datetime.now()

    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "state": self.debugger_manager.get_debugger_state(),
            "watches": [
                {"id": w.id, "expression": w.expression, "value": str(w.value)}
                for w in self.watch_expressions
            ],
            "memory_summary": self.memory_inspector.get_memory_summary()
        }


# 便捷函数
def create_debug_session() -> DebugSession:
    """创建调试会话"""
    import uuid
    session_id = str(uuid.uuid4())[:8]
    return DebugSession(session_id)


def get_debugger_manager() -> DebuggerManager:
    """获取调试管理器"""
    return DebuggerManager()
