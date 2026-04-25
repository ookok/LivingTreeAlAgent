"""
意图结果 - 定义意图执行结果的数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict


class IntentStatus(Enum):
    """意图执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"     # 部分成功
    PENDING = "pending"     # 待处理
    RUNNING = "running"     # 执行中
    CANCELLED = "cancelled" # 已取消


@dataclass
class IntentResult:
    """
    意图执行结果
    
    Attributes:
        status: 执行状态
        intent_type: 意图类型
        output: 执行输出
        error: 错误信息
        metadata: 元数据
        suggestions: 建议
        context_updates: 上下文更新
    """
    status: IntentStatus = IntentStatus.PENDING
    intent_type: str = ""
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    context_updates: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """是否成功"""
        return self.status == IntentStatus.SUCCESS
    
    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == IntentStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'status': self.status.value,
            'intent_type': self.intent_type,
            'output': self.output,
            'error': self.error,
            'metadata': self.metadata,
            'suggestions': self.suggestions,
            'context_updates': self.context_updates,
        }
