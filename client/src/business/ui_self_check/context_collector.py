"""
轻量级上下文采集器 - ContextCollector
核心理念：只采集"指纹"级别的数据，而非"全量数据"

采集策略：
1. 错误时：最小必要信息（错误对象、组件名、输入参数）
2. 静默时：Source Map 映射，而非运行时分析庞大源码
3. 所有采集都经过压缩和限制，避免内存泄漏
"""

import json
import traceback
import threading
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import inspect
import sys
import os


class ContextLevel(Enum):
    """采集级别 - 控制数据量"""
    MINIMAL = 1      # 最小采集：仅错误类型和消息
    LIGHTWEIGHT = 2  # 轻量采集：错误+组件+时间戳
    STANDARD = 3    # 标准采集：+堆栈+参数
    FULL = 4        # 完整采集：+环境+状态快照


@dataclass
class ErrorContext:
    """错误上下文对象 - 最小必要信息"""
    error_type: str           # 错误类型（如 ValueError, TypeError）
    error_message: str        # 错误消息
    component_name: str        # 发生错误的组件名
    action: str               # 触发错误的操作
    timestamp: float          # 时间戳
    stack_hash: str           # 堆栈哈希（用于缓存Key）
    # 以下为可选字段
    stack_trace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    method_name: Optional[str] = None
    input_params: Optional[Dict[str, Any]] = None
    additional_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def get_cache_key(self) -> str:
        """生成缓存Key - 用于结果缓存"""
        key_data = f"{self.error_type}:{self.component_name}:{self.stack_hash}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]


@dataclass
class SilentContext:
    """静默分析上下文 - 更轻量"""
    component_name: str
    action: str
    timestamp: float
    duration_ms: float        # 操作持续时间
    response_status: str       # success/timeout/no_response
    source_file: Optional[str] = None


