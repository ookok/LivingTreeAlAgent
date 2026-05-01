"""
API响应封装 - API Response

功能：
1. 响应数据封装
2. 错误处理
3. 状态码管理
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class APIResponse:
    """API响应封装"""
    success: bool
    data: Any = None
    message: str = ""
    error_code: int = 0
    request_id: str = ""
    timestamp: float = None
    execution_time: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'success': self.success,
            'data': self.data,
            'message': self.message,
            'error_code': self.error_code,
            'request_id': self.request_id,
            'timestamp': self.timestamp,
            'execution_time': self.execution_time
        }
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", request_id: str = "") -> 'APIResponse':
        """创建成功响应"""
        return APIResponse(
            success=True,
            data=data,
            message=message,
            request_id=request_id
        )
    
    @staticmethod
    def error(error_code: int = 500, message: str = "操作失败", request_id: str = "") -> 'APIResponse':
        """创建错误响应"""
        return APIResponse(
            success=False,
            error_code=error_code,
            message=message,
            request_id=request_id
        )


@dataclass
class ErrorResponse:
    """错误响应"""
    error_code: int
    message: str
    details: Optional[str] = None
    request_id: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'request_id': self.request_id
        }