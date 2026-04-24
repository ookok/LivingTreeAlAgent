"""
Agent Progress Tracker - 进度追踪器
=====================================

用于追踪 AI Agent 的执行进度，支持流式输出和 UI 进度条更新。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict, Any
from datetime import datetime
import time
import threading


class ProgressPhase(Enum):
    """Agent 执行阶段"""
    # 初始化
    INITIALIZING = "initializing"
    LOADING_MODEL = "loading_model"

    # 意图理解
    INTENT_CLASSIFY = "intent_classify"
    CONTEXT_PARSING = "context_parsing"

    # 任务处理
    THINKING = "thinking"
    DECOMPOSING = "decomposing"
    EXECUTING = "executing"

    # 搜索
    KNOWLEDGE_SEARCH = "knowledge_search"
    DEEP_SEARCH = "deep_search"
    WEB_SEARCH = "web_search"

    # 模型
    MODEL_ROUTE = "model_route"
    LLM_GENERATING = "llm_generating"
    THINKING_GENERATING = "thinking_generating"

    # 输出
    FORMATTING = "formatting"
    STREAMING = "streaming"

    # 完成
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentProgress:
    """Agent 进度信息"""
    phase: ProgressPhase
    message: str
    progress: float = 0.0  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "phase": self.phase.value,
            "message": self.message,
            "progress": self.progress,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ProgressEmitter:
    """
    进度发射器

    将进度信息发射到 UI 或其他订阅者
    """

    def __init__(self, callback: Optional[Callable[[AgentProgress], None]] = None):
        self.callback = callback
        self.current_phase: Optional[ProgressPhase] = None
        self.current_message: str = ""
        self.start_time: Optional[float] = None
        self._lock = threading.Lock()

    def start(self):
        """开始追踪"""
        self.start_time = time.time()

    def emit_phase(
        self,
        phase: ProgressPhase,
        message: str,
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        发射阶段更新

        Args:
            phase: 当前阶段
            message: 阶段消息
            progress: 进度 (0.0-1.0)，可选
            metadata: 附加数据
        """
        with self._lock:
            self.current_phase = phase
            self.current_message = message

            # 计算进度
            if progress is None:
                progress = self._estimate_progress(phase)

            progress_info = AgentProgress(
                phase=phase,
                message=message,
                progress=progress,
                metadata=metadata or {}
            )

            # 调用回调
            if self.callback:
                try:
                    self.callback(progress_info)
                except Exception as e:
                    print(f"[ProgressEmitter] Callback error: {e}")

    def _estimate_progress(self, phase: ProgressPhase) -> float:
        """估算阶段进度"""
        progress_map = {
            # 初始化阶段
            ProgressPhase.INITIALIZING: 0.05,
            ProgressPhase.LOADING_MODEL: 0.10,

            # 意图理解
            ProgressPhase.INTENT_CLASSIFY: 0.15,
            ProgressPhase.CONTEXT_PARSING: 0.20,

            # 任务处理
            ProgressPhase.THINKING: 0.25,
            ProgressPhase.DECOMPOSING: 0.30,
            ProgressPhase.EXECUTING: 0.50,

            # 搜索
            ProgressPhase.KNOWLEDGE_SEARCH: 0.40,
            ProgressPhase.DEEP_SEARCH: 0.55,
            ProgressPhase.WEB_SEARCH: 0.60,

            # 模型
            ProgressPhase.MODEL_ROUTE: 0.65,
            ProgressPhase.LLM_GENERATING: 0.70,
            ProgressPhase.THINKING_GENERATING: 0.75,

            # 输出
            ProgressPhase.FORMATTING: 0.90,
            ProgressPhase.STREAMING: 0.95,

            # 完成
            ProgressPhase.COMPLETED: 1.0,
            ProgressPhase.ERROR: 0.0,
        }
        return progress_map.get(phase, 0.5)

    def complete(self, message: str = "完成"):
        """标记完成"""
        self.emit_phase(ProgressPhase.COMPLETED, message, 1.0)

    def error(self, message: str):
        """标记错误"""
        self.emit_phase(ProgressPhase.ERROR, message, 0.0)

    def get_current(self) -> Optional[AgentProgress]:
        """获取当前进度"""
        if self.current_phase:
            return AgentProgress(
                phase=self.current_phase,
                message=self.current_message,
                progress=self._estimate_progress(self.current_phase),
            )
        return None


class ProgressTracker:
    """
    全局进度追踪器

    支持多个订阅者，可追踪多个 Agent 实例
    """

    def __init__(self):
        self._emitters: Dict[str, ProgressEmitter] = {}
        self._lock = threading.Lock()

    def create_emitter(
        self,
        agent_id: str,
        callback: Optional[Callable[[AgentProgress], None]] = None
    ) -> ProgressEmitter:
        """为指定 Agent 创建发射器"""
        with self._lock:
            emitter = ProgressEmitter(callback)
            self._emitters[agent_id] = emitter
            return emitter

    def get_emitter(self, agent_id: str) -> Optional[ProgressEmitter]:
        """获取发射器"""
        return self._emitters.get(agent_id)

    def remove_emitter(self, agent_id: str):
        """移除发射器"""
        with self._lock:
            self._emitters.pop(agent_id, None)

    def emit_to_all(
        self,
        phase: ProgressPhase,
        message: str,
        progress: Optional[float] = None
    ):
        """向所有发射器广播"""
        with self._lock:
            for emitter in self._emitters.values():
                emitter.emit_phase(phase, message, progress)


# 全局实例
_progress_tracker: Optional[ProgressTracker] = None
_tracker_lock = threading.Lock()


def get_progress_tracker() -> ProgressTracker:
    """获取全局进度追踪器单例"""
    global _progress_tracker
    with _tracker_lock:
        if _progress_tracker is None:
            _progress_tracker = ProgressTracker()
        return _progress_tracker


def create_emitter(
    agent_id: str,
    callback: Optional[Callable[[AgentProgress], None]] = None
) -> ProgressEmitter:
    """便捷函数：创建发射器"""
    tracker = get_progress_tracker()
    return tracker.create_emitter(agent_id, callback)


# ═══════════════════════════════════════════════════════════════════════════
# 流式进度支持
# ═══════════════════════════════════════════════════════════════════════════

class StreamProgressHandler:
    """
    流式输出进度处理器

    用于处理流式 LLM 输出时的进度显示
    """

    def __init__(
        self,
        emitter: ProgressEmitter,
        phase: ProgressPhase = ProgressPhase.LLM_GENERATING,
        chunk_callback: Optional[Callable[[str], None]] = None
    ):
        self.emitter = emitter
        self.phase = phase
        self.chunk_callback = chunk_callback
        self.buffer = ""
        self.start_time = time.time()
        self.chunk_count = 0

    def process_chunk(self, chunk: str) -> str:
        """处理单个 chunk"""
        self.buffer += chunk
        self.chunk_count += 1

        # 更新进度（基于时间估算）
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            # 简单估算：每秒约 10 个 chunk
            estimated_progress = min(0.95, 0.70 + (elapsed * 0.1))
            self.emitter.emit_phase(
                self.phase,
                f"生成中... ({self.chunk_count} chunks)",
                estimated_progress
            )

        if self.chunk_callback:
            self.chunk_callback(chunk)

        return chunk

    def finalize(self):
        """完成处理"""
        self.emitter.complete(f"生成完成 ({self.chunk_count} tokens)")
