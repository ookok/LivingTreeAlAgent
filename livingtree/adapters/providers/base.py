"""
base.py — 三模式驱动系统的统一抽象层

定义所有驱动共用的数据模型和抽象接口。
上层代码只需依赖此文件即可与任意驱动交互。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional


# ── 枚举 ──────────────────────────────────────────────────────────

class DriverMode(Enum):
    """驱动模式"""
    HARD_LOAD = "hard_load"            # 硬加载：进程内直接加载模型
    LOCAL_SERVICE = "local_service"    # 本地服务：连接本地 OpenAI 兼容 API
    CLOUD_SERVICE = "cloud_service"    # 云服务：调用云端 API


class DriverState(Enum):
    """驱动状态"""
    UNINITIALIZED = "uninitialized"    # 未初始化
    LOADING = "loading"               # 加载中
    READY = "ready"                    # 就绪
    DEGRADED = "degraded"             # 降级运行
    ERROR = "error"                   # 错误
    UNLOADED = "unloaded"             # 已卸载


# ── 请求数据模型 ───────────────────────────────────────────────────

@dataclass
class ChatMessage:
    """聊天消息"""
    role: str                  # "system" | "user" | "assistant" | "tool"
    content: str
    name: Optional[str] = None           # 发送者名称
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatRequest:
    """聊天请求"""
    messages: List[ChatMessage]
    model: str = ""                      # 模型标识（可为空=使用驱动默认）
    temperature: float = 0.7
    top_p: float = 1.0
    top_k: int = 0
    max_tokens: int = 2048
    stop: List[str] = field(default_factory=list)
    stream: bool = True
    tools: Optional[List[Dict]] = None   # 工具定义（function calling）
    extra: Dict[str, Any] = field(default_factory=dict)  # 驱动特定参数


@dataclass
class UsageInfo:
    """Token 使用信息"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class StreamChunk:
    """流式响应块"""
    delta: str = ""                      # 内容增量
    done: bool = False                   # 是否结束
    reasoning: str = ""                  # 推理内容（DeepSeek-R1 / QwQ 等）
    tool_calls: Optional[List[Dict]] = None
    usage: Optional[UsageInfo] = None
    error: str = ""                      # 错误信息


@dataclass
class ChatResponse:
    """聊天完整响应"""
    content: str = ""
    reasoning: str = ""
    tool_calls: Optional[List[Dict]] = None
    usage: UsageInfo = field(default_factory=UsageInfo)
    model: str = ""
    finish_reason: str = ""
    error: str = ""


@dataclass
class CompletionRequest:
    """补全请求（兼容旧接口）"""
    prompt: str
    model: str = ""
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 2048
    stop: List[str] = field(default_factory=list)
    stream: bool = True
    echo: bool = False


@dataclass
class CompletionResponse:
    """补全响应"""
    text: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    model: str = ""
    finish_reason: str = ""
    error: str = ""


@dataclass
class EmbeddingRequest:
    """嵌入请求"""
    texts: List[str]
    model: str = ""
    encoding_format: str = "float"  # "float" | "base64"


@dataclass
class EmbeddingResponse:
    """嵌入响应"""
    embeddings: List[List[float]] = field(default_factory=list)
    model: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    error: str = ""


# ── 健康报告 ───────────────────────────────────────────────────────

@dataclass
class HealthReport:
    """驱动健康报告"""
    healthy: bool = False
    state: DriverState = DriverState.UNINITIALIZED
    latency_ms: float = 0.0            # 最近一次请求延迟
    error_count: int = 0                # 连续错误次数
    total_requests: int = 0
    total_errors: int = 0
    last_error: str = ""
    uptime_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


# ── 驱动抽象基类 ──────────────────────────────────────────────────

class ModelDriver(ABC):
    """
    模型驱动抽象基类

    所有三种驱动（硬加载/本地服务/云服务）都必须实现此接口。
    上层代码通过此接口与驱动交互，无需关心底层实现。
    """

    def __init__(self, name: str, mode: DriverMode):
        self.name = name
        self.mode = mode
        self._state = DriverState.UNINITIALIZED
        self._start_time: float = 0.0
        self._error_count: int = 0
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._last_error: str = ""
        self._last_latency: float = 0.0

    @property
    def state(self) -> DriverState:
        return self._state

    @property
    def mode_value(self) -> DriverMode:
        return self.mode

    # ── 生命周期 ─────────────────────────────────────────────

    @abstractmethod
    def initialize(self) -> bool:
        """初始化驱动（加载模型/连接服务等）"""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """关闭驱动，释放资源"""
        ...

    @abstractmethod
    def health_check(self) -> HealthReport:
        """健康检查"""
        ...

    # ── 核心推理接口 ─────────────────────────────────────────

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话"""
        ...

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]:
        """流式对话"""
        ...

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """文本补全"""
        ...

    @abstractmethod
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """文本嵌入"""
        ...

    # ── 模型管理 ─────────────────────────────────────────────

    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        ...

    @abstractmethod
    def is_model_loaded(self, model: str) -> bool:
        """检查指定模型是否已加载/可用"""
        ...

    # ── 内部辅助 ─────────────────────────────────────────────

    def _set_state(self, state: DriverState) -> None:
        """更新驱动状态"""
        old = self._state
        self._state = state
        if state == DriverState.READY and old != DriverState.READY:
            self._start_time = time.time()

    def _record_success(self, latency_ms: float) -> None:
        self._total_requests += 1
        self._last_latency = latency_ms
        self._error_count = 0  # 重置连续错误计数

    def _record_error(self, error: str) -> None:
        self._total_requests += 1
        self._total_errors += 1
        self._error_count += 1
        self._last_error = error

    def _build_health(self, details: Dict[str, Any] | None = None) -> HealthReport:
        """构建健康报告"""
        return HealthReport(
            healthy=self._state == DriverState.READY,
            state=self._state,
            latency_ms=self._last_latency,
            error_count=self._error_count,
            total_requests=self._total_requests,
            total_errors=self._total_errors,
            last_error=self._last_error,
            uptime_seconds=time.time() - self._start_time if self._start_time else 0.0,
            details=details or {},
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} mode={self.mode.value} state={self._state.value}>"
