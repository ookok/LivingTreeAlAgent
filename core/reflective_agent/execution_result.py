"""
反思式Agent执行结果数据模型

定义执行结果的统一数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


@dataclass
class ExecutionContext:
    """
    执行上下文

    在错误处理时传递上下文信息
    """
    task: str = ""
    step_id: Optional[str] = None
    plan_id: Optional[str] = None
    attempt: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "step_id": self.step_id,
            "plan_id": self.plan_id,
            "attempt": self.attempt,
            "metadata": self.metadata
        }


class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误分类"""
    SYNTAX = "syntax_error"
    LOGIC = "logic_error"
    RESOURCE = "resource_error"
    TIMEOUT = "timeout_error"
    KNOWLEDGE_GAP = "knowledge_gap"
    API = "api_error"
    MODEL = "model_error"
    UNKNOWN = "unknown"


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    name: str
    description: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "metrics": self.metrics
        }


@dataclass
class ExecutionError:
    """执行错误"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    recovered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "recovered": self.recovered
        }


@dataclass
class ExecutionMetrics:
    """执行指标"""
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    total_duration_ms: float = 0.0
    token_usage: int = 0
    cache_hit_rate: float = 0.0
    quality_score: float = 0.0  # 0.0 - 1.0
    confidence: float = 0.0     # 0.0 - 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "total_duration_ms": self.total_duration_ms,
            "token_usage": self.token_usage,
            "cache_hit_rate": self.cache_hit_rate,
            "quality_score": self.quality_score,
            "confidence": self.confidence
        }


@dataclass
class ExecutionResult:
    """
    执行结果容器

    包含完整的执行过程信息和结果
    """

    # 基础信息
    task: str
    status: ExecutionStatus
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # 执行过程
    steps: List[ExecutionStep] = field(default_factory=list)
    errors: List[ExecutionError] = field(default_factory=list)
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    # 执行历史（用于反思）
    execution_history: List[Dict[str, Any]] = field(default_factory=list)

    # 结果
    final_result: Optional[Any] = None
    reflection_notes: str = ""
    improvements_applied: List[str] = field(default_factory=list)

    # 元数据
    attempt_number: int = 1
    max_attempts: int = 3
    parent_result_id: Optional[str] = None  # 用于追踪多次尝试

    def add_step(self, step: ExecutionStep):
        """添加执行步骤"""
        self.steps.append(step)
        self.metrics.total_steps += 1

        if step.status == ExecutionStatus.SUCCESS:
            self.metrics.completed_steps += 1
        elif step.status == ExecutionStatus.FAILED:
            self.metrics.failed_steps += 1

    def add_error(self, error: ExecutionError):
        """添加错误"""
        self.errors.append(error)

    def mark_success(self):
        """标记为成功"""
        self.status = ExecutionStatus.SUCCESS
        self.end_time = datetime.now()

        # 计算总时长
        if self.start_time:
            self.metrics.total_duration_ms = (
                self.end_time - self.start_time
            ).total_seconds() * 1000

    def mark_failed(self, reason: str):
        """标记为失败"""
        self.status = ExecutionStatus.FAILED
        self.end_time = datetime.now()
        self.final_result = {"error": reason}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task": self.task,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "steps": [s.to_dict() for s in self.steps],
            "errors": [e.to_dict() for e in self.errors],
            "metrics": self.metrics.to_dict(),
            "final_result": str(self.final_result)[:1000] if self.final_result else None,
            "reflection_notes": self.reflection_notes,
            "improvements_applied": self.improvements_applied,
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts
        }

    @property
    def success(self) -> bool:
        """是否成功"""
        return self.status == ExecutionStatus.SUCCESS

    @property
    def total_duration_ms(self) -> float:
        """总执行时长(ms)"""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return self.metrics.total_duration_ms

    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.metrics.total_steps == 0:
            return 0.0
        return self.metrics.failed_steps / self.metrics.total_steps

    @property
    def completion_rate(self) -> float:
        """完成率"""
        if self.metrics.total_steps == 0:
            return 0.0
        return self.metrics.completed_steps / self.metrics.total_steps
