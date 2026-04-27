"""
ToolResult - 工具执行结果
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """工具执行结果"""
    
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        return self.success
    
    @property
    def is_success(self) -> bool:
        return self.success and self.error is None
    
    @property
    def is_failure(self) -> bool:
        return not self.success or self.error is not None
    
    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "ToolResult":
        """创建成功结果"""
        return cls(success=True, data=data, message=message)
    
    @classmethod
    def fail(cls, error: str, data: Any = None) -> "ToolResult":
        """创建失败结果"""
        return cls(success=False, data=data, error=error)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "ToolResult":
        """从字典创建"""
        return cls(
            success=d.get("success", True),
            data=d.get("data"),
            error=d.get("error"),
            message=d.get("message", ""),
            metadata=d.get("metadata", {})
        )