class ContextCollector:
    """
    轻量级上下文采集器

    设计原则：
    1. 非侵入式：通过装饰器或猴子补丁注入，而非修改原有代码
    2. 低功耗：异步采集，不阻塞主线程
    3. 防泄漏：采集后立即序列化，原始对象可被GC
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._callbacks: Dict[str, Callable] = {}
        self._collection_level = ContextLevel.STANDARD  # 默认采集级别
        self._max_stack_depth = 10  # 限制堆栈深度
        self._max_param_size = 1024  # 参数大小限制
        self._enable_file_location = True  # 是否采集文件位置
        self._last_collection_time = 0
        self._collection_interval_ms = 100  # 采集间隔防抖

    def register_callback(self, event_type: str, callback: Callable):
        """注册采集回调"""
        self._callbacks[event_type] = callback

    def collect_error_context(
        self,
        error: Exception,
        component_name: str = "Unknown",
        action: str = "unknown_action",
        level: ContextLevel = ContextLevel.STANDARD,
        input_params: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """
        采集错误上下文

        Args:
            error: 异常对象
            component_name: 组件名称
            action: 操作描述
            level: 采集级别
            input_params: 输入参数（会进行脱敏处理）

        Returns:
            ErrorContext: 轻量级错误上下文
        """
        # 获取堆栈信息
        stack_trace = traceback.format_exc(limit=self._max_stack_depth)
        stack_hash = hashlib.sha256(stack_trace.encode()).hexdigest()[:8]

        # 提取文件位置（如果启用）
        file_path = None
        line_number = None
        method_name = None
        if self._enable_file_location and error.__traceback__:
            tb = error.__traceback__
            if tb.tb_frame:
                file_path = tb.tb_frame.f_code.co_filename
                line_number = tb.tb_lineno
                method_name = tb.tb_frame.f_code.co_name

        # 脱敏处理输入参数
        safe_params = self._sanitize_params(input_params) if input_params else None

        context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error)[:500],  # 限制消息长度
            component_name=component_name,
            action=action,
            timestamp=datetime.now().timestamp(),
            stack_hash=stack_hash,
            stack_trace=stack_trace if level.value >= ContextLevel.STANDARD.value else None,
            file_path=file_path,
            line_number=line_number,
            method_name=method_name,
            input_params=safe_params,
            additional_data=self._collect_environment(level)
        )

        return context

    def collect_error_from_info(
        self,
        error_type: str,
        error_message: str,
        component_name: str = "Unknown",
        action: str = "unknown_action",
        stack_trace: Optional[str] = None
    ) -> ErrorContext:
        """
        从已知信息采集错误上下文（不持有异常对象）

        用于捕获系统级错误（如 window.onerror）
        """
        stack_hash = hashlib.sha256((stack_trace or "").encode()).hexdigest()[:8]

        # 从堆栈提取文件位置
        file_path = None
        line_number = None
        method_name = None
        if stack_trace:
            lines = stack_trace.split('\n')
            for line in lines:
                if 'File "' in line and '", line ' in line:
                    try:
                        # 尝试解析 "File \"xxx.py\", line 123, in method"
                        parts = line.split('", line ')
                        if len(parts) == 2:
                            file_path = parts[0].replace('  File "', '').strip()
                            line_part = parts[1].split(', in ')
                            line_number = int(line_part[0])
                            if len(line_part) > 1:
                                method_name = line_part[1].strip()
                    except:
                        pass

        return ErrorContext(
            error_type=error_type,
            error_message=error_message[:500],
            component_name=component_name,
            action=action,
            timestamp=datetime.now().timestamp(),
            stack_hash=stack_hash,
            stack_trace=stack_trace,
            file_path=file_path,
            line_number=line_number,
            method_name=method_name
        )

    def collect_silent_context(
        self,
        component_name: str,
        action: str,
        duration_ms: float,
        response_status: str = "success"
    ) -> SilentContext:
        """
        采集静默分析上下文

        用于监控"操作成功但无响应"的情况
        """
        return SilentContext(
            component_name=component_name,
            action=action,
            timestamp=datetime.now().timestamp(),
            duration_ms=duration_ms,
            response_status=response_status
        )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        脱敏处理参数

        敏感字段替换为 ***，大对象进行截断
        """
        sensitive_keys = {
            'password', 'passwd', 'secret', 'token', 'api_key', 'apikey',
            'auth', 'credential', 'private_key', 'token', 'access_token',
            'refresh_token', 'session', 'cookie'
        }

        sanitized = {}
        for key, value in params.items():
            # 检查是否敏感
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "***"
            elif isinstance(value, str) and len(value) > self._max_param_size:
                sanitized[key] = value[:self._max_param_size] + "...[truncated]"
            elif isinstance(value, (dict, list)):
                try:
                    json_str = json.dumps(value)
                    if len(json_str) > self._max_param_size:
                        sanitized[key] = "...[large object truncated]"
                    else:
                        sanitized[key] = value
                except:
                    sanitized[key] = "...[non-serializable]"
            else:
                sanitized[key] = value

        return sanitized

    def _collect_environment(self, level: ContextLevel) -> Optional[Dict[str, Any]]:
        """采集环境信息"""
        if level.value < ContextLevel.STANDARD.value:
            return None

        env = {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
        }

        if level.value >= ContextLevel.FULL.value:
            env.update({
                "working_dir": os.getcwd(),
                "pid": os.getpid(),
                "thread_count": threading.active_count(),
            })

        return env

    def set_collection_level(self, level: ContextLevel):
        """设置采集级别"""
        self._collection_level = level
        # 根据级别调整采集参数
        if level == ContextLevel.MINIMAL:
            self._max_stack_depth = 3
            self._max_param_size = 256
        elif level == ContextLevel.LIGHTWEIGHT:
            self._max_stack_depth = 5
            self._max_param_size = 512
        elif level == ContextLevel.STANDARD:
            self._max_stack_depth = 10
            self._max_param_size = 1024
        elif level == ContextLevel.FULL:
            self._max_stack_depth = 20
            self._max_param_size = 4096

    def enable_file_location(self, enable: bool):
        """启用/禁用文件位置采集"""
        self._enable_file_location = enable


# 全局单例
collector = ContextCollector()
